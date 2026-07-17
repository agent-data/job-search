---
title: Best-in-class cost-aware job-search DX and verified recurring runs
state: active
created: 2026-07-16
---

# Best-in-class cost-aware job-search DX — Implementation Plan

> **Execution choice:** the user explicitly authorized superpowers:subagent-driven-development on
> 2026-07-16. Execute task-by-task with a fresh implementer and task reviewer, then a whole-branch review.
> Work only on the existing codex/job-postings-pagination branch and checkout; do not create a branch or
> worktree. Keep the Progress and Decision logs current in the same commit as the work they describe.

This plan executes
[Cost-aware decisions, explicit models, and canary-verified recurring jobs](../../design-docs/2026-07-16-cost-aware-verified-recurring-jobs-design.md).
Read that design, [ARCHITECTURE.md](../../../ARCHITECTURE.md),
[core beliefs](../../design-docs/core-beliefs.md), and [docs/PLANS.md](../../PLANS.md) before editing.
The first task incorporates the approved post-design amendments into the design document, after which that
document is the product source of truth and this plan is the ordered delivery contract.

## Private authoring anchors — never runtime dependencies

Prompt and skill edits are reviewed against the private authoring guides under docs-private/. Those files
are intentionally untracked and do not ship in the plugin. The stable rule IDs below are the review anchors;
runtime skills and shared references must remain complete without loading, linking to, or discovering
docs-private/.

| Concern | Private authoring source | Stable rules |
|---|---|---|
| Cost-impact decisions and consent | docs-private/agent-agnostic-skills/07-autonomy-calibration.md; docs-private/prompt-style-guide/03-tool-definitions.md | AAS-AUTO-01/02/04/07/11; PSG-TOOL-04/05/14 |
| Clear, truthful user communication | docs-private/prompt-style-guide/06-user-communication.md; docs-private/prompt-style-guide/01-foundations.md | PSG-COMM-01/04/05/06/07/09/10/11/18/20; PSG-F-01/03/09/10/11/14 |
| Exact model dispatch and cold-context workers | docs-private/prompt-style-guide/04-subagents-and-delegation.md; docs-private/agent-agnostic-skills/09-harness-neutral-language.md | PSG-SUB-02/03/04/06/09/13; AAS-LANG-01/03/04 |
| Durable progress and completion evidence | docs-private/agent-agnostic-skills/08-process-vs-domain-skills.md; docs-private/prompt-style-guide/05-harness-injections.md | AAS-PROC-03/04; PSG-INJ-03/04/05/11/14 |
| Harness-neutral scheduling and fallbacks | docs-private/agent-agnostic-skills/09-harness-neutral-language.md; docs-private/agent-agnostic-skills/10-portability-mechanics.md | AAS-LANG-01/03/08; AAS-PORT-01/03/04/05/10 |
| Canonical representation and safe mechanics | docs-private/agent-agnostic-skills/03-conceptual-boundaries-and-disclosure.md; docs-private/agent-agnostic-skills/05-guidance-representation.md | AAS-BOUND-01/03/04/08; AAS-FORM-03/04/06/07/08/09/10/14 |
| Behavioral verification under pressure | docs-private/agent-agnostic-skills/12-testing-and-verification.md; docs-private/prompt-style-guide/08-anti-patterns.md | AAS-TEST-02/03/04/06/07/08/09/10/11/12/13/15; PSG-ANTI-02/03/04/05/07/10/11/12/13 |
| Safety, privacy, and honest recovery | docs-private/prompt-style-guide/07-safety-and-honesty-pressure.md | PSG-SAFE-02/05/08/11/13/14/16/17 |
| Skill shape, triggering, and portability | docs-private/agent-agnostic-skills/02-skill-anatomy.md; docs-private/agent-agnostic-skills/04-triggering-and-descriptions.md; docs-private/agent-agnostic-skills/11-distribution-packaging-and-versioning.md | AAS-SKILL-02/04/05/06; AAS-TRIG-01/02/03/04/05; AAS-DIST-03/05/06 |

Each task below cites the relevant rule IDs. During implementation, use those IDs to review the change; do
not copy authoring-guide prose into the shipped pack or create a runtime pointer to docs-private/.

## Goal

Make the first job-search setup reach a personalized live match quickly, continue reliably after early
results, explain every decision that can increase agent-data calls, and create a recurring job only when
the exact configured models and real unattended execution path have passed a canary.

## Product outcome contract

- **Primary persona:** a technically comfortable job seeker using a coding agent who values the first
  relevant live match and trustworthy unattended follow-through more than configuration ceremony.
- **Time to helpful work:** under two minutes when agent-data is already connected; under five minutes from
  a cold start, measured locally with a fake clock in tests and actual timestamps in release evidence.
- **Activation:** a non-blocked live run has fully evaluated at least one posting and shown at least one
  relevant match with reasoning. A zero-relevant run is useful diagnostic work but is not activation.
- **Three checkpoints:** provisional preferences plus derived searches; the first personalized live match;
  a canary-verified unattended schedule when the user opts in.
- **Cost scope:** agent-data calls only. Do not add model-token prices, compute-cost estimates, budget fields,
  credit controls, or balance claims.
- **Workspace:** silently default to ~/.job-search. Mention an override only as an escape hatch or when
  adopting an existing workspace.
- **Ordinary onboarding:** default to a quick sketch; do not ask the user to choose a workspace, interview
  depth, parallelism, primary model, or detail model.
- **Incremental interaction:** interactive runs show a small set of fully judged relevant matches early and
  then continue automatically. Scheduled and canary runs remain quiet and publish atomically.
- **Recurring truth:** verified means both unattended and canary-tested through the registered execution
  path. A session loop is session-only and never rendered as a verified recurring job.

## Architecture and dependency order

The durable lifecycle contract lands before any UX says a run will continue. Exact config/model ownership
lands before scheduling captures it. The scheduling state machine lands before the home view reports health.
Documentation follows the executable contracts.

    P0 approved design addendum and deferral ledger
      → P1 lifecycle ledger, fold/check mechanics, and local milestone timestamps
      → P2 canonical agent-data usage-context protocol
      → P3 config v2, exact detail model, migration, and model-expiry repair
      → P4 runner progression, early results, interruption recovery, and trigger attribution
      → P5 quick onboarding, activation, and iterative refinement
      → P6 scheduler eligibility, single confirmation, canary, and rollback
      → P7 schedule health and user-safe error rendering
      → P8 Quickstart, cookbook, support matrix, and privacy-safe diagnostics
      → P9 pressure evals, live evidence, release gates, and version bump

P0–P7 and the Quickstart/support-matrix portion of P8 are release blockers. The local support-summary
helper in P8 is P2 tune work: implement it in this plan if the blocking path remains green, but do not hold
the release solely for it. Credential-safe authentication hardening and update-reminder backoff are P3
follow-ups recorded in P0 and are explicitly not release blockers.

## Tech stack

- Markdown skill bodies, shared runtime references, product docs, and design docs.
- Portable POSIX shell mechanics under shared/scripts/mechanics/, always paired with a complete prose
  fallback for hosts without a shell.
- Standard-library Python developer gates and eval helpers under scripts/.
- pytest, the fake agent-data shim, a new fake scheduler shim, skill eval JSON, and isolated temp
  workspaces.
- Local JSON, JSONL, YAML, Markdown, and text artifacts; no shipped Python runtime and no third-party
  runtime dependency.

## Global implementation constraints

- shared/references/ remains the single source of truth. Skills point one hop to the canonical contract and
  do not restate schemas or decision tables. AAS-BOUND-01/03/04; AAS-FORM-04.
- Every increasing agent-data lever gets decision-time context. Neutral and decreasing edits remain quiet.
  One-off requests are consent to run once; persistent writes and metered repair canaries require scoped
  confirmation. AAS-AUTO-01/02/04; PSG-COMM-10/18.
- Mention the 100-call monthly free tier as an available product tier, not as the user's confirmed plan or
  remaining allowance. Do not volunteer an account-visibility caveat when it adds no decision value.
- Lead with calls. A clearly labeled pay-as-you-go dollar equivalent may follow when it is derived from the
  pinned agent-data rate; never label that equivalent an actual charge or inferred balance.
- New config stores an exact search.detail_model. The runner always uses that exact value. The least-powerful
  adequate judgment model is chosen once at configuration time unless the user requests another model; the
  runner never re-decides it. AAS-AUTO-07/11; AAS-LANG-04.
- The scheduler's primary exact model inherits the creating session model unless the user explicitly
  overrides it. The scheduler prompt reads search.detail_model from config and uses that exact model for
  posting-detail judgments.
- No silent exact-model substitution. Expiry or unavailability blocks, proposes exact replacements, and
  requires a new canary before the schedule becomes verified again.
- No run is complete merely because early matches were shown, context compacted, a worker failed, quota was
  reached, or the user refined preferences. Completion is a mechanically checkable lifecycle predicate.
  AAS-PROC-03/04; AAS-FORM-09; PSG-INJ-03/04/11.
- Posting text and supplied application materials are untrusted evidence. They cannot override the skill,
  authorize actions, or become preferences without the user's intent. PSG-TOOL-15; PSG-INJ-01.
