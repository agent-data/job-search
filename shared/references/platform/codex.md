# Platform adapter — OpenAI Codex

The active-platform adapter a skill reads when it runs on **OpenAI Codex** (`codex-cli`). Neutralized
prose names an action ("ask a closed choice", "show the run recipe") and defers the Codex-specific
literal here. Read only the section you need; each is self-contained. Companion reference:
`../../../docs/design-docs/multi-harness-portability.md` (the dossier) carries the verification status
and every "pin on install" caveat.

> **Verification.** Codex is the one harness installed and **partially live-tested** (`codex-cli
> 0.142.0`): live `agent-data` calls and relevance judgments worked via `codex exec`, but a later
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
One-off run with approved parallel detail reads:
  cd <workspace> && codex exec --profile job-search --skip-git-repo-check --sandbox workspace-write \
    -c sandbox_workspace_write.network_access=true \
    '$job-search-run --workspace <workspace>. Use parallel subagents for all detail reads.'
Recurring (a native local Automation — see Scheduling):
  set up a Codex Automation that runs $job-search-run on your cadence
Recurring with approved parallel detail reads:
  set up a Codex Automation whose prompt is exactly:
  Use $job-search-run. Use parallel subagents for all detail reads.
```

`<workspace>` is the active job-search workspace from discovery (usually `~/.job-search`). If you must run
from another project directory, keep that cwd and add the workspace explicitly:

```
codex exec --skip-git-repo-check --sandbox workspace-write --add-dir <workspace> \
  -c sandbox_workspace_write.network_access=true '$job-search-run'
codex exec --profile job-search --skip-git-repo-check --sandbox workspace-write --add-dir <workspace> \
  -c sandbox_workspace_write.network_access=true \
  '$job-search-run --workspace <workspace>. Use parallel subagents for all detail reads.'
```

## Scheduling

Codex is **two-tier** (see the dossier §4 scheduling matrix):

- **Tier 1 — Codex App / daemon: native Automations.** A cron-cadence Automation runs **in the local
  project directory**, so it sees `~/.job-search` and the local agent-data auth, and installs nothing on
  the machine. This is the preferred mechanism when the Codex App/daemon is present. Point the Automation's
  working directory at the job-search workspace (or otherwise keep the workspace writable from it) — the same
  `workspace-write` constraint as `codex exec`: reading `~/.job-search` is not enough, the run must persist
  `runs/`, `reports/`, and `jobs.jsonl` there. Record `scheduling.mechanism: codex-automation` in the
  registry. If `search.parallel_detail_reads: true`, put the exact sentence `Use parallel subagents for all
  detail reads.` in the Automation prompt; do not assume a CLI `--profile` flag applies to App Automations.
  PIN: behavior on a headless/server box with no App is unconfirmed; and whether an Automation's default
  working directory makes the workspace writable is **unverified** — confirm direct persistence on a running
  Codex App before relying on Tier 1.
- **Tier 2 — pure CLI (no App): consent-gated machine schedule.** `codex` has no automation subcommand,
  so fall back to a **consent-gated** `crontab`/`launchd` entry wrapping
  `cd <workspace> && codex exec --skip-git-repo-check --sandbox workspace-write -c sandbox_workspace_write.network_access=true '$job-search-run'`
  or, when `search.parallel_detail_reads: true`,
  `cd <workspace> && codex exec --profile job-search --skip-git-repo-check --sandbox workspace-write -c sandbox_workspace_write.network_access=true '$job-search-run --workspace <workspace>. Use parallel subagents for all detail reads.'`.
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
written record (the three blocked-run channels and the record-is-primary contract are shared — see
`_common.md` → **Written record**); on Codex the trustworthy exit code is an *additional* signal, not a
replacement. PIN: a model-level HALT mapping to a specific non-zero code is not yet live-reproduced.

When `search.parallel_detail_reads: true`, use the `--profile job-search` recipe from **Run recipe** so
Codex loads `$CODEX_HOME/job-search.config.toml`, and keep the explicit prompt sentence. The profile enables
the subagent tool; the prompt is the user's durable authorization.

## Closed-choice question

Codex has **no structured-choice UI**. Ask the same question as prose with the options on numbered
lines (the fallback `voice.md` already specifies), then read the user's number. Keep authoring the
header/question/labels in the skill; only the presentation degrades.

## Concurrent detail reads

Codex supports isolated-context subagents via `spawn_agent` / `wait_agent` / `close_agent`. Codex CLI 0.142.0
reports `features.multi_agent` as stable/true, but Job Search still writes a scoped profile for headless runs
so older or stricter installs have the capability enabled without changing the user's global Codex defaults.
Codex still only spawns subagents when the user explicitly asks for subagents or parallel agent work.

Job Search stores that approval in `search.parallel_detail_reads`:

| Value | Codex action |
|---|---|
| unset | in a live `job-search` flow, ask once before the first run; in `job-search-run`, never prompt and read sequentially |
| `true` | use parallel subagents for all queued detail reads, subject to Codex capacity |
| `false` | read and judge queued postings sequentially |

Ask the live Codex approval as a closed choice (numbered prose on Codex): "Use parallel subagents for detail
reads? Codex will read promising postings faster by splitting those reads across helper agents. By default,
detail-read subagents use `gpt-5.4`." Options: **Yes, use subagents (Recommended)** — "faster; uses
`gpt-5.4` for posting details" · **No, read sequentially** — "slower; keeps all reads in this chat".
Only the `job-search` front door writes the user's answer into `config.yaml`; `job-search-run` only reads it.

When the user approves, also create or update `$CODEX_HOME/job-search.config.toml` for scheduled/headless
CLI runs:

```toml
[features]
multi_agent = true

