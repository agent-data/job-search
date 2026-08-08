#!/usr/bin/env python3
"""Run one behavior-eval case against the live plugin.

Usage: python3 evals/run_eval.py --case <name> --model {sonnet|haiku}

Loads evals/cases/<name>.yaml, moves any real ~/.job-search aside, optionally seeds a
workspace from evals/seeds/<name>/, spawns `claude -p` with stream-json output, stamps
every output line with elapsed wall-clock seconds, then captures the produced workspace
into evals/results/<ts>-<name>-<model>/ and restores the stash. Runner pattern proven in
the 2026-07-30 census evals: Popen + readline loop + timeout kill.

A case that exercises the recurring job installs a real scheduler entry, and that entry outlives
the session, so the run also lists the machine's scheduler entries before and after and names every
one that survived. A case that declares `expects_scheduler_entry` is allowed one entry per class it
declares; every other case, and anything beyond what was declared, reports FAILED. The scheduler
comment below has the detail.
"""
import argparse, collections, glob, json, os, re, shutil, signal, subprocess, sys
import threading, time, traceback

EVALS_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.join(os.path.expanduser("~"), ".job-search")
LISTING = "f9a6ec16-0bfd-44d8-b3ee-073776745ee7"  # Job Postings API listing id
ALLOWED = "Bash,Read,Write,Edit,Glob,Grep,Skill,Task,AskUserQuestion,TodoWrite"

