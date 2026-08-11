#!/bin/sh
# record-api-response.sh — turn one agent-data response into the events it implies.
#
# Usage: record-api-response.sh <run_id> <jobs.jsonl> <response.json> \
#          --route search-jobs --query-id ID [--source S]
#        record-api-response.sh <run_id> <jobs.jsonl> <response.json> \
#          --route get-posting [--source S]
#
# A search-jobs response appends one `call` event and one `surfaced` event per new row, each value
# copied as the raw JSON it arrived as. A posting already judged in any run, and a posting this run
# already surfaced, are both skipped: one opening reached by two queries is one posting.
#
# A get-posting response appends one `call` event and one `detail` event carrying the posting's
# full text. The posting must be one this run surfaced, and storing it twice in a run stores one
# `detail` event and reports the second read.
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
# Exit 0: the rows were appended, or the search legitimately returned none, or the posting was
#         already stored for this run and only its call was recorded.
# Exit 1: no rows appended; stderr names the problem. The call event is still recorded.
# Exit 2: bad arguments, a missing file, or a body that is not what --route says it is. A body that
#         was scanned still records its call — the file came off a metered call whatever shape it
#         arrived in — so only the checks that run before the scan leave no event: the argument
#         checks, the missing-file check, and mktemp.
set -u

here=$(dirname "$0")

usage() {
  printf 'usage: record-api-response.sh <run_id> <jobs.jsonl> <response.json> --route search-jobs --query-id ID [--source S]\n' >&2
  printf '       record-api-response.sh <run_id> <jobs.jsonl> <response.json> --route get-posting [--source S]\n' >&2
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

# An identifier is refused rather than escaped. Free text is the opposite case — esc writes a
# judgment reason out whole, control characters included — but a run id, a source and a query id
# name things other scripts look up, and neither of these two characters survives the trip:
#
#   A control character does not cross awk -v the same way twice. A literal newline in a -v
#   assignment is a syntax error under BSD awk (`newline in string`) and an accepted value under
#   mawk, which is the awk Ubuntu CI runs — measured, the same queue-detail-read.sh command wrote no
#   queued event under one and one under the other. esc would make the value
#   valid JSON wherever it did arrive, but it would then sit in the log escaped while every lookup
#   greps for the raw form it was handed, so the posting could never be found again.
#
#   A backslash is resolved by awk before the program runs, so --query-id a\tb reaches the row
#   builder as a real tab through -v and reaches emit_call as the four characters through the
#   environment. Measured at that point: the call event carried a\tb and all 25 surfaced events
#   carried a tab, and run-counts.sh groups on the call event, so the group and its rows disagreed.
#
# The same three checks, in the same order, are in queue-detail-read.sh and record-judgment.sh.
reject_id() {
  case $2 in
    *[[:cntrl:]]*)
      printf 'record-api-response.sh: %s may hold no control character\n' "$1" >&2
      printf 'record-api-response.sh:   awk takes a newline in a -v assignment on one host and refuses it on the next, and an escaped value is one no later lookup can grep for\n' >&2
      exit 2 ;;
    *\\*)
      printf 'record-api-response.sh: %s may hold no backslash: %s\n' "$1" "$2" >&2
      printf 'record-api-response.sh:   awk resolves the escape in a -v assignment, so the value reaching the event is not the value passed in\n' >&2
      exit 2 ;;
  esac
}
reject_id run_id "$run_id"
reject_id --source "$src_flag"
reject_id --query-id "$query_id"

# --source and --query-id are the two halves of the source:query_id pair run-counts.sh names a
# search that never returned by, in a comma-separated list. A comma in either splits that list at
# the wrong place and a colon splits the pair at the wrong place: measured, three failed attempts
# with --source a,b reported searches_never_succeeded_ids=a,b:q1, which reads as two lost searches.
for pair_half in "$src_flag" "$query_id"; do
  case $pair_half in
    *,*|*:*)
      printf 'record-api-response.sh: --source and --query-id may hold neither a comma nor a colon: %s\n' \
        "$pair_half" >&2
      printf 'record-api-response.sh:   run-counts.sh names the searches that never returned as a comma-separated list of source:query_id pairs\n' >&2
      exit 2 ;;
  esac
done

