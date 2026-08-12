#!/bin/sh
# record-judgment.sh — record one posting's judgment.
#
# Usage: record-judgment.sh [<jobs.jsonl>] [--run-id ID] --source S --source-id ID \
#          --detail-read true|false --relevant true|false [--match strong|moderate|weak] \
#          [--needs-human-check true|false] [--dealbreakers 'a;b'] [--unknowns 'a;b'] \
#          [--reasoning TEXT] [--same-role-as SOURCE:ID] [--posted-at-extracted DATE] [--ts TS]
#
# The script writes the JSON, so nothing the judgment says has to be escaped by whoever is calling.
# A judgment can only be about a posting a search surfaced for this run, and the title, company,
# location, URL and date come off that surfaced event rather than from the caller.
#
# The log path and --run-id are both optional. Left off, they come from resolve-run.sh, which reads
# the workspace and the runs/.started-<run_id> marker from disk. Passing either still works and
# still wins, which is what replaying an older run needs. --workspace is for the tests.
#
# A semicolon separates one dealbreaker or unknown from the next, so a dealbreaker that contains a
# semicolon has to be reworded. Spaces around the semicolon are trimmed, so `pay; then equity` and
# `pay;then equity` give the same two entries.
#
# A posting is judged once, and the judgment already in the log can have been recorded by an earlier
# run: the already-judged check below names no run. A judgment from an earlier run always lands on
# exit 1 rather than on the exit-0 retry path, and the refusal names the run that recorded it — or
# says the recorded judgment names no run, when it carries none. The comment above that check says
# why each of those is the right answer.
#
# Exit 0: recorded, or this posting already carries exactly this judgment.
# Exit 1: nothing written; stderr names the problem.
# Exit 2: nothing was written — no temporary file could be made, or the log path or the run id was
#         left off and resolve-run.sh found no workspace, no open run, or more than one. A flag
#         given without its value is the one case where the shell picks the status rather than this
#         script: measured 2026-08-12 on `--run-id` with nothing after it, at 1 under sh and bash
#         and 2 under dash.
set -u

here=$(dirname "$0")
# The first operand is the log only when it is not a flag, so the whole call can be flags.
jobs=''
case ${1-} in
  ''|--*) ;;
  *) jobs=$1; shift ;;
esac

run_id='' ws_flag='' source='' source_id='' detail_read='' relevant='' band=''
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
    --workspace)           ws_flag=${2?}; shift 2 ;;
    *) die "unknown option $1" ;;
  esac
done

[ -n "$source" ]    || die 'missing --source'
[ -n "$source_id" ] || die 'missing --source-id'

# One call to resolve-run.sh answers both, and only when something is missing, so a caller that
# passed everything does not depend on a workspace being discoverable.
if [ -z "$jobs" ] || [ -z "$run_id" ]; then
  resolved=$(sh "$here/resolve-run.sh" ${ws_flag:+--workspace "$ws_flag"}) || exit 2
  [ -n "$jobs" ]   || jobs=$(printf '%s\n' "$resolved" | sed -n 's/^workspace=//p')/jobs.jsonl
  [ -n "$run_id" ] || run_id=$(printf '%s\n' "$resolved" | sed -n 's/^run_id=//p')
fi
[ -f "$jobs" ] || die "no such log: $jobs"

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

# A judgment already recorded for this posting, by this run or by an earlier one. The same one again
# is a retry and changes nothing; anything else is a conflict the caller has to settle, so write
# neither.
#
# The lookup names no run. find-judgment.awk's header records that decision and names the two
# programs that read the log the same way. A posting judged in an earlier run only reaches this
# check when it was judged some way other than through a run that surfaced it — the surfaced check
# above requires a surfaced event from THIS run, and record-api-response.sh writes no surfaced event
# for a posting that already carries a judgment — so what usually reaches it is a judgment written
# into the log by hand.
#
# This lookup reads the fields with jval instead of grepping for their quoted text.
# event-log-append.sh accepts a judgment written by hand with a space after any colon, so such a
# line is in the log by design, and a chain of greps matching the quoted text finds none of it. The
# conflict below was then never reached and the second verdict went into the log. The measurement,
# and why the surfaced lookup above still greps, are in find-judgment.awk.
prev=$(awk -f "$here/event-field.awk" -f "$here/find-judgment.awk" \
           -v source="$source" -v source_id="$source_id" "$jobs")
prevstatus=$?

# The status is checked for the reason the builder's is checked above: an awk that died before
# printing anything looks exactly like a posting no one has judged yet, and this script would then
# append a second verdict for a posting that already has one.
[ "$prevstatus" -eq 0 ] || die 'reading the judgments already recorded failed — nothing written'

