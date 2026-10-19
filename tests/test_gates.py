import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from jev_factor.data import synthetic
from jev_factor.gates import (
    OPTIONS,
    RemoteGate,
    learned_gate,
    multiplier,
    state_features,
    validate_probabilities,
    winning_action,
)
from jev_factor.models import fit_factor
from jev_factor.state import build_state, prepare_origin, questions_for


def sample_state():
    config = json.loads(Path("configs/synthetic.json").read_text())
    prepared = prepare_origin(synthetic(), 250, config)
    return build_state(prepared, fit_factor(prepared, 10), 48, 1)


@pytest.mark.parametrize(
    "probabilities",
    [
        {"suppress": -0.1, "weaken": 0.2, "retain": 0.9},
        {"suppress": 0, "weaken": 0.2, "retain": 0.7},
        {"suppress": 0, "weaken": np.nan, "retain": 1},
        {"suppress": 0, "retain": 1},
        {"suppress": 0, "weaken": 0, "retain": 1, "unknown": 0},
    ],
)
def test_rejects_invalid_distributions(probabilities):
    with pytest.raises(ValueError):
        validate_probabilities(probabilities)


def test_weighted_action_policy():
    assert multiplier({"suppress": 0.2, "weaken": 0.4, "retain": 0.4}) == pytest.approx(0.6)


def test_action_label_and_tie_policy():
    factor = {"candidate_forecasts": {"suppress": 0.0, "weaken": 1.0, "retain": 2.0}}
    assert winning_action(factor, 0.1) == "suppress"
    assert winning_action(factor, 1.1) == "weaken"
    assert winning_action(factor, 1.5) == "retain"
    factor["candidate_forecasts"] = dict.fromkeys(OPTIONS, 1.0)
    assert winning_action(factor, 1.0) == "retain"


def test_question_ids_are_explicit_in_instructions():
    state = sample_state()
    forward, reverse = questions_for(state), questions_for(state, reverse_order=True)
    for factor in state["factors"]:
        name = factor["id"]
        assert name in forward[name]["instructions"]
        assert list(forward[name]["criteria"]) == list(reversed(reverse[name]["criteria"]))


def test_learned_gate_cannot_use_unmatured_labels():
    state = sample_state()
    history = [
        {
            "features": state_features(state, state["factors"][i % 4]),
            "label": OPTIONS[i % 3],
            "label_position": 500,
        }
        for i in range(60)
    ]
    result = learned_gate(state, history, known_through=250)
    assert all(values == dict.fromkeys(OPTIONS, 1 / 3) for values in result.values())


def test_remote_sdk_contract_and_cache_without_network(tmp_path, monkeypatch):
    sdk = pytest.importorskip("typesafe_sdk")
    state = sample_state()
    calls = []
    response = {
        "model": "jev-1.13.0",
        "usage": {"input_tokens": 10},
        "answers": {
            f["id"]: {
                "type": "choice",
                "choice": "retain",
                "confidence": 0.7,
                "probabilities": {"suppress": 0.1, "weaken": 0.1, "retain": 0.8},
            }
            for f in state["factors"]
        },
    }

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def system_one(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(model_dump=lambda **_: response)

    monkeypatch.setattr(sdk, "TypeSafeClient", Client)
    gate = RemoteGate("jev", "jev-1.13.0", tmp_path)
    first = gate.decide(state)
    assert gate.decide(state) == first
    assert len(calls) == 1
    gate.decide(state, reverse_order=True)
    assert len(calls) == 2
    cached = list(tmp_path.glob("*.json"))
    assert len(cached) == 2
    assert json.loads(cached[0].read_text())["response"]["model"] == "jev-1.13.0"


def test_remote_failure_is_recorded_and_not_replaced(tmp_path, monkeypatch):
    sdk = pytest.importorskip("typesafe_sdk")

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def system_one(self, **kwargs):
            raise RuntimeError("This message may contain credentials and must not be saved")

    monkeypatch.setattr(sdk, "TypeSafeClient", Client)
    with pytest.raises(RuntimeError):
        RemoteGate("jev", "jev-1.13.0", tmp_path).decide(sample_state())
    records = list(tmp_path.glob("*.error.json"))
    assert len(records) == 1
    assert "credentials" not in records[0].read_text()
    assert json.loads(records[0].read_text())["error_type"] == "RuntimeError"