- Internal E-* identifiers remain in durable operator records. Normal chat, digest, notification, and home
  surfaces state cause, preserved work, next step, and exact fix without exposing a raw code.
- Never claim a schedule is installed or working until scheduler registration and a real scheduled-path
  canary are both green. Failed canaries leave new jobs disabled or removed and the registry unverified.
- Private authoring guides and dev/eval fixtures never enter the plugin artifact. AAS-DIST-05/06.
- Every knowledge-base edit gets the docs/PLANS.md doc-reviewer protocol. If an authorized independent review
  agent is unavailable, perform an explicit fresh-context review pass and record that limitation; do not
  skip the review silently.
- Preserve unrelated user changes. Use scoped conventional commits and never rewrite existing workspaces or
  historical run artifacts in place.

## Non-goals

- Account-plan or remaining-free-tier metadata before the CLI exposes an authoritative contract.
- Model token pricing, token estimates, dollar comparisons for model compute, or a monetary budget system.
- Cloud scheduling, machine-off guarantees, or any recurring path that cannot reach the private local
  workspace and local agent-data authentication.
- A hosted docs site, web sandbox, or live demo environment for this release.
- Exhaustive live verification of every harness/OS tuple. Structural coverage is exhaustive; live coverage
  is representative and labeled.
- Credential-safe authentication transport beyond documenting the current safe path; tracked as P3.
- Automatic plugin updates; update reminder backoff is tracked as P3 and never auto-updates.
- Re-evaluating already shown postings after every preference edit when the outcome cannot change.
- Resuming opaque or expired pagination cursors. Such runs close as interrupted and restart search cleanly.

## Done when

All release-blocking checks hold from the repo root:

- [ ] The approved design addendum contains every product outcome and deferred item in this plan and no
      longer calls docs-private guides in-repo runtime dependencies.
- [ ] New first-run config is version 2 with an exact search.detail_model; version-1 headless runs remain
      read-compatible and passive home inspection does not migrate them.
- [ ] Interactive early results are followed by reviewing_remaining, never by an early terminal return.
- [ ] lifecycle-fold.sh reports can_complete=true only when remaining and in_flight are zero, every selected
      posting is evaluated or terminally skipped, every attempt is accounted, final run and digest artifacts
      exist, and the ledger is closed.
- [ ] Every scheduled job records trigger attribution, scheduler identity, exact primary model, exact detail
      model, registration evidence, and a green canary run ID.
- [ ] Home distinguishes verified/running, unverified, session-only, registration drift, latest scheduled
      blocked, one missed expected fire, and two-or-more missed fires.
- [ ] Normal user surfaces contain no raw E-* code; internal run records retain the canonical code.
- [ ] README starts with the natural-language golden path, the free-tier context, npm preflight/recovery,
      one expected output, What you can ask, and a dated support matrix.
- [ ] pytest and every repository gate pass.
- [ ] Judgment-heavy and pressure evals run at least five repetitions on the least-powerful available
      adequate test model, with no-guidance controls and pass-rate evidence.
- [ ] Separately authorized live evidence covers one connected first run, one cold start, one eligible
      harness-native scheduler path where available, and one OS scheduler path; gaps are labeled, not
      upgraded to passes.
- [ ] A real metered canary is never run without fresh agent-data cost context and scoped consent.
- [ ] Release manifests are version-synchronized, the build is deterministic, and no docs-private path or
      dev/eval asset ships.

## Execution protocol

For every task:

1. Read the named canonical references and private rule anchors.
2. Add the failing structural test or behavioral eval first and run the narrow RED command.
3. Make the smallest contract and skill changes that turn it green.
4. Run the task's narrow tests, doc lint, and any named grep gate.
5. Run the docs/PLANS.md review protocol for changed knowledge-base docs.
6. Append evidence and decisions to this plan.
7. Commit with the exact scoped conventional-commit subject shown.

Use [BLOCKS] for work another task depends on and [TUNE] for non-blocking polish. Sizes are rough.

### Per-task commit map

Commit after every completed task; do not squash a whole phase into one change.

| Task | Commit subject |
|---|---|
| T0.1 | docs: incorporate approved job-search DX addendum |
| T0.2 | docs: record deferred job-search hardening |
| T1.1 | docs: define run lifecycle and metrics |
| T1.2 | feat: add lifecycle ledger mechanics |
| T1.3 | docs: define activation milestone ownership |
| T2.1 | docs: define agent-data usage decisions |
| T2.2 | feat: surface agent-data usage context |
| T3.1 | docs: define exact-model config v2 |
| T3.2 | feat: migrate legacy model config safely |
| T3.3 | feat: repair unavailable exact models |
| T4.1 | feat: drive runs with a durable lifecycle |
| T4.2 | feat: validate detail evaluation envelopes |
| T4.3 | feat: show early matches and keep reviewing |
| T4.4 | feat: resume review without cursor reuse |
| T5.1 | feat: streamline first-run job search |
| T5.2 | feat: track first relevant activation |
| T5.3 | feat: apply iterative job-search feedback |
| T6.1 | test: add fake scheduler effect harness |
| T6.2 | feat: select only eligible recurring schedulers |
| T6.3 | feat: canary-verify recurring schedules |
| T7.1 | feat: derive recurring schedule health |
| T7.2 | feat: render user-safe job-search failures |
| T8.1 | docs: make the job-search golden path obvious |
| T8.2 | feat: add privacy-safe support diagnostics |
| T9.1 | test: cover cost and scheduling pressure paths |
| T9.2 | no commit when clean; if cross-cutting fixes are required, use fix: close release-gate regressions |
| T9.3 | test: record repeated behavioral eval evidence |
| T9.4 | test: record live recurring-job verification |
| T9.5 | release: ship cost-aware verified job search |

---

## P0 — Ratify the approved addendum and deferred hardening

Rules: PSG-COMM-09/20; AAS-BOUND-03; AAS-DIST-03.

- [x] **T0.1 [BLOCKS, M] Make the design document the complete approved source of truth.**

  **Modify:**
  - docs/design-docs/2026-07-16-cost-aware-verified-recurring-jobs-design.md
  - docs/design-docs/index.md only if its summary needs to reflect the expanded scope

  **RED:** run these audits and save the hits in the Progress log:

      rg -n "in-repo prompt|Current account context is incomplete|cannot confirm|re-canarying" \
        docs/design-docs/2026-07-16-cost-aware-verified-recurring-jobs-design.md

  The current document should fail because it still describes the private guides as in-repo, retains the
  rejected account caveat, and says detail-model changes do not require a canary.

  **GREEN:** add an approved DX addendum covering the persona, time-to-help targets, activation definition,
  silent workspace default, quick sketch, relevant-material wording, provisional confidence checkpoint,
  incremental interactive results, durable lifecycle phases, refinement routing, schedule handoff,
  scheduler liveness, config-v1 migration, exact-model repair, natural-language golden path, documentation
  cookbook, support matrix, privacy-safe support summary, local milestone timestamps, and release/deferred
  classification. Remove the rejected account caveat. State that docs-private is authoring-only and absent
  at runtime. Update the affected-files, test matrix, acceptance criteria, and rollout sections.

  **Verify:**

      python3 scripts/doc_lint.py --root .
      rg -n "docs-private|time to helpful|early_results_shown|registration drift|activated" \
        docs/design-docs/2026-07-16-cost-aware-verified-recurring-jobs-design.md

- [x] **T0.2 [TUNE, S] Record explicit non-release-blocking debt.**

  **Modify:** docs/exec-plans/tech-debt-tracker.md

  Add:

  - P3 credential-safe authentication transport and credential-handling tests, with the current documented
    local init path as the bounded fallback.
  - P3 update-reminder backoff: record checked version/time, suppress the same reminder during the interval,
    let a newer version and compatibility blocker bypass backoff, honor explicit checks, never auto-update.

  Do not create a docs-site or sandbox backlog item; those are deliberate non-goals rather than discovered
  defects.

  **Verify:**

      python3 scripts/doc_lint.py --root .
      rg -n "credential-safe|backoff|never auto-update" docs/exec-plans/tech-debt-tracker.md

---

## P1 — Durable lifecycle, completion guard, and local milestones

Rules: AAS-PROC-03/04; AAS-FORM-08/09/14; AAS-LANG-08; PSG-INJ-03/04/05/11/14.

