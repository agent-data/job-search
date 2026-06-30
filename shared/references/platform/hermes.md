# Platform adapter — Hermes

The active-platform adapter a skill reads when it runs on **Hermes** (Nous Research's `hermes` agent).
Neutralized prose names an action ("ask a closed choice", "show the run recipe") and defers the
Hermes-specific literal here. Read only the section you need; each is self-contained. Companion
reference: `../../../docs/design-docs/multi-harness-portability.md` (the dossier) carries the
verification status and every PIN caveat.

> **Verification.** Hermes is **not installed on the CI runner**, so these literals are **source-cited**
> against `NousResearch/hermes-agent@main` (the file each maps to is named inline) and **structurally
> validated** (`scripts/validate_platforms.py`), then **live-verified by the maintainer on a real Hermes
> install from this branch**. A line not yet reproduced on a running instance carries a **PIN** tag —
> confirm it on that live pass before treating it as shipped.

## Identity

The host agent is **Hermes** (or "Hermes Agent"), built by Nous Research; the CLI is `hermes`. Refer to
it as "Hermes" in any user-facing line. Hermes's own persona lives in `SOUL.md` under `HERMES_HOME`
(`~/.hermes/SOUL.md`) and is loaded only from there — **do not** put job-search instructions in `SOUL.md`.
Inject workspace/job-search guidance through the workspace **`AGENTS.md`** instead (Hermes loads a project
`AGENTS.md` from the directory it starts in — cwd, top-level only; the cwd→git-root walk applies to
`.hermes.md`/`HERMES.md`, not `AGENTS.md`. Source: `agent/prompt_builder.py`.); that is the supported channel
for repo guidance, kept separate from identity. (Source: `hermes_cli/config.py`, `docs/user-guide/features/personality`, `context-files`.)

## Tool map

Skills speak in actions; on Hermes they resolve to these built-in tools. Hermes skills load natively from
the on-disk skill set — an installed skill is also exposed as a slash command (`/job-search-run`), not a
separate skill-invoke tool. (Source: `website/docs/reference/tools-reference.md`.)

| Action | Hermes tool |
|---|---|
| Read a file | `read_file` |
| Write a whole file | `write_file` — overwrites, creates parent dirs; see **Whole-file write** |
| Edit part of a file | `patch` |
| Run a shell command | `terminal` (`command`; `workdir`/`timeout` [PIN]) |
| Search / list files | `search_files` (ripgrep-backed) |
| Dispatch a subagent | `delegate_task` — see **Concurrent detail reads** |
| Ask a closed-choice question | `clarify` — see **Closed-choice question** |
| Fetch / search the web | `web_extract` / `web_search` (there is no `web_fetch`) |

The bundled state-ops runtime is invoked through `terminal` (see **Whole-file write**).

## Run recipe

Show the user **verbatim**, copied exactly — do not reconstruct the tokens elsewhere.

```
Recurring (native Hermes cron — delivers the result back to this chat):
  hermes cron create "<schedule>" "run a job search now" --skill job-search-run --deliver origin --name "Daily job search"
One-off run anytime (headless):
  hermes chat -Q -s job-search-run -q "run a job search now"
Interactive:
  /job-search-run
```

Compose `<schedule>` from `schedule.frequency` (a cron expression or interval Hermes accepts — see
**Scheduling**): hourly→`"every 1h"`, every-2-hours→`"every 2h"`, every-6-hours→`"0 */6 * * *"`,
daily→`"0 9 * * *"` (using `schedule.time`), weekly→`"0 9 * * 1"`. [PIN: confirm the
`hermes chat -Q -s … -q …` flags against `hermes chat --help`.]

## Scheduling

Hermes is **Tier 1** with a genuinely native scheduler — no consent-gated machine cron needed:

- **Tier 1 — native `hermes cron`.** Job Search schedules with Hermes's built-in cron subsystem, driven
  either by the `hermes cron` CLI or the agent's `cronjob` tool —
  `cronjob(action="create", schedule="<sched>", prompt="run a job search now", skills=["job-search-run"], deliver="origin", name="Daily job search")`.
  One engine writes the job to `~/.hermes/cron/jobs.json`; the **gateway daemon ticks it every ~60s**, so
  the gateway must be running for jobs to fire. Cadence accepts a cron expression (`"0 9 * * *"`), an
  interval (`"every 2h"`), a relative duration (`"30m"`/`"2h"`/`"1d"`), or an ISO timestamp. Lifecycle:
  `create | list | update | pause | resume | run | remove`. Record `scheduling.mechanism: hermes-cron` in
  the registry (plus the optional `job_id` and `deliver` — the bundled runtime's `set-scheduling` writes
  all three). A cron run is a **fresh, isolated session with no prior context and cannot `clarify`**, so
  the scheduled prompt must be self-contained — `job-search-run` already is. Delivery defaults to
  `"origin"` → the chat the job was created from (else the platform's configured home channel); see
  **Block-alert channel**. (Source: `cron/jobs.py`, `cron/scheduler.py`, `hermes_cli/subcommands/cron.py`,
  `docs/chronos-managed-cron-contract.md`.)

To bind `--deliver origin` to *this* chat, create the job with the in-session **`cronjob` tool**
(`cronjob(action="create", …)`), not a shelled `hermes cron create` from a bare terminal; origin binds to
the session that creates the job. Confirm the gateway daemon is running (it ticks ~every 60s) before
promising automation.

The judgment-bearing run uses `--skill job-search-run` (the model judges fit); Hermes's `--no-agent
--script` cron path runs a script with no model and is **not** used for the search.

A cloud scheduler that cannot see the local `~/.job-search` workspace or the local agent-data auth does
**not** qualify. To turn scheduling off: `hermes cron remove <job_id>` (or `pause`), then clear the
scheduling marker (registry write rules — no more stale `installed: true`).

## Headless invocation

Run the search pass non-interactively with **`hermes chat -Q -s job-search-run -q "run a job search
now"`** — `-s/--skills` preloads the skill, `-q` passes the prompt, `-Q/--quiet` keeps stdout to the
response and makes the exit code reliable. **Exit code trustworthy: YES** [PIN] — unlike Claude's
`claude -p`, a quiet Hermes run exits `0` on success and non-zero on failure. (`hermes -z "<prompt>"` is a
stricter 0/1/2 oneshot but **ignores `-s/--skills`**, so prefer `chat -Q -s … -q …` to run *this* skill.)
[PIN: confirm the `-Q/-s/-q` flags and exit-code semantics against `hermes chat --help` / `hermes_cli/`.]

Even with a trustworthy exit code, surface every outcome through the **written record** — it is the
contract the home view reads, and the same on every harness:

- the **blocked run record** (`runs/<run_id>.json` with `run_health:"blocked"` + the named error, written
  before any HALT exits),
- the **blocked digest** (`reports/<date>-digest.md` with the named error's cause+fix as the body),
- the **home view** the next time the user opens the **job-search** skill.

The record is primary; the trustworthy exit code is an *additional* signal a cron wrapper may read.

## Closed-choice question

When an ask has a small closed set of answers, present it with the **`clarify` tool**: a question plus a
`choices` list of **≤4 options**, each a label + a one-line description. Hermes **auto-appends a final
"Other" choice** for free text, so **never author an "other / something else" option** yourself. The
skill playbooks keep authoring the words (the lead sentence becomes the question; the choices become the
options); only the presentation is the tool's. If more than four discrete options are needed, ask the
same question as prose with the options on numbered lines. `clarify` is **unavailable in a headless or
cron run** (a scheduled session cannot ask) — there, pick a sane default and never block. (Source:
`tools-reference.md`; `delegation.md` notes leaf subagents also have `clarify` blocked.)

## Prior-session recall

Hermes can search the user's **prior sessions** with `session_search` (an FTS5 index over past
conversations). This is the capability behind the preference interview's *draft-from-prior-context* offer:
with permission, search prior sessions for what the user has said about jobs/work and synthesize a **draft**
Job Preferences Brief.

- **Ask first.** Never read prior sessions to draft without explicit permission; offer it, state the
  benefit, and give a clean decline path.
- **Sessions, not memory.** Hermes's `MEMORY.md`/`USER.md` is already auto-injected into context as a frozen
  snapshot at session start — you do not "use memory" on request. This offer is specifically about searching
  *prior sessions* via `session_search`.
- **Draft, not truth.** Write the synthesized result **only** to the workspace brief
  (`<workspace>/preferences.md`) and present it as an editable draft. **Never** write `USER.md` and never
  silently promote an inferred preference to durable user-profile truth — the workspace brief is canonical.
- **Interactive only.** A scheduled/headless run is a fresh session with no prior-session access and cannot
  ask, so this offer never fires there.

## Concurrent detail reads

Hermes fans out isolated subagents via the **`delegate_task`** tool in **batch** form —
`delegate_task(tasks=[{goal, context, toolsets, role}, …])`, one task per promising posting. Each child
is a **fresh agent with no parent history**, so pass the full context in each task: the posting `id` and
`source_url`, the brief path, the `evaluate-job-fit` contract, and the parent's per-posting steer — the
child knows nothing you do not hand it. Results return **inline, sorted by task index**, and the call
**blocks until every child finishes**. (Source: `docs/user-guide/features/delegation.md`.)

Two limits shape the dispatch:

- **Concurrency defaults to 3** (`delegation.max_concurrent_children`), and a batch larger than the cap is
  **rejected**, not truncated — so **chunk the promising postings into groups of ≤3** (or raise the
  config) and run the groups in sequence.
- **Depth is flat** (`max_spawn_depth: 1`): a child cannot itself delegate or `clarify`.

`delegate_task` children **inherit the parent's model**. **Fallback:** if Hermes refuses to spawn
subagents or none can be scheduled, read and judge each posting **sequentially** in the main turn — never
fabricate a dispatch, never drop a posting; a capacity/authorization fallback is not a run-health error.
[PIN: one code path suggested top-level delegations may run in the background — results arriving as a
later message rather than inline; the docs say inline/blocking. Confirm on the live pass; until then the
sequential fallback is the safe path for a strictly in-turn run.]

**Collect results from disk, not the return channel.** Each detail subagent writes its `evaluate-job-fit`
verdict for its posting to a run-scoped scratch file (e.g. `<workspace>/.runs/<run_id>/details/<posting_id>.json`)
instead of relying on its text returning to the parent. The orchestrator's completion signal is "the expected
verdict files exist"; it then reads them, folds them into the durable digest / run record / event log (the
bundled runtime does the bookkeeping; judgment stays in the subagents and the orchestrator), and never holds
the long descriptions in its own context. This is deliberate, not a fallback: it keeps the primary context
lean and makes the run **correct regardless of the inline-vs-background question above** — whichever way
`delegate_task` returns, the verdicts are already on disk. A true sequential in-turn read is only a
last-resort fallback when no subagent can be spawned at all.

## Model tiers

Hermes has no native tier abstraction — a model is a `provider/model_id` pair. `config.yaml` carries a
portable tier token; map it to a concrete Hermes model here. **This adapter is the one place the literal
Hermes model names live**, and model IDs drift, so [PIN] confirm the current IDs at install.

| Tier token | Hermes model |
|---|---|
| `fast` | `deepseek/deepseek-v4-flash` (or `anthropic/claude-haiku-4-5`) |
| `balanced` | `anthropic/claude-sonnet-4-6` |
| `high` | `anthropic/claude-opus-4-8` (or `claude-fable-5`) |
| `inherit` | the model this run is already on — emit no model; Hermes uses the configured default, and `delegate_task` children inherit the parent |

Normalize per provider: Anthropic *native* uses hyphens (`claude-opus-4-8`); aggregator providers (nous,
openrouter) take the dotted `vendor/model` form (`anthropic/claude-opus-4.8`). Set the model via
`--model <provider/model>`, the `model.default` + `model.provider` config, or `/model` at runtime. Legacy
`haiku|sonnet|opus` config values map to `fast|balanced|high`. (Source: `hermes_cli/model_catalog.py`,
`hermes_cli/model_normalize.py`, `docs/user-guide/configuration`.)

## Whole-file write

For structured-state files (the registry `config.json`, the workspace `config.yaml`, a `runs/<id>.json`
record, the digest), write the **whole file back** with **`write_file`** (it overwrites and creates parent
dirs) — never a streamed/partial write. `write_file`'s atomicity is not evidenced [PIN], so for a state
file write to a temp path with `terminal` and `mv` it into place, or let the bundled runtime do it (it
writes via a temp file + `os.replace`). Appending one immutable line to the event log (`jobs.jsonl`) stays
a legitimate `terminal` `>>` append.

**Bundled state-ops runtime (the Hermes divergence).** On Hermes, perform the deterministic OS-state
operations through the small stdlib-Python runtime bundled in this skill at `scripts/hermes_job_search/`,
called via the `terminal` tool:

```
python3 ${HERMES_SKILL_DIR}/scripts/hermes_job_search/cli.py <op> [flags]   # one JSON object on stdout
```

`${HERMES_SKILL_DIR}` is a **load-time `SKILL.md` template token** (text-substituted into the rendered skill
markdown, gated by `skills.template_vars`, default on), **not** a shell env var. The call works because the
model reads the already-substituted concrete path from its rendered `SKILL.md`; if `skills.template_vars` is
off the token will not expand — fall back to resolving the skill directory from the run path. (Source:
`agent/skill_preprocessing.py`.) The ops — `discover-workspace`, `read-registry`,
`set-active-workspace`, `set-scheduling` / `clear-scheduling`, `load-config`, `update-config`,
`known-ids`, `append-event`, `fold-state`, `write-run-record`, `write-digest` — take inputs from flags or
stdin JSON and return one JSON object on stdout (logs go to stderr). Their **inputs, semantics, and
on-disk bytes are identical** to the native procedures in `internals.md` / `conventions.md`; **judgment
never moves into the runtime** — it does deterministic bookkeeping only, while relevance, match, and
reasoning stay in the model. Every other harness performs these same procedures in-context and ignores
the runtime.

## Block-alert channel

The durable guarantee is two file-backed channels (the blocked digest + the home-view run record) — plain
file writes that survive regardless of any alert surface. On Hermes, a scheduled run also surfaces a block
as its **final response text**, which the cron pipeline **delivers to the job's `deliver` target** —
default `"origin"`, i.e. the chat the job was created from (else the platform's home channel). Because a
cron session cannot `clarify`, a block is a *delivered message*, not an interactive prompt; an empty or
`[SILENT]` final output suppresses delivery, so a real block must emit non-empty text. Hermes has no
documented desktop-notify surface [PIN]; the cron delivery to the originating chat IS the attention-pull
channel, so `notify.desktop_notify_on_block` maps to "deliver the block to chat." (Source:
`cron/scheduler.py` delivery routing.)

## agent-data setup

Authenticate the agent-data CLI for Hermes:

```
agent-data init --hermes --api-key <KEY> --yes      # then: agent-data whoami  → api_key_set:true
```

`agent_data_init_flag = --hermes` — `--hermes` is one of agent-data init's real harness selectors
(`--claude-code | --open-claw | --hermes | --nano-claw`; the same enum is documented in `codex.md`'s
agent-data setup). [PIN: confirm `--hermes` does not also install a foreign discovery skill job-search
does not need; if it does, fall back to the bare `agent-data init --api-key <KEY> -y` the Codex adapter
uses.] Run it through the `terminal` tool. The agent-data CLI installs to `~/.local/bin` — the same
directory Hermes symlinks `hermes` into — so it is already on the expected PATH; the CLI is unauthenticated
until `init`, and needs outbound network. The `npm install -g agent-data` floor and the `whoami` probe are
harness-neutral.

## Packaging & install

Ships as a **Hermes skill pack** — the `SKILL.md` directories of the **same** one `skills/` tree, with
**no plugin manifest** required (Hermes discovers skills by scanning for `SKILL.md`; the frontmatter is
agentskills.io-compatible and Hermes ignores the Claude-only keys). The Hermes path also carries the
bundled stdlib runtime at `scripts/hermes_job_search/` (see **Whole-file write**), synced into the
consuming skills by `scripts/build.sh`. Install one of three ways:

- `hermes skills tap add <owner/repo>` — add the repo as a skills source, then install from it.
- Drop the skill directories into `~/.hermes/skills/<category>/<skill>/`.
- Point `skills.external_dirs` in `~/.hermes/config.yaml` at the repo's `skills/` dir. [PIN: confirm the
  `skills.external_dirs` key against `hermes skills --help` / `docs/user-guide/configuration`.]

**Verify this branch on a real Hermes install:**

```
agent-data init --hermes --api-key <KEY> --yes && agent-data whoami     # api_key_set:true; gateway running
git clone -b feat/hermes-native-host https://github.com/agent-data/job-search && cd job-search
./scripts/build.sh                                                       # materialize synced refs + runtime
hermes skills tap add agent-data/job-search                             # or skills.external_dirs / copy into ~/.hermes/skills/
hermes skills install job-search                                        # [PIN: confirm tap add alone does not load the skill]
hermes chat -Q -s job-search-run -q "run a job search now"             # one-off
hermes cron create "0 9 * * *" "run a job search now" --skill job-search-run --deliver origin --name "Daily job search"
hermes cron list                                                        # confirm the job in ~/.hermes/cron/jobs.json
```
