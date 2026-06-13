"""Read-only Kubernetes access.

``KubernetesReader`` is the protocol investigators depend on; ``RealKubernetesClient``
implements it against the official ``kubernetes`` client using **read-only** calls
only. Tests inject a fake implementing the same protocol.
"""

from __future__ import annotations

from typing import Protocol


class PodInfo(dict):
    """A plain dict of normalized pod facts (phase, container statuses, etc.)."""


class KubernetesReader(Protocol):
    def get_pod(self, namespace: str, name: str) -> dict: ...
    def get_pod_events(self, namespace: str, name: str) -> list[dict]: ...
    def get_pod_logs(self, namespace: str, name: str, *, previous: bool = True, tail: int = 100) -> str: ...
    def list_workload_pods(self, namespace: str, workload: str) -> list[dict]: ...


class RealKubernetesClient:
    """Implements KubernetesReader against a live cluster (read-only)."""

    def __init__(self) -> None:
        from kubernetes import client, config

        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self._core = client.CoreV1Api()

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _container_statuses(pod) -> list[dict]:
        out: list[dict] = []
        for cs in (pod.status.container_statuses or []):
            state = cs.state
            waiting = getattr(state, "waiting", None)
            terminated = getattr(state, "terminated", None)
            last = getattr(cs, "last_state", None)
            last_term = getattr(last, "terminated", None) if last else None
            out.append(
                {
                    "name": cs.name,
                    "ready": cs.ready,
                    "restart_count": cs.restart_count,
                    "waiting_reason": getattr(waiting, "reason", None) if waiting else None,
                    "terminated_reason": getattr(terminated, "reason", None) if terminated else None,
                    "last_terminated_reason": getattr(last_term, "reason", None) if last_term else None,
                    "last_exit_code": getattr(last_term, "exit_code", None) if last_term else None,
                    "memory_limit": (
                        (cs_resources := getattr(cs, "resources", None))
                        and getattr(cs_resources, "limits", None)
                        and cs_resources.limits.get("memory")
                    ),
                }
            )
        return out

    # --- KubernetesReader ------------------------------------------------
    def get_pod(self, namespace: str, name: str) -> dict:
        pod = self._core.read_namespaced_pod(name=name, namespace=namespace)
        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "phase": pod.status.phase,
            "container_statuses": self._container_statuses(pod),
            "conditions": [
                {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
                for c in (pod.status.conditions or [])
            ],
        }

    def get_pod_events(self, namespace: str, name: str) -> list[dict]:
        field = f"involvedObject.name={name}"
        events = self._core.list_namespaced_event(namespace=namespace, field_selector=field)
        return [
            {
                "type": e.type,
                "reason": e.reason,
                "message": e.message,
                "count": e.count,
            }
            for e in events.items
        ]

    def get_pod_logs(self, namespace: str, name: str, *, previous: bool = True, tail: int = 100) -> str:
        try:
            return self._core.read_namespaced_pod_log(
                name=name, namespace=namespace, previous=previous, tail_lines=tail
            )
        except Exception:
            # 'previous' logs may not exist if the container never restarted.
            return self._core.read_namespaced_pod_log(name=name, namespace=namespace, tail_lines=tail)

    def list_workload_pods(self, namespace: str, workload: str) -> list[dict]:
        pods = self._core.list_namespaced_pod(namespace=namespace)
        matched = [p for p in pods.items if p.metadata.name.startswith(workload)]
        return [
            {
                "name": p.metadata.name,
                "phase": p.status.phase,
                "container_statuses": self._container_statuses(p),
            }
            for p in matched
        ]
