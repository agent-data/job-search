# Platform adapter — opencode

The active-platform adapter a skill reads when it runs on **opencode** (OpenCode.ai). Neutralized
prose names an action ("ask a closed choice", "show the run recipe") and defers the opencode-specific
literal here. Read only the section you need. Shared boilerplate is in `_common.md`; the full
per-platform study and every "confirm on install" item are in the dossier
(`../../../docs/design-docs/multi-harness-portability.md`).

> **Verification.** opencode is **not installed** here — every runtime claim below is structural
> (vendor docs + the shipped plugin + the integration-test layer), not a live probe. This adapter is
> deliberately lean: it carries only the genuine opencode residual and honest stubs. Treat every
> literal as unconfirmed until probed on a running instance (AAS-TEST-15).

## Identity

The host agent is **opencode**; refer to it as "opencode" (or "the agent") in any user-facing line
that would otherwise say "Claude Code". opencode reads `AGENTS.md` for instructions; the committed
plugin points it there via a session-start bootstrap message (see **Packaging & install**).

## Tool map

Skills speak in actions; on opencode they resolve to opencode's native tools. The action vocabulary
is the portable contract; the native tool-name literals are unverified here. opencode loads skills
through the JS plugin's `config.skills.paths` hook (no separate skill-invoke tool; a skill invocation
emits a `"tool":"skill"` entry in the structured output). Subagents dispatch via **`@mention`** — see
**Concurrent detail reads**. Closed-choice questions have no structured UI — see **Closed-choice
question**.

## Run recipe

opencode's `run` subcommand is the headless path; the recurring recipe wraps it in a consent-gated
machine schedule (see **Scheduling**).

```
One-off run anytime:
  opencode run --print-logs --format json 'job-search-run'
Recurring (consent-gated machine schedule — see Scheduling):
  cron/launchd wrapping the above command on your cadence
```

Confirm the exact skill-invocation token (`job-search-run` vs a namespaced form) and any network /
sandbox flags inside `opencode run` on a running instance.

## Scheduling

opencode is **Tier 2** — no native local scheduler is documented (a cloud scheduler does not qualify:
it cannot see the local `~/.job-search` workspace or agent-data auth). Fall back to a **consent-gated**
`crontab`/`launchd` entry wrapping `opencode run --print-logs --format json 'job-search-run'`: show
the exact line, get an explicit yes, never install it silently, leave it user-removable, and record
`scheduling.mechanism: cron` (or `launchd`). opencode's own process returns real exit codes (see
**Headless invocation**), so a cron wrapper may read `$?` as a secondary signal — but success is read
from the written record.

## Headless invocation

Run the search pass non-interactively with `opencode run --print-logs --format json 'job-search-run'`.
Surface every outcome through the **written record** as the primary channel (the three blocked-run
channels and the record-is-primary contract are shared — see `_common.md` → **Written record**).
opencode's own process exits non-zero when the run fails — this is the shipped integration test's
**assertion** (non-zero = failure, 124 = timeout), not a live-observed fact, and whether a
skill-level HALT maps to a specific non-zero code is unverified; treat `$?` as an additional signal a
cron wrapper may act on, never the authority.

## Closed-choice question

opencode has **no structured-choice UI** in vendor documentation. Ask the same question as prose with
the options on numbered lines (the fallback `voice.md` already specifies), then read the user's
number. Keep authoring the header/question/labels in the skill; only the presentation degrades.

## Concurrent detail reads

opencode supports an optional **`@mention`** subagent system (mention another agent by name in a
prompt). Where the subagent primitive is confirmed, dispatch all queued postings **at once, in a
single batch** — never a one-at-a-time loop. When no subagent primitive is available or confirmed,
read and judge each posting **sequentially** — never block one read on another, but **do not fabricate
a dispatch**. (`@mention` concurrency semantics and any enabling flag are unverified.)

## Model tiers

`config.yaml` carries a portable tier token; map it to an opencode model id here. The tier tokens are
the portable contract; the concrete opencode model ids are unverified — confirm on install.

| Tier token | opencode model |
|---|---|
| `fast` | a fast/lightweight opencode model |
| `balanced` | a mid-tier opencode model |
| `high` | a capable/frontier opencode model |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default `fast`).

## Whole-file write

On opencode the whole-file write uses the native write tool, or write to a temp file then `mv` into
place. The shared read-modify-write-the-whole-file rule (and the `jobs.jsonl` `>>` append exception)
is in `_common.md` → **Whole-file write**.

## Block-alert channel

opencode's attention-pull alert surface is **not confirmed** — skip the alert silently until a live
channel is confirmed. The shared two-file durable-guarantee frame is in `_common.md` → **Block-alert
channel**.

## agent-data setup

Authenticate with the shared harness-neutral `--api-key` path — see `_common.md` → **agent-data auth
(harness-neutral)** (opencode has no `--opencode` flag). The `config.skills.paths` hook (see
**Packaging & install**) loads the plugin's skills into opencode's skill registry.

## Packaging & install

opencode loads the pack from committed wiring — **the committed manifest and plugin are the spec**
(AAS-PORT-07): the root `package.json` (`"type":"module"`, `"main":".opencode/plugins/job-search.js"`)
and the JS plugin at `.opencode/plugins/job-search.js` both exist in the repo. The JS plugin does two
things:

1. **`config` hook** — pushes `./skills/` into `config.skills.paths` so opencode loads the one shared
   `skills/` tree (no per-platform bundle).
2. **`experimental.chat.messages.transform` hook** — injects a bootstrap message that points the agent
   at `AGENTS.md` and the tool map. This hook fires on **every agent step**, so the injection follows
   the AAS-PORT-08 lifecycle: it is a **user-role** message (not system — repeated system messages
   bloat tokens and break some models), **dedup-guarded** (a per-step callback recognizes an
   already-present bootstrap and does not duplicate it), and **re-injected after compaction** (the
   same guard re-adds the bootstrap when a compacted context has dropped it). Structural, not
   live-verified (opencode is not installed here); confirm the hook name and message-object shape on a
   running instance — `experimental.chat.messages.transform` is correct per the committed JS (ground
   truth over any README that says `system.transform`).

The `package.json` is shared with Pi (Pi's `pi` block lives in the same file). Install via opencode's
plugin manager or the standard package-discovery path (see `.opencode/INSTALL.md`).
