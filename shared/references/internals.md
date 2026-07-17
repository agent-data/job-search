# OS internals — registry, workspace discovery, config & scheduling

The "OS state" that survives across sessions so any skill finds the user's data identically. The host agent performs these procedures itself, with its own file-read/write and shell
tools, plus the exact shell lines below. Never hard-code or re-derive the
paths and precedence rules — follow the procedures as written; they are the contract every skill shares.
Durable run progression, safe recovery, completion, and local milestone evidence are owned by
[run-lifecycle.md](run-lifecycle.md), including the setup-record shape, timestamp writers, activation
predicate, and derived durations; this file does not restate those contracts.

## Registry (machine-managed OS state — JSON, not YAML)
Location (tests/evals redirect it via `$JOBSEARCH_OS_REGISTRY`):
```bash
REG="${JOBSEARCH_OS_REGISTRY:-${XDG_CONFIG_HOME:-${JOBSEARCH_OS_HOME:-$HOME}/.config}/job-search/config.json}"
```
i.e. `~/.config/job-search/config.json` by default. Schema:
```json
{ "version": 1,
  "active_workspace": "/Users/<u>/.job-search",
  "scheduling": {
    "installed": true, "mechanism": "loop", "set_at": "<iso>",
    "primary_model": "<exact live model identifier>",
    "primary_model_origin": "session_inheritance"
  },
  "deeper_coverage_nudges": {
    "/Users/<u>/.job-search": {
      "workspace": "/Users/<u>/.job-search",
      "shown_at": "<iso>",
      "outcome": "enabled|declined|deferred"
    }
  } }
```
The registry is machine state; the workspace's `config.yaml` stays the user-facing config.

The scheduling metadata owns the recurring primary-model binding. It never stores the posting-detail model
or its origin; those belong to workspace config and run records respectively.

<!-- exact-model-contract:scheduler-fields -->
| Field | Owner | Presence | Value |
|---|---|---|---|
| `primary_model` | `scheduler_registry` | `required_for_installed_schedule` | `nonempty_exact_live_model_identifier` |
| `primary_model_origin` | `scheduler_registry` | `required_for_installed_schedule` | `primary_model_origin_enum` |
<!-- /exact-model-contract:scheduler-fields -->

<!-- exact-model-contract:primary-origins -->
| Origin | Meaning |
|---|---|
| `session_inheritance` | `creating_session_exact_model` |
| `user_override` | `user_selected_exact_available_model` |
| `repair_session` | `repair_session_exact_model` |
<!-- /exact-model-contract:primary-origins -->

The resolved `$REG` is **the one and only registry**: evaluate the expression in Bash and use the path it
prints for every read and write. Never consult or touch any other location — in particular, when
`$JOBSEARCH_OS_REGISTRY` resolves it elsewhere, the default `~/.config/...` path is out of bounds entirely
(reading it can only mix two registries and confuse the result).

**Write rules (every structured-state whole-file write).** These govern the registry `config.json` and the
workspace `config.yaml` alike. Read the current file first (it may not exist), apply the change to the
parsed object, and write the **whole file back atomically** — a full replace in place, never a streamed,
redirected, or partial write that can truncate or interleave a structured-state file. Use your host's
whole-file write tool; where none is guaranteed-atomic, write to a temp file then `mv` it into place.
Appending one immutable line to the event log (`jobs.jsonl`) stays a legitimate shell `>>` append (a heredoc
keeps quoting safe). For the registry, write at the resolved `$REG` path; preserve any keys you don't own;
always keep `"version": 1`; store `active_workspace` as an absolute path (expand `~`); 2-space indent;
trailing newline; `mkdir -p` the parent directory first.
If the file exists but is not valid JSON, stop and tell the user (offer to rewrite it from the known
workspace) — never guess or silently fall through; guessing could switch workspaces. Only the **job-search**
front door (onboarding / adoption) and the scheduling flows write the registry; the headless runner never
does.

- **Record the active workspace** (adoption and onboarding both end here): merge
  `{"version": 1, "active_workspace": "<abs path>"}` per the write rules. This writes ONLY the registry; it
  never touches workspace files.
- **Read the scheduling marker:** the registry's `scheduling` object, defaulting to
  `{"installed": false, "mechanism": null, "set_at": null, "primary_model": null, "primary_model_origin": null}`
  when absent. Null model fields are valid only for an uninstalled marker.
- **Set the scheduling marker** (a recurring run was started): merge
  `"scheduling": {"installed": true, "mechanism": "<active mechanism>", "set_at": "<UTC ISO>", "primary_model": "<exact live model identifier>", "primary_model_origin": "<primary-model origin>"}` — record the
  mechanism actually used: a short token for the scheduler the agent bound the run to (an unattended
  `cron`/`launchd` schedule, or `loop` for the in-session fallback), plus the exact recurring primary model
  and one origin from the table above. Take the timestamp
  from `date -u +%Y-%m-%dT%H:%M:%S+00:00`.
- **Clear the scheduling marker** (turn-off): merge
  `"scheduling": {"installed": false, "mechanism": null, "set_at": null, "primary_model": null, "primary_model_origin": null}`.
- **Read the deeper-coverage nudge marker for workspace W:** expand W to its absolute path and look up that
  exact path in `deeper_coverage_nudges`; absence means no marker. The map is per absolute workspace, not
  global, and each marker's `workspace` value must equal its map key.
