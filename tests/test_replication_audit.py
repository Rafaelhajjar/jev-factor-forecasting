"""Verifier contracts use explicitly synthetic saved artifacts, never published scores."""

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor import replication, replication_audit
from jev_factor.quarterly import QuarterlyData


@pytest.fixture
def synthetic_artifacts(tmp_path, monkeypatch):
    rng = np.random.default_rng(92)
    index = pd.period_range("1959Q1", periods=240, freq="Q")
    panel = pd.DataFrame(
        rng.normal(size=(240, 7)), index=index, columns=[f"series{i}" for i in range(7)]
    )
    levels = pd.DataFrame({"UNRATE": np.exp(2 + np.cumsum(rng.normal(0, 0.02, 240)))}, index=index)
    target = np.log(levels.UNRATE).diff()
    metadata = {"fixture": "synthetic_contract_data_not_journal_archive"}
    data = QuarterlyData(
        levels,
        panel,
        target,
        pd.Series(1, index=panel.columns),
        pd.Series(1, index=panel.columns),
        metadata,
    )
    config = json.loads(Path("configs/mrf_unemployment.json").read_text())
    config.update(
        study="synthetic_saved_artifact_contract_only",
        em_rank=3,
        pca_rank=3,
        outlier_iqr=None,
        trees=2,
    )
    monkeypatch.setattr(replication, "load_quarterly", lambda path: data)
    monkeypatch.setattr(replication_audit, "load_quarterly", lambda path: data)
    run = tmp_path / "synthetic-contract-not-a-real-benchmark"
    run.mkdir()
    manifest = replication.prepare_jobs(config, tmp_path / "unused.zip", run)
    manifest["external_engine"] = {
        "commit": replication.AUTHOR_COMMIT,
        "sha256": replication.AUTHOR_SHA256,
    }
    manifest["integration_source_sha256"] = {
        name: replication_audit._sha(Path(replication.__file__).with_name(name))
        for name in ["replication.py", "quarterly.py", "reference_mrf.R"]
    }
    shutil.copyfile(
        Path(replication.__file__).with_name("reference_mrf.R"), run / "reference_mrf.R"
    )
    baseline = pd.read_csv(run / "baseline_predictions.csv")
    frames = [baseline]
    for job in manifest["jobs"]:
        destination = Path(job["prediction_path"])
        # Deliberately fake zero forecasts exercise serialization and identity checks.
        # Actual-engine correctness is covered by separate real-R contracts/smokes.
        pd.DataFrame(
            0.0,
            index=range(len(job["targets"])),
            columns=["prediction", "intercept", *replication.LINEAR_X],
        ).to_csv(destination, index=False)
        Path(str(destination) + ".runtime.dcf").write_text(
            "R_version: synthetic-fixture-not-executed\npracma_version: fixture\n"
            "prior: OLS\nstandardization: train_only\nelapsed_seconds: 0\n"
        )
        frames.append(
            pd.DataFrame(
                [
                    {**record, "model": f"FA_ARRF_seed{job['seed']}", "prediction": 0.0}
                    for record in job["targets"]
                ]
            )
        )
    forecasts = pd.concat(frames, ignore_index=True)
    ensemble = forecasts.loc[forecasts.model.eq("FA_ARRF_seed101")].copy()
    ensemble["model"] = "FA_ARRF_seed_mean_prediction"
    forecasts = pd.concat([forecasts, ensemble], ignore_index=True)
    forecasts.to_csv(run / "predictions.csv", index=False)
    replication.score_table(forecasts).to_csv(run / "metrics.csv", index=False)
    manifest.update(
        completed=True, status="completed_reconstruction_not_verified_exact_replication"
    )
    (run / "manifest.json").write_text(json.dumps(manifest))

    def fake_qr(matrix_path, ntrain, rscript, directory):
        matrix = pd.read_csv(matrix_path)
        ar = [f"y_lag{k}" for k in range(1, 5)]
        fa = ar + [f"F{j}_lag{k}" for j in [1, 2] for k in [1, 2]]
        result = {
            model: replication.linear_prediction(matrix.iloc[:ntrain], matrix.iloc[ntrain:], cols)
            for model, cols in [("AR4", ar), ("FA_AR", fa)]
        }
        return pd.DataFrame(result), "mock QR for verifier unit contract only"

    monkeypatch.setattr(replication_audit, "_r_linear", fake_qr)
    return run, config, manifest


def _audit(artifacts, **kwargs):
    run, config, _ = artifacts
    return replication_audit.audit_run(run, run / "unused.zip", config, **kwargs)


