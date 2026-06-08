import importlib.util, pathlib

spec = importlib.util.spec_from_file_location(
    "guard", pathlib.Path(__file__).resolve().parents[1] / "hooks" / "guard-scheduled-tasks.py")
guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)


def _decision(cmd):
    d = guard.decide(cmd)
    return d[0] if d else None


# --- Installs are denied: the model must never write the user's machine. ---

def test_cron_install_denies():
    assert _decision('(crontab -l 2>/dev/null; echo "0 8 * * * claude -p /job-search-run") | crontab -') == "deny"
    assert _decision("crontab -e") == "deny"
    assert _decision("crontab /tmp/my.cron") == "deny"


def test_launchd_install_denies():
    assert _decision("launchctl load ~/Library/LaunchAgents/dev.jobsearchos.run.plist") == "deny"
    assert _decision("launchctl bootstrap gui/501 ~/Library/LaunchAgents/x.plist") == "deny"
    assert _decision("cp dev.jobsearchos.run.plist ~/Library/LaunchAgents/") == "deny"
    assert _decision('cat <<EOF > ~/Library/LaunchAgents/dev.jobsearchos.run.plist') == "deny"


# --- Reads, removals, and /loop defer (not gated). ---

def test_reads_removals_and_loop_defer():
    assert _decision("crontab -l") is None
    assert _decision("crontab -l | grep job-search-run") is None
    assert _decision("crontab -r") is None                                       # removal, not an install
    assert _decision("launchctl list | grep jobsearch") is None
    assert _decision("launchctl unload ~/Library/LaunchAgents/dev.jobsearchos.run.plist") is None
    assert _decision("rm ~/Library/LaunchAgents/dev.jobsearchos.run.plist") is None
    assert _decision("echo set up /loop daily /job-search-run") is None
    assert _decision("agent-data call f9a6 search-jobs --keywords engineer") is None


# --- Regression: a command that merely MENTIONS these words is never flagged. ---
# (This is the bug that made `grep -E "crontab|launchd|..."` and the doc-search agents trip the guard.)

def test_grep_and_mentions_defer():
    assert _decision('grep -rIn -E "crontab|launchd|launchctl|schedule-line" .') is None
    assert _decision('grep -rn "launchd|crontab" docs/') is None                 # crontab after a literal pipe
    assert _decision("rg crontab docs/") is None                                 # crontab as a bare arg
    assert _decision('grep "launchctl load" hooks/') is None                     # verb phrase quoted as a pattern
    assert _decision('grep -rn "LaunchAgents" .') is None                        # plist dir mentioned, no write verb
    assert _decision("echo 'remember to set up crontab later'") is None
    assert _decision("# crontab -e would install a cron schedule") is None       # a comment
