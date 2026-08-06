"""Unit tests for the bundled portable-shell mechanics scripts (P4/T4.1, AAS-FORM-08).

The fiddly deterministic mechanics that skills used to execute as model-run prose contracts are
bundled as portable POSIX-`sh` scripts. Every script sits in the `scripts/` directory of a
skill, so the skill that owns it names it without computing a path; the two more than one skill runs
sit in the `job-search-runbook` skill, and its two consumers name them from the repo root. Each test drives one script via subprocess
against a temp fixture and asserts what the script does: dedup, the jobs.jsonl event-line append,
schedule-line composition, and workspace discovery.

Scripts are invoked through `sh` (and, where present, strict `dash`) — never `bash` — so a bash-only
construct fails the suite. The two `.awk` programs are driven the same way, one `awk` subprocess per
case, asserting what the program prints. Nothing here asserts how the reference documents word the
same rules.
"""
import base64
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNBOOK_SCRIPTS = ROOT / "skills" / "job-search-runbook" / "scripts"
RUN_SCRIPTS = ROOT / "skills" / "job-search-run" / "scripts"
SEARCH_SCRIPTS = ROOT / "skills" / "job-search" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures" / "api-responses"
DEDUP = RUN_SCRIPTS / "dedup.sh"
APPEND = RUN_SCRIPTS / "event-log-append.sh"
SCHEDULE = SEARCH_SCRIPTS / "schedule-line.sh"
DISCOVERY = RUNBOOK_SCRIPTS / "workspace-discovery.sh"
VALIDATE = RUNBOOK_SCRIPTS / "validate-workspace.sh"
SCAN = RUN_SCRIPTS / "json-scan.awk"
FIELD = RUN_SCRIPTS / "event-field.awk"
RECORD_API = RUN_SCRIPTS / "record-api-response.sh"
QUEUE = RUN_SCRIPTS / "queue-detail-read.sh"
LIST_QUEUE = RUN_SCRIPTS / "list-detail-read-queue.sh"
JUDGE = RUN_SCRIPTS / "record-judgment.sh"
COUNTS = RUN_SCRIPTS / "run-counts.sh"

ALL_SCRIPTS = [DEDUP, APPEND, SCHEDULE, DISCOVERY, VALIDATE, RECORD_API, QUEUE, LIST_QUEUE,
               JUDGE, COUNTS]


# A contract-valid single-line `evaluated` event, in the shape
# skills/job-search-run/templates/jobs-event.example.json shows.
def evaluated(source, source_id, ts="2026-07-11T00:00:00Z", extra=""):
    return (
        '{"event":"evaluated","ts":"%s","source":"%s","source_id":"%s",'
        '"query_id":"q","title":"T","company_name":"C","location_display":"Remote",'
        '"salary_display":"","posted_at":"%s","source_url":"https://example/%s",'
        '"posting_id_at_seen":"jp_1","detail_read":true,"relevant":true,"match":"strong",'
        '"reasoning":"solid fit","dealbreakers_hit":[],"unknowns":[],'
        '"needs_human_check":false,"status":"new","first_seen":"%s"%s}'
        % (ts, source, source_id, ts, source_id, ts, extra)
    )


def run_sh(script, args=(), input_text=None, env=None):
    """Run a mechanics script through POSIX `sh` (portable; not bash)."""
    return subprocess.run(
        ["sh", str(script), *args],
        input=input_text,
        capture_output=True,
        text=True,
        env=env,
    )


def base_env(home):
    """A clean environment rooted at `home`: no stray registry / XDG leakage from the dev box."""
    return {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "JOBSEARCH_OS_HOME": str(home),
    }


# --------------------------------------------------------------------------- dedup

