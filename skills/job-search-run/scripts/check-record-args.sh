#!/bin/sh
# check-record-args.sh — refuse a value record-api-response.sh would refuse, before the call is made.
#
# Usage: check-record-args.sh [--source S] [--query-id ID]
#
# The wrappers that spend a metered call — fetch-posting.sh and search-jobs.sh — run this before
# their `agent-data call`, and pass on the same values they will later hand record-api-response.sh.
#
# Why it has to run first. record-api-response.sh refuses four characters in --source and
# --query-id: a control character and a backslash at record-api-response.sh:92-106, and a comma and
# a colon at :112-120. All four checks exit 2 there, and all four run before `emit_call` is so much
# as defined at :173, so nothing is written to jobs.jsonl. A wrapper that spends the call and finds
# out afterwards is left with a call the API billed and no `call` event naming it — measured
# 2026-08-11 with --source 'linked:in' against an open run: the saved error body carried
# request_id req_eca95b6e566b46dca902c900 and `grep '"event":"call"'` on that run's jobs.jsonl
# matched only the earlier search. A run's metered-call count is built from those events, so the
# billed call is invisible to it.
#
# The rules are repeated here; the reasons they exist are not. Each is written out in
# record-api-response.sh above the check it belongs to, and that is the one place to read them.
#
# This checks the characters in a value and never which sources exist. agent-data-reference/SKILL.md
# names the four sources the API serves, and the API refuses the rest with a 400 — a second list
# here would be a copy to drift.
#
# There is no --run-id. Both wrappers take the run id from resolve-run.sh, which prints only a name
# matching its RUN_ID_GLOB at resolve-run.sh:62 — digits, dashes, `T` and `Z` — so a run id cannot
# hold any of the four characters. record-api-response.sh checks it at :104 anyway, because it takes
# the run id from its caller rather than from that script.
#
# Exit 0: record-api-response.sh accepts every value given.
# Exit 2: it would refuse one, or this script's own arguments are wrong. stderr names the rule.
set -u

usage() {
  printf 'usage: check-record-args.sh [--source S] [--query-id ID]\n' >&2
}

die() {
  printf 'check-record-args.sh: %s\n' "$1" >&2
  printf 'check-record-args.sh:   record-api-response.sh refuses this value before it records anything, so the call would be billed and no `call` event would name it\n' >&2
  exit 2
}

# The same three `case` patterns record-api-response.sh matches, in the same order.
check() {
  case $2 in
    *[[:cntrl:]]*) die "$1 may hold no control character" ;;
    *\\*)          die "$1 may hold no backslash: $2" ;;
    *,*|*:*)       die "$1 may hold neither a comma nor a colon: $2" ;;
  esac
}

while [ $# -gt 0 ]; do
  case $1 in
    --source)   [ $# -ge 2 ] || { usage; exit 2; }; check --source "$2";   shift 2 ;;
    --query-id) [ $# -ge 2 ] || { usage; exit 2; }; check --query-id "$2"; shift 2 ;;
    *) usage; exit 2 ;;
  esac
done

exit 0
