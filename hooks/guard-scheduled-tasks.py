#!/usr/bin/env python3
"""PreToolUse safety net for Job Search OS — scheduling stays native (/loop), off the machine.

Job Search OS schedules through Claude Code's native `/loop`; it never writes the user's
crontab or launchd. This guard DENIES a model-initiated cron/launchd *install* and defers
everything else — reads (`crontab -l`, `launchctl list`), removals, `/loop`, and any command
that merely *mentions* these words (a `grep`/`rg` search, an `echo`, a comment).

Detection is anchored to a shell **command position** (start of line, or right after a
separator like `|` `;` `&&` `(`) AND requires real write syntax, so searches such as
`grep -E "crontab|launchd"` or `rg crontab docs/` are never flagged — only an actual
invocation is. Stdlib only; self-contained.
"""
import json, re, sys

# A shell "command position": start of input, or right after a separator / operator / subshell
# opener. The character class already covers `&&`, `||`, pipes, and `$(`/backtick subshells.
# Anchoring here is what lets `grep "crontab"`, `echo "... crontab ..."`, and comments through.
_CMD = r"(?:^|[\n;&|(`])\s*(?:sudo\s+)?"

# Installing a cron schedule: `crontab -e`, `crontab <file>`, or `… | crontab -`. The arg after
# `crontab` must be real write syntax (`-e`, a bare `-` for stdin, or a filename); `crontab -l`
# (read) and `crontab -r` (removal) are intentionally NOT gated, and a quoted mention like
# `"foo|crontab"` has no whitespace+arg after it, so it never matches.
CRON_INSTALL = re.compile(
    _CMD + r"crontab\s+(?:-e\b|-(?=\s|$)|[^\s\-]\S*)", re.IGNORECASE)

# Installing a launchd agent: `launchctl load|bootstrap|enable|submit …` (at a command position),
# or redirecting/copying a plist into LaunchAgents/LaunchDaemons. Removal (`unload`, `rm`) is not
# gated; `launchctl list` (read) needs no exclusion since it isn't an install verb.
LAUNCHD_INSTALL = re.compile(
    _CMD + r"launchctl\s+(?:load|bootstrap|enable|submit)\b"
    r"|(?:>>?|\bcp\b|\bmv\b|\btee\b|\binstall\b)[^\n]*Launch(?:Agents|Daemons)\b",
    re.IGNORECASE)

_DENY_REASON = (
    "Job Search OS schedules with Claude Code's native /loop and never writes your machine's "
    "crontab or launchd. Set up recurring runs with:  /loop <interval> /job-search-os:job-search-run "
    "(plugin install) or  /loop <interval> /job-search-run  (loose skills) — "
    "`osctl.py loop-command --frequency <f> [--namespace job-search-os]` emits the exact line.")


def decide(cmd):
    """Pure decision: ('deny', reason) for a model-initiated cron/launchd install, else None."""
    if CRON_INSTALL.search(cmd) or LAUNCHD_INSTALL.search(cmd):
        return ("deny", _DENY_REASON)
    return None


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
