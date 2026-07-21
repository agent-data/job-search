"""Canonical query-strategy contract: one shared home, direct one-hop pointers, marked tables.

`shared/references/query-strategy.md` is the single authored home for query judgment — recall-oriented
portfolio construction, contextual retrieval-health assessment, and user-approved broadening. The two
consuming skills (the interactive front door and the operator manual) point at it directly with
`../../shared/references/query-strategy.md`; there is no skill-local copy and no reference-to-reference
hop (`tests/test_reference_resolution.py` proves those pointers resolve on every supported host).

Assertions are made against MARKED machine-readable tables rather than model narration, so wording can
be edited freely while the contract values stay pinned.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
STRATEGY = ROOT / "shared" / "references" / "query-strategy.md"
FRONT_DOOR = ROOT / "skills" / "job-search" / "SKILL.md"
OPERATOR = ROOT / "skills" / "job-search-agent" / "SKILL.md"
ONBOARDING = ROOT / "skills" / "job-search" / "references" / "onboarding.md"
CONVENTIONS = ROOT / "shared" / "references" / "conventions.md"
INTERNALS = ROOT / "shared" / "references" / "internals.md"

# A PATH pointer to the strategy: `references/query-strategy.md`, with or without a `shared/` segment and
# any number of `../` hops. Modeled on `_PTR` in tests/test_reference_resolution.py, which draws exactly
# this path-versus-name distinction: a bare backticked `query-strategy.md` carries no directory component,
# is not a path, and is deliberately NOT matched — conventions.md names the file that way on purpose, to
# satisfy the intra-reference duplication lint, and any file may do the same.
_STRATEGY_PTR = re.compile(r"(?:\.\./)*(?:shared/)?references/query-strategy\.md")

# A RANGED query-derivation instruction, banned across every scanned surface. The portfolio contract
# derives the count from coverage closure, so naming a range — the removed "Derive 2-3 queries", its
# checklist twin, the disguised "usually two or three queries", or "writes 2-3 distinct queries" — is a
# regression, and the plan checked for it only with a one-time manual scan. Every pattern requires the
# query/search noun in the same phrase, at most one intervening adjective away, which is what keeps this
# narrow instead of allowlisted: "a 2-3 sentence Summary" (conventions.md and job-preference-interview,
# describing the BRIEF, not retrieval) is legitimate and must keep passing.
#
# SCOPE, deliberately RANGED (plus the one narrow `exactly N enabled queries` form) and never a bare single
# count: "usually three queries" and "no more than four queries" are NOT caught. Extending the patterns to
# catch them was measured and rejected — a bare `(\d+|one..five)\s+(\w+\s+)?(quer|search)` matches eight
# legitimate live lines: query-strategy.md's own "One query may cover several lanes" and "it may be one
# query for a narrow search", conventions.md's "one logical query/source stream", onboarding.md's "the
# three searches below", agent-data-contract.md's `... search-jobs` CLI example and "one search row",
# home.md's "one metered search call", and errors.md's "a 200 search response" — plus the reporting phrase
# "Ran 3 searches" this module already pins as legal. Dropping "one" still leaves three of those hits.
# Catching bare counts would therefore need suppressions or an allowlist; the test name states the ranged
# scope instead, so a maintainer reads what the patterns actually deliver.
_RANGE_DIGITS = r"\d+\s*(?:[-\u2010-\u2015]|\s+to\s+)\s*\d+"  # ASCII hyphen, U+2010..U+2015 dashes, or "to"
_RANGE_WORDS = r"(?:one|two|three|four|five)\s+(?:or|to)\s+(?:one|two|three|four|five)"
_RANGED_COUNT_QUERIES = (
    re.compile(rf"deriv\w*\s+{_RANGE_DIGITS}", re.I),
    re.compile(rf"(?:{_RANGE_DIGITS}|{_RANGE_WORDS})\s+(?:\w+\s+)?(?:quer|search)", re.I),
    re.compile(r"exactly\s+(?:\d+|one|two|three|four|five)\s+enabled\s+quer", re.I),
)


def pointer_scanned_surfaces():
    """Every shipped Markdown surface an agent reads at runtime: both `SKILL.md` runbooks and their
    skill-local reference bodies, plus the shared reference layer. Product specs are deliberately excluded
    — they are prose about the product, not a surface an agent loads, so a path there costs no hop."""
    return sorted(ROOT.glob("skills/**/*.md")) + sorted((ROOT / "shared" / "references").glob("*.md"))


def scanned_surfaces():
    """Every shipped Markdown surface an agent reads at runtime — both SKILL.md runbooks and their
    skill-local reference bodies, plus the shared reference layer — AND `docs/product-specs/*.md`.

    The product specs are not runtime surfaces, but the stale "derives 2-3 searches" line this gate exists
    to stop actually lived in `docs/product-specs/new-user-onboarding.md`: it matched the patterns and sat
    outside a skills+shared-only glob, so the same regression could have silently returned there. The
    directory is clean under these patterns today, so scanning it costs nothing."""
    return (sorted(ROOT.glob("skills/**/*.md"))
            + sorted((ROOT / "shared" / "references").glob("*.md"))
            + sorted((ROOT / "docs" / "product-specs").glob("*.md")))


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


def test_path_pointers_to_the_strategy_appear_only_in_skill_md():
    """The invariant is the SHAPE of the pointer graph, not a pointer count: a path pointer to the strategy
    may appear only in a `SKILL.md`. That is what keeps the single home exactly one hop from a runbook —
    every other runtime surface (skill-local reference bodies and the shared reference layer alike) applies
    its local part of the contract in its own words instead of linking to it, so no reference-to-reference
    hop and no skill-local copy can appear. A one-hop `../../../shared/references/query-strategy.md` added
    to any of them would resolve, so tests/test_reference_resolution.py would happily accept it; this is the
    only structural guard.

    Scanned over EVERY `.md` under `skills/` and `shared/references/`, not a named allowlist: the earlier
    four-file allowlist would have let a pointer in `skills/job-search-run/SKILL.md`,
    `skills/evaluate-job-fit/SKILL.md`, or a new shared reference pass silently."""
    # the path-versus-name distinction the rule is built on (a bare name mention stays legal)
    assert _STRATEGY_PTR.search("read `../../../shared/references/query-strategy.md` when retuning")
    assert _STRATEGY_PTR.search("see `references/query-strategy.md`")
    assert not _STRATEGY_PTR.search("the repeated-thin rule is owned by `query-strategy.md`")

    surfaces = pointer_scanned_surfaces()
    assert len(surfaces) >= 10, f"pointer scan collapsed to {len(surfaces)} files: {surfaces}"
    assert any(path.name == "SKILL.md" for path in surfaces)
    for surface in surfaces:
        if surface.name == "SKILL.md":
            continue
        found = sorted({m.group(0) for m in _STRATEGY_PTR.finditer(surface.read_text(encoding="utf-8"))})
        assert not found, (
            f"{surface.relative_to(ROOT)} points at the query strategy ({found}). Only `SKILL.md` files "
            f"may carry a path pointer to `shared/references/query-strategy.md`; every other surface "
            f"applies its local part of the contract in its own words. Name the file inline if you must — "
            f"a bare backticked `query-strategy.md` is allowed — but do not add a path pointer.")


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


def test_new_run_streams_record_comparable_request_evidence():
    assert marked_table(CONVENTIONS, "run-stream-request-fields") == {
        "request_origin": "required_saved_or_one_off",
        "location": "required_normalized_string_or_null",
        "limit": "required_integer_1_through_100",
        "freshness": "required_saved_selector_or_null_for_one_off",
        "published_on_or_after": "required_iso_date_or_null",
        "legacy_missing_fields": "readable_but_query_health_ineligible",
    }


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


def test_no_scanned_surface_prescribes_a_ranged_query_count():
    """`query_count` is `derived_no_universal_target_or_cap`, so no scanned surface may instruct an agent
    to derive a RANGE of queries. The plan verified that twice with a one-time manual `rg`, which cannot
    stop "Derive 2-3 queries" from coming back; this is the standing gate. Bare single counts are outside
    the patterns by measurement, not oversight — see the SCOPE note above `_RANGED_COUNT_QUERIES`."""
    # controls — the plan's own scan phrasings in both dash forms, plus one intervening adjective
    for banned in ("Derive 2-3 queries", "Derive 2–3 queries", "2–3 queries", "2-3 queries",
                   "usually two or three queries", "exactly two enabled queries",
                   "The skill writes 2–3 distinct queries", "two or three separate searches"):
        assert any(p.search(banned) for p in _RANGED_COUNT_QUERIES), banned
    # control — a fixed count of BRIEF SENTENCES is not a query-derivation instruction and stays legal
    for legal in ("a 2–3 sentence **Summary**", "Ran 3 searches", "for a source with Q enabled queries"):
        assert not any(p.search(legal) for p in _RANGED_COUNT_QUERIES), legal
    # control — the deliberate scope limit: a bare single count is documented as out of range, not caught
    for uncaught in ("usually three queries", "no more than four queries"):
        assert not any(p.search(uncaught) for p in _RANGED_COUNT_QUERIES), uncaught

    hits = []
    for path in scanned_surfaces():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(p.search(line) for p in _RANGED_COUNT_QUERIES):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")
    assert not hits, (
        "a scanned surface prescribes a ranged query count; the portfolio contract derives it from lane "
        "coverage closure, so state the coverage rule instead of a number:\n" + "\n".join(hits))


def test_query_health_decisions_distinguish_retrieval_from_fit():
    assert marked_table(STRATEGY, "decision-table") == {
        "failed_blocked_or_incomplete": "operational_recovery_then_wait_for_healthy_evidence",
        "contextually_or_repeatedly_thin": "propose_broader_complementary_role_families",
        "healthy_raw_but_zero_relevant": "inspect_rejections_then_replace_lane_or_clarify_brief",
        "healthy_noisy_and_user_wants_less": "intentional_narrowing",
        "healthy_but_all_known": "report_seen_results_and_leave_breadth_unchanged",
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
