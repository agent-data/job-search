---
title: Plan B/D — Handoff
status: historical
verified: unverified
last_reviewed: 2026-06-07
code_refs: [shared/references/conventions.md, scripts/state.py, scripts/osctl.py]
---

# Handoff — Job Search OS: Plan B (Claude-Code-driven Onboarding) + Plan D (Packaging)

> **Historical snapshot (2026-06-05).** This handoff is preserved as written. Machine-local paths
> below (`~/cookbooks/…`, `~/job-search-os/…`) describe the original author's machine at handoff
> time and resolve nowhere else; the work they pointed at now lives in this repo. Superseded
> details: schemas/errors live in `shared/references/`; scheduling is `/loop`-only per
> core-beliefs 7.

**Purpose:** everything a fresh Claude Code session needs to design and build Plan B and Plan D. The
**new headline requirement**: the **entire onboarding is driven by Claude Code**. A user installs the plugin
(or clones the repo), opens Claude Code, says "go," and Claude Code runs the whole setup + onboarding —
checking prerequisites, deciding/recording where to store data, running the preferences interview, configuring
the "OS," doing a first live run, and setting up the schedule — asking the user questions as needed. To do this
Claude Code needs **internal knowledge ("OS internals")**: where state lives, how to find the active workspace,
how to read/update config, and how to detect first-run vs returning user.

> **How to use this doc:** paste the kickoff prompt in §10 into a new Claude Code session. This handoff is the
> source of truth and points to the spec, Plan A, and the code. Build Plan B and Plan D the same way Plan A was
> built: **brainstorming → writing-plans → subagent-driven-development**, honoring the design philosophy below.

---

## 1. Where things stand (Plan A — DONE and verified)

The **core engine** is built, tested, and verified against the live API. It lives in a local git repo:

- **Repo:** `~/job-search-os` (git, on `main`, ~22 commits, NOT pushed to any remote). 18 pytest tests green.
- **Spec (read it):** `~/cookbooks/docs/superpowers/specs/2026-06-05-job-search-os-design.md`
- **Plan A (read it):** `~/cookbooks/docs/superpowers/plans/2026-06-05-job-search-os-foundation-core.md`
- **Opinionated guides to honor:** `~/cookbooks/references/` (ceo-review, devex-review, office-hours,
  plan-devex-review, plan-eng-review + dx-hall-of-fame). These shaped Plan A; keep applying them.

What exists in `~/job-search-os`:
```
skills/evaluate-job-fit/   SKILL.md + references/ + evals/   # the relevance "brain" (qualitative)
skills/job-search-run/     SKILL.md + references/ + scripts/state.py (bundled) + evals/ + evals/files/
scripts/state.py           # dependency-free jobs.jsonl engine: known-ids | append | fold (10 TDD tests)
scripts/build.sh           # syncs shared/references + state.py into each skill (loose-skills self-containment)
shared/references/         # agent-data-contract.md, errors.md, conventions.md  (SINGLE SOURCE OF TRUTH)
templates/                 # config.example.yaml, preferences.example.md, workspace.gitignore
tests/                     # test_state.py, test_fake_agent_data.py, fake-agent-data shim + fixtures/
README.md                  # current quick-start (manual install + manual workspace; Plan D replaces this)
LICENSE (MIT)
```

**Two skills are already working** and were installed this session for testing:
- Symlinks: `~/.claude/skills/evaluate-job-fit` and `~/.claude/skills/job-search-run` → the repo skills.
- A scaffolded test workspace at `~/job-search/` (from templates; the user may have edited
  `~/job-search/preferences.md` with real data — **treat `~/job-search/` as possibly containing real user data;
  do not clobber it**).
- Plan B's restructure (orchestrator + registry/internals + plugin) should account for / supersede these dev
  symlinks; the user can `rm ~/.claude/skills/{evaluate-job-fit,job-search-run}` once the plugin is the install path.

**The single job source** is the agent-data "Job Postings API" (LinkedIn-backed), listing id
`f9a6ec16-0bfd-44d8-b3ee-073776745ee7`. All its facts (routes, params, error envelope, retry rules) are already
distilled in `shared/references/agent-data-contract.md` — **do not re-discover; trust that file** (it was
verified against live `agent-data docs`). `search`/`docs`/`status`/`whoami` are FREE; only `search-jobs` and
`get-posting` are metered.

