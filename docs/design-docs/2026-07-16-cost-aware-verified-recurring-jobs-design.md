---
type: design-doc
title: "Cost-aware decisions, explicit models, and canary-verified recurring jobs"
status: current
verified: partial
last_reviewed: 2026-07-16
code_refs: [shared/references/agent-data-contract.md, shared/references/internals.md, shared/references/conventions.md, shared/references/parallelism.md, shared/references/errors.md, skills/job-search/SKILL.md, skills/job-search/references/onboarding.md, skills/job-search/references/home.md, skills/job-search-agent/SKILL.md, skills/job-search-agent/references/customization.md, skills/job-search-agent/references/scheduling-and-consent.md, skills/job-search-run/SKILL.md, templates/config.example.yaml, tests/fake-agent-data]
claimed_paths: [skills, shared/references, templates, tests, docs/design-docs]
owner_area: Skills & references
repos: [job-search-os]
---

# Cost-aware decisions, explicit models, and canary-verified recurring jobs

This design responds to three failures observed during a Job Search plugin dogfood:

1. the setup flow created a local recurring job but did not prove that its scheduled path worked;
2. the recurring primary used an older hardcoded model instead of the model creating the job; and
3. cost context appeared for pagination but not for other choices that can increase agent-data calls.

The design is approved. Implementation is pending. Until implementation lands, the runtime contracts in
`shared/references/` remain the executable source of truth; this document owns the approved delta and
supersedes the design intent in
[`2026-07-11-verify-dont-encode-design.md`](2026-07-11-verify-dont-encode-design.md).

The three changes share one product requirement: a recurring search must be understandable before the user
commits to it and observable before the agent calls it working. The user sees what can drive agent-data
usage, the scheduler carries deliberate model choices, and setup ends only after a real scheduled-path
canary succeeds.

## Goals

- Provide agent-data call context at every decision that can increase expected metered calls.
- Mention the available 100-call-per-month free tier without claiming a user's plan or remaining allowance.
- Make the recurring primary inherit the exact model from the session creating the job unless the user
  specifies another model.
- Select one exact detail-read model during configuration, persist it in `search.detail_model`, and use it
  without re-deciding on every run.
- Choose a recurring mechanism by capabilities: unattended execution and a real scheduled-path canary are
  both mandatory.
- Prefer a harness-native mechanism only when it satisfies the same eligibility gates as every fallback.
- Write `installed: true` only after registration and execution evidence are green.
- Preserve existing workspaces and schedules through explicit, non-destructive migration paths.
- Review every skill and reference edit against the private prompt and agent-agnostic style-guide rule IDs.
  `docs-private/` is an untracked, authoring-only input; it is absent from the installed plugin, and no
  runtime skill or shared reference may load, link to, or discover it.

## Non-goals

- Model-compute prices, token estimates, or model-spend comparisons.
- `budget`, `credits`, or `cost` configuration fields, monetary caps, or a cost dashboard.
- Account-plan or remaining-allowance integration before agent-data exposes authoritative CLI metadata.
- Inventing a future account command, response field, or plan schema.
- Automatic substitution when an exact configured model becomes unavailable.
- Cloud scheduling; the recurring job must reach the user's local workspace and local agent-data auth.
- Guaranteeing execution while the machine itself is powered off.
- Re-running a live canary against an existing schedule without scoped user consent.

## Product stance

### Context, not budget controls

The user decides outcomes: how many searches run, which sources are covered, how often the search fires,
and how deeply unseen postings are reviewed. The agent translates those choices into calls-first context at
the moment it can change the decision. It does not make the user administer a monetary budget or teach API
mechanics during ordinary use.

The two failure directions are:

- silent expansion, where a reversible configuration edit increases recurring metered work without useful
  context; and
- warning fatigue, where every run or harmless edit triggers an account lesson or redundant confirmation.

The chosen design previews cost-impacting decisions, treats explicit one-off requests as consent, records
durable consent for scheduled runs, and leaves neutral or decreasing edits quiet. This operationalizes the
decision instead of relying on "be cost-aware" prose (PSG-F-09/10; AAS-AUTO-02/04).

### Verified recurring means unattended and canary-tested

A registered job is not necessarily a working job. A scheduler can accept a definition that later fails
because its execution context cannot write the workspace, reach the network, see agent-data credentials, or
preserve the intended model. Setup therefore proves both existence and execution through the real scheduled
path before recording success (PSG-SUB-06; AAS-FORM-09; AAS-TEST-12).

An in-session loop is useful as a temporary monitor but does not meet the product definition of a recurring
job: it stops when the session closes. The new `installed: true` meaning is deliberately narrower — a
verified unattended job only.

## Approved DX addendum

The following product outcomes were approved after the original design review. They are normative for this
release and complete the approved delta that implementation must follow. Private style guides under
`docs-private/` may inform authoring review by stable rule ID, but they do not ship and are never runtime
dependencies. The installed plugin and its public references must be complete when `docs-private/` is
absent.

### Persona, time to help, and activation

- **Primary persona:** a technically comfortable job seeker using a coding agent who values the first
  relevant live match and trustworthy unattended follow-through more than configuration ceremony.
- **Time to helpful work:** under two minutes when agent-data is already connected; under five minutes from
  a cold start. Tests use a fake clock, and separately authorized release evidence records actual local
  timestamps.
- **Activated:** setup is activated only when a non-blocked live run has fully evaluated at least one
  posting and shown at least one relevant match with reasoning. A zero-relevant run is useful diagnostic
  work but is not activation; explain what the run learned and offer one high-signal broadening suggestion.
- **Three checkpoints:** provisional preferences plus derived searches; the first personalized live match;
  and, only when the user opts in, a canary-verified unattended schedule.

