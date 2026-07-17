"""Executable T4.1 pressure for the dev-only lifecycle coordinator fixture.

These tests use only temp workspaces and the repository's fake mechanics.  They do not exercise a
live model, agent-data, scheduler, network, or credits.  The fixture is deliberately narrower than
the runner skill: it proves ordering, accounting, terminal-state, and artifact invariants that prose
regressions otherwise make easy to miss.
"""
import json
import pathlib
import subprocess

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fake-run-lifecycle"
RUNNER = ROOT / "skills" / "job-search-run" / "SKILL.md"
CONVENTIONS = ROOT / "shared" / "references" / "conventions.md"
ERRORS = ROOT / "shared" / "references" / "errors.md"
EVALS = ROOT / "skills" / "job-search-run" / "evals" / "evals.json"
SETUP = ROOT / "skills" / "job-search-run" / "evals" / "files" / "setup-workspace.sh"


def drive(tmp_path, scenario):
    workspace = tmp_path / scenario
    result = subprocess.run(
        [str(FIXTURE), scenario, str(workspace)],
        capture_output=True,
        text=True,
    )
    summary = json.loads(result.stdout) if result.stdout.strip() else {}
    return result, summary, workspace


@pytest.mark.parametrize(
    "scenario,trigger,scheduler_id,presented",
    [
        ("happy_manual", "manual", None, 1),
        ("happy_scheduled", "scheduled", "scheduler-fixture-1", 0),
        ("happy_canary", "canary", "scheduler-fixture-1", 0),
    ],
)
def test_lifecycle_fixture_happy_paths_close_only_after_valid_artifacts(
    tmp_path, scenario, trigger, scheduler_id, presented
):
    result, summary, workspace = drive(tmp_path, scenario)
    assert result.returncode == 0, result.stderr
    assert summary["close_state"] == "complete"
    assert summary["phase"] == "complete"
    assert summary["can_complete"] is True
    assert summary["trigger"] == trigger
    assert summary["scheduler_id"] == scheduler_id
    assert summary["presented"] == presented
    assert summary["run_record_valid"] is True
    assert summary["digest_valid"] is True
    assert summary["validated_before_complete_close"] is True

    record = json.loads((workspace / "runs" / (summary["run_id"] + ".json")).read_text())
    assert set(record) == {
        "agent_data_usage",
        "build",
        "completed_at",
        "detail_model",
        "detail_model_binding_id",
        "detail_model_origin",
        "error",
        "errors",
        "lifecycle",
        "pagination_metrics",
        "primary_model",
        "primary_model_origin",
        "queries",
        "results_summary",
        "review_scope",
        "run_health",
        "run_id",
        "scheduler_id",
        "sources_failed",
        "sources_searched",
        "started_at",
        "status_probe",
        "trigger",
    }
    assert record["trigger"] == trigger
    assert record["scheduler_id"] == scheduler_id
    assert record["primary_model"] == "fixture-primary-exact"
    assert record["primary_model_origin"] == "session_inheritance"
    assert record["detail_model"] == "fixture-detail-exact"
    assert record["detail_model_origin"] == "configured_user"
    assert record["detail_model_binding_id"] == "fixture-binding-1"
    assert record["lifecycle"] == {
        "phase": "complete",
        "close_state": "complete",
        "health": "healthy",
    }
    digest = (workspace / "reports" / "2026-07-17-digest.md").read_text()
    assert digest.startswith("# Job search digest — 2026-07-17\n")
    assert "Run health: healthy\n" in digest
    assert "new posting" in digest
    assert "strong" in digest
    assert "searches" in digest
    assert "detail reads" in digest
    assert "Agent-data usage: 2 metered calls this run\n" in digest


def test_lifecycle_fixture_orders_ledger_selection_detail_render_and_accounting(tmp_path):
    result, summary, workspace = drive(tmp_path, "happy_manual")
    assert result.returncode == 0, result.stderr
    assert summary["effects"][0] == "ledger_started"
    assert summary["effects"].index("ledger_started") < summary["effects"].index("mutable_jobs_append")
    assert summary["effects"].index("attempt_started:search-1") + 1 == summary["effects"].index(
        "producer_call:search-1"
    )
    assert summary["effects"].index("producer_call:search-1") + 1 == summary["effects"].index(
        "attempt_accounted:search-1"
    )

    rows = [json.loads(line) for line in (workspace / "runs" / summary["ledger_name"]).read_text().splitlines()]
    queued = next(i for i, row in enumerate(rows) if row.get("state") == "queued")
    selection_settled = next(
        i for i, row in enumerate(rows) if row.get("phase") == "selection_settled"
    )
    evaluating = next(i for i, row in enumerate(rows) if row.get("state") == "evaluating")
    evaluated = next(i for i, row in enumerate(rows) if row.get("state") == "evaluated")
    presented = next(i for i, row in enumerate(rows) if row.get("state") == "presented")
    render = summary["effects"].index("interactive_render_succeeded")
    assert queued < selection_settled < evaluating < evaluated < presented
    assert summary["effects"].index("posting_queued") < summary["effects"].index("producer_call:detail-1")
    assert summary["effects"].index("posting_evaluated") < render < summary["effects"].index(
        "posting_presented"
    )


