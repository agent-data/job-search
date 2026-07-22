---
type: review
title: "Handoff: reconciling the audit-remediation design and plan"
status: current
verified: partial
last_reviewed: 2026-07-22
reviewed_commit: abbd88d
claimed_paths: [docs/superpowers, skills, shared, tests]
owner_area: Skills & references
repos: [job-search-os]
---

# Handoff: reconciling the audit-remediation design and plan

**For the next session.** Implementation is paused. A conflict sweep found 35 blocking contradictions
between the plan and the shipped pack. The owner will bring their calls on how to reconcile each one;
this session's job is to apply them to the **design doc and the implementation plan**, not to write
runtime code.

## State in one paragraph

Branch `feat/recall-oriented-query-strategy`, HEAD **`abbd88d`**, working tree clean, all gates green
(`pytest` 626 passed at last full run, `doc_lint` clean, `philosophy_guard` clean). Three of 28 plan
tasks have landed. Task 3 is **implemented but never reviewed** — its implementer's concerns are what
triggered the sweep. Nothing is pushed.

## Read these, in this order

| # | Document | Why |
|---|---|---|
| 1 | `docs/superpowers/reviews/2026-07-22-plan-conflict-sweep.md` | **The work item.** 35 Blocking (B1–B37), 18 Should-fix, 11 Watch, with a summary table and elaboration on the five that change what a task *is* |
| 2 | `docs/superpowers/specs/2026-07-22-audit-remediation-design.md` | The design to be fixed |
| 3 | `docs/superpowers/plans/2026-07-22-audit-remediation.md` | The plan to be fixed (28 tasks, six phases) |
| 4 | `docs/superpowers/reviews/2026-07-22-plugin-style-audit.md` | The original audit both respond to — the source of truth for *what must be fixed*, unaffected by the sweep |
| 5 | `.superpowers/sdd/progress.md` | Execution ledger — **contains two projects**; this one starts at the `audit remediation (2026-07-22)` heading |

## What has actually landed

| Task | Commits | State |
|---|---|---|
| 1 — reference maps | `253b4a8`..`35a475b` | Complete, **approved** after 3 fix waves |
| 2 — ownership contract | `593fc9f`..`b1465c6` | Complete, **approved** after 3 fix waves |
| 3 — fence the front door | `07882e5` | **Implemented, NOT reviewed.** See caveat below |
| 4–28 | — | Not started |

Controller commits interleaved: `4046255`, `50ab62c`, `97c8e15`, `4b90e90`, `ac3402e` (plan
amendments), `7035a3e`, `abbd88d` (sweep records).

### The Task 3 caveat

`07882e5` fenced the front door against the **current, defective** contract. Once B1 re-specifies the
`Never` column, Task 3's shipped prose needs re-checking — specifically the Principles bullet and the
mental-model paragraph in `skills/job-search/SKILL.md`, which quote the artifact list. Its implementer
also flagged, and nobody has adjudicated:

- the `jobs.jsonl` ban vs. `home.md:268` and `onboarding.md:139` (now B2);
- `job-search-agent/SKILL.md:71` still saying the manual applies config edits itself (now S8-adjacent);
- that its mutation harness briefly clobbered three `SKILL.md` files and restored them from HEAD —
  verified by diff, tree clean, but unreviewed.

Decide whether Task 3 gets a review pass, a redo against the corrected contract, or is folded into the
reconciliation.

## Owner decisions

**Already made, not yet applied:** the ownership contract narrows to the **two protected actions** —
only `job-search-run` may call the job source and write run outputs; only `evaluate-job-fit` may
produce a verdict. Config edits, `status_changed` events and scaffolding are shared and claimed
exclusively by nobody. This is the B1 fix and it has not been written yet.

**Open, listed at the end of the sweep doc:**

1. **The word budget (B9, B10).** The runner cannot reach 2,000 words — simulated best is 373 lines /
   4,276 words, and the design's own "kept in the body" list totals 3,771. Two other skills already
   exceed the cap the plan applies globally. Options: adopt `AAS-SKILL-04`'s ~3,800-word figure
   pack-wide; hold 2,000 and name a further ~2,300 words to relocate; or per-skill ceilings.
2. **Unknowns vs. the band cap (B21).** `conventions.md:612` says unknowns are "NEVER counted against a
   posting"; Task 8 requires an unestablished domain to cap the band below `strong`. Options: never
   rejects but does cap; keep unknowns fully neutral; or mark protected terms in the brief.
3. **Revision scope.** Revise design and plan in place — the Track A–E structure survives, ~12 tasks
   need rework — or re-derive the affected tasks from the audit.

## How to work the reconciliation

Suggested shape, once the owner's calls are in:

