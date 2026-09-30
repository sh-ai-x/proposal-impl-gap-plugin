"""Pluggable judge candidates for the retrieval subsystem's 'Good?' gate.

Each judge decides, for one BM25 query, whether the retrieved candidates are
good enough to accept (a fixed CONFIDENCE_THRESHOLD is the single source of
truth for that decision, shared by every judge so retrieval.py stays
judge-agnostic and only reads `.accepted`).
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from gap_plugin.llm import call_claude, default_model
from gap_plugin.types import Candidate, JudgeVerdict, Section

CONFIDENCE_THRESHOLD = 0.7

Judge = Callable[[Section, list[Candidate], set[str]], JudgeVerdict]

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def heuristic_judge(section: Section, candidates: list[Candidate], after_files: set[str]) -> JudgeVerdict:
    """No AI, no cost: token-overlap between section_text and candidate snippets,
    plus an 'After bullets' intersection bonus (the file was actually touched)."""
    section_tokens = _tokenize(section.section_text)
    best_overlap = 0.0
    for c in candidates:
        if not section_tokens:
            continue
        overlap = len(section_tokens & _tokenize(c.snippet)) / len(section_tokens)
        best_overlap = max(best_overlap, overlap)

    after_hit = any(c.file_path in after_files for c in candidates)
    confidence = min(1.0, best_overlap + (0.2 if after_hit else 0.0))
    accepted = confidence >= CONFIDENCE_THRESHOLD
    return JudgeVerdict(
        accepted=accepted,
        confidence=confidence,
        reasoning=f"token overlap={best_overlap:.2f}, after_files hit={after_hit}",
    )


def _build_judge_prompt(section: Section, candidates: list[Candidate]) -> str:
    candidate_text = "\n\n".join(f"[{c.file_path}]\n{c.snippet}" for c in candidates) or "(no candidates)"
    return (
        "You are judging whether the retrieved implementation evidence below is "
        "sufficient to answer the proposal section. Respond with JSON only: "
        '{"confidence": <0..1>, "reasoning": "<one sentence>"}.\n\n'
        f"Proposal section:\n{section.section_text}\n\n"
        f"Retrieved evidence:\n{candidate_text}"
    )


def _parse_judge_response(raw_text: str) -> JudgeVerdict:
    try:
        data: dict[str, Any] = json.loads(raw_text)
        confidence = float(data["confidence"])
        reasoning = str(data.get("reasoning", ""))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return JudgeVerdict(accepted=False, confidence=0.0, reasoning=f"parse error: {exc}")
    confidence = max(0.0, min(1.0, confidence))
    return JudgeVerdict(
        accepted=confidence >= CONFIDENCE_THRESHOLD,
        confidence=confidence,
        reasoning=reasoning,
    )


def haiku_judge(
    section: Section,
    candidates: list[Candidate],
    after_files: set[str],
    *,
    provider: str = "anthropic",
    model: str | None = None,
) -> JudgeVerdict:
    model = model or default_model(provider, "haiku")
    raw_text = call_claude(
        _build_judge_prompt(section, candidates), model=model, max_tokens=200, provider=provider
    )
    return _parse_judge_response(raw_text)


def jev_judge(section: Section, candidates: list[Candidate], after_files: set[str]) -> JudgeVerdict:
    raise NotImplementedError(
        "Jev/typesafe-ai judge integration is pending -- see README.md 'Jev integration' status"
    )


_JUDGES: dict[str, Judge] = {
    "heuristic": heuristic_judge,
    "haiku": haiku_judge,
    "jev": jev_judge,
}


def get_judge(name: str) -> Judge:
    try:
        return _JUDGES[name]
    except KeyError:
        raise ValueError(f"unknown judge: {name!r}; choices: {sorted(_JUDGES)}") from None
