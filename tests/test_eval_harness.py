"""Unit tests for scripts/eval_harness.py — the eval-scenario validator + the live-harness
support math (rep aggregation, control-delta).

Two jobs: (1) prove the REAL five evals.json are coherent, carry a discovery scenario per skill,
mark the named judgment-heavy scenarios stochastic with a control arm, and hold no pack-authored `gpt-5*`
literal from the pinned regression family; (2) unit-test the deterministic helpers the off-CI live harness
feeds observed pass/fail into (aggregate_reps / control_delta).
"""
import json
import pathlib
import subprocess
import sys
from importlib import util as _util

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "eval_harness.py"


def _load_module():
    spec = _util.spec_from_file_location("eval_harness", MODULE)
    mod = _util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eh = _load_module()


# ---------------------------------------------------------------------------
# The real suite is coherent
# ---------------------------------------------------------------------------
def test_all_real_evals_valid():
    hits = eh.validate_evals(str(ROOT))
    assert hits == [], "eval scenarios incoherent:\n" + "\n".join(hits)


def test_real_suite_coverage():
    hits = eh.validate_coverage(str(ROOT))
    assert hits == [], "\n".join(hits)


def test_cli_reports_clean():
    r = subprocess.run([sys.executable, str(MODULE), "--root", str(ROOT)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "coherent" in r.stdout


def test_no_gpt5_literal_in_any_eval():
    """finding #24 / the `grep -rn gpt-5 skills/*/evals/` gate, pinned as a regression test."""
    offenders = []
    for path in sorted(ROOT.glob("skills/*/evals/evals.json")):
        if eh.MODEL_ID_LITERAL.search(path.read_text(encoding="utf-8")):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == [], (
        f"pack-authored gpt-5* literals in evals: {offenders} "
        "(legacy v1 may use host tier roles; v2 injects an exact host-resolved id at runtime)"
    )


def test_every_skill_has_a_discovery_scenario():
    disc = eh.discovery_scenarios(str(ROOT))
    skills = {name for name, _ in disc}
    loaded = set(eh.load_evals(str(ROOT)).keys())
    assert skills == loaded, f"skills missing a discovery scenario: {loaded - skills}"


def test_discovery_scenarios_cover_the_four_overlap_pairs():
    disc = eh.discovery_scenarios(str(ROOT))
    boundaries = set()
    for name, e in disc:
        for other in e["must_not_select"]:
            boundaries.add(frozenset((name, other)))
    for a, b in eh.OVERLAP_PAIRS:
        assert frozenset((a, b)) in boundaries, f"overlap pair {a} <-> {b} not disambiguated"


def test_named_judgment_scenarios_are_stochastic():
    """The audit-named judgment-heavy scenarios (fit verdicts, injection, cross-source merge)
    must be repped + controlled — not left single-shot (AAS-TEST-08)."""
    loaded = eh.load_evals(str(ROOT))

    def scenario(skill, sid):
        return next(e for e in loaded[skill][1]["evals"] if e["id"] == sid)

    named = [
        ("evaluate-job-fit", 1), ("evaluate-job-fit", 2), ("evaluate-job-fit", 3),  # fit verdicts
        ("job-search-run", 13),   # injection-resistance
        ("job-search-run", 19),   # cross-source merge
    ]
    for skill, sid in named:
        e = scenario(skill, sid)
        assert e.get("stochastic") is True, f"{skill}#{sid} should be stochastic"
        assert e.get("reps", 0) >= eh.MIN_REPS, f"{skill}#{sid} reps < {eh.MIN_REPS}"
        assert isinstance(e.get("control"), dict), f"{skill}#{sid} missing control arm"


def test_every_stochastic_scenario_has_reps_and_control():
    for name, (_rel, data) in eh.load_evals(str(ROOT)).items():
        for e in data["evals"]:
            if e.get("stochastic"):
                assert e.get("reps", 0) >= eh.MIN_REPS, f"{name}#{e['id']} reps"
                c = e.get("control")
                assert isinstance(c, dict) and all(c.get(k) for k in ("arm", "strip", "expectation")), \
                    f"{name}#{e['id']} control arm"


# ---------------------------------------------------------------------------
# The validator catches malformed scenarios (self-test)
# ---------------------------------------------------------------------------
def _write(tmp_path, skill, data):
    p = tmp_path / "skills" / skill / "evals" / "evals.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _good_file(skill="evaluate-job-fit"):
    return {
        "skill_name": skill,
        "evals": [
            {"id": 1, "prompt": "p", "expectations": ["e"]},
            {"id": 2, "prompt": "p", "discovery": True, "stochastic": True, "reps": 5,
             "siblings": ["job-search-run"], "must_select": skill, "must_not_select": ["job-search-run"],
             "control": {"arm": "no-guidance", "strip": "s", "expectation": "x"},
             "expectations": ["selected among siblings"]},
        ],
    }


def test_validator_accepts_a_good_file(tmp_path):
    # Well-formed files (coverage across the whole suite is a separate check). Seed the sibling
    # too so the discovery scenario's sibling/must_not_select references resolve.
    _write(tmp_path, "evaluate-job-fit", _good_file())
    _write(tmp_path, "job-search-run",
           {"skill_name": "job-search-run", "evals": [{"id": 1, "prompt": "p", "expectations": ["e"]}]})
    assert eh.validate_evals(str(tmp_path)) == []


def test_validator_flags_invalid_json(tmp_path):
    p = tmp_path / "skills" / "x" / "evals" / "evals.json"
    p.parent.mkdir(parents=True)
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        eh.validate_evals(str(tmp_path))


def test_validator_flags_gpt5_literal(tmp_path):
    data = _good_file()
    data["evals"][0]["expectations"] = ["uses gpt-5.4 by default"]
    _write(tmp_path, "evaluate-job-fit", data)
    hits = eh.validate_evals(str(tmp_path))
    assert any(
        "forbidden pack-authored gpt-5* literal family" in h
        and "legacy v1 may name selectors" in h
        and "v2 must inject an exact host-resolved id at runtime" in h
        for h in hits
    )


def test_validator_flags_noncontiguous_ids(tmp_path):
    data = _good_file()
    data["evals"][1]["id"] = 9
    _write(tmp_path, "evaluate-job-fit", data)
    hits = eh.validate_evals(str(tmp_path))
    assert any("contiguous" in h for h in hits)


def test_validator_flags_stochastic_without_control(tmp_path):
    data = _good_file()
    del data["evals"][1]["control"]
    _write(tmp_path, "evaluate-job-fit", data)
    hits = eh.validate_evals(str(tmp_path))
    assert any("control" in h for h in hits)


def test_validator_flags_underpowered_reps(tmp_path):
    data = _good_file()
    data["evals"][1]["reps"] = 3
    _write(tmp_path, "evaluate-job-fit", data)
    hits = eh.validate_evals(str(tmp_path))
    assert any("reps >=" in h for h in hits)


def test_validator_flags_discovery_missing_siblings(tmp_path):
    data = _good_file()
    del data["evals"][1]["siblings"]
    _write(tmp_path, "evaluate-job-fit", data)
    hits = eh.validate_evals(str(tmp_path))
    assert any("siblings" in h for h in hits)


def test_validator_flags_discovery_must_select_mismatch(tmp_path):
    data = _good_file()
    data["evals"][1]["must_select"] = "job-search-run"  # != this file's skill
    _write(tmp_path, "evaluate-job-fit", data)
    hits = eh.validate_evals(str(tmp_path))
    assert any("must_select" in h for h in hits)


# ---------------------------------------------------------------------------
# Rep aggregation — pass-rate + variance
# ---------------------------------------------------------------------------
def test_aggregate_reps_rate_and_variance():
    r = eh.aggregate_reps([True, True, True, True, False])  # 4/5
    assert r["n"] == 5 and r["passes"] == 4
    assert r["pass_rate"] == pytest.approx(0.8)
    assert r["variance"] == pytest.approx(0.16)  # p*(1-p) = .8*.2
    assert r["stdev"] == pytest.approx(0.4)
    assert r["meets_min_reps"] is True


def test_aggregate_reps_all_pass_zero_variance():
    r = eh.aggregate_reps([1, 1, 1, 1, 1])
    assert r["pass_rate"] == 1.0 and r["variance"] == 0.0


def test_aggregate_reps_flags_underpowered():
    assert eh.aggregate_reps([1, 0, 1])["meets_min_reps"] is False


def test_aggregate_reps_empty_raises():
    with pytest.raises(ValueError):
        eh.aggregate_reps([])


def test_control_delta_guided_beats_control():
    d = eh.control_delta([1, 1, 1, 1, 1], [1, 0, 0, 0, 0])  # 1.0 vs 0.2
    assert d["delta"] == pytest.approx(0.8)
    assert d["guided_beats_control"] is True


def test_control_delta_no_lift_is_flagged():
    d = eh.control_delta([1, 0, 1, 0, 0], [1, 1, 0, 1, 1])  # guided 0.4 < control 0.8
    assert d["guided_beats_control"] is False


# ---------------------------------------------------------------------------
# Opt-in dev mode: --check-artifacts (T6.1)
#
# A local, untracked evidence file names a workspace plus assertions the off-CI live
# canary harness records. These are schema-validated and evaluated against real files;
# the mode is invoked only with an explicit path, so CI's --root run never needs them.
# ---------------------------------------------------------------------------
def _artifacts_workspace(tmp_path):
    ws = tmp_path / "ws"
    (ws / "runs").mkdir(parents=True)
    run_id = "2026-07-17T12-00-00Z"
    record = {
        "trigger": "scheduled",
        "scheduler_id": "job-1",
        "run_health": "healthy",
        "lifecycle": {"close_state": "complete"},
        "primary_model": "fixture-primary-exact",
    }
    (ws / "runs" / f"{run_id}.json").write_text(json.dumps(record), encoding="utf-8")
    ledger = [
        {"event": "run_started", "phase": "preflight"},
        {"event": "phase_changed", "phase": "searching"},
        {"event": "posting_state", "state": "queued"},
        {"event": "phase_changed", "phase": "finalizing"},
        {"event": "run_closed", "close_state": "complete"},
    ]
    (ws / "runs" / f".lifecycle-{run_id}.jsonl").write_text(
        "\n".join(json.dumps(r) for r in ledger), encoding="utf-8"
    )
    (ws / "runs" / f"{run_id}-digest.md").write_text(
        "# Job search digest\nRun health: healthy\n", encoding="utf-8"
    )
    (ws / "config.yaml").write_text(
        'version: 2\nsearch:\n  detail_model: "fixture-detail-exact"\n', encoding="utf-8"
    )
    return ws, run_id


def _all_kinds_evidence(ws, run_id):
    return {
        "workspace": str(ws),
        "assertions": [
            {"kind": "file_exists", "path": f"runs/{run_id}.json"},
            {"kind": "json_field_equals", "path": f"runs/{run_id}.json",
             "field": "trigger", "equals": "scheduled"},
            {"kind": "json_field_equals", "path": f"runs/{run_id}.json",
             "field": "lifecycle.close_state", "equals": "complete"},
            {"kind": "jsonl_event_sequence", "path": f"runs/.lifecycle-{run_id}.jsonl",
             "field": "phase", "sequence": ["preflight", "searching", "finalizing"]},
            {"kind": "text_absent", "path": f"runs/{run_id}-digest.md",
             "pattern": "Here's what I found so far"},
            {"kind": "text_matches", "path": "config.yaml",
             "pattern": r'detail_model:\s*"fixture-detail-exact"'},
        ],
    }


def test_check_artifacts_all_five_kinds_pass(tmp_path):
    ws, run_id = _artifacts_workspace(tmp_path)
    assert eh.check_artifacts(_all_kinds_evidence(ws, run_id)) == []


def test_check_artifacts_flags_json_field_mismatch(tmp_path):
    ws, run_id = _artifacts_workspace(tmp_path)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "json_field_equals", "path": f"runs/{run_id}.json",
         "field": "run_health", "equals": "blocked"}]}
    hits = eh.check_artifacts(evidence)
    assert len(hits) == 1 and "run_health" in hits[0]


