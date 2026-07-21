# Private style-guide audit — recall-oriented query strategy

**Audited range:** `1e3dbe3...fc70b9b` — 15 commits: the design commit `1e3dbe3` is the behavioral
baseline, `d0ed626` is the plan, and the fourteen implementation commits `105c82c` … `fc70b9b` are the
change under audit. 24 files, +1905/−56. `git diff --check 1e3dbe3...HEAD` is clean.

**Audited against** the private authoring doctrine in `docs-private/prompt-style-guide/` (9 files, `PSG-*`)
and `docs-private/agent-agnostic-skills/` (17 files, `AAS-*`). Every file in both directories was read in
full; the four index files (`prompt-style-guide/09-checklist-and-rule-index.md`,
`agent-agnostic-skills/13-anti-patterns.md`, `14-checklist-and-rule-index.md`, `16-tension-register.md`)
were re-read last and govern every count and rule ID cited below. `docs-private/` remains untracked
(`git ls-files docs-private` prints nothing) and is named nowhere under `skills/` or `shared/references/`.

## Index counts — expected vs actual

The plan's Task 8 predicted 18 PSG checklist rows, 14 AAS checklist rows, 13 PSG anti-patterns, 42 AAS
anti-patterns, and 10 AAS tensions. **Every prediction matches the live indexes; there is no discrepancy.**
Verified by counting the indexes themselves:

| Index | Expected | Actual | ID range |
|---|---:|---:|---|
| PSG PR checklist (`09`, Part 1) | 18 | **18** | Q1–Q18 |
| PSG rule index (`09`, Part 2) | — | **101** | `PSG-F-01` … `PSG-SAFE-19` |
| PSG anti-patterns (`08`) | 13 | **13** | `PSG-ANTI-01` … `PSG-ANTI-13` |
| AAS pack checklist (`14`, Part 1) | 14 | **14** | Q1–Q14 |
| AAS rule index (`14`, Part 2) | — | **122** | `AAS-PACK-01` … `AAS-TEST-16` |
| AAS anti-patterns (`13`) | 42 | **42** | `AAS-ANTI-01` … `AAS-ANTI-42` |
| AAS tension register (`16`) | 10 | **10** | `AAS-T-01` … `AAS-T-10` |

Every rule ID cited in this audit was resolved against those indexes before use.

## Findings and repairs

Four defects were found in the Tasks 1–7 output. All four are repaired in this commit.

### F1 — `TESTING.md` still grades against the deleted zero-results wording (repaired)

`shared/references/errors.md` previously fixed the literally-empty case with the verbatim string
*"Searches ran but returned 0 results. Broaden keywords in `config.yaml`…"*. This branch replaced that
contract with a stream-completion check plus a contextual offer of broader complementary role families, and
updated `job-search-run` eval 4 to match — but left two copies of the superseded string in `TESTING.md`:
the **Sparse-data fallback** paragraph and the **T7.11** expected-result cell. A tester grading T7.11
against the stale cell would fail a correct implementation, or "fix" the product back to the removed
wording. The same sentence also pointed at **T7.10** (many-promising postings) for behaviour owned by
**T7.11**.

*Classification:* `AAS-ANTI-04` (hand-synced duplicate with no drift gate), `AAS-ANTI-41` (internally
contradictory guidance), `AAS-ANTI-42` (broken cross-reference), `AAS-BOUND-03`, `PSG-ANTI-02`,
`PSG-ANTI-03`. *Repair:* both cells restated to the shipped contract; the cross-reference corrected to
T7.11.

### F2 — `docs/product-specs/new-user-onboarding.md` §Sparse market contradicts the new onboarding (repaired)

The spec still said zero search results *"prompt the agent to offer keyword broadening conversationally."*
`skills/job-search/references/onboarding.md` now requires stream-completion confirmation first, a contextual
read second, and an offer only where the volume is surprisingly thin — changing nothing until the user
accepts. §5 of this same file was updated by this branch; §Sparse market was missed.

*Classification:* `AAS-ANTI-41`, `AAS-BOUND-03`, `PSG-ANTI-02`. *Repair:* the paragraph now states the
shipped order of operations and the accept-before-write rule.

### F3 — `customization.md` asserted an unverifiable context state (repaired)

§2 read *"judged the way `query-strategy.md` (already loaded by this manual) judges thinness"*. The operator
manual's routing table is a **lookup** table keyed to operations, not an unconditional load, so an agent
reaching §2 through the Contents list or the front door's *Applying your feedback* route may never have
loaded the strategy. The parenthetical is a false reassurance whose effect is to suppress the read the
honest fact would trigger.

*Classification:* `PSG-COMM-20` (**MUST**) read at its stated mechanism — a standing false
capability/durability claim that suppresses the behaviour the honest fact would produce; `AAS-BOUND-04`
(a reference named without a load-trigger). A reviewer who reads `PSG-COMM-20` narrowly as
harness-capability-only would grade this at `AAS-BOUND-04` (SHOULD) instead. It is repaired either way.
*Repair:* the claim is replaced with an explicit conditional read-trigger — *"but judge thinness the way
`query-strategy.md` does, reading it first if this manual has not already"*. The bare backticked name is
retained (the two-pointer contract test permits a name, not a path).

