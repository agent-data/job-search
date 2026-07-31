---
title: Core Beliefs — Agent-First Operating Principles
status: current
verified: partial
last_reviewed: 2026-07-31
code_refs: [scripts/philosophy_guard.py, scripts/doc_lint.py, tests/test_philosophy_guard.py, tests/test_reference_resolution.py, tests/test_mechanics_scripts.py, skills/job-search-run/scripts/dedup.sh, .github/workflows/ci.yml]
---
# Core Beliefs — Agent-First Operating Principles

These are the beliefs that define how the agent — and the people who change it — operate. Read
this before you change product behavior: a change that regresses one of these is almost always the
wrong direction. They split by how they hold. Most are non-negotiable because they are
mechanically blocked in CI — the philosophy guard, the doc linter, the workspace validator, or a
pytest suite fails the PR, so the regression can't land. There is no build step and no hook: nothing
is generated into `skills/`, so there is nothing to check for drift. The rest are
cultural: held by review and habit rather than tooling, and each belief's
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

The runtime contracts these beliefs *protect* are owned elsewhere and are linked, never restated here —
this doc is a live design-doc subject to the `no-shared-reference-duplication` rule in
[scripts/doc_lint.py](../../scripts/doc_lint.py). How a run opens and closes and what each workspace file
holds are in the `job-search-runbook` skill; retries and what a call costs
are in the `agent-data-reference` skill; the exact fields of a config,
a run record, a job event, and the brief are the copyable examples in the `templates/` directory of
the skill that writes each one, listed in
[../../ARCHITECTURE.md](../../ARCHITECTURE.md#where-the-contracts-live).

## 1. Qualitative, never numeric

- **Statement.** Relevance is *relevant or not*, and if relevant *weak / moderate / strong*, with
  plain-language reasoning — never a 0–100 fit score, a category weight, or per-criterion points in
  shipped output.
- **Why.** Job fit is a judgment, not an arithmetic. A number invites false precision and tuning a
  rubric instead of writing better preferences; the qualitative vocabulary keeps the reasoning legible.
- **Enforced by.** [scripts/philosophy_guard.py](../../scripts/philosophy_guard.py) scans shipped
  default output (`examples/` and every skill's `templates/`) for fit scores / weights / points and
  fails the build;
  it runs in CI ([.github/workflows/ci.yml](../../.github/workflows/ci.yml)) and as
  `tests/test_philosophy_guard.py`. The relevance vocabulary it protects is defined by the
  [evaluate-job-fit](../../skills/evaluate-job-fit/SKILL.md) skill that returns it, and one judged
  posting's exact fields are `skills/job-search-run/templates/jobs-event.example.json`. A score a user explicitly
  asks for *in chat* is fine — it just must never be written into a digest, brief, or the job log.
- **How to verify.** `python3 scripts/philosophy_guard.py --root .` → `Philosophy guard: clean.`

## 2. Usage context, not budget controls

- **Statement.** Users control outcomes — frequency, sources, and review depth — with exact usage
  context at decision time and actual calls after a run, never through a monetary budget control.
- **Why.** Silently increasing metered work leaves users uninformed, while a budget knob makes them
  micromanage credits and a hard monetary cap instead of choosing the search outcome they want. The
  agent therefore previews known call impact before an increase, reports calls first afterward, and
  clearly labels any account-neutral equivalent rather than claiming an actual charge.
- **Enforced by.** [scripts/philosophy_guard.py](../../scripts/philosophy_guard.py) rejects any
  `budget` / `credits` / `cost` config field, cost knob, or unverified actual-charge claim in shipped
  output while allowing accurate calls-first usage context. What a run stores about its own metered
  work is the `agent_data_usage` block in
  `skills/job-search-run/templates/run-record.example.json`; a spent allowance is
  named where the run hits it, in the [job-search-run](../../skills/job-search-run/SKILL.md) skill;
  and canonical pricing and metering facts live only in
  the `agent-data-reference` skill.
- **How to verify.** `python3 scripts/philosophy_guard.py --root .` → `Philosophy guard: clean.`

## 3. Private & local

- **Statement.** The per-user workspace is private PII protected by a deny-all `.gitignore`; it is
  never committed, and no personal data belongs in this repo.
- **Why.** A job search is sensitive: resumes, preferences, the postings you looked at. Local-first
  with a deny-all default means the safe thing happens even if someone runs `git add` from inside the
  workspace.
- **Enforced by.** The workspace gitignore *template* ships a deny-all (`*` then `!.gitignore`) that
  the first-run setup copies in; the workspace layout and what stays off disk entirely are owned by
  the `job-search-runbook` skill. Beyond the template this
  is **cultural** — there is no CI check that scans for committed PII, so review must catch it.
- **How to verify.** Inspect `skills/job-search/templates/workspace.gitignore` (the deny-all template)
  and confirm no
  workspace contents are tracked.

## 4. No silent failures — named errors

- **Statement.** Every blocked path is named where it is hit, in the words a user would use, with a cause
  and a fix — and it reaches the user through the digest and the home view, plus a desktop notification
  where supported. There is no error-code catalogue and no internal token that could leak into either.
- **Why.** A headless run that fails quietly is worse than no run. Naming each failure — with the fix
  attached — means a user always learns what to do next, and never has to read a log to find out a run
  did nothing. A code was never what the user read; the sentence next to the failing step was, so the
  codes went and the sentences stayed.
- **Enforced by.** The run's close carries it: a run that stops still writes `runs/<run_id>.json` with
  `close_state: blocked` and `run_health: degraded` (the shape is `skills/job-search-run/templates/run-record.example.json`)
  plus a digest whose body is the cause and the fix, *before* it stops — because a headless `claude -p`
  exits 0 even when blocked, so the record is the only trustworthy signal. The start-to-close sequence is
  owned by the `job-search-runbook` skill, and
  `validate-workspace.sh --post-close <run_id>` checks that even a run that stopped early left no
  started-marker and no scratch. The behavior is graded by the live evals in `evals/` — B9 covers a run
  killed mid-flight — and by the blocked scenarios in `skills/job-search-run/evals/evals.json`.
- **How to verify.** Read the "One run, start to close" section of
  the `job-search-runbook` skill; then run the job-search-run
  evals (ask Claude to "run the evals for job-search-run") and confirm each blocked scenario writes its
  record and a digest a user could act on without reading a log.

## 5. Single source of truth

- **Statement.** Each fact has exactly one canonical home in a reference skill; other skills invoke it
  in place under the guaranteed bundle install. No fact is hand-copied, and no reference is fanned into
  per-skill copies tracked in source.
- **Why.** Every supported host installs the whole pack via its manifest — there is no loose
  single-skill install — so a skill resolves a sibling reference under the bundle (the corpus
  compose-by-reference model, AAS-PACK-02/BOUND-03). Where a host cannot resolve a path outside a
  skill's own directory, the build assembles that host's self-contained copies from the single source
  (AAS-DIST-03) — a generated copy, never hand-maintained.
- **Enforced by.** There is no build step at all now — nothing is generated into `skills/`, so
  there is nothing to fall out of sync. What holds the property is
  [scripts/doc_lint.py](../../scripts/doc_lint.py)'s duplication check
  (`no-shared-reference-duplication`, which guards both the knowledge base and the reference skills
  itself) and the per-host resolution tests in
  [tests/test_reference_resolution.py](../../tests/test_reference_resolution.py).
- **How to verify.** `git ls-files 'skills/*/references/*.md'` prints nothing — there are no
  skill-local reference files left; every skill invokes the two reference skills by name.
  `python3 -m pytest -q tests/test_reference_resolution.py` → every in-place pointer resolves under
  each host's install.

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
  `skills/job-search-runbook/scripts/` — dedup, the event-log append, schedule-line composition, workspace
  discovery, and `validate-workspace.sh`, which decides whether a workspace on disk obeys the file
  rules. The prose those scripts pair with is the `job-search-runbook` skill
  (find the workspace, what each file holds, one run start to close); the runner invokes the script
  where a shell runtime exists and follows the runbook's steps otherwise.
  `tests/test_mechanics_scripts.py` drives each script through `sh` against a temp fixture and
  `tests/test_validate_workspace.py` drives the validator against workspaces built per case, so the
  rules are mechanically checked rather than asserted in prose. "Read the record, not the exit code"
  is belief 4's close contract, in the same runbook.
- **How to verify.** Run `python3 -m pytest tests/test_mechanics_scripts.py tests/test_validate_workspace.py`,
  then the live evals in `evals/` (e.g. `python3 evals/run_eval.py --case headless-run --model sonnet`)
  and confirm the captured workspace passes `validate-workspace.sh --post-close <run_id>`.

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
  unattended-first model (session loop as its named fallback) and the canary are owned by the front-door
  skill [skills/job-search/SKILL.md](../../skills/job-search/SKILL.md), which offers the schedule, runs the
  canary, and records the marker only on a green one; the `job-search-runbook` skill
  ("Running it unattended") gives the shape of the command a scheduler has to run.
- **Enforced by.** **Instruction-level + evals** — there is no runtime hook. The stance asserts **no
  silent / un-consented privileged write**, and now that the advocated default is an unattended schedule (a
  real machine change) the same gate covers it: shown first, approved on a yes, user-removable. The
  unattended-first model, the in-session-loop fallback, and the mandatory **config-time canary** are pinned
  in [skills/job-search/SKILL.md](../../skills/job-search/SKILL.md) and stated user-facing in
  [docs/SECURITY.md](../SECURITY.md). The canary's proof routes through the **written record** — a run
  record with `trigger: scheduled` and a healthy close, read from the artifact rather than the process exit
  code (belief 6). Graded by the `schedule` eval case (behavior row B11) and by the job-search scenario
  suite: the yes/no offer, the composed schedule line for the cadence, and the registry marker — not an
  enforced prohibition.
- **How to verify.** Run the job-search evals and confirm the agent *offers* scheduling as a yes/no,
  composes the correct schedule line for the chosen cadence, and — on a yes — records the registry marker,
  never writing a privileged schedule *without* consent. Because the evals stub scheduling (no real
  crontab/launchd runs in tests), the canary's "prove the real invocation before recording" gate is
  verified by the `schedule` case, which installs a real scheduler entry and reads the run record the canary
  wrote: `python3 evals/run_eval.py --case schedule --model sonnet` (remove the entry after grading). The
  marker is written only after that record shows a healthy close.

## 8. Conversational-first configuration

- **Statement.** Users change anything by chatting with the agent; hand-editing config is an escape
  hatch, not a requirement.
- **Why.** The whole point of an agent-first product is that the conversation *is* the interface. A
  user should never have to learn a YAML schema to add a search or change cadence — they say it, and
  the agent makes the edit.
- **Enforced by.** **Cultural / by design** — this is a product principle, not a linted rule. It is
  upheld by the skills (the front door and interview drive configuration through conversation) and by
  keeping the config human-only; the file's shape is the copyable
  [config.example.yaml](../../skills/job-search/templates/config.example.yaml), which is the escape hatch.
- **How to verify.** Read [config.example.yaml](../../skills/job-search/templates/config.example.yaml) — every key
  is in human terms, with no tuning knob — and confirm the config-editing skills are conversational.

## 9. Config version stability

- **Statement.** The `config.yaml` schema version is never bumped to ship a feature; a bump means a
  genuine breaking change that an existing workspace cannot survive unchanged.
- **Why.** Bumping the schema on a whim breaks every existing workspace. Reserving the version for real
  breaking changes is what lets a release add keys — `schedule.consented`, `search.max_new_postings_per_run` —
  without touching anyone's workspace, and lets a run ignore a key an older workspace still carries.
- **Enforced by.** **Cultural**, backed by one mechanical check.
  `skills/job-search-runbook/scripts/validate-workspace.sh` requires `version` to be present and numeric and says
  nothing about its value, so an older workspace keeps working — that permissiveness is the point, and it
  is what makes bumping the version a deliberate act rather than a side effect. Whether a change *deserves*
  a bump is a judgment; the release rule for the plugin version, and the requirement that a release note
  say what an existing workspace must do, are in
  [CONTRIBUTING.md](../../CONTRIBUTING.md#versioning--bump-it-every-release).
- **How to verify.** Read the config-check block in
  [skills/job-search-runbook/scripts/validate-workspace.sh](../../skills/job-search-runbook/scripts/validate-workspace.sh)
  (required keys: `version`, `queries`, `search.sources`, `schedule`), then check that the newest CHANGELOG
  entry has a **Compatibility** section whenever it changed what a run writes into a workspace.

## 10. Prose over knobs

- **Statement.** Preferences are a prose brief, not a rubric; a preference's importance lives in which
  bucket it sits in, not in a number attached to it.
- **Why.** People describe what they want in sentences, not weights. A prose brief with must-haves /
  strong preferences / nice-to-haves captures importance structurally, which the model can reason over
  far better than a tuned scoring table — and it keeps belief 1 honest at the input side.
- **Enforced by.** The prose-brief shape — the buckets, no weights, the qualitative vocabulary — is shown
  by [preferences.example.md](../../skills/job-preference-interview/templates/preferences.example.md) and built by the
  [job-preference-interview](../../skills/job-preference-interview/SKILL.md) skill;
  [scripts/philosophy_guard.py](../../scripts/philosophy_guard.py) backstops the *output* side by
  rejecting numeric scoring. The "importance = bucket" framing is restated in
  [CONTRIBUTING.md](../../CONTRIBUTING.md#project-philosophy-please-dont-regress-these). There is no
  linter over the brief's prose itself, so this is partly **cultural**.
- **How to verify.** Read
  [preferences.example.md](../../skills/job-preference-interview/templates/preferences.example.md) — prose
  sections, no machine-readable rubric; run `python3 scripts/philosophy_guard.py --root .` for the output
  backstop.

## 11. Docs-as-product

- **Statement.** Documentation ships with the feature, error messages name the fix, and the knowledge
  base itself is mechanically enforced — docs are part of the product, not an afterthought.
- **Why.** An agent-first product is only as good as what it can explain. If a doc drifts from the
  code, or an error tells you something broke without telling you how to fix it, the product has failed
  the user. Treating docs as a product means they are linked, fresh, and checked like code.
- **Enforced by.** [scripts/doc_lint.py](../../scripts/doc_lint.py) lints the knowledge base — links
  resolve, frontmatter and `code_refs` are valid, indexes are complete, and live docs don't duplicate
  the reference skills' source of truth — and runs in CI
  ([.github/workflows/ci.yml](../../.github/workflows/ci.yml)). The structural map and the docs-as-
  product framing live in [ARCHITECTURE.md](../../ARCHITECTURE.md). That every failure names its fix is
  belief 4, carried by each skill next to the step that can hit it.
- **How to verify.** `python3 scripts/doc_lint.py --root .` → `Doc lint: clean.`

## 12. Parallel by default

- **Statement.** Independent work runs concurrently, not in sequence — a run dispatches one detail-read
  subagent per posting wherever the host has subagents, and briefs each like a colleague with zero context.
  Where the host has none, or gates subagents behind explicit user approval (Codex), the run works the list
  in order instead. Both paths run on the host's own model; nothing pins a separate model for the search.
- **Why.** Time-to-value is a product feature. Parallelizing independent work turns a serial crawl into one
  concurrent step, and isolating each detail read in its own subagent keeps the primary context clean — the
  run consolidates the verdicts rather than carrying every job description. A well-briefed subagent makes
  judgment calls; a terse one returns shallow, generic work, which is why the brief matters more than the
  fan-out. The setup-time model binding this belief used to carry was removed on 2026-07-31: it made setup
  ask a question users could not answer, and pinning a model bought nothing the host's own model did not
  already give.
- **Enforced by.** **Cultural / by design** — no linter for parallelism. The behavior lives in
  [skills/job-search-run/SKILL.md](../../skills/job-search-run/SKILL.md): scan, fan out one subagent per
  posting on the read list, work in order where the host cannot, then consolidate. The optional
  `search.parallel_detail_reads` key in
  [config.example.yaml](../../skills/job-search/templates/config.example.yaml) records that a user approved
  subagents on a host that asks.
- **How to verify.** Read the detail-read step of
  [skills/job-search-run/SKILL.md](../../skills/job-search-run/SKILL.md) and the brief it hands each
  subagent; confirm independent work is dispatched concurrently by default, and that the in-order path
  still reaches a judgment for every posting on the list.