- [x] **T1.1 [BLOCKS, M] Pin the lifecycle and metrics contract in one public reference.**

  **Create:** shared/references/run-lifecycle.md

  **Modify:**
  - ARCHITECTURE.md
  - shared/references/conventions.md
  - shared/references/internals.md
  - tests/test_reference_resolution.py

  **RED:** add a reference-resolution test that fails until every lifecycle consumer points to the new
  shared reference and the reference defines all eight ordered phases:

      preflight
      searching
      selection_settled
      reviewing_initial_batch
      early_results_shown
      reviewing_remaining
      finalizing
      complete

  **GREEN:** define:

  - hidden append-only ledger path: runs/.lifecycle-{run_id}.jsonl;
  - event vocabulary: run_started, phase_changed, posting_state, attempt_started, attempt_accounted,
    brief_revision, milestone, and run_closed;
  - posting states: queued, evaluating, evaluated, presented, terminally_skipped;
    presented is a flag-like evaluated state and counts in both evaluated and presented, so showing a result
    never makes it look unevaluated;
  - nonterminal early_results_shown semantics;
  - the completion predicate: remaining=0, in_flight=0, selected=evaluated+terminally_skipped, all started
    attempts accounted, final runs/{run_id}.json and reports/{ISO-date}-digest.md written, and ledger closed;
  - blocked and interrupted closing states, neither equivalent to complete;
  - safe resume rules after compaction or process loss;
  - non-resumable pagination cursors and opaque API tokens;
  - prohibited fields: API keys, auth headers, environment dumps, cursors, full job descriptions,
    preferences text, and match prose;
  - local metrics path {workspace}/metrics.json and timestamps: onboarding_started_at,
    agent_data_ready_at, first_live_call_at, first_relevant_match_ready_at, early_results_shown_at,
    run_completed_at, schedule_verified_at;
  - local-only, no-PII, no-telemetry semantics and atomic whole-file writes for metrics.

  Keep the existing pagination scratch separate and explicitly non-resumable.

  **Verify:**

      python3 -m pytest -q tests/test_reference_resolution.py
      python3 scripts/doc_lint.py --root .

- [x] **T1.2 [BLOCKS, L] Add deterministic append and fold/check mechanics.**

  **Create:**
  - shared/scripts/mechanics/lifecycle-append.sh
  - shared/scripts/mechanics/lifecycle-fold.sh

  **Modify:** tests/test_mechanics_scripts.py

  The coordinator is the ledger's only writer. lifecycle-append.sh accepts these exact command shapes and
  emits a canonical single-line JSON object:

      lifecycle-append.sh LEDGER start RUN_ID ISO_TIMESTAMP
      lifecycle-append.sh LEDGER phase RUN_ID ISO_TIMESTAMP PHASE
      lifecycle-append.sh LEDGER posting RUN_ID ISO_TIMESTAMP SOURCE SOURCE_ID STATE BRIEF_REVISION
      lifecycle-append.sh LEDGER attempt-started RUN_ID ISO_TIMESTAMP ATTEMPT_ID OPERATION
      lifecycle-append.sh LEDGER attempt-accounted RUN_ID ISO_TIMESTAMP ATTEMPT_ID METERED OUTCOME REQUEST_ID_OR_DASH
      lifecycle-append.sh LEDGER revision RUN_ID ISO_TIMESTAMP BRIEF_REVISION
      lifecycle-append.sh LEDGER milestone RUN_ID ISO_TIMESTAMP MILESTONE
      lifecycle-append.sh LEDGER close RUN_ID ISO_TIMESTAMP COMPLETE_OR_BLOCKED_OR_INTERRUPTED INTERNAL_CODE_OR_DASH

  Tokens are closed enums or restricted nonsecret identifiers; no free-form posting, preference, or error
  prose enters the ledger. The script validates phase/state tokens, run identity, attempt pairing, monotonic
  terminal closure, and a denylist of secret/cursor fields.

      lifecycle-fold.sh LEDGER WORKSPACE

  lifecycle-fold.sh reads only canonical rows, verifies the derived runs/RUN_ID.json and final digest exist,
  and emits normalized key=value state, including phase, selected, evaluated, terminally_skipped, presented,
  remaining, in_flight, attempts_started, attempts_accounted, closed, close_state, ready_to_close, and
  can_complete. A presented posting remains counted as evaluated. The phase subcommand rejects complete:
  after finalizing and artifact writes, the coordinator requires ready_to_close=true and the close complete
  command atomically establishes phase=complete plus closed=true. Blocked/interrupted closure preserves the
  last reached phase. The fold exits nonzero for malformed or contradictory ledgers. Both scripts must be
  POSIX sh and have a complete prose fallback in run-lifecycle.md.

  **RED tests:**

  - happy phase sequence folds to can_complete=true only after final artifacts exist on disk and a
    run_closed event exists;
  - early_results_shown with remaining postings folds to can_complete=false;
  - an evaluating posting makes in_flight nonzero;
  - an unaccounted retry attempt prevents completion;
  - duplicate posting-state updates fold last-write-wins without double counting;
  - blocked/interrupted close never reports complete;
  - invalid backward phase transitions fail;
  - a cursor, API-key-shaped field, full description, or multiline value is rejected;
  - both scripts pass sh and dash execution where dash exists.

  Run the new tests before creating the scripts and record the expected missing-file failures.

  **Verify:**

      python3 -m pytest -q tests/test_mechanics_scripts.py
      sh -n shared/scripts/mechanics/lifecycle-append.sh
      sh -n shared/scripts/mechanics/lifecycle-fold.sh

- [x] **T1.3 [BLOCKS, S] Define activation and metric-write ownership.**

  **Modify:**
  - shared/references/run-lifecycle.md
  - shared/references/internals.md
  - shared/references/conventions.md

  The front door owns onboarding_started_at and agent_data_ready_at; the runner owns live-call, match,
  early-results, and completion timestamps; schedule setup owns schedule_verified_at. Write the first
  observed timestamp once, except each new onboarding attempt may start a new local setup record. Activation
  is derived from a nonblocked run, one fully evaluated posting, and one relevant match shown with reasoning;
  do not store preferences or match content in metrics. Derive, rather than persist, three durations:
  time-to-help is onboarding_started_at to early_results_shown_at, first-match review latency is
  first_live_call_at to first_relevant_match_ready_at, and total run time is first_live_call_at to
  run_completed_at.

  **Verify:**

      python3 -m pytest -q tests/test_reference_resolution.py tests/test_mechanics_scripts.py
      python3 scripts/doc_lint.py --root .

---

## P2 — Canonical agent-data call context

Rules: AAS-AUTO-01/02/04/07; AAS-FORM-07; PSG-TOOL-04/05/14; PSG-COMM-01/09/10/18.

- [x] **T2.1 [BLOCKS, M] Add one decision table for every call-increasing lever.**

  **Modify:**
  - shared/references/agent-data-contract.md
  - shared/references/internals.md
  - shared/references/conventions.md
  - shared/references/errors.md

  Keep volatile free-tier/rate facts in agent-data-contract.md. Put the action-classification and consent
  protocol in internals.md and point every skill to it.

  The table must cover:

  - first live run;
  - adding/enabling a query or source;
  - increasing cadence;
  - increasing saved or one-off review depth;
  - broadening retrieval in a way likely to create more detail reads;
  - enabling a schedule and its one canary;
  - a metered canary retry or repair canary.

  Classify each action as one-off, persistent, neutral/decreasing, or retry/repair. For each, define known
  first-page calls, uncertain continuation/detail calls, recurring multiplier where applicable, whether the
  free-tier fact is useful, and whether confirmation is required. Model or concurrency edits alone do not
  receive an agent-data warning unless they cause a canary.

  **RED:** add structural assertions in a new tests/test_usage_context_contract.py for the complete action
  set, the exact free-tier number, and the absence of budget/credits/cost config keys.

  **Verify:**

      python3 -m pytest -q tests/test_usage_context_contract.py
      python3 scripts/doc_lint.py --root .

- [x] **T2.2 [BLOCKS, M] Install concise user-facing templates and actual-attempt reporting.**

  **Modify:**
  - shared/references/voice.md
  - skills/job-search/references/onboarding.md
  - skills/job-search-agent/references/customization.md
  - skills/job-search-run/SKILL.md
  - skills/job-search-agent/SKILL.md

  Use one or two sentences on the first live run. When the baseline is four, preserve this approved example:

  > Agent-data offers a 100-call monthly free tier. This search starts with 4 calls; reading promising
  > postings may add detail calls.

  Before agent-data installation, say: “Agent-data offers a 100-call monthly free tier—enough to get started
  with this search.” Do not append an obvious account-visibility caveat. For persistent changes, render the
  structured before/after preview and one confirmation. Scheduled/headless runs use durable consent without
  prompting. Every run reports actual completed attempts from producer-authoritative metering, including
  failed/retried attempts according to the dated contract. Optional dollar equivalents appear after calls,
  are labeled pay-as-you-go equivalents, and are never described as actual charges.

  **RED evals:**

  - first connected setup gets baseline, variable work, and free tier before the first metered call;
  - install-needed setup gets free-tier context without an account caveat;
  - adding a source and raising cadence each preview recurring impact before any write;
  - reducing cadence and disabling a source write immediately without warning fatigue;
  - a second metered canary attempt requires new scoped consent;
  - actual attempt totals match the fake call log after retry and failure.

  **Verify:**

      python3 scripts/eval_harness.py --root .
      python3 -m pytest -q tests/test_usage_context_contract.py tests/test_fake_agent_data.py
      python3 scripts/doc_lint.py --root .

---

## P3 — Config v2, exact model ownership, migration, and repair

Rules: AAS-AUTO-02/07/11; AAS-LANG-03/04/08; PSG-SUB-02/03/04/09/13; PSG-COMM-09/10/20.

