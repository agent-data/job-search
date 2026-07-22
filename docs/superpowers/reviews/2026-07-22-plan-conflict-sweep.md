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

Five parallel sweeps over [the design](../specs/2026-07-22-audit-remediation-design.md) and
[the plan](../plans/2026-07-22-audit-remediation.md), hunting one defect class: **a planned change
that forbids, mandates, or redefines something the shipped pack already documents differently, or
that an existing gate already asserts.**

Commissioned after Task 3's implementer found the new ownership contract banning behavior the front
door is currently instructed to perform. That instance surfaced during implementation; it was
findable at design time. This is the retroactive check.

**35 Blocking · 18 Should-fix · 11 Watch.** Every finding is anchored to a quoted line and was
verified by opening the file. Three design targets do not survive contact with the codebase.

## The three mistakes underneath all of it

| Mistake | Count | What it looks like | Preventive check |
|---|---:|---|---|
| **Absolute by subtraction** — a prohibition derived from a failure report without asking what the pack currently *requires* | 7 | "the front door never writes `runs/*.json`" | For every new prohibition, grep who is presently told to do that thing |
| **Asserted, not measured** — a claim about the codebase written as fact | 11 | "the invariants are already in `run-lifecycle.md`" | Run the grep or `wc` *before* writing the `Expected:` line |
| **Gate specified without simulation** — a new or widened rule never executed against today's content | 17 | `SKILL_MAX_WORDS = 2000` | Execute the proposed rule over the tree before committing to it |

## Blocking

