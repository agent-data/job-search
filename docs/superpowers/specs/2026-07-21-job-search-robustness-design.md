---
type: design-doc
title: "Robust intent preservation, delegated ownership, and verifiable job-search runs"
status: current
verified: partial
last_reviewed: 2026-07-21
code_refs: [ARCHITECTURE.md, TESTING.md, docs/design-docs/core-beliefs.md, docs-private/agent-agnostic-skills, docs-private/prompt-style-guide, shared/references/conventions.md, shared/references/internals.md, shared/references/parallelism.md, shared/references/query-strategy.md, shared/references/run-lifecycle.md, shared/scripts/mechanics/event-log-append.sh, skills/evaluate-job-fit/SKILL.md, skills/job-search/SKILL.md, skills/job-search/references/onboarding.md, skills/job-search-run/SKILL.md, scripts/eval_harness.py, tests/test_mechanics_scripts.py, tests/test_query_strategy_contract.py]
claimed_paths: [skills/job-search, skills/job-search-run, skills/evaluate-job-fit, shared/references, shared/scripts/mechanics, scripts, tests, docs/superpowers/reviews, ARCHITECTURE.md, TESTING.md]
owner_area: Skills & references
repos: [job-search-os]
---

# Robust intent preservation, delegated ownership, and verifiable job-search runs

This design responds to a failed first-run dogfood session on the
`feat/recall-oriented-query-strategy` branch. The user asked for roles at early-stage startups or small
companies specifically involving web scraping or web-based data systems. The session saved the generic
query `data platform engineer`, broadened the domain requirement to generic extraction, and presented
Rebar and Cogent as strong matches even though their postings did not establish the requested web-data
work. OnHires was the only one of the three that clearly fit the central domain requirement.

The session also bypassed the intended workflow. The front door called the job-data source, judged
postings, and wrote a digest and thin job rows itself rather than invoking `job-search-run` and applying
`evaluate-job-fit`. The rows omitted the canonical event type, verdict, reasoning, dealbreakers, and
unknowns. No authoritative run bundle or lifecycle ledger existed to support the digest.

The failure is not one missing sentence. It combines:

- **semantic shaping drift:** the user's domain intent did not survive preference compilation and query
  translation;
- **process-discipline failure:** the front door reproduced work exclusively owned by sibling skills; and
- **mechanical integrity failure:** malformed judgments and run artifacts could be written and surfaced.

The current tests did not expose this because they validate scenario structure, prompt contracts, and
isolated mechanics without running the complete first-run skill workflow. The prior private style audit
also accepted a 686-line, 7,772-word `job-search-run/SKILL.md` as indivisible and activation-critical. That
conclusion is rejected by this design: the skill has clear phase seams, the activation footprint dilutes
its critical gates, and directly linked phase references satisfy the one-hop rule without retaining the
monolith.

The design is approved. Implementation is pending. Until it lands, existing runtime contracts remain
authoritative; this document owns the approved delta.

## Goals

- Preserve each user must-have verbatim from `preferences.md` through search planning and fit judgment.
- Keep job relevance qualitative: postings need not repeat the user's words, and imperfect but plausibly
  relevant findings may remain moderate or weak.
- Prevent strong preferences such as startup stage or ownership from compensating for a role that does not
  plausibly address a must-have.
- Preserve recall by allowing justified broad proxy queries without treating their results as fit evidence.
- Make `job-search-run` the exclusive owner of posting calls and run artifacts, and
  `evaluate-job-fit` the exclusive owner of semantic posting judgments.
- Turn skipped instructions, stale configuration, malformed verdicts, and noncanonical artifacts into
  visible fail-closed states.
- Reduce `job-search-run/SKILL.md` from 7,772 words to a phase-oriented orchestration spine expected to
  land around 1,500–2,500 words, with 2,500 as the completion-blocking ceiling and no minimum, plus one-hop,
  just-in-time references.
- Replace false-green structural confidence with deterministic gates plus executed behavioral evidence.
- Require an independent post-implementation review against the complete private style-guide packs before
  completion can be claimed.

## Non-goals

- Requiring literal keyword matches between a posting and a must-have.
- Making relevance a deterministic scoring formula.
- Automatically rejecting every posting that omits one must-have.
- Banning broad queries such as `data platform engineer` in all contexts.
- Automatically broadening a configured query during a run.
- Building a host-level security boundary around an agent with unrestricted API and filesystem access.
- Redesigning unrelated scheduling, compensation, or source-health behavior except where contradictory
  prompt guidance must be corrected in touched surfaces.
