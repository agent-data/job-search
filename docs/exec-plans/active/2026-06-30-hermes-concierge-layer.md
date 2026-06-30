---
title: Hermes concierge layer — bootstrap, concierge flow, and Hermes-specific source layer
state: active
created: 2026-06-30
---

# Hermes concierge layer — bootstrap, concierge flow, and Hermes-specific source layer

> **Superseded** by [Hermes Job Search Assistant](2026-06-30-hermes-job-search-assistant.md) (design:
> [here](../../design-docs/2026-06-30-hermes-job-search-assistant.md)). Closed without execution after the
> [harness review](../../design-docs/hermes-harness-review/overview.md). Kept in `active/` only because the
> review docs link this path; **do not execute it.**

## Goal

Make the Hermes experience feel native and seamless: the Hermes installation section in `README.md` points to a single bootstrap file (`hermes/INSTALL.md`), generic Hermes can use that file to install/register the plugin and verify readiness, and once installed the existing `job-search` skill behaves as a Hermes-specific concierge — asking permission before drafting preferences from prior context, running a first manual calibration batch with lightweight analytics, asking for the user's reaction before tuning, and then proactively offering recurring delivery through Hermes-native setup paths. The installable front door stays canonical (`job-search`), the portable core remains intact for other hosts, and Hermes-only UX logic is source-separated under `hermes/` then bundled into the relevant installable skills.

## Non-goals

- **No second public front door.** Do not introduce a competing everyday user-facing skill name like `hermes-job-search`; the visible front door remains `job-search`.
- **No cross-host behavior change.** The concierge behavior activates only when the active host is Hermes; other hosts keep the existing portable flow.
- **No dashboard or heavy persistent analytics layer.** This remains conversational infrastructure; analytics and explanations are derived mostly on demand from existing state plus optional live re-checks.
- **No duplication of Hermes messaging setup docs.** If the user wants a new destination, `job-search` hands off to Hermes-native setup and resumes; it does not become its own channel-setup manual.
- **No numeric fit scoring or ranking changes.** The qualitative relevance model stays intact.
- **No source-repo runtime dependency after install.** Installed Hermes behavior must not require the repo-local `hermes/` directory to remain present; any needed Hermes-only references are bundled into installable skills.

## Done when

All hold, run from repo root:

- [ ] `python3 scripts/doc_lint.py --root .` → clean
- [ ] `python3 -m pytest -q` → green
- [ ] `python3 scripts/philosophy_guard.py --root .` → green
- [ ] `./scripts/build.sh` then `git status --porcelain skills` → empty (no hand-edited bundles)
- [ ] `python3 scripts/validate_platforms.py --root .` → clean, including any new Hermes-source / bundle assertions
- [ ] The Hermes section in `README.md` no longer inlines setup steps and instead points to `hermes/INSTALL.md`
- [ ] `hermes/INSTALL.md` is sufficient for generic Hermes to bootstrap install/registration, verify `agent-data`, and reach the first invocation path
- [ ] Hermes-only references under `hermes/` are bundled into the intended installable skills and are not required by non-Hermes hosts
- [ ] On Hermes, `job-search` asks permission before drafting preferences from prior context; declining leads directly to the short / comprehensive / import choice
- [ ] On Hermes, open-ended questions in the preference flow are truly open-ended and no broken `clarify` fallback renders duplicate “Other” choices
- [ ] On Hermes, the first manual batch shows relevant jobs plus lightweight analytics (including filtered-out counts/reasons), then asks for the user's reaction before proposing tuning
- [ ] On Hermes, after the user indicates satisfaction, `job-search` proactively offers automation, recommends daily, offers `here` + configured destinations + `set up a new destination`, shows a final informational summary, and then creates the recurring job
- [ ] Explanatory questions like “why didn’t we alert on X?” can use stored artifacts first and then optionally perform a live re-check
- [ ] The new design doc is indexed and any touched docs that describe the Hermes path are reconciled

