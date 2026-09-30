#!/usr/bin/env python3
"""gap_metrics.py -- reference-free evaluation of a scan(), no ground truth needed.

Unlike scripts/eval_judge.py (needs scripts/derive_gt.py's git-history-derived
ground truth, specific to this repo's ai_saas worktree setup), these metrics
are computed from the retrieval process's own behavior on its own proposals.
Runs on any repo, today, with no labeled data.

Usage:
  python3 scripts/gap_metrics.py                          # this repo, HEAD vs working tree
  python3 scripts/gap_metrics.py --base-ref origin/main    # this repo, vs a specific base
  python3 scripts/gap_metrics.py --repo /path/to/other/repo

Output:
  data/metrics/reports/<timestamp>.json   full per-section diagnostics
  data/metrics/reports/<timestamp>.md     human-readable summary
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gap_plugin.refmetrics import compute_metrics, diagnose  # noqa: E402


def render_markdown(metrics, run) -> str:
    lines = [
        "# Reference-Free Metrics Report",
        "",
        "No ground truth used -- computed entirely from this run's own retrieval process.",
        "",
        f"- sections: {metrics.n_sections}",
        f"- retrieval_completion_rate: {metrics.retrieval_completion_rate:.3f}  "
        "(fraction resolved as `answer` rather than `missing_info`)",
        f"- mean_attempts: {metrics.mean_attempts:.2f}",
        f"- first_try_rate: {metrics.first_try_rate:.3f}",
        f"- mean_context_relevance: {metrics.mean_context_relevance:.3f}  "
        "(avg best-candidate token overlap with the query section)",
        f"- evidence_diversity: {metrics.evidence_diversity:.3f}  "
        "(distinct cited files / distinct evidence files available)",
        "",
        "| Section | Status | Attempts | Best overlap |",
        "|---|---|---|---|",
    ]
    for s in run.sections:
        best = max((c.overlap for c in s.candidates), default=0.0)
        lines.append(f"| {s.doc_path}#{s.section_id} | {s.status} | {s.attempts} | {best:.2f} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--files", nargs="*", default=None)
    parser.add_argument("--judge", default="heuristic", choices=["heuristic", "haiku", "jev"])
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--out-dir", type=Path, default=REPO / "data" / "metrics" / "reports")
    args = parser.parse_args()

    run = diagnose(args.repo, files=args.files, judge_name=args.judge, base_ref=args.base_ref)
    metrics = compute_metrics(run.sections, total_evidence_files=run.total_evidence_files)

    print(f"n_sections: {metrics.n_sections}")
    print(f"retrieval_completion_rate: {metrics.retrieval_completion_rate:.3f}")
    print(f"mean_attempts: {metrics.mean_attempts:.2f}")
    print(f"first_try_rate: {metrics.first_try_rate:.3f}")
    print(f"mean_context_relevance: {metrics.mean_context_relevance:.3f}")
    print(f"evidence_diversity: {metrics.evidence_diversity:.3f}")

    if run.sections:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (args.out_dir / f"{ts}.json").write_text(
            json.dumps({"metrics": asdict(metrics), "sections": [asdict(s) for s in run.sections]}, indent=2)
        )
        (args.out_dir / f"{ts}.md").write_text(render_markdown(metrics, run))

    return 0


if __name__ == "__main__":
    sys.exit(main())
