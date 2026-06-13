"""Classify a Kubernetes failure into one of the four MVP failure modes.

Deterministic, signal-based — no LLM. Runs before synthesis so the LLM (or the
fake engine) gets a strong prior and the right investigators are emphasized.
"""

from __future__ import annotations

from .models import AlertEvent, FailureMode


def _statuses(pod: dict) -> list[dict]:
    return pod.get("container_statuses", []) or []


def classify(alert: AlertEvent, pods: list[dict]) -> FailureMode:
    """Return the most specific failure mode the evidence supports."""
    title = (alert.title or "").lower()

    # OOMKilled — most specific, check first (current or last termination).
    for pod in pods:
        for cs in _statuses(pod):
            if "OOMKilled" in (cs.get("terminated_reason"), cs.get("last_terminated_reason")):
                return FailureMode.oom_killed

    # CrashLoopBackOff — waiting reason, or repeated non-zero exits.
    for pod in pods:
        for cs in _statuses(pod):
            if cs.get("waiting_reason") == "CrashLoopBackOff":
                return FailureMode.crash_loop
            if (cs.get("restart_count") or 0) >= 3 and (cs.get("last_exit_code") or 0) != 0:
                return FailureMode.crash_loop

    # Failed deploy — image pull / config errors are bad-rollout signals. Check
    # these BEFORE the generic Pending phase, since such pods are also Pending.
    for pod in pods:
        for cs in _statuses(pod):
            if cs.get("waiting_reason") in ("ErrImagePull", "ImagePullBackOff", "CreateContainerConfigError"):
                return FailureMode.failed_deploy

    # ...or inferred from the alert when pods look like a broken rollout.
    if any(word in title for word in ("deploy", "rollout", "progressdeadline", "rollouts")):
        return FailureMode.failed_deploy

    # Pending / unschedulable (after the more-specific failed-deploy checks).
    if any((p.get("phase") == "Pending") for p in pods):
        return FailureMode.pending

    return FailureMode.unknown
