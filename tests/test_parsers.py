from sherlock.intake.parsers import parse_alertmanager, parse_pagerduty, workload_from_pod
from sherlock.models import Severity


def test_workload_from_deployment_pod():
    assert workload_from_pod("api-7d9f8c6b5-abc12") == "api"


def test_workload_from_statefulset_pod():
    assert workload_from_pod("postgres-0") == "postgres"


def test_parse_alertmanager_basic():
    payload = {
        "alerts": [
            {
                "labels": {
                    "alertname": "KubePodCrashLooping",
                    "namespace": "prod",
                    "deployment": "api",
                    "severity": "critical",
                },
                "annotations": {"summary": "Pod api is crash looping"},
                "fingerprint": "abc123",
            }
        ]
    }
    events = parse_alertmanager(payload)
    assert len(events) == 1
    e = events[0]
    assert e.namespace == "prod"
    assert e.workload == "api"
    assert e.severity is Severity.critical
    assert e.fingerprint == "abc123"
    assert e.title == "Pod api is crash looping"


def test_parse_alertmanager_derives_workload_from_pod():
    payload = {"alerts": [{"labels": {"namespace": "prod", "pod": "worker-abc123def-xy12z"}}]}
    events = parse_alertmanager(payload)
    assert events[0].workload == "worker"


def test_parse_pagerduty_with_custom_details():
    payload = {
        "event": {
            "data": {
                "id": "PD123",
                "title": "High latency on checkout",
                "severity": "critical",
                "body": {"details": {"namespace": "shop", "deployment": "checkout"}},
            }
        }
    }
    events = parse_pagerduty(payload)
    assert len(events) == 1
    assert events[0].namespace == "shop"
    assert events[0].workload == "checkout"
    assert events[0].fingerprint == "PD123"
