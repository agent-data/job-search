# Scheduling & consent

How the Job Search Agent installs its recurring schedule, what mechanisms are available, and how the consent hook enforces safe behavior.

## Mechanisms

| Mechanism | How it works | Generate with | Notes |
|-----------|-------------|---------------|-------|
| **cron** | OS cron daemon; runs even when Claude is closed | `python3 "$OS" schedule-line --frequency <f> --time <t> --workspace <ws>` | **Default — prefer this unless the user explicitly asks otherwise** |
| **launchd** | macOS LaunchAgents; `StartCalendarInterval` can wake the machine | `python3 "$OS" launchd-plist --frequency <f> --time <t> --workspace <ws>` | Robust macOS option; non-default — requires explicit user choice |
| **/loop** | Keeps a Claude session open via `/loop <frequency> /job-search-run` | n/a (no artifact) | No privileged write; session-bound only |

Cron is the default. Prefer it unless the user explicitly names launchd or /loop.

## The record-intent-then-install workflow

Scheduling installs are consent-guarded (see [§ The consent hook](#the-consent-hook) below). Follow this exact order:

1. **Default is cron.** Prefer it unless the user explicitly asked for launchd or /loop.
2. **Record intent only if the user named a non-default mechanism.** After the user explicitly chooses launchd or /loop, record their choice so the guard can distinguish user intent from model improvisation:
   ```
   python3 "$OS" set-sched-intent --choice <cron|launchd|loop>
   ```
   Run this step ONLY after the user has named that mechanism. Do not set it for cron (the default) and do not set it for any mechanism the user has not named.
3. **Perform the install.** The guard will `ask` or `deny` based on the mechanism and whether a fresh intent marker exists (see decision table below).
4. **On success, record completion and clear the intent marker:**
   ```
   python3 "$OS" set-scheduled --mechanism <cron|launchd|loop>
   python3 "$OS" clear-sched-intent
   ```
5. **To turn scheduling off:** remove the OS artifact (delete the crontab line or the launchd plist), then:
   ```
   python3 "$OS" set-unscheduled
   ```
   This clears the `installed: true` marker so `schedule-status` reads `installed: false`.

## The consent hook

`hooks/guard-scheduled-tasks.py` is a `PreToolUse` (Bash) guard that intercepts every Bash command before it runs. It inspects the command for scheduling install patterns and applies this decision table:

| Command pattern | Condition | Decision | Message shown |
|-----------------|-----------|----------|---------------|
| `crontab` write / `/etc/cron` | — | **ask** | "This installs a cron schedule… Confirm the privileged write to your crontab." |
| `launchctl load/bootstrap/enable/submit` or writing to `LaunchAgents/LaunchDaemons` | Fresh `set-sched-intent --choice launchd` marker (≤ 300 s old) | **ask** | "You're installing a launchd agent, which is NOT the default (cron is). Confirm you want launchd specifically." |
| `launchctl load/bootstrap/enable/submit` or writing to `LaunchAgents/LaunchDaemons` | No fresh marker (model reached for launchd unprompted) | **deny** | "Do not install a launchd agent here. The default is cron, and /loop needs no privileged write." |
| Removal / turn-off (`launchctl unload`, `rm` the plist) | — | **not gated** (defer) | — |
| `/loop` | — | **not gated** (defer) | — |
| Read-only commands (`crontab -l`, `launchctl list`) | — | **not gated** (defer) | — |

**Rationale:** The guard makes the consent gate unbypassable regardless of how the model is prompted. Phrasings like "make it run hourly" or "set up a schedule" can no longer silently install a launchd agent — the hook denies it unless the user explicitly confirmed launchd first via `set-sched-intent`. The 300-second TTL on the intent marker means stale confirmations do not carry over to a later session.

Note: the `CRON` regex in the hook matches `crontab` writes but explicitly excludes `crontab -l` (read-only list), so inspection commands are never gated.

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