### F4 — substitution slots rendered as concrete values in the runner (repaired)

`skills/job-search-run/SKILL.md` introduced the five request-evidence fields with a JSON sample sitting
immediately before *"Bind the five actual values once, here"* — the textbook substitution-slot position —
yet rendered three of the five concretely: `"location": null`, `"freshness": "past-2-weeks"`,
`"published_on_or_after": "2026-07-03"`. A fabricated cutoff date next to a write instruction is exactly the
"realistic token pasted into a live artifact" hazard, and here the artifact is run-record **audit
evidence**: a recited date is fabricated evidence about what the run asked for.

The other two new JSON samples do not have this problem, and the contrast is what makes this a defect rather
than house style. `shared/references/internals.md` ships **both** renderings — the registry *schema* block
with angle-bracket slots (`"<id>"`, `"<keywords>"`, `"<normalized|null>"`, `"<iso>"`) and a separately
fenced filled example — which is the sanctioned teaching-detail/substitution-slot split. `conventions.md`
renders these same five fields schematically (`"<normalized location sent|null>"`,
`"<saved recency selector|null for one_off>"`, `"<YYYY-MM-DD|null>"`). The runner's block was the one site
carrying only a concrete rendering.

*Classification:* `AAS-EX-04`, `AAS-EX-02`, `AAS-ANTI-29`, `AAS-ANTI-37`, and the `AAS-T-08` ruling.
*Repair:* the three free-form slots now use the exact schematic forms `conventions.md` already uses;
`request_origin` and `limit` were already byte-identical to the canonical schema and are unchanged.

## Part 1 — PSG PR checklist (18 rows)