Milestones are local product evidence, not telemetry. Store no preferences, match content, or other PII in
`{workspace}/metrics.json`; write the whole file atomically. The front door owns
`onboarding_started_at` and `agent_data_ready_at`, the runner owns `first_live_call_at`,
`first_relevant_match_ready_at`, `early_results_shown_at`, and `run_completed_at`, and schedule setup owns
`schedule_verified_at`. Write each first-observed timestamp once, except that a new onboarding attempt may
start a new local setup record. Derive time to helpful work from `onboarding_started_at` to
`early_results_shown_at`, first-match review latency from `first_live_call_at` to
`first_relevant_match_ready_at`, and total run time from `first_live_call_at` to `run_completed_at`.

### Silent workspace and quick natural-language setup

Ordinary first use silently resolves `~/.job-search`. Mention an override only as an escape hatch, when
honoring an explicit override, or when adopting an existing workspace. Never make the default workspace a
setup choice.

The natural-language golden path begins with a request such as “Set up my job search. I’m looking for…”.
Use preferences already present in the invocation. Otherwise ask exactly one quick-sketch question:

> In a sentence or two, what are you looking for? If useful, share or point me to relevant material such as
> a resume, cover letter, or notes from previous applications.

Supplied material is background evidence, never an existing preferences brief and never an automatic source
of preferences. Write a provisional high-signal brief and derived searches, then show one compact confidence
checkpoint containing the provisional brief and the search interpretation. After the agent-data call context,
the setup request itself authorizes the default live run; do not ask for another confirmation. Workspace,
interview depth, parallelism, primary model, detail model, and schedule are not first-result gates. Standard
and thorough interviews remain explicit refinement actions.

### Durable lifecycle and incremental interactive results

Every run has an append-only local lifecycle ledger at `runs/.lifecycle-{run_id}.jsonl`. The ordered phases
are:

1. `preflight`
2. `searching`
3. `selection_settled`
4. `reviewing_initial_batch`
5. `early_results_shown`
6. `reviewing_remaining`
7. `finalizing`
8. `complete`

The event vocabulary is `run_started`, `phase_changed`, `posting_state`, `attempt_started`,
`attempt_accounted`, `brief_revision`, `milestone`, and `run_closed`. Selected postings move through
`queued`, `evaluating`, and `evaluated` or `terminally_skipped`; `presented` is a flag-like evaluated state
and counts as both evaluated and presented. The coordinator is the only ledger writer. The ledger contains
restricted identifiers and state only: never API keys, auth headers, environment dumps, cursors, full job
descriptions, preferences text, or match prose.

`early_results_shown` is nonterminal. A run can close complete only when `remaining=0`, `in_flight=0`, every
selected posting is evaluated or terminally skipped, every started attempt is accounted, the final
`runs/{run_id}.json` and `reports/{ISO-date}-digest.md` exist, and the ledger is closed. Blocked and
interrupted are honest terminal close states, not completion. After context compaction or process loss, the
ledger is authoritative: resume queued review only after `selection_settled`; otherwise close interrupted
and start a fresh search with new call context. Opaque pagination cursors are never persisted or resumed.

In an interactive run, settle the candidate selection before detail judgment, then target three fully judged
relevant matches for an early presentation. At a natural sparse-feed boundary — the first rolling parallel
batch or five sequential judgments — show one or two ready relevant matches; if none are relevant, keep
reviewing without an empty early card. Label the presentation early, append `early_results_shown`, transition
immediately to `reviewing_remaining`, and continue without asking permission. Scheduled and canary runs stay
quiet and publish atomically during finalization.

### Immediate, scoped refinement

Route feedback by its effect:

- clear general preference feedback updates `preferences.md` immediately, increments the brief revision,
  appends `brief_revision` to an active ledger, and gets a one-line confirmation;
- posting-specific feedback changes only pipeline state unless the user generalizes it;
- ambiguous feedback gets one short clarification only when its interpretation would change the result;
- preference-only changes apply to the remaining queue, and shown jobs are rechecked only when the outcome
  could change;
- retrieval-changing feedback receives fresh agent-data impact context before a new search or persistent
  write; and
- in-flight evaluations settle under their recorded brief revision before the new revision applies.

### One schedule handoff and ongoing liveness

Offer scheduling after activation, or when the user explicitly asks for it, as one decision:

- Daily — recommended;
- Different schedule; or
- Not now.

When the user declines, do not dump scheduler recipes. On yes, one scoped confirmation contains the cadence,
exact machine change, removal path, exact primary and detail bindings as facts rather than new model choices,
any required version-1 migration, the agent-data call preview, and one canary. Register disabled where
possible, inspect the definition, fire it through the scheduler’s real path, require a fresh attributable
non-blocked run plus digest and workspace write, then enable and atomically mark the schedule installed and
verified. Failed canaries remove or disable a newly created job, leave it unverified, preserve the exact
failure internally, and make no success claim. A retry after metering requires a fresh preview and scoped
confirmation; a pre-meter failure does not consume the authorized canary.

Home derives scheduler liveness from the local registry, the scheduler’s registration, and the latest
scheduled-attributable run. Use the configured cadence, local time, and timezone with a 30-minute post-fire
grace period. One missed expected fire is “not recently observed”; two or more is “needs attention.” Render
states in this precedence: registration drift; latest scheduled run blocked; overdue by two or more expected
fires; one missed fire; verified/running; unverified; session-only; absent. A canary proves setup but does
not count as an ordinary scheduled fire. Liveness checks are local and unmetered; repair canaries remain
separately costed and consented.

Normal chat, digest, notification, and home surfaces state the cause, preserved work, next step, and exact fix
without exposing a raw internal `E-*` code. Durable run records and operator explanations retain the canonical
classification. Retry language follows verified state: name the next verified run only for a verified
schedule; otherwise offer a manual retry or the exact repair for an unverified, session-only, or drifted job.