def test_check_artifacts_flags_missing_file(tmp_path):
    ws, _ = _artifacts_workspace(tmp_path)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "file_exists", "path": "runs/nope.json"}]}
    assert len(eh.check_artifacts(evidence)) == 1


def test_check_artifacts_text_absent_catches_forbidden_surface(tmp_path):
    ws, run_id = _artifacts_workspace(tmp_path)
    (ws / "runs" / f"{run_id}-digest.md").write_text(
        "Here's what I found so far", encoding="utf-8")
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "text_absent", "path": f"runs/{run_id}-digest.md",
         "pattern": "Here's what I found so far"}]}
    assert len(eh.check_artifacts(evidence)) == 1


def test_check_artifacts_jsonl_sequence_out_of_order_fails(tmp_path):
    ws, run_id = _artifacts_workspace(tmp_path)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "jsonl_event_sequence", "path": f"runs/.lifecycle-{run_id}.jsonl",
         "field": "phase", "sequence": ["finalizing", "preflight"]}]}
    assert len(eh.check_artifacts(evidence)) == 1


def test_check_artifacts_rejects_unknown_kind(tmp_path):
    ws, _ = _artifacts_workspace(tmp_path)
    with pytest.raises(ValueError):
        eh.check_artifacts({"workspace": str(ws),
                            "assertions": [{"kind": "telepathy", "path": "x"}]})