| # | Governing IDs | Disposition |
|---|---|---|
| 1 | `PSG-SAFE-02` (MUST), `PSG-COMM-09`, `PSG-SAFE-17` | **Pass.** Every new persistence directive carries its honesty brake in the same sentence: `query-strategy.md` §*A run never broadens itself* — "Finish the configured streams, **record the truthful raw evidence in the run record**, and leave any broader request to a later user-approved retune"; `job-search-run/SKILL.md` — "record its truthful evidence and never issue a second search with altered keywords"; `run-lifecycle.md` — a zero-relevant run "is nonetheless a truthful **completed** outcome, not a failure". The honest exit is named as a valid outcome at every site. |
| 2 | `PSG-F-10`, `PSG-COMM-06`, `PSG-SAFE-11` | **Pass.** `query-strategy.md` ¶3 names both failure directions (an over-constrained phrase that suppresses candidates *vs* indiscriminate generic retrieval that spends calls without opening a lane), declares the winner ("Queries maximize plausible recall; the Job Preferences Brief supplies precision") and attaches the cost argument ("What they do not cost is precision: the complete brief is still applied to every candidate"). |
| 3 | `PSG-COMM-09`, `PSG-COMM-20`, `PSG-SUB-06`, `PSG-SAFE-05` | **Pass after repair.** Verify-the-artifact half holds: the query-health read is gated on `run-lifecycle.md` → *Artifact authority for every reader*, and eval 57 expectation 1 grades "the trace it leaves rather than on any account of what was read". False-claim half produced **F3** (repaired) plus **F1/F2** — the `PSG-COMM-20` "remove it from EVERY copy" discipline applied to a superseded behavioural claim (repaired). Credit where due: the branch *removed* a standing absolute ("the search API has no remote filter") and replaced it with a conditional plus a named fallback. |
| 4 | `PSG-SAFE-08`, `PSG-SAFE-01`, `PSG-INJ-05`, `PSG-INJ-11` | **Pass.** The failed/blocked/incomplete branch prescribes the sanctioned recovery by name ("Apply that failure's named recovery in `errors.md` and wait for healthy evidence before judging breadth") and the bypass repertoire is enumerated and outlawed ("No automatic retry with different terms, no fallback query, no quietly raised limit or deeper pagination"). `errors.md` orders the zero-empty case the same way. |
| 5 | `PSG-SUB-13`, `PSG-SUB-04`, `PSG-COMM-03` | **Pass.** No subagent text channel is added; the local analog is the machine-consumed run record and registry marker, and both are pinned exactly — six marked contract tables asserted by exact-dict equality, plus `tests/fake-run-lifecycle` rejecting 5 field omissions and 12 adversarial mutations. |
| 6 | `PSG-SUB-04`, `PSG-SUB-05`, `PSG-SUB-11`, `PSG-SUB-13` | **N/A — untouched surface.** No delegated verdict or judge output is added or edited; the `job-search-run/SKILL.md` hunks land in the search-request, pagination, and finalization sections only — the detail-read delegation section and `parallelism.md` are untouched by the range. |
| 7 | `PSG-INJ-01`, `PSG-SAFE-10`, `PSG-TOOL-15` | **N/A — untouched surface.** No new lower-trust payload is spliced. The five new stream fields record parameters the runner itself composed and normalized; no third-party posting text path changed. |
| 8 | `PSG-INJ-09`, `PSG-INJ-05` | **Pass.** Every new machine-consumed fragment carries a stable recognizable envelope: the six `<!-- query-strategy-contract:… -->` delimiter pairs are the emit-then-detect contract the tests parse, and `query_health_nudge` is one named, bounded, overwritten-not-accumulated registry object. Degradation-notice half is Q4. |
| 9 | `PSG-INJ-03`, `PSG-INJ-04`, `PSG-COMM-05` | **N/A — untouched surface.** No compaction or continuation-summary prompt exists in the range. Adjacent support only: the run record is a producer→consumer handoff, and the branch strengthens it by preserving the request verbatim (`request_origin`, the saved `freshness` selector) so a later reader compares like with like. |
| 10 | `PSG-SUB-02`, `PSG-COMM-03` | **N/A — untouched surface.** No subagent prompt is added or edited. |
| 11 | `PSG-SUB-01`, `PSG-TOOL-02`, `PSG-TOOL-03` | **N/A — untouched surface.** No `SKILL.md` frontmatter `description` changed anywhere in the range (verified: the diff contains no frontmatter hunk). The body-level routing the branch does add is trigger-keyed on both sides. |
| 12 | `PSG-SUB-09`, `PSG-SUB-08`, `PSG-SUB-14` | **Pass.** Nothing flips parallel-by-default: the concurrent first-page batch and its named sequential fallback are untouched context. Posture stays stated per-mode — "only the **job-search** front door writes it … the headless runner never writes it". |
| 13 | `PSG-TOOL-01`, `PSG-TOOL-07`, `PSG-TOOL-16` | **N/A — untouched surface.** No tool/skill `description` changed. The one new reference header does apply the discipline ("This file governs query derivation, contextual retrieval-health assessment, and user-approved broadening"). |
| 14 | `PSG-TOOL-05`, `PSG-TOOL-09`, `PSG-TOOL-10`, `PSG-TOOL-12` | **Pass.** Each of the five new fields states required/optional and its null semantics, with the enumerable spaces glossed per value (`saved`/`one_off`; `shown`/`accepted`/`dismissed` with per-value write conditions) and `limit` carrying its bounded range (1–100). Policy (when to write) stays in the write-rules section rather than inside a field gloss. |
| 15 | `PSG-TOOL-04`, `PSG-TOOL-11` | **Pass.** The precondition is stated as an enforced gate naming its consequence — "New records stay strict: a stream that omits one of them **fails final artifact validation**" — and `tests/fake-run-lifecycle` actually enforces it, so the consequence is real rather than advisory. |
| 16 | `PSG-F-02`, `PSG-F-11`, `PSG-SUB-11`, `PSG-COMM-06` | **Pass.** Budgets are countable with relaxation conditions: "one evidence sentence … — one evidence bullet instead when a long source list would be hard to scan — then one question"; "exactly **one** high-signal next step (not a list)"; "three newest comparable authoritative runs"; "for `Q` enabled queries, a source total of `0` through `Q - 1` qualifies that run and `Q` or more does not". Category bans are grounded in literal emit-syntax instances — the fenced query block renders the suppressing and opening shapes, and the runner ban enumerates its members. |
| 17 | `PSG-F-06`, `PSG-SAFE-16`, `PSG-TOOL-06`, `PSG-F-14`, `PSG-F-03` | **Pass (delta-test satisfied).** Measured across the whole range: **zero** new ALL-CAPS / IMPORTANT / NEVER / MUST tokens in any shipped prose surface, so the MUST-graded added-caps delta-test cannot be failed. Rationing improved rather than held: the new `query-strategy.md` carries 16 bold marks in 160 lines, the lowest density of the four shared references measured (`voice.md` 31/167, `errors.md` 63/294, `parallelism.md` 26/145). Certainty is graded, not absolute — "the terms *may* be too specific", "may be suppressing recall" — with an absolute spent only on a genuine invariant ("can never activate it"). |
| 18 | `PSG-F-08`, `PSG-COMM-15`, `PSG-F-09`, `PSG-COMM-01` | **Pass (F4 repaired under this heading's example discipline).** The teaching example is contrastive and labelled (`preference intersection (suppresses recall)` against `complementary role families (open the lanes)`) and closes with an emulation directive ("emulate the relationship, not these terms"). Abstractions are operationalized into observable predicates: the stop condition ("stop once every acceptable lane has coverage and the next query would add none"), the repeated-thin threshold, and "Raw volume is the only evidence … every count downstream of it … describes fit". |

## Part 2 — AAS pack-PR checklist (14 rows)

| # | Governing IDs | Disposition |
|---|---|---|
| 1 | `AAS-PORT-01` (MUST), `AAS-LANG-03`, `AAS-ANTI-26` | **Pass.** The one host-dependent capability the branch expresses is conditional with a named default — "A remote requirement rides in `location` where the source contract can carry it (`agent-data-contract.md`), and fit judgment enforces it either way" — so the requirement holds whichever way the condition resolves. No fabricated call is licensed; the runner is explicitly barred from issuing an unauthorized second search. |
| 2 | `AAS-SKILL-01`, `AAS-SKILL-02`, `AAS-SKILL-03` (all MUST) | **N/A — untouched surface.** No skill created or renamed, no frontmatter hunk in the diff, no new companion file under any skill directory. |
| 3 | `AAS-BOUND-01` (MUST), `AAS-BOUND-04`, `AAS-BOUND-03`, `AAS-ANTI-04`, `AAS-ANTI-08`, `AAS-ANTI-09` | **Pass after repair.** One hop: exactly two `../../shared/references/query-strategy.md` pointers, both in `SKILL.md` files; `find skills -name 'query-strategy.md'` returns nothing and `scripts/build.sh` remains stamp-only, so no generated copy exists either. Load-triggers present on both pointers. `AAS-BOUND-03` produced **F1/F2** — three stale copies of the superseded zero-results contract (repaired). No always-resolved include (`AAS-ANTI-08`) and no parent↔child verbatim duplication (`AAS-ANTI-09`). |
| 4 | `AAS-TRIG-01`–`04`, `AAS-ANTI-10`, `AAS-ANTI-11` | **N/A — untouched surface.** No `description` field changed; no body keyword section added. |
| 5 | `AAS-LANG-01`–`05`, `AAS-PORT-06`, `AAS-ANTI-20`, `AAS-ANTI-21`, `AAS-ANTI-27` | **Pass.** Measured across every added line of shipped prose: zero host tool names, zero host filesystem paths, zero host setup commands, zero host product names, and no host execution mechanic asserted as universal. Model-tier vocabulary and instructions-file references are untouched. |
| 6 | `AAS-SKILL-04`, `AAS-BOUND-02`, `AAS-BOUND-07` | **Pass with one recorded SHOULD deviation** (`AAS-SKILL-04`, below). The branch's new depth went to the shared reference layer (`query-strategy.md`, 160 lines), not into a `SKILL.md` body — the direction `AAS-BOUND-02` asks for. No skill was split. |
| 7 | `AAS-FORM-01`, `AAS-FORM-10`, `AAS-ANTI-12` | **Pass.** Failure classes are correctly separated. The portfolio guidance targets an output-**shaping** failure under a competing incentive (the pull to encode brief preferences into the phrase) and is authored as a pure-positive recipe with an observable stop condition, the two "never" clauses trailing as the grounded backstop rather than leading. The runner rules target a **discipline** slip (re-searching under completion pressure) and correctly keep grounded prohibitions paired with the alternative. `AAS-ANTI-12`: `run-lifecycle.md`'s zero-relevant paragraph was **re-derived** — "broadening suggestion" became "next step" plus a conditional keyed to an observable predicate (raw per-source volume) — which is precisely the remedy that anti-pattern prescribes, not a nuance clause appended to a working recipe. |
| 8 | `AAS-AUTO-05`, `AAS-AUTO-01`, `AAS-PROC-01`, `AAS-ANTI-13`, `AAS-ANTI-18` | **Pass.** Zero new emphasis tokens and the lowest bold density of the shared references (measured, Q17 above). No invented user quote, uncited statistic, or coercive framing in any added line; the one user-facing sentence rendered in full is the onboarding checkpoint example, explicitly labelled as this example's own outcome. |
| 9 | `AAS-EX-01`–`06`, `AAS-ANTI-14`, `AAS-ANTI-38` | **Pass after repair.** All four new samples sit behind an explicit fence at the point of maximum risk (`AAS-EX-01`): "Illustrative only — emulate the relationship, not these terms"; "The values below are schematic, not literals to copy"; "schematic: it shows the keys and value forms, never values to write"; "**illustrative** — … never a count to aim for". Each is annotated with its why (`AAS-EX-06`). **F4** was the substitution-slot violation (`AAS-EX-04`/`AAS-EX-02`), repaired. No fully-rendered sample deliverable (`AAS-ANTI-14`) and no scripted announce line (`AAS-ANTI-38`) — the nudge specifies intent and slots, never a verbatim sentence to emit. |
| 10 | `AAS-AUTO-01`–`03`, `AAS-AUTO-06`, `AAS-ANTI-15` | **Pass.** The one persistent retrieval change is triple-gated — proposal → user acceptance → the *Retrieval-changing* usage preview and scoped confirmation — before any `config.yaml` write, and read-only-until-confirmed is restated at each decision point rather than parked in a footer. The one unconfirmed write is the bounded local `query_health_nudge` marker after the nudge renders, which matches the existing `deeper_coverage_nudges` precedent and is not a one-way door. No blanket mandate: "The signal only asks for the assessment above; it decides nothing." |
| 11 | `AAS-FORM-06`, `AAS-PORT-06`, `AAS-ANTI-29`, `AAS-ANTI-37` | **Pass after repair.** The one genuinely volatile value the branch touches — the rolling cutoff — is handled by removing it from the comparison path rather than by stamping it: "`published_on_or_after` is audit evidence of what this run asked for and never the basis for comparing runs: comparability keys off the saved selector". The `freshness` enum keeps one owner (`conventions.md`), named on the same line at each restatement. **F4** removed the one fabricated dated literal from a shipped body. |
| 12 | `AAS-DIST-01`–`06`, `AAS-ANTI-35`, `AAS-ANTI-36`, `AAS-ANTI-30` | **Pass.** No packaging change at all: `scripts/build.sh` untouched and still stamp-only, no manifest or version edit, no new runtime dependency, nothing executable added. New fixtures live under `tests/fixtures/`, outside the runtime payload (`AAS-DIST-06` / `AAS-ANTI-35`). The version-propagation and determinism halves are untouched surfaces. |
| 13 | `AAS-TEST-01`, `AAS-TEST-02`, `AAS-TEST-04`, `AAS-TEST-05`, `AAS-ANTI-32`, `AAS-ANTI-33`, `AAS-ANTI-34` | **Pass with one recorded SHOULD deviation** (`AAS-TEST-04`, below). New pytest assertions target the fixture-produced run record and the shim's JSON rows, never model prose. New eval expectations grade artifacts — `calls.jsonl` rows, `config.yaml` bytes, `jobs.jsonl` evaluated events, registry bytes — with an explicit instruction not to grade narration (case 57 expectation 1; case 54 expectation 4). No host-namespaced tool name appears in any new success criterion (`AAS-ANTI-34`, checked line by line). `AAS-ANTI-33` is actively prevented: T14.1c records `SKIPPED — authorization or network unavailable` and "a skipped smoke is **never** reported as passed". |
| 14 | `AAS-TEST-10`, `AAS-TEST-11`, `AAS-TEST-15`, `AAS-ANTI-28`, `AAS-ANTI-31` | **Pass.** The branch adds the live contract check outside the shim that `AAS-TEST-09` asks for, and labels its evidence tier honestly (`AAS-TEST-15`): merge-gating behaviour is proved offline by the shim (`job-search` eval 54, `job-search-run` eval 72, plus the deterministic contract tests), while the live smoke checks only that the upstream contract still has the shape the shim encodes. `TESTING.md`'s transitional-residual paragraph now separates four evidence tiers — structural gate, shim scenarios, off-CI stochastic reps, separately-authorized live contract — so a green gate cannot be read as a passed behavioural matrix (`AAS-ANTI-31`'s exact failure). No adapter content added, so no manufactured sections (`AAS-ANTI-28`). |