if [ -n "$prev" ]; then
  # The timestamp is dropped from both sides before they are compared: a retry a minute later writes
  # the same line but for its `ts`, and comparing the lines whole would send it to the branch below.
  #
  # A judgment recorded by an earlier run never matches here and always falls through to the
  # conflict below, because the line this call would write carries this run's `run_id` and the
  # recorded one carries the earlier run's, so dropping the timestamp still leaves the two lines
  # different. Exit 1 is the answer it should get. Exiting 0 here says the log already holds exactly
  # what this call was asked to record, so the caller can carry on; a verdict reached in an earlier
  # run, against whatever brief that run used, is not that, and nothing here can tell whether it
  # still stands. So the caller is stopped and both lines are printed for a person to compare.
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
  # like. test_a_judgment_written_with_spaces_after_its_colons_still_blocks_a_second_one, in
  # tests/test_mechanics_scripts.py, commits a prior of the second kind — a space after its first
  # four colons and none after `ts` — and its recorded line prints with no ts.
  #
  # The run the message names is the one written on the recorded judgment, read off that line, not
  # "$run_id". The lookup above is not scoped to a run, so the recorded judgment can come from an
  # earlier one, and naming the calling run would send the caller to a log entry that is not there.
  # The value is read the way validate-workspace.sh reads a field off a record: `grep -o` for the
  # key with its quoted value, the first match of it, then the fourth field when that match is split
  # on the quote character, which is the value whatever spacing the colon carries. A judgment written
  # by hand can carry no run_id at all — event-log-append.sh requires a source_id, and a source on an
  # evaluated event, and nothing else — so there is a second message for that, rather than an empty
  # run id in the first.
  prev_run=$(printf '%s\n' "$prev" \
             | grep -o '"run_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | cut -d'"' -f4)
  if [ -n "$prev_run" ]; then
    printf 'record-judgment: %s:%s already has a judgment recorded in run %s, and it is not the line this call would write — nothing written\n' \
      "$source" "$source_id" "$prev_run" >&2
  else
    printf 'record-judgment: %s:%s already has a judgment that names no run, and it is not the line this call would write — nothing written\n' \
      "$source" "$source_id" >&2
  fi
  printf 'record-judgment:   recorded: %s\n' "$a" >&2
  printf 'record-judgment:   offered:  %s\n' "$b" >&2
  exit 1
fi

# End the last line before appending, so this judgment is not written onto the last line of a log
# that ends without a newline. The joined line is read as the event above it, so the judgment is lost
# and every count the run reports is worked out without it. What `tail -c1 | wc -l` prints, why
# `[ -s ]` comes first, and the measurement under sh, dash and bash are written out at
# event-log-append.sh, above its own append.
if [ -s "$jobs" ] && [ "$(tail -c1 "$jobs" | wc -l)" -eq 0 ]; then printf '\n' >> "$jobs"; fi

cat "$line" >> "$jobs"
status=$?

# The verdict that landed, said back. The branch above that finds this exact verdict already
# recorded, and the one that finds a different judgment already recorded, each print a line saying
# nothing was written; without this line the branch that does write says nothing at all, so nothing
# on stdout, nothing on stderr and exit 0 covers both a recorded judgment and a refused one. Saying
# the verdict back also lets the caller check that the flags it passed are the fields the log now
# holds. The fields are read from the variables checked at the top of this script, not re-parsed
# from the line that was just written.
#
# The status is taken before the printf and given back after it, so when the append fails the caller
# still gets its non-zero exit status. Before this block was added, the `cat` above was the last
# command in the file and the script ended with the append's status, so `exit "$status"` gives back
# the status the script would have exited with anyway. The EXIT trap at :40 still removes the
# temporary file when the script ends at an explicit `exit` — measured under sh, dash and bash.
if [ "$status" -eq 0 ]; then
  verdict="relevant $relevant"
  [ -z "$band" ] || verdict="$verdict, match $band"
  verdict="$verdict, detail_read $detail_read"
  [ "$nhc" = true ] && verdict="$verdict, needs_human_check true"
  [ -z "$same_role" ] || verdict="$verdict, same_role_as $same_role"
  [ -z "$posted_extracted" ] || verdict="$verdict, posted_at_extracted $posted_extracted"
  printf 'record-judgment: recorded %s:%s for run %s — %s\n' \
    "$source" "$source_id" "$run_id" "$verdict" >&2
fi
exit "$status"
