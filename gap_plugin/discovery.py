"""discover_docs: file-pattern scan of proposal docs -> implementation claims.

harness-lite:proposal's fixed template (Before/After/Business impact/Pros/
Cons/Limitations/Decision) means only "## After" lists things that must show
up in the implementing diff -- "List every file that changes -- this list is
the reviewer's commitment" (the proposal skill's own words). Checking
Before/Business impact/Pros/Cons/Limitations/Decision against code evidence
is a category error: they are narrative, not implementation claims, and can
never "match" regardless of judge quality. So this extracts one claim per
top-level bullet in the After section only.
"""
from __future__ import annotations

import re
from pathlib import Path

from gap_plugin.types import ProposalDoc, Section

_PATTERNS = ("docs/proposals/**/*.md", "**/*.proposal.md")
# A repo adopting this tool shouldn't get its own *.proposal.md test fixtures
# swept in as if they were real proposals to check against.
_EXCLUDED_DIR_PARTS = {"tests", "test", "node_modules", "venv", ".venv"}
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_CLAIM_HEADING = "after"
_BULLET = re.compile(r"^-\s+(.+)$")
_CODE_SPAN = re.compile(r"`([^`]+)`")


def _strip_frontmatter(text: str) -> str:
    return _FRONTMATTER.sub("", text, count=1)


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def _heading_bodies(body: str) -> list[tuple[str, str]]:
    headings = list(_HEADING.finditer(body))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(headings):
        heading = m.group(1).strip()
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        out.append((heading, body[start:end].strip()))
    return out


def _split_into_claims(doc_path: str, after_body: str) -> list[Section]:
    """One claim per top-level '- ' bullet; wrapped continuation lines merge
    into the bullet above them; prose outside a bullet (lead-ins, bold
    subheadings) is not a claim."""
    claims: list[Section] = []
    current: list[str] = []

    def flush() -> None:
        if not current:
            return
        text = " ".join(current).strip()
        code = _CODE_SPAN.search(text)
        label = code.group(1) if code else f"claim-{len(claims)}"
        claims.append(Section(doc_path=doc_path, section_id=_slug(label), heading=label, section_text=text))
        current.clear()

    for line in after_body.splitlines():
        m = _BULLET.match(line)
        if m:
            flush()
            current.append(m.group(1))
        elif line.strip():
            if current:
                current.append(line.strip())
        else:
            flush()
    flush()
    return claims


def parse_sections(doc_path: str, text: str) -> list[Section]:
    body = _strip_frontmatter(text)
    claims: list[Section] = []
    for heading, section_body in _heading_bodies(body):
        if _slug(heading) == _CLAIM_HEADING:
            claims.extend(_split_into_claims(doc_path, section_body))
    return claims


def discover_docs(repo_root: Path) -> list[ProposalDoc]:
    repo_root = Path(repo_root)
    paths: set[Path] = set()
    for pattern in _PATTERNS:
        paths.update(repo_root.glob(pattern))

    docs: list[ProposalDoc] = []
    for path in sorted(paths):
        rel = path.relative_to(repo_root).as_posix()
        if _EXCLUDED_DIR_PARTS & set(Path(rel).parts[:-1]):
            continue
        sections = parse_sections(rel, path.read_text())
        docs.append(ProposalDoc(path=rel, sections=sections))
    return docs
