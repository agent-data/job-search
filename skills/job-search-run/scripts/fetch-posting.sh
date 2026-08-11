#!/bin/sh
# fetch-posting.sh — read one posting and record the call that read it, in one step.
#
# Usage: fetch-posting.sh --posting-id P --source-url U --source S [--workspace W]
#   --posting-id P  required. The `posting_id_at_seen` in the row list-detail-read-queue.sh printed
#                   for this posting.
#   --source-url U  required. The same row's `source_url`, which the route matches the posting
#                   against; a url from anywhere else is refused.
#   --source S      required. The same row's `source`.
#   --workspace W   resolve against W instead of asking workspace-discovery.sh. Omit it in a run;
#                   the tests pass it.
#
# The posting must be one a search of this open run surfaced, or record-api-response.sh refuses the
# response and this exits 1. Take the three values from one line of what list-detail-read-queue.sh
# prints rather than composing them.
#
# Not for reading a posting outside a run: there is no run to bill the call to and no log to record
# it in. That case is the `get-posting` recipe in the agent-data-reference skill.
#
# Prints one line on stdout: response=<path to the saved body>.
#
# A run's billable-call count is built from the `call` events in jobs.jsonl, and
# record-api-response.sh is the only thing that writes one. Calling agent-data on its own leaves no
# event, so the call is charged and absent from the count. Measured on the 2026-08-11 opencode run:
# 35 get-posting calls were made and 14 reached the workspace log.
#
# The workspace and the run id come from resolve-run.sh, so no caller passes either.
#
# There is no flag to swap the command this runs. The tests spend real calls, because a wrapper
# that makes a call and records it cannot be proven against something that never calls anything.
#
# Exit 0: the posting was read and both events are in the log.
# Exit 1: the call failed, or the response was refused. The `call` event is recorded either way,
#         because a failed call was still charged. stderr carries the body.
# Exit 2: bad arguments, or no single open run to record against. Nothing was called.
set -u

here=$(dirname "$0")

usage() {
  printf 'usage: fetch-posting.sh --posting-id P --source-url U --source S [--workspace W]\n' >&2
}

posting_id='' source_url='' src='' ws_flag=''
while [ $# -gt 0 ]; do
  case $1 in
    --posting-id) [ $# -ge 2 ] || { usage; exit 2; }; posting_id=$2; shift 2 ;;
    --source-url) [ $# -ge 2 ] || { usage; exit 2; }; source_url=$2; shift 2 ;;
    --source)     [ $# -ge 2 ] || { usage; exit 2; }; src=$2; shift 2 ;;
    --workspace)  [ $# -ge 2 ] || { usage; exit 2; }; ws_flag=$2; shift 2 ;;
    *) usage; exit 2 ;;
  esac
done
[ -n "$posting_id" ] || { usage; exit 2; }
[ -n "$source_url" ] || { usage; exit 2; }
[ -n "$src" ]        || { usage; exit 2; }

# --workspace is passed on only when the caller gave one, so resolve-run.sh asks
# workspace-discovery.sh in a run and takes the temporary directory in a test. The expansion is
# unquoted so that an empty ws_flag adds no argument at all; the inner quotes still hold a workspace
# path with a space together. Measured under sh, dash and bash: with ws_flag set to `/a work space`
# the called script receives two arguments, `--workspace` and `/a work space`, and with ws_flag
# empty it receives none.
resolved=$(sh "$here/resolve-run.sh" ${ws_flag:+--workspace "$ws_flag"}) || exit 2
ws=$(printf '%s\n' "$resolved" | sed -n 's/^workspace=//p')
run_id=$(printf '%s\n' "$resolved" | sed -n 's/^run_id=//p')

out_dir=$ws/runs/.scratch/$run_id
mkdir -p "$out_dir" || { printf 'fetch-posting.sh: cannot make %s\n' "$out_dir" >&2; exit 2; }

# The posting id names the file, so two subagents reading different postings in one run never write
# the same path. Two reads of one posting do reuse the path, and the second overwrites the first
# with the same posting's body.
resp=$out_dir/detail-$posting_id.json
err=$out_dir/detail-$posting_id.err

# The listing id is the one agent-data-reference/SKILL.md names — `command grep -n f9a6ec16
# skills/agent-data-reference/SKILL.md`. It is copied here because a shell script cannot read a
# value out of a skill document, so a change to the listing has to reach both copies.
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 get-posting \
  --posting_id "$posting_id" --source_url "$source_url" --source "$src" \
  > "$resp" 2> "$err"
callstatus=$?

# A failed call leaves stdout empty and the body on stderr, so the file with the body is the one
# handed over. record-api-response.sh records the call either way.
if [ "$callstatus" -ne 0 ]; then
  sh "$here/record-api-response.sh" "$run_id" "$ws/jobs.jsonl" "$err" \
     --route get-posting --source "$src" >&2
  cat "$err" >&2
  exit 1
fi

sh "$here/record-api-response.sh" "$run_id" "$ws/jobs.jsonl" "$resp" \
   --route get-posting --source "$src" >&2
recstatus=$?

printf 'response=%s\n' "$resp"
[ "$recstatus" -eq 0 ] || exit 1
exit 0
