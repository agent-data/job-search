# tests/test_osctl.py
import json, subprocess, sys, pathlib
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
