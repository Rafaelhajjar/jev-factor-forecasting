"""Bounded reconstruction of the pinned FRED jj=2, DEMEAN=2 EM recipe.

This does not claim the unavailable MRF runner used that recipe. The completion
rank and the five state PCs are deliberately separate. Existing runs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from threadpoolctl import threadpool_limits


@dataclass
class EMFit:
    filled: np.ndarray
    standardized: np.ndarray
    mean: np.ndarray
    std: np.ndarray
    completion_basis: np.ndarray
    rank_history: list[int]
    errors: list[float | None]
    iterations: int
    converged: bool
    at_iteration_cap: bool
    stopping_reason: str


def _rank(z: np.ndarray, singular: np.ndarray, kmax: int) -> tuple[int, np.ndarray]:
    t, n = z.shape
    if type(kmax) is not int or not 1 <= kmax < min(t, n):
        raise ValueError("Need an integer completion bound smaller than both dimensions")
    # Source candidate order is 1..kmax followed by zero. Tail sums avoid
    # cancellation in total-minus-explained residual sums of squares.
    tail = np.cumsum((singular**2)[::-1])[::-1]
    variance = np.array([tail[k] / (n * t) for k in range(1, kmax + 1)] + [np.mean(z**2)])
    penalty = np.r_[np.arange(1, kmax + 1) * (n + t) / (n * t) * np.log(min(n, t)), 0]
    with np.errstate(divide="ignore"):
        criteria = np.log(variance) + penalty
    best = np.flatnonzero(criteria == np.min(criteria))
    if len(best) != 1 or np.isnan(criteria).any():
        raise ValueError("The source criterion must have a unique minimum")
    return (int(best[0]) + 1 if best[0] < kmax else 0), criteria


@threadpool_limits.wrap(limits=1)
def ic2_rank(z: np.ndarray, kmax: int = 8) -> tuple[int, np.ndarray]:
    """The log-residual jj=2 formula in the pinned code, not its PC-label comment."""
    z = np.asarray(z, dtype=float)
    if z.ndim != 2 or not z.size or not np.isfinite(z).all() or np.sum(z**2) <= 0:
        raise ValueError("Expected a finite, nonzero standardized matrix")
    singular = np.linalg.svd(np.ascontiguousarray(z), compute_uv=False)
    return _rank(z, singular, kmax)


@threadpool_limits.wrap(limits=1)
def em_complete(
    x: np.ndarray, *, kmax: int = 8, max_iter: int = 50, tolerance: float = 1e-6
) -> EMFit:
    """Preserve observed cells; select rank anew after every missing-cell update.

    Only source mode DEMEAN=2/jj=2 is reconstructed, not the complete MATLAB API.
    The source's zero-reconstruction 0/0 stopping case is exposed, not relabeled
    ordinary convergence. Reaching the cap is also explicit, not silently extended.
    """
    x = np.asarray(x, dtype=float)
    if (
        x.ndim != 2
        or not x.size
        or np.isinf(x).any()
        or np.isnan(x).all(axis=0).any()
        or np.isnan(x).all(axis=1).any()
    ):
        raise ValueError("Invalid EM input or entirely missing row/column")
    if type(max_iter) is not int or max_iter < 1 or not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("Need positive iteration limit and finite tolerance")
    missing = np.isnan(x)
    filled = np.where(missing, np.nanmean(x, axis=0), x).copy()

    def step():
        mean, std = filled.mean(axis=0), filled.std(axis=0, ddof=1)
        if not np.isfinite(std).all() or (std <= 1e-12).any():
            raise ValueError("Constant or invalid series cannot be standardized")
        z = np.ascontiguousarray((filled - mean) / std)
        _, singular, vt = np.linalg.svd(z, full_matrices=False)
        rank, _ = _rank(z, singular, kmax)
        basis = vt[:rank]
        chat = (z @ basis.T) @ basis
        return mean, std, z, basis, rank, chat

    mean, std, z, basis, rank, chat = step()
    ranks, errors = [rank], [None]
    error, iteration = 999.0, 0
    while error > tolerance and iteration < max_iter:
        iteration += 1
        predicted = chat * std + mean
        filled[missing] = predicted[missing]
        previous = chat
        mean, std, z, basis, rank, chat = step()
        numerator, denominator = np.sum((chat - previous) ** 2), np.sum(previous**2)
        error = (
            float(numerator / denominator)
            if denominator > 0
            else (float("nan") if numerator == 0 else float("inf"))
        )
        ranks.append(rank)
        errors.append(error if np.isfinite(error) else None)
    if not np.array_equal(filled[~missing], x[~missing]):
        raise ValueError("Observed data changed during completion")
    converged = bool(np.isfinite(error) and error <= tolerance)
    reason = (
        "tolerance_met"
        if converged
        else "zero_reconstruction_undefined_ratio"
        if np.isnan(error)
        else "iteration_cap"
    )
    return EMFit(
        filled,
        z,
        mean,
        std,
        basis,
        ranks,
        errors,
        iteration,
        converged,
        iteration == max_iter,
        reason,
    )


class FredRecipeRepresentation:
    """Source-recipe training completion plus an explicitly separate causal extension."""

    def __init__(
        self,
        factor_rank: int = 5,
        kmax: int = 8,
        max_iter: int = 50,
        tolerance: float = 1e-6,
        outlier_iqr: float = 10,
    ):
        if (
            type(factor_rank) is not int
            or factor_rank < 1
            or not np.isfinite(outlier_iqr)
            or outlier_iqr <= 0
        ):
            raise ValueError("Need positive state factor count and outlier threshold")
        self.factor_rank, self.kmax, self.max_iter = factor_rank, kmax, max_iter
        self.tolerance, self.outlier_iqr = tolerance, outlier_iqr

    @threadpool_limits.wrap(limits=1)
    def fit(self, frame: pd.DataFrame):
        if (
            not frame.index.is_unique
            or not frame.index.is_monotonic_increasing
            or not frame.columns.is_unique
            or min(frame.shape) <= self.factor_rank
        ):
            raise ValueError("Invalid training layout for factor extraction")
        values = frame.to_numpy(dtype=float)
        if np.isinf(values).any() or np.isnan(values).all(axis=0).any():
            raise ValueError("Invalid or entirely missing training series")
        self.columns, self.training_index = frame.columns.copy(), frame.index.copy()
        self.median = np.nanmedian(values, axis=0)
        q = np.nanpercentile(values, [25, 75], axis=0, method="hazen")
        self.iqr = q[1] - q[0]
        self.cleaned_training = self._clean(values)
        self.training_outliers = int(np.sum(np.isfinite(values) & np.isnan(self.cleaned_training)))
        self.em = em_complete(
            self.cleaned_training, kmax=self.kmax, max_iter=self.max_iter, tolerance=self.tolerance
        )
        self.pca = PCA(n_components=self.factor_rank, svd_solver="full").fit(self.em.standardized)
        return self

    def _clean(self, values):
        x = np.asarray(values, dtype=float).copy()
        x[np.abs(x - self.median) > self.outlier_iqr * self.iqr] = np.nan
        return x

    @threadpool_limits.wrap(limits=1)
    def transform(self, frame: pd.DataFrame):
        """Future rows use frozen moments/basis independently: this is our extension.

        The supplied FRED script does not define this out-of-sample procedure.
        """
        if not frame.columns.equals(self.columns) or not frame.index.is_unique:
            raise ValueError("Factor series/order or row identity differs")
        if np.isinf(frame.to_numpy(dtype=float)).any():
            raise ValueError("Infinite predictor values")
        z = (self._clean(frame.to_numpy(dtype=float)) - self.em.mean) / self.em.std
        basis = self.em.completion_basis
        for row in z:
            present = np.isfinite(row)
            if not present.any():
                raise ValueError("No contemporaneous observed predictors")
            if not present.all():
                if len(basis):
                    score = np.linalg.lstsq(basis[:, present].T, row[present], rcond=None)[0]
                    row[~present] = (score @ basis)[~present]
                else:
                    row[~present] = 0
        common = frame.index.intersection(self.training_index)
        z[frame.index.get_indexer(common)] = self.em.standardized[
            self.training_index.get_indexer(common)
        ]
        factors = self.pca.transform(z)
        return (
            pd.DataFrame(z, index=frame.index, columns=self.columns),
            pd.DataFrame(
                factors, index=frame.index, columns=[f"F{k + 1}" for k in range(self.factor_rank)]
            ),
        )
