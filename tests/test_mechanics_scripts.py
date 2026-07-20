"""Unit tests for the bundled portable-shell mechanics scripts (P4/T4.1, AAS-FORM-08).

The fiddly deterministic mechanics that skills used to execute as model-run prose contracts are
now bundled as portable POSIX-`sh` scripts under `shared/scripts/mechanics/` (their single home).
Each test drives one script via subprocess against a temp fixture and asserts the PINNED behavior
from `shared/references/internals.md` (registry / workspace discovery / scheduling) and
`shared/references/conventions.md` (the jobs.jsonl event-line contract + dedup / append operations).

Scripts are invoked through `sh` (and, where present, strict `dash`) — never `bash` — so a bash-only
construct fails the suite. The prose contracts these scripts mirror remain in place as the D10 fallback;
these tests pin the scripted form to that same behavior.
"""
import os
import pathlib
import re
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MECH = ROOT / "shared" / "scripts" / "mechanics"
DEDUP = MECH / "dedup.sh"
APPEND = MECH / "event-log-append.sh"
SCHEDULE = MECH / "schedule-line.sh"
DISCOVERY = MECH / "workspace-discovery.sh"
LIFECYCLE_APPEND = MECH / "lifecycle-append.sh"
LIFECYCLE_FOLD = MECH / "lifecycle-fold.sh"
SUPPORT = MECH / "support-summary.sh"
LIFECYCLE_REFERENCE = ROOT / "shared" / "references" / "run-lifecycle.md"
INTERNALS_REFERENCE = ROOT / "shared" / "references" / "internals.md"

ALL_SCRIPTS = [DEDUP, APPEND, SCHEDULE, DISCOVERY, LIFECYCLE_APPEND, LIFECYCLE_FOLD, SUPPORT]

RUN_ID = "2026-07-16T14-30-00Z"
RUN_STARTED = "2026-07-16T10:30:00-04:00"
RUN_TRIGGER = "manual"
RUN_SCHEDULER_ID = "-"

# A contract-valid single-line `evaluated` event (conventions.md §jobs.jsonl event-line contract).
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


def lifecycle_append(ledger, command, *args, run_id=RUN_ID, ts=RUN_STARTED, shell="sh"):
    """Append one lifecycle event through the fixed coordinator interface."""
    return subprocess.run(
        [shell, str(LIFECYCLE_APPEND), str(ledger), command, run_id, ts, *args],
        capture_output=True,
        text=True,
    )


def lifecycle_fold(ledger, workspace, shell="sh"):
    """Fold a ledger and parse its normalized key=value output."""
    r = subprocess.run(
        [shell, str(LIFECYCLE_FOLD), str(ledger), str(workspace)],
        capture_output=True,
        text=True,
    )
    values = {}
    for line in r.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return r, values


def start_lifecycle(
    workspace,
    run_id=RUN_ID,
    ts=RUN_STARTED,
    trigger=RUN_TRIGGER,
    scheduler_id=RUN_SCHEDULER_ID,
    source_order="linkedin",
):
    ledger = workspace / "runs" / (".lifecycle-%s.jsonl" % run_id)
    r = lifecycle_append(
        ledger, "start", trigger, scheduler_id, source_order, run_id=run_id, ts=ts
    )
    assert r.returncode == 0, r.stderr
    return ledger


def append_ok(ledger, command, *args, run_id=RUN_ID, ts=RUN_STARTED):
    r = lifecycle_append(ledger, command, *args, run_id=run_id, ts=ts)
    assert r.returncode == 0, r.stderr


def advance_to_finalizing(ledger, with_posting=True, with_attempt=True):
    append_ok(ledger, "phase", "searching")
    if with_attempt:
        append_ok(
            ledger, "attempt-started", "attempt-1", "initial_search", "search-1", "1"
        )
        append_ok(ledger, "attempt-accounted", "attempt-1", "true", "success", "req-1")
    if with_posting:
        append_ok(ledger, "posting", "linkedin", "posting-1", "queued", "revision-1")
    append_ok(ledger, "phase", "selection_settled")
    if with_posting:
        append_ok(ledger, "phase", "reviewing_initial_batch")
        append_ok(ledger, "posting", "linkedin", "posting-1", "evaluating", "revision-1")
        append_ok(ledger, "posting", "linkedin", "posting-1", "evaluated", "revision-1")
        append_ok(ledger, "posting", "linkedin", "posting-1", "presented", "revision-1")
    else:
        append_ok(ledger, "phase", "reviewing_initial_batch")
    append_ok(ledger, "phase", "early_results_shown")
    append_ok(ledger, "milestone", "early_results_shown")
    append_ok(ledger, "phase", "reviewing_remaining")
    append_ok(ledger, "phase", "finalizing")


def write_final_artifacts(workspace, run_id=RUN_ID, digest_date="2026-07-16"):
    runs = workspace / "runs"
    reports = workspace / "reports"
    runs.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    (runs / ("%s.json" % run_id)).write_text('{"run_id":"%s"}\n' % run_id)
    (reports / ("%s-digest.md" % digest_date)).write_text("# Digest\n")


def record_final_artifact_milestones(ledger):
    append_ok(ledger, "milestone", "final_run_record_written")
    append_ok(ledger, "milestone", "final_digest_written")


def write_lifecycle_rows(workspace, *rows, run_id=RUN_ID):
    ledger = workspace / "runs" / (".lifecycle-%s.jsonl" % run_id)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("\n".join(rows) + "\n")
    return ledger


def started_row(
    run_id=RUN_ID,
    ts=RUN_STARTED,
    trigger=RUN_TRIGGER,
    scheduler_id=None,
    source_order="linkedin",
):
    scheduler_json = "null" if scheduler_id is None else '"%s"' % scheduler_id
    return ('{"event":"run_started","run_id":"%s","ts":"%s","phase":"preflight",'
            '"trigger":"%s","scheduler_id":%s,"source_order":"%s"}') % (
        run_id,
        ts,
        trigger,
        scheduler_json,
        source_order,
    )


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
    """Missing jobs.jsonl = empty known set (conventions.md) -> every candidate is new."""
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
    (conventions.md idempotency: never write a duplicate evaluated event for a known pair)."""
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
    """Every evaluated event carries a non-empty `"source"` (conventions.md event-line contract)."""
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
    (internals.md: 'never fall through to the other candidates')."""
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


# --------------------------------------------------------------- lifecycle ledger