---

## 2. Design philosophy — carried forward, NON-NEGOTIABLE

These were deliberate user decisions during Plan A. Do **not** revert them:

1. **Relevance is QUALITATIVE.** Binary relevant/not, and if relevant **weak/moderate/strong**. **Never** numeric
   scores, 0–100, points, or category weights (false precision). The model reads a prose brief and judges.
2. **Frequency, not budget.** The user controls **how often** to pull (hourly→weekly). **No** credit/USD/budget
   knobs, no per-call math shown as a decision input. Cost surfaces only **reactively** as a plain-language
   `E-QUOTA` ("pull less often, or upgrade your agent-data plan").
3. **Local-first.** Runs on the user's machine (OS cron/launchd or a kept-open session). No cloud secrets.
4. **Private workspace.** Personal data (preferences, jobs, later resume) lives in a per-user folder
   (default `~/job-search/`), deny-all `.gitignore`, never committed. The public repo has no personal data.
5. **No silent failures.** Every failure is a **named error** (`E-*` in `errors.md`) with cause + fix; headless
   runs exit non-zero when blocked. Trace happy/empty/error paths.
6. **Magical moment + zero-friction T0.** Onboarding should end by showing real matches fast (<~5 min).
7. **Docs-as-product.** Ship docs with the feature; error messages name the fix.
8. Honor the `~/cookbooks/references/` guides (DX first principles, plan/eng/CEO review rigor, office-hours
   demand thinking). Build/iterate each skill with **skill-creator** (evals where gradable).

---

## 3. The new vision — Claude-Code-driven onboarding ("the OS shell")

Today, a user must manually install skills and hand-build a workspace (see README). The target experience:

> **Install the plugin → open Claude Code → `/job-search` (or "set up job search") → Claude Code does the rest**,
> asking questions inline (the interview, the queries, the frequency), recording the answers, doing a first live
> run, and setting up the schedule. Next session, `/job-search` recognizes the user and shows their status.

This requires Claude Code to hold **persistent "OS internals"** — knowledge + state that survives across sessions:

- **OS state / registry:** a small, plugin-owned record of *where the active workspace is* (and any global
  settings), so any skill can locate the user's data without being told each time. Proposed:
  `~/.config/job-search-os/config.json` (XDG; fall back `~/.job-search-os/config.json`), e.g.
  `{ "version": 1, "active_workspace": "/Users/<u>/job-search" }`. (Open decision — see §6.)
- **Workspace discovery algorithm:** read the registry → `active_workspace`; else default `~/job-search/`; if that
  has no `config.yaml`, you're in **first-run** → trigger onboarding. This replaces the current `--workspace`
  flag with auto-discovery (`--workspace` stays as an override).
- **An "OS manual" the skills consult** — the literal "internal skill(s)" the user asked for: a reference (and/or
  a model-only skill) documenting the registry location + schema, the discovery algorithm, first-run detection,
  how to read/update `config.yaml` safely (add a query, change frequency), the workspace file contracts (already
  in `conventions.md`), and how to set up local scheduling per-platform.
- **An orchestrator skill (the "shell"/home):** the `/job-search` entrypoint. On invoke it reads the OS internals,
  then either runs **onboarding** (first-run) or shows the **home** (status: latest digest, new-match count,
  pipeline) with quick actions (run now, edit preferences, change frequency, etc.). This is the "click go."

Mental model: Claude Code is the kernel/shell; the orchestrator skill is the login shell + home screen; the
registry is the OS state; `conventions.md`/`internals` is the filesystem spec; the run skill is cron's job; the
agent-data CLI is the syscall layer. Plan A built the syscalls and the job; Plan B builds the shell + state + the
onboarding wizard; Plan D ships it as an installable OS image (plugin).

---

## 4. Plan B scope — Onboarding (build these; refine names/splits in brainstorming)

**New skills / components**
1. **`job-search` — orchestrator / OS shell** (user- + model-invocable; the "go" entrypoint). Description must
   trigger on `/job-search`, "set up job search," "start my job search," "find me jobs," "check job search." Reads
   OS internals → branches first-run (onboard) vs returning (home). Onboarding flow:
   prereq check (agent-data installed? `whoami` authed? — name the exact fix if not) → choose/confirm workspace
   location + create it + write the registry → **interview OR import** an existing brief → configure `queries`
   (keywords/location) + `schedule.frequency` by Q&A (plain-language nudges; no credit math) → **first live sample
   run** (the magical moment; reuse `job-search-run`) → set up the local schedule (with consent) → print the home.