- [x] **T3.1 [BLOCKS, M] Pin version-2 config and exact model schemas.**

  **Modify:**
  - shared/references/conventions.md
  - shared/references/internals.md
  - shared/references/errors.md
  - shared/references/parallelism.md
  - templates/config.example.yaml
  - docs/design-docs/core-beliefs.md
  - skills/job-search-run/SKILL.md
  - skills/job-search-run/evals/evals.json
  - skills/job-search-run/evals/files/setup-workspace.sh
  - skills/job-search/references/onboarding.md
  - skills/job-search/references/home.md
  - skills/job-search-agent/SKILL.md
  - skills/job-search-agent/references/customization.md
  - skills/job-search/evals/evals.json
  - TESTING.md
  - scripts/eval_harness.py
  - tests/test_eval_harness.py
  - tests/test_usage_context_contract.py

  Version 2 stores search.detail_model as an exact model identifier, never fast, balanced, high, or inherit.
  The template must not invent a model ID: omit the value and require setup to insert the resolved live
  model. New setup chooses the least-powerful available model that can perform fit judgment well, unless the
  user requested another model. If the host cannot assign a separate worker model, set detail_model equal to
  the exact primary model and run sequentially.

  The runtime dispatch contract is one line of authority: for each posting-detail judgment, use the exact
  search.detail_model. Do not repeat a least-powerful-model decision at run time.

  Scheduler metadata owns the exact primary model and its origin; workspace config owns only the exact detail
  model. Use primary origins session_inheritance, user_override, and repair_session. Run records copy the
  exact detail model and use detail origins configured_auto, configured_user, legacy_v1_selector, and repair.
  If setup cannot determine the creating session's exact model, no verified schedule may be created until
  the user selects an exact available model.

  The formal-review fix also pins a current private binding sidecar and makes onboarding produce its valid
  version-2 config/sidecar pair before the first run. It pulls forward only the runner's bounded version-1
  fail-closed compatibility branches plus the narrow run-record filename filter needed to keep the sidecar
  out of home/usage readers; full migration, rollback mechanics, and interactive repair remain in T3.2/T3.3.

  **RED:** tests fail on any new-config tier token, absent run-record model-origin field, invented template
  model, or runner language that tells a headless run to choose a model again.

  **Verify:**

      python3 -m pytest -q tests/test_usage_context_contract.py tests/test_reference_resolution.py
      python3 scripts/doc_lint.py --root .

- [ ] **T3.2 [BLOCKS, L] Add safe version-1 compatibility and staged migration.**

  **Modify:**
  - shared/references/conventions.md
  - shared/references/build-stamp.md (generated by deterministic build)
  - shared/references/internals.md
  - shared/references/errors.md
  - skills/job-search/references/home.md
  - skills/job-search-agent/references/customization.md
  - skills/job-search-run/SKILL.md
  - skills/job-search/evals/evals.json
  - skills/job-search-run/evals/evals.json
  - skills/job-search-run/evals/files/setup-workspace.sh
  - tests/fake-host-capabilities
  - tests/test_config_v1_migration.py

  Contract:

  - deterministic executable version-1 model-resolution, migration, and repair pressure belongs here and
    requires fake host-capability controls; T3.1 case 39 pins the seven failure conditions structurally but
    is not a behavioral pass;
  - passive home reads version 1 and does not write;
  - version-1 headless runs remain compatible and do not migrate;
  - an action requiring version 2, especially scheduling, resolves an exact detail model and folds migration
    into the single schedule confirmation;
  - migration builds a candidate, preserves comments and unrelated fields, validates it, saves a
    non-clobbering backup at runs/config-backups/{UTC-safe-timestamp}-config-v1.yaml, atomically replaces
    config, performs free preflight, and rolls back if setup/canary fails;
  - after the first successful version-2 run, subsequent failures do not automatically restore stale v1;
  - no raw migration error code is shown in normal chat.

  **RED evals:** passive v1 bytes unchanged; v1 headless run completes; schedule confirmation shows the exact
  migration and model; validation failure leaves original bytes; canary failure restores the pre-migration
  config and removes the new job; first successful v2 run establishes the rollback cutoff.

  **Verify:**

      python3 scripts/eval_harness.py --root .
      python3 -m pytest -q

- [ ] **T3.3 [BLOCKS, M] Define exact-model expiry and one-confirmation repair.**

  **Modify:**
  - shared/references/errors.md
  - shared/references/internals.md
  - skills/job-search-agent/references/scheduling-and-consent.md
  - skills/job-search-agent/references/customization.md
  - skills/job-search-run/SKILL.md
  - skills/job-search/evals/evals.json
  - skills/job-search-agent/evals/evals.json
  - skills/job-search-run/evals/evals.json

  On unavailable exact primary or detail model, never silently substitute. An interactive repair recommends
  the current repair session's exact model for primary and the least-powerful currently available adequate
  judgment model for detail. One scoped confirmation covers exact config replacement, scheduler update,
  costed canary, and rollback behavior. The schedule remains unverified until that canary is green.

  **RED evals:** expired primary, expired detail, user override, failed repair canary, and a baited
  auto-substitution request.

  **Verify:**

      python3 scripts/eval_harness.py --root .
      python3 scripts/doc_lint.py --root .

---

## P4 — Runner progression, incremental results, and honest resumption

Rules: AAS-PROC-03/04; AAS-FORM-09/14; AAS-AUTO-11; PSG-SUB-02/03/04/06/13;
PSG-INJ-03/04/05/11; PSG-COMM-04/09/11.

- [ ] **T4.1 [BLOCKS, L] Drive every run through the lifecycle ledger.**

  **Modify:**
  - skills/job-search-run/SKILL.md
  - shared/references/conventions.md
  - shared/references/errors.md
  - skills/job-search-run/evals/evals.json
  - skills/job-search-run/evals/files/setup-workspace.sh

  The runner must:

  1. create the ledger before mutable work;
  2. append each phase transition;
  3. record every selected posting before detail review;
  4. move posting state through queued, evaluating, and evaluated or terminally_skipped, and mark evaluated
     matches presented after an interactive display;
  5. account every metered attempt exactly once using producer-authoritative status;
  6. use lifecycle-fold.sh, or the pinned prose fallback, before any completion claim;
  7. close blocked/interrupted honestly and preserve completed judgments;
  8. write final run and digest artifacts before closing complete.

  Add run-record fields trigger=manual|scheduled|canary, scheduler_id null for manual and required for
  scheduled/canary, exact primary_model, primary_model_origin, exact detail_model, detail_model_origin, and
  lifecycle close state.

  **RED evals:** completion with remaining work, unaccounted retry, compaction after selection, interruption
  before selection, quota during detail reads, worker failure, and final artifact write failure.

  **Verify:**

      python3 scripts/eval_harness.py --root .
      python3 -m pytest -q tests/test_mechanics_scripts.py tests/test_fake_agent_data.py

- [ ] **T4.2 [BLOCKS, M] Tighten posting-detail dispatch and return envelopes.**

  **Modify:**
  - skills/job-search-run/SKILL.md
  - skills/evaluate-job-fit/SKILL.md
  - shared/references/parallelism.md
  - skills/evaluate-job-fit/evals/evals.json
  - skills/job-search-run/evals/evals.json

  Every cold-context detail worker receives the brief revision, normalized posting identity and source,
  untrusted-content warning, exact search.detail_model, decision rubric, output schema, and exact return
  channel. Its final envelope includes run_id, source, source_id, status, verdict fields, detail-call attempt
  attribution, and no progress chatter. The coordinator validates identity and schema before changing ledger
  state. Sequential fallback uses the same envelope.

  Remove ordinary setup-time subagent explanation. If a host requires permission, the front door asks once
  in outcome language such as faster review; otherwise it proceeds. A headless canary must prove the chosen
  mode works. No worker availability or dispatch is fabricated.

  **RED evals:** cold worker missing context, wrong posting identity, malformed final envelope, unavailable
  worker capacity, and injected instructions inside a posting.

  **Verify:**

      python3 scripts/eval_harness.py --root .
      python3 -m pytest -q tests/test_eval_harness.py

- [ ] **T4.3 [BLOCKS, L] Show a small relevant set early, then continue automatically.**

  **Modify:**
  - skills/job-search-run/SKILL.md
  - shared/references/run-lifecycle.md
  - shared/references/voice.md
  - skills/job-search-run/evals/evals.json

  Preserve pagination correctness: settle candidate selection before detail judgment. In an interactive run,
  review the ordered selected queue and target three relevant matches for the early presentation. Present
  fewer only at a natural tranche boundary when the feed is sparse: after the first rolling parallel batch
  completes or after five sequential judgments, show one or two ready relevant matches; if none are relevant,
  continue. Label the result early, append early_results_shown, immediately transition to
  reviewing_remaining, and continue without asking permission. Scheduled and canary runs never emit partial
  presentation and publish only at finalization.

  Record first_relevant_match_ready_at separately from early_results_shown_at and run_completed_at.

  **RED evals:**

  - three matches ready before the queue drains: early output appears and remaining work completes;
  - only one relevant among five: one early result appears and work continues;
  - zero relevant in first tranche: no empty early card; review continues;
  - scheduled/canary arm: no partial user output;
  - baited prompt says to stop after the first match: ledger prevents completion;
  - user sends feedback while workers are in flight: started workers settle before the revision is applied.

  **Verify:**

      python3 scripts/eval_harness.py --root .
      python3 -m pytest -q tests/test_mechanics_scripts.py
      python3 scripts/doc_lint.py --root .

