"""Declared appendix NN ensembles on the unchanged quarterly primary states."""

from __future__ import annotations

import hashlib
import json
import time
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

from jev_factor.arrf_audit import verify_aggregates
from jev_factor.neural import (
    TORCH_VERSION,
    audit_member,
    backend,
    fit_member,
    save_member,
    validate_training,
)
from jev_factor.replication import score_table
from jev_factor.replication_audit import _dcf, audit_run

PRIMARY_CONFIG_DIGEST = "cd2df267c60250cf06a310b2265421a068c642b33c19b65948a359fb980d15e8"
SEEDS = [101, 202, 303]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def validate_config(config, *, declaration=False):
    fixed = {
        "study": "quarterly_unemployment_appendix_NN_control",
        "model": "NN",
        "required_torch_version": TORCH_VERSION,
        "state_rule": "unchanged_original_all248_primary_1041_state_columns",
        "validation": "random_omitted_15_percent_of_past_fitting_window",
        "scaler_uses_validation_covariates_but_not_validation_outcomes": True,
        "ensemble": "uniform_mean_of_10_member_forecasts_not_parameter_average",
        "reported_RMSE_over_AR4": 0.80,
        "absolute_ratio_diagnostic_tolerance": 0.03,
        "all_three_seed_ensembles_required_for_diagnostic": True,
        "outer_seed_mean_excluded_from_diagnostic": True,
        "prior_primary_and_control_losses_already_public": True,
        "chosen_using_new_NN_losses": False,
        "original_primary_preserved": True,
        "original_NN_runner_and_unstated_training_details_recovered": False,
        "control_match_cannot_establish_FA_ARRF_replication": True,
    }
    if (
        set(config) != {*fixed, "declaration_date", "members", "seeds", "training"}
        or any(type(config[k]) is not type(v) or config[k] != v for k, v in fixed.items())
        or type(config["members"]) is not int
        or not 1 <= config["members"] <= 10
        or not config["seeds"]
        or any(type(s) is not int for s in config["seeds"])
        or config["seeds"] != [s for s in SEEDS if s in config["seeds"]]
        or (declaration and (config["members"] != 10 or config["seeds"] != SEEDS))
    ):
        raise ValueError("Only the declared NN control or a reduced pilot is supported")
    validate_training(config["training"], declaration=declaration)


def source_inputs(source_run, archive, primary, rscript):
    canonical = json.dumps(primary, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != PRIMARY_CONFIG_DIGEST:
        raise ValueError("NN requires the unchanged original primary configuration")
    audit = audit_run(source_run, archive, primary, rscript=rscript)
    if (
        not audit["full_48_quarter_artifacts_verified"]
        or not audit["matches_declared_config"]
        or len(audit["recomputed_state_input_checks"]) != 6
        or any(
            c["columns_including_target"] != 1042 for c in audit["recomputed_state_input_checks"]
        )
    ):
        raise ValueError("NN requires all six complete original 1041-column matrices")
    source = json.loads((source_run / "manifest.json").read_text())
    if not source["completed"] or source["max_refits"] is not None:
        raise ValueError("NN requires a complete original primary run")
    return source


def jobs_for(source, output, config, limit):
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 6):
        raise ValueError("NN refit limit must be one through six")
    keys = [(j["group"], j["seed"]) for j in source["jobs"]]
    if len(keys) != 18 or set(keys) != {(g, s) for g in range(6) for s in SEEDS}:
        raise ValueError("Missing or duplicated original NN source grid")
    result = []
    for original in source["jobs"]:
        if original["seed"] not in config["seeds"] or (
            limit is not None and original["group"] >= limit
        ):
            continue
        group, seed = original["group"], original["seed"]
        prefix = output / f"refit_{group:02d}_{original['fit_end']}" / f"seed_{seed}"
        case_seed = int(np.random.SeedSequence([seed, group, 0x4E4E]).generate_state(1)[0])
        result.append(
            {
                "group": group,
                "seed": seed,
                "case_seed": case_seed,
                "fit_end": original["fit_end"],
                "matrix": original["matrix"],
                "matrix_sha256": original["matrix_sha256"],
                "settings": original["settings"],
                "settings_sha256": original["settings_sha256"],
                "ntrain": int(_dcf(Path(original["settings"]))["ntrain"]),
                "targets": original["targets"],
                "member_directories": [
                    str((prefix / f"member_{i:02d}").resolve()) for i in range(config["members"])
                ],
            }
        )
    return result


