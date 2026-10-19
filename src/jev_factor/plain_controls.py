"""Separate RF-MAF and AR(2)+RF controls on the frozen primary state matrices."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
import sklearn
from threadpoolctl import threadpool_limits

from jev_factor.arrf_audit import verify_aggregates
from jev_factor.plain_forest import PlainBlockForest, block_subsample
from jev_factor.replication import ensure_engine, score_table
from jev_factor.replication_audit import _close, _dcf, audit_run

MODELS = ["RF_MAF", "AR_plus_RF"]
PRIMARY_CONFIG_DIGEST = "cd2df267c60250cf06a310b2265421a068c642b33c19b65948a359fb980d15e8"
FOREST = {
    "block_size": 8,
    "rate": 0.75,
    "feature_fraction": 1 / 3,
    "min_parent": 10,
    "min_leaf": 1,
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _backend():
    return {
        "sklearn": sklearn.__version__,
        "numpy": np.__version__,
        "python": platform.python_version(),
    }


def validate_config(config, *, declaration=False):
    if (
        config["models"] != MODELS
        or config["forest"] != FOREST
        or config["required_sklearn_version"] != "1.9.1"
        or sklearn.__version__ != config["required_sklearn_version"]
        or config["state_rule"] != "unchanged_original_all248_primary_1041_state_columns"
        or config["scaling"] != "training_only_sample_SD_target_after_AR2_filter"
        or config["target_zero_SD_rule"] != "unit_scale_if_SD_leq_1e-12"
        or config["sampling_rule"]
        != "native_random_group_quantile_law_numpy_not_R_seed_equivalence"
        or config["reported_ratios"] != {"RF_MAF": 0.85, "AR_plus_RF": 0.84}
        or config["absolute_ratio_diagnostic_tolerance"] != 0.03
        or config["selected_using_new_control_test_losses"] is not False
        or config["all_individual_seeds_of_both_controls_required_for_control_gate"] is not True
        or config["ensembles_excluded_from_seed_gate"] is not True
        or config["AR2_filter_reported_separately_not_a_source_Table4_cell"] is not True
        or config["original_primary_and_all_sensitivities_preserved"] is not True
        or config["original_author_plain_RF_backend_or_exact_per_table_settings_recovered"]
        is not False
        or config["control_match_cannot_establish_FA_ARRF_replication"] is not True
        or type(config["trees"]) is not int
        or not 1 <= config["trees"] <= 100
        or not config["seeds"]
        or any(type(seed) is not int for seed in config["seeds"])
        or len(set(config["seeds"])) != len(config["seeds"])
        or not set(config["seeds"]).issubset({101, 202, 303})
        or (declaration and (config["trees"] != 100 or config["seeds"] != [101, 202, 303]))
    ):
        raise ValueError(
            "Only the declared plain-control construction or a reduced pilot is supported"
        )


@threadpool_limits.wrap(limits=1)
def fit_inputs(frame, ntrain, model):
    """Only training target values enter the filter and scaling operations."""
    if (
        model not in MODELS
        or type(ntrain) is not int
        or not 16 <= ntrain < len(frame)
        or not frame.columns.is_unique
        or frame.columns[0] != "target"
        or not {"y_lag1", "y_lag2"}.issubset(frame)
        or not np.isfinite(frame.to_numpy(dtype=float)).all()
    ):
        raise ValueError("Invalid finite control matrix, equation or training split")
    x = np.ascontiguousarray(frame.iloc[:, 1:].to_numpy(dtype=float))
    center, scale = x[:ntrain].mean(axis=0), x[:ntrain].std(axis=0, ddof=1)
    if (scale <= 1e-12).any():
        raise ValueError("Frozen primary state must retain nonconstant training columns")
    target = frame.target.iloc[:ntrain].to_numpy(dtype=float)
    ar = np.column_stack([np.ones(len(frame)), frame[["y_lag1", "y_lag2"]]])
    beta = np.linalg.lstsq(ar[:ntrain], target, rcond=None)[0] if model == "AR_plus_RF" else []
    base = ar @ beta if model == "AR_plus_RF" else np.zeros(len(frame))
    residual = target - base[:ntrain]
    ymean, yscale = float(residual.mean()), float(residual.std(ddof=1))
    if yscale <= 1e-12:
        yscale = 1.0
    metadata = {
        "state_names": list(frame.columns[1:]),
        "ntrain": ntrain,
        "forecast_rows": len(frame) - ntrain,
        "center_x": center.tolist(),
        "scale_x": scale.tolist(),
        "base_coefficients": list(beta),
        "center_y": ymean,
        "scale_y": yscale,
    }
    return (x - center) / scale, (residual - ymean) / yscale, base, metadata


def r_ar2(matrix: Path, ntrain: int, rscript: str):
    with TemporaryDirectory(prefix="control-ar2-") as scratch:
        result = subprocess.run(
            [
                rscript,
                "--vanilla",
                str(Path(__file__).with_name("reference_control_ar2.R")),
                str(matrix.resolve()),
                str(ntrain),
                scratch,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"Independent AR(2) QR failed: {result.stderr[-2000:]}")
        beta = pd.read_csv(Path(scratch) / "beta.csv")
        prediction = pd.read_csv(Path(scratch) / "prediction.csv").prediction.to_numpy()
        residual = pd.read_csv(Path(scratch) / "residual.csv").residual.to_numpy()
    if list(beta.term) != ["intercept", "y_lag1", "y_lag2"]:
        raise ValueError("Independent AR(2) term order differs")
    return beta.coefficient.to_numpy(), prediction, residual, result.stdout.strip()


def fit_payload(frame, ntrain, model, seed, config):
    x, y, base, preprocessing = fit_inputs(frame, ntrain, model)
    fitted = PlainBlockForest(trees=config["trees"], seed=seed, **config["forest"]).fit(
        x[:ntrain], y
    )
    trees = []
    for tree, sample, tree_seed in zip(
        fitted.models_, fitted.samples_, fitted.tree_seeds_, strict=True
    ):
        nodes = tree.tree_
        trees.append(
            {
                "seed": tree_seed,
                "groups": sample.groups.tolist(),
                "weights": sample.group_weights.tolist(),
                "rows": sample.rows.tolist(),
                "left": nodes.children_left.tolist(),
                "right": nodes.children_right.tolist(),
                "feature": nodes.feature.tolist(),
                "threshold": nodes.threshold.tolist(),
                "value": nodes.value[:, 0, 0].tolist(),
                "count": nodes.n_node_samples.tolist(),
            }
        )
    payload = {
        "model": model,
        "seed": seed,
        "backend": _backend(),
        "forest_settings": config["forest"],
        "preprocessing": preprocessing,
        "trees": trees,
    }
    nonlinear = preprocessing["center_y"] + preprocessing["scale_y"] * fitted.predict(x[ntrain:])
    return payload, pd.DataFrame(
        {
            "prediction": base[ntrain:] + nonlinear,
            "base_prediction": base[ntrain:],
            "nonlinear_prediction": nonlinear,
        }
    )


def _tree_predictions(tree, x, y, query, config):
    """Independent JSON-tree traversal and direct sampled-node mean checks."""
    integer_fields = ("left", "right", "feature", "count")
    if any(any(type(v) is not int for v in tree[k]) for k in integer_fields):
        raise ValueError("Tree integer fields differ")
    left, right, feature, count = (np.asarray(tree[k], dtype=int) for k in integer_fields)
    threshold, value = (np.asarray(tree[k], dtype=float) for k in ("threshold", "value"))
    size = len(left)
    if (
        not 1 <= size <= 2 * len(y) - 1
        or any(a.shape != (size,) for a in (left, right, feature, count, threshold, value))
        or not np.isfinite(threshold).all()
        or not np.isfinite(value).all()
    ):
        raise ValueError("Invalid serialized tree dimensions or values")
    leaf = left == -1
    internal = np.flatnonzero(~leaf)
    if (
        not np.array_equal(leaf, right == -1)
        or (feature[leaf] != -2).any()
        or ((feature[internal] < 0) | (feature[internal] >= x.shape[1])).any()
        or (left[internal] <= internal).any()
        or (right[internal] <= internal).any()
        or (left[internal] >= size).any()
        or (right[internal] >= size).any()
    ):
        raise ValueError("Invalid tree topology or feature indices")
    parents = np.bincount(np.r_[left[internal], right[internal]], minlength=size)
    if not np.array_equal(parents, np.r_[0, np.ones(size - 1, dtype=int)]):
        raise ValueError("Tree nodes must have exactly one parent, except the root")
    x32, query32 = x.astype(np.float32), query.astype(np.float32)
    if not np.isfinite(x32).all() or not np.isfinite(query32).all():
        raise ValueError("Features overflowed the declared CART float32 backend")
    stack, means, maximum = [(0, np.arange(len(y)))], np.empty(size), 0.0
    while stack:
        node, rows = stack.pop()
        if not len(rows) or count[node] != len(rows):
            raise ValueError("Tree node training membership/count differs")
        means[node] = y[rows].mean()
        maximum = max(maximum, _close([value[node]], [means[node]], "sampled node mean"))
        if leaf[node]:
            if len(rows) < config["forest"]["min_leaf"]:
                raise ValueError("Terminal leaf is too small")
        else:
            choose = x32[rows, feature[node]] <= threshold[node]
            a, b = rows[choose], rows[~choose]
            if (
                len(rows) < config["forest"]["min_parent"]
                or min(len(a), len(b)) < config["forest"]["min_leaf"]
            ):
                raise ValueError("Tree violates declared parent/leaf size")
            stack.extend([(left[node], a), (right[node], b)])
    nodes = np.zeros(len(query), dtype=int)
    for _ in range(size):
        active = np.flatnonzero(~leaf[nodes])
        if not len(active):
            break
        current = nodes[active]
        choose = query32[active, feature[current]] <= threshold[current]
        nodes[active] = np.where(choose, left[current], right[current])
    if not leaf[nodes].all():
        raise ValueError("Tree traversal did not terminate")
    return means[nodes], maximum


def verify_payload(payload, frame, ntrain, model, seed, config):
    x, y, base, metadata = fit_inputs(frame, ntrain, model)
    if (
        payload["model"] != model
        or payload["seed"] != seed
        or payload["backend"] != _backend()
        or payload["forest_settings"] != config["forest"]
        or payload["preprocessing"] != metadata
        or len(payload["trees"]) != config["trees"]
    ):
        raise ValueError("Control payload modes, preprocessing or tree count differs")
    rng, predictions, error = np.random.default_rng(seed), [], 0.0
    for tree in payload["trees"]:
        sample = block_subsample(
            ntrain, rng, block_size=config["forest"]["block_size"], rate=config["forest"]["rate"]
        )
        tree_seed = int(rng.integers(np.iinfo(np.int32).max))
        if (
            type(tree["seed"]) is not int
            or any(type(v) is not int for name in ("groups", "rows") for v in tree[name])
            or tree["groups"] != sample.groups.tolist()
            or tree["weights"] != sample.group_weights.tolist()
            or tree["rows"] != sample.rows.tolist()
            or tree["seed"] != tree_seed
        ):
            raise ValueError("Control sampling provenance differs")
        prediction, difference = _tree_predictions(
            tree, x[sample.rows], y[sample.rows], x[ntrain:], config
        )
        predictions.append(prediction)
        error = max(error, difference)
    nonlinear = metadata["center_y"] + metadata["scale_y"] * np.mean(predictions, axis=0)
    expected = pd.DataFrame(
        {
            "prediction": base[ntrain:] + nonlinear,
            "base_prediction": base[ntrain:],
            "nonlinear_prediction": nonlinear,
        }
    )
    return expected, error


def jobs_for(source, config, output, limit):
    validate_config(config)
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 6):
        raise ValueError("Pilot refit limit must be 1-6")
    selected = [
        j
        for j in source["jobs"]
        if j["seed"] in config["seeds"] and (limit is None or j["group"] < limit)
    ]
    if not selected:
        raise ValueError("No selected primary jobs")
    keys = [(j["group"], j["seed"]) for j in selected]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate selected primary refit/seed jobs")
    jobs = []
    for original in selected:
        for model in MODELS:
            directory = output / f"refit_{original['group']:02d}_{original['fit_end']}"
            prefix = directory / f"{model}_seed_{original['seed']}"
            jobs.append(
                {
                    **{
                        k: original[k]
                        for k in (
                            "group",
                            "seed",
                            "fit_end",
                            "targets",
                            "matrix",
                            "matrix_sha256",
                            "settings",
                            "settings_sha256",
                        )
                    },
                    "model": model,
                    "ntrain": int(_dcf(Path(original["settings"]))["ntrain"]),
                    "tree_path": str(prefix.with_suffix(".trees.json").resolve()),
                    "prediction_path": str(prefix.with_suffix(".csv").resolve()),
                }
            )
    return jobs


def _inputs(source_run, archive, engine, primary, rscript):
    digest = hashlib.sha256(
        json.dumps(primary, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if digest != PRIMARY_CONFIG_DIGEST:
        raise ValueError("Plain controls require the frozen original primary configuration")
    report = audit_run(source_run, archive, primary, rscript=rscript)
    if (
        not report["full_48_quarter_artifacts_verified"]
        or not report["matches_declared_config"]
        or primary["factor_panel"] != "all"
        or primary["pca_rank"] != 5
        or len(report["recomputed_state_input_checks"]) != 6
        or any(
            r["columns_including_target"] != 1042 for r in report["recomputed_state_input_checks"]
        )
    ):
        raise ValueError("Use the complete declared all-248 primary with 1041 state columns")
    ensure_engine(engine)
    return json.loads((source_run / "manifest.json").read_text()), pd.read_csv(
        source_run / "predictions.csv", float_precision="round_trip"
    )


def _provenance(source_run, engine, declaration, config, limit):
    names = (
        "plain_forest.py",
        "quarterly.py",
        "replication.py",
        "replication_audit.py",
        "arrf_audit.py",
        "reference_linear.R",
        "reference_mrf.R",
        "reference_control_ar2.R",
    )
    return {
        "declaration": declaration,
        "config": config,
        "max_refits": limit,
        "source_run": str(source_run.resolve()),
        "source_manifest_sha256": _sha(source_run / "manifest.json"),
        "source_predictions_sha256": _sha(source_run / "predictions.csv"),
        "external_engine_of_primary": ensure_engine(engine),
        "backend": _backend(),
        "runner_source_sha256": _sha(Path(__file__)),
        "dependencies_sha256": {n: _sha(Path(__file__).with_name(n)) for n in names},
    }


def validate_provenance(manifest, expected):
    if any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError("Plain-control run provenance differs")


def verify_inputs(manifest, source, output, rscript):
    jobs = jobs_for(source, manifest["config"], output, manifest["max_refits"])
    if manifest["jobs"] != jobs:
        raise ValueError("Control grid, source paths, target/origin records or outputs differ")
    checked, checks = set(), []
    for job in jobs:
        if any(_sha(job[k]) != job[k + "_sha256"] for k in ("matrix", "settings")):
            raise ValueError("Frozen primary matrix or settings changed")
        if job["group"] in checked:
            continue
        checked.add(job["group"])
        frame = pd.read_csv(job["matrix"], float_precision="round_trip")
        _, _, base, metadata = fit_inputs(frame, job["ntrain"], "AR_plus_RF")
        errors, version = {}, None
        if rscript is not None:
            beta, prediction, residual, version = r_ar2(Path(job["matrix"]), job["ntrain"], rscript)
            errors = {
                "AR2_coefficients": _close(
                    beta, metadata["base_coefficients"], "AR2 QR coefficients"
                ),
                "AR2_all_row_predictions": _close(prediction, base, "AR2 QR predictions"),
                "AR2_training_residuals": _close(
                    residual,
                    frame.target.iloc[: job["ntrain"]] - base[: job["ntrain"]],
                    "AR2 QR residuals",
                ),
            }
        checks.append(
            {
                "fit_end": job["fit_end"],
                "all_primary_matrix_entries_preserved": True,
                "state_columns": len(frame.columns) - 1,
                "R_version": version,
                "maximum_absolute_differences": errors,
            }
        )
    return checks


def check_job(job, config, *, refit=False):
    if any(_sha(job[k]) != job[k + "_sha256"] for k in ("matrix", "settings")):
        raise ValueError("Control checkpoint primary inputs changed")
    frame = pd.read_csv(job["matrix"], float_precision="round_trip")
    payload = json.loads(Path(job["tree_path"]).read_text())
    expected, error = verify_payload(
        payload, frame, job["ntrain"], job["model"], job["seed"], config
    )
    saved = pd.read_csv(job["prediction_path"], float_precision="round_trip")
    if list(saved) != list(expected) or len(saved) != len(job["targets"]):
        raise ValueError("Control saved forecast schema or target row count differs")
    forecast_error = _close(saved, expected, "independently reconstructed control forecasts")
    if refit:
        repeated, _ = fit_payload(frame, job["ntrain"], job["model"], job["seed"], config)
        if payload != repeated:
            raise ValueError("Saved CART forest differs from deterministic refit")
    return saved, {
        "fit_end": job["fit_end"],
        "model": job["model"],
        "seed": job["seed"],
        "tree_sha256": _sha(job["tree_path"]),
        "prediction_sha256": _sha(job["prediction_path"]),
        "maximum_node_mean_error_standardized_units": error,
        "maximum_forecast_reconstruction_error": forecast_error,
        "deterministic_refit_verified": refit,
    }


def collect_outputs(manifest, source_predictions, *, refit=False):
    frames, checks, filters = [], [], {}
    for job in manifest["jobs"]:
        saved, check = check_job(job, manifest["config"], refit=refit)
        checks.append(check)
        frames.extend(
            {**record, "model": f"{job['model']}_seed{job['seed']}", "prediction": float(p)}
            for record, p in zip(job["targets"], saved.prediction, strict=True)
        )
        if job["model"] == "AR_plus_RF":
            if job["group"] in filters:
                _close(filters[job["group"]][1], saved.base_prediction, "shared AR2 filter")
            else:
                filters[job["group"]] = job["targets"], saved.base_prediction.to_numpy()
    individual = pd.DataFrame(frames)
    dates, additions = set(individual.target_date), [individual]
    for model in MODELS:
        mean = (
            individual.loc[individual.model.str.startswith(model + "_seed")]
            .groupby(["target_date", "origin_date", "actual"], as_index=False)
            .prediction.mean()
        )
        mean["model"] = model + "_seed_mean_prediction"
        additions.append(mean)
    additions.append(
        pd.DataFrame(
            [
                {**r, "model": "AR2_filter", "prediction": float(p)}
                for records, values in filters.values()
                for r, p in zip(records, values, strict=True)
            ]
        )
    )
    forecasts = pd.concat(
        [source_predictions.loc[source_predictions.target_date.isin(dates)], *additions],
        ignore_index=True,
    )
    full = manifest["full_declared_comparison"]
    if full and (
        manifest["config"] != manifest["declaration"]
        or len(manifest["jobs"]) != 36
        or len(dates) != 48
        or dates != set(source_predictions.target_date)
    ):
        raise ValueError("Incomplete full plain-control comparison")
    metrics = score_table(forecasts).to_dict("records") if full else []
    comparisons = []
    for row in metrics:
        for model in MODELS:
            if row["model"].startswith(model + "_seed"):
                reported = manifest["config"]["reported_ratios"][model]
                delta = row["RMSE_over_AR4"] - reported
                comparisons.append(
                    {
                        "model": row["model"],
                        "reported_ratio": reported,
                        "reconstructed_ratio": row["RMSE_over_AR4"],
                        "difference": delta,
                        "within_diagnostic_tolerance": abs(delta) <= 0.03,
                        "ensemble_excluded_from_seed_rule": row["model"].endswith(
                            "mean_prediction"
                        ),
                    }
                )
    return {
        "status": "completed_plain_controls_not_exact_author_replication"
        if full
        else "bounded_plain_control_pilot_not_source_comparison",
        "jobs_verified": len(checks),
        "targets_per_model": len(dates),
        "output_checks": checks,
        "partial_scores_suppressed": not full,
        "metrics": metrics,
        "published_ratio_comparisons": comparisons,
        "all_individual_control_seeds_within_tolerance": all(
            r["within_diagnostic_tolerance"]
            for r in comparisons
            if not r["ensemble_excluded_from_seed_rule"]
        )
        if comparisons
        else None,
        "FA_ARRF_replication_established": False,
        "exact_author_pipeline_verified": False,
        "primary_result_replaced": False,
    }, forecasts


def _write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def _verify_linear_checks(stored, linear):
    if len(linear) != len(stored):
        raise ValueError("Saved AR2 check grid differs")
    for a, b in zip(stored, linear, strict=True):
        if {k: v for k, v in a.items() if k != "maximum_absolute_differences"} != {
            k: v for k, v in b.items() if k != "maximum_absolute_differences"
        } or set(a["maximum_absolute_differences"]) != set(b["maximum_absolute_differences"]):
            raise ValueError("Saved AR2 check schema or runtime differs")
        _close(
            list(a["maximum_absolute_differences"].values()),
            list(b["maximum_absolute_differences"].values()),
            "saved AR2 checks",
        )


def run_controls(
    source_run,
    archive,
    engine,
    output,
    declaration,
    primary,
    *,
    rscript="Rscript",
    trees=None,
    seeds=None,
    max_refits=None,
    resume=False,
    prepare_only=False,
):
    validate_config(declaration, declaration=True)
    source, reference = _inputs(source_run, archive, engine, primary, rscript)
    config = {
        **declaration,
        "trees": trees if trees is not None else declaration["trees"],
        "seeds": seeds if seeds is not None else declaration["seeds"],
    }
    validate_config(config)
    provenance = _provenance(source_run, engine, declaration, config, max_refits)
    if output.exists():
        if not resume:
            raise FileExistsError("Choose a fresh plain-control run or use --resume")
        manifest = json.loads((output / "manifest.json").read_text())
        validate_provenance(manifest, provenance)
    else:
        output.mkdir(parents=True)
        jobs = jobs_for(source, config, output, max_refits)
        manifest = {
            **provenance,
            "jobs": jobs,
            "completed": False,
            "full_declared_comparison": config == declaration and len(jobs) == 36,
        }
        _write_json(output / "manifest.json", manifest)
    checks = verify_inputs(manifest, source, output, rscript)
    linear_path = output / "linear_checks.json"
    if linear_path.exists():
        _verify_linear_checks(json.loads(linear_path.read_text()), checks)
    else:
        _write_json(linear_path, checks)
    if prepare_only:
        return {
            "status": "plain_controls_prepared_no_forests_or_scores",
            "jobs": len(manifest["jobs"]),
        }
    for job in manifest["jobs"]:
        if Path(job["tree_path"]).exists() and Path(job["prediction_path"]).exists():
            check_job(job, config)
            continue
        started = time.monotonic()
        frame = pd.read_csv(job["matrix"], float_precision="round_trip")
        payload, predictions = fit_payload(frame, job["ntrain"], job["model"], job["seed"], config)
        destination = Path(job["tree_path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        _write_json(destination, payload)
        path = Path(job["prediction_path"])
        temporary = path.with_suffix(".csv.tmp")
        predictions.to_csv(temporary, index=False, float_format="%.17g")
        temporary.replace(path)
        check_job(job, config)
        print(
            f"Finished {job['model']} {job['fit_end']} seed {job['seed']} "
            f"in {time.monotonic() - started:.1f}s",
            flush=True,
        )
    result, forecasts = collect_outputs(manifest, reference)
    forecasts.to_csv(output / "predictions.csv", index=False, float_format="%.17g")
    if result["metrics"]:
        pd.DataFrame(result["metrics"]).to_csv(
            output / "metrics.csv", index=False, float_format="%.17g"
        )
    _write_json(output / "result.json", result)
    manifest.update(completed=True, status=result["status"])
    _write_json(output / "manifest.json", manifest)
    return result


def audit_controls(
    run, archive, engine, declaration, primary, *, rscript="Rscript", allow_partial=False
):
    validate_config(declaration, declaration=True)
    manifest = json.loads((run / "manifest.json").read_text())
    source_run = Path(manifest["source_run"])
    source, reference = _inputs(source_run, archive, engine, primary, rscript)
    expected = _provenance(
        source_run, engine, declaration, manifest["config"], manifest["max_refits"]
    )
    validate_provenance(manifest, expected)
    linear = verify_inputs(manifest, source, run, rscript)
    stored = json.loads((run / "linear_checks.json").read_text())
    _verify_linear_checks(stored, linear)
    pending, checks = [], []
    for job in manifest["jobs"]:
        if not Path(job["tree_path"]).exists() or not Path(job["prediction_path"]).exists():
            pending.append({k: job[k] for k in ("fit_end", "seed", "model")})
        else:
            _, check = check_job(job, manifest["config"], refit=True)
            checks.append(check)
    complete = not pending and manifest["completed"]
    full = complete and manifest["full_declared_comparison"] and manifest["config"] == declaration
    if not full and not allow_partial:
        raise ValueError("Plain-control comparison is incomplete or not its full declaration")
    if not manifest["full_declared_comparison"] and (run / "metrics.csv").exists():
        raise ValueError("A reduced pilot must not publish a metrics file")
    result = None
    if complete:
        result, forecasts = collect_outputs(manifest, reference)
        if json.loads((run / "result.json").read_text()) != result:
            raise ValueError("Saved plain-control result differs")
        saved = pd.read_csv(run / "predictions.csv", float_precision="round_trip")
        keys = ["model", "target_date"]
        a, b = (f.sort_values(keys).set_index(keys) for f in (saved, forecasts))
        if (
            saved.duplicated(keys).any()
            or list(saved) != list(forecasts)
            or not a.index.equals(b.index)
        ):
            raise ValueError("Saved plain-control forecast grid differs")
        if not a.origin_date.equals(b.origin_date):
            raise ValueError("Saved plain-control origins differ")
        _close(a[["actual", "prediction"]], b[["actual", "prediction"]], "saved control forecasts")
        if full:
            verify_aggregates(run, forecasts)
    return {
        "status": "full_plain_control_artifacts_verified"
        if full
        else "partial_plain_control_integrity_only",
        "primary_artifact_audit_repeated": True,
        "manifest_sha256": _sha(run / "manifest.json"),
        "runner_source_sha256": expected["runner_source_sha256"],
        "dependencies_sha256": expected["dependencies_sha256"],
        "backend": _backend(),
        "jobs_verified": len(checks),
        "pending_jobs": pending,
        "output_checks": checks,
        "linear_checks": linear,
        "partial_scores_suppressed": not full,
        "metrics": result["metrics"] if full else [],
        "published_ratio_comparisons": result["published_ratio_comparisons"] if full else [],
        "all_individual_control_seeds_within_tolerance": result[
            "all_individual_control_seeds_within_tolerance"
        ]
        if full
        else None,
        "FA_ARRF_replication_established": False,
        "exact_author_pipeline_verified": False,
        "primary_result_replaced": False,
    }