### Config-v1 migration and exact-model repair

Version-1 headless runs remain read-compatible and never migrate config; a passive home read also leaves the
bytes unchanged. An action that requires version 2, especially scheduling, resolves the exact detail model
and folds migration into the action’s single confirmation. Build and validate a candidate while preserving
comments and unrelated fields, save a non-clobbering backup at
`runs/config-backups/{UTC-safe-timestamp}-config-v1.yaml`, then atomically replace the config and run free
preflight. If setup or the first canary fails, restore the original config and remove the new job. The first
successful version-2 run is the rollback cutoff; later run failures do not restore stale version-1 config.

An unavailable exact primary or detail model is never silently replaced. Interactive repair recommends the
repair session’s exact model for primary and the least-powerful currently available adequate judgment model
for detail. One scoped confirmation covers the exact config replacement, scheduler update, agent-data call
preview, canary, and rollback behavior. When a schedule exists, changing the exact detail model makes it
unverified until a real-path canary proves the new binding; a repair schedule becomes verified again only
after that canary is green.

### Documentation cookbook, support truth, and privacy-safe help

The README is part of the release contract. Its order is: outcome and privacy promise; the natural-language
Quickstart; agent-data npm preflight plus install/auth recovery and the 100-call monthly free tier; one compact
example of early output and automatic continuation; a “What you can ask” cookbook covering setup, refine,
run now, schedule, explain usage, why a match, and pause/stop; a dated support matrix; then installation and
contributor internals. Commands are deterministic shortcuts and fallbacks, not the golden path.

The support matrix records harness and version, OS and architecture, scheduler, interactive and headless
coverage, tested exact primary and detail model IDs, structural or live status, and verification date.
Structural-only and expected-to-work tuples stay labeled; the design does not imply exhaustive live coverage.

On explicit request, a local privacy-safe support summary may contain only the build stamp, host-reported
harness and version, OS and architecture, schedule state, latest run health, internal error code, aggregate
agent-data calls, and nonsecret request IDs. It excludes preferences, job descriptions, match details, API
keys, auth headers, cursors, and environment dumps. Show the complete local summary before the user decides
whether to attach it to an issue. Never upload it, open an issue, or launch a browser automatically.

### Release and deferred classification

The lifecycle, usage-context, exact-model, runner, quick-onboarding, scheduling, and health/error phases are
release blockers, as are the README Quickstart/cookbook and dated support matrix. The local support-summary
helper is P2 tune work: implement it while the blocking path remains green, but do not hold the release solely
for it. Credential-safe authentication transport and update-reminder backoff are P3, explicitly non-release-
blocking follow-ups. A hosted docs site, web sandbox, and live demo are deliberate non-goals rather than
backlog defects. Offline structural coverage is exhaustive; live scheduler and connected-run evidence is
representative, separately authorized, and labeled without upgrading unexercised tuples to passes.

## Feature A — one canonical agent-data cost-impact protocol

### Scope

The protocol covers agent-data calls only. Model selection still follows a cost-conscious capability rule,
but this release neither estimates nor discusses model-compute spend.

At every proposed action, evaluate one observable predicate:

> Can this action increase expected agent-data calls now or in future recurring runs?

If yes, invoke the preview procedure before acting. If no, proceed normally. Put this branching in a
compact decision table rather than scattering ad hoc warnings through skills (AAS-FORM-07).

| Decision class | Examples | Required context | Consent |
|---|---|---|---|
| Deterministic persistent increase | enable a schedule; raise cadence; add or enable a query; add or enable a source | exact before/after first-page baseline per run and comparison period; variable-call categories | explicit confirmation before config or scheduler write |
| Variable-yield increase | broaden keywords, location, or freshness; raise `queries[].limit`; increase review depth or pagination | stable known baseline plus the reason detail, continuation, or retry calls may rise; an exact bound only when the contract proves one | explicit confirmation for a saved increase; one-off scope rules below |
| One-off metered action | first sample run; requested fresh run; scheduling canary | current first-page baseline plus variable-call categories | an explicit ordinary run request is consent; a materially broader scope still confirms |
| Neutral or decreasing | disable a query/source; lower cadence/depth; narrow a search; change primary/detail model when no canary is required; change parallelism | no cost warning | apply and report normally |

This table is exhaustive for the currently shipped levers. A future lever joins it when it changes fixed
call count or can increase result-dependent detail/continuation work. Merely changing concurrency or model
identity does not change agent-data call count; a required repair canary is the separate metered action that
triggers this protocol.

### Canonical math

Use calls as the primary unit:

```text
first_page_calls_per_run = enabled_query_count * enabled_source_count
comparison_window_calls = first_page_calls_per_run * canonical_runs_in_window
```

The canonical cadence windows remain:

| Cadence | Labeled window | Runs |
|---|---:|---:|
| hourly | 30-day month | 720 |
| every 2 hours | 30-day month | 360 |
| every 6 hours | 30-day month | 120 |
| daily | 30-day month | 30 |
| weekly | 4 weeks | 4 |

Label the period result as a comparison, not a billing forecast. Search-page, full-posting, failed-attempt,
retry, and quota-rejection metering follow the dated producer contract in
`shared/references/agent-data-contract.md`; no consuming surface copies those volatile facts
(AAS-BOUND-03; AAS-FORM-06).

Every schedule preview adds one immediate canary run to the setup impact. A canary is not "free testing":
it follows the same agent-data metering contract as an ordinary run. If the first canary consumed metered
calls and another attempt is proposed, the retry is a new cost-driving decision and gets a fresh preview and
confirmation. A pre-meter failure does not consume that one-canary authorization.

### Preview shape

The canonical preview carries must-survive facts as slots rather than optional prose (AAS-FORM-14):

