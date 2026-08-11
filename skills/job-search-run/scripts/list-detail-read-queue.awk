# list-detail-read-queue.awk — see list-detail-read-queue.sh.
#
# Titles and company names are free text and come through jval, which resolves the escapes a real
# posting carries. A JSON string cannot hold a literal tab, so the six fields stay six fields —
# measured with a title carrying two backslashes and a URL carrying %3D%3D, which both awks print
# as six fields and neither reinterprets.
#
# The evaluated check is scoped to this run. It changes nothing today: dedup-surfaced.awk puts an
# `evaluated` event of ANY run into the set of postings to skip, so a posting judged in an earlier
# run is never surfaced for this one and can never be queued for it. Measured — removing
# `&& rid == want` from that branch alone fails no test in tests/test_mechanics_scripts.py, while
# removing it from the surfaced or the queued branch fails
# test_the_queue_is_scoped_to_the_run_it_is_asked_for.
#
# Keep it anyway, because scoped is the answer this script wants if that rule ever changes. Were a
# posting judged in an earlier run surfaced again, this run has not judged it, so it belongs on this
# run's queue until this run does. run-counts.sh reads these same events, scoped to the same run id,
# and has to reach the same answer, so the two are written the same way.

{
  ev = jval($0, "event")
  k  = jval($0, "source") "|" jval($0, "source_id")
  rid = jval($0, "run_id")

  if (ev == "surfaced" && rid == want) {
    src[k]   = jval($0, "source");             sid[k]     = jval($0, "source_id")
    pid[k]   = jval($0, "posting_id_at_seen"); url[k]     = jval($0, "source_url")
    title[k] = jval($0, "title");              company[k] = jval($0, "company_name")
  }
  else if (ev == "queued" && rid == want) {
    if (!(k in queued)) { queued[k] = 1; n++; order[n] = k }
  }
  else if (ev == "evaluated" && rid == want) judged[k] = 1
}

END {
  for (i = 1; i <= n; i++) {
    k = order[i]
    if (k in judged) { done++; continue }
    listed++
    printf "%s\t%s\t%s\t%s\t%s\t%s\n", src[k], sid[k], pid[k], url[k], title[k], company[k]
  }
  # No rows is the ordinary case at the end of a run, and it is also what a mistyped run id gives.
  # A caller could not tell those two apart: both printed nothing on stdout, nothing on stderr, and
  # exited 0. This line tells them apart. `| "cat 1>&2"` is how an awk program in this pack writes
  # to stderr; json-scan.awk:51-52 is the precedent, and the close() is what flushes it.
  printf "list-detail-read-queue: %d queued for run %s, %d already judged, %d to read\n", \
    n+0, want, done+0, listed+0 | "cat 1>&2"
  close("cat 1>&2")
}
