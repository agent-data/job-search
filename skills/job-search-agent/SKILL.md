---
name: job-search-agent
description: The operator manual for the Job Search Agent — configure, customize, extend, or troubleshoot the agent itself, or explain how it works. Use when the user asks how the agent works, why a run failed, what it can do, or how to change its behavior — a query, schedule, recency, review depth, usage, detail-read model, or parallel reads — "how does my job search agent work", "explain my agent-data usage", "why did the run fail", "how do I change/add/customize …", "change how often it runs". Not for daily use — onboarding, the home view, and running a search are job-search; the search pass itself is job-search-run.
---

# Job Search Agent

You are working on the agent itself — configuring, extending, or troubleshooting it — not running a search. Daily use lives elsewhere: onboarding and the home view in **job-search**, the search pass in **job-search-run**. This manual holds the playbooks and guardrails for changing the system safely.

The system in one paragraph: a private, local-first job-search agent. It searches LinkedIn, Ashby, Greenhouse, and Lever company-board postings via agent-data, judges each one against the user's prose preferences brief, and writes digests to a workspace that never touches source control (`~/.job-search/` by default).

Hold these stances in every change you make — each exists for a reason, and several are CI-enforced:

- **Qualitative-by-default.** Relevance is expressed as relevant or not, and if relevant as weak / moderate / strong with plain-language reasoning. No score is computed or stored unless you explicitly ask — and even then a numeric score is never written into your saved digests, `jobs.jsonl`, or preferences brief.
- **Usage context, not budget controls.** The user controls outcomes—frequency, sources, and review depth—and
  gets the applicable decision-time context from the canonical
  [Agent-data usage decisions](../../shared/references/internals.md#agent-data-usage-decisions) plus
  calls-first actual usage afterward. Actual usage comes from completed, producer-authoritative attempt
  metering, including failures/retries under the dated contract without double counting diagnostics. An
  optional dollar equivalent follows calls, is labeled a pay-as-you-go equivalent, and is never described
  as an actual charge. User-facing rendering lives in `../../shared/references/voice.md`.
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

The OS state is plain files, and every operation on it is a pinned procedure in the bundled references. Never hard-code workspace paths; follow the procedure for each operation exactly as written.

| Operation | Pinned where |
|---|---|
| Find the active workspace + `first_run` + `source` | `../../shared/references/internals.md` → Workspace discovery — the one correct way to find the workspace |
| Record the active workspace in the registry | `../../shared/references/internals.md` → Registry write rules |
| Compose the scheduling run recipe for a frequency | `../../shared/references/internals.md` → Scheduling setup (compose the cadence; the host composes its own run recipe) |
| Check scheduler eligibility (six gates) + select native/OS/none | `../../shared/references/internals.md` → Scheduling setup (eligibility gates + selection); doctrine in `references/scheduling-and-consent.md` |
| Read / stage / set (post-canary) / clear the scheduling marker | `../../shared/references/internals.md` → Registry (the `scheduling` object + state machine) |
| Repair an unavailable/refused exact primary or detail model | `../../shared/references/internals.md` → Exact-model repair; user rendering in `../../shared/references/errors.md` → model-repair-rendering |
| Known ids — the dedup set from `jobs.jsonl` | `../../shared/references/conventions.md` → §jobs.jsonl operations |
| Append one evaluated or status-changed event | `../../shared/references/conventions.md` → §jobs.jsonl operations |
| Current state (fold by (`source`, `source_id`), last-write-wins; alias pairs count as one role) | `../../shared/references/conventions.md` → §jobs.jsonl operations |
| Read or change one-off/saved review depth (`max_new_postings_per_run`) | `../../shared/references/internals.md` → Config read/update recipes; `references/customization.md` → Review depth |
| Explain recent agent-data usage without changing state | `references/customization.md` → Explaining agent-data usage; run fields in `../../shared/references/conventions.md` |
| Read or write the one-time deeper-coverage marker | `../../shared/references/internals.md` → Registry write rules |

Any operation that surfaces, explains, activates, or verifies a run first applies
`../../shared/references/run-lifecycle.md` → **Artifact authority for every reader**: invoke
`lifecycle-fold.sh` for the candidate's exact run_id, require `closed=true` and matching record state, and
use only its fold-derived digest. An open intended-complete artifact is not terminal evidence and cannot
verify a canary or schedule.

---

## Configuring it (conversational)

The user changes configuration by chatting — you apply it by reading `config.yaml`, editing it minimally (preserving comments and structure), and writing it back.

For every supported edit — adding, editing, or pausing a query (`enabled: false`); the `search` block
(`sources`, `freshness`, `detail_model`, `parallel_detail_reads`, `max_new_postings_per_run`, and
`queries[].limit`); `schedule.frequency`/`time`; the never-clobber adoption rule; and exact field schemas —
see `../../shared/references/internals.md` → "Config read/update recipes". Review-depth increases require
the action classification in
[Agent-data usage decisions](../../shared/references/internals.md#agent-data-usage-decisions) and the shared
rendering in `../../shared/references/voice.md`; `references/customization.md` applies both to every outcome
lever. Persistent increases get the structured before/after preview and one scoped confirmation before the
write. A one-off request is scoped consent after context. Neutral/decreasing edits apply immediately and
quietly; scheduled/headless runs consume durable saved consent without prompting. “Explain my agent-data
usage” is read-only: follow the same reference and leave config and registry state untouched. Marking a job
status (`new | interested | applied | rejected | archived`) is a `status_changed` event appended to
`jobs.jsonl` (the append operation in
`../../shared/references/conventions.md` → §jobs.jsonl), not a `config.yaml` edit. To update the brief itself,
run `job-preference-interview` or edit `preferences.md` directly.

**Invariants — never break these:**
- Preserve the existing config major on ordinary edits. New workspaces use config `version: 2`; never
  migrate a version-1 workspace incidentally. Every supported version-2 config write refreshes the canonical
  private detail-model binding sidecar per `internals.md`.
- Always preserve existing comments and structure when editing.
- Never add a `score` or `weight` field anywhere.
- Never add `budget`, `credits`, or `cost` config fields. Accurate calls-first usage and a clearly labeled
  pay-as-you-go equivalent are context, not a monetary control or an account-balance claim.

---

## Job sources

Searches run against the sources listed in `config.yaml` `search.sources` (see
`../../shared/references/conventions.md`; absent means the default pair). What each source is, honestly:

- **linkedin** — LinkedIn job search, fetched live (slow, seconds per query). Posting links go
  to LinkedIn; LinkedIn withholds the direct application URL.
- **ashby** — a broad crawl of public Ashby company boards, served from an index (fast).
  Board links ARE the live apply pages. The service supplies a `published_at` for most Ashby rows, so they carry a real date; a rare
  still-undated match carries "date not stated" (or a date read out of the posting text) rather than being hidden.
- **greenhouse** — a crawl of public Greenhouse company boards, served from a service-refreshed
  store (fast). Board links ARE the live apply pages. Postings carry real dates, so freshness
  filters normally.
- **lever** — a crawl of public Lever company boards, served from a store (fast). Board links ARE
  the live apply pages. Postings carry real dates; some list salary as embedded HTML (shown as
  plain text, never parsed for numbers).

To disable a source, set the list without it (e.g. `search.sources: ["linkedin"]`). Per-query
source targeting ("search only Ashby for this query") is a known deferred knob — today every
query runs against every enabled source. Source-related failures are named errors:
E-SOURCE-UNSUPPORTED and E-SOURCE-IGNORED in `../../shared/references/errors.md`.

---

## Customizing & extending it

The agent is designed to be extended — add queries, swap the brief, point the runner at a different workspace, or build new skills that slot into the same conventions. For the full flexibility workflows — including review depth, usage explanations, and how to honor an explicit score request without polluting the clean data — see `references/customization.md`.

**Run architecture.** Each run scans new posting summaries in the primary context (cheaply rejecting clear dealbreakers), then reads each promising posting in full — by default fanning out one detail-read subagent per posting as a concurrent batch where capacity allows (model = `search.detail_model`, each follows the `evaluate-job-fit` skill). `search.parallel_detail_reads` resolves the mode: `false` reads sequentially, `true` fans out, and unset takes your host's default — a host that gates subagents behind user approval reads sequentially until approved, every other host keeps the parallel fan-out. When the host applies a thread limit it continues in rolling batches; when it refuses or no slot is available it reads sequentially and still evaluates every queued posting. The concurrent dispatch uses your host's own subagent primitive, with the mandatory sequential fallback where it has none. See `../../shared/references/parallelism.md` for the parallel-by-default principle and how to brief a subagent; see `references/customization.md` for the recency, model, parallel-approval, and feed-size knobs.

---

## Scheduling

The recurring run schedules on the **host's or the OS's own scheduler**; the actions are the same on every host, and the agent composes the schedule and the run recipe for its own host — there is no per-host recipe to look up here.

- **Unattended schedule (the default).** Advocate a schedule that keeps firing with **no interactive session open** — a `cron` or `launchd` job, or the host's native unattended scheduler that survives session-close. A search is only useful when it runs while the user isn't watching, so reliability outweighs installing nothing. It stays a real machine change: shown before it is written, applied only on an explicit yes, user-removable — never silent, never auto-installed.
- **In-session loop (the fallback).** When the host has no unattended scheduler, or the user declines the machine change, offer an in-session loop — installs nothing but runs **only while a session is open**. The named fallback, not the recommendation.
- **Cloud schedulers do not qualify** — a cloud runner can't see the local `~/.job-search` workspace or the local agent-data auth, so a run there reaches neither the user's data nor their credentials and produces nothing.
- **Eligibility gates + selection.** A scheduler qualifies only when it passes all **six** gates — unattended, canary-testable through its registered invocation, exact-primary-model-preserving, reaching the local workspace/auth/network, inspectable, and reversible. Probe the native mechanism first and pick it only if every gate passes; else an OS mechanism that passes every gate; else create no verified job (the session-only loop is the labeled fallback). An existing job the agent didn't stage is unowned — inspect, then adopt-or-replace, never clobber. The registry records `installed`/`verified` only after a green canary. Gate table, selection order, and the registry state machine are single-homed in `../../shared/references/internals.md` → Scheduling setup and the Registry; doctrine in `references/scheduling-and-consent.md`.

To start scheduling: offer it as a yes/no (check the scheduling marker first — never re-ask if already set),
compose the run recipe, then apply the `schedule_enable_with_canary` row in
[Agent-data usage decisions](../../shared/references/internals.md#agent-data-usage-decisions). The structured
preview and exact machine change precede one scoped confirmation; that yes covers the machine change and
exactly one real scheduled-path canary. **Prove it with the canary before recording** — never call it
scheduled until the exact unattended invocation has been observed to succeed end to end. If a metered canary
fails, every repair or retry attempt gets fresh calls-first context and a fresh scoped confirmation;
the first approval is not standing authority. Only after a green canary set the scheduling marker. To turn
scheduling off: stop the active schedule, then clear the scheduling marker. Always show the user the
verbatim run recipe composed for the host — copy it exactly as written; do not reconstruct those tokens.

If a saved exact primary or detail model expires or exact dispatch is refused, keep the schedule disabled
and unverified and run the canonical **Exact-model repair** procedure in `internals.md`. It preserves valid
unchanged slots, rejects guessed identifiers, previews both exact bindings and all state effects, and uses
one scoped confirmation for the complete repair plus one real scheduled-path canary. A failed setup or
canary restores the exact transaction snapshot; only a green canary enables and verifies the schedule.

For the full flow — unattended-first advocacy, the consent line, and the mandatory canary (including what to do when the user explicitly asks for cron or launchd) — see `references/scheduling-and-consent.md`.

---

## When something fails

For an authority-qualified closed run, the outcome is the `run_health` field in `runs/<id>.json` and its
fold-derived digest header — one of `healthy | partial (<why>) | degraded (job sources flaky) | blocked
(action needed)`. For what each state means and when it's written, see `../../shared/references/errors.md`
(the four states and the surfacing story) and `../../shared/references/conventions.md` → the digest "Run
health" line. One meaning lives with the runner instead: a `degraded` run still reads promising matches in
full — no detail-read cap, relevance decides (see **job-search-run**).

**How failures surface:** a blocked run writes two durable artifacts — a `runs/<id>.json` record with `run_health:"blocked"`, and a `reports/<date>-digest.md` whose body is the named error + fix. The **home view** the next time you open the **job-search** skill reads `runs/<id>.json` and shows the error there. An attention-pull alert is capability-gated: if your host has an attention-pull surface, fire one alert on a blocked run when `notify.desktop_notify_on_block` is set; otherwise the two file channels carry the failure. **The written record is the primary signal on every harness** — surface every outcome through it (`../../shared/references/errors.md`); where your host provides a trustworthy exit code, that is an additional signal only, never a replacement.

For the full `E-*` table with exact cause and fix wording: see `../../shared/references/errors.md`.

**Symptom → fix quick lookup:**

| Symptom | Likely cause | Fix |
|---|---|---|
| Runs complete but 0 matches even though real postings exist | Query keywords don't match the brief's must-haves | Broaden the query in `config.yaml`, or run the **job-preference-interview** skill to align the brief |
| 0 results (literally empty) | Keywords too narrow or location too specific | Broaden `keywords` or `location` in the query |
| Last run: blocked — E-QUOTA | agent-data rejected a call for quota/payment | Check account access at https://agent-data.motie.dev/settings/billing; existing matches are unaffected. Discuss frequency, sources, or review depth only if the user later asks how to make calls last |
| Schedule isn't firing | The active schedule stopped (e.g. an in-session loop's session closed) | Check the scheduling marker in the registry (`../../shared/references/internals.md`); restart it with the run recipe composed for the host |
| "Stale brief" nudge in the digest | `preferences.md` hasn't been updated in a long time | Run the **job-preference-interview** skill to refresh it |

---

## Where to find things

| Looking for... | Go to |
|---|---|
| Workspace layout and `config.yaml` schema | `../../shared/references/conventions.md` |
| Every `E-*` error with cause + fix | `../../shared/references/errors.md` |
| OS registry, workspace discovery, config recipes, scheduling | `../../shared/references/internals.md` |
| agent-data CLI contract (routes, retry rules, listing ID, pricing/metering) | `../../shared/references/agent-data-contract.md` |
| The active workspace path | the Discovery procedure — `../../shared/references/internals.md` |
| Scheduling status | the registry's scheduling marker — `../../shared/references/internals.md` |
| Customization and flexibility workflows | `references/customization.md` |
| Parallel-by-default principle + how to brief a subagent | `../../shared/references/parallelism.md` |
| How skills talk to the user (voice, banned jargon, rendering briefs/digests) | `../../shared/references/voice.md` |
| Scheduling consent workflow | `references/scheduling-and-consent.md` |
| This operator manual | `job-search-agent` skill |

---

## Extending & contributing

**Single source of truth.** Each fact lives once in `shared/references/*.md`; skills reference it in place under the guaranteed bundle install (e.g. `../../shared/references/conventions.md` from a `SKILL.md`) — there are no per-skill copies to keep in sync. Edit the one canonical file. `./scripts/build.sh` regenerates only the content-hash build stamp; the sole case it assembles per-skill copies is a host that cannot resolve a path outside a skill directory (none today).

**Adding a new skill.** Create a folder under `skills/<skill>/` with a `SKILL.md` and an `evals/evals.json`. Reference any shared contract in place (`../../shared/references/<file>.md`) — nothing to sync. Write evals that cover the happy path and the named-error HALT paths.

**Evals use the fake shim.** Evals run through the fake `agent-data` shim in `tests/`, not the live CLI. When you add a code path that calls `agent-data`, route its eval through the shim.

**Philosophy guard.** The repo's CI runs a philosophy guard that rejects any file introducing numeric scores or score-threshold config into the shipped default output (`examples/`, `templates/`). Keep the guard green before opening a PR (exact commands in `CONTRIBUTING.md`).

**Versioning.** New workspaces use config `version: 2`; the runner retains bounded version-1 compatibility.
If a later breaking schema change is needed, bump the major version and add the corresponding
`E-CONFIG-VERSION` detection to the runner's preflight.

**Full contributor guide:** `CONTRIBUTING.md`.