def test_dedup_emits_only_new_ids(tmp_path):
    """Plan RED case: seen registry {a,b} + candidates {a,c,d} -> the script prints c,d.

    The "seen registry" is the jobs.jsonl event log; the script extracts the known source_ids for the
    source with the pinned "Known ids" pipeline and emits the candidates not already recorded.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(evaluated("linkedin", "a") + "\n" + evaluated("linkedin", "b") + "\n")
    r = run_sh(DEDUP, [str(jobs), "linkedin"], input_text="a\nc\nd\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["c", "d"], r.stdout


def test_dedup_missing_file_all_new(tmp_path):
    """Missing jobs.jsonl = an empty known set, so every candidate is new."""
    jobs = tmp_path / "does-not-exist.jsonl"
    r = run_sh(DEDUP, [str(jobs), "linkedin"], input_text="x\ny\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["x", "y"], r.stdout


def test_dedup_is_per_source_and_not_confused_by_source_id_or_url(tmp_path):
    """The `"source":"S"` grep must key per-source and never match `"source_id"`/`"source_url"`.

    linkedin has 111 (and a source_url); ashby has 222. Known(linkedin) must be exactly {111}, so
    candidate 222 (ashby's id, unknown to linkedin) and 999 are new; 111 is filtered.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(evaluated("linkedin", "111") + "\n" + evaluated("ashby", "222") + "\n")
    r = run_sh(DEDUP, [str(jobs), "linkedin"], input_text="111\n222\n999\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["222", "999"], r.stdout


def test_dedup_skips_blank_candidate_lines(tmp_path):
    """Null/blank candidate source_ids can't be deduped -> skipped (runner step 2)."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(evaluated("linkedin", "a") + "\n")
    r = run_sh(DEDUP, [str(jobs), "linkedin"], input_text="\nc\n\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["c"], r.stdout


# ------------------------------------------------------------------- event-log append

def _count_source_id(path, source_id):
    if not path.exists():
        return 0
    needle = '"source_id":"%s"' % source_id
    return sum(1 for ln in path.read_text().splitlines() if needle in ln)


def test_event_log_append_writes_exactly_one_line(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    r = run_sh(APPEND, [str(jobs)], input_text=evaluated("linkedin", "X"))
    assert r.returncode == 0, r.stderr
    assert _count_source_id(jobs, "X") == 1
    assert len(jobs.read_text().splitlines()) == 1


def test_event_log_append_is_idempotent_on_source_and_source_id(tmp_path):
    """Re-appending an evaluated event for a known (source, source_id) does not duplicate it
    (idempotency: never write a duplicate evaluated event for a known pair)."""
    jobs = tmp_path / "jobs.jsonl"
    run_sh(APPEND, [str(jobs)], input_text=evaluated("linkedin", "X", ts="2026-07-11T00:00:00Z"))
    # Same (source, source_id), later ts -> still idempotent, no second line.
    r = run_sh(APPEND, [str(jobs)], input_text=evaluated("linkedin", "X", ts="2026-07-11T09:00:00Z"))
    assert r.returncode == 0, r.stderr
    assert _count_source_id(jobs, "X") == 1, jobs.read_text()


def test_event_log_append_distinct_source_id_appends(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    run_sh(APPEND, [str(jobs)], input_text=evaluated("linkedin", "X"))
    run_sh(APPEND, [str(jobs)], input_text=evaluated("linkedin", "Y"))
    assert _count_source_id(jobs, "X") == 1
    assert _count_source_id(jobs, "Y") == 1
    assert len(jobs.read_text().splitlines()) == 2


def test_event_log_append_rejects_missing_source_id(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    bad = '{"event":"evaluated","ts":"2026-07-11T00:00:00Z","source":"linkedin","title":"T"}'
    r = run_sh(APPEND, [str(jobs)], input_text=bad)
    assert r.returncode != 0
    assert not jobs.exists() or jobs.read_text() == ""


def test_event_log_append_rejects_duplicate_source_id_key(tmp_path):
    """`"source_id"` must appear exactly once per line (grep-extraction is load-bearing)."""
    jobs = tmp_path / "jobs.jsonl"
    bad = ('{"event":"evaluated","source":"linkedin","source_id":"1","source_id":"2",'
           '"title":"T"}')
    r = run_sh(APPEND, [str(jobs)], input_text=bad)
    assert r.returncode != 0
    assert not jobs.exists() or jobs.read_text() == ""


def test_event_log_append_rejects_evaluated_without_source(tmp_path):
    """Every evaluated event carries a non-empty `"source"`, which the script requires."""
    jobs = tmp_path / "jobs.jsonl"
    bad = '{"event":"evaluated","ts":"2026-07-11T00:00:00Z","source_id":"9","title":"T"}'
    r = run_sh(APPEND, [str(jobs)], input_text=bad)
    assert r.returncode != 0
    assert not jobs.exists() or jobs.read_text() == ""


def test_event_log_append_rejects_multiline_input(tmp_path):
    """One event per line — a pretty-printed / multi-line event is rejected."""
    jobs = tmp_path / "jobs.jsonl"
    bad = evaluated("linkedin", "A") + "\n" + evaluated("linkedin", "B")
    r = run_sh(APPEND, [str(jobs)], input_text=bad)
    assert r.returncode != 0
    assert not jobs.exists() or jobs.read_text() == ""


def test_event_log_append_rejects_nested_same_role_as(tmp_path):
    """`same_role_as` is a FLAT string, never a nested object."""
    jobs = tmp_path / "jobs.jsonl"
    bad = evaluated("greenhouse", "acme:1", extra=',"same_role_as":{"source":"linkedin"}')
    r = run_sh(APPEND, [str(jobs)], input_text=bad)
    assert r.returncode != 0
    assert not jobs.exists() or jobs.read_text() == ""


def test_event_log_append_accepts_flat_same_role_as(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    good = evaluated("greenhouse", "acme:1", extra=',"same_role_as":"linkedin:999"')
    r = run_sh(APPEND, [str(jobs)], input_text=good)
    assert r.returncode == 0, r.stderr
    assert _count_source_id(jobs, "acme:1") == 1


# ----------------------------------------------------------------- schedule-line

@pytest.mark.parametrize(
    "args,expected",
    [
        (["hourly"], "0 * * * *"),
        (["every-2-hours"], "0 */2 * * *"),
        (["every-6-hours"], "0 */6 * * *"),
        (["daily"], "0 8 * * *"),            # default time 08:00
        (["daily", "08:00"], "0 8 * * *"),
        (["daily", "13:05"], "5 13 * * *"),
        (["weekly"], "0 8 * * 1"),           # default time 08:00, Monday
        (["weekly", "09:30"], "30 9 * * 1"),
    ],
)
def test_schedule_line_cadences(args, expected):
    r = run_sh(SCHEDULE, args)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == expected


def test_schedule_line_rejects_unknown_frequency():
    r = run_sh(SCHEDULE, ["fortnightly"])
    assert r.returncode != 0
    assert r.stdout.strip() == ""


# --------------------------------------------------------------- workspace discovery

def _discover(env):
    r = run_sh(DISCOVERY, env=env)
    assert r.returncode == 0, r.stderr
    out = {}
    for line in r.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def test_workspace_discovery_first_run_default(tmp_path):
    """No registry, no config anywhere -> first run at the default hidden workspace, source none."""
    d = _discover(base_env(tmp_path))
    assert d["workspace"] == str(tmp_path / ".job-search")
    assert d["source"] == "none"
    assert d["first_run"] == "true"


def test_workspace_discovery_default_has_config(tmp_path):
    ws = tmp_path / ".job-search"
    ws.mkdir()
    (ws / "config.yaml").write_text("version: 1\n")
    d = _discover(base_env(tmp_path))
    assert d["workspace"] == str(ws)
    assert d["source"] == "default"
    assert d["first_run"] == "false"


def test_workspace_discovery_legacy(tmp_path):
    ws = tmp_path / "job-search"  # visible legacy location
    ws.mkdir()
    (ws / "config.yaml").write_text("version: 1\n")
    d = _discover(base_env(tmp_path))
    assert d["workspace"] == str(ws)
    assert d["source"] == "legacy"
    assert d["first_run"] == "false"


def test_workspace_discovery_registry_override(tmp_path):
    """The registry's active_workspace wins, with an explicit $JOBSEARCH_OS_REGISTRY redirect."""
    custom = tmp_path / "custom-ws"
    custom.mkdir()
    (custom / "config.yaml").write_text("version: 1\n")
    reg = tmp_path / "registry.json"
    reg.write_text('{ "version": 1, "active_workspace": "%s" }\n' % custom)
    env = base_env(tmp_path)
    env["JOBSEARCH_OS_REGISTRY"] = str(reg)
    d = _discover(env)
    assert d["workspace"] == str(custom)
    assert d["source"] == "registry"
    assert d["first_run"] == "false"


def test_workspace_discovery_registry_wins_unconditionally(tmp_path):
    """Registry wins even when its workspace lacks config.yaml AND a default workspace has one
    (the registry decides on its own; a run never falls through to the other candidates)."""
    # A default workspace WITH a config that must NOT be chosen.
    default_ws = tmp_path / ".job-search"
    default_ws.mkdir()
    (default_ws / "config.yaml").write_text("version: 1\n")
    # Registry points elsewhere, to a workspace that has no config yet.
    custom = tmp_path / "custom-ws"
    reg = tmp_path / "registry.json"
    reg.write_text('{ "version": 1, "active_workspace": "%s" }\n' % custom)
    env = base_env(tmp_path)
    env["JOBSEARCH_OS_REGISTRY"] = str(reg)
    d = _discover(env)
    assert d["workspace"] == str(custom)
    assert d["source"] == "registry"
    assert d["first_run"] == "true"  # its config.yaml does not exist yet


# ------------------------------------------------------------------------------- json-scan.awk

def scan(text):
    r = subprocess.run(["awk", "-f", str(SCAN)], input=text, capture_output=True, text=True)
    return r, [l.split("\t", 1) for l in r.stdout.splitlines()]


def test_a_scalar_is_printed_with_its_path_and_its_raw_value():
    r, out = scan('{"data": {"results": [{"title": "Strategic Finance", "source_id": "4417545222"}]}}')
    assert r.returncode == 0, r.stderr
    assert ["data.results.0.title", '"Strategic Finance"'] in out
    assert ["data.results.0.source_id", '"4417545222"'] in out


@pytest.mark.skipif(
    not (FIXTURES / "search.linkedin.json").exists(), reason="fixture arrives in Task 1"
)
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
    # Without the byte offset, awk's own "can't open file .../json-scan.awk" also exits 2 and
    # also contains "json-scan", so a missing scanner would pass this test.
    assert re.search(r"at byte \d+", r.stderr), r.stderr


@pytest.mark.parametrize(
    "document,reason",
    [
        ('"just a string"', "a JSON document starts with { or ["),
        ('{"a":1} junk', "trailing text after the document"),
        ('{"a":"no end', "unterminated string"),
        ('{"a":}', "expected a value"),
        ('{1:2}', "expected a key"),
        ('{"a" 1}', "expected : after a key"),
        ('{"a":1 "b":2}', "expected , or } in an object"),
        ('{"a":[1 2]}', "expected , or ] in an array"),
    ],
)
def test_every_malformed_shape_exits_two_and_says_what_was_wrong(document, reason):
    r, _ = scan(document)
    assert r.returncode == 2
    assert reason in r.stderr, r.stderr
    assert re.search(r"at byte \d+", r.stderr), r.stderr


@pytest.mark.parametrize("raw", ["\n", "\t", "\r", "\001"])
def test_a_raw_control_character_inside_a_string_exits_two(raw):
    """RFC 8259 forbids a raw control character in a string, and a raw newline or tab would put a
    line break or a second tab inside a value — breaking the one-line-one-field framing that every
    `awk -F'\\t'` consumer reads by. It must not pass through as a row."""
    r, _ = scan('{"a":"one%stwo","b":2}' % raw)
    assert r.returncode == 2, r.stdout
    assert "control character" in r.stderr, r.stderr


def test_a_raw_control_character_after_a_backslash_also_exits_two():
    """The input is a backslash immediately followed by a raw newline. The escape branch skips two
    characters at once, so without a check on the second one that newline would reach the value."""
    r, _ = scan('{"a":"one\\\ntwo","b":2}')
    assert r.returncode == 2, r.stdout
    assert "control character" in r.stderr, r.stderr


def test_a_raw_control_character_inside_a_bare_token_exits_two():
    """A tab, newline or CR ends a number legitimately, so only the other control characters are
    wrong here. `{"a":1\\0012}` used to print the control character as part of the value."""
    r, _ = scan('{"a":1\0012}')
    assert r.returncode == 2, r.stdout
    assert "control character" in r.stderr, r.stderr


@pytest.mark.parametrize("ends_the_token", [" ", "\t", "\n", "\r"])
def test_whitespace_still_ends_a_bare_token_rather_than_failing(ends_the_token):
    r, out = scan('{"a":1%s,"b":2}' % ends_the_token)
    assert r.returncode == 0, r.stderr
    assert ["a", "1"] in out


def test_the_scanner_reads_a_file_named_as_an_operand(tmp_path):
    """The documented form is `awk -f json-scan.awk <file.json>`; every other test pipes stdin."""
    path = tmp_path / "response.json"
    path.write_text('{"data": {"query": {"source": "ashby"}}}', encoding="utf-8")
    r = subprocess.run(["awk", "-f", str(SCAN), str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout == 'data.query.source\t"ashby"\n'


@pytest.mark.skipif(
    not (FIXTURES / "detail.error.json").exists(), reason="fixture arrives in Task 1"
)
def test_the_real_error_body_scans_to_its_fields():
    r, out = scan((FIXTURES / "detail.error.json").read_text())
    d = dict(out)
    assert d["error.code"] == '"validation_error"'
    assert d["error.retryable"] == "false"
    assert d["error.request_id"].startswith('"req_')


# ----------------------------------------------------------------------------- event-field.awk

PROBE = "{ printf \"%s\\n%s\\n\", jraw($0, k), jval($0, k) }"


def field(line, key):
    """Read one field with the library, driven by a one-line probe program.

    POSIX awk forbids mixing `-f` with inline program text, so the probe goes in a file of its own
    and the library is chained ahead of it with a second `-f` — the way every caller runs it.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        probe = pathlib.Path(tmpdir) / "probe.awk"
        probe.write_text(PROBE + "\n", encoding="utf-8")
        r = subprocess.run(
            ["awk", "-v", "k=" + key, "-f", str(FIELD), "-f", str(probe)],
            input=line + "\n",
            capture_output=True,
            text=True,
        )
    assert r.returncode == 0, r.stderr
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


def test_a_doubled_backslash_is_one_backslash_and_does_not_eat_the_next_character():
    line = r'{"t":"C:\\temp and \\nope","company_name":"Globex"}'
    assert field(line, "t")[0] == r'"C:\\temp and \\nope"'      # jraw: byte-exact
    assert field(line, "t")[1] == "C:\\temp and \\nope"         # jval: two literal backslashes
    assert field(line, "company_name")[1] == "Globex"           # the field after it still reads


def test_a_number_a_boolean_and_a_null_come_back_as_written():
    line = '{"n":25,"ok":true,"m":null}'
    assert field(line, "n")[0] == "25"
    assert field(line, "ok")[0] == "true"
    assert field(line, "m")[0] == "null"


def test_an_absent_key_is_empty():
    assert field('{"a":1}', "b") == ("", "")


@pytest.mark.parametrize(
    "line",
    [
        '{"source":"linkedin","status":"applied","n":25}',
        '{"source": "linkedin","status": "applied","n": 25}',
        '{"source" :"linkedin","status" :"applied","n" :25}',
        '{"source" : "linkedin" , "status" : "applied" , "n" : 25 }',
    ],
)
def test_whitespace_around_the_colon_does_not_hide_a_field(line):
    """`event-log-append.sh` accepts every one of these — its field checks all read
    `"key"[[:space:]]*:[[:space:]]*` — so an event written by hand arrives in these shapes. A
    `status_changed` read as `" \\"applied\\""` would land in the wrong pipeline bucket."""
    assert field(line, "source") == ('"linkedin"', "linkedin")
    assert field(line, "status") == ('"applied"', "applied")
    assert field(line, "n") == ("25", "25")


def test_a_value_that_reads_like_the_key_is_skipped_for_the_real_key():
    """The input holds `"title"` twice: first as the value of `a`, with a space and a comma after
    it, then as the real key, with a space before its colon. Both halves are needed to reach the
    retry. Without the bare-value occurrence there is nothing to skip; without the space before the
    real key's colon, a search for the glued `"title":` would already land on the right one and
    never retry. An escaped quote in free text is written `\\"title\\"`, which never forms the bare
    `"title"` the search looks for, so free text alone does not reach this path either."""
    line = '{"a":"title" ,"title" :"Real Title"}'
    assert field(line, "title") == ('"Real Title"', "Real Title")


def test_an_object_or_an_array_value_comes_back_empty_rather_than_as_a_fragment():
    """Cut at the first `}` or `]`, a nested value would read like a real one. `json-scan.awk` is
    what reads a nested value."""
    line = '{"obj":{"b":1},"arr":[1,2],"after":"OK"}'
    assert field(line, "obj") == ("", "")
    assert field(line, "arr") == ("", "")
    assert field(line, "after")[1] == "OK"


def test_backspace_and_formfeed_resolve_and_a_unicode_escape_is_left_as_written():
    """The escape set is a decision on the record: the API sends raw UTF-8, never `\\uXXXX`
    (`grep -c '\\\\u[0-9a-fA-F]\\{4\\}'` answers 0 on a live search and a live get-posting response),
    so a `\\uXXXX` escape stays as its six characters instead of being decoded."""
    escape = "\\u00f6"                       # the six characters a JSON \uXXXX escape is written with
    assert len(escape) == 6
    line = '{"t":"a\\bb\\fc","u":"gr%sffnung","after":"OK"}' % escape
    assert field(line, "t")[1] == "a b c"
    assert json.loads(line)["u"] == "gröffnung"          # what the escape means
    assert field(line, "u")[1] == "gr%sffnung" % escape       # what jval returns: left as written
    assert field(line, "after")[1] == "OK"


# ------------------------------------------------------------------ record-api-response.sh

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


def record_search(jobs, fixture, query_id="q", shell="sh"):
    return run_script(RECORD_API, RID, jobs, FIXTURES / fixture,
                      "--route", "search-jobs", "--query-id", query_id, shell=shell)


def awk_shim(tmp_path, marker, spill=""):
    """A PATH whose `awk` fails the one invocation carrying `marker` and passes the rest through.

    Returns the env to hand `run_script`. `spill` is printed to stdout before the failure, standing
    in for the lines an awk that died partway had already written — the whole point of checking the
    status is that those lines are there and must not be used.
    """
    d = tmp_path / "shim"
    d.mkdir(exist_ok=True)
    shim = d / "awk"
    shim.write_text(
        "#!/bin/sh\n"
        "for a in \"$@\"; do\n"
        "  case $a in\n"
        "    *%s*)\n"
        "      printf '%%s' '%s'\n"
        "      echo 'awk: simulated failure' >&2\n"
        "      exit 2 ;;\n"
        "  esac\n"
        "done\n"
        "exec %s \"$@\"\n" % (marker, spill, shutil.which("awk")),
        encoding="utf-8")
    shim.chmod(0o755)
    return {"PATH": "%s:%s" % (d, os.environ["PATH"])}


SPILL = '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"partial-1"}\\n' % RID


def test_a_failure_reading_the_rows_appends_nothing_and_records_the_call(tmp_path):
    """The row count is written in that awk's END block, so it is absent exactly when the awk died.
    Reading it as 0 would append the rows that did reach the file next to a call event saying the
    call returned nothing."""
    jobs = tmp_path / "jobs.jsonl"
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "search.linkedin.json", "--route",
                   "search-jobs", "--query-id", "q", env=awk_shim(tmp_path, "badfile=", SPILL))
    assert r.returncode == 1, r.stdout + r.stderr
    assert [e for e in lines(jobs) if e["event"] == "surfaced"] == []
    calls = [e for e in lines(jobs) if e["event"] == "call"]
    assert len(calls) == 1 and calls[0]["ok"] is False


def test_a_failure_skipping_seen_postings_appends_nothing_and_records_the_call(tmp_path):
    """Lower stakes than the row builder — the response was read, so the call event still carries
    a truthful `rows_returned` — but appending a partial dedup would record part of a response as
    all of it."""
    jobs = tmp_path / "jobs.jsonl"
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "search.linkedin.json", "--route",
                   "search-jobs", "--query-id", "q",
                   env=awk_shim(tmp_path, "dedup-surfaced.awk", SPILL))
    assert r.returncode == 1, r.stdout + r.stderr
    assert [e for e in lines(jobs) if e["event"] == "surfaced"] == []
    calls = [e for e in lines(jobs) if e["event"] == "call"]
    assert len(calls) == 1
    assert calls[0]["ok"] is True
    assert calls[0]["rows_returned"] == len(api_rows("search.linkedin.json"))
    assert calls[0]["rows_new"] == 0


@pytest.mark.parametrize("tail,says", [
    ([], "usage:"),                                            # fewer than three arguments
    (["--route"], "usage:"),                                   # --route with no value after it
    (["--route", "bogus"], "--route must be"),                 # not a route this script knows
    (["--route", "search-jobs", "--nope"], "unknown option"),  # an option it does not take
])
def test_bad_arguments_exit_two_and_append_nothing(tmp_path, tail, says):
    """Each case asserts what stderr says, not only the exit code. `set -u` turns an unguarded
    `$2` into an exit 2 of its own, so a test that checked the code alone would pass with the
    argument guards deleted and the operator left reading `$2: parameter not set`."""
    jobs = tmp_path / "jobs.jsonl"
    head = [RID] if not tail else [RID, jobs, FIXTURES / "search.zero.json"]
    r = run_script(RECORD_API, *head, *tail)
    assert r.returncode == 2, r.stdout
    assert says in r.stderr, r.stderr
    assert not jobs.exists()


@pytest.mark.parametrize("flag,says", [
    ([], "needs --query-id"),                              # no --query-id at all
    (["--query-id", ""], "needs --query-id"),              # an empty one says nothing either
    (["--query-id", "sf,remote"], "neither a comma nor a colon"),
    (["--query-id", "sf:remote"], "neither a comma nor a colon"),
    (["--query-id", "q", "--source", "a,b"], "neither a comma nor a colon"),
    (["--query-id", "q", "--source", "a:b"], "neither a comma nor a colon"),
], ids=["absent", "empty", "query-id comma", "query-id colon", "source comma", "source colon"])
def test_a_search_call_is_refused_without_a_query_id_that_names_one_search(tmp_path, flag, says):
    """`run-counts.sh` groups the search calls by source and query id, so the query id is what tells
    one search on a source from another. Refusing it here rather than working around a null one in
    the counter is what keeps a retry sequence a single group.

    A comma and a colon are refused in **both** halves of that pair, because the lost searches are
    named as a comma-separated list of `source:query_id` entries. Measured with only the query id
    checked: three failed attempts with `--source a,b --query-id q1` reported
    `searches_never_succeeded_ids=a,b:q1`, which reads as two lost searches, at exit 0.
    """
    jobs = tmp_path / "jobs.jsonl"
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "search.zero.json", "--route", "search-jobs",
                   *flag)
    assert r.returncode == 2, r.stdout + r.stderr
    assert says in r.stderr, r.stderr
    assert not jobs.exists()


@pytest.mark.parametrize("bad,says", [
    ("a\vb", "control character"),      # a vertical tab: not whitespace, and JSON forbids it raw
    ("a\nb", "control character"),      # the one awk itself disagrees about
    ("a\\tb", "backslash"),
], ids=["vertical-tab", "newline", "backslash"])
@pytest.mark.parametrize("where", ["run_id", "--source", "--query-id"])
def test_an_identifier_the_search_writer_takes_is_refused(tmp_path, where, bad, says):
    """A run id, a source and a query id name things other scripts look up, so neither of these
    characters may be in one.

    A control character does not cross `awk -v` the same way twice: a literal newline in a -v
    assignment is a syntax error under BSD awk and an accepted value under mawk, which is the awk
    Ubuntu CI runs. `esc` would make it valid JSON wherever it did arrive, but it would then sit in
    the log escaped while every lookup greps for the raw form, so the posting could never be found.

    A backslash is resolved by awk before the program runs. Measured before this guard:
    `--query-id a\\tb` put the four characters on the call event, through the environment, and a real
    tab on all 25 surfaced events, through -v, and `run-counts.awk` groups on the call event — so
    the group and its own rows disagreed, with every line parsing.
    """
    jobs = tmp_path / "jobs.jsonl"
    args = {"run_id": RID, "--source": "linkedin", "--query-id": "q"}
    args[where] = bad
    r = run_script(RECORD_API, args["run_id"], jobs, FIXTURES / "search.zero.json",
                   "--route", "search-jobs", "--source", args["--source"],
                   "--query-id", args["--query-id"])
    assert r.returncode == 2, r.stdout + r.stderr
    assert says in r.stderr, r.stderr
    assert where in r.stderr, r.stderr                 # which of the three carries it
    assert not jobs.exists()


def test_a_missing_response_file_exits_two_and_appends_nothing(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    r = run_script(RECORD_API, RID, jobs, tmp_path / "nope.json", "--route", "search-jobs",
                   "--query-id", "q")
    assert r.returncode == 2
    assert "no such file" in r.stderr
    assert not jobs.exists()


def test_the_source_flag_names_the_source_of_a_call_that_returned_no_rows(tmp_path):
    """With no rows there is no row to read the source from, so `--source` is the only thing that
    can say which source the call was billed against."""
    with_flag = tmp_path / "with.jsonl"
    r = run_script(RECORD_API, RID, with_flag, FIXTURES / "search.zero.json",
                   "--route", "search-jobs", "--query-id", "q", "--source", "ashby")
    assert r.returncode == 0, r.stderr
    assert [e for e in lines(with_flag) if e["event"] == "call"][0]["source"] == "ashby"
    without = tmp_path / "without.jsonl"
    run_script(RECORD_API, RID, without, FIXTURES / "search.zero.json", "--route", "search-jobs",
               "--query-id", "q")
    assert [e for e in lines(without) if e["event"] == "call"][0]["source"] is None


def test_a_search_response_surfaces_one_event_per_row(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = record_search(jobs, "search.linkedin.json", "strategic-finance-sf")
    assert r.returncode == 0, r.stderr
    api = api_rows("search.linkedin.json")
    surfaced = [e for e in lines(jobs) if e["event"] == "surfaced"]
    assert len(surfaced) == len(api)
    assert {e["posting_id_at_seen"] for e in surfaced} == {row["id"] for row in api}
    # The call event's own fields: `source` is read back out of the first surfaced line, and the
    # two counts are what every later task's per-source and per-run totals are added up from.
    call = [e for e in lines(jobs) if e["event"] == "call"][0]
    assert call["source"] == api[0]["source"]
    assert call["rows_returned"] == len(api) and call["rows_new"] == len(api)


def test_surfaced_values_equal_the_api_values(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = record_search(jobs, "search.ashby.json")
    assert r.returncode == 0, r.stderr
    api = {row["id"]: row for row in api_rows("search.ashby.json")}
    surfaced = [x for x in lines(jobs) if x["event"] == "surfaced"]
    # Without this the loop below iterates nothing and the test passes with no script at all.
    assert len(surfaced) == len(api)
    for e in surfaced:
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
        r = record_search(jobs, name)
        assert r.returncode == 0, r.stderr
        for row in api_rows(name):
            api[row["id"]] = row
    surfaced = [x for x in lines(jobs) if x["event"] == "surfaced"]
    # Without this the loop below iterates nothing and the test passes with no script at all.
    assert len(surfaced) == len(api)
    for e in surfaced:
        row = api[e["posting_id_at_seen"]]
        p, q = row.get("posted_at"), row.get("published_at")
        assert e["posted_at"] == (max(p, q) if p and q else (p or q))


def test_posted_at_takes_the_later_date_when_a_row_carries_both(tmp_path):
    """Neither live fixture fills both fields — LinkedIn fills `posted_at` and leaves
    `published_at` null, Ashby the reverse — so the branch that compares the two dates is only
    reached from a row written here."""
    both = tmp_path / "both.json"
    both.write_text(json.dumps({"data": {"query": {"source": "ashby"}, "results": [
        {"source": "ashby", "source_id": "s1", "id": "jp_1",
         "source_url": "https://example.invalid/1",
         "posted_at": "2026-01-01T00:00:00+00:00", "published_at": "2026-06-30T00:00:00+00:00"},
        {"source": "ashby", "source_id": "s2", "id": "jp_2",
         "source_url": "https://example.invalid/2",
         "posted_at": "2026-06-30T00:00:00+00:00", "published_at": "2026-01-01T00:00:00+00:00"}]}}))
    jobs = tmp_path / "jobs.jsonl"
    r = run_script(RECORD_API, RID, jobs, both, "--route", "search-jobs", "--query-id", "q")
    assert r.returncode == 0, r.stderr
    dates = {e["source_id"]: e["posted_at"] for e in lines(jobs) if e["event"] == "surfaced"}
    assert dates == {"s1": "2026-06-30T00:00:00+00:00", "s2": "2026-06-30T00:00:00+00:00"}


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


def test_one_bad_row_rejects_the_whole_response(tmp_path):
    """All-or-nothing: the good rows next to a bad one are not appended either, so a response is
    never half-recorded."""
    bad = tmp_path / "onebad.json"
    rows = [dict(r) for r in api_rows("search.ashby.json")[:3]]
    del rows[1]["source_id"]
    bad.write_text(json.dumps({"data": {"query": {"source": "ashby"}, "results": rows}}))
    jobs = tmp_path / "jobs.jsonl"
    r = run_script(RECORD_API, RID, jobs, bad, "--route", "search-jobs", "--query-id", "q")
    assert r.returncode == 1
    assert "row 2" in r.stderr, r.stderr
    assert [e for e in lines(jobs) if e["event"] == "surfaced"] == []
    call = [e for e in lines(jobs) if e["event"] == "call"][0]
    assert call["rows_returned"] == len(rows) and call["rows_new"] == 0


def test_a_truncated_response_records_the_call_and_appends_no_rows(tmp_path):
    """`json-scan.awk` prints the rows it read before the bad byte, then exits 2. Those rows are
    real and complete, so a script that read them would append a short list of results and report
    it as the whole response."""
    cut = tmp_path / "cut.json"
    whole = (FIXTURES / "search.ashby.json").read_text()
    cut.write_text(whole[:len(whole) // 2])
    jobs = tmp_path / "jobs.jsonl"
    r = run_script(RECORD_API, RID, jobs, cut, "--route", "search-jobs", "--query-id", "q")
    assert r.returncode == 1
    assert "not well-formed JSON" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "surfaced"] == []
    calls = [e for e in lines(jobs) if e["event"] == "call"]
    assert len(calls) == 1 and calls[0]["ok"] is False and calls[0]["rows_returned"] == 0


@pytest.mark.parametrize("key", ["source", "source_id", "id", "source_url"])
def test_an_empty_string_in_a_required_field_is_refused(tmp_path, key):
    """A JSON empty string reaches the row builder as the two characters `""`, not as awk's own
    empty string, so it has to be named separately. A row carrying `"source_id":""` would be
    appended and then never found again — the outcome the non-string check refuses one branch
    later, in the same words."""
    row = {"source": "linkedin", "source_id": "s1", "id": "jp_x",
           "source_url": "https://example.invalid/x"}
    row[key] = ""
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"data": {"results": [row]}}))
    jobs = tmp_path / "jobs.jsonl"
    r = run_script(RECORD_API, RID, jobs, empty, "--route", "search-jobs", "--query-id", "q")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "is missing %s" % key in r.stderr, r.stderr
    assert [e for e in lines(jobs) if e["event"] == "surfaced"] == []


def test_a_non_string_id_is_refused_at_ingestion(tmp_path):
    """Every script that finds a posting greps for the quoted form, so a numeric id would be
    surfaced and then unreachable. Refuse it where it arrives, not three scripts later."""
    bad = tmp_path / "numeric.json"
    bad.write_text(json.dumps({"data": {"results": [
        {"source": "linkedin", "source_id": 4449006488, "id": "jp_x",
         "source_url": "https://example.invalid/x"}]}}))
    r = run_script(RECORD_API, RID, tmp_path / "jobs.jsonl", bad, "--route", "search-jobs",
                   "--query-id", "q")
    assert r.returncode == 1
    assert "source_id" in r.stderr


def test_a_response_that_does_not_match_the_route_is_refused(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "search.linkedin.json", "--route", "get-posting")
    assert r.returncode == 2
    assert "get-posting" in r.stderr


def test_a_get_posting_body_is_not_recorded_as_a_search(tmp_path):
    """A posting body carries neither `data.query` nor `data.results`. Read as a search it would
    record a call that returned nothing, which is what a search that found nothing also records."""
    posting = tmp_path / "posting.json"
    posting.write_text(json.dumps({"data": {"source": "ashby", "source_id": "s1", "id": "jp_1",
                                            "description_markdown": "A role."},
                                   "meta": {"request_id": "req_1"}}))
    jobs = tmp_path / "jobs.jsonl"
    r = run_script(RECORD_API, RID, jobs, posting, "--route", "search-jobs", "--query-id", "q")
    assert r.returncode == 2
    assert [e for e in lines(jobs) if e["event"] == "surfaced"] == []


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


def seeded_jobs(tmp_path, search_fixture):
    """A log holding the surfaced events of one search, which is what a detail read needs to exist
    against: a posting is only stored for a run that surfaced it.

    The search is asserted here rather than in each caller. Without it a seeding search that failed
    — a missing fixture, a broken script — leaves an empty log, and every test that seeds then runs
    against something other than what it says it does.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = record_search(jobs, search_fixture)
    assert r.returncode == 0, r.stderr
    return jobs


def record_detail(jobs, fixture, shell="sh"):
    return run_script(RECORD_API, RID, jobs, FIXTURES / fixture, "--route", "get-posting",
                      shell=shell)


def test_a_detail_read_takes_no_query_id(tmp_path):
    """A detail read is not grouped by query when a run's numbers are worked out, so the query-id
    guard on the search route must not reach it. Every call here passes no `--query-id` at all."""
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    r = record_detail(jobs, "detail.ashby.json")
    assert r.returncode == 0, r.stderr
    assert len([e for e in lines(jobs) if e["event"] == "detail"]) == 1


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
    r = record_detail(jobs, "detail.linkedin.json")
    assert r.returncode == 0, r.stderr
    stored = [e for e in lines(jobs) if e["event"] == "detail"][0]
    original = json.loads((FIXTURES / "detail.linkedin.json").read_text())["data"]
    assert stored["description_markdown"] == original["description_markdown"]


def test_a_nested_object_in_a_posting_body_does_not_reach_the_detail_event(tmp_path):
    """A live posting body nests — `address_structured` and `compensation_structured` are objects —
    so the event is built from the fields directly under `data` and nothing deeper. The nested keys
    here are named after fields the event does carry, which is the only way this is observable at
    all.

    Two things hold the rule up, and only losing both leaks: the `^data\\.[^.]+$` pattern, which a
    three-segment path never matches, and taking the second path segment rather than the last.
    Measured — switching to the last segment on its own changes no output, because the pattern has
    already rejected the line. Relaxing the pattern as well is what puts `Basement` and
    `nested-0001` on the event, and that is the mutation this fails against.
    """
    assert any(isinstance(v, dict) and v for v in
               json.loads((FIXTURES / "detail.ashby.json").read_text())["data"].values()), \
        "the live shape no longer nests, so this test guards nothing that happens"
    body = tmp_path / "nested.json"
    body.write_text(json.dumps({"data": {
        "source": "ashby", "source_id": "ashby-0000", "workplace_type": "Hybrid",
        "description_markdown": "A role.",
        "address_structured": {"locality": "Sydney", "workplace_type": "Basement",
                               "source_id": "nested-0001"}},
        "meta": {"request_id": "req_1"}}))
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    r = run_script(RECORD_API, RID, jobs, body, "--route", "get-posting")
    assert r.returncode == 0, r.stderr
    stored = [e for e in lines(jobs) if e["event"] == "detail"][0]
    assert stored["workplace_type"] == "Hybrid"
    assert stored["source_id"] == "ashby-0000"


@pytest.mark.parametrize("row,names", [
    ({"source_id": "ashby-0000"}, "data.source"),                    # no source key at all
    ({"source": "", "source_id": "ashby-0000"}, "data.source"),      # source is an empty string
    ({"source": None, "source_id": "ashby-0000"}, "data.source"),    # source is a JSON null
    ({"source": "ashby", "source_id": ""}, "data.source_id"),        # source_id is an empty string
    ({"source": "ashby", "source_id": None}, "data.source_id"),      # source_id is a JSON null
    ({"source": None, "source_id": None}, "data.source and data.source_id"),
])
def test_a_posting_body_without_a_usable_source_and_source_id_is_refused(tmp_path, row, names):
    """Both values are what a posting is filed under, and both have to hold text. Absent, empty
    string and null all satisfy the `data.source_id` path check the branch opens with, and all
    three are caught only here.

    The message names which field, because the operator has to know where to look. A null read
    through `field` would say `no surfaced posting for ashby:null`, pointing at the run's search
    results when the fault is in the response body.

    Exit 2, not 1, and no `call` event: an unusable body is the caller handing over the wrong file,
    which is what the search path does with the same shape. A call that happened is recorded by the
    branches below this one."""
    body = tmp_path / "body.json"
    body.write_text(json.dumps({"data": dict(row, description_markdown="A role."),
                                "meta": {"request_id": "req_1"}}))
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    before = [e for e in lines(jobs) if e["event"] == "call"]
    r = run_script(RECORD_API, RID, jobs, body, "--route", "get-posting")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "no usable %s —" % names in r.stderr, r.stderr
    assert [e for e in lines(jobs) if e["event"] == "detail"] == []
    assert [e for e in lines(jobs) if e["event"] == "call"] == before


@pytest.mark.parametrize("row,names", [
    ({"source": "ashby", "source_id": 4449006488}, "data.source_id"),
    ({"source": "ashby", "source_id": True}, "data.source_id"),
    ({"source": 7, "source_id": "ashby-0000"}, "data.source"),
    ({"source": 7, "source_id": 8}, "data.source and data.source_id"),
])
def test_a_non_string_source_or_source_id_in_a_posting_body_is_refused(tmp_path, row, names):
    """The fourth check the row builder makes, brought across. Every script that finds a posting
    matches the quoted form, so a numeric `source_id` would be stored and then never found again —
    the same reason the search half refuses it where it arrives.

    Without it the body reached the surfaced check and the operator was told `no surfaced posting
    for ashby:123`, which sends them to the run's search results when the fault is in the body. An
    object or an array never gets this far: the shape gate wants `data.source_id` as a scalar."""
    body = tmp_path / "body.json"
    body.write_text(json.dumps({"data": dict(row, description_markdown="A role."),
                                "meta": {"request_id": "req_1"}}))
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    before = [e for e in lines(jobs) if e["event"] == "call"]
    r = run_script(RECORD_API, RID, jobs, body, "--route", "get-posting")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "has a non-string %s —" % names in r.stderr, r.stderr
    assert [e for e in lines(jobs) if e["event"] == "detail"] == []
    assert [e for e in lines(jobs) if e["event"] == "call"] == before


def test_a_source_id_that_is_the_string_null_is_still_a_real_value(tmp_path):
    """`field` strips the quotes, so a JSON null and the four-character string `null` come out of
    it identical. The check above reads the raw scan value instead, where the two are six
    characters and four. This body therefore gets past it and is refused by the surfaced check —
    exit 1 for a posting this run did not surface, not exit 2 for an unusable body."""
    body = tmp_path / "body.json"
    body.write_text(json.dumps({"data": {"source": "ashby", "source_id": "null",
                                         "description_markdown": "A role."},
                                "meta": {"request_id": "req_1"}}))
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    r = run_script(RECORD_API, RID, jobs, body, "--route", "get-posting")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "no surfaced posting for ashby:null" in r.stderr, r.stderr


def test_a_detail_for_a_posting_this_run_never_surfaced_is_refused(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r = record_detail(jobs, "detail.ashby.json")
    assert r.returncode == 1
    assert "no surfaced posting" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "detail"] == []
    # The caller had already paid for the read before handing it here, so the refusal still counts.
    calls = [e for e in lines(jobs) if e["event"] == "call"]
    assert len(calls) == 1 and calls[0]["route"] == "get-posting"


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
    # Paired with the repeat read above, which records 0: one read stores one posting.
    assert calls[0]["rows_new"] == 1


def test_a_posting_surfaced_by_another_run_is_not_enough(tmp_path):
    """The surfaced check is scoped to this run, unlike the judged check the search path uses. A
    posting carried over from an earlier run has no summary row in this run to store text against."""
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    other = "\n".join(l.replace(RID, "2026-01-01T00-00-00Z") for l in
                      jobs.read_text().splitlines() if l.strip())
    jobs.write_text(other + "\n")
    r = record_detail(jobs, "detail.ashby.json")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "no surfaced posting" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "detail"] == []


@pytest.mark.skipif(not shutil.which("dash"), reason="dash is not installed here")
def test_the_detail_path_runs_under_dash(tmp_path):
    """The posting branch adds constructs the search path does not use — a negated pipeline of
    greps and an awk exit status read back into a variable — so run it under strict dash too."""
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    r = record_detail(jobs, "detail.ashby.json", shell="dash")
    assert r.returncode == 0, r.stderr
    stored = [e for e in lines(jobs) if e["event"] == "detail"]
    original = json.loads((FIXTURES / "detail.ashby.json").read_text())["data"]
    assert len(stored) == 1
    assert stored[0]["description_markdown"] == original["description_markdown"]


# ------------------------------- queue-detail-read.sh / list-detail-read-queue.sh

def first_surfaced(jobs):
    return [e for e in lines(jobs) if e["event"] == "surfaced"][0]


def test_queueing_records_only_that_the_posting_is_to_be_read(tmp_path):
    """Five keys and no sixth. Nothing about the expected judgment goes on the event: a provisional
    band would tell the reader what to conclude before it has read the posting, and a named question
    would fix the scope of its answer. `evaluate-job-fit` derives the open question from the posting
    itself, with the posting in front of it.

    The key set is asserted whole rather than key by key, because a sixth key is the regression this
    test exists to catch, and asserting the five present ones still passes with a sixth one there."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(QUEUE, jobs, "--run-id", RID, "--source", row["source"],
                   "--source-id", row["source_id"])
    assert r.returncode == 0, r.stderr
    q = [e for e in lines(jobs) if e["event"] == "queued"]
    assert len(q) == 1
    assert set(q[0]) == {"event", "run_id", "source", "source_id", "ts"}


@pytest.mark.parametrize("bad,says", [
    ("a\vb", "control character"),
    ("a\nb", "control character"),
    ("a\\tb", "backslash"),
], ids=["vertical-tab", "newline", "backslash"])
@pytest.mark.parametrize("flag", ["--run-id", "--source", "--source-id", "--ts"])
def test_an_identifier_the_queue_writer_takes_is_refused(tmp_path, flag, bad, says):
    """Every value this script writes is an identifier, `--ts` included, and `--ts` is the one with
    no lookup in front of it — the run id, the source and the source id have to match a surfaced
    event first, so a bad one of those fails that match rather than reaching the event.

    Measured before this guard, `--ts` carrying a newline: BSD awk wrote no queued event and exited
    2, mawk wrote one and exited 0. The same command, two answers — and on the BSD awk side the
    queued posting is absent from the list a reader works from, for a reason the operator sees only
    as `awk: newline in string`.
    """
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    row = first_surfaced(jobs)
    args = {"--run-id": RID, "--source": row["source"], "--source-id": row["source_id"],
            "--ts": "2026-01-01T00:00:00Z"}
    args[flag] = bad
    before = jobs.read_text()
    r = run_script(QUEUE, jobs, *[x for kv in args.items() for x in kv])
    assert r.returncode == 1, r.stdout + r.stderr
    assert says in r.stderr, r.stderr
    assert flag in r.stderr, r.stderr
    assert jobs.read_text() == before                  # nothing written either way


def test_queueing_a_posting_no_search_surfaced_is_refused(tmp_path):
    """The queue is a list of postings this run can fetch and judge, so every entry has to name a
    posting this run surfaced. Without the check a typo puts an id on the queue that no later script
    can resolve to a title, a company or a URL."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    r = run_script(QUEUE, jobs, "--run-id", RID, "--source", "linkedin",
                   "--source-id", "not-a-real-id")
    assert r.returncode == 1
    assert "no surfaced posting" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "queued"] == []


@pytest.mark.parametrize("drop", ["--run-id", "--source", "--source-id"])
def test_a_missing_flag_is_named_rather_than_read_as_a_posting_nothing_surfaced(tmp_path, drop):
    """Each case asserts the whole stderr line, not only the exit code. Without the three guards an
    absent flag reaches the grep chain as an empty string, matches nothing, and the operator is told
    `no surfaced posting for :linkedin-0000 in run 2026-08-06T00-00-00Z` — which sends them to the
    run's search results when the fault is on the command line. Both paths exit 1, so a test reading
    the code alone would pass with the guards deleted (measured: with all three removed, the three
    cases here are the only tests in this module that fail)."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    flags = {"--run-id": RID, "--source": row["source"], "--source-id": row["source_id"]}
    del flags[drop]
    r = run_script(QUEUE, jobs, *[x for pair in flags.items() for x in pair])
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stderr == "queue-detail-read: missing %s\n" % drop
    assert [e for e in lines(jobs) if e["event"] == "queued"] == []


def test_queueing_against_a_missing_log_names_the_path(tmp_path):
    """The whole stderr line, for the same reason the missing-flag cases assert it. Without the
    guard the path reaches the grep chain, which prints its own `grep: …: No such file or directory`
    and then the operator is told `no surfaced posting for ashby:a in run …` — the run's search
    results, when the fault is on the command line. Exit 1 either way."""
    jobs = tmp_path / "nope.jsonl"
    r = run_script(QUEUE, jobs, "--run-id", RID, "--source", "ashby", "--source-id", "a")
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stderr == "queue-detail-read: no such file: %s\n" % jobs
    assert not jobs.exists()


def test_queueing_twice_is_reported_and_appends_nothing(tmp_path):
    """Exit 0, because the posting the caller asked for is on the queue when the script returns.
    The line count is what says the second invocation wrote nothing — a second `queued` event would
    make the posting appear twice in the list a reader works from."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    args = (jobs, "--run-id", RID, "--source", row["source"], "--source-id", row["source_id"])
    run_script(QUEUE, *args)
    before = len(lines(jobs))
    r = run_script(QUEUE, *args)
    assert r.returncode == 0 and "already queued" in r.stderr
    assert len(lines(jobs)) == before


def test_a_given_timestamp_is_what_the_queued_event_carries(tmp_path):
    """`--ts` is what lets a caller stamp every event of one run with the same time, and it is the
    only way to assert the value of `ts` rather than its presence — the default reads the clock."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(QUEUE, jobs, "--run-id", RID, "--source", row["source"],
                   "--source-id", row["source_id"], "--ts", "2026-08-06T12:00:00Z")
    assert r.returncode == 0, r.stderr
    assert [e for e in lines(jobs) if e["event"] == "queued"][0]["ts"] == "2026-08-06T12:00:00Z"


def test_a_queued_event_with_no_ts_flag_carries_the_time_it_was_written(tmp_path):
    """With no `--ts` the script reads the clock, and this is what says so. The key-set assertion
    above checks that `ts` is present, not that it holds anything, so dropping the `date` call and
    leaving `ts` empty ships `"ts":""` and passes there. `ts` is one of the five fields on the
    event, and Task 5 counts a run from these timestamps.

    Both bounds are read from Python's own UTC clock around the call, so nothing here is a literal
    date. The format is asserted as well as the value, because `date -u +%Y-%m-%dT%H:%M:%SZ` is
    what every other event in the log is stamped with."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    before = time.strftime(fmt, time.gmtime())
    r = run_script(QUEUE, jobs, "--run-id", RID, "--source", row["source"],
                   "--source-id", row["source_id"])
    after = time.strftime(fmt, time.gmtime())
    assert r.returncode == 0, r.stderr
    ts = [e for e in lines(jobs) if e["event"] == "queued"][0]["ts"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ts), ts
    assert before <= ts <= after, (before, ts, after)


def test_the_queue_carries_what_a_reader_needs_and_nothing_that_prejudges(tmp_path):
    """Six fields, in this order, taken from the surfaced event rather than from anything the test
    knows: `source` and `source_id` file the posting, `posting_id_at_seen` and `source_url` fetch
    it, `title` and `company_name` let a reader see which posting the line is. Comparing the whole
    list is what rules out a seventh field holding a provisional band or a named question."""
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
    """Titles and company names are free text, so the queue reads them through `jval`, which
    resolves the escapes a real posting carries. Reading them with `jraw` instead hands the reader
    `"Manager \\"Finance\\" role"` — the outer quotes and the escapes exactly as the event has
    them (measured by running both readers over this line)."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"surfaced","run_id":"%s","source":"ashby","source_id":"a",'
        '"posting_id_at_seen":"jp_1","source_url":"https://example.invalid/1",'
        '"title":"Manager \\"Finance\\" role","company_name":"Globex"}\n'
        '{"event":"queued","run_id":"%s","source":"ashby","source_id":"a","ts":"x"}\n' % (RID, RID))
    r = run_script(LIST_QUEUE, jobs, RID)
    assert r.stdout.rstrip("\n").split("\t")[4] == 'Manager "Finance" role'


def test_a_posting_queued_twice_in_the_log_is_listed_once(tmp_path):
    """`queue-detail-read.sh` checks for an existing `queued` event and then appends, and those two
    steps are not one operation: two invocations racing each other can both pass the check and both
    write. Readers run in parallel on a host with subagents, so the log really can hold the pair.

    The `!(k in queued)` guard in the awk is the only thing that keeps that from putting the posting
    on the list twice, and this is the only test that drives it — the script refuses to produce the
    input, so the duplicate is written here by hand."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    dup = ('{"event":"queued","run_id":"%s","source":"%s","source_id":"%s","ts":"x"}\n'
           % (RID, row["source"], row["source_id"]))
    jobs.write_text(jobs.read_text() + dup + dup)
    out = run_script(LIST_QUEUE, jobs, RID).stdout.strip().splitlines()
    assert len(out) == 1, out
    assert out[0].split("\t")[1] == row["source_id"]


