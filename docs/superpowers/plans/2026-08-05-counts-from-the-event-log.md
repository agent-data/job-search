# Counts From The Event Log — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every count and every timestamp in a run out of the model's account of the run and into scripts that read the run's own append-only event log.

**Architecture:** `jobs.jsonl` gains four event types — `call`, `surfaced`, `queued`, `detail` — alongside the `evaluated` one it already holds. Scripts write every event: a search response becomes `surfaced` rows, a posting response becomes a `detail`, the model's judgment becomes an `evaluated`. `run-counts.sh` reads that log and prints the run's numbers; `close-run.sh` copies them into the run record; `validate-workspace.sh` recomputes them and fails a record that disagrees. The model supplies judgments, which postings to read, and three values at close.

**Tech Stack:** POSIX `sh` + `awk` for everything shipped inside a skill (no `jq`, no Python, no bash-isms). Stdlib-only Python 3 for the dev tooling in `tests/` and `evals/`. `pytest` for unit tests; the live behavior-eval harness in `evals/` for anything a skill's prose governs.

**Spec:** `docs/superpowers/specs/2026-08-05-counts-from-the-event-log-design.md`

## Global Constraints

- **Branch:** `feat/counts-from-the-event-log`. Never commit to `main`.
- **Shipped scripts are POSIX `sh` + `awk`.** No `jq`, no Python, no `bash` constructs. Tests invoke every script through `sh`, and through `dash` where present.
- **`match` is an `awk` built-in.** Never use it as an `awk` variable name — use `band`. This cost a debugging cycle during design.
- **`awk -v` cannot carry a literal newline.** Free text (reasoning, dealbreakers, unknowns) passes through the environment and is read with `ENVIRON[...]`.
- **Nothing is appended unless the whole response checks out.** A response with one bad row appends none of its rows. Every rejection exits non-zero and names the file, the row, and the field on stderr. The one exception is the `call` event, which is written for every attempt including a failed one.
- **Never assert on a skill's prose.** No test may grep a `SKILL.md` for a phrase, a sentence, or a regex standing in for a documented rule. Script behavior is tested with pytest against real artifacts; anything a skill's prose governs is graded by the live behavior evals in `evals/`. `tests/test_mechanics_scripts.py`'s own docstring already states this: "Nothing here asserts how the reference documents word the same rules."
- **Word budget:** `AGENTS.md` sets 10,000 words across the seven `SKILL.md` files. `wc -w skills/*/SKILL.md` reports 9,092 at the start of this plan. Exceeding 10,000 at the end is a blocking defect.
- **Public repo, MIT, © Aptiq Labs, Inc.** No tracked file — not a doc, not a commit message — mentions a hosted or commercial product. This is a counting and timestamp fix.
- **Prose voice.** The `SKILL.md` files are continuous prose read by a model at runtime. Do not restructure them into checklists or add headings that were not there.
- **No metaphors, no invented jargon.** Say what the code does. "The last line for a `source` and `source_id` wins", never "the fold". Personification is the same failure: a gate does not see, a contract does not know.
- **Never state a measurable fact without running the command that settles it.** Cite the command next to the number.
- Unchanged: the `strong / moderate / weak` vocabulary; `run_id`'s format (`2026-07-30T15-04-02Z`); `.scratch/` and `.started-<run_id>` semantics. No token or cost field is added.

## The event shapes every task depends on

Single-line JSON, one event per line, appended to `<workspace>/jobs.jsonl`.

```
{"event":"call","run_id":"2026-08-05T16-47-00Z","ts":"2026-08-05T16:47:14Z","route":"search-jobs","source":"linkedin","query_id":"strategic-finance-sf","ok":true,"rows_returned":25,"rows_new":25,"request_id":"req_9a79bdf4a26f4e98854f259d"}
{"event":"surfaced","run_id":"…","query_id":"…","source":"linkedin","source_id":"4449006488","posting_id_at_seen":"jp_74856f265f40","source_url":"…","title":"…","company_name":"…","location_display":"…","salary_display":null,"employment_type":null,"department_name":null,"team_name":null,"is_remote":null,"workplace_type":null,"posted_at":"2026-08-04T00:00:00+00:00","detail_available":true}
{"event":"queued","run_id":"…","source":"linkedin","source_id":"4449006488","ts":"…"}
{"event":"detail","run_id":"…","source":"linkedin","source_id":"4449006488","description_markdown":"…","employment_type":"…","apply_url":"…","is_listed":true,"is_remote":null,"workplace_type":null,"staleness_status":"fresh"}
{"event":"evaluated","run_id":"…","source":"linkedin","source_id":"4449006488","detail_read":true,"relevant":true,"match":"strong","reasoning":"…","dealbreakers_hit":[],"unknowns":["equity"],"needs_human_check":false,"status":"new","ts":"…"}
```

`status_changed` is unchanged.

## `run-counts.sh` output contract

