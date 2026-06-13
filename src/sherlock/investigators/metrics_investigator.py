"""Metrics investigator: memory/CPU/restart signals from Prometheus.

Optional — if no Prometheus client is configured, returns a benign Finding
noting that metrics were unavailable (never an error that sinks the run).
"""

from __future__ import annotations

from ..clients.prometheus_client import PrometheusReader, scalar
from ..models import AlertEvent, Evidence, Finding
from .base import Investigator


class MetricsInvestigator(Investigator):
    name = "metrics"

    def __init__(self, reader: PrometheusReader | None) -> None:
        self.reader = reader

    def _investigate(self, incident: AlertEvent) -> Finding:
        if self.reader is None:
            return Finding(
                investigator=self.name,
                summary="Prometheus not configured; skipped metrics investigation.",
            )

        ns, wl = incident.namespace, incident.workload
        pod_re = f'{wl}.*'
        evidence: list[Evidence] = []
        signals: dict = {}

        # Working-set memory for the workload's pods.
        mem = scalar(
            self.reader.query(
                f'max(container_memory_working_set_bytes{{namespace="{ns}",pod=~"{pod_re}"}})'
            )
        )
        if mem is not None:
            signals["memory_working_set_bytes"] = mem
            evidence.append(
                Evidence(source="prometheus", summary=f"peak working-set memory ≈ {mem/1e6:.0f} MB")
            )

        # CPU throttling (a common latency cause).
        throttle = scalar(
            self.reader.query(
                f'sum(rate(container_cpu_cfs_throttled_periods_total{{namespace="{ns}",pod=~"{pod_re}"}}[5m]))'
            )
        )
        if throttle is not None:
            signals["cpu_throttled_rate"] = throttle
            if throttle > 0:
                evidence.append(
                    Evidence(source="prometheus", summary=f"CPU is being throttled (rate={throttle:.2f})")
                )

        # Restart rate.
        restarts = scalar(
            self.reader.query(
                f'max(kube_pod_container_status_restarts_total{{namespace="{ns}",pod=~"{pod_re}"}})'
            )
        )
        if restarts is not None:
            signals["restarts_total"] = restarts
            evidence.append(
                Evidence(source="prometheus", summary=f"container restart count ≈ {restarts:.0f}")
            )

        summary = (
            "Queried Prometheus for memory, CPU throttling, and restart metrics."
            if evidence
            else "Prometheus returned no series for this workload (check labels/retention)."
        )
        return Finding(investigator=self.name, summary=summary, evidence=evidence, signals=signals)
