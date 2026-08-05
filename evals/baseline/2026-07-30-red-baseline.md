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
| time to first live result (headless quickstart) | 190 s | 88–121 s | 107 s |
| full first-run onboarding wall-clock | 28–41 min | 8.6 min | 4.4 min |
| metered API calls, onboarding run | 37 | 13 | 10 |
| metered API calls, one daily pass (same seed) | 64 | 43–50 | 40 |
| lines read before the first API call | ~3,550 (9 files) | 271 (4 files) | 224–248 (2–4 files) |
| position of the greeting among visible outputs | 4th | 2nd or 3rd | 2nd |
| permission dialogs in the first 10 min | 35 | not measurable | not measurable |

### Measurement condition for the timing rows above

**In the GREEN columns**, time to first live result is the moment a **metered** `search-jobs` result
came back — not the free `agent-data docs` call that precedes it in some runs. An earlier draft took
the docs call for the search and understated one figure by 32 s.

**RED's 190 s was not re-measured under that rule.** It came from the earlier harness and its own
first-result event was never re-checked, so the two columns are not known to be measured the same
way. The direction is safe for the release argument: if RED also timed a free call, the true RED
figure is larger, and the GREEN figures beat it by more. It is not safe for anything that needs the
gap's size.

What is known about the service these runs ran against, and nothing beyond it: every session behind
the GREEN column ran inside the window **18:18:28Z–20:11:25Z on 2026-07-31**, and no session was
running at the moment a latency fix to the job-postings API was reported. **The deploy's own
timestamp was not recorded anywhere**, so whether these runs preceded it is not established here.

Treat the timing rows accordingly. A run made under a different service latency is not comparable
with these, in either direction, and refreshing the GREEN timing figures alone would compare two
different services; a future pass that wants timing numbers needs a RED equivalent measured beside
them.

The rows that carry the release argument do not depend on service latency and stay comparable:
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
| quickstart time to first live result ≤ 190 s | yes — worst case 121 s (sonnet reps 121 s and 88 s; haiku 107 s) |
| headless metered calls ≤ 64 on the same seed | yes — 43 and 50 across two sonnet reps, 40 haiku |
| B1–B12 pass on both models | **no** — four rows, below |

The time-to-first-result row is the one target that rests on a timing measurement, so it carries the
caveat above: what the service was doing under these runs is only partly known, and the row should
not be refreshed on its own.

## Behavior rows

| row | sonnet | haiku |
|---|---|---|
| B1 first message, plain language | 1 of 2 reps on ordering; content right everywhere | pass |
| B2 concepts defined at first mention | pass | pass |
| B3 whoami-only preflight, no `status` call | pass | pass |
| B4 cost context before the first metered call | pass | pass |
| B5 summary scan reduces detail reads | pass | pass |
| B6 id + source_url pairing, 0 fabricated ids | pass | not gradable |
| B7 detail-read fault fallback | fallback half: failed, **fixed**, re-run passes. Stop-after-two half: **not exercised** | fallback half: failed, **fixed**, re-run passes. Stop-after-two half **and** the call-shape half: **not exercised** |
| B8 jobs.jsonl conformance, digest re-derives | pass | **fail** |
| B9 orphaned marker reported honestly | pass | pass |
| B10 recurring job offered, consent recorded | offer passes | offer passes |
| B11 canary before setup is called done | not reachable without an OAuth token | **fail** |
| B12 fit judgment | pass | pass, 3 of 3 reps |
| B13 read path budget | pass | pass |
| B14 wall-clock and metered calls vs RED | pass | pass |

B3 is exact: **zero** calls to the `status` route in any run of the matrix, on either model.

B7 has two halves and only one of them was exercised. The half that was — judge a posting from its
summary row when the detail read comes back rejected, rather than stopping — failed on both models,
was fixed, and passes on both re-runs. The other half, "stop after 2 consecutive failed detail reads
and attempt no more", was **not exercised on either model**: the case supplies three postings and the
sonnet re-run read all three, so there was never a third attempt to withhold. On haiku a further half
did not take either — the run never sent a valid call in the documented shape, reaching its (correct)
"cannot fetch" conclusion by trying the open web and an invented sub-command instead. The fallback is
fixed; the stop rule and the call shape remain unproven live.

