"""Executable T4.1 pressure for the dev-only lifecycle coordinator fixture.

These tests use only temp workspaces and the repository's fake mechanics.  They do not exercise a
live model, agent-data, scheduler, network, or credits.  The fixture is deliberately narrower than
the runner skill: it proves ordering, accounting, terminal-state, and artifact invariants that prose
regressions otherwise make easy to miss.
"""
import json
import pathlib
import re
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

LINKEDIN_ID = "9100001"
LINKEDIN_ID_2 = "9100002"
LINKEDIN_PRIOR_ID = "9100000"
ASHBY_ID = "a1111111-1111-4111-8111-111111111111"
POSTING_ID = "jp_0123456789ab"


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
        assert json.loads(jobs[0])["source_id"] == LINKEDIN_PRIOR_ID


def test_lifecycle_fixture_compaction_after_selection_resumes_without_search_replay(tmp_path):
    result, summary, workspace = drive(tmp_path, "compaction_after_selection")
    assert result.returncode == 0, result.stderr
    assert summary["close_state"] == "complete"
    assert summary["can_complete"] is True
    assert summary["coordinator_reinstantiated"] is True
    assert summary["reconstructed_posting_states"] == {
        "linkedin:%s" % LINKEDIN_ID: "evaluating",
        "linkedin:%s" % LINKEDIN_ID_2: "queued",
    }
    assert summary["reconstructed_job_identities"] == ["linkedin:%s" % LINKEDIN_ID]
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
    coordinator.posting(LINKEDIN_ID, "queued")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(LINKEDIN_ID, "evaluating")
    coordinator.producer(
        "detail-1",
        "detail_read",
        True,
        "success",
        "request-detail-1",
        logical_operation_id="detail-linkedin-%s" % LINKEDIN_ID,
    )
    coordinator.evaluated_job(LINKEDIN_ID)
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
    coordinator.source_order = "ashby"
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting(ASHBY_ID, "queued", source="ashby")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(ASHBY_ID, "evaluating", source="ashby")
    coordinator.producer(
        "detail-ashby",
        "detail_read",
        True,
        "success",
        "request-detail-ashby",
        logical_operation_id="detail-ashby-%s" % ASHBY_ID,
    )
    coordinator.evaluated_job(
        ASHBY_ID, source="ashby", salary_display="", posted_at=None
    )

    recovered = namespace["Coordinator"].recover("recovery", tmp_path)
    assert recovered.reconstructed_job_identities == ["ashby:%s" % ASHBY_ID]
    assert recovered.resume_recovered_work() == ["ashby:%s" % ASHBY_ID]
    assert recovered.fold()["evaluated"] == "1"


