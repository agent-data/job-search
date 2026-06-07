#!/usr/bin/env python3
"""osctl.py — Job Search OS internals: registry + workspace discovery + scheduling artifacts.

Deterministic, dependency-free (stdlib only; NOT YAML-aware). The registry is a small JSON file
(machine-managed OS state); the workspace's config.yaml stays the user-facing config.

NOTE: this file is deliberately NOT named os.py — that would shadow the stdlib `os` module when run
as a script (the script dir lands on sys.path[0]).

Path defaults can be redirected for tests/evals without touching real data, via flags or env:
  registry:  --registry  >  $JOBSEARCH_OS_REGISTRY  >  $XDG_CONFIG_HOME/job-search-os/config.json  >  ~/.config/...
  workspaces: --default-workspace/--legacy-workspace  >  derived from $JOBSEARCH_OS_HOME  >  ~
"""
import argparse, html, json, os, sys, time
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


SCHED_CHOICES = ("cron", "launchd", "loop")


def _intent_path(registry_override=None):
    d = os.path.dirname(registry_path(registry_override)) or "."
    return os.path.join(d, ".sched-intent.json")


def cmd_set_sched_intent(args):
    path = _intent_path(args.registry)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"choice": args.choice, "set_at_epoch": int(time.time()),
                   "set_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}, f)
        f.write("\n")
    print(json.dumps({"choice": args.choice}))
    return 0


def cmd_clear_sched_intent(args):
    try:
        os.remove(_intent_path(args.registry))
    except FileNotFoundError:
        pass
    print(json.dumps({"cleared": True}))
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


CRON = {"hourly": "0 * * * *", "every-2-hours": "0 */2 * * *", "every-6-hours": "0 */6 * * *"}


def cron_schedule(frequency, time_str):
    if frequency in CRON:
        return CRON[frequency]
    hh, mm = (time_str or "08:00").split(":")
    h, m = int(hh), int(mm)
    if frequency == "daily":
        return f"{m} {h} * * *"
    if frequency == "weekly":
        return f"{m} {h} * * 1"   # Monday
    raise ValueError(f"unknown frequency {frequency!r} (hourly|every-2-hours|every-6-hours|daily|weekly)")


def cron_line(frequency, time_str, workspace):
    ws = workspace or default_workspace()
    return f'{cron_schedule(frequency, time_str)} cd "{ws}" && claude -p "/job-search-run" >> "{ws}/runs/cron.log" 2>&1'


def cmd_schedule_line(args):
    try:
        print(cron_line(args.frequency, args.time, args.workspace))
    except ValueError as e:
        print(f"schedule-line failed: {e}", file=sys.stderr)
        return 1
    return 0


PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>dev.jobsearchos.run</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string><string>-lc</string>
    <string>cd "{ws}" &amp;&amp; claude -p "/job-search-run" >> "{ws}/runs/cron.log" 2>&amp;1</string>
  </array>
  <key>StartCalendarInterval</key><dict>{cal}</dict>
  <key>RunAtLoad</key><false/>
</dict>
</plist>"""


def launchd_cal(frequency, time_str):
    if frequency == "hourly":
        return "<key>Minute</key><integer>0</integer>"
    hh, mm = (time_str or "08:00").split(":")
    h, m = int(hh), int(mm)
    if frequency == "daily":
        return f"<key>Hour</key><integer>{h}</integer><key>Minute</key><integer>{m}</integer>"
    if frequency == "weekly":
        return f"<key>Weekday</key><integer>1</integer><key>Hour</key><integer>{h}</integer><key>Minute</key><integer>{m}</integer>"
    raise ValueError(f"launchd plist supports hourly|daily|weekly; for {frequency!r} use cron")


def cmd_launchd_plist(args):
    try:
        ws = args.workspace or default_workspace()
        print(PLIST.format(ws=html.escape(ws), cal=launchd_cal(args.frequency, args.time)))
    except ValueError as e:
        print(f"launchd-plist failed: {e}", file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Job Search OS internals (registry, discovery, scheduling)")
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

    sl = sub.add_parser("schedule-line", help="emit the cron line for a frequency")
    sl.add_argument("--frequency", required=True)
    sl.add_argument("--time", default="08:00")
    sl.add_argument("--timezone", help="accepted for compatibility; cron uses the system timezone")
    sl.add_argument("--workspace")
    sl.set_defaults(func=cmd_schedule_line)

    lp = sub.add_parser("launchd-plist", help="emit a launchd plist (macOS)")
    lp.add_argument("--frequency", required=True)
    lp.add_argument("--time", default="08:00")
    lp.add_argument("--workspace")
    lp.set_defaults(func=cmd_launchd_plist)

    ss = sub.add_parser("schedule-status", help="print the scheduling marker as JSON")
    ss.add_argument("--registry")
    ss.set_defaults(func=cmd_schedule_status)

    sd = sub.add_parser("set-scheduled", help="record that scheduling was installed")
    sd.add_argument("--mechanism", required=True, choices=["cron", "launchd", "loop"])
    sd.add_argument("--set-at")
    sd.add_argument("--registry")
    sd.set_defaults(func=cmd_set_scheduled)

    si = sub.add_parser("set-sched-intent", help="record the user's chosen schedule mechanism (for the consent hook)")
    si.add_argument("--choice", required=True, choices=SCHED_CHOICES)
    si.add_argument("--registry")
    si.set_defaults(func=cmd_set_sched_intent)

    ci = sub.add_parser("clear-sched-intent", help="remove the schedule-intent marker")
    ci.add_argument("--registry")
    ci.set_defaults(func=cmd_clear_sched_intent)

    su = sub.add_parser("set-unscheduled", help="clear the scheduling marker (turn-off)")
    su.add_argument("--registry")
    su.set_defaults(func=cmd_set_unscheduled)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
