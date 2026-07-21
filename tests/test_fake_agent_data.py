# tests/test_fake_agent_data.py
import json, os, subprocess, pathlib
SHIM = str(pathlib.Path(__file__).resolve().parent / "fake-agent-data")
LISTING = "f9a6ec16-0bfd-44d8-b3ee-073776745ee7"

def shim(args, scenario="happy", extra_env=None):
    env = dict(os.environ, JOBSEARCH_TEST_SCENARIO=scenario,
               JOBSEARCH_FIXTURES=str(pathlib.Path(SHIM).parent / "fixtures"))
    if extra_env:
        env.update(extra_env)
    return subprocess.run([SHIM, *args], capture_output=True, text=True, env=env)

def test_version_flag_supported():
    # onboarding's install branch verifies with `agent-data --version` right after npm install
    r = shim(["--version"])
    assert r.returncode == 0 and r.stdout.strip()

def test_whoami_authed_by_default():
    r = shim(["whoami"])
    assert r.returncode == 0 and json.loads(r.stdout)["api_key_set"] is True

def test_whoami_unauth_when_env_set():
    r = shim(["whoami"], extra_env={"JOBSEARCH_TEST_NOAUTH": "1"})
    assert json.loads(r.stdout)["api_key_set"] is False

def test_status_ok_by_default():
    r = shim(["call", LISTING, "status"])
    assert json.loads(r.stdout)["status"] == "ok"

def test_search_returns_fixture():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "AI engineer"])
    assert r.returncode == 0
    assert len(json.loads(r.stdout)["data"]["results"]) >= 1

def test_search_502_on_stretch_scenario():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x"], scenario="stretch")
    assert r.returncode != 0
    assert json.loads(r.stderr)["error"]["retryable"] is True

def test_status_down_halts_non_retryable():
    r = shim(["call", LISTING, "status"], scenario="down")
    assert r.returncode != 0
    assert json.loads(r.stderr)["error"]["retryable"] is False

def test_get_posting_detail_fetch_failed_is_retryable():
    r = shim(["call", LISTING, "get-posting", "--posting_id", "jp_x", "--source_url", "u"],
             scenario="detail-fetch-failed")
    assert r.returncode != 0
    body = json.loads(r.stderr)["error"]
    assert body["code"] == "upstream_unavailable" and body["retryable"] is True

def test_error_scenario_reuses_happy_search_fixture():
    # 'degraded' has no own search-jobs fixture; it must fall back to happy's 2-result fixture
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x"], scenario="degraded")
    assert r.returncode == 0
    assert len(json.loads(r.stdout)["data"]["results"]) == 2

def test_error_scenarios_reuse_happy_ashby_fixture():
    # degraded has no own ashby fixture; the cascade must serve happy's ashby data with the echo injected
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "ashby"], scenario="degraded")
    assert r.returncode == 0
    data = json.loads(r.stdout)["data"]
    assert data["query"]["source"] == "ashby"
    assert [row["source"] for row in data["results"]] == ["ashby"]

def test_many_promising_fixture_exceeds_codex_thread_limit_observed_in_live_run():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "AI engineer"], scenario="many-promising")
    assert r.returncode == 0
    rows = json.loads(r.stdout)["data"]["results"]
    assert len(rows) == 10
    assert all(row["detail_available"] and row["source_id"] for row in rows)

def test_bad_query_422_on_sentinel_location():
    # E-BAD-QUERY: a query whose location carries the INVALID sentinel returns 422 validation_error
    # with details[].loc naming the bad param, non-retryable (the run skips it, never retries).
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--location", "INVALID-ZZ"],
             scenario="bad-query")
    assert r.returncode != 0
    body = json.loads(r.stderr)["error"]
    assert body["code"] == "validation_error" and body["retryable"] is False
    assert body["param"] == "location"
    assert body["details"][0]["loc"][-1] == "location"

def test_bad_query_scenario_passes_through_valid_location():
    # a query without the sentinel still returns the happy fixture, so OTHER queries continue the same run
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--location", "United States"],
             scenario="bad-query")
    assert r.returncode == 0
    assert len(json.loads(r.stdout)["data"]["results"]) == 2

def test_search_source_flag_echoes_requested_source():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "ashby"],
             scenario="multi-source")
    data = json.loads(r.stdout)["data"]
    assert data["query"]["source"] == "ashby"
    assert all(row["source"] == "ashby" and row["posted_at"] is None for row in data["results"])

def test_search_defaults_to_linkedin_and_injects_echo():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x"], scenario="multi-source")
    data = json.loads(r.stdout)["data"]
    assert data["query"]["source"] == "linkedin"
    assert len(data["results"]) == 2  # happy fallback carries the linkedin rows

