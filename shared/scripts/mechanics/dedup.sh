#!/bin/sh
# dedup.sh — emit the NEW candidate source_ids for a source.
#
# Given the workspace event log <jobs.jsonl> and a <source>, read candidate source_ids on stdin
# (one per line) and print only those NOT already recorded as an event for that source.
#
# Reproduces the pinned "Known ids" dedup contract in shared/references/conventions.md §jobs.jsonl:
# grep the `"source":"S"` events, extract `"source_id"`, take the value, unique-sort — that is the
# known set; the NEW set is the candidates minus it. Missing jobs file = empty known set (every
# candidate is new). Blank candidate lines (a null source_id can't be deduped) are skipped. This is
# the scripted form of the model-run prose contract; that prose remains the no-runtime fallback.
#
# Usage: dedup.sh <jobs.jsonl> <source>          # candidate source_ids on stdin, NEW ones on stdout
set -u
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
