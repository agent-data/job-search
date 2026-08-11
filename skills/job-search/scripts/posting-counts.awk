# posting-counts.awk — see posting-counts.sh.
#
# A posting is keyed by its source and its source_id joined with SUBSEP, the 0x1c byte, the way
# run-counts.awk keys one. That byte cannot reach a value: json-scan.awk refuses a raw
# control character inside a string, and jval leaves the escape that spells it as the six
# characters it is written with. Joining with a printable byte instead would give two postings one
# key: with a pipe, source `a` with source_id `b|c` and source `a|b` with source_id `c` both come
# out as `a|b|c`, and the two would be counted as one.
#
# An `evaluated` event is the only one that says what a run decided about a posting, so a posting's
# current state is its last `evaluated` line. The event-type test below is LOAD-BEARING, not an
# optimisation: the END block sorts every posting it reaches into `relevant` or `filtered`, so a
# `surfaced`, `queued`, `call` or `detail` line that got through would be counted as filtered out.
# Measured on 2026-08-07 against a log of one surfaced, one queued and one call line: this program
# prints filtered=0, and the same program with that one test deleted prints filtered=3, under both
# BSD awk and mawk. Do not drop it to save the four jval calls it skips.
#
# Nothing here depends on the order the END block visits postings in: every number it prints is a
# sum over that loop or NR, and the printf statements are in a fixed order, so `for (k in seen)`
# prints the same output under every awk, on stdout and on stderr alike.
#
# same_role_as is read for whether it is there, not for what it names. The row it names is the row
# that was read, and that row is counted on its own line; looking it up would change no count.

{
  if (jval($0, "event") != "evaluated") next
  k = jval($0, "source") SUBSEP jval($0, "source_id")
  seen[k] = 1

  # In any log the product writes, these three assignments never overwrite anything, because both
  # scripts that append an evaluated event refuse a second one for a (source, source_id) that
  # already carries one, whichever run recorded that first judgment. event-log-append.sh skips its
  # append and exits 0. record-judgment.sh exits 0 when the judgment offered is the line already in
  # the log, and 1 when it is anything else — an earlier run's judgment included, since that line
  # names a different run — and writes nothing either way. Two tests hold the pair, and this runs
  # both of them and gives `2 passed`:
  #   python3 -m pytest -q \
  #     tests/test_mechanics_scripts.py::test_event_log_append_is_idempotent_on_source_and_source_id \
  #     tests/test_mechanics_scripts.py::test_a_judgment_from_an_earlier_run_blocks_a_contradictory_one_in_this_run
  #
  # Assigning rather than testing first keeps this loop the same shape as run-counts.awk's and costs
  # nothing; a hand-edited log with two judgments for one posting would take the later line.
  #
  # same_role_as is assigned like the other two rather than being set once and left. Written
  # `if (jval($0, "same_role_as") != "") alias[k] = 1`, a posting named as a duplicate on its first
  # judgment stayed one after a second judgment that named nobody, while run-counts.awk read the
  # later line and put it back in a band. Measured on a log where the second posting first names the
  # first and is then re-judged with no same_role_as: run-counts.sh printed match_strong=1
  # match_weak=1 duplicates_of_another=0, run-matches.sh printed two rows, and this script printed
  # relevant=1 — two openings on the digest and one on the home card.
  rel[k]   = jval($0, "relevant")
  human[k] = jval($0, "needs_human_check")
  alias[k] = jval($0, "same_role_as")
}

END {
  for (k in seen) {
    # Counted before the test below, so this is every posting carrying a judgment, including the
    # ones the three keys leave out. Only the stderr line at the end of this block reads it.
    judged++
    if (alias[k] != "") {
      aliased++                     # so the stderr line accounts for this posting too
      continue                      # the same opening, counted under the row that was read
    }
    if (rel[k] == "true") {
      relevant++
      if (human[k] == "true") confirm++
    } else {
      filtered++
    }
  }
  printf "relevant=%d\n",   relevant+0
  printf "to_confirm=%d\n", confirm+0
  printf "filtered=%d\n",   filtered+0
  # All three keys print as 0 for a log with no judgments, for an empty log, and for a file of lines
  # that are not JSON at all: `posting-counts.sh <log> | wc -c` answers 35 for each of the three,
  # measured 2026-08-11 on an empty file, on 200 lines of `not json at all <n>`, and on a log of one
  # surfaced, one queued and one call line. This line is what separates them, and it goes to stderr,
  # which is what keeps those 35 bytes the same as they were before it existed. job-search/SKILL.md
  # tells the agent to run this script rather than read the log itself, so the three keys were the
  # whole of what it had. `grep -n 'reading that log yourself' skills/job-search/SKILL.md` is where
  # that instruction is written.
  #
  # The third count is what makes the numbers add up. `judged` counts a posting whose judgment names
  # another one in same_role_as, because it does carry a judgment, and the alias test above leaves
  # that posting out of all three keys. With only the first two numbers, a log of one such posting
  # and the one it names prints `2 postings carry a judgment` over a stdout reading `relevant=1
  # to_confirm=0 filtered=0`, and 1 plus 0 is not 2. With the third, relevant plus filtered plus it
  # equals judged on every log. to_confirm is not a term in that sum, because it counts within
  # relevant — `grep -n 'to_confirm counts over' posting-counts.sh` is where that is written down.
  #
  # Each count names what it counts, and the noun and its verb are singular at one: a log of one
  # judgment reads `1 line read, 1 posting carries a judgment`. The third count is a clause of its
  # own with its own verb — `1 of those is the same opening as another posting` — and what that
  # posting is left out of follows it after a comma, rather than hanging off the same `of those`.
  #
  # `| "cat 1>&2"` is how an awk program in this pack writes to stderr — json-scan.awk:51-52 is the
  # precedent — and the close() is what flushes it.
  printf "posting-counts.sh: %d %s read, %d %s a judgment, %d of those %s the same opening as" \
         " another posting, counted under neither relevant nor filtered\n", \
    NR, (NR == 1 ? "line" : "lines"), \
    judged+0, (judged+0 == 1 ? "posting carries" : "postings carry"), \
    aliased+0, (aliased+0 == 1 ? "is" : "are") | "cat 1>&2"
  close("cat 1>&2")
}