# --- Scheduler entries the session leaves behind ---------------------------------------------
#
# On 2026-08-07 the `schedule` case installed a real launchd job. `kill_group` below SIGKILLs the
# child's process group, and launchd starts its job outside that group, so the SIGKILL never
# reached it: the job survived the session, fired after main's `finally` had already moved the
# owner's real ~/.job-search back, and wrote events and a scratch directory into it. The run was
# reported ok, because ok was computed from session return codes and nothing else.
#
# The fix is to list the machine's scheduler entries before the session and again after it, and to
# fail the run when an entry that was not there before is there now. The other candidate — giving
# the eval its own scheduler namespace to install into and remove afterwards — was not taken: the
# agent installs the recurring job through whatever its host offers, and nothing in this harness
# constrains that choice, so a namespace finds the job only when the agent happens to adopt it. A
# listing of what the machine already had finds a new entry however the agent installed it.
#
# The harness reports and fails; it never removes an entry. `launchctl list` and the user crontab
# both hold entries this harness did not create, this machine's own among them, and a removal
# driven by a before/after difference would delete those too.
#
# A case whose behavior under test is the recurring job passes only by leaving the job installed:
# the product keeps it when the canary succeeds. A status that is red on every correct run carries no
# information, and training the operator to ignore it is how the 2026-08-07 entry survived in the
# first place. So a case file may declare `expects_scheduler_entry`, naming the classes it expects
# to leave one entry in. One entry in a declared class is named and reported like any other and does
# not fail the run; a second entry in that class, or any entry in a class the case did not declare,
# still does, and so do entries in launchd and cron at the same time — SCHEDULER_MECHANISMS below
# says why. A case that declares nothing fails on any new entry at all.
#
# Each probe reads an environment variable before falling back to this machine's scheduler, so
# tests/test_eval_harness.py points all three at a directory and two scripts it wrote itself and
# never installs, loads or removes anything.
#
# Both launchd classes fail on a new entry, because neither sees what the other sees. A loaded job
# does not have to leave a plist in ~/Library/LaunchAgents: `launchctl bootstrap` takes paths to
# plists anywhere on disk, and the 18-line entry that says so prints with
#   man launchctl | col -b | sed -n '/bootstrap | bootout domain-target/,/enable | disable/p'
# So a job bootstrapped from a plist written into the eval's own project directory runs and is
# listed while that directory stays empty. Measured on this macOS host, read-only, from a bash shell
# (the third and fourth need process substitution):
#   launchctl list | awk 'NR>1{print $NF}' | sort -u | wc -l                -> 492 loaded labels
#   ls -1 ~/Library/LaunchAgents | sed 's/\.plist$//' | sort -u | wc -l     ->   8 plists there
#   comm -12 <(launchctl list | awk 'NR>1{print $NF}' | sort -u) \
#            <(ls -1 ~/Library/LaunchAgents | sed 's/\.plist$//' | sort -u) | wc -l
#                                                                          ->   6 in both
#   comm -23 <(launchctl list | awk 'NR>1{print $NF}' | sort -u) \
#            <(ls -1 ~/Library/LaunchAgents /Library/LaunchAgents /Library/LaunchDaemons \
#                    /System/Library/LaunchAgents /System/Library/LaunchDaemons 2>/dev/null \
#              | sed 's/\.plist$//' | sort -u) | wc -l                      ->  94 loaded, no plist
#                                                                                anywhere standard
# So 486 loaded jobs have no plist in ~/Library/LaunchAgents, 2 plists in it are not loaded, and 94
# loaded jobs have no plist in any of the five standard directories. Neither class contains the
# other, so dropping either would leave an install unwatched.
#
# The remaining worry was churn: this machine starts jobs of its own, and a label that appeared for
# an unrelated reason would fail an eval that installed nothing. Sampled every 20 seconds across
# 1583 seconds — longer than the 1500-second timeout_s in evals/cases/schedule.yaml — while this
# repo's test suite ran several times on the same machine:
#   for i in $(seq 1 80); do launchctl list | awk 'NR>1{print $NF}' | sort -u; \
#       ls -1 ~/Library/LaunchAgents; sleep 20; done | sort | uniq -c | awk '$1 != 80'
# printed nothing, so every entry was present in all 80 samples: the same 492 labels and the same 8
# plists throughout, nothing appearing and nothing going away in 26 minutes. Nil churn over a
# session-length window, so nothing here is filtered and all three classes fail on a new entry.
# Rerun that loop if a run ever fails naming an entry nobody installed.
SCHEDULER_CLASSES = ("launchd-plists", "launchd-loaded", "cron")
# One recurring job is installed through one mechanism, and a launchd install shows up in both
# launchd classes at once — a plist file and a loaded label for the same job. So the allowance a
# case declares is one entry per class, plus this: the classes holding new entries must all belong
# to one mechanism. Entries in launchd and in cron together are two jobs, whatever the case
# declared.
#
# What the per-class allowance does NOT check is that a new plist and a new label are the same job.
# A plist for one job and a loaded label for another pass as one launchd install. Checking it would
# mean matching the plist's filename against the label, and a plist's filename does not have to
# match the Label inside it, so that check would fail correct runs. Both entries are printed by
# name, which is where an operator sees two names that do not go together.
SCHEDULER_MECHANISMS = {"launchd-plists": "launchd", "launchd-loaded": "launchd", "cron": "cron"}
LAUNCH_AGENTS_ENV = "JOBSEARCH_EVAL_LAUNCH_AGENTS_DIR"
LAUNCHCTL_ENV = "JOBSEARCH_EVAL_LAUNCHCTL"
CRONTAB_ENV = "JOBSEARCH_EVAL_CRONTAB"
# The recurring-job step tells the agent to install through whatever its host offers:
#   /usr/bin/grep -n "cron, launchd, or the host" skills/job-search/SKILL.md
# The third of those, the host's own recurring-job command, is not launchd and not cron, so none of
# the probes above would list what it installs. Every run says so rather than leaving a reader to
# assume the check covered it.
NOT_PROBED = "recurring jobs installed by the host's own command, which are neither launchd nor cron"
# A probe that never returns would hang the teardown, so each command gets a deadline. Named here so
# a test can shorten it rather than wait a minute.
PROBE_TIMEOUT_S = 60


def _command_lines(argv, empty_marker=None):
    """Run `argv` and return (lines, absent_reason, failure_reason); exactly one of the three is set.

    A command that is not on this machine means the class of scheduler it lists is not on this
    machine either: launchd runs only on macOS, and a machine with no `crontab` command has no user
    crontab. `crontab -l` exits 1 and prints `no crontab for <user>` on stderr when the user has
    none, which is an empty listing rather than a failed probe; `empty_marker` is the text that says
    so. On an account with no crontab, `crontab -l; echo "rc=$?"` prints that line and `rc=1`.
    """
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=PROBE_TIMEOUT_S)
    except FileNotFoundError:
        return None, "%s is not on this machine" % argv[0], None
    except (OSError, subprocess.TimeoutExpired) as err:
        return None, None, "%s did not finish: %s" % (" ".join(argv), err)
    if proc.returncode != 0:
        if empty_marker and empty_marker in (proc.stderr or ""):
            return [], None, None
        return None, None, "%s exited %d: %s" % (
            " ".join(argv), proc.returncode, (proc.stderr or proc.stdout or "").strip()[:200])
    return proc.stdout.splitlines(), None, None


def _launchctl_labels(lines):
    """The job label from each row of `launchctl list`: its last whitespace-separated field. The
    first row is the `PID Status Label` header, which names no job."""
    labels = []
    for line in lines:
        fields = line.split()
        if not fields or fields == ["PID", "Status", "Label"]:
            continue
        labels.append(fields[-1])
    return labels


