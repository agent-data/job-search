# Query strategy — deriving queries, judging retrieval health, broadening with consent

This file governs query derivation, contextual retrieval-health assessment, and user-approved broadening: it
is the single home for **what to search for and when to search wider**. The interactive front door and the
operator manual load it directly; onboarding, the home view, and customization apply their part of it and
never restate it.

**The rule:** Queries maximize plausible recall; the Job Preferences Brief supplies precision.

Retrieval and judgment have different jobs. A query's job is to return roles that *could* plausibly fit; the
brief's job is to decide whether a returned role actually fits. Two failure directions bracket the target: an
over-constrained phrase that suppresses plausible candidates before anything can judge them, and
indiscriminate generic retrieval that spends calls and detail reads without opening a distinct candidate lane.

## Building a query portfolio

Apply this when a search is **created** or when the user **deliberately retunes** one. Otherwise saved query
text stays byte-for-byte untouched — opening the home view is not a retune.

<!-- query-strategy-contract:portfolio -->
| Field | Contract value |
|---|---|
| `scope` | `new_search_or_user_approved_retune` |
| `coverage_unit` | `materially_distinct_acceptable_role_lane` |
| `query_vocabulary` | `real_posting_title_or_description_terms` |
| `add_query_when` | `materially_different_lane_or_posting_vocabulary` |
| `merge_or_remove_when` | `no_unique_lane_or_vocabulary_coverage` |
| `stop_when` | `every_lane_covered_and_next_query_adds_no_meaningful_coverage` |
| `query_count` | `derived_no_universal_target_or_cap` |
| `precision_owner` | `job_preferences_brief_and_fit_judgment` |
<!-- /query-strategy-contract:portfolio -->

Read the brief and enumerate every materially distinct role lane the user would plausibly accept, treating
mutually exclusive job families — or families whose title vocabularies barely overlap — as separate lanes.
Map each lane to one or more high-recall queries in terminology that actually occurs in job titles and
descriptions. One query may cover several lanes when the same posting vocabulary genuinely retrieves them all.
Then close the map: add a query inside a lane when it reaches posting vocabulary the existing one is likely to
miss, merge or drop a query whose candidate pool another query already covers, and stop once every acceptable
lane has coverage and the next query would add none. The resulting count is an *output* — it may be one query
for a narrow search or several for a user open to mutually exclusive careers. Never compress unrelated lanes
to hit a number, and never pad the portfolio to look thorough.

Leave stage, founder access, ownership, culture, compensation, coding-agent use, and similar preference
evidence in the brief, unless the term is itself common posting vocabulary that opens a distinct lane. Keep
the saved result limits and pagination depth as they are — improve term coverage first. Express a remote
requirement through the query's location where the source contract can carry it
(`agent-data-contract.md`), keep it in fit judgment either way, and never conjoin "remote" onto every role
phrase as a keyword.

Illustrative only — emulate the relationship, not these terms:

```text
preference intersection (suppresses recall):  founding product engineer AI startup
complementary role families (open the lanes): product engineering -> product engineer
                                              AI engineering      -> AI engineer
```

The broad queries are how plausible candidates reach judgment at all. What they do not cost is precision: the
complete brief is still applied to every candidate that reaches fit evaluation.

## Judging retrieval health in context

A raw count means nothing by itself. Two results can be surprisingly thin for a broadly available role and
entirely plausible for a rare specialty. Read the raw volume of each query and source — the count before
deduplication, seen-item filtering, selection, and judgment, recorded per query stream in `conventions.md` —
against all of:

- **role commonness** — the plausible market supply for that role family;
- **posting vocabulary** — how many concepts the phrase conjoins, and whether those words appear in real
  postings;
- **location** — how tight the requested location is;
- **freshness** — how narrow the saved freshness selector is (its enum is owned by `conventions.md`);
- **healthy-source evidence** — only completed, successful streams say anything about keyword quality, and a
  sibling query or another healthy source in the same run is the sharpest contrast available;
- **fit-rejection evidence** — postings that arrive and get rejected are a precision signal, not a shortage.

