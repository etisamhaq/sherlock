"""LLM abstraction. ``build_llm(config)`` returns a provider-portable client."""

from __future__ import annotations

from ..config import Config
from .base import LLMClient, SynthesisContext
from .fake import FakeLLM

__all__ = ["LLMClient", "SynthesisContext", "FakeLLM", "build_llm"]


def build_llm(config: Config) -> LLMClient:
    """Construct the configured LLM client.

    Falls back to the deterministic FakeLLM when the provider is 'fake' or when
    no API key is available — so the tool always runs, even offline / in CI.
    """
    provider = (config.llm_provider or "anthropic").lower()
    if provider == "fake":
        return FakeLLM()
    if provider == "anthropic":
        if not config.anthropic_api_key:
            # No key — degrade gracefully to the heuristic engine rather than crash.
            return FakeLLM(reason="no ANTHROPIC_API_KEY set")
        from .anthropic_client import AnthropicLLM

        return AnthropicLLM(model=config.llm_model, api_key=config.anthropic_api_key)
    raise ValueError(f"unknown LLM provider: {config.llm_provider!r}")