## Part 3 — PSG anti-patterns (all 13, checked against the diff)

| ID | Verdict |
|---|---|
| `PSG-ANTI-01` monolithic prompt | Not present. New material is one 160-line single-concern shared reference plus small per-surface application blocks; no essay was created and none was folded back together. |
| `PSG-ANTI-02` duplicate or orphan home | **Found ×3, repaired (F1/F2).** The strategy itself has one home enforced by `test_query_strategy_contract.py`; the defects were stale copies of the *superseded* contract in `TESTING.md` and the product spec. |
| `PSG-ANTI-03` hardcoded volatile fact | **Found ×1, repaired (F4).** Otherwise the branch moves the other way: the rolling cutoff is explicitly demoted out of the run-comparison path. |
| `PSG-ANTI-04` one-sided pressure | Not present. The persistence directive carries its truthful-record brake in the same sentence, and the zero-relevant path names both the fit failure and the recall failure. |
| `PSG-ANTI-05` trust delegated output | Not present. New evidence reads are gated on the artifact-authority procedure; evals grade artifacts and forbid grading narration. |
| `PSG-ANTI-06` performative / narration / secrecy filler | Not present. No announce line, no do-not-mention clause; the nudge is capped at one sentence plus one question and silence is explicitly a correct outcome. |
| `PSG-ANTI-07` instruct toward an absent primitive | Not present. The headless runner is explicitly barred from the interactive nudge and marker path; the front door owns both. |
| `PSG-ANTI-08` parallel persona/mode prompt | Not present. The interactive-vs-headless split is carried by per-surface guidance, which is the sanctioned axis. |
| `PSG-ANTI-09` near-identical sibling variants | Not present. The two `SKILL.md` references are pointers, not sibling copies; no adapter-suffixed variant was created. |
| `PSG-ANTI-10` over-trigger by softening | Not present. No description was softened. The nudge is fenced with negative space — a deterministic precondition, then a contextual assessment, then a suppression marker. |
| `PSG-ANTI-11` quantify nothing, ground nothing | Not present. See Q16: countable budgets with relaxation conditions and literal-instance grounding throughout. |
| `PSG-ANTI-12` bare shouted prohibition | Not present. Zero new caps tokens, and every new prohibition states its mechanism. |
| `PSG-ANTI-13` lossy-summary drift | Not present — inverted, in fact: the run record now preserves the issued request verbatim so a later reader compares like with like. |

