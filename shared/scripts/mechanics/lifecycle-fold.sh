#!/bin/sh
# lifecycle-fold.sh — validate and fold one canonical run-lifecycle ledger.
#
# The ledger is coordinator-written, append-only JSON Lines. This script accepts only the exact rows
# emitted by lifecycle-append.sh, folds posting state last-write-wins, pairs attempts, and verifies
# completion against the exact final artifacts for the run. The digest date is the calendar date in the
# run_started timestamp; no arbitrary or newest digest is accepted.
#
# Usage: lifecycle-fold.sh LEDGER WORKSPACE
set -u

if [ "$#" -ne 2 ]; then
  echo 'usage: lifecycle-fold.sh LEDGER WORKSPACE' >&2
  exit 2
fi

ledger=$1
workspace=$2
case $ledger in
  *'
'*) echo 'lifecycle-fold: multiline ledger paths are prohibited' >&2; exit 1 ;;
esac
case $workspace in
  *'
'*) echo 'lifecycle-fold: multiline workspace paths are prohibited' >&2; exit 1 ;;
esac
[ -f "$ledger" ] && [ -s "$ledger" ] || {
  echo 'lifecycle-fold: ledger is missing or empty' >&2
  exit 1
}

folded=$(mktemp) || exit 2
trap 'rm -f "$folded"' EXIT INT HUP TERM