Every consumer reads these exact keys. Task 5 produces them; Tasks 8 and 9 consume them.

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
rows_new_total=50
```

A relevant row carrying no band prints one extra line, `INVALID relevant-row-without-a-band=<n>`, and exits 1.

## File structure

| Path | Responsibility |
|---|---|
| `skills/job-search-runbook/scripts/open-run.sh` | mint `run_id` + `started_at` from one clock read, create the marker, take the brief revision, run the workspace checks |
| `skills/job-search-runbook/scripts/close-run.sh` | read the clock for `completed_at`, take counts from `run-counts.sh`, derive `run_health`, write the record, clear the marker and scratch |
| `skills/job-search-runbook/scripts/validate-workspace.sh` | *(modify)* the count fields, the four invariants, the two timestamp gates |
| `skills/job-search-run/scripts/record-api-response.sh` | one agent-data response → the events it implies |
| `skills/job-search-run/scripts/queue-detail-read.sh` | mark one posting as one to read in full |
| `skills/job-search-run/scripts/list-detail-read-queue.sh` | print the queued, not-yet-judged postings |
| `skills/job-search-run/scripts/record-judgment.sh` | record one posting's judgment |
| `skills/job-search-run/scripts/run-counts.sh` | this run's numbers, from the log |
| `skills/job-search-run/scripts/dedup.sh` | *(modify)* known set keys on `evaluated` events only |
| `skills/job-search-run/scripts/event-log-append.sh` | *(modify)* idempotency check looks only at `evaluated` lines |
| `skills/job-search/scripts/pipeline-counts.sh` | the home view's per-status counts |
| `tests/test_mechanics_scripts.py` | *(modify)* every new script, every failure path |
| `tests/test_validate_workspace.py` | *(modify)* the invariants and timestamp gates |
| `evals/cases/*.yaml`, `evals/behaviors.md` | the behavior rows that grade the prose |

---

### Task 1: `record-api-response.sh` — search responses

**Files:**
- Create: `skills/job-search-run/scripts/record-api-response.sh`
- Test: `tests/test_mechanics_scripts.py`
- Create: `tests/fixtures/api-responses/search.linkedin.json`, `search.ashby.json`, `search.zero.json`, `search.error.json`, `search.badrow.json`

**Interfaces:**
- Consumes: nothing.
- Produces: `record-api-response.sh <run_id> <jobs.jsonl> <response.json> [--query-id ID]`. Appends one `call` event always, then one `surfaced` event per new row. Exit 0 on success (including a search that legitimately returned zero rows); exit 1 with nothing but the `call` event appended when the response is an error or any row is unusable; exit 2 on a missing file or bad arguments.

- [ ] **Step 1: Capture real fixtures from the live API**

These four shapes were confirmed live on 2026-08-05 and are what the parser must absorb. Run:

```sh
L=f9a6ec16-0bfd-44d8-b3ee-073776745ee7
mkdir -p tests/fixtures/api-responses
agent-data call $L search-jobs --keywords "strategic finance" --location "San Francisco Bay Area" \
  --limit 25 --source linkedin > tests/fixtures/api-responses/search.linkedin.json
agent-data call $L search-jobs --keywords "strategic finance" --location "San Francisco" \
  --limit 25 --source ashby > tests/fixtures/api-responses/search.ashby.json
agent-data call $L search-jobs --keywords "zzzqqq nonexistent xyzzy" --limit 5 --source ashby \
  > tests/fixtures/api-responses/search.zero.json
agent-data call $L get-posting --posting_id jp_74856f265f40 \
  --source_url "https://jobs.ashbyhq.com/aiuc/3de3fbde-af29-48a3-9ec8-18811973ec86" \
  > tests/fixtures/api-responses/search.error.json 2>&1 || true
```

The last one is a mismatched `posting_id`/`source_url` pair, which returns a real `400 validation_error`. Then hand-write the bad-row fixture:

```json
{
  "data": {
    "results": [
      { "id": "jp_x", "title": "No id row", "source_url": "http://example/x" }
    ]
  }
}
```

Save it as `tests/fixtures/api-responses/search.badrow.json`. It is missing `source` and `source_id`.

The two live fixtures differ in exactly the ways the parser must handle: LinkedIn fills `posted_at` and leaves `published_at`, `salary_display`, `is_remote`, `workplace_type`, `employment_type`, `department_name` and `team_name` null on every row; Ashby is the reverse, and its `published_at` carries no timezone (`2026-08-05T04:37:31.446000`) where LinkedIn's does (`2026-08-04T00:00:00+00:00`).

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_mechanics_scripts.py`:

```python
import json

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


def test_search_response_appends_one_surfaced_event_per_row(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "search.linkedin.json",
                   "--query-id", "strategic-finance-sf")
    assert r.returncode == 0, r.stderr
    api = json.loads((FIXTURES / "search.linkedin.json").read_text())["data"]["results"]
    surfaced = [e for e in lines(jobs) if e["event"] == "surfaced"]
    assert len(surfaced) == len(api)
    assert {e["posting_id_at_seen"] for e in surfaced} == {row["id"] for row in api}


def test_surfaced_values_equal_the_api_values(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, RID, jobs, FIXTURES / "search.ashby.json", "--query-id", "q")
    api = {row["id"]: row for row in
           json.loads((FIXTURES / "search.ashby.json").read_text())["data"]["results"]}
    for e in [x for x in lines(jobs) if x["event"] == "surfaced"]:
        row = api[e["posting_id_at_seen"]]
        for key in ("title", "company_name", "location_display", "source_url", "source_id",
                    "salary_display", "employment_type", "is_remote", "workplace_type",
                    "department_name", "team_name"):
            assert e[key] == row.get(key), (e["posting_id_at_seen"], key)


def test_posted_at_takes_whichever_date_field_the_source_filled(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    for name in ("search.linkedin.json", "search.ashby.json"):
        run_script(RECORD_API, RID, jobs, FIXTURES / name, "--query-id", "q")
    api = {}
    for name in ("search.linkedin.json", "search.ashby.json"):
        for row in json.loads((FIXTURES / name).read_text())["data"]["results"]:
            api[row["id"]] = row
    for e in [x for x in lines(jobs) if x["event"] == "surfaced"]:
        row = api[e["posting_id_at_seen"]]
        p, q = row.get("posted_at"), row.get("published_at")
        expected = max(p, q) if p and q else (p or q)
        assert e["posted_at"] == expected


def test_error_response_fails_loudly_and_appends_no_rows(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "search.error.json", "--query-id", "q")
    assert r.returncode == 1
    assert "validation_error" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "surfaced"] == []


def test_error_response_still_records_the_call(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, RID, jobs, FIXTURES / "search.error.json", "--query-id", "q")
    calls = [e for e in lines(jobs) if e["event"] == "call"]
    assert len(calls) == 1
    assert calls[0]["ok"] is False


def test_zero_row_search_is_not_a_failure(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "search.zero.json", "--query-id", "q")
    assert r.returncode == 0, r.stderr
    calls = [e for e in lines(jobs) if e["event"] == "call"]
    assert calls[0]["ok"] is True and calls[0]["rows_returned"] == 0


def test_row_missing_source_id_appends_nothing_and_names_it(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "search.badrow.json", "--query-id", "q")
    assert r.returncode == 1
    assert "source_id" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "surfaced"] == []


def test_same_posting_from_two_queries_is_surfaced_once(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, RID, jobs, FIXTURES / "search.linkedin.json", "--query-id", "a")
    run_script(RECORD_API, RID, jobs, FIXTURES / "search.linkedin.json", "--query-id", "b")
    surfaced = [e for e in lines(jobs) if e["event"] == "surfaced"]
    keys = [(e["source"], e["source_id"]) for e in surfaced]
    assert len(keys) == len(set(keys))
    calls = [e for e in lines(jobs) if e["event"] == "call"]
    assert calls[1]["rows_returned"] == 25 and calls[1]["rows_new"] == 0


def test_a_posting_already_judged_in_an_earlier_run_is_not_surfaced_again(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    api = json.loads((FIXTURES / "search.linkedin.json").read_text())["data"]["results"]
    known = api[0]
    jobs.write_text(
        '{"event":"evaluated","run_id":"2026-01-01T00-00-00Z","source":"linkedin",'
        '"source_id":"%s","detail_read":true,"relevant":false,"match":null}\n' % known["source_id"]
    )
    run_script(RECORD_API, RID, jobs, FIXTURES / "search.linkedin.json", "--query-id", "q")
    surfaced = [e for e in lines(jobs) if e["event"] == "surfaced"]
    assert known["source_id"] not in {e["source_id"] for e in surfaced}
    assert len(surfaced) == len(api) - 1
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k record_api -v`
Expected: every test errors — `record-api-response.sh` does not exist.

- [ ] **Step 4: Write the script**

Create `skills/job-search-run/scripts/record-api-response.sh`:

```sh
#!/bin/sh
# record-api-response.sh — turn one agent-data response into the events it implies.
#
# Usage: record-api-response.sh <run_id> <jobs.jsonl> <response.json> [--query-id ID]
#
# A search-jobs response appends one `call` event and one `surfaced` event per new row, each value
# copied as the raw JSON it arrived as. A posting already judged in any run, and a posting this run
# already surfaced, are both skipped: one opening reached by two queries is one posting.
#
# The `call` event is written for every attempt, a failed one included — it is the record that the
# call happened, and what a run's metered-call count is worked out from. The rows are
# all-or-nothing: a response with one unusable row appends none of its rows.
#
# This is the scripted form of the model-run prose contract; that prose remains the no-runtime
# fallback, and a host with no shell states that its counts were worked out by hand.
#
# Exit 0: the rows were appended, or the search legitimately returned none.
# Exit 1: no rows appended; stderr names the problem. The call event is still recorded.
# Exit 2: bad arguments or a missing file.
set -u

usage() {
  printf 'usage: record-api-response.sh <run_id> <jobs.jsonl> <response.json> [--query-id ID]\n' >&2
}

[ $# -ge 3 ] || { usage; exit 2; }
run_id=$1; jobs=$2; resp=$3; shift 3
query_id=''
while [ $# -gt 0 ]; do
  case $1 in
    --query-id) [ $# -ge 2 ] || { usage; exit 2; }; query_id=$2; shift 2 ;;
    *) printf 'record-api-response.sh: unknown option %s\n' "$1" >&2; usage; exit 2 ;;
  esac
done

[ -f "$resp" ] || { printf 'record-api-response.sh: no such file: %s\n' "$resp" >&2; exit 2; }
dir=$(dirname "$jobs"); [ -d "$dir" ] || mkdir -p "$dir"
[ -f "$jobs" ] || : > "$jobs"

ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
req=$(grep -o '"request_id"[[:space:]]*:[[:space:]]*"[^"]*"' "$resp" | head -1 | cut -d'"' -f4)

# One `call` event per attempt. Built here so a failure below still leaves it behind.
emit_call() {
  RAR_QUERY=$query_id RAR_REQ=$req \
  awk -v run_id="$run_id" -v ts="$ts" -v route="$1" -v source="$2" \
      -v ok="$3" -v returned="$4" -v new="$5" '
    function esc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return s }
    function jstr(s) { return "\"" esc(s) "\"" }
    BEGIN {
      out = "{\"event\":\"call\",\"run_id\":" jstr(run_id) ",\"ts\":" jstr(ts)
      out = out ",\"route\":" jstr(route)
      out = out ",\"source\":" (source == "" ? "null" : jstr(source))
      if (ENVIRON["RAR_QUERY"] != "") out = out ",\"query_id\":" jstr(ENVIRON["RAR_QUERY"])
      out = out ",\"ok\":" ok
      out = out ",\"rows_returned\":" returned ",\"rows_new\":" new
      out = out ",\"request_id\":" (ENVIRON["RAR_REQ"] == "" ? "null" : jstr(ENVIRON["RAR_REQ"]))
      out = out "}"
      print out
    }' >> "$jobs"
}

# Which shape is this? A failed call is not an empty result, and must not read as one.
if grep -q '^[ \t]*"error"[ \t]*:' "$resp"; then
  code=$(grep -o '"code"[[:space:]]*:[[:space:]]*"[^"]*"' "$resp" | head -1 | cut -d'"' -f4)
  msg=$(grep -o '"message"[[:space:]]*:[[:space:]]*"[^"]*"' "$resp" | head -1 | cut -d'"' -f4)
  route=search-jobs
  grep -q '"description_markdown"' "$resp" && route=get-posting
  emit_call "$route" '' false 0 0
  printf 'record-api-response.sh: the response is an error, not results: %s — %s\n' \
    "${code:-unknown}" "${msg:-no message}" >&2
  exit 1
fi

grep -q '^[ \t]*"results"[ \t]*:' "$resp" || {
  printf 'record-api-response.sh: no results array in %s — this is not a search-jobs response\n' \
    "$resp" >&2
  exit 2
}

new=$(mktemp) || exit 2
bad=$(mktemp) || exit 2
keep=$(mktemp) || exit 2
trap 'rm -f "$new" "$bad" "$keep"' EXIT INT HUP TERM

awk -v run_id="$run_id" -v query_id="$query_id" -v badfile="$bad" '
  function esc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return s }
  function fld(k) { return (k in v && v[k] != "") ? v[k] : "null" }

  # Walk the response one character at a time, tracking how deep we are and whether we are inside
  # a string, so a brace inside a job title cannot be mistaken for structure.
  {
    line = $0
    n = length(line)
    for (i = 1; i <= n; i++) {
      c = substr(line, i, 1)
      if (instr) {
        if (c == "\\") { i++; continue }
        if (c == "\"") instr = 0
        continue
      }
      if (c == "\"") { instr = 1; continue }
      if (c == "{" || c == "[") { depth++; if (depth == 4 && inresults) rowopen = 1; continue }
      if (c == "}" || c == "]") {
        if (depth == 4 && inresults && rowopen) { emit(); rowopen = 0 }
        if (depth == 3 && inresults) inresults = 0
        depth--
        continue
      }
    }
    if (match(line, /^[ \t]*"[^"]+"[ \t]*:/)) {
      key = line; sub(/^[ \t]*"/, "", key); sub(/".*$/, "", key)
      val = line; sub(/^[ \t]*"[^"]+"[ \t]*:[ \t]*/, "", val); sub(/,[ \t]*$/, "", val)
      if (key == "results" && depth >= 3) inresults = 1
      else if (rowopen && val != "") v[key] = val
    }
  }

  function emit(   out, p, q, eff, missing, k, i, req) {
    rows++
    # Every row has to carry the four values the rest of the run is keyed on.
    missing = ""
    split("source source_id id source_url", req, " ")
    for (i = 1; i <= 4; i++) {
      k = req[i]
      if (!(k in v) || v[k] == "" || v[k] == "null") missing = missing (missing == "" ? "" : ", ") k
    }
    if (missing != "") {
      printf "row %d is missing %s (title %s, company %s)\n", rows, missing,
             (("title" in v) ? v["title"] : "absent"),
             (("company_name" in v) ? v["company_name"] : "absent") >> badfile
      delete v
      return
    }

    p = v["posted_at"]; q = v["published_at"]; eff = "null"
    if (p != "" && p != "null" && q != "" && q != "null") eff = (p > q ? p : q)
    else if (p != "" && p != "null") eff = p
    else if (q != "" && q != "null") eff = q

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
    out = out "}"
    print out
    delete v
  }
  END { print rows+0 > badfile ".count" }
