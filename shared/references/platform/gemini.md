# Platform adapter — Gemini CLI

The active-platform adapter a skill reads when it runs on **Gemini CLI** (Google). Neutralized prose
names an action ("ask a closed choice", "show the run recipe") and defers the Gemini-specific literal
here. Read only the section you need. Shared boilerplate is in `_common.md`; the full per-platform
study and every "confirm on install" item are in the dossier
(`../../../docs/design-docs/multi-harness-portability.md`).

> **Verification.** Gemini CLI is **not installed** here — every runtime claim below is structural
> (vendor docs + the dossier's per-platform study), not a live probe. This adapter is deliberately
> lean: it carries only the genuine Gemini residual and honest stubs. Treat every literal as
> unconfirmed until probed on a running instance (AAS-TEST-15).

## Identity

The host agent is **Gemini CLI**; refer to it as "Gemini" (or "the agent") in any user-facing line
that would otherwise say "Claude Code". Gemini CLI loads its session context from `GEMINI.md` (via
`contextFileName: GEMINI.md` in the committed extension manifest); `GEMINI.md` `@`-imports the
front-door `SKILL.md` and points at this adapter for the tool map — so `AGENTS.md` is untouched (see
**Packaging & install**).

## Tool map

Skills speak in actions; on Gemini CLI they resolve to Gemini's native tools (loaded through the
extension). The action vocabulary is the portable contract; the native tool-name literals are
unverified here. Subagents dispatch via **`@generalist`** (a built-in all-tools agent) or **`@named`**
— see **Concurrent detail reads**. Closed-choice questions use **`ask_user`** — see **Closed-choice
question**.

## Run recipe

The Gemini CLI headless invocation command is **not confirmed** — do not publish a recipe line until a
live probe confirms the correct command form (and any network / extension-loading / skill-invocation
flags); until then, run interactively.

## Scheduling

Gemini CLI is **Tier 2** — no native local scheduler was found in any vendor doc or file read (a cloud
scheduler does not qualify: it cannot see the local `~/.job-search` workspace or agent-data auth). Fall
back to a **consent-gated** `crontab`/`launchd` entry wrapping Gemini CLI's headless invocation once
confirmed: show the exact line, get an explicit yes, never install it silently, leave it
user-removable, and record `scheduling.mechanism: cron` (or `launchd`). If a native local Gemini
scheduler is discovered on install, prefer it and record `scheduling.mechanism` accordingly.

## Headless invocation

The headless launch command for Gemini CLI is **not confirmed** — no print-mode or non-interactive
command was found in any vendor doc or file read. Keep the **written record as primary** on every run
(the three blocked-run channels and the record-is-primary contract are shared — see `_common.md` →
**Written record**). Gemini's exit-code trust is unverified — until confirmed, never tell the user a
cron wrapper's `$?` will be non-zero on a blocked run; surface every outcome through the written
record.

## Closed-choice question

Gemini CLI exposes an **`ask_user`** tool ("request structured input" in vendor docs) — the likely
closed-choice analog, but whether it renders labeled options as discrete choices (not collapsed to
free-text) is unverified. If `ask_user` is unavailable or does not render discrete options, ask the
same question as prose with the options on numbered lines (the fallback `voice.md` already specifies),
then read the user's number. Keep authoring the header/question/labels in the skill; only the
presentation degrades. Do not write any tool name in user-facing message text — the user sees only the
question and its choices.

## Concurrent detail reads

Gemini CLI supports isolated-context subagents natively: **`@generalist`** (built-in all-tools) and
**`@named`**. Parallel dispatch is requesting all subagents in a single prompt (mention every target
in one message). Where the subagent primitive is confirmed, dispatch all queued postings **at once, in
a single batch** — never a one-at-a-time loop. When no subagent primitive is confirmed or available,
read and judge each posting **sequentially** — never block one read on another, but **do not fabricate
a dispatch**.

## Model tiers

`config.yaml` carries a portable tier token; map it to a Gemini model id here. The tier tokens are the
portable contract; the concrete Gemini model ids (Flash/Pro-class ids change per release cycle) and
whether per-subagent model selection is supported are unverified — confirm on install.

| Tier token | Gemini CLI model |
|---|---|
| `fast` | a fast/lightweight Gemini model (Flash-class) |
| `balanced` | a mid-tier Gemini model |
| `high` | a capable/frontier Gemini model (Pro-class) |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default `fast`).

## Whole-file write

On Gemini CLI the whole-file write uses the native write tool, or write to a temp file then `mv` into
place. The shared read-modify-write-the-whole-file rule (and the `jobs.jsonl` `>>` append exception)
is in `_common.md` → **Whole-file write**. Whether Gemini's write tool is an atomic replacement or a
streamed write is unverified — the temp-file-then-`mv` path is the safe default until confirmed.

## Block-alert channel

Gemini CLI's attention-pull alert surface is **not confirmed** — skip the alert silently until a live
channel is confirmed. The shared two-file durable-guarantee frame is in `_common.md` → **Block-alert
channel**.

## agent-data setup

Authenticate with the shared harness-neutral `--api-key` path — see `_common.md` → **agent-data auth
(harness-neutral)** (Gemini CLI has no `--gemini` flag). The extension manifest (see **Packaging &
install**) loads the job-search skills into Gemini CLI's session context.

## Packaging & install

Gemini CLI loads the pack from committed wiring — **the committed manifests are the spec**
(AAS-PORT-07): two repo-root files ship, both committed:

1. **`gemini-extension.json`** — the extension manifest (`name`, `description`, `version`, and
   `contextFileName: GEMINI.md`, which loads `GEMINI.md` as the session context rather than
   `AGENTS.md`).
2. **`GEMINI.md`** — the entry file. Uses Gemini's `@`-import syntax to pull in the front-door
   `SKILL.md`, and points at this adapter for the tool map that maps the skill's action vocabulary to
   Gemini's native tools (no separate per-platform tool-map file).

The `skills/` tree is the same shared tree all harnesses point at (no per-platform bundle). The exact
`gemini extensions install <url>` form, and whether Gemini reads `gemini-extension.json` from the repo
root automatically on startup, are unverified — confirm on install.