def test_lifecycle_start_requires_exact_trigger_and_scheduler_attribution(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = workspace / "runs" / (".lifecycle-%s.jsonl" % RUN_ID)

    missing = lifecycle_append(ledger, "start")
    assert missing.returncode != 0
    assert not ledger.exists()

    invalid_combinations = [
        ("manual", "scheduler-1"),
        ("scheduled", "-"),
        ("canary", "-"),
        ("interactive", "-"),
    ]
    for trigger, scheduler_id in invalid_combinations:
        rejected = lifecycle_append(ledger, "start", trigger, scheduler_id, "linkedin")
        assert rejected.returncode != 0
        assert not ledger.exists()


@pytest.mark.parametrize("trigger", ["scheduled", "canary"])
def test_lifecycle_start_persists_scheduler_attribution_without_normalizing(
    tmp_path, trigger
):
    workspace = tmp_path / trigger
    ledger = start_lifecycle(
        workspace,
        trigger=trigger,
        scheduler_id="scheduler-prod-1",
    )
    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["trigger"] == trigger
    assert state["scheduler_id"] == "scheduler-prod-1"
    assert ledger.read_text().splitlines()[0] == started_row(
        trigger=trigger,
        scheduler_id="scheduler-prod-1",
    )


def test_lifecycle_start_persists_exact_immutable_source_order(tmp_path):
    workspace = tmp_path / "source-order"
    ledger = workspace / "runs" / (".lifecycle-%s.jsonl" % RUN_ID)
    started = lifecycle_append(
        ledger,
        "start",
        "manual",
        "-",
        "linkedin+ashby+greenhouse",
    )
    assert started.returncode == 0, started.stderr

    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["source_order"] == "linkedin+ashby+greenhouse"
    assert '"source_order":"linkedin+ashby+greenhouse"' in ledger.read_text()
    append_ok(ledger, "phase", "searching")
    assert lifecycle_append(
        ledger, "posting", "lever", "fixture:job", "queued", "revision-1"
    ).returncode != 0

    for invalid in ("", "linkedin+linkedin", "linkedin+unknown", "ashby+linkedin+"):
        rejected_workspace = tmp_path / ("invalid-" + (invalid or "empty"))
        rejected_ledger = rejected_workspace / "runs" / (
            ".lifecycle-%s.jsonl" % RUN_ID
        )
        rejected = lifecycle_append(
            rejected_ledger,
            "start",
            "manual",
            "-",
            invalid,
        )
        assert rejected.returncode != 0, invalid
        assert not rejected_ledger.exists()


@pytest.mark.parametrize(
    "trigger,scheduler_json",
    [
        ("manual", '"scheduler-prod-1"'),
        ("scheduled", "null"),
        ("canary", "null"),
        ("interactive", "null"),
    ],
)
def test_lifecycle_fold_rejects_invalid_trigger_scheduler_attribution(
    tmp_path, trigger, scheduler_json
):
    workspace = tmp_path / trigger / scheduler_json.replace('"', "")
    row = (
        '{"event":"run_started","run_id":"%s","ts":"%s","phase":"preflight",'
        '"trigger":"%s","scheduler_id":%s,"source_order":"linkedin"}'
        % (RUN_ID, RUN_STARTED, trigger, scheduler_json)
    )
    ledger = write_lifecycle_rows(workspace, row)
    folded, _ = lifecycle_fold(ledger, workspace)
    assert folded.returncode != 0


def test_lifecycle_rejects_phase_skips_late_selection_and_posting_state_shortcuts(tmp_path):
    workspace = tmp_path / "phase-skip"
    ledger = start_lifecycle(workspace)
    assert lifecycle_append(ledger, "phase", "selection_settled").returncode != 0

    workspace = tmp_path / "late-selection"
    ledger = start_lifecycle(workspace)
    append_ok(ledger, "phase", "searching")
    append_ok(ledger, "phase", "selection_settled")
    assert lifecycle_append(
        ledger, "posting", "linkedin", "late-posting", "queued", "revision-1"
    ).returncode != 0

    workspace = tmp_path / "posting-shortcut"
    ledger = start_lifecycle(workspace)
    append_ok(ledger, "phase", "searching")
    append_ok(ledger, "posting", "linkedin", "posting-1", "queued", "revision-1")
    append_ok(ledger, "phase", "selection_settled")
    append_ok(ledger, "phase", "reviewing_initial_batch")
    assert lifecycle_append(
        ledger, "posting", "linkedin", "posting-1", "evaluated", "revision-1"
    ).returncode != 0
    append_ok(ledger, "posting", "linkedin", "posting-1", "evaluating", "revision-1")
    assert lifecycle_append(
        ledger, "posting", "linkedin", "posting-1", "presented", "revision-1"
    ).returncode != 0

def test_lifecycle_append_emits_canonical_rows_for_every_command(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace)
    append_ok(ledger, "phase", "searching")
    append_ok(ledger, "posting", "linkedin", "posting-1", "queued", "revision-1")
    append_ok(
        ledger, "attempt-started", "attempt-1", "detail_read", "detail-posting-1", "1"
    )
    append_ok(
        ledger, "attempt-accounted", "attempt-1", "true", "terminal_failure", "req-1"
    )
    append_ok(ledger, "attempt-resolved", "attempt-1", "summary_fallback")
    append_ok(ledger, "revision", "revision-2")
    append_ok(ledger, "milestone", "early_results_shown")
    append_ok(ledger, "close", "blocked", "E-TEST-BLOCK")

    assert ledger.read_text().splitlines() == [
        ('{"event":"run_started","run_id":"%s","ts":"%s","phase":"preflight",'
         '"trigger":"manual","scheduler_id":null,"source_order":"linkedin"}')
        % (RUN_ID, RUN_STARTED),
        '{"event":"phase_changed","run_id":"%s","ts":"%s","phase":"searching"}'
        % (RUN_ID, RUN_STARTED),
        ('{"event":"posting_state","run_id":"%s","ts":"%s","source":"linkedin",'
         '"source_id":"posting-1","state":"queued","brief_revision":"revision-1"}')
        % (RUN_ID, RUN_STARTED),
        ('{"event":"attempt_started","run_id":"%s","ts":"%s","attempt_id":"attempt-1",'
         '"operation":"detail_read","logical_operation_id":"detail-posting-1",'
         '"attempt_number":1}') % (RUN_ID, RUN_STARTED),
        ('{"event":"attempt_accounted","run_id":"%s","ts":"%s","attempt_id":"attempt-1",'
         '"metered":true,"outcome":"terminal_failure","request_id":"req-1"}')
        % (RUN_ID, RUN_STARTED),
        ('{"event":"attempt_resolved","run_id":"%s","ts":"%s",'
         '"attempt_id":"attempt-1","resolution":"summary_fallback"}')
        % (RUN_ID, RUN_STARTED),
        '{"event":"brief_revision","run_id":"%s","ts":"%s","brief_revision":"revision-2"}'
        % (RUN_ID, RUN_STARTED),
        '{"event":"milestone","run_id":"%s","ts":"%s","milestone":"early_results_shown"}'
        % (RUN_ID, RUN_STARTED),
        ('{"event":"run_closed","run_id":"%s","ts":"%s","close_state":"blocked",'
         '"internal_code":"E-TEST-BLOCK"}') % (RUN_ID, RUN_STARTED),
    ]


def test_lifecycle_happy_path_needs_artifacts_milestones_and_complete_close(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace)
    advance_to_finalizing(ledger)
    write_final_artifacts(workspace)
    record_final_artifact_milestones(ledger)

    before_close, state = lifecycle_fold(ledger, workspace)
    assert before_close.returncode == 0, before_close.stderr
    assert state == {
        "run_id": RUN_ID,
        "trigger": "manual",
        "scheduler_id": "null",
        "source_order": "linkedin",
        "phase": "finalizing",
        "selected": "1",
        "evaluated": "1",
        "terminally_skipped": "0",
        "presented": "1",
        "remaining": "0",
        "in_flight": "0",
        "attempts_started": "1",
        "attempts_accounted": "1",
        "blocking_attempt_failures": "0",
        "final_run_record_written": "true",
        "final_digest_written": "true",
        "closed": "false",
        "close_state": "open",
        "ready_to_close": "true",
        "can_complete": "false",
    }

    closed = lifecycle_append(ledger, "close", "complete", "-")
    assert closed.returncode == 0, closed.stderr
    after_close, state = lifecycle_fold(ledger, workspace)
    assert after_close.returncode == 0, after_close.stderr
    assert state["phase"] == "complete"
    assert state["closed"] == "true"
    assert state["close_state"] == "complete"
    assert state["ready_to_close"] == "true"
    assert state["can_complete"] == "true"


def test_lifecycle_handled_summary_fallback_resolves_failed_detail_operation(tmp_path):
    workspace = tmp_path / "handled-summary"
    ledger = start_lifecycle(workspace)
    append_ok(ledger, "phase", "searching")
    append_ok(ledger, "posting", "linkedin", "posting-1", "queued", "revision-1")
    append_ok(ledger, "phase", "selection_settled")
    append_ok(ledger, "phase", "reviewing_initial_batch")
    append_ok(ledger, "posting", "linkedin", "posting-1", "evaluating", "revision-1")
    append_ok(
        ledger,
        "attempt-started",
        "detail-1",
        "detail_read",
        "detail-linkedin-posting-1",
        "1",
    )
    append_ok(
        ledger,
        "attempt-accounted",
        "detail-1",
        "true",
        "terminal_failure",
        "request-detail-1",
    )
    append_ok(ledger, "attempt-resolved", "detail-1", "summary_fallback")
    append_ok(ledger, "posting", "linkedin", "posting-1", "evaluated", "revision-1")
    append_ok(ledger, "phase", "early_results_shown")
    append_ok(ledger, "phase", "reviewing_remaining")
    append_ok(ledger, "phase", "finalizing")
    write_final_artifacts(workspace)
    record_final_artifact_milestones(ledger)

    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["blocking_attempt_failures"] == "0"
    assert state["ready_to_close"] == "true"
    append_ok(ledger, "close", "complete", "-")
    closed, state = lifecycle_fold(ledger, workspace)
    assert closed.returncode == 0, closed.stderr
    assert state["can_complete"] == "true"


@pytest.mark.parametrize("outcome", ["success", "terminal_failure", "quota_rejected"])
def test_lifecycle_rejects_retry_after_nonretryable_outcome(tmp_path, outcome):
    workspace = tmp_path / outcome
    ledger = start_lifecycle(workspace)
    append_ok(
        ledger,
        "attempt-started",
        "detail-1",
        "detail_read",
        "detail-linkedin-posting-1",
        "1",
    )
    append_ok(
        ledger,
        "attempt-accounted",
        "detail-1",
        "false" if outcome == "quota_rejected" else "true",
        outcome,
        "-" if outcome == "quota_rejected" else "request-detail-1",
    )
    rejected = lifecycle_append(
        ledger,
        "attempt-started",
        "detail-2",
        "detail_read",
        "detail-linkedin-posting-1",
        "2",
    )
    assert rejected.returncode != 0
    folded, _ = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr


def test_lifecycle_fold_rejects_success_hidden_by_later_summary_resolution(tmp_path):
    workspace = tmp_path / "hidden-success"
    ledger = start_lifecycle(workspace)
    append_ok(
        ledger,
        "attempt-started",
        "detail-1",
        "detail_read",
        "detail-linkedin-posting-1",
        "1",
    )
    append_ok(
        ledger,
        "attempt-accounted",
        "detail-1",
        "true",
        "success",
        "request-detail-1",
    )
    with ledger.open("a") as stream:
        stream.write(
            '{"event":"attempt_started","run_id":"%s","ts":"%s",'
            '"attempt_id":"detail-2","operation":"detail_read",'
            '"logical_operation_id":"detail-linkedin-posting-1","attempt_number":2}\n'
            '{"event":"attempt_accounted","run_id":"%s","ts":"%s",'
            '"attempt_id":"detail-2","metered":true,"outcome":"terminal_failure",'
            '"request_id":"request-detail-2"}\n'
            '{"event":"attempt_resolved","run_id":"%s","ts":"%s",'
            '"attempt_id":"detail-2","resolution":"summary_fallback"}\n'
            % (RUN_ID, RUN_STARTED, RUN_ID, RUN_STARTED, RUN_ID, RUN_STARTED)
        )
    folded, _ = lifecycle_fold(ledger, workspace)
    assert folded.returncode != 0


def test_lifecycle_complete_close_fails_closed_without_artifact_milestones(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace)
    advance_to_finalizing(ledger, with_posting=False, with_attempt=False)
    write_final_artifacts(workspace)

    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["final_run_record_written"] == "true"
    assert state["final_digest_written"] == "true"
    assert state["ready_to_close"] == "false"
    closed = lifecycle_append(ledger, "close", "complete", "-")
    assert closed.returncode != 0


def test_lifecycle_complete_close_fails_closed_without_concrete_artifacts(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace)
    advance_to_finalizing(ledger, with_posting=False, with_attempt=False)
    record_final_artifact_milestones(ledger)

    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["final_run_record_written"] == "false"
    assert state["final_digest_written"] == "false"
    assert state["ready_to_close"] == "false"
    closed = lifecycle_append(ledger, "close", "complete", "-")
    assert closed.returncode != 0


def test_lifecycle_digest_path_uses_run_started_calendar_date_exactly(tmp_path):
    """Never accept the run-id date, an arbitrary digest, or the newest digest in reports/."""
    workspace = tmp_path / "workspace"
    started = "2026-07-15T23:30:00-04:00"
    ledger = start_lifecycle(workspace, ts=started)
    advance_to_finalizing(ledger, with_posting=False, with_attempt=False)
    write_final_artifacts(workspace, digest_date="2026-07-16")  # wrong: this is the UTC run-id date
    record_final_artifact_milestones(ledger)

    wrong_digest, state = lifecycle_fold(ledger, workspace)
    assert wrong_digest.returncode == 0, wrong_digest.stderr
    assert state["final_digest_written"] == "false"
    assert state["ready_to_close"] == "false"
    assert lifecycle_append(ledger, "close", "complete", "-").returncode != 0

    (workspace / "reports" / "2026-07-15-digest.md").write_text("# Exact digest\n")
    exact_digest, state = lifecycle_fold(ledger, workspace)
    assert exact_digest.returncode == 0, exact_digest.stderr
    assert state["final_digest_written"] == "true"
    assert state["ready_to_close"] == "true"


def test_lifecycle_fold_rejects_ledger_from_a_different_workspace(tmp_path):
    """Artifacts from WORKSPACE B can never close a ledger supplied from WORKSPACE A."""
    ledger_workspace = tmp_path / "ledger-workspace"
    artifact_workspace = tmp_path / "artifact-workspace"
    ledger = start_lifecycle(ledger_workspace)
    advance_to_finalizing(ledger, with_posting=False, with_attempt=False)
    record_final_artifact_milestones(ledger)
    write_final_artifacts(artifact_workspace)

    folded, _ = lifecycle_fold(ledger, artifact_workspace)
    assert folded.returncode != 0


def test_lifecycle_early_results_with_remaining_work_is_not_complete(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace, source_order="linkedin+ashby")
    append_ok(ledger, "phase", "searching")
    append_ok(ledger, "posting", "linkedin", "ready", "queued", "revision-1")
    append_ok(ledger, "posting", "ashby", "waiting", "queued", "revision-1")
    append_ok(ledger, "phase", "selection_settled")
    append_ok(ledger, "phase", "reviewing_initial_batch")
    append_ok(ledger, "posting", "linkedin", "ready", "evaluating", "revision-1")
    append_ok(ledger, "posting", "linkedin", "ready", "evaluated", "revision-1")
    append_ok(ledger, "posting", "linkedin", "ready", "presented", "revision-1")
    append_ok(ledger, "phase", "early_results_shown")
    append_ok(ledger, "milestone", "early_results_shown")

    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["phase"] == "early_results_shown"
    assert state["selected"] == "2"
    assert state["evaluated"] == "1"
    assert state["presented"] == "1"
    assert state["remaining"] == "1"
    assert state["ready_to_close"] == "false"
    assert state["can_complete"] == "false"


def test_lifecycle_evaluating_posting_counts_as_in_flight(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace, source_order="greenhouse")
    append_ok(ledger, "phase", "searching")
    append_ok(ledger, "posting", "greenhouse", "acme:7310605", "queued", "revision-1")
    append_ok(ledger, "phase", "selection_settled")
    append_ok(ledger, "phase", "reviewing_initial_batch")
    append_ok(ledger, "posting", "greenhouse", "acme:7310605", "evaluating", "revision-1")

    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["selected"] == "1"
    assert state["remaining"] == "0"
    assert state["in_flight"] == "1"
    assert state["evaluated"] == "0"
    assert state["can_complete"] == "false"


def test_lifecycle_unaccounted_retry_attempt_prevents_completion(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace)
    append_ok(ledger, "phase", "searching")
    append_ok(
        ledger, "attempt-started", "attempt-1", "initial_search", "search-1", "1"
    )
    append_ok(ledger, "attempt-accounted", "attempt-1", "true", "retryable_failure", "req-1")
    append_ok(
        ledger, "attempt-started", "attempt-2", "initial_search", "search-1", "2"
    )
    append_ok(ledger, "phase", "selection_settled")
    append_ok(ledger, "phase", "reviewing_initial_batch")
    append_ok(ledger, "phase", "early_results_shown")
    append_ok(ledger, "milestone", "early_results_shown")
    append_ok(ledger, "phase", "reviewing_remaining")
    append_ok(ledger, "phase", "finalizing")
    write_final_artifacts(workspace)
    record_final_artifact_milestones(ledger)

    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["attempts_started"] == "2"
    assert state["attempts_accounted"] == "1"
    assert state["ready_to_close"] == "false"
    assert lifecycle_append(ledger, "close", "complete", "-").returncode != 0


@pytest.mark.parametrize("outcome", ["quota_rejected", "worker_failed", "terminal_failure"])
def test_lifecycle_authoritative_terminal_attempt_outcomes_prevent_complete_close(
    tmp_path, outcome
):
    workspace = tmp_path / outcome
    ledger = start_lifecycle(workspace)
    append_ok(ledger, "phase", "searching")
    append_ok(
        ledger,
        "attempt-started",
        "attempt-1",
        "detail_read",
        "detail-linkedin-posting-1",
        "1",
    )
    append_ok(
        ledger,
        "attempt-accounted",
        "attempt-1",
        "false" if outcome == "quota_rejected" else "true",
        outcome,
        "-" if outcome == "quota_rejected" else "req-1",
    )
    append_ok(ledger, "posting", "linkedin", "posting-1", "queued", "revision-1")
    append_ok(ledger, "phase", "selection_settled")
    append_ok(ledger, "phase", "reviewing_initial_batch")
    append_ok(ledger, "posting", "linkedin", "posting-1", "evaluating", "revision-1")
    append_ok(
        ledger, "posting", "linkedin", "posting-1", "terminally_skipped", "revision-1"
    )
    append_ok(ledger, "phase", "early_results_shown")
    append_ok(ledger, "phase", "reviewing_remaining")
    append_ok(ledger, "phase", "finalizing")
    write_final_artifacts(workspace)
    record_final_artifact_milestones(ledger)

    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["ready_to_close"] == "false"
    assert state["blocking_attempt_failures"] == "1"
    assert lifecycle_append(ledger, "close", "complete", "-").returncode != 0


def test_lifecycle_later_linked_success_resolves_worker_failure_only(tmp_path):
    workspace = tmp_path / "resolved-worker"
    ledger = start_lifecycle(workspace)
    append_ok(ledger, "phase", "searching")
    append_ok(
        ledger,
        "attempt-started",
        "attempt-1",
        "detail_read",
        "detail-linkedin-posting-1",
        "1",
    )
    append_ok(
        ledger, "attempt-accounted", "attempt-1", "true", "worker_failed", "req-1"
    )
    append_ok(
        ledger,
        "attempt-started",
        "attempt-2",
        "detail_read",
        "detail-linkedin-posting-1",
        "2",
    )
    append_ok(ledger, "attempt-accounted", "attempt-2", "true", "success", "req-2")
    append_ok(ledger, "posting", "linkedin", "posting-1", "queued", "revision-1")
    append_ok(ledger, "phase", "selection_settled")
    append_ok(ledger, "phase", "reviewing_initial_batch")
    append_ok(ledger, "posting", "linkedin", "posting-1", "evaluating", "revision-1")
    append_ok(ledger, "posting", "linkedin", "posting-1", "evaluated", "revision-1")
    append_ok(ledger, "phase", "early_results_shown")
    append_ok(ledger, "phase", "reviewing_remaining")
    append_ok(ledger, "phase", "finalizing")
    write_final_artifacts(workspace)
    record_final_artifact_milestones(ledger)

    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["blocking_attempt_failures"] == "0"
    assert state["ready_to_close"] == "true"
    closed = lifecycle_append(ledger, "close", "complete", "-")
    assert closed.returncode == 0, closed.stderr


def test_lifecycle_retry_linkage_requires_adjacent_coordinator_attempt_numbers(tmp_path):
    workspace = tmp_path / "retry-sequence"
    ledger = start_lifecycle(workspace)
    append_ok(ledger, "phase", "searching")
    append_ok(
        ledger,
        "attempt-started",
        "attempt-1",
        "initial_search",
        "search-query-1-linkedin",
        "1",
    )
    append_ok(
        ledger, "attempt-accounted", "attempt-1", "true", "retryable_failure", "req-1"
    )
    skipped = lifecycle_append(
        ledger,
        "attempt-started",
        "attempt-3",
        "initial_search",
        "search-query-1-linkedin",
        "3",
    )
    assert skipped.returncode != 0
    wrong_operation = lifecycle_append(
        ledger,
        "attempt-started",
        "attempt-2",
        "detail_read",
        "search-query-1-linkedin",
        "2",
    )
    assert wrong_operation.returncode != 0


def test_lifecycle_posting_updates_are_last_write_wins_without_double_counting(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace, source_order="lever+ashby")
    append_ok(ledger, "phase", "searching")
    append_ok(ledger, "posting", "lever", "acme/123", "queued", "revision-1")
    append_ok(ledger, "posting", "ashby", "other", "queued", "revision-1")
    append_ok(ledger, "phase", "selection_settled")
    append_ok(ledger, "phase", "reviewing_initial_batch")
    append_ok(ledger, "posting", "lever", "acme/123", "evaluating", "revision-1")
    append_ok(ledger, "posting", "lever", "acme/123", "evaluated", "revision-1")
    append_ok(ledger, "posting", "lever", "acme/123", "presented", "revision-1")
    append_ok(ledger, "posting", "ashby", "other", "evaluating", "revision-1")
    append_ok(ledger, "posting", "ashby", "other", "terminally_skipped", "revision-1")

    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["selected"] == "2"
    assert state["evaluated"] == "1"  # presented remains evaluated
    assert state["presented"] == "1"
    assert state["terminally_skipped"] == "1"
    assert state["remaining"] == "0"
    assert state["in_flight"] == "0"


@pytest.mark.parametrize("close_state", ["blocked", "interrupted"])
def test_lifecycle_noncomplete_close_states_preserve_phase_and_never_complete(tmp_path, close_state):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace)
    append_ok(ledger, "phase", "searching")
    append_ok(ledger, "close", close_state, "E-TEST")

    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["phase"] == "searching"
    assert state["closed"] == "true"
    assert state["close_state"] == close_state
    assert state["ready_to_close"] == "false"
    assert state["can_complete"] == "false"
    assert lifecycle_append(ledger, "phase", "selection_settled").returncode != 0


