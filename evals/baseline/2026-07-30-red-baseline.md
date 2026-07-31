# RED baseline — 2026-07-30 iteration-1 live evals (pre-overhaul plugin)

Aggregate numbers from the 2026-07-30 iteration-1 live evals of the pre-overhaul plugin —
the numbers the overhaul must beat. B14 (see `evals/behaviors.md`) compares every
post-rewrite run against this file. Aggregates only: no machine paths, no user data.

## Headline measurements

| measurement | RED value |
|---|---|
| time to first live result (headless quickstart) | 190 s |
| full first-run onboarding wall-clock | 28–41 min |
| metered API calls, onboarding run | 37 |
| metered API calls, one daily pass | 64 |
| lines read before the first API call | ~3,550 (9 files) |
| first-run TUI: position of the greeting among visible outputs | 4th (after mechanics narration, a skill card, and raw tool output) |
| permission dialogs in the first 10 min of the TUI run | 35 |

## Per-eval assertion outcomes

| iteration-1 eval | assertions passed |
|---|---|
| eval-0 quickstart (headless) | 6/6 |
| eval-1 persona probes | 2/3 |
| eval-2 headless run | 5/5 |
| eval-3 fit | 3/3 |
| eval-4 no-plugin baseline (control) | 3/3 |
| eval-5 real-TUI first-run | 1/3 (greeting-order and no-mechanics-narration failed) |
| **total** | **20/23** |

End-to-end outcomes (matches found, digests written, jobs.jsonl rows) were correct in every
eval; the failed assertions above are first-run communication behaviors, and the headline
rows are the time, metered-call, and reading costs the overhaul is built to cut.
