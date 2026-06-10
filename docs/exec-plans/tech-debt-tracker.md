# Technical Debt Tracker

The canonical, itemised technical-debt backlog for job-search-os. The high-level maturity view is
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

## P2 — turn-off doesn't clear the schedule marker (`TODO-SCHED-OFF`)
**What:** Add an `osctl.py set-unscheduled` (or `set-scheduled --installed false`) command and call it from the
home/onboarding "turn off the schedule" flow.
**Why:** `set-scheduled` can set `installed: true` but nothing clears it; the turn-off flow ([`home.md:79-80`](../../skills/job-search/references/home.md)) only
removes the OS artifact, so `schedule-status` keeps reporting a **stale `installed: true`** after a turn-off — the
home view and T4.4 then misreport the schedule as on.
**Impact:** *verified the described failure no longer holds* — `set-unscheduled` now exists (`scripts/osctl.py`, `cmd_set_unscheduled`, writing `{"installed": false, "mechanism": null}`), the turn-off flow in [`home.md`](../../skills/job-search/references/home.md) already calls it, and [`TESTING.md` T4.4](../../TESTING.md) asserts `schedule-status` reads `installed: false` afterward; so no stale marker is left and the home view does not misreport. This item reads as **substantively resolved in code** — flag for a maintainer to confirm and close.
**How to apply:** Add the command (mirrors `set-scheduled`, writing `{"installed": false, "mechanism": null}`);
have the turn-off path call it after removing the cron line / `launchctl unload`. Then T4.4's marker check passes.
**Linked tests:** [`TESTING.md`](../../TESTING.md) T4.4 (marker assertion, flagged ⚠), §13 T13.3.

## P3 — untested config fields & edges
**What:** `notify.desktop_notify_on_block` (blocked-run desktop alert), `schedule.timezone` runtime behavior, and
concurrency / interrupted-run recovery (two overlapping runs; a hard-kill mid-run).
**Why:** Each is environment-dependent or an edge for v0.1; `jobs.jsonl` is append-only so corruption risk is low.
**Impact:** verified all three carry **zero tests** (no hit in `tests/` for `desktop_notify_on_block`, `schedule.timezone`, or any concurrency/interrupted-run case; `schedule.timezone` is informational-only under `/loop` per `osctl.py`) — a regression in any of them ships silently and only surfaces in the field; blast radius stays low because the append-only `jobs.jsonl` (`scripts/state.py`) bounds the corruption risk.
**How to apply:** Add targeted tests when these surfaces are exercised in the field.
**Linked tests:** none yet.

## P3 — osctl schedule-line accepts an out-of-range --time (`TODO-TIME-RANGE`) — ✅ resolved (obsolete)
**Resolved 2026-06-08 by removal.** The cron/launchd generators (`schedule-line`, `cron_schedule()`, `launchd_cal()`) no longer exist — scheduling is native `/loop` (see [`../../shared/references/internals.md`](../../shared/references/internals.md)). `loop-command` takes only `--frequency` (no `--time`), so there is no time value to range-check. No action needed.
