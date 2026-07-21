# Recall-Oriented Query Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make new and deliberately retuned job searches use the smallest nonredundant, coverage-complete portfolio of high-recall role queries, while proactively but conservatively suggesting broader terms when comparable saved runs are repeatedly and contextually thin.

**Architecture:** Keep query judgment single-homed in a new public `shared/references/query-strategy.md`. The interactive front door and operator manual load it directly; onboarding, home, customization, lifecycle, and runner files only apply their local part of the contract. Add normalized request evidence to every new run-record query stream, and store one bounded registry marker only after a query-health nudge is shown. The headless runner remains a literal executor and never broadens or retries with different terms.

**Tech Stack:** Markdown skills and shared references, JSON eval scenarios and plugin manifests, Python 3.9+ `pytest` contract tests, the stdlib-only fake `agent-data` and lifecycle fixtures, Bash build stamping, Git.

## Global Constraints

- Treat the approved design at `docs/superpowers/specs/2026-07-20-recall-oriented-query-strategy-design.md` and design commit `1e3dbe3` as the behavioral baseline.
- Apply coverage-based query derivation only to a newly created search or a user-approved retune. Do not rewrite an existing saved query merely because the home view opens.
- Derive query count from coverage closure. Never introduce a fixed query target or cap, including disguised wording such as “usually two or three.”
- Keep retrieval broad enough to expose plausible candidates; keep stage, founder access, ownership, culture, compensation, coding-agent use, and similar fit criteria in the Job Preferences Brief unless a term is itself common posting vocabulary that opens a distinct role lane.
- Do not add a config schema version. The new fields are run-audit and registry state only.
- Do not add automatic broadening, fallback searches, source-specific keyword recipes, higher default limits, or deeper pagination.
- Preserve calls-first usage context and existing scoped confirmation before any persistent retrieval increase.
- Keep the query strategy in one public shared file. Both consumers must point directly to `../../shared/references/query-strategy.md`; do not create `skills/*/references/query-strategy.md` copies or reference-to-reference links.
- Keep the build stamp-only. Do not restore fan-out logic in `scripts/build.sh`.
- Write tests against marked contracts, records, call logs, files, and configuration effects—not exact model narration.
- Run every Python test command with `-p no:cacheprovider` when the repository is mounted read-only to pytest's cache.
- Preserve unrelated work. Before every commit, run `git status --short` and stage only the files named by that task.

## File Map

| File | Planned responsibility |
|---|---|
| `shared/references/query-strategy.md` | Canonical portfolio, contextual-thinness, repeated-thin, decision, and nudge guidance |
| `skills/job-search/SKILL.md` | Direct conditional load trigger for setup, retune, and home query-health work |
| `skills/job-search-agent/SKILL.md` | Direct conditional load trigger for query configuration and troubleshooting |
| `skills/job-search/references/onboarding.md` | Coverage map during new setup/retune; first-run contextual review |
| `skills/job-search/references/home.md` | Read three comparable runs, assess thinness, suppress/reconcile one proactive nudge |
| `skills/job-search-agent/references/customization.md` | Source-neutral broadening advice and intentional-narrowing branch |
| `skills/job-search-run/SKILL.md` | Freeze and record normalized request evidence; execute low-volume streams literally |
| `shared/references/conventions.md` | New-run query-stream request fields and compatibility rules |
| `shared/references/internals.md` | Bounded `query_health_nudge` registry marker and write ownership |
| `shared/references/run-lifecycle.md` | Replace unconditional zero-relevant broadening with query-health routing |
| `tests/test_query_strategy_contract.py` | Marked-table, one-hop, scope, record-field, marker, and no-fallback contracts |
| `tests/fake-agent-data` | Deterministic keyword-sensitive `search-jobs` scenario |
| `tests/fixtures/query-sensitive/search-jobs.empty.json` | Healthy empty response for phrase-stuffed terms |
| `tests/test_fake_agent_data.py` | Same-source proof that broad role families recover rows |
| `tests/fake-run-lifecycle` | Emit and strictly validate the five new query-stream fields |
| `tests/test_run_lifecycle_pressure.py` | Positive and fail-closed compatibility tests for request evidence |
| `skills/job-search/evals/evals.json` | First-run, multi-lane, redundancy, and proactive-nudge behavioral scenarios |
| `skills/job-search-agent/evals/evals.json` | Thin-versus-healthy troubleshooting behavioral scenario |
| `skills/job-search-run/evals/evals.json` | Request evidence and no-automatic-broadening runner scenario |
| `TESTING.md` | Deterministic lanes and separately authorized live ATS contract smoke |
| `docs/superpowers/reviews/2026-07-21-recall-oriented-query-strategy-style-audit.md` | Complete PSG/AAS checklist, anti-pattern, and tension dispositions for the final diff |
| Six version manifests | Synchronized patch release `0.6.1` |
| `shared/references/build-stamp.md` | Regenerated deterministic runtime hash |

---

### Task 1: Pin the canonical strategy and one-hop wiring

**Files:**

- Create: `tests/test_query_strategy_contract.py`
- Create: `shared/references/query-strategy.md`
- Modify: `skills/job-search/SKILL.md`
- Modify: `skills/job-search-agent/SKILL.md`
- Test: `tests/test_reference_resolution.py`

