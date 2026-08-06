# event-field.awk — read one field out of a single-line JSON event.
#
# Combine it with a program file: awk -f event-field.awk -f <program>.awk …
# POSIX awk forbids mixing -f with inline program text, which is why the callers are thin wrappers.
#
#   jraw(line, key)   the field's raw JSON text, quotes and escapes exactly as written, "" when the
#                     key is absent. Splice this into another event and nothing is escaped twice.
#   jval(line, key)   the field as text: a string with its quotes removed and its escapes resolved,
#                     any other value as written. Use it for display and for comparisons.
#
# The key is found by its quoted form, so "source" never matches "source_id" or "source_url", and
# the first occurrence wins. A string value is walked one character at a time, so an escaped quote
# inside a job title does not end it. Events put every structural and display field before the free
# text for this reason: reasoning that happens to contain "title": is found second, never first.

function _jafter(line, key,   tag, p) {
  tag = "\"" key "\":"
  p = index(line, tag)
  if (p == 0) return 0
  return p + length(tag)
}

function jraw(line, key,   p, i, c, len) {
  p = _jafter(line, key)
  if (p == 0) return ""
  len = length(line)
  if (substr(line, p, 1) != "\"") {
    for (i = p; i <= len; i++) {
      c = substr(line, i, 1)
      if (c == "," || c == "}" || c == "]") break
    }
    return substr(line, p, i - p)
  }
  for (i = p + 1; i <= len; i++) {
    c = substr(line, i, 1)
    if (c == "\\") { i++; continue }
    if (c == "\"") return substr(line, p, i - p + 1)
  }
  return ""
}

# A doubled backslash is resolved first and held aside as \001, so the character after it cannot be
# read as part of an escape: "C:\\temp" is C:\temp, not C:\ + a tab. \001 is safe to borrow because
# a JSON string cannot carry a raw control character — it has to be written \u0001, which arrives
# here as those six characters and is left alone. The held backslash goes back last.
function jval(line, key,   v) {
  v = jraw(line, key)
  if (substr(v, 1, 1) != "\"") return v
  v = substr(v, 2, length(v) - 2)
  gsub(/\\\\/, "\001", v)
  gsub(/\\n/, " ", v)
  gsub(/\\r/, " ", v)
  gsub(/\\t/, " ", v)
  gsub(/\\"/, "\"", v)
  gsub(/\\\//, "/", v)
  gsub(/\001/, "\\", v)
  return v
}
