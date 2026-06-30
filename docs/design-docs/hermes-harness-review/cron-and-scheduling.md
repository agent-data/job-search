---
title: Hermes Harness Review — Cron & Scheduling
status: current
verified: partial
last_reviewed: 2026-06-30
code_refs: [shared/references/platform/hermes.md, docs/design-docs/2026-06-30-hermes-job-search-concierge.md, docs/exec-plans/active/2026-06-30-hermes-concierge-layer.md, runtime/hermes_job_search/cli.py]
---
# Hermes Harness Review — Cron & Scheduling

> **Fact-check caveat.** A later verification pass overturned two claims below: `--no-agent` is a **real**
> registered flag (not "fabricated"), and `hermes_cli/subcommands/cron.py` + `docs/chronos-managed-cron-contract.md`
> **do exist** — so the adapter's cron citations stand. The doc's CLI-`edit`-vs-tool-`update` verb table is
> still its most valuable, confirmed contribution. Read the [Corrections log](overview.md#corrections-log) first.

One doc of the Hermes-agent harness review. It grounds Hermes's cron subsystem against what the
[concierge design](../2026-06-30-hermes-job-search-concierge.md) and its
[exec plan](../../exec-plans/active/2026-06-30-hermes-concierge-layer.md) assume about scheduling
and delivery, and reconciles both against the shipped
[Hermes adapter](../../../shared/references/platform/hermes.md). **In scope:** the `hermes cron`
CLI, the `cronjob` agent tool, the gateway tick loop, job persistence, fresh-session semantics, and
delivery routing — the surfaces the concierge's "offer automation" and "why didn't we alert" flows
ride on. **Out of scope:** the job-search runtime's own registry writes (a job-search concern, not a
Hermes one) and headless non-cron invocation, except where the latter touches the first-batch path.

Hermes literals are **source-cited** against `NousResearch/hermes-agent@main`; line numbers are
current at review time. Anything only a running Hermes can settle carries a **[PIN]**.

## What Hermes provides

### Two control surfaces — and they disagree on one verb

Hermes drives cron from two places, plus an interactive slash command. The lifecycle verbs are **not
spelled the same** across them, which is the single most error-prone fact here.

| Surface | Invoked by | Lifecycle verbs | "edit a job" verb |
|---|---|---|---|
| `hermes cron` CLI | a terminal / a shelled command | `list`, `create` (alias `add`), `edit`, `pause`, `resume`, `run`, `remove` (aliases `rm`/`delete`), `status`, `tick` | `edit` |
| `cronjob` agent tool | a model tool-call | `create`, `list`, `update`, `pause`, `resume`, `remove`, `run` (aliases `run_now`/`trigger`) | `update` |
| `/cron` chat command | interactive chat | `add`, `edit`, `list`, `pause`, `resume`, `run`, `remove` | `edit` |

