"""Shared two-factor action algebra, separate from the legacy three-label gate.

No targets, history, model calls or calibration claims belong in this layer.
Callers must construct genuinely past-only evidence before querying a selector.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import product
from math import fsum, isclose, isfinite
from types import MappingProxyType

MULTIPLIERS = (0.0, 0.5, 1.0, 1.5, 2.0)
ACTION_MULTIPLIERS = MappingProxyType(
    {f"a{i:02d}": pair for i, pair in enumerate(product(MULTIPLIERS, repeat=2))}
)
IDENTITY_ACTION = "a12"
EQUATION_TERMS = ("y_lag1", "y_lag2", "F1_lag1", "F2_lag1")


def _finite(value: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Forecast inputs must be finite numbers") from exc
    if not isfinite(result):
        raise ValueError("Forecast inputs must be finite numbers")
    return result


def _sum(values) -> float:
    try:
        return _finite(fsum(values))
    except OverflowError as exc:
        raise ValueError("Forecast arithmetic overflow") from exc


@dataclass(frozen=True)
class ForestContributions:
    """Intercept plus AR terms stays fixed; the two factor contributions vary."""

    fixed: float
    factor1: float
    factor2: float

    def __post_init__(self):
        for name in ("fixed", "factor1", "factor2"):
            object.__setattr__(self, name, _finite(getattr(self, name)))
        _finite(self.baseline)

    @property
    def baseline(self) -> float:
        return _sum((self.fixed, self.factor1, self.factor2))

    @classmethod
    def from_coefficients(
        cls,
        intercept: float,
        coefficients: Mapping[str, float],
        predictors: Mapping[str, float],
    ) -> ForestContributions:
        """Accept only the four equation terms, never a state/target blob.

        Inputs must share one basis and units, e.g. saved original-unit R
        coefficients and their corresponding original-unit matrix row.
        """
        if set(coefficients) != set(EQUATION_TERMS) or set(predictors) != set(EQUATION_TERMS):
            raise ValueError("Expected exactly the four FA-ARRF equation terms")
        terms = {
            name: _finite(_finite(coefficients[name]) * _finite(predictors[name]))
            for name in EQUATION_TERMS
        }
        return cls(
            _sum((_finite(intercept), terms["y_lag1"], terms["y_lag2"])),
            terms["F1_lag1"],
            terms["F2_lag1"],
        )


@dataclass(frozen=True)
class JointCandidate:
    action_id: str
    multiplier1: float
    multiplier2: float
    forecast: float


def joint_candidates(parts: ForestContributions) -> tuple[JointCandidate, ...]:
    """Stable IDs retain their meaning even if a prompt reverses display order.

    Duplicate numerical forecasts remain distinct actions, including when a
    factor contribution is zero. No test outcome is used to collapse the menu.
    """
    return tuple(
        JointCandidate(name, a, b, _sum((parts.fixed, a * parts.factor1, b * parts.factor2)))
        for name, (a, b) in ACTION_MULTIPLIERS.items()
    )


def validate_joint_probabilities(probabilities: Mapping[str, float]) -> dict[str, float]:
    if set(probabilities) != set(ACTION_MULTIPLIERS):
        raise ValueError("Return all 25 declared action IDs and no extra IDs")
    values = {name: _finite(probabilities[name]) for name in ACTION_MULTIPLIERS}
    if any(p < 0 or p > 1 for p in values.values()):
        raise ValueError("Action probabilities must be in [0, 1]")
    if not isclose(fsum(values.values()), 1.0, rel_tol=0, abs_tol=1e-8):
        raise ValueError("Action probabilities must sum to 1; no silent renormalization")
    return values


def expected_multipliers(probabilities: Mapping[str, float]) -> tuple[float, float]:
    values = validate_joint_probabilities(probabilities)
    return tuple(
        fsum(values[name] * pair[j] for name, pair in ACTION_MULTIPLIERS.items()) for j in range(2)
    )


def weighted_forecast(parts: ForestContributions, probabilities: Mapping[str, float]) -> float:
    """Decision-weighted forecast, not a posterior over economic effects."""
    values = validate_joint_probabilities(probabilities)
    return _sum(values[action.action_id] * action.forecast for action in joint_candidates(parts))
