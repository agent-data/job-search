"""Unit tests for the bundled portable-shell mechanics scripts (P4/T4.1, AAS-FORM-08).

The fiddly deterministic mechanics that skills used to execute as model-run prose contracts are
now bundled as portable POSIX-`sh` scripts under `shared/scripts/mechanics/` (their single home).
Each test drives one script via subprocess against a temp fixture and asserts what the script does:
dedup, the jobs.jsonl event-line append, schedule-line composition, workspace discovery, and the
local support summary.

Scripts are invoked through `sh` (and, where present, strict `dash`) — never `bash` — so a bash-only
construct fails the suite. Nothing here asserts how the reference documents word the same rules.
"""
import os
import pathlib
import re
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MECH = ROOT / "shared" / "scripts" / "mechanics"
DEDUP = MECH / "dedup.sh"
APPEND = MECH / "event-log-append.sh"
SCHEDULE = MECH / "schedule-line.sh"
DISCOVERY = MECH / "workspace-discovery.sh"
LIFECYCLE_APPEND = MECH / "lifecycle-append.sh"
LIFECYCLE_FOLD = MECH / "lifecycle-fold.sh"
SUPPORT = MECH / "support-summary.sh"

ALL_SCRIPTS = [DEDUP, APPEND, SCHEDULE, DISCOVERY, LIFECYCLE_APPEND, LIFECYCLE_FOLD, SUPPORT]


# A contract-valid single-line `evaluated` event (conventions.md §jobs.jsonl event-line contract).
def evaluated(source, source_id, ts="2026-07-11T00:00:00Z", extra=""):
    return (
        '{"event":"evaluated","ts":"%s","source":"%s","source_id":"%s",'
        '"query_id":"q","title":"T","company_name":"C","location_display":"Remote",'
        '"salary_display":"","posted_at":"%s","source_url":"https://example/%s",'
        '"posting_id_at_seen":"jp_1","detail_read":true,"relevant":true,"match":"strong",'
        '"reasoning":"solid fit","dealbreakers_hit":[],"unknowns":[],'
        '"needs_human_check":false,"status":"new","first_seen":"%s"%s}'
        % (ts, source, source_id, ts, source_id, ts, extra)
    )


def run_sh(script, args=(), input_text=None, env=None):
    """Run a mechanics script through POSIX `sh` (portable; not bash)."""
    return subprocess.run(
        ["sh", str(script), *args],
        input=input_text,
        capture_output=True,
        text=True,
        env=env,
    )


def base_env(home):
    """A clean environment rooted at `home`: no stray registry / XDG leakage from the dev box."""
    return {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "JOBSEARCH_OS_HOME": str(home),
    }


# --------------------------------------------------------------------------- dedup

