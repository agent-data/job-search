---
name: job-search-agent
description: The operator manual for the Job Search Agent — configure, customize, extend, or troubleshoot the agent itself, or explain how it works. Use when the user asks how the agent works, why a run failed, what it can do, or how to change its behavior — a query, the schedule, the recency window, the detail-read model, parallel detail reads — "how does my job search agent work", "why did the run fail", "how do I change/add/customize …", "change how often it runs". Not for daily use — onboarding, the home view, and running a search are job-search; the search pass itself is job-search-run.
disable-model-invocation: false
user-invocable: true
---

# Job Search Agent

You are working on the agent itself — configuring, extending, or troubleshooting it — not running a search. Daily use lives elsewhere: onboarding and the home view in **job-search**, the search pass in **job-search-run**. This manual holds the playbooks and guardrails for changing the system safely.

The system in one paragraph: a private, local-first job-search agent. It searches LinkedIn postings via agent-data, judges each one against the user's prose preferences brief, and writes digests to a workspace that never touches source control (`~/.job-search/` by default).

Hold these stances in every change you make — each exists for a reason, and several are CI-enforced:

- **Qualitative-by-default.** Relevance is expressed as relevant or not, and if relevant as weak / moderate / strong with plain-language reasoning. No score is computed or stored unless you explicitly ask — and even then a numeric score is never written into your saved digests, `jobs.jsonl`, or preferences brief.
- **Frequency, in human terms.** You tune the system by how often to pull: hourly, daily, weekly.
- **Private-local.** All data lives under `~/.job-search/` (hidden, deny-all `.gitignore`). Nothing is ever committed to a public repo by the agent.
- **Every blocked path is a named error.** If anything can't proceed, the agent names the exact `E-*` with its cause and fix, then stops. No silent failures.
- **Conversational-first config.** You change anything — a query, the frequency, your preferences — by chatting. The agent edits `config.yaml` minimally and writes it back. Hand-editing files is an escape hatch you can always use, not a required step.

---

## The skills

| Skill | What it does | When to use it |
|---|---|---|
| `job-search` | Front door: onboarding on first run; home view (latest digest, new matches, pipeline) with quick actions on return | Daily use — set up, check in, run now, change anything |
| `job-search-run` | Headless scheduled pull: preflight → search → dedup → judge → persist → digest | Run by the active schedule, or manually for a fresh pull without the home view |
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
| Compose the scheduling run recipe for a frequency | your platform's adapter → Run recipe (interval table and verbatim run recipe; namespaced target for plugin installs — plugin skills are only invocable namespaced; bare for loose skills) |
| Read / set / clear the scheduling marker | `references/internals.md` → Registry (the `scheduling` object) |
| Known ids — the dedup set from `jobs.jsonl` | `references/conventions.md` → §jobs.jsonl operations |
| Append one evaluated or status-changed event | `references/conventions.md` → §jobs.jsonl operations |
| Current state (fold by `source_id`, last-write-wins) | `references/conventions.md` → §jobs.jsonl operations |

---

## Configuring it (conversational)

The user changes configuration by chatting — you apply it by reading `config.yaml`, editing it minimally (preserving comments and structure), and writing it back.

For every supported edit — adding, editing, or pausing a query (`enabled: false`); the `search` block (`freshness`, `detail_model`, `parallel_detail_reads`, `queries[].limit`); `schedule.frequency`/`time`; the never-clobber adoption rule; and exact field schemas — see `references/internals.md` → "Config read/update recipes". Marking a job status (`new | interested | applied | rejected | archived`) is a `status_changed` event appended to `jobs.jsonl` (the append operation in `references/conventions.md` → §jobs.jsonl), not a `config.yaml` edit. To update the brief itself, run `job-preference-interview` or edit `preferences.md` directly.

**Invariants — never break these:**
- Always preserve `version: 1` in `config.yaml`.
- Always preserve existing comments and structure when editing.
- Never add a `score` or `weight` field anywhere.

---

## Customizing & extending it

The agent is designed to be extended — add queries, swap the brief, point the runner at a different workspace, or build new skills that slot into the same conventions. For the full flexibility workflows — including how to honor an explicit score request without polluting the clean data — see `references/customization.md`.

