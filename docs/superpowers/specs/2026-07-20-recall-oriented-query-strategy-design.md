---
type: design-doc
title: "Recall-oriented query portfolios and contextual query-health nudges"
status: current
verified: partial
last_reviewed: 2026-07-21
code_refs: [ARCHITECTURE.md, docs/PRODUCT_SENSE.md, docs/design-docs/core-beliefs.md, shared/references/conventions.md, shared/references/internals.md, shared/references/run-lifecycle.md, skills/job-search/SKILL.md, skills/job-search/references/onboarding.md, skills/job-search/references/home.md, skills/job-search-agent/SKILL.md, skills/job-search-agent/references/customization.md, skills/job-search-run/SKILL.md, scripts/build.sh, scripts/check_release_integrity.py, tests/test_reference_resolution.py, .claude-plugin/plugin.json]
claimed_paths: [skills/job-search, skills/job-search-agent, skills/job-search-run, shared/references, scripts, tests, .claude-plugin]
owner_area: Skills & references
repos: [job-search-os]
---

# Recall-oriented query portfolios and contextual query-health nudges

This design addresses a retrieval failure observed during Job Search plugin dogfooding. A brief for an early
product engineer at a seed-to-Series C AI startup produced phrases such as `founding product engineer AI
startup`. Ashby returned no rows for the narrow phrases, while broader probes such as `product engineer` and
`AI engineer` returned full result pages under the same timing conditions. The effective posting date was
not the limiting factor in that session; phrase sensitivity was.

The current onboarding guidance encourages this failure by telling the agent to derive searches from the
brief's Summary, Must-haves, and Strong preferences. That can turn a retrieval query into a compressed
version of the entire brief. The runner then correctly executes the saved phrase across every source, but no
runtime fallback restores recall. Existing same-source and cross-source deduplication already makes a small
portfolio of broader, complementary queries feasible without duplicate judgments.

The design is approved. Implementation is pending. Until implementation lands, the current skill and shared
reference contracts remain authoritative; this document owns the approved delta.

## Goals

- Make newly created and deliberately retuned searches retrieve a broad plausible candidate set with the
  smallest nonredundant portfolio that covers every materially distinct acceptable role lane.
- Keep precision in the Job Preferences Brief and fit judgment instead of encoding the whole preference set
  in source keywords.
- Give the configuring or troubleshooting agent a source-neutral recipe for recognizing contextually thin
  retrieval and proposing broader role-family terms.
- Add a conservative repeated-thin signal that prompts semantic assessment without defining a universal
  result-count threshold.
- Proactively nudge the user at most once for an unchanged search shape when the evidence and contextual
  judgment support broadening.
- Preserve predictable source-call behavior, explicit usage context, and the saved configuration schema.
- Remain complementary to upstream Ashby, Greenhouse, and Lever search improvements rather than encoding
  current provider quirks in the plugin.
- Make every prompt and skill change pass the complete private prompt-style and agent-agnostic pack review
  checklists, with explicit applicability dispositions rather than selective rule citations.

## Non-goals

- Automatically retrying a source with broader keywords during a run.
- Mutating existing saved searches without a user-approved retune.
- Adding broad/narrow variants, source-specific queries, or query roles to the config schema.
- Guaranteeing a fixed number of results for every role or source.
- Treating zero relevant matches, zero new matches after deduplication, or a sparse labor market as proof of
  a keyword problem.
- Adding provider-specific keyword rules or ranking assumptions.
- Increasing query limits or pagination depth by default.
- Applying a universal query-count floor, target, or ceiling to briefs whose acceptable role space differs.

## Product stance

### Retrieval supplies recall; judgment supplies precision

Source queries and fit evaluation have different jobs. Queries should retrieve roles that could plausibly
fit. The Job Preferences Brief should decide whether a retrieved role actually fits. Stage, founder access,
scope, team practices, compensation, and similar preferences usually belong in judgment because they are
often absent from titles and inconsistently indexed in job-board keyword search.

The concise operator rule is:

> Queries maximize plausible recall; the Job Preferences Brief supplies precision.

The design targets the space between two failure directions:

- **over-constrained retrieval**, where a mini-brief phrase suppresses plausible candidates before the agent
  can judge them; and
