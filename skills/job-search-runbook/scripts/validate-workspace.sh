#!/bin/sh
# validate-workspace.sh — check a workspace's files against the mechanical rules.
#
# Every mechanical rule about workspace files lives here, so a skill never has to restate one in
# prose: which keys config.yaml must carry and what shape their values take, the front matter
# preferences.md needs, the fields a run record must get right, and the leftovers a finished run
# must not leave behind.
#
# Prints one line per broken rule — `INVALID <file> <rule> [observed value]` — and exits 1. A
# workspace with nothing wrong prints nothing and exits 0. Bad arguments or a missing workspace
# exit 2 with a message on stderr; those are the caller's mistake, not the workspace's.
#
# Usage: validate-workspace.sh WORKSPACE [--post-close RUN_ID]
#   --post-close RUN_ID   also check run RUN_ID: that it left no started-marker and no scratch dir,
#                         and that its record's counts and timestamps hold up. Every count the
#                         record states is read back out of jobs.jsonl with run-counts.sh and
#                         compared, including each match band and each source the log names; the
#                         record's own three sums are checked with or without a log; and completed_at
#                         is required to be no earlier than started_at and no later than the
#                         record's mtime.
set -u

WS=''
POST_CLOSE=''

usage() {
  printf 'usage: validate-workspace.sh WORKSPACE [--post-close RUN_ID]\n' >&2
}

while [ $# -gt 0 ]; do
  case $1 in
    --post-close)
      if [ $# -lt 2 ]; then usage; exit 2; fi
      POST_CLOSE=$2
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    -*) printf 'validate-workspace.sh: unknown option %s\n' "$1" >&2; usage; exit 2 ;;
    *)
      if [ -n "$WS" ]; then usage; exit 2; fi
      WS=$1
      shift
      ;;
  esac
done

if [ -z "$WS" ]; then usage; exit 2; fi
if [ ! -d "$WS" ]; then
  printf 'validate-workspace.sh: no such workspace: %s\n' "$WS" >&2
  exit 2
fi

# A run id is a UTC timestamp with dashes where a time would use colons: 2026-07-16T14-30-00Z.
# Run-record filenames carry it. `runs/` holds files that are not run records, so a file counts as a
# run record only when its whole name matches this.
#
# A `case` glob rather than a grep on the value. POSIX pattern matching compares the whole word and
# has no notion of lines, while `printf '%s\n' "$v" | grep -qE ...` exits 0 when ANY line matches.
# Measured on 2026-08-07 by putting the grep form back and running the suite: a file named
# `2026-07-16T14-30-00Z<newline>.json` was read as a run record rather than skipped, and each
# finding about it printed across two lines — `INVALID runs/2026-07-16T14-30-00Z`, then
# `.json missing-key close_state`. A caller counting INVALID lines counts two findings as four, and
# the path on the first line of each pair is not the path of any file. `--post-close` took all four
# of the run ids tests/test_validate_workspace.py names for it, each carrying a newline, at exit 1
# rather than the exit 2 an unusable run id gets.
#
# The digits are written out one by one rather than as `[0-9]`, because a range inside a bracket
# expression is decided by the collation order the locale sets and a list of ten characters is not.
# close-run.sh records the measurement — `grep -n 'digits are written out'
# skills/job-search-runbook/scripts/close-run.sh`: under LC_ALL=ar_SA.UTF-8 in sh and bash,
# `[0-9]` matched a run id spelled in Arabic-Indic digits. Which shell reads this file decides
# whether that matters here — measured on 2026-08-07, bash under that
# locale matched them and dash refused them, on macOS and on Debian alike, and `/bin/sh` is bash on
# one and dash on the other. close-run.sh and clear-run.sh each carry the same glob — `grep -n
# '0123456789' skills/job-search-runbook/scripts/close-run.sh
# skills/job-search-runbook/scripts/clear-run.sh` — and tests/test_mechanics_scripts.py drives one
# table of run ids through all three and requires the same verdict for each.
RUN_ID_GLOB='[0123456789][0123456789][0123456789][0123456789]-[0123456789][0123456789]-[0123456789][0123456789]T[0123456789][0123456789]-[0123456789][0123456789]-[0123456789][0123456789]Z'
# Run-record timestamps are UTC with a trailing Z. An offset such as +00:00 names the same instant
# but fails: with one written form, comparing two timestamps is a plain string compare. This one
# stays a regular expression because a fractional second is one or more digits and a glob cannot
# say "one or more" — and the value reaching it comes from json_str, which reads one line of one
# grep match, so there is no multi-line value for a per-line grep to be wrong about.
UTC_TS_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$'