def test_the_queue_drains_as_judgments_land(tmp_path):
    """What makes the queue usable across more than one context window: a reader that comes back
    after judging one of the three postings is handed the two it has not judged."""
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


def test_the_queue_is_scoped_to_the_run_it_is_asked_for(tmp_path):
    """jobs.jsonl holds every run the workspace has ever done, and this is what a run reads to find
    its own remaining work. Without the scope each run is handed the other's queue.

    The last event seeds the harder half. Both runs surface the same posting under different
    titles, so the display fields have to be taken from the run being listed rather than from
    whichever surfaced event landed last. Dropping `rid == want` from the three branches — which is
    the same as ignoring the second operand — was caught by nothing before this test.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"][:2]
    run_script(QUEUE, jobs, "--run-id", RID, "--source", rows[0]["source"],
               "--source-id", rows[0]["source_id"])
    older, stale = "2026-01-01T00-00-00Z", "Surfaced by the earlier run"
    assert rows[0]["title"] != stale

    def event(row, **over):
        return json.dumps(dict(row, **over), separators=(",", ":")) + "\n"

    jobs.write_text(
        jobs.read_text()
        + event(rows[1], run_id=older)
        + '{"event":"queued","run_id":"%s","source":"%s","source_id":"%s","ts":"x"}\n'
          % (older, rows[1]["source"], rows[1]["source_id"])
        + event(rows[0], run_id=older, title=stale))
    mine = run_script(LIST_QUEUE, jobs, RID).stdout.strip().splitlines()
    theirs = run_script(LIST_QUEUE, jobs, older).stdout.strip().splitlines()
    assert [l.split("\t")[1] for l in mine] == [rows[0]["source_id"]]
    assert [l.split("\t")[1] for l in theirs] == [rows[1]["source_id"]]
    assert mine[0].split("\t")[4] == rows[0]["title"]


def test_an_empty_queue_prints_nothing_and_succeeds(tmp_path):
    """A run that surfaced postings and queued none of them prints nothing and exits 0. An empty
    stdout is how the caller learns there is nothing left to read, so a non-zero exit would tell it
    the log is broken instead."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    r = run_script(LIST_QUEUE, jobs, RID)
    assert r.returncode == 0 and r.stdout == ""