- **indiscriminate retrieval**, where generic searches create avoidable source calls and detail reads without
  opening a distinct candidate lane.

The agent therefore chooses the smallest nonredundant set of complementary queries that covers every
materially distinct acceptable role lane. Query count is an output of that coverage analysis: it may be one
for a narrow search or several for a user open to mutually exclusive careers. The agent neither compresses
unrelated lanes to hit a quota nor maximizes raw query or row count. This is a positive recipe with an
observable stopping condition rather than a collection of keyword prohibitions (PSG-F-04, PSG-F-09,
PSG-F-10; AAS-FORM-01).

### Thinness is contextual

A raw count has meaning only in context. Two results can be unexpectedly thin for a broadly available role
and entirely plausible for a rare specialty. A deterministic low-volume rule can identify a search that
deserves review, but the configuring agent must judge whether the observed supply is surprising for the
role, terminology, location, freshness window, and healthy-source evidence.

The repeated-thin rule below is therefore a diagnostic signal, not an automatic user-facing alert and not a
definition of search quality.

## Query portfolio behavior

Apply this behavior only when creating a search or when the user deliberately retunes an existing search.
Existing query text otherwise remains byte-for-byte untouched.

1. Read the Job Preferences Brief and enumerate every materially distinct role lane the user would plausibly
   accept. Treat mutually exclusive job families or families with meaningfully different title vocabularies
   as separate lanes.
2. Build a coverage map from each acceptable lane to one or more high-recall queries using terminology likely
   to occur in real job titles or descriptions. A query may cover multiple lanes only when the same posting
   vocabulary genuinely retrieves both.
3. Add another query within a lane when it covers materially different posting vocabulary that the existing
   query is likely to miss.
4. Merge or remove a query when another query already covers its likely candidate pool and it adds no unique
   lane or vocabulary coverage.
5. Stop when every acceptable lane maps to retrieval coverage and another query would add no meaningful lane
   or vocabulary coverage. There is no universal query-count target or cap.
6. Leave stage, founder access, ownership, culture, compensation, coding-agent usage, and similar preference
   evidence in the brief unless a term is itself a common role-family label and opens a distinct pool.
7. Preserve the current query limits and pagination defaults. Improve term coverage before increasing result
   depth.
8. Show the brief summary and lane-to-query coverage map in the existing single setup or retune checkpoint so
   the user can see both omitted lanes and redundant queries.
9. Represent a remote requirement through the query location where the source contract can express it and
   always retain it in fit judgment; when the contract cannot express it, retrieve broadly and filter
   agent-side instead of automatically conjoining `remote` with every role phrase.

For the dogfood brief, the contrast is:

```text
Avoid mini-brief intersections:
  founding product engineer AI startup
  early product engineer developer tools
  agent infrastructure product engineer

Prefer a coverage map of complementary role families:
  product engineering       -> product engineer
  AI engineering            -> AI engineer
  infrastructure engineering -> infrastructure engineer  # only if this is an acceptable distinct lane
```

These phrases are contrastive examples with open slots, not templates to copy. A different brief may imply
different canonical terms. In all cases, the evaluator still applies the complete preferences brief to every
candidate that reaches judgment. Emulate the relationship shown here — complementary role families replace
preference intersections — rather than the literal terms (PSG-F-08, PSG-F-11; AAS-EX-02, AAS-EX-03,
AAS-EX-04, AAS-EX-06).

## Contextual thinness guidance

The canonical troubleshooting guidance is:

> If healthy source calls return fewer results than reasonably expected for the role family, consider
> broadening the search queries. Judge thinness relative to role rarity and active filters instead of a
> universal result-count threshold. Broaden by removing preference terms and using canonical role families,
> while retaining those preferences for fit evaluation.

When configuring, retuning, reviewing first-run results, or troubleshooting, the agent follows this recipe:

1. Inspect raw `results_returned` by query and source before deduplication, seen-item filtering, selection,
   or fit judgment.
2. Use only completed, healthy source streams as evidence about keyword quality; route failed, blocked, or
   incomplete streams through their existing operational recovery.
3. Consider the role family's plausible supply, the number of concepts conjoined in each phrase, location,
   freshness, and contrasting results from sibling queries or other healthy sources.
