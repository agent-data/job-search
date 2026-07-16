# Run lifecycle, completion, recovery & local metrics

This is the single runtime contract for durable run progress, honest completion, safe recovery after context
loss, and local product-milestone evidence. The final run-record and digest shapes remain in
[conventions.md](conventions.md); workspace discovery remains in [internals.md](internals.md). Consumers
point here instead of restating the lifecycle schema.

## Durable ledger

<!-- lifecycle-contract:ledger -->
| Attribute | Contract value |
|---|---|
| `path` | `runs/.lifecycle-{run_id}.jsonl` |
| `write_mode` | `append_only` |
| `visibility` | `hidden` |
| `writer` | `coordinator_only` |
<!-- /lifecycle-contract:ledger -->

Every run creates the ledger above before mutable run work begins. Each append is one complete JSON Lines
event; existing lines are immutable, and a closed ledger accepts no later events. The ledger is the
authoritative resume record after context compaction or process loss, not the current conversation's
recollection.

The ledger stores restricted identifiers, timestamps, enums, and accounting state only. Its path is separate
from the pagination scratch described in [conventions.md](conventions.md#pagination-scratch-lifecycle), and
neither file substitutes for the other.

## Ordered phases

<!-- lifecycle-contract:phases -->
1. `preflight`
2. `searching`
3. `selection_settled`
4. `reviewing_initial_batch`
5. `early_results_shown`
6. `reviewing_remaining`
7. `finalizing`
8. `complete`
<!-- /lifecycle-contract:phases -->

The order is monotonic: a run never returns to an earlier phase. `selection_settled` means the selected set
is durable before posting review begins. An interactive run enters `early_results_shown` only after it has
actually presented fully evaluated results; a scheduled or canary run, or an interactive run with no ready
early result, may advance past that inapplicable presentation phase without claiming the milestone.
`complete` is not an ordinary progress transition: only a valid `run_closed` event with close state
`complete` establishes it.

`early_results_shown` is nonterminal. It does not mean the selected queue is exhausted, attempts are
accounted, or final artifacts exist. After an interactive early presentation, advance immediately to
`reviewing_remaining` and continue without another confirmation. Scheduled and canary runs remain quiet and
publish only from `finalizing`.

## Event and posting vocabulary

The event vocabulary is closed:

<!-- lifecycle-contract:events -->
- `run_started`
- `phase_changed`
- `posting_state`
- `attempt_started`
- `attempt_accounted`
- `brief_revision`
- `milestone`
- `run_closed`
<!-- /lifecycle-contract:events -->

- `run_started` establishes the run identity and initial `preflight` phase once.
- `phase_changed` records a valid forward phase transition other than the terminal `complete` transition.
- `posting_state` records the latest state for one selected `(source, source_id)` posting identity and the
  brief revision under which its evaluation began.
- `attempt_started` and `attempt_accounted` pair by restricted attempt identifier. Every started attempt,
  including a failed or retried attempt, requires exactly one accounting event before completion.
- `brief_revision` records a revision identifier, never the preferences text itself.
- `milestone` records a closed milestone token, never user-facing result content.
- `run_closed` is the final line and carries exactly one close state.

The posting-state vocabulary is closed:

<!-- lifecycle-contract:posting-states -->
- `queued`
- `evaluating`
- `evaluated`
- `presented`
- `terminally_skipped`
<!-- /lifecycle-contract:posting-states -->

`presented` is a flag-like evaluated state: a posting whose latest state is
`presented` counts in both `evaluated` and `presented`, so showing it can never make it look unevaluated.
`terminally_skipped` is reserved for a selected posting that will not be retried in this run; it is not a
cleanup shortcut for forcing the completion predicate.

<!-- lifecycle-contract:invariants -->
| Invariant | Contract value |
|---|---|
| `presented_counts_as_evaluated` | `true` |
| `presented_counts_as_presented` | `true` |
| `early_results_terminal` | `false` |
| `blocked_counts_as_complete` | `false` |
| `interrupted_counts_as_complete` | `false` |
<!-- /lifecycle-contract:invariants -->

Fold posting state last-write-wins per selected identity. Derive counters as follows:

- `selected` is the number of unique posting identities recorded by `posting_state`.
- `remaining` is the number whose latest state is `queued`.
- `in_flight` is the number whose latest state is `evaluating`.
- `evaluated` is the number whose latest state is `evaluated` or `presented`.
- `presented` is the number whose latest state is `presented`.
- `terminally_skipped` is the number whose latest state is `terminally_skipped`.

## Completion and close states

A run satisfies the completion contract only when every clause below is verified from the folded ledger and
filesystem:

<!-- lifecycle-contract:completion -->
| Completion clause | Required value |
|---|---|
| `remaining_zero` | `remaining=0` |
| `in_flight_zero` | `in_flight=0` |
| `selected_settled` | `selected=evaluated+terminally_skipped` |
| `all_started_attempts_accounted` | `each_attempt_started_has_exactly_one_attempt_accounted` |
| `final_run_record_written` | `runs/{run_id}.json` |
| `final_digest_written` | `reports/{ISO-date}-digest.md` |
| `ledger_closed_complete` | `closed_with_complete_state` |
<!-- /lifecycle-contract:completion -->

The first six clauses make a run ready to close. Only then may the coordinator append `run_closed` with
close state `complete`, which establishes the seventh clause. If any clause is unproved, completion is
unproved; do not close complete or claim success. In `selected_settled`, evaluated includes presented
postings. In `all_started_attempts_accounted`, every `attempt_started` has exactly one matching
`attempt_accounted`. The two final-artifact clauses require the named files to have been written.

The close-state vocabulary is closed:

<!-- lifecycle-contract:close-states -->
- `complete`
- `blocked`
- `interrupted`
<!-- /lifecycle-contract:close-states -->

- `complete` establishes phase `complete` after the completion predicate passes.
- `blocked` records a named condition that prevented the run from continuing safely.
- `interrupted` records a run that cannot safely continue or be reconstructed.

`blocked` and `interrupted` are honest terminal closing states, but neither is equivalent to `complete`.
They preserve the last reached working phase and any durable evaluated work. A closed ledger is never
reopened, regardless of close state.

## Safe recovery and non-resumable search state

After compaction or process loss, read and fold the ledger before applying this recovery map:

<!-- lifecycle-contract:recovery -->
| Ledger branch | Required action |
|---|---|
| `closed` | `do_not_append_or_replay` |
| `open_after_selection_settled` | `resume_queued_and_reconcile_evaluating` |
| `open_before_selection_settled` | `close_interrupted_and_restart_with_fresh_call_context` |
<!-- /lifecycle-contract:recovery -->

- For `closed`, treat only close state `complete` as completion; do not append or replay work for any close
  state.
- For `open_after_selection_settled`, preserve settled results and resume queued review. Reconcile every
  evaluating item and its attempt record explicitly; never assume an unresolved call was free, silently
  replay it, or mark it evaluated without evidence.
- For `open_before_selection_settled`, close the run `interrupted` when the valid ledger prefix permits that
  append, then start a fresh search with fresh call context. Do not infer a selected set from conversation
  memory or incomplete scratch.

Pagination cursors and other opaque API continuation tokens are non-resumable. Never persist, reconstruct,
or reuse them from the lifecycle ledger, final run record, digest, registry, jobs log, metrics, or pagination
scratch. A search that would require such a token restarts cleanly. The pagination scratch remains a separate,
explicitly non-resumable bounded candidate handoff; follow its deletion rules in
[conventions.md](conventions.md#pagination-scratch-lifecycle).

## Privacy boundary

The lifecycle ledger must exclude these content classes:

<!-- lifecycle-contract:persistence-prohibitions -->
- `api_keys` — API keys.
- `auth_headers` — auth headers.
- `environment_dumps` — environment dumps.
- `pagination_cursors` — pagination cursors.
- `opaque_api_continuation_tokens` — opaque API continuation tokens.
- `full_job_descriptions` — full job descriptions.
- `preferences_text` — preferences text.
- `match_prose` — match prose.
<!-- /lifecycle-contract:persistence-prohibitions -->

Do not place a secret or free-form user/job payload into an identifier field. A request identifier may be
stored only as restricted, nonsecret attempt provenance; it is not a continuation token.

The hidden filename is an organization detail, not an access-control boundary. The ledger stays inside the
private workspace protected by the workspace's deny-all source-control rules.

## Local metrics

Local milestone evidence has these storage properties:

<!-- lifecycle-contract:metric-properties -->
| Attribute | Contract value |
|---|---|
| `path` | `{workspace}/metrics.json` |
| `local_only` | `true` |
| `pii_allowed` | `false` |
| `telemetry_enabled` | `false` |
| `write_mode` | `atomic_whole_file` |
<!-- /lifecycle-contract:metric-properties -->

Its timestamp field vocabulary is closed:

<!-- lifecycle-contract:metric-timestamps -->
- `onboarding_started_at`
- `agent_data_ready_at`
- `first_live_call_at`
- `first_relevant_match_ready_at`
- `early_results_shown_at`
- `run_completed_at`
- `schedule_verified_at`
<!-- /lifecycle-contract:metric-timestamps -->

Metrics are local-only, no-PII product evidence, not telemetry. Never transmit them automatically or store
preferences, resumes, job or posting text, match content, credentials, auth material, environment dumps,
cursors, or other opaque continuation tokens in this file. Update metrics with an atomic whole-file write:
read the current JSON object, merge the owned timestamp, preserve fields owned by other flows, and atomically
replace the file. Never stream or append a partial JSON update.
