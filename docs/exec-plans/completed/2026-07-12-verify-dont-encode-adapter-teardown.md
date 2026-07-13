---
title: Verify-don't-encode — adapter teardown, unattended scheduling & config-time verification
state: completed
created: 2026-07-12
completed: 2026-07-13
---

# Verify-don't-encode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` (recommended)
> or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

Executes [`docs/design-docs/2026-07-11-verify-dont-encode-design.md`](../../design-docs/2026-07-11-verify-dont-encode-design.md)
(the spec — **read it first**). The design is the source of truth for every ruling and the exact
doctrine-amendment and prose wording; this plan sequences the work into landable, gated tasks and **does
not re-derive** decisions.

**Guide anchoring.** Every task cites the AAS / PSG rule IDs it turns on. They resolve against the
AAS rule index, the
PSG rule index, and the
[core beliefs](../../design-docs/core-beliefs.md). Where a rule's line/section moved, the **rule ID is the
anchor, not the number**.

**Goal:** delete the per-host adapter layer entirely (zero residual), advocate the unattended schedule, and
make a config-time run-verification canary mandatory before any schedule is recorded — so a headless run
that can't write or reach agent-data is caught at setup, never the next day.

**Architecture / order:** seven dependency-ordered phases. Neutralization (P2–P4) must strip **every**
adapter pointer before the files are deleted (P5), and `_common.md`'s neutral content must be re-homed (P1)
before its file is removed. Beliefs 7 and 12 are amended **inside their implementing phase** (P4/P3), never
ahead of the code — the same refinement the prior refactor adopted, so `core-beliefs.md` never describes a
state the code hasn't reached.

```
P0 authoring-doctrine amendments (AAS/PSG text only)
  → P1 re-home _common.md's neutral content into shared refs   (belief 5, already live)
  → P2 neutralize the mechanical adapter pointers               (AAS-LANG-01/03/08)
  → P3 model self-selection, no tier→id table                   (+ belief 12; AAS-AUTO-07/11)
  → P4 scheduling: advocate unattended + the canary             (+ belief 7; Features A & B)
  → P5 delete the adapter layer + validator                     (the teardown)
  → P6 tests & evals
  → P7 final verification sweep + version bump
```

**Tech stack:** Markdown skills/references (the product is prompt text); Python gate scripts
(`doc_lint.py`, `philosophy_guard.py`, `check_release_integrity.py`); `pytest`; the skill **evals**
(`skills/*/evals/evals.json`); portable-shell mechanics under `shared/scripts/mechanics/` (unchanged here).

## Global constraints (verbatim from the spec)

- **Zero per-host adapters.** After P5, `shared/references/platform/` does not exist; no shared body names a
  host or a host's tool. The one portable per-run knob that survives is the `search.detail_model` **tier
  token** (`fast|balanced|high`) — intent, not an id.
- **Verify, don't encode.** Encode a per-host fact only if it is *all three* of: not derivable by the agent,
  not probeable at runtime, and not verifiable after the fact. Nothing in this pack passes the test → nothing
  is encoded. (Adapter-necessity test, spec §Thesis.)
- **No harness troubleshooting.** The setup directive states required conditions in-skill; the agent debugs
  its own host. agent-data-side troubleshooting may live on (product, not harness).
- **Consent preserved** (belief 7 / AAS-AUTO-02) — the unattended schedule is shown before it's written,
  started only on an explicit yes, and stays user-removable. No silent privileged write.
- **No silent failures** (belief 4) — never claim a job is scheduled until the canary is green; on an
  unfixable failure, name the gap and stop.
- **Read the record, not the exit code** (belief 6 / AAS-LANG-08) — unchanged; the written record stays the
  universal success signal.
- **Qualitative, never numeric** (belief 1) — `philosophy_guard.py` stays green on every commit.

## Non-goals

- **Design-doc status cleanup** (stale `aspirational`/`active` frontmatter on *other* docs) — a separate
  session. This plan touches another doc **only** to fix a reference the adapter deletion would otherwise
  dangle (P5) — no status or prose change.