```text
Change: <before> -> <after>
Known baseline: <before calls/run> -> <after calls/run>
Recurring comparison: <before calls/window> -> <after calls/window>, or no recurring multiplier
Variable work: <detail / continuation / retry explanation, with a bound only if known>
Setup canary: <one immediate run, when creating or repairing a schedule>
Plan context: <free-tier/account-state branch below>
Price context: <optional dated pay-as-you-go equivalent; never an actual-charge claim>
```

Dollar equivalents are secondary and may appear only from the dated rate in the canonical contract. They
remain labeled equivalents unless live account metadata explicitly supplies an account-specific fact.

### Free-tier and account-state language

The canonical contract owns three distinct facts:

1. **Product availability:** agent-data offers a 100-metered-call-per-month free tier.
2. **Account entitlement:** unknown unless live CLI output identifies the current plan.
3. **Remaining allowance:** unknown unless live CLI output reports it.

Do not collapse product availability into an account claim (PSG-COMM-20).

| State | Required framing |
|---|---|
| CLI not installed / account not connected | Mention the free tier directly: the user can get started without purchasing calls. Do not narrate the obvious fact that account state is not visible before installation. |
| Authenticated, current CLI exposes no account metadata | Mention product free-tier availability without claiming the account's plan or remaining allowance. |
| Future authoritative account metadata is present | Prefer the live plan/allowance fields; the live source wins over the dated cache. Do not invent this branch's command or schema before release. |

A statement such as "plenty to support this run" requires a grounded comparison. Before account metadata
exists, qualify it: if the free tier applies, its allowance covers the known `<N>`-call baseline. Keep
variable detail, continuation, and retry calls visible. Never imply that the user is enrolled in the tier
or still has all 100 calls.

### Consent behavior

- A persistent increase gets a preview and explicit confirmation before config or scheduler state changes.
- A user who explicitly asks for a normal one-off run has already consented to that run. Show the context and
  proceed without a second question.
- A broader one-off request with no reliable ceiling, such as exhaustive traversal, previews and confirms.
- A saved setting is durable consent; scheduled/headless runs do not prompt.
- Schedule confirmation covers one canary and names it in the preview.
- Decreases and removals are immediate and do not require confirmation.

## Feature B — capability-gated recurring-job selection

### Eligibility gates

A scheduling mechanism qualifies only when every row passes:

| Gate | Requirement | Proof during setup |
|---|---|---|
| Unattended | fires with no active interactive session | capability inspection plus the scheduled-path canary |
| Canary-testable | supports a run-now action or a near-term fire through the registered job's actual invocation, permissions, and environment | fresh canary artifacts attributable to that scheduler fire |
| Primary-model preserving | binds the required recurring primary rather than silently taking an unrelated default | inspect the registered job definition |
| Local access | can reach workspace, agent-data credentials, and network | canary reaches agent-data and writes the workspace |
| Reversible | can be inspected, disabled, and removed | setup identifies the native inspection and removal actions before writing |

This is a hard eligibility gate because the failure is silent, recurring, and potentially metered
(AAS-AUTO-01/05). A manually executed interactive command does not count as a canary. A temporary
near-term scheduled fire does count when it uses the same registered job definition and execution context
as later fires.

### Selection order

1. Probe the harness-native recurring mechanism first.
2. If it passes every eligibility gate, use it.
3. If it fails even one gate, probe local OS mechanisms and choose one that passes all gates.
4. If multiple mechanisms pass, prefer native; otherwise prefer the lowest-footprint reversible local
   mechanism, with missed-wake recovery as a secondary advantage.
5. If none pass, do not create or claim a recurring job.

The rule is native-first among eligible options, not native-at-any-cost (AAS-PORT-03/04). Shared bodies
name actions and required capabilities, not harness tools. A running agent inspects its actual capability
surface and scheduler state rather than sniffing a host identity (AAS-LANG-01/03; AAS-PORT-03).

Cloud schedulers remain ineligible because they cannot see the private local workspace or local agent-data
credentials. An in-session loop may be offered as a temporary monitor, explicitly labeled session-bound,
but it never receives `installed: true`.

### Setup lifecycle

1. Resolve the workspace, cadence, exact recurring primary model, exact configured detail model, and an
   eligible mechanism.
2. Calculate the cost preview, including one canary.
3. Show the exact machine change, model binding, cadence, removal path, and cost context.
4. Obtain scoped confirmation.
5. Prefer staged registration: create the job paused/disabled, then invoke it through the scheduler. If the
   mechanism cannot stage but can trigger immediately, register and trigger without delay.
6. Verify registration and the execution canary.
7. Activate ordinary cadence and write the verified registry marker only after every proof is green.

For a newly created job, a failed canary disables or removes the partial registration before the agent
returns control. For a pre-existing job, the verification confirmation explains that failure will pause it;
the agent does not silently take ownership of user-created scheduler state (AAS-AUTO-02; AAS-PORT-05).

### Canary proof

Both proof layers are required:

1. **Registration:** the job appears in the scheduler's own registry, with the expected workspace,
   invocation, cadence, and primary model.
2. **Execution:** a real scheduler fire produces a fresh `runs/<id>.json` and digest, reaches agent-data,
   writes the intended workspace, and ends with `run_health` other than `blocked`.

The canary runs with the scheduled job's permissions, environment, model, and non-interactive context —
not the creating session's more privileged context. The run record is the durable cross-harness outcome
signal; a trustworthy exit code is only additive (AAS-LANG-08).

If the canary fails:

- do not write `installed: true`;
- disable or remove a newly created partial job;
- report the observed registration or execution gap;
- show any machine-level fix before applying it;
- re-run only under the call-context rule above; and
- never end with "all set" or equivalent success language.

A new canary is required after changing mechanism, invocation, workspace, permission environment, or the
recurring primary model. A cadence-only in-place edit verifies registration but does not spend another
metered run when the invocation is unchanged.