def equation_arrays(job):
    for field in ("matrix", "settings"):
        if _sha(job[field]) != job[field + "_sha256"]:
            raise ValueError("Frozen NN source matrix or settings changed")
    frame = pd.read_csv(job["matrix"], float_precision="round_trip")
    n = job["ntrain"]
    if (
        frame.shape[1] != 1042
        or not frame.columns.is_unique
        or frame.columns[0] != "target"
        or not np.isfinite(frame.to_numpy()).all()
        or len(frame) - n != len(job["targets"])
        or len(job["targets"]) != 8
    ):
        raise ValueError("Invalid original NN matrix or target grid")
    # Forecast target placeholders/actuals are not passed to any training function.
    return (
        frame.iloc[:n, 1:].to_numpy(),
        frame.target.iloc[:n].to_numpy(),
        frame.iloc[n:, 1:].to_numpy(),
    )


def provenance(source_run, declaration, config, limit):
    names = (
        "neural.py",
        "quarterly.py",
        "replication.py",
        "replication_audit.py",
        "reference_linear.R",
        "reference_mrf.R",
        "arrf_audit.py",
    )
    root = Path(__file__).resolve().parents[2]
    return {
        "declaration": declaration,
        "config": config,
        "max_refits": limit,
        "source_run": str(source_run.resolve()),
        "source_manifest_sha256": _sha(source_run / "manifest.json"),
        "source_predictions_sha256": _sha(source_run / "predictions.csv"),
        "backend": backend(),
        "runner_sha256": _sha(Path(__file__)),
        "dependencies_sha256": {n: _sha(Path(__file__).with_name(n)) for n in names},
        "environment_files_sha256": {n: _sha(root / n) for n in ("pyproject.toml", "uv.lock")},
    }


def verify_manifest(manifest, expected, source, output):
    if any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError("NN source, configuration, code, backend or dependency lock changed")
    if manifest["jobs"] != jobs_for(source, output, manifest["config"], manifest["max_refits"]):
        raise ValueError("NN model/refit/member/target/path grid differs")


def check_member(job, member, training, *, refit=False):
    x, y, future = equation_arrays(job)
    directory = Path(job["member_directories"][member])
    check = audit_member(directory, x, y, future, job["case_seed"], member, training, refit=refit)
    metadata = json.loads((directory / "member.json").read_text())
    return metadata["forecast_prediction"], {
        "group": job["group"],
        "outer_seed": job["seed"],
        **check,
    }


