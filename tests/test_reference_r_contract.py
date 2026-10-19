"""Optional real-R contracts. No network calls or synthetic stand-in for the engine."""

import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor.replication import LINEAR_X

ENGINE = os.environ.get("JEV_MRF_REFERENCE_ENGINE")
R_LIBRARY = os.environ.get("JEV_MRF_R_LIBRARY")
pytestmark = pytest.mark.skipif(
    not ENGINE or not R_LIBRARY or not shutil.which("Rscript"),
    reason="Set JEV_MRF_REFERENCE_ENGINE and JEV_MRF_R_LIBRARY for real-R contracts",
)


def _run(tmp_path, name, matrix, mode):
    directory = tmp_path / name
    directory.mkdir()
    matrix.to_csv(directory / "input.csv", index=False, float_format="%.17g")
    settings = {
        "ntrain": 70,
        "xnames": ",".join(LINEAR_X),
        "seed": 19,
        "trees": 2,
        "block": 8,
        "RWR": 0.75,
        "ridge_lambda": 0.1,
        "MLF": 1,
        "mtry": 0.5,
        "minsize": 10,
        "trend_push": 1,
        "prior": "OLS",
        "standardization": mode,
    }
    (directory / "settings.dcf").write_text(
        "\n".join(f"{k}: {v}" for k, v in settings.items()) + "\n"
    )
    result = subprocess.run(
        [
            shutil.which("Rscript"),
            "--vanilla",
            str(files("jev_factor").joinpath("reference_mrf.R")),
            str(Path(ENGINE).resolve()),
            str(directory / "input.csv"),
            str(directory / "settings.dcf"),
            str(directory / "output.csv"),
            str(Path(R_LIBRARY).resolve()),
        ],
        env={**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return pd.read_csv(directory / "output.csv")


def _matrix():
    rng = np.random.default_rng(99)
    matrix = pd.DataFrame(
        rng.normal(size=(78, 11)),
        columns=["target", *LINEAR_X, *[f"state{i}" for i in range(5)], "trend"],
    )
    matrix["trend"] = np.arange(len(matrix))
    matrix["target"] = matrix["y_lag1"] + 2 * matrix["F1_lag1"] + rng.normal(size=78)
    return matrix


def test_reference_future_targets_are_masked_and_coefficients_reconstruct(tmp_path):
    matrix = _matrix()
    original = _run(tmp_path, "original", matrix, "train_only")
    changed = matrix.copy()
    changed.loc[70:, "target"] = 1e12
    altered = _run(tmp_path, "future_y", changed, "train_only")
    np.testing.assert_allclose(original, altered, atol=1e-10, rtol=0)
    reconstruct = original.intercept.to_numpy() + np.sum(
        original[LINEAR_X].to_numpy() * matrix.loc[70:, LINEAR_X].to_numpy(), axis=1
    )
    np.testing.assert_allclose(reconstruct, original.prediction, atol=1e-10)


def test_train_only_scaling_is_insensitive_to_later_forecast_rows(tmp_path):
    matrix = _matrix()
    original = _run(tmp_path, "original", matrix, "train_only")
    changed = matrix.copy()
    changed.loc[71:, LINEAR_X] *= 1e6
    altered = _run(tmp_path, "future_x", changed, "train_only")
    np.testing.assert_allclose(original.iloc[0], altered.iloc[0], atol=1e-10, rtol=0)


def test_native_all_rows_scaling_exposes_transductive_dependence(tmp_path):
    matrix = _matrix()
    original = _run(tmp_path, "original", matrix, "native_all_supplied_rows")
    changed = matrix.copy()
    changed.loc[71:, LINEAR_X] *= 1e6
    altered = _run(tmp_path, "future_x", changed, "native_all_supplied_rows")
    assert abs(original.prediction.iloc[0] - altered.prediction.iloc[0]) > 1e-8
