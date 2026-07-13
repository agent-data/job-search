"""Unit tests for scripts/eval_harness.py — the eval-scenario validator + the live-harness
support math (rep aggregation, control-delta).

Two jobs: (1) prove the REAL five evals.json are coherent, carry a discovery scenario per skill,
mark the named judgment-heavy scenarios stochastic with a control arm, and hold no host model-id
literal; (2) unit-test the deterministic helpers the off-CI live harness feeds observed pass/fail
into (aggregate_reps / control_delta).
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
    assert offenders == [], f"literal model ids in evals: {offenders} (assert the tier binding instead)"


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
    assert any("literal model id" in h for h in hits)


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
