#!/bin/sh
# record-judgment.sh — record one posting's judgment.
#
# Usage: record-judgment.sh <jobs.jsonl> --run-id ID --source S --source-id ID \
#          --detail-read true|false --relevant true|false [--match strong|moderate|weak] \
#          [--needs-human-check true|false] [--dealbreakers 'a;b'] [--unknowns 'a;b'] \
#          [--reasoning TEXT] [--same-role-as SOURCE:ID] [--posted-at-extracted DATE] [--ts TS]
#
# The script writes the JSON, so nothing the judgment says has to be escaped by whoever is calling.
# A judgment can only be about a posting a search surfaced for this run, and the title, company,
# location, URL and date come off that surfaced event rather than from the caller.
#
# A semicolon separates one dealbreaker or unknown from the next, so a dealbreaker that contains a
# semicolon has to be reworded. Spaces around the semicolon are trimmed, so `pay; then equity` and
# `pay;then equity` give the same two entries.
#
# Exit 0: recorded, or this posting already carries exactly this judgment.
# Exit 1: nothing written; stderr names the problem.
# Exit 2: nothing was attempted — no operand at all, or no temporary file could be made. The shell
#         picks the code when the operand is missing, so that case is 2 under dash and 1 under sh
#         and bash; every exit this script chooses itself is 0 or 1.
set -u

here=$(dirname "$0")
jobs=${1:?usage: record-judgment.sh <jobs.jsonl> --run-id ID --source S --source-id ID ...}
shift

run_id='' source='' source_id='' detail_read='' relevant='' band=''
nhc=false dealbreakers='' unknowns='' reasoning='' same_role='' posted_extracted='' ts=''

die() { printf 'record-judgment: %s\n' "$1" >&2; exit 1; }

line=$(mktemp) || exit 2
trap 'rm -f "$line"' EXIT INT HUP TERM

while [ $# -gt 0 ]; do
  case $1 in
    --run-id)              run_id=${2?}; shift 2 ;;
    --source)              source=${2?}; shift 2 ;;
    --source-id)           source_id=${2?}; shift 2 ;;
    --detail-read)         detail_read=${2?}; shift 2 ;;
    --relevant)            relevant=${2?}; shift 2 ;;
    --match)               band=${2?}; shift 2 ;;
    --needs-human-check)   nhc=${2?}; shift 2 ;;
    --dealbreakers)        dealbreakers=${2?}; shift 2 ;;
    --unknowns)            unknowns=${2?}; shift 2 ;;
    --reasoning)           reasoning=${2?}; shift 2 ;;
    --same-role-as)        same_role=${2?}; shift 2 ;;
    --posted-at-extracted) posted_extracted=${2?}; shift 2 ;;
    --ts)                  ts=${2?}; shift 2 ;;
    *) die "unknown option $1" ;;
  esac
done

[ -n "$run_id" ]    || die 'missing --run-id'
[ -n "$source" ]    || die 'missing --source'
[ -n "$source_id" ] || die 'missing --source-id'
[ -f "$jobs" ]      || die "no such file: $jobs"

case $detail_read in true|false) ;; *) die '--detail-read must be true or false' ;; esac
case $relevant in true|false) ;; *) die '--relevant must be true or false' ;; esac
case $nhc in true|false) ;; *) die '--needs-human-check must be true or false' ;; esac

# The identifiers are refused rather than escaped; the three free-text values are not checked at
# all, because esc writes them out whole and a reason legitimately holds a newline. The reasons are
# written out at record-api-response.sh, which makes the same two checks: awk takes a literal
# newline in a -v assignment under mawk and refuses it under BSD awk, and awk resolves a backslash
# escape in a -v assignment before the program runs. Measured on --ts here, with a newline: BSD awk
# wrote no evaluated event and exited 1, mawk wrote one and exited 0.
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
reject_id --same-role-as "$same_role"
reject_id --posted-at-extracted "$posted_extracted"

# A relevant posting carries a band; one that is not relevant carries none.
if [ "$relevant" = true ]; then
  case $band in
    strong|moderate|weak) ;;
    *) die '--relevant true needs --match strong|moderate|weak' ;;
  esac
else
  [ -z "$band" ] || die '--relevant false takes no --match'
fi

# The surfaced event proves the posting belongs to this run, and carries the five display fields.
#
# grep -F matches a substring, so a source_id that is a prefix of another posting's matches the
# wrong posting. The hazard, the measurement showing it cannot fire on tests/fixtures/api-responses,
# and the reason not to change one script on its own are written out at queue-detail-read.sh:59-68.
# This is the third script to match postings this way. The already-judged check below no longer
# greps — it reads the fields with jval, in find-judgment.awk, which ends this hazard and the
# whitespace one together — so five lookups still match this way: this one, and both lookups in each
# of queue-detail-read.sh and record-api-response.sh.
#
# Two things for whoever does that. What rules the hazard out on the api-response fixtures is that
# every id of one source is the same width, and numeric ids elsewhere in this repo are not:
#   grep -rhoE '"source_id"[[:space:]]*:[[:space:]]*"[0-9]+"' docs evals skills tests \
#     | grep -oE '[0-9]+' | awk '{ print length }' | sort -n | uniq -c
# gives 3 ids of 1 digit, 10 of 3, 21 of 4, 2 of 7 and 13 of 10.
#
# No committed fixture or log holds a numeric pair where one id is a prefix of the other: grouping
# the numeric ids under tests/fixtures and every .jsonl by file gives 20 distinct ids and no such
# pair, in one file or across all of them. So nothing a test reads can fire this today. Prose and
# hand-written events do hold such pairs — "1" and "123" are both in
# tests/test_mechanics_scripts.py, and 18 more span files ("2"/"2001", "444"/"4449006488") — and
# nothing keeps a live numeric id one width, so a run that surfaced "100" and "1001" would match
# the wrong one.
#
# Anchoring on the following comma is the fix: every event that carries source_id writes another
# field after it — surfaced, detail, queued and evaluated all do — so matching "source_id":"ID",
# with the comma ends the match at the id.
surfaced=$(grep -F '"event":"surfaced"' "$jobs" \
           | grep -F "\"run_id\":\"$run_id\"" \
           | grep -F "\"source\":\"$source\"" \
           | grep -F "\"source_id\":\"$source_id\"" | tail -1)
