# Platform adapter — Claude Code

The active-platform adapter a skill reads when it runs on **Claude Code** (`claude`). Neutralized prose
names an action ("ask a closed choice", "show the run recipe") and defers the Claude-specific literal
here. Read only the section you need; each is self-contained. Companion reference:
`../../../docs/design-docs/multi-harness-portability.md` (the dossier) carries the verification status
and every "pin on install" caveat for the other harnesses.

> **Verification.** Claude Code is the **baseline / reference harness** — the one job-search was built on
> and ships against today. The strings below are the *current shipped* literals, copied verbatim from the
> live source files, so they need no PIN tag: a reader on Claude reproduces today's behavior exactly. If
> any line here changes, the Claude path itself has changed.

## Identity

The host agent is **Claude Code**; refer to it as "Claude Code" (or "the agent") in any user-facing line.
Claude Code auto-loads `CLAUDE.md` from the repo root on session start; that file is a thin redirect to
the agnostic `AGENTS.md` (the real instruction map) — keep `CLAUDE.md` as the Claude-only entry point.

## Tool map

Skills speak in actions; on Claude Code they resolve to these. Claude Code skills load natively — a
plugin skill is invoked by its namespaced slash command, not a separate skill-invoke tool.

| Action | Claude Code tool |
|---|---|
| Read a file | `Read` |
| Write a whole file | `Write` — see **Whole-file write** below |
| Edit part of a file | `Edit` |
| Run a shell command | `Bash` |
| Search / list files | `Bash` (`grep`/`find`/`rg`), or `Grep`/`Glob` |
| Dispatch a subagent | the `Task` tool — see **Concurrent detail reads** |
| Track a task list | `TodoWrite` |
| Ask a closed-choice question | `AskUserQuestion` — see **Closed-choice question** |

## Run recipe

Show the user **verbatim**, copied exactly — do not reconstruct the tokens elsewhere. Plugin skills are
only invocable namespaced, so when these skills run as a plugin (the usual install — this skill appears
as `job-search:…` in the skill list) the target carries the `job-search:` prefix; loose skills copied
into `~/.claude/skills/` use the bare form.

```
Recurring (runs while a Claude session is open — nothing installed on your machine):
  /loop <interval> /job-search:job-search-run      # hourly → 1h · daily → 24h · weekly → 168h
One-off run anytime:
  /job-search:job-search-run
```

(For loose-skill installs, drop the `job-search:` prefix from both lines.)

Intervals are hour-based — `24h`, not `1d` — because `/loop`'s duration parser is not guaranteed to
accept a day unit. Compose `<interval>` from `schedule.frequency`: hourly→`1h`, every-2-hours→`2h`,
every-6-hours→`6h`, daily→`24h`, weekly→`168h`.

## Scheduling

Claude Code is **Tier 1** (see the dossier §4 scheduling matrix):

- **Tier 1 — native `/loop`.** Job Search schedules with Claude Code's native **`/loop`**: it re-runs the
  search on an interval **inside an open Claude session** and **installs nothing on the user's machine**
  (no crontab, no launchd, no privileged write). The one tradeoff: it runs only while a Claude session is
  open. Record `scheduling.mechanism: loop` in the registry. `schedule.time` is **informational under
  `/loop`** — the loop fires on an interval from when it's started, not at a wall-clock time, so the
  cadence is interval-only.
- **If the user explicitly asks for cron.** It's their machine and their call — show the `/loop` recipe
  **first** and let them decide; never initiate a crontab/launchd install yourself.

A cloud scheduler does **not** qualify — it can't see the local `~/.job-search` workspace or the local
agent-data auth.

To turn scheduling off: stop the loop (end the session, or cancel the pending wakeup), then clear the
scheduling marker (registry write rules — no more stale `installed: true`).

## Headless invocation

