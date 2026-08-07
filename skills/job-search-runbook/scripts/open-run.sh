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
# Exit 1: opened — the marker is on disk and the three lines printed — and something is wrong that
#         this run cannot fix, so close it blocked. Where the detail is depends on whose problem it
#         is: findings about the workspace print on stdout after the three lines, and a failure of
#         this script's own, such as no way to take the brief revision, prints on stderr.
# Exit 2: the run did not open and nothing was written. Four causes, and the message on stderr says
#         which one: no such workspace, no config.yaml, the run_id is already taken by a run that
#         opened this same second, or the started-marker could not be written.
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

mkdir -p "$ws/runs" || exit 2

# The marker is written before the three lines are printed, so a run_id never reaches a caller for a
# run that has no marker on disk.
#
# `set -C` makes the redirection refuse a file that is already there, so writing the marker and
# claiming run_id are one operation. Testing with `[ -e ]` first and writing afterwards leaves a gap
# between the two, and a second process that starts in the same second can pass the test before the
# first one writes: measured with a pinned clock and two processes forked from one shell, 261 of 300
# rounds under sh and 267 of 300 under dash had both exit 0 with one marker on disk. The same
# harness over the write below gives 0 of 300 under each.
#
# Why a shared run_id has to be refused: run_id is the clock read to the second, so two runs that
# open inside one second are handed the same one. They write runs/<run_id>.json to a single path, so
# the second close overwrites the first's record, and run-counts.sh selects events by run_id, so it
# counts both runs' events together — searches, detail_reads and total_metered come out as the sum
# of two runs presented as one.
#
# The marker a run that died left behind is a different thing, handled by the run contract's step 1.
# It carries that run's id, so the name written here differs from it and the write succeeds.
#
# printf writes the marker rather than `:`, and the two differ by shell. Measured with `runs/` at
# mode 500, so only the write fails: `: > runs/.started-x || { …; exit 9; }` is caught by the `||`
# under bash and exits 9, while dash aborts on the failed redirection before the `||` runs, so the
# message below never prints and the caller gets dash's. The status is 2 in both, since that is what
# this script exits here too, so the message is the whole difference. This names bash and dash
# rather than `sh` because `/bin/sh` is bash on the machine where it was measured and dash on the CI
# runner. The same line written with printf is caught under both.
#
# stderr is dropped for this one command because the shell writes its own diagnostic there when
# `set -C` refuses — "cannot overwrite existing file" under bash, "File exists" under dash — and it
# is the wrong wording for either case. The `if` below tests whether the marker is on disk: if it
# is, the name is taken; if it is not, the write failed for another reason, an unwritable `runs/`
# among them.
set -C
{ printf '' > "$ws/runs/.started-$run_id"; } 2>/dev/null || {
  if [ -e "$ws/runs/.started-$run_id" ]; then
    printf 'open-run.sh: %s is already taken — another run opened this same second. Run open-run.sh again a second later; the marker under that name belongs to that run, not to an earlier one that stopped.\n' \
      "$run_id" >&2
  else
    printf 'open-run.sh: cannot write the started-marker in %s/runs\n' "$ws" >&2
  fi
  exit 2
}
set +C

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