B6 is not gradable on haiku because that run issued its detail reads from a shell variable, so the
transcript cannot pair each id with the row it came from. On sonnet all 46 reads carried both a
`posting_id` and its own row's `source_url`, and every id traced to an earlier search response.

B10's offer half passes on both models. Its other half — a recorded consent date — cannot pass in a
headless case, because nobody is there to say yes; a run that records one anyway would be wrong.

B11 needs a long-lived token that only an interactive `claude setup-token` can produce, so the canary
cannot run inside this suite. On sonnet the flow behaves honestly without it: it records consent,
states the blocker, leaves the registry unwritten, and tells the user the schedule is not live.

One thing it got wrong, since fixed. It left the launchd job file on disk — a job the user had just
been told is not working, which macOS loads at the next login. The recipe has two endings, and a
canary that cannot be fired is not the passing one, so the job should have been removed. The owning
skill was reworded to name that ending explicitly, and the case was re-run twice on sonnet: both runs
left no job file, nothing loaded, and no cron line.

**What that re-run does not prove.** Neither post-fix run installed anything — both stopped earlier,
at the missing credential — so the removal branch itself has still never been exercised. The re-run
establishes the outcome a user would see, not that the reworded branch fires.

## Detail-read spread on one seed

Five sonnet runs of the identical `headless-run` seed — two enabled queries across two sources, an
empty event log — spent 25, 36, 39, 46 and 49 detail reads. Every one closed healthy and every one
stayed under RED's 64 metered calls, but the summary scan's threshold is set by model judgment, so the cost
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

---

# LOCALITY — 2026-08-01 live evals after the skill locality restructure

The restructure moved every file a skill reads to an address inside the skill that reads it, and
promoted the two shared references to skills — five skills became seven. Two questions had to be
answered with numbers before it could ship: do files resolve, and did the two extra skills make
routing worse. Both were measured live on sonnet and haiku. Aggregates only, like the blocks above: no paths, no run ids, no transcripts.

## Pointer misses, before and after

**The mechanism is the argument here. The counts below support it and cannot carry it alone.**

Two of the three miss shapes 0.8.0 measured are now impossible rather than merely rarer, and the
third — the one the evals caught *after* the restructure — is gated in the seven written forms
below.
Each row was put back into a single SKILL.md and the suite run, so these are failure counts, not
expectations:

| pointer shape reintroduced | tests that fail | which |
|---|---|---|
| `../../shared/references/runbook.md` | **11** | `test_every_reference_resolves_in_place_on_host` (8, one per host), `test_every_plugin_file_a_skill_names_exists`, `test_no_computed_pointer_survives_anywhere`, `test_no_skill_counts_directory_steps_up` |
| `<plugin-root>/templates/x.yaml` | **2** | `test_every_plugin_file_a_skill_names_exists`, `test_no_computed_pointer_survives_anywhere` |
| a reference skill naming its own `scripts/<file>` | **1** | `test_no_reference_skill_addresses_a_file_from_its_own_directory` |
| the same with a leading `./` | **1** | the same test |
| the same as a bare `templates/` or `scripts/` | **2** | the same test, plus `test_every_plugin_file_a_skill_names_exists` |
| the same as a bare file name, no directory | **1** | the same test |
| a bare file name with a leading `./` | **1** | the same test |
| the same inside a fenced command, or after `cd … &&` | **1** | the same test |
| a file in a directory the gate was never told about | **1** | the same test |

**What "gated" claims, exactly.** Those rows are ways of writing one defect, and the gate has been
declared working twice and defeated twice — each time by a way of writing the defect that no test
case covered, never by a flaw anyone found by reading the rule. Its first version required a file
name with an extension and could not see past a leading `./`, the form the failing run executed;
its second reopened the same `./` hole in the rule it had just added. **Sixteen written forms are
test cases in the suite now, by name — twelve in the parametrize list, three more in
`test_the_reference_gate_covers_a_directory_it_was_never_told_about`, one in
`test_the_bare_name_rule_leaves_the_routing_description_alone` — and the claim goes no further
than those sixteen.** Each one
someone gets past the gate with becomes a permanent case, which is the only thing that has actually
worked. Nothing here gates a defect nobody has written down yet, and past experience says more
forms exist.