- Splitting `job-search-run` into overlapping sibling skills solely to reduce its size.

## Design decision and alternatives

### Chosen: layered semantic contracts and fail-closed mechanics

Use concise positive guidance for semantic shaping, hard ownership boundaries for process discipline,
structured evidence for must-survive information, and portable validators for mechanically decidable
invariants. Exercise the complete workflow in release-gating behavioral evaluations.

This approach preserves model judgment while making omissions and bypasses observable. It follows the
private guidance's failure-class distinction: shaping failures receive recipes and required output slots;
discipline failures receive prohibitions paired with the correct alternative; deterministic integrity
rules move into scripts and schemas.

### Rejected: stronger prose only

Shortening prompts, adding contrastive examples, and strengthening warnings would improve salience but
would remain stochastic. The failed branch already contained many correct statements that the dogfood
agent skipped. More emphasis alone would not prevent malformed events, unsupported digests, or manual
workflow reproduction.

### Rejected: structured evidence without runtime gates

A search-plan receipt and per-posting evidence matrix would make semantic omissions visible, but the front
door could still skip them and write ad hoc artifacts. Structure must be paired with exclusive ownership,
preflight validation, and bundle authority.

## Product semantics

### Must-haves gate relevance; preferences rank relevant roles

A must-have is a qualitative relevance gate, not a lexical checkbox. The evaluator decides whether direct
or indirect posting evidence satisfies it. A posting can therefore meet a web-data requirement through
responsibilities such as operating distributed crawlers or acquiring public-web data even if the phrase
`web scraping` is absent.

Every must-have receives one assessment:

- `met`: the posting provides enough direct or defensible indirect evidence;
- `unclear`: the posting does not provide enough evidence to decide; or
- `conflicts`: the posting establishes work incompatible with the requirement.

`conflicts` on a must-have makes the posting not relevant. `unclear` normally keeps it out of the digest,
but the evaluator may feature it as moderate or weak when concrete evidence makes the role plausibly
aligned and the uncertainty is explained. A strong finding requires every must-have to be `met`. Strong
preferences influence the band only after relevance has been established.

This is an upper-bound contract, not a scoring rubric. Meeting every must-have permits but does not force a
strong verdict, and an evaluator may reject a posting whose overall evidence remains implausible even when
no single sentence explicitly conflicts.

### Translate for retrieval; preserve for judgment

Search vocabulary may be broader than the user's wording because job titles are inconsistent. Every query
must nevertheless map to an acceptable role lane and to the unchanged user criteria that make the lane
relevant.

Queries have two semantic types:

- `direct`: uses domain-specific role vocabulary likely to retrieve the lane; and
- `proxy`: uses broader title vocabulary to expose an otherwise hidden candidate pool.

A proxy query is allowed only when it adds a distinct plausible pool and records that rationale. It cannot
be the sole coverage for a lane with a protected domain requirement. Retrieval by a proxy is never evidence
that a returned posting fits. The evaluator always applies the complete brief.

## Ownership and prompt architecture

| Component | Exclusive responsibility | Forbidden shortcut |
|---|---|---|
| `job-search` | Setup, status, user-facing home, and invoking the runner | Calling posting-data routes, judging postings, or writing run-owned artifacts |
| `job-search-run` | Preflight, metered posting calls, orchestration, validated persistence, and run finalization | Reproducing the fit rubric or semantically rejecting a posting from a summary |
| `evaluate-job-fit` | Relevance, must-have assessments, match band, reasoning, and unknowns | Writing workspace state or changing retrieval configuration |
| Mechanics scripts | Schema, binding, append, and bundle consistency checks | Making semantic fit or query-quality judgments |

If the runner is unavailable, the front door stops and names the repair; it does not imitate the runner. If
the evaluator is unavailable, the runner stops semantic evaluation; it does not use an embedded mini-rubric.
Mechanical duplicate or malformed-record rejection remains in the runner and validators because it is not
a fit judgment.

### Thin runner

`skills/job-search-run/SKILL.md` becomes a compact orchestration spine, expected to land around
1,500–2,500 words, containing only:

