"""Executable and structural pressure for exact-model repair."""

import json
import os
import pathlib
import re
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]
FAKE_HOST = ROOT / "tests" / "fake-host-capabilities"
BINDING_PATH = pathlib.Path("runs/detail-model-binding.json")
OLD_BINDING_ID = "binding-123e4567-e89b-42d3-a456-426614174000"
INTERNALS = ROOT / "shared" / "references" / "internals.md"
ERRORS = ROOT / "shared" / "references" / "errors.md"
AGENT = ROOT / "skills" / "job-search-agent" / "SKILL.md"
CUSTOMIZATION = ROOT / "skills" / "job-search-agent" / "references" / "customization.md"
SCHEDULING = ROOT / "skills" / "job-search-agent" / "references" / "scheduling-and-consent.md"
RUNNER = ROOT / "skills" / "job-search-run" / "SKILL.md"


def _marked_table(path, marker):
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- exact-model-contract:{re.escape(marker)} -->\n(.*?)\n"
        rf"<!-- /exact-model-contract:{re.escape(marker)} -->",
        text,
        re.DOTALL,
    )
    assert match, f"missing exact-model-contract:{marker} in {path}"
    rows = {}
    for line in match.group(1).splitlines():
        if not line.startswith("|") or set(line.replace("|", "").strip()) <= {"-"}:
            continue
        cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        if cells[0].lower() in {"policy", "situation", "phase", "field"}:
            continue
        rows[cells[0]] = tuple(cells[1:])
    return rows


def _evals(skill):
    path = ROOT / "skills" / skill / "evals" / "evals.json"
    return json.loads(path.read_text(encoding="utf-8"))["evals"]


def _run_host(tmp_path, scenario, *args):
    env = dict(
        os.environ,
        JOBSEARCH_TEST_HOST_SCENARIO=scenario,
        JOBSEARCH_TEST_HOST_LOG=str(tmp_path / "host.jsonl"),
        JOBSEARCH_TEST_HOST_STATE=str(tmp_path / "host-state.json"),
    )
    return subprocess.run(
        [str(FAKE_HOST), *args], capture_output=True, text=True, env=env
    )


def _json_stdout(result):
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def _json_stderr(result):
    assert result.returncode != 0, result.stdout + result.stderr
    return json.loads(result.stderr)