## Part 4 — AAS anti-patterns (all 42, checked against the diff)

| ID | Verdict |
|---|---|
| `AAS-ANTI-01` host-registered named subagent | Not present — no subagent dispatch added or edited. |
| `AAS-ANTI-02` forwarding command wrappers | Not present — no command layer touched. |
| `AAS-ANTI-03` vendored external doc as doctrine | Not present — nothing vendored. |
| `AAS-ANTI-04` hand-synced duplicate, no drift gate | **Found ×3, repaired (F1/F2).** The new contract values are pinned by marked tables asserted with exact-dict equality, so they cannot drift silently. |
| `AAS-ANTI-05` meta-skill breaks its own budget | Not applicable — no meta-skill in this pack. |
| `AAS-ANTI-06` directive files under `examples/` | Not present. |
| `AAS-ANTI-07` inert per-file ownership sidecars | Not present. |
| `AAS-ANTI-08` always-resolved includes | Not present — both pointers are ordinary relative links. |
| `AAS-ANTI-09` duplicate rules across parent and disclosure child | Not present — the two-pointer rule plus per-surface local application is the structural defence, and a test enforces it. |
| `AAS-ANTI-10` workflow recipe in a description | Not present — no description touched. |
| `AAS-ANTI-11` body keyword sections for discovery | Not present. |
| `AAS-ANTI-12` nuance-clause repair | Not present — the zero-relevant paragraph was re-derived into an observable-predicate conditional (Q7 above). |
| `AAS-ANTI-13` emphasis saturation | Not present — zero new caps tokens; lowest measured bold density. |
| `AAS-ANTI-14` fully-rendered sample deliverable | Not present — no fabricated digest, findings list, or run record ships; F4 tightened the one sample drifting toward concrete. |
| `AAS-ANTI-15` blanket mandate stripping choice | Not present — "The signal only asks for the assessment above; it decides nothing." |
| `AAS-ANTI-16` unmeasured process ceremony | Not present — every new stochastic eval ships a no-guidance control arm with a `control_delta > 0` expectation, which is the measurement this anti-pattern demands. |
| `AAS-ANTI-17` gate demoted to a trailing recap | Not present — the read-only-until-confirmed gate is restated at each decision point, not parked in a footer. |
| `AAS-ANTI-18` fabricated ground truth or coercion | Not present — no invented quote, no uncited statistic, no existential framing. |
| `AAS-ANTI-19` vendor-bound workflow as portable process | Not present. |
| `AAS-ANTI-20` host mechanic as universal law | Not present — checked every added line. |
| `AAS-ANTI-21` hardcoded host filesystem paths | Not present. |
| `AAS-ANTI-22` vendor brand in user-facing artifacts | Not present. |
| `AAS-ANTI-23` platform constraint as prose metadata | Not present — no compatibility-bearing change. |
| `AAS-ANTI-24` single-toolchain lock-in | Not present. |
| `AAS-ANTI-25` assuming skill text is inert | Checked, not present. No added token is a known host trigger keyword; the six new `<!-- query-strategy-contract:… -->` delimiters are inert in Markdown and reuse the delimiter family `conventions.md` already ships. |
| `AAS-ANTI-26` hardcoded subagent-dispatch shape | Not present — the concurrent batch and its sequential fallback are untouched context. |
| `AAS-ANTI-27` host setup commands in shared bodies | Not present. |
| `AAS-ANTI-28` fat unverified adapters | Not present — no adapter content added; the live smoke moves in the corrective direction. |
| `AAS-ANTI-29` volatile literal duplicated across prose and scripts | **Found ×1, repaired (F4).** The `freshness` enum keeps one owner named on the same line at each restatement. |
| `AAS-ANTI-30` copyleft binaries | Not applicable — nothing binary ships. |
| `AAS-ANTI-31` per-host silos with no unifying gate | Not present — the branch strengthens tier honesty in `TESTING.md` rather than adding a silo. |
| `AAS-ANTI-32` assert on skill prose / loose grep alternations | **One recorded SHOULD deviation** (below); every other new assertion targets an artifact. |
| `AAS-ANTI-33` graceful-skip tests exit green | Actively prevented — T14.1c's skip token is mandatory and "never reported as passed", repeated in the closing checklist. |
| `AAS-ANTI-34` host tool names in eval criteria | Not present — every new success criterion checked. |
| `AAS-ANTI-35` dev/eval artifacts in the runtime payload | Not present — new fixtures live under `tests/fixtures/`. |
| `AAS-ANTI-36` bundled tool phones home | Not applicable — nothing executable ships; the live smoke is a documented, separately authorized manual step, never a default. |
| `AAS-ANTI-37` dated facts as bare prose defaults | **Found ×1, repaired (F4).** The rolling cutoff is otherwise demoted out of the comparison path by rule. |
| `AAS-ANTI-38` scripted narration | Not present — the nudge specifies intent and slots ("one evidence sentence naming …, then one question offering …"), not a verbatim line to emit. |
| `AAS-ANTI-39` controller authority over reviewer findings | Not applicable — no review flow in the range. |
| `AAS-ANTI-40` metadata theater | Not present — no padded field, no `[TODO: …]` placeholder shipped. |
| `AAS-ANTI-41` internally contradictory guidance | **Found ×3, repaired (F1/F2).** Noted in the branch's favour: it also *removed* a pre-existing contradiction in onboarding, which previously mapped "remote within the US" onto `location` and, two bullets later, told the agent to fold `remote` into `keywords`. |
| `AAS-ANTI-42` broken references and commands | **Found ×1, repaired (F1).** `TESTING.md`'s sparse-data fallback pointed at T7.10 (many-promising) for behaviour owned by T7.11. Every other new pointer resolves — doc-lint internal-links and `test_reference_resolution.py` are both green. |

