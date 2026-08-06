#!/bin/sh
# close-run.sh — write one run's record. Deleting what the run was using is clear-run.sh's job,
# because the digest goes between the two.
#
# Usage: close-run.sh <workspace> <run_id> --trigger manual|scheduled \
#          [--scheduler-id ID] --close-state complete|blocked|interrupted \
#          [--brief-revision REV] [--sources 'a,b'] [--queries 'a,b']
#
# Prints one line, run_health=healthy or run_health=degraded, which the digest's header carries.
#
# Every count comes from run-counts.sh and completed_at from a clock read here, so no number in the
# record is anyone's account of the run. run_health is worked out the same way: healthy means the
# run closed complete, left no posting unjudged, and every search it attempted answered at least
# once. A single failed attempt inside a retry sequence that then succeeded is not a lost search,
# and a failed detail read is not a search — that posting gets judged from its summary row.
#
# A close_state of complete over unjudged postings is refused and nothing is written: a run that
# did not finish must not read as one that did. A lost search does not block the close; the run
# finished the work it could reach, and the record says degraded.
#
# run-counts.sh has two ways of exiting non-zero and they mean different things:
#
#   a finding — status 1 with `INVALID relevant-row-without-a-band=<n>` on the last line. Its END
#     block prints that line after every count line (run-counts.awk:88-104 then :105-108), so
#     seeing it last means the whole count set reached stdout. Measured on 2026-08-06 against a
#     two-line log of that shape: seventeen count lines, then the INVALID line, status 1. The
#     record is written and the finding goes to stderr.
#   a failure — any other non-zero status. Status 2 is no log at that path, and run-counts.sh runs
#     its awk with `exec`, so an awk that stops partway hands back its own status having already
#     written part of the key set to stdout. Reading keys off that would put numbers in the record
#     that no log supports, so nothing is written.
#
# Refusing both would leave a run with one unbanded row unclosable — no record, the marker still on
# disk — which is the state this script exists to remove, and the opposite of what open-run.sh
# settled for a broken workspace: a run opens anyway so that it can close with a record.
#
# A third case shows up in neither status: a reader that exits 0 having left a key out. An absent
# key reaches awk's `printf "%d"` as 0, so the thirteen keys this record is built from are checked
# for presence before anything is written.
#
# `../../job-search-run/scripts` is where run-counts.sh lives, and the walk out of this skill and
# into the next one holds because `skills/` ships as one directory in every packaging in this repo:
# `.codex-plugin`, `.cursor-plugin` and `.factory-plugin` each name `"skills": "./skills/"`,
# `.claude-plugin/plugin.json` names no path at all, and INSTALL_FOR_HERMES.md:206 checks
# `skills/job-search-runbook/scripts/workspace-discovery.sh` under the installed plugin.
#
# Exit 0: the record is written.
# Exit 1: nothing written; stderr names what contradicts the close.
#
# A missing operand is the exception the caller sees a shell-picked code for, the way
# run-counts.sh:28-29 records: measured at 1 under sh and bash and 2 under dash.
set -u

ws=${1:?usage: close-run.sh <workspace> <run_id> --trigger T --close-state S}
run_id=${2:?usage: close-run.sh <workspace> <run_id> --trigger T --close-state S}
shift 2

trigger='' scheduler_id='' close_state='' brief_rev='' sources='' queries=''
die() { printf 'close-run: %s\n' "$1" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case $1 in
    --trigger)         trigger=${2?}; shift 2 ;;
    --scheduler-id)    scheduler_id=${2?}; shift 2 ;;
    --close-state)     close_state=${2?}; shift 2 ;;
    --brief-revision)  brief_rev=${2?}; shift 2 ;;
    --sources)         sources=${2?}; shift 2 ;;
    --queries)         queries=${2?}; shift 2 ;;
    *) die "unknown option $1" ;;
  esac
done

case $trigger in manual|scheduled) ;; *) die '--trigger must be manual or scheduled' ;; esac
case $close_state in
  complete|blocked|interrupted) ;;
  *) die '--close-state must be complete, blocked or interrupted' ;;
esac

