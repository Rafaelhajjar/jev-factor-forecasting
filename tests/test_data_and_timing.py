import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor.data import synthetic, transform
from jev_factor.experiment import run
from jev_factor.models import fit_factor
from jev_factor.state import build_state, prepare_origin


def configuration():
    return json.loads(Path("configs/synthetic.json").read_text())


@pytest.mark.parametrize(
    "code,expected",
    [
        (1, [1, 2, 4, 8]),
        (2, [np.nan, 1, 2, 4]),
        (3, [np.nan, np.nan, 1, 2]),
        (4, [0, np.log(2), np.log(4), np.log(8)]),
        (5, [np.nan, np.log(2), np.log(2), np.log(2)]),
        (6, [np.nan, np.nan, 0, 0]),
        (7, [np.nan, np.nan, 0, 0]),
    ],
)
def test_fred_transforms(code, expected):
    np.testing.assert_allclose(
        transform(pd.Series([1.0, 2.0, 4.0, 8.0]), code), expected, atol=1e-12, equal_nan=True
    )


def test_transform_does_not_bridge_missing_values():
    values = transform(pd.Series([1.0, 2.0, np.nan, 8.0, 16.0]), 7)
    assert values.iloc[2:5].isna().all()


def test_synthetic_is_reproducible():
    first, second = synthetic(42), synthetic(42)
    pd.testing.assert_frame_equal(first.X, second.X)
    pd.testing.assert_series_equal(first.y, second.y)
    assert "regime" not in first.X
    assert not first.y.equals(synthetic(7).y)


@pytest.mark.parametrize("representation", ["observed", "pca"])
@pytest.mark.parametrize("horizon,lag", [(1, 0), (3, 1), (12, 2)])
def test_future_changes_cannot_change_state(representation, horizon, lag):
    config = {
        **configuration(),
        "representation": representation,
        "horizon": horizon,
        "data_lag": lag,
    }
    first, changed = synthetic(7), synthetic(7)
    origin = 250
    # Even values already present in the retrospective file are unavailable
    # if they are more recent than the declared information boundary.
    changed.X.iloc[origin - lag + 1 :] = 1e8
    changed.y.iloc[origin - lag + 1 :] = -1e8
    before = prepare_origin(first, origin, config)
    after = prepare_origin(changed, origin, config)
    np.testing.assert_allclose(before.train_x, after.train_x)
    np.testing.assert_allclose(before.current_f, after.current_f)
    np.testing.assert_allclose(before.train_y, after.train_y)
    assert before.last_label_position <= origin - lag
    state_before = build_state(before, fit_factor(before, 10), 48, horizon)
    state_after = build_state(after, fit_factor(after, 10), 48, horizon)
    assert state_before == state_after


def test_training_label_end_includes_horizon_and_lag():
    data = synthetic()
    config = {**configuration(), "horizon": 3, "data_lag": 2}
    prepared = prepare_origin(data, 100, config)
    assert prepared.last_label_position == 98
    assert prepared.train_y[-1] == data.y.iloc[98]
    assert prepared.known_target == data.y.iloc[98]


def test_walk_forward_saves_complete_provenance(tmp_path):
    config = {
        **configuration(),
        "seeds": [7],
        "methods": ["ar", "factor_static", "factor_kalman", "gate_rule", "gate_learned"],
    }
    result = run(config, tmp_path / "run", max_origins=3)
    manifest = json.loads((tmp_path / "run/manifest.json").read_text())
    predictions = pd.read_csv(tmp_path / "run/predictions.csv")
    assert result["api_calls"] == manifest["api_calls"] == 0
    assert len(predictions) == 15
    assert predictions.groupby("origin").actual.nunique().eq(1).all()
    assert manifest["complete"]
    with pytest.raises(ValueError, match="already exists"):
        run(config, tmp_path / "run", max_origins=3)


def test_remote_gate_requires_explicit_budget_before_creating_output(tmp_path):
    config = {**configuration(), "methods": ["gate_jev"]}
    with pytest.raises(ValueError, match="max-api-calls"):
        run(config, tmp_path / "run", max_origins=1)
    assert not (tmp_path / "run").exists()


def test_unknown_methods_are_not_accepted_as_benchmarks(tmp_path):
    config = {**configuration(), "methods": ["fake_model"]}
    with pytest.raises(ValueError, match="Unknown forecast method"):
        run(config, tmp_path / "run", max_origins=1)
