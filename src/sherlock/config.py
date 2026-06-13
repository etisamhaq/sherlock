"""Configuration, loaded from environment variables.

Kept deliberately simple (no settings framework) so the OSS install is one
container + a handful of env vars. See ``.env.example`` for the full list.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


@dataclass
class Config:
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-4-8"
    anthropic_api_key: str = ""

    slack_webhook_url: str = ""

    prometheus_url: str = ""

    git_provider: str = ""
    git_token: str = ""
    git_repo: str = ""

    token_budget: int = 20_000
    time_budget_seconds: float = 180.0

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            llm_provider=os.environ.get("SHERLOCK_LLM_PROVIDER", "anthropic").strip() or "anthropic",
            llm_model=os.environ.get("SHERLOCK_LLM_MODEL", "claude-opus-4-8").strip() or "claude-opus-4-8",
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
            slack_webhook_url=os.environ.get("SHERLOCK_SLACK_WEBHOOK_URL", "").strip(),
            prometheus_url=os.environ.get("SHERLOCK_PROMETHEUS_URL", "").strip(),
            git_provider=os.environ.get("SHERLOCK_GIT_PROVIDER", "").strip(),
            git_token=os.environ.get("SHERLOCK_GIT_TOKEN", "").strip(),
            git_repo=os.environ.get("SHERLOCK_GIT_REPO", "").strip(),
            token_budget=_int("SHERLOCK_TOKEN_BUDGET", 20_000),
            time_budget_seconds=_float("SHERLOCK_TIME_BUDGET_SECONDS", 180.0),
        )