@pytest.mark.skipif(not shutil.which("dash"), reason="dash is not installed here")
def test_the_queue_scripts_run_under_dash(tmp_path):
    """Both scripts use constructs `record-api-response.sh` does not — it contains no `:?` and no
    `exec` (`grep -c` answers 0 for each). These use `${1:?}` and `${2?}` to reject a missing
    operand or option value, and `exec` to replace the shell with awk. Run them under strict dash as
    well as the host `sh`, because `sh -n` and `dash -n` only check syntax."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    q = run_script(QUEUE, jobs, "--run-id", RID, "--source", row["source"],
                   "--source-id", row["source_id"], shell="dash")
    assert q.returncode == 0, q.stderr
    r = run_script(LIST_QUEUE, jobs, RID, shell="dash")
    assert r.returncode == 0, r.stderr
    assert r.stdout.rstrip("\n").split("\t")[:2] == [row["source"], row["source_id"]]


# ------------------------------------------------------------------------ record-judgment.sh

HOSTILE = 'He said "it\'s a \\"strong\\" fit" — path C:\\temp\ttab\nand a newline.'


def judge_args(jobs, row, **kw):
    args = [jobs, "--run-id", RID, "--source", row["source"], "--source-id", row["source_id"]]
    for k, v in kw.items():
        args += ["--" + k.replace("_", "-"), v]
    return args


@pytest.mark.parametrize("bad,says", [
    ("a\vb", "control character"),
    ("a\nb", "control character"),
    ("a\\tb", "backslash"),
], ids=["vertical-tab", "newline", "backslash"])
@pytest.mark.parametrize("flag", ["--run-id", "--source", "--source-id", "--ts",
                                  "--same-role-as", "--posted-at-extracted"])
def test_an_identifier_the_judgment_writer_takes_is_refused(tmp_path, flag, bad, says):
    """The identifiers, and only the identifiers. The three free-text values are the case below and
    are never refused.

    Measured before this guard, `--ts` carrying a newline: BSD awk wrote no evaluated event and
    exited 1, mawk wrote one and exited 0 — the same judgment recorded on one host and lost on the
    next.
    """
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    row = first_surfaced(jobs)
    args = {"--run-id": RID, "--source": row["source"], "--source-id": row["source_id"],
            "--detail-read": "false", "--relevant": "false"}
    args[flag] = bad
    before = jobs.read_text()
    r = run_script(JUDGE, jobs, *[x for kv in args.items() for x in kv])
    assert r.returncode == 1, r.stdout + r.stderr
    assert says in r.stderr, r.stderr
    assert flag in r.stderr, r.stderr
    assert jobs.read_text() == before


# Every control character a JSON string may not carry raw, in one value. A vertical tab and a
# form feed have no escape of their own in JSON and are written as a \u escape; NUL is left out
# because a shell argument cannot carry one.
EVERY_CONTROL = "".join(chr(i) for i in range(1, 32))


def test_free_text_carrying_every_control_character_is_written_out_whole(tmp_path):
    """Free text is escaped, never refused: a reason legitimately holds a newline, and a judgment
    that cannot be recorded because of one is worse than one that reads oddly.

    `esc` handled `\\t`, `\\r` and `\\n` and nothing else until this round, so a single vertical tab
    in a value wrote a line no JSON parser would take. Measured then, on `--query-id` with one: 26
    lines written, 0 parseable, exit 0. All 31 go through here at once, and the reason has to come
    back out of the log exactly as it went in.
    """
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    row = first_surfaced(jobs)
    reason = "before" + EVERY_CONTROL + "after"
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="false",
                                      reasoning=reason))
    assert r.returncode == 0, r.stderr
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"]   # every line through json.loads
    assert len(ev) == 1
    assert ev[0]["reasoning"] == reason
    assert "\\u000b" in jobs.read_text()               # the \u fallback, not a raw byte


def test_a_dealbreaker_carrying_a_control_character_is_written_out_whole(tmp_path):
    """The list values reach `esc` through `jlist`, which is a second way into it."""
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="false",
                                      dealbreakers="on\vsite;pay\x01band"))
    assert r.returncode == 0, r.stderr
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"]
    assert ev[0]["dealbreakers_hit"] == ["on\vsite", "pay\x01band"]


ESC_COPIES_TODAY = 5      # a floor, not a count: see test_every_event_builder_escapes_a_value...
ESC_SCAN_DIRS = sorted((ROOT / "skills").glob("*/scripts"))


def _esc_bodies():
    """The text of every `esc` under every skill's `scripts/`, keyed by repo path and line, with the
    definition's own indentation taken off so copies at different depths compare equal.

    Every skill's script directory is scanned rather than the one that holds the copies today. The
    five are all in `job-search-run/scripts` now, but the next event builder the plan adds is
    `close-run.sh` under `job-search-runbook/scripts`, and a guard that looked only where the copies
    already are would still be green on the day a sixth one landed next door.
    """
    bodies = {}
    for path in sorted(p for d in ESC_SCAN_DIRS for p in d.glob("*")):
        if path.suffix not in (".sh", ".awk"):
            continue
        src = path.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(src):
            if line.lstrip().startswith("function esc("):
                indent = line[:len(line) - len(line.lstrip())]
                body = []
                for follow in src[i:]:
                    body.append(follow[len(indent):] if follow.startswith(indent) else follow)
                    if follow == indent + "}":
                        break
                bodies["%s:%d" % (path.relative_to(ROOT), i + 1)] = "\n".join(body)
    return bodies


def test_every_event_builder_escapes_a_value_the_same_way():
    """One function, copied. The copies disagreed twice: `record-judgment.awk` escaped a tab, a
    carriage return and a newline while the other four escaped none of the three, and any value that
    reached one of those four carrying one stopped the log being JSON.

    Comparing the text is what catches the third divergence before it ships. A copy that has to
    differ is a copy that should not be a copy.

    The count is a floor rather than a fixed number, so a matching copy added by a later task passes
    and a drifting one fails. It is there at all because a glob that found nothing would otherwise
    make this pass over an empty set.

    The directory list is asserted too, because narrowing it back to the one directory that holds
    the copies today would not move either of the other two assertions: measured with a drifted
    sixth copy written to `job-search-runbook/scripts`, the narrow scan found 5 copies, 1 distinct,
    and passed, while this one found 6, 2 distinct, and failed.
    """
    bodies = _esc_bodies()
    assert set(ESC_SCAN_DIRS) >= {RUN_SCRIPTS, RUNBOOK_SCRIPTS, SEARCH_SCRIPTS}, ESC_SCAN_DIRS
    assert len(bodies) >= ESC_COPIES_TODAY, sorted(bodies)
    assert len(set(bodies.values())) == 1, {k: v.splitlines()[0] for k, v in bodies.items()}
    assert "sprintf(\"\\\\u%04x\", i)" in next(iter(bodies.values()))


def test_a_judgment_lands_as_one_evaluated_event(tmp_path):
    """One invocation, one event. The caller writes no JSON: it hands over flags, and the script
    turns them into the `evaluated` event Task 5 counts a run from."""
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
    """The caller passes no title, company, location, URL or date. The script reads the surfaced
    event anyway to prove the posting belongs to this run, and takes all five off that line, so the
    digest can list a posting by title and company without reading the whole log."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true", match="strong"))
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    for key in ("title", "company_name", "location_display", "source_url", "posted_at"):
        assert ev[key] == row[key], key


