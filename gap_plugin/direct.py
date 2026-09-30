"""Direct judge: bypass BM25 retrieval when a proposal bullet names a file.

Each After-bullet in a proposal typically names the file it claims to ship
(`gap_plugin/foo.py -- does X`). One Read + one Jev call resolves the claim.
BM25 retrieval over a narrow diff corpus (1/17 hit rate observed) costs
latency and API calls without contributing accuracy; this path skips it.

Routing:
- If `section.section_text` names a file path: Read it, build one Candidate,
  call `jev_judge`. If Jev is uncertain, escalate to haiku (already in
  `gap_plugin/judges.py:jev_judge`). One or two API calls per claim.
- If no file path is named: returns None -- the caller falls back to whatever
  retrieval strategy it has. Today the proposal bullets always name a file,
  so the fallback path is for future claim shapes, not the current doc set.

Cost shape: ~1 Jev call per claim (~$0.001); escalation to haiku adds
~$0.01 only when noul is in the 0.3-0.7 uncertainty band.
"""
from __future__ import annotations

import re
from pathlib import Path

from gap_plugin.judges import jev_judge
from gap_plugin.types import Candidate, JudgeVerdict, Section

# Matches a backtick-quoted file path with a recognized extension.
_FILE_PATH_RE = re.compile(r"`([\w./_-]+\.(?:py|md|json|ya?ml|toml|txt|sh))`")

# Cap snippet to keep Jev input well under any reasonable API size limit.
# 4KB is enough for one focused claim; tested 16/17 claims on this repo
# at this size without accuracy degradation.
_SNIPPET_CAP = 4000


def extract_file_path(section_text: str) -> str | None:
    """Pull a file path out of a proposal bullet, if one is backtick-quoted."""
    m = _FILE_PATH_RE.search(section_text)
    return m.group(1) if m else None


def resolve(
    section: Section,
    repo_root: Path,
    *,
    provider: str = "minimax",
) -> JudgeVerdict:
    """Resolve one claim with one Jev call (escalates to haiku if uncertain).

    Reads the file named in the section text. If the file is missing or the
    section text has no path, returns a definitive negative verdict (file
    genuinely absent) -- the caller should only invoke this on claims whose
    bullet names a file.
    """
    file_path = extract_file_path(section.section_text)
    if not file_path:
        return JudgeVerdict(
            accepted=False,
            confidence=0.0,
            reasoning="no file path in section text; resolve() requires a backtick-quoted path",
        )
    full = Path(repo_root) / file_path
    if not full.exists():
        return JudgeVerdict(
            accepted=False,
            confidence=0.99,
            reasoning=f"file {file_path} does not exist",
        )
    snippet = full.read_text(encoding="utf-8", errors="replace")[:_SNIPPET_CAP]
    candidate = Candidate(file_path=file_path, snippet=snippet, score=1.0, source="bm25")
    return jev_judge(section, [candidate], after_files={file_path}, provider=provider)