The consequence: `hermes cron update <id>` is **not a command** — the CLI prints
`Unknown cron command`. Use `edit` at the CLI, `update` in the tool. (CLI dispatch:
[hermes_cli/cron.py](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/cron.py),
L262–299; argparse: [hermes_cli/main.py](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/main.py),
L8608–8715; tool actions: [tools/cronjob_tools.py](https://github.com/NousResearch/hermes-agent/blob/main/tools/cronjob_tools.py),
L271–448; `/cron`: [cli.py](https://github.com/NousResearch/hermes-agent/blob/main/cli.py), L5912–5995.)

### `hermes cron create` signature

Positional `<schedule>` (required) then positional `<prompt>` (optional, `nargs='?'`); flags
`--name`, `--deliver`, `--repeat`, `--skill` (repeatable; `dest=skills`), `--script`, `--workdir`.
There is **no `--skills` (plural)**, and **no `--model` / `--context-from` / `--enabled-toolsets`**
at the CLI — those exist only on the tool. ([main.py](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/main.py),
L8618–8646.) A marketing doc inside the Hermes tree (`hermes-already-has-routines.md`) shows
`--skills "arxiv,obsidian"`; that spelling is **wrong** for the real argparse — copy the repeatable
`--skill` instead.

### `cronjob` tool schema

Parameters: `action`, `job_id`, `prompt`, `schedule`, `name`, `repeat`, `deliver`, `skills` (array),
`model` (`{provider, model}`), `script`, `context_from` (array), `enabled_toolsets` (array),
`workdir`. There is **no `no_agent` parameter** anywhere in the schema or the repo.
([cronjob_tools.py](https://github.com/NousResearch/hermes-agent/blob/main/tools/cronjob_tools.py),
L474–552.)

### Schedule formats

`parse_schedule` accepts four shapes ([cron/jobs.py](https://github.com/NousResearch/hermes-agent/blob/main/cron/jobs.py),
L124–209):

| Shape | Example | `repeat` default |
|---|---|---|
| one-shot duration | `30m` / `2h` / `1d` | `1` |
| recurring interval | `every 30m` / `every 2h` / `every 1d` | forever |
| 5- or 6-field cron | `0 9 * * *` | forever |
| ISO timestamp | a one-shot absolute time | `1` |

`croniter` is a **core dependency** ([pyproject.toml](https://github.com/NousResearch/hermes-agent/blob/main/pyproject.toml),
L33–34), so cron expressions work on a stock install — the "requires croniter" `ValueError` in
`parse_schedule` is a defensive fallback that does not fire normally.

### The skip-the-model path is `--script`, not `--no-agent`

There is **no `--no-agent` flag** (zero repo hits). To skip the model on a tick, attach a pre-run
`--script` (a relative path under `~/.hermes/scripts/`) whose final stdout line emits
`{"wakeAgent": false}`; the default (no script, or `wakeAgent: true`) wakes the model.
([cron/scheduler.py](https://github.com/NousResearch/hermes-agent/blob/main/cron/scheduler.py),
L634–652, L820–837; [cronjob_tools.py](https://github.com/NousResearch/hermes-agent/blob/main/tools/cronjob_tools.py),
L174–210.)

### Persistence

- Jobs: `~/.hermes/cron/jobs.json`, written atomically (`mkstemp` + atomic replace).
- Per-run output: `~/.hermes/cron/output/<job_id>/<timestamp>.md`.
- Tick lock: `~/.hermes/cron/.tick.lock`, which prevents overlapping ticks.

([cron/jobs.py](https://github.com/NousResearch/hermes-agent/blob/main/cron/jobs.py), L37–38,
L373–380; [cron/scheduler.py](https://github.com/NousResearch/hermes-agent/blob/main/cron/scheduler.py),
L120–122.)

### The scheduler is the gateway, not a system crontab

The gateway process runs `_start_cron_ticker`, a background thread that calls `scheduler.tick()`
every **60s (default)** — it fires jobs without a separate daemon or a system cron entry. So **the
gateway must be running or nothing fires.** When it is not, `hermes cron list` and `hermes cron
status` warn that jobs will **not** fire and point at `hermes gateway install` /
`sudo hermes gateway install --system` / `hermes gateway` (foreground).
([gateway/run.py](https://github.com/NousResearch/hermes-agent/blob/main/gateway/run.py),
L13409–13436; [hermes_cli/cron.py](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/cron.py),
L116–147.)

### `run` is queued, not synchronous

`cronjob(action="run")` / `hermes cron run <id>` sets `next_run_at=now` so the job fires on the
**next tick (≤60s)**; the CLI prints "It will run on the next scheduler tick." It still needs the
gateway ticker (or a manual `hermes cron tick`). It is **not** an in-conversation, blocking
execution. ([cron/jobs.py](https://github.com/NousResearch/hermes-agent/blob/main/cron/jobs.py),
L650–662; [hermes_cli/cron.py](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/cron.py),
L255–258.)

### Fresh-session semantics

A scheduled run executes in a **fresh, isolated session with no current-chat context**, with
`disabled_toolsets = ['cronjob', 'messaging', 'clarify']`. So the run **cannot ask the user
anything** and **cannot recursively schedule more jobs** — the prompt must be self-contained.
([cron/scheduler.py](https://github.com/NousResearch/hermes-agent/blob/main/cron/scheduler.py),
L1045; [cronjob_tools.py](https://github.com/NousResearch/hermes-agent/blob/main/tools/cronjob_tools.py),
L465–471.)

### Delivery routing

`deliver` targets: `origin` (the chat the job was created from), `local` (no message; saved under
`~/.hermes/cron/output/` only), and platform forms (`telegram` / `telegram:chat_id` / `discord` /
`discord:#chan` / `slack` / `sms:+1…` / `signal` / `whatsapp` / `matrix` / `mattermost` / `email`).
The default is `origin` **if an origin was captured, else `local`**.
([cron/jobs.py](https://github.com/NousResearch/hermes-agent/blob/main/cron/jobs.py), L483–485;
[cron/scheduler.py](https://github.com/NousResearch/hermes-agent/blob/main/cron/scheduler.py),
L74–99, L150–233.)

Origin is captured **at create time only when `HERMES_SESSION_PLATFORM` and `HERMES_SESSION_CHAT_ID`
are set** in the session env — i.e., the job was created from inside a messaging/gateway chat. If
origin is missing (job created from a plain terminal / API / script), `--deliver origin` falls back
to the **first** platform whose `*_HOME_CHANNEL` env var is set; if none is set, it delivers
**nowhere** and only saves locally. ([cronjob_tools.py](https://github.com/NousResearch/hermes-agent/blob/main/tools/cronjob_tools.py),
L71–88; [cron/scheduler.py](https://github.com/NousResearch/hermes-agent/blob/main/cron/scheduler.py),
L158–180.)

### `[SILENT]` suppression and inspectable signals

If a run's final response starts with or contains `[SILENT]`, **delivery is suppressed** (the output
is still saved locally for audit). **Failed jobs always deliver** regardless of `[SILENT]`. So a
"nothing new" run can be silenced, but a real block must emit non-empty, non-`[SILENT]` text to be
delivered. ([cron/scheduler.py](https://github.com/NousResearch/hermes-agent/blob/main/cron/scheduler.py),
L115, L1341–1346.)

Per-job signals — `last_status`, `last_error`, `last_delivery_error`, `next_run_at`, `state`
(`scheduled` / `paused` / `completed`), `enabled` — are stored in `jobs.json` and rendered by
`hermes cron list`. They are the raw material for "why didn't it fire / why no alert" explanations.
([hermes_cli/cron.py](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/cron.py),
L100–112; [cronjob_tools.py](https://github.com/NousResearch/hermes-agent/blob/main/tools/cronjob_tools.py),
L213–243.)

## How the job-search adapter uses it

Reconciliation of the [Hermes adapter](../../../shared/references/platform/hermes.md) (Scheduling,
Run recipe, Block-alert channel) against the Hermes source. Verdicts: **CONFIRMS** /
**CONTRADICTS** / **UNCONFIRMED**.

| Adapter claim (hermes.md) | Verdict | Source check |
|---|---|---|
| Recipe `hermes cron create "<schedule>" "run a job search now" --skill job-search-run --deliver origin --name "Daily job search"` (L49, 235) | **CONFIRMS** | Every token matches argparse; `origin` is a documented `--deliver` value. |
| Tool form `cronjob(action="create", …, skills=["job-search-run"], deliver="origin", …)` (L67) | **CONFIRMS** | Matches the `cronjob` schema exactly. |
| Writes the job to `~/.hermes/cron/jobs.json` (L69, 236) | **CONFIRMS** | `JOBS_FILE`, atomic write. |
| Gateway ticks ~60s; must be running (L69) | **CONFIRMS** | `_start_cron_ticker(interval=60)`; status warns when the gateway PID is absent. |
| Cadence accepts cron / interval / duration / ISO (L70) | **CONFIRMS** | All four parse; croniter is core. |
| Lifecycle `create \| list \| update \| pause \| resume \| run \| remove` (L71) | **CONTRADICTS** (partial) | These are the **tool** action names (correct for the tool). At the **CLI** the verb is `edit`, not `update` — `hermes cron update <id>` → `Unknown cron command`. |
| Fresh, isolated session; cannot `clarify` (L74) | **CONFIRMS** | `clarify`, `cronjob`, `messaging` disabled in cron sessions. |
| Delivery "defaults to `origin` → the chat it was created from (else home channel)" (L74, 190–195) | **CONFIRMS** (caveat) | Origin→home-channel fallback is real; but `origin` is the default **only when origin was captured**. From a bare CLI the default is `local`. The recipe's explicit `--deliver origin` overrides the default, so shipped behavior is fine — but see §Implications for the capture caveat. |
| `--no-agent --script` cron path runs a script with no model (L79–80) | **CONTRADICTS** | No `--no-agent` flag exists. The skip-model mechanism is `--script` + the script emitting `{"wakeAgent": false}`. |
| Source citations: `cron/jobs.py`, `cron/scheduler.py`, `hermes_cli/subcommands/cron.py`, `docs/chronos-managed-cron-contract.md` (L76) | **CONTRADICTS** (half) | `jobs.py` + `scheduler.py` exist. `hermes_cli/subcommands/cron.py` does **not** (real: `hermes_cli/cron.py` + argparse in `hermes_cli/main.py`); `docs/chronos-managed-cron-contract.md` does **not** exist anywhere. |
| Turn off: `hermes cron remove <job_id>` (or `pause`) (L83) | **CONFIRMS** | Both are real CLI subcommands and tool actions. |
| Empty / `[SILENT]` final output suppresses delivery (L192) | **CONFIRMS** | Suppressed but saved locally; failed runs deliver regardless. |
| `set-scheduling` writes `mechanism` + `job_id` + `deliver` to the registry (L71–72) | **UNCONFIRMED** | A job-search runtime claim (see [runtime/hermes_job_search/cli.py](../../../runtime/hermes_job_search/cli.py)); not verifiable from the Hermes clone. |
| Headless `hermes chat -Q -s job-search-run -q …` flags + exit code (L59, 93) | **UNCONFIRMED** | Already **[PIN]**-tagged in the adapter; not verified against Hermes source. Bears on the first-batch path below. |

### Corrections the adapter needs

Three items are wrong on the page even though the **behavior** the concierge relies on is real — fix
them before downstream skills copy the errors:

1. **`update` vs `edit`.** The adapter presents the lifecycle verbs as belonging to "the `hermes
   cron` CLI **or** the `cronjob` tool," but the listed verbs are the **tool's**. Disambiguate:
   `update` (tool) / `edit` (CLI). A reader who types `hermes cron update` gets `Unknown cron
   command`.
2. **`--no-agent` is fabricated.** Replace it with the real `--script` + `{"wakeAgent": false}`
   mechanism. The adapter's *intent* — use `--skill job-search-run` so the model judges, and avoid
   the agentless path — is correct and should stand; only the flag name is invented.
3. **Two dead source citations.** Drop `hermes_cli/subcommands/cron.py` and
   `docs/chronos-managed-cron-contract.md`; cite `hermes_cli/cron.py`, `hermes_cli/main.py`,
   `cron/jobs.py`, `cron/scheduler.py`, and `tools/cronjob_tools.py` instead.

## Implications for the concierge layer

The cron behavior the [concierge design](../2026-06-30-hermes-job-search-concierge.md) leans on is
real; nothing here **blocks** the design. Two items need an **implementation** constraint, and the
adapter needs the corrections above.

| Concierge assumption | Verdict | Why |
|---|---|---|
| §10 "present a small cadence menu, recommend daily" | **SOUND** | Every menu entry has a valid Hermes token. |
| §11/§12 offer "here" as a destination, then "creates the job immediately" | **NEEDS-CHANGE (impl)** | "here" works only if the job is created **via the `cronjob` tool, in-session** — origin is captured from the session env at create time. |
| §7 "run the first batch manually … as calibration" | **NEEDS-CHANGE (impl)** | Must be a direct `job-search-run` invocation, **not** `hermes cron run` (which only queues for the next tick). |
| "why didn't we alert on X?" / a scheduled run that didn't fire | **SOUND** (strong fit) | Hermes exposes the exact signals needed to answer from stored state first. |
| §13 recurring delivery = "the digest-ready summary" + "lightweight analytics", simplifiable to "summary-only" | **SOUND** | Delivery is the agent's final response; format is a prompt choice, not a cron toggle. |
| Design treats the adapter as the Hermes source of truth | **WATCH** | The cron behavior is real, but the adapter's citations + `--no-agent` are wrong (see above). |

**Cadence menu (§10).** Map each menu entry to a Hermes-accepted token: hourly → `every 1h`, the
two-hour option → `every 2h`, six-hourly → `0 */6 * * *`, daily → `0 9 * * *`, weekly →
`0 9 * * 1`. croniter is core, so the cron-expression forms work out of the box. No blocker.

**"here" and "creates the job immediately" (§11/§12).** `here` resolves to `deliver="origin"`, and
**origin is captured only from `HERMES_SESSION_PLATFORM` / `HERMES_SESSION_CHAT_ID` at create time.**
So the concierge must create the recurring job by **calling the `cronjob` tool inside the live Hermes
chat** — where those env vars are set — **not** by shelling out the user-facing
`hermes cron create … --deliver origin` recipe. On the shelled path, if the terminal subprocess does
not inherit those vars (see Open questions), `origin` is not captured and "here" **silently
degrades** to a configured home channel, or to local-only if none is configured. The adapter's
verbatim CLI recipe is the *display* artifact for the user; the *create* action should be the tool
call.

**First batch (§7).** "run the first batch manually" must be a direct `job-search-run` invocation —
the headless `hermes chat -Q -s job-search-run …` path (flags **[PIN]**) — **not** `hermes cron
run`/`trigger`, which only flags the job to fire on the next gateway tick and needs the gateway up.
The design already treats §7 (manual calibration) and §10 (automation) as **distinct**, so the
design is sound; the implementer just must not wire "run first batch" through `cron run`.

**Explainability.** The conversational target "I saw X company posted a new job, but we didn't get
an alert — why not?" is a strong fit. Answer from stored state first, then live re-check. Name the
two most common Hermes-specific causes:

- *Didn't fire at all* → the **gateway was not running** (check `hermes cron status`), or the job is
  `paused`/`completed`/disabled, or `next_run_at` is still in the future.
- *Fired but no alert* → `[SILENT]` suppression (the run found nothing new; output is still saved
  under `~/.hermes/cron/output/<job_id>/`), **or** an origin-less `deliver="origin"` that fell back
  to `local` (`last_delivery_error` will show it).

**Delivery format (§13).** The cron pipeline auto-delivers the agent's **final response** (wrapped
with a "Cronjob Response" header unless `cron.wrap_response=false`). Whatever `job-search-run` emits
as its final response is what gets delivered, so "summary + analytics" vs "summary-only" is a
**prompt/format choice, not a cron-API toggle**. The scheduled prompt needs no explicit
`send_message` for the same target — the scheduler delivers the final response and de-dupes a
same-target `send_message`.

## Open questions / must-verify-live

Only a running Hermes from this branch can settle these:

- **[PIN] Does the `terminal` subprocess inherit `HERMES_SESSION_PLATFORM` / `HERMES_SESSION_CHAT_ID`?**
  This decides whether a shelled `hermes cron create … --deliver origin` captures origin (delivers
  back to the live chat) or degrades. It is the load-bearing question for the "here" path. Until it
  is answered, **create the recurring job via the `cronjob` tool**, which captures origin in-session
  regardless.
- **[PIN] Is the 60s tick interval configurable?** 60s is the default in `_start_cron_ticker`;
  user-configurability was not traced. It bounds the worst-case latency for `cron run` and "creates
  the job immediately."
- **[PIN] `hermes chat -Q -s job-search-run -q …` flags + exit-code semantics** for the first-batch
  path — not verified against Hermes source; the adapter already PIN-tags these.
- **Out of scope (job-search side):** whether `set-scheduling` writes `mechanism` / `job_id` /
  `deliver` to the registry — verify against
  [runtime/hermes_job_search/cli.py](../../../runtime/hermes_job_search/cli.py), not the Hermes
  clone.
- **Noted, not a problem:** a per-job model override exists only on the `cronjob` **tool** (a `model`
  object); there is no `--model` on `hermes cron create`. job-search's scheduled run uses tier
  `inherit` (emits no model), so this is a non-issue — but a writer adding a per-run model must use
  the tool, not the CLI.

To re-verify on a live Hermes, the real cron tests are `tests/cron/test_cron_script.py` (script /
`wakeAgent`), `tests/cron/test_jobs.py`, `tests/cron/test_scheduler.py`,
`tests/hermes_cli/test_cron.py`, and `tests/tools/test_cronjob_tools.py`. (The review brief named
`test_cronjob_schema.py`, `test_cron_no_agent.py`, `test_cron_parser_builder.py`, and
`test_cronjob_run_immediate.py` — none of those exist; do not look for them.)