@pytest.mark.parametrize(
    "scenario,close_state,remaining,in_flight,started,accounted",
    [
        ("remaining_work", "blocked", 1, 0, 2, 2),
        ("in_flight_work", "interrupted", 0, 1, 2, 2),
        ("unaccounted_retry", "blocked", 0, 0, 3, 2),
        ("interruption_before_selection", "interrupted", 0, 0, 1, 1),
        ("quota_during_detail", "blocked", 0, 0, 3, 3),
        ("worker_failure", "blocked", 0, 0, 3, 3),
        ("display_failure", "blocked", 0, 0, 2, 2),
        ("artifact_write_failure", "blocked", 0, 0, 2, 2),
        ("artifact_validation_failure", "blocked", 0, 0, 2, 2),
    ],
)
def test_lifecycle_fixture_failure_pressure_never_claims_complete(
    tmp_path, scenario, close_state, remaining, in_flight, started, accounted
):
    result, summary, workspace = drive(tmp_path, scenario)
    assert result.returncode == 0, result.stderr
    assert summary["close_state"] == close_state
    assert summary["can_complete"] is False
    assert summary["remaining"] == remaining
    assert summary["in_flight"] == in_flight
    assert summary["attempts_started"] == started
    assert summary["attempts_accounted"] == accounted
    assert summary["complete_close_attempted"] is False
    ledger = (workspace / "runs" / summary["ledger_name"]).read_text()
    assert '"close_state":"complete"' not in ledger
    if summary["run_record_valid"]:
        record = json.loads(
            (workspace / "runs" / (summary["run_id"] + ".json")).read_text()
        )
        assert record["lifecycle"]["health"] == record["run_health"]


def test_lifecycle_fixture_quota_and_worker_failure_use_authoritative_accounting_once(tmp_path):
    for scenario, expected_outcome, metered in [
        ("quota_during_detail", "quota_rejected", False),
        ("worker_failure", "worker_failed", True),
    ]:
        result, summary, workspace = drive(tmp_path, scenario)
        assert result.returncode == 0, result.stderr
        rows = [json.loads(line) for line in (workspace / "runs" / summary["ledger_name"]).read_text().splitlines()]
        accounted = [row for row in rows if row["event"] == "attempt_accounted" and row["attempt_id"] == "detail-1"]
        assert len(accounted) == 1
        assert accounted[0]["outcome"] == expected_outcome
        assert accounted[0]["metered"] is metered
        assert summary["judgments_preserved"] is True
        assert summary["judgment_snapshot_sha256"] == summary["judgment_final_prefix_sha256"]
        jobs = (workspace / "jobs.jsonl").read_bytes().splitlines(keepends=True)
        assert json.loads(jobs[0])["source_id"] == "posting-prior"


def test_lifecycle_fixture_compaction_after_selection_resumes_without_search_replay(tmp_path):
    result, summary, workspace = drive(tmp_path, "compaction_after_selection")
    assert result.returncode == 0, result.stderr
    assert summary["close_state"] == "complete"
    assert summary["can_complete"] is True
    assert "context_compacted" in summary["effects"]
    assert "context_recovered_from_fold" in summary["effects"]
    assert summary["effects"].count("producer_call:search-1") == 1
    assert summary["remaining"] == 0
    ledger = (workspace / "runs" / summary["ledger_name"]).read_text()
    assert '"close_state":"interrupted"' not in ledger


def test_lifecycle_fixture_presented_requires_successful_interactive_render(tmp_path):
    result, summary, workspace = drive(tmp_path, "display_failure")
    assert result.returncode == 0, result.stderr
    jobs = [json.loads(line) for line in (workspace / "jobs.jsonl").read_text().splitlines()]
    assert jobs[-1]["event"] == "evaluated"
    assert jobs[-1]["relevant"] is True
    assert jobs[-1]["reasoning"].strip()
    ledger = (workspace / "runs" / summary["ledger_name"]).read_text()
    assert '"state":"evaluated"' in ledger
    assert '"state":"presented"' not in ledger


