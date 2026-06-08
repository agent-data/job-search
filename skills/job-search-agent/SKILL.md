---
name: job-search-agent
description: The operator manual for the Job Search Agent — reach for this to CONFIGURE, set up, use, EXTEND, customize, or TROUBLESHOOT the agent itself, or to understand its features and capabilities. Use for "how does my job search agent work", "how do I change/add/customize …", "why did the run fail", "what can it do", or any change to how the agent behaves. (For daily use — onboarding, the home view, running a search — use job-search.)
disable-model-invocation: false
user-invocable: true
version: 0.1.0
metadata:
  tags: [job-search, configuration, customization, scheduling, troubleshooting, extension]
  homepage: https://github.com/agent-data/job-search-os
  related_skills: [job-search, job-search-run, job-preference-interview, evaluate-job-fit]
---

# Job Search Agent

Job Search OS turns Claude Code into a private, local-first job-search agent that runs entirely on your machine. It searches LinkedIn job postings via the agent-data marketplace, judges each match against your prose preferences brief, and writes human-readable digests to a private workspace that never touches source control.

Core philosophy:

- **Qualitative-by-default.** Relevance is expressed as relevant or not, and if relevant as weak / moderate / strong with plain-language reasoning. No score is computed or stored unless you explicitly ask — and even then a numeric score is never written into your saved digests, `jobs.jsonl`, or preferences brief.
- **Frequency-not-budget.** You tune the system in human terms (how often to pull: hourly, daily, weekly). Credits and per-call cost are never surfaced except reactively as the named error `E-QUOTA` when the API limit is actually hit.
- **Private-local.** All data lives under `~/.job-search/` (hidden, deny-all `.gitignore`). Nothing is ever committed to a public repo by the agent.
- **Every blocked path is a named error.** If anything can't proceed, the agent names the exact `E-*` with its cause and fix, then stops. No silent failures.
- **Conversational-first config.** You change anything — a query, the frequency, your preferences — by chatting. The agent edits `config.yaml` minimally and writes it back. Hand-editing files is an escape hatch you can always use, not a required step.

*This skill is what you (Claude) reach for to configure, extend, or troubleshoot the agent — the playbooks and guardrails live here.*

---

## The skills

| Skill | What it does | When to use it |
|---|---|---|
| `job-search` | Front door: onboarding on first run; home view (latest digest, new matches, pipeline) with quick actions on return | Daily use — set up, check in, run now, change anything |
| `job-search-run` | Headless scheduled pull: preflight → search → dedup → judge → persist → digest | Called by cron / launchd / `/loop`; also manually when you want a fresh pull without the home view |
| `job-preference-interview` | Interactive interview that builds or refines the prose preferences brief | Whenever you want to update what you're looking for |
| `evaluate-job-fit` | Judge one posting against the current brief | When you paste a single job description and want a fit assessment |
| `job-search-agent` | This operator manual | Configure, extend, troubleshoot, or understand the agent itself |

---

## Quick reference (deterministic core)

The deterministic OS state lives in `scripts/osctl.py` (bundled into each skill). Resolve its absolute path from the skill's own directory — never assume cwd, never hard-code workspace paths. Always use `osctl resolve`.

**`osctl.py` subcommands:**

| Subcommand | What it does |
|---|---|
| `resolve` | Print active workspace, `first_run`, and `source` as JSON — the one correct way to find the workspace |
| `set-active --workspace P` | Write the active workspace path to the registry |
| `loop-command --frequency F` | Emit `/loop <interval> /job-search-run` for a given frequency |
| `schedule-status` | Print the scheduling marker (installed mechanism) as JSON |
| `set-scheduled [--mechanism loop]` | Record that a `/loop` schedule is running |
| `set-unscheduled` | Clear the scheduling marker when turning scheduling off |

**`state.py` subcommands:**

| Subcommand | What it does |
|---|---|
| `known-ids --jobs <path>` | Print one `source_id` per line — the dedup set |
| `append --jobs <path> --event '<json>'` | Append one evaluated or status-changed event |
| `fold --jobs <path>` | Print current state as a JSON array (folded by `source_id`, last-write-wins) |

---

## Configuring it (conversational)

The user changes configuration by chatting — you apply it by reading `config.yaml`, editing it minimally (preserving comments and structure), and writing it back. Common recipes:

| What to change | How |
|---|---|
| Add a search query | Append an item to `queries:` with `id`, `keywords`, `location`, `limit`, `enabled: true` |
| Edit or remove a query | Find the item by `id`, update its fields or set `enabled: false` / remove the item |
| Change search frequency | Set `schedule.frequency` to one of `hourly \| every-2-hours \| every-6-hours \| daily \| weekly` |
| Mark a job status | Write a `status_changed` event via `state.py append` (statuses: `new \| interested \| applied \| rejected \| archived`) |
| Update preferences | Run `job-preference-interview` (interactive) or edit `preferences.md` directly |

For the exact edit rules, field schemas, and the never-clobber adoption rule: see `references/internals.md`.