' "$resp" > "$new"

returned=$(cat "$bad.count" 2>/dev/null || echo 0)
rm -f "$bad.count"
src=$(head -1 "$new" 2>/dev/null | sed -n 's/.*"source":"\([^"]*\)".*/\1/p')

if [ -s "$bad" ]; then
  emit_call search-jobs "$src" true "$returned" 0
  printf 'record-api-response.sh: nothing was appended — %s\n' "$resp" >&2
  sed 's/^/record-api-response.sh:   /' "$bad" >&2
  exit 1
fi

# Skip a posting this run already surfaced, and one any run has already judged.
awk -v jobs="$jobs" -v run_id="$run_id" '
  function val(line, key,   v) {
    v = line
    if (v !~ ("\"" key "\":")) return ""
    sub(".*\"" key "\":", "", v)
    if (substr(v, 1, 1) == "\"") { sub(/^"/, "", v); sub(/".*$/, "", v) }
    else sub(/[,}].*$/, "", v)
    return v
  }
  BEGIN {
    while ((getline line < jobs) > 0) {
      ev = val(line, "event")
      k = val(line, "source") "|" val(line, "source_id")
      if (ev == "surfaced" && val(line, "run_id") == run_id) have[k] = 1
      else if (ev == "evaluated") have[k] = 1
    }
    close(jobs)
  }
  { k = val($0, "source") "|" val($0, "source_id")
    if (k in have) next
    have[k] = 1; print }
' "$new" > "$keep"

kept=$(wc -l < "$keep" | tr -d ' ')
emit_call search-jobs "$src" true "$returned" "$kept"
[ "$kept" -gt 0 ] && cat "$keep" >> "$jobs"
printf 'record-api-response.sh: %s rows appended, %s rows in the response\n' "$kept" "$returned" >&2
exit 0
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k record_api -v`
Expected: all nine PASS.

- [ ] **Step 6: Verify it runs under `sh` and `dash`**

Run: `sh -n skills/job-search-run/scripts/record-api-response.sh && command -v dash >/dev/null && dash -n skills/job-search-run/scripts/record-api-response.sh; echo "syntax ok"`
Expected: `syntax ok`, no diagnostics.

- [ ] **Step 7: Commit**

```bash
git add skills/job-search-run/scripts/record-api-response.sh tests/test_mechanics_scripts.py tests/fixtures/api-responses/
git commit -m "feat(run): record every row a search returns, before anything judges it"
```

---

### Task 2: `record-api-response.sh` — posting responses

**Files:**
- Modify: `skills/job-search-run/scripts/record-api-response.sh`
- Test: `tests/test_mechanics_scripts.py`
- Create: `tests/fixtures/api-responses/detail.ashby.json`, `detail.linkedin.json`

**Interfaces:**
- Consumes: `record-api-response.sh` from Task 1.
- Produces: the same command applied to a `get-posting` response appends one `call` event and one `detail` event. A posting this run did not surface is refused. A posting already carrying a `detail` event for this run is reported and skipped, exit 0.

- [ ] **Step 1: Capture the detail fixtures**

```sh
L=f9a6ec16-0bfd-44d8-b3ee-073776745ee7
# Take an id + source_url PAIR from the same row of the search fixture — a mismatched pair is a 400.
python3 -c "
import json
for name,src in (('ashby','ashby'),('linkedin','linkedin')):
    rows=json.load(open('tests/fixtures/api-responses/search.%s.json'%name))['data']['results']
    print(src, rows[0]['id'], rows[0]['source_url'])
"
# then, for each printed line:
agent-data call $L get-posting --posting_id <id> --source_url "<source_url>" --source <src> \
  > tests/fixtures/api-responses/detail.<src>.json
```

- [ ] **Step 2: Write the failing tests**

```python
def surfaced_from(fixture_name):
    """The (source, source_id) a detail fixture belongs to."""
    d = json.loads((FIXTURES / fixture_name).read_text())["data"]
    return d["source"], d["source_id"]


def seeded_jobs(tmp_path, search_fixture):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, RID, jobs, FIXTURES / search_fixture, "--query-id", "q")
    return jobs


def test_detail_response_stores_the_description_byte_exact(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "detail.ashby.json")
    assert r.returncode == 0, r.stderr
    stored = [e for e in lines(jobs) if e["event"] == "detail"]
    assert len(stored) == 1
    original = json.loads((FIXTURES / "detail.ashby.json").read_text())["data"]
    assert stored[0]["description_markdown"] == original["description_markdown"]
    assert stored[0]["apply_url"] == original.get("apply_url")


def test_linkedin_detail_stores_byte_exact_too(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    run_script(RECORD_API, RID, jobs, FIXTURES / "detail.linkedin.json")
    stored = [e for e in lines(jobs) if e["event"] == "detail"][0]
    original = json.loads((FIXTURES / "detail.linkedin.json").read_text())["data"]
    assert stored["description_markdown"] == original["description_markdown"]


def test_detail_for_a_posting_this_run_never_surfaced_is_refused(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "detail.ashby.json")
    assert r.returncode == 1
    assert "no surfaced posting" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "detail"] == []


def test_storing_the_same_detail_twice_is_reported_and_skipped(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    run_script(RECORD_API, RID, jobs, FIXTURES / "detail.ashby.json")
    before = len(lines(jobs))
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "detail.ashby.json")
    assert r.returncode == 0
    assert "already stored" in r.stderr
    assert len(lines(jobs)) == before


def test_a_detail_read_records_its_call(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    run_script(RECORD_API, RID, jobs, FIXTURES / "detail.ashby.json")
    calls = [e for e in lines(jobs) if e["event"] == "call" and e["route"] == "get-posting"]
    assert len(calls) == 1 and calls[0]["ok"] is True
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k detail -v`
Expected: FAIL — the script only handles search responses.

- [ ] **Step 4: Add the posting branch**

In `record-api-response.sh`, replace the `grep -q '^[ \t]*"results"' … || exit 2` guard with a shape dispatch. Insert immediately after the error-response block:

```sh
# A posting response carries the posting's own fields under data, with no results array.
if ! grep -q '^[ \t]*"results"[ \t]*:' "$resp"; then
  grep -q '"description_markdown"\|"description_plain"' "$resp" || {
    printf 'record-api-response.sh: %s is neither a search nor a posting response\n' "$resp" >&2
    exit 2
  }

  det=$(mktemp) || exit 2
  trap 'rm -f "$det"' EXIT INT HUP TERM

  awk -v run_id="$run_id" '
    function esc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return s }
    function fld(k) { return (k in v && v[k] != "") ? v[k] : "null" }
    {
      line = $0
      n = length(line)
      for (i = 1; i <= n; i++) {
        c = substr(line, i, 1)
        if (instr) { if (c == "\\") { i++; continue }; if (c == "\"") instr = 0; continue }
        if (c == "\"") { instr = 1; continue }
        if (c == "{" || c == "[") { depth++; continue }
        if (c == "}" || c == "]") { depth--; continue }
      }
      if (match(line, /^[ \t]*"[^"]+"[ \t]*:/)) {
        key = line; sub(/^[ \t]*"/, "", key); sub(/".*$/, "", key)
        val = line; sub(/^[ \t]*"[^"]+"[ \t]*:[ \t]*/, "", val); sub(/,[ \t]*$/, "", val)
        # Depth 2 is inside data{}; anything deeper belongs to a nested object.
        if (depth == 2 && val != "" && val != "{" && val != "[") v[key] = val
      }
    }
    END {
      if (!("source_id" in v) || v["source_id"] == "" || v["source_id"] == "null") exit 3
      if (!("source" in v) || v["source"] == "" || v["source"] == "null") exit 3
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
      out = out "}"
      print out
    }
  ' "$resp" > "$det" || {
    printf 'record-api-response.sh: %s carries no source and source_id\n' "$resp" >&2
    exit 1
  }

  dsrc=$(sed -n 's/.*"source":"\([^"]*\)".*/\1/p' "$det")
  dsid=$(sed -n 's/.*"source_id":"\([^"]*\)".*/\1/p' "$det")

  grep -F '"event":"surfaced"' "$jobs" \
    | grep -F "\"run_id\":\"$run_id\"" \
    | grep -F "\"source\":\"$dsrc\"" \
    | grep -qF "\"source_id\":\"$dsid\"" || {
      emit_call get-posting "$dsrc" true 0 0
      printf 'record-api-response.sh: no surfaced posting for %s:%s in run %s\n' \
        "$dsrc" "$dsid" "$run_id" >&2
      exit 1
    }

  if grep -F '"event":"detail"' "$jobs" \
       | grep -F "\"run_id\":\"$run_id\"" \
       | grep -F "\"source\":\"$dsrc\"" \
       | grep -qF "\"source_id\":\"$dsid\""; then
    printf 'record-api-response.sh: %s:%s already stored for this run — nothing written\n' \
      "$dsrc" "$dsid" >&2
    exit 0
  fi

  emit_call get-posting "$dsrc" true 1 1
  cat "$det" >> "$jobs"
  printf 'record-api-response.sh: stored %s:%s\n' "$dsrc" "$dsid" >&2
  exit 0
fi
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k "record_api or detail" -v`
Expected: all PASS, Task 1's tests included.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search-run/scripts/record-api-response.sh tests/test_mechanics_scripts.py tests/fixtures/api-responses/
git commit -m "feat(run): store a posting's full text on its own event"
```

---

### Task 3: `queue-detail-read.sh` and `list-detail-read-queue.sh`

**Files:**
- Create: `skills/job-search-run/scripts/queue-detail-read.sh`, `skills/job-search-run/scripts/list-detail-read-queue.sh`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `surfaced` events from Task 1.
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
    assert len(fields) == 6
    assert fields[0] == row["source"]
    assert fields[1] == row["source_id"]
    assert fields[2] == row["posting_id_at_seen"]
    assert fields[3] == row["source_url"]
    assert fields[4] == row["title"]
    assert fields[5] == row["company_name"]


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

