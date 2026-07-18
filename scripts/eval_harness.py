#!/usr/bin/env python3
"""Eval-harness support: validate the skill eval scenarios and provide the pieces the
LIVE (Claude-driven) harness needs — a rep aggregator (pass-rate + variance) and a no-guidance
control-delta.

Context. The skill evals are a LIVE HARNESS: each `skills/<skill>/evals/evals.json` carries a
prose `harness` (how to set up the fake-agent-data shim + drive the skill) and per-scenario
`expectations` graded by the driver. There is no pytest that "runs" a skill — the behavioral
N>=5 reps happen off-CI against the shim. What CI CAN gate is the SCENARIOS' structural
coherence and the deterministic math the driver feeds its observed pass/fail into. That is this
module: `validate_evals` is the structural gate — it also rejects the pinned pack-authored `gpt-5*`
literal regression family. Legacy version-1 selectors may resolve through host tier roles; version-2
eval/runtime setup injects an exact host-resolved ID. Eval prose and fixtures must not hard-code that
runtime value. `aggregate_reps` /
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
MODEL_ID_LITERAL = re.compile(r"gpt-5", re.I)  # AAS-TEST-04 / finding #24: pinned literal regression.


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

        # Reject the pinned pack-authored gpt-5* literal family (finding #24 regression gate).
        raw = json.dumps(data)
        if MODEL_ID_LITERAL.search(raw):
            hits.append(
                f"{rel}: contains the forbidden pack-authored gpt-5* literal family; "
                "legacy v1 may name selectors, while v2 must inject an exact host-resolved id at runtime"
            )

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
# Opt-in developer modes (T6.1): artifact assertions + result aggregation over LOCAL,
# UNTRACKED evidence.
#
# The off-CI live canary harness records two evidence files under docs-private/ (gitignored,
# never shipped): current-artifacts.json (a workspace + assertions about the artifacts a real
# scheduled-path fire produced) and current-results.json (per-scenario guided vs control reps).
# These modes are invoked only with an explicit path, so the free, deterministic --root CI run
# never requires either file. Both schema-validate their input (a malformed file is never
# "clean") and reuse the same deterministic math as the live rep aggregation above.
# ---------------------------------------------------------------------------
ARTIFACT_KINDS = {
    "file_exists": (),
    "json_field_equals": ("field", "equals"),
    "jsonl_event_sequence": ("sequence",),
    "text_absent": ("pattern",),
    "text_matches": ("pattern",),
}

# T7.2 belief-4 separation, made checkable. An optional `surface` on any assertion declares
# whether the artifact is shown to the user or is an internal record, and the harness enforces
# the matching direction: a user-facing surface (chat/digest/home/notification) must carry NO
# raw canonical error code; an internal record MUST retain one. This is additive — an assertion
# without `surface` behaves exactly as before, so --root and the T6.1 kinds are untouched.
SURFACES = ("user_facing", "internal_record")
# A canonical E-* code: E- then an uppercase-alnum segment, optionally more hyphen-joined
# segments (E-QUOTA, E-NO-AUTH, E-UPSTREAM-STRETCH, E-SCHEDULE-CANARY). Bounded lowercase
# internal classes are asserted by field, not by this token.
RAW_ERROR_CODE = re.compile(r"\bE-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\b")


def _read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _dig(data, dotted):
    """Traverse a dotted field path (e.g. 'lifecycle.close_state'); return (found, value)."""
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def _is_subsequence(expected, actual):
    idx = 0
    for value in actual:
        if idx < len(expected) and value == expected[idx]:
            idx += 1
    return idx == len(expected)


def _validate_artifacts_schema(evidence):
    if not isinstance(evidence, dict):
        raise ValueError("artifacts evidence must be a JSON object")
    workspace = evidence.get("workspace")
    if not _is_nonempty_str(workspace):
        raise ValueError("artifacts evidence needs a non-empty 'workspace'")
    assertions = evidence.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        raise ValueError("artifacts evidence needs a non-empty 'assertions' list")
    for i, a in enumerate(assertions):
        where = f"assertion[{i}]"
        if not isinstance(a, dict):
            raise ValueError(f"{where} must be an object")
        kind = a.get("kind")
        if kind not in ARTIFACT_KINDS:
            raise ValueError(
                f"{where}: unknown kind {kind!r} (want one of {sorted(ARTIFACT_KINDS)})"
            )
        if not _is_nonempty_str(a.get("path")):
            raise ValueError(f"{where}: needs a non-empty 'path'")
        for key in ARTIFACT_KINDS[kind]:
            if key not in a:
                raise ValueError(f"{where} ({kind}): missing required {key!r}")
        if kind in ("text_absent", "text_matches") and not _is_nonempty_str(a.get("pattern")):
            raise ValueError(f"{where} ({kind}): 'pattern' must be a non-empty string")
        if kind == "json_field_equals" and not _is_nonempty_str(a.get("field")):
            raise ValueError(f"{where} (json_field_equals): 'field' must be a non-empty string")
        if kind == "jsonl_event_sequence":
            seq = a.get("sequence")
            if not isinstance(seq, list) or not seq:
                raise ValueError(
                    f"{where} (jsonl_event_sequence): 'sequence' must be a non-empty list"
                )
        surface = a.get("surface")
        if surface is not None and surface not in SURFACES:
            raise ValueError(
                f"{where}: unknown surface {surface!r} (want one of {list(SURFACES)})"
            )
    return workspace, assertions


def check_artifacts(evidence):
    """Evaluate an artifact-evidence object (a workspace plus assertions) and return a list of
    failure hits (empty == clean). Schema-validates first (raising ValueError on a malformed
    object). Assertion kinds: file_exists, json_field_equals (dotted field), jsonl_event_sequence
    (an ordered subsequence of a per-line field, default 'event'), text_absent, text_matches.

    An assertion may also carry a `surface` (T7.2): `user_facing` fails if the file contains a raw
    canonical E-* code (chat/digest/home/notification must render cause+fix, never the code);
    `internal_record` fails if the file contains none (the record must retain its classification).
    """
    workspace, assertions = _validate_artifacts_schema(evidence)
    hits = []
    for a in assertions:
        kind, rel = a["kind"], a["path"]
        full = os.path.join(workspace, rel)
        if kind == "file_exists":
            if not os.path.isfile(full):
                hits.append(f"file_exists: {rel} does not exist")
            continue
        if not os.path.isfile(full):
            hits.append(f"{kind}: {rel} does not exist")
            continue
        if kind == "json_field_equals":
            try:
                data = json.loads(_read_text(full))
            except ValueError:
                hits.append(f"json_field_equals: {rel} is not valid JSON")
                continue
            found, value = _dig(data, a["field"])
            if not found:
                hits.append(f"json_field_equals: {rel} has no field {a['field']!r}")
            elif value != a["equals"]:
                hits.append(
                    f"json_field_equals: {rel} {a['field']} = {value!r}, "
                    f"expected {a['equals']!r}"
                )
        elif kind == "jsonl_event_sequence":
            field = a.get("field", "event")
            values, malformed = [], False
            for line in _read_text(full).splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    hits.append(f"jsonl_event_sequence: {rel} has a malformed JSON line")
                    malformed = True
                    break
                if isinstance(row, dict) and field in row:
                    values.append(row[field])
            if not malformed and not _is_subsequence(a["sequence"], values):
                hits.append(
                    f"jsonl_event_sequence: {rel} {field} values {values} "
                    f"do not contain {a['sequence']} in order"
                )
        elif kind == "text_absent":
            if re.search(a["pattern"], _read_text(full)):
                hits.append(f"text_absent: {rel} matches forbidden /{a['pattern']}/")
        elif kind == "text_matches":
            if not re.search(a["pattern"], _read_text(full)):
                hits.append(f"text_matches: {rel} does not match /{a['pattern']}/")
    hits += _surface_hits(workspace, assertions)
    return hits


def _surface_hits(workspace, assertions):
    """Enforce the belief-4 separation for any assertion that declares a `surface`. A missing
    file is left to the assertion's own kind to flag, so this never double-reports existence."""
    hits = []
    for a in assertions:
        surface = a.get("surface")
        if not surface:
            continue
        rel = a["path"]
        full = os.path.join(workspace, rel)
        if not os.path.isfile(full):
            continue
        match = RAW_ERROR_CODE.search(_read_text(full))
        if surface == "user_facing" and match:
            hits.append(
                f"user_facing: {rel} exposes raw error code {match.group(0)!r} "
                "(user-facing surfaces render cause+fix, never the code)"
            )
        elif surface == "internal_record" and not match:
            hits.append(
                f"internal_record: {rel} retains no canonical E-* classification code "
                "(the internal record must keep the code)"
            )
    return hits


