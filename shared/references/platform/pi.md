# Platform adapter — Pi (earendil-works pi-coding-agent)

The active-platform adapter a skill reads when it runs on **Pi** (earendil-works pi-coding-agent).
Neutralized prose names an action ("ask a closed choice", "show the run recipe") and defers the
Pi-specific literal here. Read only the section you need. Shared boilerplate is in `_common.md`; the
full per-platform study and every "confirm on install" item are in the dossier
(`../../../docs/design-docs/multi-harness-portability.md`).

> **Verification.** Pi is **not installed** here — every runtime claim below is structural (vendor
> docs + the superpowers origin repo), not a live probe. This adapter is deliberately lean: it carries
> only the genuine Pi residual and honest stubs. Treat every literal as unconfirmed until probed on a
> running instance (AAS-TEST-15). The install-line repo slug (`agent-data/job-search`) comes from
> project memory, not a Pi file.

## Identity

The host agent is **Pi**; refer to it as "Pi" (or "the agent") in any user-facing line that would
otherwise say "Claude Code". Pi reads `AGENTS.md` for instructions; ensure the repo root contains an
entry-point file (or symlink) that Pi auto-loads on session start — the exact filename is unverified.

## Tool map

Skills speak in actions; on Pi they resolve to Pi's native tools (loaded via the `pi.skills` manifest
pointer; no separate skill-invoke tool). The action vocabulary is the portable contract; the native
tool-name literals are unverified here. Subagents are available **only via the optional `pi-subagents`
package** (install-gated) — see **Concurrent detail reads**. Closed-choice questions have no
structured UI — see **Closed-choice question**.

## Run recipe

Pi's headless invocation command is **not confirmed** — no `pi exec`-style command was found in any
file read. Do not publish a recipe line until a live probe confirms the spelling; until then, run
interactively. The recurring path, once confirmed, is a consent-gated cron/launchd entry wrapping the
one-off command (see **Scheduling**).

## Scheduling

Pi is **Tier 2** — no native local scheduler is documented (zero scheduler hits across all Pi files
read; a cloud scheduler does not qualify: it cannot see the local `~/.job-search` workspace or
agent-data auth). Fall back to a **consent-gated** `crontab`/`launchd` entry wrapping the Pi headless
command once confirmed: show the exact line, get an explicit yes, never install it silently, leave it
user-removable, and record `scheduling.mechanism: cron` (or `launchd`). Confirm no native Pi scheduler
exists before relying on the Tier-2 fallback.

## Headless invocation

Pi's headless command is **not confirmed** — no `pi exec`-style command was found, and its exit-code
contract is unknown. Keep the **written record as primary** on every run (the three blocked-run
channels and the record-is-primary contract are shared — see `_common.md` → **Written record**).
Whether a Pi headless run exits non-zero on a blocked run is unverified — confirm before wiring `$?`
in a Tier-2 cron wrapper; until then, surface every outcome through the written record. (The "native
skill tool / headless command / exit code" facts are the shipped integration test's assertions — the
test SKIPs when Pi is absent — not observed on a running instance.)

## Closed-choice question

Pi has **no structured-choice UI** documented. Ask the same question as prose with the options on
numbered lines (the fallback `voice.md` already specifies), then read the user's number. Keep
authoring the header/question/labels in the skill; only the presentation degrades.

## Concurrent detail reads

Pi does **not** include a subagent dispatch primitive in its core install. Subagents are available
only via the optional **`pi-subagents`** package — **install-gated**, not a config flag. If
`pi-subagents` is installed, dispatch all queued postings **at once, in a single batch** — never a
one-at-a-time loop. If it is **not installed**, read and judge each posting **sequentially** — never
block one read on another, and **never fabricate a dispatch**. The mandatory sequential path is always
present; the concurrent path is strictly install-gated. (The exact subagent dispatch API is
unverified.)

## Model tiers

`config.yaml` carries a portable tier token; map it to a Pi model id here. The tier tokens are the
portable contract; the concrete Pi model ids are unverified — confirm on install.

| Tier token | Pi model |
|---|---|
| `fast` | a fast/lightweight Pi model |
| `balanced` | a mid-tier Pi model |
| `high` | a capable/reasoning Pi model |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default `fast`).

## Whole-file write

On Pi the whole-file write uses Pi's native write tool, or write to a temp file then `mv` into place.
The shared read-modify-write-the-whole-file rule (and the `jobs.jsonl` `>>` append exception) is in
`_common.md` → **Whole-file write**.

## Block-alert channel

Pi's attention-pull alert channel is **unknown** — skip the alert silently until a live channel is
confirmed before enabling the `notify.desktop_notify_on_block` knob on this harness. The shared
two-file durable-guarantee frame is in `_common.md` → **Block-alert channel**.

## agent-data setup

Authenticate with the shared harness-neutral `--api-key` path — see `_common.md` → **agent-data auth
(harness-neutral)** (Pi has no `--pi` flag). Pi-specific: `agent_type` will be `null` — cosmetic
skill-install metadata, **not** an auth/runtime gate. The plugin install (via the `pi.skills`
manifest) is what places the job-search skills; `init` only needs to authenticate.

## Packaging & install

Pi loads the pack from committed wiring — **the committed manifest is the spec** (AAS-PORT-07): the
root `package.json` carries a committed `pi` block —

```json
{
  "keywords": ["pi-package"],
  "pi": {
    "skills": ["./skills"]
  }
}
```

— pointing `pi.skills` at the **same** one `skills/` tree (no per-platform bundle). This `package.json`
is shared with opencode (opencode's `main`/`type` fields live in the same file). Install via Pi's
package manager, or provide the repo slug to `pi install` (the exact install command and the repo slug
`agent-data/job-search` — from project memory, not a Pi file — are unverified; confirm on install).
