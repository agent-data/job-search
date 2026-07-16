"""Structural contract tests for calls-first agent-data usage decisions."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared" / "references"
INTERNALS = SHARED / "internals.md"
AGENT_DATA = SHARED / "agent-data-contract.md"

ACTION_DECISIONS = {
    "first_live_run": (
        "one_off",
        "B",
        "continuation_plus_detail_calls",
        "none",
        "yes",
        "request_is_scoped_consent",
    ),
    "query_or_source_enable": (
        "persistent",
        "post_change_B_and_delta",
        "continuation_plus_detail_calls",
        "saved_cadence_window",
        "yes",
        "confirm_before_write",
    ),
    "cadence_increase": (
        "persistent",
        "B_per_run",
        "continuation_plus_detail_calls",
        "current_vs_new_cadence_window",
        "yes",
        "confirm_before_write",
    ),
    "saved_review_depth_increase": (
        "persistent",
        "B",
        "continuation_plus_detail_calls",
        "saved_cadence_window",
        "yes",
        "confirm_before_write",
    ),
    "one_off_review_depth_increase": (
        "one_off",
        "B",
        "continuation_plus_detail_calls",
        "none",
        "no",
        "request_is_scoped_consent",
    ),
    "retrieval_broadening_likely_detail_reads": (
        "persistent",
        "B_or_post_change_B",
        "detail_calls_likely_not_bounded",
        "saved_cadence_window",
        "yes",
        "confirm_before_write",
    ),
    "schedule_enable_with_canary": (
        "persistent",
        "B_per_canary_and_run",
        "continuation_plus_detail_calls",
        "one_canary_plus_saved_cadence_window",
        "yes",
        "confirm_schedule_and_one_canary",
    ),
    "metered_canary_retry_or_repair": (
        "retry_or_repair",
        "B_per_canary_attempt",
        "continuation_plus_detail_calls",
        "approved_attempt_only",
        "no",
        "confirm_each_metered_canary_attempt",
    ),
}

POLICY_DECISIONS = {
    "baseline_formula": "enabled_queries*enabled_sources",
    "baseline_is_ceiling": "false",
    "one_off_request": "scoped_consent_after_context",
    "persistent_increase": "confirm_before_write",
    "metered_repair_or_retry_canary": "confirm_each_attempt",
    "scheduled_headless_run": "consume_durable_saved_consent",
    "neutral_or_decreasing_edit": "quiet",
    "model_or_concurrency_only_edit": "quiet_unless_canary",
    "first_live_context": "one_or_two_sentences_calls_first_plus_available_free_tier",
    "account_claims": "never_infer_plan_or_balance",
    "account_visibility_caveat": "omit_when_no_decision_value",
    "uncertain_additions": "not_a_ceiling",
}


def _marked_block(text, namespace, name):
    pattern = (
        rf"<!-- {re.escape(namespace)}:{re.escape(name)} -->\s*"
        rf"(?P<body>.*?)\s*"
        rf"<!-- /{re.escape(namespace)}:{re.escape(name)} -->"
    )
    match = re.search(pattern, text, re.DOTALL)
    assert match, f"missing marked contract block {namespace}:{name}"
    return match.group("body")


def _code_table(text, namespace, name, columns):
    """Parse a marked Markdown table whose data cells are stable code tokens."""
    block = _marked_block(text, namespace, name)
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    assert len(lines) >= 3, f"{namespace}:{name} has no data rows"
    assert len(lines[0].strip("|").split("|")) == columns
    separators = [cell.strip() for cell in lines[1].strip("|").split("|")]
    assert len(separators) == columns
    assert all(re.fullmatch(r":?-+:?", cell) for cell in separators)

    rows = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == columns, f"malformed row in {namespace}:{name}: {line!r}"
        values = []
        for cell in cells:
            match = re.fullmatch(r"`([^`]+)`", cell)
            assert match, f"non-token cell in {namespace}:{name}: {cell!r}"
            values.append(match.group(1))
        rows.append(values)

    keys = [row[0] for row in rows]
    assert len(keys) == len(set(keys)), f"duplicate keys in {namespace}:{name}: {keys}"
    return {row[0]: tuple(row[1:]) for row in rows}


def test_usage_decision_table_covers_exact_action_families_and_rules():
    text = INTERNALS.read_text(encoding="utf-8")
    assert _code_table(text, "usage-context-contract", "action-decisions", 7) == ACTION_DECISIONS
    assert _code_table(text, "usage-context-contract", "policy", 2) == {
        key: (value,) for key, value in POLICY_DECISIONS.items()
    }
    assert {row[0] for row in ACTION_DECISIONS.values()} <= {
        "one_off", "persistent", "neutral_or_decreasing", "retry_or_repair"
    }


def test_free_tier_fact_is_exact_dated_and_loaded_from_its_canonical_owner():
    contract = AGENT_DATA.read_text(encoding="utf-8")
    pricing = _code_table(contract, "agent-data-metering-contract", "pricing", 3)
    assert pricing["free_tier"] == ("100", "no_charge")
    assert re.search(r"These values were verified on \d{4}-\d{2}-\d{2}\.", contract)

    internals = INTERNALS.read_text(encoding="utf-8")
    assert "(agent-data-contract.md#pricing-and-metering)" in internals
    for literal in ("$0.008", "$0.0075", "$0.0067", "$0.005"):
        for path in SHARED.glob("*.md"):
            if path != AGENT_DATA:
                assert literal not in path.read_text(encoding="utf-8"), (
                    f"volatile dollar fact {literal!r} duplicated in {path.relative_to(ROOT)}"
                )


def test_usage_context_is_single_homed_and_every_skill_reaches_it_one_hop():
    canonical_marker = "<!-- usage-context-contract:action-decisions -->"
    for path in SHARED.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if path == INTERNALS:
            assert canonical_marker in text
        else:
            assert canonical_marker not in text

    for name in ("agent-data-contract.md", "conventions.md", "errors.md"):
        text = (SHARED / name).read_text(encoding="utf-8")
        assert "(internals.md#agent-data-usage-decisions)" in text, (
            f"{name} must point to the canonical usage decision table"
        )

    skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
    assert len(skills) == 5
    for skill in skills:
        assert "../../shared/references/internals.md" in skill.read_text(encoding="utf-8"), (
            f"{skill.relative_to(ROOT)} needs a one-hop pointer to internals.md"
        )


def test_no_budget_credits_or_cost_config_key_ships():
    config_key = re.compile(
        r"(?im)^[ \t]*(?:-[ \t]*)?[\"']?(budget|credits|cost)[\"']?[ \t]*:"
    )
    roots = (ROOT / "shared", ROOT / "skills", ROOT / "templates", ROOT / "examples")
    offenders = []
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".yaml", ".yml", ".json", ".jsonl"}:
                if config_key.search(path.read_text(encoding="utf-8")):
                    offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, f"forbidden monetary config keys ship in: {offenders}"
