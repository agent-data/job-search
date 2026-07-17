"""Executable and structural pressure for the version-1 migration contract."""

import json
import os
import pathlib
import re
import subprocess

import pytest


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
LIFECYCLE_APPEND = ROOT / "shared" / "scripts" / "mechanics" / "lifecycle-append.sh"
RUN_ID = "2026-07-16T14-30-00Z"
RUN_STARTED = "2026-07-16T10:30:00-04:00"
BINDING_ID = "binding-123e4567-e89b-42d3-a456-426614174000"
DETAIL_MODEL = "fake-review-001"


def _valid_config(*, include_sources=True, detail_model=DETAIL_MODEL):
    sources = '  sources: ["linkedin", "ashby"]\n' if include_sources else ""
    return f'''# migration-comment-sentinel
version: 2
workspace:
  preferences_path: "preferences.md"
  master_resume_path: "resumes/master.md"
queries:
  - {{ id: "ai-eng", keywords: "AI engineer", location: "United States", limit: 25, enabled: true }}
search:
{sources}  freshness: "past-2-weeks"
  detail_model: "{detail_model}"
schedule:
  frequency: "daily"
  time: "08:00"
  timezone: "America/New_York"
notify:
  digest_path_template: "reports/{{date}}-digest.md"
  desktop_notify_on_block: true
unrelated_sentinel: "preserve-me"
'''


def _binding(*, binding_id=BINDING_ID, detail_model=DETAIL_MODEL):
    return {
        "version": 1,
        "binding_id": binding_id,
        "detail_model": detail_model,
        "detail_model_origin": "configured_auto",
        "bound_at": "2026-07-16T12:00:00+00:00",
    }


def _write_active_pair(workspace, *, include_sources=True):
    runs = workspace / "runs"
    reports = workspace / "reports"
    runs.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    (workspace / "config.yaml").write_text(
        _valid_config(include_sources=include_sources), encoding="utf-8"
    )
    (runs / "detail-model-binding.json").write_text(
        json.dumps(_binding(), sort_keys=True) + "\n", encoding="utf-8"
    )


