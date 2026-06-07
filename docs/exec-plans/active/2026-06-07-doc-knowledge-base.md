---
title: Documentation Knowledge Base
state: active
created: 2026-06-07
---

# Documentation Knowledge Base — Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This is the CHECKED-IN execution plan; it carries the live Progress Log and Decision Log at the bottom — every task appends to them as part of its commit.

**Goal:** Build a documentation knowledge base that puts all required context in-repo, so a coding agent (Claude Code) working *on* `job-search-os` can reason about the project from a small, stable entry point (`AGENTS.md`) that points to deeper sources (progressive disclosure) — and so CI fails any PR that lets the knowledge base rot. The knowledge base is enforced mechanically by a stdlib doc-linter (run in CI) and semantically by a `doc-reviewer` agent (per-commit during implementation, and on-demand as a doc-gardening sweep). The single biggest risk this plan guards hardest against is the knowledge base *re-stating* the runtime contracts that already live in `shared/references/` and silently drifting from them — recreating the exact problem `build.sh` exists to prevent. The knowledge base **points to** `shared/references/`; it never duplicates it. A dedicated, tested lint rule enforces this.

**Architecture:** A small, stable entry point plus enforced pillars, layered for progressive disclosure:
- **Entry point:** `AGENTS.md` is the canonical map (a map, not the territory; under a size budget). `CLAUDE.md` is a one-line stub pointing to it so Claude Code auto-injects the map.
- **Pillars (under `docs/` and a few repo-root files):** architecture, product sense, reliability, security, interface, plans methodology, a qualitative quality-score, plus catalogued `design-docs/`, `exec-plans/`, and `product-specs/` (each with an `index.md`).
- **Enforcement layer:** `scripts/doc_lint.py` (stdlib, mirrors `scripts/philosophy_guard.py`) runs a registry of rules; `scripts/gen_osctl_docs.py` emits a generated command reference from argparse with a sync-check test; a `doc-reviewer` agent does the semantic doc-vs-code check.
- **Point, don't duplicate:** every knowledge-base doc that touches a runtime contract links to the owning `shared/references/*.md` instead of restating it. `ARCHITECTURE.md`, `RELIABILITY.md`, and `INTERFACE.md` are the highest-risk duplicators; the no-shared-reference-duplication rule guards them.

**Tech Stack:** Python 3.9+ (stdlib only, matching the project — no PyYAML runtime dep; frontmatter is parsed by a tiny hand-rolled flat `key: value` + bracket-list parser), pytest (subprocess harness via `sys.executable`, mirroring `tests/test_philosophy_guard.py`), Markdown knowledge-base docs, Claude Code subagents (the `doc-reviewer`), the `gh` CLI (for the on-demand gardening fix-up PR), GitHub Actions (the doc-lint + generated-docs-sync CI gates).

**Conventions inherited from the repo (do not regress):**
- **Single source of truth:** edit `shared/references/*.md` and `scripts/*`, then run `./scripts/build.sh` to re-sync each skill's bundled copies. Never hand-edit `skills/*/references/` or `skills/*/scripts/`. The knowledge base **points to** these references, never duplicates them — including in the knowledge base itself.
- **Stdlib-only Python 3.9+**, pytest subprocess harness, no new runtime deps.
- **Qualitative-not-numeric / frequency-not-budget / private-local / named-errors** — including in the knowledge base itself (hence the qualitative `QUALITY_SCORE.md`).
- **Scoped conventional commits** (`feat(scope):`, `docs(scope):`, `test(scope):`, `ci:`).

---

## Execution protocol — every task follows this

1. **Red:** write the failing test/fixture (a linter rule or the generator) — run it, watch it fail.
2. **Green:** implement the minimal code.
3. **Refactor:** extract shared helpers; keep tests green.
4. **Re-sync** if `shared/` or `scripts/` changed: `./scripts/build.sh`.
5. **Gate:** `python3 -m pytest -q` **and** `python3 scripts/doc_lint.py --root .` — both green.
6. **Commit** with a scoped conventional message.
7. **Spawn a fresh `doc-reviewer` subagent** scoped to the docs this commit touched (`git show --name-only HEAD | grep -E '\.md$'`); two-stage review (a semantic doc-vs-code check, then a reviewer confirming the findings are real). Fix real drift now or log it in the Decision Log. (Steps 7–8 begin once the `doc-reviewer` agent exists; earlier tasks note "reviewer n/a — agent not yet created".)
8. **Log** progress in this file's Progress Log as part of the commit.

