#!/bin/sh
# event-log-append.sh — validate a jobs.jsonl event line, then append it idempotently.
#
# Appends one jobs.jsonl posting event, in one of the posting-event shapes this skill's
# templates/jobs-event.example.json shows.
#
# This is the append path for an `evaluated` event written by hand. No skill's prose sends a
# judgment here any more: SKILL.md's "Read and judge" section names record-judgment.sh, which builds
# the event itself, so this script is the standalone path a harness takes when it is writing an event
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
# Nothing goes to stdout. One line goes to stderr on each of the two paths that exit 0: an append
# says which event type it wrote and which source and source_id it wrote it for, and a skip says the
# posting already carries that event and nothing was written. Without those two lines an event that
# landed and a duplicate that was skipped look the same to the caller. Each refusal writes its own
# line and exits 1.
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
src=$(printf '%s\n' "$ev" | grep -o '"source"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)

if [ "$evtype" = evaluated ]; then
  # Every evaluated event carries a non-empty "source".
  [ -n "$src" ] || { echo 'event-log-append: evaluated event needs a non-empty "source"' >&2; exit 1; }

  # Idempotency: skip if this (source, source_id) already has an `evaluated` event. The filter on
  # event type matters — a posting is recorded as `surfaced` before it is judged, and without it
  # that first event would make the judgment look like a duplicate and drop it.
  #
  # The source name comes off the event this script was handed, so grep has to match it as text
  # rather than read it as a search pattern. Read as a pattern, `a.c` matched a line whose source is
  # `axc`: the check took that line's source_id, decided this posting was already judged, and
  # dropped the judgment for `a.c` at exit 0 with nothing on stderr. And `[x` opened a bracket
  # expression grep never closed, so grep printed `brackets ([ ]) not balanced`, exited 2 and matched
  # nothing, and a second judgment for a posting that already had one was appended. The two cases are
  # held by test_a_source_whose_name_holds_a_regex_metacharacter_is_matched_literally and
  # test_a_source_whose_name_holds_an_unbalanced_bracket_does_not_break_the_duplicate_check in
  # tests/test_mechanics_scripts.py.
  #
  # The source_id is a value too, and the last grep takes it as an argument of its own, where a
  # value starting with `-` is read as an option instead: `printf 'x\n' | grep -qxF "-v"` exits 2 and
  # prints grep's usage text, so the check found no earlier judgment and a second `evaluated` event
  # went into the log. `--` ends grep's options, and the same command with it exits 1.
  # test_a_source_id_that_looks_like_an_option_is_read_as_a_value holds it.
  #
  # So the matches below are `grep -F`, which takes a fixed string and reads no pattern at all. That
  # leaves them with no whitespace tolerance of their own, and the `sed` puts it back ahead of them
  # instead of inside them: it closes up the spaces and tabs on either side of a colon that has a
  # quote on both sides, so a hand-written `"event": "evaluated"` or `"source" : "ashby"` reaches the
  # matches in the compact form they are written in.
  #
  # That rule is about quotes and colons on the line, not about JSON, so it also rewrites a colon
  # inside a string value when an escaped quote sits to its left and the value's closing quote to its
  # right: `"reasoning":"he said \"source\" : "` comes out as `"reasoning":"he said \"source\":"`.
  # No match outcome changes, for two reasons. The `sed` rewrites only the copy going through the
  # pipe, so the log on disk keeps the line as it was written. And the three matches below see
  # exactly the text the `grep -E` they replaced saw: the only way to reach `"event":"evaluated"`
  # through this rewrite is from `"event"` then spaces, a colon, spaces, then `"evaluated"`, which is
  # what that pattern matched. What the `sed` leaves alone is a colon without a quote on both sides,
  # as in `"posted_at": null` — and no match below reads a value that is not a quoted string.
  # test_a_value_ending_in_an_escaped_quote_before_a_colon_is_still_deduped holds the rewritten case.
  if [ -f "$jobs" ] && sed 's/"[[:space:]]*:[[:space:]]*"/":"/g' "$jobs" 2>/dev/null \
       | grep -F '"event":"evaluated"' \
       | grep -F '"source":"'"$src"'"' \
       | grep -o '"source_id":"[^"]*"' | cut -d'"' -f4 \
       | grep -qxF -- "$sid"; then
    printf 'event-log-append: %s:%s already has this event — nothing written\n' "$src" "$sid" >&2; exit 0
  fi
fi

# Append (create the workspace dir if needed; the >> here is the sanctioned append exception).
dir=$(dirname "$jobs")
[ -d "$dir" ] || mkdir -p "$dir"

# End the last line first. A log can end without a newline after its last event — a hand edit, a
# truncated copy, an editor that does not end its files with one — and this event would then be
# written onto that last line. Every field reader takes a key's first occurrence — the header of
# event-field.awk states it, in the sentence ending "the first occurrence wins" — so the joined line
# is read as the earlier event and this one is lost: measured 2026-08-08 on a posting whose judgment
# landed on its surfaced event, `run-counts.sh` reported
# `postings_reviewed=0 postings_unreviewed=1`, `run-matches.sh` printed no rows, and
# `posting-counts.sh` printed `relevant=0 to_confirm=0 filtered=0`, all at exit 0.
#
# `tail -c1 | wc -l` prints 1 when the last byte is a newline and 0 when it is not. `[ -s "$jobs" ]`
# in front of it leaves an empty log alone: without that test this writes a newline into a file that
# holds no line at all, putting a blank line above the first event. Measured 2026-08-08 under sh,
# dash and bash alike: a file with no newline on its last line grew by exactly one byte, one already
# ending in a newline was left at its own size, and so was an empty one. The three other scripts that
# append to jobs.jsonl — queue-detail-read.sh, record-api-response.sh and record-judgment.sh, which
# is the rest of what `grep -rl '>> "$jobs"' skills/` lists — do the same before their own appends
# and point back here for the reason.
if [ -s "$jobs" ] && [ "$(tail -c1 "$jobs" | wc -l)" -eq 0 ]; then printf '\n' >> "$jobs"; fi

printf '%s\n' "$ev" >> "$jobs"
status=$?

# The append is announced, and the skip above announces the write it did not make. Without those two
# lines an event that was appended and a duplicate that was skipped look the same from outside —
# nothing on stdout, nothing on stderr, exit 0 — and the caller cannot tell which of the two
# happened. The append used to be the last command in the script, so the status the caller saw was
# the append's own; the status is taken before the printf and given back after it, so an append that
# failed still reaches the caller as a failure. The source is read at the top of the script next to
# the event type: the assignment it replaced was inside the evaluated branch, and the `set -u` above
# makes reading an unset variable an error on every other path.
if [ "$status" -eq 0 ]; then
  printf 'event-log-append: appended %s for %s:%s\n' "$evtype" "$src" "$sid" >&2
fi
exit "$status"