- **Set the deeper-coverage nudge marker:** only the **job-search home view**, after it actually displays the
  evidence-backed deeper-coverage nudge, merges
  `"deeper_coverage_nudges": {"<absolute W>": {"workspace":"<absolute W>", "shown_at":"<UTC ISO>", "outcome":"enabled|declined|deferred"}}`.
  Use `enabled` when the user enables deeper coverage, `declined` when they decline, and `deferred` when they
  leave it for later. The runner never writes this shown marker. A present marker suppresses later automatic
  nudges for that workspace, including after decline or deferral; the user can still request deeper coverage.
  Apply the ordinary registry write rules: merge into the current object, preserve every unknown registry
  key, and atomically replace the whole file.

## Workspace discovery & first-run detection
**Run the shared script where a shell runtime exists:** `../scripts/mechanics/workspace-discovery.sh` prints
three lines — `workspace=<abs path>`, `source=<registry|default|legacy|none>`, `first_run=<true|false>` —
reproducing the precedence below EXACTLY (pinned by `tests/test_mechanics_scripts.py`), honoring `$REG`/`$H`
as defined here. **Where there is no shell runtime, gather the facts and apply the precedence in-model.**

**Corrupt-registry guard (a caller MUST check this before trusting discovery's result).** The script
grep-extracts `active_workspace` and CANNOT detect a corrupt-but-non-grepable registry — a corrupt file
would make it silently fall through to default/first-run, the "guessing could switch workspaces" hazard the
Registry write-rules warn against. Robust JSON validation is out of the zero-dependency script's scope by
design, so this check lives in the caller's prose: before trusting the result, confirm the registry file (if
present) parses as JSON; a **present-but-unparseable** registry is the corrupt-registry case above — never
guess, never fall through. The **headless runner** maps it to **E-BAD-REGISTRY** (`errors.md`, HALT); the
**job-search** front door offers to rewrite it from the known workspace.