- [ ] **Step 1: Write the failing single-home and marked-contract tests**

Create `tests/test_query_strategy_contract.py` with a Markdown-table parser and these first tests:

```python
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
STRATEGY = ROOT / "shared" / "references" / "query-strategy.md"
FRONT_DOOR = ROOT / "skills" / "job-search" / "SKILL.md"
OPERATOR = ROOT / "skills" / "job-search-agent" / "SKILL.md"


def marked_table(path, marker):
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- query-strategy-contract:{re.escape(marker)} -->\n(.*?)\n"
        rf"<!-- /query-strategy-contract:{re.escape(marker)} -->",
        text,
        re.DOTALL,
    )
    assert match, f"missing query-strategy-contract:{marker} in {path}"
    rows = {}
    for line in match.group(1).splitlines():
        if not line.startswith("|") or line.startswith("|---") or "Field" in line:
            continue
        cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        rows[cells[0]] = cells[1]
    return rows


def test_query_strategy_is_single_homed_and_loaded_directly():
    assert STRATEGY.is_file()
    pointer = "../../shared/references/query-strategy.md"
    assert pointer in FRONT_DOOR.read_text(encoding="utf-8")
    assert pointer in OPERATOR.read_text(encoding="utf-8")
    assert not (ROOT / "skills" / "job-search" / "references" / "query-strategy.md").exists()
    assert not (ROOT / "skills" / "job-search-agent" / "references" / "query-strategy.md").exists()


def test_portfolio_contract_has_coverage_closure_not_a_count_quota():
    assert marked_table(STRATEGY, "portfolio") == {
        "scope": "new_search_or_user_approved_retune",
        "coverage_unit": "materially_distinct_acceptable_role_lane",
        "query_vocabulary": "real_posting_title_or_description_terms",
        "add_query_when": "materially_different_lane_or_posting_vocabulary",
        "merge_or_remove_when": "no_unique_lane_or_vocabulary_coverage",
        "stop_when": "every_lane_covered_and_next_query_adds_no_meaningful_coverage",
        "query_count": "derived_no_universal_target_or_cap",
        "precision_owner": "job_preferences_brief_and_fit_judgment",
    }
```

- [ ] **Step 2: Run the tests and confirm RED for the missing canonical strategy**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_query_strategy_contract.py tests/test_reference_resolution.py
```

Expected: `test_query_strategy_is_single_homed_and_loaded_directly` and `test_portfolio_contract_has_coverage_closure_not_a_count_quota` fail because the new shared reference and pointers do not exist. Existing reference-resolution tests remain green.

- [ ] **Step 3: Add the canonical strategy reference**

Write `shared/references/query-strategy.md` in this order:

1. A self-locating opening sentence: this reference governs query derivation, contextual retrieval-health assessment, and user-approved broadening.
2. The concise rule: “Queries maximize plausible recall; the Job Preferences Brief supplies precision.”
3. The marked `portfolio` table with the exact values asserted above.
4. One schematic contrast: phrase-stuffed mini-brief versus complementary role-family queries. Mark it illustrative and explain that the broad queries expose candidates for later fit judgment.
5. The contextual assessment recipe: compare raw volume with role commonness, posting vocabulary, location, freshness, healthy-source evidence, and fit-rejection evidence.
6. The query-health decision table from the design: unhealthy/incomplete; contextually thin; healthy but irrelevant; intentionally noisy; healthy but already known.
7. The repeated-thin signal and `Q` threshold.
8. The one-nudge, one-question behavior and suppression rule.
9. The executor alternative: finish the configured streams, record truthful evidence, never broaden during a run.

Keep this file at or below 150 lines. Do not include host-specific tool names, provider-specific query advice, or a rendered user response.

- [ ] **Step 4: Add direct conditional load triggers in both parent skills**

In `skills/job-search/SKILL.md`, add one direct pointer near Step 0 that says to read `../../shared/references/query-strategy.md` when deriving or retuning queries, reviewing first-run retrieval volume, or assessing saved-search query health.

In `skills/job-search-agent/SKILL.md`, add one direct pointer near its routing/reference block that says to read the same path when creating, retuning, explaining, or troubleshooting retrieval queries or thin results.

Do not add pointers from onboarding, home, customization, lifecycle, or another shared reference.

- [ ] **Step 5: Run focused tests and inspect the reference graph**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_query_strategy_contract.py tests/test_reference_resolution.py
rg -n "query-strategy.md" skills shared/references --glob '*.md'
```

Expected: tests pass. `rg` shows one canonical file plus exactly two direct `SKILL.md` pointers and no skill-local copy.

- [ ] **Step 6: Commit the canonical strategy**

```bash
git add tests/test_query_strategy_contract.py shared/references/query-strategy.md skills/job-search/SKILL.md skills/job-search-agent/SKILL.md
git commit -m "feat(job-search): add recall-oriented query strategy"
```

---

### Task 2: Replace fixed-count onboarding with coverage closure

**Files:**

- Modify: `tests/test_query_strategy_contract.py`
- Modify: `skills/job-search/references/onboarding.md`
- Modify: `skills/job-search/evals/evals.json`

