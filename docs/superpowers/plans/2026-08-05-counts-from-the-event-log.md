# Counts From The Event Log — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every count, every timestamp, and every posting the digest names out of the model's account of the run and into scripts that read the run's own append-only event log.

**Architecture:** `jobs.jsonl` gains four event types — `call`, `surfaced`, `queued`, `detail` — alongside the `evaluated` one it already holds. Scripts write every event: a search response becomes `surfaced` rows, a posting response becomes a `detail`, the model's judgment becomes an `evaluated`. `run-counts.sh` reads that log and prints the run's numbers; `run-matches.sh` reads it and prints the postings the digest lists; `close-run.sh` copies the numbers into the run record; `validate-workspace.sh` recomputes them and fails a record that disagrees. The model supplies judgments, which postings to read, and three values at close.

**Tech Stack:** POSIX `sh` + `awk` for everything shipped inside a skill (no `jq`, no Python, no bash-isms). Stdlib-only Python 3 for the dev tooling in `tests/` and `evals/`. `pytest` for unit tests; the live behavior-eval harness in `evals/` for anything a skill's prose governs.

**Spec:** `docs/superpowers/specs/2026-08-05-counts-from-the-event-log-design.md`

**Nineteen tasks, 0 through 18.** Task 0 is new and everything else rests on it: the JSON parsing the rest of the plan needs is one scanner, written once.

## Global Constraints

- **Branch:** `feat/counts-from-the-event-log`. Never commit to `main`.
- **Shipped scripts are POSIX `sh` + `awk`.** No `jq`, no Python, no `bash` constructs. Tests invoke every script through `sh`, and through `dash` where present.
- **An `awk` program that needs the shared field readers is its own `.awk` file**, invoked as `awk -f event-field.awk -f <program>.awk`. POSIX `awk` forbids mixing `-f` with inline program text, so those scripts are thin shell wrappers that check arguments and hand off. Seven `.awk` files ship: `json-scan.awk`, `event-field.awk`, `record-judgment.awk`, `list-detail-read-queue.awk`, `run-counts.awk`, `run-matches.awk`, `pipeline-counts.awk`. A skill's prose names only the `.sh` in front of each; the wrapper resolves its own `.awk` from `$(dirname "$0")`.
- **`match` is an `awk` built-in.** Never use it as an `awk` variable name — use `band`. This cost a debugging cycle during design.
- **`awk -v` cannot carry a literal newline.** Free text (reasoning, dealbreakers, unknowns) and any whole event line passed into a program go through the environment and are read with `ENVIRON[...]`.
- **Nothing is appended unless the whole response checks out.** A response with one bad row appends none of its rows. Every rejection exits non-zero and names the file, the row, and the field on stderr. The one exception is the `call` event, which is written for every attempt — a failed one, and a duplicate one, included.
- **Never assert on a skill's prose.** No test may grep a `SKILL.md` for a phrase, a sentence, or a regex standing in for a documented rule. Script behavior is tested with pytest against real artifacts; anything a skill's prose governs is graded by the live behavior evals in `evals/`. `tests/test_mechanics_scripts.py`'s own docstring already states this: "Nothing here asserts how the reference documents word the same rules."
- **No test hardcodes a number that came from a capture.** A count that depends on what a fixture holds is read from the fixture (`len(api_rows("search.linkedin.json"))`), never written as a literal. A live capture that returns 24 rows instead of 25 must not turn into a red suite.
- **Fixtures carry no real posting.** `.gitignore` already states the rule for eval output — "they carry machine paths and live posting text; only the aggregate numbers in `evals/baseline/` are committed." `tests/fixtures/` is not gitignored, so every captured response is scrubbed to fictional companies, titles, URLs and description text before it is committed, by `tests/fixtures/scrub.py` so a re-capture is reproducible. `evals/cases/fault-503.yaml` states the same convention: "The companies are fictional, as in every other fixture here."
- **Word budget:** `AGENTS.md:29` sets 10,000 words across the seven `SKILL.md` files. `wc -w skills/*/SKILL.md` reports 9,092 at the start of this plan. Exceeding 10,000 at the end is a blocking defect.
- **Public repo, MIT, © Aptiq Labs, Inc.** No tracked file — not a doc, not a commit message — mentions a hosted or commercial product. This is a counting and timestamp fix.
- **Prose voice.** The `SKILL.md` files are continuous prose read by a model at runtime. Do not restructure them into checklists or add headings that were not there.
- **No metaphors, no invented jargon.** Say what the code does. "The last line for a `source` and `source_id` wins", never "the fold". Personification is the same failure: a gate does not see, a contract does not know.
- **Never state a measurable fact without running the command that settles it.** Cite the command next to the number.
- **`git add` names paths.** No `git add -A` in any commit step; a blunt `-A` is how an untracked stray gets committed.
- Unchanged: the `strong / moderate / weak` vocabulary; `run_id`'s format (`2026-07-30T15-04-02Z`); `.scratch/` and `.started-<run_id>` semantics. No token or cost field is added.

## What the live API actually returns

Four facts settled by live calls on 2026-08-05 and 2026-08-06. Three of them are not in `agent-data-reference` today; Task 15 puts them there.

1. **A search response is pretty-printed, one key per line**, and `source_id` arrives as a quoted string (`"source_id": "4417545222"`). The scanner in Task 0 does not depend on either — that is the point of it — but the fixtures will look like this.
2. **`request_id` on a success is at `meta.request_id`**, not at the top level.
3. **A failed call writes its body to stderr and exits 1.** stdout is empty. Any recipe that wants the error body must redirect: `agent-data call … > resp.json 2> resp.err`.
4. **The error body is a top-level `error` object** carrying `status`, `code`, `message`, `param`, `request_id`, `retryable`, `source`, and a nested duplicate under `error.body.error`. Note `error.source` is `"service"` — it is not a job source, and nothing may read it as one.

```json
{ "error": { "status": 400, "code": "validation_error",
             "message": "posting_id and source_url refer to different jobs",
             "param": "source_url", "request_id": "req_186fafd5efd14ea98f9338ee",
             "retryable": false, "source": "service" } }
```

`retryable` is the boolean `agent-data-reference:66-71` already tells a run to branch on, so the `call` event carries it.

## The event shapes every task depends on

Single-line JSON, one event per line, appended to `<workspace>/jobs.jsonl`.

```
{"event":"call","run_id":"2026-08-05T16-47-00Z","ts":"2026-08-05T16:47:14Z","route":"search-jobs","source":"linkedin","query_id":"strategic-finance-sf","ok":true,"rows_returned":25,"rows_new":25,"error_code":null,"retryable":null,"request_id":"req_9a79bdf4a26f4e98854f259d"}
{"event":"surfaced","run_id":"…","query_id":"…","source":"linkedin","source_id":"4449006488","posting_id_at_seen":"jp_74856f265f40","source_url":"…","title":"…","company_name":"…","location_display":"…","salary_display":null,"employment_type":null,"department_name":null,"team_name":null,"is_remote":null,"workplace_type":null,"posted_at":"2026-08-04T00:00:00+00:00","detail_available":true,"ts":"…"}
{"event":"queued","run_id":"…","source":"linkedin","source_id":"4449006488","ts":"…"}
{"event":"detail","run_id":"…","source":"linkedin","source_id":"4449006488","description_markdown":"…","employment_type":"…","apply_url":"…","is_listed":true,"is_remote":null,"workplace_type":null,"staleness_status":"fresh","ts":"…"}
{"event":"evaluated","run_id":"…","source":"linkedin","source_id":"4449006488","title":"…","company_name":"…","location_display":"…","source_url":"…","posted_at":"…","detail_read":true,"relevant":true,"match":"strong","needs_human_check":false,"status":"new","ts":"…","dealbreakers_hit":[],"unknowns":["equity"],"reasoning":"…"}
```

`status_changed` is unchanged.

**Field order in the `evaluated` event is load-bearing.** Every structural and display field comes before `reasoning`, `dealbreakers_hit` and `unknowns`. The field readers find a key by its first occurrence, so free text that happens to contain `"title":` cannot be mistaken for the field when the real field was already found earlier in the line.

**The five display fields on `evaluated` are copied by the script**, verbatim from the `surfaced` event it already looks up to prove the posting belongs to this run. The model supplies none of them, so §2's "the model supplies judgments and nothing else" still holds exactly. They are there because the digest's per-posting line and the home view's status-change flow both need them, and because a run's postings must be readable without opening a log that grows past a context window.

Three fields the pre-change `evaluated` event carried are dropped on purpose, and §14 of the spec records each:

| Field | Why |
|---|---|
| `first_seen` | Nothing reads it. `grep -rn first_seen skills/` returns the instruction to write it and the template, and no consumer. |
| `salary_display` | Read at scan time off the row and by `evaluate-job-fit`; never rendered in the digest. Stays on `surfaced`. |
| `query_id` | Its only consumer was the eval expectation at `skills/job-search-run/evals/evals.json:15`, which Task 17 rewrites. Stays on `surfaced` and on `call`. |

## `run-counts.sh` output contract

Every consumer reads these exact keys. Task 5 produces them; Tasks 9, 10 and 13 consume them.

```
postings_surfaced=50
postings_reviewed=47
postings_unreviewed=3
postings_detail_read=35
match_strong=3
match_moderate=12
match_weak=0
filtered_out=32
by_source_linkedin=25
by_source_ashby=25
calls_searches=6
calls_detail_reads=38
calls_other=0
calls_total_metered=44
calls_failed=1
searches_never_succeeded=1
searches_never_succeeded_ids=ashby:ml-platform-sf
rows_new_total=50
```

Every value is an integer except `searches_never_succeeded_ids`, which is a comma-separated list of `source:query_id` and may be empty. `close-run.sh` reads keys by name, so the one non-integer value never reaches a `%d`.

A relevant row carrying no band prints one extra line, `INVALID relevant-row-without-a-band=<n>`, and exits 1.

## `run-matches.sh` output contract

One tab-separated line per posting this run judged, ordered strong, moderate, weak, filtered, and within a band in the order the judgments landed.

```
band  source  source_id  title  company_name  location_display  source_url  needs_human_check  posted_at  reasoning
```

`band` is `strong`, `moderate`, `weak` or `filtered`. This is what the digest lists. Task 6 produces it; Task 13 consumes it; Task 17 grades the digest against it.

## File structure

| Path | Responsibility |
|---|---|
| `skills/job-search-run/scripts/json-scan.awk` | scan one JSON document, print every scalar as `path<TAB>raw value` |
| `skills/job-search-run/scripts/event-field.awk` | read one field out of a single-line event: `jraw` raw, `jval` as text |
| `skills/job-search-run/scripts/record-api-response.sh` | one agent-data response → the events it implies |
| `skills/job-search-run/scripts/queue-detail-read.sh` | mark one posting as one to read in full |
| `skills/job-search-run/scripts/list-detail-read-queue.sh` + `.awk` | print the queued, not-yet-judged postings |
| `skills/job-search-run/scripts/record-judgment.sh` + `record-judgment.awk` | record one posting's judgment |
| `skills/job-search-run/scripts/run-counts.sh` + `run-counts.awk` | this run's numbers, from the log |
| `skills/job-search-run/scripts/run-matches.sh` + `run-matches.awk` | the postings this run judged, for the digest |
| `skills/job-search-run/scripts/dedup.sh` | *(modify)* known set keys on `evaluated` events only |
| `skills/job-search-run/scripts/event-log-append.sh` | *(modify)* idempotency check looks only at `evaluated` lines; header contract reconciled |
| `skills/job-search-runbook/scripts/open-run.sh` | mint `run_id` + `started_at` from one clock read, create the marker, take the brief revision, run the workspace checks |
| `skills/job-search-runbook/scripts/close-run.sh` | read the clock for `completed_at`, take counts from `run-counts.sh`, derive `run_health`, write the record |
| `skills/job-search-runbook/scripts/clear-run.sh` | delete the marker and the scratch directory, after the digest is written |
| `skills/job-search-runbook/scripts/validate-workspace.sh` | *(modify)* the count fields, the four invariants, the two timestamp gates |
| `skills/job-search/scripts/pipeline-counts.sh` + `pipeline-counts.awk` | the home view's per-status counts |
| `tests/conftest.py` | the `tmp_workspace` fixture, shared by both test modules |
| `tests/fixtures/scrub.py` | turn a live capture into a committable fixture |
| `tests/test_mechanics_scripts.py` | *(modify)* every new script, every failure path |
| `tests/test_validate_workspace.py` | *(modify)* the invariants and timestamp gates |
| `evals/cases/*.yaml`, `evals/behaviors.md` | the behavior rows that grade the prose |

---

### Task 0: `json-scan.awk` and `event-field.awk`

Everything downstream parses JSON. Written once, here, so no other task hand-rolls it. The scanner reads the whole document as one string and walks it character by character, so line breaks carry no meaning: the same response pretty-printed and compacted scan identically. That is the whole reason this task exists — a line-oriented parser works on today's CLI output and silently produces one garbage row the day that output changes.

**Files:**
- Create: `skills/job-search-run/scripts/json-scan.awk`, `skills/job-search-run/scripts/event-field.awk`
- Create: `tests/conftest.py`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `awk -f json-scan.awk <file.json>` prints one line per scalar, `path<TAB>raw JSON value`, in document order. Exit 0 when the document parsed; exit 2 with the byte offset on stderr when it did not. `event-field.awk` defines `jraw(line, key)` and `jval(line, key)` for use by other `.awk` programs.

- [ ] **Step 1: Write the failing tests**

```python
import json, os, pathlib, subprocess

SCAN = RUN_SCRIPTS / "json-scan.awk"


def scan(text):
    r = subprocess.run(["awk", "-f", str(SCAN)], input=text, capture_output=True, text=True)
    return r, [l.split("\t", 1) for l in r.stdout.splitlines()]


def test_a_scalar_is_printed_with_its_path_and_its_raw_value():
    r, out = scan('{"data": {"results": [{"title": "Strategic Finance", "source_id": "4417545222"}]}}')
    assert r.returncode == 0, r.stderr
    assert ["data.results.0.title", '"Strategic Finance"'] in out
    assert ["data.results.0.source_id", '"4417545222"'] in out


def test_the_same_document_compacted_scans_identically():
    pretty = (FIXTURES / "search.linkedin.json").read_text()
    compact = json.dumps(json.loads(pretty), separators=(",", ":"), ensure_ascii=False)
    assert scan(pretty)[1] == scan(compact)[1]


def test_a_row_closing_on_the_same_line_as_its_last_field_keeps_that_field():
    _, out = scan('{"data":{"results":[\n  {"a": 1,\n   "b": "last" }\n]}}')
    assert ["data.results.0.b", '"last"'] in out


def test_a_nested_object_inside_a_row_does_not_leak_into_the_row():
    _, out = scan('{"data":{"results":[{"source_id":"x","co":{"source_id":"LEAK"},"t":[1,2]}]}}')
    row = [p for p, _ in out if p.startswith("data.results.0.") and p.count(".") == 3]
    assert row == ["data.results.0.source_id"]
    assert ["data.results.0.co.source_id", '"LEAK"'] in out


def test_braces_and_quotes_inside_a_string_are_not_structure():
    hostile = 'He said \\"{done}\\" — path C:\\\\temp\\tand\\na newline.'
    _, out = scan('{"data": {"description_markdown": "%s"}}' % hostile)
    assert dict(out)["data.description_markdown"] == '"%s"' % hostile


def test_an_empty_results_array_prints_no_row_and_succeeds():
    r, out = scan('{"data": {"results": [], "query": {"source": "ashby"}}}')
    assert r.returncode == 0
    assert [p for p, _ in out if p.startswith("data.results.")] == []
    assert ["data.query.source", '"ashby"'] in out


def test_malformed_json_exits_two_and_names_the_offset():
    r, _ = scan('{"data": {"results": [')
    assert r.returncode == 2
    assert "json-scan" in r.stderr


def test_the_real_error_body_scans_to_its_fields():
    r, out = scan((FIXTURES / "detail.error.json").read_text())
    d = dict(out)
    assert d["error.code"] == '"validation_error"'
    assert d["error.retryable"] == "false"
    assert d["error.request_id"].startswith('"req_')
```

For `event-field.awk`, drive it through a one-line probe program so the library is tested on its own:

```python
FIELD = RUN_SCRIPTS / "event-field.awk"
PROBE = "{ printf \"%s\\n%s\\n\", jraw($0, k), jval($0, k) }"


def field(line, key):
    r = subprocess.run(["awk", "-f", str(FIELD), "-v", "k=" + key, PROBE],
                       input=line + "\n", capture_output=True, text=True)
    raw, val = r.stdout.split("\n")[:2]
    return raw, val


def test_source_never_matches_source_id_or_source_url():
    line = '{"source":"linkedin","source_id":"123","source_url":"https://x/y"}'
    assert field(line, "source") == ('"linkedin"', "linkedin")
    assert field(line, "source_id") == ('"123"', "123")


def test_an_escaped_quote_inside_a_value_does_not_end_it():
    line = '{"title":"Manager \\"Finance\\" role","company_name":"Acme"}'
    assert field(line, "title")[0] == '"Manager \\"Finance\\" role"'
    assert field(line, "title")[1] == 'Manager "Finance" role'
    assert field(line, "company_name")[1] == "Acme"


def test_a_number_a_boolean_and_a_null_come_back_as_written():
    line = '{"n":25,"ok":true,"m":null}'
    assert field(line, "n")[0] == "25"
    assert field(line, "ok")[0] == "true"
    assert field(line, "m")[0] == "null"


def test_an_absent_key_is_empty():
    assert field('{"a":1}', "b") == ("", "")
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k "scan or field" -v`
Expected: every test errors — neither `.awk` file exists.

- [ ] **Step 3: Write `json-scan.awk`**

```awk
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
```

A key holding a `.` would make an ambiguous path. No route in this API has one; if one ever does, the consumers' fixed-segment-count match is what would need to change.

- [ ] **Step 4: Write `event-field.awk`**

```awk
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

function jval(line, key,   v) {
  v = jraw(line, key)
  if (substr(v, 1, 1) != "\"") return v
  v = substr(v, 2, length(v) - 2)
  gsub(/\\n/, " ", v)
  gsub(/\\r/, " ", v)
  gsub(/\\t/, " ", v)
  gsub(/\\"/, "\"", v)
  gsub(/\\\//, "/", v)
  gsub(/\\\\/, "\\", v)
  return v
}
```

`jval` resolves the escapes a posting title and a company name actually carry. It is for display only; `jraw` is what moves a value from one event to another, and it is byte-exact.

- [ ] **Step 5: Write `tests/conftest.py`**

`tmp_workspace` is defined in `tests/test_validate_workspace.py` today and Tasks 8, 9, 10 and 11 all need it. Move it, rather than copying it:

```python
"""Fixtures shared by the mechanics and validator suites."""
import pathlib
import pytest

CONFIG = "version: 1\nqueries: []\nschedule:\n  frequency: daily\nsearch:\n  sources: [linkedin]\n"
PREFS = "---\ncreated_at: 2026-07-16T14:00:00Z\nupdated_at: 2026-07-16T14:00:00Z\n---\n\nA brief.\n"


@pytest.fixture
def tmp_workspace(tmp_path):
    ws = tmp_path / "workspace"
    (ws / "runs").mkdir(parents=True)
    (ws / "config.yaml").write_text(CONFIG, encoding="utf-8")
    (ws / "preferences.md").write_text(PREFS, encoding="utf-8")
    return ws
```

Delete the copy in `tests/test_validate_workspace.py`, keeping its `CONFIG`/`PREFS` content — that module's existing tests must go on passing unchanged.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k "scan or field" -v && python3 -m pytest tests/test_validate_workspace.py -q`
Expected: the new tests PASS and the validator suite is unchanged.

Tasks 1 and 2 create `search.linkedin.json` and `detail.error.json`; run the two tests that need them after Task 1 Step 2, and note here that they were deferred rather than reporting a pass you did not see.

- [ ] **Step 7: Commit**

```bash
git add skills/job-search-run/scripts/json-scan.awk skills/job-search-run/scripts/event-field.awk \
        tests/conftest.py tests/test_mechanics_scripts.py tests/test_validate_workspace.py
git commit -m "feat(run): parse JSON by scanning it, not by reading it a line at a time"
```

---

### Task 1: `record-api-response.sh` — search responses

**Files:**
- Create: `skills/job-search-run/scripts/record-api-response.sh`
- Create: `tests/fixtures/scrub.py`
- Create: `tests/fixtures/api-responses/search.linkedin.json`, `search.ashby.json`, `search.zero.json`, `detail.error.json`, `search.badrow.json`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `json-scan.awk` (Task 0).
- Produces: `record-api-response.sh <run_id> <jobs.jsonl> <response.json> --route search-jobs [--query-id ID] [--source S]`. Appends one `call` event always, then one `surfaced` event per new row. Exit 0 on success, a search that legitimately returned zero rows included; exit 1 with nothing but the `call` event appended when the response is an error or any row is unusable; exit 2 on a missing file, bad arguments, or a response whose shape does not match `--route`.

**The route is passed in, never inferred.** The caller knows which route it called. Deciding it from the response body — as an earlier draft of this plan did, by looking for `description_markdown` — records every *failed* detail read as a failed search, because an error body carries no description. That corrupts `agent_data_usage.searches` and `detail_reads`, which are two of the numbers this change exists to make true.

- [ ] **Step 1: Capture the fixtures, then scrub them**

Capture live. Note that a failed call writes its body to **stderr** and exits 1, so the error capture redirects stderr, not stdout.

