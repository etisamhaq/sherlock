import sherlock.runtime as runtime
from sherlock.cli import main

from .fakes import FakeKubernetesClient, oom_pod


def test_cli_investigate(monkeypatch, capsys):
    monkeypatch.setenv("SHERLOCK_LLM_PROVIDER", "fake")
    monkeypatch.setenv("SHERLOCK_SLACK_WEBHOOK_URL", "")
    # Inject a fake cluster so the CLI doesn't try to reach a real one.
    monkeypatch.setattr(runtime, "_build_k8s", lambda: FakeKubernetesClient(pods=[oom_pod()]))

    rc = main(["investigate", "-n", "prod", "-w", "api", "--no-deliver"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "SHERLOCK" in out
    assert "OOMKilled" in out


def test_cli_investigate_json(monkeypatch, capsys):
    monkeypatch.setenv("SHERLOCK_LLM_PROVIDER", "fake")
    monkeypatch.setattr(runtime, "_build_k8s", lambda: FakeKubernetesClient(pods=[oom_pod()]))

    rc = main(["investigate", "-n", "prod", "-w", "api", "--no-deliver", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    assert '"failure_mode"' in out


def test_cli_version(capsys):
    rc = main(["version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "sherlock" in out
