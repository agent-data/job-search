#!/bin/sh
# search-jobs.sh — run one search and record the call that ran it, in one step.
#
# Usage: search-jobs.sh --query-id ID --source S [--workspace W] -- <the route's own parameters>
#   --query-id ID   required. The id of the query in config.yaml this search runs. run-counts.sh
#                   groups a run's search calls by source and query id, so a wrong id files the
#                   call under the wrong query.
#   --source S      required. The source to search; one search-jobs call reaches one source. This
#                   script passes it to the route, so it is not one of the parameters after `--`.
#   --workspace W   resolve against W instead of asking workspace-discovery.sh. Omit it in a run;
#                   the tests pass it, because their workspace is a temporary directory
#                   workspace-discovery.sh would never find.
#   --              required. Everything after it goes to the route unchanged; a call carrying no
#                   route parameters is refused.
#
# Not for any other route. Reading one posting is fetch-posting.sh.
#
# Prints one line on stdout: response=<path to the saved body>. It is printed whenever the call
# itself succeeded, including when record-api-response.sh then refuses the body and this exits 1 —
# the search ran and its rows are saved, so the path is worth having either way.
#
# Everything after `--` goes to the route unchanged, so the parameter names come from
# `agent-data docs` and this script never has to know them. job-search-run/SKILL.md:42-43 says to
# read the route list once with `agent-data docs` and take every parameter name from it, and a
# wrapper with a fixed flag per parameter would stop matching that list the next time the route
# gains one.
#
# A run's billable-call count is built from the `call` events in jobs.jsonl, and
# record-api-response.sh is the only thing that writes one. Calling agent-data on its own leaves no
# event, so the call is charged and absent from the count.
#
# In a run nothing passes a workspace or a run id: both come from resolve-run.sh.
#
# There is no flag to swap the command this runs. The tests spend real calls, because a wrapper
# that makes a call and records it cannot be proven against something that never calls anything.
#
# Exit 0: the search ran and its rows are in the log, or it returned none and there were none to
#         record.
# Exit 1: the call failed, or record-api-response.sh refused the response. The `call` event is
#         recorded either way, because a failed call was still charged. A failed call prints nothing
#         on stdout and puts the error body on stderr after record-api-response.sh's diagnostic; a
#         refused response prints the response= line, and the body is in the file that line names.
# Exit 2: bad arguments, a --query-id or a --source this script will not take, or no single open run
#         to record against. Nothing was called.
set -u

here=$(dirname "$0")

usage() {
  printf 'usage: search-jobs.sh --query-id ID --source S [--workspace W] -- <route params>\n' >&2
}

query_id='' src='' ws_flag=''
while [ $# -gt 0 ]; do
  case $1 in
    --query-id)  [ $# -ge 2 ] || { usage; exit 2; }; query_id=$2; shift 2 ;;
    --source)    [ $# -ge 2 ] || { usage; exit 2; }; src=$2; shift 2 ;;
    --workspace) [ $# -ge 2 ] || { usage; exit 2; }; ws_flag=$2; shift 2 ;;
    --) shift; break ;;
    *) usage; exit 2 ;;
  esac
