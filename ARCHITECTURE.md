# Architecture

Job Search OS turns **Claude Code** into a private, local-first **job-search operating system**: a plugin
of five skills, a deterministic stdlib-Python core, a single-source-of-truth `shared/references/` tree, a
consent hook, and a pytest + fake-shim + eval harness. It searches LinkedIn postings through the agent-data
marketplace, judges each one qualitatively against your prose preferences brief, and writes human digests
into a workspace that never touches source control.

This doc is the **structural map**: the OS model, the five product **domains**, the five architectural
**layers**, and how packages depend on each other and data flows through a run. It is deliberately a map,
not the territory — the binding details live elsewhere and are linked, never restated. For the full design
specs see [docs/design-docs/index.md](docs/design-docs/index.md); the runtime contracts (errors, config,
conventions, the agent-data API, OS internals) are the single source of truth under
[shared/references/](shared/references/internals.md). Read [AGENTS.md](AGENTS.md) first for the agent-facing
entry point. Companion grading: [docs/QUALITY_SCORE.md](docs/QUALITY_SCORE.md) scores every domain × layer.

## The "OS" model

The product framing is an operating system whose userland is your job search:

| OS concept | In Job Search OS |
|---|---|
| Kernel / shell | Claude Code itself — runs the skills, holds the conversation |
| Programs | the five skills (the front door, the runner, the interview, the judge, the operator manual) |
| Shared libraries | `shared/references/` (contracts) + `scripts/` (deterministic helpers) |
| Filesystem | the private per-user workspace (default `~/.job-search/`), never committed |
| System calls | the agent-data CLI — the one job source the runner shells out to |
| Cron | the local schedule (cron / launchd / `/loop`), consent-guarded before any install |

Where the OS state lives and how the workspace is discovered is specified in
[shared/references/internals.md](shared/references/internals.md); the on-disk file layout is in
[shared/references/conventions.md](shared/references/conventions.md).

## Product domains

Five canonical domains describe *what the system does*. Each names the files/skills that implement it and
the `shared/references/` file that owns its contract.

### discovery-search
Find postings: run each saved query against the agent-data Job Postings API, dedup new results against the
local database, and respect retry / outage rules. Implemented by the [job-search-run](skills/job-search-run/SKILL.md)
skill over [scripts/state.py](scripts/state.py) (dedup + persistence). The CLI routes, fields, and retry
semantics are owned by [shared/references/agent-data-contract.md](shared/references/agent-data-contract.md).

### preferences-judgment
Capture what the user wants and judge postings against it — qualitatively, never numerically. The
[job-preference-interview](skills/job-preference-interview/SKILL.md) skill builds the prose brief; the
[evaluate-job-fit](skills/evaluate-job-fit/SKILL.md) skill reads that brief next to a posting and returns a
relevance verdict. The brief shape and the relevance vocabulary are defined in
[shared/references/conventions.md](shared/references/conventions.md).

### workspace-state
Persist everything durably and discoverably: the workspace, config, the append-only job-event log, run
audit logs, and digests. The deterministic engines are [scripts/osctl.py](scripts/osctl.py) (registry +
workspace discovery) and [scripts/state.py](scripts/state.py) (the event log). File contracts live in
[shared/references/conventions.md](shared/references/conventions.md); registry and discovery internals in
[shared/references/internals.md](shared/references/internals.md).

### scheduling-consent
Run on a cadence the user controls, and never install a privileged schedule without explicit consent. The
[job-search](skills/job-search/SKILL.md) skill offers setup; [scripts/osctl.py](scripts/osctl.py) emits the
schedule artifacts and records intent; [hooks/guard-scheduled-tasks.py](hooks/guard-scheduled-tasks.py)
gates the install. The record-intent-then-install workflow and the cadence options live in
[shared/references/internals.md](shared/references/internals.md).

### error-surfacing
Make every failure named and visible — no silent failures. Each blocked path is a named `E-*` error that
surfaces through a blocked digest, a desktop notification, and the home view. The full catalog (codes,
cause + fix wording, run effect, run-health states) is owned by
[shared/references/errors.md](shared/references/errors.md); the runner enforces it.

## Architectural layers

Five canonical layers describe *how the system is built*, bottom-up.

### deterministic-core
Stdlib-only Python helpers under [scripts/](scripts/osctl.py) that do the non-judgment work the skills must
not improvise: [scripts/osctl.py](scripts/osctl.py) (registry, workspace resolution, schedule artifacts) and
[scripts/state.py](scripts/state.py) (the `jobs.jsonl` engine). Skills call these by absolute path resolved
from their own directory. `osctl`'s full subcommand surface is generated at
[docs/generated/osctl-commands.md](docs/generated/osctl-commands.md).

