#!/bin/sh
# dedup.sh — drop the candidate postings a run does not need to read.
#
# Usage: dedup.sh --near                          # id<TAB>company<TAB>title rows on stdin, the ids
#                                                 # to judge on stdout; on stderr, one line per
#                                                 # collapsed row naming the row it was matched to,
#                                                 # then a line of counts
#        dedup.sh <jobs.jsonl> <source>          # candidate source_ids on stdin, NEW ones on stdout
#
# The --near mode answers a different question about one run's own rows: which of them are the
# same opening seen twice? A company that posts one opening in several locations returns several
# rows, with different source_ids and titles that differ only by a location parenthetical, and
# reading each of them bills a detail call for a posting already read. Candidate rows arrive as
# `<source>:<source_id><TAB>company<TAB>title`, and the openings to judge come back on stdout: the
# first row of each group sharing a company and a title that match once lowercased, stripped of
# their parentheses, and re-spaced. Column 1 is passed through as written and never parsed —
# SKILL.md sends the `<source>:<source_id>` form so the pairing this mode writes to stderr is what
# `record-judgment.sh --same-role-as` takes. A row missing its company or title has nothing to
# compare and is kept. This mode reads no file and looks only within the rows it is given.
#
# Given the workspace event log <jobs.jsonl> and a <source>, read candidate source_ids on stdin
# (one per line) and print only those NOT already judged for that source.
#
# The "known ids" dedup step:
# grep the `evaluated` events for source S, extract `"source_id"`, take the value, unique-sort —
# that is the known set; the NEW set is the candidates minus it. A posting a run surfaced but never
# judged is not in the known set, so the next run offers it again. Missing jobs file = empty known
# set (every candidate is new). Blank candidate lines (a null source_id can't be deduped) are
# skipped. record-api-response.sh now makes this same judged-posting check as it appends, so the
# two-argument mode is redundant for a run that records its responses through that script, and is
# kept for a host that runs it standalone. The --near mode above is separate and keeps its caller.
# This is the scripted form of the model-run prose contract; that prose remains the no-runtime
# fallback.
set -u

usage() {
  printf 'usage: dedup.sh <jobs.jsonl> <source>   (candidate source_ids on stdin)\n' >&2
  printf '       dedup.sh --near                  (id<TAB>company<TAB>title rows on stdin)\n' >&2
}

if [ "${1:-}" = --near ]; then
  [ $# -eq 1 ] || { usage; exit 2; }
  # First row of each (company, title) group wins; a repeated source_id prints once.
  #
  # stdout carries the ids to judge and nothing else. Two more things go to stderr. One line per
  # collapsed row names that row and the row it was matched to, because SKILL.md asks for
  # `--same-role-as <source>:<source_id>` on every posting this mode leaves out and the pairing is
  # worked out here to make the decision. A closing line gives the counts, so even a call that
  # collapsed nothing writes a sentence rather than 0 bytes. The 2026-08-10 run got 65 ids from 67
  # rows with an empty stderr, and wrote that this script "reads from jobs.jsonl directly, not via
  # my generated TSV" and "seems to have queried the log itself" (16:27:26). The call at 16:27:18
  # had already produced those 65 ids; three more bash calls, at 16:27:34, 16:27:42 and 16:27:49,
  # re-derived the rows, read this script's source, and ran the same call a second time.
  #
  # The counts add up to `rows read`. Every row lands in one of them: an opening to judge, the same
  # opening as one above, a row with no id, or a row carrying an id that was read already. The last
  # two are printed only when they are not zero, so an ordinary call still reports three counts, and
  # a caller that adds up the numbers it was given always gets `rows read` back and is never left
  # looking for a row the line did not mention.
  #
  # `first[company, title]` is assigned on the keep path below, so it holds the id of the row that
  # was kept for that pair — the one a later row is collapsed into. `rows` counts every line read,
  # blanks included, so `rows read` is the input size the caller handed over.
  exec awk -F'\t' '
    function norm(s) {
      s = tolower(s)
      gsub(/\([^)]*\)/, " ", s)     # a location parenthetical is not part of the opening
      gsub(/[ \t]+/, " ", s)
      sub(/^ /, "", s)
      sub(/ $/, "", s)
      return s
    }
    { rows++; id = $1; company = norm($2); title = norm($3) }
    id == ""                  { no_id++; next }
    seen_id[id]++             { repeat_id++; next }
    company == "" || title == "" { kept++; print id; next }
    seen_role[company, title]++  { same++
                                  printf "dedup.sh --near: %s is the same opening as %s\n", \
                                    id, first[company, title] | "cat 1>&2"
                                  next }
    { kept++; first[company, title] = id; print id }
    END { counts = sprintf("%d rows read, %d openings to judge, %d the same opening as one above", \
                           rows, kept, same+0)
          if (no_id)     counts = counts sprintf(", %d with no id", no_id)
          if (repeat_id) counts = counts sprintf(", %d the same id as one above", repeat_id)
          printf "dedup.sh --near: %s\n", counts | "cat 1>&2"
          close("cat 1>&2") }'
fi

jobs=${1:?usage: dedup.sh <jobs.jsonl> <source>   (candidate source_ids on stdin)}
src=${2:?usage: dedup.sh <jobs.jsonl> <source>   (candidate source_ids on stdin)}

known=$(mktemp) || exit 2
trap 'rm -f "$known"' EXIT INT HUP TERM

# Known-ids set for this source: the postings that already carry a judgment, whichever run recorded
# it — nothing in this file reads a run id. A posting a stopped run surfaced and never judged is NOT
# known: the next run has to offer it again.
#
# The source is the caller's second argument, so grep has to match it as text rather than read it as
# a search pattern. Read as a pattern, `a.c` matched a line whose source is `axc`, so 111 came back
# as already known for a source that has never judged it and the run never saw that posting; and
# `[x` opened a bracket expression grep never closed, so grep exited 2 and matched nothing, the
# known set came back empty, and every posting this source had judged was offered again. The two
# cases are held by test_a_source_whose_name_holds_a_regex_metacharacter_matches_only_that_source
# and test_a_source_whose_name_holds_an_unbalanced_bracket_still_has_a_known_set in
# tests/test_mechanics_scripts.py.
#
# So the matches below are `grep -F`, which takes a fixed string and reads no pattern at all, and
# the `sed` ahead of them carries the whitespace tolerance they no longer have: it closes up the
# spaces and tabs on either side of a colon that has a quote on both sides, so a hand-written
# `"event": "evaluated"` is still read as a judgment and a posting whose judgment it names is not
# offered to the next run as new.
#
# That rule is about quotes and colons on the line, not about JSON, so it also rewrites a colon
# inside a string value when an escaped quote sits to its left and the value's closing quote to its
# right: `"reasoning":"he said \"source\" : "` comes out as `"reasoning":"he said \"source\":"`. No
# match outcome changes, and event-log-append.sh's comment above its own append writes out why. The
# short version: the `sed` rewrites only the copy going through the pipe, and the only way to reach
# `"event":"evaluated"` through the rewrite is from `"event"` then spaces, a colon, spaces, then
# `"evaluated"` — which is what the `grep -E` this replaced matched. event-log-append.sh matches the
# same three fields the same way.
sed 's/"[[:space:]]*:[[:space:]]*"/":"/g' "$jobs" 2>/dev/null \
  | grep -F '"event":"evaluated"' \
  | grep -F '"source":"'"$src"'"' \
  | grep -o '"source_id":"[^"]*"' \
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
