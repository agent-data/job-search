#!/bin/sh
# run-counts.sh — work out one run's numbers from jobs.jsonl and print them, one key=value per line.
#
# Usage: run-counts.sh <jobs.jsonl> <run_id>
#
# This is the only place a run's numbers are worked out. The run record copies these values and the
# digest's counts line reads the same ones, so the two cannot disagree.
#
# Every event is filtered by run_id, judgments included. That is what makes these numbers the same
# a year from now as they are at close: a later run judging a posting this one left unjudged does
# not reach back and change what this run did.
#
# Five keys add up to postings_reviewed: match_strong, match_moderate, match_weak, filtered_out and
# duplicates_of_another. The fifth counts the postings that are the same opening as one already
# counted — a company posting one opening in several cities gets one row back per city, the run
# reads one of them, and the judgment on each of the others names the row that was read in
# same_role_as. Such a posting is counted here and in no band, on the same test posting-counts.sh
# uses for the home view — whether the field is there, never on what it names — and both read it off
# the posting's last judgment, so a posting re-judged without the field goes back into its band on
# both screens at once. That is what makes the digest and the home card report one opening once.
# run-matches.sh gives such a posting no row and puts its location on the row it names; the rule for
# a value naming no such row is written out there.
#
# postings_reviewed still counts postings. It pairs with postings_unreviewed against
# postings_surfaced and says how much work the run did, and judging the second posting of one
# opening is work the run did. That is why the duplicate gets a key of its own rather than being
# dropped from every number: the sum has to name every posting the run reviewed.
#
# The calls_* keys count `call` events, so retries, repeats and failures are in them without anyone
# reporting them. Four of them carry the numbers the run record's `agent_data_usage` block holds:
# searches, detail_reads, other and total_metered. searches_never_succeeded groups the search calls
# by source and query and counts the groups where none of the attempts returned — one failed attempt
# inside a group that later answered is not a lost search.
#
# This is the scripted form of the model-run prose contract; that prose remains the no-runtime
# fallback, and counts worked out by hand are not gated by anything, so a run that works them out
# that way says so rather than presenting them as checked.
#
# It also writes one line to stderr: how many of the log's lines name this run, out of how many
# lines it read. Every key above prints whether or not the run id matched anything, so a run that
# did nothing and a run id no event carries print the same zeroed keys, and that pair of numbers is
# what tells the two apart. The line is written before the check that exits 1 below, so a caller
# that got exit 1 has it too.
#
# Exit 0: the counts printed. Exit 1: a relevant row carries no band, named on the last line; the
# counts are printed first. Exit 2: no counts printed — no log at that path, named on stderr. Any
# other status is awk failing partway, which leaves part of the key set on stdout: read these counts
# after checking the status, never because stdout has lines in it.
#
# A missing operand is the exception the caller sees a shell-picked code for, the way
# record-judgment.sh:19-21 records: measured at 1 under sh and bash and 2 under dash.
set -u

here=$(dirname "$0")
jobs=${1:?usage: run-counts.sh <jobs.jsonl> <run_id>}
run_id=${2:?usage: run-counts.sh <jobs.jsonl> <run_id>}

[ -f "$jobs" ] || { printf 'run-counts.sh: no such file: %s\n' "$jobs" >&2; exit 2; }

# exec, so the status the caller sees is awk's own. Nothing is post-processed here, and a pipeline
# would report the last stage rather than awk.
exec awk -f "$here/event-field.awk" -f "$here/run-counts.awk" -v want="$run_id" "$jobs"