def _lifecycle_append(workspace, command, *args, run_id=RUN_ID):
    ledger = workspace / "runs" / f".lifecycle-{run_id}.jsonl"
    result = subprocess.run(
        [
            "sh",
            str(LIFECYCLE_APPEND),
            str(ledger),
            command,
            run_id,
            RUN_STARTED,
            *args,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return ledger


def _write_cutoff_evidence(workspace, *, close=True):
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    ledger = _lifecycle_append(workspace, "start", "manual", "-")
    for phase in (
        "searching",
        "selection_settled",
        "reviewing_initial_batch",
        "early_results_shown",
    ):
        _lifecycle_append(workspace, "phase", phase)
    _lifecycle_append(workspace, "milestone", "early_results_shown")
    for phase in ("reviewing_remaining", "finalizing"):
        _lifecycle_append(workspace, "phase", phase)
    (workspace / "runs" / f"{RUN_ID}.json").write_text(
        json.dumps(
            {
                "run_id": RUN_ID,
                "completed_at": "2026-07-16T14:31:00+00:00",
                "run_health": "healthy",
                "detail_model_binding_id": BINDING_ID,
                "detail_model": DETAIL_MODEL,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace / "reports" / "2026-07-16-digest.md").write_text(
        "# Exact final digest\n", encoding="utf-8"
    )
    _lifecycle_append(workspace, "milestone", "final_run_record_written")
    _lifecycle_append(workspace, "milestone", "final_digest_written")
    if close:
        _lifecycle_append(workspace, "close", "complete", "-")
    return ledger


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

def test_cutoff_is_derived_from_canonical_workspace_evidence_and_persists(tmp_path):
    workspace = tmp_path / "workspace"
    original_v1 = _prepare_v1_workspace(workspace)
    candidate_config, candidate_binding = _candidate_files(tmp_path, "cutoff")
    _json_stdout(_run_host(tmp_path, "happy", "begin-migration", str(workspace)))
    _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "activate-pair",
            str(workspace),
            str(candidate_config),
            str(candidate_binding),
        )
    )
    _write_cutoff_evidence(workspace)

    assert _json_stdout(
        _run_host(tmp_path, "happy", "qualify-cutoff", str(workspace), RUN_ID)
    ) == {
        "binding_id": BINDING_ID,
        "cutoff_qualifies": True,
        "detail_model": DETAIL_MODEL,
        "run_id": RUN_ID,
    }

    config_before = (workspace / "config.yaml").read_bytes()
    binding_before = (workspace / "runs" / "detail-model-binding.json").read_bytes()
    refused = _run_host(
        tmp_path, "happy", "rollback-migration", str(workspace), "migration-job"
    )
    assert refused.returncode != 0
    assert json.loads(refused.stderr)["error"] == "rollback_forbidden_after_cutoff"
    assert (workspace / "config.yaml").read_bytes() == config_before
    assert (workspace / "runs" / "detail-model-binding.json").read_bytes() == binding_before
    assert config_before != original_v1


def test_cutoff_rejects_caller_supplied_paths_and_completion_flag(tmp_path):
    workspace = tmp_path / "workspace"
    _write_active_pair(workspace)
    _write_cutoff_evidence(workspace)
    lied = _run_host(
        tmp_path,
        "happy",
        "qualify-cutoff",
        str(workspace / "runs" / f"{RUN_ID}.json"),
        str(workspace / "reports" / "2026-07-16-digest.md"),
        str(workspace / "runs" / "detail-model-binding.json"),
        "true",
    )
    assert lied.returncode != 0
    assert json.loads(lied.stderr)["error"] == "invalid_cutoff_request"


@pytest.mark.parametrize(
    "evidence_gap",
    (
        "caller_lied_completion",
        "missing_ledger",
        "mismatched_requested_run_id",
        "mismatched_record_run_id",
        "mismatched_model",
        "mismatched_binding",
        "missing_digest",
        "mismatched_active_config",
    ),
)
def test_cutoff_rejects_incomplete_or_mismatched_canonical_evidence(
    tmp_path, evidence_gap
):
    workspace = tmp_path / evidence_gap
    _prepare_v1_workspace(workspace)
    candidate_config, candidate_binding = _candidate_files(tmp_path, evidence_gap)
    _json_stdout(_run_host(tmp_path, "happy", "begin-migration", str(workspace)))
    _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "activate-pair",
            str(workspace),
            str(candidate_config),
            str(candidate_binding),
        )
    )
    ledger = _write_cutoff_evidence(
        workspace, close=evidence_gap != "caller_lied_completion"
    )
    requested_run_id = RUN_ID
    run_record_path = workspace / "runs" / f"{RUN_ID}.json"

    if evidence_gap == "missing_ledger":
        ledger.unlink()
    elif evidence_gap == "mismatched_requested_run_id":
        requested_run_id = "2026-07-16T14-30-01Z"
    elif evidence_gap in {
        "mismatched_record_run_id",
        "mismatched_model",
        "mismatched_binding",
    }:
        run_record = json.loads(run_record_path.read_text(encoding="utf-8"))
        if evidence_gap == "mismatched_record_run_id":
            run_record["run_id"] = "2026-07-16T14-30-01Z"
        elif evidence_gap == "mismatched_model":
            run_record["detail_model"] = "fake-capable-001"
        else:
            run_record["detail_model_binding_id"] = (
                "binding-00000000-0000-4000-8000-000000000000"
            )
        run_record_path.write_text(json.dumps(run_record) + "\n", encoding="utf-8")
    elif evidence_gap == "missing_digest":
        (workspace / "reports" / "2026-07-16-digest.md").unlink()
    elif evidence_gap == "mismatched_active_config":
        (workspace / "config.yaml").write_text(
            _valid_config(detail_model="fake-capable-001"), encoding="utf-8"
        )

    rejected = _run_host(
        tmp_path,
        "happy",
        "qualify-cutoff",
        str(workspace),
        requested_run_id,
    )
    assert rejected.returncode != 0
    assert json.loads(rejected.stderr)["error"] == "cutoff_not_qualified"