Run the search pass non-interactively with `claude -p`. **Exit code trustworthy: NO** — a headless
`claude -p` run returns **0 even when blocked** (a skill cannot set the host exit code), so never trust
`$?` and never tell the user a cron job's `$?` will be non-zero on a blocked run. Surface every outcome
through the **written record** instead (the three blocked-run channels and the record-is-primary contract
are shared — see `_common.md` → **Written record**). On Claude the exit-code add-on is "do not rely on it."

## Closed-choice question

When an ask has a small closed set of answers, present it with the **`AskUserQuestion` tool**: one
question at a time, a short header (**≤12 characters**), **2–4 options** each with a label and a one-line
description. **Never add an "other / something else" option** — the tool supplies free-text
automatically. The skill playbooks keep authoring the words (the lead sentence becomes the question text;
the choices become the option labels and descriptions); only the presentation is the tool's. The tool's
name is machinery — it never appears in the user's message text (the user sees only the question and its
choices). This is the mechanism that renders onboarding's closed-choice questions (workspace location,
interview-or-import, frequency, scheduling). If the tool is unavailable (headless or print mode), ask the
same question as prose with the options on numbered lines.

## Concurrent detail reads

Claude Code supports isolated-context subagents via the **`Task`** tool, with **per-subagent model
selection** (a faster/cheaper model can do the bulk reads while the orchestrating context stays clean).
Dispatch all queued postings **at once, in a single batch** of concurrent `Task` subagents — never a
one-at-a-time loop. When no subagent slot is available, read and judge each posting **sequentially** —
never block one read on another, but do not fabricate a dispatch.

## Model tiers

`config.yaml` carries a portable tier token; map it to a Claude model here. **This adapter is the one
place the literal Claude model names live.**

| Tier token | Claude model |
|---|---|
| `fast` | `haiku` |
| `balanced` | `sonnet` |
| `high` | `opus` |
| `inherit` | the model this run is already on |

Legacy `haiku|sonnet|opus` config values are accepted as aliases for `fast|balanced|high` (live
`config.yaml` files carry the legacy form — `search.detail_model` defaults to `haiku`).

## Whole-file write

On Claude Code the whole-file write uses the **`Write` tool** (atomic replacement) — **never shell
redirection** for a structured-state file. The shared read-modify-write-the-whole-file rule (and the
`jobs.jsonl` `>>` append exception) is in `_common.md` → **Whole-file write**.

## Block-alert channel

On Claude Code, fire one **desktop / terminal notification** (or phone) on a blocked run when the on-block
notify knob (`notify.desktop_notify_on_block`) is set. The shared two-file durable-guarantee frame — and
the rule to skip the attention-pull alert silently when no surface is available — is in `_common.md` →
**Block-alert channel**.

## agent-data setup

Authenticate the agent-data CLI and install its Claude Code discovery skill:

```
agent-data init --claude-code --api-key <KEY> --yes     # then: agent-data whoami  → api_key_set:true
```

`agent_data_init_flag = --claude-code`. This saves the key to `~/.agent-data/config.json` and installs
the **Claude Code discovery skill**. Setup-doc URL: <https://agent-data.dev/setup/claude-code.md>.
Post-install note: if Claude Code is older than `2.1.0`, a session restart may be needed for the new tool
to load; `2.1.0`+ hot-loads, so no restart is needed. The `npm install -g agent-data` floor and the
`whoami` probe are harness-neutral and apply unchanged; a permission-blocked global install becomes a
one-line `! npm install -g agent-data` in-prompt handoff (the `!`-bang runs it in-session so the agent
sees the result).

## Packaging & install

Ships as a Claude Code plugin: `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` pointing
at the **same** one `skills/` tree (no per-platform bundle). Install via Claude Code's plugin manager, or
drop the skills loose into `~/.claude/skills/`. **Plugin skills are invocable only namespaced** (the
`job-search:` prefix); loose-installed skills use the bare slash command.

### Update recipe

Show the user **verbatim** when `references/update.md` reports an update is available:

```bash
claude plugin marketplace update agent-data
claude plugin update job-search@agent-data
```

Restart Claude Code after the update so the new plugin cache is loaded.
