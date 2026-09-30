"""Shared data types for the Gap Plugin pipeline (see archify/architecture-gap-plugin)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Verbatim from scripts/eval_judge.py STATUSES -- single source of truth for the taxonomy.
ACStatus = Literal["implemented", "partial", "missing", "added", "contradicted", "unknown"]
STATUSES: tuple[ACStatus, ...] = (
    "implemented", "partial", "missing", "added", "contradicted", "unknown",
)


@dataclass(frozen=True)
class Section:
    doc_path: str
    section_id: str
    heading: str
    section_text: str


@dataclass(frozen=True)
class ProposalDoc:
    path: str
    sections: list[Section]


@dataclass(frozen=True)
class EvidenceItem:
    """One 'After bullet' -- implementation evidence for a changed file, BM25's corpus."""

    file_path: str
    text: str


@dataclass(frozen=True)
class Candidate:
    file_path: str
    snippet: str
    score: float
    source: Literal["bm25", "symbol"]


@dataclass(frozen=True)
class JudgeVerdict:
    accepted: bool
    confidence: float
    reasoning: str


@dataclass(frozen=True)
class RetrievalOutcome:
    status: Literal["answer", "missing_info"]
    candidates: list[Candidate]
    attempts: int


@dataclass(frozen=True)
class VerdictResult:
    status: ACStatus
    confidence: float
    reasoning: str


@dataclass(frozen=True)
class SectionVerdict:
    doc_path: str
    section_id: str
    status: ACStatus
    confidence: float | None
    reasoning: str
    judge_name: str
    retrieval_attempts: int


@dataclass(frozen=True)
class DocReport:
    doc_path: str
    sections: list[SectionVerdict]
    status_counts: dict[str, int]


@dataclass(frozen=True)
class RepoReport:
    docs: list[DocReport]
    repo_score: float
    judge_name: str
    verdict_model: str
    generated_at: str
