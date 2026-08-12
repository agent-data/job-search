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
from types import SimpleNamespace

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
MATCHES = RUN_SCRIPTS / "run-matches.sh"
OPEN_RUN = RUNBOOK_SCRIPTS / "open-run.sh"
CLOSE_RUN = RUNBOOK_SCRIPTS / "close-run.sh"
CLEAR_RUN = RUNBOOK_SCRIPTS / "clear-run.sh"
POSTINGS = SEARCH_SCRIPTS / "posting-counts.sh"
RESOLVE_RUN = RUN_SCRIPTS / "resolve-run.sh"
FETCH_POSTING = RUN_SCRIPTS / "fetch-posting.sh"
CHECK_ARGS = RUN_SCRIPTS / "check-record-args.sh"
SEARCH_JOBS = RUN_SCRIPTS / "search-jobs.sh"
LISTING = "f9a6ec16-0bfd-44d8-b3ee-073776745ee7"

ALL_SCRIPTS = [DEDUP, APPEND, SCHEDULE, DISCOVERY, VALIDATE, RECORD_API, QUEUE, LIST_QUEUE,
               JUDGE, COUNTS, MATCHES, OPEN_RUN, CLOSE_RUN, CLEAR_RUN, POSTINGS,
               RESOLVE_RUN, FETCH_POSTING, CHECK_ARGS, SEARCH_JOBS]


# A contract-valid single-line `evaluated` event, in the shape
# skills/job-search-run/templates/jobs-event.example.json shows.
def evaluated(source, source_id, ts="2026-07-11T00:00:00Z", extra=""):
    return (
        '{"event":"evaluated","ts":"%s","source":"%s","source_id":"%s",'
        '"query_id":"q","title":"T","company_name":"C","location_display":"Remote",'
        '"salary_display":"","posted_at":"%s","source_url":"https://example/%s",'
        '"posting_id_at_seen":"jp_1","detail_read":true,"relevant":true,"match":"strong",'
        '"reasoning":"solid fit","dealbreakers_hit":[],"unknowns":[],'
        '"needs_human_check":false,"first_seen":"%s"%s}'
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


# ------------------------------------------------------------ the live agent-data harness

def _live_blocker():
    """Why the live tests cannot run on this machine, or None when they can.

    Four different states used to answer one bare `False`, and the skip line then read "agent-data
    is absent or unauthenticated" for every one of them. That is a false statement in two of the
    four: when `agent-data whoami` exits non-zero it has said nothing about a key, and when it
    prints something other than JSON there is no `api_key_set` to have read. Each state names
    itself here instead, because the skip line is the only thing a reader of a skipped run gets.
    """
    if not shutil.which("agent-data"):
        return "the agent-data CLI is not on PATH here"
    r = subprocess.run(["agent-data", "whoami"], capture_output=True, text=True)
    if r.returncode != 0:
        return "`agent-data whoami` exited %d: %s" % (
            r.returncode, (r.stderr or r.stdout).strip()[:200] or "it printed nothing")
    try:
        whoami = json.loads(r.stdout)
    except json.JSONDecodeError:
        return "`agent-data whoami` printed something other than JSON: %r" % r.stdout[:200]
    if whoami.get("api_key_set") is not True:
        return "`agent-data whoami` reports api_key_set=%r, so no key is configured here" % (
            whoami.get("api_key_set"),)
    return None


LIVE_BLOCKER = _live_blocker()
needs_api = pytest.mark.skipif(LIVE_BLOCKER is not None, reason=LIVE_BLOCKER or "")


def json_object_in(text):
    """The first complete JSON object in `text`, whatever precedes it.

    fetch-posting.sh prints record-api-response.sh's diagnostic line before an error body, and that
    line carries the API's own `message` interpolated into it (record-api-response.sh:233). Slicing
    from the first `{` to the last `}` starts inside the diagnostic as soon as a message holds a
    brace, and the test would then fail on a change that has nothing to do with what it checks.
    Each `{` is tried in turn instead, and the first one that decodes whole is the body.
    """
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                return decoder.raw_decode(text, i)[0]
            except json.JSONDecodeError:
                continue
    raise AssertionError("no JSON object in:\n%s" % text)


def open_run_in(ws):
    """Open a run in `ws`, empty its log, and return the run id resolve-run.sh reports.

    The run id comes from resolve-run.sh for the reason the `live_run` fixture gives: a glob over
    `runs/` repeats the run-id-shape filter that script applies at resolve-run.sh:62, and can hand
    back `runs/.started-` — the marker that names no run — as if it were a run id.

    It sits with the live harness rather than in one script's section because the record-judgment
    cases, the search-jobs cases and test_a_subagent_needs_only_the_posting_row all use it.
    """
    opened = subprocess.run(["sh", str(OPEN_RUN), str(ws)], capture_output=True, text=True)
    assert opened.returncode == 0, opened.stdout + opened.stderr
    (ws / "jobs.jsonl").write_text("", encoding="utf-8")
    resolved = subprocess.run(["sh", str(RESOLVE_RUN), "--workspace", str(ws)],
                              capture_output=True, text=True)
    assert resolved.returncode == 0, resolved.stderr
    return dict(l.split("=", 1) for l in resolved.stdout.splitlines() if "=" in l)["run_id"]


@pytest.fixture
def live_run(tmp_workspace):
    """A workspace with an open run and one live search already recorded.

    The search is real because record-api-response.sh refuses a detail event for a posting no
    search of this run surfaced, so a hand-written surfaced row would be testing against a log
    state the API never produced.

    The run id comes from resolve-run.sh, the script that owns finding it. A glob over `runs/`
    would repeat the run-id-shape filter that script applies at resolve-run.sh:62, and could hand
    back `runs/.started-` — the marker that names no run — as if it were a run id. `Path.glob`
    returns its names in no defined order, so which one came back would vary.

    This calls agent-data directly rather than through search-jobs.sh, so a break in that script
    fails its own cases and leaves the fetch-posting.sh cases below reporting what they are about.
    Task 7 runs the same chain through both wrappers.
    """
    opened = subprocess.run(["sh", str(OPEN_RUN), str(tmp_workspace)],
                            capture_output=True, text=True)
    assert opened.returncode == 0, opened.stdout + opened.stderr
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("", encoding="utf-8")

    resolved = subprocess.run(["sh", str(RESOLVE_RUN), "--workspace", str(tmp_workspace)],
                              capture_output=True, text=True)
    assert resolved.returncode == 0, resolved.stderr
    run_id = dict(l.split("=", 1) for l in resolved.stdout.splitlines() if "=" in l)["run_id"]

    resp = tmp_workspace / "search.json"
    with resp.open("w", encoding="utf-8") as out:
        r = subprocess.run(
            ["agent-data", "call", LISTING, "search-jobs", "--source", "linkedin",
             "--keywords", "strategic finance", "--limit", "5"],
            stdout=out, stderr=subprocess.PIPE, text=True)
    assert r.returncode == 0, r.stderr
    body = json.loads(resp.read_text(encoding="utf-8"))
    assert body["meta"]["request_id"].startswith("req_"), "no request_id — this did not reach the API"

    rec = subprocess.run(
        ["sh", str(RECORD_API), run_id, str(jobs), str(resp),
         "--route", "search-jobs", "--query-id", "strategic-finance", "--source", "linkedin"],
        capture_output=True, text=True)
    assert rec.returncode == 0, rec.stderr

    rows = [json.loads(l) for l in jobs.read_text(encoding="utf-8").splitlines() if l.strip()]
    surfaced = [x for x in rows if x["event"] == "surfaced"]
    assert surfaced, "the live search surfaced no rows — widen the keywords"
    return SimpleNamespace(ws=tmp_workspace, jobs=jobs, run_id=run_id, row=surfaced[0])


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


def test_dedup_reads_a_judgment_whose_event_key_carries_a_space(tmp_path):
    """dedup.sh's event-type filter tolerates the whitespace event-log-append.sh tolerates. A
    hand-written `"event": "evaluated"` is a judgment, and a posting whose judgment the filter
    misses is offered to the next run as new. Without this case, swapping the filter for
    `grep -F '"event":"evaluated"'` passes the whole suite.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text('{"event": "evaluated","run_id":"R","source": "ashby","source_id": "abc-123",'
                    '"relevant":true,"match":"strong"}\n')
    r = subprocess.run(["sh", str(DEDUP), str(jobs), "ashby"],
                       input="abc-123\nxyz-999\n", capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["xyz-999"], r.stdout


def test_a_source_whose_name_holds_a_regex_metacharacter_matches_only_that_source(tmp_path):
    """The source dedup.sh is given reaches the known-ids match as text, not as a pattern.

    Spliced into `grep -E` it was a pattern, and `a.c` matched a line whose source is `axc`. The
    known set for `a.c` then held 111, a posting `a.c` has never had judged, and the run never saw
    it. Measured 2026-08-08 on a log of one `evaluated` event for source `axc`:
    `grep -E '"source"[[:space:]]*:[[:space:]]*"a.c"'` prints that line and
    `grep -F '"source":"a.c"'` prints nothing.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(evaluated("axc", "111") + "\n")
    r = run_sh(DEDUP, [str(jobs), "a.c"], input_text="111\n222\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["111", "222"], r.stdout


def test_a_source_whose_name_holds_an_unbalanced_bracket_still_has_a_known_set(tmp_path):
    """`[x` opens a bracket expression that is never closed. `grep -E` prints
    `brackets ([ ]) not balanced`, exits 2 and matches nothing, so the known set came back empty
    and every posting this source had already judged was offered to the run again.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(evaluated("[x", "111") + "\n")
    r = run_sh(DEDUP, [str(jobs), "[x"], input_text="111\n222\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["222"], r.stdout


def test_a_judgment_whose_colons_carry_tabs_is_read_by_both_dedup_paths(tmp_path):
    """Both scripts close up `[[:space:]]` around the colon, not a literal space, and both comments
    say "spaces and tabs". This is what holds the tab half of that claim: with `[[:space:]]`
    narrowed to a literal space in both `sed`s, `python3 -m pytest tests/test_mechanics_scripts.py
    -q` gives 1 failed, and the one failure is this case.

    dedup.sh has to find the judgment, so the posting is not offered to the next run as new, and
    event-log-append.sh has to find it too, so a second copy is not appended.
    """
    jobs = tmp_path / "jobs.jsonl"
    ev = ('{"event":\t"evaluated","run_id":"R","source"\t:\t"ashby","source_id"\t: "abc-123",'
          '"relevant":true,"match":"strong"}')
    jobs.write_text(ev + "\n")
    d = run_sh(DEDUP, [str(jobs), "ashby"], input_text="abc-123\nxyz-999\n")
    assert d.returncode == 0, d.stderr
    assert d.stdout.split() == ["xyz-999"], d.stdout
    a = run_sh(APPEND, [str(jobs)], input_text=ev)
    assert a.returncode == 0, a.stderr
    assert len(lines(jobs)) == 1, jobs.read_text()


def test_a_value_ending_in_an_escaped_quote_before_a_colon_is_still_deduped(tmp_path):
    """The `sed` closes up a colon that has a quote on both sides, which is a rule about the
    characters on the line rather than about JSON, so it also fires inside a string value when an
    escaped quote sits to the left of the colon and the value's closing quote to the right. Measured
    2026-08-08: `"reasoning":"he said \\"source\\" : "` comes out as
    `"reasoning":"he said \\"source\\":"`.

    Nothing about the outcome changes, and this is the case that says so: the judgment is still
    found on such a line, and the log on disk still holds the reasoning as it was written, because
    the `sed` rewrites only the copy going through the pipe.
    """
    jobs = tmp_path / "jobs.jsonl"
    ev = ('{"event":"evaluated","run_id":"R","source":"ashby","source_id":"abc-123",'
          '"relevant":true,"match":"strong","reasoning":"he said \\"source\\" : "}')
    jobs.write_text(ev + "\n")
    r = run_sh(DEDUP, [str(jobs), "ashby"], input_text="abc-123\nxyz-999\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["xyz-999"], r.stdout
    assert lines(jobs)[0]["reasoning"] == 'he said "source" : ', jobs.read_text()


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


def test_a_hand_written_evaluated_event_with_spaces_is_still_deduped(tmp_path):
    """The event-type filter must tolerate the whitespace the rest of this script tolerates;
    a host writing an event by hand may put a space after the colon."""
    jobs = tmp_path / "jobs.jsonl"
    ev = ('{"event": "evaluated","run_id":"R","source": "ashby","source_id": "abc-123",'
          '"relevant":true,"match":"strong"}')
    for _ in range(2):
        r = subprocess.run(["sh", str(APPEND), str(jobs)], input=ev, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    assert len(lines(jobs)) == 1


def test_a_source_whose_name_holds_a_regex_metacharacter_is_matched_literally(tmp_path):
    """The source name comes off the event and reaches the idempotency check as text.

    Spliced into `grep -E` it was a pattern: for source `a.c` the check matched a line whose source
    is `axc`, read 111 off it, decided this posting already carried a judgment, and dropped the
    judgment for `a.c` with nothing on stderr and exit 0.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(evaluated("axc", "111") + "\n")
    r = run_sh(APPEND, [str(jobs)], input_text=evaluated("a.c", "111"))
    assert r.returncode == 0, r.stderr
    assert [(e["source"], e["source_id"]) for e in lines(jobs)] == [("axc", "111"), ("a.c", "111")]


def test_a_source_whose_name_holds_an_unbalanced_bracket_does_not_break_the_duplicate_check(tmp_path):
    """`[x` opens a bracket expression that is never closed, so `grep -E` prints
    `brackets ([ ]) not balanced`, exits 2 and matches nothing. The idempotency check then found no
    earlier judgment and appended a second one for a posting that already had one, at exit 0.
    """
    jobs = tmp_path / "jobs.jsonl"
    ev = evaluated("[x", "111")
    for _ in range(2):
        r = run_sh(APPEND, [str(jobs)], input_text=ev)
        assert r.returncode == 0, r.stderr
    assert len(lines(jobs)) == 1, jobs.read_text()


def test_a_source_id_that_looks_like_an_option_is_read_as_a_value(tmp_path):
    """The source_id reaches the last grep of the idempotency check as an argument of its own, so
    one starting with `-` was read as an option rather than as the text to match. Measured
    2026-08-08: `printf 'x\\n' | grep -qxF "-v"` exits 2 and prints grep's usage text, and the same
    command with `--` in front of the value exits 1. Through the script that meant the check found
    no earlier judgment, a second `evaluated` event for the same posting was appended, and the usage
    text reached the caller's stderr.

    Nothing reaches this today — no committed source_id starts with `-`, and this gives 0:
    `git ls-files -z | xargs -0 grep -rhoE '"source_id"[[:space:]]*:[[:space:]]*"[^"]*"'
    | cut -d'"' -f4 | sort -u | grep -c '^-'`. It is kept because it is the same defect as the two
    cases above: a value read as something other than the data it is.
    """
    jobs = tmp_path / "jobs.jsonl"
    ev = evaluated("ashby", "-v")
    for _ in range(2):
        r = run_sh(APPEND, [str(jobs)], input_text=ev)
        assert r.returncode == 0, r.stderr
        assert "usage" not in r.stderr.lower(), r.stderr
    assert len(lines(jobs)) == 1, jobs.read_text()


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
    """Two rows are read off the fixture by hand first, so the comparison below is against a scan
    that printed something. Measured 2026-08-06 with both `printf` statements in `json-scan.awk`
    replaced by bare `readstring()` / `readbare()` calls — the scanner still parses, and prints no
    rows: 156 of the 303 cases in this module failed and this one passed, because both sides of the
    comparison were the empty list."""
    pretty = (FIXTURES / "search.linkedin.json").read_text()
    compact = json.dumps(json.loads(pretty), separators=(",", ":"), ensure_ascii=False)
    assert ["data.query.source", '"linkedin"'] in scan(pretty)[1]
    assert ["data.results.0.source_id", '"linkedin-0000"'] in scan(pretty)[1]
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
        '{"source":"linkedin","match":"strong","n":25}',
        '{"source": "linkedin","match": "strong","n": 25}',
        '{"source" :"linkedin","match" :"strong","n" :25}',
        '{"source" : "linkedin" , "match" : "strong" , "n" : 25 }',
    ],
)
def test_whitespace_around_the_colon_does_not_hide_a_field(line):
    """`event-log-append.sh` accepts every one of these — its field checks all read
    `"key"[[:space:]]*:[[:space:]]*` — so an event written by hand arrives in these shapes. A
    `match` read as `" \\"strong\\""` equals none of the three band names `run-counts.awk`'s END
    block tests for — `grep -n 'b == "strong"' skills/job-search-run/scripts/run-counts.awk`:
    measured 2026-08-07 against a copy of `event-field.awk` outside the repository with
    the post-colon `_jskipws` call in `_jafter` dropped, a log carrying `"match" : "strong"` gave
    `match_strong=0` and the line `INVALID relevant-row-without-a-band=1`, exit 1, under
    /usr/bin/awk and mawk."""
    assert field(line, "source") == ('"linkedin"', "linkedin")
    assert field(line, "match") == ('"strong"', "strong")
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


def awk_shim(tmp_path, marker, spill="", status=2, stderr="awk: simulated failure"):
    """A PATH whose `awk` answers the one invocation carrying `marker` itself and passes the rest
    through.

    Returns the env to hand `run_script`. `spill` is printed to stdout before the exit, standing in
    for the lines an awk that died partway had already written — the whole point of checking the
    status is that those lines are there and must not be used.

    `status` is what that invocation exits with. It defaults to 2, which is what a real awk gives
    for a program it cannot run, and `close-run.sh`'s cases drive 0 and 1 as well: a reader that
    exits 1 means one thing when it printed every count and a finding on the last line and another
    when it printed half a count set, and a reader that exits 0 having left a key out reaches the
    record as a zero. Only the caller's own handling of each can tell them apart, so each status has
    to be producible here.
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
        "      echo '%s' >&2\n"
        "      exit %d ;;\n"
        "  esac\n"
        "done\n"
        "exec %s \"$@\"\n" % (marker, spill, stderr, status, shutil.which("awk")),
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

    Exit 2, and the call is recorded. The body came off a metered call whatever shape it arrived
    in — `agent-data-reference:19` says one metered call per attempt — and refusing to log it lost
    40 of the 74 get-posting calls one 2026-08-10 run made, whose digest reported 38 metered calls
    against a true 78. Only the checks that run before the body is scanned leave no event."""
    body = tmp_path / "body.json"
    body.write_text(json.dumps({"data": dict(row, description_markdown="A role."),
                                "meta": {"request_id": "req_1"}}))
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    before = [e for e in lines(jobs) if e["event"] == "call"]
    r = run_script(RECORD_API, RID, jobs, body, "--route", "get-posting")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "no usable %s —" % names in r.stderr, r.stderr
    assert [e for e in lines(jobs) if e["event"] == "detail"] == []
    after = [e for e in lines(jobs) if e["event"] == "call"]
    assert len(after) == len(before) + 1, after
    assert after[-1]["route"] == "get-posting"
    assert after[-1]["ok"] is False
    assert after[-1]["rows_returned"] == 0 and after[-1]["rows_new"] == 0


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
    object or an array never gets this far: the shape gate wants `data.source_id` as a scalar.

    Exit 2, and the call is recorded. The body came off a metered call whatever shape it arrived
    in — `agent-data-reference:19` says one metered call per attempt — and refusing to log it lost
    40 of the 74 get-posting calls one 2026-08-10 run made, whose digest reported 38 metered calls
    against a true 78. Only the checks that run before the body is scanned leave no event."""
    body = tmp_path / "body.json"
    body.write_text(json.dumps({"data": dict(row, description_markdown="A role."),
                                "meta": {"request_id": "req_1"}}))
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    before = [e for e in lines(jobs) if e["event"] == "call"]
    r = run_script(RECORD_API, RID, jobs, body, "--route", "get-posting")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "has a non-string %s —" % names in r.stderr, r.stderr
    assert [e for e in lines(jobs) if e["event"] == "detail"] == []
    after = [e for e in lines(jobs) if e["event"] == "call"]
    assert len(after) == len(before) + 1, after
    assert after[-1]["route"] == "get-posting"
    assert after[-1]["ok"] is False
    assert after[-1]["rows_returned"] == 0 and after[-1]["rows_new"] == 0


def test_a_posting_body_missing_data_source_id_entirely_still_records_its_call(tmp_path):
    """The shape gate, and the path a `--fields` list that dropped `source_id` lands on. It had no
    test at all, and 40 of the 74 metered get-posting calls of the 2026-08-10 run went unrecorded
    across these reject paths: HTTP 200 with valid bodies, trimmed by a field list that left out
    `source`, `source_id`, or both.

    The event carries the request id off `meta`, because `req` is read at
    `record-api-response.sh:238`, before the route branch. That is what lets an operator match a
    refused call against the service's own record."""
    body = tmp_path / "trimmed.json"
    body.write_text(json.dumps({"data": {"id": "jp_22d0d871db24", "title": "Head of FP&A",
                                         "company_name": "Acme",
                                         "description_markdown": "A role."},
                                "meta": {"request_id": "req_1"}}))
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    before = [e for e in lines(jobs) if e["event"] == "call"]
    r = run_script(RECORD_API, RID, jobs, body, "--route", "get-posting", "--source", "ashby")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "carries no data.source_id" in r.stderr, r.stderr
    after = [e for e in lines(jobs) if e["event"] == "call"]
    assert len(after) == len(before) + 1, after
    ev = after[-1]
    assert ev["route"] == "get-posting" and ev["ok"] is False
    assert ev["source"] == "ashby"
    assert ev["rows_returned"] == 0 and ev["rows_new"] == 0
    assert ev["request_id"] == "req_1"
    assert [e for e in lines(jobs) if e["event"] == "detail"] == []


def test_a_search_body_recorded_as_a_detail_read_keeps_the_route_it_was_given(tmp_path):
    """A search body arriving with --route get-posting carries no --query-id, because
    `record-api-response.sh:130-136` requires one only for a search. Filing it as a search would
    open the group `<source>:null` that nothing can ever mark answered — an invented lost search,
    which is the outcome correcting the route at the search gate exists to avoid. So the call is
    filed as the detail read the caller said it was, and `calls_total_metered` — the number the
    digest prints on its usage line — is right either way."""
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "search.linkedin.json",
                   "--route", "get-posting", "--source", "linkedin")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "carries no data.source_id" in r.stderr, r.stderr
    ev = [e for e in lines(jobs) if e["event"] == "call"][-1]
    assert ev["route"] == "get-posting" and ev["ok"] is False
    _, c = counts(jobs)
    assert c["calls_detail_reads"] == "1"
    assert c["calls_total_metered"] == "2"
    assert c["searches_never_succeeded"] == "0"


def test_a_refused_detail_read_reaches_the_counts_a_digest_prints(tmp_path):
    """The defect was only visible in the digest. The 2026-08-10 run made 74 metered get-posting
    calls, wrote 34 `call` events with route get-posting into `jobs.jsonl`, and printed
    `Agent-data usage: 38 metered calls this run` against a true 78. The script-level assertions
    above do not catch that on their own: the number a run reports is what `run-counts.sh` prints,
    and it counts events."""
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    trimmed = tmp_path / "trimmed.json"
    trimmed.write_text(json.dumps({"data": {"id": "jp_22d0d871db24", "title": "Head of FP&A"},
                                   "meta": {"request_id": "req_1"}}))
    refused = run_script(RECORD_API, RID, jobs, trimmed, "--route", "get-posting",
                         "--source", "ashby")
    assert refused.returncode == 2, refused.stderr
    ok = record_detail(jobs, "detail.ashby.json")
    assert ok.returncode == 0, ok.stderr
    _, c = counts(jobs)
    assert c["calls_detail_reads"] == "2"          # the refused read and the one that stored
    assert c["calls_searches"] == "1"              # the search `seeded_jobs` ran
    assert c["calls_total_metered"] == "3"
    assert c["calls_failed"] == "1"


def test_a_missing_response_file_records_nothing(tmp_path):
    """Where the exit-2 contract now draws its line: a body that was scanned records its call, and
    the checks that run before the scan do not. Nothing proves a call was made when the file naming
    the response is not there, and `jobs.jsonl` is not created at all — which is what
    `test_the_writer_cannot_produce_two_searches_on_one_source_that_share_a_query_id` relies on for
    the missing-query-id refusal.

    This passes before the change as well as after. It is here so the next edit to the reject paths
    cannot quietly widen them into the argument checks."""
    jobs = tmp_path / "jobs.jsonl"
    r = run_script(RECORD_API, RID, jobs, tmp_path / "nope.json", "--route", "get-posting")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "no such file" in r.stderr, r.stderr
    assert not jobs.exists()


@pytest.mark.parametrize("shell", ["sh", "dash"])
def test_a_posting_body_recorded_as_a_search_is_filed_as_the_detail_read_it_was(tmp_path, shell):
    """The search branch's shape gate. The call behind such a body was made and billed on
    get-posting, so the event carries that route rather than the one the caller passed. An event
    carrying search-jobs would open a source:query_id group in `run-counts.awk`, a group with no
    ok:true member counts as a search that never returned, and `close-run.sh` turns that into
    run_health=degraded — a lost search invented out of a mislabelled recording.

    The identification is positive rather than a guess: the body has passed the error gate and
    carries `data.source_id` at two segments, which no search body does. Measured with
    `json-scan.awk` — 1 such path in detail.ashby.json, 0 in search.zero.json and 0 in
    happy/search-jobs.ashby.json."""
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    before = [e for e in lines(jobs) if e["event"] == "call"]
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "detail.ashby.json",
                   "--route", "search-jobs", "--query-id", "q9", "--source", "ashby", shell=shell)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "carries neither data.query nor data.results" in r.stderr, r.stderr
    after = [e for e in lines(jobs) if e["event"] == "call"]
    assert len(after) == len(before) + 1, after
    assert after[-1]["route"] == "get-posting"
    assert after[-1]["ok"] is False
    _, c = counts(jobs)
    assert c["calls_detail_reads"] == "1"
    assert c["calls_searches"] == "1"              # the search `seeded_jobs` ran, and only that
    assert c["calls_total_metered"] == "2"
    assert c["searches_never_succeeded"] == "0"    # no group opened on q9


def test_a_body_carrying_neither_data_query_nor_data_results_nor_data_source_id_keeps_its_route(tmp_path):
    """The correction above is scoped to a body carrying data.source_id at two segments. A body
    carrying neither data.query nor data.results nor data.source_id is filed under the route the
    caller passed, because neither of the gate's two patterns matches any path in it — this one
    scans to data.nothing and meta.request_id.

    That leaves the group `ashby:q9` unanswered, which is counted as a search that never returned.
    It is the right reading of what happened: a search call was recorded, and no search body ever
    arrived for it."""
    body = tmp_path / "odd.json"
    body.write_text(json.dumps({"data": {"nothing": "useful"}, "meta": {"request_id": "req_1"}}))
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    r = run_script(RECORD_API, RID, jobs, body, "--route", "search-jobs", "--query-id", "q9",
                   "--source", "ashby")
    assert r.returncode == 2, r.stdout + r.stderr
    ev = [e for e in lines(jobs) if e["event"] == "call"][-1]
    assert ev["route"] == "search-jobs" and ev["ok"] is False
    # A refused body brought no rows in. Only a search adds rows_new to rows_new_total
    # (`run-counts.awk:41`, inside the `route == "search-jobs"` block), and this event kept that
    # route, so a non-zero value here would push rows_new_total above postings_surfaced and trip the
    # `surfaced-does-not-match-rows-new` check at `validate-workspace.sh:490`.
    assert ev["rows_new"] == 0
    _, c = counts(jobs)
    assert c["searches_never_succeeded"] == "1"
    assert c["searches_never_succeeded_ids"] == "ashby:q9"


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


def detail_line(run_id, source, source_id):
    """The `detail` event a stored posting leaves in the log, as one line ready to append.

    `record-api-response.sh` builds the real one off the response body and puts twelve keys on it.
    The six left out here — `employment_type`, `apply_url`, `is_listed`, `is_remote`,
    `workplace_type` and `staleness_status` — are read by nothing that reads this event.

    The separators are not a style choice. `record-judgment.sh` finds this event with `grep -F` on
    `"run_id":"…"`, with no space after the colon, so a line built by `json.dumps` with its default
    separators matches none of the chain and the script reports no detail event for a posting whose
    event is right there.
    """
    return json.dumps({"event": "detail", "run_id": run_id, "source": source,
                       "source_id": source_id, "description_markdown": "The full text.",
                       "ts": "2026-08-05T16:48:00Z"}, separators=(",", ":")) + "\n"


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


ESC_COPIES_TODAY = 6      # a floor, not a count: see test_every_event_builder_escapes_a_value...
ESC_SCAN_DIRS = sorted((ROOT / "skills").glob("*/scripts"))

# How many copies each file carries today, and the floor for each. A whole-set floor cannot catch a
# deletion once the set grows past it — with a sixth copy landed and one of the five removed, 5 >= 5
# passes — so each file is held to its own number as well.
ESC_COPIES_BY_FILE = {
    "skills/job-search-run/scripts/queue-detail-read.sh": 1,
    "skills/job-search-run/scripts/record-api-response.sh": 3,
    "skills/job-search-run/scripts/record-judgment.awk": 1,
    "skills/job-search-runbook/scripts/close-run.sh": 1,
}


def _esc_bodies():
    """The text of every `esc` under every skill's `scripts/`, keyed by repo path and line, with the
    definition's own indentation taken off so copies at different depths compare equal.

    Every skill's script directory is scanned rather than the ones that hold the copies today. Five
    were in `job-search-run/scripts` when this was written and `close-run.sh` added a sixth under
    `job-search-runbook/scripts`; a guard that looked only where the copies already were would have
    been green on the day that one landed next door.
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

    The counts are floors rather than fixed numbers, so a matching copy added by a later task passes
    and a drifting one fails. They are there at all because a glob that found nothing would
    otherwise make this pass over an empty set.

    A whole-set floor on its own stops catching a deletion as soon as another copy makes up the
    number, which is why each file is also held to the count it carries. Measured on 2026-08-06 with
    `close-run.sh`'s copy deleted and a matching copy added to `dedup-surfaced.awk`, so six are
    still found: with only the whole-set floor this passed, and with the per-file floors it fails on
    `close-run.sh`.

    The directory list is asserted too, because narrowing it back to the one directory that held
    the copies before this task would not move any of the other assertions: measured with a drifted
    sixth copy written to `job-search-runbook/scripts`, the narrow scan found 5 copies, 1 distinct,
    and passed, while this one found 6, 2 distinct, and failed.
    """
    bodies = _esc_bodies()
    assert set(ESC_SCAN_DIRS) >= {RUN_SCRIPTS, RUNBOOK_SCRIPTS, SEARCH_SCRIPTS}, ESC_SCAN_DIRS
    assert len(bodies) >= ESC_COPIES_TODAY, sorted(bodies)
    per_file = {}
    for key in bodies:
        per_file[key.rsplit(":", 1)[0]] = per_file.get(key.rsplit(":", 1)[0], 0) + 1
    for path, least in ESC_COPIES_BY_FILE.items():
        assert per_file.get(path, 0) >= least, (path, per_file)
    assert len(set(bodies.values())) == 1, {k: v.splitlines()[0] for k, v in bodies.items()}
    assert "sprintf(\"\\\\u%04x\", i)" in next(iter(bodies.values()))


def test_a_judgment_lands_as_one_evaluated_event(tmp_path):
    """One invocation, one event. The caller writes no JSON: it hands over flags, and the script
    turns them into the `evaluated` event Task 5 counts a run from."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true",
                                      match="strong", reasoning="Clears every must-have."))
    assert r.returncode == 0, r.stderr
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"]
    assert len(ev) == 1
    assert ev[0]["match"] == "strong" and ev[0]["relevant"] is True
    assert ev[0]["dealbreakers_hit"] == [] and ev[0]["unknowns"] == []
    assert ev[0]["needs_human_check"] is False


def test_the_display_fields_are_copied_off_the_surfaced_event(tmp_path):
    """The caller passes no title, company, location, URL or date. The script reads the surfaced
    event anyway to prove the posting belongs to this run, and takes all five off that line, so the
    digest can list a posting by title and company without reading the whole log."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true", match="strong"))
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
    run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true", match="weak"))
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    for gone in ("first_seen", "salary_display", "query_id"):
        assert gone not in ev


