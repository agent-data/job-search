# Design Docs

Catalogued design documentation. The **living** principles are in `core-beliefs.md`; the dated
specs below are **historical** snapshots of the original design (kept for rationale; the live
contracts now live in `shared/references/`).

## Living
- [Core Beliefs — Agent-First Operating Principles](core-beliefs.md) — _status: current_
- [Prompt & Doc Style Guide](prompt-style-guide.md) — _status: current_
- [Hermes-Native Host — Adapter + Bundled State-Ops Runtime](2026-06-29-hermes-native-plugin.md) — _status: current_

## Historical design snapshots
- [Job Search OS — Original Design Spec](2026-06-05-os-design.md) — _status: historical_
- [Plan B/D — Design Delta & Resolved Decisions](2026-06-05-plan-b-d-design.md) — _status: historical_
- [Plan B/D — Handoff](2026-06-05-plan-b-d-handoff.md) — _status: historical_

## Forward-looking (aspirational)
- [Multi-Harness Portability — Research Dossier](multi-harness-portability.md) — _status: aspirational_

## Superseded
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