```sh
L=f9a6ec16-0bfd-44d8-b3ee-073776745ee7
mkdir -p tests/fixtures/api-responses
cd tests/fixtures/api-responses

agent-data call $L search-jobs --keywords "strategic finance" --location "San Francisco Bay Area" \
  --limit 25 --source linkedin > raw.search.linkedin.json
agent-data call $L search-jobs --keywords "strategic finance" --location "San Francisco" \
  --limit 25 --source ashby > raw.search.ashby.json
agent-data call $L search-jobs --keywords "zzzqqq nonexistent xyzzy" --limit 5 --source ashby \
  > raw.search.zero.json
# A mismatched posting_id/source_url pair returns a real 400 validation_error, on stderr.
agent-data call $L get-posting --posting_id jp_74856f265f40 \
  --source_url "https://jobs.ashbyhq.com/aiuc/3de3fbde-af29-48a3-9ec8-18811973ec86" \
  > /dev/null 2> raw.detail.error.json || true
```

The two live search fixtures differ in exactly the ways the event builder must absorb, and Task 15 adds the third of these to `agent-data-reference`: LinkedIn fills `posted_at` and leaves `published_at`, `salary_display`, `is_remote`, `workplace_type`, `employment_type`, `department_name` and `team_name` null on every row; Ashby is the reverse; and Ashby's `published_at` carries no timezone (`2026-08-05T04:37:31.446000`) where LinkedIn's does (`2026-08-04T00:00:00+00:00`).

Then scrub. `tests/fixtures/scrub.py` rewrites the identifying values and leaves everything the parser and the event builder care about intact:

```python
#!/usr/bin/env python3
"""Turn a live agent-data capture into a fixture that can be committed.

The repo does not commit live posting text — .gitignore says so for eval output, and the same
holds here. What a fixture is FOR is the row shape, so the scrub keeps every key, every type,
every null, the row count, and the per-source date pattern, and replaces only what identifies a
real posting: company, title, the two ids, the URL, and the description body.

Usage: python3 tests/fixtures/scrub.py raw.search.linkedin.json search.linkedin.json
"""
import hashlib, json, re, sys

COMPANIES = ["Globex", "Initech", "Umbrella Systems", "Northwind Labs", "Acme Robotics",
             "Vandelay Industries", "Soylent Foods", "Cyberdyne", "Wonka Industries", "Tyrell Corp"]
TITLES = ["Strategic Finance Manager", "Senior Financial Analyst", "Director, FP&A",
          "Finance Business Partner", "Corporate Development Associate"]

# Every character a JSON string can carry that the scanner and the event builder must survive.
HOSTILE = ('A role at the company. He said "it\'s a \\"strong\\" fit" — path C:\\temp, '
           'a {braced} phrase, a tab\there and a newline\nafter it.\n\n')


def pick(seq, seed):
    return seq[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(seq)]


def scrub_row(row, i):
    if "company_name" in row and row["company_name"] is not None:
        row["company_name"] = pick(COMPANIES, row.get("source_id", "") or str(i))
    if "title" in row and row["title"] is not None:
        row["title"] = pick(TITLES, (row.get("source_id", "") or str(i)) + "t")
    if row.get("source_id"):
        row["source_id"] = "%s-%04d" % (row.get("source", "src"), i)
    if row.get("id"):
        row["id"] = "jp_%s" % hashlib.sha256(("%d" % i).encode()).hexdigest()[:12]
    if row.get("source_url"):
        # Keep LinkedIn's tracking-parameter shape; it is a real parser input.
        tail = "?position=%d&pageNum=0&refId=AAAA%%3D%%3D" % (i + 1) if "?" in row["source_url"] else ""
        row["source_url"] = "https://example.invalid/jobs/%s%s" % (row["id"], tail)
    if row.get("description_markdown"):
        body = HOSTILE + ("Responsibilities and requirements. " * 120)
        row["description_markdown"] = body[:len(row["description_markdown"])] or body
    if row.get("apply_url"):
        row["apply_url"] = "https://example.invalid/apply/%s" % row["id"]
    return row


def main(src, dst):
    doc = json.load(open(src))
    data = doc.get("data")
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        for i, row in enumerate(data["results"]):
            scrub_row(row, i)
        q = data.get("query") or {}
        for k in ("keywords", "location"):
            if q.get(k):
                q[k] = "scrubbed"
    elif isinstance(data, dict):
        scrub_row(data, 0)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    assert not re.search(r"linkedin\.com/jobs/view|ashbyhq\.com/[a-z]", text), "an id survived"
    open(dst, "w").write(text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

```sh
for n in search.linkedin search.ashby search.zero detail.error; do
  python3 ../../scrub.py raw.$n.json $n.json && rm raw.$n.json
done
cd -
```

`description_markdown` comes out of this **better** than the live text: it is built to contain a `"`, a `\`, a tab, a newline and a `{`, so Task 2's byte-exactness assertion is exercising the string handling on purpose rather than by luck. The length band is preserved, so §9's storage arithmetic still describes the fixtures.

Then hand-write the bad-row fixture:

```json
{
  "data": {
    "results": [
      { "id": "jp_x", "title": "No id row", "source_url": "https://example.invalid/x" }
    ]
  }
}
```

Save it as `tests/fixtures/api-responses/search.badrow.json`. It is missing `source` and `source_id`.

Finally, run the two Task 0 tests that were waiting on a fixture:

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k "compacted or error_body" -v`

- [ ] **Step 2: Write the failing tests**

```python
RECORD_API = RUN_SCRIPTS / "record-api-response.sh"
FIXTURES = ROOT / "tests" / "fixtures" / "api-responses"
RID = "2026-08-05T16-47-00Z"


