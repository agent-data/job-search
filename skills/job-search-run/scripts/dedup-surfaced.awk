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
#
# It writes one line to stderr counting the rows it dropped under each of the three rules that drop
# one. record-api-response.sh tells its caller how many rows it appended and how many the response
# held, and the difference between those two numbers was everything the caller got. The 2026-08-10
# run printed `1 rows appended, 10 rows in the response`, and three different things produce that
# same line: nine postings that already carry a verdict, nine an earlier search of the same run
# surfaced, and one posting the response repeated nine times.
#
# Each of the three counts says `row` or `rows`, because rows are what is counted and one response
# can hold several rows for the same posting. A response repeating a posting the log already judged
# counts both of its rows under `already judged` and neither under `repeated inside this response`,
# because the pair is already in the set when the first of them is read: measured 2026-08-11 on a
# response of 5 rows covering 3 postings that already carry a verdict, two of them sent twice, the
# line read
# `5 rows already judged, 0 rows already surfaced by this run, 0 rows repeated inside this response`.
# Counting rows is what keeps the three adding up to `rows in the response` minus `rows appended` on
# record-api-response.sh's line beside it, which counts rows too.

# A count and its unit, with the noun singular at one. Every count on the stderr line below goes
# through here, so all three read the same way.
function rows(n) { return n " row" (n == 1 ? "" : "s") }

BEGIN {
  while ((getline line < jobs) > 0) {
    ev = jval(line, "event")
    k = jval(line, "source") "|" jval(line, "source_id")
    if (ev == "surfaced" && jval(line, "run_id") == run_id) have[k] = 1
    else if (ev == "evaluated") have[k] = 1
    else continue
    why[k] = ev
  }
  close(jobs)
}
{
  k = jval($0, "source") "|" jval($0, "source_id")
  if (k in have) {
    # Which of the two rules above put the pair in the set, counted rather than thrown away. Every
    # row this branch drops is counted once and by one of the three: the BEGIN scan is the only
    # place that sets why[k], it sets it to "evaluated" or to "surfaced", and the one other way a
    # pair reaches the set is the line below, which leaves why[k] empty because the response itself
    # is where that pair came from.
    if (why[k] == "evaluated")     judged++
    else if (why[k] == "surfaced") already++
    else                           repeat++
    next
  }
  have[k] = 1
  print
}

END {
  # record-api-response.sh redirects this program's stdout into the file it appends to jobs.jsonl,
  # so every line printed there is an event in the user's log. This is a diagnostic rather than an
  # event, so it goes to stderr, where it passes through to the caller of record-api-response.sh.
  # `| "cat 1>&2"` is how an awk program in this pack writes to stderr — json-scan.awk:51-52 is the
  # precedent — and the close() is what flushes it.
  printf "dedup-surfaced: %s already judged, %s already surfaced by this run, %s repeated inside" \
         " this response\n", \
    rows(judged+0), rows(already+0), rows(repeat+0) | "cat 1>&2"
  close("cat 1>&2")
}
