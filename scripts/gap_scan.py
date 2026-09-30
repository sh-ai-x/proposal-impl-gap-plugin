#!/usr/bin/env python3
"""gap_scan.py -- run gap_plugin.scan(repo) and print a summary.

Direct-judge pipeline: each proposal bullet names a file, the scanner reads
it and asks Jev (TypeSafe System One / Noul) to classify. Needs JEV_API_KEY.
Jev escalates internally to an LLM judge (provider's matching key) when its
own answer is in the 0.3-0.7 uncertainty band.

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
from gap_plugin.discovery import discover_docs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, default=REPO, help="repo root to scan (default: this repo)")
    parser.add_argument("--provider", default="minimax", choices=["anthropic", "minimax", "deepseek"])
    parser.add_argument("--out-dir", type=Path, default=REPO / "data" / "scan" / "reports")
    args = parser.parse_args()

    docs = discover_docs(args.repo)
    report = scan(args.repo, docs=docs, provider=args.provider, out_dir=args.out_dir)

    print(f"repo_score: {report.repo_score:.3f}")
    print(f"judge: {report.judge_name}  verdict_model: {report.verdict_model}")
    print(f"docs scanned: {len(report.docs)}")
    for doc in report.docs:
        counts = ", ".join(f"{k}={v}" for k, v in sorted(doc.status_counts.items()))
        print(f"  {doc.doc_path}: {counts or '(no sections)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
