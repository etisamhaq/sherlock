"""End-to-end orchestrator tests across all four MVP failure modes (offline)."""

import pytest

from sherlock.budget import Budget
from sherlock.llm.fake import FakeLLM
from sherlock.models import AlertEvent, FailureMode
from sherlock.orchestrator import investigate_async

from .fakes import (
    FakeGitClient,
    FakeKubernetesClient,
    FakePrometheusClient,
    crashloop_pod,
    imagepull_pod,
    oom_pod,
    pending_pod,
    sample_commits,
)


def _alert(title="alert", workload="api"):
    return AlertEvent(source="t", title=title, namespace="prod", workload=workload)


async def test_oom_end_to_end_with_what_changed():
    k8s = FakeKubernetesClient(
        pods=[oom_pod()],
        events=[{"type": "Warning", "reason": "BackOff", "message": "Back-off restarting failed container"}],
        logs="java.lang.OutOfMemoryError: Java heap space",
    )
    git = FakeGitClient(commits=sample_commits())
    prom = FakePrometheusClient(
        results={"container_memory_working_set_bytes": [{"value": [0, "260000000"]}]}
    )

    inv = await investigate_async(_alert("OOM"), k8s=k8s, llm=FakeLLM(), prometheus=prom, git=git)

    assert inv.failure_mode is FailureMode.oom_killed
    assert inv.analysis.overall_confidence == "high"  # deploy correlated → high
    assert inv.analysis.hypotheses
    assert "a1b2c3d4" in inv.analysis.hypotheses[0].cause or "deploy" in inv.analysis.hypotheses[0].cause.lower()
    # trace records the pipeline
    steps = [s["step"] for s in inv.trace]
    assert "intake" in steps and "classify" in steps and "synthesize" in steps
    # three investigators ran
    assert {f.investigator for f in inv.findings} == {"kubernetes", "metrics", "change"}


async def test_crashloop_end_to_end():
    k8s = FakeKubernetesClient(pods=[crashloop_pod()], logs="panic: nil pointer dereference")
    inv = await investigate_async(_alert("CrashLoop"), k8s=k8s, llm=FakeLLM())
    assert inv.failure_mode is FailureMode.crash_loop
    assert inv.analysis.hypotheses


async def test_pending_end_to_end():
    k8s = FakeKubernetesClient(
        pods=[pending_pod()],
        events=[{"type": "Warning", "reason": "FailedScheduling", "message": "0/3 nodes: Insufficient cpu"}],
    )
    inv = await investigate_async(_alert("Pending"), k8s=k8s, llm=FakeLLM())
    assert inv.failure_mode is FailureMode.pending
    assert inv.analysis.hypotheses


async def test_failed_deploy_end_to_end():
    k8s = FakeKubernetesClient(pods=[imagepull_pod()])
    inv = await investigate_async(_alert("rollout failed"), k8s=k8s, llm=FakeLLM(), git=FakeGitClient(sample_commits()))
    assert inv.failure_mode is FailureMode.failed_deploy
    assert inv.analysis.hypotheses


async def test_resilient_when_kube_unreachable():
    # k8s list fails for classification AND investigation — must still return a result.
    k8s = FakeKubernetesClient(raise_on_list=True)
    inv = await investigate_async(_alert("mystery"), k8s=k8s, llm=FakeLLM())
    assert inv.failure_mode is FailureMode.unknown
    assert inv.analysis.needs_human is True


async def test_budget_exhaustion_halts_synthesis():
    k8s = FakeKubernetesClient(pods=[oom_pod()])
    spent = Budget(token_budget=10)
    spent.add_tokens(20)  # already over budget before synthesis
    inv = await investigate_async(_alert("OOM"), k8s=k8s, llm=FakeLLM(), budget=spent)
    assert inv.analysis.needs_human is True
    assert "budget" in inv.analysis.summary.lower()


async def test_git_investigator_failure_does_not_sink_run():
    k8s = FakeKubernetesClient(pods=[oom_pod()])
    inv = await investigate_async(_alert("OOM"), k8s=k8s, llm=FakeLLM(), git=FakeGitClient(raise_error=True))
    assert inv.failure_mode is FailureMode.oom_killed  # still classified
    change = next(f for f in inv.findings if f.investigator == "change")
    assert change.error  # error captured on the finding