| # | Conflict | Type | Introduced in | What we wanted | Collides with | Why that's load-bearing | Recommendation | Impact | Key tradeoff |
|---|---|---|---|---|---|---|---|---|---|
| B1 | Contract bans front door from `runs/*.json`, but it must write `runs/detail-model-binding.json` | Absolute by subtraction | Design Track A1; shipped `ownership.md:13` | Stop the front door writing run outputs | `conventions.md:270` — *"A broad `runs/*.json` glob is not a run-record definition: it would admit the binding sidecar"* | The codebase had already solved this boundary and documented the trap | Re-specify by action: run records, ledger, `evaluated` events, digests are the runner's; the config/sidecar pair, `status_changed`, `brief_revision` are the front door's | Contract rewritten a 3rd time; Tasks 3-6 re-verified | Positive framing is longer than a glob; needs a named-exception list the gate must pin |
| B2 | Same row bans writing `jobs.jsonl`, but the front door appends `status_changed` and creates the file | Absolute by subtraction | Design A1 | Same | `home.md:268`, `onboarding.md:139` | Pipeline state is the front door's core job | Folded into B1 | — | — |
| B3 | Contract's `Instead` points at the runner, which is itself barred from editing config | Design flaw | Design A1 | Give every prohibition an alternative | `job-search-run/SKILL.md:429` | AAS-FORM-10 requires a *reachable* alternative | Folded into B1 | — | — |
| B4 | `job-search-agent` barred from "run artifacts" while its own operation table tells it to append `jobs.jsonl` events | Absolute by subtraction | Design A1 | Keep the manual out of the runner's lane | `job-search-agent/SKILL.md:53`, `:84-86` | The Quick-reference table is introduced as *"every operation … a pinned procedure"* | Scope the row to run records and digests | Small edit | Manual keeps a write capability, weakening "only the runner persists" |
| B5 | 13 of 14 lifecycle invariants have **no home** in `run-lifecycle.md` | Asserted, not measured | Design C1; Plan T12 Step 2 | Delete a hand-copy by re-pointing its pins | Only `rewrite and revalidate both artifacts…` is present (`:218`) | The block is a *reworded restatement*, not a copy — the whole re-pointing premise | Split the list: re-word ~9 pins to canonical wording, move 2 to `parallelism.md`, keep 2 as `RUNNER_OWNED` | T12 becomes a 3-way triage, not a delete | Re-wording pins couples them to canonical prose that may itself change |
| B6 | `producer-authoritative` — the plan names the wrong canonical home | Asserted, not measured | Plan T12 | Pin the invariant somewhere | Real homes are `parallelism.md:123`, `conventions.md:450`, `voice.md:96` | Pinning against the wrong file proves nothing | Move that pin to `parallelism.md` | Included in B5 | — |
| B7 | T12's replacement spine contains `before any mutable or metered work` — a string its own test forbids | Plan self-contradiction | Plan T12 Steps 1 vs 3 | Invert the assertion to enforce single-homing | Itself, 12 lines apart | The task fails its own Step 4 | Drop that fragment (genuinely runner-owned) or reword the spine | Trivial | Fewer pinned invariants |
| B8 | T13's accounting pointer re-introduces `producer-authoritative`, re-reddening T12 one task later | Plan self-contradiction | Plan T13 Step 5 | Point at the moved section | T12's inverted assertion | Cross-task regression | Same fix as B6 | Trivial | — |
| B9 | **The runner cannot reach 2,000 words** — simulated result is 373 lines / 4,276 words | Arithmetic | Design C1 | A lean orchestration spine | The design's own "Kept in the body" list totals **3,771 words** | The headline thinning target is unreachable by construction | Re-derive the target from content, or name the further ~2,300 words to move | Design target changes; **owner decision** | Leaner spine vs. a runner that still reads as a coherent procedure |
| B10 | T18's 2,000-word cap is **global**, rejecting two shipped skills the audit ruled compliant | Gate without simulation | Plan T18 Step 3 | Stop the runner re-inflating | `job-search-agent` 3,147 w; `job-preference-interview` 2,193 w | `doc_lint` fails from T18 on, for reasons no task can fix — Phase 4 cannot complete | Per-skill ceilings, or scope the word half to the runner | Unblocks Phase 4; **owner decision** | A per-file table is a maintenance surface and invites waivers |
| B11 | T18's own diagnostic mis-attributes the failure | Plan bug | Plan T18 Step 4 | Help the implementer | "if `skill-size-budget` fires, Task 14 left the runner over budget" | Sends them to the wrong task | Rewrite with B10 | Trivial | — |
| B12 | T12 breaks two pressure tests the plan never names | Plan→test | Plan T12 Step 3 | Delete the block | `test_run_lifecycle_pressure.py:1527`, `:1569` — 5 strings live only inside it | Both go red on correct behavior | Add both to T12's Files and re-point (3 of 5 have canonical homes) | T12 grows | — |
| B13 | T13 moves the only carrier of `completed attempt` | Plan→test | Plan T13 Step 5 | Extract accounting | `test_usage_context_contract.py:808` | Red on correct behavior | Keep the phrase, or re-point the assertion at the new reference | Trivial | — |
| B14 | T14's run-health rewrite drops one of two required `complete canonical run-record schema` mentions | Plan→test | Plan T14 Step 2 | Collapse restated prose | `test_run_lifecycle_pressure.py:1630` asserts `count(...) >= 2` | Red on correct behavior | Keep the literal, or lower to `>= 1` with a note | Trivial | Weakens a real redundancy check |
| B15 | T15's prescribed `query-strategy.md` pointer form is **banned** in exactly the two files it edits | Plan→test | Plan T15 Step 6 | Replace restatements with a pointer | `test_query_strategy_contract.py:128` — only `SKILL.md` may carry a path pointer | The guard's docstring prescribes the alternative | Use the bare backticked name, no directory component | Trivial | — |
| B16 | T15's gate collapse deletes the only occurrence of two pinned tokens | Plan→test | Plan T15 Step 5 | One home for the six gates | `test_scheduling_eligibility.py:94-95` — `reversible`, `exact primary model` | Red on correct behavior | Re-point at `internals.md`'s table, or keep bare gate names in the doctrine | Small | Operator manual loses an at-a-glance list |
| B17 | T15's tri-state test pins a sentence that is not in `parallelism.md` | Asserted, not measured | Plan T15 Step 1 | Prove one home | `parallelism.md:26` words it differently | Assertion fails in both directions; no step adds the sentence | Pin the wording that exists, or add the exact sentence in Step 4 | Trivial | — |
| B18 | **No task in Phase 3 regenerates the build stamp** | Coverage gap | Plan T12-16 commit steps | — | CI's *"Build is a no-op"* gate; `hash_scope` covers `skills/**`, `shared/references/**` | CI fails on push | Add `./scripts/build.sh` + stage the stamp to every task touching those trees | Mechanical, ~8 tasks | Slightly noisier commits |
| B19 | **Stubbing the preferences template guts the runner eval suite** | Gate without simulation | Plan T10 Step 5 | Stop the bundled persona anchoring drafts | `job-search-run/evals/files/setup-workspace.sh:22` copies it as the workspace brief for **every** runner eval | Dealbreaker, strong-match and injection scenarios lose the must-haves they name | Move the persona to a runner-eval fixture and repoint the setup script in the same commit, then stub | T10 grows by one file | Two briefs to keep coherent |
| B20 | T11 adds a must-have to the **shared** judge fixture, breaking eval 1 | Plan→eval | Plan T11 Step 1 | Give the adjacent-domain case a domain must-have | `evaluate-job-fit/evals/evals.json:19` asserts `strong` on a posting with no web-data content | The new rule would forbid what the existing crown jewel asserts | Use a Task-11-only brief fixture | Trivial | One more fixture |
| B21 | **The band cap contradicts "unknowns are NEVER counted against a posting"** | Design flaw | Design Track B; Plan T7/T8 | Stop a broadened term earning `strong` | `conventions.md:612`; `evaluate-job-fit/SKILL.md:25` | Two treatments of one situation, landing in one canonical home | Split the rule: never *rejects*, but does cap the band | Semantic change; **owner decision** | Precision vs. the existing protection against over-rejection |
| B22 | Eval 6's two expectations are mutually unsatisfiable | Plan bug | Plan T11 Step 3 | Assert the gap is visible | `dealbreakers_hit` ⇒ `relevant:false` ⇒ null band, vs "moderate or weak" | Also licenses the auto-rejection the design's Non-goals forbid | Require the gap in `unknowns` + `needs_human_check` | Trivial | — |
| B23 | The `band_rule` slot restates the rubric the same file forbids restating | Design flaw | Design B2; Plan T9 Step 5 | Get the band rule to a cheap delegated model | `parallelism.md:105`; `job-search-run/SKILL.md:631`; eval `:679` asserts "not restated in the prompt" | By-reference is the pack's stated defense against rubric drift | Re-point the by-reference bullet and eval 679 to name these two values as the explicit carve-out | Small, 3 sites | A carve-out weakens a clean rule |
| B24 | The own-words rule collides with "plain, observable language" | Design flaw | Design B1; Plan T7 Step 3 | Preserve the user's term | `conventions.md:603`; `job-preference-interview/SKILL.md:120`, `:159` | The canonical home would require verbatim wording *and* rewriting | Scope verbatim to the requirement's **subject term** — keep the noun, sharpen the predicate | Wording | Less absolute, needs care in the gate |
| B25 | T4 routes the recheck to a verdict nobody may persist | Design flaw | Design A3; Plan T4 Step 4 | Stop the front door judging | `evals.json:563` (eval 42) invokes `job-search` alone, asserts a `jobs.jsonl`-recorded re-judgment | Unsatisfiable by construction | Add an explicit clause: the front door persists a judge-returned verdict when no run is in flight | Contract + home.md | A narrow write exception in the contract |
| B26 | T6's eval 58 contradicts the suite-wide `harness` string | Plan→eval | Plan T6 Steps 1-2 | Prove the front door delegates | `evals.json:3` instructs the driver to run the runner; every scenario inherits it | T6 Step 1 also targets a clause that is not where it says | Move the clause out of `harness` into the per-case prompts that need it | Touches ~12 cases | Larger eval diff |
| B27 | Widened `_PTR` breaks the scan's own classification branch | Gate without simulation | Plan T17 Step 1 | See dangling pointers | `test_reference_resolution.py:397` — non-`shared/references` pointers must be in `SKILL_LOCAL_ORIGINALS` | Gate stays red after all four prescribed fixes; obvious "fix" weakens the fan-out guard | Classify by token shape before asserting | T17 grows | More branching in the resolver |
| B28 | Bare-`.sh` matching flags the CLI-signature block T17 exempts | Plan self-contradiction | Plan T17 Steps 1 vs 5 | Path every script invocation | `run-lifecycle.md:298-308` — ten signature lines in a fence | Two steps of one task specify opposite treatments | Make the `.sh` arm fence-aware via the existing `_unfenced_lines()`; state the exemption as a rule | Small | — |
| B29 | Bare-`.sh` matching double-matches seven already-correct paths | Gate without simulation | Plan T17 Step 1 | Same | e.g. `job-search-run/SKILL.md:17` `../../shared/scripts/mechanics/workspace-discovery.sh` | Correct invocations go red; the commit message's "17" matches no measurement | Anchor with a negative lookbehind for `/`; extend Step 5 to three genuinely bare non-lifecycle names | Small | — |
| B30 | Widened scan flags two URLs and a repo-root path in a generated file | Gate without simulation | Plan T17 Step 2 | Expect 4 failures | Six hits; `build-stamp.md:10` is a URL in a file marked *"Do not edit it by hand"* | Permanently red — a generated file cannot be hand-fixed | Skip matches preceded by `://`; decide explicitly on repo-root form | Small | One more exemption rule |
| B31 | Derived `GATES` raises **KeyError** against every scheduler fixture | Gate without simulation | Plan T19 Step 3 | Stop the tuple drifting | All ten fixtures under `tests/fixtures/scheduler/` lack an `inspectable` key | Not an assertion failure — a crash; T19's stated PASS is unreachable | Add `inspectable: true` to the ten fixtures and the shim in the same commit | T19 grows | — |
| B32 | `--check-undeclared-version` flags CONTRIBUTING.md's semver *examples* | Gate without simulation | Plan T22 Step 3 | Catch stale versions | `CONTRIBUTING.md:87-88` — `0.1.0 → 0.1.1` as illustration | T22 Step 5 and T28 Step 1 both expect a pass | Exclude semvers inside a bump example, or drop the file from the scan | Trivial | Slightly narrower audit |
| B33 | "Settle through the summary fallback" is barred after a **successful** detail call | Design flaw | Plan T21 Step 3 | Reject a bad band instead of coercing | `job-search-run/SKILL.md:536`; `run-lifecycle.md:249-251`, `:345` | An implementer following T21 writes a ledger the fold rejects | Offer only `terminally_skipped` after a successful call | Wording | — |
| B34 | T24 quotes a sentence that does not exist in `parallelism.md` | Asserted, not measured | Plan T24 Step 5 | Conditionalize the worker re-emit | `parallelism.md:137-139` words it differently | Per the plan's own rule the task must halt — yet its gate demands the edit | Quote the actual clause as a second, separately-worded target | Trivial | — |
| B35 | T25 leaves the universal claim it was written to remove | Plan bug | Plan T25 Step 3 | Host-scope the visibility premise | `voice.md:8-9` — *"nothing offscreen reaches the user"* survives outside the replaced span | The pack would ship a self-contradiction atop the file every skill's voice derives from | Extend the replaced span through that sentence | Trivial | — |
| B36 | T27's own test cannot pass on T27's own copy | Plan bug | Plan T27 Steps 1 vs 5 | Prove the consent question ships | `assert "Check for updates"` vs prose containing only lowercase `check` | The exact failure mode the plan's Global Constraints flag for T2, reintroduced in the last task | Assert case-insensitively, or pin the stable heading | Trivial | — |
| B37 | T27 Step 4 edits an `update_check` object `internals.md` does not have | Asserted, not measured | Plan T27 Step 4 | Add the consent key | `update_check` is defined only in `update.md:30-42` | No edit target; creating it there would duplicate a schema | Add `consent` where the object lives; `internals.md` links | Trivial | — |

