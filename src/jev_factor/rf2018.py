"""Declared September 2018 raw-indicator RF run and reproducibility checks."""

from __future__ import annotations

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

from jev_factor.replication import linear_prediction, score_table
from jev_factor.vintage2018 import download_vintage, load_vintage, prepare_window, sha

CORE = [
    "vintage2018.py",
    "rf2018.py",
    "reference_ranger.R",
    "quarterly.py",
    "data.py",
    "replication.py",
]


def validate_config(c):
    expected = {
        "vintage": "2018-09",
        "target": "delta_log_UNRATE",
        "horizon": 1,
        "panel_start": "1959Q3",
        "first_training_target": "1961Q3",
        "evaluation_start": "2003Q1",
        "evaluation_end": "2014Q4",
        "refit_every_quarters": 8,
        "trees": 500,
        "min_node_size": 3,
        "seeds": [101, 202, 303],
        "primary": "ranger_defaults",
        "reported_plain_RF_ratio": 1.0,
        "absolute_ratio_tolerance": 0.03,
        "preprocessing": {
            "completion_rank": 5,
            "outlier_iqr": 10,
            "fit_through": "last_training_origin",
            "factor_features_in_plain_RF": False,
        },
        "variants": {
            "ranger_defaults": {
                "mtry": "floor_sqrt_p",
                "replace": True,
                "sample_fraction": 1.0,
            },
            "appendix_style": {
                "mtry": "floor_p_over_3",
                "replace": False,
                "sample_fraction": 0.75,
            },
        },
        "gate": "all_three_primary_seeds_within_tolerance_secondary_cannot_rescue",
    }
    if any(c.get(k) != v for k, v in expected.items()):
        raise ValueError("Only the fixed, declared September 2018 RF study is supported")


def source_hashes():
    root = Path(__file__).parent
    return {name: sha(root / name) for name in CORE}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def prepare(config_path: Path, archive: Path, output: Path):
    c = json.loads(config_path.read_text())
    validate_config(c)
    download_vintage(archive)
    data = load_vintage(archive)
    output.mkdir(parents=True, exist_ok=False)
    dates = pd.period_range(c["evaluation_start"], c["evaluation_end"], freq="Q")
    windows, jobs = [], []
    for group, start in enumerate(range(0, len(dates), c["refit_every_quarters"])):
        targets = dates[start : start + c["refit_every_quarters"]]
        end = targets[0] - 1
        raw, ar, metadata = prepare_window(data, end, targets[-1], c)
        test = raw.index.isin(targets)
        n = int((~test).sum())
        if n != metadata["ntrain"] or not raw.index[test].equals(targets):
            raise ValueError("Unexpected training or forecast dates")
        folder = output / f"refit_{group:02d}_{end}"
        folder.mkdir()
        alignment = pd.DataFrame(
            {
                "target_date": raw.index.astype(str),
                "origin_date": (raw.index - c["horizon"]).astype(str),
                "oldest_raw_date": (raw.index - c["horizon"] - 7).astype(str),
                "role": np.where(test, "forecast", "train"),
                "actual": raw.target.to_numpy(),
            }
        )
        raw.loc[targets, "target"] = raw.target.iloc[:n].mean()
        ar.loc[targets, "target"] = ar.target.iloc[:n].mean()
        paths = {
            key: folder / name
            for key, name in [
                ("raw", "rf_matrix.csv"),
                ("ar", "ar_matrix.csv"),
                ("alignment", "alignment.csv"),
            ]
        }
        for key, frame in [("raw", raw), ("ar", ar), ("alignment", alignment)]:
            frame.to_csv(paths[key], index=False, float_format="%.17g")
        windows.append(
            {
                "group": group,
                **metadata,
                "paths": {key: str(path.resolve()) for key, path in paths.items()},
                "hashes": {key: sha(path) for key, path in paths.items()},
            }
        )
        p = raw.shape[1] - 1
        for variant, v in c["variants"].items():
            for seed in c["seeds"]:
                settings = {
                    "ntrain": n,
                    "trees": c["trees"],
                    "min_node_size": c["min_node_size"],
                    "seed": seed,
                    "mtry": int(np.sqrt(p)) if v["mtry"] == "floor_sqrt_p" else p // 3,
                    "replace": str(v["replace"]).upper(),
                    "sample_fraction": v["sample_fraction"],
                }
                settings_path = folder / f"{variant}_{seed}.dcf"
                settings_path.write_text("\n".join(f"{k}: {v}" for k, v in settings.items()) + "\n")
                jobs.append(
                    {
                        "group": group,
                        "variant": variant,
                        "seed": seed,
                        "settings": str(settings_path.resolve()),
                        "settings_sha256": sha(settings_path),
                        "prediction": str((folder / f"{variant}_{seed}.csv").resolve()),
                    }
                )
        print(f"Prepared {end}: {n} training rows, {p} raw-indicator features", flush=True)
    manifest = {
        "status": "prepared_no_forecast_losses",
        "config": c,
        "config_path": str(config_path.resolve()),
        "config_sha256": sha(config_path),
        "archive": str(archive.resolve()),
        "data": data.metadata,
        "code": source_hashes(),
        "windows": windows,
        "jobs": jobs,
        "completed": False,
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def checked_manifest(output):
    m = json.loads((output / "manifest.json").read_text())
    validate_config(m["config"])
    if source_hashes() != m["code"] or sha(Path(m["config_path"])) != m["config_sha256"]:
        raise ValueError("Declared code/config changed")
    expected_jobs = {
        (g, v, s) for g in range(6) for v in m["config"]["variants"] for s in m["config"]["seeds"]
    }
    actual = [(j["group"], j["variant"], j["seed"]) for j in m["jobs"]]
    if len(actual) != len(expected_jobs) or set(actual) != expected_jobs:
        raise ValueError("Incomplete or duplicate job grid")
    if [w["group"] for w in m["windows"]] != list(range(6)):
        raise ValueError("Invalid refit grid")
    for w in m["windows"]:
        if {k: sha(Path(p)) for k, p in w["paths"].items()} != w["hashes"]:
            raise ValueError("Prepared matrix/alignment changed")
    for j in m["jobs"]:
        if sha(Path(j["settings"])) != j["settings_sha256"]:
            raise ValueError("Prepared settings changed")
    return m


def run_job(j, w, library, mode):
    adapter = Path(__file__).with_name("reference_ranger.R")
    result = subprocess.run(
        [
            "Rscript",
            "--vanilla",
            str(adapter),
            w["paths"]["raw"],
            w["paths"]["ar"],
            j["settings"],
            j["prediction"],
            str(library.resolve()),
            mode,
        ],
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
        },
    )
    Path(j["prediction"] + f".{mode}.stdout").write_text(result.stdout)
    Path(j["prediction"] + f".{mode}.stderr").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f"{mode} failed for {j}: {result.stderr[-2000:]}")
    return result.stdout.strip()