4. If the observed supply is surprisingly low, propose replacing preference-heavy phrases with broader,
   complementary role families.
5. Preserve the accepted role-lane coverage while replacing over-specific phrases in place where possible.
   Add or remove queries only when the coverage map requires it, and state the resulting query-count delta.
6. Use the existing retrieval-changing configuration flow: preview usage impact, obtain confirmation, then
   persist the retune; until confirmation, limit the action to a read-only proposal.

The agent may suggest broadening after a single live run when the evidence is strong. For example, zero to
two rows for `founding AI engineer` on a healthy general job source is plausibly surprising; the same count
for `founding astrophysicist early stage startup` may reflect a genuinely rare role. These examples teach the
comparison and serve only as contrastive evidence, not as a role-specific allowlist.

Low relevance is a separate outcome. A query that retrieves many candidates which the evaluator rejects is
not retrieval-starved; it may need better judgment guidance or a deliberately narrower role family, not the
thin-results recovery path.

Use this decision table to keep neighboring recovery paths consistent:

| Observed state | Interpretation | One next action |
|---|---|---|
| A source call failed, blocked, or ended incomplete | Operational health is unknown | Apply the named source/error recovery and wait for healthy evidence before judging query breadth. |
| Raw retrieval is contextually or repeatedly thin | The current phrases may be suppressing recall | Propose broader, complementary role families. |
| Raw retrieval is healthy but no posting is relevant | Recall exists; the returned lane or brief alignment is wrong | Inspect rejection reasons and propose one targeted lane replacement or brief clarification; broadening is appropriate only when that evidence identifies a missing adjacent lane. |
| The user explicitly wants fewer fetched postings from a healthy noisy lane | Source-side narrowing is intentional | Offer a narrower role term, location, lower limit, or disabled query with the ordinary usage/change semantics. |
| Raw results are healthy but all candidates are already known | The feed has no unseen work, not a retrieval shortage | Report that the current results were already seen and leave query breadth unchanged. |

This table supersedes unconditional broadening language in onboarding, home, customization, and
zero-relevant recovery. Implementation must update or remove every conflicting copy in the same change so
the plugin never ships both policies (AAS-BOUND-03, AAS-BOUND-06, AAS-FORM-07, AAS-ANTI-09, AAS-ANTI-41,
PSG-COMM-20).

## Repeated-thin diagnostic signal

The home view uses a conservative deterministic condition to decide when contextual query-health assessment
is warranted for an existing search.

A source is a repeated-thin candidate when all of the following are true:

- the three newest comparable, lifecycle-authoritative runs are closed, complete, non-canary runs;
- every enabled query stream for that source completed successfully in each run;
- every stream used the active saved request rather than an ad-hoc keyword, source, location, recency, or
  limit override;
- the saved query portfolio, source, locations, limits, source set, and freshness policy are unchanged across
  the three runs; and
- in each run, total raw `results_returned` across that source's enabled queries is less than the number of
  enabled queries — fewer than one raw row per query on average.

For `Q` enabled queries, a source total from zero through `Q − 1` qualifies that run; `Q` or more does not.
The count is intentionally raw: `new`, `unique_candidates`, `selected_for_review`, detail reads, and relevance
verdicts cannot activate the signal.

The signal asks the agent to apply the contextual recipe. It does not force a nudge. A rare role, deliberately
tight location, or other plausible explanation may make no user-facing suggestion the right outcome.

If one or more sources warrant a suggestion, render one evidence sentence followed by one question. When a
long source list would make that sentence hard to scan, use one evidence bullet followed by the same one
question. Use this schematic shape, adapting its words and slots rather than quoting it literally:

```text
<affected source or source count> returned only <observed raw range> across each of the last three comparable
runs, so the current search terms may be too specific.
Would you like me to propose broader role families?
```

Name the affected source or sources and the observed range, and use `may` so the wording preserves market
supply and active filters as plausible explanations instead of claiming keywords are proven causal. Offer
exactly one action; until the user accepts and confirms its usage impact, keep the interaction read-only.