## Should-fix

| # | Conflict | Type | Introduced in | Collides with | Recommendation |
|---|---|---|---|---|---|
| S1 | Five audit findings have a track but no task | Coverage gap | Design Traceability | AAS-FORM-03, AAS-DIST-06, AAS-ANTI-35, AAS-ANTI-38, Track D's half of AAS-FORM-01 | Add a step, decline with a reason, or record as open |
| S2 | The gate paired with the false data-locality claim does not exist | Design flaw | Design D table | `doc_lint`'s nine rules inspect no prose claims | Add a real check, or mark the cell `—` and soften the completion criterion |
| S3 | T7 installs a second home for the classifier while deleting another | Plan self-contradiction | Plan T7 Steps 3+4 | Global Constraint "one canonical home" | Reduce Step 4 to a pointer, as Step 5 does for onboarding |
| S4 | T24 pins one sentence in two files | Plan self-contradiction | Plan T24 Step 1 | Phase 3 removes four such copies | Assert the sentence in `parallelism.md`, a pointer in the runner |
| S5 | The runner grows ~155 words after T14 declares it at budget, with T18's gate live | Ordering | Plan T16/21/23/24 | T14 Step 3's measurement | Re-measure as the last step of T24, or target headroom |
| S6 | T5's two modes leave the sequential in-primary path unmoded | Design flaw | Design A4 | `parallelism.md:143`; `job-search-run/SKILL.md:646` | Key the delegated section on *producing the envelope*, not on dispatch |
| S7 | T3's narrowing cuts off `location` semantics the front door needs | Absolute by subtraction | Plan T3 Step 5 | `onboarding.md:227`; `query-strategy.md:47-48` | Extend to § Route: search-jobs params, or relocate the fact |
| S8 | `customization.md:63` still says absence ⇒ not relevant | Coverage gap | — (untouched by any task) | Design Non-goal; T8's required `moderate` | Correct both rows, citing T8's rule IDs |
| S9 | The Import path would have bucket assignments overridden | Design flaw | Design B1 | `job-preference-interview/evals/evals.json:22` | State that an imported brief's existing buckets are authoritative |
| S10 | T15's replacement blocks carry unresolvable bare pointers | Plan bug | Plan T15 Steps 4-5 | `test_reference_resolution.py:389` | Write the three depth-correct variants out |
| S11 | Evals 22/23/33 expect six gate names from a surface T15 empties | Plan→eval | Plan T15 Step 5 | `job-search-agent/evals/evals.json` | Keep bare gate names, or record the expected rate change |
| S12 | Design A5 specifies a verification contradicting Design A3 | Design self-contradiction | Design A5 vs A3 | — | Delete the "absent" clause; assert section-scoping instead |
| S13 | The checkpoint's "invite a correction" adds a question the paragraph disclaims | Design flaw | Design B3 | `evals.json:19` grades its absence | Phrase as standing editability, not an interrogative |
| S14 | `brief_terms` puts preferences text in a brief that carries none | Design flaw | Plan T9 Step 5 | `parallelism.md:94`; `run-lifecycle.md:519` | Amend the brief-revision bullet in the same task |
| S15 | T20 fixes one of three copies of the decline claim | Coverage gap | Plan T20 Step 3 | `TESTING.md:79`, `:161` | Fix all three; change `:161`'s scripted answer to a plain "Not now" |
| S16 | T21 leaves an eval that still accepts coercion | Plan→eval | Plan T21 | `job-search-run/evals/evals.json:707` | Update in T21's commit |
| S17 | Two competing settling paths survive for a rejected envelope | Design flaw | T21 vs `parallelism.md:137-139` | — | Make `parallelism.md` the single settling contract |
| S18 | Anchoring the philosophy grep to `jobs.jsonl` makes salary a false positive | Gate without simulation | Plan T26 Step 5 | `TESTING.md:689`; `salary_display` is free text | Keep the transcript probe and its concession; tighten only the artifact grep |
| S19 | A fifth repo-root `templates/` pointer no step fixes | Gate without simulation | Plan T17 Step 4 | `conventions.md:22`, inside a fenced tree diagram | Decide fence handling for `templates/` alongside `.sh` |