## How to execute

Per `docs/PLANS.md`: task-by-task, one scoped Conventional-Commit per logical task, appending to the Progress log and Decision log as part of each task's commit. Keep the plan cold-reader friendly: change the Hermes bootstrap docs before tightening the in-skill concierge flow, because the README and `hermes/INSTALL.md` define the intended user story. Prefer red → green where behavior can be captured by tests or evals; where the work is primarily docs/prompt behavior, verify with targeted transcript-level checks and structural assertions rather than inventing brittle end-to-end mocks.

## Tasks

### T1 [BLOCKS] — Create the Hermes bootstrap source layer and move the README Hermes path

**Objective:** Establish `hermes/` as the source-only Hermes guidance area and replace the current README Hermes install section with a pointer to one bootstrap doc.

**Files:**
- Create: `hermes/INSTALL.md`
- Create: `hermes/references/bootstrap-contract.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `ARCHITECTURE.md`
- Modify: `CONTRIBUTING.md` (only if contributor guidance must acknowledge `hermes/` as an authored source area)
- Test/verify: `scripts/doc_lint.py`, manual cross-read against `docs/design-docs/prompt-style-guide.md`

**Step 1: Write the failing doc expectation**

Document the expected new README Hermes section and bootstrap boundary in the new bootstrap contract first, so the repo has a single source of truth before rewriting user docs.

**Step 2: Add `hermes/INSTALL.md`**

Write a complete Hermes bootstrap guide covering:
- install/register path
- how generic Hermes knows the plugin is ready
- agent-data presence/auth verification
- first invocation path
- distinction between bootstrap and post-install concierge mode

The file should be self-contained for the pre-install phase and clearly labeled as Hermes-specific.

**Step 3: Rewrite the README Hermes section**

Replace the inlined Hermes setup steps with a concise pointer to `hermes/INSTALL.md`.

**Step 4: Reconcile architecture/docs framing**

Update `AGENTS.md` / `ARCHITECTURE.md` so `hermes/` is clearly described as a source-only Hermes layer, not an accidental cross-host dependency.

**Step 5: Verify**

Run:
```bash
python3 scripts/doc_lint.py --root .
```
Expected: clean

Cross-read the new docs against `docs/design-docs/prompt-style-guide.md` and confirm:
- boundaries first
- no duplicated install truth
- purpose before procedure

**Step 6: Commit**

```bash
git add README.md AGENTS.md ARCHITECTURE.md hermes/INSTALL.md hermes/references/bootstrap-contract.md CONTRIBUTING.md
git commit -m "docs(hermes): add bootstrap install guide and README handoff"
```

### T2 [BLOCKS] — Teach the build/validation layer about Hermes source references

**Objective:** Bundle Hermes-only references into the installable skills that need them, without making other hosts depend on `hermes/`.

**Files:**
- Modify: `scripts/build.sh`
- Modify: `scripts/validate_platforms.py`
- Modify: any existing tests covering build/validation behavior
- Create/modify: tests/fixtures only if needed

**Step 1: Write the failing validation expectation**

Add a targeted validation rule that will fail if Hermes-only bundled references drift from the `hermes/` source or appear in the wrong installable skills.

**Step 2: Extend `build.sh` minimally**

Bundle Hermes-only references from `hermes/references/` into the intended installable skills — likely `skills/job-search/` and `skills/job-search-agent/`, and `skills/job-search-run/` only if there is a concrete need.

**Step 3: Add no-bleed validation**

Extend `validate_platforms.py` so it asserts:
- the expected Hermes bundles exist where intended
- bundled copies match source byte-for-byte
- no unintended skill carries Hermes-only bundles

**Step 4: Verify**

Run:
```bash
./scripts/build.sh
python3 scripts/validate_platforms.py --root .
```
Expected: build clean; validation clean

**Step 5: Commit**

```bash
git add scripts/build.sh scripts/validate_platforms.py tests
git commit -m "feat(hermes): bundle and validate Hermes-only references"
```

### T3 [BLOCKS] — Rework `job-search` into a Hermes-only concierge flow

**Objective:** Keep `job-search` as the canonical front door but make its behavior host-gated so Hermes gets the concierge flow and other hosts keep the portable flow.

**Files:**
- Modify: `skills/job-search/SKILL.md`
- Modify: Hermes-bundled references under `skills/job-search/references/hermes/` via source changes in `hermes/references/`
- Modify: any onboarding/home playbooks the skill uses if the Hermes path needs explicit branch guidance
- Test/eval: targeted skill evals or transcript-facing tests if present

**Step 1: Write the failing behavior expectations**

Capture the Hermes-only concierge expectations in the skill-facing docs or evals first:
- permission before memory/session drafting
- decline path → short / comprehensive / import
- first manual batch includes lightweight analytics
- ask for the user's reaction before tuning
- proactive automation offer after satisfaction

**Step 2: Host-gate the front door behavior**

Edit `skills/job-search/SKILL.md` so Hermes is explicitly instructed to follow the concierge flow while other hosts keep the existing portable route. Keep the public trigger ownership anchored on `job-search`; do not introduce a second public front door.

**Step 3: Wire in permissioned draft-from-context behavior**

Make the Hermes path ask permission before using memory/session history. On approval, synthesize and show a draft; on decline, go directly to short / comprehensive / import.

**Step 4: Define the first manual calibration batch behavior**

Require Hermes to present:
- relevant jobs only
- concise reasoning on presented jobs
- lightweight analytics
- filtered-out summary with counts/reasons and optional deeper inspection
- a follow-up question asking for the user's reaction before proposing tuning

**Step 5: Define the automation handoff behavior**

After satisfaction, require Hermes to:
- proactively offer automation
- recommend daily from a small cadence menu
- offer `here`, configured destinations, and `set up a new destination`
- if the user chooses a new destination, hand off to Hermes-native setup and resume
- show an informational summary, then create the job immediately

**Step 6: Verify**

Use transcript-level/manual verification on Hermes and any available evals to confirm the branching and wording work.

**Step 7: Commit**

```bash
git add skills/job-search/SKILL.md hermes/references skills/job-search/references
 git commit -m "feat(job-search): add Hermes concierge flow"
