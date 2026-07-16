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
check_payload_value() {
  value=$1
  case $value in
    *'
'*) reject 'multiline values are prohibited' ;;
  esac
  lower=$(printf '%s\n' "$value" | LC_ALL=C tr '[:upper:]' '[:lower:]')
  if printf '%s\n' "$lower" | LC_ALL=C grep -Eq '(^|[^a-z0-9])(api[_-]?keys?|auth([_-]?headers?|orization)|bearer|environment[_-]?dumps?|pagination[_-]?cursors?|cursors?|opaque[_-]?api[_-]?continuation[_-]?tokens?|continuation[_-]?tokens?|full[_-]?job[_-]?descriptions?|job[_-]?descriptions?|preferences?[_-]?text|match[_-]?prose)([^a-z0-9]|$)'; then
    reject 'prohibited secret, cursor, environment, description, preference, or match field'
  fi
  if printf '%s\n' "$lower" | LC_ALL=C grep -Eq '(^|[^a-z0-9])sk-[a-z0-9_-]{8,}([^a-z0-9]|$)'; then
    reject 'API-key-shaped values are prohibited'
  fi
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
  check_payload_value "$value"
done

printf '%s\n' "$run_id" | LC_ALL=C grep -Eq \
  '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$' \
  || reject 'invalid run_id'
printf '%s\n' "$timestamp" | LC_ALL=C grep -Eq \
  '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$' \
  || reject 'invalid ISO timestamp'

runs_dir=$(dirname "$ledger")
[ "$(basename "$runs_dir")" = runs ] || reject 'ledger must be under WORKSPACE/runs'
[ "$(basename "$ledger")" = ".lifecycle-$run_id.jsonl" ] \
  || reject 'ledger filename does not match run_id'

if [ "$command" = start ]; then
  [ "$#" -eq 0 ] || usage
  [ ! -e "$ledger" ] || reject 'run_started already exists'
  [ -d "$runs_dir" ] || mkdir -p "$runs_dir" || reject 'could not create runs directory'
  append_line "{\"event\":\"run_started\",\"run_id\":\"$run_id\",\"ts\":\"$timestamp\",\"phase\":\"preflight\"}"
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
    [ "$next_rank" -gt "$current_rank" ] || reject 'phase transition must move forward'
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
    restricted "$source_id" || reject 'invalid source_id'
    restricted "$brief_revision" || reject 'invalid brief revision'
    append_line "{\"event\":\"posting_state\",\"run_id\":\"$run_id\",\"ts\":\"$timestamp\",\"source\":\"$source\",\"source_id\":\"$source_id\",\"state\":\"$posting_state\",\"brief_revision\":\"$brief_revision\"}"
    ;;

  attempt-started)
    [ "$#" -eq 2 ] || usage
    attempt_id=$1
    operation=$2
    restricted "$attempt_id" || reject 'invalid attempt_id'
    restricted "$operation" || reject 'invalid operation'
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
    restricted "$attempt_id" || reject 'invalid attempt_id'
    case $metered in true|false) : ;; *) reject 'metered must be true or false' ;; esac
    restricted "$outcome" || reject 'invalid outcome'
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
      restricted "$request_id" || reject 'invalid request_id'
      request_json="\"$request_id\""
    fi
    append_line "{\"event\":\"attempt_accounted\",\"run_id\":\"$run_id\",\"ts\":\"$timestamp\",\"attempt_id\":\"$attempt_id\",\"metered\":$metered,\"outcome\":\"$outcome\",\"request_id\":$request_json}"
    ;;

  revision)
    [ "$#" -eq 1 ] || usage
    brief_revision=$1
    restricted "$brief_revision" || reject 'invalid brief revision'
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
      restricted "$internal_code" || reject 'invalid internal code'
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
