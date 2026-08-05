# Skill Locality Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every path an agent has to compute, by giving each file an address the harness
supplies instead of one the model infers.

**Architecture:** Two moves. First, fold every single-owner template and script into the skill
directory that owns it, so the skill addresses them under its own base directory. Second, promote
the two shared reference files to skills, so consumers reach them by name instead of by relative
path. Together these retire the `<plugin-root>` token and the `../../` reference form — the two
pointer shapes both models were measured mis-resolving.

**Tech stack:** Markdown skills, POSIX shell mechanics scripts, the `evals/run_eval.py` harness,
pytest for structural gates.

## Why (measured, not assumed)

Concern C10 of the 0.8.0 eval matrix measured every reference read across the live runs:

| run | missed | of | what it tried |
|---|---|---|---|
| quickstart sonnet | 1 | 11 | `skills/shared/references/runbook.md` — one `..` too few for `../../shared/references/runbook.md` |
| quickstart haiku | 2 | 6 | `skills/job-search/templates/…` — `<plugin-root>` resolved as the skill's own directory |

Both recovered, so nothing failed outright. The cost is a wasted tool call per miss plus the
recovery flailing: in the sonnet quickstart the first-read miss cost roughly 22 seconds of `pwd`,
`ls`, `Glob`, `ls` before the file was found, and the user watched raw tool output during it.

The token's only definition lives at `shared/references/runbook.md:4` — behind the pointer that
needs the token. A model that guesses wrong cannot self-correct from the text.

Ownership, measured with `git grep -l <file> -- skills/*/SKILL.md shared/references/`:

| file | referencing skills | disposition |
|---|---|---|
| `templates/config.example.yaml` | job-search | fold into job-search |
| `templates/workspace.gitignore` | job-search | fold into job-search |
| `templates/preferences.example.md` | job-preference-interview | fold into job-preference-interview |
| `templates/run-record.example.json` | job-search-run | fold into job-search-run |
| `templates/jobs-event.example.json` | job-search-run | fold into job-search-run |
| `shared/scripts/mechanics/schedule-line.sh` | job-search | fold into job-search |
| `shared/scripts/mechanics/event-log-append.sh` | job-search-run | fold into job-search-run |
| `shared/scripts/mechanics/dedup.sh` | job-search-run | fold into job-search-run |
| `shared/scripts/mechanics/workspace-discovery.sh` | none directly (runbook.md only) | move with the runbook skill |
| `shared/scripts/mechanics/validate-workspace.sh` | job-search-run, job-search-agent | single home in the runbook skill |
| `shared/references/runbook.md` | 4 skills | promote to a skill |
| `shared/references/agent-data.md` | 4 skills | promote to a skill |

No template is shared by two skills, so folding duplicates nothing.

## Global Constraints

- The agent-facing corpus stays ≤10,000 words: `wc -w skills/*/SKILL.md shared/references/*.md`
  (8,977 before this plan). Promotion moves words between directories; it must not add them.
- No file is duplicated. If two skills need the same file, it keeps exactly one home. Copying a
  shared file is the drift failure this repo spent twelve tasks removing.
- Live API only in evals — no mocks, no fixtures, no shims.
- Test-driven here means **evals**, not substring assertions. Structural pytest gates (a pointer
  resolves, a file exists) are fine and expected; grading agent behavior by string match is not.
- Work on `main`. Commit. Never push.
- All 9 hosts must still resolve every referenced path: Claude, codex, cursor, opencode, gemini,
  copilot, droid, pi, and Hermes.
- Any task that writes or edits skill text reads the `superpowers:writing-skills` skill, the
  `skill-creator:skill-creator` skill, and `CLAUDE.md` first, plus any further sources its dispatch
  names, and follows them all. Where they conflict with this plan, this plan governs; Task 2 names
  the two conflicts it resolves.
- A user-triggered skill's description states triggering conditions, never a workflow summary — an
  agent that can read the workflow in the description will follow it instead of reading the skill.
  The two reference skills Task 2 creates are the exception it defines: they are consulted by
  sibling skills, so their descriptions state what they hold and claim no user phrases.

---

### Task 1: Fold the single-owner templates and scripts into their skills

**Files:**
- Move: `templates/config.example.yaml`, `templates/workspace.gitignore` →
  `skills/job-search/templates/`
