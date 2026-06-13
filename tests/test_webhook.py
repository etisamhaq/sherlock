from fastapi.testclient import TestClient

from sherlock.config import Config
from sherlock.intake.webhook import create_app

from .fakes import FakeKubernetesClient, oom_pod


def _client():
    config = Config(llm_provider="fake")
    app = create_app(config, k8s=FakeKubernetesClient(pods=[oom_pod()]))
    return TestClient(app)


def test_healthz():
    resp = _client().get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_alertmanager_webhook_runs_investigation():
    payload = {
        "alerts": [
            {
                "labels": {
                    "alertname": "KubePodOOM",
                    "namespace": "prod",
                    "deployment": "api",
                    "severity": "critical",
                },
                "annotations": {"summary": "api OOMKilled"},
                "fingerprint": "fp1",
            }
        ]
    }
    resp = _client().post("/webhook/alertmanager", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["investigations"]) == 1
    inv = body["investigations"][0]
    assert inv["workload"] == "api"
    assert inv["failure_mode"] == "OOMKilled"


def test_alertmanager_skips_when_no_workload():
    payload = {"alerts": [{"labels": {"namespace": "prod"}, "annotations": {}}]}
    resp = _client().post("/webhook/alertmanager", json=payload)
    assert resp.status_code == 200
    assert "skipped" in resp.json()["investigations"][0]


def test_pagerduty_webhook():
    payload = {
        "event": {
            "data": {
                "id": "PD1",
                "title": "api down",
                "severity": "critical",
                "body": {"details": {"namespace": "prod", "deployment": "api"}},
            }
        }
    }
    resp = _client().post("/webhook/pagerduty", json=payload)
    assert resp.status_code == 200
    assert resp.json()["investigations"][0]["workload"] == "api"
