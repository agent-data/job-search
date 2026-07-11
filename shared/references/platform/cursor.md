# Platform adapter — Cursor

The active-platform adapter a skill reads when it runs on **Cursor**. Neutralized prose names an
action ("ask a closed choice", "show the run recipe") and defers the Cursor-specific literal here.
Read only the section you need. Shared boilerplate is in `_common.md`; the full per-platform study and
every "confirm on install" item are in the dossier
(`../../../docs/design-docs/multi-harness-portability.md`).

> **Verification.** Cursor is **not installed** here — every runtime claim below is structural (vendor
> docs + superpowers' shipped integration layer), not a live probe. This adapter is deliberately lean:
> it carries only the genuine Cursor residual and honest stubs. Treat every literal as unconfirmed
> until probed on a running instance (AAS-TEST-15).

## Identity

The host agent is **Cursor**; refer to it as "Cursor" (or "the agent") in any user-facing line that
would otherwise say "Claude Code". Cursor reads `AGENTS.md` (and a Cursor entry file pointing at it)
for instructions.

## Tool map

Skills speak in actions; on Cursor they resolve to Cursor's native tools. Cursor is Claude-compatible,
so the tool shapes are assumed from the Claude-compatible inventory (no Cursor-specific remap was found
in superpowers' adapter layer); the exact tool-name literals are unverified here. Subagents dispatch
via a **`Task`-compatible** tool — see **Concurrent detail reads**. Closed-choice questions use a
**structured-choice** tool (assumed Claude-compatible) — see **Closed-choice question**.

## Run recipe

Cursor's headless invocation command is **not confirmed** — it was not found in any vendor
documentation or file read. Do not publish a recipe line until a live probe confirms the correct
command form (and any sandbox / network / skill-invocation flags); until then, run interactively.

## Scheduling

Cursor is **Tier 2** — no native local scheduler was found in any file or vendor doc reviewed (a cloud
scheduler does not qualify: it cannot see the local `~/.job-search` workspace or agent-data auth).
Fall back to a **consent-gated** `crontab`/`launchd` entry wrapping Cursor's headless invocation once
confirmed: show the exact line, get an explicit yes, never install it silently, leave it
user-removable, and record `scheduling.mechanism: cron` (or `launchd`). If a native local Cursor
scheduler is discovered on install, prefer it and record `scheduling.mechanism` accordingly.

## Headless invocation

The headless launch command for Cursor is **not confirmed** — it was not found in any vendor
documentation or file read. Keep the **written record as primary** on every run (the three
blocked-run channels and the record-is-primary contract are shared — see `_common.md` → **Written
record**). Cursor's exit-code trust is unverified — until confirmed, never tell the user a cron
wrapper's `$?` will be non-zero on a blocked run; surface every outcome through the written record.

## Closed-choice question

Cursor is assumed to support a **structured-choice** tool (Claude-compatible), but its availability and
labeled-option fidelity (discrete choices, not collapsed to free-text) are unverified. If the tool is
unavailable or unconfirmed, ask the same question as prose with the options on numbered lines (the
fallback `voice.md` already specifies), then read the user's number. Keep authoring the
header/question/labels in the skill; only the presentation degrades. Do not write the tool's name in
user-facing message text — the user sees only the question and its choices.

## Concurrent detail reads

Cursor is assumed to support isolated-context subagents via a **`Task`-compatible** tool
(Claude-compatible inventory; no Cursor-specific remap found), unverified. Where the subagent primitive
is confirmed, dispatch all queued postings **at once, in a single batch** — never a one-at-a-time loop.
When no subagent slot is available or confirmed, read and judge each posting **sequentially** — never
block one read on another, but **do not fabricate a dispatch**.

## Model tiers

`config.yaml` carries a portable tier token; map it to a Cursor model id here. The tier tokens are the
portable contract; the concrete Cursor model ids (and whether per-subagent model selection is
supported) are unverified — confirm on install.

| Tier token | Cursor model |
|---|---|
| `fast` | a fast/lightweight Cursor model |
| `balanced` | a mid-tier Cursor model |
| `high` | a capable/frontier Cursor model |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default `fast`).

## Whole-file write

On Cursor the whole-file write uses the native write tool, or write to a temp file then `mv` into
place. The shared read-modify-write-the-whole-file rule (and the `jobs.jsonl` `>>` append exception)
is in `_common.md` → **Whole-file write**. Whether Cursor's write tool is an atomic replacement or a
streamed write is unverified — the temp-file-then-`mv` path is the safe default until confirmed.

## Block-alert channel

Cursor's attention-pull alert surface is **not confirmed** — skip the alert silently until a live
channel is confirmed. The shared two-file durable-guarantee frame is in `_common.md` → **Block-alert
channel**.

## agent-data setup

Authenticate with the shared harness-neutral `--api-key` path — see `_common.md` → **agent-data auth
(harness-neutral)** (Cursor has no `--cursor` flag).

## Packaging & install

Cursor loads the pack from a committed manifest — **the committed manifest is the spec** (AAS-PORT-07):
`.cursor-plugin/plugin.json` exists in the repo (`skills: "./skills/"`) pointing at the **same** one
`skills/` tree (no per-platform bundle); it includes only fields that resolve to real paths. Install
via Cursor's plugin manager. Whether Cursor reads `.cursor-plugin/plugin.json` directly, whether it
also reads loose skills, and whether plugin skills are invoked namespaced or by bare name are
unverified — confirm on install.
