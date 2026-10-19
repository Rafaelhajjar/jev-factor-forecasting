"""Optional actual pinned TVP + fGarch contracts, never a quarterly score."""

import os
import shutil
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor.tvp_ridge import DEFAULT_SETTINGS, audit_tvp_output, run_native_tvp

ENGINE = os.environ.get("JEV_TVP_REFERENCE_ENGINE")
LIBRARY = os.environ.get("JEV_MRF_R_LIBRARY")
pytestmark = pytest.mark.skipif(
    not ENGINE or not LIBRARY or not shutil.which("Rscript"),
    reason="Set JEV_TVP_REFERENCE_ENGINE and prepared JEV_MRF_R_LIBRARY",
)


def _inputs():
    rng = np.random.default_rng(763)
    x = rng.normal(size=(70, 3)) + [0.3, 1.2, -0.5]
    scale = np.linspace(0.2, 1.0, len(x))
    beta = 0.5 + np.linspace(0, 0.4, len(x))
    y = 1.3 + x[:, 0] * beta - 0.4 * x[:, 1] + rng.normal(size=len(x)) * scale
    test = rng.normal(size=(5, 3))
    settings = deepcopy(DEFAULT_SETTINGS)
    settings["lambda_candidates"] = [0.01, 1.0, 100.0]
    return x, y, test, settings


def _run(directory, x, y, test, settings):
    return run_native_tvp(x, y, test, Path(ENGINE), Path(LIBRARY), directory, settings)


def test_actual_two_step_ridge_CV_GARCH_and_future_rows(tmp_path):
    x, y, test, settings = _inputs()
    original = _run(tmp_path / "original", x, y, test, settings)
    changed = test.copy()
    changed[1:] += 10000
    altered = _run(tmp_path / "later_forecast_x", x, y, changed, settings)
    assert original["status"] == "native_TVP_algebra_verified_not_quarterly_benchmark"
    assert original["lambda_step1"] == altered["lambda_step1"]
    assert original["lambda_step2"] == altered["lambda_step2"]
    for file in ("beta_rr.csv", "beta_2srr.csv", "cv_first.csv", "cv_second.csv", "folds.csv"):
        np.testing.assert_array_equal(
            pd.read_csv(tmp_path / "original" / file),
            pd.read_csv(tmp_path / "later_forecast_x" / file),
        )
    first = pd.read_csv(tmp_path / "original" / "predictions.csv").prediction.iloc[0]
    second = pd.read_csv(tmp_path / "later_forecast_x" / "predictions.csv").prediction.iloc[0]
    assert first == second
    assert original["native_random_CV_is_not_chronological"]
    assert original["public_lambda_return_is_first_step_only"]


@pytest.mark.parametrize(
    "artifact",
    ["beta_2srr.csv", "cv_second.csv", "predictions.csv", "volatility.csv", "forecast_x.csv"],
)
def test_actual_native_output_tampering_is_rejected(tmp_path, artifact):
    x, y, test, settings = _inputs()
    directory = tmp_path / "native"
    _run(directory, x, y, test, settings)
    data = pd.read_csv(directory / artifact)
    data.iloc[0, -1] += 0.02
    data.to_csv(directory / artifact, index=False, float_format="%.17g")
    with pytest.raises(ValueError):
        audit_tvp_output(directory, settings)


def test_actual_default_nine_coefficient_native_model(tmp_path):
    rng = np.random.default_rng(205)
    x = rng.normal(size=(85, 8)) + np.arange(8) / 3
    y = 0.7 + x[:, 0] - x[:, 4] + rng.normal(size=85) * np.linspace(0.4, 1.1, 85)
    result = _run(tmp_path / "nine", x, y, rng.normal(size=(8, 8)), deepcopy(DEFAULT_SETTINGS))
    assert result["coefficients"] == 9
    assert result["CV_folds"] == 5
    assert result["quarterly_benchmark_completed"] is False