## Feature C — model ownership at the correct layer

### Recurring primary

At schedule creation, resolve the exact model powering the creating session. Persist that model in the
scheduler's primary-model field and in the local scheduling record. If the user explicitly names another
primary model, that exact override wins.

"Inherit" means capture and persist the creator session's model at creation time. It does not mean omit a
model field and accept a mutable harness default. If the model cannot be discovered or the candidate
scheduler cannot preserve it, ask the user to name one or choose another eligible scheduler
(AAS-AUTO-07; PSG-ANTI-03).

No shared body or reference contains a concrete vendor model ID. The only concrete primary ID is local
runtime state resolved from the current session or the user's request.

### Detail model — choose once, then obey config

The configuration agent applies the model-selection rule once:

> For posting-fit judgment, choose the least powerful model available that can perform that judgment well,
> unless the user specifies another model.

Because the detail task produces a qualitative fit verdict, it is judgment rather than mechanical
extraction. The normal floor is a capable mid-tier reviewer; ambiguity or risk may justify a stronger model.
Cheap deterministic work remains in scripts or the primary context. This follows the subagent-driven
development phrasing: cheapen mechanics, never judgment, and use the least powerful model adequate for each
role (AAS-AUTO-11).

The agent then writes the **exact selected model identifier** to `search.detail_model`. From that point the
runner's rule is deliberately simpler:

> Read `search.detail_model` and use that exact model for every posting-detail dispatch.

The runner does not re-apply the selection heuristic, reinterpret a tier, or silently substitute another
model. The required slot lives in workspace config, not in the scheduler artifact. The scheduler owns only
the recurring primary.

If the host cannot execute a separately modeled subagent, setup writes the exact primary model as
`search.detail_model`; the runner performs detail judgments sequentially on that primary. If a later run
cannot execute the configured detail model, it surfaces `E-DETAIL-MODEL-UNAVAILABLE`. Where the host can
inspect its model roster, preflight this before metered calls; otherwise a refused first dispatch blocks the
run, accounts for calls already made, and makes no substitute judgment.

Changing `search.detail_model` affects the next run without rebuilding the scheduler. If a verified schedule
exists, it becomes unverified until a real scheduled-path canary proves the new detail-model binding.

### Local-state application of the model style rules

`AAS-LANG-04` rejects literal model IDs in harness-neutral shared prose because rosters churn. This design
keeps that prohibition: shipped skills and references state the selection rule with schematic slots. The
concrete ID is resolved from the user's current environment and stored only in their local config/registry,
where determinism across future headless runs is the purpose. That local runtime value is not a pack-authored
default or adapter table. Its volatility is handled by an unavailable-model error and an interactive refresh,
never by silent substitution (AAS-FORM-06; AAS-LANG-02/04).

## Configuration and registry schemas

### Workspace config version 2

Changing `search.detail_model` from a portable tier to an exact ID changes field semantics, so new
workspaces use config `version: 2`. The template carries no vendor literal; interactive setup must insert the
exact value before the first run. A missing, empty, placeholder, or unavailable value is a preflight error.

Conceptual completed shape:

```yaml
version: 2
search:
  detail_model: "<exact model selected during configuration>"
```

Version 1 remains read-compatible during migration:

- `fast | balanced | high | inherit` and legacy vendor-tier aliases keep their existing legacy meaning;
- a headless run may resolve the legacy selector for compatibility but never writes config;
- the run record marks `detail_model_origin: legacy_v1_selector`; and
- the next interactive home/configuration flow shows the concrete resolution and offers to persist it as
  version 2.

Migration is a user-visible config change because it fixes a concrete future model. On confirmation, write
the exact model and `version: 2` atomically while preserving comments and unrelated fields. New schedule
setup requires a completed version-2 config first. No automatic migration occurs inside a scheduled run.

### Verified scheduling record

The registry's scheduling object becomes:

```json
{
  "installed": true,
  "verified": true,
  "mechanism": "<scheduler token>",
  "scheduler_id": "<registered job id>",
  "workspace": "<absolute workspace path>",
  "cadence": "<configured cadence>",
  "set_at": "<UTC ISO>",
  "verified_at": "<UTC ISO>",
  "canary_run_id": "<run id>",
  "primary_model": "<exact model>",
  "primary_model_origin": "session_inheritance|user_override"
}
```

`installed: true` without `verified: true`, scheduler identity, `verified_at`, `canary_run_id`, and the
primary-model fields is legacy/unverified, not proof. Registry readers must not render it as a verified
recurring job.

Each run record adds `trigger: manual|scheduled|canary`, a scheduler id for scheduled/canary triggers, the
exact configured detail model and its origin, the exact primary model and its origin when observed, and the
lifecycle close state. Record a primary model only when the runtime exposes it as an observed or registered
fact; never reconstruct one from memory.

## Existing-state migration

Before creating a job, inspect the relevant native and OS scheduler registries for an existing job targeting
the active workspace. This prevents the new flow from duplicating an unrecorded job.

| Existing state | Home/setup behavior |
|---|---|
| no marker and no scheduler job | normal eligible-mechanism setup |
| scheduler job exists, marker absent | offer to inspect and adopt or replace it; canary before recording |
| marker says installed but lacks verification fields | label unverified; offer a consented canary and pause-on-failure behavior |
| `mechanism: loop` | label session-only monitor, never verified recurring; offer unattended replacement |
| verified marker and matching job exists | show active verified schedule; do not re-ask |
| verified marker but job missing/mismatched | show drift/action-needed; never claim active |

Existing jobs are not silently removed. If the user declines migration, preserve external state and keep the
home label honest. If they approve replacement, stop the old mechanism, install the eligible one, canary it,
then replace the marker.

## Named failures

Implementation adds two named outcomes to the canonical error table:

| Code | Trigger | User-visible recovery | Effect |
|---|---|---|---|
| `E-DETAIL-MODEL-UNAVAILABLE` | version-2 `search.detail_model` is missing, invalid, or cannot be executed in the current environment | open the interactive Job Search agent to choose and save an available exact detail model | halt before metered calls where detectable; otherwise halt before any substitute judgment and account for prior calls |
| `E-SCHEDULE-CANARY` | registration or the real scheduled-path execution proof fails | name the failed proof, leave the schedule unverified, and offer the exact consent-gated fix or another eligible mechanism | no verified marker; newly created partial job disabled/removed |

Both use cause + fix + effect, with an empty/failure path as deterministic as the happy path
(AAS-FORM-03/10; PSG-COMM-09/20).

## Files affected and style-guide anchors

Every implementation task touching a skill or reference must cite the corresponding rule IDs in its plan or
commit. The matrix is normative, not illustrative.

| Surface | Change | Primary anchors |
|---|---|---|
| `shared/references/agent-data-contract.md` | own the dated 100-calls/month free tier, metering, pricing, and future live-account precedence | AAS-BOUND-03; AAS-FORM-06; PSG-COMM-20 |
| `shared/references/internals.md` | canonical cost decision table, math, scheduler eligibility, selection, canary, and registry schema | AAS-AUTO-01/02/04/05; AAS-FORM-07/09; AAS-PORT-03/04/05/10; PSG-F-09/10 |
| `shared/references/conventions.md` | version-2 exact detail model, legacy compatibility, registry/run-record fields | AAS-AUTO-07/11; AAS-FORM-06/14; AAS-LANG-04 |
| `shared/references/parallelism.md` | configuration-time detail-model selection; direct config use at dispatch; sequential same-model fallback | AAS-AUTO-07/11; AAS-LANG-01/03; PSG-SUB-03/06 |
| `shared/references/run-lifecycle.md` | ordered run phases, append-only ledger, completion predicate, interruption recovery, activation, and local milestone ownership | AAS-PROC-03/04; AAS-FORM-08/09/14; PSG-INJ-03/04/05/11/14 |
| `shared/references/errors.md` | unavailable-model and failed-canary outcomes | AAS-FORM-03/10; PSG-COMM-09/20 |
| `shared/references/voice.md` | concise usage previews, incremental-result labels, and cause/fix user rendering without raw internal codes | PSG-COMM-01/04/09/10/11/18/20 |
| `skills/job-search/SKILL.md` | front-door stance: all cost levers use the canonical preview; verified schedule semantics | AAS-BOUND-03; PSG-COMM-09/20 |
| `skills/job-search/references/onboarding.md` | free-tier install framing, first-run preview, exact detail-model choice, eligible scheduler setup | AAS-AUTO-02/04/07/11; PSG-F-09/10; PSG-COMM-10/18/20 |
| `skills/job-search/references/home.md` | verified/unverified/loop/drift states; config and schedule migration actions | AAS-LANG-08; AAS-TEST-15; PSG-COMM-09/20 |
| `skills/job-search-agent/SKILL.md` | operator explanation for cost levers, exact model ownership, and eligible recurring jobs | AAS-BOUND-03; AAS-LANG-01/03; PSG-COMM-05/20 |
| `skills/job-search-agent/references/customization.md` | cost-aware query/source/cadence/depth edits; version-2 exact model changes | AAS-AUTO-02/04/07; AAS-FORM-07; PSG-F-09/10 |
| `skills/job-search-agent/references/scheduling-and-consent.md` | capability gate, native-first selection, costed canary, cleanup, and migration | AAS-AUTO-01/02/05; AAS-FORM-09/10; AAS-PORT-03/04/05/10; PSG-SUB-06 |
| `skills/job-search-run/SKILL.md` | version-aware preflight, exact `search.detail_model`, no substitution, model provenance | AAS-AUTO-07/11; AAS-TEST-04/12; PSG-COMM-09 |
| `templates/config.example.yaml` | version 2 without a hardcoded model; setup-owned exact-value insertion | AAS-FORM-03/06; AAS-LANG-02/04; PSG-ANTI-03 |
| `shared/scripts/mechanics/lifecycle-append.sh`, `shared/scripts/mechanics/lifecycle-fold.sh` | deterministic lifecycle append, validation, fold, and completion checks with a prose fallback | AAS-FORM-08/09/14; AAS-PORT-01 |
| `shared/scripts/mechanics/support-summary.sh` | optional whitelist-only local diagnostics with no upload side effect | PSG-SAFE-13/14/17; AAS-DIST-03/06 |
| affected skill evals, `tests/fake-scheduler`, and developer eval helpers | observable lifecycle, activation, cost, model, scheduler, canary, liveness, migration, and privacy effects | AAS-TEST-03/04/07/08/09/10/13/15 |
| `README.md`, onboarding/product/doctrine docs, `TESTING.md`, and `docs/QUALITY_SCORE.md` | natural-language Quickstart and cookbook, dated support matrix, lifecycle/model/scheduler/cost/error truth, and labeled evidence | PSG-F-10; PSG-COMM-04/05/06/07/09/20; AAS-BOUND-03 |
| `docs/design-docs/core-beliefs.md`, `docs/PRODUCT_SENSE.md`, `docs/INTERFACE.md`, `docs/RELIABILITY.md`, `docs/SECURITY.md` | broaden usage-context doctrine; narrow installed-schedule meaning; document exact model ownership and private support boundaries | PSG-F-10; PSG-COMM-09/20; PSG-SAFE-13/14/17; AAS-BOUND-03 |
| `docs/exec-plans/tech-debt-tracker.md` | close `TODO-USAGE-PREVIEW-LEVERS` when implementation and tests land | repository planning method |

## Test plan