def run_script(script, *args, shell="sh", env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([shell, str(script), *[str(a) for a in args]],
                          capture_output=True, text=True, env=e)


def lines(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def api_rows(name):
    return json.loads((FIXTURES / name).read_text())["data"]["results"]


def record_search(jobs, fixture, query_id="q"):
    return run_script(RECORD_API, RID, jobs, FIXTURES / fixture,
                      "--route", "search-jobs", "--query-id", query_id)


def test_a_search_response_surfaces_one_event_per_row(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = record_search(jobs, "search.linkedin.json", "strategic-finance-sf")
    assert r.returncode == 0, r.stderr
    api = api_rows("search.linkedin.json")
    surfaced = [e for e in lines(jobs) if e["event"] == "surfaced"]
    assert len(surfaced) == len(api)
    assert {e["posting_id_at_seen"] for e in surfaced} == {row["id"] for row in api}


def test_surfaced_values_equal_the_api_values(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    record_search(jobs, "search.ashby.json")
    api = {row["id"]: row for row in api_rows("search.ashby.json")}
    for e in [x for x in lines(jobs) if x["event"] == "surfaced"]:
        row = api[e["posting_id_at_seen"]]
        for key in ("title", "company_name", "location_display", "source_url", "source_id",
                    "salary_display", "employment_type", "is_remote", "workplace_type",
                    "department_name", "team_name"):
            assert e[key] == row.get(key), (e["posting_id_at_seen"], key)


def test_posted_at_takes_whichever_date_field_the_source_filled(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    api = {}
    for name in ("search.linkedin.json", "search.ashby.json"):
        record_search(jobs, name)
        for row in api_rows(name):
            api[row["id"]] = row
    for e in [x for x in lines(jobs) if x["event"] == "surfaced"]:
        row = api[e["posting_id_at_seen"]]
        p, q = row.get("posted_at"), row.get("published_at")
        assert e["posted_at"] == (max(p, q) if p and q else (p or q))


def test_an_error_response_fails_loudly_and_appends_no_rows(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = record_search(jobs, "detail.error.json")
    assert r.returncode == 1
    assert "validation_error" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "surfaced"] == []


def test_an_error_response_records_the_call_with_its_code_and_retryable(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, RID, jobs, FIXTURES / "detail.error.json", "--route", "get-posting")
    calls = [e for e in lines(jobs) if e["event"] == "call"]
    assert len(calls) == 1
    assert calls[0]["ok"] is False
    assert calls[0]["route"] == "get-posting"      # the route is passed in, not guessed
    assert calls[0]["error_code"] == "validation_error"
    assert calls[0]["retryable"] is False
    assert calls[0]["request_id"].startswith("req_")


def test_a_successful_call_records_its_request_id_from_meta(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    record_search(jobs, "search.linkedin.json")
    call = [e for e in lines(jobs) if e["event"] == "call"][0]
    meta = json.loads((FIXTURES / "search.linkedin.json").read_text()).get("meta", {})
    assert call["request_id"] == meta.get("request_id")


def test_a_zero_row_search_is_not_a_failure(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = record_search(jobs, "search.zero.json")
    assert r.returncode == 0, r.stderr
    call = [e for e in lines(jobs) if e["event"] == "call"][0]
    assert call["ok"] is True and call["rows_returned"] == 0


def test_a_row_missing_source_id_appends_nothing_and_names_it(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = record_search(jobs, "search.badrow.json")
    assert r.returncode == 1
    assert "source_id" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "surfaced"] == []


def test_a_non_string_id_is_refused_at_ingestion(tmp_path):
    """Every script that finds a posting greps for the quoted form, so a numeric id would be
    surfaced and then unreachable. Refuse it where it arrives, not three scripts later."""
    bad = tmp_path / "numeric.json"
    bad.write_text(json.dumps({"data": {"results": [
        {"source": "linkedin", "source_id": 4449006488, "id": "jp_x",
         "source_url": "https://example.invalid/x"}]}}))
    r = run_script(RECORD_API, RID, tmp_path / "jobs.jsonl", bad, "--route", "search-jobs")
    assert r.returncode == 1
    assert "source_id" in r.stderr


def test_a_response_that_does_not_match_the_route_is_refused(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "search.linkedin.json", "--route", "get-posting")
    assert r.returncode == 2
    assert "get-posting" in r.stderr


def test_the_same_posting_from_two_queries_is_surfaced_once(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    n = len(api_rows("search.linkedin.json"))
    record_search(jobs, "search.linkedin.json", "a")
    record_search(jobs, "search.linkedin.json", "b")
    keys = [(e["source"], e["source_id"]) for e in lines(jobs) if e["event"] == "surfaced"]
    assert len(keys) == len(set(keys)) == n
    calls = [e for e in lines(jobs) if e["event"] == "call"]
    assert calls[1]["rows_returned"] == n and calls[1]["rows_new"] == 0


def test_a_posting_already_judged_in_an_earlier_run_is_not_surfaced_again(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    api = api_rows("search.linkedin.json")
    known = api[0]
    jobs.write_text(
        '{"event":"evaluated","run_id":"2026-01-01T00-00-00Z","source":"%s",'
        '"source_id":"%s","detail_read":true,"relevant":false,"match":null}\n'
        % (known["source"], known["source_id"]))
    record_search(jobs, "search.linkedin.json")
    surfaced = [e for e in lines(jobs) if e["event"] == "surfaced"]
    assert known["source_id"] not in {e["source_id"] for e in surfaced}
    assert len(surfaced) == len(api) - 1
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k record_api -v`
Expected: every test errors — `record-api-response.sh` does not exist.

- [ ] **Step 4: Write the script**

```sh
#!/bin/sh
# record-api-response.sh — turn one agent-data response into the events it implies.
#
# Usage: record-api-response.sh <run_id> <jobs.jsonl> <response.json> \
#          --route search-jobs|get-posting [--query-id ID] [--source S]
#
# A search-jobs response appends one `call` event and one `surfaced` event per new row, each value
# copied as the raw JSON it arrived as. A posting already judged in any run, and a posting this run
# already surfaced, are both skipped: one opening reached by two queries is one posting.
#
# The route is given, never guessed from the body. An error body carries no results and no
# description, so a response cannot say which route produced it, and guessing files every failed
# detail read under searches.
#
# The `call` event is written for every attempt — a failed one and a repeat one included. It is the
# record that the call happened, and what a run's metered-call count is worked out from. The rows
# are all-or-nothing: a response with one unusable row appends none of its rows.
#
# A failed call writes its body to stderr and exits 1, so the caller captures it with `2>` and
# hands that file here.
#
# This is the scripted form of the model-run prose contract; that prose remains the no-runtime
# fallback, and a host with no shell states that its counts were worked out by hand.
#
# Exit 0: the rows were appended, or the search legitimately returned none.
# Exit 1: no rows appended; stderr names the problem. The call event is still recorded.
# Exit 2: bad arguments, a missing file, or a body that is not what --route says it is.
set -u

here=$(dirname "$0")

usage() {
  printf 'usage: record-api-response.sh <run_id> <jobs.jsonl> <response.json> --route search-jobs|get-posting [--query-id ID] [--source S]\n' >&2
}

[ $# -ge 3 ] || { usage; exit 2; }
run_id=$1; jobs=$2; resp=$3; shift 3
route='' query_id='' src_flag=''
while [ $# -gt 0 ]; do
  case $1 in
    --route)    [ $# -ge 2 ] || { usage; exit 2; }; route=$2; shift 2 ;;
    --query-id) [ $# -ge 2 ] || { usage; exit 2; }; query_id=$2; shift 2 ;;
    --source)   [ $# -ge 2 ] || { usage; exit 2; }; src_flag=$2; shift 2 ;;
    *) printf 'record-api-response.sh: unknown option %s\n' "$1" >&2; usage; exit 2 ;;
  esac
done
case $route in
  search-jobs|get-posting) ;;
  *) printf 'record-api-response.sh: --route must be search-jobs or get-posting\n' >&2; exit 2 ;;
esac

[ -f "$resp" ] || { printf 'record-api-response.sh: no such file: %s\n' "$resp" >&2; exit 2; }
dir=$(dirname "$jobs"); [ -d "$dir" ] || mkdir -p "$dir"
[ -f "$jobs" ] || : > "$jobs"

scan=$(mktemp) || exit 2
new=$(mktemp) || exit 2
bad=$(mktemp) || exit 2
keep=$(mktemp) || exit 2
trap 'rm -f "$scan" "$new" "$bad" "$keep" "$bad.count"' EXIT INT HUP TERM

ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# One `call` event per attempt. Defined before anything can fail, so a failure still leaves it.
emit_call() {
  RAR_QUERY=$query_id RAR_REQ=${req:-} RAR_CODE=${code:-} \
  awk -v run_id="$run_id" -v ts="$ts" -v route="$route" -v source="$1" \
      -v ok="$2" -v returned="$3" -v new="$4" -v retryable="${retryable:-}" '
    function esc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return s }
    function jstr(s) { return "\"" esc(s) "\"" }
    function jopt(s) { return s == "" ? "null" : jstr(s) }
    BEGIN {
      out = "{\"event\":\"call\",\"run_id\":" jstr(run_id) ",\"ts\":" jstr(ts)
      out = out ",\"route\":" jstr(route)
      out = out ",\"source\":" jopt(source)
      out = out ",\"query_id\":" jopt(ENVIRON["RAR_QUERY"])
      out = out ",\"ok\":" ok
      out = out ",\"rows_returned\":" returned ",\"rows_new\":" new
      out = out ",\"error_code\":" jopt(ENVIRON["RAR_CODE"])
      out = out ",\"retryable\":" (retryable == "" ? "null" : retryable)
      out = out ",\"request_id\":" jopt(ENVIRON["RAR_REQ"])
      out = out "}"
      print out
    }' >> "$jobs"
}

# Scan once. A body we cannot parse is still a call that happened.
if ! awk -f "$here/json-scan.awk" "$resp" > "$scan" 2>/dev/null; then
  emit_call "$src_flag" false 0 0
  printf 'record-api-response.sh: %s is not well-formed JSON — the call is recorded, nothing else\n' \
    "$resp" >&2
  exit 1
fi

field() { awk -F'\t' -v p="$1" '$1 == p { print $2; exit }' "$scan" | sed 's/^"//; s/"$//'; }
haspath() { awk -F'\t' -v p="$1" '$1 ~ p { found = 1; exit } END { exit !found }' "$scan"; }

# An error body: a top-level `error` object. error.source is "service", never a job source.
if [ -n "$(field error.code)" ]; then
  code=$(field error.code)
  msg=$(field error.message)
  retryable=$(field error.retryable)
  req=$(field error.request_id)
  emit_call "$src_flag" false 0 0
  printf 'record-api-response.sh: the response is an error, not results: %s — %s (retryable %s)\n' \
    "${code:-unknown}" "${msg:-no message}" "${retryable:-unknown}" >&2
  exit 1
fi

req=$(field meta.request_id)

if [ "$route" = get-posting ]; then
  # Task 2 owns this branch.
  . "$here/record-api-response.posting.inc" 2>/dev/null || true
fi

# A search body carries data.query and, when it found anything, data.results[].
haspath '^data\.query\.' || {
  printf 'record-api-response.sh: %s carries no data.query — it is not a search-jobs response\n' \
    "$resp" >&2
  exit 2
}

awk -F'\t' -v run_id="$run_id" -v query_id="$query_id" -v ts="$ts" -v badfile="$bad" '
  function esc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return s }
  function fld(k) { return (k in v && v[k] != "") ? v[k] : "null" }
  function isstr(k) { return (k in v) && substr(v[k], 1, 1) == "\"" }

  # Only a row own field: data.results.<n>.<key>, four segments and no more. A nested object
  # inside a row has five and cannot overwrite the row it sits in.
  $1 ~ /^data\.results\.[0-9]+\.[^.]+$/ {
    split($1, p, ".")
    if (p[3] != cur) { if (open) emit(); cur = p[3]; open = 1; delete v }
    v[p[4]] = $2
  }
  END { if (open) emit(); print rows+0 > (badfile ".count") }

  function emit(   out, pd, pb, eff, missing, notstr, k, i, req) {
    rows++
    split("source source_id id source_url", req, " ")
    missing = ""; notstr = ""
    for (i = 1; i <= 4; i++) {
      k = req[i]
      if (!(k in v) || v[k] == "" || v[k] == "null")
        missing = missing (missing == "" ? "" : ", ") k
      else if (!isstr(k))
        notstr = notstr (notstr == "" ? "" : ", ") k
    }
    if (missing != "" || notstr != "") {
      if (missing != "")
        printf "row %d is missing %s (title %s, company %s)\n", rows, missing,
               (("title" in v) ? v["title"] : "absent"),
               (("company_name" in v) ? v["company_name"] : "absent") >> badfile
      if (notstr != "")
        printf "row %d has a non-string %s — every script that finds a posting matches the quoted form, so this row would be surfaced and then unreachable\n",
               rows, notstr >> badfile
      delete v
      return
    }

    pd = v["posted_at"]; pb = v["published_at"]; eff = "null"
    if (pd != "" && pd != "null" && pb != "" && pb != "null") eff = (pd > pb ? pd : pb)
    else if (pd != "" && pd != "null") eff = pd
    else if (pb != "" && pb != "null") eff = pb

    out = "{\"event\":\"surfaced\""
    out = out ",\"run_id\":\"" esc(run_id) "\""
    out = out ",\"query_id\":\"" esc(query_id) "\""
    out = out ",\"source\":" fld("source")
    out = out ",\"source_id\":" fld("source_id")
    out = out ",\"posting_id_at_seen\":" fld("id")
    out = out ",\"source_url\":" fld("source_url")
    out = out ",\"title\":" fld("title")
    out = out ",\"company_name\":" fld("company_name")
    out = out ",\"location_display\":" fld("location_display")
    out = out ",\"salary_display\":" fld("salary_display")
    out = out ",\"employment_type\":" fld("employment_type")
    out = out ",\"department_name\":" fld("department_name")
    out = out ",\"team_name\":" fld("team_name")
    out = out ",\"is_remote\":" fld("is_remote")
    out = out ",\"workplace_type\":" fld("workplace_type")
    out = out ",\"posted_at\":" eff
    out = out ",\"detail_available\":" fld("detail_available")
    out = out ",\"ts\":\"" esc(ts) "\""
    out = out "}"
    print out
    delete v
  }
' "$scan" > "$new"

returned=$(cat "$bad.count" 2>/dev/null || echo 0)
src=$(head -1 "$new" 2>/dev/null | sed -n 's/.*"source":"\([^"]*\)".*/\1/p')
[ -n "$src" ] || src=$src_flag

if [ -s "$bad" ]; then
  emit_call "$src" true "$returned" 0
  printf 'record-api-response.sh: nothing was appended — %s\n' "$resp" >&2
  sed 's/^/record-api-response.sh:   /' "$bad" >&2
  exit 1
fi

# Skip a posting this run already surfaced, and one any run has already judged. The judged check
# is deliberately not scoped to this run: a posting with a verdict is not offered again.
awk -f "$here/event-field.awk" -f - -v jobs="$jobs" -v run_id="$run_id" "$new" > "$keep" <<'AWKEOF'
BEGIN {
  while ((getline line < jobs) > 0) {
    ev = jval(line, "event")
    k = jval(line, "source") "|" jval(line, "source_id")
    if (ev == "surfaced" && jval(line, "run_id") == run_id) have[k] = 1
    else if (ev == "evaluated") have[k] = 1
  }
  close(jobs)
}
{
  k = jval($0, "source") "|" jval($0, "source_id")
  if (k in have) next
  have[k] = 1
  print
}
AWKEOF

kept=$(wc -l < "$keep" | tr -d ' ')
emit_call "$src" true "$returned" "$kept"
[ "$kept" -gt 0 ] && cat "$keep" >> "$jobs"
printf 'record-api-response.sh: %s rows appended, %s rows in the response\n' "$kept" "$returned" >&2
exit 0
```

Two notes for whoever implements this. `awk -f event-field.awk -f -` reads the second program from stdin, which is how a script keeps a here-document program while still combining it with the library; verify it under `dash` in Step 6, and if `-f -` is not accepted, put that program in `skills/job-search-run/scripts/dedup-surfaced.awk` and reference it by path. And the `record-api-response.posting.inc` line is a placeholder that Task 2 replaces with the real branch — leave it out entirely until Task 2, since `--route get-posting` is not supported yet and the route check already rejects the mismatch.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k record_api -v`
Expected: all thirteen PASS, except the two `get-posting` ones Task 2 finishes — name them if they are still red.

- [ ] **Step 6: Verify it runs under `sh` and `dash`**

Run: `sh -n skills/job-search-run/scripts/record-api-response.sh && command -v dash >/dev/null && dash -n skills/job-search-run/scripts/record-api-response.sh; echo "syntax ok"`
Then re-run the suite with `shell="dash"` for at least one test, to prove `awk -f … -f -` works there.

- [ ] **Step 7: Commit**

```bash
git add skills/job-search-run/scripts/record-api-response.sh tests/test_mechanics_scripts.py \
        tests/fixtures/scrub.py tests/fixtures/api-responses/
git commit -m "feat(run): record every row a search returns, before anything judges it"
```

---

### Task 2: `record-api-response.sh` — posting responses

**Files:**
- Modify: `skills/job-search-run/scripts/record-api-response.sh`
- Create: `tests/fixtures/api-responses/detail.ashby.json`, `detail.linkedin.json`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `record-api-response.sh` from Task 1.
- Produces: the same command with `--route get-posting` appends one `call` event and one `detail` event. A posting this run did not surface is refused. A posting already carrying a `detail` event for this run is reported and skipped with exit 0 — **and its call is still recorded**, because the caller paid for it.

- [ ] **Step 1: Capture the detail fixtures, then scrub them**

Take the `id` and `source_url` from the same row of a **raw** capture — the pair must be the one the API issued, and the scrub replaces both. Capture before scrubbing the search fixtures, or re-capture the two rows.

```sh
L=f9a6ec16-0bfd-44d8-b3ee-073776745ee7
cd tests/fixtures/api-responses
python3 -c "
import json
for name in ('linkedin', 'ashby'):
    rows = json.load(open('raw.search.%s.json' % name))['data']['results']
    print(name, rows[0]['id'], rows[0]['source_url'])
"
# then, for each printed line:
agent-data call $L get-posting --posting_id <id> --source_url "<source_url>" --source <src> \
  > raw.detail.<src>.json
python3 ../../scrub.py raw.detail.<src>.json detail.<src>.json && rm raw.detail.<src>.json
cd -
```

The scrub gives each detail fixture the same `source_id` the corresponding scrubbed search row got, so a test can seed the log from the search fixture and then store the detail against it. Confirm that before writing the tests:

```sh
python3 -c "
import json
for s in ('linkedin','ashby'):
    d = json.load(open('tests/fixtures/api-responses/detail.%s.json' % s))['data']
    rows = json.load(open('tests/fixtures/api-responses/search.%s.json' % s))['data']['results']
    assert d['source_id'] in {r['source_id'] for r in rows}, s
print('detail fixtures line up with their search fixtures')
"
```

- [ ] **Step 2: Write the failing tests**

```python
def seeded_jobs(tmp_path, search_fixture):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    record_search(jobs, search_fixture)
    return jobs


def record_detail(jobs, fixture):
    return run_script(RECORD_API, RID, jobs, FIXTURES / fixture, "--route", "get-posting")


def test_a_detail_response_stores_the_description_byte_exact(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    r = record_detail(jobs, "detail.ashby.json")
    assert r.returncode == 0, r.stderr
    stored = [e for e in lines(jobs) if e["event"] == "detail"]
    assert len(stored) == 1
    original = json.loads((FIXTURES / "detail.ashby.json").read_text())["data"]
    assert stored[0]["description_markdown"] == original["description_markdown"]
    assert stored[0]["apply_url"] == original.get("apply_url")


def test_a_description_carrying_every_hostile_character_round_trips(tmp_path):
    """The scrubbed description holds a quote, a backslash, a brace, a tab and a newline on
    purpose. If any of them moves, this is the test that says so."""
    original = json.loads((FIXTURES / "detail.ashby.json").read_text())["data"]["description_markdown"]
    for ch in ('"', "\\", "{", "\t", "\n"):
        assert ch in original, ch
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    record_detail(jobs, "detail.ashby.json")
    stored = [e for e in lines(jobs) if e["event"] == "detail"][0]
    assert stored["description_markdown"] == original


def test_linkedin_detail_stores_byte_exact_too(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    record_detail(jobs, "detail.linkedin.json")
    stored = [e for e in lines(jobs) if e["event"] == "detail"][0]
    original = json.loads((FIXTURES / "detail.linkedin.json").read_text())["data"]
    assert stored["description_markdown"] == original["description_markdown"]


def test_a_detail_for_a_posting_this_run_never_surfaced_is_refused(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = record_detail(jobs, "detail.ashby.json")
    assert r.returncode == 1
    assert "no surfaced posting" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "detail"] == []


def test_storing_the_same_detail_twice_is_reported_and_still_records_the_call(tmp_path):
    """The caller made a metered call before handing the response here. agent_data_usage is a
    count of call events, so a call it does not count is a call the record undersells."""
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    record_detail(jobs, "detail.ashby.json")
    before = lines(jobs)
    r = record_detail(jobs, "detail.ashby.json")
    assert r.returncode == 0
    assert "already stored" in r.stderr
    after = lines(jobs)
    assert len(after) == len(before) + 1
    assert after[-1]["event"] == "call" and after[-1]["route"] == "get-posting"
    assert after[-1]["ok"] is True and after[-1]["rows_new"] == 0
    assert len([e for e in after if e["event"] == "detail"]) == 1


def test_a_detail_read_records_its_call(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    record_detail(jobs, "detail.ashby.json")
    calls = [e for e in lines(jobs) if e["event"] == "call" and e["route"] == "get-posting"]
    assert len(calls) == 1 and calls[0]["ok"] is True
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k detail -v`
Expected: FAIL — the script only handles search responses.

- [ ] **Step 4: Add the posting branch**

Replace the `if [ "$route" = get-posting ]; then … fi` placeholder in `record-api-response.sh` with the real branch. It sits after the error handling and the `req=$(field meta.request_id)` line, so a failed detail read has already been recorded and returned.

```sh
if [ "$route" = get-posting ]; then
  # A posting body carries the posting's own fields under data, with no results array.
  haspath '^data\.source_id$' || {
    printf 'record-api-response.sh: %s carries no data.source_id — it is not a get-posting response\n' \
      "$resp" >&2
    exit 2
  }

  dsrc=$(field data.source)
  dsid=$(field data.source_id)
  [ -n "$dsrc" ] && [ -n "$dsid" ] || {
    printf 'record-api-response.sh: %s carries no source and source_id\n' "$resp" >&2
    exit 2
  }

  # Every posting this run stores must be one a search surfaced for it.
  if ! grep -F '"event":"surfaced"' "$jobs" \
       | grep -F "\"run_id\":\"$run_id\"" \
       | grep -F "\"source\":\"$dsrc\"" \
       | grep -qF "\"source_id\":\"$dsid\""; then
    emit_call "$dsrc" true 1 0
    printf 'record-api-response.sh: no surfaced posting for %s:%s in run %s\n' \
      "$dsrc" "$dsid" "$run_id" >&2
    exit 1
  fi

  # Already stored: nothing new to write, but the call was still made and still billed.
  if grep -F '"event":"detail"' "$jobs" \
       | grep -F "\"run_id\":\"$run_id\"" \
       | grep -F "\"source\":\"$dsrc\"" \
       | grep -qF "\"source_id\":\"$dsid\""; then
    emit_call "$dsrc" true 1 0
    printf 'record-api-response.sh: %s:%s already stored for this run — the call is recorded, nothing else\n' \
      "$dsrc" "$dsid" >&2
    exit 0
  fi

  # data own fields only: two segments, so a nested object under data cannot reach the event.
  awk -F'\t' -v run_id="$run_id" -v ts="$ts" '
    function esc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return s }
    function fld(k) { return (k in v && v[k] != "") ? v[k] : "null" }
    $1 ~ /^data\.[^.]+$/ { split($1, p, "."); v[p[2]] = $2 }
    END {
      out = "{\"event\":\"detail\",\"run_id\":\"" esc(run_id) "\""
      out = out ",\"source\":" fld("source")
      out = out ",\"source_id\":" fld("source_id")
      out = out ",\"description_markdown\":" fld("description_markdown")
      out = out ",\"employment_type\":" fld("employment_type")
      out = out ",\"apply_url\":" fld("apply_url")
      out = out ",\"is_listed\":" fld("is_listed")
      out = out ",\"is_remote\":" fld("is_remote")
      out = out ",\"workplace_type\":" fld("workplace_type")
      out = out ",\"staleness_status\":" fld("staleness_status")
      out = out ",\"ts\":\"" esc(ts) "\""
      out = out "}"
      print out
    }
  ' "$scan" > "$new"

  [ -s "$new" ] || {
    emit_call "$dsrc" true 1 0
    printf 'record-api-response.sh: built an empty detail event for %s:%s\n' "$dsrc" "$dsid" >&2
    exit 1
  }

  emit_call "$dsrc" true 1 1
  cat "$new" >> "$jobs"
  printf 'record-api-response.sh: stored %s:%s\n' "$dsrc" "$dsid" >&2
  exit 0
fi
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k "record_api or detail" -v`
Expected: all PASS, Task 1's tests included.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search-run/scripts/record-api-response.sh tests/test_mechanics_scripts.py \
        tests/fixtures/api-responses/
git commit -m "feat(run): store a posting's full text on its own event, and count the call either way"
```

---

### Task 3: `queue-detail-read.sh` and `list-detail-read-queue.sh`

**Files:**
- Create: `skills/job-search-run/scripts/queue-detail-read.sh`, `skills/job-search-run/scripts/list-detail-read-queue.sh`, `skills/job-search-run/scripts/list-detail-read-queue.awk`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `surfaced` events from Task 1; `event-field.awk` from Task 0.
- Produces: `queue-detail-read.sh <jobs.jsonl> --run-id ID --source S --source-id ID` appends a `queued` event. `list-detail-read-queue.sh <jobs.jsonl> <run_id>` prints one tab-separated line per queued, not-yet-judged posting: `source`, `source_id`, `posting_id_at_seen`, `source_url`, `title`, `company_name`.

**Nothing about the expected judgment enters the queue.** A provisional band would anchor the reader before it has read anything, and a named question would become the scope of its answer. `evaluate-job-fit` already owns the open question and places it with the reader that has the posting in front of it.

- [ ] **Step 1: Write the failing tests**

```python
QUEUE = RUN_SCRIPTS / "queue-detail-read.sh"
LIST_QUEUE = RUN_SCRIPTS / "list-detail-read-queue.sh"


def first_surfaced(jobs):
    return [e for e in lines(jobs) if e["event"] == "surfaced"][0]


def test_queueing_records_only_that_the_posting_is_to_be_read(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(QUEUE, jobs, "--run-id", RID, "--source", row["source"],
                   "--source-id", row["source_id"])
    assert r.returncode == 0, r.stderr
    q = [e for e in lines(jobs) if e["event"] == "queued"]
    assert len(q) == 1
    assert set(q[0]) == {"event", "run_id", "source", "source_id", "ts"}


def test_queueing_a_posting_no_search_surfaced_is_refused(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    r = run_script(QUEUE, jobs, "--run-id", RID, "--source", "linkedin",
                   "--source-id", "not-a-real-id")
    assert r.returncode == 1
    assert "no surfaced posting" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "queued"] == []


def test_queueing_twice_is_reported_and_appends_nothing(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    args = (jobs, "--run-id", RID, "--source", row["source"], "--source-id", row["source_id"])
    run_script(QUEUE, *args)
    before = len(lines(jobs))
    r = run_script(QUEUE, *args)
    assert r.returncode == 0 and "already queued" in r.stderr
    assert len(lines(jobs)) == before


def test_the_queue_carries_what_a_reader_needs_and_nothing_that_prejudges(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(QUEUE, jobs, "--run-id", RID, "--source", row["source"],
               "--source-id", row["source_id"])
    r = run_script(LIST_QUEUE, jobs, RID)
    assert r.returncode == 0, r.stderr
    fields = r.stdout.rstrip("\n").split("\t")
    assert fields == [row["source"], row["source_id"], row["posting_id_at_seen"],
                      row["source_url"], row["title"], row["company_name"]]


def test_a_title_with_an_escaped_quote_reaches_the_reader_intact(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"surfaced","run_id":"%s","source":"ashby","source_id":"a",'
        '"posting_id_at_seen":"jp_1","source_url":"https://example.invalid/1",'
        '"title":"Manager \\"Finance\\" role","company_name":"Globex"}\n'
        '{"event":"queued","run_id":"%s","source":"ashby","source_id":"a","ts":"x"}\n' % (RID, RID))
    r = run_script(LIST_QUEUE, jobs, RID)
    assert r.stdout.rstrip("\n").split("\t")[4] == 'Manager "Finance" role'


def test_the_queue_drains_as_judgments_land(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"][:3]
    for row in rows:
        run_script(QUEUE, jobs, "--run-id", RID, "--source", row["source"],
                   "--source-id", row["source_id"])
    assert len(run_script(LIST_QUEUE, jobs, RID).stdout.strip().splitlines()) == 3
    jobs.write_text(jobs.read_text() +
        '{"event":"evaluated","run_id":"%s","source":"%s","source_id":"%s",'
        '"detail_read":true,"relevant":true,"match":"strong"}\n'
        % (RID, rows[0]["source"], rows[0]["source_id"]))
    assert len(run_script(LIST_QUEUE, jobs, RID).stdout.strip().splitlines()) == 2


def test_an_empty_queue_prints_nothing_and_succeeds(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    r = run_script(LIST_QUEUE, jobs, RID)
    assert r.returncode == 0 and r.stdout == ""
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k "queue" -v`
Expected: FAIL — neither script exists.

- [ ] **Step 3: Write `queue-detail-read.sh`**

```sh
#!/bin/sh
# queue-detail-read.sh — mark one posting as one to read in full.
#
# Usage: queue-detail-read.sh <jobs.jsonl> --run-id ID --source S --source-id ID [--ts TS]
#
# Records one fact and no more: this posting is to be read. It carries nothing about the expected
# judgment — a provisional band would anchor the reader before it has read anything, and a named
# question would become the scope of its answer. The open question a read has to settle is the
# reader's to derive from the posting, and lives in the reasoning it writes.
#
# The point of the script is that a posting is marked without editing jobs.jsonl by hand, and the
# list of what is still to read survives outside any one agent's context.
#
# Exit 0: queued, or already queued for this run.
# Exit 1: nothing written; stderr names the problem.
set -u

jobs=${1:?usage: queue-detail-read.sh <jobs.jsonl> --run-id ID --source S --source-id ID}
shift

run_id='' source='' source_id='' ts=''
die() { printf 'queue-detail-read: %s\n' "$1" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case $1 in
    --run-id)    run_id=${2?}; shift 2 ;;
    --source)    source=${2?}; shift 2 ;;
    --source-id) source_id=${2?}; shift 2 ;;
    --ts)        ts=${2?}; shift 2 ;;
    *) die "unknown option $1" ;;
  esac
done

[ -n "$run_id" ]    || die 'missing --run-id'
[ -n "$source" ]    || die 'missing --source'
[ -n "$source_id" ] || die 'missing --source-id'
[ -f "$jobs" ]      || die "no such file: $jobs"

grep -F '"event":"surfaced"' "$jobs" \
  | grep -F "\"run_id\":\"$run_id\"" \
  | grep -F "\"source\":\"$source\"" \
  | grep -qF "\"source_id\":\"$source_id\"" \
  || die "no surfaced posting for $source:$source_id in run $run_id"

if grep -F '"event":"queued"' "$jobs" \
     | grep -F "\"run_id\":\"$run_id\"" \
     | grep -F "\"source\":\"$source\"" \
     | grep -qF "\"source_id\":\"$source_id\""; then
  printf 'queue-detail-read: %s:%s is already queued for this run — nothing written\n' \
    "$source" "$source_id" >&2
  exit 0
fi

[ -n "$ts" ] || ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

awk -v run_id="$run_id" -v source="$source" -v source_id="$source_id" -v ts="$ts" '
  function esc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return s }
  function jstr(s) { return "\"" esc(s) "\"" }
  BEGIN {
    print "{\"event\":\"queued\",\"run_id\":" jstr(run_id) ",\"source\":" jstr(source) \
          ",\"source_id\":" jstr(source_id) ",\"ts\":" jstr(ts) "}"
  }' >> "$jobs"
```

- [ ] **Step 4: Write `list-detail-read-queue.sh` and its program**

```sh
#!/bin/sh
# list-detail-read-queue.sh — print the postings this run queued and has not judged yet.
#
# Usage: list-detail-read-queue.sh <jobs.jsonl> <run_id>
#
# One posting per line, tab-separated, carrying what a reader needs to fetch and judge it and
# nothing that pre-judges it:
#   source  source_id  posting_id_at_seen  source_url  title  company_name
#
# This is what the run hands out. The event log grows past what a context window holds, so nothing
# reads it directly to work out what is left to do.
set -u

here=$(dirname "$0")
jobs=${1:?usage: list-detail-read-queue.sh <jobs.jsonl> <run_id>}
run_id=${2:?usage: list-detail-read-queue.sh <jobs.jsonl> <run_id>}

[ -f "$jobs" ] || { printf 'list-detail-read-queue: no such file: %s\n' "$jobs" >&2; exit 2; }

exec awk -f "$here/event-field.awk" -f "$here/list-detail-read-queue.awk" -v want="$run_id" "$jobs"
```

```awk
# list-detail-read-queue.awk — see list-detail-read-queue.sh.
#
# Titles and company names are free text and come through jval, which resolves the escapes a real
# posting carries. A JSON string cannot hold a literal tab, so the six fields stay six fields.

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
```

The `evaluated` check is scoped to this run, matching `run-counts.sh` in Task 5. A posting judged in an earlier run is never surfaced for this one, so the scope changes nothing today; it keeps the three scripts saying the same thing if the dedup rule ever moves.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k "queue" -v`
Expected: all seven PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search-run/scripts/queue-detail-read.sh \
        skills/job-search-run/scripts/list-detail-read-queue.sh \
        skills/job-search-run/scripts/list-detail-read-queue.awk tests/test_mechanics_scripts.py
git commit -m "feat(run): track which postings are still to be read, without pre-judging them"
```

---

### Task 4: `record-judgment.sh`

**Files:**
- Create: `skills/job-search-run/scripts/record-judgment.sh`, `skills/job-search-run/scripts/record-judgment.awk`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `surfaced` events from Task 1; `event-field.awk` from Task 0.
- Produces: `record-judgment.sh <jobs.jsonl> --run-id ID --source S --source-id ID --detail-read true|false --relevant true|false [--match strong|moderate|weak] [--needs-human-check true|false] [--dealbreakers 'a;b'] [--unknowns 'a;b'] [--reasoning TEXT] [--same-role-as SOURCE:ID] [--posted-at-extracted DATE] [--ts TS]`. Appends one `evaluated` event. The script writes the JSON, so nothing the judgment says is escaped by the caller.

**The script copies five display fields off the `surfaced` event.** It already reads that event to prove the posting belongs to this run, so `title`, `company_name`, `location_display`, `source_url` and `posted_at` come across for free. The model supplies none of them. They are on the judgment because the digest lists postings by title and company, and because the home view resolves "I applied at Globex" to a `source_id` without opening a log that grows past a context window. They are spliced in as the raw JSON they already are — never unescaped and re-escaped, so a title carrying `\"` stays byte-exact.

- [ ] **Step 1: Write the failing tests**

```python
JUDGE = RUN_SCRIPTS / "record-judgment.sh"

HOSTILE = 'He said "it\'s a \\"strong\\" fit" — path C:\\temp\ttab\nand a newline.'


def judge_args(jobs, row, **kw):
    args = [jobs, "--run-id", RID, "--source", row["source"], "--source-id", row["source_id"]]
    for k, v in kw.items():
        args += ["--" + k.replace("_", "-"), v]
    return args


def test_a_judgment_lands_as_one_evaluated_event(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                      match="strong", reasoning="Clears every must-have."))
    assert r.returncode == 0, r.stderr
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"]
    assert len(ev) == 1
    assert ev[0]["match"] == "strong" and ev[0]["relevant"] is True
    assert ev[0]["dealbreakers_hit"] == [] and ev[0]["unknowns"] == []
    assert ev[0]["status"] == "new"


def test_the_display_fields_are_copied_off_the_surfaced_event(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true", match="strong"))
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    for key in ("title", "company_name", "location_display", "source_url", "posted_at"):
        assert ev[key] == row[key], key


def test_a_copied_title_with_an_escaped_quote_is_byte_exact(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"surfaced","run_id":"%s","source":"ashby","source_id":"a",'
        '"source_url":"https://example.invalid/1","title":"Manager \\"Finance\\" role",'
        '"company_name":"Globex","location_display":"Remote","posted_at":null}\n' % RID)
    run_script(JUDGE, jobs, "--run-id", RID, "--source", "ashby", "--source-id", "a",
               "--detail-read", "false", "--relevant", "false", "--reasoning", "No.")
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    assert ev["title"] == 'Manager "Finance" role'
    assert ev["posted_at"] is None


def test_the_dropped_fields_are_gone_on_purpose(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true", match="weak"))
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    for gone in ("first_seen", "salary_display", "query_id"):
        assert gone not in ev


def test_every_field_a_script_decides_on_comes_before_the_free_text(tmp_path):
    """The readers take a key's first occurrence, so reasoning holding the literal "status":
    must not be found before the real one."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true", match="strong",
                                  reasoning='It says "status": "closed" halfway down.'))
    raw = [l for l in jobs.read_text().splitlines() if '"event":"evaluated"' in l][0]
    for key in ('"status":', '"needs_human_check":', '"match":', '"relevant":'):
        assert raw.index(key) < raw.index('"reasoning":'), key
    ev = json.loads(raw)
    assert ev["status"] == "new"


def test_free_text_with_quotes_backslashes_tabs_and_newlines_round_trips(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                  match="strong", reasoning=HOSTILE,
                                  unknowns="equity;start date"))
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    assert ev["reasoning"] == HOSTILE
    assert ev["unknowns"] == ["equity", "start date"]


def test_relevant_true_without_a_band_is_refused(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true"))
    assert r.returncode == 1
    assert "strong|moderate|weak" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "evaluated"] == []


def test_relevant_false_carrying_a_band_is_refused(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="false",
                                      match="weak"))
    assert r.returncode == 1
    assert [e for e in lines(jobs) if e["event"] == "evaluated"] == []


def test_an_invented_band_is_refused(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                      match="excellent"))
    assert r.returncode == 1


def test_a_judgment_about_a_posting_no_search_surfaced_is_refused(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    r = run_script(JUDGE, jobs, "--run-id", RID, "--source", "linkedin",
                   "--source-id", "jp_INVENTED", "--detail-read", "true",
                   "--relevant", "true", "--match", "strong")
    assert r.returncode == 1
    assert "no surfaced posting" in r.stderr


def test_the_same_judgment_twice_is_reported_and_skipped(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    base = dict(detail_read="true", relevant="true", match="strong", reasoning="Same.")
    run_script(JUDGE, *judge_args(jobs, row, ts="2026-08-05T00:00:00Z", **base))
    before = len(lines(jobs))
    r = run_script(JUDGE, *judge_args(jobs, row, ts="2026-08-05T09:30:30Z", **base))
    assert r.returncode == 0 and "already carries this verdict" in r.stderr
    assert len(lines(jobs)) == before


def test_a_different_judgment_for_the_same_posting_is_refused_with_both_lines(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                  match="strong", reasoning="First."))
    before = len(lines(jobs))
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                      match="weak", reasoning="Changed my mind."))
    assert r.returncode == 1
    assert "recorded:" in r.stderr and "offered:" in r.stderr
    assert len(lines(jobs)) == before


def test_concurrent_judgments_all_land_as_valid_json(tmp_path):
    """Readers run in parallel where the host has subagents; appends must not interleave."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    procs = [subprocess.Popen(
        ["sh", str(JUDGE), str(jobs), "--run-id", RID, "--source", row["source"],
         "--source-id", row["source_id"], "--detail-read", "true", "--relevant", "false",
         "--reasoning", "Outside the brief."],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for row in rows]
    for p in procs:
        p.wait()
    parsed = lines(jobs)   # raises on any interleaved or truncated line
    assert len([e for e in parsed if e["event"] == "evaluated"]) == len(rows)
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k judgment -v`
Expected: FAIL — the script does not exist.

- [ ] **Step 3: Write `record-judgment.sh`**

```sh
#!/bin/sh
# record-judgment.sh — record one posting's judgment.
#
# Usage: record-judgment.sh <jobs.jsonl> --run-id ID --source S --source-id ID \
#          --detail-read true|false --relevant true|false [--match strong|moderate|weak] \
#          [--needs-human-check true|false] [--dealbreakers 'a;b'] [--unknowns 'a;b'] \
#          [--reasoning TEXT] [--same-role-as SOURCE:ID] [--posted-at-extracted DATE] [--ts TS]
#
# The script writes the JSON, so nothing the judgment says has to be escaped by whoever is calling.
# A judgment can only be about a posting a search surfaced for this run, and the title, company,
# location, URL and date come off that surfaced event rather than from the caller.
#
# A semicolon separates one dealbreaker or unknown from the next, so a dealbreaker that contains a
# semicolon has to be reworded.
#
# Exit 0: recorded, or this posting already carries exactly this judgment.
# Exit 1: nothing written; stderr names the problem.
set -u

here=$(dirname "$0")
jobs=${1:?usage: record-judgment.sh <jobs.jsonl> --run-id ID --source S --source-id ID ...}
shift

run_id='' source='' source_id='' detail_read='' relevant='' band=''
nhc=false dealbreakers='' unknowns='' reasoning='' same_role='' posted_extracted='' ts=''

die() { printf 'record-judgment: %s\n' "$1" >&2; exit 1; }

line=$(mktemp) || exit 2
trap 'rm -f "$line"' EXIT INT HUP TERM

while [ $# -gt 0 ]; do
  case $1 in
    --run-id)              run_id=${2?}; shift 2 ;;
    --source)              source=${2?}; shift 2 ;;
    --source-id)           source_id=${2?}; shift 2 ;;
    --detail-read)         detail_read=${2?}; shift 2 ;;
    --relevant)            relevant=${2?}; shift 2 ;;
    --match)               band=${2?}; shift 2 ;;
    --needs-human-check)   nhc=${2?}; shift 2 ;;
    --dealbreakers)        dealbreakers=${2?}; shift 2 ;;
    --unknowns)            unknowns=${2?}; shift 2 ;;
    --reasoning)           reasoning=${2?}; shift 2 ;;
    --same-role-as)        same_role=${2?}; shift 2 ;;
    --posted-at-extracted) posted_extracted=${2?}; shift 2 ;;
    --ts)                  ts=${2?}; shift 2 ;;
    *) die "unknown option $1" ;;
  esac
done

[ -n "$run_id" ]    || die 'missing --run-id'
[ -n "$source" ]    || die 'missing --source'
[ -n "$source_id" ] || die 'missing --source-id'
[ -f "$jobs" ]      || die "no such file: $jobs"

case $detail_read in true|false) ;; *) die '--detail-read must be true or false' ;; esac
case $relevant in true|false) ;; *) die '--relevant must be true or false' ;; esac
case $nhc in true|false) ;; *) die '--needs-human-check must be true or false' ;; esac

# A relevant posting carries a band; one that is not relevant carries none.
if [ "$relevant" = true ]; then
  case $band in
    strong|moderate|weak) ;;
    *) die '--relevant true needs --match strong|moderate|weak' ;;
  esac
else
  [ -z "$band" ] || die '--relevant false takes no --match'
fi

# The surfaced event proves the posting belongs to this run, and carries the five display fields.
surfaced=$(grep -F '"event":"surfaced"' "$jobs" \
           | grep -F "\"run_id\":\"$run_id\"" \
           | grep -F "\"source\":\"$source\"" \
           | grep -F "\"source_id\":\"$source_id\"" | tail -1)
[ -n "$surfaced" ] || die "no surfaced posting for $source:$source_id in run $run_id"

[ -n "$ts" ] || ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Free text and the whole surfaced line ride in the environment rather than through -v, which
# cannot carry a literal newline. `band` is not called `match`, which is an awk built-in.
RJ_REASONING=$reasoning RJ_DEALBREAKERS=$dealbreakers RJ_UNKNOWNS=$unknowns RJ_SURFACED=$surfaced \
awk -f "$here/event-field.awk" -f "$here/record-judgment.awk" \
    -v run_id="$run_id" -v source="$source" -v source_id="$source_id" \
    -v detail_read="$detail_read" -v relevant="$relevant" -v band="$band" \
    -v nhc="$nhc" -v same_role="$same_role" \
    -v posted_extracted="$posted_extracted" -v ts="$ts" > "$line"

[ -s "$line" ] || die 'built an empty event line'

# A judgment already recorded for this posting in this run. The same one again is a retry and
# changes nothing; a different one is a conflict the caller has to settle, so write neither.
prev=$(grep -F '"event":"evaluated"' "$jobs" \
       | grep -F "\"run_id\":\"$run_id\"" \
       | grep -F "\"source\":\"$source\"" \
       | grep -F "\"source_id\":\"$source_id\"" | tail -1)

if [ -n "$prev" ]; then
  a=$(printf '%s\n' "$prev" | sed 's/,"ts":"[^"]*"//')
  b=$(sed 's/,"ts":"[^"]*"//' "$line")
  if [ "$a" = "$b" ]; then
    printf 'record-judgment: %s:%s already carries this verdict — nothing written\n' \
      "$source" "$source_id" >&2
    exit 0
  fi
  printf 'record-judgment: %s:%s already has a DIFFERENT verdict in run %s — nothing written\n' \
    "$source" "$source_id" "$run_id" >&2
  printf 'record-judgment:   recorded: %s\n' "$a" >&2
  printf 'record-judgment:   offered:  %s\n' "$b" >&2
  exit 1
fi

cat "$line" >> "$jobs"
```

- [ ] **Step 4: Write `record-judgment.awk`**

```awk
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
```

Both files are function definitions and a `BEGIN` block, so `awk` reads no input and exits after `BEGIN`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k judgment -v`
Expected: all thirteen PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search-run/scripts/record-judgment.sh \
        skills/job-search-run/scripts/record-judgment.awk tests/test_mechanics_scripts.py
git commit -m "feat(run): record a judgment without the caller writing any JSON"
```

---

### Task 5: `run-counts.sh`

**Files:**
- Create: `skills/job-search-run/scripts/run-counts.sh`, `skills/job-search-run/scripts/run-counts.awk`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: every event type from Tasks 1–4; `event-field.awk` from Task 0.
- Produces: `run-counts.sh <jobs.jsonl> <run_id>` prints the key/value lines in the output contract at the top of this plan, one per line, and exits 0. A relevant row with no band prints `INVALID relevant-row-without-a-band=<n>` and exits 1.

**`evaluated` events are scoped to the run.** Every event type this script reads is filtered by `run_id`. Without that, a later run judging a posting an earlier interrupted run surfaced would change the earlier run's recomputed counts, so `validate-workspace.sh --post-close` would start failing a record that was right when it was written. With it, the numbers for any run_id are the same the day it closed and a year later, which is what makes invariant 4 an invariant.

**`searches_never_succeeded` is what makes a run degraded.** `call` events with `route: search-jobs` are grouped by `source` and `query_id` — a retry sequence is several events in one group, because `agent-data-reference:74` says a call counts as failed once its three attempts are spent. A group with no `ok: true` member is a search that never returned. A single failed attempt inside a group that later succeeded is not one, and does not degrade the run.

- [ ] **Step 1: Write the failing tests**

```python
COUNTS = RUN_SCRIPTS / "run-counts.sh"


def counts(jobs, run_id=RID):
    r = run_script(COUNTS, jobs, run_id)
    return r, dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)


def judge_all(jobs, rows, **kw):
    for row in rows:
        run_script(JUDGE, *judge_args(jobs, row, **kw))


def test_a_run_killed_after_the_search_reports_everything_unreviewed(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    n = len(api_rows("search.linkedin.json"))
    r, c = counts(jobs)
    assert r.returncode == 0, r.stderr
    assert c["postings_surfaced"] == str(n)
    assert c["postings_reviewed"] == "0"
    assert c["postings_unreviewed"] == str(n)


def test_the_bands_and_filtered_out_sum_to_reviewed(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    a, b = 2, 7                                    # slice points, not row counts
    judge_all(jobs, rows[:a], detail_read="true", relevant="true", match="strong",
              reasoning="Fits.")
    judge_all(jobs, rows[a:b], detail_read="true", relevant="true", match="moderate",
              reasoning="Partly fits.")
    judge_all(jobs, rows[b:], detail_read="false", relevant="false", reasoning="Outside the brief.")
    _, c = counts(jobs)
    reviewed = int(c["postings_reviewed"])
    assert (int(c["match_strong"]) + int(c["match_moderate"]) + int(c["match_weak"])
            + int(c["filtered_out"])) == reviewed
    assert reviewed + int(c["postings_unreviewed"]) == int(c["postings_surfaced"])
    assert int(c["match_strong"]) == a
    assert int(c["match_moderate"]) == b - a
    assert int(c["match_weak"]) == 0
    assert int(c["filtered_out"]) == len(rows) - b
    assert c["postings_detail_read"] == "0"        # no detail events recorded


def test_by_source_sums_to_surfaced(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    for name in ("search.linkedin.json", "search.ashby.json"):
        record_search(jobs, name)
    _, c = counts(jobs)
    per = {k: int(v) for k, v in c.items() if k.startswith("by_source_")}
    assert sum(per.values()) == int(c["postings_surfaced"])
    assert per == {"by_source_linkedin": len(api_rows("search.linkedin.json")),
                   "by_source_ashby": len(api_rows("search.ashby.json"))}


def test_rows_new_total_equals_surfaced(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    for qid in ("a", "b"):
        record_search(jobs, "search.linkedin.json", qid)
    _, c = counts(jobs)
    assert c["rows_new_total"] == c["postings_surfaced"] == str(len(api_rows("search.linkedin.json")))


def test_metered_calls_are_counted_including_a_failed_one(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    run_script(RECORD_API, RID, jobs, FIXTURES / "detail.error.json", "--route", "get-posting")
    _, c = counts(jobs)
    assert c["calls_searches"] == "1"          # the failed call was a get-posting, and is filed so
    assert c["calls_detail_reads"] == "1"
    assert c["calls_failed"] == "1"
    assert int(c["calls_total_metered"]) == (int(c["calls_searches"])
                                             + int(c["calls_detail_reads"])
                                             + int(c["calls_other"]))


def test_postings_detail_read_counts_postings_not_calls(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    record_detail(jobs, "detail.ashby.json")
    record_detail(jobs, "detail.ashby.json")       # a repeat: one more call, no more coverage
    _, c = counts(jobs)
    assert c["postings_detail_read"] == "1"
    assert c["calls_detail_reads"] == "2"


def test_a_search_that_failed_then_succeeded_is_not_a_lost_search(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"call","run_id":"%s","route":"search-jobs","source":"ashby","query_id":"q1",'
        '"ok":false,"rows_returned":0,"rows_new":0,"retryable":true}\n'
        '{"event":"call","run_id":"%s","route":"search-jobs","source":"ashby","query_id":"q1",'
        '"ok":true,"rows_returned":0,"rows_new":0,"retryable":null}\n' % (RID, RID))
    _, c = counts(jobs)
    assert c["calls_failed"] == "1"
    assert c["searches_never_succeeded"] == "0"
    assert c["searches_never_succeeded_ids"] == ""


def test_a_search_that_never_returned_is_named(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("".join(
        '{"event":"call","run_id":"%s","route":"search-jobs","source":"ashby","query_id":"q2",'
        '"ok":false,"rows_returned":0,"rows_new":0,"retryable":true}\n' % RID for _ in range(3)))
    _, c = counts(jobs)
    assert c["searches_never_succeeded"] == "1"
    assert c["searches_never_succeeded_ids"] == "ashby:q2"


def test_a_failed_detail_read_is_not_a_lost_search(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    run_script(RECORD_API, RID, jobs, FIXTURES / "detail.error.json", "--route", "get-posting")
    _, c = counts(jobs)
    assert c["calls_failed"] == "1"
    assert c["searches_never_succeeded"] == "0"


def test_a_relevant_row_with_no_band_is_reported_as_invalid(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    jobs.write_text(jobs.read_text() +
        '{"event":"evaluated","run_id":"%s","source":"%s","source_id":"%s",'
        '"detail_read":true,"relevant":true,"match":null}\n'
        % (RID, row["source"], row["source_id"]))
    r, _ = counts(jobs)
    assert r.returncode == 1
    assert "relevant-row-without-a-band=1" in r.stdout


def test_another_runs_events_do_not_enter_these_counts(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    other = jobs.read_text().replace(RID, "2026-01-01T00-00-00Z")
    jobs.write_text(jobs.read_text() + other)
    _, c = counts(jobs)
    assert c["postings_surfaced"] == str(len(api_rows("search.linkedin.json")))


def test_a_later_run_judging_an_earlier_runs_posting_does_not_move_its_counts(tmp_path):
    """Invariant 4 has to hold a year later, not only at close."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    _, before = counts(jobs)
    row = first_surfaced(jobs)
    later = "2026-09-01T00-00-00Z"
    jobs.write_text(jobs.read_text() +
        '{"event":"surfaced","run_id":"%s","source":"%s","source_id":"%s","title":"T",'
        '"company_name":"C"}\n'
        '{"event":"evaluated","run_id":"%s","source":"%s","source_id":"%s",'
        '"detail_read":true,"relevant":true,"match":"strong"}\n'
        % (later, row["source"], row["source_id"], later, row["source"], row["source_id"]))
    _, after = counts(jobs)
    assert after["postings_unreviewed"] == before["postings_unreviewed"]
    assert after["postings_reviewed"] == before["postings_reviewed"]
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k counts -v`
Expected: FAIL — `run-counts.sh` does not exist.

- [ ] **Step 3: Write `run-counts.sh`**

```sh
#!/bin/sh
# run-counts.sh — work out one run's numbers from jobs.jsonl and print them, one key=value per line.
#
# Usage: run-counts.sh <jobs.jsonl> <run_id>
#
# This is the only place a run's numbers are worked out. The run record copies these values and the
# digest's counts line reads the same ones, so the two cannot disagree.
#
# Every event is filtered by run_id, judgments included. That is what makes these numbers the same
# a year from now as they are at close: a later run judging a posting this one left unjudged does
# not reach back and change what this run did.
#
# agent_data_usage is a count of `call` events, so retries, repeats and failures are in it without
# anyone reporting them. searches_never_succeeded groups the search calls by source and query and
# counts the groups where none of the attempts returned — one failed attempt inside a group that
# later answered is not a lost search.
#
# This is the scripted form of the model-run prose contract; that prose remains the no-runtime
# fallback, and counts worked out by hand are not gated by anything, so a run that works them out
# that way says so rather than presenting them as checked.
#
# Exit 0: the counts printed. Exit 1: a relevant row carries no band, named on the last line.
set -u

here=$(dirname "$0")
jobs=${1:?usage: run-counts.sh <jobs.jsonl> <run_id>}
run_id=${2:?usage: run-counts.sh <jobs.jsonl> <run_id>}

[ -f "$jobs" ] || { printf 'run-counts.sh: no such file: %s\n' "$jobs" >&2; exit 2; }

exec awk -f "$here/event-field.awk" -f "$here/run-counts.awk" -v want="$run_id" "$jobs"
```

- [ ] **Step 4: Write `run-counts.awk`**

```awk
# run-counts.awk — see run-counts.sh.

{
  ev  = jval($0, "event")
  if (jval($0, "run_id") != want) next
  k = jval($0, "source") "|" jval($0, "source_id")

  if (ev == "call") {
    route = jval($0, "route")
    ok    = jval($0, "ok")
    if (ok != "true") failed++
    if (route == "search-jobs") {
      searches++
      g = jval($0, "source") ":" jval($0, "query_id")
      if (!(g in group)) { group[g] = 1; ngroup++; grouporder[ngroup] = g }
      if (ok == "true") answered[g] = 1
    }
    else if (route == "get-posting") detailcalls++
    else                             other++
    n = jval($0, "rows_new"); if (n != "") rowsnew += n
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k counts -v`
Expected: all twelve PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search-run/scripts/run-counts.sh skills/job-search-run/scripts/run-counts.awk \
        tests/test_mechanics_scripts.py
git commit -m "feat(run): work out a run's numbers from its own event log"
```

---

### Task 6: `run-matches.sh` — what the digest lists

**Files:**
- Create: `skills/job-search-run/scripts/run-matches.sh`, `skills/job-search-run/scripts/run-matches.awk`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `evaluated` events from Task 4; `event-field.awk` from Task 0.
- Produces: `run-matches.sh <jobs.jsonl> <run_id>` prints the `run-matches.sh` output contract at the top of this plan.

`run-counts.sh` makes the digest's **numbers** come from the log. The postings the digest **names** still came from the model's account of the run — and the measured defect in §1(c) is an error in the listing, not in the counts: a weak match reported with no weak row behind it. Both halves of the digest read from the same place or neither does.

- [ ] **Step 1: Write the failing tests**

```python
MATCHES = RUN_SCRIPTS / "run-matches.sh"


def matches(jobs, run_id=RID):
    r = run_script(MATCHES, jobs, run_id)
    rows = [l.split("\t") for l in r.stdout.splitlines()]
    return r, rows


def test_every_judged_posting_appears_once_with_its_band(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    judge_all(jobs, rows[:2], detail_read="true", relevant="true", match="strong", reasoning="Fits.")
    judge_all(jobs, rows[2:4], detail_read="false", relevant="false", reasoning="On-site only.")
    r, out = matches(jobs)
    assert r.returncode == 0, r.stderr
    assert len(out) == 4
    assert [o[0] for o in out] == ["strong", "strong", "filtered", "filtered"]


def test_the_bands_come_out_in_digest_order(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    judge_all(jobs, rows[0:1], detail_read="false", relevant="false", reasoning="No.")
    judge_all(jobs, rows[1:2], detail_read="true", relevant="true", match="weak", reasoning="Thin.")
    judge_all(jobs, rows[2:3], detail_read="true", relevant="true", match="strong", reasoning="Yes.")
    judge_all(jobs, rows[3:4], detail_read="true", relevant="true", match="moderate", reasoning="Ok.")
    _, out = matches(jobs)
    assert [o[0] for o in out] == ["strong", "moderate", "weak", "filtered"]


def test_a_row_carries_what_the_digest_prints(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true", match="strong",
                                  needs_human_check="true",
                                  reasoning="Remote within the US and the range clears the floor."))
    _, out = matches(jobs)
    band, source, sid, title, company, loc, url, nhc, posted, reasoning = out[0]
    assert (band, source, sid) == ("strong", row["source"], row["source_id"])
    assert (title, company, url) == (row["title"], row["company_name"], row["source_url"])
    assert loc == row["location_display"]
    assert nhc == "true"
    assert reasoning.startswith("Remote within the US")


def test_reasoning_with_a_newline_stays_on_one_line(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true", match="strong",
                                  reasoning="First line.\nSecond line."))
    r, out = matches(jobs)
    assert len(r.stdout.splitlines()) == 1
    assert len(out[0]) == 10
    assert "First line." in out[0][9] and "Second line." in out[0][9]


def test_a_surfaced_but_unjudged_posting_is_not_listed(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    r, out = matches(jobs)
    assert r.returncode == 0 and out == []


def test_another_runs_judgments_are_not_listed(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true", match="strong"))
    other = jobs.read_text().replace(RID, "2026-01-01T00-00-00Z")
    jobs.write_text(jobs.read_text() + other)
    _, out = matches(jobs)
    assert len(out) == 1


def test_the_listing_and_the_counts_agree(tmp_path):
    """The assertion B8 will make against a live run, made here against a fixture."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    judge_all(jobs, rows[:3], detail_read="true", relevant="true", match="moderate", reasoning="Ok.")
    judge_all(jobs, rows[3:], detail_read="false", relevant="false", reasoning="No.")
    _, c = counts(jobs)
    _, out = matches(jobs)
    tally = {}
    for o in out:
        tally[o[0]] = tally.get(o[0], 0) + 1
    assert tally.get("strong", 0) == int(c["match_strong"])
    assert tally.get("moderate", 0) == int(c["match_moderate"])
    assert tally.get("weak", 0) == int(c["match_weak"])
    assert tally.get("filtered", 0) == int(c["filtered_out"])
    assert len(out) == int(c["postings_reviewed"])
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k matches -v`
Expected: FAIL — the script does not exist.

- [ ] **Step 3: Write `run-matches.sh`**

```sh
#!/bin/sh
# run-matches.sh — the postings this run judged, in the order the digest lists them.
#
# Usage: run-matches.sh <jobs.jsonl> <run_id>
#
# One posting per line, tab-separated:
#   band  source  source_id  title  company_name  location_display  source_url
#   needs_human_check  posted_at  reasoning
#
# band is strong, moderate, weak or filtered. Strong first, then moderate, weak, and the postings
# the run judged not relevant; within a band, the order the judgments landed.
#
# The digest's numbers come from run-counts.sh and the postings it names come from here, so the
# section headed "3 strong" holds three postings and they are the three the log says are strong.
# Nothing composes either list from memory of the run.
#
# reasoning is free text with its newlines and tabs turned into spaces, because one posting is one
# line. The full text stays on the event.
set -u

here=$(dirname "$0")
jobs=${1:?usage: run-matches.sh <jobs.jsonl> <run_id>}
run_id=${2:?usage: run-matches.sh <jobs.jsonl> <run_id>}

[ -f "$jobs" ] || { printf 'run-matches.sh: no such file: %s\n' "$jobs" >&2; exit 2; }

exec awk -f "$here/event-field.awk" -f "$here/run-matches.awk" -v want="$run_id" "$jobs"
```

- [ ] **Step 4: Write `run-matches.awk`**

```awk
# run-matches.awk — see run-matches.sh.

BEGIN {
  rank["strong"] = 1; rank["moderate"] = 2; rank["weak"] = 3; rank["filtered"] = 4
}

jval($0, "event") == "evaluated" && jval($0, "run_id") == want {
  k = jval($0, "source") "|" jval($0, "source_id")
  if (!(k in seen)) { seen[k] = 1; n++; order[n] = k }
  ev[k] = $0
}

END {
  for (b = 1; b <= 4; b++) {
    for (i = 1; i <= n; i++) {
      k = order[i]
      l = ev[k]
      band = (jval(l, "relevant") == "true") ? jval(l, "match") : "filtered"
      if (band == "" || !(band in rank) || rank[band] != b) continue
      printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n",
        band,
        jval(l, "source"), jval(l, "source_id"),
        jval(l, "title"), jval(l, "company_name"), jval(l, "location_display"),
        jval(l, "source_url"), jval(l, "needs_human_check"),
        jval(l, "posted_at"), jval(l, "reasoning")
    }
  }
}
```

`jval` already turns `\n`, `\r` and `\t` into spaces, so a reasoning paragraph cannot split a line or invent a column. A relevant row with no band is dropped here and reported by `run-counts.sh`, which is the script that owns that finding.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k matches -v`
Expected: all seven PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search-run/scripts/run-matches.sh skills/job-search-run/scripts/run-matches.awk \
        tests/test_mechanics_scripts.py
git commit -m "feat(run): list the postings a run judged from the log that holds them"
```

---

### Task 7: Fix the two shipped scripts this change breaks

**Files:**
- Modify: `skills/job-search-run/scripts/event-log-append.sh:53-58` and its header
- Modify: `skills/job-search-run/scripts/dedup.sh:58-62` and its header
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `event-log-append.sh`'s idempotency check keys on `evaluated` lines only, and its header contract matches the five event types a run now writes. `dedup.sh`'s known set is source_ids carrying an `evaluated` event, not any event.

Both failures were reproduced against the shipped scripts while designing this. Neither is hypothetical.

- [ ] **Step 1: Write the failing tests**

```python
def test_an_evaluated_event_after_a_surfaced_event_is_not_dropped(tmp_path):
    """The idempotency key is (source, source_id); without an event-type filter a surfaced
    event makes the judgment that follows it look like a duplicate."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text('{"event":"surfaced","run_id":"R","source":"ashby",'
                    '"source_id":"abc-123","title":"Strategic Finance"}\n')
    ev = ('{"event":"evaluated","run_id":"R","source":"ashby","source_id":"abc-123",'
          '"relevant":true,"match":"strong"}')
    r = subprocess.run(["sh", str(APPEND), str(jobs)], input=ev, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert len(lines(jobs)) == 2


def test_a_surfaced_but_never_judged_posting_is_still_a_candidate(tmp_path):
    """A run that stopped leaves surfaced rows with no judgment; the next run must re-offer them."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text('{"event":"surfaced","run_id":"R","source":"ashby","source_id":"abc-123"}\n')
    r = subprocess.run(["sh", str(DEDUP), str(jobs), "ashby"],
                       input="abc-123\nxyz-999\n", capture_output=True, text=True)
    assert sorted(r.stdout.split()) == ["abc-123", "xyz-999"]


def test_a_judged_posting_is_still_filtered_out(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text('{"event":"evaluated","run_id":"R","source":"ashby","source_id":"abc-123",'
                    '"relevant":false,"match":null}\n')
    r = subprocess.run(["sh", str(DEDUP), str(jobs), "ashby"],
                       input="abc-123\nxyz-999\n", capture_output=True, text=True)
    assert r.stdout.split() == ["xyz-999"]
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k "not_dropped or never_judged or still_filtered" -v`
Expected: the first two FAIL (1 line instead of 2; `abc-123` missing from the output); the third already passes.

- [ ] **Step 3: Fix `event-log-append.sh`**

Replace the idempotency block (currently lines 53-58):

```sh
  # Idempotency: skip if this (source, source_id) already has an `evaluated` event. The filter on
  # event type matters — a posting is recorded as `surfaced` before it is judged, and without it
  # that first event would make the judgment look like a duplicate and drop it.
  if [ -f "$jobs" ] && grep -F '"event":"evaluated"' "$jobs" 2>/dev/null \
       | grep -E '"source"[[:space:]]*:[[:space:]]*"'"$src"'"' \
       | grep -o '"source_id"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4 \
       | grep -qxF "$sid"; then
    exit 0
  fi
```

- [ ] **Step 4: Reconcile `event-log-append.sh`'s header with the five event types**

Its header states that every event carries a non-empty `source_id`. A `call` event carries none — it is about a request, not a posting — and `record-api-response.sh` appends it directly. The checks themselves stay as they are; the header must stop claiming a rule the log no longer keeps. Replace the bullet list with:

> This is the append path for a `status_changed` event, and for an `evaluated` event on a host that is writing one by hand. The four events a run's scripts write — `call`, `surfaced`, `queued`, `detail` — are appended by `record-api-response.sh` and `queue-detail-read.sh`, which build them, so they never come through here. What this script checks is therefore what a hand-written posting event must satisfy: one event per line; a non-empty `"source_id"`, with the literal key appearing exactly once; for an `evaluated` event a non-empty `"source"`, with that key appearing at most once, because the per-source grep depends on it; and `"same_role_as"`, when present, a flat string rather than a nested object.

- [ ] **Step 5: Fix `dedup.sh`**

Replace the known-ids pipeline (currently lines 58-62):

```sh
# Known-ids set for this source: the postings that already carry a judgment. A posting a stopped
# run surfaced and never judged is NOT known — the next run has to offer it again.
grep -F '"event":"evaluated"' "$jobs" 2>/dev/null \
  | grep -E '"source"[[:space:]]*:[[:space:]]*"'"$src"'"' \
  | grep -o '"source_id"[[:space:]]*:[[:space:]]*"[^"]*"' \
  | cut -d'"' -f4 \
  | sort -u > "$known"
```

Update the header comment's description of the known set to match, and add one sentence recording that `record-api-response.sh` now does this check as it appends, so this mode has no caller in the run skill's prose after Task 13 and is kept as the no-runtime fallback and for a host that wants it standalone. `--near` keeps its caller and is unchanged.

- [ ] **Step 6: Run the whole mechanics suite**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -v`
Expected: all PASS, including the pre-existing dedup and append tests.

- [ ] **Step 7: Commit**

```bash
git add skills/job-search-run/scripts/event-log-append.sh skills/job-search-run/scripts/dedup.sh \
        tests/test_mechanics_scripts.py
git commit -m "fix(run): key the append and dedup checks on judged postings, not seen ones"
```

---

### Task 8: `open-run.sh`

**Files:**
- Create: `skills/job-search-runbook/scripts/open-run.sh`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `validate-workspace.sh` (existing); the `tmp_workspace` fixture from Task 0.
- Produces: `open-run.sh <workspace>` prints three lines — `run_id=…`, `started_at=…`, `brief_revision=…` — creates `runs/.started-<run_id>`, and runs the workspace checks. Exit 0 clean; exit 1 when the run opened but the workspace has findings, which print on stdout after the three lines; exit 2 when there is no `config.yaml` to write into, with no marker and no run.

Looking for a leftover marker stays in the runbook's prose rather than moving in here. That is a deliberate limit of this change and not an oversight: the decision a leftover marker calls for is to tell the user their last run did not finish, which is the model's to make and to say. The Self-review at the end records it as a gap a follow-on change can close.

- [ ] **Step 1: Write the failing tests**

```python
OPEN_RUN = RUNBOOK_SCRIPTS / "open-run.sh"
RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$")
UTC_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def parsed_output(r):
    return dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)


def test_run_id_and_started_at_name_the_same_instant(tmp_workspace):
    r = run_script(OPEN_RUN, tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr
    out = parsed_output(r)
    assert RUN_ID_RE.match(out["run_id"])
    assert UTC_TS_RE.match(out["started_at"])
    assert out["run_id"] == out["started_at"].replace(":", "-")


def test_opening_creates_the_marker(tmp_workspace):
    out = parsed_output(run_script(OPEN_RUN, tmp_workspace))
    assert (tmp_workspace / "runs" / (".started-" + out["run_id"])).exists()


def test_brief_revision_is_the_first_twelve_of_the_digest(tmp_workspace):
    import hashlib
    out = parsed_output(run_script(OPEN_RUN, tmp_workspace))
    digest = hashlib.sha256((tmp_workspace / "preferences.md").read_bytes()).hexdigest()
    assert out["brief_revision"] == digest[:12]


def test_a_broken_workspace_still_opens_the_run_and_reports_the_findings(tmp_workspace):
    (tmp_workspace / "config.yaml").write_text("version: 2\n")     # missing queries, schedule, sources
    r = run_script(OPEN_RUN, tmp_workspace)
    assert r.returncode == 1
    out = parsed_output(r)
    assert RUN_ID_RE.match(out["run_id"])
    assert (tmp_workspace / "runs" / (".started-" + out["run_id"])).exists()
    assert "INVALID config.yaml" in r.stdout


def test_no_config_means_no_run_at_all(tmp_path):
    ws = tmp_path / "empty"
    ws.mkdir()
    r = run_script(OPEN_RUN, ws)
    assert r.returncode == 2
    assert "config.yaml" in r.stderr
    assert not list(ws.glob("runs/.started-*"))


def test_a_workspace_with_no_brief_does_not_open_a_run_with_an_empty_revision(tmp_workspace):
    (tmp_workspace / "preferences.md").unlink()
    r = run_script(OPEN_RUN, tmp_workspace)
    assert r.returncode != 0
    assert "preferences.md" in (r.stdout + r.stderr)
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k open_run -v`
Expected: FAIL — the script does not exist.

- [ ] **Step 3: Write the script**

```sh
#!/bin/sh
# open-run.sh — open one run: mint its id, mark it started, take the brief revision, check the
# workspace.
#
# Usage: open-run.sh <workspace>
#
# Prints three lines:
#   run_id=2026-07-30T15-04-02Z
#   started_at=2026-07-30T15:04:02Z
#   brief_revision=9f2c41a7be05
#
# The clock is read once. started_at keeps the colons; run_id uses dashes because it is a
# filename, so the two name the same instant and nothing has to compose either of them.
#
# The workspace checks run here rather than as a separate step, so opening a run and checking it
# cannot come apart. A workspace with broken files still opens a run: the failure then closes as a
# blocked run with a record, rather than leaving nothing behind.
#
# Exit 0: opened, workspace clean.
# Exit 1: opened, and the workspace findings follow the three lines on stdout — close blocked.
# Exit 2: no config.yaml, so there is nothing to write into; no marker and no run.
set -u

ws=${1:?usage: open-run.sh <workspace>}
here=$(dirname "$0")

[ -d "$ws" ] || { printf 'open-run.sh: no such workspace: %s\n' "$ws" >&2; exit 2; }
[ -f "$ws/config.yaml" ] || {
  printf 'open-run.sh: no config.yaml in %s — setup has not run, so there is no workspace to write into\n' \
    "$ws" >&2
  exit 2
}

now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
run_id=$(printf '%s\n' "$now" | tr ':' '-')

mkdir -p "$ws/runs"
: > "$ws/runs/.started-$run_id"

rev=''
if [ -f "$ws/preferences.md" ]; then
  if command -v shasum >/dev/null 2>&1; then
    rev=$(shasum -a 256 "$ws/preferences.md" | cut -c1-12)
  else
    rev=$(sha256sum "$ws/preferences.md" | cut -c1-12)
  fi
fi

printf 'run_id=%s\n' "$run_id"
printf 'started_at=%s\n' "$now"
printf 'brief_revision=%s\n' "$rev"

# An empty revision would ride into the record as a null nobody notices, so say it here. The
# validator reports the missing brief too; this makes the run's own output carry it.
[ -n "$rev" ] || printf 'INVALID preferences.md missing-file\n'

sh "$here/validate-workspace.sh" "$ws" || exit 1
[ -n "$rev" ] || exit 1
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k open_run -v`
Expected: all six PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/job-search-runbook/scripts/open-run.sh tests/test_mechanics_scripts.py
git commit -m "feat(runbook): open a run from one clock read, and check the workspace while doing it"
```

---

### Task 9: `close-run.sh`, `clear-run.sh`, and the run-record template

**Files:**
- Create: `skills/job-search-runbook/scripts/close-run.sh`, `skills/job-search-runbook/scripts/clear-run.sh`
- Modify: `skills/job-search-run/templates/run-record.example.json`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `run-counts.sh` (Task 5) and its output contract.
- Produces: `close-run.sh <workspace> <run_id> --trigger manual|scheduled [--scheduler-id ID] --close-state complete|blocked|interrupted [--brief-revision REV] [--sources 'a,b'] [--queries 'a,b']` writes `runs/<run_id>.json` and prints `run_health=<healthy|degraded>`. It deletes nothing. `clear-run.sh <workspace> <run_id>` deletes `runs/.started-<run_id>` and `runs/.scratch/<run_id>/`.

**Writing the record and clearing the run are two steps because the digest sits between them.** The scratch directory holds each search response as it arrived, and the digest is written after the record so it can carry `run_health`. One script that did both would delete the run's working files before the digest that may still need them — which is the ordering the runbook has today (`job-search-runbook/SKILL.md:64-72`: record, digest, then delete the marker and the scratch). `validate-workspace.sh --post-close` already fails on a leftover marker or scratch directory, so a run that dies between the digest and `clear-run.sh` is reported rather than silent.

**`run_health` no longer turns on whether a call failed.**

```
healthy  = close_state is complete
           AND postings_unreviewed == 0
           AND every search that was attempted returned at least once
degraded = anything else
```

A single failed attempt inside a retry sequence that later answered is not a lost search, and a failed detail read is not a search at all — a posting whose detail read failed permanently gets judged from its summary row, so it is reviewed and the run is healthy, with the failures visible in `agent_data_usage` and named in the digest's footnotes. That is what `evals/cases/fault-503.yaml` asks a run to do. A search that never returned after its retry budget is spent **is** a lost search and does degrade the run: its postings were never surfaced, so nothing else would notice their absence.

A lost search does not block a `complete` close. The run did finish the work it could reach.

- [ ] **Step 1: Write the failing tests**

```python
CLOSE_RUN = RUNBOOK_SCRIPTS / "close-run.sh"
CLEAR_RUN = RUNBOOK_SCRIPTS / "clear-run.sh"


def opened(ws):
    return parsed_output(run_script(OPEN_RUN, ws))


def close(ws, run_id, close_state="complete", **kw):
    args = [ws, run_id, "--trigger", "manual", "--close-state", close_state]
    for k, v in kw.items():
        args += ["--" + k.replace("_", "-"), v]
    return run_script(CLOSE_RUN, *args)


def record_of(ws, run_id):
    return json.loads((ws / "runs" / (run_id + ".json")).read_text())


def test_the_record_carries_the_counts_from_the_log(tmp_workspace):
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.linkedin.json",
               "--route", "search-jobs", "--query-id", "q")
    n = len(api_rows("search.linkedin.json"))
    for row in [e for e in lines(jobs) if e["event"] == "surfaced"]:
        run_script(JUDGE, jobs, "--run-id", o["run_id"], "--source", row["source"],
                   "--source-id", row["source_id"], "--detail-read", "false",
                   "--relevant", "false", "--reasoning", "Outside the brief.")
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["postings_surfaced"] == n
    assert rec["postings_reviewed"] == n
    assert rec["postings_unreviewed"] == 0
    assert rec["filtered_out"] == n
    assert rec["matches"] == {"strong": 0, "moderate": 0, "weak": 0}
    assert rec["by_source"] == {"linkedin": n}
    assert rec["agent_data_usage"]["total_metered"] == 1


def test_close_prints_run_health_for_the_digest(tmp_workspace):
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    r = close(tmp_workspace, o["run_id"])
    assert parsed_output(r)["run_health"] == "healthy"
    assert record_of(tmp_workspace, o["run_id"])["run_health"] == "healthy"


def test_completed_at_is_later_than_started_at_and_not_later_than_the_file(tmp_workspace):
    import datetime
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    close(tmp_workspace, o["run_id"])
    path = tmp_workspace / "runs" / (o["run_id"] + ".json")
    rec = json.loads(path.read_text())
    assert UTC_TS_RE.match(rec["completed_at"])
    assert rec["completed_at"] >= rec["started_at"]
    stated = datetime.datetime.strptime(rec["completed_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc)
    written = datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc)
    assert stated <= written + datetime.timedelta(seconds=2)


def test_a_complete_close_over_unreviewed_postings_is_refused(tmp_workspace):
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.linkedin.json",
               "--route", "search-jobs", "--query-id", "q")
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 1
    assert "unreviewed" in r.stderr or "never judged" in r.stderr
    assert not (tmp_workspace / "runs" / (o["run_id"] + ".json")).exists()
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()


def test_the_same_run_closes_interrupted_and_records_run_health_degraded(tmp_workspace):
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.linkedin.json",
               "--route", "search-jobs", "--query-id", "q")
    r = close(tmp_workspace, o["run_id"], "interrupted")
    assert r.returncode == 0, r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["run_health"] == "degraded"
    assert rec["postings_unreviewed"] == len(api_rows("search.linkedin.json"))


def test_a_failed_detail_read_does_not_degrade_a_finished_run(tmp_workspace):
    """fault-503: every posting judged from its summary row, so the pass finished."""
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.ashby.json",
               "--route", "search-jobs", "--query-id", "q")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "detail.error.json",
               "--route", "get-posting")
    for row in [e for e in lines(jobs) if e["event"] == "surfaced"]:
        run_script(JUDGE, jobs, "--run-id", o["run_id"], "--source", row["source"],
                   "--source-id", row["source_id"], "--detail-read", "false",
                   "--relevant", "false", "--reasoning", "Judged from the row.")
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["run_health"] == "healthy"
    assert rec["agent_data_usage"]["detail_reads"] == 1


def test_a_search_that_never_returned_degrades_the_run_without_blocking_the_close(tmp_workspace):
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("".join(
        '{"event":"call","run_id":"%s","route":"search-jobs","source":"ashby","query_id":"q2",'
        '"ok":false,"rows_returned":0,"rows_new":0,"retryable":true}\n' % o["run_id"]
        for _ in range(3)))
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["close_state"] == "complete"
    assert rec["run_health"] == "degraded"


def test_clearing_removes_the_marker_and_the_scratch_directory(tmp_workspace):
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    scratch = tmp_workspace / "runs" / ".scratch" / o["run_id"]
    scratch.mkdir(parents=True)
    (scratch / "search.json").write_text("{}")
    close(tmp_workspace, o["run_id"])
    assert scratch.exists(), "close must leave the digest's working files alone"
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()
    r = run_script(CLEAR_RUN, tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stderr
    assert not (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()
    assert not scratch.exists()


def test_clearing_a_run_with_no_record_is_refused(tmp_workspace):
    o = opened(tmp_workspace)
    r = run_script(CLEAR_RUN, tmp_workspace, o["run_id"])
    assert r.returncode == 1
    assert "no record" in r.stderr
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()


def test_the_record_matches_the_template_field_set(tmp_workspace):
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    close(tmp_workspace, o["run_id"])
    rec = record_of(tmp_workspace, o["run_id"])
    template = json.loads((RUN_SCRIPTS.parent / "templates" / "run-record.example.json").read_text())
    assert set(rec) == set(template)
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k "close_run or clear" -v`
Expected: FAIL — neither script exists.

- [ ] **Step 3: Update the template**

Replace `skills/job-search-run/templates/run-record.example.json` with:

```json
{
  "run_id": "2026-07-30T15-04-02Z",
  "trigger": "scheduled",
  "scheduler_id": "com.job-search.daily",
  "brief_revision": "9f2c41a7be05",
  "close_state": "complete",
  "run_health": "healthy",
  "sources": ["linkedin", "ashby"],
  "queries": ["ai-eng-remote", "ml-platform-sf"],
  "postings_surfaced": 50,
  "postings_reviewed": 50,
  "postings_unreviewed": 0,
  "postings_detail_read": 12,
  "matches": { "strong": 3, "moderate": 6, "weak": 2 },
  "filtered_out": 39,
  "by_source": { "linkedin": 25, "ashby": 25 },
  "agent_data_usage": {
    "searches": 4,
    "detail_reads": 13,
    "other": 0,
    "total_metered": 17
  },
  "started_at": "2026-07-30T15:04:02Z",
  "completed_at": "2026-07-30T15:12:47Z"
}
```

Check the arithmetic: `3 + 6 + 2 + 39 = 50` reviewed; `50 + 0 = 50` surfaced; `25 + 25 = 50`; `4 + 13 + 0 = 17`. `detail_reads: 13` against `postings_detail_read: 12` is one posting that needed a second call — the two fields answer different questions and are meant to differ.

- [ ] **Step 4: Write `close-run.sh`**

```sh
#!/bin/sh
# close-run.sh — write one run's record. Deleting what the run was using is clear-run.sh's job,
# because the digest goes between the two.
#
# Usage: close-run.sh <workspace> <run_id> --trigger manual|scheduled \
#          [--scheduler-id ID] --close-state complete|blocked|interrupted \
#          [--brief-revision REV] [--sources 'a,b'] [--queries 'a,b']
#
# Prints one line, run_health=healthy or run_health=degraded, which the digest's header carries.
#
# Every count comes from run-counts.sh and completed_at from a clock read here, so no number in the
# record is anyone's account of the run. run_health is worked out the same way: healthy means the
# run closed complete, left no posting unjudged, and every search it attempted answered at least
# once. A single failed attempt inside a retry sequence that then succeeded is not a lost search,
# and a failed detail read is not a search — that posting gets judged from its summary row.
#
# A close_state of complete over unjudged postings is refused and nothing is written: a run that
# did not finish must not read as one that did. A lost search does not block the close; the run
# finished the work it could reach, and the record says degraded.
#
# Exit 0: the record is written.
# Exit 1: nothing written; stderr names what contradicts the close.
set -u

ws=${1:?usage: close-run.sh <workspace> <run_id> --trigger T --close-state S}
run_id=${2:?usage: close-run.sh <workspace> <run_id> --trigger T --close-state S}
shift 2

trigger='' scheduler_id='' close_state='' brief_rev='' sources='' queries=''
die() { printf 'close-run: %s\n' "$1" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case $1 in
    --trigger)         trigger=${2?}; shift 2 ;;
    --scheduler-id)    scheduler_id=${2?}; shift 2 ;;
    --close-state)     close_state=${2?}; shift 2 ;;
    --brief-revision)  brief_rev=${2?}; shift 2 ;;
    --sources)         sources=${2?}; shift 2 ;;
    --queries)         queries=${2?}; shift 2 ;;
    *) die "unknown option $1" ;;
  esac
done

case $trigger in manual|scheduled) ;; *) die '--trigger must be manual or scheduled' ;; esac
case $close_state in
  complete|blocked|interrupted) ;;
  *) die '--close-state must be complete, blocked or interrupted' ;;
esac
[ -d "$ws" ] || die "no such workspace: $ws"
[ -d "$ws/runs" ] || mkdir -p "$ws/runs"

here=$(dirname "$0")
runscripts=$here/../../job-search-run/scripts     # one plugin, one tree; see the header of clear-run.sh
jobs=$ws/jobs.jsonl
[ -f "$jobs" ] || : > "$jobs"

counts=$(sh "$runscripts/run-counts.sh" "$jobs" "$run_id") || die "run-counts.sh reported: $counts"

get() { printf '%s\n' "$counts" | grep "^$1=" | cut -d= -f2; }
unreviewed=$(get postings_unreviewed)
lost=$(get searches_never_succeeded)
lostids=$(get searches_never_succeeded_ids)

if [ "$close_state" = complete ] && [ "${unreviewed:-0}" -ne 0 ]; then
  die "close_state complete, but $unreviewed postings were never judged — close interrupted, or judge them"
fi

run_health=degraded
if [ "$close_state" = complete ] && [ "${unreviewed:-0}" -eq 0 ] && [ "${lost:-0}" -eq 0 ]; then
  run_health=healthy
fi
[ "${lost:-0}" -eq 0 ] || \
  printf 'close-run: %s search(es) never returned and are not in these counts: %s\n' \
    "$lost" "$lostids" >&2

completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
started_at=$(printf '%s\n' "$run_id" | sed 's/T\(..\)-\(..\)-\(..\)Z$/T\1:\2:\3Z/')

record=$ws/runs/$run_id.json
tmp=$record.tmp

CR_COUNTS=$counts CR_SOURCES=$sources CR_QUERIES=$queries \
awk -v run_id="$run_id" -v trigger="$trigger" -v sched="$scheduler_id" \
    -v close_state="$close_state" -v run_health="$run_health" -v brief_rev="$brief_rev" \
    -v started_at="$started_at" -v completed_at="$completed_at" '
  function esc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return s }
  function jstr(s) { return "\"" esc(s) "\"" }
  function jarr(s,   n, p, i, out) {
    if (s == "") return "[]"
    n = split(s, p, ",")
    out = "["
    for (i = 1; i <= n; i++) { if (i > 1) out = out ", "; out = out jstr(p[i]) }
    return out "]"
  }
  BEGIN {
    n = split(ENVIRON["CR_COUNTS"], rows, "\n")
    for (i = 1; i <= n; i++) {
      eq = index(rows[i], "=")
      if (eq == 0) continue
      key = substr(rows[i], 1, eq - 1); val = substr(rows[i], eq + 1)
      c[key] = val
      if (key ~ /^by_source_/) {
        s = key; sub(/^by_source_/, "", s)
        nsrc++; srck[nsrc] = s; srcv[nsrc] = val
      }
    }
    print "{"
    printf "  \"run_id\": %s,\n", jstr(run_id)
    printf "  \"trigger\": %s,\n", jstr(trigger)
    printf "  \"scheduler_id\": %s,\n", (sched == "" ? "null" : jstr(sched))
    printf "  \"brief_revision\": %s,\n", (brief_rev == "" ? "null" : jstr(brief_rev))
    printf "  \"close_state\": %s,\n", jstr(close_state)
    printf "  \"run_health\": %s,\n", jstr(run_health)
    printf "  \"sources\": %s,\n", jarr(ENVIRON["CR_SOURCES"])
    printf "  \"queries\": %s,\n", jarr(ENVIRON["CR_QUERIES"])
    printf "  \"postings_surfaced\": %d,\n", c["postings_surfaced"]
    printf "  \"postings_reviewed\": %d,\n", c["postings_reviewed"]
    printf "  \"postings_unreviewed\": %d,\n", c["postings_unreviewed"]
    printf "  \"postings_detail_read\": %d,\n", c["postings_detail_read"]
    printf "  \"matches\": { \"strong\": %d, \"moderate\": %d, \"weak\": %d },\n",
           c["match_strong"], c["match_moderate"], c["match_weak"]
    printf "  \"filtered_out\": %d,\n", c["filtered_out"]
    printf "  \"by_source\": {"
    for (i = 1; i <= nsrc; i++) {
      if (i > 1) printf ","
      printf " %s: %d", jstr(srck[i]), srcv[i]
    }
    printf " },\n"
    print  "  \"agent_data_usage\": {"
    printf "    \"searches\": %d,\n", c["calls_searches"]
    printf "    \"detail_reads\": %d,\n", c["calls_detail_reads"]
    printf "    \"other\": %d,\n", c["calls_other"]
    printf "    \"total_metered\": %d\n", c["calls_total_metered"]
    print  "  },"
    printf "  \"started_at\": %s,\n", jstr(started_at)
    printf "  \"completed_at\": %s\n", jstr(completed_at)
    print "}"
  }' > "$tmp"

# A half-written record at the real path would be worse than none, and the marker and the scratch
# are still there to try again from.
if [ ! -s "$tmp" ]; then
  rm -f "$tmp"
  die "the record came out empty — nothing written, the marker and the scratch are untouched"
fi
mv "$tmp" "$record"

printf 'run_health=%s\n' "$run_health"
printf 'close-run: wrote runs/%s.json (%s, %s)\n' "$run_id" "$close_state" "$run_health" >&2
```

The `=` is found with `index` rather than `split(rows[i], kv, "=")`, so `searches_never_succeeded_ids=ashby:q2` keeps its value whole and a source name is never cut in half.

- [ ] **Step 5: Write `clear-run.sh`**

```sh
#!/bin/sh
# clear-run.sh — delete what one run was using, once its record and its digest are written.
#
# Usage: clear-run.sh <workspace> <run_id>
#
# Removes runs/.started-<run_id> and runs/.scratch/<run_id>/. It is a separate step from close-run.sh
# because the digest is written between the two and the scratch directory holds the responses the
# run collected. validate-workspace.sh --post-close reports either leftover, so a run that stops
# before this step is named rather than silently half-closed.
#
# It refuses to clear a run with no record: the marker is the only thing that says the run happened.
#
# Exit 0: cleared. Exit 1: nothing removed; stderr names why.
set -u

ws=${1:?usage: clear-run.sh <workspace> <run_id>}
run_id=${2:?usage: clear-run.sh <workspace> <run_id>}

[ -d "$ws" ] || { printf 'clear-run: no such workspace: %s\n' "$ws" >&2; exit 1; }
[ -f "$ws/runs/$run_id.json" ] || {
  printf 'clear-run: no record at runs/%s.json — close the run before clearing it\n' "$run_id" >&2
  exit 1
}

rm -f "$ws/runs/.started-$run_id"
rm -rf "$ws/runs/.scratch/$run_id"
printf 'clear-run: cleared the marker and the scratch for %s\n' "$run_id" >&2
```

Both runbook scripts reach `../../job-search-run/scripts/` for `run-counts.sh`. Every host packaging ships `./skills/` as one tree — `.claude-plugin`, `.codex-plugin`, `.cursor-plugin` and `.factory-plugin` all point at it, and `INSTALL_FOR_HERMES.md:206` checks a path through it — so the relative walk resolves everywhere. Say that in the header of whichever script an implementer reads first, so the next person does not re-derive it.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k "close_run or clear" -v`
Expected: all ten PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/job-search-runbook/scripts/close-run.sh skills/job-search-runbook/scripts/clear-run.sh \
        skills/job-search-run/templates/run-record.example.json tests/test_mechanics_scripts.py
git commit -m "feat(runbook): write the run record from the log, and clear the run after the digest"
```

---

### Task 10: `validate-workspace.sh` — the invariants and the timestamp gates

**Files:**
- Modify: `skills/job-search-runbook/scripts/validate-workspace.sh`
- Test: `tests/test_validate_workspace.py`

**Interfaces:**
- Consumes: `run-counts.sh` (Task 5).
- Produces: `validate-workspace.sh <workspace> --post-close <run_id>` additionally reports `missing-key <field>` for each absent count field, `counts-disagree-with-log <field> <record> vs <log>`, `bands-do-not-sum-to-reviewed`, `reviewed-plus-unreviewed-is-not-surfaced`, `surfaced-does-not-match-rows-new`, `completed-at-before-started-at`, and `completed-at-after-the-file-that-states-it`.

Because Task 5 scopes every event to its run, invariant 4 holds whenever it is checked, not only at close. A record written in July still validates in December, and re-running `--post-close` against an old run is a supported thing to do rather than a way to manufacture a false finding.

- [ ] **Step 1: Write the failing tests**

`tmp_workspace` now comes from `tests/conftest.py` (Task 0). Update `run_record()` to carry the new fields, then add:

```python
def full_record(run_id=RUN_ID, **overrides):
    record = run_record(run_id)
    record.update({
        "postings_surfaced": 2, "postings_reviewed": 2, "postings_unreviewed": 0,
        "postings_detail_read": 1,
        "matches": {"strong": 1, "moderate": 0, "weak": 0},
        "filtered_out": 1,
        "by_source": {"linkedin": 2},
    })
    record.update(overrides)
    return record


def seed_log(workspace, run_id=RUN_ID):
    """Two postings surfaced by one search, one a strong match and one filtered out."""
    rows = [
        '{"event":"call","run_id":"%s","route":"search-jobs","source":"linkedin","query_id":"q",'
        '"ok":true,"rows_returned":2,"rows_new":2}' % run_id,
        '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"a"}' % run_id,
        '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"b"}' % run_id,
        '{"event":"detail","run_id":"%s","source":"linkedin","source_id":"a"}' % run_id,
        '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"a",'
        '"detail_read":true,"relevant":true,"match":"strong"}' % run_id,
        '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"b",'
        '"detail_read":false,"relevant":false,"match":null}' % run_id,
    ]
    (workspace / "jobs.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_a_record_without_the_count_fields_fails(tmp_workspace):
    seed_log(tmp_workspace)
    write_run(tmp_workspace, run_record())          # the pre-change field set
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "missing-key postings_surfaced" in r.stdout


def test_counts_matching_the_log_pass(tmp_workspace):
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record())
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_count_that_disagrees_with_the_log_fails(tmp_workspace):
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(postings_surfaced=9))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "counts-disagree-with-log postings_surfaced 9 vs 2" in r.stdout


def test_internally_consistent_but_uniformly_wrong_counts_still_fail(tmp_workspace):
    """The real defect: 2+5+2 balanced against 17 actual rows."""
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(
        postings_surfaced=9, postings_reviewed=9, postings_unreviewed=0,
        matches={"strong": 4, "moderate": 3, "weak": 1}, filtered_out=1,
        by_source={"linkedin": 9}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "counts-disagree-with-log" in r.stdout


def test_bands_that_do_not_sum_to_reviewed_fail(tmp_workspace):
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(matches={"strong": 1, "moderate": 1, "weak": 0}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "bands-do-not-sum-to-reviewed" in r.stdout


def test_completed_at_before_started_at_fails(tmp_workspace):
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(started_at="2026-07-16T14:41:12Z",
                                         completed_at="2026-07-16T14:30:00Z"))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "completed-at-before-started-at" in r.stdout


def test_completed_at_later_than_the_file_that_states_it_fails(tmp_workspace):
    """The defect measured on 2026-08-05: a record stating 03:15:00Z, written at 03:06:50Z."""
    import datetime
    seed_log(tmp_workspace)
    future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    write_run(tmp_workspace, full_record(completed_at=future))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "completed-at-after-the-file-that-states-it" in r.stdout


def test_a_record_for_a_run_with_no_log_events_is_not_checked_against_counts(tmp_workspace):
    """An older record, written before this change, must still read as valid."""
    (tmp_workspace / "jobs.jsonl").write_text("", encoding="utf-8")
    write_run(tmp_workspace, run_record())
    r = run_validator(tmp_workspace)          # no --post-close
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_later_run_judging_this_runs_leftovers_does_not_invalidate_this_record(tmp_workspace):
    """Invariant 4 is checkable at any time, not only at close."""
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(
        postings_reviewed=1, postings_unreviewed=1, filtered_out=0,
        matches={"strong": 1, "moderate": 0, "weak": 0}))
    # b was surfaced by this run and judged by a later one.
    log = (tmp_workspace / "jobs.jsonl").read_text().replace(
        '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"b",'
        '"detail_read":false,"relevant":false,"match":null}\n' % RUN_ID,
        '{"event":"evaluated","run_id":"2026-09-01T00-00-00Z","source":"linkedin","source_id":"b",'
        '"detail_read":false,"relevant":false,"match":null}\n')
    (tmp_workspace / "jobs.jsonl").write_text(log, encoding="utf-8")
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr
```

Both `datetime.utcnow()` and `datetime.utcfromtimestamp()` are deprecated from Python 3.12; every timestamp in these suites uses the timezone-aware form so the tests do not start warning on a newer CI image than the 3.9.6 on this machine (`python3 -V`).

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_validate_workspace.py -v`
Expected: the nine new tests FAIL; the existing ones still pass.

- [ ] **Step 3: Add the checks**

In `validate-workspace.sh`, insert this block inside the `if [ -n "$POST_CLOSE" ]; then` section, after the existing marker and scratch checks. It needs a numeric reader alongside the existing `json_str`:

```sh
# Read one JSON number by key, including one nested a single level down.
json_num() {
  grep -o "\"$2\"[[:space:]]*:[[:space:]]*-\{0,1\}[0-9][0-9]*" "$1" 2>/dev/null \
    | head -1 | sed 's/.*:[[:space:]]*//'
}
json_num_in() {
  # $2 = outer key, $3 = inner key. The record is written one field per line by close-run.sh,
  # and the two objects that nest — matches and by_source — are each on one line.
  grep -o "\"$2\"[[:space:]]*:[[:space:]]*{[^}]*}" "$1" 2>/dev/null \
    | grep -o "\"$3\"[[:space:]]*:[[:space:]]*[0-9][0-9]*" | head -1 | sed 's/.*:[[:space:]]*//'
}
```

Then:

```sh
  record="$WS/runs/$POST_CLOSE.json"
  if [ -f "$record" ]; then
    rel="runs/$POST_CLOSE.json"

    # Every count field has to be there before it can be compared.
    for field in postings_surfaced postings_reviewed postings_unreviewed postings_detail_read \
                 filtered_out; do
      [ -n "$(json_num "$record" "$field")" ] || invalid "$rel" "missing-key $field"
    done
    grep -q '"matches"[[:space:]]*:' "$record"   || invalid "$rel" "missing-key matches"
    grep -q '"by_source"[[:space:]]*:' "$record" || invalid "$rel" "missing-key by_source"

    # Compare the record against the log it describes. A record can be internally consistent and
    # still be uniformly wrong, so the comparison is against the events, not against itself.
    counts=$(sh "$(dirname "$0")/../../job-search-run/scripts/run-counts.sh" \
               "$WS/jobs.jsonl" "$POST_CLOSE" 2>/dev/null)
    if [ -n "$counts" ]; then
      logval() { printf '%s\n' "$counts" | grep "^$1=" | cut -d= -f2; }
      for pair in postings_surfaced postings_reviewed postings_unreviewed \
                  postings_detail_read filtered_out; do
        want=$(logval "$pair"); got=$(json_num "$record" "$pair")
        [ -z "$want" ] || [ -z "$got" ] || [ "$want" = "$got" ] || \
          invalid "$rel" "counts-disagree-with-log $pair $got vs $want"
      done
      for b in strong moderate weak; do
        want=$(logval "match_$b"); got=$(json_num_in "$record" matches "$b")
        [ -z "$want" ] || [ -z "$got" ] || [ "$want" = "$got" ] || \
          invalid "$rel" "counts-disagree-with-log matches.$b $got vs $want"
      done

      surfaced=$(json_num "$record" postings_surfaced)
      reviewed=$(json_num "$record" postings_reviewed)
      unreviewed=$(json_num "$record" postings_unreviewed)
      filtered=$(json_num "$record" filtered_out)
      s=$(json_num_in "$record" matches strong)
      m=$(json_num_in "$record" matches moderate)
      w=$(json_num_in "$record" matches weak)
      if [ -n "$reviewed" ] && [ -n "$filtered" ] && [ -n "$s" ] && [ -n "$m" ] && [ -n "$w" ]; then
        [ $((s + m + w + filtered)) -eq "$reviewed" ] || \
          invalid "$rel" "bands-do-not-sum-to-reviewed $((s + m + w + filtered)) vs $reviewed"
      fi
      if [ -n "$surfaced" ] && [ -n "$reviewed" ] && [ -n "$unreviewed" ]; then
        [ $((reviewed + unreviewed)) -eq "$surfaced" ] || \
          invalid "$rel" "reviewed-plus-unreviewed-is-not-surfaced $((reviewed + unreviewed)) vs $surfaced"
      fi
      rowsnew=$(logval rows_new_total)
      [ -z "$surfaced" ] || [ -z "$rowsnew" ] || [ "$surfaced" = "$rowsnew" ] || \
        invalid "$rel" "surfaced-does-not-match-rows-new $surfaced vs $rowsnew"
    fi

    # A timestamp read before a file is written cannot be later than that file.
    sa=$(json_str "$record" started_at)
    ca=$(json_str "$record" completed_at)
    if [ -n "$sa" ] && [ -n "$ca" ]; then
      [ "$ca" \> "$sa" ] || [ "$ca" = "$sa" ] || \
        invalid "$rel" "completed-at-before-started-at $ca"
      ref=$(mktemp) || exit 2
      stamp=$(printf '%s\n' "$ca" | sed 's/[-:]//g; s/T\(..\)\(..\)\(..\)Z/\1\2.\3/')
      if TZ=UTC touch -t "$stamp" "$ref" 2>/dev/null && [ "$ref" -nt "$record" ]; then
        invalid "$rel" "completed-at-after-the-file-that-states-it $ca"
      fi
      rm -f "$ref"
    fi
  fi
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_validate_workspace.py -v`
Expected: all PASS, existing tests included.

- [ ] **Step 5: Confirm the gate catches the real defective record**

```bash
cp -r ~/.job-search /tmp/defective-run-check
sh skills/job-search-runbook/scripts/validate-workspace.sh /tmp/defective-run-check \
  --post-close 2026-08-05T02-59-42Z; echo "exit=$?"
rm -rf /tmp/defective-run-check
```

Expected: a non-zero exit reporting `missing-key postings_surfaced` and `completed-at-after-the-file-that-states-it 2026-08-05T03:15:00Z`. Both halves were re-measured on 2026-08-06 and still hold: `grep completed_at` gives `2026-08-05T03:15:00Z` against an mtime of `2026-08-05T03:06:50Z`. If the workspace has moved on since, skip this step and say so rather than reporting a check you did not run.

- [ ] **Step 6: Confirm both `test` operators on the CI runner**

`[ "$ca" \> "$sa" ]` and `[ "$ref" -nt "$record" ]` are both outside POSIX `test`. Measured on this machine on 2026-08-06: `dash` supports both — `dash -c '[ b \> a ]'` exits 0, and `[ newer -nt older ]` is true given a real mtime gap. An earlier note in the spec called `-nt` unverified; it is verified on macOS `dash` and what remains is the Linux runner.

Run: `python3 -m pytest tests/test_validate_workspace.py -k "completed_at_later or completed_at_before" -v` under Linux — in CI or a container.

If `-nt` fails there, replace the `touch -t` reference-file comparison with `find "$record" -newermt "$ca"` behind a capability probe, keeping the `touch`/`-nt` path as the fallback, and note that `-newermt` is GNU `find` and absent on macOS, which is why it cannot simply replace the current path. Do not remove the gate.

- [ ] **Step 7: Commit**

```bash
git add skills/job-search-runbook/scripts/validate-workspace.sh tests/test_validate_workspace.py
git commit -m "feat(runbook): fail a run record whose counts or timestamps contradict its log"
```

---

### Task 11: `pipeline-counts.sh`

**Files:**
- Create: `skills/job-search/scripts/pipeline-counts.sh`, `skills/job-search/scripts/pipeline-counts.awk`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `jobs.jsonl` across all runs; `event-field.awk` from `job-search-run/scripts/`.
- Produces: `pipeline-counts.sh <jobs.jsonl>` prints `new=`, `interested=`, `applied=`, `rejected=`, `archived=`, `to_confirm=`, one per line.

**A posting is in the pipeline when its last judgment says it is relevant, or when the user has reacted to it.** `record-judgment.sh` writes `"status":"new"` on every judgment, a rejection included — the status is the funnel's starting state, not a claim about relevance, and making the event shape conditional would cost the uniform field set the whole design rests on. So the filter lives here. Without it the home card's `new` count is dominated by rejects: this change makes a run write a line for every posting it surfaced instead of only the handful it read, so `new` would jump from around nine to around fifty, nearly all of them postings the run threw out.

The second clause matters because the user can react to a rejected posting — `job-search/SKILL.md:161`, "already applied there" — and that reaction pulls it in.

`to_confirm` counts over the same filtered set. A rejected posting whose judgment set `needs_human_check` is not surfaced anywhere by this change; the home card's `(<k> to confirm)` sits on the Pipeline line, and a count that included non-pipeline postings would not reconcile with the numbers beside it. Surfacing those is a later change, not this one.

- [ ] **Step 1: Write the failing tests**

```python
PIPELINE = SEARCH_SCRIPTS / "pipeline-counts.sh"


def pipeline(jobs):
    r = run_script(PIPELINE, jobs)
    return r, dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)


def ev(source_id, **kw):
    d = {"event": "evaluated", "source": "linkedin", "source_id": source_id,
         "relevant": True, "match": "strong", "needs_human_check": False, "status": "new"}
    d.update(kw)
    return json.dumps(d)


def test_the_last_line_for_a_posting_wins(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(ev("a") + "\n" +
                    '{"event":"status_changed","source":"linkedin","source_id":"a",'
                    '"status":"applied"}\n')
    r, p = pipeline(jobs)
    assert r.returncode == 0, r.stderr
    assert p["applied"] == "1" and p["new"] == "0"


def test_a_posting_judged_not_relevant_is_not_in_the_pipeline(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(ev("a") + "\n" + ev("b", relevant=False, match=None) + "\n")
    _, p = pipeline(jobs)
    assert p["new"] == "1"
    assert sum(int(v) for v in p.values()) == 1


def test_a_rejected_posting_the_user_reacts_to_enters_the_pipeline(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(ev("b", relevant=False, match=None) + "\n" +
                    '{"event":"status_changed","source":"linkedin","source_id":"b",'
                    '"status":"applied"}\n')
    _, p = pipeline(jobs)
    assert p["applied"] == "1" and p["new"] == "0"


def test_surfaced_rows_without_a_judgment_are_not_in_the_pipeline(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"surfaced","source":"linkedin","source_id":"a"}\n'
        '{"event":"call","route":"search-jobs","ok":true}\n'
        '{"event":"queued","source":"linkedin","source_id":"a"}\n')
    _, p = pipeline(jobs)
    assert p["new"] == "0" and p["applied"] == "0"


def test_to_confirm_counts_pipeline_judgments_needing_a_human(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(ev("a", needs_human_check=True) + "\n" +
                    ev("b", match="weak") + "\n" +
                    ev("c", relevant=False, match=None, needs_human_check=True) + "\n")
    _, p = pipeline(jobs)
    assert p["to_confirm"] == "1" and p["new"] == "2"


def test_a_second_posting_for_the_same_role_is_counted_once(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(ev("a", source="ashby") + "\n" +
                    ev("b", source="ashby", same_role_as="ashby:a") + "\n")
    _, p = pipeline(jobs)
    assert p["new"] == "1"


def test_an_empty_log_prints_zeroes(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r, p = pipeline(jobs)
    assert r.returncode == 0
    assert p == {"new": "0", "interested": "0", "applied": "0",
                 "rejected": "0", "archived": "0", "to_confirm": "0"}
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k pipeline -v`
Expected: FAIL — the script does not exist.

- [ ] **Step 3: Write `pipeline-counts.sh`**

```sh
#!/bin/sh
# pipeline-counts.sh — print how many postings sit in each state, for the home view.
#
# Usage: pipeline-counts.sh <jobs.jsonl>
#
# Prints one key=value per line: new, interested, applied, rejected, archived, to_confirm.
#
# A posting can have several lines — the judgment the run that found it wrote, then a
# status_changed line when the user says they applied somewhere. Its current state is the last line
# sharing its source and source_id. A posting that names another in same_role_as is the same
# opening seen twice and counts once, under the one that was read.
#
# A posting the run judged not relevant is not in the pipeline. Its judgment still carries
# status new — that is the funnel's starting state, not a claim about relevance — and a run now
# writes a line for every posting it surfaced, so counting by status alone would fill `new` with
# postings the run threw out. A posting the user has reacted to is in the pipeline whatever the
# run decided, because the reaction is the more recent and better-informed answer.
#
# The event log grows past what a context window holds, so nothing reads it directly to work this
# out.
set -u

here=$(dirname "$0")
lib=$here/../../job-search-run/scripts/event-field.awk

jobs=${1:?usage: pipeline-counts.sh <jobs.jsonl>}
[ -f "$jobs" ] || { printf 'pipeline-counts.sh: no such file: %s\n' "$jobs" >&2; exit 2; }

exec awk -f "$lib" -f "$here/pipeline-counts.awk" "$jobs"
```

- [ ] **Step 4: Write `pipeline-counts.awk`**

```awk
# pipeline-counts.awk — see pipeline-counts.sh.

{
  ev = jval($0, "event")
  if (ev != "evaluated" && ev != "status_changed") next
  k = jval($0, "source") "|" jval($0, "source_id")
  if (!(k in seen)) { seen[k] = 1; n++; order[n] = k }

  if (ev == "evaluated")      rel[k] = jval($0, "relevant")
  if (ev == "status_changed") reacted[k] = 1

  s = jval($0, "status");            if (s != "") status[k] = s
  h = jval($0, "needs_human_check"); if (h != "") human[k] = h
  r = jval($0, "same_role_as")
  if (r != "") { split(r, p, ":"); alias[k] = p[1] "|" p[2] }
}

END {
  for (i = 1; i <= n; i++) {
    k = order[i]
    if (k in alias) continue                      # the same opening, counted under the row that was read
    if (rel[k] != "true" && !(k in reacted)) continue
    s = status[k]
    if (s == "") s = "new"
    count[s]++
    if (human[k] == "true") confirm++
  }
  printf "new=%d\n",         count["new"]+0
  printf "interested=%d\n",  count["interested"]+0
  printf "applied=%d\n",     count["applied"]+0
  printf "rejected=%d\n",    count["rejected"]+0
  printf "archived=%d\n",    count["archived"]+0
  printf "to_confirm=%d\n",  confirm+0
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k pipeline -v`
Expected: all seven PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search/scripts/pipeline-counts.sh skills/job-search/scripts/pipeline-counts.awk \
        tests/test_mechanics_scripts.py
git commit -m "feat(job-search): count the pipeline with a script instead of reading the whole log"
```

---

### Task 12: `job-search-runbook/SKILL.md`

**Files:**
- Modify: `skills/job-search-runbook/SKILL.md:48-59` (the file table), `:61-84` ("One run, start to close"), `:96-98` (Scratch), `:100-103` (What stays off disk)

**Interfaces:**
- Consumes: `open-run.sh`, `close-run.sh`, `clear-run.sh` (Tasks 8, 9).
- Produces: prose the run skill reads. No script or test consumes this file.

**This task's result is graded by the live behavior evals in Task 17, never by a string match.** Do not add a test that greps this file for a phrase.

- [ ] **Step 1: Rewrite "One run, start to close"**

The five numbered steps become four. Keep the numbered-prose shape; do not turn it into a checklist.

1. **Look for a leftover marker** — `ls <workspace>/runs/.started-* 2>/dev/null`. A marker there belongs to a run that stopped before it could close. Say that the last run did not finish, delete the marker, and go on with this run.
2. **Open the run** — run `skills/job-search-runbook/scripts/open-run.sh <workspace>`. It prints `run_id`, `started_at` and `brief_revision`; carry those three values through the run. Exit 1 means the run is open and the workspace findings printed after those three lines: report them in plain language and close `blocked`. Exit 2 means there is no `config.yaml`, so setup has not run and there is nothing to write into.
3. **Do the run's work**, recording events as you go.
4. **Close, in three steps and this order.** `skills/job-search-runbook/scripts/close-run.sh <workspace> <run_id> --trigger … --close-state …`, passing `--brief-revision`, `--sources` and `--queries` from step 2 and the run — it writes the record, works out `run_health` and prints it, and refuses a `complete` close over unjudged postings, naming how many. Then the digest, which the run skill defines. Then `skills/job-search-runbook/scripts/clear-run.sh <workspace> <run_id>`, which deletes the marker and the scratch directory. Then `skills/job-search-runbook/scripts/validate-workspace.sh <workspace> --post-close <run_id>`, fixing whatever it prints.

Say why the order is what it is, in one sentence: the digest is written between the record and the clearing because it carries `run_health` from the record and may still need the responses in the scratch directory.

Then state what the model still supplies: `trigger`, `scheduler_id`, `close_state`. Every count and both timestamps come from the log and the clock.

- [ ] **Step 2: Rewrite the file table's `jobs.jsonl` row**

Replace "a posting's current state is the fold of its events by `source` + `source_id`" with a plain statement. The rule: a posting can have several lines, and its current state is the last line sharing its `source` and `source_id`. Name the five event types a run writes — `call`, `surfaced`, `queued`, `detail`, `evaluated` — plus `status_changed` for what the user tells it.

- [ ] **Step 3: Remove full job descriptions from the off-disk list**

`:103` currently lists "API keys and auth headers, pagination cursors, full job descriptions, preference text anywhere but `preferences.md`". Drop "full job descriptions" and keep the rest. Add one sentence saying a posting's text is stored on its `detail` event so a changed brief can be re-applied without paying to read the posting again.

- [ ] **Step 4: Update the Scratch section**

`:96-98` says step 4 deletes the scratch. Step 4's third part does — name `clear-run.sh`, and drop "plus the posting lines you cite", because a posting's text now lives on its `detail` event.

- [ ] **Step 5: Check the word count**

Run: `wc -w skills/job-search-runbook/SKILL.md skills/*/SKILL.md`
The runbook was 986 words and the corpus 9,092. Record both numbers in the commit message.

- [ ] **Step 6: Run the doc gates**

Run: `python3 scripts/doc_lint.py --root . && python3 scripts/philosophy_guard.py --root . && python3 -m pytest tests/test_skill_frontmatter.py tests/test_reference_resolution.py -q`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add skills/job-search-runbook/SKILL.md
git commit -m "docs(runbook): open and close a run with the scripts that read the clock and the log"
```

---

### Task 13: `job-search-run/SKILL.md` and the event templates

**Files:**
- Modify: `skills/job-search-run/SKILL.md:32-44` (Search), `:46-55` (Reconcile), `:56-65` (Scan), `:66-95` (Read and judge), `:98-129` (Digest), `:131-145` (Close)
- Modify: `skills/job-search-run/templates/jobs-event.example.json`

**Interfaces:**
- Consumes: every script from Tasks 1–9.
- Produces: prose. Graded by the evals in Task 17, never by a string match.

- [ ] **Step 1: Replace the template with one example per event type**

`templates/jobs-event.example.json` currently holds one `evaluated` line. Make it hold one line per event type a run writes — `call`, `surfaced`, `queued`, `detail`, `evaluated` — using the shapes at the top of this plan, each with every field filled with a realistic value and a fictional company. Truncate the `detail` line's `description_markdown` to a sentence with a trailing note that the real one is the posting's full text; a multi-kilobyte template is not readable.

The `evaluated` example must show the field order the scripts write, since that order is what keeps a reader from finding a key inside free text: every field a script decides on before `dealbreakers_hit`, `unknowns` and `reasoning`.

- [ ] **Step 2: Rewrite Search**

After each `search-jobs` call, the response goes to `runs/.scratch/<run_id>/` and then through `skills/job-search-run/scripts/record-api-response.sh <run_id> <workspace>/jobs.jsonl <response> --route search-jobs --query-id <id>`. That records the call and every row it returned. A non-zero exit means the call failed or a row was unusable, and it says which — nothing was recorded but the call.

State the capture form, which is new: a failed call writes its body to stderr and exits 1, so the call is `agent-data call … > <response>.json 2> <response>.err` and the error file is what goes to `record-api-response.sh` when the call failed.

The source-echo check stays: compare `data.query.source` against the source asked for.

- [ ] **Step 3: Delete Reconcile's known-ids step**

`record-api-response.sh` skips a posting already carrying a judgment from any run and one this run already surfaced, so the by-hand known-ids step and the `dedup.sh <jobs> <source>` call go. Keep `dedup.sh --near` for one opening posted in several cities, which is still the model's call.

- [ ] **Step 4: Rewrite Scan**

Judge every surfaced row from what the row carries. A row that plainly breaks a must-have the brief names is settled right there with `record-judgment.sh … --detail-read false --relevant false`, with no detail read. Everything else goes through `queue-detail-read.sh <jobs> --run-id … --source … --source-id …`.

Delete the steer — the provisional read and the question the read has to answer, at `:57-65` and `:73`. Nothing about the expected judgment is passed to the reader.

This section is now the only thing deciding whether a posting costs a detail call, so say plainly that settling a row here is what keeps detail reads few. Task 18 step 5 measures whether it holds.

- [ ] **Step 5: Rewrite Read and judge**

The read list is `skills/job-search-run/scripts/list-detail-read-queue.sh <jobs> <run_id>`, which prints one tab-separated line per posting still to read: `source`, `source_id`, `posting_id_at_seen`, `source_url`, `title`, `company_name`. Brief each reader with its line, the path to `preferences.md`, and the `evaluate-job-fit` skill — the reader has none of this session's context, so the line is the whole brief.

Each detail response goes through `record-api-response.sh … --route get-posting`, which stores the posting's text. Each judgment goes through `record-judgment.sh` with the fields `evaluate-job-fit` returned. Delete the 20-field event list at `:76-95` — nothing hand-writes a `jobs.jsonl` line any more, and the script copies the posting's title, company, location, URL and date off the row that surfaced it.

- [ ] **Step 6: Rewrite the Digest**

Both halves of the digest read from the log.

The counts line is built from `skills/job-search-run/scripts/run-counts.sh <jobs> <run_id>`: `postings_surfaced` opens it, then `match_strong`, `match_moderate`, `match_weak`, `filtered_out`, the `by_source_*` values, and `calls_total_metered` on the usage line. When `postings_unreviewed` is not zero, the digest says how many postings the run never judged. When `searches_never_succeeded` is not zero, a footnote names the searches in `searches_never_succeeded_ids` that never returned.

The postings under each heading come from `skills/job-search-run/scripts/run-matches.sh <jobs> <run_id>`, which prints one line per judged posting — band, source, source_id, title, company, location, URL, whether it needs a human, its date, and its reasoning — strong first, then moderate, weak, and the filtered-out ones. Render each section from the lines with that band. Nothing about a posting is written from memory of the run.

`Run health:` in the header is the `run_health=` line `close-run.sh` printed.

Keep the fenced digest shape. Update the example's numbers so the bands and filtered-out sum to the opening number.

- [ ] **Step 7: Rewrite Close**

Close is the runbook's four-part step 4: `close-run.sh`, then this digest, then `clear-run.sh`, then `validate-workspace.sh <workspace> --post-close <run_id>`. Delete the record-field prose at `:136-145` — the script writes those fields. Keep the sentence defining `trigger`, and the closing sentence about telling the user what the run found.

`run_health` is no longer prose here either; state that the script works it out, and that a run reads `degraded` when it closed anything but `complete`, left a posting unjudged, or had a search that never returned after its retries.

- [ ] **Step 8: Measure the corpus**

Run: `wc -w skills/*/SKILL.md`
Expected: the total is below 10,000. It was 9,092 before this plan. If it is above, cut prose the scripts have made unnecessary rather than compressing what is left.

- [ ] **Step 9: Run the doc gates and the whole unit suite**

Run: `python3 scripts/doc_lint.py --root . && python3 scripts/philosophy_guard.py --root . && python3 -m pytest -q`
Expected: clean, all green.

- [ ] **Step 10: Commit**

```bash
git add skills/job-search-run/SKILL.md skills/job-search-run/templates/jobs-event.example.json
git commit -m "docs(run): record the run's events with the scripts, and count from what they wrote"
```

---

### Task 14: `job-search/SKILL.md` and `job-search-agent/SKILL.md`

**Files:**
- Modify: `skills/job-search/SKILL.md:122-129` (Home)
- Modify: `skills/job-search-agent/SKILL.md:40-47` ("Explaining what a run spent"), `:50-58` (Symptom → fix)

**Interfaces:**
- Consumes: `pipeline-counts.sh` (Task 11), the record's new fields (Task 9).
- Produces: prose. Graded by the evals in Task 17.

- [ ] **Step 1: Rewrite the home view's read**

`:127` currently says to read "`jobs.jsonl` folded to one entry per `source` + `source_id` with the last line winning, counting a line that names another posting in `same_role_as` as that one role". Replace with a call to `skills/job-search/scripts/pipeline-counts.sh <workspace>/jobs.jsonl`, which prints `new`, `interested`, `applied`, `rejected`, `archived` and `to_confirm`. The rule about the last line winning stays in the runbook's file table, where it has its one home.

- [ ] **Step 2: Add the unreviewed line to the home card**

A newest record whose `postings_unreviewed` is not zero earns a line under the card saying how many postings that run never judged and offering to run again — the same shape as the existing `blocked`/`interrupted` line at `:150-152`.

- [ ] **Step 3: Say how a posting the user names is found**

The reaction row at `:161` tells the agent to append a `status_changed` event for "that posting's line in `jobs.jsonl`". Say how to find it now that the log is large: every `evaluated` event carries the posting's title, company, location and URL, so `grep` the company or the title in `jobs.jsonl` and take the `source` and `source_id` from the line that matches. Ask which one when more than one matches.

- [ ] **Step 4: Rewrite "Explaining what a run spent"**

`agent_data_usage` is now counted from the run's `call` events rather than reported, so the numbers in the record are what the run actually spent — retries, repeats and failed attempts included. Say that. The billing pointer and the rate table pointer stay as they are.

- [ ] **Step 5: Add two symptom rows**

| The digest says the run left postings unjudged | the run stopped before it finished, or a source failed partway | Its record's `postings_unreviewed` is how many; run the search again, which offers them once more because a posting with no judgment is not treated as already seen |
| The run says `degraded` but nothing looks wrong | a search never returned after its retries, so its postings were never seen at all | The digest's footnote names which search; the record's counts cover only what did return, and running again is what covers the rest |

- [ ] **Step 6: Run the gates**

Run: `python3 scripts/doc_lint.py --root . && python3 scripts/philosophy_guard.py --root . && python3 -m pytest -q && wc -w skills/*/SKILL.md`

- [ ] **Step 7: Commit**

```bash
git add skills/job-search/SKILL.md skills/job-search-agent/SKILL.md
git commit -m "docs(job-search,agent): count the pipeline with a script and report what a run spent from its calls"
```

---

### Task 15: `agent-data-reference/SKILL.md` — three facts the API has and the reference does not

**Files:**
- Modify: `skills/agent-data-reference/SKILL.md` (the row-shape table around `:40-50`, and "When a call fails" around `:64-75`)

**Interfaces:**
- Consumes: nothing.
- Produces: prose. Every script in this plan was written against these facts; the reference is where they belong, and the no-runtime fallback path has no other source for them.

All three were settled by live calls on 2026-08-05 and 2026-08-06 and are recorded in "What the live API actually returns" at the top of this plan.

- [ ] **Step 1: Add the row-shape row**

Ashby's `published_at` carries no timezone (`2026-08-05T04:37:31.446000`) where LinkedIn's does (`2026-08-04T00:00:00+00:00`). The existing date row at `:47` already says to take freshness from whichever field is present and the later one when both are; this adds that the two are not the same format, so comparing them as text works only because the date leads.

- [ ] **Step 2: Add the failure-capture row**

A failed call writes its body to **stderr** and exits non-zero; stdout is empty. Any recipe that wants to read `retryable`, `code` or `param` has to redirect stderr. Update the `get-posting` and `search-jobs` recipes to show the two-file form, `> resp.json 2> resp.err`.

- [ ] **Step 3: Add the request-id row**

`request_id` is at `meta.request_id` on a success and at `error.request_id` on a failure. Note also that `error.source` is the string `service` and is not a job source, so nothing may read a source from an error body.

- [ ] **Step 4: Check the word count and the gates**

Run: `wc -w skills/*/SKILL.md && python3 scripts/doc_lint.py --root . && python3 scripts/philosophy_guard.py --root .`
The reference was 1,497 words. Three table rows should cost under 80; if this pushes the corpus over 10,000, cut from `job-search-run` where the scripts replaced prose.

- [ ] **Step 5: Commit**

```bash
git add skills/agent-data-reference/SKILL.md
git commit -m "docs(agent-data): record where an error body goes and where a request id lives"
```

---

### Task 16: The language sweep

**Files:**
- Modify: `skills/job-search/evals/evals.json:65`, `docs/RELIABILITY.md:41,44,53`, `ARCHITECTURE.md:96`, `TESTING.md:302`, `INSTALL_FOR_HERMES.md:264`, `docs/design-docs/multi-harness-portability.md:588`, `skills/job-search-run/evals/evals.json:174,193,194`

Live files only. Dated design docs and dated plans keep their wording as written records — which is why `docs/superpowers/plans/2026-07-23-hermes-plugin-install.md:720` is **not** on this list, though an earlier draft of this plan had it there while stating the opposite rule two lines above. `evals/baseline/2026-07-30-red-baseline.md:178` ("the close state's presence and spelling") is literal — it means whether `complete` is spelled correctly — and stays.

- [ ] **Step 1: Replace "fold"**

Each of these stands in for a plain fact. Say the fact.

| File | Line | Now | Say instead |
|---|---|---|---|
| `skills/job-search/evals/evals.json` | 65 | "The pipeline counts are the fold of jobs.jsonl by source and source_id with the last line winning" | "The pipeline counts come from `pipeline-counts.sh`, which takes the last line for each source and source_id" |
| `docs/RELIABILITY.md` | 41 | "the event-log fold" | "working out a posting's current state from its lines" |
| `docs/RELIABILITY.md` | 44 | "the same event log always folds" | "the same event log always gives the same current state" |
| `docs/RELIABILITY.md` | 53 | "current state is computed by folding them by dedup key" | "current state is the last line for each dedup key" |
| `ARCHITECTURE.md` | 96 | "(known-ids / append / fold)" | "(the known-ids check, the event append, and working out current state)" |
| `TESTING.md` | 302 | "fold the state" | "work out the current state" |

- [ ] **Step 2: Replace "spelling"**

| File | Line | Now | Say instead |
|---|---|---|---|
| `INSTALL_FOR_HERMES.md` | 264 | "any `~`/`${VAR}` spelling of the same directory" | "any `~` or `${VAR}` form of the same directory" |
| `docs/design-docs/multi-harness-portability.md` | 588 | "headless/print-mode command spelling" | "the exact headless/print-mode command" |

- [ ] **Step 3: Remove the steer from the run skill's evals**

`skills/job-search-run/evals/evals.json`:
- `:194` grades the steer alone. Delete the assertion.
- `:193` lists everything a reader is briefed with. Remove only its steer clause; the rest still describes what `list-detail-read-queue.sh` emits, so rewrite it to name those six fields.
- `:174` is a strip-the-guidance control naming "the read-list steer in the scan section". Rewrite it to strip the scan's settle-or-queue instruction instead, which is what now decides whether a posting is read.

- [ ] **Step 4: Verify no live file still carries either term**

```bash
grep -rniE "\bfold(s|ed|ing)?\b" skills/ ARCHITECTURE.md TESTING.md docs/RELIABILITY.md AGENTS.md
grep -rniE "\bspelling" skills/ INSTALL_FOR_HERMES.md docs/design-docs/multi-harness-portability.md
grep -rn "steer" skills/job-search-run/
```

Expected: all three print nothing.

The second command does **not** sweep `docs/superpowers/plans/`, and that is deliberate rather than an oversight: this plan's own Step 2 table writes the word "spelling" four times, so a grep over that directory reports itself. Dated plans keep their wording anyway, which is the same reason the Hermes plan is off the file list.

- [ ] **Step 5: Leave `doc_lint.py` alone**

An earlier draft of this plan gave `DUP_SIGNATURES`' digest-counts-line entry (`scripts/doc_lint.py:284`) an owner of `skills/job-search-run/SKILL.md` and extended `DUP_ALLOW` to accept `job-search-run`. Do neither.

`doc_lint.py:249-271` says what `owner` means: it names the **reference skill** that owns a fact, and setting it switches on a second enforcement arm across the reference layer. The file records that only the job-source enum qualifies, "because only it is a fact a reference skill owns". `job-search-run` is not a reference skill; the signature's live holders are `skills/job-search-run/SKILL.md` and `examples/sample-digest.md`, neither of which the reference-layer arm iterates, so the change would enforce nothing. And `DUP_ALLOW` is tested before any signature (`doc_lint.py:349`), so adding `job-search-run` to it would exempt every KB-doc line mentioning that skill from all five signatures — a quiet loosening of a gate this plan has no reason to touch.

The first arm already guards the signature owner-agnostically, and it goes on doing so.

- [ ] **Step 6: Run the gates**

Run: `python3 scripts/doc_lint.py --root . && python3 scripts/philosophy_guard.py --root . && python3 -m pytest -q`

- [ ] **Step 7: Commit**

```bash
git add skills/job-search/evals/evals.json skills/job-search-run/evals/evals.json \
        docs/RELIABILITY.md ARCHITECTURE.md TESTING.md INSTALL_FOR_HERMES.md \
        docs/design-docs/multi-harness-portability.md
git commit -m "docs: say what the code does instead of naming it by metaphor"
```

---

### Task 17: The behavior evals

**Files:**
- Modify: `evals/behaviors.md`, `evals/cases/headless-run.yaml`, `evals/cases/kill-midrun.yaml`, `evals/cases/fault-503.yaml`
- Modify: `skills/job-search-run/evals/evals.json`, `skills/job-search/evals/evals.json`, `skills/job-search-agent/evals/evals.json`

**Everything a skill's prose governs is graded here, by reading the artifacts a run leaves behind.** No assertion may match a substring of a documentation file. This is the existing bar — `evals/behaviors.md:27` already states "No assertion may match substrings of documentation files", and `tests/test_mechanics_scripts.py`'s docstring says "Nothing here asserts how the reference documents word the same rules."

- [ ] **Step 1: Give B8 an assertion it can fail, covering both halves of the digest**

`evals/behaviors.md:39` row B8 is "jobs.jsonl conformance + digest numbers re-derive from it", graded by "validator + artifact check". It cannot currently fail, because nothing compares the two, and it only ever spoke about the numbers. Rewrite its grading method to:

> artifact check: for the run's `run_id`, `skills/job-search-run/scripts/run-counts.sh` over the captured `workspace/jobs.jsonl`, the count fields in the captured `workspace/runs/<run_id>.json`, and the numbers parsed out of the digest's counts line must all be the same. The postings the digest names under each band must be the postings `skills/job-search-run/scripts/run-matches.sh` prints for that band, matched on company and title. Plus `validate-workspace.sh --post-close <run_id>` exiting 0.

The listing half is the one the measured defect actually broke: §1(c) is a weak match reported with no weak row behind it.

- [ ] **Step 2: Add four behavior rows**

| id | behavior | case file | grading method |
|---|---|---|---|
| B17 | `completed_at` is a clock read: later than `started_at`, and no later than the run record's own mtime | headless-run.yaml | artifact check (parse both timestamps from the captured record; compare against its mtime) |
| B18 | every posting a search returned has a `surfaced` event, and every one the run judged has an `evaluated` event | headless-run.yaml | artifact check (count `search-jobs` responses in the transcript against `surfaced` events in the captured log) |
| B19 | a run that stops mid-flight reports how many postings it left unjudged, rather than closing as if it finished | kill-midrun.yaml | artifact check (`postings_unreviewed` in the record is non-zero and `close_state` is not `complete`) + grader-judged transcript (the follow-up session says how many were left) |
| B20 | a run whose detail reads all fail still finishes: every posting judged from its summary row, `close_state` complete and `run_health` healthy, with the failures in `agent_data_usage` | fault-503.yaml | artifact check (`postings_unreviewed` is 0, `agent_data_usage.detail_reads` is non-zero, `calls_failed` from `run-counts.sh` is non-zero, `run_health` is `healthy`) |

Add `B17, B18` to `headless-run.yaml`'s `behaviors:` list, `B19` to `kill-midrun.yaml`'s, and `B20` to `fault-503.yaml`'s alongside the `B7` it already carries.

B20 is the row that pins down the relaxed `run_health`. Under the pre-change rule a permanently failing detail read left the run degraded; under this one the run that judged every posting from its summary row reads healthy, and the failures are visible where they cost money rather than in a health word. If that is not the behavior wanted, B20 is where to say so — not `close-run.sh`.

- [ ] **Step 3: Update the shim scenarios in `skills/job-search-run/evals/evals.json`**

The `harness` paragraph says the result is read from the digest, `jobs.jsonl` and the run record. Add that the close is also checked by running `run-counts.sh` and `run-matches.sh` and comparing their output against the record and the digest.

Scenario 1's expectations currently include "Appends one evaluated event per judged row to jobs.jsonl, each with source, source_id, query_id, detail_read, and the judgment fields". Replace with expectations that read the artifacts:

- "Every row the search returned has a `surfaced` event carrying the row's own values"
- "Every posting the run judged has an `evaluated` event carrying the posting's title, company, location and URL, and every posting it read in full has a `detail` event"
- "The digest's counts line, the run record's counts, and `run-counts.sh` output are the same numbers"
- "The postings the digest lists under each band are the ones `run-matches.sh` prints for that band"
- "`postings_unreviewed` is zero and the close is `complete`"

Scenario 3 ("every returned row is already judged") still holds: `record-api-response.sh` skips a posting carrying an `evaluated` event from any run. Keep it and add "no `surfaced` event is written for a posting that already has a judgment".

Add a scenario: **a run killed after the search leaves an honest record.** Kill the run after the last `search-jobs` call, then run `close-run.sh … --close-state interrupted`, and expect the record's `postings_surfaced` to equal the rows the searches returned and `postings_unreviewed` to equal the same number.

- [ ] **Step 4: Update `skills/job-search/evals/evals.json` and `skills/job-search-agent/evals/evals.json`**

The home-view scenario's pipeline-count assertion reads whatever `pipeline-counts.sh` prints, not a hand-worked-out number, and gains one expectation: a posting the run judged not relevant is not among the pipeline counts. The agent skill's usage scenario asserts the reported `agent_data_usage` equals the record's, which now equals the `call` events.

- [ ] **Step 5: Check the case files still load**

Run: `python3 -m pytest tests/test_eval_cases.py tests/test_eval_harness.py -q && python3 scripts/eval_harness.py --root .`
Expected: clean. `eval_harness.py` is not a CI job, so nothing else catches a malformed scenario file.

- [ ] **Step 6: Commit**

```bash
git add evals/behaviors.md evals/cases/ skills/job-search-run/evals/evals.json \
        skills/job-search/evals/evals.json skills/job-search-agent/evals/evals.json
git commit -m "test(evals): grade the counts and the listings against the log the run actually wrote"
```

---

### Task 18: Run the evals and measure

**Files:** none modified unless a run finds a defect.

This is the task that decides whether the change works. Everything before it is unverified against a live model.

- [ ] **Step 1: Run the full unit suite and every gate**

```bash
python3 -m pytest -q
python3 scripts/philosophy_guard.py --root .
python3 scripts/doc_lint.py --root .
python3 scripts/check_release_integrity.py --root . --check-version-sync
python3 scripts/eval_harness.py --root .
```
Expected: all clean. Paste the actual output into the commit or the report; do not summarize it as passing without it.

- [ ] **Step 2: Re-measure the corpus**

```bash
wc -w skills/*/SKILL.md
```
The budget is 10,000 and the start was 9,092. Above 10,000 is a blocking defect — cut prose the scripts made unnecessary.

- [ ] **Step 3: Run the headless behavior eval on both models**

```bash
python3 evals/run_eval.py --case headless-run --model sonnet
python3 evals/run_eval.py --case headless-run --model haiku
```

For each result directory, check B8, B17 and B18 by hand against the captured `workspace/`:

```bash
D=evals/results/<the-run-dir>
RID=$(ls $D/workspace/runs/*.json | head -1 | xargs basename | sed 's/\.json$//')
sh skills/job-search-run/scripts/run-counts.sh $D/workspace/jobs.jsonl $RID
sh skills/job-search-run/scripts/run-matches.sh $D/workspace/jobs.jsonl $RID
cat $D/workspace/runs/$RID.json
sed -n '1,20p' $D/workspace/reports/*-digest.md
sh skills/job-search-runbook/scripts/validate-workspace.sh $D/workspace --post-close $RID; echo "exit=$?"
```
Expected: the three sets of numbers agree, every posting the digest names appears in `run-matches.sh` output under the same band, and the validator exits 0.

- [ ] **Step 4: Run the kill-midrun and fault-503 evals on both models**

```bash
for c in kill-midrun fault-503; do
  python3 evals/run_eval.py --case $c --model sonnet
  python3 evals/run_eval.py --case $c --model haiku
done
```
Expected (B19): the record's `postings_unreviewed` is non-zero, `close_state` is not `complete`, and the follow-up session says how many postings were left.
Expected (B20): `postings_unreviewed` is 0, `close_state` is `complete`, `run_health` is `healthy`, `agent_data_usage.detail_reads` is non-zero, and the digest's footnotes name the failed reads.

- [ ] **Step 5: Compare detail-call count against the RED baseline**

The spec records an inference that needs settling: `docs/superpowers/specs/2026-07-30-skill-overhaul-design.md:74` credits "summary-scan steer" with killing 65% of detail calls as one phrase, and this change removes the steer while keeping the scan.

From the `headless-run` results, take `postings_detail_read` and `postings_surfaced` from the record and compare the ratio against `evals/baseline/2026-07-30-red-baseline.md`. Report the actual numbers.

If detail reads rose materially, the scan's settle-or-queue instruction in `job-search-run/SKILL.md` is what to strengthen — not the steer, which anchored the reader rather than reducing reads. Re-run this step after any such edit.

- [ ] **Step 6: Run the remaining cases on both models**

```bash
for c in quickstart schedule fit; do
  python3 evals/run_eval.py --case $c --model sonnet
  python3 evals/run_eval.py --case $c --model haiku
done
python3 evals/run_triggering.py --model sonnet --reps 9
python3 evals/run_triggering.py --model haiku --reps 9
```
Expected: no regression against `evals/baseline/2026-07-30-red-baseline.md`. Two rows matter most here and both are about the size of this change:

- **B15** (every plugin file the agent opens resolves first try) — this plan adds ten script paths a skill's prose names: `record-api-response.sh`, `queue-detail-read.sh`, `list-detail-read-queue.sh`, `record-judgment.sh`, `run-counts.sh`, `run-matches.sh`, `open-run.sh`, `close-run.sh`, `clear-run.sh`, `pipeline-counts.sh`. Every one is a path that can be wrong. The seven `.awk` files are resolved by the wrappers, not by the agent, so they are not B15's problem — but a wrapper that cannot find its own program is, and that is what Task 1 step 6's `dash` run catches.
- **B13** (files and lines read before the first API call, target ~650) — those ten scripts are ten things the agent might read. Report the measured number against the baseline whether or not it moved.

- [ ] **Step 7: Confirm the fixtures carry nothing real**

```bash
grep -rniE "linkedin\.com/jobs/view|ashbyhq\.com/[a-z]|jobs\.lever\.co/[a-z]" tests/fixtures/ ; echo "exit=$?"
git status --porcelain evals/results | head
```
Expected: the first prints nothing. The second prints nothing — `.gitignore` carries `evals/results/`, and `git ls-files evals/results` returns only its own `.gitignore`.

- [ ] **Step 8: Write the result report**

Create `docs-private/2026-08-05-counts-eval-report.md` (gitignored) with, for each case and model: the run directory, whether each behavior row passed, the measured numbers, and every row that failed with what it did instead. State plainly what was not run.

- [ ] **Step 9: Commit**

```bash
git add skills/ tests/ evals/behaviors.md evals/cases/ docs/
git commit -m "test: run the behavior evals against the counted run"
```

---

## Self-review

**Spec coverage.** Every section of the spec maps to a task:

| Spec section | Task |
|---|---|
| §3 architecture — parsing the responses at all | 0 |
| §3 architecture — `call`, `surfaced` | 1 |
| §3 architecture — `detail` | 2 |
| §3 architecture — `queued` | 3 |
| §3 architecture — `evaluated` | 4 |
| §4 the run record and its four invariants | 5, 9, 10 |
| §5 timestamps and both gates | 8, 9, 10 |
| §6 opening a run validates the workspace | 8 |
| §7 a close that cannot contradict its log | 9 |
| §8 the detail-read queue | 3, 13 |
| §9 storing descriptions, and the off-disk rule reversal | 2, 12 |
| §10 file-by-file changes | 12, 13, 14 |
| §10 the two reproduced script conflicts | 7 |
| §10 the language sweep | 16 |
| §10 the word budget | 12, 13, 15, 18 |
| §11 where no shell runs | 1, 5, 7 (script headers) |
| §12 testing — unit | 0–11 |
| §12 testing — behavioral | 17, 18 |
| §12 testing — live | 1, 2 (fixtures captured from the real API, then scrubbed), 15 |
| §13 style anchoring | 12, 13, 14, 15 |

**What changed from the first draft of this plan, and why.** Each of these was a defect found by reviewing it, not a preference:

| Change | It fixes |
|---|---|
| Task 0's scanner replaces two hand-rolled line parsers | a parser that worked only on the CLI's current pretty-printing, and silently produced one garbage row otherwise |
| `--route` is a required flag | every failed detail read was recorded as a failed search, corrupting `agent_data_usage` |
| the repeat-detail branch emits its `call` event | a metered call the record did not count |
| `record-judgment.sh` copies five display fields | the digest and the home view lost the title, company, location and URL they render |
| `run-matches.sh` is new | the digest's listed postings still came from the model's memory of the run, which is what §1(c) got wrong |
| `clear-run.sh` splits off from `close-run.sh` | the record write deleted the scratch directory before the digest was written |
| `run_health` drops `calls_failed` for `searches_never_succeeded` | one transient failure made every run degraded forever, and `fault-503` could never close complete |
| `evaluated` is scoped to the run in `run-counts.sh` | a later run judging an earlier run's leftovers invalidated the earlier record |
| `pipeline-counts.sh` filters on relevance | the home card's `new` count would have filled with rejected postings |
| the string check on `source` and `source_id` | a numeric id would be surfaced and then unreachable by every script that looks one up |
| `close-run.sh` writes to a temp path and renames | a failed write left an empty record at the real path |
| fixtures are scrubbed | live company names, URLs and job descriptions in a public repo |
| tests derive counts from the fixture | a capture returning 24 rows instead of 25 turned the suite red |
| `doc_lint.py` is left alone | a change that enforced nothing and quietly widened an exemption |

**Type consistency.** `run-counts.sh`'s eighteen output keys are declared once at the top of this plan and consumed by name in Tasks 9, 10 and 13; seventeen are integers and `searches_never_succeeded_ids` is a comma list, which is why `close-run.sh` splits on the first `=` rather than every one. `run-matches.sh`'s ten columns are declared once and consumed in Tasks 13 and 17. The five event shapes are declared once and used in every task. `band` is the awk variable in Tasks 4, 5 and 6; `match` is only ever the JSON key. `record-api-response.sh` takes `<run_id> <jobs.jsonl> <response.json> --route …` in Tasks 1 and 2 alike.

**Four gaps this plan does not close, stated rather than hidden:**

1. **`--sources` and `--queries` still come from the model.** `close-run.sh` takes them as flags because a `call` event carries the source and query of each call, but a query that was enabled and never reached — a source dropped after two failures — has no call event to be counted from. Deriving them from the log would silently narrow the record. Task 18 step 3 should check whether the two fields match the config's enabled entries. Closing it properly means `close-run.sh` reading `config.yaml`, which would also let `searches_never_succeeded` cover a search that was never attempted at all, rather than only one that was attempted and never answered.

2. **Looking for a leftover marker stays in prose.** Task 12 step 1 keeps it as the runbook's step 1. The action it calls for — tell the user their last run did not finish — is a judgment, but the check itself is exactly the kind of mechanic this plan moves into scripts, and `open-run.sh` already owns the marker. A follow-on change can have `open-run.sh` report the leftover and let the prose decide what to say about it.

3. **A rejected posting that needs a human is not surfaced.** `pipeline-counts.sh` counts `to_confirm` over pipeline members only, so a `needs_human_check` on a posting the run threw out goes nowhere. Deliberate, and out of scope here.

4. **`test -nt` is verified on macOS `dash` and not on the CI runner.** Task 10 step 6 is the gate; the fallback is specified there, along with the reason it cannot simply replace the current path (`find -newermt` is GNU-only).

**Placeholder scan:** no "TBD", no "add appropriate error handling", no "similar to Task N". Every code step carries the code. Every prose step names the file, the lines, and what must be true of the result, and says which eval grades it. The one choice an earlier draft left open — whether `tmp_workspace` moves to a `conftest.py` or is copied — is settled in Task 0 step 5: it moves.