- Move: `templates/preferences.example.md` → `skills/job-preference-interview/templates/`
- Move: `templates/run-record.example.json`, `templates/jobs-event.example.json` →
  `skills/job-search-run/templates/`
- Move: `shared/scripts/mechanics/schedule-line.sh` → `skills/job-search/scripts/`
- Move: `shared/scripts/mechanics/event-log-append.sh`, `shared/scripts/mechanics/dedup.sh` →
  `skills/job-search-run/scripts/`
- Modify: `skills/job-search/SKILL.md`, `skills/job-search-run/SKILL.md`,
  `skills/job-preference-interview/SKILL.md`, `shared/references/runbook.md` (its
  `run-record.example.json` and `workspace.gitignore` pointers)
- Modify: `tests/test_reference_resolution.py`, `tests/test_mechanics_scripts.py`,
  `scripts/doc_lint.py`, `scripts/check_release_integrity.py` (any hardcoded `templates/` or
  `shared/scripts/mechanics/` path)
- Test: `tests/test_reference_resolution.py`

**Interfaces:**
- Produces: the pointer form every later task uses for a co-located file. Name it explicitly in
  the report — Tasks 2 and 3 must use the same form.

**The pointer form is a co-located path, decided (spec owner, 2026-07-31).** A file inside the
skill that uses it gets an address that needs no computation: on Claude Code the harness states the
skill's own directory, and on a host that includes SKILL.md by path — `GEMINI.md:9` uses
`@skills/job-search/SKILL.md` — the same file sits at a stable path from the repo root. Both
`<plugin-root>` and `../../` require the model to compute, which is what C10 measured it getting
wrong. Do not introduce a new token.

Use `git mv` so history follows the files.

- [ ] **Step 1: Write the failing test.** Extend `tests/test_reference_resolution.py` with a test
  that every path a SKILL.md names resolves to a file that exists, and that no SKILL.md contains
  the substring `<plugin-root>` or `../../`. Run it; it must fail on the current tree, naming the
  pointers that still exist.
- [ ] **Step 2:** `git mv` each file per the list above. Create the destination directories.
- [ ] **Step 3:** Rewrite every pointer in the four modified markdown files to the co-located form
  Task 1 established. `shared/references/runbook.md` still names two of these templates — it must
  point at their new homes even though it is itself moving in Task 3.
- [ ] **Step 4:** Update the gate scripts and tests that hardcode the old locations. Find them with
  `git grep -n "templates/\|shared/scripts/mechanics/" -- tests/ scripts/ .github/`.
- [ ] **Step 5:** Run `python3 -m pytest tests/ -q`, `python3 scripts/doc_lint.py`,
  `python3 scripts/philosophy_guard.py`, and
  `python3 scripts/check_release_integrity.py --root . --check-version-sync`. All green.
- [ ] **Step 6:** Confirm `templates/` and `shared/scripts/mechanics/` are empty except
  `validate-workspace.sh` and `workspace-discovery.sh`, which Task 3 moves. Remove any directory
  left empty.
- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor(skills): co-locate single-owner templates and scripts"
```

---

### Task 2: Promote the two shared references to skills

**Files:**
- Create: `skills/job-search-runbook/SKILL.md` (from `shared/references/runbook.md`)
- Create: `skills/agent-data-reference/SKILL.md` (from `shared/references/agent-data.md`)
- Move: `shared/scripts/mechanics/validate-workspace.sh`,
  `shared/scripts/mechanics/workspace-discovery.sh` → `skills/job-search-runbook/scripts/`
- Delete: `shared/references/`, `shared/scripts/` once empty
- Modify: all five existing `skills/*/SKILL.md` (replace `../../shared/references/…` pointers with
  a skill invocation), `AGENTS.md`, `ARCHITECTURE.md`, `README.md`, `TESTING.md`, `CONTRIBUTING.md`,
  `GEMINI.md`, and every host manifest that names `shared/`
- Test: `tests/test_reference_resolution.py`, `tests/test_skill_frontmatter.py` (create if absent)

**Interfaces:**
- Consumes: Task 1's co-located pointer form.
- Produces: two new skill names. Use exactly `job-search-runbook` and `agent-data-reference` in
  every consumer — Task 3's triggering evals grade these names.

Names are prefixed so they read as this plugin's internals, not as user entry points.

**Style sources, and what governs when they disagree.** A reference file becoming a skill inherits
skill anatomy, so read all of these before writing either SKILL.md: the `superpowers:writing-skills`
skill (SKILL.md structure, description discipline, token efficiency, naming), the
`skill-creator:skill-creator` skill (skill anatomy, progressive disclosure, description authoring),
the repo's own writing doctrine in `CLAUDE.md`, and any further sources your dispatch names.
Where any of those conflicts with this plan, **this plan governs**, and the two known conflicts are
resolved below. Everything they agree on binds: write concretely and name the thing rather than its
abstraction, never use an idiom or personification to state a plain fact, and never state a
measurable fact without running the command that settles it.

**Conflict 1 — description pushiness. This plan overrides skill-creator.** skill-creator says to
make descriptions "pushy" to combat undertriggering, because most skills fail by not firing. These
two skills have the opposite failure mode: they are consulted by sibling skills, never requested by
users, and every user-facing phrase they claim competes with the front door for routing. The 0.8.0
matrix measured haiku routing "Set up my job search" to `job-preference-interview` in 5 of 9 reps
with only five skills present. Write these two descriptions to be found by a sibling skill that
already knows it needs them, and by nothing else. No user utterances, no "use when the user…".

**Conflict 2 — description content. This plan overrides writing-skills.** writing-skills says a
description states only triggering conditions and never what the skill does. That rule assumes a
user-triggered skill. For a reference consulted by a sibling, what it holds *is* the triggering
condition — a sibling decides whether to spend a read on the file by knowing what is in it. State
the contents plainly and briefly.

**Description length:** keep each under 200 characters. writing-skills allows up to 1024 characters
of frontmatter and suggests under 500 for descriptions, but a prior compatibility pass found
claude.ai truncating at roughly 200 (research only, never live-tested — verify rather than trust it,
and treat 200 as the budget either way). These two are read by sibling skills, so brevity costs
nothing.

**Scope discipline:** the body content moves unchanged. If skill anatomy seems to require reshaping
the guidance itself — reordering sections, rewriting a rule, adding a worked example — that is a
wording change, not a relocation, and it needs the micro-test evidence any wording change needs
(shipped arm, variant, no-guidance control, 5+ reps per model). Do not reshape guidance inside a
relocation task. Report the tension instead and let the controller scope it.

- [ ] **Step 1: Write the failing test.** A test asserting `shared/` does not exist, that both new
  SKILL.md files carry valid frontmatter with `name` and `description`, and that no SKILL.md
  contains `../../`. Run it; it fails.
- [ ] **Step 2:** `git mv` the two reference files into their new skill directories as `SKILL.md`
  and add frontmatter per the description rule above. Body content moves unchanged — this task
  relocates and re-addresses; it does not rewrite the guidance.
- [ ] **Step 3:** `git mv` the two remaining scripts into `skills/job-search-runbook/scripts/` and
  point the runbook skill at them in its own co-located form. `validate-workspace.sh` now has one
  home; `job-search-run` and `job-search-agent` reach it through the runbook skill rather than by
  path.
- [ ] **Step 4:** In each of the five existing skills, replace the `../../shared/references/…`
  pointer with an instruction to invoke the named skill. Keep the one-line summary of what the
  reference holds — that summary is how a skill decides whether it needs the reference at all.
- [ ] **Step 5:** Update the repo docs and every host manifest or entry file that names `shared/`.
  Find them with `git grep -n "shared/references\|shared/scripts"` (use `git grep`, not `grep -r` —
  nested `.gitignore` files silently skip directories on this machine).
- [ ] **Step 6:** Re-measure the corpus. `wc -w skills/*/SKILL.md shared/references/*.md` no longer
  applies once `shared/` is gone — update the command in `AGENTS.md`, `CONTRIBUTING.md`, and
  `CHANGELOG.md` to `wc -w skills/*/SKILL.md` and confirm the total is ≤10,000 and has not grown
  beyond the 8,977 starting point by more than the frontmatter added here.
- [ ] **Step 7:** All four gates green, plus the 8-host sweep: for each adapter, extract every path
  it references and confirm the file exists. Zero dangling references.
- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "refactor(skills): promote the shared references to named skills"
```

---

### Task 3: Prove it with evals, on both models

**Files:**
- Modify: `evals/behaviors.md` (add B15: every referenced path resolves on the first attempt)
- Create: `evals/cases/triggering.yaml` (routing discrimination across the now-seven skills)
- Modify: `evals/baseline/2026-07-30-red-baseline.md` (append the locality comparison, aggregates
  only)