def test_every_field_a_script_decides_on_comes_before_the_free_text(tmp_path):
    """The readers take a key's first occurrence, so reasoning holding the literal "match":
    must not be found before the real one.

    The assertions compare positions in the raw line, so moving any of the named fields after
    `reasoning` fails here. Measured 2026-08-07 on a copy of the repository outside it: with the
    `match` line of `record-judgment.awk` moved below the `reasoning` line, `python3 -m pytest
    tests/test_mechanics_scripts.py -q` gives 1 failed, 448 passed, and the one failure is this
    test; moving `needs_human_check` there instead gives the same.

    All five machine-read fields the event carries are listed. The plan named four, `status` among
    them, and that field is gone. `detail_read` and `ts` are the two added: with them left out,
    moving either one below `reasoning` gave a fully green module — and Task 5 derives a run's
    start and end from `ts`."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true", match="strong",
                                  reasoning='It pastes a config rule holding "match": "any".'))
    raw = [l for l in jobs.read_text().splitlines() if '"event":"evaluated"' in l][0]
    for key in ('"needs_human_check":', '"match":', '"relevant":', '"detail_read":', '"ts":'):
        assert raw.index(key) < raw.index('"reasoning":'), key
    ev = json.loads(raw)
    assert ev["match"] == "strong"


def test_free_text_with_quotes_backslashes_tabs_and_newlines_round_trips(tmp_path):
    """Nothing the judgment says is escaped by the caller, so every hostile character has to
    survive the script writing the JSON. The tab and the newline also say the value reached awk
    through the environment: `awk -v` cannot carry a literal newline."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true",
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
    run_script(JUDGE, *judge_args(jobs, rows[0], detail_read="false", relevant="false",
                                  needs_human_check="true",
                                  dealbreakers="on-site five days;pay below the floor",
                                  same_role_as="ashby:abc123",
                                  posted_at_extracted="2026-07-30"))
    run_script(JUDGE, *judge_args(jobs, rows[1], detail_read="false", relevant="false"))
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
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="false",
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
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true",
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
    run_script(JUDGE, *judge_args(jobs, rows[0], detail_read="false", relevant="false", ts=given))
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    before = time.strftime(fmt, time.gmtime())
    r = run_script(JUDGE, *judge_args(jobs, rows[1], detail_read="false", relevant="false"))
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


@pytest.mark.parametrize("drop", ["--source", "--source-id"])
def test_a_judgment_missing_a_flag_names_it_rather_than_the_posting(tmp_path, drop):
    """Each case asserts the whole stderr line, not only the exit code, because both paths exit 1.
    Measured 2026-08-12 with both guards removed: the empty value reaches the grep chain, matches
    nothing, and the caller is told `record-judgment: no surfaced posting for :linkedin-0000 in run
    2026-08-05T16-47-00Z` with `--source` dropped, and `no surfaced posting for linkedin: in run
    2026-08-05T16-47-00Z` with `--source-id` dropped — which sends it to the run's search results
    when the fault is on the command line.

    `--run-id` was a third case here until it became optional. Left off, it comes from
    resolve-run.sh, and `test_record_judgment_resolves_the_log_and_the_run_from_disk` is the case
    that covers it.

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
    assert r.stderr == "record-judgment: no such log: %s\n" % jobs
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


def test_a_read_claimed_on_a_posting_with_no_detail_event_is_refused_without_an_api_key(tmp_path):
    """The detail-read guard, driven off a fixture log — the state CI runs in.

    Every live case covering this guard is `needs_api`-gated and CI holds no key. Measured
    2026-08-12 with the whole guard deleted: `python3 -m pytest -q -m "not live"` gives 4 failed,
    1143 passed, and the four are this case and the three wrong-scope cases below.

    The second call is what makes this case self-contained: it is the one that goes red against a
    guard that refuses every claim rather than only an unbacked one. Measured 2026-08-12 with the
    `if [ "$detail_read" = true ]` condition removed and the grep and `die` left unconditional: this
    case fails at that second call, carrying the `--detail-read true` message having passed `false`.
    That mutation takes 56 cases down across the two test files, because it makes every judgment
    need a `detail` event, so this case is not the only thing holding the condition.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    claimed = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                            match="strong", reasoning="Reads well."))
    assert claimed.returncode == 1, claimed.stdout + claimed.stderr
    assert "no detail event for %s:%s" % (row["source"], row["source_id"]) in claimed.stderr
    assert [e for e in lines(jobs) if e["event"] == "evaluated"] == []

    judged_from_the_row = run_script(JUDGE, *judge_args(jobs, row, detail_read="false",
                                                        relevant="false", reasoning="Wrong city."))
    assert judged_from_the_row.returncode == 0, judged_from_the_row.stderr


# A `detail` event that differs from the judgment in exactly one of the three fields the lookup is
# scoped by. Each case is the only thing holding its own grep: measured 2026-08-12 by dropping one
# grep at a time from the detail lookup in `record-judgment.sh`, each case goes red on its own grep
# and on neither of the others, and the rest of the module stays green either way.
WRONG_SCOPE = {
    "another run":     ("run_id",    "2026-09-01T00-00-00Z"),
    "another source":  ("source",    "ashby"),
    "another posting": ("source_id", "linkedin-0024"),
}


@pytest.mark.parametrize("case", sorted(WRONG_SCOPE), ids=lambda c: c.replace(" ", "-"))
def test_a_detail_event_naming_something_else_does_not_back_a_read_claim(tmp_path, case):
    """A posting read in another run, a posting read under another source, and a different posting
    read in this one. None of the three is a read of the posting being judged, so none may let the
    claim through.

    `run-counts.awk` counts `postings_detail_read` from `detail` events keyed by source and
    source_id and skips any event carrying another run's id, so a claim let through by a
    wrong-scope event is exactly the divergence this guard exists to stop: the judgment says the
    posting was read and the count says it was not. Task 8 reads that gap.

    The refusal reads the same in all three cases, because what the caller has to do about it is
    the same: read the posting it is judging.
    """
    field, wrong = WRONG_SCOPE[case]
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    scope = {"run_id": RID, "source": row["source"], "source_id": row["source_id"]}
    assert scope[field] != wrong, (field, wrong)
    scope[field] = wrong
    jobs.write_text(jobs.read_text() + detail_line(**scope))

    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                      match="strong", reasoning="Reads well."))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "no detail event for %s:%s in run %s" % (row["source"], row["source_id"], RID) \
        in r.stderr, r.stderr
    assert [e for e in lines(jobs) if e["event"] == "evaluated"] == []


def test_a_detail_event_for_this_posting_and_run_backs_the_claim(tmp_path):
    """The control for the three cases above. They would all pass against a guard that refused
    every claim, and this is the call that fails then: one `detail` event, scoped to this posting
    and this run, and the judgment is recorded.

    The event is written by hand rather than recorded through `record-api-response.sh`, because the
    only committed get-posting body names `linkedin-0000`; that is the posting judged here, so the
    fixture would work, and `detail_line` is used anyway so the three cases above and this one
    differ in the one field under test and in nothing else.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    jobs.write_text(jobs.read_text() + detail_line(RID, row["source"], row["source_id"]))

    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="true", relevant="true",
                                      match="strong", reasoning="Reads well."))
    assert r.returncode == 0, r.stdout + r.stderr
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"]
    assert len(ev) == 1 and ev[0]["detail_read"] is True


def test_the_same_judgment_twice_is_reported_and_skipped(tmp_path):
    """A retry. The two invocations differ only in `--ts`, and the timestamp is not part of the
    verdict, so the second one writes nothing and exits 0. A second event would count the posting
    twice in every band total Task 5 reads off the log."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    base = dict(detail_read="false", relevant="true", match="strong", reasoning="Same.")
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
    run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true",
                                  match="strong", reasoning="First."))
    before = len(lines(jobs))
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true",
                                      match="weak", reasoning="Changed my mind."))
    assert r.returncode == 1
    assert "recorded:" in r.stderr and "offered:" in r.stderr
    assert len(lines(jobs)) == before


def test_a_judgment_written_with_spaces_after_its_colons_still_blocks_a_second_one(tmp_path):
    """event-log-append.sh accepts a judgment written by hand with a space after any colon, so such
    a line is in the log by design. The already-judged lookup reads its fields with jval rather than
    grepping for their quoted text, which a space defeats.

    Measured on 2026-08-06 before find-judgment.awk existed: with the recorded judgment written this
    way, the conflicting one was accepted — exit 0, a second evaluated event appended, and
    `run-matches.sh` then reported the later verdict. The same workspace with that judgment written
    compact exited 1 and wrote nothing, so whitespace alone decided whether a conflict was refused.
    """
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    row = first_surfaced(jobs)
    prior = ('{"event": "evaluated","run_id": "%s","source": "%s","source_id": "%s",'
             '"relevant":true,"match":"strong","ts":"2026-08-05T00:00:00Z"}'
             % (RID, row["source"], row["source_id"]))
    a = run_sh(APPEND, [str(jobs)], input_text=prior)
    assert a.returncode == 0, a.stderr
    before = len(lines(jobs))
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true",
                                      match="weak", reasoning="Changed my mind."))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "recorded:" in r.stderr and "offered:" in r.stderr, r.stderr
    assert len(lines(jobs)) == before, jobs.read_text()


def test_a_judgment_from_an_earlier_run_blocks_a_contradictory_one_in_this_run(tmp_path):
    """The already-judged lookup is not scoped to a run, so a verdict an earlier run recorded stops
    this run recording a second one for the same posting.

    Measured 2026-08-08 with the lookup still scoped to a run: this call exited 0 and left two
    `evaluated` lines for one posting, and `run-matches.sh` then reported the later verdict.

    The run the refusal names is the one on the recorded judgment, which is the entry the caller has
    to go and read. Naming the calling run instead sends them to a log entry that is not there.
    """
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    row = first_surfaced(jobs)
    earlier = "2026-01-01T00-00-00Z"
    prior = ('{"event":"evaluated","run_id":"%s","source":"%s","source_id":"%s",'
             '"detail_read":true,"relevant":true,"match":"strong","ts":"2026-01-01T00:00:00Z"}'
             % (earlier, row["source"], row["source_id"]))
    a = run_sh(APPEND, [str(jobs)], input_text=prior)
    assert a.returncode == 0, a.stderr
    before = jobs.read_text()

    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="false",
                                      reasoning="Changed my mind."))
    assert r.returncode == 1, r.stdout + r.stderr
    said = r.stderr.splitlines()[0]
    assert earlier in said, said
    assert RID not in said, said
    assert jobs.read_text() == before
    assert len([e for e in lines(jobs) if e["event"] == "evaluated"]) == 1


def test_a_prior_judgment_that_names_no_run_is_refused_without_naming_one(tmp_path):
    """`event-log-append.sh` requires a `source_id`, and a `source` on an `evaluated` event; it
    requires no `run_id`, so a judgment written by hand can carry none. The refusal reads the run
    off the recorded judgment, so here there is nothing to read, and the message says that rather
    than printing an empty run id or the calling run's.
    """
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    row = first_surfaced(jobs)
    prior = ('{"event":"evaluated","source":"%s","source_id":"%s","detail_read":true,'
             '"relevant":true,"match":"strong","ts":"2026-01-01T00:00:00Z"}'
             % (row["source"], row["source_id"]))
    a = run_sh(APPEND, [str(jobs)], input_text=prior)
    assert a.returncode == 0, a.stderr
    before = jobs.read_text()

    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="false",
                                      reasoning="Changed my mind."))
    assert r.returncode == 1, r.stdout + r.stderr
    said = r.stderr.splitlines()[0]
    assert "names no run" in said, said
    assert RID not in said, said
    assert jobs.read_text() == before


def test_the_refusal_does_not_claim_two_verdicts_differ_when_they_are_the_same(tmp_path):
    """The lookup above became whitespace-tolerant; the comparison under it did not. It is a byte
    compare against the line this call would write, and the `sed` that drops the timestamp keys on
    the compact `,"ts":"`, so a judgment written by hand is refused whatever it says.

    Refusing is the safe answer and stays. What the script must not do is name a cause it has not
    established: here the recorded verdict and the offered one are the same `relevant` and the same
    `match`, and the message used to read `already has a DIFFERENT verdict`. The two lines are
    printed and the caller compares them.

    The prior is built by rewriting the event this script itself wrote, so the two differ in nothing
    but their separators — asserted below, since a hand-typed prior could differ in a field too and
    the point of the case would be gone.
    """
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    row = first_surfaced(jobs)
    verdict = dict(detail_read="false", relevant="true", match="strong", reasoning="Solid fit.",
                   ts="2026-08-05T00:00:00Z")
    assert run_script(JUDGE, *judge_args(jobs, row, **verdict)).returncode == 0

    kept = jobs.read_text().splitlines()
    compact = [l for l in kept if json.loads(l)["event"] == "evaluated"][0]
    spaced = json.dumps(json.loads(compact), separators=(",", ": "), ensure_ascii=False)
    assert json.loads(spaced) == json.loads(compact) and spaced != compact
    jobs.write_text("\n".join([l for l in kept if l != compact] + [spaced]) + "\n")
    before = jobs.read_text()

    r = run_script(JUDGE, *judge_args(jobs, row, **verdict))
    assert r.returncode == 1, r.stdout + r.stderr
    assert jobs.read_text() == before

    said, rec, off = r.stderr.splitlines()
    assert "different" not in said.lower(), said
    assert "not the line this call would write" in said, said
    recorded = json.loads(rec.split("recorded: ", 1)[1])
    offered = json.loads(off.split("offered:  ", 1)[1])
    assert (recorded["relevant"], recorded["match"]) == (offered["relevant"], offered["match"])


def test_an_awk_that_fails_reading_the_recorded_judgments_writes_no_second_verdict(tmp_path):
    """That lookup prints nothing for a posting no one has judged yet, and an awk that died before
    printing prints nothing either, so the output alone cannot tell the two apart. With only the
    output checked, the conflict below it is skipped and a second verdict for a posting that already
    has one lands in the log. The status is checked for the same reason the builder's is."""
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true",
                                  match="strong", reasoning="First."))
    before = jobs.read_text()
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true",
                                      match="weak", reasoning="Changed my mind."),
                   env=awk_shim(tmp_path, "find-judgment.awk"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "reading the judgments already recorded failed" in r.stderr, r.stderr
    assert jobs.read_text() == before


def test_concurrent_judgments_all_land_as_valid_json(tmp_path):
    """Readers run in parallel where the host has subagents; appends must not interleave."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    procs = [subprocess.Popen(
        ["sh", str(JUDGE), str(jobs), "--run-id", RID, "--source", row["source"],
         "--source-id", row["source_id"], "--detail-read", "false", "--relevant", "false",
         "--reasoning", "Outside the brief."],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for row in rows]
    for p in procs:
        p.wait()
    parsed = lines(jobs)   # raises on any interleaved or truncated line
    assert len([e for e in parsed if e["event"] == "evaluated"]) == len(rows)


@pytest.mark.skipif(not shutil.which("dash"), reason="dash is not installed here")
def test_recording_a_judgment_runs_under_dash(tmp_path):
    """`sh -n` and `dash -n` check syntax only, so the script is also run end to end under strict
    dash: it uses `${1-}`, `${2?}`, `mktemp`, a trap, and a prefixed environment assignment in
    front of `awk`, and none of those is exercised by a syntax check. The log path and the run id
    are both passed here, so this case never reaches the resolve-run.sh branch; the case below
    drives that branch under dash."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    r = run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true",
                                      match="moderate", reasoning=HOSTILE), shell="dash")
    assert r.returncode == 0, r.stderr
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"][0]
    assert ev["reasoning"] == HOSTILE and ev["title"] == row["title"]


@pytest.mark.skipif(not shutil.which("dash"), reason="dash is not installed here")
def test_resolving_the_log_and_the_run_runs_under_dash(tmp_path):
    """The branch the case above never reaches, under strict dash: `case ${1-}` with no operand at
    all, and `${ws_flag:+--workspace "$ws_flag"}`, which has to add two arguments or none.

    The directory name holds a space, so a broken expansion splits it and resolve-run.sh answers
    with its usage line instead of naming the directory. Measured 2026-08-12 under dash with the
    inner quotes removed: `usage: resolve-run.sh [--workspace W]`, exit 2 — the same status the
    shipped script gives here, so the message is the only thing that separates the two.

    This spends nothing: the workspace holds no open run, so the script exits before it reads a
    posting. resolve-run.sh checks that the workspace directory is there and then looks for a marker
    in the `runs/` directory inside it, so an empty `runs/` is all this workspace needs.
    """
    ws = tmp_path / "a work space"
    (ws / "runs").mkdir(parents=True)
    r = run_script(JUDGE, "--workspace", ws, "--source", "linkedin", "--source-id", "42",
                   "--detail-read", "false", "--relevant", "false", shell="dash")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "resolve-run.sh: no run is open in %s" % ws in r.stderr, r.stderr


