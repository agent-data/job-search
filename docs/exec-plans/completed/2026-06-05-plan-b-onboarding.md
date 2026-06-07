---
title: Plan B — Claude-Code-Driven Onboarding
state: completed
created: 2026-06-05
completed: 2026-06-07
---

# Job Search OS — Plan B: Claude-Code-driven Onboarding + OS internals — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the entire job-search setup Claude-Code-driven — a single `/job-search` orchestrator onboards a user end-to-end (prereqs → workspace → preferences → queries + frequency → first live run → scheduling) and shows a home screen on return, backed by persistent "OS internals" (a registry + a discovery/scheduling script + an OS manual) that every skill uses identically.

**Architecture:** A dependency-free `scripts/osctl.py` (stdlib only; mirrors `state.py`) owns the deterministic OS state — registry read/write (JSON at XDG `~/.config/job-search-os/config.json`), workspace discovery (registry → `~/.job-search/` → legacy `~/job-search/` → first-run), and scheduling-artifact generation (cron line / launchd plist) + a scheduling marker. A `shared/references/internals.md` documents the schema/algorithm/recipes for the model. Two new skills — `job-search` (orchestrator/home) and `job-preference-interview` (prose-only) — plus wiring `job-search-run` and `evaluate-job-fit` to resolve the workspace via `osctl.py`. `config.yaml` edits stay model-driven (stdlib has no YAML parser; we keep the dependency-free constraint), which is also the conversational-first config path.

**Tech Stack:** Python 3.9+ stdlib (`argparse`, `json`, `os`, `datetime`); pytest; Claude Code skills (SKILL.md + YAML frontmatter + `references/`); skill-creator for authoring/evals; the existing `tests/fake-agent-data` PATH shim (zero real credits).

---

## Philosophy guardrails (every task must hold these)

- **Qualitative relevance only** — never a numeric score, 0–100, points, or category weights.
- **Frequency, not budget** — no credit/USD math anywhere a user decides; cost only via reactive `E-QUOTA`.
- **No silent failures** — every blocked path is a named `E-*` (cause + fix); headless runs exit non-zero.
- **Conversational-first config** — every change has a Claude-driven path; manual editing is an escape hatch.
- **Never clobber real data** — adopt an existing workspace; never overwrite `config.yaml`/`preferences.md`/`jobs.jsonl`.
- **Single source of truth** — edit `shared/references/*` and `scripts/*`, then run `./scripts/build.sh`; never hand-edit a skill's synced `references/`/`scripts/` copies.

## File Structure

**Create:**
- `scripts/osctl.py` — OS internals CLI (registry, discovery, scheduling artifacts). Stdlib only. *(named `osctl.py`, NOT `os.py`, to avoid shadowing the stdlib `os` module on `sys.path[0]`.)*
- `tests/test_osctl.py` — pytest for `osctl.py` (mirrors `tests/test_state.py`).
- `shared/references/internals.md` — the OS manual (registry schema, discovery algorithm, first-run detection, never-clobber adoption, config read/update recipes, scheduling-setup knowledge).
- `skills/job-preference-interview/SKILL.md` (+ `evals/`) — prose-only interview.
- `skills/job-search/SKILL.md`, `skills/job-search/references/onboarding.md`, `skills/job-search/references/home.md` (+ `evals/`) — the orchestrator/shell.
- `skills/job-search/evals/files/setup-onboarding.sh`, `skills/job-preference-interview/evals/files/setup-interview-ws.sh` — eval harness setup.

**Modify:**
- `scripts/build.sh` — also bundle `osctl.py` (and `state.py`) into every skill's `scripts/`.
- `shared/references/errors.md` — fix `E-NO-CONFIG` fix-copy (`/job-search`), add `E-NO-AGENT-DATA`.
- `shared/references/conventions.md` — new hidden default `~/.job-search/`; pointer to `internals.md`.
- `skills/job-search-run/SKILL.md` — resolve workspace via `osctl.py`; add `E-NO-AGENT-DATA` preflight; stay headless.
- `skills/job-search-run/evals/evals.json` — harness uses `--workspace <tmp>`; add a first-run E-NO-CONFIG eval.
- `skills/evaluate-job-fit/SKILL.md` — resolve workspace via `osctl.py` (fallback to pasted brief).

**Synced (do not hand-edit; produced by `build.sh`):** `skills/*/references/*.md`, `skills/*/scripts/*.py`.

---

## Setup: branch

- [ ] **Step 1: Create a feature branch**

```bash
cd ~/job-search-os && git checkout -b plan-b-onboarding && git status --short --branch
```
Expected: `## plan-b-onboarding`, clean tree.

---

## Milestone B-I — OS internals foundation

### Task B1: `osctl.py` — registry + workspace discovery (`resolve`, `set-active`) [TDD]

**Files:**
- Create: `scripts/osctl.py`
- Test: `tests/test_osctl.py`

- [ ] **Step 1: Write the failing tests** (`tests/test_osctl.py`)

```python
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
```

- [ ] **Step 2: Run the tests, verify they fail**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_osctl.py -q`
Expected: FAIL (no such file `scripts/osctl.py`).

- [ ] **Step 3: Implement `scripts/osctl.py`** (resolve + set-active + the shared helpers + a `main()` wiring only these two subcommands)

```python
#!/usr/bin/env python3
"""osctl.py — Job Search OS internals: registry + workspace discovery + scheduling artifacts.

Deterministic, dependency-free (stdlib only; NOT YAML-aware). The registry is a small JSON file
(machine-managed OS state); the workspace's config.yaml stays the user-facing config.

NOTE: this file is deliberately NOT named os.py — that would shadow the stdlib `os` module when run
as a script (the script dir lands on sys.path[0]).

Path defaults can be redirected for tests/evals without touching real data, via flags or env:
  registry:  --registry  >  $JOBSEARCH_OS_REGISTRY  >  $XDG_CONFIG_HOME/job-search-os/config.json  >  ~/.config/...
  workspaces: --default-workspace/--legacy-workspace  >  derived from $JOBSEARCH_OS_HOME  >  ~
"""
import argparse, json, os, sys
from datetime import datetime, timezone

REGISTRY_VERSION = 1
CONFIG_NAME = "config.yaml"


