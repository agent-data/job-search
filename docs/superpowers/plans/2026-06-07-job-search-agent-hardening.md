# Job Search Agent — Hardening & Self-Knowledge Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three real gaps the live DX audit found and ship a canonical self-knowledge skill, so the Job Search Agent (1) can never silently install a non-default scheduled task, (2) surfaces every headless failure on next interactive open, (3) enforces its "qualitative-by-default" philosophy in CI while honoring explicit user requests, and (4) has one operator manual Claude Code reaches for to configure/use/extend/troubleshoot it.

**Architecture:** Four independently-shippable workstreams against the existing plugin at `~/job-search-os`:
- **A — Consent hook:** a stdlib `PreToolUse` guard that **asks** before a default (cron) schedule write, **asks** before a user-chosen non-default (launchd), and **denies** a non-default the model reached for on its own. "Who chose" comes from a short-lived intent marker written by a new deterministic `osctl set-sched-intent` command.
- **B — Failure surfacing:** make every HALT write a `runs/<id>.json` blocked record (the source the home view reads) and correct the docs that over-promise a non-zero process exit.
- **C — Philosophy guard:** a real CI grep-guard over shipped artifacts (making CONTRIBUTING's claim true) plus a `TESTING.md` fix so explicit on-request scores are honored, not failed.
- **D — `job-search-agent` skill:** a hub/operator-manual skill (modeled on the Hermes skill) that documents capabilities, config recipes, the customization workflows (incl. how to honor a score request without polluting the clean data), scheduling+consent, and troubleshooting — pointing to `shared/references/` as the source of truth (DRY).

**Tech Stack:** Python 3.9+ (stdlib only, matching the project), pytest, Claude Code plugin skills (Markdown `SKILL.md` + `references/*.md`), Claude Code hooks (`PreToolUse`), GitHub Actions, the fake-`agent-data` shim for credit-free evals.

**Conventions inherited from the repo (do not regress):**
- Single source of truth: edit `shared/references/*.md` and `scripts/*`, then run `./scripts/build.sh` to re-sync each skill's bundled copies. Never hand-edit `skills/*/references/` or `skills/*/scripts/`.
- Qualitative-by-default (no 0–100 score / weight / per-criterion points / budget knob in **default** output), frequency-not-budget, private-local, every blocked path is a named `E-*`.
- `version: 1` in `config.yaml` is never bumped by a feature; no budget/score fields ever added to config.
- Commit style: `feat(scope): …`, `fix(scope): …`, `test(scope): …`, `docs(scope): …`.

**Execution order:** A → B → C → D. Each group is independently committable and shippable; D is last because it documents the real, final behavior of A/B/C. Run `cd ~/job-search-os && python3 -m pytest -q` after each code task; it must stay green (baseline: `47 passed`).

---

## File Structure

**Workstream A — Consent hook**
- Create `hooks/guard-scheduled-tasks.py` — PreToolUse guard; pure `decide()` + thin stdin wrapper.
- Modify `scripts/osctl.py` — add `set-sched-intent`, `clear-sched-intent`, `set-unscheduled` subcommands (deterministic marker + resolve TODO-SCHED-OFF).
- Create `tests/test_guard_scheduled_tasks.py` — unit tests for `decide()`.
- Modify `tests/test_osctl.py` — tests for the three new subcommands.
- Create `.claude/settings.json` — register the hook (repo-local).
- Modify `shared/references/internals.md` — document the "write intent marker, then install" scheduling workflow + the hook contract.
- Modify `skills/job-search/references/onboarding.md` and `skills/job-search/references/home.md` — scheduling step calls `set-sched-intent` before any privileged write; turn-off calls `set-unscheduled`.

**Workstream B — Failure surfacing**
- Modify `skills/job-search-run/SKILL.md` — every HALT writes a `runs/<id>.json` blocked record (+ blocked digest when a workspace exists); correct the exit-code section.
- Modify `shared/references/errors.md` — reword surfacing ("next-session home + notification + blocked digest", not "exits non-zero").
- Modify `README.md` — same surfacing correction in Troubleshooting.
- Modify `skills/job-search-run/evals/evals.json` — HALT evals assert a `runs/*.json` blocked record exists.

**Workstream C — Philosophy guard**
- Create `scripts/philosophy_guard.py` — grep guard over shipped artifacts.
- Create `tests/test_philosophy_guard.py` — runs the guard, asserts clean.
- Create `.github/workflows/ci.yml` — pytest + guard on PRs.
- Modify `CONTRIBUTING.md` — point to the real guard.
- Modify `TESTING.md` — reframe T10.2 (explicit on-request scores are honored, not ❌; default/unsolicited must stay clean) and the exit-code assertions from B.

**Workstream D — job-search-agent skill**
- Create `skills/job-search-agent/SKILL.md` — the operator manual / hub.
- Create `skills/job-search-agent/references/customization.md` — flexibility workflows incl. score/cost-math requests.
- Create `skills/job-search-agent/references/scheduling-and-consent.md` — mechanisms + intent marker + hook behavior.
- Create `skills/job-search-agent/evals/evals.json` + eval files — lock in the customization/capabilities behaviors.
- Modify `skills/{job-search,job-search-run,job-preference-interview,evaluate-job-fit}/SKILL.md` — one-line pointer to `job-search-agent` for configure/extend/troubleshoot.
- Modify `README.md` — mention the operator-manual skill; `.claude-plugin/plugin.json` — bump `version` to `0.2.0`.
- Verify `scripts/build.sh` syncs shared refs/scripts into the new skill (it globs `skills/*`).

---

## Workstream A — Scheduling consent hook

**Why:** The audit found `"make it run hourly"` caused a real `launchctl load` of `dev.jobsearchos.run` with **no** yes/no consent. Model discipline is not enough; a `PreToolUse` hook makes it deterministic. Refinement (your call): **ask** when the user explicitly chose a non-default mechanism ("are you sure? default is cron"), **deny** when the model reached for a non-default on its own.

### Task A1: `osctl` intent + unschedule commands

**Files:**
- Modify: `scripts/osctl.py`
- Test: `tests/test_osctl.py`

- [ ] **Step 1: Write failing tests** — add to `tests/test_osctl.py`:

```python
def test_set_sched_intent_writes_marker_next_to_registry(tmp_path):
    reg = tmp_path / "reg.json"
    r = run(["set-sched-intent", "--choice", "launchd", "--registry", str(reg)])
    assert r.returncode == 0
    marker = tmp_path / ".sched-intent.json"
    assert marker.exists()
    data = json.loads(marker.read_text())
    assert data["choice"] == "launchd"
    assert isinstance(data["set_at_epoch"], int)

def test_set_sched_intent_rejects_unknown_choice(tmp_path):
    reg = tmp_path / "reg.json"
    r = run(["set-sched-intent", "--choice", "telepathy", "--registry", str(reg)])
    assert r.returncode != 0
    assert "Traceback" not in r.stderr

def test_clear_sched_intent_removes_marker(tmp_path):
    reg = tmp_path / "reg.json"
    run(["set-sched-intent", "--choice", "cron", "--registry", str(reg)])
    r = run(["clear-sched-intent", "--registry", str(reg)])
    assert r.returncode == 0
    assert not (tmp_path / ".sched-intent.json").exists()

def test_set_unscheduled_clears_installed_and_preserves_active(tmp_path):
    reg = tmp_path / "reg.json"
    run(["set-active", "--workspace", str(tmp_path / "ws"), "--registry", str(reg)])
    run(["set-scheduled", "--mechanism", "cron", "--registry", str(reg)])
    r = run(["set-unscheduled", "--registry", str(reg)])
    assert r.returncode == 0
    status = json.loads(run(["schedule-status", "--registry", str(reg)]).stdout)
    assert status["installed"] is False and status["mechanism"] is None
    reg_data = json.loads(reg.read_text())
    assert reg_data["active_workspace"].endswith("/ws")  # untouched
```

- [ ] **Step 2: Run the new tests, verify they fail**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_osctl.py -k "sched_intent or unscheduled" -q`
Expected: FAIL (`invalid choice: 'set-sched-intent'` / commands not defined).

- [ ] **Step 3: Implement the commands in `scripts/osctl.py`**

Add `import time` to the existing top-of-file import line (`import argparse, html, json, os, sys` → add `time`). Add a helper + three command functions:

```python
SCHED_CHOICES = ("cron", "launchd", "loop")


def _intent_path(registry_override=None):
    d = os.path.dirname(registry_path(registry_override)) or "."
    return os.path.join(d, ".sched-intent.json")


def cmd_set_sched_intent(args):
    if args.choice not in SCHED_CHOICES:
        print(f"set-sched-intent failed: unknown choice {args.choice!r} "
              f"({'|'.join(SCHED_CHOICES)})", file=sys.stderr)
        return 1
    path = _intent_path(args.registry)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"choice": args.choice, "set_at_epoch": int(time.time()),
                   "set_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}, f)
        f.write("\n")
    print(json.dumps({"choice": args.choice}))
    return 0


def cmd_clear_sched_intent(args):
    try:
        os.remove(_intent_path(args.registry))
    except FileNotFoundError:
        pass
    print(json.dumps({"cleared": True}))
    return 0


def cmd_set_unscheduled(args):
    try:
        path = registry_path(args.registry)
        reg = read_registry(path) or {"version": REGISTRY_VERSION}
        reg["version"] = REGISTRY_VERSION
        reg["scheduling"] = {"installed": False, "mechanism": None, "set_at": None}
        write_registry(path, reg)
        print(json.dumps(reg["scheduling"]))
    except ValueError as e:
        print(f"set-unscheduled failed: {e}", file=sys.stderr)
        return 1
    return 0
```

In `main()`, register the parsers next to the other scheduling subcommands:

```python
    si = sub.add_parser("set-sched-intent", help="record the user's chosen schedule mechanism (for the consent hook)")
    si.add_argument("--choice", required=True, help="cron|launchd|loop")
    si.add_argument("--registry")
    si.set_defaults(func=cmd_set_sched_intent)

    ci = sub.add_parser("clear-sched-intent", help="remove the schedule-intent marker")
    ci.add_argument("--registry")
    ci.set_defaults(func=cmd_clear_sched_intent)

    su = sub.add_parser("set-unscheduled", help="clear the scheduling marker (turn-off)")
    su.add_argument("--registry")
    su.set_defaults(func=cmd_set_unscheduled)
```

- [ ] **Step 4: Run the tests, verify they pass**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_osctl.py -q`
Expected: PASS (existing 18 + 4 new).

- [ ] **Step 5: Re-sync bundled copies and commit**

Run: `cd ~/job-search-os && ./scripts/build.sh && python3 -m pytest -q`
Expected: build prints the sync line; `51 passed`.

```bash
git add scripts/osctl.py tests/test_osctl.py skills/*/scripts/osctl.py
git commit -m "feat(osctl): add set-sched-intent/clear-sched-intent/set-unscheduled"
```

### Task A2: the PreToolUse guard (`decide()` + wrapper)

**Files:**
- Create: `hooks/guard-scheduled-tasks.py`
- Test: `tests/test_guard_scheduled_tasks.py`

- [ ] **Step 1: Write failing tests** — create `tests/test_guard_scheduled_tasks.py`:

```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_guard_scheduled_tasks.py -q`
Expected: FAIL (file `hooks/guard-scheduled-tasks.py` does not exist).

- [ ] **Step 3: Implement `hooks/guard-scheduled-tasks.py`**

```python
#!/usr/bin/env python3
"""PreToolUse guard for the Job Search Agent — deterministic scheduling consent.

  default mechanism (cron)               -> ASK  (confirm the privileged write)
  non-default (launchd) the USER chose   -> ASK  ("are you sure? the default is cron")
  non-default (launchd) the MODEL chose  -> DENY (default is cron / use /loop)
  reads, line-generation, /loop, normal  -> defer (no decision)

"Who chose" is read from a short-lived marker the scheduling workflow writes via
`osctl.py set-sched-intent --choice <mechanism>` right before installing. No fresh
marker => the model reached for it unprompted. Stdlib only; self-contained.
"""
import json, os, re, sys, time

DEFAULT_MECHANISM = "cron"
MARKER_TTL_SECONDS = 300

LAUNCHD = re.compile(
    r"launchctl\s+(load|bootstrap|enable|submit|unload|bootout|remove)"
    r"|(?:>|>>|\bcp\b|\bmv\b|\btee\b|\binstall\b)[^\n]*Launch(Agents|Daemons)",
    re.IGNORECASE)
CRON = re.compile(r"crontab(?!\s+-l\b)|/etc/cron", re.IGNORECASE)


def _registry_dir():
    reg = os.environ.get("JOBSEARCH_OS_REGISTRY")
    if reg:
        return os.path.dirname(reg) or "."
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.environ.get("JOBSEARCH_OS_HOME") or os.path.expanduser("~"), ".config")
    return os.path.join(xdg, "job-search-os")


def _explicit_choice():
    """Return the user's freshly-recorded mechanism choice, or None."""
    try:
        with open(os.path.join(_registry_dir(), ".sched-intent.json"), encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - float(data.get("set_at_epoch", 0)) > MARKER_TTL_SECONDS:
            return None
        return data.get("choice")
    except Exception:
        return None


def decide(cmd):
    """Pure decision: returns (decision, reason) or None to defer."""
    is_launchd, is_cron = bool(LAUNCHD.search(cmd)), bool(CRON.search(cmd))
    if not (is_launchd or is_cron):
        return None
    if is_launchd:
        if _explicit_choice() == "launchd":
            return ("ask", "You're installing a launchd agent, which is NOT the default "
                           "(cron is). Confirm you want launchd specifically.")
        return ("deny", "Do not install a launchd agent here. The Job Search Agent's "
                        "default scheduler is cron, and /loop needs no privileged write. "
                        "Use cron, or have the user explicitly confirm launchd first.")
    return ("ask", "This installs a cron schedule for the Job Search Agent. Confirm the "
                   "privileged write to your crontab.")


def main():
    try:
        evt = json.load(sys.stdin)
    except Exception:
        return 0
    d = decide(((evt.get("tool_input") or {}).get("command") or ""))
    if d:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": d[0],
            "permissionDecisionReason": d[1]}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_guard_scheduled_tasks.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Smoke-test the stdin wrapper end-to-end**

Run:
```bash
cd ~/job-search-os
echo '{"tool_name":"Bash","tool_input":{"command":"launchctl load ~/Library/LaunchAgents/x.plist"}}' \
  | python3 hooks/guard-scheduled-tasks.py
```
Expected: a JSON line with `"permissionDecision": "deny"` (no marker present).

- [ ] **Step 6: Commit**

```bash
git add hooks/guard-scheduled-tasks.py tests/test_guard_scheduled_tasks.py
git commit -m "feat(hooks): PreToolUse guard for scheduling consent (ask/deny)"
```

### Task A3: register the hook + verify plugin packaging

**Files:**
- Create: `.claude/settings.json`
- Verify: plugin-bundled hooks path

- [ ] **Step 1: Create `.claude/settings.json`** (repo-local enforcement, works today):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PROJECT_DIR}/hooks/guard-scheduled-tasks.py\"",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Verify the hook fires in a real session**

Run (from the repo, interactive or `-p`): ask Claude to `launchctl load ~/Library/LaunchAgents/test.plist`.
Expected: Claude is denied with the guard's reason (no marker). Then run `python3 scripts/osctl.py set-sched-intent --choice launchd` and retry → Claude is **asked** (prompted), not denied.

- [ ] **Step 3: Resolve plugin-bundled-hooks packaging (the one open question)**

The `.claude/settings.json` above protects *this checkout*; it does **not** ship to users who `/plugin install`. Determine the current plugin-hooks mechanism (consult the Claude Code plugin docs / `claude-code-guide`) and wire the same hook so it ships with the plugin (the script already lives inside the plugin at `hooks/`). Document the chosen mechanism in `skills/job-search-agent/references/scheduling-and-consent.md` (Task D3). Note in that file that **loose-skills installs do not get plugin hooks** — those users add the `.claude/settings.json` snippet manually.

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.json
git commit -m "feat(hooks): register scheduling-consent guard (PreToolUse/Bash)"
```

### Task A4: wire the workflow to write the marker

**Files:**
- Modify: `shared/references/internals.md`
- Modify: `skills/job-search/references/onboarding.md` (§7 scheduling)
- Modify: `skills/job-search/references/home.md` (schedule change + turn-off)

- [ ] **Step 1: Document the consent workflow in `internals.md`**

In the scheduling section, add (verbatim) the proven order and the hook contract:

```markdown
### Scheduling: record intent, then install (consent-guarded)

Scheduling installs are guarded by a PreToolUse hook (`hooks/guard-scheduled-tasks.py`).
Before any privileged write (a `crontab` line or a launchd plist), follow this order:

1. The DEFAULT mechanism is **cron**. Prefer it unless the user explicitly asks for
   launchd or /loop.
2. Record the user's explicit choice so the guard can tell intent from improvisation:
   `python3 "$OS" set-sched-intent --choice <cron|launchd|loop>` — run this ONLY after
   the user has explicitly chosen that mechanism.
3. Perform the install. The guard will **ask** (cron, or a user-chosen launchd) or
   **deny** (a launchd the user did not choose — reach for cron or /loop instead).
4. On success record it: `python3 "$OS" set-scheduled --mechanism <m>`, then clear the
   intent: `python3 "$OS" clear-sched-intent`.
5. To turn scheduling off: remove the OS artifact, then
   `python3 "$OS" set-unscheduled` (clears the marker — no more stale `installed: true`).

Never set `set-sched-intent` for a mechanism the user did not name. /loop performs no
privileged write and is never gated.
```

- [ ] **Step 2: Update `onboarding.md` §7** — in the "On yes" steps, insert before the privileged write: *"If the user chose launchd or /loop specifically, first run `python3 "$OS" set-sched-intent --choice <mechanism>` (records consent for the guard)."* and after recording: *"then `python3 "$OS" clear-sched-intent`."*

- [ ] **Step 3: Update `home.md`** — in "Change or turn off the schedule", replace the turn-off line with: *"remove the crontab line or `launchctl unload` + delete the plist, then `python3 "$OS" set-unscheduled` so `schedule-status` reads `installed: false`, and tell the user it's off."*

- [ ] **Step 4: Re-sync and commit**

Run: `cd ~/job-search-os && ./scripts/build.sh && git status --short`
Expected: `internals.md` synced into all skills; no other unexpected diffs.

```bash
git add shared/references/internals.md skills/*/references/internals.md \
        skills/job-search/references/onboarding.md skills/job-search/references/home.md
git commit -m "docs(scheduling): record-intent-then-install workflow + turn-off clears marker"
```

---

## Workstream B — Headless failure surfacing

**Why:** The audit proved blocked `claude -p "/job-search-run"` runs exit **0** (the model can't set the host process exit code), contradicting the README/SKILL "exits non-zero" promise. The real, verified surfacing for an interactive-first user is the **home view**, which reads `run_health` from the newest `runs/<id>.json`. Gap: the three preflight HALTs (E-NO-CONFIG, E-NO-PREFERENCES, E-CONFIG-VERSION) write neither a digest nor a `runs/` record, so they'd show "Last run: none." Fix = make every HALT write the `runs/` record; correct the docs.

### Task B1: HALT paths write a blocked `runs/` record

**Files:**
- Modify: `skills/job-search-run/SKILL.md`

- [ ] **Step 1: Strengthen the "Run health & exit codes" section.** Replace it with:

```markdown
## Run health, surfacing & exit codes
Every run ends by writing `runs/<run_id>.json` with at least `{"run_id","run_health",
"error"|null,"ts"}`. **Every HALT path writes this record with `run_health:"blocked"` and
its `E-*` BEFORE stopping** — this is the source the home view reads, so a failed scheduled
run is named on the user's next `/job-search`. When a workspace exists, a HALT also writes
the blocked `reports/<date>-digest.md` (named error + fix as the body). If
`notify.desktop_notify_on_block` is true, fire one desktop notification on a blocked run.

Surfacing is the home view + the blocked digest + the desktop notification — NOT the
process exit code. A headless `claude -p` run returns 0 even when blocked (a skill cannot
set the host exit code); do not rely on it, and do not tell the user a cron job's `$?`
will be non-zero.

Exception: **E-NO-CONFIG / first_run** means there is no workspace to write into — this is
inherently visible because the next `/job-search` routes to onboarding. Name the error and
stop.
```

- [ ] **Step 2: Add an explicit instruction at each HALT.** In the Loop's Preflight bullets and the E-QUOTA/E-SERVICE-DOWN branches, ensure each says "write the `runs/<id>.json` blocked record (and blocked digest if a workspace exists) before exiting." Add one sentence to the preflight intro:

```markdown
> Before exiting on ANY E-* HALT where a workspace exists (E-NO-AUTH, E-NO-PREFERENCES,
> E-CONFIG-VERSION, E-SERVICE-DOWN, E-QUOTA), write `runs/<run_id>.json` with
> `run_health:"blocked"` + the error, so the next home view surfaces it.
```

- [ ] **Step 3: Commit**

```bash
git add skills/job-search-run/SKILL.md
git commit -m "fix(run): every HALT writes a blocked runs/ record so home surfaces it"
```

### Task B2: correct the surfacing wording in shared docs + README

**Files:**
- Modify: `shared/references/errors.md`
- Modify: `README.md`

- [ ] **Step 1: `errors.md`** — replace the opening "Headless runs that are BLOCKED exit non-zero so a cron log/desktop notify shows it." with:

```markdown
Blocked runs surface three ways — the **blocked digest** (named error as the body), a
**desktop notification** (`notify.desktop_notify_on_block`), and the **home view** on the
user's next `/job-search` (which reads `run_health` from the newest `runs/<id>.json`).
Do not rely on the process exit code: a headless `claude -p` run returns 0 even when
blocked. Every HALT therefore writes a `runs/<id>.json` blocked record.
```

- [ ] **Step 2: `README.md` Troubleshooting** — replace "Blocked headless runs exit non-zero so a cron log or desktop notification surfaces them, and every named error tells you the fix." with:

```markdown
Blocked runs never fail silently: each writes a **blocked digest** (the named error + its
fix as the body), fires a **desktop notification**, and is named in your **home view** the
next time you run `/job-search`. (A headless `claude -p` run itself exits 0 even when
blocked — the surfacing is the digest/notification/home, not the shell exit code.)
```

- [ ] **Step 3: Re-sync and commit**

Run: `cd ~/job-search-os && ./scripts/build.sh`

```bash
git add shared/references/errors.md skills/*/references/errors.md README.md
git commit -m "docs(errors): describe real blocked-run surfacing (home/digest/notify, not exit code)"
```

### Task B3: evals assert the blocked `runs/` record

**Files:**
- Modify: `skills/job-search-run/evals/evals.json`

- [ ] **Step 1: For the `quota`, `down`, `no-preferences`, and `config-version` evals, add an expected-outcome assertion** that after the run a `runs/*.json` exists whose `run_health` is `blocked` and whose `error` names the matching `E-*`. Follow the existing assertion shape in that file (match the harness's `expect`/`checks` schema already used for digest assertions; mirror an existing eval's structure exactly).

- [ ] **Step 2: Run the job-search-run evals** (fake-shim, credit-free) and confirm green.

Run: in a Claude Code session at the repo, "run the evals for job-search-run".
Expected: all pass, including the new blocked-`runs/` assertions.

- [ ] **Step 3: Commit**

```bash
git add skills/job-search-run/evals/evals.json
git commit -m "test(run): assert HALT paths write a blocked runs/ record"
```

---

## Workstream C — Philosophy guard (CI) + test-spec fix

**Why:** (1) CONTRIBUTING claims the philosophy is "enforced by a grep guard in CI" but there is no CI. (2) `TESTING.md` T10.2 currently fails the model for producing a score **even when the user explicitly asked** — which contradicts the flexibility goal. Fix both: a real guard over *shipped artifacts* (defaults), and a test that only polices *default/unsolicited* output.

### Task C1: the philosophy guard script

**Files:**
- Create: `scripts/philosophy_guard.py`
- Test: `tests/test_philosophy_guard.py`

- [ ] **Step 1: Write the failing test** — create `tests/test_philosophy_guard.py`:

```python
import subprocess, sys, pathlib, tempfile, os
ROOT = pathlib.Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "philosophy_guard.py"

def run_guard(target):
    return subprocess.run([sys.executable, str(GUARD), "--root", str(target)],
                          capture_output=True, text=True)

def test_repo_is_clean():
    r = run_guard(ROOT)
    assert r.returncode == 0, r.stdout + r.stderr

def test_flags_a_fit_score_in_an_example(tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "bad.md").write_text("Fit score: 87/100\n")
    r = run_guard(tmp_path)
    assert r.returncode == 1
    assert "bad.md" in r.stdout

def test_allows_salary_display_and_equota(tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "ok.md").write_text(
        "- Senior Engineer — Acme — $180K–$220K\nE-QUOTA: API limit reached.\n")
    r = run_guard(tmp_path)
    assert r.returncode == 0, r.stdout
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_philosophy_guard.py -q`
Expected: FAIL (guard script missing).

- [ ] **Step 3: Implement `scripts/philosophy_guard.py`**

```python
#!/usr/bin/env python3
"""Philosophy guard: fail if SHIPPED default-output artifacts contain a numeric fit score,
category weight, per-criterion points, or a budget/credit knob. Honored-on-request scores
live only in chat, never in committed artifacts — so this scans what we ship, not what a
user might ask for.

Scanned: examples/, templates/. Skipped: prose that DEFINES the philosophy (it names the
forbidden things to forbid them) and the source data field salary_display.
"""
import argparse, os, re, sys

SCAN_DIRS = ("examples", "templates")
# forbidden in shipped default output:
PATTERNS = [
    (re.compile(r"\bfit score\b", re.I), "fit score"),
    (re.compile(r"\b\d{1,3}\s*/\s*100\b"), "N/100 score"),
    (re.compile(r"\b0\s*[-–]\s*100\b"), "0-100 scale"),
    (re.compile(r"\bcategory weight", re.I), "category weight"),
    (re.compile(r"\b\d+\s*(points|pts)\b", re.I), "points"),
    (re.compile(r"\bbudget\b", re.I), "budget knob"),
    (re.compile(r"\bcredits?\b", re.I), "credit math"),
]
# allowed cost language is the reactive E-QUOTA note; salary_display is source data.
ALLOW_LINE = re.compile(r"E-QUOTA|salary|\$\s?\d", re.I)


def scan(root):
    hits = []
    for d in SCAN_DIRS:
        base = os.path.join(root, d)
        for dirpath, _, files in os.walk(base):
            for fn in files:
                if not fn.endswith((".md", ".yaml", ".yml")):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if ALLOW_LINE.search(line):
                            continue
                        for rx, label in PATTERNS:
                            if rx.search(line):
                                hits.append(f"{os.path.relpath(path, root)}:{i}: {label}: {line.strip()}")
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    hits = scan(args.root)
    if hits:
        print("Philosophy guard FAILED — numeric score / budget language in shipped output:")
        print("\n".join(hits))
        return 1
    print("Philosophy guard: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_philosophy_guard.py -q`
Expected: PASS (3 tests). If `test_repo_is_clean` fails, the guard found a real issue in `examples/`/`templates/` — fix the artifact, not the guard.

- [ ] **Step 5: Commit**

```bash
git add scripts/philosophy_guard.py tests/test_philosophy_guard.py
git commit -m "feat(ci): philosophy guard over shipped default-output artifacts"
```

### Task C2: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: ci
on:
  push: { branches: [main] }
  pull_request: {}
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - name: Unit tests
        run: python3 -m pytest -q
      - name: Philosophy guard
        run: python3 scripts/philosophy_guard.py --root .
      - name: Build is a no-op (bundled copies in sync)
        run: |
          ./scripts/build.sh
          test -z "$(git status --porcelain skills)" \
            || { echo "build.sh changed bundled skill copies — commit the re-sync"; git --no-pager diff --stat skills; exit 1; }
```

- [ ] **Step 2: Validate the workflow YAML locally**

Run: `cd ~/job-search-os && python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml ok')"`
Expected: `yaml ok` (install `pyyaml` if needed: `python3 -m pip install --quiet pyyaml`).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run pytest + philosophy guard + build-sync check on PRs"
```

### Task C3: fix CONTRIBUTING + TESTING.md spec

**Files:**
- Modify: `CONTRIBUTING.md`
- Modify: `TESTING.md`

- [ ] **Step 1: `CONTRIBUTING.md`** — under "Project philosophy", change "enforced by a grep guard in CI and review" to a true statement and point at the script:

```markdown
These are enforced by `scripts/philosophy_guard.py` (run in CI via
`.github/workflows/ci.yml` and as `tests/test_philosophy_guard.py`) and in review. The
guard scans shipped default output (`examples/`, `templates/`). Note: a numeric score a
user *explicitly asks for* is fine in chat — it just must never be written into a digest,
brief, `config.yaml`, or `jobs.jsonl`.
```

- [ ] **Step 2: `TESTING.md` T10.2** — replace the expectation so explicit requests are honored:

```markdown
**Expected (read the transcript):** Default/unsolicited output stays band-only with no cost
math. The cost answer leads with **frequency** (and may explain that more queries × higher
limit × more often = more usage); it must not invent a per-call **dollar/credit** figure or
a budget knob. For the **explicit** "fit score out of 100" request, honoring it in the reply
is acceptable (the agent is flexible) **as long as** it (a) notes scoring is non-default and
qualitative bands are the real signal, and (b) does NOT persist the score into any
digest/brief/`config.yaml`/`jobs.jsonl`. A ❌ is: a numeric score or budget figure in
**unsolicited** output, OR an on-request score written into a saved artifact.
```

Update the grep guidance below it to grep the **saved files** for persisted scores (not the chat transcript) and to treat `salary_display`/`$`-amounts and reactive `E-QUOTA` wording as allowed.

- [ ] **Step 3: `TESTING.md` exit-code assertions (from Workstream B)** — in T5.3, T7.1, T7.4, T7.11, and the §"Acceptance checklist", replace each "non-zero exit" assertion with: *"writes a `runs/<id>.json` with `run_health: blocked` naming the `E-*`; the next `/job-search` home view surfaces it (the `claude -p` process itself returns 0 — do not assert on `$?`)."* Add one new check to T4.8's blocked-state: *"a seeded `runs/…blocked` record is named in home with its fix (verified)."*

- [ ] **Step 4: Commit**

```bash
git add CONTRIBUTING.md TESTING.md
git commit -m "docs(testing): philosophy guard is real; honor explicit scores; surfacing not exit code"
```

---

## Workstream D — The `job-search-agent` skill (operator manual)

**Why:** You want one canonical doc Claude Code reaches for to **configure, set up, use, extend, or troubleshoot** the agent, or understand its capabilities — the home of "proven workflows," including how to honor a customization (e.g., a score request) consistently. Modeled on `references/hermes-agent/SKILL.md`: a hub `SKILL.md` that indexes capabilities + points to deeper references, DRY against `shared/references/`.

### Task D1: the hub `SKILL.md`

**Files:**
- Create: `skills/job-search-agent/SKILL.md`

- [ ] **Step 1: Write the frontmatter exactly** (triggers on the meta/self situations; distinct from the daily-use `job-search` front door):

```markdown
---
name: job-search-agent
description: The operator manual for the Job Search Agent — reach for this to CONFIGURE, set up, use, EXTEND, customize, or TROUBLESHOOT the agent itself, or to understand its features and capabilities. Use for "how does my job search agent work", "how do I change/add/customize …", "why did the run fail", "what can it do", or any change to how the agent behaves. (For daily use — onboarding, the home view, running a search — use job-search.)
disable-model-invocation: false
user-invocable: true
version: 0.1.0
metadata:
  tags: [job-search, configuration, customization, scheduling, troubleshooting, extension]
  homepage: https://github.com/agent-data/job-search-os
  related_skills: [job-search, job-search-run, job-preference-interview, evaluate-job-fit]
---
```

- [ ] **Step 2: Write the body, section by section** (Hermes shape; concise hub that points to `shared/references/` as source of truth). Include these sections with this content:

  - **# Job Search Agent** — one paragraph: what it is (Claude Code turned into a private, local-first job-search agent), and the load-bearing philosophy as a bullet list: qualitative-by-default (relevant + weak/moderate/strong + reasoning, *no score unless you ask*), frequency-not-budget, private-local (`~/.job-search/`, deny-all `.gitignore`), every blocked path is a named `E-*`, conversational-first config. End with: *"This skill is what you (Claude) reach for to configure, extend, or troubleshoot the agent — the playbooks and guardrails live here."*
  - **## The skills** — a table: `job-search` (front door: onboard/home/run-now), `job-search-run` (the headless scheduled pull), `job-preference-interview` (build/refine the prose brief — interactive only), `evaluate-job-fit` (judge one posting), `job-search-agent` (this manual). One line each on what + when.
  - **## Quick reference (deterministic core)** — the `osctl.py` subcommands (`resolve`, `set-active`, `schedule-line`, `launchd-plist`, `schedule-status`, `set-scheduled`, `set-unscheduled`, `set-sched-intent`, `clear-sched-intent`) and `state.py` (`known-ids`, `append`, `fold`), one line each. Note: *"never hard-code workspace paths — always `osctl resolve`."*
  - **## Configuring it (conversational)** — the recipes: add/edit/remove a query, change frequency, mark a job status, update preferences. Point to `references/internals.md` (synced) for the exact edit rules; restate the invariants: preserve `version: 1`, preserve comments, never add a budget/score field.
  - **## Customizing & extending it** — one-paragraph intro, then *"For the full flexibility workflows — including how to honor an explicit score or cost-math request without polluting the clean data — see `references/customization.md`."*
  - **## Scheduling** — the three mechanisms (cron default, launchd, /loop) one line each; then *"Scheduling is consent-guarded — see `references/scheduling-and-consent.md` for the record-intent-then-install workflow and the hook's ask/deny behavior."*
  - **## When something fails** — the run-health line states (`healthy | partial (N) | degraded (LinkedIn flaky) | blocked (action needed)`); how failures surface (blocked digest + desktop notification + the **home view** on next `/job-search`, which reads `runs/<id>.json`); pointer to `references/errors.md` for every `E-*` with cause+fix. A short symptom→fix table: "0 matches but real postings shown" → query↔brief mismatch (fix the query or the brief); "0 results" → broaden keywords; "Last run: blocked — E-QUOTA" → pull less often / upgrade; "schedule isn't firing" → `schedule-status`, the Mac must be awake (caffeinate/launchd); "stale brief nudge" → `/job-preference-interview`.
  - **## Where to find things** — a table mapping "looking for X" → command/file/skill (config → `osctl resolve` + `conventions.md`; errors → `errors.md`; the API contract → `agent-data-contract.md`; workspace layout → `conventions.md`; this manual → `job-search-agent`).
  - **## Extending & contributing** — single-source-of-truth + `./scripts/build.sh` rule; how to add a skill (folder + `SKILL.md` + evals; build syncs shared refs/scripts); evals are credit-free via the fake shim; the philosophy guard (`scripts/philosophy_guard.py`, CI); versioning + `E-CONFIG-VERSION`; pointer to `CONTRIBUTING.md`.

- [ ] **Step 3: Validate the plugin still loads + lists the new skill**

Run: `cd ~/job-search-os && claude plugin validate . --strict`
Expected: `Validation passed`.

- [ ] **Step 4: Commit**

```bash
git add skills/job-search-agent/SKILL.md
git commit -m "feat(skill): add job-search-agent operator-manual skill"
```

### Task D2: `references/customization.md` (the flexibility workflows)

**Files:**
- Create: `skills/job-search-agent/references/customization.md`

- [ ] **Step 1: Write the file.** It must contain these workflows with concrete guidance:

  - **Honoring an explicit score / cost-math request (the key one).** State the rule plainly:
    > Default output is qualitative (bands + reasoning) and has no scores or cost math. But the agent is yours and flexible — when a user *explicitly* asks for a 0–100 score, a ranking number, or per-call cost estimates, **honor it in your reply**. Two hard rules: (1) note once that scoring is non-default and that the bands+reasoning are the real signal (so it stays informed, not silently re-architected); (2) **never persist** the requested numbers into a digest, the brief, `config.yaml`, or `jobs.jsonl` — those stay band-only so the default experience and the CI philosophy guard remain clean. If the user wants the numbers saved, write them to a clearly-named side file (e.g. `reports/<date>-scored.md`), never the canonical event log.
  - **Adding a custom filter / query shape** — extend `config.yaml`'s `queries[]` (keywords/location/limit/enabled); for richer filtering, add it to the *brief* (a must-have/red flag) so `evaluate-job-fit` enforces it qualitatively, rather than inventing a numeric filter.
  - **Changing how postings are judged** — `evaluate-job-fit` is the rubric; adjust the brief's buckets (must-have vs strong vs nice-to-have) to shift importance — importance lives in the bucket, not in math.
  - **Adding a new capability/skill** — point to the Extending section of `SKILL.md` and `CONTRIBUTING.md`.

- [ ] **Step 2: Run the philosophy guard to ensure this file doesn't trip it**

Run: `cd ~/job-search-os && python3 scripts/philosophy_guard.py --root .`
Expected: `clean.` (the guard scans `examples/`/`templates/`, not `skills/`, but confirm no accidental scope creep).

- [ ] **Step 3: Commit**

```bash
git add skills/job-search-agent/references/customization.md
git commit -m "docs(job-search-agent): customization workflows incl. honoring score requests"
```

### Task D3: `references/scheduling-and-consent.md`

**Files:**
- Create: `skills/job-search-agent/references/scheduling-and-consent.md`

- [ ] **Step 1: Write the file** documenting: the three mechanisms (cron default / launchd / /loop) and when to pick each; the **record-intent-then-install** order from `internals.md` (`set-sched-intent` → install → `set-scheduled` → `clear-sched-intent`); the **hook contract** (cron → ask; user-chosen launchd → ask; model-chosen launchd → deny; /loop and reads → never gated); turn-off (`set-unscheduled`); and the packaging note from Task A3 (ships with the plugin via the plugin-hooks mechanism; loose-skills users add the `.claude/settings.json` snippet — include the snippet verbatim).

- [ ] **Step 2: Commit**

```bash
git add skills/job-search-agent/references/scheduling-and-consent.md
git commit -m "docs(job-search-agent): scheduling mechanisms, consent workflow, hook contract"
```

### Task D4: evals for the new skill

**Files:**
- Create: `skills/job-search-agent/evals/evals.json`
- Create: `skills/job-search-agent/evals/files/` fixtures as referenced

- [ ] **Step 1: Author 3 evals** (mirror the structure of `skills/evaluate-job-fit/evals/evals.json` exactly — same `harness`/setup shape, fake shim where a workspace is needed):
  1. **explicit-score-honored** — seed a workspace with a digest; user says "give each match a fit score out of 100." Expect: the reply provides scores AND notes scoring is non-default; assert **no** score was written into `jobs.jsonl`/the digest (fold the state, grep the digest).
  2. **how-to-customize** — user asks "how do I make it only show remote roles?" Expect: routes to the brief/query workflow (add a must-have / adjust the query), not a numeric filter; `version: 1` preserved.
  3. **capabilities** — user asks "what can my job search agent do?" Expect: a capabilities overview drawn from the skills map; no numbers/credits.

- [ ] **Step 2: Run the new evals**

Run: in a Claude Code session at the repo, "run the evals for job-search-agent".
Expected: all 3 pass; outputs philosophy-clean.

- [ ] **Step 3: Commit**

```bash
git add skills/job-search-agent/evals
git commit -m "test(job-search-agent): evals for score-honoring, customization, capabilities"
```

### Task D5: wire references from the other skills + ship

**Files:**
- Modify: `skills/{job-search,job-search-run,job-preference-interview,evaluate-job-fit}/SKILL.md`
- Modify: `README.md`, `.claude-plugin/plugin.json`
- Verify: `scripts/build.sh`

- [ ] **Step 1: Add a one-line pointer** near the top of each of the four existing `SKILL.md` files:

```markdown
> To configure, extend, customize, or troubleshoot the agent itself (or understand its
> capabilities), use the **job-search-agent** skill — the operator manual.
```

- [ ] **Step 2: Verify `build.sh` syncs the new skill.** It globs `skills/*`, so the new skill should receive `shared/references/*.md` + `scripts/{osctl,state}.py`.

Run: `cd ~/job-search-os && ./scripts/build.sh && ls skills/job-search-agent/scripts/osctl.py skills/job-search-agent/references/errors.md`
Expected: both paths exist; `git status` shows the new bundled copies only.

- [ ] **Step 3: README + version bump.** Add a short "Operator manual" line to `README.md` pointing at the `job-search-agent` skill. In `.claude-plugin/plugin.json`, bump `"version": "0.1.0"` → `"0.2.0"` (new user-visible skill, backward compatible — per CONTRIBUTING's minor-bump rule).

- [ ] **Step 4: Full green gate**

Run: `cd ~/job-search-os && python3 -m pytest -q && claude plugin validate . --strict && python3 scripts/philosophy_guard.py --root .`
Expected: `pytest` green (≈54+ passed), `Validation passed`, `Philosophy guard: clean.`

- [ ] **Step 5: Commit**

```bash
git add skills/*/SKILL.md README.md .claude-plugin/plugin.json skills/*/references skills/*/scripts
git commit -m "feat(job-search-agent): cross-link from skills, bundle, bump to 0.2.0"
```

---

## Self-Review

**Spec coverage (audit findings & your three points → task):**
- Finding #1 (exit-code) → **B1/B2/B3** (HALT writes `runs/` record; docs corrected; evals assert it) + the verified home-surfacing it relies on.
- Finding #2 (philosophy in chat) → reframed per your intent: **C3** (honor explicit; police only default), **D2** (the proven honor-without-persisting workflow), **D4 eval #1** (locks it in), **C1/C2** (guard the *shipped defaults*).
- Finding #3 (scheduling consent) → **A1–A4** (intent marker + ask/deny hook + workflow), with your ask-vs-deny refinement implemented exactly in `decide()`.
- "job search agent" framing + canonical self-knowledge skill → **D1–D5**.
- Minor #4 (time range) — *not in scope here; tracked separately in `TODOS.md`.* (Flag if you want it added.)
- Minor #5 (CI grep-guard claim) → **C1/C2/C3** (now true).
- `TODO-SCHED-OFF` (bonus) → **A1** `set-unscheduled` + **A4** turn-off wiring.

**Placeholder scan:** code tasks (A1, A2, C1, C2) carry complete, runnable code + tests. Doc/skill tasks (A4, B1–B2, C3, D1–D3) carry exact frontmatter and the load-bearing verbatim passages (the consent workflow, the surfacing wording, the score-honoring rule) rather than vague directives; section specs name exactly what each section contains. Remaining authoring (the prose *around* the verbatim passages) is bounded by the section-by-section spec + the Hermes template, which is the intended plan granularity for a documentation deliverable.

**Type/name consistency:** marker file `.sched-intent.json` with keys `choice` / `set_at_epoch`; `osctl set-sched-intent --choice {cron,launchd,loop}`, `clear-sched-intent`, `set-unscheduled`; hook `decide()` returns `(decision, reason)|None`; `MARKER_TTL_SECONDS`; env `JOBSEARCH_OS_REGISTRY` — all consistent across A1/A2/A4 and D3.

**Known unknown (made an explicit step, not a hidden gap):** plugin-bundled-hooks packaging (A3 Step 3) — the `.claude/settings.json` form is verified-working for the repo; shipping with the plugin requires confirming the current plugin-hooks mechanism before wiring.

---

## Execution Handoff

Plan complete and saved to `~/job-search-os/docs/superpowers/plans/2026-06-07-job-search-agent-hardening.md`.
