"""Groq Cloud-backed root-cause synthesis (primary provider).

Uses Groq's OpenAI-compatible chat completions with JSON mode, then validates
the output against the ``RootCauseAnalysis`` schema with Pydantic. Falls back to
the deterministic engine if Groq errors or returns unparseable JSON.

Reuses the same system prompt + context renderer as the Anthropic client, so the
two providers behave consistently.
"""

from __future__ import annotations

import json

from ..models import RootCauseAnalysis
from .anthropic_client import _SYSTEM, _render_context
from .base import SynthesisContext
from .fake import FakeLLM

# Groq's JSON mode needs the word "json" in the prompt and benefits from an
# explicit shape, since it has no Pydantic-aware parse helper across all models.
_JSON_INSTRUCTION = """

Respond with a single JSON object (and nothing else) matching exactly this shape:
{
  "summary": "<one-paragraph human summary>",
  "failure_mode": "CrashLoopBackOff" | "OOMKilled" | "FailedDeploy" | "Pending" | "Unknown",
  "hypotheses": [
    {
      "cause": "<one-line likely cause>",
      "confidence": "low" | "medium" | "high",
      "explanation": "<why the evidence points here>",
      "evidence": ["<supporting evidence>", "..."],
      "suggested_fix": "<concrete, safe, reversible remediation>"
    }
  ],
  "overall_confidence": "low" | "medium" | "high",
  "needs_human": true | false
}
Rank hypotheses strongest-first. If evidence is too weak to assert a cause, set
needs_human=true and return an empty or low-confidence hypotheses list."""


def _coerce_json(content: str) -> str:
    """Return the JSON object substring from a model response, best-effort."""
    content = content.strip()
    if content.startswith("{"):
        return content
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        return content[start : end + 1]
    return content


class GroqLLM:
    def __init__(self, model: str = "llama-3.3-70b-versatile", api_key: str = "") -> None:
        from groq import Groq  # lazy import so the package installs without the key

        self.model = model
        self._client = Groq(api_key=api_key or None)
        self._tokens = 0
        self._fallback = FakeLLM(reason="Groq unavailable, used heuristics")

    def tokens_spent(self) -> int:
        return self._tokens

    def analyze_root_cause(self, ctx: SynthesisContext) -> RootCauseAnalysis:
        self._tokens = 0
        user = _render_context(ctx)
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM + _JSON_INSTRUCTION},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                max_tokens=2048,
                temperature=0.2,
            )
        except Exception:  # noqa: BLE001 - any Groq/network error → heuristics
            return self._fallback.analyze_root_cause(ctx)

        usage = getattr(resp, "usage", None)
        if usage is not None:
            self._tokens = int(getattr(usage, "completion_tokens", 0) or 0)

        try:
            content = resp.choices[0].message.content or ""
        except (AttributeError, IndexError):
            return self._fallback.analyze_root_cause(ctx)

        try:
            analysis = RootCauseAnalysis.model_validate_json(_coerce_json(content))
        except Exception:  # noqa: BLE001 - malformed JSON → heuristics, never crash
            return self._fallback.analyze_root_cause(ctx)

        if analysis.failure_mode is None:  # pragma: no cover - defensive
            analysis.failure_mode = ctx.failure_mode
        return analysis
