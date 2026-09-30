---
title: "Gap Plugin: proposal-vs-implementation drift detection pipeline"
status: draft
date: 2026-09-30
---

This proposal is retroactive: the pipeline it describes was built and committed
during the session that produced this document, on branch
`feature/gap-plugin-implementation` (6 commits, unpushed, unmerged). It is
written for review before merge, not after acceptance — the Before/After below
are honest descriptions of the repository state on either side of that branch,
not a plan. The dogfooding is also real: this repo's job is to check proposal
documents against the diffs that implement them, so this document is a
candidate input to the very tool it proposes.

## Before

The repository contained a complete design and a complete *unrelated* eval
harness, with nothing joining them.

- **Design, no runtime.** `archify/architecture-gap-plugin/candidate.json`,
  `archify/lifecycle-retrieval/candidate.json`, and
  `archify/sequence-pr-scan/candidate.json` existed as rendered diagrams with
  JSON as the source of truth. They specify a PR-time scan: discover proposal
  docs, retrieve evidence from the diff, judge each section, aggregate. No
  module in the repository implemented any of it.
- **An eval harness that is not the pipeline.** `scripts/derive_gt.py` derives
  ground truth from git history; `scripts/eval_judge.py` runs A/B judge
  comparisons against that ground truth. Neither performs a PR-time scan:
  `eval_judge.py`'s judges consume git-diff-derived GT rows directly, never
  BM25-retrieved section evidence. It answers "which judge is more accurate on
  known rows", not "does this PR implement its proposal".
- **No real LLM integration anywhere.** `scripts/eval_judge.py`'s `predict_llm`
  (lines ~95-136) silently falls back to a mock when `ANTHROPIC_API_KEY` is
  absent. A run with no key returns numbers that look like judgments and are
  not. There was no call boundary in the repo that failed loudly on a missing
  key.
- **Consequence.** There was no way — automated or scripted — to take a
  proposal document and a changed-file list and get back a per-section verdict.
  The only available answer was a human reading both.

## After

A new `gap_plugin/` package implements the three diagrams, plus a CLI. Every
file below is new unless marked.

**New package `gap_plugin/` (11 modules):**

- `gap_plugin/__init__.py` — package surface, re-exports `scan`.
- `gap_plugin/types.py` — shared dataclasses. `ACStatus`/`STATUSES` taxonomy
  copied verbatim from `scripts/eval_judge.py`'s
  `STATUSES = ["implemented","partial","missing","added","contradicted","unknown"]`,
  so verdicts stay comparable with the existing eval harness.
- `gap_plugin/errors.py` — `MissingAPIKeyError`.
- `gap_plugin/discovery.py` — `discover_docs()`: globs `docs/proposals/**/*.md`
  and `**/*.proposal.md`, strips YAML frontmatter, splits into headed sections.
  Excludes `tests/`, `test/`, `node_modules/`, `venv/`, `.venv/`.
- `gap_plugin/diffscan.py` — `parse_after_files()` (`git diff --name-only`) and
  `diff_bullets()` (added-line text per changed file; this is the BM25 corpus).
- `gap_plugin/bm25.py` — hand-rolled Okapi BM25, stdlib `Counter`/`math.log`
  only.
- `gap_plugin/symbols.py` — symbol/tree-sitter index stub; `symbol_candidates()`
  returns `[]`, wired into the retrieval candidate set (the diagram's
  `sym→Question` edge).
