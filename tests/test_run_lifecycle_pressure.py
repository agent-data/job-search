"""Executable T4.1 pressure for the dev-only lifecycle coordinator fixture.

These tests use only temp workspaces and the repository's fake mechanics.  They do not exercise a
live model, agent-data, scheduler, network, or credits.  The fixture is deliberately narrower than
the runner skill: it proves ordering, accounting, terminal-state, and artifact invariants that prose
regressions otherwise make easy to miss.
"""
import json
import pathlib
import runpy
import subprocess

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fake-run-lifecycle"
RUNNER = ROOT / "skills" / "job-search-run" / "SKILL.md"
CONVENTIONS = ROOT / "shared" / "references" / "conventions.md"
ERRORS = ROOT / "shared" / "references" / "errors.md"
EVALS = ROOT / "skills" / "job-search-run" / "evals" / "evals.json"
SETUP = ROOT / "skills" / "job-search-run" / "evals" / "files" / "setup-workspace.sh"
LIFECYCLE = ROOT / "shared" / "references" / "run-lifecycle.md"
HOME = ROOT / "skills" / "job-search" / "references" / "home.md"
ONBOARDING = ROOT / "skills" / "job-search" / "references" / "onboarding.md"
AGENT = ROOT / "skills" / "job-search-agent" / "SKILL.md"
SCHEDULING = ROOT / "skills" / "job-search-agent" / "references" / "scheduling-and-consent.md"
CUSTOMIZATION = ROOT / "skills" / "job-search-agent" / "references" / "customization.md"
INTERNALS = ROOT / "shared" / "references" / "internals.md"


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
    assert summary["coordinator_reinstantiated"] is True
    assert summary["reconstructed_posting_states"] == {
        "linkedin:posting-1": "evaluating",
        "linkedin:posting-2": "queued",
    }
    assert summary["reconstructed_job_identities"] == ["linkedin:posting-1"]
    assert summary["reconstructed_attempt_ids"] == ["detail-1", "search-1"]
    assert summary["remaining"] == 0
    rows = [
        json.loads(line)
        for line in (workspace / "runs" / summary["ledger_name"]).read_text().splitlines()
    ]
    search_starts = [
        row for row in rows
        if row["event"] == "attempt_started" and row["operation"] == "initial_search"
    ]
    assert len(search_starts) == 1
    assert not any(row.get("close_state") == "interrupted" for row in rows)


