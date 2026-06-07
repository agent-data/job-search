---
title: Plan D — Packaging & Dual Distribution
state: completed
created: 2026-06-05
completed: 2026-06-07
---

# Job Search OS — Plan D: Packaging & dual-distribution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the repo as an installable Claude Code plugin (one step → `/job-search` → onboarded) that ALSO works from a clone, with docs-as-product quality and real examples — verified end-to-end with a tiny live smoke test that never touches the user's real data.

**Architecture:** The repo root IS the plugin: a `.claude-plugin/plugin.json` manifest + auto-discovered top-level `skills/` (made self-contained by `build.sh`, which bundles `shared/references/*` + `state.py`/`osctl.py` into each skill). A `.claude-plugin/marketplace.json` lists this one plugin (source `.`) for marketplace install. From a clone, `claude --plugin-dir <repo>` or a local marketplace add loads the same files. Skills resolve bundled files from their own dir (`${CLAUDE_SKILL_DIR}/...`), which is why no `../` traversal is needed (plugins are copied, not linked).

**Tech Stack:** Claude Code plugin/marketplace manifests (JSON), `claude plugin validate`, `claude --plugin-dir`; the existing skills/scripts/templates; agent-data CLI (live smoke only).

**Prerequisite:** Plan B is complete and committed (all four skills exist, full pytest + all evals green). This plan assumes the current Claude Code plugin format verified on 2026-06-05 (see the spec-delta) — re-confirm with `claude --version` and `claude plugin validate` before relying on any field; flag anything that differs.

---

## File Structure

**Create:**
- `.claude-plugin/plugin.json` — the plugin manifest.
- `.claude-plugin/marketplace.json` — single-plugin marketplace (source `.`).
- `examples/sample-digest.md`, `examples/sample-preferences.md` — real, score-free examples.
- `CONTRIBUTING.md` — edit `shared/`+`scripts/` then `build.sh`; run pytest + evals.
- (Maybe) `commands/job-search.md` — only if verification shows it yields a cleaner `/job-search` trigger.

**Modify:**
- `README.md` — replace the interim quick-start with the docs-as-product README.

---

## Setup: branch

- [ ] **Step 1: Branch from the completed Plan B state**

```bash
cd ~/job-search-os && git checkout -b plan-d-packaging && python3 -m pytest -q && git status --short --branch
```
Expected: tests green; `## plan-d-packaging`.

---

## Task D1: Plugin manifest + validation + clean trigger [packaging]

**Files:** Create `.claude-plugin/plugin.json`

- [ ] **Step 1: Write `.claude-plugin/plugin.json`**

```json
{
  "name": "job-search-os",
  "version": "0.1.0",
  "description": "Claude Code as a job-search OS: a private, local-first workspace that pulls postings, judges each one's relevance against your prose preferences (qualitative — no scores), and digests the matches on a schedule you control. Run /job-search to onboard end-to-end.",
  "author": { "name": "agent-data" },
  "homepage": "https://github.com/agent-data/job-search-os",
  "repository": "https://github.com/agent-data/job-search-os",
  "license": "MIT",
  "keywords": ["job-search", "career", "agent-data", "linkedin", "skills", "automation"]
}
```
(Published under the agent-data org: `https://github.com/agent-data/job-search-os` — an open-source, ready-to-use plugin for the agent-data Job Postings endpoint.)

- [ ] **Step 2: Validate the manifest + skill auto-discovery**

```bash
cd ~/job-search-os && claude plugin validate . --strict
```
Expected: passes; reports the four skills discovered from `skills/` (`job-search`, `job-preference-interview`, `job-search-run`, `evaluate-job-fit`). If it fails on a field, fix per the validator's message (the format may have moved since 2026-06-05).

- [ ] **Step 3: Load locally and verify triggers (empirical, no assumptions)**

