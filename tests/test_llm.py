from types import SimpleNamespace

import pytest

from gap_plugin.errors import MissingAPIKeyError
from gap_plugin.llm import call_claude, default_model


def test_raises_naming_the_right_env_var_per_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)

    with pytest.raises(MissingAPIKeyError, match="MINIMAX_API_KEY"):
        call_claude("hi", model="MiniMax-M3[1m]", max_tokens=10, provider="minimax")


def test_unknown_provider_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        call_claude("hi", model="x", max_tokens=10, provider="openai")


def test_minimax_call_uses_anthropic_compatible_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
    seen: dict[str, object] = {}

    class FakeMessages:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(content=[SimpleNamespace(text="ok")])

    class FakeClient:
        def __init__(self, api_key: str, base_url: str | None = None) -> None:
            seen["api_key"] = api_key
            seen["base_url"] = base_url
            self.messages = FakeMessages()

    monkeypatch.setattr("anthropic.Anthropic", FakeClient)

    result = call_claude("hi", model="MiniMax-M3[1m]", max_tokens=10, provider="minimax")

    assert result == "ok"
    assert seen["api_key"] == "mm-key"
    assert seen["base_url"] == "https://api.minimax.io/anthropic"


def test_anthropic_call_uses_default_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "an-key")
    seen: dict[str, object] = {}

    class FakeMessages:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(content=[SimpleNamespace(text="ok")])

    class FakeClient:
        def __init__(self, api_key: str, base_url: str | None = None) -> None:
            seen["base_url"] = base_url
            self.messages = FakeMessages()

    monkeypatch.setattr("anthropic.Anthropic", FakeClient)

    call_claude("hi", model="claude-haiku-4-5", max_tokens=10, provider="anthropic")

    assert seen["base_url"] is None


def test_default_model_per_provider_and_tier() -> None:
    assert default_model("anthropic", "haiku") == "claude-haiku-4-5"
    assert default_model("anthropic", "sonnet") == "claude-sonnet-4-5"
    assert default_model("minimax", "haiku") == "MiniMax-M3[1m]"
    assert default_model("minimax", "sonnet") == "MiniMax-M3[1m]"
    assert default_model("deepseek", "haiku") == "deepseek-v4-flash"
    assert default_model("deepseek", "sonnet") == "deepseek-v4-pro"
