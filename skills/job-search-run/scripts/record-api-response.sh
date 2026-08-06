#!/bin/sh
# record-api-response.sh — turn one agent-data response into the events it implies.
#
# Usage: record-api-response.sh <run_id> <jobs.jsonl> <response.json> \
#          --route search-jobs|get-posting [--query-id ID] [--source S]
#
# A search-jobs response appends one `call` event and one `surfaced` event per new row, each value
# copied as the raw JSON it arrived as. A posting already judged in any run, and a posting this run
# already surfaced, are both skipped: one opening reached by two queries is one posting.
#
# The route is given, never guessed from the body. An error body carries no results and no
# description, so nothing in it identifies the route that produced it, and guessing files every
# failed detail read under searches.
#
# The `call` event is written for every attempt — a failed one and a repeat one included. It is the
# record that the call happened, and what a run's metered-call count is worked out from. The rows
# are all-or-nothing: a response with one unusable row appends none of its rows.
#
# A failed call writes its body to stderr and exits 1, so the caller captures it with `2>` and
# hands that file here.
#
# This is the scripted form of the model-run prose contract; that prose remains the no-runtime
# fallback, and on a host with no shell the run says in its summary that the counts were worked
# out by hand.
#
# Exit 0: the rows were appended, or the search legitimately returned none.
# Exit 1: no rows appended; stderr names the problem. The call event is still recorded.
# Exit 2: bad arguments, a missing file, or a body that is not what --route says it is.
set -u

here=$(dirname "$0")

usage() {
  printf 'usage: record-api-response.sh <run_id> <jobs.jsonl> <response.json> --route search-jobs|get-posting [--query-id ID] [--source S]\n' >&2
}

[ $# -ge 3 ] || { usage; exit 2; }
run_id=$1; jobs=$2; resp=$3; shift 3
route='' query_id='' src_flag=''
while [ $# -gt 0 ]; do
  case $1 in
    --route)    [ $# -ge 2 ] || { usage; exit 2; }; route=$2; shift 2 ;;
    --query-id) [ $# -ge 2 ] || { usage; exit 2; }; query_id=$2; shift 2 ;;
    --source)   [ $# -ge 2 ] || { usage; exit 2; }; src_flag=$2; shift 2 ;;
    *) printf 'record-api-response.sh: unknown option %s\n' "$1" >&2; usage; exit 2 ;;
  esac
done
case $route in
  search-jobs|get-posting) ;;
  *) printf 'record-api-response.sh: --route must be search-jobs or get-posting\n' >&2; exit 2 ;;
esac

[ -f "$resp" ] || { printf 'record-api-response.sh: no such file: %s\n' "$resp" >&2; exit 2; }
dir=$(dirname "$jobs"); [ -d "$dir" ] || mkdir -p "$dir"
[ -f "$jobs" ] || : > "$jobs"

scan=$(mktemp) || exit 2
new=$(mktemp) || exit 2
bad=$(mktemp) || exit 2
keep=$(mktemp) || exit 2
trap 'rm -f "$scan" "$new" "$bad" "$keep" "$bad.count"' EXIT INT HUP TERM

ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# One `call` event per attempt. Defined before anything can fail, so a failure still leaves it.
emit_call() {
  RAR_QUERY=$query_id RAR_REQ=${req:-} RAR_CODE=${code:-} \
  awk -v run_id="$run_id" -v ts="$ts" -v route="$route" -v source="$1" \
      -v ok="$2" -v returned="$3" -v new="$4" -v retryable="${retryable:-}" '
    function esc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return s }
    function jstr(s) { return "\"" esc(s) "\"" }
    function jopt(s) { return s == "" ? "null" : jstr(s) }
    BEGIN {
      out = "{\"event\":\"call\",\"run_id\":" jstr(run_id) ",\"ts\":" jstr(ts)
      out = out ",\"route\":" jstr(route)
      out = out ",\"source\":" jopt(source)
      out = out ",\"query_id\":" jopt(ENVIRON["RAR_QUERY"])
      out = out ",\"ok\":" ok
      out = out ",\"rows_returned\":" returned ",\"rows_new\":" new
      out = out ",\"error_code\":" jopt(ENVIRON["RAR_CODE"])
      out = out ",\"retryable\":" (retryable == "" ? "null" : retryable)
      out = out ",\"request_id\":" jopt(ENVIRON["RAR_REQ"])
      out = out "}"
      print out
    }' >> "$jobs"
}

# Scan once. A body we cannot parse is still a call that happened.
if ! awk -f "$here/json-scan.awk" "$resp" > "$scan" 2>/dev/null; then
  emit_call "$src_flag" false 0 0
  printf 'record-api-response.sh: %s is not well-formed JSON — the call is recorded, nothing else\n' \
    "$resp" >&2
  exit 1
fi

field() { awk -F'\t' -v p="$1" '$1 == p { print $2; exit }' "$scan" | sed 's/^"//; s/"$//'; }
# The pattern is written with [.] rather than \. because awk resolves escape sequences in a -v
# assignment before the string is ever used as a pattern: `-v p='^data\.query\.'` arrives as
# `^data.query.`, where each dot matches any character (measured — `dataXqueryYz` matches it).
haspath() { awk -F'\t' -v p="$1" '$1 ~ p { found = 1; exit } END { exit !found }' "$scan"; }

# An error body: a top-level `error` object. error.source is "service", never a job source.
if [ -n "$(field error.code)" ]; then
  code=$(field error.code)
  msg=$(field error.message)
  retryable=$(field error.retryable)
  req=$(field error.request_id)
  emit_call "$src_flag" false 0 0
  printf 'record-api-response.sh: the response is an error, not results: %s — %s (retryable %s)\n' \
    "${code:-unknown}" "${msg:-no message}" "${retryable:-unknown}" >&2
  exit 1