def _seed_repair_state(tmp_path):
    workspace = tmp_path / "workspace"
    runs = workspace / "runs"
    runs.mkdir(parents=True)
    config = (
        '# repair-comment-sentinel\nversion: 2\nqueries:\n'
        '  - { id: "ai", keywords: "AI engineer", enabled: true }\n'
        'search:\n  detail_model: "fake-review-001"\n'
        'schedule:\n  frequency: "daily"\nunrelated: "keep-exact"\n'
    ).encode()
    binding = (
        json.dumps(
            {
                "version": 1,
                "binding_id": OLD_BINDING_ID,
                "detail_model": "fake-review-001",
                "detail_model_origin": "configured_auto",
                "bound_at": "2026-07-16T12:00:00+00:00",
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    registry_path = tmp_path / "registry.json"
    registry = (
        json.dumps(
            {
                "version": 1,
                "active_workspace": str(workspace.resolve()),
                "unrelated_registry": {"keep": True},
                "scheduling": {
                    "installed": True,
                    "verified": False,
                    "mechanism": "fake-unattended",
                    "scheduler_id": "repair-job",
                    "set_at": "2026-07-16T11:00:00+00:00",
                    "primary_model": "fake-primary-001",
                    "primary_model_origin": "session_inheritance",
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    (workspace / "config.yaml").write_bytes(config)
    (workspace / BINDING_PATH).write_bytes(binding)
    registry_path.write_bytes(registry)
    state_path = tmp_path / "host-state.json"
    state_path.write_text(
        json.dumps(
            {
                "jobs": {
                    "repair-job": {
                        "state": "disabled",
                        "verified": False,
                        "primary_model": "fake-primary-001",
                        "primary_model_origin": "session_inheritance",
                        "unrelated_job": "keep-exact",
                    }
                }
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return workspace, registry_path, config, binding, registry


def _seed_unscheduled_detail_state(tmp_path):
    workspace, registry_path, config, binding, _ = _seed_repair_state(tmp_path)
    registry_path.unlink()
    (tmp_path / "host-state.json").write_text(
        json.dumps({"jobs": {}}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert not registry_path.exists()
    return workspace, registry_path, config, binding


def _begin_and_authorize(
    tmp_path,
    scenario,
    workspace,
    registry_path,
    primary,
    primary_origin,
    detail,
    write_detail,
):
    proposal = _json_stdout(
        _run_host(
            tmp_path,
            scenario,
            "begin-repair",
            str(workspace),
            str(registry_path),
            "repair-job",
            primary,
            primary_origin,
            detail,
            "true" if write_detail else "false",
        )
    )
    assert proposal["confirmation_required"] is True
    assert proposal["canary_action"] == "metered_canary_retry_or_repair"
    assert proposal["confirmation_count"] == 0
    authorized = _json_stdout(
        _run_host(
            tmp_path,
            scenario,
            "authorize-repair",
            str(workspace),
            "repair-job",
        )
    )
    assert authorized == {"confirmation_count": 1, "scope": "one_repair_canary"}
    return proposal


def test_repair_candidate_defaults_only_unavailable_slots(tmp_path):
    primary = _json_stdout(
        _run_host(
            tmp_path,
            "expired-primary",
            "repair-candidate",
            "fake-primary-001",
            "user_override",
            "fake-review-001",
            "repair",
        )
    )
    assert primary == {
        "primary": {
            "after": "fake-primary-002",
            "before": "fake-primary-001",
            "changed": True,
            "origin": "repair_session",
        },
        "detail": {
            "after": "fake-review-001",
            "before": "fake-review-001",
            "changed": False,
            "origin": "repair",
            "write_required": False,
        },
    }

    detail = _json_stdout(
        _run_host(
            tmp_path,
            "expired-detail",
            "repair-candidate",
            "fake-primary-001",
            "repair_session",
            "fake-review-001",
            "configured_user",
        )
    )
    assert detail == {
        "primary": {
            "after": "fake-primary-001",
            "before": "fake-primary-001",
            "changed": False,
            "origin": "repair_session",
        },
        "detail": {
            "after": "fake-review-002",
            "before": "fake-review-001",
            "changed": True,
            "origin": "repair",
            "write_required": True,
        },
    }


def test_repair_candidate_requires_exact_primary_when_session_model_unknown(tmp_path):
    result = _run_host(
        tmp_path,
        "expired-primary-session-unknown",
        "repair-candidate",
        "fake-primary-001",
        "session_inheritance",
        "fake-review-001",
        "configured_auto",
    )
    assert _json_stderr(result) == {
        "error": "repair_primary_exact_selection_required"
    }


def test_exact_available_user_overrides_win_and_inexact_ids_are_rejected(tmp_path):
    override = _json_stdout(
        _run_host(
            tmp_path,
            "both-expired",
            "repair-candidate",
            "fake-primary-001",
            "session_inheritance",
            "fake-review-001",
            "configured_auto",
            "fake-user-primary-001",
            "fake-capable-002",
        )
    )
    assert override["primary"] == {
        "after": "fake-user-primary-001",
        "before": "fake-primary-001",
        "changed": True,
        "origin": "user_override",
    }
    assert override["detail"] == {
        "after": "fake-capable-002",
        "before": "fake-review-001",
        "changed": True,
        "origin": "repair",
        "write_required": True,
    }

    for invalid, expected in (
        ("fake-missing-001", "repair_model_unavailable"),
        ("fake-review", "repair_model_ambiguous"),
    ):
        result = _run_host(
            tmp_path,
            "both-expired",
            "repair-candidate",
            "fake-primary-001",
            "session_inheritance",
            "fake-review-001",
            "configured_auto",
            invalid,
            "fake-review-002",
        )
        assert _json_stderr(result) == {"error": expected, "selection": invalid}


def test_same_id_primary_override_rebinds_user_origin_and_is_accepted(tmp_path):
    candidate = _json_stdout(
        _run_host(
            tmp_path,
            "expired-detail",
            "repair-candidate",
            "fake-primary-001",
            "session_inheritance",
            "fake-review-001",
            "configured_auto",
            "fake-primary-001",
        )
    )
    assert candidate["primary"] == {
        "after": "fake-primary-001",
        "before": "fake-primary-001",
        "changed": False,
        "origin": "user_override",
    }
    workspace, registry_path, _, _, _ = _seed_repair_state(tmp_path)
    proposal = _json_stdout(
        _run_host(
            tmp_path,
            "expired-detail",
            "begin-repair",
            str(workspace),
            str(registry_path),
            "repair-job",
            "fake-primary-001",
            "user_override",
            "fake-review-002",
            "true",
        )
    )
    assert proposal["primary"]["origin_after"] == "user_override"


def test_primary_only_repair_preserves_config_and_sidecar_bytes(tmp_path):
    workspace, registry_path, config_before, binding_before, _ = _seed_repair_state(
        tmp_path
    )
    proposal = _begin_and_authorize(
        tmp_path,
        "expired-primary",
        workspace,
        registry_path,
        "fake-primary-002",
        "repair_session",
        "fake-review-001",
        False,
    )
    assert proposal["primary"] == {
        "after": "fake-primary-002",
        "before": "fake-primary-001",
        "origin_after": "repair_session",
        "origin_before": "session_inheritance",
    }
    assert proposal["detail"] == {
        "after": "fake-review-001",
        "before": "fake-review-001",
        "write_required": False,
    }
    _json_stdout(
        _run_host(
            tmp_path,
            "expired-primary",
            "activate-repair",
            str(workspace),
            str(registry_path),
            "repair-job",
        )
    )
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["scheduling"]["verified"] is False
    assert registry["scheduling"]["primary_model"] == "fake-primary-002"
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    assert state["jobs"]["repair-job"]["state"] == "disabled"
    assert state["jobs"]["repair-job"]["verified"] is False


def test_unscheduled_detail_repair_is_neutral_atomic_and_has_no_canary(tmp_path):
    workspace, registry_path, config_before, binding_before = (
        _seed_unscheduled_detail_state(tmp_path)
    )
    repaired = _json_stdout(
        _run_host(
            tmp_path,
            "expired-detail",
            "repair-unscheduled-detail",
            str(workspace),
            str(registry_path),
            "fake-review-002",
        )
    )
    assert repaired == {
        "canary_required": False,
        "confirmation_required": False,
        "detail": {
            "after": "fake-review-002",
            "before": "fake-review-001",
            "origin": "repair",
        },
        "state": "repaired",
    }
    assert (workspace / "config.yaml").read_bytes() != config_before
    assert b'# repair-comment-sentinel' in (workspace / "config.yaml").read_bytes()
    binding = json.loads((workspace / BINDING_PATH).read_text(encoding="utf-8"))
    assert (workspace / BINDING_PATH).read_bytes() != binding_before
    assert binding["detail_model"] == "fake-review-002"
    assert binding["detail_model_origin"] == "repair"
    log = [
        json.loads(line)
        for line in (tmp_path / "host.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [(row["operation"], row["outcome"]) for row in log] == [
        ("repair-unscheduled-detail", "atomic_pair_repaired")
    ]
    assert not registry_path.exists()
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    assert state["jobs"] == {}


def test_unscheduled_detail_repair_partial_write_restores_exact_pair(tmp_path):
    workspace, registry_path, config_before, binding_before = (
        _seed_unscheduled_detail_state(tmp_path)
    )
    failed = _run_host(
        tmp_path,
        "repair-unscheduled-partial-failure",
        "repair-unscheduled-detail",
        str(workspace),
        str(registry_path),
        "fake-review-002",
    )
    assert _json_stderr(failed) == {
        "error": "repair_activation_failed",
        "config": "restored_exact",
        "sidecar": "restored_exact",
    }
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before


def test_unscheduled_detail_operation_rejects_an_installed_schedule(tmp_path):
    workspace, registry_path, config_before, binding_before, _ = _seed_repair_state(
        tmp_path
    )
    rejected = _run_host(
        tmp_path,
        "expired-detail",
        "repair-unscheduled-detail",
        str(workspace),
        str(registry_path),
        "fake-review-002",
    )
    assert _json_stderr(rejected) == {"error": "scheduled_repair_required"}
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before


def test_detail_repair_writes_fresh_matching_binding_even_for_same_exact_id(tmp_path):
    workspace, registry_path, config_before, binding_before, _ = _seed_repair_state(
        tmp_path
    )
    proposal = _begin_and_authorize(
        tmp_path,
        "happy",
        workspace,
        registry_path,
        "fake-primary-001",
        "session_inheritance",
        "fake-review-001",
        True,
    )
    assert proposal["detail"]["before"] == proposal["detail"]["after"]
    assert proposal["detail"]["write_required"] is True
    _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "activate-repair",
            str(workspace),
            str(registry_path),
            "repair-job",
        )
    )
    assert (workspace / "config.yaml").read_bytes() == config_before
    binding_after = (workspace / BINDING_PATH).read_bytes()
    assert binding_after != binding_before
    binding = json.loads(binding_after)
    assert binding["detail_model"] == "fake-review-001"
    assert binding["detail_model_origin"] == "repair"
    assert binding["binding_id"] != OLD_BINDING_ID


def test_failed_repair_canary_rolls_back_every_surface_and_needs_fresh_consent(
    tmp_path,
):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    _begin_and_authorize(
        tmp_path,
        "repair-canary-failure",
        workspace,
        registry_path,
        "fake-primary-002",
        "repair_session",
        "fake-review-002",
        True,
    )
    _json_stdout(
        _run_host(
            tmp_path,
            "repair-canary-failure",
            "activate-repair",
            str(workspace),
            str(registry_path),
            "repair-job",
        )
    )
    failed = _run_host(
        tmp_path,
        "repair-canary-failure",
        "repair-canary",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(failed) == {
        "error": "repair_canary_failed",
        "registry": "restored_exact",
        "config": "restored_exact",
        "sidecar": "restored_exact",
        "job": "restored_exact",
        "verified": False,
    }
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert registry_path.read_bytes() == registry_before
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    assert state["jobs"]["repair-job"]["primary_model"] == "fake-primary-001"
    assert state["jobs"]["repair-job"]["state"] == "disabled"

    retry = _run_host(
        tmp_path,
        "happy",
        "repair-canary",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(retry) == {"error": "fresh_repair_confirmation_required"}


def test_green_real_path_canary_is_the_only_commit_and_restores_verified_status(
    tmp_path,
):
    workspace, registry_path, _, _, _ = _seed_repair_state(tmp_path)
    _begin_and_authorize(
        tmp_path,
        "both-expired",
        workspace,
        registry_path,
        "fake-primary-002",
        "repair_session",
        "fake-review-002",
        True,
    )
    _json_stdout(
        _run_host(
            tmp_path,
            "both-expired",
            "activate-repair",
            str(workspace),
            str(registry_path),
            "repair-job",
        )
    )
    before_canary = json.loads(registry_path.read_text(encoding="utf-8"))
    assert before_canary["scheduling"]["verified"] is False

    committed = _json_stdout(
        _run_host(
            tmp_path,
            "both-expired",
            "repair-canary",
            str(workspace),
            str(registry_path),
            "repair-job",
        )
    )
    assert committed == {
        "canary_path": "simulated_registered_job_real_path_input",
        "committed": True,
        "fixture_scope": "t3_3_not_scheduler_fidelity",
        "run_health": "healthy",
        "verified": True,
    }
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["scheduling"]["primary_model"] == "fake-primary-002"
    assert registry["scheduling"]["primary_model_origin"] == "repair_session"
    assert registry["scheduling"]["verified"] is True
    binding = json.loads((workspace / BINDING_PATH).read_text(encoding="utf-8"))
    assert binding["detail_model"] == "fake-review-002"
    assert binding["detail_model_origin"] == "repair"
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    assert state["jobs"]["repair-job"]["state"] == "enabled"
    assert state["jobs"]["repair-job"]["verified"] is True


def test_repair_allows_only_one_scoped_confirmation(tmp_path):
    workspace, registry_path, _, _, _ = _seed_repair_state(tmp_path)
    _begin_and_authorize(
        tmp_path,
        "expired-primary",
        workspace,
        registry_path,
        "fake-primary-002",
        "repair_session",
        "fake-review-001",
        False,
    )
    duplicate = _run_host(
        tmp_path,
        "expired-primary",
        "authorize-repair",
        str(workspace),
        "repair-job",
    )
    assert _json_stderr(duplicate) == {"error": "duplicate_repair_confirmation"}


def test_repair_transaction_rejects_primary_origin_drift(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    for scenario, primary, origin in (
        ("happy", "fake-primary-001", "repair_session"),
        ("expired-primary", "fake-primary-002", "session_inheritance"),
    ):
        rejected = _run_host(
            tmp_path,
            scenario,
            "begin-repair",
            str(workspace),
            str(registry_path),
            "repair-job",
            primary,
            origin,
            "fake-review-001",
            "false",
        )
        assert _json_stderr(rejected) == {"error": "invalid_repair_request"}
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert registry_path.read_bytes() == registry_before


def test_partial_repair_activation_rolls_back_before_any_canary(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    _begin_and_authorize(
        tmp_path,
        "repair-partial-activation-failure",
        workspace,
        registry_path,
        "fake-primary-002",
        "repair_session",
        "fake-review-002",
        True,
    )
    failed = _run_host(
        tmp_path,
        "repair-partial-activation-failure",
        "activate-repair",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(failed) == {
        "error": "repair_activation_failed",
        "registry": "restored_exact",
        "config": "restored_exact",
        "sidecar": "restored_exact",
        "job": "restored_exact",
        "verified": False,
    }
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert registry_path.read_bytes() == registry_before
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    assert state["jobs"]["repair-job"]["state"] == "disabled"
    assert "repair_transactions" not in state or not state["repair_transactions"]


def test_invalid_staged_repair_evidence_restores_exact_snapshot(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    _begin_and_authorize(
        tmp_path,
        "expired-detail",
        workspace,
        registry_path,
        "fake-primary-001",
        "session_inheritance",
        "fake-review-002",
        True,
    )
    _json_stdout(
        _run_host(
            tmp_path,
            "expired-detail",
            "activate-repair",
            str(workspace),
            str(registry_path),
            "repair-job",
        )
    )
    (workspace / "config.yaml").write_text(
        'version: 2\nsearch:\n  detail_model: "tampered-model"\n',
        encoding="utf-8",
    )
    failed = _run_host(
        tmp_path,
        "expired-detail",
        "repair-canary",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(failed) == {
        "error": "repair_canary_evidence_invalid",
        "registry": "restored_exact",
        "config": "restored_exact",
        "sidecar": "restored_exact",
        "job": "restored_exact",
        "verified": False,
    }
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert registry_path.read_bytes() == registry_before


def test_headless_expiry_and_auto_substitution_bait_block_without_dispatch(tmp_path):
    for scenario, slots in (
        ("expired-primary", ["primary"]),
        ("expired-detail", ["detail"]),
        ("both-expired", ["primary", "detail"]),
        ("auto-substitution-bait", ["primary", "detail"]),
    ):
        case_dir = tmp_path / scenario
        case_dir.mkdir()
        blocked = _run_host(
            case_dir,
            scenario,
            "headless-model-check",
            "fake-primary-001",
            "fake-review-001",
        )
        assert _json_stderr(blocked) == {
            "error": "exact_model_repair_required",
            "slots": slots,
            "substitution_attempted": False,
        }
        log = [
            json.loads(line)
            for line in (case_dir / "host.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert [entry["operation"] for entry in log] == ["headless-model-check"]
        assert log[0]["outcome"] == "blocked_no_substitute"


def test_exact_model_repair_contract_pins_defaults_transaction_and_consent():
    assert _marked_table(INTERNALS, "exact-model-repair-candidate") == {
        "valid_unchanged_slot": ("preserve_exact_value_and_state",),
        "primary_unavailable_default": (
            "repair_session_exact_model_origin_repair_session",
        ),
        "primary_repair_session_unknown": (
            "require_exact_available_user_selection",
        ),
        "detail_unavailable_default": (
            "least_powerful_available_adequate_judgment_model_origin_repair",
        ),
        "user_override": ("exact_available_identifier_only",),
        "same_id_primary_user_override": ("allowed_origin_user_override",),
        "unknown_unavailable_or_ambiguous": ("reject",),
    }
    assert _marked_table(INTERNALS, "exact-model-repair-transaction") == {
        "snapshot": (
            "exact_affected_config_sidecar_and_when_present_registry_scheduler_verification_state",
        ),
        "primary_only": ("preserve_valid_config_and_sidecar_bytes",),
        "detail_write": ("canonical_fresh_binding_even_when_literal_is_unchanged",),
        "schedule_exists": ("one_confirmation_and_green_real_path_canary_required",),
        "no_schedule_detail_repair": ("atomic_config_and_fresh_binding_pair_no_canary",),
        "no_schedule_confirmation": ("explicit_repair_request_is_neutral_authority",),
        "during_repair": ("scheduler_disabled_and_registry_unverified",),
        "setup_or_canary_failure": (
            "restore_exact_prior_transaction_state_no_proposed_model_active",
        ),
        "green_real_path_canary": ("only_commit_enable_and_verify",),
        "scheduled_failed_retry": (
            "fresh_calls_first_context_and_scoped_confirmation",
        ),
        "unscheduled_failed_retry": (
            "fresh_explicit_request_no_calls_preview_or_confirmation",
        ),
        "fixture_scope": ("t3_3_only_not_general_scheduler_fidelity",),
    }
    assert _marked_table(INTERNALS, "exact-model-repair-confirmation") == {
        "applies": ("scheduled_repair",),
        "no_schedule": ("not_applicable_explicit_request_is_authority",),
        "count": ("one",),
        "model_identity": ("neutral",),
        "metered_action": ("repair_canary",),
        "primary_and_detail": ("exact_before_after_including_unchanged_slots",),
        "state_effects": (
            "scheduler_config_binding_machine_change_removal_and_rollback",
        ),
        "canary_context": ("canonical_calls_first_preview",),
    }


def test_model_repair_user_rendering_is_complete_and_conversational():
    assert _marked_table(ERRORS, "model-repair-rendering") == {
        "initial_binding_failure": ("exact_unavailable_or_refused_slot",),
        "repair_transaction_failure": ("observed_setup_activation_or_canary_phase",),
        "safe_state": ("what_was_preserved_or_restored",),
        "next_step": ("interactive_exact_model_repair",),
        "exact_fix": ("conversational_available_model_selection_or_default",),
        "raw_internal_class": ("never_show",),
        "invented_e_code": ("never_show",),
    }
    rendered = re.sub(r"\s+", " ", ERRORS.read_text(encoding="utf-8").lower())
    assert "say “repair the job-search models”" in rendered
    assert "repair setup, activation, or canary failed" in rendered


def test_agent_and_runner_skills_route_through_one_canonical_repair_flow():
    agent = AGENT.read_text(encoding="utf-8").lower()
    customization = CUSTOMIZATION.read_text(encoding="utf-8").lower()
    scheduling = SCHEDULING.read_text(encoding="utf-8").lower()
    runner = RUNNER.read_text(encoding="utf-8").lower()
    assert "exact-model repair" in agent
    assert "exact-model-repair-candidate" in customization
    assert "exact-model-repair-transaction" in customization
    assert "without a schedule" in customization
    assert "no extra confirmation or canary" in customization
    assert "one scoped confirmation" in scheduling
    assert "exact-model-repair-confirmation" in scheduling
    assert "disabled and unverified" in scheduling
    assert "only a green real scheduled-path canary" in scheduling
    assert "fresh calls-first context" in scheduling
    assert "model-repair-rendering" in scheduling
    assert "headless" in runner
    assert "exact-model repair" in runner
    assert "never substitute" in runner
    assert "model-repair-rendering" in runner


def test_exact_model_repair_eval_matrix_is_structural_and_executable():
    home = _evals("job-search")
    agent = _evals("job-search-agent")
    runner = _evals("job-search-run")
    assert [case["id"] for case in home[-5:]] == [25, 26, 27, 28, 29]
    assert [case["id"] for case in agent[-6:]] == [15, 16, 17, 18, 19, 20]
    assert [case["id"] for case in runner[-4:]] == [42, 43, 44, 45]
    home_matrix = " ".join(case["scenario"].lower() for case in home[-5:])
    agent_matrix = " ".join(case["scenario"].lower() for case in agent[-6:])
    runner_matrix = " ".join(case["scenario"].lower() for case in runner[-4:])
    for phrase in (
        "primary-only",
        "detail-only",
        "both expired",
        "exact override",
        "rollback",
    ):
        assert phrase in home_matrix
    for phrase in (
        "one confirmation",
        "same-id detail rewrite",
        "green canary",
        "partial activation rollback",
        "unscheduled detail repair",
    ):
        assert phrase in agent_matrix
    for phrase in (
        "expired primary",
        "expired detail",
        "both expired",
        "substitution bait",
    ):
        assert phrase in runner_matrix
    override_case = next(case for case in home if case["id"] == 28)
    override_text = " ".join(
        [override_case["prompt"], *override_case["expectations"]]
    ).lower()
    assert "same exact primary" in override_text
    assert "alternate prior origins" in override_text
    assert all(case.get("coverage_kind") == "executable_fixture" for case in home[-5:])
    assert all(case.get("coverage_kind") == "executable_fixture" for case in agent[-6:])
    assert all(case.get("coverage_kind") == "executable_fixture" for case in runner[-4:])