# A search call needs a query id, because run-counts.sh groups the search calls by source and query
# id and calls a group with no attempt that returned a search that never returned. Every search on
# one source with no query id lands in one group, so a search that returned marks the group answered
# and a search whose attempts all failed stops being counted: measured on two linkedin searches, one
# that returned and one whose 3 attempts all failed, both written with no query id —
# searches_never_succeeded is 0, so nothing in a run's numbers says a whole search never returned.
#
# A detail read is not grouped, so --route get-posting takes no query id.
if [ "$route" = search-jobs ]; then
  [ -n "$query_id" ] || {
    printf 'record-api-response.sh: --route search-jobs needs --query-id\n' >&2
    printf 'record-api-response.sh:   a search call with no query id is grouped with every other one on its source, so a search that never returned stops being counted\n' >&2
    exit 2
  }
fi

[ -f "$resp" ] || { printf 'record-api-response.sh: no such file: %s\n' "$resp" >&2; exit 2; }
dir=$(dirname "$jobs"); [ -d "$dir" ] || mkdir -p "$dir"
[ -f "$jobs" ] || : > "$jobs"

scan=$(mktemp) || exit 2
new=$(mktemp) || exit 2
bad=$(mktemp) || exit 2
keep=$(mktemp) || exit 2
trap 'rm -f "$scan" "$new" "$bad" "$keep" "$bad.count"' EXIT INT HUP TERM

ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# End the last line of the log, so the event a caller is about to append is not written onto the last
# line of a log that ends without a newline. Every field reader takes a key's first occurrence, so a
# joined line is read as the earlier event and the appended one is lost. What `tail -c1 | wc -l`
# prints, why `[ -s ]` comes first, and the measurement under sh, dash and bash are written out at
# event-log-append.sh, above its own append.
#
# This script appends in three places and calls this before each of them. The call inside `emit_call`
# is the one that runs against a log some other writer left ending without a newline. The two
# before the `cat` appends run against one this script left that way itself: it sets `-u` and never
# `-e` (`grep -n '^set ' ` on this file gives a single line), and no call site checks what
# `emit_call` returned, so an awk that died partway through the call event leaves a fragment with no
# newline after it and the script appends the posting or the rows anyway. Measured 2026-08-08
# against an awk shimmed to write half a call event and exit 2 — with the call before the detail
# `cat` deleted, the detail event landed on the end of that fragment, and with the one before the
# rows `cat` deleted, the first surfaced row did. Their cases are
# test_a_detail_event_is_not_appended_onto_a_half_written_call_event and
# test_the_first_surfaced_row_is_not_appended_onto_a_half_written_call_event, in
# tests/test_mechanics_scripts.py.
end_last_line() {
  if [ -s "$jobs" ] && [ "$(tail -c1 "$jobs" | wc -l)" -eq 0 ]; then printf '\n' >> "$jobs"; fi
}