def test_artifact_verification_never_claims_unknown_author_pipeline(synthetic_artifacts):
    report = _audit(synthetic_artifacts)
    assert report["full_48_quarter_artifacts_verified"]
    assert report["jobs_verified"] == 18
    assert report["exact_author_pipeline_verified"] is False
    assert report["matches_declared_config"]
    assert len(report["linear_R_QR_vs_Python_SVD"]) == 6
    assert len(report["metrics"]) == 6  # AR, FA-AR, all 3 seeds and separately named mean.
    assert len(report["published_ratio_comparisons"]) == 5
    assert report["config"]["study"] == "synthetic_saved_artifact_contract_only"


def test_partial_outputs_cannot_claim_reproduction_or_publish_partial_scores(synthetic_artifacts):
    _, _, manifest = synthetic_artifacts
    Path(manifest["jobs"][0]["prediction_path"]).unlink()
    with pytest.raises(ValueError, match="incomplete"):
        _audit(synthetic_artifacts)
    report = _audit(synthetic_artifacts, allow_partial=True)
    assert not report["full_48_quarter_artifacts_verified"]
    assert report["jobs_verified"] == 17
    assert {row["model"] for row in report["metrics"]} == {"AR4", "FA_AR"}
    assert not report["published_ratio_comparisons"]
    assert report["partial_forest_scores_suppressed"]


@pytest.mark.parametrize("field", ["intercept", "F1_lag1"])
def test_wrong_coefficient_decomposition_is_detected(synthetic_artifacts, field):
    _, _, manifest = synthetic_artifacts
    path = Path(manifest["jobs"][0]["prediction_path"])
    frame = pd.read_csv(path)
    frame.loc[0, field] = 1
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="forecast/coefficient"):
        _audit(synthetic_artifacts)


@pytest.mark.parametrize("column", ["y_lag1", "F1_lag1", "MAF_000_1"])
def test_timing_checked_even_if_input_checksum_is_rewritten(synthetic_artifacts, column):
    run, _, manifest = synthetic_artifacts
    path = Path(manifest["jobs"][0]["matrix"])
    matrix = pd.read_csv(path)
    matrix.loc[0, column] += 1
    matrix.to_csv(path, index=False)
    for job in manifest["jobs"]:
        if job["matrix"] == str(path):
            job["matrix_sha256"] = replication_audit._sha(path)
    (run / "manifest.json").write_text(json.dumps(manifest))
    error = "target lag 1" if column == "y_lag1" else "recomputed frozen states"
    with pytest.raises(ValueError, match=error):
        _audit(synthetic_artifacts)


def test_saved_final_metrics_are_recomputed(synthetic_artifacts):
    run, _, _ = synthetic_artifacts
    metrics = pd.read_csv(run / "metrics.csv")
    metrics.loc[0, "RMSE"] += 1
    metrics.to_csv(run / "metrics.csv", index=False)
    with pytest.raises(ValueError, match="saved final metrics"):
        _audit(synthetic_artifacts)


@pytest.mark.parametrize("filename", ["baseline_metrics.csv", "metrics.csv"])
def test_undeclared_models_in_metric_tables_are_rejected(synthetic_artifacts, filename):
    run, _, _ = synthetic_artifacts
    path = run / filename
    metrics = pd.read_csv(path)
    extra = metrics.iloc[:1].assign(model="undeclared_stale_result", RMSE=0)
    pd.concat([metrics, extra], ignore_index=True).to_csv(path, index=False)
    with pytest.raises(ValueError, match="metric model grid differs"):
        _audit(synthetic_artifacts)


@pytest.mark.parametrize("change", ["missing_seed", "shifted_origin", "unmasked_target"])
def test_job_grid_and_future_target_mask_checked(synthetic_artifacts, change):
    run, _, manifest = synthetic_artifacts
    if change == "missing_seed":
        manifest["jobs"].pop()
        error = "declared refit/seed"
    elif change == "shifted_origin":
        manifest["jobs"][0]["targets"][0]["origin_date"] = "2000Q1"
        error = "origin-date"
    else:
        job = manifest["jobs"][0]
        path = Path(job["matrix"])
        frame = pd.read_csv(path)
        frame.loc[len(frame) - 1, "target"] = 100
        frame.to_csv(path, index=False)
        for item in manifest["jobs"]:
            if item["matrix"] == str(path):
                item["matrix_sha256"] = replication_audit._sha(path)
        error = "held-out target mask"
    (run / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=error):
        _audit(synthetic_artifacts)