if [ -n "$POST_CLOSE" ]; then
  case $POST_CLOSE in
    $RUN_ID_GLOB) ;;
    *)
      printf 'validate-workspace.sh: --post-close needs a run id like 2026-07-16T14-30-00Z, got: %s\n' \
        "$POST_CLOSE" >&2
      exit 2 ;;
  esac
fi

findings=$(mktemp) || exit 2
# The reference file the completed_at gate stamps. Both temp files are made here, so the trap that
# removes them names two values that are always set.
tsref=$(mktemp) || { rm -f "$findings"; exit 2; }
trap 'rm -f "$findings" "$tsref"' EXIT INT HUP TERM

# Report one broken rule: the file it is about, the rule, and the observed value when short.
invalid() {
  printf 'INVALID %s %s\n' "$1" "$2" >> "$findings"
}

# Read one JSON string value by key. Same idiom as the other mechanics scripts: no jq, no python.
json_str() {
  grep -o "\"$2\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$1" 2>/dev/null | head -1 | cut -d'"' -f4
}

# Read one JSON number by key, at the top level of the record.
#
# The leading zeros come off, because every number this script reads reaches `$(( ))` or `test -eq`
# and POSIX arithmetic reads a leading zero as octal. `08` is not a valid octal number, and an
# arithmetic syntax error is fatal: measured on 2026-08-07 on a record carrying
# `"postings_reviewed": 08` and no close_state, sh exited 1 and dash exited 2 with EVERY finding
# collected so far unprinted, and bash carried on. A count written that way is still that count, so
# it is read as 8 rather than reported. json_num's own pattern is a minus and digits, so a leading
# zero is the only value it can return that arithmetic refuses.
json_num() {
  grep -o "\"$2\"[[:space:]]*:[[:space:]]*-\{0,1\}[0-9][0-9]*" "$1" 2>/dev/null \
    | head -1 | sed 's/.*:[[:space:]]*//; s/^\(-\{0,1\}\)0*\([0-9]\)/\1\2/'
}

# Every `"<key>": <number>` member of the object one top-level key names, printed as one
# `<key>=<number>` line each. `matches` and `by_source` are the two objects the record has.
#
# The newlines come out first, so the object may be on one line, the way close-run.sh writes it, or
# split over several. Reading it per line finds nothing on a split record, and every band comparison
# was then skipped — a check that reports nothing rather than one that fails.
#
# awk rather than a second grep, because a source name is model-supplied: record-api-response.sh
# refuses only a control character and a backslash, so `*` is an accepted source. Built into a
# regular expression that name matches the wrong member. Measured on 2026-08-07 with the grep form
# and a run whose only source was `*`: a record stating `by_source { "AAAA": 99 }` drew no finding.
# index() compares literal text, so a name is looked up as itself.
#
# A name holding a `"` reads as the text up to that quote and so matches no key the log has, which
# reports a missing key rather than passing a wrong number.
#
# The name has to be followed by a colon and then an opening brace, and every occurrence is tried
# until one is. `sources` and `queries` hold model-supplied words, so `"by_source"` can appear in
# the record as a value rather than as a key — and taking the first occurrence and then looking
# ahead for a brace would read the next object along, which is `matches`.
json_obj_nums() {
  tr '\n' ' ' < "$1" 2>/dev/null | awk -v want="$2" '
    {
      s = $0
      while ((i = index(s, "\"" want "\"")) > 0) {
        rest = substr(s, i + length(want) + 2)
        s = rest
        if (rest !~ /^[ \t]*:/) continue
        sub(/^[ \t]*:[ \t]*/, "", rest)
        if (substr(rest, 1, 1) != "{") continue
        e = index(rest, "}")
        if (e == 0) exit
        obj = substr(rest, 2, e - 2)
        while ((q1 = index(obj, "\"")) > 0) {
          obj = substr(obj, q1 + 1)
          q2 = index(obj, "\"")
          if (q2 == 0) break
          k = substr(obj, 1, q2 - 1)
          obj = substr(obj, q2 + 1)
          sub(/^[ \t]*:[ \t]*/, "", obj)
          v = obj
          sub(/[^-0-9].*$/, "", v)
          # %d reads 08 as 8, which is why nothing here has to strip a leading zero by hand.
          if (v ~ /^-?[0-9]+$/) printf "%s=%d\n", k, v
        }
        exit
      }
    }'
}

