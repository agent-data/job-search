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