## Watch

Stale baselines in both documents (the runner is now **690 lines / 7,804 words**, not 686/7,772; bold
densities are 0.463 and 0.417, not 0.50 and 0.44) · both documents miscount the pinned substrings
(**18 asserted / 14 prose**, not 19/16) · *"every audit finding maps to exactly one track"* is
contradicted by the table asserting it (three findings are split) · the size gate enforces 500 lines
while the completion criterion names 300 · T25 claims `voice.md` is untouched when T1 modified it ·
`SKILL_LOCAL_ORIGINALS`' docstrings keep saying "four" in five places · the listing id keeps five
copies in `TESTING.md`, outside the new gate's scan · `evaluate-job-fit`'s only sanctioned alternative
assumes a coordinator the interactive mode lacks · T21 and T24 give "missing returned evidence"
opposite consequences ten lines apart · T27's new question has no answer in any scripted scenario and
no checklist box · the new reader persona asserts a phone surface `voice.md`'s own list omits.

## Verified clean

Checked and holding: the six phase boundaries are correct · the T24/25/26 split lost nothing · all
thirteen of the audit's verified defects have a named task · the eval-count arithmetic is right
(57→58; 5→6 twice) · completion criterion 8 is already satisfied in the tree · the frontmatter
validator passes all five shipped skills (descriptions 402–814 chars, well under 1024) · `AGENTS.md`
is 29 lines against a 150-line ceiling · an absent `update_check.consent` breaks no documented state
machine · the Non-goals on new skills, schema change, registry relocation and qualitative relevance
are respected by all 28 tasks.