# Every value this script writes is an identifier — there is no free text among them — so each is
# refused rather than escaped, and refused here, before anything is written. An identifier stored
# escaped is one no `grep -F` lookup will ever match again, and a run_id carrying a newline names a
# file no later run can find. record-api-response.sh, queue-detail-read.sh and record-judgment.sh
# each carry the same check for the same reason: awk takes a literal newline in a -v assignment
# under mawk and refuses it under BSD awk, and awk resolves a backslash escape in a -v assignment
# before the program runs.
#
# --trigger and --close-state take no check here. The two case statements above already hold them
# to two and three words, which is stricter than this.
reject_id() {
  case $2 in
    *[[:cntrl:]]*) die "$1 may hold no control character" ;;
    *\\*)          die "$1 may hold no backslash: $2" ;;
  esac
}
reject_id '<run_id>' "$run_id"
reject_id --scheduler-id "$scheduler_id"
reject_id --brief-revision "$brief_rev"
reject_id --sources "$sources"
reject_id --queries "$queries"

[ -d "$ws" ] || die "no such workspace: $ws"
[ -d "$ws/runs" ] || mkdir -p "$ws/runs"

here=$(dirname "$0")
runscripts=$here/../../job-search-run/scripts
jobs=$ws/jobs.jsonl
# A run that opened and recorded nothing still closes, with a record of zeroes, rather than being
# stuck open: run-counts.sh exits 2 on a log that is not there.
[ -f "$jobs" ] || : > "$jobs"

counts=$(sh "$runscripts/run-counts.sh" "$jobs" "$run_id")
counts_status=$?

if [ "$counts_status" -ne 0 ]; then
  case $counts_status:$(printf '%s\n' "$counts" | tail -n 1) in
    1:INVALID\ relevant-row-without-a-band=*)
      printf 'close-run: run-counts.sh reported: %s\n' \
        "$(printf '%s\n' "$counts" | tail -n 1)" >&2 ;;
    *)
      die "run-counts.sh exited $counts_status, so this run's numbers are not known — nothing written, the marker and the scratch are untouched" ;;
  esac
fi

# The thirteen keys the record and the two checks below are built from. by_source_* is not among
# them: a run that surfaced nothing prints none.
for key in postings_surfaced postings_reviewed postings_unreviewed postings_detail_read \
           match_strong match_moderate match_weak filtered_out \
           calls_searches calls_detail_reads calls_other calls_total_metered \
           searches_never_succeeded; do
  printf '%s\n' "$counts" | grep -q "^$key=" || \
    die "run-counts.sh printed no $key, so this run's numbers are not all known — nothing written"
done

# -f2- rather than -f2, so a value carrying an `=` keeps it. searches_never_succeeded_ids holds
# `<source>:<query_id>` pairs, and a query id is model-supplied.
get() { printf '%s\n' "$counts" | grep "^$1=" | cut -d= -f2-; }
unreviewed=$(get postings_unreviewed)
lost=$(get searches_never_succeeded)
lostids=$(get searches_never_succeeded_ids)

# `[ "$x" -ne 0 ]` on a value that is not a number writes a diagnostic and exits non-zero, so the
# surrounding `if` runs its else branch. Measured on 2026-08-06 with x=many: `integer expression
# expected` under sh and bash, `Illegal number` under dash, and the else branch in all three. An
# unreadable postings_unreviewed would therefore read as no posting left unjudged, let a complete
# close through, and close the run healthy.
case $unreviewed in ''|*[!0-9]*) die "postings_unreviewed is not a number: $unreviewed" ;; esac
case $lost in ''|*[!0-9]*) die "searches_never_succeeded is not a number: $lost" ;; esac

if [ "$close_state" = complete ] && [ "$unreviewed" -ne 0 ]; then
  die "close_state complete, but $unreviewed postings were never judged — close interrupted, or judge them"
fi

# The rule as it is written down: complete, nothing left unjudged, and every search that was
# attempted answered at least once. The middle term decides nothing on its own — the refusal above
# has already stopped a complete close over unjudged postings, so reaching here with close_state
# complete means unreviewed is 0 — and it is spelled out anyway so the line reads as the rule.
run_health=degraded
if [ "$close_state" = complete ] && [ "$unreviewed" -eq 0 ] && [ "$lost" -eq 0 ]; then
  run_health=healthy
fi
[ "$lost" -eq 0 ] || \
  printf 'close-run: %s search(es) never returned and are not in these counts: %s\n' \
    "$lost" "$lostids" >&2

completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
started_at=$(printf '%s\n' "$run_id" | sed 's/T\(..\)-\(..\)-\(..\)Z$/T\1:\2:\3Z/')

record=$ws/runs/$run_id.json
tmp=$record.tmp

