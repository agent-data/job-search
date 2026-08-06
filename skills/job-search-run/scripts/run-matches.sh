#!/bin/sh
# run-matches.sh — the postings this run judged, in the order the digest lists them.
#
# Usage: run-matches.sh <jobs.jsonl> <run_id>
#
# One posting per line, tab-separated:
#   band  source  source_id  title  company_name  location_display  source_url
#   needs_human_check  posted_at  reasoning
#
# band is strong, moderate, weak or filtered. Strong first, then moderate, weak, and the postings
# the run judged not relevant; within a band, the order the judgments landed.
#
# The digest's numbers come from run-counts.sh and the postings it names come from here, so the
# section headed "3 strong" holds three postings and they are the three the log says are strong.
# Nothing composes either list from memory of the run.
#
# reasoning is free text with its newlines and tabs turned into spaces, because one posting is one
# line. The full text stays on the event.
#
# One row per posting this run surfaced and this run judged, which is the set run-counts.sh reports
# as postings_reviewed. So the row count equals that number and the rows of one band count out to
# that band's key, and a caller can check the digest against both.
#
# Exit 0: the listing printed. A run that judged nothing prints no rows and exits 0.
# Exit 2: nothing printed — no log at that path.
# Any other status is awk failing partway, which leaves part of the listing on stdout: read these
# rows after checking the status, never because stdout has lines in it.
#
# A missing operand is the one case where the shell picks the status rather than this script:
# measured at 1 under sh and bash and 2 under dash. record-judgment.sh:19-21 records the same.
set -u

here=$(dirname "$0")
jobs=${1:?usage: run-matches.sh <jobs.jsonl> <run_id>}
run_id=${2:?usage: run-matches.sh <jobs.jsonl> <run_id>}

[ -f "$jobs" ] || { printf 'run-matches.sh: no such file: %s\n' "$jobs" >&2; exit 2; }

# exec, so the status the caller sees is awk's own. Nothing is post-processed here, and a pipeline
# would report the last stage rather than awk. run-counts.sh:38-40 hands off the same way.
exec awk -f "$here/event-field.awk" -f "$here/run-matches.awk" -v want="$run_id" "$jobs"