---

# Elaboration

## Why B1 is the most instructive row

The contract's `Never` column bans **by artifact glob**. Every collision follows from that one choice.
The front door legitimately touches several paths under `runs/` and inside `jobs.jsonl`; what it must
never do is produce a **run output** or a **verdict**. A glob cannot express that distinction, so it
over-reaches in four directions at once and under-reaches in a fifth — it never mentions the lifecycle
ledger, the one `runs/` path a marked contract genuinely restricts to the coordinator, and which
`home.md:267` has the front door append to.

The sharpest detail: `conventions.md:270` already contains the sentence *"A broad `runs/*.json` glob is
not a run-record definition: it would admit the binding sidecar."* The repository had encountered this
exact boundary, worked out that the glob is wrong, and written the reason down. The design used the
glob anyway. This is what "absolute by subtraction" costs — the design was derived from the audit's
list of failures, and never asked the codebase what it already knew.

## Why B5 changes what Task 12 *is*

The design describes the runner's lifecycle block as a hand-copy and the fix as "a re-pointing with no
loss of coverage." Measured fragment by fragment, only one of fourteen appears verbatim in
`run-lifecycle.md`. The rest are near-misses of a specific kind:

- `bidirectional primary job-to-evaluated/presented **lifecycle** join` vs. `:209`'s
  *"…job-to-evaluated/presented **posting** join"* — one word.
