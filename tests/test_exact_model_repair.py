"""Executable and structural pressure for exact-model repair."""

import base64
import json
import os
import pathlib
import re
import subprocess

import pytest


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
        JOBSEARCH_OS_REGISTRY=str(tmp_path / "registry.json"),
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


def _issue_candidate(
    tmp_path,
    scenario,
    workspace,
    primary_override="-",
    detail_override="-",
):
    return _json_stdout(
        _run_host(
            tmp_path,
            scenario,
            "repair-candidate",
            str(workspace),
            "repair-job",
            primary_override,
            detail_override,
        )
    )


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
    primary_override="-",
    detail_override="-",
):
    candidate = _issue_candidate(
        tmp_path,
        scenario,
        workspace,
        primary_override,
        detail_override,
    )
    receipt_id = candidate["receipt_id"]
    authorized = _json_stdout(
        _run_host(
            tmp_path,
            scenario,
            "authorize-repair",
            str(workspace),
            receipt_id,
        )
    )
    assert authorized == {
        "confirmation_count": 1,
        "receipt_id": receipt_id,
        "scope": "exact_candidate_and_one_repair_canary",
    }
    begun = _json_stdout(
        _run_host(
            tmp_path,
            scenario,
            "begin-repair",
            str(workspace),
            receipt_id,
        )
    )
    assert begun == {
        "confirmation_count": 1,
        "receipt_id": receipt_id,
        "schedule_during_repair": "disabled_unverified",
        "stage": "authorized_candidate_snapshotted",
    }
    return candidate


def test_repair_candidate_defaults_only_unavailable_slots(tmp_path):
    primary_dir = tmp_path / "primary"
    primary_dir.mkdir()
    primary_workspace, primary_registry, _, _, _ = _seed_repair_state(primary_dir)
    registry = json.loads(primary_registry.read_text(encoding="utf-8"))
    registry["scheduling"]["primary_model_origin"] = "user_override"
    primary_registry.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    state_path = primary_dir / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["jobs"]["repair-job"]["primary_model_origin"] = "user_override"
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sidecar_path = primary_workspace / BINDING_PATH
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["detail_model_origin"] = "repair"
    sidecar_path.write_text(json.dumps(sidecar, sort_keys=True) + "\n", encoding="utf-8")
    primary = _issue_candidate(primary_dir, "expired-primary", primary_workspace)
    assert primary["primary"] == {
        "after": "fake-primary-002",
        "before": "fake-primary-001",
        "changed": True,
        "origin_after": "repair_session",
        "origin_before": "user_override",
    }
    assert primary["detail"] == {
        "after": "fake-review-001",
        "before": "fake-review-001",
        "changed": False,
        "origin_after": "repair",
        "origin_before": "repair",
        "write_required": False,
    }

    detail_dir = tmp_path / "detail"
    detail_dir.mkdir()
    detail_workspace, detail_registry, _, _, _ = _seed_repair_state(detail_dir)
    registry = json.loads(detail_registry.read_text(encoding="utf-8"))
    registry["scheduling"]["primary_model_origin"] = "repair_session"
    detail_registry.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    state_path = detail_dir / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["jobs"]["repair-job"]["primary_model_origin"] = "repair_session"
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sidecar_path = detail_workspace / BINDING_PATH
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["detail_model_origin"] = "configured_user"
    sidecar_path.write_text(json.dumps(sidecar, sort_keys=True) + "\n", encoding="utf-8")
    detail = _issue_candidate(detail_dir, "expired-detail", detail_workspace)
    assert detail["primary"] == {
        "after": "fake-primary-001",
        "before": "fake-primary-001",
        "changed": False,
        "origin_after": "repair_session",
        "origin_before": "repair_session",
    }
    assert detail["detail"] == {
        "after": "fake-review-002",
        "before": "fake-review-001",
        "changed": True,
        "origin_after": "repair",
        "origin_before": "configured_user",
        "write_required": True,
    }


def test_repair_candidate_requires_exact_primary_when_session_model_unknown(tmp_path):
    workspace, _, _, _, _ = _seed_repair_state(tmp_path)
    result = _run_host(
        tmp_path,
        "expired-primary-session-unknown",
        "repair-candidate",
        str(workspace),
        "repair-job",
        "-",
        "-",
    )
    assert _json_stderr(result) == {
        "error": "repair_primary_exact_selection_required"
    }


def test_exact_available_user_overrides_win_and_inexact_ids_are_rejected(tmp_path):
    workspace, _, _, _, _ = _seed_repair_state(tmp_path)
    override = _issue_candidate(
        tmp_path,
        "both-expired",
        workspace,
        "fake-user-primary-001",
        "fake-capable-002",
    )
    assert override["primary"] == {
        "after": "fake-user-primary-001",
        "before": "fake-primary-001",
        "changed": True,
        "origin_after": "user_override",
        "origin_before": "session_inheritance",
    }
    assert override["detail"] == {
        "after": "fake-capable-002",
        "before": "fake-review-001",
        "changed": True,
        "origin_after": "repair",
        "origin_before": "configured_auto",
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
            str(workspace),
            "repair-job",
            invalid,
            "fake-review-002",
        )
        assert _json_stderr(result) == {"error": expected, "selection": invalid}


def test_same_id_primary_override_rebinds_user_origin_and_is_accepted(tmp_path):
    workspace, _, _, _, _ = _seed_repair_state(tmp_path)
    candidate = _issue_candidate(
        tmp_path,
        "expired-detail",
        workspace,
        "fake-primary-001",
    )
    assert candidate["primary"] == {
        "after": "fake-primary-001",
        "before": "fake-primary-001",
        "changed": False,
        "origin_after": "user_override",
        "origin_before": "session_inheritance",
    }
    assert candidate["confirmation"]["effects"]["scheduler"] == (
        "update_exact_primary_keep_disabled_unverified"
    )
    receipt_id = candidate["receipt_id"]
    _json_stdout(
        _run_host(
            tmp_path,
            "expired-detail",
            "authorize-repair",
            str(workspace),
            receipt_id,
        )
    )
    _json_stdout(
        _run_host(
            tmp_path,
            "expired-detail",
            "begin-repair",
            str(workspace),
            receipt_id,
        )
    )
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    transaction = state["repair_transactions"][str(workspace.resolve())]
    assert transaction["primary_origin_after"] == "user_override"


