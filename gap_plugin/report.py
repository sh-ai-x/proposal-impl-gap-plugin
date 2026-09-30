"""Aggregation: per-doc report -> repo_score (weighted) -> emit_report (markdown + JSON)."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from gap_plugin.types import DocReport, ProposalDoc, RepoReport, SectionVerdict

# Gap weight per status: 1.0 = full gap, 0.0 = no gap. repo_score = 1 - mean(weight).
_GAP_WEIGHT: dict[str, float] = {
    "implemented": 0.0,
    "added": 0.0,
    "partial": 0.5,
    "unknown": 0.5,
    "missing": 1.0,
    "contradicted": 1.0,
}


def build_doc_report(doc: ProposalDoc, verdicts: list[SectionVerdict]) -> DocReport:
    counts = Counter(v.status for v in verdicts)
    return DocReport(doc_path=doc.path, sections=verdicts, status_counts=dict(counts))


def build_repo_report(
    doc_reports: list[DocReport],
    *,
    judge_name: str,
    verdict_model: str,
) -> RepoReport:
    all_verdicts = [v for d in doc_reports for v in d.sections]
    if all_verdicts:
        gap = sum(_GAP_WEIGHT.get(v.status, 0.5) for v in all_verdicts) / len(all_verdicts)
        repo_score = 1.0 - gap
    else:
        repo_score = 1.0
    return RepoReport(
        docs=doc_reports,
        repo_score=repo_score,
        judge_name=judge_name,
        verdict_model=verdict_model,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _render_markdown(report: RepoReport) -> str:
    lines = [
        "# Gap Plugin Report",
        "",
        f"- judge: {report.judge_name}",
        f"- verdict_model: {report.verdict_model}",
        f"- generated_at: {report.generated_at}",
        f"- repo_score: {report.repo_score:.3f}",
        "",
        "| Doc | Status counts |",
        "|---|---|",
    ]
    for doc in report.docs:
        counts = ", ".join(f"{k}={v}" for k, v in sorted(doc.status_counts.items()))
        lines.append(f"| {doc.doc_path} | {counts} |")
    return "\n".join(lines) + "\n"


def emit_report(report: RepoReport, out_dir: Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"{ts}.json"
    md_path = out_dir / f"{ts}.md"
    json_path.write_text(json.dumps(asdict(report), indent=2))
    md_path.write_text(_render_markdown(report))
    return json_path, md_path
