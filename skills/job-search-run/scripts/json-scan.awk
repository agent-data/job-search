# json-scan.awk — print every scalar in a JSON document as <path><TAB><raw value>.
#
# Usage: awk -f json-scan.awk <file.json>
#
# The whole document is read as one string and walked one character at a time, so line breaks
# carry no meaning: the same response pretty-printed and compacted scan identically, and a brace
# or a quote inside a job title is part of that title rather than structure.
#
# Path segments are joined with "."; an array index is a segment of its own. A search response
# prints lines like
#   data.results.0.title<TAB>"Strategic Finance, International"
#   data.results.0.source_id<TAB>"4417545222"
# and a posting response prints
#   data.description_markdown<TAB>"…"
#
# The value is the raw JSON text — a string keeps its quotes and its escapes — so a consumer can
# splice it into an event line without unescaping and re-escaping it. To read one result row's own
# fields and skip the fields of an object nested inside it, count the segments in the path:
# data.results.0.title has four, and data.results.0.company.name has five.
#
# A JSON string cannot hold a raw tab or newline, and this scanner exits 2 rather than passing one
# through, so one output line is always one field and the tab always separates path from value.
#
# Exit 0: the document parsed. Exit 2: it is not well-formed, with the byte offset on stderr.
#
# Scan into a file, check the status, then read the file. Never pipe this straight into another
# program: the rows found before a malformed byte are already on stdout, and POSIX sh has no
# PIPESTATUS, so `json-scan.awk resp.json | count.awk` reports the status of count.awk and a
# truncated response reads as a complete, short list of results.

# The C0 control characters, which RFC 8259 forbids raw inside a string. Building the set once and
# testing it with index() costs less than comparing the character against "\n", "\r" and "\t" one at
# a time: 400,000 iterations of the index() form take 0.063s against 0.178s for the three
# comparisons (`time awk 'BEGIN{ … for(j=0;j<400000;j++){ c=substr(s,3,1); … } }'`).
BEGIN { for (k = 1; k < 32; k++) ctl = ctl sprintf("%c", k) }

{ doc = doc $0 "\n" }

END {
  n = length(doc)
  i = 1
  skipws()
  c = substr(doc, i, 1)
  if (c != "{" && c != "[") bail("a JSON document starts with { or [")
  value("")
  skipws()
  if (i <= n) bail("trailing text after the document")
}

function bail(msg) {
  printf "json-scan: %s at byte %d\n", msg, i | "cat 1>&2"
  close("cat 1>&2")
  exit 2
}

function skipws(   c) {
  while (i <= n) {
    c = substr(doc, i, 1)
    if (c == " " || c == "\t" || c == "\n" || c == "\r") i++
    else return
  }
}

# At the opening quote; returns the raw string including both quotes and leaves i past the close.
# A raw control character exits 2 rather than passing through: a raw newline or tab inside a value
# would make a consumer splitting on the tab read one field as two, or one row as two.
function readstring(   start, c) {
  start = i
  i++
  while (i <= n) {
    c = substr(doc, i, 1)
    if (index(ctl, c) > 0) ctlbail(i)
    if (c == "\\") {
      if (index(ctl, substr(doc, i + 1, 1)) > 0) ctlbail(i + 1)
      i += 2
      continue
    }
    if (c == "\"") { i++; return substr(doc, start, i - start) }
    i++
  }
  bail("unterminated string")
}

# Byte n is always the newline this scanner appends after the last input line, so a string that
# reaches it was never closed; anywhere earlier it is a control character someone put in the value.
# `at` becomes the reported offset, so an escaped one points at the character, not at its backslash.
function ctlbail(at) {
  i = at
  if (at >= n) bail("unterminated string")
  bail("a raw control character inside a string")
}

# A number, true, false or null: everything up to the next structural character or space. The
# control-character check comes after the break, because a tab, newline or CR ends the token here
# rather than being wrong; any other control character is inside the token and is not valid JSON.
function readbare(   start, c) {
  start = i
  while (i <= n) {
    c = substr(doc, i, 1)
    if (c == "," || c == "}" || c == "]" || c == " " || c == "\t" || c == "\n" || c == "\r") break
    if (index(ctl, c) > 0) bail("a raw control character in a value")
    i++
  }
  if (i == start) bail("expected a value")
  return substr(doc, start, i - start)
}

function value(path,   c, key, idx) {
  skipws()
  c = substr(doc, i, 1)

  if (c == "{") {
    i++
    skipws()
    if (substr(doc, i, 1) == "}") { i++; return }
    for (;;) {
      skipws()
      if (substr(doc, i, 1) != "\"") bail("expected a key")
      key = readstring()
      key = substr(key, 2, length(key) - 2)
      skipws()
      if (substr(doc, i, 1) != ":") bail("expected : after a key")
      i++
      value(path == "" ? key : path "." key)
      skipws()
      c = substr(doc, i, 1)
      if (c == ",") { i++; continue }
      if (c == "}") { i++; return }
      bail("expected , or } in an object")
    }
  }

  if (c == "[") {
    i++
    skipws()
    if (substr(doc, i, 1) == "]") { i++; return }
    idx = 0
    for (;;) {
      value(path == "" ? idx : path "." idx)
      idx++
      skipws()
      c = substr(doc, i, 1)
      if (c == ",") { i++; continue }
      if (c == "]") { i++; return }
      bail("expected , or ] in an array")
    }
  }

  if (c == "\"") { printf "%s\t%s\n", path, readstring(); return }
  printf "%s\t%s\n", path, readbare()
}
