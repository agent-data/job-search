# Named errors (E-*) — cause + fix + what the user sees

Every failure is named internally and visible — no silent failures. The E-* table owns established canonical
errors. Exact-model binding failures use the narrow internal class below and the complete interactive repair
rendering that follows it; the internal class is never shown as a raw user code. The durable
guarantee for blocked runs is two **file-backed channels** when a writable workspace exists: the **blocked
digest** (cause + next interactive step) and the **home view** (reads `run_health` from the newest record
that passes [run-lifecycle.md](run-lifecycle.md) exact run_id + `lifecycle-fold.sh` + matching `closed=true`
authority) — both plain file writes that survive on any host. Every HALT or model-binding block with a
writable workspace therefore writes a `runs/<id>.json` blocked record. The named exception is **E-NO-CONFIG
/ first_run** with no workspace: there is no run record to write, and visibility comes from the next
**job-search** visit routing to onboarding. An attention-pull alert is *additional*, capability-gated by the
`notify.desktop_notify_on_block` knob: if your host has an attention-pull surface (desktop / terminal /
phone), fire one alert on a blocked run when the knob is set; otherwise skip it silently — the two file
channels still carry the failure.

Surface every outcome through the lifecycle-authorized written record — the record is **primary on every
harness**, the contract the home view reads — because a skill cannot set the host's exit code. An open
intended-complete file is never an outcome. Where a host provides a trustworthy exit code, that is an
additional signal only, never a replacement. The digest's "Run health" line carries one of the four
run-health states; their names, meanings, and the `<why>` breakdown are defined in `conventions.md` (the
digest "Run health" line).

## Internal classification vs. user rendering

Every named failure has two audiences kept strictly apart.