The two template paths those shapes missed four times in the 0.8.0 runs are opened four times in the
runs after, and missed none.

Behavior row B15, graded by `evals/grade_b15.py`, which replays a run's transcript and checks every
path under the plugin directory the run opened — by `Read`, or named in a `Bash` command, including
a path reached through `cd` and one the shell reported it could not open — against the tree that run
actually saw. Both columns are graded by the same script at the same width.

**Two 0.8.0 denominators, because the choice changes the headline.** The window named above holds
**24 sessions across six cases**. Only two of those cases — `quickstart` and `headless-run` — were
re-run after the restructure, so a like-for-like comparison uses the 12 sessions of those two cases,
and a whole-window comparison uses all 24. Both are given; neither is picked for its result.

| | 0.8.0, whole window (24 sessions, six cases) | 0.8.0, the two cases re-run after (12 sessions) | after the restructure (9 sessions, the same two cases) |
|---|---|---|---|
| plugin file opens | 136 | 91 | 54 |
| **opens that missed** | **6 (4.4%)** | **6 (6.6%)** | **2 (3.7%)** |
| runs with at least one failed open | 4 of 24 | 4 of 12 | 2 of 9 |
| recovery searches after a miss | 9 | 9 | 5 |
| references reached by skill name instead of by path | 0 | 0 | 25 |

Both 0.8.0 columns carry the same six misses; they differ only in how many opens sit beside them.
The `fit`, `fault-503`, `kill-midrun` and `schedule` sessions add 45 opens and no misses.

**On the counts alone, nothing is established.** Fisher exact two-sided against the post column is
**p = 1.000** on the whole window and **p = 0.710** on the two re-run cases; on runs with at least
one failed open, p = 0.659. Even a clean sweep would not have carried the strong claim: zero misses
in 54 opens has probability 0.025 under the two-case 0.8.0 rate (exact binomial), which is
suggestive and not decisive. **What these numbers support is that the restructure reduced pointer
misses — not that pointer misses went away, and on the wider denominator not even that much.**

**B15's verdict: it fails on 2 of the 9 runs after**, both haiku daily passes. The row's pass rule
is a miss count of zero and those runs have one each; it passes on every sonnet run and on every
`quickstart` run.

The misses did not go away. Two failed opens survive in the runs after, and neither is one of the
shapes the restructure removed:

- A skill's text told the agent to run "this skill's" script. The agent was executing a *different*
  skill at the time — the sentence lives in a reference that siblings read — so it resolved the
  possessive against its own directory, failed, and spent three `ls` calls over about 7 seconds
  finding the real path. Fixed here: both pointers in that reference now name
  `skills/<skill>/scripts/…` in full.
- An agent read a reference by its **directory** rather than its `SKILL.md`, got `EISDIR`, and spent
  two `find` calls recovering. A reference is only a directory to aim at because it became a skill,
  so this shape is new since the promotion.

The third 0.8.0 shape — a model inventing a reference filename — remains possible, because nothing
stops a model naming a file that was never there. It did not occur in the nine runs after.

## Read path, first result, metered calls

| measurement | GREEN sonnet | GREEN haiku | LOCALITY sonnet | LOCALITY haiku |
|---|---|---|---|---|
| lines read before the first API call, first run | 271 (4 files) | 224–248 (2–4 files) | 98 (5 files) | not reached |
| lines read before the first API call, daily pass | 252 (4 files) | — | 49 (2 files) | 18, 18, 173 (1–6 files) |
| time to first live result, first run | 88–121 s | 107 s | 94 s | not reached |
| time to first live result, daily pass | — | — | 48 s | 57 s and 66 s |
| metered calls, first run | 13 | 10 | 17 | not reached |
| metered calls, one daily pass (same seed) | 43–50 | 40 | 55 | 31 and 44 |

**Read the read-path rows with one correction.** They no longer count the same text. A reference now
arrives through the Skill tool rather than a `Read`, so its body never appears as read lines. What
the rows support is that fewer files are opened — not that less text reaches the model, and not that
every open lands: two of 54 still did not, and they are described above.

