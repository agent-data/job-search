---
title: Public OSS Release Readiness — docs + community files for a public launch
state: active
created: 2026-06-15
---

# Public OSS Release Readiness

> **For agentic workers:** Execute this plan task-by-task with the superpowers:subagent-driven-development sub-skill (or superpowers:executing-plans for a separate review session). Steps use checkbox (`- [ ]`) syntax for tracking. This is the CHECKED-IN execution plan; it carries the live Progress Log and Decision Log at the bottom — every task appends to them as part of its commit. Use scoped Conventional-Commit messages per `CONTRIBUTING.md`.

## Goal

Make `job-search-os` ready to flip from private to a **public open-source** repository, with two
focuses: (1) **human-facing documentation** a newcomer can act on, and (2) **OSS-readiness** —
correct public metadata, honest support claims, and the community files an evaluator expects. The
repo is already heavily and accurately documented; this plan is the **delta to release-ready**, not
a docs regeneration. Primary audience optimized for: the **prospective end user** (the
"technically comfortable job seeker") in their first ten minutes — evaluate, install, reach a first
digest. Secondary: contributors/evaluators (already well served by `AGENTS.md` → `ARCHITECTURE.md`
→ `CONTRIBUTING.md` → `TESTING.md` and the `docs/` pillars).

## Approach

Small, surgical changes. All new newcomer narrative goes into the **root `README.md`** or
`.github/` — never under `docs/` — because of one hard constraint (below). The agent-runtime
contracts (`shared/references/*`), every `SKILL.md`, and the existing `docs/` pillars are **not**
touched: they're accurate and they're the single source of truth. The 0.3.0 release ritual (version
bump + completing the zero-Python plan + a CHANGELOG) is folded in, since the owner has confirmed
the zero-Python live-API acceptance pass is green.

### Hard constraint that governs doc placement

`scripts/doc_lint.py` scans only `AGENTS.md`, `CLAUDE.md`, `ARCHITECTURE.md`, and everything under
`docs/`. Its `no-shared-reference-duplication` rule **fails any scanned doc** that reproduces a
runtime literal (the digest counts line, the run-health states, the `E-QUOTA` wording, the
frequency enum, the `run_id` format, the job-status enum, `desktop_notify_on_block`) unless that
same line links `shared/references`. Newcomer prose quotes these literals freely, so it must live in
the **root `README.md`** (not scanned) or `examples/` — exactly where it lives today. `.github/`
files are also unscanned. Exec-plans (this file included) are exempt, which is why draft prose below
can quote literals without tripping the linter.

`scripts/philosophy_guard.py` scans only `examples/` and `templates/`; none of the files this plan
adds fall under it.

## Non-goals

- **No edits to `shared/references/*`, any `SKILL.md`, or the bundled `skills/*/references/`.** Those
  are the runtime SSOT / generated copies; out of scope by design.
- **No new docs under `docs/`** for newcomer content (the placement constraint above). No
  restructuring of the existing `docs/` knowledge base or pillar docs — they're accurate; this is
  curation, not regeneration.
- **No per-skill how-to doc set.** A single conversational "everyday use" phrasebook instead — a
  per-skill how-to corpus fights the conversational-first product thesis (see `docs/PRODUCT_SENSE.md`).
- **No excluding/pruning context-only docs from the public repo.** The linter couples them
  (`agents-map` requires `AGENTS.md` to link every pillar; `index-completeness` requires each index
  to link every sibling), and the docs-as-product posture makes keep-all the right public call.
- **No publishing to the agent-data marketplace.** That listing isn't live yet; the README is
  already honest about it. Separate step, separate owner action.
- **No 1.0.0 bump, no resume tools (Plan C), no marketing site.** 0.3.0 matches the project's own
  versioning plan; the rest is future work.

---

## Phase 1 — Launch-blocking accuracy & identity

### Task 1: Reconcile the plugin author with the legal entity `[BLOCKS]`

**Files:**
- Modify: `.claude-plugin/plugin.json` (the `author` field; verify `homepage`/`repository`)

- [ ] **Step 1: Set the author to the legal entity.** The `LICENSE` copyright holder is
  `Aptiq Labs, Inc.`, but `plugin.json` declares `"author": { "name": "agent-data" }` — public
  metadata that contradicts the license. Change it to:

  ```json
  "author": { "name": "Aptiq Labs, Inc." },
  ```

