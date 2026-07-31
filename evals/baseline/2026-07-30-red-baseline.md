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

---

# GREEN — 2026-07-31 post-overhaul live evals (0.8.0)

The same measurements against the rewritten skills, live, on the same seeds. Six cases
(`evals/cases/`) across sonnet and haiku, driven by `evals/run_eval.py`; the behavior rows are the
ones in `evals/behaviors.md`. Aggregates only, like the RED block above: no paths, no run
transcripts, no user data.

## Headline measurements

| measurement | RED | GREEN sonnet | GREEN haiku |
|---|---|---|---|
| time to first live result (headless quickstart) | 190 s | 121 s | 75 s |
| full first-run onboarding wall-clock | 28–41 min | 8.6 min | 4.4 min |
| metered API calls, onboarding run | 37 | 13 | 10 |
| metered API calls, one daily pass (same seed) | 64 | 43–50 | 40 |
| lines read before the first API call | ~3,550 (9 files) | 271 (4 files) | 224–248 (2–4 files) |
| position of the greeting among visible outputs | 4th | 2nd or 3rd | 2nd |
| permission dialogs in the first 10 min | 35 | not measurable | not measurable |

### Measurement condition for every timing row above

**Both** columns of the timing rows — RED and GREEN, time to first live result and wall-clock —
were measured **before the 2026-07-31 latency fix to the job-postings API**. Every run behind the
GREEN column ran before it; none of these numbers includes any of that improvement.

A run made after that fix will be faster for reasons that have nothing to do with the skill rewrite.
Do not compare a later run's timing against these rows to credit or fault the skills, and do not
update the GREEN timing figures with a post-fix run — the comparison only holds while both sides
were measured under the same service. If a future pass wants timing numbers, it needs a fresh
RED-equivalent measured under the same conditions.

The rows that carry the release argument are unaffected by service latency and stay comparable:
metered-call counts, lines read before the first API call, and every behavior pass or fail below.

Every eval runs with permissions pre-accepted, so no dialog is ever shown; that row's GREEN number
has to come from an interactive session, not from this suite.

The greeting row moved but did not land. Its content is right in every run on both models — the
first message says what setup creates and what the user ends up with, in plain words. Its position
is intermittent on sonnet: one run put it second with every piece of mechanics narration after it,
and one put it third, behind a line naming a configuration file.

The haiku onboarding figures buy a much smaller pass than sonnet's — 4 postings judged against 92 —
so they are not a like-for-like saving. See the behavior rows below.

## The four release targets

| target | met? |
|---|---|
| read path before the first API call ≤ 700 lines | yes — worst case 271 |
| quickstart time to first live result ≤ 190 s | yes — 121 s sonnet, 75 s haiku, both sides pre-fix |
| headless metered calls ≤ 64 on the same seed | yes — 43 and 50 across two sonnet reps, 40 haiku |
| B1–B12 pass on both models | **no** — four rows, below |

The time-to-first-result row is the one target that rests on a timing measurement, so it carries the
caveat above: it is a valid comparison because both sides were measured under the same service, and
it stops being one the moment either side is re-measured after the latency fix.

## Behavior rows

| row | sonnet | haiku |
|---|---|---|
| B1 first message, plain language | 1 of 2 reps on ordering; content right everywhere | pass |
| B2 concepts defined at first mention | pass | pass |
| B3 whoami-only preflight, no `status` call | pass | pass |
| B4 cost context before the first metered call | pass | pass |
| B5 summary scan reduces detail reads | pass | pass |
| B6 id + source_url pairing, 0 fabricated ids | pass | not gradable |
| B7 detail-read fault fallback | failed, **fixed**, re-run passes | failed, **fixed**, re-run passes |
| B8 jobs.jsonl conformance, digest re-derives | pass | **fail** |
| B9 orphaned marker reported honestly | pass | pass |
| B10 recurring job offered, consent recorded | offer passes | offer passes |
| B11 canary before setup is called done | not reachable without an OAuth token | **fail** |
| B12 fit judgment | pass | pass, 3 of 3 reps |
| B13 read path budget | pass | pass |
| B14 wall-clock and metered calls vs RED | pass | pass |

B3 is exact: **zero** calls to the `status` route in any run of the matrix, on either model.

B6 is not gradable on haiku because that run issued its detail reads from a shell variable, so the
transcript cannot pair each id with the row it came from. On sonnet all 46 reads carried both a
`posting_id` and its own row's `source_url`, and every id traced to an earlier search response.

B10's offer half passes on both models. Its other half — a recorded consent date — cannot pass in a
headless case, because nobody is there to say yes; a run that records one anyway would be wrong.

B11 needs a long-lived token that only an interactive `claude setup-token` can produce, so the canary
cannot run inside this suite. On sonnet the flow behaves honestly without it: it records consent,
states the blocker, leaves the registry unwritten, and tells the user the schedule is not live. It
does leave the launchd job file on disk, which the turn-off recipe says to remove.

## Detail-read spread on one seed

Five runs of the identical `headless-run` seed — two enabled queries across two sources, an empty
event log — spent 25, 36, 39, 46 and 49 detail reads. Every one closed healthy and every one stayed
under RED's 64 metered calls, but the summary scan's threshold is set by model judgment, so the cost
of one pass varies close to twofold between runs of the same configuration.


## What did not reach green

Three behaviors, each with a different owner.

**One model cannot carry a full pass.** On haiku a run judges a fraction of what it finds — 4 of 137
on one first run, 36 of 91 on a headless pass — and still writes a complete, healthy close. The same
skill text on sonnet, on the same seed, judges every candidate and writes a record whose numbers
re-derive exactly, twice. The close wording is not the cause: handed a small, settled state, haiku
writes a correct record and a correct digest in five isolated reps out of five. This is a limit on
how much per-posting bookkeeping fits through one context, and no wording closes it.

**The workspace validator does not catch it.** `validate-workspace.sh --post-close` exits 0 on a
record missing two required fields, on a digest whose counts line contradicts the event log beside
it, and on a healthy close over a hundred unjudged candidates. It checks the close state's presence
and spelling, the timestamp formats, the configuration keys, and the absence of leftovers. It is the
gate the skills tell a run to satisfy, so a run that satisfies it believes it closed correctly.

**Skill selection misses the front door's own trigger phrases on haiku.** Five of nine first-run
reps went to the preferences interview instead of the front door, and the one scheduling prompt
matched no skill at all. Both prompts are sentences the front door's description lists as triggers.
This is not visible as a routing failure from the outside: entered directly, the interview correctly
opens by asking a question, so the run looks like an interview that stalled rather than a front door
that was never reached.

The canary that proves a recurring job (B11) needs a long-lived token an interactive login creates,
so it stays unproven here and belongs to the human dogfood.