- **Cloud / machine-off scheduling** — the target is unattended-on-this-machine (no session open).
- **The multi-source plans** and **re-verifying the six structural-only harnesses live** — untouched.
- **No skill count change** — the five skills stay.

## Done when

All hold, run from repo root, after P7:

- [ ] `python3 scripts/doc_lint.py --root .` → `Doc lint: clean.`
- [ ] `python3 -m pytest -q` → green
- [ ] `python3 scripts/philosophy_guard.py --root .` → `Philosophy guard: clean.`
- [ ] `python3 scripts/check_release_integrity.py --check-version-sync` → passes (version bumped once for the
      runtime-surface change; all manifests in sync)
- [ ] `./scripts/build.sh` run twice → deterministic; `git status --porcelain` empty the second time
- [ ] The adapter layer is gone: `test -d shared/references/platform && echo PRESENT || echo GONE` → `GONE`
- [ ] No shared/skill body defers to an adapter:
      `grep -rniE "your (platform's )?adapter|platform/[a-z]+\.md|Model tiers →|→ Scheduling" skills shared` → 0
- [ ] No shared body names a host:
      `grep -rniE "codex|cursor|opencode|gemini|copilot|droid|claude code" shared/references/*.md` → 0
- [ ] The validator is gone: `test -f scripts/validate_platforms.py && echo PRESENT || echo GONE` → `GONE`;
      `grep -rn "validate_platforms" .github scripts Makefile* 2>/dev/null` → 0
- [ ] The behavioral evals pass, including the flipped tier-binding assertion and the new scheduling-canary
      scenario

## How to execute

Task-by-task in phase order, **one scoped conventional commit per task**, appending to the Progress log (and
the Decision log for any judgment call) as part of that task's commit. Prose/doctrine tasks are **edit →
gate**, where the gate is the `doc_lint` / `grep` / eval named in `*Verify:*`. Code/test tasks are **red →
green** (write the failing assertion first, named below). Every commit touching a knowledge-base doc triggers
the per-commit doc-reviewer pass (`docs/PLANS.md` §Execution protocol). Run the Done-when gate before
flipping `state: completed` and moving this file per the lifecycle.

**Task tags:** `[BLOCKS]` a later phase depends on it · `[S/M/L]` rough size.

---

## P0 — Authoring-doctrine amendments (AAS/PSG text only)

Edits `status: current` guide docs that describe **how to write**, not the current code state — safe to land
first. Apply the **exact wording from the spec's §Doctrine touched**; do not paraphrase.

- [ ] **T0.1 [BLOCKS, S] Add the verify-don't-encode clause to `AAS-LANG-07`** in
  the agent-agnostic skill-pack guidance. Append a **Rule addition** stating:
  *"Where a host-specific action produces an observable artifact, runtime verification substitutes for the
  adapter this rule would otherwise require; the pure-abstraction failure this rule records applies only
  where no runtime backstop exists."* Cite the spec (`2026-07-11-verify-dont-encode-design.md` §Thesis).
  *Verify:* `doc_lint` clean; the clause is present in the skill-pack guidance.

- [ ] **T0.2 [BLOCKS, S] Note the `AAS-LANG-04` self-selection deviation** in the same file. Add: this pack
  binds the model tier to a concrete id by **agent self-selection from its own roster**, not an adapter table
  — the tier token stays the portable intent; the required-model slot (`AAS-AUTO-07`) and the
  judgment-never-cheapest guardrail (`AAS-AUTO-11`) are the mitigation for the absent runtime backstop.
  *Verify:* `doc_lint` clean; the self-selection note is present in the skill-pack guidance.

- [ ] **T0.3 [BLOCKS, S] Update the `PSG-SUB-09` local application** in
  the prompt/doc style guidance §"What we deliberately do
  differently": the Codex subagent-approval gate moves from *"preserved as a harness-specific exception in
  the adapters"* to **a self-aware conditional in the shared body** ("*if* your host gates subagents behind
  approval, get it once before fanning out"). *Verify:* `doc_lint` clean; grep the section shows the
  conditional phrasing and no "in the adapters".

---

## P1 — Re-home `_common.md`'s neutral content into the shared references

