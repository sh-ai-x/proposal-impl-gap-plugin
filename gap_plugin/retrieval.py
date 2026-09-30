"""Retrieval subsystem state machine (archify/lifecycle-retrieval):
enter -> Question (BM25 top-k) -> Good?(judge) -> answer | Rewrite -> retry-limit gate -> Question | missing_info.
"""
from __future__ import annotations

import re

from gap_plugin.judges import Judge
from gap_plugin.types import RetrievalOutcome, Section

_CASE_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")


def _rewrite_query(text: str) -> str:
    """Synonym/CamelCase rewrite: expand identifiers without embeddings."""
    split = _CASE_BOUNDARY.sub(r"\1 \2", text).replace("_", " ").replace("-", " ")
    return f"{text} {split}"


def run_retrieval(
    section: Section,
    bm25: object,
    judge: Judge,
    after_files: set[str],
    *,
    retry_limit: int = 2,
    top_k: int = 10,
) -> RetrievalOutcome:
    query_text = section.section_text
    attempt = 0
    candidates = []
    while True:
        attempt += 1
        candidates = bm25.query(query_text, k=top_k)
        verdict = judge(section, candidates, after_files)
        if verdict.accepted:
            return RetrievalOutcome(status="answer", candidates=candidates, attempts=attempt)
        if attempt > retry_limit:
            return RetrievalOutcome(status="missing_info", candidates=candidates, attempts=attempt)
        query_text = _rewrite_query(query_text)
