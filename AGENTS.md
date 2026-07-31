# job-search — Agent Map

An agent harness as a private, local-first **job-search** operating system: a plugin with seven skills —
five a user reaches, and two the other five invoke for the mechanics — that the host agent reads and
executes natively (nothing ships to user machines but markdown), and three test layers — pytest over the dev tooling, per-skill scenario suites, and the live
behavior evals in `evals/`.
**This file is the entry point for coding agents working on this repo** — a map, not the territory.
Start here, then follow the pointers.

## Start here
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — the five product domains × five layers and how they fit; read before any change.
- **[Core beliefs](docs/design-docs/core-beliefs.md)** — the agent-first operating principles; read before changing behavior.
- **Runtime contracts** — two skills, and between them the single source of truth for everything a run does: [job-search-runbook](skills/job-search-runbook/SKILL.md) (the workspace, what each file holds, how one run opens and closes, what stays off disk) and [agent-data-reference](skills/agent-data-reference/SKILL.md) (the CLI, the four job sources, retries, what a call costs). Docs here POINT to these; never duplicate them. The exact shape of each workspace file is a copyable example in the `templates/` directory of the skill that writes it — [config.example.yaml](skills/job-search/templates/config.example.yaml) and [workspace.gitignore](skills/job-search/templates/workspace.gitignore) under job-search, [preferences.example.md](skills/job-preference-interview/templates/preferences.example.md) under job-preference-interview, [run-record.example.json](skills/job-search-run/templates/run-record.example.json) and [jobs-event.example.json](skills/job-search-run/templates/jobs-event.example.json) under job-search-run.

## Design & product
- [Design docs index](docs/design-docs/index.md) — catalogued specs with verification status.
- [Product specs index](docs/product-specs/index.md) — product flows (onboarding, …).
- [PRODUCT_SENSE](docs/PRODUCT_SENSE.md) — product philosophy and non-goals.

## Quality · reliability · security · interface
- [QUALITY_SCORE](docs/QUALITY_SCORE.md) — graded coverage per domain × layer.
- [RELIABILITY](docs/RELIABILITY.md) · [SECURITY](docs/SECURITY.md) · [INTERFACE](docs/INTERFACE.md)

## Plans & work
- [Plans methodology](docs/PLANS.md) · [Exec-plans index](docs/exec-plans/index.md)

## Working here
- **Single source of truth:** the shared contracts live once, in the `job-search-runbook` and `agent-data-reference` skills — the other five invoke them by name, nothing is copied per-skill and no build step writes into `skills/`.
- **Keep the agent-facing corpus small.** The seven `SKILL.md` files are 9,096 words (`wc -w skills/*/SKILL.md`); the budget is 10,000. Adding words there is a real cost — every run reads them.
- Dev tooling is stdlib-only Python (nothing Python ships in the skills); scoped conventional commits. CI runs four jobs (`.github/workflows/ci.yml`): `python3 -m pytest -q`, `python3 scripts/philosophy_guard.py --root .`, `python3 scripts/doc_lint.py --root .`, and `python3 scripts/check_release_integrity.py --root . --check-version-sync`. Run `python3 scripts/eval_harness.py --root .` too — it is not a CI job, so nothing else catches a malformed scenario file. See [CONTRIBUTING](CONTRIBUTING.md) for the full pre-PR list.
- Daily contributor docs: [README](README.md) · [CONTRIBUTING](CONTRIBUTING.md) · [TESTING](TESTING.md)