- Create: the private eval report for this plan (full outputs; written to the location your
  dispatch names, never to a tracked path)

**Interfaces:**
- Consumes: the skill names from Task 2.

Two questions this task answers, and it is not done until both have numbers: did the misses go
away, and did adding two skills make routing worse.

- [ ] **Step 1: Add B15 to `evals/behaviors.md`** — "every file the agent reads resolves on the
  first attempt; zero recovery searches", graded by an artifact check that replays each run's
  transcript and confirms every Read/Bash path resolved to a file that exists. The C10 method is the
  model: check each attempted path against the tree, and count misses.
- [ ] **Step 2: Write the triggering case.** `evals/cases/triggering.yaml` drives the front door's
  own trigger phrases — "set up job search", "keep this running daily", "check my job search",
  "run a search now", "why did my run fail" — and grades which skill actually loads. This is the
  regression gate for the routing risk the promotion creates. Run it on both models, 9 reps each,
  matching the rep count that produced the 0.8.0 C12 measurement so the two are comparable.
- [ ] **Step 3: Baseline the routing BEFORE the promotion lands.** Check out the pre-Task-2 commit,
  run the triggering case, record per-phrase routing rates. Without this, a post-promotion number
  has nothing to compare against and the risk cannot be judged. Record in the private report.
- [ ] **Step 4: Run the matrix** — `quickstart` and `headless-run` on sonnet and haiku, plus the
  triggering case on both. Grade B15 and B1–B12. Compare read-path lines and time-to-first-result
  against the 0.8.0 GREEN block; the pointer misses should be zero and the recovery time gone.
- [ ] **Step 5: Judge the routing result.** If any front-door phrase routes worse than the
  pre-promotion baseline, the descriptions are the fix, not the structure — tighten them and re-run
  Step 4. If tightening cannot recover the baseline rate, report BLOCKED to the controller: the
  promotion half of this plan trades a measured path defect for a measured routing defect, and that
  is a spec-owner decision, not an implementer's.
- [ ] **Step 6: Append the aggregate comparison** to `evals/baseline/2026-07-30-red-baseline.md` —
  pointer misses before and after, read-path lines, time-to-first-result, and the per-phrase
  routing rates before and after. 
- [ ] **Step 7: Commit**

```bash
git add evals/ && git commit -m "test(evals): locality restructure proven on both models"
```

---

### Task 4: Docs, version, and the host sweep

**Files:**
- Modify: `ARCHITECTURE.md`, `AGENTS.md`, `README.md`, `TESTING.md`, `CONTRIBUTING.md`,
  `CHANGELOG.md` (0.9.0 entry), all 7 version manifests
- Verify: all 8 adapters

- [ ] **Step 1:** Update the five repo docs to describe seven skills and no `shared/` directory.
  Every count you state must be measured, with the command cited next to it.
- [ ] **Step 2:** CHANGELOG 0.9.0 entry, keep-a-changelog style. Say plainly what changed for a
  user upgrading: nothing in their workspace, and the skills they can invoke by name now include
  two references. Name any behavior that changed.
- [ ] **Step 3:** Bump all 7 manifests to 0.9.0; run
  `python3 scripts/check_release_integrity.py --root . --check-version-sync`.
- [ ] **Step 4: Harness sweep** — for each of the 8 hosts, extract every path its adapter and entry
  file reference and confirm each exists. Zero dangling references is the gate. Report per host.
- [ ] **Step 5:** All four gates green.
- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore(release): 0.9.0 — skill locality restructure"
```

---

## Open decisions carried to the spec owner

These are not implementer choices. Each is recorded here so the final review can route them.

1. **Whether the reference promotion ships at all.** Task 3 Step 5 defines the abort condition: if
   routing degrades against its own pre-promotion baseline and descriptions cannot recover it, the
   folding half (Task 1) still stands on its own and the promotion half reverts. Task 1 and Task 2
   are separate commits for exactly this reason.
2. **The haiku volume limit** (0.8.0 concern C1): haiku judges a fraction of what it finds and
   still closes healthy. Scope haiku to small-pass paths, or give a run a chunking contract. Not
   addressed here.
3. **Whether the scheduled job should install before the canary can verify it** (0.8.0 finding I4).
   The 0.8.0 fix makes the removal branch cover a canary that cannot run; not installing until the
   canary can run is the larger design change.
