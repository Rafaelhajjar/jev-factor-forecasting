"""Workflow guards use toy data, not purported macroeconomic benchmark scores."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor import replication
from jev_factor.quarterly import QuarterlyData


@pytest.fixture
def prepared_inputs(monkeypatch):
    rng = np.random.default_rng(81)
    index = pd.period_range("1959Q1", periods=90, freq="Q")
    panel = pd.DataFrame(rng.normal(size=(90, 7)), index=index)
    panel.columns = [f"series{i}" for i in range(7)]
    target = pd.Series(rng.normal(size=90), index=index)
    data = QuarterlyData(
        panel.copy(),
        panel,
        target,
        pd.Series(1, index=panel.columns),
        pd.Series(1, index=panel.columns),
        {"toy_data_not_real_benchmark": True},
    )
    config = json.loads(Path("configs/mrf_unemployment.json").read_text())
    config.update(
        evaluation_start=str(index[66]),
        evaluation_end=str(index[73]),
        em_rank=3,
        pca_rank=3,
        outlier_iqr=None,
        trees=2,
        seeds=[101],
    )
    monkeypatch.setattr(replication, "load_quarterly", lambda path: data)
    monkeypatch.setattr(replication, "download_archive", lambda path: None)
    monkeypatch.setattr(replication, "ensure_engine", lambda path: {"toy_engine": True})
    return data, config


def test_prepared_engine_inputs_never_contain_held_out_truth(tmp_path, prepared_inputs):
    data, config = prepared_inputs
    manifest = replication.prepare_jobs(config, tmp_path / "unused.zip", tmp_path)
    assert manifest["full_evaluation"]
    job = manifest["jobs"][0]
    matrix = pd.read_csv(job["matrix"])
    ntrain = manifest["representations"][0]["ntrain"]
    np.testing.assert_allclose(matrix.target.iloc[ntrain:], matrix.target.iloc[:ntrain].mean())
    actual = [record["actual"] for record in job["targets"]]
    np.testing.assert_allclose(
        actual, data.target.loc[config["evaluation_start"] : config["evaluation_end"]]
    )
    assert not np.allclose(matrix.target.iloc[ntrain:], actual)
    assert job["fit_end"] == str(pd.Period(config["evaluation_start"]) - 1)
    assert job["targets"][0]["origin_date"] == job["fit_end"]
    assert hashlib.sha256(Path(job["matrix"]).read_bytes()).hexdigest() == job["matrix_sha256"]
    assert hashlib.sha256(Path(job["settings"]).read_bytes()).hexdigest() == job["settings_sha256"]


def test_reconstruction_does_not_overwrite_existing_run(tmp_path, prepared_inputs):
    _, config = prepared_inputs
    with pytest.raises(FileExistsError, match="Output already exists"):
        replication.run_reconstruction(
            config, tmp_path / "unused.zip", tmp_path / "unused.R", tmp_path
        )


@pytest.mark.parametrize("change", ["config", "source", "matrix", "settings"])
def test_resume_rejects_changed_inputs(tmp_path, prepared_inputs, change):
    _, config = prepared_inputs
    output = tmp_path / "run"
    kwargs = {
        "config": config,
        "archive": tmp_path / "unused.zip",
        "engine": tmp_path / "unused.R",
        "output": output,
    }
    replication.run_reconstruction(**kwargs, prepare_only=True)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if change == "config":
        kwargs["config"] = {**config, "trees": 3}
    elif change == "source":
        manifest["integration_source_sha256"]["quarterly.py"] = "different-source"
        manifest_path.write_text(json.dumps(manifest))
    else:
        Path(manifest["jobs"][0][change]).write_text("modified prepared input\n")
    with pytest.raises(ValueError, match="differ|changed"):
        replication.run_reconstruction(**kwargs, resume=True)


def test_checkpoint_requires_complete_finite_coefficient_output(tmp_path):
    output = tmp_path / "forecast.csv"
    job = {"prediction_path": str(output), "targets": [1, 2]}
    assert not replication._valid_checkpoint(job)
    columns = ["prediction", "intercept", *replication.LINEAR_X]
    pd.DataFrame(np.ones((2, len(columns))), columns=columns).to_csv(output, index=False)
    assert not replication._valid_checkpoint(job)  # No completed runtime sidecar.
    Path(str(output) + ".runtime.dcf").write_text("R_version: contract-test\n")
    assert replication._valid_checkpoint(job)
    pd.DataFrame({"prediction": [1, 2]}).to_csv(output, index=False)
    assert not replication._valid_checkpoint(job)
    frame = pd.DataFrame(np.ones((2, len(columns))), columns=columns)
    frame.loc[0, "prediction"] = np.nan
    frame.to_csv(output, index=False)
    assert not replication._valid_checkpoint(job)


def test_corrupt_external_engine_fails_before_execution(tmp_path):
    engine = tmp_path / "engine.R"
    engine.write_text("not the checksum-pinned engine\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        replication.ensure_engine(engine)