def test_a_copied_title_with_an_escaped_quote_is_byte_exact(tmp_path):
    """The five copied values are spliced in as the raw JSON the surfaced event already holds.
    Reading one out and escaping it again turns `Manager \\"Finance\\" role` into a string whose
    own quotes are part of the text; reading it out and putting the quotes back turns the JSON
    null in `posted_at` into the four-character string "null". This catches both."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"surfaced","run_id":"%s","source":"ashby","source_id":"a",'
        '"source_url":"https:\\/\\/example.invalid\\/1","title":"Manager \\"Finance\\" role",'
        '"company_name":"Globex","location_display":"Remote","posted_at":null}\n' % RID)
    run_script(JUDGE, jobs, "--run-id", RID, "--source", "ashby", "--source-id", "a",
               "--detail-read", "false", "--relevant", "false", "--reasoning", "No.")
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    assert ev["title"] == 'Manager "Finance" role'
    assert ev["posted_at"] is None
    # The escaped slashes say the copy is byte-for-byte rather than merely equivalent. `\/` and `/`
    # decode to the same string, so a reader that unescaped each value and escaped it again would
    # pass every assertion above and still rewrite the URL. The raw line is what tells them apart.
    raw = [l for l in jobs.read_text().splitlines() if '"event":"evaluated"' in l][0]
    assert '"source_url":"https:\\/\\/example.invalid\\/1"' in raw
    assert ev["source_url"] == "https://example.invalid/1"


def test_the_dropped_fields_are_gone_on_purpose(tmp_path):
    """Three fields the hand-written event shape carried and this one does not. `first_seen` and
    `query_id` belong to the surfaced event, and `salary_display` is display text no count and no
    view reads off a judgment."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true", match="weak"))
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    for gone in ("first_seen", "salary_display", "query_id"):
        assert gone not in ev