def test_lifecycle_phase_rejects_complete_and_backward_transitions(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace)
    append_ok(ledger, "phase", "searching")

    assert lifecycle_append(ledger, "phase", "preflight").returncode != 0
    assert lifecycle_append(ledger, "phase", "complete").returncode != 0
    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["phase"] == "searching"


def test_lifecycle_fold_rejects_handwritten_noncanonical_or_contradictory_rows(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = workspace / "runs" / (".lifecycle-%s.jsonl" % RUN_ID)
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        ('{ "event": "run_started", "run_id": "%s", "ts": "%s", "phase": "preflight", '
         '"trigger": "manual", "scheduler_id": null }\n')
        % (RUN_ID, RUN_STARTED)
    )
    malformed, _ = lifecycle_fold(ledger, workspace)
    assert malformed.returncode != 0

    ledger.write_text(
        ('{"event":"run_started","run_id":"%s","ts":"%s","phase":"preflight",'
         '"trigger":"manual","scheduler_id":null,"source_order":"linkedin"}\n'
         '{"event":"phase_changed","run_id":"%s","ts":"%s","phase":"searching"}\n'
         '{"event":"phase_changed","run_id":"%s","ts":"%s","phase":"preflight"}\n')
        % (RUN_ID, RUN_STARTED, RUN_ID, RUN_STARTED, RUN_ID, RUN_STARTED)
    )
    contradictory, _ = lifecycle_fold(ledger, workspace)
    assert contradictory.returncode != 0


