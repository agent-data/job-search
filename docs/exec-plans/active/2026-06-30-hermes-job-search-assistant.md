---
title: Hermes Job Search Assistant — Seamless Install + Adapter-Native Onboarding
state: active
created: 2026-06-30
---
# Hermes Job Search Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax
> for tracking.

**Goal:** Let a Hermes user say *"install `agent-data/job-search` and help me find a job"* and have it work
through the **existing** end-to-end onboarding — by adding a seamless install path, one new Hermes
capability (permissioned prior-session preference drafting), a disk-handoff for parallel detail reads, and
the adapter corrections the harness review surfaced. No runtime host-gating; no new skill.

**Architecture:** Adapter-first. The five skills stay harness-neutral and defer Hermes mechanics to
[`shared/references/platform/hermes.md`](../../../shared/references/platform/hermes.md); each host reads only
its own adapter, so Hermes behavior is isolated **without host detection**. Install differentiation lives in
docs (`hermes/INSTALL.md` + a one-line README pointer). Design:
[Hermes Job Search Assistant](../../design-docs/2026-06-30-hermes-job-search-assistant.md); grounding:
[harness review](../../design-docs/hermes-harness-review/overview.md).

**Tech Stack:** Markdown skill/reference prose + stdlib-only Python tooling (`scripts/build.sh`,
`scripts/doc_lint.py`, `scripts/validate_platforms.py`, `scripts/philosophy_guard.py`, `pytest`).

## Global Constraints

Copied verbatim from repo rules; every task's requirements implicitly include these.

- **Single source of truth.** Edit `shared/references/` (and `runtime/`), then run `./scripts/build.sh`.
  **Never hand-edit `skills/*/references/` or `skills/*/scripts/hermes_job_search/`** — build.sh regenerates
  them and a hand edit is silently lost. `skills/*/SKILL.md` and `skills/job-search/references/onboarding.md`
  + `home.md` are **per-skill source** (not synced) and are edited directly.
- **`hermes.md` must retain these literal tokens** (the `hermes-runtime-invocation` validator check):
  `delegate_task`, `hermes-cron`, `scripts/hermes_job_search/cli.py`. Never delete them.
- **Adapters keep all 12 canonical `## ` sections** (the `adapter-sections` check): Identity, Tool map, Run
  recipe, Scheduling, Headless invocation, Closed-choice question, Concurrent detail reads, Model tiers,
  Whole-file write, Block-alert channel, agent-data setup, Packaging & install. Extra sections are allowed;
  a missing one fails.
- **Adapter cross-references** of the form `adapter → <Section>` / `defers to → <Section>` must name a
  canonical section present in **every** adapter (the `adapter-cross-refs` check). The new prior-session
  capability is **not** canonical, so neutral prose refers to it **without** the `→` arrow form.
- **No numeric relevance** anywhere (the `philosophy_guard` check): no fit score, 0–100 scale, per-category
  points, or weights.
- **Stdlib-only Python.** No new dependencies.
- **Commits:** one scoped Conventional Commit per task; append the Progress log + Decision log in the same
  commit. Do not commit until the task's verification passes.

## Done when

All hold, run from repo root:

- [ ] `python3 scripts/doc_lint.py --root .` → clean
- [ ] `python3 -m pytest -q` → green
- [ ] `python3 scripts/philosophy_guard.py --root .` → green
- [ ] `./scripts/build.sh` then `git status --porcelain skills` → empty (no hand-edited bundles)
- [ ] `python3 scripts/validate_platforms.py --root .` → clean, including the new `hermes-prior-session` check
- [ ] The README Hermes section is a one-line pointer to `hermes/INSTALL.md`; `hermes/INSTALL.md` is
  sufficient for generic Hermes to install/register/load the plugin, verify `agent-data`, and reach `job-search`
- [ ] `hermes.md` documents prior-session recall (session_search, permission, draft-to-brief-never-`USER.md`),
  the detail-read disk-handoff, and the corrected Identity / `${HERMES_SKILL_DIR}` / delivery / install lines;
  the delegation background PIN is retained
- [ ] `job-preference-interview` offers a permissioned prior-session draft where the adapter documents it,
  declining (or absence) goes straight to the depth choice, and open-ended asks render as free text
- [ ] `job-search-run` collects detail-read verdicts from disk on completion (not inline-only)
- [ ] The superseded design and exec plan are marked and indexed; the new design + plan are indexed

## How to execute