Record a nudge only when it is actually shown. Suppress another user-facing query-health nudge while the
normalized saved search shape is unchanged. A confirmed query, location, limit, freshness, or source change
creates a new shape that may be assessed after three new comparable runs. Multiple thin sources share one
marker and one suggestion.

## Comparable request evidence

The current query-source run record contains `query_id`, `source`, and `keywords`, but not enough request
evidence to prove that low-volume runs used the same location, recency policy, or result limit. Add these
normalized fields to each `queries[]` stream:

- `request_origin`: `saved | one_off`
- `location`: the exact normalized location sent, or `null`
- `limit`: the exact positive integer sent
- `freshness`: the canonical saved freshness selector when `request_origin` is `saved`, otherwise `null`
- `published_on_or_after`: the exact effective date sent, or `null`

`freshness` uses the enum owned by `shared/references/conventions.md`; this design does not create another
enum owner. Record `published_on_or_after` for auditability, but compare the saved freshness selector rather
than literal effective dates. A rolling `past-2-weeks` policy produces a different cutoff on every run while
remaining the same saved search shape. Only streams with `request_origin: saved` contribute to the repeated
signal.

Older run records without these fields remain readable for their existing purposes but are ineligible for
query-health comparison. This fails closed instead of guessing request equivalence.

Add one bounded registry marker for the last user-facing query-health nudge. Store the explicit normalized
shape so an agent can inspect and compare it without reproducing an unspecified hashing algorithm:

```jsonc
"query_health_nudge": {
  "search_shape": {
    "queries": [
      {"id":"<query id>", "keywords":"<normalized keywords>", "location":null, "limit":25}
    ],
    "sources": ["<enabled source>"],
    "freshness": "<canonical saved selector>"
  },
  "shown_at": "<UTC ISO-8601>",
  "affected_sources": ["<source>"],
  "outcome": "shown|accepted|dismissed"
}
```

The shape contains enabled retrieval configuration only — no preference prose, posting data, or credentials.
The marker is an index and suppression aid, not evidence that a nudge is warranted; readers revalidate the
authoritative run records before every decision. Update `outcome` only when that interaction occurs. The
single marker may be overwritten after a new search shape qualifies, so state remains bounded. Explicit
fields resolve the runtime-dependency-versus-determinism tension without adding a hashing script (AAS-T-02;
AAS-FORM-08; AAS-LANG-08).

These additions affect run-audit and registry state only. The version-2 saved configuration schema does not
change and needs no config migration or config-version bump; the shipped plugin still receives its ordinary
manifest version bump because agent-facing runtime content changes.

## Responsibility map

### `shared/references/query-strategy.md` — canonical guidance

Create one public shared reference that opens with a self-locating line naming query derivation and
thin-retrieval troubleshooting as its purpose. It owns:

- retrieval queries versus fit preferences;
- recall-oriented portfolio construction with the coverage-map stopping condition;
- the contextual thinness recipe;
- the repeated-thin signal and proactive nudge behavior; and
- the executor alternative for low volume: finish the configured streams, record truthful evidence, and
  leave any broader request to a later user-approved retune.

Keep agent-facing strategy here and run-record field mechanics in `conventions.md`. The shared reference is
justified even with two consuming skills because the same substantive domain method crosses the interactive
front door and the operator manual; forcing the runner to load judgment guidance it never applies would
waste disclosure budget. Keep the reference short enough to load with those flows; if schema mechanics or
long examples make it exceed 150 lines, move those mechanics to their existing canonical owner and retain a
one-hop pointer rather than expanding this strategy reference (AAS-SKILL-04, AAS-SKILL-07, AAS-BOUND-02,
AAS-BOUND-05, AAS-BOUND-11).

The installed plugin is complete from its public references. Private prompt and agent-agnostic style guides
inform authoring and review only and stay outside every shipped skill and package artifact.

### `skills/job-search/SKILL.md`

- Add a direct conditional pointer to `../../shared/references/query-strategy.md`: load it when
  deriving or retuning queries, reviewing first-run retrieval volume, or assessing a saved search's query
  health.
- Keep the existing direct pointers to onboarding and home. Those local references apply the already-loaded
  strategy without linking onward or restating its rules.
- Preserve the current frontmatter description because the existing setup, retune, and home triggers already
  cover the new behavior; no new skill or discovery surface is introduced.

