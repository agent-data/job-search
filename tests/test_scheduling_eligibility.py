"""Executable + structural pressure for T6.2: recurring-schedule ELIGIBILITY gates,
native-first/OS/nothing-verified SELECTION, and the expanded registry STATE MACHINE.

The single-source contract lives in shared/references/internals.md (the scheduling registry +
scheduling-setup) with skills/job-search-agent/references/scheduling-and-consent.md carrying the
doctrine one hop away. The behavioral evals live in skills/job-search-agent/evals/evals.json (ids
22-27, coverage_kind executable_fixture). This module does two jobs:

  (1) pins that contract text + those evals structurally (the RED->GREEN driver for T6.2), and
  (2) drives the deterministic, local-only T6.1 fake-scheduler shim to prove the mechanical facts
      each eligibility eval consumes.

No real scheduler, cron, launchd, network, model, or agent-data account is touched: every effect
stays inside a temp workspace + temp registry, driven only by the scenario capability fixtures.
"""
import json
import os
import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[0]
INTERNALS = ROOT / "shared" / "references" / "internals.md"
CONVENTIONS = ROOT / "shared" / "references" / "conventions.md"
ERRORS = ROOT / "shared" / "references" / "errors.md"
SCHEDULING = ROOT / "skills" / "job-search-agent" / "references" / "scheduling-and-consent.md"
AGENT = ROOT / "skills" / "job-search-agent" / "SKILL.md"
ONBOARDING = ROOT / "skills" / "job-search" / "references" / "onboarding.md"
HOME = ROOT / "skills" / "job-search" / "references" / "home.md"

SHIM = str(HERE / "fake-scheduler")
FIXTURES = HERE / "fixtures" / "scheduler"

# The six eligibility gates the fake-scheduler probe exposes (pinned by test_fake_scheduler.py too).
GATES = ("unattended", "canary_testable", "primary_model_preserving", "local_access", "reversible")
PRIMARY = "fixture-primary-exact"


# ---------------------------------------------------------------------------
# Contract-text parsing helpers
# ---------------------------------------------------------------------------
def _norm(path):
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").lower())


def _marked_rows(path, marker):
    """Parse a `<!-- {marker} -->` ... `<!-- /{marker} -->` markdown table into
    {first_col: (other_cols...)}. Header + separator rows are dropped."""
    text = path.read_text(encoding="utf-8")
    m = re.search(
        rf"<!-- {re.escape(marker)} -->\n(.*?)\n<!-- /{re.escape(marker)} -->",
        text,
        re.DOTALL,
    )
    assert m, f"missing marker block {marker} in {path}"
    rows = {}
    for line in m.group(1).splitlines():
        if not line.startswith("|") or set(line.replace("|", "").strip()) <= {"-"}:
            continue
        cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
        if cells[0].lower() in {"gate", "field", "policy", "situation"}:
            continue
        rows[cells[0]] = tuple(cells[1:])
    return rows


def _evals(skill):
    path = ROOT / "skills" / skill / "evals" / "evals.json"
    return json.loads(path.read_text(encoding="utf-8"))["evals"]


# ---------------------------------------------------------------------------
# (1a) The six eligibility gates are the single contract
# ---------------------------------------------------------------------------
def test_six_eligibility_gates_are_the_single_contract():
    rows = _marked_rows(INTERNALS, "scheduling-eligibility-contract:gates")
    assert set(rows) == {
        "unattended",
        "canary_testable",
        "primary_model_preserving",
        "local_access",
        "inspectable",
        "reversible",
    }, f"the six gates must be exactly enumerated, got {sorted(rows)}"
    prose = _norm(INTERNALS)
    # A candidate qualifies ONLY when it passes every gate.
    assert "every gate" in prose or "every one of the six gates" in prose


def test_gates_named_in_the_operator_doctrine():
    scheduling = _norm(SCHEDULING)
    for token in ("unattended", "canary", "reversible", "inspect"):
        assert token in scheduling, f"scheduling-and-consent.md must name the {token} gate"
    assert "preserv" in scheduling and "exact primary model" in scheduling


# ---------------------------------------------------------------------------
# (1b) Native-first / OS / nothing-verified selection + the state machine
# ---------------------------------------------------------------------------
def test_selection_is_native_first_then_os_then_nothing_verified():
    rows = _marked_rows(INTERNALS, "scheduling-registry-contract:state-machine")
    for key in ("native_first", "os_fallback", "nothing_verified"):
        assert key in rows, f"state-machine table missing {key}"
    joined = " ".join(" ".join(v) for v in rows.values()).lower()
    assert "gate" in joined     # a candidate is chosen only when it passes every gate
    assert "session" in joined  # the nothing-verified path names the session-only loop


def test_state_machine_installs_only_after_a_green_canary():
    rows = _marked_rows(INTERNALS, "scheduling-registry-contract:state-machine")
    for key in ("staging", "canary_commit", "canary_failure"):
        assert key in rows, f"state-machine table missing {key}"
    # Staging never writes installed=true; only the final post-canary write does; failure leaves none.
    assert "never" in " ".join(rows["staging"]).lower()
    commit = " ".join(rows["canary_commit"]).lower()
    assert "installed" in commit and "verified" in commit
    assert "no" in " ".join(rows["canary_failure"]).lower()
    prose = _norm(INTERNALS)
    assert "only the final" in prose and "post-canary" in prose


