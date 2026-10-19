import csv
import io

import numpy as np
import pandas as pd
import pytest

from jev_factor.quarterly import (
    SP_NAMES,
    PastRepresentation,
    QuarterlyData,
    make_design,
    parse_quarterly_csv,
)
from jev_factor.replication import linear_prediction, score_table


def _csv(rows):
    stream = io.StringIO()
    csv.writer(stream).writerows(rows)
    return stream.getvalue().encode()


def test_metadata_and_quarter_dates():
    raw = _csv(
        [
            ["sasdate", "A", "B"],
            ["factors", 1, 0],
            ["transform", 5, 2],
            ["3/1/1959", 100, 5],
            ["6/1/1959", 101, 6],
            ["9/1/1959", 103, 7],
        ]
    )
    levels, codes, flags, repairs = parse_quarterly_csv(raw)
    assert levels.index.equals(pd.period_range("1959Q1", "1959Q3", freq="Q"))
    assert codes.to_dict() == {"A": 5, "B": 2}
    assert flags.to_dict() == {"A": 1, "B": 0}
    assert not repairs


def test_exact_split_header_repair_rejects_populated_padding():
    header = ["sasdate"] + [f"col{i}" for i in range(1, 245)]
    header += ["S&P", "500", "S&P:", "indust", "S&P", "div", "yield", "S&P", "PE", "ratio"]
    rows = [header, ["factors"] + [1] * 248 + [""] * 6, ["transform"] + [5] * 248 + [""] * 6]
    rows += [[date] + [1] * 248 + [""] * 6 for date in ["3/1/1959", "6/1/1959"]]
    levels, _, _, repairs = parse_quarterly_csv(_csv(rows))
    assert list(levels.columns[-4:]) == SP_NAMES
    assert len(levels.columns) == 248
    assert repairs["245"] == "S&P 500"
    rows[-1][-1] = 100
    with pytest.raises(ValueError, match="padding"):
        parse_quarterly_csv(_csv(rows))


def test_rejects_missing_quarter_and_ragged_csv():
    rows = [["sasdate", "A"], ["factors", 1], ["transform", 2], ["3/1/1959", 1], ["9/1/1959", 2]]
    with pytest.raises(ValueError, match="Missing calendar"):
        parse_quarterly_csv(_csv(rows))
    rows[-1].append(0)
    with pytest.raises(ValueError, match="Ragged"):
        parse_quarterly_csv(_csv(rows))


def test_past_representation_keeps_observed_values_and_fills_missing():
    rng = np.random.default_rng(4)
    values = rng.normal(size=(70, 6))
    values[:, 4] = values[:, 0] + 0.2 * rng.normal(size=70)
    values[10:15, 1] = np.nan
    frame = pd.DataFrame(values, index=pd.period_range("1959Q1", periods=70, freq="Q"))
    rep = PastRepresentation(rank=2, outlier_iqr=None).fit(frame.iloc[:60])
    z, factors = rep.transform(frame)
    assert np.isfinite(z.to_numpy()).all()
    assert np.isfinite(factors.to_numpy()).all()
    restored = z.to_numpy() * rep.std + rep.mean
    observed = np.isfinite(values)
    np.testing.assert_allclose(restored[observed], values[observed], atol=1e-10)
    changed = frame.copy()
    changed.iloc[65:] *= 1000
    z_changed, f_changed = rep.transform(changed)
    np.testing.assert_allclose(z.iloc[:65], z_changed.iloc[:65])
    np.testing.assert_allclose(factors.iloc[:65], f_changed.iloc[:65])


def _toy_data():
    rng = np.random.default_rng(6)
    index = pd.period_range("1959Q1", periods=90, freq="Q")
    panel = pd.DataFrame(
        rng.normal(size=(90, 7)), index=index, columns=[f"series{i}" for i in range(7)]
    )
    target = pd.Series(rng.normal(size=90), index=index)
    codes = pd.Series(1, index=panel.columns)
    return QuarterlyData(panel.copy(), panel, target, codes, pd.Series(1, index=panel.columns), {})


def test_design_has_final_forecast_row_and_no_future_feature_leakage():
    data = _toy_data()
    end = data.panel.index[65]
    through = end + 8
    design, metadata = make_design(data, end, through, rank=3, outlier_iqr=None)
    assert design.index[0] == pd.Period("1961Q3")
    assert design.index[-1] == through
    assert metadata["state_columns"] == 8 + 3 * 8 + 7 * 2 + 7 * 2 + 1
    assert design.loc[end + 1, "y_lag1"] == data.target[end]
    assert design.loc[end + 1, "y_lag2"] == data.target[end - 1]
    data.panel.loc[end + 1 :] *= 1e4
    data.target.loc[end + 1 :] *= 1e4
    changed, _ = make_design(data, end, through, rank=3, outlier_iqr=None)
    np.testing.assert_allclose(
        design.loc[: end + 1].drop(columns="target"),
        changed.loc[: end + 1].drop(columns="target"),
        atol=1e-10,
    )


def test_linear_and_metrics_require_matched_dates():
    train = pd.DataFrame({"x": np.arange(10), "target": 2 + 3 * np.arange(10)})
    predicted = linear_prediction(train, pd.DataFrame({"x": [10, 11]}), ["x"])
    np.testing.assert_allclose(predicted, [32, 35])
    frame = pd.DataFrame(
        {
            "target_date": ["2003Q1", "2003Q2"] * 2,
            "model": ["AR4"] * 2 + ["test"] * 2,
            "actual": [1, 2] * 2,
            "prediction": [0, 0, 0.5, 1],
        }
    )
    scores = score_table(frame).set_index("model")
    assert scores.loc["test", "RMSE_over_AR4"] == pytest.approx(0.5)
    with pytest.raises(ValueError, match="Unmatched"):
        score_table(frame.iloc[:-1])
    with pytest.raises(ValueError, match="Duplicate"):
        score_table(pd.concat([frame, frame.iloc[:1]]))
