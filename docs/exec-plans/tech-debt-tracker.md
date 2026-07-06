# Technical Debt Tracker

The canonical, itemised technical-debt backlog for job-search. The high-level maturity view is
in [QUALITY_SCORE.md](../QUALITY_SCORE.md); this is the detailed list. (Migrated from the former
root `TODOS.md`, which now points here.)

Product/test debt surfaced during the **[TESTING.md](../../TESTING.md) DX hardening pass (2026-06-06)**.

**Legend.** **Priority** — `P2` = should fix; it hurts maintainability or test coverage *now* (a planned
test stays parked, or a flow misreports state) · `P3` = nice-to-fix; low blast radius — an
edge or environment-dependent surface where the safe default already holds (e.g. append-only state).
**Item schema** — each heading is *priority — what* + a `TODO-ID` slug, then **What** · **Why** · **Impact**
(the one-line blast radius: what breaks, and how it stays unnoticed) · **How to apply** · **Linked tests**.

## P2 — config command surface (`TODO-CONFIG-COMMANDS`)
**What:** Add an `/effort`-style config slash-command surface alongside the conversational path — e.g.
`/job-search-frequency <hourly…weekly>`, `/job-search-add-query "<kw>" "<loc>"`, `/job-search-schedule off`.
**Why:** Config today is 100% natural-language; some users want a fast, explicit command modality (like Claude
Code's native `/effort`). Requested during planning.
**Impact:** the command modality has no working tests — [`TESTING.md` §13](../../TESTING.md) (T13.1–T13.3) stays
permanently `pending-build` / N/A (never green), so the conversational path is the only config surface CI exercises;
low user-facing risk (the feature simply doesn't exist yet), but the coverage gap is invisible in a green test run.
**How to apply:** Each command calls the *same* config-edit recipes as the conversational flow (parity), keeps
`version: 1`, rejects bad input with a named `E-*`, and never adds a numeric/budget field. Then flip §13's
pending-build tests to live.
**Linked tests:** [`TESTING.md`](../../TESTING.md) §13 (T13.1–T13.3, currently pending-build).
**Depends on:** deciding command names + argument grammar.

## P2 — turn-off doesn't clear the schedule marker (`TODO-SCHED-OFF`) — ✅ resolved (closed 2026-06-11)
**Resolved.** The clear-the-marker operation exists and the turn-off flow calls it: the scheduling marker's
set/clear procedures are pinned in [`../../shared/references/internals.md`](../../shared/references/internals.md)
(Registry → scheduling marker; the former `osctl.py set-unscheduled` was its script-era shape), the turn-off
flow in [`home.md`](../../skills/job-search/references/home.md) clears the marker so it reads
`installed: false`, and [`TESTING.md` T4.4](../../TESTING.md) asserts it. No stale marker is left; closed.
**Linked tests:** [`TESTING.md`](../../TESTING.md) T4.4 (marker assertion), §13 T13.3.

## P3 — jobs.jsonl grows unboundedly; the in-context fold cost grows with it (`TODO-JOBS-COMPACTION`)
**What:** The home view's pipeline folds `jobs.jsonl` in-context (per the fold operation in
[`../../shared/references/conventions.md`](../../shared/references/conventions.md)); a long-lived workspace
accumulates events without bound, so the read cost of the fold grows with history.
**Why:** Watch-only for now — realistic logs (hundreds of postings) fold cheaply, the append-only design is
the corruption-safety property we keep, and compaction would add a mutating code path with real risk.
**Impact:** very large logs make the home view slower/heavier to render; nothing corrupts and nothing
misreports — cost, not correctness.
**How to apply:** if it bites in the field, add an explicit, user-visible compaction ("archive my rejected
postings") that writes a new file and never edits in place. Do not build preemptively.
**Linked tests:** none (watch item).

## P3 — untested config fields & edges
**What:** `notify.desktop_notify_on_block` (blocked-run desktop alert), `schedule.timezone` runtime behavior, and
concurrency / interrupted-run recovery (two overlapping runs; a hard-kill mid-run).
**Why:** Each is environment-dependent or an edge for v0.1; `jobs.jsonl` is append-only so corruption risk is low.
**Impact:** verified all three carry **zero tests** (no hit in `tests/` for `desktop_notify_on_block`, `schedule.timezone`, or any concurrency/interrupted-run case; `schedule.timezone` is informational-only under `/loop` per the scheduling section of [`../../shared/references/internals.md`](../../shared/references/internals.md)) — a regression in any of them ships silently and only surfaces in the field; blast radius stays low because the append-only `jobs.jsonl` contract ([`../../shared/references/conventions.md`](../../shared/references/conventions.md)) bounds the corruption risk.
**How to apply:** Add targeted tests when these surfaces are exercised in the field.
**Linked tests:** none yet.

## P3 — schedule-line accepts an out-of-range --time (`TODO-TIME-RANGE`) — ✅ resolved (obsolete)
**Resolved 2026-06-08 by removal.** The cron/launchd generators no longer exist — scheduling is native `/loop` (see [`../../shared/references/internals.md`](../../shared/references/internals.md)). The `/loop` line is composed from `schedule.frequency` alone (no `--time`), so there is no time value to range-check. No action needed.

## Wave 2 inherits (multi-source)

Watch items the multi-source wave (PR1–PR3) hands forward — each parked behind a concrete trigger,
none with a test yet (the surface it guards isn't built).

### P3 — merged-entry strings hardcode LinkedIn/Ashby; Ashby-primary is fixed (`TODO-MERGE-SOURCE-PRIMARY`)
**Resolved 2026-07-06 by [2026-07-06-multi-source-reconciliation-greenhouse-lever](active/2026-07-06-multi-source-reconciliation-greenhouse-lever.md).** Greenhouse + Lever are the third/fourth mergeable board sources; the merged-entry copy, the primary-selection rule (board-source row, earliest in `search.sources`), and run-health `<why>` are now N-source. Kept as a resolved record.
**What:** The cross-source merge bakes the `linkedin`/`ashby` names into the merged-entry copy and always
picks the Ashby row as the primary of an aliased pair.
**Why:** Two mergeable sources is the whole world today, so a two-name string and a fixed primary read
cleanly; generalizing now would be speculative (YAGNI).
**Impact:** the moment a third mergeable source lands, the two-name copy and the fixed Ashby-primary rule
misdescribe the merge — a presentation bug, not a data bug (the fold key stays correct).
**How to apply:** generalize the merged-entry copy and the primary-selection rule to N sources when a
third mergeable source is added.
**Linked tests:** none (watch item).

### P3 — alias status-divergence rule unspecified (`TODO-ALIAS-STATUS-DIVERGENCE`)
**What:** When two records aliased by `same_role_as` carry different `status` values, which status the
collapsed role shows is unspecified.
**Why:** No pipeline action mutates one leg of an aliased pair yet, so a divergence can't arise in
practice today.
**Impact:** once pipeline actions (mark interested/applied) can touch one alias leg, a divergent pair has
no defined winner — the collapsed role could show either status.
**How to apply:** define the precedence (e.g. most-advanced status wins) when pipeline actions land.
**Linked tests:** none (watch item).

### P3 — run-health `<why>` can't name a two-of-three source loss (`TODO-WHY-ENUM-MULTILOSS`)
**What:** The run-health `<why>` vocabulary names one lost source or "all sources unavailable"; it can't
say two of three sources were lost (e.g. LinkedIn and Ashby down while Workday survives).
**Why:** With the two default sources the only cases are "one lost" or "all lost", both already covered.
**Impact:** reachable only once Workday is opted in against a legacy server — a three-source run that
loses two would collapse to "all sources unavailable" or a single-source name, understating the outage in
the digest header.
**How to apply:** extend the `<why>` vocabulary to name a partial-but-multiple loss once a third source is
in routine use.
**Linked tests:** none (watch item).
