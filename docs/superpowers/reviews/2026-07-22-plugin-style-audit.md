---
type: review
title: "Plugin + skills audit against the private style guides"
status: current
verified: partial
last_reviewed: 2026-07-22
reviewed_commit: de42734
claimed_paths: [skills, shared, .claude-plugin, .opencode, scripts, tests, .github]
owner_area: Skills & references
repos: [job-search-os]
---

# Plugin + skills audit against the private style guides

Full-surface review of the five skills, their references, the shared references, the mechanics
scripts, the host manifests, the eval suite, and CI — against **every** rule in
`docs-private/prompt-style-guide/` (101 rules + the anti-pattern catalog) and
`docs-private/agent-agnostic-skills/` (122 rules + 42 anti-patterns). 278 items visited.

Rule IDs below resolve against those two rule indexes (`09-checklist-and-rule-index.md` and
`14-checklist-and-rule-index.md`). Rules the repo marks **reject** were skipped as out of scope.

**Scope note.** The `2026-07-21-job-search-robustness` design/plan on this branch was excluded at the
requester's direction; this audit supersedes it and reaches its conclusions independently.

## Verdict

The pack is in good shape on the dimensions it has invested in — voice, consent, error rendering,
honest completion, trust demotion in the delegated worker, host-neutral language. It fails on one
axis, and that axis produced both dogfooding failures:

> **The pack has an ownership *metaphor*, not an ownership *boundary*.** Who may call the job source,
> who may judge a posting, and who may write run artifacts is stated in `ARCHITECTURE.md`, in the
> operator manual's "when to use it" table, and in soft framing in the front door — none of which is a
> constraint at the moment the decision is made. A repo-wide grep for any exclusivity statement in
> `shared/references/` returns **nothing**.

The verbosity concern is real but it is a *symptom*, not the disease. `job-search-run/SKILL.md` is 686
lines / 7,772 words because roughly 2,200 of those words are hand-maintained restatements of contracts
that already have canonical homes — and those copies have measurably drifted.

Counts: **12 MUST-rule violations**, ~67 SHOULD/CONSIDER violations, **11 anti-pattern hits**.

## Part 1 — The two dogfooding failures, root-caused

### Failure 1 — the front door bypassed both owners

Four independent causes, each verified. Any one of them alone makes the bypass a locally correct
reading of the pack's own text.

**1a. No prohibition exists.** A grep across `skills/job-search/SKILL.md`, `references/onboarding.md`,
and `references/home.md` for any form of "never call / do not judge / not yourself" returns one hit, and
it is about composing a host authorization sentence. Nothing forbids the front door from searching,
judging, or writing artifacts. *(PSG-SUB-12, AAS-FORM-10)*

**1b. The only stated exclusion is keyed to interactivity, not to ownership.**
`skills/job-search/SKILL.md:17` — "Not the place for a **non-interactive** run — that's
`job-search-run`". An interactive onboarding pull is not a non-interactive run, so the one exclusion on
the page reads as not applying. *(PSG-SUB-01 MUST, AAS-AUTO-10)*

**1c. The front door is handed the means and only softly discouraged from using them.**
`skills/job-search/SKILL.md:87-92` puts `agent-data-contract.md` — the file carrying the literal
`search-jobs` / `get-posting` invocations and the listing id — inside a mandatory **"Read and follow
exactly"** list, described as "the source contract `job-search-run` honors". Means, no gate.
*(PSG-SUB-12)*

