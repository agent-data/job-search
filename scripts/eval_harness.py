#!/usr/bin/env python3
"""Eval-harness support: validate the skill eval scenarios and provide the pieces the
LIVE (Claude-driven) harness needs — a rep aggregator (pass-rate + variance) and a no-guidance
control-delta.

Context. The skill evals are a LIVE HARNESS: each `skills/<skill>/evals/evals.json` carries a
prose `harness` (how to set up the fake-agent-data shim + drive the skill) and per-scenario
`expectations` graded by the driver. There is no pytest that "runs" a skill — the behavioral
N>=5 reps happen off-CI against the shim. What CI CAN gate is the SCENARIOS' structural
coherence and the deterministic math the driver feeds its observed pass/fail into. That is this
module: `validate_evals` is the structural gate — it also de-literalizes the model id (evals must
name the portable tier the agent self-binds, never a host model id); `aggregate_reps` /
`control_delta` are the rate+variance + control-arm capability. Stdlib only; mirrors doc_lint/philosophy_guard shape
(scan -> hits; main prints and returns 1 on failure).
"""
import argparse
import glob
import json
import math
import os
import re
import sys

EVAL_GLOB = "skills/*/evals/evals.json"
MIN_REPS = 5  # AAS-TEST-08: judgment-heavy behavioral scenarios run at N>=5.
# The four overlap pairs the routing web must disambiguate (design Verification / finding #22).
OVERLAP_PAIRS = (
    ("job-search-run", "job-search"),                  # run  <-> search
    ("job-search", "job-search-agent"),                # search <-> agent
    ("job-preference-interview", "evaluate-job-fit"),  # interview -> fit
    ("evaluate-job-fit", "job-search-run"),            # fit -> run
)
MODEL_ID_LITERAL = re.compile(r"gpt-5", re.I)  # AAS-TEST-04 / finding #24: no host model id in evals.


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_evals(root="."):
    """Return {skill_name: (rel_path, parsed_json)} for every evals.json under `root`.

    Raises ValueError on invalid JSON (a hard gate — a broken eval file is never "clean").
    """
    out = {}
    for path in sorted(glob.glob(os.path.join(root, EVAL_GLOB))):
        rel = os.path.relpath(path, root)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        try:
            data = json.loads(text)
        except ValueError as e:
            raise ValueError(f"{rel}: invalid JSON ({e})") from e
        name = data.get("skill_name") or rel
        out[name] = (rel, data)
    return out


# ---------------------------------------------------------------------------
# Structural validation (the CI gate)
# ---------------------------------------------------------------------------
def _is_nonempty_str(v):
    return isinstance(v, str) and v.strip() != ""


def validate_evals(root="."):
    """Return a list of coherence hits (empty == clean). Validates every evals.json:
    ids contiguous-from-1 + unique; prompt/expectations well-formed; no `gpt-5` literal;
    discovery scenarios name their siblings + routing target; stochastic scenarios carry
    reps>=5 + a no-guidance control arm."""
    loaded = load_evals(root)
    known_skills = set(loaded.keys())
    hits = []

    for name, (rel, data) in sorted(loaded.items()):
        if not _is_nonempty_str(data.get("skill_name")):
            hits.append(f"{rel}: missing non-empty skill_name")
        if "harness" in data and not _is_nonempty_str(data["harness"]):
            hits.append(f"{rel}: harness present but empty")

        # No host model-id literal anywhere in the file (finding #24 de-literalization gate).
        raw = json.dumps(data)
        if MODEL_ID_LITERAL.search(raw):
            hits.append(f"{rel}: contains a literal model id (gpt-5*); assert the tier binding instead")

        evals = data.get("evals")
        if not isinstance(evals, list) or not evals:
            hits.append(f"{rel}: evals must be a non-empty list")
            continue

        ids = [e.get("id") for e in evals]
        if any(not isinstance(i, int) for i in ids):
            hits.append(f"{rel}: every scenario needs an integer id")
        else:
            if len(set(ids)) != len(ids):
                hits.append(f"{rel}: duplicate scenario ids {sorted(ids)}")
            if sorted(ids) != list(range(1, len(ids) + 1)):
                hits.append(f"{rel}: ids not contiguous from 1: {sorted(ids)}")

        for e in evals:
            sid = e.get("id")
            where = f"{rel}#{sid}"
            if not _is_nonempty_str(e.get("prompt")):
                hits.append(f"{where}: missing non-empty prompt")
            exps = e.get("expectations")
            if not isinstance(exps, list) or not exps or not all(_is_nonempty_str(x) for x in exps):
                hits.append(f"{where}: expectations must be a non-empty list of non-empty strings")

            if e.get("discovery"):
                hits += _validate_discovery(where, name, e, known_skills)
            if e.get("stochastic"):
                hits += _validate_stochastic(where, e)

    return hits