Per [`docs/PLANS.md`](../../PLANS.md): task-by-task, one scoped Conventional-Commit per logical task,
appending to the Progress log and Decision log as part of each task's commit. The work is mostly
prompt/reference prose; verify with the structural gates above and targeted transcript-level reads rather
than brittle end-to-end mocks. Where a task changes a validator, write the failing check first, watch it
fail, then make it pass (red → green).

---

## Task 1: Hermes bootstrap — `hermes/INSTALL.md` + README pointer

**Files:**
- Create: `hermes/INSTALL.md`
- Modify: `README.md` (Hermes section → pointer)
- Modify: `AGENTS.md`, `ARCHITECTURE.md` (note `hermes/` as a source-only, pre-install bootstrap area)

**Interfaces:**
- Produces: the `hermes/INSTALL.md` path the README points to and the post-install entrypoint (`job-search`).

- [ ] **Step 1: Write `hermes/INSTALL.md`.** Create the file with this content:

```markdown
# Install job-search on Hermes

Hermes-specific bootstrap. This is a pre-install document — once installed, you never need it again; drive
everything from the `job-search` skill. (Other hosts: ignore this file and follow your own install path.)

## 1. Install and load the plugin
- Add the source and install the skills:
  - `hermes skills tap add agent-data/job-search`
  - `hermes skills install job-search`   # tap add registers the source; install loads the skills [PIN: confirm on a live install]
  - Alternatives: point `skills.external_dirs` in `~/.hermes/config.yaml` at the repo's `skills/` dir, or
    copy the skill directories into `~/.hermes/skills/<category>/<skill>/`.
- If installing from this repo's source tree, first run `./scripts/build.sh` so each skill carries its
  synced references and the bundled state-ops runtime.

## 2. Verify the skills are visible
- `hermes skills list` should show `job-search`, `job-search-run`, `job-preference-interview`,
  `evaluate-job-fit`, and `job-search-agent` (each is also a slash command, e.g. `/job-search-run`).

## 3. Set up agent-data (the only step that needs you)
- `agent-data init --hermes --api-key <KEY> --yes` then `agent-data whoami` → expect `api_key_set: true`.
- Get a key by creating an agent-data account first; everything else installs without your input.

## 4. First run
- Run the `job-search` skill (or `/job-search`). On first run it onboards end-to-end: a quick prerequisite
  check, a private workspace, your preferences (it can draft a starting point from your prior sessions, with
  your permission), your first live search shown as real matches, and a recurring schedule delivered to a
  channel you choose.
```

- [ ] **Step 2: Rewrite the README Hermes section** to a concise pointer (no inlined steps). Replace the
  section body with a `### Hermes` heading and one sentence that is a normal Markdown link from `README.md`
  to the repo-root `hermes/INSTALL.md` (link text e.g. "read hermes/INSTALL.md"), noting it covers
  install/registration, `agent-data` setup, and the first run, and closing with "after install, just use the
  `job-search` skill." (Written as prose here so this plan does not itself carry a plan-relative broken link.)

- [ ] **Step 3: Note `hermes/` in `AGENTS.md` and `ARCHITECTURE.md`** as a source-only, pre-install
  bootstrap area (one line each), so it is not mistaken for a cross-host runtime dependency. Example line:
  `` `hermes/` — Hermes-only **pre-install** bootstrap docs (e.g. `INSTALL.md`); not shipped into skills, not read by other hosts. ``

- [ ] **Step 4: Verify.**

Run: `python3 scripts/doc_lint.py --root .`
Expected: `Doc lint: clean.` (README is not KB-scanned; AGENTS.md/ARCHITECTURE.md are — confirm no broken links.)

- [ ] **Step 5: Commit.**

```bash
git add hermes/INSTALL.md README.md AGENTS.md ARCHITECTURE.md docs/exec-plans/active/2026-06-30-hermes-job-search-assistant.md
git commit -m "docs(hermes): add INSTALL.md bootstrap and README pointer"
```

---

## Task 2: Hermes adapter pass — prior-session recall, detail-read disk-handoff, and corrections

**Files:**
- Modify: `scripts/validate_platforms.py` (add the `hermes-prior-session` check)
- Modify: `tests/test_validate_platforms.py` (cover the new check)
- Modify: `shared/references/platform/hermes.md` (new section + reworks + corrections)
- Modify: `shared/references/parallelism.md` (neutral disk-handoff note)
- Run: `./scripts/build.sh`

