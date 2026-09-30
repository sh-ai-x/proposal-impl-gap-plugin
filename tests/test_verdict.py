import json
from types import SimpleNamespace

import pytest

from gap_plugin.errors import MissingAPIKeyError
from gap_plugin.types import Candidate, Section
from gap_plugin.verdict import llm_status_verdict


def _section() -> Section:
    return Section("docs/proposals/x.md", "s1", "Goals", "ship the widget")


def test_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(MissingAPIKeyError):
        llm_status_verdict(_section(), [])


def test_parses_well_formed_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    payload = json.dumps({"status": "partial", "confidence": 0.6, "reasoning": "half done"})
    fake_response = SimpleNamespace(content=[SimpleNamespace(text=payload)])

    class FakeMessages:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return fake_response

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.messages = FakeMessages()

    monkeypatch.setattr("anthropic.Anthropic", FakeClient)

    result = llm_status_verdict(_section(), [Candidate("x.py", "evidence", 1.0, "bm25")])

    assert result.status == "partial"
    assert result.confidence == 0.6
    assert result.reasoning == "half done"


def test_falls_back_to_unknown_on_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    fake_response = SimpleNamespace(content=[SimpleNamespace(text="not json")])

    class FakeMessages:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return fake_response

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.messages = FakeMessages()

    monkeypatch.setattr("anthropic.Anthropic", FakeClient)

    result = llm_status_verdict(_section(), [])

    assert result.status == "unknown"


def test_falls_back_to_unknown_on_status_outside_taxonomy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    payload = json.dumps({"status": "done", "confidence": 0.9, "reasoning": "x"})
    fake_response = SimpleNamespace(content=[SimpleNamespace(text=payload)])

    class FakeMessages:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return fake_response

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.messages = FakeMessages()

    monkeypatch.setattr("anthropic.Anthropic", FakeClient)

    result = llm_status_verdict(_section(), [])

    assert result.status == "unknown"
