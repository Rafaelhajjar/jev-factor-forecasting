import json
import os
import shutil
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor.quarterly import QuarterlyData
from jev_factor.rf2018 import run_job, validate_config
from jev_factor.vintage2018 import load_vintage, origin_aligned_design, prepare_window


def toy():
    dates = pd.period_range("1959Q1", periods=200, freq="Q")
    rng = np.random.default_rng(3)
    panel = pd.DataFrame(rng.normal(size=(200, 8)), index=dates)
    target = pd.Series(rng.normal(size=200), index=dates)
    codes = pd.Series(1, index=panel.columns)
    return QuarterlyData(panel, panel, target, codes, codes, {})


def config():
    return json.loads(Path("configs/rf_september2018.json").read_text())


@pytest.mark.parametrize("horizon", [1, 2, 4, 6, 8])
def test_direct_labels_and_current_plus_seven_lags(horizon):
    data = toy()
    raw, ar = origin_aligned_design(data.panel, data.target, horizon)
    origin = data.panel.index[60]
    d = origin + horizon
    assert raw.loc[d, "target"] == data.target[d]
    for lag in range(8):
        assert raw.loc[d, f"raw_000_lag{lag}"] == data.panel.loc[origin - lag, 0]
    for lag in range(4):
        assert ar.loc[d, f"ar_lag{lag}"] == data.target[origin - lag]
    # Target-indexed L1:L8 is exactly origin-indexed L0:L7 for h=1.
    if horizon == 1:
        for lag in range(8):
            assert raw.loc[d, f"raw_000_lag{lag}"] == data.panel[0].shift(lag + 1)[d]


def test_irregular_quarter_grid_rejected():
    data = toy()
    with pytest.raises(ValueError, match="calendar"):
        origin_aligned_design(
            data.panel.drop(data.panel.index[12]), data.target.drop(data.panel.index[12])
        )


def test_pinned_vintage_rejects_wrong_bytes(tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not the declared archive")
    with pytest.raises(ValueError, match="checksum"):
        load_vintage(bad)


def test_final_forecast_and_first_training_row_are_retained():
    data = toy()
    end = data.panel.index[160]
    raw, ar, meta = prepare_window(data, end, end + 8, config())
    assert str(raw.index[0]) == "1961Q3"
    assert raw.index[-1] == end + 8
    assert raw.target.iloc[-1] == data.target[end + 8]
    assert ar.target.equals(raw.target)
    assert meta["representation_fit_end"] == str(end - 1)
    assert meta["first_training_origin"] == "1961Q2"
    assert meta["features"] == 8 * data.panel.shape[1]


def test_future_covariates_do_not_change_training_or_first_forecast():
    data = toy()
    end = data.panel.index[160]
    raw, ar, _ = prepare_window(data, end, end + 8, config())
    altered = deepcopy(data)
    altered.panel.loc[end + 1 :, 0] += 10000
    altered.target.loc[end + 1 :] -= 10000
    changed, changed_ar, _ = prepare_window(altered, end, end + 8, config())
    np.testing.assert_allclose(
        raw.loc[: end + 1].iloc[:, 1:], changed.loc[: end + 1].iloc[:, 1:], atol=1e-12
    )
    np.testing.assert_array_equal(
        ar.loc[: end + 1].iloc[:, 1:], changed_ar.loc[: end + 1].iloc[:, 1:]
    )


@pytest.mark.parametrize(
    "key,value",
    [("trees", 100), ("min_node_size", 10), ("primary", "appendix_style"), ("horizon", 2)],
)
def test_declaration_cannot_be_silently_changed(key, value):
    c = config()
    validate_config(c)
    c[key] = value
    with pytest.raises(ValueError, match="declared"):
        validate_config(c)


@pytest.mark.skipif(
    not os.environ.get("JEV_RF_R_LIBRARY") or not shutil.which("Rscript"),
    reason="Set JEV_RF_R_LIBRARY to an installed ranger library",
)
@pytest.mark.parametrize("replace,fraction", [(True, 1.0), (False, 0.75)])
def test_real_ranger_leaf_audit_and_heldout_target_independence(tmp_path, replace, fraction):
    rng = np.random.default_rng(125)
    x = rng.normal(size=(70, 6))
    y = 2 * x[:, 0] + rng.normal(size=70)
    frame = pd.DataFrame(x, columns=[f"x{i}" for i in range(6)])
    frame.insert(0, "target", y)
    matrix = tmp_path / "matrix.csv"
    ar = tmp_path / "ar.csv"
    frame.to_csv(matrix, index=False)
    frame.iloc[:, :5].to_csv(ar, index=False)
    settings = tmp_path / "settings.dcf"
    settings.write_text(
        f"ntrain: 60\ntrees: 5\nmin_node_size: 3\nseed: 101\nmtry: 2\n"
        f"replace: {str(replace).upper()}\nsample_fraction: {fraction}\n"
    )
    job = {"settings": str(settings), "prediction": str(tmp_path / "prediction.csv")}
    window = {"paths": {"raw": str(matrix), "ar": str(ar)}}
    lib = Path(os.environ["JEV_RF_R_LIBRARY"])
    run_job(job, window, lib, "fit")
    original = pd.read_csv(job["prediction"])
    run_job(job, window, lib, "audit")
    frame.loc[60:, "target"] += 1e9
    frame.to_csv(matrix, index=False)
    frame.iloc[:, :5].to_csv(ar, index=False)
    run_job(job, window, lib, "fit")
    np.testing.assert_array_equal(original, pd.read_csv(job["prediction"]))
