"""Independent random-walk algebra and strict native-adapter input contracts."""

from copy import deepcopy

import numpy as np
import pytest

from jev_factor.tvp_ridge import (
    DEFAULT_SETTINGS,
    ensure_tvp_engine,
    native_cv_scores,
    random_walk_solution,
    run_native_tvp,
    validate_inputs,
    validate_settings,
)


def test_random_walk_matches_direct_penalized_coefficient_path():
    rng = np.random.default_rng(91)
    n, p = 12, 3
    a = np.column_stack([np.ones(n), rng.normal(size=(n, p - 1))])
    y, w, e = rng.normal(size=n), np.array([0.5, 1.3, 2.0]), np.linspace(0.4, 1.5, n)
    penalty, level = 3.2, 0.1
    design = np.zeros((n, n * p))
    for t in range(n):
        design[t, t * p : (t + 1) * p] = a[t]
    differences = np.diff(np.eye(n), axis=0)
    precision = np.kron(differences.T @ differences, np.diag(penalty / w))
    precision[:p, :p] += level * np.eye(p)
    normal = (design.T / e) @ design + precision
    expected = np.linalg.solve(normal, design.T @ (y / e)).reshape(n, p)
    beta, prediction = random_walk_solution(a, y, penalty, level, w, e)
    np.testing.assert_allclose(beta, expected, atol=2e-13)
    np.testing.assert_allclose(prediction, (design @ expected.ravel()), atol=2e-13)


def test_cv_matches_direct_augmented_basis_and_dropout_column_scaling():
    rng = np.random.default_rng(37)
    n, p = 15, 3
    a = np.column_stack([np.ones(n), rng.normal(size=(n, p - 1))])
    y = rng.normal(size=n)
    folds = np.array([1, 1, 2, 3, 2, 1, 3, 3, 2, 1, 2, 3, 1, 3, 2])
    weights, noise, candidates = np.array([0.4, 1.5, 2.0]), np.linspace(0.8, 1.2, n), [0.1, 10]
    step = (np.arange(n)[:, None] > np.arange(n - 1)).astype(float)
    z = np.column_stack([*(a[:, j, None] * step for j in range(p)), a])
    expected = []
    for fold in range(1, 4):
        tr, te = np.flatnonzero(folds != fold), np.flatnonzero(folds == fold)
        run, dropout = 0, []
        for f in folds:
            run = run + 1 if f == fold else 0
            dropout.append(1 + run)
        projected = []
        targets = []
        for rows in (tr, te):
            ar = a[rows]
            residual = np.eye(len(rows)) - ar @ np.linalg.solve(ar.T @ ar + 0.1 * np.eye(p), ar.T)
            projected.append(residual @ z[rows])
            targets.append(residual @ y[rows])
        ztr, zte = projected
        for j in range(p):
            block = slice(j * (n - 1), (j + 1) * (n - 1))
            ztr[:, block] *= weights[j] * np.asarray(dropout)[1:]
            zte[:, block] *= weights[j]
        expected.append(
            [
                np.mean(
                    (
                        zte
                        @ ztr.T
                        @ np.linalg.solve(ztr @ ztr.T + c * np.diag(noise[tr]), targets[0])
                        - targets[1]
                    )
                    ** 2
                )
                for c in candidates
            ]
        )
    actual = native_cv_scores(a, y, folds, candidates, 0.1, weights, noise)
    np.testing.assert_allclose(actual, expected, atol=2e-12)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("lambda_candidates", [1, 1]),
        ("lambda_candidates", [1, float("nan")]),
        ("lambda_candidates", [-1, 1]),
        ("lambda_candidates", [1]),
        ("lambda2", 0),
        ("kfold", True),
        ("kfold", 1),
        ("sig_u", 0),
        ("sig_eps", 2),
        ("ols_prior", 1),
        ("CV_2SRR", False),
    ],
)
def test_invalid_settings_rejected(key, value):
    settings = deepcopy(DEFAULT_SETTINGS)
    settings[key] = value
    with pytest.raises(ValueError):
        validate_settings(settings)


def test_default_settings_valid_and_source_tampering_rejected(tmp_path):
    validate_settings(deepcopy(DEFAULT_SETTINGS))
    engine = tmp_path / "changed.R"
    engine.write_text("print('not the author engine')\n")
    with pytest.raises(ValueError, match="checksum"):
        ensure_tvp_engine(engine)


@pytest.mark.parametrize(
    "change", ["constant_x", "constant_y", "future_nan", "dimensions", "short"]
)
def test_invalid_native_input_rejected(change):
    rng = np.random.default_rng(42)
    x, y, test = rng.normal(size=(40, 3)), rng.normal(size=40), rng.normal(size=(4, 3))
    if change == "constant_x":
        x[:, 0] = 1
    elif change == "constant_y":
        y[:] = 1
    elif change == "future_nan":
        test[2, 1] = np.nan
    elif change == "dimensions":
        y = y[:, None]
    elif change == "short":
        x, y = x[:20], y[:20]
    with pytest.raises(ValueError):
        validate_inputs(x, y, test)


def test_existing_output_cannot_be_overwritten(tmp_path):
    rng = np.random.default_rng(4)
    with pytest.raises(FileExistsError):
        run_native_tvp(
            rng.normal(size=(40, 2)),
            rng.normal(size=40),
            np.ones((3, 2)),
            tmp_path / "absent.R",
            tmp_path,
            tmp_path,
        )


@pytest.mark.parametrize("bad_weight", [-1, np.nan, 0])
def test_invalid_random_walk_weights_rejected(bad_weight):
    with pytest.raises(ValueError):
        random_walk_solution(np.ones((6, 2)), np.arange(6), 1, 0.1, [1, bad_weight])
