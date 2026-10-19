"""Explicit synthetic artifact contracts, not simulated replication evidence."""

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor.arrf_diagnostic import (
    LINEAR_TERMS,
    _sha,
    check_arrf_output,
    collect_outputs,
    prepare_arrf_jobs,
    validate_job_grid,
    validate_resume,
)


@pytest.fixture
def fixture_artifacts(tmp_path):
    primary = tmp_path / "synthetic-source"
    primary.mkdir()
    rng = np.random.default_rng(80)
    matrix = pd.DataFrame(
        rng.normal(size=(38, 8)),
        columns=["target", "y_lag1", "y_lag2", "F1_lag1", "F2_lag1", "state_a", "state_b", "trend"],
    )
    matrix.loc[30:, "target"] = matrix.target.iloc[:30].mean()
    path = primary / "matrix.csv"
    matrix.to_csv(path, index=False)
    dates = pd.period_range("2003Q1", periods=8, freq="Q")
    targets = [
        {"target_date": str(t), "origin_date": str(t - 1), "actual": 0.01 * i}
        for i, t in enumerate(dates)
    ]
    source = {"config": {"seeds": [101, 202]}, "jobs": []}
    for seed in [101, 202]:
        settings = primary / f"settings_{seed}.dcf"
        settings.write_text(
            f"ntrain: 30\nxnames: y_lag1,y_lag2,F1_lag1,F2_lag1\ntrees: 100\n"
            f"seed: {seed}\nprior: OLS\nstandardization: train_only\nblock: 8\n"
        )
        source["jobs"].append(
            {
                "group": 0,
                "seed": seed,
                "fit_end": "2002Q4",
                "targets": targets,
                "matrix": str(path),
                "matrix_sha256": _sha(path),
                "settings": str(settings),
                "settings_sha256": _sha(settings),
                "prediction_path": "unused.csv",
            }
        )
    config = json.loads(Path("configs/mrf_arrf_diagnostic.json").read_text())
    config.update(trees=2, seeds=[101, 202])
    output = tmp_path / "synthetic-ARRF-contract-only"
    output.mkdir()
    jobs = prepare_arrf_jobs(source, output, config, max_refits=1)
    manifest = {
        "config": config,
        "declaration": copy.deepcopy(config),
        "max_refits": 1,
        "jobs": jobs,
        "full_declared_diagnostic": False,
    }
    for job in jobs:
        # Known artificial coefficients test serialization and reconstruction only.
        result = pd.DataFrame({"intercept": np.repeat(0.1, 8), "y_lag1": 0.2, "y_lag2": -0.1})
        result.insert(
            0,
            "prediction",
            result.intercept
            + np.sum(
                result[LINEAR_TERMS].to_numpy() * matrix.iloc[30:][LINEAR_TERMS].to_numpy(), axis=1
            ),
        )
        result.to_csv(job["prediction_path"], index=False)
        Path(job["prediction_path"] + ".runtime.dcf").write_text(
            "R_version: fake-fixture-not-executed\nprior: OLS\nstandardization: train_only\n"
        )
    predictions = pd.DataFrame([{**r, "model": "AR4", "prediction": 0.1} for r in targets])
    return source, manifest, output, predictions


def test_only_explicit_equation_changes_and_full_state_is_retained(fixture_artifacts):
    source, manifest, output, _ = fixture_artifacts
    validate_job_grid(manifest, source, output)
    for original, job in zip(source["jobs"], manifest["jobs"], strict=True):
        assert job["matrix"] == original["matrix"]
        assert job["matrix_sha256"] == original["matrix_sha256"]
        assert _sha(Path(original["settings"])) == original["settings_sha256"]
        assert "F1_lag1" in pd.read_csv(job["matrix"])
        assert "state_b" in pd.read_csv(job["matrix"])
        assert "xnames: y_lag1,y_lag2\n" in Path(job["settings"]).read_text()


@pytest.mark.parametrize(
    "problem", ["missing", "duplicate", "targets", "matrix", "path", "setting"]
)
def test_grid_or_setting_tampering_is_rejected(fixture_artifacts, problem):
    source, original, output, _ = fixture_artifacts
    manifest = copy.deepcopy(original)
    if problem == "missing":
        manifest["jobs"].pop()
    elif problem == "duplicate":
        manifest["jobs"].append(copy.deepcopy(manifest["jobs"][0]))
    elif problem == "targets":
        manifest["jobs"][0]["targets"][0]["target_date"] = "2004Q1"
    elif problem == "matrix":
        manifest["jobs"][0]["matrix_sha256"] = "incorrect"
    elif problem == "path":
        manifest["jobs"][0]["prediction_path"] = str(output.parent / "outside.csv")
    else:
        job = manifest["jobs"][0]
        path = Path(job["settings"])
        path.write_text(path.read_text().replace("block: 8", "block: 12"))
        job["settings_sha256"] = _sha(path)  # updating a checksum cannot authorize a change
    with pytest.raises(ValueError):
        validate_job_grid(manifest, source, output)


def test_output_coefficients_reconstruct_and_bad_values_are_rejected(fixture_artifacts):
    _, manifest, _, _ = fixture_artifacts
    job = manifest["jobs"][0]
    _, error, _ = check_arrf_output(job)
    assert error < 1e-14
    frame = pd.read_csv(job["prediction_path"])
    frame.loc[0, "y_lag1"] += 1
    frame.to_csv(job["prediction_path"], index=False)
    with pytest.raises(ValueError, match="reconstruct"):
        check_arrf_output(job)


def test_factor_coefficients_cannot_enter_the_ARRF_output(fixture_artifacts):
    _, manifest, _, _ = fixture_artifacts
    job = manifest["jobs"][0]
    frame = pd.read_csv(job["prediction_path"])
    frame["F1_lag1"] = 0
    frame.to_csv(job["prediction_path"], index=False)
    with pytest.raises(ValueError, match="schema"):
        check_arrf_output(job)


def test_bounded_pilot_never_publishes_forest_scores_or_source_comparisons(fixture_artifacts):
    _, manifest, _, predictions = fixture_artifacts
    result, frames = collect_outputs(manifest, predictions)
    assert result["jobs_verified"] == 2
    assert result["partial_forest_scores_suppressed"]
    assert result["metrics"] == result["published_ARRF_comparisons"] == []
    assert result["FA_ARRF_replication_established_by_this_diagnostic"] is False
    assert len(frames) == 8 * 4  # reference, 2 seeds and separately labeled mean


def test_false_full_flag_cannot_relabel_a_pilot(fixture_artifacts):
    _, manifest, _, predictions = fixture_artifacts
    manifest["full_declared_diagnostic"] = True
    with pytest.raises(ValueError, match="48-quarter"):
        collect_outputs(manifest, predictions)


def test_resume_rejects_changed_provenance_and_changed_frozen_inputs(fixture_artifacts):
    _, manifest, _, _ = fixture_artifacts
    expected = {"source_manifest_sha256": "known"}
    manifest.update(expected)
    validate_resume(manifest, expected)
    with pytest.raises(ValueError, match="provenance"):
        validate_resume(manifest, {"source_manifest_sha256": "different"})
    path = Path(manifest["jobs"][0]["matrix"])
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="matrix"):
        validate_resume(manifest, expected)
