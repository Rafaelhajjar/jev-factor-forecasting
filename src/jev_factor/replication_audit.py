"""Verify saved reconstruction artifacts rather than trusting completion flags."""

from __future__ import annotations

import hashlib
import json
import subprocess
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from jev_factor.quarterly import load_quarterly, make_design
from jev_factor.replication import AUTHOR_COMMIT, AUTHOR_SHA256, LINEAR_X, score_table


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _close(actual, expected, label: str, atol: float = 1e-11) -> float:
    actual, expected = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    if actual.shape != expected.shape or not np.isfinite(actual).all():
        raise ValueError(f"Invalid shape/nonfinite values: {label}")
    if not np.allclose(actual, expected, atol=atol, rtol=1e-10, equal_nan=False):
        raise ValueError(f"Values differ: {label}")
    return float(np.max(np.abs(actual - expected))) if actual.size else 0.0


def _dcf(path: Path) -> dict[str, str]:
    return dict(line.split(": ", 1) for line in path.read_text().splitlines() if line.strip())


def check_engine_output(frame: pd.DataFrame, matrix: pd.DataFrame) -> float:
    expected = ["prediction", "intercept", *LINEAR_X]
    if set(frame) != set(expected) or len(frame) != len(matrix):
        raise ValueError("Invalid coefficient/forecast schema")
    if not np.isfinite(frame[expected].to_numpy()).all():
        raise ValueError("Nonfinite forest coefficient/forecast")
    reconstructed = frame.intercept.to_numpy() + np.sum(
        frame[LINEAR_X].to_numpy() * matrix[LINEAR_X].to_numpy(), axis=1
    )
    return _close(frame.prediction, reconstructed, "forecast/coefficient reconstruction")


