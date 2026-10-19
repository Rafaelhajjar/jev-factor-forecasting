"""Auditable appendix-inspired Torch NN members; no historical-runner claim."""

from __future__ import annotations

import hashlib
import json
import platform
from contextlib import contextmanager
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

TORCH_VERSION = "2.14.1"
TRAINING = {
    "hidden": [100, 100, 100, 100, 100],
    "epochs": 100,
    "batch_size": 32,
    "training_fraction": 0.85,
    "learning_rate": 0.001,
    "betas": [0.9, 0.999],
    "eps": 1e-8,
    "weight_decay": 0.0,
    "amsgrad": False,
    "patience": 10,
    "min_delta": 0.0,
    "restore_best": True,
    "first_eligible_epoch": 1,
    "feature_scaling": "full_fitting_window_mean_sample_SD",
    "constant_scale_rule": "unit_if_SD_leq_1e-12",
    "target_scaling": "none",
    "dtype": "float32",
    "device": "cpu",
    "threads": 1,
    "initialization": "Torch_Linear_default",
    "activation": "ReLU",
    "output": "linear",
    "loss": "mean_squared_error",
    "dropout": 0.0,
    "foreach": False,
    "fused": False,
}


def _torch():
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install the optional NN dependency with uv sync --extra nn") from exc
    if str(torch.__version__).split("+")[0] != TORCH_VERSION:
        raise ValueError("NN reconstruction requires the pinned Torch version")
    return torch


def backend():
    torch = _torch()
    return {
        "torch": str(torch.__version__),
        "torch_git": torch.version.git_version,
        "torch_build_sha256": hashlib.sha256(torch.__config__.show().encode()).hexdigest(),
        "numpy": np.__version__,
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "device": "cpu",
        "dtype": "float32",
        "threads": 1,
        "deterministic_algorithms": True,
    }


@contextmanager
def execution_context():
    torch = _torch()
    threads = torch.get_num_threads()
    deterministic = torch.are_deterministic_algorithms_enabled()
    warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    try:
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        with torch.random.fork_rng(devices=[]), threadpool_limits(limits=1):
            yield torch
    finally:
        torch.set_num_threads(threads)
        torch.use_deterministic_algorithms(deterministic, warn_only=warn_only)


def validate_training(settings, *, declaration=False):
    if (
        set(settings) != set(TRAINING)
        or type(settings["epochs"]) is not int
        or not 1 <= settings["epochs"] <= 100
        or (declaration and settings["epochs"] != 100)
        or any(
            type(settings[k]) is not type(v) or settings[k] != v
            for k, v in TRAINING.items()
            if k != "epochs"
        )
    ):
        raise ValueError("Only the fixed NN construction or a reduced epoch pilot is supported")


def arrays(x, y, forecast_x):
    x, y, forecast_x = (np.asarray(a, dtype=np.float64) for a in (x, y, forecast_x))
    if (
        x.ndim != 2
        or forecast_x.ndim != 2
        or not 30 <= len(x)
        or not 1 <= x.shape[1]
        or y.shape != (len(x),)
        or forecast_x.shape[1] != x.shape[1]
        or not len(forecast_x)
        or not all(np.isfinite(a).all() for a in (x, y, forecast_x))
    ):
        raise ValueError("Invalid finite NN fitting/forecast arrays")
    center, scale = x.mean(axis=0), x.std(axis=0, ddof=1)
    scale = np.where(scale <= 1e-12, 1.0, scale)
    standardized = (x - center) / scale
    future = (forecast_x - center) / scale
    if not all(np.isfinite(a.astype(np.float32)).all() for a in (standardized, future, y)):
        raise ValueError("NN inputs are not representable as finite float32")
    return x, y, forecast_x, center, scale


def streams(seed, member):
    if (
        type(seed) is not int
        or not 0 <= seed < 2**32
        or type(member) is not int
        or not 0 <= member < 10
    ):
        raise ValueError("Invalid NN seed/member identity")
    values = np.random.SeedSequence([seed, member, 0x4E4E]).generate_state(3)
    return dict(zip(("partition", "initialization", "batches"), map(int, values), strict=True))


def partition(n, seed, member, fraction=0.85):
    if type(n) is not int or n < 30 or fraction != 0.85:
        raise ValueError("NN subsampling requires at least 30 rows and fixed 85%")
    order = np.random.default_rng(streams(seed, member)["partition"]).permutation(n)
    split = int(np.floor(fraction * n))
    return np.sort(order[:split]), np.sort(order[split:])


