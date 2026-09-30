import shutil
import subprocess
from pathlib import Path

import gap_plugin.pipeline as pipeline
from gap_plugin.types import VerdictResult

FIXTURES = Path(__file__).parent / "fixtures"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo_with_proposal(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs" / "proposals").mkdir(parents=True)
    shutil.copy(FIXTURES / "widget.proposal.md", repo / "docs" / "proposals" / "widget.proposal.md")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "proposal only")

    (repo / "src").mkdir()
    shutil.copy(FIXTURES / "retrieval_config.py", repo / "src" / "retrieval_config.py")
    _git(repo, "add", "-A")
    return repo


def test_scan_runs_end_to_end_and_emits_report(tmp_path, monkeypatch) -> None:
    repo = _init_repo_with_proposal(tmp_path)

    def fake_verdict(section, candidates, *, model="claude-sonnet-4-5"):
        return VerdictResult(status="implemented", confidence=0.9, reasoning="matched evidence")

    monkeypatch.setattr(pipeline, "llm_status_verdict", fake_verdict)

    out_dir = tmp_path / "out"
    report = pipeline.scan(None, repo, judge_name="heuristic", out_dir=out_dir)

    assert len(report.docs) == 1
    doc = report.docs[0]
    assert doc.doc_path == "docs/proposals/widget.proposal.md"
    statuses = {v.section_id: v.status for v in doc.sections}

    # "Goals" section shares tokens with src/retrieval_config.py (an After
    # file) -> heuristic judge accepts -> the (faked) verdict runs.
    assert statuses["goals"] == "implemented"
    # "Non-goals" shares no tokens with any evidence -> retrieval exhausts
    # its retry budget -> missing_info -> "unknown" without calling verdict.
    assert statuses["non-goals"] == "unknown"

    assert report.repo_score == 0.75  # gap=(0.0 implemented + 0.5 unknown)/2=0.25 -> repo_score=1-0.25
    assert list(out_dir.glob("*.json")), "emit_report should have written a json report"
    assert list(out_dir.glob("*.md")), "emit_report should have written a markdown report"


def test_scan_uses_files_param_instead_of_shelling_git_when_given(tmp_path, monkeypatch) -> None:
    repo = _init_repo_with_proposal(tmp_path)

    def fake_verdict(section, candidates, *, model="claude-sonnet-4-5"):
        return VerdictResult(status="implemented", confidence=0.9, reasoning="matched evidence")

    monkeypatch.setattr(pipeline, "llm_status_verdict", fake_verdict)

    def boom(*args, **kwargs):
        raise AssertionError("parse_after_files should not run when files= is given")

    monkeypatch.setattr(pipeline, "parse_after_files", boom)

    report = pipeline.scan(["src/retrieval_config.py"], repo, judge_name="heuristic")

    statuses = {v.section_id: v.status for v in report.docs[0].sections}
    assert statuses["goals"] == "implemented"
