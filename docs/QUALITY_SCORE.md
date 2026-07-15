# Quality Score

A living, **qualitative** grade for each product domain and architectural layer — and the gaps
behind each grade. Grades are words, not numbers, on purpose: this project's identity is
qualitative-not-numeric, so its own scorecard eats that dogfood. Re-grade as the code changes
(the on-demand doc-gardening sweep is a good trigger).

**Scale:** `strong` (solid, well-tested, no known material gaps) · `adequate` (works, with known
gaps worth tracking) · `thin` (partial / lightly tested) · `missing` (not yet built).

_Last assessed: 2026-07-15._

| Area | Kind | Grade | Gaps |
|---|---|---|---|
| `discovery-search` | domain | strong | Four live sources (LinkedIn, Ashby, Greenhouse, Lever); opt-in cursor traversal, progress guards, and fair selection are shim/eval-covered for the three company-board sources, while a separately authorized live cursor acceptance check remains outside CI; cross-source merging is conservative by design (unsure → distinct entries). |
| `preferences-judgment` | domain | strong | Judgment consistency rests on the prose method; there is no automated consistency check. |
| `workspace-state` | domain | adequate | State procedures are model-executed against pinned contracts — verified by evals + the TESTING matrix, not unit tests; the concurrency-recovery path is not exercised by a test (tracked). |
| `scheduling-consent` | domain | adequate | Unattended-first scheduling, explicit consent, and the config-time canary remain instruction-level + eval behavior; a real unattended canary and out-of-range time / `timezone` runtime behavior are not automated in CI. |
| `error-surfacing` | domain | strong | The desktop block-notification toggle is not exercised at runtime. |
| `deterministic-core` | layer | adequate | The contracts are pinned once in `shared/references/` and exercised by evals, but no unit suite pins them since the Python helpers were removed (the named zero-dependency tradeoff; tracked). |
| `shared-references` | layer | strong | References are single-homed under `shared/references/` and resolve in place from each skill (no per-skill copies), verified by `tests/test_reference_resolution.py`; no material gaps. |
| `skill-layer` | layer | adequate | Conversational one-off/saved review depth, usage explanations, and one-time nudges are specified in effect-based evals; the evals run via skill-creator rather than pytest CI, and the planned config slash-commands remain pending. |
| `hooks-guards` | layer | adequate | CI-only guards now distinguish accurate calls-first context from budget controls and invented charge claims; nothing executable ships to user machines, so runtime conduct still rests on instruction-level stances plus evals. |
| `tests-evals` | layer | adequate | The fake shim covers cursor chains and attempt accounting, with effect-based evals for progress, cleanup, partial depth, quota, consent, and nudges; behavioral skill evals and live acceptance still run outside CI, so CI does not prove model behavior. |

> Detailed, itemised debt lives in the tech-debt tracker under `docs/exec-plans/`. This scorecard is
> the high-level view; the tracker is the backlog.