@pytest.mark.parametrize(
    ("completed_at_case", "completed_at"),
    (
        ("missing", None),
        ("empty", ""),
        ("boolean", True),
        ("number", 1),
        ("malformed", "not-a-timestamp"),
        ("non-utc", "2026-07-16T10:31:00-04:00"),
    ),
)
def test_cutoff_rejects_missing_or_noncanonical_utc_completed_at(
    tmp_path, completed_at_case, completed_at
):
    workspace = tmp_path / f"completed-at-{completed_at_case}"
    _prepare_v1_workspace(workspace)
    candidate_config, candidate_binding = _candidate_files(
        tmp_path, f"completed-at-{completed_at_case}"
    )
    _json_stdout(_run_host(tmp_path, "happy", "begin-migration", str(workspace)))
    _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "activate-pair",
            str(workspace),
            str(candidate_config),
            str(candidate_binding),
        )
    )
    _write_cutoff_evidence(workspace)
    run_record_path = workspace / "runs" / f"{RUN_ID}.json"
    run_record = json.loads(run_record_path.read_text(encoding="utf-8"))
    if completed_at_case == "missing":
        run_record.pop("completed_at")
    else:
        run_record["completed_at"] = completed_at
    run_record_path.write_text(json.dumps(run_record) + "\n", encoding="utf-8")

    rejected = _run_host(
        tmp_path, "happy", "qualify-cutoff", str(workspace), RUN_ID
    )
    assert rejected.returncode != 0
    assert json.loads(rejected.stderr)["error"] == "cutoff_not_qualified"


def test_cutoff_rejects_unrelated_v2_run_without_matching_migration_snapshot(tmp_path):
    workspace = tmp_path / "unrelated-v2"
    _write_active_pair(workspace)
    _write_cutoff_evidence(workspace)
    rejected = _run_host(
        tmp_path, "happy", "qualify-cutoff", str(workspace), RUN_ID
    )
    assert rejected.returncode != 0
    assert json.loads(rejected.stderr)["error"] == "cutoff_not_qualified"


def _validate_candidate(tmp_path, config_text, binding=None):
    config_path = tmp_path / "candidate.yaml"
    binding_path = tmp_path / "candidate-binding.json"
    config_path.write_text(config_text, encoding="utf-8")
    binding_path.write_text(
        json.dumps(_binding() if binding is None else binding) + "\n",
        encoding="utf-8",
    )
    result = _run_host(
        tmp_path,
        "happy",
        "validate-candidate",
        str(config_path),
        str(binding_path),
    )
    return result, config_path.read_bytes()


def test_candidate_validation_accepts_omitted_optional_sources_without_rewrite(
    tmp_path,
):
    candidate = _valid_config(include_sources=False)
    result, bytes_after = _validate_candidate(tmp_path, candidate)
    assert _json_stdout(result) == {"candidate": "validated"}
    assert bytes_after == candidate.encode()
    assert b"sources:" not in bytes_after
    assert b"migration-comment-sentinel" in bytes_after
    assert b"unrelated_sentinel" in bytes_after


def test_candidate_validation_accepts_sources_block_list_without_rewrite(tmp_path):
    candidate = _valid_config(include_sources=False).replace(
        'search:\n  freshness: "past-2-weeks"',
        'search:\n'
        "  sources:\n"
        "    - linkedin # preserve block-list comment\n"
        '    - "ashby"\n'
        '  freshness: "past-2-weeks"',
    )
    result, bytes_after = _validate_candidate(tmp_path, candidate)
    assert _json_stdout(result) == {"candidate": "validated"}
    assert bytes_after == candidate.encode()
    assert b"preserve block-list comment" in bytes_after


def test_candidate_validation_accepts_canonical_defaultable_section_and_query_omissions(
    tmp_path,
):
    candidate = f'''version: 2
queries:
  - {{ id: "ai-eng", keywords: "AI engineer" }}
search:
  detail_model: "{DETAIL_MODEL}"
unrelated_sentinel: "preserve-me"
'''
    result, bytes_after = _validate_candidate(tmp_path, candidate)
    assert _json_stdout(result) == {"candidate": "validated"}
    assert bytes_after == candidate.encode()


