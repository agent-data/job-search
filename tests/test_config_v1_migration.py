"""Executable and structural pressure for the version-1 migration contract."""

import json
import os
import pathlib
import re
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]
FAKE_HOST = ROOT / "tests" / "fake-host-capabilities"
CONVENTIONS = ROOT / "shared" / "references" / "conventions.md"
INTERNALS = ROOT / "shared" / "references" / "internals.md"
ERRORS = ROOT / "shared" / "references" / "errors.md"
HOME = ROOT / "skills" / "job-search" / "references" / "home.md"
CUSTOMIZATION = ROOT / "skills" / "job-search-agent" / "references" / "customization.md"
RUNNER = ROOT / "skills" / "job-search-run" / "SKILL.md"
PLAN = (
    ROOT
    / "docs"
    / "exec-plans"
    / "active"
    / "2026-07-16-best-in-class-cost-aware-job-search-dx.md"
)


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


def _marked_table(path, marker):
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- exact-model-contract:{re.escape(marker)} -->\n(.*?)\n"
        rf"<!-- /exact-model-contract:{re.escape(marker)} -->",
        text,
        re.S,
    )
    assert match, f"missing exact-model-contract:{marker} in {path}"
    rows = {}
    for line in match.group(1).splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        if cells[0].lower() in {"policy", "evidence"}:
            continue
        rows[cells[0]] = tuple(cells[1:])
    return rows


def _evals(skill):
    path = ROOT / "skills" / skill / "evals" / "evals.json"
    return json.loads(path.read_text(encoding="utf-8"))["evals"]


def test_fake_host_resolves_exact_v1_models_and_drives_all_failure_arms(tmp_path):
    roster = _json_stdout(_run_host(tmp_path, "happy", "model-roster"))
    assert roster == {
        "fast": "fake-fast-001",
        "balanced": "fake-review-001",
        "high": "fake-capable-001",
    }
    assert _json_stdout(
        _run_host(tmp_path, "happy", "resolve-detail", "sonnet")
    ) == {"selector": "sonnet", "exact_model": "fake-review-001"}
    assert _json_stdout(_run_host(tmp_path, "happy", "primary-model")) == {
        "exact_model": "fake-primary-001"
    }
    assert _json_stdout(
        _run_host(tmp_path, "happy", "dispatch-exact", "fake-review-001")
    )["observed_executable"] is True

    for scenario, command in (
        ("tier-roster-unavailable", ("model-roster",)),
        ("tier-resolution-unavailable", ("resolve-detail", "balanced")),
        ("primary-unknown", ("primary-model",)),
        ("exact-dispatch-unsupported", ("dispatch-exact", "fake-review-001")),
        ("exact-dispatch-refused", ("dispatch-exact", "fake-review-001")),
    ):
        result = _run_host(tmp_path, scenario, *command)
        assert result.returncode != 0, f"{scenario} unexpectedly succeeded"
        assert json.loads(result.stderr)["error"] == scenario.replace("-", "_")