**Interfaces:**
- Produces: a `## Prior-session recall` section in `hermes.md` (mechanism `session_search`; permission gate;
  draft-to-`preferences.md`-never-`USER.md`); a disk-handoff result-collection contract in `hermes.md` →
  `Concurrent detail reads`; the corrected Identity / `${HERMES_SKILL_DIR}` / delivery / install lines.
- Consumes: nothing from other tasks.

- [ ] **Step 1: Add the failing validator check.** In `scripts/validate_platforms.py`, add this function
  near `scan_hermes_runtime_invocation`:

```python
def scan_hermes_prior_session(root):
    """Once the Hermes adapter exists, it must document the prior-session recall capability the preference
    interview's draft-from-prior-context offer depends on: the session_search mechanism, the permission
    gate, and that drafts go to the workspace brief, never USER.md. No-op until hermes.md is authored."""
    hits = []
    rel = os.path.join(PLATFORM_DIR, "hermes.md")
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        return hits
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if "## Prior-session recall" not in text:
        hits.append(f"{rel}: hermes-prior-session: missing the '## Prior-session recall' section")
        return hits
    for needle, message in (
        ("session_search", "missing the `session_search` mechanism marker"),
        ("USER.md", "must state the draft never writes USER.md (durable-profile guard)"),
    ):
        if needle not in text:
            hits.append(f"{rel}: hermes-prior-session: {message}")
    return hits
```

  Register it in `CHECKS`:

```python
    "hermes-prior-session": scan_hermes_prior_session,
```

- [ ] **Step 2: Run the check — verify it fails.**

Run: `python3 scripts/validate_platforms.py --root . --only hermes-prior-session`
Expected: FAIL — `hermes.md: hermes-prior-session: missing the '## Prior-session recall' section`

- [ ] **Step 3: Add the `## Prior-session recall` section to `hermes.md`** (place it after `## Closed-choice question`):

```markdown
## Prior-session recall

Hermes can search the user's **prior sessions** with `session_search` (an FTS5 index over past
conversations). This is the capability behind the preference interview's *draft-from-prior-context* offer:
with permission, search prior sessions for what the user has said about jobs/work and synthesize a **draft**
Job Preferences Brief.

- **Ask first.** Never read prior sessions to draft without explicit permission; offer it, state the
  benefit, and give a clean decline path.
- **Sessions, not memory.** Hermes's `MEMORY.md`/`USER.md` is already auto-injected into context as a frozen
  snapshot at session start — you do not "use memory" on request. This offer is specifically about searching
  *prior sessions* via `session_search`.
- **Draft, not truth.** Write the synthesized result **only** to the workspace brief
  (`<workspace>/preferences.md`) and present it as an editable draft. **Never** write `USER.md` and never
  silently promote an inferred preference to durable user-profile truth — the workspace brief is canonical.
- **Interactive only.** A scheduled/headless run is a fresh session with no prior-session access and cannot
  ask, so this offer never fires there.
```

- [ ] **Step 4: Rework `## Concurrent detail reads` in `hermes.md`** to add the disk-handoff. Keep the
  existing `delegate_task` mechanics, the concurrency cap, the flat depth, the model-inheritance line, the
  sequential fallback, **and the background/inline PIN** (do not assert inline/blocking — the review
  confirmed the PIN must stay). Append this paragraph to the section:

```markdown
**Collect results from disk, not the return channel.** Each detail subagent writes its `evaluate-job-fit`
verdict for its posting to a run-scoped scratch file (e.g. `<workspace>/.runs/<run_id>/details/<posting_id>.json`)
instead of relying on its text returning to the parent. The orchestrator's completion signal is "the expected
verdict files exist"; it then reads them, folds them into the durable digest / run record / event log (the
bundled runtime does the bookkeeping; judgment stays in the subagents and the orchestrator), and never holds
the long descriptions in its own context. This is deliberate, not a fallback: it keeps the primary context
lean and makes the run **correct regardless of the inline-vs-background question above** — whichever way
`delegate_task` returns, the verdicts are already on disk. A true sequential in-turn read is only a
last-resort fallback when no subagent can be spawned at all.
```