Gather the facts with one command, then apply the precedence rules:
```bash
REG="${JOBSEARCH_OS_REGISTRY:-${XDG_CONFIG_HOME:-${JOBSEARCH_OS_HOME:-$HOME}/.config}/job-search/config.json}"
H="${JOBSEARCH_OS_HOME:-$HOME}"
echo "registry: $REG"; cat "$REG" 2>/dev/null
test -f "$H/.job-search/config.yaml" && echo DEFAULT_HAS_CONFIG
test -f "$H/job-search/config.yaml"  && echo LEGACY_HAS_CONFIG
```
The printed `registry:` path is the one to use for any later registry write in this session.
First match decides — the result is a workspace path, a `source`, and whether this is a **first run**:
1. The registry parses and has a non-empty `active_workspace` W → workspace = W, source `registry`;
   first-run only if W has no `config.yaml` (check: `test -f "<W>/config.yaml"`). **The registry wins
   unconditionally — never fall through to the other candidates, even when W lacks `config.yaml`** (falling
   through could silently switch the user's workspace).
2. `DEFAULT_HAS_CONFIG` → workspace `$H/.job-search`, source `default`, not a first run.
3. `LEGACY_HAS_CONFIG` → workspace `$H/job-search`, source `legacy`, not a first run.
4. Otherwise **first run**: workspace = `$H/.job-search` (not yet created), source `none`.

First-run = no candidate workspace has a `config.yaml`. (`$JOBSEARCH_OS_HOME` redirects the home base for
tests/evals.)

## Never-clobber adoption
If discovery lands on the legacy workspace (or you otherwise find an existing workspace), **adopt** it:
record it as the active workspace in the registry (write rules above — only the registry is written). NEVER
overwrite an existing `config.yaml`, `preferences.md`, or `jobs.jsonl`; only additively create missing
`runs/` and `reports/`. Tell the user: "Found an existing workspace at <path> — using it."

## Agent-data usage decisions

The user sees conversation and durable job-search artifacts, not the call arithmetic the agent performs to
decide what to run. Give concise calls-first context at the decision point, then apply this table. Load the
current available free-tier and metering facts from
[agent-data-contract.md § Pricing and metering](agent-data-contract.md#pricing-and-metering); that dated
contract is the only owner of volatile tier and rate values.

Let `B = enabled_queries * enabled_sources`, counting only enabled queries and valid enabled sources after
the proposed change. `B` is the known ordinary first-page baseline for one run because every enabled query
targets every enabled source once. It is not a ceiling: continuation pages, full-posting detail reads,
failures currently marked metered, and retries currently marked metered can add calls. Never present an
uncertain addition as a maximum.

<!-- usage-context-contract:action-decisions -->
| Action family | Action class | Known first-page calls | Uncertain continuation/detail calls | Recurring multiplier | Free-tier fact useful | Confirmation rule |
|---|---|---|---|---|---|---|
| `first_live_run` | `one_off` | `B` | `continuation_plus_detail_calls` | `none` | `yes` | `request_is_scoped_consent` |
| `query_or_source_enable` | `persistent` | `post_change_B_and_delta` | `continuation_plus_detail_calls` | `saved_cadence_window` | `yes` | `confirm_before_write` |
| `cadence_increase` | `persistent` | `B_per_run` | `continuation_plus_detail_calls` | `current_vs_new_cadence_window` | `yes` | `confirm_before_write` |
| `saved_review_depth_increase` | `persistent` | `B` | `continuation_plus_detail_calls` | `saved_cadence_window` | `yes` | `confirm_before_write` |
| `one_off_review_depth_increase` | `one_off` | `B` | `continuation_plus_detail_calls` | `none` | `no` | `request_is_scoped_consent` |
| `retrieval_broadening_likely_detail_reads` | `persistent` | `B_or_post_change_B` | `detail_calls_likely_not_bounded` | `saved_cadence_window` | `yes` | `confirm_before_write` |
| `schedule_enable_with_canary` | `persistent` | `B_per_canary_and_run` | `continuation_plus_detail_calls` | `one_canary_plus_saved_cadence_window` | `yes` | `confirm_schedule_and_one_canary` |
| `metered_canary_retry_or_repair` | `retry_or_repair` | `B_per_canary_attempt` | `continuation_plus_detail_calls` | `approved_attempt_only` | `no` | `confirm_each_metered_canary_attempt` |
<!-- /usage-context-contract:action-decisions -->

Read the table tokens this way:

- `post_change_B_and_delta` means show both the proposed `B` and its increase from the current baseline.
  `B_or_post_change_B` uses the current baseline when the enabled query/source counts stay fixed and the
  proposed baseline when the broadening also changes either count.
- A `saved_cadence_window` multiplies the per-run context by the saved cadence's labeled comparison window
  below. `current_vs_new_cadence_window` shows both cadence multipliers. A schedule enablement includes one
  canary run plus the future saved-cadence comparison; the canary is not silently folded into the multiplier.
- `continuation_plus_detail_calls` and `detail_calls_likely_not_bounded` are explicitly uncertain. Explain
  which operations may add calls and why their number depends on returned rows, deduplication, pagination,
  and which postings merit detail reads. A finite review target bounds roles judged, not calls.
- `yes` in the free-tier column means the current available product-tier fact helps calibrate the decision;
  load it from the dated metering contract and state it after the known call count. `no` means omit it by
  default because it adds little to that scoped decision. Never describe an available tier as the user's
  plan, remaining allowance, or balance. Do not volunteer an account-visibility caveat when it adds no
  decision value.

These policy rows pin the cross-action behavior:

<!-- usage-context-contract:policy -->
| Policy | Decision |
|---|---|
| `baseline_formula` | `enabled_queries*enabled_sources` |
| `baseline_is_ceiling` | `false` |
| `one_off_request` | `scoped_consent_after_context` |
| `persistent_increase` | `confirm_before_write` |
| `metered_repair_or_retry_canary` | `confirm_each_attempt` |
| `scheduled_headless_run` | `consume_durable_saved_consent` |
| `neutral_or_decreasing_edit` | `quiet` |
| `model_or_concurrency_only_edit` | `quiet_unless_canary` |
| `first_live_context` | `one_or_two_sentences_calls_first_plus_available_free_tier` |
| `account_claims` | `never_infer_plan_or_balance` |
| `account_visibility_caveat` | `omit_when_no_decision_value` |
| `uncertain_additions` | `not_a_ceiling` |
<!-- /usage-context-contract:policy -->

For a one-off request, the request itself is scoped consent to run once. Give the row's concise context and
proceed without asking the user to repeat approval; do not write the one-off scope to config. A first live
run gets one or two sentences: lead with `B` calls, load and render the current available free-tier fact from
its dated canonical owner, and say that promising postings or continuation pages may add calls. Do not turn
first-run context into an account disclaimer.

For a persistent increase, preview the applicable row and ask for scoped confirmation before the atomic
config write or scheduler change. Enabling a schedule includes consent for its exact machine change and
exactly one real scheduled-path canary after the preview; a metered repair canary or any metered canary
retry needs a fresh scoped confirmation for that attempt. Once saved, an enabled query/source set, cadence,
review depth, retrieval setting, and verified schedule are durable consent: scheduled and other headless
runs consume those saved choices without prompting.

Neutral or decreasing edits are quiet: apply them without an agent-data warning or confirmation. A model
or concurrency-only edit is also quiet because it does not itself change agent-data calls; if applying it
requires a canary, classify that canary under the canary row and show its context. Store only outcome levers
in config—never introduce monetary-control fields.

## Config read/update recipes (conversational-first; config.yaml is YAML)
The user changes config by **chatting**; manual editing is an escape hatch. To apply a change, read
`<workspace>/config.yaml`, edit it minimally (preserve comments/structure), and write it back.

For a new version-2 workspace, setup resolves model bindings once before writing a valid config or creating
a verified schedule. Posting-fit evaluation is judgment, so the automatic choice is the least-powerful
available model that can perform that judgment well; an exact available model the user requests overrides
that default. If the host cannot assign a separate worker model, write the exact primary model as
`search.detail_model` and configure sequential detail judgments. The static template intentionally omits
the required key because it cannot know the live roster.

<!-- exact-model-contract:setup-policy -->
| Situation | Decision |
|---|---|
| `detail_model_default` | `least_powerful_available_model_that_performs_fit_judgment_well` |
| `detail_model_user_preference` | `exact_user_selected_available_model` |
| `separate_worker_model_unavailable` | `detail_model_equals_exact_primary_model_and_runs_sequentially` |
| `creating_session_primary_unknown` | `block_verified_schedule_until_user_selects_exact_available_model` |
<!-- /exact-model-contract:setup-policy -->

A version-2 write that establishes or changes the exact model binding also replaces the active workspace's
private `runs/detail-model-binding.json` using the canonical schema and policy in `conventions.md`. Treat
config as the sole exact-model authority and the sidecar as provenance evidence only. Before a model-binding
write, build and validate both complete candidates in memory; generate a fresh local binding id and
timestamp even when the model literal is unchanged. For setup or an explicit user model choice use
`configured_auto` or `configured_user`; a repair uses `repair`. Serialize the two whole-file atomic
replacements, and if either replacement fails, restore the prior pair (or leave a new workspace
non-runnable) and do not run.

An unrelated version-2 config edit, including a depth-only edit, does not write model-binding provenance.
Require the current sidecar to be valid, then preserve it byte-for-byte while atomically writing only the
config. Missing, malformed, or mismatched current evidence is not a writable baseline: route to interactive
model repair. Compatible version-1 edits preserve version 1 and do not create a sidecar. T3.2 must apply the
pair-consistency rule to migration rollback; this is not the full migration procedure.

- **Add a query:** append to `queries:` an item like
  `  - { id: "ml-platform-sf", keywords: "ML platform engineer", location: "San Francisco Bay Area", limit: 25, enabled: true }`
  When the user hasn't named keywords (onboarding, or a vague "add another search"), **derive** them from
  `preferences.md` — role/title + domain terms for `keywords`, the brief's location constraints for
  `location` — then **acknowledge** what you saved rather than asking them to pick.
- **Tune the feed (`search` block):** `search.freshness` narrows or widens the recency filter on
  `posted_at`/`published_at` (server-side via `published_on_or_after`, with a client-side fallback);
  version-2 `search.detail_model` is the nonempty exact live model identifier selected once by the setup
  policy above; the exact config schema and legacy version-1 boundary live in `conventions.md`.
  `search.parallel_detail_reads` is optional: unset
  means an interactive front-door flow may ask whether to use parallel subagents where the host requires
  explicit approval; `true` means the user approved; `false` means use sequential detail reads. Only
  conversational front-door flows write this preference; the headless runner reads it and never changes config.
  `queries[].limit` is the per-query feed size (its range and default live in `conventions.md`).
- **Choose job sources:** set `search.sources` — an ordered list from the contract's source enum
  (see `agent-data-contract.md`); omit the key for the default `["linkedin", "ashby"]`. The default is
  `["linkedin", "ashby"]`; add `"greenhouse"` and/or `"lever"` to search more public company boards. One
  source failing never blocks the others.
  Only conversational flows write this; the headless runner reads it and never changes config.
- **Derive "remote" into the query:** `search-jobs` has no remote flag, so when the brief requires remote (or
  rejects onsite-elsewhere), fold `remote` into the query `keywords` and/or set `location` to the brief's allowed
  geographies — otherwise the feed fills with onsite roles the judge then filters out.
- **Choose one-off or saved review depth:** interpret the user's time scope before changing anything. The
  accepted `search.max_new_postings_per_run` values and exact run-record fields live in `conventions.md`;
  `queries[].limit` remains each query/source call's page size, not a run total.

  | User wording | Interpretation | Config write |
  |---|---|---|
  | “now,” “once,” “this run” | one-off finite, exhaustive, or first-page override | none |
  | “each run,” “from now on,” “every time” | saved setting | write the positive integer or exact `"all"` only after preview and confirmation |
  | ambiguous “scan everything” or depth request | default to one run and say that scope before running | none |
  | “go back to normal,” “use first-page coverage” | remove the saved key or use a one-off first-page override, according to the explicit time scope | remove immediately when saved |

  For any enablement/increase (`first_page → finite`, larger finite target, or `finite → all`), apply the
  corresponding one-off or saved row in **Agent-data usage decisions** above. The one-off request is scoped
  consent after the concise preview, so run it once without a second confirmation question. A saved increase
  needs explicit confirmation before the atomic config write. A finite target bounds unique roles judged
  rather than continuation calls, and `"all"` has no reliable call ceiling in advance.

  Use this single canonical saved-cadence comparison for the first-page baseline:

  | Saved cadence | Labeled comparison window | Runs in window | First-page comparison |
  |---|---:|---:|---:|
  | `hourly` | 30-day month | 720 | baseline × 720 |
  | `every-2-hours` | 30-day month | 360 | baseline × 360 |
  | `every-6-hours` | 30-day month | 120 | baseline × 120 |
  | `daily` | 30-day month | 30 | baseline × 30 |
  | `weekly` | 4 weeks | 4 | baseline × 4 |

  Label the result approximate because this is a comparison window, not a billing forecast. Use it for a
  saved increase; for a one-off, say the run does not change the recurring schedule and do not attach a
  recurring multiplier. If scheduling is off, say there is no recurring multiplier.

  A saved value is durable consent, so scheduled/headless runs use it without prompting. A one-off override
  records `review_scope.origin:one_off` in the run but never mutates config. Decreasing a finite target,
  changing `all → finite`, removing the key, or choosing a one-off first-page override is reversible and
  immediate; make that reduction without confirmation. Preserve the existing config major; this setting
  never performs a version-1 migration.
- **Explain my agent-data usage (read-only):** read only the workspace's `runs/<run_id>.json` records whose
  complete filenames match the run-id format in `conventions.md`, then explain actual
  `agent_data_usage` call totals, the recorded pay-as-you-go equivalent when present, the operation breakdown,
  and the configured outcome drivers (frequency, enabled sources/queries, and review mode). Use the decimal
  strings stored with each historical run; point to `agent-data-contract.md` for current canonical
  metering/pricing context. Do not write config or registry state, make an API call, infer a current balance or
  plan, or relabel the recorded equivalent as an actual charge.
- **Change frequency:** set `schedule.frequency` to one of `hourly | every-2-hours | every-6-hours | daily | weekly`
  (the cadence→cron mapping the active scheduler uses is composed in → Scheduling setup below).
- **Change run time:** set `schedule.time` (HH:MM, used for daily/weekly).
- New workspaces are `version: 2`. Never change an existing version-1 workspace as an incidental edit;
  migration is a separate explicit flow. NEVER add a score or weight field (philosophy).

## Version-1 staged migration

Migration is an interactive transaction, never a passive read or an ordinary headless-run side effect. It
starts only when the requested action requires a version-2 exact binding—especially creating a verified
schedule or changing the detail model. Resolve the exact detail model through the setup policy above before
asking. If resolution cannot produce an observed executable exact identifier, preserve the version-1 bytes,
use the bounded model-binding block in `errors.md`, and stop without a backup, sidecar, scheduler job, or
metered call. Never guess or substitute.

Fold migration into the requested action's one scoped confirmation. For scheduling, that confirmation names
the cadence and exact machine change, removal path, exact primary and detail model bindings, the version-1 to
version-2 config change, backup path pattern, calls-first schedule/canary context, one canary, and rollback
behavior. Do not add a separate migration prompt. A user override of the exact detail model uses
`configured_user`; the automatic setup-policy resolution uses `configured_auto`.

After confirmation, execute this transaction in order:

1. Read and retain the exact original `config.yaml` bytes. Record whether
   `runs/detail-model-binding.json` was absent; if an unexpected file exists, retain its exact bytes and
   treat that prior state as part of rollback rather than deleting or silently accepting it as v1 evidence.
2. Build the complete version-2 config candidate in memory. Preserve comments, ordering, formatting, and
   every unrelated field; replace only the required schema material (`version: 1` to `version: 2`) and the
   legacy selector with the resolved exact `search.detail_model`. Build a complete fresh matching binding
   sidecar per `conventions.md`, with a fresh id, current UTC timestamp, and the observed origin. Validate the
   complete parsed config, exact model value, complete sidecar shape, and exact equality before any active
   file changes. Honor the canonical config defaults: an omitted optional key such as `search.sources`
   remains omitted and resolves through its documented default; migration never materializes optional
   defaults merely to validate or upgrade the required schema/model fields. Validate every known optional
   value that is present against `conventions.md`, including query controls and
   `search.max_new_postings_per_run`; an example config is not a required-field schema.
3. Create `runs/config-backups/` if needed and save the exact original config bytes at
   `runs/config-backups/<UTC-safe-timestamp>-config-v1.yaml`. The timestamp uses UTC with filename-safe
   punctuation (hyphens rather than colons in its time component). Use an exclusive create. On collision,
   choose a fresh UTC-safe timestamp and try another exclusive create; never truncate, replace, or reuse an
   existing backup. If a distinct name cannot be allocated, stop before activation.
4. Activate config plus binding as one transaction: write each complete candidate to a same-directory temp
   file, atomically replace the two whole files, then immediately re-read and validate the active pair. A
   partial replacement is transaction failure, not a runnable intermediate state, and takes the same
   pre-cutoff rollback path as any other activation failure.
5. Perform the free preflight with the active candidate pair: local config/sidecar validation, CLI presence,
   authentication, preferences, and service status only. Make no metered search or detail call during this
   preflight. For schedule setup, register the new job disabled only after this preflight passes, then run the
   one approved canary through the requested setup path; do not enable or record the schedule as verified
   until its written run evidence qualifies below. A failed disabled-job registration is setup failure and
   takes the rollback path; registration alone is never success evidence.
6. If candidate validation, backup, activation, re-read, free preflight, setup, or canary fails before the
   cutoff, roll back the whole migration transaction. Atomically restore the exact original version-1 config
   bytes; restore an exact prior sidecar if one existed, otherwise remove the newly created binding sidecar;
   and remove the new scheduler job or leave it disabled when removal is unavailable. Re-read the restored
   state. Keep the non-clobbering backup as recovery evidence. Never report migration or scheduling success.

<!-- exact-model-contract:legacy-v1-migration-transaction -->
| Policy | Decision |
|---|---|
| `trigger` | `interactive_action_requires_version_2` |
| `confirmation` | `single_action_confirmation_includes_migration_no_separate_prompt` |
| `candidate` | `preserve_comments_and_unrelated_fields_replace_only_required_schema_and_model` |
| `candidate_validation` | `complete_v2_config_and_fresh_matching_binding_before_activation` |
| `candidate_defaults` | `preserve_optional_omission_do_not_materialize` |
| `activated_pair_identity` | `fresh_binding_id_and_exact_model_bound_to_migration_snapshot` |
| `backup_path` | `runs/config-backups/<utc-safe-timestamp>-config-v1.yaml` |
| `backup_write` | `exclusive_create_retry_fresh_timestamp_never_overwrite` |
| `activation` | `atomic_whole_file_replacements_one_config_binding_transaction` |
| `preflight` | `free_after_activation_before_canary_or_enable` |
| `setup_or_canary_failure` | `restore_exact_v1_bytes_and_prior_sidecar_state` |
| `register_failure` | `rollback_before_cutoff` |
| `partial_activation` | `rollback_before_cutoff` |
| `prior_sidecar_on_rollback` | `restore_exact_prior_bytes` |
| `new_binding_on_rollback` | `remove` |
| `new_scheduler_job_on_rollback` | `remove_or_disable` |
| `post_cutoff_failure` | `never_restore_stale_v1` |
<!-- /exact-model-contract:legacy-v1-migration-transaction -->

The mechanically checkable rollback cutoff is the first complete, nonblocked run record whose
`detail_model_binding_id` equals the fresh migration sidecar's binding id and whose `detail_model` equals the
active version-2 config and sidecar. That binding id and model must be the activated pair recorded by this
migration transaction's pre-activation snapshot; an unrelated valid version-2 run cannot commit this
migration. Fold the canonical lifecycle ledger from `run-lifecycle.md` and require
`can_complete=true`; do not infer completion from a process exit or run-record field alone. The eligible,
non-symlink complete run record and its exact required final digest must exist. A started run, blocked record,
missing completion timestamp, mismatched binding, `can_complete=false`, or incomplete/missing final artifact
does not qualify. Once qualifying evidence exists, the migration is committed: later failures may repair the
active version-2 pair, but must never resurrect the stale version-1 backup automatically. The canonical
ledger, matching run record, active config/sidecar, and exact digest are durable cutoff evidence. A persisted
cutoff marker is only an index into that evidence. Before every rollback decision, compare it with this
migration's activated-pair identity and re-fold and re-check all canonical evidence rather than trusting
process memory, persisted state, or a caller-supplied flag. Ignore a marker for a foreign migration and take
the ordinary pre-cutoff rollback path. If a marker matches this migration but its canonical evidence cannot
be verified, fail closed and do not restore version 1.

<!-- exact-model-contract:legacy-v1-rollback-cutoff -->
| Evidence | Decision |
|---|---|
| `qualifying_record` | `complete_nonblocked_run_with_matching_migration_binding_and_exact_model` |
| `started_run` | `not_qualifying` |
| `blocked_run` | `not_qualifying` |
| `incomplete_or_missing_artifacts` | `not_qualifying` |
| `lifecycle_gate` | `folded_run_ledger_can_complete_true` |
| `persistence` | `recheck_canonical_cutoff_artifacts_before_any_rollback` |
| `persisted_marker` | `index_only_revalidate_canonical_evidence` |
| `foreign_marker` | `ignore_for_this_migration_and_rollback` |
| `unverifiable_marker` | `fail_closed_never_restore_v1` |
| `effect` | `migration_committed_rollback_to_v1_forbidden` |
<!-- /exact-model-contract:legacy-v1-rollback-cutoff -->

## Exact-model repair

Interactive repair is the only place that may replace an unavailable or refused exact model. A headless
run detects the affected primary and/or detail slot, writes the bounded blocked artifacts when possible,
and stops without selecting, tier-resolving, guessing, or accepting an automatic host substitution. Route
the user to the interactive operator flow. When a schedule exists, repair begins only after that schedule
has been disabled and its registry state is unverified; expiry never leaves an unverified job running. A
workspace without a schedule may repair its detail binding directly and has no primary scheduler slot.

Resolve a complete candidate from live exact identifiers. Preserve every still-valid slot exactly as it is.
For an unavailable primary, prefer the repair session's exact primary and record `repair_session`; if that
identity cannot be observed, require the user to choose one exact available identifier. For an unavailable
detail model, choose the least-powerful available model adequate for fit judgment and record `repair`. An
explicit exact available user choice overrides either default. Reject an unknown, unavailable, or ambiguous
prefix instead of guessing what the user meant. An available slot with no explicit override preserves both
its identifier and origin. An explicit same-identifier primary choice is still a user override and may
rebind only its origin to `user_override`; it does not turn into implicit session inheritance. Before any
preview or receipt, require the disabled job's duplicated primary identifier and origin to equal the
canonical registry scheduling fields exactly. Reject a contradiction without normalizing or mutating either
surface. A same-identifier origin rebind is still a real scheduler change and the confirmation effects must
say that it updates the exact primary metadata.

<!-- exact-model-contract:exact-model-repair-candidate -->
| Situation | Decision |
|---|---|
| `valid_unchanged_slot` | `preserve_exact_value_and_state` |
| `primary_unavailable_default` | `repair_session_exact_model_origin_repair_session` |
| `primary_repair_session_unknown` | `require_exact_available_user_selection` |
| `detail_unavailable_default` | `least_powerful_available_adequate_judgment_model_origin_repair` |
| `user_override` | `exact_available_identifier_only` |
| `same_id_primary_user_override` | `allowed_origin_user_override` |
| `candidate_registry_job_baseline` | `exact_primary_model_and_origin_equality_or_reject_before_preview` |
| `origin_only_change_preview` | `update_exact_primary_scheduler_effect` |
| `unknown_unavailable_or_ambiguous` | `reject` |
| `roster_present_refused_slot` | `treat_as_unusable_for_that_slot_and_replace_exactly` |
| `transaction_authority` | `candidate_owned_one_use_exact_receipt_not_caller_models_or_origins` |
| `receipt_staleness` | `reject_consume_recompute_and_reconfirm` |
<!-- /exact-model-contract:exact-model-repair-candidate -->

Snapshot every affected surface. For a scheduled repair that means the exact config, detail-binding sidecar,
registry scheduling metadata and verification state, and scheduler job metadata. Preview both slots with
exact before/after values even when one is unchanged. Also show whether config or binding evidence will
change, the exact scheduler machine change and removal path, the disabled/unverified state during repair,
and the exact rollback effect. Give the canonical calls-first context for one real scheduled-path repair
canary. Model identity alone is neutral; the canary is the metered action. Ask one scoped confirmation that
covers this whole scheduled candidate, machine change, and exactly one canary—never separate model, config,
migration, scheduler, or canary prompts.

Carry that one rendered proposal into execution as one-use candidate authority bound to its own receipt id,
the workspace; exact slot values and origins; model availability; explicit overrides; scenario; config,
sidecar, registry, and job
snapshots; calls-first quantity and uncertainty; effects; rollback; and one canary. The candidate owns those
facts: transaction setup does not accept replacement model identifiers or origins from its caller. Consume
the authority only after the single confirmation. Any tamper or baseline/roster/scenario drift rejects and
consumes it, so the proposal must be recomputed and reconfirmed. The deterministic T3.3 fake host represents
this authority with a stateful one-use receipt and a deterministic SHA-256 payload check. That receipt is
development-fixture transaction evidence only—not a shipped runtime file format, security mechanism, or
cryptographic trust boundary.

Roster membership does not override observed exact-dispatch refusal. For candidate resolution, remove the
refused saved identifier from that slot's executable choices, preserve unaffected slots, reject explicit
reuse of the refused identifier, and bind the refused-slot facts into the one-use candidate authority. A
canary cannot commit unless every refused slot now carries a different exact executable identifier. The
unscheduled detail path applies the same slot-specific executable set: it rejects fresh provenance around
the same refused detail id and accepts only an exact executable alternate.

Without a schedule, only a detail binding can require repair. The user's explicit interactive repair request
is authority for this neutral model-only edit: show the exact detail before/after and pair-write effect, then
atomically replace the config plus fresh binding sidecar without cost context, an extra confirmation, or a
canary. Restore the exact pair if either replacement fails.

<!-- exact-model-contract:exact-model-repair-confirmation -->
| Policy | Decision |
|---|---|
| `applies` | `scheduled_repair` |
| `no_schedule` | `not_applicable_explicit_request_is_authority` |
| `count` | `one` |
| `model_identity` | `neutral` |
| `metered_action` | `repair_canary` |
| `primary_and_detail` | `exact_before_after_including_unchanged_slots` |
| `state_effects` | `scheduler_config_binding_machine_change_removal_and_rollback` |
| `canary_context` | `canonical_calls_first_preview` |
| `single_surface` | `candidate_receipt_owns_only_rendered_confirmation_preview` |
| `authority_consumption` | `after_one_confirmation_then_one_begin_attempt` |
<!-- /exact-model-contract:exact-model-repair-confirmation -->

After the scheduled-repair yes, stage the candidate while the scheduler remains disabled and the registry
remains unverified. A
primary-only repair changes only scheduler/registry model metadata and preserves a valid config and sidecar
byte-for-byte. Any detail-binding repair writes the version-2 config plus a complete fresh canonical sidecar
as one recoverable pair; generate a fresh binding id, timestamp, and `repair` origin even when an explicit
repair rewrites the same model literal. Validate the staged exact pair and scheduler metadata before the
canary. Execute one real run through the registered job's actual unattended invocation and require the same
green evidence as schedule setup. That green real-path canary is the only commit point: only then enable the
job and mark the registry verified.

If candidate setup, a partial write, scheduler activation, or the canary fails, automatically restore every
snapshotted surface exactly and ensure no proposed model remains active. The restored schedule stays in its
prior transaction state—on expiry repair that state is disabled and unverified. Explain the observed cause,
restoration, next step, and conversational fix. A scheduled retry is a new transaction with a fresh
calls-first preview and fresh scoped confirmation; the prior yes is consumed. An unscheduled pair-write
retry instead needs a fresh explicit interactive repair request, but remains neutral: no calls preview,
extra confirmation, or canary. The deterministic T3.3 fake-host flow tests these boundaries only and is not
evidence of general scheduler fidelity.

Post-confirmation setup, snapshot-baseline, activation, staged-evidence, or canary failure always restores
the exact snapshot, cancels the transaction, and consumes its authority. External restoration cannot revive
that transaction. For a detail write, store the exact newly generated binding id, timestamp, model, and
`repair` origin in the transaction; the canary requires byte-equivalent staged binding evidence and proves
both id and timestamp are fresh relative to the snapshot. Resolve the registry from the owned registry
contract. In particular, the unscheduled detail operation never accepts a caller-selected registry path and
rejects a missing owned location, malformed or ambiguous scheduling state, or any canonical installed
registry/job. Fresh timestamp means valid UTC and strictly chronologically newer than the snapshot—not
merely a different string—and the deterministic fixture generator remains monotonic across minute rollover.
Generate and validate the complete config replacement and binding evidence before mutating registry or job
state; malformed generator state or a parser/replacement mismatch takes the same restore/cancel/consume path.
Copy the candidate-bound scenario into transaction state and require it at activation and canary, so phase
behavior cannot change after confirmation. Store and validate exact staged config, sidecar, and registry
bytes plus the exact staged job value; a semantic-equivalent byte rewrite is not the staged evidence that
was authorized. Decode and type-check transaction-staged byte and object evidence without leaving the
shared invalid-evidence path: missing, wrong-type, undecodable, malformed, or mismatched staged evidence
restores the exact snapshot, cancels the transaction, and consumes its authority rather than exiting early.

<!-- exact-model-contract:exact-model-repair-transaction -->
| Phase | Decision |
|---|---|
| `snapshot` | `exact_affected_config_sidecar_and_when_present_registry_scheduler_verification_state` |
| `primary_only` | `preserve_valid_config_and_sidecar_bytes` |
| `detail_write` | `canonical_fresh_binding_even_when_literal_is_unchanged` |
| `schedule_exists` | `one_confirmation_and_green_real_path_canary_required` |
| `no_schedule_detail_repair` | `atomic_config_and_fresh_binding_pair_no_canary` |
| `no_schedule_confirmation` | `explicit_repair_request_is_neutral_authority` |
| `during_repair` | `scheduler_disabled_and_registry_unverified` |
| `setup_or_canary_failure` | `restore_exact_prior_transaction_state_no_proposed_model_active` |
| `post_authorization_failure` | `restore_cancel_and_consume_authority_no_resume` |
| `staged_binding_evidence` | `exact_generated_id_timestamp_model_origin_and_snapshot_freshness` |
| `phase_continuity` | `receipt_scenario_revalidated_at_activation_and_canary` |
| `staged_surface_derivatives` | `exact_config_sidecar_registry_bytes_and_job_value` |
| `malformed_staged_evidence` | `restore_cancel_and_consume_no_early_exit` |
| `registry_location` | `owned_canonical_contract_never_caller_selected` |
| `green_real_path_canary` | `only_commit_enable_and_verify` |
| `scheduled_failed_retry` | `fresh_calls_first_context_and_scoped_confirmation` |
| `unscheduled_failed_retry` | `fresh_explicit_request_no_calls_preview_or_confirmation` |
| `fixture_scope` | `t3_3_only_not_general_scheduler_fidelity` |
<!-- /exact-model-contract:exact-model-repair-transaction -->

Headless execution treats exact-dispatch refusal as an invalid exact binding even when roster membership
still lists the identifier. It blocks the affected primary, detail, or both slots, preserves completed
attempt accounting, never substitutes, and hands the user to the same interactive repair flow.

<!-- exact-model-contract:exact-model-repair-headless -->
| Situation | Decision |
|---|---|
| `unavailable_exact_identifier` | `block_affected_slots_no_substitution` |
| `roster_present_exact_dispatch_refused` | `block_primary_detail_or_both_no_substitution` |
| `completed_attempt_accounting` | `preserve` |
| `repair_owner` | `interactive_exact_model_repair` |
<!-- /exact-model-contract:exact-model-repair-headless -->

## Scheduling setup
**Advocate an unattended schedule** for the recurring run — one that keeps firing with **no interactive
session open** — on the host's or the OS's own scheduler that survives session-close (a `cron` or `launchd`
job, or the host's native unattended scheduler); where that scheduler can re-fire a run missed while the
machine slept, prefer it. The agent composes the schedule for its own host — there is no per-host recipe to
look up. Advocate it because an in-session loop stops the instant the session closes, so the overnight and
next-morning runs — the ones that matter most — silently never happen. When the host has **no** unattended
scheduler, or the user declines the machine change, offer an **in-session loop** — a recurring run driven
from inside an open session that installs nothing but runs **only while a session is open** — as the **named
fallback**. On either path, **cloud schedulers do not qualify**: a cloud runner can't see the local
`~/.job-search` workspace or the local agent-data auth, so a run there reaches neither the user's data nor
their credentials and produces nothing — the test any candidate scheduler must pass. (Full doctrine, consent
framing, and canary spec: the operator manual's `scheduling-and-consent.md`.)

The ACTIONS are the same across hosts; the agent binds each to its own host. Compose the cadence from
`schedule.frequency`. **Compose the five-field cron time expression with the shared script where a shell
runtime exists:** `../scripts/mechanics/schedule-line.sh <frequency> [HH:MM]`
prints `minute hour day-of-month month day-of-week` for the cadence; the host then wraps it with its own
command/launchd or interval translation. **Fallback (no shell runtime) — compose it directly:**
`hourly → 0 * * * *`; `every-2-hours → 0 */2 * * *`; `every-6-hours → 0 */6 * * *`;
`daily HH:MM → <m> <h> * * *`; `weekly HH:MM → <m> <h> * * 1` (**weekly day-of-week = Monday, `1`**).
`schedule.time` (`HH:MM`) is honored for daily/weekly and its **default is `08:00`**; strip a single leading
zero so cron gets `8`/`5`, not `08`/`05`. (Both soft-defaults — Monday for weekly, `08:00` for the time —
match the script and are pinned by `tests/test_mechanics_scripts.py`.) Offer scheduling as a yes/no; check
the scheduling marker first so you never re-ask. Before that choice, give the
`schedule_enable_with_canary` calls-first context from **Agent-data usage decisions**. On yes — after showing
the user the exact machine change — the scoped consent covers that change and one real scheduled-path
canary. Start the **unattended schedule** (the in-session loop only as the fallback above). ALWAYS also **compose the
recurring-run recipe and the one-off-run recipe for the host** and show both to the user verbatim, so they
can re-run the search on demand and stop or restart the schedule themselves.

Before creating the recurring job, resolve the creating session's exact primary model. The default binding
captures that exact value with origin `session_inheritance`; an explicit exact available model selected by
the user uses `user_override`; repair uses `repair_session`. “Inherit” never means an omitted or mutable
scheduler model. If the creating session's exact model cannot be determined, do not create or describe a
verified schedule until the user selects an exact available primary model. The scheduler registration and
the local scheduling metadata both carry the same exact primary-model binding; workspace config continues
to own only the exact posting-detail model.

**Verify before recording — the canary (mandatory).** Before recording the scheduling marker, verify the
schedule works. For the **unattended schedule**, use the **config-time canary**: **registration** (it appears
in the host scheduler's job list) + one **real run through the exact scheduled invocation** (its own
permissions/env, not this session's) proving a fresh `runs/<id>.json` (`run_health` ≠ `blocked`), agent-data
reached, and workspace written; on failure, diagnose and show the fix, then get fresh scoped confirmation
before any metered repair or retry canary; **never record the marker until the canary is green**. The
**in-session-loop fallback** (`mechanism: loop`) can satisfy neither canary
layer — it registers in no scheduler job list and its run *is* this session — so verify it differently:
confirm its **first in-session fire** leaves a fresh run record, then record the marker. Full consent-framed
flow: the operator manual's `scheduling-and-consent.md` §the canary. Only then set the scheduling marker
(write rules above — recording the mechanism actually used). After that proof succeeds, apply the
schedule-setup-owned local milestone procedure in [run-lifecycle.md](run-lifecycle.md); registration alone
does not satisfy that procedure.

To turn scheduling off, stop the active schedule, then clear the scheduling marker (write rules above — no
more stale `installed: true`).