def test_recovery_settles_canonical_summary_only_judgment_without_detail_attempt(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("summary-recovery", tmp_path, "manual", "-")
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting(LINKEDIN_ID, "queued")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(LINKEDIN_ID, "evaluating")
    coordinator.evaluated_job(LINKEDIN_ID)
    event = json.loads((tmp_path / "jobs.jsonl").read_text())
    event["detail_read"] = False
    (tmp_path / "jobs.jsonl").write_text(
        json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n"
    )

    recovered = namespace["Coordinator"].recover("summary-recovery", tmp_path)
    assert recovered.resume_recovered_work() == ["linkedin:%s" % LINKEDIN_ID]
    assert recovered.fold()["evaluated"] == "1"


def test_recovery_rejects_summary_only_judgment_with_detail_attempt_evidence(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("summary-contradiction", tmp_path, "manual", "-")
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting(LINKEDIN_ID, "queued")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(LINKEDIN_ID, "evaluating")
    coordinator.producer(
        "detail-1",
        "detail_read",
        True,
        "success",
        "request-detail-1",
        logical_operation_id="detail-linkedin-%s" % LINKEDIN_ID,
    )
    coordinator.evaluated_job(LINKEDIN_ID)
    event = json.loads((tmp_path / "jobs.jsonl").read_text())
    event["detail_read"] = False
    (tmp_path / "jobs.jsonl").write_text(
        json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n"
    )

    recovered = namespace["Coordinator"].recover("summary-contradiction", tmp_path)
    with pytest.raises(RuntimeError, match="summary-only judgment had detail attempt"):
        recovered.resume_recovered_work()


def test_recovery_accepts_durably_handled_failed_detail_summary_fallback(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("handled-summary", tmp_path, "manual", "-")
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting(LINKEDIN_ID, "queued")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(LINKEDIN_ID, "evaluating")
    logical_id = "detail-linkedin-%s" % LINKEDIN_ID
    coordinator.producer(
        "detail-1",
        "detail_read",
        True,
        "terminal_failure",
        "request-detail-1",
        logical_operation_id=logical_id,
    )
    coordinator.evaluated_job(LINKEDIN_ID)
    event = json.loads((tmp_path / "jobs.jsonl").read_text())
    event["detail_read"] = False
    (tmp_path / "jobs.jsonl").write_text(
        json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n"
    )
    coordinator.append("attempt-resolved", "detail-1", "summary_fallback")

    recovered = namespace["Coordinator"].recover("handled-summary", tmp_path)
    assert recovered.resume_recovered_work() == ["linkedin:%s" % LINKEDIN_ID]
    assert recovered.fold()["blocking_attempt_failures"] == "0"


def test_recovery_rejects_queued_identity_that_already_has_durable_job(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("queued-job", tmp_path, "manual", "-")
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting(LINKEDIN_ID, "queued")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.evaluated_job(LINKEDIN_ID)

    recovered = namespace["Coordinator"].recover("queued-job", tmp_path)
    before = (tmp_path / "jobs.jsonl").read_bytes()
    with pytest.raises(RuntimeError, match="queued posting already had durable job"):
        recovered.resume_recovered_work()
    assert (tmp_path / "jobs.jsonl").read_bytes() == before
    assert not any(
        row.get("operation") == "detail_read"
        for row in recovered.ledger_rows()
        if row["event"] == "attempt_started"
    )


def test_preclose_artifact_validation_rejects_evaluated_state_without_job(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("preclose-missing-job", tmp_path, "manual", "-")
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting(LINKEDIN_ID, "queued")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(LINKEDIN_ID, "evaluating")
    coordinator.producer(
        "detail-1",
        "detail_read",
        True,
        "success",
        "request-detail-1",
        logical_operation_id="detail-linkedin-%s" % LINKEDIN_ID,
    )
    coordinator.posting(LINKEDIN_ID, "evaluated")
    coordinator.phase("early_results_shown")
    coordinator.phase("reviewing_remaining")
    coordinator.phase("finalizing")

    assert coordinator.write_and_validate_artifacts("complete") is False
    state = coordinator.fold()
    assert not any(
        row["event"] == "milestone"
        and row["milestone"] in ("final_run_record_written", "final_digest_written")
        for row in coordinator.ledger_rows()
    )
    assert state["ready_to_close"] == "false"
    with pytest.raises(RuntimeError):
        coordinator.close("complete", "-")


def test_preclose_rejects_summary_resolution_bound_to_detail_read_true_job(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("resolution-true-job", tmp_path, "manual", "-")
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting(LINKEDIN_ID, "queued")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(LINKEDIN_ID, "evaluating")
    coordinator.producer(
        "detail-1",
        "detail_read",
        True,
        "terminal_failure",
        "request-detail-1",
        logical_operation_id="detail-linkedin-%s" % LINKEDIN_ID,
    )
    coordinator.append("attempt-resolved", "detail-1", "summary_fallback")
    coordinator.evaluated_job(LINKEDIN_ID)
    coordinator.posting(LINKEDIN_ID, "evaluated")
    coordinator.phase("early_results_shown")
    coordinator.phase("reviewing_remaining")
    coordinator.phase("finalizing")

    assert coordinator.write_and_validate_artifacts("complete") is False
    assert coordinator.fold()["ready_to_close"] == "false"


def test_recovery_and_preclose_reject_orphan_summary_resolution(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("orphan-resolution", tmp_path, "manual", "-")
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting(LINKEDIN_ID, "queued")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(LINKEDIN_ID, "evaluating")
    coordinator.producer(
        "detail-1",
        "detail_read",
        True,
        "success",
        "request-detail-1",
        logical_operation_id="detail-linkedin-%s" % LINKEDIN_ID,
    )
    coordinator.evaluated_job(LINKEDIN_ID)
    coordinator.posting(LINKEDIN_ID, "evaluated")

    coordinator.producer(
        "orphan-detail-1",
        "detail_read",
        True,
        "terminal_failure",
        "request-orphan-detail-1",
        logical_operation_id="detail-linkedin-9990000",
    )
    coordinator.append("attempt-resolved", "orphan-detail-1", "summary_fallback")

    recovered = namespace["Coordinator"].recover("orphan-resolution", tmp_path)
    with pytest.raises(RuntimeError, match="resolution lacked exact durable false primary"):
        recovered.resume_recovered_work()

    coordinator.phase("early_results_shown")
    coordinator.phase("reviewing_remaining")
    coordinator.phase("finalizing")
    assert coordinator.write_and_validate_artifacts("complete") is False
    assert coordinator.fold()["ready_to_close"] == "false"


def test_current_run_job_evidence_enforces_source_native_agent_data_contract(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    validator = namespace["Coordinator"]("validate", tmp_path, "manual", "-")

    def event(source, source_id, source_url, posted_at):
        return {
            "event": "evaluated",
            "ts": "2026-07-17T12:00:00Z",
            "run_id": namespace["RUN_ID"],
            "source": source,
            "source_id": source_id,
            "query_id": "fixture-query",
            "title": "Fixture role",
            "company_name": "Fixture company",
            "location_display": "Remote",
            "salary_display": "",
            "posted_at": posted_at,
            "source_url": source_url,
            "posting_id_at_seen": POSTING_ID,
            "detail_read": True,
            "relevant": True,
            "match": "strong",
            "reasoning": "Deterministic fixture reasoning.",
            "dealbreakers_hit": [],
            "unknowns": [],
            "needs_human_check": False,
            "status": "new",
            "first_seen": "2026-07-17T12:00:00Z",
        }

    greenhouse_id = "fixture:7310605"
    lever_uuid = "f4746da4-1234-4234-8234-123456789abc"
    lever_id = "fixture:%s" % lever_uuid
    valid = {
        "linkedin": event(
            "linkedin",
            LINKEDIN_ID,
            "https://www.linkedin.com/jobs/view/%s?trackingId=fixture" % LINKEDIN_ID,
            "2026-07-16T12:00:00Z",
        ),
        "ashby": event(
            "ashby",
            ASHBY_ID,
            "https://jobs.ashbyhq.com/fixture/%s" % ASHBY_ID,
            None,
        ),
        "greenhouse": event(
            "greenhouse",
            greenhouse_id,
            "https://boards.greenhouse.io/fixture/jobs/7310605?gh_jid=7310605",
            "2026-07-16T12:00:00Z",
        ),
        "lever": event(
            "lever",
            lever_id,
            "https://jobs.lever.co/fixture/%s" % lever_uuid,
            "2026-07-16T12:00:00Z",
        ),
    }
    for source, row in valid.items():
        assert validator.valid_evaluated_job_event(row) is True, source

    extracted = json.loads(json.dumps(valid["ashby"]))
    extracted["detail_read"] = False
    extracted["posted_at_extracted"] = "2026-07-16"
    extracted["same_role_as"] = "greenhouse:%s" % greenhouse_id
    assert validator.valid_evaluated_job_event(extracted) is True
    assert validator.valid_current_run_job_events([valid["greenhouse"], extracted]) is True

    summary_only_primary = json.loads(json.dumps(valid["greenhouse"]))
    summary_only_primary["detail_read"] = False
    summary_only_alias = json.loads(json.dumps(extracted))
    summary_only_alias["posted_at_extracted"] = "2026-07-16"
    assert validator.valid_current_run_job_events(
        [summary_only_primary, summary_only_alias]
    ) is True

    inverted_board_primary = json.loads(json.dumps(valid["greenhouse"]))
    inverted_board_primary["detail_read"] = False
    inverted_board_primary["same_role_as"] = "linkedin:%s" % LINKEDIN_ID
    assert validator.valid_current_run_job_events(
        [valid["linkedin"], inverted_board_primary]
    ) is False

    assert validator.valid_current_run_job_events([extracted]) is False
    mismatched_alias = json.loads(json.dumps(extracted))
    mismatched_alias["reasoning"] = "Different verdict evidence."
    assert validator.valid_current_run_job_events(
        [valid["greenhouse"], mismatched_alias]
    ) is False
    alias_chain_target = json.loads(json.dumps(valid["greenhouse"]))
    alias_chain_target["same_role_as"] = "linkedin:%s" % LINKEDIN_ID
    assert validator.valid_current_run_job_events(
        [valid["linkedin"], alias_chain_target, extracted]
    ) is False

    mutations = [
        ("bad_linkedin_id", "linkedin", lambda row: row.update(source_id="posting-1")),
        ("bad_ashby_id", "ashby", lambda row: row.update(source_id="posting-ashby")),
        ("bad_greenhouse_id", "greenhouse", lambda row: row.update(source_id="7310605")),
        ("bad_lever_id", "lever", lambda row: row.update(source_id="fixture:not-a-uuid")),
        ("bad_posting_id_prefix", "linkedin", lambda row: row.update(posting_id_at_seen="fixture-posting-id")),
        ("short_posting_id", "linkedin", lambda row: row.update(posting_id_at_seen="jp_gg")),
        ("long_posting_id", "linkedin", lambda row: row.update(posting_id_at_seen="jp_0000000000000")),
        ("nonhex_posting_id", "linkedin", lambda row: row.update(posting_id_at_seen="jp_gggggggggggg")),
        ("bad_posting_id_hex", "linkedin", lambda row: row.update(posting_id_at_seen="jp_ABCDEF123456")),
        ("wrong_source_url", "ashby", lambda row: row.update(source_url="https://example.invalid/job")),
        ("wrong_linkedin_url_id", "linkedin", lambda row: row.update(source_url="https://www.linkedin.com/jobs/view/91000010")),
        ("dirty_ashby_url", "ashby", lambda row: row.update(source_url=row["source_url"] + "?tracking=1")),
        ("dirty_greenhouse_url", "greenhouse", lambda row: row.update(source_url=row["source_url"] + "&tracking=1")),
        ("dirty_lever_url", "lever", lambda row: row.update(source_url=row["source_url"] + "?tracking=1")),
        ("ashby_api_date", "ashby", lambda row: row.update(posted_at="2026-07-16T12:00:00Z")),
        ("linkedin_missing_date", "linkedin", lambda row: row.update(posted_at=None)),
        ("linkedin_detail_date", "linkedin", lambda row: row.update(posted_at="2026-07-16")),
        ("greenhouse_missing_date", "greenhouse", lambda row: row.update(posted_at=None)),
        ("lever_missing_date", "lever", lambda row: row.update(posted_at=None)),
        ("bad_posted_at", "linkedin", lambda row: row.update(posted_at="2026-99-99")),
        ("empty_extracted", "ashby", lambda row: row.update(posted_at_extracted="")),
        ("bad_extracted", "ashby", lambda row: row.update(posted_at_extracted="2026-02-30")),
        ("extracted_with_api_date", "linkedin", lambda row: row.update(posted_at_extracted="2026-07-16")),
        ("object_same_role", "linkedin", lambda row: row.update(same_role_as={"source": "ashby"})),
        ("empty_same_role", "linkedin", lambda row: row.update(same_role_as="")),
        ("bad_same_role_source", "linkedin", lambda row: row.update(same_role_as="workday:123")),
        ("bad_same_role_id", "linkedin", lambda row: row.update(same_role_as="ashby:not-a-uuid")),
        ("self_same_role", "linkedin", lambda row: row.update(same_role_as="linkedin:%s" % LINKEDIN_ID)),
        ("empty_unknown", "linkedin", lambda row: row.update(unknowns=[""])),
    ]
    for name, source, mutate in mutations:
        candidate = json.loads(json.dumps(valid[source]))
        mutate(candidate)
        assert validator.valid_evaluated_job_event(candidate) is False, name


@pytest.mark.parametrize(
    "evidence_kind",
    ["wrong_operation", "wrong_source", "wrong_source_id", "later_failure", "later_unaccounted"],
)
def test_recovery_requires_latest_accounted_detail_success_for_exact_posting(
    tmp_path, evidence_kind
):
    namespace = runpy.run_path(str(FIXTURE))
    workspace = tmp_path / evidence_kind
    coordinator = namespace["Coordinator"]("recovery", workspace, "manual", "-")
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting(LINKEDIN_ID, "queued")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(LINKEDIN_ID, "evaluating")

    logical_id = "detail-linkedin-%s" % LINKEDIN_ID
    operation = "detail_read"
    if evidence_kind == "wrong_operation":
        operation = "initial_search"
    elif evidence_kind == "wrong_source":
        logical_id = "detail-ashby-%s" % LINKEDIN_ID
    elif evidence_kind == "wrong_source_id":
        logical_id = "detail-linkedin-9999999"
    first_outcome = (
        "retryable_failure"
        if evidence_kind in ("later_failure", "later_unaccounted")
        else "success"
    )
    coordinator.producer(
        "detail-1",
        operation,
        True,
        first_outcome,
        "request-detail-1",
        logical_operation_id=logical_id,
    )
    if evidence_kind in ("later_failure", "later_unaccounted"):
        coordinator.producer(
            "detail-2",
            "detail_read",
            evidence_kind == "later_failure",
            "worker_failed" if evidence_kind == "later_failure" else "success",
            "request-detail-2",
            account=evidence_kind == "later_failure",
            logical_operation_id="detail-linkedin-%s" % LINKEDIN_ID,
            attempt_number=2,
        )
    coordinator.evaluated_job(LINKEDIN_ID)

    recovered = namespace["Coordinator"].recover("recovery", workspace)
    with pytest.raises(RuntimeError, match="durable result evidence"):
        recovered.resume_recovered_work()


def test_recovery_rejects_noncanonical_attempt_ordinal_even_with_durable_job(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("recovery", tmp_path, "manual", "-")
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting(LINKEDIN_ID, "queued")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(LINKEDIN_ID, "evaluating")
    coordinator.producer(
        "detail-1",
        "detail_read",
        True,
        "success",
        "request-detail-1",
        logical_operation_id="detail-linkedin-%s" % LINKEDIN_ID,
    )
    coordinator.evaluated_job(LINKEDIN_ID)
    rows = [json.loads(line) for line in coordinator.ledger.read_text().splitlines()]
    next(row for row in rows if row.get("attempt_id") == "detail-1" and row["event"] == "attempt_started")[
        "attempt_number"
    ] = 2
    coordinator.ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))

    with pytest.raises(RuntimeError, match="fold failed"):
        namespace["Coordinator"].recover("recovery", tmp_path)


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
    assert record["error"] == {"code": "E-FINAL-ARTIFACT"}
    digest = (workspace / "reports" / "2026-07-17-digest.md").read_text()
    assert "Run health: blocked (action needed)" in digest
    assert "E-FINAL-ARTIFACT" in digest
    assert "Cause:" in digest and "Fix:" in digest


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


def test_canonical_forbidden_model_vocabulary_pressures_both_run_record_fields(tmp_path):
    conventions = CONVENTIONS.read_text()
    match = re.search(
        r"<!-- exact-model-contract:forbidden-run-record-values -->\n(.*?)\n"
        r"<!-- /exact-model-contract:forbidden-run-record-values -->",
        conventions,
        re.DOTALL,
    )
    assert match is not None
    forbidden = set(re.findall(r"^- `([^`]+)`$", match.group(1), re.MULTILINE))
    assert forbidden == {
        "auto",
        "balanced",
        "default",
        "fast",
        "haiku",
        "high",
        "inherit",
        "latest",
        "opus",
        "quality",
        "sonnet",
    }

    result, summary, workspace = drive(tmp_path, "happy_manual")
    assert result.returncode == 0, result.stderr
    namespace = runpy.run_path(str(FIXTURE))
    validator = namespace["Coordinator"]("validate", workspace, "manual", "-")
    original = json.loads((workspace / "runs" / (summary["run_id"] + ".json")).read_text())
    for field in ("primary_model", "detail_model"):
        for selector in sorted(forbidden):
            for value in (selector, selector.upper(), " %s " % selector):
                candidate = json.loads(json.dumps(original))
                candidate[field] = value
                assert validator.validate_run_record(candidate) is False, (field, value)

    for field, exact_id in (
        ("primary_model", "gpt-5.4-2026-06-01"),
        ("detail_model", "claude-sonnet-4-5-20250929"),
    ):
        candidate = json.loads(json.dumps(original))
        candidate[field] = exact_id
        assert validator.validate_run_record(candidate) is True, (field, exact_id)


def test_run_record_review_scope_rejects_every_mode_outcome_contradiction(tmp_path):
    result, summary, workspace = drive(tmp_path, "happy_manual")
    assert result.returncode == 0, result.stderr
    namespace = runpy.run_path(str(FIXTURE))
    validator = namespace["Coordinator"]("validate", workspace, "manual", "-")
    original = json.loads((workspace / "runs" / (summary["run_id"] + ".json")).read_text())
    outcomes = {
        "first_page": {"completed_first_pages", "incomplete"},
        "finite": {"target_reached", "sources_exhausted", "incomplete"},
        "all": {"sources_exhausted", "incomplete"},
    }
    for mode, allowed in outcomes.items():
        for outcome in {
            "completed_first_pages", "target_reached", "sources_exhausted", "incomplete"
        } - allowed:
            candidate = json.loads(json.dumps(original))
            candidate["review_scope"].update(
                mode=mode,
                target_new_postings=1 if mode == "finite" else None,
                outcome=outcome,
            )
            assert validator.validate_run_record(candidate) is False, (mode, outcome)

    positive = [
        ("first_page", None, "completed_first_pages"),
        ("finite", 1, "target_reached"),
        ("finite", 2, "sources_exhausted"),
        ("all", None, "sources_exhausted"),
    ]
    for mode, target, outcome in positive:
        candidate = json.loads(json.dumps(original))
        candidate["review_scope"].update(
            mode=mode, target_new_postings=target, outcome=outcome
        )
        assert validator.validate_run_record(candidate) is True, (mode, outcome)

    target_count_mismatch = json.loads(json.dumps(original))
    target_count_mismatch["review_scope"].update(
        mode="finite", target_new_postings=2, outcome="target_reached"
    )
    assert validator.validate_run_record(target_count_mismatch) is False

    exhausted_at_target = json.loads(json.dumps(original))
    exhausted_at_target["review_scope"].update(
        mode="finite", target_new_postings=1, outcome="sources_exhausted"
    )
    assert validator.validate_run_record(exhausted_at_target) is False


def test_run_record_query_stop_reason_is_exact_for_review_mode_and_outcome(tmp_path):
    result, summary, workspace = drive(tmp_path, "happy_manual")
    assert result.returncode == 0, result.stderr
    namespace = runpy.run_path(str(FIXTURE))
    validator = namespace["Coordinator"]("validate", workspace, "manual", "-")
    original = json.loads((workspace / "runs" / (summary["run_id"] + ".json")).read_text())

    def board_record(mode, outcome, stop_reason):
        candidate = json.loads(json.dumps(original))
        candidate["queries"][0].update(
            source="ashby",
            stop_reason=stop_reason,
            has_more_at_stop=(
                True
                if stop_reason in ("first_page_complete", "target_reached")
                else False if stop_reason == "sources_exhausted" else None
            ),
        )
        candidate["sources_searched"] = ["ashby"]
        candidate["sources_failed"] = ["ashby"] if stop_reason == "source_failed" else []
        candidate["review_scope"].update(
            mode=mode,
            target_new_postings=(
                2 if mode == "finite" and outcome == "sources_exhausted"
                else 1 if mode == "finite" else None
            ),
            outcome=outcome,
        )
        return candidate

    valid = [
        ("first_page", "completed_first_pages", "first_page_complete"),
        ("finite", "target_reached", "target_reached"),
        ("finite", "sources_exhausted", "sources_exhausted"),
        ("all", "sources_exhausted", "sources_exhausted"),
        ("first_page", "incomplete", "source_failed"),
        ("finite", "incomplete", "pagination_incomplete"),
        ("all", "incomplete", "pagination_incomplete"),
    ]
    for mode, outcome, reason in valid:
        assert validator.validate_run_record(board_record(mode, outcome, reason)) is True, (
            mode,
            outcome,
            reason,
        )

    invalid = [
        ("first_page", "completed_first_pages", "target_reached"),
        ("first_page", "completed_first_pages", "sources_exhausted"),
        ("finite", "target_reached", "first_page_complete"),
        ("finite", "sources_exhausted", "target_reached"),
        ("all", "sources_exhausted", "first_page_complete"),
        ("all", "sources_exhausted", "target_reached"),
        ("all", "sources_exhausted", "pagination_incomplete"),
        ("finite", "target_reached", "source_failed"),
    ]
    for mode, outcome, reason in invalid:
        assert validator.validate_run_record(board_record(mode, outcome, reason)) is False, (
            mode,
            outcome,
            reason,
        )

    bad_has_more = [
        ("first_page", "completed_first_pages", "first_page_complete", None),
        ("finite", "target_reached", "target_reached", False),
        ("finite", "sources_exhausted", "sources_exhausted", True),
        ("all", "incomplete", "pagination_incomplete", True),
    ]
    for mode, outcome, reason, has_more in bad_has_more:
        candidate = board_record(mode, outcome, reason)
        candidate["queries"][0]["has_more_at_stop"] = has_more
        assert validator.validate_run_record(candidate) is False, (
            mode,
            outcome,
            reason,
            has_more,
        )

    final_page_target = board_record("finite", "target_reached", "sources_exhausted")
    assert final_page_target["queries"][0]["selected_for_review"] == 1
    assert validator.validate_run_record(final_page_target) is True

    mixed_final_page_target = json.loads(json.dumps(final_page_target))
    linkedin = json.loads(json.dumps(original["queries"][0]))
    linkedin.update(
        query_id="fixture-linkedin-query",
        results_returned=0,
        new=0,
        rows_scanned=0,
        unique_candidates=0,
        selected_for_review=0,
    )
    mixed_final_page_target["queries"].insert(0, linkedin)
    mixed_final_page_target["sources_searched"].insert(0, "linkedin")
    assert validator.validate_run_record(mixed_final_page_target) is True


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


def test_public_artifact_authority_strictly_rederives_entire_digest(tmp_path):
    result, summary, workspace = drive(tmp_path, "happy_manual")
    assert result.returncode == 0, result.stderr
    namespace = runpy.run_path(str(FIXTURE))
    reader = namespace["Coordinator"]("reader", workspace, "manual", "-")
    path = workspace / "reports" / "2026-07-17-digest.md"
    original = path.read_text()
    assert "Run ID: %s\n" % summary["run_id"] in original
    assert reader.public_artifact_authority() is True

    usage_line = "Agent-data usage: 2 metered calls this run\n"
    mutations = {
        "heading": original.replace("2026-07-17\n", "2026-07-16\n", 1),
        "run_id": original.replace(summary["run_id"], "2026-07-17T12-00-01Z", 1),
        "health": original.replace("Run health: healthy", "Run health: degraded (job sources flaky)", 1),
        "counts": original.replace("1 new posting", "2 new postings", 1),
        "calls": original.replace("2 metered calls", "1 metered call", 1),
        "calls_first": original.replace(usage_line, "", 1) + "\n" + usage_line,
        "band": original.replace("## Strong matches", "## Top matches", 1),
        "content": original.replace("Deterministic fixture reasoning.", "Invented reasoning.", 1),
    }
    for name, candidate in mutations.items():
        path.write_text(candidate)
        assert reader.public_artifact_authority() is False, name
        path.write_text(original)


def test_public_artifact_authority_excludes_malformed_current_record_with_closed_ledger(tmp_path):
    result, summary, workspace = drive(tmp_path, "happy_manual")
    assert result.returncode == 0, result.stderr
    namespace = runpy.run_path(str(FIXTURE))
    reader = namespace["Coordinator"]("reader", workspace, "manual", "-")
    path = workspace / "runs" / (summary["run_id"] + ".json")
    original = json.loads(path.read_text())
    mutations = {
        "indirect_model": lambda row: row.update(primary_model="default"),
        "mode_outcome": lambda row: row["review_scope"].update(outcome="target_reached"),
        "summary_counts": lambda row: row["results_summary"].update(strong=0),
        "unknown_field": lambda row: row.update(coordinator_memory=True),
    }
    for name, mutate in mutations.items():
        candidate = json.loads(json.dumps(original))
        mutate(candidate)
        path.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n")
        assert reader.public_artifact_authority() is False, name
    path.write_text(json.dumps(original, indent=2, sort_keys=True) + "\n")


def test_public_artifact_authority_rederives_retry_diagnostics_from_attempt_ordinals(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("retry-authority", tmp_path, "manual", "-")
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting(LINKEDIN_ID, "queued")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(LINKEDIN_ID, "evaluating")
    logical_id = "detail-linkedin-%s" % LINKEDIN_ID
    coordinator.producer(
        "detail-1",
        "detail_read",
        True,
        "retryable_failure",
        "request-detail-1",
        logical_operation_id=logical_id,
        attempt_number=1,
    )
    coordinator.producer(
        "detail-2",
        "detail_read",
        True,
        "success",
        "request-detail-2",
        logical_operation_id=logical_id,
        attempt_number=2,
    )
    coordinator.evaluated_job(LINKEDIN_ID)
    coordinator.posting(LINKEDIN_ID, "evaluated")
    coordinator.phase("early_results_shown")
    coordinator.phase("reviewing_remaining")
    coordinator.phase("finalizing")
    assert coordinator.write_and_validate_artifacts("complete") is True
    coordinator.close("complete", "-")

    path = tmp_path / "runs" / (namespace["RUN_ID"] + ".json")
    record = json.loads(path.read_text())
    assert record["agent_data_usage"]["diagnostics"]["retry_attempts"] == 1
    assert coordinator.public_artifact_authority() is True

    record["agent_data_usage"]["diagnostics"]["retry_attempts"] = 0
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    assert coordinator.public_artifact_authority() is False


def test_blocked_digest_names_exact_terminal_condition_and_fix(tmp_path):
    result, summary, workspace = drive(tmp_path, "quota_during_detail")
    assert result.returncode == 0, result.stderr
    record = json.loads((workspace / "runs" / (summary["run_id"] + ".json")).read_text())
    digest = (workspace / "reports" / "2026-07-17-digest.md").read_text()
    assert record["error"] == {"code": "E-QUOTA"}
    assert "E-QUOTA" in digest
    assert (
        "Cause: agent-data's API allowance has been reached, so this run cannot "
        "continue until calls are available.\n"
    ) in digest
    assert (
        "Fix: Check your account at https://agent-data.motie.dev/settings/billing. "
        "Your existing matches are unaffected.\n"
    ) in digest
    assert "Run could not be safely finalized." not in digest


def test_digest_collapses_same_role_aliases_into_one_canonical_entry(tmp_path):
    result, summary, workspace = drive(tmp_path, "happy_manual")
    assert result.returncode == 0, result.stderr
    namespace = runpy.run_path(str(FIXTURE))
    reader = namespace["Coordinator"]("reader", workspace, "manual", "-")
    original = json.loads((workspace / "jobs.jsonl").read_text())
    record, _ = reader.artifact_values("complete")

    primary = json.loads(json.dumps(original))
    primary.update(
        source="ashby",
        source_id=ASHBY_ID,
        source_url="https://jobs.ashbyhq.com/fixture/%s" % ASHBY_ID,
        posting_id_at_seen="jp_111111111111",
        posted_at=None,
        posted_at_extracted="2026-07-16",
    )
    alias = json.loads(json.dumps(original))
    alias.update(
        detail_read=False,
        posting_id_at_seen="jp_222222222222",
        same_role_as="ashby:%s" % ASHBY_ID,
    )
    (workspace / "jobs.jsonl").write_text(
        json.dumps(primary, separators=(",", ":"), sort_keys=True)
        + "\n"
        + json.dumps(alias, separators=(",", ":"), sort_keys=True)
        + "\n"
    )

    record["sources_searched"] = ["linkedin", "ashby"]
    ashby_query = json.loads(json.dumps(record["queries"][0]))
    ashby_query.update(query_id="fixture-ashby-query", source="ashby")
    record["queries"].append(ashby_query)
    digest = reader.canonical_digest(record)
    assert record["results_summary"]["relevant"] == 1
    assert record["results_summary"]["strong"] == 1
    assert record["results_summary"]["detail_read"] == 1
    assert "2 new postings (1 LinkedIn · 1 Ashby)" in digest
    assert "· 2 searches ·" in digest
    assert digest.count("- **Fixture role**") == 1
    assert "- **Fixture role** — Fixture company — Remote · Ashby" in digest
    assert "posted ~Jul 16 (from posting text)" in digest
    assert "[view on company board](https://jobs.ashbyhq.com/fixture/%s)" % ASHBY_ID in digest
    assert "[also on LinkedIn](https://www.linkedin.com/jobs/view/%s)" % LINKEDIN_ID in digest


def test_public_artifact_authority_rejects_jobs_without_folded_source_evidence(tmp_path):
    result, summary, workspace = drive(tmp_path, "happy_manual")
    assert result.returncode == 0, result.stderr
    namespace = runpy.run_path(str(FIXTURE))
    reader = namespace["Coordinator"]("reader", workspace, "manual", "-")
    original = json.loads((workspace / "jobs.jsonl").read_text())

    primary = json.loads(json.dumps(original))
    primary.update(
        source="ashby",
        source_id=ASHBY_ID,
        source_url="https://jobs.ashbyhq.com/fixture/%s" % ASHBY_ID,
        posting_id_at_seen="jp_111111111111",
        posted_at=None,
        posted_at_extracted="2026-07-16",
    )
    alias = json.loads(json.dumps(original))
    alias.update(
        detail_read=False,
        posting_id_at_seen="jp_222222222222",
        same_role_as="ashby:%s" % ASHBY_ID,
    )
    (workspace / "jobs.jsonl").write_text(
        json.dumps(primary, separators=(",", ":"), sort_keys=True)
        + "\n"
        + json.dumps(alias, separators=(",", ":"), sort_keys=True)
        + "\n"
    )
    assert reader.public_artifact_authority() is False


def test_public_artifact_authority_accepts_aliases_joined_through_primary_role(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("alias-authority", tmp_path, "manual", "-")
    coordinator.source_order = "linkedin+ashby"
    coordinator.start()
    coordinator.phase("searching")
    coordinator.producer("search-1", "initial_search", True, "success", "request-search-1")
    coordinator.posting(ASHBY_ID, "queued", source="ashby")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(ASHBY_ID, "evaluating", source="ashby")
    coordinator.producer(
        "detail-1",
        "detail_read",
        True,
        "success",
        "request-detail-1",
        logical_operation_id="detail-ashby-%s" % ASHBY_ID,
    )
    coordinator.evaluated_job(ASHBY_ID, source="ashby", posted_at=None)
    primary = json.loads((tmp_path / "jobs.jsonl").read_text())
    alias = json.loads(json.dumps(primary))
    alias.update(
        source="linkedin",
        source_id=LINKEDIN_ID,
        source_url="https://www.linkedin.com/jobs/view/%s" % LINKEDIN_ID,
        posting_id_at_seen="jp_222222222222",
        posted_at="2026-07-16T12:00:00Z",
        detail_read=False,
        same_role_as="ashby:%s" % ASHBY_ID,
    )
    with (tmp_path / "jobs.jsonl").open("a") as stream:
        stream.write(json.dumps(alias, separators=(",", ":"), sort_keys=True) + "\n")
    coordinator.posting(ASHBY_ID, "evaluated", source="ashby")
    coordinator.render_and_present(True, ASHBY_ID, source="ashby")
    coordinator.phase("early_results_shown")
    coordinator.phase("reviewing_remaining")
    coordinator.phase("finalizing")
    assert coordinator.write_and_validate_artifacts("complete") is True
    coordinator.close("complete", "-")

    record = json.loads(
        (tmp_path / "runs" / (namespace["RUN_ID"] + ".json")).read_text()
    )
    assert record["sources_searched"] == ["linkedin", "ashby"]
    assert record["results_summary"]["new_postings"] == 1
    assert record["results_summary"]["evaluated"] == 1
    assert "2 new postings (1 LinkedIn · 1 Ashby)" in (
        tmp_path / "reports" / "2026-07-17-digest.md"
    ).read_text()
    assert coordinator.public_artifact_authority() is True


def test_recovery_rejects_cross_board_primary_inverted_against_durable_order(tmp_path):
    namespace = runpy.run_path(str(FIXTURE))
    coordinator = namespace["Coordinator"]("board-order", tmp_path, "manual", "-")
    coordinator.source_order = "greenhouse+ashby"
    coordinator.start()
    coordinator.phase("searching")
    coordinator.posting(ASHBY_ID, "queued", source="ashby")
    coordinator.phase("selection_settled")
    coordinator.phase("reviewing_initial_batch")
    coordinator.posting(ASHBY_ID, "evaluating", source="ashby")
    coordinator.producer(
        "detail-1",
        "detail_read",
        True,
        "success",
        "request-detail-1",
        logical_operation_id="detail-ashby-%s" % ASHBY_ID,
    )
    coordinator.evaluated_job(ASHBY_ID, source="ashby", posted_at=None)
    primary = json.loads((tmp_path / "jobs.jsonl").read_text())
    greenhouse_id = "fixture:7310605"
    alias = json.loads(json.dumps(primary))
    alias.update(
        source="greenhouse",
        source_id=greenhouse_id,
        source_url=(
            "https://boards.greenhouse.io/fixture/jobs/7310605?gh_jid=7310605"
        ),
        posting_id_at_seen="jp_333333333333",
        posted_at="2026-07-16T12:00:00Z",
        detail_read=False,
        same_role_as="ashby:%s" % ASHBY_ID,
    )
    with (tmp_path / "jobs.jsonl").open("a") as stream:
        stream.write(json.dumps(alias, separators=(",", ":"), sort_keys=True) + "\n")

    with pytest.raises(RuntimeError, match="primary source order"):
        namespace["Coordinator"].recover("board-order", tmp_path)


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
        "strictly validate the complete current run-record schema",
        "digest heading",
        "Run ID",
        "band headings and content",
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
        "append `queued` for every selected unique role's primary source row before any detail dispatch",
        "Non-primary merged-source rows receive their canonical alias events in `jobs.jsonl` but no separate lifecycle states",
        "immutable folded source order",
        "attempt_resolved:summary_fallback",
        "bidirectional primary job-to-evaluated/presented lifecycle join",
        "orphan resolution fails this pre-close validation",
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
