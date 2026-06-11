---
title: New-User Onboarding
status: current
verified: partial
last_reviewed: 2026-06-11
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

The **job-search** skill is the front door (`/job-search-os:job-search` as a plugin — plugin skills
are only invocable namespaced; bare `/job-search` for loose-skill installs). On every invocation the skill calls `python3 "$OS" resolve` to
read the workspace state. When `resolve` returns `first_run: true` the skill routes to the
first-run playbook; when `first_run: false` it routes to the returning-user home. The routing
logic and both playbooks are owned by [`skills/job-search/SKILL.md`](../../skills/job-search/SKILL.md).

## The onboarding flow

The full playbook lives in
[`skills/job-search/references/onboarding.md`](../../skills/job-search/references/onboarding.md).
This section names each step and points to the owning reference; it does not restate mechanics.
Every ask follows the zero-context voice rules owned by
[`shared/references/voice.md`](../../shared/references/voice.md) — one short line of plain-English
context (what the thing is, why it's asked), then the question; internal vocabulary never reaches
the user.

### 1. Welcome

A one- or two-sentence opener that sets the user's expectation: prereqs, workspace, preferences,
first search, real matches — in a few minutes, nothing fails silently.

### 2. Preflight prerequisites

A free check before any workspace is created or any metered call is made: is `agent-data` present on
PATH (`command -v agent-data`) and authenticated (`agent-data whoami` reports `api_key_set: true`)?

The agent leads with *why* it's checking and never pre-claims a result it hasn't verified —
**say-then-run**: every command in this step is announced on screen before it runs; none runs silently.
If the check passes, the agent says so as a verified fact and continues. If `agent-data` is missing or
unauthenticated, **interactive onboarding remediates rather than stopping** — install first, then
connect. A missing CLI is installed immediately and without user input (`npm install -g agent-data`,
verified with `agent-data --version`) — the agent says why first (agent-data is a dependency of this
plugin; it pulls and reads live job postings). If permission settings block the install, that's a
one-line handoff, not an error: the agent gives the exact in-session command
(`! npm install -g agent-data`) and resumes once it lands. Then — and starting here when the CLI was
present but unauthenticated —
the agent walks the user through generating an API key (with explicit steps), authenticates
(`agent-data init --claude-code --api-key <KEY> --yes`), and verifies with `agent-data whoami` before
continuing. The API key is requested only at this connect step, never before the install. Steps stay in
sync with the canonical setup doc <https://agent-data.dev/setup/claude-code.md>. The internal codes for
this state (`E-NO-AGENT-DATA`, `E-NO-AUTH`, owned by
[`shared/references/errors.md`](../../shared/references/errors.md)) are never shown to the user. The
**headless runner** (`job-search-run`) can't prompt, so it still halts on these with a blocked digest.

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

### 5. Searches and frequency (derived from the brief)

The skill **derives** 2–3 searches from the brief it just built — it does not ask the user to name
keywords — and writes them as `queries[]` entries into `config.yaml` (editing minimally, preserving
comments and structure), then **acknowledges** what it saved and notes the searches are editable
anytime. The user picks a run frequency in plain human terms — no credit math, no cost reasoning.
Config schema and the derive/edit recipes are owned by
[`shared/references/internals.md`](../../shared/references/internals.md) and
[`shared/references/conventions.md`](../../shared/references/conventions.md).

### 6. First live search — the magical moment

The skill invokes `job-search-run` against the new workspace (the run loop itself — search,
dedup, judge, detail-read, digest — is owned by
[`skills/job-search/references/onboarding.md`](../../skills/job-search/references/onboarding.md)).
What the user sees at this step is the payoff: the agent presents strong and moderate matches as
a discovery — "Here are N jobs matching your brief, found seconds ago."

If the run is blocked instead, the user meets a named error in the digest and the home view; how
that surfacing works is owned by
[`../RELIABILITY.md`](../RELIABILITY.md#4-run-health--blocked-surfacing--visible-without-the-exit-code).
Onboarding-specific note: the likeliest blocks here are `E-QUOTA` (the only point where API
limits surface, reactively) and `E-SERVICE-DOWN`, both catalogued in
[`shared/references/errors.md`](../../shared/references/errors.md).

### 7. Schedule offer (native `/loop`)

The skill offers to keep the search running automatically with Claude Code's native `/loop` — it
re-runs the search on an interval inside an open Claude session and never writes the user's machine
(no crontab, no launchd). The user answers yes/no; on yes the skill runs the `/loop` line emitted by
`loop-command` and records it with `set-scheduled`. The `/loop` recipe is shown either way. The
scheduling protocol and the safety-net guard hook are owned by
[`shared/references/internals.md`](../../shared/references/internals.md).

## What the user sees / success criteria

At the end of onboarding all of the following are true:

- A **digest** exists at `<workspace>/reports/<date>-digest.md` with real, judged postings.
- A **persisted workspace** at `~/.job-search/` (or a user-chosen path) contains `config.yaml`,
  `preferences.md`, and `jobs.jsonl` — all created or adopted without hand-editing.
- An **optional `/loop` schedule** is running and recorded in the OS registry if the user consented
  (session-bound; nothing is installed on the user's machine).

On a **returning session**, `python3 "$OS" resolve` returns `first_run: false` because
`config.yaml` exists in the workspace, and the skill routes to the home view (latest digest,
pipeline, quick actions) instead of restarting onboarding.

## Edge cases

All failure paths surface a named `E-*` code. Wording and fixes are owned by
[`shared/references/errors.md`](../../shared/references/errors.md); they are not restated here.

- **Missing prerequisites** — `agent-data` missing or unauthenticated. Interactive onboarding
  **remediates** (immediate install — no user input — then guided key + auth) rather than halting;
  the headless runner halts with `E-NO-AGENT-DATA` / `E-NO-AUTH` before any workspace is touched.
  Codes stay internal — never shown to the user.
- **No preferences yet** — `E-NO-PREFERENCES`; the first run halts and directs the user to
  `/job-preference-interview`.
- **Sparse market** — not a named error; zero search results prompt the agent to offer keyword
  broadening conversationally (see
  [`skills/job-search/references/onboarding.md`](../../skills/job-search/references/onboarding.md)).

## Related

- [`../design-docs/index.md`](../design-docs/index.md) — original design rationale and historical
  decision snapshots.
- [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) — system architecture and component map.
