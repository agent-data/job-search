# tests/test_osctl.py
import json, os, subprocess, sys, pathlib
SCRIPT = str(pathlib.Path(__file__).resolve().parent.parent / "scripts" / "osctl.py")

def run(args, **kw):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, **kw)

# --- resolve ---
def test_resolve_first_run_when_nothing_exists(tmp_path):
    r = run(["resolve", "--registry", str(tmp_path / "reg.json"),
             "--default-workspace", str(tmp_path / ".job-search"),
             "--legacy-workspace", str(tmp_path / "job-search")])
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out == {"workspace": str(tmp_path / ".job-search"), "first_run": True, "source": "none"}

def test_resolve_prefers_registry(tmp_path):
    ws = tmp_path / "custom"; ws.mkdir(); (ws / "config.yaml").write_text("version: 1\n")
    reg = tmp_path / "reg.json"
    run(["set-active", "--registry", str(reg), "--workspace", str(ws)])
    out = json.loads(run(["resolve", "--registry", str(reg)]).stdout)
    assert out["source"] == "registry" and out["first_run"] is False and out["workspace"] == str(ws)

def test_resolve_default_when_present(tmp_path):
    dw = tmp_path / ".job-search"; dw.mkdir(); (dw / "config.yaml").write_text("version: 1\n")
    out = json.loads(run(["resolve", "--registry", str(tmp_path / "absent.json"),
                          "--default-workspace", str(dw),
                          "--legacy-workspace", str(tmp_path / "job-search")]).stdout)
    assert out == {"workspace": str(dw), "first_run": False, "source": "default"}

def test_resolve_adopts_legacy_when_only_legacy_has_config(tmp_path):
    lw = tmp_path / "job-search"; lw.mkdir(); (lw / "config.yaml").write_text("version: 1\n")
    out = json.loads(run(["resolve", "--registry", str(tmp_path / "absent.json"),
                          "--default-workspace", str(tmp_path / ".job-search"),
                          "--legacy-workspace", str(lw)]).stdout)
    assert out == {"workspace": str(lw), "first_run": False, "source": "legacy"}

