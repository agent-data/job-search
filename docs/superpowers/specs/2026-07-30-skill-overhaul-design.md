# Job-search skill overhaul — design

**Date:** 2026-07-30 · **Status:** awaiting review · **Approach:** rebuild every surface on the
structural shape the census proved out (approach A, user-approved with four amendments).

## Evidence base

Held privately (not in this repository): a 2026-07-30 churn analysis of live usage and a 12-entry
per-file census with a cross-cutting pass, both built from live evals of this plugin plus service
telemetry. Aggregate findings this design relies on: 79% churn among classifiable users with
retention concentrated entirely in scheduled runs; six live-eval failure classes (F1
recitation/ordering, F2 unenforced prose contracts, F3 self-inconsistency, F4 path traps, F5
instruction tax, F6 unsatisfiable model-ID rule); ~54% of the 59,213-word corpus with no observed
execution in evals, no repo-visible consumer, or an unmeasurable audience; everything agents
demonstrably followed totaling under ~2,000 words; and the run-lifecycle system (~11.4k words +
1,008 script lines + 144 CI tests) going 0-for-3 in live runs while every run still produced a
correct digest. Evidence-tier discipline applies: server telemetry observes API calls only;
plugin-local state is unobservable; the eval set covers N=6 runs.

## Goals

1. Remove the structural causes of the six failure classes (F1 recitation/ordering, F2 unenforced
   prose contracts, F3 self-inconsistency, F4 path traps, F5 instruction tax, F6 unsatisfiable
   model-ID rule).
2. Cut the corpus from 59,213 words to ~9,000; first-run read path from ~3,550 lines to ~650.
3. Preserve the proven value loop: live multi-source pull → per-posting judgment → durable
   jobs.jsonl → digest → recurring job.
4. Make recurring-job creation the stated goal of onboarding, with a mandatory canary on every
   job the agent configures.
5. Every kept behavior gets a behavior eval, run on both sonnet and haiku. No substring tests.

## Non-goals

API-side fixes (latency, billing — separate track). New features. Any change to user-facing
workspace file formats (preferences.md, jobs.jsonl, config.yaml, digests remain compatible).
Dropping any of the 8 supported harnesses.

## Design laws (from the census; constraints on every file written)

1. Positive recipes with worked examples; no prohibitions where shape is the failure; no quoted
   anti-examples or sayable samples anywhere.
2. Encode invariants in the artifact the agent must touch (files, templates, validators), not in
   reminders.
3. Mechanical rules live in executables (validator script), not prose.
4. Templates are the contract: agents copy them; prose never describes a format a template shows.
5. Weight follows observed traffic; no speculative-audience surfaces.
6. One owner per rule; skills carry their own surface content; the shared core holds only what
   ≥2 skills genuinely need.
7. Tests assert behavior via evals, never substrings.

## Communication model

No welcome template, no canonical sentences, no greeting-order contract. One short "how to
communicate" recipe (~10 positive rules) in the front-door skill, governing HOW, never WHAT:

- Define each concept in plain language the first time the user meets it (brief, source, free
  tier, recurring job, digest) — the offer carries the explanation.
- State cost facts in your own words before metered work (free-tier size, how many calls this
  action starts with).
- One question at a time; discrete choices through the host's question mechanism where present.
- Present matches as message text with reasoning; never a bare file path.
- Never fabricate posting facts; say what the posting does not state.
- Match the user's language and vocabulary; no internal vocabulary (discovery, registry, ledger,
  SKILL, reference files) in user-facing text.

Evals grade the first user-visible message behaviorally: does it tell a non-expert what is
happening in plain language, free of internal vocabulary? (Replaces greeting-order assertions.)

## The five skills (stable namespace; each self-contained; line budgets)

