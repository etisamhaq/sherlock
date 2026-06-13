"""LLM client protocol + the synthesis context passed to it."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from ..models import AlertEvent, FailureMode, Finding, RootCauseAnalysis


class SynthesisContext(BaseModel):
    """Everything the LLM needs to synthesize a root cause, grounded in real data."""

    incident: AlertEvent
    failure_mode: FailureMode
    findings: list[Finding]


class LLMClient(Protocol):
    """A root-cause synthesizer. Implementations: AnthropicLLM, FakeLLM."""

    def analyze_root_cause(self, ctx: SynthesisContext) -> RootCauseAnalysis:
        """Return a ranked, evidence-cited analysis. Must never bluff: set
        ``needs_human=True`` when the evidence is too weak to assert a cause."""
        ...

    def tokens_spent(self) -> int:
        """Output tokens spent on the most recent call (0 for the fake engine)."""
        ...
