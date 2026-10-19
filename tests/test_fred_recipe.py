"""Source-recipe algebra and timing contracts, not new forecasting results."""

import numpy as np
import pandas as pd
import pytest

from jev_factor.fred_recipe import FredRecipeRepresentation, em_complete, ic2_rank
from jev_factor.fred_recipe_audit import verify_code_archive


def synthetic_panel():
    rng = np.random.default_rng(821)
    factors = rng.normal(size=(100, 2))
    values = factors @ rng.normal(size=(2, 12)) + rng.normal(0, 0.15, (100, 12))
    values[rng.random(values.shape) < 0.12] = np.nan
    return pd.DataFrame(
        values,
        index=pd.period_range("1960Q1", periods=100, freq="Q"),
        columns=[f"X{k}" for k in range(12)],
    )


def test_criterion_can_choose_zero_or_two_from_training_data():
    rng = np.random.default_rng(477)
    noise = rng.normal(size=(400, 50))
    z = (noise - noise.mean(axis=0)) / noise.std(axis=0, ddof=1)
    rank, criteria = ic2_rank(z)
    assert rank == 0 and len(criteria) == 9
    # Balanced signal strengths: arbitrary heteroskedastic noise can make this
    # criterion select more than the known latent count in a finite sample.
    angles = np.linspace(0, 2 * np.pi, 50, endpoint=False)
    loadings = np.vstack([np.cos(angles), np.sin(angles)])
    values = rng.normal(size=(400, 2)) @ loadings + 0.1 * noise
    z = (values - values.mean(axis=0)) / values.std(axis=0, ddof=1)
    rank, criteria = ic2_rank(z)
    assert rank == 2
    _, _, vt = np.linalg.svd(z, full_matrices=False)
    t, n = z.shape
    manual = [
        np.log(np.mean((z - z @ vt[:k].T @ vt[:k]) ** 2))
        + k * (n + t) / (n * t) * np.log(min(n, t))
        for k in range(1, 9)
    ]
    manual.append(np.log(np.mean(z**2)))
    np.testing.assert_allclose(criteria, manual, atol=1e-12)


def test_each_iteration_preserves_observed_cells_and_reports_its_rank():
    x = synthetic_panel().to_numpy()
    before = x.copy()
    fit = em_complete(x)
    observed = np.isfinite(x)
    np.testing.assert_array_equal(fit.filled[observed], x[observed])
    np.testing.assert_array_equal(x, before)
    assert np.isfinite(fit.filled).all() and np.isfinite(fit.standardized).all()
    assert len(fit.rank_history) == len(fit.errors) == fit.iterations + 1
    assert all(0 <= k <= 8 for k in fit.rank_history)
    np.testing.assert_allclose(fit.standardized.mean(axis=0), 0, atol=1e-12)
    np.testing.assert_allclose(fit.standardized.std(axis=0, ddof=1), 1, atol=1e-12)


def test_cap_is_exposed_not_silently_extended():
    fit = em_complete(synthetic_panel().to_numpy(), max_iter=1)
    assert fit.iterations == 1 and fit.at_iteration_cap and not fit.converged
    assert fit.stopping_reason == "iteration_cap"


def test_zero_rank_source_nan_ratio_is_not_called_normal_convergence():
    x = np.random.default_rng(61).normal(size=(400, 40))
    x[0, 0] = np.nan
    fit = em_complete(x)
    assert fit.rank_history == [0, 0]
    assert fit.iterations == 1 and fit.errors == [None, None]
    assert not fit.converged and not fit.at_iteration_cap
    assert fit.stopping_reason == "zero_reconstruction_undefined_ratio"
    np.testing.assert_allclose(fit.filled[0, 0], np.nanmean(x[:, 0]), atol=1e-14)


@pytest.mark.parametrize(
    "problem", ["shape", "row", "column", "constant", "inf", "rank", "iterations", "tolerance"]
)
def test_invalid_completion_input_is_rejected(problem):
    x = synthetic_panel().to_numpy()
    options = {}
    if problem == "shape":
        x = x[0]
    elif problem == "row":
        x[0, :] = np.nan
    elif problem == "column":
        x[:, 0] = np.nan
    elif problem == "constant":
        x[:, 0] = 1
    elif problem == "inf":
        x[0, 0] = np.inf
    elif problem == "rank":
        options["kmax"] = 12
    elif problem == "iterations":
        options["max_iter"] = 0
    else:
        options["tolerance"] = np.nan
    with pytest.raises(ValueError):
        em_complete(x, **options)


def test_representation_keeps_five_state_pcs_separate_from_completion_rank():
    frame = synthetic_panel()
    fitted = FredRecipeRepresentation().fit(frame.iloc[:80])
    z, scores = fitted.transform(frame)
    assert list(scores) == [f"F{k}" for k in range(1, 6)]
    assert z.shape == frame.shape and np.isfinite(z.to_numpy()).all()
    np.testing.assert_array_equal(z.iloc[:80], fitted.em.standardized)
    assert len(fitted.em.completion_basis) == fitted.em.rank_history[-1]


def test_later_predictor_rows_cannot_change_an_earlier_forecast_row_or_loadings():
    frame = synthetic_panel()
    fitted = FredRecipeRepresentation().fit(frame.iloc[:80])
    _, original = fitted.transform(frame)
    basis = fitted.pca.components_.copy()
    changed = frame.copy()
    changed.iloc[81:, :2] *= 10000
    _, altered = fitted.transform(changed)
    np.testing.assert_array_equal(original.iloc[:81], altered.iloc[:81])
    np.testing.assert_array_equal(basis, fitted.pca.components_)


def test_outlier_thresholds_are_fitted_on_past_only_and_observed_cells_are_not_changed():
    frame = synthetic_panel()
    frame.iloc[0, 0] = 1e8
    fitted = FredRecipeRepresentation().fit(frame.iloc[:80])
    assert np.isnan(fitted.cleaned_training[0, 0]) and fitted.training_outliers >= 1
    known = np.isfinite(fitted.cleaned_training)
    np.testing.assert_array_equal(fitted.em.filled[known], fitted.cleaned_training[known])


@pytest.mark.parametrize("problem", ["order", "all_missing", "infinite", "duplicate"])
def test_invalid_queries_are_rejected(problem):
    frame = synthetic_panel()
    fitted = FredRecipeRepresentation().fit(frame.iloc[:80])
    query = frame.iloc[80:].copy()
    if problem == "order":
        query = query.iloc[:, ::-1]
    elif problem == "all_missing":
        query.iloc[0] = np.nan
    elif problem == "infinite":
        query.iloc[0, 0] = np.inf
    else:
        query = pd.concat([query, query.iloc[:1]])
    with pytest.raises(ValueError):
        fitted.transform(query)


def test_uninspected_code_archive_cannot_claim_source_provenance(tmp_path):
    path = tmp_path / "not-the-source.zip"
    path.write_bytes(b"synthetic invalid archive contract")
    with pytest.raises(ValueError, match="checksum"):
        verify_code_archive(path)
