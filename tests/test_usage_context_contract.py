"""Structural contract tests for calls-first agent-data usage decisions.

Everything here reads a machine-readable surface: a `<!-- namespace:name -->` marked block in a
shared reference, a config template or fenced config example, a shell fixture, or an entry in a
skill's evals.json. How the surrounding guidance prose reads is graded by the behavior evals in
evals/ — never by substring assertions here.
"""

from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared" / "references"
INTERNALS = SHARED / "internals.md"
AGENT_DATA = SHARED / "agent-data-contract.md"
CONVENTIONS = SHARED / "conventions.md"
ERRORS = SHARED / "errors.md"
PARALLELISM = SHARED / "parallelism.md"
CONFIG_TEMPLATE = ROOT / "templates" / "config.example.yaml"
CUSTOMIZATION = ROOT / "skills" / "job-search-agent" / "references" / "customization.md"
RUNNER_SETUP = ROOT / "skills" / "job-search-run" / "evals" / "files" / "setup-workspace.sh"

# Agent-data's per-call prices, which change whenever its plans change.
VOLATILE_PRICE_LITERALS = ("$0.008", "$0.0075", "$0.0067", "$0.005")

FORBIDDEN_EQUIVALENT_CHARGE_EXCEPTIONS = (
    re.compile(r"unless live account data says otherwise"),
    re.compile(
        r"(?:pay-as-you-go|computed|dollar) equivalent.{0,160}"
        r"\b(?:unless|except(?: when)?|but if)\b.{0,160}\b(?:account|charge)\b"
    ),
    re.compile(
        r"\b(?:unless|except(?: when)?|but if)\b.{0,160}\b(?:account|billing)\b"
        r".{0,160}\b(?:pay-as-you-go|computed|dollar) equivalent\b"
    ),
    re.compile(
        r"if live account(?:-plan)? metadata is absent,?\s+say the equivalent is not an actual charge"
    ),
    re.compile(
        r"(?:pay-as-you-go equivalent|equivalent).{0,200}\bnot an actual charge\b.{0,100}"
        r"\b(?:because|if|when|unless|except)\b.{0,160}\b(?:account|metadata)\b"
    ),
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

CONFIG_V2_MODEL_FIELDS = {
    "version": ("workspace_config", "required", "2"),
    "search.detail_model": (
        "workspace_config",
        "required",
        "haiku_sonnet_opus_or_exact_model_id",
    ),
}

RUN_RECORD_MODEL_FIELDS = {
    "detail_model": (
        "run_record",
        "required_after_binding_else_null_on_model_binding_block",
        "exact_model_used_or_resolved",
    ),
    "detail_model_origin": (
        "run_record",
        "required_after_binding_else_null_on_model_binding_block",
        "detail_model_origin_enum",
    ),
    "detail_model_binding_id": (
        "run_record",
        "required_after_binding_else_null_on_model_binding_block",
        "current_binding_id_or_null_for_legacy_v1",
    ),
}

MODEL_BINDING_BLOCK = {
    "internal_class": ("detail_model_binding_unavailable",),
    "applies": ("v2_evidence_or_v1_resolution_or_exact_dispatch_failure",),
    "config_effect": ("preserve_bytes",),
    "run_effect": ("blocked_record_and_digest_when_workspace_writable",),
    "model_fields_before_binding": ("null",),
    "metering": ("preserve_completed_attempt_accounting",),
    "user_route": ("t3_3_interactive_model_repair",),
    "raw_user_code": ("none",),
}

DETAIL_MODEL_ORIGINS = {
    "configured_auto": ("setup_selected_exact_model",),
    "configured_user": ("user_selected_exact_model",),
    "legacy_v1_selector": ("legacy_version_1_resolution",),
    "repair": ("repaired_exact_model",),
}

DETAIL_MODEL_ORIGIN_EVIDENCE = {
    "writer": ("run_record_producer",),
    "accepted_evidence": (
        "canonical_active_workspace_binding_sidecar_or_observed_legacy_v1_resolution",
    ),
    "version_2_copy": ("binding_id_and_origin_from_valid_sidecar",),
    "prior_run_evidence": ("prohibited_even_for_same_exact_model",),
    "missing_invalid_or_mismatched": ("block_and_route_interactive_model_repair",),
}

DETAIL_MODEL_BINDING_FIELDS = {
    "version": ("binding_sidecar", "required", "1"),
    "binding_id": (
        "binding_sidecar",
        "required",
        "fresh_locally_generated_identifier",
    ),
    "detail_model": (
        "binding_sidecar",
        "required",
        "exact_copy_of_config_search.detail_model",
    ),
    "detail_model_origin": (
        "binding_sidecar",
        "required",
        "binding_origin_enum",
    ),
    "bound_at": ("binding_sidecar", "required", "utc_iso8601_timestamp"),
}

DETAIL_MODEL_BINDING_ORIGINS = {
    "configured_auto": ("setup_selected_exact_model",),
    "configured_user": ("user_selected_exact_model",),
    "repair": ("repaired_exact_model",),
}

DETAIL_MODEL_BINDING_POLICY = {
    "path": ("runs/detail-model-binding.json",),
    "authority": ("config_search.detail_model",),
    "write_mode": ("atomic_whole_file_replace",),
    "write_on": ("every_model_binding_write_even_same_model",),
    "binding_id": ("fresh_on_every_write",),
    "history": ("current_only_not_append_history",),
    "pii": ("none",),
    "preflight_validation": ("canonical_active_workspace_exact_model_equality",),
    "run_record_copy": ("binding_id_and_origin",),
    "invalid_evidence": ("missing_malformed_or_mismatch_blocks_interactive_repair",),
    "prior_run_lookup": ("prohibited",),
    "t3_2_rollback": ("restore_config_and_sidecar_consistently",),
}

RUN_RECORD_SELECTION = {
    "candidate_path": ("runs/<run_id>.json",),
    "filename_filter": ("complete_name_matches_run_id_format",),
    "detail_model_binding_sidecar": ("excluded",),
    "hidden_lifecycle_or_scratch": ("excluded",),
}

LEGACY_V1_RUNTIME = {
    "selector_source": ("version_1.search.detail_model",),
    "fast": ("host_fast_tier_model",),
    "balanced": ("host_balanced_reviewer_floor_model",),
    "high": ("host_most_capable_tier_model",),
    "inherit": ("exact_primary_model",),
    "legacy_aliases": ("haiku=fast,sonnet=balanced,opus=high",),
    "config_effect": ("preserve_bytes_no_write_no_migration",),
    "run_model": ("exact_resolved_model",),
    "run_origin": ("legacy_v1_selector",),
}

LEGACY_V1_FAILURES = {
    "missing_selector": ("block_preserve_bytes_route_interactive_repair",),
    "invalid_selector": ("block_preserve_bytes_route_interactive_repair",),
    "tier_roster_unavailable": ("block_preserve_bytes_route_interactive_repair",),
    "tier_resolution_unavailable": ("block_preserve_bytes_route_interactive_repair",),
    "inherit_primary_unknown": ("block_preserve_bytes_route_interactive_repair",),
    "exact_dispatch_unsupported": ("block_no_substitute_route_interactive_repair",),
    "exact_dispatch_refused": ("block_no_substitute_route_interactive_repair",),
    "legacy_origin": ("only_after_observed_executable_exact_resolution",),
    "failure_route_owner": ("t3_3_interactive_model_repair_no_new_user_facing_code",),
}

SCHEDULER_MODEL_FIELDS = {
    "primary_model": (
        "scheduler_registry",
        "required_for_installed_schedule",
        "nonempty_exact_live_model_identifier",
    ),
    "primary_model_origin": (
        "scheduler_registry",
        "required_for_installed_schedule",
        "primary_model_origin_enum",
    ),
}

PRIMARY_MODEL_ORIGINS = {
    "session_inheritance": ("creating_session_exact_model",),
    "user_override": ("user_selected_exact_available_model",),
    "repair_session": ("repair_session_exact_model",),
}

MODEL_SETUP_POLICIES = {
    "detail_model_default": (
        "least_powerful_available_model_that_performs_fit_judgment_well",
    ),
    "detail_model_user_preference": ("exact_user_selected_available_model",),
    "separate_worker_model_unavailable": (
        "detail_model_equals_exact_primary_model_and_runs_sequentially",
    ),
    "creating_session_primary_unknown": (
        "block_verified_schedule_until_user_selects_exact_available_model",
    ),
}

RUNTIME_DETAIL_MODEL_AUTHORITY = (
    "For each posting-detail judgment, use the configured `search.detail_model`."
)


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


def _eval(skill):
    path = ROOT / "skills" / skill / "evals" / "evals.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_config_v2_requires_one_detail_model_and_isolates_legacy_selectors():
    text = CONVENTIONS.read_text(encoding="utf-8")
    assert _code_table(text, "exact-model-contract", "config-v2-fields", 4) == {
        key: value for key, value in CONFIG_V2_MODEL_FIELDS.items()
    }

    v2 = _marked_block(text, "exact-model-contract", "config-v2-fields").lower()
    legacy = _marked_block(text, "exact-model-contract", "legacy-v1-selectors").lower()
    for selector in ("fast", "balanced", "high", "inherit"):
        assert not re.search(rf"`{selector}`", v2), (
            f"version 2 must not accept the legacy tier selector {selector!r}"
        )
        assert re.search(rf"`{selector}`", legacy), (
            f"legacy version-1 compatibility must keep naming {selector!r}"
        )
    assert _code_table(text, "exact-model-contract", "legacy-v1-runtime", 2) == {
        key: value for key, value in LEGACY_V1_RUNTIME.items()
    }
    assert _code_table(text, "exact-model-contract", "legacy-v1-fail-closed", 2) == {
        key: value for key, value in LEGACY_V1_FAILURES.items()
    }


def test_static_config_template_is_v2_but_never_invents_a_model_identifier():
    """The template setup copies carries no model field at all: the 2026-07-30 rewrite retired
    that apparatus, so the line telling setup to insert one went with the onboarding prose."""
    template = CONFIG_TEMPLATE.read_text(encoding="utf-8")
    assert re.search(r"(?m)^version:\s*2\s*$", template)
    assert not re.search(r"(?m)^\s*detail_model\s*:", template)
    for selector in ("fast", "balanced", "high", "inherit"):
        assert not re.search(rf"\b{selector}\b", template.lower())


def test_canonical_v2_config_example_also_leaves_live_model_insertion_to_setup():
    text = CONVENTIONS.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^## config\.yaml\s+.*?^```yaml\n(?P<body>.*?)^```", text)
    assert match, "conventions.md is missing its canonical config.yaml example"
    example = match.group("body")
    assert re.search(r"(?m)^version:\s*2\s*$", example)
    assert not re.search(r"(?m)^\s*detail_model\s*:", example)


def test_exact_model_ownership_and_origin_enums_are_pinned_to_their_canonical_owners():
    conventions = CONVENTIONS.read_text(encoding="utf-8")
    internals = INTERNALS.read_text(encoding="utf-8")

    assert _code_table(conventions, "exact-model-contract", "run-record-fields", 4) == {
        key: value for key, value in RUN_RECORD_MODEL_FIELDS.items()
    }
    assert _code_table(conventions, "exact-model-contract", "detail-origins", 2) == {
        key: value for key, value in DETAIL_MODEL_ORIGINS.items()
    }
    assert _code_table(
        conventions, "exact-model-contract", "detail-origin-evidence", 2
    ) == {key: value for key, value in DETAIL_MODEL_ORIGIN_EVIDENCE.items()}
    assert _code_table(conventions, "exact-model-contract", "binding-sidecar-fields", 4) == {
        key: value for key, value in DETAIL_MODEL_BINDING_FIELDS.items()
    }
    assert _code_table(conventions, "exact-model-contract", "binding-sidecar-origins", 2) == {
        key: value for key, value in DETAIL_MODEL_BINDING_ORIGINS.items()
    }
    assert _code_table(conventions, "exact-model-contract", "binding-sidecar-policy", 2) == {
        key: value for key, value in DETAIL_MODEL_BINDING_POLICY.items()
    }
    assert _code_table(internals, "exact-model-contract", "scheduler-fields", 4) == {
        key: value for key, value in SCHEDULER_MODEL_FIELDS.items()
    }
    assert _code_table(internals, "exact-model-contract", "primary-origins", 2) == {
        key: value for key, value in PRIMARY_MODEL_ORIGINS.items()
    }

    assert "primary_model" not in _marked_block(
        conventions, "exact-model-contract", "config-v2-fields"
    )
    assert "detail_model_origin" not in _marked_block(
        conventions, "exact-model-contract", "config-v2-fields"
    )
    assert "detail_model" not in _marked_block(
        internals, "exact-model-contract", "scheduler-fields"
    )
    assert "detail_model_origin" not in _marked_block(
        internals, "exact-model-contract", "scheduler-fields"
    )


def test_errors_owns_the_model_binding_block_contract():
    assert _code_table(
        ERRORS.read_text(encoding="utf-8"),
        "exact-model-contract",
        "model-binding-block",
        2,
    ) == {key: value for key, value in MODEL_BINDING_BLOCK.items()}


def test_binding_sidecar_cannot_be_misread_as_a_run_record():
    conventions = CONVENTIONS.read_text(encoding="utf-8")
    assert _code_table(conventions, "exact-model-contract", "run-record-selection", 2) == {
        key: value for key, value in RUN_RECORD_SELECTION.items()
    }
    for consumer in (INTERNALS, CUSTOMIZATION):
        text = consumer.read_text(encoding="utf-8")
        assert "runs/*.json" not in text, (
            f"{consumer.relative_to(ROOT)} must not admit the detail-model sidecar as a run record"
        )


def test_runner_eval_fixture_pins_calls_first_context_and_a_validator_checked_close():
    """What the runner's shim fixtures pin about usage decisions, after the 2026-07-30 rewrite
    replaced the model-binding and config-version fixtures (that apparatus is retired): the setup
    script points discovery at a private workspace served by the fake shim, the happy case requires
    the calls-first context before the first metered call, and the quota case requires the
    allowance message."""
    setup = RUNNER_SETUP.read_text(encoding="utf-8")
    assert "registry.json" in setup          # discovery lands on the built workspace
    assert "fake-agent-data" in setup        # every case runs against the shim, spending nothing

    evals = _eval("job-search-run")["evals"]
    happy = next(case for case in evals if case["id"] == 1)
    joined = " ".join(happy["expectations"]).lower()
    assert "before the first search-jobs call" in joined
    assert "free monthly allowance" in joined
    assert "validate-workspace.sh --post-close exits 0" in joined

    quota = next(case for case in evals if "quota" in case["scenario"])
    assert "monthly allowance is spent" in " ".join(quota["expectations"]).lower()


def test_model_setup_is_one_time_and_unknown_primary_blocks_verified_scheduling():
    internals = INTERNALS.read_text(encoding="utf-8")
    assert _code_table(internals, "exact-model-contract", "setup-policy", 2) == {
        key: value for key, value in MODEL_SETUP_POLICIES.items()
    }


def test_headless_runner_uses_the_one_line_exact_model_authority_without_reselection():
    parallelism = PARALLELISM.read_text(encoding="utf-8")
    authority = _marked_block(
        parallelism, "exact-model-contract", "runtime-detail-dispatch"
    ).strip()
    assert authority == RUNTIME_DETAIL_MODEL_AUTHORITY


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


def test_per_call_dollar_prices_live_in_one_shared_reference():
    """Agent-data's per-call prices change when its plans change. One copy can be corrected; a
    second copy goes stale silently and the agent then quotes a price that is no longer real.

    The test does not name the owning file. Right now that is agent-data-contract.md; a later task
    moves these facts to a new shared reference and deletes the old one, and this guard follows
    them without an edit."""
    owners = {}
    for path in sorted(SHARED.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        found = [literal for literal in VOLATILE_PRICE_LITERALS if literal in text]
        if found:
            owners[path.relative_to(ROOT).as_posix()] = found
    assert len(owners) <= 1, (
        f"the per-call dollar prices {list(VOLATILE_PRICE_LITERALS)} are copied into more than one "
        f"shared reference, so a price change now has to be made in several places: {owners}"
    )


def test_usage_context_contract_block_is_single_homed():
    canonical_marker = "<!-- usage-context-contract:action-decisions -->"
    for path in SHARED.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if path == INTERNALS:
            assert canonical_marker in text
        else:
            assert canonical_marker not in text, (
                f"{path.relative_to(ROOT)} duplicates the canonical usage-decision contract block"
            )


def test_behavioral_evals_keep_computed_equivalents_unconditionally_non_charge():
    violations = []
    for eval_path in sorted(ROOT.glob("skills/*/evals/evals.json")):
        data = json.loads(eval_path.read_text(encoding="utf-8"))
        for case in data["evals"]:
            for expectation in case["expectations"]:
                normalized = " ".join(expectation.lower().split())
                for pattern in FORBIDDEN_EQUIVALENT_CHARGE_EXCEPTIONS:
                    if pattern.search(normalized):
                        violations.append((data["skill_name"], case["id"], pattern.pattern))
    assert not violations, f"behavioral evals condition equivalent-vs-charge semantics: {violations}"

    usage_case = next(case for case in _eval("job-search-agent")["evals"] if case["id"] == 11)
    expectations = " ".join(usage_case["expectations"]).lower()
    assert "stored 0.063 value byte-for-byte" in expectations
    assert "never describes that computed value as an actual charge" in expectations
    assert "authoritative live account data is unavailable in this scenario" in expectations


def test_t2_2_effect_evals_cover_the_fake_only_red_cases():
    """The runner's per-attempt accounting case left this set with the attempt ledger it graded
    (the 2026-07-30 rewrite counts calls in the run record instead); what the runner's fixtures now
    pin about usage lives in test_runner_eval_fixture_pins_calls_first_context... above. The front
    door's two approved-sentence fixtures went with the same rewrite: the cost facts are stated in
    the agent's own words now, so its first-run fixture pins the ordering instead of the wording."""
    search = _eval("job-search")
    agent = _eval("job-search-agent")

    search_by_id = {case["id"]: case for case in search["evals"]}
    first_run = " ".join(search_by_id[1]["expectations"]).lower()
    assert "before the first search-jobs entry" in first_run
    assert "free monthly calls" in first_run

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
