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
set -u

here=$(dirname "$0")
jobs=${1:?usage: list-detail-read-queue.sh <jobs.jsonl> <run_id>}
run_id=${2:?usage: list-detail-read-queue.sh <jobs.jsonl> <run_id>}

[ -f "$jobs" ] || { printf 'list-detail-read-queue: no such file: %s\n' "$jobs" >&2; exit 2; }

exec awk -f "$here/event-field.awk" -f "$here/list-detail-read-queue.awk" -v want="$run_id" "$jobs"
