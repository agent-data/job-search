---
title: Core Beliefs — Agent-First Operating Principles
status: current
verified: partial
last_reviewed: 2026-06-29
code_refs: [scripts/philosophy_guard.py, scripts/doc_lint.py, scripts/build.sh, .github/workflows/ci.yml, shared/references/internals.md, shared/references/conventions.md]
---
# Core Beliefs — Agent-First Operating Principles

These are the beliefs that define how the agent — and the people who change it — operate. Read
this before you change product behavior: a change that regresses one of these is almost always the
wrong direction. They split by how they hold. Most are non-negotiable because they are
mechanically blocked in CI — a guard, a build check, or a hook fails the PR, so the regression
can't land. The rest are cultural: held by review and habit rather than tooling, and each belief's
**Enforced by** says so honestly (some are wholly cultural; a couple have a mechanical backstop
plus a residual judgment review must catch). The beliefs themselves are the canonical framing in
[CONTRIBUTING.md](../../CONTRIBUTING.md#project-philosophy-please-dont-regress-these); this doc adds
the *enforcement* — for each belief, where it lives in the code and how to check it.

Each belief is written in four parts:

- **Statement** — the belief in one line.
- **Why** — the rationale.
- **Enforced by** — the concrete mechanism (a script, hook, CI job, or reference). Where a belief
  is cultural rather than mechanical, this says so honestly.
- **How to verify** — the exact command to run or file to inspect.

The runtime contracts these beliefs *protect* (the named errors, the config schema, the digest, the
status vocabulary, the frequency lever) are owned by [shared/references/](../../shared/references/conventions.md)
and are linked, never restated here — this doc is a live design-doc subject to the
`no-shared-reference-duplication` rule in [scripts/doc_lint.py](../../scripts/doc_lint.py).

## 1. Qualitative, never numeric

- **Statement.** Relevance is *relevant or not*, and if relevant *weak / moderate / strong*, with
  plain-language reasoning — never a 0–100 fit score, a category weight, or per-criterion points in
  shipped output.
- **Why.** Job fit is a judgment, not an arithmetic. A number invites false precision and tuning a
  rubric instead of writing better preferences; the qualitative vocabulary keeps the reasoning legible.
- **Enforced by.** [scripts/philosophy_guard.py](../../scripts/philosophy_guard.py) scans shipped
  default output (`examples/`, `templates/`) for fit scores / weights / points and fails the build;
  it runs in CI ([.github/workflows/ci.yml](../../.github/workflows/ci.yml)) and as
  `tests/test_philosophy_guard.py`. The relevance vocabulary it protects is defined in
  [shared/references/conventions.md](../../shared/references/conventions.md). A score a user explicitly
  asks for *in chat* is fine — it just must never be written into a digest, brief, or the job log.
- **How to verify.** `python3 scripts/philosophy_guard.py --root .` → `Philosophy guard: clean.`

## 2. Frequency, not budget

- **Statement.** The only cost lever the user touches is *how often* the system runs; cost surfaces
  reactively, in exactly one place, as a named quota error.
- **Why.** A budget knob forces users to reason about credits and per-call math they can't predict.
  Frequency is the lever they actually understand, and the one place cost should ever appear is when a
  metered call is rejected — with a fix (run less often, or upgrade the plan).
- **Enforced by.** [scripts/philosophy_guard.py](../../scripts/philosophy_guard.py) rejects any
  `budget` / `credits` / `cost` config field or cost knob in shipped output. The reactive quota error
  and its fix are owned by [shared/references/errors.md](../../shared/references/errors.md); the
  frequency enum lives in [shared/references/conventions.md](../../shared/references/conventions.md).
- **How to verify.** `python3 scripts/philosophy_guard.py --root .` → `Philosophy guard: clean.`

## 3. Private & local

- **Statement.** The per-user workspace is private PII protected by a deny-all `.gitignore`; it is
  never committed, and no personal data belongs in this repo.
- **Why.** A job search is sensitive: resumes, preferences, the postings you looked at. Local-first
  with a deny-all default means the safe thing happens even if someone runs `git add` from inside the
  workspace.
- **Enforced by.** The workspace gitignore *template* ships a deny-all (`*` then `!.gitignore`) that
  the first-run setup copies in; the file layout and "never committed" contract are owned by
  [shared/references/conventions.md](../../shared/references/conventions.md). Beyond the template this
  is **cultural** — there is no CI check that scans for committed PII, so review must catch it.
- **How to verify.** Inspect `templates/workspace.gitignore` (the deny-all template) and confirm no
  workspace contents are tracked.

## 4. No silent failures — named errors

- **Statement.** Every blocked path is a named `E-*` error carrying its own cause and fix, surfaced to
  the user through the home view, the digest, and a desktop notification.
- **Why.** A headless run that fails quietly is worse than no run. Naming each failure — with the fix
  attached — means a user always learns what to do next, and never has to read a log to find out a run
  did nothing.
- **Enforced by.** The named-error catalogue, the three surfacing channels, and the rule that a HALT
  writes a blocked record (because a headless `claude -p` exits 0 even when blocked) are all owned by
  [shared/references/errors.md](../../shared/references/errors.md). The behavior is exercised by the
  job-search-run skill's evals (the quota / service-down / no-auth / no-preferences / config-version
  halt scenarios in `skills/job-search-run/evals/evals.json`).