def test_begin_repair_rejects_direct_models_without_candidate_receipt(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    direct = _run_host(
        tmp_path,
        "expired-detail",
        "begin-repair",
        str(workspace),
        str(registry_path),
        "repair-job",
        "fake-user-primary-001",
        "user_override",
        "fake-review-002",
        "true",
    )
    assert _json_stderr(direct) == {"error": "repair_candidate_receipt_required"}
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert registry_path.read_bytes() == registry_before


def test_candidate_receipt_owns_exact_preview_and_preserves_valid_slots(tmp_path):
    workspace, _, _, _, _ = _seed_repair_state(tmp_path)
    candidate = _issue_candidate(tmp_path, "expired-detail", workspace)
    assert candidate == {
        "receipt_id": "repair-receipt-000001",
        "receipt_integrity": "sha256_deterministic_tamper_detection_only",
        "primary": {
            "before": "fake-primary-001",
            "after": "fake-primary-001",
            "changed": False,
            "origin_before": "session_inheritance",
            "origin_after": "session_inheritance",
        },
        "detail": {
            "before": "fake-review-001",
            "after": "fake-review-002",
            "changed": True,
            "origin_before": "configured_auto",
            "origin_after": "repair",
            "write_required": True,
        },
        "confirmation": {
            "required": True,
            "count": 0,
            "scope": "exact_candidate_machine_change_and_one_canary",
            "canary_count": 1,
            "usage_context": {
                "action": "metered_canary_retry_or_repair",
                "known_first_page_calls": 2,
                "baseline_formula": "1_enabled_query*2_enabled_sources",
                "uncertain_additions": [
                    "continuation_pages",
                    "full_posting_detail_reads",
                    "metered_failures_and_retries",
                ],
                "recurring_multiplier": "approved_canary_attempt_only",
            },
            "effects": {
                "config": "replace_exact_detail_model",
                "binding": "write_fresh_canonical_repair_binding",
                "scheduler": "preserve_exact_primary_keep_disabled_unverified",
                "machine_change": "update_existing_registered_job_without_enabling",
                "removal": "stop_or_remove_job_and_clear_scheduling_marker",
                "rollback": "restore_exact_config_sidecar_registry_and_job_snapshot",
            },
        },
    }


def test_authorized_candidate_receipt_tamper_is_consumed_before_begin(tmp_path):
    workspace, _, config_before, binding_before, registry_before = _seed_repair_state(
        tmp_path
    )
    candidate = _issue_candidate(tmp_path, "both-expired", workspace)
    receipt_id = candidate["receipt_id"]
    authorized = _json_stdout(
        _run_host(
            tmp_path,
            "both-expired",
            "authorize-repair",
            str(workspace),
            receipt_id,
        )
    )
    assert authorized == {
        "confirmation_count": 1,
        "receipt_id": receipt_id,
        "scope": "exact_candidate_and_one_repair_canary",
    }
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["repair_candidate_receipts"][receipt_id]["payload"]["primary_after"] = (
        "fake-user-primary-001"
    )
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rejected = _run_host(
        tmp_path,
        "both-expired",
        "begin-repair",
        str(workspace),
        receipt_id,
    )
    assert _json_stderr(rejected) == {"error": "repair_candidate_receipt_invalid"}
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert (tmp_path / "registry.json").read_bytes() == registry_before
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert receipt_id not in state.get("repair_candidate_receipts", {})


def test_authorized_candidate_receipt_staleness_requires_recompute_and_reconfirm(
    tmp_path,
):
    workspace, _, config_before, _, _ = _seed_repair_state(tmp_path)
    candidate = _issue_candidate(tmp_path, "expired-primary", workspace)
    receipt_id = candidate["receipt_id"]
    _json_stdout(
        _run_host(
            tmp_path,
            "expired-primary",
            "authorize-repair",
            str(workspace),
            receipt_id,
        )
    )
    (workspace / "config.yaml").write_bytes(config_before + b"# external-drift\n")
    stale = _run_host(
        tmp_path,
        "expired-primary",
        "begin-repair",
        str(workspace),
        receipt_id,
    )
    assert _json_stderr(stale) == {"error": "repair_candidate_receipt_stale"}
    (workspace / "config.yaml").write_bytes(config_before)
    reused = _run_host(
        tmp_path,
        "expired-primary",
        "begin-repair",
        str(workspace),
        receipt_id,
    )
    assert _json_stderr(reused) == {"error": "repair_candidate_receipt_required"}


def test_authorized_candidate_receipt_missing_owned_registry_is_consumed(tmp_path):
    workspace, _, _, _, _ = _seed_repair_state(tmp_path)
    candidate = _issue_candidate(tmp_path, "expired-detail", workspace)
    receipt_id = candidate["receipt_id"]
    _json_stdout(
        _run_host(
            tmp_path,
            "expired-detail",
            "authorize-repair",
            str(workspace),
            receipt_id,
        )
    )
    env = dict(
        os.environ,
        JOBSEARCH_TEST_HOST_SCENARIO="expired-detail",
        JOBSEARCH_TEST_HOST_LOG=str(tmp_path / "host.jsonl"),
        JOBSEARCH_TEST_HOST_STATE=str(tmp_path / "host-state.json"),
    )
    env.pop("JOBSEARCH_OS_REGISTRY", None)
    missing = subprocess.run(
        [str(FAKE_HOST), "begin-repair", str(workspace), receipt_id],
        capture_output=True,
        text=True,
        env=env,
    )
    assert _json_stderr(missing) == {"error": "repair_candidate_receipt_invalid"}
    reused = _run_host(
        tmp_path,
        "expired-detail",
        "begin-repair",
        str(workspace),
        receipt_id,
    )
    assert _json_stderr(reused) == {"error": "repair_candidate_receipt_required"}


def test_confirmed_receipt_envelope_cannot_be_replayed_under_a_new_key(tmp_path):
    workspace, registry_path, config_before, _, _ = _seed_repair_state(tmp_path)
    candidate = _issue_candidate(tmp_path, "expired-primary", workspace)
    receipt_id = candidate["receipt_id"]
    _json_stdout(
        _run_host(
            tmp_path,
            "expired-primary",
            "authorize-repair",
            str(workspace),
            receipt_id,
        )
    )
    cloned_id = "repair-receipt-999999"
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["repair_candidate_receipts"][cloned_id] = json.loads(
        json.dumps(state["repair_candidate_receipts"][receipt_id])
    )
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _json_stdout(
        _run_host(
            tmp_path,
            "expired-primary",
            "begin-repair",
            str(workspace),
            receipt_id,
        )
    )
    (workspace / "config.yaml").write_bytes(config_before + b"# external-drift\n")
    failed = _run_host(
        tmp_path,
        "expired-primary",
        "activate-repair",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(failed)["error"] == "repair_baseline_changed"
    replayed = _run_host(
        tmp_path,
        "expired-primary",
        "begin-repair",
        str(workspace),
        cloned_id,
    )
    assert _json_stderr(replayed) == {"error": "repair_candidate_receipt_invalid"}
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert cloned_id not in state.get("repair_candidate_receipts", {})


def test_primary_only_repair_preserves_config_and_sidecar_bytes(tmp_path):
    workspace, registry_path, config_before, binding_before, _ = _seed_repair_state(
        tmp_path
    )
    proposal = _begin_and_authorize(
        tmp_path,
        "expired-primary",
        workspace,
    )
    assert proposal["primary"] == {
        "after": "fake-primary-002",
        "before": "fake-primary-001",
        "changed": True,
        "origin_after": "repair_session",
        "origin_before": "session_inheritance",
    }
    assert proposal["detail"] == {
        "after": "fake-review-001",
        "before": "fake-review-001",
        "changed": False,
        "origin_after": "configured_auto",
        "origin_before": "configured_auto",
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
        "fake-review-002",
    )
    assert _json_stderr(rejected) == {"error": "scheduled_repair_required"}
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before


def test_unscheduled_detail_repair_rejects_caller_registry_path_injection(tmp_path):
    workspace, registry_path, config_before, binding_before = (
        _seed_unscheduled_detail_state(tmp_path)
    )
    alternate = tmp_path / "caller-selected-registry.json"
    injected = _run_host(
        tmp_path,
        "expired-detail",
        "repair-unscheduled-detail",
        str(workspace),
        str(alternate),
        "fake-review-002",
    )
    assert _json_stderr(injected) == {"error": "invalid_repair_request"}
    assert not alternate.exists()
    assert not registry_path.exists()
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before


def test_unscheduled_detail_repair_requires_owned_registry_location(tmp_path):
    workspace, registry_path, config_before, binding_before = (
        _seed_unscheduled_detail_state(tmp_path)
    )
    env = dict(
        os.environ,
        JOBSEARCH_TEST_HOST_SCENARIO="expired-detail",
        JOBSEARCH_TEST_HOST_LOG=str(tmp_path / "host.jsonl"),
        JOBSEARCH_TEST_HOST_STATE=str(tmp_path / "host-state.json"),
    )
    env.pop("JOBSEARCH_OS_REGISTRY", None)
    missing = subprocess.run(
        [
            str(FAKE_HOST),
            "repair-unscheduled-detail",
            str(workspace),
            "fake-review-002",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert _json_stderr(missing) == {"error": "missing_test_registry_path"}
    assert not registry_path.exists()
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before


def test_unscheduled_detail_repair_fails_closed_on_ambiguous_scheduling_state(tmp_path):
    for name, scheduling in (
        ("non_boolean_installed", {"installed": 1, "scheduler_id": "repair-job"}),
        ("non_mapping_scheduling", []),
        (
            "uninstalled_with_active_fields",
            {
                "installed": False,
                "mechanism": "fake-unattended",
                "set_at": None,
                "primary_model": "fake-primary-001",
                "primary_model_origin": None,
            },
        ),
        (
            "uninstalled_with_stale_scheduler_evidence",
            {
                "installed": False,
                "mechanism": None,
                "set_at": None,
                "primary_model": None,
                "primary_model_origin": None,
                "scheduler_id": "repair-job",
                "verified": True,
            },
        ),
    ):
        case_dir = tmp_path / name
        case_dir.mkdir()
        workspace, registry_path, config_before, binding_before = (
            _seed_unscheduled_detail_state(case_dir)
        )
        registry_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "active_workspace": str(workspace.resolve()),
                    "scheduling": scheduling,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        rejected = _run_host(
            case_dir,
            "expired-detail",
            "repair-unscheduled-detail",
            str(workspace),
            "fake-review-002",
        )
        assert _json_stderr(rejected) == {"error": "invalid_repair_state"}
        assert (workspace / "config.yaml").read_bytes() == config_before
        assert (workspace / BINDING_PATH).read_bytes() == binding_before


def test_unscheduled_detail_repair_binding_timestamp_rolls_forward_monotonically(
    tmp_path,
):
    workspace, _, _, _ = _seed_unscheduled_detail_state(tmp_path)
    sidecar_path = workspace / BINDING_PATH
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["bound_at"] = "2026-07-16T13:00:59+00:00"
    sidecar_path.write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["repair_binding_tick"] = 60
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _json_stdout(
        _run_host(
            tmp_path,
            "expired-detail",
            "repair-unscheduled-detail",
            str(workspace),
            "fake-review-002",
        )
    )
    binding = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert binding["bound_at"] == "2026-07-16T13:01:00+00:00"


def test_unscheduled_detail_repair_rejects_non_newer_generated_timestamp(tmp_path):
    workspace, _, config_before, _ = _seed_unscheduled_detail_state(tmp_path)
    sidecar_path = workspace / BINDING_PATH
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["bound_at"] = "2027-07-16T12:00:00+00:00"
    sidecar_path.write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    binding_before = sidecar_path.read_bytes()
    failed = _run_host(
        tmp_path,
        "expired-detail",
        "repair-unscheduled-detail",
        str(workspace),
        "fake-review-002",
    )
    assert _json_stderr(failed) == {
        "config": "restored_exact",
        "error": "repair_activation_failed",
        "sidecar": "restored_exact",
    }
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert sidecar_path.read_bytes() == binding_before


def test_unscheduled_detail_repair_rejects_reused_generated_id_and_timestamp(
    tmp_path,
):
    workspace, _, config_before, _ = _seed_unscheduled_detail_state(tmp_path)
    sidecar_path = workspace / BINDING_PATH
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["binding_id"] = "binding-00000000-0000-4000-8000-000000000001"
    sidecar["bound_at"] = "2026-07-16T13:00:01+00:00"
    sidecar_path.write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    binding_before = sidecar_path.read_bytes()
    failed = _run_host(
        tmp_path,
        "expired-detail",
        "repair-unscheduled-detail",
        str(workspace),
        "fake-review-002",
    )
    assert _json_stderr(failed) == {
        "config": "restored_exact",
        "error": "repair_activation_failed",
        "sidecar": "restored_exact",
    }
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert sidecar_path.read_bytes() == binding_before


def test_unscheduled_repair_rejects_refused_same_id_and_accepts_exact_alternate(
    tmp_path,
):
    for scenario in (
        "exact-dispatch-refused-detail",
        "exact-dispatch-refused-both",
    ):
        case_dir = tmp_path / scenario
        case_dir.mkdir()
        workspace, _, config_before, binding_before = (
            _seed_unscheduled_detail_state(case_dir)
        )
        rejected = _run_host(
            case_dir,
            scenario,
            "repair-unscheduled-detail",
            str(workspace),
            "fake-review-001",
        )
        assert _json_stderr(rejected) == {
            "error": "repair_model_unavailable",
            "selection": "fake-review-001",
        }
        assert (workspace / "config.yaml").read_bytes() == config_before
        assert (workspace / BINDING_PATH).read_bytes() == binding_before
        repaired = _json_stdout(
            _run_host(
                case_dir,
                scenario,
                "repair-unscheduled-detail",
                str(workspace),
                "fake-review-002",
            )
        )
        assert repaired["detail"]["after"] == "fake-review-002"
        binding = json.loads(
            (workspace / BINDING_PATH).read_text(encoding="utf-8")
        )
        assert binding["detail_model"] == "fake-review-002"
        assert binding["detail_model_origin"] == "repair"


def test_detail_repair_writes_fresh_matching_binding_even_for_same_exact_id(tmp_path):
    workspace, registry_path, config_before, binding_before, _ = _seed_repair_state(
        tmp_path
    )
    proposal = _begin_and_authorize(
        tmp_path,
        "happy",
        workspace,
        detail_override="fake-review-001",
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


def test_activation_rejects_generated_binding_timestamp_not_newer_than_snapshot(
    tmp_path,
):
    workspace, registry_path, config_before, _, registry_before = _seed_repair_state(
        tmp_path
    )
    sidecar_path = workspace / BINDING_PATH
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["bound_at"] = "2027-07-16T12:00:00+00:00"
    sidecar_path.write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    future_binding_before = sidecar_path.read_bytes()
    _begin_and_authorize(tmp_path, "expired-detail", workspace)
    failed = _run_host(
        tmp_path,
        "expired-detail",
        "activate-repair",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(failed) == {
        "authorization_consumed": True,
        "config": "restored_exact",
        "error": "repair_activation_failed",
        "job": "restored_exact",
        "registry": "restored_exact",
        "sidecar": "restored_exact",
        "verified": False,
    }
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert sidecar_path.read_bytes() == future_binding_before
    assert registry_path.read_bytes() == registry_before
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    assert not state.get("repair_transactions")


def test_scheduled_binding_timestamp_rolls_forward_monotonically(tmp_path):
    workspace, registry_path, _, _, _ = _seed_repair_state(tmp_path)
    sidecar_path = workspace / BINDING_PATH
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["bound_at"] = "2026-07-16T13:00:59+00:00"
    sidecar_path.write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["repair_binding_tick"] = 60
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _begin_and_authorize(tmp_path, "expired-detail", workspace)
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
    state = json.loads(state_path.read_text(encoding="utf-8"))
    transaction = state["repair_transactions"][str(workspace.resolve())]
    assert transaction["staged_detail_binding"]["bound_at"] == (
        "2026-07-16T13:01:00+00:00"
    )


def test_binding_generator_failure_restores_and_consumes_before_surface_mutation(
    tmp_path,
):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    _begin_and_authorize(tmp_path, "both-expired", workspace)
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["repair_binding_tick"] = "corrupt"
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    failed = _run_host(
        tmp_path,
        "both-expired",
        "activate-repair",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(failed) == {
        "authorization_consumed": True,
        "config": "restored_exact",
        "error": "repair_activation_failed",
        "job": "restored_exact",
        "registry": "restored_exact",
        "sidecar": "restored_exact",
        "verified": False,
    }
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert registry_path.read_bytes() == registry_before
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert not state.get("repair_transactions")


def test_parser_accepted_unquoted_detail_model_activates_without_partial_state(
    tmp_path,
):
    workspace, registry_path, _, _, _ = _seed_repair_state(tmp_path)
    config_path = workspace / "config.yaml"
    config_path.write_bytes(
        config_path.read_bytes().replace(
            b'detail_model: "fake-review-001"',
            b"detail_model: fake-review-001",
        )
    )
    _begin_and_authorize(tmp_path, "both-expired", workspace)
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
    assert b'detail_model: "fake-review-002"' in config_path.read_bytes()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["scheduling"]["primary_model"] == "fake-primary-002"
    assert registry["scheduling"]["verified"] is False


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
        primary_override="fake-primary-002",
        detail_override="fake-review-002",
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
        "authorization_consumed": True,
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
    workspace, _, _, _, _ = _seed_repair_state(tmp_path)
    candidate = _issue_candidate(tmp_path, "expired-primary", workspace)
    receipt_id = candidate["receipt_id"]
    _json_stdout(
        _run_host(
            tmp_path,
            "expired-primary",
            "authorize-repair",
            str(workspace),
            receipt_id,
        )
    )
    duplicate = _run_host(
        tmp_path,
        "expired-primary",
        "authorize-repair",
        str(workspace),
        receipt_id,
    )
    assert _json_stderr(duplicate) == {"error": "duplicate_repair_confirmation"}
    _json_stdout(
        _run_host(
            tmp_path,
            "expired-primary",
            "begin-repair",
            str(workspace),
            receipt_id,
        )
    )
    reused = _run_host(
        tmp_path,
        "expired-primary",
        "begin-repair",
        str(workspace),
        receipt_id,
    )
    assert _json_stderr(reused) == {"error": "repair_candidate_receipt_required"}


def test_repair_candidate_derives_origins_from_canonical_baseline(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["scheduling"]["primary_model_origin"] = "user_override"
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["jobs"]["repair-job"]["primary_model_origin"] = "user_override"
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sidecar_path = workspace / BINDING_PATH
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["detail_model_origin"] = "repair"
    sidecar_path.write_text(json.dumps(sidecar, sort_keys=True) + "\n", encoding="utf-8")
    candidate = _issue_candidate(tmp_path, "happy", workspace)
    assert candidate["primary"]["origin_before"] == "user_override"
    assert candidate["primary"]["origin_after"] == "user_override"
    assert candidate["detail"]["origin_before"] == "repair"
    assert candidate["detail"]["origin_after"] == "repair"
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert sidecar_path.read_bytes() != binding_before
    assert registry_path.read_bytes() != registry_before


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("primary_model", "fake-primary-002"),
        ("primary_model_origin", "user_override"),
    ),
)
def test_repair_candidate_rejects_registry_job_primary_disagreement_before_preview(
    tmp_path,
    field,
    replacement,
):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["jobs"]["repair-job"][field] = replacement
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    state_before = state_path.read_bytes()
    rejected = _run_host(
        tmp_path,
        "happy",
        "repair-candidate",
        str(workspace),
        "repair-job",
        "-",
        "-",
    )
    assert _json_stderr(rejected) == {"error": "invalid_repair_state"}
    assert state_path.read_bytes() == state_before
    assert "repair_candidate_receipts" not in state
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert registry_path.read_bytes() == registry_before


def test_repair_candidate_rejects_unrecognized_canonical_origin(tmp_path):
    workspace, registry_path, config_before, binding_before, _ = _seed_repair_state(
        tmp_path
    )
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["scheduling"]["primary_model_origin"] = "caller_injected"
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rejected = _run_host(
        tmp_path,
        "happy",
        "repair-candidate",
        str(workspace),
        "repair-job",
        "-",
        "-",
    )
    assert _json_stderr(rejected) == {"error": "invalid_repair_state"}
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before


def test_partial_repair_activation_rolls_back_before_any_canary(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    _begin_and_authorize(
        tmp_path,
        "repair-partial-activation-failure",
        workspace,
        primary_override="fake-primary-002",
        detail_override="fake-review-002",
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
        "authorization_consumed": True,
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


def test_post_authorization_baseline_drift_restores_cancels_and_requires_fresh_flow(
    tmp_path,
):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    candidate = _begin_and_authorize(tmp_path, "expired-primary", workspace)
    receipt_id = candidate["receipt_id"]
    (workspace / "config.yaml").write_bytes(config_before + b"# external-drift\n")

    failed = _run_host(
        tmp_path,
        "expired-primary",
        "activate-repair",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(failed) == {
        "authorization_consumed": True,
        "config": "restored_exact",
        "error": "repair_baseline_changed",
        "job": "restored_exact",
        "registry": "restored_exact",
        "sidecar": "restored_exact",
        "verified": False,
    }
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert registry_path.read_bytes() == registry_before
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    assert receipt_id not in state.get("repair_candidate_receipts", {})
    assert not state.get("repair_transactions")

    resumed = _run_host(
        tmp_path,
        "expired-primary",
        "activate-repair",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(resumed) == {"error": "missing_repair_candidate"}
    reused = _run_host(
        tmp_path,
        "expired-primary",
        "begin-repair",
        str(workspace),
        receipt_id,
    )
    assert _json_stderr(reused) == {"error": "repair_candidate_receipt_required"}

    fresh = _issue_candidate(tmp_path, "expired-primary", workspace)
    assert fresh["receipt_id"] != receipt_id


def test_post_authorization_setup_mismatch_restores_and_consumes_transaction(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    _begin_and_authorize(tmp_path, "expired-detail", workspace)
    alternate_registry = tmp_path / "caller-registry.json"
    failed = _run_host(
        tmp_path,
        "expired-detail",
        "activate-repair",
        str(workspace),
        str(alternate_registry),
        "caller-job",
    )
    assert _json_stderr(failed) == {
        "authorization_consumed": True,
        "config": "restored_exact",
        "error": "repair_setup_invalid",
        "job": "restored_exact",
        "registry": "restored_exact",
        "sidecar": "restored_exact",
        "verified": False,
    }
    assert not alternate_registry.exists()
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert registry_path.read_bytes() == registry_before
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    assert not state.get("repair_transactions")


def test_transaction_bound_scenario_cannot_change_before_activation(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    _begin_and_authorize(
        tmp_path,
        "repair-partial-activation-failure",
        workspace,
        primary_override="fake-primary-002",
        detail_override="fake-review-002",
    )
    failed = _run_host(
        tmp_path,
        "happy",
        "activate-repair",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(failed) == {
        "authorization_consumed": True,
        "config": "restored_exact",
        "error": "repair_setup_invalid",
        "job": "restored_exact",
        "registry": "restored_exact",
        "sidecar": "restored_exact",
        "verified": False,
    }
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert registry_path.read_bytes() == registry_before


def test_invalid_staged_repair_evidence_restores_exact_snapshot(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    _begin_and_authorize(
        tmp_path,
        "expired-detail",
        workspace,
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
        "authorization_consumed": True,
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


def test_post_activation_canary_setup_mismatch_restores_and_consumes(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    _begin_and_authorize(tmp_path, "expired-detail", workspace)
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
    alternate_registry = tmp_path / "caller-canary-registry.json"
    failed = _run_host(
        tmp_path,
        "expired-detail",
        "repair-canary",
        str(workspace),
        str(alternate_registry),
        "caller-job",
    )
    assert _json_stderr(failed) == {
        "authorization_consumed": True,
        "config": "restored_exact",
        "error": "repair_canary_evidence_invalid",
        "job": "restored_exact",
        "registry": "restored_exact",
        "sidecar": "restored_exact",
        "verified": False,
    }
    assert not alternate_registry.exists()
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert registry_path.read_bytes() == registry_before
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    assert not state.get("repair_transactions")


def test_transaction_bound_scenario_cannot_change_before_canary(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    _begin_and_authorize(
        tmp_path,
        "repair-canary-failure",
        workspace,
        primary_override="fake-primary-002",
        detail_override="fake-review-002",
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
        "happy",
        "repair-canary",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(failed) == {
        "authorization_consumed": True,
        "config": "restored_exact",
        "error": "repair_canary_evidence_invalid",
        "job": "restored_exact",
        "registry": "restored_exact",
        "sidecar": "restored_exact",
        "verified": False,
    }
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / BINDING_PATH).read_bytes() == binding_before
    assert registry_path.read_bytes() == registry_before
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    assert not state.get("repair_transactions")


def test_canary_malformed_registry_scheduling_restores_and_consumes(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _activate_detail_repair(tmp_path)
    )
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["scheduling"] = []
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _assert_invalid_canary_restores_exact(
        tmp_path,
        "expired-detail",
        workspace,
        registry_path,
        config_before,
        binding_before,
        registry_before,
    )
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    assert not state.get("repair_transactions")


def test_canary_requires_exact_staged_registry_and_job_derivatives(tmp_path):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _activate_detail_repair(tmp_path)
    )
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["unrelated_registry"]["keep"] = False
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["jobs"]["repair-job"]["unrelated_job"] = "tampered"
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _assert_invalid_canary_restores_exact(
        tmp_path,
        "expired-detail",
        workspace,
        registry_path,
        config_before,
        binding_before,
        registry_before,
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["jobs"]["repair-job"]["unrelated_job"] == "keep-exact"
    assert not state.get("repair_transactions")


def _activate_detail_repair(tmp_path, scenario="expired-detail"):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _seed_repair_state(tmp_path)
    )
    _begin_and_authorize(tmp_path, scenario, workspace)
    _json_stdout(
        _run_host(
            tmp_path,
            scenario,
            "activate-repair",
            str(workspace),
            str(registry_path),
            "repair-job",
        )
    )
    return workspace, registry_path, config_before, binding_before, registry_before


def _assert_invalid_canary_restores_exact(
    tmp_path, scenario, workspace, registry_path, config_before, binding_before, registry_before
):
    failed = _run_host(
        tmp_path,
        scenario,
        "repair-canary",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(failed) == {
        "authorization_consumed": True,
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


def test_canary_rejects_stale_binding_id_even_with_matching_model_and_origin(tmp_path):
    evidence = _activate_detail_repair(tmp_path)
    workspace, registry_path, config_before, binding_before, registry_before = evidence
    sidecar_path = workspace / BINDING_PATH
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["binding_id"] = OLD_BINDING_ID
    sidecar_path.write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _assert_invalid_canary_restores_exact(
        tmp_path,
        "expired-detail",
        workspace,
        registry_path,
        config_before,
        binding_before,
        registry_before,
    )


def test_canary_rejects_stale_binding_timestamp_even_with_fresh_id(tmp_path):
    evidence = _activate_detail_repair(tmp_path)
    workspace, registry_path, config_before, binding_before, registry_before = evidence
    sidecar_path = workspace / BINDING_PATH
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["bound_at"] = "2026-07-16T12:00:00+00:00"
    sidecar_path.write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _assert_invalid_canary_restores_exact(
        tmp_path,
        "expired-detail",
        workspace,
        registry_path,
        config_before,
        binding_before,
        registry_before,
    )


def test_canary_rejects_binding_that_mismatches_staged_transaction_evidence(tmp_path):
    evidence = _activate_detail_repair(tmp_path)
    workspace, registry_path, config_before, binding_before, registry_before = evidence
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    transaction = state["repair_transactions"][str(workspace.resolve())]
    assert transaction["staged_detail_binding"] == json.loads(
        (workspace / BINDING_PATH).read_text(encoding="utf-8")
    )
    transaction["staged_detail_binding"]["binding_id"] = (
        "binding-00000000-0000-4000-8000-000000000099"
    )
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _assert_invalid_canary_restores_exact(
        tmp_path,
        "expired-detail",
        workspace,
        registry_path,
        config_before,
        binding_before,
        registry_before,
    )


def test_canary_rejects_semantic_equal_binding_with_different_staged_bytes(tmp_path):
    evidence = _activate_detail_repair(tmp_path)
    workspace, registry_path, config_before, binding_before, registry_before = evidence
    sidecar_path = workspace / BINDING_PATH
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar_path.write_text(json.dumps(sidecar) + "\n", encoding="utf-8")
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    transaction = state["repair_transactions"][str(workspace.resolve())]
    assert sidecar == transaction["staged_detail_binding"]
    assert sidecar_path.read_bytes() != json.dumps(
        transaction["staged_detail_binding"], indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"
    _assert_invalid_canary_restores_exact(
        tmp_path,
        "expired-detail",
        workspace,
        registry_path,
        config_before,
        binding_before,
        registry_before,
    )


@pytest.mark.parametrize(
    ("field", "replacement", "remove"),
    (
        ("staged_sidecar_b64", None, True),
        ("staged_sidecar_b64", [], False),
        ("staged_sidecar_b64", "not-base64!", False),
        (
            "staged_sidecar_b64",
            base64.b64encode(b"malformed-staged-sidecar").decode("ascii"),
            False,
        ),
        ("staged_registry_b64", None, True),
        ("staged_registry_b64", {}, False),
        ("staged_registry_b64", "not-base64!", False),
        (
            "staged_registry_b64",
            base64.b64encode(b"malformed-staged-registry").decode("ascii"),
            False,
        ),
        ("staged_detail_binding", [], False),
        ("staged_registry", "malformed", False),
        ("staged_job", ["malformed"], False),
    ),
)
def test_malformed_staged_transaction_evidence_restores_consumes_and_cannot_resume(
    tmp_path,
    field,
    replacement,
    remove,
):
    workspace, registry_path, config_before, binding_before, registry_before = (
        _activate_detail_repair(tmp_path)
    )
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    transaction = state["repair_transactions"][str(workspace.resolve())]
    if remove:
        transaction.pop(field)
    else:
        transaction[field] = replacement
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _assert_invalid_canary_restores_exact(
        tmp_path,
        "expired-detail",
        workspace,
        registry_path,
        config_before,
        binding_before,
        registry_before,
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["jobs"]["repair-job"] == {
        "primary_model": "fake-primary-001",
        "primary_model_origin": "session_inheritance",
        "state": "disabled",
        "unrelated_job": "keep-exact",
        "verified": False,
    }
    assert not state.get("repair_transactions")
    resumed = _run_host(
        tmp_path,
        "expired-detail",
        "repair-canary",
        str(workspace),
        str(registry_path),
        "repair-job",
    )
    assert _json_stderr(resumed) == {"error": "fresh_repair_confirmation_required"}


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


def test_headless_exact_dispatch_refusal_blocks_without_substitution_or_lost_accounting(
    tmp_path,
):
    for scenario, slots in (
        ("exact-dispatch-refused-primary", ["primary"]),
        ("exact-dispatch-refused-detail", ["detail"]),
        ("exact-dispatch-refused-both", ["primary", "detail"]),
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
            "cause": "exact_dispatch_refused",
            "completed_attempt_accounting": "preserved",
            "error": "exact_model_repair_required",
            "slots": slots,
            "substitution_attempted": False,
        }
        log = [
            json.loads(line)
            for line in (case_dir / "host.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert [entry["operation"] for entry in log] == ["headless-model-check"]
        assert log[0]["outcome"] == "blocked_exact_dispatch_refused_no_substitute"


def test_interactive_repair_replaces_roster_present_refused_slots_before_canary(
    tmp_path,
):
    for scenario, refused_slots in (
        ("exact-dispatch-refused-primary", {"primary"}),
        ("exact-dispatch-refused-detail", {"detail"}),
        ("exact-dispatch-refused-both", {"primary", "detail"}),
    ):
        case_dir = tmp_path / scenario
        case_dir.mkdir()
        workspace, registry_path, _, _, _ = _seed_repair_state(case_dir)
        candidate = _issue_candidate(case_dir, scenario, workspace)
        assert candidate["primary"]["changed"] is ("primary" in refused_slots)
        assert candidate["detail"]["changed"] is ("detail" in refused_slots)
        assert candidate["primary"]["after"] == (
            "fake-primary-002"
            if "primary" in refused_slots
            else "fake-primary-001"
        )
        assert candidate["detail"]["after"] == (
            "fake-review-002"
            if "detail" in refused_slots
            else "fake-review-001"
        )
        receipt_id = candidate["receipt_id"]
        _json_stdout(
            _run_host(
                case_dir,
                scenario,
                "authorize-repair",
                str(workspace),
                receipt_id,
            )
        )
        _json_stdout(
            _run_host(
                case_dir,
                scenario,
                "begin-repair",
                str(workspace),
                receipt_id,
            )
        )
        _json_stdout(
            _run_host(
                case_dir,
                scenario,
                "activate-repair",
                str(workspace),
                str(registry_path),
                "repair-job",
            )
        )
        committed = _json_stdout(
            _run_host(
                case_dir,
                scenario,
                "repair-canary",
                str(workspace),
                str(registry_path),
                "repair-job",
            )
        )
        assert committed["committed"] is True


def test_interactive_repair_rejects_explicit_reuse_of_refused_exact_slot(tmp_path):
    for scenario, primary_override, detail_override, selection in (
        (
            "exact-dispatch-refused-primary",
            "fake-primary-001",
            "-",
            "fake-primary-001",
        ),
        (
            "exact-dispatch-refused-detail",
            "-",
            "fake-review-001",
            "fake-review-001",
        ),
    ):
        case_dir = tmp_path / scenario
        case_dir.mkdir()
        workspace, _, _, _, _ = _seed_repair_state(case_dir)
        rejected = _run_host(
            case_dir,
            scenario,
            "repair-candidate",
            str(workspace),
            "repair-job",
            primary_override,
            detail_override,
        )
        assert _json_stderr(rejected) == {
            "error": "repair_model_unavailable",
            "selection": selection,
        }


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
        "candidate_registry_job_baseline": (
            "exact_primary_model_and_origin_equality_or_reject_before_preview",
        ),
        "origin_only_change_preview": (
            "update_exact_primary_scheduler_effect",
        ),
        "unknown_unavailable_or_ambiguous": ("reject",),
        "roster_present_refused_slot": (
            "treat_as_unusable_for_that_slot_and_replace_exactly",
        ),
        "transaction_authority": (
            "candidate_owned_one_use_exact_receipt_not_caller_models_or_origins",
        ),
        "receipt_staleness": ("reject_consume_recompute_and_reconfirm",),
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
        "post_authorization_failure": (
            "restore_cancel_and_consume_authority_no_resume",
        ),
        "staged_binding_evidence": (
            "exact_generated_id_timestamp_model_origin_and_snapshot_freshness",
        ),
        "phase_continuity": (
            "receipt_scenario_revalidated_at_activation_and_canary",
        ),
        "staged_surface_derivatives": (
            "exact_config_sidecar_registry_bytes_and_job_value",
        ),
        "malformed_staged_evidence": (
            "restore_cancel_and_consume_no_early_exit",
        ),
        "registry_location": (
            "owned_canonical_contract_never_caller_selected",
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
        "single_surface": (
            "candidate_receipt_owns_only_rendered_confirmation_preview",
        ),
        "authority_consumption": (
            "after_one_confirmation_then_one_begin_attempt",
        ),
    }
    assert _marked_table(INTERNALS, "exact-model-repair-headless") == {
        "unavailable_exact_identifier": (
            "block_affected_slots_no_substitution",
        ),
        "roster_present_exact_dispatch_refused": (
            "block_primary_detail_or_both_no_substitution",
        ),
        "completed_attempt_accounting": ("preserve",),
        "repair_owner": ("interactive_exact_model_repair",),
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
    runner_repair = [case for case in runner if 42 <= case["id"] <= 46]
    assert [case["id"] for case in home[-7:]] == [25, 26, 27, 28, 29, 30, 31]
    assert [case["id"] for case in agent[-7:]] == [15, 16, 17, 18, 19, 20, 21]
    assert [case["id"] for case in runner_repair] == [42, 43, 44, 45, 46]
    home_matrix = " ".join(case["scenario"].lower() for case in home[-7:])
    agent_matrix = " ".join(case["scenario"].lower() for case in agent[-7:])
    runner_matrix = " ".join(case["scenario"].lower() for case in runner_repair)
    for phrase in (
        "primary-only",
        "detail-only",
        "both expired",
        "exact override",
        "rollback",
        "one-use repair candidate receipt",
        "roster-present refused",
    ):
        assert phrase in home_matrix
    for phrase in (
        "one confirmation",
        "same-id detail rewrite",
        "green canary",
        "partial activation rollback",
        "unscheduled detail repair",
        "exact staged binding provenance",
    ):
        assert phrase in agent_matrix
    for phrase in (
        "expired primary",
        "expired detail",
        "both expired",
        "substitution bait",
        "exact dispatch refusal",
    ):
        assert phrase in runner_matrix
    override_case = next(case for case in home if case["id"] == 28)
    override_text = " ".join(
        [override_case["prompt"], *override_case["expectations"]]
    ).lower()
    assert "same exact primary" in override_text
    assert "alternate prior origins" in override_text
    receipt_case = next(case for case in home if case["id"] == 30)
    receipt_text = " ".join(
        [receipt_case["prompt"], *receipt_case["expectations"]]
    ).lower()
    for phrase in (
        "caller-selected model identifiers/origins",
        "actual enabled-query/source first-page quantity",
        "confirmed-envelope clone",
        "development-fixture tamper evidence",
    ):
        assert phrase in receipt_text
    refused_case = next(case for case in home if case["id"] == 31)
    refused_text = " ".join(
        [refused_case["prompt"], *refused_case["expectations"]]
    ).lower()
    assert "refusal as unusable" in refused_text
    assert "same refused exact identifier" in refused_text
    provenance_case = next(case for case in agent if case["id"] == 21)
    provenance_text = " ".join(
        [provenance_case["prompt"], *provenance_case["expectations"]]
    ).lower()
    for phrase in (
        "authority consumed",
        "stale id",
        "strictly chronologically newer",
        "disk/transaction mismatch",
        "malformed registry scheduling",
        "semantic-equal byte rewrite",
        "candidate-bound failure scenario",
    ):
        assert phrase in provenance_text
    refusal_case = next(case for case in runner if case["id"] == 46)
    refusal_text = " ".join(
        [refusal_case["prompt"], *refusal_case["expectations"]]
    ).lower()
    assert "roster membership" in refusal_text
    assert "preserves completed attempt accounting" in refusal_text
    assert all(case.get("coverage_kind") == "executable_fixture" for case in home[-7:])
    assert all(case.get("coverage_kind") == "executable_fixture" for case in agent[-7:])
    assert all(case.get("coverage_kind") == "executable_fixture" for case in runner[-5:])
