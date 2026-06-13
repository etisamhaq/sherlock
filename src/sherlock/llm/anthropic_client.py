"""Claude-backed root-cause synthesis.

Uses the Anthropic Python SDK's structured-output path (``messages.parse``) so
the model is forced to return a validated ``RootCauseAnalysis`` — no brittle JSON
parsing. Defaults to ``claude-opus-4-8`` (the reasoning-heavy tier) with adaptive
thinking; falls back to the deterministic engine if the API refuses or errors.
"""

from __future__ import annotations

import json

from ..models import RootCauseAnalysis
from .base import SynthesisContext
from .fake import FakeLLM

_SYSTEM = """You are Sherlock, an expert Site Reliability Engineer doing root-cause \
analysis of a Kubernetes incident.

You are given an alert, the failure mode, and findings gathered from the live \
cluster (pod state, events, logs), from Prometheus metrics, and from the recent \
deploy history ("what changed").

Rules:
- Ground every claim in the provided findings. Do NOT invent evidence, metrics, \
or deploys that are not in the input.
- The single highest-signal cause of a sudden failure is usually a recent change/deploy. \
Weigh "what changed" heavily when it correlates in time.
- Rank hypotheses by confidence. Cite the specific evidence for each.
- Propose a concrete, safe, reversible fix (rollback, raise a limit, restart, scale) — \
never a destructive one.
- If the evidence is too weak to assert a cause, set needs_human=true and say what's missing. \
Never bluff a confident root cause you cannot support."""


def _render_context(ctx: SynthesisContext) -> str:
    lines = [
        f"## Alert\nTitle: {ctx.incident.title}",
        f"Namespace: {ctx.incident.namespace}",
        f"Workload: {ctx.incident.workload}",
        f"Severity: {ctx.incident.severity.value}",
        f"Classified failure mode: {ctx.failure_mode.value}",
        "\n## Findings",
    ]
    for f in ctx.findings:
        lines.append(f"\n### {f.investigator}")
        if f.error:
            lines.append(f"(investigator error: {f.error})")
        lines.append(f.summary or "(no summary)")
        if f.signals:
            lines.append(f"signals: {json.dumps(f.signals, default=str)}")
        for e in f.evidence:
            link = f" <{e.link}>" if e.link else ""
            lines.append(f"- [{e.source}] {e.summary}{link}")
            if e.detail:
                # Keep detail bounded — logs can be huge.
                lines.append(f"    {e.detail[:1500]}")
    return "\n".join(lines)


class AnthropicLLM:
    def __init__(self, model: str = "claude-opus-4-8", api_key: str = "") -> None:
        import anthropic  # imported lazily so the package installs without a key

        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key or None)
        self._tokens = 0
        self._fallback = FakeLLM(reason="LLM unavailable, used heuristics")

    def tokens_spent(self) -> int:
        return self._tokens

    def analyze_root_cause(self, ctx: SynthesisContext) -> RootCauseAnalysis:
        import anthropic

        self._tokens = 0
        user = _render_context(ctx)
        try:
            resp = self._client.messages.parse(
                model=self.model,
                max_tokens=4096,
                system=_SYSTEM,
                messages=[{"role": "user", "content": user}],
                output_format=RootCauseAnalysis,
                thinking={"type": "adaptive"},
            )
        except anthropic.APIError:
            # Network/auth/parse failure — degrade to the heuristic engine.
            return self._fallback.analyze_root_cause(ctx)

        usage = getattr(resp, "usage", None)
        if usage is not None:
            self._tokens = int(getattr(usage, "output_tokens", 0) or 0)

        if getattr(resp, "stop_reason", None) == "refusal":
            analysis = self._fallback.analyze_root_cause(ctx)
            analysis.needs_human = True
            analysis.summary = "Model declined to analyze this input; falling back to heuristics. " + analysis.summary
            return analysis

        parsed = getattr(resp, "parsed_output", None)
        if parsed is None:
            return self._fallback.analyze_root_cause(ctx)
        # Ensure the failure mode is set even if the model omitted it.
        if parsed.failure_mode is None:  # pragma: no cover - defensive
            parsed.failure_mode = ctx.failure_mode
        return parsed