The `doc-reviewer` runs in two modes from one definition: a **per-commit review** scoped to a commit's touched docs (reports findings; real drift is fixed in a follow-up commit within the same task, or logged in the Decision Log if deferred); and an **on-demand gardening sweep** over the whole `docs/` tree (plus `doc_lint.py --strict-fresh`) that opens a fix-up PR via the embedded `gh` recipe — it proposes semantic rewrites for human review and never force-merges. There is no cron (gardening is invoked manually).

---

## The doc-lint rule set

`scripts/doc_lint.py` runs each rule as a `scan_<rule>(root) -> list[str]` sub-check dispatched through an ordered `RULES` registry; `main()` aggregates, prints `Doc lint FAILED:` + hits and returns 1, else `Doc lint: clean.` and 0. Flags: `--root` (point tests at a fixture tree), `--strict-fresh` (escalate staleness warnings to failures), and `--only <rule>` (run only the named rule(s); repeatable — lets each rule's unit tests run in isolation). The knowledge base = a few root files (`AGENTS.md`, `CLAUDE.md`, `ARCHITECTURE.md`) plus everything under `docs/`. Each rule is one TDD task: a fixture pair (or inline `tmp_path` tree) + named tests following the `test_philosophy_guard.py` subprocess shape, plus the gate `test_kb_is_clean()` which runs all rules against the repo and asserts return code 0.

| # | Rule | Checks | Fail example |
|---|---|---|---|
| 1 | `internal-links` | Every repo-relative Markdown link `](…)` and same-file `](#anchor)` resolves to an existing file / heading; `http(s)`/`mailto` skipped; links into `shared/references/` allowed. | a link to `./does-not-exist.md` |
| 2 | `frontmatter-schema` | Files under `design-docs/` and `exec-plans/{active,completed}/` (except `index.md`) carry required frontmatter. **design-docs:** `title`, a `status` from its enum, a `verified` value from its enum, an ISO `last_reviewed`, and a `code_refs` list. **plans:** `title`, a `state` from its enum, an ISO `created`, plus a `completed` date when the state is completed. | omits `status:` or uses an out-of-enum value |
| 3 | `code-refs-exist` | Every path listed in a design-doc's `code_refs:` exists in the repo (the mechanical half of "doc matches code"). | `code_refs: [scripts/deleted.py]` |
| 4 | `index-completeness` | `design-docs/index.md`, `product-specs/index.md`, and `exec-plans/index.md` each link to **every** sibling doc; no index entry points at a missing file. | index omits an existing sibling |
| 5 | `quality-score-coverage` | `QUALITY_SCORE.md` has an entry for **each** of the canonical 5 domains and 5 layers (names held in a linter constant), each with a grade word from the qualitative grade set and a `gaps` field. | omits a domain |
| 6 | `plan-location` | A plan's `state:` agrees with its directory (`active/` ⇒ active, `completed/` ⇒ completed); no loose plan files in the `exec-plans/` root. | a completed-state plan sitting in `active/` |
| 7 | `no-shared-reference-duplication` **(key rule, lands Task 1.3)** | Live knowledge-base docs don't restate `shared/references/` contracts. A curated signature list (the frequency enum, the `run_id` timestamp format, the run-health states, the job-`status` enum, each `E-*` code's user-facing wording, the digest counts-line template) flags any line reproducing a signature **unless** that line/section links to the owning `shared/references/*.md` (the allow-rule, mirroring `philosophy_guard`'s `ALLOW_LINE`). Exempts process artifacts and historical/superseded snapshots (see D4). | a doc that lists the frequency enum with no link |
| 8 | `freshness-markers` | `last_reviewed` is present and parseable; older than the staleness window emits a **warning** (matching the brief-staleness convention); `--strict-fresh` makes it a failure (for the on-demand freshness sweep). | a very old `last_reviewed` |
| 9 | `agents-map` | `AGENTS.md` exists (when a `docs/` tree is present), stays under a line-count budget (keeping it a *map*), and links to each pillar (`ARCHITECTURE.md`, the three `index.md`s, `QUALITY_SCORE.md`, `PRODUCT_SENSE`/`RELIABILITY`/`SECURITY`/`INTERFACE`/`PLANS`, core-beliefs) **and** to `shared/references/`. | `AGENTS.md` missing a pillar link or oversize |

---

## Phased task breakdown

Phases run in order. Each task = files + red/green/refactor + scoped commit (+ per-commit reviewer once available). Enforcement (the linter, the entry point, the reviewer) lands first so every doc authored afterward is born compliant and reviewed.

### Phase 0 — Bootstrap enforcement + entry point

- [x] **0.1 Linter skeleton + clean-repo gate.** Create `scripts/doc_lint.py` (skeleton with zero rules ⇒ always clean) + `tests/test_doc_lint.py` (`test_lint_runs`, `test_kb_is_clean`). Red→green. Commit `feat(docs): doc_lint skeleton + clean-repo gate`.
- [x] **0.2 Rule 1 `internal-links`** + fixtures + tests. Refactor out shared `iter_md_files()` / `parse_links()` / `slugify()` helpers (reused by Rules 4, 7, 9). Commit `feat(docs): doc_lint internal-link rule`.
- [x] **0.3 `AGENTS.md` + Rule 9 `agents-map`.** Author the small map; create **stubs** for its forward-link targets (`ARCHITECTURE.md`, the three `index.md`s, `core-beliefs.md`, and the pillar docs) with `status: aspirational` frontmatter so Rule 1 stays green; add Rule 9 + fixtures + tests + the `--only`/`RULES` registry. This is the moment the real knowledge base starts passing the linter. Commit `feat(docs): AGENTS.md entry-point map + agents-map rule`.
- [x] **0.4 `CLAUDE.md` stub + materialize this plan.** Create `CLAUDE.md` (one line → `AGENTS.md`); create `docs/exec-plans/active/2026-06-07-doc-knowledge-base.md` (this file) in writing-plans form, with the Progress Log and Decision Log sections every later task appends to. Commit `docs(kb): CLAUDE.md stub + checked-in exec-plan with progress & decision logs`.
- [x] **0.5 Extend CI.** Add a `Doc lint` step to `.github/workflows/ci.yml` (`python3 scripts/doc_lint.py --root .`). Commit `ci: run doc_lint on PRs`.
- [x] **0.6 `doc-reviewer` agent.** Create `.claude/agents/doc-reviewer.md` (both modes + the `gh` fix-up-PR recipe). Smoke-test it against one stub doc. Commit `feat(docs): doc-reviewer agent (per-commit + on-demand gardening)`.

### Phase 1 — Remaining lint rules (one TDD task each)

One task per rule, each mirroring the Rule-1 pattern (rule fn + pass/fail fixtures + named tests + commit `feat(docs): <rule> lint rule`):

- [x] **1.1 Rule 2 `frontmatter-schema`** — the hand-rolled frontmatter parser + required-key/enum checks for design-docs and plans.
- [x] **1.2 Rule 3 `code-refs-exist`** — every `code_refs:` path resolves in the repo.
- [x] **1.3 Rule 7 `no-shared-reference-duplication`** (the key rule) — author the forbidden-signature list from `shared/references/`, prove the link allow-rule, and apply the exemptions in D4.
- [x] **1.4 Rule 4 `index-completeness`** — each `index.md` links every sibling; no entry points at a missing file.
- [x] **1.5 Rule 5 `quality-score-coverage`** — `QUALITY_SCORE.md` covers every canonical domain and layer with a grade word + gaps.
- [x] **1.6 Rule 6 `plan-location`** — a plan's `state:` agrees with its directory; no loose plans in the `exec-plans/` root.
- [x] **1.7 Rule 8 `freshness-markers`** — `last_reviewed` parseable; stale ⇒ warning; `--strict-fresh` ⇒ failure.

After Phase 1 the linter is complete and green against the Phase-0 stubs; every later doc is authored to keep it green.

### Phase 2 — Author the real KB docs (replace stubs, under full enforcement)

Each task: write the real doc (passing every rule, **linking** to `shared/references/` for any contract), keep `doc_lint --root .` green, commit `docs(kb): <doc>`, spawn the per-commit reviewer.

- [x] **2.1 `ARCHITECTURE.md`** — the 5 product domains × 5 layers and how they fit; points to `shared/references/` for every contract.
- [x] **2.2 `design-docs/core-beliefs.md`** — agent-first operating principles (statement / why / enforced-by-link / how-to-verify).
- [x] **2.3 Port the design specs + `design-docs/index.md`** — port the source design specs into `design-docs/` with frontmatter; catalogue them with verification status.
- [x] **2.4 Port plans + move the hardening plan** — port the source plans into `exec-plans/completed/` and move `docs/superpowers/plans/2026-06-07-job-search-agent-hardening.md` into `completed/` (add `state:` frontmatter; remove the now-empty `docs/superpowers/`).
- [x] **2.5 `exec-plans/tech-debt-tracker.md` + `exec-plans/index.md`** — make the tracker canonical (migrate `TODOS.md`; convert `TODOS.md` to a one-line pointer; fix the one `TESTING.md` reference); catalogue active/ + completed/ + the tracker.
- [x] **2.6 `product-specs/new-user-onboarding.md` + `product-specs/index.md`** — the magical-moment onboarding spec (points to the job-search skill) + the catalogue.
- [x] **2.7 `docs/PRODUCT_SENSE.md`** — product philosophy + non-goals/YAGNI + who-the-user-is.
- [x] **2.8 `docs/QUALITY_SCORE.md`** — every domain × layer graded with qualitative words + gaps. (Done within Task 1.5, which the coverage rule forced.)
- [x] **2.9 `docs/RELIABILITY.md`** — determinism, named errors, retry/circuit-breaker, run-health, headless surfacing, testing/eval strategy (maps into `shared/references/`).
- [x] **2.10 `docs/SECURITY.md`** — private-local, deny-all `.gitignore`, no-PII, the consent hook, the fake shim.
- [x] **2.11 `docs/INTERFACE.md`** — the conversational / CLI / digest / home surfaces (points to `conventions.md` for the digest contract).
- [x] **2.12 `docs/PLANS.md`** — plans methodology (ephemeral vs exec-plans; TDD/subagent/reviewer) + how to run the on-demand gardening sweep.

### Phase 3 — Generated docs

- [ ] **3.1 Generate `docs/generated/osctl-commands.md`** — `scripts/gen_osctl_docs.py` imports `osctl.py`'s subparsers and emits the command reference with a do-not-edit header + `tests/test_gen_osctl_docs.py` sync-check (generate to temp, assert byte-match with the committed file — mirrors CI's build-sync gate). Red→green. Commit `feat(docs): generate osctl-commands.md from argparse`.
- [ ] **3.2 CI generated-docs sync check** — add a `Generated docs in sync` step to `.github/workflows/ci.yml` (run the generator, fail if it changes `docs/generated`). Commit `ci: generated-docs sync check`.

