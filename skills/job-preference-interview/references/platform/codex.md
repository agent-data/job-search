# Platform adapter — OpenAI Codex

The active-platform adapter a skill reads when it runs on **OpenAI Codex** (`codex-cli`). Neutralized
prose names an action ("ask a closed choice", "show the run recipe") and defers the Codex-specific
literal here. Read only the section you need; each is self-contained. Companion reference:
`../../../docs/design-docs/multi-harness-portability.md` (the dossier) carries the verification status
and every "pin on install" caveat.

> **Verification.** Codex is the one harness installed and **partially live-tested** (`codex-cli
> 0.140.0`): live `agent-data` calls and relevance judgments worked via `codex exec`, but a later
> nested run showed the default `workspace-write` sandbox can read `~/.job-search` while refusing to
> write run artifacts there unless the workspace is the Codex cwd or is passed with `--add-dir`.
> Items still unconfirmed on a running instance carry a **PIN** tag — confirm them before relying on
> the line in shipped copy.

## Identity

The host agent is **Codex**; refer to it as "Codex" (or "the agent") in any user-facing line that would
otherwise say "Claude Code". Codex reads `AGENTS.md` and `~/.codex/AGENTS.md` for instructions.

## Tool map

Skills speak in actions; on Codex they resolve to these. Codex skills load natively — there is no
separate skill-invoke tool.

| Action | Codex tool |
|---|---|
| Read a file | `shell` (`cat`/`sed -n`), or the native read tool |
| Write a whole file | `apply_patch` — see **Whole-file write** below |
| Edit part of a file | `apply_patch` |
| Run a shell command | `shell` |
| Search / list files | `shell` (`grep`/`find`/`rg`) |
| Dispatch a subagent | `spawn_agent` / `wait_agent` / `close_agent` — see **Concurrent detail reads** |
| Track a task list | `update_plan` |
| Ask a closed-choice question | none — see **Closed-choice question** |

## Run recipe

Show the user **verbatim**, copied exactly — do not reconstruct the tokens elsewhere. Codex skills are
invoked by name; there is no Claude-style `job-search:` namespace prefix.

```
One-off run anytime:
  cd <workspace> && codex exec --skip-git-repo-check --sandbox workspace-write \
    -c sandbox_workspace_write.network_access=true '$job-search-run'
Recurring (a native local Automation — see Scheduling):
  set up a Codex Automation that runs $job-search-run on your cadence
```

`<workspace>` is the active job-search workspace from discovery (usually `~/.job-search`). If you must run
from another project directory, keep that cwd and add the workspace explicitly:

```
codex exec --skip-git-repo-check --sandbox workspace-write --add-dir <workspace> \
  -c sandbox_workspace_write.network_access=true '$job-search-run'
```

## Scheduling

Codex is **two-tier** (see the dossier §4 scheduling matrix):

- **Tier 1 — Codex App / daemon: native Automations.** A cron-cadence Automation runs **in the local
  project directory**, so it sees `~/.job-search` and the local agent-data auth, and installs nothing on
  the machine. This is the preferred mechanism when the Codex App/daemon is present. Point the Automation's
  working directory at the job-search workspace (or otherwise keep the workspace writable from it) — the same
  `workspace-write` constraint as `codex exec`: reading `~/.job-search` is not enough, the run must persist
  `runs/`, `reports/`, and `jobs.jsonl` there. Record `scheduling.mechanism: codex-automation` in the
  registry. PIN: behavior on a headless/server box with no App is unconfirmed; and whether an Automation's
  default working directory makes the workspace writable is **unverified** — confirm direct persistence on a
  running Codex App before relying on Tier 1.
- **Tier 2 — pure CLI (no App): consent-gated machine schedule.** `codex` has no automation subcommand,
  so fall back to a **consent-gated** `crontab`/`launchd` entry wrapping
  `cd <workspace> && codex exec --skip-git-repo-check --sandbox workspace-write -c sandbox_workspace_write.network_access=true '$job-search-run'`.
  Show the exact line with `<workspace>` resolved to an absolute path, get an explicit yes,
  never install it silently, and leave it user-removable. Record `scheduling.mechanism: cron` (or
  `launchd`). The relaxed-cron fallback is sanctioned here precisely because Codex offers no native local
  alternative in pure-CLI mode.