`_common.md` is host-neutral already; its content moves to the shared reference it belongs to, so nothing
dangles when the adapter layer is deleted (P5). Rules: belief 5 (single home), `AAS-FORM-04` (one edit home),
`AAS-LANG-08` (written record).

- [ ] **T1.1 [BLOCKS, M] Move the *Written record* contract into `errors.md`.** Copy `_common.md` →
  *Written record* (the three blocked-run channels + record-is-primary) into `shared/references/errors.md`
  next to the named-error surfacing rules, as neutral prose. *Verify:* `doc_lint` clean;
  `grep -n "written record\|record is primary" shared/references/errors.md` → hits.

- [ ] **T1.2 [BLOCKS, S] Move the *atomic whole-file write* rule into `internals.md`** (it already owns the
  registry whole-file write rules — natural home). Include the `jobs.jsonl` `>>` append exception. *Verify:*
  `doc_lint` clean; `grep -n "whole file\|atomic" shared/references/internals.md` → hits.

- [ ] **T1.3 [BLOCKS, S] Move the *Block-alert two-file frame* into `errors.md`** (alongside the surfacing
  channels): the durable guarantee is the two file channels; the attention-pull alert is additional and
  skipped silently where absent (`AAS-LANG-03`). *Verify:* `doc_lint` clean; grep in `errors.md`.

- [ ] **T1.4 [BLOCKS, S] Move the *neutral agent-data auth* path into `agent-data-contract.md`** (the
  `agent-data init --api-key … -y` path). *Verify:* `doc_lint` clean;
  `grep -n "api-key" shared/references/agent-data-contract.md` → hits.

- [ ] **T1.5 [S] Repoint any non-adapter reference to `_common.md`** to the new homes:
  `grep -rn "_common.md" skills shared | grep -v "platform/"` → rewrite each to the T1.1–T1.4 home. *Verify:*
  that grep → 0.

---

## P2 — Neutralize the mechanical adapter pointers (no behavior change)

Rewrite every non-scheduling, non-model `"your platform's adapter → …"` pointer to neutral action-language
(`AAS-LANG-01`), a self-aware conditional (`AAS-LANG-03`, `PSG-SUB-09`), or the written-record contract
(`AAS-LANG-08`). Scheduling and model pointers are owned by P4/P3. Transformation rule, three worked
examples, then an exhaustive grep gate — the same pattern the repo's prior refactor used for its bulk
pointer sweep.

**Transformation rule.** `"do X (see your platform's adapter → Y)"` → name the **action** X directly and drop
the pointer; if X is a capability some hosts lack, phrase it as a conditional with a named fallback.

**Worked examples (apply verbatim; representative of the class):**
- Tool map — `"dispatch a subagent (see your platform's adapter → Concurrent detail reads)"` →
  `"dispatch a subagent"`.
- Headless success — `"whether $? is trustworthy is per-harness (see your adapter → Headless invocation)"` →
  `"surface every outcome through the written record; a real exit code, where your host provides one, is an
  additional signal only"` (`AAS-LANG-08`).
- Alert — `"fire the block alert (see your adapter → Block-alert channel)"` → `"if your host has an
  attention-pull surface, fire one block alert; otherwise the two file channels carry the failure"`
  (`AAS-LANG-03`).

- [ ] **T2.1 [BLOCKS, S] Build the worklist.** `grep -rn "your platform's adapter\|your adapter" skills shared`
  → record every hit. Mark each as *mechanical* (this phase), *model* (P3), or *scheduling* (P4). *Verify:*
  the list is complete and partitioned (paste into the Progress log).

- [ ] **T2.2 [M] Rewrite the Tool-map / Closed-choice / Whole-file-write pointers** to neutral actions across
  `internals.md`, `conventions.md`, `voice.md`, and the SKILL bodies. `AAS-LANG-01`; closed-choice keeps its
  numbered-prose fallback (`voice.md`). *Verify:* those pointers → 0 in grep.