### `skills/job-search/references/onboarding.md`

- Apply the strategy loaded directly by the parent skill during new setup and explicit retuning without
  copying its recipe into this file.
- Replace the current `2–3` derivation instruction and checklist item with lane-to-query coverage: write the
  nonredundant queries needed to cover every materially distinct acceptable lane, with no fixed total.
- Inspect the first live retrieval and use contextual judgment to flag surprisingly thin results.
- Keep the existing fast first-run flow and single confidence checkpoint, rendering the coverage map so the
  user can spot an omitted lane or a redundant query before the first live run.

### `skills/job-search/references/home.md`

- Apply the strategy loaded directly by the parent skill during troubleshooting and query editing without
  copying its recipe into this file.
- Read only lifecycle-authoritative records for the newest three comparable runs.
- Treat the deterministic signal as a prompt for contextual assessment.
- Show at most one combined proactive nudge for an unchanged shape.
- Route acceptance through the existing retrieval-changing usage preview and confirmation flow.

### `skills/job-search-agent/references/customization.md`

- Apply the strategy loaded directly by the parent skill during source-side filtering and thin-result
  troubleshooting without copying its recipe into this file.
- State the general advice: if results are thin, consider broadening search queries.
- Keep raw retrieval health separate from fit quality.

### `skills/job-search-agent/SKILL.md`

- Add a direct conditional pointer to `../../shared/references/query-strategy.md`: load it when the
  user creates, retunes, explains, or troubleshoots retrieval queries or thin results.
- Keep the current frontmatter description; its query-customization and troubleshooting triggers already
  cover this behavior.

### `skills/job-search-run/SKILL.md`

- Continue to execute the saved or authorized one-off request exactly as resolved.
- Write the additional normalized request evidence to each query-source stream.
- Treat a healthy low-volume response as completed retrieval, write its evidence, and return control to the
  interactive configuration flow for any later broadening decision.

### `shared/references/conventions.md`

- Own the additive run-record fields.
- Preserve strict validation for new records while retaining the repository's explicit compatibility rules
  for older records.

### `shared/references/internals.md`

- Own the bounded registry marker schema and its ordinary whole-file write rules.

The strategy reference remains single-homed under `shared/references/`. Each consuming `SKILL.md` points
directly to that canonical file with an observable load trigger; no reference links through another
reference, and the stamp-only build creates no per-skill copy. This satisfies one-hop disclosure while
preserving one authoritative authored home. `tests/test_reference_resolution.py` proves the direct pointers
resolve under every supported host install view (AAS-PACK-02, AAS-BOUND-01, AAS-BOUND-03, AAS-BOUND-04,
AAS-DIST-03, AAS-T-01).

## User and usage behavior

Coverage-complete portfolios may contain more queries than the old fixed default, and broader phrases can
increase the number of candidates selected for detail reads. Use the existing setup and saved-retune consent
rules rather than adding another gate:

- during setup, show the exact `enabled queries × enabled sources` first-page baseline in the existing
  confidence/calls-first flow; the user's setup request remains the authorization defined by onboarding;
- during a saved retune, show the exact current and proposed first-page baselines and their delta;
- say that broader results may increase detail and continuation calls without inventing an exact maximum;
- apply the existing scoped confirmation before writing a later persistent increase; and
- keep one-off explicitly requested searches within the existing one-off consent rules.

Coverage remains the derivation criterion: the agent may show the exact call consequence and let the user
narrow their accepted role space, but it does not silently omit a stated role lane merely to preserve the old
query count.

The proactive nudge itself performs no metered work. Looking at local run records and proposing a retune is
read-only until the user confirms a configuration change or requests a fresh run.

## Failure and edge behavior

- **Source error or incomplete pagination:** exclude that source/run from the three-run sequence and apply
  its existing operational recovery; query breadth remains unclassified until healthy evidence exists.
- **Zero new after deduplication:** leave the query-health signal inactive when raw results are healthy.
- **Zero relevant after judgment:** use the query-health decision table above: thin raw evidence may support
  broadening, while healthy raw evidence routes to rejection-pattern analysis and one targeted retune.
