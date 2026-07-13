# Technical Debt Tracker

The canonical, itemised technical-debt backlog for job-search. The high-level maturity view is
in [QUALITY_SCORE.md](../QUALITY_SCORE.md); this is the detailed list. (Migrated from the former
root `TODOS.md`, which now points here.)

Product/test debt surfaced during the **[TESTING.md](../../TESTING.md) DX hardening pass (2026-06-06)**.

**Legend.** **Priority** — `P1` = fix before the next release; a shipped or updated skill can silently
run the wrong content, voiding a whole capability with no runtime signal · `P2` = should fix; it hurts
maintainability or test coverage *now* (a planned test stays parked, or a flow misreports state) · `P3` =
nice-to-fix; low blast radius — an edge or environment-dependent surface where the safe default already
holds (e.g. append-only state).
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
**Resolved 2026-07-06 by [2026-07-06-multi-source-reconciliation-greenhouse-lever](completed/2026-07-06-multi-source-reconciliation-greenhouse-lever.md).** Greenhouse + Lever are the third/fourth mergeable board sources; the merged-entry copy, the primary-selection rule (board-source row, earliest in `search.sources`), and run-health `<why>` are now N-source. Kept as a resolved record.
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
**Resolved 2026-07-06 by [2026-07-06-multi-source-reconciliation-greenhouse-lever](completed/2026-07-06-multi-source-reconciliation-greenhouse-lever.md).** With Greenhouse + Lever now in routine use, the `<why>` vocabulary gained a "several — but not all — sources lost, each named in `search.sources` order" band (`conventions.md` digest format, `job-search-run` step 5, `errors.md` E-UPSTREAM-STRETCH), so a partial-but-multiple loss is named exactly. Kept as a resolved record.
**What:** The run-health `<why>` vocabulary names one lost source or "all sources unavailable"; it can't
say two of three sources were lost (e.g. LinkedIn and Ashby down while Workday survives).
**Why:** With the two default sources the only cases are "one lost" or "all lost", both already covered.
**Impact:** reachable only once Workday is opted in against a legacy server — a three-source run that
loses two would collapse to "all sources unavailable" or a single-source name, understating the outage in
the digest header.
**How to apply:** extend the `<why>` vocabulary to name a partial-but-multiple loss once a third source is
in routine use.
**Linked tests:** none (watch item).

## Multi-source dogfooding pass (2026-07-06)

Surfaced during a live **"run a search now"** dogfooding session for the multi-source update. **Root cause:**
the harness executed the **pre-multi-source** skill from the installed plugin cache
(`~/.claude/plugins/cache/agent-data/job-search/0.3.0/`) while the repo at the **same `0.3.0` version**
carried the new multi-source skill — divergent skill content under an identical version string, with no
runtime signal. The multi-source feature never ran; every result defaulted to LinkedIn and a **human** (not
the system) noticed. The items below turn "a person eyeballed it" into "the system states it," and remove the
version-identity collision that caused the miss.

### P1 — content changes ship under an unchanged version; runs don't self-identify their build (`TODO-SKILL-BUILD-STAMP`)
**What:** (a) A CI gate that fails when anything under `skills/` or `shared/references/` changes without a
version bump in `.claude-plugin/plugin.json`. (b) A **build-stamp** (version + short content-hash + git sha)
emitted in the run summary and written to `runs/<run_id>.json`, so any run is traceable to a concrete artifact.
**Why:** The repo and the installed cache both read `0.3.0` with divergent skill content; the stale cache is
what executed, so the shipped multi-source update was silently not run.
**Impact:** a shipped or updated skill can run the wrong (old) content with **zero signal** — a whole
capability looks absent/broken while every downstream digest and event stays faithful to the wrong build; only
a sharp human eyeball catches it.
**How to apply:** add the version-bump gate to CI; compute a content hash over the skill tree at package time
and surface it (plus git sha) in the 5-line summary and `runs/<run_id>.json`. Pairs with
`TODO-DOGFOOD-BUILD-VERIFY`.
**Linked tests:** none yet (add a CI assertion for the version-bump gate).