| skill | budget | carries | stops carrying |
|---|---|---|---|
| job-search (front door) | ~150 | routing; communication recipe; first-run flow (whoami check → workspace from templates → one-question sketch → query derivation → run → matches → schedule moment §Scheduling); home view as render recipe + feedback routing + next-actions menu (~80 lines) | onboarding.md (499), home.md (318), greeting contracts, install walkthrough beyond the check+pointer, nudge machinery, update banner |
| job-search-run | ~150 | run recipe: streams, summary-scan steer (kept: killed 65% of detail calls), detail reads sequential or parallel with tier-alias model names, judgment by evaluate-job-fit's rule, jobs.jsonl appends, embedded run-record + digest templates, ~15-line close checklist, consecutive-503 fallback; detail reads parallel-by-default via subagents wherever the host has them (sequential only where it does not), passing `search.detail_model` through only when the user set it | all ledger choreography (L42-144), phase machine, pagination/continuation prose, early-look branch, "read these 8 files", any required model binding |
| evaluate-job-fit | ~80 | current content; posted_at rule fixed to the both-null variant; the two config keys it needs inlined | batch-envelope paragraph; Discovery dependency |
| job-preference-interview | ~120 | sketch + standard interview; front matter via template copy | depth tiers (384w, 0 firings); invoker-pre-pick guard |
| job-search-agent | ~60 | symptom→fix table; usage explanation; config-change pointers | customization.md (253), scheduling-and-consent.md (228), second routing table, quoted near-misses, exact-model copy |

## Shared core (two files replace nine; ~2.5k words)

**`shared/references/agent-data.md`** — the gotchas + cost file:
- Per-source quirks table, extended with the rows the evals proved missing: LinkedIn
  `--location "Remote"` silently returns India-located rows (put remote in keywords; filter on
  `location_display`); `is_remote`/`workplace_type` are null on every LinkedIn row (use
  `location_display` + description text); Ashby/Greenhouse/Lever full-text match is
  progressively relaxed — expect off-topic rows, judge from titles; `id` + `source_url` travel
  together from the search row you copy them from; stop after 2 consecutive detail 503s on a
  source and fall back to summary judgment; `status` bills a call and is never required.
- Pricing/free-tier facts; retryable-boolean branching; cost-context recipe (B = queries ×
  sources; state context before the first metered call).

**`shared/references/runbook.md`** — mechanics:
- Discovery recipe (~334 words) with ONE path convention (all script/template paths written
  plugin-root-relative, e.g. `<plugin-root>/shared/scripts/mechanics/workspace-discovery.sh`).
- Workspace file map (who writes/reads each file).
- Run contract: started-marker → work → end-record + digest; orphaned marker = say the last run
  died, then rerun.
- Scratch rule: `runs/.scratch/<run_id>/` only, deleted at close, never holds full job
  descriptions.

Deleted or absorbed: internals.md, conventions.md (schemas move to templates + validator),
run-lifecycle.md, errors.md (E-QUOTA cause+fix moves to the quirks table), voice.md,
parallelism.md, update.md, build-stamp.md (version read from plugin manifest at the single place
the record template needs it), home.md, onboarding.md, customization.md, scheduling-and-consent.md.

## Structures

- **jobs.jsonl — unchanged.** (189/189 conformance; every digest/record number re-derives.)
- **Run record — slimmed.** Keep: run_id, trigger, scheduler_id, close_state, run_health,
  sources/queries, cost tallies (metered calls by operation), timestamps (one documented format:
  UTC `Z`). Drop: derived counters (re-derive from jobs.jsonl), lifecycle block, pagination
  metrics. Reader stays tolerant of old records.
- **Started-marker** (`runs/.started-<run_id>`) replaces the ledger. Deleted on close.
- **Deleted:** metrics.json (+its 1,072-word contract; local telemetry removed per user),
  detail-model-binding.json (the model-field apparatus is retired entirely: `search.detail_model`
  may exist in config.yaml as a user-owned passthrough, but nothing requires it, nothing
  validates it, and no flow documents it as a decision to make. In its place the run skill
  carries one positive principle, borrowed from subagent-driven development: delegate detail
  reads to fresh subagents — each posting judged in its own isolated context keeps the
  coordinating session's context clean for coordination and lets reads run in parallel wherever
  the host has subagents; sequential only where it does not. The old required+exact form had low
  adherence and forced headless runs sequential — that mechanism is dead; F6 dead),
  pagination scratch contract (subsumed by the scratch rule), lifecycle ledger.
- **preferences.md:** format defined by `templates/preferences.example.md` (cited, copied);
  4-line front-matter check moves to the validator.
- **brief_revision:** defined as `sha256(preferences.md)[:12]`, computed at run start, stored in
  the run record only.

## Scripts

