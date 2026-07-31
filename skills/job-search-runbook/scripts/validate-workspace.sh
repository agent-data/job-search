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
#   --post-close RUN_ID   also require that run RUN_ID left no started-marker and no scratch dir.
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
RUN_ID_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z$'
# Run-record timestamps are UTC with a trailing Z. An offset such as +00:00 names the same instant
# but fails: with one written form, comparing two timestamps is a plain string compare.
UTC_TS_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$'

if [ -n "$POST_CLOSE" ] && ! printf '%s\n' "$POST_CLOSE" | grep -qE "$RUN_ID_RE"; then
  printf 'validate-workspace.sh: --post-close needs a run id like 2026-07-16T14-30-00Z, got: %s\n' \
    "$POST_CLOSE" >&2
  exit 2
fi

findings=$(mktemp) || exit 2
trap 'rm -f "$findings"' EXIT INT HUP TERM

# Report one broken rule: the file it is about, the rule, and the observed value when short.
invalid() {
  printf 'INVALID %s %s\n' "$1" "$2" >> "$findings"
}

# Read one JSON string value by key. Same idiom as the other mechanics scripts: no jq, no python.
json_str() {
  grep -o "\"$2\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$1" 2>/dev/null | head -1 | cut -d'"' -f4
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
    printf '%s\n' "$id" | grep -qE "$RUN_ID_RE" || continue
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
fi

if [ -s "$findings" ]; then
  sort "$findings"
  exit 1
fi
exit 0