def test_one_source_down_fails_only_the_down_source():
    down = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "ashby"],
                scenario="one-source-down")
    assert down.returncode != 0
    body = json.loads(down.stderr)["error"]
    assert body["code"] == "upstream_unavailable" and body["retryable"] is True
    ok = shim(["call", LISTING, "search-jobs", "--keywords", "x"], scenario="one-source-down")
    assert ok.returncode == 0

def test_source_unsupported_400s_non_linkedin():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "ashby"],
             scenario="source-unsupported")
    assert r.returncode != 0
    body = json.loads(r.stderr)["error"]
    assert body["code"] == "validation_error" and body["param"] == "source" \
        and body["retryable"] is False

def test_legacy_swallow_returns_linkedin_rows_without_source_echo():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "ashby"],
             scenario="legacy-source-swallow")
    data = json.loads(r.stdout)["data"]
    assert "source" not in data["query"]  # absent echo = linkedin (the E-SOURCE-IGNORED trigger)
    assert all(row["source"] == "linkedin" for row in data["results"])

def test_unknown_source_value_is_rejected():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "monster"])
    assert r.returncode != 0
    assert json.loads(r.stderr)["error"]["code"] == "validation_error"

def test_get_posting_routes_per_source_and_per_posting_id():
    default = shim(["call", LISTING, "get-posting", "--posting_id", "jp_ashbyzeph01",
                    "--source_url", "u", "--source", "ashby"], scenario="multi-source")
    assert json.loads(default.stdout)["data"]["company_name"] == "Zephyr Robotics"
    acme = shim(["call", LISTING, "get-posting", "--posting_id", "jp_ashbyacme01",
                 "--source_url", "u", "--source", "ashby"], scenario="multi-source")
    assert json.loads(acme.stdout)["data"]["company_name"] == "Acme"

def test_greenhouse_echoes_source_and_populated_posted_at():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "greenhouse"])
    data = json.loads(r.stdout)["data"]
    assert data["query"]["source"] == "greenhouse"
    assert all(row["source"] == "greenhouse" and row["posted_at"] for row in data["results"])

def test_lever_salary_html_passes_through_untouched():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "lever"])
    data = json.loads(r.stdout)["data"]
    assert data["query"]["source"] == "lever"
    assert data["results"][0]["source"] == "lever" and data["results"][0]["posted_at"]
    assert "<div>" in data["results"][0]["salary_display"]  # raw HTML preserved verbatim

def test_get_posting_greenhouse_and_lever_route_per_source():
    gh = shim(["call", LISTING, "get-posting", "--posting_id", "jp_gh0000000001",
               "--source_url", "u", "--source", "greenhouse"])
    assert json.loads(gh.stdout)["data"]["title"] == "Senior AI Engineer"
    lv = shim(["call", LISTING, "get-posting", "--posting_id", "jp_lv0000000001",
               "--source_url", "u", "--source", "lever"])
    assert json.loads(lv.stdout)["data"]["employment_type"] == "Full-time"

def test_recency_filter_echoes_and_drops_older_rows():
    # published_on_or_after echoes and keeps only rows whose effective date >= cutoff
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--published_on_or_after", "2026-06-03"])
    data = json.loads(r.stdout)["data"]
    assert data["query"]["published_on_or_after"] == "2026-06-03"
    assert [row["id"] for row in data["results"]] == ["jp_aaaaaaaaaaaa"]  # 06-03 kept; 06-02 dropped

def test_recency_filter_uses_published_at_when_posted_at_null_ashby():
    # ashby posted_at is null; the filter must use published_at (2026-06-04)
    kept = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "ashby",
                 "--published_on_or_after", "2026-06-01"])
    assert len(json.loads(kept.stdout)["data"]["results"]) == 1
    dropped = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "ashby",
                    "--published_on_or_after", "2026-06-10"])
    assert json.loads(dropped.stdout)["data"]["results"] == []

def test_recency_no_param_returns_all_rows_and_no_echo():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x"])
    data = json.loads(r.stdout)["data"]
    assert "published_on_or_after" not in data["query"]
    assert len(data["results"]) == 2  # unfiltered

def test_recency_swallow_env_ignores_param_no_echo_no_filter():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--published_on_or_after", "2026-06-03"],
             extra_env={"JOBSEARCH_TEST_RECENCY_SWALLOW": "1"})
    data = json.loads(r.stdout)["data"]
    assert "published_on_or_after" not in data["query"]  # absent echo = legacy server ignored it
    assert len(data["results"]) == 2                      # returned UNFILTERED (incl the 06-02 row)

def test_recency_bad_date_is_422_validation_error():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--published_on_or_after", "07-14-2026"])
    assert r.returncode != 0
    body = json.loads(r.stderr)["error"]
    assert body["code"] == "validation_error" and body["param"] == "published_on_or_after" \
        and body["retryable"] is False


