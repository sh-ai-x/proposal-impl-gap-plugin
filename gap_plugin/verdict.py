"""llm_status_verdict: Claude call producing an ACStatus verdict with structured output."""
from __future__ import annotations

import json
import os
from typing import Any

from gap_plugin.errors import MissingAPIKeyError
from gap_plugin.types import Candidate, STATUSES, Section, VerdictResult


def _build_prompt(section: Section, candidates: list[Candidate]) -> str:
    candidate_text = "\n\n".join(f"[{c.file_path}]\n{c.snippet}" for c in candidates) or "(no evidence retrieved)"
    return (
        "Given the proposal section and the implementation evidence below, decide the "
        f"implementation status. Respond with JSON only: "
        f'{{"status": "<one of {list(STATUSES)}>", "confidence": <0..1>, "reasoning": "<one sentence>"}}.\n\n'
        f"Proposal section:\n{section.section_text}\n\n"
        f"Evidence:\n{candidate_text}"
    )


def _parse_verdict(raw_text: str) -> VerdictResult:
    try:
        data: dict[str, Any] = json.loads(raw_text)
        status = str(data["status"])
        confidence = float(data.get("confidence", 0.0))
        reasoning = str(data.get("reasoning", ""))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return VerdictResult(status="unknown", confidence=0.0, reasoning=f"parse error: {exc}")
    if status not in STATUSES:
        return VerdictResult(status="unknown", confidence=confidence, reasoning=f"status {status!r} outside taxonomy")
    return VerdictResult(status=status, confidence=max(0.0, min(1.0, confidence)), reasoning=reasoning)


def llm_status_verdict(
    section: Section,
    candidates: list[Candidate],
    *,
    model: str = "claude-sonnet-4-5",
) -> VerdictResult:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise MissingAPIKeyError("llm_status_verdict requires ANTHROPIC_API_KEY")
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    prompt = _build_prompt(section, candidates)
    resp = client.messages.create(model=model, max_tokens=300, messages=[{"role": "user", "content": prompt}])
    raw_text = resp.content[0].text
    return _parse_verdict(raw_text)
