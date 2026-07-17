# Workspace conventions & file contracts
<!-- reference-resolution-marker:8f2a4c1e-single-home — this is the ONE canonical home; every skill reaches it in place. Asserted by tests/test_reference_resolution.py; do not remove. -->

The **workspace** (default the hidden `~/.job-search/`; an existing visible `~/job-search/` is **adopted**, not replaced — see `internals.md`) is PRIVATE per-user data — never committed to a public repo.

Durable run progression, completion, recovery, and local milestone evidence are owned by
[run-lifecycle.md](run-lifecycle.md), including the metrics document, ownership, activation, and duration
contracts. This file owns the workspace artifacts and final record shapes; it does not restate those
lifecycle contracts.

```
~/.job-search/
  config.yaml                # queries + schedule (human terms only; no score thresholds)
  preferences.md             # Job Preferences Brief — prose only
  resumes/master.md          # base resume; resumes/tailored/ for generated ones (Plan C)
  jobs.jsonl                 # append-only EVENT log; current state = fold by (source, source_id)
  runs/detail-model-binding.json # current private provenance for config's exact detail model
  runs/<run_id>.json         # per-run audit log
  reports/<date>-digest.md   # human digest per run
  .gitignore                 # deny-all (from templates/workspace.gitignore)
```
**Discovery & OS state:** skills never hard-code the workspace path — they find it with the Discovery
procedure in `internals.md` (registry → `~/.job-search/` → legacy `~/job-search/` → first-run). The registry
and the discovery/first-run/scheduling rules live in `internals.md`.

**Machine registry file (`config.json`).** The machine registry is a JSON file — `config.json` at the path
`internals.md` resolves (`$REG`) — not a workspace file, so it is not in the tree above. As an on-disk file
its contract is: valid JSON with `"version": 1`; every write is a **whole-file atomic replace** (temp file
then `mv` where no atomic writer exists) that **preserves every unknown key** it does not own; a
present-but-unparseable file is the corrupt-registry case (never guessed past). Its `scheduling` object holds
the recurring-run state machine — `installed`/`verified` booleans, `mechanism`/`scheduler_id`,
`workspace`/`cadence`/`set_at`, `verified_at`/`canary_run_id`, and the exact recurring primary model — whose
schema, field presence, and staging→post-canary transitions are single-homed in `internals.md` (the Registry
and Scheduling setup sections); this file does not restate them.

## config.yaml

An actual newly created workspace uses version 2 and is valid only after interactive setup has written one
nonempty exact live model identifier to `search.detail_model`. An exact identifier is a model the current
host can execute by that identifier; it is not a capability tier, an inheritance token, or a placeholder.

<!-- exact-model-contract:config-v2-fields -->
| Field | Owner | Presence | Value |
|---|---|---|---|
| `version` | `workspace_config` | `required` | `2` |
| `search.detail_model` | `workspace_config` | `required` | `nonempty_exact_live_model_identifier` |
<!-- /exact-model-contract:config-v2-fields -->

```yaml
version: 2
workspace:
  preferences_path: "preferences.md"
  master_resume_path: "resumes/master.md"
queries:
  - { id: "ai-eng-remote", keywords: "AI engineer", location: "United States", limit: 25, enabled: true }
search:
  sources: ["linkedin", "ashby"]  # ordered job sources every query runs against (the source enum is defined in agent-data-contract.md) — omit the key for this default; greenhouse/lever widen coverage across more company boards
  freshness: "past-2-weeks"  # any | past-week | past-2-weeks | past-month — recency window; resolves to a server-side published_on_or_after cutoff (client-side fallback if the echo is absent); default past-2-weeks
  # Setup inserts the required exact search.detail_model before writing a valid new workspace.
  # max_new_postings_per_run: 50  # optional: positive integer or "all"; omit for first-page coverage
  # parallel_detail_reads: true  # optional: approved use of parallel subagents for detail reads where the host supports them
schedule:
  frequency: "daily"         # hourly | every-2-hours | every-6-hours | daily | weekly — the cadence the schedule runs on (its cron mapping composed via `schedule-line.sh` — see `internals.md` → Scheduling setup)
  time: "08:00"              # HH:MM, honored when the active scheduler is wall-clock-based (an unattended cron/launchd schedule); ignored when it is interval-only (an in-session loop)
  timezone: "America/Los_Angeles"
notify:
  digest_path_template: "reports/{date}-digest.md"
  desktop_notify_on_block: true
```
The **`search` block** tunes the feed: `sources` is the ordered list of job sources each enabled query runs
against (order = presentation order in per-source counts). An absent key means `["linkedin", "ashby"]`. Tokens
outside the enum are dropped at preflight with a digest footnote (E-SOURCE-UNSUPPORTED), never a HALT.
Per-query source targeting is a known deferred knob — all queries run against all enabled sources. The runner
reads `sources` and never writes it. `freshness` is a recency window that resolves to a **`published_on_or_after` cutoff** the search API
applies server-side, with a client-side filter as fallback. A row's **effective publication date** is
the later of `published_at` and `posted_at`, using whichever is present (unknown only when both are
null); the window admits rows whose effective date is on or after the cutoff. `any` sends no cutoff (no
filter); `past-week` = today − 7 days; `past-2-weeks` = today − 14 days (the default); `past-month` =
today − 30 days. Those values are the persisted defaults — the cutoff is only a date, so an ad-hoc
recency the user names for a single run ("only postings published in the past day", "since June 1")
resolves to its own cutoff and overrides the saved default for that run, with no new enum value. The
runner sends the cutoff and echo-verifies `data.query.published_on_or_after`; where a deployment omits
the echo it filters client-side by the same effective date. Under an active window a row with no
effective date is dropped (server parity); with `any` nothing is dropped. `detail_model` is the exact model
identifier for the per-posting **fit verdict** — the judgment the detail read produces. In version 2,
setup resolves that model once and writes its exact live
identifier; every later posting-detail judgment obeys that stored value without tier interpretation or a
new selection decision. Workspace config is the sole authority for the exact detail model: the private
binding sidecar below is provenance evidence only and can never override `search.detail_model`. Config never
stores the recurring primary model or either model's provenance field.