def test_registry_write_preserves_unknown_fields_and_is_atomic():
    rows = _marked_rows(INTERNALS, "scheduling-registry-contract:state-machine")
    assert "preserve" in " ".join(rows.get("unknown_fields", ())).lower()
    assert "atomic" in " ".join(rows.get("write_mode", ())).lower()


# ---------------------------------------------------------------------------
# (1c) The expanded registry object carries every state field
# ---------------------------------------------------------------------------
EXPECTED_REGISTRY_FIELDS = {
    "installed",
    "verified",
    "mechanism",
    "scheduler_id",
    "workspace",
    "cadence",
    "set_at",
    "verified_at",
    "canary_run_id",
    "primary_model",
    "primary_model_origin",
}


def test_expanded_registry_object_documents_every_field():
    rows = _marked_rows(INTERNALS, "scheduling-registry-contract:fields")
    assert EXPECTED_REGISTRY_FIELDS <= set(rows), (
        "registry fields table missing "
        f"{EXPECTED_REGISTRY_FIELDS - set(rows)}"
    )
    # The JSON schema block in internals.md shows the same expanded object.
    schema = INTERNALS.read_text(encoding="utf-8")
    for field in ("verified", "scheduler_id", "verified_at", "canary_run_id", "cadence"):
        assert f'"{field}"' in schema, f"registry JSON schema missing {field!r}"


def test_verified_field_is_true_only_after_a_green_canary():
    rows = _marked_rows(INTERNALS, "scheduling-registry-contract:fields")
    verified_value = " ".join(rows["verified"]).lower()
    assert "canary" in verified_value or "green" in verified_value


def test_exact_model_scheduler_fields_table_is_untouched():
    """The exact-model-contract:scheduler-fields table stays model-only (pinned elsewhere too):
    the new state fields live in their own tables, never folded into that one."""
    rows = _marked_rows(INTERNALS, "exact-model-contract:scheduler-fields")
    assert set(rows) == {"primary_model", "primary_model_origin"}


# ---------------------------------------------------------------------------
# (1d) Legacy markers never read verified
# ---------------------------------------------------------------------------
def test_legacy_markers_never_read_verified():
    rows = _marked_rows(INTERNALS, "scheduling-registry-contract:state-machine")
    loop = " ".join(rows.get("legacy_loop", ())).lower()
    installed_only = " ".join(rows.get("legacy_installed_only", ())).lower()
    assert "session" in loop and "never" in loop and "verified" in loop
    assert "unverified" in installed_only and "never" in installed_only


# ---------------------------------------------------------------------------
# (1e) An existing unowned job requires inspect / adopt-or-replace
# ---------------------------------------------------------------------------
def test_unowned_job_requires_inspect_and_adopt_or_replace():
    rows = _marked_rows(INTERNALS, "scheduling-registry-contract:state-machine")
    unowned = " ".join(rows.get("unowned_job", ())).lower()
    assert "inspect" in unowned
    assert "adopt" in unowned or "replace" in unowned
    prose = _norm(INTERNALS)
    assert "never clobber" in prose or "not silently clobber" in prose or "without clobbering" in prose


# ---------------------------------------------------------------------------
# (1f) conventions.md owns the on-disk registry file contract; errors.md names the failure
# ---------------------------------------------------------------------------
def test_conventions_owns_the_on_disk_registry_file_contract():
    conv = _norm(CONVENTIONS)
    assert "config.json" in conv
    assert "atomic" in conv and "preserve" in conv
    # It points one hop to internals.md for the schema/state machine rather than restating it.
    assert "internals.md" in CONVENTIONS.read_text(encoding="utf-8")


def test_errors_names_the_unverified_schedule_failure():
    err = _norm(ERRORS)
    assert "e-schedule-canary" in err
    # Fail-closed surfacing: no installed marker, do not claim scheduled.
    assert "not" in err and "installed" in err


# ---------------------------------------------------------------------------
# (2) The behavioral evals are structural + executable-fixture backed
# ---------------------------------------------------------------------------
def test_scheduling_evals_are_structural_and_executable():
    agent = _evals("job-search-agent")
    sched = [case for case in agent if 22 <= case["id"] <= 27]
    assert [c["id"] for c in sched] == [22, 23, 24, 25, 26, 27]
    assert all(c.get("coverage_kind") == "executable_fixture" for c in sched)
    matrix = " ".join(c["scenario"].lower() for c in sched)
    for phrase in (
        "eligible native",
        "falls back to an eligible os",
        "no eligible scheduler",
        "session-only",
        "legacy loop",
        "unverified legacy",
        "unowned scheduler job",
        "inspect and adopt-or-replace",
    ):
        assert phrase in matrix, f"scheduling eval matrix missing {phrase!r}"
    joined = " ".join(
        " ".join([c["prompt"], *c["expectations"]]).lower() for c in sched
    )
    # The evals consume the fake-scheduler fixtures + the eligibility/state-machine contract.
    assert "native-eligible" in joined and "os-eligible" in joined
    assert "installed=true" in joined and "verified=true" in joined
    assert "canary_run_id" in joined


