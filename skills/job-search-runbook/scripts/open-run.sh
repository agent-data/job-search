#!/bin/sh
# open-run.sh — open one run: mint its id, mark it started, take the brief revision, check the
# workspace.
#
# Usage: open-run.sh <workspace>
#
# Prints three lines:
#   run_id=2026-07-30T15-04-02Z
#   started_at=2026-07-30T15:04:02Z
#   brief_revision=9f2c41a7be05
#
# The clock is read once. started_at keeps the colons; run_id uses dashes because it is a
# filename, so the two name the same instant and nothing has to compose either of them.
#
# The workspace checks run here rather than as a separate step, so opening a run and checking it
# cannot come apart. A workspace with broken files still opens a run: the failure then closes as a
# blocked run with a record, rather than leaving nothing behind.
#
# Every finding about a workspace file comes from validate-workspace.sh, a missing preferences.md
# included; this script prints none of them itself. Those findings go to stdout after the three
# lines above.
#
# Exit 0: opened, workspace clean.
# Exit 1: opened, and the workspace findings follow the three lines on stdout — close blocked.
# Exit 2: the run did not open and nothing was written — no such workspace, no config.yaml, or the
#         started-marker could not be created.
#
# A missing operand is the exception the caller sees a shell-picked code for, the way
# run-counts.sh:28-29 records: measured at 1 under sh and bash and 2 under dash.
set -u

ws=${1:?usage: open-run.sh <workspace>}
here=$(dirname "$0")

[ -d "$ws" ] || { printf 'open-run.sh: no such workspace: %s\n' "$ws" >&2; exit 2; }
[ -f "$ws/config.yaml" ] || {
  printf 'open-run.sh: no config.yaml in %s — setup has not run, so there is no workspace to write into\n' \
    "$ws" >&2
  exit 2
}

now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
run_id=$(printf '%s\n' "$now" | tr ':' '-')

# The marker is written before the three lines are printed, so a run_id never reaches a caller for a
# run that has no marker on disk. printf writes it rather than `:`, because a failed redirection on
# `:` does not return here to be reported. Running `: > /nonexistent-root/xyz/.started-1` under each
# shell measures three different outcomes: sh aborts with exit 1, dash aborts with exit 2, and bash
# carries on to the next line and exits 0 — which would print a run_id for a run with no marker.
# printf returns non-zero in all three, so the check below is the same everywhere.
mkdir -p "$ws/runs" || exit 2
printf '' > "$ws/runs/.started-$run_id" || {
  printf 'open-run.sh: cannot write the started-marker in %s/runs\n' "$ws" >&2
  exit 2
}

# The brief revision is the first 12 characters of the SHA-256 of preferences.md, taken now, before
# anything in the run can edit the file. Hosts differ in which of the two commands they carry, and
# both print the same digest: on one file, `shasum -a 256`, `sha256sum` and Python's
# hashlib.sha256 all answer cfbcd3439f69…, and hashlib is what the test compares against.
rev=''
if [ -f "$ws/preferences.md" ]; then
  if command -v shasum >/dev/null 2>&1; then
    rev=$(shasum -a 256 "$ws/preferences.md" | cut -c1-12)
  elif command -v sha256sum >/dev/null 2>&1; then
    rev=$(sha256sum "$ws/preferences.md" | cut -c1-12)
  fi
fi

printf 'run_id=%s\n' "$run_id"
printf 'started_at=%s\n' "$now"
printf 'brief_revision=%s\n' "$rev"

status=0

# An empty revision has two causes, and they are different problems. No preferences.md is a broken
# workspace file, and validate-workspace.sh below already prints `INVALID preferences.md
# missing-file` for it — printing that line here as well would report one finding on two lines, and
# a caller counting INVALID lines would count it twice. A preferences.md that is there but whose
# digest could not be taken is this script failing rather than the workspace being wrong, so it says
# so on stderr in its own words, where no count of findings picks it up.
if [ -z "$rev" ] && [ -f "$ws/preferences.md" ]; then
  printf 'open-run.sh: could not take the revision of %s/preferences.md. It needs shasum or sha256sum on PATH and a readable file.\n' \
    "$ws" >&2
  status=1
fi

sh "$here/validate-workspace.sh" "$ws" || status=1
exit $status