def _home():
    return os.environ.get("JOBSEARCH_OS_HOME") or os.path.expanduser("~")

def default_workspace():
    return os.path.join(_home(), ".job-search")

def legacy_workspace():
    return os.path.join(_home(), "job-search")

def registry_path(override=None):
    if override:
        return override
    if os.environ.get("JOBSEARCH_OS_REGISTRY"):
        return os.environ["JOBSEARCH_OS_REGISTRY"]
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(_home(), ".config")
    return os.path.join(xdg, "job-search-os", "config.json")

def read_registry(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise ValueError(f"registry at {path} is not valid JSON: {exc}") from exc

def write_registry(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

def has_config(workspace):
    return bool(workspace) and os.path.isfile(os.path.join(workspace, CONFIG_NAME))

def resolve(registry_override=None, default_ws=None, legacy_ws=None):
    default_ws = default_ws or default_workspace()
    legacy_ws = legacy_ws or legacy_workspace()
    reg = read_registry(registry_path(registry_override))
    if reg and reg.get("active_workspace"):
        ws = reg["active_workspace"]
        return {"workspace": ws, "first_run": not has_config(ws), "source": "registry"}
    if has_config(default_ws):
        return {"workspace": default_ws, "first_run": False, "source": "default"}
    if has_config(legacy_ws):
        return {"workspace": legacy_ws, "first_run": False, "source": "legacy"}
    return {"workspace": default_ws, "first_run": True, "source": "none"}

def cmd_resolve(args):
    try:
        print(json.dumps(resolve(args.registry, args.default_workspace, args.legacy_workspace)))
    except ValueError as e:
        print(f"resolve failed: {e}", file=sys.stderr); return 1
    return 0

def cmd_set_active(args):
    try:
        path = registry_path(args.registry)
        reg = read_registry(path) or {"version": REGISTRY_VERSION}
        reg["version"] = REGISTRY_VERSION
        reg["active_workspace"] = os.path.abspath(os.path.expanduser(args.workspace))
        write_registry(path, reg)   # writes ONLY the registry; never touches the workspace
        print(json.dumps(reg))
    except ValueError as e:
        print(f"set-active failed: {e}", file=sys.stderr); return 1
    return 0

def main(argv=None):
    p = argparse.ArgumentParser(description="Job Search OS internals (registry, discovery, scheduling)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("resolve", help="print active workspace + first_run + source as JSON")
    r.add_argument("--registry"); r.add_argument("--default-workspace"); r.add_argument("--legacy-workspace")
    r.set_defaults(func=cmd_resolve)

    s = sub.add_parser("set-active", help="record the active workspace in the registry")
    s.add_argument("--workspace", required=True); s.add_argument("--registry")
    s.set_defaults(func=cmd_set_active)

    args = p.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests, verify they pass**

Run: `python3 -m pytest tests/test_osctl.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/osctl.py tests/test_osctl.py
git commit -m "feat(osctl): registry + workspace discovery (resolve, set-active) with never-clobber"
```

### Task B2: `osctl.py` — scheduling artifacts (`schedule-line`, `launchd-plist`) [TDD]

**Files:**
- Modify: `scripts/osctl.py`
- Test: `tests/test_osctl.py`

- [ ] **Step 1: Append failing tests** to `tests/test_osctl.py`

```python
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
```

- [ ] **Step 2: Run, verify the new tests fail**

Run: `python3 -m pytest tests/test_osctl.py -q -k "schedule_line or launchd"`
Expected: FAIL (`invalid choice: 'schedule-line'`).

- [ ] **Step 3: Add the implementation to `scripts/osctl.py`** (insert these functions above `main()`)

```python
CRON = {"hourly": "0 * * * *", "every-2-hours": "0 */2 * * *", "every-6-hours": "0 */6 * * *"}

def cron_schedule(frequency, time_str):
    if frequency in CRON:
        return CRON[frequency]
    hh, mm = (time_str or "08:00").split(":"); h, m = int(hh), int(mm)
    if frequency == "daily":
        return f"{m} {h} * * *"
    if frequency == "weekly":
        return f"{m} {h} * * 1"   # Monday
    raise ValueError(f"unknown frequency {frequency!r} (hourly|every-2-hours|every-6-hours|daily|weekly)")

def cron_line(frequency, time_str, workspace):
    ws = workspace or default_workspace()
    return f'{cron_schedule(frequency, time_str)} cd {ws} && claude -p "/job-search-run" >> {ws}/runs/cron.log 2>&1'

def cmd_schedule_line(args):
    try:
        print(cron_line(args.frequency, args.time, args.workspace))
    except ValueError as e:
        print(f"schedule-line failed: {e}", file=sys.stderr); return 1
    return 0

PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>dev.jobsearchos.run</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string><string>-lc</string>
    <string>cd {ws} &amp;&amp; claude -p "/job-search-run" >> {ws}/runs/cron.log 2>&amp;1</string>
  </array>
  <key>StartCalendarInterval</key><dict>{cal}</dict>
  <key>RunAtLoad</key><false/>
</dict>
</plist>"""

def launchd_cal(frequency, time_str):
    hh, mm = (time_str or "08:00").split(":"); h, m = int(hh), int(mm)
    if frequency == "hourly":
        return "<key>Minute</key><integer>0</integer>"
    if frequency == "daily":
        return f"<key>Hour</key><integer>{h}</integer><key>Minute</key><integer>{m}</integer>"
    if frequency == "weekly":
        return f"<key>Weekday</key><integer>1</integer><key>Hour</key><integer>{h}</integer><key>Minute</key><integer>{m}</integer>"
    raise ValueError(f"launchd plist supports hourly|daily|weekly; for {frequency!r} use cron")

def cmd_launchd_plist(args):
    try:
        print(PLIST.format(ws=(args.workspace or default_workspace()), cal=launchd_cal(args.frequency, args.time)))
    except ValueError as e:
        print(f"launchd-plist failed: {e}", file=sys.stderr); return 1
    return 0
```

Then wire the subparsers — insert into `main()` immediately before `args = p.parse_args(argv)`:

```python
    sl = sub.add_parser("schedule-line", help="emit the cron line for a frequency")
    sl.add_argument("--frequency", required=True); sl.add_argument("--time", default="08:00")
    sl.add_argument("--timezone"); sl.add_argument("--workspace")   # timezone accepted; cron uses system tz
    sl.set_defaults(func=cmd_schedule_line)

    lp = sub.add_parser("launchd-plist", help="emit a launchd plist (macOS)")
    lp.add_argument("--frequency", required=True); lp.add_argument("--time", default="08:00"); lp.add_argument("--workspace")
    lp.set_defaults(func=cmd_launchd_plist)
```

- [ ] **Step 4: Run, verify pass**

Run: `python3 -m pytest tests/test_osctl.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add scripts/osctl.py tests/test_osctl.py
git commit -m "feat(osctl): deterministic cron-line + launchd-plist generation"
```

### Task B3: `osctl.py` — scheduling marker (`schedule-status`, `set-scheduled`) [TDD]

**Files:**
- Modify: `scripts/osctl.py`
- Test: `tests/test_osctl.py`

- [ ] **Step 1: Append failing tests**

```python
# --- schedule-status / set-scheduled ---
def test_schedule_status_default_not_installed(tmp_path):
    out = json.loads(run(["schedule-status", "--registry", str(tmp_path / "absent.json")]).stdout)
    assert out == {"installed": False, "mechanism": None, "set_at": None}

def test_set_scheduled_roundtrip_and_preserves_active(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir(); reg = tmp_path / "reg.json"
    run(["set-active", "--registry", str(reg), "--workspace", str(ws)])
    run(["set-scheduled", "--registry", str(reg), "--mechanism", "launchd", "--set-at", "2026-06-05T08:00:00+00:00"])
    data = json.loads(reg.read_text())
    assert data["active_workspace"] == str(ws.resolve())          # set-scheduled preserved active_workspace
    assert data["scheduling"] == {"installed": True, "mechanism": "launchd", "set_at": "2026-06-05T08:00:00+00:00"}
    out = json.loads(run(["schedule-status", "--registry", str(reg)]).stdout)
    assert out["installed"] is True and out["mechanism"] == "launchd"

def test_set_active_preserves_scheduling(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir(); reg = tmp_path / "reg.json"
    run(["set-scheduled", "--registry", str(reg), "--mechanism", "cron", "--set-at", "2026-06-05T08:00:00+00:00"])
    run(["set-active", "--registry", str(reg), "--workspace", str(ws)])
    assert json.loads(reg.read_text())["scheduling"]["mechanism"] == "cron"   # not dropped
```

- [ ] **Step 2: Run, verify fail** — `python3 -m pytest tests/test_osctl.py -q -k "schedule_status or set_scheduled or set_active_preserves"` → FAIL.

- [ ] **Step 3: Add implementation** to `scripts/osctl.py` (functions above `main()`):

```python
def cmd_schedule_status(args):
    try:
        reg = read_registry(registry_path(args.registry)) or {}
        print(json.dumps(reg.get("scheduling") or {"installed": False, "mechanism": None, "set_at": None}))
    except ValueError as e:
        print(f"schedule-status failed: {e}", file=sys.stderr); return 1
    return 0

def cmd_set_scheduled(args):
    try:
        path = registry_path(args.registry)
        reg = read_registry(path) or {"version": REGISTRY_VERSION}
        reg["version"] = REGISTRY_VERSION
        reg["scheduling"] = {"installed": True, "mechanism": args.mechanism,
                             "set_at": args.set_at or datetime.now(timezone.utc).isoformat(timespec="seconds")}
        write_registry(path, reg)
        print(json.dumps(reg["scheduling"]))
    except ValueError as e:
        print(f"set-scheduled failed: {e}", file=sys.stderr); return 1
    return 0
```

Wire subparsers in `main()` (before `args = p.parse_args(argv)`):

```python
    ss = sub.add_parser("schedule-status", help="print the scheduling marker as JSON")
    ss.add_argument("--registry"); ss.set_defaults(func=cmd_schedule_status)

    sd = sub.add_parser("set-scheduled", help="record that scheduling was installed")
    sd.add_argument("--mechanism", required=True, choices=["cron", "launchd", "loop"])
    sd.add_argument("--set-at"); sd.add_argument("--registry"); sd.set_defaults(func=cmd_set_scheduled)
```

- [ ] **Step 4: Run full osctl suite, verify pass** — `python3 -m pytest tests/test_osctl.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/osctl.py tests/test_osctl.py
git commit -m "feat(osctl): scheduling marker (schedule-status, set-scheduled)"
```

### Task B4: OS manual + reference updates + build.sh bundling [docs/build]

**Files:**
- Create: `shared/references/internals.md`
- Modify: `shared/references/errors.md`, `shared/references/conventions.md`, `scripts/build.sh`

- [ ] **Step 1: Update `scripts/build.sh`** to bundle both scripts into every skill. Replace the body's loop + state.py block (lines 10–18) with:

```bash
# 1) Sync shared references AND bundle the helper scripts into every skill (self-contained loose mode).
for skill in skills/*/; do
  mkdir -p "${skill}references" "${skill}scripts"
  cp shared/references/*.md "${skill}references/"
  cp scripts/state.py scripts/osctl.py "${skill}scripts/"
done

echo "build: synced references + bundled state.py/osctl.py into $(ls -d skills/*/ | wc -l | tr -d ' ') skill(s)"
```

- [ ] **Step 2: Fix + extend `shared/references/errors.md`.** In the table, change the `E-NO-CONFIG` row's fix copy from `Run \`/job-search-setup\` to create one.` to `Run \`/job-search\` to set it up.`. Then add this row (place it first, above `E-NO-CONFIG`):

```
| **E-NO-AGENT-DATA** | the `agent-data` CLI is not found on PATH (prereq check, before `whoami`) | "The agent-data CLI isn't installed. Install it (`npm install -g agent-data`), then run `agent-data whoami` to authenticate. Nothing was pulled." | HALT, exit 1 |
```

- [ ] **Step 3: Update `shared/references/conventions.md`.** Change line 3 to:

```
The **workspace** (default the hidden `~/.job-search/`; an existing visible `~/job-search/` is **adopted**, not replaced — see `internals.md`) is PRIVATE per-user data — never committed to a public repo.
```

Change the layout block heading `~/job-search/` to `~/.job-search/`. Add this line directly under the layout block:

```
**Discovery & OS state:** skills never hard-code the workspace path — they resolve it with `osctl.py resolve` (registry → `~/.job-search/` → legacy `~/job-search/` → first-run). The registry and the discovery/first-run/scheduling rules live in `internals.md`.
```

- [ ] **Step 4: Create `shared/references/internals.md`** with the complete OS manual:

```markdown
# OS internals — registry, workspace discovery, config & scheduling

The "OS state" that survives across sessions so any skill finds the user's data identically. Deterministic
parts live in `scripts/osctl.py` (bundled into each skill at `scripts/osctl.py`; resolve its absolute path
from the skill's own directory and call it as `$OS`, exactly like `$STATE`). Never hard-code or re-derive
the paths below — call `osctl.py`.

## Registry (machine-managed OS state — JSON, not YAML)
Location: `$XDG_CONFIG_HOME/job-search-os/config.json`, i.e. `~/.config/job-search-os/config.json`
(fallback `~/.job-search-os/config.json` when `~/.config` is unavailable). Tests/evals redirect it with
`$JOBSEARCH_OS_REGISTRY`. Schema:
```json
{ "version": 1,
  "active_workspace": "/Users/<u>/.job-search",
  "scheduling": { "installed": true, "mechanism": "cron|launchd|loop", "set_at": "<iso>" } }
```
The registry is machine state; the workspace's `config.yaml` stays the user-facing config.

## Workspace discovery & first-run detection
`python3 "$OS" resolve` → `{"workspace": "<abs>", "first_run": <bool>, "source": "registry|default|legacy|none"}`.
Order: registry `active_workspace` (if it has `config.yaml`) → `~/.job-search/` (if `config.yaml`) →
legacy `~/job-search/` (if `config.yaml`) → else **first-run** (workspace = `~/.job-search/`, not yet created).
First-run = no candidate workspace has a `config.yaml`.

## Never-clobber adoption
If `resolve` returns `source: "legacy"` (or you otherwise find an existing workspace), **adopt** it:
`python3 "$OS" set-active --workspace <path>` (writes only the registry). NEVER overwrite an existing
`config.yaml`, `preferences.md`, or `jobs.jsonl`; only additively create missing `runs/` and `reports/`.
Tell the user: "Found an existing workspace at <path> — using it."

## Config read/update recipes (conversational-first; config.yaml is YAML)
The user changes config by **chatting**; manual editing is an escape hatch. To apply a change, read
`<workspace>/config.yaml`, edit it minimally (preserve comments/structure), and write it back.
- **Add a query:** append to `queries:` an item like
  `  - { id: "ml-platform-sf", keywords: "ML platform engineer", location: "San Francisco Bay Area", limit: 25, enabled: true }`
- **Change frequency:** set `schedule.frequency` to one of `hourly | every-2-hours | every-6-hours | daily | weekly`.
- **Change run time:** set `schedule.time` (HH:MM, used for daily/weekly).
- Always keep `version: 1`. NEVER add a budget, cost, or score/weight field (philosophy).

## Scheduling setup (offer to set it up; consent + marker; always show the copy-paste fallback)
Generate the artifact deterministically: `python3 "$OS" schedule-line --frequency <f> --time <t> --workspace <ws>`
(cron), or `python3 "$OS" launchd-plist --frequency <f> --time <t> --workspace <ws>` (macOS robust). Explain
the options, ask a yes/no, and ONLY on yes perform the privileged write (append the crontab line, or write the
plist to `~/Library/LaunchAgents/dev.jobsearchos.run.plist` and `launchctl load` it). Then record it:
`python3 "$OS" set-scheduled --mechanism <cron|launchd|loop>`. Check `schedule-status` so you never re-ask.
ALWAYS also print this copy-paste fallback verbatim:

```
OPTION A — OS cron (recommended; runs even when Claude is closed)
  crontab -e  →  0 8 * * *  cd ~/.job-search && claude -p "/job-search-run" >> ~/.job-search/runs/cron.log 2>&1
       (an hourly frequency would generate `0 * * * *`, etc. — setup writes the line matching your choice)
  • Verify now:  cd ~/.job-search && claude -p "/job-search-run"
  • macOS: the Mac must be awake at run time — keep it on, use `caffeinate`, or install the launchd plist
    (StartCalendarInterval can wake the machine — the robust mac option).
OPTION B — keep Claude open and loop:  /loop <frequency> /job-search-run
Not sure? Use Option A.
```

## osctl.py command reference
`resolve` · `set-active --workspace P` · `schedule-line --frequency F [--time T] [--workspace W]` ·
`launchd-plist --frequency F [--time T] [--workspace W]` · `schedule-status` · `set-scheduled --mechanism M`.
All accept `--registry P` (and resolve accepts `--default-workspace`/`--legacy-workspace`) for tests/evals.
```

- [ ] **Step 5: Sync and verify build**

Run: `cd ~/job-search-os && ./scripts/build.sh && python3 -m pytest -q`
Expected: build prints the sync line; all tests pass (state + osctl + fake-agent-data). Confirm each skill now has `scripts/osctl.py` and `references/internals.md`:
Run: `ls skills/*/scripts/osctl.py skills/*/references/internals.md`

- [ ] **Step 6: Commit**

```bash
git add shared/references/internals.md shared/references/errors.md shared/references/conventions.md scripts/build.sh skills/
git commit -m "feat(internals): OS manual + E-NO-AGENT-DATA + hidden ~/.job-search default; bundle osctl into all skills"
```

---

## Milestone B-II — Preferences interview (prose-only)

### Task B5: `job-preference-interview` skill [skill-creator authoring]

**Files:**
- Create: `skills/job-preference-interview/SKILL.md`

- [ ] **Step 1: Author the SKILL.md.** Frontmatter (exact):

```yaml
---
name: job-preference-interview
description: Build or update the user's Job Preferences Brief through a one-question-at-a-time interview, producing a prose preferences.md (Summary, Must-haves/dealbreakers, Strong preferences, Nice-to-haves, Red flags). Also imports an existing brief. Use when the user wants to set up or refine what they want in a job, or when job-search onboarding needs a brief.
disable-model-invocation: false
user-invocable: true
---
```

Body must contain these sections (author the prose with skill-creator; honor the constraints exactly):

- **Purpose** — produce a PROSE brief the model reads to judge postings qualitatively. **No numeric scoring, no 0–100 rubric, no category weights** (this is the explicit refactor of the old interview doc). Interactive only — never used in a headless run.
- **Where it writes** — resolve the workspace with `python3 "$OS" resolve` (bundled `scripts/osctl.py`; `$OS` from this skill's own dir). Write the brief to `<workspace>/<config.workspace.preferences_path>` (default `preferences.md`). If `resolve` reports `first_run` (no workspace yet) and you were invoked standalone, write to the resolved default path and tell the user. Put a `created_at: YYYY-MM-DD` line at the top (front-matter style, matching `templates/preferences.example.md`).
- **Interview method** — ask ONE main question at a time (one tight follow-up ok); WAIT for the answer. Start with the user's current situation and what's prompting the search, then work the dimensions below. Turn vague answers ("good culture") into concrete, observable criteria. Offer example options/scales to make answering easy; let the user say "no preference / skip / dealbreaker". Reflect back every 4–5 questions. Keep messages short.
- **Dimensions** (cover, skip any the user says don't matter): 1 Role (function, title, seniority, scope, IC vs manager); 2 Industry/domain/mission/product; 3 Company (size, stage, culture, values); 4 Compensation (base, bonus, equity, benefits, minimum acceptable) — captured as prose, never as math; 5 Location & arrangement (remote/hybrid/onsite, geography, travel, relocation); 6 Work-life balance (hours, intensity, on-call, PTO); 7 Growth (learning, promotion, mentorship); 8 Team & management; 9 Tools/tech stack/skills; 10 Stability vs risk; 11 Hard constraints/dealbreakers. For each: what the user wants AND how much it matters AND what would be a dealbreaker.
- **Calibration (qualitative buckets, NOT weights)** — sort factors into **Must-haves/dealbreakers**, **Strong preferences**, **Nice-to-haves**, **Red flags**. Do NOT ask the user to assign numeric weights and do NOT produce a scoring formula.
- **Output: the brief** — write the prose document with exactly these sections: a 2–3 sentence **Summary**; **Must-haves / dealbreakers** (binary, checkable); **Strong preferences**; **Nice-to-haves**; **Red flags**. Each item plain and observable (a reader could check it against a posting). End with a one-line "How to use this" note: Claude reads this brief next to a posting and judges relevant / not, and if relevant weak/moderate/strong — with reasoning, no score.
- **Import an existing brief** — if the user says they already have one, accept a file path or pasted prose. Validate it's usable: has at least a Summary and Must-haves, and is prose (not a 0–100 rubric). If it contains a numeric rubric/weights, tell the user this system is qualitative and offer to convert it to prose (drop the numbers). If it's thin, offer a few enrich questions. Then write `preferences.md`.

- [ ] **Step 2: Sync + sanity-check the frontmatter loads**

Run: `cd ~/job-search-os && ./scripts/build.sh && python3 - <<'PY'
import pathlib, re
t = pathlib.Path("skills/job-preference-interview/SKILL.md").read_text()
assert t.startswith("---") and "name: job-preference-interview" in t
assert "0–100" not in t and "scoring rubric" not in t.lower()  # numeric rubric must be gone
print("ok")
PY`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add skills/job-preference-interview/SKILL.md skills/
git commit -m "feat(skill): job-preference-interview — prose-only brief (drops the 0–100 rubric)"
```

### Task B6: `job-preference-interview` evals [skill-creator evals]

**Files:**
- Create: `skills/job-preference-interview/evals/evals.json`
- Create: `skills/job-preference-interview/evals/files/setup-interview-ws.sh`
- Create: `skills/job-preference-interview/evals/files/imported-brief.md` (a usable prose brief), `imported-rubric-brief.md` (a brief that wrongly includes a 0–100 rubric)

- [ ] **Step 1: Create the eval workspace setup script** `evals/files/setup-interview-ws.sh`:

```bash
#!/usr/bin/env bash
# Usage: setup-interview-ws.sh <tmp>. Isolated, no real data touched: the eval exports
# JOBSEARCH_OS_REGISTRY=<tmp>/registry.json and JOBSEARCH_OS_HOME=<tmp> so resolve → first-run default
# <tmp>/.job-search. Prints <tmp>.
set -euo pipefail
DEST="$1"; mkdir -p "$DEST"; echo "$DEST"
```

- [ ] **Step 2: Create the eval fixtures.** `imported-brief.md` = a short, well-formed prose brief (Summary + Must-haves + Strong preferences + Red flags; no numbers). `imported-rubric-brief.md` = same but with a "Scoring rubric: 0–100…" section and per-category weights.

- [ ] **Step 3: Author `evals/evals.json`** (harness + cases):

```json
{
  "skill_name": "job-preference-interview",
  "harness": "For each case: run skills/job-preference-interview/evals/files/setup-interview-ws.sh <tmp>; export JOBSEARCH_OS_REGISTRY=<tmp>/registry.json and JOBSEARCH_OS_HOME=<tmp> (so the brief is written under <tmp>/.job-search, never real data). Invoke /job-preference-interview. When the skill asks questions, answer with the canned answers in the prompt. Then inspect <tmp>/.job-search/preferences.md.",
  "evals": [
    { "id": 1, "scenario": "fresh interview",
      "prompt": "Canned answers: situation='employed, passively looking'; role='senior/staff AI engineer, individual contributor, NOT management'; domain='LLM products at a startup'; location='remote in the US, or SF Bay onsite; onsite elsewhere is a dealbreaker'; comp='wants meaningful equity; base flexible'; wlb='no heavy on-call'; stack='Python + modern LLM tooling'; dealbreakers='primarily people-management; onsite outside SF'. When asked to calibrate, keep it qualitative. Finish the interview.",
      "expectations": [
        "Asks questions ONE at a time (not a single long dump)",
        "Writes <tmp>/.job-search/preferences.md containing all five sections: Summary, Must-haves / dealbreakers, Strong preferences, Nice-to-haves, Red flags, plus a created_at line",
        "Items are concrete/observable prose (e.g. 'Remote within the US, or SF Bay onsite')",
        "Contains NO numeric score, NO 0–100 rubric, NO category weights, NO scoring formula",
        "The IC-not-management and onsite-location dealbreakers appear under Must-haves / dealbreakers"
      ] },
    { "id": 2, "scenario": "import a usable prose brief",
      "prompt": "User says 'I already have a brief' and provides the contents of evals/files/imported-brief.md. Do not run a full interview.",
      "expectations": [
        "Skips the full interview",
        "Writes <tmp>/.job-search/preferences.md preserving the user's prose (sections intact)",
        "Adds/keeps a created_at line; output has no numeric scoring"
      ] },
    { "id": 3, "scenario": "import a brief that contains a 0–100 rubric",
      "prompt": "User provides evals/files/imported-rubric-brief.md (which includes a 0–100 scoring rubric and per-category weights).",
      "expectations": [
        "Notes that this system judges qualitatively and converts the brief to prose, dropping the numeric rubric/weights",
        "The written preferences.md contains the prose sections and NO 0–100 rubric and NO weights"
      ] }
  ]
}
```

- [ ] **Step 4: Run the evals via skill-creator** (the Skill tool: `skill-creator`, run-evals mode against this skill). Iterate the SKILL.md until all three pass. Zero real API credits (no agent-data calls in the interview).

- [ ] **Step 5: Commit**

```bash
git add skills/job-preference-interview/evals/
git commit -m "test(skill): job-preference-interview evals (fresh / import-prose / import-rubric→prose)"
```

---

## Milestone B-III — Orchestrator (the OS shell)

### Task B7: `job-search` orchestrator — SKILL.md + onboarding.md + home.md [skill-creator authoring]

**Files:**
- Create: `skills/job-search/SKILL.md`, `skills/job-search/references/onboarding.md`, `skills/job-search/references/home.md`

- [ ] **Step 1: Author `skills/job-search/SKILL.md`.** Frontmatter (exact):

```yaml
---
name: job-search
description: Set up and run your job search — the front door. Use for "set up job search", "start my job search", "find me jobs", "check my job search", "job search status", or /job-search. On first run it onboards you end-to-end (prereqs, workspace, preferences interview, queries + frequency, a first live search, and scheduling); afterward it shows your job-search home (latest digest, new matches, pipeline) with quick actions.
disable-model-invocation: false
user-invocable: true
---
```

Body:
- **What this is** — the OS shell / front door. Mental model: this skill is the login shell + home screen; `osctl.py` is OS state; `job-search-run` is the scheduled job; `job-preference-interview` builds the brief.
- **Step 0 — route.** Run `python3 "$OS" resolve` (bundled `scripts/osctl.py`; `$OS`/`$STATE` resolved from this skill's own dir, e.g. `${CLAUDE_SKILL_DIR}/scripts/...` when installed as a plugin). If `first_run` is true → follow `references/onboarding.md`. Else → follow `references/home.md`.
- **Principles** — configuration is conversational-first (apply changes by chatting; follow `references/internals.md` recipes); no numeric scores/weights; no credit math; every blocked path is a named `E-*` from `references/errors.md`. Read `references/conventions.md`, `references/internals.md`, `references/errors.md`, `references/agent-data-contract.md` and follow them exactly.

- [ ] **Step 2: Author `skills/job-search/references/onboarding.md`** (the first-run playbook). It MUST encode this flow, end to end, with named errors and the magical finish:

  1. **Welcome** — one or two lines on what's about to happen and that it ends with real matches in a few minutes.
  2. **Prereqs (free).** If `agent-data` is not on PATH → **E-NO-AGENT-DATA** (name the install fix; stop). Run `agent-data whoami`; if `api_key_set:false` → **E-NO-AUTH** (name the export fix; stop).
  3. **Workspace.** Run `$OS resolve`. If `source` is `legacy` (or you detect an existing workspace) → **adopt** it: tell the user, run `$OS set-active --workspace <path>`, ensure `runs/`+`reports/` exist, do NOT overwrite any existing file. Else default to `~/.job-search/`: confirm the location (offer an override), create `runs/`+`reports/`, copy `templates/config.example.yaml`→`config.yaml`, `templates/workspace.gitignore`→`.gitignore`, create empty `jobs.jsonl`, then `$OS set-active --workspace <path>`. Never clobber (see `internals.md`).
  4. **Preferences (interview-or-import fork).** Ask "Shall I interview you to build your preferences, or do you already have a brief to import?" Interview → invoke `job-preference-interview`. Import → validate prose + write `preferences.md` (per the interview skill's import rules).
  5. **Queries + frequency (conversational-first).** Ask for the role/keywords and location; write a `queries[]` entry in `config.yaml` (edit YAML per `internals.md`). Ask how often to pull with the plain-language nudge — "Daily suits most searches; choose hourly only if you're in a fast-moving, active search" — and set `schedule.frequency` (one of the allowed values). **No credit/cost math.**
  6. **First live sample run (the magical moment).** Disclose that this makes a few live calls, then invoke `job-search-run` against the workspace. Show the digest's strong/moderate matches: "Here are N jobs matching your brief, found seconds ago." (In evals this hits the fake shim.)
  7. **Scheduling (offer to set it up; consent + fallback).** Per `internals.md`: explain cron (default) / launchd (robust mac) / `/loop`; ask a yes/no. On yes, generate the artifact with `$OS schedule-line` (or `$OS launchd-plist`), perform the privileged write, then `$OS set-scheduled --mechanism <m>`. Always also print the verbatim copy-paste fallback (OPTION A/B block + macOS caveat). On no, print the fallback and only `set-scheduled` if the user confirms they did it.
  8. **Home.** Print the home view (hand off to `home.md`'s format). Done.

- [ ] **Step 3: Author `skills/job-search/references/home.md`** (the returning-user playbook):
  - Resolve the workspace (`$OS resolve`). Show a compact home:
    - **Status line:** workspace path · brief age (from `preferences.md` `created_at`; nudge if older than ~3 months) · schedule (from `$OS schedule-status`: on/off + mechanism) · last run health (newest `runs/*.json` `run_health`, or the latest digest's Run health line).
    - **Latest digest:** read the newest `reports/<date>-digest.md`; show its date and the counts line.
    - **Pipeline:** `python3 "$STATE" fold --jobs <ws>/jobs.jsonl` → counts by `status` (new/interested/applied/rejected/archived) and how many have `needs_human_check: true` to review.
    - **Quick actions (conversational):** run a search now (→ `job-search-run`) · add or edit a query · change how often it runs · update your preferences (→ `job-preference-interview`) · change or turn off the schedule · show the latest digest. Apply each by chatting (edit config per `internals.md`); never require the user to hand-edit files.
    - **Nudges:** stale brief; if the last run was blocked/failed, name the error + fix.
  - Resume actions (compare/tailor) are **coming soon (Plan C)** — mention but defer.

- [ ] **Step 4: Sync + sanity check** — `./scripts/build.sh` and confirm `skills/job-search/{SKILL.md,references/onboarding.md,references/home.md}` exist and the skill's `references/` got the synced shared docs + `internals.md`.

- [ ] **Step 5: Commit**

```bash
git add skills/job-search/ skills/
git commit -m "feat(skill): job-search orchestrator (shell) — onboarding + home playbooks"
```

### Task B8: `job-search` onboarding + home evals (fake shim, temp registry, zero credits) [skill-creator evals]

**Files:**
- Create: `skills/job-search/evals/files/setup-onboarding.sh`, `skills/job-search/evals/evals.json`

- [ ] **Step 1: Create `evals/files/setup-onboarding.sh`** (first-run isolation: a temp base + the shim; NO workspace, NO real registry):

```bash
#!/usr/bin/env bash
# Usage: setup-onboarding.sh <tmp>. Builds a FIRST-RUN sandbox: a _bin/agent-data shim symlink only.
# The eval exports JOBSEARCH_OS_REGISTRY=<tmp>/registry.json and JOBSEARCH_OS_HOME=<tmp> so the registry
# and the default/legacy workspaces live under <tmp> — real ~/.config, ~/.job-search, ~/job-search are
# never touched. Plus PATH=<tmp>/_bin:$PATH + JOBSEARCH_FIXTURES + JOBSEARCH_TEST_SCENARIO for the shim.
set -euo pipefail
DEST="$1"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
mkdir -p "$DEST/_bin"
ln -sf "$REPO/tests/fake-agent-data" "$DEST/_bin/agent-data"
echo "$DEST"
```

- [ ] **Step 2: Author `evals/evals.json`** with these cases (harness sets `PATH=<tmp>/_bin:$PATH`, `JOBSEARCH_FIXTURES=<repo>/tests/fixtures`, `JOBSEARCH_TEST_SCENARIO=happy`, `JOBSEARCH_OS_REGISTRY=<tmp>/registry.json`, `JOBSEARCH_OS_HOME=<tmp>`; canned answers in each prompt):

  - **id 1 — first-run happy path.** Canned: interview a few prefs; query keywords "AI engineer" / location "United States"; frequency "daily"; scheduling "yes, cron". Expectations:
    - Checks prereqs (`whoami`) before any `search-jobs` call.
    - Creates `<tmp>/.job-search/` with `config.yaml`, `preferences.md` (prose, no numbers), empty `jobs.jsonl`, `.gitignore`, `runs/`, `reports/`.
    - Writes the registry at `<tmp>/registry.json` with `active_workspace` = `<tmp>/.job-search`.
    - Runs a sample search and surfaces the Acme "Senior AI Engineer (Remote US)" strong match from the happy fixture ("found seconds ago").
    - Records the scheduling marker (`mechanism: cron`) AND prints the verbatim copy-paste fallback.
    - Prints the home view at the end.
    - Output has NO numeric score/weights and NO credit/dollar math.
  - **id 2 — first-run, import brief.** Canned: "I have a brief" + pasted prose; frequency "weekly"; scheduling "no". Expectations: no interview; `preferences.md` = the prose; onboarding still configures a query + frequency and does the sample run; prints the copy-paste fallback (no marker set, since user declined); no numbers.
  - **id 3 — first-run, not authenticated.** Also export `JOBSEARCH_TEST_NOAUTH=1`. Expectations: stops at prereqs with **E-NO-AUTH** naming the fix; creates NO workspace and writes NO registry; nothing pulled.
  - **id 4 — returning-user home.** Pre-seed before invoking: `setup-onboarding.sh <tmp>`; create `<tmp>/.job-search` from templates; append two `evaluated` events to its `jobs.jsonl` via `state.py` (one `status:new`, one `status:interested`); write a sample `reports/2026-06-05-digest.md`; `osctl.py set-active --registry <tmp>/registry.json --workspace <tmp>/.job-search`. Then invoke `/job-search`. Expectations: NO onboarding (no interview, no workspace creation); shows the status line + the latest digest summary + pipeline counts (1 new, 1 interested) + quick actions; no numbers.
  - **id 5 — never-clobber adoption of a legacy workspace.** Pre-seed a LEGACY workspace at `<tmp>/job-search` (because `JOBSEARCH_OS_HOME=<tmp>`) with sentinel content: `config.yaml` (valid `version: 1` + one query), `preferences.md` containing the exact string `SENTINEL-PREFS`, and `jobs.jsonl` with one event containing `SENTINEL-JOB`. Do NOT write a registry. Invoke `/job-search`. Expectations: adopts the legacy workspace (registry now points to `<tmp>/job-search`); `preferences.md` still contains `SENTINEL-PREFS` and `jobs.jsonl` still contains `SENTINEL-JOB` **byte-for-byte unchanged**; only missing `runs/`+`reports/` were created; shows the home (does NOT start a fresh interview).

- [ ] **Step 3: Run via skill-creator**, iterate `SKILL.md`/`onboarding.md`/`home.md` until all five pass. Zero real credits (the shim handles all `agent-data` calls; `osctl.py` writes only under `<tmp>`).

- [ ] **Step 4: Commit**

```bash
git add skills/job-search/evals/
git commit -m "test(skill): job-search onboarding + home evals (first-run, import, noauth, home, never-clobber)"
```

---

## Milestone B-IV — Wire existing skills to OS internals

### Task B9: `job-search-run` — resolve via osctl; E-NO-AGENT-DATA; stay headless [edit + eval]

**Files:**
- Modify: `skills/job-search-run/SKILL.md` (source is this path — it has no separate shared source), `skills/job-search-run/evals/evals.json`

- [ ] **Step 1: Edit the workspace-resolution paragraph** (currently lines 14–18). Replace the first sentence ("Workspace = the current directory unless `--workspace <path>` is given …") with:

```
Resolve the workspace with `python3 "$OS" resolve` (bundled `scripts/osctl.py`; registry → `~/.job-search/`
→ legacy `~/job-search/`) UNLESS `--workspace <path>` is given, which overrides. Resolve `$OS` (and `$STATE`)
from this skill's own directory (e.g. `${CLAUDE_SKILL_DIR}/scripts/...` as a plugin) — never assume cwd. This
run is HEADLESS: never prompt. If `resolve` reports `first_run` (no workspace/config yet) → **E-NO-CONFIG**
naming `/job-search` (HALT, exit 1); onboarding is interactive and lives in the `job-search` skill, not here.
```

- [ ] **Step 2: Add an E-NO-AGENT-DATA preflight line** as the first bullet of step `0. Preflight (free).`:

```
   - `agent-data` not found on PATH → E-NO-AGENT-DATA (HALT, exit 1).
```

- [ ] **Step 3: Update the eval harness** in `skills/job-search-run/evals/evals.json`: in the `harness` string, change "Then run /job-search-run against <tmp>" to "Then run /job-search-run --workspace <tmp> (the override path, so discovery is bypassed in these workspace-provided cases)". Append one new eval:

```json
    {
      "id": 11,
      "scenario": "first-run, no workspace (headless)",
      "prompt": "Do NOT create a workspace. Export JOBSEARCH_OS_REGISTRY=<tmp>/absent.json and JOBSEARCH_OS_HOME=<tmp> (empty), PATH=<tmp>/_bin:$PATH with the shim, JOBSEARCH_TEST_SCENARIO=happy. Run /job-search-run with NO --workspace.",
      "expectations": [
        "resolve reports first_run → E-NO-CONFIG naming /job-search; does NOT prompt (headless)",
        "Makes no search-jobs/get-posting calls",
        "Exits non-zero"
      ]
    }
```

- [ ] **Step 4: Sync + run the run-skill evals** via skill-creator (all 11 pass, zero credits). `./scripts/build.sh` first so the bundled `osctl.py` is present.

- [ ] **Step 5: Commit**

```bash
git add skills/job-search-run/ skills/
git commit -m "feat(skill): job-search-run resolves workspace via osctl (registry→default→legacy); E-NO-CONFIG on first-run; headless"
```

### Task B10: `evaluate-job-fit` — resolve workspace via osctl [edit]

**Files:**
- Modify: `skills/evaluate-job-fit/SKILL.md`

- [ ] **Step 1: Edit the first Inputs bullet** (line 13). Replace with:

```
- The brief: resolve the active workspace with `python3 "$OS" resolve` (bundled `scripts/osctl.py`) and read
  its `config.yaml:workspace.preferences_path` (default `preferences.md`); `--workspace <path>` overrides. If a
  posting is supplied without a workspace (resolve reports `first_run`), accept a brief pasted by the user.
```

- [ ] **Step 2: Sync + sanity check** — `./scripts/build.sh`; confirm the existing evaluate-job-fit evals (paste brief + posting) still pass via skill-creator (no behavior change to the pasted-brief path).

- [ ] **Step 3: Commit**

```bash
git add skills/evaluate-job-fit/SKILL.md skills/
git commit -m "feat(skill): evaluate-job-fit resolves workspace via osctl (fallback to pasted brief)"
```

### Task B11: Full green + Plan B self-review [verify]

- [ ] **Step 1: Build + full unit suite** — `cd ~/job-search-os && ./scripts/build.sh && python3 -m pytest -q`. Expected: all green (state + osctl + fake-agent-data; ≥18 + new osctl tests).
- [ ] **Step 2: Run every skill's evals** via skill-creator: `evaluate-job-fit`, `job-search-run` (11), `job-preference-interview` (3), `job-search` (5). All pass, zero real credits.
- [ ] **Step 3: Grep guard for philosophy** — confirm no numeric scoring leaked into authored skills/docs:

```bash
grep -rniE "0[-–]100|score|weight|budget|credits?|\\$[0-9]" skills/*/SKILL.md skills/job-search/references shared/references/internals.md | grep -viE "no (numeric )?score|never a number|no .*weights|no credit|reactive|E-QUOTA|salary_display" || echo "clean"
```
Expected: `clean` (any hit must be a negation/explanation, not an actual score/weight/budget knob).

- [ ] **Step 4: Commit any fixes; push the branch is deferred** until Plan D + user sign-off.

---

## Self-Review (run after writing; fix inline)

**Spec coverage (handoff §4 + spec-delta):** orchestrator (B7/B8) ✓; prose interview dropping the rubric (B5/B6) ✓; OS internals = osctl.py + internals.md (B1–B4) ✓; scheduling with consent + marker + fallback (B2/B3/B4 + B7) ✓; existing skills auto-discover the workspace (B9/B10) ✓; first-run vs returning detection (B1 resolve + B7 routing) ✓; never-clobber adoption (B1 + B8 id5) ✓; named errors incl. new E-NO-AGENT-DATA (B4) ✓; acceptance criteria covered by B8 + B11.

**Placeholder scan:** osctl.py + tests are complete code; SKILL.md tasks give exact frontmatter + section contracts + the verbatim scheduling copy + complete eval expectation lists (the skill prose is authored via skill-creator against those evals — the standard Plan A approach). No TBD/TODO.

**Type/name consistency:** script is `osctl.py` everywhere (never `os.py`); subcommands `resolve | set-active | schedule-line | launchd-plist | schedule-status | set-scheduled` match across tasks, internals.md, and the skills; registry keys `version | active_workspace | scheduling{installed,mechanism,set_at}` match osctl.py, tests, internals.md, and the spec-delta; env overrides `JOBSEARCH_OS_REGISTRY` / `JOBSEARCH_OS_HOME` match across osctl.py, internals.md, and the eval setup scripts; default workspace `~/.job-search/` and legacy `~/job-search/` consistent throughout.