def make_network(n_input, hidden=(100, 100, 100, 100, 100)):
    torch = _torch()
    if (
        type(n_input) is not int
        or n_input < 1
        or not hidden
        or any(type(n) is not int or n < 1 for n in hidden)
    ):
        raise ValueError("Invalid dense network dimensions")
    dimensions = [n_input, *hidden, 1]
    layers = []
    for i, (before, after) in enumerate(zip(dimensions[:-1], dimensions[1:], strict=True)):
        layers.append(torch.nn.Linear(before, after, device="cpu", dtype=torch.float32))
        if i < len(dimensions) - 2:
            layers.append(torch.nn.ReLU())
    return torch.nn.Sequential(*layers)


def make_optimizer(model, settings):
    torch = _torch()
    return torch.optim.Adam(
        model.parameters(),
        lr=settings["learning_rate"],
        betas=tuple(settings["betas"]),
        eps=settings["eps"],
        weight_decay=settings["weight_decay"],
        amsgrad=settings["amsgrad"],
        foreach=False,
        fused=False,
        maximize=False,
        capturable=False,
        differentiable=False,
        decoupled_weight_decay=False,
    )


def export_weights(model):
    torch = _torch()
    result = {}
    for i, layer in enumerate(layer for layer in model if isinstance(layer, torch.nn.Linear)):
        result[f"w{i}"] = layer.weight.detach().cpu().numpy().copy()
        result[f"b{i}"] = layer.bias.detach().cpu().numpy().copy()
    return result


def validate_weights(weights, n_input, hidden):
    dimensions = [n_input, *hidden, 1]
    expected = {f"{kind}{i}" for i in range(len(dimensions) - 1) for kind in ("w", "b")}
    if set(weights) != expected:
        raise ValueError("NN parameter names/layer count differ")
    for i, (before, after) in enumerate(zip(dimensions[:-1], dimensions[1:], strict=True)):
        for key, shape in ((f"w{i}", (after, before)), (f"b{i}", (after,))):
            a = weights[key]
            if a.shape != shape or a.dtype != np.float32 or not np.isfinite(a).all():
                raise ValueError("NN parameter shape/dtype/value differs")


def numpy_forward(x, weights):
    """Independent dense/ReLU traversal, never loading a pickled model."""
    x = np.asarray(x, dtype=np.float32)
    if x.ndim != 2 or not np.isfinite(x).all() or len(weights) % 2:
        raise ValueError("Invalid independent NN forward inputs")
    layers = len(weights) // 2
    if not layers or set(weights) != {f"{k}{i}" for i in range(layers) for k in ("w", "b")}:
        raise ValueError("Invalid NN weight keys")
    result = x
    for i in range(layers):
        w, b = weights[f"w{i}"], weights[f"b{i}"]
        if (
            w.ndim != 2
            or w.shape[1] != result.shape[1]
            or b.shape != (w.shape[0],)
            or not all(np.isfinite(z).all() for z in (w, b))
        ):
            raise ValueError("Invalid NN layer topology/values")
        result = result @ w.T + b
        if i < layers - 1:
            result = np.maximum(result, np.float32(0))
    if result.shape[1] != 1 or not np.isfinite(result).all():
        raise ValueError("Invalid NN scalar output")
    return result[:, 0].astype(np.float64)


def _digest_arrays(data):
    result = {}
    for name, a in data.items():
        a = np.ascontiguousarray(a)
        digest = hashlib.sha256()
        digest.update(str(a.shape).encode())
        digest.update(str(a.dtype).encode())
        digest.update(a.tobytes())
        result[name] = digest.hexdigest()
    return result


def _input_hashes(x, y, future):
    return _digest_arrays({"fitting_x": x, "fitting_y": y, "forecast_x": future})


def _numeric(actual, expected, label):
    actual, expected = np.asarray(actual), np.asarray(expected)
    if (
        actual.shape != expected.shape
        or not np.isfinite(actual).all()
        or not np.allclose(actual, expected, rtol=2e-5, atol=2e-6)
    ):
        raise ValueError(f"Independent NN {label} disagrees")
    return float(np.max(np.abs(actual - expected)))