- [ ] **Step 1: Add a failing onboarding application contract**

Extend `tests/test_query_strategy_contract.py`:

```python
ONBOARDING = ROOT / "skills" / "job-search" / "references" / "onboarding.md"


def test_onboarding_applies_coverage_closure_at_one_existing_checkpoint():
    assert marked_table(ONBOARDING, "onboarding-application") == {
        "trigger": "new_search_or_user_approved_retune",
        "input": "job_preferences_brief",
        "artifact": "lane_to_query_coverage_map",
        "result": "smallest_nonredundant_coverage_complete_portfolio",
        "fixed_query_count": "prohibited",
        "checkpoint": "existing_brief_and_search_interpretation_checkpoint",
        "first_live_review": "contextual_raw_retrieval_assessment",
    }
```

- [ ] **Step 2: Run the new test and confirm RED**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_query_strategy_contract.py::test_onboarding_applies_coverage_closure_at_one_existing_checkpoint
```

Expected: failure for missing `query-strategy-contract:onboarding-application`.

- [ ] **Step 3: Rewrite onboarding's Search section and checklist**

In `skills/job-search/references/onboarding.md`:

- Replace “Derive 2–3 queries” and the matching checklist item with the marked application table.
- Instruct the agent to enumerate materially distinct acceptable lanes, map each lane to likely posting vocabulary, merge redundant aliases, and stop at coverage closure.
- Render the lane-to-query coverage map in the existing confidence checkpoint; do not add a second confirmation gate.
- Keep `remote` in `queries[].location` when the source contract can express it. Do not automatically append “remote” to every keyword phrase.
- After the first live run, assess raw retrieval contextually. A surprisingly thin result can prompt a proposed retune; a healthy empty or low-volume stream is not retried automatically.
- Preserve the exact calls-first baseline formula `enabled queries × enabled sources`. Do not preserve a hard-coded assumption that every brief creates two queries.

Update job-search eval case 1 so its persona still naturally produces an `AI engineer` query, but its prompt and expectations no longer instruct the model to derive exactly two queries. Assert that the usage line reports the exact observed `Q × 2` baseline before metered calls. Keep the existing approved four-call wording test elsewhere unchanged; it remains valid for a specific two-query fixture, not as a universal derivation rule.

- [ ] **Step 4: Scan for contradictory fixed-count guidance**

Run:

```bash
rg -n "Derive 2.?3|2.?3 queries|two or three queries|exactly two enabled queries" skills/job-search skills/job-search-agent shared/references
```

Expected: no query-derivation instruction anchors the agent to two or three. Any historical sentence outside runtime guidance must be labeled as historical rather than prescriptive.

- [ ] **Step 5: Run focused contracts and eval-schema validation**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_query_strategy_contract.py tests/test_usage_context_contract.py tests/test_eval_harness.py
python3 scripts/eval_harness.py --root .
```

Expected: all focused tests pass; eval harness reports every eval file structurally valid.

- [ ] **Step 6: Commit onboarding coverage closure**

```bash
git add tests/test_query_strategy_contract.py skills/job-search/references/onboarding.md skills/job-search/evals/evals.json
git commit -m "feat(job-search): derive coverage-complete query portfolios"
```

---

### Task 3: Add a deterministic keyword-sensitive source fixture

**Files:**

- Modify: `tests/test_fake_agent_data.py`
- Modify: `tests/fake-agent-data`
- Create: `tests/fixtures/query-sensitive/search-jobs.empty.json`

- [ ] **Step 1: Write the failing same-source sensitivity test**

Add to `tests/test_fake_agent_data.py`:

```python
def test_query_sensitive_ashby_returns_rows_for_role_families_not_phrase_stuffing():
    common = ["call", LISTING, "search-jobs", "--source", "ashby",
              "--location", "United States", "--limit", "25",
              "--published_on_or_after", "2026-06-01"]
    narrow = shim([*common, "--keywords",
                   "founding AI product engineer seed Series C developer tools coding agents"],
                  scenario="query-sensitive")
    product = shim([*common, "--keywords", "product engineer"],
                   scenario="query-sensitive")
    ai = shim([*common, "--keywords", "AI engineer"],
              scenario="query-sensitive")

    assert narrow.returncode == product.returncode == ai.returncode == 0
    assert json.loads(narrow.stdout)["data"]["results"] == []
    assert len(json.loads(product.stdout)["data"]["results"]) >= 1
    assert len(json.loads(ai.stdout)["data"]["results"]) >= 1
```

- [ ] **Step 2: Run the test and confirm it fails because all keywords currently share one fixture**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_fake_agent_data.py::test_query_sensitive_ashby_returns_rows_for_role_families_not_phrase_stuffing
```

Expected: the narrow call returns the happy Ashby row, so the empty-result assertion fails.

- [ ] **Step 3: Implement the query-sensitive branch**

In `tests/fake-agent-data`, after source validation and before ordinary fixture selection:

```python
            if SCEN == "query-sensitive":
                keywords = (flag(argv, "--keywords") or "").strip().casefold()
                if keywords not in {"product engineer", "ai engineer"}:
                    fx = fixture("search-jobs.empty.json")
                else:
                    names = [f"search-jobs.{src}.json"] if src != "linkedin" else ["search-jobs.json"]
                    fx = fixture("search-jobs.json", names=names)
            elif SCEN.startswith("pagination"):
                # retain the existing pagination body unchanged
