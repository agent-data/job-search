---
title: New-User Onboarding
status: current
verified: partial
last_reviewed: 2026-06-07
code_refs: [skills/job-search/SKILL.md, skills/job-search/references/onboarding.md, scripts/osctl.py]
---

# New-User Onboarding

## Goal and the magical moment

Within approximately five minutes of installing Job Search OS, a new user sees real, live job
postings judged against their own stated preferences — strong, moderate, or weak matches with
plain-language reasoning — without writing a single file by hand. That first digest, produced
seconds after the interview ends, is the **magical moment**: the system is no longer abstract; it
works, and it works on their actual search.

The five-minute **time-to-first-value (TTFV)** target matters because setup friction is the
primary drop-off point for developer tools. Every step in onboarding either directly builds toward
that moment or gates it safely; none is bureaucratic overhead.

## Trigger and routing

`/job-search` is the front door. On every invocation the skill calls `python3 "$OS" resolve` to
read the workspace state. When `resolve` returns `first_run: true` the skill routes to the
first-run playbook; when `first_run: false` it routes to the returning-user home. The routing
logic and both playbooks are owned by [`skills/job-search/SKILL.md`](../../skills/job-search/SKILL.md).

## The onboarding flow

The full playbook lives in
[`skills/job-search/references/onboarding.md`](../../skills/job-search/references/onboarding.md).
This section names each step and points to the owning reference; it does not restate mechanics.

### 1. Welcome

A one- or two-sentence opener that sets the user's expectation: prereqs, workspace, preferences,
first search, real matches — in a few minutes, nothing fails silently.

### 2. Preflight prerequisites

Two free checks before any workspace is created or any metered call is made.

- Is the `agent-data` CLI present on PATH?
- Is it authenticated (`agent-data whoami` reports `api_key_set: true`)?

Either failure halts immediately with a named error. Failure wording and fix instructions are
owned by [`shared/references/errors.md`](../../shared/references/errors.md) (`E-NO-AGENT-DATA`,
`E-NO-AUTH`). Nothing is set up before these pass.

### 3. Workspace creation or adoption

The skill calls `python3 "$OS" resolve` to discover the workspace path and first-run status. The
discovery order, never-clobber adoption rule, and `set-active` write are owned by
[`shared/references/internals.md`](../../shared/references/internals.md).

- **Adopt** an existing workspace: record it with `set-active`; additively create only missing
  subdirectories; never overwrite existing `config.yaml`, `preferences.md`, or `jobs.jsonl`.
- **Create fresh**: default path `~/.job-search/`; confirm with the user; scaffold directories
  and copy starter templates.

An adopted workspace that already has both `config.yaml` and `preferences.md` skips the interview
and jumps straight to the first live run.

### 4. Build the brief: interview or import

The system needs a Job Preferences Brief (`preferences.md`) to judge postings against. The user
chooses one path:

- **Interview** — invoke [`skills/job-preference-interview`](../../skills/job-preference-interview/SKILL.md),
  which asks one question at a time and writes a prose brief (Summary, Must-haves/dealbreakers,
  Strong preferences, Nice-to-haves, Red flags) to the workspace.
- **Import** — also handed to `job-preference-interview`, which validates, converts any numeric
  rubric to prose (this system is qualitative only), enriches thin sections, and writes
  `preferences.md`.

Either path ends with `preferences.md` present at the workspace path. If a run is attempted
without a usable brief, the error is `E-NO-PREFERENCES` (see
[`shared/references/errors.md`](../../shared/references/errors.md)).

### 5. Queries and frequency (conversational)

The user names a role and location; the skill writes a `queries[]` entry into `config.yaml` by
editing the file minimally (preserve comments and structure). The user picks a run frequency in
plain human terms — no credit math, no cost reasoning. Config schema and edit recipes are owned by
[`shared/references/internals.md`](../../shared/references/internals.md) and
[`shared/references/conventions.md`](../../shared/references/conventions.md).

### 6. First live search — the magical moment

The skill invokes `job-search-run` against the new workspace. It searches each enabled query,
deduplicates against the local jobs database, judges each new posting against the brief
(qualitatively: relevant or not, and if relevant weak/moderate/strong), reads full descriptions
for the promising ones, and writes a digest. The agent presents strong and moderate matches as a
discovery — "Here are N jobs matching your brief, found seconds ago."

Blocked-run handling: any failure surfaces a named error from
[`shared/references/errors.md`](../../shared/references/errors.md). The most likely at this step
are `E-QUOTA` (the only point where API limits surface, reactively) and `E-SERVICE-DOWN`.
Mechanics and the full run-result taxonomy are in
[`skills/job-search/references/onboarding.md`](../../skills/job-search/references/onboarding.md).

### 7. Schedule offer (consent-gated)

The skill offers to automate the search. Three mechanisms: OS cron (recommended), launchd (robust
macOS), or `/loop`. The user answers yes/no; on yes the skill performs the privileged write and
records it with `set-scheduled`. A copy-paste fallback block is always printed. The scheduling
protocol — consent guard, `set-sched-intent`, `set-scheduled`, and the verbatim fallback block —
is owned by [`shared/references/internals.md`](../../shared/references/internals.md).

## What the user sees / success criteria

At the end of onboarding all of the following are true:

- A **digest** exists at `<workspace>/reports/<date>-digest.md` with real, judged postings.
- A **persisted workspace** at `~/.job-search/` (or a user-chosen path) contains `config.yaml`,
  `preferences.md`, and `jobs.jsonl` — all created or adopted without hand-editing.
- An **optional schedule** is installed and recorded in the OS registry if the user consented.

On a **returning session**, `python3 "$OS" resolve` returns `first_run: false` because
`config.yaml` exists in the workspace, and the skill routes to the home view (latest digest,
pipeline, quick actions) instead of restarting onboarding.

## Edge cases

All failure paths surface a named `E-*` code. Wording and fixes are owned by
[`shared/references/errors.md`](../../shared/references/errors.md); they are not restated here.

- **Missing prerequisites** — `E-NO-AGENT-DATA` or `E-NO-AUTH`; onboarding halts before any
  workspace is touched.
- **No preferences yet** — `E-NO-PREFERENCES`; the first run halts and directs the user to
  `/job-preference-interview`.
- **Sparse market** — not a named error; zero search results prompt the agent to offer keyword
  broadening conversationally (see
  [`skills/job-search/references/onboarding.md`](../../skills/job-search/references/onboarding.md)).

## Related

- [`../design-docs/index.md`](../design-docs/index.md) — original design rationale and historical
  decision snapshots.
- [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) — system architecture and component map.
