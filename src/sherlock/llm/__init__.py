"""LLM abstraction. ``build_llm(config)`` returns a provider-portable client.

Provider precedence (when ``SHERLOCK_LLM_PROVIDER`` is unset or 'auto'):
    Groq (if GROQ_API_KEY)  →  Anthropic Claude (if ANTHROPIC_API_KEY)  →  fake.

Set ``SHERLOCK_LLM_PROVIDER`` explicitly (groq | anthropic | fake) to force one.
"""

from __future__ import annotations

from ..config import Config
from .base import LLMClient, SynthesisContext
from .fake import FakeLLM

__all__ = ["LLMClient", "SynthesisContext", "FakeLLM", "build_llm"]


def build_llm(config: Config) -> LLMClient:
    """Construct the configured LLM client.

    Falls back to the deterministic FakeLLM whenever the chosen provider has no
    key — so the tool always runs, even offline / in CI.
    """
    provider = (config.llm_provider or "auto").lower()

    if provider == "auto":
        if config.groq_api_key:
            provider = "groq"
        elif config.anthropic_api_key:
            provider = "anthropic"
        else:
            return FakeLLM(reason="no GROQ_API_KEY or ANTHROPIC_API_KEY set")

    if provider == "fake":
        return FakeLLM()

    if provider == "groq":
        if not config.groq_api_key:
            return FakeLLM(reason="no GROQ_API_KEY set")
        from .groq_client import GroqLLM

        return GroqLLM(model=config.groq_model, api_key=config.groq_api_key)

    if provider == "anthropic":
        if not config.anthropic_api_key:
            return FakeLLM(reason="no ANTHROPIC_API_KEY set")
        from .anthropic_client import AnthropicLLM

        return AnthropicLLM(model=config.llm_model, api_key=config.anthropic_api_key)

    raise ValueError(f"unknown LLM provider: {config.llm_provider!r}")