awk '
function fail(message) {
  print "lifecycle-fold: line " NR ": " message > "/dev/stderr"
  invalid = 1
  exit 1
}
function string_value(row, key, marker, start, rest, finish) {
  marker = "\"" key "\":\""
  start = index(row, marker)
  if (!start) return ""
  rest = substr(row, start + length(marker))
  finish = index(rest, "\"")
  if (!finish) return ""
  return substr(rest, 1, finish - 1)
}
function number_value(row, key, marker, start, rest, comma, brace, finish) {
  marker = "\"" key "\":"
  start = index(row, marker)
  if (!start) return ""
  rest = substr(row, start + length(marker))
  comma = index(rest, ",")
  brace = index(rest, "}")
  if (comma && brace) finish = comma < brace ? comma : brace
  else finish = comma ? comma : brace
  if (!finish) return ""
  return substr(rest, 1, finish - 1)
}
function restricted(value) {
  return value ~ /^[A-Za-z0-9][A-Za-z0-9._:@\/+%~-]*$/ && length(value) <= 256
}
function operator_code(value) {
  return length(value) <= 256 && value ~ /^E-[A-Z0-9]+(-[A-Z0-9]+)*$/
}
function valid_source_order(value, parts, count, i, j) {
  count = split(value, parts, "+")
  if (count < 1) return 0
  for (i = 1; i <= count; i++) {
    if (parts[i] !~ /^(linkedin|ashby|greenhouse|lever)$/) return 0
    for (j = 1; j < i; j++) if (parts[i] == parts[j]) return 0
  }
  return 1
}
function has_long_token(lower, prefix, minimum, start, position, absolute, before, rest, i, character, count) {
  start = 1
  while ((position = index(substr(lower, start), prefix)) > 0) {
    absolute = start + position - 1
    before = absolute == 1 ? "" : substr(lower, absolute - 1, 1)
    if (before == "" || before !~ /[a-z0-9]/) {
      rest = substr(lower, absolute + length(prefix))
      count = 0
      for (i = 1; i <= length(rest); i++) {
        character = substr(rest, i, 1)
        if (character !~ /[a-z0-9_-]/) break
        count++
      }
      if (count >= minimum) return 1
    }
    start = absolute + 1
  }
  return 0
}
function unsafe_identifier(field, value, lower) {
  lower = tolower(value)
  return lower ~ /%[0-9a-f][0-9a-f]/ \
      || (field != "operation" && lower ~ /(^|[-._:@\/+%~])(api[_-]?keys?|authorization|auth[_-]?headers?|bearer|environment[_-]?dumps?|pagination[_-]?cursors?|cursors?|next[_-]?page[_-]?tokens?|page[_-]?tokens?|opaque[_-]?api[_-]?continuation[_-]?tokens?|continuation[_-]?tokens?|full[_-]?job[_-]?descriptions?|job[_-]?descriptions?|preferences?[_-]?text|match[_-]?prose)([-._:@\/+%~]|$)/) \
      || has_long_token(lower, "sk-", 8) \
      || has_long_token(lower, "ghp_", 20) \
      || has_long_token(lower, "gho_", 20) \
      || has_long_token(lower, "ghu_", 20) \
      || has_long_token(lower, "ghs_", 20) \
      || has_long_token(lower, "ghr_", 20) \
      || has_long_token(lower, "github_pat_", 20) \
      || has_long_token(lower, "akia", 16)
}
function valid_calendar_date(value, year, month, day, maximum) {
  year = substr(value, 1, 4) + 0
  month = substr(value, 6, 2) + 0
  day = substr(value, 9, 2) + 0
  if (year < 1 || month < 1 || month > 12 || day < 1) return 0
  if (month == 2) {
    maximum = 28
    if (year % 400 == 0 || (year % 4 == 0 && year % 100 != 0)) maximum = 29
  } else if (month == 4 || month == 6 || month == 9 || month == 11) maximum = 30
  else maximum = 31
  return day <= maximum
}
function valid_clock(value, hour, minute, second) {
  hour = substr(value, 12, 2) + 0
  minute = substr(value, 15, 2) + 0
  second = substr(value, 18, 2) + 0
  return hour <= 23 && minute <= 59 && second <= 59
}
function valid_offset(value, zone, hour, minute) {
  zone = substr(value, length(value), 1)
  if (zone == "Z") return 1
  zone = substr(value, length(value) - 5)
  hour = substr(zone, 2, 2) + 0
  minute = substr(zone, 5, 2) + 0
  return hour <= 14 && minute <= 59 && (hour < 14 || minute == 0)
}
function valid_run_id(value) {
  return value ~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]-[0-9][0-9]-[0-9][0-9]Z$/ \
      && valid_calendar_date(value) && valid_clock(value)
}
function valid_timestamp(value) {
  return value ~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9](\.[0-9][0-9]*)?(Z|[+-][0-9][0-9]:[0-9][0-9])$/ \
      && valid_calendar_date(value) && valid_clock(value) && valid_offset(value)
}
function common_fields(row, expected_event, rid, timestamp) {
  rid = string_value(row, "run_id")
  timestamp = string_value(row, "ts")
  if (!valid_run_id(rid) || !valid_timestamp(timestamp)) fail("invalid run identity or timestamp")
  if (started && rid != run_id) fail("run_id changed")
  event_run_id = rid
  event_timestamp = timestamp
}
BEGIN {
  phase_rank["preflight"] = 1
  phase_rank["searching"] = 2
  phase_rank["selection_settled"] = 3
  phase_rank["reviewing_initial_batch"] = 4
  phase_rank["early_results_shown"] = 5
  phase_rank["reviewing_remaining"] = 6
  phase_rank["finalizing"] = 7
  working_phase = ""
  close_state = "open"
}
{
  row = $0
  if (row == "") fail("empty row")
  event = string_value(row, "event")
  if (event == "") fail("missing event")
  if (closed) fail("event follows terminal run_closed")

  common_fields(row, event)
  rid = event_run_id
  timestamp = event_timestamp

  if (event == "run_started") {
    phase = string_value(row, "phase")
    trigger = string_value(row, "trigger")
    scheduler_marker = "\"scheduler_id\":"
    scheduler_start = index(row, scheduler_marker)
    if (!scheduler_start) fail("missing scheduler_id")
    scheduler_tail = substr(row, scheduler_start + length(scheduler_marker))
    if (substr(scheduler_tail, 1, 5) == "null,") {
      scheduler_json = "null"
      scheduler_is_null = 1
      scheduler_id = ""
    } else {
      scheduler_is_null = 0
      scheduler_id = string_value(row, "scheduler_id")
      if (scheduler_id == "") fail("scheduler_id must be null or nonempty")
      scheduler_json = "\"" scheduler_id "\""
    }
    source_order = string_value(row, "source_order")
    canonical = "{\"event\":\"run_started\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"phase\":\"preflight\",\"trigger\":\"" trigger "\",\"scheduler_id\":" scheduler_json ",\"source_order\":\"" source_order "\"}"
    if (row != canonical || NR != 1 || started || phase != "preflight") fail("invalid run_started row")
    if (trigger !~ /^(manual|scheduled|canary)$/) fail("invalid trigger")
    if (trigger == "manual" && !scheduler_is_null) fail("manual trigger requires null scheduler_id")
    if (trigger != "manual" && (scheduler_is_null || !restricted(scheduler_id) || unsafe_identifier("scheduler_id", scheduler_id))) fail("scheduled and canary triggers require a safe scheduler_id")
    if (!valid_source_order(source_order)) fail("invalid source_order")
    started = 1
    run_id = rid
    run_trigger = trigger
    run_scheduler_id = scheduler_is_null ? "null" : scheduler_id
    run_source_order = source_order
    started_date = substr(timestamp, 1, 10)
    working_phase = "preflight"
    current_rank = phase_rank[working_phase]
    next
  }

  if (!started) fail("first row must be run_started")

  if (event == "phase_changed") {
    phase = string_value(row, "phase")
    canonical = "{\"event\":\"phase_changed\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"phase\":\"" phase "\"}"
    if (row != canonical || !(phase in phase_rank)) fail("invalid phase_changed row")
    if (phase_rank[phase] != current_rank + 1) fail("phase transition must advance exactly one canonical phase")
    current_rank = phase_rank[phase]
    working_phase = phase
    next
  }

  if (event == "posting_state") {
    source = string_value(row, "source")
    source_id = string_value(row, "source_id")
    state = string_value(row, "state")
    revision = string_value(row, "brief_revision")
    canonical = "{\"event\":\"posting_state\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"source\":\"" source "\",\"source_id\":\"" source_id "\",\"state\":\"" state "\",\"brief_revision\":\"" revision "\"}"
    if (row != canonical) fail("noncanonical posting_state row")
    if (source !~ /^(linkedin|ashby|greenhouse|lever)$/ || !restricted(source_id) || !restricted(revision)) fail("invalid posting identifier")
    if (!index("+" run_source_order "+", "+" source "+")) fail("posting source is absent from source_order")
    if (state !~ /^(queued|evaluating|evaluated|presented|terminally_skipped)$/) fail("invalid posting state")
    if (unsafe_identifier("source_id", source_id) || unsafe_identifier("brief_revision", revision)) fail("prohibited posting value")
    identity = source SUBSEP source_id
    if (!(identity in posting)) {
      if (state != "queued" || working_phase != "searching") fail("selected posting must first queue while selection is settling")
    } else {
      prior_state = posting[identity]
      review_phase = working_phase == "reviewing_initial_batch" || working_phase == "reviewing_remaining"
      if (state == "evaluating") {
        if (prior_state != "queued" || !review_phase) fail("invalid queued-to-evaluating transition")
      } else if (state == "evaluated" || state == "terminally_skipped") {
        if (prior_state != "evaluating" || !review_phase) fail("invalid evaluating-to-terminal transition")
      } else if (state == "presented") {
        if (prior_state != "evaluated" || !review_phase) fail("invalid evaluated-to-presented transition")
      } else fail("duplicate queued or invalid posting transition")
    }
    posting[identity] = state
    next
  }

  if (event == "attempt_started") {
    attempt_id = string_value(row, "attempt_id")
    operation = string_value(row, "operation")
    logical_operation_id = string_value(row, "logical_operation_id")
    attempt_number = number_value(row, "attempt_number")
    canonical = "{\"event\":\"attempt_started\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"attempt_id\":\"" attempt_id "\",\"operation\":\"" operation "\",\"logical_operation_id\":\"" logical_operation_id "\",\"attempt_number\":" attempt_number "}"
    if (row != canonical || !restricted(attempt_id) || !restricted(operation) || !restricted(logical_operation_id) || attempt_number !~ /^[1-9][0-9]*$/ || length(attempt_number) > 6) fail("invalid attempt_started row")
    if (unsafe_identifier("attempt_id", attempt_id) || unsafe_identifier("operation", operation) || unsafe_identifier("logical_operation_id", logical_operation_id)) fail("prohibited attempt value")
    if (attempt_id in attempts_started) fail("duplicate attempt_started")
    if (logical_operation_id in logical_resolution) fail("resolved logical operation cannot be retried")
    if (logical_operation_id in logical_attempt_count) {
      if (operation != logical_operation[logical_operation_id]) fail("logical operation changed operation")
      if (attempt_number + 0 != logical_attempt_count[logical_operation_id] + 1) fail("retry attempt_number must advance exactly one")
      prior_attempt = logical_latest_attempt[logical_operation_id]
      if (!(prior_attempt in attempts_accounted)) fail("retry started before prior attempt was accounted")
      if (attempt_outcome[prior_attempt] !~ /^(retryable_failure|worker_failed)$/) fail("retry followed a nonretryable outcome")
    } else if (attempt_number + 0 != 1) fail("logical operation did not begin at attempt_number 1")
    attempts_started[attempt_id] = 1
    attempt_operation[attempt_id] = operation
    attempt_logical[attempt_id] = logical_operation_id
    attempt_ordinal[attempt_id] = attempt_number + 0
    logical_attempt_count[logical_operation_id] = attempt_number + 0
    logical_operation[logical_operation_id] = operation
    logical_latest_attempt[logical_operation_id] = attempt_id
    next
  }

  if (event == "attempt_resolved") {
    attempt_id = string_value(row, "attempt_id")
    resolution = string_value(row, "resolution")
    canonical = "{\"event\":\"attempt_resolved\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"attempt_id\":\"" attempt_id "\",\"resolution\":\"" resolution "\"}"
    if (row != canonical || !restricted(attempt_id) || resolution != "summary_fallback") fail("invalid attempt_resolved row")
    if (!(attempt_id in attempts_started) || !(attempt_id in attempts_accounted)) fail("attempt_resolved requires a fully accounted attempt")
    logical = attempt_logical[attempt_id]
    if (attempt_operation[attempt_id] != "detail_read") fail("summary fallback requires detail_read")
    if (logical_latest_attempt[logical] != attempt_id) fail("summary fallback must resolve the latest attempt")
    if (attempt_outcome[attempt_id] !~ /^(retryable_failure|terminal_failure|worker_failed)$/) fail("summary fallback requires an accounted failure")
    for (prior_attempt in attempt_logical) {
      if (attempt_logical[prior_attempt] == logical && attempt_outcome[prior_attempt] == "success") fail("summary fallback cannot follow a successful attempt")
    }
    if (logical in logical_resolution) fail("duplicate logical operation resolution")
    logical_resolution[logical] = resolution
    resolution_attempt[logical] = attempt_id
    next
  }

  if (event == "attempt_accounted") {
    attempt_id = string_value(row, "attempt_id")
    outcome = string_value(row, "outcome")
    request_id = string_value(row, "request_id")
    meter_marker = "\"metered\":"
    meter_start = index(row, meter_marker)
    if (!meter_start) fail("missing metered value")
    meter_rest = substr(row, meter_start + length(meter_marker))
    if (substr(meter_rest, 1, 5) == "true,") metered = "true"
    else if (substr(meter_rest, 1, 6) == "false,") metered = "false"
    else fail("invalid metered value")
    request_marker = "\"request_id\":"
    request_start = index(row, request_marker)
    if (!request_start) fail("missing request_id")
    request_tail = substr(row, request_start + length(request_marker))
    if (request_tail == "null}") {
      request_json = "null"
      request_is_null = 1
      request_id = ""
    } else {
      request_is_null = 0
      if (request_id == "") fail("request_id must be null or nonempty")
      request_json = "\"" request_id "\""
    }
    canonical = "{\"event\":\"attempt_accounted\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"attempt_id\":\"" attempt_id "\",\"metered\":" metered ",\"outcome\":\"" outcome "\",\"request_id\":" request_json "}"
    if (row != canonical || !restricted(attempt_id) || outcome !~ /^(success|retryable_failure|terminal_failure|worker_failed|quota_rejected)$/) fail("invalid attempt_accounted row")
    if (!request_is_null && !restricted(request_id)) fail("invalid request_id")
    if (unsafe_identifier("attempt_id", attempt_id) || unsafe_identifier("outcome", outcome) || (!request_is_null && unsafe_identifier("request_id", request_id))) fail("prohibited accounting value")
    if (!(attempt_id in attempts_started)) fail("attempt_accounted has no prior start")
    if (attempt_id in attempts_accounted) fail("duplicate attempt_accounted")
    if (outcome == "quota_rejected" && metered != "false") fail("quota_rejected must be unmetered")
    attempts_accounted[attempt_id] = 1
    attempt_outcome[attempt_id] = outcome
    if (outcome == "success") {
      logical = attempt_logical[attempt_id]
      if (attempt_ordinal[attempt_id] > logical_success_ordinal[logical]) logical_success_ordinal[logical] = attempt_ordinal[attempt_id]
    }
    next
  }

  if (event == "brief_revision") {
    revision = string_value(row, "brief_revision")
    canonical = "{\"event\":\"brief_revision\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"brief_revision\":\"" revision "\"}"
    if (row != canonical || !restricted(revision) || unsafe_identifier("brief_revision", revision)) fail("invalid brief_revision row")
    next
  }

  if (event == "milestone") {
    milestone = string_value(row, "milestone")
    canonical = "{\"event\":\"milestone\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"milestone\":\"" milestone "\"}"
    if (row != canonical || milestone !~ /^(early_results_shown|final_run_record_written|final_digest_written)$/) fail("invalid milestone row")
    milestones[milestone] = 1
    next
  }

  if (event == "run_closed") {
    state = string_value(row, "close_state")
    code = string_value(row, "internal_code")
    code_marker = "\"internal_code\":"
    code_start = index(row, code_marker)
    if (!code_start) fail("missing internal_code")
    code_tail = substr(row, code_start + length(code_marker))
    if (code_tail == "null}") {
      code_json = "null"
      code_is_null = 1
      code = ""
    } else {
      code_is_null = 0
      if (code == "") fail("internal_code must be null or nonempty")
      code_json = "\"" code "\""
    }
    canonical = "{\"event\":\"run_closed\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"close_state\":\"" state "\",\"internal_code\":" code_json "}"
    if (row != canonical || state !~ /^(complete|blocked|interrupted)$/) fail("invalid run_closed row")
    if (!code_is_null && !operator_code(code)) fail("invalid internal_code")
    if (state == "complete" && !code_is_null) fail("complete close cannot carry an internal code")
    if (state == "complete" && working_phase != "finalizing") fail("complete close requires finalizing")
    closed = 1
    close_state = state
    next
  }

  fail("unknown event")
}
END {
  if (invalid) exit 1
  if (!started) {
    print "lifecycle-fold: missing run_started" > "/dev/stderr"
    exit 1
  }
  selected = remaining = in_flight = evaluated = presented = terminally_skipped = 0
  for (identity in posting) {
    selected++
    state = posting[identity]
    if (state == "queued") remaining++
    else if (state == "evaluating") in_flight++
    else if (state == "evaluated") evaluated++
    else if (state == "presented") { evaluated++; presented++ }
    else if (state == "terminally_skipped") terminally_skipped++
  }
  started_count = accounted_count = blocking_attempt_failures = 0
  for (attempt_id in attempts_started) started_count++
  for (attempt_id in attempts_accounted) accounted_count++
  for (attempt_id in attempt_outcome) {
    outcome = attempt_outcome[attempt_id]
    logical = attempt_logical[attempt_id]
    if (logical_resolution[logical] == "summary_fallback") continue
    if (outcome == "quota_rejected" || outcome == "terminal_failure") blocking_attempt_failures++
    else if ((outcome == "worker_failed" || outcome == "retryable_failure") && logical_success_ordinal[logical] <= attempt_ordinal[attempt_id]) blocking_attempt_failures++
  }

  print "run_id=" run_id
  print "trigger=" run_trigger
  print "scheduler_id=" run_scheduler_id
  print "source_order=" run_source_order
  print "started_date=" started_date
  print "working_phase=" working_phase
  print "selected=" selected
  print "evaluated=" evaluated
  print "terminally_skipped=" terminally_skipped
  print "presented=" presented
  print "remaining=" remaining
  print "in_flight=" in_flight
  print "attempts_started=" started_count
  print "attempts_accounted=" accounted_count
  print "blocking_attempt_failures=" blocking_attempt_failures
  print "run_record_milestone=" (("final_run_record_written" in milestones) ? "true" : "false")
  print "digest_milestone=" (("final_digest_written" in milestones) ? "true" : "false")
  print "closed=" (closed ? "true" : "false")
  print "close_state=" close_state
}
' "$ledger" > "$folded" || exit 1