def _crontab_entries(lines):
    """Each scheduling line of a user crontab, kept whole: the line is what a cron job is. Blank
    lines and comments schedule nothing."""
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def snapshot_schedulers(env=None):
    """List the scheduler entries on this machine, one class at a time.

    Returns {"entries": {class: [entry, ...]}, "absent": {class: why}, "failed": {class: why}}.
    A class is in `entries` when its probe produced a listing, and an empty list there means the
    class holds nothing; in `absent` when the class cannot hold an entry on this machine; and in
    `failed` when its probe was there and produced no listing — the case where this harness cannot
    say whether a job survived the session.
    """
    env = os.environ if env is None else env
    snap = {"entries": {}, "absent": {}, "failed": {}}

    agents = env.get(LAUNCH_AGENTS_ENV) or os.path.join(
        os.path.expanduser("~"), "Library", "LaunchAgents")
    # os.path.isdir answers False both when nothing is there and when the path cannot be reached at
    # all, so it used to record an unreadable directory as absent — a class that could not be read,
    # passing as a class that holds nothing. os.stat separates the two: only FileNotFoundError means
    # the directory is not there. Measured on a directory whose parent is mode 000, and on a path
    # that is a file rather than a directory: both now land in `failed`.
    try:
        os.stat(agents)
    except FileNotFoundError:
        snap["absent"]["launchd-plists"] = "%s does not exist" % agents
    except OSError as err:
        snap["failed"]["launchd-plists"] = "cannot reach %s: %s" % (agents, err)
    else:
        try:
            snap["entries"]["launchd-plists"] = sorted(os.listdir(agents))
        except OSError as err:  # a file rather than a directory, or a directory that cannot be read
            snap["failed"]["launchd-plists"] = "cannot list %s: %s" % (agents, err)

    for name, argv, parse, empty_marker in (
            ("launchd-loaded", [env.get(LAUNCHCTL_ENV) or "launchctl", "list"],
             _launchctl_labels, None),
            ("cron", [env.get(CRONTAB_ENV) or "crontab", "-l"], _crontab_entries, "no crontab")):
        lines, absent, failed = _command_lines(argv, empty_marker)
        if failed:
            snap["failed"][name] = failed
        elif absent:
            snap["absent"][name] = absent
        else:
            snap["entries"][name] = sorted(parse(lines))
    return snap


def declared_classes(case, case_name):
    """The scheduler classes a case declares it expects to leave one entry in, from the case file's
    `expects_scheduler_entry`. Returns (classes, error); error is None when the declaration is well
    formed, and a message to exit on when it is not.

    A case declares this when installing a recurring job is the behavior under test and the product
    is meant to keep it: `evals/cases/schedule.yaml` is the one that does. Everything else leaves
    the field out and fails on any surviving entry.
    """
    expected = case.get("expects_scheduler_entry")
    if expected is None:
        return [], None
    if not isinstance(expected, list) or not expected:
        return [], ("case %s: expects_scheduler_entry must be a non-empty list of scheduler "
                    "classes, one of %s" % (case_name, list(SCHEDULER_CLASSES)))
    unknown = [name for name in expected if name not in SCHEDULER_CLASSES]
    if unknown:
        return [], ("case %s: expects_scheduler_entry names %s, which this harness does not list. "
                    "The classes it lists are %s."
                    % (case_name, unknown, list(SCHEDULER_CLASSES)))
    return list(expected), None


def scheduler_report(verdict, listed):
    """The lines the operator reads: what appeared, whether the case declared it, and what to do."""
    lines = []
    declared = verdict["expected_classes"]
    if verdict["new"]:
        lines.append("scheduler check: these entries appeared while the session ran and are still "
                     "installed:")
        for name, entries in sorted(verdict["new"].items()):
            for entry in entries:
                mark = ""
                if declared:
                    mark = ("  [unexpected]" if entry in verdict["unexpected"].get(name, ())
                            else "  [expected]")
                lines.append("  %-15s %s%s" % (name, entry, mark))
        lines.append("Remove each one the way it was installed — a launchd job unloaded and its "
                     "plist file removed, a cron line deleted. Entries this machine installed for "
                     "its own reasons appear here too; leave those alone.")
        if declared:
            # States the declaration itself, which is true whatever the outcome. Saying that one
            # entry "does not fail the run" was true only on the paths where nothing failed, and on
            # the launchd-and-cron path it sat one line above "This run is FAILED".
            lines.append("The case declares one entry in %s%s" % (
                ", ".join(declared),
                "." if verdict["reasons"] else ", so nothing here fails the run."))
        if verdict["reasons"]:
            lines.append("This run is FAILED: %s. Remove what is named above and rerun."
                         % "; ".join(verdict["reasons"]))
    elif listed:
        lines.append("scheduler check: no new entry in %s." % ", ".join(listed))
    for name, why in sorted(verdict["probe_failed"].items()):
        lines.append("scheduler check: cannot list %s — %s. This run cannot say whether the session "
                     "left a recurring job installed." % (name, why))
    if not listed:
        lines.append("scheduler check: no scheduler class could be listed on this machine. Nothing "
                     "was checked, so this run cannot report the machine clean.")
    lines.append("scheduler check: not covered — %s." % NOT_PROBED)
    return lines


