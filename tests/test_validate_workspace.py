"""Unit tests for `skills/job-search-runbook/scripts/validate-workspace.sh`.

Every mechanical rule about workspace files lives in that one script: which keys `config.yaml` must
carry and what shape their values take, the front matter `preferences.md` needs, the fields a run
record in `runs/` must get right, and the leftovers a finished run must not leave behind. The script
prints one `INVALID <file> <rule>` line per broken rule and exits 1; a workspace with nothing wrong
prints nothing and exits 0.

Scripts are the one place ordinary unit tests belong — skill behavior is graded by the scenario
suites at `skills/<skill>/evals/evals.json` and by the maintainer's live behavior evals instead —
so each test here builds a temp workspace, runs the script through POSIX `sh` (never bash), and
asserts the exact line it prints.

`search.detail_model` is deliberately absent from the rules. The validator does not require it and
does not look at its value, whatever a workspace has written there.
"""
import datetime
import json
import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "skills" / "job-search-runbook" / "scripts" / "validate-workspace.sh"
RUN_COUNTS = ROOT / "skills" / "job-search-run" / "scripts" / "run-counts.sh"
CLOSE_RUN = ROOT / "skills" / "job-search-runbook" / "scripts" / "close-run.sh"
RECORD_TEMPLATE = ROOT / "skills" / "job-search-run" / "templates" / "run-record.example.json"
# A real workspace, kept under tests/ so that a fresh clone has one for this test to validate. It is
# a copy of the seed workspace the maintainer's live behavior evals use for a headless run. They keep
# the original, because their runner looks for a seeded case's workspace inside that harness, and the
# harness is not in this repository: `git ls-files evals` prints nothing.
SEED_WORKSPACE = ROOT / "tests" / "fixtures" / "seed-workspace"
CONFIG_TEMPLATE = ROOT / "skills" / "job-search" / "templates" / "config.example.yaml"
PREFERENCES_TEMPLATE = (
    ROOT / "skills" / "job-preference-interview" / "templates" / "preferences.example.md")

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
    """A run record the validator passes with no `--post-close`: every field those rules require,
    and none of the count fields, which only that flag reaches."""
    record = {
        "run_id": run_id,
        "trigger": "manual",
        "scheduler_id": None,
        "close_state": "complete",
        "run_health": "healthy",
        "degraded_reasons": [],
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


def full_record(run_id=RUN_ID, **overrides):
    """A run record carrying the count fields too — what `close-run.sh` writes today.

    The numbers are the ones `seed_log` below puts in the log, worked out by reading its six rows:
    two `surfaced` events, so `postings_surfaced` 2; both carry an `evaluated` event, so
    `postings_reviewed` 2 and `postings_unreviewed` 0; one `detail` event, so
    `postings_detail_read` 1; one judgment relevant with band `strong` and one not relevant, so
    `matches` 1/0/0 and `filtered_out` 1; neither judgment names the other in `same_role_as`, so
    `duplicates_of_another` 0; both postings came from `linkedin`, so `by_source` 2.
    `test_the_seeded_log_holds_the_numbers_these_cases_assume` asserts that reading against
    `run-counts.sh` so no case here rests on the two agreeing by accident.
    """
    record = run_record(run_id)
    record.update({
        "postings_surfaced": 2, "postings_reviewed": 2, "postings_unreviewed": 0,
        "postings_detail_read": 1,
        "matches": {"strong": 1, "moderate": 0, "weak": 0},
        "filtered_out": 1,
        "duplicates_of_another": 0,
        "by_source": {"linkedin": 2},
    })
    record.update(overrides)
    return record


SEED_LOG_ROWS = [
    '{"event":"call","run_id":"%s","route":"search-jobs","source":"linkedin","query_id":"q",'
    '"ok":true,"rows_returned":2,"rows_new":%d}',
    '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"a"}',
    '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"b"}',
    '{"event":"detail","run_id":"%s","source":"linkedin","source_id":"a"}',
    '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"a",'
    '"detail_read":true,"relevant":true,"match":"strong"}',
    '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"b",'
    '"detail_read":false,"relevant":false,"match":null}',
]

B_JUDGED_BY = (
    '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"b",'
    '"detail_read":false,"relevant":false,"match":null}')


def seed_log(workspace, run_id=RUN_ID, rows_new=2):
    """Two postings surfaced by one search, one a strong match and one filtered out."""
    rows = [SEED_LOG_ROWS[0] % (run_id, rows_new)] + [r % run_id for r in SEED_LOG_ROWS[1:]]
    (workspace / "jobs.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")


# `seed_log`'s six rows with b's judgment naming a as the same opening. Read off by hand: two
# postings surfaced and both judged, so `postings_surfaced` 2, `postings_reviewed` 2 and
# `postings_unreviewed` 0; a is strong and b is the same opening as a, so `matches` 1/0/0,
# `filtered_out` 0 and `duplicates_of_another` 1.
DUPLICATE_LOG_ROWS = SEED_LOG_ROWS[:5] + [
    '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"b",'
    '"detail_read":false,"relevant":true,"match":"strong","same_role_as":"linkedin:a"}',
]


def seed_log_with_a_duplicate(workspace, run_id=RUN_ID):
    """One opening surfaced twice: b's judgment names a, so the run found one opening in two rows."""
    rows = [DUPLICATE_LOG_ROWS[0] % (run_id, 2)] + [r % run_id for r in DUPLICATE_LOG_ROWS[1:]]
    (workspace / "jobs.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")


def duplicate_record(run_id=RUN_ID, **overrides):
    """The record `seed_log_with_a_duplicate`'s rows add up to."""
    fields = {"matches": {"strong": 1, "moderate": 0, "weak": 0},
              "filtered_out": 0, "duplicates_of_another": 1}
    fields.update(overrides)
    return full_record(run_id, **fields)


def run_validator(workspace, *args, shell="sh", env=None, cwd=None):
    e = None
    if env is not None:
        e = dict(os.environ)
        e.update(env)
    return subprocess.run(
        [shell, str(VALIDATOR), str(workspace), *args],
        capture_output=True,
        text=True,
        env=e,
        cwd=None if cwd is None else str(cwd),
    )


SHELLS = ["sh"] + [s for s in ("dash", "bash") if shutil.which(s)]


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
    """The workspace under tests/fixtures/ is a real one, not built here; it stays valid."""
    r = run_validator(SEED_WORKSPACE)
    assert r.returncode == 0, r.stdout + r.stderr


def test_workspace_built_from_the_templates_passes(tmp_path):
    """A new workspace copied straight from the two skills' templates/ directories validates."""
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


@pytest.mark.parametrize(
    "written",
    [
        "2026-07-30",
        '"2026-07-30"',
        "'2026-07-30'",
        "2026-07-30   # the day I started looking",
        "2026-07-30T18:04:00Z",
        '"2026-07-30T18:04:00Z"',
        "2026-07-30T18:04:00",
        "2026-07-30T18:04:00-04:00",
        "2026-07-30T18:04:00.512Z",
    ],
)
def test_front_matter_date_spellings_pass(tmp_workspace, written):
    """A quoted date is valid YAML and a working brief — reading it must not depend on the quotes."""
    body = VALID_PREFERENCES.replace("created_at: 2026-07-30", "created_at: %s" % written)
    (tmp_workspace / "preferences.md").write_text(body, encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize(
    "written,observed",
    [
        ('"garbage"', "garbage"),
        ('"07/30/2026"', "07/30/2026"),
        ("2026-07-30T18:04:00garbage", "2026-07-30T18:04:00garbage"),
        ('"2026-07-30T18:04:00garbage"', "2026-07-30T18:04:00garbage"),
        ("2026-07-30-extra", "2026-07-30-extra"),
    ],
)
def test_non_iso_front_matter_dates_fail_however_they_are_written(
    tmp_workspace, written, observed
):
    """Stripping the quotes must not also stop the check: what is inside them still has to be a date."""
    body = VALID_PREFERENCES.replace("created_at: 2026-07-30", "created_at: %s" % written)
    (tmp_workspace / "preferences.md").write_text(body, encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID preferences.md created_at-not-iso %s" % observed in r.stdout


@pytest.mark.parametrize("written", ['""', "''"])
def test_empty_front_matter_date_fails(tmp_workspace, written):
    body = VALID_PREFERENCES.replace("created_at: 2026-07-30", "created_at: %s" % written)
    (tmp_workspace / "preferences.md").write_text(body, encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID preferences.md empty-value created_at" in r.stdout


# ----------------------------------------------------------------------------------- run records


def test_offset_timestamp_in_run_record_fails(tmp_workspace):
    """Run-record timestamps are UTC with a `Z`; `+00:00` names the same instant but fails."""
    write_run(tmp_workspace, run_record(started_at="2026-07-16T14:30:00+00:00"))
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert (
        "INVALID runs/%s.json started_at-not-utc 2026-07-16T14:30:00+00:00" % RUN_ID in r.stdout
    )


@pytest.mark.parametrize(
    "ts", ["2026-07-30T18:04:00garbage", "2026-07-16T14:30:00", "2026-07-16", "14:30:00Z"]
)
def test_run_record_timestamp_must_be_a_whole_utc_timestamp(tmp_workspace, ts):
    """The `Z` rule is anchored at both ends — a trailing suffix does not sneak past it."""
    write_run(tmp_workspace, run_record(started_at=ts))
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID runs/%s.json started_at-not-utc %s" % (RUN_ID, ts) in r.stdout


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


# ------------------------------------------------------------------- degraded_reasons in a record


# The run record as it was shipped before this branch: the same fields, values and order as
# `git show b3ac24d:skills/job-search-run/templates/run-record.example.json`, the template at the
# branch point, compared against it on 2026-08-12. The shipped template differs from it by
# `degraded_reasons`, the eight count fields and three `agent_data_usage` numbers. Every record in a
# workspace that has not run this version has these fields and no others, and nothing rewrites an
# old record.
PRE_BRANCH_RECORD = {
    "run_id": "2026-07-30T15-04-02Z",
    "trigger": "scheduled",
    "scheduler_id": "com.job-search.daily",
    "brief_revision": "9f2c41a7be05",
    "close_state": "complete",
    "run_health": "healthy",
    "sources": ["linkedin", "ashby"],
    "queries": ["ai-eng-remote", "ml-platform-sf"],
    "agent_data_usage": {"searches": 4, "detail_reads": 5, "other": 1, "total_metered": 10},
    "started_at": "2026-07-30T15:04:02Z",
    "completed_at": "2026-07-30T15:12:47Z",
}


def test_a_record_with_no_degraded_reasons_key_is_invalid(tmp_workspace):
    """`close-run.sh` writes the field on every close, the empty list included, so a record for the
    run being checked that has no list at all was not written by this version's close.

    The second half is the one-finding-per-problem shape: a degraded record that carries no list is
    one problem, and the key to add is what the caller is told. `only` is the whole of stdout there,
    so `degraded-with-no-reasons` printing alongside it would fail this case.
    """
    only = "INVALID runs/%s.json missing-key degraded_reasons\n" % RUN_ID
    record = full_record()
    del record["degraded_reasons"]
    write_run(tmp_workspace, record)
    # No jobs.jsonl, so the counts are held to the record's own arithmetic, which holds — this is
    # the one field it is missing, and the whole of stdout is the one finding about it.
    assert not (tmp_workspace / "jobs.jsonl").exists()
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stdout == only, r.stdout

    record = full_record(run_health="degraded")
    del record["degraded_reasons"]
    write_run(tmp_workspace, record)
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stdout == only, r.stdout


def test_the_degraded_reasons_key_check_is_behind_post_close(tmp_workspace):
    """A record written before the field existed must still read as valid when the run it belongs
    to is not the one being checked. Nothing rewrites an old record, so a rule that reported it in
    plain validation would report it on every validation for as long as the workspace exists.

    The count fields are behind the flag for this reason too, and pinned the same way — see
    `test_the_count_checks_are_behind_post_close`. The record here is missing `degraded_reasons` and
    nothing else, so the run without the flag passing at exit 0 is what shows the check is reached
    only through it.
    """
    record = full_record()
    del record["degraded_reasons"]
    write_run(tmp_workspace, record)
    plain = run_validator(tmp_workspace)          # no --post-close
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert plain.stdout == "", plain.stdout
    checked = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert checked.stdout == "INVALID runs/%s.json missing-key degraded_reasons\n" % RUN_ID, \
        checked.stdout


def test_a_record_written_before_the_field_existed_passes_plain_validation(tmp_workspace):
    """The record a workspace holds when its last run was 0.8.0 — the released version this branch
    is based on, measured off the CHANGELOG at the branch point — driven whole rather than as a
    field taken off a current one.

    The second half is the case `degraded-with-no-reasons` has to stay silent on: a record from
    before the field existed that closed `complete` and came back `degraded` — a lost search was
    enough — carries no list to be empty, and `json_arr_state` prints nothing for a field that is
    not there.
    """
    write_run(tmp_workspace, PRE_BRANCH_RECORD)
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout

    write_run(tmp_workspace, dict(PRE_BRANCH_RECORD, run_health="degraded"))
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout


def test_a_degraded_record_with_an_empty_reasons_list_is_invalid(tmp_workspace):
    """A run that completed and still came back degraded was degraded by one of the three checks
    that write a reason, so a record that says degraded and names nothing is missing the reason its
    close found. `close-run.sh` prints each reason on stderr as it finds it and puts the same lines
    in this field, because the stderr is gone by the time anyone asks."""
    write_run(tmp_workspace, run_record(run_health="degraded", degraded_reasons=[]))
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID runs/%s.json degraded-with-no-reasons" % RUN_ID in r.stdout, r.stdout


def test_a_healthy_record_with_an_empty_reasons_list_is_valid(tmp_workspace):
    """The empty list is what a run with nothing wrong carries — the ordinary record, not a rule
    anyone broke."""
    write_run(tmp_workspace, run_record(run_health="healthy", degraded_reasons=[]))
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout


def test_a_degraded_record_that_names_a_reason_is_valid(tmp_workspace):
    """The other half of the rule: what it asks for is a reason, so a record carrying one passes.

    `write_run` writes a list holding one string across three lines. `close-run.sh` writes the whole
    array on one line — one `printf`, measured on 2026-08-12 on a record it wrote carrying two
    reasons — so a record split this way is one written by hand, and this case is what holds the
    reader to reading that form as well.

    Both modes are driven, because they read the array for different rules and only one of them can
    see this. A reader that gave up at the end of the line would report nothing here and satisfy the
    value rule, and `--post-close` is where that reader gets caught: it would find no array at all
    and call the key missing.
    """
    write_run(tmp_workspace, full_record(
        run_health="degraded",
        degraded_reasons=["a relevant posting carries no band, so postings_reviewed does not add up "
                          "from matches, filtered_out and duplicates_of_another — re-judge that "
                          "posting with a --match value"]))
    body = (tmp_workspace / "runs" / ("%s.json" % RUN_ID)).read_text(encoding="utf-8")
    assert '"degraded_reasons": [\n' in body, body
    plain = run_validator(tmp_workspace)
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert plain.stdout == "", plain.stdout
    # No jobs.jsonl here, so the counts are held to the record's own arithmetic and nothing else.
    assert not (tmp_workspace / "jobs.jsonl").exists()
    checked = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert checked.stdout == "", checked.stdout


@pytest.mark.parametrize("close_state", ["blocked", "interrupted"])
def test_a_close_that_did_not_complete_may_carry_no_reasons(tmp_workspace, close_state):
    """A close that is not `complete` is degraded whatever else the run did, and that term writes no
    reason — so `close-run.sh` writes `run_health: degraded` alongside `degraded_reasons: []`, and
    the rule above must not report a record its own writer produced.

    The record is written by that script rather than by hand, which is what makes this a record a
    real close leaves behind. The other health term that writes no reason is a posting left
    unjudged, and it needs no case of its own: `close-run.sh` refuses a `complete` close while any
    posting is unjudged — `grep -n 'close_state complete, but'
    skills/job-search-runbook/scripts/close-run.sh`, one line — so no record it writes is both.
    """
    seed_log(tmp_workspace)
    c = subprocess.run(["sh", str(CLOSE_RUN), str(tmp_workspace), RUN_ID,
                        "--trigger", "manual", "--close-state", close_state,
                        "--sources", "linkedin"], capture_output=True, text=True)
    assert c.returncode == 0, c.stdout + c.stderr
    assert "run_health=degraded" in c.stdout, c.stdout
    written = json.loads((tmp_workspace / "runs" / ("%s.json" % RUN_ID)).read_text())
    assert written["run_health"] == "degraded", written
    assert written["degraded_reasons"] == [], written
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout


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


# -------------------------------------------- the counts a record states against the log it names


def findings(r):
    return [l for l in r.stdout.splitlines() if l.startswith("INVALID ")]


def test_the_seeded_log_holds_the_numbers_these_cases_assume(tmp_workspace):
    """`seed_log` is six event rows and `full_record` states the counts they add up to. Every case
    below compares those two through the validator, so if the record's numbers were only ever
    checked against the validator's own reading of the log, a reader that mis-read every field the
    same way would pass them all.

    The expected values here are read off the six rows by hand — see `full_record` — and compared
    against `run-counts.sh`, which is the reader the validator calls. That pins the fixture to
    numbers no script produced.
    """
    seed_log(tmp_workspace)
    r = subprocess.run(["sh", str(RUN_COUNTS), str(tmp_workspace / "jobs.jsonl"), RUN_ID],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    counts = dict(l.split("=", 1) for l in r.stdout.splitlines())
    assert counts["postings_surfaced"] == "2"
    assert counts["postings_reviewed"] == "2"
    assert counts["postings_unreviewed"] == "0"
    assert counts["postings_detail_read"] == "1"
    assert counts["match_strong"] == "1"
    assert counts["match_moderate"] == "0"
    assert counts["match_weak"] == "0"
    assert counts["filtered_out"] == "1"
    assert counts["duplicates_of_another"] == "0"
    assert counts["by_source_linkedin"] == "2"
    assert counts["rows_new_total"] == "2"


def test_a_record_without_the_count_fields_fails(tmp_workspace):
    """A record with no count field on it. Every count field is named, one finding each, so a caller
    sees which fields to add rather than the first one missing — which is what a workspace holding a
    record from before those fields existed gets."""
    seed_log(tmp_workspace)
    write_run(tmp_workspace, run_record())          # no count fields
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    for field in ("postings_surfaced", "postings_reviewed", "postings_unreviewed",
                  "postings_detail_read", "filtered_out", "duplicates_of_another",
                  "matches", "by_source"):
        assert "INVALID runs/%s.json missing-key %s" % (RUN_ID, field) in r.stdout, r.stdout


def test_counts_matching_the_log_pass(tmp_workspace):
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record())
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_seeded_duplicate_log_holds_the_numbers_these_cases_assume(tmp_workspace):
    """The same pinning `test_the_seeded_log_holds_the_numbers_these_cases_assume` does, for the log
    holding one opening surfaced twice. The expected values are read off the six rows by hand — see
    `DUPLICATE_LOG_ROWS` — and compared against `run-counts.sh`, the reader the validator calls."""
    seed_log_with_a_duplicate(tmp_workspace)
    r = subprocess.run(["sh", str(RUN_COUNTS), str(tmp_workspace / "jobs.jsonl"), RUN_ID],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    counts = dict(l.split("=", 1) for l in r.stdout.splitlines())
    assert counts["postings_reviewed"] == "2"
    assert counts["match_strong"] == "1"
    assert counts["filtered_out"] == "0"
    assert counts["duplicates_of_another"] == "1"


def test_a_record_carrying_the_duplicate_matches_the_log(tmp_workspace):
    """One opening surfaced twice: one band, one duplicate, and 1 + 0 + 0 + 0 + 1 against the 2
    postings the run reviewed."""
    seed_log_with_a_duplicate(tmp_workspace)
    write_run(tmp_workspace, duplicate_record())
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_record_that_counts_the_duplicate_as_a_second_match_is_reported(tmp_workspace):
    """The record this change removes: the same opening counted in a band twice and nothing under
    `duplicates_of_another`. Its own arithmetic holds — 2 + 0 + 0 + 0 + 0 against 2 reviewed — so
    only the comparison against the log can see it, on two fields at once."""
    seed_log_with_a_duplicate(tmp_workspace)
    write_run(tmp_workspace, duplicate_record(matches={"strong": 2, "moderate": 0, "weak": 0},
                                              duplicates_of_another=0))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert [l.split(" ", 2)[2] for l in findings(r)] == [
        "counts-disagree-with-log duplicates_of_another 0 vs 1",
        "counts-disagree-with-log matches.strong 2 vs 1",
    ], r.stdout


def test_a_record_that_drops_the_duplicate_from_every_key_does_not_sum(tmp_workspace):
    """A record that left the duplicate out of the bands and out of `duplicates_of_another` too:
    the count of postings it reviewed is one above what its keys name, which the sum sees with no
    log at all. The log comparison names the field as well, so both halves report it."""
    seed_log_with_a_duplicate(tmp_workspace)
    write_run(tmp_workspace, duplicate_record(duplicates_of_another=0))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert [l.split(" ", 2)[2] for l in findings(r)] == [
        "bands-do-not-sum-to-reviewed 1 vs 2",
        "counts-disagree-with-log duplicates_of_another 0 vs 1",
    ], r.stdout


def test_a_count_that_disagrees_with_the_log_fails(tmp_workspace):
    """9 is the record's number and 2 is the log's, and the finding carries both so a caller can
    see which way the record is wrong without re-running the reader."""
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(postings_surfaced=9))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "counts-disagree-with-log postings_surfaced 9 vs 2" in r.stdout, r.stdout


@pytest.mark.parametrize("field,written,in_log", [
    ("postings_reviewed", 1, 2),
    ("postings_unreviewed", 3, 0),
    ("postings_detail_read", 2, 1),
    ("filtered_out", 0, 1),
    ("duplicates_of_another", 4, 0),
])
def test_every_top_level_count_is_compared_against_the_log(tmp_workspace, field, written, in_log):
    """One case per compared field, because a loop that dropped a field would still pass a case
    that only ever changed `postings_surfaced`. Each `in_log` is read off `seed_log`'s six rows by
    hand and pinned by `test_the_seeded_log_holds_the_numbers_these_cases_assume`."""
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(**{field: written}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "counts-disagree-with-log %s %d vs %d" % (field, written, in_log) in r.stdout, r.stdout


@pytest.mark.parametrize("band,written,in_log", [
    ("strong", 0, 1), ("moderate", 2, 0), ("weak", 5, 0)])
def test_every_band_is_compared_against_the_log(tmp_workspace, band, written, in_log):
    """The three bands are read out of the record's nested `matches` object, so they need their own
    reader and their own cases. `filtered_out` is moved with them to keep the record's own
    arithmetic intact, so what fails here is the log comparison and not the sum."""
    matches = {"strong": 1, "moderate": 0, "weak": 0}
    matches[band] = written
    filtered = 2 - sum(matches.values())
    write_run(tmp_workspace, full_record(matches=matches, filtered_out=filtered))
    seed_log(tmp_workspace)
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "counts-disagree-with-log matches.%s %d vs %d" % (band, written, in_log) in r.stdout, \
        r.stdout
    assert "bands-do-not-sum-to-reviewed" not in r.stdout, r.stdout


def test_a_by_source_count_that_disagrees_with_the_log_fails(tmp_workspace):
    """`by_source` is the fourth thing the log counts. Without this comparison a record could name
    any source split it liked and every other check would still pass, since nothing else reads that
    block. Both postings in `seed_log` come from linkedin, so the log says 2."""
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(by_source={"linkedin": 7}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "counts-disagree-with-log by_source.linkedin 7 vs 2" in r.stdout, r.stdout


def test_internally_consistent_but_uniformly_wrong_counts_still_fail(tmp_workspace):
    """The real defect: 2+5+2 balanced against 17 actual rows.

    Every arithmetic rule the record can be checked against by itself holds here — 4+3+1+1 is the 9
    it claims to have reviewed, and 9+0 is the 9 it claims to have surfaced — so the two arithmetic
    findings must not be printed and the log comparison has to be what fails. Asserting their absence
    is what makes this case about the log rather than about the arithmetic.
    """
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(
        postings_surfaced=9, postings_reviewed=9, postings_unreviewed=0,
        matches={"strong": 4, "moderate": 3, "weak": 1}, filtered_out=1,
        by_source={"linkedin": 9}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "bands-do-not-sum-to-reviewed" not in r.stdout, r.stdout
    assert "reviewed-plus-unreviewed-is-not-surfaced" not in r.stdout, r.stdout
    assert "counts-disagree-with-log postings_surfaced 9 vs 2" in r.stdout, r.stdout


def test_bands_that_do_not_sum_to_reviewed_fail(tmp_workspace):
    """1 strong + 1 moderate + 0 weak + 1 filtered out is 3, against 2 reviewed."""
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(matches={"strong": 1, "moderate": 1, "weak": 0}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "bands-do-not-sum-to-reviewed 3 vs 2" in r.stdout, r.stdout


def test_reviewed_plus_unreviewed_that_is_not_surfaced_fails(tmp_workspace):
    """2 reviewed + 1 unreviewed is 3, against 2 surfaced. The log comparison would catch the
    unreviewed field on its own, so the arithmetic finding is asserted by name."""
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(postings_unreviewed=1))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "reviewed-plus-unreviewed-is-not-surfaced 3 vs 2" in r.stdout, r.stdout


def test_surfaced_that_does_not_match_the_rows_the_searches_brought_in_fails(tmp_workspace):
    """A record can agree with every count the log holds and still contradict the log's own rows.
    Here the search says it brought in 5 new rows and only 2 postings were surfaced, so the record
    — which states the 2 the log counted — is right about the postings and the run lost three rows
    somewhere between the search and the log. Every other check passes, which is what makes this
    the only finding.
    """
    seed_log(tmp_workspace, rows_new=5)
    write_run(tmp_workspace, full_record())
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert [l.split(" ", 2)[2] for l in findings(r)] == ["surfaced-does-not-match-rows-new 2 vs 5"], \
        r.stdout


def test_a_record_close_run_wrote_validates_against_the_log_it_was_written_from(tmp_workspace):
    """The writer and the reader end to end, so the two cannot drift apart behind the hand-written
    records every other case here uses. `close-run.sh` lays `matches` and `by_source` out on one
    line each and `write_run` splits them across lines, and both have to read the same.
    """
    seed_log(tmp_workspace)
    r = subprocess.run(["sh", str(CLOSE_RUN), str(tmp_workspace), RUN_ID,
                        "--trigger", "manual", "--close-state", "complete",
                        "--sources", "linkedin"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    written = json.loads((tmp_workspace / "runs" / ("%s.json" % RUN_ID)).read_text())
    # Pinned by hand off `seed_log`'s six rows, so this fails if `close-run.sh` starts writing
    # something else rather than only if the two scripts disagree with each other.
    assert written["postings_surfaced"] == 2
    assert written["postings_reviewed"] == 2
    assert written["matches"] == {"strong": 1, "moderate": 0, "weak": 0}
    assert written["by_source"] == {"linkedin": 2}
    v = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert v.returncode == 0, v.stdout + v.stderr


def test_a_run_with_an_unbanded_relevant_row_closes_degraded_and_is_reported_here(tmp_workspace):
    """A relevant posting carrying no band is counted in `postings_reviewed` and in neither
    `matches` nor `filtered_out`, so the record `close-run.sh` writes for it genuinely does not add
    up. `close-run.sh` still writes it — a run with one bad row must not be left unclosable — and
    says `run_health=degraded`. This is the finding that names the same record for anyone checking
    the close rather than writing it, and `close-run.sh` quotes it in its own comment.

    `record-judgment.sh` refuses to write a relevant row with no band, so the row is written here by
    hand, the way the no-runtime prose fallback would.
    """
    rows = [SEED_LOG_ROWS[0] % (RUN_ID, 2)] + [r % RUN_ID for r in SEED_LOG_ROWS[1:4]] + [
        '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"a",'
        '"detail_read":true,"relevant":true,"match":"strong"}' % RUN_ID,
        '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"b",'
        '"detail_read":false,"relevant":true,"match":null}' % RUN_ID,
    ]
    (tmp_workspace / "jobs.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    c = subprocess.run(["sh", str(CLOSE_RUN), str(tmp_workspace), RUN_ID,
                        "--trigger", "manual", "--close-state", "complete",
                        "--sources", "linkedin"], capture_output=True, text=True)
    assert c.returncode == 0, c.stdout + c.stderr
    assert "run_health=degraded" in c.stdout, c.stdout
    written = json.loads((tmp_workspace / "runs" / ("%s.json" % RUN_ID)).read_text())
    # By hand off the six rows: two postings, both judged, one banded strong and one relevant with
    # no band, so 1 + 0 + 0 banded and 0 filtered against 2 reviewed.
    assert written["postings_reviewed"] == 2
    assert written["matches"] == {"strong": 1, "moderate": 0, "weak": 0}
    assert written["filtered_out"] == 0
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert [l.split(" ", 2)[2] for l in findings(r)] == ["bands-do-not-sum-to-reviewed 1 vs 2"], \
        r.stdout


def test_the_count_checks_are_behind_post_close(tmp_workspace):
    """An older record, written before this change, must still read as valid when the run it
    belongs to is not the one being checked.

    The record here fails `--post-close` — its `postings_surfaced` is 9 against the log's 2 — so the
    run without it passing at exit 0 is what shows the count checks are reached only through that
    flag. Hoisting the block out of the `--post-close` branch would make every workspace holding an
    old record fail every validation, which is what this pins.
    """
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(postings_surfaced=9))
    plain = run_validator(tmp_workspace)          # no --post-close
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert plain.stdout == "", plain.stdout
    checked = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert "counts-disagree-with-log postings_surfaced 9 vs 2" in checked.stdout, checked.stdout


def test_a_record_for_a_run_the_log_holds_no_events_for_is_compared_against_zeroes(tmp_workspace):
    """`run-counts.sh` prints every key as 0 for a run id its log holds no event for, rather than
    printing nothing, so such a record is compared against zeroes rather than skipped. The log here
    holds one whole run's events under a different run id."""
    seed_log(tmp_workspace, run_id="2026-09-01T00-00-00Z")
    empty = full_record(postings_surfaced=0, postings_reviewed=0, postings_unreviewed=0,
                        postings_detail_read=0, filtered_out=0,
                        matches={"strong": 0, "moderate": 0, "weak": 0}, by_source={})
    write_run(tmp_workspace, empty)
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr
    # The other half: the 2 the other run surfaced is not this run's, so a record claiming it fails.
    write_run(tmp_workspace, full_record())
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "counts-disagree-with-log postings_surfaced 2 vs 0" in r.stdout, r.stdout


def test_a_workspace_with_no_log_at_all_reports_no_count_disagreement(tmp_workspace):
    """`run-counts.sh` exits 2 with nothing on stdout when there is no `jobs.jsonl`. Reading counts
    off that would compare every field against an empty string, so the comparison is skipped and
    only the fields the record is actually missing are named."""
    write_run(tmp_workspace, full_record())
    assert not (tmp_workspace / "jobs.jsonl").exists()
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("rule,record", [
    ("bands-do-not-sum-to-reviewed 3 vs 2", full_record(matches={"strong": 1, "moderate": 1,
                                                                "weak": 0})),
    ("reviewed-plus-unreviewed-is-not-surfaced 3 vs 2", full_record(postings_unreviewed=1)),
])
def test_the_records_own_arithmetic_is_checked_without_a_log(tmp_workspace, rule, record):
    """A record whose log has since been deleted can still be held to the two rules that need
    nothing but the record. Nothing in the workspace here can settle whether the numbers are the
    run's — only whether they contradict each other."""
    write_run(tmp_workspace, record)
    assert not (tmp_workspace / "jobs.jsonl").exists()
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert [l.split(" ", 2)[2] for l in findings(r)] == [rule], r.stdout


def test_the_shipped_run_record_template_holds_up(tmp_workspace):
    """The template is what a model copies when it writes a record by hand on the no-runtime path,
    so a template that contradicted the rules would put a contradiction in every such record. Its
    own numbers are pinned here as well, since the arithmetic alone would pass a template with all
    zeros."""
    body = json.loads(RECORD_TEMPLATE.read_text(encoding="utf-8"))
    assert body["matches"] == {"strong": 3, "moderate": 6, "weak": 2}
    assert body["filtered_out"] == 37
    assert body["duplicates_of_another"] == 2
    assert body["postings_reviewed"] == 50
    assert body["postings_unreviewed"] == 0
    assert body["postings_surfaced"] == 50
    assert body["by_source"] == {"linkedin": 25, "ashby": 25}
    body["run_id"] = RUN_ID
    body["started_at"] = "2026-07-16T14:30:00Z"
    body["completed_at"] = "2026-07-16T14:41:12Z"
    write_run(tmp_workspace, body)
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_later_run_judging_this_runs_leftovers_does_not_invalidate_this_record(tmp_workspace):
    """Invariant 4 is checkable at any time, not only at close."""
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(
        postings_reviewed=1, postings_unreviewed=1, filtered_out=0,
        matches={"strong": 1, "moderate": 0, "weak": 0}))
    # b was surfaced by this run and judged by a later one.
    log = (tmp_workspace / "jobs.jsonl").read_text().replace(
        B_JUDGED_BY % RUN_ID, B_JUDGED_BY % "2026-09-01T00-00-00Z")
    assert B_JUDGED_BY % "2026-09-01T00-00-00Z" in log, log
    (tmp_workspace / "jobs.jsonl").write_text(log, encoding="utf-8")
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr


# ----------------------------------------- an object that is there and states nothing, and awk

# `record-api-response.sh` refuses only a control character and a backslash in `--source`, so this
# is an accepted source name. It is here because it is a shell glob and a regular-expression
# metacharacter at once: the source list was read with an unquoted `$(...)` and the name was built
# into a `grep -o` pattern, and both read it as something other than itself.
GLOB_SOURCE = "*"

# `.` matches any character in a regular expression, so a source named this finds a record key
# spelled `abc` when it is built into a pattern instead of compared as text.
REGEX_SOURCE = "a.c"


def source_log(workspace, source, run_id=RUN_ID):
    """`seed_log`'s six rows with every `linkedin` replaced by `source`."""
    rows = [r.replace('"linkedin"', '"%s"' % source) for r in SEED_LOG_ROWS]
    rows = [rows[0] % (run_id, 2)] + [r % run_id for r in rows[1:]]
    (workspace / "jobs.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_the_record_the_review_measured_names_every_field_it_states_nothing_for(tmp_workspace):
    """`"matches": {}` and `"by_source": {}` passed every check at exit 0: the key was there, so the
    presence check was satisfied, and no band or source could be read, so every comparison that
    guards on an unreadable value skipped it. Two objects stating nothing drew no finding.

    Five findings now, counted by hand off the seeded log: one per band, one for the one source the
    log has, and the sum of an empty block against the 2 postings the record says it surfaced.

    `bands-do-not-sum-to-reviewed` deliberately stays quiet. The reason is written once, at the
    guard that implements it — `grep -n 'a decision, not a precaution'
    skills/job-search-runbook/scripts/validate-workspace.sh`. This case is what holds the
    decision: it asserts the whole finding list, so adding the zeros fails here.
    """
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(matches={}, by_source={}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert [l.split(" ", 2)[2] for l in findings(r)] == [
        "by-source-does-not-sum-to-surfaced 0 vs 2",
        "missing-key by_source.linkedin",
        "missing-key matches.moderate",
        "missing-key matches.strong",
        "missing-key matches.weak",
    ], r.stdout


@pytest.mark.parametrize("word", ["matches", "by_source"])
def test_a_query_id_spelling_an_object_key_does_not_move_the_reader(tmp_workspace, word):
    """`queries` holds model-supplied words, so the text `"by_source"` can be in the record as a
    value rather than as a key — and it comes before both objects. A reader that took the first
    occurrence and then looked ahead for a `{` would read `matches` as `by_source`, and the record
    would be compared against the wrong numbers with no finding to say so.

    The record here is correct in every other way, so any finding at all means the reader moved.
    """
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(queries=[word], sources=[word]))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr
    # And the numbers are still being read: moving one band has to still fail.
    write_run(tmp_workspace, full_record(queries=[word], sources=[word],
                                         matches={"strong": 0, "moderate": 1, "weak": 0}))
    bad = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert "counts-disagree-with-log matches.strong 0 vs 1" in bad.stdout, bad.stdout


@pytest.mark.parametrize("band", ["strong", "moderate", "weak"])
def test_a_matches_object_that_leaves_one_band_out_names_that_band(tmp_workspace, band):
    """One case per band, because a loop that checked two of the three would pass a case that only
    ever removed `strong`. Every other rule holds: the two bands left carry the log's own numbers
    and `filtered_out` absorbs the one removed, so the finding named here is the only one."""
    matches = {"strong": 1, "moderate": 0, "weak": 0}
    filtered = 1 + matches.pop(band)
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(matches=matches, filtered_out=filtered))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "missing-key matches.%s" % band in r.stdout, r.stdout


def test_a_by_source_block_that_leaves_out_a_source_the_log_has_fails(tmp_workspace):
    """The likelier of the two by_source mistakes. The log holds two sources; the record names one
    and gives it both postings, so the block still sums to the 2 surfaced and only the log knows
    which source they came from."""
    rows = [
        '{"event":"call","run_id":"%s","route":"search-jobs","source":"linkedin","query_id":"q",'
        '"ok":true,"rows_returned":1,"rows_new":1}' % RUN_ID,
        '{"event":"call","run_id":"%s","route":"search-jobs","source":"ashby","query_id":"q",'
        '"ok":true,"rows_returned":1,"rows_new":1}' % RUN_ID,
        '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"a"}' % RUN_ID,
        '{"event":"surfaced","run_id":"%s","source":"ashby","source_id":"b"}' % RUN_ID,
        '{"event":"detail","run_id":"%s","source":"linkedin","source_id":"a"}' % RUN_ID,
        '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"a",'
        '"detail_read":true,"relevant":true,"match":"strong"}' % RUN_ID,
        '{"event":"evaluated","run_id":"%s","source":"ashby","source_id":"b",'
        '"detail_read":false,"relevant":false,"match":null}' % RUN_ID,
    ]
    (tmp_workspace / "jobs.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    write_run(tmp_workspace, full_record(by_source={"linkedin": 2}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert [l.split(" ", 2)[2] for l in findings(r)] == [
        "counts-disagree-with-log by_source.linkedin 2 vs 1",
        "missing-key by_source.ashby",
    ], r.stdout


def test_a_by_source_block_naming_a_source_the_log_never_had_fails(tmp_workspace):
    """The other direction, and the one the comparison against the log cannot see: it walks the
    log's sources, so a source only the record names is never looked for. 2 + 3 against the 2
    postings surfaced is what catches it."""
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(by_source={"linkedin": 2, "greenhouse": 3}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert [l.split(" ", 2)[2] for l in findings(r)] == [
        "by-source-does-not-sum-to-surfaced 5 vs 2"], r.stdout


def test_by_source_that_does_not_sum_to_surfaced_fails_without_a_log(tmp_workspace):
    """The sum is arithmetic over the record alone, so it holds for a record whose log has since
    been deleted. 1 against the 2 the record says it surfaced."""
    write_run(tmp_workspace, full_record(by_source={"linkedin": 1}))
    assert not (tmp_workspace / "jobs.jsonl").exists()
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert [l.split(" ", 2)[2] for l in findings(r)] == [
        "by-source-does-not-sum-to-surfaced 1 vs 2"], r.stdout


def test_a_source_named_with_a_glob_character_is_looked_up_as_itself(tmp_workspace, tmp_path):
    """Measured on 2026-08-07 before the fix, on a run whose only source was `*`: the unquoted
    `$(...)` in the source loop expanded the name as a pathname, so the loop walked the working
    directory instead of the log's one source, and a record stating `by_source { "AAAA": 99 }`
    passed with nothing said about it.

    The validator is run from a directory holding two files, so a pathname expansion has something
    to expand to and the loop would name those files rather than the source.
    """
    elsewhere = tmp_path / "cwd-with-files"
    elsewhere.mkdir()
    (elsewhere / "linkedin").write_text("", encoding="utf-8")
    (elsewhere / "ashby").write_text("", encoding="utf-8")
    source_log(tmp_workspace, GLOB_SOURCE)
    write_run(tmp_workspace, full_record(by_source={"AAAA": 99}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID, cwd=elsewhere)
    assert r.returncode == 1, r.stdout + r.stderr
    assert [l.split(" ", 2)[2] for l in findings(r)] == [
        "by-source-does-not-sum-to-surfaced 99 vs 2",
        "missing-key by_source.*",
    ], r.stdout


def test_a_source_named_with_a_glob_character_still_compares_when_the_record_carries_it(
    tmp_workspace, tmp_path
):
    """The other half. A lookup that refused every name would pass the case above and report a
    missing key for every source a run ever had."""
    elsewhere = tmp_path / "cwd-with-files"
    elsewhere.mkdir()
    (elsewhere / "linkedin").write_text("", encoding="utf-8")
    source_log(tmp_workspace, GLOB_SOURCE)
    write_run(tmp_workspace, full_record(by_source={GLOB_SOURCE: 2}))
    good = run_validator(tmp_workspace, "--post-close", RUN_ID, cwd=elsewhere)
    assert good.returncode == 0, good.stdout + good.stderr
    write_run(tmp_workspace, full_record(by_source={GLOB_SOURCE: 2, "linkedin": 0}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID, cwd=elsewhere)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_source_name_holding_a_regular_expression_character_is_looked_up_as_text(tmp_workspace):
    """`a.c` is an accepted source name — `record-api-response.sh` refuses only a control character
    and a backslash — and `.` matches any character in a regular expression. Looked up with
    `grep "^$src="` in a record whose block holds `abc`, the log's `a.c` finds `abc`'s number and
    the record passes carrying a source the run never had. Compared as text it does not, and the
    sum cannot catch it: 2 against the 2 postings surfaced adds up either way.
    """
    source_log(tmp_workspace, REGEX_SOURCE)
    write_run(tmp_workspace, full_record(by_source={"abc": 2}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert [l.split(" ", 2)[2] for l in findings(r)] == ["missing-key by_source.a.c"], r.stdout


def test_a_source_name_holding_a_regular_expression_character_still_compares(tmp_workspace):
    """The other half. The same record naming the source the log actually had passes."""
    source_log(tmp_workspace, REGEX_SOURCE)
    write_run(tmp_workspace, full_record(by_source={REGEX_SOURCE: 2}))
    good = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert good.returncode == 0, good.stdout + good.stderr
    write_run(tmp_workspace, full_record(by_source={REGEX_SOURCE: 2, "z": 0}))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr


# Where the badly written count sits decides which reader has to cope with it: a top-level field
# goes through json_num and a band through json_obj_nums. Both values reach `$(( ))`.
#
# The digit is 8 in both, not 4: `04` is a valid octal number and reads as 4, so a case built on it
# passes whether the reader normalises the value or hands it on as written.
LEADING_ZERO_RECORDS = {
    # matches 4 + 3 + 0 and filtered 1 against the 8 the record means by `08`.
    "top-level-count": (dict(postings_reviewed=8, matches={"strong": 4, "moderate": 3, "weak": 0},
                             filtered_out=1),
                        '"postings_reviewed": 8', '"postings_reviewed": 08'),
    # matches 8 + 0 + 0 and filtered 0 against the 8 reviewed.
    "match-band": (dict(postings_reviewed=8, matches={"strong": 8, "moderate": 0, "weak": 0},
                        filtered_out=0),
                   '"strong": 8', '"strong": 08'),
}


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("where", sorted(LEADING_ZERO_RECORDS))
def test_a_count_written_with_a_leading_zero_loses_no_finding(tmp_workspace, shell, where):
    """`08` is not a valid octal number and POSIX arithmetic reads a leading zero as octal.
    Measured on 2026-08-07 before the fix, on the top-level record below: sh exited 1 and dash
    exited 2, both with empty stdout — the `missing-key close_state` finding collected before the
    arithmetic was thrown away with the shell — and bash carried on and printed it. Three shells,
    three answers, and the two that aborted said nothing at all about a record with a missing key.

    8 is what the record means, and the two records are built so their bands add up to it, so the
    one finding every shell has to print is the missing `close_state` and nothing else.
    """
    fields, plain, zeroed = LEADING_ZERO_RECORDS[where]
    body = full_record(postings_surfaced=8, postings_unreviewed=0,
                       by_source={"linkedin": 8}, **fields)
    del body["close_state"]
    text = json.dumps(body, indent=2)
    assert text.count(plain) == 1, (where, plain)
    text = text.replace(plain, zeroed)
    (tmp_workspace / "runs" / ("%s.json" % RUN_ID)).write_text(text + "\n", encoding="utf-8")
    r = run_validator(tmp_workspace, "--post-close", RUN_ID, shell=shell)
    assert r.stderr == "", r.stderr
    assert r.returncode == 1, r.stdout + r.stderr
    assert [l.split(" ", 2)[2] for l in findings(r)] == ["missing-key close_state"], r.stdout


# --------------------------------------------------------------------------- the timestamp gates


def test_completed_at_before_started_at_fails(tmp_workspace):
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(started_at="2026-07-16T14:41:12Z",
                                         completed_at="2026-07-16T14:30:00Z"))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "completed-at-before-started-at 2026-07-16T14:30:00Z" in r.stdout, r.stdout


def test_completed_at_equal_to_started_at_passes(tmp_workspace):
    """A run that opened and closed inside one second. The clock is read to the second at both ends,
    so the two are equal rather than out of order."""
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(started_at="2026-07-16T14:30:00Z",
                                         completed_at="2026-07-16T14:30:00Z"))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr


def utc_now_plus(**kw):
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(**kw)) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")


def test_completed_at_later_than_the_file_that_states_it_fails(tmp_workspace):
    """The defect measured on 2026-08-05: a record stating 03:15:00Z, written at 03:06:50Z."""
    seed_log(tmp_workspace)
    future = utc_now_plus(hours=1)
    write_run(tmp_workspace, full_record(completed_at=future))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "completed-at-after-the-file-that-states-it %s" % future in r.stdout, r.stdout


def test_completed_at_a_minute_ahead_of_the_file_fails(tmp_workspace):
    """A minute, not an hour. The gate compares mtimes, so it has to fire on a gap smaller than any
    clock skew story would explain — the real record was nine minutes out."""
    seed_log(tmp_workspace)
    future = utc_now_plus(minutes=1)
    write_run(tmp_workspace, full_record(completed_at=future))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode != 0
    assert "completed-at-after-the-file-that-states-it %s" % future in r.stdout, r.stdout


def test_a_record_written_after_the_time_it_states_passes(tmp_workspace):
    """The other half. A gate that fired on every record would pass the two cases above and be
    useless, so a `completed_at` a minute in the past — the ordinary case, since the clock is read
    before the file is written — has to be silent."""
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record(completed_at=utc_now_plus(minutes=-1)))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_mtime_gate_fires_on_a_record_with_no_started_at(tmp_workspace):
    """The two gates were one `if` requiring both timestamps, so a record with no `started_at`
    turned the mtime gate off with it. Measured on 2026-08-07 before the split: this record drew no
    finding, and the same record with a `started_at` added reported the line below. A clock five
    hours ahead is what the gate exists to catch, and leaving a field out must not switch it off.
    """
    seed_log(tmp_workspace)
    record = full_record(completed_at="2099-01-01T00:00:00Z")
    del record["started_at"]
    write_run(tmp_workspace, record)
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 1, r.stdout + r.stderr
    assert [l.split(" ", 2)[2] for l in findings(r)] == [
        "completed-at-after-the-file-that-states-it 2099-01-01T00:00:00Z"], r.stdout


def test_a_record_with_no_started_at_and_a_past_completed_at_still_passes(tmp_workspace):
    """The other half. A mtime gate that fired whenever `started_at` was absent would pass the case
    above and fail every record written by an older close."""
    seed_log(tmp_workspace)
    record = full_record(completed_at=utc_now_plus(minutes=-1))
    del record["started_at"]
    write_run(tmp_workspace, record)
    r = run_validator(tmp_workspace, "--post-close", RUN_ID)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_mtime_gate_reads_the_stated_time_as_utc(tmp_workspace):
    """`completed_at` is UTC and `touch -t` reads local time, so the reference file is stamped with
    `TZ=UTC`. Without it the gate is wrong by the runner's offset: run under a zone 12 hours behind
    UTC, a `completed_at` 6 hours in the future would read as 6 hours in the past and pass.
    """
    seed_log(tmp_workspace)
    future = utc_now_plus(hours=6)
    write_run(tmp_workspace, full_record(completed_at=future))
    r = run_validator(tmp_workspace, "--post-close", RUN_ID, env={"TZ": "Pacific/Auckland"})
    assert r.returncode != 0
    assert "completed-at-after-the-file-that-states-it %s" % future in r.stdout, r.stdout


# --------------------------------------------------------- which files count as a run record

# One id per digit, each carrying that digit in all fourteen digit positions of the format. Between
# them they cover every position-and-digit pair the run-id glob can be wrong about — 14 x 10 = 140,
# asserted below rather than counted by eye. They are shape probes rather than instants: the glob
# checks that a run id is twenty characters in the documented arrangement, not that it names a real
# time. `close-run.sh` and `clear-run.sh` carry their own copies of the glob and
# `tests/test_mechanics_scripts.py` drives the same ten through those two.
DIGIT_COVER_RUN_IDS = [d * 4 + "-" + d * 2 + "-" + d * 2 + "T" + d * 2 + "-" + d * 2 + "-" + d * 2
                       + "Z" for d in "0123456789"]


def test_the_ten_shape_probe_ids_carry_every_digit_in_every_position():
    """The table is worth running only while it does what its comment says. The positions come from
    the format written out here, not from the script and not from the table itself."""
    template = "YYYY-MM-DDTHH-MM-SSZ"
    positions = [i for i, ch in enumerate(template) if ch in "YMDHS"]
    assert len(positions) == 14, positions
    assert len(DIGIT_COVER_RUN_IDS) == 10
    pairs = {(p, rid[p]) for rid in DIGIT_COVER_RUN_IDS for p in positions}
    assert len(pairs) == 140, len(pairs)
    for rid in DIGIT_COVER_RUN_IDS:
        assert len(rid) == len(template), rid
        assert [i for i, ch in enumerate(rid) if ch.isdigit()] == positions, rid


@pytest.mark.parametrize("run_id", DIGIT_COVER_RUN_IDS)
def test_a_record_named_with_one_digit_in_every_position_is_read(tmp_workspace, run_id):
    """A digit missing from any one of the glob's fourteen brackets makes the validator skip a
    record that is named correctly, and a skipped record is checked by nothing at all. The record
    written here is missing `close_state`, so the finding naming it is what shows the file was read
    rather than skipped."""
    record = tmp_workspace / "runs" / ("%s.json" % run_id)
    body = run_record(run_id)
    del body["close_state"]
    record.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID runs/%s.json missing-key close_state" % run_id in r.stdout, r.stdout


@pytest.mark.parametrize("run_id", DIGIT_COVER_RUN_IDS)
def test_post_close_takes_a_run_id_with_one_digit_in_every_position(tmp_workspace, run_id):
    """The other place the glob is used. A missing digit here refuses a run id `open-run.sh` minted
    and `close-run.sh` already wrote a record for, so the close could never be checked."""
    r = run_validator(tmp_workspace, "--post-close", run_id)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_record_whose_name_holds_a_newline_is_skipped(tmp_workspace):
    """Measured on 2026-08-07 with the per-line `grep -qE` this replaced: a file named
    `2026-07-16T14-30-00Z<newline>.json` was read as a run record, and its two findings printed
    across four lines — `INVALID runs/2026-07-16T14-30-00Z`, then `.json missing-key close_state`.
    A caller counting `INVALID` lines counted two findings as four, and the file each named could
    not be opened from the text printed.

    A whole-word `case` glob skips it, which is what happens to every other name in `runs/` that is
    not a run id.
    """
    record = tmp_workspace / "runs" / ("%s\n.json" % RUN_ID)
    body = run_record()
    del body["close_state"]
    record.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout


@pytest.mark.parametrize("run_id", [
    "%s\n" % RUN_ID,
    "\n%s" % RUN_ID,
    "not-a-run-id\n%s" % RUN_ID,
    "%s\n../../victim" % RUN_ID,
])
def test_post_close_with_a_run_id_holding_a_newline_is_an_operator_error(tmp_workspace, run_id):
    """Measured on 2026-08-07 with the per-line `grep -qE` this replaced: each of these was taken
    as a run id, because one of its lines is one. The path `--post-close` composes from the value
    would then name a marker and a scratch directory nothing ever wrote."""
    r = run_validator(tmp_workspace, "--post-close", run_id)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "--post-close needs a run id" in r.stderr, r.stderr


def collating_locale():
    """The name this host gives the locale below, or None where it is not installed.

    Two spellings, because `LC_ALL` has to be set to the one `locale -a` reports: macOS lists
    `ar_SA.UTF-8` and Debian lists `ar_SA.utf8`, and setting the other one leaves the process in
    the C locale, where the cases using it would pass on nothing.
    """
    have = subprocess.run(["locale", "-a"], capture_output=True, text=True).stdout.split()
    for name in ("ar_SA.UTF-8", "ar_SA.utf8"):
        if name in have:
            return name
    return None


# `2026-07-30T15-04-02Z` written in Arabic-Indic digits, under a locale whose collation makes a
# `[0-9]` range match them. `close-run.sh` and `clear-run.sh` write their ten digits out for this
# reason, and this file has to hold the same line: a validator whose glob drifted to `[0-9]` would
# read a record under this locale that those two scripts refuse to write, and skip nothing.
AR_DIGIT_RUN_ID = "٢٠٢٦-٠٧-٣٠T١٥-٠٤-٠٢Z"
COLLATING_LOCALE = collating_locale()
needs_collating_locale = pytest.mark.skipif(
    COLLATING_LOCALE is None, reason="no ar_SA UTF-8 locale is installed here")


# `bash` by name as well as `sh`, because which shell reads the script decides whether a `[0-9]`
# range would move here at all. Measured on 2026-08-07: under this locale, `case ٢٠٢٦ in [0-9][0-9]
# [0-9][0-9])` matched in bash and refused in dash, on macOS and on Debian alike. `/bin/sh` is bash
# on the machine this was written on and dash on the CI runner, so driving `sh` alone leaves the
# range form unpunished wherever `sh` is dash — measured: with `[0-9]` in the glob, the two cases
# below failed on macOS and passed on Debian until `bash` was named here.
COLLATING_SHELLS = ["sh"] + (["bash"] if shutil.which("bash") else [])


@needs_collating_locale
@pytest.mark.parametrize("shell", COLLATING_SHELLS)
def test_a_record_named_in_digits_outside_ascii_is_skipped_under_a_collating_locale(
    tmp_workspace, shell
):
    record = tmp_workspace / "runs" / ("%s.json" % AR_DIGIT_RUN_ID)
    body = run_record(AR_DIGIT_RUN_ID)
    del body["close_state"]
    record.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    r = run_validator(tmp_workspace, shell=shell, env={"LC_ALL": COLLATING_LOCALE})
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout


@needs_collating_locale
@pytest.mark.parametrize("shell", COLLATING_SHELLS)
def test_post_close_in_digits_outside_ascii_is_refused_under_a_collating_locale(
    tmp_workspace, shell
):
    r = run_validator(tmp_workspace, "--post-close", AR_DIGIT_RUN_ID, shell=shell,
                      env={"LC_ALL": COLLATING_LOCALE})
    assert r.returncode == 2, r.stdout + r.stderr
    assert "--post-close needs a run id" in r.stderr, r.stderr


@needs_collating_locale
@pytest.mark.parametrize("shell", COLLATING_SHELLS)
def test_a_real_run_id_is_still_taken_under_a_collating_locale(tmp_workspace, shell):
    """The other half. A glob that refused everything under this locale would pass both cases above
    and stop the validator reading any record at all."""
    body = run_record()
    del body["close_state"]
    (tmp_workspace / "runs" / ("%s.json" % RUN_ID)).write_text(
        json.dumps(body, indent=2) + "\n", encoding="utf-8")
    r = run_validator(tmp_workspace, shell=shell, env={"LC_ALL": COLLATING_LOCALE})
    assert r.returncode == 1, r.stdout + r.stderr
    assert "INVALID runs/%s.json missing-key close_state" % RUN_ID in r.stdout, r.stdout


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


@pytest.mark.parametrize("shell", ["sh"] + (["dash"] if shutil.which("dash") else []))
def test_the_count_and_timestamp_checks_run_under_every_shell(tmp_workspace, shell):
    """`sh -n` above reaches none of this: `[ "$ca" \\> "$sa" ]` and `[ "$ref" -nt "$record" ]` are
    both outside POSIX `test`, and a shell that lacks either would parse clean and then report
    nothing. So the whole block is driven under each shell, on a record that must pass and on one
    that must fail, and the two verdicts have to differ.
    """
    seed_log(tmp_workspace)
    write_run(tmp_workspace, full_record())
    good = run_validator(tmp_workspace, "--post-close", RUN_ID, shell=shell)
    assert good.returncode == 0, good.stdout + good.stderr
    future = utc_now_plus(hours=1)
    write_run(tmp_workspace, full_record(postings_surfaced=9, completed_at=future))
    bad = run_validator(tmp_workspace, "--post-close", RUN_ID, shell=shell)
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert "counts-disagree-with-log postings_surfaced 9 vs 2" in bad.stdout, bad.stdout
    assert "completed-at-after-the-file-that-states-it %s" % future in bad.stdout, bad.stdout
    assert bad.stderr == "", bad.stderr
