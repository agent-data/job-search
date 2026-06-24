---
title: Multi-Harness Portability — Adapter Layer + Per-Platform Distribution
state: active
created: 2026-06-22
---

# Multi-Harness Portability — Adapter Layer + Per-Platform Distribution

> **How this plan was produced.** A 57-agent research workflow inventoried every Claude-Code coupling
> in the repo (193 found), designed an adapter per target harness, and adversarially verified each
> mapping and scheduling claim. The findings — the complete coupling inventory, the per-platform
> adapter table, the neutralization pattern per kind, the scheduling matrix, and every unverified
> claim — live in the companion design doc
> [`design-docs/multi-harness-portability.md`](../../design-docs/multi-harness-portability.md)
> ("the dossier"). **This plan points at the dossier for detail; it does not restate the inventory.**
> The dossier supersedes the Codex-only [`codex-portability.md`](../../design-docs/codex-portability.md).

## Goal

Generalize job-search from a Claude-Code-only product into an **agent-harness-agnostic** one, by
introducing a thin per-platform **adapter layer** and shipping a hand-committed manifest per harness —
the proven superpowers pattern: one `skills/` tree read in place, no per-platform bundle emission, no
codegen. Agent-consumed prose stops naming Claude tools inline and instead speaks in **actions** that
defer the harness-specific literal to the active platform's adapter, which each skill self-selects (the
agent knows its platform). Codex is **live-verified end to end** (it is the only target installed here);
Cursor, opencode, Gemini, Copilot, Factory Droid, and Pi are emitted and **structurally validated**,
with every runtime claim flagged for an install-time pin (dossier §6). The one product-behavior change
is the **relaxed scheduling rule**: a native local consent-based scheduler where one exists, else a
**consent-gated** machine cron/launchd schedule as the sanctioned fallback (never silent, never cloud).

## Non-goals

- **No per-platform bundle emission or codegen.** Distribution is manifest-only — one tree, read in
  place (dossier §1, §7). `build.sh` keeps its single job (fanning `shared/references/` into skills);
  it gains a subdir copy, not a transform step. The dossier's `<active>`-resolution framing is
  **rejected** in favor of self-select (see Decision log).
- **No live verification of the six uninstalled harnesses.** Codex is the only live lane
  ([[live-data-for-all-tests]]); the rest are structural-only until installed. Every runtime claim for
  them ships with an inline "pin on install" marker (dossier §6c).
- **No rewrite of completed exec-plans, and no new product behavior** beyond the relaxed-cron rule.
- **No agent-data CLI fork.** `init` has no `--codex/--cursor/…` selector; the `--api-key`-only path is
  the sanctioned workaround (dossier §5). File the upstream ask; do not vendor or patch the CLI.
- **No flat edits to the four hand-authored references** in isolation — they must be neutralized in the
  **same pass** as their shared-tree siblings or the repo ships contradicting copies (dossier §2, §6d).
- **The Claude build must stay behaviorally byte-identical.** The Claude adapter restores today's exact
  strings; if any Claude-path behavior changes, the task is wrong.

## Done when

All hold, run from repo root:

- [ ] `python3 scripts/doc_lint.py --root .` → clean
- [ ] `python3 -m pytest -q` → green
- [ ] `python3 scripts/philosophy_guard.py` → green (the `fast|balanced|high` rename adds no score/credit field)
- [ ] `./scripts/build.sh` then `git status --porcelain skills` → empty (the `references/platform/` subdir syncs; no hand-edited bundles)
- [ ] **Claude byte-identity:** with `platform/claude.md` active, a cross-read reproduces today's `/loop` recipe, the four onboarding `AskUserQuestion` choices, the `haiku|sonnet|opus` buckets (as legacy aliases), and the `claude -p` exit-0 rule verbatim
- [ ] **Neutralization complete:** `grep -rEl 'AskUserQuestion|/loop|claude -p|\b(haiku|sonnet|opus)\b|init --claude-code' shared/references skills` returns **only** `platform/claude.md` (and dev-only docs) — no inline Claude tokens in neutralized prose
- [ ] **The four hand-authored refs** (`onboarding.md`, `scheduling-and-consent.md`, `home.md`, `customization.md`) carry no stale verbatim copy contradicting the shared tree
- [ ] **Style-guide conformance:** every neutralized agent-consumed file cross-reads clean against [`prompt-style-guide.md`](../../design-docs/prompt-style-guide.md)
- [ ] **Live Codex proof:** `codex exec` runs the search pass against **real** agent-data and returns real matches + writes a digest (transcript in Progress log)
- [ ] **Scheduling reconciled:** belief #7 + its eval, `SECURITY.md`, and `conventions.md` `schedule.time` no longer assert the blanket no-cron prohibition — all defer to the two-tier rule
- [ ] **All 7 manifests parse and every adapter resolves its cross-references** (structural lane green)
- [ ] `codex-portability.md` reconciled (CI-gate error fixed, dist-bundle framing corrected, marked superseded)

