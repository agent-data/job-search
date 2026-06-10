# job-search-os — Agent Map

Claude Code as a private, local-first **job-search OS**: a plugin with five skills, a deterministic
stdlib Python core, a single-source-of-truth `shared/references/` tree, a consent hook, and a
pytest + fake-shim + skill-creator eval harness. **This file is the entry point for coding agents
working on this repo** — a map, not the territory. Start here, then follow the pointers.

## Start here
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — the five product domains × five layers and how they fit.
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
- **Single source of truth:** edit `shared/references/` + `scripts/`, then run `./scripts/build.sh`; never hand-edit `skills/*/references` or `skills/*/scripts`.
- All prompts and docs are held to the [prompt & doc style guide](docs/design-docs/prompt-style-guide.md).
- Stdlib-only Python; scoped conventional commits; `python3 scripts/doc_lint.py --root .` and `python3 -m pytest -q` must be green before a PR.
- Daily contributor docs: [README](README.md) · [CONTRIBUTING](CONTRIBUTING.md) · [TESTING](TESTING.md)