- [ ] **Step 2: Confirm the public repo URL.** Verify the repo will be hosted at
  `github.com/agent-data/job-search-os`. If yes, leave `homepage`/`repository` unchanged (the
  `agent-data` org is the marketplace handle; the author is the legal entity — these can legitimately
  differ). If it will live elsewhere, update both `homepage` and `repository` to the real URL.

- [ ] **Step 3: Verify.** Run `python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))"`
  (valid JSON) and `claude plugin validate . --strict`. Expected: both pass.

- [ ] **Step 4: Commit.** `git add .claude-plugin/plugin.json && git commit -m "fix(packaging): set plugin author to the Aptiq Labs legal entity"`

### Task 2: Include all five skills in the loose-install instructions `[BLOCKS]`

**Files:**
- Modify: `README.md` (option **C**, the `ln -s` block — currently ~lines 71–75)

- [ ] **Step 1: Add the missing operator-manual skill.** Option C symlinks only four skills and
  silently omits `job-search-agent` (the operator manual). Add the fifth line so the block lists all
  five skills:

  ```bash
  ln -s "$PWD/skills/job-search-agent"         ~/.claude/skills/job-search-agent
  ```

- [ ] **Step 2: Verify the set is complete.** Run
  `ls -1 skills` and confirm every directory it prints has a matching `ln -s` line in README option C
  (`job-search`, `job-search-run`, `evaluate-job-fit`, `job-preference-interview`,
  `job-search-agent`). Expected: 5 dirs, 5 symlink lines.

- [ ] **Step 3: Commit.** `git add README.md && git commit -m "fix(docs): include all five skills in the loose-install instructions"`

### Task 3: Add an honest supported-environments note `[BLOCKS]`

**Files:**
- Modify: `README.md` (end of the `## Requirements` section)

- [ ] **Step 1: Add the note.** There's no platform overclaim today, but no honesty line either.
  Add a short subsection at the end of `## Requirements` (before the `---`):

  ```markdown
  ### Supported environments

  Tested on **Claude Code (CLI)** on macOS and Linux. Claude Code's IDE and desktop builds run the
  same plugin and are *expected* to work but are **not yet tested**. Other Claude surfaces (claude.ai
  and other hosts) are **untested** — the scheduled pass relies on Claude Code's native `/loop`,
  which those surfaces don't provide. If you try it elsewhere, the interactive parts may work; the
  scheduling won't.
  ```

- [ ] **Step 2: Verify.** Re-read the section; confirm it claims only *tested on Claude Code* and
  marks everything else expected/untested.

- [ ] **Step 3: Commit.** `git add README.md && git commit -m "docs(readme): add an honest supported-environments note"`

---

## Phase 2 — Community & security files for public launch

### Task 4: Add a vulnerability-reporting policy `[BLOCKS]`

**Files:**
- Create: `.github/SECURITY.md`

- [ ] **Step 1: Write the policy.** This is the file GitHub surfaces on the Security tab; it is the
  *reporting* policy, distinct from `docs/SECURITY.md` (the posture/explanation doc). Keep GitHub
  private reporting as the primary channel so no email needs inventing; add a real security email
  only if Aptiq Labs has one (otherwise omit that bullet):

  ```markdown
  # Security Policy

  ## Reporting a vulnerability

  If you find a security or privacy issue in Job Search OS, please report it **privately** — do not
  open a public issue:

  - Use GitHub's private vulnerability reporting: the **"Report a vulnerability"** button on this
    repository's **Security** tab.
  - (Optional, if configured) email the maintainers at the address listed on the repository profile.

  We aim to acknowledge a report within 5 business days and will coordinate a fix and disclosure
  with you.

  ## Posture and scope

  Job Search OS handles career-sensitive data **locally**. How that data is kept on your machine and
  out of any public repository — the deny-all workspace `.gitignore`, the no-PII-in-repo rule, the
  credit-free test shim — and the **explicit out-of-scope** items (a compromised machine,
  prompt-injection in fetched postings) are documented in `docs/SECURITY.md`.
  ```

  In the shipped `.github/SECURITY.md`, make that `docs/SECURITY.md` mention a Markdown link whose
  target is `../docs/SECURITY.md`.

- [ ] **Step 2: Confirm the security contact.** Decide whether to keep the optional email bullet;
  if Aptiq Labs has a security inbox, name it, otherwise delete that bullet. Do not ship a fake
  address.

