---
name: review
description: Run scripts/gap_scan.py, then walk a human through every disputed proposal-vs-implementation claim (status partial/missing/contradicted/unknown) with the proposal's own wording quoted alongside the judge's reasoning, and route the human's answer to a proposal-doc fix, a follow-up implementation task, or (for a fully-rotted doc) a deletion. Use after a scan has flagged claims and a human is available to adjudicate -- never to auto-resolve a disagreement. Claude Code and Codex CLI compatible.
---

# Gap Plugin: Review

Turns a `gap_scan.py` report into decisions. This skill never decides who's
right (the proposal or the implementation) -- it always asks, cites both
sides, and records the human's answer. See `docs/proposals/gap-plugin-pipeline.md`
for why: a text-diffing pipeline cannot know which side was updated more
recently or more deliberately, and a report with an unread reasoning string
is not a decision.

## What it does

1. Runs (or reuses) a scan, gets a `RepoReport`.
2. For every claim whose `status` is `partial`, `missing`, `contradicted`, or
   `unknown`: quotes the proposal's own bullet next to the judge's
   `reasoning`, asks the human which side is right, and acts on the answer.
3. Appends one line per resolved claim to `data/scan/decisions.jsonl`
   (append-only; never overwritten, never read back to skip a claim unless
   the human asked to skip it last time).
4. After every claim in a doc is resolved, offers to delete the doc if
   >=80% of its claims ended up `missing`/`contradicted` (a doc that's
   mostly wrong is more likely stale than the implementation is behind).

## What it does not do

- Does NOT decide `implementation-is-right` or `proposal-is-right` on its
  own. Every disputed claim gets a human answer, every time.
- Does NOT touch claims already `implemented`/`added` -- those aren't
  disputes.
- Does NOT invent evidence. If the proposal doc's wording for a claim
  can't be found (renamed heading, edited since the scan ran), say so and
  ask instead of guessing.

## Instructions

### Step 1 -- Get a report

If the caller already has a report path (JSON under `data/scan/reports/`),
use it. Otherwise run a scan:

```bash
python3 scripts/gap_scan.py --judge heuristic --out-dir data/scan/reports
```

`heuristic` is the default here on purpose: this skill already puts a human
(and, running inside an agent session, an LLM) in the loop for every
disputed claim, so paying for `haiku`/a hosted provider on top buys little.
Pass `--judge haiku --provider <name>` through if the caller asked for it.

Load the newest `data/scan/reports/*.json`.

### Step 2 -- Build the work list

For each doc, for each section in `status_counts` where status is
`partial`, `missing`, `contradicted`, or `unknown`: that's one claim to
review. Skip `implemented`/`added` entirely.

For each claim, read the proposal doc at `doc_path` yourself (Read tool)
and find the `## After` bullet whose slug matches `section_id` (same rule
`gap_plugin/discovery.py` uses: lowercase, non-alphanumeric runs become
`-`). Quote that bullet verbatim -- this is the proposal side of the
evidence. If no bullet matches (doc edited since the scan ran), say so to
the human instead of fabricating one.

### Step 3 -- Ask, per claim

Present, together:
- The quoted proposal bullet (Step 2).
- The judge's `reasoning`, `status`, and `confidence` from the report --
  this is the implementation side of the evidence, already computed.
- Three options: **implementation is right** (the proposal is stale),
  **proposal is right** (the implementation is missing or wrong), **skip**.

**Claude Code**: use the `AskUserQuestion` tool, one call per claim, header
naming the doc, options exactly the three above (skip is always an
explicit option, never the default when the tool times out or errors --
stop and surface the error instead).

**Codex CLI**: no structured multi-choice tool exists here -- ask in plain
text, spelling out the same three options, and wait for the next user
message. Do not proceed to Step 4 on a guessed or inferred answer; if the
reply is ambiguous, ask again naming exactly the three options.

### Step 4 -- Act on the answer

- **implementation is right**: open the proposal doc (Edit tool) and fix
  the stale bullet -- either correct its wording to match what's actually
  implemented, or remove it if it no longer applies. Show the human the
  diff before or as part of the edit; this is a doc change like any other,
  not a silent rewrite.
- **proposal is right**: hand off a concrete, scoped implementation task
  naming the file(s), the claim's exact wording, and the doc/section it
  came from.
  - **Claude Code**: spawn via the `Agent` tool (`general-purpose`
    subagent, not a fork -- this is new work, not continuing this
    conversation's context), one call per claim, self-contained prompt.
  - **Codex CLI**: explicitly delegate to a Codex subagent the same way,
    one per claim, in the same turn where possible.
- **skip**: do nothing. Still log it (Step 5) so a later run doesn't
  re-ask silently -- the human sees it was skipped, not missed.

### Step 5 -- Log the decision

Append one JSON line to `data/scan/decisions.jsonl` (create the file and
`data/scan/` if needed; never truncate or rewrite existing lines):

```json
{"doc_path": "...", "section_id": "...", "status": "...", "decision": "implementation-right|proposal-right|skip", "resolved_at": "<ISO 8601 UTC>"}
```

### Step 6 -- Doc-level rot check

After all of one doc's claims are resolved, compute:
`(missing + contradicted) / total_claims_in_doc` from the report's
`status_counts`. If >=0.8, tell the human this doc looks mostly stale and
ask (plain yes/no, same per-host mechanism as Step 3) whether to delete
it. On yes: `git rm <doc_path>` and a one-line commit-message-worthy
explanation citing the ratio. On no or no answer: leave it, move on.

## Known gap

The report JSON has no stored per-claim evidence excerpt yet (no
`claim_id`, no `proposal_excerpt`/`evidence_excerpt` fields --
`gap_plugin/types.py:SectionVerdict` only carries `reasoning`). Step 2's
live re-read of the proposal doc is how this skill gets the proposal-side
quote without that field existing. If `gap_plugin` later adds those
fields, Step 2 can read them directly instead of re-deriving the slug
match -- prefer the stored field when present, fall back to the live
re-read when absent, so this skill doesn't break on an older report.

## References

- `archify/architecture-gap-plugin/candidate.json` -- the "Human Review"
  region this skill implements (`ask`, `decisions_log`, `act_edit`,
  `act_spawn`, `act_delete` nodes).
- `docs/proposals/gap-plugin-pipeline.md` -- why the pipeline never
  auto-decides who's right.
- `gap_plugin/report.py`, `gap_plugin/types.py` -- the actual `RepoReport`
  shape this skill reads.
