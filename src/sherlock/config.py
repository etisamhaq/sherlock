"""Configuration, loaded from environment variables.

Kept deliberately simple (no settings framework) so the OSS install is one
container + a handful of env vars. See ``.env.example`` for the full list.
A minimal ``.env`` loader is included (no extra dependency) for local dev.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: str | os.PathLike = ".env") -> None:
    """Load KEY=VALUE lines from a .env file into os.environ (existing vars win)."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


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
    # provider: auto | groq | anthropic | fake  (auto = groq → anthropic → fake)
    llm_provider: str = "auto"

    # Groq (primary)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Anthropic (fallback)
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-8"

    slack_webhook_url: str = ""
    prometheus_url: str = ""

    git_provider: str = ""
    git_token: str = ""
    git_repo: str = ""

    token_budget: int = 20_000
    time_budget_seconds: float = 180.0

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        return cls(
            llm_provider=os.environ.get("SHERLOCK_LLM_PROVIDER", "auto").strip() or "auto",
            groq_api_key=os.environ.get("GROQ_API_KEY", "").strip(),
            groq_model=os.environ.get("SHERLOCK_GROQ_MODEL", "llama-3.3-70b-versatile").strip()
            or "llama-3.3-70b-versatile",
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
            llm_model=os.environ.get("SHERLOCK_LLM_MODEL", "claude-opus-4-8").strip() or "claude-opus-4-8",
            slack_webhook_url=os.environ.get("SHERLOCK_SLACK_WEBHOOK_URL", "").strip(),
            prometheus_url=os.environ.get("SHERLOCK_PROMETHEUS_URL", "").strip(),
            git_provider=os.environ.get("SHERLOCK_GIT_PROVIDER", "").strip(),
            git_token=os.environ.get("SHERLOCK_GIT_TOKEN", "").strip(),
            git_repo=os.environ.get("SHERLOCK_GIT_REPO", "").strip(),
            token_budget=_int("SHERLOCK_TOKEN_BUDGET", 20_000),
            time_budget_seconds=_float("SHERLOCK_TIME_BUDGET_SECONDS", 180.0),
        )
