---
title: Hermes Job Search Concierge Layer
status: superseded
verified: partial
last_reviewed: 2026-06-30
code_refs: [README.md, skills/job-search/SKILL.md, skills/job-search-run/SKILL.md, skills/job-search-agent/SKILL.md, shared/references/platform/hermes.md, runtime/hermes_job_search/cli.py, scripts/build.sh, scripts/validate_platforms.py]
---
# Hermes Job Search Concierge Layer

> **Superseded** by [Hermes Job Search Assistant — Seamless Install + Adapter-Native Onboarding](2026-06-30-hermes-job-search-assistant.md). Kept for history. Its host-gating, memory-permission model, and "calibration" framing did not survive the [harness review](hermes-harness-review/overview.md); the successor is adapter-first.

Adds a Hermes-specific concierge layer that makes job-search feel like a native Hermes assistant without forking the product's domain core. The concierge layer owns the Hermes-only experience — bootstrap guidance, memory-assisted preference drafting (with permission), first-run calibration, and Hermes-native scheduling/delivery orchestration — while the existing installable skills and deterministic runtime remain the execution substrate. The visible front door stays canonical: on Hermes, `job-search` behaves like a concierge; on every other host, it keeps the existing portable behavior.

## Goal

From a Hermes user's perspective, the experience should collapse into one ask: install this and help me find a job. The user should not need to think about taps, runtime bundles, internal skill boundaries, or which worker skill actually runs the search. Hermes should absorb that complexity, guide the user through a clear preference-shaping and calibration loop, and then offer automation once the first manual results look right.

## Non-goals

- Do not replace the portable core skills or rename the public front door away from `job-search`.
- Do not create a dashboard or other traditional application surface; this remains conversational infrastructure for Hermes and other agents.
- Do not duplicate Hermes-native messaging/channel-setup documentation inside the plugin; if a new destination needs setup, Hermes should follow its own native setup path and then resume job-search.
- Do not add a large persistent analytics subsystem; derive most explanations and lightweight analytics on demand from existing state plus optional live re-checks.
- Do not introduce numeric fit scoring, weighted ranking, or a machine-readable rubric in saved state.

## Architecture

The Hermes design is explicitly two-layered, with a small source-only bootstrap layer:

1. **Installable skill surface remains canonical.** The installable skills stay in `skills/`: `job-search`, `job-search-run`, `job-preference-interview`, `evaluate-job-fit`, and `job-search-agent`. On Hermes only, `job-search` becomes the concierge front door and `job-search-agent` becomes the admin/power-user surface. The other three remain worker/power-user skills.
2. **Hermes-specific source layer lives separately.** Hermes-only guidance and contracts live under `hermes/`, not in the cross-host shared references. This source layer stores bootstrap and concierge-specific material that other hosts can ignore safely.
3. **Variant A build strategy.** Keep installable skills directly in `skills/`. Use `hermes/` as a source area for Hermes-only references and build-time bundling into the relevant installable skills. Avoid a second generated public skill family unless a later change proves it necessary.
4. **Deterministic runtime stays shared.** The existing `runtime/hermes_job_search/` CLI remains the Hermes path's deterministic executor for workspace, registry, config, event-log, run-record, and digest operations. The concierge layer does not re-own those concerns; it orchestrates when and why they are used.

## Bootstrap vs post-install use

The design treats pre-install bootstrap and post-install concierge use as different phases.

### Bootstrap phase (before installation)

Before the plugin is installed, there is no concierge skill. The bootstrap source of truth is a single file:

- `hermes/INSTALL.md`

The main README's Hermes section should stop duplicating step-by-step setup and instead point there directly. `hermes/INSTALL.md` must contain everything generic Hermes needs to:

- install or register the plugin
- verify that the skills are visible
- verify `agent-data` presence and auth state
- understand the first invocation path

This is a documentation boundary only. It is acceptable that other hosts ignore `hermes/`; the assumption is that the active agent is smart enough to follow only the installation path that applies to it.

### Post-install phase

Once installed, the user should never need to think about `hermes/` again. The normal user entrypoint is still `job-search`, but on Hermes the host-specific concierge flow activates automatically. Installed behavior must not depend on the source repo's `hermes/` tree still existing; any Hermes-only references needed at runtime should be bundled into the installable skills.

## Hermes-only behavior is host-gated

The concierge behavior is active only when the host is Hermes.

- On Hermes, `job-search` follows the concierge flow defined here.
- On every other host, `job-search` keeps the existing portable flow.

This preserves one canonical front door and avoids introducing a second public skill name that would create routing ambiguity (`job-search` vs a hypothetical `hermes-job-search`). The skill's trigger phrasing and references should be written so Hermes naturally treats `job-search` as the first-run and returning-user front door without weakening other hosts.

## Hermes source layer (`hermes/`)

Recommended source layout:

- `hermes/INSTALL.md`
- `hermes/references/bootstrap-contract.md`
- `hermes/references/onboarding-flow.md`
- `hermes/references/memory-draft-policy.md`
- `hermes/references/delivery-handoff.md`

The goal is separation without a second runtime dependency. `hermes/` is the source layer for Hermes-only guidance, while bundled copies inside the installable skills are the runtime layer for installed behavior.

## Post-install concierge flow inside `job-search`

On Hermes only, `job-search` should follow this flow.

### 1. Silent readiness check

Before any user-visible branching, do a quick silent check of:

- skill/runtime presence
- workspace presence
- `agent-data` CLI presence
- `agent-data` auth state
- whether a preferences brief already exists
- whether a prior schedule/delivery target already exists