### Deterministic tests and fake shims

Extend the free agent-data shim and add a fake scheduler surface so tests can inject capability families and
observe artifacts without changing the user's machine or spending calls (AAS-TEST-09).

- Cost math covers every cadence and before/after query/source combination.
- Variable-yield decisions never invent a total; exact bounded cases retain their bound.
- Free routes stay outside metered totals.
- The free-tier amount and period have one canonical literal home and consumers point to it.
- Config version 2 requires a non-empty exact detail model; version 1 remains read-compatible.
- Version-2 runs use the exact config value for every detail dispatch.
- Unavailable configured models never trigger a different model dispatch.
- Registry writes reject `installed: true` without all verification fields.
- Scheduler-state fixtures cover native eligible, native session-bound, native untestable, OS eligible, no
  eligible mechanism, unrecorded existing job, unverified marker, loop marker, and drifted verified marker.
- Canary fixtures prove the scheduler fired, not merely that the command runs interactively.
- Failed new-job canaries leave no active partial job and no verified marker.
- Lifecycle append/fold fixtures cover every ordered phase, posting state, attempt-accounting invariant,
  blocked/interrupted closure, compaction recovery, artifact-before-completion gate, and prohibited field.
- Fixed-time metrics fixtures prove timestamp ownership, write-once behavior, activation derivation, time to
  helpful work, first-match latency, and total-run duration without storing PII.
- Fake-clock schedule fixtures cover the 30-minute grace period, one and multiple missed fires, daylight-
  saving transitions, manual/canary attribution, recovery, and registration drift precedence.
- The privacy-safe support-summary fixture places every excluded secret beside allowed fields and proves the
  output is whitelist-only under both `sh` and `dash` where available.
- Documentation gates check the natural-language Quickstart, request cookbook, dated support matrix, and
  absence of `docs-private/` from installed artifacts.

### Behavioral evals

Assert observable effects rather than exact narration (AAS-TEST-03/04):

1. **Install context:** missing CLI → free-tier availability is mentioned; no unnecessary account-visibility
   caveat appears.
2. **Authenticated unknown account:** current CLI has no plan fields → product free-tier context plus an
   explicit unknown plan/allowance boundary; no account claim.
3. **First live run:** baseline and variable work appear before execution; the onboarding request does not
   trigger a redundant second confirmation.
4. **Persistent levers:** cadence, query, source, and depth increases preview and confirm; decreases do not.
5. **Yield levers:** broader query/freshness/limit changes explain variable detail work without a fake total.
6. **Native qualifies:** native passes every gate → native selected and no OS scheduler write.
7. **Native partially qualifies:** native passes only unattended or only canary-testable → eligible OS path
   selected.
8. **No eligible path:** no schedule, no marker, and no success claim.
9. **Primary inheritance:** registered primary equals the creating session's exact model; an explicit user
   override wins; no pack-authored literal appears.
10. **Detail configuration:** setup selects and writes one exact detail model; later runs use it directly.
11. **Canary green:** registration plus real scheduled fire → verified marker with the canary run id.
12. **Canary failure:** new job paused/removed, no marker, observed gap reported.
13. **Canary retry:** a metered failed canary gets a fresh call preview before another attempt; a pre-meter
    failure does not consume the authorized canary.
14. **Legacy config:** version 1 still runs; home offers a concrete version-2 migration; headless does not
    write config.
15. **Legacy schedule:** loop and unverified markers are never rendered as verified recurring jobs.
16. **Quick sketch:** invocation preferences or one short answer produces a provisional brief, derived
    searches, one confidence checkpoint, and a live run without optional setup questions.
17. **Relevant material:** resumes, cover letters, and prior-application notes remain evidence and never
    become instructions or preferences without user intent.
18. **Activation:** a relevant match is fully evaluated and shown with reasoning before activation is
    claimed; a zero-relevant or blocked run reports useful recovery without claiming activation.
19. **Incremental results:** interactive runs show the approved early tranche and continue through
    `reviewing_remaining`; scheduled and canary runs publish no partial output.
20. **Durable completion:** remaining work, in-flight work, unaccounted attempts, missing final artifacts,
    context compaction, and worker failures cannot produce a false complete claim.
21. **Refinement:** general, posting-specific, ambiguous, retrieval-changing, and in-flight feedback follow
    their distinct routes and preserve the recorded brief revision.
22. **Schedule handoff:** daily, custom, and decline paths produce one useful decision, one confirmation and
    canary on yes, and no recipe dump on decline.
23. **Schedule liveness:** registration drift, blocked, overdue, not-recently-observed, verified, unverified,
    session-only, and absent states render in the approved precedence from local evidence.
24. **Exact-model repair:** unavailable primary or detail models block substitution; one confirmed repair
    updates exact bindings, rolls back on failure, and restores verified status only after a green canary.
25. **Privacy-safe support:** only explicitly requested whitelist fields appear, the full summary is shown
    locally, and no upload, issue creation, or browser launch occurs automatically.

Run behavior-changing evals RED/GREEN and include no-guidance controls plus multi-repetition rates where the
assertion is stochastic (AAS-TEST-07/08/13).

### Live verification

Offline shims prove the decision logic but cannot establish a real scheduler contract. Separately authorized
acceptance runs must prove at least one harness-native eligible path and one OS-level path where those
capabilities are available. Each live run records:

- scheduler mechanism and inspected registration;
- creator-session and registered primary model;
- canary trigger path;
- canary run id and artifact timestamps;
- workspace-write and agent-data evidence; and
- cleanup evidence for one deliberately failed canary.
- local onboarding and run milestone timestamps with measured connected and cold-start time to helpful work;
  and
- support-matrix tuple details: harness/version, OS/architecture, scheduler, exact models, and verification
  date.