- [ ] **T2.3 [M] Rewrite the Concurrent-detail-reads pointer to a self-aware conditional** in
  `parallelism.md` and `skills/job-search-run/SKILL.md`: *"Dispatch a subagent per queued posting. If your
  host gates subagents behind explicit user approval, get it once before fanning out; if it has no subagent
  primitive or no slot is free, read sequentially — never fabricate a dispatch."* `AAS-LANG-03`, `PSG-SUB-09`,
  belief 12. *Verify:* grep the pointer → 0; the conditional present.

- [ ] **T2.4 [M] Rewrite the Headless-invocation pointer** in `skills/job-search-run/SKILL.md` and
  `errors.md`: name the action ("run the pass non-interactively") and route success through the written
  record (T1.1); **drop all exit-code-trust language**. `AAS-LANG-08`, belief 6. *Verify:* grep
  `"exit code.*per-harness\|adapter → Headless"` → 0.

- [ ] **T2.5 [S] Rewrite the Block-alert and agent-data-setup pointers** to the re-homed homes (T1.3, T1.4)
  and neutral action. *Verify:* those pointers → 0.

- [ ] **P2 gate:** `grep -rn "your platform's adapter\|your adapter" skills shared` → only *model* (P3) and
  *scheduling* (P4) hits remain. `doc_lint` clean.

---

## P3 — Model self-selection (no tier→id table)

Rules: belief 12, `AAS-AUTO-07` (required model slot), `AAS-AUTO-11` (cheapen mechanics, never judgment),
`AAS-LANG-04` (deviation noted in T0.2).

**Canonical wording to install (spec §Model selection without a table):**
> Dispatch every subtask with an **explicitly specified** model (a required slot — never omit it, or it
> silently inherits the wrong tier). Use the **least powerful model that can handle the task well, to
> conserve cost and increase speed**: the mechanical steps (dedup, prefilter, extraction, provenance) on your
> **cheapest** model; the per-posting fit **verdict is a judgment, so never your cheapest** — the
> least-powerful model that does *that judgment* well, scaled up for a higher-risk or ambiguous posting. Bind
> the tier to a concrete model **from your own roster**.

- [ ] **T3.1 [BLOCKS, M] Rewrite the runner's model-dispatch guidance** in `skills/job-search-run/SKILL.md`:
  replace "resolved from `search.detail_model` … the model id each tier maps to is in your platform's adapter
  → Model tiers" with the canonical wording above. Keep `search.detail_model` as the portable tier token.
  *Verify:* `grep -n "adapter → Model" skills/job-search-run/SKILL.md` → 0; the required-slot + judgment-never-cheapest phrasing present.

- [ ] **T3.2 [S] Update `parallelism.md`** model-selection language to the canonical wording (self-selection,
  required explicit model). *Verify:* grep the adapter pointer → 0.

- [ ] **T3.3 [S] Update `conventions.md` `detail_model`** description: the tier token is portable intent; drop
  "the model each tier maps to lives in your platform's adapter → Model tiers"; add "the agent binds the tier
  to a concrete model from its own roster." *Verify:* grep → 0; `doc_lint` clean.

- [ ] **T3.4 [S] Amend belief 12** in `docs/design-docs/core-beliefs.md`: append that the dispatching model is
  bound by **agent self-selection from its own roster with an explicit required slot**, no adapter table
  (`AAS-AUTO-07`, `AAS-LANG-04` deviation). *Verify:* `doc_lint` clean.

- [ ] **P3 gate:** `grep -rniE "tier.*→.*id|adapter → Model|Model tiers" skills shared` → 0 (outside the
  yet-to-be-deleted `platform/`).

---

## P4 — Scheduling: advocate unattended + the canary (Features A & B)

Rules: belief 4 (no silent failures), belief 7 (consent-gated scheduling — amended here), `AAS-AUTO-02`
(consent on the one-way door), `AAS-LANG-08` (written record), `PSG-SUB-06` (prove it works, not that it
exists).