def test_lifecycle_fold_rejects_api_key_shaped_value_in_canonical_row(tmp_path):
    """Canonical field order cannot bypass the privacy denylist with a secret-shaped identifier."""
    workspace = tmp_path / "workspace"
    ledger = workspace / "runs" / (".lifecycle-%s.jsonl" % RUN_ID)
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        ('{"event":"run_started","run_id":"%s","ts":"%s","phase":"preflight",'
         '"trigger":"manual","scheduler_id":null,"source_order":"linkedin"}\n'
         '{"event":"posting_state","run_id":"%s","ts":"%s","source":"linkedin",'
         '"source_id":"sk-secretvalue","state":"queued","brief_revision":"revision-1"}\n')
        % (RUN_ID, RUN_STARTED, RUN_ID, RUN_STARTED)
    )
    folded, _ = lifecycle_fold(ledger, workspace)
    assert folded.returncode != 0


@pytest.mark.parametrize(
    "prohibited",
    [
        "cursor=opaque-token",
        "api_key=sk-secretvalue",
        "full_job_description",
        "preferences_text",
        "match_prose",
        "revision-1\nrevision-2",
    ],
)
def test_lifecycle_append_rejects_prohibited_or_multiline_values(tmp_path, prohibited):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace)
    rejected = lifecycle_append(
        ledger,
        "posting",
        "linkedin",
        "posting-1",
        "queued",
        prohibited,
    )
    assert rejected.returncode != 0
    assert len(ledger.read_text().splitlines()) == 1


