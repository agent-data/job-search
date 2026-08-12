#!/bin/sh
# list-detail-read-queue.sh — print the postings this run queued and has not judged yet.
#
# Usage: list-detail-read-queue.sh <jobs.jsonl> <run_id>
#
# One posting per line, tab-separated, carrying what a reader needs to fetch and judge it and
# nothing that pre-judges it:
#   source  source_id  posting_id_at_seen  source_url  title  company_name
#
# This is what the run hands out. The event log grows past what a context window holds, so nothing
# reads it directly to work out what is left to do.
#
# It also writes one line to stderr: how many lines of the log name this run, out of how many lines
# in all, and then the queue — how many postings this run queued, how many of them already carry a
# judgment, and how many are left to read. No rows on stdout is the ordinary end of a run and also
# what a mistyped run id gives, and that line is what tells the two apart. The counts alone do not:
# a run that queued nothing reads `0 queued, 0 already judged, 0 to read`, and so does a mistyped
# id. The opening pair is what separates them — a mistyped id reads `0 of <n> lines`, where a run
# whose events are in the log reads a count above zero. run-counts.sh and run-matches.sh open on the
# same clause, in the same words.
set -u

here=$(dirname "$0")
jobs=${1:?usage: list-detail-read-queue.sh <jobs.jsonl> <run_id>}
run_id=${2:?usage: list-detail-read-queue.sh <jobs.jsonl> <run_id>}

[ -f "$jobs" ] || { printf 'list-detail-read-queue: no such file: %s\n' "$jobs" >&2; exit 2; }

exec awk -f "$here/event-field.awk" -f "$here/list-detail-read-queue.awk" -v want="$run_id" "$jobs"
