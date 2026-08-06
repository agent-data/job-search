# dedup-surfaced.awk — drop the `surfaced` events for postings that are already accounted for.
#
# Usage: awk -f event-field.awk -f dedup-surfaced.awk -v jobs=<jobs.jsonl> -v run_id=<id> <new.jsonl>
#
# It needs jval() from event-field.awk, so it is chained behind that file with a second -f. POSIX
# awk forbids mixing -f with inline program text, which is why this is a file rather than a
# here-document inside record-api-response.sh.
#
# Reads jobs.jsonl once, builds the set of (source, source_id) pairs to skip, then prints the lines
# of <new.jsonl> whose pair is not in that set and not a repeat within <new.jsonl> itself.
#
# Two kinds of pair go into the set:
#   a `surfaced` event of THIS run — one opening reached by two of this run's queries is one
#     posting, so the second query does not surface it again;
#   an `evaluated` event of ANY run — a posting that already has a verdict is not offered again.
# A `surfaced` event of an earlier run that was never evaluated is deliberately absent from the set:
# an opening that still has no verdict needs one, so this run surfaces it.
#
# A `call` event carries no source_id, and its event name is neither of the two above, so it never
# goes into the set.

BEGIN {
  while ((getline line < jobs) > 0) {
    ev = jval(line, "event")
    k = jval(line, "source") "|" jval(line, "source_id")
    if (ev == "surfaced" && jval(line, "run_id") == run_id) have[k] = 1
    else if (ev == "evaluated") have[k] = 1
  }
  close(jobs)
}
{
  k = jval($0, "source") "|" jval($0, "source_id")
  if (k in have) next
  have[k] = 1
  print
}
