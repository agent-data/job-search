# Platform adapter — GitHub Copilot CLI

The active-platform adapter a skill reads when it runs on **GitHub Copilot CLI** (`copilot`, also
invocable as `gh copilot`). Neutralized prose names an action ("ask a closed choice", "show the run
recipe") and defers the Copilot-specific literal here. Read only the section you need; each is
self-contained. Companion reference:
`../../../docs/design-docs/multi-harness-portability.md` (the dossier) carries the verification status
and every "pin on install" caveat.

> **Verification.** GitHub Copilot CLI (`copilot`) is **not installed** in this environment — every
> runtime claim is structural, grounded in vendor documentation and superpowers' shipped adapter files,
> never a live probe. Items unconfirmed on a running instance carry a **PIN** tag — confirm them
> empirically before relying on the line in shipped copy.

## Identity

The host agent is **GitHub Copilot CLI**; refer to it as "Copilot" (or "the agent") in any user-facing
line that would otherwise say "Claude Code". Copilot reads `COPILOT.md` from the repo root on session
start — PIN: whether the `COPILOT_CLI` session-start hook contract is honored in the installed version
(superpowers confirms it in v1.0.11+).

## Tool map

Skills speak in actions; on Copilot they resolve to these.

| Action | Copilot tool |
|---|---|
| Read a file | the native read/file tool |
| Write a whole file | the native write tool — see **Whole-file write** below |
| Edit part of a file | the native edit tool |
| Run a shell command | the native shell/terminal tool |
| Search / list files | the native search or shell tool (`grep`/`find`) |
| Dispatch a subagent | `task` with `agent_type:"general-purpose"` or `"explore"` — see **Concurrent detail reads** |
| Track a task list | no dedicated tool; track inline or in a scratch file |
| Ask a closed-choice question | none — see **Closed-choice question** |

## Run recipe

Show the user **verbatim**, copied exactly — do not reconstruct the tokens elsewhere. Copilot skills are
invoked by name from the manifest; there is no separate slash-command namespace prefix (PIN: skill-invocation form unconfirmed on a live install).

```
One-off run anytime:
  copilot -p "job-search-run" --allow-tool shell --allow-tool read --allow-tool write
Recurring (consent-gated machine schedule — see Scheduling):
  a cron/launchd entry wrapping the one-off command above, on your cadence
```

PIN: the exact `--allow-tool` flag spelling and the `--allow-all-tools` flag name are not confirmed
against the installed binary — verify with `copilot --help` before using. PIN: exit-code behavior of
`copilot -p` in a cron context is unverified (see **Headless invocation**).

## Scheduling

Copilot CLI is **Tier 2** — the first harness where the relaxed-cron rule fires unconditionally (see the
dossier §4 scheduling matrix):

- **No native local scheduler.** `gh copilot` is a one-shot launcher with no schedule subcommand. GitHub
  Actions cron is **cloud** — the Actions runner cannot see the local `~/.job-search` workspace or the
  local agent-data auth — so it does not qualify. There is no Copilot equivalent to a native
  in-session/local scheduler (nor to Codex Automations).
- **Tier 2 — consent-gated machine schedule.** Fall back to a **consent-gated** `crontab`/`launchd`
  entry wrapping `copilot -p "job-search-run" --allow-tool shell --allow-tool read --allow-tool write`.
  Show the exact line to the user, get an explicit yes, never install it silently, and leave it
  user-removable. Record `scheduling.mechanism: cron` (or `launchd`). The consent gate travels inside
  this recipe — do not run the cron install without an explicit user confirmation.

A cloud scheduler (GitHub Actions) does **not** qualify — it cannot see the local workspace or auth.

To turn scheduling off: remove the crontab entry (`crontab -e`, delete the line), then clear the
scheduling marker in the registry.

## Headless invocation

Run the search pass non-interactively with `copilot -p`:

```
copilot -p "job-search-run" --allow-tool shell --allow-tool read --allow-tool write
```

PIN: `--allow-all-tools` may be available as a shorthand flag — verify with `copilot --help` before
using; the full form above is safer. **Exit codes likely real but UNVERIFIED** — the binary is not
installed here, so unlike harnesses where a headless run can return 0 even on a block, Copilot's
exit-code behavior is unconfirmed (PIN). Surface every outcome through the **written record** instead (the
three blocked-run channels and the record-is-primary contract are shared — see `_common.md` → **Written
record**); on Copilot, whether `$?` can also be trusted is unverified — treat it as a secondary signal, not
the authority. PIN: confirm exit-code semantics on a live install.

## Closed-choice question

Copilot CLI has **no structured-choice UI** — `EnterPlanMode`/`ExitPlanMode` have no equivalent and no
structured picker tool is documented. Ask the same question as prose with the options on numbered lines
(the fallback `voice.md` already specifies), then read the user's number. Keep authoring the
header/question/labels in the skill; only the presentation degrades.

## Concurrent detail reads

Copilot supports isolated-context subagents via the **`task`** tool, with `agent_type:"general-purpose"`
for full-capability subagents or `agent_type:"explore"` for read-focused ones. Check running agents with
`read_agent` / `list_agents`. Dispatch all queued postings **at once, in a single batch** of concurrent
`task` calls — never a one-at-a-time loop. PIN: whether `task` carries any runtime gate or cap is
undocumented — no enabling flag analogous to Codex's `multi_agent` was found. When no subagent slot is
available, read and judge each posting **sequentially** — never block one read on another, but do not
fabricate a dispatch.

## Model tiers

`config.yaml` carries a portable tier token; map it to a Copilot model here.

| Tier token | Copilot model |
|---|---|
| `fast` | a fast model tier (PIN: exact Copilot model id) |
| `balanced` | a mid-tier model (PIN: exact id) |
| `high` | a high-capability model tier (PIN: exact id) |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default `fast`).
PIN: exact current Copilot model ids and the selector mechanism — verify with `copilot model list` or
equivalent.

## Whole-file write

On Copilot the whole-file write uses the native write tool, or write to a temp file then `mv` into place.
The shared read-modify-write-the-whole-file rule (and the `jobs.jsonl` `>>` append exception) is in
`_common.md` → **Whole-file write**.

## Block-alert channel

On Copilot CLI there is **no documented desktop-notification channel** — skip the attention-pull alert
silently when the `notify.desktop_notify_on_block` knob is set. The shared two-file durable-guarantee frame
is in `_common.md` → **Block-alert channel**.

## agent-data setup

Authenticate with the shared harness-neutral `--api-key` path — see `_common.md` → **agent-data auth
(harness-neutral)** (Copilot has no `--copilot` flag). Verify agent-data is on `PATH` inside Copilot's
execution environment and its network egress is not blocked before the first run.

## Packaging & install

Copilot **reuses the Claude Code manifest** — `.claude-plugin/marketplace.json` + `.claude-plugin/plugin.json`
pointing at the **same** one `skills/` tree (no per-platform bundle, no `.copilot-plugin/` directory —
superpowers ships none for Copilot). Install via Copilot's plugin manager, referencing the marketplace
manifest; the plugin manager resolves against `.claude-plugin/marketplace.json`. PIN: the exact
`copilot plugin marketplace add` / `install` argument form — the marketplace-repo slug used in
superpowers (`obra/superpowers-marketplace`) may not generalize directly to job-search's own repo slug;
verify the install command against `copilot plugin --help` on a live install.
