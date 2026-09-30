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


def test_jev_judge_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with pytest.raises(MissingAPIKeyError):
        jev_judge(_section("ship the widget"), [], after_files=set())


def test_jev_judge_accepts_on_high_noul(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    import gap_plugin.judges as judges_module

    monkeypatch.setattr(judges_module, "_call_jev", lambda *a, **k: 0.92)

    verdict = jev_judge(_section("ship the widget"), [_candidate("x.py", "widget shipped")], after_files=set())

    assert verdict.accepted is True
    assert verdict.confidence == pytest.approx(0.84, abs=0.01)  # certainty = |0.92-0.5|*2


def test_jev_judge_rejects_on_low_noul(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    import gap_plugin.judges as judges_module

    monkeypatch.setattr(judges_module, "_call_jev", lambda *a, **k: 0.05)

    verdict = jev_judge(_section("ship the widget"), [], after_files=set())

    assert verdict.accepted is False
    assert verdict.confidence == pytest.approx(0.9, abs=0.01)  # certainty = |0.05-0.5|*2


def test_jev_judge_escalates_to_haiku_when_noul_is_near_half(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    import gap_plugin.judges as judges_module
    from gap_plugin.types import JudgeVerdict

    monkeypatch.setattr(judges_module, "_call_jev", lambda *a, **k: 0.55)  # certainty=0.1, below default 0.4
    monkeypatch.setattr(
        judges_module,
        "haiku_judge",
        lambda *a, **k: JudgeVerdict(accepted=True, confidence=0.81, reasoning="haiku says yes"),
    )

    verdict = jev_judge(_section("ship the widget"), [], after_files=set())

    assert verdict.accepted is True
    assert verdict.confidence == 0.81
    assert "escalated" in verdict.reasoning
    assert "haiku says yes" in verdict.reasoning


def test_jev_judge_does_not_escalate_at_the_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    import gap_plugin.judges as judges_module

    # noul=0.71 -> certainty=0.42, at/above the default 0.4 escalation floor -> resolves directly
    monkeypatch.setattr(judges_module, "_call_jev", lambda *a, **k: 0.71)

    verdict = jev_judge(_section("ship the widget"), [], after_files=set())

    assert verdict.accepted is True
    assert "escalated" not in verdict.reasoning


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
