# Interface — human-facing surfaces

Job Search has no web frontend and no graphical application. The product's human
interface is three things: a **conversational chat** (Claude Code), a **CLI/headless
scheduled run**, and **Markdown artifacts** (the digest, the home view). This document
maps those surfaces.

**TL;DR.** Six surfaces, each its own section — jump straight to the one you need:
- [The front door and home view](#the-front-door-and-home-view) (`/job-search`) — the home dashboard
- [Conversational configuration](#conversational-configuration) — how users change anything
- [The interview](#the-interview--building-and-refining-the-brief) (`/job-preference-interview`)
- [The digest](#the-digest--primary-output) — the primary output the user reads
- [Error surfacing as UX](#error-surfacing-as-ux) — how a blocked run reaches the user
- [The CLI / headless surface](#cli--headless-surface) — the scheduled run

Slash commands in this doc use the **short skill names** as shorthand. The typed form depends on
the install: plugin installs (the usual case) are namespaced — `/job-search:job-search` — because
plugin skills are only invocable as `/plugin-name:skill-name`; the bare `/job-search` form exists
only for loose-skill installs into `~/.claude/skills/`. See README → Install.

---

## Conversational configuration

Users change **everything** — search queries, run frequency, preferences, pipeline
status — by chatting. Skills read `config.yaml` or the relevant file, apply a minimal
edit that preserves comments and structure, and write it back. Hand-editing files is an
escape hatch: it works, but skills never require it or guide users toward it by default.

Review depth uses the same conversational surface. “Review up to 50 new postings this run” is a
one-off finite request; “review up to 50 every run” is saved; ambiguous “scan everything” defaults
to one run and says so. Enabling or increasing depth first shows the known calls and uncertain
additions, then asks for explicit confirmation before a metered run or config write. A confirmed
saved setting is durable consent for later headless runs; reductions and a return to normal first-
page coverage take effect immediately.

For the exact config recipes (how to add a query, change frequency, update the brief, or change
review depth) and the preview arithmetic,
see the `job-search-runbook` skill.

For the product judgment behind this — preferences as prose, configuration by conversation — see
[`PRODUCT_SENSE.md`](PRODUCT_SENSE.md#prose-over-knobs).

How skills speak — plain English, outcome first, no internal vocabulary, briefs and digests
rendered inline rather than described — is carried by each skill's own `SKILL.md`, and graded by
the maintainer's live behavior evals rather than pinned in a style reference.

---

## The front door and home view

`/job-search` is the entry point for all user interactions. On first run it routes to onboarding;
for a returning user it routes to the home view. Both flows are described in
[`../skills/job-search/SKILL.md`](../skills/job-search/SKILL.md).

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
  the `job-search-runbook` skill) and how many need a human check.
- **One-time deeper-coverage offer** — only after the latest local run provides the qualifying
  evidence, and never again after it is shown; the marker and eligibility rules are owned by
  the `job-search-runbook` skill.
- **Quick actions** — conversational prompts: run a search now, add or edit a query,
  change frequency or review depth, explain usage, update preferences, toggle the schedule,
  show the latest digest.

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
includes a counts line and a calls-first usage summary, and gives a one-line reason for every
shown match so the user can audit why it landed in its band. Any account-neutral dollar context
is labeled as a pay-as-you-go equivalent, not an actual charge. Footnotes cover stale detail
links, incomplete deeper coverage, partial failures, and a brief-age nudge when applicable.

The **exact digest format** (section layout, counts line shape, run-health vocabulary,
footnote conventions) is owned by
the `job-search-runbook` skill — refer
there; it is not reproduced here.

For how the digest is produced (the search loop, dedup, evaluation, detail reads,
persist step), see [`../skills/job-search-run/SKILL.md`](../skills/job-search-run/SKILL.md).

---

## Error surfacing as UX

A blocked run still reaches the user — it never relies on the process exit code (a headless
`claude -p` run returns 0 even when blocked). *How* it surfaces — every channel, and the
exit-code trap — is owned by
[`RELIABILITY.md`](RELIABILITY.md#4-run-health--blocked-surfacing--visible-without-the-exit-code);
from the interface's side, what the user meets is the blocked digest in place of the normal
match listing and the same blocked state named in the home view on their next `/job-search`.

Every failure is named internally and reaches the user as a plain, four-part cause · preserved
work · next step · exact fix — sentences a user can act on. There are no silent failures, and there
is no code token to leak, because there is no error-code catalogue: the run says what stopped it in
the words the user would use, at the step that hit it.

What a stopped run writes is the record and the digest: `close_state` (`complete` / `blocked` /
`interrupted`) and `run_health` (`healthy` / `degraded`) in `runs/<run_id>.json`, whose shape is
[`run-record.example.json`](../skills/job-search-run/templates/run-record.example.json), plus a digest whose
body is the cause and the fix. The close sequence is owned by
the `job-search-runbook` skill.

---

## CLI / headless surface

The scheduled pass is the headless `job-search-run` — the same search loop, run non-interactively
by a schedule (the one-off "run a search now" is the same target invoked by hand). Users set
scheduling up conversationally through the `/job-search` home view. The advocated default is an
**unattended machine schedule** — a `cron`/`launchd` entry, or the host's own scheduler — that
fires with no session open; the **in-session loop is the named fallback** when the host has no
unattended scheduler or the user declines the machine change. Either way the schedule is
consent-gated (the exact change is shown first and written only on an explicit yes) and is
recorded as running only after a **config-time canary** proves the real invocation works.

The OS state — the registry, the local jobs file, the schedule marker — is plain files the host
agent reads and writes natively, following the pinned procedures in the `job-search-runbook` and
`agent-data-reference` skills. None of
it is user-facing; users never interact with those files directly.

For the full surface and how the scheduling mechanisms and canary work, see
[`../ARCHITECTURE.md`](../ARCHITECTURE.md) and
the `job-search-runbook` skill (Scheduling setup).