def collect(manifest):
    config = manifest["config"]
    predictions, member_rows, checks, pending = [], [], [], []
    completed = 0
    for job in manifest["jobs"]:
        values, missing = [], []
        for member, directory in enumerate(job["member_directories"]):
            if not (Path(directory) / "member.json").exists():
                missing.append(member)
                continue
            prediction, check = check_member(job, member, config["training"])
            check.pop("deterministic_refit_verified")  # Final auditor proves training separately.
            checks.append(check)
            values.append(prediction)
            member_rows.extend(
                {
                    **record,
                    "group": job["group"],
                    "fit_end": job["fit_end"],
                    "seed": job["seed"],
                    "member": member,
                    "prediction": float(p),
                }
                for record, p in zip(job["targets"], prediction, strict=True)
            )
        if missing:
            pending.append({"group": job["group"], "seed": job["seed"], "members": missing})
            continue
        mean = np.mean(np.asarray(values, dtype=float), axis=0)
        predictions.extend(
            {**record, "model": f"NN_seed{job['seed']}", "prediction": float(p)}
            for record, p in zip(job["targets"], mean, strict=True)
        )
        completed += 1
    members = pd.DataFrame(
        member_rows,
        columns=[
            "target_date",
            "origin_date",
            "actual",
            "group",
            "fit_end",
            "seed",
            "member",
            "prediction",
        ],
    )
    if predictions:
        new = pd.DataFrame(predictions)
        source = pd.read_csv(
            Path(manifest["source_run"]) / "predictions.csv", float_precision="round_trip"
        )
        common = set.intersection(
            *(set(new.loc[new.model.eq(f"NN_seed{s}"), "target_date"]) for s in config["seeds"])
        )
        new = new.loc[new.target_date.isin(common)]
        mean = new.groupby(
            ["target_date", "origin_date", "actual"], as_index=False
        ).prediction.mean()
        mean["model"] = "NN_outer_seed_mean_prediction"
        source = source.loc[source.target_date.isin(common)]
        combined = pd.concat([source, new, mean], ignore_index=True)
    else:
        combined = pd.DataFrame(
            columns=["target_date", "origin_date", "actual", "model", "prediction"]
        )
    full = (
        manifest["max_refits"] is None
        and config == manifest["declaration"]
        and completed == 18
        and len(checks) == 180
        and not pending
    )
    result = {
        "status": "completed_NN_control_not_exact_author_replication"
        if full
        else "partial_NN_integrity_only",
        "ensemble_fits_verified": completed,
        "members_verified": len(checks),
        "pending_jobs": pending,
        "member_checks": checks,
        "targets_per_model": len(combined.target_date.unique()),
        "partial_scores_suppressed": not full,
        "metrics": [],
        "published_ratio_comparisons": [],
        "all_seed_ensembles_within_ratio_tolerance": None,
        "FA_ARRF_replication_established": False,
        "exact_author_NN_pipeline_verified": False,
        "primary_result_replaced": False,
    }
    if full:
        if len(combined) != 480 or combined.groupby("model").size().ne(48).any():
            raise ValueError("Full NN comparison requires ten methods on all 48 dates")
        metrics = score_table(combined)
        comparisons = []
        for model in [*(f"NN_seed{s}" for s in SEEDS), "NN_outer_seed_mean_prediction"]:
            ratio = float(metrics.loc[metrics.model.eq(model), "RMSE_over_AR4"].iloc[0])
            comparisons.append(
                {
                    "model": model,
                    "reported_ratio": 0.80,
                    "reconstructed_ratio": ratio,
                    "difference": ratio - 0.80,
                    "within_ratio_tolerance": bool(abs(ratio - 0.80) <= 0.03),
                    "outer_seed_mean_excluded_from_diagnostic": model
                    == "NN_outer_seed_mean_prediction",
                }
            )
        result.update(
            metrics=metrics.to_dict("records"),
            published_ratio_comparisons=comparisons,
            all_seed_ensembles_within_ratio_tolerance=all(
                c["within_ratio_tolerance"] for c in comparisons[:3]
            ),
        )
    return combined, members, result


def run_comparison(
    source_run,
    archive,
    output,
    declaration,
    primary,
    *,
    members=None,
    epochs=None,
    seeds=None,
    max_refits=None,
    prepare_only=False,
    resume=False,
    rscript="Rscript",
):
    validate_config(declaration, declaration=True)
    config = deepcopy(declaration)
    if members is not None:
        config["members"] = members
    if epochs is not None:
        config["training"]["epochs"] = epochs
    if seeds is not None:
        config["seeds"] = list(seeds)
    validate_config(config)
    source_run, output = Path(source_run).resolve(), Path(output).resolve()
    source = source_inputs(source_run, archive, primary, rscript)
    expected = provenance(source_run, declaration, config, max_refits)
    if resume:
        manifest = json.loads((output / "manifest.json").read_text())
        verify_manifest(manifest, expected, source, output)
    else:
        if output.exists():
            raise FileExistsError("Choose a fresh NN comparison output")
        jobs = jobs_for(source, output, config, max_refits)
        for job in jobs:
            equation_arrays(job)
        output.mkdir(parents=True)
        manifest = {**expected, "jobs": jobs, "completed": False}
        _save(output / "manifest.json", manifest)
    if prepare_only:
        return {
            "status": "NN_prepared_no_training_or_scores",
            "ensembles_planned": len(manifest["jobs"]),
            "members_planned": len(manifest["jobs"]) * config["members"],
        }
    for job in manifest["jobs"]:
        for member, folder in enumerate(job["member_directories"]):
            directory = Path(folder)
            if (directory / "member.json").exists():
                check_member(job, member, config["training"])
                continue
            if directory.exists():
                raise ValueError(
                    "Incomplete NN member retained; choose a fresh run rather than overwrite"
                )
            x, y, future = equation_arrays(job)
            start = time.perf_counter()
            weights, metadata = fit_member(
                x, y, future, job["case_seed"], member, config["training"]
            )
            save_member(directory, weights, metadata)
            check_member(job, member, config["training"])
            print(
                f"Finished NN {job['fit_end']} seed {job['seed']} member {member:02d} "
                f"in {time.perf_counter() - start:.1f}s",
                flush=True,
            )
    predictions, member_predictions, result = collect(manifest)
    predictions.to_csv(output / "predictions.csv", index=False, float_format="%.17g")
    member_predictions.to_csv(output / "member_predictions.csv", index=False, float_format="%.17g")
    if not result["partial_scores_suppressed"]:
        pd.DataFrame(result["metrics"]).to_csv(
            output / "metrics.csv", index=False, float_format="%.17g"
        )
    _save(output / "result.json", result)
    manifest["completed"] = not result["pending_jobs"]
    _save(output / "manifest.json", manifest)
    return result