- [ ] **Step 3: Verify.** Confirm the relative link resolves:
  `test -f docs/SECURITY.md && echo OK` from repo root (the `../docs/SECURITY.md` target exists).
  `.github/` is not doc_lint-scanned, so this is a manual check.

- [ ] **Step 4: Commit.** `git add .github/SECURITY.md && git commit -m "docs(security): add a vulnerability-reporting policy"`

### Task 5: Add a Code of Conduct `[TUNE]`

**Files:**
- Create: `CODE_OF_CONDUCT.md`
- Modify: `CONTRIBUTING.md` (one pointer line), `README.md` (one pointer line)

- [ ] **Step 1: Create the file from the canonical source.** Use **Contributor Covenant v2.1**
  verbatim (https://www.contributor-covenant.org/version/2/1/code_of_conduct/). Do not hand-author a
  CoC. Replace the single `[INSERT CONTACT METHOD]` placeholder in the Covenant with the project's
  enforcement contact (the same channel as the security policy — GitHub private reporting or a real
  Aptiq Labs conduct/security email).

- [ ] **Step 2: Link it from CONTRIBUTING.** Add a line near the top of `CONTRIBUTING.md` that links
  the words "Code of Conduct" to `CODE_OF_CONDUCT.md`, e.g.: *This project follows a Code of Conduct —
  by participating you agree to uphold it.*

- [ ] **Step 3: Link it from the README.** Add a short line to the contributor-pointer area of
  `README.md` linking "Code of Conduct" to `CODE_OF_CONDUCT.md` (e.g. *This project has a Code of Conduct.*).

- [ ] **Step 4: Verify.** `test -f CODE_OF_CONDUCT.md && echo OK`; confirm no `[INSERT CONTACT METHOD]`
  remains: `grep -n "INSERT CONTACT" CODE_OF_CONDUCT.md` returns nothing.

- [ ] **Step 5: Commit.** `git add CODE_OF_CONDUCT.md CONTRIBUTING.md README.md && git commit -m "docs(community): add Contributor Covenant code of conduct"`

### Task 6: Add issue and pull-request templates `[TUNE]`

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.md`, `.github/ISSUE_TEMPLATE/feature_request.md`, `.github/PULL_REQUEST_TEMPLATE.md`

- [ ] **Step 1: Bug report template.**

  ```markdown
  ---
  name: Bug report
  about: Something didn't work as documented
  labels: bug
  ---

  **What happened**

  **What you expected**

  **Steps to reproduce** (the slash command or sentence you used)

  **Run health / named error** (e.g. `E-NO-AUTH`), if the digest or home view showed one

  **Environment** — Claude Code version (`claude --version`), OS, `agent-data --version`
  ```

- [ ] **Step 2: Feature request template.**

  ```markdown
  ---
  name: Feature request
  about: Suggest an improvement
  labels: enhancement
  ---

  **The problem you're trying to solve**

  **Proposed behavior**

  **Have you checked the non-goals?** See `docs/PRODUCT_SENSE.md` — some things (numeric scores,
  budget knobs, cloud sync) are deliberately not built.
  ```

- [ ] **Step 3: Pull-request template** (mirrors the green gate in `CONTRIBUTING.md`).

  ```markdown
  ## What & why

  ## Checklist
  - [ ] `python3 -m pytest -q` passes (0 failed)
  - [ ] `python3 scripts/doc_lint.py --root .` is clean
  - [ ] `python3 scripts/philosophy_guard.py --root .` is clean
  - [ ] `./scripts/build.sh` is a no-op (bundled skill copies in sync)
  - [ ] Scoped Conventional-Commit messages
  - [ ] No numeric scores / budget / credit knobs; no PII in `examples/` or `templates/`
  ```

- [ ] **Step 4: Verify.** `ls .github/ISSUE_TEMPLATE/ .github/PULL_REQUEST_TEMPLATE.md` lists all three.

- [ ] **Step 5: Commit.** `git add .github/ISSUE_TEMPLATE .github/PULL_REQUEST_TEMPLATE.md && git commit -m "docs(community): add issue and pull-request templates"`

---

## Phase 3 — Primary-audience README content

### Task 7: Add a first-run walkthrough (the Diataxis tutorial gap) `[TUNE]`

**Files:**
- Modify: `README.md` (new section after `## Install from the marketplace (once published)`, before `## What it does`)

- [ ] **Step 1: Add the walkthrough.** This is the one genuine end-user content gap — a hand-held
  view of the first run. It quotes a digest line, so it **must** live in the README (root), never
  under `docs/`. Insert:

  ```markdown
  ## What your first run looks like

  You don't configure anything by hand. After install, run the front door and answer a few
  questions — here's the shape of it:

  ```text
  You:    /job-search-os:job-search          (or just: "set up job search")

  Claude: Looks like this is your first run. I'll create a private workspace at ~/.job-search/
          and ask a few questions to learn what you're after. What kind of role are you looking for?

  You:    senior product designer, remote in the US or hybrid in the PNW

  Claude: Got it. (a few more questions — level, must-haves, dealbreakers, what to search,
          how often) … I'll search "product designer" in the United States. Run it now?

  You:    yes

  Claude: 9 new postings · 2 strong · 2 moderate · 2 weak · 3 filtered out.
          Strongest: Senior Product Designer — Tidewater Health — Remote (US) …
  ```

  Seconds later you have a ranked digest of real postings judged against your brief — see
  `examples/sample-digest.md` for a full one. Claude then offers to keep it running on a schedule
  you choose (you can always say no).
  ```

  (Keep the `examples/sample-digest.md` reference a Markdown link in the README, as the intro already does.)

- [ ] **Step 2: Verify placement constraint.** Confirm the section is in `README.md`, not `docs/`,
  then run `python3 scripts/doc_lint.py --root .`. Expected: `Doc lint: clean.` (the literals are in
  the root README, which the linter does not scan).

- [ ] **Step 3: Commit.** `git add README.md && git commit -m "docs(readme): add a first-run walkthrough"`

### Task 8: Add an everyday-use phrasebook (the how-to gap, kept light) `[TUNE]`

**Files:**
- Modify: `README.md` (new section after the first-run walkthrough)

- [ ] **Step 1: Add the phrasebook.** Consolidate the natural-language phrasings the README only
  hints at today, sized to the conversational-first thesis (no per-skill how-to docs):

  ```markdown
  ## Everyday use — just say what you want

  Everything is conversational. You never have to remember a command or hand-edit a file:

  | To… | Say something like… |
  |---|---|
  | Set up / onboard | "set up job search" |
  | Run a search now | "find me jobs" · "run a job search now" |
  | Check status & latest digest | "check my job search" |
  | Add or change a search | "also search for staff product designer roles" |
  | Change how often it runs | "run this daily instead of hourly" |
  | Update your preferences | "update my preferences — I'm open to fully remote now" |
  | Pause / resume scheduling | "pause the scheduled search" |

  Prefer slash commands? Use `/job-search-os:job-search` (plugin installs) or `/job-search`
  (loose-skill installs).
  ```

- [ ] **Step 2: Verify.** `python3 scripts/doc_lint.py --root .` → clean (root README, unscanned).

- [ ] **Step 3: Commit.** `git add README.md && git commit -m "docs(readme): add an everyday-use phrasebook"`

### Task 9: Add status badges `[TUNE]`

**Files:**
- Modify: `README.md` (just below the bold tagline on line ~3)

- [ ] **Step 1: Add badges.**

  ```markdown
  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
  ![Tested on Claude Code](https://img.shields.io/badge/tested%20on-Claude%20Code-6b46c1)
  ```

- [ ] **Step 2: Verify.** `python3 scripts/doc_lint.py --root .` → clean (http(s) links are skipped;
  README is unscanned anyway). Eyeball that the `LICENSE` relative link is correct.

- [ ] **Step 3: Commit.** `git add README.md && git commit -m "docs(readme): add license and tested-on badges"`

---

## Phase 4 — Cut the 0.3.0 release

### Task 10: Complete the zero-Python shipped-surface plan `[BLOCKS]`

**Files:**
- Move: `docs/exec-plans/active/2026-06-11-zero-python-shipped-surface.md` → `docs/exec-plans/completed/`
- Modify: that file's frontmatter + progress log; `docs/exec-plans/index.md`

- [ ] **Step 1: Move the file.**
  `git mv docs/exec-plans/active/2026-06-11-zero-python-shipped-surface.md docs/exec-plans/completed/2026-06-11-zero-python-shipped-surface.md`

- [ ] **Step 2: Flip the frontmatter.** In the moved file set `state: completed` and add
  `completed: 2026-06-15` (the `plan-location` and `frontmatter-schema` rules require a completed
  plan to live in `completed/` and carry a `completed:` date):

  ```yaml
  state: completed
  created: 2026-06-11
  completed: 2026-06-15
  ```

- [ ] **Step 3: Log the close.** Append to that file's Progress Log:

  ```markdown
  - 2026-06-15 — live-API acceptance pass green (owner). Plan complete; released in 0.3.0.
  ```

- [ ] **Step 4: Update the index.** In `docs/exec-plans/index.md`, move the
  `Zero-Python Shipped Surface` entry from **Active** to **Completed** (point it at the new
  `completed/…` path).

- [ ] **Step 5: Verify.** `python3 scripts/doc_lint.py --root .` → clean (state matches directory;
  index links resolve and are complete).

- [ ] **Step 6: Commit.** `git add -A docs/exec-plans && git commit -m "docs(plans): complete the zero-Python shipped-surface plan"`

### Task 11: Bump to 0.3.0 and seed the CHANGELOG `[BLOCKS]`

**Files:**
- Modify: `.claude-plugin/plugin.json` (`version`)
- Create: `CHANGELOG.md`

- [ ] **Step 1: Bump the version.** `0.2.3 → 0.3.0` in `.claude-plugin/plugin.json` (minor: the
  zero-Python shipped-surface change is user-visible/behavioral per `CONTRIBUTING.md` versioning).

  ```json
  "version": "0.3.0",
  ```

- [ ] **Step 2: Create the CHANGELOG** (Keep a Changelog format; first public release):

  ```markdown
  # Changelog

  All notable changes to this project are documented here. The format is based on
  [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
  [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

  ## [0.3.0] — 2026-06-15

  First public release.

  ### Changed
  - **Zero-Python shipped surface.** Removed every Python artifact that previously shipped to user
    machines (the bundled `osctl.py` / `state.py` and the scheduling guard hook). Claude Code now
    executes the OS's state procedures natively from the pinned contracts in `shared/references/`.
    Nothing but Markdown ships — only Claude Code and the `agent-data` CLI are required at runtime.
  - Plugin author set to the Aptiq Labs, Inc. legal entity (matching the LICENSE copyright holder).

  ### Added
  - Public-release docs: a first-run walkthrough and an everyday-use phrasebook in the README, an
    honest supported-environments note, this `CHANGELOG`, a `CODE_OF_CONDUCT`, a security policy
    (`.github/SECURITY.md`), and issue/pull-request templates.

  ### Fixed
  - Loose-skill install instructions now include all five skills (the operator-manual skill
    `job-search-agent` was previously omitted).

  ### Notes
  - Tested on Claude Code (CLI) on macOS/Linux. Scheduling uses Claude Code's native `/loop`.
  ```

- [ ] **Step 3: Verify.** `claude plugin validate . --strict` passes; `grep -rn '0\.2\.3' .claude-plugin`
  returns nothing; `python3 scripts/philosophy_guard.py --root .` clean (CHANGELOG is at root, not
  scanned, but run the full guard anyway).

- [ ] **Step 4: Commit.** `git add .claude-plugin/plugin.json CHANGELOG.md && git commit -m "chore(release): 0.3.0"`

---

## Phase 5 — Final green gate

### Task 12: Run the full release gate and a human read `[BLOCKS]`

**Files:** none (verification only)

- [ ] **Step 1: Mechanical gates.** Run and confirm each:

  ```bash
  python3 -m pytest -q                              # 0 failed
  python3 scripts/doc_lint.py --root .             # Doc lint: clean.
  python3 scripts/doc_lint.py --root . --strict-fresh   # clean (no stale pillars)
  python3 scripts/philosophy_guard.py --root .     # Philosophy guard: clean.
  ./scripts/build.sh && git status --porcelain skills   # empty (bundled copies in sync)
  claude plugin validate . --strict                # passes
  ```

- [ ] **Step 2: Targeted greps.**

  ```bash
  grep -rn '"version"' .claude-plugin/plugin.json  # 0.3.0
  grep -rn 'agent-data' .claude-plugin/plugin.json # only org/marketplace refs, not the author name
  grep -rinE 'your-name' --include=*.md --include=*.json . | grep -v '.git/'   # nothing
  ```

- [ ] **Step 3: Files present.** `ls CHANGELOG.md CODE_OF_CONDUCT.md .github/SECURITY.md .github/PULL_REQUEST_TEMPLATE.md .github/ISSUE_TEMPLATE/`

- [ ] **Step 4: Human read.** Render `README.md` on GitHub (or a Markdown preview) and confirm: badges
  render, the first-run walkthrough code block and the everyday-use table display correctly, option C
  lists five skills, and the supported-environments note reads honestly.

- [ ] **Step 5: Flip this plan.** Once the gate is green, move this file to
  `docs/exec-plans/completed/`, set `state: completed` + `completed: 2026-06-15`, update
  `docs/exec-plans/index.md`, and commit `docs(plans): complete the public OSS release-readiness plan`.

---

## Done when

- [ ] `.claude-plugin/plugin.json`: `author.name` = `Aptiq Labs, Inc.`; `version` = `0.3.0`; valid JSON; `claude plugin validate . --strict` passes.
- [ ] `README.md`: option C lists all five skills; supported-environments note present; first-run walkthrough present; everyday-use phrasebook present; license + tested-on badges render; CoC pointer present.
- [ ] New files exist and read correctly: `CHANGELOG.md`, `CODE_OF_CONDUCT.md` (no `[INSERT CONTACT METHOD]` left), `.github/SECURITY.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.md`.
- [ ] Zero-Python plan is `state: completed` in `docs/exec-plans/completed/`; `docs/exec-plans/index.md` reflects it.
- [ ] `python3 -m pytest -q` → 0 failed; `python3 scripts/doc_lint.py --root .` (and `--strict-fresh`) clean; `python3 scripts/philosophy_guard.py --root .` clean; `./scripts/build.sh` is a no-op on `skills/`.
- [ ] `grep -rn '0\.2\.3' .claude-plugin` → nothing; no personal-name leakage in tracked files.
- [ ] README renders correctly on GitHub (human read done).

## Self-Review (author pass, 2026-06-15)

- **Spec coverage** — every accepted item maps to a task: L1→T1; L2→T10+T11; L3→T2; L4→T3;
  L5→verified (no task, see D7); N1→T7; N2→T4; N3→T11; N4→T5; N5→T6; N6→T8; N7→T9. No item unmapped.
- **Placeholder scan** — the only deliberate fill-in is the CoC/security contact (T4 Step 2, T5
  Step 1), flagged because the real address isn't known here; GitHub private reporting is the
  no-invention default. No "TBD"/"handle later" steps.
- **Path/name consistency** — file paths verified against the working tree; skill set verified as the
  five dirs under `skills/`; the placement constraint (root README, not `docs/`) is applied to every
  literal-bearing section (T3, T7, T8) and re-checked by `doc_lint` in those tasks.

## Progress Log

- 2026-06-15 — plan created (this commit). Author self-review done (above). Awaiting execution mode choice.

## Decision Log

- **D1 — Author = Aptiq Labs, Inc.; repo URLs left under the `agent-data` org.** The author/legal
  entity (matching LICENSE) and the hosting org (the marketplace handle) can legitimately differ;
  T1 Step 2 verifies the URL and updates it only if hosting moves. (Owner, 2026-06-15)
- **D2 — 0.3.0, not 1.0.0.** Matches the zero-Python plan's task 7 and signals pre-1.0. The
  live-API acceptance pass is green (owner), clearing the only gate that deferred this. (Owner, 2026-06-15)
- **D3 — Newcomer narrative lives in the root README, not `docs/`.** `doc_lint`'s
  `no-shared-reference-duplication` rule fails any `docs/`-scanned file that quotes digest/error
  literals without linking `shared/references`; the README is not scanned, so it's the correct home.
- **D4 — Keep-all for context-only docs.** `agents-map` + `index-completeness` couple `AGENTS.md` and
  the section indexes to every pillar/sibling, so excluding a doc would mean editing the linter; the
  docs-as-product posture makes keeping them the right public call.
- **D5 — One everyday-use phrasebook, not per-skill how-tos.** Per-skill how-to docs would fight the
  conversational-first thesis in `docs/PRODUCT_SENSE.md`.
- **D6 — SECURITY split.** `.github/SECURITY.md` is the vuln-reporting policy GitHub surfaces;
  `docs/SECURITY.md` stays the posture/explanation doc; the former links the latter — no duplication.
- **D7 — L5 verified by owner.** The `agent-data` CLI (public npm package, `npm install -g agent-data`)
  and the API-key signup are confirmed available, so no README caveat is needed for the external
  dependency. (Owner, 2026-06-15)
