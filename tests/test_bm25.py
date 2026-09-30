from gap_plugin.bm25 import BM25Index
from gap_plugin.types import EvidenceItem


def test_query_ranks_the_matching_evidence_first() -> None:
    corpus = [
        EvidenceItem("gap_plugin/retrieval.py", "def run_retrieval with a retry budget and BM25 index."),
        EvidenceItem("payroll.py", "invoice totals and payroll calculations"),
        EvidenceItem("scheduler.py", "meeting scheduling helpers"),
    ]
    index = BM25Index()
    index.build(corpus)

    results = index.query("retry budget BM25 index", k=10)

    assert results
    assert results[0].file_path == "gap_plugin/retrieval.py"
    assert results[0].source == "bm25"
    assert results[0].score > 0


def test_query_respects_k_limit() -> None:
    corpus = [EvidenceItem(f"f{i}.py", f"widget module number {i}") for i in range(5)]
    index = BM25Index()
    index.build(corpus)

    results = index.query("widget module", k=2)

    assert len(results) == 2


def test_query_on_empty_index_returns_empty() -> None:
    index = BM25Index()
    index.build([])

    assert index.query("anything", k=10) == []