- `immutable **folded** source order` vs. `:73`'s *"immutable **enabled-source** order"*.
- `producer-authoritative` — absent from `run-lifecycle.md` entirely; it lives in `parallelism.md`,
  `conventions.md` and `voice.md`.
- `append \`evaluating\` immediately before detail work` and `fold again after the close…` — no
  equivalent anywhere. Genuinely the runner's.

So the block is a **paraphrase**, not a copy. That matters because the plan's escape clause — "if a
fragment has no canonical home it is runner-owned and stays" — applied thirteen times leaves the block
essentially intact and the thinning target unreachable. And the alternative recovery the plan offers,
"move it into `run-lifecycle.md` first", would copy the runner's wording *into* the canonical file,
which is the precise inverse of the design's stated goal.

Task 12 is therefore not a delete-and-re-point. It is a three-way triage: re-word ~9 pins to the
canonical phrasing that already exists, relocate 2 to `parallelism.md`, and keep 2 in the runner.

## Why B9 and B10 are one decision, not two

B9 says the runner cannot reach 2,000 words; B10 says two other skills already exceed that cap. Both
trace to a single unexamined number. The design wrote **≤2,000 words** for the runner without summing
what it planned to keep — the "Kept in the body" list alone is 3,771 words. The plan then applied that
same number as a *global* ceiling, which the design never asked for, against skills the audit itself
had ruled compliant.

