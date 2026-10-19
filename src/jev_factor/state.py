"""Define information available at a forecast origin before any future label is read."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

PROMPT_VERSION = "factor-gate-v1"
GATE_OPTIONS = {
    "suppress": "Zero contribution gives the smallest squared forecast error.",
    "weaken": "Half the fitted contribution gives the smallest squared forecast error.",
    "retain": "The full fitted contribution gives the smallest squared forecast error.",
}
MULTIPLIERS = {"suppress": 0.0, "weaken": 0.5, "retain": 1.0}


@dataclass
class OriginData:
    train_x: np.ndarray
    train_f: np.ndarray
    train_y: np.ndarray
    current_x: np.ndarray
    current_f: np.ndarray
    feature_names: list[str]
    factor_names: list[str]
    factor_descriptions: list[str]
    known_target: float
    last_label_position: int


def prepare_origin(data, origin: int, config: dict) -> OriginData:
    """Fit imputation/scaling/PCA exclusively on eligible training feature rows.

    origin s is eligible for training only if s+h <= t-data_lag. Data lag is
    applied to predictors and target-history features as well as label availability.
    """
    horizon, lag = config["horizon"], config["data_lag"]
    if horizon < 1 or lag < 0:
        raise ValueError("horizon >= 1 and data_lag >= 0 are required")
    last = origin - horizon - lag
    if last < 24:
        raise ValueError("Not enough eligible training observations")
    # Slice before transforming so future values cannot enter pre-processing.
    X = data.X.iloc[: origin + 1].shift(lag)
    target_history = data.y.iloc[: origin + 1].shift(lag)
    X = X.assign(
        target_lag_0=target_history,
        target_lag_1=target_history.shift(1),
        target_lag_2=target_history.shift(2),
    )
    eligible = np.arange(3 + lag, last + 1)
    labels = data.y.iloc[eligible + horizon].to_numpy(dtype=float)
    eligible = eligible[np.isfinite(labels)]
    labels = labels[np.isfinite(labels)]
    # Variable eligibility is determined using this origin's training rows only.
    keep = (X.iloc[eligible].notna().mean() >= 0.8) & (X.iloc[eligible].std() > 1e-10)
    X = X.loc[:, keep]
    ar_columns = [c for c in X if c.startswith("target_lag_")]
    signal_columns = [c for c in X if c not in ar_columns]
    if not signal_columns or len(ar_columns) != 3:
        raise ValueError("Insufficient usable predictors or target history")
    imputer = SimpleImputer(strategy="median")
    train = imputer.fit_transform(X.iloc[eligible])
    current = imputer.transform(X.iloc[[origin]])
    scaler = StandardScaler().fit(train)
    train, current = scaler.transform(train), scaler.transform(current)
    signal_idx = [X.columns.get_loc(c) for c in signal_columns]
    ar_idx = [X.columns.get_loc(c) for c in ar_columns]
    n_factors = min(config["n_factors"], len(signal_idx), len(eligible))
    descriptions = []
    if config["representation"] == "pca":
        pca = PCA(n_components=n_factors, svd_solver="full").fit(train[:, signal_idx])
        train_f, current_f = (
            pca.transform(train[:, signal_idx]),
            pca.transform(current[:, signal_idx]),
        )
        # Deterministic orientation within each origin. Refit components are not
        # assumed to keep their identities between origins.
        for i, component in enumerate(pca.components_):
            top = np.argsort(np.abs(component))[-3:][::-1]
            sign = 1 if component[top[0]] >= 0 else -1
            train_f[:, i] *= sign
            current_f[:, i] *= sign
            descriptions.append(
                "PCA loading leaders: "
                + ", ".join(f"{signal_columns[j]} ({component[j] * sign:+.3f})" for j in top)
            )
        names = [f"pc_{i}" for i in range(n_factors)]
    elif config["representation"] == "observed":
        train_f, current_f = train[:, signal_idx[:n_factors]], current[:, signal_idx[:n_factors]]
        names = signal_columns[:n_factors]
        descriptions = [f"Engineered observed signal: {name}" for name in names]
    else:
        raise ValueError("representation must be observed or pca")
    return OriginData(
        np.column_stack([train[:, ar_idx], train[:, signal_idx]]),
        np.column_stack([train[:, ar_idx], train_f]),
        labels,
        np.column_stack([current[:, ar_idx], current[:, signal_idx]]),
        np.column_stack([current[:, ar_idx], current_f]),
        ar_columns + signal_columns,
        names,
        descriptions,
        float(target_history.iloc[origin]),
        int(eligible[-1] + horizon),
    )


def correlation(a: np.ndarray, b: np.ndarray) -> float:
    if np.std(a) < 1e-10 or np.std(b) < 1e-10:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def build_state(prepared: OriginData, fitted, recent_window: int, horizon: int) -> dict:
    residual = prepared.train_y - fitted.intercept_ - prepared.train_f[:, :3] @ fitted.coef_[:3]
    recent = min(recent_window, len(residual))
    factors = []
    full_forecast = float(fitted.predict(prepared.current_f)[0])
    for i, name in enumerate(prepared.factor_names):
        signal = prepared.train_f[:, i + 3]
        coefficient = float(fitted.coef_[i + 3])
        full_corr = correlation(signal, residual)
        recent_corr = correlation(signal[-recent:], residual[-recent:])
        factors.append(
            {
                "id": name,
                "description": prepared.factor_descriptions[i],
                "fitted_coefficient": coefficient,
                "current_standardized_value": float(prepared.current_f[0, i + 3]),
                "current_fitted_contribution": float(prepared.current_f[0, i + 3] * coefficient),
                "training_partial_residual_correlation": full_corr,
                "recent_partial_residual_correlation": recent_corr,
                "recent_sign_supports_fitted_coefficient": bool(recent_corr * coefficient > 0),
                "relationship_summary": (
                    "recent association opposes fitted direction"
                    if recent_corr * coefficient < 0
                    else "recent association supports fitted direction"
                ),
                "candidate_forecasts": {
                    option: full_forecast
                    - (1 - multiplier) * float(prepared.current_f[0, i + 3] * coefficient)
                    for option, multiplier in MULTIPLIERS.items()
                },
            }
        )
    return {
        "prompt_version": PROMPT_VERSION,
        "task": "Assess reliability of fitted factor contributions for forecasting.",
        "horizon_steps": horizon,
        "known_training_labels": len(prepared.train_y),
        "recent_window": recent,
        "target_recent_mean": float(prepared.train_y[-recent:].mean()),
        "target_recent_std": float(prepared.train_y[-recent:].std()),
        "target_long_run_std": float(prepared.train_y.std()),
        "full_model_forecast": full_forecast,
        "evidence_note": (
            "Correlations are training diagnostics, not out-of-sample performance "
            "or causal effects. "
            "Coefficients condition jointly on all factors and target lags."
        ),
        "factors": factors,
    }


def questions_for(state: dict, reverse_order: bool = False) -> dict:
    criteria = dict(reversed(list(GATE_OPTIONS.items()))) if reverse_order else GATE_OPTIONS
    return {
        factor["id"]: {
            "type": "choice",
            "instructions": (
                f"For factor `{factor['id']}` in state.factors, which of its three "
                "candidate_forecasts is most likely to have the smallest squared error "
                "against the future target? Other contributions stay fixed at their full-model "
                "values for this question. Use the computed evidence and factor meaning. "
                "Distribute uncertainty across suppress, weaken, retain. Break exact ties "
                "in favor of retain, then weaken. Do not recompute statistics."
            ),
            "criteria": criteria,
        }
        for factor in state["factors"]
    }
