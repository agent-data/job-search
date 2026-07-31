---
title: New-User Onboarding
status: current
verified: partial
last_reviewed: 2026-07-31
code_refs: [skills/job-search/SKILL.md]
---

# New-User Onboarding

## Goal and the magical moment

Within approximately five minutes of installing Job Search, a new user sees real, live job
postings judged against their own stated preferences — strong, moderate, or weak matches with
plain-language reasoning — without writing a single file by hand. Seeing that first digest is the
**magical moment**: the system is no longer abstract; it works, and it works on their actual search.

The five-minute **time-to-first-value (TTFV)** target matters because setup friction is the
primary drop-off point for developer tools. Every step in onboarding either directly builds toward
that moment or gates it safely; none is bureaucratic overhead.

## Trigger and routing

The **job-search** skill is the front door (`/job-search:job-search` as a plugin — plugin skills
are only invocable namespaced; bare `/job-search` for loose-skill installs). On every invocation the skill runs the workspace-discovery
procedure to read the workspace state. When discovery reports `first_run: true` the skill routes to the
first-run playbook; when `first_run: false` it routes to the returning-user home. The routing
logic and both playbooks are owned by [`skills/job-search/SKILL.md`](../../skills/job-search/SKILL.md);
the discovery procedure by `shared/references/runbook.md`.

## The onboarding flow

The full playbook lives in
[`skills/job-search/SKILL.md`](../../skills/job-search/SKILL.md).
This section names each step and points to the owning reference; it does not restate mechanics.
Every ask assumes the user has zero context: one short line of plain English saying what the thing
is and why it is being asked, then the question. Internal vocabulary never reaches the user. That is
carried by the skill itself and graded by behavior rows B1 and B2 in
[`../../evals/behaviors.md`](../../evals/behaviors.md), not pinned in a separate style reference.

### 1. Welcome

A one- or two-sentence opener that sets the user's expectation: prereqs, workspace, preferences,
first search, real matches. No meta-promises ("nothing fails silently", "every step will say so
plainly") — reliability is demonstrated, not announced.

### 2. Preflight prerequisites

A free check before any workspace is created or any metered call is made: is `agent-data` present on
PATH (`command -v agent-data`) and authenticated (`agent-data whoami` reports `api_key_set: true`)?

The agent leads with *why* it's checking and never pre-claims a result it hasn't verified. It keeps the
user oriented — a short what/why line around non-obvious work, in its own words, no per-command
formula — introduces agent-data exactly once (a dependency of this plugin that pulls and reads live
job postings), never re-defining it step by step, and narrates what's happening, never what isn't
("this needs nothing from you"). If the check passes, the agent says so as a verified fact and
continues. If `agent-data` is missing or unauthenticated, **interactive onboarding remediates rather
than stopping** — install first, then connect. A missing CLI is installed immediately and without user
input (`npm install -g agent-data`, verified with `agent-data --version`). If permission settings block
the install, that's a one-line handoff, not an error: the agent gives the exact in-session command
(`! npm install -g agent-data`) and resumes once it lands. Then — and starting here when the CLI was
present but unauthenticated — the agent walks the user through generating an API key (with explicit
steps), authenticates with the contract's `agent-data init --api-key <KEY> -y` line (the same on
every host — see `shared/references/agent-data.md`
→ Auth), and verifies with `agent-data whoami` before continuing. The API key is requested only at
this connect step, never before the install. The **headless runner** (`job-search-run`) can't prompt,
so when it meets either state it stops and closes `blocked` with a digest naming the missing CLI or
the missing key and the command that fixes it.

### 3. Workspace creation or adoption

The skill runs the workspace-discovery procedure to find the workspace path and first-run status. The
discovery order, never-clobber adoption rule, and registry write rules are owned by
`shared/references/runbook.md`.

- **Adopt** an existing workspace: record it in the registry; additively create only missing
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

Either path ends with `preferences.md` present at the workspace path. A run attempted without a
usable brief has nothing to judge postings against, so it stops and closes `blocked`, naming the
missing brief and pointing at `job-preference-interview`.

### 5. Searches and frequency (derived from the brief)

The skill **derives** 2–3 searches from the brief it just built — it does not ask the user to name
keywords — and writes them as `queries[]` entries into `config.yaml` (editing minimally, preserving
comments and structure), then **acknowledges** what it saved and notes the searches are editable
anytime. The user picks a run frequency in plain human terms — no credit math, no cost reasoning.
Config schema and the derive/edit recipes are owned by
`shared/references/runbook.md` and
`shared/references/runbook.md`.

### 6. First live search — the magical moment

The skill invokes `job-search-run` against the new workspace (the run loop itself — search,
dedup, judge, detail-read, digest — is owned by
[`skills/job-search-run/SKILL.md`](../../skills/job-search-run/SKILL.md)).
What the user sees at this step is the payoff: the agent presents strong and moderate matches as
a discovery, with each role's title, company, location, plain-language reasoning, and link.

If the run is blocked instead, the digest and the home view both say what stopped it and what fixes
it; how that surfacing works is owned by
[`../RELIABILITY.md`](../RELIABILITY.md#4-run-health--blocked-surfacing--visible-without-the-exit-code).
Onboarding-specific note: the two likeliest blocks here are a spent monthly allowance — the only
point where API limits surface, and only reactively — and an unreachable service.

### 7. Schedule offer

The skill offers to keep the search running automatically on the user's chosen cadence, as a
yes/no. The advocated default is an **unattended** machine schedule (a `cron`/`launchd` entry or
the host's own scheduler) that fires with no session open; the **in-session loop is the named
fallback**. It is consent-gated — the exact machine change is shown first and written only on the
user's explicit yes — and the scheduling marker is recorded as running **only after a config-time
canary** proves the real invocation works; a failed canary records nothing and stays honest that it
is not scheduled. The agent composes the schedule and the run recipe for its own host (there is no
per-host recipe to look up). The scheduling protocol, eligibility gates, and canary are owned by
`shared/references/runbook.md` (Scheduling setup).

## What the user sees / success criteria

At the end of onboarding all of the following are true:

- A **digest** exists at `<workspace>/reports/<date>-digest.md` with real, judged postings.
- A **persisted workspace** at `~/.job-search/` (or a user-chosen path) contains `config.yaml`,
  `preferences.md`, and `jobs.jsonl` — all created or adopted without hand-editing.
- An **optional recurring schedule** is running and recorded in the OS registry if the user consented
  and its config-time canary passed (the agent resolves the mechanism for its own host; see
  `shared/references/runbook.md` → Scheduling setup).

On a **returning session**, discovery reports `first_run: false` because
`config.yaml` exists in the workspace, and the skill routes to the home view (latest digest,
pipeline, quick actions) instead of restarting onboarding.

## Edge cases

Every failure path reaches the user as a plain cause and fix, written where the step hits it. There
is no error-code catalogue and no code to leak; the wording lives in the skill, and what a stopped
run writes is in `../../shared/references/runbook.md`.

- **Missing prerequisites** — `agent-data` missing or unauthenticated. Interactive onboarding
  **remediates** (immediate install — no user input — then guided key + auth) rather than halting;
  the headless runner stops before any workspace is touched, naming the missing CLI or key.
- **No preferences yet** — the first run stops and directs the user to
  `/job-preference-interview`.
- **Sparse market** — not a named error; zero search results prompt the agent to offer keyword
  broadening conversationally (see
  [`skills/job-search/SKILL.md`](../../skills/job-search/SKILL.md)).

## Related

- [`../design-docs/index.md`](../design-docs/index.md) — original design rationale and historical
  decision snapshots.
- [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) — system architecture and component map.