2. **`job-preference-interview`** (user-invocable). Refactor `~/cookbooks/job-preference-interview.md` into a skill
   that produces the **prose** `preferences.md` brief (Summary, Must-haves/dealbreakers, Strong preferences,
   Nice-to-haves, Red flags). **Drop its 0–100 scoring rubric** (philosophy #1). Callable by the orchestrator and
   standalone (re-run to update the brief). One-question-at-a-time; make criteria concrete/observable.
3. **OS internals** — the "internal skill(s)": a `shared/references/internals.md` (OS manual: registry schema +
   location, workspace discovery, first-run detection, config read/update recipes, scheduling-setup knowledge),
   and/or a model-only helper skill if dynamic behavior is needed. Decide skill-vs-reference in brainstorming.
4. **Scheduling setup** — driven by Claude with the user's chosen frequency: write the cron/launchd entry (consent
   + a marker so it never re-asks), or the `/loop` path; handle the macOS "must be awake" caveat (the spec's
   Scheduling UX section has the exact copy). "Boring default" = OS cron / launchd headless `claude -p "/job-search-run"`.

**Updates to existing skills**
5. **`job-search-run`** and **`evaluate-job-fit`**: auto-discover the active workspace via OS internals (registry
   → default), with `--workspace` as an override. Today the run skill resolves the workspace from cwd/`--workspace`;
   wire it to the registry. Keep the headless/interactive split: the scheduled run stays non-interactive (it must
   never block on a question); onboarding is interactive and separate.

**First-run vs returning-user**
6. First-run = no registry AND no default-workspace `config.yaml`. Returning = registry/workspace present →
   orchestrator shows status + actions and can nudge ("brief is N months old — re-run the interview?").

**Acceptance criteria (Plan B "done")**
- With skills available, `/job-search` from a clean machine walks a user through prereqs → brief → queries +
  frequency → first real matches → schedule, entirely via dialogue, and **persists** the workspace location +
  config so the next session recognizes them.
- A returning `/job-search` shows the latest digest/status and offers run/adjust actions.
- A scheduled headless run still works unattended (uses the registry, never prompts).
- No numeric scores/weights; no credit/budget knobs; every blocked path is a named `E-*` with a fix.

---

## 5. Plan D scope — Packaging & dual-distribution

Goal: **install → `/job-search` → onboarded**, plus a "from source" path, plus polished docs.

1. **Claude Code plugin** — author the plugin manifest so installing the plugin makes all skills
   (orchestrator, interview, run, evaluate, + internals) available. **Verify the CURRENT plugin/marketplace
   format against Claude Code docs** (it evolves) — use the `claude-code-guide` agent or `/plugin` docs; don't
   assume. Bundle: skills (self-contained via `build.sh`), `scripts/` (state.py + build.sh), `shared/references/`,
   `templates/`, `examples/`.
