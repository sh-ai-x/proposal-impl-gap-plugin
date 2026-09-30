"""Reference-free evaluation: assess a scan() run's retrieval quality with no
ground truth and no extra labeled data.

Motivation: scripts/derive_gt.py + scripts/eval_judge.py need a git-history-
derived (or curated) ground truth set, which is specific to this repo's
ai_saas worktree setup and doesn't travel to another repo. Most repos
adopting gap_plugin will have many proposals and no GT at all. These metrics
are computed entirely from the retrieval/judge process's own behavior on its
own input, so they run on any repo, on the actual proposals it has, today.

Faithfulness/groundedness of verdict.reasoning (a common reference-free RAG
metric) is deliberately not included yet: it requires a verdict to actually
be produced, and pipeline.scan() discards the evidence candidates once a
SectionVerdict is built. Add it once llm_status_verdict output is wired to
retain its input evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gap_plugin.bm25 import BM25Index
from gap_plugin.diffscan import diff_bullets, parse_after_files
from gap_plugin.discovery import discover_docs
from gap_plugin.judges import get_judge
from gap_plugin.retrieval import run_retrieval
from gap_plugin.text import tokenize


@dataclass(frozen=True)
class CandidateDiagnostic:
    file_path: str
    score: float
    overlap: float  # token-overlap fraction with the section's query text


@dataclass(frozen=True)
class SectionDiagnostic:
    doc_path: str
    section_id: str
    status: str  # "answer" | "missing_info"
    attempts: int
    candidates: list[CandidateDiagnostic]


@dataclass(frozen=True)
class DiagnosticsRun:
    sections: list[SectionDiagnostic]
    total_evidence_files: int


@dataclass(frozen=True)
class ReferenceFreeMetrics:
    n_sections: int
    retrieval_completion_rate: float  # fraction of sections resolved as "answer"
    mean_attempts: float
    first_try_rate: float  # fraction resolved without any retry
    mean_context_relevance: float  # avg best-candidate token-overlap per section
    evidence_diversity: float  # distinct cited files / distinct evidence files available


def diagnose(
    repo: Path,
    *,
    files: list[str] | None = None,
    judge_name: str = "heuristic",
    base_ref: str = "HEAD",
    retry_limit: int = 2,
    top_k: int = 10,
) -> DiagnosticsRun:
    repo = Path(repo)
    docs = discover_docs(repo)

    if docs:
        changed = set(files) if files else parse_after_files(repo, base_ref=base_ref)
        bullets = diff_bullets(repo, changed, base_ref=base_ref) if changed else []
    else:
        changed, bullets = set(), []

    bm25 = BM25Index()
    bm25.build(bullets)
    judge = get_judge(judge_name)

    sections: list[SectionDiagnostic] = []
    for doc in docs:
        for section in doc.sections:
            outcome = run_retrieval(section, bm25, judge, changed, retry_limit=retry_limit, top_k=top_k)
            section_tokens = set(tokenize(section.section_text))
            candidates = [
                CandidateDiagnostic(
                    file_path=c.file_path,
                    score=c.score,
                    overlap=(
                        len(section_tokens & set(tokenize(c.snippet))) / len(section_tokens)
                        if section_tokens
                        else 0.0
                    ),
                )
                for c in outcome.candidates
            ]
            sections.append(
                SectionDiagnostic(
                    doc_path=doc.path,
                    section_id=section.section_id,
                    status=outcome.status,
                    attempts=outcome.attempts,
                    candidates=candidates,
                )
            )
    return DiagnosticsRun(sections=sections, total_evidence_files=len(bullets))


def compute_metrics(diagnostics: list[SectionDiagnostic], *, total_evidence_files: int) -> ReferenceFreeMetrics:
    n = len(diagnostics)
    if n == 0:
        nan = float("nan")
        return ReferenceFreeMetrics(0, nan, nan, nan, nan, nan)

    completion = sum(1 for d in diagnostics if d.status == "answer") / n
    mean_attempts = sum(d.attempts for d in diagnostics) / n
    first_try = sum(1 for d in diagnostics if d.attempts == 1) / n
    mean_relevance = sum(max((c.overlap for c in d.candidates), default=0.0) for d in diagnostics) / n

    cited_files = {c.file_path for d in diagnostics for c in d.candidates}
    diversity = (len(cited_files) / total_evidence_files) if total_evidence_files else 0.0

    return ReferenceFreeMetrics(
        n_sections=n,
        retrieval_completion_rate=completion,
        mean_attempts=mean_attempts,
        first_try_rate=first_try,
        mean_context_relevance=mean_relevance,
        evidence_diversity=diversity,
    )
