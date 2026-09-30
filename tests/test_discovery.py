from pathlib import Path

from gap_plugin.discovery import discover_docs


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_discover_docs_finds_proposal_files_and_splits_sections(tmp_path: Path) -> None:
    doc_text = (
        "---\n"
        "title: Sample\n"
        "---\n"
        "## Goals\n"
        "Ship the widget.\n\n"
        "## Non-goals\n"
        "Do not ship the gadget.\n"
    )
    _write(tmp_path / "docs" / "proposals" / "widget.proposal.md", doc_text)

    docs = discover_docs(tmp_path)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.path == "docs/proposals/widget.proposal.md"
    assert [s.heading for s in doc.sections] == ["Goals", "Non-goals"]
    assert "Ship the widget." in doc.sections[0].section_text
    assert "frontmatter" not in doc.sections[0].section_text.lower()
    assert "title: Sample" not in doc.sections[0].section_text


def test_discover_docs_ignores_unrelated_markdown(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "research" / "notes.md", "## Not a proposal\nirrelevant\n")

    docs = discover_docs(tmp_path)

    assert docs == []


def test_discover_docs_returns_empty_list_when_no_proposals_dir(tmp_path: Path) -> None:
    assert discover_docs(tmp_path) == []


def test_discover_docs_excludes_test_fixtures(tmp_path: Path) -> None:
    """A repo adopting this tool shouldn't get its own *.proposal.md test
    fixtures swept in as if they were real proposals to check against."""
    _write(tmp_path / "tests" / "fixtures" / "sample.proposal.md", "## Goals\nx\n")
    _write(tmp_path / "docs" / "proposals" / "real.proposal.md", "## Goals\ny\n")

    docs = discover_docs(tmp_path)

    assert [d.path for d in docs] == ["docs/proposals/real.proposal.md"]