- `gap_plugin/retrieval.py` — the bounded-retry state machine from
  `archify/lifecycle-retrieval`: enter → Question (BM25 top-`k=10` + symbol
  candidates) → Good?(judge) → `answer` (accepted) or Rewrite (camelCase /
  snake_case query expansion) → retry-limit gate (`retry_limit=2`, so at most 3
  attempts per section, matching the diagram's own card annotation) → back to
  Question or `missing_info`.
- `gap_plugin/judges.py` — `Judge` protocol
  (`Callable[[Section, list[Candidate], set[str]], JudgeVerdict]`);
  `heuristic_judge` (default, no AI: token overlap plus an "After files"
  intersection bonus, `CONFIDENCE_THRESHOLD=0.7`), `haiku_judge` (real Claude
  call), `jev_judge` (raises `NotImplementedError`).
- `gap_plugin/llm.py` — shared Claude-Messages-API call boundary; providers
  `anthropic`, `minimax`, `deepseek` selected by `base_url`, the same
  convention `.github/workflows/hl-review.yml` already uses. Loads `.env` via
  `python-dotenv` at import time, no-op if absent.
- `gap_plugin/verdict.py` — `llm_status_verdict()`: Claude call producing an
  `ACStatus` with structured JSON output; raises `MissingAPIKeyError` when the
  relevant key is absent.
- `gap_plugin/report.py` — `build_doc_report` / `build_repo_report`
  (`repo_score = 1 - mean(gap_weight)`, with `missing`/`contradicted` = 1.0,
  `partial`/`unknown` = 0.5, `implemented`/`added` = 0.0) and `emit_report`
  (timestamped Markdown + JSON).
- `gap_plugin/pipeline.py` — `scan(files, repo, ...)`, a plain for-loop
  orchestrator per `archify/sequence-pr-scan` (deliberately not a state machine
  at the top level; only retrieval is). `files` lets CI hand in the PR's
  changed-file list directly, matching the sequence diagram's `scan(files, repo)`
  call shape and bypassing the internal git shell-out. Skips the git-diff step
  entirely when zero proposal docs are discovered.

**New CLI and supporting files:**

- `scripts/gap_scan.py` — thin argparse CLI over `gap_plugin.scan()`, in the
  style of the existing `scripts/derive_gt.py` / `scripts/eval_judge.py`.
- `tests/` — 42 unit and integration tests, including one synthetic end-to-end
  fixture (a proposal doc plus a real git repo with an added implementation
  file) and `tests/fixtures/widget.proposal.md`.
- `.env.example` — documents the three provider key names.
- `.gitignore` — adds `.env` / `.env.*`.
- `README.md` — records the Jev integration as Pending.

**Explicitly outside the diff:** `scripts/eval_judge.py` and
`scripts/derive_gt.py` are untouched. Both were re-run after every change in
this session (`derive_gt.py` exit 0; `eval_judge.py --judges heuristic` renders
its report normally), confirming no accidental coupling between the new package
and the existing harness.

Two design corrections were made mid-build and are worth recording because they
changed the wiring, not just the code:

1. The architecture diagram labels its `bm25` node "section_text corpus", but
   tracing the wired edges (`after_parse →"After bullets"→ bm25`;
   `bm25 →"k=10"→ Question`; `scan →"section_text"→ Question` directly) shows
   the corpus must be git-diff evidence — a proposal section *queries* the
   evidence index, it does not query other proposal sections. Fixed before it
   reached `retrieval.py`.
2. `discovery.py`'s directory exclusions were added after live-running the tool
   against this repository, which swept up `tests/fixtures/widget.proposal.md`
   as a real proposal. Unit tests had not caught it.

## Business impact

- **Who is affected.** The maintainer of this repository in their reviewer
  role, and the `hl-*` CI gates that run on PRs here — specifically, whoever
  has to decide whether a PR claiming to implement `docs/proposals/<x>.md`
  actually does. Today that is one person reading two artifacts side by side.
- **What concretely changes for them.** Per-section drift becomes a machine
  output instead of a reading task. Each proposal section resolves to one of
  the six `STATUSES` values; `missing`, `contradicted`, and `unknown` are the
  actionable ones. `build_repo_report` folds them into
  `repo_score = 1 - mean(gap_weight)` (`missing`/`contradicted` = 1.0,
  `partial`/`unknown` = 0.5, `implemented`/`added` = 0.0), which is a single
  number a CI gate can threshold. Before: zero automated signal — the only
  detection mechanism was a human noticing. After: `python3
  scripts/gap_scan.py` returns a scored Markdown + JSON report; the live run
  against this repo produced `repo_score: 1.000`, `docs scanned: 0`, exit 0 —
  correct, since no real `docs/proposals/*.md` existed until this file. The
  `missing_info` terminal in `retrieval.py` is the other half of the mechanism:
  a section whose evidence cannot be retrieved within 3 attempts reports
  `unknown` rather than silently scoring as implemented, so the failure mode is
  a flagged section, not a false pass.
- **Cost of not doing this.** Drift between a proposal and its implementation
  stays undetected until someone manually audits — which is exactly the gap
  this repository exists to close, per its own one-line description. Without
  the pipeline, the repo has ground truth (`derive_gt.py`) and judge evaluation
  (`eval_judge.py`) but no consumer for either: it can measure how good a judge
  *would* be without ever running one on a real PR. Every proposal merged in
  the meantime is unverified, and the unverified ones accumulate — the audit
  cost grows with the backlog, while the evidence needed to do the audit (the
  diff, fresh in reviewers' heads) decays.

## Pros

- **No new dependencies.** BM25 and the retry state machine are hand-rolled on
  stdlib (`Counter`, `math.log`) because neither `rank_bm25` nor `langgraph`
  was installed, and the alternative — adding two dependencies for a scoring
  formula and a bounded loop — was rejected as a recorded decision in this
  session. The three LLM providers share one already-installed SDK
  (`anthropic`), because MiniMax and DeepSeek expose Anthropic-Messages-
  compatible endpoints at different `base_url`s, the same trick
  `.github/workflows/hl-review.yml` already uses. `python-dotenv` was likewise
  already installed.
- **Default path needs no API key.** `heuristic_judge` is the default judge and
  makes no network call, so `scripts/gap_scan.py` runs in CI without a secret.
  The LLM path is opt-in.
- **Fails loudly where the existing harness fails quietly.**
  `gap_plugin/verdict.py` raises the typed `MissingAPIKeyError` on a missing
  key — a deliberate divergence from `scripts/eval_judge.py`'s `predict_llm`
  (lines ~95-136), which silently mocks. A mocked verdict that looks real is
  the worse failure for a tool whose output is a pass/fail signal.
- **Verified end to end, not just in units.** Final test run: `42 passed in
  12.14s`, exit 0. The suite includes a synthetic fixture with a real git repo,
  exercising both the `answer`→verdict path and the `missing_info`→`unknown`
  path, so the state machine's terminal branches are both covered.
- **The existing eval harness is provably unaffected.** `derive_gt.py` and
  `eval_judge.py` were re-run after every change and still behave as before.
- **Reviewed on two axes before this proposal.** A Standards-conformance and a
  Spec-fidelity-vs-diagrams review ran in parallel; findings (dead `symbols.py`
  wiring, an `after_files` name collision, duplicated Claude-call logic, a
  missing type annotation) were fixed in commit `f5472e4`, with the duplicated
  call logic extracted into `gap_plugin/llm.py`.

## Cons

- **`jev_judge` is unimplemented.** It raises `NotImplementedError`. Mitigation:
  it raises rather than returning a plausible fake, the `Judge` protocol is
  already exercised by two working implementations (`heuristic_judge`,
  `haiku_judge`), and the README already lists Jev/typesafe-ai as Pending — so
  the stub matches the documented state rather than contradicting it.
- **`symbols.py` returns `[]`.** Retrieval currently sees BM25 candidates only.
  Mitigation: the `sym→Question` edge is wired and covered, so replacing the
  function body is the whole change; and BM25 over added-line text is the
  primary evidence channel in the diagram, with symbols as an augmentation.
- **`heuristic_judge`'s `CONFIDENCE_THRESHOLD=0.7` is an untuned constant.**
  Token overlap plus an "After files" intersection bonus is a naive relevance
  signal. Mitigation: the repo already owns the tuning apparatus —
  `derive_gt.py` produces ground truth and `eval_judge.py` does A/B judge
  comparison against it, and the taxonomy is shared verbatim, so the threshold
  can be calibrated with tooling that already exists and was left intact.
- **BM25 is hand-rolled, so its correctness is ours.** Mitigation: Okapi BM25 is
  a fixed published formula with no tuning surface beyond `k1`/`b`, it is under
  unit test, and the alternative was a dependency for roughly the same amount of
  code.
- **Two bugs reached live-running that unit tests missed** (the
  `tests/fixtures` false positive; the crash on a repo with no commits, now
  fixed by skipping the git-diff step when zero docs are discovered).
  Mitigation: both fixes shipped in `0ae11ed` with the live run as the check,
  and the end-to-end fixture now covers the full `scan()` path — but this is
  honest evidence that the unit suite alone was not sufficient.

## Limitations

- **Jev / typesafe-ai integration is out of scope by design.** The `Judge`
  protocol exists precisely so a third judge is an addition, not a
  modification. Implementing it now would mean committing to an integration the
  repo's own README declares Pending.
- **LangSmith observability is excluded entirely — no hook, not even a no-op.**
  It is optional and env-var-gated in the architecture diagram, and nothing on
  the core path calls it. A hook with no caller is scaffolding for a later
  session; the later session can write it against real requirements.
- **This is a single-repository, local-git tool.** `diffscan.py` shells out to
  `git diff` in a working tree. It does not talk to a forge API, does not
  handle cross-repository proposals, and `scan(files, repo, ...)` takes the
  changed-file list as a parameter precisely so CI supplies it — integration
  with a PR event is a separate, deliberate boundary.
- **Retrieval is capped at 3 attempts per section** (`retry_limit=2`). This is
  the diagram's specified bound, not a placeholder. Sections whose evidence
  needs more than two query rewrites terminate at `missing_info` and report
  `unknown` — by design, an honest non-answer rather than an unbounded search.

## Decision

Pending review. Branch `feature/gap-plugin-implementation` holds 6 commits
(`a64ef56` initial pipeline, `f5472e4` review fixes, `6b140cf` provider
support, `bae43c9` `.env` loading, `0ae11ed` CLI and live-run bug fixes) and is
neither pushed nor merged. Merge is the decision being asked for.
