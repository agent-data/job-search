# pipeline-counts.awk — see pipeline-counts.sh.
#
# A posting is keyed by its source and its source_id joined with SUBSEP, the 0x1c byte, the way
# run-counts.awk:14-16 keys one. That byte cannot reach a value: json-scan.awk refuses a raw
# control character inside a string, and jval leaves the escape that spells it as the six
# characters it is written with. Joining with a printable byte instead would give two postings one
# key: with a pipe, source `a` with source_id `b|c` and source `a|b` with source_id `c` both come
# out as `a|b|c`, and the two would be counted as one.
#
# `order` fixes nothing that is printed. The six lines are six printf statements in a fixed order
# and every number on them is a sum, so it is only how the END block reaches each posting exactly
# once. Measured on 2026-08-07 against a live log of 159 lines: rewritten as `for (k in seen)`,
# this prints byte-identical output under BSD awk and under mawk.
#
# same_role_as is read for whether it is there, not for what it names. The row it names is the row
# that was read, and that row is counted on its own line; looking it up would change no count.

{
  ev = jval($0, "event")
  # Only these two events say anything about a posting's state, and dropping the rest here saves
  # five jval calls on each one. It is not what keeps a surfaced row out of the counts:
  # measured on 2026-08-07 against a live log of 159 lines — 75 evaluated, 4
  # status_changed, 75 surfaced, 4 call, 1 detail — jval read nothing at all for status, relevant or
  # needs_human_check out of any of the 80 lines this drops, so the END block leaves them out of
  # every count on its own. An event type added later that carried one of those fields would need
  # this line.
  if (ev != "evaluated" && ev != "status_changed") next
  k = jval($0, "source") SUBSEP jval($0, "source_id")
  if (!(k in seen)) { seen[k] = 1; n++; order[n] = k }

  # The last judgment for a posting decides whether it is relevant; any reaction at all puts it in
  # the pipeline, so this one is set and never cleared.
  if (ev == "evaluated")      rel[k] = jval($0, "relevant")
  if (ev == "status_changed") reacted[k] = 1

  # A status_changed event carries a status and no needs_human_check, so each field takes the last
  # line that carried it rather than the last line for the posting.
  s = jval($0, "status");            if (s != "") status[k] = s
  h = jval($0, "needs_human_check"); if (h != "") human[k] = h
  if (jval($0, "same_role_as") != "") alias[k] = 1
}

END {
  for (i = 1; i <= n; i++) {
    k = order[i]
    if (k in alias) continue                      # the same opening, counted under the row that was read
    if (rel[k] != "true" && !(k in reacted)) continue
    s = status[k]
    if (s == "") s = "new"
    count[s]++
    if (human[k] == "true") confirm++
  }
  printf "new=%d\n",         count["new"]+0
  printf "interested=%d\n",  count["interested"]+0
  printf "applied=%d\n",     count["applied"]+0
  printf "rejected=%d\n",    count["rejected"]+0
  printf "archived=%d\n",    count["archived"]+0
  printf "to_confirm=%d\n",  confirm+0
}
