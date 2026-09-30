"""Symbol index (tree-sitter/LSP) -- secondary retrieval signal, stubbed: no parser dependency."""
from __future__ import annotations

from gap_plugin.types import Candidate, Section


def symbol_candidates(section: Section) -> list[Candidate]:
    return []