- **Rolling freshness dates:** compare the saved freshness selector, not the changing effective cutoff date.
- **Ad-hoc searches:** record their exact request evidence but exclude them from proactive saved-search
  assessment.
- **Config changes between runs:** start a new comparable sequence for the new shape and keep each shape's
  evidence separate.
- **Rare roles:** let contextual judgment decline the nudge even when the deterministic signal is present.
- **Multiple affected sources:** render one suggestion and one action.
- **Old records:** ignore them for query health instead of backfilling or inferring missing request fields.
- **Dismissal:** retain the marker and suppress another nudge for the same shape.

## Validation strategy

Skill and prompt edits follow RED-GREEN-REFACTOR rather than relying on post-hoc review:

1. **RED:** before changing runtime guidance, add the source-sensitive query scenario and run the current
   plugin for at least five fresh-context repetitions. Confirm the baseline produces the observed shaping
   failure at a measurable rate; if it does not, stop and redesign the scenario before authoring guidance.
2. **GREEN:** add the minimum query-strategy guidance and rerun both the guided arm and the unchanged
   no-guidance control for at least five repetitions each.
3. **REFACTOR:** tighten wording only when effect-level review finds a loophole or high variance, then rerun
   both arms and the deterministic suite.

### Behavioral evaluations

Add focused evaluations for the observable configuration, calls, and user-facing decisions:

1. Given the dogfood preferences, setup maps every materially distinct acceptable lane to high-recall terms,
   gives each emitted query a unique coverage rationale, and produces no preference-heavy mini-brief.
2. Given preferences spanning private-equity investing, long/short equity investing, equity research, and
   corporate development, setup covers all four mutually exclusive lanes even though that exceeds the former
   `2–3` default; the checkpoint makes the complete mapping visible.
3. Given overlapping role aliases whose likely candidate pools are already covered, setup merges or omits the
   redundant query instead of treating every phrase in the brief as a separate lane.
4. A source-neutral fake search service returns no rows for phrase-stuffed input and current rows for broad
   role terms; guided setup retrieves candidates and evaluates them against the full brief.
5. Removing stage, founder-access, and agent-usage words from retrieval does not remove those criteria from
   fit reasoning.
6. A broad role with surprisingly sparse healthy results produces a broadening proposal after contextual
   assessment.
7. An exceptionally rare role with the same row count may correctly produce no proposal.
8. Setup renders the exact query-source baseline before its first live run without adding another confirmation;
   a later persistent retune renders the current and proposed baselines, their delta, and possible variable
   detail/continuation growth, then waits for the confirmation required by the existing saved-change flow.
9. The runner call log contains exactly the configured query-source streams and no hidden fallback call.

Run behavioral wording cases at least five repetitions and include a no-guidance control that withholds the
new query-strategy guidance. Assert effects in query artifacts, call logs, fit judgments, and configuration
writes rather than exact explanatory prose. Manually inspect every flagged result, report pass rates and
variance, and review whether each assertion discriminates the intended failure rather than rewarding a
keyword echo. Run the suite on every release-intended primary model the eval harness can select, including
the two dogfood model variants when available; record an unavailable model as a skip rather than a pass
(PSG-F-09; AAS-TEST-03, AAS-TEST-04, AAS-TEST-07, AAS-TEST-08, AAS-TEST-13, AAS-TEST-16).

### Deterministic tests

- New run-record validation accepts and requires the normalized request fields for current records.
- Explicit compatibility tests keep older authoritative records readable while proving they cannot qualify
  for query-health comparison.
- Fewer than three comparable runs, any failed stream, any one-off request, or any search-shape difference
  prevents the repeated-thin candidate signal.
- Three healthy comparable runs below the per-query average threshold request contextual assessment.
- `new`, dedup, selection, and relevance counts cannot activate the signal.
- A shown or dismissed marker suppresses another user-facing nudge for the same shape.
- Changing queries, location, limits, freshness, or sources permits a new sequence and later nudge.
- Multiple affected sources produce one marker and one suggestion.
- Documentation lint verifies canonical ownership and one-hop pointers rather than duplicated rules.

