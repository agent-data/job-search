# run-matches.awk — see run-matches.sh.
#
# `order` fixes the order the rows come out in, because awk walks an array in no defined order. It
# holds the postings in the order this run first judged them, and the END block walks it four
# times, once per band. Replacing it with a `for (k in judgment)` walk moves the rows within a
# band, so the same log read on two machines prints two different digests. Measured on a log whose
# five strong judgments landed in the order 0003, 0000, 0004, 0002, 0001: BSD awk 20200816 printed
# them 0000, 0001, 0002, 0003, 0004 and mawk 1.3.4 printed them 0004, 0000, 0001, 0002, 0003 —
# three orders, no two alike. With `order`, both awks print the order the judgments landed.
#
# A posting is keyed by its source and its source_id joined with SUBSEP, the same key
# run-counts.awk builds and for the reason written out there at :14-16.
#
# The row set is the same one run-counts.awk counts as reviewed: a posting this run surfaced and
# this run judged. That is what keeps the digest's listing and its counts the same length. A
# judgment carrying an id no search of this run turned up is in neither.
#
# A relevant row carrying no band is left out here and reported by run-counts.sh, which is the
# script that owns that finding and exits 1 on it. An absent `match` key reads as an empty string
# and a JSON null reads as the four characters `null`; `rank` has an entry for neither, so the one
# check leaves both out.

BEGIN {
  rank["strong"] = 1; rank["moderate"] = 2; rank["weak"] = 3; rank["filtered"] = 4
}

{
  if (jval($0, "run_id") != want) next
  ev = jval($0, "event")
  if (ev != "surfaced" && ev != "evaluated") next
  k = jval($0, "source") SUBSEP jval($0, "source_id")
  if (ev == "surfaced") { mine[k] = 1; next }
  # The last judgment this run recorded for a posting wins, which is the rule run-counts.awk:57-60
  # counts by. The posting keeps the place its first judgment gave it, so a re-judged posting does
  # not jump to the end of its band.
  if (!(k in seen)) { seen[k] = 1; n++; order[n] = k }
  judgment[k] = $0
}

END {
  for (b = 1; b <= 4; b++) {
    for (i = 1; i <= n; i++) {
      k = order[i]
      if (!(k in mine)) continue
      l = judgment[k]
      band = (jval(l, "relevant") == "true") ? jval(l, "match") : "filtered"
      if (!(band in rank) || rank[band] != b) continue
      printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n",
        band,
        jval(l, "source"), jval(l, "source_id"),
        jval(l, "title"), jval(l, "company_name"), jval(l, "location_display"),
        jval(l, "source_url"), jval(l, "needs_human_check"),
        jval(l, "posted_at"), jval(l, "reasoning")
    }
  }
}
