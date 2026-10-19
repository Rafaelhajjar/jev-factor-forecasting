"""Coordinate-only sensitivity on frozen inputs, never a search over signs or test loss."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from jev_factor.arrf_audit import verify_aggregates
from jev_factor.pca_basis_audit import audit_basis
from jev_factor.replication import LINEAR_X, _run_job, ensure_engine, linear_prediction, score_table
from jev_factor.replication_audit import _close, _dcf, _r_linear, check_engine_output


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_basis(report: dict, observed: dict) -> None:
    """Require independently repeated native-R sign maps, not just asserted flags."""
    for field in (
        "status",
        "primary_manifest_sha256",
        "primary_integration_source_sha256",
        "data",
        "external_engine",
        "audit_source_sha256",
        "R_helper_sha256",
        "basis_calculation_uses_only_each_refit_training_panel",
        "basis_selected_using_forecast_loss",
    ):
        if report[field] != observed[field]:
            raise ValueError(f"Basis provenance differs: {field}")
    if (
        report["basis_selected_using_forecast_loss"]
        or not report["basis_calculation_uses_only_each_refit_training_panel"]
    ):
        raise ValueError("Basis must come from the training-only convention audit")
    stored = {r["group"]: r for r in report["refits"]}
    actual = {r["group"]: r for r in observed["refits"]}
    if len(stored) != len(report["refits"]) or set(stored) != set(actual):
        raise ValueError("Basis refit grid differs")
    for group, candidate in stored.items():
        truth = actual[group]
        for field in (
            "fit_end",
            "active_series",
            "active_series_order_sha256",
            "R_version",
            "all_MAFs_match_up_to_component_signs",
            "all_MAFs_have_same_retained_subspace",
            "MAF1_opposite_R_sign_series_indices",
            "MAF2_opposite_R_sign_series_indices",
        ):
            if candidate[field] != truth[field]:
                raise ValueError(f"Native basis differs: {field}")
        if (
            candidate["cross_sectional_PCA"]["signs_to_align_R_with_Python"]
            != truth["cross_sectional_PCA"]["signs_to_align_R_with_Python"]
        ):
            raise ValueError("Native cross-sectional signs differ")
        if (
            not candidate["cross_sectional_PCA"]["same_up_to_component_signs"]
            or not candidate["all_MAFs_match_up_to_component_signs"]
        ):
            raise ValueError("Only verified sign-equivalent bases are supported")


def sign_vector(columns: pd.Index, record: dict, rank: int) -> pd.Series:
    signs = pd.Series(1.0, index=columns)
    if not columns.is_unique or "target" not in columns:
        raise ValueError("Invalid source matrix columns")
    cross = record["cross_sectional_PCA"]["signs_to_align_R_with_Python"]
    if (
        not isinstance(cross, list)
        or len(cross) != rank
        or any(type(s) is not int or s not in (-1, 1) for s in cross)
    ):
        raise ValueError("Invalid cross-sectional sign map")
    for k, sign in enumerate(cross, start=1):
        for lag in range(1, 9):
            name = f"F{k}_lag{lag}"
            if name not in signs:
                raise ValueError(f"Missing PCA coordinate: {name}")
            signs[name] = sign
    for component in (1, 2):
        negative = record[f"MAF{component}_opposite_R_sign_series_indices"]
        if len(negative) != len(set(negative)) or any(
            type(j) is not int or not 0 <= j < record["active_series"] for j in negative
        ):
            raise ValueError("Invalid MAF sign map")
        for j in negative:
            name = f"MAF_{j:03d}_{component}"
            if name not in signs:
                raise ValueError(f"Missing MAF coordinate: {name}")
            signs[name] = -1
    return signs


def _selected(source: dict, config: dict, limit: int | None) -> list[dict]:
    if config["linear_terms"] != LINEAR_X or config["model_prefix"] != "FA_ARRF_R_basis":
        raise ValueError("Only the declared factor-augmented orientation sensitivity is supported")
    if (
        config["trees"] < 1
        or not config["seeds"]
        or len(set(config["seeds"])) != len(config["seeds"])
    ):
        raise ValueError("Need positive trees and unique seeds")
    if not set(config["seeds"]).issubset(source["config"]["seeds"]) or (
        limit is not None and limit < 1
    ):
        raise ValueError("Invalid source seeds or refit bound")
    return [
        j
        for j in source["jobs"]
        if j["seed"] in config["seeds"] and (limit is None or j["group"] < limit)
    ]


def prepare_jobs(
    source: dict, basis: dict, output: Path, config: dict, limit: int | None
) -> list[dict]:
    records = {r["group"]: r for r in basis["refits"]}
    jobs, matrices = [], {}
    for original in _selected(source, config, limit):
        group = original["group"]
        directory = output / f"refit_{group:02d}_{original['fit_end']}"
        directory.mkdir(exist_ok=True)
        if group not in matrices:
            matrix = pd.read_csv(original["matrix"], float_precision="round_trip")
            signs = sign_vector(matrix.columns, records[group], source["config"]["pca_rank"])
            path = directory / "signed_matrix.csv"
            matrix.mul(signs, axis="columns").to_csv(path, index=False, float_format="%.17g")
            matrices[group] = path
        settings = _dcf(Path(original["settings"]))
        if settings["xnames"].split(",") != LINEAR_X:
            raise ValueError("Source equation differs")
        settings["trees"] = str(config["trees"])
        settings_path = directory / f"settings_seed_{original['seed']}.dcf"
        settings_path.write_text("\n".join(f"{k}: {v}" for k, v in settings.items()) + "\n")
        path = matrices[group]
        jobs.append(
            {
                **original,
                "source_matrix": original["matrix"],
                "source_matrix_sha256": original["matrix_sha256"],
                "source_settings_sha256": original["settings_sha256"],
                "matrix": str(path.resolve()),
                "matrix_sha256": _sha(path),
                "settings": str(settings_path.resolve()),
                "settings_sha256": _sha(settings_path),
                "prediction_path": str((directory / f"seed_{original['seed']}.csv").resolve()),
            }
        )
    if not jobs:
        raise ValueError("No selected source jobs")
    return jobs


def verify_jobs(
    manifest: dict,
    source: dict,
    basis: dict,
    output: Path,
    source_predictions: pd.DataFrame,
    *,
    rscript: str | None = None,
) -> list[dict]:
    config = manifest["config"]
    originals = {
        (j["group"], j["seed"]): j for j in _selected(source, config, manifest["max_refits"])
    }
    keys = [(j["group"], j["seed"]) for j in manifest["jobs"]]
    if len(keys) != len(set(keys)) or set(keys) != set(originals):
        raise ValueError("Orientation job grid differs")
    records = {r["group"]: r for r in basis["refits"]}
    checked, linear_checks = set(), []
    for job in manifest["jobs"]:
        original = originals[job["group"], job["seed"]]
        if any(job[k] != original[k] for k in ("targets", "fit_end")):
            raise ValueError("Orientation target/origin records differ")
        if (
            job["source_matrix"] != original["matrix"]
            or job["source_matrix_sha256"] != original["matrix_sha256"]
            or job["source_settings_sha256"] != original["settings_sha256"]
        ):
            raise ValueError("Orientation source provenance differs")
        if (
            _sha(Path(original["matrix"])) != original["matrix_sha256"]
            or _sha(Path(original["settings"])) != original["settings_sha256"]
        ):
            raise ValueError("Primary inputs changed")
        directory = output / f"refit_{job['group']:02d}_{job['fit_end']}"
        paths = {
            "matrix": directory / "signed_matrix.csv",
            "settings": directory / f"settings_seed_{job['seed']}.dcf",
            "prediction_path": directory / f"seed_{job['seed']}.csv",
        }
        if any(Path(job[name]) != path.resolve() for name, path in paths.items()):
            raise ValueError("Orientation output layout differs")
        if any(_sha(Path(job[name])) != job[name + "_sha256"] for name in ("matrix", "settings")):
            raise ValueError("Orientation prepared input changed")
        expected_settings = _dcf(Path(original["settings"]))
        expected_settings["trees"] = str(config["trees"])
        if _dcf(Path(job["settings"])) != expected_settings:
            raise ValueError("An undeclared forest setting changed")
        if job["group"] in checked:
            continue
        checked.add(job["group"])
        raw = pd.read_csv(original["matrix"], float_precision="round_trip")
        signed = pd.read_csv(job["matrix"], float_precision="round_trip")
        signs = sign_vector(raw.columns, records[job["group"]], source["config"]["pca_rank"])
        if list(raw) != list(signed) or not np.array_equal(
            signed.to_numpy(), raw.mul(signs, axis="columns").to_numpy()
        ):
            raise ValueError("Prepared matrix differs by more than the recorded signs")
        ntrain = int(expected_settings["ntrain"])
        dates = [r["target_date"] for r in job["targets"]]
        errors = {}
        columns = {"AR4": [f"y_lag{k}" for k in range(1, 5)]}
        columns["FA_AR"] = columns["AR4"] + [f"F{j}_lag{k}" for j in (1, 2) for k in (1, 2)]
        for model, predictors in columns.items():
            reference = (
                source_predictions.loc[source_predictions.model.eq(model)]
                .set_index("target_date")
                .reindex(dates)
                .prediction
            )
            prediction = linear_prediction(signed.iloc[:ntrain], signed.iloc[ntrain:], predictors)
            errors[model] = _close(prediction, reference, f"sign-invariant linear model {model}")
        if rscript is not None:
            with TemporaryDirectory(prefix="oriented-linear-") as scratch:
                qr, version = _r_linear(Path(job["matrix"]), ntrain, rscript, Path(scratch))
            for model in columns:
                reference = (
                    source_predictions.loc[source_predictions.model.eq(model)]
                    .set_index("target_date")
                    .reindex(dates)
                    .prediction
                )
                errors[model + "_R_QR"] = _close(qr[model], reference, f"oriented R QR {model}")
        else:
            version = None
        linear_checks.append(
            {
                "fit_end": job["fit_end"],
                "maximum_absolute_differences": errors,
                "R_version": version,
            }
        )
    return linear_checks


def check_output(job: dict) -> tuple[pd.DataFrame, float, dict]:
    for name in ("matrix", "settings"):
        if _sha(Path(job[name])) != job[name + "_sha256"]:
            raise ValueError("Orientation checkpoint inputs changed")
    result = pd.read_csv(job["prediction_path"])
    settings = _dcf(Path(job["settings"]))
    ntrain = int(settings["ntrain"])
    matrix = pd.read_csv(job["matrix"])
    error = check_engine_output(result, matrix.iloc[ntrain:])
    runtime = _dcf(Path(job["prediction_path"] + ".runtime.dcf"))
    if any(runtime[k] != settings[k] for k in ("prior", "standardization")):
        raise ValueError("Orientation runtime differs")
    return result, error, runtime


def collect_outputs(manifest: dict, source_predictions: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    prefix = manifest["config"]["model_prefix"]
    frames, checks = [], []
    for job in manifest["jobs"]:
        result, error, runtime = check_output(job)
        checks.append(
            {
                "fit_end": job["fit_end"],
                "seed": job["seed"],
                "sha256": _sha(Path(job["prediction_path"])),
                "coefficient_error": error,
                "runtime": runtime,
            }
        )
        frames.append(
            pd.DataFrame(
                [
                    {**r, "model": f"{prefix}_seed{job['seed']}", "prediction": float(p)}
                    for r, p in zip(job["targets"], result.prediction, strict=True)
                ]
            )
        )
    individual = pd.concat(frames, ignore_index=True)
    dates = set(individual.target_date)
    ensemble = individual.groupby(
        ["target_date", "origin_date", "actual"], as_index=False
    ).prediction.mean()
    ensemble["model"] = f"{prefix}_seed_mean_prediction"
    forecasts = pd.concat(
        [source_predictions.loc[source_predictions.target_date.isin(dates)], individual, ensemble],
        ignore_index=True,
    )
    full = manifest["full_declared_sensitivity"]
    if full and (
        len(dates) != 48
        or dates != set(source_predictions.loc[source_predictions.model.eq("AR4"), "target_date"])
        or manifest["config"] != manifest["declaration"]
    ):
        raise ValueError("Incomplete full orientation sensitivity")
    metrics = score_table(forecasts) if full else pd.DataFrame()
    comparisons, effects = [], []
    if full:
        indexed = metrics.set_index("model")
        for row in metrics.to_dict("records"):
            if row["model"] == "FA_AR" or row["model"].startswith(prefix):
                reported = manifest["config"][
                    "reported_FA_AR_ratio" if row["model"] == "FA_AR" else "reported_FA_ARRF_ratio"
                ]
                delta = row["RMSE_over_AR4"] - reported
                comparisons.append(
                    {
                        "model": row["model"],
                        "reported_ratio": reported,
                        "reconstructed_ratio": row["RMSE_over_AR4"],
                        "difference": delta,
                        "within_diagnostic_tolerance": abs(delta)
                        <= manifest["config"]["absolute_ratio_diagnostic_tolerance"],
                        "ensemble_excluded_from_seed_rule": row["model"].endswith(
                            "mean_prediction"
                        ),
                    }
                )
        for seed in manifest["config"]["seeds"]:
            old, new = f"FA_ARRF_seed{seed}", f"{prefix}_seed{seed}"
            a = forecasts.loc[forecasts.model.eq(old)].set_index("target_date").prediction
            b = (
                forecasts.loc[forecasts.model.eq(new)]
                .set_index("target_date")
                .prediction.reindex(a.index)
            )
            effects.append(
                {
                    "seed": seed,
                    "maximum_absolute_forecast_change": float(np.max(np.abs(b - a))),
                    "RMSE_ratio_change": float(
                        indexed.loc[new, "RMSE_over_AR4"] - indexed.loc[old, "RMSE_over_AR4"]
                    ),
                }
            )
    return {
        "status": "completed_coordinate_sensitivity_not_exact_author_replication"
        if full
        else "bounded_orientation_pilot_not_source_comparison",
        "jobs_verified": len(checks),
        "targets_per_model": len(dates),
        "output_checks": checks,
        "partial_forest_scores_suppressed": not full,
        "metrics": metrics.to_dict("records"),
        "published_ratio_comparisons": comparisons,
        "paired_orientation_effects": effects,
        "FA_AR_and_all_individual_R_basis_seeds_within_tolerance": all(
            c["within_diagnostic_tolerance"]
            for c in comparisons
            if not c["ensemble_excluded_from_seed_rule"]
        )
        if comparisons
        else None,
        "exact_author_pipeline_verified": False,
        "original_author_basis_recovered": False,
        "coefficient_basis": "recorded_R_sign_coordinates_use_each_jobs_signed_matrix",
        "primary_result_replaced": False,
        "basis_selected_using_forecast_loss": False,
    }, forecasts


def _inputs(
    source_run: Path,
    archive: Path,
    engine: Path,
    basis_path: Path,
    primary_config: dict,
    rscript: str,
) -> tuple[dict, dict, pd.DataFrame]:
    report = json.loads(basis_path.read_text())
    observed = audit_basis(source_run, archive, engine, primary_config, rscript=rscript)
    verify_basis(report, observed)
    source = json.loads((source_run / "manifest.json").read_text())
    return source, report, pd.read_csv(source_run / "predictions.csv")


def run_sensitivity(
    source_run: Path,
    archive: Path,
    engine: Path,
    basis_path: Path,
    output: Path,
    declaration: dict,
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
    source, basis, source_predictions = _inputs(
        source_run, archive, engine, basis_path, primary_config, rscript
    )
    config = {**declaration}
    if trees is not None:
        config["trees"] = trees
    if seeds is not None:
        config["seeds"] = seeds
    adapter = Path(str(files("jev_factor").joinpath("reference_mrf.R")))
    provenance = {
        "config": config,
        "declaration": declaration,
        "max_refits": max_refits,
        "source_run": str(source_run.resolve()),
        "source_manifest_sha256": _sha(source_run / "manifest.json"),
        "source_predictions_sha256": _sha(source_run / "predictions.csv"),
        "basis_report_sha256": _sha(basis_path),
        "external_engine": ensure_engine(engine),
        "adapter_sha256": _sha(adapter),
        "sensitivity_source_sha256": _sha(Path(__file__)),
    }
    if output.exists():
        if not resume:
            raise FileExistsError("Choose a fresh sensitivity output or use --resume")
        manifest = json.loads((output / "manifest.json").read_text())
        if any(manifest.get(k) != v for k, v in provenance.items()):
            raise ValueError("Orientation resume provenance differs")
    else:
        output.mkdir(parents=True)
        jobs = prepare_jobs(source, basis, output, config, max_refits)
        manifest = {
            **provenance,
            "jobs": jobs,
            "full_declared_sensitivity": config == declaration
            and len(jobs) == 18
            and len({r["target_date"] for j in jobs for r in j["targets"]}) == 48,
            "completed": False,
        }
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    checks = verify_jobs(manifest, source, basis, output, source_predictions, rscript=rscript)
    (output / "linear_invariance_checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    todo = []
    for job in manifest["jobs"]:
        if (
            Path(job["prediction_path"]).exists()
            and Path(job["prediction_path"] + ".runtime.dcf").exists()
        ):
            check_output(job)
        else:
            todo.append(job)
    print(
        f"R-basis sensitivity: {len(manifest['jobs'])} jobs; {len(todo)} require fitting",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_job, job, engine, rscript, r_library, adapter) for job in todo]
        for future in as_completed(futures):
            with (output / "completed_jobs.jsonl").open("a") as stream:
                stream.write(json.dumps(future.result()) + "\n")
    result, forecasts = collect_outputs(manifest, source_predictions)
    forecasts.to_csv(output / "predictions.csv", index=False)
    if result["metrics"]:
        pd.DataFrame(result["metrics"]).to_csv(output / "metrics.csv", index=False)
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    manifest.update(completed=True, status=result["status"])
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return result


def audit_sensitivity(
    run: Path,
    archive: Path,
    engine: Path,
    basis_path: Path,
    declaration: dict,
    primary_config: dict,
    *,
    rscript: str = "Rscript",
    allow_partial: bool = False,
) -> dict:
    manifest = json.loads((run / "manifest.json").read_text())
    source_run = Path(manifest["source_run"])
    source, basis, predictions = _inputs(
        source_run, archive, engine, basis_path, primary_config, rscript
    )
    expected = {
        "declaration": declaration,
        "source_manifest_sha256": _sha(source_run / "manifest.json"),
        "source_predictions_sha256": _sha(source_run / "predictions.csv"),
        "basis_report_sha256": _sha(basis_path),
        "sensitivity_source_sha256": _sha(Path(__file__)),
        "external_engine": basis["external_engine"],
        "adapter_sha256": _sha(Path(str(files("jev_factor").joinpath("reference_mrf.R")))),
    }
    if any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError("Orientation audit provenance differs")
    checks = verify_jobs(manifest, source, basis, run, predictions, rscript=rscript)
    completed, pending, errors = [], [], []
    for job in manifest["jobs"]:
        if (
            not Path(job["prediction_path"]).exists()
            or not Path(job["prediction_path"] + ".runtime.dcf").exists()
        ):
            pending.append({"fit_end": job["fit_end"], "seed": job["seed"]})
        else:
            _, error, _ = check_output(job)
            errors.append(error)
            completed.append(
                {
                    "fit_end": job["fit_end"],
                    "seed": job["seed"],
                    "sha256": _sha(Path(job["prediction_path"])),
                }
            )
    full = (
        not pending
        and manifest["completed"]
        and manifest["full_declared_sensitivity"]
        and manifest["config"] == declaration
        and len(completed) == 18
    )
    if not full and not allow_partial:
        raise ValueError("Sensitivity is incomplete or differs from its full declaration")
    result = None
    if full:
        result, forecasts = collect_outputs(manifest, predictions)
        verify_aggregates(run, forecasts)
        if json.loads((run / "result.json").read_text()) != result:
            raise ValueError("Saved orientation result differs")
        saved_checks = json.loads((run / "linear_invariance_checks.json").read_text())
        if [r["fit_end"] for r in saved_checks] != [r["fit_end"] for r in checks]:
            raise ValueError("Saved linear-invariance grid differs")
        for saved, current in zip(saved_checks, checks, strict=True):
            if saved["R_version"] != current["R_version"] or set(
                saved["maximum_absolute_differences"]
            ) != set(current["maximum_absolute_differences"]):
                raise ValueError("Saved linear-invariance check schema differs")
            _close(
                list(saved["maximum_absolute_differences"].values()),
                list(current["maximum_absolute_differences"].values()),
                "saved linear-invariance errors",
            )
    return {
        "status": "full_orientation_artifacts_verified"
        if full
        else "partial_orientation_integrity_only",
        "source_primary_integrity_verified": True,
        "native_R_sign_maps_recomputed_and_verified": True,
        "sensitivity_source_sha256": _sha(Path(__file__)),
        "manifest_sha256": _sha(run / "manifest.json"),
        "basis_report_sha256": _sha(basis_path),
        "jobs_verified": len(completed),
        "pending_jobs": pending,
        "output_checks": completed,
        "maximum_coefficient_reconstruction_error": max(errors, default=0),
        "linear_invariance_checks": checks,
        "metrics": result["metrics"] if result else [],
        "published_ratio_comparisons": result["published_ratio_comparisons"] if result else [],
        "paired_orientation_effects": result["paired_orientation_effects"] if result else [],
        "FA_AR_and_all_individual_R_basis_seeds_within_tolerance": result[
            "FA_AR_and_all_individual_R_basis_seeds_within_tolerance"
        ]
        if result
        else None,
        "partial_forest_scores_suppressed": not full,
        "exact_author_pipeline_verified": False,
        "original_author_basis_recovered": False,
        "primary_result_replaced": False,
    }
