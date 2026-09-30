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
class Candidate:
    file_path: str
    snippet: str
    score: float
    # `source` was Literal["bm25", "symbol"] when a retrieval layer
    # existed; direct.py and tests/test_judges.py only ever pass
    # "bm25", but the post-refactor `Candidate` is a direct-Read
    # candidate and "symbol" never materialized. Keep it a plain
    # `str` so callers can name future sources without widening
    # the literal.
    source: str


@dataclass(frozen=True)
class JudgeVerdict:
    accepted: bool
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
