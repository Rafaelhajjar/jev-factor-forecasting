"""Walk-forward evaluation with explicit label maturation and saved provenance."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from jev_factor.data import load_fred, synthetic
from jev_factor.gates import (
    OPTIONS,
    RemoteGate,
    learned_gate,
    multiplier,
    rule_gate,
    state_features,
    winning_action,
)
from jev_factor.models import conventional, fit_factor
from jev_factor.state import PROMPT_VERSION, build_state, prepare_origin


def json_write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


@threadpool_limits.wrap(limits=1)
def run(
    config: dict,
    output: Path,
    *,
    api: dict | None = None,
    max_origins: int | None = None,
    max_api_calls: int = 0,
) -> dict:
    if output.exists():
        raise ValueError(f"Run directory already exists: {output}; choose a new one")
    remote_methods = set(config["methods"]) & {"gate_jev", "gate_llm"}
    if remote_methods and (not api or max_api_calls < 1):
        raise ValueError("Remote methods require explicit API settings and --max-api-calls")
    if "gate_jev" in remote_methods and "latest" in api.get("jev_model", ""):
        raise ValueError("Pin a versioned Jev model for reproducible experiments")
    if "gate_llm" in remote_methods and not api.get("llm_model"):
        raise ValueError("An explicit LLM model ID is required")
    output.mkdir(parents=True)
    json_write(
        output / "config.json",
        {**config, "api": api, "max_origins": max_origins, "max_api_calls": max_api_calls},
    )
    rows, gate_rows, states, datasets = [], [], [], []
    calls = 0
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except subprocess.CalledProcessError:
        revision = "uncommitted"
    for seed in config["seeds"]:
        if config["dataset"] == "synthetic":
            data = synthetic(seed, config["n_samples"])
            start = config["test_start"]
        elif config["dataset"] == "fred_md":
            data = load_fred(
                Path(config["path"]), config["target"], config["start_date"], config["end_date"]
            )
            start = int(data.y.index.searchsorted(pd.Timestamp(config["test_start_date"])))
        else:
            raise ValueError("Unknown dataset")
        datasets.append(data.metadata)
        origins = list(range(start, len(data.y) - config["horizon"], config["step"]))
        if max_origins is not None:
            origins = origins[:max_origins]
        history = []
        for origin in origins:
            prepared = prepare_origin(data, origin, config)
            fitted = fit_factor(prepared, config["ridge_alpha"])
            state = build_state(prepared, fitted, config["recent_window"], config["horizon"])
            if config.get("anonymize", False):
                for factor in state["factors"]:
                    factor["description"] = "Anonymous predictor; use supplied diagnostics."
            # State contains no dates: historical macro recall should not be
            # enough to identify the future. This cannot prove no contamination.
            state_json = json.dumps(state, sort_keys=True, allow_nan=False)
            state_hash = hashlib.sha256(state_json.encode()).hexdigest()
            states.append(
                {
                    "seed": seed,
                    "origin": origin,
                    "state_sha256": state_hash,
                    "last_training_label_position": prepared.last_label_position,
                    "state": state,
                }
            )
            pending_predictions = []
            pending_probabilities = []
            for method in config["methods"]:
                start_clock = time.perf_counter()
                if method.startswith("gate_"):
                    if method == "gate_rule":
                        probabilities = rule_gate(state)
                    elif method == "gate_learned":
                        probabilities = learned_gate(state, history, origin - config["data_lag"])
                    elif method in {"gate_jev", "gate_llm"}:
                        if calls >= max_api_calls:
                            raise ValueError("Explicit API request budget exhausted; run stopped")
                        kind = method.removeprefix("gate_")
                        gate = RemoteGate(
                            kind,
                            api[f"{kind}_model"],
                            output / "api_cache",
                            api.get("llm_provider") if kind == "llm" else None,
                        )
                        probabilities = gate.decide(state, config.get("reverse_options", False))
                        calls += 1
                    else:
                        raise ValueError(f"Unknown gate: {method}")
                    weights = np.array(
                        [multiplier(probabilities[f["id"]]) for f in state["factors"]]
                    )
                    prediction = float(
                        fitted.intercept_
                        + prepared.current_f[0, :3] @ fitted.coef_[:3]
                        + (prepared.current_f[0, 3:] * fitted.coef_[3:] * weights).sum()
                    )
                    pending_probabilities.append((method, probabilities))
                else:
                    prediction = conventional(method, prepared, fitted, config, seed)
                if not np.isfinite(prediction):
                    raise ValueError(f"Non-finite prediction from {method}")
                pending_predictions.append((method, prediction, time.perf_counter() - start_clock))
            # The evaluator reads the outcome only AFTER all forecasts are fixed.
            label_position = origin + config["horizon"]
            actual = float(data.y.iloc[label_position])
            if not np.isfinite(actual):
                raise ValueError("Evaluation target is missing; select complete target origins")
            for method, prediction, elapsed in pending_predictions:
                rows.append(
                    {
                        "dataset": config["dataset"],
                        "seed": seed,
                        "origin": origin,
                        "origin_date": str(data.y.index[origin].date()),
                        "label_position": label_position,
                        "horizon": config["horizon"],
                        "method": method,
                        "actual": actual,
                        "prediction": prediction,
                        "squared_error": (actual - prediction) ** 2,
                        "absolute_error": abs(actual - prediction),
                        "model_seconds": elapsed,
                        "state_sha256": state_hash,
                    }
                )
            for factor in state["factors"]:
                label = winning_action(factor, actual)
                history.append(
                    {
                        "features": state_features(state, factor),
                        "label": label,
                        "label_position": label_position,
                    }
                )
                for method, probabilities in pending_probabilities:
                    values = probabilities[factor["id"]]
                    gate_rows.append(
                        {
                            "seed": seed,
                            "origin": origin,
                            "factor": factor["id"],
                            "method": method,
                            "winning_action": label,
                            "brier_multiclass": sum(
                                (values[k] - float(k == label)) ** 2 for k in OPTIONS
                            ),
                            "log_loss": float(-np.log(max(values[label], 1e-12))),
                            "multiplier": multiplier(values),
                            **{f"p_{k}": v for k, v in values.items()},
                        }
                    )
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("No evaluation origins selected")
    frame.to_csv(output / "predictions.csv", index=False)
    per_seed = (
        frame.groupby(["method", "seed"])
        .agg(
            mse=("squared_error", "mean"),
            mae=("absolute_error", "mean"),
            n=("squared_error", "size"),
            model_seconds=("model_seconds", "sum"),
        )
        .reset_index()
    )
    per_seed.to_csv(output / "metrics_by_seed.csv", index=False)
    summary = (
        frame.groupby("method")
        .agg(
            mse=("squared_error", "mean"),
            mae=("absolute_error", "mean"),
            n=("squared_error", "size"),
            model_seconds=("model_seconds", "sum"),
        )
        .reset_index()
    )
    summary["rmse"] = np.sqrt(summary.mse)
    summary.to_csv(output / "metrics.csv", index=False)
    if gate_rows:
        pd.DataFrame(gate_rows).to_csv(output / "gate_metrics.csv", index=False)
    json_write(output / "states.json", states)
    manifest = {
        "created_utc": datetime.now(UTC).isoformat(),
        "git_revision": revision,
        "python": platform.python_version(),
        "prompt_version": PROMPT_VERSION,
        "datasets": datasets,
        "api_calls": calls,
        "complete": True,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ["numpy", "pandas", "scikit-learn", "httpx"]
        },
    }
    json_write(output / "manifest.json", manifest)
    return {
        "output": str(output),
        "api_calls": calls,
        "metrics": summary.sort_values("mse").to_dict(orient="records"),
    }
