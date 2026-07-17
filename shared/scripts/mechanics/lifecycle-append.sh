#!/bin/sh
# lifecycle-append.sh — validate and append one canonical lifecycle event.
#
# The run coordinator is the only caller/writer. Values are closed enums or restricted nonsecret
# identifiers; free-form posting, preference, error, secret, environment, cursor, and continuation-token
# content is rejected. Existing ledger rows are validated by lifecycle-fold.sh before every append.
#
# Usage: see shared/references/run-lifecycle.md, "Scripted append and fold/check operations".
set -u

usage() {
  echo 'usage: lifecycle-append.sh LEDGER COMMAND RUN_ID ISO_TIMESTAMP [COMMAND_ARGS...]' >&2
  exit 2
}
reject() {
  echo "lifecycle-append: $1" >&2
  exit 1
}
restricted() {
  value=$1
  [ -n "$value" ] && [ "${#value}" -le 256 ] \
    && printf '%s\n' "$value" | LC_ALL=C grep -Eq '^[A-Za-z0-9][A-Za-z0-9._:@/+%~-]*$'
}
single_line() {
  _line_value=$1
  case $_line_value in
    *'
'*) reject 'multiline values are prohibited' ;;
  esac
}
payload_identifier() {
  _field=$1
  _field_value=$2
  restricted "$_field_value" || reject "invalid $_field"
  _lower=$(printf '%s\n' "$_field_value" | LC_ALL=C tr '[:upper:]' '[:lower:]')
  if printf '%s\n' "$_lower" | LC_ALL=C grep -Eq '%[0-9a-f]{2}'; then
    reject "$_field contains a prohibited percent-encoded octet"
  fi
  if [ "$_field" != operation ]; then
    if printf '%s\n' "$_lower" | LC_ALL=C grep -Eq '(^|[._:@/+%~-])(api[_-]?keys?|authorization|auth[_-]?headers?|bearer|environment[_-]?dumps?|pagination[_-]?cursors?|cursors?|next[_-]?page[_-]?tokens?|page[_-]?tokens?|opaque[_-]?api[_-]?continuation[_-]?tokens?|continuation[_-]?tokens?|full[_-]?job[_-]?descriptions?|job[_-]?descriptions?|preferences?[_-]?text|match[_-]?prose)([._:@/+%~-]|$)'; then
      reject "$_field contains a prohibited field or opaque-token signature"
    fi
  fi
  if printf '%s\n' "$_lower" | LC_ALL=C grep -Eq '(^|[^a-z0-9])(sk-[a-z0-9_-]{8,}|gh[pousr]_[a-z0-9_-]{20,}|github_pat_[a-z0-9_-]{20,}|akia[a-z0-9_-]{16,})([^a-z0-9]|$)'; then
    reject "$_field contains an API-key-shaped value"
  fi
}
operator_code() {
  _operator_code=$1
  [ "${#_operator_code}" -le 256 ] \
    && printf '%s\n' "$_operator_code" | LC_ALL=C grep -Eq '^E-[A-Z0-9]+(-[A-Z0-9]+)*$'
}
decimal() {
  _decimal=$1
  while [ "${_decimal#0}" != "$_decimal" ]; do
    _decimal=${_decimal#0}
  done
  [ -n "$_decimal" ] || _decimal=0
  printf '%s\n' "$_decimal"
}
valid_calendar_date() {
  _date=$1
  _year_text=${_date%%-*}
  _date_rest=${_date#*-}
  _month_text=${_date_rest%%-*}
  _day_text=${_date_rest##*-}
  _year=$(decimal "$_year_text")
  _month=$(decimal "$_month_text")
  _day=$(decimal "$_day_text")
  [ "$_year" -ge 1 ] && [ "$_month" -ge 1 ] && [ "$_month" -le 12 ] \
    && [ "$_day" -ge 1 ] || return 1
  case $_month in
    1|3|5|7|8|10|12) _max_day=31 ;;
    4|6|9|11) _max_day=30 ;;
    2)
      _max_day=28
      if [ $((_year % 400)) -eq 0 ] \
         || { [ $((_year % 4)) -eq 0 ] && [ $((_year % 100)) -ne 0 ]; }; then
        _max_day=29
      fi
      ;;
  esac
  [ "$_day" -le "$_max_day" ]
}
valid_clock() {
  _clock=$1
  _clock_separator=$2
  if [ "$_clock_separator" = : ]; then
    _hour_text=${_clock%%:*}
    _clock_rest=${_clock#*:}
    _minute_text=${_clock_rest%%:*}
    _second_text=${_clock_rest##*:}
  else
    _hour_text=${_clock%%-*}
    _clock_rest=${_clock#*-}
    _minute_text=${_clock_rest%%-*}
    _second_text=${_clock_rest##*-}
  fi
  _hour=$(decimal "$_hour_text")
  _minute=$(decimal "$_minute_text")
  _second=$(decimal "$_second_text")
  [ "$_hour" -le 23 ] && [ "$_minute" -le 59 ] && [ "$_second" -le 59 ]
}
valid_offset() {
  _timestamp=$1
  case $_timestamp in
    *Z) return 0 ;;
  esac
  _offset=$(printf '%s\n' "$_timestamp" | awk '{ print substr($0, length($0) - 5) }')
  _offset_hour_text=$(printf '%s\n' "$_offset" | cut -c2-3)
  _offset_minute_text=$(printf '%s\n' "$_offset" | cut -c5-6)
  _offset_hour=$(decimal "$_offset_hour_text")
  _offset_minute=$(decimal "$_offset_minute_text")
  [ "$_offset_hour" -le 14 ] && [ "$_offset_minute" -le 59 ] \
    && { [ "$_offset_hour" -lt 14 ] || [ "$_offset_minute" -eq 0 ]; }
}
valid_run_id_value() {
  _run_id=$1
  printf '%s\n' "$_run_id" | LC_ALL=C grep -Eq \
    '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$' || return 1
  _run_date=${_run_id%%T*}
  _run_clock=${_run_id#*T}
  _run_clock=${_run_clock%Z}
  valid_calendar_date "$_run_date" && valid_clock "$_run_clock" -
}
valid_timestamp_value() {
  _iso_timestamp=$1
  printf '%s\n' "$_iso_timestamp" | LC_ALL=C grep -Eq \
    '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$' || return 1
  _iso_date=${_iso_timestamp%%T*}
  _iso_time_zone=${_iso_timestamp#*T}
  _iso_clock=$(printf '%s\n' "$_iso_time_zone" | cut -c1-8)
  valid_calendar_date "$_iso_date" && valid_clock "$_iso_clock" : && valid_offset "$_iso_timestamp"
}
phase_rank() {
  case $1 in
    preflight) printf '1\n' ;;
    searching) printf '2\n' ;;
    selection_settled) printf '3\n' ;;
    reviewing_initial_batch) printf '4\n' ;;
    early_results_shown) printf '5\n' ;;
    reviewing_remaining) printf '6\n' ;;
    finalizing) printf '7\n' ;;
    *) return 1 ;;
  esac
}
state_value() {
  key=$1
  printf '%s\n' "$fold_state" | awk -F= -v wanted="$key" '$1 == wanted { print substr($0, length($1) + 2); exit }'
}
append_line() {
  printf '%s\n' "$1" >> "$ledger" || reject 'could not append ledger row'
}

