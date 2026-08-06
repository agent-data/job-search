# find-judgment.awk — print the `evaluated` event a posting already carries in one run.
#
# Usage: awk -f event-field.awk -f find-judgment.awk \
#          -v run_id=<id> -v source=<S> -v source_id=<id> <jobs.jsonl>
#
# It needs jval() from event-field.awk, so it is chained behind that file with a second -f. POSIX
# awk forbids mixing -f with inline program text, which is why this is a file rather than a
# here-document inside record-judgment.sh.
#
# Prints the last matching event, or nothing at all. The last one wins because the log is
# append-only, so a later event is the later word — the same rule the `tail -1` it replaced kept.
#
# Reading the four fields with jval, rather than grepping for their quoted text, settles two things
# at once.
#
# Whitespace. event-log-append.sh accepts an event with a space after any colon, and that is the
# path a host writing a judgment by hand comes through, so such an event is in the log by design. A
# chain of `grep -F "\"run_id\":\"R\""` finds none of it, and finding no judgment is what this
# script does when a posting has none. Measured on 2026-08-06, before this program existed: with the
# recorded judgment written by hand with a space after each of its four colons, a second and
# conflicting judgment was accepted — exit 0, a second evaluated event appended, and run-matches.sh
# then reported the later verdict. The same workspace with that judgment written compact exited 1,
# wrote nothing, and named both verdicts on stderr.
#
# Free text in a pattern. Three of the four values are supplied by the caller, and a source_id is
# whatever any of the four APIs puts in it, so switching those greps to `grep -E` would make a `.`
# or a `+` in an id match characters the id does not name. jval compares values and takes no
# pattern, so there is nothing to escape. The values still arrive through -v, where the caller's
# reject_id has already refused a control character and a backslash — the same three values reach
# record-judgment.awk that way.
#
# jval also ends the substring match `grep -F` does, where `"source_id":"abc"` is found on a line
# carrying `"source_id":"abcd"`. Five lookups still match by grep and still have it: the surfaced
# lookup in record-judgment.sh, and both lookups in each of queue-detail-read.sh and
# record-api-response.sh. record-judgment.sh:95-119 writes out that hazard, what rules it out on the
# committed fixtures, and why those five were left to move together.

jval($0, "event") != "evaluated"   { next }
jval($0, "run_id") != run_id       { next }
jval($0, "source") != source       { next }
jval($0, "source_id") != source_id { next }
{ last = $0 }
END { if (last != "") print last }
