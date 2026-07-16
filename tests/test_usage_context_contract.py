"""Structural contract tests for calls-first agent-data usage decisions."""

from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared" / "references"
INTERNALS = SHARED / "internals.md"
AGENT_DATA = SHARED / "agent-data-contract.md"
VOICE = SHARED / "voice.md"
ONBOARDING = ROOT / "skills" / "job-search" / "references" / "onboarding.md"
CUSTOMIZATION = ROOT / "skills" / "job-search-agent" / "references" / "customization.md"
RUNNER = ROOT / "skills" / "job-search-run" / "SKILL.md"
OPERATOR = ROOT / "skills" / "job-search-agent" / "SKILL.md"

APPROVED_CONNECTED_BASELINE = (
    "Agent-data offers a 100-call monthly free tier. This search starts with 4 calls; "
    "reading promising postings may add detail calls."
)
APPROVED_PREINSTALL = (
    "Agent-data offers a 100-call monthly free tier—enough to get started with this search."
)

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


def _persisted_config_surfaces(root):
    """Yield real config templates/schemas and fenced persisted-config examples."""
    roots = [root / name for name in ("shared", "skills", "templates", "examples")]
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if re.search(r"(?:^|/)(?:config|[^/]+\.config)(?:\.[^/]+)*\.(?:ya?ml|json)$", relative):
                yield relative, path.read_text(encoding="utf-8")
                continue
            if path.suffix != ".md":
                continue

            text = path.read_text(encoding="utf-8")
            for index, match in enumerate(
                re.finditer(r"(?ms)^```(?P<info>[^\n]*)\n(?P<body>.*?)^```[ \t]*$", text), start=1
            ):
                info = match.group("info").strip().lower()
                if info not in {"", "yaml", "yml", "config.yaml", "config.yml"}:
                    continue
                heading_start = text.rfind("\n#", 0, match.start())
                context = text[heading_start + 1 if heading_start >= 0 else 0:match.start()]
                if "config.yaml" in context.lower() or info.startswith("config."):
                    yield f"{relative}#config-fence-{index}", match.group("body")


def _forbidden_monetary_config_key_hits(root):
    config_key = re.compile(
        r"(?im)^[ \t]*(?:-[ \t]*)?[\"']?(budget|credits|cost)[\"']?[ \t]*:"
    )
    hits = []
    for surface, text in _persisted_config_surfaces(root):
        hits.extend((surface, match.group(1).lower()) for match in config_key.finditer(text))
    return hits


def _normalized_prose(path):
    return " ".join(path.read_text(encoding="utf-8").split())


def _eval(skill):
    path = ROOT / "skills" / skill / "evals" / "evals.json"
    return json.loads(path.read_text(encoding="utf-8"))


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
    assert pricing["free_tier"] == ("100_calls_per_month", "no_charge")
    assert re.search(r"These values were verified on \d{4}-\d{2}-\d{2}\.", contract)


def test_usage_decision_contract_loads_but_does_not_duplicate_the_free_tier_fact():
    internals = INTERNALS.read_text(encoding="utf-8")
    assert "(agent-data-contract.md#pricing-and-metering)" in internals
    assert not re.search(r"(?i)monthly[ -]free[- ]tier|100[- _]calls?(?:[- _]|/)+per[- _]month", internals)
    for literal in ("$0.008", "$0.0075", "$0.0067", "$0.005"):
        for path in SHARED.glob("*.md"):
            if path != AGENT_DATA:
                assert literal not in path.read_text(encoding="utf-8"), (
                    f"volatile dollar fact {literal!r} duplicated in {path.relative_to(ROOT)}"
                )

    for path in SHARED.glob("*.md"):
        if path != AGENT_DATA:
            text = path.read_text(encoding="utf-8")
            assert "100_calls_per_month" not in text
            assert not re.search(r"(?i)100[- ]calls?\s*(?:/|per)\s*month", text)


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


def test_voice_single_homes_the_two_approved_user_facing_renderings():
    voice = _normalized_prose(VOICE)
    assert APPROVED_CONNECTED_BASELINE in voice
    assert APPROVED_PREINSTALL in voice

    shipped = [*SHARED.glob("*.md"), *ROOT.glob("skills/**/*.md")]
    for sentence in (APPROVED_CONNECTED_BASELINE, APPROVED_PREINSTALL):
        owners = [path.relative_to(ROOT).as_posix() for path in shipped
                  if sentence in _normalized_prose(path)]
        assert owners == ["shared/references/voice.md"], (
            f"approved rendering must stay single-homed in voice.md: {sentence!r} -> {owners}"
        )