- [ ] **T4.1 [BLOCKS, M] Rewrite `skills/job-search-agent/references/scheduling-and-consent.md`** —
  **Feature A.** Advocate the **unattended** schedule (runs with no session open) as the default, using the
  host's/OS's scheduler that survives session-close, preferring one that re-fires missed runs on wake. Demote
  the in-session loop to a **named fallback** (say plainly it runs only while a session is open). Keep consent
  intact: show the exact change first, apply on an explicit yes, keep it user-removable. State the required-
  conditions setup directive: *"set up the run so it can write the workspace and call agent-data."* Remove the
  Tier-1/Tier-2 "see your adapter → Scheduling" pointers. *Verify:* `doc_lint` clean; grep no adapter pointer;
  "unattended" advocated before the loop.

- [ ] **T4.2 [M] Rewrite `shared/references/internals.md` Scheduling setup** to the same re-weighting in
  neutral terms ("your host's/OS's scheduler that survives session-close"). **Keep** the cadence composition
  via `../scripts/mechanics/schedule-line.sh` (host-neutral, unchanged). *Verify:* `doc_lint` clean; grep no
  adapter pointer; `schedule-line.sh` still referenced.

- [ ] **T4.3 [BLOCKS, L] Add the config-time canary — Feature B** to `scheduling-and-consent.md` and
  `internals.md` (Scheduling setup). Install this behavior verbatim in spirit (spec §Feature B):
  > **Before recording the schedule, prove it works.** (1) *Registration:* confirm the schedule appears in the
  > host/OS scheduler's own job list. (2) *Execution canary:* trigger **one real run through the exact
  > scheduled invocation** — non-interactive, the scheduled command's permissions and environment, not this
  > session's — and confirm the artifacts: a fresh `runs/<id>.json` with `run_health` ≠ `blocked`, that
  > agent-data was reached, and that the workspace was written. If the canary fails, **debug it yourself**:
  > diagnose the specific missing capability from the artifacts, propose the exact host-appropriate fix, show
  > it, apply on the user's yes, and re-run the canary — loop until green. If it cannot be made to work, name
  > the exact gap and stop; **do not** claim it is scheduled. Only after a green canary, set the scheduling
  > marker.
  *Verify:* `doc_lint` clean; grep `"canary\|before recording the schedule"` → hits; the "same-context" and
  "never claim scheduled until green" sentences present.

- [ ] **T4.4 [M] Update `skills/job-search/references/onboarding.md` §7** (scheduling offer) to advocate the
  unattended schedule and **run the canary before recording**, in the onboarding voice. *Verify:* `doc_lint`
  clean; grep the canary reference in onboarding.

- [ ] **T4.5 [S] Amend belief 7** in `core-beliefs.md`: advocate the unattended schedule (consent preserved;
  session-loop demoted to fallback) and **add the mandatory config-time canary** as a precondition to
  recording a schedule. *Verify:* `doc_lint` clean.

- [ ] **P4 gate:** `grep -rn "your platform's adapter\|your adapter" skills shared` → **0** (all pointers now
  gone). `doc_lint` clean; `philosophy_guard` clean.

---

## P5 — Delete the adapter layer + validator (the teardown)

Only runnable once P2–P4 removed every pointer (P4 gate) and P1 re-homed `_common.md`. Rule: the
adapter-necessity test (spec §Thesis) — nothing passes, so nothing remains.

- [ ] **T5.1 [BLOCKS, S] Pre-flight the deletion.** Confirm zero live references into `platform/` from runtime
  surfaces: `grep -rn "platform/" skills shared` → 0. (Design-doc `code_refs` are handled in T5.4.) *Verify:*
  that grep → 0.

- [ ] **T5.2 [BLOCKS, S] Delete the adapter files.** `git rm shared/references/platform/*.md` (all nine,
  `_common.md` included) and remove the now-empty directory. *Verify:*
  `test -d shared/references/platform && echo PRESENT || echo GONE` → `GONE`; `doc_lint` clean.

- [ ] **T5.3 [BLOCKS, M] Delete the validator + its CI lane.** `git rm scripts/validate_platforms.py`; remove
  the `validate_platforms` step from `.github/workflows/ci.yml` and any `Makefile`/test invocation. *Verify:*
  `grep -rn "validate_platforms" .github scripts Makefile* tests 2>/dev/null` → 0.

