"""Shared tokenizer: single source of truth for bm25.py, judges.py, refmetrics.py."""
from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())
