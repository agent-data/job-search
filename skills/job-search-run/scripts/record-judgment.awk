# record-judgment.awk — build one `evaluated` event. See record-judgment.sh.
#
# Field order is load-bearing. Every field a script reads to decide something comes before the
# three free-text ones, because the readers take a key's first occurrence: reasoning that happens
# to contain "status": cannot be mistaken for the status field. The reverse case — a dealbreaker
# holding the literal "reasoning": — would misread one line of display text and no count, which is
# the trade this ordering makes on purpose.
#
# The five display fields are spliced in as the raw JSON they already are on the surfaced event,
# so a title carrying \" moves across byte-exact instead of being unescaped and escaped again.

function esc(s) {
  gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s)
  gsub(/\t/, "\\t", s); gsub(/\r/, "\\r", s); gsub(/\n/, "\\n", s)
  return s
}
function jstr(s) { return "\"" esc(s) "\"" }
function jlist(s,   n, parts, i, out) {
  if (s == "") return "[]"
  n = split(s, parts, ";")
  out = "["
  for (i = 1; i <= n; i++) {
    if (parts[i] == "") continue
    if (out != "[") out = out ","
    out = out jstr(parts[i])
  }
  return out "]"
}
# jraw returns two characters for a JSON empty string and none at all for an absent key, which is
# why presence is tested with it rather than with jval.
function copied(key,   v) { v = jraw(ENVIRON["RJ_SURFACED"], key); return v == "" ? "null" : v }

BEGIN {
  out = "{\"event\":\"evaluated\""
  out = out ",\"run_id\":" jstr(run_id)
  out = out ",\"source\":" jstr(source)
  out = out ",\"source_id\":" jstr(source_id)
  out = out ",\"title\":" copied("title")
  out = out ",\"company_name\":" copied("company_name")
  out = out ",\"location_display\":" copied("location_display")
  out = out ",\"source_url\":" copied("source_url")
  out = out ",\"posted_at\":" copied("posted_at")
  out = out ",\"detail_read\":" detail_read
  out = out ",\"relevant\":" relevant
  out = out ",\"match\":" (band == "" ? "null" : jstr(band))
  out = out ",\"needs_human_check\":" nhc
  out = out ",\"status\":\"new\""
  out = out ",\"ts\":" jstr(ts)
  if (same_role != "")        out = out ",\"same_role_as\":" jstr(same_role)
  if (posted_extracted != "") out = out ",\"posted_at_extracted\":" jstr(posted_extracted)
  out = out ",\"dealbreakers_hit\":" jlist(ENVIRON["RJ_DEALBREAKERS"])
  out = out ",\"unknowns\":" jlist(ENVIRON["RJ_UNKNOWNS"])
  out = out ",\"reasoning\":" \
        (ENVIRON["RJ_REASONING"] == "" ? "null" : jstr(ENVIRON["RJ_REASONING"]))
  out = out "}"
  print out
}
