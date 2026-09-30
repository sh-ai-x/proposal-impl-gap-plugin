# proposal-impl-gap-plugin

Measures drift between `/harness-lite:proposal` documents and their implementations.

## Architecture

See `archify/` for rendered diagrams + candidate sources. Each diagram has a sibling `candidate.json` source file in the same dir — the JSON is the truth; the HTML/PNG are renders.

- `archify/gap-plugin-architecture.html` — system map (subsystems: discovery → retrieval → verdict → aggregation → observability)
- `archify/gap-plugin-sequence.html` — PR-time scan flow (BM25 → judge → Claude verdict → report)
- `archify/gap-plugin-lifecycle.html` — LangGraph retrieval state machine (bounded retry)
- `archify/measurement-architecture.html` — measurement system architecture
- `archify/measurement-sequence.html` — eval harness execution
- `gap_plugin/` — the implementation of the above: `discover_docs` → hand-rolled BM25 (over
  git-diff "After bullets") → bounded-retry retrieval state machine → pluggable judge
  (`heuristic`/`haiku`/`jev`) → `llm_status_verdict` → per-doc/repo report. Entry point:
  `gap_plugin.scan(files, repo)`. Tests: `pytest tests/`.

## Status

| Stage | State |
|---|---|
| Design | Complete (archify-rendered) |
| GT derivation | `scripts/derive_gt.py` (git-only) |
| Eval harness | `scripts/eval_judge.py` (anti-contamination) |
| Gap Plugin pipeline | Implemented — `gap_plugin/`, runnable via `scripts/gap_scan.py` |
| Real LLM integration | Implemented for `anthropic`/`minimax`/`deepseek` (all Anthropic-Messages-compatible, one SDK, see `gap_plugin/llm.py`) — needs the matching `*_API_KEY` in `.env` or the environment |
| Jev integration | Implemented — TypeSafe System One (Noul primitive) via `TYPESAFE_API_KEY`; escalates to an LLM judge when Jev's own answer is near 50/50, see `gap_plugin/judges.py:jev_judge` |

## Run

```bash
# Generate GT from ai_saas worktrees
python3 scripts/derive_gt.py

# Evaluate judges against GT (heuristic + Jev mock always work; LLM judges need API key)
python3 scripts/eval_judge.py

# Run the actual Gap Plugin scan (heuristic judge needs no key; haiku/verdict need one)
python3 scripts/gap_scan.py
python3 scripts/gap_scan.py --judge haiku --provider minimax   # needs MINIMAX_API_KEY
python3 scripts/gap_scan.py --judge jev                        # needs TYPESAFE_API_KEY (+ ANTHROPIC_API_KEY for escalation)

# Run the gap_plugin test suite
python3 -m pytest tests/

# Audit CI gates
/harness-lite:ci-doctor
```
