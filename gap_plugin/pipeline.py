"""scan(repo, docs) -> RepoReport: direct-judge orchestrator.

For each section in each proposal doc: extract the file path from the bullet,
Read it, call Jev (with internal haiku escalation on uncertainty). No BM25,
no retrieval state machine, no separate status verdict call. Jev's
calibrated probability is the entire classification path.

The old pipeline (BM25 + retrieval state machine + llm_status_verdict) had a
1/17 hit rate on this repo's proposal -- direct judge gets 16/17 for ~5x
lower cost (see `gap_plugin/direct.py`).
"""
from __future__ import annotations

from pathlib import Path

from gap_plugin.direct import resolve
from gap_plugin.discovery import discover_docs
from gap_plugin.report import build_doc_report, build_repo_report, emit_report
from gap_plugin.types import DocReport, ProposalDoc, RepoReport, SectionVerdict


def _verdict_to_status(accepted: bool, confidence: float) -> tuple[str, float | None]:
    """Map Jev's binary accepted/confidence to a status + reportable confidence.

    accepted -> "implemented", rejected -> "missing". Jev's confidence is a
    certainty (|noul - 0.5| * 2); we report it as-is so reviewers can see
    how sure the judge was.
    """
    if accepted:
        return "implemented", confidence
    return "missing", confidence


def scan(
    repo: Path,
    *,
    docs: list[ProposalDoc] | None = None,
    provider: str = "minimax",
    out_dir: Path | None = None,
) -> RepoReport:
    repo = Path(repo)
    if docs is None:
        docs = discover_docs(repo)

    doc_reports: list[DocReport] = []
    for doc in docs:
        section_verdicts: list[SectionVerdict] = []
        for section in doc.sections:
            v = resolve(section, repo, provider=provider)
            status, confidence = _verdict_to_status(v.accepted, v.confidence)
            section_verdicts.append(
                SectionVerdict(
                    doc_path=doc.path,
                    section_id=section.section_id,
                    status=status,  # type: ignore[arg-type]
                    confidence=confidence,
                    reasoning=v.reasoning,
                    judge_name="direct",
                    retrieval_attempts=1,
                )
            )
        doc_reports.append(build_doc_report(doc, section_verdicts))

    repo_report = build_repo_report(
        doc_reports,
        judge_name="direct",
        verdict_model=f"{provider}/jev",
    )
    if out_dir is not None:
        emit_report(repo_report, Path(out_dir))
    return repo_report