```

Use this exact empty response shape in `tests/fixtures/query-sensitive/search-jobs.empty.json`:

```json
{
  "data": {
    "query": {},
    "results": []
  }
}
```

Keep the existing source echo and recency filtering after fixture selection so the narrow and broad arms differ only in keywords.

- [ ] **Step 4: Run the entire fake-service suite**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_fake_agent_data.py
```

Expected: all fake-service tests pass, including pagination, source echo, recency, and query sensitivity.

- [ ] **Step 5: Commit the deterministic fixture**

```bash
git add tests/fake-agent-data tests/test_fake_agent_data.py tests/fixtures/query-sensitive/search-jobs.empty.json
git commit -m "test(job-search): add keyword-sensitive source fixture"
```

---

### Task 4: Record comparable saved-request evidence on every stream

**Files:**

- Modify: `tests/test_query_strategy_contract.py`
- Modify: `tests/test_run_lifecycle_pressure.py`
- Modify: `tests/fake-run-lifecycle`
- Modify: `shared/references/conventions.md`
- Modify: `skills/job-search-run/SKILL.md`

- [ ] **Step 1: Add failing schema and lifecycle assertions**

Extend `tests/test_query_strategy_contract.py` with the exact canonical field contract:

```python
CONVENTIONS = ROOT / "shared" / "references" / "conventions.md"


def test_new_run_streams_record_comparable_request_evidence():
    assert marked_table(CONVENTIONS, "run-stream-request-fields") == {
        "request_origin": "required_saved_or_one_off",
        "location": "required_normalized_string_or_null",
        "limit": "required_integer_1_through_100",
        "freshness": "required_saved_selector_or_null_for_one_off",
        "published_on_or_after": "required_iso_date_or_null",
        "legacy_missing_fields": "readable_but_query_health_ineligible",
    }
```

In `test_lifecycle_fixture_happy_paths_close_only_after_valid_artifacts`, assert every emitted query contains:

```python
    for query in record["queries"]:
        assert query["request_origin"] == "saved"
        assert query["location"] is None
        assert query["limit"] == 25
        assert query["freshness"] == "past-2-weeks"
        assert query["published_on_or_after"] == "2026-07-03"
```

Add a validator test that removes each new key in turn and expects `validate_run_record` to return `False` for a new record. Also assert that the prose compatibility contract classifies an older record missing all five fields as readable but ineligible for query-health comparison; do not loosen the strict new-record fixture validator.

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_query_strategy_contract.py::test_new_run_streams_record_comparable_request_evidence tests/test_run_lifecycle_pressure.py::test_lifecycle_fixture_happy_paths_close_only_after_valid_artifacts
```

Expected: missing marked table and missing query keys fail.

- [ ] **Step 3: Add the canonical run-record contract**

In `shared/references/conventions.md`:

- Add the five fields to the `queries[]` JSON example immediately after `keywords`.
- Add a marked `run-stream-request-fields` table with the exact values above.
- Define `request_origin`, normalized `location`, exact resolved `limit`, saved freshness selector, and effective cutoff.
- State that rolling cutoff dates are audit evidence but comparability uses the saved selector.
- State that only `request_origin: saved` contributes to repeated-thin assessment.
- Preserve older records for existing reads, but make them query-health-ineligible when any of the five fields is absent.

- [ ] **Step 4: Freeze and write the evidence in the runner**

In `skills/job-search-run/SKILL.md`, extend each immutable query-source stream before its first call:

```json
{
  "request_origin": "saved|one_off",
  "location": null,
  "limit": 25,
  "freshness": "past-2-weeks",
  "published_on_or_after": "2026-07-03"
}
```

Label this object schematic. In prose, bind the actual values once and replay them unchanged on continuations. For one-off requests, write `freshness: null` even when the one-off resolves an effective cutoff. A healthy low-volume response completes normally; do not issue a second search with altered keywords.

- [ ] **Step 5: Update the lifecycle fixture's producer and strict validator**

In `tests/fake-run-lifecycle`, add these exact fixture values to every generated query:

```python
"request_origin": "saved",
"location": None,
"limit": 25,
"freshness": "past-2-weeks",
"published_on_or_after": "2026-07-03",
```

Add the keys to `query_keys` and validate:

- origin is `saved` or `one_off`;
- location is `None` or a nonempty string;
- limit is an integer from 1 through 100 and not a boolean;
- freshness is `any`, `past-week`, `past-2-weeks`, or `past-month` for saved, and `None` for one-off;
- cutoff is `None` or `YYYY-MM-DD`.

- [ ] **Step 6: Run schema, lifecycle, and existing continuation tests**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_query_strategy_contract.py tests/test_run_lifecycle_pressure.py tests/test_fake_agent_data.py
```

Expected: all tests pass. Existing immutable continuation request tests remain green.

- [ ] **Step 7: Commit request evidence**

```bash
git add tests/test_query_strategy_contract.py tests/test_run_lifecycle_pressure.py tests/fake-run-lifecycle shared/references/conventions.md skills/job-search-run/SKILL.md
git commit -m "feat(job-search): record comparable search request evidence"
```

