# Platform adapter — Factory Droid

The active-platform adapter a skill reads when it runs on **Factory Droid** (`droid`). Neutralized
prose names an action ("ask a closed choice", "show the run recipe") and defers the Droid-specific
literal here. Read only the section you need; each is self-contained. Companion reference:
`../../../docs/design-docs/multi-harness-portability.md` (the dossier) carries the verification status
and every "pin on install" caveat.

> **Verification.** Factory Droid (`droid`) is **not installed** in this environment — every runtime
> claim is structural, grounded in vendor documentation and superpowers' shipped adapter files, never a
> live probe. Items unconfirmed on a running instance carry a **PIN** tag — confirm them empirically
> before relying on the line in shipped copy.

## Identity

The host agent is **Factory Droid**; refer to it as "Droid" (or "the agent") in any user-facing line
that would otherwise say "Claude Code". Droid reads its session-start context file on launch — PIN:
the exact filename Droid auto-loads (analogous to `CLAUDE.md`; confirm with `droid --help` on a live
install).

## Tool map

Skills speak in actions; on Droid they resolve to these.

| Action | Droid tool |
|---|---|
| Read a file | the native read/file tool |
| Write a whole file | the native write tool — see **Whole-file write** below |
| Edit part of a file | the native edit tool |
| Run a shell command | the native shell/terminal tool |
| Search / list files | the native search or shell tool (`grep`/`find`) |
| Dispatch a subagent | `Task` with `subagent_type` — see **Concurrent detail reads** |
| Track a task list | no dedicated tool; track inline or in a scratch file |
| Ask a closed-choice question | none — see **Closed-choice question** |

## Run recipe

Show the user **verbatim**, copied exactly — do not reconstruct the tokens elsewhere. `droid exec`
defaults to **read-only mode**; a search pass writes run records and digests, so the run needs at least
`--auto low` to permit those writes.

```
One-off run anytime:
  droid exec --auto low "run job-search-run"
Recurring (consent-gated machine schedule — see Scheduling):
  a cron/launchd entry wrapping `droid exec --auto low "run job-search-run"` on your cadence — see Scheduling
```

PIN: the exact skill-invocation syntax for Droid (callable tool vs namespaced slash vs pure
auto-invocation) is the highest-risk unverified item — confirm the literal prompt string Droid
expects to invoke the skill before using the recipe above. PIN: confirm the `--auto low` level
is sufficient for the scheduled pass (writing run records + digest) and does not require `--auto
medium` or higher.

## Scheduling

Droid is **Tier 2** — no native local scheduler exists (see the dossier §4 scheduling matrix):

- **No native local scheduler.** Droid's documentation delegates scheduling to external CI/CD systems,
  citing only a GitHub Actions cron example. GitHub Actions runs on a remote runner — it cannot see the
  local `~/.job-search` workspace or the local agent-data auth — so it does **not** qualify. There is
  no Droid equivalent to Claude's `/loop` or Codex Automations.
- **Tier 2 — consent-gated machine schedule.** Fall back to a **consent-gated** `crontab`/`launchd`
  entry wrapping `droid exec --auto low "run job-search-run"`. Show the exact line to the user, get an
  explicit yes, never install it silently, and leave it user-removable. Record
  `scheduling.mechanism: cron` (or `launchd`). The consent gate travels inside this recipe — do not run
  the cron install without an explicit user confirmation. Droid returns **real exit codes**, so the
  wrapper may act on `$?` (non-zero = failed run — see **Headless invocation**).

A cloud scheduler (GitHub Actions or equivalent) does **not** qualify — it cannot see the local
workspace or auth.

To turn scheduling off: remove the crontab entry (`crontab -e`, delete the line), then clear the
scheduling marker in the registry.

## Headless invocation

Run the search pass non-interactively with `droid exec`. The `--auto` flag controls the autonomy
level — the default is **read-only**, so a writing run (which must record run results and write the
digest) needs at least `--auto low`:

```
droid exec --auto low "run job-search-run"
```

**Exit codes are real** — Droid returns non-zero on failure, including when the objective is unmet,
the autonomy level is exceeded, or partial changes are abandoned. A Tier-2 cron wrapper may act on
`$?`. Still surface every outcome through the **written record** — the record is the contract the home
view reads:

- the **blocked run record** (`runs/<run_id>.json` with `run_health:"blocked"` + the named error,
  written before any exit),
- the **blocked digest** (`reports/<date>-digest.md` with the named error's cause+fix as the body),
- the **home view** the next time the user opens the **job-search** skill (it reads `run_health` from
  the newest `runs/<id>.json`).

The record is primary on every harness; the real exit code is an additional signal on Droid, not a
replacement. PIN: whether a skill-level HALT (a blocked run stopped by the skill itself) maps to a
specific non-zero exit code, or only infra/objective failures do — confirm on a live install.

## Closed-choice question

Droid has **no structured-choice UI** — no `AskUserQuestion` analog is documented. Ask the same
question as prose with the options on numbered lines (the fallback `voice.md` already specifies), then
read the user's number. Keep authoring the header/question/labels in the skill; only the presentation
degrades.

## Concurrent detail reads

Droid supports isolated-context subagents via the **`Task`** tool with `subagent_type`. This is
**enabled by default** — no enabling flag is required (contrast Codex's `multi_agent` feature flag);
to disable it, toggle the setting off in `/settings` → Experimental. Dispatch all queued postings **at
once, in a single batch** of concurrent `Task` calls — never a one-at-a-time loop. When no subagent
slot is available, read and judge each posting **sequentially** — never block one read on another, but
do not fabricate a dispatch. PIN: the exact `subagent_type` values Droid accepts (e.g. whether
`"general-purpose"` or a Droid-specific type string is required).

## Model tiers

`config.yaml` carries a portable tier token; map it to a Droid model here.

| Tier token | Droid model |
|---|---|
| `fast` | a fast model (Factory's current fast tier) |
| `balanced` | a mid-tier model |
| `high` | a high-capability model |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default `fast`).
PIN: exact current Droid model ids — Factory's model catalog may lag; verify with `droid models list`
or equivalent on a live install.

## Whole-file write

For structured-state files (the registry `config.json`, the workspace `config.yaml`), read the current
file first, apply the change to the parsed object, and write the **whole file back** atomically — use
the native write tool, or write to a temp file then `mv` into place. **Never shell redirection** for
structured-state files (it can truncate or interleave). Appending one immutable line to the event log
(`jobs.jsonl`) stays a legitimate shell `>>` append.

## Block-alert channel

The durable guarantee is two file-backed channels (the blocked digest + the home-view run record) — both
plain file writes that survive regardless of any alert surface. An attention-pull alert is
capability-gated: Droid has **no documented desktop-notification channel** — skip it silently when the
`notify.desktop_notify_on_block` knob is set; the two file channels still carry the failure. PIN:
confirm whether Droid exposes any attention-pull notification API on a live install.

## agent-data setup

`agent-data init` has **no `--droid` or `--factory` flag** (its selectors are
`--claude-code|--open-claw|--hermes|--nano-claw`). Authenticate with the harness-neutral path — it
sets the key without installing a harness-specific discovery skill, which job-search does not need:

```
agent-data init --api-key <KEY> -y     # then: agent-data whoami  → api_key_set:true
```

The agent-data CLI must be on `PATH` inside Droid's execution environment and its network egress
permitted. Verify egress is not blocked before the first run.

## Packaging & install

Droid's own plugin format uses **`.factory-plugin/plugin.json`** — only `plugin.json` goes inside
`.factory-plugin/`. Droid also supports reading `.claude-plugin/` via a Claude-plugin compatibility
layer (the doc says the format is interoperable with plugins built for Claude Code). Superpowers ships
no `.factory-plugin/` directory and relies on this compat path. PIN: confirm which manifest Droid
actually loads for job-search — whether `.factory-plugin/plugin.json` must be hand-authored (T5.2
task) or whether the existing `.claude-plugin/` compat path is sufficient without a separate manifest.
Both paths point at the **same** one `skills/` tree (no per-platform bundle). Install via Droid's
plugin manager. PIN: the exact `droid plugin marketplace add` / `install` argument form — verify the
install command against `droid plugin --help` on a live install.