def test_check_artifacts_rejects_malformed_schema(tmp_path):
    ws, _ = _artifacts_workspace(tmp_path)
    with pytest.raises(ValueError):
        eh.check_artifacts({"assertions": []})           # no workspace
    with pytest.raises(ValueError):
        eh.check_artifacts({"workspace": str(ws)})       # no assertions
    with pytest.raises(ValueError):
        eh.check_artifacts({"workspace": str(ws), "assertions": [
            {"kind": "json_field_equals", "path": "p"}]})  # missing field/equals


# ---------------------------------------------------------------------------
# T7.2: surface enforcement — belief 4's internal/user separation is checkable.
# A user-facing artifact (chat/digest/home/notification) must never carry a raw
# E-* code; the internal record must retain it. The `surface` flag makes the
# harness enforce the correct direction, extending --check-artifacts additively.
# ---------------------------------------------------------------------------
STRUCTURED_DIGEST = (
    "# Job search digest\n"
    "Run health: blocked (action needed)\n\n"
    "agent-data's API allowance has been reached, so this run cannot continue until "
    "calls are available. Check your account at "
    "https://agent-data.motie.dev/settings/billing. Your existing matches are "
    "unaffected.\n"
)
LEAKED_CODE_DIGEST = STRUCTURED_DIGEST + "\n(internal classification: E-QUOTA)\n"
RECORD_WITH_CODE = {"run_health": "blocked", "error": {"code": "E-QUOTA"}}
RECORD_WITHOUT_CODE = {"run_health": "blocked", "error": {"reason": "quota rejected"}}


