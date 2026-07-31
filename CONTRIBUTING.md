# Contributing to Job Search

Thanks for helping out. This project has a few hard rules that keep the codebase honest and the skills
self-contained — please read these before opening a PR.

> Coding agent, or want the map of this repo? Start with [AGENTS.md](AGENTS.md) — the agent-facing entry point.

## Single source of truth — shared references live once

The shared runtime contracts live **once** under **`shared/references/*.md`** and are the single source of
truth. The install lays down the whole pack tree, so each skill resolves them **in place** — skills point at
`../../shared/references/<file>.md`, and there are **no per-skill copies** to keep in sync.

There are exactly two of them, and between them they own everything a run does:

- **`runbook.md`** — find the workspace, what each file in it holds, how one run opens and closes, running
  it unattended, scratch, and what stays off disk.
- **`agent-data.md`** — the agent-data CLI, the four job sources and their quirks, retries, and what a
  call costs.

The exact *shape* of each workspace file is not prose in either one: it is a copyable example in
`templates/` — `config.example.yaml`, `run-record.example.json`, `jobs-event.example.json`,
`preferences.example.md`. Whether a workspace on disk obeys the file rules is decided by
`shared/scripts/mechanics/validate-workspace.sh`, not by a paragraph a skill has to restate.

**Edit the source:**

- Shared references live in **`shared/references/*.md`** (dev tooling lives in `scripts/` and `evals/` —
  the Python linters, the release-integrity check, and the eval runners; none of it ships in the skills).
- Edit the file in `shared/references/` and you're done — every skill sees the change, because they all
  resolve the same file.

Nothing is generated into `skills/` or `shared/`: there is no build step, and no file there is a copy of
another.

A skill's own `SKILL.md` and its `evals/` are **authored originals**, not generated — edit them in
place.

## Keep the agent-facing corpus under 10,000 words

The five `SKILL.md` files plus both references are what every run reads before it can do anything, so their
combined length is a product cost, not a style question. Measure before and after any change to them:

```bash
wc -w skills/*/SKILL.md shared/references/*.md   # 8,822 total as of 0.8.0; the budget is 10,000
```

If a change needs more words there, cut somewhere else in the same PR. Detail that only a contributor needs
belongs in this repo's docs, which no run reads.

## Before you open a PR: everything must be green

Run all of these and make sure they pass:

```bash
# 1) Unit tests — the doc linter, the philosophy guard, the release-integrity checks, the
#    mechanics scripts, validate-workspace.sh, the eval-case lint, and the shims. No API calls.
python3 -m pytest -q

# 2) Doc-lint (knowledge base) + philosophy guard (shipped output) — both run in CI too
python3 scripts/doc_lint.py --root .
python3 scripts/philosophy_guard.py --root .

# 3) The per-skill scenario suites are well formed
python3 scripts/eval_harness.py --root .
```

Those four are what CI runs, and they must be green before you open a PR.

**Two eval layers sit on top, and neither runs in CI.** Per-skill scenarios live in
`skills/<skill>/evals/evals.json`, with a `harness` block describing setup; drive them by asking Claude in a
Claude Code session ("run the evals for job-search-run"), which invokes the skill-creator skill against that
file. They are **credit-free** — every `agent-data` call goes through the fake shim in `tests/`, so nothing
is billed. Keep them that way: if you add a skill or a code path that talks to `agent-data`, route the
scenario through the shim rather than the live CLI.

The **live behavior evals** in `evals/` are the release gate. `evals/behaviors.md` maps the fourteen kept
behaviors B1–B14 onto the six cases in `evals/cases/`, and each case runs on two models:

```bash
python3 evals/run_eval.py --case fit --model sonnet
```

Each run spawns a real session against the live Job Postings API, so it needs your API key and spends
metered calls — that is why CI only checks that the case config is coherent (`tests/test_eval_cases.py`).
Run the full matrix before tagging a release; TESTING.md § Behavior evals has the details.

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

CI runs that check on every change, and on a pull request it also fails when `skills/`,
`shared/references/`, or `shared/scripts/` changed without a forward bump.

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
guard scans shipped default output (`examples/`, `templates/`). Note: a numeric score a
user *explicitly asks for* is fine in chat — it just must never be written into a digest,
brief, `config.yaml`, or `jobs.jsonl`. Keep them intact:

- **Qualitative relevance, never numeric.** Postings are *relevant or not*, and if relevant *weak / moderate
  / strong*, with reasoning. No 0–100 fit scores, no category weights, no per-criterion points. Importance
  lives in which bucket a preference sits in.
- **Usage context, not budget controls.** Users choose outcomes — frequency, sources, and review depth — and
  see exact usage context before added metered work plus actual calls after each run. Accurate calls-first
  context is expected; a `budget`, `credits`, or `cost` config field, hard monetary cap, or invented actual
  charge is not. Pricing and metering facts live only in `shared/references/agent-data.md`.
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