## Part 5 — AAS tension register (all 10)

All ten entries were adjudicated on 2026-07-11; the audit checks whether this branch honours each ruling.

| ID | Ruling | This branch |
|---|---|---|
| `AAS-T-01` single source vs self-contained copies | Single-home the source tree; skills reference in place under the guaranteed bundle; build-assemble only as a per-host fallback. | **Honoured.** `shared/references/query-strategy.md` is the one home; no `skills/*/references/query-strategy.md` exists (verified by `find` and by the contract test); `scripts/build.sh` stays stamp-only with no fan-out restored; `test_reference_resolution.py` proves the two in-place pointers resolve on every supported host. |
| `AAS-T-02` zero runtime deps vs script-carried determinism | Bundle portable scripts with a named prose-contract fallback. | **Honoured on the prose-contract side.** No dependency and nothing executable is added. The deterministic parts — the repeated-thin threshold, the five request fields, the marker shape — are pinned as machine-readable marked tables, verified by stdlib-only pytest and the stdlib fixtures, and executed by the model. The threshold is arithmetic the model evaluates directly, so no script is warranted. |
| `AAS-T-03` parallel-by-default on cheap models vs cheapen-mechanics-never-judgment | Mechanical steps cheapest; the fit verdict at the mid-tier reviewer floor; the dispatching model always explicit. | **Untouched.** No model tier, `detail_model`, or dispatch changed. The one new judgment (is this volume contextually thin?) runs in the front door's own turn, never on a delegated cheaper tier. |
| `AAS-T-04` emphasis delta-test vs pushy descriptions | Trigger-calibration caps allowed only on holdout-validated evidence of a real miss. | **Untouched.** No description edited and no trigger-calibration token added; the delta-test is satisfied with zero new caps tokens. |
| `AAS-T-05` what+when vs trigger-only descriptions | Keep the terse capability "what" plus triggers and routing; strip the ordered-workflow recipe. | **Untouched.** No `description` frontmatter changed anywhere in the range. |
| `AAS-T-06` paired prohibition vs pure-positive recipes | Pure-positive recipes for shaping-under-incentive failures; grounded escape-hatch prohibitions stay for discipline failures. | **Honoured, and the split is applied correctly on both sides.** The portfolio guidance (a shaping failure under a competing incentive) is a positive recipe with an observable stop condition, the two "never" clauses trailing as a grounded backstop rather than leading. The runner's rules (a discipline slip under completion pressure) keep grounded prohibitions paired with their alternative. |
| `AAS-T-07` explain-mechanism vs hard fences and excuse walls | Genre-scoped: saturation only in discipline skills; this pack gets mechanism-framing plus a verify-stamp on volatile facts. | **Honoured.** Every new rule states its mechanism — why raw volume is the only breadth evidence, why a rolling cutoff cannot key comparability, why zero relevant is a fit signal. No excuse→reality wall and no saturation. |
| `AAS-T-08` realistic detail vs recitation-resistant schematic slots | Teaching instances stay realistic; substitution slots render as obvious placeholders. | **Honoured after repair.** The teaching instances stay concrete (the query block's real-looking phrases, which the reader is told to reason about rather than copy). The substitution slots were **F4**: the runner's five-field sample rendered three slots concretely next to a bind-and-write instruction and was the one site with no paired schematic rendering. Repaired to the forms `conventions.md` already uses. |
| `AAS-T-09` inline host-tool naming vs actions-only shared bodies | Shared bodies name actions and defer the tool to the adapter. | **Honoured.** Zero host tool names in any added line of shipped prose (measured); the one host-varying capability is a conditional with a named fallback. |
| `AAS-T-10` manual matrix vs unified cross-host gate | Lift the matrix into automated lanes; the manual matrix stays only as the labelled transitional residual. | **Honoured.** The merge-gating behavioural assertions run offline against the shim; the newly added live check sits explicitly outside the gate, is separately authorized, and is recorded as a labelled residual in both the residual paragraph and the closing checklist. |

## Prior-review acceptances re-verified

Three items were accepted by earlier reviews with stated reasons. Each was re-checked against the guides
rather than taken on trust; all three still hold.

- **No path pointer from `home.md`, `onboarding.md`, `customization.md`, or `run-lifecycle.md`.** The
  reasoning holds: a pointer from any of those four would be a second hop from `SKILL.md`, which
  `AAS-BOUND-01` (MUST) forbids for load-bearing material. Honest caveat — the repo's ambient practice is
  looser (`customization.md` already carries second-hop pointers to `internals.md` and `voice.md`), so the
  two-pointer rule is a *stricter* reading chosen deliberately for this contract rather than one the MUST
  compels here. Choosing the stricter form is the more conformant outcome either way, and
  `test_query_strategy_contract.py::test_application_surfaces_apply_the_strategy_instead_of_pointing_at_it`
  is what keeps it true.
- **Contract tables asserted by exact-dict equality against marker-delimited Markdown.** Still the right
  call under `AAS-TEST-04` and `AAS-ANTI-32`: the assertion targets a structured artifact, so wording can be
  rewritten freely while the contract values stay pinned. This is what let F1–F4's prose repairs land
  without touching a single test expectation.
- **`job-search-agent` eval 46 expectations 1–3 grade branch classification rather than an artifact.**
  Re-verified: the case's three arms are byte-identical read-only by design (expectation 5 pins
  `config.yaml` unchanged in every arm), so there is no differentiating artifact to assert on and the branch
  taken *is* the observable outcome. Expectations 4–6 still grade artifacts and call logs, so the case is not
  wholly narration-graded.

