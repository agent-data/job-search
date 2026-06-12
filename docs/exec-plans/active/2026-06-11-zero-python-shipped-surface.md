---
title: Zero-Python shipped surface — native procedures replace osctl.py / state.py
state: active
created: 2026-06-11
---

# Zero-Python shipped surface

## Goal

Users can't be assumed to have Python. Three Python artifacts ship to user machines today: the
bundled `scripts/osctl.py` + `scripts/state.py` inside every skill, and the plugin hook
(`hooks/hooks.json` runs `python3 …/guard-scheduled-tasks.py` on **every** Bash call — on a
Python-less Mac that errors or pops the CLT-install dialog). Everything the scripts do is tiny
JSON file I/O plus string mapping that Claude Code performs natively (Read/Write tools + portable
Bash one-liners). After this plan, the shipped surface (skills + plugin) contains **no Python at
all**; each former script operation becomes a canonical procedure defined once in
`shared/references/` and cited by the skills.

Owner decisions (recorded 2026-06-11): scope is **ship-side only** — dev/CI tooling
(`doc_lint.py`, `philosophy_guard.py`, `build.sh`, pytest, the fake-agent-data shim) stays
Python, since CI pins Python 3.11 and users never run it. The guard hook is **deleted, not
ported** — users are free to use cron/launchd on their own machine if they explicitly ask; the
skills keep the instruction-level stance (schedule via `/loop`, never initiate cron/launchd
installs yourself).

## Non-goals

- **No Python removal from dev/CI tooling.** `doc_lint.py`, `philosophy_guard.py`, pytest, the
  eval shim, and `build.sh`'s Python-adjacent checks stay exactly as they are.
- **No bash port of the guard hook.** It is removed outright (owner decision above).
- **No jobs.jsonl compaction.** The home view folds `jobs.jsonl` in-context; growth is tracked as
  a watch-only debt item (`TODO-JOBS-COMPACTION`), not built.
- **No change to the /loop scheduling design**, the registry schema, the discovery precedence, or
  any file contract — only the *executor* changes (Claude Code natively instead of Python).
- **No history rewrites.** Dated design docs (`2026-06-05-*`) get a one-line supersession note +
  `code_refs` fix only.

## Tasks

Most tasks here are prose/contract work, so "red → green" means: make the change, then prove it
with the named gate (doc_lint / pytest / grep / a live run) rather than a unit test.

1. **[BLOCKS] Native contracts in shared references.** Rewrite
   `shared/references/internals.md` (registry path expression, registry write rules, the
   Discovery procedure replacing `osctl resolve` — pinning registry-wins-unconditionally, which
   the old prose understated — scheduling marker recipes; delete the guard-hook and
   osctl-reference sections) and extend `shared/references/conventions.md` §jobs.jsonl with the
   event-line contract + the known-ids / append / fold recipes. `./scripts/build.sh` to sync.
2. **[BLOCKS] Skills cite the procedures.** Replace every `python3 "$OS"`/`"$STATE"` invocation
   across the five SKILL.md files and `skills/job-search/references/{onboarding,home}.md` with
   citations of the named procedures; rewrite `skills/job-search-agent/SKILL.md`'s subcommand
   tables into an operation→reference map; rewrite
   `skills/job-search-agent/references/scheduling-and-consent.md` without the hook.
3. **[BLOCKS] Evals assert on artifacts.** The three eval files that mention the scripts
   (`skills/{job-search,job-search-run,job-search-agent}/evals/evals.json`) assert on registry
   file contents / `jobs.jsonl` lines and seed fixtures with `printf`, not script calls.