def test_every_field_a_script_decides_on_comes_before_the_free_text(tmp_path):
    """The readers take a key's first occurrence, so reasoning holding the literal "status":
    must not be found before the real one.

    The assertions compare positions in the raw line, so moving any of the named fields after
    `reasoning` fails here (measured: moving the `status` field alone below `reasoning` fails this
    test and no other in the module; the same holds for `needs_human_check`).

    All six machine-read fields are listed, not the four the plan names. With `detail_read` and
    `ts` left out, moving either one below `reasoning` gave a fully green module — and Task 5
    derives a run's start and end from `ts`."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true", match="strong",
                                  reasoning='It says "status": "closed" halfway down.'))
    raw = [l for l in jobs.read_text().splitlines() if '"event":"evaluated"' in l][0]
    for key in ('"status":', '"needs_human_check":', '"match":', '"relevant":',
                '"detail_read":', '"ts":'):
        assert raw.index(key) < raw.index('"reasoning":'), key
    ev = json.loads(raw)
    assert ev["status"] == "new"


def test_free_text_with_quotes_backslashes_tabs_and_newlines_round_trips(tmp_path):
    """Nothing the judgment says is escaped by the caller, so every hostile character has to
    survive the script writing the JSON. The tab and the newline also say the value reached awk
    through the environment: `awk -v` cannot carry a literal newline."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                  match="strong", reasoning=HOSTILE,
                                  unknowns="equity;start date"))
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    assert ev["reasoning"] == HOSTILE
    assert ev["unknowns"] == ["equity", "start date"]


def test_the_optional_flags_reach_the_event(tmp_path):
    """The four flags no other case passes: `--needs-human-check` is written as a JSON boolean and
    defaults to false, `--dealbreakers` splits on the semicolon the script header names, and
    `--same-role-as` and `--posted-at-extracted` put a key on the event only when supplied. The
    second judgment is the control: it passes none of them."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"][:2]
    run_script(JUDGE, *judge_args(jobs, rows[0], detail_read="true", relevant="false",
                                  needs_human_check="true",
                                  dealbreakers="on-site five days;pay below the floor",
                                  same_role_as="ashby:abc123",
                                  posted_at_extracted="2026-07-30"))
    run_script(JUDGE, *judge_args(jobs, rows[1], detail_read="true", relevant="false"))
    supplied, control = [e for e in lines(jobs) if e["event"] == "evaluated"]
    assert supplied["needs_human_check"] is True
    assert supplied["dealbreakers_hit"] == ["on-site five days", "pay below the floor"]
    assert supplied["same_role_as"] == "ashby:abc123"
    assert supplied["posted_at_extracted"] == "2026-07-30"
    assert control["needs_human_check"] is False
    assert control["reasoning"] is None
    assert "same_role_as" not in control and "posted_at_extracted" not in control


def test_a_list_entry_is_trimmed_around_the_separator(tmp_path):
    """A caller writing the list the way it reads — `pay; then equity` — must not put a leading
    space into the digest, so each entry is trimmed and an entry that is only whitespace is
    dropped. Untrimmed, the second entry arrives as `" then equity"` with exit 0 and no warning.

    A dealbreaker that itself contains a semicolon still splits in two. That is why the script
    header says such a dealbreaker has to be reworded, and the second entry here shows what the
    caller gets if it is not."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="false",
                                      dealbreakers="pay below the floor; then equity ;  ;",
                                      unknowns="  start date  "))
    assert r.returncode == 0, r.stderr
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    assert ev["dealbreakers_hit"] == ["pay below the floor", "then equity"]
    assert ev["unknowns"] == ["start date"]


def test_a_posting_outside_the_brief_lands_with_relevant_false_and_no_band(tmp_path):
    """`relevant` is the field the digest filters on, and this is the only case that reads it in
    its false state. Every other case either judges the posting relevant or does not read the
    field, so writing `"relevant":true` into the event unconditionally passes all of them
    (measured before this case was written: with the value hardcoded, every test in this module
    still passed)."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="false",
                                      reasoning="Outside the brief."))
    assert r.returncode == 0, r.stderr
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    assert ev["relevant"] is False
    assert ev["detail_read"] is False
    assert ev["match"] is None


def test_an_awk_that_fails_keeps_the_judgment_out_of_the_log(tmp_path):
    """The script checks the awk's exit status as well as the file, because an awk that died
    partway through writing the line leaves part of an event behind. The shim supplies that part.

    Appending it is worse than appending nothing: the fragment ends without a newline, so the next
    event written to the log is joined onto it and two events are lost rather than one. Measured
    against the file check alone: exit 0, and `jobs.jsonl` ends with
    `…"source_id":"linkedin-0000","title":"Fin` that `json.loads` refuses.

    The whole file is compared rather than the line count, because a fragment with no newline
    lands on the end of the last line instead of adding one."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    before = jobs.read_text()
    half = ('{"event":"evaluated","run_id":%s,"source":"linkedin","source_id":%s,"title":"Fin'
            % (json.dumps(RID), json.dumps(row["source_id"])))
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                      match="strong"),
                   env=awk_shim(tmp_path, "record-judgment.awk", half))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "building the event failed" in r.stderr
    assert jobs.read_text() == before


def test_a_judgment_carries_the_timestamp_given_or_the_time_it_was_written(tmp_path):
    """Task 5 works out when a run started and ended from these timestamps, and nothing else here
    asserts the field: the retry case passes `--ts` twice but compares the two lines with the
    timestamp cut out, so it still passes with `ts` dropped from the event altogether.

    The second judgment reads the clock. Both bounds come from Python's own UTC clock around the
    call, so nothing here is a literal date, and the format is asserted as well as the value,
    because `date -u +%Y-%m-%dT%H:%M:%SZ` is what every other event in the log is stamped with."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"][:2]
    given = "2026-08-06T12:00:00Z"
    run_script(JUDGE, *judge_args(jobs, rows[0], detail_read="true", relevant="false", ts=given))
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    before = time.strftime(fmt, time.gmtime())
    r = run_script(JUDGE, *judge_args(jobs, rows[1], detail_read="true", relevant="false"))
    after = time.strftime(fmt, time.gmtime())
    assert r.returncode == 0, r.stderr
    stamped, clocked = [e["ts"] for e in lines(jobs) if e["event"] == "evaluated"]
    assert stamped == given
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", clocked), clocked
    assert before <= clocked <= after, (before, clocked, after)


@pytest.mark.parametrize("flag", ["detail_read", "relevant", "needs_human_check"])
def test_a_boolean_flag_that_is_not_true_or_false_is_refused(tmp_path, flag):
    """All three go onto the event unquoted, so a value that is not `true` or `false` writes a line
    no JSON parser can read. Measured with the `--detail-read` check removed: the script exits 0,
    says nothing, and appends a line carrying `"detail_read":yes` that `json.loads` refuses. The
    stderr is asserted whole so each case shows its own flag was the one named."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    kw = dict(detail_read="true", relevant="false")
    kw[flag] = "yes"
    r = run_script(JUDGE, *judge_args(jobs, row, **kw))
    assert r.returncode == 1
    assert r.stderr == "record-judgment: --%s must be true or false\n" % flag.replace("_", "-")
    assert [e for e in lines(jobs) if e["event"] == "evaluated"] == []


@pytest.mark.parametrize("drop", ["--run-id", "--source", "--source-id"])
def test_a_judgment_missing_a_flag_names_it_rather_than_the_posting(tmp_path, drop):
    """Each case asserts the whole stderr line, not only the exit code, because both paths exit 1.
    Measured with the `--run-id` guard removed: the empty value reaches the grep chain, matches
    nothing, and the caller is told `record-judgment: no surfaced posting for
    linkedin:linkedin-0000 in run` — which sends it to the run's search results when the fault is
    on the command line.

    The name differs from the queue script's case of the same shape on purpose: two test functions
    with one name in a module leaves only the second, and pytest reports no clash."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    flags = {"--run-id": RID, "--source": row["source"], "--source-id": row["source_id"]}
    del flags[drop]
    r = run_script(JUDGE, jobs, *[x for pair in flags.items() for x in pair],
                   "--detail-read", "true", "--relevant", "false")
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stderr == "record-judgment: missing %s\n" % drop
    assert [e for e in lines(jobs) if e["event"] == "evaluated"] == []


def test_recording_against_a_missing_log_names_the_path(tmp_path):
    """The whole stderr line, for the same reason the missing-flag cases assert it. Without the
    guard the path reaches the grep chain, which prints its own `grep: …: No such file or
    directory` and then the caller is told `no surfaced posting for ashby:a in run …`. Exit 1
    either way, and no log is created."""
    jobs = tmp_path / "nope.jsonl"
    r = run_script(JUDGE, jobs, "--run-id", RID, "--source", "ashby", "--source-id", "a",
                   "--detail-read", "true", "--relevant", "false")
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stderr == "record-judgment: no such file: %s\n" % jobs
    assert not jobs.exists()


def test_relevant_true_without_a_band_is_refused(tmp_path):
    """A relevant posting carries a band, because the digest groups by it. The stderr names the
    three values, so the caller does not have to open the script to find them."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true"))
    assert r.returncode == 1
    assert "strong|moderate|weak" in r.stderr
    assert [e for e in lines(jobs) if e["event"] == "evaluated"] == []


def test_relevant_false_carrying_a_band_is_refused(tmp_path):
    """The other half of the same rule. A posting outside the brief has no match band, so a band
    on it is a judgment the caller has half-changed and not finished changing."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="false",
                                      match="weak"))
    assert r.returncode == 1
    assert [e for e in lines(jobs) if e["event"] == "evaluated"] == []


def test_an_invented_band_is_refused(tmp_path):
    """Three bands and no fourth. A band the digest does not group by would put the posting in no
    section of the digest at all."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                      match="excellent"))
    assert r.returncode == 1
    assert [e for e in lines(jobs) if e["event"] == "evaluated"] == []


def test_a_judgment_about_a_posting_no_search_surfaced_is_refused(tmp_path):
    """The same rule the queue enforces, for the same reason: a judgment names a posting this run
    surfaced, or nothing later can resolve its id to a title, a company or a URL."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    r = run_script(JUDGE, jobs, "--run-id", RID, "--source", "linkedin",
                   "--source-id", "jp_INVENTED", "--detail-read", "true",
                   "--relevant", "true", "--match", "strong")
    assert r.returncode == 1
    assert "no surfaced posting" in r.stderr


def test_the_same_judgment_twice_is_reported_and_skipped(tmp_path):
    """A retry. The two invocations differ only in `--ts`, and the timestamp is not part of the
    verdict, so the second one writes nothing and exits 0. A second event would count the posting
    twice in every band total Task 5 reads off the log."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    base = dict(detail_read="true", relevant="true", match="strong", reasoning="Same.")
    run_script(JUDGE, *judge_args(jobs, row, ts="2026-08-05T00:00:00Z", **base))
    before = len(lines(jobs))
    r = run_script(JUDGE, *judge_args(jobs, row, ts="2026-08-05T09:30:30Z", **base))
    assert r.returncode == 0 and "already carries this verdict" in r.stderr
    assert len(lines(jobs)) == before


def test_a_different_judgment_for_the_same_posting_is_refused_with_both_lines(tmp_path):
    """Two verdicts for one posting is a conflict only the caller can settle, so the script writes
    neither and prints both. Without both lines the caller is told the verdicts differ and has to
    open the log to see how."""
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


