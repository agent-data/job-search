---
title: Hermes Job Search Assistant — Seamless Install + Adapter-Native Onboarding
status: current
verified: partial
last_reviewed: 2026-06-30
code_refs: [shared/references/platform/hermes.md, skills/job-preference-interview/SKILL.md, skills/job-search-run/SKILL.md, skills/job-search/references/onboarding.md, docs/design-docs/hermes-harness-review/overview.md, docs/design-docs/2026-06-30-hermes-job-search-concierge.md, runtime/hermes_job_search/cli.py, README.md]
---
# Hermes Job Search Assistant — Seamless Install + Adapter-Native Onboarding

Make a Hermes user able to say *"install `agent-data/job-search` and help me find a job"* and have it
just work: Hermes installs the plugin itself, asks only for an agent-data key, and then runs the
**existing** end-to-end `job-search` onboarding — preferences first, a live first run, then a scheduled
delivery to a channel they choose. The plugin is a set of skills plus the workspace/state structure that
turns a generic Hermes agent into a job-search assistant; this doc says how that lands natively on Hermes
**without** a new runtime layer.

**Supersedes** [Hermes Job Search Concierge Layer](2026-06-30-hermes-job-search-concierge.md). That design
introduced a host-gated "concierge" front door, a memory-permission model, and a "calibration" abstraction.
A source-grounded review of the Hermes harness ([overview](hermes-harness-review/overview.md)) showed the
first is unimplementable, the second gates the wrong thing, and the third re-invents the existing first-run
flow. This design replaces it with a smaller, adapter-first plan.

## Goal

One seamless arc, all of it already shaped by the existing first-run playbook
([`onboarding.md`](../../skills/job-search/references/onboarding.md)):

1. **Install** — Hermes reads `hermes/INSTALL.md`, registers and loads the plugin, and sets up the
   agent-data CLI. The only thing it asks the user for is the agent-data account + API key.
2. **Preferences first** — onboarding explains *why* (so postings can be judged for relevance before
   anything is pulled or scheduled) and, on Hermes, offers to pre-draft the brief from the user's **prior
   sessions** (with permission). The draft is editable working material; the user can interview, refine, or
   import instead.
3. **First live run** — the orchestrator pulls postings via agent-data, reads every title/summary, and
   delegates the promising ones to parallel subagents for detail judgment; relevant matches are shown with
   plain-language reasoning.
4. **Schedule + deliver** — once the user is happy, set a cadence (recommend daily) and **ask where to send
   it**, then create the recurring job delivering to that channel.

## Non-goals

- **No runtime host-gating.** There is no `host==Hermes` check; Hermes exposes none (the platform env vars
  are the *messaging channel*, not host identity — see [overview](hermes-harness-review/overview.md)).
  Differentiation is **install-time only**.
- **No second front door, no "concierge" skill.** `job-search` stays the canonical front door; the five
  skills keep their roles.
- **No memory-based drafting.** Hermes memory (`MEMORY.md`/`USER.md`) is auto-injected into context and is
  not what we draw on; drafting reads **prior sessions** via session search, and only with permission.
- **No "calibration" / analytics subsystem and no dashboard.** The first run is just the existing first
  live run; explanations are derived on demand from existing state.
- **No numeric fit scoring; no post-install dependency on the repo's `hermes/` tree** (unchanged).

## Architecture: adapter-first

The skills stay harness-neutral and defer every Hermes mechanism to the existing adapter
[`shared/references/platform/hermes.md`](../../shared/references/platform/hermes.md). Each host reads only
its own adapter, so Hermes-specific behavior is isolated **without any host detection** — the property the
review found Hermes cannot provide is simply not needed. Exactly one new behavior threads a neutral skill
hook to an adapter section (prior-session drafting); everything else already exists.

Install differentiation lives in docs, not code: `hermes/INSTALL.md` is the Hermes bootstrap path, and the
coding-agent install paths are untouched and pull in nothing Hermes-specific.

## Install — `hermes/INSTALL.md` + a one-line README pointer

`hermes/INSTALL.md` must let a generic Hermes, unattended:

- register and **load** the plugin — note that `hermes skills tap add` registers a source but a
  `hermes skills install` step is likely required to actually load the skill (**verify-live**; the shipped
  adapter's verify recipe currently omits it);
- confirm the skills are visible;
- set up agent-data (`agent-data init --hermes --api-key <KEY> --yes` → `whoami`);
- reach the first invocation (`job-search`).

Install steps run autonomously; the agent-data key is the only user input, requested at the step that
consumes it. The README Hermes section collapses to a pointer: *"On Hermes, read `hermes/INSTALL.md`."*

## Onboarding behavior changes

Three light edits to the existing flow; no new playbook.

### Preferences (§4): offer a prior-session draft, permissioned

In [`job-preference-interview`](../../skills/job-preference-interview/SKILL.md), before the existing
interview/import fork, add a **neutral** step: *if the active adapter can recall prior sessions, offer to
pre-draft the brief from them.* Ask permission, state the benefit, give a clean decline path; on decline,
fall through to the existing depth choice (quick / standard / thorough) or import.

The Hermes adapter gains a **"Prior-session recall"** section: the mechanism is
`session_search` (FTS5 over past sessions); ask first; synthesize the draft from what prior sessions
actually show; write **only** to the workspace `preferences.md`, **never** to `USER.md`, and never silently
promote inferred preferences to durable profile truth; present the result as an **editable draft**. Because
prior-session recall is a Hermes-specific capability (not a universal one), it is a Hermes-only adapter
section and **no other host's adapter needs an edit** — the neutral skill defers in prose, so where an
adapter has no such section the offer is simply skipped. (Grounding: [memory-and-sessions](hermes-harness-review/memory-and-sessions.md).)

**Clarify discipline** (reaffirmed here, the old "T4" issue): an open-ended question passes **no** choices
(Hermes renders it as free text); a closed question never authors its own "Other" (Hermes auto-appends
one). This is correct authoring, not a broken fallback to repair — the eval asserts the behavioral
contract, not "no duplicate Other." (Grounding:
[tools-clarify-and-channels](hermes-harness-review/tools-clarify-and-channels.md).)

### First live run (§6): orchestrator → parallel detail reads → results from disk

The existing "first live sample run" already is the first interactive run — there is no separate
calibration. Its contract on Hermes: the orchestrator pulls postings per saved query and reads **all**
titles/summaries itself, then **delegates detail reads of the promising postings to parallel subagents**
(`delegate_task`, chunked to the concurrency cap of 3). Each subagent reads one full description, judges fit
via `evaluate-job-fit`, and **writes its structured verdict to a run-scoped scratch file** (e.g.
`<run-scratch>/<posting_id>.json`) instead of returning it in the orchestrator's context.

**The orchestrator collects results from disk, not from the return channel.** On completion it reads the
per-posting verdict files, folds them into the durable digest / run record / event log (the bundled runtime
does the bookkeeping; the model keeps the judgment), and shows the relevant matches with reasoning plus a
brief note on what was filtered. This disk-handoff is the **deliberate pattern, not a fallback**, for two
reasons: it keeps the main agent's context lean (subagents absorb the long descriptions; only compact
verdicts touch disk) and it is faster and **robust to the delegation execution model** — whether
`delegate_task` returns inline or **background-async** (results arriving as later messages, per
[delegation-and-subagents](hermes-harness-review/delegation-and-subagents.md)), the orchestrator's
completion signal is simply "the expected verdict files exist." A sequential in-turn read is only a
last-resort fallback if subagents cannot be spawned at all. (The verdict files are ephemeral run scratch;
the durable artifacts remain the digest, `jobs.jsonl`, and the run record.) The same disk-handoff is the
general pattern for any host with subagents, not Hermes-only — Hermes just needs it most, because its
top-level delegation may be background.

### Scheduling + delivery (§7): ask where, deliver there

After the user is satisfied, offer a cadence in human terms (hourly / daily / weekly; recommend daily) and
**ask where to deliver**. Then create the recurring job delivering to that channel:

- **"here" or an already-configured channel** → seamless; create via the in-session `cronjob` **tool** so
  the `origin` delivery target binds to *this* chat (a shelled `hermes cron create` from a bare terminal
  does not bind origin to the session).
- **a brand-new platform (v1 scope: acknowledged, not built out)** → a one-time, out-of-band setup; bringing
  up a new gateway channel can restart the gateway and drop the active session, so confirm and resume on the
  next interaction rather than promising one continuous flow.

