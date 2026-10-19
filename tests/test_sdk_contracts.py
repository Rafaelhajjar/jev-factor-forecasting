"""Exercise real SDK serialization/parsing with local transports, never hosted inference."""

import json

import pytest


def test_real_jev_sdk_serialization():
    httpx = pytest.importorskip("httpx2")
    sdk = pytest.importorskip("typesafe_sdk")
    from jev_factor.state import questions_for

    state = {"factors": [{"id": "factor_0"}]}
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {
                    "factor_0": {
                        "type": "choice",
                        "choice": "retain",
                        "confidence": 0.7,
                        "probabilities": {"suppress": 0.1, "weaken": 0.1, "retain": 0.8},
                    }
                },
                "usage": {"input_tokens": 100, "output_tokens": 10},
            },
        )

    with sdk.TypeSafeClient(
        api_key="local-test-placeholder", transport=httpx.MockTransport(handler), compression=False
    ) as client:
        result = client.system_one(state=state, questions=questions_for(state), model="jev-1.13.0")
    assert captured[0]["questions"]["factor_0"]["type"] == "choice"
    assert result.model == "jev-1.13.0"
    assert result.answers["factor_0"].probabilities["retain"] == 0.8


def test_real_llm_adapter_serialization():
    adapter = pytest.importorskip("system_one_adapter")
    from system_one_adapter.providers import ProviderResult

    captured = []

    class LocalProvider:
        model_name = "local-contract-fixture"

        def request(self, messages, *, schema, structured):
            captured.append((messages, schema, structured))
            return ProviderResult(
                text=json.dumps(
                    {"answers": {"factor_0": {"suppress": 0.1, "weaken": 0.1, "retain": 0.8}}}
                ),
                input_tokens=100,
                output_tokens=10,
            )

        def translate_error(self, error):
            return error

    with adapter.SystemOneAdapterClient(
        structured_outputs=True,
        llm_answer_mode="probabilities",
        normalize_probabilities=False,
        n_retry_malformed_structure=0,
    ) as client:
        result = client.system_one(
            state="A public research fixture",
            model=LocalProvider(),
            questions={
                "factor_0": {
                    "type": "choice",
                    "instructions": "Choose action",
                    "criteria": {"suppress": None, "weaken": None, "retain": None},
                }
            },
        )
    assert captured[0][2] is True
    assert result.answers["factor_0"].probabilities["retain"] == 0.8
