# list-detail-read-queue.awk — see list-detail-read-queue.sh.
#
# Titles and company names are free text and come through jval, which resolves the escapes a real
# posting carries. A JSON string cannot hold a literal tab, so the six fields stay six fields —
# measured with a title carrying two backslashes and a URL carrying %3D%3D, which both awks print
# as six fields and neither reinterprets.
#
# The evaluated check is scoped to this run, matching run-counts.sh. It changes nothing today:
# record-api-response.sh skips a posting any run has judged, so a posting judged earlier is never
# surfaced for this run and can never be queued for it. Measured — removing `&& rid == want` from
# that branch alone fails no test in tests/test_mechanics_scripts.py, while removing it from the
# surfaced or the queued branch fails test_the_queue_is_scoped_to_the_run_it_is_asked_for. It is
# here so the three scripts keep saying the same thing if the dedup rule ever moves.

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
    if (k in judged) continue
    printf "%s\t%s\t%s\t%s\t%s\t%s\n", src[k], sid[k], pid[k], url[k], title[k], company[k]
  }
}
