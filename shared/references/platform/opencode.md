# Platform adapter — opencode

The active-platform adapter a skill reads when it runs on **opencode** (OpenCode.ai). Neutralized prose
names an action ("ask a closed choice", "show the run recipe") and defers the opencode-specific literal
here. Read only the section you need; each is self-contained. Companion reference:
`../../../docs/design-docs/multi-harness-portability.md` (the dossier) carries the verification status
and every "pin on install" caveat.

> **Verification.** opencode is **not installed** in the environment where this adapter was authored.
> Every runtime claim below is structural — grounded in vendor documentation and the shipped integration
> test layer, never a live probe. Items that require a running opencode instance to confirm carry a
> **PIN** tag — verify them before relying on the line in shipped copy.

## Identity

The host agent is **opencode**; refer to it as "opencode" (or "the agent") in any user-facing line that
would otherwise say "Claude Code". opencode reads the configured entry file for instructions; point it
at `AGENTS.md` via the plugin's messages-transform hook (see **Packaging & install**).

## Tool map

Skills speak in actions; on opencode they resolve to these. opencode loads skills through the JS plugin's
`config.skills.paths` hook — there is no separate skill-invoke tool, but a skill invocation emits a
`"tool":"skill"` entry in the structured output. PIN: confirm the exact opencode file/edit/web-fetch
tool names and the invocation syntax on a running instance.

| Action | opencode tool |
|---|---|
| Read a file | the native read tool (PIN exact name) |
| Write a whole file | the native write tool — see **Whole-file write** below (PIN) |
| Edit part of a file | the native edit tool (PIN) |
| Run a shell command | the native shell tool (PIN) |
| Search / list files | shell (`grep`/`find`/`rg`) or a native search tool (PIN) |
| Dispatch a subagent | `@mention` — see **Concurrent detail reads** (PIN) |
| Track a task list | a native task-tracking tool, if available (PIN) |
| Ask a closed-choice question | none — see **Closed-choice question** |

## Run recipe

Show the user **verbatim**, copied exactly — do not reconstruct the tokens elsewhere. opencode's
`run` subcommand is the headless invocation path; the recurring recipe wraps it in a consent-gated
machine schedule (see **Scheduling**).

```
One-off run anytime:
  opencode run --print-logs --format json 'job-search-run'
Recurring (consent-gated machine schedule — see Scheduling):
  cron/launchd wrapping the above command on your cadence
```

PIN: confirm the exact skill-invocation token (`job-search-run` vs a namespaced form) and any flags
needed for network access or sandbox permissions inside `opencode run`.

## Scheduling

opencode is **Tier 2** (see the dossier §4 scheduling matrix):

- **No native local scheduler documented.** No opencode automation or scheduling subcommand was found
  in vendor documentation or any file read in this session. A cloud scheduler does **not** qualify —
  it cannot see the local `~/.job-search` workspace or the local agent-data auth.
- **Tier 2 — consent-gated machine schedule.** Because no native local scheduler is known, the
  sanctioned fallback is a **consent-gated** `crontab`/`launchd` entry wrapping
  `opencode run --print-logs --format json 'job-search-run'`. Show the exact cron/launchd line to
  the user **before** writing it, get an explicit yes, never install it silently, and leave it
  user-removable. Record `scheduling.mechanism: cron` (or `launchd`). opencode returns real process
  exit codes, so a cron wrapper may act on `$?` (see **Headless invocation**). PIN: if a native
  local opencode scheduler is discovered on install, prefer it and record `scheduling.mechanism`
  accordingly.

The consent gate travels inside this section — the user must explicitly approve the cron/launchd
entry before it is written. Never auto-install. The cloud-rejection rationale (no local
workspace/auth access) is harness-agnostic and applies to any candidate scheduler.

## Headless invocation

Run the search pass non-interactively with `opencode run`:

```
opencode run --print-logs --format json 'job-search-run'
```

**Exit codes: real process exit codes** — opencode's own process exits non-zero when the run fails
(the test harness treats non-zero as failure and 124 as timeout). Surface every outcome through the
**written record** as the primary channel (the three blocked-run channels and the record-is-primary
contract are shared — see `_common.md` → **Written record**); on opencode the trustworthy exit code is an
additional signal a cron wrapper may act on. PIN: whether a skill-level HALT maps to a specific non-zero
exit code from the `opencode run` process — this is the test harness's assertion, not a live-observed fact.
Also confirm that agent-data is on `PATH` inside opencode's execution environment and that outbound network
egress is not blocked.

