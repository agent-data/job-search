# run-counts.awk — see run-counts.sh.
#
# Two ordered lists fix the order of the lines this prints, because awk walks an array in no defined
# order. `srcorder` holds the sources in the order they first surfaced a posting and orders the
# by_source_* lines; `grouporder` holds the search groups in the order they first appear in the log
# and orders searches_never_succeeded_ids. Replacing either with a `for (x in array)` walk moves the
# output: measured on a log with four lost searches, BSD awk and mawk each gave a different order
# and neither matched the log, so the same log read on two machines would print two different lines.
#
# `keys` orders nothing that is printed. It is how the END block reaches each posting this run
# surfaced exactly once, and every counter in that loop is a sum the order does not change —
# replacing that walk with `for (k in mine)` gives byte-identical output.
#
# A posting is keyed by its source and its source_id joined with SUBSEP, the 0x1c byte. That byte
# cannot reach a value: json-scan.awk refuses a raw control character inside a string, and jval
# leaves the escape that spells it as the six characters it is written with.

{
  ev = jval($0, "event")
  if (jval($0, "run_id") != want) next
  k = jval($0, "source") SUBSEP jval($0, "source_id")

  if (ev == "call") {
    route = jval($0, "route")
    ok    = jval($0, "ok")
    if (ok != "true") failed++
    if (route == "search-jobs") {
      searches++
      # A retry sequence lands as several events in one group: agent-data-reference:74 says a call
      # counts as failed once its three attempts are spent, so the group is the search and a group
      # with no ok:true member is a search that never returned. A single failed attempt in a group
      # that later answered is not one.
      g = jval($0, "source") ":" jval($0, "query_id")
      if (!(g in group)) { group[g] = 1; ngroup++; grouporder[ngroup] = g }
      if (ok == "true") answered[g] = 1
      # Only a search brings new rows in, which is what keeps rows_new_total equal to
      # postings_surfaced. A stored posting body writes a call event carrying rows_new 1
      # (record-api-response.sh:227), so adding rows_new from every route would put rows_new_total
      # one above postings_surfaced for each posting read in full. An absent, null or non-numeric
      # rows_new adds 0.
      rowsnew += jval($0, "rows_new")
    }
    else if (route == "get-posting") detailcalls++
    else                             other++
    next
  }
  if (ev == "surfaced") {
    if (!(k in mine)) {
      mine[k] = 1; count++; keys[count] = k
      s = jval($0, "source")
      if (!(s in bysrc)) { nsrc++; srcorder[nsrc] = s }
      bysrc[s]++
    }
    next
  }
  if (ev == "detail") { hasdetail[k] = 1; next }
  if (ev == "evaluated") {
    # The last judgment this run recorded for a posting wins.
    rel[k] = jval($0, "relevant"); band[k] = jval($0, "match"); judged[k] = 1
  }
}

END {
  # Only the postings this run surfaced are counted, so a detail read or a judgment carrying an id
  # no search of this run turned up adds nothing.
  for (i = 1; i <= count; i++) {
    k = keys[i]
    if (k in hasdetail) detailread++
    if (!(k in judged)) { unreviewed++; continue }
    reviewed++
    if (rel[k] == "true") {
      b = band[k]
      if (b == "strong")        strong++
      else if (b == "moderate") moderate++
      else if (b == "weak")     weak++
      else                      unbanded++
    } else filtered++
  }

  lostids = ""
  for (i = 1; i <= ngroup; i++) {
    g = grouporder[i]
    if (g in answered) continue
    lost++
    lostids = lostids (lostids == "" ? "" : ",") g
  }

  printf "postings_surfaced=%d\n",    count+0
  printf "postings_reviewed=%d\n",    reviewed+0
  printf "postings_unreviewed=%d\n",  unreviewed+0
  printf "postings_detail_read=%d\n", detailread+0
  printf "match_strong=%d\n",         strong+0
  printf "match_moderate=%d\n",       moderate+0
  printf "match_weak=%d\n",           weak+0
  printf "filtered_out=%d\n",         filtered+0
  for (i = 1; i <= nsrc; i++) printf "by_source_%s=%d\n", srcorder[i], bysrc[srcorder[i]]
  printf "calls_searches=%d\n",       searches+0
  printf "calls_detail_reads=%d\n",   detailcalls+0
  printf "calls_other=%d\n",          other+0
  printf "calls_total_metered=%d\n",  searches+detailcalls+other
  printf "calls_failed=%d\n",         failed+0
  printf "searches_never_succeeded=%d\n", lost+0
  printf "searches_never_succeeded_ids=%s\n", lostids
  printf "rows_new_total=%d\n",       rowsnew+0
  if (unbanded > 0) {
    printf "INVALID relevant-row-without-a-band=%d\n", unbanded
    exit 1
  }
}
