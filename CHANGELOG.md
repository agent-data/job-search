# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Multi-source job search.** `search.sources` selects the job sources each query runs against
  (`linkedin`, `ashby`, plus experimental `workday`); searches fan out per query × source with
  per-source circuit breakers, composite (source, source_id) dedup, and honest handling of
  Ashby's undated postings (a JD-stated date is extracted during the detail read). Digests
  carry per-source counts and source tags. Two new named errors (E-SOURCE-UNSUPPORTED,
  E-SOURCE-IGNORED) cover unknown sources and legacy servers that ignore source selection.
- Multi-source test surface: fake-shim `--source` support, per-source fixtures, and four new
  scenarios (multi-source, one-source-down, source-unsupported, legacy-source-swallow).
- Workday is available as an explicit opt-in experimental source (`search.sources: [..., "workday"]`); a failing source degrades the run to `partial`, never blocks it.

### Fixed
- CI actually runs the unit-test gate (pytest was never installed on the runner).
- `search-jobs` limit default corrected to the API's real value (20) in the run skill and
  conventions; the config template still sets 25 explicitly.

## [0.3.0] — 2026-06-15

First public release.

### Changed
- **Zero-Python shipped surface.** Removed every Python artifact that previously shipped to user
  machines (the bundled `osctl.py` / `state.py` and the scheduling guard hook). Claude Code now
  executes the OS's state procedures natively from the pinned contracts in `shared/references/`.
  Nothing but Markdown ships — only Claude Code and the `agent-data` CLI are required at runtime.
- Plugin author set to the Aptiq Labs, Inc. legal entity (matching the LICENSE copyright holder).

### Added
- Public-release docs: a first-run walkthrough and an everyday-use phrasebook in the README, an
  honest supported-environments note, this `CHANGELOG`, a security policy
  (`.github/SECURITY.md`), and issue/pull-request templates.

### Fixed
- Loose-skill install instructions now include all five skills (the operator-manual skill
  `job-search-agent` was previously omitted).

### Notes
- Tested on Claude Code (CLI) on macOS/Linux. Scheduling uses Claude Code's native `/loop`.
