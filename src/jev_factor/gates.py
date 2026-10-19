"""Interchangeable decision models, common validation, and full local call records."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

from jev_factor.state import MULTIPLIERS, questions_for

OPTIONS = list(MULTIPLIERS)


def validate_probabilities(probabilities: dict) -> dict[str, float]:
    if set(probabilities) != set(OPTIONS):
        raise ValueError("A gate must return every declared option and no extra options")
    array = np.array([probabilities[name] for name in OPTIONS], dtype=float)
    if not np.isfinite(array).all() or (array < 0).any() or (array > 1).any():
        raise ValueError("Probabilities must be finite numbers in [0, 1]")
    if not np.isclose(array.sum(), 1, atol=1e-5, rtol=0):
        raise ValueError("Probabilities must sum to 1; no silent renormalization")
    return dict(zip(OPTIONS, array.tolist(), strict=True))


def multiplier(probabilities: dict) -> float:
    probabilities = validate_probabilities(probabilities)
    return sum(probabilities[key] * MULTIPLIERS[key] for key in OPTIONS)


def state_features(state: dict, factor: dict) -> list[float]:
    return [
        factor["fitted_coefficient"],
        factor["current_standardized_value"],
        factor["current_fitted_contribution"],
        factor["training_partial_residual_correlation"],
        factor["recent_partial_residual_correlation"],
        float(factor["recent_sign_supports_fitted_coefficient"]),
        state["target_recent_std"] / max(state["target_long_run_std"], 1e-10),
        state["target_recent_mean"],
        state["full_model_forecast"],
    ]


def rule_gate(state: dict) -> dict:
    """Explicit heuristic control. These are decision weights, not calibrated probabilities."""
    result = {}
    for factor in state["factors"]:
        if not factor["recent_sign_supports_fitted_coefficient"]:
            values = [0.8, 0.15, 0.05]
        elif abs(factor["recent_partial_residual_correlation"]) < 0.1:
            values = [0.2, 0.6, 0.2]
        else:
            values = [0.05, 0.15, 0.8]
        result[factor["id"]] = dict(zip(OPTIONS, values, strict=True))
    return result


def learned_gate(state: dict, history: list[dict], known_through: int) -> dict:
    """Prequential multinomial logistic control, fit only on matured gate outcomes."""
    available = [r for r in history if r["label_position"] <= known_through]
    if len(available) < 30 or len({r["label"] for r in available}) < 2:
        return {f["id"]: dict.fromkeys(OPTIONS, 1 / 3) for f in state["factors"]}
    # The same numeric diagnostics are supplied to every gate. Semantic labels
    # are deliberately omitted here; metadata-only ablations test their value.
    X = np.array([r["features"] for r in available])
    mean, scale = X.mean(axis=0), X.std(axis=0)
    scale[scale < 1e-8] = 1
    model = LogisticRegression(C=1.0, max_iter=500).fit(
        (X - mean) / scale, [r["label"] for r in available]
    )
    result = {}
    for factor in state["factors"]:
        probabilities = model.predict_proba(
            (np.array([state_features(state, factor)]) - mean) / scale
        )[0]
        values = dict.fromkeys(OPTIONS, 0.0)
        values.update(dict(zip(model.classes_, probabilities.tolist(), strict=True)))
        result[factor["id"]] = validate_probabilities(values)
    return result


def winning_action(factor: dict, actual: float) -> str:
    # Enumerating in this order gives stable, declared tie handling.
    return min(
        ["retain", "weaken", "suppress"],
        key=lambda name: (actual - factor["candidate_forecasts"][name]) ** 2,
    )


class RemoteGate:
    """Use the vendor SDK and its official LLM comparison adapter.

    No model request occurs during construction. Calls are explicit and bounded
    by the experiment runner's max_api_calls. Failures abort, never masquerade
    as successful Jev forecasts. Local cache stores public research evidence only.
    """

    def __init__(self, kind: str, model: str, directory: Path, provider: str | None = None):
        self.kind, self.model, self.provider = kind, model, provider
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)

    def decide(self, state: dict, reverse_order: bool = False) -> dict:
        questions = questions_for(state, reverse_order)
        request = {
            "state": state,
            "questions": questions,
            "model": self.model,
            "kind": self.kind,
            "provider": self.provider,
            "adapter_settings": {
                "structured_outputs": True,
                "llm_answer_mode": "probabilities",
                "normalize_probabilities": False,
                "n_retry_malformed_structure": 0,
            },
        }
        serialized = json.dumps(request, sort_keys=True, allow_nan=False)
        # sort_keys preserves a canonical cache identity, but option order is
        # separately included because this is a real experimental treatment.
        digest = hashlib.sha256((serialized + str(reverse_order)).encode()).hexdigest()
        cached = self.directory / f"{digest}.json"
        if cached.exists():
            response = json.loads(cached.read_text())["response"]
        else:
            start = time.perf_counter()
            try:
                if self.kind == "jev":
                    from typesafe_sdk import TypeSafeClient

                    with TypeSafeClient() as client:
                        output = client.system_one(
                            state=state, questions=questions, model=self.model
                        )
                elif self.kind == "llm":
                    from system_one_adapter import SystemOneAdapterClient

                    with SystemOneAdapterClient(**request["adapter_settings"]) as client:
                        output = client.system_one(
                            state=state,
                            questions=questions,
                            model=self.model,
                            provider=self.provider,
                        )
                else:
                    raise ValueError("kind must be jev or llm")
                response = output.model_dump(mode="json")
            except Exception as exc:
                # Never record exception text, which may contain headers or keys.
                (self.directory / f"{digest}.error.json").write_text(
                    json.dumps(
                        {
                            "request": request,
                            "error_type": type(exc).__name__,
                            "elapsed_seconds": time.perf_counter() - start,
                        },
                        indent=2,
                    )
                    + "\n"
                )
                raise
            cached.write_text(
                json.dumps(
                    {
                        "request": request,
                        "response": response,
                        "elapsed_seconds": time.perf_counter() - start,
                    },
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            )
        answers = response["answers"]
        if set(answers) != {f["id"] for f in state["factors"]}:
            raise ValueError("Remote gate returned missing or extra factor answers")
        return {
            name: validate_probabilities(answer["probabilities"])
            for name, answer in answers.items()
        }
