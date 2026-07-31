"""Unit tests for `shared/scripts/mechanics/validate-workspace.sh`.

Every mechanical rule about workspace files lives in that one script: which keys `config.yaml` must
carry and what shape their values take, the front matter `preferences.md` needs, the fields a run
record in `runs/` must get right, and the leftovers a finished run must not leave behind. The script
prints one `INVALID <file> <rule>` line per broken rule and exits 1; a workspace with nothing wrong
prints nothing and exits 0.

Scripts are the one place ordinary unit tests belong — skill behavior is graded by `evals/` instead —
so each test here builds a temp workspace, runs the script through POSIX `sh` (never bash), and
asserts the exact line it prints.

`search.detail_model` is deliberately absent from the rules. The validator does not require it and
does not look at its value, whatever a workspace has written there.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "shared" / "scripts" / "mechanics" / "validate-workspace.sh"
SEED_WORKSPACE = ROOT / "evals" / "seeds" / "headless-run"
CONFIG_TEMPLATE = ROOT / "templates" / "config.example.yaml"
PREFERENCES_TEMPLATE = ROOT / "templates" / "preferences.example.md"

RUN_ID = "2026-07-16T14-30-00Z"

VALID_PREFERENCES = """---
created_at: 2026-07-30
updated_at: 2026-07-30
---
# Job Preferences Brief

**Summary:** Senior AI engineer, individual contributor, remote in the US.

