from sherlock.investigators import (
    ChangeInvestigator,
    KubernetesInvestigator,
    MetricsInvestigator,
)
from sherlock.models import AlertEvent

from .fakes import (
    FakeGitClient,
    FakeKubernetesClient,
    FakePrometheusClient,
    oom_pod,
    sample_commits,
)


def _alert():
    return AlertEvent(source="t", title="OOM", namespace="prod", workload="api")


def test_kubernetes_investigator_extracts_oom_signal():
    k8s = FakeKubernetesClient(
        pods=[oom_pod()],
        events=[{"type": "Warning", "reason": "BackOff", "message": "Back-off restarting"}],
        logs="MemoryError: out of memory\npassword: leakme123",
    )
    finding = KubernetesInvestigator(k8s).investigate(_alert())
    assert finding.signals.get("oom_killed") is True
    assert finding.signals.get("exit_code") == 137
    assert finding.signals.get("memory_limit") == "256Mi"
    # logs are redacted
    blob = " ".join(e.detail for e in finding.evidence)
    assert "leakme123" not in blob


def test_kubernetes_investigator_no_pods():
    finding = KubernetesInvestigator(FakeKubernetesClient(pods=[])).investigate(_alert())
    assert "No pods found" in finding.summary
    assert finding.error == ""


def test_kubernetes_investigator_resilient_to_exception():
    finding = KubernetesInvestigator(FakeKubernetesClient(raise_on_list=True)).investigate(_alert())
    assert finding.error  # captured, not raised


def test_metrics_investigator_disabled_when_no_client():
    finding = MetricsInvestigator(None).investigate(_alert())
    assert "not configured" in finding.summary
    assert finding.error == ""


def test_metrics_investigator_reads_memory():
    prom = FakePrometheusClient(
        results={"container_memory_working_set_bytes": [{"value": [0, "260000000"]}]}
    )
    finding = MetricsInvestigator(prom).investigate(_alert())
    assert finding.signals.get("memory_working_set_bytes") == 260000000.0


def test_change_investigator_surfaces_recent_deploy():
    finding = ChangeInvestigator(FakeGitClient(commits=sample_commits())).investigate(_alert())
    assert "a1b2c3d4" in finding.signals.get("recent_deploy", "")
    assert finding.evidence[0].link.startswith("https://")


def test_change_investigator_disabled_when_no_client():
    finding = ChangeInvestigator(None).investigate(_alert())
    assert "No Git provider" in finding.summary
