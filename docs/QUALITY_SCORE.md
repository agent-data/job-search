# Quality Score

A living, **qualitative** grade for each product domain and architectural layer — and the gaps
behind each grade. Grades are words, not numbers, on purpose: this project's identity is
qualitative-not-numeric, so its own scorecard eats that dogfood. Re-grade as the code changes
(the on-demand doc-gardening sweep is a good trigger).

**Scale:** `strong` (solid, well-tested, no known material gaps) · `adequate` (works, with known
gaps worth tracking) · `thin` (partial / lightly tested) · `missing` (not yet built).

_Last assessed: 2026-06-07._

| Area | Kind | Grade | Gaps |
|---|---|---|---|
| `discovery-search` | domain | strong | LinkedIn-only source; the multi-source seam is intentionally not built (YAGNI). |
| `preferences-judgment` | domain | strong | Judgment consistency rests on the prose method; there is no automated consistency check. |
| `workspace-state` | domain | strong | The concurrency-recovery path is not exercised by a test (tracked in the tech-debt tracker). |
| `scheduling-consent` | domain | adequate | Plugin-bundled-hooks shipping is unresolved; out-of-range time validation and `timezone` runtime behaviour are untested. |
| `error-surfacing` | domain | strong | The desktop block-notification toggle is not exercised at runtime. |
| `deterministic-core` | layer | strong | Broad unit coverage across the helper scripts; no material gaps. |
| `shared-references` | layer | strong | A build step plus a CI sync-check keep the bundled copies honest; no material gaps. |
| `skill-layer` | layer | adequate | Skill evals run via skill-creator, not pytest CI; the conversational config slash-commands are still pending. |
| `hooks-guards` | layer | adequate | The mechanism that ships the consent hook with the installed plugin is still an open question. |
| `tests-evals` | layer | adequate | Skill evals and the live acceptance pass run outside CI (manual / skill-creator), so CI proves the deterministic core, not the model behaviour. |

> Detailed, itemised debt lives in the tech-debt tracker under `docs/exec-plans/`. This scorecard is
> the high-level view; the tracker is the backlog.