When the observed supply is surprisingly low, propose replacing preference-heavy phrases with broader,
complementary role families. Preserve the accepted lane coverage: replace over-specific phrases in place where
you can, add or remove a query only where the coverage map requires it, and say what the query count becomes.
Every proposal stays read-only until the user accepts it — preview the impact with
[Agent-data usage decisions](internals.md#agent-data-usage-decisions), take the confirmation the retrieval
change requires, then persist.

## Which path a query-health observation takes

**Retrieval health is not fit quality.** Raw volume is the only evidence about whether the phrases are
suppressing recall; every count downstream of it — new, deduplicated, selected, detail-read, relevant —
describes fit and says nothing about breadth. Read the observation, then take its one action:

<!-- query-strategy-contract:decision-table -->
| Field | Contract value |
|---|---|
| `failed_blocked_or_incomplete` | `operational_recovery_then_wait_for_healthy_evidence` |
| `contextually_or_repeatedly_thin` | `propose_broader_complementary_role_families` |
| `healthy_raw_but_zero_relevant` | `inspect_rejections_then_replace_lane_or_clarify_brief` |
| `healthy_noisy_and_user_wants_less` | `intentional_narrowing` |
| `healthy_but_all_known` | `report_seen_results_and_leave_breadth_unchanged` |
<!-- /query-strategy-contract:decision-table -->

- **A source call failed, was blocked, or ended incomplete.** Operational health is unknown, so retrieval
  says nothing yet. Apply that failure's named recovery in `errors.md` and wait for healthy evidence before
  judging breadth.
- **Raw retrieval is contextually or repeatedly thin.** The current phrases may be suppressing recall.
  Propose broader, complementary role families.
- **Raw retrieval is healthy but nothing is relevant.** Recall already exists; the lane or the brief
  alignment is what is wrong, and zero relevant results never prove on their own that the terms were too
  narrow. Inspect the rejection reasons, then propose one targeted lane replacement or one brief
  clarification; broaden only where that evidence names a missing adjacent lane.
- **The user wants fewer fetched postings from a healthy, noisy lane.** The narrowing is intentional. Offer
  a narrower role term, location, lower limit, or a disabled query under the ordinary change semantics.
- **Raw results are healthy but every candidate is already known.** The feed holds no unseen work. Say the
  results were already seen and leave query breadth unchanged.

## The repeated-thin signal

For an existing saved search, one deterministic condition decides when a contextual assessment is *warranted*.

<!-- query-strategy-contract:repeated-thin -->
| Field | Contract value |
|---|---|
| `window` | `three_newest_comparable_authoritative_runs` |
| `run_state` | `closed_complete_non_canary` |
| `stream_state` | `every_enabled_stream_for_source_successful` |
| `request_origin` | `saved_only` |
| `shape` | `queries_sources_locations_limits_and_freshness_unchanged` |
| `threshold` | `source_total_results_returned_less_than_enabled_query_count_each_run` |
| `effect` | `contextual_assessment_not_automatic_nudge` |
<!-- /query-strategy-contract:repeated-thin -->

A source is a repeated-thin candidate only when every row holds across the three newest comparable runs, each
of them lifecycle-authoritative. `saved_only` excludes any stream that ran under an ad-hoc override, and the
shape comparison keys off the saved freshness selector rather than the rolling cutoff each run happened to
send (`conventions.md`). The threshold applies per run: for `Q` enabled queries, a source total of `0` through
`Q - 1` qualifies that run and `Q` or more does not. The count is deliberately raw `results_returned` — new,
deduplicated, selected, detail-read, and relevance counts can never activate it.

The signal only asks for the assessment above; it decides nothing. A rare role, a deliberately tight location,
or any other plausible explanation makes saying nothing the right outcome.

## One nudge, one question

When the assessment supports speaking up, say it once: one evidence sentence naming the affected source or
sources and the raw volume observed — one evidence bullet instead when a long source list would be hard to
scan — then one question offering to propose broader role families. Keep the causal claim honest: the terms
*may* be too specific, because market supply and the active filters remain plausible explanations. Offer
exactly one action and stay read-only until the user accepts and confirms its usage impact. Several thin
sources share a single nudge.

Record the nudge only once it has actually been shown, in the bounded registry marker owned by
`internals.md`. While the saved search shape is unchanged, show no further query-health nudge — a dismissal
suppresses it exactly as an acceptance does. A confirmed query, location, limit, freshness, or source change
creates a new shape, which becomes assessable again after three new comparable runs of its own.

## A run never broadens itself

The headless runner is a literal executor: it issues exactly the configured query-source streams. A healthy
stream returning few rows or none is completed retrieval — not a failure, and not a trigger. Finish the
configured streams, record the truthful raw evidence in the run record, and leave any broader request to a
later user-approved retune. No automatic retry with different terms, no fallback query, no quietly raised
limit or deeper pagination.
