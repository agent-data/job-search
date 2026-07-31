# job-search — Agent Map

An agent harness as a private, local-first **job-search** operating system: a plugin with five skills, two
shared reference files the host agent reads and executes natively (nothing ships to user machines but
markdown), and three test layers — pytest over the dev tooling, per-skill scenario suites, and the live
behavior evals in `evals/`.
**This file is the entry point for coding agents working on this repo** — a map, not the territory.
Start here, then follow the pointers.

## Start here
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — the five product domains × five layers and how they fit; read before any change.
- **[Core beliefs](docs/design-docs/core-beliefs.md)** — the agent-first operating principles; read before changing behavior.
- **[Runtime contracts](shared/references/)** — two files, and between them the single source of truth for everything a run does: `runbook.md` (the workspace, what each file holds, how one run opens and closes, what stays off disk) and `agent-data.md` (the CLI, the four job sources, retries, what a call costs). Docs here POINT to these; never duplicate them. The exact shape of each workspace file is a copyable example in [templates/](templates/).

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
- **Single source of truth:** shared contracts live once in `shared/references/` and resolve in place from the installed pack bundle — skills point at them, nothing is copied per-skill and no build step writes into `skills/` or `shared/`.
- **Keep the agent-facing corpus small.** The five `SKILL.md` files plus both references are 8,822 words (`wc -w skills/*/SKILL.md shared/references/*.md`); the budget is 10,000. Adding words there is a real cost — every run reads them.
- Dev tooling is stdlib-only Python (nothing Python ships in the skills); scoped conventional commits. CI runs four jobs (`.github/workflows/ci.yml`): `python3 -m pytest -q`, `python3 scripts/philosophy_guard.py --root .`, `python3 scripts/doc_lint.py --root .`, and `python3 scripts/check_release_integrity.py --root . --check-version-sync`. Run `python3 scripts/eval_harness.py --root .` too — it is not a CI job, so nothing else catches a malformed scenario file. See [CONTRIBUTING](CONTRIBUTING.md) for the full pre-PR list.
- Daily contributor docs: [README](README.md) · [CONTRIBUTING](CONTRIBUTING.md) · [TESTING](TESTING.md)
