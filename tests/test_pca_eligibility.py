"""Representation contracts on synthetic inputs, not macroeconomic forecast results."""

import numpy as np
import pandas as pd
import pytest

from jev_factor.pca_eligibility import replace_factor_lags, score_geometry, subset_factors


def panel():
    index = pd.period_range("1960Q1", periods=50, freq="Q")
    z = pd.DataFrame(np.random.default_rng(711).normal(size=(50, 8)), index=index)
    z.columns = [f"series_{k}" for k in range(8)]
    membership = pd.Series([1] * 6 + [0] * 2, index=z.columns)
    return z, membership, index[35]


def test_subset_pca_uses_the_declared_columns_and_matches_independent_svd():
    z, membership, endpoint = panel()
    scores, fitted, selected = subset_factors(z, membership, endpoint)
    assert selected == list(z.columns[:6])
    assert list(scores) == [f"F{k}" for k in range(1, 6)]
    x = z.loc[:endpoint, selected].to_numpy()
    _, _, vt = np.linalg.svd(x - x.mean(axis=0), full_matrices=False)
    np.testing.assert_allclose(np.abs(fitted.components_ @ vt[:5].T), np.eye(5), atol=1e-12)
    np.testing.assert_allclose(scores.loc[:endpoint], (x - x.mean(axis=0)) @ fitted.components_.T)


def test_future_values_cannot_change_loadings_or_training_scores():
    z, membership, endpoint = panel()
    scores, fitted, _ = subset_factors(z, membership, endpoint)
    perturbed = z.copy()
    perturbed.loc[endpoint + 1 :] *= 10000
    changed, other, _ = subset_factors(perturbed, membership, endpoint)
    np.testing.assert_array_equal(fitted.components_, other.components_)
    np.testing.assert_array_equal(scores.loc[:endpoint], changed.loc[:endpoint])
    assert not np.array_equal(scores.loc[endpoint + 1 :], changed.loc[endpoint + 1 :])


def test_excluded_training_series_do_not_affect_subset_pca():
    z, membership, endpoint = panel()
    scores, _, _ = subset_factors(z, membership, endpoint)
    changed = z.copy()
    changed.loc[:, membership.eq(0)] *= 10000
    other, _, _ = subset_factors(changed, membership, endpoint)
    np.testing.assert_array_equal(scores, other)


@pytest.mark.parametrize("kind", ["order", "flag", "nan", "dates", "constant", "rank", "endpoint"])
def test_invalid_or_ambiguous_subset_input_is_rejected(kind):
    z, membership, endpoint = panel()
    rank = 5
    if kind == "order":
        membership = membership.iloc[::-1]
    elif kind == "flag":
        membership.iloc[0] = 2
    elif kind == "nan":
        z.iloc[-1, -1] = np.nan
    elif kind == "dates":
        z = z.drop(z.index[3])
    elif kind == "constant":
        z.iloc[:, 0] = 1
    elif kind == "rank":
        rank = 7
    elif kind == "endpoint":
        endpoint = z.index[-1] + 1
    with pytest.raises(ValueError):
        subset_factors(z, membership, endpoint, rank)


def design_and_scores():
    index = pd.period_range("1960Q1", periods=20, freq="Q")
    scores = pd.DataFrame({"F1": np.arange(20.0), "F2": np.arange(20.0) ** 2}, index=index)
    targets = pd.period_range(index[8], index[-1] + 1, freq="Q")
    values = {"target": np.arange(len(targets), dtype=float)}
    values.update({f"F{k}_lag{lag}": np.zeros(len(targets)) for k in (1, 2) for lag in range(1, 9)})
    values.update(
        {k: np.ones(len(targets)) for k in ("y_lag1", "series_001_lag1", "MAF_001_1", "trend")}
    )
    return pd.DataFrame(values, index=targets), scores


def test_replacement_preserves_all_other_entries_and_the_final_forecast_row():
    design, scores = design_and_scores()
    before = design.copy(deep=True)
    changed = replace_factor_lags(design, scores)
    assert design.equals(before)
    assert list(changed) == list(design) and changed.index.equals(design.index)
    untouched = [k for k in design if not k.startswith("F")]
    pd.testing.assert_frame_equal(changed[untouched], design[untouched], check_exact=True)
    assert changed.iloc[-1].F1_lag1 == scores.iloc[-1].F1
    assert changed.iloc[0].F2_lag8 == scores.iloc[0].F2
    assert np.isfinite(changed.to_numpy()).all()


@pytest.mark.parametrize("kind", ["history", "extra_factor", "missing_lag", "nan", "names"])
def test_invalid_factor_replacement_is_rejected(kind):
    design, scores = design_and_scores()
    if kind == "history":
        scores = scores.iloc[1:]
    elif kind == "extra_factor":
        design["F3_lag1"] = 0
    elif kind == "missing_lag":
        design = design.drop(columns="F1_lag8")
    elif kind == "nan":
        scores.iloc[-1, 0] = np.nan
    elif kind == "names":
        scores = scores.rename(columns={"F1": "Factor1"})
    with pytest.raises(ValueError):
        replace_factor_lags(design, scores)


def test_score_geometry_distinguishes_signs_from_different_subspaces():
    values = np.random.default_rng(13).normal(size=(20, 8))
    basis = np.linalg.qr(values - values.mean(axis=0))[0]
    signed = score_geometry(basis[:, :5], basis[:, :5] * [-1, 1, -1, 1, -1])
    np.testing.assert_allclose(signed["training_score_subspace_principal_cosines"]["5"], 1)
    np.testing.assert_allclose(
        signed["absolute_training_score_correlations_all_by_subset"], np.eye(5), atol=1e-12
    )
    other = score_geometry(basis[:, :2], basis[:, 2:4])
    np.testing.assert_allclose(
        other["training_score_subspace_principal_cosines"]["2"], 0, atol=1e-12
    )


@pytest.mark.parametrize("other", [np.ones((12, 2)), np.full((12, 2), np.nan), np.ones((10, 3))])
def test_score_geometry_rejects_invalid_inputs(other):
    with pytest.raises(ValueError):
        score_geometry(np.random.default_rng(4).normal(size=(12, 2)), other)
