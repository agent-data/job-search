# Platform adapter — GitHub Copilot CLI

The active-platform adapter a skill reads when it runs on **GitHub Copilot CLI** (`copilot`, also
invocable as `gh copilot`). Neutralized prose names an action ("ask a closed choice", "show the run
recipe") and defers the Copilot-specific literal here. Read only the section you need. Shared
boilerplate is in `_common.md`; the full per-platform study and every "confirm on install" item are in
the dossier (`../../../docs/design-docs/multi-harness-portability.md`).

> **Verification.** GitHub Copilot CLI (`copilot`) is **not installed** here — every runtime claim
> below is structural (vendor docs + superpowers' shipped adapter files), not a live probe. This
> adapter is deliberately lean: it carries only the genuine Copilot residual and honest stubs. Treat
> every literal as unconfirmed until probed on a running instance (AAS-TEST-15).

## Identity

The host agent is **GitHub Copilot CLI**; refer to it as "Copilot" (or "the agent") in any user-facing
line that would otherwise say "Claude Code". Copilot reads `COPILOT.md` from the repo root on session
start (the `COPILOT_CLI` session-start hook); that file **ships** at the repo root as a thin redirect
to `AGENTS.md` (mirroring `CLAUDE.md`). Whether the installed version honors the session-start hook is
unverified here — superpowers confirms it in v1.0.11+.

## Tool map

Skills speak in actions; on Copilot they resolve to Copilot's native tools. The action vocabulary is
the portable contract; the native tool-name literals are unverified here. The one host-specific note
that carries weight: subagents dispatch via the **`task`** tool (`agent_type:"general-purpose"` for
full-capability, `agent_type:"explore"` for read-focused; `read_agent`/`list_agents` inspect running
ones) — see **Concurrent detail reads**. Closed-choice questions have no structured UI — see
**Closed-choice question**.

## Run recipe

```
One-off run anytime:
  copilot -p "job-search-run" --allow-tool shell --allow-tool read --allow-tool write
Recurring (consent-gated machine schedule — see Scheduling):
  a cron/launchd entry wrapping the one-off command above, on your cadence
```

The exact `--allow-tool` spellings (and whether an `--allow-all-tools` shorthand exists) are
unverified — check `copilot --help` on a live install before relying on them.

## Scheduling

Copilot CLI is **Tier 2** — `gh copilot` is a one-shot launcher with no schedule subcommand, and
GitHub Actions cron is cloud (the Actions runner cannot see the local `~/.job-search` workspace or
agent-data auth). Fall back to a **consent-gated** `crontab`/`launchd` entry wrapping
`copilot -p "job-search-run" --allow-tool shell --allow-tool read --allow-tool write`: show the exact
line, get an explicit yes, never install it silently, leave it user-removable, and record
`scheduling.mechanism: cron` (or `launchd`). To turn scheduling off, remove the crontab entry and
clear the scheduling marker in the registry.

## Headless invocation

Run the search pass non-interactively with `copilot -p "job-search-run" --allow-tool shell
--allow-tool read --allow-tool write`. Surface every outcome through the **written record** (the three
blocked-run channels and the record-is-primary contract are shared — see `_common.md` → **Written
record**). Copilot's exit-code behavior is **UNVERIFIED here** — the binary is not installed, so
whether `$?` is trustworthy on a blocked run is unconfirmed; treat it as a secondary signal, not the
authority, and never tell the user a cron wrapper's `$?` will be non-zero on a blocked run until it is
probed on a live install.

## Closed-choice question

Copilot CLI has **no structured-choice UI** — no `Enter/ExitPlanMode` equivalent and no picker tool is
documented. Ask the same question as prose with the options on numbered lines (the fallback `voice.md`
already specifies), then read the user's number. Keep authoring the header/question/labels in the
skill; only the presentation degrades.

## Concurrent detail reads

Copilot supports isolated-context subagents via the **`task`** tool
(`agent_type:"general-purpose"`/`"explore"`). Where the subagent primitive is available, dispatch all
queued postings **at once, in a single batch** — never a one-at-a-time loop. When no subagent slot is
available, read and judge each posting **sequentially** — never block one read on another, but **do
not fabricate a dispatch**. (Whether `task` carries any runtime gate or cap is undocumented.)

## Model tiers

`config.yaml` carries a portable tier token; map it to a Copilot model here. The tier tokens are the
portable contract; the concrete Copilot model ids and the selector mechanism are unverified — confirm
with `copilot model list` or equivalent on a live install.

| Tier token | Copilot model |
|---|---|
| `fast` | a fast model tier |
| `balanced` | a mid-tier model |
| `high` | a high-capability model tier |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default `fast`).

## Whole-file write

On Copilot the whole-file write uses the native write tool, or write to a temp file then `mv` into
place. The shared read-modify-write-the-whole-file rule (and the `jobs.jsonl` `>>` append exception)
is in `_common.md` → **Whole-file write**.

## Block-alert channel

Copilot CLI exposes **no documented desktop-notification channel** — skip the attention-pull alert
silently when the `notify.desktop_notify_on_block` knob is set. The shared two-file durable-guarantee
frame is in `_common.md` → **Block-alert channel**.

## agent-data setup

Authenticate with the shared harness-neutral `--api-key` path — see `_common.md` → **agent-data auth
(harness-neutral)** (Copilot has no `--copilot` flag).

## Packaging & install

Copilot loads the pack from committed wiring — **the committed manifest is the spec** (AAS-PORT-07):
it **reuses the Claude Code manifest** (`.claude-plugin/marketplace.json` + `.claude-plugin/plugin.json`,
both committed) pointing at the **same** one `skills/` tree (no per-platform bundle, no
`.copilot-plugin/` directory). Install via Copilot's plugin manager, referencing the marketplace
manifest. The exact `copilot plugin marketplace add` / `install` argument form is unverified — the
superpowers precedent uses a marketplace-repo slug that may not generalize to job-search's repo slug;
verify against `copilot plugin --help` on a live install.