2. **Dual distribution from one folder set** (already designed in the spec's packaging section). `build.sh` exists
   and syncs `shared/references/*` + `state.py` into each skill so a skill works whether loaded as a plugin or
   copied into `~/.claude/skills/`. Confirm both install modes; CI/`build.sh` keeps copies in sync (don't hand-edit
   the synced copies — edit `shared/`/`scripts/` then run `build.sh`).
3. **Full README** (replace the current interim quick-start): the plugin-install golden path first
   (install → `/job-search`), then a "from source" path; cost honesty in plain language; privacy; the named-error
   troubleshooting table from `errors.md`; a real sample digest (`examples/sample-digest.md`); the roadmap.
4. **Examples & onboarding polish:** `examples/sample-digest.md`, `examples/sample-preferences.md`; a magical-moment
   first-run; TTFV < ~5 min (honest about live LinkedIn latency).
5. **Update/versioning flow** for the plugin; `LICENSE` already MIT.

**Acceptance criteria (Plan D "done")**
- A new user installs the plugin (one step), runs `/job-search`, and is onboarded end-to-end.
- The same skills also work via the clone + `build.sh` + copy/symlink path.
- README is docs-as-product quality; examples show real output before install.

---

## 6. Open design decisions — resolve these in brainstorming (don't assume)

1. **Workspace location model:** fixed canonical `~/job-search/` (simplest, no registry) vs a **registry-recorded
   configurable** location (flexible, supports custom path / multiple searches). Recommended middle ground: default
   `~/job-search/`, registry override for power users. Pick and justify.
2. **Registry location + format:** `~/.config/job-search-os/config.json` (XDG) vs `~/.job-search-os/config.json`;
   minimal schema. Cross-platform (macOS focus, but keep it portable).
3. **"Internal" mechanism:** a `references/internals.md` (OS manual) vs a model-only skill vs both. Where does the
   workspace-discovery logic live so every skill uses it identically?
4. **Orchestrator vs separate setup skill:** one `job-search` skill that does both onboarding and home, or a thin
   orchestrator that delegates to a `job-search-setup` skill? (Plan A's spec named a separate `job-search-setup`;
   the new "shell" vision may merge it.)
5. **The "go" trigger:** `/job-search` slash command, natural-language triggers, or both. How obvious is it post-install?
6. **Scheduling mechanism + consent:** OS cron vs launchd (macOS wake) vs `/loop`; how Claude writes it with consent;
   how it records that scheduling is set up (so it doesn't re-ask).
7. **Returning-user "home" UX:** what status to show (latest digest summary, new/interested counts), what quick
   actions, how to surface `needs_human_check` items and a stale-brief nudge.
8. **Clone-path bootstrap:** if a user clones instead of installing the plugin, how do skills get loaded? (A
   documented one-liner / a bootstrap that runs `build.sh` + copies skills, or "install as a plugin from the clone.")
9. **Interview-vs-import fork in onboarding:** how the orchestrator offers "interview me" vs "I have a brief"
   (validate an imported brief is usable prose).
10. **Migration of this session's dev install:** how onboarding coexists with / supersedes the existing
    `~/.claude/skills` symlinks and the `~/job-search/` test workspace (don't destroy real data).

---

## 7. Integration points & gotchas

- **Don't re-discover agent-data facts** — they're in `shared/references/agent-data-contract.md` (verified). If you
  must check the live service, `agent-data docs <listing-id>`, `status`, `search` are FREE; only `call search-jobs`/
  `get-posting` cost. Keep the live-smoke budget tiny (≤3 calls), like Plan A's Task 14.
- **Single source of truth for references/scripts:** edit `shared/references/*` and `scripts/*`, then run
  `./scripts/build.sh` to fan them into each skill. Never hand-edit a skill's synced `references/` or bundled
  `scripts/state.py`.
- **`state.py` interface:** `known-ids --jobs PATH`, `append --jobs PATH --event JSON`, `fold --jobs PATH`. It's the
  only thing that touches `jobs.jsonl`. Reuse it; don't write a parallel store.
- **Headless ≠ interactive:** the scheduled `job-search-run` must never prompt. All onboarding/interview/config Q&A
  lives in the orchestrator/interview skills, which are interactive only.
- **Testing skills without spending credits:** reuse `tests/fake-agent-data` (a PATH shim with scenarios:
  happy/zero-empty/stretch/quota/down/invalid-pair/detail-fetch-failed/degraded; `JOBSEARCH_TEST_*` envs). The run
  evals install it via a `_bin/agent-data` symlink on PATH (`skills/job-search-run/evals/files/setup-workspace.sh`).
  Use the same pattern to test the orchestrator's onboarding flow with canned responses + a temp registry/workspace.
- **Plan A's run-skill nuances to preserve:** free `status` gate before metered calls; retry only on the `retryable`
  boolean; stop after two consecutive failed queries (E-UPSTREAM-STRETCH); dedup by `source_id`; full
  provenance-carrying `evaluated` events; `$STATE` resolved from the skill's own dir (bundled `scripts/state.py`).
- **Plan C (resume) is still future** — out of scope here. The orchestrator can stub/defer resume actions.

---

## 8. Recommended process (what worked for Plan A)

1. **Read first:** this handoff → the spec → Plan A → the code (`shared/references/*`, both `SKILL.md`s, `state.py`),
   skim `~/cookbooks/references/` guides. Use `Explore` subagents to fan out if helpful.
2. **Brainstorm** (`superpowers:brainstorming`): resolve §6's decisions with the user (one focused round of
   questions is fine). Produce/update a short design addendum for the onboarding + internals (a spec delta).
3. **Write plans** (`superpowers:writing-plans`): a **Plan B** and a **Plan D** (separate, milestone-sized, each
   producing testable software). Bite-sized TDD for any deterministic scripts; skill-creator authoring + evals for
   the prose/orchestrator skills (use the fake-agent-data shim for onboarding-flow evals).
4. **Implement** (`superpowers:subagent-driven-development`): one implementer subagent per task + two-stage review
   (spec compliance → code quality). Commit frequently. Run the full suite + a tiny live smoke test at the end.
5. **Finish** (`superpowers:finishing-a-development-branch`). Then ask the user about publishing.
6. Throughout: keep the **qualitative, frequency-not-budget** philosophy; name every error; magical-moment T0;
   docs-as-product. Build/eval with skill-creator. Verify plugin format against current docs (`claude-code-guide`).

---

## 9. Quick reference — paths & commands

```
Repo:        ~/job-search-os                 (git on main; build/test from here)
Spec:        ~/cookbooks/docs/superpowers/specs/2026-06-05-job-search-os-design.md
Plan A:      ~/cookbooks/docs/superpowers/plans/2026-06-05-job-search-os-foundation-core.md
This handoff:~/cookbooks/docs/superpowers/2026-06-05-job-search-os-plan-b-d-handoff.md
DX guides:   ~/cookbooks/references/
User brief source to refactor: ~/cookbooks/job-preference-interview.md

Tests:       cd ~/job-search-os && python3 -m pytest -q          # 18 green (no real API)
Sync:        ./scripts/build.sh                                  # after editing shared/ or scripts/
Live (free): agent-data whoami ; agent-data docs f9a6ec16-0bfd-44d8-b3ee-073776745ee7
Dev install (this session): ~/.claude/skills/{evaluate-job-fit,job-search-run} -> repo skills ; workspace ~/job-search/
```

---

## 10. Kickoff prompt (paste into a new Claude Code session)

> We're continuing the **Job Search OS** project. Plan A (the core engine) is built and verified. I now want to
> build **Plan B (onboarding)** and **Plan D (packaging)** with a new headline requirement: **the ENTIRE
> onboarding must be driven by Claude Code.** A user installs the plugin (or clones the repo), opens Claude Code,
> says "go" (e.g. `/job-search`), and Claude Code handles setup + onboarding end-to-end — checking prerequisites,
> deciding/recording where to store data, running the preferences interview, configuring the "OS" (queries,
> frequency), doing a first live run, and setting up the schedule — asking me questions inline as needed. This
> needs persistent **"OS internals"**: internal skill(s)/reference(s) telling Claude where state lives, how to find
> the active workspace, how to read/update config, and how to detect first-run vs returning user.
>
> **Start by reading the handoff — it's the source of truth and points to everything else:**
> `~/cookbooks/docs/superpowers/2026-06-05-job-search-os-plan-b-d-handoff.md`
> Then read the spec and Plan A (paths in the handoff) and the existing code at `~/job-search-os`
> (`shared/references/*`, `skills/*/SKILL.md`, `scripts/state.py`). Use Explore subagents to fan out.
>
> Then proceed exactly as Plan A was built: **brainstorming** (resolve the open design decisions in the handoff's
> §6 with me — one focused round), then **writing-plans** (a separate Plan B and Plan D, milestone-sized), then
> **subagent-driven-development** (one implementer per task + two-stage spec/quality review, frequent commits,
> a final review + a tiny ≤3-call live smoke test). Honor the opinionated guides in `~/cookbooks/references/` and
> the project's **non-negotiable philosophy**: relevance is QUALITATIVE (no numeric scores/weights), users control
> FREQUENCY not credits/budget (cost only via reactive plain-language E-QUOTA), local-first, private workspace,
> named errors / no silent failures, magical-moment onboarding, docs-as-product. Build and eval each skill with
> **skill-creator**, reusing the `tests/fake-agent-data` shim so onboarding-flow evals spend no real credits.
> **Verify the current Claude Code plugin/marketplace format** before authoring the manifest (use the
> claude-code-guide agent). Don't reintroduce numeric scoring or credit/budget knobs, and don't clobber my real
> data in `~/job-search/`. Keep me in the loop at each phase gate (design approval, plan approval, and between
> implementation tasks).