def test_candidate_validation_accepts_preserved_block_style_query_mapping(tmp_path):
    candidate = _valid_config(include_sources=False).replace(
        '  - { id: "ai-eng", keywords: "AI engineer", location: "United States", limit: 25, enabled: true }',
        '  - id: "ai-eng"\n'
        '    keywords: "AI engineer"\n'
        '    location: "United States"\n'
        "    limit: 25\n"
        "    enabled: true",
    )
    result, bytes_after = _validate_candidate(tmp_path, candidate)
    assert _json_stdout(result) == {"candidate": "validated"}
    assert bytes_after == candidate.encode()


def test_candidate_validation_preserves_unrelated_nested_yaml_without_interpreting_it(
    tmp_path,
):
    candidate = _valid_config(include_sources=False) + (
        "unrelated_nested:\n"
        "  child:\n"
        "    - alpha\n"
        "    - beta # keep this comment\n"
    )
    result, bytes_after = _validate_candidate(tmp_path, candidate)
    assert _json_stdout(result) == {"candidate": "validated"}
    assert bytes_after == candidate.encode()


@pytest.mark.parametrize(
    "candidate",
    (
        _valid_config().replace("version: 2", 'version: "2"'),
        _valid_config().replace("search:\n", "search: []\n"),
        _valid_config().replace(
            '  sources: ["linkedin", "ashby"]', '  sources: "linkedin"'
        ),
        _valid_config().replace('  frequency: "daily"', '  frequency: "sometimes"'),
        _valid_config().replace("  desktop_notify_on_block: true", '  desktop_notify_on_block: "yes"'),
        _valid_config().replace(
            '  - { id: "ai-eng", keywords: "AI engineer", location: "United States", limit: 25, enabled: true }',
            '  - { id: "", keywords: "", location: 9, limit: 0, enabled: "yes" }',
        ),
        _valid_config().replace(
            'queries:\n  - { id: "ai-eng", keywords: "AI engineer", location: "United States", limit: 25, enabled: true }',
            "queries: []",
        ),
    ),
)
def test_candidate_validation_rejects_malformed_sections_values_and_queries(
    tmp_path, candidate
):
    result, _ = _validate_candidate(tmp_path, candidate)
    assert result.returncode != 0
    assert json.loads(result.stderr)["error"] == "candidate_validation_failed"


def test_candidate_validation_rejects_actual_config_sidecar_model_mismatch(tmp_path):
    result, _ = _validate_candidate(
        tmp_path, _valid_config(), _binding(detail_model="fake-capable-001")
    )
    assert result.returncode != 0
    assert json.loads(result.stderr)["error"] == "candidate_validation_failed"


@pytest.mark.parametrize("invalid_version", (True, 1.0, "1", None))
def test_candidate_validation_rejects_noninteger_binding_version(
    tmp_path, invalid_version
):
    binding = _binding()
    binding["version"] = invalid_version
    result, _ = _validate_candidate(tmp_path, _valid_config(), binding)
    assert result.returncode != 0
    assert json.loads(result.stderr)["error"] == "candidate_validation_failed"


@pytest.mark.parametrize(
    "invalid_depth",
    ("null", "0", "-1", "1.5", '"50"', "true"),
)
def test_candidate_validation_rejects_invalid_saved_review_depth_before_activation(
    tmp_path, invalid_depth
):
    candidate = _valid_config().replace(
        f'  detail_model: "{DETAIL_MODEL}"',
        f"  max_new_postings_per_run: {invalid_depth}\n"
        f'  detail_model: "{DETAIL_MODEL}"',
    )
    result, _ = _validate_candidate(tmp_path, candidate)
    assert result.returncode != 0
    assert json.loads(result.stderr)["error"] == "candidate_validation_failed"