def test_dedup_emits_only_new_ids(tmp_path):
    """Plan RED case: seen registry {a,b} + candidates {a,c,d} -> the script prints c,d.

    The "seen registry" is the jobs.jsonl event log; the script extracts the known source_ids for the
    source with the pinned "Known ids" pipeline and emits the candidates not already recorded.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(evaluated("linkedin", "a") + "\n" + evaluated("linkedin", "b") + "\n")
    r = run_sh(DEDUP, [str(jobs), "linkedin"], input_text="a\nc\nd\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["c", "d"], r.stdout


def test_dedup_missing_file_all_new(tmp_path):
    """Missing jobs.jsonl = empty known set (conventions.md) -> every candidate is new."""
    jobs = tmp_path / "does-not-exist.jsonl"
    r = run_sh(DEDUP, [str(jobs), "linkedin"], input_text="x\ny\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["x", "y"], r.stdout


def test_dedup_is_per_source_and_not_confused_by_source_id_or_url(tmp_path):
    """The `"source":"S"` grep must key per-source and never match `"source_id"`/`"source_url"`.

    linkedin has 111 (and a source_url); ashby has 222. Known(linkedin) must be exactly {111}, so
    candidate 222 (ashby's id, unknown to linkedin) and 999 are new; 111 is filtered.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(evaluated("linkedin", "111") + "\n" + evaluated("ashby", "222") + "\n")
    r = run_sh(DEDUP, [str(jobs), "linkedin"], input_text="111\n222\n999\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["222", "999"], r.stdout


def test_dedup_skips_blank_candidate_lines(tmp_path):
    """Null/blank candidate source_ids can't be deduped -> skipped (runner step 2)."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(evaluated("linkedin", "a") + "\n")
    r = run_sh(DEDUP, [str(jobs), "linkedin"], input_text="\nc\n\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["c"], r.stdout


# ------------------------------------------------------------------- event-log append

def _count_source_id(path, source_id):
    if not path.exists():
        return 0
    needle = '"source_id":"%s"' % source_id
    return sum(1 for ln in path.read_text().splitlines() if needle in ln)


def test_event_log_append_writes_exactly_one_line(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    r = run_sh(APPEND, [str(jobs)], input_text=evaluated("linkedin", "X"))
    assert r.returncode == 0, r.stderr
    assert _count_source_id(jobs, "X") == 1
    assert len(jobs.read_text().splitlines()) == 1


def test_event_log_append_is_idempotent_on_source_and_source_id(tmp_path):
    """Re-appending an evaluated event for a known (source, source_id) does not duplicate it
    (conventions.md idempotency: never write a duplicate evaluated event for a known pair)."""
    jobs = tmp_path / "jobs.jsonl"
    run_sh(APPEND, [str(jobs)], input_text=evaluated("linkedin", "X", ts="2026-07-11T00:00:00Z"))
    # Same (source, source_id), later ts -> still idempotent, no second line.
    r = run_sh(APPEND, [str(jobs)], input_text=evaluated("linkedin", "X", ts="2026-07-11T09:00:00Z"))
    assert r.returncode == 0, r.stderr
    assert _count_source_id(jobs, "X") == 1, jobs.read_text()


def test_event_log_append_distinct_source_id_appends(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    run_sh(APPEND, [str(jobs)], input_text=evaluated("linkedin", "X"))
    run_sh(APPEND, [str(jobs)], input_text=evaluated("linkedin", "Y"))
    assert _count_source_id(jobs, "X") == 1
    assert _count_source_id(jobs, "Y") == 1
    assert len(jobs.read_text().splitlines()) == 2


def test_event_log_append_rejects_missing_source_id(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    bad = '{"event":"evaluated","ts":"2026-07-11T00:00:00Z","source":"linkedin","title":"T"}'
    r = run_sh(APPEND, [str(jobs)], input_text=bad)
    assert r.returncode != 0
    assert not jobs.exists() or jobs.read_text() == ""


def test_event_log_append_rejects_duplicate_source_id_key(tmp_path):
    """`"source_id"` must appear exactly once per line (grep-extraction is load-bearing)."""
    jobs = tmp_path / "jobs.jsonl"
    bad = ('{"event":"evaluated","source":"linkedin","source_id":"1","source_id":"2",'
           '"title":"T"}')
    r = run_sh(APPEND, [str(jobs)], input_text=bad)
    assert r.returncode != 0
    assert not jobs.exists() or jobs.read_text() == ""


def test_event_log_append_rejects_evaluated_without_source(tmp_path):
    """Every evaluated event carries a non-empty `"source"` (conventions.md event-line contract)."""
    jobs = tmp_path / "jobs.jsonl"
    bad = '{"event":"evaluated","ts":"2026-07-11T00:00:00Z","source_id":"9","title":"T"}'
    r = run_sh(APPEND, [str(jobs)], input_text=bad)
    assert r.returncode != 0
    assert not jobs.exists() or jobs.read_text() == ""


def test_event_log_append_rejects_multiline_input(tmp_path):
    """One event per line — a pretty-printed / multi-line event is rejected."""
    jobs = tmp_path / "jobs.jsonl"
    bad = evaluated("linkedin", "A") + "\n" + evaluated("linkedin", "B")
    r = run_sh(APPEND, [str(jobs)], input_text=bad)
    assert r.returncode != 0
    assert not jobs.exists() or jobs.read_text() == ""


def test_event_log_append_rejects_nested_same_role_as(tmp_path):
    """`same_role_as` is a FLAT string, never a nested object."""
    jobs = tmp_path / "jobs.jsonl"
    bad = evaluated("greenhouse", "acme:1", extra=',"same_role_as":{"source":"linkedin"}')
    r = run_sh(APPEND, [str(jobs)], input_text=bad)
    assert r.returncode != 0
    assert not jobs.exists() or jobs.read_text() == ""


def test_event_log_append_accepts_flat_same_role_as(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    good = evaluated("greenhouse", "acme:1", extra=',"same_role_as":"linkedin:999"')
    r = run_sh(APPEND, [str(jobs)], input_text=good)
    assert r.returncode == 0, r.stderr
    assert _count_source_id(jobs, "acme:1") == 1


# ----------------------------------------------------------------- schedule-line

@pytest.mark.parametrize(
    "args,expected",
    [
        (["hourly"], "0 * * * *"),
        (["every-2-hours"], "0 */2 * * *"),
        (["every-6-hours"], "0 */6 * * *"),
        (["daily"], "0 8 * * *"),            # default time 08:00
        (["daily", "08:00"], "0 8 * * *"),
        (["daily", "13:05"], "5 13 * * *"),
        (["weekly"], "0 8 * * 1"),           # default time 08:00, Monday
        (["weekly", "09:30"], "30 9 * * 1"),
    ],
)
def test_schedule_line_cadences(args, expected):
    r = run_sh(SCHEDULE, args)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == expected


def test_schedule_line_rejects_unknown_frequency():
    r = run_sh(SCHEDULE, ["fortnightly"])
    assert r.returncode != 0
    assert r.stdout.strip() == ""


# --------------------------------------------------------------- workspace discovery

def _discover(env):
    r = run_sh(DISCOVERY, env=env)
    assert r.returncode == 0, r.stderr
    out = {}
    for line in r.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def test_workspace_discovery_first_run_default(tmp_path):
    """No registry, no config anywhere -> first run at the default hidden workspace, source none."""
    d = _discover(base_env(tmp_path))
    assert d["workspace"] == str(tmp_path / ".job-search")
    assert d["source"] == "none"
    assert d["first_run"] == "true"


def test_workspace_discovery_default_has_config(tmp_path):
    ws = tmp_path / ".job-search"
    ws.mkdir()
    (ws / "config.yaml").write_text("version: 1\n")
    d = _discover(base_env(tmp_path))
    assert d["workspace"] == str(ws)
    assert d["source"] == "default"
    assert d["first_run"] == "false"


def test_workspace_discovery_legacy(tmp_path):
    ws = tmp_path / "job-search"  # visible legacy location
    ws.mkdir()
    (ws / "config.yaml").write_text("version: 1\n")
    d = _discover(base_env(tmp_path))
    assert d["workspace"] == str(ws)
    assert d["source"] == "legacy"
    assert d["first_run"] == "false"


def test_workspace_discovery_registry_override(tmp_path):
    """The registry's active_workspace wins, with an explicit $JOBSEARCH_OS_REGISTRY redirect."""
    custom = tmp_path / "custom-ws"
    custom.mkdir()
    (custom / "config.yaml").write_text("version: 1\n")
    reg = tmp_path / "registry.json"
    reg.write_text('{ "version": 1, "active_workspace": "%s" }\n' % custom)
    env = base_env(tmp_path)
    env["JOBSEARCH_OS_REGISTRY"] = str(reg)
    d = _discover(env)
    assert d["workspace"] == str(custom)
    assert d["source"] == "registry"
    assert d["first_run"] == "false"


def test_workspace_discovery_registry_wins_unconditionally(tmp_path):
    """Registry wins even when its workspace lacks config.yaml AND a default workspace has one
    (internals.md: 'never fall through to the other candidates')."""
    # A default workspace WITH a config that must NOT be chosen.
    default_ws = tmp_path / ".job-search"
    default_ws.mkdir()
    (default_ws / "config.yaml").write_text("version: 1\n")
    # Registry points elsewhere, to a workspace that has no config yet.
    custom = tmp_path / "custom-ws"
    reg = tmp_path / "registry.json"
    reg.write_text('{ "version": 1, "active_workspace": "%s" }\n' % custom)
    env = base_env(tmp_path)
    env["JOBSEARCH_OS_REGISTRY"] = str(reg)
    d = _discover(env)
    assert d["workspace"] == str(custom)
    assert d["source"] == "registry"
    assert d["first_run"] == "true"  # its config.yaml does not exist yet
# --------------------------------------------------------------- support summary
#
# support-summary.sh emits, on the user's explicit request, a WHITELIST-ONLY local diagnostic
# (internals.md §"Local support summary"). It is built by extracting ONLY the allowed nonsecret
# fields — build stamp, host-reported harness/version, OS/arch, schedule state, latest run health,
# internal error code, aggregate agent-data calls, and nonsecret request IDs — never by dumping and
# filtering. These tests seed EVERY forbidden secret/PII/cursor/preference/description value beside
# the allowed fields and prove the output carries the whitelist and NONE of the bait, under sh + dash.

SUPPORT_RUN_ID = "2026-07-16T14-30-00Z"

# Every forbidden value the whitelist must NEVER emit, each a unique sentinel so a single substring
# hit is a definitive leak. None contains an `E-<CAPS>` operator-code shape, so a hit could only come
# from dumping the value's home field rather than from the deliberately whitelisted internal code.
SUPPORT_BAIT = [
    "PREFERENCESBAIT_remote_only_must_have",      # preferences.md prose
    "JOBDESCBAIT_full_posting_description_text",   # full job description (jobs.jsonl)
    "MATCHPROSEBAIT_owns_the_roadmap_strong",      # match reasoning prose (jobs.jsonl)
    "sk-APIKEYBAITroute0000000000",                # API key seeded in the run record
    "sk-CONFIGAPIKEYBAIT111111111",                # API key seeded in config.yaml
    "sk-REGISTRYKEYBAIT2222222222",                # API key seeded in the registry
    "AUTHBAIT_bearer_header_value",                # auth header (run record)
    "CURSORBAIT_opaque_pagination_cursor",         # pagination cursor (run record)
    "NEXTPAGEBAIT_next_page_token_value",          # next_page_token (run record)
    "ENVDUMPBAIT_PATH_SECRET_dump",                # environment dump (run record)
    "KEYWORDBAIT_senior_staff_designer",           # search keywords (not whitelisted)
    "SCHEDIDBAIT_com_example_jobsearch",           # scheduler_id neighbor in the scheduling object
    "PRIMARYMODELBAIT_exact_model_id",             # primary_model neighbor in the scheduling object
]

# The most PII-sensitive field of all — the absolute workspace path — lives as a flat `workspace` key
# INSIDE the scheduling object in the real registry schema (internals.md). It is NOT one of the four
# scheduling fields support-summary.sh reads (installed/verified/mechanism/cadence), so it must never
# reach the summary. Seeded where it actually lives and asserted absent below.
SUPPORT_WORKSPACE_PATH_BAIT = "/Users/pii-sentinel/PRIVATE-WORKSPACEPATHBAIT"


def run_support(workspace, registry, harness="Claude Code", version="2.1.7", shell="sh"):
    """Run support-summary.sh through a POSIX shell; the whitelist-only summary is on stdout."""
    return subprocess.run(
        [shell, str(SUPPORT), str(workspace), str(registry), harness, version],
        capture_output=True,
        text=True,
    )


def _write_support_fixture(tmp_path):
    """A workspace + registry carrying EVERY whitelist field and EVERY forbidden value side by side.

    The run record is pretty-printed (multi-line) on purpose, so the mechanic must tolerate a
    formatted record and still extract by exact key rather than by dumping lines.
    """
    workspace = tmp_path / "ws"
    runs = workspace / "runs"
    (workspace / "reports").mkdir(parents=True)
    runs.mkdir(parents=True)

    # config.yaml — bait only; the mechanic must never read it.
    (workspace / "config.yaml").write_text(
        "version: 2\n"
        'search: { detail_model: "x", api_key: "sk-CONFIGAPIKEYBAIT111111111" }\n'
        'queries: [ { id: "q", keywords: "KEYWORDBAIT_senior_staff_designer" } ]\n'
    )
    # preferences.md — pure PII prose bait.
    (workspace / "preferences.md").write_text(
        "# Brief\nMust-have: PREFERENCESBAIT_remote_only_must_have.\n"
    )
    # jobs.jsonl — job-description + match-prose bait.
    (workspace / "jobs.jsonl").write_text(
        '{"event":"evaluated","source":"linkedin","source_id":"1",'
        '"reasoning":"MATCHPROSEBAIT_owns_the_roadmap_strong",'
        '"description":"JOBDESCBAIT_full_posting_description_text"}\n'
    )

    # The latest run record: blocked, whitelist fields AND forbidden neighbors, pretty-printed.
    record = (
        "{\n"
        '  "run_id": "%s",\n' % SUPPORT_RUN_ID
        + '  "run_health": "blocked",\n'
        '  "error": { "code": "E-NO-AUTH" },\n'
        '  "api_key": "sk-APIKEYBAITroute0000000000",\n'
        '  "authorization": "AUTHBAIT_bearer_header_value",\n'
        '  "environment": "ENVDUMPBAIT_PATH_SECRET_dump",\n'
        '  "queries": [\n'
        '    { "query_id": "q", "source": "linkedin",\n'
        '      "keywords": "KEYWORDBAIT_senior_staff_designer",\n'
        '      "cursor": "CURSORBAIT_opaque_pagination_cursor",\n'
        '      "next_page_token": "NEXTPAGEBAIT_next_page_token_value",\n'
        '      "request_ids": ["req_whitelist_alpha", "req_whitelist_bravo"] }\n'
        "  ],\n"
        '  "errors": [\n'
        '    { "stage": "get-posting", "code": "upstream_unavailable",\n'
        '      "request_id": "req_whitelist_charlie" }\n'
        "  ],\n"
        '  "agent_data_usage": { "metered_calls": 9,\n'
        '    "by_operation": { "initial_search": 4, "continuation_search": 2, "detail_read": 3 } },\n'
        '  "lifecycle": { "phase": "searching", "close_state": "blocked", "health": "blocked" }\n'
        "}\n"
    )
    (runs / ("%s.json" % SUPPORT_RUN_ID)).write_text(record)
    # An older run record and a non-run file — neither may be chosen as "latest".
    (runs / "2026-07-01T09-00-00Z.json").write_text('{"run_health":"healthy","error":null}\n')
    (runs / "detail-model-binding.json").write_text('{"detail_model":"x"}\n')

    registry = tmp_path / "config.json"
    registry.write_text(
        "{\n"
        '  "version": 1,\n'
        '  "active_workspace": "%s",\n' % workspace
        + '  "api_key": "sk-REGISTRYKEYBAIT2222222222",\n'
        '  "scheduling": {\n'
        '    "installed": true, "verified": true,\n'
        '    "mechanism": "launchd", "cadence": "daily",\n'
        '    "workspace": "%s",\n' % SUPPORT_WORKSPACE_PATH_BAIT
        + '    "scheduler_id": "SCHEDIDBAIT_com_example_jobsearch",\n'
        '    "primary_model": "PRIMARYMODELBAIT_exact_model_id",\n'
        '    "canary_run_id": "%s"\n' % SUPPORT_RUN_ID
        + "  }\n"
        "}\n"
    )
    return workspace, registry


def _build_stamp_fields():
    stamp = (ROOT / "shared" / "references" / "build-stamp.md").read_text()
    fields = {}
    for line in stamp.splitlines():
        if line.startswith("version:"):
            fields["version"] = line.split(":", 1)[1].strip()
        elif line.startswith("content_hash:"):
            fields["content_hash"] = line.split(":", 1)[1].strip()
    return fields


@pytest.mark.parametrize("shell", ["sh"] + (["dash"] if shutil.which("dash") else []))
def test_support_summary_is_whitelist_only_under_posix_shells(tmp_path, shell):
    """Whitelist present, EVERY forbidden value absent — the safety-critical property — under sh+dash."""
    workspace, registry = _write_support_fixture(tmp_path)
    stamp = _build_stamp_fields()

    r = run_support(workspace, registry, harness="Claude Code", version="2.1.7", shell=shell)
    assert r.returncode == 0, r.stderr
    out = r.stdout

    # --- whitelist present ---
    assert stamp["version"] in out                      # build stamp version
    assert stamp["content_hash"] in out                 # build stamp content hash
    assert "Claude Code" in out and "2.1.7" in out       # host-reported harness/version
    assert os.uname().sysname in out and os.uname().machine in out  # OS / architecture
    assert "launchd" in out and "daily" in out           # schedule state (mechanism + cadence)
    assert "installed=true" in out and "verified=true" in out
    assert "blocked" in out                              # latest run health
    assert "E-NO-AUTH" in out                            # internal error code — DELIBERATELY included
    assert "9 metered" in out                            # aggregate agent-data calls
    for rid in ("req_whitelist_alpha", "req_whitelist_bravo", "req_whitelist_charlie"):
        assert rid in out                                # nonsecret request IDs
    assert "https://github.com/agent-data/job-search/issues" in out

    # --- none of the forbidden values leaked ---
    for bait in SUPPORT_BAIT:
        assert bait not in out, "LEAKED forbidden value %r under %s" % (bait, shell)
    # The flat scheduling `workspace` absolute path — the most PII-sensitive field, and the one the real
    # registry schema keeps in the scheduling object — is read for none of the whitelist fields.
    assert SUPPORT_WORKSPACE_PATH_BAIT not in out, "LEAKED workspace path"


def test_support_summary_selects_the_newest_run_record_only(tmp_path):
    """Only the newest run_id-shaped record supplies health/code/calls; the sidecar is never read."""
    workspace, registry = _write_support_fixture(tmp_path)
    r = run_support(workspace, registry)
    assert r.returncode == 0, r.stderr
    assert SUPPORT_RUN_ID in r.stdout            # the 2026-07-16 record, not the 2026-07-01 one
    assert "blocked" in r.stdout                 # its health, not the older record's "healthy"


def test_support_summary_graceful_when_no_workspace_or_registry(tmp_path):
    """A first-run user with no runs and no registry still gets build/harness/OS + the issues link."""
    workspace = tmp_path / "empty-ws"    # never created
    registry = tmp_path / "absent.json"  # never created
    r = run_support(workspace, registry, harness="Codex", version="9.9")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "Codex" in out and "9.9" in out
    assert os.uname().sysname in out
    assert "not configured" in out       # no scheduling object
    assert "none recorded" in out        # no latest run record
    assert "https://github.com/agent-data/job-search/issues" in out


def test_support_summary_healthy_run_fabricates_no_error_code(tmp_path):
    """A healthy run (error null) reports no operator code — the code is read, never invented."""
    workspace = tmp_path / "ws"
    runs = workspace / "runs"
    runs.mkdir(parents=True)
    (runs / ("%s.json" % SUPPORT_RUN_ID)).write_text(
        '{ "run_id": "%s", "run_health": "healthy", "error": null,\n'
        '  "agent_data_usage": { "metered_calls": 3 },\n'
        '  "queries": [ { "request_ids": ["req_ok_one"] } ] }\n' % SUPPORT_RUN_ID
    )
    registry = tmp_path / "config.json"
    registry.write_text('{ "version": 1, "scheduling": { "installed": false, "verified": false } }\n')
    r = run_support(workspace, registry, harness="Cursor", version="1.0")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "healthy" in out
    assert "3 metered" in out
    assert "req_ok_one" in out
    assert "installed=false" in out and "verified=false" in out
    assert re.search(r"E-[A-Z0-9]", out) is None   # no operator code fabricated when error is null


# ------------------------------------------------------------------- POSIX portability

def test_scripts_pass_posix_syntax_check():
    """Each script is POSIX `sh` (not bash-only): `sh -n` and strict `dash -n` both clean."""
    shells = ["sh"]
    if shutil.which("dash"):
        shells.append("dash")
    for script in ALL_SCRIPTS:
        assert script.exists(), "missing script: %s" % script
        for sh in shells:
            r = subprocess.run([sh, "-n", str(script)], capture_output=True, text=True)
            assert r.returncode == 0, "%s -n failed on %s:\n%s" % (sh, script.name, r.stderr)
