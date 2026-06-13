"""Deterministic, offline root-cause engine.

Used when no API key is present, when ``SHERLOCK_LLM_PROVIDER=fake``, and in
every test. It encodes the same heuristics a senior SRE applies to the four MVP
failure modes, so the tool produces a genuinely useful (if less nuanced) result
without an LLM — and the demo/CI never depend on a network call.
"""

from __future__ import annotations

from ..models import (
    Confidence,
    FailureMode,
    Finding,
    Hypothesis,
    RootCauseAnalysis,
)
from .base import SynthesisContext


def _signal(findings: list[Finding], key: str, default=None):
    for f in findings:
        if key in f.signals:
            return f.signals[key]
    return default


def _evidence_summaries(findings: list[Finding]) -> list[str]:
    out: list[str] = []
    for f in findings:
        for e in f.evidence:
            out.append(f"[{e.source}] {e.summary}")
    return out


class FakeLLM:
    def __init__(self, reason: str = "") -> None:
        self._reason = reason

    def tokens_spent(self) -> int:
        return 0

    def analyze_root_cause(self, ctx: SynthesisContext) -> RootCauseAnalysis:
        findings = ctx.findings
        mode = ctx.failure_mode
        ev = _evidence_summaries(findings)
        recent_deploy = _signal(findings, "recent_deploy")

        hypotheses: list[Hypothesis] = []
        confidence: Confidence = "low"
        summary = ""

        if mode is FailureMode.oom_killed:
            confidence = "high" if recent_deploy else "medium"
            limit = _signal(findings, "memory_limit")
            cause = "Container was OOMKilled — memory usage exceeded its limit"
            if recent_deploy:
                cause += f", and a recent deploy ({recent_deploy}) likely changed the limit or memory footprint"
            hypotheses.append(
                Hypothesis(
                    cause=cause,
                    confidence=confidence,
                    explanation=(
                        "The pod's last termination reason is OOMKilled. "
                        + (f"The memory limit is {limit}. " if limit else "")
                        + ("A deploy happened shortly before the incident, which is the highest-signal cause."
                           if recent_deploy else
                           "No recent deploy correlated, so this is likely organic growth or a leak.")
                    ),
                    evidence=ev,
                    suggested_fix=(
                        f"Revert {recent_deploy} or raise the memory limit; "
                        "then profile the workload's real memory footprint."
                        if recent_deploy
                        else "Raise the memory limit to fit observed usage, then investigate for a leak."
                    ),
                )
            )
            summary = "The workload is being OOMKilled (out-of-memory). " + (
                f"A recent deploy ({recent_deploy}) is the most likely trigger."
                if recent_deploy else
                "No recent deploy correlated; suspect organic growth or a memory leak."
            )

        elif mode is FailureMode.crash_loop:
            confidence = "high" if recent_deploy else "medium"
            exit_code = _signal(findings, "exit_code")
            cause = "Container is crash-looping on startup"
            if recent_deploy:
                cause += f", coinciding with deploy {recent_deploy}"
            hypotheses.append(
                Hypothesis(
                    cause=cause,
                    confidence=confidence,
                    explanation=(
                        f"The container repeatedly exits (exit code {exit_code}) and Kubernetes "
                        "backs off restarts. "
                        + (f"Deploy {recent_deploy} landed just before the failures began, making a "
                           "bad image/config/migration the leading cause."
                           if recent_deploy else
                           "No deploy correlated; suspect a config/secret/dependency change or a failing readiness path.")
                    ),
                    evidence=ev,
                    suggested_fix=(
                        f"Roll back {recent_deploy} and inspect its diff for the startup-breaking change."
                        if recent_deploy
                        else "Inspect the crash logs/exit code; check config, secrets, and upstream dependencies."
                    ),
                )
            )
            summary = "The workload is in CrashLoopBackOff. " + (
                f"Deploy {recent_deploy} is the most likely trigger."
                if recent_deploy else
                "No recent deploy correlated; suspect config or a dependency."
            )

        elif mode is FailureMode.failed_deploy:
            confidence = "high"
            hypotheses.append(
                Hypothesis(
                    cause=f"A recent deploy ({recent_deploy or 'unknown'}) failed to roll out",
                    confidence=confidence,
                    explanation=(
                        "New pods from the latest rollout are not becoming ready, so the Deployment "
                        "is stuck. The change in the latest deploy is the cause until proven otherwise."
                    ),
                    evidence=ev,
                    suggested_fix=(
                        f"Roll back to the previous revision (kubectl rollout undo), then inspect "
                        f"{recent_deploy or 'the latest deploy'} for the breaking change."
                    ),
                )
            )
            summary = "A deployment rollout is failing — new pods aren't reaching readiness."

        elif mode is FailureMode.pending:
            confidence = "medium"
            reason = _signal(findings, "pending_reason", "unschedulable")
            hypotheses.append(
                Hypothesis(
                    cause=f"Pods are stuck Pending ({reason})",
                    confidence=confidence,
                    explanation=(
                        "The scheduler cannot place the pods. The most common causes are insufficient "
                        "cluster resources (CPU/memory), node taints/affinity that no node satisfies, or "
                        "an unbound PersistentVolumeClaim."
                    ),
                    evidence=ev,
                    suggested_fix=(
                        "Check node capacity and the pod's resource requests; review taints/affinity and "
                        "any pending PVCs. Scale the node pool or lower requests if it's a capacity issue."
                    ),
                )
            )
            summary = "Pods are unschedulable and stuck in Pending."

        else:
            confidence = "low"
            summary = (
                "Could not classify the failure into a known mode from the available signals. "
                "Surfacing raw findings for a human to review."
            )

        needs_human = confidence == "low" or not hypotheses
        if self._reason and hypotheses:
            hypotheses[0].explanation += f"  (Heuristic engine — {self._reason}.)"

        return RootCauseAnalysis(
            summary=summary,
            failure_mode=mode,
            hypotheses=hypotheses,
            overall_confidence=confidence,
            needs_human=needs_human,
        )
