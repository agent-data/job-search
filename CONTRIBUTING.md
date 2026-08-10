# Contributing to Job Search

Thanks for helping out. This project has a few hard rules that keep the codebase honest and the skills
self-contained — please read these before opening a PR.

> Coding agent, or want the map of this repo? Start with [AGENTS.md](AGENTS.md) — the agent-facing entry point.

## Single source of truth — the two reference skills

The shared runtime contracts live **once**, as two skills of their own, and are the single source of
truth. The install lays down the whole pack tree, so any skill can invoke either by name, and there are
**no per-skill copies** to keep in sync.

There are exactly two of them, and between them they own everything a run does:

- **`job-search-runbook`** — find the workspace, what each file in it holds, how one run opens and closes,
  running it unattended, scratch, and what stays off disk. It also holds the two scripts more than one
  skill runs, at `skills/job-search-runbook/scripts/workspace-discovery.sh` and
  `skills/job-search-runbook/scripts/validate-workspace.sh`.
- **`agent-data-reference`** — the agent-data CLI, the four job sources and their quirks, retries, and
  what a call costs.

The exact *shape* of each workspace file is not prose in either one: it is a copyable example in the
`templates/` directory of the skill that writes it — `config.example.yaml` and
`workspace.gitignore` under `skills/job-search/`, `run-record.example.json` and
`jobs-event.example.json` under `skills/job-search-run/`, `preferences.example.md` under
`skills/job-preference-interview/`. Whether a workspace on disk obeys the file rules is decided by
`skills/job-search-runbook/scripts/validate-workspace.sh`, not by a paragraph a skill has to restate.

**Edit the source:**

- The two references live in **`skills/job-search-runbook/SKILL.md`** and
  **`skills/agent-data-reference/SKILL.md`** (dev tooling lives in `scripts/` — the Python linters,
  the release-integrity check, and the scenario-suite validator; none of it ships in the skills).
- Edit one of those two files and you're done — every skill that invokes that reference sees the
  change, because there is only one copy of it to edit.

Nothing is generated into `skills/`: there is no build step, and no file there is a copy of another.

A skill's own `SKILL.md` and its `evals/` are **authored originals**, not generated — edit them in
place.

## Keep the agent-facing corpus near 10,000 words

The seven `SKILL.md` files are what every run reads before it can do anything, so their
combined length is a product cost, not a style question. Measure before and after any change to them:

```bash
wc -w skills/*/SKILL.md   # 10,619 total on 2026-08-10
```

10,000 is the figure to aim at, not a gate: no check fails for going over it, and the corpus is over it
today. So a change that needs more words there is a judgment call — look for something to cut in the same
PR, and say in the PR why the words earn their place if you keep them. Detail that only a contributor needs
belongs in this repo's docs, which no run reads.

## Before you open a PR: everything must be green

Run all of these and make sure they pass:

```bash
# Unit tests — the doc linter, the philosophy guard, the release-integrity checks, the
# mechanics scripts, validate-workspace.sh, and the shims. No API calls.
python3 -m pytest -q

# Philosophy guard (shipped output) + doc-lint (knowledge base)
python3 scripts/philosophy_guard.py --root .
python3 scripts/doc_lint.py --root .

# The seven manifests agree on a version
python3 scripts/check_release_integrity.py --root . --check-version-sync

# The scenario suites the five user-facing skills ship are well formed (not a CI job — see below)
python3 scripts/eval_harness.py --root .
```

**Four of those five are the CI jobs**, in `.github/workflows/ci.yml`: `pytest`, the philosophy
guard, the doc linter, and release integrity (which on a pull request also fails when anything under
`skills/` changed without a forward version bump). `eval_harness.py`
is **not** wired into CI — `grep -rn "eval_harness" .github/` returns nothing — so run it yourself;
nothing else catches a malformed scenario file. All five must be green before you open a PR.

**Two eval layers sit on top, and neither runs in CI.** Scenario suites live in the five user-facing
skills, at `skills/<skill>/evals/evals.json`, with a `harness` block describing setup; drive them by asking Claude in a
Claude Code session ("run the evals for job-search-run"), which invokes the skill-creator skill against that
file. They are **credit-free** — every `agent-data` call goes through the fake shim in `tests/`, so nothing
is billed. Keep them that way: if you add a skill or a code path that talks to `agent-data`, route the
scenario through the shim rather than the live CLI.

