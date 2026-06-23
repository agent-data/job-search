# Platform adapter — Gemini CLI

The active-platform adapter a skill reads when it runs on **Gemini CLI** (Google). Neutralized prose
names an action ("ask a closed choice", "show the run recipe") and defers the Gemini-specific literal
here. Read only the section you need; each is self-contained. Companion reference:
`../../../docs/design-docs/multi-harness-portability.md` (the dossier) carries the verification status
and every "pin on install" caveat.

> **Verification.** Gemini CLI is **not installed** in the environment where this adapter was authored.
> Every runtime claim below is structural — grounded in vendor documentation and the dossier's
> per-platform study, never a live probe. Items that require a running Gemini CLI instance to confirm
> carry a **PIN** tag — verify them before relying on the line in shipped copy.

## Identity

The host agent is **Gemini CLI**; refer to it as "Gemini" (or "the agent") in any user-facing line
that would otherwise say "Claude Code". Gemini CLI loads its session context from `GEMINI.md` (via
`contextFileName: GEMINI.md` in the extension manifest). `AGENTS.md` is a regular file in this repo
— not a symlink — so `contextFileName` isolates Gemini to `GEMINI.md` without touching `AGENTS.md`.
The `GEMINI.md` file `@`-imports the front-door `SKILL.md` so the agent has instructions at session
start, and points at this adapter (`shared/references/platform/gemini.md`) for the tool map — there
is no separate per-platform tool-map file.

## Tool map

Skills speak in actions; on Gemini CLI they resolve to these. Gemini CLI loads skills through the
extension declared in `gemini-extension.json`. PIN: confirm the exact Gemini native tool names for
file read/write/edit/shell on a running instance.

| Action | Gemini CLI tool |
|---|---|
| Read a file | the native read tool (PIN exact name) |
| Write a whole file | the native write tool — see **Whole-file write** below (PIN) |
| Edit part of a file | the native edit tool (PIN) |
| Run a shell command | the native shell tool (PIN) |
| Search / list files | shell (`grep`/`find`/`rg`) or a native search tool (PIN) |
| Dispatch a subagent | `@generalist` / `@named` — see **Concurrent detail reads** |
| Track a task list | a native task-tracking tool, if available (PIN) |
| Ask a closed-choice question | `ask_user` — see **Closed-choice question** |

## Run recipe

Show the user **verbatim**, copied exactly — do not reconstruct the tokens elsewhere. The Gemini CLI
headless invocation command is not confirmed; show the one-off and recurring recipes as soon as a
live probe confirms the correct command form.

```
One-off run anytime:
  [Gemini CLI headless command — confirm on install] 'job-search-run'
Recurring (consent-gated machine schedule — see Scheduling):
  cron/launchd wrapping the above command on your cadence
```

PIN: the exact Gemini CLI headless command, its flags (network access, extension loading, skill
invocation syntax), and any exit-code semantics — do not publish a final recipe line until confirmed
on a running Gemini CLI instance.

## Scheduling

Gemini CLI is **Tier 2** (see the dossier §4 scheduling matrix):

- **No native local scheduler found.** No Gemini CLI automation or scheduling subcommand was found
  in any vendor documentation or file read in this session. A cloud scheduler does **not** qualify —
  it cannot see the local `~/.job-search` workspace or the local agent-data auth.
- **Tier 2 — consent-gated machine schedule.** Because no native local scheduler is available, the
  sanctioned fallback is a **consent-gated** `crontab`/`launchd` entry wrapping Gemini CLI's
  headless invocation. Show the exact cron/launchd line to the user **before** writing it, get an
  explicit yes, never install it silently, and leave it user-removable. Record
  `scheduling.mechanism: cron` (or `launchd`). PIN: if a native local Gemini CLI scheduler is
  discovered on install, prefer it and record `scheduling.mechanism` accordingly.

The consent gate travels inside this section — the user must explicitly approve the cron/launchd
entry before it is written. Never auto-install. The cloud-rejection rationale (no local
workspace/auth access) is harness-agnostic and applies to any candidate scheduler.

## Headless invocation

The headless launch command for Gemini CLI is **not confirmed** — no print-mode or non-interactive
command was found in any vendor documentation or file read in this session. Keep the **written
record as primary** on every run:

- the **blocked run record** (`runs/<run_id>.json` with `run_health:"blocked"` + the named error,
  written before any halt exits),
- the **blocked digest** (`reports/<date>-digest.md` with the named error's cause and fix as the
  body),
- the **home view** the next time the user opens the **job-search** skill (it reads `run_health`
  from the newest `runs/<id>.json`).

The record is the contract the home view reads on every harness. PIN: Gemini CLI's headless command,
any required flags, and whether its exit code is trustworthy (real non-zero on failure vs always-0).
Until confirmed, never tell the user a cron wrapper's `$?` will be non-zero on a blocked run —
surface every outcome through the written record.

