"""Change investigator: "what changed" — correlate the incident to a recent deploy.

This is Sherlock's wedge. k8sgpt explains the pod; the Change Investigator
explains *why it broke now* by surfacing the most recent commit/deploy as the
prime suspect.
"""

from __future__ import annotations

from ..clients.git_client import GitReader
from ..models import AlertEvent, Evidence, Finding
from .base import Investigator


class ChangeInvestigator(Investigator):
    name = "change"

    def __init__(self, reader: GitReader | None) -> None:
        self.reader = reader

    def _investigate(self, incident: AlertEvent) -> Finding:
        if self.reader is None:
            return Finding(
                investigator=self.name,
                summary="No Git provider configured; skipped 'what changed' correlation.",
            )

        commits = self.reader.recent_commits(limit=8)
        if not commits:
            return Finding(
                investigator=self.name,
                summary="No recent commits found in the configured repository.",
            )

        evidence: list[Evidence] = []
        for c in commits:
            evidence.append(
                Evidence(
                    source="git",
                    summary=f"{c.get('sha')} {c.get('message')} ({c.get('author')}, {c.get('date')})",
                    link=c.get("url", ""),
                )
            )

        latest = commits[0]
        signals = {
            "recent_deploy": f"{latest.get('sha')} {latest.get('message')}",
            "recent_deploy_url": latest.get("url", ""),
            "recent_commit_count": len(commits),
        }
        summary = (
            f"Most recent change: {latest.get('sha')} \"{latest.get('message')}\" "
            f"by {latest.get('author')} at {latest.get('date')}. "
            "Recent changes are the leading suspects for a sudden failure."
        )
        return Finding(investigator=self.name, summary=summary, evidence=evidence, signals=signals)
