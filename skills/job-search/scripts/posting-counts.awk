# posting-counts.awk — see posting-counts.sh.
#
# A posting is keyed by its source and its source_id joined with SUBSEP, the 0x1c byte, the way
# run-counts.awk:14-16 keys one. That byte cannot reach a value: json-scan.awk refuses a raw
# control character inside a string, and jval leaves the escape that spells it as the six
# characters it is written with. Joining with a printable byte instead would give two postings one
# key: with a pipe, source `a` with source_id `b|c` and source `a|b` with source_id `c` both come
# out as `a|b|c`, and the two would be counted as one.
#
# An `evaluated` event is the only one that says what a run decided about a posting, so a posting's
# current state is its last `evaluated` line. Dropping the other event types here saves three jval
# calls on each one; it is not what keeps them out of the counts, since none of them carries
# `relevant` for the END block to read.
#
# Nothing here depends on the order the END block visits postings in: all three printed numbers are
# sums and the three printf statements are in a fixed order, so `for (k in seen)` prints the same
# output under every awk.
#
# same_role_as is read for whether it is there, not for what it names. The row it names is the row
# that was read, and that row is counted on its own line; looking it up would change no count.

{
  if (jval($0, "event") != "evaluated") next
  k = jval($0, "source") SUBSEP jval($0, "source_id")
  seen[k] = 1

  # In any log the product writes, these three assignments never overwrite anything: a posting has
  # at most one evaluated line, because event-log-append.sh and record-judgment.sh both refuse a
  # second evaluated event for a (source, source_id) that already has one. Assigning rather than
  # testing first keeps this loop the same shape as run-counts.awk's and costs nothing; a
  # hand-edited log with two judgments for one posting would take the later line.
  rel[k]   = jval($0, "relevant")
  human[k] = jval($0, "needs_human_check")
  if (jval($0, "same_role_as") != "") alias[k] = 1
}

END {
  for (k in seen) {
    if (k in alias) continue    # the same opening, counted under the row that was read
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
}
