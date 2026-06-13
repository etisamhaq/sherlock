"""Read-only Git provider access for "what changed" correlation.

Fetches recent commits/deploys from GitHub or GitLab so the Change Investigator
can correlate an incident with the deploy that most likely caused it. This is
Sherlock's wedge feature.
"""

from __future__ import annotations

from typing import Protocol

import requests


class GitReader(Protocol):
    def recent_commits(self, limit: int = 10) -> list[dict]: ...


class GitHubClient:
    def __init__(self, token: str, repo: str, timeout: float = 10.0) -> None:
        self.token = token
        self.repo = repo  # "owner/repo"
        self.timeout = timeout

    def recent_commits(self, limit: int = 10) -> list[dict]:
        resp = requests.get(
            f"https://api.github.com/repos/{self.repo}/commits",
            params={"per_page": limit},
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        out = []
        for c in resp.json():
            out.append(
                {
                    "sha": c.get("sha", "")[:8],
                    "message": (c.get("commit", {}).get("message") or "").splitlines()[0],
                    "author": c.get("commit", {}).get("author", {}).get("name", ""),
                    "date": c.get("commit", {}).get("author", {}).get("date", ""),
                    "url": c.get("html_url", ""),
                }
            )
        return out


class GitLabClient:
    def __init__(self, token: str, repo: str, timeout: float = 10.0) -> None:
        self.token = token
        self.repo = repo  # "group/project"
        self.timeout = timeout

    def recent_commits(self, limit: int = 10) -> list[dict]:
        from urllib.parse import quote

        project = quote(self.repo, safe="")
        resp = requests.get(
            f"https://gitlab.com/api/v4/projects/{project}/repository/commits",
            params={"per_page": limit},
            headers={"PRIVATE-TOKEN": self.token},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        out = []
        for c in resp.json():
            out.append(
                {
                    "sha": (c.get("id") or "")[:8],
                    "message": (c.get("title") or ""),
                    "author": c.get("author_name", ""),
                    "date": c.get("committed_date", ""),
                    "url": c.get("web_url", ""),
                }
            )
        return out


def build_git_client(provider: str, token: str, repo: str) -> GitReader | None:
    provider = (provider or "").lower()
    if not provider or not token or not repo:
        return None
    if provider == "github":
        return GitHubClient(token, repo)
    if provider == "gitlab":
        return GitLabClient(token, repo)
    return None
