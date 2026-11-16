"""Contracts for exploratory factor comparisons, not alternative forecast-model selection."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor.factor_forensics2018 import (
    BASE,
    NAMES,
    SUBSET,
    component_comparison,
    keep_future_extremes,
    sha,
)
from jev_factor.quarterly import PastRepresentation


def test_comparison_removes_only_training_sign_and_scale_conventions():
    rng = np.random.default_rng(53)
    index = pd.period_range("1980Q1", periods=60, freq="Q")
    reference = pd.DataFrame(
        rng.normal(size=(60, 5)), index=index, columns=[f"F{k}" for k in range(1, 6)]
    )
    candidate = reference * np.array([-3, 2, -0.5, 1, 4]) + np.arange(5)
    a, b, correlations, signs = component_comparison(reference, candidate, index[39])
    np.testing.assert_allclose(a, b, atol=1e-12)
    np.testing.assert_allclose(abs(correlations), 1, atol=1e-12)
    np.testing.assert_array_equal(signs, [-1, 1, -1, 1, 1])


def test_future_values_cannot_choose_sign_or_scaling():
    index = pd.period_range("1980Q1", periods=60, freq="Q")
    reference = pd.DataFrame(np.random.default_rng(54).normal(size=(60, 5)), index=index)
    candidate = reference * -2
    _, original, corr, signs = component_comparison(reference, candidate, index[39])
    changed = candidate.copy()
    changed.iloc[40:] *= -1e8
    _, altered, new_corr, new_signs = component_comparison(reference, changed, index[39])
    np.testing.assert_array_equal(corr, new_corr)
    np.testing.assert_array_equal(signs, new_signs)
    np.testing.assert_allclose(original.iloc[:40], altered.iloc[:40], rtol=0, atol=1e-14)


def test_future_screening_toggle_preserves_fitted_history_and_original_object():
    rng = np.random.default_rng(55)
    frame = pd.DataFrame(
        rng.normal(size=(90, 8)), index=pd.period_range("1980Q1", periods=90, freq="Q")
    )
    frame.iloc[82, 0] = 1e5
    rep = PastRepresentation(5, 10).fit(frame.iloc[:80])
    original_z, _ = rep.transform(frame)
    basis = rep.pca.components_.copy()
    altered_z, _ = keep_future_extremes(rep, frame)
    np.testing.assert_array_equal(altered_z.iloc[:80], original_z.iloc[:80])
    np.testing.assert_array_equal(rep.pca.components_, basis)
    assert rep.outlier_iqr == 10
    assert abs(altered_z.iloc[82, 0]) > 1e4
    assert abs(original_z.iloc[82, 0]) < 100


def test_comparison_rejects_calendar_mismatch():
    index = pd.period_range("1980Q1", periods=60, freq="Q")
    a = pd.DataFrame(np.random.default_rng(56).normal(size=(60, 5)), index=index)
    b = a.copy()
    b.index = index + 1
    with pytest.raises(ValueError, match="rows/components"):
        component_comparison(a, b, index[39])


def test_diagnostic_configuration_retains_no_variant_forest_selection():
    config = json.loads(Path("configs/factor_forensics2018.json").read_text())
    assert set(config["variants"]) == set(NAMES)
    assert config["no_variant_forest_fits_or_forecast_loss_selection"]
    assert not config["author_factor_pipeline_recovered"]
    assert not config["original_run_replaced"]


def test_generated_forensic_artifacts_if_present():
    output = Path("reports/mrf-factor-forensics")
    if not (output / "audit.json").exists():
        pytest.skip("Complete forensic report not generated")
    a = json.loads((output / "audit.json").read_text())
    if a["status"] != "preprocessing_and_crisis_routing_audited" or "findings" not in a:
        pytest.skip("Diagnostic work still in progress")
    assert a["new_variant_forest_fits"] == 0
    assert not a["new_variant_forecast_losses_computed"]
    assert a["crisis_replay"]["saved_output_max_difference"] == 0
    assert a["independent_numerical_check"]["outlier_masks_equal"]
    for name, expected in a["artifact_checksums"].items():
        assert sha(output / name) == expected
    drivers = pd.read_csv(output / "factor-drivers.csv")
    factors = pd.read_csv(output / "factor-variant-scores.csv")
    for (date, component), g in drivers.groupby(["origin_date", "component"]):
        expected = factors[
            factors.group.eq(3)
            & factors.origin_date.eq(date)
            & factors.component.eq(component)
            & factors.variant.eq(BASE)
        ].raw_score.item()
        assert g.contribution.sum() == pytest.approx(expected, abs=1e-10)
    s = pd.read_csv(output / "crisis-factor-snapshot.csv")
    f2 = s[s.component.eq("F2")].set_index("variant")
    assert f2.loc[BASE, "sign_aligned_training_SD"] > 0
    assert f2.loc[SUBSET, "sign_aligned_training_SD"] < 0
