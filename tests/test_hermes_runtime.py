# tests/test_hermes_runtime.py
# Exercises the bundled stdlib-Python state-ops runtime (runtime/hermes_job_search/) the Hermes
# adapter invokes via the terminal tool. Subprocess-style, like test_fake_agent_data.py: every
# command prints exactly one JSON object to stdout and exits 0/non-0.
import json, os, subprocess, pathlib

CLI = str(pathlib.Path(__file__).resolve().parents[1] / "runtime" / "hermes_job_search" / "cli.py")
# Isolate from the real machine: tests must drive every path via these env vars (or flags).
_ISOLATE = ("JOBSEARCH_OS_REGISTRY", "JOBSEARCH_OS_HOME", "XDG_CONFIG_HOME")


def run(args, env=None, stdin=None):
    e = {k: v for k, v in os.environ.items() if k not in _ISOLATE}
    if env:
        e.update(env)
    return subprocess.run(["python3", CLI, *args], capture_output=True, text=True, env=e, input=stdin)


def out(r):
    """Parse the single stdout JSON object; assert nothing leaked onto a second line."""
    assert r.stdout.strip(), f"no stdout; stderr={r.stderr!r}"
    obj = json.loads(r.stdout)  # one object, parses clean
    return obj


# ---------- workspace discovery ----------

def test_discover_workspace_first_run(tmp_path):
    env = {"JOBSEARCH_OS_HOME": str(tmp_path), "JOBSEARCH_OS_REGISTRY": str(tmp_path / "reg.json")}
    o = out(run(["discover-workspace"], env=env))
    assert o["ok"] is True
    assert o["first_run"] is True
    assert o["source"] == "none"
    assert o["workspace"] == str(tmp_path / ".job-search")


def test_discover_workspace_registry_wins_even_without_config(tmp_path):
    reg, ws = tmp_path / "reg.json", tmp_path / "custom-ws"
    reg.write_text(json.dumps({"version": 1, "active_workspace": str(ws)}))
    env = {"JOBSEARCH_OS_HOME": str(tmp_path), "JOBSEARCH_OS_REGISTRY": str(reg)}
    o = out(run(["discover-workspace"], env=env))
    assert o["source"] == "registry"
    assert o["workspace"] == str(ws)
    assert o["first_run"] is True  # ws has no config.yaml, but registry still wins


def test_discover_workspace_default_precedence(tmp_path):
    (tmp_path / ".job-search").mkdir()
    (tmp_path / ".job-search" / "config.yaml").write_text("version: 1\n")
    env = {"JOBSEARCH_OS_HOME": str(tmp_path), "JOBSEARCH_OS_REGISTRY": str(tmp_path / "absent.json")}
    o = out(run(["discover-workspace"], env=env))
    assert o["source"] == "default"
    assert o["first_run"] is False
    assert o["workspace"] == str(tmp_path / ".job-search")


def test_discover_workspace_legacy(tmp_path):
    (tmp_path / "job-search").mkdir()
    (tmp_path / "job-search" / "config.yaml").write_text("version: 1\n")
    env = {"JOBSEARCH_OS_HOME": str(tmp_path), "JOBSEARCH_OS_REGISTRY": str(tmp_path / "absent.json")}
    o = out(run(["discover-workspace"], env=env))
    assert o["source"] == "legacy"
    assert o["workspace"] == str(tmp_path / "job-search")


def test_discover_workspace_invalid_registry_does_not_fall_through(tmp_path):
    # A corrupt registry must stop loudly, never silently switch to a default workspace.
    reg = tmp_path / "reg.json"
    reg.write_text("{ not json")
    (tmp_path / ".job-search").mkdir()
    (tmp_path / ".job-search" / "config.yaml").write_text("version: 1\n")
    env = {"JOBSEARCH_OS_HOME": str(tmp_path), "JOBSEARCH_OS_REGISTRY": str(reg)}
    r = run(["discover-workspace"], env=env)
    assert r.returncode != 0
    assert out(r)["error"] == "registry_invalid_json"


# ---------- registry path + read ----------

