---
name: job-search-agent
description: The operator manual for the Job Search Agent — configure, customize, extend, or troubleshoot the agent itself, or explain how it works. Use when the user asks how the agent works, why a run failed, what it can do, or how to change its behavior — a query, the schedule, the recency window, the detail-read model: "how does my job search agent work", "why did the run fail", "how do I change/add/customize …", "change how often it runs". Not for daily use — onboarding, the home view, and running a search are job-search; the search pass itself is job-search-run.
disable-model-invocation: false
user-invocable: true
---

# Job Search Agent

You are working on the agent itself — configuring, extending, or troubleshooting it — not running a search. Daily use lives elsewhere: onboarding and the home view in **job-search**, the search pass in **job-search-run**. This manual holds the playbooks and guardrails for changing the system safely.

The system in one paragraph: a private, local-first job-search agent. It searches LinkedIn postings via agent-data, judges each one against the user's prose preferences brief, and writes digests to a workspace that never touches source control (`~/.job-search/` by default).

Hold these stances in every change you make — each exists for a reason, and several are CI-enforced:

- **Qualitative-by-default.** Relevance is expressed as relevant or not, and if relevant as weak / moderate / strong with plain-language reasoning. No score is computed or stored unless you explicitly ask — and even then a numeric score is never written into your saved digests, `jobs.jsonl`, or preferences brief.
- **Frequency-not-budget.** You tune the system in human terms (how often to pull: hourly, daily, weekly). Credits and per-call cost are never surfaced except reactively as the named error `E-QUOTA` when the API limit is actually hit.
- **Private-local.** All data lives under `~/.job-search/` (hidden, deny-all `.gitignore`). Nothing is ever committed to a public repo by the agent.
- **Every blocked path is a named error.** If anything can't proceed, the agent names the exact `E-*` with its cause and fix, then stops. No silent failures.
- **Conversational-first config.** You change anything — a query, the frequency, your preferences — by chatting. The agent edits `config.yaml` minimally and writes it back. Hand-editing files is an escape hatch you can always use, not a required step.

---

## The skills

| Skill | What it does | When to use it |
|---|---|---|
| `job-search` | Front door: onboarding on first run; home view (latest digest, new matches, pipeline) with quick actions on return | Daily use — set up, check in, run now, change anything |
| `job-search-run` | Headless scheduled pull: preflight → search → dedup → judge → persist → digest | Run by the `/loop` schedule, or manually for a fresh pull without the home view |
| `job-preference-interview` | Interactive interview that builds or refines the prose preferences brief | Whenever you want to update what you're looking for |
| `evaluate-job-fit` | Judge one posting against the current brief | When you paste a single job description and want a fit assessment |
| `job-search-agent` | This operator manual | Configure, extend, troubleshoot, or understand the agent itself |

---

## Quick reference (OS state)

There is no helper script — the OS state is plain files, and every operation on it is a pinned procedure in the bundled references. Never hard-code workspace paths; follow the procedure for each operation exactly as written.

| Operation | Pinned where |
|---|---|
| Find the active workspace + `first_run` + `source` | `references/internals.md` → Workspace discovery — the one correct way to find the workspace |
| Record the active workspace in the registry | `references/internals.md` → Registry write rules |
| Compose the `/loop` scheduling line for a frequency | `references/internals.md` → Scheduling setup (interval table; namespaced target for plugin installs — plugin skills are only invocable namespaced; bare for loose skills) |
| Read / set / clear the scheduling marker | `references/internals.md` → Registry (the `scheduling` object) |
| Known ids — the dedup set from `jobs.jsonl` | `references/conventions.md` → §jobs.jsonl operations |
| Append one evaluated or status-changed event | `references/conventions.md` → §jobs.jsonl operations |
| Current state (fold by `source_id`, last-write-wins) | `references/conventions.md` → §jobs.jsonl operations |

---

## Configuring it (conversational)

The user changes configuration by chatting — you apply it by reading `config.yaml`, editing it minimally (preserving comments and structure), and writing it back.

For every supported edit — adding, editing, or pausing a query (`enabled: false`); the `search` block (`freshness`, `detail_model`, `queries[].limit`); `schedule.frequency`/`time`; the never-clobber adoption rule; and exact field schemas — see `references/internals.md` → "Config read/update recipes". Marking a job status (`new | interested | applied | rejected | archived`) is a `status_changed` event appended to `jobs.jsonl` (the append operation in `references/conventions.md` → §jobs.jsonl), not a `config.yaml` edit. To update the brief itself, run `job-preference-interview` or edit `preferences.md` directly.

**Invariants — never break these:**
- Always preserve `version: 1` in `config.yaml`.
- Always preserve existing comments and structure when editing.
- Never add a `budget`, `cost`, `score`, or `weight` field anywhere.

---

## Customizing & extending it

The agent is designed to be extended — add queries, swap the brief, point the runner at a different workspace, or build new skills that slot into the same conventions. For the full flexibility workflows — including how to honor an explicit score or cost-math request without polluting the clean data — see `references/customization.md`.