## Items on the controller's list (guide bearing noted, not repaired here)

- **The build stamp is drifted; Task 9 regenerates it.** `AAS-DIST-03` names exactly this: the CI
  "build is a no-op" byte-equality gate is the sanctioned mechanism for generated-copy drift, and
  regeneration is its correct owner. Nothing in this audit changes that ownership.
- **`shared/references/internals.md` names one actor two ways** ("job-search home view" vs "job-search
  front door") in adjacent bullets. `PSG-COMM-05` (self-contained, parallel wording) and `AAS-LANG-06`
  (one neutral name for each actor) both prefer a single name. Left to the controller.
- **`test_query_strategy_contract.py`'s `_RANGE_DIGITS` can match ISO-date substrings** (`2026-07-03` yields
  `2026-07`), so a future line such as "the 2026-07-03 search" would false-positive. `AAS-ANTI-32`-adjacent.
  It does not fire today — the gate is green. Left to the controller.

## Verdict

**Blocking defects: 0.** Four defects were found and all four are repaired in this commit. One of them (F3)
is MUST-backed under `PSG-COMM-20` read at its stated mechanism; the other three are SHOULD-backed contract
drift and example-hygiene defects. No MUST-backed checklist row is left failing, and no
`PSG-ANTI-*`/`AAS-ANTI-*` entry remains exhibited.

