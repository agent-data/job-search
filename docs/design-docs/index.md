# Design Docs

Catalogued design documentation. The **living** principles are in `core-beliefs.md`; the dated
specs below are **historical** snapshots of the original design (kept for rationale; the live
contracts now live in `shared/references/`).

## Living
- [Core Beliefs — Agent-First Operating Principles](core-beliefs.md) — _status: current_
- [Prompt & Doc Style Guide](prompt-style-guide.md) — _status: current_
- [Hermes-Native Host — Adapter + Bundled State-Ops Runtime](2026-06-29-hermes-native-plugin.md) — _status: current_
- [Hermes Job Search Assistant — Seamless Install + Adapter-Native Onboarding](2026-06-30-hermes-job-search-assistant.md) — _status: current_

## Historical design snapshots
- [Job Search OS — Original Design Spec](2026-06-05-os-design.md) — _status: historical_
- [Plan B/D — Design Delta & Resolved Decisions](2026-06-05-plan-b-d-design.md) — _status: historical_
- [Plan B/D — Handoff](2026-06-05-plan-b-d-handoff.md) — _status: historical_

## Forward-looking (aspirational)
- [Multi-Harness Portability — Research Dossier](multi-harness-portability.md) — _status: aspirational_

## Hermes harness review

Source-grounded review of the Hermes agent harness, for maintainers scoping the Hermes concierge layer
(under `hermes-harness-review/`; start at the `overview.md` cross-doc synthesis).

- [Hermes Harness Review — Overview](hermes-harness-review/overview.md) — _status: current_
- [Hermes Harness — Memory & Session History](hermes-harness-review/memory-and-sessions.md) — _status: current_
- [Hermes Harness — Identity, Architecture & Install](hermes-harness-review/identity-architecture-and-install.md) — _status: current_
- [Hermes Harness — Cron & Scheduling](hermes-harness-review/cron-and-scheduling.md) — _status: current_
- [Hermes Harness — Skills System & Packaging](hermes-harness-review/skills-system-and-packaging.md) — _status: current_
- [Hermes Harness — Delegation & Subagents](hermes-harness-review/delegation-and-subagents.md) — _status: current_
- [Hermes Harness — Tools, Clarify & Delivery Channels](hermes-harness-review/tools-clarify-and-channels.md) — _status: current_

## Superseded
- [Hermes Job Search Concierge Layer](2026-06-30-hermes-job-search-concierge.md) — _status: superseded_ (superseded by the [Hermes Job Search Assistant](2026-06-30-hermes-job-search-assistant.md) design, after the [harness review](hermes-harness-review/overview.md))
- [Codex Portability — What It Takes to Run job-search on OpenAI Codex](codex-portability.md) — _status: superseded_ (superseded by the [Multi-Harness Portability dossier](multi-harness-portability.md), which generalizes it to seven harnesses)

---

## Status vocabularies

The one place every status/verification value used across the knowledge base is defined. Each
value below is a member of an enum the `frontmatter-schema` rule in
[`../../scripts/doc_lint.py`](../../scripts/doc_lint.py) enforces — a value not listed here fails
the lint. Design docs and [product specs](../product-specs/index.md) carry `status` + `verified`;
plans carry `state`. The `_status: …_` italics in this index and the product-specs index just echo
each doc's frontmatter `status`.

**`status`** — what a `status`-bearing doc (design doc, product spec) commits the team to. Enum:
`current`, `superseded`, `historical`, `aspirational`.

| Value | Meaning |
|-------|---------|
| `current` | Live and authoritative — the team stands behind it today; keep it true as the code changes. (In use: core-beliefs, the style guide, the onboarding spec.) |
| `superseded` | Replaced by a newer doc; kept only for history. Excluded from the no-shared-reference-duplication check, like `historical`. (Defined; none live yet.) |
| `historical` | A frozen snapshot of past design — read for rationale, not as the live contract (which now lives in `shared/references/`). Wears a snapshot banner. (In use: the three dated `2026-06-05-*` design specs.) |
| `aspirational` | Describes intended, not-yet-built behavior. (Defined; none live yet.) |

**`verified`** — how thoroughly the doc's checkable claims were confirmed against the code/corpus.
Enum: `verified`, `partial`, `unverified`.

| Value | Meaning |
|-------|---------|
| `verified` | Every checkable claim was confirmed against the repo with tooling a reader can re-run. (Defined; none live yet.) |
| `partial` | Some claims confirmed, some not re-checkable with repo tooling — e.g. the style guide quotes a corpus that lives outside this repo. The honest middle. (In use: core-beliefs, the style guide, the onboarding spec.) |
| `unverified` | Claims not systematically checked — treat specifics with caution. (In use: the three historical design specs.) |

**`state`** — a plan's lifecycle position; must also match its directory (`active/` vs
`completed/`), enforced by the `plan-location` rule. Enum: `active`, `completed`, `abandoned`.
Defined once in [`../PLANS.md`](../PLANS.md#how-an-execution-plan-is-structured) (the lifecycle
table + the `active → completed` move) — see there, not duplicated here.