- **How to verify.** Read [shared/references/errors.md](../../shared/references/errors.md); then run
  the job-search-run evals (ask Claude to "run the evals for job-search-run") and confirm each blocked
  scenario names its `E-*` and writes a blocked record.

## 5. Single source of truth

- **Statement.** You edit `shared/references/`, then run the build; you never hand-edit a skill's
  synced copies.
- **Why.** Each skill ships self-contained (its own bundled references) so it works as a loose skill
  with no plugin system. Those copies are *generated* — editing them by hand creates drift that the
  next build silently erases.
- **Enforced by.** [scripts/build.sh](../../scripts/build.sh) regenerates every skill's bundled copies
  from the source, and CI ([.github/workflows/ci.yml](../../.github/workflows/ci.yml)) runs the build
  and fails if it changed any tracked `skills/` file — so a PR with stale or hand-edited copies is
  blocked. The rule is stated in [CONTRIBUTING.md](../../CONTRIBUTING.md#single-source-of-truth--never-hand-edit-a-skills-synced-copies).
- **How to verify.** `./scripts/build.sh` then `git status --porcelain skills` → empty output (the
  bundled copies are already in sync with the source).

## 6. Deterministic, testable, headless

- **Statement.** The mechanics — dedup, the event log, schedule lines, workspace discovery — are
  pinned written contracts (exact procedures and portable one-liners) that Claude Code executes
  natively, with **zero runtime dependencies** on the native-execution harnesses; the Hermes adapter is
  the one exception — it drives an optional bundled stdlib-Python runtime for the same deterministic
  mechanics (identical artifacts), with judgment staying in the model. The headless run reports
  outcomes through records and the digest, not through process exit codes.
- **Why.** The model handles judgment; everything else must be *specified* deterministically so any
  skill performs it identically — but it must not require an interpreter the user may not have
  on the native-execution path (Python is not assumed there; the Hermes runtime is opt-in via its
  adapter). The named tradeoff, accepted 2026-06-11: on the native path the mechanics are model-executed
  against a pinned contract rather than script-executed, so they are verified by the skill evals and the
  TESTING.md matrix; the Hermes runtime additionally executes the same contracts and is unit-tested
  (`tests/test_hermes_runtime.py`). And because a scheduled `claude -p` returns 0 even when
  it halted, success must be read from the written record, never from the exit code.
- **Enforced by.** The contracts are owned by
  [shared/references/internals.md](../../shared/references/internals.md) (registry, discovery,
  scheduling marker) and [shared/references/conventions.md](../../shared/references/conventions.md)
  (the `jobs.jsonl` event-line contract + operations); the skill evals assert on the artifacts those
  procedures produce (registry bytes, event lines). The "read the record, not the exit code" contract
  is owned by [shared/references/errors.md](../../shared/references/errors.md).
- **How to verify.** Run the skill evals (e.g. "run the evals for job-search-run") and the TESTING.md
  state/discovery checks; confirm registry writes and `jobs.jsonl` lines match the pinned contracts.

## 7. Consent-gated autonomy

- **Statement.** Scheduling uses the host's scheduler — a native *local* scheduler where one exists
  (it installs nothing on the machine), else a consent-gated machine schedule — and whichever applies,
  the agent never initiates a **silent / un-consented** privileged write; scheduling is offered as a
  yes/no, never assumed.
- **Why.** Installing a system scheduler is a privileged, persistent change to someone's machine. Where
  the host has a native *local* scheduler there's no reason for the agent to write the machine at all —
  prefer it (it installs nothing). Where none exists, a consent-gated machine schedule is allowed *as a
  fallback*: the exact line is shown first and written only on an explicit yes, and it stays
  user-removable — it's the user's machine and their explicit call. Either way the user's own machine
  stays theirs: scheduling is a yes/no they choose, never a silent install, and if they explicitly ask
  for cron the skills offer the no-install option first, then defer to their choice (decision recorded
  2026-06-11 — the former PreToolUse deny-hook was removed; it required Python on the user's machine and
  gated something the user is entitled to do). The two tiers and the "cloud schedulers don't qualify"
  test are owned by [shared/references/internals.md](../../shared/references/internals.md) (Scheduling
  setup).
- **Enforced by.** **Instruction-level + evals** — there is no runtime hook. The stance asserts **no
  silent / un-consented privileged write**; a machine schedule shown first and approved by the user (the
  Tier-2 fallback) is explicitly allowed. It is pinned in
  [shared/references/internals.md](../../shared/references/internals.md) (Scheduling setup) and
  `skills/job-search-agent/references/scheduling-and-consent.md`, stated user-facing in
  [docs/SECURITY.md](../SECURITY.md), and exercised by the job-search evals (scheduling is verified via
  the offered yes/no, the composed schedule line for the cadence, and the registry marker — not by an
  enforced prohibition).
- **How to verify.** Run the job-search evals and confirm the agent *offers* scheduling as a yes/no,
  composes the correct schedule line for the chosen cadence, records the registry marker on a yes, and
  never writes a privileged schedule *without* consent. The evals stub scheduling (no real
  crontab/launchd runs in tests), so a green eval reflects this consent + compose + record behavior, not
  an enforced prohibition.

## 8. Conversational-first configuration

- **Statement.** Users change anything by chatting with the agent; hand-editing config is an escape
  hatch, not a requirement.
- **Why.** The whole point of an agent-first product is that the conversation *is* the interface. A
  user should never have to learn a YAML schema to add a search or change cadence — they say it, and
  the agent makes the edit.
- **Enforced by.** **Cultural / by design** — this is a product principle, not a linted rule. It is
  upheld by the skills (the front door and interview drive configuration through conversation) and by
  keeping the config human-only; the file's shape is documented in
  [shared/references/conventions.md](../../shared/references/conventions.md) as the escape hatch.
- **How to verify.** Inspect [shared/references/conventions.md](../../shared/references/conventions.md)
  (human-terms-only config) and confirm the config-editing skills are conversational.

## 9. Config version stability

- **Statement.** The config schema version is never bumped to ship a feature; a version bump means a
  genuine breaking change, and an out-of-range version surfaces as a named config-version error.
- **Why.** Bumping the schema on a whim breaks every existing workspace. Reserving the version for
  real breaking changes — and detecting "config written by a newer version" as a named, fixable error
  — keeps upgrades safe.
- **Enforced by.** The config-version named error (its cause + fix) is owned by
  [shared/references/errors.md](../../shared/references/errors.md), exercised by the config-version
  halt eval in `skills/job-search-run/evals/evals.json`. That the *major* version implies a breaking
  change is the release rule in [CONTRIBUTING.md](../../CONTRIBUTING.md#versioning--bump-it-every-release).
  Whether a feature *deserves* a bump is a **cultural** judgment, not a linted gate.
- **How to verify.** Read the config-version row in
  [shared/references/errors.md](../../shared/references/errors.md); run the config-version eval and
  confirm it halts and writes a blocked record.

## 10. Prose over knobs

- **Statement.** Preferences are a prose brief, not a rubric; a preference's importance lives in which
  bucket it sits in, not in a number attached to it.
- **Why.** People describe what they want in sentences, not weights. A prose brief with must-haves /
  strong preferences / nice-to-haves captures importance structurally, which the model can reason over
  far better than a tuned scoring table — and it keeps belief 1 honest at the input side.
- **Enforced by.** The prose-brief shape (the buckets, "no weights", the qualitative vocabulary) is
  owned by [shared/references/conventions.md](../../shared/references/conventions.md);
  [scripts/philosophy_guard.py](../../scripts/philosophy_guard.py) backstops the *output* side by
  rejecting numeric scoring. The "importance = bucket" framing is restated in
  [CONTRIBUTING.md](../../CONTRIBUTING.md#project-philosophy-please-dont-regress-these). There is no
  linter over the brief's prose itself, so this is partly **cultural**.
- **How to verify.** Inspect [shared/references/conventions.md](../../shared/references/conventions.md)
  (the prose brief sections, no machine-readable contract); run `python3 scripts/philosophy_guard.py
  --root .` for the output backstop.

## 11. Docs-as-product

- **Statement.** Documentation ships with the feature, error messages name the fix, and the knowledge
  base itself is mechanically enforced — docs are part of the product, not an afterthought.
- **Why.** An agent-first product is only as good as what it can explain. If a doc drifts from the
  code, or an error tells you something broke without telling you how to fix it, the product has failed
  the user. Treating docs as a product means they are linked, fresh, and checked like code.
- **Enforced by.** [scripts/doc_lint.py](../../scripts/doc_lint.py) lints the knowledge base — links
  resolve, frontmatter and `code_refs` are valid, indexes are complete, and live docs don't duplicate
  the [shared/references/](../../shared/references/conventions.md) source of truth — and runs in CI
  ([.github/workflows/ci.yml](../../.github/workflows/ci.yml)). The structural map and the docs-as-
  product framing live in [ARCHITECTURE.md](../../ARCHITECTURE.md). That every error names its fix is
  the contract in [shared/references/errors.md](../../shared/references/errors.md).
- **How to verify.** `python3 scripts/doc_lint.py --root .` → `Doc lint: clean.`

## 12. Parallel by default

- **Statement.** Independent work runs concurrently, not in sequence — a run dispatches mutually-independent
  subtasks (e.g. one detail-read subagent per posting) wherever the host supports it, and briefs each like a
  colleague with zero context. The one carve-out: hosts that gate subagents behind explicit user approval
  (e.g. Codex) wait for that approval before fanning out; every other host parallelizes by default.
- **Why.** Time-to-value is a product feature. Parallelizing independent work turns a serial crawl into one
  concurrent step; isolating each subtask in its own subagent keeps the primary context clean and lets a faster,
  cheaper model do the bulk. A well-briefed subagent makes judgment calls — a terse one returns shallow, generic work.
- **Enforced by.** **Cultural / by design** — no linter for parallelism. The principle and the subagent-briefing
  guidance are owned by [shared/references/parallelism.md](../../shared/references/parallelism.md) (bundled into
  every skill); `job-search-run` embodies it (scan → parallel per-posting fan-out by default, sequential only
  where the host lacks the primitive or awaits subagent approval → consolidate; the `search.detail_model` and
  parallel-approval knobs live in [shared/references/conventions.md](../../shared/references/conventions.md)).
- **How to verify.** Inspect [shared/references/parallelism.md](../../shared/references/parallelism.md) and
  `skills/job-search-run/SKILL.md`; confirm mutually-independent work is dispatched concurrently by default
  (sequential only where the host lacks the primitive or awaits subagent approval), and that the fallback
  still evaluates every queued item.