## Must-haves / dealbreakers
- Remote within the US.
"""

CONFIG_BLOCKS = {
    "version": ["version: 2"],
    "workspace": ["workspace:", '  preferences_path: "preferences.md"'],
    "queries": [
        "queries:",
        '  - { id: "ai-eng-remote", keywords: "AI engineer", location: "United States", '
        "limit: 25, enabled: true }",
    ],
    "search": [
        "search:",
        "@sources",
        '  freshness: "past-2-weeks"    # any | past-week | past-2-weeks | past-month',
    ],
    "schedule": [
        "schedule:",
        '  frequency: "daily"',
        '  time: "08:00"',
        '  timezone: "America/Los_Angeles"',
    ],
    "notify": ["notify:", '  digest_path_template: "reports/{date}-digest.md"'],
}


def config_text(detail_model=None, drop_blocks=(), sources='["linkedin", "ashby"]'):
    """A config.yaml body. `detail_model=None` omits the optional key; `sources=None` drops it."""
    lines = []
    for name, block in CONFIG_BLOCKS.items():
        if name in drop_blocks:
            continue
        for line in block:
            if line != "@sources":
                lines.append(line)
                continue
            if sources is not None:
                lines.append(
                    "  sources: %s   # linkedin | ashby | greenhouse | lever" % sources
                )
            if detail_model is not None:
                lines.append("  detail_model: %s" % detail_model)
    return "\n".join(lines) + "\n"


def run_record(run_id=RUN_ID, **overrides):
    """A run record carrying the fields the slim schema and the current schema agree on."""
    record = {
        "run_id": run_id,
        "trigger": "manual",
        "scheduler_id": None,
        "close_state": "complete",
        "run_health": "healthy",
        "sources": ["linkedin", "ashby"],
        "queries": ["ai-eng-remote"],
        "agent_data_usage": {
            "searches": 2,
            "detail_reads": 5,
            "other": 0,
            "total_metered": 7,
        },
        "started_at": "2026-07-16T14:30:00Z",
        "completed_at": "2026-07-16T14:41:12Z",
    }
    record.update(overrides)
    return record


def write_run(workspace, record):
    path = workspace / "runs" / ("%s.json" % record["run_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def tmp_workspace(tmp_path):
    """A workspace with nothing wrong with it: valid config, valid brief, one valid run record."""
    workspace = tmp_path / "workspace"
    (workspace / "runs").mkdir(parents=True)
    (workspace / "config.yaml").write_text(config_text(), encoding="utf-8")
    (workspace / "preferences.md").write_text(VALID_PREFERENCES, encoding="utf-8")
    write_run(workspace, run_record())
    return workspace


def run_validator(workspace, *args, shell="sh"):
    return subprocess.run(
        [shell, str(VALIDATOR), str(workspace), *args],
        capture_output=True,
        text=True,
    )


# ----------------------------------------------------------------- a workspace with nothing wrong


def test_valid_workspace_passes(tmp_workspace):
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == ""


def test_workspace_without_runs_directory_passes(tmp_workspace):
    shutil.rmtree(tmp_workspace / "runs")
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr


def test_seed_workspace_passes():
    """The eval seed is a real workspace; it stays valid."""
    r = run_validator(SEED_WORKSPACE)
    assert r.returncode == 0, r.stdout + r.stderr


def test_workspace_built_from_the_templates_passes(tmp_path):
    """A new workspace copied straight from `templates/` validates."""
    workspace = tmp_path / "from-templates"
    workspace.mkdir()
    shutil.copyfile(CONFIG_TEMPLATE, workspace / "config.yaml")
    shutil.copyfile(PREFERENCES_TEMPLATE, workspace / "preferences.md")
    r = run_validator(workspace)
    assert r.returncode == 0, r.stdout + r.stderr


# ------------------------------------------------------------------------------- config.yaml keys


def test_missing_config_fails(tmp_workspace):
    (tmp_workspace / "config.yaml").unlink()
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID config.yaml missing-file" in r.stdout


@pytest.mark.parametrize(
    "block,key", [("version", "version"), ("queries", "queries"), ("schedule", "schedule")]
)
def test_missing_required_top_level_key_fails(tmp_workspace, block, key):
    (tmp_workspace / "config.yaml").write_text(
        config_text(drop_blocks=(block,)), encoding="utf-8"
    )
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID config.yaml missing-key %s" % key in r.stdout


def test_missing_search_sources_fails(tmp_workspace):
    (tmp_workspace / "config.yaml").write_text(config_text(sources=None), encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID config.yaml missing-key search.sources" in r.stdout


def test_empty_search_sources_fails(tmp_workspace):
    (tmp_workspace / "config.yaml").write_text(config_text(sources="[]"), encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID config.yaml empty-value search.sources" in r.stdout


@pytest.mark.parametrize("sources", ["['linkedin']", '["linkedin","ashby","greenhouse","lever"]'])
def test_other_sources_spellings_pass(tmp_workspace, sources):
    (tmp_workspace / "config.yaml").write_text(config_text(sources=sources), encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr


def test_non_numeric_version_fails(tmp_workspace):
    (tmp_workspace / "config.yaml").write_text(
        config_text().replace("version: 2", 'version: "two"'), encoding="utf-8"
    )
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID config.yaml version-not-a-number two" in r.stdout


def test_commented_out_key_does_not_count_as_present(tmp_workspace):
    (tmp_workspace / "config.yaml").write_text(
        config_text(drop_blocks=("version",)).replace(
            "workspace:", "# version: 2\nworkspace:"
        ),
        encoding="utf-8",
    )
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID config.yaml missing-key version" in r.stdout


# --------------------------------------------------------------- config.yaml search.detail_model


def test_config_without_detail_model_passes(tmp_workspace):
    """The validator does not require `search.detail_model`."""
    (tmp_workspace / "config.yaml").write_text(config_text(detail_model=None), encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("value", ['"sonnet"', '"gemini-2.5-pro"', '"inherit"', '"claude sonnet 4"'])
def test_detail_model_value_is_never_checked(tmp_workspace, value):
    """When the key is there, the validator ignores it — whatever it says."""
    (tmp_workspace / "config.yaml").write_text(
        config_text(detail_model=value), encoding="utf-8"
    )
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr


# ------------------------------------------------------------------------------- preferences.md


def test_missing_preferences_fails(tmp_workspace):
    (tmp_workspace / "preferences.md").unlink()
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID preferences.md missing-file" in r.stdout


def test_missing_front_matter_fails(tmp_workspace):
    (tmp_workspace / "preferences.md").write_text("# Brief\nJust text\n", encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID preferences.md front-matter" in r.stdout


def test_empty_preferences_fails(tmp_workspace):
    (tmp_workspace / "preferences.md").write_text("", encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID preferences.md front-matter" in r.stdout


def test_unterminated_front_matter_fails(tmp_workspace):
    (tmp_workspace / "preferences.md").write_text(
        "---\ncreated_at: 2026-07-30\nupdated_at: 2026-07-30\n# Brief\n", encoding="utf-8"
    )
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID preferences.md front-matter-unterminated" in r.stdout


@pytest.mark.parametrize("key", ["created_at", "updated_at"])
def test_missing_front_matter_date_fails(tmp_workspace, key):
    body = VALID_PREFERENCES.replace("%s: 2026-07-30\n" % key, "")
    (tmp_workspace / "preferences.md").write_text(body, encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID preferences.md missing-key %s" % key in r.stdout


def test_non_iso_front_matter_date_fails(tmp_workspace):
    body = VALID_PREFERENCES.replace("created_at: 2026-07-30", "created_at: 07/30/2026")
    (tmp_workspace / "preferences.md").write_text(body, encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID preferences.md created_at-not-iso 07/30/2026" in r.stdout


def test_full_timestamp_front_matter_date_passes(tmp_workspace):
    body = VALID_PREFERENCES.replace("updated_at: 2026-07-30", "updated_at: 2026-07-30T18:04:00Z")
    (tmp_workspace / "preferences.md").write_text(body, encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr


# ----------------------------------------------------------------------------------- run records


def test_offset_timestamp_in_run_record_fails(tmp_workspace):
    """Run-record timestamps are UTC with a `Z`; `+00:00` names the same instant but fails."""
    write_run(tmp_workspace, run_record(started_at="2026-07-16T14:30:00+00:00"))
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert (
        "INVALID runs/%s.json started_at-not-utc 2026-07-16T14:30:00+00:00" % RUN_ID in r.stdout
    )


def test_offset_completed_at_fails(tmp_workspace):
    write_run(tmp_workspace, run_record(completed_at="2026-07-16T14:41:12-04:00"))
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert (
        "INVALID runs/%s.json completed_at-not-utc 2026-07-16T14:41:12-04:00" % RUN_ID in r.stdout
    )


def test_null_completed_at_is_skipped(tmp_workspace):
    write_run(tmp_workspace, run_record(completed_at=None))
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("trigger", ["manual", "scheduled"])
def test_valid_trigger_passes(tmp_workspace, trigger):
    write_run(tmp_workspace, run_record(trigger=trigger))
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr


def test_unknown_trigger_fails(tmp_workspace):
    write_run(tmp_workspace, run_record(trigger="canary"))
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID runs/%s.json trigger-not-manual-or-scheduled canary" % RUN_ID in r.stdout


@pytest.mark.parametrize("close_state", ["complete", "blocked", "interrupted"])
def test_valid_close_state_passes(tmp_workspace, close_state):
    write_run(tmp_workspace, run_record(close_state=close_state))
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr


def test_unknown_close_state_fails(tmp_workspace):
    write_run(tmp_workspace, run_record(close_state="finished"))
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID runs/%s.json close-state-unknown finished" % RUN_ID in r.stdout


def test_run_id_that_disagrees_with_the_filename_fails(tmp_workspace):
    path = tmp_workspace / "runs" / ("%s.json" % RUN_ID)
    path.write_text(
        json.dumps(run_record(), indent=2).replace(RUN_ID, "2026-07-16T14-30-01Z") + "\n",
        encoding="utf-8",
    )
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert (
        "INVALID runs/%s.json run-id-not-the-filename 2026-07-16T14-30-01Z" % RUN_ID in r.stdout
    )


@pytest.mark.parametrize("key", ["run_id", "trigger", "close_state"])
def test_missing_run_record_key_fails(tmp_workspace, key):
    record = run_record()
    del record[key]
    path = tmp_workspace / "runs" / ("%s.json" % RUN_ID)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID runs/%s.json missing-key %s" % (RUN_ID, key) in r.stdout


def test_extra_fields_in_a_run_record_are_accepted(tmp_workspace):
    """Unknown keys pass: the record schema is still being narrowed, and old records must read."""
    write_run(
        tmp_workspace,
        run_record(
            build={"version": "0.7.0", "git_sha": "282d0c8"},
            detail_model="sonnet",
            pagination_metrics={"first_page_rows": 80},
        ),
    )
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr


def test_non_run_json_in_runs_is_ignored(tmp_workspace):
    """`runs/` holds more than run records; only timestamp-named files are run records."""
    (tmp_workspace / "runs" / "detail-model-binding.json").write_text(
        json.dumps({"version": 1, "detail_model": "sonnet", "trigger": "nonsense"}) + "\n",
        encoding="utf-8",
    )
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_broken_run_record_is_reported(tmp_workspace):
    """One line per broken rule — the caller sees all of them, not just the first."""
    other = "2026-07-17T09-00-00Z"
    write_run(tmp_workspace, run_record(trigger="canary"))
    write_run(tmp_workspace, run_record(run_id=other, close_state="finished"))
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID runs/%s.json trigger-not-manual-or-scheduled canary" % RUN_ID in r.stdout
    assert "INVALID runs/%s.json close-state-unknown finished" % other in r.stdout


# ------------------------------------------------------------------------------------ post-close


def test_clean_post_close_passes(tmp_workspace):
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr


def test_leftover_marker_fails_post_close(tmp_workspace):
    (tmp_workspace / "runs" / (".started-%s" % RUN_ID)).write_text("", encoding="utf-8")
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "INVALID runs/.started-%s leftover-marker" % RUN_ID in r.stdout


def test_leftover_scratch_dir_fails_post_close(tmp_workspace):
    scratch = tmp_workspace / "runs" / ".scratch" / RUN_ID
    scratch.mkdir(parents=True)
    (scratch / "page-1.json").write_text("{}", encoding="utf-8")
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "INVALID runs/.scratch/%s leftover-scratch-dir" % RUN_ID in r.stdout


def test_leftovers_are_not_checked_without_post_close(tmp_workspace):
    (tmp_workspace / "runs" / (".started-%s" % RUN_ID)).write_text("", encoding="utf-8")
    (tmp_workspace / "runs" / ".scratch" / RUN_ID).mkdir(parents=True)
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr


def test_another_runs_leftovers_do_not_fail_this_run(tmp_workspace):
    other = "2026-07-17T09-00-00Z"
    (tmp_workspace / "runs" / (".started-%s" % other)).write_text("", encoding="utf-8")
    (tmp_workspace / "runs" / ".scratch" / other).mkdir(parents=True)
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr


# ------------------------------------------------------------------------------ operator errors


def test_no_arguments_is_a_usage_error():
    r = subprocess.run(["sh", str(VALIDATOR)], capture_output=True, text=True)
    assert r.returncode == 2
    assert "usage" in r.stderr


def test_missing_workspace_directory_is_an_operator_error(tmp_path):
    r = run_validator(tmp_path / "not-a-workspace")
    assert r.returncode == 2
    assert "not-a-workspace" in r.stderr


def test_post_close_without_a_run_id_is_a_usage_error(tmp_workspace):
    r = run_validator(tmp_workspace, "--post-close")
    assert r.returncode == 2
    assert "usage" in r.stderr


def test_post_close_with_a_malformed_run_id_is_an_operator_error(tmp_workspace):
    r = run_validator(tmp_workspace, "--post-close", "yesterday")
    assert r.returncode == 2
    assert "yesterday" in r.stderr


# --------------------------------------------------------------------------------- portable sh


@pytest.mark.parametrize("shell", ["sh"] + (["dash"] if shutil.which("dash") else []))
def test_script_is_posix_sh(shell):
    """The script is POSIX `sh`, not bash-only: `sh -n` and strict `dash -n` are both clean."""
    r = subprocess.run([shell, "-n", str(VALIDATOR)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("shell", ["sh"] + (["dash"] if shutil.which("dash") else []))
def test_valid_workspace_passes_under_every_shell(tmp_workspace, shell):
    r = run_validator(tmp_workspace, shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
