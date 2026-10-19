"""Actual sklearn fits on synthetic data: contracts, not macro performance evidence."""

import numpy as np
import pytest

from jev_factor.plain_forest import PlainBlockForest, block_subsample


def data():
    rng = np.random.default_rng(782)
    x = rng.normal(size=(160, 12))
    y = 0.3 * x[:, 0] + x[:, 1] ** 2 + rng.normal(0, 0.1, len(x))
    return x, y


def test_random_group_law_quantile_and_whole_group_membership():
    sample = block_subsample(173, np.random.default_rng(101))
    assert len(sample.group_weights) == 173 // 8
    assert np.all(np.diff(sample.groups) >= 0)
    expected = np.flatnonzero(
        sample.group_weights[sample.groups]
        > np.quantile(sample.group_weights[sample.groups], 0.25, method="linear")
    )
    np.testing.assert_array_equal(sample.rows, expected)
    assert len(np.unique(sample.rows)) == len(sample.rows)
    for group in np.unique(sample.groups):
        rows = np.flatnonzero(sample.groups == group)
        assert len(np.intersect1d(rows, sample.rows)) in (0, len(rows))
    counts = np.bincount(sample.groups)
    assert not np.all(counts == 8)
    assert len(sample.rows) / 173 != 0.75
    with pytest.raises(ValueError):
        sample.rows[0] = 0


@pytest.mark.parametrize(
    "options", [{"n": 8}, {"n": True}, {"block_size": 0}, {"rate": 1}, {"rate": np.nan}]
)
def test_invalid_block_sampling_options_are_rejected(options):
    values = {"n": 160, "rng": np.random.default_rng(1), **options}
    with pytest.raises(ValueError):
        block_subsample(**values)


def test_empty_strict_cutoff_draw_fails_without_hidden_redraw():
    # One observed group in the smallest allowed setup makes all weights equal.
    for seed in range(20):
        rng = np.random.default_rng(seed)
        groups = np.sort(rng.integers(2, size=2))
        if groups[0] == groups[1]:
            with pytest.raises(ValueError, match="no silent redraw"):
                block_subsample(2, np.random.default_rng(seed), block_size=1)
            break
    else:
        raise AssertionError("Synthetic empty-draw edge case was not found")


def test_reproducible_plain_trees_use_sampled_leaf_means_and_uniform_averaging():
    x, y = data()
    original_x, original_y = x.copy(), y.copy()
    forest = PlainBlockForest(trees=5).fit(x, y)
    repeated = PlainBlockForest(trees=5).fit(x, y)
    assert forest.candidates_ == 4 and len(forest.models_) == 5
    assert forest.leaf_mean_error(x, y) < 1e-12
    np.testing.assert_array_equal(forest.predict(x[:8]), repeated.predict(x[:8]))
    np.testing.assert_array_equal(
        forest.predict(x[:8]), forest.tree_predictions(x[:8]).mean(axis=0)
    )
    np.testing.assert_array_equal(x, original_x)
    np.testing.assert_array_equal(y, original_y)
    for tree in forest.models_:
        settings = tree.get_params()
        assert settings["criterion"] == "squared_error"
        assert settings["min_samples_split"] == 10 and settings["min_samples_leaf"] == 1
        assert settings["max_depth"] is None and settings["ccp_alpha"] == 0


def test_unselected_rows_do_not_enter_terminal_mean_refits():
    x, y = data()
    forest = PlainBlockForest(trees=1, min_parent=1000).fit(x, y)
    sample = forest.samples_[0].rows
    omitted = np.setdiff1d(np.arange(len(y)), sample)
    assert len(omitted) > 0
    changed = y.copy()
    changed[omitted] = 1e9
    alternate = PlainBlockForest(trees=1, min_parent=1000).fit(x, changed)
    np.testing.assert_allclose(forest.predict(x[:8]), y[sample].mean(), atol=1e-12)
    np.testing.assert_array_equal(forest.predict(x[:8]), alternate.predict(x[:8]))
    assert abs(y.mean() - changed.mean()) > 1e6


def test_future_rows_are_predicted_independently_and_never_refit_the_forest():
    x, y = data()
    forest = PlainBlockForest(trees=5).fit(x[:140], y[:140])
    before = forest.predict(x[140:])
    query = x[140:].copy()
    query[1:] *= 1e5
    after = forest.predict(query)
    np.testing.assert_array_equal(before[:1], after[:1])
    np.testing.assert_array_equal(before, forest.predict(x[140:]))


@pytest.mark.parametrize(
    "options",
    [
        {"trees": 0},
        {"trees": True},
        {"seed": -1},
        {"block_size": 0},
        {"rate": 0},
        {"rate": 1},
        {"feature_fraction": 0},
        {"feature_fraction": True},
        {"feature_fraction": 2},
        {"min_parent": 1},
        {"min_leaf": 0},
    ],
)
def test_invalid_plain_forest_settings_are_rejected(options):
    with pytest.raises(ValueError):
        PlainBlockForest(**options)


@pytest.mark.parametrize("problem", ["shape", "target", "nonfinite", "few_rows", "few_features"])
def test_invalid_training_input_is_rejected(problem):
    x, y = data()
    if problem == "shape":
        x = x[0]
    elif problem == "target":
        y = y[:-1]
    elif problem == "nonfinite":
        x[0, 0] = np.nan
    elif problem == "few_rows":
        x, y = x[:10], y[:10]
    else:
        x = x[:, :1]
    with pytest.raises(ValueError):
        PlainBlockForest(trees=2).fit(x, y)


def test_failed_refit_cannot_leave_a_previous_forest_usable():
    x, y = data()
    forest = PlainBlockForest(trees=2).fit(x, y)
    with pytest.raises(ValueError):
        forest.fit(x, y[:-1])
    with pytest.raises(ValueError, match="successfully fitted"):
        forest.predict(x)


@pytest.mark.parametrize("problem", ["unfitted", "wrong_columns", "nonfinite", "empty"])
def test_invalid_forecast_input_is_rejected(problem):
    x, y = data()
    forest = PlainBlockForest(trees=2)
    if problem != "unfitted":
        forest.fit(x, y)
    if problem == "wrong_columns":
        x = x[:, :-1]
    elif problem == "nonfinite":
        x[0, 0] = np.inf
    elif problem == "empty":
        x = x[:0]
    with pytest.raises(ValueError):
        forest.predict(x)
