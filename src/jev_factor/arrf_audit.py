"""Revalidate saved ARRF artifacts; never confuse a comparator with FA-ARRF replication."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import pandas as pd

from jev_factor import arrf_diagnostic
from jev_factor.arrf_diagnostic import (
    _sha,
    check_arrf_output,
    collect_outputs,
    validate_job_grid,
    validate_resume,
)
from jev_factor.replication import score_table
from jev_factor.replication_audit import _close, audit_run


def verify_aggregates(run: Path, expected: pd.DataFrame) -> None:
    saved = pd.read_csv(run / "predictions.csv")
    keys = ["model", "target_date"]
    if set(saved) != set(expected) or saved.duplicated(keys).any():
        raise ValueError("ARRF saved forecast schema/grid differs")
    actual = saved.sort_values(keys).set_index(keys)
    reference = expected.sort_values(keys).set_index(keys)
    if not actual.index.equals(reference.index) or not actual.origin_date.equals(
        reference.origin_date
    ):
        raise ValueError("ARRF saved forecast dates/origins differ")
    _close(
        actual[["actual", "prediction"]],
        reference[["actual", "prediction"]],
        "saved ARRF forecasts",
    )
    metrics = score_table(expected).set_index("model")
    saved_metrics = pd.read_csv(run / "metrics.csv").set_index("model")
    if (
        not saved_metrics.index.is_unique
        or set(saved_metrics.index) != set(metrics.index)
        or set(saved_metrics) != set(metrics)
    ):
        raise ValueError("ARRF saved metric model/schema grid differs")
    numeric = ["n", "RMSE", "MAE", "RMSE_over_AR4"]
    _close(saved_metrics.reindex(metrics.index)[numeric], metrics[numeric], "saved ARRF metrics")


def audit_arrf(
    run: Path,
    archive: Path,
    engine: Path,
    declared_config: dict,
    primary_config: dict,
    *,
    rscript: str = "Rscript",
    allow_partial: bool = False,
) -> dict:
    manifest = json.loads((run / "manifest.json").read_text())
    source = Path(manifest["source_run"])
    primary = audit_run(source, archive, primary_config, rscript=rscript)
    if not primary["full_48_quarter_artifacts_verified"] or not primary["matches_declared_config"]:
        raise ValueError("ARRF primary source no longer matches its full declaration")
    source_manifest = json.loads((source / "manifest.json").read_text())
    provenance = {
        "declaration": declared_config,
        "source_manifest_sha256": _sha(source / "manifest.json"),
        "source_predictions_sha256": _sha(source / "predictions.csv"),
        "external_engine": primary["external_engine"],
        "adapter_sha256": _sha(Path(str(files("jev_factor").joinpath("reference_mrf.R")))),
        "diagnostic_source_sha256": _sha(Path(arrf_diagnostic.__file__)),
    }
    if _sha(engine) != primary["external_engine"]["sha256"]:
        raise ValueError("ARRF external engine file differs")
    validate_resume(manifest, provenance)
    validate_job_grid(manifest, source_manifest, run)
    verified, pending, errors = [], [], []
    for job in manifest["jobs"]:
        destination = Path(job["prediction_path"])
        if not destination.exists() or not Path(str(destination) + ".runtime.dcf").exists():
            pending.append({"fit_end": job["fit_end"], "seed": job["seed"]})
            continue
        _, error, runtime = check_arrf_output(job)
        errors.append(error)
        verified.append(
            {
                "fit_end": job["fit_end"],
                "seed": job["seed"],
                "sha256": _sha(destination),
                "runtime": runtime,
            }
        )
    complete = not pending and manifest["completed"]
    full = complete and manifest["config"] == declared_config and len(verified) == 18
    if not full and not allow_partial:
        raise ValueError("ARRF diagnostic is incomplete or not the full declaration")
    result = None
    if full:
        result, predictions = collect_outputs(manifest, pd.read_csv(source / "predictions.csv"))
        if result["targets_per_model"] != 48 or not manifest["full_declared_diagnostic"]:
            raise ValueError("ARRF full target grid differs")
        verify_aggregates(run, predictions)
        if json.loads((run / "result.json").read_text()) != result:
            raise ValueError("ARRF saved result differs from recomputed artifact checks")
    comparisons = result["published_ARRF_comparisons"] if result else []
    return {
        "status": "full_ARRF_artifacts_verified_not_FA_ARRF_replication"
        if full
        else "partial_ARRF_integrity_only",
        "source_primary_integrity_verified": True,
        "matches_full_ARRF_declaration": full,
        "primary_manifest_sha256": provenance["source_manifest_sha256"],
        "diagnostic_manifest_sha256": _sha(run / "manifest.json"),
        "diagnostic_source_sha256": provenance["diagnostic_source_sha256"],
        "verifier_sha256": _sha(Path(__file__)),
        "jobs_verified": len(verified),
        "pending_jobs": pending,
        "output_checks": verified,
        "maximum_coefficient_reconstruction_error": max(errors, default=0),
        "metrics": result["metrics"] if result else [],
        "published_ARRF_comparisons": comparisons,
        "all_individual_ARRF_seeds_within_diagnostic_tolerance": all(
            c["within_diagnostic_tolerance"]
            for c in comparisons
            if not c["ensemble_excluded_from_seed_rule"]
        )
        if comparisons
        else None,
        "partial_forest_scores_suppressed": not full,
        "exact_author_pipeline_verified": False,
        "FA_ARRF_replication_established_by_this_diagnostic": False,
    }
