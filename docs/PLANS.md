# Plans

This doc explains **how we plan** in job-search-os — which kind of plan to use, how to structure
a checked-in execution plan, and how to run the on-demand doc-gardening sweep. For the catalogue
of actual plans see [`exec-plans/index.md`](exec-plans/index.md).

**TL;DR.** Small bounded change → an ephemeral scratch plan; multi-commit or decision-bearing work →
a checked-in execution plan with the structure below. Jump table:
[Two kinds of plans](#two-kinds-of-plans) ·
[How an execution plan is structured](#how-an-execution-plan-is-structured) (frontmatter + body format) ·
[Execution protocol](#execution-protocol) (TDD + the per-commit doc-reviewer pass) ·
[Plan lifecycle](#plan-lifecycle) (active → completed) ·
[Technical debt](#technical-debt) · [On-demand doc-gardening](#on-demand-doc-gardening).

---

## Two kinds of plans

### Ephemeral / lightweight plans

For small, bounded changes. Write them in your working session (e.g. `~/.claude/plans/`) as a
scratch checklist. They are **not checked in** — they exist only to keep a short task organised
and are discarded when done.

Use an ephemeral plan when: the change is a single-commit fix, a docs tweak, or any task where
the full scope is clear up-front and no decision record is needed.

### Execution plans (checked in)

For complex, multi-step work that spans multiple commits, involves design decisions, or where a
decision log matters for future readers. These are Markdown files that live in version control.

- **In-flight:** `docs/exec-plans/active/`
- **Done:** `docs/exec-plans/completed/`
- **Exemplar (completed):** [`exec-plans/completed/2026-06-09-voice-and-onboarding-clarity.md`](exec-plans/completed/2026-06-09-voice-and-onboarding-clarity.md)
  — closest match for the body format below (a Non-goals fence, scoped per-task logs, verification
  baked into each task). For a completed plan that models the full upgraded template — including the
  Done-when gate and `[BLOCKS]`/`[TUNE]` tags — see
  [`exec-plans/completed/2026-06-09-prompt-style-conformance.md`](exec-plans/completed/2026-06-09-prompt-style-conformance.md).

Use an execution plan when: the work has more than one logical phase, involves trade-off decisions
worth recording, or when multiple commits will touch related files over time.

---

## How an execution plan is structured

### Required frontmatter

Every plan file (except `index.md`) must carry a leading `--- … ---` frontmatter block with:

| Key | Active plan | Completed plan |
|-----|-------------|----------------|
| `title` | required | required |
| `state` | `active` | `completed` |
| `created` | ISO date (`YYYY-MM-DD`) | ISO date |
| `completed` | — | ISO date (required) |

`state` must be one of `active`, `completed`, or `abandoned`. These constraints are enforced
mechanically by the `frontmatter-schema` rule in [`../scripts/doc_lint.py`](../scripts/doc_lint.py).
For what each `state` means alongside the design-doc `status` / `verified` values it sits beside,
see the [status vocabularies](design-docs/index.md#status-vocabularies) glossary.

### Body format

A plan is read cold by an executor who wasn't in the room. Lead with **why this change** (a Goal
paragraph), name the critical files, and show each pattern once with a representative path — do not
re-enumerate every file the change touches or inline whole file bodies (a diff does that; the plan
rots when the file moves). State commands you actually intend to run, and verify rather than assume.

Plans follow the [commit + message conventions in CONTRIBUTING.md](../CONTRIBUTING.md#commit-message-conventions):

- **Bite-sized red → green TDD steps, each tagged `[BLOCKS]` or `[TUNE]`** — each task writes a
  failing test first, then the minimal implementation, then refactors; commands are written out
  exactly. The tag says why the task matters — `[BLOCKS]` for a correctness, routing, or publishing
  issue, `[TUNE]` for quality or readability — so an executor on a budget does the blocking work
  first and a reviewer knows which gaps are load-bearing.
- **Non-goals** — an explicit fence naming what the plan will *not* do and, where it isn't obvious,
  why; a reviewer shouldn't have to re-litigate scope the author already closed, and "I assumed you
  also wanted…" is how a bounded change sprawls.
- **A single "Done when" gate** — one checklist of verifiable commands and criteria (`doc_lint`
  clean, tests green, a grep that returns 0, a cross-read), run once before the plan flips to
  completed — not done-ness scattered across sections where no one can see the whole bar at a glance.
- **Frequent scoped commits** — one commit per logical task, using Conventional-Commit prefixes
  (`feat(scope):`, `docs(scope):`, `test(scope):`, `ci:`).
- **Progress log** — a running append-only section at the bottom of the file; each task adds a
  line with its commit SHA when done.
- **Decision log** — also at the bottom; each non-obvious design choice is recorded with its
  rationale so future readers understand *why*, not just *what*.
- **Self-Review** — a required pass the author makes over their own plan before execution begins:
  re-read it as the cold executor would, confirm every named file and command is real, and check
  that the Non-goals and Done-when gate actually fence the work. Catching a wrong path or a missing
  gate here costs a sentence; catching it mid-execution costs a wasted task.

Both logs are updated as part of the commit that completes each task.

---

## Execution protocol

Plans are executed using **TDD + subagent-driven-development**: every task is red → green →
refactor → commit, and every commit that touches substantive KB docs triggers a **doc-reviewer
pass** scoped to the docs that commit touched.

The doc-reviewer operates in two modes from one definition:

1. **Per-commit (read-only):** identifies the KB docs changed by `HEAD`, checks that each doc's
   checkable claims still match the code, and produces a concise structured report. Real drift is
   fixed in a follow-up commit within the same task, or logged in the Decision Log if deferred.
2. **On-demand gardening sweep:** scans the entire `docs/` tree (see below).

For the full reviewer behaviour — what counts as a "checkable claim", the report format, the
gardening recipe — see [`.claude/agents/doc-reviewer.md`](../.claude/agents/doc-reviewer.md).

---

## Plan lifecycle

```
active/  →  completed/
```

When a plan finishes:

1. Flip `state: active` to `state: completed` and add a `completed: YYYY-MM-DD` field.
2. Move the file from `docs/exec-plans/active/` to `docs/exec-plans/completed/`.
3. Update [`exec-plans/index.md`](exec-plans/index.md) to move the entry under **Completed**.

The `plan-location` rule in [`../scripts/doc_lint.py`](../scripts/doc_lint.py) enforces that a
plan's `state` field agrees with its directory — a completed-state file sitting in `active/`
will fail CI.

---

## Technical debt

Itemised P2/P3 debt lives in [`exec-plans/tech-debt-tracker.md`](exec-plans/tech-debt-tracker.md).
The high-level maturity view — qualitative grades per domain and layer — is
[`QUALITY_SCORE.md`](QUALITY_SCORE.md).

---

## On-demand doc-gardening

Doc-gardening is a sweep over the whole knowledge base that finds stale or drifted docs and opens
a fix-up PR for human review. It is **on-demand** (no cron).

To run it:

1. Invoke the doc-reviewer agent ([`.claude/agents/doc-reviewer.md`](../.claude/agents/doc-reviewer.md))
   in gardening mode over every KB doc (`AGENTS.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `docs/**/*.md`).
2. The agent also runs the mechanical passes:
   ```bash
   python3 scripts/doc_lint.py --root .
   python3 scripts/doc_lint.py --root . --strict-fresh
   ```
   `--strict-fresh` escalates staleness warnings (old `last_reviewed` dates) to failures,
   giving a full picture of what needs attention.
3. The agent applies only **confident** fixes (bump a verified date, correct a drifted factual
   claim, repair an index entry) and proposes the rest in the PR body — it never guesses at
   rewrites and never merges without human approval.

The gardening sweep covers the whole knowledge base as described in
[`../ARCHITECTURE.md`](../ARCHITECTURE.md). The doc-reviewer never edits `shared/references/`
(those are the source of truth, owned by the build pipeline) and never edits code to fit a doc.
