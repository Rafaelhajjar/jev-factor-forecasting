"""Qualified MRF on the pinned September vintage and frozen plain-RF calendar.

All old reconstruction code and outputs remain unchanged. This module binds a
completed RF source without treating its failed source-cell diagnostic as a pass.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from threadpoolctl import threadpool_limits

from jev_factor.quarterly import PastRepresentation
from jev_factor.replication import LINEAR_X, _run_job, ensure_engine, linear_prediction, score_table
from jev_factor.replication_audit import _close, _dcf, _r_linear, check_engine_output
from jev_factor.rf2018 import checked_manifest, write_json
from jev_factor.vintage2018 import load_vintage, prepare_window, sha

CORE = [
    "mrf2018.py",
    "vintage2018.py",
    "rf2018.py",
    "quarterly.py",
    "data.py",
    "replication.py",
    "replication_audit.py",
    "reference_mrf.R",
    "reference_linear.R",
    "mrf2018_report.py",
]
FOREST = {
    "block": 8,
    "RWR": 0.75,
    "ridge_lambda": 0.1,
    "MLF": 1,
    "mtry": 1 / 3,
    "minsize": 10,
    "trend_push": 1,
    "prior": "OLS",
    "standardization": "train_only",
}


def code_hashes():
    return {name: sha(Path(__file__).with_name(name)) for name in CORE}


def validate_config(c):
    wanted = {
        "qualified_advance_authorized": True,
        "plain_RF_gate_passed": False,
        "vintage": "2018-09",
        "target": "delta_log_UNRATE",
        "horizon": 1,
        "panel_start": "1959Q3",
        "first_training_target": "1961Q3",
        "evaluation_start": "2003Q1",
        "evaluation_end": "2014Q4",
        "refit_every_quarters": 8,
        "trees": 100,
        "seeds": [101, 202, 303],
        "forest": FOREST,
        "reported_FA_AR_ratio": 0.83,
        "reported_FA_ARRF_ratio": 0.72,
        "absolute_ratio_tolerance": 0.03,
        "gate": "matching_FA_AR_and_all_three_MRF_seeds_no_ensemble_rescue",
        "preprocessing": {
            "completion_rank": 5,
            "outlier_iqr": 10,
            "fit_through": "last_training_origin",
            "factor_features_in_plain_RF": False,
        },
    }
    if any(c.get(k) != v for k, v in wanted.items()):
        raise ValueError("Only the declared, qualified September MRF construction is supported")


def rf_binding(source: Path):
    m = checked_manifest(source)
    a = json.loads((source / "audit.json").read_text())
    if (
        m["status"] != "completed_and_audited"
        or not m["completed"]
        or a["jobs_verified"] != 36
        or a["dates_per_method"] != 48
        or a["plain_RF_approximate_source_cell_gate"] is not False
        or sha(source / "predictions.csv") != a["prediction_sha256"]
        or sha(source / "metrics.csv") != a["metrics_sha256"]
    ):
        raise ValueError("Require the complete audited RF source, retaining its failed gate")
    return {
        "source": str(source.resolve()),
        "manifest_sha256": sha(source / "manifest.json"),
        "audit_sha256": sha(source / "audit.json"),
        "predictions_sha256": sha(source / "predictions.csv"),
        "data": m["data"],
        "plain_RF_gate_passed": False,
        "qualified_advance_authorized_not_a_claim_of_reproduced_RF": True,
    }


@threadpool_limits.wrap(limits=1)
def rich_design(data, fit_end, through, config):
    """Same raw preparation as RF; add the small equation and rich MRF state."""
    raw, ar, rfmeta = prepare_window(data, fit_end, through, config)
    panel = data.panel.loc[config["panel_start"] : through - 1]
    rep = PastRepresentation(5, 10).fit(panel.loc[: fit_end - 1])
    z, factors = rep.transform(panel)
    full_index = data.target.loc[config["panel_start"] : through].index
    cols = {f"y_lag{k}": data.target.shift(k).reindex(raw.index) for k in range(1, 9)}
    for name in factors:
        for lag in range(1, 9):
            cols[f"{name}_lag{lag}"] = (
                factors[name].reindex(full_index).shift(lag).reindex(raw.index)
            )
    n = rfmeta["ntrain"]
    maximum, maf_loadings = 0.0, []
    for j, name in enumerate(z):
        lagged = raw[[f"raw_{j:03d}_lag{k}" for k in range(8)]]
        # Explicit value/date comparison, not only agreement of column names.
        for lag in range(8):
            expected = z[name].reindex(full_index).shift(lag + 1).reindex(raw.index)
            maximum = max(maximum, _close(lagged.iloc[:, lag], expected, "RF raw lag pairing"))
        for lag in [1, 2]:
            cols[f"series_{j:03d}_lag{lag}"] = lagged.iloc[:, lag - 1]
        maf = PCA(n_components=2, svd_solver="full").fit(lagged.iloc[:n].to_numpy())
        scores = maf.transform(lagged.to_numpy())
        maf_loadings.append(maf.components_.tolist())
        for k in range(2):
            cols[f"MAF_{j:03d}_{k + 1}"] = pd.Series(scores[:, k], index=raw.index)
    # Match the established order: target, target lags, factor lags, raw lags, MAFs, trend.
    ordered = (
        [f"y_lag{k}" for k in range(1, 9)]
        + [f"F{j}_lag{k}" for j in range(1, 6) for k in range(1, 9)]
        + [f"series_{j:03d}_lag{k}" for j in range(len(z.columns)) for k in [1, 2]]
        + [f"MAF_{j:03d}_{k}" for j in range(len(z.columns)) for k in [1, 2]]
    )
    frame = pd.DataFrame(cols, index=raw.index)[ordered]
    frame["trend"] = pd.Series(np.arange(len(full_index), dtype=float), index=full_index).reindex(
        raw.index
    )
    frame.insert(0, "target", raw.target)
    for k in range(4):
        _close(frame[f"y_lag{k + 1}"], ar[f"ar_lag{k}"], "RF/MRF AR term alignment")
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Nonfinite rich-state matrix")
    std = frame.iloc[:n].std(ddof=1)
    dropped = [c for c in frame if c != "target" and std[c] <= 1e-10]
    if set(dropped) & set(LINEAR_X):
        raise ValueError("Constant required equation term")
    frame = frame.drop(columns=dropped)
    metadata = {
        **rfmeta,
        "state_columns": len(frame.columns) - 1,
        "constant_state_columns_dropped": dropped,
        "maximum_RF_raw_pairing_error": maximum,
        "cross_sectional_PCA_loadings": rep.pca.components_.tolist(),
        "MAF_loadings": maf_loadings,
        "MAF_fit_rows": n,
    }
    return frame, raw, ar, metadata


def settings_for(config, ntrain, seed, trees):
    return {
        "ntrain": ntrain,
        "xnames": ",".join(LINEAR_X),
        "trees": trees,
        **config["forest"],
        "seed": seed,
    }


def prepare(config_path, archive, source_rf, engine, output, *, pilot=False):
    c = json.loads(config_path.read_text())
    validate_config(c)
    binding = rf_binding(source_rf)
    data = load_vintage(archive)
    if data.metadata != binding["data"]:
        raise ValueError("RF and MRF use different archived data")
    engine_meta = ensure_engine(engine)
    rf = checked_manifest(source_rf)
    for key in [
        "horizon",
        "panel_start",
        "first_training_target",
        "evaluation_start",
        "evaluation_end",
        "refit_every_quarters",
        "preprocessing",
    ]:
        if c[key] != rf["config"][key]:
            raise ValueError(f"RF/MRF preparation differs: {key}")
    output.mkdir(parents=True, exist_ok=False)
    dates = pd.period_range(c["evaluation_start"], c["evaluation_end"], freq="Q")
    starts = [0] if pilot else list(range(0, 48, 8))
    seeds, trees = ([101], 2) if pilot else (c["seeds"], c["trees"])
    windows, jobs, baselines = [], [], []
    for group, start in enumerate(starts):
        targets = dates[start : start + 8]
        end = targets[0] - 1
        frame, raw, _, metadata = rich_design(data, end, targets[-1], c)
        n = metadata["ntrain"]
        source_window = rf["windows"][group]
        raw_saved = pd.read_csv(source_window["paths"]["raw"], float_precision="round_trip")
        raw_masked = raw.copy()
        raw_masked.loc[targets, "target"] = raw.target.iloc[:n].mean()
        if list(raw_masked) != list(raw_saved):
            raise ValueError("RF source feature order differs")
        _close(raw_masked, raw_saved, "frozen RF preparation")
        folder = output / f"refit_{group:02d}_{end}"
        folder.mkdir()
        alignment = pd.read_csv(source_window["paths"]["alignment"], float_precision="round_trip")
        if list(alignment.target_date) != list(frame.index.astype(str)):
            raise ValueError("RF/MRF target rows differ")
        train, test = frame.iloc[:n], frame.iloc[n:]
        for model, names in [
            ("AR4", [f"y_lag{k}" for k in range(1, 5)]),
            (
                "FA_AR",
                [f"y_lag{k}" for k in range(1, 5)]
                + [f"F{j}_lag{k}" for j in [1, 2] for k in [1, 2]],
            ),
        ]:
            pred = linear_prediction(train, test, names)
            baselines.extend(
                {
                    "model": model,
                    "target_date": str(d),
                    "origin_date": str(d - 1),
                    "actual": float(data.target[d]),
                    "prediction": float(p),
                }
                for d, p in zip(targets, pred, strict=True)
            )
        masked = frame.copy()
        masked.loc[targets, "target"] = train.target.mean()
        matrix = folder / "masked_matrix.csv"
        masked.to_csv(matrix, index=False, float_format="%.17g")
        align_path = folder / "alignment.csv"
        alignment.to_csv(align_path, index=False, float_format="%.17g")
        windows.append(
            {
                "group": group,
                "fit_end": str(end),
                "metadata": metadata,
                "matrix": str(matrix.resolve()),
                "matrix_sha256": sha(matrix),
                "alignment": str(align_path.resolve()),
                "alignment_sha256": sha(align_path),
                "RF_raw_matrix_sha256": source_window["hashes"]["raw"],
            }
        )
        for seed in seeds:
            settings = settings_for(c, n, seed, trees)
            settings_path = folder / f"seed_{seed}.dcf"
            settings_path.write_text("\n".join(f"{k}: {v}" for k, v in settings.items()) + "\n")
            jobs.append(
                {
                    "group": group,
                    "seed": seed,
                    "fit_end": str(end),
                    "matrix": str(matrix.resolve()),
                    "matrix_sha256": sha(matrix),
                    "settings": str(settings_path.resolve()),
                    "settings_sha256": sha(settings_path),
                    "prediction_path": str((folder / f"seed_{seed}.csv").resolve()),
                    "targets": [
                        {
                            "target_date": str(d),
                            "origin_date": str(d - 1),
                            "actual": float(data.target[d]),
                        }
                        for d in targets
                    ],
                }
            )
        print(
            f"Prepared {end}: {n} training rows, {metadata['state_columns']} state columns",
            flush=True,
        )
    baseline = pd.DataFrame(baselines)
    baseline.to_csv(output / "baseline_predictions.csv", index=False, float_format="%.17g")
    manifest = {
        "status": "prepared_no_MRF_forecasts",
        "completed": False,
        "pilot": pilot,
        "config": c,
        "config_path": str(config_path.resolve()),
        "config_sha256": sha(config_path),
        "actual_trees": trees,
        "actual_seeds": seeds,
        "archive": str(archive.resolve()),
        "data": data.metadata,
        "RF_source": binding,
        "engine_path": str(engine.resolve()),
        "engine": engine_meta,
        "code": code_hashes(),
        "windows": windows,
        "jobs": jobs,
        "baseline_sha256": sha(output / "baseline_predictions.csv"),
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def checked(output):
    m = json.loads((output / "manifest.json").read_text())
    validate_config(m["config"])
    if m["code"] != code_hashes() or sha(Path(m["config_path"])) != m["config_sha256"]:
        raise ValueError("Declared source or config bytes changed")
    if m["RF_source"] != rf_binding(Path(m["RF_source"]["source"])):
        raise ValueError("RF source provenance changed")
    if ensure_engine(Path(m["engine_path"])) != m["engine"]:
        raise ValueError("Native engine provenance changed")
    if load_vintage(Path(m["archive"])).metadata != m["data"]:
        raise ValueError("Vintage data changed")
    seeds, trees, groups = ([101], 2, range(1)) if m["pilot"] else ([101, 202, 303], 100, range(6))
    if m["actual_trees"] != trees or m["actual_seeds"] != seeds:
        raise ValueError("Pilot/full settings differ from declaration")
    keys = [(j["group"], j["seed"]) for j in m["jobs"]]
    expected = {(g, s) for g in groups for s in seeds}
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError("Missing or duplicate declared MRF job")
    if [w["group"] for w in m["windows"]] != list(groups):
        raise ValueError("Refit windows differ")
    if sha(output / "baseline_predictions.csv") != m["baseline_sha256"]:
        raise ValueError("Baseline predictions changed")
    for w in m["windows"]:
        for key in ["matrix", "alignment"]:
            if sha(Path(w[key])) != w[key + "_sha256"]:
                raise ValueError("Prepared input bytes changed")
    for job in m["jobs"]:
        w = m["windows"][job["group"]]
        if (
            job["matrix"] != w["matrix"]
            or job["matrix_sha256"] != w["matrix_sha256"]
            or job["fit_end"] != w["fit_end"]
            or sha(Path(job["settings"])) != job["settings_sha256"]
        ):
            raise ValueError("MRF job input binding differs")
        expected_settings = {
            k: str(v)
            for k, v in settings_for(
                m["config"], w["metadata"]["ntrain"], job["seed"], trees
            ).items()
        }
        if _dcf(Path(job["settings"])) != expected_settings:
            raise ValueError("Actual MRF settings differ from declared invocation")
    return m


def run(output, library, workers=6):
    if not 1 <= workers <= 8:
        raise ValueError("Use one through eight workers")
    m = checked(output)
    m["status"] = "running"
    write_json(output / "manifest.json", m)
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for job in m["jobs"]:
                if job.get("completed"):
                    for suffix, digest in job["output_hashes"].items():
                        if sha(Path(job["prediction_path"] + suffix)) != digest:
                            raise ValueError("Completed MRF output changed")
                    continue
                future = pool.submit(
                    _run_job,
                    job,
                    Path(m["engine_path"]),
                    "Rscript",
                    library,
                    Path(__file__).with_name("reference_mrf.R"),
                )
                futures[future] = job
            for future in as_completed(futures):
                job = futures[future]
                job["execution"] = future.result()
                job["completed"] = True
                job["output_hashes"] = {
                    suffix: sha(Path(job["prediction_path"] + suffix))
                    for suffix in ["", ".runtime.dcf"]
                }
                write_json(output / "manifest.json", m)
    except Exception as exc:
        m.update(status="failed", error=str(exc))
        write_json(output / "manifest.json", m)
        raise
    m.update(completed=True, status="completed_pending_audit")
    write_json(output / "manifest.json", m)


def audit(output, *, allow_partial=False):
    """Rebuild inputs and verify actual native outputs; do not refit every tree."""
    m = checked(output)
    c = m["config"]
    data = load_vintage(Path(m["archive"]))
    baseline = pd.read_csv(output / "baseline_predictions.csv", float_precision="round_trip")
    rf_source = Path(m["RF_source"]["source"])
    rf_predictions = pd.read_csv(rf_source / "predictions.csv", float_precision="round_trip")
    rf_manifest = checked_manifest(rf_source)
    frames, window_checks, completed, pending, runtimes = [baseline], [], [], [], []
    max_coefficient_error = 0.0
    for w in m["windows"]:
        end = pd.Period(w["fit_end"], freq="Q")
        dates = pd.period_range(end + 1, periods=8, freq="Q")
        rebuilt, raw, _, metadata = rich_design(data, end, dates[-1], c)
        if metadata != w["metadata"]:
            raise ValueError("Rebuilt representation metadata differs")
        n = metadata["ntrain"]
        rebuilt.loc[dates, "target"] = rebuilt.target.iloc[:n].mean()
        saved = pd.read_csv(w["matrix"], float_precision="round_trip")
        if list(saved) != list(rebuilt) or saved.shape != rebuilt.shape:
            raise ValueError("Rebuilt MRF state schema differs")
        matrix_error = _close(saved, rebuilt, "rebuilt September MRF state")
        raw.loc[dates, "target"] = raw.target.iloc[:n].mean()
        rf_window = rf_manifest["windows"][w["group"]]
        old_raw = pd.read_csv(rf_window["paths"]["raw"], float_precision="round_trip")
        raw_error = _close(raw, old_raw, "RF source raw preparation")
        alignment = pd.read_csv(w["alignment"], float_precision="round_trip")
        if (
            list(alignment.target_date) != list(rebuilt.index.astype(str))
            or list(alignment.origin_date) != list((rebuilt.index - 1).astype(str))
            or list(alignment.role) != ["train"] * n + ["forecast"] * 8
        ):
            raise ValueError("MRF origin/target alignment differs")
        _close(alignment.actual, data.target.reindex(rebuilt.index), "alignment outcomes")
        for lag in range(1, 9):
            _close(
                saved[f"y_lag{lag}"],
                data.target.shift(lag).reindex(rebuilt.index),
                f"independent target lag {lag}",
            )
        errors = {}
        with TemporaryDirectory(prefix="september-linear-audit-") as scratch:
            qr, version = _r_linear(Path(w["matrix"]), n, "Rscript", Path(scratch))
        for model in ["AR4", "FA_AR"]:
            expected = baseline.loc[baseline.model.eq(model)].set_index("target_date")
            errors[model] = _close(
                qr[model],
                expected.reindex(dates.astype(str)).prediction,
                f"independent R QR {model}",
            )
            _close(
                expected.reindex(dates.astype(str)).actual,
                data.target.reindex(dates),
                "baseline outcomes",
            )
        reference_ar = rf_predictions.loc[rf_predictions.model.eq("AR4")].set_index("target_date")
        _close(qr.AR4, reference_ar.reindex(dates.astype(str)).prediction, "same RF/MRF AR4")
        window_checks.append(
            {
                "fit_end": str(end),
                "ntrain": n,
                "state_columns": metadata["state_columns"],
                "matrix_rebuild_max_error": matrix_error,
                "RF_raw_pairing_max_error": raw_error,
                "independent_R_QR_errors": errors,
                "R_version": version,
            }
        )
        for job in [j for j in m["jobs"] if j["group"] == w["group"]]:
            if [r["target_date"] for r in job["targets"]] != list(dates.astype(str)):
                raise ValueError("Forecast target grid differs")
            if [r["origin_date"] for r in job["targets"]] != list((dates - 1).astype(str)):
                raise ValueError("Forecast origin grid differs")
            _close([r["actual"] for r in job["targets"]], data.target.reindex(dates), "job targets")
            if not job.get("completed"):
                pending.append({"group": job["group"], "seed": job["seed"]})
                continue
            for suffix, digest in job["output_hashes"].items():
                if sha(Path(job["prediction_path"] + suffix)) != digest:
                    raise ValueError("Native completed output checksum differs")
            prediction = pd.read_csv(job["prediction_path"], float_precision="round_trip")
            max_coefficient_error = max(
                max_coefficient_error, check_engine_output(prediction, saved.iloc[n:])
            )
            runtime = _dcf(Path(job["prediction_path"] + ".runtime.dcf"))
            if runtime["standardization"] != "train_only" or runtime["prior"] != "OLS":
                raise ValueError("Native runtime differs from declaration")
            runtimes.append(runtime)
            frames.append(
                pd.DataFrame(
                    [
                        {**rec, "model": f"FA_ARRF_seed{job['seed']}", "prediction": float(p)}
                        for rec, p in zip(job["targets"], prediction.prediction, strict=True)
                    ]
                )
            )
            completed.append(
                {
                    "group": job["group"],
                    "seed": job["seed"],
                    "prediction_sha256": sha(Path(job["prediction_path"])),
                }
            )
    full = (
        not m["pilot"]
        and m["completed"]
        and not pending
        and len(completed) == 18
        and m["actual_trees"] == c["trees"] == 100
        and m["actual_seeds"] == c["seeds"] == [101, 202, 303]
        and len(m["windows"]) == 6
    )
    if not full and not allow_partial:
        raise ValueError("Full audit needs every declared seed, all six windows and 100 trees")
    result = {
        "status": "full_qualified_MRF_artifacts_verified" if full else "partial_integrity_only",
        "full_declaration_verified": full,
        "qualified_advance_authorized": True,
        "plain_RF_gate_passed": False,
        "exact_author_pipeline_verified": False,
        "jobs_expected": len(m["jobs"]),
        "jobs_verified": len(completed),
        "pending_jobs": pending,
        "actual_trees": m["actual_trees"],
        "data": m["data"],
        "config": c,
        "code": m["code"],
        "RF_source": {k: v for k, v in m["RF_source"].items() if k != "source"},
        "external_engine": m["engine"],
        "input_and_linear_checks": window_checks,
        "maximum_coefficient_decomposition_error": max_coefficient_error,
        "runtime_records": runtimes,
        "completed_output_checksums": completed,
        "partial_scores_suppressed": not full,
        "metrics": [],
        "source_cell_checks": [],
        "joint_source_cell_diagnostic": None,
        "original_results_replaced": False,
        "full_native_tree_refits_claimed": False,
    }
    if full:
        versions = {(r["R_version"], r["pracma_version"]) for r in runtimes}
        if len(versions) != 1:
            raise ValueError("Native runtime changed within the experiment")
        forecasts = pd.concat(frames, ignore_index=True).sort_values(["model", "target_date"])
        metrics = score_table(forecasts)
        comparisons = []
        for row in metrics.to_dict(orient="records"):
            if row["model"] == "AR4":
                continue
            source = (
                c["reported_FA_AR_ratio"]
                if row["model"] == "FA_AR"
                else c["reported_FA_ARRF_ratio"]
            )
            comparisons.append(
                {
                    "model": row["model"],
                    "source_ratio": source,
                    "ratio": row["RMSE_over_AR4"],
                    "within_tolerance": abs(row["RMSE_over_AR4"] - source)
                    <= c["absolute_ratio_tolerance"],
                }
            )
        by_model = metrics.set_index("model")
        gains = {
            str(s): 1
            - float(by_model.loc[f"FA_ARRF_seed{s}", "RMSE"]) / float(by_model.loc["FA_AR", "RMSE"])
            for s in c["seeds"]
        }
        forecasts.to_csv(output / "predictions.csv", index=False, float_format="%.17g")
        metrics.to_csv(output / "metrics.csv", index=False, float_format="%.17g")
        result.update(
            metrics=metrics.to_dict(orient="records"),
            source_cell_checks=comparisons,
            joint_source_cell_diagnostic=all(r["within_tolerance"] for r in comparisons),
            RMSE_reduction_vs_matching_FA_AR=gains,
            prediction_sha256=sha(output / "predictions.csv"),
            metrics_sha256=sha(output / "metrics.csv"),
        )
    write_json(output / "audit.json", result)
    if m["completed"]:
        m["status"] = "completed_and_audited" if full else "pilot_completed_integrity_verified"
        write_json(output / "manifest.json", m)
    return result