---

### Task 5: Add the bounded proactive query-health nudge

**Files:**

- Modify: `tests/test_query_strategy_contract.py`
- Modify: `shared/references/internals.md`
- Modify: `skills/job-search/references/home.md`

- [ ] **Step 1: Add failing marker and eligibility contract tests**

Extend `tests/test_query_strategy_contract.py`:

```python
INTERNALS = ROOT / "shared" / "references" / "internals.md"
HOME = ROOT / "skills" / "job-search" / "references" / "home.md"


def test_query_health_marker_is_bounded_explicit_and_written_only_after_showing():
    assert marked_table(INTERNALS, "registry-marker") == {
        "registry_key": "query_health_nudge",
        "cardinality": "one_marker_overwritten_by_new_qualifying_shape",
        "search_shape": "enabled_queries_sources_and_saved_freshness",
        "shape_query_fields": "id_keywords_location_limit",
        "evidence_role": "suppression_index_not_nudge_authority",
        "write_when": "after_user_facing_nudge_is_shown",
        "outcome": "shown_or_accepted_or_dismissed",
        "unknown_registry_keys": "preserved",
    }


def test_repeated_thin_signal_is_a_contextual_assessment_trigger():
    assert marked_table(STRATEGY, "repeated-thin") == {
        "window": "three_newest_comparable_authoritative_runs",
        "run_state": "closed_complete_non_canary",
        "stream_state": "every_enabled_stream_for_source_successful",
        "request_origin": "saved_only",
        "shape": "queries_sources_locations_limits_and_freshness_unchanged",
        "threshold": "source_total_results_returned_less_than_enabled_query_count_each_run",
        "effect": "contextual_assessment_not_automatic_nudge",
    }
```

- [ ] **Step 2: Run the tests and confirm RED**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_query_strategy_contract.py::test_query_health_marker_is_bounded_explicit_and_written_only_after_showing tests/test_query_strategy_contract.py::test_repeated_thin_signal_is_a_contextual_assessment_trigger
```

Expected: both marked contracts are absent.

- [ ] **Step 3: Add the canonical registry marker**

In `shared/references/internals.md`, add the marked table plus this exact schema near `deeper_coverage_nudges`:

```json
"query_health_nudge": {
  "search_shape": {
    "queries": [
      {"id": "ai-eng", "keywords": "AI engineer", "location": null, "limit": 25}
    ],
    "sources": ["ashby"],
    "freshness": "past-2-weeks"
  },
  "shown_at": "2026-07-21T12:00:00Z",
  "affected_sources": ["ashby"],
  "outcome": "shown"
}
```

Label values schematic. State that the front door owns writes, merges with the current registry, preserves unknown keys, writes atomically, and writes only after rendering the nudge. Reads must revalidate authoritative runs; the marker cannot prove thinness.

- [ ] **Step 4: Add the repeated-thin table to the strategy**

Add the marked `repeated-thin` table with the exact values asserted above. Keep the surrounding explanation concise and avoid restating registry mechanics.

- [ ] **Step 5: Apply the assessment in the returning home**

In `skills/job-search/references/home.md`:

- Gather the newest three comparable lifecycle-authoritative records only when they exist.
- Compare successful per-source stream totals using raw `results_returned`; never use `new`, deduped, selected, detail-read, or relevant counts to activate the signal.
- Require current-format request fields, `request_origin: saved`, identical saved search shape, complete non-canary records, and every enabled stream successful.
- For `Q` enabled queries, treat totals `0..Q-1` as candidates and `Q+` as non-candidates.
- Apply contextual judgment before showing anything. Rare roles, tight location, or plausible market scarcity may justify silence.
- Combine all qualifying sources into one evidence sentence or one evidence bullet, followed by one question asking whether to propose broader role families. Use causal uncertainty (`may`).
- Read the marker and suppress the nudge while the normalized shape is unchanged.
- Keep assessment local and unmetered. If the user accepts, route the proposed retune through the existing usage preview and persistent-change confirmation before writing config.
- Record the marker only after the nudge is actually shown; update its outcome only after the corresponding interaction.

- [ ] **Step 6: Run focused home, registry, and contract tests**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_query_strategy_contract.py tests/test_usage_context_contract.py tests/test_schedule_health.py tests/test_scheduling_eligibility.py
```

Expected: all tests pass; no scheduling or deeper-coverage marker behavior regresses.

- [ ] **Step 7: Commit the proactive nudge**

```bash
git add tests/test_query_strategy_contract.py shared/references/query-strategy.md shared/references/internals.md skills/job-search/references/home.md
git commit -m "feat(job-search): add contextual thin-result nudge"
```

---

### Task 6: Reconcile every query-health troubleshooting branch

**Files:**

- Modify: `tests/test_query_strategy_contract.py`
- Modify: `skills/job-search-agent/references/customization.md`
- Modify: `shared/references/run-lifecycle.md`
- Modify: `skills/job-search/references/onboarding.md`
- Modify: `skills/job-search/references/home.md`
- Modify: `skills/job-search-agent/SKILL.md`
- Modify: `skills/job-search-run/SKILL.md`