def _validate_results_schema(evidence):
    if not isinstance(evidence, dict):
        raise ValueError("results evidence must be a JSON object")
    scenarios = evidence.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("results evidence needs a non-empty 'scenarios' list")
    for i, row in enumerate(scenarios):
        where = f"scenario[{i}]"
        if not isinstance(row, dict):
            raise ValueError(f"{where} must be an object")
        for key in ("skill", "exact_model"):
            if not _is_nonempty_str(row.get(key)):
                raise ValueError(f"{where}: '{key}' must be a non-empty string")
        sid = row.get("scenario_id")
        if not (_is_nonempty_str(sid) or (isinstance(sid, int) and not isinstance(sid, bool))):
            raise ValueError(f"{where}: 'scenario_id' must be a non-empty string or int")
        for arm in ("guided", "control"):
            xs = row.get(arm)
            if not isinstance(xs, list) or not xs or not all(
                isinstance(x, bool) or x in (0, 1) for x in xs
            ):
                raise ValueError(f"{where}: '{arm}' must be a non-empty list of booleans")
        delta = row.get("required_control_delta")
        if isinstance(delta, bool) or not isinstance(delta, (int, float)):
            raise ValueError(f"{where}: 'required_control_delta' must be a number")
    return scenarios


def aggregate_results(evidence):
    """Aggregate scenario result rows (guided vs no-guidance control reps) into pass-rate,
    variance, and control-delta, and check each row clears its required_control_delta with an
    adequately powered guided arm (N>=MIN_REPS). Returns {ok, scenarios:[...]}. Raises
    ValueError on a malformed object."""
    scenarios = _validate_results_schema(evidence)
    rows, overall_ok = [], True
    for row in scenarios:
        delta = control_delta(row["guided"], row["control"])
        meets_delta = delta["delta"] >= row["required_control_delta"]
        meets_reps = delta["guided"]["meets_min_reps"]
        ok = bool(meets_delta and meets_reps)
        overall_ok = overall_ok and ok
        rows.append({
            "skill": row["skill"],
            "scenario_id": row["scenario_id"],
            "exact_model": row["exact_model"],
            "guided_rate": delta["guided_rate"],
            "control_rate": delta["control_rate"],
            "delta": delta["delta"],
            "required_control_delta": row["required_control_delta"],
            "variance": delta["guided"]["variance"],
            "meets_required_delta": meets_delta,
            "meets_min_reps": meets_reps,
            "guided_beats_control": delta["guided_beats_control"],
            "ok": ok,
        })
    return {"ok": overall_ok, "scenarios": rows}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _run_check_artifacts(path):
    try:
        hits = check_artifacts(json.loads(_read_text(path)))
    except (OSError, ValueError) as e:
        print(f"Artifact check FAILED — {e}")
        return 1
    if hits:
        print(f"Artifact check FAILED — {len(hits)} assertion(s) failed:")
        for h in hits:
            print(f"- {h}")
        return 1
    print("Artifact check: all assertions passed.")
    return 0