1. **Fix the design first, then the plan.** Several blocking rows (B1, B9, B21, B23, B24, B25, S6, S12)
   are design-level; the plan's tasks are downstream of them. Fixing the plan first means fixing it
   twice.
2. **Group by root cause, not by finding.** B1–B4 are one rewrite of the `Never` column. B5–B8 are one
   re-scoping of Task 12. B27–B30 are one specification of the pointer gate. Thirty-five rows are
   roughly a dozen edits.
3. **Simulate every gate before writing it into the plan.** Seventeen of the 35 blocking findings are
   gates specified but never executed against the tree. Run the proposed rule; paste the real output
   into the `Expected:` line.
4. **Re-baseline the stale numbers** as a single pass — see the table below.
5. **Preserve the execution record.** Tasks 1–3 are executed; amend them with As-built notes rather
   than rewriting their steps, as Task 1 already does.

## Facts the documents currently get wrong

Correct these while reconciling; a fresh session verifying `Expected:` lines against reality will hit
each one.

| Claim in design/plan | Reality at `abbd88d` |
|---|---|
| runner is 686 lines / 7,772 words | **689 / 7,804** |
| `job-search/SKILL.md` ~95 lines / 1,126 words | **108 / 1,310** |
| the test pins "nineteen substrings … sixteen prose fragments" | **18 asserted / 14 prose** |
| bold density 0.50 and 0.44 | **0.463** and **0.417** |
| "the two files over 5,000 words" | **four**: internals 9,127 · onboarding 6,145 · conventions 5,981 · run-lifecycle 5,937 |
| "every audit finding maps to exactly one track" | three findings are split across two tracks each |
| design's problem statement, present tense | the front-door prohibition and `evaluate-job-fit` routing were fixed by `07882e5` |
| Task 25: "`voice.md` is untouched by every other task" | Task 1 added its `**Contents:**` map |

Current measured sizes, for re-baselining:

```
evaluate-job-fit          76 lines    842 words
job-search               108 lines   1310 words
job-preference-interview 203 lines   2193 words
job-search-agent         228 lines   3147 words
job-search-run           689 lines   7804 words
```

## Constraints that still bind

From the plan's Global Constraints — carry these into the reconciliation:

- Stdlib only; no new runtime or test dependencies.
- No config schema change, no `version: 3`, no migration. Only new persisted key: `update_check.consent`.
- No new sibling skills.
- One canonical home per fact.
- **Never delete a failing assertion to make CI green** — re-point it at the fact's new home.
- Assert prose against whitespace-normalized text; every markdown surface here is hard-wrapped.
- A test that passes on gutted content is not a gate.
- Line numbers are advisory; locate edits by quoted content.
- All work stays on `feat/recall-oriented-query-strategy`.

## Things that will mislead a fresh session

- **The ledger holds two projects.** `.superpowers/sdd/progress.md` opens with a completed
  9-task project (recall-oriented query strategy, pushed 2026-07-21). This project's section is the
  second one. Task numbers are unrelated.
- **The design doc's ownership table was already revised once** (four rows → six, after the owner's
  five-skill call) and the glob defect survived that revision. Row count and `Never` cells are separate
  problems; `docs/superpowers/specs/2026-07-22-audit-remediation-design.md:138` still carries
  `runs/*.json`.
- **`shared/references/ownership.md` is CI-pinned** by `tests/test_ownership_contract.py`, which now
  enforces per-column semantics, the two-prohibition invariant, residual-claim detection and the
  pairing paragraph. Any B1 rewrite must update that gate in the same commit — and the gate errs
  toward false-RED by design, so a reworded cell may need its accepted vocabulary widened.
- **Three fix waves' worth of hardening sits on top of Tasks 1 and 2** that the plan's own step text
  does not describe. Task 1 carries an As-built note; Task 2 does not yet.
- **`docs-private/` is untracked.** The two style guides the audit cites exist locally but are not in
  git. Rule IDs may be cited; paths must not appear in shipped artifacts.

## What "done" looks like for the next session

- Every B-row in the sweep doc is either applied to the design/plan, explicitly declined with a reason
  recorded, or converted to an owner-approved change of target.
- The design's Non-goals, Completion Criteria and Traceability table are consistent with the revised
  tasks — including the five audit findings currently listed with a track but no task (S1).
- Every `Expected:` line in a revised task reflects output actually observed, not predicted.
- The stale-numbers table above is emptied.
- `doc_lint` and `philosophy_guard` stay clean; no runtime file changes unless a decision requires it.
- The sweep doc gains a short disposition column or companion note, so the reconciliation is auditable
  against it.

Resume implementation only after the design and plan are consistent, starting from the Task 3 decision
above.