<!-- exact-model-contract:legacy-v1-selectors -->
Historical version-1 workspaces may contain the selectors `fast`, `balanced`, `high`, or `inherit`.
Those tokens, plus the older `haiku` / `sonnet` / `opus` aliases, are legacy version-1 inputs only; none is a
valid version-2 `search.detail_model` value. This compatibility boundary does not authorize a headless run
to rewrite or migrate the workspace.
<!-- /exact-model-contract:legacy-v1-selectors -->

Run-record model fields contain exact executable identifiers, never a selector or indirection token. The
validator requires an already-trimmed value and compares that complete value, case-insensitively, with this
closed vocabulary; it does not
reject an exact identifier merely because one of these words is a substring (for example,
`claude-sonnet-4-5-20250929` remains an exact identifier).

<!-- exact-model-contract:forbidden-run-record-values -->
- `auto`
- `balanced`
- `default`
- `fast`
- `haiku`
- `high`
- `inherit`
- `latest`
- `opus`
- `quality`
- `sonnet`
<!-- /exact-model-contract:forbidden-run-record-values -->

A version-1 headless run recognizes that saved selector and uses the canonical resolver below. Resolve the
selector once for the run from the host's current roster; this is a bounded compatibility resolution, not a
new per-posting selection decision. Preserve the config bytes, never migrate in the runner, and record the
exact resolved model with `detail_model_origin:legacy_v1_selector`.

<!-- exact-model-contract:legacy-v1-runtime -->
| Policy | Decision |
|---|---|
| `selector_source` | `version_1.search.detail_model` |
| `fast` | `host_fast_tier_model` |
| `balanced` | `host_balanced_reviewer_floor_model` |
| `high` | `host_most_capable_tier_model` |
| `inherit` | `exact_primary_model` |
| `legacy_aliases` | `haiku=fast,sonnet=balanced,opus=high` |
| `config_effect` | `preserve_bytes_no_write_no_migration` |
| `run_model` | `exact_resolved_model` |
| `run_origin` | `legacy_v1_selector` |
<!-- /exact-model-contract:legacy-v1-runtime -->

The legacy origin is valid only after the host has resolved the saved selector to an exact model and
observed that exact model as executable. Unresolved compatibility input never authorizes guessing a model,
substituting a different model, changing config bytes, or recording `legacy_v1_selector`. The bounded
failure route below blocks and hands the workspace to interactive model repair; T3.3 owns that repair's
canonical user rendering, so this compatibility contract does not invent a new user-facing error code.

<!-- exact-model-contract:legacy-v1-fail-closed -->
| Condition | Decision |
|---|---|
| `missing_selector` | `block_preserve_bytes_route_interactive_repair` |
| `invalid_selector` | `block_preserve_bytes_route_interactive_repair` |
| `tier_roster_unavailable` | `block_preserve_bytes_route_interactive_repair` |
| `tier_resolution_unavailable` | `block_preserve_bytes_route_interactive_repair` |
| `inherit_primary_unknown` | `block_preserve_bytes_route_interactive_repair` |
| `exact_dispatch_unsupported` | `block_no_substitute_route_interactive_repair` |
| `exact_dispatch_refused` | `block_no_substitute_route_interactive_repair` |
| `legacy_origin` | `only_after_observed_executable_exact_resolution` |
| `failure_route_owner` | `t3_3_interactive_model_repair_no_new_user_facing_code` |
<!-- /exact-model-contract:legacy-v1-fail-closed -->

Passive compatibility is intentionally narrower than migration. Reading a version-1 workspace for the home
view and running an ordinary version-1 headless pass preserve the exact original `config.yaml` bytes and do
not create `runs/detail-model-binding.json`. A headless pass may resolve the saved selector once through the
bounded resolver above, but that observed exact runtime value is run evidence only; it is not permission to
rewrite config, create version-2 provenance, or substitute another model.