**Run architecture.** Each run scans new posting summaries in the primary context (cheaply rejecting clear dealbreakers), then fans out one detail-read subagent per promising posting in parallel (model = `search.detail_model`, each follows the `evaluate-job-fit` skill), then consolidates and validates all verdicts before persisting. See `references/parallelism.md` for the parallel-by-default principle and how to brief a subagent; see `references/customization.md` for the recency, model, and feed-size knobs.

---

## Scheduling

Scheduling is Claude Code's native **`/loop`** — the only mechanism the agent sets up.
`/loop <interval> /job-search-os:job-search-run` (plugin installs; loose skills drop the `job-search-os:`
prefix) re-runs the search on an interval inside an open Claude session; nothing is installed on the user's
machine (no crontab, no launchd). Compose the line from the interval table in `references/internals.md` →
Scheduling setup, run it, and set the scheduling marker. The one tradeoff: it runs only while a Claude
session is open. The agent never initiates a crontab/launchd install itself; the user remains free to set
one up in their own shell — see `references/scheduling-and-consent.md`.

---

## When something fails

The run's outcome is the `run_health` field in `runs/<id>.json` and the digest header — one of `healthy | partial (N errors) | degraded (LinkedIn flaky) | blocked (action needed)`. For what each state means and when it's written, see `references/errors.md` (the four states and the surfacing story) and `references/conventions.md` → the digest "Run health" line. One meaning lives with the runner instead: a `degraded` run still reads promising matches in full — no detail-read cap, relevance decides (see **job-search-run**).

**How failures surface:** a blocked run writes three artifacts — a `runs/<id>.json` record with `run_health:"blocked"`, a `reports/<date>-digest.md` whose body is the named error + fix, and (if `notify.desktop_notify_on_block: true`) a desktop notification. The **home view** the next time you open the **job-search** skill reads `runs/<id>.json` and shows the error there. Do not rely on the process exit code — a headless `claude -p` run returns 0 even when blocked.

For the full `E-*` table with exact cause and fix wording: see `references/errors.md`.

**Symptom → fix quick lookup:**

| Symptom | Likely cause | Fix |
|---|---|---|
| Runs complete but 0 matches even though real postings exist | Query keywords don't match the brief's must-haves | Broaden the query in `config.yaml`, or run the **job-preference-interview** skill to align the brief |
| 0 results (literally empty) | Keywords too narrow or location too specific | Broaden `keywords` or `location` in the query |
| Last run: blocked — E-QUOTA | API limit reached for the period | Lower `schedule.frequency` (e.g. `daily` instead of `hourly`), or upgrade your plan at agent-data.motie.dev |
| Schedule isn't firing | The `/loop` isn't running (its Claude session closed) | Check the scheduling marker in the registry (`references/internals.md`); restart it with the `/loop` line from the interval table (namespaced `/job-search-os:job-search-run` for plugin installs) |
| "Stale brief" nudge in the digest | `preferences.md` hasn't been updated in a long time | Run the **job-preference-interview** skill to refresh it |

---

## Where to find things

| Looking for... | Go to |
|---|---|
| Workspace layout and `config.yaml` schema | `references/conventions.md` |
| Every `E-*` error with cause + fix | `references/errors.md` |
| OS registry, workspace discovery, config recipes, scheduling | `references/internals.md` |
| agent-data CLI contract (routes, retry rules, listing ID) | `references/agent-data-contract.md` |
| The active workspace path | the Discovery procedure — `references/internals.md` |
| Scheduling status | the registry's scheduling marker — `references/internals.md` |
| Customization and flexibility workflows | `references/customization.md` |
| Parallel-by-default principle + how to brief a subagent | `references/parallelism.md` |
| How skills talk to the user (voice, banned jargon, rendering briefs/digests) | `references/voice.md` |
| Scheduling consent workflow | `references/scheduling-and-consent.md` |
| This operator manual | `job-search-agent` skill |

---

## Extending & contributing

**Single source of truth.** Shared references live in `shared/references/*.md`. Skills bundle their own copies — but those copies are generated, not authored. After editing a shared reference, run `./scripts/build.sh` to re-sync every skill's bundled copies. Never hand-edit files under `skills/<skill>/references/` — the next build will overwrite them silently.

**Adding a new skill.** Create a folder under `skills/<skill>/` with a `SKILL.md` and an `evals/evals.json`. Run `./scripts/build.sh` to sync the shared refs into the new skill. Write evals that cover the happy path and the named-error HALT paths.

**Evals are credit-free.** Evals run through the fake `agent-data` shim in `tests/` — no metered API calls, nothing billed. When you add a code path that calls `agent-data`, route the eval through the shim rather than the live CLI.

**Philosophy guard.** The repo's CI runs a philosophy guard that rejects any file introducing numeric scores, budget/cost/credit fields, or score-threshold config into the shipped default output (`examples/`, `templates/`). Keep the guard green before opening a PR (exact commands in `CONTRIBUTING.md`).

**Versioning.** `config.yaml` carries `version: 1`. If a breaking schema change is needed, bump the major version and add the corresponding `E-CONFIG-VERSION` detection to the runner's preflight.

**Full contributor guide:** `CONTRIBUTING.md`.
