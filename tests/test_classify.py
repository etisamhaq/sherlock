from sherlock.classify import classify
from sherlock.models import AlertEvent, FailureMode

from .fakes import crashloop_pod, imagepull_pod, oom_pod, pending_pod


def _alert(title=""):
    return AlertEvent(source="t", title=title, namespace="prod", workload="api")


def test_classify_oom_wins_over_crashloop():
    # An OOM pod also shows CrashLoopBackOff; OOM is more specific and must win.
    assert classify(_alert(), [oom_pod()]) is FailureMode.oom_killed


def test_classify_crashloop():
    assert classify(_alert(), [crashloop_pod()]) is FailureMode.crash_loop


def test_classify_pending():
    assert classify(_alert(), [pending_pod()]) is FailureMode.pending


def test_classify_failed_deploy_from_imagepull():
    assert classify(_alert(), [imagepull_pod()]) is FailureMode.failed_deploy


def test_classify_failed_deploy_from_title():
    assert classify(_alert("Deployment rollout stuck"), []) is FailureMode.failed_deploy


def test_classify_unknown_when_no_signal():
    assert classify(_alert("something vague"), []) is FailureMode.unknown
