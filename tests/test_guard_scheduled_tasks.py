import importlib.util, json, os, time, pathlib
spec = importlib.util.spec_from_file_location(
    "guard", pathlib.Path(__file__).resolve().parents[1] / "hooks" / "guard-scheduled-tasks.py")
guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)


def _set_marker(tmp_path, choice, age=0):
    reg = tmp_path / "reg.json"
    os.environ["JOBSEARCH_OS_REGISTRY"] = str(reg)
    (tmp_path / ".sched-intent.json").write_text(json.dumps(
        {"choice": choice, "set_at_epoch": int(time.time()) - age}))


def test_launchd_with_explicit_choice_asks(tmp_path):
    _set_marker(tmp_path, "launchd")
    d = guard.decide("launchctl load ~/Library/LaunchAgents/dev.jobsearchos.run.plist")
    assert d[0] == "ask"


def test_launchd_without_marker_denies(tmp_path):
    os.environ["JOBSEARCH_OS_REGISTRY"] = str(tmp_path / "reg.json")  # no marker file
    d = guard.decide("launchctl load ~/Library/LaunchAgents/dev.jobsearchos.run.plist")
    assert d[0] == "deny"


def test_stale_marker_is_ignored_denies(tmp_path):
    _set_marker(tmp_path, "launchd", age=guard.MARKER_TTL_SECONDS + 10)
    d = guard.decide("launchctl load ~/Library/LaunchAgents/x.plist")
    assert d[0] == "deny"


def test_cron_install_asks(tmp_path):
    os.environ["JOBSEARCH_OS_REGISTRY"] = str(tmp_path / "reg.json")
    d = guard.decide('(crontab -l; echo "0 8 * * * claude -p /job-search-run") | crontab -')
    assert d[0] == "ask"


def test_reads_and_loop_and_benign_defer(tmp_path):
    os.environ["JOBSEARCH_OS_REGISTRY"] = str(tmp_path / "reg.json")
    assert guard.decide("crontab -l | grep job-search-run") is None
    assert guard.decide("python3 scripts/osctl.py schedule-line --frequency daily") is None
    assert guard.decide("echo set up /loop daily /job-search-run") is None
    assert guard.decide("agent-data call f9a6 search-jobs --keywords engineer") is None


def test_launchd_removal_and_plist_delete_defer(tmp_path):
    os.environ["JOBSEARCH_OS_REGISTRY"] = str(tmp_path / "reg.json")
    assert guard.decide("launchctl unload ~/Library/LaunchAgents/dev.jobsearchos.run.plist") is None
    assert guard.decide("rm ~/Library/LaunchAgents/dev.jobsearchos.run.plist") is None
    assert guard.decide("launchctl bootout gui/501 ~/Library/LaunchAgents/x.plist") is None
