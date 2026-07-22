---
type: review
title: "Conflict sweep: audit-remediation design and plan vs. the shipped pack"
status: current
verified: partial
last_reviewed: 2026-07-22
reviewed_commit: 07882e5
claimed_paths: [skills, shared, scripts, tests, templates, docs/superpowers]
owner_area: Skills & references
repos: [job-search-os]
---

# Conflict sweep: audit-remediation design and plan vs. the shipped pack

Five parallel sweeps over
[the design](../specs/2026-07-22-audit-remediation-design.md) and
[the plan](../plans/2026-07-22-audit-remediation.md), hunting one defect class: **a planned change
that forbids, mandates, or redefines something the shipped pack already documents differently, or
that an existing gate already asserts.**

Commissioned after Task 3's implementer found the new ownership contract banning behavior the front
door is currently instructed to perform. That instance was found during implementation; it should
have been found at design time. This sweep is the retroactive check.

Four sweeps compared each track's changes against the codebase; a fifth checked the two documents
against themselves. **23 Blocking, 14 Should-fix, 9 Watch.** Every finding is anchored to a quoted
line and was verified by opening the file.

## The pattern

Three distinct mistakes recur, and each has a cheap preventive check:

| Mistake | Instances | Preventive check |
|---|---|---|
| An absolute written by subtraction from a failure report, without asking what the pack currently *requires* | 6 | For every new prohibition, grep who is presently told to do that thing |
| A claim about the codebase asserted rather than measured | 7 | Run the grep/`wc` before writing the `Expected:` line |
| A new or widened gate specified without simulating it against today's content | 8 | Execute the proposed rule over the tree before committing to it |

## Blocking — the plan cannot be executed as written

### B1. The ownership contract bans by artifact glob, not by action

`shared/references/ownership.md:13` forbids the front door to write `jobs.jsonl`, `runs/*.json`, or a
digest. Every clause collides with shipped behavior:

- **`runs/*.json`** — the front door must write `runs/detail-model-binding.json` to produce a runnable
  workspace (`onboarding.md:308`, refreshed at `home.md:139`, eval-pinned at
  `skills/job-search/evals/evals.json:18`). `conventions.md:270` states the trap outright: *"A broad
  `runs/*.json` glob is not a run-record definition: it would admit the binding sidecar."* The
  codebase had already solved this boundary and said so.
- **`jobs.jsonl`** — `home.md:268` instructs the front door to append a `status_changed` event;
  `onboarding.md:139` creates the file during scaffolding.
- The row's `Instead` points at `job-search-run`, which is itself forbidden to edit config
  (`job-search-run/SKILL.md:429`) — so the sidecar has no legal writer at all.
- The `Never` column omits the one `runs/` write a marked contract *does* restrict: the ledger,
  `coordinator_only` per `run-lifecycle.md:18` — yet `home.md:267` has the front door append a
  `brief_revision` event to it.

Same defect in the `job-search-agent` row (`ownership.md:17`, "write run artifacts") against that
skill's own operation table (`job-search-agent/SKILL.md:53`, `:84-86`).

**Resolution:** re-specify the boundary positively and by action. Run records (`runs/<run_id>.json`),
the lifecycle ledger, `evaluated` events, and digests are the runner's. Named exceptions: the
config/binding-sidecar pair, `status_changed` events, and the `brief_revision` append are the front
door's. Owner has already ruled the contract narrows to the two protected actions.

### B2. Task 12's premise is false — 13 of 14 lifecycle invariants have no home in `run-lifecycle.md`

The design calls the runner's lifecycle block a hand-copy and the re-pointing "a re-pointing with no
loss of coverage". Measured per fragment, only `rewrite and revalidate both artifacts to the truthful
noncomplete state` is present verbatim (`run-lifecycle.md:218`). The block is a **reworded
restatement**, not a copy. Representative gaps:

- `bidirectional primary job-to-evaluated/presented lifecycle join` — absent by one word; `:209` says
  *posting* join.
- `immutable folded source order` — nearest is "immutable enabled-source order" (`:73`).
- `producer-authoritative` — absent entirely; its real homes are `parallelism.md:123`,
  `conventions.md:450`, `voice.md:96`. **The plan names the wrong canonical home.**
- `append \`evaluating\` immediately before detail work` and `fold again after the close …` — no
  semantic equivalent anywhere. Genuinely runner-owned.

The plan's escape clause ("that fragment is runner-owned and stays") applied 13 times leaves the block
essentially intact, so the thinning target is unreachable by this route. The alternative recovery
("move it into `run-lifecycle.md` first") would copy the runner's wording into the canonical file —
the inverse of the design's goal.