### P3 — dogfooding can validate the wrong build (`TODO-DOGFOOD-BUILD-VERIFY`)
**What:** The dogfooding / verification recipe asserts the artifact under test is the one actually loaded —
print the build-stamp (`TODO-SKILL-BUILD-STAMP`) and confirm the installed cache matches the intended build
before starting.
**Why:** This session exercised the stale cached skill, not the repo's updated skill; only an observant user
surfaced the mismatch.
**Impact:** a dogfooding "pass" can validate code that never executed — false confidence that a feature works.
**How to apply:** add a pre-flight step to [`TESTING.md`](../../TESTING.md) that displays the build-stamp and
fails loudly on cache/repo divergence.
**Linked tests:** none yet.

### P2 — the source enum is hard-coded in prose; drift is invisible (`TODO-SOURCE-CAPABILITY-PROBE`)
**What:** Resolve the supported-source list from the CLI at runtime (`agent-data docs <listing>` capability
metadata) instead of the static contract prose; validate `config.sources` against the **live** enum; surface
**"Supported sources: …"** in the welcome/home dashboard.
**Why:** The contract doc hard-codes the sources, so reality drifts silently — exactly how "Workday dropped"
and "Ashby/Greenhouse/Lever added" became stale-doc events.
**Impact:** the skill's notion of which sources exist can diverge from the live API with no signal; a run can
under-search or reference a dropped source, unnoticed until someone reads raw output.
**How to apply:** add a capability read to preflight; cache it for the run; render the list in the dashboard
and validate `search.sources` against it (unknown token → the existing `E-SOURCE-UNSUPPORTED` footnote, now
keyed off live data rather than a hard-coded enum).
**Linked tests:** none yet.

### P2 — a run never states which sources it searched (`TODO-RUN-SOURCE-DISCLOSURE`)
**What:** Every run summary + digest counts line names the sources **searched**, and (via
`TODO-SOURCE-CAPABILITY-PROBE`) the sources **available but not enabled** — e.g. "Searched: linkedin, ashby ·
Available but not enabled: greenhouse, lever".
**Why:** A single-source run is visually identical to a four-source run; the only reason this session's
LinkedIn-only miss was caught is that a human eyeballed the results.
**Impact:** source-coverage regressions (a mis-set config, a stale skill, a stretched-out source) ship
invisibly — the digest looks complete.
**How to apply:** add the sources line to the 5-line run summary and the digest header. Complements the repo's
per-source counts (which only list sources that *were* searched, never the available-but-missing delta).
**Linked tests:** none yet.

### P3 — existing workspaces silently inherit the default source set (`TODO-SOURCES-MIGRATION-NUDGE`)
**What:** When the live source enum (`TODO-SOURCE-CAPABILITY-PROBE`) contains sources not in `config.sources`
(or the key is absent), nudge on the home/onboarding view: "Greenhouse and Lever are now available — want to
add them?"
**Why:** Pre-multi-source workspaces have no `search.sources` key and silently take the `["linkedin","ashby"]`
default; users never learn broader coverage exists.
**Impact:** users under-search indefinitely without knowing wider coverage is available — a silent value gap,
not an error.
**How to apply:** compare the live enum against the effective config on the home view; surface an additive,
conversational nudge (never auto-edit config). Downstream of the new skill actually installing.
**Linked tests:** none yet.