Use the fake agent-data service for deterministic source behavior and merge-gating behavioral evaluation; no
merge-gating assertion depends on live Ashby, Greenhouse, Lever, or LinkedIn row counts. Maintain one
separately authorized, non-blocking live contract smoke outside the shim to verify the request fields,
response echo, and source identity contract. Limit its assertions to that stable contract because market
inventory is volatile, and report a skipped live smoke as skipped rather than green
(AAS-TEST-02, AAS-TEST-09, AAS-TEST-15; AAS-T-10).

## Complete style-guide compliance gate

Before implementation is called complete, review the actual prompt/skill diff against both operational
checklists, not only the rule IDs cited in this design:

1. Answer all 18 questions in `docs-private/prompt-style-guide/09-checklist-and-rule-index.md`.
2. Answer all 14 questions in
   `docs-private/agent-agnostic-skills/14-checklist-and-rule-index.md`.
3. For every question, record `pass` or `N/A — <untouched surface and reason>`. Inconvenience is not an N/A
   reason.
4. A failed MUST-backed question blocks completion. A SHOULD or CONSIDER deviation requires a one-line
   technical justification tied to this repo.
5. Check all 13 PSG and 42 AAS anti-patterns against the diff, explicitly including duplicate guidance,
   nuance-clause repairs, emphasis walls, fully rendered user narration, prose-string assertions,
   contradictory guidance, and broken references.
6. Revisit all ten AAS tensions. This delta resolves the applicable tensions as follows: a single-homed
   canonical reference plus direct one-hop pointers for T-01; explicit shape data without a new script for T-02; positive recipes
   for shaping and alternative-paired invariants for T-06; schematic examples for T-08; and deterministic
   shim gates plus a labeled live smoke for T-10. Record the other tensions as N/A with their untouched
   surfaces.
7. Cite current rule IDs only. Verify each citation against the two private rule indexes during the authoring
   audit; repository document lint still runs for structural checks but is not represented as an ID validator.

This gate covers all 101 PSG rules and all 122 AAS rules through their complete indexes. It does not pretend
that tool-definition, injection, delegation-output, or adapter rules govern an untouched surface; it makes
their non-applicability explicit and reviewable.

### Design-time checklist disposition

The approved design itself has the following complete checklist disposition. Implementation repeats the
exercise against the actual diff because an aligned design cannot prove aligned wording on its own.

| PSG checklist item | Disposition | Design evidence |
|---|---|---|
| 1 | N/A | This delta adds no persistence or finish-at-all-costs directive. |
| 2 | Pass | Over-constrained versus indiscriminate retrieval and deterministic signal versus contextual rarity are both ranked. |
| 3 | Pass | Raw authoritative records ground the nudge; causal language remains `may`. |
| 4 | Pass | Failed streams route to named operational recovery rather than keyword diagnosis. |
| 5 | Pass | New durable fields and marker shapes have exact JSON slots and deterministic ownership. |
| 6 | N/A | No delegated verdict contract changes. |
| 7 | N/A | No lower-trust payload is spliced into a new higher-trust prompt. |
| 8 | N/A | No harness injection or degrading injection changes. |
| 9 | N/A | No compaction or continuation-summary changes. |
| 10 | N/A | No subagent brief or return-channel changes. |
| 11 | N/A | Existing skill descriptions remain unchanged because their current scopes cover the behavior. |
| 12 | N/A | No delegation mode or concurrency change. |
| 13 | N/A | No tool description changes. |
| 14 | N/A | No tool parameter-description changes. |
| 15 | N/A | No tool precondition or error-string changes. |
| 16 | Pass | Query coverage has an observable stop condition; comparison window, threshold, nudge shape, and examples are countable or explicitly schematic. |
| 17 | Pass | The planned runtime guidance adds no alarm-channel emphasis. |
| 18 | Pass | Query derivation uses a labeled contrast and all recovery tests assert observable effects. |