**The timing row is not comparable to the GREEN column.** A latency fix to the job-postings API was
deployed on 2026-07-31; every GREEN timing number predates it and every LOCALITY number postdates
it, so the two describe different services. Metered-call counts, read-path lines, and every behavior
pass or fail are latency-independent and stay comparable across all three blocks.

The sonnet daily pass spent 55 metered calls against the GREEN column's 43 and 50. Its 51 detail
reads sit just above the 25–49 spread five earlier sonnet runs produced from the identical seed, so
this is the same variation the GREEN block already records for this configuration rather than a new
cost. It stays under RED's 64.

## Routing across the now-seven skills

Behavior row B16, case `evals/cases/triggering.yaml`. Each trigger phrase runs as its own session
from a fresh workspace, 9 reps per phrase per model — the rep count behind the 0.8.0 skill-selection
finding, so the two are comparable. What is graded is which skill the session loaded. **"before" is
this same case run against the plugin as it stood one commit before the promotion**, on the same day
and the same machine, not a figure carried over from an earlier block.

| phrase | sonnet before | sonnet after | haiku before | haiku after |
|---|---|---|---|---|
| set up job search | 9/9 | 9/9 | 5/9 | **9/9** |
| the README quickstart sentence | 9/9 | 9/9 | 0/9 | 0/9 |
| keep this running daily | 9/9 | 9/9 | 0/9 | 0/9 |
| check my job search | 9/9 | 9/9 | 3/9 | 2/9 |
| run a search now | 9/9 | 9/9 | 9/9 | 9/9 |
| why did my run fail | 9/9 | 9/9 | 0/9 | 0/9 |

No phrase routes measurably worse than before the promotion, and one routes much better: on haiku,
`set up job search` went from five reps in nine to nine in nine. The one phrase reading lower —
`check my job search` on haiku — was re-run at 27 reps a side: 10 of 27 before, 8 of 27 after,
Fisher exact two-sided p = 0.773. In both conditions its majority destination is `job-search-run`, a
skill the promotion did not touch.

The phrases haiku still misses do not lose to a skill in this pack. `keep this running daily` goes
to the host's own scheduling skill, `why did my run fail` to a general debugging skill, and the
README quickstart sentence to the preferences interview — all three at identical rates before and
after. That is the same finding the GREEN block records, now measured at nine reps per phrase
instead of one.

## What the promotion put at risk, measured and fixed

A skill that other skills consult claims no user phrases, so any user sentence selecting one is a
routing defect. Three probes tested exactly that, each using a promoted skill's own most user-shaped
description phrase. The number is how often the probe selected a reference skill:

| probe | sonnet as promoted | sonnet shipping | haiku as promoted | haiku shipping |
|---|---|---|---|---|
| a cost question | **9/9** | 0/9 | 0/9 | 0/9 |
| a workspace question | **9/9** | 0/9 | 0/9 | 0/9 |
| naming the agent-data CLI | 0/9 | 0/9 | 2/9 | 2/9 |

The first shipped descriptions took two ordinary user questions on sonnet in every rep. Appending a
redirect did not fix it — the cost probe still landed 9 of 9. What fixed it was putting the redirect
**first**, ahead of what the file holds, and rewording the one phrase that reads like a user's
sentence. Five rounds of measurement say one thing: the router matches the description's own words,
a negative clause does not cancel a phrase the description also contains, and a redirect works only
once it precedes the content list. Both descriptions stay inside the 200-character budget the
frontmatter test enforces.

One residual, which no wording moved: on haiku, naming the agent-data CLI selects the job-postings
reference on 2 reps of 9. That points at the skill's name rather than its description — it shares a
prefix with a separate marketplace skill that claims that phrase, and both load in the same list.
Before the promotion those same reps selected no skill at all, so nothing that worked stopped
working.

## Measurement condition

Every figure above was measured on 2026-08-01 UTC, one session at a time, against the live API, with
the plugin loaded from the working tree. The before column comes from checking the tree out at the
last commit before the promotion and running the identical case.

Two behavior results outside B15 and B16 are worth recording. One haiku daily pass of three stopped
after judging a single posting and left the run open — no record, no digest, an orphaned start
marker; the other two closed healthy. And no fresh-workspace run in this block read a previous
eval's captured workspace, with the captured briefs renamed out of the way for the duration.