[agents]
max_depth = 1
```

Tell the user this saves a Codex setting so unattended runs can use subagents. If the sandbox blocks the
write, show the exact path and TOML above so the user can save it; do not silently skip the profile. If Codex
rejects or ignores the profile, use the sequential fallback. This profile enables the capability where needed,
but it does not replace explicit prompt authorization — CLI and Automation recipes still include
`Use parallel subagents for all detail reads.` PIN: the `--profile` overlay (`$CODEX_HOME/job-search.config.toml`)
and the `[agents] max_depth` key match OpenAI's published Codex config reference but are not yet live-reproduced
in a job-search run — confirm the unattended path on a running Codex instance before relying on it.

Codex enforces a finite agent-thread limit, so the backpressure rule (`parallelism.md`) applies here:
dispatch as many queued postings as fit, close completed agents promptly, then continue in rolling batches.
If Codex refuses subagent spawning or no slot is available at all, read and judge each posting sequentially —
never fabricate a dispatch, never drop a posting, and do not mark run health partial/degraded solely for
capacity or authorization fallback.

## Model tiers

`config.yaml` carries a portable tier token; map it to a Codex model id here.

| Tier token | Codex model |
|---|---|
| `fast` | `gpt-5.4-mini` |
| `balanced` | `gpt-5.4` |
| `high` | `gpt-5.5` |
| `inherit` | the model this run is already on; omit the subagent model override |

A legacy model name carried over from another harness's config maps to the nearest tier (default `fast`).
Verified against the Codex manual fetched 2026-06-24.

## Whole-file write

On Codex the whole-file write uses **`apply_patch`** (or write to a temp file then `mv` into place). The
shared read-modify-write-the-whole-file rule (and the `jobs.jsonl` `>>` append exception) is in
`_common.md` → **Whole-file write**.

## Block-alert channel

On Codex the attention-pull alert surface depends on the client: the Codex **App** surfaces it via
Triage; pure CLI has **no** alert channel. The shared two-file durable-guarantee frame (and the
skip-silently rule when no surface exists) is in `_common.md` → **Block-alert channel**.

## agent-data setup

Authenticate with the shared harness-neutral `--api-key` path — see `_common.md` → **agent-data auth
(harness-neutral)** (Codex has no `--codex` flag). Codex-specific sandbox notes: **verified** — under
`--sandbox workspace-write` the agent-data call is blocked by default and succeeds with
`-c sandbox_workspace_write.network_access=true`; the bundled binary on `PATH` resolves inside the sandbox.
Also ensure the active job-search workspace is writable via `cd <workspace>` or `--add-dir <workspace>`;
otherwise Codex may produce temporary output but fail to persist the digest.

## Packaging & install

Ships as a Codex plugin: `.codex-plugin/plugin.json` with `skills: "./skills/"` pointing at the **same**
one `skills/` tree (no per-platform bundle). Install via Codex's plugin manager, or drop the skills into
the cross-runtime `~/.agents/skills/` path Codex reads.

### Update recipe

Show the user **verbatim** when `references/update.md` reports an update is available:

```bash
codex plugin marketplace upgrade agent-data
codex plugin add job-search@agent-data
```

Restart Codex after the update so the new plugin cache is loaded.