run_id=
trigger=
scheduler_id=
source_order=
started_date=
working_phase=
selected=0
evaluated=0
terminally_skipped=0
presented=0
remaining=0
in_flight=0
attempts_started=0
attempts_accounted=0
blocking_attempt_failures=0
run_record_milestone=false
digest_milestone=false
closed=false
close_state=open

while IFS='=' read -r key value; do
  case $key in
    run_id) run_id=$value ;;
    trigger) trigger=$value ;;
    scheduler_id) scheduler_id=$value ;;
    source_order) source_order=$value ;;
    started_date) started_date=$value ;;
    working_phase) working_phase=$value ;;
    selected) selected=$value ;;
    evaluated) evaluated=$value ;;
    terminally_skipped) terminally_skipped=$value ;;
    presented) presented=$value ;;
    remaining) remaining=$value ;;
    in_flight) in_flight=$value ;;
    attempts_started) attempts_started=$value ;;
    attempts_accounted) attempts_accounted=$value ;;
    blocking_attempt_failures) blocking_attempt_failures=$value ;;
    run_record_milestone) run_record_milestone=$value ;;
    digest_milestone) digest_milestone=$value ;;
    closed) closed=$value ;;
    close_state) close_state=$value ;;
    *) echo 'lifecycle-fold: internal fold output is invalid' >&2; exit 1 ;;
  esac