def test_registry_default_path_uses_job_search_not_job_search_os(tmp_path):
    # No JOBSEARCH_OS_REGISTRY -> XDG/job-search/config.json (the current contract; NOT job-search-os).
    env = {"JOBSEARCH_OS_HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "xdg")}
    o = out(run(["read-registry"], env=env))
    assert o["path"] == str(tmp_path / "xdg" / "job-search" / "config.json")
    assert o["registry"] is None  # file absent


def test_read_registry_invalid_json_errors(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text("{ broken")
    r = run(["read-registry"], env={"JOBSEARCH_OS_REGISTRY": str(reg)})
    assert r.returncode != 0
    assert out(r)["error"] == "registry_invalid_json"


# ---------- registry write (set-active) ----------

def test_set_active_workspace_writes_registry(tmp_path):
    reg, ws = tmp_path / "reg.json", tmp_path / "ws"
    o = out(run(["set-active-workspace", "--workspace", str(ws)], env={"JOBSEARCH_OS_REGISTRY": str(reg)}))
    assert o["ok"] is True
    text = reg.read_text()
    data = json.loads(text)
    assert data["version"] == 1
    assert data["active_workspace"] == str(ws)  # absolute path stored
    assert text.endswith("\n")           # trailing newline
    assert '  "active_workspace"' in text  # 2-space indent


def test_set_active_workspace_preserves_other_keys(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"version": 1, "scheduling": {"installed": True, "mechanism": "loop", "set_at": "t"}}))
    run(["set-active-workspace", "--workspace", str(tmp_path / "ws")], env={"JOBSEARCH_OS_REGISTRY": str(reg)})
    data = json.loads(reg.read_text())
    assert data["scheduling"]["mechanism"] == "loop"   # untouched
    assert data["active_workspace"] == str(tmp_path / "ws")


def test_registry_write_is_atomic_no_tmp_left(tmp_path):
    reg = tmp_path / "reg.json"
    run(["set-active-workspace", "--workspace", str(tmp_path / "ws")], env={"JOBSEARCH_OS_REGISTRY": str(reg)})
    assert [p.name for p in tmp_path.iterdir() if ".tmp" in p.name] == []


# ---------- scheduling marker (hermes-cron + optional job_id/deliver) ----------

def test_set_scheduling_hermes_cron_with_job_id_and_deliver(tmp_path):
    reg = tmp_path / "reg.json"
    o = out(run(["set-scheduling", "--job-id", "abc123def456", "--deliver", "origin",
                 "--set-at", "2026-06-29T09:00:00+00:00"], env={"JOBSEARCH_OS_REGISTRY": str(reg)}))
    sch = o["scheduling"]
    assert sch["installed"] is True
    assert sch["mechanism"] == "hermes-cron"      # the Hermes-native default
    assert sch["job_id"] == "abc123def456"
    assert sch["deliver"] == "origin"
    assert sch["set_at"] == "2026-06-29T09:00:00+00:00"


def test_set_scheduling_omits_optional_fields_when_absent(tmp_path):
    # job_id / deliver are additive: when not given, the marker stays minimal (back-compat with the
    # Claude `loop` shape {installed, mechanism, set_at}).
    reg = tmp_path / "reg.json"
    sch = out(run(["set-scheduling", "--set-at", "t"], env={"JOBSEARCH_OS_REGISTRY": str(reg)}))["scheduling"]
    assert sch["mechanism"] == "hermes-cron"
    assert "job_id" not in sch and "deliver" not in sch


def test_clear_scheduling_preserves_version_and_active(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"version": 1, "active_workspace": "/x",
                               "scheduling": {"installed": True, "mechanism": "hermes-cron",
                                              "set_at": "t", "job_id": "j"}}))
    sch = out(run(["clear-scheduling"], env={"JOBSEARCH_OS_REGISTRY": str(reg)}))["scheduling"]
    assert sch == {"installed": False, "mechanism": None, "set_at": None}
    data = json.loads(reg.read_text())
    assert data["active_workspace"] == "/x"   # preserved
    assert data["version"] == 1


def test_read_registry_with_loop_mechanism_roundtrips(tmp_path):
    # A Claude host's registry (mechanism: loop) must read without error — one shared cross-host registry.
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"version": 1, "scheduling": {"installed": True, "mechanism": "loop", "set_at": "t"}}))
    o = out(run(["read-registry"], env={"JOBSEARCH_OS_REGISTRY": str(reg)}))
    assert o["registry"]["scheduling"]["mechanism"] == "loop"


# ---------- config load + surgical update (stdlib-only YAML) ----------