def scheduler_verdict(before, after, expected=()):
    """Compare two snapshots and say whether the machine came back the way the session found it.

    `expected` names the classes the case declares it expects to leave one entry in. One new entry
    in a declared class is expected: it is still listed and still named, and it does not fail the
    run. A second entry in that class, and any entry in a class the case did not declare, is
    unexpected and does fail — as do new entries in launchd and in cron at the same time, which are
    two recurring jobs rather than the one the case declared. A case that declares nothing fails on
    any new entry at all.

    Also not ok when a probe failed, or when no class could be listed: a run that checked nothing
    cannot report a clean machine. Entries are counted rather than set-compared, so a second copy of
    a cron line already in the crontab is a new entry too.
    """
    declared = list(expected)
    new = {}
    for name, entries in after["entries"].items():
        added = collections.Counter(entries) - collections.Counter(before["entries"].get(name, []))
        if added:
            new[name] = sorted(added.elements())

    undeclared = sorted(name for name in new if name not in declared)
    over_allowance = sorted(name for name in new if name in declared and len(new[name]) > 1)
    unexpected = {name: new[name] for name in undeclared + over_allowance}
    # launchd and cron together are two jobs; which one was meant is not something this harness can
    # tell, so every entry is named. This runs only when nothing else has already failed, because an
    # entry in an undeclared class is the more precise thing to report.
    two_mechanisms = not unexpected and len({SCHEDULER_MECHANISMS[name] for name in new}) > 1
    if two_mechanisms:
        unexpected = dict(new)

    # One clause per cause, each naming the class it is about, so the printed sentence says why this
    # particular run failed rather than a reason that fits only one of the paths.
    reasons = []
    for name in undeclared:
        if declared:
            reasons.append("%s is not one of the classes the case declares (%s)"
                           % (name, ", ".join(declared)))
        else:
            reasons.append("%s held a new entry and the case declares none" % name)
    for name in over_allowance:
        reasons.append("%s held %d new entries and the case declares one" % (name, len(new[name])))
    if two_mechanisms:
        reasons.append("new entries appeared in launchd and in cron, which are two recurring jobs "
                       "and not the one the case declares")

    listed = sorted(after["entries"])
    verdict = {
        "new": new,
        "unexpected": unexpected,
        "reasons": reasons,
        "expected_classes": declared,
        "probe_failed": dict(after["failed"]),
        "not_on_this_machine": dict(after["absent"]),
        "counts": {name: len(entries) for name, entries in sorted(after["entries"].items())},
        "not_probed": NOT_PROBED,
        "ok": not unexpected and not after["failed"] and bool(listed),
    }
    verdict["report"] = scheduler_report(verdict, listed)
    return verdict


def opening_scheduler_refusal():
    """The check both runners make before spawning anything: returns (snapshot, refusal), where
    refusal is None when every probe worked and a message to exit on when one did not.

    Comparing the opening snapshot with itself finds no new entry by construction, so what this
    settles is whether the probes work at all — before a run spends a session's time and calls.
    """
    start = snapshot_schedulers()
    opening = scheduler_verdict(start, start)
    if opening["ok"]:
        return start, None
    return start, ("refusing to run: this harness lists the machine's scheduler entries before and "
                   "after the session, so that a job the session installs cannot survive the run "
                   "unreported. That listing does not work on this machine:\n"
                   + "\n".join(opening["report"]))


def run_ok(sessions, verdict):
    """The one value both `result.json`'s `ok` and this program's exit status come from: every
    session ended cleanly, and the machine's scheduler entries came back the way the session found
    them. A scheduled job that outlived the session therefore cannot leave a run reported ok."""
    return (bool(sessions)
            and all(s["rc"] == 0 or s["event_killed"] for s in sessions)
            and not any(s["timeout_killed"] for s in sessions)
            and verdict["ok"])


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