### P2 — delegation guidance is deferred to model-runtime and to an adapter how-to (`TODO-DELEGATION-ALTITUDE`)
**What:** The run skill has the model **read a platform-adapter doc mid-run** to learn (a) whether the harness
has a concurrent-subagent primitive, (b) how to invoke it, and (c) the tier→model map — and phrases the
fan-out as a runtime conditional ("if your harness supports subagents…"). Replace this with harness
capabilities **resolved once and read as data**.
**Why:** On a harness with native delegation, teaching the model to read a doc about spawning its *own*
subagents is the wrong altitude — it adds first-action latency and makes the plugin carry per-harness
delegation mechanics that rot. The "if your harness supports subagents" phrasing defers to model-runtime a
fact that is fixed at **install** time.
**Impact:** every run pays a doc-read the model shouldn't need; the per-harness mechanism prose is silent
maintenance debt (drifts as each host's tooling changes, with no test guarding it).
**How to apply:** **Recommended (B1)** — the harness is already known at setup (each host's
`agent_data_init_flag`, e.g. `--claude-code`); capture that identity into a marker at install (runtime
env-probe as fallback), and have the skills deterministically load the active adapter's **capability record**
— `{ delegate_detail_reads: true, tier_to_model: {fast: haiku, …}, scheduler, run_recipe }` — as *data*. The
model then reads a resolved boolean + a small table and uses its **own native** subagent tool for the
mechanism (never a plugin-authored how-to). This preserves the load-bearing "one shared `skills/` tree — no
per-platform bundle" principle: the record is a small selected/generated data file, not a forked skill.
**Rejected (B2)** — install-time skill specialization (templating literals into a per-harness skill fork):
cleanest read-time, but violates the single-tree principle and adds a build step plus generated cache
artifacts. Also, define the precedence between the `search.detail_model` tier and a user's standing model
preference (this run honored config; the rule is currently unwritten).
**Linked tests:** none yet.

### P2 — no in-product signal that a newer plugin version exists (`TODO-UPDATE-AVAILABLE`)
**What:** Detect when a newer published version/build exists and surface it non-blockingly in the welcome/home
dashboard — e.g. "Update available: 0.3.0 → 0.4.0 — run `<update command>`". Compare the installed
version/build-stamp (`TODO-SKILL-BUILD-STAMP`) against the latest published (the `marketplace.json` the plugin
already ships, or a lightweight remote version endpoint).
**Why:** Today a user has to check the repo to know they're behind — the exact staleness that voided this
dogfooding session, now from the *user's* side. Staleness should announce itself.
**Impact:** users run stale skills indefinitely (missing sources, missing fixes) with no prompt; the gap only
surfaces if someone manually diffs against the repo.
**How to apply:** on the home/onboarding view, read the installed version and compare to the latest published;
if behind, show a one-line banner + the update command (`TODO-UPDATE-COMMAND`). Cache the check (don't hit the
network every run). Never auto-update. **Depends on** `TODO-SKILL-BUILD-STAMP` (a reliable local version/build
id to compare) and pairs with `TODO-UPDATE-COMMAND`.
**Linked tests:** none yet.

### P3 — no easy "update the plugin" affordance (`TODO-UPDATE-COMMAND`)
**What:** Surface a one-step update path — the exact host command to pull the latest plugin — in the
update-available banner and as a documented recipe. The skill can't self-update, but it can hand the user the
precise command.
**Why:** Even once a user knows they're behind (`TODO-UPDATE-AVAILABLE`), the update path is host-specific and
undocumented in-product, so they fall back to manual repo/plugin-manager fiddling.
**Impact:** a known-stale install stays stale because updating is friction; the coverage/fix gap persists.
**How to apply:** add **"Update recipe"** entries for the primary tested harnesses first — Claude Code and
Codex — alongside their existing Run recipes. Show the host's plugin-manager update command verbatim from the
active adapter. Defer update recipes for other adapters until that adapter is promoted by
`TODO-HARNESS-SUPPORT-SCOPE` with a live install/run/update verification transcript. This rides the same
capability-record mechanism as `TODO-DELEGATION-ALTITUDE`: `update_recipe` becomes another resolved
per-harness literal, so no forked skill and no model-runtime guessing.
**Linked tests:** none yet.

### P2 — broad harness support is overstated relative to live verification (`TODO-HARNESS-SUPPORT-SCOPE`)
**What:** Reframe non-Claude/Codex harnesses as "expected to work, not deeply tested" until each has a
live install/run/update verification lane. Keep Claude Code and Codex as the primary supported surfaces for
product-critical affordances such as update banners and scheduling recipes.
**Why:** The repo prematurely extended support language and installation instructions across several
harnesses, but only Claude Code and Codex have meaningful live testing. Treating every adapter as equally
supported makes future product work spend effort on unverified surfaces and can hand users commands that were
never exercised.
**Impact:** users on unverified harnesses may read aspirational install/update/schedule copy as a tested
promise; regressions on those hosts stay invisible because CI mostly checks structure, not real runtime
behavior.
**How to apply:** mark Claude/Codex as primary supported harnesses in user docs; label other adapters as
experimental/expected-to-work; require a live verification transcript before promoting any adapter to primary
or adding product-critical commands like update recipes.
**Linked tests:** none yet; future adapter-promotion work should add a manual live verification lane to
`TESTING.md`.
