#!/bin/sh
# check-record-args.sh — refuse a value record-api-response.sh would refuse, before the call is made.
#
# Usage: check-record-args.sh --route get-posting [--source S]
#        check-record-args.sh --route search-jobs [--source S] --query-id ID
#
# A wrapper that spends a metered call runs this before its `agent-data call`, passing the values it
# will later hand record-api-response.sh. search-jobs.sh and fetch-posting.sh both do. The
# flag names are record-api-response.sh's own, so the same arguments go to both.
#
# Why it has to run first. record-api-response.sh exits 2 on a value it will not take, and every one
# of those checks runs before `emit_call` is even defined at record-api-response.sh:173, so a refused
# value leaves nothing in jobs.jsonl. A wrapper that spends the call and finds out afterwards is left
# with a call the API billed and no `call` event naming it — measured 2026-08-11 with
# --source 'linked:in' against an open run: the saved error body carried request_id
# req_eca95b6e566b46dca902c900 and `grep '"event":"call"'` on that run's jobs.jsonl matched only the
# earlier search. A run's metered-call count is built from those events, and a billed call that
# left none is missing from it.
#
# The rules, and where record-api-response.sh checks each:
#   :65-68    --route is search-jobs or get-posting
#   :92-106   --source and --query-id hold no control character and no backslash
#   :112-120  --source and --query-id hold neither a comma nor a colon
#   :130-136  --route search-jobs is given a --query-id that is not empty
#
# The rules are repeated here; the reasons they exist are not. Each is written out in
# record-api-response.sh above the check it belongs to, and that is the one place to read them.
#
# --route is required because the last rule is the one that is not about characters and applies to
# one route only: a search is grouped by source and query id, and a detail read is not grouped and
# takes no query id. Nothing else in the arguments says which of the two calls is being guarded.
# Measured 2026-08-11: `record-api-response.sh <run_id> <jobs> <resp> --route search-jobs
# --query-id '' --source linkedin` exits 2 saying `--route search-jobs needs --query-id`, and the
# jobs.jsonl path it was given is never created. `--route bogus` exits 2 the same way.
#
# This checks the characters in a value and never which sources exist. agent-data-reference/SKILL.md
# names the sources the API serves, and the API refuses the rest with a 400 — a second copy here
# would stop matching that one.
#
# There is no --run-id. A wrapper takes the run id from resolve-run.sh, which prints only a name
# matching its RUN_ID_GLOB at resolve-run.sh:62 — digits, dashes, `T` and `Z` — so a run id cannot
# hold any of the characters above. record-api-response.sh checks it at :104 anyway, because it takes
# the run id from its caller rather than from that script.
#
# Exit 0: nothing given here is a value record-api-response.sh refuses. It can still exit 2 over
#         something this script is not given: the run id it takes from its own caller, the response
#         file, or mktemp.
# Exit 2: record-api-response.sh would refuse one of these values, or this script's own arguments are
#         wrong. stderr names the rule.
set -u

usage() {
  printf 'usage: check-record-args.sh --route get-posting [--source S]\n' >&2
  printf '       check-record-args.sh --route search-jobs [--source S] --query-id ID\n' >&2
}

die() {
  printf 'check-record-args.sh: %s\n' "$1" >&2
  printf 'check-record-args.sh:   record-api-response.sh checks this before it records anything, so the call would be billed and no `call` event would name it\n' >&2
  exit 2
}

# The same `case` patterns record-api-response.sh matches, at :92-106 and :112-120.
check() {
  case $2 in
    *[[:cntrl:]]*) die "$1 may hold no control character" ;;
    *\\*)          die "$1 may hold no backslash: $2" ;;
    *,*|*:*)       die "$1 may hold neither a comma nor a colon: $2" ;;
  esac
}

route='' src='' query_id=''
while [ $# -gt 0 ]; do
  case $1 in
    --route)    [ $# -ge 2 ] || { usage; exit 2; }; route=$2;    shift 2 ;;
    --source)   [ $# -ge 2 ] || { usage; exit 2; }; src=$2;      shift 2 ;;
    --query-id) [ $# -ge 2 ] || { usage; exit 2; }; query_id=$2; shift 2 ;;
    *) usage; exit 2 ;;
  esac
done

# The order below is record-api-response.sh's: the route at :65-68, the characters at :92-120,
# then the query id at :130-136.
case $route in
  search-jobs|get-posting) ;;
  *) die "--route must be search-jobs or get-posting" ;;
esac

check --source "$src"
check --query-id "$query_id"

# Only a search needs one, and only a non-empty one counts: record-api-response.sh:130-136 treats
# an absent --query-id and an empty one the same way.
if [ "$route" = search-jobs ]; then
  [ -n "$query_id" ] || die "--route search-jobs needs a --query-id that is not empty"
fi

exit 0