def kill_group(proc):
    """SIGKILL the child's whole process group, so tool subprocesses (e.g. a hanging Bash
    call) die with it and nothing can write into the restored real workspace afterwards.
    The child is spawned with start_new_session=True, so its pid is the group id."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # group already gone


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
    proc = subprocess.Popen(cmd, cwd=cwd, text=True, start_new_session=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    t0, state, pending = time.time(), {"timeout": False, "event": False}, set()

    def backstop():  # kills a child that hangs producing no output past the timeout
        state["timeout"] = True
        kill_group(proc)

    watchdog = threading.Timer(timeout_s + 60, backstop)
    watchdog.daemon = True
    watchdog.start()
    try:
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
                        kill_group(proc)
                if time.time() - t0 > timeout_s and not (state["timeout"] or state["event"]):
                    state["timeout"] = True
                    kill_group(proc)
    finally:
        # The whole child group must be dead before the caller swaps workspaces back,
        # on every exit path — clean, killed, or an exception from the read loop.
        watchdog.cancel()
        kill_group(proc)
        try:
            rc = proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
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
    leftovers = sorted(glob.glob(WORKSPACE + ".stash-*"))
    if leftovers:
        sys.exit("refusing to run: %s exists — a previous eval run did not restore it, or "
                 "another eval run is in progress (runs are one at a time). If it holds your "
                 "real workspace, move it back to %s; otherwise remove it. Then rerun."
                 % (leftovers[0], WORKSPACE))
    start, refusal = opening_scheduler_refusal()
    if refusal:
        sys.exit(refusal)
    # PyYAML is imported here rather than at module level because CI installs pytest and nothing
    # else, and tests/test_eval_harness.py imports this module to exercise the scheduler check.
    import yaml
    with open(os.path.join(EVALS_DIR, "cases", args.case + ".yaml")) as f:
        case = yaml.safe_load(f)
    if args.model not in case["models"]:
        sys.exit("case %s does not list model %s" % (args.case, args.model))
    expected, bad_declaration = declared_classes(case, args.case)
    if bad_declaration:
        sys.exit(bad_declaration)
    kill_regex = args.kill_after_event or case.get("kill_after_event")
    # A precondition, so it is settled before the workspace is stashed: an exit here leaves nothing
    # to put back, and nothing inside the run block below exits.
    seed = None
    if case["workspace"] == "seeded":
        seed = os.path.join(EVALS_DIR, "seeds", args.case)
        if not os.path.isdir(seed):
            sys.exit("case %s declares workspace: seeded but %s is missing" % (args.case, seed))

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
    sessions, aborted = [], None
    try:
        if seed:
            shutil.copytree(seed, WORKSPACE)
        runs = [(prompt, kill_regex)]
        if case.get("followup_prompt"):
            runs.append((case["followup_prompt"], None))
        for i, (p, kr) in enumerate(runs):
            if i:
                with open(transcript, "a") as f:
                    f.write(json.dumps({"t": None, "runner": "followup-session-start"}) + "\n")
            sessions.append(run_session(p, args.model, project, transcript, case["timeout_s"], kr))
    except (Exception, KeyboardInterrupt):
        # Ctrl-C during a 25-minute run is the likely one. The scheduler comparison below still has
        # to run and still has to name what the session installed, so the abort is recorded and
        # reported rather than ending the program in a traceback here. SystemExit is not caught: the
        # arguments, the case file and the seed directory are all checked before this block, so an
        # exit raised inside it carries a message of its own.
        aborted = traceback.format_exc()
    finally:
        captured = os.path.exists(WORKSPACE)
        if captured:
            shutil.move(WORKSPACE, os.path.join(run_dir, "workspace"))
        if stash:
            shutil.move(stash, WORKSPACE)

    verdict = scheduler_verdict(start, snapshot_schedulers(), expected)
    ok = aborted is None and run_ok(sessions, verdict)
    with open(os.path.join(run_dir, "result.json"), "w") as f:
        json.dump({"case": args.case, "model": args.model, "started_utc": ts,
                   "behaviors": case["behaviors"], "kill_regex": kill_regex,
                   "sessions": sessions, "workspace_captured": captured,
                   "aborted": aborted, "scheduler": verdict, "ok": ok},
                  f, indent=1)
    for line in verdict["report"]:
        print(line)
    if aborted:
        print(aborted, file=sys.stderr)
    print("%s: %s (results in %s)" % (args.case, "ok" if ok else "FAILED", run_dir))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
