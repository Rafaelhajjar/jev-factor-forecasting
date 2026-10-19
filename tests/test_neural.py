"""Actual Torch contracts and independent NumPy arithmetic; never macro scores."""

import json
from copy import deepcopy

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from jev_factor.neural import (  # noqa: E402
    TRAINING,
    arrays,
    audit_member,
    execution_context,
    export_weights,
    fit_member,
    history_summary,
    make_network,
    make_optimizer,
    numpy_forward,
    partition,
    save_member,
    streams,
    validate_training,
    validate_weights,
)


def _data():
    rng = np.random.default_rng(118)
    x = rng.normal(size=(40, 6)) + np.arange(6) / 4
    y = 0.02 * x[:, 0] - 0.01 * x[:, 1] + rng.normal(size=40) * 0.02
    return x, y, rng.normal(size=(8, 6)), {**deepcopy(TRAINING), "epochs": 2}


def test_exact_paper_architecture_default_initialization_and_numpy_forward():
    with execution_context():
        torch.manual_seed(17)
        model = make_network(7)
        linear = [layer for layer in model if isinstance(layer, torch.nn.Linear)]
        assert len(linear) == 6
        assert [a.out_features for a in linear] == [100, 100, 100, 100, 100, 1]
        assert len([a for a in model if isinstance(a, torch.nn.ReLU)]) == 5
        assert len(list(model)) == 11
        for a in linear:
            assert a.weight.dtype == torch.float32 and a.weight.device.type == "cpu"
            bound = 1 / np.sqrt(a.in_features)
            assert float(a.weight.detach().abs().max()) <= bound
            assert float(a.bias.detach().abs().max()) <= bound
        x = np.random.default_rng(99).normal(size=(13, 7)).astype(np.float32)
        with torch.no_grad():
            expected = model(torch.tensor(x)).numpy()[:, 0]
        weights = export_weights(model)
        validate_weights(weights, 7, TRAINING["hidden"])
        np.testing.assert_allclose(numpy_forward(x, weights), expected, atol=5e-8, rtol=1e-6)


def test_autograd_matches_independent_dense_relu_MSE_derivative():
    with execution_context():
        model = make_network(2, hidden=(3,)).double()
        x = np.array([[0.4, 0.2], [0.3, -0.1], [-0.2, 0.7]])
        y = np.array([[0.1], [0.2], [-0.1]])
        w0 = np.array([[0.3, 0.1], [-0.2, 0.4], [0.1, 0.5]])
        b0, w1, b1 = np.array([0.5, 0.2, -0.3]), np.array([[0.2, -0.3, 0.4]]), np.array([0.1])
        with torch.no_grad():
            model[0].weight.copy_(torch.tensor(w0))
            model[0].bias.copy_(torch.tensor(b0))
            model[2].weight.copy_(torch.tensor(w1))
            model[2].bias.copy_(torch.tensor(b1))
        prediction = model(torch.tensor(x))
        loss = torch.nn.functional.mse_loss(prediction, torch.tensor(y))
        loss.backward()
        before = x @ w0.T + b0
        hidden = np.maximum(before, 0)
        error_derivative = 2 * (hidden @ w1.T + b1 - y) / len(x)
        dz = (error_derivative @ w1) * (before > 0)
        np.testing.assert_allclose(model[0].weight.grad, dz.T @ x, atol=2e-15)
        np.testing.assert_allclose(model[0].bias.grad, dz.sum(axis=0), atol=2e-15)
        np.testing.assert_allclose(model[2].weight.grad, error_derivative.T @ hidden, atol=2e-15)
        np.testing.assert_allclose(model[2].bias.grad, error_derivative.sum(axis=0), atol=2e-15)
        assert float(loss.detach()) == pytest.approx(np.mean((hidden @ w1.T + b1 - y) ** 2))


