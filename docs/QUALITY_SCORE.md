# Quality Score

A living, **qualitative** grade for each product domain and architectural layer — and the gaps
behind each grade. Grades are words, not numbers, on purpose: this project's identity is
qualitative-not-numeric, so its own scorecard eats that dogfood. Re-grade as the code changes
(the on-demand doc-gardening sweep is a good trigger).

**Scale:** `strong` (solid, well-tested, no known material gaps) · `adequate` (works, with known
gaps worth tracking) · `thin` (partial / lightly tested) · `missing` (not yet built).

_Last assessed: 2026-06-11._

| Area | Kind | Grade | Gaps |
|---|---|---|---|
| `discovery-search` | domain | strong | LinkedIn-only source; the multi-source seam is intentionally not built (YAGNI). |
| `preferences-judgment` | domain | strong | Judgment consistency rests on the prose method; there is no automated consistency check. |
| `workspace-state` | domain | adequate | State procedures are model-executed against pinned contracts — verified by evals + the TESTING matrix, not unit tests; the concurrency-recovery path is not exercised by a test (tracked). |
| `scheduling-consent` | domain | adequate | The no-cron stance is instruction-level only (the deny hook was removed 2026-06-11 — resolves the former hooks-shipping question); out-of-range time validation and `timezone` runtime behaviour are untested. |
| `error-surfacing` | domain | strong | The desktop block-notification toggle is not exercised at runtime. |
| `deterministic-core` | layer | adequate | The contracts are pinned once in `shared/references/` and exercised by evals, but no unit suite pins them since the Python helpers were removed (the named zero-dependency tradeoff; tracked). |
| `shared-references` | layer | strong | A build step plus a CI sync-check keep the bundled copies honest; no material gaps. |
| `skill-layer` | layer | adequate | Skill evals run via skill-creator, not pytest CI; the conversational config slash-commands are still pending. |
| `hooks-guards` | layer | adequate | Now CI-only guards (philosophy guard + doc lint); nothing executable ships to user machines, so runtime conduct rests on the instruction-level stances the evals check. |
| `tests-evals` | layer | adequate | Skill evals and the live acceptance pass run outside CI (manual / skill-creator), so CI proves the dev tooling, not the model behaviour — which now includes the pinned state procedures. |

> Detailed, itemised debt lives in the tech-debt tracker under `docs/exec-plans/`. This scorecard is
> the high-level view; the tracker is the backlog.
