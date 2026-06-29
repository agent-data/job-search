# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Hermes (Nous Research) as a first-class host.** New adapter
  `shared/references/platform/hermes.md` mapping job-search to Hermes-native primitives — native
  `hermes cron` scheduling (deliver-to-chat), `delegate_task` parallel detail reads, `clarify`
  questions, and the headless `hermes chat -Q -s` run. All eight existing harnesses are unchanged.
- **Optional bundled stdlib-Python state-ops runtime** (`runtime/hermes_job_search/`, synced into the
  consuming skills by `build.sh`) that the Hermes adapter invokes via the `terminal` tool for the
  deterministic bookkeeping (workspace, registry, config, event-log fold, run-record, digest). Every
  other harness keeps executing those operations natively in-context (markdown-only); judgment stays
  in the model everywhere.

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
