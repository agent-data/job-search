# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] — 2026-07-15

### Added
- **Opt-in deeper company-board coverage.** Ask to review up to a positive number of unseen roles or to
  exhaust the currently traversable Ashby, Greenhouse, and Lever results once or on every run. Enabling or
  increasing depth previews the known call impact and confirms the exact one-off or saved scope first;
  omitting `search.max_new_postings_per_run` remains first-page-only, and LinkedIn remains first-page-only
  in every mode.
- **Calls-first usage context.** Run records retain actual metered-call totals and operation breakdowns;
  digests and summaries lead with the actual total, and read-only explanations expose the stored breakdown
  before any clearly labeled pay-as-you-go equivalent. No monetary budget control or invented account charge
  is added.
- **Named depth and accounting errors.** `E-BAD-CONFIG` blocks invalid review-depth values before metered
  work, `E-PAGINATION-INCOMPLETE` keeps trustworthy rows when continuation stops early, and `E-QUOTA`
  reports the run's actual prior metered calls while treating the rejected attempt as unmetered.
- **Local one-time deeper-coverage nudge.** A returning home view can offer deeper company-board coverage
  after local evidence shows zero unseen first-page roles while more board results exist; its per-workspace
  outcome is recorded locally so the offer does not repeat.

### Compatibility
- No config migration is required: `config.yaml` stays at `version: 1`, existing workspaces keep their
  schedules and first-page-only behavior when the optional depth key is absent, and LinkedIn remains
  first-page-only.

## [0.5.0] — 2026-07-14

### Added
- **Server-side recency filtering.** The `search.freshness` window now resolves to the job API's
  `published_on_or_after` parameter — an inclusive `YYYY-MM-DD` cutoff the service applies **as part of
  the search** — so a windowed pull returns a full page of genuinely-recent postings instead of
  over-fetching and discarding stale rows client-side. Freshness filters on each posting's **effective
  publication date** (the later of the new `published_at` field and `posted_at`), which fixes the prior
  blind spot where undated Ashby postings always passed the window. The runner echo-verifies the
  parameter and falls back to a client-side filter on deployments that predate it.
- **Ad-hoc recency windows.** Beyond the saved `search.freshness` default, you can ask for any one-off
  window in the moment — "only postings published in the past day", "since June 1" — and that single
  search uses it, no config edit.

### Changed
- Freshness null handling moved to **server parity**: under an active window a posting with no known
  publication date is excluded (the API omits it); `any` keeps everything, unchanged.

## [0.4.0] — 2026-07-13

### Added
- **Multi-source job search.** `search.sources` selects the job sources each query runs against
  (`linkedin`, `ashby`, `greenhouse`, `lever`); searches fan out per query × source with
  per-source circuit breakers, composite (source, source_id) dedup, and honest handling of
  Ashby's undated postings (a JD-stated date is extracted during the detail read). Digests
  carry per-source counts and source tags. Two new named errors (E-SOURCE-UNSUPPORTED,
  E-SOURCE-IGNORED) cover unknown sources and legacy servers that ignore source selection.
- Multi-source test surface: fake-shim `--source` support, per-source fixtures, and four new
  scenarios (multi-source, one-source-down, source-unsupported, legacy-source-swallow).
- **Update banners.** Claude Code and Codex sessions surface a non-blocking banner when a newer
  plugin version is available, so users pick up updates without checking by hand.

### Changed
- **Per-host adapter layer removed.** Deleted the per-host adapter docs
  (`shared/references/platform/*.md`) and `scripts/validate_platforms.py`. Model tier and
  host-primitive binding are now by **self-selection**: each host resolves its own tools,
  scheduler, and a concrete model at the named tier (`fast | balanced | high | inherit`) at run
  time and verifies the result, rather than looking up a host-specific recipe — there is no
  adapter table and no tier→id resolver.
- **References single-homed.** The shared runtime contracts live **once** under
  `shared/references/` and resolve **in place** from each installed skill (skills point at
  `../../shared/references/<file>.md`); there are no per-skill bundled copies and no fan-out/sync
  build step. Single-home resolution is verified by `tests/test_reference_resolution.py`.
- **Deterministic build stamp.** `scripts/build.sh` is now stamp-only: it regenerates
  `shared/references/build-stamp.md` deterministically and copies nothing into the skills.
- **Scheduling is unattended-first.** The advocated default is an **unattended wall-clock
  schedule** (`cron`/`launchd` where the host has one), with the in-session `/loop` as the named
  fallback. A **mandatory config-time canary** proves the schedule actually fires before it is
  recorded active in the registry.
- **Job sources:** added **Greenhouse** and **Lever**; **removed Workday** (dropped upstream —
  now a hard 400 `validation_error`); wire error codes reconciled to `validation_error` /
  `503 upstream_unavailable`; cross-source merge generalized to N board sources.

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
