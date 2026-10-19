"""Optional real-R contracts. No network calls or synthetic stand-in for the engine."""

import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor.fred_recipe import FredRecipeRepresentation
from jev_factor.fred_recipe_audit import r_recipe_check
from jev_factor.invocation_audit import audit_invocation
from jev_factor.pca_basis_audit import compare_rotations, r_rotations
from jev_factor.plain_controls import fit_inputs, r_ar2
from jev_factor.plain_forest import block_subsample
from jev_factor.replication import LINEAR_X, linear_prediction
from jev_factor.replication_audit import _r_linear

ENGINE = os.environ.get("JEV_MRF_REFERENCE_ENGINE")
R_LIBRARY = os.environ.get("JEV_MRF_R_LIBRARY")
pytestmark = pytest.mark.skipif(
    not ENGINE or not R_LIBRARY or not shutil.which("Rscript"),
    reason="Set JEV_MRF_REFERENCE_ENGINE and JEV_MRF_R_LIBRARY for real-R contracts",
)


def _prepare(tmp_path, name, matrix, mode, xnames=LINEAR_X):
    directory = tmp_path / name
    directory.mkdir()
    matrix.to_csv(directory / "input.csv", index=False, float_format="%.17g")
    settings = {
        "ntrain": 70,
        "xnames": ",".join(xnames),
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
    return directory


def _run(tmp_path, name, matrix, mode, xnames=LINEAR_X):
    directory = _prepare(tmp_path, name, matrix, mode, xnames)
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


@pytest.mark.parametrize("xnames", [LINEAR_X, ["y_lag1", "y_lag2"]], ids=["FA_ARRF", "ARRF"])
def test_reference_future_targets_are_masked_and_coefficients_reconstruct(tmp_path, xnames):
    matrix = _matrix()
    original = _run(tmp_path, "original", matrix, "train_only", xnames)
    changed = matrix.copy()
    changed.loc[70:, "target"] = 1e12
    altered = _run(tmp_path, "future_y", changed, "train_only", xnames)
    np.testing.assert_allclose(original, altered, atol=1e-10, rtol=0)
    reconstruct = original.intercept.to_numpy() + np.sum(
        original[xnames].to_numpy() * matrix.loc[70:, xnames].to_numpy(), axis=1
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


def test_independent_base_r_qr_agrees_with_python_least_squares(tmp_path):
    matrix = _matrix()
    matrix["y_lag3"] = matrix["state1"]
    matrix["y_lag4"] = matrix["state2"]
    matrix["F1_lag2"] = matrix["state3"]
    matrix["F2_lag2"] = matrix["state4"]
    path = tmp_path / "matrix.csv"
    matrix.to_csv(path, index=False, float_format="%.17g")
    qr, runtime = _r_linear(path, 70, shutil.which("Rscript"), tmp_path)
    ar = [f"y_lag{k}" for k in range(1, 5)]
    fa = ar + [f"F{j}_lag{k}" for j in [1, 2] for k in [1, 2]]
    assert "R version" in runtime
    for model, columns in [("AR4", ar), ("FA_AR", fa)]:
        expected = linear_prediction(matrix.iloc[:70], matrix.iloc[70:], columns)
        np.testing.assert_allclose(qr[model], expected, rtol=0, atol=1e-10)


def test_current_pinned_engine_is_not_factor_sign_invariant(tmp_path):
    # A diagnostic of the pinned implementation, not a desirable property.
    # The equation and state factor are flipped consistently; OLS prior refits.
    matrix = _matrix()
    original = _run(tmp_path, "original", matrix, "train_only")
    changed = matrix.copy()
    changed["F1_lag1"] *= -1
    reversed_basis = _run(tmp_path, "reversed_basis", changed, "train_only")
    assert np.max(np.abs(original.prediction - reversed_basis.prediction)) > 1e-5


def test_base_r_pca_and_maf_agree_up_to_signs_and_native_penalty_is_asymmetric(tmp_path):
    from sklearn.decomposition import PCA

    rng = np.random.default_rng(73)
    values = pd.DataFrame(rng.normal(size=(80, 6)), columns=["A", "B", "C", "D", "E", "S&P 500"])
    rotation, maf, weights, version = r_rotations(
        values, 3, Path(ENGINE), shutil.which("Rscript"), tmp_path
    )
    comparison = compare_rotations(
        PCA(n_components=3, svd_solver="full").fit(values).components_, rotation
    )
    assert comparison["same_up_to_component_signs"]
    assert len(maf) == 12
    x = values.A.to_numpy()
    lagged = np.column_stack([x[8 - k : len(x) - k] for k in range(1, 9)])
    comparison = compare_rotations(
        PCA(n_components=2, svd_solver="full").fit(lagged).components_,
        maf.loc[maf.series_index.eq(0)].iloc[:, 2:].to_numpy(),
    )
    assert comparison["same_up_to_component_signs"]
    assert np.max(np.abs(weights - weights[::-1])) > 0.1
    assert version.startswith("R version")


@pytest.mark.parametrize("terms,parent_size", [(LINEAR_X, 12), (["y_lag1", "y_lag2"], 10)])
def test_actual_native_initialization_receives_expected_roles_and_effective_guard(
    tmp_path, terms, parent_size
):
    directory = _prepare(tmp_path, "input", _matrix(), "train_only", terms)
    report = audit_invocation(
        directory / "input.csv",
        directory / "settings.dcf",
        Path(ENGINE),
        Path(R_LIBRARY),
        rscript=shutil.which("Rscript"),
    )
    assert report["linear_names"] == terms
    assert report["state_columns"] == 10
    assert report["native_settings"]["effective_parent_size"] == parent_size
    assert report["forests_fitted"] == 0
    assert report["forecast_scores_computed"] is False


@pytest.mark.parametrize("rows,columns,signal", [(70, 12, True), (16, 30, True), (400, 30, False)])
def test_independent_r_fred_recipe_matches_rank_path_completion_and_stopping(
    tmp_path, rows, columns, signal
):
    rng = np.random.default_rng(829)
    values = rng.normal(0, 0.2, (rows, columns))
    if signal:
        values += rng.normal(size=(rows, 2)) @ rng.normal(size=(2, columns))
    values[rng.random(values.shape) < 0.08] = np.nan
    values[0, 0] = 1e8
    frame = pd.DataFrame(values, columns=[f"series {k}" for k in range(columns)])
    fitted = FredRecipeRepresentation().fit(frame)
    check = r_recipe_check(frame, fitted, shutil.which("Rscript"), tmp_path)
    assert check["rank_path_and_stopping_reason_match"]
    assert check["maximum_standardized_matrix_difference"] < 1e-8
    assert check["final_PCA"]["same_up_to_component_signs"]


@pytest.mark.parametrize("rows", [160, 173, 211])
def test_plain_control_sampling_dimensions_and_quantile_match_base_r(tmp_path, rows):
    # This checks the distribution port's dimensions and cutoff algebra, not R
    # RNG equivalence. Both languages consume exactly the same supplied weights.
    sample = block_subsample(rows, np.random.default_rng(849))
    source = tmp_path / "row_weights.csv"
    output = tmp_path / "selected.csv"
    pd.DataFrame({"weight": sample.group_weights[sample.groups]}).to_csv(
        source, index=False, float_format="%.17g"
    )
    code = (
        "args <- commandArgs(TRUE); x <- read.csv(args[1])$weight; n <- length(x); "
        'cat(length(1:(n/8)), length(rexp(n=n/8)), "\\n"); '
        "write.csv(data.frame(row=which(x > quantile(x, .25, type=7))-1L), "
        "args[2], row.names=FALSE)"
    )
    result = subprocess.run(
        [shutil.which("Rscript"), "--vanilla", "-e", code, str(source), str(output)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert [int(value) for value in result.stdout.split()] == [rows // 8, rows // 8]
    np.testing.assert_array_equal(pd.read_csv(output)["row"], sample.rows)


def test_native_engine_rejects_an_empty_linear_equation_not_plain_rf_maf(tmp_path):
    path = tmp_path / "input.csv"
    _matrix().to_csv(path, index=False)
    code = (
        "args <- commandArgs(TRUE); env <- new.env(); source(args[1], local=env); "
        "answer <- tryCatch({env$MRF(read.csv(args[2]), x.pos=integer(0), "
        'oos.pos=71:78, printb=FALSE); "unexpected_success"}, '
        "error=function(e) conditionMessage(e)); cat(answer)"
    )
    result = subprocess.run(
        [shutil.which("Rscript"), "--vanilla", "-e", code, str(Path(ENGINE).resolve()), str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "at least one X" in result.stdout


def test_plain_control_ar2_filter_matches_independent_r_and_ignores_future_targets(tmp_path):
    matrix = _matrix()
    path = tmp_path / "filter.csv"
    matrix.to_csv(path, index=False, float_format="%.17g")
    _, _, base, metadata = fit_inputs(matrix, 70, "AR_plus_RF")
    beta, prediction, residual, version = r_ar2(path, 70, shutil.which("Rscript"))
    np.testing.assert_allclose(beta, metadata["base_coefficients"], atol=1e-10, rtol=0)
    np.testing.assert_allclose(prediction, base, atol=1e-10, rtol=0)
    np.testing.assert_allclose(residual, matrix.target.iloc[:70] - base[:70], atol=1e-10, rtol=0)
    assert version.startswith("R version")
    matrix.loc[70:, "target"] = 1e12
    matrix.to_csv(path, index=False, float_format="%.17g")
    altered = r_ar2(path, 70, shutil.which("Rscript"))
    for first, second in zip((beta, prediction, residual), altered[:3], strict=True):
        np.testing.assert_array_equal(first, second)
