"""Read-only Prometheus HTTP API access (instant + range queries)."""

from __future__ import annotations

from typing import Optional, Protocol

import requests


class PrometheusReader(Protocol):
    def query(self, promql: str) -> list[dict]: ...


class RealPrometheusClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def query(self, promql: str) -> list[dict]:
        """Run an instant query, returning the raw result vector (list of series)."""
        resp = requests.get(
            f"{self.base_url}/api/v1/query",
            params={"query": promql},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != "success":
            return []
        return body.get("data", {}).get("result", [])


def scalar(result: list[dict]) -> Optional[float]:
    """Extract the first scalar value from a Prometheus instant-query result."""
    if not result:
        return None
    value = result[0].get("value")
    if not value or len(value) < 2:
        return None
    try:
        return float(value[1])
    except (TypeError, ValueError):
        return None