# One member of that list, looked up by its whole key. The parameter expansions compare text, so a
# key holding a regular-expression character is looked up as itself.
objval() {
  printf '%s\n' "$2" | while IFS= read -r kv; do
    if [ "${kv%%=*}" = "$1" ]; then printf '%s' "${kv##*=}"; break; fi
  done
}

# One awk function, prepended to both file checks below, that reads a YAML scalar as written. Both
# config.yaml values and preferences.md front-matter values go through it, so `2026-07-30` and
# `"2026-07-30"` are read the same way. Keeping it in one place is the point: when only the config
# check stripped quotes, a quoted date in the brief failed validation on a workspace that worked.
AWK_SCALAR='
    function clean(v,   q, i) {
      # A quoted value is exactly what is between the quotes. An unquoted one runs up to a trailing
      # comment, and only a # that follows a space starts one.
      q = substr(v, 1, 1)
      if (q == "\"" || q == "\047") {
        v = substr(v, 2)
        i = index(v, q)
        if (i > 0) v = substr(v, 1, i - 1)
        return v
      }
      sub(/[ \t]+#.*$/, "", v)
      sub(/[ \t]+$/, "", v)
      return v
    }
'

# ------------------------------------------------------------------------------------ config.yaml
# config.yaml is written by setup and hand-edited by the user, and it stays simple enough to read
# line by line: top-level keys at column 0, their settings indented under them. Required keys are
# version, queries, search.sources, and schedule. Any other key a workspace carries is left alone.
if [ ! -f "$WS/config.yaml" ]; then
  invalid config.yaml missing-file
else
  awk "$AWK_SCALAR"'
    {
      line = $0
      sub(/\r$/, "", line)
      if (line ~ /^[ \t]*#/ || line ~ /^[ \t]*$/) next
      stripped = line
      sub(/^[ \t]+/, "", stripped)
      if (stripped !~ /^[A-Za-z_][A-Za-z0-9_-]*[ \t]*:/) next     # list items and continuations
      indent = length(line) - length(stripped)
      key = stripped
      sub(/[ \t]*:.*$/, "", key)
      value = stripped
      sub(/^[A-Za-z_][A-Za-z0-9_-]*[ \t]*:[ \t]*/, "", value)
      if (indent == 0) {
        section = key
        if (key == "version")  { has_version = 1; version_value = clean(value) }
        if (key == "queries")  { has_queries = 1 }
        if (key == "schedule") { has_schedule = 1 }
        next
      }
      if (section == "search" && key == "sources") { has_sources = 1; sources = clean(value) }
    }
    END {
      if (!has_version)  print "INVALID config.yaml missing-key version"
      else {
        if (version_value !~ /^[0-9]+$/)
          print "INVALID config.yaml version-not-a-number " version_value
      }
      if (!has_queries)  print "INVALID config.yaml missing-key queries"
      if (!has_schedule) print "INVALID config.yaml missing-key schedule"
      if (!has_sources)  print "INVALID config.yaml missing-key search.sources"
      # A sources value with no letter or digit in it — `[]`, `""` — names no source to search.
      else if (sources !~ /[A-Za-z0-9]/) print "INVALID config.yaml empty-value search.sources"
    }' "$WS/config.yaml" >> "$findings"
fi

# ---------------------------------------------------------------------------------- preferences.md
# The brief opens with a `---` front-matter block holding the dates the home view reads to show how
# old the brief is (`updated_at`, falling back to `created_at`).
if [ ! -f "$WS/preferences.md" ]; then
  invalid preferences.md missing-file
else
  awk "$AWK_SCALAR"'
    function iso(d,   date, time) {
      # A plain date, or a date and time. Both patterns are anchored at both ends, so a date with
      # anything trailing it — `2026-07-30T18:04:00nonsense` — is not an ISO date.
      date = "^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]"
      if (d ~ date "$") return 1
      time = "T[0-9][0-9]:[0-9][0-9]:[0-9][0-9](\\.[0-9]+)?(Z|[+-][0-9][0-9]:[0-9][0-9])?$"
      return d ~ (date time)
    }
    { line = $0; sub(/\r$/, "", line) }
    NR == 1 { if (line != "---") { no_front_matter = 1; exit } ; next }
    closed { next }
    line == "---" { closed = 1; next }
    {
      key = line
      sub(/[ \t]*:.*$/, "", key)
      value = line
      sub(/^[A-Za-z_][A-Za-z0-9_-]*[ \t]*:[ \t]*/, "", value)
      value = clean(value)
      if (key == "created_at") { created = value; has_created = 1 }
      if (key == "updated_at") { updated = value; has_updated = 1 }
    }
    END {
      if (NR == 0 || no_front_matter) { print "INVALID preferences.md front-matter"; exit }
      if (!closed) { print "INVALID preferences.md front-matter-unterminated"; exit }
      if (!has_created)       print "INVALID preferences.md missing-key created_at"
      else if (created == "") print "INVALID preferences.md empty-value created_at"
      else if (!iso(created)) print "INVALID preferences.md created_at-not-iso " created
      if (!has_updated)       print "INVALID preferences.md missing-key updated_at"
      else if (updated == "") print "INVALID preferences.md empty-value updated_at"
      else if (!iso(updated)) print "INVALID preferences.md updated_at-not-iso " updated
    }' "$WS/preferences.md" >> "$findings"
fi

# ------------------------------------------------------------------------------------ run records
# Check the fields every version of the run record shares. Extra keys pass: the record gains fields
# over time, and records written by older versions must still be readable.
if [ -d "$WS/runs" ]; then
  for record in "$WS"/runs/*.json; do
    [ -f "$record" ] || continue
    name=${record##*/}
    id=${name%.json}
    case $id in $RUN_ID_GLOB) ;; *) continue ;; esac
    rel="runs/$name"

    body_id=$(json_str "$record" run_id)
    if [ -z "$body_id" ]; then
      invalid "$rel" "missing-key run_id"
    elif [ "$body_id" != "$id" ]; then
      invalid "$rel" "run-id-not-the-filename $body_id"
    fi

    trigger=$(json_str "$record" trigger)
    case $trigger in
      manual|scheduled) ;;
      '') invalid "$rel" "missing-key trigger" ;;
      *)  invalid "$rel" "trigger-not-manual-or-scheduled $trigger" ;;
    esac

    close_state=$(json_str "$record" close_state)
    case $close_state in
      complete|blocked|interrupted) ;;
      '') invalid "$rel" "missing-key close_state" ;;
      *)  invalid "$rel" "close-state-unknown $close_state" ;;
    esac

    for field in started_at completed_at; do
      # An absent field and a JSON null both read as empty; the rule is about how a timestamp that
      # IS there is written, so skip both.
      ts=$(json_str "$record" "$field")
      if [ -n "$ts" ] && ! printf '%s\n' "$ts" | grep -qE "$UTC_TS_RE"; then
        invalid "$rel" "$field-not-utc $ts"
      fi
    done
  done
