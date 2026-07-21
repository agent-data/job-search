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
