# run-matches.awk — see run-matches.sh.
#
# `order` fixes the order the rows come out in, because awk walks an array in no defined order. It
# holds the postings in the order this run first judged them, and the END block walks it four
# times, once per band. Replacing it with a `for (k in judgment)` walk moves the rows within a
# band, so the same log read on two machines prints two different digests. Measured on a log whose
# five strong judgments landed in the order 0003, 0000, 0004, 0002, 0001: BSD awk 20200816 printed
# them 0000, 0001, 0002, 0003, 0004 and mawk 1.3.4 printed them 0004, 0000, 0001, 0002, 0003 —
# three orders, no two alike. With `order`, both awks print the order the postings were first
# judged in.
#
# A posting is keyed by its source and its source_id joined with SUBSEP, the 0x1c byte, which
# cannot reach a value — the reason written out at run-counts.awk:14-16. A source_id may hold a
# `|`, so joining on one would let two postings share a key: record-judgment.sh:70-75 refuses only
# a control character and a backslash, and measured, source `s` with source_id `x|y` and source
# `s|x` with source_id `y` were both recorded at exit 0 and both join to `s|x|y`. With the key
# joined on `|`, this script printed one row for those two postings instead of two.
#
# run-counts.awk builds the same key, which keeps the two readable side by side, but the scripts
# never exchange keys, so that is a maintainability point rather than a correctness one.
#
# The row set is the one run-counts.awk counts as reviewed — a posting this run surfaced and this
# run judged — less two kinds of row the two paragraphs below cover: a posting that is the same
# opening as another, and a relevant row carrying no band. A judgment carrying an id no search of
# this run turned up is in none of them.
#
# A posting whose judgment carries same_role_as is the same opening as another posting, so it gets
# no row of its own and its location goes on the row of the posting it names. run-counts.awk counts
# it under duplicates_of_another and in no band, on the same test — whether the field is there,
# never on what it names — so the count above a band and the rows under it stay equal. The rule for
# a value that names no row here is written out in run-matches.sh.
#
# A relevant row carrying no band is left out here and reported by run-counts.sh, which is the
# script that owns that finding and exits 1 on it. A relevant row's band is one of strong, moderate
# and weak, so all three of these are rows with no band: an absent `match` key, which reads as an
# empty string; a JSON null, which reads as the four characters `null`; and the string `filtered`,
# which is what a row judged not relevant gets rather than a value a judgment carries.

BEGIN {
  rank["strong"] = 1; rank["moderate"] = 2; rank["weak"] = 3; rank["filtered"] = 4
}

{
  if (jval($0, "run_id") != want) next
  ev = jval($0, "event")
  if (ev != "surfaced" && ev != "evaluated") next
  k = jval($0, "source") SUBSEP jval($0, "source_id")
  if (ev == "surfaced") { mine[k] = 1; next }
  # The last judgment this run recorded for a posting wins, which is the rule run-counts.awk counts
  # by on its own `evaluated` branch — `grep -n 'The last judgment'
  # skills/job-search-run/scripts/run-counts.awk`. The posting keeps the place its first
  # judgment gave it, so a re-judged posting does not jump to the end of its band.
  if (!(k in seen)) { seen[k] = 1; n++; order[n] = k }
  judgment[k] = $0
}

END {
  # This first walk works out which postings are the same opening as another, and where else that
  # opening was posted. It runs before any row is printed, so a row carries the locations of
  # postings judged after it as well as of postings judged before it.
  #
  # The value is read as <source>:<source_id> split at the FIRST colon, because a source_id can hold
  # one: a greenhouse id is written <board>:<number>, so same_role_as:"greenhouse:acme:7310605" is
  # source greenhouse and source_id acme:7310605. Splitting at the last colon would build a key no
  # posting in the log has.
  for (i = 1; i <= n; i++) {
    k = order[i]
    if (!(k in mine)) continue
    rl = jval(judgment[k], "same_role_as")
    if (rl == "") continue
    dup[k] = 1
    p = index(rl, ":")
    if (p == 0) continue
    t = substr(rl, 1, p - 1) SUBSEP substr(rl, p + 1)
    loc = jval(judgment[k], "location_display")
    # A row that came back without a location has nothing to add to the column. record-api-response
    # writes null for a field a row does not carry and record-judgment copies it, so an absent
    # location arrives here as the four characters `null` and an empty one as the empty string.
    # Joined rather than skipped, the two reach the digest as `also posted in null; Boston, MA` and
    # `also posted in ; Boston, MA`. A location whose text really is `null` is skipped too; jval
    # gives the same four characters either way, and no live row has ever carried it.
    if (loc == "" || loc == "null") continue
    # The test is a statement of its own, not `also[t] = (t in also) ? also[t] "; " loc : loc`.
    # Measured on a log holding one opening posted in two cities: mawk 1.3.4 creates the element for
    # the left-hand side before it evaluates the right, so `t in also` was already true on the first
    # location and the column came out `; San Francisco, CA`, while BSD awk 20200816 printed
    # `San Francisco, CA` — one log, and a different column under each awk.
    if (t in also) also[t] = also[t] "; " loc
    else           also[t] = loc
  }

  for (b = 1; b <= 4; b++) {
    for (i = 1; i <= n; i++) {
      k = order[i]
      if (!(k in mine)) continue
      if (k in dup) continue
      l = judgment[k]
      if (jval(l, "relevant") == "true") {
        band = jval(l, "match")
        # The three bands a judgment carries, tested one by one the way run-counts.awk's END block
        # tests them — `grep -n 'b == "strong"' skills/job-search-run/scripts/run-counts.awk` — so
        # the two scripts call the same rows unbanded. `filtered` is not among them: it is what a
        # row judged not relevant gets, so a relevant row carrying the string `filtered` is a row
        # with no band, not a filtered-out posting.
        if (band != "strong" && band != "moderate" && band != "weak") continue
      } else band = "filtered"
      if (rank[band] != b) continue
      printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n",
        band,
        jval(l, "source"), jval(l, "source_id"),
        jval(l, "title"), jval(l, "company_name"), jval(l, "location_display"),
        jval(l, "source_url"), jval(l, "needs_human_check"),
        jval(l, "posted_at"), jval(l, "reasoning"), also[k]
    }
  }
}
