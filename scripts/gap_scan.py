#!/usr/bin/env python3
"""gap_scan.py -- run gap_plugin.scan(files, repo) and print a summary.

Usage:
  python3 scripts/gap_scan.py                              # scan this repo
  python3 scripts/gap_scan.py --judge haiku --provider minimax
  python3 scripts/gap_scan.py --files a.py b.py             # CI-style: hand in the changed-file list

Output:
  data/scan/reports/<timestamp>.json   full structured RepoReport
  data/scan/reports/<timestamp>.md     human-readable summary
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))  # run directly without installing the package

from gap_plugin import scan  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, default=REPO, help="repo root to scan (default: this repo)")
    parser.add_argument("--files", nargs="*", default=None, help="changed files (default: computed via git diff)")
    parser.add_argument("--judge", default="heuristic", choices=["heuristic", "haiku", "jev"])
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "minimax", "deepseek"])
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--out-dir", type=Path, default=REPO / "data" / "scan" / "reports")
    args = parser.parse_args()

    report = scan(
        args.files,
        args.repo,
        judge_name=args.judge,
        provider=args.provider,
        base_ref=args.base_ref,
        out_dir=args.out_dir,
    )

    print(f"repo_score: {report.repo_score:.3f}")
    print(f"judge: {report.judge_name}  verdict_model: {report.verdict_model}")
    print(f"docs scanned: {len(report.docs)}")
    for doc in report.docs:
        counts = ", ".join(f"{k}={v}" for k, v in sorted(doc.status_counts.items()))
        print(f"  {doc.doc_path}: {counts or '(no sections)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