def test_actual_Adam_defaults_and_three_updates_match_numpy():
    with execution_context():
        model = torch.nn.Linear(3, 1, bias=False, dtype=torch.float64)
        initial = np.array([[0.2, -0.4, 0.8]])
        with torch.no_grad():
            model.weight.copy_(torch.tensor(initial))
        optimizer = make_optimizer(model, TRAINING)
        assert optimizer.defaults["lr"] == 0.001
        assert optimizer.defaults["betas"] == (0.9, 0.999)
        assert optimizer.defaults["eps"] == 1e-8
        assert optimizer.defaults["weight_decay"] == 0
        assert optimizer.defaults["amsgrad"] is False
        assert optimizer.defaults["foreach"] is False
        assert optimizer.defaults["fused"] is False
        expected, m, v = initial.copy(), np.zeros_like(initial), np.zeros_like(initial)
        for step, gradient in enumerate(
            (
                np.array([[0.1, -0.3, 0.2]]),
                np.array([[-0.2, 0.1, 0.4]]),
                np.array([[0.05, 0.2, -0.2]]),
            ),
            1,
        ):
            model.weight.grad = torch.tensor(gradient)
            optimizer.step()
            m = 0.9 * m + 0.1 * gradient
            v = 0.999 * v + 0.001 * gradient**2
            expected -= 0.001 * (m / (1 - 0.9**step)) / (np.sqrt(v / (1 - 0.999**step)) + 1e-8)
            np.testing.assert_allclose(model.weight.detach(), expected, atol=2e-15)


def test_partition_is_exact_85_percent_without_replacement():
    fit, val = partition(166, 101, 0)
    assert len(fit) == 141 and len(val) == 25
    assert not set(fit) & set(val)
    assert sorted([*fit, *val]) == list(range(166))
    np.testing.assert_array_equal(partition(166, 101, 0)[0], fit)
    assert not np.array_equal(partition(166, 202, 0)[0], fit)
    assert streams(101, 0) != streams(101, 1)


def test_actual_fit_is_deterministic_future_independent_and_restores_global_state(tmp_path):
    x, y, future, settings = _data()
    rng, threads = torch.get_rng_state().clone(), torch.get_num_threads()
    mode = torch.are_deterministic_algorithms_enabled()
    weights, metadata = fit_member(x, y, future, 101, 0, settings)
    assert torch.equal(rng, torch.get_rng_state())
    assert torch.get_num_threads() == threads
    assert torch.are_deterministic_algorithms_enabled() == mode
    altered = future.copy()
    altered[1:] += 1000
    other_weights, other = fit_member(x, y, altered, 101, 0, settings)
    assert metadata["history"] == other["history"]
    assert metadata["initial_parameter_sha256"] == other["initial_parameter_sha256"]
    for k in weights:
        np.testing.assert_array_equal(weights[k], other_weights[k])
    assert metadata["forecast_prediction"][0] == other["forecast_prediction"][0]
    directory = tmp_path / "member"
    save_member(directory, weights, metadata)
    check = audit_member(directory, x, y, future, 101, 0, settings, refit=True)
    assert check["deterministic_refit_verified"]
    assert check["fit_rows"] == 34 and check["validation_rows"] == 6
    assert check["epochs_trained"] == 2


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("hidden", [100] * 4),
        ("patience", 5),
        ("target_scaling", "standardize"),
        ("training_fraction", 0.9),
        ("weight_decay", 0.01),
        ("epochs", 101),
        ("epochs", True),
        ("restore_best", False),
        ("device", "mps"),
    ],
)
def test_undeclared_training_change_rejected(key, value):
    settings = deepcopy(TRAINING)
    settings[key] = value
    with pytest.raises(ValueError):
        validate_training(settings)


def test_history_requires_first_best_and_declared_patience():
    rows = [
        {
            "epoch": i,
            "training_MSE": 0.1,
            "validation_MSE": 0.2 if i == 1 else 0.3,
            "improved": i == 1,
            "batch_order_sha256": "test",
        }
        for i in range(1, 12)
    ]
    summary = history_summary(rows, TRAINING)
    assert summary["best_epoch"] == 1 and summary["stop_reason"] == "patience"
    with pytest.raises(ValueError, match="stopping point"):
        history_summary(rows + [{**rows[-1], "epoch": 12}], TRAINING)
    with pytest.raises(ValueError, match="before patience"):
        history_summary(rows[:5], TRAINING)


@pytest.mark.parametrize("change", ["future_nan", "y_column", "short", "wrong_features"])
def test_invalid_arrays_rejected(change):
    x, y, future, _ = _data()
    if change == "future_nan":
        future[0, 0] = np.nan
    elif change == "y_column":
        y = y[:, None]
    elif change == "short":
        x, y = x[:20], y[:20]
    else:
        future = future[:, :2]
    with pytest.raises(ValueError):
        arrays(x, y, future)