**1d. `evaluate-job-fit` is named nowhere in the front door.** Grep across all three front-door files
returns zero hits. Meanwhile `job-search/SKILL.md:68-71` hands the front door the full verdict
vocabulary in the second person ("Say **relevant or not**, and if relevant **weak / moderate /
strong**"). The front door is given the judge's output language and never told the judge exists.
*(AAS-PROC-02, AAS-TRIG-03, PSG-TOOL-03, PSG-ANTI-10)*

Aggravating: `skills/job-search/SKILL.md:3` positively claims the capability — "First run reaches real
live matches fast — a one-question sketch, **then live postings**". A model acting from the
always-resident description alone has been told the whole procedure and never told to delegate.
*(AAS-ANTI-10, AAS-TRIG-01)*

### Failure 2 — "web scraping" broadened to "data extraction", then called STRONG

Failure 1 removed the guardrail; two composition bugs supplied the error.

**2a. The brief-drafting classifier demotes a stated domain out of Must-haves — by rule.**
`onboarding.md:182-183` and `job-preference-interview/SKILL.md:99-100` both say: *"a stated **role /
location / pay floor** becomes a **Must-have**, softer wants go to **Strong preferences /
Nice-to-haves**."* That is a closed three-item list. A stated **domain** is not in it, so the user's
most specific constraint is routed to Strong preferences by the rule itself.

**2b. Nothing requires the user's own wording to survive.** The guardrail present is *"Don't invent
preferences they didn't express"* — a ban on **addition**. The failure was **generalization** of an
expressed preference, the opposite direction, and it is uncovered. The licence that does exist —
*"plus safe, direct implications"* — is an unbounded virtue phrase with an expanding example.
"verbatim" appears five times in `onboarding.md`, every one of them about reciting a *question*, an
*error fix*, or a *run recipe* — never about preserving what the user said they want. *(PSG-F-09)*

**2c. The band rule then permits the outcome.** `evaluate-job-fit/SKILL.md:39` — `strong` = "hits the
must-haves and **most strong preferences**". With the domain demoted to a strong preference, the other
strong preferences (IC, remote, startup stage) outvote it and `strong` is earned. The anti-slip
caution four lines below names this exact case ("the domain is adjacent rather than the one the brief
names") but it is a soft warning against a rule that allows the result. *(PSG-SUB-05, AAS-EX-03)*

**2d. The steer example anchors the worker on the answer.** `job-search-run/SKILL.md:626` illustrates a
steer as *"**Strong** on AI/LLM-IC-Python; confirm remote-US"* — a flat band assertion in the exact
vocabulary the worker must choose independently, in the same sentence that bans verdicts ("never a
verdict"). `:416` repeats the shape. *(PSG-F-08, AAS-EX-02)*

**2e. No eval could have caught it.** Across all 185 eval scenarios, **not one expectation requires
`moderate` or `weak`** — four require `strong`. A model that answers "strong" for every relevant
posting passes every band assertion in the suite. *(AAS-TEST-03)*

### The structural lesson

`query-strategy.md`'s doctrine — *"Queries maximize plausible recall; the Job Preferences Brief
supplies precision"* — is correct **only** if the brief's precision is preserved and the judge applies
it. Those are two halves of one contract living in two files with no shared assertion binding them, and
no hard boundary between the layer that broadens and the layer that discriminates. When the front door
also judges, it carries the recall-maximizing frame into the step where it is exactly wrong.

`query-strategy.md:57` states the belief that licenses this outright: *"Broad queries cost no
precision"* — an ungraded absolute about probabilistic judgment, in a file that correctly names the
two-sided cost 45 lines earlier. *(PSG-F-14)*

## Part 2 — Verbosity and overload

### Measurements

| Surface | Lines | Words | vs AAS-SKILL-04 budget (~500 lines / ~5,000 tokens) |
|---|---:|---:|---|
| `job-search-run/SKILL.md` | **686** | **7,772** | **+37% lines, ~2× tokens** |
| `job-search-agent/SKILL.md` | 228 | 3,124 | ok |
| `job-preference-interview/SKILL.md` | 203 | 2,193 | ok |
| `job-search/SKILL.md` | 95 | 1,126 | ok |
| `evaluate-job-fit/SKILL.md` | 76 | 842 | ok |

Only one skill breaches, and the meta/reference escape hatch does not apply: its content is
demonstrably not all activation-critical. It also ships **no `references/` directory at all** — there
is nowhere for depth to go.

### Where the 7,772 words are

| Section | Lines | Words | Assessment |
|---|---:|---:|---|
| Lifecycle coordinator | 103 | 1,206 | Hand-copy of `run-lifecycle.md` — **already drifted** |
| Loop | 403 | 4,607 | Real work, but step 5's field enumeration duplicates `conventions.md` |
| Attempt accounting | 61 | 609 | Bookkeeping; `conventions.md` owns the `agent_data_usage` schema |
| Run health / surfacing | 32 | 403 | Largely `errors.md` restated |
| Everything else | 87 | 947 | Keep |

### The drift, demonstrated

`run-lifecycle.md:461-462` (canonical): reconstruct *"phase, **immutable source order**, **primary**
posting states, and attempt identities"*.
`job-search-run/SKILL.md:103` (hand-copy): reconstruct *"phase, posting states, and attempt
identities"*.

Two hand-maintained copies of one rule, already diverging on which state must survive compaction. No
build generates the block — `scripts/build.sh` writes only the build stamp — so the
`<!-- run-lifecycle-runner:coordinator -->` fences are decoration, not a sync contract.
*(AAS-BOUND-03, AAS-ANTI-04, PSG-ANTI-02)*

Every persistence field the runner enumerates (`first_page_rows`, `continuation_rows`,
`deeper_coverage_nudge_eligible`, `stop_reason`, `selected_for_review`, …) is already defined in
`conventions.md`.

### Recommendation: thin, don't split

**Do not create sibling skills.** AAS-BOUND-07 is explicit: split only at a genuine scope or
execution-model seam; the sanctioned response to size is a references split. The runner's phases share
one run's mutable state — that is not a seam.

Proposed shape for `job-search-run/` (target ~250–300 lines):

- **Delete** the Lifecycle coordinator block; keep ~10 lines of genuinely runner-specific ordering plus
  the one-hop pointer the block's own first sentence already implies.
- **New** `references/retrieval-and-selection.md` — stream construction, the pagination branch table,
  the finite allocator, the scratch lifecycle. Load-trigger: *"when paginating past the first page."*
- **New** `references/accounting.md` — the attempt-accounting tables and the decimal arithmetic.
  Load-trigger: *"before the first metered attempt."*
- **Reduce** step 5's field lists to a pointer at `conventions.md` § `runs/<run_id>.json`.
- **Keep in the body:** scope + exclusive ownership, the phase table, the gates before metered calls /
  persistence / reporting, the scan-and-steer, the delegation contract, narration, the completion
  self-check.

### The references have no maps

**Eight of ten `shared/references/*.md` files carry no table of contents**, including `internals.md`
(926 lines / 9,091 words), `run-lifecycle.md` (705), `conventions.md` (658), and `errors.md` (294).
AAS-BOUND-05 wants a ToC over ~100 lines and grep hints for very large files. Only `onboarding.md`,
`home.md`, and `customization.md` carry the `**Contents:**` line.

This matters for the thinning plan: pushing more depth into unmapped references makes partial-read
failures *worse*, not better. Add the maps first.

## Part 3 — Verified defects that bite regardless of style

These I confirmed line-by-line. They are not style opinions.

1. **`lifecycle-fold.sh` is invoked from 17 places and never once with a resolvable path.**
   `job-search/SKILL.md:93`, `home.md:9`, `onboarding.md:340,455`, `job-search-run/SKILL.md:93`,
   `job-search-agent/SKILL.md:63`, `scheduling-and-consent.md:111,196`, `customization.md:233`,
   `internals.md:10,800,817`, `conventions.md:271`, `errors.md:8`. Same for `lifecycle-append.sh` at
   `job-search-run/SKILL.md:54`. By contrast `event-log-append.sh` and `workspace-discovery.sh` **are**
   properly pathed in the same file. *(AAS-SKILL-03 MUST)*

2. **Two dangling build-stamp pointers.** `update.md:10` and `conventions.md:495` both say
   `` `references/build-stamp.md` `` — a fan-out-era path that from `shared/references/` resolves to
   `shared/references/references/build-stamp.md`, which does not exist. This is step 1 of the update
   procedure. `internals.md:901` gets it right. *(AAS-SKILL-03 MUST, AAS-ANTI-42)*

3. **The pointer gate cannot see either of them.** `tests/test_reference_resolution.py:329`
   (`_pointer_files`) scans only `skills/*/SKILL.md` plus four skill-local playbooks — **all of
   `shared/references/*.md` is excluded**, which is exactly where both dangling pointers live. Its
   sibling `_script_pointer_files()` already globs the shared tree. One-line fix. *(AAS-TEST-11)*

4. **Repo-root-relative template paths inside skill files.** `onboarding.md:139,140,302` copy
   `templates/workspace.gitignore` and `templates/config.example.yaml`; from an installed skill the cwd
   is the user's project, so these resolve nowhere. `job-preference-interview/SKILL.md:41` repeats it.
   *(AAS-SKILL-03 MUST, AAS-ANTI-21)*

5. **The eval suite contradicts itself.** `skills/job-search/evals/evals.json` eval 2 expects *"Prints
   the verbatim /loop recipe block (scheduling was declined…)"*; eval 47 expects *"Does NOT dump the
   recurring-run or one-off-run recipe blocks on decline"*; `onboarding.md:411-414` forbids it. Correct
   behavior fails eval 2. `TESTING.md:174` carries the same wrong expectation. *(AAS-ANTI-41)*

6. **The scheduling gate test asserts five of six gates.** `tests/test_scheduling_eligibility.py:36` —
   the comment says "The six eligibility gates", the tuple lists five: `inspectable` is missing, so
   that gate is never asserted. 617 passing tests hide it.

7. **The opencode session-start injection makes a false claim about the repo.**
   `.opencode/plugins/job-search.js:12,16` both point at `shared/references/platform/opencode.md`. That
   directory was deleted in the adapter teardown and does not exist. This text is injected into every
   opencode session. *(AAS-PORT-07)*

8. **`CHANGELOG.md` is stuck at 0.6.0** while all six manifests and the build stamp read 0.6.1.
   `check_release_integrity.py` verifies sync across the six manifests and audits nothing beyond them.
   *(AAS-DIST-01)*

9. **A false data-locality guarantee in the one skill whose job is answering it.**
   `job-search-agent/SKILL.md:22` — *"All data lives under `~/.job-search/`"*. The registry is at
   `~/.config/job-search/config.json` (`internals.md:20`), explicitly *"not a workspace file"*
   (`conventions.md:27`), and it stores the user's actual query keywords in
   `query_health_nudge.search_shape`. The API key lives in `~/.agent-data/config.json`. Neither is
   covered by the workspace `.gitignore`. *(PSG-COMM-20 MUST)*

10. **The runner is licensed to manufacture a verdict.** `job-search-run/SKILL.md:524` says to
    **"coerce anything else"** when a returned `match` is out of vocabulary. Since `match` may be null
    only when `relevant` is false, the only available coercion is *to a band* — inventing a judgment the
    evaluator never returned and persisting it to `jobs.jsonl` and the digest. The canonical wording in
    `parallelism.md:132` is *"coerced **or rejected**, never persisted"*; the runner dropped the honest
    exit. *(PSG-COMM-09 MUST)*

11. **Unconsented network egress in a "private, local-first" pack.** `update.md:47-50` fetches the
    author-hosted `raw.githubusercontent.com/agent-data/job-search` stamp whenever the 24h cache is
    stale — no opt-in, no disclosure. It degrades gracefully, but it discloses pack usage to the
    author's host by default. *(AAS-ANTI-36)*

12. **No frontmatter/naming validator gates anything.** CI runs pytest, `philosophy_guard`, `doc_lint`
    (scoped to `docs/` + three root files), release integrity, and the build-stamp sync. Nothing
    validates `skills/*/SKILL.md` frontmatter — the closed key set, `name` ↔ directory equality, or the
    description cap. The only such check in the repo is a hand-run single-host command at
    `TESTING.md:118`. *(AAS-TEST-01)*

13. **No eval asserts delegation.** There are five discovery evals — one per skill — and they all test
    that the *right skill is selected*. None tests that once `job-search` is selected it then **hands
    off**. Worse, `skills/job-search/evals/evals.json:3` instructs the eval *driver* to run
    `job-search-run` itself, so eval 1's "Runs a real sample job-search-run" is satisfied by the
    harness, not the skill. *(AAS-TEST-16)*

## Part 4 — Rule-by-rule results

All 278 items visited. Violations only; everything not listed passed or was out of scope.

**Prompt style guide** (27 violations of 101 rules; MUST violations in **bold**)

| Doc | Violated |
|---|---|
| 01 Foundations | **F-01**, **F-02**, **F-04**, F-05, F-07, F-08, F-09, F-14 |
| 03 Tool definitions | **TOOL-01**, TOOL-03, **TOOL-05**, TOOL-10, TOOL-13, TOOL-15 |
| 04 Subagents | **SUB-01**, SUB-05, SUB-09, SUB-12, **SUB-13** |
| 05 Injections | **INJ-01** |
| 06 Communication | **COMM-09**, **COMM-20** |
| 07 Safety | SAFE-10 |
| 08 Anti-patterns | ANTI-02, ANTI-07, ANTI-09, ANTI-10 |

**Agent-agnostic skill packs** (52 violations of 122 rules + 11 anti-pattern hits)

| Doc | Violated |
|---|---|
| 01 Pack anatomy | PACK-02, PACK-04, PACK-06 |
| 02 Skill anatomy | **SKILL-03**, SKILL-04, SKILL-08, SKILL-09 |
| 03 Boundaries | **BOUND-01**, BOUND-02, BOUND-03, BOUND-05 |
| 04 Triggering | TRIG-01, TRIG-03, TRIG-05 |
| 05 Guidance form | FORM-01, FORM-03, FORM-04, FORM-07, FORM-08, FORM-09, FORM-10, FORM-14 |
| 06 Examples | EX-01, EX-02, EX-03, EX-04 |
| 07 Autonomy | AUTO-06, AUTO-10, AUTO-11 |
| 08 Process vs domain | PROC-02 |
| 09 Neutral language | LANG-02 |
| 10 Portability | PORT-04, PORT-05, PORT-07 |
| 11 Distribution | DIST-01, DIST-06 |
| 12 Testing | TEST-01, TEST-03, TEST-04, TEST-11, TEST-16 |
| 13 Anti-patterns | ANTI-04, ANTI-10, ANTI-13, ANTI-21, ANTI-29, ANTI-32, ANTI-35, ANTI-36, ANTI-38, ANTI-41, ANTI-42 |

**Adjudicated as compliant (worth recording):**

- **AAS-SKILL-03 and `../../shared/…`** — reaching outside the skill root is *sanctioned* by the rule's
  own text ("acceptable only via a plain relative path that resolves on any host — and couples you to
  bundle-install"), and the pack states that premise in `build.sh:5-8`, `AGENTS.md:27`, and
  `CONTRIBUTING.md:10-12`. The SKILL-03 violations above are unresolvable paths, not the shared reach.
- **AAS-SKILL-02** — all five frontmatters now carry only `name` + `description`. The Claude-only keys
  the guide cites as this repo's failure case are gone.
- **AAS-LANG-04 (exact model binding)** — a defensible repo-specific adaptation, not a violation: no
  model id is hardcoded in a neutral body, and the slot is a REQUIRED value per AAS-AUTO-07.
- **AAS-PORT-01 (MUST)** — every optional capability (subagents, notifications, shell runtime,
  scheduler, question box) carries a named degradation. Clean.
- **AAS-TEST-02** — behavioral evals correctly stay out of the merge gate.

**Landing on open tensions — not resolved here:**

- **AAS-AUTO-11** (`detail_model_default` = "least-powerful available model that performs fit judgment
  well" vs. the mid-tier reviewer floor for judgment work) → tension register AAS-T-03. Worth
  revisiting given failure 2, but it is not this audit's call.
- **AAS-FORM-01** (prohibition wall vs. positive recipe in the front door's greeting block) → AAS-T-06.
- **AAS-TRIG-01** (the "what-half" of a description) → AAS-T-05. The *workflow-ban* half is common
  ground on both sides of that tension, and that is the half violated.

## Part 5 — What I would do, in order

**P0 — close the ownership hole (fixes failure 1).**

1. Add an exclusive-ownership statement to `shared/references/` as a single canonical home, and fence
   it in `job-search/SKILL.md` as a Principle stated **by action, not by interactivity**: *never search
   the job source, judge a posting, or write `jobs.jsonl`/a digest here; `job-search-run` owns the pull,
   `evaluate-job-fit` owns the verdict.* Pair each prohibition with its alternative (AAS-FORM-10).
2. Add `evaluate-job-fit` to `job-search`'s description negative scope **and** to its mental-model
   paragraph, and route to it from both playbooks and the home quick actions.
3. Cut the workflow recipe from `job-search`'s description; state the delegation instead of the steps.
4. Narrow the front door's mandatory read of `agent-data-contract.md` to the auth/tier facts onboarding
   actually consumes.
5. Add the ownership eval: drive only `job-search`, assert on effects the runner alone produces (a
   `runs/<run_id>.json` plus its lifecycle ledger), with a `must_not` on front-door `search-jobs` rows.

**P1 — close the semantic hole (fixes failure 2).**

6. Add domain/industry to the must-have classifier in both homes — or better, delete one of the two
   copies and fix the survivor.
7. Add the missing preservation rule: a stated preference enters the brief in the user's own terms;
   broadening happens in query vocabulary only, never in the brief. Ban category-level restatement of a
   brief term as a band-hit in `evaluate-job-fit`.
8. Give the strong/moderate boundary a contrastive near-miss pair (same role, location, pay; domain
   named vs. domain adjacent), and add the `moderate` eval the suite has never had.
9. Rewrite the two steer examples so they cannot anchor a band.
10. Grade `query-strategy.md:57` to its base rate.

**P2 — thin the runner.** Execute the Part 2 plan. Add `**Contents:**` maps to every reference over
~100 lines *first*.

**P3 — the verified defects.** Part 3, items 1–13. Items 1–5 and 10 are the ones that can produce wrong
behavior today; the rest are hygiene. Extend the pointer gate (item 3) in the same change as the path
fixes so they cannot regress.

## Evidence and limits

Reviewed at commit `de42734`, working tree clean. `python3 -m pytest -q` → 617 passed;
`philosophy_guard` clean; `doc_lint` clean; build stamp current. Coverage was produced by seven
independent rule-major sweeps (one per guide-doc cluster), each required to quote the offending line;
every finding reproduced in Part 3 was re-verified by hand against the file. Findings in Part 4 that are
not reproduced in Part 3 carry the sweeps' evidence but not an independent second read.

No behavioral evals were executed — this is a static audit. Claims about what a model *would* do under
this guidance are inferences from the text plus the observed dogfood session, not measurements.