def test_lifecycle_attempt_accounting_requires_one_prior_start(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace)
    no_start = lifecycle_append(
        ledger, "attempt-accounted", "attempt-1", "false", "quota_rejected", "-"
    )
    assert no_start.returncode != 0

    append_ok(
        ledger, "attempt-started", "attempt-1", "initial_search", "search-1", "1"
    )
    append_ok(ledger, "attempt-accounted", "attempt-1", "false", "quota_rejected", "-")
    duplicate = lifecycle_append(
        ledger, "attempt-accounted", "attempt-1", "false", "quota_rejected", "-"
    )
    assert duplicate.returncode != 0


@pytest.mark.parametrize("field", ["request_id", "internal_code"])
def test_lifecycle_fold_rejects_empty_string_for_nullable_fields(tmp_path, field):
    workspace = tmp_path / field
    if field == "request_id":
        rows = [
            started_row(),
            ('{"event":"attempt_started","run_id":"%s","ts":"%s",'
             '"attempt_id":"attempt-1","operation":"initial_search",'
             '"logical_operation_id":"search-1","attempt_number":1}')
            % (RUN_ID, RUN_STARTED),
            ('{"event":"attempt_accounted","run_id":"%s","ts":"%s",'
             '"attempt_id":"attempt-1","metered":false,"outcome":"quota_rejected",'
             '"request_id":""}') % (RUN_ID, RUN_STARTED),
        ]
    else:
        rows = [
            started_row(),
            ('{"event":"run_closed","run_id":"%s","ts":"%s",'
             '"close_state":"blocked","internal_code":""}') % (RUN_ID, RUN_STARTED),
        ]
    ledger = write_lifecycle_rows(workspace, *rows)
    folded, _ = lifecycle_fold(ledger, workspace)
    assert folded.returncode != 0


