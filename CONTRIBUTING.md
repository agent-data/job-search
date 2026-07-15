# Contributing to Job Search

Thanks for helping out. This project has a few hard rules that keep the codebase honest and the skills
self-contained — please read these before opening a PR.

> Coding agent, or want the map of this repo? Start with [AGENTS.md](AGENTS.md) — the agent-facing entry point.

## Single source of truth — shared references live once

The shared runtime contracts live **once** under **`shared/references/*.md`** and are the single source of
truth. The install lays down the whole pack tree, so each skill resolves them **in place** — skills point at
`../../shared/references/<file>.md`, and there are **no per-skill copies** to keep in sync.

**Edit the source:**

- Shared references live in **`shared/references/*.md`** (dev tooling lives in `scripts/` — `build.sh` plus
  the Python linters; none of it ships in the skills).
- Edit the file in `shared/references/` and you're done — every skill sees the change, because they all
  resolve the same file.

`./scripts/build.sh` is **stamp-only**: it regenerates `shared/references/build-stamp.md` (the deterministic
build stamp) and nothing else. It does **not** copy or sync references into the skills.

A skill's own `SKILL.md`, its `evals/`, and the handful of authored playbooks under
`skills/<skill>/references/` (e.g. `home.md`, `onboarding.md`, `customization.md`,
`scheduling-and-consent.md`) are **authored originals**, not generated — edit them in place.

## Before you open a PR: everything must be green

Run all of these and make sure they pass:

```bash
# 1) Unit tests (the doc linter, the philosophy guard, the agent-data shim) — no real API calls
python3 -m pytest -q

# 2) Doc-lint (knowledge base) + philosophy guard (shipped output) — both run in CI too
python3 scripts/doc_lint.py --root .
python3 scripts/philosophy_guard.py --root .

# 3) Skill-creator evals — one suite per skill
#    (run each skill's evals under skills/<skill>/evals/)
```

Each skill's evals live in `skills/<skill>/evals/evals.json`, with a `harness` block describing setup; run
them by asking Claude in a Claude Code session (e.g. "run the evals for job-search-run"), which invokes the
skill-creator skill against that file.

The eval runs are **credit-free**: they go through the fake-`agent-data` shim in `tests/`, so no metered API
calls are made and nothing is billed. Keep them that way — if you add a skill or a code path that talks to
`agent-data`, route the eval through the shim rather than the live CLI.

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
fix(internals): pin the registry-wins rule in the discovery procedure
test(job-search-run): cover the E-QUOTA halt path
docs(packaging): docs-as-product README + real examples + CONTRIBUTING
```

Keep the subject in the imperative mood and under ~72 characters; put the *why* in the body if it isn't
obvious.

## Versioning — bump it every release

Releases are pulled by Claude Code from the plugin manifest. If you don't bump the version, **users won't get
your update.** On each release, bump `version` (semver) in:

```
.claude-plugin/plugin.json
```

- **patch** (`0.1.0 → 0.1.1`) — bug fixes, docs, internal refactors with no behavior change.
- **minor** (`0.1.0 → 0.2.0`) — new skills or user-visible features, backward compatible.
- **major** (`0.x → 1.0`, then `1.x → 2.x`) — breaking changes (notably to the `config.yaml` schema; see the
  `E-CONFIG-VERSION` named error, which fires when a workspace's `config.yaml` major is newer than the code).

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
  charge is not. Pricing and metering facts live only in `shared/references/agent-data-contract.md`.
- **Private and local.** The user workspace is private PII with a deny-all `.gitignore` and is never
  committed. No personal data belongs in this repo.
- **Every blocked path is a named error.** No silent failures: if something can't proceed, name the exact
  `E-*` from `shared/references/errors.md` with its cause + fix.

If a change would add a score, a weight, or a monetary budget control, it's almost certainly the wrong
direction — open an issue to discuss first. When a choice changes metered work, give accurate calls-first
context and point account-specific billing questions to the canonical agent-data sources instead of hiding
usage or inventing a charge.