```

### T4 [BLOCKS] — Fix the Hermes preference/onboarding interaction bug and tighten open-ended prompting

**Objective:** Eliminate the broken clarify/open-ended behavior seen in dogfooding and ensure Hermes-only open-ended asks stay truly open-ended.

**Files:**
- Modify: `skills/job-preference-interview/SKILL.md`
- Modify: any Hermes-bundled onboarding references the preference flow depends on
- Modify: any relevant evals/tests

**Step 1: Write the failing expectation**

Add or update an eval/transcript expectation that explicitly rejects duplicated “Other” choice rendering for open-ended prompts in the Hermes flow.

**Step 2: Separate open-ended from closed-choice guidance**

Tighten the prompt instructions so Hermes uses `clarify` only for true bounded choices and uses plain conversational asks for open-ended preference questions.

**Step 3: Verify**

Exercise the first-run path manually on Hermes until the first open-ended preference question and confirm it is rendered as an actual free-text question, not as a malformed choice picker.

**Step 4: Commit**

```bash
git add skills/job-preference-interview/SKILL.md hermes/references skills/job-preference-interview/evals
 git commit -m "fix(hermes): keep open-ended preference questions truly open"
```

### T5 [TUNE] — Rework `job-search-agent` into the Hermes admin/power-user surface

**Objective:** Make `job-search-agent` the explicit Hermes admin and maintainer surface without changing its cross-host role.

**Files:**
- Modify: `skills/job-search-agent/SKILL.md`
- Modify: Hermes-bundled admin references under `hermes/references/`

**Step 1: Clarify admin ownership**

Make the Hermes path explicitly cover:
- installation verification
- runtime/path diagnostics
- workspace/config/schedule inspection
- explaining Hermes-specific concierge behavior
- troubleshooting why a run or delivery did not happen

**Step 2: Verify trigger boundaries**

Ensure `job-search-agent` does not reclaim everyday first-run or “help me find a job” ownership from `job-search`.

**Step 3: Commit**

```bash
git add skills/job-search-agent/SKILL.md hermes/references skills/job-search-agent/references
 git commit -m "feat(job-search-agent): define Hermes admin and power-user surface"
