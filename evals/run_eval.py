#!/usr/bin/env python3
"""Run one behavior-eval case against the live plugin.

Usage: python3 evals/run_eval.py --case <name> --model {sonnet|haiku}

Loads evals/cases/<name>.yaml, moves any real ~/.job-search aside, optionally seeds a
workspace from evals/seeds/<name>/, spawns `claude -p` with stream-json output, stamps
every output line with elapsed wall-clock seconds, then captures the produced workspace
into evals/results/<ts>-<name>-<model>/ and restores the stash. Runner pattern proven in
the 2026-07-30 census evals: Popen + readline loop + timeout kill.
"""
import argparse, json, os, re, shutil, subprocess, sys, threading, time

import yaml

EVALS_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.join(os.path.expanduser("~"), ".job-search")
LISTING = "f9a6ec16-0bfd-44d8-b3ee-073776745ee7"  # Job Postings API listing id
ALLOWED = "Bash,Read,Write,Edit,Glob,Grep,Skill,AskUserQuestion,TodoWrite"


def fetch_live_posting():
    """Fetch one live posting (one search-jobs + one get-posting call) for fit.yaml."""
    search = subprocess.run(
        ["agent-data", "call", LISTING, "search-jobs", "--keywords",
         "machine learning engineer", "--source", "ashby", "--limit", "3"],
        capture_output=True, text=True, timeout=120)
    row = json.loads(search.stdout)["data"]["results"][0]
    detail = subprocess.run(
        ["agent-data", "call", LISTING, "get-posting",
         "--posting_id", row["id"], "--source_url", row["source_url"]],
        capture_output=True, text=True, timeout=120)
    return detail.stdout[:6000]


def scan_for_kill(line, regex, pending):
    """Track tool_use blocks whose name+input match regex; True when one's result arrives."""
    try:
        event = json.loads(line)
    except ValueError:
        return False
    for block in (event.get("message") or {}).get("content") or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use":
            if re.search(regex, block.get("name", "") + " " + json.dumps(block.get("input", {}))):
                pending.add(block.get("id"))
        elif block.get("type") == "tool_result" and block.get("tool_use_id") in pending:
            return True
    return False


def run_session(prompt, model, cwd, transcript, timeout_s, kill_regex=None):
    """One `claude -p` session; returns {"rc", "wall_s", "timeout_killed", "event_killed"}."""
    cmd = ["claude", "-p", prompt, "--model", model, "--allowedTools", ALLOWED,
           "--permission-mode", "acceptEdits", "--verbose", "--output-format", "stream-json"]
    proc = subprocess.Popen(cmd, cwd=cwd, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    t0, state, pending = time.time(), {"timeout": False, "event": False}, set()

    def backstop():  # kills a child that hangs producing no output past the timeout
        state["timeout"] = True
        proc.kill()

    watchdog = threading.Timer(timeout_s + 60, backstop)
    watchdog.daemon = True
    watchdog.start()
    with open(transcript, "a") as f:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                f.write(json.dumps({"t": round(time.time() - t0, 2),
                                    "line": line.rstrip()[:20000]}) + "\n")
                if kill_regex and not state["event"] and scan_for_kill(line, kill_regex, pending):
                    state["event"] = True
                    proc.kill()
            if time.time() - t0 > timeout_s and not (state["timeout"] or state["event"]):
                state["timeout"] = True
                proc.kill()
    watchdog.cancel()
    try:
        rc = proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        rc = -99
    return {"rc": rc, "wall_s": round(time.time() - t0, 1),
            "timeout_killed": state["timeout"], "event_killed": state["event"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case", required=True, help="case name under evals/cases/")
    ap.add_argument("--model", required=True, choices=["sonnet", "haiku"])
    ap.add_argument("--kill-after-event", metavar="REGEX",
                    help="terminate the child after the first tool call whose name+input "
                         "matches REGEX completes (overrides the case file's kill_after_event)")
    args = ap.parse_args()
    with open(os.path.join(EVALS_DIR, "cases", args.case + ".yaml")) as f:
        case = yaml.safe_load(f)
    if args.model not in case["models"]:
        sys.exit("case %s does not list model %s" % (args.case, args.model))
    kill_regex = args.kill_after_event or case.get("kill_after_event")

    prompt = case["prompt"]
    if "{live_posting}" in prompt:
        prompt = prompt.replace("{live_posting}", fetch_live_posting())

    ts = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    run_dir = os.path.join(EVALS_DIR, "results", "%s-%s-%s" % (ts, args.case, args.model))
    project = os.path.join(run_dir, "project")  # the child's cwd, kept out of the repo root
    os.makedirs(project)
    transcript = os.path.join(run_dir, "transcript.jsonl")

    stash = None
    if os.path.exists(WORKSPACE):
        stash = WORKSPACE + ".stash-" + ts
        shutil.move(WORKSPACE, stash)
    sessions = []
    try:
        if case["workspace"] == "seeded":
            seed = os.path.join(EVALS_DIR, "seeds", args.case)
            if not os.path.isdir(seed):
                sys.exit("case %s declares workspace: seeded but %s is missing" % (args.case, seed))
            shutil.copytree(seed, WORKSPACE)
        runs = [(prompt, kill_regex)]
        if case.get("followup_prompt"):
            runs.append((case["followup_prompt"], None))
        for i, (p, kr) in enumerate(runs):
            if i:
                with open(transcript, "a") as f:
                    f.write(json.dumps({"t": None, "runner": "followup-session-start"}) + "\n")
            sessions.append(run_session(p, args.model, project, transcript, case["timeout_s"], kr))
    finally:
        captured = os.path.exists(WORKSPACE)
        if captured:
            shutil.move(WORKSPACE, os.path.join(run_dir, "workspace"))
        if stash:
            shutil.move(stash, WORKSPACE)

    ok = bool(sessions) and all(
        s["rc"] == 0 or s["event_killed"] for s in sessions) and not any(
        s["timeout_killed"] for s in sessions)
    with open(os.path.join(run_dir, "result.json"), "w") as f:
        json.dump({"case": args.case, "model": args.model, "started_utc": ts,
                   "behaviors": case["behaviors"], "kill_regex": kill_regex,
                   "sessions": sessions, "workspace_captured": captured, "ok": ok},
                  f, indent=1)
    print("%s: %s (results in %s)" % (args.case, "ok" if ok else "FAILED", run_dir))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