done < "$folded"

ledger_name=$(basename "$ledger")
[ "$ledger_name" = ".lifecycle-$run_id.jsonl" ] || {
  echo 'lifecycle-fold: ledger filename does not match the folded run_id' >&2
  exit 1
}
ledger_runs=$(CDPATH= cd -P "$(dirname "$ledger")" && pwd -P) || exit 1
workspace_runs=$(CDPATH= cd -P "$workspace/runs" && pwd -P) || {
  echo 'lifecycle-fold: WORKSPACE/runs does not exist' >&2
  exit 1
}
[ "$ledger_runs" = "$workspace_runs" ] || {
  echo 'lifecycle-fold: ledger does not belong to WORKSPACE/runs' >&2
  exit 1
}

final_run_record_written=false
final_digest_written=false
run_record=$workspace/runs/$run_id.json
reports_directory=$workspace/reports
digest=$reports_directory/$started_date-digest.md
[ -f "$run_record" ] && [ ! -L "$run_record" ] && final_run_record_written=true
if [ -d "$reports_directory" ] && [ ! -L "$reports_directory" ] \
   && [ -f "$digest" ] && [ ! -L "$digest" ]; then
  final_digest_written=true
fi

settled=$((evaluated + terminally_skipped))
ready_to_close=false
if [ "$working_phase" = finalizing ] \
   && [ "$remaining" -eq 0 ] \
   && [ "$in_flight" -eq 0 ] \
   && [ "$selected" -eq "$settled" ] \
   && [ "$attempts_started" -eq "$attempts_accounted" ] \
   && [ "$blocking_attempt_failures" -eq 0 ] \
   && [ "$final_run_record_written" = true ] \
   && [ "$final_digest_written" = true ] \
   && [ "$run_record_milestone" = true ] \
   && [ "$digest_milestone" = true ]; then
  ready_to_close=true
