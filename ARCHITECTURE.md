# Architecture

Job Search turns **an agent harness** into a private, local-first **job-search operating system**: a plugin
of five skills, a single-source-of-truth `shared/references/` tree whose pinned contracts the host agent
executes natively (no bundled runtime — no Python), and a pytest + fake-shim + eval harness. It searches LinkedIn, Ashby, Greenhouse, and Lever company-board postings through the agent-data
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

| OS concept | In Job Search |
|---|---|
| Kernel / shell | the host agent (e.g. Claude Code, Codex) — runs the skills, holds the conversation |
| Programs | the five skills (the front door, the runner, the interview, the judge, the operator manual) |
| Shared libraries | `shared/references/` — the contracts and pinned procedures the host agent executes |
| Filesystem | the private per-user workspace (default `~/.job-search/`), never committed |
| System calls | the agent-data CLI — the one job source the runner shells out to |
| Cron | the schedule — an unattended machine schedule (`cron`/`launchd`, or the host's own scheduler) the agent composes for its host and gates on consent; an in-session loop is the named fallback. See [shared/references/internals.md](shared/references/internals.md) → Scheduling setup |

Where the OS state lives and how the workspace is discovered is specified in
[shared/references/internals.md](shared/references/internals.md); the on-disk file layout is in
[shared/references/conventions.md](shared/references/conventions.md).

## Product domains

Five canonical domains describe *what the system does*. Each names the files/skills that implement it and
the `shared/references/` file that owns its contract.

### discovery-search
Find postings: run each saved query against the agent-data Job Postings API, dedup new results against the
local record of already-seen postings, and respect retry / outage rules. Implemented by the [job-search-run](skills/job-search-run/SKILL.md)
skill over the `jobs.jsonl` operations in [shared/references/conventions.md](shared/references/conventions.md)
(dedup + persistence). The CLI routes, fields, and retry
semantics are owned by [shared/references/agent-data-contract.md](shared/references/agent-data-contract.md).

### preferences-judgment
Capture what the user wants and judge postings against it — qualitatively, never numerically. The
[job-preference-interview](skills/job-preference-interview/SKILL.md) skill builds the prose brief; the
[evaluate-job-fit](skills/evaluate-job-fit/SKILL.md) skill reads that brief next to a posting and returns a
relevance verdict. The brief shape and the relevance vocabulary are defined in
[shared/references/conventions.md](shared/references/conventions.md).

### workspace-state
Persist everything durably and discoverably: the workspace, config, the append-only job-event log, run
audit logs, and digests. The engines are pinned procedures executed natively by the host agent: the registry +
workspace-discovery rules in [shared/references/internals.md](shared/references/internals.md) and the
event-log operations in [shared/references/conventions.md](shared/references/conventions.md), which also
owns the file contracts.

### scheduling-consent
Run on a cadence the user controls: the agent advocates an **unattended** machine schedule (`cron`/`launchd`
or the host's own scheduler) it composes for its host — an in-session loop is the named fallback — never a
SILENT or un-consented privileged write. The
[job-search](skills/job-search/SKILL.md) skill offers setup from the pinned interval table and, once the
config-time canary proves the schedule actually runs, records the schedule marker in the registry; the agent
resolves the concrete mechanism for its own host (there is no per-host adapter). The consent-gated stance is an instruction-level design rule carried by every skill
([docs/SECURITY.md](docs/SECURITY.md), [core-beliefs.md](docs/design-docs/core-beliefs.md) Belief 7), not a
runtime control. The cadence options live in [shared/references/internals.md](shared/references/internals.md).

### error-surfacing
Make every failure named and visible — no silent failures. Each blocked path is a named `E-*` error whose
durable guarantee is two file-backed channels — the blocked digest and the home view — plus a
capability-gated attention-pull alert (fires only when the host has such a channel). The full catalog (codes,
cause + fix wording, run effect, run-health states) is owned by
[shared/references/errors.md](shared/references/errors.md); the runner enforces it.

## Architectural layers

Five canonical layers describe *how the system is built*, bottom-up.

### deterministic-core
The pinned contracts for the non-judgment work the skills must not improvise: the registry schema + write
rules, the workspace-discovery precedence, the scheduling marker, and the `jobs.jsonl` operations
(known-ids / append / fold). They are defined once — as exact procedures and portable shell one-liners in
[shared/references/internals.md](shared/references/internals.md) and
[shared/references/conventions.md](shared/references/conventions.md) — and the host agent executes them with
its native tools. No helper binary or script ships with the skills.

### shared-references
The single source of truth for every runtime contract:
[errors.md](shared/references/errors.md), [conventions.md](shared/references/conventions.md),
[agent-data-contract.md](shared/references/agent-data-contract.md),
[internals.md](shared/references/internals.md), and the durable run and local-metrics contract in
[run-lifecycle.md](shared/references/run-lifecycle.md). The install lays down the whole pack tree, so these
resolve in place from each skill — nothing is fanned into per-skill copies;
[scripts/build.sh](scripts/build.sh) only regenerates the build stamp
(`shared/references/build-stamp.md`).

### skill-layer
The five programs: [job-search](skills/job-search/SKILL.md) (front door / home view),
[job-search-run](skills/job-search-run/SKILL.md) (headless pass),
[job-preference-interview](skills/job-preference-interview/SKILL.md) (brief builder),
[evaluate-job-fit](skills/evaluate-job-fit/SKILL.md) (single-posting judge), and
[job-search-agent](skills/job-search-agent/SKILL.md) (the operator manual). Skills hold playbooks and
prose; they execute the deterministic core's pinned procedures and defer every contract to the references.

### hooks-guards
CI guardrails (dev-side only — nothing executable ships to user machines):
[scripts/philosophy_guard.py](scripts/philosophy_guard.py) rejects numeric scores or budget/cost fields
leaking into shipped artifacts, and [scripts/doc_lint.py](scripts/doc_lint.py) keeps the knowledge base
structurally sound. The scheduling stance is instruction-level (see scheduling-consent above).

### tests-evals
The deterministic test bed under [tests/](tests/): pytest suites for the dev tooling (the doc linter, the
philosophy guard, the agent-data shim's self-checks); a fake `agent-data` PATH shim
(`tests/fake-agent-data`) so runs are exercised with no network and no credits; and per-skill `evals/`
measured by the skill-creator harness — the evals are what verify the pinned runtime procedures end-to-end.
See [TESTING.md](TESTING.md) for the matrix.

## Package layering & data flow

**Dependency direction.** Skills depend downward only: a skill reads
[shared/references/](shared/references/conventions.md) for its contracts and the pinned procedures it
executes. The references depend on nothing in the skills, so contracts stay authoritative and verifiable in
isolation.

**Single source of truth + the build.** Authors edit `shared/references/*.md`; there is nothing to sync.
The install lays down the whole pack tree, so those files resolve in place from each skill — there are **no
per-skill bundled copies**. [scripts/build.sh](scripts/build.sh) is stamp-only: it regenerates the build
stamp (`shared/references/build-stamp.md`) and never copies references into the skills.

**Distribution.** One `skills/` tree, read in place, ships to every harness via a per-harness manifest —
`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`, `.factory-plugin/`, `gemini-extension.json`,
`package.json`. There is **no per-host adapter layer**: each host resolves its own tools, models, scheduler,
and permissions from the neutral action-language in the pinned procedures, then verifies the result rather
than looking up a host-specific recipe. Every supported host installs the whole pack tree, so
`shared/references/` resolves from each skill in place; the contracts are identical across all harnesses.
Install steps are in [README.md](README.md).

**Headless run flow.** A scheduled pass runs [job-search-run](skills/job-search-run/SKILL.md): free preflight
gates (CLI present, config, auth, brief, service status), then one metered search per enabled query, dedup via
the known-ids operation ([shared/references/conventions.md](shared/references/conventions.md)), qualitative
judgment per new posting, detail reads for the promising
ones, and finally a persisted run record plus a digest. Any blocked gate writes a named-error record so the
next home view surfaces it. Detail and failure modes are in
[docs/product-specs/index.md](docs/product-specs/index.md) and
[shared/references/errors.md](shared/references/errors.md).

**Onboarding flow.** On first run [job-search](skills/job-search/SKILL.md) walks the user end-to-end —
prereqs, workspace, the preferences interview, queries + cadence, a first live search, and optional
scheduling (offered as a yes/no, never assumed) — ending with real matches. The full flow is specified in
[docs/product-specs/index.md](docs/product-specs/index.md); the design rationale in
[docs/design-docs/index.md](docs/design-docs/index.md).

## Where the contracts live

When you need an exact runtime detail, go to its owner — do not reproduce it here:

| Need | Owner |
|---|---|
| Named errors, run-health states, surfacing | [shared/references/errors.md](shared/references/errors.md) |
| Workspace layout, `config.yaml`, jobs log, digest format | [shared/references/conventions.md](shared/references/conventions.md) |
| Run lifecycle, completion, recovery, local metrics | [shared/references/run-lifecycle.md](shared/references/run-lifecycle.md) |
| agent-data CLI: routes, fields, retry rules, listing id | [shared/references/agent-data-contract.md](shared/references/agent-data-contract.md) |
| Registry, workspace discovery, config recipes, scheduling | [shared/references/internals.md](shared/references/internals.md) |

Contributor workflow and the green-gate commands are in [CONTRIBUTING.md](CONTRIBUTING.md) and
[TESTING.md](TESTING.md); planned work is tracked in [docs/exec-plans/index.md](docs/exec-plans/index.md).