4. **[TUNE] Knowledge-base docs tell the truth.** README drops the Python requirement;
   ARCHITECTURE/RELIABILITY/SECURITY/INTERFACE/core-beliefs (#5, #6, #7)/QUALITY_SCORE/
   product-spec/AGENTS/CONTRIBUTING/TESTING describe the native architecture honestly (named
   tradeoff: runtime mechanics are eval-verified, no longer pytest-proven); historical design
   docs get `code_refs` fixes + a supersession line.
5. **[BLOCKS] Delete the Python artifacts.** `scripts/{osctl,state,gen_osctl_docs}.py`,
   `docs/generated/`, `hooks/`, `.claude/settings.json`, the four obsolete test files, all
   `skills/*/scripts/` copies; `build.sh` becomes references-only; CI drops the generated-docs
   step.
6. **[BLOCKS] Verify** per the Done-when gate, including live sandboxed end-to-end runs and the
   python3-masked headline run.
7. **[TUNE] Release.** Plugin `0.2.3 → 0.3.0`; flip this plan to completed.

## Done when

- [ ] `python3 -m pytest -q` → 0 failed (4 obsolete suites deleted; ~56 remain).
- [ ] `./scripts/build.sh && git status --porcelain skills` → empty.
- [ ] `python3 scripts/doc_lint.py --root .` → clean.
- [ ] `python3 scripts/philosophy_guard.py --root .` → clean.
- [ ] `grep -rn 'python3\|osctl\|state\.py' skills/ .claude-plugin/` → zero hits;
      `hooks/`, `docs/generated/`, `.claude/settings.json`, `skills/*/scripts/` all gone.
- [ ] Live sandboxed end-to-end (`JOBSEARCH_OS_REGISTRY`/`JOBSEARCH_OS_HOME` redirected, real
      agent-data): first-run onboarding writes the registry natively; `job-search-run` appends
      valid one-line events each with `source_id` and writes a digest; an immediate re-run dedups
      (no re-evaluation); the home view renders the pipeline from an in-context fold; the
      schedule marker toggles on/off correctly.
- [ ] Headline: a live run with `python3` masked out of PATH behaves identically — zero Python
      on the user path.

## Progress log

- 2026-06-11 — plan created.
- 2026-06-11 — tasks 1–5 done (c61a954, 3693ed8, 183caa5, da5c063, ed26e31, a218e24): contracts pinned,
  skills + evals + KB docs converted, all Python artifacts deleted. Dev gates green (pytest 56, build
  no-op, doc_lint, philosophy_guard, `claude plugin validate --strict`).
- 2026-06-11 — verification: headless E-NO-CONFIG ✅; legacy adoption (registry write byte-contract +
  never-clobber sha256-identical) ✅; home-view in-context fold ✅; schedule-marker off-toggle ✅;
  **python3-masked** full runner pass + dedup re-run + home view ✅ (shim-backed). Sandboxed home-view
  testing surfaced one robustness gap — fixed and re-verified (see Decision log). Live-API pass pending
  an agent-data key.

## Decision log

- **Ship-side only.** Dev/CI tooling stays Python: CI pins 3.11, users never execute it, and a
  deterministic linter beats a model-run check for CI. (Owner, 2026-06-11)
- **Guard hook deleted, not ported to bash.** "It's their computer, their Claude Code instance,
  and their copy of the package — they can if they want." The no-cron stance survives at
  instruction level in internals.md / SECURITY.md. (Owner, 2026-06-11)
- **Registry-wins-unconditionally pinned.** `osctl.resolve()` never fell through when the
  registry's `active_workspace` lacked `config.yaml` (it reported `first_run` instead); the old
  internals.md prose implied fallthrough. The native Discovery procedure pins the code's
  behavior — falling through silently could switch a user's workspace.
- **known-ids extraction uses `grep -o … | cut -d'"' -f4`**, not sed — the obvious
  `sed 's/.*"//'` strips the whole match (greedy); `cut` is BSD+GNU portable. The recipe is
  contract-dependent (one event per line, key once per line), so those bullets are pinned in
  conventions.md §jobs.jsonl.
- **The resolved `$REG` is the only registry — pinned after a live test caught drift.** In an
  env-redirected sandbox, a home-view run also *read* the default `~/.config/...` registry path and
  produced a confused report mixing the two registries (no write escaped; the user's pre-existing
  registry file was misattributed). The script era never had this failure because `osctl` evaluated the
  env chain in code. Fix: internals.md now prints the resolved path in the Discovery snippet and forbids
  consulting any other location; it also pins that only the front door / scheduling flows write the
  registry — the headless runner never does. Masked re-test passed.
