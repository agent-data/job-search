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
# the first occurrence wins. Whitespace is allowed on both sides of the colon, because
# event-log-append.sh accepts an event written that way — every field check in it reads
# "key"[[:space:]]*:[[:space:]]* — and an event written by hand arrives here with it. A quoted
# string that no colon follows is a value rather than a key, so the search goes on to the next
# occurrence. A string value is walked one character at a time, so an escaped quote inside a job
# title does not end it. Events put every structural and display field before the free text for this
# reason: reasoning that happens to contain "title": is found second, never first.
#
# jval resolves \\ \" \/ \n \r \t \b \f, and maps the five whitespace escapes to a space because an
# event is one line. It leaves a \uXXXX escape as the six characters it is written with. The API
# sends raw UTF-8 rather than escapes: a live search response and a live get-posting response, 9,512
# and 13,792 bytes, both answer 0 to `grep -c '\\u[0-9a-fA-F]\{4\}'` and carry — ’ € ≤ as raw bytes.
# An event written by hand that used \u00f6 would show those six characters in a title rather than
# put a wrong value in a count, which is why resolving it is not worth the code it would take.
#
# jraw returns "" for an object or an array value. Such a value cut off at its first } or ] would
# come back as a fragment that reads like a whole one. Scan the document with json-scan.awk when a
# nested value is needed.

# The first position at or after p that is not JSON whitespace.
function _jskipws(line, p, len,   c) {
  while (p <= len) {
    c = substr(line, p, 1)
    if (c == " " || c == "\t" || c == "\n" || c == "\r") p++
    else return p
  }
  return p
}

function _jafter(line, key,   tag, p, q, off, len) {
  tag = "\"" key "\""
  len = length(line)
  off = 0
  for (;;) {
    p = index(substr(line, off + 1), tag)
    if (p == 0) return 0
    p = off + p
    q = _jskipws(line, p + length(tag), len)
    if (substr(line, q, 1) == ":") return _jskipws(line, q + 1, len)
    off = p
  }
}

function jraw(line, key,   p, i, c, len) {
  p = _jafter(line, key)
  if (p == 0) return ""
  len = length(line)
  c = substr(line, p, 1)
  if (c == "{" || c == "[") return ""
  if (c != "\"") {
    for (i = p; i <= len; i++) {
      c = substr(line, i, 1)
      if (c == "," || c == "}" || c == "]") break
    }
    while (i > p) {
      c = substr(line, i - 1, 1)
      if (c == " " || c == "\t" || c == "\n" || c == "\r") i--
      else break
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

# A doubled backslash is resolved first and replaced with \001, so the character after it cannot be
# read as part of an escape: "C:\\temp" is C:\temp, not C:\ followed by a tab. The input cannot
# contain \001 itself, because a JSON string cannot carry a raw control character — it has to be
# written \u0001, which arrives here as those six characters. The last gsub turns each \001 back
# into a backslash.
function jval(line, key,   v) {
  v = jraw(line, key)
  if (substr(v, 1, 1) != "\"") return v
  v = substr(v, 2, length(v) - 2)
  gsub(/\\\\/, "\001", v)
  gsub(/\\n/, " ", v)
  gsub(/\\r/, " ", v)
  gsub(/\\t/, " ", v)
  gsub(/\\b/, " ", v)
  gsub(/\\f/, " ", v)
  gsub(/\\"/, "\"", v)
  gsub(/\\\//, "/", v)
  gsub(/\001/, "\\", v)
  return v
}
