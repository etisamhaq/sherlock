"""Provider-precedence tests for build_llm: Groq → Anthropic → fake."""

from sherlock.config import Config
from sherlock.llm import build_llm
from sherlock.llm.fake import FakeLLM


def test_auto_prefers_groq_when_groq_key_present():
    cfg = Config(llm_provider="auto", groq_api_key="gsk_x", anthropic_api_key="sk-ant")
    llm = build_llm(cfg)
    assert type(llm).__name__ == "GroqLLM"


def test_auto_uses_anthropic_when_only_anthropic_key():
    cfg = Config(llm_provider="auto", groq_api_key="", anthropic_api_key="sk-ant")
    llm = build_llm(cfg)
    assert type(llm).__name__ == "AnthropicLLM"


def test_auto_falls_back_to_fake_with_no_keys():
    cfg = Config(llm_provider="auto", groq_api_key="", anthropic_api_key="")
    assert isinstance(build_llm(cfg), FakeLLM)


def test_explicit_fake_provider():
    cfg = Config(llm_provider="fake", groq_api_key="gsk_x")
    assert isinstance(build_llm(cfg), FakeLLM)


def test_explicit_groq_without_key_falls_back():
    cfg = Config(llm_provider="groq", groq_api_key="")
    assert isinstance(build_llm(cfg), FakeLLM)


def test_explicit_anthropic_selects_anthropic():
    cfg = Config(llm_provider="anthropic", anthropic_api_key="sk-ant")
    assert type(build_llm(cfg)).__name__ == "AnthropicLLM"
