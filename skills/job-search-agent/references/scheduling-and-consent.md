# Scheduling & consent

How the Job Search Agent schedules its recurring run with Claude Code's native `/loop`, and how the
safety-net hook keeps scheduling native and off the user's machine.

## Mechanism: native `/loop` (the only one)

Job Search OS schedules with Claude Code's native **`/loop`**: `/loop <interval> /job-search-os:job-search-run`
(plugin installs — plugin skills are only invocable namespaced; loose-skill installs drop the prefix) re-runs the
search on an interval inside an **open Claude session**. There is no privileged write — nothing is added to
the user's crontab or launchd, and nothing persists on their machine. The tradeoff: it runs only while a
Claude session is open. (`/schedule` — cloud routines — is intentionally not used: a cloud agent wouldn't
have the local workspace or `agent-data` auth.)

| Step | Command | Notes |
|------|---------|-------|
| Get the artifact | `python3 "$OS" loop-command --frequency <f> [--namespace job-search-os]` | Prints the `/loop` line. Pass `--namespace job-search-os` when running as a plugin (this skill appears as `job-search-os:…` in the skill list) → `/loop <interval> /job-search-os:job-search-run`; omit it for loose skills. hourly→`1h`, every-2-hours→`2h`, every-6-hours→`6h`, daily→`24h`, weekly→`168h`. |
| Start it (on yes) | run the printed `/loop …` line | Runs in the current session; stops when the session ends. |
| Record it | `python3 "$OS" set-scheduled` | Records `mechanism: loop` so the home view shows the schedule and you don't re-ask. |
| Turn it off | stop the loop, then `python3 "$OS" set-unscheduled` | Clears the marker so `schedule-status` reads `installed: false`. |

`schedule.time` in `config.yaml` is informational under `/loop` (the loop fires on an interval from when it's
started, not at a wall-clock time). Always also show the user the verbatim `/loop` recipe from `internals.md`
so they can start or restart it themselves.

## The safety-net hook

`hooks/guard-scheduled-tasks.py` is a `PreToolUse` (Bash) guard — a **defense-in-depth backstop, not part of
the normal flow**. Because scheduling is native `/loop`, the model never needs to write the machine, so the
guard refuses any attempt to install an OS schedule and defers everything else:

| Command | Decision | Why |
|---------|----------|-----|
| A `crontab` install (`crontab -e`, `crontab <file>`, or piping into `crontab -`) | **deny** | Scheduling is `/loop`; the model must never write the user's crontab. |
| A launchd install (`launchctl load/bootstrap/enable/submit`, or writing a plist into `LaunchAgents`/`LaunchDaemons`) | **deny** | Same — `/loop` needs no launch agent. |
| Reads (`crontab -l`, `launchctl list`), removals (`launchctl unload`, `rm …plist`), `/loop`, and anything that merely *mentions* these words (a `grep`, an `echo`, a comment) | **defer** (not gated) | They don't write the machine; flagging them was a false-positive bug. |

The deny message points the model back to the `/loop` line from `osctl loop-command`. Detection is anchored to a
shell **command position** (start of line, or right after a separator like `|` `;` `&&` `(`) and requires
real write syntax — so a search like `grep -E "crontab|launchd"` or `rg crontab docs/` is never flagged; only
an actual invocation is. The guard sees only the **agent's** Bash tool calls; a user typing `crontab -e` in
their own terminal is unaffected.

## Packaging

The guard ships with the plugin via `hooks/hooks.json` at the plugin root, which references the hook as:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/guard-scheduled-tasks.py\"",
            "timeout": 5 }
        ]
      }
    ]
  }
}
```

Plugin hooks merge with the user's own hooks automatically. The user can disable all plugin hooks with `"disableAllHooks": true` in their Claude settings.

**Loose-skills installs** (copying a skill folder without the plugin) do NOT get plugin hooks. Those users must add the hook manually to their `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command",
            "command": "python3 \"${CLAUDE_PROJECT_DIR}/hooks/guard-scheduled-tasks.py\"",
            "timeout": 5 }
        ]
      }
    ]
  }
}
```
