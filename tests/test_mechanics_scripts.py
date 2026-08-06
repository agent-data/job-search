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
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

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

ALL_SCRIPTS = [DEDUP, APPEND, SCHEDULE, DISCOVERY, VALIDATE]


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
    """The escape branch skips two characters, so the character after a backslash needs the same
    check — otherwise a raw newline reaches the value by riding behind one."""
    r, _ = scan('{"a":"one\\\ntwo","b":2}')
    assert r.returncode == 2, r.stdout
    assert "control character" in r.stderr, r.stderr


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
    """`"title"` here is a value with a comma after it, not a key with a colon, so the search goes
    on to the next occurrence. This is the one shape that exercises that retry: an escaped quote in
    free text is written `\\"title\\"` and never forms the bare `"title"` the search looks for."""
    assert field('{"a":"title","title":"Real Title"}', "title") == ('"Real Title"', "Real Title")
    line = '{"reasoning":"they call it \\"title\\" over there","title":"Real Title"}'
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