@pytest.mark.parametrize("change", ["forecast", "split", "best_epoch", "weights", "source"])
def test_changed_member_artifacts_are_rejected(tmp_path, change):
    x, y, future, settings = _data()
    weights, metadata = fit_member(x, y, future, 101, 0, settings)
    directory = tmp_path / "member"
    save_member(directory, weights, metadata)
    file = directory / "member.json"
    saved = json.loads(file.read_text())
    if change == "forecast":
        saved["forecast_prediction"][0] += 0.01
    elif change == "split":
        saved["fit_indices"] = saved["fit_indices"][1:]
    elif change == "best_epoch":
        saved["best_epoch"] = 0
    elif change == "source":
        saved["trainer_sha256"] = "changed"
    else:
        weights["w0"][0, 0] += 0.1
        np.savez_compressed(directory / "weights.npz", **weights)
    file.write_text(json.dumps(saved))
    with pytest.raises(ValueError):
        audit_member(directory, x, y, future, 101, 0, settings)


def test_constant_feature_scale_is_fitting_only_and_target_unscaled():
    x, y, future, _ = _data()
    x[:, 2] = 7
    _, original_y, _, center, scale = arrays(x, y, future)
    assert center[2] == 7 and scale[2] == 1
    np.testing.assert_array_equal(original_y, y)
    future[:] += 1000
    _, _, _, changed_center, changed_scale = arrays(x, y, future)
    np.testing.assert_array_equal(center, changed_center)
    np.testing.assert_array_equal(scale, changed_scale)


def test_existing_member_is_not_overwritten(tmp_path):
    with pytest.raises(FileExistsError):
        save_member(tmp_path, {}, {})


def test_validation_stopping_restores_epoch_one_not_last_epoch(monkeypatch):
    x, y, future, settings = _data()
    real_loss = torch.nn.functional.mse_loss
    counter = 0

    def controlled_validation(prediction, target, *args, **kwargs):
        nonlocal counter
        if len(prediction) == 6:  # This fixture's held-out size; never a fitting batch.
            counter += 1
            return torch.tensor(float(counter), dtype=prediction.dtype)
        return real_loss(prediction, target, *args, **kwargs)

    # Force the validation criterion only, to exercise stopping/restoration. No accuracy claim.
    monkeypatch.setattr(torch.nn.functional, "mse_loss", controlled_validation)
    longer = {**settings, "epochs": 12}
    weights, metadata = fit_member(x, y, future, 101, 0, longer)
    assert metadata["best_epoch"] == 1 and metadata["epochs_trained"] == 11
    assert metadata["stop_reason"] == "patience"
    counter = 0
    first, _ = fit_member(x, y, future, 101, 0, {**settings, "epochs": 1})
    for key in weights:
        np.testing.assert_array_equal(weights[key], first[key])


def test_arithmetically_valid_substitute_is_rejected_by_training_refit(tmp_path):
    x, y, future, settings = _data()
    weights, metadata = fit_member(x, y, future, 101, 0, settings)
    directory = tmp_path / "member"
    save_member(directory, weights, metadata)
    for key in weights:
        weights[key][:] = 0
    validation = metadata["validation_indices"]
    fitting = metadata["fit_indices"]
    constant = np.float32(y[validation].mean())
    weights["b5"][0] = constant
    saved = json.loads((directory / "member.json").read_text())
    val_loss = float(np.mean((constant - y[validation]) ** 2))
    train_loss = float(np.mean((constant - y[fitting]) ** 2))
    for i, row in enumerate(saved["history"]):
        row.update(training_MSE=train_loss, validation_MSE=val_loss, improved=i == 0)
    saved.update(
        best_epoch=1,
        best_validation_MSE=val_loss,
        forecast_prediction=[float(constant)] * len(future),
    )
    np.savez_compressed(directory / "weights.npz", **weights)
    import hashlib

    saved["weights_file_sha256"] = hashlib.sha256(
        (directory / "weights.npz").read_bytes()
    ).hexdigest()
    (directory / "member.json").write_text(json.dumps(saved))
    # A valid traversal and loss calculation is not proof the declared optimizer produced it.
    audit_member(directory, x, y, future, 101, 0, settings)
    with pytest.raises(ValueError, match="Deterministic"):
        audit_member(directory, x, y, future, 101, 0, settings, refit=True)