- [ ] **Step 4: Write `list-detail-read-queue.sh`**

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
# This is what the run hands out. The event log itself grows past what a context window holds, so
# nothing reads it directly to work out what is left to do.
set -u

jobs=${1:?usage: list-detail-read-queue.sh <jobs.jsonl> <run_id>}
run_id=${2:?usage: list-detail-read-queue.sh <jobs.jsonl> <run_id>}

[ -f "$jobs" ] || { printf 'list-detail-read-queue: no such file: %s\n' "$jobs" >&2; exit 2; }

awk -v want="$run_id" '
  function val(line, key,   v) {
    v = line
    if (v !~ ("\"" key "\":")) return ""
    sub(".*\"" key "\":", "", v)
    if (substr(v, 1, 1) == "\"") { sub(/^"/, "", v); sub(/".*$/, "", v) }
    else sub(/[,}].*$/, "", v)
    return v
  }
  function unesc(s) {
    gsub(/\\"/, "\"", s); gsub(/\\t/, " ", s); gsub(/\\n/, " ", s); gsub(/\\\\/, "\\", s)
    return s
  }
  {
    ev = val($0, "event")
    k  = val($0, "source") "|" val($0, "source_id")
    if (ev == "surfaced" && val($0, "run_id") == want) {
      src[k] = val($0, "source"); sid[k] = val($0, "source_id")
      pid[k] = val($0, "posting_id_at_seen"); url[k] = val($0, "source_url")
      title[k] = val($0, "title"); company[k] = val($0, "company_name")
    }
    else if (ev == "queued" && val($0, "run_id") == want) {
      if (!(k in queued)) { queued[k] = 1; n++; order[n] = k }
    }
    else if (ev == "evaluated") judged[k] = 1
  }
  END {
    for (i = 1; i <= n; i++) {
      k = order[i]
      if (k in judged) continue
      printf "%s\t%s\t%s\t%s\t%s\t%s\n",
        src[k], sid[k], pid[k], url[k], unesc(title[k]), unesc(company[k])
    }
  }
' "$jobs"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k "queue" -v`
Expected: all six PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search-run/scripts/queue-detail-read.sh skills/job-search-run/scripts/list-detail-read-queue.sh tests/test_mechanics_scripts.py
git commit -m "feat(run): track which postings are still to be read, without pre-judging them"
```

---

### Task 4: `record-judgment.sh`

**Files:**
- Create: `skills/job-search-run/scripts/record-judgment.sh`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `surfaced` events from Task 1.
- Produces: `record-judgment.sh <jobs.jsonl> --run-id ID --source S --source-id ID --detail-read true|false --relevant true|false [--match strong|moderate|weak] [--needs-human-check true|false] [--dealbreakers 'a;b'] [--unknowns 'a;b'] [--reasoning TEXT] [--same-role-as SOURCE:ID] [--posted-at-extracted DATE] [--ts TS]`. Appends one `evaluated` event. The script writes the JSON, so nothing the judgment says is escaped by the caller.

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
    args = judge_args(jobs, row, detail_read="true", relevant="true", match="strong",
                      reasoning="Same.", ts="2026-08-05T00:00:00Z")
    run_script(JUDGE, *args)
    before = len(lines(jobs))
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                      match="strong", reasoning="Same.",
                                      ts="2026-08-05T09:99:99Z".replace("99", "30")))
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

- [ ] **Step 3: Write the script**

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
# A judgment can only be about a posting a search surfaced for this run.
#
# Exit 0: recorded, or this posting already carries exactly this judgment.
# Exit 1: nothing written; stderr names the problem.
set -u

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

grep -F '"event":"surfaced"' "$jobs" \
  | grep -F "\"run_id\":\"$run_id\"" \
  | grep -F "\"source\":\"$source\"" \
  | grep -qF "\"source_id\":\"$source_id\"" \
  || die "no surfaced posting for $source:$source_id in run $run_id"

[ -n "$ts" ] || ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# The three free-text values ride in the environment rather than through -v, which cannot carry a
# literal newline. `band` is not called `match`, which is an awk built-in.
RJ_REASONING=$reasoning RJ_DEALBREAKERS=$dealbreakers RJ_UNKNOWNS=$unknowns \
awk -v run_id="$run_id" -v source="$source" -v source_id="$source_id" \
    -v detail_read="$detail_read" -v relevant="$relevant" -v band="$band" \
    -v nhc="$nhc" -v same_role="$same_role" \
    -v posted_extracted="$posted_extracted" -v ts="$ts" '
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
  BEGIN {
    reasoning = ENVIRON["RJ_REASONING"]
    out = "{\"event\":\"evaluated\""
    out = out ",\"run_id\":" jstr(run_id)
    out = out ",\"source\":" jstr(source)
    out = out ",\"source_id\":" jstr(source_id)
    out = out ",\"detail_read\":" detail_read
    out = out ",\"relevant\":" relevant
    out = out ",\"match\":" (band == "" ? "null" : jstr(band))
    out = out ",\"reasoning\":" (reasoning == "" ? "null" : jstr(reasoning))
    out = out ",\"dealbreakers_hit\":" jlist(ENVIRON["RJ_DEALBREAKERS"])
    out = out ",\"unknowns\":" jlist(ENVIRON["RJ_UNKNOWNS"])
    out = out ",\"needs_human_check\":" nhc
    if (same_role != "")        out = out ",\"same_role_as\":" jstr(same_role)
    if (posted_extracted != "") out = out ",\"posted_at_extracted\":" jstr(posted_extracted)
    out = out ",\"status\":\"new\""
    out = out ",\"ts\":" jstr(ts)
    out = out "}"
    print out
  }' > "$line"

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

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k judgment -v`
Expected: all nine PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/job-search-run/scripts/record-judgment.sh tests/test_mechanics_scripts.py
git commit -m "feat(run): record a judgment without the caller writing any JSON"
```

---

### Task 5: `run-counts.sh`

**Files:**
- Create: `skills/job-search-run/scripts/run-counts.sh`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: every event type from Tasks 1–4.
- Produces: `run-counts.sh <jobs.jsonl> <run_id>` prints the key/value lines in the output contract at the top of this plan, one per line, and exits 0. A relevant row with no band prints `INVALID relevant-row-without-a-band=<n>` and exits 1.

- [ ] **Step 1: Write the failing tests**

```python
COUNTS = RUN_SCRIPTS / "run-counts.sh"


def counts(jobs, run_id=RID):
    r = run_script(COUNTS, jobs, run_id)
    return r, dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)


def test_a_run_killed_after_the_search_reports_everything_unreviewed(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    r, c = counts(jobs)
    assert r.returncode == 0, r.stderr
    assert c["postings_surfaced"] == "25"
    assert c["postings_reviewed"] == "0"
    assert c["postings_unreviewed"] == "25"


def test_the_bands_and_filtered_out_sum_to_reviewed(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    for row in rows[:2]:
        run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                      match="strong", reasoning="Fits."))
    for row in rows[2:7]:
        run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                      match="moderate", reasoning="Partly fits."))
    for row in rows[7:20]:
        run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="false",
                                      reasoning="Outside the brief."))
    _, c = counts(jobs)
    reviewed = int(c["postings_reviewed"])
    assert (int(c["match_strong"]) + int(c["match_moderate"]) + int(c["match_weak"])
            + int(c["filtered_out"])) == reviewed
    assert reviewed + int(c["postings_unreviewed"]) == int(c["postings_surfaced"])
    assert c["match_strong"] == "2" and c["match_moderate"] == "5" and c["match_weak"] == "0"
    assert c["filtered_out"] == "13"
    assert c["postings_detail_read"] == "0"   # no detail events recorded


