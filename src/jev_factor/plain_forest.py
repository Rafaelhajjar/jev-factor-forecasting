"""Plain CART control building block, not the missing author's RF-MAF runner.

The sampling law ports the pinned MRF's random-group/quantile scheme. NumPy
and sklearn are separate backend choices, not historical R seed equivalence.
No MRF ridge/RW prior, jitter, rank penalty or full-sample leaf refit is used.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.tree import DecisionTreeRegressor
from threadpoolctl import threadpool_limits


@dataclass(frozen=True)
class BlockSample:
    groups: np.ndarray
    group_weights: np.ndarray
    rows: np.ndarray


def block_subsample(
    n: int, rng: np.random.Generator, *, block_size: int = 8, rate: float = 0.75
) -> BlockSample:
    """Port the native resampling.opt=2 law, not fixed length-eight blocks.

    Groups are contiguous but randomly sized. Retention uses a strict cutoff
    at the row-weight quantile (R type 7 / NumPy linear), so realized retained
    fractions need not equal the nominal rate. Empty draws fail explicitly.
    """
    if (
        type(n) is not int
        or type(block_size) is not int
        or block_size < 1
        or n < 2 * block_size
        or not np.isfinite(rate)
        or not 0 < rate < 1
        or not isinstance(rng, np.random.Generator)
    ):
        raise ValueError(
            "Need at least two groups, a generator and a rate strictly between 0 and 1"
        )
    count = n // block_size
    groups = np.sort(rng.integers(count, size=n))
    weights = rng.exponential(size=count) + 0.1
    row_weights = weights[groups]
    rows = np.flatnonzero(row_weights > np.quantile(row_weights, 1 - rate, method="linear"))
    if not len(rows):
        raise ValueError("Native-law draw retained no rows; no silent redraw is permitted")
    for values in (groups, weights, rows):
        values.flags.writeable = False
    return BlockSample(groups, weights, rows)


class PlainBlockForest:
    """Mean of plain squared-error CART trees on independently drawn block subsets.

    Default settings are explicit reconstruction choices for a future control,
    not recovered per-table settings. sklearn converts features to float32;
    its valid-split fallback may inspect more than the max_features setting.
    Fit takes training data only; predict has no target argument.
    """

    def __init__(
        self,
        *,
        trees: int = 100,
        seed: int = 101,
        block_size: int = 8,
        rate: float = 0.75,
        feature_fraction: float = 1 / 3,
        min_parent: int = 10,
        min_leaf: int = 1,
    ):
        if (
            type(trees) is not int
            or trees < 1
            or type(seed) is not int
            or seed < 0
            or type(block_size) is not int
            or block_size < 1
            or not np.isfinite(rate)
            or not 0 < rate < 1
            or not np.isfinite(feature_fraction)
            or isinstance(feature_fraction, bool)
            or not 0 < feature_fraction <= 1
            or type(min_parent) is not int
            or min_parent < 2
            or type(min_leaf) is not int
            or min_leaf < 1
        ):
            raise ValueError("Invalid plain-forest reconstruction settings")
        self.trees, self.seed, self.block_size = trees, seed, block_size
        self.rate, self.feature_fraction = rate, feature_fraction
        self.min_parent, self.min_leaf = min_parent, min_leaf
        self.fitted_ = False

    @threadpool_limits.wrap(limits=1)
    def fit(self, x: np.ndarray, y: np.ndarray):
        self.fitted_ = False
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        if (
            x.ndim != 2
            or y.ndim != 1
            or len(x) != len(y)
            or not x.size
            or not np.isfinite(x).all()
            or not np.isfinite(y).all()
            or len(x) < 2 * self.block_size
            or x.shape[1] * self.feature_fraction < 1
        ):
            raise ValueError("Expected finite training predictors/targets and enough rows/features")
        self.n_features_in_ = x.shape[1]
        self.candidates_ = round(self.n_features_in_ * self.feature_fraction)
        rng = np.random.default_rng(self.seed)
        models, samples, seeds = [], [], []
        for _ in range(self.trees):
            sample = block_subsample(len(y), rng, block_size=self.block_size, rate=self.rate)
            tree_seed = int(rng.integers(np.iinfo(np.int32).max))
            tree = DecisionTreeRegressor(
                criterion="squared_error",
                splitter="best",
                max_depth=None,
                min_samples_split=self.min_parent,
                min_samples_leaf=self.min_leaf,
                max_features=self.candidates_,
                random_state=tree_seed,
                ccp_alpha=0.0,
            ).fit(x[sample.rows], y[sample.rows])
            models.append(tree)
            samples.append(sample)
            seeds.append(tree_seed)
        self.models_, self.samples_, self.tree_seeds_ = models, samples, seeds
        self.fitted_ = True
        return self

    @threadpool_limits.wrap(limits=1)
    def tree_predictions(self, x: np.ndarray) -> np.ndarray:
        if not self.fitted_:
            raise ValueError("Plain forest has not been successfully fitted")
        x = np.asarray(x, dtype=float)
        if (
            x.ndim != 2
            or not len(x)
            or x.shape[1] != self.n_features_in_
            or not np.isfinite(x).all()
        ):
            raise ValueError("Expected finite forecast rows with the original feature count")
        return np.stack([tree.predict(x) for tree in self.models_])

    def predict(self, x: np.ndarray) -> np.ndarray:
        return self.tree_predictions(x).mean(axis=0)

    def leaf_mean_error(self, x: np.ndarray, y: np.ndarray) -> float:
        """Audit sampled-leaf means independently of tree_.value storage."""
        if not self.fitted_:
            raise ValueError("Plain forest has not been successfully fitted")
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        if (
            x.ndim != 2
            or x.shape[1] != self.n_features_in_
            or y.shape != (len(x),)
            or not np.isfinite(x).all()
            or not np.isfinite(y).all()
        ):
            raise ValueError("Expected the original finite training data for leaf checks")
        maximum = 0.0
        for tree, sample in zip(self.models_, self.samples_, strict=True):
            if sample.groups.shape != (len(y),):
                raise ValueError("Training row count differs from saved sampling provenance")
            rows = sample.rows
            leaves = tree.apply(x[rows])
            predicted = tree.predict(x[rows])
            expected = np.empty(len(rows))
            for leaf in np.unique(leaves):
                mask = leaves == leaf
                expected[mask] = y[rows[mask]].mean()
            maximum = max(maximum, float(np.max(np.abs(predicted - expected))))
        return maximum