def test_fake_host_drives_preflight_canary_cleanup_and_cutoff_evidence(tmp_path):
    assert _json_stdout(_run_host(tmp_path, "happy", "utc-now")) == {
        "iso": "2026-07-16T12:00:00+00:00",
        "filename_safe": "2026-07-16T12-00-00Z",
    }
    assert _json_stdout(_run_host(tmp_path, "happy", "utc-now")) == {
        "iso": "2026-07-16T12:00:01+00:00",
        "filename_safe": "2026-07-16T12-00-01Z",
    }
    candidate_config = tmp_path / "candidate.yaml"
    candidate_binding = tmp_path / "candidate-binding.json"
    candidate_config.write_text("version: 2\n", encoding="utf-8")
    candidate_binding.write_text("{}\n", encoding="utf-8")
    malformed = _run_host(
        tmp_path,
        "happy",
        "validate-candidate",
        str(candidate_config),
        str(candidate_binding),
    )
    assert malformed.returncode != 0
    assert json.loads(malformed.stderr)["error"] == "candidate_validation_failed"

    candidate_config.write_text(
        """version: 2
workspace:
  preferences_path: "preferences.md"
  master_resume_path: "resumes/master.md"
queries:
  - { id: "ai-eng", keywords: "AI engineer", location: "United States", limit: 25, enabled: true }
search:
  sources: ["linkedin", "ashby"]
  freshness: "past-2-weeks"
  detail_model: "fake-review-001"
schedule:
  frequency: "daily"
  time: "08:00"
  timezone: "America/New_York"
notify:
  digest_path_template: "reports/{date}-digest.md"
  desktop_notify_on_block: true
""",
        encoding="utf-8",
    )
    candidate_binding.write_text(
        json.dumps(
            {
                "version": 1,
                "binding_id": "binding-123e4567-e89b-42d3-a456-426614174000",
                "detail_model": "fake-review-001",
                "detail_model_origin": "configured_auto",
                "bound_at": "2026-07-16T12:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "validate-candidate",
            str(candidate_config),
            str(candidate_binding),
        )
    ) == {"candidate": "validated"}

    invalid = _run_host(
        tmp_path,
        "candidate-validation-failure",
        "validate-candidate",
        str(candidate_config),
        str(candidate_binding),
    )
    assert invalid.returncode != 0
    assert json.loads(invalid.stderr)["error"] == "candidate_validation_failed"

    assert _json_stdout(_run_host(tmp_path, "happy", "free-preflight")) == {
        "status": "ok",
        "metered_calls": 0,
    }
    assert _run_host(tmp_path, "preflight-failure", "free-preflight").returncode != 0

    registered = _json_stdout(
        _run_host(tmp_path, "canary-failure", "register-disabled", "migration-job")
    )
    assert registered == {"job_id": "migration-job", "state": "disabled"}
    blocked = _run_host(tmp_path, "canary-failure", "canary", "migration-job")
    assert blocked.returncode != 0
    assert json.loads(blocked.stderr) == {
        "error": "canary_failed",
        "run_state": "blocked",
        "completed_at": None,
    }
    assert _json_stdout(
        _run_host(tmp_path, "canary-failure", "remove-job", "migration-job")
    ) == {"job_id": "migration-job", "state": "absent"}

    _json_stdout(_run_host(tmp_path, "started-only", "register-disabled", "migration-job"))
    started = _json_stdout(
        _run_host(tmp_path, "started-only", "canary", "migration-job")
    )
    assert started == {
        "run_state": "started",
        "run_health": None,
        "completed_at": None,
    }
    _json_stdout(_run_host(tmp_path, "started-only", "remove-job", "migration-job"))

    _json_stdout(_run_host(tmp_path, "happy", "register-disabled", "migration-job"))
    complete = _json_stdout(_run_host(tmp_path, "happy", "canary", "migration-job"))
    assert complete["run_state"] == "complete"
    assert complete["run_health"] == "healthy"
    assert complete["completed_at"] is not None

    run_record = tmp_path / "2026-07-16T12-00-00Z.json"
    digest = tmp_path / "2026-07-16-digest.md"
    digest.write_text("# Final digest\n", encoding="utf-8")
    run_record.write_text(
        json.dumps(
            {
                "completed_at": "2026-07-16T12:00:00+00:00",
                "run_health": "healthy",
                "detail_model_binding_id": "binding-123e4567-e89b-42d3-a456-426614174000",
                "detail_model": "fake-review-001",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "qualify-cutoff",
            str(run_record),
            str(digest),
            str(candidate_binding),
            "true",
        )
    ) == {"cutoff_qualifies": True}
    not_complete = _run_host(
        tmp_path,
        "happy",
        "qualify-cutoff",
        str(run_record),
        str(digest),
        str(candidate_binding),
        "false",
    )
    assert not_complete.returncode != 0
    assert json.loads(not_complete.stderr)["error"] == "cutoff_not_qualified"

    mismatched = json.loads(run_record.read_text(encoding="utf-8"))
    mismatched["detail_model_binding_id"] = "binding-00000000-0000-4000-8000-000000000000"
    run_record.write_text(json.dumps(mismatched) + "\n", encoding="utf-8")
    mismatch = _run_host(
        tmp_path,
        "happy",
        "qualify-cutoff",
        str(run_record),
        str(digest),
        str(candidate_binding),
        "true",
    )
    assert mismatch.returncode != 0
    assert json.loads(mismatch.stderr)["error"] == "cutoff_not_qualified"

    mismatched["detail_model_binding_id"] = (
        "binding-123e4567-e89b-42d3-a456-426614174000"
    )
    run_record.write_text(json.dumps(mismatched) + "\n", encoding="utf-8")
    candidate_binding.write_text("[]\n", encoding="utf-8")
    malformed_binding = _run_host(
        tmp_path,
        "happy",
        "qualify-cutoff",
        str(run_record),
        str(digest),
        str(candidate_binding),
        "true",
    )
    assert malformed_binding.returncode != 0
    assert json.loads(malformed_binding.stderr)["error"] == "cutoff_not_qualified"


def test_canonical_contract_pins_passive_compatibility_transaction_and_cutoff():
    assert _marked_table(CONVENTIONS, "legacy-v1-passive-compatibility") == {
        "home_read": ("preserve_exact_config_bytes",),
        "ordinary_headless_run": ("preserve_exact_config_bytes",),
        "binding_sidecar": ("do_not_create",),
        "runtime_resolution": ("resolve_once_to_observed_executable_exact_model",),
        "failure_behavior": ("preserve_bytes_fail_closed_no_guess_or_substitute",),
    }
    transaction = _marked_table(INTERNALS, "legacy-v1-migration-transaction")
    assert transaction == {
        "trigger": ("interactive_action_requires_version_2",),
        "confirmation": ("single_action_confirmation_includes_migration_no_separate_prompt",),
        "candidate": ("preserve_comments_and_unrelated_fields_replace_only_required_schema_and_model",),
        "candidate_validation": ("complete_v2_config_and_fresh_matching_binding_before_activation",),
        "backup_path": ("runs/config-backups/<utc-safe-timestamp>-config-v1.yaml",),
        "backup_write": ("exclusive_create_retry_fresh_timestamp_never_overwrite",),
        "activation": ("atomic_whole_file_replacements_one_config_binding_transaction",),
        "preflight": ("free_after_activation_before_canary_or_enable",),
        "setup_or_canary_failure": ("restore_exact_v1_bytes_and_prior_sidecar_state",),
        "new_binding_on_rollback": ("remove",),
        "new_scheduler_job_on_rollback": ("remove_or_disable",),
        "post_cutoff_failure": ("never_restore_stale_v1",),
    }
    assert _marked_table(INTERNALS, "legacy-v1-rollback-cutoff") == {
        "qualifying_record": (
            "complete_nonblocked_run_with_matching_migration_binding_and_exact_model",
        ),
        "started_run": ("not_qualifying",),
        "blocked_run": ("not_qualifying",),
        "incomplete_or_missing_artifacts": ("not_qualifying",),
        "lifecycle_gate": ("folded_run_ledger_can_complete_true",),
        "effect": ("migration_committed_rollback_to_v1_forbidden",),
    }
    migration_error = _marked_table(ERRORS, "config-v1-migration-block")
    assert migration_error["internal_class"] == ("config_v1_migration_failed",)
    assert migration_error["raw_user_code"] == ("none",)
    assert migration_error["user_rendering"] == (
        "observed_cause_preserved_work_next_step_exact_fix",
    )

    task = PLAN.read_text(encoding="utf-8").split(
        "- [ ] **T3.2 [BLOCKS, L] Add safe version-1 compatibility and staged migration.**",
        1,
    )[1].split("- [ ] **T3.3", 1)[0]
    assert "- shared/references/build-stamp.md" in task


def test_skill_surfaces_delegate_to_canonical_migration_contract_without_code_leaks():
    home = HOME.read_text(encoding="utf-8").lower()
    assert "passive version-1 home read" in home
    assert "byte-for-byte" in home
    assert "do not create `runs/detail-model-binding.json`" in home

    customization = " ".join(
        CUSTOMIZATION.read_text(encoding="utf-8").lower().split()
    )
    assert "version-1 staged migration" in customization
    assert "single confirmation" in customization
    assert "separate migration prompt" in customization

    runner = " ".join(RUNNER.read_text(encoding="utf-8").lower().split())
    assert "ordinary version-1 run" in runner
    assert "byte-for-byte" in runner
    assert "never create `runs/detail-model-binding.json`" in runner

    for path in (HOME, CUSTOMIZATION, RUNNER):
        text = path.read_text(encoding="utf-8")
        assert "E-CONFIG-MIGRATION" not in text


def test_evals_keep_case_39_structural_and_add_executable_migration_pressure():
    runner_cases = _evals("job-search-run")
    structural = next(case for case in runner_cases if case["id"] == 39)
    assert structural["coverage_kind"] == "structural_contract"
    assert structural["executable_host_controls"] is False

    executable = [case for case in runner_cases if case.get("coverage_kind") == "executable_fixture"]
    joined = json.dumps(executable).lower()
    for token in (
        "fake-host-capabilities",
        "passive",
        "ordinary version-1 headless",
        "tier-roster-unavailable",
        "tier-resolution-unavailable",
        "primary-unknown",
        "exact-dispatch-unsupported",
        "exact-dispatch-refused",
        "config bytes",
        "detail-model-binding.json",
    ):
        assert token in joined

    search_cases = _evals("job-search")
    passive_home = next(case for case in search_cases if case["id"] == 15)
    assert "fresh update_check cache" in passive_home["prompt"].lower()
    migration = [case for case in search_cases if case.get("coverage_kind") == "executable_fixture"]
    joined = json.dumps(migration).lower()
    for token in (
        "single schedule confirmation",
        "exact detail model",
        "validation failure",
        "canary failure",
        "config-backups",
        "remove-job",
        "qualify-cutoff",
        "first successful version-2 run",
        "later failure",
        "never restore",
    ):
        assert token in joined