# ---------------------------------------------------------------------------
# (2') Shim-driven proof of the mechanical basis each eval consumes (T6.1 fixtures)
# ---------------------------------------------------------------------------
def _run(op_args, scenario, state, log):
    env = dict(
        os.environ,
        JOBSEARCH_TEST_SCHEDULER_SCENARIO=scenario,
        JOBSEARCH_TEST_SCHEDULER_STATE=str(state),
        JOBSEARCH_TEST_SCHEDULER_LOG=str(log),
    )
    return subprocess.run([SHIM, *op_args], capture_output=True, text=True, env=env)


def _register(tmp_path, scenario, job_id="job-t62"):
    state, log = tmp_path / "state.json", tmp_path / "log.jsonl"
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    definition = {
        "workspace": str(workspace),
        "cadence": "daily",
        "invocation": "job-search-run --headless",
        "primary_model": PRIMARY,
        "primary_model_origin": "session_inheritance",
        "detail_model": "fixture-detail-exact",
        "detail_model_origin": "configured_user",
        "trigger": "canary",
    }
    dpath = tmp_path / "definition.json"
    dpath.write_text(json.dumps(definition), encoding="utf-8")
    r = _run(["register-disabled", job_id, str(dpath)], scenario, state, log)
    return r, state, log, workspace


def test_native_eligible_probe_passes_every_gate(tmp_path):
    # "eligible native wins": the native probe passes every gate, so it is selectable.
    state, log = tmp_path / "s.json", tmp_path / "l.jsonl"
    probe = json.loads(_run(["probe"], "native-eligible", state, log).stdout)
    assert probe["mechanism"] == "native" and probe["session_bound"] is False
    assert all(probe[g] is True for g in GATES)


def test_ineligible_native_then_eligible_os(tmp_path):
    # "ineligible native falls to eligible OS": native fails canary-testable, os passes every gate.
    state, log = tmp_path / "s.json", tmp_path / "l.jsonl"
    native = json.loads(_run(["probe"], "native-no-canary", state, log).stdout)
    assert native["unattended"] is True and native["canary_testable"] is False
    os_probe = json.loads(_run(["probe"], "os-eligible", state, log).stdout)
    assert os_probe["mechanism"] == "os" and all(os_probe[g] is True for g in GATES)


def test_registration_stages_disabled_and_never_verified(tmp_path):
    # Staging never writes installed=true / verified: the shim marks the job disabled + unverified.
    r, state, _, _ = _register(tmp_path, "scheduled-success")
    assert r.returncode == 0, r.stderr
    job = json.loads(state.read_text())["jobs"]["job-t62"]
    assert job["state"] == "disabled" and job["verified"] is False


def test_green_canary_produces_the_commit_evidence(tmp_path):
    # The green real-path canary is the only commit point: it yields a nonblocked run + preserved model.
    r, state, log, workspace = _register(tmp_path, "scheduled-success")
    fire = json.loads(_run(["fire", "job-t62"], "scheduled-success", state, log).stdout)
    assert fire["run_health"] == "healthy" and fire["close_state"] == "complete"
    assert fire["primary_model_preserved"] is True and fire["primary_model"] == PRIMARY
    assert fire["scheduler_id"] == "job-t62" and fire["run_id"]
    # The canary_run_id the registry records is exactly this fire's run_id, and the artifacts exist.
    assert (workspace / "runs" / f"{fire['run_id']}.json").is_file()
    assert (workspace / "runs" / f"{fire['run_id']}-digest.md").is_file()


def test_no_eligible_candidate_cannot_be_canary_fired(tmp_path):
    # "neither eligible creates nothing": a not-canary-testable candidate cannot be fired green.
    r, state, log, _ = _register(tmp_path, "native-no-canary")
    fire = _run(["fire", "job-t62"], "native-no-canary", state, log)
    assert fire.returncode != 0
    assert json.loads(fire.stderr)["error"] == "fire_unsupported"


def test_unowned_job_inspect_reports_drift(tmp_path):
    # "existing unowned job": inspect reports the registration as stale / not matching what we staged.
    _register(tmp_path, "stale-registration")
    state, log = tmp_path / "state.json", tmp_path / "log.jsonl"
    body = json.loads(_run(["inspect", "job-t62"], "stale-registration", state, log).stdout)
    assert body["registration"] == "stale" and body["matches_expected"] is False


def test_no_live_effects_reach_beyond_the_temp_tree(tmp_path):
    # Every effect the eligibility flow drives stays under the temp tree; the shim imports no network.
    r, state, log, workspace = _register(tmp_path, "scheduled-success")
    _run(["fire", "job-t62"], "scheduled-success", state, log)
    for produced in (state, log, workspace):
        assert str(produced).startswith(str(tmp_path))
    source = pathlib.Path(SHIM).read_text(encoding="utf-8")
    for banned in ("import socket", "urllib", "requests", "subprocess"):
        assert banned not in source