If something is missing, fix it automatically when safe and local; otherwise ask only the minimum needed question.

### 2. Preferences come before searching

If there is no workspace or no usable preferences brief, start with preference shaping, not manual query authoring. Briefly explain why preferences come first — so Hermes can decide which postings are relevant before it starts pulling and notifying.

### 3. Ask permission before drafting from prior context

If Hermes has enough prior context to be useful, `job-search` must ask permission before using memory and session history to draft a starting brief. Only if the user agrees should Hermes synthesize and show a draft. The prompt should explain the benefit briefly, make clear that prior context would be used, avoid sounding creepy or overconfident, and offer a clean decline path.

If the user declines, offer an immediate choice between:

- short interview
- comprehensive interview
- import existing brief

### 4. Draft-first path (only with permission)

If the user agrees, Hermes should create a concise, editable draft brief from memory and session history and present it clearly as a draft, not as settled truth. After showing the draft, offer:

- use this as a starting point and refine over time
- short interview
- comprehensive interview
- import an existing brief

The draft is working material, not durable profile truth.

### 5. Interview/refinement path

If the user chooses interview:

- ask one question at a time
- keep open-ended questions actually open-ended
- use `clarify` only for true multiple-choice decisions
- write the result back into the canonical workspace brief

If the user chooses refinement:

- make surgical edits to the draft
- avoid restarting a full interview unless the user wants that

The short/comprehensive distinction should be concrete: what kinds of topics each covers, rough question count, and why someone would choose one over the other.

### 6. Derive starter search setup automatically

Once the brief is good enough, Hermes should derive one or more starter queries automatically and explain what it saved. The user should not be forced to author raw query syntax unless they want that level of control.

### 7. Run the first batch manually

After preferences exist, Hermes should run the first batch manually and treat it as calibration, not just as a demo. The user-facing result should include:

- relevant jobs only
- concise reasoning for each presented match
- lightweight analytics about the batch
- a summary of filtered-out jobs, not the full filtered list by default

The analytics should help the user decide whether the system is aimed correctly. Include, at minimum:

- total pulled
- total filtered out
- rough breakdown of why jobs were discarded
- counts by major discard reason
- uncertainty markers where relevant

Filtered-out jobs should be summarized first, with an option to inspect them if the user wants.

### 8. Ask for the user's reaction first

After the first manual batch, Hermes should ask for the user's reaction before proposing any tuning changes. Hermes should not decide on the user's behalf that results were "poor" or "good enough"; it should make the batch legible enough for the user to judge. Tuning suggestions can follow the user's reaction.

### 9. Tuning loop

If the user wants changes, Hermes should help tune natural concepts first:

- role focus
- location/remote preference
- seniority
- compensation floor
- company stage/type
- dealbreakers
- search breadth/freshness

Avoid surfacing internal knobs unless the user asks. The plugin's job is to make the system steerable, not expose every mechanism up front.

### 10. Offer automation proactively once the user is satisfied

Once the user indicates the first manual batch is satisfactory, Hermes should proactively offer automation. It should present a small cadence menu, recommend daily, and let the user choose.

### 11. Delivery destination selection

When asking where results should go, Hermes should offer:

- here
- any already-configured destinations
- set up a new destination

If the user selects a new destination, `job-search` should ask which platform or destination they want, then hand off to Hermes-native channel setup and resume the flow afterward. This should feel continuous to the user, not like a separate product.

### 12. Final informational summary, then create the job

Before creating the recurring job, Hermes should show a short informational summary of:

- the current preferences basis
- chosen cadence
- delivery destination
- what the recurring job will do

This summary is informational only. After showing it, Hermes creates the job immediately.

### 13. Delivery format defaults

Recurring delivery should contain:

- the digest-ready summary
- lightweight analytics

by default. Hermes should mention that it can simplify future deliveries to summary-only if the user prefers a shorter format.

## Conversational use after setup

This plugin is not a dashboard. The important design target is natural follow-up questions such as:

- "any new jobs today?"
- "how many jobs have we filtered out?"
- "I saw X company posted a new job, but we didn't get an alert — why not?"

The plugin should provide Hermes enough structure and inspectable state that these questions are easy to answer.

### Explainability model

For questions like "why didn't we alert on X?", Hermes should:

1. inspect stored local artifacts first
2. if needed, perform a live re-check of the posting or search state

Most explanations and analytics should be derived on demand from existing logs and state plus optional live checks, not from a large new persistent analytics layer.

## Memory and session-history policy

Use a moderate drafting policy.

- Memory and session history may inform a draft preferences brief, but only with permission.
- The draft must always be presented as editable working material.
- The canonical working state is the local workspace brief, not Hermes global memory.
- Inferred preferences should not be silently promoted to durable user-profile truth unless the user explicitly confirms they are durable.

## Delivery-handoff policy

The plugin should not teach messaging setup itself. If the user wants delivery in a new destination, the plugin should hand off to Hermes-native setup and then resume. The plugin owns the orchestration decision, not the messaging product surface.

## Explainability and state

Prefer lean, inspectable persistent state and on-demand analytics. The existing workspace artifacts plus the deterministic runtime should remain sufficient for most explanations. Add new persistent analytics state only if a concrete explanation gap cannot be solved from existing records plus live re-checks.

## Why this design

This design keeps the cross-agent domain core stable, preserves one canonical front door, avoids a second visible Hermes-specific skill family, and still lets Hermes feel truly native. It also matches the repo's prompt-style-guide: clear boundaries, purpose before procedure, explicit non-goals, and host-specific behavior without polluting the shared contracts.