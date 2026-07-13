---
title: Core Beliefs — Agent-First Operating Principles
status: current
verified: partial
last_reviewed: 2026-07-12
code_refs: [scripts/philosophy_guard.py, scripts/doc_lint.py, scripts/build.sh, tests/test_reference_resolution.py, tests/test_mechanics_scripts.py, shared/scripts/mechanics/dedup.sh, .github/workflows/ci.yml, shared/references/internals.md, shared/references/conventions.md]
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

- **Statement.** Each fact has exactly one canonical home in `shared/references/`; skills reference it
  in place under the guaranteed bundle install. No fact is hand-copied, and no reference is fanned into
  per-skill copies tracked in source.
- **Why.** Every supported host installs the whole pack via its manifest — there is no loose
  single-skill install — so a skill resolves a sibling reference under the bundle (the corpus
  compose-by-reference model, AAS-PACK-02/BOUND-03). Where a host cannot resolve a path outside a
  skill's own directory, the build assembles that host's self-contained copies from the single source
  (AAS-DIST-03) — a generated copy, never hand-maintained.
- **Enforced by.** [scripts/build.sh](../../scripts/build.sh) (assembly only where a host needs it;
  today every host resolves in place, so it regenerates only the content-hash build stamp),
  [scripts/doc_lint.py](../../scripts/doc_lint.py)'s intra-reference duplication check
  (`no-shared-reference-duplication`, which guards `shared/references/` and the skill-local originals
  directly), and the per-host resolution marker tests in
  [tests/test_reference_resolution.py](../../tests/test_reference_resolution.py).
- **How to verify.** `git ls-files 'skills/*/references/*.md'` lists only the four skill-local
  originals (`home.md`, `onboarding.md`, `customization.md`, `scheduling-and-consent.md`) — no fanned
  copies; `python3 -m pytest -q tests/test_reference_resolution.py` → every in-place pointer resolves
  under each host's install; `./scripts/build.sh` then `git status --porcelain` → empty (the stamp is
  already current).

## 6. Deterministic, testable, headless

- **Statement.** The fiddly deterministic mechanics are bundled as portable scripts where a runtime
  exists (AAS-FORM-08), each paired with a named prose-contract fallback for hosts without one
  (AAS-PORT-01); no third-party runtime dependency ships (AAS-DIST-05). Success is read from the
  written record, never the process exit code.
- **Why.** The model handles judgment; everything else must be *specified* deterministically so any
  skill performs it identically. The scripted form is verified by unit tests; the prose fallback and
  the judgment layer by the skill evals. This supersedes the 2026-06-11 zero-Python decision for the
  mechanics only — no *third-party* runtime dependency ships (the scripts are the skills' own portable
  shell, AAS-DIST-05), and portable **shell** (near-universal) shrinks the no-runtime surface so the
  mandatory fallback stays a thin residual, not a second full implementation. And because a scheduled
  `claude -p` returns 0 even when it halted, success must be read from the written record, never from
  the exit code.
- **Enforced by.** The mechanics are bundled as portable POSIX-`sh` scripts under
  `shared/scripts/mechanics/` (dedup, the event log, schedule-line composition, workspace discovery),
  each reproducing — and paired with — the pinned prose contract owned by
  [shared/references/internals.md](../../shared/references/internals.md) (registry, discovery,
  scheduling marker) and [shared/references/conventions.md](../../shared/references/conventions.md)
  (the `jobs.jsonl` event-line contract + operations); the runner invokes the script where a shell
  runtime exists and follows the named prose fallback otherwise. `tests/test_mechanics_scripts.py`
  pins the scripted form to the contract; the skill evals assert on the artifacts those procedures
  produce (registry bytes, event lines). The "read the record, not the exit code" contract is owned by
  [shared/references/errors.md](../../shared/references/errors.md).
- **How to verify.** Run `python3 -m pytest tests/test_mechanics_scripts.py` (the scripted mechanics
  reproduce their pinned contracts) plus the skill evals (e.g. "run the evals for job-search-run") and
  the TESTING.md state/discovery checks; confirm registry writes and `jobs.jsonl` lines match the
  pinned contracts.

## 7. Consent-gated autonomy

- **Statement.** Scheduling advocates an **unattended** schedule — a recurring run that fires with **no
  interactive session open**, on the host's or OS's own scheduler that survives session-close — as the
  default; a session-bound in-session loop is a **named fallback**. It stays **consent-gated**: the exact
  machine change is shown first, written only on an explicit yes, and stays user-removable, and the agent
  never initiates a **silent / un-consented** privileged write. And it never records a schedule as active
  until a **config-time canary** has proven the real unattended invocation succeeds — writes the workspace,
  reaches agent-data. Scheduling is offered as a yes/no, never assumed.