def run(output: Path, library: Path, workers=2):
    m = checked_manifest(output)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for j in m["jobs"]:
            # Resume only outputs with a previously saved success marker/hash.
            if j.get("completed"):
                for suffix, digest in j["output_hashes"].items():
                    if sha(Path(j["prediction"] + suffix)) != digest:
                        raise ValueError("Completed output changed")
                continue
            futures[pool.submit(run_job, j, m["windows"][j["group"]], library, "fit")] = j
        for future in as_completed(futures):
            j = futures[future]
            print(future.result(), j["group"], j["variant"], j["seed"], flush=True)
            j["completed"] = True
            j["output_hashes"] = {
                s: sha(Path(j["prediction"] + s)) for s in ["", ".rds", ".fit.dcf"]
            }
            m["status"] = "fitting"
            write_json(output / "manifest.json", m)
    m["completed"] = all(j.get("completed") for j in m["jobs"])
    m["status"] = "completed_pending_audit"
    write_json(output / "manifest.json", m)


def audit(output: Path, library: Path, workers=2):
    m = checked_manifest(output)
    if not m["completed"] or not all(j.get("completed") for j in m["jobs"]):
        raise ValueError("Full grid required; no reduced pilot performance is reported")
    data = load_vintage(Path(m["archive"]))
    dates = pd.period_range(
        m["config"]["evaluation_start"], m["config"]["evaluation_end"], freq="Q"
    )
    maximum, baseline, rows = 0.0, {}, []
    for w in m["windows"]:
        targets = dates[w["group"] * 8 : (w["group"] + 1) * 8]
        raw, ar, meta = prepare_window(data, targets[0] - 1, targets[-1], m["config"])
        if meta != {k: w[k] for k in meta}:
            raise ValueError("Rebuilt representation metadata differs")
        n = meta["ntrain"]
        for key, frame in [("raw", raw), ("ar", ar)]:
            frame = frame.copy()
            frame.loc[targets, "target"] = frame.target.iloc[:n].mean()
            saved = pd.read_csv(w["paths"][key], float_precision="round_trip")
            if list(frame.columns) != list(saved.columns) or frame.shape != saved.shape:
                raise ValueError("Rebuilt matrix schema differs")
            delta = float(np.max(np.abs(frame.to_numpy() - saved.to_numpy())))
            maximum = max(maximum, delta)
            if delta > 1e-12:
                raise ValueError("Rebuilt inputs differ")
        alignment = pd.read_csv(w["paths"]["alignment"], float_precision="round_trip")
        origins = raw.index - m["config"]["horizon"]
        if (
            list(alignment.target_date) != list(raw.index.astype(str))
            or list(alignment.origin_date) != list(origins.astype(str))
            or list(alignment.oldest_raw_date) != list((origins - 7).astype(str))
            or list(alignment.role) != ["train"] * n + ["forecast"] * 8
            or not np.array_equal(alignment.actual, data.target.reindex(raw.index))
        ):
            raise ValueError("Origin/target alignment differs")
        baseline[w["group"]] = linear_prediction(ar.iloc[:n], ar.iloc[n:], list(ar.columns[1:]))
        rows.extend(
            {
                "target_date": str(d),
                "origin_date": str(d - 1),
                "model": "AR4",
                "actual": float(data.target[d]),
                "prediction": float(p),
            }
            for d, p in zip(targets, baseline[w["group"]], strict=True)
        )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(run_job, j, m["windows"][j["group"]], library, "audit"): j
            for j in m["jobs"]
        }
        for future in as_completed(futures):
            j = futures[future]
            print(future.result(), j["group"], j["variant"], j["seed"], flush=True)
            for suffix, digest in j["output_hashes"].items():
                if sha(Path(j["prediction"] + suffix)) != digest:
                    raise ValueError("Completed output changed")
            p = pd.read_csv(j["prediction"], float_precision="round_trip")
            if p.shape != (8, 2) or not np.isfinite(p.to_numpy()).all():
                raise ValueError("Invalid predictions")
            np.testing.assert_allclose(p.AR4, baseline[j["group"]], rtol=0, atol=1e-12)
            targets = dates[j["group"] * 8 : (j["group"] + 1) * 8]
            rows.extend(
                {
                    "target_date": str(d),
                    "origin_date": str(d - 1),
                    "model": f"RF_{j['variant']}_seed_{j['seed']}",
                    "actual": float(data.target[d]),
                    "prediction": float(v),
                }
                for d, v in zip(targets, p.prediction, strict=True)
            )
    predictions = pd.DataFrame(rows).sort_values(["model", "target_date"]).reset_index(drop=True)
    metrics = score_table(predictions)
    c = m["config"]
    checked = []
    for seed in c["seeds"]:
        name = f"RF_{c['primary']}_seed_{seed}"
        ratio = float(metrics.set_index("model").loc[name, "RMSE_over_AR4"])
        checked.append(
            {
                "seed": seed,
                "ratio": ratio,
                "within_tolerance": abs(ratio - c["reported_plain_RF_ratio"])
                <= c["absolute_ratio_tolerance"],
            }
        )
    predictions.to_csv(output / "predictions.csv", index=False, float_format="%.17g")
    metrics.to_csv(output / "metrics.csv", index=False, float_format="%.17g")
    result = {
        "status": "completed_and_audited_not_exact_original_caller",
        "data": m["data"],
        "code": m["code"],
        "config_sha256": m["config_sha256"],
        "jobs_verified": len(m["jobs"]),
        "trees_verified": len(m["jobs"]) * c["trees"],
        "dates_per_method": len(dates),
        "max_rebuilt_matrix_difference": maximum,
        "R_QR_AR4_matches_independent_numpy": True,
        "all_stored_trees_traversed_and_sampled_leaf_means_checked": True,
        "primary_seed_checks": checked,
        "plain_RF_approximate_source_cell_gate": all(x["within_tolerance"] for x in checked),
        "secondary_cannot_rescue_primary": True,
        "exact_replication_claim": False,
        "MRF_replication_established": False,
        "metrics": metrics.to_dict(orient="records"),
        "prediction_sha256": sha(output / "predictions.csv"),
        "metrics_sha256": sha(output / "metrics.csv"),
    }
    write_json(output / "audit.json", result)
    m["status"] = "completed_and_audited"
    write_json(output / "manifest.json", m)
    return result
