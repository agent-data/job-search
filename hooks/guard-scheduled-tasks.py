#!/usr/bin/env python3
"""PreToolUse guard for the Job Search Agent — deterministic scheduling consent.

  default mechanism (cron)               -> ASK  (confirm the privileged write)
  non-default (launchd) the USER chose   -> ASK  ("are you sure? the default is cron")
  non-default (launchd) the MODEL chose  -> DENY (default is cron / use /loop)
  reads, line-generation, /loop, normal  -> defer (no decision)

"Who chose" is read from a short-lived marker the scheduling workflow writes via
`osctl.py set-sched-intent --choice <mechanism>` right before installing. No fresh
marker => the model reached for it unprompted. Stdlib only; self-contained.
"""
import json, os, re, sys, time

DEFAULT_MECHANISM = "cron"
MARKER_TTL_SECONDS = 300

LAUNCHD = re.compile(
    r"launchctl\s+(load|bootstrap|enable|submit)"   # install verbs only; removal (unload/rm, for turn-off) is intentionally NOT gated
    r"|(?:>|>>|\bcp\b|\bmv\b|\btee\b|\binstall\b)[^\n]*Launch(Agents|Daemons)",
    re.IGNORECASE)
CRON = re.compile(r"crontab(?!\s+-l\b)|/etc/cron", re.IGNORECASE)


def _registry_dir():
    reg = os.environ.get("JOBSEARCH_OS_REGISTRY")
    if reg:
        return os.path.dirname(reg) or "."
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.environ.get("JOBSEARCH_OS_HOME") or os.path.expanduser("~"), ".config")
    return os.path.join(xdg, "job-search-os")


def _explicit_choice():
    """Return the user's freshly-recorded mechanism choice, or None."""
    try:
        with open(os.path.join(_registry_dir(), ".sched-intent.json"), encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - float(data.get("set_at_epoch", 0)) > MARKER_TTL_SECONDS:
            return None
        return data.get("choice")
    except Exception:
        return None


def decide(cmd):
    """Pure decision: returns (decision, reason) or None to defer."""
    is_launchd, is_cron = bool(LAUNCHD.search(cmd)), bool(CRON.search(cmd))
    if not (is_launchd or is_cron):
        return None
    if is_launchd:
        if _explicit_choice() == "launchd":
            return ("ask", "You're installing a launchd agent, which is NOT the default "
                           "(cron is). Confirm you want launchd specifically.")
        return ("deny", "Do not install a launchd agent here. The Job Search Agent's "
                        "default scheduler is cron, and /loop needs no privileged write. "
                        "Use cron, or have the user explicitly confirm launchd first.")
    return ("ask", "This installs a cron schedule for the Job Search Agent. Confirm the "
                   "privileged write to your crontab.")


def main():
    try:
        evt = json.load(sys.stdin)
    except Exception:
        return 0
    d = decide(((evt.get("tool_input") or {}).get("command") or ""))
    if d:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": d[0],
            "permissionDecisionReason": d[1]}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