- [ ] **Step 5: Apply the adapter corrections in `hermes.md`** (the harness review grounded each):
  - **Identity:** replace the parenthetical "(Hermes reads a project `AGENTS.md` by walking cwd → git root)"
    with: `(Hermes loads a project `AGENTS.md` from the directory it starts in — cwd, top-level only; the cwd→git-root walk applies to `.hermes.md`/`HERMES.md`, not `AGENTS.md`. Source: agent/prompt_builder.py.)`
  - **Whole-file write (bundled runtime):** replace the `${HERMES_SKILL_DIR}` PIN with:
    `` `${HERMES_SKILL_DIR}` is a **load-time `SKILL.md` template token** (text-substituted into the rendered skill markdown, gated by `skills.template_vars`, default on), **not** a shell env var. The call works because the model reads the already-substituted concrete path from its rendered `SKILL.md`; if `skills.template_vars` is off the token will not expand — fall back to resolving the skill directory from the run path. (Source: agent/skill_preprocessing.py.) ``
  - **Scheduling / Run recipe:** add — `To bind `--deliver origin` to *this* chat, create the job with the in-session **`cronjob` tool** (`cronjob(action="create", …)`), not a shelled `hermes cron create` from a bare terminal; origin binds to the session that creates the job. Confirm the gateway daemon is running (it ticks ~every 60s) before promising automation.`
  - **Packaging & install:** in the verify block, add `hermes skills install job-search` after
    `hermes skills tap add agent-data/job-search` with a `[PIN: confirm tap add alone does not load the skill]`.
  - **Leave `--no-agent` as written** — it is a real flag, correctly described; do **not** act on the review
    doc's "fabricated" claim.

- [ ] **Step 6: Add a neutral disk-handoff note to `shared/references/parallelism.md`** (after the fallback
  paragraph):

```markdown
**Collecting results.** How a finished subagent's result reaches you — inline in the dispatch turn, or via a
**disk-handoff** (the subagent writes its result to a run-scoped scratch file and you read it on completion)
— is the active platform's adapter → Concurrent detail reads. Prefer the disk-handoff where a host's
subagents may return out-of-band, or simply to keep the primary context lean; it also makes the run correct
regardless of whether dispatch is blocking or background.
```

- [ ] **Step 7: Add tests** for the new check in `tests/test_validate_platforms.py`:

```python
def test_hermes_prior_session_present_passes(tmp_path):
    d = tmp_path / "shared" / "references" / "platform"
    d.mkdir(parents=True)
    (d / "hermes.md").write_text(
        "## Prior-session recall\n\nUse `session_search`; draft to the brief, never USER.md.\n")
    r = run_validate(tmp_path, "--only", "hermes-prior-session")
    assert r.returncode == 0, r.stdout


def test_hermes_prior_session_missing_section_fails(tmp_path):
    d = tmp_path / "shared" / "references" / "platform"
    d.mkdir(parents=True)
    (d / "hermes.md").write_text("## Identity\n\nHermes.\n")
    r = run_validate(tmp_path, "--only", "hermes-prior-session")
    assert r.returncode == 1
    assert "hermes-prior-session" in r.stdout
```

- [ ] **Step 8: Build and verify.**

```bash
./scripts/build.sh
python3 scripts/validate_platforms.py --root .
python3 -m pytest -q tests/test_validate_platforms.py
python3 scripts/doc_lint.py --root .
git status --porcelain skills
```
Expected: `Platform validation: clean.`; pytest green; `Doc lint: clean.`; `git status --porcelain skills`
empty (build.sh synced the edited adapter + parallelism.md into every skill).

- [ ] **Step 9: Commit.**

```bash
git add scripts/validate_platforms.py tests/test_validate_platforms.py shared/references/platform/hermes.md shared/references/parallelism.md skills docs/exec-plans/active/2026-06-30-hermes-job-search-assistant.md
git commit -m "feat(hermes): prior-session recall, detail-read disk-handoff, adapter corrections"
```

---

## Task 3: `job-preference-interview` — prior-session draft offer + clarify discipline

**Files:**
- Modify: `skills/job-preference-interview/SKILL.md`

**Interfaces:**
- Consumes: the `hermes.md` → `Prior-session recall` section from Task 2 (the adapter that documents the
  capability).

- [ ] **Step 1: Add the draft-offer step** to `skills/job-preference-interview/SKILL.md`, just before the
  existing depth/import fork. Use plain prose (no `adapter → …` arrow — prior-session recall is not a
  canonical section):

```markdown
## Offer a head start from prior context (only where the platform supports it)

If your platform adapter documents recalling prior sessions (a **Prior-session recall** note), you may —
**with the user's permission** — search their prior sessions and synthesize a **draft** brief to start from.
Ask first, state the benefit ("I can pre-fill a draft from what you've already told me, then you edit it"),
and give a clean decline path. On agreement, follow the adapter's rules (what to search; that the draft is
written to the workspace brief, never to durable profile memory) and present the result as an **editable
draft** alongside the usual paths: refine this draft · interview (quick / standard / thorough) · import an
existing brief. On decline — or if your platform has no such note — go straight to the depth choice. The
draft is working material, never settled truth.
```

