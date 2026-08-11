#!/bin/sh
# run-matches.sh — the postings this run judged, in the order the digest lists them.
#
# Usage: run-matches.sh <jobs.jsonl> <run_id>
#
# One posting per line, tab-separated:
#   band  source  source_id  title  company_name  location_display  source_url
#   needs_human_check  posted_at  reasoning  also_posted
#
# band is strong, moderate, weak or filtered. Strong first, then moderate, weak, and the postings
# the run judged not relevant. Within a band, the order the first judgments landed: a posting
# judged twice keeps the place its first judgment gave it, and the row carries its last judgment.
#
# The digest's numbers come from run-counts.sh and the postings it names come from here, so the
# section headed "3 strong" holds three postings and they are the three the log says are strong.
# Nothing composes either list from memory of the run.
#
# reasoning is free text with its newlines and tabs turned into spaces, because one posting is one
# line. The full text stays on the event.
#
# also_posted names the other places the same opening was posted, and is empty on a row no other
# posting names. A company that posts one opening in several cities gets one row back per city; the
# run reads one of them and records each of the others with --same-role-as naming the row it read.
# Those postings get no row of their own here — the digest lists the opening once — and each one's
# location_display is joined onto the row it names, with `; `, in the order this run judged them. A
# semicolon and not a comma, because a location holds commas of its own: `San Francisco, CA` and
# `San Francisco Bay Area` joined with a comma read as four places rather than two. The column is
# printed on every row whether or not anything names it, so the number of columns never varies.
#
# One of those postings adds nothing to the column: one whose row came back with no location, which
# reaches this script as an empty location_display or as the four characters `null`. It is still
# counted under duplicates_of_another and still gets no row of its own — there is just no place to
# name. So the column can name fewer places than duplicates_of_another counts, and on a run where
# every duplicate came back without a location it is empty on every row.
#
# The value is read as <source>:<source_id> split at the FIRST colon, because a source_id can hold
# one — a greenhouse id is written <board>:<number>. A value that names no row here — an id no
# search of this run turned up, or a value not written as a pair — changes no count and prints no
# location, and the posting carrying it is still left out. Giving it a row instead would print one
# opening twice whenever the value is a misspelling of a posting already listed, which is what
# --same-role-as is written for, and nothing here can tell that apart from a value naming a posting
# that really is somewhere else. posting-counts.sh, which the home view reads, leaves such a posting
# out of its counts on the same test — whether the field is there, never on what it names — so the
# digest and the home card report one opening once.
#
# One row per posting this run surfaced and this run judged, less the postings that are the same
# opening as another and less any relevant row carrying no band. A relevant row's band is strong,
# moderate or weak, so all three of these are rows with no band: an absent match, a null one, and
# the string `filtered`, which is what a row judged not relevant gets rather than a value a
# judgment carries.
#
# run-counts.sh counts both kinds in postings_reviewed, so the row count is postings_reviewed minus
# duplicates_of_another minus the number on run-counts.sh's INVALID relevant-row-without-a-band
# line. run-counts.sh prints that line only when it exits 1, so for every log it exits 0 on, the row
# count is postings_reviewed minus duplicates_of_another. Measured on a log of three surfaced
# postings, one judged strong, one naming that one in same_role_as, and one relevant with match
# null: run-counts.sh printed postings_reviewed=3, match_strong=1, duplicates_of_another=1,
# filtered_out=0 and INVALID relevant-row-without-a-band=1 at exit 1, and this script printed one
# row at exit 0.
#
# The rows of one band still count out to that band's key, because run-counts.sh puts a duplicate
# and an unbanded row in none of the four bands and this script gives neither a row. So a caller can
# check the digest against both.
#
# It also writes one line to stderr: how many of the log's lines name this run, out of how many
# lines it read — the same pair run-counts.sh reports, in the same words — then the rows printed
# under each of the four bands, the postings that are the same opening as another and so got no row,
# and, when that last count is above zero, the postings judged relevant with no band and given no
# row. A run that judged nothing and a run id no event carries both print no rows at all, and the
# first pair of numbers is what tells the two apart.
#
# Exit 0: the listing printed. A run that judged nothing prints no rows and exits 0.
# Exit 2: no rows printed — no log at that path, named on stderr.
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
# would report the last stage rather than awk. run-counts.sh hands off the same way — its last line
# is the same `exec awk -f event-field.awk -f <program>.awk` form.
exec awk -f "$here/event-field.awk" -f "$here/run-matches.awk" -v want="$run_id" "$jobs"