- Keep: `workspace-discovery.sh`, `dedup.sh`, `event-log-append.sh`, `schedule-line.sh`.
- Delete: `lifecycle-append.sh`, `lifecycle-fold.sh`, `support-summary.sh`.
- Add: `validate-workspace.sh` — config.yaml schema, preferences front matter, run-record schema,
  timestamp format, scratch-dir absence after close. The mechanical rules leave prose and live
  here; run at close and by evals.
- `dedup.sh`: add a same-company + near-identical-title guard so multi-location reposts of one
  opening do not each bill a detail read (3 billed duplicates across evals).

## Scheduling and the canary

- The recurring job is the stated goal of onboarding. The ask happens at the peak-value moment:
  immediately after first matches render.
- Consent recorded in config.yaml (`schedule.consented: <ISO date>`); headless/subagent runs
  proceed on recorded consent (fixes the interactive-yes dead end: both headless evals ended
  unscheduled under the old rule).
- **Canary, mandatory, production-derived:** after configuring any recurring job (cron, launchd,
  or host-native loop), the agent verifies the job by running it once through the real scheduled
  path, immediately. Because it follows the first run, cross-run dedup means few or no new
  postings — the canary is naturally cheap. If real time has passed and new postings exist, a
  full run is correct and is what the user wants. Verification = a run record with
  `trigger: scheduled` and healthy close, written by the canary invocation. The first configured
  job must work; setup is not done until the canary passes.
- One copy of the doctrine, in the front door's flow (~300 words). schedule-line.sh stays as the
  install mechanism.

## Eval plan

Behavior → eval matrix (each row = an eval assertion set; all run on **sonnet AND haiku**; RED
baseline = today's iteration-1 artifacts):

| behavior | eval surface |
|---|---|
| first message explains in plain language, no internal vocabulary | TUI + -p quickstart |
| concepts defined at first mention (brief, free tier, recurring job) | quickstart transcript grading |
| whoami-only preflight; no status call anywhere | run transcripts + APIGW-visible calls |
| cost context stated before first metered call | quickstart + headless run |
| summary scan reduces detail reads (ratio vs postings found) | headless run |
| id+source_url pairing (0 fabricated ids) | run transcripts |
| consecutive-503 fallback (fault-injected upstream failures; method chosen in the plan) | targeted eval |
| jobs.jsonl conformance + digest numbers re-derive | validator + grader on artifacts |
| run killed mid-flight → orphaned marker reported honestly next run | kill-injection eval |
| schedule offered right after first matches; consent recorded | quickstart |
| canary runs the real job via the scheduled path before setup is called done | scheduling eval |
| fit judgment: dealbreakers cited, unknowns surfaced, no fabrication | fit eval (unchanged) |
| read-path budget: files/lines read before first API call ≤ target | transcript accounting |
| wall-clock and metered calls vs RED baseline | benchmark deltas |

Plus: writing-skills micro-tests (5+ reps, no-guidance control, manual reads) for the two
highest-risk wordings (first-message behavior; cost context). Grading by artifacts and behavior;
zero substring assertions. CI: the 144 lifecycle tests and all substring tests are retired; the
eval suite + validator become the gate; scripts keep ordinary script tests.

## Migration and compatibility

Existing workspaces work untouched. Old ledgers are ignored; old run records remain readable
(tolerant reader). Hermes/Codex/Cursor/opencode/Gemini/Copilot/Droid/Pi adapters reference no
deleted contract (census-verified: zero lifecycle references outside the repo); each gets a
structural re-verification pass. Version bump: minor (0.8.0) with a CHANGELOG migration note.

## Landing order

1. Harmful-line fixes that stand alone (status-probe removal, contract:66 billing fact, posted_at
   variant, F4 path convention, exact-model → tier aliases).
2. CI conversion: retire substring/lifecycle tests, land the eval suite + validator.
3. The rewrite (skills + shared core + structures + scripts).
4. Full eval matrix on sonnet + haiku; benchmark vs RED baseline; iterate wordings via
   micro-tests where evals fail.
5. Dogfood, 8-harness structural verification, CHANGELOG, version bump.

## Decisions recorded

- Work proceeds on `main` (user-confirmed 2026-07-30).
- The churn analysis and census stay private (they reference external users of the Job Postings
  API); this spec carries only aggregate figures. Private copies live outside the committed tree.