Any harness not exercised live stays explicitly labeled structural rather than live-verified
(AAS-TEST-10/15). Live acceptance is not part of a zero-cost merge gate and requires separate authorization
because its canary can meter calls.

## Rollout and compatibility

1. Ratify this DX addendum and record non-release-blocking authentication/update debt before runtime edits.
2. Land the durable lifecycle, completion predicate, local milestones, and deterministic append/fold checks
   before any UX claims that an early result will continue or that a run is complete.
3. Land the canonical usage-context protocol for every agent-data call-increasing lever.
4. Preserve version-1 passive/headless compatibility, then land version-2 exact model ownership, migration,
   rollback, and model-expiry repair before new setup emits version 2.
5. Drive the runner through lifecycle state, validate every detail envelope, add incremental interactive
   results, and make interrupted search restart honestly without cursor reuse.
6. Replace setup ceremony with the silent workspace, quick sketch, confidence checkpoint, activation gate,
   and scoped refinement routes.
7. Add the fake scheduler, capability selection, exact registry state, single schedule handoff, real-path
   canary, cleanup, and model-repair canary before home reports schedule health.
8. Derive liveness and user-safe errors from local evidence; retain raw classifications only in internal
   records and operator explanations.
9. Ship the natural-language Quickstart/cookbook and dated support matrix; add the privacy-safe support
   summary if blocking work remains green.
10. Run deterministic gates and repeated pressure evals, then perform separately authorized connected and
    scheduler live evidence with honest structural/live labels.
11. Close `TODO-USAGE-PREVIEW-LEVERS` only after source/frequency/query/depth evals pass, synchronize the
    release version once, verify a deterministic build, and exclude `docs-private/` and dev/eval assets.

Existing schedules are never bulk-disabled during release. Their home status becomes more honest, and any
replacement or pause follows scoped user consent. Existing version-1 workspaces keep running until an
interactive migration is accepted.

## Acceptance criteria

- Every currently shipped cost-increasing lever maps to the canonical decision table and an effect-based
  test; no adjacent skill carries its own formula or price.
- Connected setup reaches time to helpful work in under two minutes and cold setup in under five minutes in
  representative live evidence, or release remains blocked with the measured cause.
- Ordinary first use silently chooses `~/.job-search`, captures a quick sketch or invocation preferences,
  treats relevant material as evidence, and shows one provisional confidence checkpoint before live work.
- Activation is claimed only after a non-blocked run fully evaluates a posting and shows a relevant match
  with reasoning; zero-relevant, blocked, or not-yet-presented outcomes are not activated.
- Pre-install messaging mentions the free tier without the redundant account-visibility caveat.
- Authenticated unknown-account messaging never claims plan, balance, or remaining allowance.
- A recurring primary equals the creator session's exact model unless the user overrides it.
- A version-2 workspace contains one exact `search.detail_model`, and every detail dispatch uses it.
- Passive/version-1 headless paths never migrate; the confirmed version-2 path preserves unrelated config,
  backs up before replacement, and rolls back setup/canary failure before its first successful version-2 run.
- No model ID is hardcoded into shipped shared guidance or templates.
- Unavailable exact models never cause substitution, and a schedule changed by exact-model repair remains
  unverified until its registered execution path passes a fresh canary.
- Interactive early output is followed immediately by `reviewing_remaining`; no completion claim is
  possible until the lifecycle fold proves all selected work and attempts settled and final artifacts exist.
- General, posting-specific, ambiguous, retrieval-changing, and in-flight refinement each follow the
  approved routing without turning supplied evidence into preferences.
- Native scheduling is selected only when it is both unattended and canary-testable, plus the remaining
  eligibility gates.
- No recurring job receives `installed: true` without registration and a green scheduled-path canary.
- A failed canary leaves no newly created active job and no success claim.
- The schedule handoff is one daily/custom/not-now decision after activation; declining emits no recipe dump.
- Registration drift, blocked, overdue, not-recently-observed, verified, unverified, session-only, and absent
  schedule states remain distinguishable in the home view with the approved precedence and grace period.
- Local milestone metrics and the optional support summary contain only their explicit non-PII whitelists;
  support output is shown before any user-directed attachment and never uploaded automatically.
- README leads with the natural-language golden path, free-tier/preflight recovery, one early-results example,
  request cookbook, and a dated support matrix with honest structural/live labels.
- Deterministic tests, behavioral evals, doc lint, and repository tests pass; live gaps are labeled.
- `docs-private/`, tests, local eval evidence, and other developer-only assets are absent from the plugin
  artifact; credential-safe auth transport and reminder backoff remain explicitly non-release-blocking.

## Risks and trade-offs

- **Exact model IDs can expire.** Determinism is intentional: block and ask for an interactive refresh rather
  than silently changing quality or cost characteristics.
- **Version 2 adds migration work.** The semantic change is real; preserving version-1 read compatibility
  avoids breaking existing schedules while keeping the new contract unambiguous.
- **Canaries consume a run.** The preview makes that cost visible, and a real scheduled-path fire is the only
  proof that catches the original failure.
- **Some native schedulers will be rejected.** Native integration is valuable only when it satisfies the
  unattended and verification outcomes the user needs.

## Approved decisions and open questions

Approved in conversational design on 2026-07-16:

1. Cost context covers agent-data calls only.
2. Free-tier availability is included, with account-state claims gated on authoritative metadata.
3. Before installation, omit the obvious "I cannot see your account" caveat.
4. The recurring primary captures the model from the creating session unless the user overrides it.
5. Configuration time chooses one exact detail model; the runner always uses `search.detail_model`.
6. Native scheduling wins only when it is both unattended and canary-testable and passes the other gates.
7. A green canary is mandatory before a verified marker or success claim.
8. The detail-model semantic change uses config version 2 with version-1 read compatibility.

No design questions remain open. Implementation planning follows user review of this document.
