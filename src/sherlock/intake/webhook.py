"""FastAPI webhook server: receives alerts, runs investigations, delivers results.

Endpoints:
    GET  /healthz                 liveness/readiness
    POST /webhook/alertmanager    Prometheus Alertmanager webhook
    POST /webhook/pagerduty       PagerDuty webhook (v3)
"""

from __future__ import annotations

from fastapi import FastAPI, Request

from ..config import Config
from ..runtime import handle_alert
from .parsers import parse_alertmanager, parse_pagerduty


def create_app(config: Config | None = None, *, k8s=None) -> FastAPI:
    config = config or Config.from_env()
    app = FastAPI(title="Sherlock", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok", "llm_provider": config.llm_provider}

    async def _process(events) -> dict:
        results = []
        for incident in events:
            if not incident.workload:
                results.append({"skipped": "no workload identified", "title": incident.title})
                continue
            inv = await handle_alert(incident, config, k8s=k8s)
            results.append(
                {
                    "workload": incident.workload,
                    "namespace": incident.namespace,
                    "failure_mode": inv.failure_mode.value,
                    "confidence": inv.analysis.overall_confidence,
                    "needs_human": inv.analysis.needs_human,
                    "summary": inv.analysis.summary,
                }
            )
        return {"investigations": results}

    @app.post("/webhook/alertmanager")
    async def alertmanager(request: Request) -> dict:
        payload = await request.json()
        return await _process(parse_alertmanager(payload))

    @app.post("/webhook/pagerduty")
    async def pagerduty(request: Request) -> dict:
        payload = await request.json()
        return await _process(parse_pagerduty(payload))

    return app
