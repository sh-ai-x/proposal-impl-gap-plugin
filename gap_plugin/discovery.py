"""discover_docs: file-pattern scan of proposal docs, split into headed sections."""
from __future__ import annotations

import re
from pathlib import Path

from gap_plugin.types import ProposalDoc, Section

_PATTERNS = ("docs/proposals/**/*.md", "**/*.proposal.md")
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


def _strip_frontmatter(text: str) -> str:
    return _FRONTMATTER.sub("", text, count=1)


def _slug(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")


def parse_sections(doc_path: str, text: str) -> list[Section]:
    body = _strip_frontmatter(text)
    headings = list(_HEADING.finditer(body))
    sections: list[Section] = []
    for i, m in enumerate(headings):
        heading = m.group(1).strip()
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        section_text = f"{heading}\n{body[start:end].strip()}".strip()
        sections.append(
            Section(
                doc_path=doc_path,
                section_id=_slug(heading),
                heading=heading,
                section_text=section_text,
            )
        )
    return sections


def discover_docs(repo_root: Path) -> list[ProposalDoc]:
    repo_root = Path(repo_root)
    paths: set[Path] = set()
    for pattern in _PATTERNS:
        paths.update(repo_root.glob(pattern))

    docs: list[ProposalDoc] = []
    for path in sorted(paths):
        rel = path.relative_to(repo_root).as_posix()
        sections = parse_sections(rel, path.read_text())
        docs.append(ProposalDoc(path=rel, sections=sections))
    return docs
