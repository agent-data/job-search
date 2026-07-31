# Architecture

Job Search turns **an agent harness** into a private, local-first **job-search operating system**: a plugin
of five skills, a single-source-of-truth `shared/references/` tree whose pinned contracts the host agent
executes natively (no bundled runtime — no Python), and a pytest + fake-shim + eval harness. It searches LinkedIn, Ashby, Greenhouse, and Lever company-board postings through the agent-data
marketplace, judges each one qualitatively against your prose preferences brief, and writes human digests
into a workspace that never touches source control.

This doc is the **structural map**: the OS model, the five product **domains**, the five architectural
**layers**, and how packages depend on each other and data flows through a run. It is deliberately a map,
not the territory — the binding details live elsewhere and are linked, never restated. For the full design
specs see [docs/design-docs/index.md](docs/design-docs/index.md); the runtime contracts — the workspace
and the run contract in `runbook.md`, the job-postings API in `agent-data.md` — are the single source of
truth under `shared/references/`. Read [AGENTS.md](AGENTS.md) first for the agent-facing
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
| Cron | the schedule — an unattended machine schedule (`cron`/`launchd`, or the host's own scheduler) the agent composes for its host and gates on consent; an in-session loop is the named fallback. See [shared/references/runbook.md](shared/references/runbook.md) → Running it unattended |

Where the OS state lives, how the workspace is discovered, and what each file in it holds are specified in
[shared/references/runbook.md](shared/references/runbook.md); the exact shape of each file is carried by the
examples in [templates/](templates/) and checked by
[shared/scripts/mechanics/validate-workspace.sh](shared/scripts/mechanics/validate-workspace.sh).

## Product domains

Five canonical domains describe *what the system does*. Each names the files/skills that implement it and
the `shared/references/` file that owns its contract.

### discovery-search
Find postings: run each saved query against the agent-data Job Postings API, dedup new results against the
local record of already-seen postings, and respect retry / outage rules. Implemented by the [job-search-run](skills/job-search-run/SKILL.md)
skill over the `jobs.jsonl` operations in
[shared/scripts/mechanics/dedup.sh](shared/scripts/mechanics/dedup.sh) and
[shared/scripts/mechanics/event-log-append.sh](shared/scripts/mechanics/event-log-append.sh) (dedup +
persistence). The CLI routes, per-source quirks, retry rules, and what a call costs are owned by
[shared/references/agent-data.md](shared/references/agent-data.md).

### preferences-judgment
Capture what the user wants and judge postings against it — qualitatively, never numerically. The
[job-preference-interview](skills/job-preference-interview/SKILL.md) skill builds the prose brief; the
[evaluate-job-fit](skills/evaluate-job-fit/SKILL.md) skill reads that brief next to a posting and returns a
relevance verdict. The brief shape is shown by
[templates/preferences.example.md](templates/preferences.example.md), and the relevance vocabulary is
defined by the [evaluate-job-fit](skills/evaluate-job-fit/SKILL.md) skill that returns it.

### workspace-state
Persist everything durably and discoverably: the workspace, config, the append-only job-event log, run
audit logs, and digests. The engines are pinned procedures executed natively by the host agent: the registry +
workspace-discovery rules in [shared/references/runbook.md](shared/references/runbook.md), which also
maps what each file holds, and the event-log operations in
[shared/scripts/mechanics/event-log-append.sh](shared/scripts/mechanics/event-log-append.sh).

### scheduling-consent
Run on a cadence the user controls: the agent advocates an **unattended** machine schedule (`cron`/`launchd`
or the host's own scheduler) it composes for its host — an in-session loop is the named fallback — never a
SILENT or un-consented privileged write. The
[job-search](skills/job-search/SKILL.md) skill offers setup from the pinned interval table and, once the
config-time canary proves the schedule actually runs, records the schedule marker in the registry; the agent
resolves the concrete mechanism for its own host (there is no per-host adapter). The consent-gated stance is an instruction-level design rule carried by every skill
([docs/SECURITY.md](docs/SECURITY.md), [core-beliefs.md](docs/design-docs/core-beliefs.md) Belief 7), not a
runtime control. The cadence options live in [templates/config.example.yaml](templates/config.example.yaml),
and the cron line for each is composed by
[shared/scripts/mechanics/schedule-line.sh](shared/scripts/mechanics/schedule-line.sh).

### error-surfacing
Make every failure named and visible — no silent failures. A run that stops early still closes: it writes a
run record saying what stopped it and a digest the user reads, which are the two file-backed channels the
home view surfaces, plus a capability-gated attention-pull alert (fires only when the host has such a
channel). Each skill names the failures its own flow can hit, in plain language next to the step that hits
them — the `E-*` code catalog was retired on 2026-07-31. The API failures every flow shares — which
responses can be retried, and when to stop spending calls on one — are in
[shared/references/agent-data.md](shared/references/agent-data.md).

## Architectural layers

Five canonical layers describe *how the system is built*, bottom-up.

### deterministic-core
The pinned contracts for the non-judgment work the skills must not improvise: the registry schema + write
rules, the workspace-discovery precedence, the scheduling marker, and the `jobs.jsonl` operations
(known-ids / append / fold). They are defined once — as the recipes in
[shared/references/runbook.md](shared/references/runbook.md) and as the POSIX shell scripts under
[shared/scripts/mechanics/](shared/scripts/mechanics/) — and the host agent runs them with its native tools.

### shared-references
The single source of truth for every runtime contract, in two files:
[runbook.md](shared/references/runbook.md) (the workspace, what each file holds, how one run opens and
closes, what stays off disk) and [agent-data.md](shared/references/agent-data.md) (the CLI, the per-source
quirks, retries, what a call costs). The install lays down the whole pack tree, so both resolve in place
from each skill — nothing is fanned into per-skill copies.

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
Three layers. The deterministic test bed under [tests/](tests/): pytest suites for the dev tooling (the doc
linter, the philosophy guard, the release-integrity checks, the mechanics scripts, the workspace validator,
the shims' self-checks), plus a fake `agent-data` PATH shim (`tests/fake-agent-data`) so a whole run is
exercised with no network and no credits. Per-skill scenario suites in `skills/<skill>/evals/evals.json`,
checked for structural coherence by [scripts/eval_harness.py](scripts/eval_harness.py) and driven through
the skill-creator skill. And the live behavior evals in [evals/](evals/) — `run_eval.py` spawns a real
session against the live Job Postings API and captures the transcript and the workspace it produced, which
a grader reads; `behaviors.md` maps the fourteen kept behaviors B1–B14 onto the six cases in `cases/`.
Because those runs cost real metered calls they are a local release gate, not a CI step. See
[TESTING.md](TESTING.md) for the matrix.

## Package layering & data flow

**Dependency direction.** Skills depend downward only: a skill reads
`shared/references/` for its contracts and the pinned procedures it
executes. The references depend on nothing in the skills, so contracts stay authoritative and verifiable in
isolation.

**Single source of truth.** Authors edit `shared/references/*.md`; there is nothing to sync. The install
lays down the whole pack tree, so those files resolve in place from each skill — there are **no per-skill
bundled copies**, and no build step writes into `skills/` or `shared/`.

**Distribution.** One `skills/` tree, read in place, ships to every harness via a per-harness manifest —
`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`, `.factory-plugin/`, `gemini-extension.json`,
`package.json`, and the root `plugin.yaml` + `__init__.py` (Hermes Agent). There is **no per-host adapter layer**: each host resolves its own tools, models, scheduler,
and permissions from the neutral action-language in the pinned procedures, then verifies the result rather
than looking up a host-specific recipe. Every supported host installs the whole pack tree, so
`shared/references/` resolves from each skill in place; the contracts are identical across all harnesses.
Install steps are in [README.md](README.md).

**Headless run flow.** A scheduled pass runs [job-search-run](skills/job-search-run/SKILL.md): free preflight
gates (CLI present, config, auth, brief, service status), then one metered search per enabled query, dedup via
the known-ids operation ([shared/scripts/mechanics/dedup.sh](shared/scripts/mechanics/dedup.sh)), qualitative
judgment per new posting, detail reads for the promising
ones, and finally a persisted run record plus a digest. A run that a gate stops still closes: it writes a
record with `close_state: blocked` and `run_health: degraded`, and a digest whose body says what stopped it
and what fixes it, so the next home view surfaces both. Detail and failure modes are in
[docs/product-specs/index.md](docs/product-specs/index.md) and
[shared/references/agent-data.md](shared/references/agent-data.md).

**Onboarding flow.** On first run [job-search](skills/job-search/SKILL.md) walks the user end-to-end —
prereqs, workspace, the preferences interview, queries + cadence, a first live search, and optional
scheduling (offered as a yes/no, never assumed) — ending with real matches. The full flow is specified in
[docs/product-specs/index.md](docs/product-specs/index.md); the design rationale in
[docs/design-docs/index.md](docs/design-docs/index.md).

## Where the contracts live

When you need an exact runtime detail, go to its owner — do not reproduce it here:

| Need | Owner |
|---|---|
| Workspace layout, registry, workspace discovery, the run contract, the scratch rule | [shared/references/runbook.md](shared/references/runbook.md) |
| agent-data CLI: routes, per-source quirks, retry rules, listing id, what a call costs | [shared/references/agent-data.md](shared/references/agent-data.md) |
| The exact shape of `config.yaml`, a run record, a `jobs.jsonl` line, the brief | [templates/](templates/) — `config.example.yaml`, `run-record.example.json`, `jobs-event.example.json`, `preferences.example.md` |
| Whether a workspace on disk is well formed | [shared/scripts/mechanics/validate-workspace.sh](shared/scripts/mechanics/validate-workspace.sh) |
| How each skill behaves | its `SKILL.md`, graded by the live behavior evals in [evals/](evals/) and its own `evals/evals.json` |

Contributor workflow and the green-gate commands are in [CONTRIBUTING.md](CONTRIBUTING.md) and
[TESTING.md](TESTING.md); planned work is tracked in [docs/exec-plans/index.md](docs/exec-plans/index.md).