# --- set-active ---
def test_set_active_creates_nested_registry_and_abspaths(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    reg = tmp_path / "sub" / "reg.json"   # nested dir must be auto-created
    r = run(["set-active", "--registry", str(reg), "--workspace", str(ws)])
    assert r.returncode == 0
    data = json.loads(reg.read_text())
    assert data["version"] == 1 and data["active_workspace"] == str(ws.resolve())

def test_set_active_never_writes_workspace_files(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir(); (ws / "config.yaml").write_text("ORIGINAL")
    run(["set-active", "--registry", str(tmp_path / "reg.json"), "--workspace", str(ws)])
    assert (ws / "config.yaml").read_text() == "ORIGINAL"
    assert [p.name for p in ws.iterdir()] == ["config.yaml"]   # nothing added to the workspace

def test_malformed_registry_is_clean_error_not_traceback(tmp_path):
    reg = tmp_path / "reg.json"; reg.write_text("{not json")
    r = run(["resolve", "--registry", str(reg)])
    assert r.returncode == 1
    assert "Traceback" not in r.stderr and "not valid JSON" in r.stderr


def test_resolve_ignores_registry_without_active_workspace_key(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text('{"version": 1}')
    dw = tmp_path / ".job-search"; dw.mkdir(); (dw / "config.yaml").write_text("version: 1\n")
    out = json.loads(run(["resolve", "--registry", str(reg),
                          "--default-workspace", str(dw),
                          "--legacy-workspace", str(tmp_path / "job-search")]).stdout)
    assert out["source"] == "default"


def test_resolve_registry_points_to_uninitialized_workspace_is_first_run(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()   # registered but no config.yaml yet
    reg = tmp_path / "reg.json"
    run(["set-active", "--registry", str(reg), "--workspace", str(ws)])
    out = json.loads(run(["resolve", "--registry", str(reg)]).stdout)
    assert out["source"] == "registry" and out["first_run"] is True and out["workspace"] == str(ws.resolve())


def test_set_active_with_bare_registry_filename_is_clean(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    r = run(["set-active", "--registry", "reg.json", "--workspace", str(ws)], cwd=tmp_path)
    assert r.returncode == 0
    assert (tmp_path / "reg.json").exists()
    assert "Traceback" not in r.stderr


def test_resolve_uses_env_registry_override(tmp_path):
    ws = tmp_path / "custom"; ws.mkdir(); (ws / "config.yaml").write_text("version: 1\n")
    reg = tmp_path / "reg.json"
    env = {**os.environ, "JOBSEARCH_OS_REGISTRY": str(reg)}
    run(["set-active", "--workspace", str(ws)], env=env)   # no --registry flag; resolves via env
    out = json.loads(run(["resolve"], env=env).stdout)
    assert out["source"] == "registry" and out["workspace"] == str(ws.resolve())


# --- schedule-line ---
def test_schedule_line_daily_uses_time_and_workspace(tmp_path):
    line = run(["schedule-line", "--frequency", "daily", "--time", "08:00", "--workspace", "/ws"]).stdout.strip()
    assert line.startswith("0 8 * * * ")
    assert 'cd /ws && claude -p "/job-search-run" >> /ws/runs/cron.log 2>&1' in line

def test_schedule_line_hourly(tmp_path):
    assert run(["schedule-line", "--frequency", "hourly", "--workspace", "/ws"]).stdout.strip().startswith("0 * * * * ")

def test_schedule_line_every_6_hours(tmp_path):
    assert run(["schedule-line", "--frequency", "every-6-hours", "--workspace", "/ws"]).stdout.strip().startswith("0 */6 * * * ")

def test_schedule_line_weekly_monday(tmp_path):
    assert run(["schedule-line", "--frequency", "weekly", "--time", "09:30", "--workspace", "/ws"]).stdout.strip().startswith("30 9 * * 1 ")

def test_schedule_line_unknown_frequency_errors(tmp_path):
    r = run(["schedule-line", "--frequency", "fortnightly", "--workspace", "/ws"])
    assert r.returncode == 1 and "unknown frequency" in r.stderr

# --- launchd-plist ---
def test_launchd_plist_daily_has_calendar_and_log(tmp_path):
    out = run(["launchd-plist", "--frequency", "daily", "--time", "08:00", "--workspace", "/ws"]).stdout
    assert "StartCalendarInterval" in out and "<integer>8</integer>" in out and "/ws/runs/cron.log" in out


# --- schedule-status / set-scheduled ---
def test_schedule_status_default_not_installed(tmp_path):
    out = json.loads(run(["schedule-status", "--registry", str(tmp_path / "absent.json")]).stdout)
    assert out == {"installed": False, "mechanism": None, "set_at": None}

def test_set_scheduled_roundtrip_and_preserves_active(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    reg = tmp_path / "reg.json"
    run(["set-active", "--registry", str(reg), "--workspace", str(ws)])
    run(["set-scheduled", "--registry", str(reg), "--mechanism", "launchd", "--set-at", "2026-06-05T08:00:00+00:00"])
    data = json.loads(reg.read_text())
    assert data["active_workspace"] == str(ws.resolve())
    assert data["scheduling"] == {"installed": True, "mechanism": "launchd", "set_at": "2026-06-05T08:00:00+00:00"}
    out = json.loads(run(["schedule-status", "--registry", str(reg)]).stdout)
    assert out["installed"] is True and out["mechanism"] == "launchd"

def test_set_active_preserves_scheduling(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    reg = tmp_path / "reg.json"
    run(["set-scheduled", "--registry", str(reg), "--mechanism", "cron", "--set-at", "2026-06-05T08:00:00+00:00"])
    run(["set-active", "--registry", str(reg), "--workspace", str(ws)])
    assert json.loads(reg.read_text())["scheduling"]["mechanism"] == "cron"
