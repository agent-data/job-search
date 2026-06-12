---
title: Plan B/D — Design Delta & Resolved Decisions
status: historical
verified: unverified
last_reviewed: 2026-06-07
code_refs: [shared/references/conventions.md, shared/references/internals.md]
---

# Spec delta: Job Search OS — Claude-Code-driven Onboarding + OS internals (Plan B/D)

**Status:** approved (design gate, 2026-06-05). Extends the original spec
`2026-06-05-os-design.md`. Driven by the handoff `2026-06-05-plan-b-d-handoff.md` (§6 open
decisions resolved here). Read those first; this document records only what is **new or changed**.
*(Historical note, 2026-06: the Python helpers this delta specifies — `state.py` / `osctl.py` —
were since replaced by native procedures pinned in `shared/references/`; nothing Python ships
with the skills anymore.)*

## Why this delta

Plan A built the core engine. The new headline requirement: the **entire onboarding is driven by
Claude Code**. A user installs the plugin, opens Claude Code, says "go" (`/job-search`), and Claude
runs setup end-to-end — prereqs, where data lives, the interview, queries + frequency, a first live
run, and scheduling — asking inline. This requires persistent **"OS internals"** (state + knowledge
that survive across sessions) so any skill can locate the active workspace, read/update config, and
tell first-run from returning user.

## Divergences from the original spec (explicit, so they don't silently disagree)

1. **Default workspace is now the hidden `~/.job-search/`** (was `~/job-search/`). A visible directory
   in `~/` is intrusive. Discovery still **adopts** an existing visible `~/job-search/` without
   clobbering it (back-compat for the current test workspace and any user who already has one).
2. **New principle — configuration is conversational-first.** Every config change (queries, frequency,
   schedule, workspace, preferences) has a Claude-Code-driven path; manual file editing remains a
   documented escape hatch, not the default. This elevates the project's "Claude Code is the OS"
   stance to all configuration, not just onboarding.

All other philosophy is unchanged and non-negotiable: qualitative relevance (no numeric scores/
weights), frequency-not-budget (reactive plain-language `E-QUOTA` only), local-first, private
workspace, named `E-*` errors / no silent failures, magical-moment T0, docs-as-product.

## Resolved §6 decisions

1. **Topology** — one `job-search` orchestrator skill is the entry point, router, and home;
   first-run onboarding and returning home live in `references/` playbooks it follows. It delegates
   the interview to `job-preference-interview` and the search to `job-search-run`.
2. **OS internals mechanism** — a dependency-free `scripts/osctl.py` (mirrors `state.py`; stdlib only,
   **not** YAML-aware) owns the deterministic, testable parts; a `shared/references/internals.md` "OS
   manual" documents schema/algorithm/recipes for the model.
3. **Data home** — default `~/.job-search/`; registry at `~/.config/job-search-os/config.json` (XDG;
   fallback `~/.job-search-os/config.json`) records the active workspace + OS state.
4. **Scheduling autonomy** — Claude offers to set it up (append cron line, or install a launchd plist)
   with explicit consent, records a marker so it never re-asks, and always also prints the copy-paste
   fallback. Mechanism menu: cron default, launchd robust-mac upgrade, `/loop` keep-open. `osctl.py`
   *generates* the artifact; the skill performs the privileged write only on consent.
5. **"Go" trigger** — slash command + natural-language triggers via a strong `description`. Plugin
   skills are namespaced (`/<plugin>:job-search`); Plan D solves a clean `/job-search` via plugin
   naming and/or a top-level `commands/job-search.md` forwarder.
6. **Home UX** — returning `/job-search` shows status (workspace, brief age, schedule + last run
   health), latest digest summary (date + counts), a pipeline snapshot (counts by status +
   `needs_human_check` to review), and conversational quick-actions (run now / add-edit query / change
   frequency / re-interview / change schedule / show digest); stale-brief + failed-run nudges. Resume
   actions deferred (Plan C).
7. **Interview-vs-import fork** — after workspace creation, offer "interview, or import a brief?";
   the import path validates the prose is usable (Summary + Must-haves present; prose not a 0–100
   rubric; offer enrich questions if thin) before writing `preferences.md`.
8. **Clone-from-source** — the repo root IS the plugin. Golden path = marketplace install. From source:
   `claude --plugin-dir <clone>` or add the clone as a local marketplace; loose-skills via `build.sh`
   + copy/symlink into `~/.claude/skills/`. (Verify the `~/.claude/skills/<plugindir>` auto-load claim
   in Plan D.)