def _verify_frame(path, expected, keys, label):
    saved = pd.read_csv(path, float_precision="round_trip")
    if list(saved) != list(expected) or saved.duplicated(keys).any():
        raise ValueError(f"Saved NN {label} schema/grid differs")
    saved, expected = (f.sort_values(keys).reset_index(drop=True) for f in (saved, expected))
    if len(saved) != len(expected):
        raise ValueError(f"Saved NN {label} row count differs")
    for column in saved:
        if pd.api.types.is_numeric_dtype(expected[column]):
            if not np.allclose(saved[column], expected[column], rtol=0, atol=1e-13):
                raise ValueError(f"Saved NN {label} numeric value differs")
        elif not saved[column].equals(expected[column]):
            raise ValueError(f"Saved NN {label} identity/order differs")


def audit_comparison(run, archive, declaration, primary, *, allow_partial=False, rscript="Rscript"):
    validate_config(declaration, declaration=True)
    run = Path(run).resolve()
    manifest = json.loads((run / "manifest.json").read_text())
    validate_config(manifest["config"])
    source_run = Path(manifest["source_run"])
    source = source_inputs(source_run, archive, primary, rscript)
    expected = provenance(source_run, declaration, manifest["config"], manifest["max_refits"])
    verify_manifest(manifest, expected, source, run)
    predictions, members, result = collect(manifest)
    if result["partial_scores_suppressed"] and not allow_partial:
        raise ValueError("Full NN audit requires all 180 declared members and 48 dates")
    if manifest["completed"] != (not result["pending_jobs"]):
        raise ValueError("NN completion marker differs from verified member grid")
    if json.loads((run / "result.json").read_text()) != result:
        raise ValueError("Saved NN result record differs")
    _verify_frame(
        run / "member_predictions.csv",
        members,
        ["group", "seed", "member", "target_date"],
        "member forecasts",
    )
    if not result["partial_scores_suppressed"]:
        verify_aggregates(run, predictions)
    else:
        if (run / "metrics.csv").exists():
            raise ValueError("Partial NN comparison must suppress metrics")
        _verify_frame(
            run / "predictions.csv", predictions, ["model", "target_date"], "partial forecasts"
        )
    deterministic = []
    for job in manifest["jobs"]:
        for member, directory in enumerate(job["member_directories"]):
            if not (Path(directory) / "member.json").exists():
                continue
            _, check = check_member(job, member, manifest["config"]["training"], refit=True)
            deterministic.append(
                {
                    "group": job["group"],
                    "outer_seed": job["seed"],
                    "member": member,
                    "all_parameters_and_training_history_identical": check[
                        "deterministic_refit_verified"
                    ],
                }
            )
    return {
        **result,
        "status": "full_NN_artifacts_verified"
        if not result["partial_scores_suppressed"]
        else "partial_NN_integrity_only",
        "primary_artifact_audit_repeated": True,
        "manifest_sha256": _sha(run / "manifest.json"),
        "runner_sha256": _sha(Path(__file__)),
        "deterministic_member_refits": deterministic,
    }