@pytest.mark.parametrize("valid_depth", ("25", '"all"'))
def test_candidate_validation_accepts_canonical_saved_review_depth(
    tmp_path, valid_depth
):
    candidate = _valid_config().replace(
        f'  detail_model: "{DETAIL_MODEL}"',
        f"  max_new_postings_per_run: {valid_depth}\n"
        f'  detail_model: "{DETAIL_MODEL}"',
    )
    result, _ = _validate_candidate(tmp_path, candidate)
    assert _json_stdout(result) == {"candidate": "validated"}


def _prepare_v1_workspace(workspace, prior_sidecar=None):
    (workspace / "runs").mkdir(parents=True, exist_ok=True)
    original_config = (
        b"# original-v1-comment\nversion: 1\nsearch:\n"
        b'  detail_model: "balanced"\nunrelated_sentinel: "keep-exact"\n'
    )
    (workspace / "config.yaml").write_bytes(original_config)
    binding_path = workspace / "runs" / "detail-model-binding.json"
    if prior_sidecar is not None:
        binding_path.write_bytes(prior_sidecar)
    return original_config


def _candidate_files(tmp_path, suffix):
    config_path = tmp_path / f"candidate-{suffix}.yaml"
    binding_path = tmp_path / f"candidate-{suffix}-binding.json"
    config_path.write_text(_valid_config(include_sources=False), encoding="utf-8")
    binding_path.write_text(json.dumps(_binding()) + "\n", encoding="utf-8")
    return config_path, binding_path


def test_rollback_restores_exact_prior_sidecar_and_removes_registered_job(tmp_path):
    workspace = tmp_path / "prior-present"
    prior_sidecar = b'{"prior":"sidecar-byte-sentinel"}\n'
    original_config = _prepare_v1_workspace(workspace, prior_sidecar)
    candidate_config, candidate_binding = _candidate_files(tmp_path, "prior-present")

    assert _json_stdout(
        _run_host(tmp_path, "happy", "begin-migration", str(workspace))
    ) == {"config_snapshotted": True, "prior_sidecar": "present"}
    assert _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "activate-pair",
            str(workspace),
            str(candidate_config),
            str(candidate_binding),
        )
    )["activation"] == "complete"
    _json_stdout(_run_host(tmp_path, "happy", "register-disabled", "migration-job"))

    assert _json_stdout(
        _run_host(
            tmp_path, "happy", "rollback-migration", str(workspace), "migration-job"
        )
    ) == {
        "config": "restored_exact",
        "job_id": "migration-job",
        "job_state": "absent",
        "sidecar": "restored_exact",
    }
    assert (workspace / "config.yaml").read_bytes() == original_config
    assert (
        workspace / "runs" / "detail-model-binding.json"
    ).read_bytes() == prior_sidecar


def test_register_failure_rolls_back_exact_v1_and_new_sidecar_absence(tmp_path):
    workspace = tmp_path / "register-failure"
    original_config = _prepare_v1_workspace(workspace)
    candidate_config, candidate_binding = _candidate_files(tmp_path, "register-failure")
    _json_stdout(_run_host(tmp_path, "happy", "begin-migration", str(workspace)))
    _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "activate-pair",
            str(workspace),
            str(candidate_config),
            str(candidate_binding),
        )
    )
    register = _run_host(
        tmp_path, "register-failure", "register-disabled", "migration-job"
    )
    assert register.returncode != 0
    assert json.loads(register.stderr)["error"] == "register_failed"

    rolled_back = _json_stdout(
        _run_host(
            tmp_path,
            "register-failure",
            "rollback-migration",
            str(workspace),
            "migration-job",
        )
    )
    assert rolled_back["job_state"] == "not_created"
    assert rolled_back["sidecar"] == "removed"
    assert (workspace / "config.yaml").read_bytes() == original_config
    assert not (workspace / "runs" / "detail-model-binding.json").exists()