### Final — Wire pointers + full green gate

- [ ] **F.1 Wire pointers + full green gate.** Update `CONTRIBUTING.md` (add doc-lint to the everything-green checklist; link `AGENTS.md`) and `README.md` (one agent-facing-map pointer). Full gate: `pytest -q` green, `doc_lint --root .` clean, `philosophy_guard --root .` clean, `claude plugin validate . --strict` passes, `./scripts/build.sh` is a no-op, `gen_osctl_docs.py` is a no-op. Commit `docs(kb): wire CONTRIBUTING/README; final green gate`.

---

## Progress Log

- 2026-06-07 — **Task 0.1** done (`6f8283b`): `doc_lint.py` skeleton + clean-repo gate. `64 passed`.
- 2026-06-07 — **Task 0.2** done (`0b4f7c0`): internal-links rule + shared `iter_md_files`/`parse_links`/`slugify` helpers. `68 passed`.
- 2026-06-07 — **Task 0.3** done (`20ea38a`): `AGENTS.md` map + agents-map rule + `--only`/RULES registry + KB stubs. `72 passed`.
- 2026-06-07 — **Task 0.4** done (`0baa3e0`): `CLAUDE.md` stub + this checked-in exec-plan.
- 2026-06-07 — **Task 0.5** done (`a1c83d7`): `Doc lint` step added to `.github/workflows/ci.yml` (runs after the philosophy guard).
- 2026-06-07 — **Task 0.6** done: `.claude/agents/doc-reviewer.md` (per-commit review + on-demand gardening sweep w/ `gh` fix-up-PR recipe). Per-commit doc-reviewer runs begin now. Phase 0 complete.
- 2026-06-07 — **Phase 1 complete** — all 9 lint rules implemented via TDD; `98 passed`; `doc_lint --root .` clean (default and `--strict-fresh`):
  - **1.1** (`6babbf5`) frontmatter-schema · **1.2** (`ddf77c5`) code-refs-exist · **1.3** (`34cc844`) no-shared-reference-duplication — preceded by `0f8a789`, which relocated the hardening plan into `exec-plans/completed/` (the move substep of Task 2.4, pulled forward so the new rule's real KB stayed clean) · **1.4** (`3584273`) index-completeness (+ brought the live indexes to completeness) · **1.5** (`79f773b`) quality-score-coverage (+ authored the real `QUALITY_SCORE.md`, folding Task 2.8; the doc-reviewer verified its gaps claims fresh) · **1.6** (`7e84fe9`) plan-location · **1.7** (`4024f72`) freshness-markers.
- 2026-06-07 — **Phase 2 complete** — the full knowledge base authored under enforcement; `100 passed`; `doc_lint --root .` clean. Substantive docs were each verified by a per-commit doc-reviewer pass:
  - **2.1** (`78262d5`) `ARCHITECTURE.md` (reviewer: fresh) · **2.2** (`df6e2e2`) `core-beliefs.md` — reviewer caught a real anchor bug, fixed in `2197487` (see D8) · **2.3** (`c7c28a7`) ported 3 design specs as historical snapshots · **2.4** (`c92f6e0`) archived plans A/B/D · **2.5** (`414a50e`) tech-debt-tracker made canonical · **2.6** (`a246907`) onboarding product spec (reviewer: fresh) · **2.7** (`a188fe6`) `PRODUCT_SENSE.md` · **2.8** done within Task 1.5 · **2.9** (`ea4eb58`) `RELIABILITY.md` (reviewer: fresh) · **2.10** (`ff6d116`) `SECURITY.md` · **2.11** (`701deb5`) `INTERFACE.md` — reviewer caught a no-dup gap, fixed in `cc8fb7c` (see D9) · **2.12** (`35985bf`) `PLANS.md`.

## Decision Log

- **D1 — Inline `tmp_path` fixtures, not committed fixtures.** Rule unit tests write fixtures inline (mirroring `tests/test_philosophy_guard.py`) instead of committing files under `tests/fixtures/`. Simpler, matches the repo pattern, and avoids the intentionally-broken-fixture exclusion problem.
- **D2 — `--only <rule>` flag + `RULES` registry.** Each rule's unit tests run in isolation, so adding rule N+1 never breaks rule N's fixtures. `test_kb_is_clean` still runs all rules.
- **D3 — agents-map "missing AGENTS.md" gated on `docs/`.** The rule only requires `AGENTS.md` when a `docs/` dir is present, so an empty tree / single-rule fixture run stays clean.
- **D4 — Rule 7 scope (lands Task 1.3).** `no-shared-reference-duplication` applies only to current/live KB docs. It EXEMPTS `docs/exec-plans/**` (process artifacts) and design-docs with `status: historical`/`superseded` (point-in-time snapshots that legitimately contain contract values). Enforced on the live pillar docs (`ARCHITECTURE.md`, `RELIABILITY.md`, `INTERFACE.md`, etc.) and current design/product docs.
- **D5 — Outline adaptations (approved).** Dropped `docs/references/`, `docs/generated/db-schema.md`, `docs/DESIGN.md`, `docs/FRONTEND.md`. `generated/` holds `osctl-commands.md` (from argparse). `FRONTEND.md`→`INTERFACE.md`. `QUALITY_SCORE.md` uses qualitative grades (`strong/adequate/thin/missing`). Tech-debt tracker becomes canonical at `docs/exec-plans/tech-debt-tracker.md`. Recurring doc-gardening is on-demand only (no cron).
- **D6 — doc-reviewer invocation.** The custom agent type isn't live mid-session, so the per-commit / on-demand reviewer is invoked by dispatching a general-purpose subagent that reads and follows `.claude/agents/doc-reviewer.md`. A fresh Claude Code session loads the agent natively.
- **D7 — per-commit reviewer scope.** After each commit the controller runs the reviewer's first step (identify changed KB docs) and escalates to a full semantic subagent only when the commit touches substantive KB content. Linter-infra commits (`scripts/`+`tests/`) and structural / process-artifact-only changes (indexes, this progress log) take the "no reviewable KB content" fast path.
- **D8 — `slugify` aligned to github-slugger (fix `2197487`).** The doc-reviewer caught that `slugify` collapsed consecutive hyphens, diverging from GitHub (which renders ` — ` between words as a DOUBLE hyphen anchor). `slugify` now matches GitHub (no collapse), so `internal-links` actually catches GitHub-broken anchors; a genuinely-broken em-dash anchor in `core-beliefs.md` was corrected. (Demonstrates the reviewer→stage-2→fix loop: the reviewer's specific suggestion was backwards, but it surfaced a real linter blind spot.)
- **D9 — no-dup status-enum signature is separator-agnostic (fix `cc8fb7c`).** The doc-reviewer caught `INTERFACE.md` restating the job-status enum in comma form, which the pipe-only signature missed. The signature now uses `\W+` between the words (catches comma, pipe, and space forms); `INTERFACE.md` now links `conventions.md` instead of listing the statuses.
