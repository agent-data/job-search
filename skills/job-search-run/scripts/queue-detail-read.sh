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

# No apostrophe may appear anywhere in this awk program: it is inside a single-quoted shell string,
# so one would end that string and the rest would be read as shell.
awk -v run_id="$run_id" -v source="$source" -v source_id="$source_id" -v ts="$ts" '
  function esc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return s }
  function jstr(s) { return "\"" esc(s) "\"" }
  BEGIN {
    print "{\"event\":\"queued\",\"run_id\":" jstr(run_id) ",\"source\":" jstr(source) \
          ",\"source_id\":" jstr(source_id) ",\"ts\":" jstr(ts) "}"
  }' >> "$jobs"