- [ ] **Step 1: Add a failing decision-contract test**

Add a `decision-table` marked table to the expected canonical strategy contract and test these exact rows:

```python
def test_query_health_decisions_distinguish_retrieval_from_fit():
    assert marked_table(STRATEGY, "decision-table") == {
        "failed_blocked_or_incomplete": "operational_recovery_then_wait_for_healthy_evidence",
        "contextually_or_repeatedly_thin": "propose_broader_complementary_role_families",
        "healthy_raw_but_zero_relevant": "inspect_rejections_then_replace_lane_or_clarify_brief",
        "healthy_noisy_and_user_wants_less": "intentional_narrowing",
        "healthy_but_all_known": "report_seen_results_and_leave_breadth_unchanged",
    }
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_query_strategy_contract.py::test_query_health_decisions_distinguish_retrieval_from_fit
```

Expected: missing marked `decision-table` contract.

- [ ] **Step 3: Mark the canonical strategy decision table**

Convert the approved five-row decision table in `shared/references/query-strategy.md` into the marked contract above. Preserve user-facing explanations outside the machine-readable values.

- [ ] **Step 4: Remove contradictory unconditional broadening**

Update all four application surfaces:

- `customization.md`: say “If results are thin, consider broadening search queries,” then route through contextual assessment. Preserve narrower keywords, location, lower limit, or disabling only when the user explicitly wants fewer results from a healthy noisy lane.
- `run-lifecycle.md`: zero relevant is a truthful completed outcome. Route interactive adjustment to query-health assessment; do not prescribe broadening solely from relevance count.
- `onboarding.md` and `home.md`: replace any zero-result or zero-relevant shortcut with the canonical branch distinction.
- `job-search-agent/SKILL.md`: add a compact quick-reference row for query health and the bounded marker, without duplicating the strategy recipe.
- `job-search-run/SKILL.md`: state that source success with zero or few rows is a successful stream; finalization records it and never alters the request.

- [ ] **Step 5: Scan all runtime guidance for conflicting copies**

Run:

```bash
rg -n -i "zero relevant|0 relevant|zero results|0 results|broaden|tighten keywords|thin results|thin retrieval" skills shared/references
```

Expected: every hit is either the canonical strategy, an application pointer to contextual assessment, an intentional-narrowing branch, or a historical/non-runtime fixture. No hit says zero relevance alone proves terms are too narrow.

