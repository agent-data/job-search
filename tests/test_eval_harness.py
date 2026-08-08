"""Unit tests for scripts/eval_harness.py — the eval-scenario validator + the live-harness
support math (rep aggregation, control-delta) — and for the scheduler check in evals/run_eval.py.

Three jobs: (1) prove the REAL five evals.json are coherent, carry a discovery scenario each,
mark the named judgment-heavy scenarios stochastic with a control arm, and hold no pack-authored `gpt-5*`
literal from the pinned regression family; (2) unit-test the deterministic helpers the off-CI live harness
feeds observed pass/fail into (aggregate_reps / control_delta); (3) prove `evals/run_eval.py` fails a
run whose session left a scheduled job installed on the machine, in the last section of this file.
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
    """The audit-named judgment-heavy scenarios (fit verdicts, injection) must be repped +
    controlled — not left single-shot (AAS-TEST-08). The cross-source merge scenario left the
    runner's fixtures with the merge/pagination machinery when job-search-run was rewritten on the
    marker+record contract; the near-duplicate collapse that replaced it is deterministic."""
    loaded = eh.load_evals(str(ROOT))

    def scenario(skill, sid):
        return next(e for e in loaded[skill][1]["evals"] if e["id"] == sid)

    named = [
        ("evaluate-job-fit", 1), ("evaluate-job-fit", 2), ("evaluate-job-fit", 3),  # fit verdicts
        ("job-search-run", 13),   # injection-resistance
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
    """A workspace holding only files a run actually writes: the slim run record, the digest,
    the jobs.jsonl event log, and config.yaml. Field names and shapes come from
    skills/job-search-run/templates/run-record.example.json,
    skills/job-search-run/templates/jobs-event.example.json and
    skills/job-search/templates/config.example.yaml, so each assertion kind below points at a live
    structure."""
    ws = tmp_path / "ws"
    (ws / "runs").mkdir(parents=True)
    (ws / "reports").mkdir(parents=True)
    run_id = "2026-07-17T12-00-00Z"
    record = {
        "run_id": run_id,
        "trigger": "scheduled",
        "scheduler_id": "com.job-search.daily",
        "brief_revision": "9f2c41a7be05",
        "close_state": "complete",
        "run_health": "healthy",
        "sources": ["linkedin", "ashby"],
        "queries": ["ai-eng-remote", "ml-platform-sf"],
        "agent_data_usage": {"searches": 4, "detail_reads": 5, "other": 1, "total_metered": 10},
        "started_at": "2026-07-17T12:00:00Z",
        "completed_at": "2026-07-17T12:08:47Z",
    }
    (ws / "runs" / f"{run_id}.json").write_text(json.dumps(record), encoding="utf-8")
    events = [
        {"event": "evaluated", "source": "linkedin", "source_id": "4012345678",
         "run_id": run_id},
        {"event": "evaluated", "source": "ashby", "source_id": "a1b2c3d4",
         "run_id": run_id},
        # A third posting the same run could not judge from the search row, so it queued a detail
        # read. The field names come from queue-detail-read.sh:104-105, which writes this event.
        {"event": "queued", "source": "linkedin", "source_id": "4012349999",
         "run_id": run_id},
    ]
    (ws / "jobs.jsonl").write_text(
        "\n".join(json.dumps(r) for r in events), encoding="utf-8"
    )
    (ws / "reports" / "2026-07-17-digest.md").write_text(
        "# Job search digest — 2026-07-17\nRun health: healthy\n", encoding="utf-8"
    )
    (ws / "config.yaml").write_text(
        'version: 2\nsearch:\n  sources: ["linkedin", "ashby"]\n  freshness: "past-2-weeks"\n',
        encoding="utf-8",
    )
    return ws, run_id


def _all_kinds_evidence(ws, run_id):
    return {
        "workspace": str(ws),
        "assertions": [
            {"kind": "file_exists", "path": f"runs/{run_id}.json"},
            {"kind": "json_field_equals", "path": f"runs/{run_id}.json",
             "field": "trigger", "equals": "scheduled"},
            # dotted traversal, against the record's one nested object
            {"kind": "json_field_equals", "path": f"runs/{run_id}.json",
             "field": "agent_data_usage.total_metered", "equals": 10},
            # default field ("event"), against the append-only log a run writes
            {"kind": "jsonl_event_sequence", "path": "jobs.jsonl",
             "sequence": ["evaluated", "queued"]},
            {"kind": "text_absent", "path": "reports/2026-07-17-digest.md",
             "pattern": "Here's what I found so far"},
            {"kind": "text_matches", "path": "config.yaml",
             "pattern": r'freshness:\s*"past-2-weeks"'},
        ],
    }


def test_check_artifacts_all_five_kinds_pass(tmp_path):
    ws, run_id = _artifacts_workspace(tmp_path)
    assert eh.check_artifacts(_all_kinds_evidence(ws, run_id)) == []


def test_check_artifacts_flags_json_field_mismatch(tmp_path):
    ws, run_id = _artifacts_workspace(tmp_path)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "json_field_equals", "path": f"runs/{run_id}.json",
         "field": "run_health", "equals": "degraded"}]}
    hits = eh.check_artifacts(evidence)
    assert len(hits) == 1 and "run_health" in hits[0]


def test_check_artifacts_flags_missing_file(tmp_path):
    ws, _ = _artifacts_workspace(tmp_path)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "file_exists", "path": "runs/nope.json"}]}
    assert len(eh.check_artifacts(evidence)) == 1


def test_check_artifacts_text_absent_catches_forbidden_surface(tmp_path):
    ws, _ = _artifacts_workspace(tmp_path)
    (ws / "reports" / "2026-07-17-digest.md").write_text(
        "Here's what I found so far", encoding="utf-8")
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "text_absent", "path": "reports/2026-07-17-digest.md",
         "pattern": "Here's what I found so far"}]}
    assert len(eh.check_artifacts(evidence)) == 1


def test_check_artifacts_jsonl_sequence_out_of_order_fails(tmp_path):
    ws, _ = _artifacts_workspace(tmp_path)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "jsonl_event_sequence", "path": "jobs.jsonl",
         "sequence": ["queued", "evaluated"]}]}
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
# T6.1 fail-closed coverage: the paths a false green would hide. A required pattern that is ABSENT,
# a malformed line in a jsonl sequence target, and an unparseable JSON target must each produce a
# HIT — never a silent pass. These pin the current (correct) behavior so a regression can't loosen it.
# ---------------------------------------------------------------------------
def test_check_artifacts_text_matches_absent_pattern_fails_closed(tmp_path):
    # A user-declared REQUIRED pattern that is absent must fail (a hit), not pass by omission.
    ws, _ = _artifacts_workspace(tmp_path)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "text_matches", "path": "config.yaml",
         "pattern": r'freshness:\s*"never-configured-this-window"'}]}
    hits = eh.check_artifacts(evidence)
    assert len(hits) == 1 and "text_matches" in hits[0] and "config.yaml" in hits[0]


def test_check_artifacts_jsonl_malformed_line_fails_closed(tmp_path):
    # A malformed JSONL line in a jsonl_event_sequence target fails closed — the sequence would
    # otherwise match, so the malformed line (not an ordering miss) is what must trip the hit.
    ws, _ = _artifacts_workspace(tmp_path)
    (ws / "jobs.jsonl").write_text(
        '{"event": "evaluated", "source": "linkedin"}\n'
        "{not valid json here\n"
        '{"event": "queued", "source": "linkedin"}\n', encoding="utf-8")
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "jsonl_event_sequence", "path": "jobs.jsonl",
         "sequence": ["evaluated", "queued"]}]}
    hits = eh.check_artifacts(evidence)
    assert len(hits) == 1 and "malformed" in hits[0]


def test_check_artifacts_invalid_json_target_fails_closed(tmp_path):
    # A json_field_equals target that is not valid JSON fails closed (a hit), never a silent pass.
    ws, run_id = _artifacts_workspace(tmp_path)
    (ws / "runs" / f"{run_id}.json").write_text("{not: valid json,", encoding="utf-8")
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "json_field_equals", "path": f"runs/{run_id}.json",
         "field": "run_health", "equals": "healthy"}]}
    hits = eh.check_artifacts(evidence)
    assert len(hits) == 1 and "not valid JSON" in hits[0]


# ---------------------------------------------------------------------------
# T7.2: surface enforcement — belief 4's internal/user separation is checkable on the side that
# still has a product behind it. A user-facing artifact (chat, digest, home view, notification)
# must never carry a raw E-* code. The companion `internal_record` surface, which required a run
# record to RETAIN such a code, was retired on 2026-07-31: no shipped file writes an E-* code any
# more, so the rule demanded a shape the product cannot produce.
# ---------------------------------------------------------------------------
STRUCTURED_DIGEST = (
    "# Job search digest — 2026-07-17\n"
    "Run health: degraded\n\n"
    "agent-data's API allowance has been reached, so this run cannot continue until "
    "calls are available. Check your account at "
    "https://agent-data.motie.dev/settings/billing. Your existing matches are "
    "unaffected.\n"
)
# The E-QUOTA token is fixture data for the raw-code matcher, not a claim that any run writes
# one. The record's own fields are written in the shape
# skills/job-search-run/templates/run-record.example.json has.
LEAKED_CODE_DIGEST = STRUCTURED_DIGEST + "\n(internal classification: E-QUOTA)\n"
BLOCKED_RECORD = {"run_id": "2026-07-17T12-00-00Z", "close_state": "blocked",
                  "run_health": "degraded"}


def _belief4_workspace(base, digest_body, record):
    ws = base / "ws"
    (ws / "runs").mkdir(parents=True)
    (ws / "reports").mkdir(parents=True)
    run_id = "2026-07-17T12-00-00Z"
    (ws / "runs" / f"{run_id}.json").write_text(json.dumps(record), encoding="utf-8")
    (ws / "reports" / "2026-07-17-digest.md").write_text(digest_body, encoding="utf-8")
    return ws, run_id


def test_check_artifacts_user_facing_surface_rejects_a_raw_error_code(tmp_path):
    ws, _ = _belief4_workspace(tmp_path, LEAKED_CODE_DIGEST, BLOCKED_RECORD)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "file_exists", "path": "reports/2026-07-17-digest.md",
         "surface": "user_facing"}]}
    hits = eh.check_artifacts(evidence)
    assert len(hits) == 1 and "E-QUOTA" in hits[0] and "user_facing" in hits[0]


def test_check_artifacts_user_facing_surface_passes_when_structured(tmp_path):
    ws, _ = _belief4_workspace(tmp_path, STRUCTURED_DIGEST, BLOCKED_RECORD)
    evidence = {"workspace": str(ws), "assertions": [
        {"kind": "file_exists", "path": "reports/2026-07-17-digest.md",
         "surface": "user_facing"}]}
    assert eh.check_artifacts(evidence) == []


def test_check_artifacts_retired_internal_record_surface_is_rejected(tmp_path):
    # The retirement is the assertion: naming the removed surface is now a schema error, so an
    # evidence file still carrying it fails loudly instead of silently checking nothing.
    ws, run_id = _belief4_workspace(tmp_path, STRUCTURED_DIGEST, BLOCKED_RECORD)
    with pytest.raises(ValueError):
        eh.check_artifacts({"workspace": str(ws), "assertions": [
            {"kind": "file_exists", "path": f"runs/{run_id}.json",
             "surface": "internal_record"}]})


def test_check_artifacts_rejects_an_unknown_surface(tmp_path):
    ws, run_id = _belief4_workspace(tmp_path, STRUCTURED_DIGEST, BLOCKED_RECORD)
    with pytest.raises(ValueError):
        eh.check_artifacts({"workspace": str(ws), "assertions": [
            {"kind": "file_exists", "path": f"runs/{run_id}.json", "surface": "operator"}]})


def test_cli_check_artifacts_flags_a_user_facing_code_leak(tmp_path):
    ws, _ = _belief4_workspace(tmp_path, LEAKED_CODE_DIGEST, BLOCKED_RECORD)
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


# The suite's schedule-health liveness fixtures went with the derivation they graded: the
# 2026-07-30 skill overhaul left the home view reading the consent date and whether the job is
# installed, and shrank the operator manual to a routing card, so no skill scenario pins a
# liveness clock. The validator's fixed_time rules stay covered by the unit tests above.


# The milestone fixed-time fixtures this file used to require of job-search-run went away with the
# per-phase milestone timestamps themselves (metrics.json and the ledger) in the 2026-07-30 rewrite. The validator's fixed_time rules are still covered by the unit tests above and by the
# schedule-health liveness fixtures in the test just before this comment.


# ---------------------------------------------------------------------------
# T9.1: unique run marker — a stale artifact cannot create a false pass
#
# An artifact-evidence object may carry a top-level `run_marker` (a unique per-run
# nonce). Any assertion may set `run_marked: true`, and the harness then also requires
# the asserted file to CONTAIN that marker — so a leftover artifact from a prior run
# (which carries a different marker, or none) fails even a file_exists assertion.
# Additive: no run_marker / no run_marked -> identical to before.
# ---------------------------------------------------------------------------
DIGEST_REL = "reports/2026-07-17-digest.md"  # the digest _artifacts_workspace writes


def _stamped_workspace(tmp_path, marker):
    ws, run_id = _artifacts_workspace(tmp_path)
    # Stamp THIS run's marker into the run-specific artifacts.
    (ws / "runs" / f"{run_id}.json").write_text(
        json.dumps({"run_id": run_id, "trigger": "scheduled", "run_marker": marker,
                    "close_state": "complete", "run_health": "healthy"}), encoding="utf-8")
    (ws / DIGEST_REL).write_text(
        f"# Job search digest — 2026-07-17\nRun health: healthy\n<!-- run: {marker} -->\n",
        encoding="utf-8")
    return ws, run_id


def test_check_artifacts_run_marker_passes_when_the_artifact_carries_it(tmp_path):
    marker = "runmark-2026-07-17-abc123"
    ws, run_id = _stamped_workspace(tmp_path, marker)
    evidence = {"workspace": str(ws), "run_marker": marker, "assertions": [
        {"kind": "file_exists", "path": f"runs/{run_id}.json", "run_marked": True},
        {"kind": "file_exists", "path": DIGEST_REL, "run_marked": True}]}
    assert eh.check_artifacts(evidence) == []


def test_check_artifacts_run_marker_fails_on_a_stale_artifact(tmp_path):
    # The digest exists (file_exists alone would PASS) but predates this run: it carries no
    # fresh marker, so run_marked catches the stale artifact and fails.
    ws, _ = _artifacts_workspace(tmp_path)  # unstamped digest from a prior run
    fresh = "runmark-fresh-XYZ-999"
    evidence = {"workspace": str(ws), "run_marker": fresh, "assertions": [
        {"kind": "file_exists", "path": DIGEST_REL, "run_marked": True}]}
    hits = eh.check_artifacts(evidence)
    assert len(hits) == 1 and "run_marker" in hits[0] and fresh in hits[0]


def test_check_artifacts_run_marker_defeats_a_stale_false_pass_end_to_end(tmp_path):
    # Run A stamped its marker; Run B (a distinct nonce) reuses the workspace. B's assertions
    # would falsely pass on A's leftover digest without the marker check.
    marker_a = "runmark-A-111"
    ws, _ = _stamped_workspace(tmp_path, marker_a)
    marker_b = "runmark-B-222"
    evidence_b = {"workspace": str(ws), "run_marker": marker_b, "assertions": [
        {"kind": "file_exists", "path": DIGEST_REL, "run_marked": True}]}
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
    ws, _ = _artifacts_workspace(tmp_path)
    ep = tmp_path / "current-artifacts.json"
    ep.write_text(json.dumps({"workspace": str(ws), "run_marker": "runmark-fresh", "assertions": [
        {"kind": "file_exists", "path": DIGEST_REL, "run_marked": True}]}),
        encoding="utf-8")
    r = subprocess.run([sys.executable, str(MODULE), "--check-artifacts", str(ep)],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "run_marker" in r.stdout


# ---------------------------------------------------------------------------
# T9.1: the crown-jewel judgment-heavy set stays stochastic (reps>=5 + control)
# ---------------------------------------------------------------------------
def test_crown_jewel_judgment_scenarios_are_marked_stochastic():
    """The baited-shortcut resistance scenario whose verdict is model-judgment — every posting on
    the read list judged, with no early stop after the first strong match — must be repped +
    controlled, alongside the fit-verdict / injection set locked above (AAS-TEST-08). The
    weighted fair-share selection scenario left with the finite-allocator machinery in the
    job-search-run rewrite."""
    loaded = eh.load_evals(str(ROOT))

    def scenario(skill, sid):
        return next(e for e in loaded[skill][1]["evals"] if e["id"] == sid)

    for skill, sid in [("job-search-run", 15)]:
        e = scenario(skill, sid)
        assert e.get("stochastic") is True, f"{skill}#{sid} should be stochastic"
        assert e.get("reps", 0) >= eh.MIN_REPS, f"{skill}#{sid} reps < {eh.MIN_REPS}"
        c = e.get("control")
        assert isinstance(c, dict) and all(c.get(k) for k in ("arm", "strip", "expectation")), \
            f"{skill}#{sid} missing a no-guidance control arm"


# ---------------------------------------------------------------------------
# evals/run_eval.py: a scheduled job must not outlive the session that installed it
#
# On 2026-08-07 the `schedule` case installed a real launchd job. launchd starts its job outside
# the child's process group, so run_eval's teardown SIGKILL never reached it; it fired after the
# harness had moved the owner's real ~/.job-search back and wrote into it, and the run was still
# reported ok. run_eval now lists the machine's scheduler entries before and after the session and
# fails the run while a new one is still installed.
#
# Every test below points all three of run_eval's probes at a directory and two scripts it wrote
# itself, so nothing here installs, loads or removes a scheduler entry on the machine running the
# suite, and nothing here reads the machine's own launchd or crontab.
# ---------------------------------------------------------------------------
RUN_EVAL = ROOT / "evals" / "run_eval.py"


def _load_run_eval():
    """Import evals/run_eval.py by path. It imports only the standard library at module level —
    PyYAML is imported inside its main() — so this works in CI, which installs pytest and nothing
    else."""
    spec = _util.spec_from_file_location("run_eval", RUN_EVAL)
    mod = _util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


run_eval = _load_run_eval()


def _write_stub(path, stdout="", stderr="", status=0):
    """A stand-in scheduler command: prints fixed text on each stream and exits with a fixed
    status. It never talks to launchd or cron."""
    if stdout and not stdout.endswith("\n"):
        stdout += "\n"
    if stderr and not stderr.endswith("\n"):
        stderr += "\n"
    path.write_text("#!/bin/sh\ncat <<'OUT'\n%sOUT\ncat >&2 <<'ERR'\n%sERR\nexit %d\n"
                    % (stdout, stderr, status), encoding="utf-8")
    path.chmod(0o755)


def _launchctl_list_output(labels):
    """What `launchctl list` prints: a header row that names no job, then one row per loaded job."""
    return "PID\tStatus\tLabel\n" + "".join("-\t0\t%s\n" % label for label in labels)


def _scheduler_env(tmp_path, plists=(), labels=(), cron=(), crontab_status=0, crontab_stderr="",
                   launchctl_status=0, launchctl_stderr="", agents_dir=True):
    """Point all three of run_eval's scheduler probes at things this test wrote: a LaunchAgents
    directory, a `launchctl list` stand-in and a `crontab -l` stand-in.

    Called a second time with the same tmp_path it rewrites all three, which is how a test says
    what the session left behind. `agents_dir=False` removes the directory, for the machine that
    has no launchd at all.
    """
    agents = tmp_path / "LaunchAgents"
    if agents_dir:
        agents.mkdir(exist_ok=True)
        for existing in agents.iterdir():
            existing.unlink()
        for name in plists:
            (agents / name).write_text("<plist/>\n", encoding="utf-8")
    elif agents.is_dir():
        for existing in agents.iterdir():
            existing.unlink()
        agents.rmdir()
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    _write_stub(stubs / "launchctl", stdout=_launchctl_list_output(labels),
                stderr=launchctl_stderr, status=launchctl_status)
    _write_stub(stubs / "crontab", stdout="".join(line + "\n" for line in cron),
                stderr=crontab_stderr, status=crontab_status)
    return {run_eval.LAUNCH_AGENTS_ENV: str(agents),
            run_eval.LAUNCHCTL_ENV: str(stubs / "launchctl"),
            run_eval.CRONTAB_ENV: str(stubs / "crontab")}


def _clean_session():
    """One session that ended the way a graded run wants: exit 0, neither kill fired."""
    return {"rc": 0, "wall_s": 12.0, "timeout_killed": False, "event_killed": False}


def test_scheduler_snapshot_lists_every_class_from_its_own_probe(tmp_path):
    env = _scheduler_env(tmp_path, plists=["com.example.one.plist"],
                         labels=["com.apple.something", "com.example.one"],
                         cron=["# a comment schedules nothing", "0 8 * * * /usr/bin/true", ""])
    snap = run_eval.snapshot_schedulers(env)
    assert snap == {
        "entries": {"launchd-plists": ["com.example.one.plist"],
                    "launchd-loaded": ["com.apple.something", "com.example.one"],
                    "cron": ["0 8 * * * /usr/bin/true"]},
        "absent": {}, "failed": {}}


def test_teardown_fails_when_a_launchd_job_outlives_the_session(tmp_path):
    # This is the 2026-08-07 defect: the recurring-job flow installs a launchd job, launchd starts
    # it outside the child's process group, and it is still installed when the session is over.
    env = _scheduler_env(tmp_path, plists=["homebrew.mxcl.postgresql.plist"],
                         labels=["homebrew.mxcl.postgresql"])
    before = run_eval.snapshot_schedulers(env)
    _scheduler_env(tmp_path, plists=["homebrew.mxcl.postgresql.plist", "com.job-search.daily.plist"],
                   labels=["homebrew.mxcl.postgresql", "com.job-search.daily"])
    verdict = run_eval.scheduler_verdict(before, run_eval.snapshot_schedulers(env))

    assert verdict["ok"] is False
    assert verdict["new"] == {"launchd-plists": ["com.job-search.daily.plist"],
                              "launchd-loaded": ["com.job-search.daily"]}
    report = "\n".join(verdict["report"])
    assert "com.job-search.daily.plist" in report and "com.job-search.daily" in report
    assert "still installed" in report
    assert run_eval.run_ok([_clean_session()], verdict) is False


def test_teardown_fails_when_a_cron_line_outlives_the_session(tmp_path):
    env = _scheduler_env(tmp_path, cron=["0 3 * * * /usr/bin/backup"])
    before = run_eval.snapshot_schedulers(env)
    _scheduler_env(tmp_path, cron=["0 3 * * * /usr/bin/backup",
                                   "0 8 * * * claude -p 'run my job search'"])
    verdict = run_eval.scheduler_verdict(before, run_eval.snapshot_schedulers(env))

    assert verdict["ok"] is False
    assert verdict["new"] == {"cron": ["0 8 * * * claude -p 'run my job search'"]}
    assert any("run my job search" in line for line in verdict["report"])
    assert run_eval.run_ok([_clean_session()], verdict) is False


def test_a_second_copy_of_a_cron_line_already_there_is_a_new_entry(tmp_path):
    # Entries are counted, not set-compared: a duplicate of a line already in the crontab is
    # another installed job, and a set comparison would report the machine unchanged.
    env = _scheduler_env(tmp_path, cron=["0 8 * * * claude -p 'run my job search'"])
    before = run_eval.snapshot_schedulers(env)
    _scheduler_env(tmp_path, cron=["0 8 * * * claude -p 'run my job search'",
                                   "0 8 * * * claude -p 'run my job search'"])
    verdict = run_eval.scheduler_verdict(before, run_eval.snapshot_schedulers(env))

    assert verdict["ok"] is False
    assert verdict["new"] == {"cron": ["0 8 * * * claude -p 'run my job search'"]}


def test_a_launch_agents_directory_the_session_created_is_all_new(tmp_path):
    # A machine that had no LaunchAgents directory until the session wrote a job into it: the
    # class was absent before, so everything listed afterwards is new.
    env = _scheduler_env(tmp_path, agents_dir=False)
    before = run_eval.snapshot_schedulers(env)
    assert "launchd-plists" in before["absent"] and "launchd-plists" not in before["entries"]

    _scheduler_env(tmp_path, plists=["com.job-search.daily.plist"])
    verdict = run_eval.scheduler_verdict(before, run_eval.snapshot_schedulers(env))
    assert verdict["ok"] is False
    assert verdict["new"] == {"launchd-plists": ["com.job-search.daily.plist"]}


def test_teardown_reports_ok_when_the_machine_comes_back_the_way_it_was_found(tmp_path):
    env = _scheduler_env(tmp_path, plists=["com.google.keystone.agent.plist"],
                         labels=["com.google.keystone.agent"], cron=["0 3 * * * /usr/bin/backup"])
    before = run_eval.snapshot_schedulers(env)
    verdict = run_eval.scheduler_verdict(before, run_eval.snapshot_schedulers(env))

    assert verdict["ok"] is True and verdict["new"] == {}
    assert verdict["counts"] == {"cron": 1, "launchd-loaded": 1, "launchd-plists": 1}
    report = "\n".join(verdict["report"])
    assert "cron, launchd-loaded, launchd-plists" in report
    # The install no probe can list is named on every run, so a reader is never left assuming the
    # check covered a job the host's own command installed.
    assert "installed by the host's own command" in report
    assert run_eval.run_ok([_clean_session()], verdict) is True


def test_teardown_fails_loudly_when_a_probe_cannot_list_its_class(tmp_path):
    # The probe is on the machine and did not produce a listing. Nothing new was detected, which
    # is exactly the silent pass that let a job reach a real workspace, so this fails instead.
    env = _scheduler_env(tmp_path)
    before = run_eval.snapshot_schedulers(env)
    _scheduler_env(tmp_path, crontab_status=3, crontab_stderr="crontab: cannot read /var/at/tabs")
    after = run_eval.snapshot_schedulers(env)
    verdict = run_eval.scheduler_verdict(before, after)

    assert after["failed"]["cron"].startswith(str(tmp_path / "stubs" / "crontab"))
    assert verdict["new"] == {} and verdict["ok"] is False
    report = "\n".join(verdict["report"])
    assert "cannot list cron" in report and "cannot read /var/at/tabs" in report
    assert run_eval.run_ok([_clean_session()], verdict) is False


def test_an_empty_crontab_is_a_listing_rather_than_a_failed_probe(tmp_path):
    # Measured on this repo's macOS host: `crontab -l` exits 1 and prints
    # `crontab: no crontab for <user>` on stderr when the user has none. That is an empty crontab,
    # and treating it as a broken probe would fail every run on a machine with no cron jobs.
    env = _scheduler_env(tmp_path, crontab_status=1, crontab_stderr="crontab: no crontab for tester")
    snap = run_eval.snapshot_schedulers(env)

    assert snap["entries"]["cron"] == [] and snap["failed"] == {}
    assert run_eval.scheduler_verdict(snap, snap)["ok"] is True


def test_a_scheduler_command_this_machine_does_not_have_is_not_a_failed_probe(tmp_path):
    # launchd runs only on macOS and a machine with no `crontab` command has no user crontab, so a
    # missing command means the class cannot hold an entry — not that the probe broke.
    env = {run_eval.LAUNCH_AGENTS_ENV: str(tmp_path / "no-such-dir"),
           run_eval.LAUNCHCTL_ENV: str(tmp_path / "no-such-launchctl"),
           run_eval.CRONTAB_ENV: str(tmp_path / "no-such-crontab")}
    snap = run_eval.snapshot_schedulers(env)

    assert snap["failed"] == {}
    assert sorted(snap["absent"]) == ["cron", "launchd-loaded", "launchd-plists"]


def test_teardown_fails_when_no_scheduler_class_can_be_listed_at_all(tmp_path):
    # Nothing was enumerated, so the run looked nowhere. Reporting ok here would claim a clean
    # machine on the strength of no evidence.
    env = {run_eval.LAUNCH_AGENTS_ENV: str(tmp_path / "no-such-dir"),
           run_eval.LAUNCHCTL_ENV: str(tmp_path / "no-such-launchctl"),
           run_eval.CRONTAB_ENV: str(tmp_path / "no-such-crontab")}
    snap = run_eval.snapshot_schedulers(env)
    verdict = run_eval.scheduler_verdict(snap, snap)

    assert verdict["ok"] is False
    assert any("looked nowhere" in line for line in verdict["report"])
    assert run_eval.run_ok([_clean_session()], verdict) is False


def test_result_json_and_the_exit_status_come_from_one_value(tmp_path):
    """`run_ok` is the only thing main writes into `result.json`'s `ok` and the only thing it exits
    on, so a run whose sessions all returned 0 is still not ok while a job it found is installed."""
    env = _scheduler_env(tmp_path)
    before = run_eval.snapshot_schedulers(env)
    clean = run_eval.scheduler_verdict(before, run_eval.snapshot_schedulers(env))
    _scheduler_env(tmp_path, labels=["com.job-search.daily"])
    survived = run_eval.scheduler_verdict(before, run_eval.snapshot_schedulers(env))

    assert run_eval.run_ok([_clean_session()], clean) is True
    assert run_eval.run_ok([_clean_session()], survived) is False
    # The session failures the runner already graded stay graded, whatever the scheduler says.
    assert run_eval.run_ok([{"rc": 1, "wall_s": 1.0, "timeout_killed": False,
                             "event_killed": False}], clean) is False
    assert run_eval.run_ok([], clean) is False
