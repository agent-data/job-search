#!/usr/bin/env python3
"""Run the routing case: which skill does each trigger phrase actually load?

Usage: python3 evals/run_triggering.py --model {sonnet|haiku} [--reps N] [--label TEXT]
                                       [--phrases id,id,...]

`evals/cases/triggering.yaml` holds many prompts, one per phrase, so it needs its own driver:
`run_eval.py` runs one prompt per case and grades a whole session, and nothing about its
behavior should change to fit a routing probe. Everything else is the same discipline —
the same stash guard, the same `run_session` with its process-group kill, the same
stream-json transcript.

One session per (phrase, rep). Each is killed the moment its first Skill call returns, which
is after the routing decision and before the skill can start working, so a probe costs no API
calls. Reps are run phrase-major inside each rep so that any drift in service conditions
lands on every phrase alike.

Writes `routing.json` with the selected skill per session and the per-phrase rate.
"""
import argparse, glob, json, os, shutil, sys, time

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_eval import EVALS_DIR, WORKSPACE, run_session  # noqa: E402


def first_skill(transcript):
    """The first Skill call in a session, and every skill it called, in order."""
    called = []
    with open(transcript) as f:
        for ln in f:
            try:
                ev = json.loads(json.loads(ln).get("line") or "null")
            except (ValueError, AttributeError):
                continue
            if not isinstance(ev, dict):
                continue
            for b in (ev.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Skill":
                    called.append((b.get("input") or {}).get("skill"))
    return (called[0] if called else None), called


def loaded_skills(transcript, prefix="job-search:"):
    with open(transcript) as f:
        for ln in f:
            try:
                ev = json.loads(json.loads(ln).get("line") or "null")
            except (ValueError, AttributeError):
                continue
            if isinstance(ev, dict) and ev.get("subtype") == "init":
                return sorted(s for s in (ev.get("skills") or []) if s.startswith(prefix))
    return []


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, choices=["sonnet", "haiku"])
    ap.add_argument("--reps", type=int)
    ap.add_argument("--label", default="", help="tag for the results directory, e.g. pre / post")
    ap.add_argument("--phrases", help="comma-separated phrase ids; default all")
    args = ap.parse_args()

    leftovers = sorted(glob.glob(WORKSPACE + ".stash-*"))
    if leftovers:
        sys.exit("refusing to run: %s exists — restore or remove it first." % leftovers[0])
    with open(os.path.join(EVALS_DIR, "cases", "triggering.yaml")) as f:
        case = yaml.safe_load(f)
    if args.model not in case["models"]:
        sys.exit("triggering does not list model %s" % args.model)
    reps = args.reps or case["reps"]
    phrases = case["phrases"]
    if args.phrases:
        wanted = args.phrases.split(",")
        phrases = [p for p in phrases if p["id"] in wanted]

    ts = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    tag = "-".join(x for x in ("triggering", args.model, args.label) if x)
    run_dir = os.path.join(EVALS_DIR, "results", "%s-%s" % (ts, tag))
    os.makedirs(run_dir)

    stash = None
    if os.path.exists(WORKSPACE):
        stash = WORKSPACE + ".stash-" + ts
        shutil.move(WORKSPACE, stash)
    sessions = []
    try:
        for rep in range(1, reps + 1):
            for ph in phrases:
                sid = "%s-r%d" % (ph["id"], rep)
                project = os.path.join(run_dir, sid, "project")
                os.makedirs(project)
                transcript = os.path.join(run_dir, sid, "transcript.jsonl")
                if os.path.exists(WORKSPACE):
                    shutil.rmtree(WORKSPACE)  # every phrase starts from a fresh workspace
                res = run_session(ph["prompt"], args.model, project, transcript,
                                  case["timeout_s"], case["kill_after_event"])
                sel, called = first_skill(transcript)
                sessions.append({"phrase": ph["id"], "rep": rep, "prompt": ph["prompt"],
                                 "expect": ph.get("expect"), "selected": sel,
                                 "all_skill_calls": called, "wall_s": res["wall_s"],
                                 "killed_on_skill": res["event_killed"],
                                 "timeout_killed": res["timeout_killed"]})
                print("  %-14s rep %d  %-6s -> %-34s (%.0fs)"
                      % (ph["id"], rep, args.model, sel or "NO SKILL", res["wall_s"]))
                if os.path.exists(WORKSPACE):
                    shutil.rmtree(WORKSPACE)
    finally:
        if os.path.exists(WORKSPACE):
            shutil.rmtree(WORKSPACE)
        if stash:
            shutil.move(stash, WORKSPACE)

    rates = {}
    for ph in phrases:
        mine = [s for s in sessions if s["phrase"] == ph["id"]]
        hit = sum(1 for s in mine if s["selected"] == ph.get("expect"))
        leak = sum(1 for s in mine if s["selected"] in (ph.get("must_not_select") or []))
        rates[ph["id"]] = {"expect": ph.get("expect"), "hit": hit, "of": len(mine),
                           "leak_to_must_not_select": leak,
                           "selected_counts": {k: sum(1 for s in mine if s["selected"] == k)
                                               for k in sorted(
                                                   {str(s["selected"]) if s["selected"] is None
                                                    else s["selected"] for s in mine})}}
    any_t = glob.glob(os.path.join(run_dir, "*", "transcript.jsonl"))
    out = {"case": "triggering", "model": args.model, "label": args.label, "started_utc": ts,
           "reps": reps, "job_search_skills_loaded": loaded_skills(any_t[0]) if any_t else [],
           "rates": rates, "sessions": sessions}
    with open(os.path.join(run_dir, "routing.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("\ntriggering %s %s: %s" % (args.model, args.label or "-", json.dumps(
        {k: "%d/%d" % (v["hit"], v["of"]) for k, v in rates.items()})))
    print("results in %s" % run_dir)


if __name__ == "__main__":
    main()