**Resolution:** split the list before executing. Re-word ~9 pins to the canonical wording that already
exists; move `producer-authoritative` and `never infer zero calls from a missing envelope` to
`parallelism.md`; put the 2 genuinely runner-owned fragments in `RUNNER_OWNED`.

### B3. The runner cannot reach 2,000 words — the design's target is arithmetically impossible

Deleting all four targeted blocks removes 3,883 words. Simulated post-Task-14 runner: **373 lines /
4,276 words**, 2.1× the target. The sections the design lists as *"Kept in the body"* total **3,771
words on their own**. Even Task 14's escape hatch (relocating all of Loop step 4) lands near 2,700.

**Resolution:** the ≤2,000 figure was never derived from the content. Either set the ceiling at
AAS-SKILL-04's actual guidance (~5,000 tokens ≈ 3,800 words) and thin to it, or name the further
~2,300 words to relocate. This is a design decision, not an implementation detail.

### B4. Task 18's word cap is unsatisfiable and mis-diagnoses its own failure

The design scopes the budget to the runner. The plan writes it as a **global** cap over every
`skills/*/SKILL.md`. Measured: `job-search-agent` **3,147** words, `job-preference-interview`
**2,193** — and the audit itself ruled both "ok" (review:128-130). No task thins either; four tasks
add to them. From Task 18 onward `doc_lint` fails for reasons no task can fix, and plan:2211 sends the
implementer to the wrong task ("Task 14 left the runner over budget").

### B5. Nine tasks break tests the plan never names

| Task | Breaks | Why |
|---|---|---|
| 12 | `test_runner_pins_coordinator_owned_single_attempt_worker_dispatch`, `test_every_shipped_run_artifact_consumer_requires_exact_closed_ledger_authority` | 5 pinned strings live only inside the deleted block |
| 12 | its own Step 4 | the replacement spine contains `before any mutable or metered work`, a forbidden string |
| 13 | 12's assertion, one task later | the accounting pointer contains `producer-authoritative` |
| 13 | `test_t2_2_guidance_covers_preview_consent_quiet_and_actual_attempt_effects` | `completed attempt` occurs once, inside the moved section |
| 14 | `test_runner_requires_full_canonical_schema_for_every_writable_workspace_halt` | asserts `count("complete canonical run-record schema") >= 2`; the rewrite drops one |
| 15 | `test_path_pointers_to_the_strategy_appear_only_in_skill_md` | the prescribed pointer form is banned in exactly the two files Step 6 edits |
| 15 | `test_gates_named_in_the_operator_doctrine` | deletes the only occurrence of `reversible` and `exact primary model` |
| 15 | its own tri-state assertion | pins a sentence that is not in `parallelism.md` and no step adds it |
| 17 | its own exemption | the widened `_PTR` flags the interface block Step 5 exempts; 5 dangling hits, not 2 |

### B6. No task in Phase 3 regenerates the build stamp

`build_stamp.py`'s `hash_scope` covers `skills/**` and `shared/references/**`. Every Task 12-16 edit
and both new reference files change the content hash. CI's *"Build is a no-op"* gate fails on push.
No task's commit step runs `./scripts/build.sh`.

### B7. Stubbing the preferences template guts the runner eval suite

`skills/job-search-run/evals/files/setup-workspace.sh:22` copies `templates/preferences.example.md` as
the workspace brief for **every** `job-search-run` eval. Task 10 replaces its body with placeholders,
so the onsite-Austin dealbreaker, the strong-match case, and the injection scenario all lose the
must-haves they name.

### B8. Task 11 breaks the eval it shares a fixture with

Adding a web-scraping must-have to `evals/files/brief.md` — the brief for evals 1, 2, 3 and 5 — makes
eval 1's `Assigns match: strong` assert exactly what Task 8's generality rule forbids, since
`posting-strong.md` never mentions web data.

### B9. The band cap contradicts "unknowns are never counted against a posting"

`conventions.md:612`: *"**unknowns**: brief criteria the posting doesn't address … NEVER counted
against a posting."* `evaluate-job-fit/SKILL.md:25` repeats it. Task 7 lands the intent contract in
that same file, and Task 8's disqualifier requires an unestablished domain to cap the band below
`strong`. **This is a genuine semantic collision, not a wording conflict** — two different treatments
of one situation, in one canonical home.

### B10. Task 4 routes the recheck to a verdict nobody may persist

The judge may never write workspace state; the front door may never write `jobs.jsonl`; no runner is
in the loop. `skills/job-search/evals/evals.json:563` (eval 42) invokes `job-search` alone and asserts
a re-judgment *recorded via a `jobs.jsonl` event*. Unsatisfiable by construction.