### shared-references
The single source of truth for every runtime contract:
[errors.md](shared/references/errors.md), [conventions.md](shared/references/conventions.md),
[agent-data-contract.md](shared/references/agent-data-contract.md), and
[internals.md](shared/references/internals.md). [scripts/build.sh](scripts/build.sh) fans this tree (and the
core scripts) into each skill so loose-skill installs are self-contained.

### skill-layer
The five programs: [job-search](skills/job-search/SKILL.md) (front door / home view),
[job-search-run](skills/job-search-run/SKILL.md) (headless pass),
[job-preference-interview](skills/job-preference-interview/SKILL.md) (brief builder),
[evaluate-job-fit](skills/evaluate-job-fit/SKILL.md) (single-posting judge), and
[job-search-agent](skills/job-search-agent/SKILL.md) (the operator manual). Skills hold playbooks and
prose; they delegate determinism to the core and defer every contract to the references.

### hooks-guards
Deterministic guardrails: [hooks/guard-scheduled-tasks.py](hooks/guard-scheduled-tasks.py) is a PreToolUse
hook that asks or denies scheduling installs based on a short-lived consent marker, and
[scripts/philosophy_guard.py](scripts/philosophy_guard.py) runs in CI to reject numeric scores or
budget/cost fields leaking into shipped artifacts.

### tests-evals
The deterministic test bed under [tests/](tests/): pytest suites for the core, hooks, and the doc linter; a
fake `agent-data` PATH shim (`tests/fake-agent-data`) so runs are exercised with no network and no credits;
and per-skill `evals/` measured by the skill-creator harness. See [TESTING.md](TESTING.md) for the matrix.

## Package layering & data flow

**Dependency direction.** Skills depend downward only: a skill calls [scripts/](scripts/osctl.py) for
determinism and reads [shared/references/](shared/references/conventions.md) for contracts. The core and the
references depend on nothing in the skills, so contracts stay authoritative and testable in isolation.

**Single source of truth + the build.** Authors edit `shared/references/*.md` and `scripts/`, then run
[scripts/build.sh](scripts/build.sh), which copies the references and the helper scripts into every skill's
bundled `references/` and `scripts/`. **Never hand-edit a skill's synced copies** — the next build overwrites
them silently.

**Distribution.** Two modes ship from one tree: as a **plugin** (declared in `.claude-plugin/plugin.json`)
where the skills load together, or as **loose skills** where each folder is self-contained because the build
bundled its dependencies. Either way the contracts are identical. Install steps are in [README.md](README.md).

**Headless run flow.** A scheduled pass runs [job-search-run](skills/job-search-run/SKILL.md): free preflight
gates (CLI present, config, auth, brief, service status), then one metered search per enabled query, dedup via
[scripts/state.py](scripts/state.py), qualitative judgment per new posting, detail reads for the promising
ones, and finally a persisted run record plus a digest. Any blocked gate writes a named-error record so the
next home view surfaces it. Detail and failure modes are in
[docs/product-specs/index.md](docs/product-specs/index.md) and
[shared/references/errors.md](shared/references/errors.md).

**Onboarding flow.** On first run [job-search](skills/job-search/SKILL.md) walks the user end-to-end —
prereqs, workspace, the preferences interview, queries + cadence, a first live search, and optional
(consent-guarded) scheduling — ending with real matches. The full flow is specified in
[docs/product-specs/index.md](docs/product-specs/index.md); the design rationale in
[docs/design-docs/index.md](docs/design-docs/index.md).

## Where the contracts live

When you need an exact runtime detail, go to its owner — do not reproduce it here:

| Need | Owner |
|---|---|
| Named errors, run-health states, surfacing | [shared/references/errors.md](shared/references/errors.md) |
| Workspace layout, `config.yaml`, jobs log, digest format | [shared/references/conventions.md](shared/references/conventions.md) |
| agent-data CLI: routes, fields, retry rules, listing id | [shared/references/agent-data-contract.md](shared/references/agent-data-contract.md) |
| Registry, workspace discovery, config recipes, scheduling | [shared/references/internals.md](shared/references/internals.md) |

Contributor workflow and the green-gate commands are in [CONTRIBUTING.md](CONTRIBUTING.md) and
[TESTING.md](TESTING.md); planned work is tracked in [docs/exec-plans/index.md](docs/exec-plans/index.md).