fi

req=$(field meta.request_id)

if [ "$route" = get-posting ]; then
  printf 'record-api-response.sh: --route get-posting is not handled yet\n' >&2
  exit 2
fi

# A search body carries data.query, and data.results[] when the search returned rows. A get-posting
# body carries neither — its fields are directly under data (measured on a live get-posting
# response) — so a posting handed here as a search is refused rather than recorded as a search that
# returned nothing.
haspath '^data[.](query|results)[.]' || {
  printf 'record-api-response.sh: %s carries neither data.query nor data.results — it is not a search-jobs response\n' \
    "$resp" >&2
  exit 2
}

awk -F'\t' -v run_id="$run_id" -v query_id="$query_id" -v ts="$ts" -v badfile="$bad" '
  function esc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return s }
  function fld(k) { return (k in v && v[k] != "") ? v[k] : "null" }
  function isstr(k) { return (k in v) && substr(v[k], 1, 1) == "\"" }

  # Only a row own field: data.results.<n>.<key>, four segments and no more. A nested object
  # inside a row has five and cannot overwrite the row that contains it.
  #
  # Whether a row is being filled is tracked by `open`, not by a sentinel value in `cur`. split()
  # makes p[3] a strnum, and an uninitialised `cur` compares equal to the number 0, so on row 0
  # `p[3] != cur` alone is false: the row is never opened, and its fields are thrown away when
  # row 1 starts. Measured before the fix — a 25-row response appended 24 rows.
  $1 ~ /^data\.results\.[0-9]+\.[^.]+$/ {
    split($1, p, ".")
    if (!open || p[3] != cur) { if (open) emit(); cur = p[3]; open = 1; delete v }
    v[p[4]] = $2
  }
  END { if (open) emit(); print rows+0 > (badfile ".count") }

  function emit(   out, pd, pb, eff, missing, notstr, k, i, req) {
    rows++
    split("source source_id id source_url", req, " ")
    missing = ""; notstr = ""
    for (i = 1; i <= 4; i++) {
      k = req[i]
      if (!(k in v) || v[k] == "" || v[k] == "null")
        missing = missing (missing == "" ? "" : ", ") k
      else if (!isstr(k))
        notstr = notstr (notstr == "" ? "" : ", ") k
    }
    if (missing != "" || notstr != "") {
      if (missing != "")
        printf "row %d is missing %s (title %s, company %s)\n", rows, missing,
               (("title" in v) ? v["title"] : "absent"),
               (("company_name" in v) ? v["company_name"] : "absent") >> badfile
      if (notstr != "")
        printf "row %d has a non-string %s — every script that finds a posting matches the quoted form, so this row would be surfaced and then unreachable\n",
               rows, notstr >> badfile
      delete v
      return
    }

    pd = v["posted_at"]; pb = v["published_at"]; eff = "null"
    if (pd != "" && pd != "null" && pb != "" && pb != "null") eff = (pd > pb ? pd : pb)
    else if (pd != "" && pd != "null") eff = pd
    else if (pb != "" && pb != "null") eff = pb

    out = "{\"event\":\"surfaced\""
    out = out ",\"run_id\":\"" esc(run_id) "\""
    out = out ",\"query_id\":\"" esc(query_id) "\""
    out = out ",\"source\":" fld("source")
    out = out ",\"source_id\":" fld("source_id")
    out = out ",\"posting_id_at_seen\":" fld("id")
    out = out ",\"source_url\":" fld("source_url")
    out = out ",\"title\":" fld("title")
    out = out ",\"company_name\":" fld("company_name")
    out = out ",\"location_display\":" fld("location_display")
    out = out ",\"salary_display\":" fld("salary_display")
    out = out ",\"employment_type\":" fld("employment_type")
    out = out ",\"department_name\":" fld("department_name")
    out = out ",\"team_name\":" fld("team_name")
    out = out ",\"is_remote\":" fld("is_remote")
    out = out ",\"workplace_type\":" fld("workplace_type")
    out = out ",\"posted_at\":" eff
    out = out ",\"detail_available\":" fld("detail_available")
    out = out ",\"ts\":\"" esc(ts) "\""
    out = out "}"
    print out
    delete v
  }
' "$scan" > "$new"

returned=$(cat "$bad.count" 2>/dev/null || echo 0)
src=$(head -1 "$new" 2>/dev/null | sed -n 's/.*"source":"\([^"]*\)".*/\1/p')
[ -n "$src" ] || src=$src_flag

if [ -s "$bad" ]; then
  emit_call "$src" true "$returned" 0
  printf 'record-api-response.sh: nothing was appended — %s\n' "$resp" >&2
  sed 's/^/record-api-response.sh:   /' "$bad" >&2
  exit 1
fi

# Skip a posting this run already surfaced, and one any run has already judged. The judged check
# is deliberately not scoped to this run: a posting with a verdict is not offered again.
awk -f "$here/event-field.awk" -f "$here/dedup-surfaced.awk" \
    -v jobs="$jobs" -v run_id="$run_id" "$new" > "$keep"

kept=$(wc -l < "$keep" | tr -d ' ')
emit_call "$src" true "$returned" "$kept"
[ "$kept" -gt 0 ] && cat "$keep" >> "$jobs"
printf 'record-api-response.sh: %s rows appended, %s rows in the response\n' "$kept" "$returned" >&2
exit 0
