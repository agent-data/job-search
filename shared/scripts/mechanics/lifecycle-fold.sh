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
function restricted(value) {
  return value ~ /^[A-Za-z0-9][A-Za-z0-9._:@\/+%~-]*$/ && length(value) <= 256
}
function prohibited(value, lower) {
  lower = tolower(value)
  return lower ~ /(^|[^a-z0-9])(api[_-]?keys?|auth([_-]?headers?|orization)|bearer|environment[_-]?dumps?|pagination[_-]?cursors?|cursors?|opaque[_-]?api[_-]?continuation[_-]?tokens?|continuation[_-]?tokens?|full[_-]?job[_-]?descriptions?|job[_-]?descriptions?|preferences?[_-]?text|match[_-]?prose)([^a-z0-9]|$)/ \
      || lower ~ /(^|[^a-z0-9])sk-[a-z0-9_-][a-z0-9_-][a-z0-9_-][a-z0-9_-][a-z0-9_-][a-z0-9_-][a-z0-9_-][a-z0-9_-]/
}
function valid_run_id(value) {
  return value ~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]-[0-9][0-9]-[0-9][0-9]Z$/
}
function valid_timestamp(value) {
  return value ~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9](\.[0-9][0-9]*)?(Z|[+-][0-9][0-9]:[0-9][0-9])$/
}
function common_fields(row, expected_event, rid, timestamp) {
  rid = string_value(row, "run_id")
  timestamp = string_value(row, "ts")
  if (!valid_run_id(rid) || !valid_timestamp(timestamp)) fail("invalid run identity or timestamp")
  if (prohibited(rid) || prohibited(timestamp)) fail("prohibited value")
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
    canonical = "{\"event\":\"run_started\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"phase\":\"preflight\"}"
    if (row != canonical || NR != 1 || started || phase != "preflight") fail("invalid run_started row")
    started = 1
    run_id = rid
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
    if (phase_rank[phase] <= current_rank) fail("phase transition is not forward")
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
    if (state !~ /^(queued|evaluating|evaluated|presented|terminally_skipped)$/) fail("invalid posting state")
    if (prohibited(source_id) || prohibited(revision)) fail("prohibited posting value")
    posting[source SUBSEP source_id] = state
    next
  }

  if (event == "attempt_started") {
    attempt_id = string_value(row, "attempt_id")
    operation = string_value(row, "operation")
    canonical = "{\"event\":\"attempt_started\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"attempt_id\":\"" attempt_id "\",\"operation\":\"" operation "\"}"
    if (row != canonical || !restricted(attempt_id) || !restricted(operation)) fail("invalid attempt_started row")
    if (prohibited(attempt_id) || prohibited(operation)) fail("prohibited attempt value")
    if (attempt_id in attempts_started) fail("duplicate attempt_started")
    attempts_started[attempt_id] = 1
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
      request_id = ""
    } else {
      request_json = "\"" request_id "\""
    }
    canonical = "{\"event\":\"attempt_accounted\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"attempt_id\":\"" attempt_id "\",\"metered\":" metered ",\"outcome\":\"" outcome "\",\"request_id\":" request_json "}"
    if (row != canonical || !restricted(attempt_id) || !restricted(outcome)) fail("invalid attempt_accounted row")
    if (request_id != "" && !restricted(request_id)) fail("invalid request_id")
    if (prohibited(attempt_id) || prohibited(outcome) || prohibited(request_id)) fail("prohibited accounting value")
    if (!(attempt_id in attempts_started)) fail("attempt_accounted has no prior start")
    if (attempt_id in attempts_accounted) fail("duplicate attempt_accounted")
    attempts_accounted[attempt_id] = 1
    next
  }

  if (event == "brief_revision") {
    revision = string_value(row, "brief_revision")
    canonical = "{\"event\":\"brief_revision\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"brief_revision\":\"" revision "\"}"
    if (row != canonical || !restricted(revision) || prohibited(revision)) fail("invalid brief_revision row")
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
      code = ""
    } else {
      code_json = "\"" code "\""
    }
    canonical = "{\"event\":\"run_closed\",\"run_id\":\"" rid "\",\"ts\":\"" timestamp "\",\"close_state\":\"" state "\",\"internal_code\":" code_json "}"
    if (row != canonical || state !~ /^(complete|blocked|interrupted)$/) fail("invalid run_closed row")
    if (code != "" && (!restricted(code) || prohibited(code))) fail("invalid internal_code")
    if (state == "complete" && code != "") fail("complete close cannot carry an internal code")
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
  started_count = accounted_count = 0
  for (attempt_id in attempts_started) started_count++
  for (attempt_id in attempts_accounted) accounted_count++

  print "run_id=" run_id
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
  print "run_record_milestone=" (("final_run_record_written" in milestones) ? "true" : "false")
  print "digest_milestone=" (("final_digest_written" in milestones) ? "true" : "false")
  print "closed=" (closed ? "true" : "false")
  print "close_state=" close_state
}
' "$ledger" > "$folded" || exit 1

run_id=
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
run_record_milestone=false
digest_milestone=false
closed=false
close_state=open

while IFS='=' read -r key value; do
  case $key in
    run_id) run_id=$value ;;
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
[ -f "$workspace/runs/$run_id.json" ] && final_run_record_written=true
[ -f "$workspace/reports/$started_date-digest.md" ] && final_digest_written=true

settled=$((evaluated + terminally_skipped))
ready_to_close=false
if [ "$working_phase" = finalizing ] \
   && [ "$remaining" -eq 0 ] \
   && [ "$in_flight" -eq 0 ] \
   && [ "$selected" -eq "$settled" ] \
   && [ "$attempts_started" -eq "$attempts_accounted" ] \
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
printf 'phase=%s\n' "$phase"
printf 'selected=%s\n' "$selected"
printf 'evaluated=%s\n' "$evaluated"
printf 'terminally_skipped=%s\n' "$terminally_skipped"
printf 'presented=%s\n' "$presented"
printf 'remaining=%s\n' "$remaining"
printf 'in_flight=%s\n' "$in_flight"
printf 'attempts_started=%s\n' "$attempts_started"
printf 'attempts_accounted=%s\n' "$attempts_accounted"
printf 'final_run_record_written=%s\n' "$final_run_record_written"
printf 'final_digest_written=%s\n' "$final_digest_written"
printf 'closed=%s\n' "$closed"
printf 'close_state=%s\n' "$close_state"
printf 'ready_to_close=%s\n' "$ready_to_close"
printf 'can_complete=%s\n' "$can_complete"