### B11. Task 6's eval contradicts the suite-wide harness

`evals.json:3` (the `harness` string every scenario inherits) instructs the driver to run
`job-search-run` directly. Task 6's eval 58 forbids exactly that. Task 6 Step 1 also targets the
clause "in eval 1's `prompt`", where it does not exist — deleting it from the harness would silently
remove the digest premise a dozen cases depend on.

### B12. The `band_rule` slot restates the rubric the same file forbids restating

`parallelism.md:105`: *"the `evaluate-job-fit` skill is the single source of truth for *how* to judge;
point to it, never restate it."* `job-search-run/SKILL.md:631` repeats the prohibition, and
`skills/job-search-run/evals/evals.json:679` asserts the rubric arrives "**not restated in the
prompt**".

### B13. The own-words rule collides with "plain, observable language"

`conventions.md:603` requires each brief item be rewritten into checkable form;
`job-preference-interview/SKILL.md:120` and `:159` say the same. Task 7's contract lands beneath that
sentence requiring verbatim wording. Scope the verbatim rule to the requirement's *subject term* —
keep the noun, sharpen the predicate.

### B14. Eval 6's two expectations are mutually unsatisfiable

`dealbreakers_hit` implies `relevant: false` implies a null band, contradicting "moderate or weak —
NEVER strong". Also licenses the automatic rejection the design's own Non-goal forbids.

## Should-fix

- **Five audit findings have a track but no task**: AAS-FORM-03, AAS-DIST-06, AAS-ANTI-35,
  AAS-ANTI-38, and Track D's half of AAS-FORM-01. Neither implemented, declined, nor recorded as open
  — the silent drop the traceability table exists to prevent.
- **The gate paired with the false data-locality claim does not exist.** `doc_lint` has nine rules,
  none inspecting prose claims, so completion criterion "each paired gate demonstrably fails on the
  pre-fix state" is unmeetable for that row.
- **Task 7 installs a second home for the classifier** while deleting another, and gates it with a
  test — the same AAS-BOUND-03 defect in a new place.
- **Task 24 pins one sentence in two files**, gating a cross-file hand-copy into CI in Phase 4 while
  Phase 3 removes four others.
- **The runner grows after Task 14 declares it at budget**, with Task 18's gate live: Tasks 16, 21,
  23 and 24 add ~155 words afterward.
- **Task 5's two invocation modes leave the sequential in-primary path unmoded** — a headless run
  would match the interactive branch and lead with a human summary, which `job-search-run:646`
  forbids.
- **Task 3's narrowing cuts off `location` semantics** the front door needs for query derivation
  (`onboarding.md:227`).
- **`customization.md:63`** still says "Absence makes the posting not relevant", contradicting the
  design's Non-goal and Task 8's required `moderate`.
- **The Import path** would have existing bucket assignments overridden by the new contract, breaking
  `job-preference-interview/evals/evals.json:22`.
- **Task 15's replacement blocks carry unresolvable bare pointers** ("adjust the relative depth" is
  not a path); three depth-correct variants must be written out.
- **Evals 22, 23, 33** expect the model to name all six scheduler gates from a surface Task 15 empties.
- **Design A5 specifies a verification that contradicts Design A3** and that no task implements.
- **The checkpoint's "invite a correction"** adds a question the same paragraph says it is not asking;
  `skills/job-search/evals/evals.json:19` grades its absence.
- **`brief_terms` puts preferences text in a brief that carries none by design**
  (`parallelism.md:94`).

## Watch

Stale baselines in both documents (the runner is now 690/7,804, not 686/7,772; bold densities are
0.463 and 0.417, not 0.50 and 0.44); both documents miscount the pinned substrings (18 asserted / 14
prose, not 19/16); "every audit finding maps to exactly one track" is contradicted by the table
asserting it; the size gate enforces 500 lines while the completion criterion names 300; Task 25
claims `voice.md` is untouched when Task 1 modified it; `SKILL_LOCAL_ORIGINALS`' docstrings keep
saying "four"; the listing id keeps five copies in `TESTING.md` outside the new gate's scan;
`evaluate-job-fit`'s only sanctioned alternative assumes a coordinator that interactive mode lacks.

## Verified clean

Worth recording, since these were checked and hold: the six phase boundaries are correct; the Task
24/25/26 split lost nothing; all thirteen of the audit's verified defects have a named task; the
eval-count arithmetic is right (57→58, and 5→6 twice); completion criterion 8 is already satisfied in
the tree; and the Non-goals on new skills, schema change, registry relocation, and qualitative
relevance are respected by all 28 tasks.