# No apostrophe may appear anywhere in this awk program: it is inside a single-quoted shell string,
# so one would end that string and the rest would be read as shell.
CR_COUNTS=$counts CR_SOURCES=$sources CR_QUERIES=$queries \
awk -v run_id="$run_id" -v trigger="$trigger" -v sched="$scheduler_id" \
    -v close_state="$close_state" -v run_health="$run_health" -v brief_rev="$brief_rev" \
    -v started_at="$started_at" -v completed_at="$completed_at" '
  # Byte-identical to the five in skills/job-search-run/scripts/ — compare them before you ship,
  # because a copy that drifts is how this defect got in. A one-line esc handling only the
  # backslash and the quote let a tab in a model-supplied value write 26 log lines with none of
  # them parsing, at exit 0; three escapes still left 29 of the 32 characters JSON forbids raw
  # inside a string doing the same. Both measured in Task 5.
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
  function jarr(s,   n, p, i, out) {
    if (s == "") return "[]"
    n = split(s, p, ",")
    out = "["
    for (i = 1; i <= n; i++) { if (i > 1) out = out ", "; out = out jstr(p[i]) }
    return out "]"
  }
  BEGIN {
    # The = is found with index rather than with split(rows[i], kv, "="), so a value keeps every
    # character after the first = rather than only the run up to the second one:
    # searches_never_succeeded_ids=ashby:role=staff stays whole.
    n = split(ENVIRON["CR_COUNTS"], rows, "\n")
    for (i = 1; i <= n; i++) {
      eq = index(rows[i], "=")
      if (eq == 0) continue
      key = substr(rows[i], 1, eq - 1); val = substr(rows[i], eq + 1)
      c[key] = val
      if (key ~ /^by_source_/) {
        s = key; sub(/^by_source_/, "", s)
        nsrc++; srck[nsrc] = s; srcv[nsrc] = val
      }
    }
    print "{"
    printf "  \"run_id\": %s,\n", jstr(run_id)
    printf "  \"trigger\": %s,\n", jstr(trigger)
    printf "  \"scheduler_id\": %s,\n", (sched == "" ? "null" : jstr(sched))
    printf "  \"brief_revision\": %s,\n", (brief_rev == "" ? "null" : jstr(brief_rev))
    printf "  \"close_state\": %s,\n", jstr(close_state)
    printf "  \"run_health\": %s,\n", jstr(run_health)
    printf "  \"sources\": %s,\n", jarr(ENVIRON["CR_SOURCES"])
    printf "  \"queries\": %s,\n", jarr(ENVIRON["CR_QUERIES"])
    printf "  \"postings_surfaced\": %d,\n", c["postings_surfaced"]
    printf "  \"postings_reviewed\": %d,\n", c["postings_reviewed"]
    printf "  \"postings_unreviewed\": %d,\n", c["postings_unreviewed"]
    printf "  \"postings_detail_read\": %d,\n", c["postings_detail_read"]
    printf "  \"matches\": { \"strong\": %d, \"moderate\": %d, \"weak\": %d },\n",
           c["match_strong"], c["match_moderate"], c["match_weak"]
    printf "  \"filtered_out\": %d,\n", c["filtered_out"]
    printf "  \"by_source\": {"
    for (i = 1; i <= nsrc; i++) {
      if (i > 1) printf ","
      printf " %s: %d", jstr(srck[i]), srcv[i]
    }
    printf " },\n"
    print  "  \"agent_data_usage\": {"
    printf "    \"searches\": %d,\n", c["calls_searches"]
    printf "    \"detail_reads\": %d,\n", c["calls_detail_reads"]
    printf "    \"other\": %d,\n", c["calls_other"]
    printf "    \"total_metered\": %d\n", c["calls_total_metered"]
    print  "  },"
    printf "  \"started_at\": %s,\n", jstr(started_at)
    printf "  \"completed_at\": %s\n", jstr(completed_at)
    print "}"
  }' > "$tmp"
buildstatus=$?

# Both the status and the file, the way record-judgment.sh:144 checks both. An awk that died before
# printing leaves this file empty; one that failed partway leaves a record that stops mid-field,
# and a half-written record at the real path would be worse than none. The marker and the scratch
# are still there to try again from.
if [ "$buildstatus" -ne 0 ] || [ ! -s "$tmp" ]; then
  rm -f "$tmp"
  die 'building the record failed — nothing written, the marker and the scratch are untouched'
fi
mv "$tmp" "$record"

printf 'run_health=%s\n' "$run_health"
printf 'close-run: wrote runs/%s.json (%s, %s)\n' "$run_id" "$close_state" "$run_health" >&2