def _run_aggregate_results(path):
    try:
        report = aggregate_results(json.loads(_read_text(path)))
    except (OSError, ValueError) as e:
        print(f"Results aggregation FAILED — {e}")
        return 1
    for row in report["scenarios"]:
        status = "ok" if row["ok"] else "FAIL"
        print(
            f"[{status}] {row['skill']}#{row['scenario_id']} "
            f"guided={row['guided_rate']:.2f} control={row['control_rate']:.2f} "
            f"delta={row['delta']:+.2f} (need >={row['required_control_delta']:.2f})"
        )
    if not report["ok"]:
        print("Results aggregation FAILED — a scenario did not clear its required control delta.")
        return 1
    print("Results aggregation: every scenario cleared its required control delta.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Validate the skill eval scenarios.")
    ap.add_argument("--root", default=".")
    ap.add_argument(
        "--check-artifacts", metavar="EVIDENCE_JSON",
        help="opt-in: evaluate a local, untracked artifact-evidence file (workspace + assertions)",
    )
    ap.add_argument(
        "--aggregate-results", metavar="EVIDENCE_JSON",
        help="opt-in: aggregate a local, untracked scenario-results file (guided vs control reps)",
    )
    args = ap.parse_args()

    if args.check_artifacts:
        return _run_check_artifacts(args.check_artifacts)
    if args.aggregate_results:
        return _run_aggregate_results(args.aggregate_results)

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