Beyond those, the maintainer runs a set of live behavior evals against the real Job Postings API
before tagging a release. Each spawns a real session and spends metered calls, so they are not in
this repository and a contributor does not run them.

If a test or eval fails, fix it (or update it deliberately, explaining why in the PR) before requesting
review. Don't mark work complete on a red suite.

## Commit message conventions

Use Conventional-Commit-style prefixes with a scope:

```
feat(scope): …      # new behavior
fix(scope): …       # bug fix
test(scope): …      # tests / evals only
docs(scope): …      # docs only
```

Examples:

```
feat(job-search): add returning-user pipeline summary to home
fix(runbook): pin the registry-wins rule in workspace discovery
test(job-search-run): cover the exhausted-quota blocked close
docs(packaging): docs-as-product README + real examples + CONTRIBUTING
```

Keep the subject in the imperative mood and under ~72 characters; put the *why* in the body if it isn't
obvious.

## Versioning — bump it every release

Releases are pulled by Claude Code from the plugin manifest. If you don't bump the version, **users won't get
your update.** Seven manifests carry the version, one per supported host, and they must all say the same
thing: `.claude-plugin/plugin.json` (the primary), `.codex-plugin/plugin.json`,
`.cursor-plugin/plugin.json`, `.factory-plugin/plugin.json`, `gemini-extension.json`, `package.json`, and
`plugin.yaml`. Bump all seven, then check them:

```bash
python3 scripts/check_release_integrity.py --root . --check-version-sync
```

CI runs that check on every change, and on a pull request it also fails when anything under `skills/`
changed without a forward bump.

- **patch** (`0.1.0 → 0.1.1`) — bug fixes, docs, internal refactors with no behavior change.
- **minor** (`0.1.0 → 0.2.0`) — new skills or user-visible features, backward compatible.
- **major** (`0.x → 1.0`, then `1.x → 2.x`) — breaking changes. The one that would force this is a
  `config.yaml` schema change that an existing workspace cannot survive: `config.yaml` carries its own
  `version` key, separate from the plugin version, and every release note says plainly what an existing
  workspace has to do (usually nothing). Add a **Compatibility** section to the CHANGELOG entry whenever a
  release changes what is written into a workspace.

## Project philosophy (please don't regress these)

These are load-bearing design choices, enforced by `scripts/philosophy_guard.py` (run in CI via
`.github/workflows/ci.yml` and as `tests/test_philosophy_guard.py`) and in review. The
guard scans shipped default output (`examples/` plus every `skills/*/templates/` directory there is). Note: a numeric score a
user *explicitly asks for* is fine in chat — it just must never be written into a digest,
brief, `config.yaml`, or `jobs.jsonl`. Keep them intact:

- **Qualitative relevance, never numeric.** Postings are *relevant or not*, and if relevant *weak / moderate
  / strong*, with reasoning. No 0–100 fit scores, no category weights, no per-criterion points. Importance
  lives in which bucket a preference sits in.
- **Usage context, not budget controls.** Users choose outcomes — frequency, sources, and review depth — and
  see exact usage context before added metered work plus actual calls after each run. Accurate calls-first
  context is expected; a `budget`, `credits`, or `cost` config field, hard monetary cap, or invented actual
  charge is not. Pricing and metering facts live only in the `agent-data-reference` skill.
- **Private and local.** The user workspace is private PII with a deny-all `.gitignore` and is never
  committed. No personal data belongs in this repo.
- **Every blocked path is named.** No silent failures: if something can't proceed, say what stopped it and
  what fixes it, at the step that hit it, in the words a user would use. A run that stops still closes —
  a `runs/<run_id>.json` with `close_state: blocked` and `run_health: degraded`, and a digest whose body is
  the cause and the fix instead of a match list — because that record is what the home view reads next time.
  There is no error-code catalogue to look a message up in; write the sentence the user needs where the step
  fails.

If a change would add a score, a weight, or a monetary budget control, it's almost certainly the wrong
direction — open an issue to discuss first. When a choice changes metered work, give accurate calls-first
context and point account-specific billing questions to the canonical agent-data sources instead of hiding
usage or inventing a charge.
