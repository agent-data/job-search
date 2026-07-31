#!/bin/sh
# dedup.sh — emit the NEW candidate source_ids for a source.
#
# Given the workspace event log <jobs.jsonl> and a <source>, read candidate source_ids on stdin
# (one per line) and print only those NOT already recorded as an event for that source.
#
# The "known ids" dedup step the run skill calls:
# grep the `"source":"S"` events, extract `"source_id"`, take the value, unique-sort — that is the
# known set; the NEW set is the candidates minus it. Missing jobs file = empty known set (every
# candidate is new). Blank candidate lines (a null source_id can't be deduped) are skipped. This is
# the scripted form of the model-run prose contract; that prose remains the no-runtime fallback.
#
# The --near mode answers a different question about one run's own rows: which of them are the
# same opening seen twice? A company that posts one opening in several locations returns several
# rows, with different source_ids and titles that differ only by a location parenthetical, and
# reading each of them bills a detail call for a posting already read. Candidate rows arrive as
# `source_id<TAB>company<TAB>title`, and the openings to judge come back on stdout: the first row
# of each group sharing a company and a title that match once lowercased, stripped of their
# parentheses, and re-spaced. A row missing its company or title has nothing to compare and is
# kept. This mode reads no file and looks only within the rows it is given.
#
# Usage: dedup.sh <jobs.jsonl> <source>          # candidate source_ids on stdin, NEW ones on stdout
#        dedup.sh --near                          # id<TAB>company<TAB>title rows on stdin,
#                                                 # the source_ids to judge on stdout
set -u

usage() {
  printf 'usage: dedup.sh <jobs.jsonl> <source>   (candidate source_ids on stdin)\n' >&2
  printf '       dedup.sh --near                  (id<TAB>company<TAB>title rows on stdin)\n' >&2
}

if [ "${1:-}" = --near ]; then
  [ $# -eq 1 ] || { usage; exit 2; }
  # First row of each (company, title) group wins; a repeated source_id prints once.
  exec awk -F'\t' '
    function norm(s) {
      s = tolower(s)
      gsub(/\([^)]*\)/, " ", s)     # a location parenthetical is not part of the opening
      gsub(/[ \t]+/, " ", s)
      sub(/^ /, "", s)
      sub(/ $/, "", s)
      return s
    }
    { id = $1; company = norm($2); title = norm($3) }
    id == ""                  { next }
    seen_id[id]++             { next }
    company == "" || title == "" { print id; next }
    seen_role[company, title]++  { next }
    { print id }'
fi

jobs=${1:?usage: dedup.sh <jobs.jsonl> <source>   (candidate source_ids on stdin)}
src=${2:?usage: dedup.sh <jobs.jsonl> <source>   (candidate source_ids on stdin)}

known=$(mktemp) || exit 2
trap 'rm -f "$known"' EXIT INT HUP TERM

# Known-ids set for this source — the pinned pipeline, verbatim.
grep -E '"source"[[:space:]]*:[[:space:]]*"'"$src"'"' "$jobs" 2>/dev/null \
  | grep -o '"source_id"[[:space:]]*:[[:space:]]*"[^"]*"' \
  | cut -d'"' -f4 \
  | sort -u > "$known"

# Candidates on stdin: skip blanks, keep first occurrence, emit those not already known.
# Preload the known set in BEGIN via getline (robust when the known set is empty — the two-file
# NR==FNR idiom would misfire on an empty first file), then read candidates from stdin.
awk -v kf="$known" '
     BEGIN { while ((getline line < kf) > 0) k[line]=1; close(kf) }
     { id=$0 }
     id == ""       { next }
     k[id]          { next }
     seen[id]++     { next }
     { print id }'