def test_lifecycle_blocked_close_accepts_canonical_operator_code(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = start_lifecycle(workspace)
    closed = lifecycle_append(ledger, "close", "blocked", "E-NO-AUTH")
    assert closed.returncode == 0, closed.stderr
    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["closed"] == "true"
    assert state["close_state"] == "blocked"
    assert state["can_complete"] == "false"


@pytest.mark.parametrize("operation", ["job_description_read", "authorization_check"])
def test_lifecycle_operation_accepts_safe_semantic_identifier_words(tmp_path, operation):
    append_workspace = tmp_path / "append" / operation
    ledger = start_lifecycle(append_workspace)
    appended = lifecycle_append(
        ledger, "attempt-started", "attempt-1", operation, "logical-operation-1", "1"
    )
    assert appended.returncode == 0, appended.stderr
    folded, state = lifecycle_fold(ledger, append_workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["attempts_started"] == "1"

    fold_workspace = tmp_path / "fold" / operation
    ledger = write_lifecycle_rows(
        fold_workspace,
        started_row(),
        ('{"event":"attempt_started","run_id":"%s","ts":"%s",'
         '"attempt_id":"attempt-1","operation":"%s",'
         '"logical_operation_id":"logical-operation-1","attempt_number":1}')
        % (RUN_ID, RUN_STARTED, operation),
    )
    folded, state = lifecycle_fold(ledger, fold_workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["attempts_started"] == "1"


@pytest.mark.parametrize(
    "operation",
    ["ghp_abcdefghijklmnopqrstuvwxyz1234567890", "full%20job%20description"],
)
def test_lifecycle_operation_still_rejects_key_or_encoded_payload(tmp_path, operation):
    append_workspace = tmp_path / "append" / operation
    ledger = start_lifecycle(append_workspace)
    assert lifecycle_append(
        ledger, "attempt-started", "attempt-1", operation, "logical-operation-1", "1"
    ).returncode != 0

    fold_workspace = tmp_path / "fold" / operation
    ledger = write_lifecycle_rows(
        fold_workspace,
        started_row(),
        ('{"event":"attempt_started","run_id":"%s","ts":"%s",'
         '"attempt_id":"attempt-1","operation":"%s",'
         '"logical_operation_id":"logical-operation-1","attempt_number":1}')
        % (RUN_ID, RUN_STARTED, operation),
    )
    folded, _ = lifecycle_fold(ledger, fold_workspace)
    assert folded.returncode != 0


def test_lifecycle_fold_accepts_null_nullable_fields(tmp_path):
    workspace = tmp_path / "workspace"
    ledger = write_lifecycle_rows(
        workspace,
        started_row(),
        ('{"event":"attempt_started","run_id":"%s","ts":"%s",'
         '"attempt_id":"attempt-1","operation":"initial_search",'
         '"logical_operation_id":"search-1","attempt_number":1}') % (RUN_ID, RUN_STARTED),
        ('{"event":"attempt_accounted","run_id":"%s","ts":"%s",'
         '"attempt_id":"attempt-1","metered":false,"outcome":"quota_rejected",'
         '"request_id":null}') % (RUN_ID, RUN_STARTED),
        ('{"event":"run_closed","run_id":"%s","ts":"%s",'
         '"close_state":"interrupted","internal_code":null}') % (RUN_ID, RUN_STARTED),
    )
    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["close_state"] == "interrupted"


@pytest.mark.parametrize("internal_code", ["NO-AUTH", "e-no-auth", "E--NO-AUTH", "E-NO-AUTH-"])
def test_lifecycle_internal_code_requires_canonical_operator_grammar(tmp_path, internal_code):
    append_workspace = tmp_path / "append" / internal_code
    ledger = start_lifecycle(append_workspace)
    assert lifecycle_append(ledger, "close", "blocked", internal_code).returncode != 0

    fold_workspace = tmp_path / "fold" / internal_code
    ledger = write_lifecycle_rows(
        fold_workspace,
        started_row(),
        ('{"event":"run_closed","run_id":"%s","ts":"%s",'
         '"close_state":"blocked","internal_code":"%s"}')
        % (RUN_ID, RUN_STARTED, internal_code),
    )
    folded, _ = lifecycle_fold(ledger, fold_workspace)
    assert folded.returncode != 0


@pytest.mark.parametrize(
    "bypass",
    [
        "next_page_token",
        "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
        "full%20job%20description",
    ],
)
def test_lifecycle_append_and_fold_reject_grammar_valid_privacy_bypasses(tmp_path, bypass):
    append_workspace = tmp_path / "append" / bypass
    ledger = start_lifecycle(append_workspace)
    appended = lifecycle_append(
        ledger, "posting", "linkedin", "posting-1", "queued", bypass
    )
    assert appended.returncode != 0
    assert len(ledger.read_text().splitlines()) == 1

    fold_workspace = tmp_path / "fold" / bypass
    ledger = write_lifecycle_rows(
        fold_workspace,
        started_row(),
        ('{"event":"posting_state","run_id":"%s","ts":"%s","source":"linkedin",'
         '"source_id":"posting-1","state":"queued","brief_revision":"%s"}')
        % (RUN_ID, RUN_STARTED, bypass),
    )
    folded, _ = lifecycle_fold(ledger, fold_workspace)
    assert folded.returncode != 0


INVALID_LIFECYCLE_TIMES = [
    ("2026-02-30T14-30-00Z", RUN_STARTED),
    ("2026-07-16T24-00-00Z", RUN_STARTED),
    (RUN_ID, "2025-02-29T10:30:00Z"),
    (RUN_ID, "2026-07-16T24:00:00Z"),
    (RUN_ID, "2026-07-16T23:60:00Z"),
    (RUN_ID, "2026-07-16T23:59:60Z"),
    (RUN_ID, "2026-07-16T10:30:00+15:00"),
    (RUN_ID, "2026-07-16T10:30:00-14:01"),
]


@pytest.mark.parametrize(
    "run_id,ts",
    [
        ("2024-02-29T23-59-59Z", "2024-02-29T23:59:59+14:00"),
        ("2000-02-29T00-00-00Z", "2000-02-29T00:00:00-14:00"),
        ("2100-02-28T00-00-00Z", "2100-02-28T00:00:00Z"),
        ("0008-02-29T00-00-00Z", "0008-02-29T00:00:00Z"),
    ],
)
def test_lifecycle_append_and_fold_accept_valid_calendar_and_offset_boundaries(
    tmp_path, run_id, ts
):
    workspace = tmp_path / run_id
    ledger = start_lifecycle(workspace, run_id=run_id, ts=ts)
    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["run_id"] == run_id


@pytest.mark.parametrize("run_id,ts", INVALID_LIFECYCLE_TIMES)
def test_lifecycle_append_rejects_impossible_calendar_time_or_offset(tmp_path, run_id, ts):
    workspace = tmp_path / "workspace"
    ledger = workspace / "runs" / (".lifecycle-%s.jsonl" % run_id)
    appended = lifecycle_append(
        ledger, "start", "manual", "-", run_id=run_id, ts=ts
    )
    assert appended.returncode != 0
    assert not ledger.exists()


@pytest.mark.parametrize("run_id,ts", INVALID_LIFECYCLE_TIMES)
def test_lifecycle_fold_rejects_impossible_calendar_time_or_offset(tmp_path, run_id, ts):
    workspace = tmp_path / "workspace"
    ledger = write_lifecycle_rows(workspace, started_row(run_id=run_id, ts=ts), run_id=run_id)
    folded, _ = lifecycle_fold(ledger, workspace)
    assert folded.returncode != 0


@pytest.mark.parametrize("linked_artifact", ["run_record", "digest", "reports_directory"])
def test_lifecycle_symlinked_final_artifact_never_satisfies_readiness(tmp_path, linked_artifact):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    outside.mkdir()
    ledger = start_lifecycle(workspace)
    advance_to_finalizing(ledger, with_posting=False, with_attempt=False)
    record_final_artifact_milestones(ledger)
    runs = workspace / "runs"
    reports = workspace / "reports"

    if linked_artifact == "run_record":
        outside_run = outside / "run.json"
        outside_run.write_text('{"run_id":"%s"}\n' % RUN_ID)
        (runs / ("%s.json" % RUN_ID)).symlink_to(outside_run)
        reports.mkdir()
        (reports / "2026-07-16-digest.md").write_text("# Digest\n")
    elif linked_artifact == "digest":
        (runs / ("%s.json" % RUN_ID)).write_text('{"run_id":"%s"}\n' % RUN_ID)
        reports.mkdir()
        outside_digest = outside / "digest.md"
        outside_digest.write_text("# Digest\n")
        (reports / "2026-07-16-digest.md").symlink_to(outside_digest)
    else:
        (runs / ("%s.json" % RUN_ID)).write_text('{"run_id":"%s"}\n' % RUN_ID)
        outside_reports = outside / "reports"
        outside_reports.mkdir()
        (outside_reports / "2026-07-16-digest.md").write_text("# Digest\n")
        reports.symlink_to(outside_reports, target_is_directory=True)

    folded, state = lifecycle_fold(ledger, workspace)
    assert folded.returncode == 0, folded.stderr
    assert state["ready_to_close"] == "false"
    assert state["can_complete"] == "false"
    assert lifecycle_append(ledger, "close", "complete", "-").returncode != 0


@pytest.mark.parametrize("shell", ["sh"] + (["dash"] if shutil.which("dash") else []))
def test_lifecycle_scripts_execute_under_posix_shells(tmp_path, shell):
    workspace = tmp_path / shell
    ledger = workspace / "runs" / (".lifecycle-%s.jsonl" % RUN_ID)
    started = lifecycle_append(ledger, "start", "manual", "-", "linkedin", shell=shell)
    assert started.returncode == 0, started.stderr
    folded, state = lifecycle_fold(ledger, workspace, shell=shell)
    assert folded.returncode == 0, folded.stderr
    assert state["phase"] == "preflight"
    assert state["can_complete"] == "false"


def test_lifecycle_reference_pins_complete_no_shell_fallback():
    """The script interface and its no-runtime fallback stay single-homed in run-lifecycle.md."""
    text = LIFECYCLE_REFERENCE.read_text()
    required = [
        ("lifecycle-append.sh LEDGER start RUN_ID ISO_TIMESTAMP "
         "TRIGGER SCHEDULER_ID_OR_DASH SOURCE_ORDER"),
        "immutable source order",
        "source absent",
        "manual requires `-`",
        "scheduled and canary require",
        "without normalization",
        "lifecycle-append.sh LEDGER phase RUN_ID ISO_TIMESTAMP PHASE",
        "lifecycle-append.sh LEDGER posting RUN_ID ISO_TIMESTAMP SOURCE SOURCE_ID STATE BRIEF_REVISION",
        ("lifecycle-append.sh LEDGER attempt-started RUN_ID ISO_TIMESTAMP ATTEMPT_ID "
         "OPERATION LOGICAL_OPERATION_ID ATTEMPT_NUMBER"),
        ("lifecycle-append.sh LEDGER attempt-accounted RUN_ID ISO_TIMESTAMP ATTEMPT_ID "
         "METERED OUTCOME REQUEST_ID_OR_DASH"),
        ("lifecycle-append.sh LEDGER attempt-resolved RUN_ID ISO_TIMESTAMP ATTEMPT_ID "
         "SUMMARY_FALLBACK"),
        "handled-failure resolution",
        "lifecycle-append.sh LEDGER revision RUN_ID ISO_TIMESTAMP BRIEF_REVISION",
        "lifecycle-append.sh LEDGER milestone RUN_ID ISO_TIMESTAMP MILESTONE",
        ("lifecycle-append.sh LEDGER close RUN_ID ISO_TIMESTAMP "
         "COMPLETE_OR_BLOCKED_OR_INTERRUPTED INTERNAL_CODE_OR_DASH"),
        "lifecycle-fold.sh LEDGER WORKSPACE",
        "final_run_record_written",
        "final_digest_written",
        "run_started timestamp",
        "local calendar date used for this run's digest",
        "later event timestamps remain ordinary ISO timestamps",
        "never an arbitrary or newest digest",
        "`E-[A-Z0-9]+(-[A-Z0-9]+)*`",
        "empty JSON string",
        "`next_page_token`",
        "`ghp_...`",
        "`OPERATION` is a controlled semantic label",
        "non-symlink",
        "host-specific date",
        "ready_to_close",
        "can_complete",
    ]
    for fragment in required:
        assert fragment in text, "run-lifecycle.md fallback is missing: %s" % fragment


# --------------------------------------------------------------- support summary
#
# support-summary.sh emits, on the user's explicit request, a WHITELIST-ONLY local diagnostic
# (internals.md §"Local support summary"). It is built by extracting ONLY the allowed nonsecret
# fields — build stamp, host-reported harness/version, OS/arch, schedule state, latest run health,
# internal error code, aggregate agent-data calls, and nonsecret request IDs — never by dumping and
# filtering. These tests seed EVERY forbidden secret/PII/cursor/preference/description value beside
# the allowed fields and prove the output carries the whitelist and NONE of the bait, under sh + dash.

SUPPORT_RUN_ID = "2026-07-16T14-30-00Z"

# Every forbidden value the whitelist must NEVER emit, each a unique sentinel so a single substring
# hit is a definitive leak. None contains an `E-<CAPS>` operator-code shape, so a hit could only come
# from dumping the value's home field rather than from the deliberately whitelisted internal code.
SUPPORT_BAIT = [
    "PREFERENCESBAIT_remote_only_must_have",      # preferences.md prose
    "JOBDESCBAIT_full_posting_description_text",   # full job description (jobs.jsonl)
    "MATCHPROSEBAIT_owns_the_roadmap_strong",      # match reasoning prose (jobs.jsonl)
    "sk-APIKEYBAITroute0000000000",                # API key seeded in the run record
    "sk-CONFIGAPIKEYBAIT111111111",                # API key seeded in config.yaml
    "sk-REGISTRYKEYBAIT2222222222",                # API key seeded in the registry
    "AUTHBAIT_bearer_header_value",                # auth header (run record)
    "CURSORBAIT_opaque_pagination_cursor",         # pagination cursor (run record)
    "NEXTPAGEBAIT_next_page_token_value",          # next_page_token (run record)
    "ENVDUMPBAIT_PATH_SECRET_dump",                # environment dump (run record)
    "KEYWORDBAIT_senior_staff_designer",           # search keywords (not whitelisted)
    "SCHEDIDBAIT_com_example_jobsearch",           # scheduler_id neighbor in the scheduling object
    "PRIMARYMODELBAIT_exact_model_id",             # primary_model neighbor in the scheduling object
]

# The most PII-sensitive field of all — the absolute workspace path — lives as a flat `workspace` key
# INSIDE the scheduling object in the real registry schema (internals.md). It is NOT one of the four
# scheduling fields support-summary.sh reads (installed/verified/mechanism/cadence), so it must never
# reach the summary. Seeded where it actually lives and asserted absent below.
SUPPORT_WORKSPACE_PATH_BAIT = "/Users/pii-sentinel/PRIVATE-WORKSPACEPATHBAIT"


def run_support(workspace, registry, harness="Claude Code", version="2.1.7", shell="sh"):
    """Run support-summary.sh through a POSIX shell; the whitelist-only summary is on stdout."""
    return subprocess.run(
        [shell, str(SUPPORT), str(workspace), str(registry), harness, version],
        capture_output=True,
        text=True,
    )


def _write_support_fixture(tmp_path):
    """A workspace + registry carrying EVERY whitelist field and EVERY forbidden value side by side.

    The run record is pretty-printed (multi-line) on purpose, so the mechanic must tolerate a
    formatted record and still extract by exact key rather than by dumping lines.
    """
    workspace = tmp_path / "ws"
    runs = workspace / "runs"
    (workspace / "reports").mkdir(parents=True)
    runs.mkdir(parents=True)

    # config.yaml — bait only; the mechanic must never read it.
    (workspace / "config.yaml").write_text(
        "version: 2\n"
        'search: { detail_model: "x", api_key: "sk-CONFIGAPIKEYBAIT111111111" }\n'
        'queries: [ { id: "q", keywords: "KEYWORDBAIT_senior_staff_designer" } ]\n'
    )
    # preferences.md — pure PII prose bait.
    (workspace / "preferences.md").write_text(
        "# Brief\nMust-have: PREFERENCESBAIT_remote_only_must_have.\n"
    )
    # jobs.jsonl — job-description + match-prose bait.
    (workspace / "jobs.jsonl").write_text(
        '{"event":"evaluated","source":"linkedin","source_id":"1",'
        '"reasoning":"MATCHPROSEBAIT_owns_the_roadmap_strong",'
        '"description":"JOBDESCBAIT_full_posting_description_text"}\n'
    )

    # The latest run record: blocked, whitelist fields AND forbidden neighbors, pretty-printed.
    record = (
        "{\n"
        '  "run_id": "%s",\n' % SUPPORT_RUN_ID
        + '  "run_health": "blocked",\n'
        '  "error": { "code": "E-NO-AUTH" },\n'
        '  "api_key": "sk-APIKEYBAITroute0000000000",\n'
        '  "authorization": "AUTHBAIT_bearer_header_value",\n'
        '  "environment": "ENVDUMPBAIT_PATH_SECRET_dump",\n'
        '  "queries": [\n'
        '    { "query_id": "q", "source": "linkedin",\n'
        '      "keywords": "KEYWORDBAIT_senior_staff_designer",\n'
        '      "cursor": "CURSORBAIT_opaque_pagination_cursor",\n'
        '      "next_page_token": "NEXTPAGEBAIT_next_page_token_value",\n'
        '      "request_ids": ["req_whitelist_alpha", "req_whitelist_bravo"] }\n'
        "  ],\n"
        '  "errors": [\n'
        '    { "stage": "get-posting", "code": "upstream_unavailable",\n'
        '      "request_id": "req_whitelist_charlie" }\n'
        "  ],\n"
        '  "agent_data_usage": { "metered_calls": 9,\n'
        '    "by_operation": { "initial_search": 4, "continuation_search": 2, "detail_read": 3 } },\n'
        '  "lifecycle": { "phase": "searching", "close_state": "blocked", "health": "blocked" }\n'
        "}\n"
    )
    (runs / ("%s.json" % SUPPORT_RUN_ID)).write_text(record)
    # An older run record and a non-run file — neither may be chosen as "latest".
    (runs / "2026-07-01T09-00-00Z.json").write_text('{"run_health":"healthy","error":null}\n')
    (runs / "detail-model-binding.json").write_text('{"detail_model":"x"}\n')

    registry = tmp_path / "config.json"
    registry.write_text(
        "{\n"
        '  "version": 1,\n'
        '  "active_workspace": "%s",\n' % workspace
        + '  "api_key": "sk-REGISTRYKEYBAIT2222222222",\n'
        '  "scheduling": {\n'
        '    "installed": true, "verified": true,\n'
        '    "mechanism": "launchd", "cadence": "daily",\n'
        '    "workspace": "%s",\n' % SUPPORT_WORKSPACE_PATH_BAIT
        + '    "scheduler_id": "SCHEDIDBAIT_com_example_jobsearch",\n'
        '    "primary_model": "PRIMARYMODELBAIT_exact_model_id",\n'
        '    "canary_run_id": "%s"\n' % SUPPORT_RUN_ID
        + "  }\n"
        "}\n"
    )
    return workspace, registry


def _build_stamp_fields():
    stamp = (ROOT / "shared" / "references" / "build-stamp.md").read_text()
    fields = {}
    for line in stamp.splitlines():
        if line.startswith("version:"):
            fields["version"] = line.split(":", 1)[1].strip()
        elif line.startswith("content_hash:"):
            fields["content_hash"] = line.split(":", 1)[1].strip()
    return fields


@pytest.mark.parametrize("shell", ["sh"] + (["dash"] if shutil.which("dash") else []))
def test_support_summary_is_whitelist_only_under_posix_shells(tmp_path, shell):
    """Whitelist present, EVERY forbidden value absent — the safety-critical property — under sh+dash."""
    workspace, registry = _write_support_fixture(tmp_path)
    stamp = _build_stamp_fields()

    r = run_support(workspace, registry, harness="Claude Code", version="2.1.7", shell=shell)
    assert r.returncode == 0, r.stderr
    out = r.stdout

    # --- whitelist present ---
    assert stamp["version"] in out                      # build stamp version
    assert stamp["content_hash"] in out                 # build stamp content hash
    assert "Claude Code" in out and "2.1.7" in out       # host-reported harness/version
    assert os.uname().sysname in out and os.uname().machine in out  # OS / architecture
    assert "launchd" in out and "daily" in out           # schedule state (mechanism + cadence)
    assert "installed=true" in out and "verified=true" in out
    assert "blocked" in out                              # latest run health
    assert "E-NO-AUTH" in out                            # internal error code — DELIBERATELY included
    assert "9 metered" in out                            # aggregate agent-data calls
    for rid in ("req_whitelist_alpha", "req_whitelist_bravo", "req_whitelist_charlie"):
        assert rid in out                                # nonsecret request IDs
    assert "https://github.com/agent-data/job-search/issues" in out

    # --- none of the forbidden values leaked ---
    for bait in SUPPORT_BAIT:
        assert bait not in out, "LEAKED forbidden value %r under %s" % (bait, shell)
    # The flat scheduling `workspace` absolute path — the most PII-sensitive field, and the one the real
    # registry schema keeps in the scheduling object — is read for none of the whitelist fields.
    assert SUPPORT_WORKSPACE_PATH_BAIT not in out, "LEAKED workspace path"


def test_support_summary_selects_the_newest_run_record_only(tmp_path):
    """Only the newest run_id-shaped record supplies health/code/calls; the sidecar is never read."""
    workspace, registry = _write_support_fixture(tmp_path)
    r = run_support(workspace, registry)
    assert r.returncode == 0, r.stderr
    assert SUPPORT_RUN_ID in r.stdout            # the 2026-07-16 record, not the 2026-07-01 one
    assert "blocked" in r.stdout                 # its health, not the older record's "healthy"


def test_support_summary_graceful_when_no_workspace_or_registry(tmp_path):
    """A first-run user with no runs and no registry still gets build/harness/OS + the issues link."""
    workspace = tmp_path / "empty-ws"    # never created
    registry = tmp_path / "absent.json"  # never created
    r = run_support(workspace, registry, harness="Codex", version="9.9")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "Codex" in out and "9.9" in out
    assert os.uname().sysname in out
    assert "not configured" in out       # no scheduling object
    assert "none recorded" in out        # no latest run record
    assert "https://github.com/agent-data/job-search/issues" in out


def test_support_summary_healthy_run_fabricates_no_error_code(tmp_path):
    """A healthy run (error null) reports no operator code — the code is read, never invented."""
    workspace = tmp_path / "ws"
    runs = workspace / "runs"
    runs.mkdir(parents=True)
    (runs / ("%s.json" % SUPPORT_RUN_ID)).write_text(
        '{ "run_id": "%s", "run_health": "healthy", "error": null,\n'
        '  "agent_data_usage": { "metered_calls": 3 },\n'
        '  "queries": [ { "request_ids": ["req_ok_one"] } ] }\n' % SUPPORT_RUN_ID
    )
    registry = tmp_path / "config.json"
    registry.write_text('{ "version": 1, "scheduling": { "installed": false, "verified": false } }\n')
    r = run_support(workspace, registry, harness="Cursor", version="1.0")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "healthy" in out
    assert "3 metered" in out
    assert "req_ok_one" in out
    assert "installed=false" in out and "verified=false" in out
    assert re.search(r"E-[A-Z0-9]", out) is None   # no operator code fabricated when error is null


def test_support_summary_reference_pins_interface_and_prose_fallback():
    """The interface and its no-runtime prose fallback stay single-homed in internals.md."""
    text = INTERNALS_REFERENCE.read_text()
    required = [
        "support-summary.sh WORKSPACE REGISTRY HARNESS_NAME HARNESS_VERSION",
        "support-summary.txt",
        "https://github.com/agent-data/job-search/issues",
        "whitelist",
        "never",  # never upload / open an issue / launch a browser
    ]
    for fragment in required:
        assert fragment in text, "internals.md support-summary contract is missing: %s" % fragment


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
