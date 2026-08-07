#!/bin/sh
# event-log-append.sh — validate a jobs.jsonl event line, then append it idempotently.
#
# Appends one jobs.jsonl posting event, in one of the posting-event shapes this skill's
# templates/jobs-event.example.json shows.
#
# This is the append path for an `evaluated` event written by hand. No skill's prose sends a
# judgment here any more: SKILL.md's "Read and judge" section names record-judgment.sh, which builds
# the event itself, so this script is the standalone path a host takes when it is writing an event
# without that script. The events a run's own scripts write never come through here, because each of
# those scripts builds its event and appends it: record-api-response.sh writes `call`, `surfaced`
# and `detail`, queue-detail-read.sh writes `queued`, and record-judgment.sh writes the run's
# `evaluated` events. A `call` event is about a request rather than a posting and carries no
# "source_id" at all, so this script refuses one — the template's `call` line is there to be read,
# not to be piped in here. What this script checks is
# therefore what a hand-written posting event must satisfy: one event per line; a non-empty
# "source_id", with the literal key appearing exactly once; for an `evaluated` event a non-empty
# "source", with that key appearing at most once, because the per-source grep depends on it; and
# "same_role_as", when present, a flat string rather than a nested object.
#
# Validate before appending; append is the sanctioned jobs.jsonl `>>` exception. Idempotent: an
# `evaluated` event for a (source, source_id) that already carries one is a no-op — "never write a
# duplicate evaluated event for a known (source, source_id) pair". This is the scripted form of the
# model-run prose contract; that prose remains the no-runtime fallback.
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

  # Idempotency: skip if this (source, source_id) already has an `evaluated` event. The filter on
  # event type matters — a posting is recorded as `surfaced` before it is judged, and without it
  # that first event would make the judgment look like a duplicate and drop it.
  #
  # The event-type match tolerates whitespace around the colon, like every other check in this
  # script, because this is the path a host writing an event by hand comes through and a hand-written
  # event may carry `"event": "evaluated"`. A plain `grep -F '"event":"evaluated"'` would not find
  # that line, and the second copy of it would be appended.
  if [ -f "$jobs" ] && grep -E '"event"[[:space:]]*:[[:space:]]*"evaluated"' "$jobs" 2>/dev/null \
       | grep -E '"source"[[:space:]]*:[[:space:]]*"'"$src"'"' \
       | grep -o '"source_id"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4 \
       | grep -qxF "$sid"; then
    exit 0
  fi
fi

# Append (create the workspace dir if needed; the >> here is the sanctioned append exception).
dir=$(dirname "$jobs")
[ -d "$dir" ] || mkdir -p "$dir"
printf '%s\n' "$ev" >> "$jobs"