def history_summary(history, settings):
    if not history or len(history) > settings["epochs"]:
        raise ValueError("Invalid NN epoch history")
    best, best_epoch, stale = float("inf"), 0, 0
    for i, row in enumerate(history, 1):
        if (
            set(row)
            != {"epoch", "training_MSE", "validation_MSE", "improved", "batch_order_sha256"}
            or row["epoch"] != i
        ):
            raise ValueError("Invalid NN epoch history schema/order")
        losses = (row["training_MSE"], row["validation_MSE"])
        if not np.isfinite(losses).all() or min(losses) < 0:
            raise ValueError("Invalid NN loss value")
        improved = row["validation_MSE"] < best - settings["min_delta"]
        if row["improved"] is not improved:
            raise ValueError("NN improvement flag disagrees")
        if improved:
            best, best_epoch, stale = row["validation_MSE"], i, 0
        else:
            stale += 1
        if stale >= settings["patience"] and i != len(history):
            raise ValueError("NN continued beyond its stopping point")
    reason = "patience" if stale >= settings["patience"] else "epoch_cap"
    if reason == "epoch_cap" and len(history) != settings["epochs"]:
        raise ValueError("NN stopped before patience or epoch cap")
    return {
        "best_epoch": best_epoch,
        "best_validation_MSE": best,
        "epochs_trained": len(history),
        "stop_reason": reason,
    }


def fit_member(x, y, forecast_x, seed, member, settings):
    validate_training(settings)
    x, y, forecast_x, center, scale = arrays(x, y, forecast_x)
    fit, validation = partition(len(x), seed, member)
    random = streams(seed, member)
    with execution_context() as torch:
        torch.manual_seed(random["initialization"])
        model = make_network(x.shape[1], settings["hidden"])
        initial = _digest_arrays(export_weights(model))
        optimizer = make_optimizer(model, settings)
        tx = torch.tensor((x - center) / scale, dtype=torch.float32, device="cpu")
        ty = torch.tensor(y, dtype=torch.float32, device="cpu").reshape(-1, 1)
        fit_index = torch.tensor(fit, dtype=torch.int64, device="cpu")
        val_index = torch.tensor(validation, dtype=torch.int64, device="cpu")
        generator = torch.Generator(device="cpu").manual_seed(random["batches"])
        best, saved, stale, history = float("inf"), None, 0, []
        for epoch in range(1, settings["epochs"] + 1):
            model.train()
            order = torch.randperm(len(fit), generator=generator, device="cpu")
            for begin in range(0, len(fit), settings["batch_size"]):
                selected = fit_index[order[begin : begin + settings["batch_size"]]]
                optimizer.zero_grad(set_to_none=True)
                loss = torch.nn.functional.mse_loss(model(tx[selected]), ty[selected])
                if not torch.isfinite(loss):
                    raise ValueError("Nonfinite NN training loss; no retry/fallback")
                loss.backward()
                if any(
                    p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()
                ):
                    raise ValueError("Nonfinite/missing NN gradient; no retry/fallback")
                optimizer.step()
            model.eval()
            with torch.no_grad():
                train_loss = float(
                    torch.nn.functional.mse_loss(model(tx[fit_index]), ty[fit_index])
                )
                val_loss = float(torch.nn.functional.mse_loss(model(tx[val_index]), ty[val_index]))
            if not np.isfinite([train_loss, val_loss]).all():
                raise ValueError("Nonfinite NN epoch loss")
            improved = val_loss < best - settings["min_delta"]
            if improved:
                best, stale = val_loss, 0
                saved = {name: a.detach().clone() for name, a in model.state_dict().items()}
            else:
                stale += 1
            history.append(
                {
                    "epoch": epoch,
                    "training_MSE": train_loss,
                    "validation_MSE": val_loss,
                    "improved": improved,
                    "batch_order_sha256": _digest_arrays({"order": order.cpu().numpy()})["order"],
                }
            )
            if stale >= settings["patience"]:
                break
        model.load_state_dict(saved)
        weights = export_weights(model)
        validate_weights(weights, x.shape[1], settings["hidden"])
        with torch.no_grad():
            prediction = (
                model(
                    torch.tensor((forecast_x - center) / scale, dtype=torch.float32, device="cpu")
                )
                .reshape(-1)
                .cpu()
                .numpy()
                .astype(float)
            )
        if not np.isfinite(prediction).all():
            raise ValueError("Nonfinite NN forecast; no retry/fallback")
        metadata = {
            "schema": 1,
            "seed": seed,
            "member": member,
            "streams": random,
            "settings": settings,
            "backend": backend(),
            "trainer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "input_sha256": _input_hashes(x, y, forecast_x),
            "fitting_rows": len(x),
            "forecast_rows": len(forecast_x),
            "features": x.shape[1],
            "fit_indices": fit.tolist(),
            "validation_indices": validation.tolist(),
            "center_x": center.tolist(),
            "scale_x": scale.tolist(),
            "initial_parameter_sha256": initial,
            "history": history,
            **history_summary(history, settings),
            "forecast_prediction": prediction.tolist(),
            "best_checkpoint_restored": True,
        }
    return weights, metadata


