"""Call the pinned external TVP author code and independently audit its algebra.

No GPL implementation is vendored here. The covariance identity below is derived
from a random-walk coefficient prior, independently of the native augmented basis.
This is an estimator integration, not yet the quarterly Table 4 experiment.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

TVP_COMMIT = "d2d52bb9e0126fb580fb8301f305035d3047b4b2"
TVP_SHA256 = "1cc6cce8fb7f3524469b37328519097908f56c56631b09bc6feb512402142a45"
TVP_URL = f"https://raw.githubusercontent.com/philgoucou/tvpridge/{TVP_COMMIT}/R/MV2SRR_v210407.R"
DEFAULT_SETTINGS = {
    "lambda_candidates": np.exp(np.linspace(-6, 20, 15)).tolist(),
    "lambda2": 0.1,
    "kfold": 5,
    "sig_u": 0.75,
    "sig_eps": 0.75,
    "ols_prior": 0,
    "CV_2SRR": True,
}
REQUIRED_PACKAGES = {"pracma": "2.4.6", "fGarch": "4052.93", "matrixcalc": "1.0.6"}


def ensure_tvp_engine(path: Path) -> dict:
    if path.exists():
        payload = path.read_bytes()
    else:
        response = httpx.get(TVP_URL, timeout=60, follow_redirects=True)
        response.raise_for_status()
        payload = response.content
    if hashlib.sha256(payload).hexdigest() != TVP_SHA256:
        raise ValueError("TVP author source checksum mismatch")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return {
        "commit": TVP_COMMIT,
        "sha256": TVP_SHA256,
        "url": TVP_URL,
        "license": "GPL-3 external dependency; not redistributed as MIT",
    }


def validate_settings(settings: dict) -> None:
    if set(settings) != set(DEFAULT_SETTINGS):
        raise ValueError("Unexpected or missing TVP settings")
    candidates = np.asarray(settings["lambda_candidates"], dtype=float)
    if (
        candidates.ndim != 1
        or len(candidates) < 2
        or not np.isfinite(candidates).all()
        or np.any(candidates <= 0)
        or np.any(np.diff(candidates) <= 0)
    ):
        raise ValueError("TVP candidates must be finite, positive and increasing")
    if (
        isinstance(settings["kfold"], bool)
        or not isinstance(settings["kfold"], int)
        or not 2 <= settings["kfold"] <= 10
    ):
        raise ValueError("Invalid TVP fold count")
    if not np.isfinite(settings["lambda2"]) or settings["lambda2"] < 1e-7:
        raise ValueError("Invalid TVP initial-level penalty")
    if any(not np.isfinite(settings[k]) or not 0 < settings[k] <= 1 for k in ("sig_u", "sig_eps")):
        raise ValueError("This adapter requires both native second-step updates")
    if settings["ols_prior"] != 0 or settings["CV_2SRR"] is not True:
        raise ValueError("This adapter audits the zero-level prior and second CV")


def validate_inputs(x, y, forecast_x):
    x, y, forecast_x = (np.asarray(a, dtype=float) for a in (x, y, forecast_x))
    if (
        x.ndim != 2
        or forecast_x.ndim != 2
        or y.shape != (len(x),)
        or len(x) < 30
        or not 1 <= x.shape[1] < len(x) - 2
        or forecast_x.shape[1] != x.shape[1]
        or not len(forecast_x)
        or not all(np.isfinite(a).all() for a in (x, y, forecast_x))
    ):
        raise ValueError("Invalid finite TVP training/forecast arrays")
    if np.any(x.std(axis=0, ddof=1) <= 1e-12) or y.std(ddof=1) <= 1e-12:
        raise ValueError("Native TVP variance scaling requires nonconstant training inputs")
    return x, y, forecast_x


def random_walk_solution(a, y, penalty, level_penalty, increment_weights=None, noise_weights=None):
    """Independent integrated random-walk covariance solution, including beta_0.

    Minimize sum(error_t^2 / noise_t) + level_penalty*||beta_0||^2
    + sum_j,t penalty/increment_weight_j * (beta_tj-beta_(t-1)j)^2.
    The first row of a is time zero; a includes the explicit intercept.
    """
    a, y = np.asarray(a, float), np.asarray(y, float)
    if a.ndim != 2 or y.shape != (len(a),) or len(a) < 2:
        raise ValueError("Invalid random-walk dimensions")
    n, p = a.shape
    w = np.ones(p) if increment_weights is None else np.asarray(increment_weights, float)
    e = np.ones(n) if noise_weights is None else np.asarray(noise_weights, float)
    if (
        w.shape != (p,)
        or e.shape != (n,)
        or not all(np.isfinite(z).all() for z in (a, y, w, e))
        or np.any(w <= 0)
        or np.any(e <= 0)
        or not np.isfinite(penalty)
        or not np.isfinite(level_penalty)
        or penalty <= 0
        or level_penalty <= 0
    ):
        raise ValueError("Invalid random-walk data or penalties")
    time_overlap = np.minimum.outer(np.arange(n), np.arange(n))
    covariance = (a * (w / penalty)) @ a.T * time_overlap + a @ a.T / level_penalty
    alpha = np.linalg.solve(covariance + np.diag(e), y)
    beta = time_overlap @ (a * alpha[:, None]) * (w / penalty)
    beta += (a.T @ alpha / level_penalty)[None, :]
    return beta, np.einsum("ij,ij->i", a, beta)


def native_cv_scores(
    a, y, folds, candidates, level_penalty, increment_weights=None, noise_weights=None
):
    """Independently express the pinned code's CV using time-covariance matrices.

    Preserve its random folds, ridge partialling, asymmetric dropout correction,
    squared increment weights, and equal fold weighting. This is not rolling CV.
    """
    a, y, folds = np.asarray(a, float), np.asarray(y, float), np.asarray(folds)
    candidates = np.asarray(candidates, float)
    if a.ndim != 2 or len(a) < 4 or a.shape[1] < 1:
        raise ValueError("Invalid native CV design")
    n, p = a.shape
    w = np.ones(p) if increment_weights is None else np.asarray(increment_weights, float)
    e = np.ones(n) if noise_weights is None else np.asarray(noise_weights, float)
    if (
        y.shape != (n,)
        or folds.shape != (n,)
        or w.shape != (p,)
        or e.shape != (n,)
        or not np.issubdtype(folds.dtype, np.integer)
        or sorted(set(folds)) != list(range(1, int(max(folds)) + 1))
        or min(folds) != 1
        or max(folds) < 2
        or candidates.ndim != 1
        or not len(candidates)
        or not all(np.isfinite(z).all() for z in (a, y, w, e, candidates))
        or np.any(w <= 0)
        or np.any(e <= 0)
        or np.any(candidates <= 0)
        or not np.isfinite(level_penalty)
        or level_penalty <= 0
    ):
        raise ValueError("Invalid native CV arrays")
    overlap = np.minimum.outer(np.arange(n), np.arange(n))
    error = []
    for fold in range(1, int(max(folds)) + 1):
        test, train = np.flatnonzero(folds == fold), np.flatnonzero(folds != fold)
        dropout = np.ones(n)
        run = 0
        for i in range(n):
            run = run + 1 if folds[i] == fold else 0
            dropout[i] += run
        train_time = np.r_[0.0, np.cumsum(dropout[1:] ** 2)]
        cross_time = np.r_[0.0, np.cumsum(dropout[1:])]
        raw_train = (a * w**2) @ a.T * train_time[overlap] + a @ a.T
        raw_cross = (a * w**2) @ a.T * cross_time[overlap] + a @ a.T

        def partial(rows):
            ar = a[rows]
            return np.eye(len(rows)) - ar @ np.linalg.solve(
                ar.T @ ar + level_penalty * np.eye(p), ar.T
            )

        mt, mv = partial(train), partial(test)
        kt = mt @ raw_train[np.ix_(train, train)] @ mt.T
        kv = mv @ raw_cross[np.ix_(test, train)] @ mt.T
        yt, yv = mt @ y[train], mv @ y[test]
        error.append(
            [
                float(np.mean((kv @ np.linalg.solve(kt + c * np.diag(e[train]), yt) - yv) ** 2))
                for c in candidates
            ]
        )
    return np.asarray(error)


def _dcf(path):
    entries = [line.split(": ", 1) for line in path.read_text().splitlines() if line]
    if any(len(entry) != 2 for entry in entries) or len({e[0] for e in entries}) != len(entries):
        raise ValueError("Invalid or duplicated TVP DCF entries")
    return {key: value.strip() for key, value in entries}


def _input_hashes(directory):
    return {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in ("train.csv", "forecast_x.csv", "settings.dcf")
    }


def _code_hashes():
    return {
        "reference_tvp.R": hashlib.sha256(
            files("jev_factor").joinpath("reference_tvp.R").read_bytes()
        ).hexdigest(),
        "tvp_ridge.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def _close(actual, expected, label, tolerance=1e-7):
    actual, expected = np.asarray(actual), np.asarray(expected)
    if actual.shape != expected.shape or not np.isfinite(actual).all():
        raise ValueError(f"Invalid native TVP {label} shape/value")
    difference = float(np.max(np.abs(actual - expected)))
    if difference > tolerance:
        raise ValueError(f"Native TVP {label} disagrees: {difference}")
    return difference


@threadpool_limits.wrap(limits=1)
def audit_tvp_output(directory: Path, settings: dict) -> dict:
    """Reconstruct both weighted ridge stages, both CV stages and all forecasts."""
    validate_settings(settings)
    manifest = json.loads((directory / "manifest.json").read_text())
    if (
        manifest["settings"] != settings
        or manifest["input_sha256"] != _input_hashes(directory)
        or manifest["code_sha256"] != _code_hashes()
        or manifest["external_source"]["sha256"] != TVP_SHA256
        or manifest["external_source"]["commit"] != TVP_COMMIT
        or manifest["external_source"]["url"] != TVP_URL
    ):
        raise ValueError("Changed TVP input, settings or source provenance")
    train = pd.read_csv(directory / "train.csv")
    forecast = pd.read_csv(directory / "forecast_x.csv")
    x, y, test = validate_inputs(train.drop(columns="target"), train.target, forecast)
    expected_x = [f"x{j}" for j in range(x.shape[1])]
    expected_terms = ["intercept", *expected_x]
    if list(train) != ["target", *expected_x] or list(forecast) != expected_x:
        raise ValueError("Changed TVP input column schema/order")
    scale_x, scale_y = x.std(axis=0, ddof=1), y.std(ddof=1)
    a = np.column_stack([np.ones(len(x)), x / scale_x])
    ys = y / scale_y  # Native code divides sample SDs; it does not demean.
    factor = np.r_[scale_y, scale_y / scale_x]
    first_frame = pd.read_csv(directory / "beta_rr.csv")
    second_frame = pd.read_csv(directory / "beta_2srr.csv")
    if list(first_frame) != expected_terms or list(second_frame) != expected_terms:
        raise ValueError("Changed TVP coefficient schema/order")
    rr = first_frame.to_numpy() / factor
    second = second_frame.to_numpy() / factor
    fitting = pd.read_csv(directory / "fitted.csv")
    volatility = pd.read_csv(directory / "volatility.csv")
    meta = _dcf(directory / "native.dcf")
    candidates = np.asarray(settings["lambda_candidates"])
    indices = [int(meta[f"lambda_{s}_index"]) - 1 for s in ("step1", "step2")]
    if any(i < 0 or i >= len(candidates) for i in indices):
        raise ValueError("Native TVP selected an undeclared lambda index")
    first_lambda, second_lambda = candidates[indices]
    for label, value in zip(("step1", "step2"), (first_lambda, second_lambda), strict=True):
        # R's text-to-double conversion can differ by one ULP on the exp grid.
        # Bind the discrete candidate index, and allow only serialization roundoff.
        if not np.isclose(float(meta[f"lambda_{label}"]), value, rtol=2e-15, atol=0):
            raise ValueError("Native TVP lambda value disagrees with its candidate index")
    returned_lambda = float(meta["lambda_returned"])
    if not np.isclose(returned_lambda, first_lambda, rtol=2e-15, atol=0):
        raise ValueError("Native public lambda return changed its meaning")
    for package, version in REQUIRED_PACKAGES.items():
        if meta[f"version_{package}"] != version:
            raise ValueError(f"Unexpected TVP package version for {package}")
    folds = pd.read_csv(directory / "folds.csv")
    if list(folds) != ["first", "second"]:
        raise ValueError("Invalid native fold record")
    if not np.array_equal(folds["first"], folds["second"]):
        raise ValueError("Native fixed-seed CV stages use inconsistent folds")
    if set(folds["first"]) != set(range(1, settings["kfold"] + 1)):
        raise ValueError("Native fold count differs from declaration")
    initial, initial_fit = random_walk_solution(a, ys, first_lambda, settings["lambda2"])
    differences = {
        "first_step_coefficients_standardized": _close(rr, initial, "first coefficients")
    }
    differences["first_step_fitted_standardized"] = _close(
        fitting.rr.to_numpy() / scale_y, initial_fit, "first fit"
    )
    innovations = np.sum(np.diff(initial, axis=0) ** 2, axis=0) ** settings["sig_u"]
    innovations /= innovations.mean()
    native_innovations = pd.read_csv(directory / "increment_weights.csv").weight.to_numpy()
    differences["increment_weights"] = _close(native_innovations, innovations, "increment weights")
    raw_residual = ys - initial_fit
    threshold = 50 * 1.4826 * np.median(np.abs(raw_residual - np.median(raw_residual)))
    clipped = np.where(np.abs(raw_residual) > threshold, 0, raw_residual)
    differences["GARCH_input"] = _close(volatility.input.to_numpy(), clipped, "GARCH residual")
    sigma = volatility.sigma.to_numpy()
    if sigma.shape != y.shape or not np.isfinite(sigma).all() or np.any(sigma <= 0):
        raise ValueError("Invalid GARCH conditional SD")
    noise = sigma ** settings["sig_eps"]
    noise /= noise.mean()
    differences["noise_weights"] = _close(volatility.weight.to_numpy(), noise, "noise weights")
    parameters = pd.read_csv(directory / "garch_coefficients.csv").set_index("term").coefficient
    if set(parameters.index) != {"mu", "omega", "alpha1", "beta1"}:
        raise ValueError("Unexpected GARCH specification")
    variance = (
        parameters["omega"]
        + parameters["alpha1"] * (clipped[:-1] - parameters["mu"]) ** 2
        + parameters["beta1"] * sigma[:-1] ** 2
    )
    differences["GARCH_variance_recursion"] = _close(sigma[1:] ** 2, variance, "GARCH recursion")
    final, final_fit = random_walk_solution(
        a, ys, second_lambda, settings["lambda2"], native_innovations, noise
    )
    differences["second_step_coefficients_standardized"] = _close(
        second, final, "second coefficients"
    )
    differences["second_step_fitted_standardized"] = _close(
        fitting.second.to_numpy() / scale_y, final_fit, "second fit"
    )
    for stage, weights in (
        ("first", {}),
        ("second", {"increment_weights": innovations, "noise_weights": noise}),
    ):
        cv = native_cv_scores(
            a, ys, folds[stage].to_numpy(), candidates, settings["lambda2"], **weights
        )
        recorded = pd.read_csv(directory / f"cv_{stage}.csv").to_numpy()
        differences[f"{stage}_CV_fold_scores"] = _close(recorded, cv, f"{stage} CV")
        selected = int(np.argmin(cv.mean(axis=0)))
        if selected != indices[0 if stage == "first" else 1]:
            raise ValueError(f"Native {stage} CV minimum disagrees")
    predictions = pd.read_csv(directory / "predictions.csv").prediction.to_numpy()
    expected = np.column_stack([np.ones(len(test)), test]) @ (final[-1] * factor)
    differences["forecast_standardized"] = _close(
        predictions / scale_y, expected / scale_y, "forecast"
    )
    differences["native_first_forecast_standardized"] = _close(
        np.array([float(meta["public_first_forecast"])]) / scale_y,
        expected[:1] / scale_y,
        "public forecast",
    )
    return {
        "status": "native_TVP_algebra_verified_not_quarterly_benchmark",
        "training_rows": len(x),
        "forecast_rows": len(test),
        "coefficients": a.shape[1],
        "lambda_step1": first_lambda,
        "lambda_step2": second_lambda,
        "public_lambda_return_is_first_step_only": True,
        "CV_folds": settings["kfold"],
        "native_CV_seed": 1071,
        "native_random_CV_is_not_chronological": True,
        "GARCH_optimizer_convergence_code": int(meta["garch_convergence"]),
        "GARCH_optimizer_converged": int(meta["garch_convergence"]) == 0,
        "maximum_absolute_differences": differences,
        "runtime": meta,
        "input_sha256": manifest["input_sha256"],
        "code_sha256": manifest["code_sha256"],
        "external_source": manifest["external_source"],
        "settings": settings,
        "wrapper_sha256": manifest["code_sha256"]["reference_tvp.R"],
        "verifier_sha256": manifest["code_sha256"]["tvp_ridge.py"],
        "quarterly_benchmark_completed": False,
        "exact_author_table_pipeline_recovered": False,
    }


def run_native_tvp(x, y, forecast_x, engine, library, directory, settings=None, rscript="Rscript"):
    """Execute the actual pinned external entry point on training outcomes only."""
    settings = json.loads(json.dumps(DEFAULT_SETTINGS if settings is None else settings))
    validate_settings(settings)
    x, y, forecast_x = validate_inputs(x, y, forecast_x)
    engine, library, directory = (Path(p).resolve() for p in (engine, library, directory))
    if directory.exists():
        raise FileExistsError("Choose a fresh TVP fit directory")
    if not library.is_dir():
        raise ValueError("TVP requires a prepared, project-local R library")
    provenance = ensure_tvp_engine(engine)
    rscript_path = shutil.which(rscript)
    if not rscript_path:
        raise RuntimeError("Rscript is required for the native TVP estimator")
    directory.mkdir(parents=True)
    train = pd.DataFrame(x, columns=[f"x{j}" for j in range(x.shape[1])])
    train.insert(0, "target", y)
    train.to_csv(directory / "train.csv", index=False, float_format="%.17g")
    pd.DataFrame(forecast_x, columns=train.columns[1:]).to_csv(
        directory / "forecast_x.csv", index=False, float_format="%.17g"
    )
    fields = {
        **settings,
        "lambda_candidates": ",".join(format(z, ".17g") for z in settings["lambda_candidates"]),
    }
    (directory / "settings.dcf").write_text(
        "\n".join(f"{k}: {v}" for k, v in fields.items()) + "\n"
    )
    wrapper = Path(str(files("jev_factor").joinpath("reference_tvp.R")))
    manifest = {
        "settings": settings,
        "input_sha256": _input_hashes(directory),
        "code_sha256": _code_hashes(),
        "external_source": provenance,
        "status": "native_estimator_prepared_not_quarterly_benchmark",
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    result = subprocess.run(
        [rscript_path, "--vanilla", str(wrapper), str(engine), str(library), str(directory)],
        cwd=directory,
        env={**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"},
        text=True,
        capture_output=True,
        timeout=300,
    )
    (directory / "native_stdout.txt").write_text(result.stdout)
    (directory / "native_stderr.txt").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(
            f"Native TVP failed; retained logs in {directory}: {result.stderr[-1500:]}"
        )
    ensure_tvp_engine(engine)  # Reject a source changed during the native call.
    audit = audit_tvp_output(directory, settings)
    audit["external_source"] = provenance
    audit["settings"] = settings
    audit["wrapper_sha256"] = hashlib.sha256(wrapper.read_bytes()).hexdigest()
    audit["verifier_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (directory / "audit.json").write_text(json.dumps(audit, indent=2, allow_nan=False) + "\n")
    return audit
