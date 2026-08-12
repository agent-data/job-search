#!/bin/sh
# fetch-posting.sh — read one posting and record the call that read it, in one step.
#
# Usage: fetch-posting.sh --posting-id P --source-url U --source S [--workspace W]
#   --posting-id P  required. The `posting_id_at_seen` in the row list-detail-read-queue.sh printed
#                   for this posting.
#   --source-url U  required. The same row's `source_url`. `get-posting` accepts a posting id and a
#                   source url only as the pair one search result row carried them in, so a url
#                   taken from another row is refused.
#   --source S      required. The same row's `source`.
#   --workspace W   resolve against W instead of asking workspace-discovery.sh. Omit it in a run;
#                   the tests pass it, because their workspace is a temporary directory
#                   workspace-discovery.sh would never find.
#
# The posting must be one a search of this open run surfaced, or record-api-response.sh refuses the
# response and this exits 1. Take the three values from one line of what list-detail-read-queue.sh
# prints rather than composing them.
#
# Not for reading a posting outside a run: there is no run to bill the call to and no log to record
# it in. That case is the `get-posting` recipe in the agent-data-reference skill.
#
# Prints one line on stdout: response=<path to the saved body>. It is printed whenever the call
# itself succeeded, including when record-api-response.sh then refuses the body and this exits 1 —
# the posting was fetched and saved, so the path is worth having either way.
#
# A run's billable-call count is built from the `call` events in jobs.jsonl, and
# record-api-response.sh is the only thing that writes one. Calling agent-data on its own leaves no
# event, so the call is charged and absent from the count. Measured on the 2026-08-11 opencode run:
# 35 get-posting calls were made and 14 reached the workspace log.
#
# In a run nothing passes a workspace or a run id: both come from resolve-run.sh.
#
# There is no flag to swap the command this runs. The tests spend real calls, because a wrapper
# that makes a call and records it cannot be proven against something that never calls anything.
#
# Exit 0: the posting was read and both events are in the log.
# Exit 1: the call failed, or record-api-response.sh refused the response. The `call` event is
#         recorded either way, because a failed call was still charged. The two differ in what the
#         streams carry, measured 2026-08-11 by driving both against a live run. A failed call
#         prints nothing on stdout, and stderr carries record-api-response.sh's diagnostic followed
#         by the error body. A refused response prints the response= line on stdout, and stderr
#         carries record-api-response.sh's diagnostic and nothing after it — the body is in the file
#         that response= line names.
# Exit 2: bad arguments, a --posting-id this script will not take, a --source record-api-response.sh
#         will not take, or no single open run to record against. Nothing was called.
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

# The posting id supplies the name of the file this script writes the response to, so it is checked
# here, before that path is built and before anything is spent. check-record-args.sh does not check
# it: record-api-response.sh is never handed a posting id — it gets a run id, a log path, a response
# path, a route and a source — so the reason to check this one belongs where the path is made.
#
# The value comes off a surfaced row, so it is the API's rather than one an operator typed. Measured
# 2026-08-11 on a live 10-row linkedin search, every `id` is `jp_` followed by 12 hex digits, and
# none of the ten holds a slash or a control character. That shape is not pinned here: the API owns
# it and a copy of it would drift out of step.
#
# Both refusals were measured 2026-08-11 against an open run, with this check removed.
#
# A slash: `--posting-id ../../../escaped` left the shell unable to open
# runs/.scratch/<run_id>/detail-../../../escaped.json, so agent-data never ran, and the failed-call
# branch below then ran against an error file that was never created. Three lines on stderr, exit 1,
# and not one of them says which argument was wrong.
#
# A control character: `--posting-id jp_a<newline>jp_b` created the file
# detail-jp_a<newline>jp_b.json, and the response= line below then printed as two lines, so
# `sed -n 's/^response=//p'` handed the caller a path that stopped at the newline and named no file.
case $posting_id in
  */*)
    printf 'fetch-posting.sh: --posting-id may hold no slash: %s\n' "$posting_id" >&2
    printf 'fetch-posting.sh:   it supplies a file name under this run, not a path\n' >&2
    exit 2 ;;
  *[[:cntrl:]]*)
    printf 'fetch-posting.sh: --posting-id may hold no control character\n' >&2
    printf 'fetch-posting.sh:   it supplies a file name under this run, and the response= line naming that file is one line\n' >&2
    exit 2 ;;
esac

# Before the call, not after it. record-api-response.sh exits 2 on a --route or a --source it will
# not take, and every one of those checks runs before it writes anything, so handing it a refused
# value once the call has been made leaves the call billed and no `call` event naming it — the exact
# loss this script exists to prevent. check-record-args.sh holds the rules and the measurement.
#
# This sits with the argument checks rather than after resolve-run.sh, so a bad --source is named
# whether or not a run is open.
sh "$here/check-record-args.sh" --route get-posting --source "$src" || exit 2

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