def _belief4_workspace(base, digest_body, record):
    ws = base / "ws"
    (ws / "runs").mkdir(parents=True)
    (ws / "reports").mkdir(parents=True)
    run_id = "2026-07-17T12-00-00Z"
    (ws / "runs" / f"{run_id}.json").write_text(json.dumps(record), encoding="utf-8")
    (ws / "reports" / "2026-07-17-digest.md").write_text(digest_body, encoding="utf-8")
    return ws, run_id


def test_check_artifacts_user_facing_surface_rejects_a_raw_error_code(tmp_path):
    ws, _ = _belief4_workspace(tmp_path, LEAKED_CODE_DIGEST, RECORD_WITH_CODE)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "file_exists", "path": "reports/2026-07-17-digest.md",
         "surface": "user_facing"}]}
    hits = eh.check_artifacts(evidence)
    assert len(hits) == 1 and "E-QUOTA" in hits[0] and "user_facing" in hits[0]


def test_check_artifacts_user_facing_surface_passes_when_structured(tmp_path):
    ws, _ = _belief4_workspace(tmp_path, STRUCTURED_DIGEST, RECORD_WITH_CODE)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "file_exists", "path": "reports/2026-07-17-digest.md",
         "surface": "user_facing"}]}
    assert eh.check_artifacts(evidence) == []


def test_check_artifacts_internal_record_surface_requires_the_code(tmp_path):
    ws, run_id = _belief4_workspace(tmp_path, STRUCTURED_DIGEST, RECORD_WITHOUT_CODE)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "file_exists", "path": f"runs/{run_id}.json",
         "surface": "internal_record"}]}
    hits = eh.check_artifacts(evidence)
    assert len(hits) == 1 and "internal_record" in hits[0]


