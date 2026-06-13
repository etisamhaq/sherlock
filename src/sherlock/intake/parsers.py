"""Pure functions that normalize provider payloads into AlertEvent(s).

Kept free of I/O so they're trivial to unit-test.
"""

from __future__ import annotations

import re

from ..models import AlertEvent, Severity

# Pod names look like "<workload>-<replicaset-hash>-<pod-hash>" for Deployments,
# or "<workload>-<ordinal>" for StatefulSets. Strip the trailing hash/ordinal.
_RS_POD_SUFFIX = re.compile(r"-[a-f0-9]{6,10}-[a-z0-9]{5}$")
_STS_SUFFIX = re.compile(r"-\d+$")


def workload_from_pod(pod: str) -> str:
    if not pod:
        return pod
    stripped = _RS_POD_SUFFIX.sub("", pod)
    if stripped != pod:
        return stripped
    return _STS_SUFFIX.sub("", pod)


def _severity(value: str) -> Severity:
    v = (value or "").lower()
    if v in ("critical", "error", "page", "p1", "p2"):
        return Severity.critical
    if v in ("warning", "warn", "p3"):
        return Severity.warning
    return Severity.info


def parse_alertmanager(payload: dict) -> list[AlertEvent]:
    """Parse a Prometheus Alertmanager webhook payload into AlertEvents."""
    events: list[AlertEvent] = []
    for alert in payload.get("alerts", []) or []:
        labels = alert.get("labels", {}) or {}
        annotations = alert.get("annotations", {}) or {}
        namespace = labels.get("namespace") or labels.get("exported_namespace") or "default"
        workload = (
            labels.get("deployment")
            or labels.get("workload")
            or labels.get("statefulset")
            or labels.get("daemonset")
            or workload_from_pod(labels.get("pod", ""))
            or labels.get("job", "")
        )
        title = (
            annotations.get("summary")
            or annotations.get("description")
            or labels.get("alertname")
            or "Alert"
        )
        events.append(
            AlertEvent(
                source="alertmanager",
                title=title,
                namespace=namespace,
                workload=workload,
                severity=_severity(labels.get("severity", "")),
                fingerprint=alert.get("fingerprint", ""),
                labels=labels,
                raw=alert,
            )
        )
    return events


def parse_pagerduty(payload: dict) -> list[AlertEvent]:
    """Parse a PagerDuty webhook (v3) payload into a single AlertEvent.

    PagerDuty payloads vary; we pull namespace/workload from custom_details when
    present and fall back to the incident title.
    """
    event = payload.get("event", payload)
    data = event.get("data", event) if isinstance(event, dict) else {}
    title = data.get("title") or data.get("summary") or "PagerDuty incident"

    details = {}
    body = data.get("body") or {}
    if isinstance(body, dict):
        details = body.get("details") or body.get("custom_details") or {}
    details = details or data.get("custom_details") or {}

    namespace = details.get("namespace", "default")
    workload = (
        details.get("deployment")
        or details.get("workload")
        or workload_from_pod(details.get("pod", ""))
        or details.get("service", "")
    )
    severity = _severity(data.get("severity", "") or details.get("severity", ""))

    return [
        AlertEvent(
            source="pagerduty",
            title=title,
            namespace=namespace,
            workload=workload,
            severity=severity,
            fingerprint=data.get("id", "") or (event.get("id", "") if isinstance(event, dict) else ""),
            labels={k: str(v) for k, v in details.items()},
            raw=payload,
        )
    ]
