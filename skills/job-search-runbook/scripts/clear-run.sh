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
# run-counts.sh's own header records — `grep -n 'missing operand'
# skills/job-search-run/scripts/run-counts.sh`: measured at 1 under sh and bash and 2 under dash.
set -u

ws=${1:?usage: clear-run.sh <workspace> <run_id>}
run_id=${2:?usage: clear-run.sh <workspace> <run_id>}

# run_id is checked for its whole shape before any path is composed from it, because both paths
# below reach rm and one of them reaches `rm -rf`. Measured on 2026-08-06 against the version with
# no check, in a workspace that had a runs/.scratch directory — which every run that stored a
# response leaves — and a file at ws/runs/../../victim.json to satisfy the record check below:
# `clear-run.sh . ../../victim` printed its normal cleared message, exited 0, and deleted ws/victim/
# with its contents. Both preconditions are needed: `rm -rf` removes nothing when a directory along
# the path is absent, and the record check stops the run before either rm without that file.
#
# A `case` glob rather than a grep on the value, for the reason close-run.sh writes out — `grep -n
# 'case. glob rather than a grep' skills/job-search-runbook/scripts/close-run.sh`: a grep on
# `printf '%s\n' "$run_id"` exits 0 when any one line matches, so a run id carrying a newline got
# through on the strength of a single well-formed line. `case` compares the whole word.
#
# The digits are written out one by one rather than as `[0-9]`, for the reason close-run.sh measures
# — `grep -n 'a range inside a bracket' skills/job-search-runbook/scripts/close-run.sh`, one
# line: a range inside a bracket expression is decided by the collation order the locale sets, so
# `[0-9]` matched a run id spelled in Arabic-Indic digits under LC_ALL=ar_SA.UTF-8. A list of ten
# characters is not a range and no locale changes it.
#
# validate-workspace.sh states the same rule in the same notation — `grep -n RUN_ID_GLOB=
# skills/job-search-runbook/scripts/validate-workspace.sh` — and uses it both to decide whether a
# file in runs/ is a run record at all and to check the run id --post-close is given. The three
# copies are driven over one table of run ids in tests/test_mechanics_scripts.py, under two
# locales, and must give the same verdict for each.
case $run_id in
  [0123456789][0123456789][0123456789][0123456789]-[0123456789][0123456789]-[0123456789][0123456789]T[0123456789][0123456789]-[0123456789][0123456789]-[0123456789][0123456789]Z) ;;
  *)
    printf 'clear-run: <run_id> must be a UTC timestamp with dashes for the colons, like 2026-07-30T15-04-02Z, and got: %s\n' \
      "$run_id" >&2
    exit 1 ;;
esac

[ -d "$ws" ] || { printf 'clear-run: no such workspace: %s\n' "$ws" >&2; exit 1; }
[ -f "$ws/runs/$run_id.json" ] || {
  printf 'clear-run: no record at runs/%s.json — close the run before clearing it\n' "$run_id" >&2
  exit 1
}

rm -f "$ws/runs/.started-$run_id"
rm -rf "$ws/runs/.scratch/$run_id"
printf 'clear-run: cleared the marker and the scratch for %s\n' "$run_id" >&2