def _validate_discovery(where, skill_name, e, known_skills):
    """Discovery scenario (AAS-TEST-05): plants the skill among siblings and asserts routing."""
    hits = []
    siblings = e.get("siblings")
    if not isinstance(siblings, list) or not siblings or not all(_is_nonempty_str(s) for s in siblings):
        hits.append(f"{where}: discovery scenario needs a non-empty siblings list")
        siblings = []
    if e.get("must_select") != skill_name:
        hits.append(f"{where}: discovery must_select must equal this skill ({skill_name!r}), "
                    f"got {e.get('must_select')!r}")
    mns = e.get("must_not_select")
    if not isinstance(mns, list) or not mns or not all(_is_nonempty_str(s) for s in mns):
        hits.append(f"{where}: discovery scenario needs a non-empty must_not_select list")
        mns = []
    if skill_name in (mns or []):
        hits.append(f"{where}: must_not_select cannot contain the selected skill")
    for s in list(siblings) + list(mns):
        if s not in known_skills:
            hits.append(f"{where}: references unknown skill {s!r} (not one of {sorted(known_skills)})")
    # Discovery is inherently behavioral -> must also be repped + controlled.
    if not e.get("stochastic"):
        hits.append(f"{where}: discovery scenario must be marked stochastic (routing is behavioral)")
    return hits


def _validate_stochastic(where, e):
    """Stochastic scenario (AAS-TEST-08/07): repped at N>=5 with a no-guidance control arm."""
    hits = []
    reps = e.get("reps")
    if not isinstance(reps, int) or reps < MIN_REPS:
        hits.append(f"{where}: stochastic scenario needs integer reps >= {MIN_REPS}, got {reps!r}")
    control = e.get("control")
    if not isinstance(control, dict):
        hits.append(f"{where}: stochastic scenario needs a no-guidance control arm (control object)")
        return hits
    for key in ("arm", "strip", "expectation"):
        if not _is_nonempty_str(control.get(key)):
            hits.append(f"{where}: control arm missing non-empty {key!r}")
    return hits


def discovery_scenarios(root="."):
    """Return [(skill_name, scenario)] for every discovery scenario across the suite."""
    out = []
    for name, (_rel, data) in load_evals(root).items():
        for e in data.get("evals", []):
            if e.get("discovery"):
                out.append((name, e))
    return out


def validate_coverage(root="."):
    """Suite-level completeness (AAS-TEST-05): every skill has a discovery scenario, and the
    discovery scenarios collectively disambiguate every overlap pair (a routing boundary is
    present in at least one direction)."""
    hits = []
    loaded = load_evals(root)
    disc = discovery_scenarios(root)
    with_disc = {name for name, _ in disc}
    for name in loaded:
        if name not in with_disc:
            hits.append(f"{name}: no discovery scenario (AAS-TEST-05 needs one per skill)")
    # A routing boundary = an unordered {selected, not-selected} pair asserted by some scenario.
    boundaries = set()
    for name, e in disc:
        for other in e.get("must_not_select", []):
            boundaries.add(frozenset((name, other)))
    for pair in OVERLAP_PAIRS:
        if frozenset(pair) not in boundaries:
            hits.append(f"overlap pair {pair[0]} <-> {pair[1]} not disambiguated by any discovery scenario")
    return hits


# ---------------------------------------------------------------------------
# Rep aggregation — pass-rate + variance (the driver feeds observed pass/fail here)
# ---------------------------------------------------------------------------
def aggregate_reps(results, min_reps=MIN_REPS):
    """Aggregate a list of per-rep outcomes (bools / 0-1) into pass-rate + variance.

    Population variance of the 0/1 outcomes (== p*(1-p) for Bernoulli). This is the math the
    off-CI live harness records per stochastic scenario; unit-tested here so the capability is
    real, not asserted. Raises ValueError on an empty list."""
    xs = [1 if bool(r) else 0 for r in results]
    n = len(xs)
    if n == 0:
        raise ValueError("aggregate_reps needs at least one rep")
    passes = sum(xs)
    rate = passes / n
    variance = sum((x - rate) ** 2 for x in xs) / n
    return {
        "n": n,
        "passes": passes,
        "pass_rate": rate,
        "variance": variance,
        "stdev": math.sqrt(variance),
        "meets_min_reps": n >= min_reps,
    }


def control_delta(guided_results, control_results):
    """Compare the guided arm against the no-guidance control (AAS-TEST-07).

    A green result only proves the guidance does the work if the guided pass-rate clears the
    control's. Returns both rates, the delta, and whether the guidance beat the base model."""
    guided = aggregate_reps(guided_results)
    control = aggregate_reps(control_results)
    delta = guided["pass_rate"] - control["pass_rate"]
    return {
        "guided_rate": guided["pass_rate"],
        "control_rate": control["pass_rate"],
        "delta": delta,
        "guided_beats_control": delta > 0,
        "guided": guided,
        "control": control,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Validate the skill eval scenarios.")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    try:
        hits = validate_evals(args.root) + validate_coverage(args.root)
    except ValueError as e:
        print(f"Eval harness FAILED — {e}")
        return 1
    if hits:
        print("Eval harness FAILED — eval scenarios incoherent:")
        for h in hits:
            print(f"- {h}")
        return 1
    print("Eval harness: eval scenarios coherent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