- [ ] **T5.4 [M] Fix references the deletion dangles — reference-only, no status/prose change.** Update
  `code_refs`/links that point at the deleted paths so `doc_lint` stays green: at minimum the two guide docs
  edited in P0, `core-beliefs.md`, and any doc whose `code_refs` lists `shared/references/platform/*`
  (`grep -rln "shared/references/platform" docs`). Remove the deleted paths from each `code_refs`; repoint any
  in-prose link to the re-homed home. **Touch nothing else in those docs** (per Non-goals). *Verify:*
  `doc_lint` clean; `grep -rn "shared/references/platform" docs` → 0.

- [ ] **P5 gate:** `doc_lint` clean; the Done-when adapter/validator greps all pass.

---

## P6 — Tests & evals

Rules: `AAS-TEST-04` (assert the tier binding, not host literals — now flipped), belief 4/7 (the canary
behavior), belief 6 (written record).

- [ ] **T6.1 [BLOCKS, M] Flip the tier-binding eval.** Locate the assertion that the model tier "resolves
  from the adapter table" (`grep -rn "tier\|detail_model\|Model tiers" skills/job-search-run/evals/ tests/`).
  Rewrite it to assert the runner **dispatches an explicit, non-cheapest model for the per-posting verdict**
  (intent-based grader, `AAS-ANTI-32`). *Verify:* the eval runs and asserts the new intent;
  `grep -rn "adapter table\|Model tiers" skills/job-search-run/evals tests` → 0.

- [ ] **T6.2 [M] Update the reference-resolution / portability tests** that asserted adapter structure.
  `grep -rn "platform\|validate_platforms\|adapter" tests/` → for each: delete the adapter-structure
  assertion or repoint it to the re-homed reference. Keep the mechanics-script and per-host in-place
  resolution tests that are still meaningful. *Verify:* `python3 -m pytest -q` → green.

- [ ] **T6.3 [M] Add a scheduling-canary eval scenario.** In the `job-search` front-door evals, add a
  **stubbed-scheduler** scenario (evals stub scheduling — no real crontab/launchd) asserting: the flow runs
  the canary before recording; on a **simulated canary failure** it does **not** set the scheduling marker and
  names the gap; on success it sets the marker. `PSG-SUB-06`, belief 4. *Verify:* the scenario runs and both
  arms pass.

- [ ] **T6.4 [S] Update `TESTING.md`.** Note that the cross-host manual matrix shrinks because verification is
  now a **runtime per-host check** (the canary); label the remaining un-installable-host residual. *Verify:*
  `doc_lint` clean.

- [ ] **P6 gate:** `pytest -q` green; the flipped + new evals pass.

---

## P7 — Final verification sweep + version bump

- [ ] **T7.1 [BLOCKS, M] Run the full Done-when gate** (every checkbox in §Done when). Fix any miss in the
  owning phase's file, re-commit, re-run. *Verify:* all Done-when boxes green.

- [ ] **T7.2 [BLOCKS, S] Bump the version.** This changes runtime surface (`skills/**`, `shared/**`,
  `scripts/**`), so bump the version in every manifest and regenerate the stamp: `./scripts/build.sh`, then
  `python3 scripts/check_release_integrity.py --check-version-sync`. *Verify:* the check passes; `build.sh`
  run twice leaves `git status --porcelain` empty.

- [ ] **T7.3 [M] Live smoke** (where a host is available): run one real headless `job-search-run` against a
  scratch workspace and confirm the neutralized runner + model self-selection still produce a digest end-to-
  end (the same shape the onboarding run produced). Then run the interactive scheduling flow far enough to see
  the **canary** fire and gate on its artifacts. *Verify:* a fresh digest is written; the canary refuses to
  record on an induced permission failure and records on success.

- [ ] **T7.4 [S] Close the plan.** Flip `state: completed`, move this file to `docs/exec-plans/completed/`,
  update `docs/exec-plans/index.md`. *Verify:* `doc_lint` clean.

---

## Progress log

_(Append one line per completed task: `T#.# — <commit sha> — <one-line outcome>`.)_

## Decision log

_(Append any judgment call made during execution that the spec did not settle, with its rationale.)_
