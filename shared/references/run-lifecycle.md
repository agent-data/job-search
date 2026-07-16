# Run lifecycle, completion, recovery & local metrics

This is the single runtime contract for durable run progress, honest completion, safe recovery after context
loss, and local product-milestone evidence. The final run-record and digest shapes remain in
[conventions.md](conventions.md); workspace discovery remains in [internals.md](internals.md). Consumers
point here instead of restating the lifecycle schema.

## Durable ledger

Every run creates one hidden append-only JSON Lines ledger at `runs/.lifecycle-{run_id}.jsonl` before
mutable run work begins. The coordinator is its only writer. Each append is one complete event line; existing
lines are immutable, and a closed ledger accepts no later events. The ledger is the authoritative resume
record after context compaction or process loss, not the current conversation's recollection.

The ledger stores restricted identifiers, timestamps, enums, and accounting state only. Its path is separate
from the pagination scratch described in [conventions.md](conventions.md#pagination-scratch-lifecycle), and
neither file substitutes for the other.

## Ordered phases

1. `preflight`
2. `searching`
3. `selection_settled`
4. `reviewing_initial_batch`
5. `early_results_shown`
6. `reviewing_remaining`
7. `finalizing`
8. `complete`

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

The closed event vocabulary is `run_started`, `phase_changed`, `posting_state`, `attempt_started`,
`attempt_accounted`, `brief_revision`, `milestone`, and `run_closed`.

- `run_started` establishes the run identity and initial `preflight` phase once.
- `phase_changed` records a valid forward phase transition other than the terminal `complete` transition.
- `posting_state` records the latest state for one selected `(source, source_id)` posting identity and the
  brief revision under which its evaluation began.
- `attempt_started` and `attempt_accounted` pair by restricted attempt identifier. Every started attempt,
  including a failed or retried attempt, requires exactly one accounting event before completion.
- `brief_revision` records a revision identifier, never the preferences text itself.
- `milestone` records a closed milestone token, never user-facing result content.
- `run_closed` is the final line and carries exactly one close state.

The closed posting-state vocabulary is `queued`, `evaluating`, `evaluated`, `presented`, and
`terminally_skipped`. `presented` is a flag-like evaluated state: a posting whose latest state is
`presented` counts in both `evaluated` and `presented`, so showing it can never make it look unevaluated.
`terminally_skipped` is reserved for a selected posting that will not be retried in this run; it is not a
cleanup shortcut for forcing the completion predicate.

Fold posting state last-write-wins per selected identity. Derive counters as follows:

- `selected` is the number of unique posting identities recorded by `posting_state`.
- `remaining` is the number whose latest state is `queued`.
- `in_flight` is the number whose latest state is `evaluating`.
- `evaluated` is the number whose latest state is `evaluated` or `presented`.
- `presented` is the number whose latest state is `presented`.
- `terminally_skipped` is the number whose latest state is `terminally_skipped`.

## Completion and close states

A run is ready to close complete only after every pre-close condition below is verified from the folded
ledger and filesystem:

1. `remaining = 0`.
2. `in_flight = 0`.
3. `selected = evaluated + terminally_skipped` (where evaluated includes presented postings).
4. Every `attempt_started` has exactly one matching `attempt_accounted`.
5. The final `runs/{run_id}.json` and `reports/{ISO-date}-digest.md` have both been written.

Only then may the coordinator append `run_closed` with close state `complete`. A run is complete only when
all five pre-close conditions still hold, the ledger is closed, and its close state is `complete`. If any
condition is unproved, completion is unproved; do not close complete or claim success.

The closed close-state vocabulary is `complete`, `blocked`, and `interrupted`:

- `complete` establishes phase `complete` after the completion predicate passes.
- `blocked` records a named condition that prevented the run from continuing safely.
- `interrupted` records a run that cannot safely continue or be reconstructed.

`blocked` and `interrupted` are honest terminal closing states, but neither is equivalent to `complete`.
They preserve the last reached working phase and any durable evaluated work. A closed ledger is never
reopened, regardless of close state.

## Safe recovery and non-resumable search state

After compaction or process loss, read and fold the ledger before acting:

1. If it is closed, do not append or replay work. Treat only a close state of `complete` as completion.
2. If it is open and `selection_settled` was reached, preserve settled results and resume queued review.
   Reconcile any evaluating item and its attempt record explicitly; never assume an unresolved call was free,
   silently replay it, or mark it evaluated without evidence.
3. If it is open and `selection_settled` was not reached, close it `interrupted` when the valid ledger prefix
   permits that append, then start a fresh search with fresh call context. Do not infer a selected set from
   conversation memory or incomplete scratch.

Pagination cursors and other opaque API continuation tokens are non-resumable. Never persist, reconstruct,
or reuse them from the lifecycle ledger, final run record, digest, registry, jobs log, metrics, or pagination
scratch. A search that would require such a token restarts cleanly. The pagination scratch remains a separate,
explicitly non-resumable bounded candidate handoff; follow its deletion rules in
[conventions.md](conventions.md#pagination-scratch-lifecycle).

## Privacy boundary

The lifecycle ledger must never contain these prohibited fields or values: API keys, auth headers,
environment dumps, cursors, full job descriptions, preferences text, and match prose. Do not place a secret
or free-form user/job payload into an identifier field. A request identifier may be stored only as restricted,
nonsecret attempt provenance; it is not a continuation token.

The hidden filename is an organization detail, not an access-control boundary. The ledger stays inside the
private workspace protected by the workspace's deny-all source-control rules.

## Local metrics

Local milestone evidence lives at `{workspace}/metrics.json`. Its product-event fields use these timestamp
names: `onboarding_started_at`, `agent_data_ready_at`, `first_live_call_at`,
`first_relevant_match_ready_at`, `early_results_shown_at`, `run_completed_at`, and `schedule_verified_at`.

Metrics are local-only, no-PII product evidence, not telemetry. Never transmit them automatically or store
preferences, resumes, job or posting text, match content, credentials, auth material, environment dumps,
cursors, or other opaque continuation tokens in this file. Update metrics with an atomic whole-file write:
read the current JSON object, merge the owned timestamp, preserve fields owned by other flows, and atomically
replace the file. Never stream or append a partial JSON update.