<!-- exact-model-contract:legacy-v1-passive-compatibility -->
| Policy | Decision |
|---|---|
| `home_read` | `preserve_exact_config_bytes` |
| `ordinary_headless_run` | `preserve_exact_config_bytes` |
| `binding_sidecar` | `do_not_create` |
| `runtime_resolution` | `resolve_once_to_observed_executable_exact_model` |
| `failure_behavior` | `preserve_bytes_fail_closed_no_guess_or_substitute` |
<!-- /exact-model-contract:legacy-v1-passive-compatibility -->

A version-2-required interactive action is the only migration trigger. The transaction, backup, rollback,
and commit-cutoff procedure is owned by `internals.md` under **Version-1 staged migration**; this file owns
only the passive compatibility boundary and the resulting version-2 config/sidecar shapes.

`parallel_detail_reads` is optional and records whether the user approved parallel subagents for detail
reads on hosts that require explicit authorization. Unset means interactive front-door flows may ask; `true`
means use parallel subagents where available; `false` means read details sequentially. The runner reads this
field but never writes it.

`search.max_new_postings_per_run` is an optional review-depth setting. Its accepted values and resolved
behavior are:

| Stored value | Resolved review scope |
|---|---|
| key omitted | `first_page`: fetch one page from each enabled query × enabled source and never follow a cursor |
| positive integer | `finite`: continue cursor-capable board streams until at most that many unique unseen real-world roles are selected for judgment, or eligible sources exhaust |
| exact string `"all"` | `all`: exhaust the currently traversable Ashby, Greenhouse, and Lever streams; LinkedIn remains one page |
| present `null`, zero, negative integer, float, numeric string, or any other token | invalid config: halt in preflight before any metered call, using E-BAD-CONFIG from `errors.md` |

