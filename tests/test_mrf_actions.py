"""Algebraic selector contracts only: no hosted or macro forecasting results."""

from dataclasses import asdict

import numpy as np
import pytest

from jev_factor.mrf_actions import (
    ACTION_MULTIPLIERS,
    EQUATION_TERMS,
    IDENTITY_ACTION,
    ForestContributions,
    expected_multipliers,
    joint_candidates,
    validate_joint_probabilities,
    weighted_forecast,
)


def one_hot(action):
    return {name: float(name == action) for name in ACTION_MULTIPLIERS}


def test_grid_has_25_stable_joint_actions_and_no_outcomes():
    parts = ForestContributions(3, 2, -1)
    actions = joint_candidates(parts)
    assert len(actions) == 25
    assert len({a.action_id for a in actions}) == 25
    assert ACTION_MULTIPLIERS[IDENTITY_ACTION] == (1.0, 1.0)
    for action in actions:
        assert action.forecast == pytest.approx(3 + 2 * action.multiplier1 - action.multiplier2)
        assert set(asdict(action)) == {"action_id", "multiplier1", "multiplier2", "forecast"}


def test_identity_and_uniform_recover_unmodified_forest():
    parts = ForestContributions(0.01, -0.04, 0.02)
    assert weighted_forecast(parts, one_hot(IDENTITY_ACTION)) == pytest.approx(parts.baseline)
    uniform = dict.fromkeys(ACTION_MULTIPLIERS, 1 / 25)
    assert weighted_forecast(parts, uniform) == pytest.approx(parts.baseline)
    assert expected_multipliers(uniform) == pytest.approx((1, 1))


def test_suppression_and_strengthening_preserve_fixed_terms_and_factor_signs():
    parts = ForestContributions(5, 2, -3)
    assert weighted_forecast(parts, one_hot("a00")) == 5  # remove both factors
    assert weighted_forecast(parts, one_hot("a24")) == 3  # double both
    assert weighted_forecast(parts, one_hot("a20")) == 9  # double first, remove second


def test_point_forecast_depends_only_on_marginal_mean_multipliers():
    parts = ForestContributions(0.2, -0.3, 0.7)
    rng = np.random.default_rng(44)
    values = rng.dirichlet(np.ones(25))
    probabilities = dict(zip(ACTION_MULTIPLIERS, values, strict=True))
    a, b = expected_multipliers(probabilities)
    assert weighted_forecast(parts, probabilities) == pytest.approx(
        parts.fixed + a * parts.factor1 + b * parts.factor2
    )
    # Different dependence, identical margins: same point forecast, not same posterior.
    diagonal = dict.fromkeys(ACTION_MULTIPLIERS, 0.0)
    diagonal.update(a00=0.5, a24=0.5)
    antidiagonal = dict.fromkeys(ACTION_MULTIPLIERS, 0.0)
    antidiagonal.update(a04=0.5, a20=0.5)
    assert diagonal != antidiagonal
    assert weighted_forecast(parts, diagonal) == pytest.approx(
        weighted_forecast(parts, antidiagonal)
    )


def test_coefficient_input_uses_products_and_is_basis_sign_invariant():
    coefficients = dict(zip(EQUATION_TERMS, (0.3, -0.1, 0.5, -0.2), strict=True))
    predictors = dict(zip(EQUATION_TERMS, (2.0, 1.0, -4.0, 3.0), strict=True))
    parts = ForestContributions.from_coefficients(0.8, coefficients, predictors)
    assert (parts.fixed, parts.factor1, parts.factor2) == pytest.approx((1.3, -2, -0.6))
    coefficients["F1_lag1"] *= -1
    predictors["F1_lag1"] *= -1
    assert ForestContributions.from_coefficients(0.8, coefficients, predictors) == parts


def test_rejects_extra_target_or_missing_equation_terms():
    terms = dict.fromkeys(EQUATION_TERMS, 1.0)
    with pytest.raises(ValueError, match="exactly"):
        ForestContributions.from_coefficients(0, terms, {**terms, "actual": 100})
    with pytest.raises(ValueError, match="exactly"):
        ForestContributions.from_coefficients(0, {"y_lag1": 1}, terms)


def test_zero_factor_does_not_remove_actions_or_invent_recoverable_signal():
    parts = ForestContributions(3, 0, 0)
    assert len(joint_candidates(parts)) == 25
    assert {a.forecast for a in joint_candidates(parts)} == {3.0}


def test_reversed_distribution_order_does_not_change_action_meaning():
    parts = ForestContributions(1, 2, -1)
    probabilities = one_hot("a20")
    reverse = dict(reversed(list(probabilities.items())))
    assert weighted_forecast(parts, reverse) == weighted_forecast(parts, probabilities)


@pytest.mark.parametrize("problem", ["missing", "extra", "negative", "nan", "too_large", "mass"])
def test_invalid_distribution_is_not_repaired_or_used_as_fallback(problem):
    probabilities = dict.fromkeys(ACTION_MULTIPLIERS, 1 / 25)
    if problem == "missing":
        probabilities.pop("a00")
    elif problem == "extra":
        probabilities["unknown"] = 0
    else:
        probabilities["a00"] = {"negative": -0.1, "nan": np.nan, "too_large": 2, "mass": 0.3}[
            problem
        ]
    with pytest.raises(ValueError):
        validate_joint_probabilities(probabilities)
    with pytest.raises(ValueError):
        weighted_forecast(ForestContributions(0, 1, 2), probabilities)


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf, "invalid"])
def test_nonfinite_or_nonnumeric_contributions_are_rejected(value):
    with pytest.raises(ValueError):
        ForestContributions(0, value, 1)


def test_overflowing_forecasts_are_rejected():
    with pytest.raises(ValueError, match="overflow"):
        ForestContributions(1e308, 1e308, 0)
    # A finite baseline can still have a nonfinite strengthened candidate.
    with pytest.raises(ValueError):
        joint_candidates(ForestContributions(0, 1e308, -1e308))