Always confirm the gateway daemon is running before promising automation (it ticks cron ~every 60s).
Delivery content defaults to the existing digest summary; offer summary-only later if the user prefers.
(Grounding: [cron-and-scheduling](hermes-harness-review/cron-and-scheduling.md),
[tools-clarify-and-channels](hermes-harness-review/tools-clarify-and-channels.md).)

## Adapter corrections (folded into this work)

The review found concrete errors in the shipped adapter; fix them in the same pass that adds the
prior-session section ([identity-architecture-and-install](hermes-harness-review/identity-architecture-and-install.md)):

- A project `AGENTS.md` loads **cwd-top-level-only**; the cwd→git-root walk belongs to `.hermes.md`/`HERMES.md`,
  not `AGENTS.md`. Correct the Identity section's "walks cwd → git root" line.
- `${HERMES_SKILL_DIR}` is a **load-time `SKILL.md` template token** (gated by `skills.template_vars`), not a
  shell env var; the runtime call must resolve the skill dir from the rendered path and tolerate the token
  being disabled.
- **Keep** the delegation inline-vs-background PIN; do not assert inline/blocking.
- `--no-agent` is a **real** registered flag; do not scrub it. Keep the CLI-`edit` vs tool-`update` verb
  disambiguation.
- Add the missing **Memory & Sessions** coverage to the adapter (session search; memory auto-injected; a
  scheduled run is `skip_memory`).
- Add the `hermes skills install` step to the packaging/verify recipe.

## Explainability

Questions like "any new jobs today?", "how many were filtered out?", and "why no alert on X?" are answered
from existing stored artifacts (`runs/`, `jobs.jsonl`, digests) first, with an optional live re-check
second. No new persistent analytics layer.

## Repo surface

- **New:** `hermes/INSTALL.md`; README Hermes section → one-line pointer.
- **Edit** [`shared/references/platform/hermes.md`](../../shared/references/platform/hermes.md): add
  "Prior-session recall"; rework "Concurrent detail reads" so subagents **persist
  verdicts to a run scratch and the orchestrator reads them on completion** (robust to inline vs background
  `delegate_task`, keeps the main context lean); tighten the clarify rule; make delivery
  create-via-`cronjob`-tool and the gateway check explicit; apply the adapter corrections above.
- **No edit** to other hosts' `platform/*.md` adapters — prior-session recall is Hermes-only; the neutral
  skill prose defaults to skipping the offer where an adapter is silent.
- **Edit** [`job-preference-interview`](../../skills/job-preference-interview/SKILL.md): the neutral
  draft-offer hook + clarify discipline.
- **Edit (light)** [`job-search-run`](../../skills/job-search-run/SKILL.md): the detail-read step collects
  each worker's verdict **from disk on completion** (mechanism per the active adapter), not via inline
  returns.
- **Edit (light)** [`onboarding.md`](../../skills/job-search/references/onboarding.md): §4 surfaces the
  prior-session draft offer **ahead of** the interview/import fork (the offer is owned by
  `job-preference-interview`, so onboarding only sequences it, it does not reimplement it); §7 asks the
  delivery destination.
- **Validation:** add a bespoke `hermes-prior-session` check to `scripts/validate_platforms.py` (mirroring
  the existing `hermes-runtime-invocation` / `codex-parallel-subagents` checks) asserting `hermes.md`
  documents the capability — a Hermes-only section, **not** a 13th canonical section. `build.sh` sync unchanged.
- **Docs:** mark the superseded design + exec plan; index this doc; reconcile any links.

## Open questions / verify-live

Carried from the review's bench checklist: the `delegate_task` execution model (inline vs background); how
`clarify` renders on a messaging surface; `session_search` availability and shape for the drafting feature;
whether `hermes skills install` is required after `tap add`; `${HERMES_SKILL_DIR}` resolution (and the
`template_vars`-off fallback); and whether the agent's `terminal` subprocess inherits the session origin so
`--deliver origin` targets the chat.

## Why this design

It keeps the cross-host domain core stable, preserves one canonical front door, and makes Hermes feel native
by **reusing the existing onboarding** rather than forking it — adding exactly one capability (permissioned
prior-session drafting) and correcting the adapter against ground truth. It removes the original's
host-gating (unimplementable), memory-permission model (gates the wrong thing), and calibration/analytics
machinery (redundant), which is most of the original's surface area.