def test_check_artifacts_internal_record_surface_passes_with_the_code(tmp_path):
    ws, run_id = _belief4_workspace(tmp_path, STRUCTURED_DIGEST, RECORD_WITH_CODE)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "json_field_equals", "path": f"runs/{run_id}.json",
         "field": "error.code", "equals": "E-QUOTA", "surface": "internal_record"}]}
    assert eh.check_artifacts(evidence) == []


def test_check_artifacts_surface_enforces_both_directions_at_once(tmp_path):
    good_ws, gid = _belief4_workspace(tmp_path / "good", STRUCTURED_DIGEST, RECORD_WITH_CODE)
    good = {"workspace": str(good_ws), "assertions": [
        {"kind": "file_exists", "path": "reports/2026-07-17-digest.md", "surface": "user_facing"},
        {"kind": "file_exists", "path": f"runs/{gid}.json", "surface": "internal_record"}]}
    assert eh.check_artifacts(good) == []
    # Inverted separation: the code leaked to the digest AND vanished from the record -> both fail.
    bad_ws, bid = _belief4_workspace(tmp_path / "bad", LEAKED_CODE_DIGEST, RECORD_WITHOUT_CODE)
    bad = {"workspace": str(bad_ws), "assertions": [
        {"kind": "file_exists", "path": "reports/2026-07-17-digest.md", "surface": "user_facing"},
        {"kind": "file_exists", "path": f"runs/{bid}.json", "surface": "internal_record"}]}
    assert len(eh.check_artifacts(bad)) == 2


def test_check_artifacts_rejects_an_unknown_surface(tmp_path):
    ws, run_id = _belief4_workspace(tmp_path, STRUCTURED_DIGEST, RECORD_WITH_CODE)
    with pytest.raises(ValueError):
        eh.check_artifacts({"workspace": str(ws), "assertions": [
            {"kind": "file_exists", "path": f"runs/{run_id}.json", "surface": "operator"}]})


