from sherlock.llm.base import SynthesisContext
from sherlock.llm.fake import FakeLLM
from sherlock.models import AlertEvent, Evidence, FailureMode, Finding


def _ctx(mode, findings):
    return SynthesisContext(
        incident=AlertEvent(source="t", title="x", namespace="prod", workload="api"),
        failure_mode=mode,
        findings=findings,
    )


def test_oom_with_deploy_is_high_confidence():
    findings = [
        Finding(investigator="kubernetes", summary="oom", signals={"oom_killed": True, "memory_limit": "256Mi"}),
        Finding(investigator="change", summary="deploy", signals={"recent_deploy": "a1b2c3d4 lower mem limit"}),
    ]
    rca = FakeLLM().analyze_root_cause(_ctx(FailureMode.oom_killed, findings))
    assert rca.overall_confidence == "high"
    assert rca.hypotheses
    assert "revert" in rca.hypotheses[0].suggested_fix.lower()
    assert not rca.needs_human


def test_oom_without_deploy_is_medium():
    findings = [Finding(investigator="kubernetes", summary="oom", signals={"oom_killed": True})]
    rca = FakeLLM().analyze_root_cause(_ctx(FailureMode.oom_killed, findings))
    assert rca.overall_confidence == "medium"


def test_unknown_mode_needs_human():
    rca = FakeLLM().analyze_root_cause(_ctx(FailureMode.unknown, []))
    assert rca.needs_human is True


def test_pending_mode_has_hypothesis():
    findings = [Finding(investigator="kubernetes", summary="pending", signals={"pending_reason": "Insufficient cpu"})]
    rca = FakeLLM().analyze_root_cause(_ctx(FailureMode.pending, findings))
    assert rca.failure_mode is FailureMode.pending
    assert rca.hypotheses


def test_evidence_is_carried_into_hypothesis():
    findings = [
        Finding(
            investigator="kubernetes",
            summary="oom",
            signals={"oom_killed": True},
            evidence=[Evidence(source="k8s-status", summary="reason=OOMKilled")],
        )
    ]
    rca = FakeLLM().analyze_root_cause(_ctx(FailureMode.oom_killed, findings))
    assert any("OOMKilled" in e for e in rca.hypotheses[0].evidence)