def test_partial_activation_failure_is_executable_and_rolls_back_exact_pair(tmp_path):
    workspace = tmp_path / "partial-activation"
    original_config = _prepare_v1_workspace(workspace)
    candidate_config, candidate_binding = _candidate_files(tmp_path, "partial")
    _json_stdout(_run_host(tmp_path, "happy", "begin-migration", str(workspace)))

    partial = _run_host(
        tmp_path,
        "partial-activation-failure",
        "activate-pair",
        str(workspace),
        str(candidate_config),
        str(candidate_binding),
    )
    assert partial.returncode != 0
    assert json.loads(partial.stderr) == {
        "active_effect": "config_only",
        "error": "partial_activation_failed",
    }
    assert (workspace / "config.yaml").read_text(encoding="utf-8").startswith(
        "# migration-comment-sentinel\nversion: 2"
    )
    assert not (workspace / "runs" / "detail-model-binding.json").exists()

    rolled_back = _json_stdout(
        _run_host(
            tmp_path,
            "partial-activation-failure",
            "rollback-migration",
            str(workspace),
            "migration-job",
        )
    )
    assert rolled_back["config"] == "restored_exact"
    assert rolled_back["sidecar"] == "removed"
    assert (workspace / "config.yaml").read_bytes() == original_config


def test_rollback_leaves_job_disabled_when_fixture_removal_is_unavailable(tmp_path):
    workspace = tmp_path / "remove-unavailable"
    _prepare_v1_workspace(workspace)
    candidate_config, candidate_binding = _candidate_files(tmp_path, "remove-unavailable")
    _json_stdout(_run_host(tmp_path, "happy", "begin-migration", str(workspace)))
    _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "activate-pair",
            str(workspace),
            str(candidate_config),
            str(candidate_binding),
        )
    )
    _json_stdout(_run_host(tmp_path, "happy", "register-disabled", "migration-job"))
    rolled_back = _json_stdout(
        _run_host(
            tmp_path,
            "remove-unavailable",
            "rollback-migration",
            str(workspace),
            "migration-job",
        )
    )
    assert rolled_back["job_state"] == "disabled"
    state = json.loads((tmp_path / "host-state.json").read_text(encoding="utf-8"))
    assert state["jobs"]["migration-job"]["state"] == "disabled"


def test_forged_cutoff_state_is_rejected_by_refold_and_does_not_block_rollback(
    tmp_path,
):
    workspace = tmp_path / "forged-cutoff"
    original_config = _prepare_v1_workspace(workspace)
    candidate_config, candidate_binding = _candidate_files(tmp_path, "forged-cutoff")
    _json_stdout(_run_host(tmp_path, "happy", "begin-migration", str(workspace)))
    _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "activate-pair",
            str(workspace),
            str(candidate_config),
            str(candidate_binding),
        )
    )
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.setdefault("migration_cutoffs", {})[str(workspace.resolve())] = {
        "run_id": RUN_ID,
        "binding_id": "binding-00000000-0000-4000-8000-000000000000",
        "detail_model": DETAIL_MODEL,
    }
    state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

    rolled_back = _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "rollback-migration",
            str(workspace),
            "migration-job",
        )
    )
    assert rolled_back["config"] == "restored_exact"
    assert (workspace / "config.yaml").read_bytes() == original_config


def test_stale_matching_cutoff_state_refolds_and_fails_closed_without_v1_restore(
    tmp_path,
):
    workspace = tmp_path / "stale-cutoff"
    original_config = _prepare_v1_workspace(workspace)
    candidate_config, candidate_binding = _candidate_files(tmp_path, "stale-cutoff")
    _json_stdout(_run_host(tmp_path, "happy", "begin-migration", str(workspace)))
    _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "activate-pair",
            str(workspace),
            str(candidate_config),
            str(candidate_binding),
        )
    )
    active_config = (workspace / "config.yaml").read_bytes()
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.setdefault("migration_cutoffs", {})[str(workspace.resolve())] = {
        "run_id": RUN_ID,
        "binding_id": BINDING_ID,
        "detail_model": DETAIL_MODEL,
    }
    state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

    refused = _run_host(
        tmp_path,
        "happy",
        "rollback-migration",
        str(workspace),
        "migration-job",
    )
    assert refused.returncode != 0
    assert json.loads(refused.stderr)["error"] == "cutoff_evidence_unverifiable"
    assert (workspace / "config.yaml").read_bytes() == active_config
    assert active_config != original_config