SAMPLE_CONFIG = '''version: 1
workspace:
  preferences_path: "preferences.md"
  master_resume_path: "resumes/master.md"
queries:
  - { id: "ai-eng",  keywords: "AI, ML engineer", location: "United States", limit: 25, enabled: true }
search:
  freshness: "past-2-weeks"    # any | past-week | past-2-weeks | past-month
  detail_model: "fast"         # fast | balanced | high | inherit
schedule:
  frequency: "daily"           # hourly | every-2-hours | every-6-hours | daily | weekly
  time: "08:00"
  timezone: "America/Los_Angeles"
notify:
  digest_path_template: "reports/{date}-digest.md"
  desktop_notify_on_block: true
'''


def _ws_with_config(tmp_path, text=SAMPLE_CONFIG):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "config.yaml").write_text(text)
    return ws


def test_load_config_roundtrips_documented_fields(tmp_path):
    ws = _ws_with_config(tmp_path)
    cfg = out(run(["load-config", "--workspace", str(ws)]))["config"]
    assert cfg["version"] == 1
    assert cfg["workspace"]["preferences_path"] == "preferences.md"
    assert cfg["search"]["freshness"] == "past-2-weeks"
    assert cfg["search"]["detail_model"] == "fast"
    assert cfg["schedule"]["frequency"] == "daily"
    assert cfg["schedule"]["time"] == "08:00"
    assert cfg["notify"]["desktop_notify_on_block"] is True


def test_load_config_keeps_comma_inside_quoted_keywords(tmp_path):
    ws = _ws_with_config(tmp_path)
    q = out(run(["load-config", "--workspace", str(ws)]))["config"]["queries"][0]
    assert q["id"] == "ai-eng"
    assert q["keywords"] == "AI, ML engineer"   # comma inside quotes must NOT split the flow-map
    assert q["limit"] == 25
    assert q["enabled"] is True


def test_load_config_missing_is_named_error(tmp_path):
    r = run(["load-config", "--workspace", str(tmp_path / "nope")])
    assert r.returncode != 0
    assert out(r)["error"] == "E-NO-CONFIG"


def test_load_config_newer_version_is_named_error(tmp_path):
    ws = _ws_with_config(tmp_path, SAMPLE_CONFIG.replace("version: 1", "version: 2"))
    r = run(["load-config", "--workspace", str(ws)])
    assert r.returncode != 0
    assert out(r)["error"] == "E-CONFIG-VERSION"


def test_update_config_set_is_surgical_and_preserves_comment(tmp_path):
    ws = _ws_with_config(tmp_path)
    before = (ws / "config.yaml").read_text().splitlines()
    o = out(run(["update-config", "--workspace", str(ws), "--set", "search.freshness=past-week"]))
    assert o["changed"] == ["search.freshness"]
    after = (ws / "config.yaml").read_text().splitlines()
    fl = [ln for ln in after if "freshness:" in ln][0]
    assert '"past-week"' in fl
    assert "# any | past-week" in fl                       # inline comment preserved
    assert [ln for ln in before if "freshness:" not in ln] == [ln for ln in after if "freshness:" not in ln]


def test_update_config_set_bool(tmp_path):
    ws = _ws_with_config(tmp_path)
    out(run(["update-config", "--workspace", str(ws), "--set", "notify.desktop_notify_on_block=false"]))
    cfg = out(run(["load-config", "--workspace", str(ws)]))["config"]
    assert cfg["notify"]["desktop_notify_on_block"] is False


def test_update_config_rejects_unknown_key(tmp_path):
    ws = _ws_with_config(tmp_path)
    r = run(["update-config", "--workspace", str(ws), "--set", "search.detail_modell=fast"])
    assert r.returncode != 0
    assert out(r)["error"] == "config_key_not_allowed"


def test_update_config_cannot_set_a_score_key(tmp_path):
    # philosophy: the runtime structurally cannot write a numeric fit score/weight.
    ws = _ws_with_config(tmp_path)
    r = run(["update-config", "--workspace", str(ws), "--set", "search.fit_score=80"])
    assert r.returncode != 0
    assert out(r)["error"] == "config_key_not_allowed"