```

### T6 [TUNE] — Make explanations and analytics legible without a new heavy state layer

**Objective:** Document and, where needed, lightly adjust the run/explanation path so Hermes can answer questions like “why didn’t we alert on X?” using stored artifacts first and optional live re-checks second.

**Files:**
- Modify: `skills/job-search-run/SKILL.md`
- Modify: `skills/evaluate-job-fit/SKILL.md` only if needed
- Modify: Hermes-only references describing explainability behavior
- Modify: design/docs if explanation semantics are described there

**Step 1: Encode explainability order**

Require the Hermes path to use:
1. stored local artifacts first
2. optional live re-checks if the local state is insufficient

**Step 2: Keep persistence lean**

Avoid adding a large analytics persistence layer unless a concrete explanation gap requires it.

**Step 3: Verify**

Review the resulting instructions against the stated user asks:
- any new jobs today?
- how many jobs were filtered out?
- why didn’t we alert on X?

**Step 4: Commit**

```bash
git add skills/job-search-run/SKILL.md skills/evaluate-job-fit/SKILL.md hermes/references docs
 git commit -m "docs(hermes): define lightweight analytics and explanation flow"
```

### T7 [BLOCKS] — Reconcile tests/docs and run the full verification gate

**Objective:** Leave the branch green and the knowledge base truthful.

**Files:**
- Modify: `TESTING.md` if the Hermes bootstrap/concierge path needs new verification steps
- Modify: `docs/design-docs/index.md` if additional indexing is needed
- Modify: other touched docs as required

**Step 1: Update verification docs if needed**

Make sure Hermes-specific dogfood/verification instructions are represented accurately in `TESTING.md` or the most appropriate doc.

**Step 2: Run the full gate**

Run:
```bash
python3 scripts/doc_lint.py --root .
python3 -m pytest -q
python3 scripts/philosophy_guard.py --root .
./scripts/build.sh
python3 scripts/validate_platforms.py --root .
```
Expected: all clean

**Step 3: Manual Hermes proof**

On a real Hermes install, verify:
- bootstrap docs are sufficient
- `job-search` asks permission before drafting from prior context
- decline path goes to short / comprehensive / import
- first manual batch includes lightweight analytics
- Hermes asks for the user's reaction before tuning
- Hermes proactively offers automation and creates the recurring job after the informational summary

**Step 4: Commit**

```bash
git add TESTING.md docs
git commit -m "test(hermes): verify concierge bootstrap and flow"
```

## Progress log

- 2026-06-30 — plan created after Hermes dogfooding identified three blocking issues: install path too manual, broken open-ended preference prompt rendering, and concierge behavior still too close to the portable core. Design anchor: `docs/design-docs/2026-06-30-hermes-job-search-concierge.md`.

## Decision log

- The visible front door remains `job-search` — introducing a second everyday user-facing skill name would create routing ambiguity and product confusion.
- Variant A was chosen — installable skills stay in `skills/`, while Hermes-only source material lives under `hermes/` and is bundled into the intended installable skills.
- The Hermes README path is fully replaced with a pointer to `hermes/INSTALL.md` — bootstrap is a docs concern before install, not a second public runtime surface.
- The concierge behavior is Hermes-only — other hosts should not inherit it just because the source layer exists.
- Memory/session-assisted drafting is permissioned and moderate — the workspace brief is canonical working state; global memory informs a draft but does not silently become truth.