@pytest.mark.parametrize(
    "marker_run_id",
    (
        pytest.param(None, id="missing-run-id"),
        pytest.param("not-a-run-id", id="malformed-run-id"),
    ),
)
def test_matching_cutoff_with_unusable_run_id_fails_closed_without_v1_restore(
    tmp_path, marker_run_id
):
    workspace = tmp_path / f"unusable-run-id-{marker_run_id}"
    original_config = _prepare_v1_workspace(workspace)
    candidate_config, candidate_binding = _candidate_files(
        tmp_path, f"unusable-run-id-{marker_run_id}"
    )
    _json_stdout(_run_host(tmp_path, "happy", "begin-migration", str(workspace)))
    _json_stdout(
        _run_host(
            tmp_path,
            "happy",
            "activate-pair",
            str(workspace),
            str(candidate_config),
            str(candidate_binding),
        )
    )
    active_config = (workspace / "config.yaml").read_bytes()
    marker = {
        "binding_id": BINDING_ID,
        "detail_model": DETAIL_MODEL,
    }
    if marker_run_id is not None:
        marker["run_id"] = marker_run_id
    state_path = tmp_path / "host-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.setdefault("migration_cutoffs", {})[str(workspace.resolve())] = marker
    state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

    refused = _run_host(
        tmp_path,
        "happy",
        "rollback-migration",
        str(workspace),
        "migration-job",
    )
    assert refused.returncode != 0
    assert json.loads(refused.stderr)["error"] == "cutoff_evidence_unverifiable"
    assert (workspace / "config.yaml").read_bytes() == active_config
    assert active_config != original_config
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["migration_cutoffs"][str(workspace.resolve())] == marker


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
        "candidate_defaults": ("preserve_optional_omission_do_not_materialize",),
        "activated_pair_identity": (
            "fresh_binding_id_and_exact_model_bound_to_migration_snapshot",
        ),
        "backup_path": ("runs/config-backups/<utc-safe-timestamp>-config-v1.yaml",),
        "backup_write": ("exclusive_create_retry_fresh_timestamp_never_overwrite",),
        "activation": ("atomic_whole_file_replacements_one_config_binding_transaction",),
        "preflight": ("free_after_activation_before_canary_or_enable",),
        "setup_or_canary_failure": ("restore_exact_v1_bytes_and_prior_sidecar_state",),
        "register_failure": ("rollback_before_cutoff",),
        "partial_activation": ("rollback_before_cutoff",),
        "prior_sidecar_on_rollback": ("restore_exact_prior_bytes",),
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
        "persistence": ("recheck_canonical_cutoff_artifacts_before_any_rollback",),
        "persisted_marker": ("index_only_revalidate_canonical_evidence",),
        "foreign_marker": ("ignore_for_this_migration_and_rollback",),
        "unverifiable_marker": ("fail_closed_never_restore_v1",),
        "effect": ("migration_committed_rollback_to_v1_forbidden",),
    }
    migration_error = _marked_table(ERRORS, "config-v1-migration-block")
    assert migration_error["internal_class"] == ("config_v1_migration_failed",)
    assert migration_error["raw_user_code"] == ("none",)
    assert migration_error["user_rendering"] == (
        "observed_cause_preserved_work_next_step_exact_fix",
    )

    task_match = re.search(
        r"- \[[ x]\] \*\*T3\.2 \[BLOCKS, L\] Add safe version-1 compatibility "
        r"and staged migration\.\*\*(.*?)(?=- \[[ x]\] \*\*T3\.3)",
        PLAN.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert task_match, "missing T3.2 plan section"
    task = task_match.group(1)
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
        "job_state absent",
        "qualify-cutoff",
        "prior sidecar",
        "register failure",
        "partial activation",
        "rollback-migration",
        "removal unavailable",
        "first successful version-2 run",
        "later failure",
        "never restore",
        "omitted optional",
        "max_new_postings_per_run",
        "unrelated version-2 run",
        "persisted cutoff marker is an index",
        "fail closed",
    ):
        assert token in joined

    candidate_contract = next(case for case in migration if case["id"] == 24)
    assert "positive integer or exact `all`" in json.dumps(candidate_contract).lower()
