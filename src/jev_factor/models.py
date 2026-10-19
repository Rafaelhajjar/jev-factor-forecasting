"""Conventional forecast baselines operating on the same eligible information."""

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge


def fit_factor(prepared, alpha: float) -> Ridge:
    return Ridge(alpha=alpha).fit(prepared.train_f, prepared.train_y)


def kalman_forecast(X: np.ndarray, y: np.ndarray, current: np.ndarray) -> float:
    """Random-walk coefficient filter; a dynamic regression, not a latent-state DFM.

    Q/R are development defaults, not estimated from test outcomes. The factor
    basis is fixed inside each origin's sequential pass, then refit next origin.
    """
    design = np.column_stack([np.ones(len(X)), X])
    state = np.zeros(design.shape[1])
    covariance = np.eye(len(state)) * 10
    process = np.eye(len(state)) * 0.001
    noise = max(float(np.var(y) * 0.1), 1e-6)
    for row, target in zip(design, y, strict=True):
        covariance = covariance + process
        gain = covariance @ row / (row @ covariance @ row + noise)
        state += gain * (target - row @ state)
        # Joseph form maintains a positive semidefinite covariance numerically.
        update = np.eye(len(state)) - np.outer(gain, row)
        covariance = update @ covariance @ update.T + noise * np.outer(gain, gain)
    return float(np.r_[1.0, current[0]] @ state)


def conventional(method: str, prepared, fitted: Ridge, config: dict, seed: int) -> float:
    if method == "zero":
        return 0.0
    if method == "persistence":
        return prepared.known_target
    if method == "ar":
        model = Ridge(alpha=config["ridge_alpha"]).fit(prepared.train_f[:, :3], prepared.train_y)
        return float(model.predict(prepared.current_f[:, :3])[0])
    if method == "ridge":
        model = Ridge(alpha=config["ridge_alpha"]).fit(prepared.train_x, prepared.train_y)
        return float(model.predict(prepared.current_x)[0])
    if method == "factor_static":
        return float(fitted.predict(prepared.current_f)[0])
    if method == "factor_rolling":
        window = config["window"]
        model = Ridge(alpha=config["ridge_alpha"]).fit(
            prepared.train_f[-window:], prepared.train_y[-window:]
        )
        return float(model.predict(prepared.current_f)[0])
    if method == "factor_rls":
        # Exponentially weighted least squares in the current factor basis.
        weights = 0.98 ** np.arange(len(prepared.train_y) - 1, -1, -1)
        model = Ridge(alpha=config["ridge_alpha"]).fit(
            prepared.train_f, prepared.train_y, sample_weight=weights
        )
        return float(model.predict(prepared.current_f)[0])
    if method == "factor_kalman":
        return kalman_forecast(prepared.train_f, prepared.train_y, prepared.current_f)
    if method == "tree":
        model = HistGradientBoostingRegressor(
            max_iter=60, max_leaf_nodes=7, l2_regularization=10, random_state=seed
        ).fit(prepared.train_x, prepared.train_y)
        return float(model.predict(prepared.current_x)[0])
    raise ValueError(f"Unknown forecast method: {method}")
