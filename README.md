# proposal-impl-gap-plugin

Measures drift between `/harness-lite:proposal` documents and their implementations.

## Architecture

See `archify/` for rendered diagrams + candidate sources. Each diagram has a sibling `candidate.json` source file in the same dir — the JSON is the truth; the HTML/PNG are renders. The current diagrams still describe the legacy BM25/retrieval design; they will be regenerated to match this direct-judge pipeline in a follow-up.

- `archify/architecture-gap-plugin/candidate.json` — source for the system architecture diagram
- `archify/gap-plugin-architecture.html` — rendered architecture

`gap_plugin/` — the implementation: `discover_docs` → `direct.resolve` (extract file path from claim → Read → Jev with internal haiku escalation) → per-doc/repo report. Entry point: `gap_plugin.scan(repo, docs=None)`. Tests: `pytest tests/`.

Why direct judge: with a narrow diff corpus BM25 retrieval hit 1/17 of claims on a real proposal. Reading the named file directly and asking Jev to classify gets 16/17 at ~5x lower cost. The BM25/retrieval state machine was removed; see `gap_plugin/direct.py` for the path that replaced it.

## Status

| Stage | State |
|---|---|
| Design | Diagrams in `archify/` are stale (legacy BM25 design); pipeline now uses direct judge |
| Pipeline | Implemented — `gap_plugin/`, runnable via `scripts/gap_scan.py` |
| LLM integration | Implemented for `anthropic`/`minimax`/`deepseek` (Anthropic-Messages-compatible, one SDK, `gap_plugin/llm.py`) — needs the matching `*_API_KEY` in `.env` |
| Jev integration | Implemented — TypeSafe System One (Noul primitive) via `JEV_API_KEY`; escalates to an LLM judge when Jev's answer is in the 0.3-0.7 uncertainty band, `gap_plugin/judges.py:jev_judge` |

## Run

```bash
# Run the Gap Plugin scan (direct judge: needs JEV_API_KEY; the matching provider's key for escalation)
python3 scripts/gap_scan.py                                    # provider=minimax default; reads JEV_API_KEY
python3 scripts/gap_scan.py --provider anthropic                # uses ANTHROPIC_API_KEY for escalation

# Run the gap_plugin test suite
python3 -m pytest tests/

# Audit CI gates
/harness-lite:ci-doctor
```