[ -n "$surfaced" ] || die "no surfaced posting for $source:$source_id in run $run_id"

[ -n "$ts" ] || ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Free text and the whole surfaced line ride in the environment rather than through -v, which
# cannot carry a literal newline. `band` is not called `match`, which is an awk built-in.
RJ_REASONING=$reasoning RJ_DEALBREAKERS=$dealbreakers RJ_UNKNOWNS=$unknowns RJ_SURFACED=$surfaced \
awk -f "$here/event-field.awk" -f "$here/record-judgment.awk" \
    -v run_id="$run_id" -v source="$source" -v source_id="$source_id" \
    -v detail_read="$detail_read" -v relevant="$relevant" -v band="$band" \
    -v nhc="$nhc" -v same_role="$same_role" \
    -v posted_extracted="$posted_extracted" -v ts="$ts" > "$line"
judgestatus=$?

# Both the status and the file, the way record-api-response.sh checks both after building its
# detail event and again after building its rows. An awk that died before printing leaves this file
# empty; one that failed partway through the line leaves part of an event in it. Appending that part
# is worse than appending nothing: the log then holds a line no JSON reader can parse, and the
# judgment it was meant to record is not in the log at all. Measured against a shimmed awk that
# prints half an event and exits 2 — with only the file checked, the script exits 0 and the truncated
# line lands.
if [ "$judgestatus" -ne 0 ] || [ ! -s "$line" ]; then
  die 'building the event failed — nothing written'
fi

# A judgment already recorded for this posting in this run. The same one again is a retry and
# changes nothing; a different one is a conflict the caller has to settle, so write neither.
#
# This lookup reads the fields with jval instead of grepping for their quoted text.
# event-log-append.sh accepts a judgment written by hand with a space after any colon, so such a
# line is in the log by design, and a chain of greps matching the quoted text finds none of it. The
# conflict below was then never reached and the second verdict went into the log. The measurement,
# and why the surfaced lookup above still greps, are in find-judgment.awk.
prev=$(awk -f "$here/event-field.awk" -f "$here/find-judgment.awk" \
           -v run_id="$run_id" -v source="$source" -v source_id="$source_id" "$jobs")
prevstatus=$?

# The status is checked for the reason the builder's is checked above: an awk that died before
# printing anything looks exactly like a posting no one has judged yet, and this script would then
# append a second verdict for a posting that already has one.
[ "$prevstatus" -eq 0 ] || die 'reading the judgments already recorded failed — nothing written'

if [ -n "$prev" ]; then
  # The timestamp is dropped from both sides before they are compared: a retry a minute later writes
  # the same line but for its `ts`, and comparing the lines whole would send it to the branch below.
  a=$(printf '%s\n' "$prev" | sed 's/,"ts":"[^"]*"//')
  b=$(sed 's/,"ts":"[^"]*"//' "$line")
  if [ "$a" = "$b" ]; then
    printf 'record-judgment: %s:%s already carries this verdict — nothing written\n' \
      "$source" "$source_id" >&2
    exit 0
  fi
  # Two lines compared byte for byte, so what this answers is whether the judgment already in the
  # log is the line this call would write — not whether the two verdicts agree. Any difference at
  # all sends a judgment here: a different field set, a different field order, a space after a
  # colon, or a genuinely different verdict. A judgment written by hand reaches here whatever it
  # says, because record-judgment.awk builds one exact line and almost nothing written by hand
  # matches it byte for byte. Measured on 2026-08-06: the compact event this script writes,
  # rewritten with a space after every colon, appended, and then offered again unchanged, arrives
  # here — the same verdict on both sides, and only the spacing different. So the message says what
  # was found and prints both lines for the caller to compare, rather than telling the caller the
  # verdicts differ.
  #
  # The sed keys on the compact `,"ts":"`, so what the recorded line shows below depends on how its
  # own ts was written: a hand-written prior whose ts colon carries a space keeps its timestamp in
  # what is printed, and one whose ts colon is compact loses it, whatever the rest of the line looks
  # like. tests/test_mechanics_scripts.py:2039-2041, in
  # test_a_judgment_written_with_spaces_after_its_colons_still_blocks_a_second_one, commits a prior
  # of the second kind — a space after its first four colons and none after `ts` — and its recorded
  # line prints with no ts.
  printf 'record-judgment: %s:%s already has a judgment in run %s, and it is not the line this call would write — nothing written\n' \
    "$source" "$source_id" "$run_id" >&2
  printf 'record-judgment:   recorded: %s\n' "$a" >&2
  printf 'record-judgment:   offered:  %s\n' "$b" >&2
  exit 1
fi

# End the last line before appending, so this judgment is not written onto the last line of a log
# that ends without a newline. The joined line is read as the event above it, so the judgment is lost
# and every count the run reports is worked out without it. What `tail -c1 | wc -l` answers, why
# `[ -s ]` comes first, and the measurement under sh, dash and bash are written out at
# event-log-append.sh, above its own append.
if [ -s "$jobs" ] && [ "$(tail -c1 "$jobs" | wc -l)" -eq 0 ]; then printf '\n' >> "$jobs"; fi

cat "$line" >> "$jobs"
