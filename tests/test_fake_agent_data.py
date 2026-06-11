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
    assert body["code"] == "detail_fetch_failed" and body["retryable"] is True

def test_error_scenario_reuses_happy_search_fixture():
    # 'degraded' has no own search-jobs fixture; it must fall back to happy's 2-result fixture
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x"], scenario="degraded")
    assert r.returncode == 0
    assert len(json.loads(r.stdout)["data"]["results"]) == 2

def test_bad_query_422_on_sentinel_location():
    # E-BAD-QUERY: a query whose location carries the INVALID sentinel returns 422 invalid_request
    # with details[].loc naming the bad param, non-retryable (the run skips it, never retries).
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--location", "INVALID-ZZ"],
             scenario="bad-query")
    assert r.returncode != 0
    body = json.loads(r.stderr)["error"]
    assert body["code"] == "invalid_request" and body["retryable"] is False
    assert body["param"] == "location"
    assert body["details"][0]["loc"][-1] == "location"

def test_bad_query_scenario_passes_through_valid_location():
    # a query without the sentinel still returns the happy fixture, so OTHER queries continue the same run
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--location", "United States"],
             scenario="bad-query")
    assert r.returncode == 0
    assert len(json.loads(r.stdout)["data"]["results"]) == 2
