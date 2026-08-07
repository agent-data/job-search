# pipeline-counts.awk — see pipeline-counts.sh.
#
# A posting is keyed by its source and its source_id joined with SUBSEP, the 0x1c byte, the way
# run-counts.awk:14-16 keys one. That byte cannot reach a value: json-scan.awk refuses a raw
# control character inside a string, and jval leaves the escape that spells it as the six
# characters it is written with. Joining with a printable byte instead would give two postings one
# key: with a pipe, source `a` with source_id `b|c` and source `a|b` with source_id `c` both come
# out as `a|b|c`, and the two would be counted as one.
#
# The six count lines do not depend on `order` or on `badorder`. The word order on the INVALID line
# depends on both. The count lines are printf statements in a fixed order and every number on them
# is a sum, so the six numbers come out the same whatever order the walk visits the postings in.
# `badorder` is filled inside that walk, so the order the walk visits them in is the order the words
# are appended to `badorder`, and the word list on the INVALID line is `badorder` read back from 1
# to nbad.
#
# The walk reaches each posting exactly once because of `seen`, not because of `order`. `seen[k]` is
# set once per distinct posting, on the same line that appends to `order`, so a `for (k in seen)`
# walk reaches each posting exactly once too. Measured on 2026-08-07 against a log where one posting
# carries three lines — two evaluated and one status_changed carrying interested — this program and
# a copy with the walk rewritten that way both print interested=1, under BSD awk and under mawk.
#
# That rewrite does change the word list on the INVALID line. Measured on 2026-08-07 against a log
# carrying shortlisted, offer and screening in that order, `badorder` left as it is: this program
# prints shortlisted,offer,screening under both awks, and the rewrite prints
# shortlisted,offer,screening under BSD awk and screening,offer,shortlisted under mawk. Replacing
# `badorder` with `for (bw in badword)` and leaving the walk alone changes the word list too: on
# that log BSD awk prints shortlisted,screening,offer and mawk prints screening,offer,shortlisted.
# Two status words are not enough to show either difference — BSD awk keeps two in log order — which
# is why the case that pins this uses three.
#
# On a log carrying no uncounted status the program prints no INVALID line at all, so such a log
# cannot show either difference. Measured on 2026-08-07 against a live log of 159 lines carrying
# none, this program and the `for (k in seen)` rewrite print byte-identical output under BSD awk and
# under mawk. Every measurement above was run by copying this file and event-field.awk to a
# directory outside the repository, making the change there, and running
# `awk -f event-field.awk -f pipeline-counts.awk <log>` under /usr/bin/awk and again under mawk.
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
    # Five status words have a count line below and no other word has one, so a posting carrying
    # any other status would be in the pipeline and in none of the six numbers. Nothing upstream
    # stops one arriving: event-log-append.sh appends a status_changed carrying shortlisted at
    # exit 0, and job-search/SKILL.md:161 hands the agent the field with no list of allowed values.
    # So the posting is reported below rather than dropped, and to_confirm skips it as well, for the
    # reason to_confirm counts over the five in the first place.
    if (s != "new" && s != "interested" && s != "applied" && s != "rejected" && s != "archived") {
      uncounted++
      if (!(s in badword)) { badword[s] = 1; nbad++; badorder[nbad] = s }
      continue
    }
    count[s]++
    if (human[k] == "true") confirm++
  }
  printf "new=%d\n",         count["new"]+0
  printf "interested=%d\n",  count["interested"]+0
  printf "applied=%d\n",     count["applied"]+0
  printf "rejected=%d\n",    count["rejected"]+0
  printf "archived=%d\n",    count["archived"]+0
  printf "to_confirm=%d\n",  confirm+0
  # After every count line and then exit 1, the shape run-counts.awk:105-108 uses: a caller that
  # checks the status before reading stdout has the whole key set, and one that reads stdout without
  # checking gets six numbers that do not account for these postings and a line saying so.
  if (uncounted > 0) {
    words = ""
    for (i = 1; i <= nbad; i++) words = words (words == "" ? "" : ",") badorder[i]
    printf "INVALID posting-with-an-uncounted-status=%d %s\n", uncounted, words
    exit 1
  }
}
