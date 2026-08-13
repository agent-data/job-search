# find-judgment.awk — print the `evaluated` event a posting already carries, from any run.
#
# Usage: awk -f event-field.awk -f find-judgment.awk \
#          -v source=<S> -v source_id=<id> <jobs.jsonl>
#
# It needs jval() from event-field.awk, so it is chained behind that file with a second -f. POSIX
# awk forbids mixing -f with inline program text, which is why this is a file rather than a
# here-document inside record-judgment.sh.
#
# Prints the last matching event, or nothing at all. The last one wins because the log is
# append-only, so a later event is the later word — the same rule the `tail -1` it replaced kept.
#
# The lookup is not scoped to a run. A posting judged in an earlier run keeps that judgment: by the
# time a later run sees it the user has already read it and applied or passed on it, or the earlier
# run judged it outside the brief, so nobody is waiting on a second verdict. What a second verdict
# does do is put a second `evaluated` line in the log for one posting, and the two readers then
# report different things about it — posting-counts.awk filters on no run and reports the later
# verdict, run-counts.awk reports whichever verdict belongs to the run it was asked about.
# Measured 2026-08-08 on a log holding one posting judged `strong` in RUN-A and not relevant in
# RUN-B: posting-counts.sh printed `relevant=0 filtered=1`, run-counts.sh printed `match_strong=1`
# for RUN-A and `filtered_out=1` for RUN-B.
#
# The two programs that decide which postings a run is offered read the log the same way, so all
# three agree about what an already-judged posting is.
#   grep -c run_id skills/job-search-run/scripts/dedup.sh
# gives 0, so that file names no run anywhere. dedup-surfaced.awk keeps a posting out of its set on
# an `evaluated` event whatever run wrote it, and this prints the branch that does it:
#   grep -F 'else if (ev == "evaluated") have[k] = 1' skills/job-search-run/scripts/dedup-surfaced.awk
# Scoping any one of the three to a run is a change to all three.
#
# What none of the three does is scope the lookup to the brief a posting was judged under. A brief
# that changes can make a posting that was filtered out relevant, and reconsidering it would need
# dedup.sh and dedup-surfaced.awk to key on the brief as well, or the posting is never surfaced
# again to be reconsidered. That is a separate change, and nothing here starts it: this program
# takes two values, `source` and `source_id`, and neither names a brief.
#
# Reading the three fields with jval, rather than grepping for their quoted text, settles two things
# at once.
#
# Whitespace. event-log-append.sh accepts an event with a space after any colon, and that is the
# path a harness writing a judgment by hand comes through, so such an event is in the log by design. A
# chain of `grep -F` against the compact quoted text finds none of it, and finding no judgment is
# what this script does when a posting has none. Measured on 2026-08-06, before this program
# existed: with the recorded judgment written by hand with a space after each of its colons, a
# second and conflicting judgment was accepted — exit 0, a second evaluated event appended, and
# run-matches.sh then reported the later verdict. The same workspace with that judgment written
# compact exited 1, wrote nothing, and named both verdicts on stderr.
#
# Free text in a pattern. Both values are supplied by the caller, and a source_id is whatever any of
# the four APIs puts in it, so matching them with `grep -E` would make a `.` or a `+` in an id match
# characters the id does not name. jval compares values and takes no pattern, so there is nothing to
# escape. The values still arrive through -v, where the caller's reject_id has already refused a
# control character and a backslash — the same values reach record-judgment.awk that way.

jval($0, "event") != "evaluated"   { next }
jval($0, "source") != source       { next }
jval($0, "source_id") != source_id { next }
{ last = $0 }
END { if (last != "") print last }
