from gap_plugin.retrieval import run_retrieval
from gap_plugin.types import Candidate, JudgeVerdict, Section


class _FakeBM25:
    def __init__(self, queries_seen: list[str]) -> None:
        self._queries_seen = queries_seen

    def query(self, text: str, k: int) -> list[Candidate]:
        self._queries_seen.append(text)
        return [Candidate(file_path="x.py", snippet="evidence", score=1.0, source="bm25")]


def _judge_sequence(results: list[bool]) -> object:
    calls = iter(results)

    def judge(section: Section, candidates: list[Candidate], after_files: set[str]) -> JudgeVerdict:
        accepted = next(calls)
        return JudgeVerdict(accepted=accepted, confidence=1.0 if accepted else 0.1, reasoning="test")

    return judge


def _section() -> Section:
    return Section("docs/proposals/x.md", "s1", "Goals", "ship the widget")


def test_accepts_on_first_attempt() -> None:
    outcome = run_retrieval(_section(), _FakeBM25([]), _judge_sequence([True]), after_files=set())

    assert outcome.status == "answer"
    assert outcome.attempts == 1


def test_retries_then_accepts() -> None:
    outcome = run_retrieval(
        _section(), _FakeBM25([]), _judge_sequence([False, False, True]), after_files=set(), retry_limit=2
    )

    assert outcome.status == "answer"
    assert outcome.attempts == 3


def test_exhausts_retry_budget_into_missing_info() -> None:
    outcome = run_retrieval(
        _section(), _FakeBM25([]), _judge_sequence([False, False, False]), after_files=set(), retry_limit=2
    )

    assert outcome.status == "missing_info"
    assert outcome.attempts == 3


def test_rewrite_expands_the_query_text_between_attempts() -> None:
    queries: list[str] = []
    run_retrieval(
        _section(), _FakeBM25(queries), _judge_sequence([False, True]), after_files=set(), retry_limit=2
    )

    assert len(queries) == 2
    assert queries[0] != queries[1]
    assert queries[0] in queries[1]