def test_cli_check_artifacts_flags_a_user_facing_code_leak(tmp_path):
    ws, _ = _belief4_workspace(tmp_path, LEAKED_CODE_DIGEST, RECORD_WITH_CODE)
    ep = tmp_path / "current-artifacts.json"
    ep.write_text(json.dumps({"workspace": str(ws), "assertions": [
        {"kind": "file_exists", "path": "reports/2026-07-17-digest.md",
         "surface": "user_facing"}]}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(MODULE), "--check-artifacts", str(ep)],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "user_facing" in r.stdout


# ---------------------------------------------------------------------------
# Opt-in dev mode: --aggregate-results (T6.1)
# ---------------------------------------------------------------------------
def _results_row(**over):
    row = {
        "skill": "job-search-run",
        "scenario_id": "scheduled-success",
        "exact_model": "fixture-primary-exact",
        "guided": [True, True, True, True, True],
        "control": [True, False, False, False, False],
        "required_control_delta": 0.4,
    }
    row.update(over)
    return row


def test_aggregate_results_row_meets_required_delta():
    report = eh.aggregate_results({"scenarios": [_results_row()]})
    row = report["scenarios"][0]
    assert row["delta"] == pytest.approx(0.8)
    assert row["meets_required_delta"] is True
    assert row["meets_min_reps"] is True
    assert row["ok"] is True
    assert report["ok"] is True


def test_aggregate_results_flags_insufficient_delta():
    report = eh.aggregate_results({"scenarios": [
        _results_row(guided=[1, 1, 0, 0, 0], control=[1, 1, 0, 0, 0],
                     required_control_delta=0.3)]})
    assert report["scenarios"][0]["meets_required_delta"] is False
    assert report["ok"] is False


def test_aggregate_results_flags_underpowered_guided_arm():
    report = eh.aggregate_results({"scenarios": [
        _results_row(guided=[1, 1, 1], control=[0, 0, 0])]})
    assert report["scenarios"][0]["meets_min_reps"] is False
    assert report["ok"] is False


def test_aggregate_results_rejects_malformed_rows():
    with pytest.raises(ValueError):
        eh.aggregate_results({"scenarios": [{"skill": "s"}]})  # missing fields
    with pytest.raises(ValueError):
        eh.aggregate_results({"scenarios": []})                # empty
    with pytest.raises(ValueError):
        eh.aggregate_results({})                               # no scenarios key


# ---------------------------------------------------------------------------
# CLI: the two opt-in modes work, and neither is required by the free --root run
# ---------------------------------------------------------------------------
def test_cli_check_artifacts_mode_clean(tmp_path):
    ws, run_id = _artifacts_workspace(tmp_path)
    ep = tmp_path / "current-artifacts.json"
    ep.write_text(json.dumps(_all_kinds_evidence(ws, run_id)), encoding="utf-8")
    r = subprocess.run([sys.executable, str(MODULE), "--check-artifacts", str(ep)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_cli_check_artifacts_mode_reports_failure(tmp_path):
    ws, _ = _artifacts_workspace(tmp_path)
    ep = tmp_path / "current-artifacts.json"
    ep.write_text(json.dumps({"workspace": str(ws), "assertions": [
        {"kind": "file_exists", "path": "runs/missing.json"}]}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(MODULE), "--check-artifacts", str(ep)],
                       capture_output=True, text=True)
    assert r.returncode == 1


def test_cli_aggregate_results_mode_clean(tmp_path):
    ep = tmp_path / "current-results.json"
    ep.write_text(json.dumps({"scenarios": [_results_row(control=[0, 0, 0, 0, 0],
                  required_control_delta=0.5)]}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(MODULE), "--aggregate-results", str(ep)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_cli_root_run_needs_no_evidence_files():
    # The CI path stays free and deterministic: --root must not require the untracked files.
    r = subprocess.run([sys.executable, str(MODULE), "--root", str(ROOT)],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "coherent" in r.stdout


# ---------------------------------------------------------------------------
# T9.1: fixed-time fixtures (deterministic clocks) for milestone/liveness checks
#
# A scenario may declare a `fixed_time` object pinning the reference clock so a
# milestone-timestamp or schedule-liveness check is deterministic (never wall-clock).
# validate_evals gates its coherence when present; it is additive (no fixed_time ->
# unchanged) so --root and the T6.1/T7.2 modes are untouched.
# ---------------------------------------------------------------------------
def _write_pair(tmp_path, data):
    """Write a fixture evaluate-job-fit file plus the sibling its discovery scenario names,
    so validate_evals resolves cleanly and only the case under test can produce a hit."""
    _write(tmp_path, "evaluate-job-fit", data)
    _write(tmp_path, "job-search-run",
           {"skill_name": "job-search-run", "evals": [{"id": 1, "prompt": "p", "expectations": ["e"]}]})


def _fixed_time_file(now="2026-06-10T09:00:00-07:00", checks=("liveness",)):
    data = _good_file()
    data["evals"][0]["fixed_time"] = {"now": now, "checks": list(checks)}
    return data


def test_validator_accepts_a_coherent_fixed_time(tmp_path):
    _write_pair(tmp_path, _fixed_time_file())
    assert eh.validate_evals(str(tmp_path)) == []


def test_validator_accepts_a_multi_instant_fixed_time(tmp_path):
    # A DST-boundary liveness fixture pins two reference instants (before/after grace).
    data = _fixed_time_file(now=["2026-11-01T09:20:00-05:00", "2026-11-01T09:45:00-05:00"])
    _write_pair(tmp_path, data)
    assert eh.validate_evals(str(tmp_path)) == []


def test_validator_accepts_a_milestone_fixed_time(tmp_path):
    _write_pair(tmp_path, _fixed_time_file(checks=["milestone"]))
    assert eh.validate_evals(str(tmp_path)) == []


def test_validator_flags_fixed_time_that_is_not_an_object(tmp_path):
    data = _good_file()
    data["evals"][0]["fixed_time"] = "2026-06-10T09:00:00-07:00"
    _write_pair(tmp_path, data)
    hits = eh.validate_evals(str(tmp_path))
    assert any("fixed_time must be an object" in h for h in hits)


def test_validator_flags_fixed_time_non_iso_now(tmp_path):
    _write_pair(tmp_path, _fixed_time_file(now="today at 9am"))
    hits = eh.validate_evals(str(tmp_path))
    assert any("fixed_time.now" in h for h in hits)


def test_validator_flags_fixed_time_empty_now_list(tmp_path):
    _write_pair(tmp_path, _fixed_time_file(now=[]))
    hits = eh.validate_evals(str(tmp_path))
    assert any("fixed_time.now" in h for h in hits)


def test_validator_flags_fixed_time_unknown_check(tmp_path):
    _write_pair(tmp_path, _fixed_time_file(checks=["telemetry"]))
    hits = eh.validate_evals(str(tmp_path))
    assert any("fixed_time.checks" in h for h in hits)


def test_validator_flags_fixed_time_empty_checks(tmp_path):
    _write_pair(tmp_path, _fixed_time_file(checks=[]))
    hits = eh.validate_evals(str(tmp_path))
    assert any("fixed_time.checks" in h for h in hits)


def test_real_suite_schedule_health_scenarios_carry_a_liveness_fixed_time():
    """Every schedule-health (liveness) scenario pins a deterministic clock so its missed-fire /
    grace / DST derivation is reproducible — not wall-clock."""
    loaded = eh.load_evals(str(ROOT))
    liveness = []
    for skill in ("job-search-agent", "job-search"):
        for e in loaded[skill][1]["evals"]:
            if "schedule health" in e.get("scenario", "").lower():
                liveness.append((skill, e))
    assert liveness, "expected schedule-health liveness scenarios"
    for skill, e in liveness:
        ft = e.get("fixed_time")
        assert isinstance(ft, dict), f"{skill}#{e['id']} schedule-health scenario needs a fixed_time"
        assert "liveness" in ft.get("checks", []), f"{skill}#{e['id']} fixed_time must check liveness"


def test_real_suite_has_milestone_fixed_time_fixtures():
    """The run-lifecycle milestone-timestamp scenarios pin a deterministic clock."""
    loaded = eh.load_evals(str(ROOT))
    milestone = [
        e for e in loaded["job-search-run"][1]["evals"]
        if isinstance(e.get("fixed_time"), dict) and "milestone" in e["fixed_time"].get("checks", [])
    ]
    assert milestone, "job-search-run must carry milestone fixed-time fixtures"


# ---------------------------------------------------------------------------
# T9.1: unique run marker — a stale artifact cannot create a false pass
#
# An artifact-evidence object may carry a top-level `run_marker` (a unique per-run
# nonce). Any assertion may set `run_marked: true`, and the harness then also requires
# the asserted file to CONTAIN that marker — so a leftover artifact from a prior run
# (which carries a different marker, or none) fails even a file_exists assertion.
# Additive: no run_marker / no run_marked -> identical to before.
# ---------------------------------------------------------------------------
def _stamped_workspace(tmp_path, marker):
    ws, run_id = _artifacts_workspace(tmp_path)
    # Stamp THIS run's marker into the run-specific artifacts.
    (ws / "runs" / f"{run_id}.json").write_text(
        json.dumps({"trigger": "scheduled", "run_marker": marker,
                    "lifecycle": {"close_state": "complete"}}), encoding="utf-8")
    (ws / "runs" / f"{run_id}-digest.md").write_text(
        f"# Job search digest\nRun health: healthy\n<!-- run: {marker} -->\n", encoding="utf-8")
    return ws, run_id


def test_check_artifacts_run_marker_passes_when_the_artifact_carries_it(tmp_path):
    marker = "runmark-2026-07-17-abc123"
    ws, run_id = _stamped_workspace(tmp_path, marker)
    evidence = {"workspace": str(ws), "run_marker": marker, "assertions": [
        {"kind": "file_exists", "path": f"runs/{run_id}.json", "run_marked": True},
        {"kind": "file_exists", "path": f"runs/{run_id}-digest.md", "run_marked": True}]}
    assert eh.check_artifacts(evidence) == []


def test_check_artifacts_run_marker_fails_on_a_stale_artifact(tmp_path):
    # The digest exists (file_exists alone would PASS) but predates this run: it carries no
    # fresh marker, so run_marked catches the stale artifact and fails.
    ws, run_id = _artifacts_workspace(tmp_path)  # unstamped digest from a prior run
    fresh = "runmark-fresh-XYZ-999"
    evidence = {"workspace": str(ws), "run_marker": fresh, "assertions": [
        {"kind": "file_exists", "path": f"runs/{run_id}-digest.md", "run_marked": True}]}
    hits = eh.check_artifacts(evidence)
    assert len(hits) == 1 and "run_marker" in hits[0] and fresh in hits[0]


def test_check_artifacts_run_marker_defeats_a_stale_false_pass_end_to_end(tmp_path):
    # Run A stamped its marker; Run B (a distinct nonce) reuses the workspace. B's assertions
    # would falsely pass on A's leftover digest without the marker check.
    marker_a = "runmark-A-111"
    ws, run_id = _stamped_workspace(tmp_path, marker_a)
    marker_b = "runmark-B-222"
    evidence_b = {"workspace": str(ws), "run_marker": marker_b, "assertions": [
        {"kind": "file_exists", "path": f"runs/{run_id}-digest.md", "run_marked": True}]}
    hits = eh.check_artifacts(evidence_b)
    assert len(hits) == 1 and marker_b in hits[0]


def test_check_artifacts_run_marker_is_ignored_without_the_flag(tmp_path):
    # Additive: a run_marker present but no run_marked assertion behaves exactly as before.
    ws, run_id = _artifacts_workspace(tmp_path)
    evidence = {"workspace": str(ws), "run_marker": "runmark-unused", "assertions": [
        {"kind": "file_exists", "path": f"runs/{run_id}.json"}]}
    assert eh.check_artifacts(evidence) == []


def test_check_artifacts_run_marked_requires_a_top_level_run_marker(tmp_path):
    ws, run_id = _artifacts_workspace(tmp_path)
    with pytest.raises(ValueError):
        eh.check_artifacts({"workspace": str(ws), "assertions": [
            {"kind": "file_exists", "path": f"runs/{run_id}.json", "run_marked": True}]})


def test_check_artifacts_rejects_a_non_bool_run_marked(tmp_path):
    ws, run_id = _artifacts_workspace(tmp_path)
    with pytest.raises(ValueError):
        eh.check_artifacts({"workspace": str(ws), "run_marker": "m", "assertions": [
            {"kind": "file_exists", "path": f"runs/{run_id}.json", "run_marked": "yes"}]})


def test_check_artifacts_rejects_an_empty_run_marker(tmp_path):
    ws, run_id = _artifacts_workspace(tmp_path)
    with pytest.raises(ValueError):
        eh.check_artifacts({"workspace": str(ws), "run_marker": "", "assertions": [
            {"kind": "file_exists", "path": f"runs/{run_id}.json"}]})


def test_cli_check_artifacts_flags_a_stale_run_marker(tmp_path):
    ws, run_id = _artifacts_workspace(tmp_path)
    ep = tmp_path / "current-artifacts.json"
    ep.write_text(json.dumps({"workspace": str(ws), "run_marker": "runmark-fresh", "assertions": [
        {"kind": "file_exists", "path": f"runs/{run_id}-digest.md", "run_marked": True}]}),
        encoding="utf-8")
    r = subprocess.run([sys.executable, str(MODULE), "--check-artifacts", str(ep)],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "run_marker" in r.stdout


# ---------------------------------------------------------------------------
# T9.1: the crown-jewel judgment-heavy set stays stochastic (reps>=5 + control)
# ---------------------------------------------------------------------------
def test_crown_jewel_judgment_scenarios_are_marked_stochastic():
    """The baited-shortcut resistance scenarios whose verdict is model-judgment (fair-share
    selection, stop-after-first-match resistance) must be repped + controlled, alongside the
    fit-verdict / injection / merge set already locked above (AAS-TEST-08)."""
    loaded = eh.load_evals(str(ROOT))

    def scenario(skill, sid):
        return next(e for e in loaded[skill][1]["evals"] if e["id"] == sid)

    for skill, sid in [("job-search-run", 34), ("job-search-run", 60)]:
        e = scenario(skill, sid)
        assert e.get("stochastic") is True, f"{skill}#{sid} should be stochastic"
        assert e.get("reps", 0) >= eh.MIN_REPS, f"{skill}#{sid} reps < {eh.MIN_REPS}"
        c = e.get("control")
        assert isinstance(c, dict) and all(c.get(k) for k in ("arm", "strip", "expectation")), \
            f"{skill}#{sid} missing a no-guidance control arm"
