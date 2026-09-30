from pathlib import Path

from gap_plugin.discovery import discover_docs


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_discover_docs_extracts_one_claim_per_after_bullet(tmp_path: Path) -> None:
    """Only '## After' lists implementation commitments (the proposal template's
    own words: "List every file that changes -- this list is the reviewer's
    commitment"). Before/Business impact/Pros/Cons/Limitations/Decision are
    narrative, not claims to check against code -- and are ignored entirely."""
    doc_text = (
        "---\n"
        "title: Sample\n"
        "---\n"
        "## Before\n"
        "No retry budget existed.\n\n"
        "## After\n"
        "- `src/retry.py` — Add a retry_limit knob to the loop.\n"
        "- `src/cache.py` — Add a caching layer.\n\n"
        "## Cons\n"
        "This is prose, not a file commitment, and must not become a claim.\n"
    )
    _write(tmp_path / "docs" / "proposals" / "widget.proposal.md", doc_text)

    docs = discover_docs(tmp_path)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.path == "docs/proposals/widget.proposal.md"
    assert [s.heading for s in doc.sections] == ["src/retry.py", "src/cache.py"]
    assert "Add a retry_limit knob" in doc.sections[0].section_text
    assert "title: Sample" not in doc.sections[0].section_text


def test_discover_docs_merges_wrapped_continuation_lines_into_one_claim(tmp_path: Path) -> None:
    doc_text = (
        "## After\n"
        "- `gap_plugin/discovery.py` — globs proposal docs\n"
        "  and splits them into sections, excluding test fixtures.\n"
    )
    _write(tmp_path / "docs" / "proposals" / "x.proposal.md", doc_text)

    docs = discover_docs(tmp_path)

    assert len(docs[0].sections) == 1
    assert "excluding test fixtures" in docs[0].sections[0].section_text


def test_discover_docs_returns_no_claims_when_doc_has_no_after_section(tmp_path: Path) -> None:
    doc_text = "## Before\nOld state.\n\n## Decision\nPending.\n"
    _write(tmp_path / "docs" / "proposals" / "x.proposal.md", doc_text)

    docs = discover_docs(tmp_path)

    assert docs[0].sections == []


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