@pytest.mark.skipif(not shutil.which("dash"), reason="dash is not installed here")
def test_recording_a_judgment_runs_under_dash(tmp_path):
    """`sh -n` and `dash -n` check syntax only, so the script is also run end to end under strict
    dash: it uses `${1:?}`, `${2?}`, `mktemp`, a trap, and a prefixed environment assignment in
    front of `awk`, and none of those is exercised by a syntax check."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                      match="moderate", reasoning=HOSTILE), shell="dash")
    assert r.returncode == 0, r.stderr
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    assert ev["reasoning"] == HOSTILE and ev["title"] == row["title"]


def _scrub_module():
    spec = importlib.util.spec_from_file_location(
        "fixture_scrub", ROOT / "tests" / "fixtures" / "scrub.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _every_object(node):
    """Every JSON object in the document, at any depth, including inside a string holding JSON.

    Walking beats indexing into a known shape: a search fixture keeps its fields under
    `data.results[]`, a get-posting fixture keeps the same fields directly under `data`, and the
    error fixture has none of them.

    The string branch is what makes this catch a class rather than one shape. A LinkedIn
    get-posting body puts the source page's whole schema.org JobPosting record inside
    `salary_display` as text, and `salary_display` and `location_display` are both kept as free
    text on purpose — so a walker that stopped at the string saw an exempt field holding an
    employer name, a title and a full description, and reported nothing. Descending in means the
    record is checked field by field wherever it is parked, in a field this guard checks or one it
    does not.
    """
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _every_object(value)
    elif isinstance(node, list):
        for value in node:
            yield from _every_object(value)
    elif isinstance(node, str) and node.lstrip()[:1] in ("{", "["):
        try:
            inner = json.loads(node)
        except ValueError:
            return
        yield from _every_object(inner)


def _decodes_to_the_scrubbed_cursor(value):
    try:
        padded = value + "=" * (-len(value) % 4)
        return json.loads(base64.urlsafe_b64decode(padded)) == {"scrubbed": True}
    except Exception:
        return False


def live_values(doc, scrub):
    """Every value in `doc` that `scrub.py` replaces but which does not look replaced.

    One entry per field, `(key, value)`. A key that is absent or null is fine — which rows carry a
    field is itself a parser input — but a key present with a value from outside the scrub's
    vocabulary is live text.

    `location_display` and a free-text `salary_display` are both absent from the field list below:
    `scrub.py` leaves them alone because they are real parser inputs. Their *contents* are still
    checked, by the shape rule after the loop — free text stays free text, and a JSON document
    parked in either one is caught.

    Two checks run over every object, and they fail differently on purpose. The field list matches
    on the name and knows what a scrubbed value of that field looks like. The shape rule matches on
    the value and ignores the name, because a schema.org JobPosting record is live text wherever it
    is parked, and only one of its own keys — `title` — is a name this guard would recognise.
    `description`, `name`, `sameAs`, `logo` and `datePosted` are not, so a record with a
    vocabulary title in an unlisted field passed both halves until the shape rule moved off the
    name.
    """
    looks_scrubbed = {
        "company_name": lambda v: v in scrub.COMPANIES,
        "title": lambda v: v in scrub.TITLES,
        "department_name": lambda v: v in scrub.DEPARTMENTS,
        "team_name": lambda v: v in scrub.TEAMS,
        "source_id": lambda v: bool(re.fullmatch(r"[a-z0-9_]+-\d{4}", str(v))),
        "id": lambda v: bool(re.fullmatch(r"jp_[0-9a-f]{12}", str(v))),
        "source_url": lambda v: str(v).startswith("https://example.invalid/"),
        "apply_url": lambda v: str(v).startswith("https://example.invalid/apply/"),
        "description_markdown": lambda v: isinstance(v, str) and scrub.BODY.startswith(v),
        "description_plain": lambda v: isinstance(v, str) and scrub.BODY.startswith(v),
        "keywords": lambda v: v == "scrubbed",
        "location": lambda v: v == "scrubbed",
        "next_cursor": lambda v: _decodes_to_the_scrubbed_cursor(v),
        # Microsecond precision is a live value and one more thing to match a real posting on.
        "posted_at": lambda v: not re.search(r"\.\d", str(v)),
        "published_at": lambda v: not re.search(r"\.\d", str(v)),
    }
    found = []
    for obj in _every_object(doc):
        for key, ok in looks_scrubbed.items():
            value = obj.get(key)
            if value is not None and not ok(value):
                found.append((key, value))
        # The shape rule: any field, any depth. A string that parses as a JSON document is a
        # record the source page embedded, not a value this API returns — the LinkedIn
        # get-posting body behind detail.linkedin.json carried 8,833 characters of one in
        # `salary_display`. `scrub.py` replaces every such string with SCRUBBED_JOB_LD, and is
        # asked here what counts as one, so the guard and the scrub cannot disagree.
        for key, value in obj.items():
            if (isinstance(value, str) and scrub.is_structured_json(value)
                    and value != scrub.SCRUBBED_JOB_LD):
                found.append((key, value))
    return found


def test_the_fixture_glob_finds_something_to_guard():
    """The two guards below are parametrized over a glob of the fixture directory. pytest reports
    an empty parameter list as a skip — `got empty parameter set for (path)` — and nothing in that
    line says the privacy guard stopped guarding. The hand-written list they replaced would have
    raised FileNotFoundError.

    The rest of the file does go red, but for its own reasons rather than for theirs. With
    `FIXTURES` on an empty directory the module gives 38 failed, 97 passed, 4 skipped. Thirty-seven
    of those failures are the tests that drive `record-api-response.sh` from a fixture, each missing
    a file it names as `FIXTURES / <name>`, and the thirty-eighth is this test. Neither guard is
    among them: both land in the 4 skipped, reported as `got empty parameter set for (path)`
    (measured 2026-08-06, `python3 -m pytest tests/test_mechanics_scripts.py -q` with FIXTURES
    pointed at an empty temp dir).

    So this is the only check that reports the guards themselves going quiet, and the only one left
    if those thirty-seven ever stop reading from `FIXTURES`. The first assertion covers the likelier
    accident, a directory renamed rather than emptied."""
    assert FIXTURES.is_dir(), "the fixture directory is gone: %s" % FIXTURES
    assert sorted(FIXTURES.glob("*.json")), "no fixtures to guard in %s" % FIXTURES


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.name)
def test_a_committed_fixture_carries_no_live_posting_text(path):
    """`.gitignore` gives the reason eval output is not committed — it "carries machine paths and
    live posting text" — and `tests/fixtures/` is not gitignored, so the same rule holds here by
    hand. This is what makes it hold: a fixture captured live and committed without `scrub.py`
    run over it fails.

    Every fixture in the directory is found by glob, so a file added by a later task is covered
    the moment it lands rather than when somebody remembers to list it.
    """
    found = live_values(json.loads(path.read_text(encoding="utf-8")), _scrub_module())
    assert found == [], "%s carries live values: %s" % (path.name, found[:5])


@pytest.mark.parametrize("key,doc", [
    # A LinkedIn source_id is a direct lookup key to a real posting.
    ("source_id", {"data": {"results": [{"source": "linkedin", "source_id": "4417545222"}]}}),
    ("id", {"data": {"results": [{"id": "4417545222"}]}}),
    ("source_url", {"data": {"results": [
        {"source_url": "https://www.linkedin.com/jobs/view/strategic-finance-at-x-4417545222"}]}}),
    ("company_name", {"data": {"results": [{"company_name": "A Real Employer, Inc."}]}}),
    ("team_name", {"data": {"results": [{"team_name": "Merchant Services"}]}}),
    ("published_at", {"data": {"results": [{"published_at": "2026-08-03T01:16:44.665000"}]}}),
    ("keywords", {"data": {"query": {"keywords": "strategic finance"}}}),
    ("location", {"data": {"query": {"location": "San Francisco Bay Area"}}}),
    ("next_cursor", {"data": {"pagination": {"next_cursor": "eyJmaWVsZHMiOm51bGwsImxhc3Rf"}}}),
    # A get-posting body keeps its fields directly under `data`, which is the shape Task 2 commits
    # and where the largest amount of live text sits.
    ("description_markdown", {"data": {"source": "ashby", "id": "jp_000000000000",
                                       "description_markdown": "About the role\n\nWe are hiring."}}),
    # A live get-posting body carries description_plain beside description_markdown. scrub.py does
    # not replace it yet, so this case is the tripwire that makes Task 2 add it rather than commit
    # a second copy of the same job text.
    ("description_plain", {"data": {"source": "ashby", "id": "jp_000000000000",
                                    "description_plain": "About the role\n\nWe are hiring."}}),
    ("apply_url", {"data": {"apply_url": "https://jobs.ashbyhq.com/OpenAI/x/application"}}),
    # A LinkedIn get-posting body puts the source page's whole schema.org JobPosting record in
    # `salary_display` — description, employer and title in one string, 8,833 characters in the
    # capture behind `detail.linkedin.json`. A free-text band in the same field is kept on purpose,
    # so this case is what holds the two apart.
    ("salary_display", {"data": {"salary_display": json.dumps(
        {"@context": "http://schema.org", "@type": "JobPosting",
         "title": "Strategic Finance, International",
         "hiringOrganization": {"@type": "Organization", "name": "OpenAI"}})}}),
    # The same record one JSON type over. A page embedding
    # `<script type="application/ld+json">[{…}]</script>` puts it in a one-element array, and a
    # check accepting only an object passes it straight through.
    ("salary_display", {"data": {"salary_display": json.dumps(
        [{"@type": "JobPosting", "title": "VP Finance, Payments",
          "hiringOrganization": {"@type": "Organization", "name": "A Real Employer Inc"}}])}}),
    # And parked in `location_display`, the other field kept as free text on purpose. There is no
    # `location_display` rule above and there should not be one — only descending into the string
    # reaches this, which is what makes the guard cover the class rather than the one field where
    # it first turned up.
    ("title", {"data": {"location_display": json.dumps(
        {"@type": "JobPosting", "title": "VP Finance, Payments",
         "hiringOrganization": {"@type": "Organization", "name": "A Real Employer Inc"}})}}),
])
def test_the_fixture_guard_catches_a_live_value(key, doc):
    """The guard is only worth having if it reaches the fields that carry the most live text, so
    each one is driven with a value taken from the shape the live API actually returns."""
    found = live_values(doc, _scrub_module())
    assert key in [k for k, _ in found], found


def _embedded_record(scrub):
    """A schema.org JobPosting record whose own `title` comes from the fixture vocabulary.

    That is what makes it the hard case. `title` is the only key of such a record that this guard
    knows by name, so a record whose title already looks scrubbed is invisible to every name-keyed
    check and can be caught only on its shape. Everything else in it is live: the employer, its
    LinkedIn company page, its logo, and a microsecond timestamp of the kind `posted_at` would have
    been caught on under its own name.
    """
    return json.dumps({
        "@context": "http://schema.org", "@type": "JobPosting",
        "title": scrub.TITLES[0],
        "datePosted": "2026-07-25T13:50:43.000Z",
        "description": "Live job text that must never be committed.",
        "hiringOrganization": {"@type": "Organization", "name": "A Real Employer Inc",
                               "sameAs": "https://www.linkedin.com/company/openai",
                               "logo": "https://media.licdn.com/dms/image/v2/xyz"}})


@pytest.mark.parametrize("place", [
    lambda rec: {"data": {"location_display": rec}},
    lambda rec: {"data": {"workplace_type": rec}},
    lambda rec: {"data": {"address_structured": {"raw_page": rec}}},
], ids=["location_display", "workplace_type", "nested"])
def test_an_embedded_record_is_caught_in_any_field_and_can_be_scrubbed(tmp_path, place):
    """The guard reaches the record wherever the API parks it, and the scrub can then fix it.

    Both halves have to hold. A guard that flags a value no scrub path replaces leaves whoever
    hits it with a fixture that is permanently red and nothing to do about it, so each placement
    is driven through `scrub.main` and checked again afterwards.

    `salary_display` was closed one round earlier by a rule keyed on that field name. These three
    placements are the ones that rule never reached.
    """
    scrub = _scrub_module()
    doc = place(_embedded_record(scrub))
    assert live_values(doc, scrub), "the guard does not see the record in this position"
    live = tmp_path / "raw.json"
    live.write_text(json.dumps(doc), encoding="utf-8")
    out = tmp_path / "clean.json"
    scrub.main(str(live), str(out))
    text = out.read_text(encoding="utf-8")
    assert "A Real Employer Inc" not in text
    assert "media.licdn.com" not in text
    assert live_values(json.loads(text), scrub) == []


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.name)
def test_scrubbing_a_committed_fixture_reproduces_it(tmp_path, path):
    """`scrub.py` is stable from its first pass, so re-running it over a committed fixture changes
    nothing. It seeds every replacement from the source and the row number, neither of which it
    replaces; seeding from `source_id`, which it does replace, made a second pass reseed every
    company and title and churn the fixtures for no reason.

    This is also what covers `id`, which the guard above can only pattern-check: a live `jp_` id
    and a scrubbed one are the same twelve hex characters, so only re-deriving it tells them apart.
    """
    out = tmp_path / path.name
    _scrub_module().main(str(path), str(out))
    assert out.read_text(encoding="utf-8") == path.read_text(encoding="utf-8")


@pytest.mark.parametrize("embedded", [
    # A page embedding one record, and a page embedding a list of them. Both forms turn up as
    # `<script type="application/ld+json">` on a job page, and both reach `salary_display` as text.
    {"@context": "http://schema.org", "@type": "JobPosting",
     "title": "Strategic Finance, International", "hiringOrganization": {"name": "OpenAI"}},
    [{"@type": "JobPosting", "title": "VP Finance, Payments",
      "hiringOrganization": {"name": "A Real Employer Inc"}}],
], ids=["one record", "a list of records"])
def test_the_scrub_clears_a_live_shaped_posting_body(tmp_path, embedded):
    """The test above starts from an already-scrubbed file, so a replacement that stopped happening
    still reproduces it and it stays green. This one starts from the live shape instead: a posting
    body carrying both description fields, and a `salary_display` holding the source page's own
    JobPosting record rather than a band. Deleting either replacement from `scrub.py` fails here and
    nowhere else (measured by removing each one and running this module)."""
    scrub = _scrub_module()
    live = tmp_path / "raw.json"
    live.write_text(json.dumps({"data": {
        "source": "linkedin", "source_id": "4417545222", "id": "jp_a319f60ebe3f",
        "source_url": "https://www.linkedin.com/jobs/view/strategic-finance-at-x-4417545222?p=1",
        "company_name": "A Real Employer, Inc.", "title": "Strategic Finance, International",
        "description_markdown": "About the role\n\nWe are hiring.",
        "description_plain": "About the role\n\nWe are hiring.",
        "apply_url": "https://jobs.ashbyhq.com/OpenAI/x/application",
        "published_at": "2026-08-03T01:16:44.665000",
        "salary_display": json.dumps(embedded),
    }}), encoding="utf-8")
    out = tmp_path / "clean.json"
    scrub.main(str(live), str(out))
    assert live_values(json.loads(out.read_text(encoding="utf-8")), scrub) == []


@pytest.mark.skipif(not shutil.which("dash"), reason="dash is not installed here")
def test_the_whole_path_runs_under_dash(tmp_path):
    """Run the dedup path — the two chained `-f` awk programs and the two-pass event build — under
    strict dash, not only under the host's `sh`."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    n = len(api_rows("search.ashby.json"))
    first = record_search(jobs, "search.ashby.json", "a", shell="dash")
    second = record_search(jobs, "search.ashby.json", "b", shell="dash")
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert len([e for e in lines(jobs) if e["event"] == "surfaced"]) == n
    calls = [e for e in lines(jobs) if e["event"] == "call"]
    assert [c["rows_new"] for c in calls] == [n, 0]