[ "$#" -ge 4 ] || usage
ledger=$1
command=$2
run_id=$3
timestamp=$4
shift 4

case $ledger in
  *'
'*) reject 'multiline ledger paths are prohibited' ;;
esac
for value in "$run_id" "$timestamp" "$@"; do
  single_line "$value"
done

valid_run_id_value "$run_id" || reject 'invalid run_id'
valid_timestamp_value "$timestamp" || reject 'invalid ISO timestamp'

runs_dir=$(dirname "$ledger")
[ "$(basename "$runs_dir")" = runs ] || reject 'ledger must be under WORKSPACE/runs'
[ "$(basename "$ledger")" = ".lifecycle-$run_id.jsonl" ] \
  || reject 'ledger filename does not match run_id'

if [ "$command" = start ]; then
  [ "$#" -eq 2 ] || usage
  trigger=$1
  scheduler_id=$2
  case $trigger in
    manual)
      [ "$scheduler_id" = - ] || reject 'manual trigger requires null scheduler_id'
      scheduler_json=null
      ;;
    scheduled|canary)
      [ "$scheduler_id" != - ] || reject 'scheduled and canary triggers require scheduler_id'
      payload_identifier scheduler_id "$scheduler_id"
      scheduler_json="\"$scheduler_id\""
      ;;
    *) reject 'unknown trigger' ;;
  esac
  [ ! -e "$ledger" ] || reject 'run_started already exists'
  [ -d "$runs_dir" ] || mkdir -p "$runs_dir" || reject 'could not create runs directory'
  append_line "{\"event\":\"run_started\",\"run_id\":\"$run_id\",\"ts\":\"$timestamp\",\"phase\":\"preflight\",\"trigger\":\"$trigger\",\"scheduler_id\":$scheduler_json}"
  exit 0