# One `call` event per attempt. Defined before anything can fail, so a failure still leaves it.
emit_call() {
  end_last_line
  RAR_QUERY=$query_id RAR_REQ=${req:-} RAR_CODE=${code:-} \
  awk -v run_id="$run_id" -v ts="$ts" -v route="$route" -v source="$1" \
      -v ok="$2" -v returned="$3" -v newrows="$4" -v retryable="${retryable:-}" '
    function esc(s,   i, c) {
      gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s)
      gsub(/\t/, "\\t", s); gsub(/\r/, "\\r", s); gsub(/\n/, "\\n", s)
      # Every other control character JSON forbids raw inside a string, written as \u00xx. index()
      # first, so a long value is scanned 31 times rather than rewritten 31 times.
      for (i = 1; i < 32; i++) {
        c = sprintf("%c", i)
        if (index(s, c)) gsub(c, sprintf("\\u%04x", i), s)
      }
      return s
    }
    function jstr(s) { return "\"" esc(s) "\"" }
    function jopt(s) { return s == "" ? "null" : jstr(s) }
    BEGIN {
      out = "{\"event\":\"call\",\"run_id\":" jstr(run_id) ",\"ts\":" jstr(ts)
      out = out ",\"route\":" jstr(route)
      out = out ",\"source\":" jopt(source)
      out = out ",\"query_id\":" jopt(ENVIRON["RAR_QUERY"])
      out = out ",\"ok\":" ok
      out = out ",\"rows_returned\":" returned ",\"rows_new\":" newrows
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
# The same value with its quotes still on. `field` strips them, and that makes three different
# things look alike: a JSON null arrives as the four characters null, which is what a posting whose
# source_id is the string "null" also gives, and a JSON empty string arrives as nothing at all.
# Only the raw form tells them apart.
rawfield() { awk -F'\t' -v p="$1" '$1 == p { print $2; exit }' "$scan"; }
# The pattern is written with [.] rather than \. because awk resolves escape sequences in a -v
# assignment before the string is ever used as a pattern: `-v p='^data\.query\.'` arrives as
# `^data.query.`, where each dot matches any character (measured — `dataXqueryYz` matches it).
haspath() { awk -F'\t' -v p="$1" '$1 ~ p { found = 1; exit } END { exit !found }' "$scan"; }

# An error body: a top-level `error` object. error.source names what rejected the call — "service"
# or "client" — and is never a job source, so nothing below reads a source out of it.
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
  # A posting body carries the posting's own fields under data, with no results array. The pattern
  # uses [.] rather than \. for the reason given at haspath above: awk resolves the escape in a -v
  # assignment, and the dot would then match any character.
  haspath '^data[.]source_id$' || {
    emit_call "$src_flag" false 0 0
    printf 'record-api-response.sh: %s carries no data.source_id — it is not a get-posting response; the call is recorded, nothing else\n' \
      "$resp" >&2
    exit 2
  }

  # The same four checks the row builder makes on the search half, for the same reasons: absent,
  # JSON null, JSON empty string, and a value that is not a string at all. Read raw, so a posting
  # whose source_id is the string "null" stays a real value — quoted it is six characters, the JSON
  # null is four. Without these a null or a number reaches the surfaced check and the operator is
  # told the run never surfaced the posting, sending them to the search results when the fault is
  # in the body. A JSON object or array never gets this far: the shape gate above wants
  # data.source_id as a scalar path.
  missing='' notstring=''
  for dfield in data.source data.source_id; do
    case $(rawfield "$dfield") in
      ''|null|'""') missing="${missing:+$missing and }$dfield" ;;
      '"'*) ;;
      *) notstring="${notstring:+$notstring and }$dfield" ;;
    esac
  done
  [ -z "$missing" ] || {
    emit_call "$src_flag" false 0 0
    printf 'record-api-response.sh: %s has no usable %s — absent, null, or an empty string; the call is recorded, nothing else\n' \
      "$resp" "$missing" >&2
    exit 2
  }
  [ -z "$notstring" ] || {
    emit_call "$src_flag" false 0 0
    printf 'record-api-response.sh: %s has a non-string %s — every script that finds a posting matches the quoted form, so this posting would be stored and then unreachable; the call is recorded, nothing else\n' \
      "$resp" "$notstring" >&2
    exit 2
  }

  dsrc=$(field data.source)
  dsid=$(field data.source_id)

  # Every posting this run stores must be one a search surfaced for it. Scoped to this run, unlike
  # the judged check the search path uses: the text is stored against the summary row this run
  # surfaced, and a run that never surfaced the posting has no row to store it against.
  if ! grep -F '"event":"surfaced"' "$jobs" \
       | grep -F "\"run_id\":\"$run_id\"" \
       | grep -F "\"source\":\"$dsrc\"" \
       | grep -qF "\"source_id\":\"$dsid\""; then
    emit_call "$dsrc" true 1 0
    printf 'record-api-response.sh: no surfaced posting for %s:%s in run %s\n' \
      "$dsrc" "$dsid" "$run_id" >&2
    exit 1
  fi

  # Already stored: nothing new to write, but the call was still made and still billed.
  if grep -F '"event":"detail"' "$jobs" \
       | grep -F "\"run_id\":\"$run_id\"" \
       | grep -F "\"source\":\"$dsrc\"" \
       | grep -qF "\"source_id\":\"$dsid\""; then
    emit_call "$dsrc" true 1 0
    printf 'record-api-response.sh: %s:%s already stored for this run — the call is recorded, nothing else\n' \
      "$dsrc" "$dsid" >&2
    exit 0
  fi

  # data own fields only: two segments, so a nested object under data cannot reach the event. A
  # live posting body nests — address_structured and compensation_structured are objects,
  # secondary_locations and missing_fields are arrays.
  #
  # No apostrophe may appear anywhere in this awk program: it is inside a single-quoted shell
  # string, so one would end that string and the rest would be read as shell.
  awk -F'\t' -v run_id="$run_id" -v ts="$ts" '
    function esc(s,   i, c) {
      gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s)
      gsub(/\t/, "\\t", s); gsub(/\r/, "\\r", s); gsub(/\n/, "\\n", s)
      # Every other control character JSON forbids raw inside a string, written as \u00xx. index()
      # first, so a long value is scanned 31 times rather than rewritten 31 times.
      for (i = 1; i < 32; i++) {
        c = sprintf("%c", i)
        if (index(s, c)) gsub(c, sprintf("\\u%04x", i), s)
      }
      return s
    }
    function fld(k) { return (k in v && v[k] != "") ? v[k] : "null" }
    $1 ~ /^data\.[^.]+$/ { split($1, p, "."); v[p[2]] = $2 }
    END {
      out = "{\"event\":\"detail\",\"run_id\":\"" esc(run_id) "\""
      out = out ",\"source\":" fld("source")
      out = out ",\"source_id\":" fld("source_id")
      out = out ",\"description_markdown\":" fld("description_markdown")
      out = out ",\"employment_type\":" fld("employment_type")
      out = out ",\"apply_url\":" fld("apply_url")
      out = out ",\"is_listed\":" fld("is_listed")
      out = out ",\"is_remote\":" fld("is_remote")
      out = out ",\"workplace_type\":" fld("workplace_type")
      out = out ",\"staleness_status\":" fld("staleness_status")
      out = out ",\"ts\":\"" esc(ts) "\""
      out = out "}"
      print out
    }
  ' "$scan" > "$new"
  detailstatus=$?

  # Both the status and the file, for the reason the row builder checks both: the line is printed
  # in the END block, so an awk that died leaves no line, and one that failed after printing would
  # leave a line built from part of the body and store it as the whole posting.
  if [ "$detailstatus" -ne 0 ] || [ ! -s "$new" ]; then
    emit_call "$dsrc" true 1 0
    printf 'record-api-response.sh: building the detail event for %s:%s failed — the call is recorded, nothing else\n' \
      "$dsrc" "$dsid" >&2
    exit 1
  fi

  emit_call "$dsrc" true 1 1
  end_last_line
  cat "$new" >> "$jobs"
  printf 'record-api-response.sh: stored %s:%s\n' "$dsrc" "$dsid" >&2
  exit 0
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
  function esc(s,   i, c) {
    gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s)
    gsub(/\t/, "\\t", s); gsub(/\r/, "\\r", s); gsub(/\n/, "\\n", s)
    # Every other control character JSON forbids raw inside a string, written as \u00xx. index()
    # first, so a long value is scanned 31 times rather than rewritten 31 times.
    for (i = 1; i < 32; i++) {
      c = sprintf("%c", i)
      if (index(s, c)) gsub(c, sprintf("\\u%04x", i), s)
    }
    return s
  }
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
    # A JSON empty string arrives from the scanner as the two characters "", where the awk empty
    # string is what an absent key gives, so it has to be named separately. Without it a row
    # carrying "source_id":"" is appended and can then never be found again, which is the outcome
    # the non-string branch below refuses in its own error text.
    #
    # No apostrophe may appear anywhere in this awk program: it is inside a single-quoted shell
    # string, so one would end that string and the rest would be read as shell.
    for (i = 1; i <= 4; i++) {
      k = req[i]
      if (!(k in v) || v[k] == "" || v[k] == "null" || v[k] == "\"\"")
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
rowstatus=$?

# Check the status, and check the count file the END block writes. Both matter, and for the same
# reason the scanner above is checked rather than piped: the rows read before a failure are already
# in "$new". Without this, an awk that died partway leaves no count file, `returned` falls back to
# 0, and the run appends those partial rows next to a call event saying the call returned nothing.
if [ "$rowstatus" -ne 0 ] || [ ! -f "$bad.count" ]; then
  emit_call "$src_flag" false 0 0
  printf 'record-api-response.sh: reading the rows of %s failed — the call is recorded, nothing else\n' \
    "$resp" >&2
  exit 1
fi

returned=$(cat "$bad.count")
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
if ! awk -f "$here/event-field.awk" -f "$here/dedup-surfaced.awk" \
     -v jobs="$jobs" -v run_id="$run_id" "$new" > "$keep"; then
  # "$keep" holds whatever was printed before the failure, so appending it would record part of a
  # response as all of it. The row count is known here, so the call event still carries it.
  emit_call "$src" true "$returned" 0
  printf 'record-api-response.sh: skipping the postings already seen failed — nothing was appended for %s\n' \
    "$resp" >&2
  exit 1
fi

kept=$(wc -l < "$keep" | tr -d ' ')
emit_call "$src" true "$returned" "$kept"
[ "$kept" -gt 0 ] && { end_last_line; cat "$keep" >> "$jobs"; }
printf 'record-api-response.sh: %s rows appended, %s rows in the response\n' "$kept" "$returned" >&2
exit 0
