# job-search — Agent Map

An agent harness as a private, local-first **job-search** operating system: a plugin with five skills, a
single-source-of-truth `shared/references/` tree whose pinned contracts the host agent executes natively
(nothing ships to user machines but markdown), and a pytest + fake-shim + skill-creator eval harness.
**This file is the entry point for coding agents working on this repo** — a map, not the territory.
Start here, then follow the pointers.

## Start here
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — the five product domains × five layers and how they fit; read before any change.
- **[Core beliefs](docs/design-docs/core-beliefs.md)** — the agent-first operating principles; read before changing behavior.
- **[Runtime contracts](shared/references/)** — the SINGLE SOURCE OF TRUTH for errors, config, conventions, and the agent-data API. Docs here POINT to these; never duplicate them.

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
- **Single source of truth:** shared contracts live once in `shared/references/` and resolve in place from the installed pack bundle — skills point at them, nothing is copied per-skill. `./scripts/build.sh` only regenerates `shared/references/build-stamp.md`; the few `skills/*/references/*.md` are authored originals, not generated.
- Dev tooling is stdlib-only Python (nothing Python ships in the skills); scoped conventional commits; `python3 scripts/doc_lint.py --root .` and `python3 -m pytest -q` must be green before a PR.
- Daily contributor docs: [README](README.md) · [CONTRIBUTING](CONTRIBUTING.md) · [TESTING](TESTING.md)