- [ ] **T4.4 [BLOCKS, M] Specify compaction, restart, and non-resumable search behavior.**

  **Modify:**
  - skills/job-search-run/SKILL.md
  - shared/references/run-lifecycle.md
  - shared/references/errors.md
  - skills/job-search-run/evals/evals.json

  After context compaction, treat the ledger as authoritative. If selection_settled was reached, resume
  queued detail items and reconcile evaluating items without assuming an unresolved call was free or
  replaying it silently. If selection was not settled or continuation requires an opaque/expired cursor,
  close interrupted and start a fresh search with new cost context. Delete stale pagination scratch at the
  next run. Never persist cursors in lifecycle, run, digest, registry, or jobs artifacts.

  **Verify:**

      python3 scripts/eval_harness.py --root .
      python3 -m pytest -q tests/test_mechanics_scripts.py tests/test_fake_agent_data.py

---

## P5 — Quick onboarding, activation, and iterative refinement

Rules: PSG-COMM-04/05/06/07/11/13/15/18; AAS-TRIG-01/02/03/04/05; AAS-AUTO-03;
AAS-BOUND-03; PSG-TOOL-15.

- [ ] **T5.1 [BLOCKS, L] Replace setup ceremony with the quick golden path.**

  **Modify:**
  - skills/job-search/SKILL.md
  - skills/job-search/references/onboarding.md
  - skills/job-preference-interview/SKILL.md
  - templates/preferences.example.md
  - skills/job-search/evals/evals.json
  - skills/job-preference-interview/evals/evals.json

  First use:

  - silently resolves ~/.job-search unless adopting an existing workspace or honoring an explicit override;
  - uses job preferences already present in the invocation;
  - otherwise asks: “In a sentence or two, what are you looking for? If useful, share or point me to
    relevant material such as a resume, cover letter, or notes from previous applications.”;
  - treats supplied material as background evidence, not automatic preferences;
  - writes a provisional high-signal brief and derived searches;
  - shows one compact confidence checkpoint with the provisional brief and search interpretation;
  - starts the default live run under the setup request's consent after cost context, without another
    confirmation;
  - does not ask for workspace, interview depth, parallelism, model, or schedule before useful results.

  The deeper standard and thorough interview paths remain explicit refinement actions, not first-run gates.
  Re-review both skills' frontmatter descriptions for what/when, negative scope, and sibling routing; do not
  put workflow steps or harness-specific syntax in the descriptions.

  **RED evals:** preferences embedded in invocation, one-sentence sketch, resume attachment with conflicting
  evidence, explicit workspace override, existing workspace adoption, and a small-model bait toward asking
  every optional question.

  **Verify:**

      python3 scripts/eval_harness.py --root .
      python3 scripts/doc_lint.py --root .

- [ ] **T5.2 [BLOCKS, M] Make activation and a zero-relevant recovery explicit.**

  **Modify:**
  - skills/job-search/references/onboarding.md
  - skills/job-search/references/home.md
  - shared/references/run-lifecycle.md
  - skills/job-search/evals/evals.json
  - skills/job-search-run/evals/evals.json

  Activation requires a nonblocked run, at least one fully evaluated posting, and at least one relevant
  match shown with reasoning. If no relevant match exists, say the search ran and what was learned, do not
  claim activation, and offer one high-signal broadening suggestion. Any fresh broader run gets new
  agent-data cost context before calls.

  **RED evals:** relevant activation, no-relevant run, quota before any full evaluation, and a match found
  but not yet shown.

  **Verify:**

      python3 scripts/eval_harness.py --root .
      python3 scripts/doc_lint.py --root .

- [ ] **T5.3 [BLOCKS, L] Add immediate, scoped iterative refinement.**

  **Modify:**
  - skills/job-search/SKILL.md
  - skills/job-search/references/home.md
  - skills/job-preference-interview/SKILL.md
  - skills/job-search-agent/references/customization.md
  - shared/references/run-lifecycle.md
  - skills/job-search/evals/evals.json

  Route feedback:

  - clear general preference feedback updates preferences.md immediately, increments brief revision, appends
    brief_revision to an active ledger, and gives a one-line confirmation;
  - posting-specific feedback updates only pipeline state unless the user generalizes it;
  - ambiguous feedback gets one short clarification only when the interpretation changes the result;
  - preference-only changes apply to the remaining queue and recheck shown jobs only when the outcome could
    change;
  - retrieval-changing feedback previews agent-data impact before a new search or persistent write;
  - in-flight evaluations settle under their recorded brief revision before the new revision applies.

  **RED evals:** general role preference, one-company rejection, ambiguous location feedback, remaining-queue
  revision, outcome-changing recheck, outcome-neutral no-recheck, and retrieval broadening.

  **Verify:**

      python3 scripts/eval_harness.py --root .
      python3 scripts/doc_lint.py --root .

---

## P6 — Capability-gated recurring setup and real canary

Rules: AAS-PORT-01/03/04/05/10; AAS-LANG-01/03/08; AAS-AUTO-02/04/07;
AAS-FORM-07/09; PSG-COMM-09/10/18/20.

- [ ] **T6.1 [BLOCKS, L] Build a deterministic fake scheduler and capability fixtures.**

  **Create:**
  - tests/fake-scheduler
  - tests/test_fake_scheduler.py
  - tests/fixtures/scheduler/native-eligible.json
  - tests/fixtures/scheduler/native-session-bound.json
  - tests/fixtures/scheduler/native-no-canary.json
  - tests/fixtures/scheduler/os-eligible.json
  - tests/fixtures/scheduler/model-binding-lost.json
  - tests/fixtures/scheduler/registration-failure.json
  - tests/fixtures/scheduler/execution-pre-meter-failure.json
  - tests/fixtures/scheduler/execution-metered-failure.json
  - tests/fixtures/scheduler/stale-registration.json
  - tests/fixtures/scheduler/scheduled-success.json

  **Modify:**
  - scripts/eval_harness.py
  - tests/test_eval_harness.py

  The dev-only shim exposes probe, register-disabled, inspect, fire, enable, disable, and remove operations.
  Scenarios cover native eligible, native session-bound, native not-canary-testable, OS eligible, model
  binding lost, registration failure, execution failure before metering, execution failure after metering,
  stale registration, and successful scheduled-path artifact creation. Every operation is logged and no real
  scheduler is touched.

  Use these exact shim interfaces, with state and log redirected to the temp workspace:

      export JOBSEARCH_TEST_SCHEDULER_STATE=STATE_JSON
      export JOBSEARCH_TEST_SCHEDULER_LOG=LOG_JSONL
      export JOBSEARCH_TEST_SCHEDULER_SCENARIO=SCENARIO
      tests/fake-scheduler probe
      tests/fake-scheduler register-disabled JOB_ID DEFINITION_JSON_FILE
      tests/fake-scheduler inspect JOB_ID
      tests/fake-scheduler fire JOB_ID
      tests/fake-scheduler enable JOB_ID
      tests/fake-scheduler disable JOB_ID
      tests/fake-scheduler remove JOB_ID

  Add optional eval artifact assertions for scheduler state, lifecycle phase sequence, run fields, registry
  fields, config byte preservation, and forbidden user-surface text. Preserve the existing structural CLI
  and add these exact developer-only interfaces:

      python3 scripts/eval_harness.py --root .
      python3 scripts/eval_harness.py --check-artifacts docs-private/eval-evidence/current-artifacts.json
      python3 scripts/eval_harness.py --aggregate-results docs-private/eval-evidence/current-results.json

  Keep CI free and deterministic. The two evidence inputs are local, untracked, schema-validated JSON.
  current-artifacts.json has workspace plus assertions whose kind is file_exists, json_field_equals,
  jsonl_event_sequence, text_absent, or text_matches. current-results.json has scenario rows with skill,
  scenario_id, exact_model, guided boolean results, control boolean results, and required_control_delta.

  **RED:** write shim unit tests and eval-schema tests first; confirm missing shim/assertion support fails.

  **Verify:**

      python3 -m pytest -q tests/test_fake_scheduler.py tests/test_eval_harness.py
      python3 scripts/eval_harness.py --root .