@pytest.mark.live
@needs_api
def test_record_judgment_resolves_the_log_and_the_run_from_disk(live_run):
    """The call a subagent makes: a verdict, and nothing about where the run keeps its files. On the
    2026-08-11 opencode run, 15 of 36 recording calls supplied no log path and none supplied a run
    id, because no subagent had been given either.

    Measured before this change, with the same arguments: `record-judgment: unknown option
    <the workspace path>`, exit 1, because `--workspace` was taken as the log path and the path
    after it then reached the flag loop.
    """
    out = subprocess.run(
        ["sh", str(JUDGE), "--workspace", str(live_run.ws),
         "--source", live_run.row["source"], "--source-id", live_run.row["source_id"],
         "--detail-read", "false", "--relevant", "false", "--reasoning", "Wrong city."],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    ev = [json.loads(l) for l in live_run.jobs.read_text(encoding="utf-8").splitlines()
          if l.strip()]
    judged = [l for l in ev if l["event"] == "evaluated"]
    assert len(judged) == 1
    assert judged[0]["run_id"] == live_run.run_id


@pytest.mark.live
@needs_api
def test_record_judgment_still_takes_the_log_and_run_id_explicitly(live_run):
    out = subprocess.run(
        ["sh", str(JUDGE), str(live_run.jobs), "--run-id", live_run.run_id,
         "--source", live_run.row["source"], "--source-id", live_run.row["source_id"],
         "--detail-read", "false", "--relevant", "false", "--reasoning", "Wrong city."],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


@pytest.mark.live
@needs_api
def test_record_judgment_refuses_a_posting_read_claim_with_no_detail_event(live_run):
    """The row is real and surfaced by a real search; nothing read the posting, so the claim is
    the only thing wrong with the call."""
    out = subprocess.run(
        ["sh", str(JUDGE), "--workspace", str(live_run.ws),
         "--source", live_run.row["source"], "--source-id", live_run.row["source_id"],
         "--detail-read", "true", "--relevant", "true", "--match", "strong",
         "--reasoning", "Reads well."],
        capture_output=True, text=True)
    assert out.returncode == 1
    assert "no detail event" in out.stderr
    assert "%s:%s" % (live_run.row["source"], live_run.row["source_id"]) in out.stderr
    assert "evaluated" not in live_run.jobs.read_text(encoding="utf-8")


@pytest.mark.live
@needs_api
def test_record_judgment_accepts_a_posting_read_claim_after_a_real_read(live_run):
    """The same call as the case above, with one real read in front of it. fetch-posting.sh stores
    the posting's text, and that is the event the claim is checked against."""
    fetched = subprocess.run(
        ["sh", str(FETCH_POSTING), "--workspace", str(live_run.ws),
         "--posting-id", live_run.row["posting_id_at_seen"],
         "--source-url", live_run.row["source_url"],
         "--source", live_run.row["source"]],
        capture_output=True, text=True)
    assert fetched.returncode == 0, fetched.stderr

    out = subprocess.run(
        ["sh", str(JUDGE), "--workspace", str(live_run.ws),
         "--source", live_run.row["source"], "--source-id", live_run.row["source_id"],
         "--detail-read", "true", "--relevant", "true", "--match", "strong",
         "--reasoning", "Reads well."],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    ev = [json.loads(l) for l in live_run.jobs.read_text(encoding="utf-8").splitlines()
          if l.strip()]
    assert [l for l in ev if l["event"] == "evaluated"][0]["detail_read"] is True


@pytest.mark.live
@needs_api
def test_record_judgment_still_takes_detail_read_false_with_no_detail_event(live_run):
    """The normal case: a posting judged from the summary row a search surfaced, with nothing read.
    The check must only reach a call that claims a read."""
    out = subprocess.run(
        ["sh", str(JUDGE), "--workspace", str(live_run.ws),
         "--source", live_run.row["source"], "--source-id", live_run.row["source_id"],
         "--detail-read", "false", "--relevant", "false", "--reasoning", "Wrong city."],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def test_record_judgment_says_so_when_nothing_identifies_the_run(tmp_workspace):
    """No run is open and no run id was given, so this exits before reading any posting.

    The workspace holds no jobs.jsonl on purpose: the script exits at the resolve step, above the
    check that the log is there, so a log file would never be opened.
    """
    out = subprocess.run(
        ["sh", str(JUDGE), "--workspace", str(tmp_workspace),
         "--source", "linkedin", "--source-id", "42",
         "--detail-read", "false", "--relevant", "false"],
        capture_output=True, text=True)
    assert out.returncode == 2
    assert "no run is open" in out.stderr


def _surfaced_row(run_id):
    return ('{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"77",'
            '"title":"Analyst","company_name":"Acme"}\n' % run_id)


def test_an_explicit_run_id_wins_over_the_open_run(tmp_workspace):
    """Replaying an older run: another run is open, and `--run-id` names the run this judgment
    belongs to. The log path is left off, so resolve-run.sh supplies that and only that.

    Leaving the log off works here because a run is open for resolve-run.sh to answer from. With
    none open the same call exits 2 instead, and the replay has to pass the log as well; the
    script's header carries both halves and the measurement behind them.

    Measured 2026-08-12 with `[ -n "$run_id" ] ||` dropped from the resolve block, so the open run
    always overwrote the caller's: exit 1, `record-judgment: no surfaced posting for linkedin:77 in
    run <the id open-run.sh had just written>` rather than the one on the command line, and no
    evaluated event in the log.
    """
    open_run_in(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text(_surfaced_row(RID), encoding="utf-8")

    r = run_script(JUDGE, "--workspace", tmp_workspace, "--run-id", RID,
                   "--source", "linkedin", "--source-id", "77",
                   "--detail-read", "false", "--relevant", "false")
    assert r.returncode == 0, r.stdout + r.stderr
    ev = [e for e in lines(jobs) if e["event"] == "evaluated"]
    assert len(ev) == 1
    assert ev[0]["run_id"] == RID


def test_an_explicit_log_path_wins_over_the_workspace_log(tmp_path, tmp_workspace):
    """The other half. The log is given and the run id is left off, so resolve-run.sh supplies the
    run id alone. The log sits outside the workspace, so a resolve block that overwrote it would
    read the workspace's own jobs.jsonl instead, and both files are checked afterwards to say which
    one the judgment landed in.

    Measured 2026-08-12 with `[ -n "$jobs" ] ||` dropped: exit 1, `record-judgment: no surfaced
    posting for linkedin:77 in run <the open run>`, and neither file gained an evaluated event.
    """
    run_id = open_run_in(tmp_workspace)      # which also leaves the workspace log empty
    inside = tmp_workspace / "jobs.jsonl"
    outside = tmp_path / "elsewhere.jsonl"
    outside.write_text(_surfaced_row(run_id), encoding="utf-8")

    r = run_script(JUDGE, outside, "--workspace", tmp_workspace,
                   "--source", "linkedin", "--source-id", "77",
                   "--detail-read", "false", "--relevant", "false")
    assert r.returncode == 0, r.stdout + r.stderr
    ev = [e for e in lines(outside) if e["event"] == "evaluated"]
    assert len(ev) == 1
    assert ev[0]["run_id"] == run_id
    assert inside.read_text(encoding="utf-8") == ""


def test_an_empty_run_id_is_refused_rather_than_read_as_one_left_off(tmp_workspace):
    """`--run-id ''` is a caller whose variable did not expand, not a caller that left the flag off,
    and the two now get different answers.

    A run is open and the log holds a posting that run surfaced, which is the state where the
    accident is quietest. Measured 2026-08-12 before this check: the judgment was recorded under the
    open run at exit 0, `record-judgment: recorded linkedin:77 for run <the open run>`, with nothing
    said about the run id on the command line having been dropped. The whole stderr line is
    asserted, because the two refusals this script now has for an empty value differ only in wording.
    """
    run_id = open_run_in(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text(_surfaced_row(run_id), encoding="utf-8")

    r = run_script(JUDGE, "--workspace", tmp_workspace, "--run-id", "",
                   "--source", "linkedin", "--source-id", "77",
                   "--detail-read", "false", "--relevant", "false")
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stderr == ("record-judgment: --run-id was given an empty value; "
                        "leave it off to take the run that is open\n")
    assert [e for e in lines(jobs) if e["event"] == "evaluated"] == []


def test_an_empty_first_argument_is_refused_rather_than_read_as_a_flag(tmp_workspace):
    """The operand pattern used to be `''|--*`, so an empty first argument matched the flag arm, was
    not shifted off, and reached the flag loop. The caller was then told `record-judgment: unknown
    option ` with nothing after the words — measured 2026-08-12 at exit 1, a message naming no
    argument at all.

    No run is open here, so a call that got past this refusal would exit 2 at the resolve step
    rather than exit 1: the status alone separates the two, and the message says which argument was
    empty.
    """
    r = run_script(JUDGE, "", "--workspace", tmp_workspace,
                   "--source", "linkedin", "--source-id", "77",
                   "--detail-read", "false", "--relevant", "false")
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stderr == ("record-judgment: the first argument is an empty log path; "
                        "leave it off instead\n")


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
    live posting text" — and no ignore rule matches this fixture directory, so the same rule holds
    here by hand: `git check-ignore --no-index -v tests/fixtures/api-responses/*.json` prints
    nothing and exits 1. The one ignore file under `tests/fixtures/` is `seed-workspace/.gitignore`,
    the deny-all a job-search workspace starts with, and it applies only inside that directory.
    This is what makes the rule hold: a fixture captured live and committed without `scrub.py` run
    over it fails.

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
    and reviewed plus unreviewed equal surfaced.

    The last assertion is a third property: `postings_detail_read` is counted from `detail` events
    and not from what a judgment claims. rows[0]'s judgment is written by hand, carrying
    `"detail_read":true` with no `detail` event anywhere in the log — the state
    `record-judgment.sh` now refuses, and the state every log written before that check landed can
    hold. Counting the claim instead would report one posting read where none was, which is the
    22-against-13 divergence that check was added for.

    Measured 2026-08-12 with `run-counts.awk` setting `hasdetail[k]` when an `evaluated` event
    carries `"detail_read":true`: this test fails at the last assertion, and
    `test_run_counts_reports_judgments_claiming_a_posting_read` fails with it because that case
    carries a hand-written claim of its own — 2 failed, 591 passed over the module. Measured with
    rows[0] judged through `record-judgment.sh` at `--detail-read false` instead, so this log holds
    no claim at all: the same mutation leaves this test green and turns only that other case red —
    1 failed, 592 passed.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    a, b = 2, 7                                    # slice points, not row counts
    # `evaluated` carries "detail_read":true, "relevant":true and "match":"strong"; the run id goes
    # on the end because run-counts.awk skips every line naming another run.
    jobs.write_text(jobs.read_text() + evaluated(rows[0]["source"], rows[0]["source_id"],
                                                 extra=',"run_id":"%s"' % RID) + "\n")
    judge_all(jobs, rows[1:a], detail_read="false", relevant="true", match="strong",
              reasoning="Fits.")
    judge_all(jobs, rows[a:b], detail_read="false", relevant="true", match="moderate",
              reasoning="Partly fits.")
    judge_all(jobs, rows[b:], detail_read="false", relevant="false", reasoning="Outside the brief.")
    _, c = counts(jobs)
    reviewed = int(c["postings_reviewed"])
    assert (int(c["match_strong"]) + int(c["match_moderate"]) + int(c["match_weak"])
            + int(c["filtered_out"])) == reviewed
    assert reviewed + int(c["postings_unreviewed"]) == int(c["postings_surfaced"])
    assert int(c["match_strong"]) == a             # rows[0] by hand, rows[1:a] through the script
    assert int(c["match_moderate"]) == b - a
    assert int(c["match_weak"]) == 0
    assert int(c["filtered_out"]) == len(rows) - b
    # One judgment claims a read and the log holds no `detail` event, so the count is 0.
    assert c["postings_detail_read"] == "0"


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

    A stored posting body writes a `call` event carrying `rows_new` 1: `record-api-response.sh:354`
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
    judge_all(jobs, [first_surfaced(jobs)], detail_read="false", relevant="true", match="weak",
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


def test_run_counts_reports_judgments_claiming_a_posting_read(tmp_path):
    """`judgments_claiming_detail_read` counts what the judgments say about having read a posting;
    `postings_detail_read` counts the `detail` events. Two postings are judged as read here and one
    of them was stored, so the run's numbers report 2 claims against 1 stored posting rather than
    reporting the 1 on its own.

    The second judgment is written straight to the log because `record-judgment.sh` refuses to write
    it: `--detail-read true` with no `detail` event behind it is what its check rejects. A log
    written before that check existed can hold any number of them, and so can a log written by
    something other than these scripts. Measured on the 2026-08-11 opencode run: 22 judgments
    carried `detail_read: true` and the log held 13 detail events.
    """
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    stored, unstored = rows[0], rows[1]
    jobs.write_text(jobs.read_text() + detail_line(RID, stored["source"], stored["source_id"]))
    judge_all(jobs, [stored], detail_read="true", relevant="true", match="strong",
              reasoning="Fits.")
    # `evaluated` carries "detail_read":true; the run id goes on the end because run-counts.awk
    # skips every line naming another run.
    jobs.write_text(jobs.read_text()
                    + evaluated(unstored["source"], unstored["source_id"],
                                extra=',"run_id":"%s"' % RID) + "\n")
    _, c = counts(jobs)
    assert c["postings_detail_read"] == "1"
    assert c["judgments_claiming_detail_read"] == "2"


def test_a_re_judgment_without_the_claim_clears_it(tmp_path):
    """The last judgment this run recorded for a posting decides the claim, the way it already
    decides `relevant`, the band and `same_role_as`. A posting judged as read and then judged again
    without the claim is not counted.

    `postings_detail_read` stays at 1 across both judgments: the stored posting is still in the log,
    and no judgment can take a `detail` event out of that count or put one into it.

    The second judgment is written straight to the log because `record-judgment.sh` refuses a second
    judgment for a posting this run already judged.
    """
    jobs = seeded_jobs(tmp_path, "search.ashby.json")
    row = first_surfaced(jobs)
    jobs.write_text(jobs.read_text() + detail_line(RID, row["source"], row["source_id"]))
    judge_all(jobs, [row], detail_read="true", relevant="true", match="strong", reasoning="Fits.")
    _, first = counts(jobs)
    assert first["judgments_claiming_detail_read"] == "1"
    jobs.write_text(jobs.read_text() +
        '{"event":"evaluated","run_id":"%s","source":"%s","source_id":"%s",'
        '"detail_read":false,"relevant":true,"match":"weak"}\n'
        % (RID, row["source"], row["source_id"]))
    _, c = counts(jobs)
    assert c["judgments_claiming_detail_read"] == "0"
    assert c["postings_detail_read"] == "1"


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


# ------------------------------------------------ one opening posted in more than one city
#
# `search.linkedin.json` holds two rows for one Northwind Labs opening, `Director, FP&A` in Palo
# Alto, CA and the same title and company in San Francisco, CA:
#
#   python3 -c 'import json,collections;
#     f="tests/fixtures/api-responses/search.linkedin.json";
#     d=json.loads(open(f).read())["data"]["results"];
#     print([(r["source_id"], r["location_display"]) for r in d
#            if (r["company_name"], r["title"]) == ("Northwind Labs", "Director, FP&A")])'
#
# prints the two ids and the two cities. That pair is what `dedup.sh --near` groups — one company,
# one title once the location parenthetical is stripped and both are lowercased — and what
# `--same-role-as` was added to record. The cases below reach the pair through `seed_two_cities`,
# which asserts the company, the title and the two cities off the log rather than trusting the
# fixture to keep its rows in one order.


def seed_two_cities(tmp_path, alias=None):
    """A log in which one opening was read in one city and named again in the other.

    Returns the log, the row that was read, and the row that names it. The second judgment carries
    `--detail-read false` and the first one's verdict, which is what `job-search-run/SKILL.md` says
    to record for a posting `dedup.sh --near` left out. `alias` replaces what that judgment names,
    for the cases where the value resolves to no row.

    The `detail` event is written here because the first judgment says the posting was read, and
    `record-judgment.sh` refuses that claim when the log holds no such event. It carries the four
    fields that check matches on — `event`, `run_id`, `source` and `source_id` — plus a body and a
    timestamp. `record-api-response.sh` builds the real one off the response body and puts twelve
    keys on it; the six left out here are read by neither the check nor the cases below, and no
    committed response body names this posting anyway: the fixtures hold one for `linkedin-0000`.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    read = next(r for r in rows if r["source_id"] == "linkedin-0002")
    other = next(r for r in rows if r["source_id"] == "linkedin-0023")
    assert read["company_name"] == other["company_name"], (read, other)
    assert read["title"] == other["title"], (read, other)
    assert read["location_display"] != other["location_display"], read["location_display"]
    if alias is None:
        alias = "%s:%s" % (read["source"], read["source_id"])
    jobs.write_text(jobs.read_text() +
        '{"event":"detail","run_id":"%s","source":"%s","source_id":"%s",'
        '"description_markdown":"The full text.","ts":"2026-08-05T16:48:00Z"}\n'
        % (RID, read["source"], read["source_id"]))
    judge_all(jobs, [read], detail_read="true", relevant="true", match="strong",
              reasoning="Fits the brief.")
    judge_all(jobs, [other], detail_read="false", relevant="true", match="strong",
              reasoning="Fits the brief.", same_role_as=alias)
    return jobs, read, other


def test_one_opening_posted_twice_is_one_match_and_one_duplicate(tmp_path):
    """A run that finds the same opening in two cities reports one match, not two, and says how
    many postings it set aside rather than dropping the second one out of every number — the digest
    and the home card have to agree about how many openings the run found.

    `postings_reviewed` still counts postings. It pairs with `postings_unreviewed` against
    `postings_surfaced` and says how much work the run did, and judging the second posting was work
    the run did even though it found no second opening. That is why the duplicate needs a key of its
    own: without one, the four band keys would have to add up to a number that counts a posting none
    of them holds.
    """
    jobs, _, _ = seed_two_cities(tmp_path)
    r, c = counts(jobs)
    assert r.returncode == 0, r.stderr
    assert c["match_strong"] == "1"
    assert c["duplicates_of_another"] == "1"
    assert c["postings_reviewed"] == "2"
    assert (int(c["match_strong"]) + int(c["match_moderate"]) + int(c["match_weak"])
            + int(c["filtered_out"]) + int(c["duplicates_of_another"])) \
        == int(c["postings_reviewed"])


def test_the_duplicate_location_rides_on_the_row_that_survives(tmp_path):
    """The other city is information the user wants, so it goes on the surviving row instead of
    being dropped along with the posting that named it."""
    jobs, read, other = seed_two_cities(tmp_path)
    r, out = matches(jobs)
    assert r.returncode == 0, r.stderr
    assert len(out) == 1, out
    assert out[0][2] == read["source_id"]
    assert out[0][5] == read["location_display"]
    assert out[0][10] == other["location_display"]


def test_the_digest_count_equals_the_rows_it_lists(tmp_path):
    """The heading and the list under it are read together, so a count above a shorter list is the
    defect these two scripts exist to keep out of the digest.

    The one opening is asserted as well as the equality. The two agreed before this change too —
    measured on this log, `match_strong=2` above two rows — so the equality on its own passes the
    digest that shows one job twice.
    """
    jobs, _, _ = seed_two_cities(tmp_path)
    _, c = counts(jobs)
    _, out = matches(jobs)
    assert int(c["match_strong"]) == len([o for o in out if o[0] == "strong"]) == 1


def test_the_digest_and_the_home_card_report_the_same_opening_count(tmp_path):
    """`run-counts.sh` reads one run's events and `posting-counts.sh` reads the whole file, and this
    log holds one run, so the two are reading the same postings. Over those postings the three bands
    add up to `relevant` and `filtered_out` equals `filtered`. That is the agreement the digest and
    the home card are read against each other for.
    """
    jobs, _, _ = seed_two_cities(tmp_path)
    _, c = counts(jobs)
    r, p = postings(jobs)
    assert r.returncode == 0, r.stderr
    assert int(c["match_strong"]) + int(c["match_moderate"]) + int(c["match_weak"]) \
        == int(p["relevant"])
    assert int(c["filtered_out"]) == int(p["filtered"])


@pytest.mark.parametrize("alias", ["linkedin:no-such-posting", "the same job"],
                         ids=["an-id-no-search-turned-up", "not-written-as-a-pair"])
def test_a_judgment_naming_no_row_here_is_still_one_opening(tmp_path, alias):
    """The rule is on the field, not on what it names: a judgment carrying `same_role_as` is the
    same opening as another posting, so it is counted under `duplicates_of_another` and gets no row,
    whatever the value says. `posting-counts.sh` counts it the same way, on the same test, which is
    what keeps the two screens agreeing for a value neither of them can resolve.

    The location has nowhere to ride and is not printed. Giving the posting its own row instead
    would print the same opening twice whenever the value is a typo for a posting already listed,
    and nothing here can tell that apart from a value naming a posting that really is elsewhere.
    """
    jobs, read, _ = seed_two_cities(tmp_path, alias=alias)
    _, c = counts(jobs)
    assert c["match_strong"] == "1"
    assert c["duplicates_of_another"] == "1"
    _, p = postings(jobs)
    assert p["relevant"] == "1"
    _, out = matches(jobs)
    assert len(out) == 1, out
    assert out[0][2] == read["source_id"]
    assert out[0][10] == ""


def a_third_city(jobs, like, source_id, location):
    """Append a `surfaced` row for the opening `like` belongs to, in a city it has no row for.

    `search.linkedin.json` holds two rows for the Northwind Labs opening and no third, so the third
    city is written here rather than taken from the fixture. It carries that opening's company and
    title, which is what makes it the same opening, and `record-judgment.sh` copies the display
    fields off it the way it does for a row a search returned. The line is written in the compact
    form the writers produce, because `record-judgment.sh` finds a surfaced row with `grep -F` on
    `"source_id":"<id>"` and a space after the colon would miss it.
    """
    row = {"event": "surfaced", "run_id": RID, "source": like["source"], "source_id": source_id,
           "title": like["title"], "company_name": like["company_name"],
           "location_display": location, "source_url": like.get("source_url"),
           "posted_at": like.get("posted_at")}
    jobs.write_text(jobs.read_text() + json.dumps(row, separators=(",", ":")) + "\n")
    return row


def test_every_other_place_the_opening_was_posted_rides_on_its_row(tmp_path):
    """One opening posted in three places puts two locations on one row, joined with `; `.

    All three rows carry one company and one title — the two the fixture holds plus a third city
    written by `a_third_city` — so the case is the shape `dedup.sh --near` groups rather than three
    unrelated postings pointed at each other.

    The separator is a semicolon rather than a comma because a location carries commas of its own:
    the two joined here are `San Francisco, CA` and `Austin, TX`, and comma-joining them would give
    `San Francisco, CA,Austin, TX`, which no reader can split back into two places.
    `record-judgment.sh` takes `--dealbreakers` and `--unknowns` as semicolon-separated lists for
    the same reason.

    The order is the order the run judged the two postings in, which is the order `run-matches.awk`
    lists a band in, so two hosts reading one log print the same row.
    """
    jobs, read, other = seed_two_cities(tmp_path)
    third = a_third_city(jobs, read, "linkedin-9003", "Austin, TX")
    assert third["company_name"] == read["company_name"] and third["title"] == read["title"]
    judge_all(jobs, [third], detail_read="false", relevant="true", match="strong",
              reasoning="Fits the brief.",
              same_role_as="%s:%s" % (read["source"], read["source_id"]))
    _, c = counts(jobs)
    assert c["match_strong"] == "1"
    assert c["duplicates_of_another"] == "2"
    assert c["postings_reviewed"] == "3"
    _, out = matches(jobs)
    assert len(out) == 1, out
    assert out[0][10] == "%s; %s" % (other["location_display"], third["location_display"])


def test_a_row_no_other_posting_names_carries_an_empty_last_column(tmp_path):
    """Every row carries the same number of columns whether or not anything names it, so a caller
    splitting on tabs reads the same fields for every row."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    judge_all(jobs, rows[:2], detail_read="false", relevant="true", match="strong",
              reasoning="Fits.")
    r, out = matches(jobs)
    assert r.returncode == 0, r.stderr
    assert [len(o) for o in out] == [11, 11], out
    assert [o[10] for o in out] == ["", ""]


def test_a_duplicate_of_a_filtered_posting_is_a_duplicate_rather_than_a_filtered_row(tmp_path):
    """A judgment naming another posting copies that posting's verdict, so an alias of a posting the
    run threw out is itself not relevant. It is still one opening seen twice, so it is counted under
    `duplicates_of_another` and not under `filtered_out` — which is how `posting-counts.sh` counts
    it, under neither `relevant` nor `filtered`.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    read, other = rows[0], rows[1]
    judge_all(jobs, [read], detail_read="false", relevant="false", reasoning="On-site only.")
    judge_all(jobs, [other], detail_read="false", relevant="false", reasoning="On-site only.",
              same_role_as="%s:%s" % (read["source"], read["source_id"]))
    _, c = counts(jobs)
    assert c["filtered_out"] == "1"
    assert c["duplicates_of_another"] == "1"
    _, p = postings(jobs)
    assert p["filtered"] == "1"
    _, out = matches(jobs)
    assert len(out) == 1, out
    assert out[0][0] == "filtered"
    assert out[0][10] == other["location_display"]


def test_two_postings_naming_each_other_leave_no_row_and_are_both_duplicates(tmp_path):
    """Two judgments each naming the other is the one shape where the rule costs the user a row:
    both postings are the same opening as something else, so both are counted under
    `duplicates_of_another`, neither is in a band, and neither location has a row to ride on.

    It is pinned here because it is the case a reader will ask about. The counts still add up and
    the home card still agrees — `posting-counts.sh` drops both as well — so the two screens say the
    same thing rather than one of them showing an opening the other does not.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    a, b = rows[0], rows[1]
    judge_all(jobs, [a], detail_read="false", relevant="true", match="strong", reasoning="Fits.",
              same_role_as="%s:%s" % (b["source"], b["source_id"]))
    judge_all(jobs, [b], detail_read="false", relevant="true", match="strong", reasoning="Fits.",
              same_role_as="%s:%s" % (a["source"], a["source_id"]))
    r, c = counts(jobs)
    assert r.returncode == 0, r.stderr
    assert c["match_strong"] == "0"
    assert c["duplicates_of_another"] == "2"
    assert c["postings_reviewed"] == "2"
    _, p = postings(jobs)
    assert p["relevant"] == "0"
    r, out = matches(jobs)
    assert r.returncode == 0, r.stderr
    assert out == []


def test_a_later_judgment_naming_no_other_posting_takes_it_out_of_the_duplicates(tmp_path):
    """The last judgment this run recorded for a posting wins, and `record-judgment.awk` writes
    `same_role_as` only when it is given one, so a re-judgment without the flag carries no such
    field. The posting is back in its band and back in the listing rather than staying a duplicate
    off a value the log no longer holds.

    The second judgment is written straight to the log because `record-judgment.sh` refuses a second
    judgment for a posting this run already judged.

    Both readers are run and compared. `posting-counts.awk` used to set its alias flag once and
    never clear it, so on this log the digest reported two openings over two rows while the home
    card reported one — the disagreement this pair of scripts exists to remove, in a narrower shape.
    Asserting the `run-counts.sh` side alone is what let that through.
    """
    jobs, read, other = seed_two_cities(tmp_path)
    jobs.write_text(jobs.read_text() +
        '{"event":"evaluated","run_id":"%s","source":"%s","source_id":"%s",'
        '"location_display":"%s","detail_read":true,"relevant":true,"match":"weak"}\n'
        % (RID, other["source"], other["source_id"], other["location_display"]))
    _, c = counts(jobs)
    assert c["match_strong"] == "1"
    assert c["match_weak"] == "1"
    assert c["duplicates_of_another"] == "0"
    _, out = matches(jobs)
    assert [o[0] for o in out] == ["strong", "weak"], out
    assert [o[10] for o in out] == ["", ""], out
    r, p = postings(jobs)
    assert r.returncode == 0, r.stderr
    assert int(p["relevant"]) == len(out) == 2
    assert int(c["match_strong"]) + int(c["match_moderate"]) + int(c["match_weak"]) \
        == int(p["relevant"])


def test_an_alias_carrying_no_location_adds_nothing_to_the_column(tmp_path):
    """A posting is still the same opening as another when its row came back without a location, so
    it is still counted under `duplicates_of_another` and still gets no row — there is just nothing
    to put on the row it names.

    `record-api-response.sh` writes `null` for a field a row does not carry and
    `record-judgment.awk` copies it, so `null` is a shape the product produces. The empty string is
    the other, and the two arrive as different values from `jval` — the four characters `null` and
    nothing at all — so the log carries one of each. Joined rather than skipped they reach the
    digest as `also posted in ; null; Austin, TX`, which is what deleting the skip prints here.

    Four rows of one Northwind Labs opening: the one the fixture holds, plus three written by
    `a_third_city`, so this is one opening posted in four places and not four companies pointed at
    each other. Every judgment goes through `record-judgment.sh`, which copies `location_display`
    off the surfaced row, so the empty and the null reach the reader the way a run would produce
    them rather than being written onto the event by hand.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    read = next(r for r in rows if r["source_id"] == "linkedin-0002")
    judge_all(jobs, [read], detail_read="false", relevant="true", match="strong", reasoning="Fits.")
    blank = a_third_city(jobs, read, "linkedin-9001", "")
    nulled = a_third_city(jobs, read, "linkedin-9002", None)
    kept = a_third_city(jobs, read, "linkedin-9003", "Austin, TX")
    alias = "%s:%s" % (read["source"], read["source_id"])
    for row in (blank, nulled, kept):
        judge_all(jobs, [row], detail_read="false", relevant="true", match="strong",
                  reasoning="Fits.", same_role_as=alias)
    judged = {e["source_id"]: e for e in lines(jobs) if e["event"] == "evaluated"}
    assert judged["linkedin-9001"]["location_display"] == ""
    assert judged["linkedin-9002"]["location_display"] is None
    _, c = counts(jobs)
    assert c["match_strong"] == "1"
    assert c["duplicates_of_another"] == "3"
    _, out = matches(jobs)
    assert len(out) == 1, out
    assert out[0][10] == kept["location_display"]


# `source_id`s that carry a colon, which is why the pair is split at the first one. A greenhouse id
# is written `<board>:<number>`; these two are the shape of one company's board with two postings on
# it. No committed fixture has a greenhouse response, so the two `surfaced` events are written by
# hand and the judgments go through `record-judgment.sh`, which is what reads `--same-role-as`.
GH_READ = "acme:7310605"
GH_OTHER = "acme:7310606"


def seed_two_greenhouse_rows(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("".join(
        '{"event":"surfaced","run_id":"%s","source":"greenhouse","source_id":"%s",'
        '"title":"Director, FP&A","company_name":"Acme","location_display":"%s",'
        '"source_url":"https://boards.greenhouse.io/acme/jobs/%s","posted_at":"2026-08-01"}\n'
        % (RID, sid, city, sid.split(":")[1])
        for sid, city in ((GH_READ, "Austin, TX"), (GH_OTHER, "Boston, MA"))))
    return jobs


def test_a_source_id_carrying_a_colon_resolves_to_the_posting_it_names(tmp_path):
    """`same_role_as` is `<source>:<source_id>` split at the FIRST colon, because a source_id can
    hold one of its own.

    Split at the last colon instead and `greenhouse:acme:7310605` names source `greenhouse:acme`
    with source_id `7310605`, which no posting in the log has. Nothing about the counts moves — the
    duplicate is still a duplicate and the row is still one row — so the only thing that changes is
    that the other city silently disappears from every greenhouse duplicate. That is what this case
    is here to catch.
    """
    jobs = seed_two_greenhouse_rows(tmp_path)
    run_script(JUDGE, jobs, "--run-id", RID, "--source", "greenhouse", "--source-id", GH_READ,
               "--detail-read", "false", "--relevant", "true", "--match", "strong",
               "--reasoning", "Fits.")
    r = run_script(JUDGE, jobs, "--run-id", RID, "--source", "greenhouse", "--source-id", GH_OTHER,
                   "--detail-read", "false", "--relevant", "true", "--match", "strong",
                   "--reasoning", "Fits.", "--same-role-as", "greenhouse:" + GH_READ)
    assert r.returncode == 0, r.stderr
    _, c = counts(jobs)
    assert c["match_strong"] == "1"
    assert c["duplicates_of_another"] == "1"
    _, out = matches(jobs)
    assert len(out) == 1, out
    assert out[0][2] == GH_READ
    assert out[0][10] == "Boston, MA"


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
    """Invariant 4 has to hold a year later, not only at close.

    The two counts are pinned to the fixture before the later run's events are added, because a
    counter that never moves at all also satisfies `after == before`. Measured 2026-08-06 with
    `reviewed++` and `unreviewed++` deleted from `run-counts.awk`'s END loop: both counts printed 0
    before and after, 8 cases in this module failed, and this one passed."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    _, before = counts(jobs)
    assert before["postings_unreviewed"] == str(len(api_rows("search.linkedin.json")))
    assert before["postings_reviewed"] == "0"
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


# ---------------------------------------------------------------------------- run-matches.sh

def matches(jobs, run_id=RID):
    r = run_script(MATCHES, jobs, run_id)
    rows = [l.split("\t") for l in r.stdout.splitlines()]
    return r, rows


def test_every_judged_posting_appears_once_with_its_band(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    judge_all(jobs, rows[:2], detail_read="false", relevant="true", match="strong", reasoning="Fits.")
    judge_all(jobs, rows[2:4], detail_read="false", relevant="false", reasoning="On-site only.")
    r, out = matches(jobs)
    assert r.returncode == 0, r.stderr
    assert len(out) == 4
    assert [o[0] for o in out] == ["strong", "strong", "filtered", "filtered"]


def test_the_bands_come_out_in_digest_order(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    judge_all(jobs, rows[0:1], detail_read="false", relevant="false", reasoning="No.")
    judge_all(jobs, rows[1:2], detail_read="false", relevant="true", match="weak", reasoning="Thin.")
    judge_all(jobs, rows[2:3], detail_read="false", relevant="true", match="strong", reasoning="Yes.")
    judge_all(jobs, rows[3:4], detail_read="false", relevant="true", match="moderate", reasoning="Ok.")
    _, out = matches(jobs)
    assert [o[0] for o in out] == ["strong", "moderate", "weak", "filtered"]


def test_a_row_carries_what_the_digest_prints(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true", match="strong",
                                  needs_human_check="true",
                                  reasoning="Remote within the US and the range clears the floor."))
    _, out = matches(jobs)
    band, source, sid, title, company, loc, url, nhc, posted, reasoning, also = out[0]
    assert (band, source, sid) == ("strong", row["source"], row["source_id"])
    assert (title, company, url) == (row["title"], row["company_name"], row["source_url"])
    assert loc == row["location_display"]
    assert nhc == "true"
    assert reasoning.startswith("Remote within the US")
    assert also == ""          # no other posting names this one as the same opening


def test_reasoning_with_a_newline_stays_on_one_line(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true", match="strong",
                                  reasoning="First line.\nSecond line."))
    r, out = matches(jobs)
    assert len(r.stdout.splitlines()) == 1
    assert len(out[0]) == 11
    assert "First line." in out[0][9] and "Second line." in out[0][9]


def test_a_surfaced_but_unjudged_posting_is_not_listed(tmp_path):
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    r, out = matches(jobs)
    assert r.returncode == 0 and out == []


def test_another_runs_judgments_are_not_listed(tmp_path):
    """The copied run judges the same posting weak, and the band is asserted alongside the row
    count because the copy carries the same ids: with the run filter removed, its judgment lands on
    the `source SUBSEP source_id` key this run already holds and the row count does not move
    (measured — that mutation passes on the row count alone). The band is where the filter is
    visible, because the later event of the two is the one the row is printed from.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true", match="strong"))
    other = (jobs.read_text().replace(RID, "2026-01-01T00-00-00Z")
             .replace('"match":"strong"', '"match":"weak"'))
    jobs.write_text(jobs.read_text() + other)
    _, out = matches(jobs)
    assert [o[0] for o in out] == ["strong"]


def test_the_listing_and_the_counts_agree(tmp_path):
    """The maintainer's live behavior evals check the same thing against a real run: that the
    digest's counts and the postings it names both come back out of `jobs.jsonl` and agree. This
    test checks it against a fixture.

    The three numbers this test recorded are pinned first, because two scripts that are wrong in
    the same way also agree. Measured 2026-08-06 with `jval` in `event-field.awk` returning "" for
    `relevant`: every judgment read as not relevant, `run-counts.sh` put all 25 postings in
    `filtered_out`, `run-matches.sh` printed all 25 under `filtered`, the two agreed, 11 cases in
    this module failed, and this one passed.

    The 3 below is the slice point the two `judge_all` calls use, not a count of the fixture's
    rows."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    judge_all(jobs, rows[:3], detail_read="false", relevant="true", match="moderate", reasoning="Ok.")
    judge_all(jobs, rows[3:], detail_read="false", relevant="false", reasoning="No.")
    _, c = counts(jobs)
    _, out = matches(jobs)
    assert int(c["match_moderate"]) == 3
    assert int(c["filtered_out"]) == len(rows) - 3
    assert len(out) == len(rows)
    tally = {}
    for o in out:
        tally[o[0]] = tally.get(o[0], 0) + 1
    assert tally.get("strong", 0) == int(c["match_strong"])
    assert tally.get("moderate", 0) == int(c["match_moderate"])
    assert tally.get("weak", 0) == int(c["match_weak"])
    assert tally.get("filtered", 0) == int(c["filtered_out"])
    assert len(out) == int(c["postings_reviewed"]) - int(c["duplicates_of_another"])


def test_one_bands_postings_come_out_in_the_order_they_were_judged(tmp_path):
    """Within a band the order is the order the judgments landed, which is neither the order the
    search surfaced them nor the order an awk array walk returns them in.

    The five are judged in a scrambled order so a listing that kept the surfaced order fails, and
    the ids are asserted rather than the bands, which are all the same here.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    judged = [rows[3], rows[0], rows[4], rows[2], rows[1]]
    judge_all(jobs, judged, detail_read="false", relevant="true", match="strong", reasoning="Fits.")
    _, out = matches(jobs)
    assert [o[2] for o in out] == [e["source_id"] for e in judged]


def test_a_judgment_for_a_posting_this_run_never_surfaced_is_not_listed(tmp_path):
    """`run-counts.sh` counts only the postings this run surfaced, so a judgment carrying an id no
    search of this run turned up is in none of its numbers. The listing leaves out the same row, so
    the digest cannot name a posting its own counts do not count.

    `record-judgment.sh` looks for the surfaced event before it writes, so nothing it writes can
    reach this state. The judgment is appended to the log here directly, which is the only way to
    reach it.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true", match="strong"))
    jobs.write_text(jobs.read_text() +
        '{"event":"evaluated","run_id":"%s","source":"%s","source_id":"never-surfaced",'
        '"detail_read":true,"relevant":true,"match":"strong"}\n' % (RID, row["source"]))
    _, c = counts(jobs)
    _, out = matches(jobs)
    assert len(out) == 1
    assert c["postings_reviewed"] == "1"


def test_one_posting_judged_twice_in_a_run_is_listed_once_with_the_later_verdict(tmp_path):
    """One row per posting, carrying the last judgment this run recorded — the rule
    `run-counts.awk` counts by on its own `evaluated` branch, `grep -n 'The last judgment'
    skills/job-search-run/scripts/run-counts.awk`, which is what keeps the listing and the
    counts the same length.

    `record-judgment.sh` writes nothing for a posting this run has already judged, so both events
    are written here directly.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    for band in ("weak", "strong"):
        jobs.write_text(jobs.read_text() +
            '{"event":"evaluated","run_id":"%s","source":"%s","source_id":"%s",'
            '"detail_read":true,"relevant":true,"match":"%s"}\n'
            % (RID, row["source"], row["source_id"], band))
    _, out = matches(jobs)
    assert [o[0] for o in out] == ["strong"]


def test_a_relevant_row_with_no_band_is_not_listed(tmp_path):
    """`run-counts.sh` is the script that reports this row: it counts it as reviewed, prints
    `INVALID relevant-row-without-a-band` and exits 1. Here the row is left out rather than put
    under a band nobody wrote, so no digest can name a strong match the log never called strong.

    The row count is asserted against `postings_reviewed` less the unbanded rows and less the
    postings that are the same opening as another, which is the relation `run-matches.sh`'s header
    states — `grep -n 'row count is'
    skills/job-search-run/scripts/run-matches.sh`.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    jobs.write_text(jobs.read_text() +
        '{"event":"evaluated","run_id":"%s","source":"%s","source_id":"%s",'
        '"detail_read":true,"relevant":true,"match":null}\n'
        % (RID, row["source"], row["source_id"]))
    r, out = matches(jobs)
    assert r.returncode == 0, r.stderr
    assert out == []
    _, c = counts(jobs)
    unbanded = int(c["INVALID relevant-row-without-a-band"])
    assert len(out) == int(c["postings_reviewed"]) - unbanded - int(c["duplicates_of_another"])


def test_a_relevant_row_carrying_the_filtered_band_is_not_listed(tmp_path):
    """`filtered` is what a row judged not relevant gets, not a value a judgment carries, so a
    relevant row holding the string is a row with no band — the same row `run-counts.awk`'s END
    block counts as relevant-row-without-a-band and leaves out of `filtered_out`. Listing it would
    put a posting under a heading whose count is one lower.

    The row count is asserted against `postings_reviewed` less the unbanded rows and less the
    postings that are the same opening as another, which is the relation `run-matches.sh`'s header
    states — `grep -n 'row count is'
    skills/job-search-run/scripts/run-matches.sh`.

    `record-judgment.sh` takes only strong, moderate or weak on a relevant row — `grep -n 'needs
    --match' skills/job-search-run/scripts/record-judgment.sh` — so the event is appended to the log
    here directly.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    rows = [e for e in lines(jobs) if e["event"] == "surfaced"]
    judge_all(jobs, rows[:1], detail_read="false", relevant="true", match="strong", reasoning="Ok.")
    jobs.write_text(jobs.read_text() +
        '{"event":"evaluated","run_id":"%s","source":"%s","source_id":"%s",'
        '"detail_read":true,"relevant":true,"match":"filtered"}\n'
        % (RID, rows[1]["source"], rows[1]["source_id"]))
    r, c = counts(jobs)
    _, out = matches(jobs)
    assert [o[0] for o in out] == ["strong"]
    assert c["filtered_out"] == "0"
    unbanded = int(c["INVALID relevant-row-without-a-band"])
    assert len(out) == int(c["postings_reviewed"]) - unbanded - int(c["duplicates_of_another"])


def test_a_tab_in_the_reasoning_does_not_add_a_twelfth_column(tmp_path):
    """A row is eleven tab-separated columns, so a tab inside the free text would put a twelfth one
    there and shift every column after it. `jval` maps a tab, a newline and a CR to a space;
    resolving the escapes here instead of calling it is what would break this.

    HOSTILE puts a real tab and a real newline on the event — see
    `test_free_text_with_quotes_backslashes_tabs_and_newlines_round_trips` — along with a quote and
    a backslash, which must arrive unchanged. The whole value is asserted rather than a substring,
    so the two whitespace substitutions are the only difference the row may carry.
    """
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true", match="strong",
                                  reasoning=HOSTILE))
    r, out = matches(jobs)
    assert len(r.stdout.splitlines()) == 1
    assert len(out[0]) == 11
    assert out[0][9] == HOSTILE.replace("\t", " ").replace("\n", " ")


def test_two_postings_that_would_share_a_pipe_joined_key_are_both_listed(tmp_path):
    """The posting key joins `source` and `source_id` with SUBSEP, the 0x1c byte, which cannot
    reach a value. A `|` can: `record-judgment.sh`'s `reject_id` refuses only a control character
    and a backslash, so source `s` with source_id `x|y` and source `s|x` with source_id `y` are
    both recorded, and both join to `s|x|y`.

    Measured with the key joined on `|` instead: those two postings collide and the listing prints
    one row where it should print two.

    The log is written here rather than seeded from a fixture, because no fixture carries a `|` in
    an id and the collision needs one on each side of the join.
    """
    pair = (("s", "x|y", "strong"), ("s|x", "y", "moderate"))
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("".join(
        '{"event":"surfaced","run_id":"%s","source":"%s","source_id":"%s","title":"T",'
        '"company_name":"C","location_display":"L","source_url":"U","posted_at":"2026-07-25"}\n'
        % (RID, source, source_id) for source, source_id, _ in pair))
    for source, source_id, band in pair:
        r = run_script(JUDGE, jobs, "--run-id", RID, "--source", source, "--source-id", source_id,
                       "--detail-read", "false", "--relevant", "true", "--match", band)
        assert r.returncode == 0, r.stderr
    _, out = matches(jobs)
    assert [(o[0], o[1], o[2]) for o in out] == [(band, source, source_id)
                                                 for source, source_id, band in pair]


def test_an_awk_that_died_partway_is_not_reported_as_a_listing(tmp_path):
    """The rows go to stdout, so a caller cannot tell a complete listing from a partial one by
    reading it — an awk that died after printing one posting leaves one real-looking row there.
    The exit status is what tells them apart, and it is awk's own status: with awk shimmed to print
    one row and then fail, this must not exit 0."""
    jobs = seeded_jobs(tmp_path, "search.linkedin.json")
    row = first_surfaced(jobs)
    run_script(JUDGE, *judge_args(jobs, row, detail_read="false", relevant="true", match="strong"))
    partial = "strong\t%s\t%s\tT\tC\tRemote\thttps://example/x\tfalse\t2026-07-25\tFits.\n" % (
        row["source"], row["source_id"])
    r = run_script(MATCHES, jobs, RID, env=awk_shim(tmp_path, "run-matches.awk", partial))
    assert r.returncode != 0, r.stdout
    assert r.stdout == partial            # the row a caller would have put in the digest


def test_a_listing_for_a_log_that_is_not_there_exits_two_and_prints_nothing(tmp_path):
    """A missing log is not a run that judged nothing. Both print no rows, and the status is what
    separates them: printing nothing at exit 0 would put an empty digest behind a path typed
    wrong."""
    r, out = matches(tmp_path / "absent.jsonl")
    assert r.returncode == 2
    assert out == []
    assert "no such file" in r.stderr


# ---------------------------------------------------------------------------------- open-run.sh

RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$")
UTC_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def parsed_output(r):
    """The `key=value` lines `open-run.sh` prints, as a dict.

    The split takes the first `=` only, and lines without one are dropped, so the workspace
    findings that follow the three lines on stdout do not enter the dict.
    """
    return dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)


def date_shim(tmp_path):
    """A PATH whose `date` answers a later second on every call and records how many it got.

    `validate-workspace.sh` runs no `date`, so every call the shim records is one this script made.
    """
    d = tmp_path / "date-shim"
    d.mkdir(exist_ok=True)
    calls = d / "calls"
    shim = d / "date"
    shim.write_text(
        "#!/bin/sh\n"
        "printf 'x' >> %s\n"
        "n=$(wc -c < %s | tr -d ' ')\n"
        "printf '2026-07-30T15:04:%%02dZ\\n' \"$n\"\n" % (calls, calls),
        encoding="utf-8")
    shim.chmod(0o755)
    return calls, {"PATH": "%s:%s" % (d, os.environ["PATH"])}


def test_run_id_and_started_at_name_the_same_instant(tmp_workspace):
    r = run_script(OPEN_RUN, tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr
    out = parsed_output(r)
    assert RUN_ID_RE.match(out["run_id"])
    assert UTC_TS_RE.match(out["started_at"])
    assert out["run_id"] == out["started_at"].replace(":", "-")


def test_the_clock_is_read_once(tmp_workspace, tmp_path):
    """Two `date` calls back to back land in the same second nearly every time, so the test above
    passes against a script that reads the clock twice: with the `tr` line replaced by a second
    `date -u` call, this is the only test in the suite that fails (1 failed, 697 passed). Against a
    `date` that never answers twice alike, only one read can produce two lines naming the same
    instant."""
    calls, env = date_shim(tmp_path)
    r = run_script(OPEN_RUN, tmp_workspace, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    out = parsed_output(r)
    assert calls.read_text() == "x"
    assert out["started_at"] == "2026-07-30T15:04:01Z"
    assert out["run_id"] == "2026-07-30T15-04-01Z"


def test_opening_creates_the_marker(tmp_workspace):
    out = parsed_output(run_script(OPEN_RUN, tmp_workspace))
    assert (tmp_workspace / "runs" / (".started-" + out["run_id"])).exists()


def test_open_run_refuses_while_another_run_is_open(tmp_workspace):
    first = subprocess.run(["sh", str(OPEN_RUN), str(tmp_workspace)],
                           capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    markers = sorted(p.name for p in (tmp_workspace / "runs").glob(".started-*"))
    assert len(markers) == 1

    second = subprocess.run(["sh", str(OPEN_RUN), str(tmp_workspace)],
                            capture_output=True, text=True)
    assert second.returncode == 2
    assert "already open" in second.stderr
    assert markers[0].replace(".started-", "") in second.stderr
    assert sorted(p.name for p in (tmp_workspace / "runs").glob(".started-*")) == markers


FROZEN_STAMP = "2026-07-30T15:04:02Z"


def frozen_date(tmp_path, stamp=FROZEN_STAMP):
    """A PATH whose `date` always answers the same second, so two runs are handed one `run_id`.

    Two consecutive calls land in the same second most of the time but not reliably, and the two
    cases that still take this pin it rather than hope for it: the concurrency case, which needs
    both children handed the same `run_id` before `set -C` decides between them, and the leftover
    marker case, which needs the id being minted to differ from the 2020 marker on disk.
    """
    d = tmp_path / "frozen-date"
    d.mkdir(exist_ok=True)
    shim = d / "date"
    shim.write_text("#!/bin/sh\nprintf '%s\\n'\n" % stamp, encoding="utf-8")
    shim.chmod(0o755)
    return {"PATH": "%s:%s" % (d, os.environ["PATH"])}


def test_a_refused_open_names_the_open_run_rather_than_an_unwritable_runs_dir(tmp_workspace):
    """A refused open prints one of two messages and they send the caller to different places: a run
    is already open, or `runs/` could not be written to. This case drives the first and asserts the
    second is absent, because a caller that read `cannot write the started-marker` here would go
    looking for a permissions problem in a workspace that has none.

    It also holds the refusal to one line on stderr and nothing at all on stdout. Stdout is where
    `run_id`, `started_at` and `brief_revision` go, so a byte there would hand a caller a run that
    did not open.

    No frozen clock. This case used to pin both opens to one second, because before the
    one-run-at-a-time guard the second open was refused by the `set -C` write and only a shared
    `run_id` could trigger that. The guard refuses on the marker's presence and never compares the
    two ids, so the second open is refused whether or not the clock has moved on, and the override
    would have pinned a condition the outcome no longer depends on. Why a shared `run_id` still has
    to be refused is written where `grep -n 'Why a shared run_id has to be refused'
    skills/job-search-runbook/scripts/open-run.sh` points, and the case below drives it.
    """
    first = run_script(OPEN_RUN, tmp_workspace)
    assert first.returncode == 0, first.stdout + first.stderr
    run_id = parsed_output(first)["run_id"]

    second = run_script(OPEN_RUN, tmp_workspace)
    assert second.returncode == 2, second.stdout + second.stderr
    assert second.stdout == ""
    assert run_id in second.stderr
    assert "cannot write the started-marker" not in second.stderr
    assert "already open" in second.stderr
    assert len(second.stderr.splitlines()) == 1, second.stderr
    assert [p.name for p in (tmp_workspace / "runs").glob(".started-*")] == [".started-" + run_id]


def test_the_refusal_names_the_flags_close_run_will_not_run_without(tmp_workspace):
    """The message tells the caller to close the open run, and `close-run.sh` exits 1 without either
    `--trigger` or `--close-state` — `close-run.sh:93` and `:96`. A message naming the two scripts
    but not the flags sends the caller to a command that fails, so both flags and their values are
    part of what this refusal has to say.

    `manual` rather than `scheduled`: nothing on disk records what started a run that never closed.
    `trigger` is written in one place, `runs/<run_id>.json` at `close-run.sh:338`, which is the file
    an unclosed run does not have; the marker is empty; and no event in `jobs.jsonl` carries the
    field. Of the two values `close-run.sh` takes, `scheduled` is the one the scheduling canary
    reads as proof the scheduler ran — `grep -n 'canary passes' skills/job-search/SKILL.md` — so
    `manual` is the one that does not write `scheduled` into a record when no scheduler ran.

    That the two commands run is not asserted here by reading them. The case below runs them.
    """
    first = run_script(OPEN_RUN, tmp_workspace)
    assert first.returncode == 0, first.stdout + first.stderr

    second = run_script(OPEN_RUN, tmp_workspace)
    assert second.returncode == 2, second.stdout + second.stderr
    assert "--trigger manual" in second.stderr
    assert "--close-state interrupted" in second.stderr


def printed_commands(refusal):
    """The commands a refusal printed, taken out of the message rather than composed from its parts.

    Each is wrapped in backticks by the message, and nothing else in it is. Composing the expected
    command here instead would only check the test's own command against the test's own command,
    which is what three rounds of review found: the command asserted against was each time the
    corrected one, and the command printed was each time the broken one.
    """
    commands = re.findall(r"`([^`]+)`", refusal.stderr)
    assert len(commands) == 2, refusal.stderr
    return commands


def run_as_printed(command, cwd):
    """Run one printed command through `sh -c`, from `cwd`, with the scripts nowhere on PATH.

    PATH holds the system directories and nothing else, so a command naming a script by bare
    basename exits 127 here — which is what it did for a caller at a shell, and what three rounds of
    hand-checking missed by running from a PATH that had been extended with the scripts directory.
    """
    return subprocess.run(["sh", "-c", command], cwd=str(cwd), capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"})


def test_the_printed_recovery_commands_run_as_printed(tmp_workspace, tmp_path):
    """The refusal's two commands are run exactly as the refusal printed them, from a directory that
    holds neither script, and both have to exit 0 and leave the workspace ready to open again.

    This is the case that closes one defect three reviews found three times in three different
    forms: the message left out `--close-state`, then left out `--trigger`, then named the scripts
    by bare basename, so `close-run.sh …` exited 127 with `command not found`. Every one of those
    shipped past a hand-check, because the command typed into the terminal was each time not the
    command the script printed. Taking the text out of stderr and running that is what makes the two
    the same thing.

    The workspace path carries a space, which is what single-quoting the arguments is for. Unquoted,
    the shell splits the path at each space when the command runs: measured on `/…/a work space`,
    `close-run.sh` gets `/…/a` as the workspace and `work` as the run id, then stops at `space` with
    `close-run: unknown option space` and exit 1, under both `sh` and `dash`.
    """
    ws = tmp_path / "a work space"
    shutil.copytree(str(tmp_workspace), str(ws))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    first = run_script(OPEN_RUN, ws)
    assert first.returncode == 0, first.stdout + first.stderr
    run_id = parsed_output(first)["run_id"]
    (ws / "jobs.jsonl").write_text("", encoding="utf-8")

    refused = run_script(OPEN_RUN, ws)
    assert refused.returncode == 2, refused.stdout + refused.stderr
    close_cmd, clear_cmd = printed_commands(refused)

    closed = run_as_printed(close_cmd, elsewhere)
    assert closed.returncode == 0, "%s\n%s%s" % (close_cmd, closed.stdout, closed.stderr)
    assert (ws / "runs" / (run_id + ".json")).exists(), close_cmd

    cleared = run_as_printed(clear_cmd, elsewhere)
    assert cleared.returncode == 0, "%s\n%s%s" % (clear_cmd, cleared.stdout, cleared.stderr)

    reopened = run_script(OPEN_RUN, ws)
    assert reopened.returncode == 0, reopened.stdout + reopened.stderr
    assert [p.name for p in (ws / "runs").glob(".started-*")] == [
        ".started-" + parsed_output(reopened)["run_id"]]


def test_the_printed_commands_run_when_open_run_was_called_by_a_relative_path(tmp_workspace,
                                                                              tmp_path):
    """`dirname "$0"` is relative whenever this script was called by a relative path, so a message
    built from it alone prints commands that run only from the directory the caller happened to be
    in. Called as `sh skills/job-search-runbook/scripts/open-run.sh` from the repo root, the printed
    commands are run from a third directory here, which is where a relative path fails.

    This is why the refusal takes `cd "$here" && pwd` rather than `$here`.
    """
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    rel = OPEN_RUN.relative_to(ROOT).as_posix()

    first = subprocess.run(["sh", rel, str(tmp_workspace)], cwd=str(ROOT),
                           capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    (tmp_workspace / "jobs.jsonl").write_text("", encoding="utf-8")

    refused = subprocess.run(["sh", rel, str(tmp_workspace)], cwd=str(ROOT),
                             capture_output=True, text=True)
    assert refused.returncode == 2, refused.stdout + refused.stderr
    for command in printed_commands(refused):
        r = run_as_printed(command, elsewhere)
        assert r.returncode == 0, "%s\n%s%s" % (command, r.stdout, r.stderr)


def test_a_marker_with_no_run_id_does_not_hide_a_real_one(tmp_workspace):
    """`runs/.started-` with nothing after the dash makes `${m##*/.started-}` expand to empty, and
    an empty value is what the guard reads as no run open. It sorts before every `.started-<run_id>`
    — measured under both `sh` and `dash`, where `for m in runs/.started-*` lists `.started-` first —
    so a guard that stopped at the first name in the directory would open a second run on top of a
    real marker, which is the one thing it exists to prevent.

    The empty name is skipped rather than refused on. Refusing would print an empty run id, and
    `close-run.sh` and `clear-run.sh` both refuse one at their `${2:?…}` usage guard, so the caller
    would be told to run two commands that cannot take the value the message gave them.
    """
    (tmp_workspace / "runs" / ".started-").write_text("")
    (tmp_workspace / "runs" / ".started-2020-01-01T00-00-00Z").write_text("")
    r = run_script(OPEN_RUN, tmp_workspace)
    assert r.returncode == 2, r.stdout + r.stderr
    assert r.stdout == ""
    assert "2020-01-01T00-00-00Z" in r.stderr
    assert sorted(p.name for p in (tmp_workspace / "runs").glob(".started-*")) == [
        ".started-", ".started-2020-01-01T00-00-00Z"]


def forked_together(workspace, env, tmp_path, count=2, shell="sh"):
    """Start `count` `open-run.sh` processes from one shell's forks and collect their exits.

    One shell forks them in a loop, so the children start tens of microseconds apart. Starting
    them with `Popen` from Python instead spaces them about seven times wider. Measured with a
    `clock_gettime` stamp taken in each child, 200 rounds: this launcher a median of 87 microseconds
    apart, `Popen` a median of 591, with 199 of its 200 samples still under a millisecond. That gap
    decides whether the defect is reachable at all: against one and the same script — the version
    that tested for the marker with `[ -e ]` and wrote it afterwards — `Popen` had both children
    open the run in 1 of 300 rounds and this launcher in 261 of 300.

    Each child's stderr goes to its own file, and the statuses come back in the order the children
    were forked, which is the order the files are named in, so the two lists line up.
    """
    out = tmp_path / "forked"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    launcher = (
        'i=0; pids=""\n'
        'while [ "$i" -lt %d ]; do "%s" "%s" "%s" >"%s/$i.out" 2>"%s/$i.err" & '
        'pids="$pids $!"; i=$((i+1)); done\n'
        'for p in $pids; do wait "$p"; printf "%%s\\n" "$?"; done\n'
        % (count, shell, OPEN_RUN, workspace, out, out))
    e = dict(os.environ)
    e.update(env)
    r = subprocess.run(["sh", "-c", launcher], capture_output=True, text=True, env=e)
    codes = [int(x) for x in r.stdout.split()]
    assert len(codes) == count, r.stdout + r.stderr
    return codes, [(out / ("%d.err" % i)).read_text() for i in range(count)]


def test_two_runs_starting_at_once_do_not_both_get_the_run_id(tmp_workspace, tmp_path):
    """The refusal above has to hold when the two runs overlap, not only when one has finished
    before the other starts — a scheduled run starting alongside a manual one is the case, and it
    needs no person at a keyboard. Testing for the marker and writing it afterwards are two
    operations, so both processes get past the test before either writes: measured with a pinned
    clock and this launcher, 261 of 300 rounds under `sh` and 267 of 300 under `dash` had both
    children exit 0 with one marker on disk, and 106 of 200 with four children. `set -C` moves the
    refusal into the write itself, and the same harness then gives 0 of 300, 0 of 300 and 0 of 200.

    Five rounds here rather than one, because a round proves something only when the two children
    overlap and they do not overlap every time. Run against a check-then-write script, this case
    failed 20 of 20 times. On the CI runner `/bin/sh` is `dash`, so it covers the shell the script
    ships against there without naming it.

    Which of the two refusals the loser gets depends on how far apart the children start: the
    one-run-at-a-time guard when the first child has already written its marker, `set -C` when it
    has not. The assertions below check the outcome — one exit 2, one marker on disk — because that
    holds either way. Asserting the message would make this case depend on the timing it measures.
    """
    env = frozen_date(tmp_path)
    run_id = FROZEN_STAMP.replace(":", "-")
    runs = tmp_workspace / "runs"
    for _ in range(5):
        for stale in runs.glob(".started-*"):
            stale.unlink()
        codes, errs = forked_together(tmp_workspace, env, tmp_path)
        assert sorted(codes) == [0, 2], codes
        refused = errs[codes.index(2)]
        assert run_id in refused
        assert "cannot write the started-marker" not in refused
        assert [p.name for p in runs.glob(".started-*")] == [".started-" + run_id]


def test_a_leftover_marker_from_an_earlier_run_refuses_this_one(tmp_workspace, tmp_path):
    """The marker a run that died left behind refuses the new run too. It is the one case `set -C`
    lets through, because the marker carries the earlier run's id and the write below is to the id
    being minted now: with the 2020 marker here and a frozen 2026 clock, the version without the
    one-run-at-a-time guard exited 0 and left both markers in `runs/`.

    Nothing in `runs/` says whether the run that wrote a marker is still going or stopped, so both
    are refused and the caller decides which it is. Refusing keeps `runs/` down to one marker, which
    is what lets a caller that was not handed a run id find the open one by reading the directory.
    """
    (tmp_workspace / "runs" / ".started-2020-01-01T00-00-00Z").write_text("")
    r = run_script(OPEN_RUN, tmp_workspace, env=frozen_date(tmp_path))
    assert r.returncode == 2, r.stdout + r.stderr
    assert r.stdout == ""
    assert "2020-01-01T00-00-00Z" in r.stderr
    assert [p.name for p in (tmp_workspace / "runs").glob(".started-*")] == [
        ".started-2020-01-01T00-00-00Z"]


def test_a_marker_that_cannot_be_written_stops_the_run_before_it_prints(tmp_workspace):
    """A run_id is what the close is given, so printing one for a run with no marker on disk would
    hand the close a run that nothing on disk records as started. The marker is written before the
    three lines for that reason, and with `runs/` at mode 500 the write is the only thing that
    fails: the workspace is otherwise whole."""
    runs = tmp_workspace / "runs"
    runs.chmod(0o500)
    try:
        r = run_script(OPEN_RUN, tmp_workspace)
    finally:
        runs.chmod(0o700)
    assert r.returncode == 2, r.stdout + r.stderr
    assert r.stdout == ""
    assert not list(runs.glob(".started-*"))


@pytest.mark.skipif(not shutil.which("dash"), reason="dash is not installed here")
def test_a_marker_that_cannot_be_written_is_reported_in_this_scripts_own_words(tmp_workspace):
    """The marker is written with `printf '' >`, not `: >`, and the two differ only under dash.
    Measured with `runs/` at mode 500: `: > runs/.started-x || { …; exit 9; }` is caught by the
    `||` under bash, but dash aborts on the redirection before the `||` runs, so this script's
    message never prints and the caller gets dash's instead. The status is 2 either way —
    `open-run.sh` exits 2 there too — so the message is the whole difference, and the message is
    what this case asserts. `shell="dash"` is named rather than left at `sh` because `/bin/sh` is
    bash on the machine where this was measured and dash on the CI runner: under bash it would pass
    whichever of the two wrote the marker.

    This is the second of the two messages a failed marker write can produce, now that `set -C`
    makes a taken `run_id` come back the same way an unwritable `runs/` does. `runs/` at mode 500
    picks this one: the marker is not on disk, so the branch reports the write rather than the
    name."""
    runs = tmp_workspace / "runs"
    runs.chmod(0o500)
    try:
        r = run_script(OPEN_RUN, tmp_workspace, shell="dash")
    finally:
        runs.chmod(0o700)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "open-run.sh: cannot write the started-marker" in r.stderr


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


def test_a_workspace_with_no_brief_opens_a_run_that_carries_an_empty_revision(tmp_workspace):
    """A missing brief is a workspace finding, not a reason to refuse to open: the marker and the
    three lines come first, and the finding prints after them, so the run closes `blocked` with a
    record instead of leaving nothing behind. Exit 1, not 2 — 2 is reserved for a workspace the
    script cannot write into at all, and a caller that read `!= 0` could not tell the two apart.
    """
    (tmp_workspace / "preferences.md").unlink()
    r = run_script(OPEN_RUN, tmp_workspace)
    assert r.returncode == 1, r.stdout + r.stderr
    out = parsed_output(r)
    assert out["brief_revision"] == ""
    assert (tmp_workspace / "runs" / (".started-" + out["run_id"])).exists()
    assert "preferences.md" in (r.stdout + r.stderr)


def test_a_workspace_with_no_brief_reports_the_missing_brief_once(tmp_workspace):
    """`validate-workspace.sh` is the only reporter of the missing brief. `open-run.sh` printing the
    same line too would report one finding on two lines, and a caller counting them would count it
    twice."""
    (tmp_workspace / "preferences.md").unlink()
    r = run_script(OPEN_RUN, tmp_workspace)
    named = [l for l in r.stdout.splitlines() if "INVALID preferences.md" in l]
    assert named == ["INVALID preferences.md missing-file"], r.stdout


def path_without_a_digest_command(tmp_path):
    """A PATH holding every command `open-run.sh` and `validate-workspace.sh` run, minus the two
    that can take a SHA-256. A host carrying neither is the case where the revision comes back empty
    for a `preferences.md` that is present and readable.

    The twelve were measured by dropping one at a time and comparing the whole run against the full
    list: each of these changes what the run prints or its status, and `wc` and `cat` change
    nothing. Four of them need a workspace of the right shape before they run at all — `grep`,
    `head` and `cut` read a run record's fields, all three in `validate-workspace.sh`'s
    `json_str`, and `sort` prints the findings — so on a clean workspace with no run record
    neither script runs any of the four. That is why the case below writes a record, and a broken
    one, rather than reusing `tmp_workspace` as it comes.

    The twelve cover the paths these cases drive, which is `open-run.sh` and the validator without
    `--post-close`. `--post-close` on a workspace holding that run's record reaches `sed`, `touch`
    and `tr` as well; no case here drives it, and no case here should be read as having measured
    those three.

    `sh` is on the list but no case here proves it. Dropping it raises `FileNotFoundError` from
    `run_script` instead, because `subprocess.run(["sh", …], env=e)` resolves the interpreter
    through this same PATH, so the harness fails before the script runs. Run with an absolute
    interpreter and no `sh` on PATH, the script reports `sh: command not found` at the line that
    runs `validate-workspace.sh`, which is what puts `sh` on the list.
    """
    d = tmp_path / "no-digest-bin"
    d.mkdir(exist_ok=True)
    for name in ("awk", "cut", "date", "dirname", "grep", "head", "mkdir", "mktemp", "rm", "sh",
                 "sort", "tr"):
        found = shutil.which(name)
        if found and not (d / name).exists():
            (d / name).symlink_to(found)
    return {"PATH": str(d)}


def test_the_restricted_path_reads_a_run_record_the_way_the_full_path_does(tmp_workspace, tmp_path):
    """`path_without_a_digest_command` is sound only if a way to take a digest is the one thing
    missing from it. The case below runs on `tmp_workspace`, which deliberately holds no run
    record, so it never reaches the `grep | head | cut` that reads one — a PATH with no `head`
    would pass it and then hand the next caller invented `missing-key` findings for every record in
    the workspace. So: same workspace, one record on it, and the validator must print exactly what
    it prints on the full PATH and exit the same way, whatever its rules are that day. The second
    record is missing `close_state`, and the finding naming it is what shows the record is being
    read at all rather than skipped by both."""
    record = tmp_workspace / "runs" / (RID + ".json")
    whole = {"run_id": RID, "trigger": "manual", "close_state": "complete",
             "started_at": "2026-08-05T16:47:00Z", "completed_at": "2026-08-05T16:49:00Z"}
    broken = {k: v for k, v in whole.items() if k != "close_state"}
    restricted = path_without_a_digest_command(tmp_path)
    for body in (whole, broken):
        record.write_text(json.dumps(body), encoding="utf-8")
        full = run_script(VALIDATE, tmp_workspace)
        cut_down = run_script(VALIDATE, tmp_workspace, env=restricted)
        # stderr is compared too, and it is what catches the commands whose absence changes no
        # finding: with no `awk` the config and the brief are never read, and the findings that go
        # missing are the ones a valid workspace would not have printed anyway.
        assert (cut_down.returncode, cut_down.stdout, cut_down.stderr) == \
               (full.returncode, full.stdout, full.stderr), \
            "restricted PATH: %r %r\nfull PATH: %r %r" % (cut_down.stdout, cut_down.stderr,
                                                          full.stdout, full.stderr)
    assert "runs/%s.json missing-key close_state" % RID in full.stdout


def test_a_present_brief_with_no_way_to_digest_it_is_not_called_missing(tmp_workspace, tmp_path):
    """An empty revision has two causes and they are different problems. Here `preferences.md` is on
    disk and readable and the workspace passes every rule, so `INVALID preferences.md missing-file`
    would name a file that is there as absent — which is what printing that line off an empty
    revision, rather than off the file check, would do. The failure is this script's, so it goes to
    stderr and the run still opens."""
    r = run_script(OPEN_RUN, tmp_workspace, env=path_without_a_digest_command(tmp_path))
    assert r.returncode == 1, r.stdout + r.stderr
    out = parsed_output(r)
    assert out["brief_revision"] == ""
    assert RUN_ID_RE.match(out["run_id"])
    assert (tmp_workspace / "preferences.md").exists()
    assert "INVALID" not in r.stdout
    # One line, and it is this one. A second line would be a `command not found` from something
    # the restricted PATH is missing, which would otherwise read as a run that did what it says.
    assert len(r.stderr.splitlines()) == 1, r.stderr
    assert "could not take the revision" in r.stderr


@pytest.mark.skipif(not shutil.which("dash"), reason="dash is not installed here")
def test_opening_a_run_runs_under_dash(tmp_workspace):
    """One of the four shipped scripts that run another shipped script rather than an awk program —
    `command grep -rn '^[^#]*sh "' skills/*/scripts/*.sh` returns four lines, one each in
    `resolve-run.sh`, `close-run.sh`, `open-run.sh` and `validate-workspace.sh` — so it is run end
    to end under strict dash:
    `${1:?}`, `command -v`, the `printf ''` that writes the marker and the `sh` call on
    `validate-workspace.sh` are none of them exercised by `dash -n`. `close-run.sh` gets the same
    treatment at `test_closing_and_clearing_a_run_run_under_dash`, `validate-workspace.sh` at
    `test_the_count_and_timestamp_checks_run_under_every_shell` in
    `tests/test_validate_workspace.py`, which is the case that drives its `sh` call, and
    `resolve-run.sh` at `test_resolving_a_run_runs_under_dash`."""
    r = run_script(OPEN_RUN, tmp_workspace, shell="dash")
    assert r.returncode == 0, r.stdout + r.stderr
    out = parsed_output(r)
    assert (tmp_workspace / "runs" / (".started-" + out["run_id"])).exists()
    assert len(out["brief_revision"]) == 12


# ------------------------------------------------------- close-run.sh and clear-run.sh

def opened(ws):
    return parsed_output(run_script(OPEN_RUN, ws))


def close(ws, run_id, close_state="complete", env=None, shell="sh", **kw):
    args = [ws, run_id, "--trigger", "manual", "--close-state", close_state]
    for k, v in kw.items():
        args += ["--" + k.replace("_", "-"), v]
    return run_script(CLOSE_RUN, *args, env=env, shell=shell)


def record_of(ws, run_id):
    return json.loads((ws / "runs" / (run_id + ".json")).read_text())


# The record's field names, written out here rather than read off either side. `set(record) ==
# set(template)` on its own is two outputs compared with nothing behind them: drop `filtered_out`
# from `close-run.sh` and from the template together and it still passes. This list is the third
# term, and the field count is stated so a field added to it without being added to the record fails
# rather than passing quietly.
RECORD_FIELDS = {
    "run_id", "trigger", "scheduler_id", "brief_revision", "close_state", "run_health",
    "degraded_reasons", "sources", "queries", "postings_surfaced", "postings_reviewed",
    "postings_unreviewed", "postings_detail_read", "matches", "filtered_out",
    "duplicates_of_another", "by_source", "agent_data_usage", "started_at", "completed_at",
}

# One count set the tests below hand to the reader, in the order and spelling `run-counts.sh`
# prints. Every numeric value is different from every other, so a field that reads the wrong key
# lands on a number that cannot be the right one. The 19 numbers are 1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
# 11, 12, 13, 14, 21, 26, 29, 33, 40 — the distinctness is asserted below rather than left to be
# read off.
#
# Every relation the record asserts holds: 2 + 4 + 5 + 12 + 10 = 33 reviewed, 33 + 7 = 40 surfaced,
# 29 + 11 = 40 by source, 6 + 14 + 1 = 21 metered. `rows_new_total` is the one number deliberately
# off what a real log would carry — a real log holds it equal to `postings_surfaced`, and that is
# exactly why nothing could separate the two if it were written that way here.
#
# `duplicates_of_another` is 10 rather than 0 for the same reason no other key is 0: an absent key
# reaches `printf "%d"` as 0, so a record that never read this key would carry the right number and
# the cases below would pass over a reader that dropped it.
#
# `judgments_claiming_detail_read` 13 sits above `postings_detail_read` 9, so this set carries a
# posting-read gap and `close-run.sh` writes a reason for it. That is forced rather than picked: 1
# through 9 are all taken already, so no free number sits at or below 9, and 13 is the smallest one
# left. It costs the cases below nothing: measured 2026-08-12, the six `close` calls below that hand
# this set to `close-run.sh` through `awk_shim` all pass `--close-state interrupted`, which is
# degraded whatever the counts say, and four of the six exit 1 before `run_health` is worked out at
# all. The set already fails two other health terms the same way, carrying `postings_unreviewed` 7
# and `searches_never_succeeded` 8.
WHOLE_COUNT_SET = (
    "postings_surfaced=40\n"
    "postings_reviewed=33\n"
    "postings_unreviewed=7\n"
    "postings_detail_read=9\n"
    "judgments_claiming_detail_read=13\n"
    "match_strong=2\n"
    "match_moderate=4\n"
    "match_weak=5\n"
    "filtered_out=12\n"
    "duplicates_of_another=10\n"
    "by_source_linkedin=29\n"
    "by_source_ashby=11\n"
    "calls_searches=6\n"
    "calls_detail_reads=14\n"
    "calls_other=1\n"
    "calls_total_metered=21\n"
    "calls_failed=3\n"
    "searches_never_succeeded=8\n"
    "searches_never_succeeded_ids=ashby:q1,ashby:q2,ashby:q3,ashby:q4,"
    "linkedin:q1,linkedin:q2,linkedin:q3,linkedin:q4\n"
    "rows_new_total=26\n"
)


def test_the_hand_written_count_set_gives_every_key_a_different_number():
    """`WHOLE_COUNT_SET` is what separates one count from another in the cases below, and it does
    that only while no two keys carry the same number. It has been wrong once: `postings_surfaced`
    and `postings_reviewed` were both 11 and `match_strong` and `calls_other` were both 1, so a
    record reading `calls_other` into `matches.strong` passed all 352 tests. This is the assertion
    that would have failed then.
    """
    values = [l.split("=", 1) for l in WHOLE_COUNT_SET.splitlines()]
    numbers = [v for _, v in values if v.isdigit()]
    assert len(numbers) == 19, values
    assert len(set(numbers)) == 19, sorted(numbers)
    c = dict(values)
    n = {k: int(v) for k, v in c.items() if v.isdigit()}
    # The posting-read gap this set carries, pinned so it stays a decision and not an accident: the
    # cases fed this set close `interrupted` or exit 1, so none of them turns on it either way.
    assert n["judgments_claiming_detail_read"] > n["postings_detail_read"]
    assert n["match_strong"] + n["match_moderate"] + n["match_weak"] + n["filtered_out"] \
        + n["duplicates_of_another"] == n["postings_reviewed"]
    assert n["postings_reviewed"] + n["postings_unreviewed"] == n["postings_surfaced"]
    assert n["by_source_linkedin"] + n["by_source_ashby"] == n["postings_surfaced"]
    assert n["calls_searches"] + n["calls_detail_reads"] + n["calls_other"] \
        == n["calls_total_metered"]
    assert len(c["searches_never_succeeded_ids"].split(",")) == n["searches_never_succeeded"]


def test_the_record_carries_the_counts_from_the_log(tmp_workspace):
    """Every number in the record comes off `jobs.jsonl` rather than from whoever is closing the
    run. One search, every row judged not relevant, so surfaced, reviewed and filtered_out are all
    the fixture's row count while unreviewed, the three bands and the detail read are all 0 and the
    metered total is the one search.

    Three of the record's fields carry the same number here and four more carry 0, so this case
    cannot tell one count from another — `test_the_record_reads_each_count_into_the_field_that_
    names_it` is the one that does. The row count is read off the fixture rather than written as a
    literal, so a re-captured fixture with a different number of rows moves the expectation with it.
    """
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.linkedin.json",
               "--route", "search-jobs", "--query-id", "q")
    n = len(api_rows("search.linkedin.json"))
    surfaced = [e for e in lines(jobs) if e["event"] == "surfaced"]
    assert len(surfaced) == n      # the log really holds them, before anything is closed
    for row in surfaced:
        run_script(JUDGE, jobs, "--run-id", o["run_id"], "--source", row["source"],
                   "--source-id", row["source_id"], "--detail-read", "false",
                   "--relevant", "false", "--reasoning", "Outside the brief.")
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["postings_surfaced"] == n
    assert rec["postings_reviewed"] == n
    assert rec["postings_unreviewed"] == 0
    assert rec["postings_detail_read"] == 0
    assert rec["filtered_out"] == n
    assert rec["matches"] == {"strong": 0, "moderate": 0, "weak": 0}
    assert rec["by_source"] == {"linkedin": n}
    assert rec["agent_data_usage"] == {"searches": 1, "detail_reads": 0, "other": 0,
                                       "total_metered": 1}
    assert rec["close_state"] == "complete"
    assert rec["trigger"] == "manual"


def test_the_record_reads_each_count_into_the_field_that_names_it(tmp_workspace, tmp_path):
    """The case above cannot separate one count from another: with every row judged the same way,
    surfaced, reviewed and filtered_out all carry the fixture's row count and four other fields
    carry 0, so a record that read `postings_reviewed` into `postings_surfaced` would pass it. This
    one hands the reader `WHOLE_COUNT_SET`, in which no two keys carry the same number, so each has
    exactly one field it can legitimately land in.

    The numbers come from the shim, so they are the test's own and not `run-counts.sh`'s. The close
    is `interrupted` rather than `complete`, so `postings_unreviewed` can carry a number of its own
    instead of the 0 a complete close requires.
    """
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    r = close(tmp_workspace, o["run_id"], "interrupted",
              env=awk_shim(tmp_path, "run-counts.awk", WHOLE_COUNT_SET, status=0, stderr=""))
    assert r.returncode == 0, r.stdout + r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["postings_surfaced"] == 40
    assert rec["postings_reviewed"] == 33
    assert rec["postings_unreviewed"] == 7
    assert rec["postings_detail_read"] == 9
    assert rec["matches"] == {"strong": 2, "moderate": 4, "weak": 5}
    assert rec["filtered_out"] == 12
    assert rec["duplicates_of_another"] == 10
    assert rec["by_source"] == {"linkedin": 29, "ashby": 11}
    assert rec["agent_data_usage"] == {"searches": 6, "detail_reads": 14, "other": 1,
                                       "total_metered": 21}


@pytest.mark.parametrize("absent", ["postings_unreviewed", "searches_never_succeeded",
                                    "judgments_claiming_detail_read",
                                    "calls_detail_reads", "match_moderate",
                                    "duplicates_of_another"])
def test_a_count_the_record_needs_but_never_arrived_stops_the_close(tmp_workspace, tmp_path,
                                                                    absent):
    """A reader that exits 0 with a key left out is the one case the exit status cannot report. An
    absent key reaches `printf "%d"` as 0 and `[ "$x" -eq 0 ]` as an unset variable, so the record
    would carry a number no log supports and `run_health` would come out healthy off a count that
    was never taken — which is the failure `searches_never_succeeded` was added to catch.

    Six keys rather than one: three the shell branches on and three only the record reads.

    The close is `interrupted` here and in the two cases below it, so the only thing in the script
    that can produce exit 1 is the check under test. `WHOLE_COUNT_SET` carries a non-zero
    `postings_unreviewed`, and over a `complete` close the refusal for that fires too — which passed
    these cases for the wrong reason and let two mutations through.
    """
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    without = "".join(l + "\n" for l in WHOLE_COUNT_SET.splitlines()
                      if not l.startswith(absent + "="))
    assert len(without.splitlines()) == len(WHOLE_COUNT_SET.splitlines()) - 1
    r = close(tmp_workspace, o["run_id"], "interrupted",
              env=awk_shim(tmp_path, "run-counts.awk", without, status=0, stderr=""))
    assert r.returncode == 1, r.stdout + r.stderr
    assert absent in r.stderr, r.stderr
    assert not (tmp_workspace / "runs" / (o["run_id"] + ".json")).exists()
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()


@pytest.mark.parametrize("key", ["postings_unreviewed", "searches_never_succeeded",
                                 "postings_detail_read", "judgments_claiming_detail_read"])
def test_a_count_the_close_branches_on_that_is_not_a_number_stops_the_close(tmp_workspace,
                                                                           tmp_path, key):
    """`[ "$x" -ne 0 ]` on a value that is not a number writes a diagnostic and exits non-zero, so
    the surrounding `if` runs its else branch — measured with x=many: `integer expression expected`
    under sh and bash, `Illegal number` under dash, else branch in all three. An unreadable
    `postings_unreviewed` would then read as no posting left unjudged and let a `complete` close
    through, and an unreadable `searches_never_succeeded` as no lost search — both of them closing a
    run healthy off a count nobody could read.

    `[ "$claimed" -gt "$detailread" ]` fails the same way, and the else branch there is `readgap`
    staying `no`: a run whose judgments claim more reads than the log has stored postings would
    close healthy because one of the two counts could not be read.
    """
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    broken = "".join((key + "=many\n") if l.startswith(key + "=") else l + "\n"
                     for l in WHOLE_COUNT_SET.splitlines())
    assert broken.count("=many") == 1
    r = close(tmp_workspace, o["run_id"], "interrupted",
              env=awk_shim(tmp_path, "run-counts.awk", broken, status=0, stderr=""))
    assert r.returncode == 1, r.stdout + r.stderr
    assert key in r.stderr, r.stderr
    assert not (tmp_workspace / "runs" / (o["run_id"] + ".json")).exists()
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()


# The first two lines of WHOLE_COUNT_SET and nothing after them, which is what an awk that stopped
# partway through its END block leaves on stdout.
HALF_A_COUNT_SET = "".join(l + "\n" for l in WHOLE_COUNT_SET.splitlines()[:2])
THE_FINDING = "INVALID relevant-row-without-a-band=1\n"


@pytest.mark.parametrize("status,spill", [
    (2, HALF_A_COUNT_SET),
    (1, HALF_A_COUNT_SET),
    (2, WHOLE_COUNT_SET),
    (1, WHOLE_COUNT_SET),
    (2, WHOLE_COUNT_SET + THE_FINDING),
], ids=["half-set-at-2", "half-set-at-1", "whole-set-at-2", "whole-set-at-1",
        "the-findings-own-shape-at-2"])
def test_counts_that_could_not_be_worked_out_stop_the_close(tmp_workspace, tmp_path, status, spill):
    """`run-counts.sh` runs its awk with `exec`, so an awk that stops partway leaves part of the key
    set on stdout and hands its own status back. Reading keys off that would put numbers in the
    record that no log supports, so nothing is written and the marker stays where a retry can find
    it.

    Only one shape closes the run: status 1 with the finding named on the last line, which is the
    case below. The other four are here because each would be let through by a plausible reading of
    the status alone. A whole count set at status 1 with nothing named is the reader failing after
    it had printed everything — accepting every status 1 takes it. A whole count set at status 2 is
    the same thing one status over — accepting every non-zero status takes it. And the finding's own
    text at status 2 is the content being trusted rather than the status.

    `interrupted`, so the status check is the only thing here that can produce exit 1. Over a
    `complete` close the refusal for `WHOLE_COUNT_SET`'s non-zero `postings_unreviewed` fires as
    well, and the two whole-set cases then passed against a script that accepted every status 1 —
    measured, and the reason this line says `interrupted` rather than taking the default.
    """
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    r = close(tmp_workspace, o["run_id"], "interrupted",
              env=awk_shim(tmp_path, "run-counts.awk", spill, status=status))
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert not (tmp_workspace / "runs" / (o["run_id"] + ".json")).exists()
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()


@pytest.mark.parametrize("spill,status", [
    ('{\n  "run_id": "x",\n  "trigger": "man', 2),
    ("", 0),
], ids=["stopped-partway", "printed-nothing-and-exited-clean"])
def test_a_record_that_did_not_come_out_whole_is_not_written(tmp_workspace, tmp_path, spill,
                                                             status):
    """Two ways the record builder can fail, and each is caught by a different half of the check.

    An awk that dies after printing leaves a record that stops mid-field: testing the file for
    content alone passes it, because the file is not empty. An awk that exits 0 having printed
    nothing leaves an empty file: testing the status alone passes that one. Either way, what lands
    at the real path would be worse than nothing — `validate-workspace.sh` reads
    `runs/<run_id>.json` and the home view lists it as a run that happened. The marker and the
    scratch are left where a retry can find them, and the temporary file is removed.

    The shim keys on `CR_COUNTS`, which appears in the record builder's program text and nowhere in
    `run-counts.sh`'s arguments, so the counts are read for real and only the record builder fails.
    """
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    r = close(tmp_workspace, o["run_id"],
              env=awk_shim(tmp_path, "CR_COUNTS", spill, status=status, stderr=""))
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert not (tmp_workspace / "runs" / (o["run_id"] + ".json")).exists()
    assert [p.name for p in (tmp_workspace / "runs").glob("*.tmp")] == []
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()


def test_a_lost_search_is_named_whole(tmp_workspace):
    """`searches_never_succeeded_ids` carries `<source>:<query_id>` pairs, and a query id is
    model-supplied: `record-api-response.sh` refuses a comma and a colon in one, and takes an `=`.
    Cutting the value at the first `=` names a query the operator cannot find — `ashby:role=staff`
    arrives as `ashby:role` — and that name is the whole point of the line.

    The log is built by the writer rather than by hand, so the case is one a real run reaches:
    measured on 2026-08-06, three failed attempts written this way give
    `searches_never_succeeded_ids=ashby:role=staff`.
    """
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    for _ in range(3):
        run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "detail.error.json",
                   "--route", "search-jobs", "--query-id", "role=staff", "--source", "ashby")
    calls = [e for e in lines(jobs) if e["event"] == "call"]
    assert len(calls) == 3 and all(e["ok"] is False for e in calls), calls
    assert calls[0]["query_id"] == "role=staff"
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stderr
    assert record_of(tmp_workspace, o["run_id"])["run_health"] == "degraded"
    assert "ashby:role=staff" in r.stderr, r.stderr


def test_a_relevant_row_with_no_band_closes_the_run_and_degrades_it(tmp_workspace):
    """`run-counts.sh` exits 1 for a finding as well as for a failure: a relevant row carrying no
    band makes it print `INVALID relevant-row-without-a-band=1` after every normal count. Measured
    on 2026-08-06 against the four-line log this case writes — seventeen count lines on stdout,
    then the INVALID line, status 1, with `postings_reviewed=2` and `match_strong=1` among them.

    Treating that as a failure would leave the run unclosable: no record, the marker still on disk,
    which is the state this work exists to remove. So the record is written — and the run is
    degraded, because such a row is counted in `postings_reviewed` and in neither `matches` nor
    `filtered_out`, so a healthy record would be one that does not add up. This case
    checks that arithmetic directly: the two hand-written rows give
    `strong + moderate + weak + filtered_out = 1` against `postings_reviewed = 2`, and `run_health`
    is the only field of the record that can say so. stderr would not do — the digest reads
    `run_health` off stdout and never sees stderr at all.
    """
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("".join(
        '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"%s"}\n'
        '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"%s",'
        '"relevant":true,"match":%s}\n' % (o["run_id"], sid, o["run_id"], sid, band)
        for sid, band in (("a", "null"), ("b", '"strong"'))))
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "relevant-row-without-a-band" in r.stderr, r.stderr
    assert "run_health=degraded" in r.stdout.splitlines(), r.stdout
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["run_health"] == "degraded"
    assert rec["close_state"] == "complete"     # the finding does not block the close
    # The counts printed alongside the finding, pinned by hand: two postings, both judged, both
    # relevant, one of them in no band and so in neither `matches` nor `filtered_out`.
    assert rec["postings_surfaced"] == 2
    assert rec["postings_reviewed"] == 2
    assert rec["postings_unreviewed"] == 0
    assert rec["matches"] == {"strong": 1, "moderate": 0, "weak": 0}
    assert rec["filtered_out"] == 0
    m = rec["matches"]
    assert m["strong"] + m["moderate"] + m["weak"] + rec["filtered_out"] < rec["postings_reviewed"]


def test_every_row_banded_over_the_same_shape_of_log_is_healthy(tmp_workspace):
    """The contrast the case above needs. The same two hand-written postings, both relevant, both
    banded: `run-counts.sh` exits 0, nothing is reported, and the run is healthy. Without this, a
    `run_health` that degraded every run would pass the case above.
    """
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("".join(
        '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"%s"}\n'
        '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"%s",'
        '"relevant":true,"match":%s}\n' % (o["run_id"], sid, o["run_id"], sid, band)
        for sid, band in (("a", '"weak"'), ("b", '"strong"'))))
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "relevant-row-without-a-band" not in r.stderr, r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["run_health"] == "healthy"
    # Every term pinned by hand off the four lines above — two postings, both judged, both relevant,
    # one weak and one strong, so none filtered out — before the sum is asserted. Without the three
    # pins the sum holds for any record whose fields are all wrong together.
    assert rec["matches"] == {"strong": 1, "moderate": 0, "weak": 1}
    assert rec["filtered_out"] == 0
    assert rec["postings_reviewed"] == 2
    m = rec["matches"]
    assert m["strong"] + m["moderate"] + m["weak"] + rec["filtered_out"] == rec["postings_reviewed"]


def test_close_prints_run_health_for_the_digest(tmp_workspace):
    """The digest's header carries `run_health`, and it reads it off this line rather than off the
    record it may not have opened. So the line is on stdout, in the `key=value` shape the other
    scripts print, and it says the same thing the record does.

    Nothing went wrong in this run, so nothing on stderr says anything did. A line reporting that no
    search was lost is a report about an event that did not happen, and the operator reading stderr
    after a clean run should find it empty of findings.
    """
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stderr
    assert "run_health=healthy" in r.stdout.splitlines(), r.stdout
    assert "run_health=degraded" not in r.stdout
    assert parsed_output(r).get("run_health") == "healthy"
    assert record_of(tmp_workspace, o["run_id"])["run_health"] == "healthy"
    assert "never returned" not in r.stderr, r.stderr
    assert "INVALID" not in r.stderr, r.stderr
    # The record is moved into place, not copied: a leftover `.tmp` beside it is a second file with
    # a run record in it, and `validate-workspace.sh` would read neither as the other.
    assert [p.name for p in (tmp_workspace / "runs").glob("*.tmp")] == []


@pytest.mark.parametrize("state", ["blocked", "interrupted"])
def test_a_close_that_is_not_complete_is_degraded_however_clean_the_log_is(tmp_workspace, state):
    """`run_health` healthy needs all three of complete, nothing unjudged, and no search lost. The
    other cases here reach `degraded` through a log with something wrong in it, so a `run_health`
    that ignored `close_state` altogether would pass every one of them. This log has nothing wrong
    in it at all: the run still did not finish, and the record says so.
    """
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    r = close(tmp_workspace, o["run_id"], state)
    assert r.returncode == 0, r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["postings_unreviewed"] == 0
    assert rec["postings_surfaced"] == 0
    assert rec["close_state"] == state
    assert rec["run_health"] == "degraded"
    assert "run_health=degraded" in r.stdout.splitlines(), r.stdout


def test_completed_at_is_later_than_started_at_and_not_later_than_the_file(tmp_workspace, tmp_path):
    """`completed_at` is a clock read at close, and `started_at` is the instant `open-run.sh` minted
    the run id. The first half checks the stamp against the file's own modification time, which
    nothing in the script can influence.

    The second half pins both to the second. Two runs a fraction of a second apart share a
    `started_at` and a `completed_at` under a real clock, so a `completed_at` copied off
    `started_at` passes the first half every time. Under a `date` that never answers the same second
    twice, `open-run.sh` takes 15:04:01Z and `close-run.sh` takes 15:04:02Z, and both numbers are
    written here rather than read off either script.
    """
    import datetime
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    close(tmp_workspace, o["run_id"])
    path = tmp_workspace / "runs" / (o["run_id"] + ".json")
    rec = json.loads(path.read_text())
    assert UTC_TS_RE.match(rec["completed_at"])
    assert rec["started_at"] == o["started_at"]
    assert rec["completed_at"] >= rec["started_at"]
    stated = datetime.datetime.strptime(rec["completed_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc)
    written = datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc)
    assert stated <= written + datetime.timedelta(seconds=2)

    # The first run is cleared before the second opens, because `open-run.sh` refuses to open while a
    # marker is on disk and `close-run.sh` leaves the marker for `clear-run.sh` to remove.
    cleared = run_script(CLEAR_RUN, tmp_workspace, o["run_id"])
    assert cleared.returncode == 0, cleared.stdout + cleared.stderr

    calls, env = date_shim(tmp_path)
    o2 = parsed_output(run_script(OPEN_RUN, tmp_workspace, env=env))
    assert o2["run_id"] == "2026-07-30T15-04-01Z"
    r2 = close(tmp_workspace, o2["run_id"], env=env)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert calls.read_text() == "xx", "one clock read opening the run and one closing it"
    rec2 = record_of(tmp_workspace, o2["run_id"])
    assert rec2["started_at"] == "2026-07-30T15:04:01Z"
    assert rec2["completed_at"] == "2026-07-30T15:04:02Z"


def test_a_complete_close_over_unreviewed_postings_is_refused(tmp_workspace):
    """A run that did not finish must not read as one that did. Nothing is written, so the marker
    and the scratch are still there to judge the rest from and close again.
    """
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.linkedin.json",
               "--route", "search-jobs", "--query-id", "q")
    unjudged = len([e for e in lines(jobs) if e["event"] == "surfaced"])
    assert unjudged > 0, "the search has to have surfaced something for this case to mean anything"
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 1
    assert str(unjudged) in r.stderr, r.stderr  # the number of postings, named
    assert r.stdout == "", r.stdout             # no run_health line for a digest to carry
    assert not (tmp_workspace / "runs" / (o["run_id"] + ".json")).exists()
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()


def test_the_same_run_closes_interrupted_and_records_run_health_degraded(tmp_workspace):
    """The same log the case above refuses closes as `interrupted`, so the refusal is about the
    close state contradicting the log rather than about the log being unclosable.
    """
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.linkedin.json",
               "--route", "search-jobs", "--query-id", "q")
    unjudged = len([e for e in lines(jobs) if e["event"] == "surfaced"])
    assert unjudged == len(api_rows("search.linkedin.json"))
    r = close(tmp_workspace, o["run_id"], "interrupted")
    assert r.returncode == 0, r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["close_state"] == "interrupted"
    assert rec["run_health"] == "degraded"
    assert rec["postings_unreviewed"] == unjudged
    assert rec["postings_reviewed"] == 0
    assert "run_health=degraded" in r.stdout.splitlines(), r.stdout


def test_a_failed_detail_read_does_not_degrade_a_finished_run(tmp_workspace):
    """fault-503: every posting judged from its summary row, so the pass finished.

    A failed detail read is not a lost search — the posting was surfaced and judged, and the failure
    is visible in `agent_data_usage` and named in the digest's footnotes. A `run_health` keyed on
    whether any call failed would call this run degraded, so the failed call is read out of the log
    first: it is really there, and the run is still healthy.
    """
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.ashby.json",
               "--route", "search-jobs", "--query-id", "q")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "detail.error.json",
               "--route", "get-posting")
    failed = [e for e in lines(jobs) if e["event"] == "call" and e["ok"] is False]
    assert len(failed) == 1 and failed[0]["route"] == "get-posting", failed
    surfaced = [e for e in lines(jobs) if e["event"] == "surfaced"]
    assert len(surfaced) == len(api_rows("search.ashby.json"))
    for row in surfaced:
        run_script(JUDGE, jobs, "--run-id", o["run_id"], "--source", row["source"],
                   "--source-id", row["source_id"], "--detail-read", "false",
                   "--relevant", "false", "--reasoning", "Judged from the row.")
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["run_health"] == "healthy"
    assert rec["agent_data_usage"]["detail_reads"] == 1
    assert rec["postings_surfaced"] == len(surfaced)
    assert rec["postings_unreviewed"] == 0
    assert rec["postings_detail_read"] == 0      # the read failed, so no posting was stored in full


def write_event_log(path, rows):
    """Write `rows` as one JSON object per line, in the compact form the log is written in."""
    path.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows),
                    encoding="utf-8")


def test_close_run_degrades_and_records_the_reason_on_a_posting_read_gap(tmp_workspace):
    """Two postings, both judged with `detail_read` true, and the log holds a `detail` event for
    only one of them. `postings_detail_read` comes out 1 and `judgments_claiming_detail_read` 2, so
    one posting was judged as if its text had been read with no call that read it. The run closes
    degraded, and the record carries the reason rather than only stderr: stderr is gone by the time
    anyone asks why a run was degraded.

    The log is written by hand because `record-judgment.sh` refuses `--detail-read true` for a
    posting with no `detail` event in the log — `grep -n 'no detail event for'
    skills/job-search-run/scripts/record-judgment.sh` finds the refusal — so the writer cannot
    produce this gap any more. Logs written before that check still hold it, and this case is what
    closing one of them does.
    """
    o = opened(tmp_workspace)
    rid = o["run_id"]
    write_event_log(tmp_workspace / "jobs.jsonl", [
        {"event": "surfaced", "run_id": rid, "source": "linkedin", "source_id": "1"},
        {"event": "detail", "run_id": rid, "source": "linkedin", "source_id": "1"},
        {"event": "evaluated", "run_id": rid, "source": "linkedin", "source_id": "1",
         "detail_read": True, "relevant": True, "match": "strong"},
        {"event": "surfaced", "run_id": rid, "source": "linkedin", "source_id": "2"},
        {"event": "evaluated", "run_id": rid, "source": "linkedin", "source_id": "2",
         "detail_read": True, "relevant": True, "match": "weak"},
    ])
    r = close(tmp_workspace, rid)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "run_health=degraded" in r.stdout.splitlines(), r.stdout
    assert "billable call" in r.stderr, r.stderr
    rec = record_of(tmp_workspace, rid)
    assert rec["run_health"] == "degraded"
    assert rec["close_state"] == "complete"      # the gap does not block the close
    assert rec["postings_detail_read"] == 1
    assert isinstance(rec["degraded_reasons"], list)
    assert len(rec["degraded_reasons"]) == 1     # one failed check, one reason
    assert "fetch-posting.sh" in rec["degraded_reasons"][0]
    # The same words on stderr and in the record, so a reader of either is reading the same reason.
    assert rec["degraded_reasons"][0] in r.stderr, r.stderr


def test_close_run_stays_healthy_and_records_no_reasons_when_the_counts_agree(tmp_workspace):
    """The contrast the case above needs. One posting, a `detail` event for it, and a judgment
    claiming the read: the claim count and the stored-posting count are both 1 and nothing else in
    the log is wrong, so the run is healthy. Without this, a `run_health` that degraded on any
    judgment claiming a read at all would pass the case above.

    `degraded_reasons` is `[]` rather than absent, so a reader can read the field without first
    testing whether the key is there.
    """
    o = opened(tmp_workspace)
    rid = o["run_id"]
    write_event_log(tmp_workspace / "jobs.jsonl", [
        {"event": "surfaced", "run_id": rid, "source": "linkedin", "source_id": "1"},
        {"event": "detail", "run_id": rid, "source": "linkedin", "source_id": "1"},
        {"event": "evaluated", "run_id": rid, "source": "linkedin", "source_id": "1",
         "detail_read": True, "relevant": True, "match": "strong"},
    ])
    r = close(tmp_workspace, rid)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "run_health=healthy" in r.stdout.splitlines(), r.stdout
    assert "billable call" not in r.stderr, r.stderr
    rec = record_of(tmp_workspace, rid)
    assert rec["run_health"] == "healthy"
    assert rec["postings_detail_read"] == 1
    assert rec["degraded_reasons"] == []


def test_a_stored_posting_the_judgment_says_it_did_not_read_is_not_a_gap(tmp_workspace):
    """The other direction across the same two counts. The posting was read and stored and the
    judgment that followed says the text was not used, so `postings_detail_read` is 1 against a
    claim count of 0. Nothing is missing from the run: the call was made and it is in the counts.

    Only a claim count above the stored count is the gap. A check written as `-ne` would degrade
    this run, so this is the case that holds the comparison to one direction.
    """
    o = opened(tmp_workspace)
    rid = o["run_id"]
    write_event_log(tmp_workspace / "jobs.jsonl", [
        {"event": "surfaced", "run_id": rid, "source": "linkedin", "source_id": "1"},
        {"event": "detail", "run_id": rid, "source": "linkedin", "source_id": "1"},
        {"event": "evaluated", "run_id": rid, "source": "linkedin", "source_id": "1",
         "detail_read": False, "relevant": False},
    ])
    r = close(tmp_workspace, rid)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "run_health=healthy" in r.stdout.splitlines(), r.stdout
    rec = record_of(tmp_workspace, rid)
    assert rec["postings_detail_read"] == 1
    assert rec["filtered_out"] == 1               # the judgment really was recorded
    assert rec["run_health"] == "healthy"
    assert rec["degraded_reasons"] == []


def failed_search_events(run_id, oks):
    """One search group — one source, one query id — as a `call` event per attempt."""
    return "".join(
        '{"event":"call","run_id":"%s","route":"search-jobs","source":"ashby","query_id":"q2",'
        '"ok":%s,"rows_returned":0,"rows_new":0,"retryable":true}\n' % (run_id, ok)
        for ok in oks)


def test_a_search_that_never_returned_degrades_the_run_without_blocking_the_close(tmp_workspace):
    """Three attempts at one search, none of which answered: its postings were never surfaced, so
    nothing else in the run would notice they are missing. That degrades the run and does not block
    the close — the run finished the work it could reach.

    The second half is the same three attempts with the last one answering. That is a retry
    sequence, not a lost search, and it must not degrade the run: without it, `run_health` keyed on
    any failed call at all would pass the first half.
    """
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text(failed_search_events(o["run_id"], ["false", "false", "false"]))
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["close_state"] == "complete"
    assert rec["run_health"] == "degraded"
    assert rec["agent_data_usage"]["searches"] == 3
    assert rec["postings_surfaced"] == 0
    assert "ashby:q2" in r.stderr, r.stderr

    retried = "2026-07-30T09-00-00Z"
    jobs.write_text(jobs.read_text()
                    + failed_search_events(retried, ["false", "false", "true"]))
    r2 = close(tmp_workspace, retried)
    assert r2.returncode == 0, r2.stderr
    rec2 = record_of(tmp_workspace, retried)
    assert rec2["run_health"] == "healthy"
    assert rec2["agent_data_usage"]["searches"] == 3
    assert "ashby:q2" not in r2.stderr, r2.stderr


def test_sources_and_queries_land_as_json_arrays(tmp_workspace):
    """`--sources` and `--queries` are comma-separated on the way in and JSON arrays in the record,
    which is what the home view reads. A record built by pasting the flag's text between brackets
    would give one entry holding a comma.
    """
    rid = "2026-07-30T15-04-02Z"
    (tmp_workspace / "jobs.jsonl").write_text("")
    r = run_script(CLOSE_RUN, tmp_workspace, rid, "--trigger", "scheduled",
                   "--scheduler-id", "com.job-search.daily", "--close-state", "complete",
                   "--brief-revision", "9f2c41a7be05",
                   "--sources", "linkedin,ashby", "--queries", "ai-eng-remote,ml-platform-sf")
    assert r.returncode == 0, r.stdout + r.stderr
    rec = record_of(tmp_workspace, rid)
    assert rec["sources"] == ["linkedin", "ashby"]
    assert rec["queries"] == ["ai-eng-remote", "ml-platform-sf"]
    assert rec["trigger"] == "scheduled"
    assert rec["scheduler_id"] == "com.job-search.daily"
    assert rec["brief_revision"] == "9f2c41a7be05"
    assert rec["run_id"] == rid


def test_a_quote_in_a_value_is_escaped_rather_than_ending_the_record(tmp_workspace):
    """The double quote is the one character `esc` still handles in this script that the entry
    guard does not refuse — a control character and a backslash are both refused above it, and
    everything `esc` does beyond those three is about control characters. Written raw, it closes the
    JSON string early and nothing downstream can read the record at all, so this is the case that
    proves `esc` is wired in rather than only present.
    """
    rid = "2026-07-30T15-04-02Z"
    (tmp_workspace / "jobs.jsonl").write_text("")
    r = run_script(CLOSE_RUN, tmp_workspace, rid, "--trigger", "manual",
                   "--close-state", "complete", "--sources", 'he said "yes",b',
                   "--scheduler-id", 'a"b')
    assert r.returncode == 0, r.stdout + r.stderr
    text = (tmp_workspace / "runs" / (rid + ".json")).read_text()
    assert '["he said \\"yes\\"", "b"]' in text, text
    rec = json.loads(text)
    assert rec["sources"] == ['he said "yes"', "b"]
    assert rec["scheduler_id"] == 'a"b'


def test_a_run_with_no_log_and_no_flags_closes_with_zeroes_and_nulls(tmp_workspace):
    """A run that opened and recorded nothing still closes, with a record saying so, rather than
    being stuck open. The two optional identifiers are JSON null and not the empty string: `null` is
    what the record's own example carries for a manual run, and a reader testing `scheduler_id` for
    truth would take `""` for a scheduler with a blank name.
    """
    o = opened(tmp_workspace)
    assert not (tmp_workspace / "jobs.jsonl").exists()
    r = close(tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stdout + r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["scheduler_id"] is None
    assert rec["brief_revision"] is None
    assert rec["sources"] == []
    assert rec["queries"] == []
    assert rec["by_source"] == {}
    assert rec["postings_surfaced"] == 0
    assert rec["agent_data_usage"] == {"searches": 0, "detail_reads": 0, "other": 0,
                                       "total_metered": 0}


@pytest.mark.parametrize("bad,says", [
    ("a\vb", "control character"),
    ("a\nb", "control character"),
    ("a\\tb", "backslash"),
], ids=["vertical-tab", "newline", "backslash"])
@pytest.mark.parametrize("flag", ["--scheduler-id", "--brief-revision", "--sources", "--queries"])
def test_an_identifier_the_close_writes_is_refused(tmp_workspace, flag, bad, says):
    """Every value this script writes is an identifier — no free text among them — so each is
    refused rather than escaped, and refused before anything is written. `--trigger` and
    `--close-state` take no check of their own: they are already held to two and three words, and
    `<run_id>` is held to its whole shape by the case below, which is stricter than this.

    An identifier stored escaped is one no `grep -F` lookup will ever match again. The message names
    the flag, because four of this script's values are checked this way and the caller has to know
    which one to fix.
    """
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    r = close(tmp_workspace, o["run_id"], **{flag[2:].replace("-", "_"): bad})
    assert r.returncode == 1, r.stdout + r.stderr
    assert says in r.stderr, r.stderr
    assert flag in r.stderr, r.stderr
    assert sorted(p.name for p in (tmp_workspace / "runs").glob("*.json")) == []
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()


# `2026-07-30T15-04-02Z` written in Arabic-Indic digits: the same instant, in characters that are
# not `0` through `9`. It is here because a `[0-9]` range inside a shell bracket expression is
# decided by the collation order the locale sets, so the guard matched this under
# `LC_ALL=ar_SA.UTF-8` while `validate-workspace.sh`'s `grep -E` refused it — the two checks
# disagreeing by locale, which is how an invisible record gets written. Nothing else in the suite
# carries a digit outside ASCII.
AR_DIGIT_RUN_ID = "٢٠٢٦-٠٧-٣٠T١٥-٠٤-٠٢Z"

# Run ids no `open-run.sh` can mint. The first two walk out of `runs/`; the next two carry a
# character an identifier may not hold; the rest traverse nothing and are still not run ids.
#
# The empty string is deliberately not here. The `${2:?}` that takes the run id in `close-run.sh`
# and in `clear-run.sh` refuses it before the format check ever runs, and the code that picks the
# status is the shell's, so it is 1 under sh and 2 under dash. A case for it would pass with the
# format check deleted and would be red under one of the two shells the suite runs.
BAD_RUN_IDS = [
    "../elsewhere/pwned",
    "../../victim",
    "a\vb",
    "a\\tb",
    "not-a-run-id",
    "2026-07-30T15:04:02Z",          # the colons of a timestamp, not the dashes of a filename
    "2026-07-30T15-04-02",           # no trailing Z
    "26-07-30T15-04-02Z",            # two-digit year
    "2026-07-30T15-04-02Z.json",     # the suffix already on it
    " 2026-07-30T15-04-02Z",         # a leading space
    "2026-07-30T15-04-02Z ",         # a trailing space
    AR_DIGIT_RUN_ID,                 # the same instant, in digits that are not 0-9
]

# Run ids whose first or last line is a run id and which are still not run ids. These are the
# reason the check is a `case` glob and not a grep: `printf '%s\n' "$v" | grep -qE` exits 0 when any
# one line matches. Measured on 2026-08-06 with the grep form, under mawk, which is Ubuntu CI's awk:
# a trailing newline gave `run_health=healthy`, exit 0, and a record whose filename holds a literal
# newline. The single-line ids above were refused by that form too and are not what broke.
MULTILINE_RUN_IDS = [
    "2026-07-30T15-04-02Z\n",
    "\n2026-07-30T15-04-02Z",
    "../../victim\n2026-07-30T15-04-02Z",
    "2026-07-30T15-04-02Z\n../../victim",
]

ALL_BAD_RUN_IDS = BAD_RUN_IDS + MULTILINE_RUN_IDS


def run_id_case_id(s):
    if not s.isascii():
        return "non-ascii-digits"
    return repr(s)[1:-1][:26] or "empty"


def locale_is_installed(name):
    r = subprocess.run(["locale", "-a"], capture_output=True, text=True)
    return name in r.stdout.split()


# A locale whose collation makes a `[0-9]` range match a digit outside ASCII. Measured on
# 2026-08-06: under it, `case ٢٠٢٦-٠٧-٣٠T١٥-٠٤-٠٢Z in [0-9][0-9]…` matched in sh and bash — and
# refused in dash, and under LC_ALL=C and LC_ALL=en_US.UTF-8 in all three. `grep -E` with the same
# expression refused it under every one.
COLLATING_LOCALE = "ar_SA.UTF-8"
needs_collating_locale = pytest.mark.skipif(
    not locale_is_installed(COLLATING_LOCALE),
    reason="%s is not installed here" % COLLATING_LOCALE)


# `RUN_ID_RE` is anchored, so it answers "is this whole string a run id". This one answers "does
# this text hold a run id anywhere", which is what a message showing the required shape does.
RUN_ID_ANYWHERE_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z")


def refusal_names_the_shape(stderr, offending):
    """The refusal names the value that is wrong and the shape it needed.

    The offending value is cut out of the message first. Without that, two of these cases pass on
    nothing: pytest names the temp directory for this test `…/test_a_run_id_that_is_not_a_ru0`, so
    any message echoing the workspace path contains the substring `run_id`, and the case whose
    offending value is `2026-07-30T15-04-02Z.json` contains a well-formed run id inside the value
    the message quotes back. `<run_id>` with its angle brackets is in neither.

    Only the last occurrence is cut, because three of these values are substrings of the example the
    message shows — `2026-07-30T15-04-02` without its `Z`, `26-07-30T15-04-02Z` without its century,
    and the one with a leading space — and cutting every occurrence would take the example with them.
    The value the message quotes back is the last thing on the line.
    """
    rest = stderr
    if offending:
        i = stderr.rfind(offending)
        if i >= 0:
            rest = stderr[:i] + stderr[i + len(offending):]
    return "<run_id>" in rest and RUN_ID_ANYWHERE_RE.search(rest) is not None


@pytest.mark.parametrize("bad", ALL_BAD_RUN_IDS, ids=run_id_case_id)
def test_a_run_id_that_is_not_a_run_id_is_refused_by_the_close(tmp_workspace, bad):
    """`run_id` is the one value here that becomes a path — the record goes to
    `runs/<run_id>.json` — so it is checked for its whole shape rather than for two characters.

    Measured on 2026-08-06 before the check existed, in a workspace whose parent holds it:
    `close-run.sh . ../pwned --trigger manual --close-state complete` printed `run_health=healthy`,
    exited 0, and left the record at `ws/pwned.json` with `runs/` empty. `ws/` is the directory the
    record lands in there, so that command needs no directory made first. A run that reports itself
    complete and healthy while its record is somewhere no reader looks is worse than one that fails.

    The ids that traverse nothing are here for a second reason: `validate-workspace.sh` reads a
    file in `runs/` as a run record only when its whole name matches the same rule, so a record
    named anything else is skipped by every check the workspace has — measured, a workspace holding
    `runs/not-a-run-id.json` gets no line about it at all — and `started_at` would carry the run id
    into a field the system compares as a timestamp.

    `ws/elsewhere/` is made first so the traversal has somewhere to land: `close-run.sh` makes no
    directory but `$ws/runs`, so without it the `mv` would fail and the case would pass on the wrong
    thing.
    """
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    (tmp_workspace / "elsewhere").mkdir()
    (tmp_workspace.parent / "elsewhere").mkdir(exist_ok=True)
    before = sorted(str(p.relative_to(tmp_workspace.parent))
                    for p in tmp_workspace.parent.rglob("*") if p.is_file())
    r = close(tmp_workspace, bad)
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert refusal_names_the_shape(r.stderr, bad), r.stderr
    assert sorted(str(p.relative_to(tmp_workspace.parent))
                  for p in tmp_workspace.parent.rglob("*") if p.is_file()) == before
    assert list((tmp_workspace / "elsewhere").iterdir()) == []
    assert list((tmp_workspace.parent / "elsewhere").iterdir()) == []
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()


@pytest.mark.parametrize("bad", ALL_BAD_RUN_IDS, ids=run_id_case_id)
def test_a_run_id_that_is_not_a_run_id_is_refused_by_the_clear(tmp_workspace, bad):
    """The same value reaches `rm -f` and `rm -rf` here, so this is the half where a bad run id
    costs data rather than putting a file in the wrong place.

    Measured on 2026-08-06 before the check existed: with `runs/.scratch/` present — which every run
    that stored a response leaves — and a file at `ws/runs/../../victim.json` to satisfy the record
    check, `clear-run.sh . ../../victim` printed its normal cleared message, exited 0, and deleted
    `ws/victim/` with its contents. Both preconditions are needed and this case sets both up: `rm
    -rf` removes nothing when a directory along the path is absent, and the record check stops the
    run before either `rm` without that file.

    Everything the id names is on disk, for every case: the record that satisfies the guard, the
    marker, and the scratch directory. So the format check is the only thing between the call and
    the removal, and if it lets a value through, something here is gone.
    """
    runs = tmp_workspace / "runs"
    (runs / ".scratch").mkdir()
    victim = tmp_workspace.parent / "victim"
    victim.mkdir(exist_ok=True)
    (victim / "keepme.txt").write_text("keep")
    for base in (tmp_workspace.parent, tmp_workspace):
        try:
            (base / (bad.lstrip("./") + ".json")).write_text("{}")
            target = base / bad.lstrip("./")
            target.mkdir(parents=True, exist_ok=True)
            (target / "keepme.txt").write_text("keep")
        except OSError:
            pass                      # a name the filesystem will not take; the refusal still holds
    (runs / (bad.replace("/", "_") + ".json")).write_text("{}")
    before = sorted(str(p.relative_to(tmp_workspace.parent))
                    for p in tmp_workspace.parent.rglob("*") if p.is_file())
    assert before, "the case has to have put something on disk to be worth running"
    r = run_script(CLEAR_RUN, tmp_workspace, bad)
    assert r.returncode == 1, r.stdout + r.stderr
    assert refusal_names_the_shape(r.stderr, bad), r.stderr
    assert sorted(str(p.relative_to(tmp_workspace.parent))
                  for p in tmp_workspace.parent.rglob("*") if p.is_file()) == before
    # The listing above is what catches a removal. This line is a second reading of the same thing
    # and cannot fire for the `../../victim` case on its own: from `runs/.scratch/` that id resolves
    # to `tmp_workspace/victim`, not to the `victim` beside the workspace that this reads.
    assert (victim / "keepme.txt").read_text() == "keep"


def _validator_reads_a_record_named(value, locale=None):
    """Whether `validate-workspace.sh` would read a file named `<value>.json` in `runs/` as a run
    record, decided by running the glob that script uses rather than by restating it here.

    The glob is expanded out of a variable in a `case`, which is what the script itself does at
    both places it decides a run id, so a value carrying a newline is compared the same way here as
    there. Running the validator on a real file instead would settle nothing for the four ids that
    hold a `/` or a control character, since no filesystem takes those names.
    """
    text = (RUNBOOK_SCRIPTS / "validate-workspace.sh").read_text(encoding="utf-8")
    found = re.findall(r"^RUN_ID_GLOB='(.+)'$", text, re.M)
    assert len(found) == 1, found
    env = dict(os.environ)
    if locale:
        env["LC_ALL"] = locale
    env["JS_VALUE"] = value
    env["JS_GLOB"] = found[0]
    r = subprocess.run(["sh", "-c", 'case $JS_VALUE in $JS_GLOB) exit 0 ;; *) exit 1 ;; esac'],
                       capture_output=True, text=True, env=env)
    return r.returncode == 0


def test_the_validators_glob_reads_a_real_record_the_way_this_helper_says_it_does(tmp_workspace):
    """`_validator_reads_a_record_named` runs the glob rather than the script, so something has to
    tie the two together. A well-formed name and a name that is not a run id both go through the
    helper and through the validator on a real file, and the two have to agree.

    The record written here is missing `close_state`, so a finding naming it is what shows the file
    was read rather than skipped by a rule this comparison never reaches.
    """
    for name, expected in (("2026-07-30T15-04-02Z", True), ("not-a-run-id", False)):
        (tmp_workspace / "runs" / (name + ".json")).write_text(
            json.dumps({"run_id": name, "trigger": "manual"}), encoding="utf-8")
        assert _validator_reads_a_record_named(name) is expected, name
        r = run_script(VALIDATE, tmp_workspace)
        read_it = ("runs/%s.json missing-key close_state" % name) in r.stdout
        assert read_it is expected, (name, r.stdout)
        (tmp_workspace / "runs" / (name + ".json")).unlink()


@pytest.mark.parametrize("locale", [None, pytest.param(COLLATING_LOCALE,
                                                       marks=needs_collating_locale)],
                         ids=["default-locale", "collating-locale"])
@pytest.mark.parametrize("value",
                         ["2026-07-30T15-04-02Z", "2026-12-31T23-59-59Z"] + ALL_BAD_RUN_IDS,
                         ids=run_id_case_id)
def test_the_two_scripts_and_the_validator_take_the_same_run_ids(tmp_workspace, value, locale):
    """All three spell the rule as a `case` glob, and each holds its own copy, so nothing compares
    as text. What has to agree is which ids they take, and that is what this drives: every id goes
    through both scripts and through the validator's own glob, and all three have to reach the same
    verdict.

    A script that drifted wider would write a record under a name the validator then skips; one that
    drifted narrower would refuse an id `open-run.sh` had already minted and written a marker for.

    Under two locales, because a `[0-9]` range in a shell bracket expression is decided by the
    locale's collation order: with `[0-9]` in the globs, this case measurably disagreed on
    `AR_DIGIT_RUN_ID` under `ar_SA.UTF-8` and agreed under the default one, because the validator
    decided with `grep -E`, which does not move. All three list their ten digits out now, so
    nothing here moves with the locale — and the case stays, since that is the property being kept.

    The multi-line ids are in the table too. They were left out while the validator decided by
    piping a filename into `grep -qE`, which takes any one matching line: it read a name holding a
    newline as a run record while both scripts refused to write one. `validate-workspace.sh` now
    compares the whole word the way they do.

    On its own this compares three implementations, so all three drifting together would survive it.
    What pins the absolute verdicts is `..._refused_by_the_close` and `..._refused_by_the_clear`
    above, which name every bad id by hand, and
    `test_a_record_whose_name_holds_a_newline_is_skipped` in `tests/test_validate_workspace.py`,
    which names the validator's.
    """
    (tmp_workspace / "jobs.jsonl").write_text("")
    env = {"LC_ALL": locale} if locale else None
    accepted_by_validator = _validator_reads_a_record_named(value, locale)
    closed = close(tmp_workspace, value, env=env)
    accepted_by_close = closed.returncode == 0
    cleared = run_script(CLEAR_RUN, tmp_workspace, value, env=env)
    # clear-run.sh exits 1 for a missing record as well as for a bad run id, so what separates the
    # two here is which message it gave.
    refused_by_clear = "must be a UTC timestamp" in cleared.stderr
    assert accepted_by_close == accepted_by_validator, (value, closed.stderr)
    assert (not refused_by_clear) == accepted_by_validator, (value, cleared.stderr)


@needs_collating_locale
@pytest.mark.parametrize("shell", ["sh", "dash"])
def test_a_run_id_in_digits_outside_ascii_is_refused_under_a_collating_locale(tmp_workspace, shell):
    """The guard has to refuse the same ids whatever locale the run is under, because
    `validate-workspace.sh` decides with `grep -E`, which does not move.

    Measured on 2026-08-06 with `[0-9]` in the glob: `case ٢٠٢٦-٠٧-٣٠T١٥-٠٤-٠٢Z in [0-9][0-9]…`
    matched under `LC_ALL=ar_SA.UTF-8` in sh and bash and refused under dash, so `close-run.sh`
    wrote `runs/٢٠٢٦-٠٧-٣٠T١٥-٠٤-٠٢Z.json` at exit 0 while the validator skipped the file entirely.
    Both shells are driven because the two disagreed with each other, and `/bin/sh` is bash on the
    machine this was written on and dash on the CI runner.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    (tmp_workspace / "jobs.jsonl").write_text("")
    env = {"LC_ALL": COLLATING_LOCALE}
    r = close(tmp_workspace, AR_DIGIT_RUN_ID, env=env, shell=shell)
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert refusal_names_the_shape(r.stderr, AR_DIGIT_RUN_ID), r.stderr
    assert list((tmp_workspace / "runs").glob("*.json")) == []
    c = run_script(CLEAR_RUN, tmp_workspace, AR_DIGIT_RUN_ID, env=env, shell=shell)
    assert c.returncode == 1, c.stdout + c.stderr
    assert refusal_names_the_shape(c.stderr, AR_DIGIT_RUN_ID), c.stderr


@needs_collating_locale
def test_a_real_run_id_still_closes_under_a_collating_locale(tmp_workspace):
    """The other half. A guard that refused everything under this locale would pass the case above
    and stop every run on a machine set to it.
    """
    env = {"LC_ALL": COLLATING_LOCALE}
    o = parsed_output(run_script(OPEN_RUN, tmp_workspace, env=env))
    assert RUN_ID_RE.match(o["run_id"]), o      # `date` still emits ASCII digits under this locale
    (tmp_workspace / "jobs.jsonl").write_text("")
    r = close(tmp_workspace, o["run_id"], env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert record_of(tmp_workspace, o["run_id"])["run_health"] == "healthy"
    c = run_script(CLEAR_RUN, tmp_workspace, o["run_id"], env=env)
    assert c.returncode == 0, c.stderr


# Ten run ids, each carrying one digit in all fourteen digit positions of the format. Between them
# they cover every position-and-digit pair either `case` glob can be wrong about — 14 × 10 = 140,
# asserted below rather than counted by eye. They are shape probes rather than instants: the globs
# and `validate-workspace.sh`'s `RUN_ID_GLOB` both check that a run id is twenty characters in the
# documented arrangement, not that it names a real time. `tests/test_validate_workspace.py` drives
# the same ten through the validator's copy, which these cases do not reach.
#
# The suite settled nothing about this before. Measured on 2026-08-06 at commit `1d1dc40` by
# dropping `8` from the first bracket of `close-run.sh`'s glob and running the module with
# `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_mechanics_scripts.py -p no:cacheprovider`:
# 414 passed, returncode 0. Same for `clear-run.sh`. The reason is that no well-formed run id
# written out in the close and clear cases carries an `8`: `git show
# 1d1dc40:tests/test_mechanics_scripts.py | sed -n '3417,4340p' | command grep -oE
# '[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z' | sort -u` returned four —
# `2026-07-30T09-00-00Z`, `2026-07-30T15-04-01Z`, `2026-07-30T15-04-02Z` and
# `2026-12-31T23-59-59Z` — which between them use 0, 1, 2, 3, 4, 5, 6, 7 and 9. Every other run id
# those cases pass is minted by `open-run.sh` from the clock, so whatever the later brackets were
# covered by was whatever the clock happened to read, which no case states and none controls.
DIGIT_COVER_RUN_IDS = [
    "0000-00-00T00-00-00Z",
    "1111-11-11T11-11-11Z",
    "2222-22-22T22-22-22Z",
    "3333-33-33T33-33-33Z",
    "4444-44-44T44-44-44Z",
    "5555-55-55T55-55-55Z",
    "6666-66-66T66-66-66Z",
    "7777-77-77T77-77-77Z",
    "8888-88-88T88-88-88Z",
    "9999-99-99T99-99-99Z",
]


def test_the_ten_shape_probe_ids_carry_every_digit_in_every_position():
    """`DIGIT_COVER_RUN_IDS` is worth running only while it does what its comment says, and nothing
    about it is obvious from reading ten similar strings. The positions come from the format written
    out here — four year, two month, two day, two hour, two minute, two second — not from either
    script and not from the table itself.
    """
    template = "YYYY-MM-DDTHH-MM-SSZ"
    positions = [i for i, ch in enumerate(template) if ch in "YMDHS"]
    assert len(positions) == 14, positions
    assert len(DIGIT_COVER_RUN_IDS) == 10
    pairs = {(p, rid[p]) for rid in DIGIT_COVER_RUN_IDS for p in positions}
    assert len(pairs) == 140, len(pairs)
    for rid in DIGIT_COVER_RUN_IDS:
        assert RUN_ID_RE.match(rid), rid
        assert len(rid) == len(template), rid
        assert [i for i, ch in enumerate(rid) if ch.isdigit()] == positions, rid


@pytest.mark.parametrize("run_id", DIGIT_COVER_RUN_IDS)
def test_a_run_id_carrying_one_digit_in_every_position_closes_and_clears(tmp_workspace, run_id):
    """Each glob lists its ten digits out fourteen times over, and a digit missing from any one of
    those twenty-eight brackets refuses a run id that is well formed: `close-run.sh` writes no
    record for it, or `clear-run.sh` leaves the marker and the scratch on disk. Neither script has
    anything else that would notice.

    One case fails for every bracket its own digit is missing from, in either script, because that
    digit is in all fourteen positions of the id. Measured on 2026-08-06 with `8` dropped from the
    first bracket of `close-run.sh`'s glob: 414 passed and returncode 0 without these cases, 1
    failed with them.

    Both scripts are driven, because they carry separate copies of the glob and only running each
    one reaches its own. The marker and the scratch are put on disk first so `clear-run.sh` has both
    removals to make and exit 0 means it made them.
    """
    runs = tmp_workspace / "runs"
    (tmp_workspace / "jobs.jsonl").write_text("")
    marker = runs / (".started-" + run_id)
    marker.write_text("")
    scratch = runs / ".scratch" / run_id
    scratch.mkdir(parents=True)
    (scratch / "response.json").write_text("{}")

    r = close(tmp_workspace, run_id)
    assert r.returncode == 0, r.stdout + r.stderr
    assert record_of(tmp_workspace, run_id)["run_id"] == run_id

    c = run_script(CLEAR_RUN, tmp_workspace, run_id)
    assert c.returncode == 0, c.stdout + c.stderr
    assert not marker.exists()
    assert not scratch.exists()


@needs_collating_locale
@pytest.mark.parametrize("shell", ["sh", "dash"])
@pytest.mark.parametrize("key", ["postings_unreviewed", "searches_never_succeeded"])
def test_a_count_in_digits_outside_ascii_stops_the_close_under_a_collating_locale(
        tmp_workspace, tmp_path, shell, key):
    """`close-run.sh` checks these two counts are numbers before it branches on them, and with
    `*[!0-9]*` that check moved with the locale: negating a bracket expression with `!` does not
    stop the range inside it being decided by the collation order.

    Measured on 2026-08-06 with `[!0-9]` in `close-run.sh` and a `run-counts.sh` shimmed to print
    `postings_unreviewed=٢`: under `LC_ALL=ar_SA.UTF-8` in sh the check passed, `[ "$unreviewed"
    -ne 0 ]` then wrote `integer expression expected` and the `&&` chain came out false, so the
    refusal over unjudged postings never ran and the script exited 0 having written the record with
    `close_state` complete and `postings_unreviewed` 0 — over a count set saying two postings were
    never judged. The same call exited 1 with nothing written under `LC_ALL=C`, under
    `LC_ALL=en_US.UTF-8`, and under dash at all three locales.

    Both shells for that reason. `/bin/sh` is bash on the machine this was written on and dash on
    the CI runner, and the two disagreed. The close is `interrupted` so the only thing in the script
    that can produce exit 1 is the check under test.

    `test_a_real_run_id_still_closes_under_a_collating_locale` is the other half: it closes a run
    with ASCII counts under this same locale at exit 0, so a check that refused every value under it
    would not pass both.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    broken = "".join((key + "=٢\n") if l.startswith(key + "=") else l + "\n"
                     for l in WHOLE_COUNT_SET.splitlines())
    assert broken.count("٢") == 1, broken
    env = dict(awk_shim(tmp_path, "run-counts.awk", broken, status=0, stderr=""))
    env["LC_ALL"] = COLLATING_LOCALE
    r = close(tmp_workspace, o["run_id"], "interrupted", env=env, shell=shell)
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert key in r.stderr, r.stderr
    assert not (tmp_workspace / "runs" / (o["run_id"] + ".json")).exists()
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()


def test_a_count_carrying_every_digit_still_reads_as_a_number(tmp_workspace, tmp_path):
    """The other direction on the same two checks. `*[!0123456789]*` scans every character of the
    value, so a digit dropped from either list turns a legitimate count into `is not a number` and
    stops the close. `1234567890` carries all ten, so one value catches a drop of any one of them.

    Measured on 2026-08-06 with this case deselected: dropping `3`, `4`, `6` or `9` from the
    `postings_unreviewed` list left the module at 429 passed, returncode 0 — no other value the
    suite hands that key carries any of those four digits. Dropping `5` failed 2 cases, so the gap
    was four digits wide rather than all ten.
    """
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    every_digit = "1234567890"
    counts = "".join(
        (l.split("=", 1)[0] + "=" + every_digit + "\n")
        if l.startswith(("postings_unreviewed=", "searches_never_succeeded=")) else l + "\n"
        for l in WHOLE_COUNT_SET.splitlines())
    assert counts.count("=" + every_digit) == 2, counts
    r = close(tmp_workspace, o["run_id"], "interrupted",
              env=awk_shim(tmp_path, "run-counts.awk", counts, status=0, stderr=""))
    assert r.returncode == 0, r.stdout + r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["postings_unreviewed"] == 1234567890
    assert rec["postings_surfaced"] == 40          # the rest of the set is untouched


def test_the_record_matches_the_template_field_set(tmp_workspace):
    """The template is what a host with no shell fills in by hand, so the two have to name the same
    fields. Both are compared against a list written out in this file: `set(record) ==
    set(template)` on its own passes when a field is dropped from both at once.
    """
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    close(tmp_workspace, o["run_id"])
    rec = record_of(tmp_workspace, o["run_id"])
    template = json.loads((RUN_SCRIPTS.parent / "templates" / "run-record.example.json").read_text())
    assert len(RECORD_FIELDS) == 20
    assert set(rec) == RECORD_FIELDS
    assert set(template) == RECORD_FIELDS
    assert set(rec) == set(template)


def test_the_template_arithmetic_holds(tmp_workspace):
    """The template is the only worked example of a whole record, and a host with no shell copies
    its shape. Numbers that do not add up would teach a wrong record. `detail_reads` above
    `postings_detail_read` is deliberate — one posting needed a second call — so that pair is
    checked as an inequality rather than for equality.
    """
    t = json.loads((RUN_SCRIPTS.parent / "templates" / "run-record.example.json").read_text())
    m = t["matches"]
    assert m["strong"] + m["moderate"] + m["weak"] + t["filtered_out"] \
        + t["duplicates_of_another"] == t["postings_reviewed"]
    assert t["postings_reviewed"] + t["postings_unreviewed"] == t["postings_surfaced"]
    assert sum(t["by_source"].values()) == t["postings_surfaced"]
    u = t["agent_data_usage"]
    assert u["searches"] + u["detail_reads"] + u["other"] == u["total_metered"]
    assert t["postings_detail_read"] <= u["detail_reads"]
    assert RUN_ID_RE.match(t["run_id"])
    assert t["run_id"] == t["started_at"].replace(":", "-")
    assert UTC_TS_RE.match(t["completed_at"]) and t["completed_at"] > t["started_at"]


def test_clearing_removes_the_marker_and_the_scratch_directory(tmp_workspace):
    """Writing the record and clearing the run are two steps because the digest is written between
    them, off the responses in the scratch directory. One script doing both would delete them first.
    """
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
    assert (tmp_workspace / "runs" / (o["run_id"] + ".json")).exists(), "the record is not scratch"
    assert (tmp_workspace / "jobs.jsonl").exists()


def test_clearing_a_run_with_no_record_is_refused(tmp_workspace):
    """The record is the only thing that says the run happened. Clearing without one would leave a
    workspace in which the run never existed, and `validate-workspace.sh --post-close` would have
    nothing to report.
    """
    o = opened(tmp_workspace)
    scratch = tmp_workspace / "runs" / ".scratch" / o["run_id"]
    scratch.mkdir(parents=True)
    (scratch / "search.json").write_text("{}")
    r = run_script(CLEAR_RUN, tmp_workspace, o["run_id"])
    assert r.returncode == 1
    assert "no record" in r.stderr
    assert (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()
    assert scratch.exists()


def test_clearing_another_runs_scratch_is_left_alone(tmp_workspace):
    """`clear-run.sh` takes one run id and removes that run's two files. A `rm -rf` over the whole
    `.scratch` directory, or over every marker, would take a run that is still open with it.
    """
    o = opened(tmp_workspace)
    (tmp_workspace / "jobs.jsonl").write_text("")
    other = "2026-07-30T09-00-00Z"
    other_marker = tmp_workspace / "runs" / (".started-" + other)
    other_marker.write_text("")
    other_scratch = tmp_workspace / "runs" / ".scratch" / other
    other_scratch.mkdir(parents=True)
    (other_scratch / "search.json").write_text("{}")
    mine = tmp_workspace / "runs" / ".scratch" / o["run_id"]
    mine.mkdir(parents=True)
    close(tmp_workspace, o["run_id"])
    r = run_script(CLEAR_RUN, tmp_workspace, o["run_id"])
    assert r.returncode == 0, r.stderr
    assert not mine.exists()
    assert other_marker.exists()
    assert (other_scratch / "search.json").exists()


@pytest.mark.skipif(not shutil.which("dash"), reason="dash is not installed here")
def test_closing_and_clearing_a_run_run_under_dash(tmp_workspace):
    """`close-run.sh` is the second shipped script that runs another shipped script rather than an
    awk program, so its `sh` call on `run-counts.sh`, its `${1:?}` operands and its `case` guards
    are run end to end under strict dash. `dash -n` exercises none of them, and on the CI runner
    `/bin/sh` is dash while it is bash on the machine this was written on.
    """
    o = opened(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"
    jobs.write_text("")
    run_script(RECORD_API, o["run_id"], jobs, FIXTURES / "search.ashby.json",
               "--route", "search-jobs", "--query-id", "q", shell="dash")
    n = len([e for e in lines(jobs) if e["event"] == "surfaced"])
    assert n == len(api_rows("search.ashby.json"))
    r = close(tmp_workspace, o["run_id"], "interrupted", shell="dash",
              sources="ashby", queries="q")
    assert r.returncode == 0, r.stdout + r.stderr
    rec = record_of(tmp_workspace, o["run_id"])
    assert rec["postings_surfaced"] == n
    assert rec["postings_unreviewed"] == n
    assert rec["sources"] == ["ashby"]
    c = run_script(CLEAR_RUN, tmp_workspace, o["run_id"], shell="dash")
    assert c.returncode == 0, c.stderr
    assert not (tmp_workspace / "runs" / (".started-" + o["run_id"])).exists()


# ---------------------------------------------------------------------------------- resolve-run.sh

def test_resolve_run_prints_the_workspace_and_the_open_run(tmp_workspace):
    """The two lines the callers read: the workspace, and the run open in it.

    The run id compared against is the one `open-run.sh` printed, not one written here, so the two
    scripts have to name the same run for this to pass. The newline count holds the output to two
    lines: a third would reach a caller that captures the whole block.
    """
    r = subprocess.run(["sh", str(OPEN_RUN), str(tmp_workspace)],
                       capture_output=True, text=True)
    run_id = [l.split("=", 1)[1] for l in r.stdout.splitlines() if l.startswith("run_id=")][0]

    out = subprocess.run(["sh", str(RESOLVE_RUN), "--workspace", str(tmp_workspace)],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    kv = dict(l.split("=", 1) for l in out.stdout.splitlines() if "=" in l)
    assert kv["workspace"] == str(tmp_workspace)
    assert kv["run_id"] == run_id
    assert out.stdout.count("\n") == 2


def test_resolve_run_says_so_when_no_run_is_open(tmp_workspace):
    """No marker in `runs/` means no run has been opened, and there is no run id to print. Exit 2
    rather than an empty `run_id=` line, which a caller would use as a run id."""
    out = subprocess.run(["sh", str(RESOLVE_RUN), "--workspace", str(tmp_workspace)],
                         capture_output=True, text=True)
    assert out.returncode == 2
    assert "no run is open" in out.stderr


def test_resolve_run_refuses_when_two_markers_are_on_disk(tmp_workspace):
    """Two markers means two runs are open, and picking either one records this work against a run
    it does not belong to. Both ids are in the message, so the caller can see which two runs the
    workspace is holding rather than go looking for them."""
    (tmp_workspace / "runs" / ".started-2026-08-11T16-06-16Z").write_text("", encoding="utf-8")
    (tmp_workspace / "runs" / ".started-2026-08-11T16-15-54Z").write_text("", encoding="utf-8")
    out = subprocess.run(["sh", str(RESOLVE_RUN), "--workspace", str(tmp_workspace)],
                         capture_output=True, text=True)
    assert out.returncode == 2
    assert "more than one run is open" in out.stderr
    assert "2026-08-11T16-06-16Z" in out.stderr
    assert "2026-08-11T16-15-54Z" in out.stderr


def test_a_marker_that_names_no_run_id_is_not_counted_as_a_second_run(tmp_workspace):
    """Markers are selected by the run-id shape, not by the `.started-*` glob alone.

    `runs/.started-` with nothing after the dash names no run, and `open-run.sh` skips it rather
    than refusing on it — `grep -n 'with nothing after the dash'
    skills/job-search-runbook/scripts/open-run.sh` — so a workspace can hold it beside a real
    marker. Counted, it would make one open run look like two and stop the run at the refusal
    above. `.started-not-a-run-id` is selected out the same way: `close-run.sh` and `clear-run.sh`
    both check a run id against that shape before doing anything with it, so a name they refuse is
    not a run this can hand to a caller.
    """
    (tmp_workspace / "runs" / ".started-").write_text("", encoding="utf-8")
    (tmp_workspace / "runs" / ".started-not-a-run-id").write_text("", encoding="utf-8")
    (tmp_workspace / "runs" / ".started-2026-08-11T16-06-16Z").write_text("", encoding="utf-8")
    out = subprocess.run(["sh", str(RESOLVE_RUN), "--workspace", str(tmp_workspace)],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout == "workspace=%s\nrun_id=2026-08-11T16-06-16Z\n" % tmp_workspace


def test_resolve_run_finds_the_workspace_when_no_flag_names_one(tmp_workspace, tmp_path):
    """The call a run makes: no arguments at all. Every other case here passes `--workspace`, which
    is how the tests reach a temporary directory, so this is the only one that runs
    `workspace-discovery.sh`, and the only one that would go red if the relative path this script
    names that script by were wrong.
    """
    home = tmp_path / "home"
    home.mkdir()
    ws = home / ".job-search"
    shutil.copytree(str(tmp_workspace), str(ws))
    opened_run = run_script(OPEN_RUN, ws)
    assert opened_run.returncode == 0, opened_run.stdout + opened_run.stderr
    run_id = parsed_output(opened_run)["run_id"]

    r = run_sh(RESOLVE_RUN, env=base_env(home))
    assert r.returncode == 0, r.stderr
    assert r.stdout == "workspace=%s\nrun_id=%s\n" % (ws, run_id)


CONSUMER = """#!/bin/sh
# What a caller does with this script: capture the output, take one value per key, use both.
set -u
resolved=$(sh "$1" --workspace "$2") || exit 2
ws=$(printf '%s\\n' "$resolved" | sed -n 's/^workspace=//p')
run_id=$(printf '%s\\n' "$resolved" | sed -n 's/^run_id=//p')
mkdir -p "$ws/runs/.scratch/$run_id" || exit 2
"""


def test_a_shell_caller_takes_both_values_out_of_what_this_printed(tmp_workspace, tmp_path):
    """A caller captures the output in `$(…)` and pulls each value out with `sed`. This runs that
    extraction against what the script actually printed, rather than against a block composed here.

    The consumer then makes `<workspace>/runs/.scratch/<run_id>`, the directory `fetch-posting.sh`
    and `search-jobs.sh` write their responses into, and the checks are that this exact directory is
    there afterwards and that it is the only one under `.scratch`. Both are needed: a run id read as
    the empty string leaves the path at `<workspace>/runs/.scratch/`, which `mkdir -p` creates at
    exit 0 — measured 2026-08-11.

    The workspace path carries a space, which is what the quoting in the consumer is for. Measured
    2026-08-11 on `<tmp>/a work space`, `mkdir -p $ws/runs/.scratch/<run_id>` unquoted exits 0
    having made three directories — `a`, `work` and `space/runs/.scratch/<run_id>`, the last of them
    under the caller's own directory — and none of them is the path the consumer asked for.
    """
    ws = tmp_path / "a work space"
    shutil.copytree(str(tmp_workspace), str(ws))
    run_id = parsed_output(run_script(OPEN_RUN, ws))["run_id"]

    consumer = tmp_path / "consumer.sh"
    consumer.write_text(CONSUMER, encoding="utf-8")
    r = subprocess.run(["sh", str(consumer), str(RESOLVE_RUN), str(ws)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (ws / "runs" / ".scratch" / run_id).is_dir()
    assert [p.name for p in (ws / "runs" / ".scratch").iterdir()] == [run_id]


def test_an_unknown_flag_prints_the_usage_line_under_every_shell():
    """A flag this script does not take is a caller error, not a workspace to go looking for, so it
    stops before reading anything. Run under `dash` as well where it is installed: the argument
    loop is `case`, `shift` and `$#`, and `dash -n` parses all three without running any of them.
    """
    for shell in ["sh"] + (["dash"] if shutil.which("dash") else []):
        r = run_script(RESOLVE_RUN, "--bogus", shell=shell)
        assert r.returncode == 2, shell + ": " + r.stdout + r.stderr
        assert r.stdout == "", shell + ": " + r.stdout
        assert r.stderr == "usage: resolve-run.sh [--workspace W]\n", shell + ": " + r.stderr


@pytest.mark.skipif(not shutil.which("dash"), reason="dash is not installed here")
def test_resolving_a_run_runs_under_dash(tmp_workspace):
    """The fourth shipped script that runs another shipped script rather than an awk program —
    `command grep -rn '^[^#]*sh "' skills/*/scripts/*.sh` returns four lines, this script's call on
    `workspace-discovery.sh` among them — so it is run end to end under strict dash the way
    `open-run.sh` and `close-run.sh` are. That `sh` call, the glob over `runs/`, the `case` that
    checks the run-id shape and the `$((n + 1))` count are none of them exercised by `dash -n`.
    """
    run_id = parsed_output(run_script(OPEN_RUN, tmp_workspace))["run_id"]
    r = run_script(RESOLVE_RUN, "--workspace", tmp_workspace, shell="dash")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "workspace=%s\nrun_id=%s\n" % (tmp_workspace, run_id)


# ------------------------------------------------------------------------ check-record-args.sh

@pytest.mark.parametrize("shell", ["sh", "dash"])
@pytest.mark.parametrize("value,rule", [
    ("linked:in", "may hold neither a comma nor a colon"),
    ("linked,in", "may hold neither a comma nor a colon"),
    ("linked\\in", "may hold no backslash"),
    ("linked\nin", "may hold no control character"),
])
def test_check_record_args_refuses_what_record_api_response_refuses(shell, value, rule):
    """The characters record-api-response.sh refuses in `--source`, checked without a call.

    Four values are driven against the three `case` patterns record-api-response.sh matches: a
    control character and a backslash at record-api-response.sh:92-106, and a comma or a colon at
    :112-120.

    This script exists so a wrapper can apply these rules before spending the metered call rather
    than after, and it is run directly here as well as through fetch-posting.sh, because the rules
    are the script's whole product.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    r = subprocess.run([shell, str(CHECK_ARGS), "--route", "get-posting", "--source", value],
                       capture_output=True, text=True)
    assert r.returncode == 2
    assert rule in r.stderr
    assert "no `call` event would name it" in r.stderr


@pytest.mark.parametrize("shell", ["sh", "dash"])
def test_check_record_args_accepts_the_values_a_run_actually_passes(shell):
    """A real source and a real query id go through, so the guard cannot be passing by refusing
    everything. The sources are not listed here or in the script — agent-data-reference/SKILL.md
    owns that set and the API refuses the rest."""
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    r = subprocess.run(
        [shell, str(CHECK_ARGS), "--route", "search-jobs",
         "--source", "linkedin", "--query-id", "strategic-finance"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout == ""
    assert r.stderr == ""


@pytest.mark.parametrize("shell", ["sh", "dash"])
def test_check_record_args_wants_a_query_id_for_a_search_and_not_for_a_detail_read(shell):
    """The one rule that is not about characters, and the one that is conditional on the route.

    record-api-response.sh:130-136 refuses `--route search-jobs` with no query id, and that check
    runs before `emit_call` is defined at :173, so it writes nothing — which for a wrapper that has
    already spent the call is a billed call with no `call` event naming it. A detail read is not
    grouped by query id and takes none, so the same missing value is fine there.

    Both halves are asserted. A case that only drove the refusal would still pass if the guard
    demanded a query id on every route, which would then refuse every legitimate detail read.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    for args in (["--route", "search-jobs", "--source", "linkedin"],
                 ["--route", "search-jobs", "--source", "linkedin", "--query-id", ""]):
        r = subprocess.run([shell, str(CHECK_ARGS), *args], capture_output=True, text=True)
        assert r.returncode == 2, "%s: %s" % (args, r.stdout + r.stderr)
        assert "--route search-jobs needs a --query-id" in r.stderr

    r = subprocess.run([shell, str(CHECK_ARGS), "--route", "get-posting", "--source", "linkedin"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stderr == ""


# Every (route, source, query-id) combination below is passed to both scripts unchanged, because the
# guard takes record-api-response.sh's own flag names. The second value is whether
# record-api-response.sh accepts the values.
GUARD_AGREEMENT_CASES = [
    (["--route", "get-posting", "--source", "linkedin"], True),
    (["--route", "get-posting"], True),
    (["--route", "get-posting", "--source", ""], True),
    (["--route", "search-jobs", "--source", "linkedin", "--query-id", "strategic-finance"], True),
    (["--route", "search-jobs", "--source", "linkedin", "--query-id", ""], False),
    (["--route", "search-jobs", "--source", "linkedin"], False),
    (["--route", "get-posting", "--source", "linked:in"], False),
    (["--route", "get-posting", "--source", "linked,in"], False),
    (["--route", "get-posting", "--source", "linked\\in"], False),
    (["--route", "get-posting", "--source", "linked\nin"], False),
    (["--route", "search-jobs", "--source", "linkedin", "--query-id", "a:b"], False),
    (["--route", "search-jobs", "--source", "linkedin", "--query-id", "a\\b"], False),
    (["--route", "bogus", "--source", "linkedin"], False),
    (["--source", "linkedin"], False),
]


@pytest.mark.parametrize("args,accepted", GUARD_AGREEMENT_CASES)
def test_the_guard_and_record_api_response_agree_on_the_same_values(args, accepted, tmp_path):
    """Whatever this guard lets through, record-api-response.sh must take — checked by running both.

    The guard's only product is a claim about what another script does, so it is checked against that
    script rather than against a list written here. Round 1 shipped it checking characters and
    nothing else while its header said record-api-response.sh accepted every value it passed:
    `--query-id ''` went through the guard and exited 2 there, before `emit_call` at
    record-api-response.sh:173. For a wrapper that had already spent the call that is a billed call
    with no `call` event naming it.

    record-api-response.sh is handed a response path that does not exist, so it reaches its
    missing-file check at record-api-response.sh:138 only once it has accepted every value ahead of
    it. That message is the discriminator: present when the values passed, absent when one was
    refused. Nothing is called and no key is needed — the check at :138 also runs before the log file
    is created at :140, which is why jobs.jsonl is still absent either way.
    """
    guard = subprocess.run(["sh", str(CHECK_ARGS), *args], capture_output=True, text=True)
    assert (guard.returncode == 0) is accepted, "%s: guard said %d\n%s" % (
        args, guard.returncode, guard.stderr)

    jobs = tmp_path / "jobs.jsonl"
    record = subprocess.run(
        ["sh", str(RECORD_API), "2026-08-11T00-00-00Z", str(jobs),
         str(tmp_path / "no-such-response.json"), *args],
        capture_output=True, text=True)
    assert record.returncode == 2, record.stdout + record.stderr
    assert ("no such file" in record.stderr) is accepted, "%s: %s" % (args, record.stderr)
    assert not jobs.exists(), "record-api-response.sh logged an event on a path that makes no call"


# ---------------------------------------------------------------------------------- fetch-posting.sh

@pytest.mark.live
@needs_api
def test_fetch_posting_records_the_call_and_the_detail(live_run):
    out = subprocess.run(
        ["sh", str(FETCH_POSTING), "--workspace", str(live_run.ws),
         "--posting-id", live_run.row["posting_id_at_seen"],
         "--source-url", live_run.row["source_url"],
         "--source", live_run.row["source"]],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith("response=")

    saved = json.loads(
        pathlib.Path(out.stdout.split("=", 1)[1].strip()).read_text(encoding="utf-8"))
    assert saved["meta"]["request_id"].startswith("req_"), \
        "no request_id — the wrapper did not reach the API"

    rows = [json.loads(l) for l in live_run.jobs.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    calls = [x for x in rows if x["event"] == "call" and x.get("route") == "get-posting"]
    details = [x for x in rows if x["event"] == "detail"]
    assert len(calls) == 1
    assert calls[0]["run_id"] == live_run.run_id
    assert len(details) == 1
    assert details[0]["source_id"] == live_run.row["source_id"]


def test_fetch_posting_refuses_before_calling_when_no_run_is_open(tmp_workspace):
    """Exits before any call, so this one spends nothing and needs no key."""
    out = subprocess.run(
        ["sh", str(FETCH_POSTING), "--workspace", str(tmp_workspace),
         "--posting-id", "jp_000000000000", "--source-url", "https://example.test/1",
         "--source", "linkedin"],
        capture_output=True, text=True)
    assert out.returncode == 2
    assert "no run is open" in out.stderr


# The state CI runs the mechanics suite in: no agent-data anywhere on PATH. A case given this
# environment cannot reach the API even if the guard it is checking were deleted.
KEYLESS_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


def keyless(shell, *args):
    """Run fetch-posting.sh with agent-data unreachable."""
    return subprocess.run([shell, str(FETCH_POSTING), *[str(a) for a in args]],
                          capture_output=True, text=True, env={"PATH": KEYLESS_PATH})


@pytest.mark.parametrize("shell", ["sh", "dash"])
def test_fetch_posting_checks_the_source_before_it_goes_looking_for_a_run(tmp_workspace, shell):
    """The `--source` guard, with no API key and no run open — the state CI runs in.

    Every other case covering this guard is `live`-marked and `needs_api`-gated, so with agent-data
    off PATH the whole suite stayed green with the guard deleted, and CI holds no key. This one costs
    nothing, because the guard runs before resolve-run.sh and resolve-run.sh refuses first on a
    workspace with no run open.

    Both branches are asserted. A case that drove only the refused source would still pass if the
    guard refused every value, so the second call passes a source the guard has to let through and
    checks that the script got as far as resolve-run.sh.

    Deleting the `check-record-args.sh` line makes the first call reach resolve-run.sh and print
    `no run is open` instead of the rule, so the first assertion goes red with no key involved.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    assert shutil.which("agent-data", path=KEYLESS_PATH) is None, \
        "agent-data is on this PATH, so this case is not running in the state it exists for"

    refused = keyless(shell, "--workspace", tmp_workspace, "--posting-id", "jp_000000000000",
                      "--source-url", "https://example.test/1", "--source", "a:b")
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert "may hold neither a comma nor a colon" in refused.stderr
    assert "no run is open" not in refused.stderr, \
        "the guard ran after resolve-run.sh, so in a workspace with a run open the call comes first"

    allowed = keyless(shell, "--workspace", tmp_workspace, "--posting-id", "jp_000000000000",
                      "--source-url", "https://example.test/1", "--source", "linkedin")
    assert allowed.returncode == 2, allowed.stdout + allowed.stderr
    assert "no run is open" in allowed.stderr
    assert "may hold" not in allowed.stderr


@pytest.mark.parametrize("shell", ["sh", "dash"])
@pytest.mark.parametrize("posting_id,rule", [
    ("../../../escaped", "may hold no slash"),
    ("a/b", "may hold no slash"),
    ("jp_a\njp_b", "may hold no control character"),
])
def test_fetch_posting_refuses_a_posting_id_that_would_name_some_other_file(
        tmp_workspace, shell, posting_id, rule):
    """The posting id supplies a file name, and it arrives from the API rather than from an operator.

    A run is open here, so without the check the script would build the path, make the call and write
    the response. Measured 2026-08-11 with the check removed and agent-data off PATH,
    `--posting-id ../../../escaped` left the shell unable to open
    `runs/.scratch/<run_id>/detail-../../../escaped.json`, and the script then ran its failed-call
    branch on an error file that was never created: exit 1, nothing on stdout, and three lines on
    stderr, not one of which says which argument was wrong. `jp_a<newline>jp_b` created the file
    `detail-jp_a<newline>jp_b.json`, and the `response=` line then printed as two lines, so
    `sed -n 's/^response=//p'` handed the caller a path that stopped at the newline and named no
    file.

    Nothing is spent and no key is needed: the check runs with the other argument checks, before
    resolve-run.sh and before the scratch directory is made — which is what the last assertion holds.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    opened = run_script(OPEN_RUN, tmp_workspace)
    assert opened.returncode == 0, opened.stdout + opened.stderr

    out = keyless(shell, "--workspace", tmp_workspace, "--posting-id", posting_id,
                  "--source-url", "https://example.test/1", "--source", "linkedin")
    assert out.returncode == 2, out.stdout + out.stderr
    assert rule in out.stderr
    assert out.stdout == ""
    assert not (tmp_workspace / "runs" / ".scratch").exists(), \
        "the response directory was made, so the check ran after the path was built"
    assert not (tmp_workspace / "jobs.jsonl").exists(), "jobs.jsonl was created"


@pytest.mark.parametrize("shell", ["sh", "dash"])
def test_fetch_posting_takes_the_posting_id_shape_the_api_returns(tmp_workspace, shell):
    """The other half of the case above: an id shaped the way live rows are shaped gets past the
    check, so it cannot be passing by refusing everything.

    `jp_` and 12 hex digits is the shape every `id` carried on a live 10-row linkedin search measured
    2026-08-11. No run is open, so the script stops at resolve-run.sh having spent nothing.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    out = keyless(shell, "--workspace", tmp_workspace, "--posting-id", "jp_a319f60ebe3f",
                  "--source-url", "https://example.test/1", "--source", "linkedin")
    assert out.returncode == 2, out.stdout + out.stderr
    assert "no run is open" in out.stderr
    assert "--posting-id" not in out.stderr


@pytest.mark.live
@needs_api
def test_fetch_posting_records_the_call_when_the_api_refuses_the_posting(live_run):
    """A refused call was still billed, so it still owes a `call` event.

    Measured 2026-08-11: `get-posting --posting_id jp_000000000000 --source_url
    https://www.linkedin.com/jobs/view/0000000000 --source linkedin` exits 1, writes nothing to
    stdout, and puts an error body on stderr carrying `error.status` 404, `error.code`
    `data_unavailable`, and an `error.request_id`.

    The assertion below reads `error.request_id` rather than the code string. This API's error
    codes have changed before — the 2026-07-06 multi-source reconciliation found them moved to
    `validation_error` and `503` — so pinning a code would make this test fail on a change that
    does not affect what it is checking: that a refused call still left a `call` event.
    """
    out = subprocess.run(
        ["sh", str(FETCH_POSTING), "--workspace", str(live_run.ws),
         "--posting-id", "jp_000000000000",
         "--source-url", "https://www.linkedin.com/jobs/view/0000000000",
         "--source", "linkedin"],
        capture_output=True, text=True)
    assert out.returncode == 1
    body = json_object_in(out.stderr)
    assert body["error"]["request_id"].startswith("req_"), \
        "no request_id in the error body — this did not reach the API"

    rows = [json.loads(l) for l in live_run.jobs.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    calls = [x for x in rows if x["event"] == "call" and x.get("route") == "get-posting"]
    assert len(calls) == 1, "the failed call was billed and left no record of itself"


@pytest.mark.live
@needs_api
def test_fetch_posting_refuses_a_source_record_api_response_would_refuse_before_calling(live_run):
    """A `--source` carrying a colon, checked before the call rather than after it.

    record-api-response.sh matches three `case` patterns against `--source` — no control character
    and no backslash at record-api-response.sh:92-106, and neither a comma nor a colon at :112-120 —
    and every one of those checks runs before `emit_call` is even defined at :173, so it writes
    nothing. Reading the posting first and finding that out afterwards leaves a call the API billed
    with no `call` event naming it, and a run's metered-call count is built from those events.

    Measured 2026-08-11 against an open run, before check-record-args.sh existed: exit 1, the saved
    error body carrying request_id req_eca95b6e566b46dca902c900, and zero `call` events with route
    get-posting.

    Two assertions separate "the call never happened" from "the call happened and its record was
    lost": the log gains nothing at all, and no file under the workspace holds a request id.
    `agent-data call … > resp 2> err` makes the shell create both files before the CLI runs, so a
    scratch directory holding either one would mean the call was attempted.
    """
    before = live_run.jobs.read_text(encoding="utf-8")
    out = subprocess.run(
        ["sh", str(FETCH_POSTING), "--workspace", str(live_run.ws),
         "--posting-id", live_run.row["posting_id_at_seen"],
         "--source-url", live_run.row["source_url"],
         "--source", "linked:in"],
        capture_output=True, text=True)
    assert out.returncode == 2, out.stdout + out.stderr
    assert "may hold neither a comma nor a colon" in out.stderr
    assert out.stdout == ""

    assert live_run.jobs.read_text(encoding="utf-8") == before, "the log gained a row"
    scratch = live_run.ws / "runs" / ".scratch"
    written = "".join(p.read_text(encoding="utf-8", errors="replace")
                      for p in scratch.rglob("*") if p.is_file()) if scratch.exists() else ""
    assert "req_" not in written, \
        "a request id is on disk, so the call was made and its record was lost: %s" % written[:400]


@pytest.mark.live
@needs_api
def test_fetch_posting_exits_1_when_the_call_worked_and_the_response_was_refused(live_run):
    """The other half of exit 1: the call succeeded and record-api-response.sh refused the body.

    The posting is a real one from a second live search this run never recorded, so the surfaced
    check at record-api-response.sh:285-293 does not find it, and that branch records the call and
    exits 1. The second search runs against ashby where live_run recorded linkedin, so no row of it
    can match a surfaced row whatever either search returns.

    Without `[ "$recstatus" -eq 0 ] || exit 1` in fetch-posting.sh this exits 0. Deleting that line
    and running `python3 -m pytest -q -m live` gave `2 passed` before this case existed, so nothing
    held the line in place.
    """
    other = live_run.ws / "other-source.json"
    with other.open("w", encoding="utf-8") as out:
        r = subprocess.run(
            ["agent-data", "call", LISTING, "search-jobs", "--source", "ashby",
             "--keywords", "strategic finance", "--limit", "5"],
            stdout=out, stderr=subprocess.PIPE, text=True)
    assert r.returncode == 0, r.stderr
    results = json.loads(other.read_text(encoding="utf-8"))["data"]["results"]
    assert results, "the ashby search returned no rows — widen the keywords"
    row = results[0]

    fetched = subprocess.run(
        ["sh", str(FETCH_POSTING), "--workspace", str(live_run.ws),
         "--posting-id", row["id"], "--source-url", row["source_url"], "--source", row["source"]],
        capture_output=True, text=True)
    assert fetched.returncode == 1, fetched.stdout + fetched.stderr
    assert "no surfaced posting" in fetched.stderr
    assert fetched.stdout.startswith("response="), \
        "the posting was fetched and saved, so the path is printed on this failure too"

    saved = json.loads(
        pathlib.Path(fetched.stdout.split("=", 1)[1].strip()).read_text(encoding="utf-8"))
    assert saved["meta"]["request_id"].startswith("req_"), \
        "no request_id — the call never reached the API, so this is not the case under test"

    rows = [json.loads(l) for l in live_run.jobs.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    calls = [x for x in rows if x["event"] == "call" and x.get("route") == "get-posting"]
    assert len(calls) == 1, "the billed call left no record of itself"
    assert [x for x in rows if x["event"] == "detail"] == [], \
        "the response was refused, so no posting text should have been stored"


# ------------------------------------------------------------------------------------ search-jobs.sh


def keyless_search(shell, *args):
    """Run search-jobs.sh with agent-data unreachable, the way CI runs the suite."""
    return subprocess.run([shell, str(SEARCH_JOBS), *[str(a) for a in args]],
                          capture_output=True, text=True, env={"PATH": KEYLESS_PATH})


@pytest.mark.live
@needs_api
def test_search_jobs_records_the_call_and_the_surfaced_rows(tmp_workspace):
    run_id = open_run_in(tmp_workspace)

    out = subprocess.run(
        ["sh", str(SEARCH_JOBS), "--workspace", str(tmp_workspace),
         "--query-id", "strategic-finance", "--source", "linkedin",
         "--", "--keywords", "strategic finance", "--limit", "5"],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith("response=")

    saved = json.loads(
        pathlib.Path(out.stdout.split("=", 1)[1].strip()).read_text(encoding="utf-8"))
    assert saved["meta"]["request_id"].startswith("req_"), \
        "no request_id — the wrapper did not reach the API"

    rows = [json.loads(l) for l in (tmp_workspace / "jobs.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip()]
    calls = [x for x in rows if x["event"] == "call" and x.get("route") == "search-jobs"]
    surfaced = [x for x in rows if x["event"] == "surfaced"]
    assert len(calls) == 1
    assert calls[0]["run_id"] == run_id
    assert calls[0]["query_id"] == "strategic-finance"
    assert surfaced, "the live search surfaced no rows — widen the keywords"


@pytest.mark.live
@needs_api
def test_search_jobs_passes_route_parameters_through_unchanged(tmp_workspace):
    """The API echoes the parameters it received under data.query, so the passthrough is checked
    against what the route actually got, not against what the script was handed.

    Measured 2026-08-11: a live search-jobs response carries
    data.query = {keywords, location, source, published_on_or_after}.
    """
    open_run_in(tmp_workspace)

    out = subprocess.run(
        ["sh", str(SEARCH_JOBS), "--workspace", str(tmp_workspace),
         "--query-id", "q", "--source", "linkedin",
         "--", "--keywords", "strategic finance", "--limit", "3",
         "--published_on_or_after", "2026-07-28"],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr

    saved = json.loads(
        pathlib.Path(out.stdout.split("=", 1)[1].strip()).read_text(encoding="utf-8"))
    q = saved["data"]["query"]
    assert q["keywords"] == "strategic finance"   # the space survived word splitting
    assert q["source"] == "linkedin"
    assert q["published_on_or_after"] == "2026-07-28"


@pytest.mark.live
@needs_api
def test_search_jobs_records_the_call_when_the_api_refuses_the_search(tmp_workspace):
    """The API answered the call with an error and the call was still billed, so the `call` event
    still has to be written.

    Measured 2026-08-11: `search-jobs --source no-such-source --keywords 'strategic finance'
    --limit 2` exits 1, writes nothing to stdout, and puts an error body on stderr carrying
    `error.status` 400, `error.code` `validation_error`, `error.request_id`, and the message
    `Unsupported source 'no-such-source' for source. Allowed values: linkedin, ashby, greenhouse,
    lever.` No job board is named no-such-source, so the route will not start accepting the value
    and turning this case into a search that succeeds.

    The assertion below reads `error.request_id` rather than the code string. This API's error codes
    have changed before — the 2026-07-06 multi-source reconciliation found them moved to
    `validation_error` and `503` — so pinning a code would make this test fail on a change that does
    not affect what it is checking: that a refused call still left a `call` event.
    """
    run_id = open_run_in(tmp_workspace)

    out = subprocess.run(
        ["sh", str(SEARCH_JOBS), "--workspace", str(tmp_workspace),
         "--query-id", "strategic-finance", "--source", "no-such-source",
         "--", "--keywords", "strategic finance", "--limit", "2"],
        capture_output=True, text=True)
    assert out.returncode == 1, out.stdout + out.stderr
    assert out.stdout == "", "a call that never returned a body printed a path to one"
    body = json_object_in(out.stderr)
    assert body["error"]["request_id"].startswith("req_"), \
        "no request_id in the error body — this did not reach the API"

    rows = [json.loads(l) for l in (tmp_workspace / "jobs.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip()]
    calls = [x for x in rows if x["event"] == "call" and x.get("route") == "search-jobs"]
    assert len(calls) == 1, "the failed call was billed and left no record of itself"
    assert calls[0]["run_id"] == run_id
    assert calls[0]["query_id"] == "strategic-finance"
    assert [x for x in rows if x["event"] == "surfaced"] == [], \
        "the call returned no results, so nothing should have been surfaced"


@pytest.mark.live
@needs_api
def test_search_jobs_exits_1_when_the_search_worked_and_the_rows_were_refused(tmp_workspace):
    """The other half of exit 1: the API answered with rows and record-api-response.sh refused them.

    `--fields` is one of the route's own parameters (`agent-data docs <the LISTING constant>`, the
    `fields` entry under search-jobs), so it reaches the route through the passthrough like any
    other. `--fields id,title,company_name` returns rows carrying those three keys and nothing
    else, and record-api-response.sh:427-433 requires `source`, `source_id`, `id` and `source_url`
    on every row, so it appends none of them and exits 1 at :496.

    The refusal follows from the field list rather than from what the search happened to return:
    every row of every response to this call is missing three of the four required keys.

    agent-data-reference/SKILL.md:64-67 gives the same reason, but it is written about the other
    route: it sits under `## Reading one posting` at :55, and
    `command grep -n fields skills/agent-data-reference/SKILL.md` finds no search-jobs prose about
    `--fields` at all. The mechanism does not belong to either route — record-api-response.sh runs
    the same four checks in two places, at :427-433 on each row of a search body and at :258-277 on
    a posting body, and a `--fields` list that leaves out `source` or `source_id` fails them either
    way. So the warning does not cover the route this case drives, and the behavior it warns about
    still does.

    Measured 2026-08-12 with `--keywords "strategic finance" --limit 3 --fields
    id,title,company_name`: `agent-data call` exited 0 with 3 rows, and the wrapper exited 1 having
    printed its `response=` line and recorded one `call` event carrying ok true, rows_returned 3
    and rows_new 0.

    Without `[ "$recstatus" -eq 0 ] || exit 1` in search-jobs.sh this exits 0. Deleting that line
    and running `python3 -m pytest -q -k "search_jobs or listing_id"` gave `21 passed` before this
    case existed, so nothing held the line in place.
    """
    run_id = open_run_in(tmp_workspace)

    out = subprocess.run(
        ["sh", str(SEARCH_JOBS), "--workspace", str(tmp_workspace),
         "--query-id", "strategic-finance", "--source", "linkedin",
         "--", "--keywords", "strategic finance", "--limit", "3",
         "--fields", "id,title,company_name"],
        capture_output=True, text=True)
    assert out.returncode == 1, out.stdout + out.stderr
    assert "nothing was appended" in out.stderr
    assert out.stdout.startswith("response="), \
        "the search ran and its body is saved, so the path is printed on this failure too"

    saved = json.loads(
        pathlib.Path(out.stdout.split("=", 1)[1].strip()).read_text(encoding="utf-8"))
    assert saved["meta"]["request_id"].startswith("req_"), \
        "no request_id — the call never reached the API, so this is not the case under test"
    assert saved["data"]["results"], \
        "the search returned no rows, so there were none to refuse — widen the keywords"

    rows = [json.loads(l) for l in (tmp_workspace / "jobs.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip()]
    calls = [x for x in rows if x["event"] == "call" and x.get("route") == "search-jobs"]
    assert len(calls) == 1, "the billed call left no record of itself"
    assert calls[0]["run_id"] == run_id
    assert calls[0]["ok"] is True, "the API answered this call, so the event says so"
    assert calls[0]["rows_new"] == 0
    assert [x for x in rows if x["event"] == "surfaced"] == [], \
        "the rows were refused, so none of them should have been surfaced"


def test_search_jobs_refuses_before_calling_when_no_run_is_open(tmp_workspace):
    """Exits before any call, so this one spends nothing and needs no key."""
    out = subprocess.run(
        ["sh", str(SEARCH_JOBS), "--workspace", str(tmp_workspace),
         "--query-id", "q", "--source", "linkedin", "--", "--keywords", "x"],
        capture_output=True, text=True)
    assert out.returncode == 2
    assert "no run is open" in out.stderr


@pytest.mark.parametrize("shell", ["sh", "dash"])
@pytest.mark.parametrize("args", [
    ["--query-id", "q", "--source", "linkedin"],
    ["--query-id", "q", "--source", "linkedin", "--"],
])
def test_search_jobs_refuses_a_call_that_names_no_route_parameters(tmp_workspace, shell, args):
    """No `--` at all and `--` with nothing after it both reach `[ $# -ge 1 ]` with no arguments
    left, and neither is called.

    Measured 2026-08-11 with that check removed, against an open run: the agent-data CLI refuses a
    parameterless call itself, writing an error body that carries "source": "cli", code
    missing_required_param and no request_id, so the API never saw the call — and the wrapper's
    failed-call branch recorded a `call` event for it anyway. That event would put one call the API
    never received into the run's metered-call count.

    This case and the missing-flag case below were one parametrized test, so a failure did not say
    which of the three checks broke. Measured 2026-08-12 with the split in place: deleting
    `[ $# -ge 1 ]` fails these two argument lists under sh and dash and leaves the case below green.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    out = keyless_search(shell, "--workspace", tmp_workspace, *args)
    assert out.returncode == 2, out.stdout + out.stderr
    assert "usage: search-jobs.sh" in out.stderr
    assert out.stdout == ""


@pytest.mark.parametrize("shell", ["sh", "dash"])
@pytest.mark.parametrize("args,absent", [
    (["--source", "linkedin", "--", "--keywords", "x"], "--query-id"),
    (["--query-id", "q", "--", "--keywords", "x"], "--source"),
])
def test_search_jobs_refuses_a_call_that_omits_a_required_flag(tmp_workspace, shell, args, absent):
    """Both flags are required because they are what the `call` event is filed under: run-counts.sh
    groups a run's search calls by source and query id, so a call recorded without one lands in the
    wrong group.

    One check per flag — `[ -n "$query_id" ]` and `[ -n "$src" ]` — and each holds only its own
    argument list. Measured 2026-08-12: deleting `[ -n "$query_id" ]` fails the two `--query-id`
    cases (check-record-args.sh then refuses the empty query id and prints its own rule instead of
    the usage line), and deleting `[ -n "$src" ]` fails the two `--source` cases (the script gets as
    far as resolve-run.sh and prints `no run is open`). Neither deletion touches the other flag's
    cases.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    assert absent not in args, "this case is about the flag being absent"
    out = keyless_search(shell, "--workspace", tmp_workspace, *args)
    assert out.returncode == 2, out.stdout + out.stderr
    assert "usage: search-jobs.sh" in out.stderr
    assert out.stdout == ""


@pytest.mark.parametrize("shell", ["sh", "dash"])
@pytest.mark.parametrize("passthrough,offending", [
    (["--keywords", "strategic finance", "--source", "ashby"], "--source"),
    (["--keywords", "strategic finance", "--source=ashby"], "--source=ashby"),
    (["--keywords", "--source"], "--source"),
])
def test_search_jobs_refuses_a_second_source_among_the_route_parameters(
        tmp_workspace, shell, passthrough, offending):
    """`--source` after `--` would search one source while the `call` event named another.

    The script sends `--source` to the route itself and the route takes the last value it is given.
    Measured 2026-08-11: `agent-data call <the LISTING constant> search-jobs --source linkedin
    --source ashby --keywords "strategic finance" --limit 1` exits 0 with data.query.source `ashby`
    and an ashby row. The wrapper would have written that body to search-q-linkedin.json and handed
    record-api-response.sh `--source linkedin`. A search with rows is still filed under the source
    that answered — record-api-response.sh:489-490 takes the source off the first surfaced row —
    but a search that returned none falls back to the flag and is filed under a source nothing
    searched.

    `--source=ashby` is the same call in the form the CLI also accepts: `agent-data call <the
    LISTING constant> search-jobs --source=ashby --keywords "strategic finance" --limit 1
    --dry-run` resolves to a URL carrying `source=ashby`, measured 2026-08-12.

    The third case is `--keywords --source`, where the string arrives in the value position rather
    than the flag position. It is refused too, because the script never learns which route
    parameters take a value and so cannot tell the two apart. That is a limit on what a caller may
    search for, so it is written in the header at search-jobs.sh:8-10 and :14-19 and in the third
    line of the refusal message, not only in the comment above the check.

    A run is open here, so without the check the script would build the path, make the call and
    write the response. Nothing is spent and no key is needed: the check runs with the other
    argument checks, before resolve-run.sh and before the scratch directory is made — which is what
    the last two assertions hold.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    opened = run_script(OPEN_RUN, tmp_workspace)
    assert opened.returncode == 0, opened.stdout + opened.stderr

    out = keyless_search(shell, "--workspace", tmp_workspace,
                         "--query-id", "q", "--source", "linkedin", "--", *passthrough)
    assert out.returncode == 2, out.stdout + out.stderr
    assert "no argument after -- may be --source" in out.stderr
    assert "cannot tell a value from a flag" in out.stderr, \
        "the message explains only the duplicate-flag case"
    assert offending in out.stderr, "search-jobs.sh did not print the argument it refused"
    assert out.stdout == ""
    assert not (tmp_workspace / "runs" / ".scratch").exists(), \
        "the response directory was made, so the check ran after the path was built"
    assert not (tmp_workspace / "jobs.jsonl").exists(), "jobs.jsonl was created"


@pytest.mark.parametrize("shell", ["sh", "dash"])
def test_search_jobs_takes_the_route_parameters_that_are_not_a_source(tmp_workspace, shell):
    """The other half of the case above: a passthrough with no `--source` in it gets through.

    Without this, the guard could refuse everything after `--` and the case above would still pass.
    No run is open, so the script stops at resolve-run.sh having spent nothing.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    out = keyless_search(shell, "--workspace", tmp_workspace,
                         "--query-id", "q", "--source", "linkedin",
                         "--", "--keywords", "strategic finance", "--limit", "3",
                         "--fields", "id,source,source_id,source_url")
    assert out.returncode == 2, out.stdout + out.stderr
    assert "no run is open" in out.stderr
    assert "--source may not appear" not in out.stderr


@pytest.mark.parametrize("shell", ["sh", "dash"])
def test_search_jobs_checks_both_recorded_values_before_it_goes_looking_for_a_run(
        tmp_workspace, shell):
    """The `--source` and `--query-id` guard, with no API key and no run open — the state CI runs in.

    Both values go to record-api-response.sh after the call, and it exits 2 on either one carrying a
    colon before it records anything, so checking them afterwards leaves a billed call with no `call`
    event naming it. Every other case covering this guard is `live`-marked and `needs_api`-gated, and
    CI holds no key. This one costs nothing, because the guard runs before resolve-run.sh and
    resolve-run.sh refuses first on a workspace with no run open.

    The last call passes values the guard has to let through, so it cannot be passing by refusing
    everything: it gets as far as resolve-run.sh and stops there, having spent nothing.

    Deleting the `check-record-args.sh` line makes both refused calls reach resolve-run.sh and print
    `no run is open` instead of the rule, so both go red with no key involved — measured 2026-08-11
    under sh and dash.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    assert shutil.which("agent-data", path=KEYLESS_PATH) is None, \
        "agent-data is on this PATH, so this case is not running in the state it exists for"

    for args in (["--query-id", "q", "--source", "linked:in"],
                 ["--query-id", "a:b", "--source", "linkedin"]):
        refused = keyless_search(shell, "--workspace", tmp_workspace, *args,
                                 "--", "--keywords", "x")
        assert refused.returncode == 2, refused.stdout + refused.stderr
        assert "may hold neither a comma nor a colon" in refused.stderr
        assert "no run is open" not in refused.stderr, \
            "the guard ran after resolve-run.sh, so in a workspace with a run open the call comes first"

    allowed = keyless_search(shell, "--workspace", tmp_workspace,
                             "--query-id", "strategic-finance", "--source", "linkedin",
                             "--", "--keywords", "x")
    assert allowed.returncode == 2, allowed.stdout + allowed.stderr
    assert "no run is open" in allowed.stderr
    assert "may hold" not in allowed.stderr


@pytest.mark.parametrize("shell", ["sh", "dash"])
@pytest.mark.parametrize("args,rule", [
    (["--query-id", "../../escaped", "--source", "linkedin"], "--query-id may hold no slash"),
    (["--query-id", "a/b", "--source", "linkedin"], "--query-id may hold no slash"),
    (["--query-id", "q", "--source", "a/b"], "--source may hold no slash"),
])
def test_search_jobs_refuses_a_value_that_would_name_some_other_file(
        tmp_workspace, shell, args, rule):
    """Both values name the response file, and neither may hold a slash.

    check-record-args.sh does not cover this: record-api-response.sh takes a slash in either value,
    so the check has to run where the path is built, the same way fetch-posting.sh checks
    `--posting-id`.

    A run is open here, so without the check the script would build the path, make the call and try
    to write the response into it.

    Nothing is spent and no key is needed: the check runs with the other argument checks, before
    resolve-run.sh and before the scratch directory is made — which is what the last assertion holds.
    """
    if shell == "dash" and not shutil.which("dash"):
        pytest.skip("dash is not installed here")
    opened = run_script(OPEN_RUN, tmp_workspace)
    assert opened.returncode == 0, opened.stdout + opened.stderr

    out = keyless_search(shell, "--workspace", tmp_workspace, *args, "--", "--keywords", "x")
    assert out.returncode == 2, out.stdout + out.stderr
    assert rule in out.stderr
    assert out.stdout == ""
    assert not (tmp_workspace / "runs" / ".scratch").exists(), \
        "the response directory was made, so the check ran after the path was built"
    assert not (tmp_workspace / "jobs.jsonl").exists(), "jobs.jsonl was created"


def test_the_listing_id_is_the_same_everywhere_it_is_written_down():
    """The listing id sits on 13 tracked lines. This compares all 13.

    Twelve of them are the output of
    `git grep -c f9a6ec16-0bfd -- . ':!tests/test_mechanics_scripts.py'`, run on 2026-08-12. The
    pattern is a prefix, so it skips the two places that mention `f9a6ec16` alone
    (fetch-posting.sh:133 and search-jobs.sh:160); this file is excluded so that the command does
    not count the line you are reading:

      fetch-posting.sh 2               a comment at :77 showing the search that produces a posting
                                       id, and the `get-posting` call at :136
      search-jobs.sh 3                 two measurement commands in the comment above the
                                       second-`--source` guard, at :80 and :89, and the
                                       `search-jobs` call at :165
      agent-data-reference/SKILL.md 2  the sentence at :22 that names the id, and the
                                       `get-posting` recipe at :58 an agent copies
      TESTING.md 4                     the `status` command at :43 and three `search-jobs`
                                       commands at :888, :897 and :906
      tests/test_fake_agent_data.py 1  that module's own `LISTING` at :4

    The thirteenth is `LISTING` at :55 of this file.

    TESTING.md and tests/test_fake_agent_data.py were added to the list on 2026-08-12, when the
    count was measured repo-wide rather than over the three files the first version read. The two
    do not carry the same risk, and both are held anyway: TESTING.md's four lines are commands a
    maintainer pastes at the real API, so a stale id there fails a release check with a confusing
    error, while test_fake_agent_data.py's constant goes to the local shim at tests/fake-agent-data
    and never reaches the network, so drift there spends nothing — it is held so the repository
    does not carry two ids for one listing. Each of the five files holds this uuid and no other,
    measured the same day.

    Every uuid in each file is collected, not the first one. Reading only `found[0]` left the two
    lines that spend metered calls unchecked, because a comment comes before the call in
    fetch-posting.sh and prose comes before the recipe in SKILL.md. Measured 2026-08-12: with
    `ids.add(found[0])`, changing fetch-posting.sh:136 to a zero uuid and running
    `python3 -m pytest -q -k listing_id` gave `1 passed`.

    This file's `LISTING` is folded in because two live cases above pass it to `agent-data call`
    directly — the `live_run` fixture at :176 and the fetch-posting refusal case at :6138. A change
    that reached the wrappers and not this constant would leave those two spending real calls
    against the old listing while every wrapper called the new one.

    This file is read through `LISTING` only; it is not scanned the way the five files are. So a
    literal written into a docstring here would not be compared, which is why none is: every other
    case names `LISTING` or writes `<the LISTING constant>` inside a quoted command, and the count
    command quoted above uses a prefix rather than the whole id.
    """
    pat = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    per_file = {"tests/test_mechanics_scripts.py (LISTING)": {LISTING}}
    for rel in ("skills/job-search-run/scripts/fetch-posting.sh",
                "skills/job-search-run/scripts/search-jobs.sh",
                "skills/agent-data-reference/SKILL.md",
                "TESTING.md",
                "tests/test_fake_agent_data.py"):
        found = pat.findall((ROOT / rel).read_text(encoding="utf-8"))
        assert found, f"no listing id in {rel}"
        per_file[rel] = set(found)
    ids = set().union(*per_file.values())
    assert len(ids) == 1, f"listing ids disagree: {per_file}"


# ------------------------ search-jobs.sh, fetch-posting.sh and record-judgment.sh together

@pytest.mark.live
@needs_api
def test_a_subagent_needs_only_the_posting_row(tmp_workspace):
    """One posting searched, read and judged against the real API, with no run id and no log path
    passed to any of the three scripts.

    Each of them asks resolve-run.sh, which reads the run id off the runs/.started-<run_id> marker
    on disk. That is what lets a subagent do a detail read with nothing but one posting row. In a
    run resolve-run.sh asks workspace-discovery.sh for the workspace as well; `--workspace` stands
    in for that here, because this workspace is a temporary directory discovery never finds.

    The `live_run` fixture is not used. It calls agent-data directly and hands the response to
    record-api-response.sh, so a chain built on it would leave search-jobs.sh out of the one case
    that is about the three scripts composing.

    The fetch runs before the judgment because record-judgment.sh records `--detail-read true` only
    when the log already holds a `detail` event for that posting under this run.

    Both response paths are read off the `response=` line the script printed rather than rebuilt
    from the run id, and the three values the fetch is given come off the surfaced row.

    The counts are what this chain did: one search call, one get-posting call, and those two are
    every metered call the run made. One posting had its text stored. postings_reviewed is asserted
    as well because it is the only one of these that reads the judgment, and it is 1 only when
    record-judgment.sh wrote the evaluated event under the run that surfaced the posting.

    The second open-run.sh call is not a check on open-run.sh. It is the only thing here that ties
    the run id these counts are read under to the marker on disk. Every other assertion would still
    hold if resolve-run.sh reported a run id no marker carries: all three scripts would record under
    that id, run-counts.sh is handed the same id, and the numbers would then agree with each other
    and with no run in the workspace. Measured 2026-08-12 with resolve-run.sh's last printf changed
    to report 2026-01-01T00-00-00Z: with these three lines deleted the case passes, and with them in
    place it fails on the last of them, printing that id against the one the marker names.
    """
    run_id = open_run_in(tmp_workspace)
    jobs = tmp_workspace / "jobs.jsonl"

    searched = subprocess.run(
        ["sh", str(SEARCH_JOBS), "--workspace", str(tmp_workspace),
         "--query-id", "strategic-finance", "--source", "linkedin",
         "--", "--keywords", "strategic finance", "--limit", "5"],
        capture_output=True, text=True)
    assert searched.returncode == 0, searched.stderr
    assert searched.stdout.startswith("response=")
    body = json.loads(
        pathlib.Path(searched.stdout.split("=", 1)[1].strip()).read_text(encoding="utf-8"))
    assert body["meta"]["request_id"].startswith("req_"), \
        "no request_id — the search did not reach the API"

    rows = [json.loads(l) for l in jobs.read_text(encoding="utf-8").splitlines() if l.strip()]
    surfaced = [x for x in rows if x["event"] == "surfaced"]
    assert surfaced, "the live search surfaced no rows — widen the keywords"
    row = surfaced[0]

    fetched = subprocess.run(
        ["sh", str(FETCH_POSTING), "--workspace", str(tmp_workspace),
         "--posting-id", row["posting_id_at_seen"], "--source-url", row["source_url"],
         "--source", row["source"]],
        capture_output=True, text=True)
    assert fetched.returncode == 0, fetched.stderr
    assert fetched.stdout.startswith("response=")
    posting = json.loads(
        pathlib.Path(fetched.stdout.split("=", 1)[1].strip()).read_text(encoding="utf-8"))
    assert posting["meta"]["request_id"].startswith("req_"), \
        "no request_id — the posting read did not reach the API"

    judged = subprocess.run(
        ["sh", str(JUDGE), "--workspace", str(tmp_workspace),
         "--source", row["source"], "--source-id", row["source_id"],
         "--detail-read", "true", "--relevant", "true", "--match", "strong",
         "--reasoning", "Owns the model."],
        capture_output=True, text=True)
    assert judged.returncode == 0, judged.stderr

    reopened = run_script(OPEN_RUN, tmp_workspace)
    assert reopened.returncode == 2, \
        "a second run opened over the one the three scripts recorded against"
    assert run_id in reopened.stderr, reopened.stderr

    r, kv = counts(jobs, run_id)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kv["calls_searches"] == "1"
    assert kv["calls_detail_reads"] == "1"
    assert kv["calls_total_metered"] == "2"
    assert kv["postings_detail_read"] == "1"
    assert kv["postings_reviewed"] == "1"


# ------------------------------------------------------------------------ posting-counts.sh

def postings(jobs, shell="sh"):
    """Run `posting-counts.sh` and return its result and its key/value lines as a dict.

    The split takes the first `=` only, matching `counts` above, so a value carrying one keeps it.
    """
    r = run_script(POSTINGS, jobs, shell=shell)
    return r, dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)


def ev(source_id, **kw):
    """One `evaluated` line, carrying the fields `posting-counts.awk` reads.

    The default is the shape a run writes for a posting it kept: relevant, banded, and no open
    question. Each case overrides only what it is about, and every count each case expects is
    worked out by hand from the lines that case writes.
    """
    d = {"event": "evaluated", "source": "linkedin", "source_id": source_id,
         "relevant": True, "match": "strong", "needs_human_check": False}
    d.update(kw)
    return json.dumps(d)


# Every mutation a docstring below names was run the same way: copy `posting-counts.awk` and
# `event-field.awk` to a directory outside the repository, make the change in the copy, and run
# `awk -f event-field.awk -f posting-counts.awk <log>` under /usr/bin/awk and again under mawk.


def test_a_posting_judged_not_relevant_is_counted_as_filtered(tmp_path):
    """A posting the run threw out is counted under `filtered`. The home card reports what the
    filtering found, so the postings it rejected are a number it shows rather than lines it drops.

    Two postings, one kept and one thrown out. All three counts are asserted, because a change that
    moves a posting from one key to another leaves the third key alone. Measured 2026-08-07 with
    the else branch's `filtered++` written `relevant++`: relevant=2 filtered=0 under both awks, the
    card naming two matches where the run kept one.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(ev("a") + "\n" + ev("b", relevant=False, match=None) + "\n")
    r, p = postings(jobs)
    assert r.returncode == 0, r.stderr
    assert p == {"relevant": "1", "to_confirm": "0", "filtered": "1"}


def test_an_evaluated_line_carrying_no_relevant_field_is_counted_as_filtered(tmp_path):
    """`record-judgment.awk` writes `relevant` on every judgment, but that is not the only way an
    `evaluated` event reaches the log: `event-log-append.sh` takes one written by hand on a host
    with no runtime, and it checks `source_id`, `source` and `same_role_as` — never `relevant`. The
    line is appended through that script here rather than written straight to the file, so the case
    stands on what that script accepts.

    A line carrying no verdict is not a posting a run kept, so it counts under `filtered`. Measured
    2026-08-07 with `rel[k] == "true"` written `rel[k] != "false"`: relevant=1 filtered=0 under
    both awks, putting every such line into the number the card leads with.
    """
    jobs = tmp_path / "jobs.jsonl"
    append = subprocess.run(
        ["sh", str(APPEND), str(jobs)], text=True, capture_output=True,
        input=json.dumps({"event": "evaluated", "source": "linkedin", "source_id": "a",
                          "match": "strong", "needs_human_check": False}))
    assert append.returncode == 0, append.stderr
    r, p = postings(jobs)
    assert r.returncode == 0, r.stderr
    assert p == {"relevant": "0", "to_confirm": "0", "filtered": "1"}


def test_rows_that_are_not_judgments_are_in_no_count(tmp_path):
    """A posting a search returned and nothing has judged is not a match and is not something the
    filtering rejected, and a `call` event is about a request rather than a posting and carries no
    `source_id` at all. A log holding only those lines prints three zeros.

    The event-type filter is the only thing that keeps them out. The END block sorts every posting
    it reaches into `relevant` or `filtered`, so there is no second check behind the filter — that
    changed when the five status counts became these three. Measured 2026-08-07 with
    `if (jval($0, "event") != "evaluated") next` deleted: filtered=2 under both awks — one for the
    posting nobody has judged, whose `surfaced` and `queued` lines share a key, and one for the
    `call` event, which carries neither `source` nor `source_id` and so keys to two empty strings
    joined by SUBSEP.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"surfaced","source":"linkedin","source_id":"a"}\n'
        '{"event":"call","route":"search-jobs","ok":true}\n'
        '{"event":"queued","source":"linkedin","source_id":"a"}\n')
    r, p = postings(jobs)
    assert r.returncode == 0, r.stderr
    assert p == {"relevant": "0", "to_confirm": "0", "filtered": "0"}


def test_to_confirm_counts_over_the_relevant_postings_only(tmp_path):
    """`to_confirm` is the count of matches the user still has to confirm, so it counts over the
    postings `relevant` counts. A posting the run threw out is behind the `filtered` number, and an
    open question on it is in no number here.

    Three postings: one kept with an open question, one kept without, one thrown out with an open
    question. Measured 2026-08-07 with `confirm++` moved above the relevance branch, so that the
    thrown-out posting's open question is counted too: to_confirm=2 beside relevant=2 under both
    awks — one more question than there are postings the card offers to confirm.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(ev("a", needs_human_check=True) + "\n" +
                    ev("b", match="weak") + "\n" +
                    ev("c", relevant=False, match=None, needs_human_check=True) + "\n")
    r, p = postings(jobs)
    assert r.returncode == 0, r.stderr
    assert p == {"relevant": "2", "to_confirm": "1", "filtered": "1"}


def test_a_second_posting_for_the_same_role_is_counted_once(tmp_path):
    """One opening reached by two queries gets an `evaluated` line each, and the second names the
    first in `same_role_as` — `job-search-run/SKILL.md:125`. It is the same job, so it is one entry.

    The second line is left out of every count rather than moved into `filtered`, which is why all
    three are asserted. Measured 2026-08-07 with `if (k in alias) continue` deleted: relevant=2
    under both awks, the card reporting two jobs where the user has one to apply to.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(ev("a", source="ashby") + "\n" +
                    ev("b", source="ashby", same_role_as="ashby:a") + "\n")
    r, p = postings(jobs)
    assert r.returncode == 0, r.stderr
    assert p == {"relevant": "1", "to_confirm": "0", "filtered": "0"}


def test_an_empty_log_prints_zeroes(tmp_path):
    """A workspace set up and never run has an empty `jobs.jsonl`, and the home card is rendered
    from it. Every key is printed at zero rather than left out, so the caller reads three numbers
    instead of deciding for itself what a missing key means."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("")
    r, p = postings(jobs)
    assert r.returncode == 0
    assert p == {"relevant": "0", "to_confirm": "0", "filtered": "0"}


def test_two_postings_that_would_share_a_pipe_joined_key_are_counted_separately(tmp_path):
    """The posting key joins `source` and `source_id` with SUBSEP, the 0x1c byte, which cannot reach
    a value — the reason is written out at `run-counts.awk:14-16`. A `|` can: `record-judgment.sh`'s
    `reject_id` refuses only a control character and a backslash, so source `s` with source_id `x|y`
    and source `s|x` with source_id `y` are both recorded, and both join to `s|x|y`.

    Measured 2026-08-07 with the key joined on `|` instead: relevant=1 under both awks where two
    postings were judged relevant, and the card shows one job where the user has two.
    `run-matches.awk` is pinned against the same collision at
    `test_two_postings_that_would_share_a_pipe_joined_key_are_both_listed`.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(ev("x|y", source="s") + "\n" + ev("y", source="s|x") + "\n")
    r, p = postings(jobs)
    assert r.returncode == 0, r.stderr
    assert p == {"relevant": "2", "to_confirm": "0", "filtered": "0"}


def test_a_hand_written_log_with_two_judgments_for_one_posting_takes_the_later_line(tmp_path):
    """No run writes this log. Both append paths refuse a second `evaluated` event for a
    `(source, source_id)` that already has one — `event-log-append.sh:21-23` states the rule and
    `:105-111` enforces it, and `record-judgment.sh`'s exit list reads "Exit 0: recorded, or this
    posting already carries exactly this judgment" — so only a log written or edited by hand
    reaches this case. What is pinned here is `posting-counts.awk`'s behavior, not the product's.

    It is pinned because the awk's header states it: the three assignments in the main block are
    unconditional, so a hand-edited log with two judgments for one posting takes the later line.
    Measured 2026-08-07 with `rel[k]` set only the first time a key is seen: relevant=1 filtered=0
    under both awks, where the later judgment is the one that threw the posting out.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(ev("a") + "\n" + ev("a", relevant=False, match=None) + "\n")
    r, p = postings(jobs)
    assert r.returncode == 0, r.stderr
    assert p == {"relevant": "0", "to_confirm": "0", "filtered": "1"}


def test_posting_counts_for_a_log_that_is_not_there_exit_two_and_print_nothing(tmp_path):
    """A workspace whose log is missing is not a workspace where the filtering found nothing.
    Printing three zeros would show an empty home card for a path typed wrong, and the user would
    read it as having no matches rather than as a broken workspace. `run-counts.sh` refuses the same
    way, at `test_counts_for_a_log_that_is_not_there_exit_two_and_print_nothing`."""
    r, p = postings(tmp_path / "absent.jsonl")
    assert r.returncode == 2
    assert p == {}
    assert "no such file" in r.stderr


@pytest.mark.skipif(not shutil.which("dash"), reason="dash is not installed here")
def test_the_posting_counts_run_under_dash(tmp_path):
    """`/bin/sh` is bash on the machine this was written on and dash on the CI runner, and a
    construct that works under one and not the other reaches CI as a script that cannot run at all.
    `sh -n` and `dash -n` do not catch it: measured 2026-08-07 with this script's `[ -f "$jobs" ]`
    written `[[ -f "$jobs" ]]`, from a copy under an absolute temp path — both syntax checks passed
    and the script ran under `sh`, and under `dash` it printed `[[: not found` and exited 2 on a log
    that is there.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(ev("a") + "\n" + ev("b", relevant=False, match=None) + "\n")
    r, p = postings(jobs, shell="dash")
    assert r.returncode == 0, r.stderr
    assert p == {"relevant": "1", "to_confirm": "0", "filtered": "1"}


# ------------------------------ appending onto a log that ends without a newline

# One `surfaced` event of this run, compact, in the shape record-api-response.sh writes and every
# lookup greps for. The tests below write it as the whole file, so the log they hand an appender ends
# without a newline after its last event. A hand edit, a truncated copy, or an editor that does not
# end its files with one all produce that.
def unterminated_surfaced(source="linkedin", source_id="100"):
    return (
        '{"event":"surfaced","run_id":"%s","query_id":"q","source":"%s","source_id":"%s",'
        '"posting_id_at_seen":"jp_%s","source_url":"https://example.invalid/%s",'
        '"title":"Staff Engineer","company_name":"Acme","location_display":"Remote, USA",'
        '"salary_display":null,"employment_type":null,"department_name":null,"team_name":null,'
        '"is_remote":true,"workplace_type":null,"posted_at":"2026-08-01T00:00:00Z",'
        '"detail_available":true,"ts":"2026-08-08T10:00:10Z"}'
        % (RID, source, source_id, source_id, source_id)
    )


def physical_lines(jobs):
    """Every line of the log, blank ones included and none of them parsed.

    `lines()` drops the blank lines and parses the rest, and neither suits this section. A blank
    first line is missing from what it returns, so a test using it counts the same number of lines
    either way; and two events joined onto one line raise a JSONDecodeError out of the helper instead
    of failing on the line count these tests assert.
    """
    return jobs.read_text(encoding="utf-8").splitlines()


# A `call` event that stops partway through a field name: no closing brace, and no newline after it.
# That is what an awk leaves on stdout when it dies in the middle of printing a line. `awk_shim`
# writes the spill inside a single-quoted shell string, so this carries no apostrophe.
HALF_CALL = '{"event":"call","run_id":"%s","ts":"2026-08-08T10:00:00Z","route":' % RID


def two_row_search_body(tmp_path):
    """A search response written here rather than taken from a fixture, so the line counts the two
    search cases assert are counted by hand: two rows, source_ids 100 and 200.

    Each row carries the four fields the row builder requires — source, source_id, id and source_url
    — plus the three the surfaced event displays.
    """
    body = tmp_path / "search.json"
    body.write_text(json.dumps({
        "data": {
            "query": {"id": "q"},
            "results": [
                {"source": "linkedin", "source_id": "100", "id": "jp_100",
                 "source_url": "https://example.invalid/100", "title": "One",
                 "company_name": "Acme", "location_display": "Remote, USA"},
                {"source": "linkedin", "source_id": "200", "id": "jp_200",
                 "source_url": "https://example.invalid/200", "title": "Two",
                 "company_name": "Acme", "location_display": "Austin, TX"},
            ]},
        "meta": {"request_id": "req_1"}}), encoding="utf-8")
    return body


def test_a_hand_written_event_appended_onto_an_unterminated_line_gets_its_own_line(tmp_path):
    """event-log-append.sh — the standalone path a host takes when it writes an event itself.

    Every field reader takes a key's first occurrence, so an event appended onto the last line of a
    log that ends mid-line is read as the earlier event and lost. Measured 2026-08-08 on a posting
    that had just been judged relevant, with the judgment joined onto its surfaced event:
    `sh run-counts.sh <log> R` gave `postings_reviewed=0 postings_unreviewed=1`,
    `sh run-matches.sh <log> R strong` printed no rows, and `sh posting-counts.sh <log>` gave
    `relevant=0 to_confirm=0 filtered=0`.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(unterminated_surfaced(), encoding="utf-8")
    r = run_sh(APPEND, [str(jobs)], input_text=evaluated("linkedin", "100") + "\n")
    assert r.returncode == 0, r.stderr
    rows = physical_lines(jobs)
    assert len(rows) == 2, rows
    assert json.loads(rows[0])["event"] == "surfaced"
    assert json.loads(rows[1])["event"] == "evaluated"


def test_a_queued_event_appended_onto_an_unterminated_line_gets_its_own_line(tmp_path):
    """queue-detail-read.sh — the event is built in awk and the redirect appends it.

    Joined onto the surfaced event, the queued event never reaches the list a reader works from.
    Measured 2026-08-08: `sh queue-detail-read.sh <log> --run-id R --source linkedin --source-id
    100` exited 0 leaving one physical line, and `sh list-detail-read-queue.sh <log> R` then printed
    nothing at exit 0 for the posting it had just queued.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(unterminated_surfaced(), encoding="utf-8")
    r = run_script(QUEUE, jobs, "--run-id", RID, "--source", "linkedin", "--source-id", "100")
    assert r.returncode == 0, r.stderr
    rows = physical_lines(jobs)
    assert len(rows) == 2, rows
    assert json.loads(rows[0])["event"] == "surfaced"
    assert json.loads(rows[1])["event"] == "queued"


def test_a_call_event_appended_onto_an_unterminated_line_gets_its_own_line(tmp_path):
    """record-api-response.sh's `emit_call`, driven on an error body so the call event is the only
    thing the script writes and nothing else can be what puts a second line in the log.

    A run's metered-call count is worked out from these events, so a joined one is a call the run
    stops counting.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(unterminated_surfaced(), encoding="utf-8")
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "detail.error.json", "--route", "get-posting")
    assert r.returncode == 1, r.stdout + r.stderr
    rows = physical_lines(jobs)
    assert len(rows) == 2, rows
    assert json.loads(rows[0])["event"] == "surfaced"
    assert json.loads(rows[1])["event"] == "call"


def test_a_detail_event_appended_onto_an_unterminated_line_gets_its_own_line(tmp_path):
    """record-api-response.sh's get-posting path, driven whole on a log that ends without a newline.

    The three expected lines are the seeded surfaced event, the call event, and the detail event, in
    that order — the script emits the call before it appends the posting. The guard this case holds
    is therefore the one inside `emit_call`, which is the guard that runs against the seeded line.
    Measured 2026-08-08: deleting that one fails this case, and deleting the one before the detail
    `cat` does not. The `cat` guard has its own case at
    `test_a_detail_event_is_not_appended_onto_a_half_written_call_event`.
    """
    body = json.loads((FIXTURES / "detail.ashby.json").read_text())["data"]
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(unterminated_surfaced(body["source"], body["source_id"]), encoding="utf-8")
    r = record_detail(jobs, "detail.ashby.json")
    assert r.returncode == 0, r.stderr
    rows = physical_lines(jobs)
    assert len(rows) == 3, rows
    assert [json.loads(l)["event"] for l in rows] == ["surfaced", "call", "detail"]


def test_surfaced_rows_appended_onto_an_unterminated_line_get_their_own_lines(tmp_path):
    """record-api-response.sh's search path, driven whole on a log that ends without a newline.

    The response is written here with two rows rather than taken from a fixture, so the four lines
    expected below are counted by hand: the seeded event, the call event, and one surfaced event per
    row. The seeded posting carries source_id 999, which neither row does, so nothing is skipped as
    already surfaced. As on the detail path above, the guard this case holds is the one inside
    `emit_call`; the guard before the rows `cat` has its own case at
    `test_the_first_surfaced_row_is_not_appended_onto_a_half_written_call_event`.
    """
    body = two_row_search_body(tmp_path)
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(unterminated_surfaced(source_id="999"), encoding="utf-8")
    r = run_script(RECORD_API, RID, jobs, body, "--route", "search-jobs", "--query-id", "q")
    assert r.returncode == 0, r.stderr
    rows = physical_lines(jobs)
    assert len(rows) == 4, rows
    assert [json.loads(l)["event"] for l in rows] == ["surfaced", "call", "surfaced", "surfaced"]
    assert [json.loads(rows[i])["source_id"] for i in (0, 2, 3)] == ["999", "100", "200"]


def test_a_detail_event_is_not_appended_onto_a_half_written_call_event(tmp_path):
    """The `end_last_line` before the detail `cat` — the guard that catches a call event this script
    only half wrote.

    `record-api-response.sh` sets `-u` and never `-e` — `grep -n '^set ' ` on it gives a single line
    — and no call site checks what `emit_call` returned, so an awk that died partway through the
    call event leaves a fragment with no newline after it and the script appends the posting anyway.
    The shim replaces only the awk whose argv holds `RAR_QUERY`:
    `grep -n RAR_QUERY skills/job-search-run/scripts/*.sh` gives two lines, the environment
    assignment and the reference inside `emit_call`'s program, so the marker selects that awk and no
    other.

    The seeded log ends with a newline, so the guard inside `emit_call` has nothing to do and the
    only line ending without one is the fragment the shim writes. Measured 2026-08-08 with this
    guard deleted: two physical lines, the detail event written onto the end of the fragment, and the
    stored posting then unreachable to every reader. The exit code below is what the script does
    today rather than a decision this case defends — a failed call event does not stop it.
    """
    body = json.loads((FIXTURES / "detail.ashby.json").read_text())["data"]
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(unterminated_surfaced(body["source"], body["source_id"]) + "\n",
                    encoding="utf-8")
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "detail.ashby.json", "--route", "get-posting",
                   env=awk_shim(tmp_path, "RAR_QUERY", HALF_CALL))
    assert r.returncode == 0, r.stdout + r.stderr
    rows = physical_lines(jobs)
    assert len(rows) == 3, rows
    assert json.loads(rows[0])["event"] == "surfaced"
    assert rows[1] == HALF_CALL                       # the fragment, whole and on its own line
    assert json.loads(rows[2])["event"] == "detail"


def test_the_first_surfaced_row_is_not_appended_onto_a_half_written_call_event(tmp_path):
    """The `end_last_line` before the rows `cat`, reached the same way as the detail one above.

    The row that joins onto the fragment is the first one, so the count and the ids are both asserted
    — a test on the count alone would still pass with row 100 inside line 1 rather than on its own.
    Measured 2026-08-08 with this guard deleted: three physical lines, and `"source_id":"100"`
    reachable only inside the fragment line.
    """
    body = two_row_search_body(tmp_path)
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(unterminated_surfaced(source_id="999") + "\n", encoding="utf-8")
    r = run_script(RECORD_API, RID, jobs, body, "--route", "search-jobs", "--query-id", "q",
                   env=awk_shim(tmp_path, "RAR_QUERY", HALF_CALL))
    assert r.returncode == 0, r.stdout + r.stderr
    rows = physical_lines(jobs)
    assert len(rows) == 4, rows
    assert json.loads(rows[0])["source_id"] == "999"
    assert rows[1] == HALF_CALL                       # the fragment, whole and on its own line
    assert [json.loads(rows[i])["source_id"] for i in (2, 3)] == ["100", "200"]


def test_a_judgment_appended_onto_an_unterminated_line_gets_its_own_line(tmp_path):
    """record-judgment.sh — the appender the defect was found on.

    The counts are asserted as well as the line count, because a wrong number in front of the user
    is what the joined line produces: one posting surfaced, judged relevant with a strong match, so
    the run reviewed 1 of the 1 it surfaced and 1 of them is a strong match.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(unterminated_surfaced(), encoding="utf-8")
    r = run_script(JUDGE, jobs, "--run-id", RID, "--source", "linkedin", "--source-id", "100",
                   "--detail-read", "false", "--relevant", "true", "--match", "strong",
                   "--needs-human-check", "false", "--reasoning", "fits")
    assert r.returncode == 0, r.stderr
    rows = physical_lines(jobs)
    assert len(rows) == 2, rows
    assert json.loads(rows[0])["event"] == "surfaced"
    assert json.loads(rows[1])["event"] == "evaluated"
    _, c = counts(jobs)
    assert c["postings_surfaced"] == "1"
    assert c["postings_reviewed"] == "1"
    assert c["postings_unreviewed"] == "0"
    assert c["match_strong"] == "1"


@pytest.mark.skipif(not shutil.which("dash"), reason="dash is not installed here")
def test_the_judgment_gets_its_own_line_under_dash_too(tmp_path):
    """The guard reads `wc -l`, whose output carries leading spaces under BSD `wc` and none under
    GNU, and compares it with `-eq`. Measured 2026-08-08 on this machine, `tail -c1 <file> | wc -l`
    prints `       0` for a file that ends mid-line, and `[ "       0" -eq 0 ]` is true under `sh`,
    `dash` and `bash` alike — but the comparison is the kind a strict shell can refuse, so one
    appender is driven end to end under `dash` here.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(unterminated_surfaced(), encoding="utf-8")
    r = run_script(JUDGE, jobs, "--run-id", RID, "--source", "linkedin", "--source-id", "100",
                   "--detail-read", "false", "--relevant", "true", "--match", "strong",
                   "--reasoning", "fits", shell="dash")
    assert r.returncode == 0, r.stderr
    rows = physical_lines(jobs)
    assert len(rows) == 2, rows
    assert json.loads(rows[1])["event"] == "evaluated"


def test_a_hand_written_event_appended_onto_an_empty_log_writes_no_blank_first_line(tmp_path):
    """A log with no bytes in it must not gain a blank line above its first event.

    This is what the `[ -s "$jobs" ]` half of the guard holds: without it, ending the last line of
    an empty file writes a newline into a file that has no line to end. Measured 2026-08-08, a
    leading blank line changes no number today — `run-counts.sh` and `posting-counts.sh` print the
    same values with and without one — so what this holds is the shape the log is documented to
    have, one JSON object per physical line, and not a count.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("", encoding="utf-8")
    r = run_sh(APPEND, [str(jobs)], input_text=evaluated("linkedin", "100") + "\n")
    assert r.returncode == 0, r.stderr
    rows = physical_lines(jobs)
    assert len(rows) == 1, rows
    assert json.loads(rows[0])["event"] == "evaluated"


def test_a_call_event_appended_onto_a_log_the_script_just_created_writes_no_blank_first_line(tmp_path):
    """record-api-response.sh creates the log itself when it is not there, so it meets an empty file
    on the first call of every new run — the same case as above, reached the way a run reaches it."""
    jobs = tmp_path / "jobs.jsonl"
    assert not jobs.exists()
    r = run_script(RECORD_API, RID, jobs, FIXTURES / "detail.error.json", "--route", "get-posting")
    assert r.returncode == 1, r.stdout + r.stderr
    rows = physical_lines(jobs)
    assert len(rows) == 1, rows
    assert json.loads(rows[0])["event"] == "call"


# ------------------------------------------------------------------- POSIX portability

def test_git_records_every_script_as_executable():
    """Each script is 100755 in git's index — the mode every other checkout of this repo gets.

    search-jobs.sh was committed at 100644 while the other 11 `.sh` files in
    skills/job-search-run/scripts/ were 100755 (`git ls-tree 683484e
    skills/job-search-run/scripts/`, measured 2026-08-11), and no test read a file mode, so the
    suite stayed green.

    `git ls-files -s` is read rather than `Path.stat`, because the two disagree exactly when
    someone changes the working-tree bit without staging it, and the mode git records is the one
    that ships. A script git does not track prints no row here at all, which is why the paths are
    compared as well as the modes.
    """
    rels = sorted(str(s.relative_to(ROOT)) for s in ALL_SCRIPTS)
    r = subprocess.run(["git", "ls-files", "-s", "--", *rels],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    # `<mode> <object> <stage>\t<path>`, one line per tracked path.
    modes = dict(reversed(line.split("\t", 1)) for line in r.stdout.splitlines())
    modes = {path: meta.split()[0] for path, meta in modes.items()}
    assert sorted(modes) == rels, \
        "git does not track these: %s" % sorted(set(rels) - set(modes))
    assert {p: m for p, m in modes.items() if m != "100755"} == {}, \
        "git records these as non-executable: %s" % {p: m for p, m in modes.items() if m != "100755"}


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
