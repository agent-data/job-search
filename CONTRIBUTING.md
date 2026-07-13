# Contributing to Job Search

Thanks for helping out. This project has a few hard rules that keep the codebase honest and the skills
self-contained — please read these before opening a PR.

> Coding agent, or want the map of this repo? Start with [AGENTS.md](AGENTS.md) — the agent-facing entry point.

## Single source of truth — never hand-edit a skill's synced copies

Each skill folder (`skills/<skill>/`) is shipped **self-contained**: it carries its own copy of the shared
references so it works as a loose skill with no plugin system. Those copies are **generated**, not authored.

**Edit the source, then build:**

- Shared references live in **`shared/references/*.md`** (dev tooling lives in `scripts/` — `build.sh` plus
  the Python linters; none of it ships in the skills).
- After editing a shared reference, run the build to re-sync every skill's bundled copies:

  ```bash
  ./scripts/build.sh
  ```

**Never hand-edit** the synced copies under `skills/<skill>/references/` — your changes there will be
silently overwritten by the next build. If you find yourself editing a file in that folder, stop and edit
the source in `shared/references/` instead, then re-run `build.sh` and commit the regenerated copies along
with the source change.

A skill's own `SKILL.md` and its `evals/` and `references/onboarding.md`-style playbooks *are* authored in
place — only the *synced* `references/*.md` are generated.

## Before you open a PR: everything must be green

All prompts and docs are held to [`docs/design-docs/prompt-style-guide/index.md`](docs/design-docs/prompt-style-guide/index.md).

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
- **Frequency, not budget.** Users tune *how often* the system runs — never a budget, never credits. Cost
  surfaces in exactly one place: the reactive `E-QUOTA` named error, whose fix is a lower frequency or a plan
  upgrade.
- **Private and local.** The user workspace is private PII with a deny-all `.gitignore` and is never
  committed. No personal data belongs in this repo.
- **Every blocked path is a named error.** No silent failures: if something can't proceed, name the exact
  `E-*` from `shared/references/errors.md` with its cause + fix.

If a change would add a score, a weight, a budget knob, or per-call cost surfaced to the user, it's almost
certainly the wrong direction — open an issue to discuss first.