9. **Dev-install migration / never-clobber** — discovery order registry → `~/.job-search/` → legacy
   `~/job-search/`; adopt an existing legacy workspace (write registry; never overwrite existing files;
   only additively create missing `runs/`/`reports/`). After plugin install, detect the dev symlinks
   (`~/.claude/skills/{evaluate-job-fit,job-search-run}`) and *tell* the user they can remove them —
   never auto-remove.

## New contracts

### Registry (OS state) — `~/.config/job-search-os/config.json`
```json
{ "version": 1,
  "active_workspace": "/Users/<u>/.job-search",
  "scheduling": { "installed": true, "mechanism": "cron|launchd|loop", "set_at": "<iso>" } }
```
XDG location; falls back to `~/.job-search-os/config.json` when `~/.config` is unavailable. JSON only
(stdlib). The registry holds machine-managed OS state; the workspace's `config.yaml` stays the
user-facing config.

### `scripts/osctl.py` (dependency-free, stdlib only)
- `resolve` → JSON `{ "workspace": "<abs>", "first_run": <bool>, "source": "registry|default|legacy|none" }`.
  Discovery: registry `active_workspace` → `~/.job-search/` → legacy `~/job-search/`; first-run when no
  workspace has a `config.yaml`.
- `register --workspace PATH` / `set-active --workspace PATH` → create/update the registry (XDG +
  fallback); never clobber workspace data; create the registry dir as needed.
- `schedule-line --frequency F --time T [--timezone TZ]` → emit the cron line for the chosen frequency
  (e.g. daily→`0 8 * * *`, hourly→`0 * * * *`); also emit a launchd plist on request.
- `schedule-status` → read the marker; `set-scheduled --mechanism M` → record it.

`config.yaml` mutations are **model-driven** (the model edits YAML via Edit following `internals.md`
recipes), because stdlib has no YAML parser and we keep the dependency-free constraint. `osctl.py`
deliberately owns only JSON/registry/scheduling/filesystem.

### `shared/references/internals.md` (the OS manual; synced into each skill by `build.sh`)
Documents: registry schema + location, the discovery algorithm, first-run detection, never-clobber
adoption rules, safe `config.yaml` read/update recipes (validate `version`; allowed `frequency`
values; preserve structure), and scheduling-setup knowledge (the original spec's exact cron/launchd/
loop copy + the macOS "must be awake" caveat + consent + marker).

### New / updated named errors (in `errors.md`)
- **E-NO-AGENT-DATA** *(new)* — the `agent-data` CLI is not installed (prereq check fails before
  `whoami`). Message names the install fix. (Complements the existing `E-NO-AUTH`.)
- Existing `E-NO-CONFIG` fix copy updates from "Run `/job-search-setup`" to "Run `/job-search`" (the
  orchestrator is now the single front door).

## New / changed components
- **New skills:** `job-search` (orchestrator/shell), `job-preference-interview` (prose-only refactor of
  `~/cookbooks/job-preference-interview.md`; drops the 0–100 rubric).
- **New script + tests:** `scripts/osctl.py`, `tests/test_osctl.py` (TDD, like `state.py`).
- **New references:** `shared/references/internals.md`; orchestrator `references/onboarding.md` +
  `references/home.md`.
- **Edited skills:** `job-search-run` and `evaluate-job-fit` resolve the workspace via `osctl.py resolve`
  (with `--workspace` override); the run skill stays headless/non-interactive.
- **Packaging (Plan D):** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, full README,
  `examples/sample-digest.md` + `examples/sample-preferences.md`, CONTRIBUTING + versioning notes.

## Acceptance criteria
- From a clean machine, `/job-search` walks prereqs → brief → queries + frequency → first real matches
  → schedule, entirely by dialogue, and **persists** the workspace + registry so the next session
  recognizes the user.
- A returning `/job-search` shows status + actions; config changes are all doable by chatting.
- A scheduled headless run uses the registry, never prompts, exits non-zero when blocked.
- No numeric scores/weights; no credit/budget knobs; every blocked path is a named `E-*` with a fix.
- Installs as a plugin (one step) **and** works from a clone; `claude plugin validate . --strict`
  passes; onboarding-flow evals spend zero real credits (fake-agent-data shim).
- TTFV < ~5 min (honest about live LinkedIn latency); the user's real `~/job-search/` / `~/.job-search/`
  are never clobbered.