- [ ] **Step 6: Run the focused policy suites**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_query_strategy_contract.py tests/test_usage_context_contract.py tests/test_run_lifecycle_pressure.py tests/test_philosophy_guard.py
```

Expected: all tests pass.

- [ ] **Step 7: Commit troubleshooting reconciliation**

```bash
git add tests/test_query_strategy_contract.py shared/references/query-strategy.md shared/references/run-lifecycle.md skills/job-search/references/onboarding.md skills/job-search/references/home.md skills/job-search-agent/references/customization.md skills/job-search-agent/SKILL.md skills/job-search-run/SKILL.md
git commit -m "fix(job-search): separate retrieval health from fit quality"
```

---

### Task 7: Add behavioral eval coverage and the live-contract residual

**Files:**

- Modify: `skills/job-search/evals/evals.json`
- Modify: `skills/job-search-agent/evals/evals.json`
- Modify: `skills/job-search-run/evals/evals.json`
- Modify: `TESTING.md`

- [ ] **Step 1: Add job-search eval cases 54–57**

Append contiguous cases:

- **54, phrase-sensitive first run:** use `JOBSEARCH_TEST_SCENARIO=query-sensitive` and the early-product-engineer AI-startup brief. Assert the persisted coverage map contains broad complementary role-family terms, the Ashby call log has at least `product engineer` and `AI engineer`, the phrase-stuffed mini-brief is not sent, and returned rows reach fit judgment. Set `stochastic: true`, `reps: 5`, and a `no-guidance` control that withholds only query-strategy guidance.
- **55, mutually exclusive careers:** use PE investing, L/S equity investing, equity research, and corporate development. Assert every acceptable lane maps to retrieval coverage; the agent does not compress all four into two or three queries. Use five reps and a no-guidance control.
- **56, redundant aliases:** give several aliases that retrieve the same product-engineering pool. Assert the coverage artifact merges redundant aliases while retaining a distinct AI-engineering vocabulary lane. Use five reps and a no-guidance control.
- **57, repeated thin saved shape:** seed three complete comparable saved-origin runs below `Q`, plus unchanged marker state. Assert contextual assessment occurs, one combined nudge is shown at most once, no config/API write occurs before acceptance, and a rare-role control can remain silent. Use five reps and a no-guidance control.

Every expectation must name observable artifacts: `config.yaml`, call-log keywords, run fields, registry bytes, and number of prompts—not exact prose.

- [ ] **Step 2: Add job-search-agent eval case 46**

Use three arms:

1. healthy source + thin raw retrieval;
2. healthy raw retrieval + zero relevant after fit judgment;
3. failed/incomplete source.

Assert only arm 1 proposes broader role families, arm 2 inspects rejection reasons and offers a targeted lane/brief repair, and arm 3 routes to operational recovery. Use `stochastic: true`, `reps: 5`, and a no-guidance control.

- [ ] **Step 3: Add job-search-run eval case 72**

Use the query-sensitive fixture with a saved narrow phrase. Assert the runner:

- executes exactly the authorized phrase once per enabled source;
- writes all five request fields;
- records a healthy zero-row stream;
- does not call `product engineer` or `AI engineer` as fallback;
- does not mutate config or registry.

Mark it `coverage_kind: executable_fixture` and keep it deterministic.

- [ ] **Step 4: Add a separately authorized live ATS smoke to TESTING.md**

Document a non-merge-gating test that, after explicit approval for billable/network calls, sends the same location, limit, freshness, and Ashby source with:

1. the phrase-stuffed query;
2. `product engineer`;
3. `AI engineer`.

Record request parameters, response counts, effective date fields, and the observation date. Grade contract shape and relative retrieval only; do not require a stable absolute count. Label a skipped live smoke as `SKIPPED — authorization or network unavailable`, never as passed.

- [ ] **Step 5: Validate eval structure and focused test lanes**

Run:

```bash
python3 scripts/eval_harness.py --root .
python3 -m pytest -q -p no:cacheprovider tests/test_eval_harness.py tests/test_fake_agent_data.py tests/test_query_strategy_contract.py
```

Expected: contiguous IDs, all stochastic cases have `reps >= 5` and a no-guidance control, and all deterministic suites pass.

- [ ] **Step 6: Commit behavioral coverage**

```bash
git add skills/job-search/evals/evals.json skills/job-search-agent/evals/evals.json skills/job-search-run/evals/evals.json TESTING.md
git commit -m "test(job-search): cover recall and query-health behavior"
```

---

### Task 8: Complete the full private style-guide audit

**Files:**

- Create: `docs/superpowers/reviews/2026-07-21-recall-oriented-query-strategy-style-audit.md`
- Modify as findings require: every runtime or test file changed in Tasks 1–7

- [ ] **Step 1: Read the complete guide set against the implementation diff**

Read every Markdown file in these two directories, not only the checklist indexes:

```bash
find docs-private/prompt-style-guide docs-private/agent-agnostic-skills -maxdepth 1 -type f -name '*.md' -print | sort
git diff --stat 1e3dbe3...HEAD
git diff --check 1e3dbe3...HEAD
```

Use the resulting list to read all files completely. Re-read these four indexes last so their counts and current IDs govern the audit:

- `docs-private/prompt-style-guide/09-checklist-and-rule-index.md`
- `docs-private/agent-agnostic-skills/13-anti-patterns.md`
- `docs-private/agent-agnostic-skills/14-checklist-and-rule-index.md`
- `docs-private/agent-agnostic-skills/16-tension-register.md`

- [ ] **Step 2: Write the complete audit artifact**

Create `docs/superpowers/reviews/2026-07-21-recall-oriented-query-strategy-style-audit.md` with:

- scope and exact implementation commit range beginning at `1e3dbe3`;
- 18 PSG checklist rows, each `Pass` or `N/A — untouched surface and reason`;
- 14 AAS checklist rows with the same disposition rule;
- all 13 PSG anti-patterns and all 42 AAS anti-patterns, each checked against the diff;
- all 10 AAS tensions, with T-01, T-02, T-06, T-08, and T-10 explicitly resolved and the rest justified as untouched when applicable;
- all cited rule IDs verified against the current indexes;
- one final blocking-defects line and one SHOULD/CONSIDER deviations line.

A failed MUST-backed row blocks the release task. A SHOULD/CONSIDER deviation requires a repository-specific technical justification; inconvenience is not a justification.

- [ ] **Step 3: Repair every audit finding before recording a pass**

Pay special attention to:

- one canonical home and direct one-hop pointers;
- positive portfolio recipe with observable stop condition;
- no nuance-clause repair layered over contradictory zero-relevant guidance;
- no emphasis wall or fully rendered user narration;
- schematic, annotated examples only;
- observable-effect tests rather than prose matching;
- no private-guide name or path in shipped skill/reference content;
- no host-specific tool names in shared guidance;
- no automatic expensive action or persistent write before scoped confirmation;
- honest separation of structural, shim, stochastic off-CI, and live-contract evidence.

- [ ] **Step 4: Run document, philosophy, and reference gates**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider tests/test_doc_lint.py tests/test_doc_lint_intra_reference.py tests/test_philosophy_guard.py tests/test_reference_resolution.py tests/test_query_strategy_contract.py
rg -n "docs-private|prompt-style-guide|agent-agnostic-skills" skills shared/references
```

Expected: all tests pass; `rg` returns no shipped runtime references to private authoring doctrine.

- [ ] **Step 5: Commit the audit and any required wording repairs**

```bash
git add docs/superpowers/reviews/2026-07-21-recall-oriented-query-strategy-style-audit.md shared/references/query-strategy.md shared/references/conventions.md shared/references/internals.md shared/references/run-lifecycle.md skills/job-search/SKILL.md skills/job-search/references/onboarding.md skills/job-search/references/home.md skills/job-search-agent/SKILL.md skills/job-search-agent/references/customization.md skills/job-search-run/SKILL.md tests/test_query_strategy_contract.py tests/test_fake_agent_data.py tests/fake-agent-data tests/test_run_lifecycle_pressure.py tests/fake-run-lifecycle
git commit -m "docs(job-search): audit query strategy style compliance"
```

