"""Unit tests for the Groq client — parsing, token tracking, and fallback.

The Groq HTTP client is replaced with a fake, so these run offline.
"""

import json
from types import SimpleNamespace

from sherlock.llm.base import SynthesisContext
from sherlock.llm.groq_client import GroqLLM
from sherlock.models import AlertEvent, FailureMode, Finding


def _fake_response(content: str, completion_tokens: int = 42):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(completion_tokens=completion_tokens),
    )


class _FakeGroqClient:
    def __init__(self, content=None, raise_error=False):
        self._content = content
        self._raise = raise_error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        if self._raise:
            raise RuntimeError("groq down")
        return _fake_response(self._content)


def _ctx():
    return SynthesisContext(
        incident=AlertEvent(source="t", title="OOM", namespace="prod", workload="api"),
        failure_mode=FailureMode.oom_killed,
        findings=[Finding(investigator="kubernetes", summary="oom", signals={"oom_killed": True})],
    )


def _llm_with(client):
    llm = GroqLLM.__new__(GroqLLM)  # skip __init__ (avoids importing/constructing real client)
    llm.model = "llama-3.3-70b-versatile"
    llm._client = client
    llm._tokens = 0
    from sherlock.llm.fake import FakeLLM

    llm._fallback = FakeLLM(reason="test")
    return llm


def test_parses_valid_json_and_tracks_tokens():
    payload = json.dumps(
        {
            "summary": "OOMKilled by a recent deploy.",
            "failure_mode": "OOMKilled",
            "hypotheses": [
                {
                    "cause": "deploy lowered memory limit",
                    "confidence": "high",
                    "explanation": "limit dropped to 256Mi just before failures",
                    "evidence": ["reason=OOMKilled", "deploy a1b2c3d4"],
                    "suggested_fix": "revert the deploy",
                }
            ],
            "overall_confidence": "high",
            "needs_human": False,
        }
    )
    llm = _llm_with(_FakeGroqClient(content=payload))
    rca = llm.analyze_root_cause(_ctx())
    assert rca.overall_confidence == "high"
    assert rca.failure_mode is FailureMode.oom_killed
    assert rca.hypotheses[0].cause == "deploy lowered memory limit"
    assert llm.tokens_spent() == 42


def test_extracts_json_wrapped_in_prose():
    content = 'Here is the analysis:\n{"summary":"x","failure_mode":"Pending","hypotheses":[],"overall_confidence":"low","needs_human":true}\nDone.'
    llm = _llm_with(_FakeGroqClient(content=content))
    rca = llm.analyze_root_cause(_ctx())
    assert rca.failure_mode is FailureMode.pending
    assert rca.needs_human is True


def test_malformed_json_falls_back_to_heuristics():
    llm = _llm_with(_FakeGroqClient(content="not json at all"))
    rca = llm.analyze_root_cause(_ctx())
    # fell back to the deterministic engine, which still produces an OOM hypothesis
    assert rca.failure_mode is FailureMode.oom_killed
    assert rca.hypotheses


def test_api_error_falls_back():
    llm = _llm_with(_FakeGroqClient(raise_error=True))
    rca = llm.analyze_root_cause(_ctx())
    assert rca.hypotheses  # heuristic fallback, no crash
