#!/bin/sh
# event-log-append.sh — validate a jobs.jsonl event line, then append it idempotently.
#
# Mirrors the pinned event-line contract + operations in shared/references/conventions.md §jobs.jsonl:
#   - one event per line (single-line JSON, never pretty-printed);
#   - every event carries a non-empty "source_id"; the literal key "source_id" appears exactly once;
#   - every `evaluated` event carries a non-empty "source"; the literal key "source" appears at most
#     once (the per-source grep depends on it, exactly as the source_id-once rule protects extraction);
#   - "same_role_as", when present, is a FLAT string — never a nested object.
# Validate before appending; append is the sanctioned jobs.jsonl `>>` exception. Idempotent: an
# `evaluated` event for a (source, source_id) already recorded is a no-op — "never write a duplicate
# evaluated event for a known (source, source_id) pair". This is the scripted form of the model-run
# prose contract; that prose remains the no-runtime fallback.
#
# Usage: event-log-append.sh <jobs.jsonl>        # the single-line event JSON on stdin
set -u
jobs=${1:?usage: event-log-append.sh <jobs.jsonl>   (event JSON on stdin)}

ev=$(cat)   # command substitution strips a single trailing newline

# One event per line — reject an embedded newline (pretty-printed or multi-event input).
case $ev in
  *'
'*) echo 'event-log-append: event must be a single line' >&2; exit 1 ;;
esac
[ -n "$ev" ] || { echo 'event-log-append: empty event' >&2; exit 1; }

# "source_id" key appears exactly once, with a non-empty value.
sid_keys=$(printf '%s\n' "$ev" | grep -o '"source_id"[[:space:]]*:' | wc -l | tr -d ' ')
[ "$sid_keys" = 1 ] || { echo 'event-log-append: "source_id" must appear exactly once' >&2; exit 1; }
sid=$(printf '%s\n' "$ev" | grep -o '"source_id"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
[ -n "$sid" ] || { echo 'event-log-append: "source_id" must be non-empty' >&2; exit 1; }

# "source" key (distinct from "source_id"/"source_url") appears at most once.
src_keys=$(printf '%s\n' "$ev" | grep -o '"source"[[:space:]]*:' | wc -l | tr -d ' ')
[ "$src_keys" -le 1 ] || { echo 'event-log-append: "source" must appear at most once' >&2; exit 1; }

# "same_role_as", when present, must be a flat string — never a nested object.
case $ev in
  *'"same_role_as"'*)
    printf '%s\n' "$ev" | grep -Eq '"same_role_as"[[:space:]]*:[[:space:]]*"' \
      || { echo 'event-log-append: "same_role_as" must be a flat string' >&2; exit 1; } ;;
esac

evtype=$(printf '%s\n' "$ev" | grep -o '"event"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)

if [ "$evtype" = evaluated ]; then
  # Every evaluated event carries a non-empty "source".
  src=$(printf '%s\n' "$ev" | grep -o '"source"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
  [ -n "$src" ] || { echo 'event-log-append: evaluated event needs a non-empty "source"' >&2; exit 1; }

  # Idempotency: skip if this (source, source_id) is already recorded (the composite dedup key).
  if [ -f "$jobs" ] && grep -E '"source"[[:space:]]*:[[:space:]]*"'"$src"'"' "$jobs" 2>/dev/null \
       | grep -o '"source_id"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4 \
       | grep -qxF "$sid"; then
    exit 0
  fi
fi

# Append (create the workspace dir if needed; the >> here is the sanctioned append exception).
dir=$(dirname "$jobs")
[ -d "$dir" ] || mkdir -p "$dir"
printf '%s\n' "$ev" >> "$jobs"