- [ ] **Step 2: Reaffirm clarify discipline.** Add (near where the skill presents the depth choice):

```markdown
When you present the depth choice or any small closed set of options, use the closed-choice mechanism
(your adapter → Closed-choice question) and **never author an "Other" option yourself** — the host supplies
free-text. For an **open-ended** question, ask it as plain free text; do not force it into a choice picker.
```

- [ ] **Step 3: Verify.**

```bash
python3 scripts/validate_platforms.py --root .   # adapter-cross-refs: the "→ Closed-choice question" arrow resolves; no arrow to the non-canonical prior-session note
python3 scripts/doc_lint.py --root .
```
Expected: both clean. Then read the edited `SKILL.md` and confirm: the offer is permissioned, the decline
path reaches the depth choice, and there is no `adapter → Prior-session recall` arrow.

- [ ] **Step 4: Commit.**

```bash
git add skills/job-preference-interview/SKILL.md docs/exec-plans/active/2026-06-30-hermes-job-search-assistant.md
git commit -m "feat(job-preference-interview): permissioned prior-session draft offer + clarify discipline"
```

---

## Task 4: Onboarding — sequence the draft offer (§4) and ask the delivery destination (§7)

**Files:**
- Modify: `skills/job-search/references/onboarding.md` (per-skill source; not synced)

**Interfaces:**
- Consumes: the `job-preference-interview` draft offer (Task 3) and the `hermes.md` delivery guidance (Task 2).

- [ ] **Step 1: §4 (Preferences) — let the draft offer lead.** Read the current §4 fork. Add, before it
  presents the interview/import choice, a hand-off note so the offer (owned by `job-preference-interview`)
  comes first where supported:

```markdown
Hand the preference step to **`job-preference-interview`**, which opens by offering a prior-session draft
where the platform supports it (see that skill), then the depth choice or import. Do not pre-decide
interview-vs-import here in a way that skips that opening offer.
```

- [ ] **Step 2: §7 (Scheduling) — ask where to deliver.** Add to the scheduling offer:

```markdown
When you offer the schedule, also ask **where results should go** — here, an already-configured channel, or
a new destination — and pass the choice into scheduling setup. (On Hermes, create the recurring job via the
`cronjob` tool with the chosen delivery target — see your adapter → Scheduling — so `origin` binds to this
chat; a brand-new platform is a one-time, out-of-band setup, so confirm and resume rather than promising one
continuous flow.)
```

- [ ] **Step 3: Verify.**

```bash
python3 scripts/validate_platforms.py --root .   # the "adapter → Scheduling" arrow resolves (canonical)
python3 scripts/doc_lint.py --root .
```
Expected: both clean (note: `onboarding.md` lives under `skills/` so `doc_lint` does not scan it; the arrow
is checked by `validate_platforms` `adapter-cross-refs`). Read §4/§7 to confirm the flow reads naturally.

- [ ] **Step 4: Commit.**

```bash
git add skills/job-search/references/onboarding.md docs/exec-plans/active/2026-06-30-hermes-job-search-assistant.md
git commit -m "feat(onboarding): sequence prior-session draft offer and ask delivery destination"
```

---

## Task 5: `job-search-run` — collect detail-read verdicts from disk

**Files:**
- Modify: `skills/job-search-run/SKILL.md`

**Interfaces:**
- Consumes: the `hermes.md` → `Concurrent detail reads` disk-handoff contract (Task 2) and
  `parallelism.md`'s neutral collecting-results note (Task 2).

- [ ] **Step 1: Edit step 4 ("Read the details …").** After the dispatch sentence, add:

```markdown
Collect each subagent's verdict **from the run scratch on completion** — the result-collection mechanism
(inline vs a disk-handoff) is your adapter → Concurrent detail reads. Treat "the expected verdict files
exist" as the completion signal; do not require results to return inline. Then fold the collected verdicts
into the digest / event log as usual.
```

- [ ] **Step 2: Verify.**

```bash
python3 scripts/validate_platforms.py --root .   # the "adapter → Concurrent detail reads" arrow resolves
python3 scripts/doc_lint.py --root .
python3 scripts/philosophy_guard.py --root .
```
Expected: all clean. Read step 4 to confirm it no longer implies inline-only returns.

