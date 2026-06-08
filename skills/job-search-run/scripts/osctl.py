#!/usr/bin/env python3
"""osctl.py — Job Search OS internals: registry + workspace discovery + the /loop schedule marker.

Deterministic, dependency-free (stdlib only; NOT YAML-aware). The registry is a small JSON file
(machine-managed OS state); the workspace's config.yaml stays the user-facing config.

NOTE: this file is deliberately NOT named os.py — that would shadow the stdlib `os` module when run
as a script (the script dir lands on sys.path[0]).

Path defaults can be redirected for tests/evals without touching real data, via flags or env:
  registry:  --registry  >  $JOBSEARCH_OS_REGISTRY  >  $XDG_CONFIG_HOME/job-search-os/config.json  >  ~/.config/...
  workspaces: --default-workspace/--legacy-workspace  >  derived from $JOBSEARCH_OS_HOME  >  ~
"""
import argparse, json, os, sys
from datetime import datetime, timezone

REGISTRY_VERSION = 1
CONFIG_NAME = "config.yaml"


def _home():
    return os.environ.get("JOBSEARCH_OS_HOME") or os.path.expanduser("~")


def default_workspace():
    return os.path.join(_home(), ".job-search")


def legacy_workspace():
    return os.path.join(_home(), "job-search")


def registry_path(override=None):
    if override:
        return override
    if os.environ.get("JOBSEARCH_OS_REGISTRY"):
        return os.environ["JOBSEARCH_OS_REGISTRY"]
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(_home(), ".config")
    return os.path.join(xdg, "job-search-os", "config.json")


def read_registry(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise ValueError(f"registry at {path} is not valid JSON: {exc}") from exc


def write_registry(path, data):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def has_config(workspace):
    return bool(workspace) and os.path.isfile(os.path.join(workspace, CONFIG_NAME))


def resolve(registry_override=None, default_ws=None, legacy_ws=None):
    default_ws = default_ws if default_ws is not None else default_workspace()
    legacy_ws = legacy_ws if legacy_ws is not None else legacy_workspace()
    reg = read_registry(registry_path(registry_override))
    if reg and reg.get("active_workspace"):
        ws = reg["active_workspace"]
        return {"workspace": ws, "first_run": not has_config(ws), "source": "registry"}
    if has_config(default_ws):
        return {"workspace": default_ws, "first_run": False, "source": "default"}
    if has_config(legacy_ws):
        return {"workspace": legacy_ws, "first_run": False, "source": "legacy"}
    return {"workspace": default_ws, "first_run": True, "source": "none"}


def cmd_resolve(args):
    try:
        print(json.dumps(resolve(args.registry, args.default_workspace, args.legacy_workspace)))
    except ValueError as e:
        print(f"resolve failed: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_set_active(args):
    try:
        path = registry_path(args.registry)
        reg = read_registry(path) or {"version": REGISTRY_VERSION}
        reg["version"] = REGISTRY_VERSION
        reg["active_workspace"] = os.path.abspath(os.path.expanduser(args.workspace))
        write_registry(path, reg)   # writes ONLY the registry; never touches the workspace
        print(json.dumps(reg))
    except ValueError as e:
        print(f"set-active failed: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_schedule_status(args):
    try:
        reg = read_registry(registry_path(args.registry)) or {}
        print(json.dumps(reg.get("scheduling") or {"installed": False, "mechanism": None, "set_at": None}))
    except ValueError as e:
        print(f"schedule-status failed: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_set_scheduled(args):
    try:
        path = registry_path(args.registry)
        reg = read_registry(path) or {"version": REGISTRY_VERSION}
        reg["version"] = REGISTRY_VERSION
        reg["scheduling"] = {
            "installed": True,
            "mechanism": args.mechanism,
            "set_at": args.set_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        write_registry(path, reg)
        print(json.dumps(reg["scheduling"]))
    except ValueError as e:
        print(f"set-scheduled failed: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_set_unscheduled(args):
    try:
        path = registry_path(args.registry)
        reg = read_registry(path) or {"version": REGISTRY_VERSION}
        reg["version"] = REGISTRY_VERSION
        reg["scheduling"] = {"installed": False, "mechanism": None, "set_at": None}
        write_registry(path, reg)
        print(json.dumps(reg["scheduling"]))
    except ValueError as e:
        print(f"set-unscheduled failed: {e}", file=sys.stderr)
        return 1
    return 0


LOOP_INTERVAL = {"hourly": "1h", "every-2-hours": "2h", "every-6-hours": "6h",
                 "daily": "24h", "weekly": "168h"}


def loop_command(frequency):
    """The native scheduler artifact: `/loop <interval> /job-search-run` for a config frequency.

    /loop runs the recurring search inside an open Claude Code session — no privileged write, nothing
    installed on the user's machine. `schedule.time` is informational under /loop: the loop fires on an
    interval from when it's started, not at a wall-clock time. Intervals are hour-based (e.g. `24h`)
    rather than `1d`/`7d`, since /loop's duration parser is not guaranteed to accept a day unit.
    """
    iv = LOOP_INTERVAL.get(frequency)
    if not iv:
        raise ValueError(f"unknown frequency {frequency!r} (hourly|every-2-hours|every-6-hours|daily|weekly)")
    return f"/loop {iv} /job-search-run"


def cmd_loop_command(args):
    try:
        print(loop_command(args.frequency))
    except ValueError as e:
        print(f"loop-command failed: {e}", file=sys.stderr)
        return 1
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Job Search OS internals (registry, discovery, /loop scheduling)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("resolve", help="print active workspace + first_run + source as JSON")
    r.add_argument("--registry")
    r.add_argument("--default-workspace")
    r.add_argument("--legacy-workspace")
    r.set_defaults(func=cmd_resolve)

    s = sub.add_parser("set-active", help="record the active workspace in the registry")
    s.add_argument("--workspace", required=True)
    s.add_argument("--registry")
    s.set_defaults(func=cmd_set_active)

    lc = sub.add_parser("loop-command", help="emit `/loop <interval> /job-search-run` for a frequency")
    lc.add_argument("--frequency", required=True)
    lc.set_defaults(func=cmd_loop_command)

    ss = sub.add_parser("schedule-status", help="print the scheduling marker as JSON")
    ss.add_argument("--registry")
    ss.set_defaults(func=cmd_schedule_status)

    sd = sub.add_parser("set-scheduled", help="record that a /loop schedule is running")
    sd.add_argument("--mechanism", default="loop", choices=["loop"])
    sd.add_argument("--set-at")
    sd.add_argument("--registry")
    sd.set_defaults(func=cmd_set_scheduled)

    su = sub.add_parser("set-unscheduled", help="clear the scheduling marker (turn-off)")
    su.add_argument("--registry")
    su.set_defaults(func=cmd_set_unscheduled)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