fi

[ -f "$ledger" ] || reject 'ledger does not exist; start the run first'
workspace=$(dirname "$runs_dir")
script_dir=$(CDPATH= cd -P "$(dirname "$0")" && pwd -P) || exit 2
fold_state=$("$script_dir/lifecycle-fold.sh" "$ledger" "$workspace") \
  || reject 'existing ledger is malformed or contradictory'
[ "$(state_value run_id)" = "$run_id" ] || reject 'run_id does not match the ledger'
[ "$(state_value closed)" = false ] || reject 'closed ledgers accept no later events'

case $command in
  phase)
    [ "$#" -eq 1 ] || usage
    phase=$1
    [ "$phase" != complete ] || reject 'phase complete is established only by close complete'
    next_rank=$(phase_rank "$phase") || reject 'unknown phase'
    current_phase=$(state_value phase)
    current_rank=$(phase_rank "$current_phase") || reject 'ledger has an invalid current phase'
    [ "$next_rank" -eq $((current_rank + 1)) ] \
      || reject 'phase transition must advance exactly one canonical phase'
    append_line "{\"event\":\"phase_changed\",\"run_id\":\"$run_id\",\"ts\":\"$timestamp\",\"phase\":\"$phase\"}"
    ;;

  posting)
    [ "$#" -eq 4 ] || usage
    source=$1
    source_id=$2
    posting_state=$3
    brief_revision=$4
    case $source in linkedin|ashby|greenhouse|lever) : ;; *) reject 'unknown source' ;; esac
    case $posting_state in
      queued|evaluating|evaluated|presented|terminally_skipped) : ;;
      *) reject 'unknown posting state' ;;
    esac
    payload_identifier source_id "$source_id"
    payload_identifier brief_revision "$brief_revision"
    identity_marker="\"source\":\"$source\",\"source_id\":\"$source_id\""
    prior_row=$(grep -F "$identity_marker" "$ledger" | tail -n 1)
    prior_state=$(printf '%s\n' "$prior_row" \
      | sed -n 's/.*"state":"\([^"]*\)".*/\1/p')
    current_phase=$(state_value phase)
    case $posting_state in
      queued)
        [ -z "$prior_state" ] || reject 'selected posting was already queued'
        [ "$current_phase" = searching ] \
          || reject 'selected postings must be queued while selection is settling'
        ;;
      evaluating)
        [ "$prior_state" = queued ] || reject 'evaluating requires prior queued state'
        case $current_phase in
          reviewing_initial_batch|reviewing_remaining) : ;;
          *) reject 'evaluating requires a review phase' ;;
        esac
        ;;
      evaluated|terminally_skipped)
        [ "$prior_state" = evaluating ] \
          || reject 'terminal posting state requires prior evaluating state'
        case $current_phase in
          reviewing_initial_batch|reviewing_remaining) : ;;
          *) reject 'terminal posting state requires a review phase' ;;
        esac
        ;;
      presented)
        [ "$prior_state" = evaluated ] || reject 'presented requires prior evaluated state'
        case $current_phase in
          reviewing_initial_batch|reviewing_remaining) : ;;
          *) reject 'presented requires a review phase' ;;
        esac
        ;;
    esac
    append_line "{\"event\":\"posting_state\",\"run_id\":\"$run_id\",\"ts\":\"$timestamp\",\"source\":\"$source\",\"source_id\":\"$source_id\",\"state\":\"$posting_state\",\"brief_revision\":\"$brief_revision\"}"
    ;;

  attempt-started)
    [ "$#" -eq 2 ] || usage
    attempt_id=$1
    operation=$2
    payload_identifier attempt_id "$attempt_id"
    payload_identifier operation "$operation"
    if grep -F '"event":"attempt_started"' "$ledger" \
       | grep -Fq "\"attempt_id\":\"$attempt_id\""; then
      reject 'attempt_id was already started'
    fi
    append_line "{\"event\":\"attempt_started\",\"run_id\":\"$run_id\",\"ts\":\"$timestamp\",\"attempt_id\":\"$attempt_id\",\"operation\":\"$operation\"}"
    ;;

  attempt-accounted)
    [ "$#" -eq 4 ] || usage
    attempt_id=$1
    metered=$2
    outcome=$3
    request_id=$4
    payload_identifier attempt_id "$attempt_id"
    case $metered in true|false) : ;; *) reject 'metered must be true or false' ;; esac
    payload_identifier outcome "$outcome"
    if ! grep -F '"event":"attempt_started"' "$ledger" \
         | grep -Fq "\"attempt_id\":\"$attempt_id\""; then
      reject 'attempt_accounted requires one prior attempt_started'
    fi
    if grep -F '"event":"attempt_accounted"' "$ledger" \
       | grep -Fq "\"attempt_id\":\"$attempt_id\""; then
      reject 'attempt_id was already accounted'
    fi
    if [ "$request_id" = - ]; then
      request_json=null
    else
      payload_identifier request_id "$request_id"
      request_json="\"$request_id\""
    fi
    append_line "{\"event\":\"attempt_accounted\",\"run_id\":\"$run_id\",\"ts\":\"$timestamp\",\"attempt_id\":\"$attempt_id\",\"metered\":$metered,\"outcome\":\"$outcome\",\"request_id\":$request_json}"
    ;;

  revision)
    [ "$#" -eq 1 ] || usage
    brief_revision=$1
    payload_identifier brief_revision "$brief_revision"
    append_line "{\"event\":\"brief_revision\",\"run_id\":\"$run_id\",\"ts\":\"$timestamp\",\"brief_revision\":\"$brief_revision\"}"
    ;;

  milestone)
    [ "$#" -eq 1 ] || usage
    milestone=$1
    case $milestone in
      early_results_shown|final_run_record_written|final_digest_written) : ;;
      *) reject 'unknown milestone' ;;
    esac
    append_line "{\"event\":\"milestone\",\"run_id\":\"$run_id\",\"ts\":\"$timestamp\",\"milestone\":\"$milestone\"}"
    ;;

  close)
    [ "$#" -eq 2 ] || usage
    close_state=$1
    internal_code=$2
    case $close_state in complete|blocked|interrupted) : ;; *) reject 'unknown close state' ;; esac
    if [ "$internal_code" = - ]; then
      code_json=null
    else
      operator_code "$internal_code" || reject 'invalid internal code'
      code_json="\"$internal_code\""
    fi
    if [ "$close_state" = complete ]; then
      [ "$internal_code" = - ] || reject 'complete close cannot carry an internal code'
      [ "$(state_value ready_to_close)" = true ] \
        || reject 'completion predicate is not ready; refusing complete close'
    fi
    append_line "{\"event\":\"run_closed\",\"run_id\":\"$run_id\",\"ts\":\"$timestamp\",\"close_state\":\"$close_state\",\"internal_code\":$code_json}"
    ;;

  *) usage ;;
esac
