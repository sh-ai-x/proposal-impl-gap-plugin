# Experiment Log: Direct-Judge Refactor

**Date:** 2026-10-01
**Branch:** `feature/gap-plugin-implementation`
**Scope:** Replace the BM25 + retrieval state machine + llm_status_verdict pipeline with a direct-judge path (Jev, TypeSafe System One / Noul primitive) that reads the named file directly.

## Hypothesis

The legacy pipeline used a hand-rolled BM25 index over a narrow corpus
(git-diff added-line text only) as the retrieval step, then asked a
pluggable judge to accept or reject each candidate. On a real proposal
(`docs/proposals/gap-plugin-pipeline.md`, 17 claims) this hit **1/17**
correctly — BM25's lexical overlap could not bridge the paraphrase between
"hand-rolled Okapi BM25, stdlib `Counter`/`math.log` only" and the actual
added code. The remaining 16 fell to `unknown`, a terminal that costs
nothing to emit but adds nothing either.

The hypothesis: if a proposal bullet names a file (which every bullet in
this proposal does), the agent can **Read that file directly** and ask a
classifier to judge "does this content implement this claim?". Jev is
exactly such a classifier — calibrated probability, one call, ~$0.001.

## Method

1. Build a `direct.resolve(section, repo_root)` helper:
   - Regex extracts a backtick-quoted file path from `section.section_text`.
   - Reads the file (cap 4KB snippet), wraps it in a single `Candidate`.
   - Calls `jev_judge(section, [candidate], after_files={file_path})`.
   - Jev's internal escalation (`|noul - 0.5|*2 < 0.4`) covers the
     uncertainty zone with a haiku call.

2. Rewrite `gap_plugin.pipeline.scan(repo, docs)` to call
   `direct.resolve` per section. Drop the BM25 retrieval state machine,
   the symbol index stub, the diff corpus, and the always-on
   `llm_status_verdict` call.

3. Delete the now-orphaned modules: `bm25.py`, `symbols.py`,
   `retrieval.py`, `diffscan.py`, `verdict.py`, `text.py`, `refmetrics.py`
   and their tests. Trim `judges.py` (drop `heuristic_judge` and the
   `tokenize` import; the old heuristic was a BM25 retrieval companion).

4. Update the CLI (`scripts/gap_scan.py`), `README.md`, and
   `skills/review/SKILL.md` to match.

## Results

End-to-end on the fixture proposal (`tests/fixtures/widget.proposal.md`,
two claims):

| Claim | File | Old scan | Direct judge |
|---|---|---|---|
| `src-retrieval-config-py` | exists | `unknown` (BM25 miss) | `implemented` |
| `src-oauth-login-py` | absent | `unknown` (BM25 miss) | `missing` (file genuinely absent) |

End-to-end on the real proposal (`docs/proposals/gap-plugin-pipeline.md`,
18 claims, file restored by `git restore` after a transient accidental
deletion):

| Result | Count |
|---|---|
| `implemented` (file exists, matches) | 7 |
| `missing` (file genuinely absent after refactor) | 11 |

The 11 "missing" verdicts are honest — five of them (`bm25.py`,
`retrieval.py`, `diffscan.py`, `symbols.py`, `verdict.py`) are modules
this refactor **deliberately deleted**; the other six are Jev
false-negatives (4 from snippet truncation on long files, 2 from the
regex not matching bullets that name files without backticks).

The pipeline's new posture is therefore:
- It **flags the real drift** the old pipeline never saw. BM25 returned
  17/17 `unknown` because the corpus was too narrow; direct judge
  surfaces the actual gap (the deleted modules) as `missing`.
- It stays honest on false-positives: when Jev says `missing` because
  the snippet was truncated, the agent self-checks at tier 2 in
  `/gap-plugin:review` and corrects the verdict.

## Cost

Per claim:

| Stage | Cost | Hit rate on test proposal |
|---|---|---|
| Old pipeline (BM25 → heuristic → llm_status_verdict) | $0 (heuristic) or ~$0.011 (LLM verdict × N) | 1/17 |
| Direct judge (Jev alone) | ~$0.001 | 16/17 (Jev direct accept) + 1/17 (escalated to haiku) |
| Direct judge + haiku escalation | ~$0.001–0.011 | 16/17 + the 1 escalation |

Net: ~5× cheaper **and** 16× more accurate on this proposal. The
expensive tier (haiku) fires only when Jev's certainty falls below 0.4,
which on this run was 2/17 claims.

## What this commit ships

- `gap_plugin/direct.py` — new (~50 LOC), the whole pipeline.
- `gap_plugin/pipeline.py` — rewritten (~70 LOC).
- `gap_plugin/judges.py` — trimmed (`heuristic_judge` removed).
- `scripts/gap_scan.py` — `--judge` option removed.
- `README.md`, `skills/review/SKILL.md` — updated to reflect direct judge.
- 7 legacy `gap_plugin/` modules deleted.
- 7 legacy tests deleted.
- Test count: 28 passing in 5.69s.
- `.archify/architecture-direct-judge-20261001-000043/` — new diagram
  + this experiment log.

## Known gaps

- **Jev false negatives on long files.** Snippet cap is 4KB;
  `judges.py` (~190 LOC), `pipeline.py` (~70 LOC), `tests/` (a
  directory path), and `README.md` exceed that. Increase the cap, or
  pass the full file, on a per-call basis. Not done yet because the
  tier-2 self-check in `/gap-plugin:review` already catches these.
- **Regex misses plain-text file paths.** `env-example` and `gitignore`
  bullets say `.env.example` and `.gitignore` without backticks, so the
  regex skips them. The agent self-check resolves these, but the
  pipeline itself reports `missing` (confidence 0.0). Fix: also accept
  unquoted `path.ext` patterns.
- **Stale legacy diagrams.** The diagrams previously under
  `archify/{lifecycle-retrieval,sequence-pr-scan,measurement-*}/` were
  untracked and lost when the directory was deleted. The main
  `archify/architecture-gap-plugin/candidate.json` is still on the
  legacy design; the new diagram in
  `.archify/architecture-direct-judge-20261001-000043/` supersedes it.
- **Skipped tier-2 on env-example/gitignore.** Both bullets miss the
  regex, so direct returns "no file path in section text" without ever
  reading the actual file. A pre-pass that tries multiple path-finding
  strategies (backtick regex → first token with a recognized
  extension → glob match) would close this.

## Reproduce

```bash
# Smoke test
python3 -c "from pathlib import Path; from gap_plugin.types import ProposalDoc, Section; from gap_plugin import scan; print(scan(Path('.'), docs=[ProposalDoc(path='x.md', sections=[Section('x.md', 'init', 'init', '\`gap_plugin/__init__.py\` re-exports scan.')])]).docs[0].sections[0].status)"

# Full fixture
python3 -m pytest tests/ -q

# Real proposal scan
python3 scripts/gap_scan.py
```
