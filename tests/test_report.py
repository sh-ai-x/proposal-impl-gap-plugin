import json
from pathlib import Path

from gap_plugin.report import build_doc_report, build_repo_report, emit_report
from gap_plugin.types import ProposalDoc, Section, SectionVerdict


def _verdict(status: str, doc_path: str = "docs/proposals/x.md") -> SectionVerdict:
    return SectionVerdict(doc_path, "s1", status, 0.9, "why", "heuristic", 1)


def test_build_doc_report_counts_statuses() -> None:
    doc = ProposalDoc("docs/proposals/x.md", [Section("docs/proposals/x.md", "s1", "Goals", "text")])
    verdicts = [_verdict("implemented"), _verdict("missing")]

    report = build_doc_report(doc, verdicts)

    assert report.doc_path == "docs/proposals/x.md"
    assert report.status_counts == {"implemented": 1, "missing": 1}


def test_repo_score_is_one_when_everything_implemented() -> None:
    doc = ProposalDoc("x.md", [])
    doc_report = build_doc_report(doc, [_verdict("implemented"), _verdict("added")])

    repo_report = build_repo_report([doc_report], judge_name="heuristic", verdict_model="sonnet")

    assert repo_report.repo_score == 1.0


def test_repo_score_is_zero_when_everything_missing() -> None:
    doc = ProposalDoc("x.md", [])
    doc_report = build_doc_report(doc, [_verdict("missing"), _verdict("contradicted")])

    repo_report = build_repo_report([doc_report], judge_name="heuristic", verdict_model="sonnet")

    assert repo_report.repo_score == 0.0


def test_emit_report_writes_json_and_markdown(tmp_path: Path) -> None:
    doc = ProposalDoc("x.md", [])
    doc_report = build_doc_report(doc, [_verdict("implemented")])
    repo_report = build_repo_report([doc_report], judge_name="heuristic", verdict_model="sonnet")

    json_path, md_path = emit_report(repo_report, tmp_path)

    assert json_path.exists() and md_path.exists()
    data = json.loads(json_path.read_text())
    assert data["repo_score"] == 1.0
    assert "repo_score" in md_path.read_text()