`AAS-SKILL-04`'s actual guidance is *"aim under ~500 lines / ~5,000 tokens"* — roughly 3,800 words. All
five skills can meet that after the planned moves; none can meet 2,000. The open question is whether to
adopt the guide's own figure, hold the aggressive target and relocate a further ~2,300 words, or
maintain per-skill ceilings.

The tradeoff is real in both directions. A 2,000-word runner would be the leanest spine, but the words
that would have to move are Loop steps 3–5 — the orchestration logic itself. Pushing those behind
load-triggers risks a runner that no longer reads as a procedure, which is the failure mode
`AAS-BOUND-02` warns about when it says to split on *heavy and rarely-read*, not on raw length.

## Why B21 is a product decision, not a wording fix

`conventions.md:612` states that unknowns — brief criteria a posting doesn't address — are *"NEVER
counted against a posting"*, and `evaluate-job-fit/SKILL.md:25` repeats it. That rule exists for a good
reason: it stops the judge rejecting a posting merely for being silent about something.

Task 8's generality disqualifier requires an unestablished domain to cap the band below `strong`. Task
7 lands the intent contract in the same file. So the canonical home would carry both rules.

These are not contradictory in intent — one governs *rejection*, the other governs *ranking* — but they
are stated as one rule about one situation, and nothing in the pack currently distinguishes the two
axes. The dogfooding failure is the case in point: Rebar and Cogent were plausibly relevant and should
have stayed in the digest; they should never have been `strong`. Splitting the rule captures exactly
that. Leaving it unsplit preserves the existing over-rejection protection but permits the verdict that
caused this project.

## The pattern worth carrying forward

Seventeen of the thirty-five Blocking findings are gates specified but never simulated. That is the
largest single category, and it is the same defect this whole project exists to fix — the audit's
central charge was that the pack had rules nothing enforced, and the remediation plan proposed
enforcement it never executed.

The cheap preventive is mechanical: **before writing a gate into a plan, run it.** Every one of B10,
B27–B32 and S18–S19 would have been caught by executing the proposed rule over the tree once. The same
applies to the eleven "asserted, not measured" rows: `grep` before `Expected:`.

## Open decisions for the owner

1. **The word budget (B9, B10).** Adopt `AAS-SKILL-04`'s ~3,800-word figure pack-wide; hold 2,000 for
   the runner and relocate a further ~2,300 words; or maintain per-skill ceilings.
2. **Unknowns vs. the band cap (B21).** Never rejects but does cap the band; keep unknowns fully
   neutral; or mark protected terms in the brief and cap only those.
3. **Scope of the revision.** Whether to revise the design and plan in place — the Track A–E structure
   survives; roughly twelve tasks need substantive rework — or re-derive the affected tasks from the
   audit.
