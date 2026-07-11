# Design Docs

Catalogued design documentation. The **living** principles are in `core-beliefs.md`; the dated
specs below are **historical** snapshots of the original design (kept for rationale; the live
contracts now live in `shared/references/`).

## Living
- [Core Beliefs — Agent-First Operating Principles](core-beliefs.md) — _status: current_
- [Prompt style guide — index & applicability matrix](prompt-style-guide/index.md) — _status: current_
- [Prompt style guide — Foundations: voice, emphasis, framing, examples, length](prompt-style-guide/01-foundations.md) — _status: current_
- [Prompt style guide — Tool definitions: description anatomy, params, steering, tool-error messages](prompt-style-guide/03-tool-definitions.md) — _status: current_
- [Prompt style guide — Subagents & delegation: prompts, routing descriptions, briefs, verdicts, economics](prompt-style-guide/04-subagents-and-delegation.md) — _status: current_
- [Prompt style guide — Harness injections: reminders, nudges, compaction, env context, trust framing](prompt-style-guide/05-harness-injections.md) — _status: current_
- [Prompt style guide — User communication: preambles, progress, final messages, truthful reporting](prompt-style-guide/06-user-communication.md) — _status: current_
- [Prompt style guide — Safety & honesty pressure: completion pressure, counterweights, permissions, plan-mode boundary](prompt-style-guide/07-safety-and-honesty-pressure.md) — _status: current_
- [Prompt style guide — Anti-patterns](prompt-style-guide/08-anti-patterns.md) — _status: current_
- [Prompt style guide — Checklist & rule index](prompt-style-guide/09-checklist-and-rule-index.md) — _status: current_
- [Agent-agnostic skill packs — index & applicability matrix](agent-agnostic-skills/index.md) — _status: current_
- [Agent-agnostic skill packs — Pack anatomy & organization](agent-agnostic-skills/01-pack-anatomy-and-organization.md) — _status: current_
- [Agent-agnostic skill packs — Skill anatomy](agent-agnostic-skills/02-skill-anatomy.md) — _status: current_
- [Agent-agnostic skill packs — Conceptual boundaries & progressive disclosure](agent-agnostic-skills/03-conceptual-boundaries-and-disclosure.md) — _status: current_
- [Agent-agnostic skill packs — Triggering & description design](agent-agnostic-skills/04-triggering-and-descriptions.md) — _status: current_
- [Agent-agnostic skill packs — Guidance representation](agent-agnostic-skills/05-guidance-representation.md) — _status: current_
- [Agent-agnostic skill packs — Examples in skills](agent-agnostic-skills/06-examples.md) — _status: current_
- [Agent-agnostic skill packs — Autonomy calibration](agent-agnostic-skills/07-autonomy-calibration.md) — _status: current_
- [Agent-agnostic skill packs — Process vs domain skills](agent-agnostic-skills/08-process-vs-domain-skills.md) — _status: current_
- [Agent-agnostic skill packs — Harness-neutral language](agent-agnostic-skills/09-harness-neutral-language.md) — _status: current_
- [Agent-agnostic skill packs — Portability mechanics](agent-agnostic-skills/10-portability-mechanics.md) — _status: current_
- [Agent-agnostic skill packs — Distribution, packaging & versioning](agent-agnostic-skills/11-distribution-packaging-and-versioning.md) — _status: current_
- [Agent-agnostic skill packs — Testing & verification of skills](agent-agnostic-skills/12-testing-and-verification.md) — _status: current_
- [Agent-agnostic skill packs — Anti-patterns](agent-agnostic-skills/13-anti-patterns.md) — _status: current_
- [Agent-agnostic skill packs — Checklist & rule index](agent-agnostic-skills/14-checklist-and-rule-index.md) — _status: current_
- [Agent-agnostic skill packs — Gap analysis: job-search-os packaging & build](agent-agnostic-skills/15-gap-analysis-jso-packaging.md) — _status: current_
- [Agent-agnostic skill packs — Tension register](agent-agnostic-skills/16-tension-register.md) — _status: current_
- [Plugin ↔ guide alignment audit: skills, references & adapters vs the AAS + PSG rules](2026-07-10-plugin-guide-alignment-audit.md) — _status: current_

## Historical design snapshots
- [Job Search OS — Original Design Spec](2026-06-05-os-design.md) — _status: historical_
- [Plan B/D — Design Delta & Resolved Decisions](2026-06-05-plan-b-d-design.md) — _status: historical_
- [Plan B/D — Handoff](2026-06-05-plan-b-d-handoff.md) — _status: historical_

## Forward-looking (aspirational)
- [Plugin ↔ guide alignment: refactor design](2026-07-11-plugin-guide-alignment-design.md) — _status: aspirational_
- [Multi-Harness Portability — Research Dossier](multi-harness-portability.md) — _status: aspirational_

## Superseded
- [Three-Skill Job Search Redesign](2026-07-09-three-skill-redesign.md) — _status: superseded_ (superseded by the [plugin ↔ guide alignment design](2026-07-11-plugin-guide-alignment-design.md), which keeps all five skills)
- [Prompt & Doc Style Guide — legacy single-file redirect](prompt-style-guide.md) — _status: superseded_
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
| `superseded` | Replaced by a newer doc; kept only for history. Excluded from the no-shared-reference-duplication check, like `historical`. (In use: `codex-portability.md`, plus the legacy single-file `prompt-style-guide.md` redirect.) |
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
