---
title: Voice & Onboarding Clarity
state: active
created: 2026-06-09
---

# Voice & Onboarding Clarity — Execution Plan

**Goal:** Make every user-facing surface speak plain, outcome-first English. A real first-run
surfaced four gaps: (1) setup questions assume context a brand-new user doesn't have ("private
workspace"); (2) nothing governs narration, so internal vocabulary leaks ("running the headless
pass", "deduping against your database"); (3) user-facing copy calls `jobs.jsonl` a "database";
(4) generated documents (the brief) are pointed at, not shown. The fix is a shared communication
contract — `shared/references/voice.md` — wired into the user-facing skills, plus context-first
rewrites of the onboarding questions and a plain-English rewording of the already-seen message.

**Non-goals:** No storage/mechanism changes (`jobs.jsonl` stays as-is); no changes to headless
run behavior, retries, or exit semantics; the `E-*` cause+fix wording stays verbatim-quotable
(voice.md carves out named errors, slash commands, and file names the user must act on).

**Approach (red → green):** The baseline failure is the recorded first-run transcript (the
improvised jargon above). Eval expectations are updated *first* to assert the new behavior —
context-carrying asks, no internal vocabulary, the brief rendered inline, the new already-seen
wording — then voice.md and the playbook edits land to make them pass, verified live per
TESTING.md §0.2 sandboxing.

## Tasks

- [ ] **1. Exec plan checked in** (this file) + `exec-plans/index.md` entry.
      Commit `docs(plans): voice-and-onboarding-clarity exec plan`.
- [ ] **2. Eval expectations first (red).** `job-search-run` eval 10 (new already-seen wording,
      never "database"); `job-search-agent` eval 3 (native `/loop`, private-local data — also
      fixes stale "cron/schedule" wording); `job-search` evals 1–2 (zero-context asks, no
      internal jargon, brief rendered inline); `job-preference-interview` eval 1 (ends by
      showing the rendered brief + one-line save location).
      Commit `test(evals): assert plain-English voice + already-seen wording`.
- [ ] **3. `shared/references/voice.md`** (the communication contract, ≤ ~50 lines) +
      `errors.md` already-seen rewording + `./scripts/build.sh` re-sync (generated copies
      committed; CI "build is a no-op" gate).
      Commit `feat(voice): shared voice contract — plain English, zero-context asks, render-inline`.
- [ ] **4. Skills follow voice.** `onboarding.md` (zero-context directive + workspace /
      preferences / scheduling question rewrites + render rules + checklist item), `home.md`
      (show-your-brief quick action, render-inline rules), `job-search/SKILL.md` +
      `job-search-run/SKILL.md` read-list wiring, `job-search-run/SKILL.md` description reword
      ("skip postings it has already seen") + interactive-narration section,
      `job-preference-interview/SKILL.md` (render the finished brief back; depth-ask context),
      `job-search-agent/SKILL.md` (where-to-find-things row).
      Commit `feat(skills): onboarding/home/runner follow the voice contract`.
- [ ] **5. Docs that quote the old wording.** README (2 sites), TESTING.md (3 sites),
      ARCHITECTURE.md, `docs/INTERFACE.md` (+ voice.md pointer),
      `docs/product-specs/new-user-onboarding.md` (+ pointer, `last_reviewed` bump).
      Commit `docs: already-seen wording; voice contract pointers`.
- [ ] **6. Gates + live verification.** `pytest`, `doc_lint.py`, `philosophy_guard.py`,
      build-no-op, `claude plugin validate --strict`, residual grep. Live (real agent-data,
      TESTING.md §0.2 sandbox): first-run voice pass, immediate re-run (already-seen wording via
      real dedup), home + show-brief; re-run the touched eval cases live.
- [ ] **7. Release.** `.claude-plugin/plugin.json` 0.2.0 → 0.2.1.
      Commit `chore(release): bump plugin to 0.2.1`. Flip this plan to completed.

## Progress log

- 2026-06-09 — plan created; baseline failure documented (first-run transcript with improvised
  internal jargon and context-free asks).

## Decision log

- **voice.md is a shared reference, not per-skill prose** — same single-source pattern as
  `errors.md`; build.sh fans it into every skill, but only the user-facing skills list it as
  required reading. Deliberately NOT wired into `evaluate-job-fit`: the runner spawns one
  evaluate-job-fit subagent per posting, so required reading there would multiply token cost
  across every parallel detail read for zero user-facing benefit.
- **"headless, non-interactive" stays in `job-search-run`'s frontmatter description** — it is
  routing text that keeps the skill from prompting in scheduled runs; the jargon ban governs
  runtime narration, not trigger descriptions.
- **voice.md carries an explicit exceptions block** (named E-* wording, slash commands, file
  names the user must act on) — without it the contract would contradict the no-silent-failures
  rule and the verbatim `/loop` recipe.
- **`job-search-agent` eval 3's "via cron/schedule" replaced with native `/loop`** while editing
  that line for the database wording — the old text contradicted the /loop-only scheduling
  design and predates it.
