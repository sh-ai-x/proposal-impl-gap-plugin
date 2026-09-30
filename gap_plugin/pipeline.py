"""scan(files, repo) -> RepoReport: the plain for-loop orchestrator (archify/sequence-pr-scan).

Retrieval itself is a state machine (retrieval.run_retrieval); the top level
stays a for-loop by design -- no state-machine overhead at the orchestrator.
"""
from __future__ import annotations

import functools
from pathlib import Path

from gap_plugin.bm25 import BM25Index
from gap_plugin.diffscan import diff_bullets, parse_after_files
from gap_plugin.discovery import discover_docs
from gap_plugin.judges import get_judge
from gap_plugin.llm import default_model
from gap_plugin.report import build_doc_report, build_repo_report, emit_report
from gap_plugin.retrieval import run_retrieval
from gap_plugin.types import DocReport, RepoReport, SectionVerdict
from gap_plugin.verdict import llm_status_verdict


def scan(
    files: list[str] | None,
    repo: Path,
    *,
    judge_name: str = "heuristic",
    provider: str = "anthropic",
    verdict_model: str | None = None,
    base_ref: str = "HEAD",
    retry_limit: int = 2,
    top_k: int = 10,
    out_dir: Path | None = None,
) -> RepoReport:
    repo = Path(repo)
    docs = discover_docs(repo)

    # `files` lets CI hand in the PR's changed-file list directly (matches the
    # sequence diagram's scan(files, repo) call); fall back to computing it
    # ourselves when the caller doesn't already know it.
    changed = set(files) if files else parse_after_files(repo, base_ref=base_ref)
    bullets = diff_bullets(repo, changed, base_ref=base_ref) if changed else []

    bm25 = BM25Index()
    bm25.build(bullets)

    judge = get_judge(judge_name)
    if judge_name == "haiku":
        judge = functools.partial(judge, provider=provider)

    verdict_model = verdict_model or default_model(provider, "sonnet")

    doc_reports: list[DocReport] = []
    for doc in docs:
        section_verdicts: list[SectionVerdict] = []
        for section in doc.sections:
            outcome = run_retrieval(section, bm25, judge, changed, retry_limit=retry_limit, top_k=top_k)
            if outcome.status == "missing_info":
                section_verdicts.append(
                    SectionVerdict(
                        doc_path=doc.path,
                        section_id=section.section_id,
                        status="unknown",
                        confidence=None,
                        reasoning="missing_info: retrieval exhausted retry budget",
                        judge_name=judge_name,
                        retrieval_attempts=outcome.attempts,
                    )
                )
                continue
            result = llm_status_verdict(section, outcome.candidates, provider=provider, model=verdict_model)
            section_verdicts.append(
                SectionVerdict(
                    doc_path=doc.path,
                    section_id=section.section_id,
                    status=result.status,
                    confidence=result.confidence,
                    reasoning=result.reasoning,
                    judge_name=judge_name,
                    retrieval_attempts=outcome.attempts,
                )
            )
        doc_reports.append(build_doc_report(doc, section_verdicts))

    repo_report = build_repo_report(doc_reports, judge_name=judge_name, verdict_model=verdict_model)
    if out_dir is not None:
        emit_report(repo_report, Path(out_dir))
    return repo_report
