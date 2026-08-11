#!/bin/sh
# queue-detail-read.sh — mark one posting as one to read in full.
#
# Usage: queue-detail-read.sh <jobs.jsonl> --run-id ID --source S --source-id ID [--ts TS]
#
# Records one fact and no more: this posting is to be read. It carries nothing about the expected
# judgment — a provisional band would anchor the reader before it has read anything, and a named
# question would become the scope of its answer. The open question a read has to settle is the
# reader's to derive from the posting, and lives in the reasoning it writes.
#
# The point of the script is that a posting is marked without editing jobs.jsonl by hand, and the
# list of what is still to read survives outside any one agent's context.
#
# Exit 0: queued, or already queued for this run.
# Exit 1: nothing written; stderr names the problem.
set -u

jobs=${1:?usage: queue-detail-read.sh <jobs.jsonl> --run-id ID --source S --source-id ID}
shift

run_id='' source='' source_id='' ts=''
die() { printf 'queue-detail-read: %s\n' "$1" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case $1 in
    --run-id)    run_id=${2?}; shift 2 ;;
    --source)    source=${2?}; shift 2 ;;
    --source-id) source_id=${2?}; shift 2 ;;
    --ts)        ts=${2?}; shift 2 ;;
    *) die "unknown option $1" ;;
  esac
done

[ -n "$run_id" ]    || die 'missing --run-id'
[ -n "$source" ]    || die 'missing --source'
[ -n "$source_id" ] || die 'missing --source-id'
[ -f "$jobs" ]      || die "no such file: $jobs"

# Every value this script writes is an identifier, so each is refused rather than escaped. The
# reasons are written out at record-api-response.sh, which makes the same two checks: awk takes a
# literal newline in a -v assignment under mawk and refuses it under BSD awk, and awk resolves a
# backslash escape in a -v assignment before the program runs. Measured on --ts here, with a
# newline: BSD awk wrote no queued event and exited 2, mawk wrote one and exited 0.
reject_id() {
  case $2 in
    *[[:cntrl:]]*) die "$1 may hold no control character" ;;
    *\\*)          die "$1 may hold no backslash: $2" ;;
  esac
}
reject_id --run-id "$run_id"
reject_id --source "$source"
reject_id --source-id "$source_id"
reject_id --ts "$ts"

# The queue lists postings this run can fetch and judge, so every entry names one this run
# surfaced. Same four-grep chain, matching the same quoted forms, as the surfaced check in
# record-api-response.sh.
grep -F '"event":"surfaced"' "$jobs" \
  | grep -F "\"run_id\":\"$run_id\"" \
  | grep -F "\"source\":\"$source\"" \
  | grep -qF "\"source_id\":\"$source_id\"" \
  || die "no surfaced posting for $source:$source_id in run $run_id"

# Already queued: the posting the caller asked for is on the queue, so exit 0. A second event
# would put the posting on the list a reader works from twice.
if grep -F '"event":"queued"' "$jobs" \
     | grep -F "\"run_id\":\"$run_id\"" \
     | grep -F "\"source\":\"$source\"" \
     | grep -qF "\"source_id\":\"$source_id\""; then
  printf 'queue-detail-read: %s:%s is already queued for this run — nothing written\n' \
    "$source" "$source_id" >&2
  exit 0
fi

[ -n "$ts" ] || ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# End the last line before appending, so the queued event is not written onto the last line of a log
# that ends without a newline. Joined onto the event above it, the queued event never reaches the
# list a reader works from: measured 2026-08-08, this script exited 0 leaving one physical line, and
# `list-detail-read-queue.sh` then printed no rows at all for a posting it had just recorded as
# queued. What `tail -c1 | wc -l` prints, why `[ -s ]` comes first, and the measurement under sh,
# dash and bash are written out at event-log-append.sh, above its own append.
if [ -s "$jobs" ] && [ "$(tail -c1 "$jobs" | wc -l)" -eq 0 ]; then printf '\n' >> "$jobs"; fi

# No apostrophe may appear anywhere in this awk program: it is inside a single-quoted shell string,
# so one would end that string and the rest would be read as shell.
awk -v run_id="$run_id" -v source="$source" -v source_id="$source_id" -v ts="$ts" '
  function esc(s,   i, c) {
    gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s)
    gsub(/\t/, "\\t", s); gsub(/\r/, "\\r", s); gsub(/\n/, "\\n", s)
    # Every other control character JSON forbids raw inside a string, written as \u00xx. index()
    # first, so a long value is scanned 31 times rather than rewritten 31 times.
    for (i = 1; i < 32; i++) {
      c = sprintf("%c", i)
      if (index(s, c)) gsub(c, sprintf("\\u%04x", i), s)
    }
    return s
  }
  function jstr(s) { return "\"" esc(s) "\"" }
  BEGIN {
    print "{\"event\":\"queued\",\"run_id\":" jstr(run_id) ",\"source\":" jstr(source) \
          ",\"source_id\":" jstr(source_id) ",\"ts\":" jstr(ts) "}"
  }' >> "$jobs"
status=$?

# The write is announced, the way the already-queued branch above prints a line saying nothing was
# written. Without this line the two outcomes look the same from outside — nothing on stdout,
# nothing on stderr, exit 0 — and the caller cannot tell a queued posting from one it queued twice.
# The status is taken before the printf and given back after it, so when awk fails the caller still
# gets its non-zero exit status.
if [ "$status" -eq 0 ]; then
  printf 'queue-detail-read: queued %s:%s for run %s\n' "$source" "$source_id" "$run_id" >&2
fi
exit "$status"