Omission is the backward-compatible default; it does not prompt, write config, or add continuation calls.
The finite target bounds unique roles judged after known-id dedup and same-role merging, not page calls:
known and duplicate rows can require additional pages before the target settles. `queries[].limit` (1–100;
the API default is 20 when omitted and this template sets 25) remains the per-call page size for one
query/source request. This additive review-depth setting does not itself change a workspace's config major
or authorize migration. Conversational one-off
and saved-change recipes use the canonical action classes, call preview, and confirmation rules in
[Agent-data usage decisions](internals.md#agent-data-usage-decisions); this file owns only the stored values
and resolved review-scope behavior.

## runs/detail-model-binding.json — current private binding provenance

This whole-file JSON sidecar proves the provenance of the active workspace's current version-2 model
binding. It is local, non-PII, current-state evidence—not append history. `config.yaml` remains the sole
authority for which exact model to execute. A sidecar is canonical only when it is at this exact path under
the active workspace, has exactly the fields and value forms below, and its `detail_model` exactly equals
the active config's `search.detail_model`.

```json
{
  "version": 1,
  "binding_id": "binding-<locally generated lowercase UUID v4>",
  "detail_model": "<exact copy of config search.detail_model>",
  "detail_model_origin": "configured_auto|configured_user|repair",
  "bound_at": "<UTC ISO-8601 timestamp>"
}
```

<!-- exact-model-contract:binding-sidecar-fields -->
| Field | Owner | Presence | Value |
|---|---|---|---|
| `version` | `binding_sidecar` | `required` | `1` |
| `binding_id` | `binding_sidecar` | `required` | `fresh_locally_generated_identifier` |
| `detail_model` | `binding_sidecar` | `required` | `exact_copy_of_config_search.detail_model` |
| `detail_model_origin` | `binding_sidecar` | `required` | `binding_origin_enum` |
| `bound_at` | `binding_sidecar` | `required` | `utc_iso8601_timestamp` |
<!-- /exact-model-contract:binding-sidecar-fields -->

<!-- exact-model-contract:binding-sidecar-origins -->
| Origin | Meaning |
|---|---|
| `configured_auto` | `setup_selected_exact_model` |
| `configured_user` | `user_selected_exact_model` |
| `repair` | `repaired_exact_model` |
<!-- /exact-model-contract:binding-sidecar-origins -->

<!-- exact-model-contract:binding-sidecar-policy -->
| Policy | Decision |
|---|---|
| `path` | `runs/detail-model-binding.json` |
| `authority` | `config_search.detail_model` |
| `write_mode` | `atomic_whole_file_replace` |
| `write_on` | `every_model_binding_write_even_same_model` |
| `binding_id` | `fresh_on_every_write` |
| `history` | `current_only_not_append_history` |
| `pii` | `none` |
| `preflight_validation` | `canonical_active_workspace_exact_model_equality` |
| `run_record_copy` | `binding_id_and_origin` |
| `invalid_evidence` | `missing_malformed_or_mismatch_blocks_interactive_repair` |
| `prior_run_lookup` | `prohibited` |
| `t3_2_rollback` | `restore_config_and_sidecar_consistently` |
<!-- /exact-model-contract:binding-sidecar-policy -->

Every model-binding write—new setup, explicit user model selection, migration, or repair—builds a complete
replacement sidecar with a fresh locally generated `binding_id` and `bound_at`, even when the exact model
literal did not change, then atomically replaces the whole file. An unrelated config edit does not write the
sidecar: when the current sidecar is valid, preserve it byte-for-byte. A setup, migration, or other
model-binding config write is not runnable until both candidate files are valid and the replacements
succeed. T3.2 migration rollback must restore config and its matching sidecar consistently; this task does
not define the full migration flow.

`run_id` format: UTC timestamp `YYYY-MM-DDTHH-MM-SSZ` (hyphens, not colons, in the time component — safe as a filename on every platform). `<date>` for digests: `YYYY-MM-DD` (local tz).

Run-record readers enumerate `runs/` but accept only a complete filename matching
`YYYY-MM-DDTHH-MM-SSZ.json`; they also require the record's `run_id` to equal that filename stem. A broad
`runs/*.json` glob is not a run-record definition: it would admit the binding sidecar. Before a reader
surfaces or uses any candidate, it must apply the exact run_id, closed-ledger, record, and derived-digest
authority procedure in [run-lifecycle.md](run-lifecycle.md#artifact-authority-for-every-reader), using
`lifecycle-fold.sh`; filename shape alone is never terminal authority.

<!-- exact-model-contract:run-record-selection -->
| Policy | Decision |
|---|---|
| `candidate_path` | `runs/<run_id>.json` |
| `filename_filter` | `complete_name_matches_run_id_format` |
| `detail_model_binding_sidecar` | `excluded` |
| `hidden_lifecycle_or_scratch` | `excluded` |
<!-- /exact-model-contract:run-record-selection -->

## jobs.jsonl — append-only events (one JSON object per line)
Current state = fold by (**`source`**, **`source_id`**), last-write-wins per field (an event with no `source` (all pre-multi-source history, and any `status_changed` line that omits it) attaches by `source_id` alone — every legacy `evaluated` event already carries `source:"linkedin"`, so in practice only old `status_changed` lines lack it). Two event types:
```jsonc
{ "event":"evaluated", "ts":"<iso>", "run_id":"…", "source":"<the result row's source — copied, NEVER a hardcoded literal>", "source_id":"<source-native id — with source, the DEDUP KEY>",
  "query_id":"…", "title":"…", "company_name":"…", "location_display":"…", "salary_display":"<free text or empty string when absent>",
  "posted_at":"<iso or null when the source omits it>", "posted_at_extracted":"<iso date — OPTIONAL; only when the API posted_at was null and the JD states a date>", "same_role_as":"<source>:<source_id> — OPTIONAL; this row is the same real-world role as that primary row — parse by splitting on the FIRST colon only (e.g. same_role_as:"greenhouse:acme:7310605" → source "greenhouse", source_id "acme:7310605")>", "source_url":"…", "posting_id_at_seen":"jp_…", "detail_read":true,
  "relevant":true, "match":"strong|moderate|weak|null", "reasoning":"…",
  "dealbreakers_hit":[], "unknowns":[], "needs_human_check":false, "status":"new", "first_seen":"<iso>" }
{ "event":"status_changed", "ts":"<iso>", "source_id":"…", "status":"interested", "note":"…" }
```
Allowed `status`: `new | interested | applied | rejected | archived`.

**Event-line contract** (the operations below depend on it): one event per line; each line is a single-line
JSON object — never pretty-printed; every event carries a non-empty `"source_id"`; the literal key
`"source_id"` appears exactly once per line; every `evaluated` event carries a non-empty `"source"`; the
literal key `"source"` appears at most once per line (the per-source pre-filter grep depends on it, exactly as
the `"source_id"`-once rule protects the id extraction); `same_role_as` is a FLAT string — never a nested object (the `"source_id"`-appears-once rule is load-bearing for the grep extraction). Validate an event against this contract before appending it.

For current-run `evaluated` evidence, validation is strict rather than best-effort: `source_id` and
`source_url` must satisfy that source's row in the sole per-source table in
[agent-data-contract.md](agent-data-contract.md#per-source-quirks-one-table-the-only-per-source-contract-surface);
`posting_id_at_seen` matches the exact listing-scoped `jp_` plus 12 lowercase hexadecimal characters; and
each populated API date is a
real ISO date or timestamp. Ashby keeps API `posted_at:null`; LinkedIn, Greenhouse, and Lever require their
populated API value. `posted_at_extracted`, when present, is a nonempty real ISO calendar date and is valid
only when `posted_at` is null. `same_role_as`, when present, is a nonempty flat string that splits on the
first colon into a different canonical `(source, source-native source_id)` identity; an object, empty
string, invalid target, or self-reference is malformed. Across a current run, that target must be a present
primary event rather than another alias, and the alias and primary share the exact verdict fields
(`relevant`, `match`, `reasoning`, `dealbreakers_hit`, `unknowns`, and `needs_human_check`). Judgment string
arrays contain only nonempty strings. Every alias carries `detail_read:false`; the primary carries the
actual group result — `true` only when the group received a detail call, and `false` when summary evidence
settled it without one. Whenever a group contains a company-board row, its primary is the earliest such
board source in `search.sources` order; LinkedIn can be primary only when the group has no board row.
Recovery and every artifact reader reject rather than normalize a current-run event that violates any of
these invariants.

Operations — **run the shared script where a shell runtime exists, else follow the prose fallback**
(each script reproduces its fallback EXACTLY — pinned by `tests/test_mechanics_scripts.py`; the scripts
are the skills' own POSIX shell, no third-party dependency):
- **Known ids** — the dedup step, one per enabled source `S` (missing file = empty set).
  **Script:** `../scripts/mechanics/dedup.sh "$WS/jobs.jsonl" "$S"` — candidate `source_id`s on stdin,
  the NEW ones (not already recorded for `S`) on stdout; blank candidate lines (a null `source_id`) are
  skipped. **Prose fallback** — extract the known set with the pinned pipeline, then keep the candidates
  not in it:
  ```bash
  grep -E '"source"[[:space:]]*:[[:space:]]*"'"$S"'"' "$WS/jobs.jsonl" 2>/dev/null \
    | grep -o '"source_id"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4 | sort -u
  ```
  (The `"source"` key pattern cannot match `"source_id"`/`"source_url"` — the closing quote
  must follow immediately. Legacy history all carries `source:"linkedin"`, so the linkedin set
  matches every pre-multi-source event: no migration.)
- **Append one event** — validate the line against the event-line contract above, then append idempotently.
  **Script:** `../scripts/mechanics/event-log-append.sh "$WS/jobs.jsonl"` — the single-line event JSON on
  stdin (it validates, then appends; an `evaluated` event whose `(source, source_id)` is already recorded is
  a no-op). **Prose fallback** (validate first; the heredoc keeps quoting safe — apostrophes in `reasoning`
  are fine):
  ```bash
  cat >> "$WS/jobs.jsonl" <<'EOF'
  {"event":"evaluated","ts":"…","source":"…","source_id":"…",…}
  EOF
  ```
- **Current state (fold):** read `jobs.jsonl` and fold in-context — group events by (`source`, `source_id`) — an event with no `source` (all pre-multi-source history, and any `status_changed` line that omits it) attaches to its `source_id`'s record — later
  events override earlier per field, drop the `event` key. The pipeline view = the folded records tallied
  by `status` (plus the `needs_human_check: true` count). A folded record whose `same_role_as` names another present record is an ALIAS of it (match the reference by splitting `same_role_as` on the FIRST colon only — source, then a possibly-colon-bearing `source_id` — the same parse as its definition above) — count and display the pair as one (the pipeline view and home counts treat aliases as one role).

## runs/<run_id>.json — audit log
```jsonc
{ "run_id":"…", "started_at":"…", "completed_at":"…",
  "build": { "version":"0.4.0", "content_hash":"sha256:abcdef123456", "git_sha":"<short sha|unknown>" },
  "trigger":"manual|scheduled|canary",
  "scheduler_id":"<exact scheduler identifier; null for manual>",
  "primary_model":"<exact primary model for this run>",
  "primary_model_origin":"session_inheritance|user_override|repair_session",
  "status_probe":"ok|degraded|unreachable",
  "detail_model":"<exact model used for posting-detail judgment>",
  "detail_model_origin":"configured_auto|configured_user|legacy_v1_selector|repair",
  "detail_model_binding_id":"<current binding id; null for legacy version 1>",
  "queries":[ {
    "query_id":"…", "source":"<source>", "keywords":"…", "results_returned":25, "new":6,
    "pages_fetched":3, "rows_scanned":75, "unique_candidates":31, "selected_for_review":25,
    "has_more_at_stop":true,
    "stop_reason":"first_page_complete|target_reached|sources_exhausted|unpaginated|pagination_incomplete|source_failed",
    "attempts":3, "request_ids":["req_…"], "upstream_code":null, "retryable":null,
    "errors":[]
  } ],
  "sources_searched":["linkedin","ashby"], "sources_failed":[],
  "review_scope": {
    "mode":"first_page|finite|all", "target_new_postings":null,
    "origin":"default|one_off|saved",
    "outcome":"completed_first_pages|target_reached|sources_exhausted|incomplete"
  },
  "agent_data_usage": {
    "metered_calls":9,
    "unit_rate_usd":"<decimal unit rate used for this run>",
    "payg_equivalent_usd":"<decimal equivalent for this run>",
    "pricing_basis":"pay_as_you_go_equivalent",
    "by_operation": { "initial_search":4, "continuation_search":2, "detail_read":3 },
    "diagnostics": { "retry_attempts":1, "charged_failures":1, "quota_rejections":0, "free_route_calls":2 }
  },
  "pagination_metrics": {
    "first_page_rows":80, "continuation_rows":50, "known_rows":62,
    "same_run_cross_query_duplicate_rows":18, "cross_source_rows_merged":4,
    "unique_unseen_roles_first_pages":0, "unique_unseen_roles_continuations":28,
    "selected_roles_from_continuations":20,
    "deeper_coverage_nudge_eligible":true,
    "deeper_coverage_nudge_streams":["ai-eng-remote:ashby"]
  },
  "results_summary":{ "total_results":50, "new_postings":9, "evaluated":9, "detail_read":5,
                      "relevant":6, "strong":3, "moderate":2, "weak":1 },
  "errors":[ { "stage":"get-posting", "source_id":"…", "code":"upstream_unavailable",
               "retryable":true, "attempts":3, "final":"gave_up", "request_id":"…" } ],
  "lifecycle": { "phase":"preflight|searching|selection_settled|reviewing_initial_batch|early_results_shown|reviewing_remaining|finalizing|complete",
                 "close_state":"complete|blocked|interrupted",
                 "health":"healthy|partial|degraded|blocked" },
  "run_health":"healthy|partial|degraded|blocked" }
```

<!-- run-lifecycle-contract:run-record -->
| Field | Required value and authority |
|---|---|
| `trigger` | Exact `manual`, `scheduled`, or `canary` copied from canonical `run_started` evidence. |
| `scheduler_id` | JSON `null` for manual; exact nonsecret scheduler identifier copied from `run_started` for scheduled/canary. |
| `primary_model` | Exact observed primary model for this run; never an alias, tier, prefix, guess, or reconstructed value. |
| `primary_model_origin` | Exact `session_inheritance`, `user_override`, or `repair_session` evidence from the current invocation/scheduler binding. |
| `detail_model` | Exact bound or resolved detail model actually used for detail dispatch. |
| `detail_model_origin` | Exact current binding/resolution provenance defined below. |
| `detail_model_binding_id` | Exact current version-2 binding ID, or JSON `null` for version 1. |
| `lifecycle.phase` | Intended terminal folded phase: `complete` only for a record being validated immediately before a complete close. |
| `lifecycle.close_state` | Intended exact terminal close from [run-lifecycle.md](run-lifecycle.md); this consumer does not redefine its closed vocabulary. |
| `lifecycle.health` | Exact final `run_health`; it never upgrades a partial/degraded/blocked run. |
<!-- /run-lifecycle-contract:run-record -->

Every ledger-started run carries trigger, scheduler, primary-model, and lifecycle evidence above. Validate
trigger/scheduler consistency and current exact primary evidence before ledger creation; invalid or
unobservable attribution is rejected before mutable or metered work rather than normalized or guessed. The
existing narrow pre-binding blocked-artifact exception in `errors.md` may keep the three detail-model fields
null because no exact executable detail binding was established; it does not permit guessing. Outside that
bounded exception, all model fields are required.

Final artifact validation is strict and fail-closed: require every documented top-level and nested field,
its exact JSON type, every closed enum, canonical timestamp/build structure, nonnegative integer metrics,
and all documented cross-field invariants. In particular trigger/scheduler pairing, detail binding/origin,
usage sums, result-band sums, review-mode target rules, lifecycle phase/close/health, and top-level
`run_health` must agree. A preflight record cannot claim complete. The bounded pre-binding blocked exception
above is the only nullable model triple; omission, extra keys, guessed values, boolean-as-integer metrics,
or contradictory state fails validation and cannot earn an artifact milestone.
When that exception's folded phase is `preflight`, it is a genuine zero-work record: queries and searched/
failed sources are empty; every usage, pagination, and result counter is zero; rate/equivalent values are
null; nudge evidence and attempt errors are empty; and review outcome is `incomplete`. A later exact-dispatch
failure may preserve producer-authoritative completed-attempt accounting only at its truthful later phase.

The ledger remains authoritative for completion. The coordinator writes the intended terminal run record
and exact digest, reads back and validates both, records their lifecycle milestones, and folds the ledger
before attempting `run_closed:complete`; neither artifact is displayed or published as complete while that
append is pending. If the complete-close append fails, rewrite and revalidate both artifacts to the truthful
`blocked` or `interrupted` state before attempting that noncomplete close. If even the fallback close cannot
be appended, leave the ledger open and surface the repaired noncomplete artifacts; never leave a visible
record or digest that claims complete without a matching complete ledger close.

<!-- exact-model-contract:run-record-fields -->
| Field | Owner | Presence | Value |
|---|---|---|---|
| `detail_model` | `run_record` | `required_after_binding_else_null_on_model_binding_block` | `exact_model_used_or_resolved` |
| `detail_model_origin` | `run_record` | `required_after_binding_else_null_on_model_binding_block` | `detail_model_origin_enum` |
| `detail_model_binding_id` | `run_record` | `required_after_binding_else_null_on_model_binding_block` | `current_binding_id_or_null_for_legacy_v1` |
<!-- /exact-model-contract:run-record-fields -->

<!-- exact-model-contract:detail-origins -->
| Origin | Meaning |
|---|---|
| `configured_auto` | `setup_selected_exact_model` |
| `configured_user` | `user_selected_exact_model` |
| `legacy_v1_selector` | `legacy_version_1_resolution` |
| `repair` | `repaired_exact_model` |
<!-- /exact-model-contract:detail-origins -->

`detail_model_origin` is observed provenance, not a guess and not another config or registry field. For
version 2, the run producer accepts it only from the canonical binding sidecar in the active workspace,
after exact equality with config, and copies both that origin and the current `binding_id`. It never searches
prior run records for provenance—even a prior record with the same exact model could belong to an older
A→B→A binding. Version 1 has no sidecar: its binding id is `null`, and its legacy origin is recorded only
after the exact resolved model has been observed executable. Missing, malformed, or mismatched version-2
evidence blocks and routes to interactive model repair rather than inventing an origin.
The narrow blocked-artifact contract for a failure before binding is established lives in `errors.md`; all
three model fields are `null` in that blocked record rather than carrying a guessed or unobserved value.

<!-- exact-model-contract:detail-origin-evidence -->
| Policy | Decision |
|---|---|
| `writer` | `run_record_producer` |
| `accepted_evidence` | `canonical_active_workspace_binding_sidecar_or_observed_legacy_v1_resolution` |
| `version_2_copy` | `binding_id_and_origin_from_valid_sidecar` |
| `prior_run_evidence` | `prohibited_even_for_same_exact_model` |
| `missing_invalid_or_mismatched` | `block_and_route_interactive_model_repair` |
<!-- /exact-model-contract:detail-origin-evidence -->

`build.version` and `build.content_hash` are copied from the bundled `references/build-stamp.md`.
`build.git_sha` is best-effort: use `git -C <job-search root> rev-parse --short HEAD` only when the
executing Job Search plugin/source root is reliably known and that root has a `.git` context; otherwise
write `"unknown"`. Never derive `git_sha` from the caller/current working directory, because that can
record the user's project SHA instead of the Job Search build. The build object is required on every run
record written by `job-search-run`, including blocked records where a workspace exists.

Each `queries` item is one logical query/source stream. LinkedIn always uses `unpaginated` with
`has_more_at_stop:null`; no cursor-capable board may use `unpaginated`.
`has_more_at_stop` is boolean only when valid board pagination metadata makes it trustworthy; write `null`
for LinkedIn and for an incomplete pagination contract branch. `attempts` includes retries, and
`request_ids` retains the observable request provenance. Never write a cursor, decoded cursor payload, or
resumable continuation state to the stream or any other durable run-record field.

`review_scope.target_new_postings` is a positive integer only in `finite` mode and `null` otherwise.
`completed_first_pages` means every enabled stream completed its ordinary first-page branch;
`target_reached` means a finite selection target settled; `sources_exhausted` means every healthy eligible
stream ended; and any quota halt, source failure, or untrustworthy pagination branch makes the outcome
`incomplete` while preserving trustworthy rows already found. `origin` records whether the resolved choice
came from omission (`default`), a conversational one-run override (`one_off`), or config (`saved`).

The mode, outcome, and per-query stop evidence are one contract, not independent enums. LinkedIn's only
normal stop is `unpaginated` in every mode. For cursor-capable boards, apply this table exactly; the two
failure stops are permitted only with the overriding `incomplete` outcome, while an `incomplete` caused
later by quota or detail work may retain the mode's otherwise-normal query stops.

<!-- review-scope-contract:mode-outcome-stop-reason -->
| Mode | Non-incomplete outcome | Cursor-capable board stop evidence |
|---|---|---|
| `first_page` | `completed_first_pages` | every healthy query is `first_page_complete` |
| `finite` | `target_reached` | each healthy query is `target_reached` or `sources_exhausted`; the global selected count is exactly the finite target, including when a terminal board page supplies the final role |
| `finite` | `sources_exhausted` | every healthy query is `sources_exhausted` |
| `all` | `sources_exhausted` | every healthy query is `sources_exhausted` |
| any mode | `incomplete` | mode-normal stops plus `pagination_incomplete` or `source_failed`; every failure stop forces this outcome |
<!-- /review-scope-contract:mode-outcome-stop-reason -->

`completed_first_pages` is invalid outside `first_page`; `target_reached` is invalid outside `finite`;
`first_page` can never claim `target_reached` or `sources_exhausted`; and `all` can never claim
`completed_first_pages` or `target_reached`. A `source_failed` query's source appears exactly once in
`sources_failed`, and a non-incomplete outcome has no failed source or failure stop.
For finite mode, `target_reached` requires exactly `target_new_postings` selected unique roles;
`sources_exhausted` requires fewer than that target because outcome precedence would otherwise select
`target_reached`.

`agent_data_usage` is attempt-based. Its three `by_operation` counters classify each metered attempt exactly
once and must sum to `metered_calls`. Charged failures are a metered subset; retry attempts are diagnostic
and count every resolved attempt numbered greater than one even when that retry is unmetered. Quota
rejections and free-route calls are unmetered, so none of the diagnostic counters is added again. Store
`unit_rate_usd` and `payg_equivalent_usd` as decimal strings so historical arithmetic does not change after
a pricing update. The canonical dated metering rules and the rate used to derive these fields live only in
`agent-data-contract.md`; verify there rather than copying a rate into this contract.

`pagination_metrics` is local aggregate evidence, not telemetry. The deeper-coverage nudge is eligible only
in `first_page` mode with `completed_first_pages`, when `unique_unseen_roles_first_pages` is zero and at least one healthy cursor-capable stream returned
trustworthy `has_more:true`; `deeper_coverage_nudge_streams` lists those `<query_id>:<source>` identities and
is empty when ineligible. The runner records this evidence but never a shown marker; the home-view registry
marker is owned by `internals.md`.

### Pagination scratch lifecycle

First-page-only runs stay in context and create no scratch file. Immediately before the first continuation
call, create `runs/.pagination-<run_id>.jsonl` and hand the candidate pool between phases by that path. Write
only normalized posting summaries, query/source provenance, stream ownership, and merge bookkeeping—never a
cursor, a decoded payload, or a recovery checkpoint. Process the file in chunks of at most 100 lines; if a
larger pool remains, process another bounded chunk.

Remove the scratch file on every handled success or halt, including quota and partial-pagination exits. A
later run may delete stale files matching the exact `.pagination-<run_id>.jsonl` shape, but it must never
resume, replay, or recover continuation from one.

## preferences.md — prose brief (the model reads this; NO machine-readable contract, NO weights)
Sections: a 2–3 sentence **Summary**; **Must-haves / dealbreakers** (the binary filters); **Strong
preferences**; **Nice-to-haves**; **Red flags**. Each item is plain, observable language a reader could check
against a posting (e.g. "Remote within the US, or SF Bay Area onsite"). Two front-matter dates sit near the
top: `created_at:` (origin, preserved across updates) and `updated_at:` (last change). **Staleness is measured
from `updated_at`** (fall back to `created_at` for briefs written before `updated_at` existed).

## Relevance vocabulary (qualitative — NO numbers)
- **relevant**: boolean. False only when a must-have/dealbreaker is clearly violated.
- **match**: `strong` (hits must-haves + most strong preferences) | `moderate` (solid, some gaps) |
  `weak` (relevant but thin) | `null` (when not relevant).
- **unknowns**: brief criteria the posting doesn't address ("not stated"). NEVER counted against a posting.
- **needs_human_check**: true when a must-have/dealbreaker can't be confirmed from the posting. When true, write the specific question to resolve into the `reasoning` field (e.g. "Remote policy not stated — confirm before applying").
- **dealbreakers_hit**: list of must-haves/dealbreakers observably violated.

## Digest format (reports/<date>-digest.md)
```
# Job search digest — <date>
Run ID: <run_id>
Run health: healthy
9 new postings (6 LinkedIn · 3 Ashby) · 3 strong · 2 moderate · 1 weak · 3 filtered out · <n> searches · <m> detail reads
Agent-data usage: <N> metered calls this run · about $<payg_equivalent_usd> pay-as-you-go equivalent

## Strong matches
- **<title>** — <company> — <location>
  <one-line reasoning>.  [view](<source_url>)
  ⚠ confirm: <needs_human_check question, if any>

## Moderate matches
…

## Weak matches
…

## Filtered out (not relevant): 3
<one line each: title — company — why rejected>

<footnotes: stale detail links, partial failures, unidentifiable (null source_id) rows, brief-age nudge; first pass over a source (that source returned rows AND its known-ids set was empty at run start): `First pass over <Source> company boards — this batch can include older postings, since boards don't always state dates.`; per-source outage / unsupported / ignored (one line each — exact texts in `errors.md`)>
```
Strong first. Always show the exact run ID immediately after the heading, then the Run health line, counts,
and calls-first usage line. Load the verified rate from
`agent-data-contract.md` and render the stored exact decimal equivalent; the label states that it is context,
not an account balance or charge. If that canonical rate is unavailable or cannot be verified, use the
calls-only fallback `Agent-data usage: <N> metered calls this run` with no dollar clause. The parenthetical
per-source breakdown in the counts line appears ONLY when more than one source was searched; single-source
runs keep today's exact line.
The counts line counts result ROWS — a cross-source merged pair contributes to both its sources' breakdown
figures and to N; the collapse to one role shows in the merged entry itself and in the pipeline/home counts
(see the alias rule in §jobs.jsonl), never by shrinking N.
When more than one source was searched, append ` · <Source>` to the match meta line (e.g. `**<title>** —
<company> — <location> · Ashby`). A match whose `posted_at` was null carries a date mark on its reasoning
line: `posted ~<Mon D> (from posting text)` when the detail read extracted a JD-stated date, else `date not
stated`; add `— older than your freshness window` when the extracted date falls outside it (the entry still
lands in its verdict band: the read is already paid; relevance decides). A cross-source role merged via `same_role_as` renders as ONE entry whose link line shows every source — the **primary board source's canonical link first**, then `· [also on <Source>](<url>)` for each other row in `search.sources` order, e.g. `[view on company board](<primary board source_url>) · [also on LinkedIn](<linkedin source_url>)`. 'view' verbs, never 'apply'. (The primary is the board-source row that got the detail read — see the merge rule in `job-search-run` step 3; a `linkedin`-only group has no company-board link and shows just its LinkedIn link.) When the JD-stated date meaningfully precedes the other source's `posted_at`, one qualitative clause is allowed — 'on the company's board days before LinkedIn — early'; never a numeric freshness score. Run health is one of `healthy` |
`partial (<why>)` | `degraded (job sources flaky)` | `blocked (action needed)`, where `<why>` is one
of `N errors` (scattered per-query/per-posting errors) · `<source> unavailable` (one whole source lost this
run) · `<sourceA>, <sourceB> unavailable` (several — but not all — sources lost, each named in
`search.sources` order) · `all sources unavailable` (every enabled source lost). Precedence: name lost
source(s) over counting errors; `all sources unavailable` only when EVERY enabled source is lost, otherwise
list the specific ones. If blocked, replace the body with the named error's cause+fix (see `errors.md`).