def test_update_config_add_query_appends_item(tmp_path):
    ws = _ws_with_config(tmp_path)
    q = {"id": "ml-sf", "keywords": "ML platform", "location": "SF Bay Area", "limit": 30, "enabled": True}
    o = out(run(["update-config", "--workspace", str(ws), "--add-query"], stdin=json.dumps(q)))
    assert "queries[+]" in o["changed"]
    cfg = out(run(["load-config", "--workspace", str(ws)]))["config"]
    new = [x for x in cfg["queries"] if x["id"] == "ml-sf"]
    assert len(new) == 1
    assert new[0]["keywords"] == "ML platform" and new[0]["limit"] == 30 and new[0]["enabled"] is True


# ---------- jobs.jsonl event log: known-ids, append, fold ----------

def test_known_ids_dedups_preserving_order(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"evaluated","source_id":"1001","title":"A"}\n'
        '{"event":"evaluated","source_id":"1002","title":"B"}\n'
        '{"event":"status_changed","source_id":"1001","status":"interested"}\n'
    )
    o = out(run(["known-ids", "--jobs", str(jobs)]))
    assert o["known_ids"] == ["1001", "1002"]
    assert o["count"] == 2


def test_known_ids_missing_file_is_empty(tmp_path):
    o = out(run(["known-ids", "--jobs", str(tmp_path / "nope.jsonl")]))
    assert o["known_ids"] == [] and o["count"] == 0


def test_known_ids_via_workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "jobs.jsonl").write_text('{"event":"evaluated","source_id":"w1"}\n')
    assert out(run(["known-ids", "--workspace", str(ws)]))["known_ids"] == ["w1"]


def test_append_event_validates_and_appends_single_line(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    ev = {"event": "evaluated", "source_id": "2001", "title": "X", "match": "strong"}
    o = out(run(["append-event", "--jobs", str(jobs)], stdin=json.dumps(ev)))
    assert o["appended"] is True and o["source_id"] == "2001"
    lines = jobs.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["source_id"] == "2001"
    assert lines[0].count('"source_id"') == 1   # event-line contract


def test_append_event_rejects_non_dict(tmp_path):
    r = run(["append-event", "--jobs", str(tmp_path / "jobs.jsonl")], stdin=json.dumps([1, 2, 3]))
    assert r.returncode != 0
    assert out(r)["error"] == "event_invalid"


def test_append_event_rejects_missing_source_id(tmp_path):
    r = run(["append-event", "--jobs", str(tmp_path / "jobs.jsonl")],
            stdin=json.dumps({"event": "evaluated", "title": "x"}))
    assert r.returncode != 0
    assert out(r)["error"] == "event_invalid"


def test_fold_last_write_wins_and_drops_event_key(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"evaluated","source_id":"3001","status":"new","match":"weak","needs_human_check":false}\n'
        '{"event":"status_changed","source_id":"3001","status":"interested"}\n'
    )
    recs = out(run(["fold-state", "--jobs", str(jobs)]))["records"]
    assert len(recs) == 1
    assert recs[0]["status"] == "interested"   # later event overrides
    assert recs[0]["match"] == "weak"          # earlier field retained
    assert "event" not in recs[0]              # the event key is stripped


def test_fold_tally_counts_status_and_needs_human_check(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"evaluated","source_id":"a","status":"new","needs_human_check":true}\n'
        '{"event":"evaluated","source_id":"b","status":"interested","needs_human_check":false}\n'
        '{"event":"evaluated","source_id":"c","status":"new","needs_human_check":false}\n'
    )
    t = out(run(["fold-state", "--jobs", str(jobs)]))["tally"]
    assert t["by_status"]["new"] == 2
    assert t["by_status"]["interested"] == 1
    assert t["needs_human_check"] == 1
    assert t["total"] == 3


