import subprocess
from pathlib import Path

from gap_plugin.diffscan import after_files, diff_bullets


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "a.txt").write_text("one\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def test_after_files_reports_modified_file_vs_base_ref(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "a.txt").write_text("one\ntwo\n")

    changed = after_files(repo, base_ref="HEAD")

    assert changed == {"a.txt"}


def test_after_files_empty_when_no_changes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    changed = after_files(repo, base_ref="HEAD")

    assert changed == set()


def test_diff_bullets_carries_added_line_text(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "a.txt").write_text("one\ntwo\nretry_limit = 2\n")

    bullets = diff_bullets(repo, {"a.txt"}, base_ref="HEAD")

    assert len(bullets) == 1
    assert bullets[0].file_path == "a.txt"
    assert "retry_limit = 2" in bullets[0].text


def test_diff_bullets_falls_back_to_path_when_no_added_lines(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "a.txt").unlink()
    _git(repo, "add", "-A")

    bullets = diff_bullets(repo, {"a.txt"}, base_ref="HEAD")

    assert len(bullets) == 1
    assert bullets[0].text == "a.txt"
