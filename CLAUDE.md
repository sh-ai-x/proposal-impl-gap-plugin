<!-- AUTO-GENERATED — DO NOT EDIT MANUALLY. Run `/harness-lite:bootstrap` to regenerate. -->

# CLAUDE.md / AGENTS.md — harness-lite pointer

> This project has the **harness-lite** plugin installed. Its skills
> (`bootstrap`, `build`, `review`, `ship`, `route`, `flow-*`,
> `ci-doctor`, `ci-setup`, `gate-select`, `gate-artifacts`, `proposal`,
> `babysit-pr`, `onboarding`) are available every session via
> `/harness-lite:<name>`, regardless of which project you're in — no
> local copy needed. Served on both `CLAUDE.md` (Claude Code) and
> `AGENTS.md` (Codex CLI, opencode, aider, etc.); on disk the two names
> point to the same file via a symlink — edit this one, both stay in
> sync.

## Iron laws (lite edition)

| # | Law |
|---|---|
| L1 | No prod code without verification artifact (test/contract/domain). |
| L2 | No fix without reproducing the bug first. |
| L3 | No completion claim without quoted exit code / test count / build log. |
| L4 | No deferred-work markers; no option list when not asked. |

## References (harness-lite plugin source — read on demand)

The plugin's rules and full skill reference live in its own repo, not
this project — there is no local `rules/` or `skills/` directory here
to read.

- **Iron laws (full text)** → https://github.com/sh-ai-x/harness-lite/blob/main/rules/iron-laws.md
- **Compatibility contract** → https://github.com/sh-ai-x/harness-lite/blob/main/rules/compat.md
- **Session hygiene** → https://github.com/sh-ai-x/harness-lite/blob/main/rules/session-hygiene.md
- **Rules index** → https://github.com/sh-ai-x/harness-lite/blob/main/rules/index.md
- **Skills index** → https://github.com/sh-ai-x/harness-lite/blob/main/skills/README.md

## This project's harness-lite state

- `.hl/hl-mode.json` — ponytail / mattpocock-defer mode for this project.
- `.hl/trace/sessions.log` — best-effort session trace.
- `.github/workflows/hl-*.yml` — the three CI gates, installed by
  `/harness-lite:bootstrap` (toggle with `/harness-lite:gate-select`).

<!-- END AUTO-GENERATED -->