- scope, modes, and exclusive ownership;
- a short phase-routing table;
- the gates before metered calls, persistence, and reporting;
- failure routing and honest terminal states; and
- a completion checklist and red flags.

The 2,500-word ceiling is countable and release-blocking; a complete shorter body is welcome. Exceeding the
ceiling requires revising this design and obtaining explicit approval; it cannot be waived in a style audit
merely by calling every line activation-critical.

Detailed material moves into focused references directly linked from the runner, so all load-bearing
resources remain one hop from `SKILL.md`. The runner tells the agent exactly which minimal reference set to
read at each phase. It must not require all references before the first operational action. Reference files
over roughly 100 lines receive an internal map, and very large files receive grep hints as required by the
private disclosure guidance.

This refactor removes duplication rather than relocating it. Query semantics, fit semantics, lifecycle,
accounting, delegated output, and error rendering each retain one canonical owner. A critical process rule
may be repeated only beside its governed action, in the completion checklist, and as a red flag paired with
the correct alternative.

The delegated evaluator contract also separates output modes before showing any schema:

- interactive invocation returns a human summary; and
- delegated invocation returns exactly one raw machine envelope with no preamble, fence, comments, or
  additional text.

Invalid delegated values are never semantically coerced. Harmless syntactic normalizations, if any, must be
enumerated exactly.

## Search-plan contract

Config v3 introduces immutable receipts under
`.job-search/search-plans/<plan_id>.json`. `preferences.md` remains the human-readable source of truth.

A receipt contains:

```json
{
  "schema_version": 1,
  "plan_id": "<immutable id>",
  "preferences_sha256": "<sha256>",
  "criteria": [
    {
      "criterion_id": "mh-001",
      "priority": "must_have",
      "source_quote": "<verbatim bullet from preferences.md>",
      "search_channels": ["keywords", "fit_judgment"],
      "direct_coverage_required": true
    }
  ],
  "lanes": [
    {
      "lane_id": "<id>",
      "description": "<acceptable role lane>",
      "criterion_ids": ["mh-001"]
    }
  ],
  "query_bindings": [
    {
      "query_id": "q-001",
      "request_sha256": "<hash of exact configured request>",
      "lane_ids": ["<id>"],
      "kind": "direct",
      "coverage_rationale": "<distinct candidate pool this request adds>"
    }
  ],
  "unresolved_assumptions": []
}
```

The active config stores stable query IDs and exact executable requests, plus the active `plan_id` and
preferences fingerprint. The receipt owns semantic rationale; config owns executable request values. A
request hash binds the two without maintaining a second prose copy of each query.

`search_channels` uses only `keywords`, `location`, and `fit_judgment`. The semantic plan review decides
whether a domain requirement needs direct query coverage; the mechanical validator enforces the resulting
boolean but does not pretend to derive it from arbitrary prose.

The plan validator verifies that:

- every current Must-haves bullet appears exactly once as a verbatim `source_quote`;
- every criterion ID and query ID is unique;
- every acceptable lane has coverage;
- every query binds to at least one lane and adds a stated coverage rationale;
- a protected domain lane has direct coverage and cannot rely only on proxies;
- config request hashes, plan ID, and preferences fingerprint match; and
- no model-authored `validated: true` field is trusted.

The validator can establish completeness and relationships, not whether a query is semantically wise. A
separate semantic review performs that judgment: use a cold-context reviewer when the host supports one and
an independent second pass otherwise. The fallback is labeled lower-confidence rather than equivalent.

## Evaluation contract

Every semantic verdict contains a complete evidence matrix in addition to the existing posting identity and
human reasoning:

```json
{
  "relevant": true,
  "match": "moderate",
  "must_have_assessments": [
    {
      "criterion_id": "mh-001",
      "assessment": "unclear",
      "evidence": ["<posting-specific fact>"],
      "explanation": "<why the fact supports this assessment>"
    }
  ],
  "why_still_plausible": "<required when relevant is true and a must-have is unclear>",
  "needs_human_check": true
}
```

The full envelope retains the existing source identity, posting URL, title, company, reasoning, and match
fields. `unknowns` and `dealbreakers_hit` are derived from the canonical assessments rather than authored as
independent facts that can drift.

The verdict validator enforces:

- every plan must-have appears exactly once;
- evidence and explanation are nonempty for every assessment;
- any `conflicts` assessment implies `relevant: false`;
- `strong` requires every assessment to be `met`;
- a relevant verdict with `unclear` requires `why_still_plausible`, `needs_human_check: true`, and a maximum
  band of `moderate`;
- a non-relevant verdict has no match band; and
- derived unknowns and dealbreakers agree with the assessment matrix.

The evaluator retains judgment over `met`, `unclear`, `conflicts`, relevance, and banding within these
consistency limits.

## Runtime flow

### Setup and activation

1. Build a draft plan from `preferences.md`, preserving every must-have verbatim.
2. Perform the semantic plan review.
3. Run deterministic plan validation.
4. Write the immutable receipt, read it back, and atomically bind config to it.
5. Invoke `job-search-run`; do not perform any runner-owned work in the front door.

### Runner phases

1. **Preflight:** validate schema versions, plan binding, preferences fingerprint, source prerequisites,
   and lifecycle writeability before a metered call.
2. **Retrieve:** execute only the frozen configured requests, preserving existing source-health,
   pagination, deduplication, and accounting semantics.
3. **Evaluate:** route every semantic posting judgment through `evaluate-job-fit`, using the complete brief
   and current plan criteria.
4. **Persist:** validate each envelope, append a complete typed event, and update lifecycle/accounting state.
5. **Finalize:** close the run, validate the authoritative bundle, and render a digest only from validated
   events.

Every evaluated event records `plan_id`, the preferences fingerprint, evaluator-contract version, complete
must-have assessments, and a canonical event type. The digest is a view over events and cannot introduce or
upgrade a verdict independently.

## Failure handling and artifact authority

- **Missing, stale, malformed, or unbound plan:** stop before metered calls and explain how to regenerate
  it.
- **Runner unavailable:** stop; no front-door manual fallback.
- **Evaluator unavailable:** stop semantic evaluation; no runner mini-rubric.
- **Malformed evaluator envelope:** request one schema-only re-emission from the retained result without
  another posting-data call.
- **Second malformed envelope:** record a terminal evaluation failure and persist no verdict.
- **Missing or unknown event type:** reject the append. `event-log-append.sh` must no longer accept an
  untyped row merely because it bypasses the `evaluated` branch.
- **Invalid event or write failure:** append no partial record and produce no success digest.
- **Partial source outage:** retain valid results under existing degraded-run semantics and disclose source
  health.
- **Unclosed or inconsistent bundle:** do not surface the digest as successful.

A workspace-level bundle validator establishes report authority by joining the closed lifecycle ledger,
run record, usage/accounting evidence, typed evaluated events, and digest metadata. The report is
authoritative only when those artifacts agree.

These controls defend against skipped references, compaction loss, stale instructions, premature writes,
and ordinary model drift. They are not an access-control boundary: preventing a deliberately noncompliant
agent from fabricating files or calling an exposed API requires host-level permissions outside this plugin.

## Testing and evidence

### Deterministic merge gates

- Missing, stale, malformed, and config-mismatched plans produce zero posting-data calls.
- Every Must-haves bullet is represented exactly once in the plan and every verdict.
- Strong verdicts with an unclear, conflicting, or missing must-have fail validation.
- Relevant uncertain verdicts without a concrete plausibility explanation fail validation.
- Missing and unknown event types, including the exact malformed dogfood row shape, fail atomically.
- A digest without a closed, internally consistent run bundle fails authority validation.
- Config migration and rollback preserve the previous valid workspace on failure.
- Reference pointers resolve one hop from each skill, canonical owners do not drift, and phase references are
  not instructed to load eagerly.
- `job-search-run/SKILL.md` remains at or below 2,500 words.

### Behavioral release gates

Run actual skills rather than only validating eval JSON structure. Required scenarios include:

1. The complete Rebar/Cogent/OnHires dogfood composite: OnHires is strong; Rebar and Cogent are never strong
   without web-data evidence; any featured uncertain role identifies the domain gap and explains why it is
   still plausibly relevant.
2. A thin posting where a central must-have is genuinely unclear: exclusion is valid; a moderate or weak
   inclusion is valid only with concrete plausibility evidence and a human-check flag.
3. A detailed posting centered on an adjacent non-web data domain: not relevant.
4. A broad proxy query that returns mostly adjacent platform roles: it survives only if the plan shows
   unique acceptable-lane coverage, and its returned roles receive independent fit judgments.