def save_member(directory, weights, metadata):
    directory = Path(directory)
    if directory.exists():
        raise FileExistsError("Choose a fresh NN member directory")
    directory.mkdir(parents=True)
    np.savez_compressed(directory / "weights.npz", **weights)
    metadata = {
        **metadata,
        "weights_file_sha256": hashlib.sha256((directory / "weights.npz").read_bytes()).hexdigest(),
    }
    temporary = directory / "member.json.tmp"
    temporary.write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n")
    temporary.replace(directory / "member.json")


@threadpool_limits.wrap(limits=1)
def audit_member(directory, x, y, forecast_x, seed, member, settings, *, refit=False):
    directory = Path(directory)
    validate_training(settings)
    x, y, forecast_x, center, scale = arrays(x, y, forecast_x)
    metadata = json.loads((directory / "member.json").read_text())
    fit, validation = partition(len(x), seed, member)
    expected = {
        "schema": 1,
        "seed": seed,
        "member": member,
        "streams": streams(seed, member),
        "settings": settings,
        "backend": backend(),
        "trainer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_sha256": _input_hashes(x, y, forecast_x),
        "fitting_rows": len(x),
        "forecast_rows": len(forecast_x),
        "features": x.shape[1],
        "fit_indices": fit.tolist(),
        "validation_indices": validation.tolist(),
        "center_x": center.tolist(),
        "scale_x": scale.tolist(),
        **history_summary(metadata["history"], settings),
        "best_checkpoint_restored": True,
        "weights_file_sha256": hashlib.sha256((directory / "weights.npz").read_bytes()).hexdigest(),
    }
    if any(metadata.get(k) != v for k, v in expected.items()):
        raise ValueError("NN member inputs, split, preprocessing, history or provenance changed")
    with np.load(directory / "weights.npz", allow_pickle=False) as checkpoint:
        weights = {name: checkpoint[name] for name in checkpoint.files}
    validate_weights(weights, x.shape[1], settings["hidden"])
    fit_prediction = numpy_forward(((x - center) / scale)[fit], weights)
    val_prediction = numpy_forward(((x - center) / scale)[validation], weights)
    prediction = numpy_forward((forecast_x - center) / scale, weights)
    best_record = metadata["history"][metadata["best_epoch"] - 1]
    errors = {
        "forecast": _numeric(metadata["forecast_prediction"], prediction, "forecast traversal"),
        "best_validation_MSE": _numeric(
            np.array([best_record["validation_MSE"]]),
            np.array([np.mean((val_prediction - y[validation]) ** 2)]),
            "restored validation loss",
        ),
        "best_training_MSE": _numeric(
            np.array([best_record["training_MSE"]]),
            np.array([np.mean((fit_prediction - y[fit]) ** 2)]),
            "restored training loss",
        ),
    }
    if refit:
        repeated_weights, repeated = fit_member(x, y, forecast_x, seed, member, settings)
        if {k: v for k, v in metadata.items() if k != "weights_file_sha256"} != repeated or any(
            not np.array_equal(weights[k], repeated_weights[k]) for k in weights
        ):
            raise ValueError("Deterministic NN training/checkpoint history differs")
    return {
        "seed": seed,
        "member": member,
        "fit_rows": len(fit),
        "validation_rows": len(validation),
        **{
            k: metadata[k]
            for k in ("best_epoch", "best_validation_MSE", "epochs_trained", "stop_reason")
        },
        "weights_sha256": metadata["weights_file_sha256"],
        "metadata_sha256": hashlib.sha256((directory / "member.json").read_bytes()).hexdigest(),
        "maximum_absolute_differences": errors,
        "deterministic_refit_verified": refit,
    }
