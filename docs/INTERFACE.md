# Interface — human-facing surfaces

Job Search OS has no web frontend and no graphical application. The product's human
interface is three things: a **conversational chat** (Claude Code), a **CLI/headless
scheduled run**, and **Markdown artifacts** (the digest, the home view). This document
maps those surfaces.

Surfaces covered here:
- The front door and home dashboard (`/job-search`)
- Conversational configuration (how users change anything)
- The preferences interview (`/job-preference-interview`)
- The digest — the primary output the user reads
- Error surfacing as part of the UX
- The CLI/headless run surface

Slash commands in this doc use the **short skill names** as shorthand. The typed form depends on
the install: plugin installs (the usual case) are namespaced — `/job-search-os:job-search` — because
plugin skills are only invocable as `/plugin-name:skill-name`; the bare `/job-search` form exists
only for loose-skill installs into `~/.claude/skills/`. See README → Install.

---

## Conversational configuration

Users change **everything** — search queries, run frequency, preferences, pipeline
status — by chatting. Skills read `config.yaml` or the relevant file, apply a minimal
edit that preserves comments and structure, and write it back. Hand-editing files is an
escape hatch: it works, but skills never require it or guide users toward it by default.

For the exact config recipes (how to add a query, change frequency, update the brief),
see [`../shared/references/internals.md`](../shared/references/internals.md).

For the product philosophy behind this (prose-over-knobs, conversational-first),
see [`design-docs/core-beliefs.md`](design-docs/core-beliefs.md).

---

## The front door and home view

`/job-search` is the entry point for all user interactions. On first run it routes to
onboarding (see [`product-specs/new-user-onboarding.md`](product-specs/new-user-onboarding.md));
for a returning user it routes to the home view described in
[`../skills/job-search/references/home.md`](../skills/job-search/references/home.md).

The home view is a compact, glanceable dashboard — not a log dump. A returning user
sees at a glance:

- **Workspace and brief age** — which workspace is active, and how old the preferences
  brief is (a stale brief triggers a gentle refresh nudge).
- **Schedule status** — whether a scheduled run is installed, its mechanism, and
  frequency.
- **Last-run health** — the health state from the most recent `runs/<id>.json`, or
  the latest digest's Run health line as a fallback.
- **Latest digest summary** — the date and the counts line from the newest digest.
- **Pipeline counts** — totals grouped by job status (the status vocabulary is owned by
  [`conventions.md`](../shared/references/conventions.md)) and how many need a human check.
- **Quick actions** — conversational prompts: run a search now, add or edit a query,
  change frequency, update preferences, toggle the schedule, show the latest digest.

All quick actions are conversational: the user types a sentence; the skill applies it.
The skill that owns this surface is [`../skills/job-search/SKILL.md`](../skills/job-search/SKILL.md).

---

## The interview — building and refining the brief

Building or updating the Job Preferences Brief is an interactive, one-question-at-a-time
conversation run by the `job-preference-interview` skill. The skill asks about role,
industry, company, compensation, location, work-life balance, growth, team, tech stack,
and hard constraints — adapting as the user answers, never dumping a checklist.

At the end, the brief is written to `preferences.md` in the workspace in five sections
(Summary, Must-haves/dealbreakers, Strong preferences, Nice-to-haves, Red flags).
Because this skill is interactive, it is never invoked in a scheduled headless run.

Full spec: [`../skills/job-preference-interview/SKILL.md`](../skills/job-preference-interview/SKILL.md).

---

## The digest — primary output

Each run writes a Markdown digest to `reports/<date>-digest.md`. The digest is the main
artifact the user reads: it groups postings by match strength, states the run-health,
and includes a counts line. Footnotes cover stale detail links, partial failures, and a
brief-age nudge when applicable.

The **exact digest format** (section layout, counts line shape, run-health vocabulary,
footnote conventions) is owned by
[`../shared/references/conventions.md`](../shared/references/conventions.md) — refer
there; it is not reproduced here.

For how the digest is produced (the search loop, dedup, evaluation, detail reads,
persist step), see [`../skills/job-search-run/SKILL.md`](../skills/job-search-run/SKILL.md).

---

## Error surfacing as UX

When a scheduled run is blocked, the failure is surfaced through three channels — not
through the process exit code (a headless `claude -p` run returns 0 even when blocked):

1. **The blocked digest** — written to `reports/<date>-digest.md` with the named error
   as its body, replacing the normal match listing.
2. **The home view** — on the user's next `/job-search`, the home view reads the newest
   `runs/<id>.json` and names the blocking error with its cause and fix.
3. **A desktop notification** — fired when the relevant notify flag is set in `config.yaml`
   (see [`../shared/references/conventions.md`](../shared/references/conventions.md) for
   the config schema).

Every failure is named (e.g. `E-NO-AUTH`, `E-QUOTA`, `E-SERVICE-DOWN`) with a
cause-and-fix message the user can act on. There are no silent failures.

Full error catalog with exact cause+fix wording:
[`../shared/references/errors.md`](../shared/references/errors.md).

---

## CLI / headless surface

The recurring run is Claude Code's native `/loop` — `/loop <interval> /job-search-os:job-search-run`
(plugin installs; loose skills drop the prefix) re-runs the search inside an open Claude
session (the one-off form is the same target without `/loop`). Users set this up
conversationally through the `/job-search` home view; nothing is installed on their
machine (no cron, no launchd).

`osctl.py` and `state.py` are deterministic internal CLIs that skills call to read and
write OS state (workspace discovery, registry, job database, schedule markers). They are
not user-facing; users never interact with them directly.

For the full CLI surface, internal scripts, and how the scheduling mechanisms work, see
[`../ARCHITECTURE.md`](../ARCHITECTURE.md).
