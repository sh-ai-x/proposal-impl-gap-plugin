import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "gap_scan.py"


def test_gap_scan_runs_clean_against_a_repo_with_no_proposals(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "docs scanned: 0" in result.stdout


def test_gap_scan_help_lists_expected_flags() -> None:
    result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)

    assert result.returncode == 0
    assert "--provider" in result.stdout
    assert "--repo" in result.stdout