- [ ] **T6.2 [BLOCKS, L] Implement eligibility, selection, and exact schedule state.**

  **Modify:**
  - shared/references/internals.md
  - shared/references/conventions.md
  - shared/references/errors.md
  - skills/job-search-agent/references/scheduling-and-consent.md
  - skills/job-search-agent/SKILL.md
  - skills/job-search/references/onboarding.md
  - skills/job-search/references/home.md

  A candidate qualifies only when it is unattended, canary-testable through the registered invocation,
  preserves the exact primary model, reaches the local workspace/auth/network, is inspectable, and is
  reversible. Probe the native mechanism first; choose it only if every gate passes. Otherwise choose an OS
  mechanism that passes every gate. If neither passes, create no verified recurring job; a session loop may
  be offered and labeled session-only.

  Expand the scheduling registry object to:

  - installed and verified booleans;
  - mechanism and scheduler_id;
  - absolute workspace, cadence, and set_at;
  - verified_at and canary_run_id;
  - exact primary_model and primary_model_origin.

  Preserve unknown registry fields and use atomic writes. Legacy loop and old installed-only markers read as
  session-only or unverified, never verified. Do not write installed=true during staging. Only the final
  post-canary atomic registry write sets installed=true and verified=true; failure leaves no newly installed
  marker.

  **RED evals:** eligible native wins; ineligible native falls to eligible OS; neither eligible creates
  nothing; legacy loop; unverified legacy marker; existing unowned job requires inspect/adopt-or-replace.

  **Verify:**

      python3 -m pytest -q tests/test_fake_scheduler.py tests/test_eval_harness.py
      python3 scripts/eval_harness.py --root .
      python3 scripts/doc_lint.py --root .

- [ ] **T6.3 [BLOCKS, L] Consolidate the schedule handoff into one useful decision and one canary.**

  **Modify:**
  - skills/job-search/references/onboarding.md
  - skills/job-search/references/home.md
  - skills/job-search-agent/references/scheduling-and-consent.md
  - shared/references/internals.md
  - skills/job-search/evals/evals.json
  - skills/job-search-agent/evals/evals.json
  - skills/job-search-run/evals/evals.json

  Ask after activation, or when the user explicitly asks to schedule:

  - Daily — recommended;
  - Different schedule;
  - Not now.

  Do not dump recipes when the user declines. On yes, show one scoped confirmation containing the cadence,
  exact machine change, removal path, exact primary/detail bindings as facts rather than model choices,
  version-1 migration if needed, agent-data call preview, and one canary. Register disabled where possible,
  inspect the definition, fire it through the scheduler's real path, require a fresh attributable nonblocked
  run plus digest and workspace write, then enable and mark verified. The scheduled prompt says the run is
  headless and must read search.detail_model from config and use that exact model for every posting-detail
  judgment.

  A failed canary removes or disables the newly created job, leaves verified=false, preserves the exact
  failure internally, and never makes a success claim. A pre-meter failure does not consume metered retry
  consent; an after-meter retry gets a new cost preview and confirmation.

  **RED evals:** daily happy path, custom cadence, decline with no recipe dump, pre-meter failure, metered
  failure, config rollback, exact primary inheritance, explicit primary override, exact detail use, and
  scheduler that silently changes the model.

  **Verify:**

      python3 -m pytest -q tests/test_fake_scheduler.py tests/test_eval_harness.py
      python3 scripts/eval_harness.py --root .
      python3 scripts/doc_lint.py --root .

---

## P7 — Schedule health and canonical user-safe errors

Rules: PSG-F-09/10/11/14; PSG-COMM-04/09/20; PSG-SAFE-02/08/11/17;
AAS-LANG-08; AAS-TEST-04/06/12.

- [ ] **T7.1 [BLOCKS, L] Derive ongoing schedule health from local evidence.**

  **Modify:**
  - shared/references/internals.md
  - shared/references/conventions.md
  - skills/job-search/references/home.md
  - skills/job-search-agent/references/scheduling-and-consent.md
  - skills/job-search/evals/evals.json
  - skills/job-search-agent/evals/evals.json
  - docs/exec-plans/tech-debt-tracker.md

  Every run stores trigger=manual|scheduled|canary and scheduler_id. Home compares the registry, the
  scheduler's own local registration, and the latest scheduled-attributable run. Use the configured
  cadence/time/timezone and a documented 30-minute post-fire grace period. One missed expected fire says
  “not recently observed”; two or more says “needs attention.”

  Render these distinct states with this precedence:

  1. registration drift;
  2. latest scheduled run blocked;
  3. overdue by two or more expected fires;
  4. not recently observed after one missed fire;
  5. verified/running;
  6. unverified;
  7. session-only;
  8. absent.

  Canary proves setup but is not counted as an ordinary scheduled fire. Checks are local and unmetered.
  Repair canaries are separately costed and consented.

  **RED fake-clock evals:** just before grace, one missed fire, two missed fires, manual run after missed
  schedule, canary-only history, drift, blocked scheduled run, recovered run, and a daily fire across a
  daylight-saving transition in the configured timezone.

  Mark the schedule.timezone and interrupted-run portions of the existing untested-edge debt entry resolved;
  leave unrelated notification and overlapping-run debt open.

  **Verify:**

      python3 -m pytest -q tests/test_fake_scheduler.py tests/test_eval_harness.py
      python3 scripts/eval_harness.py --root .
      python3 scripts/doc_lint.py --root .

- [ ] **T7.2 [BLOCKS, L] Separate internal classification from user rendering.**

  **Modify:**
  - shared/references/errors.md
  - shared/references/voice.md
  - skills/job-search-run/SKILL.md
  - skills/job-search/references/home.md
  - skills/job-search-agent/SKILL.md
  - all affected eval JSON
  - scripts/eval_harness.py
  - tests/test_eval_harness.py

  Keep canonical E-* values in runs/{run_id}.json and operator explanations. Normal chat, digest, desktop
  notification, and home output use a structured rendering with cause, preserved work, next step, and exact
  fix, with no raw code. Interactive recovery performs safe fixes conversationally instead of requiring
  manual config edits.

  Retry language depends on verified state:

  - verified schedule: name when the next verified run should retry;
  - no schedule: offer a manual retry, not a scheduled one;
  - unverified/session-only/drifted: say it cannot be relied on and offer the exact repair path.

  Extend the eval harness so any declared user-facing artifact containing a raw E-* token fails. Internal
  record assertions require the code, preventing the opposite failure where classification disappears.

  **RED evals:** auth, quota, upstream stretch, model unavailable, config migration failure, canary failure,
  drift, and blocked scheduled run across chat/digest/home/internal record.

  **Verify:**

      python3 -m pytest -q tests/test_eval_harness.py
      python3 scripts/eval_harness.py --root .
      python3 scripts/doc_lint.py --root .

---

## P8 — Quickstart, cookbook, support truth, and privacy-safe help

Rules: PSG-COMM-04/05/06/07/13/15/20; AAS-LANG-01/03; AAS-DIST-03/06;
PSG-SAFE-13/14/17.

- [ ] **T8.1 [BLOCKS, L] Rebuild README around the natural-language golden path.**

  **Modify:**
  - README.md
  - docs/product-specs/onboarding.md
  - docs/PRODUCT_SENSE.md
  - docs/INTERFACE.md
  - docs/RELIABILITY.md
  - docs/SECURITY.md
  - docs/QUALITY_SCORE.md
  - TESTING.md
  - CONTRIBUTING.md only if contributor commands change

  README order:

  1. outcome and privacy promise;
  2. Quickstart with “Set up my job search. I’m looking for…”;
  3. agent-data npm preflight, install/auth recovery, and the 100-call monthly free tier;
  4. one compact example of expected early output and automatic continuation;
  5. What you can ask: setup, refine, run now, schedule, explain usage, why a match, pause/stop;
  6. dated support matrix;
  7. installation and contributor internals.

  Commands are deterministic shortcuts/fallbacks, not the golden path. Do not suggest that new users already
  have a preferences brief; say relevant material such as a resume, cover letter, or prior application
  notes. Explain the private ~/.job-search default without making it a choice.

  The support matrix records harness/version, OS/architecture, scheduler, interactive/headless, tested
  primary and detail model IDs, structural/live status, and verification date. Label structural-only and
  expected-to-work tuples honestly. Do not imply exhaustive live coverage.

  Update product/reliability/security/interface docs to match lifecycle, model, scheduler, cost, and error
  contracts. Remove stale loop-as-recurring, version-1-only, tier-token, adapter, and raw-code language.

  **RED audit:**

      rg -n "choose.*workspace|existing brief|balanced|fast|mechanism:loop|E-[A-Z]" \
        README.md docs/product-specs docs/INTERFACE.md docs/RELIABILITY.md

  Classify each hit before editing; user-facing raw-code examples are removed, internal contract references
  may remain where appropriate.

  **Verify:**

      python3 scripts/doc_lint.py --root .
      python3 scripts/philosophy_guard.py --root .
      rg -n "Set up my job search|What you can ask|100-call|Support matrix" README.md

