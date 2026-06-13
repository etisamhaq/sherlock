"""The incident orchestrator — Sherlock's entry point.

Lifecycle (deterministic scaffolding around the stochastic synthesis step):

    intake → investigate (parallel) → classify → budget-check → synthesize → result

Investigators run concurrently (latency matters at 3 AM). The LLM synthesis is
the only stochastic step and is bounded by the token/time budget.
"""

from __future__ import annotations

import asyncio
import time

from .budget import Budget, BudgetExceeded
from .classify import classify
from .clients.kubernetes_client import KubernetesReader
from .clients.prometheus_client import PrometheusReader
from .clients.git_client import GitReader
from .investigators import (
    ChangeInvestigator,
    Investigator,
    KubernetesInvestigator,
    MetricsInvestigator,
)
from .llm.base import LLMClient, SynthesisContext
from .models import AlertEvent, FailureMode, Finding, Investigation, RootCauseAnalysis
from .trace import Trace


async def investigate_async(
    incident: AlertEvent,
    *,
    k8s: KubernetesReader,
    llm: LLMClient,
    prometheus: PrometheusReader | None = None,
    git: GitReader | None = None,
    budget: Budget | None = None,
) -> Investigation:
    budget = budget or Budget()
    trace = Trace()
    start = time.monotonic()
    trace.add("intake", workload=incident.workload, namespace=incident.namespace, source=incident.source)

    investigators: list[Investigator] = [
        KubernetesInvestigator(k8s),
        MetricsInvestigator(prometheus),
        ChangeInvestigator(git),
    ]

    # Run investigators concurrently — each is sync, so offload to threads.
    findings: list[Finding] = await asyncio.gather(
        *(asyncio.to_thread(inv.investigate, incident) for inv in investigators)
    )
    for f in findings:
        trace.add("investigator", name=f.investigator, evidence_count=len(f.evidence), error=f.error or None)

    # Classify from live pod state (best-effort).
    pods: list[dict] = []
    try:
        pods = k8s.list_workload_pods(incident.namespace, incident.workload)
    except Exception as exc:  # noqa: BLE001
        trace.add("classify_fetch_failed", error=str(exc))
    mode = classify(incident, pods)
    trace.add("classify", failure_mode=mode.value)

    # Budget gate before the expensive synthesis step.
    try:
        budget.check()
        ctx = SynthesisContext(incident=incident, failure_mode=mode, findings=list(findings))
        analysis = llm.analyze_root_cause(ctx)
        budget.add_tokens(llm.tokens_spent())
        trace.add("synthesize", tokens=llm.tokens_spent(), confidence=analysis.overall_confidence)
    except BudgetExceeded as exc:
        trace.add("budget_exceeded", reason=str(exc))
        analysis = RootCauseAnalysis(
            summary=f"Investigation halted by budget guardrail: {exc}. Raw findings preserved for a human.",
            failure_mode=mode,
            needs_human=True,
        )

    if analysis.failure_mode is FailureMode.unknown:
        analysis.failure_mode = mode

    duration_ms = int((time.monotonic() - start) * 1000)
    return Investigation(
        incident=incident,
        failure_mode=mode,
        findings=list(findings),
        analysis=analysis,
        duration_ms=duration_ms,
        tokens_spent=budget.tokens_spent,
        trace=trace.to_list(),
    )


def investigate(incident: AlertEvent, **kwargs) -> Investigation:
    """Synchronous wrapper around :func:`investigate_async` (for the CLI)."""
    return asyncio.run(investigate_async(incident, **kwargs))
