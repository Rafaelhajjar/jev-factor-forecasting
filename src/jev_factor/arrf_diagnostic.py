"""Named paper comparator on immutable primary-run inputs, not a new Jev study.

Keep the first reconstruction's preparation and R adapter byte-identical. This
diagnostic changes only the explicit equation to AR(2); all rich state columns
remain available to the forest. An ARRF match cannot establish FA-ARRF replication.
"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib.resources import files
from pathlib import Path

import numpy as np
import pandas as pd

from jev_factor.replication import _run_job, ensure_engine, score_table
from jev_factor.replication_audit import _dcf, audit_run

LINEAR_TERMS = ["y_lag1", "y_lag2"]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_arrf_jobs(
    source: dict, output: Path, config: dict, max_refits: int | None
) -> list[dict]:
    if config["model"] != "ARRF" or config["linear_terms"] != LINEAR_TERMS:
        raise ValueError("This diagnostic only implements the named ARRF equation")
    if (
        config["trees"] < 1
        or not config["seeds"]
        or len(set(config["seeds"])) != len(config["seeds"])
    ):
        raise ValueError("Need positive tree count and unique seeds")
    source_seeds = set(source["config"]["seeds"])
    if not set(config["seeds"]).issubset(source_seeds):
        raise ValueError("Use seeds declared in the primary run")
    if max_refits is not None and max_refits < 1:
        raise ValueError("max_refits must be positive")
    jobs = []
    for original in source["jobs"]:
        if original["seed"] not in config["seeds"]:
            continue
        if max_refits is not None and original["group"] >= max_refits:
            continue
        directory = output / f"refit_{original['group']:02d}_{original['fit_end']}"
        directory.mkdir(exist_ok=True)
        settings = _dcf(Path(original["settings"]))
        settings.update(xnames=",".join(LINEAR_TERMS), trees=str(config["trees"]))
        destination = directory / f"settings_seed_{original['seed']}.dcf"
        destination.write_text("\n".join(f"{k}: {v}" for k, v in settings.items()) + "\n")
        jobs.append(
            {
                **original,
                "source_settings_sha256": original["settings_sha256"],
                "settings": str(destination.resolve()),
                "settings_sha256": _sha(destination),
                "prediction_path": str((directory / f"seed_{original['seed']}.csv").resolve()),
            }
        )
    if not jobs:
        raise ValueError("No matching source jobs")
    return jobs


def check_arrf_output(job: dict) -> tuple[pd.DataFrame, float, dict]:
    """Check an existing checkpoint before reuse or aggregation."""
    for field in ("matrix", "settings"):
        if _sha(Path(job[field])) != job[field + "_sha256"]:
            raise ValueError(f"ARRF {field} changed")
    settings = _dcf(Path(job["settings"]))
    if settings["xnames"].split(",") != LINEAR_TERMS:
        raise ValueError("ARRF equation terms differ")
    result = pd.read_csv(job["prediction_path"])
    expected = {"prediction", "intercept", *LINEAR_TERMS}
    if set(result) != expected or len(result) != len(job["targets"]):
        raise ValueError("ARRF coefficient/output schema differs")
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError("Nonfinite ARRF output")
    matrix = pd.read_csv(job["matrix"])
    ntrain = int(settings["ntrain"])
    if len(matrix) != ntrain + len(result):
        raise ValueError("ARRF row count differs")
    reconstructed = result.intercept.to_numpy() + np.sum(
        result[LINEAR_TERMS].to_numpy() * matrix.iloc[ntrain:][LINEAR_TERMS].to_numpy(), axis=1
    )
    error = float(np.max(np.abs(reconstructed - result.prediction)))
    if not np.allclose(reconstructed, result.prediction, atol=1e-11, rtol=1e-10):
        raise ValueError("ARRF coefficients do not reconstruct the forecast")
    runtime = _dcf(Path(job["prediction_path"] + ".runtime.dcf"))
    if any(runtime[name] != settings[name] for name in ("prior", "standardization")):
        raise ValueError("ARRF runtime mode differs")
    return result, error, runtime


def validate_resume(saved: dict, expected: dict) -> None:
    for name, value in expected.items():
        if saved.get(name) != value:
            raise ValueError(f"ARRF resume provenance differs: {name}")
    for job in saved["jobs"]:
        for field in ("matrix", "settings"):
            if _sha(Path(job[field])) != job[field + "_sha256"]:
                raise ValueError(f"ARRF resume {field} changed")


def validate_job_grid(manifest: dict, source: dict, output: Path) -> None:
    config = manifest["config"]
    limit = manifest["max_refits"]
    originals = {
        (j["group"], j["seed"]): j
        for j in source["jobs"]
        if j["seed"] in config["seeds"] and (limit is None or j["group"] < limit)
    }
    keys = [(j["group"], j["seed"]) for j in manifest["jobs"]]
    if len(keys) != len(set(keys)) or set(keys) != set(originals):
        raise ValueError("ARRF job grid is missing, duplicated or undeclared")
    for job in manifest["jobs"]:
        original = originals[(job["group"], job["seed"])]
        for field in ("matrix", "matrix_sha256", "targets", "fit_end"):
            if job[field] != original[field]:
                raise ValueError(f"ARRF changed primary {field}")
        if job["source_settings_sha256"] != original["settings_sha256"]:
            raise ValueError("ARRF source settings checksum differs")
        directory = output / f"refit_{job['group']:02d}_{job['fit_end']}"
        if Path(job["settings"]) != (directory / f"settings_seed_{job['seed']}.dcf").resolve():
            raise ValueError("ARRF settings path differs")
        if Path(job["prediction_path"]) != (directory / f"seed_{job['seed']}.csv").resolve():
            raise ValueError("ARRF prediction path differs")
        expected = _dcf(Path(original["settings"]))
        expected.update(xnames=",".join(LINEAR_TERMS), trees=str(config["trees"]))
        if (
            _dcf(Path(job["settings"])) != expected
            or _sha(Path(job["settings"])) != job["settings_sha256"]
        ):
            raise ValueError("ARRF changed an undeclared setting")


def collect_outputs(manifest: dict, source_predictions: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    frames, errors, checks = [], [], []
    for job in manifest["jobs"]:
        result, error, runtime = check_arrf_output(job)
        errors.append(error)
        checks.append(
            {
                "fit_end": job["fit_end"],
                "seed": job["seed"],
                "sha256": _sha(Path(job["prediction_path"])),
                "runtime": runtime,
            }
        )
        frames.append(
            pd.DataFrame(
                [
                    {**record, "model": f"ARRF_seed{job['seed']}", "prediction": float(p)}
                    for record, p in zip(job["targets"], result.prediction, strict=True)
                ]
            )
        )
    forecasts = pd.concat(frames, ignore_index=True)
    dates = set(forecasts.target_date)
    ensemble = forecasts.groupby(
        ["target_date", "origin_date", "actual"], as_index=False
    ).prediction.mean()
    ensemble["model"] = "ARRF_seed_mean_prediction"
    forecasts = pd.concat(
        [source_predictions.loc[source_predictions.target_date.isin(dates)], forecasts, ensemble],
        ignore_index=True,
    )
    # Partial pilots get execution evidence, never a source-comparison result.
    full = manifest["full_declared_diagnostic"]
    if full:
        source_dates = set(
            source_predictions.loc[source_predictions.model.eq("AR4"), "target_date"]
        )
        expected_models = {f"ARRF_seed{seed}" for seed in manifest["config"]["seeds"]}
        individual = forecasts.loc[forecasts.model.isin(expected_models)]
        if (
            len(source_dates) != 48
            or dates != source_dates
            or set(individual.model) != expected_models
        ):
            raise ValueError("Full ARRF diagnostic requires the complete 48-quarter grid")
        if any(set(frame.target_date) != source_dates for _, frame in individual.groupby("model")):
            raise ValueError("Full ARRF seed grid differs")
        if manifest["config"] != manifest["declaration"]:
            raise ValueError("Full ARRF diagnostic differs from its declaration")
    metrics = score_table(forecasts) if full else pd.DataFrame()
    comparisons = []
    if full:
        for row in metrics.to_dict("records"):
            if row["model"].startswith("ARRF_seed"):
                difference = row["RMSE_over_AR4"] - manifest["config"]["reported_ratio"]
                comparisons.append(
                    {
                        "model": row["model"],
                        "reported_ratio": manifest["config"]["reported_ratio"],
                        "reconstructed_ratio": row["RMSE_over_AR4"],
                        "difference": difference,
                        "within_diagnostic_tolerance": abs(difference)
                        <= manifest["config"]["absolute_ratio_diagnostic_tolerance"],
                        "ensemble_excluded_from_seed_rule": row["model"]
                        == "ARRF_seed_mean_prediction",
                    }
                )
    return {
        "status": "completed_ARRF_diagnostic_not_FA_ARRF_replication"
        if full
        else "bounded_pilot_not_source_comparison",
        "jobs_verified": len(checks),
        "targets_per_model": len(dates),
        "maximum_coefficient_reconstruction_error": max(errors),
        "output_checks": checks,
        "partial_forest_scores_suppressed": not full,
        "metrics": metrics.to_dict("records"),
        "published_ARRF_comparisons": comparisons,
        "exact_author_pipeline_verified": False,
        "FA_ARRF_replication_established_by_this_diagnostic": False,
    }, forecasts


def run_diagnostic(
    source_run: Path,
    archive: Path,
    engine: Path,
    output: Path,
    declared_config: dict,
    primary_config: dict,
    *,
    rscript: str = "Rscript",
    r_library: Path = Path("runs/r-library"),
    workers: int = 4,
    trees: int | None = None,
    seeds: list[int] | None = None,
    max_refits: int | None = None,
    resume: bool = False,
) -> dict:
    if not 1 <= workers <= 8:
        raise ValueError("workers must be 1–8")
    engine_metadata = ensure_engine(engine)
    primary_audit = audit_run(source_run, archive, primary_config, rscript=rscript)
    if (
        not primary_audit["full_48_quarter_artifacts_verified"]
        or not primary_audit["matches_declared_config"]
    ):
        raise ValueError("Use the full audited primary reconstruction, not a pilot")
    source = json.loads((source_run / "manifest.json").read_text())
    config = {**declared_config}
    if trees is not None:
        config["trees"] = trees
    if seeds is not None:
        config["seeds"] = seeds
    adapter = Path(str(files("jev_factor").joinpath("reference_mrf.R")))
    provenance = {
        "config": config,
        "declaration": declared_config,
        "max_refits": max_refits,
        "source_run": str(source_run.resolve()),
        "source_manifest_sha256": _sha(source_run / "manifest.json"),
        "source_predictions_sha256": _sha(source_run / "predictions.csv"),
        "external_engine": engine_metadata,
        "adapter_sha256": _sha(adapter),
        "diagnostic_source_sha256": _sha(Path(__file__)),
    }
    if output.exists():
        if not resume:
            raise FileExistsError("Choose a fresh diagnostic output or use --resume")
        manifest = json.loads((output / "manifest.json").read_text())
        validate_resume(manifest, provenance)
    else:
        output.mkdir(parents=True)
        jobs = prepare_arrf_jobs(source, output, config, max_refits)
        full = (
            config == declared_config
            and len(jobs) == 18
            and len({r["target_date"] for j in jobs for r in j["targets"]}) == 48
        )
        manifest = {
            **provenance,
            "jobs": jobs,
            "full_declared_diagnostic": full,
            "completed": False,
        }
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (output / "primary_integrity_audit.json").write_text(
            json.dumps(primary_audit, indent=2) + "\n"
        )
    validate_job_grid(manifest, source, output)
    todo = []
    for job in manifest["jobs"]:
        destination = Path(job["prediction_path"])
        if destination.exists() and Path(str(destination) + ".runtime.dcf").exists():
            check_arrf_output(job)
        else:
            todo.append(job)
    print(f"ARRF diagnostic: {len(manifest['jobs'])} jobs; {len(todo)} require fitting", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_job, job, engine, rscript, r_library, adapter) for job in todo]
        for future in as_completed(futures):
            completed = future.result()
            with (output / "completed_jobs.jsonl").open("a") as stream:
                stream.write(json.dumps(completed) + "\n")
    result, predictions = collect_outputs(manifest, pd.read_csv(source_run / "predictions.csv"))
    predictions.to_csv(output / "predictions.csv", index=False)
    if result["metrics"]:
        pd.DataFrame(result["metrics"]).to_csv(output / "metrics.csv", index=False)
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    manifest.update(completed=True, status=result["status"])
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return result
