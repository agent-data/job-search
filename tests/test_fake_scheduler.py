"""Executable T6.1 pressure for the dev-only fake scheduler shim.

These tests use only temp workspaces and the scenario capability fixtures. They do NOT
exercise a real scheduler, cron, launchd, network, model, or agent-data account. The shim
reads one scenario fixture and writes its state, log, and any scheduled-path artifacts to the
temp workspace via env vars. The tests prove the seven operations (probe, register-disabled,
inspect, fire, enable, disable, remove) behave deterministically across the ten scenarios,
that every operation is logged, and that a successful fire creates the scheduled-path
artifacts (run record, digest, lifecycle ledger) the T6.2/T6.3 canary flow consumes.
"""
import json
import os
import pathlib

import pytest

HERE = pathlib.Path(__file__).resolve().parent
SHIM = str(HERE / "fake-scheduler")
FIXTURES = HERE / "fixtures" / "scheduler"

SCENARIOS = [
    "native-eligible",
    "native-session-bound",
    "native-no-canary",
    "os-eligible",
    "model-binding-lost",
    "registration-failure",
    "execution-pre-meter-failure",
    "execution-metered-failure",
    "stale-registration",
    "scheduled-success",
]

PRIMARY = "fixture-primary-exact"
DETAIL = "fixture-detail-exact"