def test_fold_malformed_line_errors_with_line_number(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text('{"event":"evaluated","source_id":"ok"}\n{ broken json\n')
    r = run(["fold-state", "--jobs", str(jobs)])
    assert r.returncode != 0
    o = out(r)
    assert o["error"] == "jobs_malformed_json"
    assert "line 2" in o["message"]


# ---------- run-record + digest writers ----------

def test_write_run_record_healthy(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    rec = {"run_id": "2026-06-29T09-00-00Z", "run_health": "healthy", "results_summary": {"strong": 3}}
    o = out(run(["write-run-record", "--workspace", str(ws)], stdin=json.dumps(rec)))
    assert o["run_health"] == "healthy"
    p = pathlib.Path(o["path"])
    assert p.exists() and p.name == "2026-06-29T09-00-00Z.json"
    assert json.loads(p.read_text())["run_id"] == rec["run_id"]


def test_write_run_record_requires_run_id(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    r = run(["write-run-record", "--workspace", str(ws)], stdin=json.dumps({"run_health": "healthy"}))
    assert r.returncode != 0
    assert out(r)["error"] == "run_record_invalid"


def test_write_run_record_validates_run_health(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    r = run(["write-run-record", "--workspace", str(ws)], stdin=json.dumps({"run_id": "x", "run_health": "great"}))
    assert r.returncode != 0
    assert out(r)["error"] == "run_record_invalid"


def test_write_run_record_blocked_carries_named_error(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    rec = {"run_id": "r1", "run_health": "blocked", "error": {"code": "E-NO-AUTH", "message": "not authed"}}
    o = out(run(["write-run-record", "--workspace", str(ws)], stdin=json.dumps(rec)))
    data = json.loads(pathlib.Path(o["path"]).read_text())
    assert data["run_health"] == "blocked" and data["error"]["code"] == "E-NO-AUTH"


DIGEST_PAYLOAD = {
    "date": "2026-06-05", "run_health": "healthy",
    "counts": {"new": 9, "strong": 2, "moderate": 1, "weak": 1, "filtered": 1, "searches": 2, "detail_reads": 5},
    "strong": [{"title": "Senior PD", "company": "Tidewater", "location": "Remote (US)",
                "reasoning": "Owns a care-nav area.", "url": "https://x/1"}],
    "moderate": [{"title": "PD (Senior)", "company": "Meridian", "location": "Hybrid, Seattle",
                  "reasoning": "Logistics domain.", "url": "https://x/2", "confirm": "Remote seat?"}],
    "weak": [{"title": "PD", "company": "Northwind", "location": "Hybrid, Portland",
              "reasoning": "Mid-level scope.", "url": "https://x/3"}],
    "filtered": [{"title": "Brand Designer", "company": "Lumen", "why": "brand not product (must-have)"}],
    "notes": ["1 detail link expired; judged from summary."],
}


def _digest(tmp_path, payload, date="2026-06-05"):
    ws = tmp_path / "ws"
    ws.mkdir()
    o = out(run(["write-digest", "--workspace", str(ws), "--date", date], stdin=json.dumps(payload)))
    return pathlib.Path(o["path"]).read_text(), o


def test_write_digest_healthy_shape(tmp_path):
    md, o = _digest(tmp_path, DIGEST_PAYLOAD)
    assert pathlib.Path(o["path"]).name == "2026-06-05-digest.md"
    assert md.startswith("# Job search digest — 2026-06-05\n")
    assert "Run health: healthy\n" in md
    assert "9 new postings · 2 strong · 1 moderate · 1 weak · 1 filtered out · 2 searches · 5 detail reads" in md
    assert "## Strong matches" in md
    assert "- **Senior PD** — Tidewater — Remote (US)" in md
    assert "  Owns a care-nav area.  [view](https://x/1)" in md
    assert "## Moderate matches" in md
    assert "  ⚠ confirm: Remote seat?" in md
    assert "## Weak matches" in md
    assert "## Filtered out (not relevant): 1" in md
    assert "- Brand Designer — Lumen — brand not product (must-have)" in md
    assert "_Notes:_" in md


def test_write_digest_has_no_numeric_score(tmp_path):
    import re
    md, _ = _digest(tmp_path, DIGEST_PAYLOAD)
    assert "fit score" not in md.lower()
    assert not re.search(r"\b\d{1,3}\s*/\s*100\b", md)
    assert not re.search(r"\b\d+\s*(points|pts)\b", md, re.I)


def test_write_digest_partial_decorates_health_line(tmp_path):
    payload = dict(DIGEST_PAYLOAD, run_health="partial", error_count=2)
    md, _ = _digest(tmp_path, payload)
    assert "Run health: partial (2 errors)" in md


def test_write_digest_blocked_replaces_body_with_named_error(tmp_path):
    payload = {"date": "2026-06-05", "run_health": "blocked",
               "error": {"code": "E-NO-AUTH", "message": "agent-data is not authenticated. Run agent-data whoami."}}
    md, _ = _digest(tmp_path, payload)
    assert "Run health: blocked (action needed)" in md
    assert "**E-NO-AUTH** — agent-data is not authenticated" in md
    assert "## Strong matches" not in md   # body replaced by the named error


# ---------- end-to-end CLI matrix + fixtures ----------

_FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "hermes_runtime"


def test_digest_byte_matches_fixture(tmp_path):
    payload = json.loads((_FIX / "digest.healthy.payload.json").read_text())
    ws = tmp_path / "ws"
    ws.mkdir()
    o = out(run(["write-digest", "--workspace", str(ws), "--date", "2026-06-05"], stdin=json.dumps(payload)))
    assert pathlib.Path(o["path"]).read_text() == (_FIX / "digest.healthy.expected.md").read_text()


def test_end_to_end_run_lifecycle(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    reg = tmp_path / "reg.json"
    ws = home / ".job-search"
    env = {"JOBSEARCH_OS_HOME": str(home), "JOBSEARCH_OS_REGISTRY": str(reg)}

    # 1) first run -> default workspace, no config yet
    o = out(run(["discover-workspace"], env=env))
    assert o["first_run"] is True and o["workspace"] == str(ws)

    # 2) adopt the workspace + (simulating onboarding) create config.yaml
    out(run(["set-active-workspace", "--workspace", str(ws)], env=env))
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "config.yaml").write_text("version: 1\n")

    # 3) append evaluated events + a status change
    for ev in (
        {"event": "evaluated", "source_id": "p1", "status": "new", "match": "strong", "needs_human_check": False},
        {"event": "evaluated", "source_id": "p2", "status": "new", "match": "weak", "needs_human_check": True},
    ):
        out(run(["append-event", "--workspace", str(ws)], env=env, stdin=json.dumps(ev)))
    out(run(["append-event", "--workspace", str(ws)], env=env,
            stdin=json.dumps({"event": "status_changed", "source_id": "p1", "status": "interested"})))

    # 4) known-ids dedups to 2; fold reflects last-write-wins + tally
    assert out(run(["known-ids", "--workspace", str(ws)], env=env))["count"] == 2
    folded = out(run(["fold-state", "--workspace", str(ws)], env=env))
    assert {r["source_id"]: r["status"] for r in folded["records"]} == {"p1": "interested", "p2": "new"}
    assert folded["tally"]["needs_human_check"] == 1

    # 5) write run record + digest as durable artifacts
    out(run(["write-run-record", "--workspace", str(ws)], env=env,
            stdin=json.dumps({"run_id": "2026-06-29T09-00-00Z", "run_health": "healthy"})))
    out(run(["write-digest", "--workspace", str(ws), "--date", "2026-06-29"], env=env,
            stdin=json.dumps({"run_health": "healthy",
                              "counts": {"new": 2, "strong": 1, "moderate": 0, "weak": 1,
                                         "filtered": 0, "searches": 1, "detail_reads": 2}})))
    assert (ws / "runs" / "2026-06-29T09-00-00Z.json").exists()
    assert (ws / "reports" / "2026-06-29-digest.md").exists()

    # 6) a later discovery now sees the populated, registry-active workspace (not a first run)
    o2 = out(run(["discover-workspace"], env=env))
    assert o2["source"] == "registry" and o2["first_run"] is False


def test_handled_errors_are_envelopes_not_tracebacks(tmp_path):
    bad_reg = tmp_path / "bad.json"
    bad_reg.write_text("{ not json")
    cases = [
        (["read-registry"], {"JOBSEARCH_OS_REGISTRY": str(bad_reg)}, None),
        (["discover-workspace"], {"JOBSEARCH_OS_REGISTRY": str(bad_reg)}, None),
        (["load-config", "--workspace", str(tmp_path / "absent")], None, None),
        (["append-event", "--jobs", str(tmp_path / "j.jsonl")], None, json.dumps({"no": "source_id"})),
        (["write-run-record", "--workspace", str(tmp_path)], None, json.dumps({"run_health": "healthy"})),
        (["update-config", "--workspace", str(tmp_path), "--set", "search.fit_score=80"], None, None),
    ]
    for args, env, stdin in cases:
        r = run(args, env=env, stdin=stdin)
        assert r.returncode != 0, args
        body = out(r)                       # exactly one JSON object on stdout
        assert body["ok"] is False and body["error"], args
        assert "Traceback (most recent call last)" not in r.stderr, args