def test_lifecycle_fixture_complete_close_write_failure_repairs_terminal_artifacts(tmp_path):
    result, summary, workspace = drive(tmp_path, "complete_close_write_failure")
    assert result.returncode == 0, result.stderr
    assert summary["complete_close_attempted"] is True
    assert summary["validated_before_complete_close"] is True
    assert summary["close_state"] == "blocked"
    assert summary["can_complete"] is False
    assert summary["run_record_valid"] is True
    assert summary["digest_valid"] is True
    assert "complete_close_failed" in summary["effects"]
    assert "terminal_artifacts_repaired" in summary["effects"]
    ledger = (workspace / "runs" / summary["ledger_name"]).read_text()
    assert '"close_state":"complete"' not in ledger
    record = json.loads((workspace / "runs" / (summary["run_id"] + ".json")).read_text())
    assert record["lifecycle"] == {
        "phase": "finalizing",
        "close_state": "blocked",
        "health": "blocked",
    }
    digest = (workspace / "reports" / "2026-07-17-digest.md").read_text()
    assert "Run health: blocked (action needed)" in digest
    assert "Run health: healthy" not in digest


@pytest.mark.parametrize(
    "scenario",
    [
        "invalid_manual_scheduler",
        "invalid_scheduled_without_scheduler",
        "invalid_canary_without_scheduler",
        "mutable_before_ledger",
    ],
)
def test_lifecycle_fixture_rejects_invalid_attribution_or_order_without_side_effects(
    tmp_path, scenario
):
    result, summary, workspace = drive(tmp_path, scenario)
    assert result.returncode == 2
    assert summary["accepted"] is False
    assert summary["effects"] == []
    assert not (workspace / "jobs.jsonl").exists()
    assert not (workspace / "runs").exists()


def test_runner_contract_drives_every_mutation_and_completion_through_ledger():
    text = RUNNER.read_text()
    normalized = " ".join(text.split())
    required = [
        "../../shared/references/run-lifecycle.md",
        "<!-- run-lifecycle-runner:coordinator -->",
        "validate trigger/scheduler attribution before creating the ledger",
        "before any mutable or metered work",
        "append `queued` for every selected posting before any detail dispatch",
        "append `evaluating` immediately before detail work",
        "producer-authoritative",
        "append `presented` only after successful interactive rendering",
        "lifecycle-fold.sh",
        "fold again after the close and require `can_complete=true` before rendering success",
        "never infer zero calls from a missing envelope",
        "rewrite and revalidate both artifacts to the truthful noncomplete state",
        "<!-- /run-lifecycle-runner:coordinator -->",
    ]
    for fragment in required:
        assert fragment in normalized, "runner lifecycle contract is missing: %s" % fragment


def test_run_record_and_error_contracts_pin_terminal_attribution_and_failure_semantics():
    conventions = CONVENTIONS.read_text()
    for fragment in [
        "<!-- run-lifecycle-contract:run-record -->",
        "`trigger`",
        "`scheduler_id`",
        "`primary_model`",
        "`primary_model_origin`",
        "`detail_model_binding_id`",
        "`lifecycle.phase`",
        "`lifecycle.close_state`",
        "`lifecycle.health`",
        "ledger remains authoritative",
        "<!-- /run-lifecycle-contract:run-record -->",
    ]:
        assert fragment in conventions, "run-record lifecycle contract is missing: %s" % fragment

    errors = ERRORS.read_text()
    for fragment in [
        "E-LIFECYCLE-INCOMPLETE",
        "E-FINAL-ARTIFACT",
        "preserve every completed judgment",
        "never publish or display a completed state",
    ]:
        assert fragment in errors, "lifecycle failure contract is missing: %s" % fragment


def test_runner_evals_and_setup_expose_executable_lifecycle_pressure():
    data = json.loads(EVALS.read_text())
    scenarios = {entry.get("scenario"): entry for entry in data["evals"]}
    required = [
        "lifecycle completion predicate pressure",
        "lifecycle interruption and compaction pressure",
        "lifecycle producer accounting pressure",
        "lifecycle final artifact and close pressure",
        "lifecycle trigger attribution and ordering pressure",
    ]
    for scenario in required:
        assert scenarios[scenario]["coverage_kind"] == "executable_fixture"
        assert scenarios[scenario]["executable_host_controls"] is True
    assert 'ln -sf "$REPO/tests/fake-run-lifecycle" "$DEST/_bin/fake-run-lifecycle"' in SETUP.read_text()
