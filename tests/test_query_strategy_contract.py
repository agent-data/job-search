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
HOME = ROOT / "skills" / "job-search" / "references" / "home.md"
CUSTOMIZATION = ROOT / "skills" / "job-search-agent" / "references" / "customization.md"
RUN_LIFECYCLE = ROOT / "shared" / "references" / "run-lifecycle.md"

# The application surfaces: files that APPLY their local part of the query-strategy contract in their own
# words. The strategy is reached by exactly two direct pointers, both in SKILL.md files; a third pointer
# from any of these would make the single home a reference-to-reference hop.
APPLICATION_SURFACES = (HOME, ONBOARDING, CUSTOMIZATION, RUN_LIFECYCLE)

# A PATH pointer to the strategy: `references/query-strategy.md`, with or without a `shared/` segment and
# any number of `../` hops. Modeled on `_PTR` in tests/test_reference_resolution.py, which draws exactly
# this path-versus-name distinction: a bare backticked `query-strategy.md` carries no directory component,
# is not a path, and is deliberately NOT matched — conventions.md names the file that way on purpose, to
# satisfy the intra-reference duplication lint, and any file may do the same.
_STRATEGY_PTR = re.compile(r"(?:\.\./)*(?:shared/)?references/query-strategy\.md")


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


def test_application_surfaces_apply_the_strategy_instead_of_pointing_at_it():
    """The strategy has exactly TWO direct pointers, both in SKILL.md files. Every application surface —
    the home view, onboarding, customization, the run lifecycle — applies its local part of the contract in
    its own words and never links to it. A one-hop `../../../shared/references/query-strategy.md` added to
    one of them would resolve, so tests/test_reference_resolution.py would happily accept it; this is the
    only structural guard on the two-pointer rule."""
    # the path-versus-name distinction the rule is built on (a bare name mention stays legal)
    assert _STRATEGY_PTR.search("read `../../../shared/references/query-strategy.md` when retuning")
    assert _STRATEGY_PTR.search("see `references/query-strategy.md`")
    assert not _STRATEGY_PTR.search("the repeated-thin rule is owned by `query-strategy.md`")

    for surface in APPLICATION_SURFACES:
        assert surface.is_file(), f"missing application surface {surface}"
        found = sorted({m.group(0) for m in _STRATEGY_PTR.finditer(surface.read_text(encoding="utf-8"))})
        assert not found, (
            f"{surface.relative_to(ROOT)} points at the query strategy ({found}). Only the two SKILL.md "
            f"files may point at `shared/references/query-strategy.md`; an application surface applies its "
            f"local part of the contract in its own words. Name the file inline if you must — a bare "
            f"backticked `query-strategy.md` is allowed — but do not add a path pointer.")


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