def test_query_sensitive_ashby_returns_rows_for_role_families_not_phrase_stuffing():
    common = ["call", LISTING, "search-jobs", "--source", "ashby",
              "--location", "United States", "--limit", "25",
              "--published_on_or_after", "2026-06-01"]
    narrow = shim([*common, "--keywords",
                   "founding AI product engineer seed Series C developer tools coding agents"],
                  scenario="query-sensitive")
    product = shim([*common, "--keywords", "product engineer"],
                   scenario="query-sensitive")
    ai = shim([*common, "--keywords", "AI engineer"],
              scenario="query-sensitive")

    assert narrow.returncode == product.returncode == ai.returncode == 0
    assert json.loads(narrow.stdout)["data"]["results"] == []
    assert len(json.loads(product.stdout)["data"]["results"]) >= 1
    assert len(json.loads(ai.stdout)["data"]["results"]) >= 1


def search_page(source, cursor=None, scenario="pagination", extra_env=None):
    args = ["call", LISTING, "search-jobs", "--keywords", "AI engineer",
            "--location", "United States", "--limit", "2", "--source", source,
            "--published_on_or_after", "2026-07-01",
            "--fields", "id,source_id,source_url,title,company_name,location_display,salary_display,posted_at,published_at,detail_available,source"]
    if cursor is not None:
        args += ["--cursor", cursor]
    return shim(args, scenario=scenario, extra_env=extra_env)


def test_board_pagination_returns_opaque_cursor_then_terminal_page():
    first = json.loads(search_page("ashby").stdout)["data"]
    assert first["pagination"] == {"has_more": True, "next_cursor": "cursor_ashby_2"}
    second = json.loads(search_page("ashby", "cursor_ashby_2").stdout)["data"]
    assert second["pagination"] == {"has_more": False, "next_cursor": None}
    assert {r["source_id"] for r in first["results"]}.isdisjoint(
        {r["source_id"] for r in second["results"]})


def test_continuation_replays_every_bound_request_field(tmp_path):
    log = tmp_path / "calls.jsonl"
    env = {"JOBSEARCH_TEST_CALL_LOG": str(log)}
    assert search_page("greenhouse", extra_env=env).returncode == 0
    assert search_page("greenhouse", "cursor_greenhouse_2", extra_env=env).returncode == 0
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert calls[0]["request"] == calls[1]["request"] == {
        "keywords": "AI engineer", "location": "United States", "limit": 2,
        "source": "greenhouse", "published_on_or_after": "2026-07-01",
        "fields": "id,source_id,source_url,title,company_name,location_display,salary_display,posted_at,published_at,detail_available,source",
    }
    assert [c["cursor"] for c in calls] == [None, "cursor_greenhouse_2"]


def test_linkedin_omits_pagination_and_rejects_cursor():
    first = json.loads(search_page("linkedin").stdout)["data"]
    assert "pagination" not in first
    rejected = search_page("linkedin", "cursor_linkedin_2")
    assert rejected.returncode != 0
    error = json.loads(rejected.stderr)["error"]
    assert error["param"] == "cursor" and error["retryable"] is False


def read_calls(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_call_log_marks_free_success_failure_and_quota_rejection(tmp_path):
    log = tmp_path / "calls.jsonl"
    env = {"JOBSEARCH_TEST_CALL_LOG": str(log), "JOBSEARCH_TEST_QUOTA_AFTER": "2"}
    assert shim(["call", LISTING, "status"], extra_env=env).returncode == 0
    assert search_page("ashby", extra_env=env).returncode == 0
    failed = shim(["call", LISTING, "search-jobs", "--keywords", "x"],
                  scenario="stretch", extra_env=env)
    assert failed.returncode != 0
    quota = search_page("ashby", "cursor_ashby_2", extra_env=env)
    assert quota.returncode != 0

    calls = read_calls(log)
    assert [(c["slug"], c["outcome"], c["metered"]) for c in calls] == [
        ("status", "success", False),
        ("search-jobs", "success", True),
        ("search-jobs", "failure", True),
        ("search-jobs", "quota_rejected", False),
    ]


def test_completed_retry_and_failure_rows_are_authoritative_metering_evidence(tmp_path):
    log = tmp_path / "calls.jsonl"
    env = {"JOBSEARCH_TEST_CALL_LOG": str(log)}
    args = ["call", LISTING, "search-jobs", "--keywords", "same immutable request",
            "--source", "ashby"]

    first = shim(args, scenario="stretch", extra_env=env)
    retry = shim(args, scenario="stretch", extra_env=env)
    assert first.returncode != 0 and retry.returncode != 0

    calls = read_calls(log)
    assert len(calls) == 2
    assert calls[0]["request"] == calls[1]["request"]
    assert [(call["outcome"], call["metered"]) for call in calls] == [
        ("failure", True),
        ("failure", True),
    ]
    assert sum(call["metered"] is True for call in calls) == 2
