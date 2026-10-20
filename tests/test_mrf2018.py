import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor.mrf2018 import FOREST, audit, rich_design, settings_for, validate_config
from jev_factor.mrf2018_report import write_report
from jev_factor.quarterly import QuarterlyData


def config():
    return json.loads(Path("configs/mrf_september2018.json").read_text())


def toy():
    rng = np.random.default_rng(118)
    dates = pd.period_range("1959Q1", periods=200, freq="Q")
    x = rng.normal(size=(200, 8))
    x[10:13, 2] = np.nan
    panel = pd.DataFrame(x, index=dates, columns=[f"s{i}" for i in range(8)])
    target = pd.Series(rng.normal(size=200), index=dates)
    codes = pd.Series(1, index=panel.columns)
    return QuarterlyData(panel.copy(), panel, target, codes, codes, {})


def test_rich_design_raw_pairing_equation_and_final_forecast():
    data = toy()
    end = data.panel.index[160]
    state, raw, ar, meta = rich_design(data, end, end + 8, config())
    assert str(state.index[0]) == "1961Q3"
    assert state.index[-1] == end + 8
    assert meta["state_columns"] == 8 + 40 + 8 * 2 + 8 * 2 + 1
    assert meta["representation_fit_end"] == str(end - 1)
    assert state.loc[end + 1, "y_lag1"] == data.target[end]
    assert state.loc[end + 1, "y_lag2"] == data.target[end - 1]
    assert meta["MAF_fit_rows"] == meta["ntrain"]
    assert meta["maximum_RF_raw_pairing_error"] == 0
    for j in range(8):
        for lag in [1, 2]:
            np.testing.assert_array_equal(
                state[f"series_{j:03d}_lag{lag}"], raw[f"raw_{j:03d}_lag{lag - 1}"]
            )
    for k in range(4):
        np.testing.assert_array_equal(state[f"y_lag{k + 1}"], ar[f"ar_lag{k}"])


def test_MAFs_agree_with_independent_covariance_eigendecomposition():
    data = toy()
    state, raw, _, meta = rich_design(data, data.panel.index[160], data.panel.index[168], config())
    n = meta["ntrain"]
    for j in range(8):
        x = raw[[f"raw_{j:03d}_lag{k}" for k in range(8)]].to_numpy()
        covariance = np.cov(x[:n], rowvar=False, ddof=1)
        values, vectors = np.linalg.eigh(covariance)
        components = vectors[:, np.argsort(values)[::-1][:2]].T
        signs = np.sign(components[np.arange(2), np.argmax(np.abs(components), axis=1)])
        components *= signs[:, None]
        expected = (x - x[:n].mean(axis=0)) @ components.T
        np.testing.assert_allclose(
            expected, state[[f"MAF_{j:03d}_1", f"MAF_{j:03d}_2"]], atol=1e-11
        )
        np.testing.assert_allclose(components, meta["MAF_loadings"][j], atol=1e-11)


def test_later_covariates_and_outcomes_cannot_change_first_forecast_design():
    data = toy()
    end = data.panel.index[160]
    original, _, _, meta = rich_design(data, end, end + 8, config())
    altered = deepcopy(data)
    altered.panel.loc[end + 1 :, "s0"] += 1e6
    altered.target.loc[end + 1 :] -= 1e6
    changed, _, _, changed_meta = rich_design(altered, end, end + 8, config())
    np.testing.assert_allclose(
        original.loc[: end + 1].iloc[:, 1:], changed.loc[: end + 1].iloc[:, 1:], atol=1e-12
    )
    assert meta == changed_meta


@pytest.mark.parametrize(
    "key,value",
    [
        ("plain_RF_gate_passed", True),
        ("qualified_advance_authorized", False),
        ("trees", 500),
        ("seeds", [101]),
        ("first_training_target", "1961Q4"),
    ],
)
def test_only_the_explicit_qualified_declaration_is_supported(key, value):
    c = config()
    validate_config(c)
    c[key] = value
    with pytest.raises(ValueError, match="qualified"):
        validate_config(c)


def test_plain_RF_settings_are_not_propagated_to_linear_leaf_MRF():
    c = config()
    s = settings_for(c, 166, 101, 100)
    assert s["trees"] == 100
    assert s["minsize"] == 10
    assert s["prior"] == "OLS"
    assert s["standardization"] == "train_only"
    assert s["xnames"] == "y_lag1,y_lag2,F1_lag1,F2_lag1"
    assert {k: s[k] for k in FOREST} == FOREST


def test_partial_or_pilot_results_do_not_get_accuracy_or_source_match(monkeypatch, tmp_path):
    # A complete pilot cannot bypass the full-grid requirement, even if an
    # upstream completion field is true. No baseline-only score is published.
    import jev_factor.mrf2018 as module

    c = config()
    baseline = pd.DataFrame(columns=["model", "target_date", "origin_date", "actual", "prediction"])
    baseline.to_csv(tmp_path / "baseline_predictions.csv", index=False)
    source = tmp_path / "rf"
    source.mkdir()
    baseline.to_csv(source / "predictions.csv", index=False)
    manifest = {
        "pilot": True,
        "completed": True,
        "config": c,
        "actual_trees": 2,
        "archive": "unused",
        "data": {},
        "code": {},
        "engine": {},
        "RF_source": {"source": str(source)},
        "windows": [],
        "jobs": [],
    }
    monkeypatch.setattr(module, "checked", lambda _: manifest)
    monkeypatch.setattr(module, "load_vintage", lambda _: None)
    monkeypatch.setattr(module, "checked_manifest", lambda _: {})
    result = audit(tmp_path, allow_partial=True)
    assert result["metrics"] == []
    assert result["source_cell_checks"] == []
    assert result["joint_source_cell_diagnostic"] is None
    assert result["full_declaration_verified"] is False
    assert result["partial_scores_suppressed"] is True
    assert not (tmp_path / "predictions.csv").exists()
    with pytest.raises(ValueError, match="Full audit"):
        audit(tmp_path)


def test_report_rejects_partial_accuracy_and_retains_qualified_wording(tmp_path):
    with pytest.raises(ValueError, match="partial"):
        write_report(tmp_path, {"full_declaration_verified": False})
    complete = {
        "full_declaration_verified": True,
        "partial_scores_suppressed": False,
        "jobs_verified": 18,
        "actual_trees": 100,
        "joint_source_cell_diagnostic": False,
        "metrics": [{"model": "FA_ARRF_seed101", "RMSE": 0.1, "RMSE_over_AR4": 0.9}],
        "RMSE_reduction_vs_matching_FA_AR": {"101": 0.01, "202": 0.02, "303": 0.03},
    }
    path = write_report(tmp_path, complete)
    text = path.read_text()
    assert "qualified reconstruction" in text
    assert "criterion remains failed" in text
    assert "**fails**" in text
    assert "not an independent refit" in text
