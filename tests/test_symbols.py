from gap_plugin.symbols import symbol_candidates
from gap_plugin.types import Section


def test_symbol_candidates_is_stubbed_empty() -> None:
    section = Section("a.md", "s1", "Goals", "some text")

    assert symbol_candidates(section) == []
