"""Saved table guards on toy data, never reported benchmark results."""

import pandas as pd
import pytest

from jev_factor.arrf_audit import verify_aggregates
from jev_factor.replication import score_table


@pytest.fixture
def saved_tables(tmp_path):
    predictions = pd.DataFrame(
        {
            "model": ["AR4", "AR4", "ARRF_seed101", "ARRF_seed101"],
            "target_date": ["2003Q1", "2003Q2"] * 2,
            "origin_date": ["2002Q4", "2003Q1"] * 2,
            "actual": [1.0, 2.0] * 2,
            "prediction": [0.0, 0.0, 1.1, 1.9],
        }
    )
    predictions.to_csv(tmp_path / "predictions.csv", index=False)
    score_table(predictions).to_csv(tmp_path / "metrics.csv", index=False)
    return tmp_path, predictions


def test_matching_saved_tables_pass(saved_tables):
    run, expected = saved_tables
    verify_aggregates(run, expected)


@pytest.mark.parametrize(
    "problem",
    [
        "prediction",
        "origin",
        "duplicate_prediction",
        "extra_metric",
        "duplicate_metric",
        "metric_value",
    ],
)
def test_stale_or_altered_saved_tables_are_rejected(saved_tables, problem):
    run, expected = saved_tables
    forecasts = pd.read_csv(run / "predictions.csv")
    metrics = pd.read_csv(run / "metrics.csv")
    if problem == "prediction":
        forecasts.loc[0, "prediction"] += 1
    elif problem == "origin":
        forecasts.loc[0, "origin_date"] = "2001Q4"
    elif problem == "duplicate_prediction":
        forecasts = pd.concat([forecasts, forecasts.iloc[:1]], ignore_index=True)
    elif problem == "extra_metric":
        row = metrics.iloc[:1].copy()
        row["model"] = "undeclared_model"
        metrics = pd.concat([metrics, row], ignore_index=True)
    elif problem == "duplicate_metric":
        metrics = pd.concat([metrics, metrics.iloc[:1]], ignore_index=True)
    else:
        metrics.loc[0, "RMSE"] *= 2
    forecasts.to_csv(run / "predictions.csv", index=False)
    metrics.to_csv(run / "metrics.csv", index=False)
    with pytest.raises(ValueError):
        verify_aggregates(run, expected)
