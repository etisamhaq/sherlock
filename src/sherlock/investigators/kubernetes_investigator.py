"""Kubernetes investigator: pod state, events, and (redacted) logs."""

from __future__ import annotations

from ..clients.kubernetes_client import KubernetesReader
from ..models import AlertEvent, Evidence, Finding
from ..redaction import redact
from .base import Investigator


def _pick_unhealthy(pods: list[dict]) -> dict | None:
    """Prefer a pod that looks broken; otherwise the first pod."""
    for pod in pods:
        for cs in pod.get("container_statuses", []) or []:
            if not cs.get("ready") or cs.get("waiting_reason") or cs.get("terminated_reason"):
                return pod
    return pods[0] if pods else None


class KubernetesInvestigator(Investigator):
    name = "kubernetes"

    def __init__(self, reader: KubernetesReader) -> None:
        self.reader = reader

    def _investigate(self, incident: AlertEvent) -> Finding:
        pods = self.reader.list_workload_pods(incident.namespace, incident.workload)
        if not pods:
            return Finding(
                investigator=self.name,
                summary=f"No pods found for workload '{incident.workload}' in namespace '{incident.namespace}'.",
            )

        pod = _pick_unhealthy(pods)
        pod_name = pod.get("name", incident.workload)
        evidence: list[Evidence] = []
        signals: dict = {}

        # Container statuses → signals + evidence.
        for cs in pod.get("container_statuses", []) or []:
            reason = (
                cs.get("terminated_reason")
                or cs.get("last_terminated_reason")
                or cs.get("waiting_reason")
            )
            signals.setdefault("restart_count", cs.get("restart_count"))
            if cs.get("last_exit_code") is not None:
                signals.setdefault("exit_code", cs.get("last_exit_code"))
            if cs.get("memory_limit"):
                signals.setdefault("memory_limit", cs.get("memory_limit"))
            if reason in ("OOMKilled",):
                signals["oom_killed"] = True
            if reason:
                evidence.append(
                    Evidence(
                        source="k8s-status",
                        summary=f"container '{cs.get('name')}' reason={reason}, "
                        f"restarts={cs.get('restart_count')}, exit_code={cs.get('last_exit_code')}",
                    )
                )

        # Events.
        try:
            events = self.reader.get_pod_events(incident.namespace, pod_name)
        except Exception:
            events = []
        for e in events[:8]:
            if e.get("type") == "Warning" or e.get("reason"):
                evidence.append(
                    Evidence(
                        source="k8s-events",
                        summary=redact(f"{e.get('reason')}: {e.get('message')}"),
                    )
                )
            if e.get("reason") in ("FailedScheduling", "Unschedulable"):
                signals["pending_reason"] = redact(e.get("message", "unschedulable"))

        # Logs (previous container, redacted, bounded).
        try:
            logs = self.reader.get_pod_logs(incident.namespace, pod_name, previous=True, tail=60)
        except Exception:
            logs = ""
        if logs:
            tail = "\n".join(logs.strip().splitlines()[-20:])
            evidence.append(
                Evidence(
                    source="k8s-logs",
                    summary=f"last log lines from {pod_name}",
                    detail=redact(tail),
                )
            )

        summary = (
            f"Inspected pod '{pod_name}' for workload '{incident.workload}'. "
            f"phase={pod.get('phase')}, "
            f"signals={ {k: v for k, v in signals.items()} }."
        )
        return Finding(investigator=self.name, summary=summary, evidence=evidence, signals=signals)
