#!/bin/sh
# resolve-run.sh — print the workspace and the run that is open in it.
#
# Usage: resolve-run.sh [--workspace W]
#   --workspace W   resolve against W instead of asking workspace-discovery.sh. Omit it in a run;
#                   the tests pass it, because their workspace is a temporary directory discovery
#                   would never find.
#
# Not called directly in a run. fetch-posting.sh, search-jobs.sh and record-judgment.sh call it,
# which is what lets each of them take no workspace and no run id.
#
# Prints exactly two lines on stdout:
#   workspace=/Users/x/.job-search
#   run_id=2026-07-30T15-04-02Z
#
# The workspace comes from the runbook skill's workspace-discovery.sh, which owns the precedence.
# The run id comes from the runs/.started-<run_id> marker open-run.sh writes and clear-run.sh
# removes. open-run.sh refuses to open a second run over an existing marker, so one marker is the
# expected state, and on two this script stops instead of choosing between them.
#
# Callers pass neither value. On the 2026-08-11 opencode run, 15 of 36 recording calls supplied no
# jobs.jsonl path and none supplied a run id, because no subagent had been given either.
#
# Exit 0: both lines printed.
# Exit 2: the arguments were wrong, or the workspace could not be resolved, or no run is open, or
#         more than one is. The message on stderr says which.
set -u

here=$(dirname "$0")
discovery=$here/../../job-search-runbook/scripts/workspace-discovery.sh

ws=''
while [ $# -gt 0 ]; do
  case $1 in
    --workspace) [ $# -ge 2 ] || { printf 'usage: resolve-run.sh [--workspace W]\n' >&2; exit 2; }
                 ws=$2; shift 2 ;;
    *) printf 'usage: resolve-run.sh [--workspace W]\n' >&2; exit 2 ;;
  esac
done

if [ -z "$ws" ]; then
  [ -f "$discovery" ] || {
    printf 'resolve-run.sh: cannot find workspace-discovery.sh at %s\n' "$discovery" >&2
    exit 2
  }
  ws=$(sh "$discovery" 2>/dev/null | sed -n 's/^workspace=//p')
  [ -n "$ws" ] || { printf 'resolve-run.sh: workspace-discovery.sh named no workspace\n' >&2; exit 2; }
fi
[ -d "$ws" ] || { printf 'resolve-run.sh: no such workspace: %s\n' "$ws" >&2; exit 2; }

# The run id comes out of the marker's name, and only from a name shaped like a run id.
# validate-workspace.sh:85 defines that shape as RUN_ID_GLOB and matches names against it at :95 and
# :303. The digits are written out rather than as the range [0-9] because a range matched
# Arabic-Indic digits under one locale, measured at validate-workspace.sh:73-84.
#
# Two kinds of name in runs/ carry the .started- prefix and name no run, and both are skipped here.
# `.started-` with nothing after the dash is one: open-run.sh:88 skips it and keeps scanning rather
# than refusing on it, so a workspace can hold it beside a real marker, and counting it would make
# one open run look like two. Any other name that misses the shape is the second: the `case` at
# close-run.sh:135 and the one at clear-run.sh:49 refuse a run id of any other shape, so printing
# such a name would hand a caller a run id neither of them will take.
RUN_ID_GLOB='[0123456789][0123456789][0123456789][0123456789]-[0123456789][0123456789]-[0123456789][0123456789]T[0123456789][0123456789]-[0123456789][0123456789]-[0123456789][0123456789]Z'

# Every marker is collected rather than the first one taken, so the refusal on two markers names
# both ids instead of this script picking one without saying so.
found='' n=0
for m in "$ws"/runs/.started-*; do
  [ -e "$m" ] || continue
  id=${m##*/.started-}
  case $id in $RUN_ID_GLOB) ;; *) continue ;; esac
  n=$((n + 1))
  found="$found${found:+ }$id"
done

[ "$n" -ne 0 ] || {
  printf 'resolve-run.sh: no run is open in %s — open-run.sh writes the marker this reads\n' "$ws" >&2
  exit 2
}
[ "$n" -eq 1 ] || {
  printf 'resolve-run.sh: more than one run is open in %s: %s — close and clear all but the one this work belongs to\n' \
    "$ws" "$found" >&2
  exit 2
}

printf 'workspace=%s\n' "$ws"
printf 'run_id=%s\n' "$found"