- [ ] **Step 3: Commit.**

```bash
git add skills/job-search-run/SKILL.md docs/exec-plans/active/2026-06-30-hermes-job-search-assistant.md
git commit -m "feat(job-search-run): collect detail-read verdicts from disk on completion"
```

---

## Task 6: Supersede the old plan, index the new docs, run the full gate

**Files:**
- Modify: `docs/exec-plans/active/2026-06-30-hermes-concierge-layer.md` (superseded banner; state stays
  `active` so its `active/` path — which the harness-review docs link — does not move)
- Modify: `docs/exec-plans/index.md` (annotate the old plan; add this plan)
- Modify: `TESTING.md` only if the Hermes dogfood steps need updating

**Interfaces:**
- Consumes: the new design + plan files (already created).

- [ ] **Step 1: Banner the old plan.** Add directly under the H1 of
  `docs/exec-plans/active/2026-06-30-hermes-concierge-layer.md`:

```markdown
> **Superseded** by [Hermes Job Search Assistant](2026-06-30-hermes-job-search-assistant.md) (design:
> [here](../../design-docs/2026-06-30-hermes-job-search-assistant.md)). Closed without execution after the
> [harness review](../../design-docs/hermes-harness-review/overview.md). Kept in `active/` only because the
> review docs link this path; **do not execute it.**
```

- [ ] **Step 2: Annotate the old plan in `docs/exec-plans/index.md`.** The new plan was indexed when this
  plan was authored, so only the old entry needs updating: append " — _superseded; do not execute_" to the
  `active/2026-06-30-hermes-concierge-layer.md` line under `## Active`.

- [ ] **Step 3: Run the full gate.**

```bash
python3 scripts/doc_lint.py --root .
python3 -m pytest -q
python3 scripts/philosophy_guard.py --root .
./scripts/build.sh && git status --porcelain skills
python3 scripts/validate_platforms.py --root .
```
Expected: doc_lint clean; pytest green; philosophy_guard green; `git status --porcelain skills` empty;
`Platform validation: clean.`

- [ ] **Step 4: Manual Hermes proof (off-CI, by the maintainer).** On a real Hermes install from this branch,
  walk the verify-live checklist in the [design doc](../../design-docs/2026-06-30-hermes-job-search-assistant.md)
  (§ Open questions / verify-live): `hermes skills install` is required after `tap add`; the prior-session
  offer fires only with permission and writes the brief, not `USER.md`; the detail-read disk-handoff
  assembles matches without inline returns; `--deliver origin` via the `cronjob` tool binds to the chat.

- [ ] **Step 5: Commit.**

```bash
git add docs/exec-plans/active/2026-06-30-hermes-concierge-layer.md docs/exec-plans/index.md TESTING.md docs/exec-plans/active/2026-06-30-hermes-job-search-assistant.md
git commit -m "docs(hermes): supersede the concierge plan; index the assistant plan"
```

## Progress log

- 2026-06-30 — plan created from the [Hermes Job Search Assistant design](../../design-docs/2026-06-30-hermes-job-search-assistant.md),
  itself grounded in the [harness review](../../design-docs/hermes-harness-review/overview.md). Replaces the
  superseded [concierge-layer plan](2026-06-30-hermes-concierge-layer.md).
- 2026-06-30 — T1 done: hermes/INSTALL.md + README pointer + AGENTS/ARCHITECTURE note.

## Decision log

- **Prior-session recall is modeled as a Hermes-specific capability, not a 13th canonical adapter section.**
  Mirrors the existing `scan_codex_parallel_subagents` / `scan_hermes_runtime_invocation` precedent for
  host-specific capabilities; it is not a universal concern, so the other 8 adapters need no edit and the
  neutral skill defers in prose (no validated `→` arrow). A bespoke `hermes-prior-session` check guards it.
- **The detail-read disk-handoff lives in the existing `Concurrent detail reads` section** (canonical) plus a
  neutral note in `parallelism.md`; it resolves — not works around — the inline-vs-background PIN, so the PIN
  is retained for live confirmation but no longer blocks the run.
- **`--no-agent` is left as written.** The review's cron doc claimed it was fabricated; the fact-check
  contradicted that. The adapter is already correct; do not scrub it.
- **The superseded concierge plan stays in `active/` with a banner** rather than moving to `completed/`,
  because the harness-review docs link its `active/` path; moving it would churn six docs for no gain, and
  `state: active` keeps `plan-location` green. The banner marks it do-not-execute.
