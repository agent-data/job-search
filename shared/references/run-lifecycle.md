# Run lifecycle, completion, recovery & local metrics

**Contents:** [Durable ledger](#durable-ledger) · [Ordered phases](#ordered-phases) · [Event and posting vocabulary](#event-and-posting-vocabulary) · [Completion and close states](#completion-and-close-states) · [Scripted append and fold/check operations](#scripted-append-and-foldcheck-operations) · [Safe recovery and non-resumable search state](#safe-recovery-and-non-resumable-search-state) · [Privacy boundary](#privacy-boundary) · [Local metrics](#local-metrics)

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

The order is monotonic and adjacent: each phase transition advances exactly one row in the canonical order,
never skips a phase, and never returns to an earlier phase. Before appending `selection_settled`, write
the `queued` posting state for every selected identity; the phase row is the commit marker proving the whole
selected set is already durable before posting review begins. An interactive run enters `early_results_shown` only after it has
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
- `attempt_resolved`
- `brief_revision`
- `milestone`
- `run_closed`
<!-- /lifecycle-contract:events -->

- `run_started` establishes the run identity, exact trigger attribution, immutable enabled-source order, and
  initial `preflight` phase once.
  Its `trigger` is exactly `manual`, `scheduled`, or `canary`; `scheduler_id` is JSON `null` for manual and
  a restricted nonsecret identifier for scheduled or canary. `source_order` is the nonempty, duplicate-free,
  `+`-joined `search.sources` list using only the canonical source enum. Reject inconsistent input without
  normalization rather than guessing or repairing its origin.
- `phase_changed` records a valid forward phase transition other than the terminal `complete` transition.
- `posting_state` records the latest state for one selected unique role's primary `(source, source_id)`
  identity and the brief revision under which its evaluation began. A merged role's non-primary alias rows
  have `jobs.jsonl` provenance events but never separate lifecycle states; otherwise source-row aliases
  would inflate the unique-role counters.
- `attempt_started` and `attempt_accounted` pair by restricted attempt identifier. The start also carries a
  coordinator-assigned `logical_operation_id` and adjacent positive `attempt_number`; these are the
  canonical retry link for the same immutable logical operation. Every started attempt, including a failed
  or retried attempt, requires exactly one accounting event before completion.
  A posting detail operation uses the deterministic identity `detail-<source>-<source_id>` copied from that
  exact queued posting. Recovery never interprets an initial-search or other operation as posting detail
  evidence merely because it reused that string.
- `attempt_resolved` is the sole handled-failure resolution. It binds the latest fully accounted
  `detail_read` attempt for one logical operation to exact resolution `summary_fallback`, only after the
  coordinator has durably written the canonical primary `detail_read:false` judgment. It is invalid for a
  logical operation containing any success, quota rejection, unaccounted attempt, non-detail operation,
  non-latest retry, or any later retry. Recovery and artifact authority also enforce the reverse join:
  every resolution's deterministic logical identity must name that durable false primary, and the set of
  resolved logical identities must equal the false-primary identities that have attempt history.
- `brief_revision` records a revision identifier, never the preferences text itself. A posting already
  `evaluating` settles under the brief revision its `posting_state` recorded at evaluation start; a newly
  recorded `brief_revision` governs only evaluations that begin after it. An in-flight producer attempt and
  its judgment are never cancelled, replaced, or re-attributed to satisfy a later revision — they finish and
  account under the revision they began under, and only then does the next revision apply to subsequent
  selection review. This ordering is the whole of the mid-run revision contract owned here. The interactive
  feedback routing that edits the brief, records this revision, applies it to the remaining queue, rechecks
  already-shown matches only when the outcome could change, and previews retrieval impact before a new search
  is the front door's concern that consumes this settling rule; it lives with that surface and is not
  re-decided here.
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
It is also a durable coordinator attestation with this closed transition invariant:

<!-- lifecycle-contract:presentation-transition -->
| Invariant | Contract value |
|---|---|
| `presented_identity` | `same_run_id+source+source_id` |
| `qualifying_job_event` | `evaluated+relevant_true+nonempty_reasoning` |
| `surface_proof` | `rendered_relevant_posting_with_reasoning` |
| `transition_order` | `append_after_successful_render` |
| `ledger_content` | `state_transition_only` |
| `reasoning_available_only` | `insufficient` |
| `title_only_render` | `insufficient` |
| `scheduled_or_canary` | `no_interactive_presented_transition` |
<!-- /lifecycle-contract:presentation-transition -->

Before appending a `presented` posting state, the coordinator must locate the `jobs.jsonl` `evaluated`
event with the same `(run_id, source, source_id)`, require `relevant:true` and a nonempty `reasoning` field,
and successfully render that relevant posting together with its reasoning on the user-facing surface. Only
after that render succeeds may it append the `presented` transition using the same run and posting identity.
Reasoning that merely exists, or a surface that renders only a title or other reasoning-free summary, does
not permit the transition. The lifecycle row stores only its ordinary state transition; reasoning content
remains solely in `jobs.jsonl` and the rendered output and never enters a lifecycle identifier or metrics.
Scheduled and canary runs remain quiet and do not append an interactive `presented` transition merely to
claim activation; publishing their final artifacts does not substitute for this invariant.

`terminally_skipped` is reserved for a selected posting that will not be retried in this run; it is not a
cleanup shortcut for forcing the completion predicate. Every selected identity first appears as `queued`
while the working phase is `searching`; only after all such rows exist may `selection_settled` be appended.
During a review phase its transitions are exactly `queued` → `evaluating` → (`evaluated` or
`terminally_skipped`), with the optional `evaluated` → `presented` transition subject to the render proof
above. Reject first-seen, duplicate, shortcut, backward, or post-terminal posting transitions.

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

- `selected` is the number of unique primary role identities recorded by `posting_state`.
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
| `no_blocking_attempt_failure` | `no_permanent_or_unresolved_attempt_failure` |
| `final_run_record_written` | `runs/{run_id}.json` |
| `final_digest_written` | `reports/{ISO-date}-digest.md` |
| `ledger_closed_complete` | `closed_with_complete_state` |
<!-- /lifecycle-contract:completion -->

The first seven clauses make a run ready to close. Only then may the coordinator append `run_closed` with
close state `complete`, which establishes the eighth clause. If any clause is unproved, completion is
unproved; do not close complete or claim success. In `selected_settled`, evaluated includes presented
postings. In `all_started_attempts_accounted`, every `attempt_started` has exactly one matching
`attempt_accounted`. Accounting alone is not success. The outcome vocabulary is exactly `success`,
`retryable_failure`, `terminal_failure`, `worker_failed`, or `quota_rejected`; quota rejection is always
unmetered. `quota_rejected` remains blocking. `terminal_failure` remains blocking unless its detail logical
operation has the canonical durable `summary_fallback` resolution. A `retryable_failure` or `worker_failed`
remains blocking unless a later fully accounted `success` has the same `logical_operation_id` and a higher
adjacent `attempt_number`, or the logical operation's latest fully accounted detail failure has the canonical
durable `summary_fallback` resolution. That resolution makes the handled logical operation nonblocking but
does not erase its attempt, metering, error, or retry diagnostics. A success on another logical operation,
or before the failure, does not resolve it. The two final-artifact clauses require both a concrete, non-symlink regular file at the
exact path and its matching lifecycle milestone; the digest's `reports/` directory must also be a real
directory, not a symlink. The digest path's ISO date is derived from `run_started` as specified by the
fold/check operation below. The coordinator appends each final-artifact milestone only after it has written
the exact path, read it back, and validated its schema/content against [conventions.md](conventions.md). The
same pre-milestone validation applies the bidirectional primary job-to-evaluated/presented posting join,
alias-through-primary/source/query checks, and durable source-order rule from **Artifact authority for every
reader** below. A missing job, premature job on a queued identity, alias lifecycle state, or contradictory
source/query blocks both milestones and therefore blocks complete close. The
fold script mechanically rechecks path identity and concrete-file existence; the milestone is the durable
coordinator attestation for validation that portable shell cannot reproduce.

For a prospective complete close, the validated artifacts may predeclare the intended terminal complete
state, but they are not authoritative or user-visible until the matching `run_closed:complete` append
succeeds. If that append fails, rewrite and revalidate both artifacts to the truthful noncomplete state
before attempting a blocked/interrupted close. If the fallback close also fails, the open ledger still makes
`can_complete=false`; surface only the repaired noncomplete artifacts. Never leave a displayed or published
complete claim without a final canonical complete close.

### Artifact authority for every reader

Run files are prospective values; the lifecycle ledger is their publication authority. Every home,
onboarding, usage, operator, activation, scheduling, and canary consumer applies this procedure before
trusting a final run record or digest:

1. Accept only a complete timestamp-shaped run-record filename and require its body `run_id` to equal that
   filename's exact run_id.
2. Locate exactly `runs/.lifecycle-{run_id}.jsonl` and run `lifecycle-fold.sh LEDGER WORKSPACE` (or its exact
   prose fallback). Require the fold's exact run_id to equal the candidate record and ledger identities.
   Require the record's exact `trigger` and `scheduler_id` to equal the folded `trigger` and `scheduler_id`;
   the fold's literal `scheduler_id=null` corresponds only to the record's JSON null.
3. Require `closed=true`, and require the record's `lifecycle.close_state` and `lifecycle.phase` to equal the
   folded close state and phase. For a complete record require `can_complete=true`; for a blocked or
   interrupted record require the matching noncomplete close and `can_complete=false`.
4. Every reader must
   strictly validate the complete current run-record schema and every cross-field invariant in
   [conventions.md](conventions.md#runsrun_idjson--audit-log), then rederive every ledger-owned count,
   retry diagnostic, attempt/call total, lifecycle value, and attribution field from the validated ledger
   and fold. Join every canonical current-run primary job event's exact `run_id+source+source_id` to a
   posting that the folded ledger leaves `evaluated` or `presented`, and require the reverse join for every
   primary posting in either of those states. A non-primary alias joins through its canonical present
   primary and never requires or permits its own lifecycle state. Every job row's `source` must occur in
   both durable `source_order` and record `sources_searched`, and its exact `source+query_id` must occur in
   `queries`; a job source absent from any required surface is contradictory. For an alias group, rederive
   the primary board source from durable `source_order` and reject an inverted primary. A primary
   `detail_read:false` must join either zero exact detail starts or the latest fully accounted failed
   detail attempt's `summary_fallback` resolution with no success anywhere in that logical history. A primary
   `detail_read:true` must join the exact logical history's latest fully accounted success and no handled
   resolution. Require the reverse join too: every handled resolution must name a present evaluated or
   presented false primary through exact deterministic logical identity, with set equality between
   resolutions and false primaries that have attempt history. Missing, orphaned, opposite, unresolved, or
   hidden-success evidence is contradictory. A
   schema-valid record that disagrees with durable evidence is not authoritative.
5. Locate only the digest derived by that same fold from the run's start date. Validate the digest heading
   exactly: date, `Run ID` line, health line, counts line, and calls-first usage line and placement. Validate
   the ordered band headings and content, filtered section, links, and blocked body against the record, canonical
   current-run `jobs.jsonl` events, and fold. Missing, added, reordered, or contradictory content rejects the
   pair. A noncomplete body names the exact terminal condition and renders its canonical cause and fix;
   alias groups render once with the primary link followed by their `also on` links. Never pair a record with
   a newest or caller-selected digest. Rederive the digest's result-row total, ordered per-source
   breakdown, per-match source tags, and missing-API-date marks from those joined canonical job rows; alias
   collapse changes rendered role/pipeline totals, never the result-row count.

This is the canonical every-reader procedure. Shipped readers delegate here and do not replace it with a
filename check, a partial JSON projection, digest substring matching, or a locally weakened interpretation.

An intended-complete record or digest may exist during the pre-close write/readback window. While its
ledger is an open ledger it is not a completed run, is excluded from latest-run/latest-digest selection,
must not be shown as complete, and must not verify a canary, schedule, activation, migration, or other
operator decision. A truthful repaired blocked file whose fallback close could not be appended remains
recovery evidence, not an authoritative final run for these readers.

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

## Scripted append and fold/check operations

Run the shared script where a POSIX shell runtime exists; otherwise execute the prose fallback in this
section exactly. The script and fallback accept the same fixed interfaces:

```text
lifecycle-append.sh LEDGER start RUN_ID ISO_TIMESTAMP TRIGGER SCHEDULER_ID_OR_DASH SOURCE_ORDER
lifecycle-append.sh LEDGER phase RUN_ID ISO_TIMESTAMP PHASE
lifecycle-append.sh LEDGER posting RUN_ID ISO_TIMESTAMP SOURCE SOURCE_ID STATE BRIEF_REVISION
lifecycle-append.sh LEDGER attempt-started RUN_ID ISO_TIMESTAMP ATTEMPT_ID OPERATION LOGICAL_OPERATION_ID ATTEMPT_NUMBER
lifecycle-append.sh LEDGER attempt-accounted RUN_ID ISO_TIMESTAMP ATTEMPT_ID METERED OUTCOME REQUEST_ID_OR_DASH
lifecycle-append.sh LEDGER attempt-resolved RUN_ID ISO_TIMESTAMP ATTEMPT_ID SUMMARY_FALLBACK
lifecycle-append.sh LEDGER revision RUN_ID ISO_TIMESTAMP BRIEF_REVISION
lifecycle-append.sh LEDGER milestone RUN_ID ISO_TIMESTAMP MILESTONE
lifecycle-append.sh LEDGER close RUN_ID ISO_TIMESTAMP COMPLETE_OR_BLOCKED_OR_INTERRUPTED INTERNAL_CODE_OR_DASH

lifecycle-fold.sh LEDGER WORKSPACE
```

`LEDGER` must be exactly `WORKSPACE/runs/.lifecycle-RUN_ID.jsonl`, and `RUN_ID` has the filename-safe format
defined in [conventions.md](conventions.md). Its date and time, and those in each ISO timestamp, must be
numerically valid Gregorian calendar and clock values: valid month/day combinations (including Gregorian
leap years), hours `00`–`23`, minutes and seconds `00`–`59`, and a numeric ISO offset no greater than
`14:00`; an ISO timestamp may instead end in `Z`. The coordinator supplies the run_started timestamp and
uses the local calendar date used for this run's digest; later event timestamps remain ordinary ISO timestamps.
This makes the exact digest path derivable through the fixed interface without accepting a
caller-supplied path. Validation is arithmetic and portable; it does not depend on a host-specific date
utility.

`TRIGGER` is exactly `manual`, `scheduled`, or `canary`. The value manual requires `-` for
`SCHEDULER_ID_OR_DASH`, which serializes as JSON `null`; scheduled and canary require a non-dash restricted
scheduler identifier. Reject every other trigger/scheduler combination without normalization and before
creating the ledger. These fields are durable source attribution, not a hint that the runner may rewrite.
`SOURCE_ORDER` is the exact nonempty `search.sources` list joined with `+` (for example,
`linkedin+ashby+greenhouse`), contains no duplicate, and uses only `linkedin`, `ashby`, `greenhouse`, and
`lever`. The start row owns it immutably. Every later posting source must occur in that durable order.

Every non-path, non-enum argument except an internal operator code is a restricted, nonsecret identifier:
1–256 characters, beginning with an ASCII letter or digit and continuing only with ASCII letters, digits,
`.`, `_`, `:`, `@`, `/`, `+`, `%`, `~`, or `-`. A non-null internal operator code is 1–256 characters and
must match `E-[A-Z0-9]+(-[A-Z0-9]+)*`; for example, `E-NO-AUTH` is safe and canonical. A dash in either
`REQUEST_ID_OR_DASH` or `INTERNAL_CODE_OR_DASH` serializes as JSON `null`. Otherwise each nullable argument
must be nonempty; the fold accepts only raw JSON `null` or a nonempty value matching its field grammar, never
an empty JSON string. `METERED` is exactly `true` or `false`. `ATTEMPT_NUMBER` is an unquoted positive
decimal integer of at most six digits. The first attempt for a `LOGICAL_OPERATION_ID` is 1; each retry
advances exactly one, retains the same `OPERATION`, and requires the prior attempt to be accounted before
its new start. Only `retryable_failure` and `worker_failed` permit that next start; `success`,
`terminal_failure`, `quota_rejected`, and a handled resolution are terminal for the logical operation.
`OUTCOME` uses the closed attempt-outcome vocabulary above, and `quota_rejected` requires
`METERED=false`. `SOURCE` is one of `linkedin`, `ashby`,
`greenhouse`, or `lever`; phase, posting-state, and close-state values use the closed vocabularies above. The
milestone vocabulary is exactly `early_results_shown`, `final_run_record_written`, and
`final_digest_written`.
`SUMMARY_FALLBACK` is the exact token `summary_fallback` and is accepted only by the handled-failure rules
above.

Before appending, reject wrong arity, multiline values, a ledger/run identity mismatch, an unknown enum, an
identifier outside that field's grammar, or a value shaped as any prohibited persistence field. The
field-aware denylist covers API keys and key-shaped values (including non-`sk-` forms such as `ghp_...`),
authorization/auth headers, bearer material, environment dumps, pagination cursors and page-token names
such as `next_page_token`, opaque continuation tokens, full job descriptions, preferences text, match prose,
and percent-encoded octets that could conceal those payloads. Internal operator codes use their dedicated
allowlist instead of secret-word filtering, so a canonical code such as `E-NO-AUTH` is not rejected merely
for containing `AUTH`. `OPERATION` is a controlled semantic label, not a payload-bearing provenance value;
it may therefore contain terms such as `job_description` or `authorization` when naming the coordinator
action, because those words persist no description prose, header contents, or authorization value. It still
uses the restricted identifier grammar and rejects percent-encoded octets and key-shaped values. The
semantic prohibited-term scan remains active for `SOURCE_ID`, `BRIEF_REVISION`, `ATTEMPT_ID`,
`LOGICAL_OPERATION_ID`, and
non-null `REQUEST_ID`, which can carry external identity, revision, result, or provenance values. Append and
fold apply these same per-field rules. These checks are defense in depth in addition to the privacy boundary
above; the fixed row shapes allow no extra fields.

### Append fallback

Validate the complete existing ledger with the fold fallback before every append. Only `start` may create a
ledger, and it fails if the path already exists. Every later command requires exactly one prior
`run_started` carrying the same run ID. A closed ledger rejects every command. `phase` rejects `complete` and
requires exactly the next canonical phase after the folded working phase. An attempt ID may have one
`attempt_started` and then exactly one `attempt_accounted`; accounting without its prior start, or either
duplicate, is invalid. A retry start is invalid unless its canonical link, stable operation, adjacent
number, and prior accounting all verify, and no handled resolution already exists for that logical
operation. `attempt-resolved` requires the latest fully accounted failed detail attempt and is unique for
the logical operation. Posting rows use last-write-wins primary unique-role identity
`(source, source_id)` and reject a source absent from the run's durable `source_order`. A `close complete`
command requires the open fold to report `ready_to_close=true`; it writes the single terminal row that
atomically establishes both `phase=complete` and `closed=true`. Other close states preserve the last working
phase. After validation, append exactly one of these canonical, no-whitespace JSON lines in the shown field
order, replacing placeholders with the validated arguments:

```jsonc
{"event":"run_started","run_id":"RUN_ID","ts":"ISO_TIMESTAMP","phase":"preflight","trigger":"TRIGGER","scheduler_id":"SCHEDULER_ID","source_order":"SOURCE_ORDER"}
{"event":"phase_changed","run_id":"RUN_ID","ts":"ISO_TIMESTAMP","phase":"PHASE"}
{"event":"posting_state","run_id":"RUN_ID","ts":"ISO_TIMESTAMP","source":"SOURCE","source_id":"SOURCE_ID","state":"STATE","brief_revision":"BRIEF_REVISION"}
{"event":"attempt_started","run_id":"RUN_ID","ts":"ISO_TIMESTAMP","attempt_id":"ATTEMPT_ID","operation":"OPERATION","logical_operation_id":"LOGICAL_OPERATION_ID","attempt_number":1}
{"event":"attempt_accounted","run_id":"RUN_ID","ts":"ISO_TIMESTAMP","attempt_id":"ATTEMPT_ID","metered":true,"outcome":"OUTCOME","request_id":"REQUEST_ID"}
{"event":"attempt_resolved","run_id":"RUN_ID","ts":"ISO_TIMESTAMP","attempt_id":"ATTEMPT_ID","resolution":"summary_fallback"}
{"event":"brief_revision","run_id":"RUN_ID","ts":"ISO_TIMESTAMP","brief_revision":"BRIEF_REVISION"}
{"event":"milestone","run_id":"RUN_ID","ts":"ISO_TIMESTAMP","milestone":"MILESTONE"}
{"event":"run_closed","run_id":"RUN_ID","ts":"ISO_TIMESTAMP","close_state":"CLOSE_STATE","internal_code":"INTERNAL_CODE"}
```

The three nullable fields (`scheduler_id`, `request_id`, and `internal_code`) use the raw JSON value `null`,
not the string `"null"`, when their command argument is a dash. Otherwise they use a nonempty JSON string;
an empty string is never canonical. A complete close
always uses a null internal code. The append is the sanctioned append-only ledger write; never rewrite or
reorder existing lines.

### Fold/check fallback

Read only canonical rows matching the shapes, field order, restricted values, and invariants above. Treat a
missing/empty ledger, noncanonical row, changed run ID, duplicate start, event after closure, non-adjacent
phase, invalid posting transition, accounting without a prior attempt start, a duplicate attempt event, or complete close outside
`finalizing` as a malformed or contradictory ledger; stop without reporting completion. An outstanding
started attempt is valid open state, but it prevents readiness until exactly one accounting event follows.

Fold valid rows in order:

1. Start at `preflight`; apply strictly forward `phase_changed` rows. Preserve that working phase for
   `blocked` or `interrupted`; use `complete` only for a valid complete close.
2. Fold `posting_state` last-write-wins by primary unique-role `(source, source_id)` and reject any posting
   source absent from immutable `source_order`. Derive `selected`, `evaluated`,
   `terminally_skipped`, `presented`, `remaining`, and `in_flight` with the counter rules above.
3. Count unique attempt starts and their exactly-once accounting rows as `attempts_started` and
   `attempts_accounted`. Derive `blocking_attempt_failures` from the outcome/link rules above; fixture or
   coordinator intent never overrides this canonical fold. A valid latest `summary_fallback` resolution
   removes the handled logical operation from `blocking_attempt_failures` without removing its accounting or
   diagnostics; every other failure follows the ordinary blocking rules.
4. From the first 10 characters of the validated `run_started` timestamp, derive exactly
   `WORKSPACE/reports/YYYY-MM-DD-digest.md`; derive the run record as `WORKSPACE/runs/RUN_ID.json`. Require
   each concrete regular file to be non-symlink and its respective `final_digest_written` or
   `final_run_record_written` milestone; require the `reports/` directory itself to be non-symlink. Accept
   never an arbitrary or newest digest.
5. Set `ready_to_close=true` only when the working phase is `finalizing`, `remaining=0`, `in_flight=0`,
   `selected=evaluated+terminally_skipped`, all started attempts are accounted,
   `blocking_attempt_failures=0`, and both final artifact
   file-plus-milestone checks pass. A closed `blocked` or `interrupted` ledger always reports
   `ready_to_close=false`.
6. Set `can_complete=true` only when `ready_to_close=true` and the final canonical row closes the run
   `complete`. An open ready ledger has `can_complete=false`; blocked and interrupted ledgers always have
   `can_complete=false`. A complete close whose predicate does not pass is contradictory and fails closed.

Emit normalized `key=value` state in this order: `run_id`, `trigger`, `scheduler_id`, `source_order`, `phase`, `selected`, `evaluated`,
`terminally_skipped`, `presented`, `remaining`, `in_flight`, `attempts_started`, `attempts_accounted`,
`blocking_attempt_failures`, `final_run_record_written`, `final_digest_written`, `closed`, `close_state`, `ready_to_close`, and
`can_complete`. The two final-artifact output values report exact eligible non-symlink file existence; their
milestone evidence is additionally required by `ready_to_close`. In normalized output, a manual run's JSON
null scheduler is emitted as the literal text `scheduler_id=null`.

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
  replay it, or mark it evaluated without evidence. An `evaluating` posting at compaction is a producer
  attempt that was started but not yet reconciled. If the ledger already accounts that attempt, or a durable
  `jobs.jsonl` result exists for its exact identity, settle from that evidence and do not re-dispatch. If it
  is genuinely unresolved, treat it as a possibly-consumed metered call: account it honestly rather than as
  zero, and re-request that detail only with fresh cost awareness, never as a silent second dispatch.
- Recovery must discard all coordinator memory, including prior effects, task-local queues, and conversation
  state. Reconstruct phase, immutable source order, primary posting states, and attempt identities only from
  the exact current run's validated lifecycle ledger. Read `jobs.jsonl` as a separate append-only source:
  accept only canonical `evaluated` groups whose primary event's exact `run_id+source+source_id` joins the
  current ledger identity. Validate each alias through that present primary, require its source in durable
  source order, and rederive the earliest board primary from that order; an alias never owns lifecycle state.
  An `evaluating` posting may advance without another producer call only through one of two exact branches.
  A joined primary with `detail_read:false` settles from that canonical durable summary judgment when either
  no attempt start exists for exact logical operation `detail-<source>-<source_id>`, or its latest start is
  a fully accounted detail failure carrying the exact durable `summary_fallback` resolution. A success,
  quota rejection, unaccounted failure, missing resolution, or later retry contradicts the false value.
  A joined primary with `detail_read:true` also requires that exact
  logical operation's latest adjacent attempt to be durable, its start to say `operation=detail_read`, and
  its unique accounting row to say `outcome=success`. A prior success followed by a failed or unaccounted
  later ordinal cannot settle the posting. Stale cross-run jobs,
  malformed events, wrong-operation starts, wrong source/source_id identities, unmatched attempts, and
  non-adjacent or unaccounted ordinals cannot settle it. Before resuming any posting, reverse-join every
  handled resolution to a durable false primary through exact deterministic logical identity and require
  set equality with the false primaries that have attempt history.
  Resume each reconstructed `queued` identity with a fresh coordinator-owned attempt start and dispatch.
- For `open_before_selection_settled`, close the run `interrupted` when the valid ledger prefix permits that
  append, then start a fresh search with fresh call context. That fresh search is a new run: it re-establishes
  calls-first cost context before its first metered attempt and never assumes a prior, possibly-consumed call
  was free. Do not infer a selected set from conversation memory or incomplete scratch.

Opaque search state follows this contract:

<!-- lifecycle-contract:search-state -->
| Search-state rule | Required value |
|---|---|
| `cursor_persistence` | `prohibited` |
| `cursor_reconstruction` | `prohibited` |
| `cursor_reuse` | `prohibited` |
| `search_restart` | `clean_required` |
| `pagination_scratch` | `separate_non_resumable` |
<!-- /lifecycle-contract:search-state -->

Pagination cursors and other opaque API continuation tokens are non-resumable. Never persist, reconstruct,
or reuse them from the lifecycle ledger, final run record, digest, registry, jobs log, metrics, or pagination
scratch. A continuation that could only proceed by reusing such a token — one lost to compaction, or one the
source has expired or rejected — never resumes: while the run is still before `selection_settled` it closes
`interrupted`, and the next run restarts that search cleanly with fresh calls-first cost context rather than
resuming the cursor. The pagination scratch remains a separate, explicitly non-resumable bounded candidate
handoff; follow its deletion rules in [conventions.md](conventions.md#pagination-scratch-lifecycle), where a
later run deletes stale scratch without reading or resuming it.

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

Do not place a secret or free-form user/job payload into an identifier field. Reject percent-encoded octets,
page-token/cursor field names such as `next_page_token`, and recognized key-shaped values such as `sk-...`,
`ghp_...`, `github_pat_...`, and `AKIA...`. A request identifier may be stored only as restricted, nonsecret
attempt provenance; it is not a continuation token. Internal operator codes are validated by their closed
`E-...` grammar rather than by scanning for broad substrings such as `AUTH`. Controlled `OPERATION` labels
likewise may name an action with semantic terms such as `authorization` or `job_description`; they remain
subject to restricted grammar plus encoded-octet and key-shape rejection.

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

Every timestamp above is scoped to one setup attempt; there is no duplicate aggregate timestamp at the
document root. The required document and record shape is:

<!-- lifecycle-contract:metric-document -->
| Attribute | Contract value |
|---|---|
| `version` | `1` |
| `required_root_keys` | `version,active_setup_id,setups` |
| `record_container` | `setups[]` |
| `active_selector` | `active_setup_id` |
| `record_identity` | `setup_id` |
| `identity_format` | `setup-{uuid_v4_lowercase}` |
| `timestamp_scope` | `per_setup_record` |
| `unobserved_timestamps` | `omitted` |
<!-- /lifecycle-contract:metric-document -->

```jsonc
{
  "version": 1,
  "active_setup_id": "setup-7f946a4d-e19f-4e3d-8a86-3f9a0ce31171",
  "setups": [
    {
      "setup_id": "setup-7f946a4d-e19f-4e3d-8a86-3f9a0ce31171",
      "onboarding_started_at": "2026-07-16T14:20:00Z"
    }
  ]
}
```

`setup_id` is generated locally as `setup-` plus a fresh canonical lowercase UUIDv4. It must match
`setup-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}`; it contains no user,
workspace, posting, run, or external-service identifier. The front door creates a new attempt by appending
one record containing a fresh `setup_id` and `onboarding_started_at`, then changing `active_setup_id` to
that identity in the same atomic write. It never reuses an identity, replaces a prior record, or deletes
history. All later owners target the one record whose `setup_id` equals `active_setup_id`; if that selector
is absent or invalid, they do not invent an attempt or backfill a timestamp.

Timestamp write ownership is closed:

<!-- lifecycle-contract:metric-owners -->
| Timestamp | Owner |
|---|---|
| `onboarding_started_at` | `front_door` |
| `agent_data_ready_at` | `front_door` |
| `first_live_call_at` | `runner` |
| `first_relevant_match_ready_at` | `runner` |
| `early_results_shown_at` | `runner` |
| `run_completed_at` | `runner` |
| `schedule_verified_at` | `schedule_setup` |
<!-- /lifecycle-contract:metric-owners -->

- The front door writes `onboarding_started_at` when it creates the attempt and writes
  `agent_data_ready_at` when it first verifies agent-data is ready for that attempt.
- The runner writes `first_live_call_at` when the first live job request begins,
  `first_relevant_match_ready_at` when a fully evaluated relevant posting first has nonempty reasoning,
  `early_results_shown_at` only when interactive early results are actually shown, and `run_completed_at`
  only when the first live run reaches a valid complete close. Skipping an inapplicable presentation phase
  does not establish the shown timestamp; a blocked or interrupted close does not establish completion.
- Schedule setup writes `schedule_verified_at` only after its real scheduled-path canary has passed. Merely
  registering a schedule does not establish verification.

Every owner follows these write rules:

<!-- lifecycle-contract:metric-write-rules -->
| Rule | Contract value |
|---|---|
| `timestamp_writer` | `owner_only` |
| `first_observation` | `write_once` |
| `existing_timestamp` | `preserve_exactly` |
| `setup_id` | `immutable` |
| `new_onboarding_attempt` | `append_new_setup_record` |
| `historical_setup_records` | `never_overwrite_or_delete` |
<!-- /lifecycle-contract:metric-write-rules -->

For the selected setup record, a timestamp owner writes its field only when the field is absent. A retry,
replay, later run, or later schedule verification preserves an existing value exactly. A genuinely new
onboarding attempt is the only reset boundary: it appends a new record and makes that record active instead
of clearing or overwriting the previous attempt. Each update reads the current JSON object, merges only the
owner's absent field, preserves unknown root keys, unknown record keys, other owners' fields, and every
historical record, then atomically replaces the whole file. Never stream or append a partial JSON update.

### Activation

Activation is a view over durable run evidence, not a metric field:

<!-- lifecycle-contract:activation -->
| Clause | Contract value |
|---|---|
| `persisted` | `false` |
| `run_health` | `not_blocked` |
| `fully_evaluated_postings` | `at_least_one` |
| `relevant_matches_shown_with_reasoning` | `at_least_one_valid_presented_transition` |
<!-- /lifecycle-contract:activation -->

Derive activation only when one run first passes **Artifact authority for every reader** above—exact run_id,
matching record, `closed=true`, and the fold-derived digest—and then satisfies all three evidence clauses.
Its final run record has `run_health` other than `blocked`; its folded lifecycle ledger has at least one evaluated posting
(`presented` still counts as evaluated); and it has at least one valid `presentation-transition` attestation
under the invariant above. That transition binds the rendered reasoning to the same run and posting as the
qualifying `jobs.jsonl` event, rather than inferring presentation from reasoning availability. A blocked run,
a run with no fully evaluated posting, a zero-relevant run, reasoning that was never rendered, title-only
output, or a relevant match that has not made the valid transition does not activate setup. Do not persist
an activation boolean, activation timestamp, matching posting identity, or reasoning in metrics.

### Zero-relevant recovery

A nonblocked run that fully evaluated at least one posting but made no valid `presented` transition — a
zero-relevant run — does not meet activation's requirement that at least one relevant match be shown with
reasoning, so it is honest diagnostic work, not activation. It is nonetheless a truthful **completed**
outcome, not a failure and not evidence that the search terms were too narrow: retrieval delivered postings
and judgment rejected them, so the relevance count describes fit, not recall. Do not claim activation, an
early-look match, or the setup payoff for it, and do not present a matches list it does not have.

Recover in a single move: say the search ran and what it learned (which sources and queries it covered, that
nothing cleared the brief this pass), then offer exactly **one** high-signal next step — the single change
most likely to surface a real match, never a list of levers, which only fatigues the user into ignoring all
of them. Choose that step by assessing query health (`query-strategy.md`), never from the relevance count
alone: where the run's raw per-source volume was healthy, start from the rejection reasons — one targeted
lane replacement, or one brief clarification — and reach for a broader role family only when that evidence
names a missing adjacent lane, or when the raw volume was itself thin in context. The suggestion stays
read-only until the user accepts it. A fresh run the user accepts is a new run: it re-earns calls-first cost
context before its first metered call (see
[Agent-data usage decisions](internals.md#agent-data-usage-decisions)) and never assumes a prior,
possibly-consumed call was free. This is distinct from the two zero-**result** outcomes in
[errors.md](errors.md) (all already known; literally empty): here postings were returned and judged, and none
was a relevant match.

### Named durations

The only named durations are derived per setup record:

<!-- lifecycle-contract:derived-durations -->
| Duration | Endpoint order |
|---|---|
| `time_to_help` | `onboarding_started_at->early_results_shown_at` |
| `first_match_review_latency` | `first_live_call_at->first_relevant_match_ready_at` |
| `total_run_time` | `first_live_call_at->run_completed_at` |
<!-- /lifecycle-contract:derived-durations -->

For each row, parse both timestamps as instants and subtract the start from the end. Report the duration as
unavailable when either endpoint is absent or the end precedes the start. Never write these duration names
or values into `metrics.json`.

### Local-only, no telemetry

Metrics are local-only, no-PII product evidence, not telemetry. Never transmit them automatically or store
preferences, resumes, job or posting text, match content, credentials, auth material, environment dumps,
cursors, or other opaque continuation tokens in this file.