Before committing, inspect `git diff --cached --name-only` and unstage any unrelated path.

---

### Task 9: Version, build, and verify the release candidate

**Files:**

- Modify: `.claude-plugin/plugin.json`
- Modify: `.codex-plugin/plugin.json`
- Modify: `.cursor-plugin/plugin.json`
- Modify: `.factory-plugin/plugin.json`
- Modify: `gemini-extension.json`
- Modify: `package.json`
- Modify: `shared/references/build-stamp.md`
- Modify: `TESTING.md` only if the automated test count is intentionally maintained there

- [ ] **Step 1: Bump all six manifests from `0.6.0` to `0.6.1`**

Use the repository's ordinary JSON formatting and change only `version` in each manifest. Do not add a version to skill frontmatter or the saved config schema.

- [ ] **Step 2: Regenerate the stamp and prove the build is idempotent**

Run:

```bash
./scripts/build.sh
shasum -a 256 shared/references/build-stamp.md > /tmp/job-search-build-stamp.sha
./scripts/build.sh
shasum -a 256 shared/references/build-stamp.md | diff - /tmp/job-search-build-stamp.sha
```

Expected: both builds print the stamp-only message; `diff` has no output. No files appear under `skills/*/references/query-strategy.md`.

- [ ] **Step 3: Run release-integrity and structural packaging gates**

Run:

```bash
python3 scripts/check_release_integrity.py --root . --check-version-sync --check-version-bump --base 1e3dbe3
python3 scripts/eval_harness.py --root .
python3 -m pytest -q -p no:cacheprovider tests/test_release_integrity.py tests/test_reference_resolution.py tests/test_doc_lint.py tests/test_doc_lint_intra_reference.py tests/test_philosophy_guard.py tests/test_query_strategy_contract.py tests/test_fake_agent_data.py tests/test_run_lifecycle_pressure.py tests/test_usage_context_contract.py tests/test_eval_harness.py
```

Expected: version sync and forward bump are clean; eval structure is valid; all focused suites pass.

- [ ] **Step 4: Run the full deterministic suite**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider
```

Expected: `0 failed`. Update an exact count in `TESTING.md` only if that document intentionally pins the count; the release gate is zero failures.

- [ ] **Step 5: Inspect the final runtime and packaging diff**

Run:

```bash
git diff --check
git diff --cached --check
git status --short
git diff --name-only 1e3dbe3...HEAD
git diff --name-only
git ls-files docs-private
find skills -path '*/references/query-strategy.md' -print
```

Expected:

- no whitespace errors;
- `git ls-files docs-private` prints nothing;
- `find` prints nothing because the strategy is single-homed;
- no config migration, new runtime dependency, provider-specific keyword rule, or build fan-out appears;
- all runtime changes are represented in version `0.6.1` and the regenerated stamp.

- [ ] **Step 6: Commit the release candidate**

```bash
git add .claude-plugin/plugin.json .codex-plugin/plugin.json .cursor-plugin/plugin.json .factory-plugin/plugin.json gemini-extension.json package.json shared/references/build-stamp.md TESTING.md
git commit -m "chore(release): ship recall-oriented query strategy"
```

- [ ] **Step 7: Perform the final no-placeholder and design-coverage review**

Run:

```bash
rg -n "TB[D]|TO[D]O|FIXM[E]|simila[r] to|generated local references/query-strateg[y]|build copies the shared referenc[e]" docs/superpowers/plans/2026-07-21-recall-oriented-query-strategy.md docs/superpowers/specs/2026-07-20-recall-oriented-query-strategy-design.md skills shared/references tests
git log --oneline 1e3dbe3..HEAD
git status --short
```

Expected: no unresolved placeholder or stale fan-out language in the implementation surfaces; the commit list maps to Tasks 1–9; the worktree is clean. Any legitimate fixture occurrence of a scanned word must be reviewed and documented rather than silently ignored.

## Completion Evidence

Implementation is complete only when all of the following are true:

- The deterministic keyword-sensitive Ashby fixture proves broad role-family queries retrieve rows where a phrase-stuffed query does not under identical non-keyword parameters.
- New setup and explicit retune derive a coverage-complete portfolio with no fixed query count.
- Existing saved searches remain unchanged until the user approves a retune.
- Every new run stream records the five request-evidence fields and older incomplete evidence fails closed for query-health comparison.
- The home view evaluates exactly the newest three comparable authoritative runs, applies contextual judgment, shows at most one nudge per unchanged shape, and remains read-only until accepted.
- Zero relevant, all known, source failure, intentional narrowing, and thin raw retrieval follow distinct branches.
- The runner executes exactly the resolved request and never broadens automatically.
- All stochastic scenarios declare five reps and a no-guidance control; the live ATS smoke remains separately authorized and outside the merge gate.
- The complete PSG/AAS audit has no unresolved MUST defect.
- Version `0.6.1`, stamp-only idempotence, focused tests, full pytest, release integrity, reference resolution, and final diff inspection are green.
