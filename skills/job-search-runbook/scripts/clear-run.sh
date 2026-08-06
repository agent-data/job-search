#!/bin/sh
# clear-run.sh — delete what one run was using, once its record and its digest are written.
#
# Usage: clear-run.sh <workspace> <run_id>
#
# Removes runs/.started-<run_id> and runs/.scratch/<run_id>/. It is a separate step from close-run.sh
# because the digest is written between the two and the scratch directory holds the responses the
# run collected. validate-workspace.sh --post-close reports either leftover, so a run that stops
# before this step is named rather than silently half-closed.
#
# It refuses to clear a run with no record: the marker is the only thing that says the run happened.
#
# Both paths carry the run id, so another run that is still open keeps its marker and its scratch.
#
# Exit 0: cleared. Exit 1: nothing removed; stderr names why.
#
# A missing operand is the exception the caller sees a shell-picked code for, the way
# run-counts.sh:28-29 records: measured at 1 under sh and bash and 2 under dash.
set -u

ws=${1:?usage: clear-run.sh <workspace> <run_id>}
run_id=${2:?usage: clear-run.sh <workspace> <run_id>}

# run_id is checked for its whole shape before any path is composed from it, because both paths
# below reach rm and one of them reaches `rm -rf`. Measured on 2026-08-06 before this check, with a
# file at ws/runs/../../victim.json to satisfy the record check: `clear-run.sh . ../../victim`
# printed its normal cleared message, exited 0, and deleted ws/victim/ with its contents.
#
# The same expression is at validate-workspace.sh:50 and in close-run.sh; the three have to agree.
# validate-workspace.sh:186 reads a file in runs/ as a run record only when its whole name matches
# it, so a run id of any other shape names a record no check in the workspace ever looks at.
RUN_ID_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$'
printf '%s\n' "$run_id" | grep -qE "$RUN_ID_RE" || {
  printf 'clear-run: <run_id> must be a UTC timestamp with dashes for the colons, like 2026-07-30T15-04-02Z, and got: %s\n' \
    "$run_id" >&2
  exit 1
}

[ -d "$ws" ] || { printf 'clear-run: no such workspace: %s\n' "$ws" >&2; exit 1; }
[ -f "$ws/runs/$run_id.json" ] || {
  printf 'clear-run: no record at runs/%s.json — close the run before clearing it\n' "$run_id" >&2
  exit 1
}

rm -f "$ws/runs/.started-$run_id"
rm -rf "$ws/runs/.scratch/$run_id"
printf 'clear-run: cleared the marker and the scratch for %s\n' "$run_id" >&2