def _r_linear(matrix: Path, ntrain: int, rscript: str, directory: Path) -> tuple[pd.DataFrame, str]:
    destination = directory / "linear_r.csv"
    script = files("jev_factor").joinpath("reference_linear.R")
    result = subprocess.run(
        [rscript, "--vanilla", str(script), str(matrix), str(ntrain), str(destination)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Independent R linear check failed: {result.stderr[-2000:]}")
    return pd.read_csv(destination), result.stdout.strip()


def audit_run(
    run: Path,
    archive: Path,
    declared_config: dict,
    *,
    rscript: str = "Rscript",
    allow_partial: bool = False,
) -> dict:
    """Read-only audit except for an isolated, automatically cleaned R scratch folder.

    A partial run never receives forest scores or a numerical reproduction pass.
    Matching scores never implies that the unknown author pipeline was recovered.
    """
    manifest = json.loads((run / "manifest.json").read_text())
    config = manifest["config"]
    if config["horizon"] != 1:
        raise ValueError("Audit currently covers the one-quarter unemployment reconstruction")
    if manifest["external_engine"]["commit"] != AUTHOR_COMMIT:
        raise ValueError("External engine revision differs")
    if manifest["external_engine"]["sha256"] != AUTHOR_SHA256:
        raise ValueError("External engine checksum differs")
    for name, digest in manifest["integration_source_sha256"].items():
        if _sha(Path(__file__).with_name(name)) != digest:
            raise ValueError(f"Integration source differs: {name}")
    if _sha(run / "reference_mrf.R") != manifest["integration_source_sha256"]["reference_mrf.R"]:
        raise ValueError("Run adapter snapshot differs")
    data = load_quarterly(archive)
    if manifest["data"] != data.metadata:
        raise ValueError("Archive metadata/provenance differs")
    # Independently obtain target and lag values from deposited levels.
    target = np.log(data.levels["UNRATE"]).diff()
    full_dates = pd.period_range(config["evaluation_start"], config["evaluation_end"], freq="Q")
    interval = config["refit_every_quarters"]
    starts = list(range(0, len(full_dates), interval))
    if manifest["max_refits"] is not None:
        starts = starts[: manifest["max_refits"]]
    expected_keys = {(g, seed) for g in range(len(starts)) for seed in config["seeds"]}
    keys = [(job["group"], job["seed"]) for job in manifest["jobs"]]
    if len(keys) != len(set(keys)) or set(keys) != expected_keys:
        raise ValueError("Missing or duplicate declared refit/seed jobs")
    dates = full_dates[: min(len(starts) * interval, len(full_dates))]
    baseline = pd.read_csv(run / "baseline_predictions.csv")
    if set(baseline.model) != {"AR4", "FA_AR"}:
        raise ValueError("Unexpected baseline model set")
    if set(baseline.target_date) != set(map(str, dates)):
        raise ValueError("Baseline evaluation dates differ")
    for model, frame in baseline.groupby("model"):
        _close(frame.actual, target.reindex(frame.target_date.map(pd.Period)), f"{model} targets")
        if not all(
            pd.Period(t) == pd.Period(o) + 1
            for t, o in zip(frame.target_date, frame.origin_date, strict=True)
        ):
            raise ValueError("Baseline origin/target timing differs")
    baseline_metrics = score_table(baseline)
    saved_baseline = pd.read_csv(run / "baseline_metrics.csv").set_index("model")
    if not saved_baseline.index.is_unique or set(saved_baseline.index) != set(
        baseline_metrics.model
    ):
        raise ValueError("Baseline metric model grid differs")
    numeric = ["n", "RMSE", "MAE", "RMSE_over_AR4"]
    _close(
        baseline_metrics[numeric],
        saved_baseline.reindex(baseline_metrics.model)[numeric],
        "saved baseline metrics",
    )
    completed, pending, matrices, linear_checks, state_checks, runtimes = [], [], {}, [], [], []
    frames = [baseline]
    worst_coefficient_error = 0.0
    for job in manifest["jobs"]:
        group = job["group"]
        group_dates = full_dates[starts[group] : starts[group] + interval]
        fit_end = group_dates[0] - 1
        if job["fit_end"] != str(fit_end):
            raise ValueError("Refit date differs from declared schedule")
        if [record["target_date"] for record in job["targets"]] != list(map(str, group_dates)):
            raise ValueError("Forest target-date grid differs")
        _close([r["actual"] for r in job["targets"]], target.reindex(group_dates), "forest targets")
        if [r["origin_date"] for r in job["targets"]] != list(map(str, group_dates - 1)):
            raise ValueError("Forest origin-date grid differs")
        for field in ["matrix", "settings"]:
            if _sha(Path(job[field])) != job[field + "_sha256"]:
                raise ValueError(f"Prepared {field} checksum differs")
        settings = _dcf(Path(job["settings"]))
        train_dates = pd.period_range(config["regression_start"], fit_end, freq="Q")
        ntrain = int(settings["ntrain"])
        if ntrain != len(train_dates) or int(settings["seed"]) != job["seed"]:
            raise ValueError("Training length or seed differs")
        if settings["xnames"].split(",") != LINEAR_X:
            raise ValueError("Unexpected forest equation terms")
        for name in [
            "trees",
            "block",
            "RWR",
            "ridge_lambda",
            "MLF",
            "mtry",
            "minsize",
            "trend_push",
        ]:
            _close(float(settings[name]), float(config[name]), f"setting {name}")
        for name in ["prior", "standardization"]:
            if settings[name] != config[name]:
                raise ValueError(f"Setting differs: {name}")
        matrix = pd.read_csv(job["matrix"])
        if len(matrix) != ntrain + len(group_dates) or not np.isfinite(matrix.to_numpy()).all():
            raise ValueError("Nonfinite matrix or wrong train/test row count")
        _close(matrix.target.iloc[:ntrain], target.reindex(train_dates), "training targets")
        _close(
            matrix.target.iloc[ntrain:],
            np.repeat(matrix.target.iloc[:ntrain].mean(), len(group_dates)),
            "held-out target mask",
        )
        all_dates = train_dates.append(group_dates)
        for lag in range(1, 9):
            _close(matrix[f"y_lag{lag}"], target.shift(lag).reindex(all_dates), f"target lag {lag}")
        if group in matrices:
            if matrices[group] != job["matrix_sha256"]:
                raise ValueError("Seeds in one refit use different matrices")
        else:
            matrices[group] = job["matrix_sha256"]
            rebuilt, representation = make_design(
                data,
                fit_end,
                group_dates[-1],
                panel_start=config["panel_start"],
                rank=config["pca_rank"],
                outlier_iqr=config["outlier_iqr"],
                factor_panel=config["factor_panel"],
            )
            rebuilt = rebuilt.loc[config["regression_start"] :]
            training_std = rebuilt.loc[:fit_end].std(ddof=1)
            kept = [name for name in rebuilt if name == "target" or training_std[name] > 1e-10]
            rebuilt = rebuilt[kept].copy()
            rebuilt.loc[group_dates, "target"] = rebuilt.loc[:fit_end, "target"].mean()
            if list(matrix) != list(rebuilt):
                raise ValueError("Recomputed frozen-state column names/order differ")
            if not representation["em_converged"]:
                raise ValueError("Recomputed missing-data completion did not converge")
            state_error = _close(matrix, rebuilt, "recomputed frozen states and inputs")
            state_checks.append(
                {
                    "fit_end": str(fit_end),
                    "columns_including_target": len(kept),
                    "maximum_absolute_difference": state_error,
                    "em_converged": representation["em_converged"],
                }
            )
            with TemporaryDirectory(prefix="linear-audit-", dir=run) as scratch:
                qr, r_version = _r_linear(Path(job["matrix"]), ntrain, rscript, Path(scratch))
            errors = {}
            for model in ["AR4", "FA_AR"]:
                expected = baseline.loc[baseline.model.eq(model)].set_index("target_date")
                errors[model] = _close(
                    qr[model],
                    expected.reindex(map(str, group_dates)).prediction,
                    f"R QR versus Python SVD: {model}",
                )
            linear_checks.append(
                {
                    "fit_end": str(fit_end),
                    "maximum_absolute_difference": errors,
                    "R_version": r_version,
                }
            )
        prediction = Path(job["prediction_path"])
        runtime = Path(str(prediction) + ".runtime.dcf")
        if not prediction.exists() or not runtime.exists():
            pending.append({"fit_end": str(fit_end), "seed": job["seed"]})
            continue
        result = pd.read_csv(prediction)
        worst_coefficient_error = max(
            worst_coefficient_error, check_engine_output(result, matrix.iloc[ntrain:])
        )
        runtime_data = _dcf(runtime)
        for name in ["prior", "standardization"]:
            if runtime_data[name] != config[name]:
                raise ValueError(f"Runtime {name} differs")
        runtimes.append(runtime_data)
        completed.append({"fit_end": str(fit_end), "seed": job["seed"], "sha256": _sha(prediction)})
        frames.append(
            pd.DataFrame(
                [
                    {**record, "model": f"FA_ARRF_seed{job['seed']}", "prediction": float(p)}
                    for record, p in zip(job["targets"], result.prediction, strict=True)
                ]
            )
        )
    if pending or not manifest["completed"]:
        if not allow_partial:
            raise ValueError("Run is incomplete; partial artifacts cannot establish reproduction")
        metrics = baseline_metrics
    else:
        forecasts = pd.concat(frames, ignore_index=True)
        ensemble = (
            forecasts.loc[forecasts.model.str.startswith("FA_ARRF_seed")]
            .groupby(["target_date", "origin_date", "actual"], as_index=False)
            .prediction.mean()
        )
        ensemble["model"] = "FA_ARRF_seed_mean_prediction"
        forecasts = pd.concat([forecasts, ensemble], ignore_index=True)
        saved = pd.read_csv(run / "predictions.csv")
        keys = ["model", "target_date"]
        expected_sorted = forecasts.sort_values(keys).set_index(keys)
        saved_sorted = saved.sort_values(keys).set_index(keys)
        if not expected_sorted.index.equals(saved_sorted.index):
            raise ValueError("Aggregated forecast grid differs")
        if not expected_sorted.origin_date.equals(saved_sorted.origin_date):
            raise ValueError("Aggregated origins differ")
        _close(
            saved_sorted[["actual", "prediction"]],
            expected_sorted[["actual", "prediction"]],
            "saved aggregated forecasts",
        )
        metrics = score_table(forecasts)
        saved_metrics = pd.read_csv(run / "metrics.csv").set_index("model")
        if not saved_metrics.index.is_unique or set(saved_metrics.index) != set(metrics.model):
            raise ValueError("Final metric model grid differs")
        _close(
            metrics[numeric], saved_metrics.reindex(metrics.model)[numeric], "saved final metrics"
        )
    published_window = (
        config["evaluation_start"] == "2003Q1"
        and config["evaluation_end"] == "2014Q4"
        and config["regression_start"] == "1961Q3"
        and len(dates) == 48
    )
    full = published_window and not pending and manifest["completed"]
    declared = config == declared_config
    if not full:
        metrics = baseline_metrics
    comparisons = []
    if full and declared:
        for row in metrics.to_dict(orient="records"):
            if row["model"] == "FA_AR" or row["model"].startswith("FA_ARRF"):
                source = config[
                    "reported_FA_AR_ratio" if row["model"] == "FA_AR" else "reported_FA_ARRF_ratio"
                ]
                difference = row["RMSE_over_AR4"] - source
                comparisons.append(
                    {
                        "model": row["model"],
                        "reported_ratio": source,
                        "reconstructed_ratio": row["RMSE_over_AR4"],
                        "difference": difference,
                        "within_project_tolerance": abs(difference)
                        <= config["predeclared_absolute_ratio_tolerance"],
                    }
                )
    numerical_agreement = None
    if comparisons:
        numerical_agreement = all(
            item["within_project_tolerance"]
            for item in comparisons
            if item["model"] != "FA_ARRF_seed_mean_prediction"
        )
    return {
        "status": "full_artifacts_verified_qualified_reconstruction"
        if full
        else "partial_or_nonpaper_run_not_reproduced",
        "full_48_quarter_artifacts_verified": full,
        "matches_declared_config": declared,
        "numerical_agreement_FA_AR_and_all_individual_seeds": numerical_agreement,
        "seed_mean_ensemble_excluded_from_numerical_agreement_rule": True,
        "exact_author_pipeline_verified": False,
        "author_pipeline_boundary": (
            "Original preprocessing and per-table runner not obtained; "
            "matching scores alone do not resolve this."
        ),
        "evaluation_targets_checked": len(dates),
        "jobs_expected": len(expected_keys),
        "jobs_verified": len(completed),
        "pending_jobs": pending,
        "data": data.metadata,
        "config": config,
        "external_engine": manifest["external_engine"],
        "integration_source_sha256": manifest["integration_source_sha256"],
        "linear_checker_sha256": _sha(
            Path(str(files("jev_factor").joinpath("reference_linear.R")))
        ),
        "verifier_sha256": _sha(Path(__file__)),
        "linear_R_QR_vs_Python_SVD": linear_checks,
        "recomputed_state_input_checks": state_checks,
        "maximum_forecast_coefficient_reconstruction_error": worst_coefficient_error,
        "completed_output_checksums": completed,
        "runtime_records": runtimes,
        "metrics": metrics.to_dict(orient="records"),
        "published_ratio_comparisons": comparisons,
        "partial_forest_scores_suppressed": not full,
        "tolerance_is_project_diagnostic_not_statistical_test": True,
    }
