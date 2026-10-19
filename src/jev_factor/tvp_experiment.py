"""Separately declared native TV-FAAR comparison on the frozen primary inputs."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from jev_factor.arrf_audit import verify_aggregates
from jev_factor.replication import score_table
from jev_factor.replication_audit import _dcf, audit_run
from jev_factor.tvp_ridge import (
    DEFAULT_SETTINGS,
    audit_tvp_output,
    ensure_tvp_engine,
    run_native_tvp,
)

PRIMARY_CONFIG_DIGEST = "cd2df267c60250cf06a310b2265421a068c642b33c19b65948a359fb980d15e8"
EQUATION = [f"y_lag{k}" for k in range(1, 5)] + [f"F{j}_lag{k}" for j in (1, 2) for k in (1, 2)]
NATIVE_FILES = (
    "beta_rr.csv",
    "beta_2srr.csv",
    "fitted.csv",
    "predictions.csv",
    "folds.csv",
    "cv_first.csv",
    "cv_second.csv",
    "increment_weights.csv",
    "volatility.csv",
    "garch_coefficients.csv",
    "native.dcf",
)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def validate_declaration(config):
    exact = {
        "study": "quarterly_unemployment_native_TV_FAAR_control",
        "model": "TV_FAAR",
        "equation": EQUATION,
        "intercept_added_by_native_engine": True,
        "factor_rule": "unchanged_original_all248_primary",
        "forecast_schedule": "six_original_two_year_refits_endpoint_beta_frozen_within_block",
        "not_single_2007Q2_or_full_sample_estimation": True,
        "native_default_settings": True,
        "native_CV_seed": 1071,
        "native_CV_is_random_not_chronological": True,
        "outer_seed_ensemble_not_applicable": True,
        "GARCH_optimizer_codes_retained_without_retry_or_fallback": True,
        "reported_RMSE_over_AR4": 1.19,
        "absolute_ratio_diagnostic_tolerance": 0.03,
        "prior_primary_and_sensitivity_losses_already_public": True,
        "chosen_using_new_TV_FAAR_losses": False,
        "original_primary_preserved": True,
        "exact_author_table_invocation_recovered": False,
        "control_match_cannot_establish_FA_ARRF_replication": True,
    }
    if set(config) != {*exact, "declaration_date"} or any(
        type(config[k]) is not type(v) or config[k] != v for k, v in exact.items()
    ):
        raise ValueError("Only the declared native TV-FAAR comparison is supported")


def _source(source_run, archive, primary, rscript):
    canonical = json.dumps(primary, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != PRIMARY_CONFIG_DIGEST:
        raise ValueError("TV-FAAR requires the unchanged original primary configuration")
    report = audit_run(source_run, archive, primary, rscript=rscript)
    if (
        not report["full_48_quarter_artifacts_verified"]
        or not report["matches_declared_config"]
        or len(report["recomputed_state_input_checks"]) != 6
        or any(
            check["columns_including_target"] != 1042
            for check in report["recomputed_state_input_checks"]
        )
    ):
        raise ValueError("Expected all six original 1041-column state matrices")
    source = json.loads((source_run / "manifest.json").read_text())
    if not source["completed"] or source["max_refits"] is not None:
        raise ValueError("TV-FAAR requires a complete primary run")
    return source


def jobs_for(source, output, limit):
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 6):
        raise ValueError("TV-FAAR refit limit must be from one through six")
    originals = [j for j in source["jobs"] if j["seed"] == 101]
    if len(originals) != 6 or [j["group"] for j in originals] != list(range(6)):
        raise ValueError("Missing, duplicated or reordered original refits")
    if limit is not None:
        originals = originals[:limit]
    return [
        {
            "group": original["group"],
            "fit_end": original["fit_end"],
            "matrix": original["matrix"],
            "matrix_sha256": original["matrix_sha256"],
            "settings": original["settings"],
            "settings_sha256": original["settings_sha256"],
            "ntrain": int(_dcf(Path(original["settings"]))["ntrain"]),
            "targets": original["targets"],
            "native_directory": str(
                (output / f"refit_{original['group']:02d}_{original['fit_end']}").resolve()
            ),
        }
        for original in originals
    ]


def _arrays(job):
    for field in ("matrix", "settings"):
        if _sha(job[field]) != job[field + "_sha256"]:
            raise ValueError("Original TV-FAAR matrix or settings changed")
    frame = pd.read_csv(job["matrix"], float_precision="round_trip")
    n = job["ntrain"]
    if (
        len(frame.columns) != 1042
        or frame.columns[0] != "target"
        or not set(EQUATION).issubset(frame)
        or len(frame) - n != len(job["targets"])
        or len(job["targets"]) != 8
        or not np.isfinite(frame.to_numpy()).all()
    ):
        raise ValueError("Invalid original TV-FAAR input or forecast grid")
    return (
        frame[EQUATION].iloc[:n].to_numpy(),
        frame.target.iloc[:n].to_numpy(),
        frame[EQUATION].iloc[n:].to_numpy(),
    )


def _provenance(source_run, engine, config, limit):
    names = (
        "tvp_ridge.py",
        "reference_tvp.R",
        "replication.py",
        "quarterly.py",
        "replication_audit.py",
        "reference_linear.R",
        "reference_mrf.R",
        "arrf_audit.py",
    )
    return {
        "config": config,
        "max_refits": limit,
        "source_run": str(source_run.resolve()),
        "source_manifest_sha256": _sha(source_run / "manifest.json"),
        "source_predictions_sha256": _sha(source_run / "predictions.csv"),
        "external_TVP_engine": ensure_tvp_engine(engine),
        "runner_sha256": _sha(Path(__file__)),
        "dependencies_sha256": {n: _sha(Path(__file__).with_name(n)) for n in names},
        "native_settings": DEFAULT_SETTINGS,
        "backend": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
    }


def verify_manifest(manifest, expected, source, output):
    if any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError("TV-FAAR source, code, configuration or runtime changed")
    if manifest["jobs"] != jobs_for(source, output, manifest["max_refits"]):
        raise ValueError("TV-FAAR model/refit/target/path grid changed")


def check_fit(job):
    directory = Path(job["native_directory"])
    x, y, forecast_x = _arrays(job)
    native_train = pd.read_csv(directory / "train.csv", float_precision="round_trip")
    native_forecast = pd.read_csv(directory / "forecast_x.csv", float_precision="round_trip")
    if not np.array_equal(native_train.to_numpy(), np.column_stack([y, x])) or not np.array_equal(
        native_forecast.to_numpy(), forecast_x
    ):
        raise ValueError("Native TV-FAAR inputs differ from the original equation rows")
    audit = audit_tvp_output(directory, DEFAULT_SETTINGS)
    saved_audit = json.loads((directory / "audit.json").read_text())
    if saved_audit != audit:
        raise ValueError("Saved native TV-FAAR fit audit differs")
    return audit


def collect(manifest):
    complete, pending, native_checks, forecasts = [], [], [], []
    for job in manifest["jobs"]:
        directory = Path(job["native_directory"])
        if not (directory / "audit.json").exists():
            pending.append({"group": job["group"], "fit_end": job["fit_end"]})
            continue
        audit = check_fit(job)
        native_checks.append({"fit_end": job["fit_end"], **audit})
        values = pd.read_csv(directory / "predictions.csv").prediction
        forecasts.extend(
            {**record, "model": "TV_FAAR", "prediction": float(value)}
            for record, value in zip(job["targets"], values, strict=True)
        )
        complete.append(job)
    if not forecasts:
        predictions = pd.DataFrame(
            columns=["target_date", "origin_date", "actual", "model", "prediction"]
        )
    else:
        new = pd.DataFrame(forecasts)
        old = pd.read_csv(Path(manifest["source_run"]) / "predictions.csv")
        old = old.loc[old.target_date.isin(new.target_date)]
        predictions = pd.concat([old, new], ignore_index=True)
    full = manifest["max_refits"] is None and len(complete) == 6 and not pending
    runtime = [check["runtime"] for check in native_checks]
    namespaces = [
        {k: v for k, v in r.items() if k.startswith("namespace_") or k == "R_version"}
        for r in runtime
    ]
    if any(r != namespaces[0] for r in namespaces[1:]):
        raise ValueError("TV-FAAR runtime changed between expanding refits")
    result = {
        "status": "completed_native_TV_FAAR_not_exact_author_replication"
        if full
        else "partial_TV_FAAR_integrity_only",
        "fits_verified": len(complete),
        "pending_jobs": pending,
        "targets_per_model": len(forecasts),
        "native_checks": native_checks,
        "partial_scores_suppressed": not full,
        "metrics": [],
        "TV_FAAR_within_ratio_tolerance": None,
        "FA_ARRF_replication_established": False,
        "exact_author_table_pipeline_verified": False,
        "primary_result_replaced": False,
    }
    if full:
        if (
            len(set(predictions.target_date)) != 48
            or predictions.groupby("model").size().ne(48).any()
        ):
            raise ValueError("Full TV-FAAR comparison requires all 48 dates")
        metrics = score_table(predictions)
        ratio = float(metrics.loc[metrics.model.eq("TV_FAAR"), "RMSE_over_AR4"].iloc[0])
        result.update(
            metrics=metrics.to_dict("records"),
            published_ratio_comparison={
                "reported_ratio": 1.19,
                "reconstructed_ratio": ratio,
                "difference": ratio - 1.19,
                "absolute_ratio_tolerance": 0.03,
            },
            TV_FAAR_within_ratio_tolerance=bool(abs(ratio - 1.19) <= 0.03),
            GARCH_optimizer_converged_for_every_refit=all(
                c["GARCH_optimizer_converged"] for c in native_checks
            ),
        )
    return predictions, result


def run_comparison(
    source_run,
    archive,
    engine,
    library,
    output,
    config,
    primary,
    *,
    max_refits=None,
    prepare_only=False,
    resume=False,
    rscript="Rscript",
):
    validate_declaration(config)
    source_run, output = Path(source_run).resolve(), Path(output).resolve()
    source = _source(source_run, archive, primary, rscript)
    expected = _provenance(source_run, engine, config, max_refits)
    if resume:
        manifest = json.loads((output / "manifest.json").read_text())
        verify_manifest(manifest, expected, source, output)
    else:
        if output.exists():
            raise FileExistsError("Choose a fresh TV-FAAR comparison output")
        jobs = jobs_for(source, output, max_refits)
        for job in jobs:
            _arrays(job)
        output.mkdir(parents=True)
        manifest = {**expected, "jobs": jobs, "completed": False}
        _save(output / "manifest.json", manifest)
    if prepare_only:
        return {
            "status": "TV_FAAR_inputs_declared_no_native_fits_or_scores",
            "fits_planned": len(manifest["jobs"]),
        }
    for job in manifest["jobs"]:
        directory = Path(job["native_directory"])
        if (directory / "audit.json").exists():
            check_fit(job)
            continue
        if directory.exists():
            raise ValueError(
                "Incomplete native fit retained; choose a fresh run rather than overwrite"
            )
        x, y, forecast_x = _arrays(job)
        run_native_tvp(x, y, forecast_x, engine, library, directory, DEFAULT_SETTINGS, rscript)
        check_fit(job)
        print(f"Finished native TV-FAAR {job['fit_end']}", flush=True)
    predictions, result = collect(manifest)
    predictions.to_csv(output / "predictions.csv", index=False, float_format="%.17g")
    if not result["partial_scores_suppressed"]:
        pd.DataFrame(result["metrics"]).to_csv(
            output / "metrics.csv", index=False, float_format="%.17g"
        )
    _save(output / "result.json", result)
    manifest["completed"] = not result["pending_jobs"]
    _save(output / "manifest.json", manifest)
    return result


def audit_comparison(
    run, archive, engine, library, config, primary, *, allow_partial=False, rscript="Rscript"
):
    validate_declaration(config)
    run = Path(run).resolve()
    manifest = json.loads((run / "manifest.json").read_text())
    source_run = Path(manifest["source_run"])
    source = _source(source_run, archive, primary, rscript)
    expected = _provenance(source_run, engine, config, manifest["max_refits"])
    verify_manifest(manifest, expected, source, run)
    predictions, result = collect(manifest)
    if result["partial_scores_suppressed"] and not allow_partial:
        raise ValueError("Full TV-FAAR audit requires six refits and 48 dates")
    if manifest["completed"] != (not result["pending_jobs"]):
        raise ValueError("TV-FAAR completion marker differs from verified fit grid")
    rerun_checks = []
    for job in manifest["jobs"]:
        directory = Path(job["native_directory"])
        if not (directory / "audit.json").exists():
            continue
        x, y, forecast_x = _arrays(job)
        with TemporaryDirectory(prefix="native-tvp-audit-") as scratch:
            repeated = Path(scratch) / "repeat"
            run_native_tvp(x, y, forecast_x, engine, library, repeated, DEFAULT_SETTINGS, rscript)
            if any(_sha(directory / name) != _sha(repeated / name) for name in NATIVE_FILES):
                raise ValueError("Deterministic native TV-FAAR refit differs")
        rerun_checks.append({"fit_end": job["fit_end"], "all_native_artifacts_reproduced": True})
    if json.loads((run / "result.json").read_text()) != result:
        raise ValueError("Saved TV-FAAR result differs")
    if not result["partial_scores_suppressed"]:
        verify_aggregates(run, predictions)
    elif (run / "metrics.csv").exists():
        raise ValueError("Partial TV-FAAR run must suppress metrics")
    else:
        saved = pd.read_csv(run / "predictions.csv")
        if (
            list(saved) != list(predictions)
            or not saved[["model", "target_date", "origin_date"]].equals(
                predictions[["model", "target_date", "origin_date"]]
            )
            or not np.allclose(
                saved[["actual", "prediction"]],
                predictions[["actual", "prediction"]],
                rtol=0,
                atol=1e-13,
            )
        ):
            raise ValueError("Saved partial TV-FAAR forecasts differ")
    return {
        **result,
        "status": "full_native_TV_FAAR_artifacts_verified"
        if not result["partial_scores_suppressed"]
        else "partial_TV_FAAR_integrity_only",
        "primary_artifact_audit_repeated": True,
        "manifest_sha256": _sha(run / "manifest.json"),
        "runner_sha256": _sha(Path(__file__)),
        "deterministic_native_refits": rerun_checks,
    }