5. A shortcut-pressure first-run prompt inviting the front door to call the data source and write a quick
   digest directly: the workflow still delegates, and only canonical runner artifacts are produced.
6. A malformed evaluator response: one retained-result re-emission occurs, semantic coercion does not.
7. A compaction/resume path: the plan binding, must-have IDs, ownership boundaries, and open-run state
   survive through durable artifacts.

Run crown-jewel wording scenarios at least five times across release-intended model and host combinations.
Include no-guidance controls, report pass rates and variance, and preserve tool traces plus resulting
artifacts. Grade observable calls, ownership, and files rather than narrated claims. A meta-grade must reject
a plausible-looking digest that calls all three dogfood roles strong.

Deterministic tests are merge-gating. The executed cross-model behavioral matrix is release-gating; it may
be merge-gating where infrastructure supports reliable execution. A skipped model or unavailable host is
reported as skipped, never green. Static eval-harness success proves scenario coherence only and must never
be described as behavioral proof.

## Migration and rollout

This is a real config v3 migration because an unbound v2 workspace is no longer runnable.

1. New workspaces create and bind a search-plan receipt during setup.
2. Existing workspaces enter an interactive migration before their next run.
3. Migration drafts and previews the plan, validates it, writes it immutably, reads it back, and only then
   switches config atomically.
4. A failed migration leaves the prior workspace recoverable and performs no metered search.
5. Direct query or preference edits make the binding visibly stale and route to conversational repair.
6. A shadow-validation period may report would-block failures for existing workspaces, but mandatory
   enforcement and removal of the legacy bypass occur before release.

`ARCHITECTURE.md` must be reconciled with the current core belief that portable mechanics scripts may ship
with pinned prose fallbacks. Script and no-runtime fallback paths are tested separately and labeled
honestly.

## Post-implementation style-guide completion gate

Functional tests and behavioral evals do not by themselves establish prompt quality. The eventual
implementation plan must end with an independent post-implementation review against:

- every chapter and operational checklist in `docs-private/prompt-style-guide/`;
- every chapter, anti-pattern, checklist, and tension in
  `docs-private/agent-agnostic-skills/`;
- this approved design;
- the complete implementation diff; and
- the actual deterministic and behavioral evidence.

Use a cold-context, non-authoring reviewer where available. The controller supplies the commit range and
artifacts but may not rewrite or suppress reviewer findings. If only a same-agent review is possible, label
the evidence tier and do not represent it as independent.

Before review, record for every affected skill:

- entrypoint lines, words, and approximate tokens;
- the references named directly by the entrypoint;
- the minimal reference set loaded in each workflow phase;
- the amount loaded before the first operational action;
- duplicated canonical rules and their owners; and
- any budget exception requested by the implementation.

The review explicitly checks one-owner boundaries, one-hop progressive disclosure, instruction form by
failure class, exact machine output, orchestration/domain separation, contrastive examples, host-neutral
fallbacks, completion-pressure behavior, artifact authority, and whether verification claims exceed what
was executed.

Write the result to
`docs/superpowers/reviews/YYYY-MM-DD-job-search-robustness-style-audit.md`. It records the reviewed commit,
measurements, rule dispositions, P0/P1/P2 findings, evidence examined, residual risks, and approved
exceptions. The prior audit's size waiver is not inherited.

Any P0 or P1 finding blocks completion. A P2 is corrected or explicitly tracked with repository-specific
rationale. After repairs, rerun affected tests and behavioral scenarios, then obtain a second clean review.
Here, a clean review means no P0/P1 remains and every P2 is either repaired or explicitly tracked with an
owner and rationale. Only that clean review permits the implementation to be called complete.

## Completion criteria

Implementation is complete only when all of the following are true:

- the three exclusive ownership boundaries are enforced in prompts and observed in behavioral runs;
- search plans preserve every must-have and bind all active queries;
- fit envelopes carry complete evidence matrices and satisfy band invariants;
- malformed events and unsupported digests fail closed;
- the dogfood regression behaves as specified over repeated runs;
- deterministic gates and the release behavioral matrix are reported at their honest evidence tiers;
- `job-search-run/SKILL.md` is no more than 2,500 words and uses phase-local one-hop references;
- config v3 migration is recoverable and leaves no permissive legacy run path; and
- the post-implementation private-guide audit is clean after remediation.
