import shutil
import subprocess
from pathlib import Path

import pytest

import gap_plugin.judges as judges_module
import gap_plugin.pipeline as pipeline
from gap_plugin.errors import MissingAPIKeyError
from gap_plugin.types import JudgeVerdict

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
    """Direct judge: implemented for the file that exists, missing for the one that doesn't."""
    repo = _init_repo_with_proposal(tmp_path)
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    # High noul (0.95) -> confident accept; noul<0.5 is unreachable here because the
    # second claim's file genuinely doesn't exist, so direct.resolve short-circuits.
    monkeypatch.setattr(judges_module, "_call_jev", lambda *a, **k: 0.95)

    out_dir = tmp_path / "out"
    report = pipeline.scan(repo, out_dir=out_dir)

    assert len(report.docs) == 1
    doc = report.docs[0]
    assert doc.doc_path == "docs/proposals/widget.proposal.md"
    statuses = {v.section_id: v.status for v in doc.sections}

    assert statuses["src-retrieval-config-py"] == "implemented"
    assert statuses["src-oauth-login-py"] == "missing"

    assert report.repo_score == 0.5  # gap = (0.0 implemented + 1.0 missing) / 2 = 0.5 -> repo_score = 0.5
    assert list(out_dir.glob("*.json")), "emit_report should have written a json report"
    assert list(out_dir.glob("*.md")), "emit_report should have written a markdown report"


def test_scan_escalates_to_haiku_when_jev_is_uncertain(tmp_path, monkeypatch) -> None:
    """Jev noul in the uncertainty zone triggers a haiku escalation; result follows haiku."""
    repo = _init_repo_with_proposal(tmp_path)
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setattr(judges_module, "_call_jev", lambda *a, **k: 0.55)  # certainty=0.1, below 0.4 floor
    monkeypatch.setattr(
        judges_module,
        "haiku_judge",
        lambda *a, **k: JudgeVerdict(accepted=True, confidence=0.81, reasoning="haiku says yes"),
    )

    report = pipeline.scan(repo, provider="minimax")
    statuses = {v.section_id: v.status for v in report.docs[0].sections}
    assert statuses["src-retrieval-config-py"] == "implemented"
    assert "escalated" in next(v.reasoning for v in report.docs[0].sections if v.section_id == "src-retrieval-config-py")


def test_scan_requires_jev_api_key(tmp_path, monkeypatch) -> None:
    repo = _init_repo_with_proposal(tmp_path)
    monkeypatch.delenv("JEV_API_KEY", raising=False)

    with pytest.raises(MissingAPIKeyError, match="JEV_API_KEY"):
        pipeline.scan(repo)
