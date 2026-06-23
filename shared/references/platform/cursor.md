# Platform adapter — Cursor

The active-platform adapter a skill reads when it runs on **Cursor**. Neutralized prose names an
action ("ask a closed choice", "show the run recipe") and defers the Cursor-specific literal here.
Read only the section you need; each is self-contained. Companion reference:
`../../../docs/design-docs/multi-harness-portability.md` (the dossier) carries the verification
status and every "pin on install" caveat.

> **Verification.** Cursor is **not installed** in the environment where this adapter was authored.
> Every runtime claim below is structural — grounded in vendor documentation and superpowers'
> shipped integration layer, never a live probe. Items that require a running Cursor instance to
> confirm carry a **PIN** tag — verify them before relying on the line in shipped copy.

## Identity

The host agent is **Cursor**; refer to it as "Cursor" (or "the agent") in any user-facing line that
would otherwise say "Claude Code". Cursor reads `AGENTS.md` (and the Cursor-specific entry file
pointing at it) for instructions.

## Tool map

Skills speak in actions; on Cursor they resolve to these. Cursor is Claude-compatible — the tool
names below are assumed from the Claude-compatible tool inventory; no Cursor-specific remap was found
in superpowers' adapter layer. PIN: confirm the exact Cursor tool identifiers on first install.

| Action | Cursor tool |
|---|---|
| Read a file | the native read tool (Claude-compatible — PIN exact name) |
| Write a whole file | the native write tool — see **Whole-file write** below (PIN) |
| Edit part of a file | the native edit tool (PIN) |
| Run a shell command | the native shell/terminal tool (PIN) |
| Search / list files | shell (`grep`/`find`/`rg`) or a native search tool (PIN) |
| Dispatch a subagent | `Task` or equivalent (assumed Claude-compatible — see **Concurrent detail reads**) (PIN) |
| Track a task list | a native task-tracking tool, if available (PIN) |
| Ask a closed-choice question | a structured-choice tool — see **Closed-choice question** (PIN) |

## Run recipe

Show the user **verbatim**, copied exactly — do not reconstruct the tokens elsewhere. The headless
invocation command for Cursor is not confirmed; show the one-off and recurring recipes as soon as a
live probe confirms the correct command form.

```
One-off run anytime:
  [Cursor headless command — confirm on install] 'job-search-run'
Recurring (consent-gated machine schedule — see Scheduling):
  cron/launchd wrapping the above command on your cadence
```

PIN: the exact Cursor headless command and any flags needed (sandboxing, network access, skill
invocation syntax) — do not publish a recipe line until confirmed on a running Cursor instance.

## Scheduling

Cursor is **Tier 2** (see the dossier §4 scheduling matrix):

- **No native local scheduler found.** No Cursor automation or scheduling subcommand was found in
  any file read or vendor documentation reviewed. A cloud scheduler does **not** qualify — it cannot
  see the local `~/.job-search` workspace or the local agent-data auth.
- **Tier 2 — consent-gated machine schedule.** Because no native local scheduler is available, the
  sanctioned fallback is a **consent-gated** `crontab`/`launchd` entry wrapping Cursor's headless
  invocation. Show the exact cron/launchd line to the user **before** writing it, get an explicit
  yes, never install it silently, and leave it user-removable. Record `scheduling.mechanism: cron`
  (or `launchd`). PIN: if a native local Cursor scheduler is discovered on install, prefer it and
  record `scheduling.mechanism` accordingly.

The consent gate travels inside this section — the user must explicitly approve the cron/launchd
entry before it is written. Never auto-install. The cloud-rejection rationale (no local
workspace/auth access) is harness-agnostic and applies to any candidate scheduler.

## Headless invocation

The headless launch command for Cursor is **not confirmed** — it was not found in any vendor
documentation or file read in this session. Keep the **written record as primary** on every run:

- the **blocked run record** (`runs/<run_id>.json` with `run_health:"blocked"` + the named error,
  written before any halt exits),
- the **blocked digest** (`reports/<date>-digest.md` with the named error's cause and fix as the
  body),
- the **home view** the next time the user opens the **job-search** skill (it reads `run_health`
  from the newest `runs/<id>.json`).

The record is the contract the home view reads on every harness. PIN: Cursor's headless command,
any required flags, and whether its exit code is trustworthy (real non-zero on failure vs always-0).
Until confirmed, never tell the user a cron wrapper's `$?` will be non-zero on a blocked run —
surface every outcome through the written record.