def test_lifecycle_recovery_rejects_stale_cross_run_job_evidence(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("recovery", tmp_path, "manual", "-")
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting("posting-1", "queued")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting("posting-1", "evaluating")
    coordinator.producer(
        "detail-1",
        "detail_read",
        True,
        "success",
        "request-detail-1",
        logical_operation_id="detail-linkedin-posting-1",
    )
    coordinator.evaluated_job("posting-1")
    stale = json.loads(coordinator.jobs.read_text())
    stale["run_id"] = "2020-01-01T00-00-00Z"
    coordinator.jobs.write_text(json.dumps(stale) + "\n")

    recovered = namespace["Coordinator"].recover("recovery", tmp_path)
    assert recovered.reconstructed_job_identities == []
    with pytest.raises(RuntimeError, match="durable result evidence"):
        recovered.resume_recovered_work()


def test_lifecycle_recovery_accepts_nullable_ashby_salary_and_posted_date(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("recovery", tmp_path, "manual", "-")
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting("posting-ashby", "queued", source="ashby")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting("posting-ashby", "evaluating", source="ashby")
    coordinator.producer(
        "detail-ashby",
        "detail_read",
        True,
        "success",
        "request-detail-ashby",
        logical_operation_id="detail-ashby-posting-ashby",
    )
    coordinator.evaluated_job(
        "posting-ashby", source="ashby", salary_display="", posted_at=None
    )

    recovered = namespace["Coordinator"].recover("recovery", tmp_path)
    assert recovered.reconstructed_job_identities == ["ashby:posting-ashby"]
    assert recovered.resume_recovered_work() == ["ashby:posting-ashby"]
    assert recovered.fold()["evaluated"] == "1"


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
    "scenario", ["artifact_write_failure", "artifact_validation_failure"]
)
def test_lifecycle_fixture_artifact_failure_publishes_valid_blocked_artifacts(
    tmp_path, scenario
):
    result, summary, workspace = drive(tmp_path, scenario)
    assert result.returncode == 0, result.stderr
    assert summary["close_state"] == "blocked"
    assert summary["run_record_valid"] is True
    assert summary["digest_valid"] is True
    record = json.loads((workspace / "runs" / (summary["run_id"] + ".json")).read_text())
    assert record["run_health"] == "blocked"
    assert record["lifecycle"]["close_state"] == "blocked"
    digest = (workspace / "reports" / "2026-07-17-digest.md").read_text()
    assert "Run health: blocked (action needed)" in digest
    assert "Run could not be safely finalized." in digest


def test_lifecycle_fixture_public_complete_artifacts_are_unauthorized_until_close(tmp_path):
    result, summary, _ = drive(tmp_path, "authority_window")
    assert result.returncode == 0, result.stderr
    assert summary["intended_complete_files_existed_before_close"] is True
    assert summary["public_complete_authorized_before_close"] is False
    assert summary["canary_authorized_before_close"] is False
    assert summary["public_complete_authorized_after_close"] is True


def test_fixture_run_record_validator_rejects_adversarial_schema_and_invariants(tmp_path):
    result, summary, workspace = drive(tmp_path, "happy_manual")
    assert result.returncode == 0, result.stderr
    namespace = runpy.run_path(str(FIXTURE))
    validator = namespace["Coordinator"]("validate", workspace, "manual", "-")
    original = json.loads((workspace / "runs" / (summary["run_id"] + ".json")).read_text())

    def all_mode_nudge(row):
        board_query = json.loads(json.dumps(row["queries"][0]))
        board_query.update(
            query_id="fixture-board-query",
            source="ashby",
            has_more_at_stop=True,
            stop_reason="first_page_complete",
        )
        row["queries"].append(board_query)
        row["sources_searched"].append("ashby")
        row["review_scope"].update(
            mode="all", target_new_postings=None, outcome="sources_exhausted"
        )
        row["pagination_metrics"].update(
            unique_unseen_roles_first_pages=0,
            deeper_coverage_nudge_eligible=True,
            deeper_coverage_nudge_streams=["fixture-board-query:ashby"],
        )

    mutations = [
        ("trigger_scheduler", lambda row: row.update(trigger="scheduled", scheduler_id=None)),
        ("preflight_complete", lambda row: row["lifecycle"].update(phase="preflight", close_state="complete")),
        ("health_mismatch", lambda row: row["lifecycle"].update(health="blocked")),
        ("missing_primary", lambda row: row.update(primary_model=None)),
        ("portable_primary", lambda row: row.update(primary_model="inherit")),
        ("tier_primary", lambda row: row.update(primary_model="high")),
        ("alias_detail", lambda row: row.update(detail_model="haiku")),
        ("bad_detail_origin", lambda row: row.update(detail_model_origin="guessed")),
        ("unreachable_complete", lambda row: row.update(status_probe="unreachable")),
        ("bad_timestamp", lambda row: row.update(completed_at="yesterday")),
        ("bool_count", lambda row: row["agent_data_usage"].update(metered_calls=True)),
        ("usage_sum", lambda row: row["agent_data_usage"]["by_operation"].update(detail_read=99)),
        ("bad_query_stop", lambda row: row["queries"][0].update(stop_reason="invented")),
        ("bad_query_error", lambda row: row["queries"][0].update(errors=[{"oops": True}])),
        ("query_source_not_searched", lambda row: row["queries"][0].update(source="ashby", stop_reason="first_page_complete")),
        ("unpaginated_board", lambda row: (row["sources_searched"].append("ashby"), row["queries"][0].update(source="ashby"))),
        ("paginated_linkedin", lambda row: row["queries"][0].update(stop_reason="first_page_complete")),
        ("bad_review_target", lambda row: row["review_scope"].update(mode="finite", target_new_postings=None)),
        ("bad_result_sum", lambda row: row["results_summary"].update(relevant=99)),
        ("bad_pagination_stream", lambda row: row["pagination_metrics"].update(deeper_coverage_nudge_streams=[1])),
        ("ineligible_nudge_stream", lambda row: row["pagination_metrics"].update(deeper_coverage_nudge_streams=["fixture-query:ashby"])),
        ("eligible_without_stream", lambda row: row["pagination_metrics"].update(deeper_coverage_nudge_eligible=True)),
        ("all_mode_nudge", all_mode_nudge),
        ("detail_reads_exceed_evaluated", lambda row: row["results_summary"].update(detail_read=99)),
        ("complete_with_error", lambda row: row.update(error={"code": "E-FIXTURE"})),
    ]
    for name, mutate in mutations:
        candidate = json.loads(json.dumps(original))
        mutate(candidate)
        assert validator.validate_run_record(candidate) is False, name


def test_fixture_run_record_validator_accepts_only_canonical_prebinding_block_exception(tmp_path):
    result, summary, workspace = drive(tmp_path, "happy_manual")
    assert result.returncode == 0, result.stderr
    namespace = runpy.run_path(str(FIXTURE))
    validator = namespace["Coordinator"]("validate", workspace, "manual", "-")
    record = json.loads((workspace / "runs" / (summary["run_id"] + ".json")).read_text())
    record.update(
        detail_model=None,
        detail_model_origin=None,
        detail_model_binding_id=None,
        error={"class": "detail_model_binding_unavailable"},
        run_health="blocked",
    )
    record["lifecycle"] = {
        "phase": "preflight",
        "close_state": "blocked",
        "health": "blocked",
    }
    record["review_scope"]["outcome"] = "incomplete"
    record["queries"] = []
    record["sources_searched"] = []
    record["sources_failed"] = []
    record["agent_data_usage"].update(
        metered_calls=0,
        unit_rate_usd=None,
        payg_equivalent_usd=None,
        by_operation={
            "initial_search": 0,
            "continuation_search": 0,
            "detail_read": 0,
        },
        diagnostics={
            "retry_attempts": 0,
            "charged_failures": 0,
            "quota_rejections": 0,
            "free_route_calls": 0,
        },
    )
    for key in record["pagination_metrics"]:
        record["pagination_metrics"][key] = (
            False if key == "deeper_coverage_nudge_eligible"
            else [] if key == "deeper_coverage_nudge_streams"
            else 0
        )
    for key in record["results_summary"]:
        record["results_summary"][key] = 0
    record["errors"] = []
    assert validator.validate_run_record(record) is True

    invalid_model = json.loads(json.dumps(record))
    invalid_model["detail_model"] = "guessed-model"
    assert validator.validate_run_record(invalid_model) is False

    prior_work = json.loads(json.dumps(record))
    prior_work["agent_data_usage"]["metered_calls"] = 1
    prior_work["agent_data_usage"]["by_operation"]["initial_search"] = 1
    assert validator.validate_run_record(prior_work) is False

    prior_result = json.loads(json.dumps(record))
    prior_result["results_summary"].update(
        total_results=1,
        new_postings=1,
        evaluated=1,
        detail_read=1,
        relevant=1,
        strong=1,
    )
    assert validator.validate_run_record(prior_result) is False


def test_public_artifact_authority_rejects_record_attribution_mismatch(tmp_path):
    result, summary, workspace = drive(tmp_path, "happy_manual")
    assert result.returncode == 0, result.stderr
    namespace = runpy.run_path(str(FIXTURE))
    reader = namespace["Coordinator"]("reader", workspace, "manual", "-")
    path = workspace / "runs" / (summary["run_id"] + ".json")
    record = json.loads(path.read_text())
    record.update(trigger="scheduled", scheduler_id="scheduler-fixture-1")
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    assert reader.validate_run_record(record) is True
    assert reader.public_artifact_authority() is False


def test_every_shipped_run_artifact_consumer_requires_exact_closed_ledger_authority():
    canonical = LIFECYCLE.read_text()
    for fragment in [
        "exact run_id",
        "record's exact `trigger` and `scheduler_id`",
        "folded `trigger` and `scheduler_id`",
        "closed=true",
        "intended-complete",
        "open ledger",
        "canary",
        "discard all coordinator memory",
        "run_id+source+source_id",
        "jobs.jsonl",
        "attempt identities",
    ]:
        assert fragment in canonical

    consumers = [HOME, ONBOARDING, AGENT, SCHEDULING, CUSTOMIZATION, INTERNALS]
    for consumer in consumers:
        normalized = " ".join(consumer.read_text().split())
        assert "run-lifecycle.md" in normalized, consumer
        assert "exact run_id" in normalized, consumer
        assert "closed" in normalized, consumer
        assert "lifecycle-fold.sh" in normalized, consumer

    runner = " ".join(RUNNER.read_text().split())
    for fragment in (
        "discard all coordinator memory",
        "run_id+source+source_id",
        "jobs.jsonl",
        "attempt identities",
    ):
        assert fragment in runner


def test_usage_history_evals_seed_closed_authority_triplets_and_adversarial_open_candidates():
    data = json.loads(EVALS.read_text())
    by_id = {entry["id"]: entry for entry in data["evals"]}
    for eval_id in (30, 38):
        text = by_id[eval_id]["prompt"] + " " + " ".join(by_id[eval_id]["expectations"])
        for fragment in (
            "matching closed lifecycle ledger",
            "fold-derived digest",
            "distinct run-start date",
            "open-ledger candidate",
            "excluded from history",
        ):
            assert fragment in text, (eval_id, fragment)


def test_parallel_detail_eval_preserves_coordinator_only_attempt_authority():
    data = json.loads(EVALS.read_text())
    parallel = next(entry for entry in data["evals"] if entry["id"] == 14)
    text = parallel["prompt"] + " " + " ".join(parallel["expectations"])
    for forbidden in ("agent_data_attempts", "returned ledger", "worker ledger"):
        assert forbidden not in text
    for required in (
        "coordinator-owned attempt",
        "one producer call",
        "producer-authoritative metered/outcome/request evidence",
        "coordinator appends",
        "sole lifecycle ledger",
    ):
        assert required in text


def test_runner_pins_coordinator_owned_single_attempt_worker_dispatch():
    normalized = " ".join(RUNNER.read_text().split())
    for fragment in [
        "coordinator is the sole ledger writer",
        "immediately before each producer dispatch",
        "one authorized attempt",
        "must not retry",
        "fresh coordinator decision",
        "new `attempt_started`",
    ]:
        assert fragment in normalized
    assert "detail worker initializes an empty task-local `agent_data_attempts` ledger" not in normalized
    assert "A retry increments `attempt_number`" not in normalized


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


def test_runner_requires_full_canonical_schema_for_every_writable_workspace_halt():
    normalized = " ".join(RUNNER.read_text().split())
    assert normalized.count("complete canonical run-record schema") >= 2
    assert '`{"run_id","run_health","build","error"|null,"ts"}`' not in normalized


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
