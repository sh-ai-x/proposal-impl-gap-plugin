"""Shared Claude call boundary for haiku_judge and llm_status_verdict."""
from __future__ import annotations

import os

from gap_plugin.errors import MissingAPIKeyError


def call_claude(prompt: str, *, model: str, max_tokens: int) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise MissingAPIKeyError(f"{model} call requires ANTHROPIC_API_KEY")
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
    return resp.content[0].text