**Internal — retains the canonical code.** The `runs/<id>.json` blocked record stores the exact `E-*` code
(or the bounded internal class) in `error.code`/`error.class`; the **job-search-agent** operator manual may
name codes when troubleshooting; and the explicitly-requested, whitelist-only **local support summary**
([internals.md](internals.md#local-support-summary)) may include that same internal code, because it is an
operator/support diagnostic the user reviews in full before choosing to share it — not a normal chat,
digest, home, or notification surface. Those are the only places a raw code legitimately appears — for
whoever operates or diagnoses the agent, and for the durable record the home view reads. Classification must
never silently disappear from the record: a blocked record with no code is itself a failure.

**User-facing — structured, never the code.** Normal chat, the **digest**, a **desktop notification**, and
the **home** view render the same four-part structure and never the raw `E-*` code or an internal class
token:

1. **Cause** — the observed reason, in plain words (the "What the user sees" wording below).
2. **Preserved work** — what stayed unchanged or was restored (existing matches, completed judgments, config bytes).
3. **Next step** — what happens next, including the retry clause by verified schedule state below.
4. **Exact fix** — the concrete command, file, or conversational repair that clears it.

Interactive recovery performs the safe fix **conversationally** — the agent runs the repair in the
conversation (e.g. "repair the job-search models", "set up job search") rather than telling the user to
hand-edit a config file; hand-editing stays an always-available escape hatch, never a required step. The raw
`E-*` string never reaches any of these four surfaces — surface the plain cause+fix instead (`voice.md`).

<!-- exact-model-contract:model-binding-block -->
| Policy | Decision |
|---|---|
| `internal_class` | `detail_model_binding_unavailable` |
| `applies` | `v2_evidence_or_v1_resolution_or_exact_dispatch_failure` |
| `config_effect` | `preserve_bytes` |
| `run_effect` | `blocked_record_and_digest_when_workspace_writable` |
| `model_fields_before_binding` | `null` |
| `metering` | `preserve_completed_attempt_accounting` |
| `user_route` | `t3_3_interactive_model_repair` |
| `raw_user_code` | `none` |
<!-- /exact-model-contract:model-binding-block -->

The blocked run record stores `error.class:"detail_model_binding_unavailable"` internally. Before an exact
binding is established, `detail_model`, `detail_model_origin`, and `detail_model_binding_id` are `null`.
The digest and normal chat state the observed cause and route to interactive model repair without showing
that class token. Pre-meter failures record zero metered work; a refused/unsupported dispatch preserves all
completed-attempt accounting already observed. Render the exact unavailable or refused slot, what stayed
unchanged or was restored, and the next interactive step. Give a concrete conversational fix: say “repair
the job-search models” to accept the displayed exact defaults, or name one exact available model identifier.
Do not tell the user to edit an internal file or expose the internal class as if it were an `E-*` code.

If repair setup, activation, or canary failed after the user approved a candidate, name that observed phase
instead of repeating the initial unavailable/refused-slot cause. State which config, sidecar, registry, and
scheduler surfaces were restored, that no proposed model remains active, and whether the job is disabled and
unverified. Then offer the precise next step: fix the observed setup/canary cause and say “repair the
job-search models” again for a fresh proposal—and, when a schedule exists, fresh calls-first context plus
one new scoped confirmation. Never print the fixture/internal failure token in normal chat or a digest.

<!-- exact-model-contract:model-repair-rendering -->
| Policy | Decision |
|---|---|
| `initial_binding_failure` | `exact_unavailable_or_refused_slot` |
| `repair_transaction_failure` | `observed_setup_activation_or_canary_phase` |
| `safe_state` | `what_was_preserved_or_restored` |
| `next_step` | `interactive_exact_model_repair` |
| `exact_fix` | `conversational_available_model_selection_or_default` |
| `raw_internal_class` | `never_show` |
| `invented_e_code` | `never_show` |
<!-- /exact-model-contract:model-repair-rendering -->

Version-1 migration failures use a separate bounded internal class because they describe the transaction,
not the model-resolution failure above. Store the observed failed phase and safe diagnostic facts in the
operator record. Normal chat, home, digest, and notification state the observed cause, what was preserved or
restored, the next step, and the exact conversational fix; they never expose the internal class or invent an
`E-*` migration code. The rollback and post-success cutoff are owned by `internals.md` under **Version-1
staged migration**.

<!-- exact-model-contract:config-v1-migration-block -->
| Policy | Decision |
|---|---|
| `internal_class` | `config_v1_migration_failed` |
| `applies` | `candidate_backup_activation_preflight_setup_or_canary_failure` |
| `config_effect_before_cutoff` | `restore_exact_v1_transaction_state` |
| `config_effect_after_cutoff` | `preserve_active_v2_never_restore_stale_v1` |
| `run_effect` | `blocked_record_and_digest_when_workspace_writable` |
| `user_rendering` | `observed_cause_preserved_work_next_step_exact_fix` |
| `raw_user_code` | `none` |
<!-- /exact-model-contract:config-v1-migration-block -->

Scheduling setup fails closed with its own bounded class. A recurring schedule is **never** recorded until a
real scheduled-path canary proves it works (`internals.md` → Scheduling setup; the registry state machine
flips `installed`/`verified` only on a green canary). **E-SCHEDULE-CANARY** is the internal class for a setup
that could **not** be verified — no probed mechanism passed every eligibility gate, the disabled registration
failed, or the real scheduled-path canary was not green. Its effect is fail-closed: **no `installed` or
`verified` marker is written** and the schedule is not recorded, so nothing claims the search is scheduled.
The user is shown the exact observed gap (which eligibility gate failed · registration failed · the canary
was blocked) and the honest state — it is **not** scheduled — and, where a mechanism runs but cannot be
unattended-verified, the **session-only** in-session loop is offered as the named fallback. Like the
model-binding class, the raw `E-SCHEDULE-CANARY` token is never shown as a user-facing code; a blocked canary
run record may carry it internally. The canary **run execution and rollback** flow lives in the operator
manual's `scheduling-and-consent.md`; this entry owns only the named-failure surface and the no-marker
guarantee.

<!-- scheduling-contract:unverified-schedule -->
| Policy | Decision |
|---|---|
| `internal_class` | `E-SCHEDULE-CANARY` |
| `applies` | `no_eligible_mechanism_or_registration_or_canary_failure` |
| `registry_effect` | `no_installed_or_verified_marker_written` |
| `user_rendering` | `observed_gap_not_scheduled_session_only_fallback_where_available` |
| `raw_user_code` | `none` |
<!-- /scheduling-contract:unverified-schedule -->

| Code | When | What the user sees (cause + fix) | Run effect |
|---|---|---|---|
| **E-NO-AGENT-DATA** | the `agent-data` CLI is not found on PATH (prereq check, before `whoami`) | "The agent-data CLI isn't installed. Install it (`npm install -g agent-data`), then run `agent-data whoami` to authenticate. Nothing was pulled." | HALT, exit 1 |
| **E-NO-CONFIG** | `config.yaml` missing in the workspace | "No `config.yaml` found in <workspace>. Run the job-search skill (say 'set up job search') to set it up." | HALT, exit 1 |
| **E-NO-AUTH** | `agent-data whoami` shows `api_key_set:false` | "agent-data is not authenticated. Run `agent-data init --api-key <KEY> -y`, then verify with `agent-data whoami`. No data was pulled." | HALT, exit 1 |
| **E-CONFIG-VERSION** | `config.yaml` `version` major is newer than this code supports | "This `config.yaml` was written by a newer version. Update the job-search skills, or check `version:` in config." | HALT, exit 1 |
| **E-BAD-CONFIG** | `search.max_new_postings_per_run` is present but is not a positive integer or the exact string `"all"` | "`search.max_new_postings_per_run` is <safely rendered value>; it must be a positive whole number or `"all"`. Say “use normal first-page coverage” to remove it, or “review up to 50 new postings each run” to replace it. No metered calls were made." | HALT in preflight before any metered call; write the ordinary blocked artifacts when the workspace is writable |
| **E-LIFECYCLE-INCOMPLETE** | lifecycle fold/check proves remaining or in-flight postings, an unaccounted attempt, missing worker evidence, invalid ordering, compaction/interruption that cannot be reconciled safely, or a malformed/contradictory ledger | State the observed unfinished condition, that completed matches were kept, and whether the next safe action is a fresh run or an interactive diagnosis. Never call the run complete. | Stop new dispatch, let already-started producer attempts settle when possible, preserve every completed judgment and authoritative attempt result, then close `blocked` or `interrupted`; never force posting state or synthesize accounting to satisfy completion. |
| **E-FINAL-ARTIFACT** | the exact run record or digest cannot be written/read back/validated, or the final complete-close append fails | State that final results could not be safely finalized, that completed matches remain preserved, and that the next run or diagnosis can retry. Do not expose the internal file/ledger mechanism. | On this failure, never publish or display a completed state. Close `blocked` when the ledger remains appendable; after a failed complete-close append, first rewrite and revalidate both artifacts to truthful noncomplete lifecycle evidence, then attempt the noncomplete close. |
| **E-BAD-REGISTRY** | the machine-state registry (`$REG`, the `config.json` in `internals.md`) exists but is **not valid JSON**, so workspace discovery can't be trusted — the grep-extract that reads `active_workspace` can't detect a corrupt-but-non-grepable file | "Your job-search settings file is corrupted, so the active workspace can't be determined safely. Run the job-search skill (say 'set up job search') to repair it from your known workspace. Nothing was pulled." | HALT, exit 1; **NEVER** fall through to a default/legacy workspace (guessing could silently switch workspaces). Write the blocked record when a workspace is independently writable; when the corrupt registry leaves no trusted workspace, name the error and stop (as with E-NO-CONFIG / first_run) |
| **E-NO-PREFERENCES** | `preferences.md` missing/empty (the no-preferences run path) | "No Job Preferences Brief found. Run the job-preference-interview skill to build one, or point `config.yaml:workspace.preferences_path` at your own prose brief. Nothing was pulled." | HALT, exit 1 |
| **E-SERVICE-DOWN** | `status` route unreachable / non-200 | "The job-search service is unreachable right now. This is usually temporary." + the retry clause by verified schedule state (below). | HALT, exit 1, write "service down" digest |
| **E-BAD-QUERY** | `422 validation_error` / `400 validation_error` on a search (a bad param or `fields=`; `error.param` / `details[].loc` names it) | "Query '<id>' is invalid: <param from details[].loc>. Fix it in `config.yaml` under `queries`." | skip that query, continue |
| **E-UPSTREAM-STRETCH** | 2 consecutive retryable `503 upstream_unavailable`s on `search-jobs` **against the same source** (all retries exhausted) | "\<Source\> was unreachable this run (repeated upstream errors) — results from the other sources only." / all enabled sources stretched: "Job sources were unreachable this run (repeated upstream errors). Partial or no results." Both take the retry clause by verified schedule state (below). | stop searching that source, others continue; all stretched → stop searching, partial digest; Run health `partial (<lost source(s) unavailable — each named in search.sources order>)` / `partial (all sources unavailable)` when every enabled source is lost |
| **E-SOURCE-UNSUPPORTED** | the service answers `400 validation_error` with `error.param:"source"` (its message names the allowed sources), or preflight finds a `search.sources` token outside the contract's source enum (a config typo) | "This agent-data service doesn't recognize the '<source>' job source — searched <the others>. Remove it from `search.sources` in `config.yaml`, or update the agent-data service." | non-retryable; drop that source for the run, continue; Run health `partial (<source> unavailable)` |
| **E-SOURCE-IGNORED** | a 200 search response whose echoed `data.query.source` ≠ the requested source (an ABSENT echo counts as `linkedin`) — a legacy server silently ignoring `--source` | "The agent-data service predates source selection — only LinkedIn was searched. Update the service, or set `search.sources: ["linkedin"]` to match it." | skip that source's remaining queries this run; keep returned rows under their row-level `source` (they dedup against the genuine calls — no event poisoning); Run health `partial (<source> unavailable)` |
| **E-PAGINATION-INCOMPLETE** | a cursor-capable stream cannot continue through a trustworthy pagination-contract branch | "<Source>'s deeper results stopped early; <rows> postings already scanned were kept. The next run scans it again from the start (retry clause by verified schedule state below). If this repeats, ask me to diagnose it." | keep trustworthy rows; stop only the affected stream; continue the others; Run health is partial because depth is incomplete |
| **E-QUOTA** | agent-data rejects a call for quota/payment | "agent-data's API allowance has been reached, so this run cannot continue until calls are available. Check your account at https://agent-data.motie.dev/settings/billing. Your existing matches are unaffected." Then append exactly one run-usage branch defined below. | global HALT, exit 1; the rejected attempt is unmetered and prior trustworthy work remains intact |

## Retry language by verified schedule state

A temporary failure recovers on a later run, so its **next-step / retry clause** must say HOW that retry
happens — and that depends on the schedule's derived health
([internals.md](internals.md#schedule-health)), never an unchecked assumption that a schedule exists or is
firing as expected. It
applies to the recovering errors — **E-SERVICE-DOWN**, **E-UPSTREAM-STRETCH**, **E-PAGINATION-INCOMPLETE** —
and to any home/chat rendering of a recovering blocked run.

| Derived schedule state | Retry clause the user sees |
|---|---|
| **verified schedule** (`verified_running`) | name WHEN the next verified run retries — "the next scheduled run (\<cadence/time\>) will retry automatically." |
| **verified but not firing as expected** (`latest_run_blocked` · `needs_attention` · `not_recently_observed`) | do **not** promise an automatic next-run retry — the schedule is verified but is **not currently firing as expected**; name that plainly and point to the schedule-health repair path ([internals.md](internals.md#schedule-health)), e.g. "your schedule is verified but hasn't been firing as expected lately, so I can't promise the next run will retry on its own — check your schedule's health (say 'check my schedule') or run a search now to retry now." |
| **no schedule** (`absent`) | offer a **manual** retry, never a scheduled one — "no schedule is set, so run a search again whenever you like (say 'run a search now') and the next run will retry." |
| **unverified / session-only / drifted** (`unverified` · `session_only` · `registration_drift`) | say it **cannot be relied on** to retry on its own, then give the **exact repair path** — "your schedule isn't verified, so it can't be relied on to retry this automatically; say 'set up a schedule' to verify it (or 'run a search now' to retry now)." |

The reader that holds the derived state selects the branch: the **home** view and interactive **chat** derive
Schedule health live; a headless **digest** renders the branch for the schedule state observed at run time.
**Never promise an automatic scheduled retry when no verified schedule exists, or when a verified schedule
is not currently firing as expected** — that is the failure this clause prevents. **E-QUOTA** is not a temporary retry case: access must be restored first (its billing
recovery stands), so it takes no schedule-state retry clause.

## E-BAD-CONFIG value rendering and preflight

This code is separate from **E-CONFIG-VERSION**: use E-CONFIG-VERSION only for an unsupported newer
config major. E-BAD-CONFIG applies when `search.max_new_postings_per_run` is present as `null`, zero, a
negative integer, a float, a numeric string, a boolean, or any other value except a positive integer or the
exact string `"all"`.

Render the parsed invalid value before substituting it into the message:

1. Use compact JSON lexical forms: strings are double-quoted, quote/backslash characters are escaped, and
   line breaks, tabs, and every other control character are represented only by JSON escapes such as `\n`,
   `\t`, or `\u0001`. Never interpolate a raw control character into the digest or run record.
2. Cap the displayed representation at **80 Unicode characters, including an ellipsis and any outer
   quotes**. If a JSON-quoted string is longer, retain both quotes, keep the longest prefix of complete
   escaped units that fits, and put `…` immediately before the closing quote. For another JSON value, keep
   the longest safely escaped prefix that fits and end it with `…`.

Validate this value during free preflight and stop before the first metered attempt. If the workspace is
writable, produce the same blocked `runs/<id>.json` and blocked digest as other HALTs; record zero metered
calls and leave `jobs.jsonl` unchanged. Use the table's conversational remove/replace phrases so recovery
does not require hand-editing YAML.

## E-PAGINATION-INCOMPLETE branches and diagnostics

This error applies only after a cursor-capable stream has trustworthy rows but cannot safely establish its
next pagination state:

| Observed continuation branch | Effect |
|---|---|
| `data.pagination` is absent, or `has_more:true` has a missing/null cursor | keep the page's rows and stop that stream |
| a non-null cursor or ordered page signature repeats | keep all rows scanned so far and stop that stream |
| a fresh cursor receives a non-retryable cursor validation error | never restart at page one; keep prior rows and stop that stream |

Continue every unaffected query/source stream. Mark the run partial for incomplete depth, set the affected
stream's `stop_reason` to `pagination_incomplete`, and make the run-level review-scope outcome `incomplete`.
The partial-depth message takes precedence over any claim that all currently available results were
exhausted. The next run begins that stream again from its ordinary first page; it does not resume, because
cursors and recovery checkpoints are never persisted.

For each affected stream, store `query_id`, `source`, `pages_fetched`, `rows_scanned`, `request_ids`,
`upstream_code`, `retryable`, and `attempts`, along with the stop reason. Set `has_more_at_stop` to `null`
when pagination metadata is untrustworthy. Do not write a cursor, decoded cursor payload, or resumable state
to the run record, digest, scratch file, or diagnostic. Request IDs remain local diagnostic evidence; the
user-facing recovery is the message in the table.

## E-LIFECYCLE-INCOMPLETE compaction, restart, and non-resumable search

[run-lifecycle.md](run-lifecycle.md) owns the close states and the safe-recovery map; this section is only how
that outcome reaches the user. After context compaction or a process restart the coordinator trusts the folded
ledger, not its recollection. If the run had reached `selection_settled`, it resumes the queued review and
reconciles each `evaluating` posting from durable evidence — no restart, and no second metered call for an
attempt that already resolved; a genuinely unresolved attempt is treated as a possibly-consumed call, not a
free one. If selection had not settled, or a continuation could only continue by reusing a pagination cursor
that compaction dropped or the source expired, the run closes `interrupted` and the next pass is a fresh
search — a non-resumable cursor never resumes.

That fresh search is a new run, so it earns fresh calls-first cost context before its first metered attempt
(see [Agent-data usage decisions](internals.md#agent-data-usage-decisions)); it never assumes a prior,
possibly-consumed call was free. Surface the plain outcome: the run stopped before finishing, every completed
match was kept, and the next safe step is a fresh run (or an interactive diagnosis if it repeats). Never show
the raw `E-LIFECYCLE-INCOMPLETE` code, a cursor, an opaque continuation token, or any resume checkpoint in
chat, the digest, or the home view; cursors are never persisted in the lifecycle, run record, digest,
registry, or jobs artifacts, so there is nothing to resume.

## E-QUOTA usage and recovery

The billing link is the immediate recovery because access must be restored before the run can continue.
Do not lead with or proactively offer lower frequency, fewer sources, or reduced review depth merely because
quota occurred. If the user later asks how to make calls last, explain those outcome levers and their call
effects then. Any later call-increasing change or metered repair/retry canary follows
[Agent-data usage decisions](internals.md#agent-data-usage-decisions), including its scoped-confirmation
rule. Do not invent account balance, current plan, rollover, renewal, or live allowance facts.

Append exactly one of these calls-first sentences to the primary message:

- No prior attempt in this run was metered: `No calls were metered for this run.`
- One or more prior attempts were metered: `This run used <N> metered calls before the rejection. The rejected call was not metered.`

Derive `N` from this run's attempt evidence, never from a fixed precursor assumption. The current canonical
metering rule in `agent-data-contract.md` § **Pricing and metering** counts successful attempts and attempts
explicitly marked metered, including currently metered failures/retries; quota rejections and free routes do
not count. An explicit charged/metered status from agent-data overrides inference. The run record's
`agent_data_usage` counters must agree with the displayed `N`, and the quota rejection belongs only in the
unmetered diagnostic count.

Optional local context may follow the dynamic sentence. Read the current pay-as-you-go unit rate and top-up
amount from `agent-data-contract.md` at consumption time, then derive
`purchased_calls = floor(top_up_amount / unit_rate)`; this file deliberately owns none of those volatile
literals. Present the result only as a **pay-as-you-go purchase example**, after the actual run call count,
not as an account charge or account state.

For a similar-run estimate, enumerate only complete-name-matching local candidates and first apply
`run-lifecycle.md`'s exact closed-ledger artifact-authority procedure. Exclude a bare record, open/mismatched
ledger, or missing/mismatched fold-derived digest before comparison. From authoritative completed runs,
filter to the exact same enabled source list (including order), enabled query count, and review mode; take at
most the five most recent comparable records. Require at least three records and a positive median
`metered_calls`, then compute
`similar_runs = floor(purchased_calls / median_calls)`. Say how many comparable records supplied the median
(`last five` only when five exist), and warn that broader or deeper searches may use more. Omit the
similar-run estimate for review mode `all`, a zero median, or fewer than three comparable completed runs;
the derived pay-as-you-go purchase example may stand alone. Never use this history to claim a balance or
plan.

### Expected non-errors (footnotes, not failures)
- **Pair mismatch** — a `400 validation_error` (`retryable:false`) on `get-posting` whose `error.param` names `posting_id`/`source_url`: the `jp_`/`source_url` pair went stale (the source
  re-indexed it). Judge from the summary instead and add a digest footnote: "1 posting's detail link had expired;
  judged from its summary." Not an error.
- **Zero results — all already known:** reassuring, not an error — "No new postings — you've already seen all N of these."
- **Zero results — literally empty:** actionable — "Searches ran but returned 0 results. Broaden keywords in
  `config.yaml`, or check `agent-data call <listing> status`."

### Detecting E-QUOTA vs E-NO-AUTH from the CLI
Both surface as a non-zero `agent-data call`. Distinguish by: run `agent-data whoami` first (covers auth). If
auth is fine but an agent-data call fails with a payment/quota/limit signal in stderr (e.g. HTTP 402/429, or a
message mentioning quota/limit), treat as E-QUOTA. Anything else upstream is treated per its
`retryable` flag (a retryable 503 → retry; otherwise record + continue).