## Closed-choice question

opencode has **no structured-choice UI** found in vendor documentation. Ask the same question as
prose with the options on numbered lines (the fallback `voice.md` already specifies), then read the
user's number. Keep authoring the header/question/labels in the skill; only the presentation
degrades to numbered prose on opencode.

Do not write any tool name in user-facing message text — the user sees only the question and its
numbered choices.

## Concurrent detail reads

opencode supports an optional `@mention` subagent system — mention another agent by name in a prompt
to involve it in the session. PIN: whether concurrent subagent dispatch (`@mention` of multiple
agents in one prompt) is supported and what the concurrency semantics are; whether any enabling
flag or version gate applies; and whether parallel `@mention` subagents share filesystem state
correctly.

The mandatory sequential fallback applies on every harness: when no subagent primitive is confirmed
or available, read and judge each posting **sequentially** — never block one read on another, but
do not fabricate a dispatch. Where a subagent primitive is confirmed, dispatch all queued postings
**at once, in a single batch** — never a one-at-a-time loop.

## Model tiers

`config.yaml` carries a portable tier token; map it to an opencode model id here.

| Tier token | opencode model |
|---|---|
| `fast` | a fast/lightweight opencode model (PIN exact id) |
| `balanced` | a mid-tier opencode model (PIN exact id) |
| `high` | a capable/frontier opencode model (PIN exact id) |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default
`fast`). PIN: exact current opencode model identifiers and whether per-subagent model selection is
supported.

## Whole-file write

On opencode the whole-file write uses the native write tool (PIN exact name), or write to a temp file then
`mv` into place. The shared read-modify-write-the-whole-file rule (and the `jobs.jsonl` `>>` append
exception) is in `_common.md` → **Whole-file write**.

PIN: confirm the exact opencode write-tool name and whether it performs an atomic replacement or a
streamed write that could leave a partial file on interruption.

## Block-alert channel

On opencode the attention-pull alert surface is **not confirmed** — PIN whether opencode surfaces an
in-editor alert, a desktop notification, or neither. The shared two-file durable-guarantee frame (and the
skip-silently rule when no surface is confirmed) is in `_common.md` → **Block-alert channel**.

## agent-data setup

Authenticate with the shared harness-neutral `--api-key` path — see `_common.md` → **agent-data auth
(harness-neutral)** (opencode has no `--opencode` flag). Skills reach agent-data through the CLI on `PATH`;
the `config.skills.paths` hook (see **Packaging & install**) loads the plugin's skills into opencode's
skill registry automatically. PIN: confirm that agent-data is accessible on `PATH` within `opencode run`
and that outbound network calls to the agent-data endpoint are not blocked.

## Packaging & install

Ships as an opencode plugin via a **new root `package.json`** (this file does not exist in the repo
today — it must be created). The manifest declares the JS plugin as the package entry point:

```json
{
  "type": "module",
  "main": ".opencode/plugins/job-search.js"
}
```

The JS plugin at `.opencode/plugins/job-search.js` does two things:

1. **`config` hook** — pushes `./skills/` into `config.skills.paths` so opencode loads the job-search
   skill tree from the one shared `skills/` directory (no per-platform bundle).
2. **`experimental.chat.messages.transform` hook** — injects a bootstrap system message and an
   **inline tool-map** that translates the skill's action vocabulary into opencode's native tool names.

Note: vendor documentation may refer to this hook as `experimental.chat.system.transform`, but the
**JS plugin is ground truth** — `experimental.chat.messages.transform` is the correct field name.
PIN: confirm the JS hook name resolves correctly on the installed opencode version.

The `package.json` is also a coordination point: the Pi adapter adds its own `pi` block to this same
file (`keywords:["pi-package"]`, `pi.skills:["./skills"]`) — sequence that addition after this file
is created (see the dossier §1, Pi row). Install by placing the `package.json` and the
`.opencode/plugins/job-search.js` file in the repo root, then loading the plugin through opencode's
plugin manager or the standard package discovery path.

PIN: confirm the exact `opencode plugin` install command, whether `opencode` reads `package.json`
from the repo root automatically, and the correct `config.skills.paths` value format on a running
instance.
