# Reliability

How Job Search stays trustworthy: a deterministic core, named failures, bounded retries,
and failures that surface where the user will actually see them. This doc describes the
*mechanisms*. It does **not** restate any runtime contract. Each concrete value has one home
elsewhere: how a run opens and closes and what each workspace file holds are in
the `job-search-runbook` skill; retry rules and what a call
costs are in the `agent-data-reference` skill; the exact
fields of a config, a run record, a `jobs.jsonl` line, and the brief are the copyable examples in the
`templates/` directory of the skill that writes each one, listed in
[../ARCHITECTURE.md](../ARCHITECTURE.md#where-the-contracts-live); and whether a workspace on disk obeys
those rules is decided by
[skills/job-search-runbook/scripts/validate-workspace.sh](../skills/job-search-runbook/scripts/validate-workspace.sh).
When a number or a literal matters, follow the link to its source of truth.

The design choice behind §2 and §4 — no silent failures, every blocked path named where it is
hit — is stated in
[../CONTRIBUTING.md](../CONTRIBUTING.md#project-philosophy-please-dont-regress-these); for the
structural map see [../ARCHITECTURE.md](../ARCHITECTURE.md).

**TL;DR (reading this mid-incident).** Run-health states and *how a blocked run surfaces without a
trustworthy exit code* both live in [§4](#4-run-health--blocked-surfacing--visible-without-the-exit-code).
There is no error-code catalogue to look a message up in: a run that stops writes what stopped it, in plain
words, into its record and its digest. The record's shape is
[`run-record.example.json`](../skills/job-search-run/templates/run-record.example.json). Jump by symptom:

| If you're chasing… | Go to |
|---|---|
| a blocked run / where the failure reaches the user / the `claude -p` exit-code trap | [§4 Run health & blocked surfacing](#4-run-health--blocked-surfacing--visible-without-the-exit-code) |
| why a call was (or wasn't) retried, the circuit-breaker | [§3 Retry & circuit-breaker](#3-retry--circuit-breaker--patient-then-it-stops) |
| "is this a silent failure?" / what a stopped run owes the user | [§2 No silent failures](#2-no-silent-failures--every-blocked-path-is-named) |
| state that looks corrupted or non-reproducible | [§1 Determinism](#1-determinism--the-core-is-a-pinned-contract-and-reproducible) |
| whether the scheduled (headless) run hung on a prompt | [§5 Headless-first](#5-headless-first--the-scheduled-run-never-blocks-on-a-human) |
| "what actually proves any of this" — tests, evals, the fake shim | [§6 Testing & evals](#6-testing--evals--what-actually-guarantees-the-above) |
| a doc that drifted from the contract it points at | [§7 Reliability of the docs](#7-reliability-of-the-docs-themselves) |

---

## 1. Determinism — the core is a pinned contract and reproducible

The mechanics that must never improvise — workspace discovery, registry writes, the schedule
line, dedup, working out a posting's current state from its lines — are **pinned written
contracts**: exact precedence rules,
portable shell one-liners, and byte-level write rules that Claude Code executes natively with
no runtime dependency (no Python on the user's machine). The *specification* is deterministic —
the same frequency always composes the same schedule line, and the same event log always gives
the same current state — while the *executor* is the model following the contract verbatim.
Two layers verify this. `tests/test_mechanics_scripts.py` drives each script through `sh` against a
temp fixture, and `tests/test_validate_workspace.py` drives the validator against workspaces built
per case — so the file rules and the scripted operations are unit-tested. What a *run* does with
them end to end is graded by the live behavior evals the maintainer runs against the real API and by
the [../TESTING.md](../TESTING.md) matrix, because that part is the model following the contract.

State is an **append-only event log**, not a mutable record: `jobs.jsonl` is a sequence of
events, and a posting's current state is its last `evaluated` line for its `source` and
`source_id`. A posting carries at most one such line: both append paths refuse a second
`evaluated` event for a pair that already has one.
[`event-log-append.sh`](../skills/job-search-run/scripts/event-log-append.sh) skips it, and
[`record-judgment.sh`](../skills/job-search-run/scripts/record-judgment.sh) writes nothing —
exiting 0 when the line it was asked to write is the one already recorded, and 1 with both lines
on stderr when it is not.
Re-running is therefore safe — nothing is overwritten in place, and a crash mid-run can at
worst leave a trailing partial line, never a corrupted record. What each workspace file holds, the
registry write rules, the workspace-discovery precedence, and the scheduling marker are all owned by
the `job-search-runbook` skill; one event line's exact
fields are [`jobs-event.example.json`](../skills/job-search-run/templates/jobs-event.example.json), and
the scripts that append every line and read the counts back out are under
[../skills/job-search-run/scripts/](../skills/job-search-run/scripts/).

Because the deterministic pieces are isolated from the LLM judgment, the parts that *can* be
proven correct *are* — the model is left to do only what genuinely needs judgment (relevance),
and everything else is testable.

Deeper company-board coverage adds two bounded state rules. Pagination stops a stream when its
cursor or page signature stops making trustworthy progress, so a bad continuation cannot loop or
restart at page one. Once continuation begins, the candidate pool moves through a private run-scoped
scratch directory in bounded chunks, which the close deletes along with the started-marker; a later
run deletes stale scratch rather than resuming it. Both the scratch rule and the run's start-to-close
sequence are owned by the `job-search-runbook` skill.

## 2. No silent failures — every blocked path is named

The system never fails quietly. Every condition that stops or degrades a run is named where it is
hit, in the words a user would use, with a **cause and a concrete fix** — not a stack trace and not
a code. This covers the full surface a run can hit: a missing or unauthenticated CLI, a missing
config or preferences brief, an unreachable or degraded job source, a malformed query, a repeated
upstream outage, and a spent API allowance.

There is deliberately **no error-code catalogue**. The `E-*` codes that used to carry this wording
were retired on 2026-07-31 along with the reference file that held them, because the code was never
what the user read — the sentence next to the failing step was. Each skill now names the failures its
own flow can hit, right beside the step that hits them, and the run's `close_state` (`complete` /
`blocked` / `interrupted`) is what a later reader keys off. That means what a failure "is" is checked
by reading the digest and the record, not by matching a token: the maintainer's live behavior evals
grade exactly that.

An interrupted continuation is degraded rather than hidden: the run keeps trustworthy postings
already scanned, marks the affected stream and overall depth incomplete, continues healthy streams,
and says in the digest that coverage was partial. It never claims exhaustive coverage or persists a
cursor for later resumption.

That "name it, never swallow it" rule is one of the design choices a change must not regress,
stated in [../CONTRIBUTING.md](../CONTRIBUTING.md#project-philosophy-please-dont-regress-these).
No linter checks it. What holds it is review, the scenarios in
`skills/job-search-run/evals/evals.json` that assert a blocked close writes both the record and a
digest carrying the cause and the fix, and the maintainer's live behavior evals.

## 3. Retry & circuit-breaker — patient, then it stops

Upstream calls (the metered searches and detail fetches) can fail transiently, so the run
retries — but only the failures the contract marks **retryable**. The branch keys on the error
envelope's `retryable` boolean, never on parsing the error code string: a transient upstream
failure (the 502s) is retried with bounded exponential backoff and jitter; a deterministic
client error (a bad field, an invalid request, a stale id/URL pair) is **never** retried,
because retrying it would only waste a metered call and still fail. The exact attempt count,
the backoff schedule, and which codes are retryable are owned by
the `agent-data-reference` skill —
paraphrased here, authoritative there.

Retries are also **bounded across the run**, not just per call — the circuit-breaker. If the
job source keeps failing search after search, the run stops searching rather than hammering a
struggling upstream, and reports what it managed to gather, naming that source as lost. A single
stale detail link, by contrast, is expected rather than a failure: that posting falls back to
summary-only judgment with a footnote and the run carries on. The strategy in one line: be patient
with transient failures, give up immediately on deterministic ones, and break the circuit when an
upstream is clearly down.

Usage accounting follows attempts, not just successful logical operations. Each completed metered
attempt is classified once; retries and charged failures remain diagnostic subsets, while free routes
and a quota-rejected attempt stay outside the metered total. That same local ledger supplies the
calls-first digest line and the exact prior-work count when quota stops a run, avoiding both double
counting and an invented account charge. The canonical counting rules live in
the `agent-data-reference` skill, and the
stored record shape lives in the `job-search-runbook` skill.

## 4. Run health & blocked surfacing — visible without the exit code

Every run records a **health state** in its `runs/<run_id>.json` record, and the digest leads with
that state. The record also carries how the run ended, separately from how healthy it was:
`close_state` is `complete`, `blocked`, or `interrupted`, while `run_health` is `healthy` or
`degraded`. Both live in the `job-search-runbook` skill, and the
record's full shape is
[`run-record.example.json`](../skills/job-search-run/templates/run-record.example.json).
The two are independent on purpose: a run can finish all its work with a source lost along the way
(`complete` + `degraded`).

The important reliability property is *how* a blocked run reaches the user. It does **not** rely
on the process exit code: a headless `claude -p` invocation returns `0` even when the run was
blocked (a skill cannot set the harness process's exit status), so a headless run's `$?` is not a
trustworthy signal and the docs never tell the user to check it. Instead, a blocked run surfaces
three records-based ways:

- the **blocked digest** — the cause and the fix replace the match list as the body;
- a **desktop notification** on a blocked run (toggled by a notify setting in `config.yaml`); and
- the **home view** on the user's next front-door visit (the `job-search` skill), which reads the
  health state from the newest run record.

So that surfacing always works, **every** halting path writes its `runs/<run_id>.json` blocked
record *before* it stops — that record is the source the home view reads, so a scheduled run
that failed overnight is named the next time the user opens the front door. The one exception is
the no-workspace / first-run case: there is nowhere to write a record, but the failure is
inherently visible because the next front-door visit routes to onboarding.

A run that is killed outright can't write anything, so the contract handles it from the other end:
a run creates the empty marker `runs/.started-<run_id>` when it opens and deletes it only at close.
A marker with no matching record means the previous run died mid-flight, and the next run says so
before doing anything else, then closes and clears it — the run contract's first step, which is
what leaves a record of the run that died. The run loop that enforces all of this is
[../skills/job-search-run/SKILL.md](../skills/job-search-run/SKILL.md).

## 5. Headless-first — the scheduled run never blocks on a human

The scheduled pass is strictly **non-interactive**: it never prompts, because there is no human
watching when the scheduled run fires. Anything that would need a decision is instead resolved by the
contract (retry vs. skip vs. halt) and recorded. All user-facing output is **records-based** —
the digest file, the run audit log, the desktop notification — never an interactive prompt the
scheduler can't answer. This is what makes the system safe to run unattended: a headless run
either completes and writes a digest, or halts and writes a named blocked record, and in both
cases the next interactive front-door visit shows the result. The headless run loop and its
surfacing rules are specified in
[../skills/job-search-run/SKILL.md](../skills/job-search-run/SKILL.md).

## 6. Testing & evals — what actually guarantees the above

Reliability claims are only as good as their tests. Four layers back this system:

- **A pytest suite over the dev tooling** ([../tests/](../tests/)) exercises the doc linter, the
  philosophy guard, the release-integrity checks, the mechanics scripts, and the shims' own
  behavior.
- **The workspace validator** ([skills/job-search-runbook/scripts/validate-workspace.sh](../skills/job-search-runbook/scripts/validate-workspace.sh)),
  self-tested by `tests/test_validate_workspace.py`, is what turns the file rules into something
  mechanical: config keys, the brief's front matter, run-record fields and UTC timestamps, and —
  with `--post-close <run_id>` — that the run left no started-marker and no scratch behind, that
  its record carries `degraded_reasons`, that every count in its record is the number
  `run-counts.sh` reads back out of `jobs.jsonl`, each match band and each source the log names
  included, that the record's own three sums hold with or without a log, and that its
  `completed_at` is neither earlier than `started_at` nor later than the record's own mtime. Those
  rules used to be prose in the skills, which meant nothing checked them.
- **A credit-free fake `agent-data` shim** (a PATH shim under [../tests/](../tests/)) lets a
  whole run be driven with deterministic, injectable upstream behavior — a spent allowance, an
  outage, stale links, a degraded service, cursor chains, malformed pagination — with **no network
  and no metered calls**, so the failure, progress, and retry paths in §2–§4 can be exercised
  repeatedly and for free.
- **The live behavior evals** the maintainer runs check the *model's* behavior against the real
  API: each spawns a real session, captures the transcript and the workspace it produced, and a
  grader reads them. They are not in this repository. This is the layer that proves the reliability
  claims above — that a blocked gate really does close the run and say what stopped it, that a
  killed run is reported on the next pass, that judgment stays qualitative. Scenario suites in the
  five user-facing skills, at `skills/<skill>/evals/evals.json`, cover routing and narrower flows
  against the shim.
- **CI** ([../.github/workflows/ci.yml](../.github/workflows/ci.yml)) runs four gates on every
  change: the pytest suite, the philosophy guard, the doc linter, and the release-integrity check.
  `scripts/eval_harness.py`, which checks that those five scenario files are well formed, is a
  local pre-PR step rather than a CI job.

Honest scope (per [QUALITY_SCORE.md](QUALITY_SCORE.md)): both eval layers and the live acceptance
pass run **outside CI**, because a behavior eval spends real metered calls against the live Job
Postings API. So CI proves the dev tooling, the file rules, and the docs; the release gate that
proves runtime behavior is a local run of the behavior evals before tagging. That split is
deliberate and tracked, not papered over. The green-gate commands and the contributor workflow are
in [../CONTRIBUTING.md](../CONTRIBUTING.md); the full acceptance matrix is
[../TESTING.md](../TESTING.md).

## 7. Reliability of the docs themselves

The knowledge base is held to the same standard as the code. Two stdlib guards run in CI:
[../scripts/doc_lint.py](../scripts/doc_lint.py) checks that every live KB doc links the
the reference skills' source of truth instead of restating
a contract literal, that every Markdown link resolves, and that the section indexes stay
complete — and [../scripts/philosophy_guard.py](../scripts/philosophy_guard.py) fails the build
if numeric score math, a budget/cost control, or an unverified actual-charge claim leaks into shipped
output; accurate calls-first context remains allowed. On top
of the mechanical checks, the doc-reviewer agent catches **semantic** drift the linters can't —
prose that has quietly diverged from the contract it points at. Together they keep this document,
and the rest of the KB, honest as the code evolves. The structural map of all of this is
[../ARCHITECTURE.md](../ARCHITECTURE.md).