| AAS checklist item | Disposition | Design evidence |
|---|---|---|
| 1 | N/A | No optional host capability or fabricated fallback is introduced. |
| 2 | N/A | No skill is added or renamed and no frontmatter field changes. |
| 3 | Pass | Each consumer gets a direct conditional pointer to the single-homed canonical reference. |
| 4 | N/A | Existing descriptions already trigger for setup, retuning, and troubleshooting and remain unchanged. |
| 5 | Pass | Runtime guidance names actions and source categories without host tools or paths. |
| 6 | Pass | The strategy reference has a 150-line budget with a move-to-owner relaxation condition. |
| 7 | Pass | Shaping uses positive recipes, branches use a table, and discipline gates name the permitted alternative. |
| 8 | Pass | Routine advice stays at ordinary register; absolutes are reserved for existing invariants. |
| 9 | Pass | Query and nudge examples are fenced, schematic, annotated, and explicitly non-verbatim. |
| 10 | Pass | Assessment is read-only by default; persistent broadening receives usage context and scoped consent. |
| 11 | N/A | No volatile host literal or dated runtime default is introduced. |
| 12 | Pass | Manifest versioning, direct-reference resolution, deterministic double-build, and payload inspection are explicit. |
| 13 | Pass | Tests use naive prompts and observable effects with RED/GREEN, controls, repetitions, and surfaced skips. |
| 14 | N/A | No adapter or host-contract surface changes; the source-contract smoke is separately labeled and non-gating. |

The anti-pattern pass finds no intended instance after these revisions. In particular, the implementation
must remove the existing contradictory query/recovery copies (AAS-ANTI-41) rather than layering a nuance
clause over them (AAS-ANTI-12), and must keep examples schematic rather than scripting narration
(AAS-ANTI-38). Of the ten tension-register entries, T-01, T-02, T-06, T-08, and T-10 are resolved above;
T-03, T-04, T-05, T-07, and T-09 have no touched surface in this delta.

## Rollout and compatibility

- Ship the canonical strategy and skill pointers together so no skill observes a partial contract.
- Apply the portfolio behavior immediately to new searches and user-approved retunes.
- Preserve existing config files byte-for-byte during installation and the first home view.
- Start repeated-thin eligibility only after three new current-format, comparable runs exist. The delayed
  first proactive nudge is intentional and avoids speculative migration.
- Keep all behavior source-neutral. Upstream ATS improvements may increase yield while the separation between
  retrieval recall and agent judgment remains valid.
- Bump the authoritative plugin manifest version rather than adding a version to skill frontmatter, propagate
  it through every host manifest with the existing release tooling, and regenerate the build stamp.
- Run the deterministic stamp-only build twice: the first run refreshes the content hash and the second must
  be a no-op. Then run reference-resolution, release-integrity, frontmatter, platform, document, and philosophy
  gates.
- Inspect the built payload to confirm `docs-private/`, design specs, and eval/dev artifacts remain excluded;
  only the intended public runtime reference and skill/runtime changes ship.
- This design document alone does not change a shipped plugin build.

## Alternatives considered

### Broad-only title anchors

Always using only canonical broad titles is simpler and can maximize recall, but crowded first pages may hide
specialized yet relevant lanes. The approved design permits another query within a lane when distinct posting
vocabulary expands coverage rather than conjoining preferences.

### Automatic runtime fallback

Running a broader second query after low yield could rescue a source immediately. It was rejected because it
adds dynamic metered calls, complicates provenance and usage previews, changes the runner from executor to
configurator, and overlaps with upstream ATS work.

### Broad/narrow query schema or per-source variants

Explicit query roles or source-specific variants would make behavior deterministic but add configuration
surface, validation, migration, and versioning work before the product has evidence that users need those
knobs. The current shared query schema and deduplication already support the approved portfolio behavior.

## Approved decisions

- Only newly created or deliberately retuned searches receive rewritten query portfolios.
- Existing searches receive a proactive, evidence-backed, once-per-shape suggestion rather than automatic
  broadening.
- Filtering primarily happens in agent judgment; source terms optimize plausible recall.
- Query count is derived from lane coverage with no universal target or cap: every acceptable lane receives
  sufficient retrieval coverage and every emitted query contributes unique lane or vocabulary coverage.
- Thinness is context-dependent agent judgment; the three-run numeric condition only prompts assessment.
- The runner remains deterministic by issuing exactly the configured query-source streams and recording a
  healthy low-volume response for later interactive assessment.
- Query strategy is source-neutral and single-homed in one new shared reference.
- Run records gain explicit request evidence; saved config remains version 2 with no schema change.