fi

# -------------------------------------------------------------------------------------- post-close
# Closing a run deletes the started-marker once the record and digest are written, and deletes the
# scratch dir with it. Either one still on disk means the close did not finish, and the next run
# would read the leftover marker as a previous run that died partway through.
if [ -n "$POST_CLOSE" ]; then
  if [ -e "$WS/runs/.started-$POST_CLOSE" ]; then
    invalid "runs/.started-$POST_CLOSE" leftover-marker
  fi
  if [ -e "$WS/runs/.scratch/$POST_CLOSE" ]; then
    invalid "runs/.scratch/$POST_CLOSE" leftover-scratch-dir
  fi

  # ------------------------------------------- the record's numbers against the log it came from
  # Every count in the record comes from run-counts.sh reading jobs.jsonl, so the same reader run
  # again has to give the same numbers. A record can be internally consistent and still be
  # uniformly wrong — 2 + 5 + 2 balances against 17 actual rows — so the record is compared against
  # the events rather than against itself.
  #
  # run-counts.sh selects events by run_id, so these numbers do not change as later runs append
  # to the same log. A record written in July still validates in December, and re-running
  # --post-close against an old run is a supported thing to do rather than a way to manufacture a
  # finding.
  record="$WS/runs/$POST_CLOSE.json"
  if [ -f "$record" ]; then
    rel="runs/$POST_CLOSE.json"

    # Every count field has to be there before it can be compared. A record written before these
    # fields existed is named field by field rather than reported once, so a caller sees the whole
    # set to add.
    for field in postings_surfaced postings_reviewed postings_unreviewed postings_detail_read \
                 filtered_out duplicates_of_another; do
      [ -n "$(json_num "$record" "$field")" ] || invalid "$rel" "missing-key $field"
    done

    # An object that is there but holds no member states no count, and a comparison that skips a
    # value it cannot read passes it. Measured on 2026-08-07 before these two blocks existed: a
    # record carrying `"matches": {}` and `"by_source": {}`, against a log holding one strong match,
    # one filtered-out row and two linkedin postings, drew no finding at all and exited 0. So each
    # band is required by name, and by_source is held to its sum below and to the log's source list
    # further down.
    hasbysrc=no
    matchnums=''
    bysrcnums=''
    if grep -q '"matches"[[:space:]]*:' "$record"; then
      matchnums=$(json_obj_nums "$record" matches)
      for b in strong moderate weak; do
        [ -n "$(objval "$b" "$matchnums")" ] || invalid "$rel" "missing-key matches.$b"
      done
    else
      invalid "$rel" "missing-key matches"
    fi
    if grep -q '"by_source"[[:space:]]*:' "$record"; then
      hasbysrc=yes
      bysrcnums=$(json_obj_nums "$record" by_source)
    else
      invalid "$rel" "missing-key by_source"
    fi

    surfaced=$(json_num "$record" postings_surfaced)
    reviewed=$(json_num "$record" postings_reviewed)
    unreviewed=$(json_num "$record" postings_unreviewed)
    filtered=$(json_num "$record" filtered_out)
    dups=$(json_num "$record" duplicates_of_another)
    s=$(objval strong "$matchnums")
    m=$(objval moderate "$matchnums")
    w=$(objval weak "$matchnums")

    # The three rules the record can be held to on its own, so they hold for a record whose log has
    # since been deleted as well as for one written this minute. A record can satisfy all three and
    # still be uniformly wrong — 2 + 5 + 2 balances against 17 actual rows — which is what the
    # comparison against the log below is for.
    #
    # The three [ -n ] tests on the bands are a decision, not a precaution, so do not replace them
    # with `[ -z "$s" ] && s=0`. A record whose matches block states no band gets one missing-key
    # line naming each band, above, and that is the whole report about it. Reading the absent bands
    # as zero here would add arithmetic over numbers the record never stated — 0 + 0 + 0 + 1 against
    # 2 reviewed — which says the same thing again and does not say which band to add. The same
    # holds for duplicates_of_another, which is in the sum because a posting that is the same
    # opening as another is counted in postings_reviewed and in no band: run-counts.sh counts it
    # there and the record carries the number.
    if [ -n "$reviewed" ] && [ -n "$filtered" ] && [ -n "$dups" ] \
       && [ -n "$s" ] && [ -n "$m" ] && [ -n "$w" ]; then
      [ $((s + m + w + filtered + dups)) -eq "$reviewed" ] || \
        invalid "$rel" \
          "bands-do-not-sum-to-reviewed $((s + m + w + filtered + dups)) vs $reviewed"
    fi
    if [ -n "$surfaced" ] && [ -n "$reviewed" ] && [ -n "$unreviewed" ]; then
      [ $((reviewed + unreviewed)) -eq "$surfaced" ] || \
        invalid "$rel" "reviewed-plus-unreviewed-is-not-surfaced $((reviewed + unreviewed)) vs $surfaced"
    fi
    # The by_source block adds up to the postings surfaced. This is what catches a source the record
    # leaves out and a source the run never had, both of which the comparison against the log misses:
    # it walks the log's sources, so a source the log does not name is never looked for, and one the
    # record does not carry only shows up as a missing key. The sum needs no log at all.
    #
    # One case is deliberately left passing: a source the run never had, stated as 0. It moves no
    # total, so this sum cannot see it, and the comparison below never looks for it. A source with no
    # postings against it says nothing false about the run, and refusing it would mean walking the
    # record's sources as well to report a name rather than a number. The other direction — a source
    # the log has and the record leaves out — is reported, by missing-key below.
    if [ "$hasbysrc" = yes ] && [ -n "$surfaced" ]; then
      bysum=$(printf '%s\n' "$bysrcnums" | awk -F= '{ t += $NF } END { printf "%d\n", t }')
      [ "$bysum" -eq "$surfaced" ] || \
        invalid "$rel" "by-source-does-not-sum-to-surfaced $bysum vs $surfaced"
    fi

    # An empty count set means the reader could not run — no jobs.jsonl, or no run-counts.sh where
    # this expects one — and comparing against nothing would report every field as wrong. So the
    # comparison is skipped and the findings above stand on their own.
    counts=$(sh "$(dirname "$0")/../../job-search-run/scripts/run-counts.sh" \
               "$WS/jobs.jsonl" "$POST_CLOSE" 2>/dev/null)
    if [ -n "$counts" ]; then
      logval() { printf '%s\n' "$counts" | grep "^$1=" | cut -d= -f2-; }
      for field in postings_surfaced postings_reviewed postings_unreviewed \
                   postings_detail_read filtered_out duplicates_of_another; do
        want=$(logval "$field"); got=$(json_num "$record" "$field")
        [ -z "$want" ] || [ -z "$got" ] || [ "$want" = "$got" ] || \
          invalid "$rel" "counts-disagree-with-log $field $got vs $want"
      done
      for b in strong moderate weak; do
        want=$(logval "match_$b"); got=$(objval "$b" "$matchnums")
        [ -z "$want" ] || [ -z "$got" ] || [ "$want" = "$got" ] || \
          invalid "$rel" "counts-disagree-with-log matches.$b $got vs $want"
      done
      # The log names which sources the run had, so each one is looked for in the record by name.
      # A source the log names and the record leaves out is a missing key rather than a silent skip.
      #
      # `while read` rather than `for src in $(...)`: the unquoted substitution split each source
      # name on whitespace and then expanded it as a pathname. Measured on 2026-08-07 with the `for`
      # form, on a run whose only source was `*`: the loop walked the files in the working directory
      # instead, and a record stating `by_source { "AAAA": 99 }` passed. `invalid` appends to a file,
      # so the findings this loop reports survive the subshell the pipeline puts it in.
      if [ "$hasbysrc" = yes ]; then
        printf '%s\n' "$counts" | grep '^by_source_' | while IFS= read -r kv; do
          src=${kv#by_source_}
          want=${src##*=}
          src=${src%%=*}
          got=$(objval "$src" "$bysrcnums")
          if [ -z "$got" ]; then
            invalid "$rel" "missing-key by_source.$src"
          elif [ "$want" != "$got" ]; then
            invalid "$rel" "counts-disagree-with-log by_source.$src $got vs $want"
          fi
        done
      fi

      # One opening reached by two queries is returned twice and surfaced once, so this counts the
      # new rows the search calls brought in rather than the rows they returned. The two disagree
      # when postings went missing between the search and the log, which no comparison above reports:
      # the record and the log agree on how many postings the log holds, and both are short.
      rowsnew=$(logval rows_new_total)
      [ -z "$surfaced" ] || [ -z "$rowsnew" ] || [ "$surfaced" = "$rowsnew" ] || \
        invalid "$rel" "surfaced-does-not-match-rows-new $surfaced vs $rowsnew"
    fi

    # --------------------------------------------------------------------- the timestamp gates
    # completed_at is a clock read taken before the record is written, so it can be neither earlier
    # than started_at nor later than the record's own mtime. Measured on 2026-08-05, the run that
    # started this work wrote a record stating 03:15:00Z into a file whose mtime is 03:06:50Z:
    # nine minutes that no clock read produced.
    #
    # Both timestamps are UTC with a trailing Z and the loop above reports any that is not, so the
    # first comparison is a plain string compare. The second stamps a reference file with
    # completed_at and compares it against the record's own mtime. `touch -t` reads local time, so
    # TZ=UTC — without it the gate is wrong by the runner's offset. A completed_at carrying a
    # fractional second does not fit `touch -t`, which takes whole seconds, so touch fails, the
    # `&&` stops, and this gate passes rather than reporting something it did not measure.
    # Two gates, and only the first one needs started_at. They were one `if` requiring both, and a
    # record with no started_at turned the mtime gate off with it: measured on 2026-08-07, a record
    # stating completed_at 2099-01-01T00:00:00Z and carrying no started_at drew no finding, and the
    # same record with a started_at added reported completed-at-after-the-file-that-states-it. A
    # clock five hours ahead is what the mtime gate exists to catch, and leaving one field out of
    # the record must not switch it off.
    sa=$(json_str "$record" started_at)
    ca=$(json_str "$record" completed_at)
    if [ -n "$ca" ]; then
      if [ -n "$sa" ]; then
        [ "$ca" \> "$sa" ] || [ "$ca" = "$sa" ] || \
          invalid "$rel" "completed-at-before-started-at $ca"
      fi
      stamp=$(printf '%s\n' "$ca" | sed 's/[-:]//g; s/T\(..\)\(..\)\(..\)Z/\1\2.\3/')
      if TZ=UTC touch -t "$stamp" "$tsref" 2>/dev/null && [ "$tsref" -nt "$record" ]; then
        invalid "$rel" "completed-at-after-the-file-that-states-it $ca"
      fi
    fi
  fi
fi

if [ -s "$findings" ]; then
  sort "$findings"
  exit 1
fi
exit 0