## Closed-choice question

When an ask has a small closed set of answers, Cursor is assumed to support **a structured-choice
tool** (Claude-compatible) — PIN: confirm the tool is available and that its labeled-option fidelity
matches expectations (options rendered as discrete choices, not collapsed to free-text). If the tool
is unavailable or unconfirmed, ask the same question as prose with the options on numbered lines
(the fallback `voice.md` already specifies), then read the user's number. Keep authoring the
header/question/labels in the skill; only the presentation degrades to numbered prose on an
unconfirmed host.

Do not write the tool's name in user-facing message text — the user sees only the question and
its choices.

## Concurrent detail reads

Cursor is assumed to support isolated-context subagents via a **`Task`-compatible tool**
(Claude-compatible tool inventory; no Cursor-specific remap found). PIN: confirm `Task` availability,
any feature-flag or version gate, and whether parallel subagents share filesystem state correctly.

When no subagent slot is available or confirmed, read and judge each posting **sequentially** —
never block one read on another, but do not fabricate a dispatch. The mandatory sequential fallback
applies on every harness: read/judge one posting at a time, in order, until the queue is clear.
Where a subagent primitive is confirmed, dispatch all queued postings **at once, in a single batch**
— never a one-at-a-time loop.

## Model tiers

`config.yaml` carries a portable tier token; map it to a Cursor model id here.

| Tier token | Cursor model |
|---|---|
| `fast` | a fast/lightweight Cursor model (PIN exact id) |
| `balanced` | a mid-tier Cursor model (PIN exact id) |
| `high` | a capable/frontier Cursor model (PIN exact id) |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default
`fast`). PIN: exact current Cursor model identifiers and whether per-subagent model selection is
supported.

## Whole-file write

For structured-state files (registry, `config.yaml`), apply the change to the parsed object and
write the **whole file back atomically** — use the native write tool (PIN), or write to a temp file
then `mv` into place. Never stream a partial or redirected write that can truncate or interleave a
structured-state file. Appending one immutable line to the event log (`jobs.jsonl`) stays a
legitimate shell `>>` append.

PIN: confirm the exact Cursor write-tool name and whether it performs an atomic replacement or a
streamed write that could leave a partial file on interruption.

## Block-alert channel

The durable guarantee is two file-backed channels (the blocked digest + the home-view run record).
An attention-pull alert is capability-gated: Cursor's notification surface is **not confirmed** —
PIN whether Cursor surfaces an in-editor alert, a desktop notification, or neither. If no
attention-pull channel is available or confirmed, skip the alert silently; the two file channels
still carry the failure.

## agent-data setup

`agent-data init` has **no `--cursor` flag** (its selectors are `--claude-code|--open-claw|--hermes|
--nano-claw`). Authenticate with the harness-neutral path — it sets the key without installing a
harness-specific discovery skill, which job-search does not need:

```
agent-data init --api-key <KEY> -y     # then: agent-data whoami  → api_key_set:true
```

**Do not use `--claude-code` on Cursor** — that flag drops a loose agent-data skill into
`~/.claude/skills/` which may shadow or duplicate the plugin skill, producing unexpected behavior.
The `--api-key`-only path is the correct and verified workaround for all non-Claude harnesses.

The agent-data CLI must be on `PATH` inside Cursor's execution environment and its network egress
permitted. PIN: confirm that agent-data is accessible on `PATH` within Cursor's sandbox and that
outbound network calls to the agent-data endpoint are not blocked.

## Packaging & install

Ships as a Cursor plugin: `.cursor-plugin/plugin.json` with `skills: "./skills/"` pointing at the
**same** one `skills/` tree (no per-platform bundle). The manifest mirrors the structure used by the
Claude plugin but omits any `agents/` or `commands/` pointers that do not exist in this repo — only
include fields that resolve to real paths. Install via Cursor's plugin manager.

PIN: confirm whether Cursor reads `.cursor-plugin/plugin.json` directly, whether it also reads
`~/.claude/skills/` for loose skill installation, and whether plugin skills are invocable namespaced
(e.g. `job-search:`) or by bare name. Also confirm that `marketplace.json` field expectations for
Cursor match job-search's actual fields (note: per-plugin marketplace fields differ between
harnesses — job-search carries `category` but no `version`/`author`; verify the Cursor registry
accepts this shape).
