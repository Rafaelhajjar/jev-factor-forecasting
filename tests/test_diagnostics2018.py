"""Diagnostic math and integrity guards; no expensive forest retraining."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor.diagnostics2018 import TERMS, digest, verify_trace


@pytest.fixture
def trace_fixture(tmp_path):
    rng = np.random.default_rng(52)
    individual = rng.normal(size=(28, 100)) / 100
    truth = rng.normal(size=28) / 100
    original = pd.DataFrame({"prediction": individual[20:].mean(axis=1)})
    for term in TERMS:
        original[term] = 0.0
    original.to_csv(tmp_path / "original.csv", index=False)
    original.to_csv(tmp_path / "replay.csv", index=False)
    trace = pd.DataFrame(individual, columns=[f"tree_{b}" for b in range(1, 101)])
    trace.insert(0, "observed_training_target", np.r_[truth[:20], np.full(8, np.nan)])
    trace.insert(0, "role", ["train"] * 20 + ["forecast"] * 8)
    trace.insert(0, "row_index", np.arange(1, 29))
    trace.to_csv(tmp_path / "replay.csv.trees.csv", index=False)
    pd.DataFrame({"actual": truth}).to_csv(tmp_path / "alignment.csv", index=False)
    pd.DataFrame({"tree": np.arange(1, 101), "path": "x < 1", "n_split_sample": 20}).to_csv(
        tmp_path / "replay.csv.leaves.csv", index=False
    )
    data = {
        "manifest": {
            "jobs": [{"prediction_path": str(tmp_path / "original.csv")}],
            "windows": [{"metadata": {"ntrain": 20}, "alignment": str(tmp_path / "alignment.csv")}],
        }
    }
    return data, tmp_path, individual, truth


def test_tree_prefix_loss_matches_independent_scalar_calculation(trace_fixture):
    data, path, individual, truth = trace_fixture
    result = verify_trace(data, path)
    for b in [1, 2, 37, 100]:
        expected_train = (
            sum(
                (sum(row[:b]) / b - y) ** 2
                for row, y in zip(individual[:20], truth[:20], strict=True)
            )
            / 20
        )
        expected_test = (
            sum(
                (sum(row[:b]) / b - y) ** 2
                for row, y in zip(individual[20:], truth[20:], strict=True)
            )
            / 8
        )
        assert result["curves"].loc[b - 1, "training_MSE"] == pytest.approx(expected_train)
        assert result["curves"].loc[b - 1, "heldout_MSE"] == pytest.approx(expected_test)
    assert result["match_max_abs"] == 0


def test_changed_replayed_coefficient_is_rejected_even_if_point_predictions_match(trace_fixture):
    data, path, _, _ = trace_fixture
    f = pd.read_csv(path / "replay.csv")
    f.loc[0, "F1_lag1"] += 0.01
    f.to_csv(path / "replay.csv", index=False)
    with pytest.raises(ValueError, match="did not reproduce"):
        verify_trace(data, path)


def test_true_future_targets_cannot_be_in_trace_training_column(trace_fixture):
    data, path, _, _ = trace_fixture
    f = pd.read_csv(path / "replay.csv.trees.csv")
    f.loc[27, "observed_training_target"] = 1.0
    f.to_csv(path / "replay.csv.trees.csv", index=False)
    with pytest.raises(ValueError, match="outcomes were supplied"):
        verify_trace(data, path)


def test_missing_tree_cannot_be_silently_averaged(trace_fixture):
    data, path, _, _ = trace_fixture
    f = pd.read_csv(path / "replay.csv.trees.csv").drop(columns="tree_100")
    f.to_csv(path / "replay.csv.trees.csv", index=False)
    with pytest.raises(ValueError, match="Missing/nonfinite"):
        verify_trace(data, path)


def test_changed_per_tree_forecast_is_rejected(trace_fixture):
    data, path, _, _ = trace_fixture
    f = pd.read_csv(path / "replay.csv.trees.csv")
    f.loc[25, "tree_41"] += 0.01
    f.to_csv(path / "replay.csv.trees.csv", index=False)
    with pytest.raises(ValueError, match="average does not match"):
        verify_trace(data, path)


def test_missing_retained_tree_is_rejected(trace_fixture):
    data, path, _, _ = trace_fixture
    f = pd.read_csv(path / "replay.csv.leaves.csv").iloc[:-1]
    f.to_csv(path / "replay.csv.leaves.csv", index=False)
    with pytest.raises(ValueError, match="Incomplete retained forest"):
        verify_trace(data, path)


def test_published_diagnostic_artifacts_if_present():
    report = Path("reports/mrf-september2018-diagnostics")
    if not (report / "diagnostics.json").exists():
        pytest.skip("The complete diagnostic report has not been generated")
    record = json.loads((report / "diagnostics.json").read_text())
    assert record["figure_count"] == 31
    assert record["original_predictions_replaced"] is False
    assert record["replay"]["maximum_saved_output_difference"] < 1e-12
    assert record["replay"]["strict_oob_validation"] is False
    for name, expected in record["artifact_checksums"].items():
        assert digest(report / name) == expected
    page = (report / "index.html").read_text()
    assert page.count("<figure id=") == 31
    for g in record["figures"]:
        assert f"figures/{g['slug']}.png" in page
        assert (report / "figures" / f"{g['slug']}.svg").is_file()
