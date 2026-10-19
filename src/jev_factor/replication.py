"""Auditable quarterly reconstruction using the pinned, external author's R engine."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib.resources import files
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from jev_factor.quarterly import download_archive, load_quarterly, make_design

AUTHOR_COMMIT = "bdb2ed435affb741aafdf78bab12c470ec6d55d0"
AUTHOR_SHA256 = "e052c0f12544a2bfb79974c07174b08116b7c80298de5905bdb3753732a7b631"
AUTHOR_URL = f"https://raw.githubusercontent.com/philgoucou/macrorf/{AUTHOR_COMMIT}/R/MRF_v210403.R"
LINEAR_X = ["y_lag1", "y_lag2", "F1_lag1", "F2_lag1"]


def ensure_engine(path: Path) -> dict:
    if path.exists():
        payload = path.read_bytes()
    else:
        response = httpx.get(AUTHOR_URL, timeout=60, follow_redirects=True)
        response.raise_for_status()
        payload = response.content
    if hashlib.sha256(payload).hexdigest() != AUTHOR_SHA256:
        raise ValueError("Author R engine checksum mismatch")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return {
        "commit": AUTHOR_COMMIT,
        "sha256": AUTHOR_SHA256,
        "url": AUTHOR_URL,
        "license": "GPL-3 external dependency; not redistributed as MIT",
    }


def linear_prediction(train: pd.DataFrame, test: pd.DataFrame, columns: list[str]) -> np.ndarray:
    x = np.column_stack([np.ones(len(train)), train[columns]])
    beta = np.linalg.lstsq(x, train.target, rcond=None)[0]
    return np.column_stack([np.ones(len(test)), test[columns]]) @ beta


def score_table(predictions: pd.DataFrame) -> pd.DataFrame:
    needed = {"target_date", "model", "actual", "prediction"}
    if not needed.issubset(predictions.columns):
        raise ValueError("Invalid prediction schema")
    if predictions.duplicated(["target_date", "model"]).any():
        raise ValueError("Duplicate model/target predictions")
    reference = predictions.loc[predictions.model.eq("AR4")]
    expected = set(reference.target_date)
    baseline = np.sqrt(np.mean((reference.actual - reference.prediction) ** 2))
    if not len(reference) or baseline <= 0:
        raise ValueError("Missing/nonpositive AR4 reference RMSE")
    rows = []
    actual_by_date = reference.set_index("target_date").actual
    for model, frame in predictions.groupby("model", sort=False):
        if set(frame.target_date) != expected:
            raise ValueError(f"Unmatched evaluation dates for {model}")
        if not np.isfinite(frame[["actual", "prediction"]].to_numpy()).all():
            raise ValueError("Nonfinite forecast or target")
        if not np.allclose(
            frame.actual, actual_by_date.reindex(frame.target_date), rtol=0, atol=1e-12
        ):
            raise ValueError("Methods must be scored on identical actual outcomes")
        error = frame.actual - frame.prediction
        rmse = float(np.sqrt(np.mean(error**2)))
        rows.append(
            {
                "model": model,
                "n": len(frame),
                "RMSE": rmse,
                "MAE": float(np.mean(np.abs(error))),
                "RMSE_over_AR4": rmse / baseline,
            }
        )
    return pd.DataFrame(rows)


@threadpool_limits.wrap(limits=1)
def prepare_jobs(config: dict, archive: Path, output: Path, max_refits: int | None = None) -> dict:
    """Write masked external-engine inputs before any R predictions are produced."""
    if config["horizon"] != 1:
        raise ValueError("This first reconstruction supports quarterly h=1 only")
    if config["em_rank"] != config["pca_rank"]:
        raise ValueError("This representation currently requires equal EM/PCA ranks")
    if not config["seeds"] or len(set(config["seeds"])) != len(config["seeds"]):
        raise ValueError("Need a nonempty set of unique seeds")
    data = load_quarterly(archive)
    dates = pd.period_range(config["evaluation_start"], config["evaluation_end"], freq="Q")
    interval = config["refit_every_quarters"]
    starts = list(range(0, len(dates), interval))
    if max_refits is not None:
        starts = starts[:max_refits]
    if not starts:
        raise ValueError("No refit groups")
    jobs, baseline_frames, representations = [], [], []
    for group, start in enumerate(starts):
        targets = dates[start : start + interval]
        fit_end = targets[0] - 1
        design, metadata = make_design(
            data,
            fit_end,
            targets[-1],
            panel_start=config["panel_start"],
            rank=config["pca_rank"],
            outlier_iqr=config["outlier_iqr"],
            factor_panel=config["factor_panel"],
        )
        design = design.loc[config["regression_start"] :]
        train, test = design.loc[:fit_end], design.loc[targets]
        if train.target.isna().any() or test.target.isna().any():
            raise ValueError("Missing observed unemployment target")
        std = train.std(ddof=1)
        kept = [c for c in design if c == "target" or std[c] > 1e-10]
        if not set(LINEAR_X).issubset(kept):
            raise ValueError("Constant required linear term")
        metadata["constant_state_columns_dropped"] = sorted(set(design.columns) - set(kept))
        train, test = train[kept], test[kept]
        group_path = output / f"refit_{group:02d}_{fit_end}"
        group_path.mkdir()
        matrix = pd.concat([train, test]).copy()
        matrix.loc[targets, "target"] = train.target.mean()
        matrix_path = group_path / "masked_matrix.csv"
        matrix.to_csv(matrix_path, index=False, float_format="%.17g")
        target_records = [
            {
                "target_date": str(t),
                "origin_date": str(t - 1),
                "actual": float(test.loc[t, "target"]),
            }
            for t in targets
        ]
        x_ar = [f"y_lag{k}" for k in range(1, 5)]
        x_fa = x_ar + [f"F{j}_lag{k}" for j in [1, 2] for k in [1, 2]]
        for model, columns in [("AR4", x_ar), ("FA_AR", x_fa)]:
            predicted = linear_prediction(train, test, columns)
            baseline_frames.extend(
                {**rec, "model": model, "prediction": float(p)}
                for rec, p in zip(target_records, predicted, strict=True)
            )
        for seed in config["seeds"]:
            settings = {
                "ntrain": len(train),
                "xnames": ",".join(LINEAR_X),
                **{
                    k: config[k]
                    for k in [
                        "trees",
                        "block",
                        "RWR",
                        "ridge_lambda",
                        "MLF",
                        "mtry",
                        "minsize",
                        "trend_push",
                        "prior",
                        "standardization",
                    ]
                },
                "seed": seed,
            }
            settings_path = group_path / f"settings_seed_{seed}.dcf"
            settings_path.write_text("\n".join(f"{k}: {v}" for k, v in settings.items()) + "\n")
            jobs.append(
                {
                    "group": group,
                    "seed": seed,
                    "fit_end": str(fit_end),
                    "matrix": str(matrix_path.resolve()),
                    "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
                    "settings": str(settings_path.resolve()),
                    "settings_sha256": hashlib.sha256(settings_path.read_bytes()).hexdigest(),
                    "prediction_path": str((group_path / f"seed_{seed}.csv").resolve()),
                    "targets": target_records,
                }
            )
        metadata.update(
            fit_end=str(fit_end),
            first_training_target=str(train.index[0]),
            last_training_target=str(train.index[-1]),
            ntrain=len(train),
            first_test_target=str(targets[0]),
            last_test_target=str(targets[-1]),
        )
        representations.append(metadata)
        print(
            f"Prepared refit {fit_end}: {len(train)} training rows, {len(test)} forecasts, "
            f"{len(kept) - 1} state columns",
            flush=True,
        )
    pd.DataFrame(baseline_frames).to_csv(output / "baseline_predictions.csv", index=False)
    score_table(pd.DataFrame(baseline_frames)).to_csv(output / "baseline_metrics.csv", index=False)
    manifest = {
        "config": config,
        "data": data.metadata,
        "jobs": jobs,
        "representations": representations,
        "completed": False,
        "status": "prepared_not_yet_run",
        "max_refits": max_refits,
        "full_evaluation": max_refits is None
        or len(starts) == (len(dates) + interval - 1) // interval,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def _run_job(job: dict, engine: Path, rscript: str, r_library: Path, adapter: Path) -> dict:
    if hashlib.sha256(Path(job["matrix"]).read_bytes()).hexdigest() != job["matrix_sha256"]:
        raise ValueError("Prepared input matrix was modified")
    if hashlib.sha256(Path(job["settings"]).read_bytes()).hexdigest() != job["settings_sha256"]:
        raise ValueError("Prepared R settings were modified")
    dest = Path(job["prediction_path"])
    command = [
        rscript,
        "--vanilla",
        str(adapter.resolve()),
        str(engine.resolve()),
        job["matrix"],
        job["settings"],
        str(dest),
        str(r_library.resolve()),
    ]
    env = {
        **os.environ,
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
    }
    started = time.monotonic()
    result = subprocess.run(command, env=env, text=True, capture_output=True, check=False)
    dest.with_suffix(".stdout.log").write_text(result.stdout)
    dest.with_suffix(".stderr.log").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f"Reference R job failed ({dest}): {result.stderr[-3000:]}")
    frame = pd.read_csv(dest)
    if len(frame) != len(job["targets"]) or not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Invalid reference engine output")
    print(
        f"Finished refit {job['fit_end']}, seed {job['seed']} in {time.monotonic() - started:.1f}s",
        flush=True,
    )
    return {
        "group": job["group"],
        "seed": job["seed"],
        "wall_seconds": time.monotonic() - started,
        "engine_returncode": result.returncode,
    }


def _valid_checkpoint(job: dict) -> bool:
    path = Path(job["prediction_path"])
    if not path.exists() or not Path(str(path) + ".runtime.dcf").exists():
        return False
    try:
        frame = pd.read_csv(path)
        return (
            len(frame) == len(job["targets"])
            and set(["prediction", "intercept", *LINEAR_X]).issubset(frame.columns)
            and np.isfinite(frame.to_numpy()).all()
        )
    except (ValueError, OSError):
        return False


def run_reconstruction(
    config: dict,
    archive: Path,
    engine: Path,
    output: Path,
    *,
    rscript: str = "Rscript",
    r_library: Path = Path("runs/r-library"),
    workers: int = 2,
    max_refits: int | None = None,
    prepare_only: bool = False,
    resume: bool = False,
) -> dict:
    engine_meta = ensure_engine(engine)
    download_archive(archive)
    if workers < 1 or workers > 8 or (max_refits is not None and max_refits < 1):
        raise ValueError("workers must be 1–8 and max_refits must be positive")
    if output.exists():
        if not resume:
            raise FileExistsError("Output already exists; choose a fresh directory or use --resume")
        manifest = json.loads((output / "manifest.json").read_text())
        if manifest["config"] != config or manifest["max_refits"] != max_refits:
            raise ValueError("Resume config/refit bounds differ from the saved manifest")
        if manifest.get("external_engine") != engine_meta:
            raise ValueError("Resume external engine provenance differs")
    else:
        output.mkdir(parents=True)
        manifest = prepare_jobs(config, archive, output, max_refits)
    manifest["external_engine"] = engine_meta
    source_hashes = {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ["replication.py", "quarterly.py", "reference_mrf.R"]
    }
    if resume and manifest.get("integration_source_sha256") != source_hashes:
        raise ValueError("Resume integration source differs; use a fresh output directory")
    manifest["integration_source_sha256"] = source_hashes
    adapter = output / "reference_mrf.R"
    if not adapter.exists():
        shutil.copyfile(str(files("jev_factor").joinpath("reference_mrf.R")), adapter)
    if hashlib.sha256(adapter.read_bytes()).hexdigest() != source_hashes["reference_mrf.R"]:
        raise ValueError("Prepared R adapter snapshot differs from its recorded source")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if prepare_only:
        return {"status": manifest["status"], "output": str(output), "jobs": len(manifest["jobs"])}
    for job in manifest["jobs"]:
        for path_key, hash_key in [("matrix", "matrix_sha256"), ("settings", "settings_sha256")]:
            if hashlib.sha256(Path(job[path_key]).read_bytes()).hexdigest() != job[hash_key]:
                raise ValueError("Prepared checkpoint inputs changed")
    pending = [job for job in manifest["jobs"] if not _valid_checkpoint(job)]
    manifest["status"] = "running"
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(_run_job, j, engine, rscript, r_library, adapter) for j in pending
            ]
            for future in as_completed(futures):
                result = future.result()
                with (output / "completed_jobs.jsonl").open("a") as stream:
                    stream.write(json.dumps(result) + "\n")
    except Exception as exc:
        manifest.update(status="failed", error=str(exc))
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        raise
    frames = [pd.read_csv(output / "baseline_predictions.csv")]
    for job in manifest["jobs"]:
        frame = pd.read_csv(job["prediction_path"])
        for rec, (_, row) in zip(job["targets"], frame.iterrows(), strict=True):
            frames.append(
                pd.DataFrame(
                    [{**rec, "model": f"FA_ARRF_seed{job['seed']}", "prediction": row.prediction}]
                )
            )
    predictions = pd.concat(frames, ignore_index=True)
    ensemble = (
        predictions.loc[predictions.model.str.startswith("FA_ARRF_seed")]
        .groupby(["target_date", "origin_date", "actual"], as_index=False)
        .prediction.mean()
    )
    ensemble["model"] = "FA_ARRF_seed_mean_prediction"
    predictions = pd.concat([predictions, ensemble], ignore_index=True)
    predictions.to_csv(output / "predictions.csv", index=False)
    metrics = score_table(predictions)
    metrics.to_csv(output / "metrics.csv", index=False)
    manifest.update(
        status="completed_reconstruction_not_verified_exact_replication", completed=True
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {
        "status": manifest["status"],
        "output": str(output),
        "metrics": metrics.to_dict(orient="records"),
        "full_evaluation": manifest["full_evaluation"],
    }
