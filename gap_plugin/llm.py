"""Shared Claude-Messages-API call boundary for haiku_judge and llm_status_verdict.

MiniMax and DeepSeek both expose an Anthropic-Messages-compatible endpoint
(same convention .github/workflows/hl-review.yml already uses for CI judging),
so the `anthropic` SDK covers all three providers via `base_url` -- no new
dependency needed.
"""
from __future__ import annotations

import os
from typing import Literal

from gap_plugin.errors import MissingAPIKeyError

Provider = Literal["anthropic", "minimax", "deepseek"]

_PROVIDERS: dict[str, dict[str, str | None]] = {
    "anthropic": {
        "env_var": "ANTHROPIC_API_KEY",
        "base_url": None,
        "haiku_model": "claude-haiku-4-5",
        "sonnet_model": "claude-sonnet-4-5",
    },
    "minimax": {
        "env_var": "MINIMAX_API_KEY",
        "base_url": "https://api.minimax.io/anthropic",
        "haiku_model": "MiniMax-M3[1m]",
        "sonnet_model": "MiniMax-M3[1m]",
    },
    "deepseek": {
        "env_var": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/anthropic",
        "haiku_model": "deepseek-v4-flash",
        "sonnet_model": "deepseek-v4-pro",
    },
}


def _config(provider: str) -> dict[str, str | None]:
    try:
        return _PROVIDERS[provider]
    except KeyError:
        raise ValueError(f"unknown provider: {provider!r}; choices: {sorted(_PROVIDERS)}") from None


def default_model(provider: str, tier: Literal["haiku", "sonnet"]) -> str:
    return _config(provider)[f"{tier}_model"]  # type: ignore[return-value]


def call_claude(prompt: str, *, model: str, max_tokens: int, provider: str = "anthropic") -> str:
    config = _config(provider)
    env_var = config["env_var"]
    api_key = os.environ.get(env_var)
    if not api_key:
        raise MissingAPIKeyError(f"{provider} call requires {env_var}")
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key, base_url=config["base_url"])
    resp = client.messages.create(model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
    return resp.content[0].text