## How to execute

Per [`docs/PLANS.md`](../../PLANS.md): task-by-task, one scoped Conventional-Commit per task, appending
to the Progress log (and Decision log for judgment calls). **Hard ordering: the build mechanism (P0)
and the Claude adapter (P1) land before any prose neutralization** — every adapter cross-reference
dangles until `build.sh` syncs `platform/` and `platform/claude.md` exists (dossier §6d). Tests here are
mostly doc-lint / build / grep / eval gates rather than pytest, since the surface is prose + manifests.
**Workflow-orchestrated phases** (P1 neutralization, P2 the four refs + SKILL bodies, P5 the six
platforms) fan out one agent per file/platform through a *neutralize → adversarially-verify-against-the-
style-guide* pipeline, worktree-isolated where agents mutate files in parallel. Run the Done-when gate
before flipping `state: completed`.

---

## P0 — Codex live spike (prove the whole pattern on real hardware) · [BLOCKS]

The cheapest end-to-end proof: one tree + one manifest + one adapter + real agent-data on the Codex
already installed here (`codex-cli 0.140.0`).

- **T0.1 [BLOCKS] — Teach `build.sh` to sync the adapter subdir.** Add a copy of
  `shared/references/platform/*.md` into each skill's `references/platform/`. *Red:* a stub
  `shared/references/platform/_probe.md`, `./scripts/build.sh`, assert it appears under
  `skills/*/references/platform/` and `git status skills` shows it. *Green:* the two-line loop addition.
  Keep the existing flat copy untouched.
- **T0.2 [BLOCKS] — Author `shared/references/platform/codex.md`.** From dossier §1/§3/§4: Run recipe
  (`codex exec` one-off; Automations recurring in local project mode), tool map, scheduling (Tier-1 App
  / Tier-2 pure-CLI cron), headless (`codex exec`, real exit codes), agent-data setup (`--api-key` only),
  model tiers (`fast→gpt-5`-class, `high→gpt-5-codex`/o-series), closed-choice fallback (numbered prose),
  block-alert channel (App Triage / CLI none). Style-guide conformant.
- **T0.3 [BLOCKS] — Add `.codex-plugin/plugin.json`** beside `.claude-plugin/`, `skills: "./skills/"`
  pointing at the same tree (dossier §1). No codegen.
- **T0.4 [BLOCKS] — Live proof.** Point Codex at the tree (drop into `~/.agents/skills/` or via the
  manifest), run a live `codex exec` of the search pass against real agent-data, confirm real postings +
  a written digest. Record the command + outcome in the Progress log ([[live-data-for-all-tests]] — no
  mocks). If `multi_agent` is off, detail-reads run sequentially — acceptable; note it.

**Phase done-when:** a real Codex run returns real matches with only the Codex adapter + manifest +
the `--api-key` auth path; `build.sh` clean.

## P1 — Adapter layer + Claude adapter, Claude build byte-identical · [BLOCKS]

- **T1.1 [BLOCKS] — Author `shared/references/platform/claude.md`** capturing **today's exact strings**:
  `/loop <interval> /job-search:job-search-run` + the hour-unit quirk, namespaced-vs-loose, the
  `AskUserQuestion` mechanism, `claude -p` exit-0, the Write tool + never-shell-redirection, the
  `haiku|sonnet|opus` ids, desktop notify, `init --claude-code`. This file is the byte-identity anchor.
- **T1.2 [BLOCKS] — Neutralize the six `shared/references/*.md`** to speak in actions and defer to
  `references/platform/<your-platform>.md`, applying the 11 patterns (dossier §3). *Per file:* red = a
  grep that finds the inline Claude token; green = an action + adapter pointer, the literal moved to
  `platform/claude.md`. **Workflow-orchestrated:** one agent per file → verify-against-style-guide stage.
  *Verify:* `./scripts/build.sh && git status skills` empty; the Claude reading reproduces today's
  behavior (byte-identity cross-read); `doc_lint` clean; style-guide cross-read (Note 1).
  `agent-data-contract.md` is already agnostic (dossier §2) — skip.
- **T1.3 [BLOCKS] — Repoint the skills' inline tool mentions** to "your platform's adapter
  (`references/platform/<name>.md`)" so the agent self-selects. No `<active>` placeholder ships (Decision
  log).