**Invariants — never break these:**
- Always preserve `version: 1` in `config.yaml`.
- Always preserve existing comments and structure when editing.
- Never add a `budget`, `cost`, `score`, or `weight` field anywhere.

---

## Customizing & extending it

The agent is designed to be extended — add queries, swap the brief, point the runner at a different workspace, or build new skills that slot into the same conventions. For the full flexibility workflows — including how to honor an explicit score or cost-math request without polluting the clean data — see `references/customization.md`.

---

## Scheduling

Scheduling is Claude Code's native **`/loop`** — the only mechanism. `/loop <interval> /job-search-run`
re-runs the search on an interval inside an open Claude session; nothing is installed on the user's machine
(no crontab, no launchd). Get the line with `osctl loop-command --frequency <f>`, run it, and record it with
`osctl set-scheduled`. The one tradeoff: it runs only while a Claude session is open.

A `PreToolUse` safety-net hook **denies** any model-initiated crontab/launchd install (and ignores reads,
removals, `/loop`, and mere mentions) — see `references/scheduling-and-consent.md`.

---

## When something fails

**Run health states** (the `run_health` field in `runs/<id>.json` and the digest header):

| State | Meaning |
|---|---|
| `healthy` | All searches ran, all details attempted |
| `partial (N)` | N query-level errors but the run completed |
| `degraded (LinkedIn flaky)` | The status probe returned `degraded`; detail reads were capped |
| `blocked (action needed)` | A named `E-*` halted the run; action required before the next run succeeds |

**How failures surface:** a blocked run writes three artifacts — a `runs/<id>.json` record with `run_health:"blocked"`, a `reports/<date>-digest.md` whose body is the named error + fix, and (if `notify.desktop_notify_on_block: true`) a desktop notification. The **home view** on your next `/job-search` reads `runs/<id>.json` and shows the error there. Do not rely on the process exit code — a headless `claude -p` run returns 0 even when blocked.

For the full `E-*` table with exact cause and fix wording: see `references/errors.md`.

**Symptom → fix quick lookup:**

| Symptom | Likely cause | Fix |
|---|---|---|
| Runs complete but 0 matches even though real postings exist | Query keywords don't match the brief's must-haves | Broaden the query in `config.yaml`, or run `/job-preference-interview` to align the brief |
| 0 results (literally empty) | Keywords too narrow or location too specific | Broaden `keywords` or `location` in the query |
| Last run: blocked — E-QUOTA | API limit reached for the period | Lower `schedule.frequency` (e.g. `daily` instead of `hourly`), or upgrade your plan at agent-data.motie.dev |
| Schedule isn't firing | The `/loop` isn't running (its Claude session closed) | Run `python3 "$OS" schedule-status`; restart it with `/loop <interval> /job-search-run` |
| "Stale brief" nudge in the digest | `preferences.md` hasn't been updated in a long time | Run `/job-preference-interview` to refresh it |

---

## Where to find things

| Looking for... | Go to |
|---|---|
| Workspace layout and `config.yaml` schema | `references/conventions.md` |
| Every `E-*` error with cause + fix | `references/errors.md` |
| OS registry, workspace discovery, config recipes, scheduling | `references/internals.md` |
| agent-data CLI contract (routes, retry rules, listing ID) | `references/agent-data-contract.md` |
| The active workspace path | `python3 "$OS" resolve` |
| Scheduling status | `python3 "$OS" schedule-status` |
| Customization and flexibility workflows | `references/customization.md` |
| Scheduling consent workflow and hook behavior | `references/scheduling-and-consent.md` |
| This operator manual | `job-search-agent` skill |

---

## Extending & contributing

**Single source of truth.** Shared references live in `shared/references/*.md`; helper scripts live in `scripts/`. Skills bundle their own copies — but those copies are generated, not authored. After editing a shared reference or script, run `./scripts/build.sh` to re-sync every skill's bundled copies. Never hand-edit files under `skills/<skill>/references/` or `skills/<skill>/scripts/` — the next build will overwrite them silently.

**Adding a new skill.** Create a folder under `skills/<skill>/` with a `SKILL.md` and an `evals/evals.json`. Run `./scripts/build.sh` to sync the shared refs and scripts into the new skill. Write evals that cover the happy path and the named-error HALT paths.

**Evals are credit-free.** Evals run through the fake `agent-data` shim in `tests/` — no metered API calls, nothing billed. When you add a code path that calls `agent-data`, route the eval through the shim rather than the live CLI.

**Philosophy guard.** `scripts/philosophy_guard.py` runs in CI (`python3 scripts/philosophy_guard.py`) and rejects any file that introduces numeric scores, budget/cost/credit fields, or score-threshold config into the shipped default output (`examples/`, `templates/`). Keep the guard green before opening a PR.

**Versioning.** `config.yaml` carries `version: 1`. If a breaking schema change is needed, bump the major version and add the corresponding `E-CONFIG-VERSION` detection to the runner's preflight.

**Full contributor guide:** `CONTRIBUTING.md`.