- [ ] **T8.2 [TUNE, M] Add a local whitelist-only support summary.**

  **Create:** shared/scripts/mechanics/support-summary.sh

  **Modify:**
  - shared/references/internals.md
  - shared/references/errors.md
  - README.md
  - tests/test_mechanics_scripts.py

  On explicit request, generate and show a local summary containing only build stamp, harness/version as
  reported by the host, OS/architecture, schedule state, latest run health, internal error code, aggregate
  agent-data calls, and nonsecret request IDs. Exclude preferences, job descriptions, match details, API
  keys, auth headers, cursors, and environment dumps. Show the complete summary before the user chooses to
  attach it to a GitHub issue. Never upload, open an issue, or launch a browser automatically. Link to
  https://github.com/agent-data/job-search/issues.

  Exact interface:

      support-summary.sh WORKSPACE REGISTRY HARNESS_NAME HARNESS_VERSION

  It writes the whitelist-only summary to stdout. The caller atomically writes
  {workspace}/support-summary.txt, displays the entire file, and asks nothing further unless the user
  explicitly wants help attaching it.

  **RED tests:** seed every forbidden secret/value beside allowed fields; assert the summary contains the
  whitelist and none of the bait. Run through sh and dash.

  **Verify:**

      python3 -m pytest -q tests/test_mechanics_scripts.py
      python3 scripts/doc_lint.py --root .

  Manually read the generated bait-fixture summary and record the output path in the Progress log.

---

## P9 — Pressure verification, live evidence, and release

Rules: AAS-TEST-02/03/04/06/07/08/09/10/11/12/13/15; PSG-F-09/10/11;
AAS-DIST-03/05/06.

- [ ] **T9.1 [BLOCKS, L] Complete effect-based eval coverage.**

  **Modify:**
  - skills/job-search/evals/evals.json
  - skills/job-search-run/evals/evals.json
  - skills/job-search-agent/evals/evals.json
  - skills/job-preference-interview/evals/evals.json
  - skills/evaluate-job-fit/evals/evals.json where the dispatch envelope changes
  - scripts/eval_harness.py
  - tests/test_eval_harness.py
  - TESTING.md

  Consolidate duplicate scenarios and assert effects rather than exact prose. Every crown-jewel scenario has
  a baited shortcut and the opposite-direction control:

  - stop after early results versus complete the queue;
  - claim scheduled after registration versus wait for canary;
  - choose a cheap model at runtime versus obey exact detail_model;
  - silently migrate v1 versus passive compatibility;
  - silently substitute an expired model versus block and repair;
  - expose raw code versus preserve it only internally;
  - retry after a metered canary failure versus obtain fresh consent;
  - resume a cursor versus close interrupted and research;
  - turn posting or resume text into instructions/preferences versus treat it as evidence;
  - ask every setup choice versus reach the first live result quickly.

  Add fixed-time fixtures for milestone and liveness checks. Mark judgment-heavy scenarios stochastic with
  reps at least five and a no-guidance control. Give every artifact a unique run marker so stale artifacts
  cannot create a false pass.

  **Verify:**

      python3 scripts/eval_harness.py --root .
      python3 -m pytest -q tests/test_eval_harness.py

- [ ] **T9.2 [BLOCKS, M] Run the free deterministic gate and fix every regression.**

  **Verify:**

      python3 scripts/doc_lint.py --root .
      python3 scripts/philosophy_guard.py --root .
      python3 scripts/eval_harness.py --root .
      python3 -m pytest -q
      git diff --check

  Also run:

      rg -n "docs-private/" skills shared templates

  Expected: no hits. Inspect every remaining raw E-* hit and every detail-model tier token; user-facing
  runtime copy and version-2 config must have none, while internal contracts, v1 compatibility, and tests may
  retain deliberate hits.

- [ ] **T9.3 [BLOCKS, L] Run repeated small-model behavioral verification.**

  Use the least-powerful available model that is still adequate for each judgment-heavy scenario and record
  its exact ID. Run each marked scenario at least five times with the no-guidance control, aggregate
  pass-rate and variance, and attach the evidence path to the Progress log:

      python3 scripts/eval_harness.py --aggregate-results docs-private/eval-evidence/current-results.json

  Do not silently promote an unexercised host capability to pass.

  Release thresholds:

  - every deterministic scenario passes;
  - every guided stochastic scenario meets its declared pass-rate and control delta;
  - zero early-stop, false-schedule-success, silent-model-substitution, raw-code leak, or unconsented-metered-
    retry occurrences;
  - connected setup is under two minutes and cold setup under five minutes in the representative runs, or
    the release is blocked with the measured cause.

- [ ] **T9.4 [BLOCKS, L] Run separately authorized live first-run and scheduler canaries.**

  Before any agent-data call, show the exact calls-first preview and free-tier context and obtain scoped
  consent. Never infer that the account is on the free tier. Use isolated disposable workspaces and unique
  run markers.

  Live matrix:

  - connected first run through first relevant match and final completion;
  - cold install/auth path without exposing credentials;
  - one eligible harness-native unattended scheduler path, if the current host exposes one;
  - one OS scheduler path, launchd on the available macOS test host;
  - exact primary inheritance and exact configured detail dispatch;
  - canary failure cleanup followed by an explicitly consented repair where practical;
  - machine/session-close survival evidence for the unattended path.

  Record harness/version, OS/arch, scheduler, exact models, timestamps, actual agent-data attempts, run IDs,
  and structural/live status. If no eligible native scheduler exists, label that arm unavailable; the OS arm
  still must pass. Remove every disposable scheduler registration and workspace after evidence capture.

- [ ] **T9.5 [BLOCKS, M] Bump once, build deterministically, and archive the plan.**

  **Modify:**
  - plugin manifests and marketplace metadata through the repo's version-sync procedure; bump the current
    0.6.0 release to 0.7.0 because config semantics and recurring-job behavior change
  - shared/references/build-stamp.md through scripts/build.sh only
  - docs/QUALITY_SCORE.md and TESTING.md with final evidence
  - this plan and docs/exec-plans/index.md

  Run:

      python3 scripts/check_release_integrity.py --check-version-sync
      ./scripts/build.sh
      git status --porcelain
      ./scripts/build.sh
      git status --porcelain
      python3 scripts/doc_lint.py --root .
      python3 scripts/philosophy_guard.py --root .
      python3 scripts/eval_harness.py --root .
      python3 -m pytest -q

  The second build must introduce no diff. Verify the built artifact excludes docs-private/, docs/, tests/,
  evals/, and developer scripts not listed by the packaging contract. Run the plan Self-review, set
  state: completed, add the actual UTC completion date, move this file to docs/exec-plans/completed/, and
  update the index in the same final commit.

---

## Progress log

- 2026-07-16 — Plan created from the approved design conversation, the gstack plan-devex review, current
  runtime contracts, and the private prompt/agent-agnostic style guides. No implementation started.
- 2026-07-16 — Execution pre-flight started on codex/job-postings-pagination at 498afe4. The prior completed
  SDD ledger is archived before this plan's ledger is initialized. Live agent-data calls and scheduler
  writes remain behind T9.4's exact cost-and-machine-change consent gate.
- 2026-07-16 — T0.1 RED audit exited 0 with the expected design failures at lines 44 (`in-repo prompt`),
  150 and 311 (`re-canarying`), and 535 (`Current account context is incomplete`). GREEN removed all four
  hits (the same audit exited 1 with no output), the required approved-term audit exited 0 with
  `docs-private`, `time to helpful`, `early_results_shown`, `registration drift`, and `activated` present,
  and full doc lint reported
  `Doc lint: clean.` The approved DX addendum and design-index summary land in this task's scoped docs commit.
- 2026-07-16 — T0.2 added only the two deferred P3 records: credential-safe authentication transport with
  the current local init path retained as the bounded fallback, and update-reminder backoff with newer-build,
  compatibility-blocker, and explicit-check bypasses plus a never-auto-update guard. The required tracker
  audit found `credential-safe`, `backoff`, and `never auto-update` at lines 248, 266–269, and 272; full doc
  lint reported `Doc lint: clean.` Both follow-ups remain explicitly non-release-blocking, and no hosted-docs
  or sandbox debt item was added.
- 2026-07-16 — T1.1 RED `python3 -m pytest -q tests/test_reference_resolution.py` exited 1 with the expected
  absent-contract assertion (`1 failed, 26 passed`). GREEN defined the single lifecycle/metrics owner and
  linked exactly the architecture, conventions, and internals consumers; the same command reported
  `27 passed`, doc lint reported `Doc lint: clean.`, and full pytest reported `185 passed`. Privacy and
  completion self-review confirmed the exact phase/event/posting/close vocabularies, the fail-closed artifact
  and attempt predicate, presented-as-evaluated counting, honest blocked/interrupted closure, and no durable
  cursor, opaque continuation-token, secret, preference, description, or match-prose persistence.
- 2026-07-16 — T1.1 review-fix RED strengthened semantic tests against the committed contract and reported
  `2 failed, 27 passed` for missing stable `ledger` and `invariants` blocks. GREEN reported `29 passed` after
  the canonical owner adopted marked lists/tables for exact normalized vocabularies, completion clauses,
  recovery branches, persistence exclusions, and metric properties; consumer checks now reject owner
  structures outside that file. Self-review kept the content denylist ledger-scoped while cursor and opaque
  continuation-token exclusion remains durable-artifact-wide. Doc lint was clean and full pytest reported
  `187 passed`.
