"""Offline demo: run a full Sherlock investigation against a synthetic OOM incident.

No cluster, no API key required — uses the deterministic engine and in-memory
fakes. This is the "show me it works" / launch-demo entry point.

    python examples/demo.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make 'sherlock' importable when run from the repo without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sherlock.delivery.slack import format_text
from sherlock.llm.fake import FakeLLM
from sherlock.models import AlertEvent, Severity
from sherlock.orchestrator import investigate_async
from tests.fakes import FakeGitClient, FakeKubernetesClient, FakePrometheusClient, oom_pod, sample_commits


async def main() -> None:
    incident = AlertEvent(
        source="alertmanager",
        title="KubePodOOMKilled: api in prod",
        namespace="prod",
        workload="api",
        severity=Severity.critical,
    )
    k8s = FakeKubernetesClient(
        pods=[oom_pod(memory_limit="256Mi", restarts=5)],
        events=[{"type": "Warning", "reason": "BackOff", "message": "Back-off restarting failed container api"}],
        logs="java.lang.OutOfMemoryError: Java heap space\n\tat com.acme.api.Cache.load(Cache.java:88)",
    )
    prom = FakePrometheusClient(
        results={"container_memory_working_set_bytes": [{"value": [0, "268000000"]}]}
    )
    git = FakeGitClient(commits=sample_commits())  # latest commit lowered the memory limit

    inv = await investigate_async(incident, k8s=k8s, llm=FakeLLM(), prometheus=prom, git=git)
    print(format_text(inv))


if __name__ == "__main__":
    asyncio.run(main())
