"""A separately declared PCA-eligibility experiment on the frozen full macro state."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from jev_factor.arrf_audit import verify_aggregates
from jev_factor.pca_eligibility import audit_eligibility, replace_factor_lags, subset_factors
from jev_factor.quarterly import PastRepresentation, QuarterlyData, load_quarterly
from jev_factor.replication import LINEAR_X, _run_job, ensure_engine, linear_prediction, score_table
from jev_factor.replication_audit import _close, _dcf, _r_linear, check_engine_output

PREFIX = "FA_ARRF_PCA125"
BASELINE = "FA_AR_PCA125"
AR = [f"y_lag{k}" for k in range(1, 5)]
FA = AR + [f"F{j}_lag{k}" for j in (1, 2) for k in (1, 2)]
FACTOR_LAGS = [f"F{j}_lag{k}" for j in range(1, 6) for k in range(1, 9)]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dependencies() -> dict:
    return {
        name: _sha(Path(__file__).with_name(name))
        for name in (
            "pca_eligibility.py",
            "pca_basis_audit.py",
            "quarterly.py",
            "replication.py",
            "replication_audit.py",
            "arrf_audit.py",
            "reference_linear.R",
            "reference_pca.R",
            "reference_mrf.R",
        )
    }


def select_jobs(source: dict, config: dict, limit: int | None) -> list[dict]:
    if (
        config["model_prefix"] != PREFIX
        or config["linear_baseline_name"] != BASELINE
        or config["linear_terms"] != LINEAR_X
        or config["factor_rule"]
        != "five_PCs_of_metadata_SW_members_on_frozen_all_248_completed_panel"
        or config["sign_rule"] != "original_deterministic_Python_convention_not_R_sign_sensitivity"
        or config["eligibility_selected_using_forecast_loss"]
    ):
        raise ValueError("Only the declared PCA-only construction is supported")
    if (
        type(config["trees"]) is not int
        or not 1 <= config["trees"] <= source["config"]["trees"]
        or not config["seeds"]
        or len(set(config["seeds"])) != len(config["seeds"])
        or not set(config["seeds"]).issubset(source["config"]["seeds"])
        or (limit is not None and (type(limit) is not int or not 1 <= limit <= 6))
    ):
        raise ValueError("Pilots may only reduce the declared trees, seeds or refits")
    selected = [
        j
        for j in source["jobs"]
        if j["seed"] in config["seeds"] and (limit is None or j["group"] < limit)
    ]
    if not selected:
        raise ValueError("No selected source jobs")
    return selected


@threadpool_limits.wrap(limits=1)
def build_matrix(data: QuarterlyData, original: dict, primary: dict) -> pd.DataFrame:
    endpoint = pd.Period(original["fit_end"], freq="Q")
    through = pd.Period(original["targets"][-1]["target_date"], freq="Q")
    panel = data.panel.loc[primary["panel_start"] : through - 1]
    representation = PastRepresentation(5, primary["outlier_iqr"]).fit(panel.loc[:endpoint])
    if not representation.converged or not representation.active.all():
        raise ValueError("The frozen full-panel completion must converge and retain all series")
    z, all_scores = representation.transform(panel)
    scores, _, selected = subset_factors(z, data.sw_membership, endpoint, rank=5)
    if len(z.columns) != 248 or len(selected) != 125:
        raise ValueError("PCA eligibility/cardinality differs from the archived declaration")
    raw = pd.read_csv(original["matrix"], float_precision="round_trip")
    raw.index = pd.period_range(primary["regression_start"], through, freq="Q")
    rebuilt = replace_factor_lags(raw, all_scores)
    _close(raw[FACTOR_LAGS], rebuilt[FACTOR_LAGS], "original factor lags")
    return replace_factor_lags(raw, scores)


def prepare_jobs(
    source: dict, data: QuarterlyData, output: Path, config: dict, limit
) -> list[dict]:
    jobs, matrices = [], {}
    for original in select_jobs(source, config, limit):
        group = original["group"]
        directory = output / f"refit_{group:02d}_{original['fit_end']}"
        directory.mkdir(exist_ok=True)
        if group not in matrices:
            matrix = build_matrix(data, original, source["config"])
            path = directory / "pca125_matrix.csv"
            matrix.to_csv(path, index=False, float_format="%.17g")
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
                "source_matrix_sha256": original["matrix_sha256"],
                "source_settings_sha256": original["settings_sha256"],
                "matrix": str(path.resolve()),
                "matrix_sha256": _sha(path),
                "settings": str(settings_path.resolve()),
                "settings_sha256": _sha(settings_path),
                "prediction_path": str((directory / f"seed_{original['seed']}.csv").resolve()),
            }
        )
    return jobs


def verify_jobs(
    manifest: dict,
    source: dict,
    data: QuarterlyData,
    output: Path,
    source_predictions: pd.DataFrame,
    *,
    rscript: str | None = None,
):
    config = manifest["config"]
    originals = {
        (j["group"], j["seed"]): j for j in select_jobs(source, config, manifest["max_refits"])
    }
    keys = [(j["group"], j["seed"]) for j in manifest["jobs"]]
    if len(keys) != len(set(keys)) or set(keys) != set(originals):
        raise ValueError("PCA125 refit/seed grid differs")
    checked, checks, linear = set(), [], []
    for job in manifest["jobs"]:
        original = originals[job["group"], job["seed"]]
        if any(job[k] != original[k] for k in ("targets", "fit_end")):
            raise ValueError("PCA125 target/origin records differ")
        for name in ("matrix", "settings"):
            if (
                _sha(Path(original[name])) != original[name + "_sha256"]
                or job["source_" + name + "_sha256"] != original[name + "_sha256"]
            ):
                raise ValueError("Primary inputs/provenance changed")
        directory = output / f"refit_{job['group']:02d}_{job['fit_end']}"
        paths = {
            "matrix": directory / "pca125_matrix.csv",
            "settings": directory / f"settings_seed_{job['seed']}.dcf",
            "prediction_path": directory / f"seed_{job['seed']}.csv",
        }
        if any(Path(job[k]) != v.resolve() for k, v in paths.items()):
            raise ValueError("PCA125 output path differs")
        if any(_sha(Path(job[k])) != job[k + "_sha256"] for k in ("matrix", "settings")):
            raise ValueError("PCA125 prepared input changed")
        expected_settings = _dcf(Path(original["settings"]))
        expected_settings["trees"] = str(config["trees"])
        if _dcf(Path(job["settings"])) != expected_settings:
            raise ValueError("An undeclared forest setting changed")
        if job["group"] in checked:
            continue
        checked.add(job["group"])
        expected = build_matrix(data, original, source["config"])
        matrix = pd.read_csv(job["matrix"], float_precision="round_trip")
        if list(matrix) != list(expected) or not np.array_equal(
            matrix.to_numpy(), expected.to_numpy()
        ):
            raise ValueError("PCA125 matrix differs from the declared reconstruction")
        raw = pd.read_csv(original["matrix"], float_precision="round_trip")
        untouched = raw.columns.difference(FACTOR_LAGS, sort=False)
        if not np.array_equal(matrix[untouched], raw[untouched]):
            raise ValueError("A non-factor entry changed")
        ntrain = int(expected_settings["ntrain"])
        errors, predictions = {}, {}
        for model, columns in (("AR4", AR), (BASELINE, FA)):
            predictions[model] = linear_prediction(
                matrix.iloc[:ntrain], matrix.iloc[ntrain:], columns
            )
            linear.extend(
                {**r, "model": model, "prediction": float(p)}
                for r, p in zip(job["targets"], predictions[model], strict=True)
            )
        dates = [r["target_date"] for r in job["targets"]]
        reference = source_predictions.loc[source_predictions.model.eq("AR4")].set_index(
            "target_date"
        )
        errors["AR4_unchanged"] = _close(
            predictions["AR4"], reference.reindex(dates).prediction, "AR4 unchanged"
        )
        if rscript is not None:
            with TemporaryDirectory(prefix="pca125-linear-") as scratch:
                qr, version = _r_linear(Path(job["matrix"]), ntrain, rscript, Path(scratch))
            errors["AR4_R_QR"] = _close(qr.AR4, predictions["AR4"], "PCA125 AR4 Python/R")
            errors["FA_AR_PCA125_R_QR"] = _close(
                qr.FA_AR, predictions[BASELINE], "PCA125 FA-AR Python/R"
            )
        else:
            version = None
        checks.append(
            {
                "fit_end": job["fit_end"],
                "maximum_absolute_differences": errors,
                "all_nonfactor_entries_exactly_preserved": True,
                "R_version": version,
            }
        )
    return checks, pd.DataFrame(linear)


def check_output(job: dict):
    if any(_sha(Path(job[k])) != job[k + "_sha256"] for k in ("matrix", "settings")):
        raise ValueError("PCA125 checkpoint inputs changed")
    settings = _dcf(Path(job["settings"]))
    if settings["xnames"].split(",") != LINEAR_X:
        raise ValueError("PCA125 forest equation differs")
    matrix = pd.read_csv(job["matrix"])
    ntrain = int(settings["ntrain"])
    if len(matrix) != ntrain + len(job["targets"]):
        raise ValueError("PCA125 matrix row count differs")
    result = pd.read_csv(job["prediction_path"])
    error = check_engine_output(result, matrix.iloc[ntrain:])
    runtime = _dcf(Path(job["prediction_path"] + ".runtime.dcf"))
    if any(runtime[k] != settings[k] for k in ("prior", "standardization")):
        raise ValueError("PCA125 runtime modes differ")
    return result, error, runtime


def collect_outputs(manifest: dict, source_predictions: pd.DataFrame, linear: pd.DataFrame):
    checks, frames = [], []
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
                    {**r, "model": f"{PREFIX}_seed{job['seed']}", "prediction": float(p)}
                    for r, p in zip(job["targets"], result.prediction, strict=True)
                ]
            )
        )
    individual = pd.concat(frames, ignore_index=True)
    dates = set(individual.target_date)
    ensemble = individual.groupby(
        ["target_date", "origin_date", "actual"], as_index=False
    ).prediction.mean()
    ensemble["model"] = f"{PREFIX}_seed_mean_prediction"
    forecasts = pd.concat(
        [
            source_predictions.loc[source_predictions.target_date.isin(dates)],
            linear.loc[linear.model.eq(BASELINE)],
            individual,
            ensemble,
        ],
        ignore_index=True,
    )
    full = manifest["full_declared_sensitivity"]
    if full and (
        len(dates) != 48
        or len(manifest["jobs"]) != 18
        or dates != set(source_predictions.loc[source_predictions.model.eq("AR4"), "target_date"])
        or manifest["config"] != manifest["declaration"]
    ):
        raise ValueError("Incomplete full PCA125 sensitivity")
    metrics = score_table(forecasts) if full else pd.DataFrame()
    comparisons, effects, gains = [], [], []
    if full:
        indexed = metrics.set_index("model")
        for row in metrics.to_dict("records"):
            if row["model"] == BASELINE or row["model"].startswith(PREFIX):
                reported = manifest["config"][
                    "reported_FA_AR_ratio" if row["model"] == BASELINE else "reported_FA_ARRF_ratio"
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
                if row["model"].startswith(PREFIX):
                    gains.append(
                        {
                            "model": row["model"],
                            "RMSE_reduction_relative_to_own_FA_AR": 1
                            - row["RMSE"] / indexed.loc[BASELINE, "RMSE"],
                        }
                    )
        for seed in manifest["config"]["seeds"]:
            old, new = f"FA_ARRF_seed{seed}", f"{PREFIX}_seed{seed}"
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
        "status": "completed_PCA_eligibility_sensitivity_not_exact_author_replication"
        if full
        else "bounded_PCA125_pilot_not_source_comparison",
        "jobs_verified": len(checks),
        "targets_per_model": len(dates),
        "output_checks": checks,
        "partial_forest_scores_suppressed": not full,
        "metrics": metrics.to_dict("records"),
        "published_ratio_comparisons": comparisons,
        "paired_eligibility_effects": effects,
        "forest_gains_over_own_fixed_factor_comparator": gains,
        "subset_FA_AR_and_all_individual_forest_seeds_within_tolerance": all(
            c["within_diagnostic_tolerance"]
            for c in comparisons
            if not c["ensemble_excluded_from_seed_rule"]
        )
        if comparisons
        else None,
        "exact_author_pipeline_verified": False,
        "original_author_PCA_eligibility_recovered": False,
        "primary_result_replaced": False,
        "eligibility_selected_using_forecast_loss": False,
        "coefficient_basis": "PCA125_coordinates_use_each_jobs_own_matrix",
    }, forecasts


def _inputs(source_run, archive, engine, eligibility_path, primary_config, rscript):
    report = json.loads(eligibility_path.read_text())
    observed = audit_eligibility(source_run, archive, engine, primary_config, rscript=rscript)
    if report != observed:
        raise ValueError("Eligibility report differs from the independently repeated audit")
    return (
        json.loads((source_run / "manifest.json").read_text()),
        load_quarterly(archive),
        pd.read_csv(source_run / "predictions.csv"),
    )


def _provenance(source_run, engine, eligibility_path, declaration, config, limit):
    return {
        "declaration": declaration,
        "config": config,
        "max_refits": limit,
        "source_run": str(source_run.resolve()),
        "source_manifest_sha256": _sha(source_run / "manifest.json"),
        "source_predictions_sha256": _sha(source_run / "predictions.csv"),
        "eligibility_report_sha256": _sha(eligibility_path),
        "external_engine": ensure_engine(engine),
        "sensitivity_source_sha256": _sha(Path(__file__)),
        "dependencies_sha256": _dependencies(),
    }


def validate_provenance(manifest: dict, expected: dict):
    if any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError("PCA125 run provenance differs")


def run_sensitivity(
    source_run: Path,
    archive: Path,
    engine: Path,
    eligibility_path: Path,
    output: Path,
    declaration: dict,
    primary_config: dict,
    *,
    rscript="Rscript",
    r_library=Path("runs/r-library"),
    workers=4,
    trees=None,
    seeds=None,
    max_refits=None,
    resume=False,
):
    if not 1 <= workers <= 8:
        raise ValueError("workers must be 1–8")
    source, data, predictions = _inputs(
        source_run, archive, engine, eligibility_path, primary_config, rscript
    )
    config = {**declaration}
    if trees is not None:
        config["trees"] = trees
    if seeds is not None:
        config["seeds"] = seeds
    provenance = _provenance(source_run, engine, eligibility_path, declaration, config, max_refits)
    if output.exists():
        if not resume:
            raise FileExistsError("Choose a fresh PCA125 output or use --resume")
        manifest = json.loads((output / "manifest.json").read_text())
        validate_provenance(manifest, provenance)
    else:
        output.mkdir(parents=True)
        jobs = prepare_jobs(source, data, output, config, max_refits)
        manifest = {
            **provenance,
            "jobs": jobs,
            "completed": False,
            "full_declared_sensitivity": config == declaration
            and len(jobs) == 18
            and len({r["target_date"] for j in jobs for r in j["targets"]}) == 48,
        }
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    checks, linear = verify_jobs(manifest, source, data, output, predictions, rscript=rscript)
    linear.to_csv(output / "linear_predictions.csv", index=False)
    (output / "linear_checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    adapter = Path(__file__).with_name("reference_mrf.R")
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
        f"PCA125 sensitivity: {len(manifest['jobs'])} jobs; {len(todo)} require fitting", flush=True
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_job, job, engine, rscript, r_library, adapter) for job in todo]
        for future in as_completed(futures):
            with (output / "completed_jobs.jsonl").open("a") as stream:
                stream.write(json.dumps(future.result()) + "\n")
    result, forecasts = collect_outputs(manifest, predictions, linear)
    forecasts.to_csv(output / "predictions.csv", index=False)
    if result["metrics"]:
        pd.DataFrame(result["metrics"]).to_csv(output / "metrics.csv", index=False)
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    manifest.update(completed=True, status=result["status"])
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return result


def _verify_frame(saved: pd.DataFrame, expected: pd.DataFrame, label: str):
    keys = ["model", "target_date"]
    if set(saved) != set(expected) or saved.duplicated(keys).any():
        raise ValueError(f"{label} schema/grid differs")
    a, b = (f.sort_values(keys).set_index(keys) for f in (saved, expected))
    if not a.index.equals(b.index) or not a.origin_date.equals(b.origin_date):
        raise ValueError(f"{label} dates/origins differ")
    _close(a[["actual", "prediction"]], b[["actual", "prediction"]], label)


def audit_sensitivity(
    run: Path,
    archive: Path,
    engine: Path,
    eligibility_path: Path,
    declaration: dict,
    primary_config: dict,
    *,
    rscript="Rscript",
    allow_partial=False,
):
    manifest = json.loads((run / "manifest.json").read_text())
    source_run = Path(manifest["source_run"])
    source, data, predictions = _inputs(
        source_run, archive, engine, eligibility_path, primary_config, rscript
    )
    expected = _provenance(
        source_run,
        engine,
        eligibility_path,
        declaration,
        manifest["config"],
        manifest["max_refits"],
    )
    validate_provenance(manifest, expected)
    checks, linear = verify_jobs(manifest, source, data, run, predictions, rscript=rscript)
    completed, pending, errors = [], [], []
    for job in manifest["jobs"]:
        if (
            not Path(job["prediction_path"]).exists()
            or not Path(job["prediction_path"] + ".runtime.dcf").exists()
        ):
            pending.append({"fit_end": job["fit_end"], "seed": job["seed"]})
        else:
            _, error, runtime = check_output(job)
            errors.append(error)
            completed.append(
                {
                    "fit_end": job["fit_end"],
                    "seed": job["seed"],
                    "sha256": _sha(Path(job["prediction_path"])),
                    "runtime": runtime,
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
        raise ValueError("PCA125 sensitivity is incomplete or differs from its full declaration")
    result = None
    if not pending and manifest["completed"]:
        result, forecasts = collect_outputs(manifest, predictions, linear)
        _verify_frame(pd.read_csv(run / "predictions.csv"), forecasts, "saved PCA125 predictions")
        if json.loads((run / "result.json").read_text()) != result:
            raise ValueError("Saved PCA125 result differs")
        if full:
            verify_aggregates(run, forecasts)
    _verify_frame(
        pd.read_csv(run / "linear_predictions.csv"), linear, "saved PCA125 linear forecasts"
    )
    stored = json.loads((run / "linear_checks.json").read_text())
    if len(stored) != len(checks):
        raise ValueError("Saved linear-check grid differs")
    for a, b in zip(stored, checks, strict=True):
        if (
            a["fit_end"] != b["fit_end"]
            or a["R_version"] != b["R_version"]
            or not a["all_nonfactor_entries_exactly_preserved"]
            or set(a["maximum_absolute_differences"]) != set(b["maximum_absolute_differences"])
        ):
            raise ValueError("Saved linear-check schema differs")
        _close(
            list(a["maximum_absolute_differences"].values()),
            list(b["maximum_absolute_differences"].values()),
            "saved linear check",
        )
    return {
        "status": "full_PCA125_artifacts_verified" if full else "partial_PCA125_integrity_only",
        "source_primary_and_eligibility_audits_repeated": True,
        "sensitivity_source_sha256": _sha(Path(__file__)),
        "dependencies_sha256": _dependencies(),
        "manifest_sha256": _sha(run / "manifest.json"),
        "eligibility_report_sha256": _sha(eligibility_path),
        "jobs_verified": len(completed),
        "pending_jobs": pending,
        "output_checks": completed,
        "linear_checks": checks,
        "maximum_coefficient_reconstruction_error": max(errors, default=0),
        "partial_forest_scores_suppressed": not full,
        **{
            k: result[k] if full else []
            for k in (
                "metrics",
                "published_ratio_comparisons",
                "paired_eligibility_effects",
                "forest_gains_over_own_fixed_factor_comparator",
            )
        },
        "subset_FA_AR_and_all_individual_forest_seeds_within_tolerance": result[
            "subset_FA_AR_and_all_individual_forest_seeds_within_tolerance"
        ]
        if full
        else None,
        "exact_author_pipeline_verified": False,
        "original_author_PCA_eligibility_recovered": False,
        "primary_result_replaced": False,
        "eligibility_selected_using_forecast_loss": False,
    }
