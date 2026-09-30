import pytest

from gap_plugin.errors import MissingAPIKeyError
from gap_plugin.judges import get_judge, heuristic_judge, jev_judge
from gap_plugin.types import Candidate, Section


def _section(text: str) -> Section:
    return Section("docs/proposals/x.md", "s1", "Goals", text)


def _candidate(file_path: str, snippet: str, score: float = 1.0) -> Candidate:
    return Candidate(file_path=file_path, snippet=snippet, score=score, source="bm25")


def test_heuristic_judge_accepts_on_strong_overlap_and_after_hit() -> None:
    section = _section("ship the widget with a retry budget and bm25 index")
    candidates = [_candidate("gap_plugin/retrieval.py", "widget retry budget bm25 index implementation")]

    verdict = heuristic_judge(section, candidates, after_files={"gap_plugin/retrieval.py"})

    assert verdict.accepted is True
    assert verdict.confidence >= 0.7


def test_heuristic_judge_rejects_on_no_overlap() -> None:
    section = _section("ship the widget with a retry budget and bm25 index")
    candidates = [_candidate("payroll.py", "unrelated invoice totals calculation")]

    verdict = heuristic_judge(section, candidates, after_files=set())

    assert verdict.accepted is False
    assert verdict.confidence < 0.7


def test_heuristic_judge_rejects_with_no_candidates() -> None:
    section = _section("ship the widget")

    verdict = heuristic_judge(section, [], after_files=set())

    assert verdict.accepted is False


def test_jev_judge_is_stubbed_pending() -> None:
    section = _section("ship the widget")

    with pytest.raises(NotImplementedError):
        jev_judge(section, [], after_files=set())


def test_haiku_judge_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from gap_plugin.judges import haiku_judge

    section = _section("ship the widget")
    with pytest.raises(MissingAPIKeyError):
        haiku_judge(section, [], after_files=set())


def test_get_judge_returns_registered_callable() -> None:
    assert get_judge("heuristic") is heuristic_judge


def test_get_judge_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        get_judge("nonexistent")