**Phase done-when:** Claude behavior byte-identical; evals green; build clean.

## P2 — Neutralize the four hand-authored refs + the SKILL bodies · [BLOCKS]

The dossier's blind-spot fix — these are **not** synced by `build.sh`, so each is edited in place.
**Workflow-orchestrated** (one agent per file, verify pipeline).

- **T2.1 [BLOCKS] — `skills/job-search/references/onboarding.md`** (densest file): the ~6
  `AskUserQuestion` choices, `init --claude-code` → adapter `agent_data_init_flag`, the
  `agent-data.dev/setup/claude-code.md` URL, the `!`-bang affordance, the `≥2.1.0` version gate, the
  `/loop` §7 recipe, the namespaced slash (dossier §2).
- **T2.2 [BLOCKS] — `skills/job-search-agent/references/scheduling-and-consent.md`** — rewrite around the
  two-tier relaxed rule (defer mechanism to the adapter; **preserve** the cloud-rejection rationale as
  the test any scheduler must pass).
- **T2.3 [TUNE] — `home.md`** (status line `daily via /loop` → adapter schedule label; model tiers;
  `/loop` compose/run) and **T2.4 [TUNE] — `customization.md`** (model tiers; subagent fan-out).
- **T2.5 [BLOCKS] — The five `SKILL.md` bodies** — defer inline tool names; turn the literal **"Claude
  reads this brief"** in `job-preference-interview` (written into user-facing `preferences.md`) into a
  generic agent reference (dossier §2).
- **T2.6 [BLOCKS] — `docs/product-specs/new-user-onboarding.md`** — also hard-codes `init --claude-code`
  (found this session; the dossier missed it). Parameterize to the adapter flag.

**Phase done-when:** the neutralization grep (Done-when) returns only `platform/claude.md`.

## P3 — Scheduling relaxation across beliefs / security / conventions · [BLOCKS]

The relaxed rule's real teeth — three doc contradictions the dossier surfaced (§4).

- **T3.1 [BLOCKS] — `core-beliefs.md` belief #7 + its eval** — re-scope "the harness forbids
  crontab/launchctl writes" → "asserts no **silent/un-consented** write; a shown, user-approved Tier-2
  line is allowed." Keep the consent intent; generalize the mechanism. Update the verify-step so a green
  eval stops enforcing the lifted prohibition.
- **T3.2 [BLOCKS] — `docs/SECURITY.md` §"Scheduling never writes your machine"** — make it conditional
  on the active mechanism (Tier 1 installs nothing; Tier 2 = consent-gated, shown, user-removable).
- **T3.3 [TUNE] — `conventions.md` `schedule.time`** — no longer "informational under `/loop`"; it **is**
  honored by a wall-clock cron/launchd fallback. Defer to the adapter.

## P4 — UX degradations (model tiers · question UI · notify · headless exit)

- **T4.1 [BLOCKS] — Model-tier migration.** Config + prose carry `fast|balanced|high|inherit`; the
  adapter "Model tiers" table maps each token to the host's model id. **Breaking config change:** accept
  legacy `haiku|sonnet|opus` as aliases (the loader/onboarding maps them) so live `config.yaml` does not
  break (dossier §3, §6d). *Verify:* `philosophy_guard` green (confirmed: it scans no model names).
- **T4.2 [TUNE] — Closed-choice question.** `voice.md` keeps the agnostic decision (closed-choice vs
  prose; no tool name in user text); the adapter owns structured-picker-vs-numbered-prose per host;
  skills keep authoring the words and swap the verb.