- **Why.** A search only earns its keep if it runs when the user isn't watching, and an in-session loop
  stops the instant the session closes — so the overnight and next-morning runs, the ones that matter most,
  silently never fire. This is a **conscious amendment**: the advocacy flips from *installs-nothing* (the
  old native-local-scheduler preference) to *unattended-reliable*. The re-weighting is
  **reliability > installs-nothing** — the install-nothing convenience yields to a schedule that actually
  fires — but never *silent > consented*: an unattended schedule is a real, privileged machine change, so
  its consent gate is preserved intact (`AAS-AUTO-02`, spend consent on the one-way door). It stays the
  user's machine and their explicit call — if they ask for cron outright, the no-install option is offered
  first, then their choice defers (the 2026-06-11 removal of the Python-dependent PreToolUse deny-hook
  stands: it gated something the user is entitled to do). The mandatory **canary** closes the gap this
  targets — a run that silently lacked permission to write the workspace or reach agent-data, discovered
  only the next day (belief 4: no silent failures) — by proving the *real* unattended invocation works
  before the schedule is called active (`PSG-SUB-06`, prove it works, not that it exists). The
  unattended-first model (session loop as its named fallback), the "cloud schedulers don't qualify" test,
  and the canary spec are owned by `skills/job-search-agent/references/scheduling-and-consent.md` and
  [shared/references/internals.md](../../shared/references/internals.md) (Scheduling setup).
- **Enforced by.** **Instruction-level + evals** — there is no runtime hook. The stance asserts **no
  silent / un-consented privileged write**, and now that the advocated default is an unattended schedule (a
  real machine change) the same gate covers it: shown first, approved on a yes, user-removable. The
  unattended-first model, the in-session-loop fallback, the "cloud schedulers don't qualify" test, and the
  mandatory **config-time canary** are pinned in
  [shared/references/internals.md](../../shared/references/internals.md) (Scheduling setup) and
  `skills/job-search-agent/references/scheduling-and-consent.md`, and stated user-facing in
  [docs/SECURITY.md](../SECURITY.md). The canary's proof routes through the **written record** — success
  read from the run artifact, not the process exit code (belief 6) — the same no-silent-failure channel
  owned by [shared/references/errors.md](../../shared/references/errors.md). Exercised by the job-search
  evals (scheduling is verified via the offered yes/no, the composed schedule line for the cadence, and the
  registry marker — not by an enforced prohibition).
- **How to verify.** Run the job-search evals and confirm the agent *offers* scheduling as a yes/no,
  composes the correct schedule line for the chosen cadence, and — on a yes — records the registry marker,
  never writing a privileged schedule *without* consent. Because the evals stub scheduling (no real
  crontab/launchd runs in tests), the canary's "prove the real invocation before recording" gate is
  verified by inspecting the pinned flow in
  `skills/job-search-agent/references/scheduling-and-consent.md` +
  [shared/references/internals.md](../../shared/references/internals.md) (marker set only after Verify passed —
  a green canary for the unattended schedule, or the loop fallback's observed first-fire run record); a green
  eval reflects the consent + compose + record behavior, not an enforced prohibition or a
  live canary.

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
  (e.g. Codex) wait for that approval before fanning out; every other host parallelizes by default. The tier
  binds to a concrete model by the agent's self-selection from its own roster — not a per-host adapter table
  (the `AAS-LANG-04` deviation for this adapter-free pack); the required-slot rule (`AAS-AUTO-07`) and the
  judgment-never-cheapest floor (`AAS-AUTO-11`) are the mitigation for the one host fact with no runtime
  backstop.
- **Why.** Time-to-value is a product feature. Parallelizing independent work turns a serial crawl into one
  concurrent step; isolating each subtask in its own subagent keeps the primary context clean and dispatches each
  isolated subtask on the least powerful model that can do it *well* — sp's spectrum: mechanical steps (dedup,
  provenance, extraction, prefilter) on the cheapest tier; the per-posting fit verdict, a well-specified
  bite-sized review, at the reviewer floor (a mid-tier model), scaled up for higher-risk postings; the
  dispatching model always specified explicitly. A well-briefed subagent makes judgment calls — a terse one returns shallow, generic work.
- **Enforced by.** **Cultural / by design** — no linter for parallelism. The principle and the subagent-briefing
  guidance are owned by [shared/references/parallelism.md](../../shared/references/parallelism.md) (bundled into
  every skill); `job-search-run` embodies it (scan → parallel per-posting fan-out by default, sequential only
  where the host lacks the primitive or awaits subagent approval → consolidate; the `search.detail_model` and
  parallel-approval knobs live in [shared/references/conventions.md](../../shared/references/conventions.md)).
  Model self-selection is owned by the runner (`skills/job-search-run/SKILL.md`) + `parallelism.md`, with **no
  adapter model-tier table**: the `config.yaml search.detail_model` tier token is the portable intent, and the
  agent binds the concrete model from its own roster.
- **How to verify.** Inspect [shared/references/parallelism.md](../../shared/references/parallelism.md) and
  `skills/job-search-run/SKILL.md`; confirm mutually-independent work is dispatched concurrently by default
  (sequential only where the host lacks the primitive or awaits subagent approval), and that the fallback
  still evaluates every queued item.
