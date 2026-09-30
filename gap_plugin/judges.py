"""Pluggable judges for the gap-plugin direct-judge path.

Only one judge is registered: `jev` (TypeSafe System One / Noul). It
classifies a single candidate against a section's claim, with internal
escalation to haiku when Jev's own answer is in the 0.3-0.7 uncertainty
band. Used by `gap_plugin/direct.py:resolve`.

The old `heuristic_judge` (token overlap + after_files bonus) lived here
because it gated BM25 retrieval candidates. With the retrieval layer
removed, there is nothing for a heuristic to gate -- direct.read +
jev_judge replaces both.

`scripts/eval_judge.py` keeps the offline heuristic evaluator for the
ground-truth harness only; production inference goes through the
single direct-judge path below.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from gap_plugin.errors import MissingAPIKeyError
from gap_plugin.llm import call_claude, default_model
from gap_plugin.types import Candidate, JudgeVerdict, Section

CONFIDENCE_THRESHOLD = 0.7

# Below this |noul - 0.5| * 2 "certainty", Jev's own answer is too close to a
# coin flip to trust -- escalate to an LLM judge instead of resolving on it.
JEV_ESCALATION_CERTAINTY = 0.4

TYPESAFE_API_URL = "https://api.typesafe.ai/v1/systemone"


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
    """LLM judge used as the second tier inside `jev_judge` when Jev is uncertain."""
    model = model or default_model(provider, "haiku")
    raw_text = call_claude(
        _build_judge_prompt(section, candidates), model=model, max_tokens=200, provider=provider
    )
    return _parse_judge_response(raw_text)


def _call_jev(state: dict[str, Any], instructions: str, criteria: dict[str, str]) -> float:
    """POST one Noul question to TypeSafe's System One API. Returns `noul`,
    the model's probability (0..1) that the condition holds -- not a
    confidence score; see JEV_ESCALATION_CERTAINTY for how this module
    derives one."""
    api_key = os.environ.get("JEV_API_KEY")
    if not api_key:
        raise MissingAPIKeyError("jev_judge requires JEV_API_KEY")
    body = json.dumps(
        {
            "state": state,
            "model": "jev-latest",
            "questions": {"match": {"type": "noul", "instructions": instructions, "criteria": criteria}},
        }
    ).encode()
    req = urllib.request.Request(
        TYPESAFE_API_URL,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return float(data["answers"]["match"]["noul"])


def jev_judge(
    section: Section,
    candidates: list[Candidate],
    after_files: set[str],
    *,
    provider: str = "anthropic",
    escalate_below: float = JEV_ESCALATION_CERTAINTY,
) -> JudgeVerdict:
    """Jev (TypeSafe System One, Noul primitive) judges whether the retrieved
    evidence shows the claim is implemented. When Jev itself is too unsure
    (noul near 0.5), escalate to haiku_judge rather than resolve on a coin
    flip -- this is the one judge that can change its mind mid-call."""
    evidence_text = "\n\n".join(f"[{c.file_path}]\n{c.snippet}" for c in candidates) or "(no evidence retrieved)"
    noul = _call_jev(
        state={
            "proposal_claim": section.section_text,
            "evidence": evidence_text,
            "after_files_touched": any(c.file_path in after_files for c in candidates),
        },
        instructions=(
            "Given the proposal claim and the retrieved code evidence, judge whether the "
            "evidence shows the claim has actually been implemented in the codebase."
        ),
        criteria={
            "true": "the evidence's file content fulfills what the claim describes",
            "false": "the evidence is missing, unrelated, or contradicts the claim",
        },
    )
    certainty = abs(noul - 0.5) * 2

    if certainty < escalate_below:
        verdict = haiku_judge(section, candidates, after_files, provider=provider)
        return JudgeVerdict(
            accepted=verdict.accepted,
            confidence=verdict.confidence,
            reasoning=(
                f"jev uncertain (noul={noul:.2f}, certainty={certainty:.2f}) "
                f"-- escalated to haiku: {verdict.reasoning}"
            ),
        )

    accepted = noul >= 0.5
    return JudgeVerdict(
        accepted=accepted,
        confidence=certainty,
        reasoning=f"jev noul={noul:.2f} ({'implemented' if accepted else 'not implemented'} per evidence)",
    )
