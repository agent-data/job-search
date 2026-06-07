---
title: Core Beliefs — Agent-First Operating Principles
status: current
verified: partial
last_reviewed: 2026-06-07
code_refs: [scripts/philosophy_guard.py, hooks/guard-scheduled-tasks.py, scripts/build.sh, .github/workflows/ci.yml, scripts/osctl.py, scripts/state.py]
---
# Core Beliefs — Agent-First Operating Principles

These are the non-negotiable beliefs that define how the agent — and the people who change it —
operate. Read this before you change product behavior: a change that regresses one of these is
almost always the wrong direction, and several are mechanically blocked in CI. The beliefs
themselves are the canonical framing in [CONTRIBUTING.md](../../CONTRIBUTING.md#project-philosophy-please-dont-regress-these);
this doc adds the *enforcement* — for each belief, where it lives in the code and how to check it.

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

- **Statement.** You edit `shared/references/` and `scripts/`, then run the build; you never hand-edit
  a skill's synced copies.
- **Why.** Each skill ships self-contained (its own bundled references + helper scripts) so it works
  as a loose skill with no plugin system. Those copies are *generated* — editing them by hand creates
  drift that the next build silently erases.
- **Enforced by.** [scripts/build.sh](../../scripts/build.sh) regenerates every skill's bundled copies
  from the source, and CI ([.github/workflows/ci.yml](../../.github/workflows/ci.yml)) runs the build
  and fails if it changed any tracked `skills/` file — so a PR with stale or hand-edited copies is
  blocked. The rule is stated in [CONTRIBUTING.md](../../CONTRIBUTING.md#single-source-of-truth-never-hand-edit-a-skills-synced-copies).
- **How to verify.** `./scripts/build.sh` then `git status --porcelain skills` → empty output (the
  bundled copies are already in sync with the source).

## 6. Deterministic, testable, headless

- **Statement.** The mechanics are deterministic, dependency-free stdlib Python; the headless run
  reports outcomes through records and the digest, not through process exit codes.
- **Why.** The model handles judgment; everything else — dedup, folding the event log, schedule lines,
  workspace discovery — must be deterministic so it can be unit-tested and trusted. And because a
  scheduled `claude -p` returns 0 even when it halted, success must be read from the written record,
  never from the exit code.
- **Enforced by.** The pytest suite over [scripts/state.py](../../scripts/state.py) and
  [scripts/osctl.py](../../scripts/osctl.py) (`tests/test_state.py`, `tests/test_osctl.py`) pins the
  deterministic behavior; CI runs it on every push and PR. The "read the record, not the exit code"
  contract is owned by [shared/references/errors.md](../../shared/references/errors.md).
- **How to verify.** `python3 -m pytest -q` → all tests pass.

## 7. Consent-gated autonomy

- **Statement.** The model suggests; it never silently performs a privileged scheduling install. A
  PreToolUse hook gates those writes — *ask* for the default mechanism, *ask* when the user explicitly
  chose a non-default, and *deny* when the model reached for a non-default unprompted.
- **Why.** Installing a system scheduler is a privileged, persistent change. Autonomy is fine for
  suggestions and reversible work, but a write that survives the session needs the human in the loop —
  and a model-initiated non-default escalation should be refused outright.
- **Enforced by.** [hooks/guard-scheduled-tasks.py](../../hooks/guard-scheduled-tasks.py) makes a
  deterministic decision from the command plus a short-lived "who chose" marker that
  [scripts/osctl.py](../../scripts/osctl.py) writes (`set-sched-intent`); reads, `/loop`, and schedule
  *removal* are intentionally not gated.
- **How to verify.** `python3 -m pytest -q tests/test_guard_scheduled_tasks.py` → the ask/deny/defer
  cases pass.

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
