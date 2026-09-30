"""'parse After-files': after_files (changed paths) and diff_bullets (evidence text for BM25)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from gap_plugin.types import EvidenceItem


def after_files(repo_root: Path, base_ref: str = "HEAD") -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base_ref],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def _added_lines(repo_root: Path, file_path: str, base_ref: str) -> str:
    result = subprocess.run(
        ["git", "diff", "--no-color", base_ref, "--", file_path],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [
        line[1:]
        for line in result.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return "\n".join(lines).strip()


def diff_bullets(repo_root: Path, files: set[str], base_ref: str = "HEAD") -> list[EvidenceItem]:
    bullets: list[EvidenceItem] = []
    for file_path in sorted(files):
        text = _added_lines(repo_root, file_path, base_ref) or file_path
        bullets.append(EvidenceItem(file_path=file_path, text=text))
    return bullets
