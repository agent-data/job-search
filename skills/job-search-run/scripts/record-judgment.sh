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
# semicolon has to be reworded.
#
# Exit 0: recorded, or this posting already carries exactly this judgment.
# Exit 1: nothing written; stderr names the problem.
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
# and the reason not to change one script on its own are written out at queue-detail-read.sh:39-52.
# This is the third script to match postings this way, and like the other two it matches twice —
# here and in the already-judged check below — so hardening the match means changing six greps
# across three files.
#
# Two things for whoever does that. What rules the hazard out on the api-response fixtures is that
# every id of one source is the same width, and numeric ids elsewhere in this repo are not:
#   grep -rhoE '"source_id"[[:space:]]*:[[:space:]]*"[0-9]+"' docs evals skills tests \
#     | grep -oE '[0-9]+' | awk '{ print length }' | sort -n | uniq -c
# gives 3 ids of 1 digit, 10 of 3, 21 of 4, 2 of 7 and 13 of 10: tests/fixtures/happy/
# search-jobs.json carries "1001" and "1002", and docs/exec-plans/completed/
# 2026-06-05-foundation-core.md carries "111" and "222". No committed file holds a numeric pair
# where one id is a prefix of the other, so nothing in the repo can fire this today — but nothing
# keeps a live numeric id one width either, and a run that surfaced "100" and "1001" would match
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

# The whole event is built in awk and printed by one statement at the end of BEGIN, so an awk that
# died leaves this file empty rather than leaving part of an event in it.
[ -s "$line" ] || die 'built an empty event line'

# A judgment already recorded for this posting in this run. The same one again is a retry and
# changes nothing; a different one is a conflict the caller has to settle, so write neither.
prev=$(grep -F '"event":"evaluated"' "$jobs" \
       | grep -F "\"run_id\":\"$run_id\"" \
       | grep -F "\"source\":\"$source\"" \
       | grep -F "\"source_id\":\"$source_id\"" | tail -1)

if [ -n "$prev" ]; then
  # The timestamp is dropped from both sides before they are compared: a retry a minute later is
  # the same verdict, and comparing the lines whole would call it a conflict.
  a=$(printf '%s\n' "$prev" | sed 's/,"ts":"[^"]*"//')
  b=$(sed 's/,"ts":"[^"]*"//' "$line")
  if [ "$a" = "$b" ]; then
    printf 'record-judgment: %s:%s already carries this verdict — nothing written\n' \
      "$source" "$source_id" >&2
    exit 0
  fi
  printf 'record-judgment: %s:%s already has a DIFFERENT verdict in run %s — nothing written\n' \
    "$source" "$source_id" "$run_id" >&2
  printf 'record-judgment:   recorded: %s\n' "$a" >&2
  printf 'record-judgment:   offered:  %s\n' "$b" >&2
  exit 1
fi

cat "$line" >> "$jobs"