**Run architecture.** Each run scans new posting summaries in the primary context (cheaply rejecting clear dealbreakers), then reads each promising posting in full — by default fanning out one detail-read subagent per posting as a concurrent batch where capacity allows (model = `search.detail_model`, each follows the `evaluate-job-fit` skill). `search.parallel_detail_reads` resolves the mode against your platform's adapter → Concurrent detail reads: `false` reads sequentially, `true` fans out, and unset takes the adapter's default — hosts that gate subagents behind user approval (e.g. Codex) read sequentially until approved, every other host keeps the parallel fan-out. When the host applies a thread limit it continues in rolling batches; when it refuses or no slot is available it reads sequentially and still evaluates every queued posting. The concurrent dispatch primitive and mandatory sequential fallback live in your platform's adapter → Concurrent detail reads. See `references/parallelism.md` for the parallel-by-default principle and how to brief a subagent; see `references/customization.md` for the recency, model, parallel-approval, and feed-size knobs.

---

## Scheduling

The scheduling **mechanism** lives in your platform's adapter → Scheduling; the **actions** below are the same on every host. The model is **two-tier** — use whichever applies to the active host:

- **Tier 1 — native local scheduler (preferred).** Where the host has one (see your adapter → Scheduling), use it: it runs where it can see the local `~/.job-search` workspace and the local agent-data auth, and **installs nothing on the user's machine** (no crontab, no launchd, no privileged write). The exact recipe lives in the adapter — do not spell it here.
- **Tier 2 — no native local scheduler.** A **consent-gated** machine-level cron/launchd schedule is the sanctioned fallback — written **only on an explicit user yes, with the exact line shown before it is written**, never silent, never auto-installed, and user-removable.
- **Cloud schedulers do not qualify** — a cloud agent can't see the local workspace or the agent-data auth, so a run there reaches neither the user's data nor their credentials and produces nothing.

A given host sits on **whichever tier its adapter names** — a Tier-1-only host never reaches for the Tier-2 fallback. Read the adapter to learn which applies.

To start scheduling: offer it as a yes/no (check the scheduling marker first — never re-ask if already set); compose the run recipe from your adapter → Run recipe; start it on an affirmative answer; set the scheduling marker. To turn scheduling off: stop the active schedule (see your adapter → Scheduling for the teardown), then clear the scheduling marker. Always show the user the verbatim run recipe **from your adapter → Run recipe** — copy it exactly as written; do not reconstruct those tokens.

For the full consent workflow — including what to do when the user explicitly asks for cron or launchd — see `references/scheduling-and-consent.md`.

---

## When something fails

The run's outcome is the `run_health` field in `runs/<id>.json` and the digest header — one of `healthy | partial (N errors) | degraded (LinkedIn flaky) | blocked (action needed)`. For what each state means and when it's written, see `references/errors.md` (the four states and the surfacing story) and `references/conventions.md` → the digest "Run health" line. One meaning lives with the runner instead: a `degraded` run still reads promising matches in full — no detail-read cap, relevance decides (see **job-search-run**).

**How failures surface:** a blocked run writes two durable artifacts — a `runs/<id>.json` record with `run_health:"blocked"`, and a `reports/<date>-digest.md` whose body is the named error + fix. The **home view** the next time you open the **job-search** skill reads `runs/<id>.json` and shows the error there. An attention-pull alert (if `notify.desktop_notify_on_block: true`) is capability-gated — see your platform's adapter → Block-alert channel. **The written record is the primary signal on every harness** — whether the host's exit code is also trustworthy is per-harness; see your adapter → Headless invocation.

For the full `E-*` table with exact cause and fix wording: see `references/errors.md`.

**Symptom → fix quick lookup:**

| Symptom | Likely cause | Fix |
|---|---|---|
| Runs complete but 0 matches even though real postings exist | Query keywords don't match the brief's must-haves | Broaden the query in `config.yaml`, or run the **job-preference-interview** skill to align the brief |
| 0 results (literally empty) | Keywords too narrow or location too specific | Broaden `keywords` or `location` in the query |
| Last run: blocked — E-QUOTA | API limit reached for the period | Lower `schedule.frequency` (e.g. `daily` instead of `hourly`), or upgrade your plan at agent-data.motie.dev |
| Schedule isn't firing | The active schedule stopped (e.g. the host session closed) | Check the scheduling marker in the registry (`references/internals.md`); restart it with the run recipe from your platform's adapter → Run recipe (namespaced for plugin installs) |
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

**Evals use the fake shim.** Evals run through the fake `agent-data` shim in `tests/`, not the live CLI. When you add a code path that calls `agent-data`, route its eval through the shim.

**Philosophy guard.** The repo's CI runs a philosophy guard that rejects any file introducing numeric scores or score-threshold config into the shipped default output (`examples/`, `templates/`). Keep the guard green before opening a PR (exact commands in `CONTRIBUTING.md`).

**Versioning.** `config.yaml` carries `version: 1`. If a breaking schema change is needed, bump the major version and add the corresponding `E-CONFIG-VERSION` detection to the runner's preflight.

**Full contributor guide:** `CONTRIBUTING.md`.