```bash
cd ~/job-search-os && ./scripts/build.sh   # ensure bundled copies are current
claude --plugin-dir . -p "/help" 2>&1 | grep -i "job-search" || true
```
Then in an interactive `claude --plugin-dir .` session, confirm: (a) the orchestrator is invocable (note the EXACT string — `/job-search` vs the namespaced `/job-search-os:job-search`); (b) natural language ("set up job search") triggers it via the description. Record the real trigger string for the README.

- [ ] **Step 4: (Conditional) add a clean-`/job-search` forwarder.** ONLY if Step 3 shows the bare `/job-search` does not resolve and a cleaner trigger is wanted, create `commands/job-search.md`:

```markdown
---
description: Front door for Job Search OS — onboard on first run, or show your job-search home.
---
Invoke the `job-search` skill (the orchestrator). Follow its routing: first-run → onboarding; otherwise → home.
```
Re-run `claude plugin validate . --strict` and re-verify. If the bare form already works, skip this step and note it.

- [ ] **Step 5: Verify bundled-script resolution in plugin mode.** In the `--plugin-dir .` session, confirm a skill can run its bundled `scripts/osctl.py` (e.g. trigger the orchestrator's Step 0 resolve in a temp sandbox: export `JOBSEARCH_OS_REGISTRY`/`JOBSEARCH_OS_HOME` to a tmp dir first). Confirm it finds `${CLAUDE_SKILL_DIR}/scripts/osctl.py` without a `../` path.

- [ ] **Step 6: Commit**

```bash
git add .claude-plugin/plugin.json commands 2>/dev/null; git add .claude-plugin/plugin.json
git commit -m "feat(packaging): add plugin.json; verify skills auto-discover and /job-search triggers"
```

## Task D2: Marketplace manifest + dual-distribution verification [packaging]

**Files:** Create `.claude-plugin/marketplace.json`

- [ ] **Step 1: Write `.claude-plugin/marketplace.json`**

```json
{
  "name": "agent-data",
  "owner": { "name": "agent-data" },
  "description": "Job Search OS — Claude Code as your job-search operating system.",
  "plugins": [
    {
      "name": "job-search-os",
      "source": ".",
      "description": "Onboard with /job-search; qualitative relevance, frequency-not-budget, private local workspace.",
      "category": "productivity"
    }
  ]
}
```

- [ ] **Step 2: Validate the marketplace**

```bash
cd ~/job-search-os && claude plugin validate . --strict
```
Expected: marketplace + plugin both validate. (If the validator wants the marketplace in a separate root or a different `source` form for a self-referential single-plugin repo, adjust per its message and note the working form.)

- [ ] **Step 3: Verify install path A — local marketplace add + install** (in a throwaway check)

```bash
# In an interactive claude session:
#   /plugin marketplace add ~/job-search-os
#   /plugin install job-search-os@agent-data
#   confirm /job-search (or the namespaced form) is available, then /plugin uninstall to clean up
```
Record the exact add/install commands that work for the README.

- [ ] **Step 4: Verify install path B — loose-skills from a clone**

```bash
cd ~/job-search-os && ./scripts/build.sh
# A user who clones can copy/symlink each self-contained skill:
#   for s in job-search job-preference-interview job-search-run evaluate-job-fit; do
#     ln -s ~/job-search-os/skills/$s ~/.claude/skills/$s ; done
# Confirm the skills load and the bundled scripts/references resolve (they are self-contained after build.sh).
```
Also confirm `claude --plugin-dir ~/job-search-os` (session-only) loads everything. Note in the README which clone path is recommended and flag (for the user) whether cloning the whole repo into `~/.claude/skills/<dir>` auto-loads as a plugin on this Claude Code version (verify; don't assume).

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/marketplace.json
git commit -m "feat(packaging): marketplace.json; verify plugin + loose-skills + --plugin-dir install paths"
```

## Task D3: Docs-as-product README + examples + CONTRIBUTING [docs]

**Files:** Modify `README.md`; Create `examples/sample-digest.md`, `examples/sample-preferences.md`, `CONTRIBUTING.md`

- [ ] **Step 1: Create `examples/sample-preferences.md`** — a realistic prose brief (Summary, Must-haves/dealbreakers, Strong preferences, Nice-to-haves, Red flags, `created_at`). Reuse the shape of `templates/preferences.example.md`. **No numeric scoring.**

- [ ] **Step 2: Create `examples/sample-digest.md`** — a realistic digest in the exact `conventions.md` format: the `# Job search digest — <date>` header, a `Run health: healthy` line, the counts line, then Strong / Moderate / Weak sections with one-line qualitative reasoning + `[view]` links and a `⚠ confirm:` note, then `Filtered out (not relevant): N`, then footnotes. **No scores, no credit figures.**

- [ ] **Step 3: Rewrite `README.md`** with these sections in this order:
  1. **Title + one-liner + the promise** — "Within ~5 minutes of install, see real jobs judged against your stated preferences; then keep getting them on a schedule you control."
  2. **Requirements** — Claude Code; the `agent-data` CLI (authenticated: `agent-data whoami` shows `api_key_set: true`); Python 3.9+.
  3. **Install (golden path — plugin):** the exact, verified commands from D2 Step 3, e.g. `/plugin marketplace add agent-data/job-search-os` → `/plugin install job-search-os@agent-data` → then `/job-search` (use the trigger string verified in D1 Step 3). "Then just say `/job-search` — Claude sets up everything by asking you a few questions."
  4. **Install (from source):** `git clone … && claude --plugin-dir ./job-search-os` (session) or add the clone as a local marketplace; the loose-skills `build.sh` + symlink path from D2 Step 4.
  5. **What it does** — qualitative relevance (relevant/not + weak/moderate/strong, with reasoning; **no scores/weights**); you control **frequency, not budget**; private local workspace.
  6. **Cost, honestly** — plain language: `search`/`docs`/`status`/`whoami` are free; only `search-jobs`/`get-posting` are metered; the system stays frugal by behavior (judge from the free summary, read full details only for promising matches, dedup). If the API limit is hit you'll see a plain-language note (the `E-QUOTA` copy) suggesting a lower frequency or a plan upgrade — **never credit math you have to reason about.**
  7. **Privacy** — the workspace (default `~/.job-search/`) is private PII with a deny-all `.gitignore`, never committed; no personal data in this repo.
  8. **Troubleshooting** — paste the named-error table verbatim from `shared/references/errors.md` (E-NO-AGENT-DATA, E-NO-AUTH, E-NO-CONFIG, E-NO-PREFERENCES, E-SERVICE-DOWN, E-BAD-QUERY, E-UPSTREAM-STRETCH, E-QUOTA, E-CONFIG-VERSION) — each row already names the fix.
  9. **A real digest** — embed/link `examples/sample-digest.md` so people see output before installing.
  10. **Roadmap** — resume compare/tailor (Plan C) is coming; this release covers discovery + relevance + scheduling.

- [ ] **Step 4: Create `CONTRIBUTING.md`** — the single-source rule: edit `shared/references/*` and `scripts/*`, then run `./scripts/build.sh` (never hand-edit a skill's synced `references/`/`scripts/`); run `python3 -m pytest -q` and the skill-creator evals before a PR; commit message conventions (`feat/test/docs/fix(scope):`). Note versioning: bump `version` in `.claude-plugin/plugin.json` on each release (semver) or users won't get updates.

- [ ] **Step 5: Commit**

```bash
git add README.md examples/ CONTRIBUTING.md
git commit -m "docs(packaging): docs-as-product README + real examples + CONTRIBUTING/versioning"
```

## Task D4: Final verification — full suite, validation, dual-install, live smoke [verify]

- [ ] **Step 1: Build + full unit suite + all evals**

```bash
cd ~/job-search-os && ./scripts/build.sh && python3 -m pytest -q
```
Expected: all green. Then run all four skills' evals via skill-creator (zero real credits) and confirm green.

- [ ] **Step 2: Packaging validation + dual-install smoke (zero credits)**

```bash
cd ~/job-search-os && claude plugin validate . --strict
```
Confirm `claude --plugin-dir .` loads all four skills and the orchestrator triggers (per D1/D2 notes).

- [ ] **Step 3: Tiny LIVE smoke test (≤3 metered calls; temp workspace only — real data untouched)**

```bash
cd ~/job-search-os
SMOKE=$(mktemp -d)
export JOBSEARCH_OS_REGISTRY="$SMOKE/registry.json" JOBSEARCH_OS_HOME="$SMOKE"
mkdir -p "$SMOKE/.job-search/runs" "$SMOKE/.job-search/reports"
cp templates/config.example.yaml    "$SMOKE/.job-search/config.yaml"
cp templates/preferences.example.md "$SMOKE/.job-search/preferences.md"
cp templates/workspace.gitignore    "$SMOKE/.job-search/.gitignore"
: > "$SMOKE/.job-search/jobs.jsonl"
python3 scripts/osctl.py set-active --workspace "$SMOKE/.job-search"
# Edit config.yaml to a SINGLE enabled query, limit 3 (cheap): keep only the first query, set limit: 3.
agent-data whoami   # confirm authed (free)
claude -p "/job-search-run --workspace $SMOKE/.job-search"   # 1 search (limit 3) + ≤2 detail reads ≈ ≤3 metered calls
cat "$SMOKE/.job-search/reports/"*-digest.md
```
Expected: a real digest with `Run health: healthy`, at least one relevance-judged posting, `jobs.jsonl` gaining `evaluated` events; **no numeric scores, no credit/dollar figures**. Verify the real `~/.job-search/` and `~/job-search/` were NOT touched (we redirected via `JOBSEARCH_OS_*` and passed `--workspace`). Clean up: `rm -rf "$SMOKE"`.

- [ ] **Step 4: Migration note for the user's machine.** Document (don't auto-run): once the plugin is installed, the dev symlinks `~/.claude/skills/{evaluate-job-fit,job-search-run}` can be removed (`rm …`) to avoid double-loading; the existing `~/job-search/` test workspace is auto-adopted by onboarding (never clobbered).

- [ ] **Step 5: Finish the branch.** Invoke `superpowers:finishing-a-development-branch`; run the full suite once more; present merge/PR options. Then ask the user about publishing (push to a public remote, set the real repo slug in the manifests).

---

## Self-Review (run after writing; fix inline)

**Spec coverage (handoff §5 + spec-delta):** plugin manifest verified against current format (D1) ✓; dual distribution plugin + clone + loose-skills (D2) ✓; docs-as-product README with golden path, cost honesty, privacy, named-error table, real sample (D3) ✓; examples score-free (D3) ✓; versioning flow (D3/CONTRIBUTING) ✓; final full-suite + packaging validation + ≤3-call live smoke that never clobbers real data (D4) ✓; dev-install migration documented (D4) ✓.

**Placeholder scan:** manifests are complete JSON; README/examples/CONTRIBUTING specified section-by-section with exact commands and the verbatim error table source; the only conditional is the `commands/` forwarder (gated on the empirical D1 trigger check) and the repo slug (confirm with user). No TBD/TODO.

**Type/name consistency:** plugin name `job-search-os`; skills `job-search | job-preference-interview | job-search-run | evaluate-job-fit`; marketplace `source: "."`; live smoke uses the same `JOBSEARCH_OS_REGISTRY`/`JOBSEARCH_OS_HOME` envs and `osctl.py set-active` as Plan B's internals; default workspace `~/.job-search/`. All consistent with the Plan B plan and the spec-delta.