def test_by_source_sums_to_surfaced(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    for name in ("search.linkedin.json", "search.ashby.json"):
        run_script(RECORD_API, RID, jobs, FIXTURES / name, "--query-id", "q")
    _, c = counts(jobs)
    per = {k: int(v) for k, v in c.items() if k.startswith("by_source_")}
    assert sum(per.values()) == int(c["postings_surfaced"])
    assert per == {"by_source_linkedin": 25, "by_source_ashby": 25}


def test_rows_new_total_equals_surfaced(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    for qid in ("a", "b"):
        run_script(RECORD_API, RID, jobs, FIXTURES / "search.linkedin.json", "--query-id", qid)
    _, c = counts(jobs)
    assert c["rows_new_total"] == c["postings_surfaced"] == "25"


def test_metered_calls_are_counted_including_a_failed_one(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    run_script(RECORD_API, RID, jobs, FIXTURES / "search.error.json", "--query-id", "q")
    _, c = counts(jobs)
    assert c["calls_searches"] == "2"
    assert c["calls_failed"] == "1"
    assert int(c["calls_total_metered"]) == (int(c["calls_searches"])
                                             + int(c["calls_detail_reads"])
                                             + int(c["calls_other"]))


def test_postings_detail_read_counts_postings_not_calls(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    run_script(RECORD_API, RID, jobs, FIXTURES / "detail.ashby.json")
    _, c = counts(jobs)
    assert c["postings_detail_read"] == "1"
    assert c["calls_detail_reads"] == "1"


def test_a_relevant_row_with_no_band_is_reported_as_invalid(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    jobs.write_text(jobs.read_text() +
        '{"event":"evaluated","run_id":"%s","source":"%s","source_id":"%s",'
        '"detail_read":true,"relevant":true,"match":null}\n'
        % (RID, row["source"], row["source_id"]))
    r, c = counts(jobs)
    assert r.returncode == 1
    assert "relevant-row-without-a-band=1" in r.stdout


def test_another_runs_events_do_not_enter_these_counts(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    other = jobs.read_text().replace(RID, "2026-01-01T00-00-00Z")
    jobs.write_text(jobs.read_text() + other)
    _, c = counts(jobs)
    assert c["postings_surfaced"] == "25"
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k counts -v`
Expected: FAIL — `run-counts.sh` does not exist.

- [ ] **Step 3: Write the script**

```sh
#!/bin/sh
# run-counts.sh — work out one run's numbers from jobs.jsonl and print them, one key=value per line.
#
# Usage: run-counts.sh <jobs.jsonl> <run_id>
#
# This is the only place a run's numbers are worked out. The run record copies these values and the
# digest's counts line reads the same ones, so the two cannot disagree.
#
# A posting belongs to this run when a `surfaced` event carries this run_id. Its judgment is the
# last `evaluated` event recorded for it; a posting with none was surfaced and never judged, which
# is what postings_unreviewed counts. agent_data_usage is a count of `call` events, so retries and
# failures are in it without anyone reporting them.
#
# This is the scripted form of the model-run prose contract; that prose remains the no-runtime
# fallback, and counts worked out by hand are not gated by anything, so a run that works them out
# that way says so rather than presenting them as checked.
#
# Exit 0: the counts printed. Exit 1: a relevant row carries no band, named on the last line.
set -u

jobs=${1:?usage: run-counts.sh <jobs.jsonl> <run_id>}
run_id=${2:?usage: run-counts.sh <jobs.jsonl> <run_id>}

[ -f "$jobs" ] || { printf 'run-counts.sh: no such file: %s\n' "$jobs" >&2; exit 2; }

awk -v want="$run_id" '
  function val(line, key,   v) {
    v = line
    if (v !~ ("\"" key "\":")) return ""
    sub(".*\"" key "\":", "", v)
    if (substr(v, 1, 1) == "\"") { sub(/^"/, "", v); sub(/".*$/, "", v) }
    else sub(/[,}].*$/, "", v)
    return v
  }
  {
    ev  = val($0, "event")
    rid = val($0, "run_id")
    k   = val($0, "source") "|" val($0, "source_id")

    if (ev == "call" && rid == want) {
      route = val($0, "route")
      if (val($0, "ok") != "true") failed++
      if (route == "search-jobs")      searches++
      else if (route == "get-posting") detailcalls++
      else                             other++
      n = val($0, "rows_new"); if (n != "") rowsnew += n
      next
    }
    if (ev == "surfaced" && rid == want) {
      if (!(k in mine)) {
        mine[k] = 1; count++; keys[count] = k
        src = val($0, "source")
        if (!(src in bysrc)) { nsrc++; srcorder[nsrc] = src }
        bysrc[src]++
      }
      next
    }
    if (ev == "detail" && rid == want) { hasdetail[k] = 1; next }
    if (ev == "evaluated") {
      # The last evaluated event for a posting wins.
      rel[k] = val($0, "relevant"); band[k] = val($0, "match"); judged[k] = 1
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
    printf "rows_new_total=%d\n",       rowsnew+0
    if (unbanded > 0) {
      printf "INVALID relevant-row-without-a-band=%d\n", unbanded
      exit 1
    }
  }
' "$jobs"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k counts -v`
Expected: all eight PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/job-search-run/scripts/run-counts.sh tests/test_mechanics_scripts.py
git commit -m "feat(run): work out a run's numbers from its own event log"
```

---

### Task 6: Fix the two shipped scripts this change breaks

**Files:**
- Modify: `skills/job-search-run/scripts/event-log-append.sh:53-58`
- Modify: `skills/job-search-run/scripts/dedup.sh:58-62`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `event-log-append.sh`'s idempotency check keys on `evaluated` lines only. `dedup.sh`'s known set is source_ids carrying an `evaluated` event, not any event.

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

- [ ] **Step 4: Fix `dedup.sh`**

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

Update the header comment's description of the known set to match.

- [ ] **Step 5: Run the whole mechanics suite**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -v`
Expected: all PASS, including the pre-existing dedup and append tests.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search-run/scripts/event-log-append.sh skills/job-search-run/scripts/dedup.sh tests/test_mechanics_scripts.py
git commit -m "fix(run): key the append and dedup checks on judged postings, not seen ones"
```

---

### Task 7: `open-run.sh`

**Files:**
- Create: `skills/job-search-runbook/scripts/open-run.sh`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `validate-workspace.sh` (existing).
- Produces: `open-run.sh <workspace>` prints three lines — `run_id=…`, `started_at=…`, `brief_revision=…` — creates `runs/.started-<run_id>`, and runs the workspace checks. Exit 0 clean; exit 1 when the run opened but the workspace has findings, which print on stdout after the three lines; exit 2 when there is no `config.yaml` to write into, with no marker and no run.

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
    out = parsed_output(run_script(OPEN_RUN, tmp_workspace))
    import hashlib
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
```

`tmp_workspace` is the fixture already defined in `tests/test_validate_workspace.py`. Import it by adding a `conftest.py` fixture, or copy the three-line construction into `tests/test_mechanics_scripts.py` — the workspace is a valid `config.yaml`, a valid `preferences.md`, and a `runs/` directory.

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

if command -v shasum >/dev/null 2>&1; then
  rev=$(shasum -a 256 "$ws/preferences.md" 2>/dev/null | cut -c1-12)
else
  rev=$(sha256sum "$ws/preferences.md" 2>/dev/null | cut -c1-12)
fi

printf 'run_id=%s\n' "$run_id"
printf 'started_at=%s\n' "$now"
printf 'brief_revision=%s\n' "$rev"

sh "$here/validate-workspace.sh" "$ws" || exit 1
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k open_run -v`
Expected: all five PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/job-search-runbook/scripts/open-run.sh tests/test_mechanics_scripts.py
git commit -m "feat(runbook): open a run from one clock read, and check the workspace while doing it"
```

---

### Task 8: `close-run.sh` and the run-record template

**Files:**
- Create: `skills/job-search-runbook/scripts/close-run.sh`
- Modify: `skills/job-search-run/templates/run-record.example.json`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `run-counts.sh` (Task 5) and its output contract.
- Produces: `close-run.sh <workspace> <run_id> --trigger manual|scheduled [--scheduler-id ID] --close-state complete|blocked|interrupted [--brief-revision REV] [--sources 'a,b'] [--queries 'a,b']` writes `runs/<run_id>.json`, deletes `runs/.started-<run_id>` and `runs/.scratch/<run_id>/`. Derives `run_health` and `completed_at`. Exit 1, writing nothing, when `--close-state complete` contradicts the log.

- [ ] **Step 1: Write the failing tests**

```python
CLOSE_RUN = RUNBOOK_SCRIPTS / "close-run.sh"


def opened(ws):
    return parsed_output(run_script(OPEN_RUN, ws))


def test_the_record_carries_the_counts_from_the_log(tmp_workspace):
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.linkedin.json", "--query-id", "q")
    for row in [e for e in lines(jobs) if e["event"] == "surfaced"]:
        run_script(JUDGE, jobs, "--run-id", o["run_id"], "--source", row["source"],
                   "--source-id", row["source_id"], "--detail-read", "false",
                   "--relevant", "false", "--reasoning", "Outside the brief.")
    r = run_script(CLOSE_RUN, tmp_workspace, o["run_id"], "--trigger", "manual",
                   "--close-state", "complete")
    assert r.returncode == 0, r.stderr
    rec = json.loads((tmp_workspace / "runs" / (o["run_id"] + ".json")).read_text())
    assert rec["postings_surfaced"] == 25
    assert rec["postings_reviewed"] == 25
    assert rec["postings_unreviewed"] == 0
    assert rec["filtered_out"] == 25
    assert rec["matches"] == {"strong": 0, "moderate": 0, "weak": 0}
    assert rec["by_source"] == {"linkedin": 25}
    assert rec["agent_data_usage"]["total_metered"] == 1


def test_completed_at_is_later_than_started_at_and_not_later_than_the_file(tmp_workspace):
    import datetime
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    run_script(CLOSE_RUN, tmp_workspace, o["run_id"], "--trigger", "manual",
               "--close-state", "complete")
    path = tmp_workspace / "runs" / (o["run_id"] + ".json")
    rec = json.loads(path.read_text())
    assert UTC_TS_RE.match(rec["completed_at"])
    assert rec["completed_at"] >= rec["started_at"]
    stated = datetime.datetime.strptime(rec["completed_at"], "%Y-%m-%dT%H:%M:%SZ")
    written = datetime.datetime.utcfromtimestamp(path.stat().st_mtime)
    assert stated <= written + datetime.timedelta(seconds=2)


def test_a_complete_close_over_unreviewed_postings_is_refused(tmp_workspace):
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.linkedin.json", "--query-id", "q")
    r = run_script(CLOSE_RUN, tmp_workspace, o["run_id"], "--trigger", "manual",
                   "--close-state", "complete")
    assert r.returncode == 1
    assert "unreviewed" in r.stderr
    assert not (tmp_workspace / "runs" / (o["run_id"] + ".json")).exists()
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()


def test_the_same_run_closes_interrupted_and_records_run_health_degraded(tmp_workspace):
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.linkedin.json", "--query-id", "q")
    r = run_script(CLOSE_RUN, tmp_workspace, o["run_id"], "--trigger", "manual",
                   "--close-state", "interrupted")
    assert r.returncode == 0, r.stderr
    rec = json.loads((tmp_workspace / "runs" / (o["run_id"] + ".json")).read_text())
    assert rec["run_health"] == "degraded"
    assert rec["postings_unreviewed"] == 25


def test_a_failed_search_call_makes_the_run_degraded(tmp_workspace):
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.error.json", "--query-id", "q")
    r = run_script(CLOSE_RUN, tmp_workspace, o["run_id"], "--trigger", "manual",
                   "--close-state", "blocked")
    assert r.returncode == 0, r.stderr
    rec = json.loads((tmp_workspace / "runs" / (o["run_id"] + ".json")).read_text())
    assert rec["run_health"] == "degraded"


def test_closing_clears_the_marker_and_the_scratch_directory(tmp_workspace):
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    scratch = tmp_workspace / "runs" / ".scratch" / o["run_id"]
    scratch.mkdir(parents=True)
    (scratch / "search.json").write_text("{}")
    run_script(CLOSE_RUN, tmp_workspace, o["run_id"], "--trigger", "manual",
               "--close-state", "complete")
    assert not (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()
    assert not scratch.exists()


def test_the_record_matches_the_template_field_set(tmp_workspace):
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    run_script(CLOSE_RUN, tmp_workspace, o["run_id"], "--trigger", "manual",
               "--close-state", "complete")
    rec = json.loads((tmp_workspace / "runs" / (o["run_id"] + ".json")).read_text())
    template = json.loads((RUN_SCRIPTS.parent / "templates" / "run-record.example.json").read_text())
    assert set(rec) == set(template)
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k close_run -v`
Expected: FAIL — the script does not exist.

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

Check the arithmetic: `3 + 6 + 2 + 39 = 50` reviewed; `50 + 0 = 50` surfaced; `25 + 25 = 50`; `4 + 13 + 0 = 17`. `detail_reads: 13` against `postings_detail_read: 12` is one posting that needed a retry — the two fields answer different questions and are meant to differ.

- [ ] **Step 4: Write the script**

```sh
#!/bin/sh
# close-run.sh — close one run: write its record, then clear what the run was using.
#
# Usage: close-run.sh <workspace> <run_id> --trigger manual|scheduled \
#          [--scheduler-id ID] --close-state complete|blocked|interrupted \
#          [--brief-revision REV] [--sources 'a,b'] [--queries 'a,b']
#
# Every count comes from run-counts.sh, and completed_at from a clock read here, so no number in
# the record is anyone's account of the run. run_health is worked out the same way: healthy means
# every search call answered and no posting was left unjudged.
#
# A close_state of complete over unjudged postings, or over a search call that failed, is refused
# and nothing is written — a run that did not finish must not read as one that did.
#
# Exit 0: the record is written and the marker and scratch are gone.
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

here=$(dirname "$0")
runscripts=$here/../../job-search-run/scripts
jobs=$ws/jobs.jsonl
[ -f "$jobs" ] || : > "$jobs"

counts=$(sh "$runscripts/run-counts.sh" "$jobs" "$run_id") || die "run-counts.sh reported: $counts"

get() { printf '%s\n' "$counts" | grep "^$1=" | cut -d= -f2; }
unreviewed=$(get postings_unreviewed)
failed=$(get calls_failed)

# A close that contradicts the log is refused rather than recorded.
if [ "$close_state" = complete ]; then
  [ "${unreviewed:-0}" -eq 0 ] || \
    die "close_state complete, but $unreviewed postings were never judged — close interrupted, or judge them"
  [ "${failed:-0}" -eq 0 ] || \
    die "close_state complete, but $failed agent-data call(s) failed — close blocked"
fi

run_health=healthy
[ "${unreviewed:-0}" -eq 0 ] || run_health=degraded
[ "${failed:-0}" -eq 0 ] || run_health=degraded
[ "$close_state" = complete ] || run_health=degraded

completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
started_at=$(printf '%s\n' "$run_id" | sed 's/T\(..\)-\(..\)-\(..\)Z$/T\1:\2:\3Z/')

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
      split(rows[i], kv, "=")
      c[kv[1]] = kv[2]
      if (kv[1] ~ /^by_source_/) {
        s = kv[1]; sub(/^by_source_/, "", s)
        nsrc++; srck[nsrc] = s; srcv[nsrc] = kv[2]
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
  }' > "$ws/runs/$run_id.json"

rm -f "$ws/runs/.started-$run_id"
rm -rf "$ws/runs/.scratch/$run_id"
printf 'close-run: wrote runs/%s.json (%s, %s)\n' "$run_id" "$close_state" "$run_health" >&2
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k close_run -v`
Expected: all seven PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search-runbook/scripts/close-run.sh skills/job-search-run/templates/run-record.example.json tests/test_mechanics_scripts.py
git commit -m "feat(runbook): write the run record from the log, and refuse a close that contradicts it"
```

---

### Task 9: `validate-workspace.sh` — the invariants and the timestamp gates

**Files:**
- Modify: `skills/job-search-runbook/scripts/validate-workspace.sh`
- Test: `tests/test_validate_workspace.py`

**Interfaces:**
- Consumes: `run-counts.sh` (Task 5).
- Produces: `validate-workspace.sh <workspace> --post-close <run_id>` additionally reports `missing-key <field>` for each absent count field, `counts-disagree-with-log <field> <record> vs <log>`, `bands-do-not-sum-to-reviewed`, `surfaced-does-not-match-rows-new`, `completed-at-before-started-at`, and `completed-at-after-the-file-that-states-it`.

- [ ] **Step 1: Write the failing tests**

Update `run_record()` in `tests/test_validate_workspace.py` to carry the new fields, then add:

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
        '{"event":"call","run_id":"%s","route":"search-jobs","source":"linkedin","ok":true,'
        '"rows_returned":2,"rows_new":2}' % run_id,
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
    future = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_validate_workspace.py -v`
Expected: the eight new tests FAIL; the existing ones still pass.

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

Expected: a non-zero exit reporting `missing-key postings_surfaced` and `completed-at-after-the-file-that-states-it 2026-08-05T03:15:00Z`. If the workspace has moved on since, skip this step and say so rather than reporting a check you did not run.

- [ ] **Step 6: Verify `test -nt` works on the CI runner**

Run: `python3 -m pytest tests/test_validate_workspace.py -k completed_at_later -v` under Linux — either in CI or a container. The spec records this as unverified because `-nt` is not in POSIX `test`.

If it fails on Linux, replace the `touch -t` reference-file comparison with `find "$record" -newermt "$ca"` guarded by a capability probe, and keep the `touch`/`-nt` path as the fallback. Do not remove the gate.

- [ ] **Step 7: Commit**

```bash
git add skills/job-search-runbook/scripts/validate-workspace.sh tests/test_validate_workspace.py
git commit -m "feat(runbook): fail a run record whose counts or timestamps contradict its log"
```

---

### Task 10: `pipeline-counts.sh`

**Files:**
- Create: `skills/job-search/scripts/pipeline-counts.sh`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Consumes: `jobs.jsonl` across all runs.
- Produces: `pipeline-counts.sh <jobs.jsonl>` prints `new=`, `interested=`, `applied=`, `rejected=`, `archived=`, `to_confirm=`, one per line. A posting's state is the last line sharing its `source` and `source_id`; a posting naming another in `same_role_as` counts as that one role.

The home view currently reads `jobs.jsonl` to work this out. At roughly 10 MB a month that read stops being possible, so it becomes a script.

- [ ] **Step 1: Write the failing tests**

```python
PIPELINE = SEARCH_SCRIPTS / "pipeline-counts.sh"


def pipeline(jobs):
    r = run_script(PIPELINE, jobs)
    return r, dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)


def test_the_last_line_for_a_posting_wins(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"evaluated","source":"linkedin","source_id":"a","relevant":true,'
        '"match":"strong","status":"new","needs_human_check":false}\n'
        '{"event":"status_changed","source":"linkedin","source_id":"a","status":"applied"}\n')
    r, p = pipeline(jobs)
    assert r.returncode == 0, r.stderr
    assert p["applied"] == "1" and p["new"] == "0"


def test_surfaced_rows_without_a_judgment_are_not_in_the_pipeline(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"surfaced","source":"linkedin","source_id":"a"}\n'
        '{"event":"call","route":"search-jobs","ok":true}\n'
        '{"event":"queued","source":"linkedin","source_id":"a"}\n')
    _, p = pipeline(jobs)
    assert p["new"] == "0" and p["applied"] == "0"


def test_to_confirm_counts_judgments_needing_a_human(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"evaluated","source":"linkedin","source_id":"a","relevant":true,'
        '"match":"strong","status":"new","needs_human_check":true}\n'
        '{"event":"evaluated","source":"linkedin","source_id":"b","relevant":true,'
        '"match":"weak","status":"new","needs_human_check":false}\n')
    _, p = pipeline(jobs)
    assert p["to_confirm"] == "1" and p["new"] == "2"


def test_a_row_folded_into_another_role_is_counted_once(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"evaluated","source":"ashby","source_id":"a","relevant":true,'
        '"match":"strong","status":"new","needs_human_check":false}\n'
        '{"event":"evaluated","source":"ashby","source_id":"b","relevant":true,'
        '"match":"strong","status":"new","needs_human_check":false,"same_role_as":"ashby:a"}\n')
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

- [ ] **Step 3: Write the script**

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
# The event log grows past what a context window holds, so nothing reads it directly to work this
# out.
set -u

jobs=${1:?usage: pipeline-counts.sh <jobs.jsonl>}
[ -f "$jobs" ] || { printf 'pipeline-counts.sh: no such file: %s\n' "$jobs" >&2; exit 2; }

awk '
  function val(line, key,   v) {
    v = line
    if (v !~ ("\"" key "\":")) return ""
    sub(".*\"" key "\":", "", v)
    if (substr(v, 1, 1) == "\"") { sub(/^"/, "", v); sub(/".*$/, "", v) }
    else sub(/[,}].*$/, "", v)
    return v
  }
  {
    ev = val($0, "event")
    if (ev != "evaluated" && ev != "status_changed") next
    k = val($0, "source") "|" val($0, "source_id")
    if (!(k in seen)) { seen[k] = 1; n++; order[n] = k }
    s = val($0, "status");           if (s != "") status[k] = s
    h = val($0, "needs_human_check"); if (h != "") human[k] = h
    r = val($0, "same_role_as");      if (r != "") { split(r, p, ":"); alias[k] = p[1] "|" p[2] }
  }
  END {
    for (i = 1; i <= n; i++) {
      k = order[i]
      if (k in alias) continue          # the same opening, already counted under the row that was read
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
' "$jobs"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k pipeline -v`
Expected: all five PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/job-search/scripts/pipeline-counts.sh tests/test_mechanics_scripts.py
git commit -m "feat(job-search): count the pipeline with a script instead of reading the whole log"
```

---

### Task 11: `job-search-runbook/SKILL.md`

**Files:**
- Modify: `skills/job-search-runbook/SKILL.md:48-59` (the file table), `:61-84` ("One run, start to close"), `:96-98` (Scratch), `:100-103` (What stays off disk)

**Interfaces:**
- Consumes: `open-run.sh`, `close-run.sh` (Tasks 7, 8).
- Produces: prose the run skill reads. No script or test consumes this file.

**This task's result is graded by the live behavior evals in Task 15, never by a string match.** Do not add a test that greps this file for a phrase.

- [ ] **Step 1: Rewrite "One run, start to close"**

The five numbered steps become three. Keep the numbered-prose shape; do not turn it into a checklist.

1. **Open the run** — run `skills/job-search-runbook/scripts/open-run.sh <workspace>`. It prints `run_id`, `started_at` and `brief_revision`; carry those three values through the run. A leftover marker from a previous run means that run stopped before it could close — say so and delete it before opening. Exit 1 means the run is open and the workspace findings printed after those three lines: report them in plain language and close `blocked`. Exit 2 means there is no `config.yaml`, so setup has not run and there is nothing to write into.
2. **Do the run's work**, recording events as you go.
3. **Close** — run `skills/job-search-runbook/scripts/close-run.sh <workspace> <run_id> --trigger … --close-state …`, passing `--brief-revision`, `--sources` and `--queries` from step 1 and the run. It writes the record, works out `run_health`, and deletes the marker and the scratch directory. It refuses a `complete` close over unjudged postings or a failed search call, and names which — fix that rather than restating the close.

Then state what the model still supplies: `trigger`, `scheduler_id`, `close_state`. Every count and both timestamps come from the log and the clock.

- [ ] **Step 2: Rewrite the file table's `jobs.jsonl` row**

Replace "a posting's current state is the fold of its events by `source` + `source_id`" with a plain statement. The rule: a posting can have several lines, and its current state is the last line sharing its `source` and `source_id`. Name the five event types a run writes.

- [ ] **Step 3: Remove full job descriptions from the off-disk list**

`:103` currently lists "API keys and auth headers, pagination cursors, full job descriptions, preference text anywhere but `preferences.md`". Drop "full job descriptions" and keep the rest. Add one sentence saying a posting's text is stored on its `detail` event so a changed brief can be re-applied without paying to read the posting again.

- [ ] **Step 4: Check the word count**

Run: `wc -w skills/job-search-runbook/SKILL.md skills/*/SKILL.md`
The runbook was 986 words and the corpus 9,092. Record both numbers in the commit message.

- [ ] **Step 5: Run the doc gates**

Run: `python3 scripts/doc_lint.py --root . && python3 scripts/philosophy_guard.py --root . && python3 -m pytest tests/test_skill_frontmatter.py tests/test_reference_resolution.py -q`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search-runbook/SKILL.md
git commit -m "docs(runbook): open and close a run with the scripts that read the clock and the log"
```

---

### Task 12: `job-search-run/SKILL.md` and the event templates

**Files:**
- Modify: `skills/job-search-run/SKILL.md:32-44` (Search), `:46-55` (Reconcile), `:56-65` (Scan), `:66-95` (Read and judge), `:98-129` (Digest), `:131-145` (Close)
- Modify: `skills/job-search-run/templates/jobs-event.example.json`

**Interfaces:**
- Consumes: every script from Tasks 1–8.
- Produces: prose. Graded by the evals in Task 15, never by a string match.

- [ ] **Step 1: Replace the template with one example per event type**

`templates/jobs-event.example.json` currently holds one `evaluated` line. Make it hold one line per event type a run writes — `call`, `surfaced`, `queued`, `detail`, `evaluated` — using the shapes at the top of this plan, each with every field filled with a realistic value. Truncate the `detail` line's `description_markdown` to a sentence with a trailing note that the real one is the posting's full text; a multi-kilobyte template is not readable.

- [ ] **Step 2: Rewrite Search**

After each `search-jobs` call, the response goes to `runs/.scratch/<run_id>/` and then through `skills/job-search-run/scripts/record-api-response.sh <run_id> <workspace>/jobs.jsonl <response> --query-id <id>`. That records the call and every row it returned. A non-zero exit means the call failed or a row was unusable, and it says which — nothing was recorded but the call.

The source-echo check stays: compare `data.query.source` against the source asked for.

- [ ] **Step 3: Delete Reconcile's known-ids step**

`record-api-response.sh` skips a posting already carrying a judgment from any run and one this run already surfaced, so the by-hand known-ids step and the `dedup.sh <jobs> <source>` call go. Keep `dedup.sh --near` for one opening posted in several cities, which is still the model's call.

- [ ] **Step 4: Rewrite Scan**

Judge every surfaced row from what the row carries. A row that plainly breaks a must-have is settled right there with `record-judgment.sh … --detail-read false --relevant false`, with no detail read. Everything else goes through `queue-detail-read.sh <jobs> --run-id … --source … --source-id …`.

Delete the steer — the provisional read and the question the read has to answer, at `:57-65` and `:73`. Nothing about the expected judgment is passed to the reader.

- [ ] **Step 5: Rewrite Read and judge**

The read list is `skills/job-search-run/scripts/list-detail-read-queue.sh <jobs> <run_id>`, which prints one tab-separated line per posting still to read: `source`, `source_id`, `posting_id_at_seen`, `source_url`, `title`, `company_name`. Brief each reader with its line, the path to `preferences.md`, and the `evaluate-job-fit` skill — the reader has none of this session's context, so the line is the whole brief.

Each detail response goes through `record-api-response.sh`, which stores the posting's text. Each judgment goes through `record-judgment.sh` with the fields `evaluate-job-fit` returned. Delete the 20-field event list at `:76-95` — nothing hand-writes a `jobs.jsonl` line any more.

- [ ] **Step 6: Rewrite the Digest's counts line**

The counts line is built from `skills/job-search-run/scripts/run-counts.sh <jobs> <run_id>`: `postings_surfaced` opens it, then `match_strong`, `match_moderate`, `match_weak`, `filtered_out`, the `by_source_*` values, and `calls_total_metered` on the usage line. When `postings_unreviewed` is not zero, the digest says how many postings the run never judged.

Keep the fenced digest shape. Update the example's numbers so the bands and filtered-out sum to the opening number.

- [ ] **Step 7: Rewrite Close**

Close is `close-run.sh`, then the digest, then `validate-workspace.sh <workspace> --post-close <run_id>`. Delete the record-field prose at `:136-145` — the script writes those fields. Keep the sentence defining `trigger`, and the closing sentence about telling the user what the run found.

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

### Task 13: `job-search/SKILL.md` and `job-search-agent/SKILL.md`

**Files:**
- Modify: `skills/job-search/SKILL.md:122-129` (Home)
- Modify: `skills/job-search-agent/SKILL.md:40-47` ("Explaining what a run spent"), `:50-58` (Symptom → fix)

**Interfaces:**
- Consumes: `pipeline-counts.sh` (Task 10), the record's new fields (Task 8).
- Produces: prose. Graded by the evals in Task 15.

- [ ] **Step 1: Rewrite the home view's read**

`:127` currently says to read "`jobs.jsonl` folded to one entry per `source` + `source_id` with the last line winning, counting a line that names another posting in `same_role_as` as that one role". Replace with a call to `skills/job-search/scripts/pipeline-counts.sh <workspace>/jobs.jsonl`, which prints `new`, `interested`, `applied`, `rejected`, `archived` and `to_confirm`. The rule about the last line winning stays in the runbook's file table, where it has its one home.

- [ ] **Step 2: Add the unreviewed line to the home card**

A newest record whose `postings_unreviewed` is not zero earns a line under the card saying how many postings that run never judged and offering to run again — the same shape as the existing `blocked`/`interrupted` line at `:150-152`.

- [ ] **Step 3: Rewrite "Explaining what a run spent"**

`agent_data_usage` is now counted from the run's `call` events rather than reported, so the numbers in the record are what the run actually spent, retries and failed attempts included. Say that. The billing pointer and the rate table pointer stay as they are.

- [ ] **Step 4: Add a symptom row**

| The digest says the run left postings unjudged | the run stopped before it finished, or a source failed partway | Its record's `postings_unreviewed` is how many; run the search again, which offers them once more because a posting with no judgment is not treated as already seen |

- [ ] **Step 5: Run the gates**

Run: `python3 scripts/doc_lint.py --root . && python3 scripts/philosophy_guard.py --root . && python3 -m pytest -q && wc -w skills/*/SKILL.md`

- [ ] **Step 6: Commit**

```bash
git add skills/job-search/SKILL.md skills/job-search-agent/SKILL.md
git commit -m "docs(job-search,agent): count the pipeline with a script and report what a run spent from its calls"
```

---

### Task 14: The language sweep

**Files:**
- Modify: `skills/job-search/evals/evals.json:65`, `docs/RELIABILITY.md:41,44,53`, `ARCHITECTURE.md:96`, `TESTING.md:302`, `INSTALL_FOR_HERMES.md:264`, `docs/superpowers/plans/2026-07-23-hermes-plugin-install.md:720`, `docs/design-docs/multi-harness-portability.md:588`, `skills/job-search-run/evals/evals.json:174,193,194`, `scripts/doc_lint.py`

Live files only. Dated design docs and completed exec-plans keep their wording as written records. `evals/baseline/2026-07-30-red-baseline.md:178` ("the close state's presence and spelling") is literal and stays.

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
| `docs/superpowers/plans/2026-07-23-hermes-plugin-install.md` | 720 | the same sentence | the same replacement |
| `docs/design-docs/multi-harness-portability.md` | 588 | "headless/print-mode command spelling" | "the exact headless/print-mode command" |

- [ ] **Step 3: Remove the steer from the run skill's evals**

`skills/job-search-run/evals/evals.json`:
- `:194` grades the steer alone. Delete the assertion.
- `:193` lists everything a reader is briefed with. Remove only its steer clause; the rest still describes what `list-detail-read-queue.sh` emits, so rewrite it to name those six fields.
- `:174` is a strip-the-guidance control naming "the read-list steer in the scan section". Rewrite it to strip the scan's settle-or-queue instruction instead, which is what now decides whether a posting is read.

- [ ] **Step 4: Give the digest-counts-line signature an owner**

In `scripts/doc_lint.py`, `DUP_SIGNATURES` line 284 carries `(re.compile(r"strong\s*·\s*\d+\s*moderate"), "digest counts line", None)`. The rule now lives in `run-counts.sh` and the prose that reads it. Set the owner to `skills/job-search-run/SKILL.md` and extend `DUP_ALLOW` to accept `job-search-run` as a pointer, so a doc that points at the owner passes.

- [ ] **Step 5: Verify no live file still carries either term**

```bash
grep -rniE "\bfold(s|ed|ing)?\b" skills/ ARCHITECTURE.md TESTING.md docs/RELIABILITY.md AGENTS.md
grep -rniE "\bspelling" skills/ INSTALL_FOR_HERMES.md docs/design-docs/multi-harness-portability.md docs/superpowers/plans/
grep -rn "steer" skills/job-search-run/
```

Expected: the first two print nothing. The third prints nothing — the verb "steering the search" in `skills/job-search/SKILL.md` and `skills/job-search-agent/SKILL.md` is ordinary English and stays, so do not grep those two files for it.

- [ ] **Step 6: Run the gates**

Run: `python3 scripts/doc_lint.py --root . && python3 scripts/philosophy_guard.py --root . && python3 -m pytest -q`

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "docs: say what the code does instead of naming it by metaphor"
```

---

### Task 15: The behavior evals

**Files:**
- Modify: `evals/behaviors.md`, `evals/cases/headless-run.yaml`, `evals/cases/kill-midrun.yaml`
- Modify: `skills/job-search-run/evals/evals.json`, `skills/job-search/evals/evals.json`, `skills/job-search-agent/evals/evals.json`

**Everything a skill's prose governs is graded here, by reading the artifacts a run leaves behind.** No assertion may match a substring of a documentation file. This is the existing bar — `evals/behaviors.md` already states "No assertion may match substrings of documentation files", and `tests/test_mechanics_scripts.py`'s docstring says "Nothing here asserts how the reference documents word the same rules."

- [ ] **Step 1: Give B8 an assertion it can fail**

`evals/behaviors.md` row B8 is "jobs.jsonl conformance + digest numbers re-derive from it", graded by "validator + artifact check". It cannot currently fail, because nothing compares the two. Rewrite its grading method to:

> artifact check: for the run's `run_id`, `skills/job-search-run/scripts/run-counts.sh` over the captured `workspace/jobs.jsonl`, the count fields in the captured `workspace/runs/<run_id>.json`, and the numbers parsed out of the digest's counts line must all be the same. Plus `validate-workspace.sh --post-close <run_id>` exiting 0.

- [ ] **Step 2: Add three behavior rows**

| id | behavior | case file | grading method |
|---|---|---|---|
| B17 | `completed_at` is a clock read: later than `started_at`, and no later than the run record's own mtime | headless-run.yaml | artifact check (parse both timestamps from the captured record; compare against its mtime) |
| B18 | every posting a search returned has a `surfaced` event, and every one the run judged has an `evaluated` event | headless-run.yaml | artifact check (count `search-jobs` responses in the transcript against `surfaced` events in the captured log) |
| B19 | a run that stops mid-flight reports how many postings it left unjudged, rather than closing as if it finished | kill-midrun.yaml | artifact check (`postings_unreviewed` in the record is non-zero and `close_state` is not `complete`) + grader-judged transcript (the follow-up session says how many were left) |

Add `B17, B18` to `headless-run.yaml`'s `behaviors:` list and `B19` to `kill-midrun.yaml`'s.

- [ ] **Step 3: Update the shim scenarios in `skills/job-search-run/evals/evals.json`**

The `harness` paragraph says the result is read from the digest, `jobs.jsonl` and the run record. Add that the close is also checked by running `run-counts.sh` and comparing its output against the record.

Scenario 1's expectations currently include "Appends one evaluated event per judged row to jobs.jsonl, each with source, source_id, query_id, detail_read, and the judgment fields". Replace with expectations that read the artifacts:

- "Every row the search returned has a `surfaced` event carrying the row's own values"
- "Every posting the run judged has an `evaluated` event, and every posting it read in full has a `detail` event"
- "The digest's counts line, the run record's counts, and `run-counts.sh` output are the same numbers"
- "`postings_unreviewed` is zero and the close is `complete`"

Scenario 3 ("every returned row is already judged") still holds: `record-api-response.sh` skips a posting carrying an `evaluated` event from any run. Keep it and add "no `surfaced` event is written for a posting that already has a judgment".

Add a scenario: **a run killed after the search leaves an honest record.** Kill the run after the last `search-jobs` call, then run `close-run.sh … --close-state interrupted`, and expect the record's `postings_surfaced` to equal the rows the searches returned and `postings_unreviewed` to equal the same number.

- [ ] **Step 4: Update `skills/job-search/evals/evals.json` and `skills/job-search-agent/evals/evals.json`**

The home-view scenario's pipeline-count assertion reads whatever `pipeline-counts.sh` prints, not a hand-worked-out number. The agent skill's usage scenario asserts the reported `agent_data_usage` equals the record's, which now equals the `call` events.

- [ ] **Step 5: Check the case files still load**

Run: `python3 -m pytest tests/test_eval_cases.py tests/test_eval_harness.py -q && python3 scripts/eval_harness.py --root .`
Expected: clean. `eval_harness.py` is not a CI job, so nothing else catches a malformed scenario file.

- [ ] **Step 6: Commit**

```bash
git add evals/ skills/*/evals/evals.json
git commit -m "test(evals): grade the counts against the log the run actually wrote"
```

---

### Task 16: Run the evals and measure

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
cat $D/workspace/runs/$RID.json
sed -n '1,6p' $D/workspace/reports/*-digest.md
sh skills/job-search-runbook/scripts/validate-workspace.sh $D/workspace --post-close $RID; echo "exit=$?"
```
Expected: the three sets of numbers agree, and the validator exits 0.

- [ ] **Step 4: Run the kill-midrun eval on both models**

```bash
python3 evals/run_eval.py --case kill-midrun --model sonnet
python3 evals/run_eval.py --case kill-midrun --model haiku
```
Expected (B19): the record's `postings_unreviewed` is non-zero, `close_state` is not `complete`, and the follow-up session says how many postings were left.

- [ ] **Step 5: Compare detail-call count against the RED baseline**

The spec records an inference that needs settling: `docs/superpowers/specs/2026-07-30-skill-overhaul-design.md:74` credits "summary-scan steer" with killing 65% of detail calls as one phrase, and this change removes the steer while keeping the scan.

From the `headless-run` results, take `postings_detail_read` and `postings_surfaced` from the record and compare the ratio against `evals/baseline/2026-07-30-red-baseline.md`. Report the actual numbers.

If detail reads rose materially, the scan's settle-or-queue instruction in `job-search-run/SKILL.md` is what to strengthen — not the steer, which anchored the reader rather than reducing reads. Re-run this step after any such edit.

- [ ] **Step 6: Run the remaining cases on both models**

```bash
for c in quickstart fault-503 schedule fit; do
  python3 evals/run_eval.py --case $c --model sonnet
  python3 evals/run_eval.py --case $c --model haiku
done
python3 evals/run_triggering.py --model sonnet --reps 9
python3 evals/run_triggering.py --model haiku --reps 9
```
Expected: no regression against `evals/baseline/2026-07-30-red-baseline.md`. B15 (every plugin file the agent opens resolves first try) matters most here — eight new scripts are eight new paths a skill names.

- [ ] **Step 7: Write the result report**

Create `docs-private/2026-08-05-counts-eval-report.md` (gitignored) with, for each case and model: the run directory, whether each behavior row passed, the measured numbers, and every row that failed with what it did instead. State plainly what was not run.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "test: run the behavior evals against the counted run"
```

---

## Self-review

**Spec coverage.** Every section of the spec maps to a task:

| Spec section | Task |
|---|---|
| §3 architecture — `call`, `surfaced` | 1 |
| §3 architecture — `detail` | 2 |
| §3 architecture — `queued` | 3 |
| §3 architecture — `evaluated` | 4 |
| §4 the run record and its four invariants | 5, 8, 9 |
| §5 timestamps and both gates | 7, 8, 9 |
| §6 opening a run validates the workspace | 7 |
| §7 a close that cannot contradict its log | 8 |
| §8 the detail-read queue | 3, 12 |
| §9 storing descriptions, and the off-disk rule reversal | 2, 11 |
| §10 file-by-file changes | 11, 12, 13 |
| §10 the two reproduced script conflicts | 6 |
| §10 the language sweep and the doc-lint owner | 14 |
| §10 the word budget | 11, 12, 16 |
| §11 where no shell runs | 1, 5 (script headers) |
| §12 testing — unit | 1–10 |
| §12 testing — behavioral | 15, 16 |
| §12 testing — live | 1, 2 (fixtures captured from the real API) |
| §13 style anchoring | 11, 12, 13 |

**Type consistency.** `run-counts.sh`'s sixteen output keys are declared once at the top of this plan and consumed by name in Tasks 8 and 9. The five event shapes are declared once and used in every task. `band` is the awk variable in Tasks 4 and 5; `match` is only ever the JSON key. `record-api-response.sh` takes `<run_id> <jobs.jsonl> <response.json>` in Tasks 1 and 2 alike.

**Two gaps this plan does not close, stated rather than hidden:**

1. **The `--sources` and `--queries` values still come from the model.** `close-run.sh` takes them as flags because a `call` event carries the source and query of each call, but a query that was enabled and never reached (a source dropped after two failures) has no call event to be counted from. Deriving them would silently narrow the record. Task 16 step 3 should check whether the two fields match the config's enabled entries, and a follow-on change can derive them from the config plus the call events if they drift.

2. **`test -nt` is unverified on Linux.** Task 9 step 6 is the gate; the fallback is specified there. If CI cannot run it, the timestamp gate ships behind a capability probe rather than being dropped.

**Placeholder scan:** no "TBD", no "add appropriate error handling", no "similar to Task N". Every code step carries the code. Every prose step names the file, the lines, and what must be true of the result, and says which eval grades it.