- **T4.3 [TUNE] — Desktop-notify demotion.** The durable guarantee is the **two file-backed channels**
  (blocked digest + home-view record); the alert becomes capability-gated (adapter "Block-alert
  channel"). Honest, not a weakening — it was already conditional in the live code (dossier §3).
- **T4.4 [TUNE] — Headless exit-code per host.** Record-based surfacing stays primary everywhere; the
  adapter "Headless invocation" pins `exit-code-trustworthy (yes/no + consequence)`. The five
  `evals.json` exit-code expectations **branch on the platform under test** (Claude=0, Codex=non-zero),
  never flat-swap (dossier §6d).

## P5 — The six remaining platforms + structural validation + framing · workflow-orchestrated

- **T5.1 [BLOCKS] — Per-platform adapters** `platform/{cursor,opencode,gemini,copilot,droid,pi}.md` from
  dossier §1/§4, with every unverified item carried inline as a **"pin on install"** marker (dossier §6c).
  Fan-out, one agent per platform.
- **T5.2 [BLOCKS] — Per-platform manifests** (worktree-isolated fan-out): `.cursor-plugin/plugin.json`
  (omit superpowers' dead `agents/`/`commands/` pointers); `.opencode/plugins/job-search.js` + a **new**
  root `package.json` (none exists today — dossier §6b); `gemini-extension.json` + `GEMINI.md`
  (`@`-importing the front-door skill + `gemini-tools` adapter); Copilot **reuses** the Claude manifest
  + the `COPILOT_CLI` session hook; Factory Droid via `.claude-plugin` compat (or `.factory-plugin/`);
  Pi via a `package.json` `pi` block.
- **T5.3 [TUNE] — Per-harness entry files** pointing at `AGENTS.md` (`CLAUDE.md` stays the Claude-only
  redirect; `AGENTS.md` is already a regular file, **not** a symlink — dossier §6b).
- **T5.4 [BLOCKS] — Structural validation + CI.** A lane that parses every manifest, lints each adapter
  table, and resolves every `platform/<name>.md` cross-reference; the Codex live lane; structural-only
  lanes for the six. Extend `doc_lint` for the `platform/` subdir.
- **T5.5 [TUNE] — Framing generalization.** `AGENTS.md`/`ARCHITECTURE.md` "Claude Code as a job-search
  OS" → "an agent harness as a job-search OS"; the OS-model **Cron** row → the two-tier rule.
- **T5.6 [TUNE] — Reconcile `codex-portability.md`.** Fix the CI-gate error (it is **not** in `ci.yml`),
  correct the `dist/`-bundle framing to the in-place pattern, align its scheduling resolution with the
  relaxed rule, and mark it `superseded` by the dossier; update `design-docs/index.md`.

---

## Progress log

- **T0.1 + T0.2** — taught `build.sh` to sync `shared/references/platform/*.md` into every skill's
  `references/platform/` (guarded glob, idempotent); added the Codex adapter
  `shared/references/platform/codex.md`. Red→green verified (0→5 skills carry the adapter); `doc_lint`
  clean, 56 tests green.
- **T0.3** — added `.codex-plugin/plugin.json` (valid JSON; `skills: "./skills/"` → the same one tree,
  no per-platform bundle), harness-neutral description, job-search metadata reused from `.claude-plugin/`.
- **T0.4** — **live Codex proof.** `codex exec` (gpt-5.5) ran the real `job-search-run` skill against
  live agent-data and returned **10 real LinkedIn postings → 1 strong + 5 moderate matches + a written
  digest, exit 0** — with **no neutralization yet**, so the portable core runs as-is on Codex.
  Artifacts verified real (real companies/IDs/URLs, qualitative judgment with no scores, detail reads,
  a caught data discrepancy). Discovered + recorded the least-privilege sandbox egress config
  (`--sandbox workspace-write -c sandbox_workspace_write.network_access=true`) the dossier had flagged
  untested, and folded it back into `platform/codex.md`. **P0 egress proof complete; see the 2026-06-23
  correction below for the separate workspace-write persistence gap.**
- **T1.1** — authored `shared/references/platform/claude.md`, the **byte-identity anchor**: 12 sections
  mirroring `codex.md`, carrying today's exact Claude literals — the `/loop` recipe `diff`-identical to
  `internals.md` L114-121, the `AskUserQuestion` constraints, `claude -p` exit-0, `init --claude-code`,
  and the `fast→haiku | balanced→sonnet | high→opus` tier mapping + legacy aliases. `build.sh` synced it
  into all 5 skills; `doc_lint` clean, 56 tests green. Task review: spec ✅, quality approved (2 Minor,
  non-blocking — accurate synthesized context, not drift).
- **T1.2** — neutralized the five shared references (`internals`, `conventions`, `voice`, `errors`,
  `parallelism`; `agent-data-contract` already agnostic — skipped) to speak in actions and defer every
  Claude literal to the active platform's adapter (`references/platform/<your-platform>.md`, self-select).
  Applied the dossier-§3 patterns per file: scheduling sections now carry the **two-tier relaxed rule**
  (Tier-1 native-local / Tier-2 consent-gated, cloud-rejection rationale preserved), the model enum is
  `fast|balanced|high|inherit`, and the parallel eager-batch imperative is kept inline. The master grep
  over `shared/references` now returns only the two adapters (`claude.md`; `codex.md`'s L108 legacy-alias
  line is the lone expected residue, reworded in P4.T4.1). `build.sh` synced all five into the skill
  copies; `doc_lint` clean, 56 tests green. Reviews: internals ✅ (validated as the idiom template);
  conventions/voice/errors/parallelism ✅ (batch) — all spec-pass, quality approved (6 Minor density nits
  total, non-blocking).
- **T1.3** — the self-select adapter-pointer convention (`references/platform/<your-platform>.md`, **no
  `<active>` placeholder**) is established by T1.2 and verified repo-wide; the skill-layer inline tool
  mentions are neutralized in P2 per-file (single-touch — see Decision log). **P1 complete.**
- **T2.1** — neutralized `skills/job-search/references/onboarding.md` (the densest-coupled file; hand-authored,
  not build-synced). All 10 coupling sites + 3 in-scope follow-ons deferred to the active adapter: the
  closed-choice asks, the agent-data setup line (dropping `--claude-code` — site 1/3), the setup-doc URL,
  the `!`-bang affordance, the version gate, the headless exit-code note, and the **§7 scheduling rewrite**
  (two-tier relaxed rule, consent gate moved INSIDE the start step, verbatim recipe behind an E7 fence).
  agent-data product literals (`motie.dev` URL, `mtk_` prefix, `npm install -g agent-data`) correctly kept.
  Token grep clean; every literal confirmed in claude.md; `doc_lint` clean, 56 tests green. Review: spec ✅,
  quality approved (1 Minor, intentional consent-gate restatement — no fix). The onboarding UX (welcome-first,
  one-sentence-context-per-ask, solution-first prereq) preserved.
- **T2.2** — rewrote `skills/job-search-agent/references/scheduling-and-consent.md` around the two-tier
  relaxed rule (Tier-1 native-local installs nothing / Tier-2 consent-gated machine schedule). The blanket
  "never initiate crontab/launchd" prohibition is lifted **only at Tier 2** and replaced by a live consent
  gate (explicit yes + exact line shown first + never silent + user-removable); the **cloud-rejection
  rationale** and the "no enforcement hook — a design rule, not a technical control" stance are preserved.
  The consent gate is unmissable at both action entry points. Token grep clean; literals in claude.md;
  `doc_lint` clean, 56 tests. Review: spec ✅, quality approved (3 Minor non-blocking → final-review triage:
  caps parity w/ internals template, an awkward L34 clause; and the job-search-agent SKILL scheduling
  section it now contradicts — neutralized in T2.5).
- **T2.3 + T2.4** — neutralized `home.md` (status line drops the `/loop` mechanism label → cadence-only;
  marker records the active mechanism; detail-model enum → `fast|balanced|high|inherit`; recipe/teardown
  deferred to the adapter; rendering surface → "wherever the user is reading") and `customization.md`
  (model-tuning table → tier tokens, model ids + per-subagent-support caveat deferred to the adapter;
  fan-out deferred). Batch review caught 2 spec misses (a `loop` value re-leaked in home.md; the missing
  per-subagent-host-support note) + 3 Minor style nits — all fixed in a follow-up wave (grep-verified).
  Token grep clean; `doc_lint` clean, 56 tests green.
- **T2.5** — neutralized the SKILL bodies: `job-search` (headless naming → adapter); `job-search-run`
  (fan-out + model tier default `fast` + notify + headless all deferred); `job-search-agent` (scheduling
  section rewritten to the two-tier rule, now AGREEING with `scheduling-and-consent.md`; notify/headless/
  fan-out deferred); `job-preference-interview` (closed-choice deferral + the user-facing `preferences.md`
  footer "Claude reads this brief" → "your job-search assistant reads this brief"). `evaluate-job-fit`
  verified agnostic (no edit). Frontmatter manifest fields untouched. Batch review: all 4 spec ✅, quality
  approved (2 Minor non-defects). Token grep clean across all five SKILLs.
- **T2.6** — neutralized `docs/product-specs/new-user-onboarding.md`: the hard-coded `agent-data init
  --claude-code` deferred to the adapter (3rd init site), the setup-doc URL deferred, the "Claude Code"
  framing removed, and §7 generalized to the two-tier schedule offer ("whichever tier applies"). `code_refs`
  resolve, `last_reviewed` bumped, `doc_lint` clean, 56 tests. Review: spec ✅, quality approved (3 Minor; 1
  fix-worthy copyedit — a thinned "follow the setup-doc steps" directive — deferred to the final fix wave).
  **P2 complete:** all four hand-authored refs + all five SKILL bodies + new-user-onboarding neutralized.
- **T3.1 + T3.2 + T3.3 (P3 — scheduling relaxation)** — re-scoped the two policy docs to the two-tier
  relaxed rule, preserving the consent intent. `core-beliefs.md` Belief 7: statement/why/enforced-by/verify
  re-scoped off `/loop`-only + "the harness forbids crontab/launchctl writes" → "the agent never initiates
  a **silent/un-consented** privileged write; a shown, user-approved Tier-2 line is allowed"; the
  verify-step now frames a green eval as offer+compose+record behavior (noting evals stub scheduling), not
  an enforced prohibition. `docs/SECURITY.md`: heading + body made conditional on the active mechanism (the
  absolute "never writes your machine" claim gone; the consent gate + design-rule/no-hook framing kept).
  T3.3: `conventions.md` `schedule.time` was already two-tier (P1.T1.2) ✓; the example-config template's
  stale comments are folded into P4.T4.1 (single-touch). Batch review: both spec ✅, quality approved,
  cross-doc agreement confirmed (consent not weakened). `doc_lint` clean, 56 tests. **P3 complete.**
- **T4.1 (model-tier migration)** — `templates/config.example.yaml` now seeds `detail_model: fast` with the
  `fast|balanced|high|inherit` enum + adapter pointer, and its `frequency`/`time` comments carry the
  `/loop`-free two-tier wording; `shared/references/platform/codex.md`'s legacy-alias line was reworded
  token-free. The `\b(haiku|sonnet|opus)\b` grep over `shared/references`+`skills` now returns **only**
  `platform/claude.md` (the sole home for literal Claude model names — D3 resolved). Back-compat holds (a
  live config carrying `haiku` resolves via claude.md's legacy→tier mapping; the loader defers, never
  hard-rejects). `philosophy_guard` clean (no score/credit field added). Review: spec ✅, quality approved.
- **T4.2 + T4.3** — CONTROLLER-VERIFIED complete (no edits): closed-choice was fully neutralized in P1.T1.2
  (voice.md decision) + adapters + P2 skills; desktop-notify was demoted in P1.T1.2 (errors.md two
  file-backed channels + capability-gated alert) + P2 SKILLs, with the `desktop_notify_on_block` field kept.
- **T4.4 (headless exit-code branching + eval init-flag)** — the 3 coupled eval suites are now
  platform-aware: `--claude-code` dropped from all 6 init sites (rephrased around the harness-neutral
  `agent-data init … --api-key … --yes` essential, still true for the Claude agent); blocked-path exit-code
  expectations platform-scoped (record-primary universal; exit-0-on-block = the Claude add-on, non-zero
  noted for trustworthy-exit harnesses — **never flat-swapped**); success-path "Exits 0" + all
  blocked-record assertions preserved; job-search-agent L34 "/loop" → "the active scheduler"; the dev-only
  `/loop`/question-box Claude tests + the stubbing instructions kept. All `evals.json` parse; `doc_lint`
  clean, 56 tests. Review: spec ✅, quality approved (1 Minor — parenthetical `--claude-code`, judged
  acceptable; 1 cosmetic doubled-parenthetical at L95/L109, deferred). **P4 complete.**
- **T5.1 (six per-platform adapters)** — authored `platform/{cursor,opencode,gemini,copilot,droid,pi}.md`,
  each mirroring codex.md's 12 sections, filled from dossier §1/§4 with every unverified runtime claim
  carried as an inline **PIN** (cursor 24 · opencode 23 · gemini 22 · pi 24 · copilot 9 · droid 10 — the
  last two lower, more file-verified). No `haiku|sonnet|opus` / `init --claude-code` in any (the grep stays
  scoped to `claude.md`); `--api-key`-only agent-data setup; Tier-2 consent-gated scheduling with the gate
  inside the recipe; mandatory sequential fallback everywhere; §6b WRONG-claim corrections applied the right
  way. Batch review (opus): 3 Important fixed — a runnable `crontab -e` was removed from the copilot+droid
  Run-recipe fences (a consent-safety regression vs codex.md), and cursor's leaked Codex `$`-prefix token
  fixed — plus 2 Minor (opencode L18 consistency, copilot invocation PIN). `build.sh` synced all six;
  `doc_lint` clean, 56 tests.
- **T5.2 + T5.3 (manifests + entry files)** — manifest-only, zero-codegen distribution: `.cursor-plugin/
  plugin.json`; root `package.json` (opencode `type:module`/`main` + the pi block, one file both consumers)
  + `.opencode/plugins/job-search.js` (config + messages.transform hooks); `gemini-extension.json` +
  `GEMINI.md`; `.factory-plugin/plugin.json`; **Copilot reuses `.claude-plugin/`** (no new file). Each points
  at the one `skills/` tree (Claude auto-discovers; others add `skills:"./skills/"` or inject via hook/`pi`
  block). T5.3: `CLAUDE.md` stays the Claude redirect, `GEMINI.md` is the only new named entry, `AGENTS.md`
  serves the rest. Reconciled the gemini adapter's stale `gemini-tools.md` reference (it now points at the
  adapter itself). Batch review (opus): all six ✅. **Crash recovery note:** the host crashed mid-T5.2
  (cursor manifest); recovered intact; remaining manifests + reviews redone on **Opus** per the corrected
  model policy. Also: an **opus re-review** of the earlier sonnet-implemented `home`/`customization`/
  `new-user-onboarding` → all ✅ at the opus bar (1 deferred Minor: customization L72/L81 duplicate sentence).
- **T5.4 (structural-validation lane)** — `scripts/validate_platforms.py` (stdlib, doc_lint shape) +
  `tests/test_validate_platforms.py` (22 cases) + a CI step. Three checks: **adapter-sections** (all 8
  adapters carry the 12 canonical sections; synced copies byte-equal), **manifest-parse** (every manifest
  JSON parses; `.opencode/…js` via `node --check`), **adapter-cross-refs** (every `adapter →` / `defers to →`
  pointer resolves to a canonical section present in EVERY adapter — 149+ pointers). Codex live lane = the
  manual P0 proof; the six are structural-only via this validator. Review (opus, code): checks confirmed
  non-vacuous; 1 Important — the cross-ref anchor missed the `defers to →` form (12 real sites silently
  unvalidated) — **FIXED** (anchor broadened, 2 tests added, probe confirms no false-match). Validator clean,
  **78 tests**, doc_lint + philosophy_guard clean. 2 Minor (source-driven synced-copy check) deferred.
- **T5.5 + T5.6 (framing + reconcile)** — `AGENTS.md`/`ARCHITECTURE.md` framing generalized ("an agent
  harness as a job-search OS"; "the host agent"), with the OS-model Cron row + scheduling-consent domain on
  the two-tier rule, error-surfacing on the two file channels + capability-gated alert, and distribution on
  the multi-harness manifest-only pattern (only legit residue: "e.g. Claude Code, Codex"). `codex-portability.md`
  marked **superseded** by the dossier, its three load-bearing stale claims corrected (false CI-gate → the
  real CI; dist-bundle → in-place one-tree; scheduling → two-tier); `design-docs/index.md` moved it under
  Superseded (still linked). Batch review (opus): both ✅, quality ship; 2 Minor (residual inconsistencies in
  the now-exempt superseded doc) → final-review triage. `doc_lint` clean, 78 tests.
  **P5 complete — P1–P5 all done.**
- **Done-when gate fix** — the full neutralization grep caught contrastive Claude-token asides in two
  adapters (`copilot.md` L60/L84 `/loop`/`claude -p`; `droid.md` L62/L103 `/loop`/`AskUserQuestion`) that
  codex.md and the other four avoid. Rephrased to codex.md's clean style (contrast kept, literal tokens
  dropped). The grep now returns ONLY `platform/claude.md` (+ synced) + the three `evals.json` dev-specs.
- **FINAL — whole-branch review + Done-when gate.** Gate GREEN: `doc_lint`, `pytest` (78), `philosophy_guard`,
  build→skills-sync, byte-identity markers in claude.md, the neutralization grep (only `platform/claude.md`
  + evals dev-specs), the four hand-authored refs clean, `validate_platforms` (8 adapters × 12 sections,
  manifests parse, 149+ cross-refs resolve), `codex-portability` superseded; live Codex proof = P0. Final
  whole-branch review (opus): **READY TO MERGE — zero Critical/Important**; every non-goal respected (Claude
  byte-identity diffed vs pre-branch `main`; no codegen/bundle; no agent-data CLI fork; the four hand-authored
  refs neutralized in the same effort); two-tier scheduling consistent across all eight surfaces; deferral
  resolution complete. Applied 2 optional shipped-file polishes (copilot model-tier PIN consistency;
  customization dedup). Remaining Minors (cosmetic / dead superseded-doc) triaged acceptable. **P1–P5
  COMPLETE.** Branch left at `state: active` — **NOT merged** (the user merges after all-harness testing).
- **Follow-up — README generalized (scope-gap fix).** The user flagged that `README.md` still read Claude-only.
  Root cause: the **human-facing docs were never in scope** — the dossier §2 coupling inventory and the P1–P5
  tasks covered the agent-consumed runtime surface (`shared/references`, `skills`, AGENTS/ARCHITECTURE, the
  policy docs), not README/CONTRIBUTING/TESTING/marketing docs, and no gate scans them (the neutralization
  grep is scoped to `shared/references`+`skills`; doc_lint checks links/frontmatter, not framing). Same
  blind-spot class as `new-user-onboarding.md` (caught mid-effort). **Fixed README only** (user's choice):
  framing → "your coding agent"; kept Claude Code as the labeled **verified** quickstart; added a "Running on
  other harnesses" section (the manifest-per-harness mechanism + a manifest table + an honest
  verified/live-proven/structural-pin-on-install tiering — **no fabricated install commands** for the six
  uninstalled harnesses). doc_lint clean, 78 tests. **Deferred (out of this fix):** the Claude-only framing
  still in `CONTRIBUTING.md`/`TESTING.md` (largely legitimate — dev-only, live-eval-on-Claude) and the
  product/design docs (`INTERFACE.md`/`RELIABILITY.md`/`PRODUCT_SENSE.md`).

## Decision log

- **Self-select adapters, not build-time `<active>` resolution.** The dossier proposed the build resolve
  `platform/<active>.md` to one file. That re-introduces per-platform emission — the exact thing the
  manifest-only pattern avoids — because one built tree serves **all** platforms via their manifests.
  Instead every adapter ships in every skill (`build.sh` copies the `platform/` subdir) and skills point
  the agent at "your platform's adapter"; the agent self-selects, exactly as superpowers relies on. No
  `<active>` placeholder ships (avoids the H7 unresolved-template risk).
- **Manifest-only, zero-codegen distribution** for all seven (dossier §1) — supersedes
  `codex-portability.md`'s `build.sh`-emits-a-`dist/`-bundle recommendation.
- **Relaxed scheduling is two-tier and consent-gated** (Note 2): native local scheduler where one exists
  (install nothing); else a consent-gated cron/launchd schedule (shown, explicit yes, user-removable).
  Cloud schedulers never qualify — they can't reach the local workspace/auth. Captured in
  [[prefer-native-claude-features]].
- **Model buckets become portable tier tokens** (`fast|balanced|high|inherit`) with legacy
  `haiku|sonnet|opus` aliases for back-compat; `philosophy_guard` verified to scan no model names.
- **Codex Automations treated as Tier-1 local** on manual-text evidence (App/daemon, local project dir);
  the headless-server-box case stays an open "pin on install" (dossier §6a/§6c).
- **`docs/product-specs/new-user-onboarding.md` added to the agent-data-init scope** (T2.6) — a
  `--claude-code` site the dossier's repo-edit flag missed; found by grep this session.
- **The dossier is the design doc; this is the exec-plan.** Detail (the 193-coupling inventory, the
  per-platform tables) lives in the dossier and is pointed at, not restated, so this plan stays lean and
  does not rot (per PLANS.md).
- **Codex sandbox egress config is now verified, not a PIN** (P0): agent-data reaches the network from
  inside `codex exec` under `--sandbox workspace-write -c sandbox_workspace_write.network_access=true`
  (plain workspace-write blocks it). Resolves the dossier's "agent-data egress allowlist untested" risk.
- **Correction from 2026-06-23 live run:** egress was verified, but workspace persistence was not fully
  pinned. A nested Codex run from outside the active job-search workspace could read `~/.job-search` but could
  not write `runs/`, `reports/`, or `jobs.jsonl`, forcing temporary output under `/private/tmp`. The Codex
  run recipe now requires `cd <workspace>` or `--add-dir <workspace>`; the P0 proof should be treated as
  partial until re-run with that recipe and direct workspace persistence verified. The same `workspace-write`
  constraint applies to **Tier-1 App Automations** (they run in the project dir, which only *sees* the
  workspace) — the Codex adapter now flags pointing the Automation's working dir at the workspace, PINned
  until verified on a running App.
- **`claude.md` is the sole owner of the literal Claude model-name mapping + legacy aliases**
  (`haiku|sonnet|opus`). The Done-when neutralization grep must return only `platform/claude.md` for
  those tokens, so neutralized loader prose (`internals.md`) defers model resolution to the active
  adapter without naming them, and every other adapter names only its own model ids. **Consequence:**
  `codex.md`'s legacy-alias line (L108) currently names `haiku|sonnet|opus`; it is reworded to avoid the
  literals in P4.T4.1 (the model-tier task), keeping the grep exception to `claude.md` alone.
- **T1.3 (self-select repoint) is realized through the per-file neutralization, not a separate skill-body
  edit pass.** The self-select convention (`references/platform/<your-platform>.md`; no `<active>`) is
  baked into the neutralization protocol every implementer follows; each skill-layer file (the five SKILL
  bodies + the four hand-authored refs) is neutralized exactly once in P2 (single-touch — avoiding the
  double edit a separate T1.3-then-T2.5 pass would cause). T1.3's hard gate (no `<active>` placeholder
  ships) is verified by grep.

## Self-Review

_(author's cold-read before execution — confirm every named file/command is real, the Non-goals and
Done-when gate fence the work, and the P0→P1 ordering holds; to be completed before the first commit)_
