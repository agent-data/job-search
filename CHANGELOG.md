# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] — 2026-07-31

### Changed
- **All five skills rewritten onto a two-skill shared core.** The mechanics live in two skills of
  their own: `job-search-runbook` (find the workspace, what each file holds, one run start to close,
  running it unattended, scratch, what stays off disk) and `agent-data-reference` (the CLI, the four
  sources and their quirks, retries, what a call costs). Each of those five invokes whichever of
  the two it needs and nothing outside them, so a first run reaches live postings after a much
  shorter read: the whole agent-facing corpus — all seven `SKILL.md` files — is 9,096 words
  (`wc -w skills/*/SKILL.md`).
- **Every runtime file lives inside the skill that owns it.** `shared/` is gone: the two references
  became the skills above, and the two mechanics scripts more than one skill runs —
  `workspace-discovery.sh` and `validate-workspace.sh` — moved into
  `skills/job-search-runbook/scripts/`. A skill needing the mechanics invokes the skill holding them
  by name; a skill needing a file another skill owns names it as
  `skills/<skill>/<dir>/<file>`.
- **The run contract is a marker plus a record.** A run creates the empty marker
  `runs/.started-<run_id>` when it opens and deletes it at close, after writing
  `runs/<run_id>.json` and `reports/<date>-digest.md`. The record carries `close_state`
  (`complete` | `blocked` | `interrupted`) and `run_health` (`healthy` | `degraded`); its full
  shape is `skills/job-search-run/templates/run-record.example.json`. A marker left behind means the
  previous run died
  mid-flight: the next run says so, deletes the marker, and goes on.
- **Failures are graded on what the user reads, not on a code.** A run that cannot proceed still
  closes — a record with `close_state: blocked` and `run_health: degraded`, and a digest whose
  body says in plain words what stopped it and what fixes it. The `E-*` code catalogue that used
  to carry that wording is gone from every shipped file.
- **A `templates/` directory in each skill is the copyable contract.** `run-record.example.json` and
  `jobs-event.example.json` join `config.example.yaml`, `workspace.gitignore` and
  `preferences.example.md`, so the exact shape of every workspace file is a file you can read rather
  than prose in a skill. Each one sits in the `templates/` directory of the single skill that copies
  it — `skills/job-search/`, `skills/job-search-run/`, `skills/job-preference-interview/` — and the
  three scripts with one caller each moved the same way, into that skill's `scripts/`. A skill names
  its own file as `templates/<file>` or `scripts/<file>`, an address that needs no path arithmetic;
  the live evals measured both models mis-resolving the plugin-root-token and `../../…` forms those
  replace.
- **`skills/job-search-runbook/scripts/validate-workspace.sh` enforces the file rules.** Config keys,
  the brief's front matter, run-record fields and UTC timestamps, and — with
  `--post-close <run_id>` — that the run left no marker and no scratch directory behind.
- **Behavior is graded by live evals.** `evals/` holds `run_eval.py`, the fourteen kept behaviors
  B1–B14 in `behaviors.md`, six cases in `cases/`, and the pre-rewrite baseline numbers B14
  compares against. Runs spawn a real session against the live Job Postings API, so they are a
  local release gate; CI checks only that the case config is coherent.

### Removed
Two of these you will notice as a user:

- **The update banner is gone.** In 0.7.0 the home view told you when a newer plugin version had been
  published and gave you the command to get it. Nothing checks now
  (`git grep -niE "update available|newer version" -- skills/ README.md` returns nothing),
  because the check read the build stamp, which went with the build step. Until it comes
  back, get updates the way your host offers them — `/plugin` in Claude Code, `codex plugin add`, and
  so on, per the install section in the README. Tracked as `TODO-UPDATE-AVAILABLE` in
  `docs/exec-plans/tech-debt-tracker.md`.
- **"Create a support summary" is gone.** In 0.7.0 you could ask for a local, whitelist-only
  diagnostic file to attach to a bug report. To report a problem now, ask "why did my last run fail?"
  — the agent reads the run record and digest already on your machine and explains what happened —
  and paste that into the issue. The underlying files are `~/.job-search/runs/<run_id>.json` and
  `~/.job-search/reports/<date>-digest.md`; read them before pasting, since nothing filters them for
  you the way the old summary did.

The rest is internal. The legacy shared corpus and the machinery it defined: `conventions.md`,
`errors.md`, `internals.md`, `voice.md`, `parallelism.md`, `update.md`, `build-stamp.md`,
`agent-data-contract.md`, `run-lifecycle.md`, the four skill-local reference files, the
lifecycle-ledger and support-summary scripts, and the build stamp with its generator
(`scripts/build.sh`, `scripts/build_stamp.py`). 27 files were deleted since 0.7.0
(`git diff -M30% --diff-filter=D --name-only 257fa2f..HEAD | wc -l`). The rename threshold is
lowered from git's default 50% so that `dedup.sh` — which moved into `skills/job-search-run/`
and grew a `--near` mode in the same release, leaving it 48% similar — counts as moved rather
than deleted.

### Compatibility
- **Existing workspaces keep working, unchanged.** `config.yaml` stays at `version: 2`; the
  required keys are still `version`, `queries`, `search.sources`, and `schedule`.
- A run no longer writes the lifecycle ledger `runs/.lifecycle-<run_id>.jsonl` or the binding file
  `runs/detail-model-binding.json`, and it no longer reads either one. A workspace that still holds
  them from an earlier version is left alone — nothing reads them, nothing deletes them; remove
  them by hand if you want them gone. (`metrics.json` was specified but never written by any
  shipped file, so no workspace has one to leave behind.)
- `search.detail_model` is no longer written or read. A workspace that still carries it is valid;
  the key is simply ignored, and every detail read runs on the host's own model.

## [0.7.0] — 2026-07-23

### Added
- **Hermes Agent support.** Job Search installs on Hermes Agent with
  `hermes plugins install agent-data/job-search --enable`, through a root-level Hermes adapter:
  `plugin.yaml`, `__init__.py` (verifies the installed tree, then registers the five skills under
  `job-search:<name>` fallback names), `after-install.md`, and the agent-facing
  `INSTALL_FOR_HERMES.md` guide, which makes the skills discoverable by their normal names via
  `skills.external_dirs` and verifies the install end to end. The README gains a Hermes Agent
  install section and the support matrix now lists Hermes Agent. Structurally verified; every
  guide claim is cited against hermes-agent v0.19.0 source.
- Release integrity now version-syncs the Hermes `plugin.yaml` alongside the six JSON manifests.

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