done
[ -n "$query_id" ] || { usage; exit 2; }
[ -n "$src" ]      || { usage; exit 2; }
# `--` with nothing after it, and no `--` at all, both land here with no arguments left. Measured
# 2026-08-11 with this check removed, against an open run: the agent-data CLI refuses the call
# itself, and the error body it writes carries "source": "cli", code missing_required_param,
# message `Missing required parameter: keywords (in: query)` and no request_id — so the API never
# saw the call. The failed-call branch below still recorded a `call` event for it, which would put
# one call the API never received into the run's metered-call count.
[ $# -ge 1 ]       || { usage; exit 2; }

# Both values supply part of the name of the file this script writes the response to, so both are
# checked here, before that path is built and before anything is spent. check-record-args.sh below
# does not cover this rule: record-api-response.sh takes a slash in either value, so the reason to
# refuse one belongs where the path is made. fetch-posting.sh checks its --posting-id in the same
# place for the same reason.
#
# Measured 2026-08-11 against an open run, with this check removed and agent-data off PATH:
# `--query-id ../../escaped` left the shell unable to open
# runs/.scratch/<run_id>/search-../../escaped-linkedin.json, so the redirection failed, agent-data
# never ran, and the failed-call branch below then ran against an error file that was never created.
# Exit 1, nothing on stdout, and three lines on stderr, not one of which says which argument was
# wrong.
#
# A control character in either value is refused by check-record-args.sh, so it is not repeated
# here.
check_no_slash() {
  case $2 in
    */*)
      printf 'search-jobs.sh: %s may hold no slash: %s\n' "$1" "$2" >&2
      printf 'search-jobs.sh:   it supplies part of a file name under this run, not a path\n' >&2
      exit 2 ;;
  esac
}
check_no_slash --query-id "$query_id"
check_no_slash --source "$src"

# Before the call, not after it. record-api-response.sh exits 2 on a --route, a --source or a
# --query-id it will not take, and every one of those checks runs before it writes anything, so
# handing it a refused value once the call has been made leaves the call billed and no `call` event
# naming it — the exact loss this script exists to prevent. check-record-args.sh holds the rules and
# the measurement, and it takes record-api-response.sh's own flag names, so the same arguments go to
# both.
#
# This sits with the argument checks rather than after resolve-run.sh, so a bad value is named
# whether or not a run is open.
sh "$here/check-record-args.sh" --route search-jobs --source "$src" --query-id "$query_id" || exit 2

# --workspace is passed on only when the caller gave one, so resolve-run.sh asks
# workspace-discovery.sh in a run and takes the temporary directory in a test. The expansion is
# unquoted so that an empty ws_flag adds no argument at all; the inner quotes still hold a workspace
# path with a space together. The measurement behind that is written at fetch-posting.sh:114-119.
resolved=$(sh "$here/resolve-run.sh" ${ws_flag:+--workspace "$ws_flag"}) || exit 2
ws=$(printf '%s\n' "$resolved" | sed -n 's/^workspace=//p')
run_id=$(printf '%s\n' "$resolved" | sed -n 's/^run_id=//p')

out_dir=$ws/runs/.scratch/$run_id
mkdir -p "$out_dir" || { printf 'search-jobs.sh: cannot make %s\n' "$out_dir" >&2; exit 2; }

# The query id and the source name the file, so two subagents searching different queries in one run
# never write the same path. Two searches naming the same query id and the same source do reuse the
# path, and the second overwrites the first.
resp=$out_dir/search-$query_id-$src.json
err=$out_dir/search-$query_id-$src.err

# The listing id is the one agent-data-reference/SKILL.md names — `command grep -n f9a6ec16
# skills/agent-data-reference/SKILL.md`. It is copied here because a shell script cannot read a
# value out of a skill document, so a change to the listing has to reach every copy.
#
# "$@" holds exactly the route parameters, so a value carrying a space stays one argument.
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 search-jobs --source "$src" "$@" \
  > "$resp" 2> "$err"
callstatus=$?

# A failed call leaves stdout empty and the body on stderr, so the file with the body is the one
# handed over. Measured 2026-08-11 with `--source no-such-source`: exit 1, zero bytes on stdout, and
# an error body on stderr carrying status 400 and a request_id. record-api-response.sh records the
# call either way.
if [ "$callstatus" -ne 0 ]; then
  sh "$here/record-api-response.sh" "$run_id" "$ws/jobs.jsonl" "$err" \
     --route search-jobs --query-id "$query_id" --source "$src" >&2
  cat "$err" >&2
  exit 1
fi

sh "$here/record-api-response.sh" "$run_id" "$ws/jobs.jsonl" "$resp" \
   --route search-jobs --query-id "$query_id" --source "$src" >&2
recstatus=$?

printf 'response=%s\n' "$resp"
[ "$recstatus" -eq 0 ] || exit 1
exit 0