- 2026-07-16 — T1.1 second review-fix RED against `ae63207` reported `4 failed, 29 passed`: duplicate list
  tokens and identical/conflicting table keys were silently accepted, and the canonical owner lacked a
  marked search-state table. GREEN reported `33 passed` after fail-closed unique/cardinality parsing, bounded
  consumer structure detection, and exact cursor persist/reconstruct/reuse, clean-restart, and separate
  non-resumable-scratch semantics. Doc lint was clean and full pytest reported `191 passed`.
- 2026-07-16 — T1.2 RED mechanics reported `22 failed, 28 passed` with the expected missing lifecycle-script
  errors under `sh` and `dash`; the no-shell-fallback RED separately reported its missing interface prose.
  GREEN added canonical coordinator-only append plus fail-closed fold/check scripts, exact digest derivation
  from the run-started local calendar date, file-plus-milestone artifact proof, last-write-wins posting state,
  attempt accounting, privacy denials, and honest complete/blocked/interrupted closure. Independent review
  found a cross-workspace artifact-binding gap; its regression first reproduced false readiness, then passed
  after the fold bound the exact ledger filename and physical runs directory to the supplied workspace. Final
  mechanics reported `53 passed` under POSIX shells, reference tests reported `33 passed`, doc lint was clean,
  and full pytest reported `216 passed`.
- 2026-07-16 — T1.2 formal review-fix RED reported `28 failed, 55 passed` for empty JSON strings in nullable
  fields, malformed operator-code grammar, append/fold privacy bypasses, impossible calendar/time/offset
  values, and symlinked final artifacts. The review subclaim that `E-NO-AUTH` was rejected was disproved by
  a pre-fix characterization (`1 passed, 82 deselected`); the safe canonical code remains valid while the
  dedicated grammar now rejects malformed codes. A pre-commit portability RED also caught leading-zero
  Gregorian years being interpreted as shell octal; decimal normalization now accepts valid `0008-02-29`
  under both `sh` and `dash`. GREEN reported `87 passed` for mechanics and `33 passed`
  for reference resolution after matching append/fold field-aware privacy checks, portable Gregorian and
  ISO-bound validation, raw-null-or-nonempty enforcement, and non-symlink artifact proof. POSIX `sh`/`dash`
  syntax and diff checks passed, doc lint was clean, and full pytest reported `250 passed`.
- 2026-07-16 — T1.3 RED reported `1 failed, 33 deselected` for the missing canonical metrics-document block.
  GREEN defined append-preserved per-attempt setup records, owner-only write-once timestamps, derived-only
  activation and duration formulas, and pointer-only internals/conventions consumers. The focused contract
  test reported `1 passed, 33 deselected`; combined reference and mechanics tests reported `125 passed`, and
  full pytest reported `255 passed`; doc lint and diff checks were clean.
- 2026-07-16 — T2.1 RED reported `3 failed, 1 passed` for the missing marked action table, marked pricing
  facts, and canonical consumer links. GREEN reported `4 passed` after defining the exact eight action
  families, calls-first baseline and uncertainty fields, recurring multipliers, free-tier usefulness, scoped
  consent rules, quiet neutral/model-only branches, and durable headless consent. Philosophy guard and doc
  lint were clean, the combined focused suites reported `14 passed`, and full pytest reported `260 passed`.
- 2026-07-16 — T2.1 formal review-fix RED reported `2 failed, 5 passed`: the free-tier owner omitted its
  monthly period, while the consumer supplied that volatile period, and the original config-key scan was too
  broad. GREEN reported `7 passed` after single-homing the complete `100_calls_per_month` fact and replacing
  the broad scan with semantic coverage of config templates/schemas and fenced persisted-config examples;
  non-config API/artifact/prose `cost` is explicitly allowed. Philosophy guard and doc lint were clean, the
  combined focused suites reported `17 passed`, and full pytest reported `263 passed`.
- 2026-07-16 — T3.1 RED reported `5 failed, 49 passed` for the missing marked version-2, run-record,
  scheduler, setup-policy, and runtime-dispatch contracts plus the version-1 static template. GREEN reported
  `54 passed` after pinning exact model ownership and origin enums, observed-only detail-origin evidence,
  setup-time least-powerful-adequate selection, exact-primary sequential fallback, and the one-line runtime
  authority. The version-2 examples omit `search.detail_model` until setup inserts a live exact identifier;
  legacy selectors remain explicitly separate version-1 inputs whose full migration mechanics belong to
  T3.2. The eval validator and doc lint were clean,
  full pytest reported `276 passed`, and a deterministic rebuild updated the content hash.
- 2026-07-16 — T3.1 documentation-review fixes added RED coverage for a placeholder in the canonical
  config example, an unscoped version-2 dispatch rule, the bounded version-1 resolver, and versioned
  sequential fallback. The canonical example now omits the model key; version 1 resolves its saved selector
  once through the pinned adapter-free tier mapping, preserves config bytes, and records the exact result
  with `legacy_v1_selector`, while version 2 performs no runtime model selection. Final GREEN reported
  `55 passed` focused and `277 passed` full; eval validation, doc lint, philosophy guard, deterministic
  rebuild, and diff whitespace were clean.
- 2026-07-16 — T3.1 formal-review fix RED reported `4 failed, 53 passed` for stale same-literal
  provenance, non-runnable onboarding, and missing version-1 fail-closed behavior. GREEN introduced the
  current private binding sidecar, runnable exact-model version-2 onboarding, and bounded v1 failure matrix.
  A follow-on collision RED (`1 failed, 22 deselected`) proved the sidecar could be mistaken for a broad
  `runs/*.json` reader; complete timestamp-shaped filename filtering fixed it. Cumulative review then drove
  a three-test integration RED for blocked artifact semantics, stale shipped tier/version guidance, and the
  incomplete runner fixture. Final GREEN reported `60 passed` focused and `282 passed` full, with a valid
  legacy-v1 runner fixture and a seven-condition structural fail-closed contract; executable migration and
  repair pressure remains in T3.2. Eval validation, doc lint, philosophy guard, and diff whitespace were
  clean.
- 2026-07-16 — T3.1 re-review alignment RED reported `5 failed, 44 passed` for complete Review-depth
  write effects, model-binding-only sidecar rotation, honest eval-39 classification, and v1/v2 test guidance.
  A semantic-review RED then reported `2 failed, 26 deselected` for the remaining one-off multiplier/
  confirmation leak and initial-setup wording. Final GREEN reported `85 passed` focused and `285 passed`
  full. Eval 39 retains all seven failure conditions as structural coverage only; deterministic executable
  migration/repair pressure remains in T3.2. Eval validation, doc lint, philosophy guard, shell syntax,
  deterministic build `sha256:dd6ddce33758`, and diff whitespace were clean; focused semantic re-review
  found no remaining Critical, Important, or Minor issues.

## Decision log

- 2026-07-16 — Use ~/.job-search silently rather than adding a workspace choice.
- 2026-07-16 — Treat relevant external materials as evidence, not as an existing preferences brief or
  automatic preference source.
- 2026-07-16 — Settle pagination/selection before judgment, then optimize time-to-first-match within the
  ordered selected queue.
- 2026-07-16 — Use an append-only hidden JSONL lifecycle ledger plus deterministic POSIX append/fold helpers;
  keep pagination scratch separate and non-resumable.
- 2026-07-16 — Store an exact version-2 detail model in workspace config and read it at every dispatch; choose
  the least-powerful adequate judgment model only during setup/repair.
- 2026-07-16 — A recurring primary inherits the exact creating-session model unless explicitly overridden.
- 2026-07-16 — Define verified recurring as unattended plus real-path canary; a session loop is never
  verified recurring.
- 2026-07-16 — Scope cost context to agent-data calls, mention the available 100-call monthly free tier, and
  omit non-actionable account-visibility caveats.
- 2026-07-16 — Keep credential-safe auth and update-reminder backoff as P3, non-release-blocking debt.
- 2026-07-16 — Keep exhaustive structural portability blocking; require representative native/OS live
  evidence and label all untested tuples honestly.
- 2026-07-16 — User override: stay on the existing branch and checkout; skip the subagent workflow's
  worktree step.
- 2026-07-16 — The collaboration API exposes no model selector. Dispatches use fresh context and explicitly
  state task/review complexity, while the unavailable model field is recorded as a harness limitation.

## Self-review

Before handing this plan to implementation:

- [x] Every approved amendment is assigned to a task or explicitly listed as a non-goal/deferred item.
- [x] Every skill/prompt task cites stable docs-private AAS/PSG rule IDs without creating a runtime
      dependency on private files.
- [x] Every blocking behavior has a RED test/eval, an observable GREEN effect, and a verification command.
- [x] The plan specifies exact paths, schemas, phase names, state names, consent boundaries, and ownership.
- [x] The two failure directions are covered: silent expansion/false success and warning fatigue/setup
      ceremony.
- [x] Exact model selection occurs once at configuration; runtime dispatch always uses search.detail_model.
- [x] Early results are explicitly nonterminal and followed by automatic continuation.
- [x] Live metered work is separately authorized and cannot occur as part of the free merge gate.
- [x] Credential and update hardening are not accidentally release blocking.
- [x] No unresolved implementation marker, fake command, or undecided product behavior remains.