**SHOULD/CONSIDER deviations: 2**, each with a repository-specific technical justification:

1. **`AAS-SKILL-04` — `skills/job-search-run/SKILL.md` is 684 lines**, over the ~500-line soft ceiling
   (656 at `1e3dbe3`; +28 here). The body is a single indivisible headless run procedure with no
   scope or execution-model seam to split at, and `AAS-BOUND-07` explicitly forbids a size-driven split into
   a sibling skill. Moving run phases into `references/` would put load-bearing steps a second hop from the
   skill, breaching `AAS-BOUND-01` (MUST) — so the deviation buys compliance with a stronger rule. The rule's
   own carve-out ("a dense meta/reference skill may exceed when its content is genuinely all
   activation-critical") applies: every line is on the run path. This branch's new depth went to the shared
   reference layer rather than the body.
2. **`AAS-TEST-04` — `test_no_scanned_surface_prescribes_a_ranged_query_count` asserts over shipped prose.**
   The regression it guards *is* a prose instruction ("Derive 2–3 queries", which previously shipped in
   `docs/product-specs/new-user-onboarding.md`), so there is no artifact to assert on instead. It bans an
   instruction **class** rather than a wording, ships eight positive and five negative controls proving it
   discriminates (a "2–3 sentence Summary" and "Ran 3 searches" must keep passing), and documents its own
   measured scope limits in-file. That is the `AAS-BOUND-08` form — a validator owning what a validator can
   decide — not the `AAS-ANTI-32` wording-coupled oracle, which reddens on harmless rephrasing.

## Gates

All commands were run after the four repairs landed. Observed output:

```
python3 -m pytest -q -p no:cacheprovider tests/test_doc_lint.py tests/test_doc_lint_intra_reference.py \
  tests/test_philosophy_guard.py tests/test_reference_resolution.py tests/test_query_strategy_contract.py
  -> 104 passed in 14.94s

python3 -m pytest -q -p no:cacheprovider
  -> 617 passed in 743.51s (0:12:23)          # exit 0; matches the TESTING.md baseline exactly

rg -n "docs-private|prompt-style-guide|agent-agnostic-skills" skills shared/references
  -> no matches (exit 1)

git ls-files docs-private
  -> no output (0 lines)
```

The four repairs touch Markdown only, so no test expectation moved and the count is unchanged from the
branch baseline. The document gate was re-run a final time with this audit file present in `docs/`, since
`test_doc_lint.py::test_kb_is_clean` walks the whole knowledge base.