A cloud scheduler (`codex cloud exec`) does **not** qualify — it can't see the local workspace or auth.

## Headless invocation

Run the search pass non-interactively with `codex exec` (alias `e`) from the active job-search workspace:

```
cd <workspace> && codex exec --skip-git-repo-check --sandbox workspace-write \
  -c sandbox_workspace_write.network_access=true '$job-search-run'
```

`--skip-git-repo-check` because the workspace is not a git repo; `cd <workspace>` because Codex
`workspace-write` only grants write access to the current workspace roots, and job-search must write
`runs/`, `reports/`, and `jobs.jsonl`; `-c sandbox_workspace_write.network_access=true` because
workspace-write blocks network by default and the agent-data call needs egress. If the process must run
from another cwd, pass `--add-dir <workspace>` so the saved job-search workspace is writable. `--json` /
`--output-schema` are available for structured output. **Exit codes are real** — a non-zero exit signals infra/MCP/submission/
git-apply failure, so a Tier-2 cron wrapper may act on `$?`. Still surface every outcome through the
written record (blocked run record + blocked digest + home view) — the record is the contract the home
view reads; the trustworthy exit code is an *additional* signal on Codex, not a replacement. PIN: a
model-level HALT mapping to a specific non-zero code is not yet live-reproduced.

## Closed-choice question

Codex has **no structured-choice UI**. Ask the same question as prose with the options on numbered
lines (the fallback `voice.md` already specifies), then read the user's number. Keep authoring the
header/question/labels in the skill; only the presentation degrades.

## Concurrent detail reads

Codex supports isolated-context subagents via `spawn_agent` / `wait_agent` / `close_agent`. In
`codex-cli 0.140.0` the `multi_agent` feature is on by default; older builds need
`[features] multi_agent = true` in `~/.codex/config.toml`. Codex enforces a finite agent-thread limit, so
the backpressure rule (`parallelism.md`) applies here: dispatch as many queued postings as fit, close
completed agents promptly, then continue in rolling batches; with no slot at all, read and judge each
posting **sequentially** — never fabricate a dispatch.

## Model tiers

`config.yaml` carries a portable tier token; map it to a Codex model id here.

| Tier token | Codex model |
|---|---|
| `fast` | a `gpt-5`-class fast model |
| `balanced` | a mid `gpt-5`-class model |
| `high` | `gpt-5-codex` / an o-series model |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default `fast`).
PIN: exact current Codex model ids.

## Whole-file write

For structured-state files (registry, `config.yaml`), apply the change to the parsed object and write
the **whole file back atomically** — `apply_patch`, or write to a temp file then `mv` into place. Never
stream a partial/redirected write that can truncate or interleave. Appending one immutable line to the
event log (`jobs.jsonl`) stays a legitimate shell `>>` append.

## Block-alert channel

The durable guarantee is two file-backed channels (the blocked digest + the home-view run record). An
attention-pull alert is capability-gated: Codex **App** surfaces it via Triage; pure CLI has **no**
alert channel — skip it silently, the two file channels still carry the failure.

## agent-data setup

`agent-data init` has **no `--codex` flag** (its selectors are `--claude-code|--open-claw|--hermes|
--nano-claw`). Authenticate with the harness-neutral path — it sets the key without installing a
harness-specific discovery skill, which job-search does not need:

```
agent-data init --api-key <KEY> -y     # then: agent-data whoami  → api_key_set:true
```

The agent-data CLI must be on `PATH` inside Codex's sandbox and its network egress permitted.
**Verified:** under `--sandbox workspace-write` the agent-data call is blocked by default and succeeds
with `-c sandbox_workspace_write.network_access=true`; the bundled binary on `PATH` resolves inside the
sandbox. Also ensure the active job-search workspace is writable via `cd <workspace>` or
`--add-dir <workspace>`; otherwise Codex may produce temporary output but fail to persist the digest.

## Packaging & install

Ships as a Codex plugin: `.codex-plugin/plugin.json` with `skills: "./skills/"` pointing at the **same**
one `skills/` tree (no per-platform bundle). Install via Codex's plugin manager, or drop the skills into
the cross-runtime `~/.agents/skills/` path Codex reads.
