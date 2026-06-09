---
title: Voice & Onboarding Clarity
state: completed
created: 2026-06-09
completed: 2026-06-09
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

- [x] **1. Exec plan checked in** (this file) + `exec-plans/index.md` entry.
      Commit `docs(plans): voice-and-onboarding-clarity exec plan`.
- [x] **2. Eval expectations first (red).** `job-search-run` eval 10 (new already-seen wording,
      never "database"); `job-search-agent` eval 3 (native `/loop`, private-local data — also
      fixes stale "cron/schedule" wording); `job-search` evals 1–2 (zero-context asks, no
      internal jargon, brief rendered inline); `job-preference-interview` eval 1 (ends by
      showing the rendered brief + one-line save location).
      Commit `test(evals): assert plain-English voice + already-seen wording`.
- [x] **3. `shared/references/voice.md`** (the communication contract, ≤ ~50 lines) +
      `errors.md` already-seen rewording + `./scripts/build.sh` re-sync (generated copies
      committed; CI "build is a no-op" gate).
      Commit `feat(voice): shared voice contract — plain English, zero-context asks, render-inline`.
- [x] **4. Skills follow voice.** `onboarding.md` (zero-context directive + workspace /
      preferences / scheduling question rewrites + render rules + checklist item), `home.md`
      (show-your-brief quick action, render-inline rules), `job-search/SKILL.md` +
      `job-search-run/SKILL.md` read-list wiring, `job-search-run/SKILL.md` description reword
      ("skip postings it has already seen") + interactive-narration section,
      `job-preference-interview/SKILL.md` (render the finished brief back; depth-ask context),
      `job-search-agent/SKILL.md` (where-to-find-things row).
      Commit `feat(skills): onboarding/home/runner follow the voice contract`.
- [x] **5. Docs that quote the old wording.** README (2 sites), TESTING.md (3 sites),
      ARCHITECTURE.md, `docs/INTERFACE.md` (+ voice.md pointer),
      `docs/product-specs/new-user-onboarding.md` (+ pointer, `last_reviewed` bump).
      Commit `docs: already-seen wording; voice contract pointers`.
- [x] **6. Gates + live verification.** `pytest`, `doc_lint.py`, `philosophy_guard.py`,
      build-no-op, `claude plugin validate --strict`, residual grep. Live (real agent-data,
      TESTING.md §0.2 sandbox): first-run voice pass, immediate re-run (already-seen wording via
      real dedup), home + show-brief; re-run the touched eval cases live.
- [x] **7. Release.** `.claude-plugin/plugin.json` 0.2.0 → 0.2.1.
      Commit `chore(release): bump plugin to 0.2.1`. Flip this plan to completed.

## Progress log

- 2026-06-09 — plan created; baseline failure documented (first-run transcript with improvised
  internal jargon and context-free asks). `713fb6e`
- 2026-06-09 — task 2: eval expectations updated (red). `de3f715`
- 2026-06-09 — task 3: voice.md + errors.md rewording + build sync. `cece62c`
- 2026-06-09 — task 4: onboarding/home/runner/interview/agent follow the contract. `a91d91a`
- 2026-06-09 — task 5: README/TESTING/ARCHITECTURE/INTERFACE/product-spec wording + KB pointers.
  `534822f`
- 2026-06-09 — live verification round 1 (sandboxed per TESTING.md §0.2, real agent-data): full
  first-run onboarding ran end-to-end (17 postings judged, healthy digest, home view with the new
  show-brief action); found the first-line narration leak class — the opening line of each skill
  parroted its own intro ("route by resolving the OS state"; "Running a headless job-search pass.
  First, loading the reference files…"). Fixed by making the router step silent (`7d9b176`) and
  front-loading the never-say list adjacent to each intro (`908d3e3`).
- 2026-06-09 — live verification round 2 (green): standalone interview ends by rendering the brief
  + one-line save location; immediate re-run prints "you've already seen all 17 of the recent
  postings" (real dedup, no 'database' anywhere); home + "show your preferences brief" render
  inline with zero jargon; post-fix run narration is outcome-language start to finish ("Checking
  for new postings…", "Reading all 19 in full now…"). Real `~/.job-search` untouched (mtimes
  pre-date the test session); sandboxes torn down.
- 2026-06-09 — task 7: plugin 0.2.0 → 0.2.1; plan completed.

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
- **Voice rules must sit adjacent to the text the model parrots.** Live runs showed the first
  narration line of a skill mirrors its intro paragraph, emitted before deep sections (or
  bundled references) are read — so the never-say list is front-loaded at the top of each
  user-facing SKILL.md in addition to living in `voice.md`. A rule that only lives in a
  referenced file arrives too late for the first line.