def test_t2_2_consumers_point_to_the_canonical_decision_table_and_rendering_owner():
    consumers = [ONBOARDING, CUSTOMIZATION, RUNNER, OPERATOR]
    for path in consumers:
        text = path.read_text(encoding="utf-8")
        assert "internals.md#agent-data-usage-decisions" in text, (
            f"{path.relative_to(ROOT)} must point to the T2.1 action table, not restate it"
        )
        assert "voice.md" in text, (
            f"{path.relative_to(ROOT)} must consume the shared user-facing rendering guidance"
        )


def test_t2_2_guidance_covers_preview_consent_quiet_and_actual_attempt_effects():
    voice = VOICE.read_text(encoding="utf-8").lower()
    onboarding = ONBOARDING.read_text(encoding="utf-8").lower()
    customization = CUSTOMIZATION.read_text(encoding="utf-8").lower()
    operator = OPERATOR.read_text(encoding="utf-8").lower()
    runner = RUNNER.read_text(encoding="utf-8").lower()

    for slot in ("before:", "after:", "variable work:", "confirm:"):
        assert slot in voice, f"persistent-change rendering is missing {slot!r}"
    assert "one or two sentences" in voice and "calls-only" in voice
    assert "before the first metered" in onboarding and "scoped consent" in onboarding
    assert "neutral or decreasing" in customization and "quiet" in customization
    assert "scheduled/headless" in customization and "durable" in customization
    assert "metered canary" in operator and "fresh scoped confirmation" in operator
    assert "producer-authoritative" in runner and "completed attempt" in runner


def test_t2_2_effect_evals_cover_all_six_fake_only_red_cases():
    search = _eval("job-search")
    agent = _eval("job-search-agent")
    runner = _eval("job-search-run")

    search_by_id = {case["id"]: case for case in search["evals"]}
    assert "first metered row" in " ".join(search_by_id[1]["expectations"])
    assert APPROVED_CONNECTED_BASELINE in " ".join(search_by_id[1]["expectations"])
    assert APPROVED_PREINSTALL in " ".join(search_by_id[6]["expectations"])

    agent_by_scenario = {case["scenario"]: case for case in agent["evals"]}
    increases = agent_by_scenario[
        "persistent source and cadence increases preview before one scoped write"
    ]
    decreases = agent_by_scenario[
        "decreasing cadence and disabling a source are immediate and quiet"
    ]
    canary = agent_by_scenario[
        "a failed metered schedule canary needs fresh consent before the second attempt"
    ]
    assert "byte-for-byte unchanged" in " ".join(increases["expectations"])
    assert "no confirmation question" in " ".join(decreases["expectations"])
    assert "no second-attempt metered row" in " ".join(canary["expectations"])
    assert all("fake" in case["prompt"].lower() or "shim" in case["prompt"].lower()
               for case in (increases, decreases, canary))

    actual_attempts = next(case for case in runner["evals"] if case["id"] == 30)
    joined = " ".join(actual_attempts["expectations"])
    assert "producer-authoritative metered field" in joined
    assert "failed original and failed retry" in joined

    # The canonical one-off rule replaces the older redundant-confirmation eval behavior.
    for case_id in (6, 8):
        case = next(case for case in agent["evals"] if case["id"] == case_id)
        joined = " ".join(case["expectations"])
        assert "without a redundant confirmation" in joined


def test_no_budget_credits_or_cost_key_in_persisted_config_surfaces():
    hits = _forbidden_monetary_config_key_hits(ROOT)
    assert not hits, f"forbidden monetary config keys ship in config surfaces: {hits}"


def test_non_config_cost_fields_and_prose_are_allowed(tmp_path):
    api_doc = tmp_path / "shared" / "references" / "api.md"
    api_doc.parent.mkdir(parents=True)
    api_doc.write_text(
        "Ordinary prose may discuss cost: it is not persisted config.\n\n"
        "```json\n{\"cost\": \"response metadata\"}\n```\n",
        encoding="utf-8",
    )
    run_artifact = tmp_path / "examples" / "sample-run.json"
    run_artifact.parent.mkdir(parents=True)
    run_artifact.write_text('{"cost": "artifact context"}\n', encoding="utf-8")

    assert _forbidden_monetary_config_key_hits(tmp_path) == []


def test_forbidden_key_detection_is_scoped_to_real_config_surfaces(tmp_path):
    template = tmp_path / "templates" / "config.example.yaml"
    template.parent.mkdir(parents=True)
    template.write_text("version: 1\nsearch:\n  cost: 10\n", encoding="utf-8")
    schema_doc = tmp_path / "shared" / "references" / "schema.md"
    schema_doc.parent.mkdir(parents=True)
    schema_doc.write_text(
        "## config.yaml\n\n```yaml\nversion: 1\nbudget: 25\ncredits: 50\n```\n",
        encoding="utf-8",
    )

    assert _forbidden_monetary_config_key_hits(tmp_path) == [
        ("shared/references/schema.md#config-fence-1", "budget"),
        ("shared/references/schema.md#config-fence-1", "credits"),
        ("templates/config.example.yaml", "cost"),
    ]