fi

if [ "$closed" = true ] && [ "$close_state" != complete ]; then
  ready_to_close=false
fi
if [ "$closed" = true ] && [ "$close_state" = complete ] && [ "$ready_to_close" != true ]; then
  echo 'lifecycle-fold: complete close contradicts the completion predicate' >&2
  exit 1
fi

phase=$working_phase
can_complete=false
if [ "$closed" = true ] && [ "$close_state" = complete ]; then
  phase=complete
  can_complete=true
fi

printf 'run_id=%s\n' "$run_id"
printf 'trigger=%s\n' "$trigger"
printf 'scheduler_id=%s\n' "$scheduler_id"
printf 'source_order=%s\n' "$source_order"
printf 'phase=%s\n' "$phase"
printf 'selected=%s\n' "$selected"
printf 'evaluated=%s\n' "$evaluated"
printf 'terminally_skipped=%s\n' "$terminally_skipped"
printf 'presented=%s\n' "$presented"
printf 'remaining=%s\n' "$remaining"
printf 'in_flight=%s\n' "$in_flight"
printf 'attempts_started=%s\n' "$attempts_started"
printf 'attempts_accounted=%s\n' "$attempts_accounted"
printf 'blocking_attempt_failures=%s\n' "$blocking_attempt_failures"
printf 'final_run_record_written=%s\n' "$final_run_record_written"
printf 'final_digest_written=%s\n' "$final_digest_written"
printf 'closed=%s\n' "$closed"
printf 'close_state=%s\n' "$close_state"
printf 'ready_to_close=%s\n' "$ready_to_close"
printf 'can_complete=%s\n' "$can_complete"
