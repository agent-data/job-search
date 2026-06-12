# Reliability

How Job Search OS stays trustworthy: a deterministic core, named failures, bounded retries,
and failures that surface where the user will actually see them. This doc describes the
*mechanisms*. It does **not** restate any runtime contract — every concrete value (error
wording, run-health states, the frequency enum, the `run_id` format, the digest counts line,
config field names, the job-status enum) is owned by [shared/references/](../shared/references/conventions.md)
and linked here. When a number or a literal matters, follow the link to its source of truth.

For the principles behind these mechanisms see
[design-docs/core-beliefs.md](design-docs/core-beliefs.md); for the structural map see
[../ARCHITECTURE.md](../ARCHITECTURE.md).

**TL;DR (reading this mid-incident).** Run-health states and *how a blocked run surfaces without a
trustworthy exit code* both live in [§4](#4-run-health--blocked-surfacing--visible-without-the-exit-code);
the named `E-*` errors themselves (cause + fix wording) are not in this doc — they are in
[`shared/references/errors.md`](../shared/references/errors.md). Jump by symptom:

| If you're chasing… | Go to |
|---|---|
| a blocked run / where the error reaches the user / the `claude -p` exit-code trap | [§4 Run health & blocked surfacing](#4-run-health--blocked-surfacing--visible-without-the-exit-code) |
| why a call was (or wasn't) retried, the circuit-breaker | [§3 Retry & circuit-breaker](#3-retry--circuit-breaker--patient-then-it-stops) |
| "is this a silent failure?" / what every `E-*` covers | [§2 No silent failures](#2-no-silent-failures--every-blocked-path-is-named) |
| state that looks corrupted or non-reproducible | [§1 Determinism](#1-determinism--the-core-is-a-pinned-contract-and-reproducible) |
| whether the scheduled (headless) run hung on a prompt | [§5 Headless-first](#5-headless-first--the-scheduled-run-never-blocks-on-a-human) |
| "what actually proves any of this" — tests, evals, the fake shim | [§6 Testing & evals](#6-testing--evals--what-actually-guarantees-the-above) |
| a doc that drifted from the contract it points at | [§7 Reliability of the docs](#7-reliability-of-the-docs-themselves) |

---

## 1. Determinism — the core is a pinned contract and reproducible

The mechanics that must never improvise — workspace discovery, registry writes, the schedule
line, dedup, the event-log fold — are **pinned written contracts**: exact precedence rules,
portable shell one-liners, and byte-level write rules that Claude Code executes natively with
no runtime dependency (no Python on the user's machine). The *specification* is deterministic —
the same frequency always maps to the same `/loop` command, and the same event log always folds
to the same current state — while the *executor* is the model following the contract verbatim.
The named tradeoff: the runtime mechanics are verified by the skill evals and the TESTING.md
matrix (artifact assertions on registry bytes and event lines), no longer by a unit-test suite.

State is an **append-only event log**, not a mutable record: `jobs.jsonl` is a sequence of
events, and current state is computed by folding them by dedup key (last-write-wins per field).
Re-running is therefore safe — nothing is overwritten in place, and a crash mid-run can at
worst leave a trailing partial line, never a corrupted record. The schema of those events, the
event-line contract, the operations (known-ids / append / fold), and the on-disk layout
(`jobs.jsonl`, `runs/<id>.json`) are owned by
[../shared/references/conventions.md](../shared/references/conventions.md); the scheduling
artifacts, the registry write rules, and the discovery precedence are owned by
[../shared/references/internals.md](../shared/references/internals.md).

Because the deterministic pieces are isolated from the LLM judgment, the parts that *can* be
proven correct *are* — the model is left to do only what genuinely needs judgment (relevance),
and everything else is testable. See the **Deterministic, testable, headless** belief in
[design-docs/core-beliefs.md](design-docs/core-beliefs.md#6-deterministic-testable-headless).

## 2. No silent failures — every blocked path is named

The system never fails quietly. Every condition that stops or degrades a run is a named `E-*`
error carrying a **cause and a concrete fix**, not a stack trace. These cover the full surface
a run can hit: a missing or unauthenticated CLI, a missing config or preferences brief, a
config written by an incompatible future version, an unreachable or degraded job source, a
malformed query, a repeated upstream outage, and a reached API limit. The complete catalogue —
every code, its trigger, the exact user-facing wording, and its effect on the run — is owned by
[../shared/references/errors.md](../shared/references/errors.md). This doc deliberately does not
reproduce any code or its message; the catalogue is the single source of truth and the runner
follows it verbatim.

That "name it, never swallow it" rule is a core belief, enforced in review and by the linters —
see **No silent failures — named errors** in
[design-docs/core-beliefs.md](design-docs/core-beliefs.md#4-no-silent-failures--named-errors).

## 3. Retry & circuit-breaker — patient, then it stops

Upstream calls (the metered searches and detail fetches) can fail transiently, so the run
retries — but only the failures the contract marks **retryable**. The branch keys on the error
envelope's `retryable` boolean, never on parsing the error code string: a transient upstream
failure (the 502s) is retried with bounded exponential backoff and jitter; a deterministic
client error (a bad field, an invalid request, a stale id/URL pair) is **never** retried,
because retrying it would only waste a metered call and still fail. The exact attempt count,
the backoff schedule, and which codes are retryable are owned by
[../shared/references/agent-data-contract.md](../shared/references/agent-data-contract.md) —
paraphrased here, authoritative there.

Retries are also **bounded across the run**, not just per call — the circuit-breaker. If the
job source keeps failing search after search, the run stops searching rather than hammering a
struggling upstream, and reports what it managed to gather. That repeated-outage condition is a
named error (the upstream-stretch case) in
[../shared/references/errors.md](../shared/references/errors.md); a single stale detail link, by
contrast, is an expected non-error that falls back to summary-only judgment with a footnote
rather than failing the run. The strategy in one line: be patient with transient failures, give
up immediately on deterministic ones, and break the circuit when an upstream is clearly down.

## 4. Run health & blocked surfacing — visible without the exit code

Every run records a **health state** in its `runs/<id>.json` audit record, and the digest leads
with that state. The set of states and the digest's health line are owned by
[../shared/references/conventions.md](../shared/references/conventions.md) and
[../shared/references/errors.md](../shared/references/errors.md) — this doc does not list them.

The important reliability property is *how* a blocked run reaches the user. It does **not** rely
on the process exit code: a headless `claude -p` invocation returns `0` even when the run was
blocked (a skill cannot set the host process's exit status), so a headless run's `$?` is not a
trustworthy signal and the docs never tell the user to check it. Instead, a blocked run surfaces
three records-based ways, all owned by [../shared/references/errors.md](../shared/references/errors.md):

- the **blocked digest** — the named error's cause + fix replaces the match list as the body;
- a **desktop notification** on a blocked run (toggled by a notify setting in `config.yaml`); and
- the **home view** on the user's next front-door visit (the `job-search` skill), which reads the
  health state from the newest run record.

So that surfacing always works, **every** halting path writes its `runs/<id>.json` blocked
record *before* it stops — that record is the source the home view reads, so a scheduled run
that failed overnight is named the next time the user opens the front door. The one exception is
the no-workspace / first-run case: there is nowhere to write a record, but the failure is
inherently visible because the next front-door visit routes to onboarding. The run loop that
enforces all of this is [../skills/job-search-run/SKILL.md](../skills/job-search-run/SKILL.md).

## 5. Headless-first — the scheduled run never blocks on a human

The scheduled pass is strictly **non-interactive**: it never prompts, because there is no human
watching when the `/loop` run fires. Anything that would need a decision is instead resolved by the
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
  philosophy guard, and the fake agent-data shim's own behavior. The runtime mechanics (discovery,
  registry writes, dedup, the fold) are pinned contracts executed by the model, so the layer that
  proves them is the evals + the TESTING.md matrix below, not pytest.
- **A credit-free fake `agent-data` shim** (a PATH shim under [../tests/](../tests/)) lets a
  whole run be driven with deterministic, injectable upstream behavior — quota, outage, stale
  links, degraded service — with **no network and no metered calls**, so the error and retry
  paths in §2–§4 can be exercised repeatedly and for free.
- **Per-skill evals** measured by the skill-creator harness check the *model's* behavior (each
  skill has its own `evals/` suite) — that the runner actually halts on a blocked gate, judges
  qualitatively, and surfaces the right named error.
- **CI** ([../.github/workflows/ci.yml](../.github/workflows/ci.yml)) runs the pytest suite, the
  philosophy guard, and the doc linter on every change.

Honest scope (per [QUALITY_SCORE.md](QUALITY_SCORE.md)): the per-skill evals and the live
acceptance pass run **outside CI** — via the skill-creator harness and the manual
[../TESTING.md](../TESTING.md) matrix — so CI proves the dev tooling and the docs, not the
model's runtime behavior (which now includes executing the pinned state procedures). That gap is
tracked, not papered over. The green-gate commands and the
contributor workflow are in [../CONTRIBUTING.md](../CONTRIBUTING.md); the full acceptance matrix
is [../TESTING.md](../TESTING.md).

## 7. Reliability of the docs themselves

The knowledge base is held to the same standard as the code. Two stdlib guards run in CI:
[../scripts/doc_lint.py](../scripts/doc_lint.py) checks that every live KB doc links the
[../shared/references/](../shared/references/conventions.md) source of truth instead of restating
a contract literal, that every Markdown link resolves, and that the section indexes stay
complete — and [../scripts/philosophy_guard.py](../scripts/philosophy_guard.py) fails the build
if a numeric score, a category weight, or a budget/cost field leaks into shipped output. On top
of the mechanical checks, the doc-reviewer agent catches **semantic** drift the linters can't —
prose that has quietly diverged from the contract it points at. Together they keep this document,
and the rest of the KB, honest as the code evolves. The structural map of all of this is
[../ARCHITECTURE.md](../ARCHITECTURE.md).
