"""Core data models shared across Sherlock.

Pydantic models, because the LLM synthesis step uses the Anthropic SDK's
structured-output (``messages.parse``) path, which validates the model's
response against these schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["low", "medium", "high"]


class Severity(str, Enum):
    critical = "critical"
    warning = "warning"
    info = "info"


class FailureMode(str, Enum):
    """The four failure modes the MVP investigates deeply (the razor)."""

    crash_loop = "CrashLoopBackOff"
    oom_killed = "OOMKilled"
    failed_deploy = "FailedDeploy"
    pending = "Pending"
    unknown = "Unknown"


class AlertEvent(BaseModel):
    """A normalized alert from any intake source (Alertmanager, PagerDuty, manual)."""

    source: str = Field(description="Where the alert came from, e.g. 'alertmanager'.")
    title: str
    namespace: str
    workload: str = Field(description="Deployment/pod/statefulset name.")
    severity: Severity = Severity.warning
    fingerprint: str = Field(
        default="",
        description="Stable dedup key. Identical fingerprints are the same incident.",
    )
    labels: dict[str, str] = Field(default_factory=dict)
    raw: dict = Field(default_factory=dict, description="Original payload, for audit.")


class Evidence(BaseModel):
    """A single piece of grounded evidence an investigator surfaced."""

    source: str = Field(description="e.g. 'k8s-events', 'prometheus', 'github'.")
    summary: str
    detail: str = ""
    link: str = ""


class Finding(BaseModel):
    """The output of one investigator."""

    investigator: str
    summary: str
    evidence: list[Evidence] = Field(default_factory=list)
    signals: dict = Field(
        default_factory=dict,
        description="Structured signals (e.g. exit_code, restart_count) for synthesis.",
    )
    error: str = ""


class Hypothesis(BaseModel):
    """One candidate root cause, ranked by confidence and cited to evidence."""

    cause: str = Field(description="A one-line statement of the likely cause.")
    confidence: Confidence
    explanation: str = Field(description="Why the evidence points to this cause.")
    evidence: list[str] = Field(
        default_factory=list,
        description="Quoted/paraphrased evidence supporting this hypothesis.",
    )
    suggested_fix: str = Field(description="A concrete, safe remediation to try.")


class RootCauseAnalysis(BaseModel):
    """The synthesized analysis — the LLM's structured output, or the fake engine's."""

    summary: str = Field(description="One-paragraph human summary of the incident.")
    failure_mode: FailureMode = FailureMode.unknown
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    overall_confidence: Confidence = "low"
    needs_human: bool = Field(
        default=False,
        description="True when evidence is too weak to assert a cause — never bluff.",
    )


class Investigation(BaseModel):
    """The full result of an investigation: the alert, the findings, the analysis."""

    incident: AlertEvent
    failure_mode: FailureMode
    findings: list[Finding] = Field(default_factory=list)
    analysis: RootCauseAnalysis
    duration_ms: int = 0
    tokens_spent: int = 0
    trace: list[dict] = Field(default_factory=list)
