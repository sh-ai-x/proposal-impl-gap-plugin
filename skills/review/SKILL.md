---
name: review
description: Run scripts/gap_scan.py, self-verify every disputed claim (status partial/missing/contradicted/unknown) by directly reading the actual files -- most "unknown" claims are heuristic-judge false negatives an agent can resolve on sight -- and only ask a human the ones that stay genuinely ambiguous after that check, quoting both the proposal's wording and what was found. Routes the answer (self-resolved or human-answered) to a proposal-doc fix, a follow-up implementation task, or (for a fully-rotted doc) a deletion. Claude Code and Codex CLI compatible.
---

# Gap Plugin: Review

Turns a `gap_scan.py` report into decisions. It does NOT ask a human
something the agent can just go check -- "does this file exist and match
the proposal" is a fact, not a judgment call, and the agent running this
skill already has Read access the direct-judge pipeline couldn't use
well. What it never does is *guess* on a genuine disagreement (proposal
says X, code does Y, and it's unclear which one should win) -- that one
gets asked, with both sides quoted.

## What it does

1. Runs (or reuses) a scan, gets a `RepoReport`.
2. For every claim whose `status` is `partial`, `missing`, `contradicted`,
   or `unknown`: reads the actual file(s) the claim is about and checks
   directly whether the proposal's wording holds. Most `missing_info`
   claims resolve right here -- the file exists and matches, or it's
   genuinely absent -- with no human involved.
3. Only asks a human the claims that are still ambiguous after that check
   (file exists but conflicts with the proposal in a way that could
   reasonably go either way, or the correct resolution is a product/scope
   call the code alone can't answer).
4. Appends one line per resolved claim (self-resolved or human-answered)
   to `data/scan/decisions.jsonl` (append-only; never overwritten).
5. After every claim in a doc is resolved, offers to delete the doc if
   >=80% of its claims ended up `missing`/`contradicted` (a doc that's
   mostly wrong is more likely stale than the implementation is behind).

## What it does not do

- Does NOT ask a human to verify something the agent can check itself by
  reading the file. A "does X exist" question the human would have to go
  open the same file to answer is a wasted round-trip, not a judgment call.
- Does NOT guess on a real disagreement. Once the agent's own check is
  inconclusive -- the file exists but genuinely conflicts with the
  proposal, or resolving it requires knowing intent the code can't
  express -- it always asks, cites both sides, and never assumes.
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
python3 scripts/gap_scan.py --out-dir data/scan/reports
```

The pipeline runs direct judge (Jev with internal haiku escalation) per claim.
A free no-key scan is no longer supported -- the old `--judge heuristic`
path was removed because its lexical-overlap signal was an order of
magnitude worse than direct judgment on this proposal. The LLM cost is
paid only for the fraction of claims that escalate from Jev's uncertainty
band, which on this proposal was 2/17.

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

### Step 3 -- Self-check each claim (three tiers, cheapest first)

Most `missing_info`/`unknown` claims are the automated retrieval judge
failing to confirm something a closer look settles immediately. Don't
skip straight to asking a human -- climb this ladder and stop at the
first tier that resolves the claim:

1. **Read it yourself.** The bullet (Step 2) usually names the file(s).
   Open them (Read tool / Glob for a rename) and check directly: does the
   content do what the bullet describes? This alone resolves the large
   majority of disputed claims -- free, and often the file plainly exists
   and matches, or plainly doesn't exist at all. If you reach this step
   the direct-judge pipeline already reached the same conclusion for most
   claims; the ones that land here are the cases Jev returned uncertain
   (`noul` in the 0.3-0.7 band) and either accepted or rejected with
   evidence the human should sanity-check.
2. **Re-run Jev on the file you just read** if you want a second calibrated
   opinion on the same evidence: `gap_plugin.judges.jev_judge(section,
   [Candidate(file_path=<path>, snippet=<content>, score=1.0, source="bm25")],
   after_files)`. Needs `JEV_API_KEY`; if it's not set, skip this tier
   entirely and go straight to Step 4. `jev_judge` already escalates
   internally to `haiku_judge` when Jev's own answer is near a coin flip,
   so this one call may itself make two -- that's expected.
3. **Still unresolved?** That's a real disagreement, not a detection gap
   -- take it to Step 4.

Resolving at tier 1 or 2 means: log the decision now (Step 6,
`implementation-right` if the file matches, `proposal-right` if it's
genuinely missing/wrong) and move to the next claim. Do not ask the human
something tiers 1-2 already settled -- that's the mistake this skill
exists to avoid (see "What it does not do").

### Step 4 -- Ask, per still-unresolved claim

Only claims that survived Step 3's three tiers land here. Present,
together:
- The quoted proposal bullet (Step 2).
- What Step 3 actually found -- the file content read, and Jev/haiku's
  reasoning if that tier ran. Never present the original automated
  judge's `reasoning` alone; it's stale the moment Step 3 looked further.
- Three options: **implementation is right** (the proposal is stale),
  **proposal is right** (the implementation is missing or wrong), **skip**.

**Claude Code**: use the `AskUserQuestion` tool, one call per claim, header
naming the doc, options exactly the three above (skip is always an
explicit option, never the default when the tool times out or errors --
stop and surface the error instead).

**Codex CLI**: no structured multi-choice tool exists here -- ask in plain
text, spelling out the same three options, and wait for the next user
message. Do not proceed to Step 5 on a guessed or inferred answer; if the
reply is ambiguous, ask again naming exactly the three options.

### Step 5 -- Act on the answer

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
- **skip**: do nothing. Still log it (Step 6) so a later run doesn't
  re-ask silently -- the human sees it was skipped, not missed.

### Step 6 -- Log the decision

Append one JSON line to `data/scan/decisions.jsonl` (create the file and
`data/scan/` if needed; never truncate or rewrite existing lines) for
every resolved claim -- self-resolved at Step 3 or human-answered at
Step 5:

```json
{"doc_path": "...", "section_id": "...", "status": "...", "decision": "implementation-right|proposal-right|skip", "resolved_by": "self-check|jev|haiku|human", "resolved_at": "<ISO 8601 UTC>"}
```

`resolved_by` records which tier actually settled it -- keep this
honest; it's how a later audit tells a real human decision from an
agent's own read.

### Step 7 -- Doc-level rot check

After all of one doc's claims are resolved, compute:
`(missing + contradicted) / total_claims_in_doc` from the report's
`status_counts`. If >=0.8, tell the human this doc looks mostly stale and
ask (plain yes/no, same per-host mechanism as Step 4) whether to delete
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
  `act_spawn`, `act_delete` nodes). Diagram is on the legacy design;
  will be regenerated to match the direct-judge pipeline.
- `gap_plugin/report.py`, `gap_plugin/types.py` -- the actual `RepoReport`
  shape this skill reads.