# ----------------------------------------------------------------------------- run-counts.sh

def counts(jobs, run_id=RID):
    """Run `run-counts.sh` and return its result and its key/value lines as a dict.

    The split takes the first `=` only, because `searches_never_succeeded_ids` carries a list whose
    entries hold no `=` but whose value must survive whatever it does hold.
    """
    r = run_script(COUNTS, jobs, run_id)
    return r, dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)


def judge_all(jobs, rows, **kw):
    """Record the same judgment for every row.

    Each call is asserted here rather than in the callers, for the reason `seeded_jobs` asserts its
    search: a judgment that failed leaves the counts short, and the test would then report a wrong
    count rather than the judgment that never landed.
    """
    for row in rows:
        r = run_script(JUDGE, *judge_args(jobs, row, **kw))
        assert r.returncode == 0, r.stderr


def test_a_run_killed_after_the_search_reports_everything_unreviewed(tmp_path):
    """A run that surfaced postings and judged none of them: every posting is unreviewed, and the
    numbers say so rather than reporting an empty run."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    n = len(api_rows("search.linkedin.json"))
    r, c = counts(jobs)
    assert r.returncode == 0, r.stderr
    assert c["postings_surfaced"] == str(n)
    assert c["postings_reviewed"] == "0"
    assert c["postings_unreviewed"] == str(n)


def test_the_bands_and_filtered_out_sum_to_reviewed(tmp_path):
    """The two sums the output contract holds to: the three bands plus filtered_out equal reviewed,
    and reviewed plus unreviewed equal surfaced."""
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
    """One `by_source_<name>` line per source that surfaced a posting, and nothing else."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    for name in ("search.linkedin.json", "search.ashby.json"):
        record_search(jobs, name)
    _, c = counts(jobs)
    per = {k: int(v) for k, v in c.items() if k.startswith("by_source_")}
    assert sum(per.values()) == int(c["postings_surfaced"])
    assert per == {"by_source_linkedin": len(api_rows("search.linkedin.json")),
                   "by_source_ashby": len(api_rows("search.ashby.json"))}
    # The order the sources first surfaced a posting, which is what `srcorder` fixes: built from an
    # unordered walk instead, these two lines swap under BSD awk (measured).
    assert list(per) == ["by_source_linkedin", "by_source_ashby"]


def test_rows_new_total_equals_surfaced(tmp_path):
    """Two queries reaching the same postings. The second search returns the same rows and appends
    none of them, so it adds nothing to either number."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    for qid in ("a", "b"):
        record_search(jobs, "search.linkedin.json", qid)
    _, c = counts(jobs)
    assert c["rows_new_total"] == c["postings_surfaced"] == str(len(api_rows("search.linkedin.json")))


def test_a_stored_posting_body_does_not_add_to_the_new_row_count(tmp_path):
    """`rows_new_total` counts the rows the searches appended, which is what keeps it equal to
    `postings_surfaced` — the output contract prints the two as the same number.

    A stored posting body writes a `call` event carrying `rows_new` 1: `record-api-response.sh:227`
    passes 1 as the new-row count for a detail read that stored something. Adding `rows_new` from
    every route would therefore put `rows_new_total` one above `postings_surfaced` for each posting
    read in full, on every run that read one.
    """
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    record_detail(jobs, "detail.ashby.json")
    _, c = counts(jobs)
    assert c["calls_detail_reads"] == "1"          # the detail read happened
    assert c["rows_new_total"] == c["postings_surfaced"]


def test_a_call_on_a_third_route_is_metered_as_other(tmp_path):
    """Every metered call is in the total, whatever route it was made against — `status` bills one
    and is neither a search nor a detail read (`agent-data-reference:51`). A route with no bucket of
    its own is counted rather than dropped, so the record cannot report fewer calls than the run
    made."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"call","run_id":"%s","route":"status","source":null,"query_id":null,'
        '"ok":true,"rows_returned":0,"rows_new":0}\n' % RID)
    _, c = counts(jobs)
    assert c["calls_other"] == "1"
    assert c["calls_searches"] == "0" and c["calls_detail_reads"] == "0"
    assert c["calls_total_metered"] == "1"


def test_one_posting_surfaced_twice_in_a_run_counts_once(tmp_path):
    """`postings_surfaced` counts postings, not surfaced events. Counting the second line would also
    put that posting into the reviewed or the unreviewed total twice, and the two would stop summing
    to surfaced for a reason no key in the output names."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    jobs.write_text(jobs.read_text() + json.dumps(first_surfaced(jobs)) + "\n")
    _, c = counts(jobs)
    assert c["postings_surfaced"] == str(len(api_rows("search.linkedin.json")))
    assert int(c["postings_reviewed"]) + int(c["postings_unreviewed"]) == int(c["postings_surfaced"])


def test_a_weak_judgment_lands_in_the_weak_band(tmp_path):
    """A digest reported a weak match with no weak row behind it, which is one of the wrong numbers
    this script exists to remove. A weak judgment is counted as weak and in no other band."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    judge_all(jobs, [first_surfaced(jobs)], detail_read="true", relevant="true", match="weak",
              reasoning="Adjacent to the brief, not in it.")
    _, c = counts(jobs)
    assert c["match_weak"] == "1"
    assert c["match_strong"] == "0" and c["match_moderate"] == "0" and c["filtered_out"] == "0"
    assert c["postings_reviewed"] == "1"


def test_metered_calls_are_counted_including_a_failed_one(tmp_path):
    """Every `call` event is metered, a failed one included, and each is filed under the route it
    was made against rather than the route its body looks like."""
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
    """How many postings this run has the full text of, which is not how many detail reads it
    paid for."""
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    record_detail(jobs, "detail.ashby.json")
    record_detail(jobs, "detail.ashby.json")       # a repeat: one more call, no more coverage
    _, c = counts(jobs)
    assert c["postings_detail_read"] == "1"
    assert c["calls_detail_reads"] == "2"


def test_a_search_that_failed_then_succeeded_is_not_a_lost_search(tmp_path):
    """A transient 503 that the retry cleared. The failed attempt is counted as a failed call, and
    the search still returned, so nothing about it degrades the run."""
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
    """Three attempts against one source and query, none of which returned. That is one search
    whose postings were never surfaced, and it is named so the digest can say which one."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("".join(
        '{"event":"call","run_id":"%s","route":"search-jobs","source":"ashby","query_id":"q2",'
        '"ok":false,"rows_returned":0,"rows_new":0,"retryable":true}\n' % RID for _ in range(3)))
    _, c = counts(jobs)
    assert c["searches_never_succeeded"] == "1"
    assert c["searches_never_succeeded_ids"] == "ashby:q2"


def test_the_writer_cannot_produce_two_searches_on_one_source_that_share_a_query_id(tmp_path):
    """A search call with no query id used to be groupable with every other query-id-less search on
    its source. One that returned marked the group answered, one whose attempts all failed stopped
    being counted, and the run closed healthy with a whole search never returned — measured at
    `searches_never_succeeded=0` on exactly this pair before the writer was guarded.

    `record-api-response.sh` refuses a search call with no query id now, so the log cannot hold that
    pair, and the same two searches written the sanctioned way name the one that never returned."""
    jobs = tmp_path / "jobs.jsonl"
    refused = run_script(RECORD_API, RID, jobs, FIXTURES / "search.zero.json",
                         "--route", "search-jobs", "--source", "linkedin")
    assert refused.returncode == 2, refused.stderr
    assert not jobs.exists()                       # no call event, so no group keyed on a null

    jobs.write_text("")
    ok = run_script(RECORD_API, RID, jobs, FIXTURES / "search.zero.json", "--route", "search-jobs",
                    "--source", "linkedin", "--query-id", "q1")
    assert ok.returncode == 0, ok.stderr
    for _ in range(3):                             # three attempts, none of which returned
        run_script(RECORD_API, RID, jobs, FIXTURES / "detail.error.json", "--route", "search-jobs",
                   "--source", "linkedin", "--query-id", "q2")
    _, c = counts(jobs)
    assert c["calls_searches"] == "4" and c["calls_failed"] == "3"
    assert c["searches_never_succeeded"] == "1"
    assert c["searches_never_succeeded_ids"] == "linkedin:q2"


def test_the_lost_searches_are_named_in_the_order_the_log_holds_them(tmp_path):
    """awk walks an array in no defined order. Built from one instead of from `grouporder`, this
    list comes out in a different order under each awk — measured on this log, BSD awk gave
    greenhouse, lever, ashby, linkedin and mawk gave ashby, lever, linkedin, greenhouse. A run
    record written on one machine and a digest written on another would then carry different
    lines for the same run."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("".join(
        '{"event":"call","run_id":"%s","route":"search-jobs","source":"%s","query_id":"%s",'
        '"ok":false,"rows_returned":0,"rows_new":0,"retryable":true}\n' % (RID, src, qid)
        for src, qid in [("ashby", "q1"), ("lever", "q2"), ("greenhouse", "q3"),
                         ("linkedin", "q4")]))
    _, c = counts(jobs)
    assert c["searches_never_succeeded"] == "4"
    assert c["searches_never_succeeded_ids"] == "ashby:q1,lever:q2,greenhouse:q3,linkedin:q4"


def test_a_later_runs_detail_event_is_not_this_runs_coverage(tmp_path):
    """`postings_detail_read` says how many of this run's postings this run has the full text of.
    A posting a later run read in full leaves that number where it was."""
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    row = first_surfaced(jobs)
    jobs.write_text(jobs.read_text() +
        '{"event":"detail","run_id":"2026-09-01T00-00-00Z","source":"%s","source_id":"%s",'
        '"description_markdown":"The full text.","ts":"2026-09-01T00:00:00Z"}\n'
        % (row["source"], row["source_id"]))
    _, c = counts(jobs)
    assert c["postings_detail_read"] == "0"


def test_a_failed_detail_read_is_not_a_lost_search(tmp_path):
    """A posting whose detail read failed gets judged from its summary row, so the run stays
    healthy. Only a search that never returned takes postings out of reach."""
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    run_script(RECORD_API, RID, jobs, FIXTURES / "detail.error.json", "--route", "get-posting")
    _, c = counts(jobs)
    assert c["calls_failed"] == "1"
    assert c["searches_never_succeeded"] == "0"


def test_a_relevant_row_with_no_band_is_reported_as_invalid(tmp_path):
    """A relevant posting carries a band. One without a band would be counted as reviewed and land
    in no band, so the bands would stop summing to reviewed with nothing saying why."""
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
    """The same postings surfaced by two runs in one log. Each run counts its own events.

    The call count is asserted alongside the posting count because the second run surfaced the same
    ids: with the run filter removed, its surfaced events land on keys this run already has and
    `postings_surfaced` does not move (measured — that mutation passes on the posting count alone).
    Its search call has no such key, so `calls_searches` is what the filter is visible in.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    other = jobs.read_text().replace(RID, "2026-01-01T00-00-00Z")
    jobs.write_text(jobs.read_text() + other)
    _, c = counts(jobs)
    assert c["postings_surfaced"] == str(len(api_rows("search.linkedin.json")))
    assert c["calls_searches"] == "1"


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


def test_an_awk_that_died_partway_is_not_reported_as_counts(tmp_path):
    """The counts go to stdout, so a caller cannot tell a complete key set from a partial one by
    reading it — an awk that died after printing four lines leaves four real-looking counts there.
    The exit status is what tells them apart, and it is awk's own status: with awk shimmed to print
    one count line and then fail, this must not exit 0."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    r = run_script(COUNTS, jobs, RID,
                   env=awk_shim(tmp_path, "run-counts.awk", "postings_surfaced=999"))
    assert r.returncode != 0, r.stdout
    assert "postings_surfaced=999" in r.stdout     # the count a caller would have used


def test_counts_for_a_log_that_is_not_there_exit_two_and_print_nothing(tmp_path):
    """A run whose log is missing is not a run that surfaced nothing. Printing zeros would let a
    record be written from a path typed wrong."""
    r, c = counts(tmp_path / "absent.jsonl")
    assert r.returncode == 2
    assert c == {}
    assert "no such file" in r.stderr


# ------------------------------------------------------------------- POSIX portability

def test_scripts_pass_posix_syntax_check():
    """Each script is POSIX `sh` (not bash-only): `sh -n` and strict `dash -n` both clean."""
    shells = ["sh"]
    if shutil.which("dash"):
        shells.append("dash")
    for script in ALL_SCRIPTS:
        assert script.exists(), "missing script: %s" % script
        for sh in shells:
            r = subprocess.run([sh, "-n", str(script)], capture_output=True, text=True)
            assert r.returncode == 0, "%s -n failed on %s:\n%s" % (sh, script.name, r.stderr)