def run(op_args, scenario, state, log, extra_env=None):
    import subprocess

    env = dict(
        os.environ,
        JOBSEARCH_TEST_SCHEDULER_SCENARIO=scenario,
        JOBSEARCH_TEST_SCHEDULER_STATE=str(state),
        JOBSEARCH_TEST_SCHEDULER_LOG=str(log),
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run([SHIM, *op_args], capture_output=True, text=True, env=env)


def paths(tmp_path):
    return tmp_path / "state.json", tmp_path / "log.jsonl"


def write_definition(tmp_path, **overrides):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    definition = {
        "workspace": str(workspace),
        "cadence": "daily",
        "invocation": "job-search-run --headless",
        "primary_model": PRIMARY,
        "primary_model_origin": "session_inheritance",
        "detail_model": DETAIL,
        "detail_model_origin": "configured_user",
        "trigger": "scheduled",
    }
    definition.update(overrides)
    path = tmp_path / "definition.json"
    path.write_text(json.dumps(definition), encoding="utf-8")
    return path, workspace


def register(tmp_path, scenario, job_id="job-fixture-1", **def_overrides):
    state, log = paths(tmp_path)
    definition, workspace = write_definition(tmp_path, **def_overrides)
    result = run(["register-disabled", job_id, str(definition)], scenario, state, log)
    return result, state, log, workspace


# ---------------------------------------------------------------------------
# Fixtures exist and describe capability profiles
# ---------------------------------------------------------------------------
def test_all_ten_scenario_fixtures_exist_and_parse():
    for scenario in SCENARIOS:
        fixture = FIXTURES / f"{scenario}.json"
        assert fixture.is_file(), f"missing fixture {fixture}"
        data = json.loads(fixture.read_text(encoding="utf-8"))
        assert data["scenario"] == scenario
        assert isinstance(data.get("probe"), dict)


def test_no_extra_scenario_fixtures():
    present = sorted(p.stem for p in FIXTURES.glob("*.json"))
    assert present == sorted(SCENARIOS)


# ---------------------------------------------------------------------------
# probe — capability inspection (what T6.2 eligibility consumes)
# ---------------------------------------------------------------------------
GATES = (
    "unattended",
    "canary_testable",
    "primary_model_preserving",
    "local_access",
    "reversible",
)


def test_probe_native_eligible_passes_every_gate(tmp_path):
    state, log = paths(tmp_path)
    r = run(["probe"], "native-eligible", state, log)
    assert r.returncode == 0, r.stderr
    probe = json.loads(r.stdout)
    assert probe["mechanism"] == "native"
    assert probe["session_bound"] is False
    assert all(probe[g] is True for g in GATES)


def test_probe_session_bound_fails_unattended(tmp_path):
    state, log = paths(tmp_path)
    probe = json.loads(run(["probe"], "native-session-bound", state, log).stdout)
    assert probe["mechanism"] == "native"
    assert probe["session_bound"] is True
    assert probe["unattended"] is False


def test_probe_no_canary_fails_canary_testable(tmp_path):
    state, log = paths(tmp_path)
    probe = json.loads(run(["probe"], "native-no-canary", state, log).stdout)
    assert probe["unattended"] is True
    assert probe["canary_testable"] is False


def test_probe_os_eligible_is_os_mechanism_and_passes_every_gate(tmp_path):
    state, log = paths(tmp_path)
    probe = json.loads(run(["probe"], "os-eligible", state, log).stdout)
    assert probe["mechanism"] == "os"
    assert all(probe[g] is True for g in GATES)


def test_silent_model_loss_looks_eligible_at_probe(tmp_path):
    # The model-binding loss is silent: it cannot be seen at probe, only at the real canary fire.
    state, log = paths(tmp_path)
    probe = json.loads(run(["probe"], "model-binding-lost", state, log).stdout)
    assert all(probe[g] is True for g in GATES)


def test_probe_does_not_write_scheduler_state(tmp_path):
    state, log = paths(tmp_path)
    run(["probe"], "native-eligible", state, log)
    assert not state.exists()


# ---------------------------------------------------------------------------
# register-disabled
# ---------------------------------------------------------------------------
def test_register_disabled_persists_a_disabled_job(tmp_path):
    result, state, log, workspace = register(tmp_path, "scheduled-success")
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body == {"job_id": "job-fixture-1", "state": "disabled"}
    jobs = json.loads(state.read_text())["jobs"]
    assert jobs["job-fixture-1"]["state"] == "disabled"
    assert jobs["job-fixture-1"]["definition"]["workspace"] == str(workspace)


def test_registration_failure_fails_and_writes_no_job(tmp_path):
    result, state, log, _ = register(tmp_path, "registration-failure")
    assert result.returncode != 0
    assert json.loads(result.stderr)["error"] == "registration_failed"
    # No partial job is ever installed on a registration failure.
    if state.exists():
        assert json.loads(state.read_text()).get("jobs", {}) == {}


def test_register_disabled_never_marks_verified(tmp_path):
    _, state, _, _ = register(tmp_path, "scheduled-success")
    job = json.loads(state.read_text())["jobs"]["job-fixture-1"]
    assert job.get("verified") is False


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------
def test_inspect_returns_current_registration(tmp_path):
    _, state, log, workspace = register(tmp_path, "scheduled-success")
    r = run(["inspect", "job-fixture-1"], "scheduled-success", state, log)
    assert r.returncode == 0, r.stderr
    body = json.loads(r.stdout)
    assert body["registration"] == "current"
    assert body["matches_expected"] is True
    assert body["definition"]["invocation"] == "job-search-run --headless"


def test_stale_registration_is_reported_as_drift(tmp_path):
    _, state, log, _ = register(tmp_path, "stale-registration")
    r = run(["inspect", "job-fixture-1"], "stale-registration", state, log)
    assert r.returncode == 0, r.stderr
    body = json.loads(r.stdout)
    assert body["registration"] == "stale"
    assert body["matches_expected"] is False
    # The scheduler's own registry drifted from what we registered.
    assert body["definition"]["invocation"] != "job-search-run --headless"


def test_inspect_unknown_job_fails(tmp_path):
    state, log = paths(tmp_path)
    r = run(["inspect", "no-such-job"], "scheduled-success", state, log)
    assert r.returncode != 0
    assert json.loads(r.stderr)["error"] == "job_not_registered"


# ---------------------------------------------------------------------------
# fire — the real scheduled-path canary
# ---------------------------------------------------------------------------
def fire(tmp_path, scenario, **def_overrides):
    _, state, log, workspace = register(tmp_path, scenario, **def_overrides)
    r = run(["fire", "job-fixture-1"], scenario, state, log)
    return r, state, log, workspace


def test_scheduled_success_creates_the_scheduled_path_artifacts(tmp_path):
    r, state, log, workspace = fire(tmp_path, "scheduled-success")
    assert r.returncode == 0, r.stderr
    body = json.loads(r.stdout)
    assert body["run_health"] == "healthy"
    assert body["close_state"] == "complete"
    assert body["trigger"] == "scheduled"
    assert body["scheduler_id"] == "job-fixture-1"
    assert body["primary_model"] == PRIMARY
    assert body["primary_model_preserved"] is True
    assert body["metered_consumed"] is True

    runs = workspace / "runs"
    record = json.loads((runs / f"{body['run_id']}.json").read_text())
    assert record["trigger"] == "scheduled"
    assert record["scheduler_id"] == "job-fixture-1"
    assert record["run_health"] == "healthy"
    assert record["lifecycle"]["close_state"] == "complete"
    assert record["primary_model"] == PRIMARY
    assert record["detail_model"] == DETAIL
    assert (runs / f"{body['run_id']}-digest.md").is_file()

    ledger_path = runs / f".lifecycle-{body['run_id']}.jsonl"
    rows = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    phases = [row["phase"] for row in rows if "phase" in row]
    # Monotonic, adjacent forward phases through the quiet scheduled path to complete.
    assert phases == [
        "preflight",
        "searching",
        "selection_settled",
        "reviewing_initial_batch",
        "early_results_shown",
        "reviewing_remaining",
        "finalizing",
    ]
    assert rows[0]["event"] == "run_started"
    assert rows[-1]["event"] == "run_closed"
    assert rows[-1]["close_state"] == "complete"
    # A quiet scheduled run never claims the early-results milestone.
    milestones = [row["milestone"] for row in rows if row.get("event") == "milestone"]
    assert "early_results_shown" not in milestones
    assert {"final_run_record_written", "final_digest_written"} <= set(milestones)


def test_scheduled_digest_has_no_interactive_user_surface(tmp_path):
    r, _, _, workspace = fire(tmp_path, "scheduled-success")
    body = json.loads(r.stdout)
    digest = (workspace / "runs" / f"{body['run_id']}-digest.md").read_text()
    # Scheduled/canary runs are quiet: no interactive presentation language leaks into the artifact.
    assert "Here's what I found so far" not in digest
    assert "Want me to keep" not in digest


def test_pre_meter_failure_is_blocked_and_consumes_no_metered_consent(tmp_path):
    r, _, _, workspace = fire(tmp_path, "execution-pre-meter-failure")
    assert r.returncode == 0, r.stderr  # a blocked canary is a recorded outcome, not a crash
    body = json.loads(r.stdout)
    assert body["run_health"] == "blocked"
    assert body["metered_calls"] == 0
    assert body["metered_consumed"] is False
    record = json.loads((workspace / "runs" / f"{body['run_id']}.json").read_text())
    assert record["run_health"] == "blocked"
    assert record["lifecycle"]["close_state"] == "blocked"
    assert record["agent_data_usage"]["metered_calls"] == 0
    assert record["error"]["code"].startswith("E-")


def test_metered_failure_is_blocked_after_a_metered_call(tmp_path):
    r, _, _, workspace = fire(tmp_path, "execution-metered-failure")
    body = json.loads(r.stdout)
    assert body["run_health"] == "blocked"
    assert body["metered_calls"] >= 1
    assert body["metered_consumed"] is True
    record = json.loads((workspace / "runs" / f"{body['run_id']}.json").read_text())
    assert record["agent_data_usage"]["metered_calls"] >= 1
    assert record["lifecycle"]["close_state"] == "blocked"


def test_model_binding_lost_completes_but_drops_the_exact_model(tmp_path):
    r, _, _, workspace = fire(tmp_path, "model-binding-lost")
    body = json.loads(r.stdout)
    # The run itself completes healthy; the canary must catch that the model was NOT preserved.
    assert body["run_health"] == "healthy"
    assert body["primary_model_preserved"] is False
    assert body["primary_model"] != PRIMARY
    record = json.loads((workspace / "runs" / f"{body['run_id']}.json").read_text())
    assert record["primary_model"] != PRIMARY


def test_not_canary_testable_fire_is_unsupported(tmp_path):
    r, _, _, _ = fire(tmp_path, "native-no-canary")
    assert r.returncode != 0
    body = json.loads(r.stderr)
    assert body["error"] == "fire_unsupported"


def test_fire_unknown_job_fails(tmp_path):
    state, log = paths(tmp_path)
    r = run(["fire", "ghost"], "scheduled-success", state, log)
    assert r.returncode != 0
    assert json.loads(r.stderr)["error"] == "job_not_registered"


def test_fire_honors_the_definitions_canary_trigger(tmp_path):
    r, _, _, workspace = fire(tmp_path, "scheduled-success", trigger="canary")
    body = json.loads(r.stdout)
    assert body["trigger"] == "canary"
    record = json.loads((workspace / "runs" / f"{body['run_id']}.json").read_text())
    assert record["trigger"] == "canary"
    assert record["scheduler_id"] == "job-fixture-1"


def test_repeated_fires_get_distinct_deterministic_run_ids(tmp_path):
    _, state, log, _ = register(tmp_path, "scheduled-success")
    first = json.loads(run(["fire", "job-fixture-1"], "scheduled-success", state, log).stdout)
    second = json.loads(run(["fire", "job-fixture-1"], "scheduled-success", state, log).stdout)
    assert first["run_id"] != second["run_id"]
    # Deterministic: a fresh run from a fresh state reproduces the first run id exactly.
    state2 = tmp_path / "state2.json"
    log2 = tmp_path / "log2.jsonl"
    definition, _ = write_definition(tmp_path)
    run(["register-disabled", "job-fixture-1", str(definition)], "scheduled-success", state2, log2)
    replay = json.loads(run(["fire", "job-fixture-1"], "scheduled-success", state2, log2).stdout)
    assert replay["run_id"] == first["run_id"]


# ---------------------------------------------------------------------------
# enable / disable / remove — reversibility
# ---------------------------------------------------------------------------
def test_enable_disable_remove_transition_state(tmp_path):
    _, state, log, _ = register(tmp_path, "scheduled-success")

    enabled = run(["enable", "job-fixture-1"], "scheduled-success", state, log)
    assert json.loads(enabled.stdout)["state"] == "enabled"
    assert json.loads(state.read_text())["jobs"]["job-fixture-1"]["state"] == "enabled"

    disabled = run(["disable", "job-fixture-1"], "scheduled-success", state, log)
    assert json.loads(disabled.stdout)["state"] == "disabled"

    removed = run(["remove", "job-fixture-1"], "scheduled-success", state, log)
    assert json.loads(removed.stdout)["state"] == "absent"
    assert "job-fixture-1" not in json.loads(state.read_text())["jobs"]


# ---------------------------------------------------------------------------
# Logging + no-live-effects invariants
# ---------------------------------------------------------------------------
def test_every_operation_appends_to_the_log(tmp_path):
    _, state, log, _ = register(tmp_path, "scheduled-success")
    for op in (["inspect", "job-fixture-1"], ["fire", "job-fixture-1"],
               ["enable", "job-fixture-1"], ["disable", "job-fixture-1"],
               ["probe"], ["remove", "job-fixture-1"]):
        run(op, "scheduled-success", state, log)
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    logged = [e["operation"] for e in entries]
    assert logged == [
        "register-disabled", "inspect", "fire", "enable", "disable", "probe", "remove",
    ]
    assert all(e["scenario"] == "scheduled-success" for e in entries)
    assert all(e["outcome"] for e in entries)


def test_registration_failure_is_logged(tmp_path):
    _, _, log, _ = register(tmp_path, "registration-failure")
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    assert entries[-1]["operation"] == "register-disabled"
    assert entries[-1]["outcome"] == "registration_failed"


def test_shim_touches_no_network_module():
    source = pathlib.Path(SHIM).read_text(encoding="utf-8")
    for banned in ("import socket", "urllib", "http.client", "requests", "subprocess"):
        assert banned not in source, f"scheduler shim must not use {banned}"


def test_all_effects_stay_inside_the_temp_workspace(tmp_path):
    # Everything the shim writes (state, log, artifacts) lives under the temp workspace.
    r, state, log, workspace = fire(tmp_path, "scheduled-success")
    for produced in (state, log, workspace):
        assert str(produced).startswith(str(tmp_path))
    assert state.exists() and log.exists()
    assert list((workspace / "runs").glob("*")), "fire wrote no artifacts into the workspace"


def test_missing_scenario_fixture_fails_cleanly(tmp_path):
    state, log = paths(tmp_path)
    r = run(["probe"], "no-such-scenario", state, log)
    assert r.returncode != 0
    assert json.loads(r.stderr)["error"]


def test_unsupported_operation_fails(tmp_path):
    state, log = paths(tmp_path)
    r = run(["teleport"], "native-eligible", state, log)
    assert r.returncode != 0
    assert json.loads(r.stderr)["error"] == "unsupported_operation"
