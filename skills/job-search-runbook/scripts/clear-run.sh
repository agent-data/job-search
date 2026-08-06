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

[ -d "$ws" ] || { printf 'clear-run: no such workspace: %s\n' "$ws" >&2; exit 1; }
[ -f "$ws/runs/$run_id.json" ] || {
  printf 'clear-run: no record at runs/%s.json — close the run before clearing it\n' "$run_id" >&2
  exit 1
}

rm -f "$ws/runs/.started-$run_id"
rm -rf "$ws/runs/.scratch/$run_id"
printf 'clear-run: cleared the marker and the scratch for %s\n' "$run_id" >&2
