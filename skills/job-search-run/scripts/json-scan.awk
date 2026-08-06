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
# splice it into an event line without unescaping and re-escaping it. A consumer that wants a row's
# own fields and not a nested object's matches a fixed segment count.
#
# A JSON string cannot hold a literal tab or newline, so one output line is always one field and
# the tab always separates path from value.
#
# Exit 0: the document parsed. Exit 2: it is not well-formed, with the byte offset on stderr.

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
function readstring(   start, c) {
  start = i
  i++
  while (i <= n) {
    c = substr(doc, i, 1)
    if (c == "\\") { i += 2; continue }
    if (c == "\"") { i++; return substr(doc, start, i - start) }
    i++
  }
  bail("unterminated string")
}

# A number, true, false or null: everything up to the next structural character or space.
function readbare(   start, c) {
  start = i
  while (i <= n) {
    c = substr(doc, i, 1)
    if (c == "," || c == "}" || c == "]" || c == " " || c == "\t" || c == "\n" || c == "\r") break
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