## Closed-choice question

When an ask has a small closed set of answers, Gemini CLI exposes an **`ask_user`** tool described
as "request structured input" in vendor documentation. This is the likely closed-choice analog.
PIN: confirm that `ask_user` renders labeled options as discrete choices (not collapsed to a
free-text prompt) — the labeled-options-vs-free-text fidelity is undocumented and requires a live
probe to verify.

If `ask_user` is unavailable or does not render discrete options, ask the same question as prose
with the options on numbered lines (the fallback `voice.md` already specifies), then read the user's
number. Keep authoring the header/question/labels in the skill; only the presentation degrades to
numbered prose on an unconfirmed host.

Do not write any tool name in user-facing message text — the user sees only the question and its
choices.

## Concurrent detail reads

Gemini CLI supports isolated-context subagents natively: **`@generalist`** (a built-in all-tools
agent) and **`@named`** (a named agent). Parallel dispatch is achieved by requesting all subagents
in a single prompt — mention all targets in one message rather than separate sequential prompts.
PIN: confirm `@generalist`/`@named` availability and whether any feature-flag or version gate
applies; confirm whether parallel `@mention` subagents share filesystem state correctly.

The mandatory sequential fallback applies on every harness: when no subagent primitive is confirmed
or available, read and judge each posting **sequentially** — never block one read on another, but
do not fabricate a dispatch. Where the subagent primitive is confirmed, dispatch all queued postings
**at once, in a single batch** (one prompt mentioning all targets) — never a one-at-a-time loop.

## Model tiers

`config.yaml` carries a portable tier token; map it to a Gemini model id here.

| Tier token | Gemini CLI model |
|---|---|
| `fast` | a fast/lightweight Gemini model (Flash-class — PIN exact id) |
| `balanced` | a mid-tier Gemini model (PIN exact id) |
| `high` | a capable/frontier Gemini model (Pro-class — PIN exact id) |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default
`fast`). PIN: exact current Gemini model identifiers (Flash/Pro-class ids may change with each
release cycle) and whether per-subagent model selection is supported.

## Whole-file write

For structured-state files (registry, `config.yaml`), apply the change to the parsed object and
write the **whole file back atomically** — use the native write tool (PIN), or write to a temp file
then `mv` into place. Never stream a partial or redirected write that can truncate or interleave a
structured-state file. Appending one immutable line to the event log (`jobs.jsonl`) stays a
legitimate shell `>>` append.

PIN: confirm the exact Gemini CLI write-tool name and whether it performs an atomic replacement or
a streamed write that could leave a partial file on interruption.

## Block-alert channel

The durable guarantee is two file-backed channels (the blocked digest + the home-view run record).
An attention-pull alert is capability-gated: Gemini CLI's notification surface is **not confirmed**
— PIN whether Gemini CLI surfaces an in-terminal alert, a desktop notification, or neither. If no
attention-pull channel is available or confirmed, skip the alert silently; the two file channels
still carry the failure.

## agent-data setup

`agent-data init` has **no `--gemini` flag** (its selectors are `--claude-code|--open-claw|--hermes|
--nano-claw`). Authenticate with the harness-neutral path — it sets the key without installing a
harness-specific discovery skill, which job-search does not need:

```
agent-data init --api-key <KEY> -y     # then: agent-data whoami  → api_key_set:true
```

The `--api-key`-only path is the verified workaround for all non-Claude harnesses. Skills reach
agent-data through the CLI on `PATH`; the extension manifest (see **Packaging & install**) loads the
job-search skills into Gemini CLI's session context.

The agent-data CLI must be on `PATH` inside Gemini CLI's execution environment and its network egress
permitted. PIN: confirm that agent-data is accessible on `PATH` within Gemini CLI's session and that
outbound network calls to the agent-data endpoint are not blocked.

## Packaging & install

Ships as a Gemini CLI extension via two files at the repo root:

1. **`gemini-extension.json`** — the extension manifest. Declares `name`, `description`, `version`,
   and `contextFileName: GEMINI.md`, which tells Gemini CLI to load `GEMINI.md` as the session
   context file rather than a default or the repo's `AGENTS.md`.

2. **`GEMINI.md`** — the Gemini CLI entry file. Uses Gemini's `@`-import syntax to pull in the
   front-door `SKILL.md` (so the agent receives the job-search skill instructions), and points at
   this adapter (`shared/references/platform/gemini.md`) for the tool map that translates the skill's
   action vocabulary into Gemini CLI's native tool names — there is no separate per-platform
   tool-map file.

This adapter describes the role of both files. The `skills/` tree is the same shared tree all
harnesses point at — no per-platform bundle.

PIN: confirm the exact `gemini extensions install <url>` command form and whether it ingests the one
`skills/` tree as-is via the manifest; confirm whether Gemini CLI reads `gemini-extension.json` from
the repo root automatically on `gemini` startup in the project directory.
