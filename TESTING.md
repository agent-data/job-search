# Job Search — Test Plan

A thorough, **Claude-Code-driven** acceptance test suite. The goal: prove every intended feature works,
end to end, with Claude Code as the primary tester. You mostly read instructions to Claude and confirm what
it reports; a few checks are pure shell or visual.

## How to use this doc

- **Driver legend:** 🤖 = give the instruction to Claude Code and let it run · 👤 = you run a shell command or eyeball output · ⚙️ = automated (pytest/CLI).
- **Platform:** written for **macOS** (BSD `stat -f`, `shasum`). Scheduling is **unattended-first** (advocated default: a wall-clock `cron`/`launchd` job; in-session `/loop` is the fallback), but this suite drives only the loop/decline path and writes no real crontab, so the only platform swap is the BSD-isms (`stat -f '%Sm'` → `stat -c '%y'`); `shasum -a 256` and `grep -E` work on both.
- **Live-first.** Tests use the real `agent-data` API (per the project's design and your call). The handful of
  error conditions you can't trigger on demand (quota, outage, stale links) use the bundled **fake-agent-data
  shim** — clearly marked.
- **Isolation is mandatory.** Every test runs in a throwaway sandbox. Your real `~/.job-search/`,
  `~/job-search/`, the OS registry, and your `crontab` are **never** touched. Setup §0.2 redirects everything
  under a temp dir via the `JOBSEARCH_OS_*` env vars.
- Mark each test ✅ / ❌ in the **Result** box. The final **Acceptance checklist** is your sign-off.
- Estimated time: **~75–90 min** for the full pass (the live first-run T2.1 and the §12 evals dominate). The **Smoke subset** — T0.3, T1.1, **T7.13**, T6.1, T7.1 — is a genuine **~10 min** mostly-offline confidence check; it skips the full live onboarding (run T2.1 in the full pass).

### Automated lanes vs. the manual residual

The terminal state (per the AAS-T-10 ruling) is **a structural gate + automated lanes + a shrinking, honestly-labeled manual residual** — not a manual cross-host ritual. What is now **automated** (⚙️, runs in `pytest` / a CLI, host-independent — no manual driving):

- **Scripted mechanics** — `tests/test_mechanics_scripts.py`: the deterministic state operations (jobs.jsonl append/fold, schedule-line composition, workspace discovery) that the skills call out to, unit-tested directly.
- **Hardened skill evals** — `python3 scripts/eval_harness.py --root .` validates every `skills/*/evals/evals.json` for structural coherence (contiguous ids, well-formed scenarios, a **discovery** scenario per skill for the four overlap pairs, **stochastic** scenarios carrying `reps ≥ 5` + a **no-guidance control** arm, and — on milestone/liveness scenarios — a **fixed-time fixture** (`fixed_time`: a deterministic reference clock with a valid ISO `now` and a `checks` subset of `milestone`/`liveness`) so those derivations never read the wall clock) and rejects the pinned pack-authored `gpt-5*` literal regression family. Legacy version-1 selectors may resolve through host tier roles; version-2 test and runtime setup injects an exact host-resolved identifier. Pack-authored fixtures and prose never hard-code that identifier. `tests/test_eval_harness.py` unit-tests the rep-aggregation (pass-rate + variance), the control-delta, the fixed-time-fixture validation, and the **unique run marker** enforcement — the off-CI artifact check (`scripts/eval_harness.py --check-artifacts`) accepts a per-run `run_marker` and, for any `run_marked` assertion, requires the artifact to carry it, so a stale artifact left in a reused workspace can never create a false pass.
- **Release integrity** — `scripts/check_release_integrity.py`: version-sync across the 6 manifests.

Verifying a host-specific action such as scheduling is now a **runtime config-time canary** check, replacing the deleted per-host **structural adapter validation**.

What stays a **labeled TRANSITIONAL residual** (👤/🤖, driven by hand): the **behavioral cross-host matrix** — actually running a skill end-to-end on each of the seven hosts that are **not installable on the CI runner** (Codex/Cursor/opencode/Gemini/Copilot/Droid/Pi), and the **N ≥ 5 stochastic eval reps** (the discovery/verdict/injection/merge scenarios run against the shim to record real pass-rate + variance + the control delta). These are the **off-CI live-harness step** — expected, not a gap: CI proves the scenarios are *well-formed*; the behavioral reps prove they *pass*, and shrink as hosts become installable. A green structural gate must never be read as a passed behavioral matrix. One further labeled residual sits **outside** the gate entirely: the **separately authorized live ATS contract smoke** (T14.1c), which needs explicit approval for billable/network calls and is recorded as `SKIPPED — authorization or network unavailable` whenever it does not run — never as passed.

---

## 0. Setup

### 0.1 Prerequisites — 👤
```bash
claude --version                 # ≥ 2.1.x
agent-data whoami                # api_key_set: true   (else: set AGENT_DATA_API_KEY and re-check)
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 status   # {"status":"ok"}  (free)
python3 --version                # ≥ 3.9 — DEV SUITE ONLY (§0.3 pytest + linters); the shipped skills need no Python
```
**Expected:** the first three succeed; `whoami` shows `api_key_set: true`; status is `ok`.
**Result:** ⬜

### 0.2 Create an isolated sandbox — 👤 (run once per test session)
```bash
export JSOS=~/job-search
export JSOS_TEST=$(mktemp -d)
export JOBSEARCH_OS_REGISTRY="$JSOS_TEST/registry.json"
export JOBSEARCH_OS_HOME="$JSOS_TEST"
echo "Sandbox: $JSOS_TEST"
```
Now the registry and the default (`$JSOS_TEST/.job-search`) + legacy (`$JSOS_TEST/job-search`) workspaces all
live under the temp dir.

**Isolation pre-flight — run before any destructive/live test (cheap insurance).** Prove the redirect is live so
nothing can reach your real data (this evaluates the same registry expression the skills' Discovery procedure
uses — `shared/references/internals.md`):
```bash
REG="${JOBSEARCH_OS_REGISTRY:-${XDG_CONFIG_HOME:-${JOBSEARCH_OS_HOME:-$HOME}/.config}/job-search/config.json}"
case "$REG" in "$JSOS_TEST"/*) echo "isolation OK → registry $REG" ;; *) echo "LEAK: registry $REG outside $JSOS_TEST" ;; esac
case "${JOBSEARCH_OS_HOME:-$HOME}" in "$JSOS_TEST") echo "isolation OK → workspaces under $JSOS_TEST" ;; *) echo "LEAK: workspace home outside sandbox" ;; esac
```
**Expected:** both lines print `isolation OK`. A `LEAK:` line means the env vars aren't set in this shell —
**stop and re-run the exports** before any test that writes or pulls.

**Launch Claude Code from this same shell** so the skills inherit the env:
```bash
claude --plugin-dir "$JSOS"
```
**Slash commands in this suite are namespaced.** `--plugin-dir` loads the skills as the `job-search`
plugin, and plugin skills are only invocable as `/job-search:<skill>` — bare `/job-search` is **not
registered** (it exists only for loose-skill installs into `~/.claude/skills/`); typing it interactively
errors with "Unknown command". Headless `claude -p` differs: an unknown slash string is passed through to
the model as plain text, which usually still works by model interpretation — but write the namespaced form
in `-p` commands anyway so the skill is invoked deterministically.
**Safety rules while testing:**
- When onboarding reaches **scheduling**, answer **"no"** — it'll just show the `/loop` recipe. (Starting a
  real `/loop` would keep re-running during your test.) Nothing is ever written to your machine; the dedicated
  scheduling test is §9.
- **Teardown** when done: `rm -rf "$JSOS_TEST"`. (Re-`export JSOS_TEST=$(mktemp -d)` + the two env vars for a
  fresh first-run.)

### 0.3 Regression baseline — ⚙️
```bash
cd "$JSOS" && python3 -m pytest -q
```
**Expected:** `617 passed` **and `0 failed`** — treat **`0 failed`** as the real gate (the exact count grows as
tests are added; bump this number when it does). Covers the doc linter, the philosophy guard, the release-integrity checks, the scripted-mechanics unit tests, the **eval-scenario validator +
harness math** (`test_eval_harness.py`), and the fake-shim self-tests (incl. the `bad-query` scenario behind
T7.12) — dev tooling only; the runtime state procedures are exercised by the live tests below and the skill evals.
**Result:** ⬜

### 0.4 Canonical test persona (use for every LIVE test) — 👤
The live tests (T2.1, T5.1, T6.1, T5.4) judge **real, current** postings, so results vary by tester and by what's
posted that day. To keep a green/red meaningful — a real signal, not "the market was quiet" — drive the live path
from one **canonical persona** instead of your personal job hunt:
```bash
cp "$JSOS/examples/sample-preferences.md" "$JSOS_TEST/canonical-brief.md"   # import this when asked for a brief
export JSOS_CANON_ROLE="software engineer"      # broad keywords → rarely empty
export JSOS_CANON_LOC="United States"           # large location → rarely empty
```
**Sparse-data fallback (apply to any LIVE test).** If a live search returns **0 results**: broaden the canonical
query once (drop the location); if still 0, re-run the *same assertion* against the fake-shim **`happy`** scenario
(§7 setup) and mark the live result **N/A — market-quiet**, not ❌. A bug looks different from an empty market: a
bug throws a named `E-*`, mis-shapes the digest, or crashes; a quiet market completes cleanly with 0 results and
offers to propose broader, complementary role families (T7.11). Only the former is a ❌.

> Prefer realism? You may swap in your own role/location as an **optional** variant — but grade the canonical run.

---

## 1. Packaging & load

### T1.1 Manifest validates — ⚙️
```bash
cd "$JSOS" && claude plugin validate . --strict
```
**Expected:** `Validation passed` (validates `marketplace.json` + the plugin).
**Result:** ⬜

### T1.2 Plugin loads — 👤
```bash
claude --plugin-dir "$JSOS" -p "reply with the single word LOADED and do nothing else"
```
**Expected:** `LOADED`, no error. (Confirms the plugin loads without invoking a skill.)
**Result:** ⬜

### T1.3 Single-home reference resolution — ⚙️
```bash
cd "$JSOS" && python3 -m pytest -q tests/test_reference_resolution.py
```
**Expected:** `0 failed` — the shared contracts live **once** under `shared/references/` and resolve in place
from each skill (skills point at `../../shared/references/<file>.md`); there are **no per-skill bundled copies**.
The build is stamp-only: `./scripts/build.sh` regenerates `shared/references/build-stamp.md` and nothing else.
**Result:** ⬜

### T1.4 Trigger resolves — 🤖
In a `claude --plugin-dir "$JSOS"` session, type `/job-` and check the completion menu; also try the natural
language "set up job search".
**Expected:** `job-search` (and the other skills) appear; `/job-search` resolves (or `/job-search:job-search`
if another plugin claims the bare name); the NL phrase triggers the orchestrator. *(Don't complete the run here —
that's T2.1.)*
**Result:** ⬜

---

## 2. First-run onboarding — the magical moment

### T2.1 Full first-run, end to end (LIVE) — 🤖 + 👤  ★ flagship test
**Setup:** fresh sandbox (§0.2), Claude launched from that shell. Confirm first-run (no registry, no
workspace candidates yet — Discovery will report `first_run:true, source:none`):
```bash
cat "$JOBSEARCH_OS_REGISTRY" 2>/dev/null              # no such file
ls "$JSOS_TEST/.job-search/config.yaml" "$JSOS_TEST/job-search/config.yaml" 2>/dev/null   # nothing
```
**Steps (🤖):** Start the TTFV clock, then say **"set up job search"** (or `/job-search:job-search`). Drive it from the
**canonical persona** (§0.4): when asked for preferences, either answer with `$JSOS_CANON_ROLE` in
`$JSOS_CANON_LOC`, or say *"I already have a brief"* and paste `$JSOS_TEST/canonical-brief.md`; accept the
suggested query; choose **daily**; at scheduling answer **"no, just show me the commands."**
```bash
date +%s > "$JSOS_TEST/.tthw_start"    # run this the moment you send the first message
```
**Expected:**
- Checks prereqs (runs `agent-data whoami`) before any search.
- Creates `$JSOS_TEST/.job-search/` with `config.yaml`, a prose `preferences.md`, empty `jobs.jsonl`,
  deny-all `.gitignore`, `runs/`, `reports/`.
- Writes the registry at `$JSOS_TEST/registry.json` → `active_workspace` = that workspace.
- Runs a **live** sample search and shows real postings judged relevant/weak/moderate/strong with
  reasoning. **No numeric scores, budget config, or invented actual charge;** an accurate
  calls-first usage line and clearly labeled equivalent are allowed. (0 results → apply the §0.4
  sparse-data fallback before calling this a ❌.)
- Prints the `/loop` scheduling recipe and the home view.
**Verify (👤):**
```bash
echo "TTFV: $(( $(date +%s) - $(cat "$JSOS_TEST/.tthw_start") )) s"   # target < ~300 s (5 min)
ls -R "$JSOS_TEST/.job-search"; cat "$JSOS_TEST/registry.json"; cat "$JSOS_TEST/.job-search/reports/"*.md
```
**Record:** TTFV = ____ s · matches shown = ____ · anything confusing? ____
**Result:** ⬜

---

## 3. Preferences interview

### T3.1 Standalone interview → prose brief — 🤖
Fresh sandbox. Tell Claude: **"/job-search:job-preference-interview"** (or "build my job preferences
brief") and answer ~6–8 questions.
**Expected:** asks **one question at a time**; writes `$JSOS_TEST/.job-search/preferences.md` with a `created_at:`
line + the five sections (Summary; Must-haves/dealbreakers; Strong preferences; Nice-to-haves; Red flags) in
plain observable prose; ends with a "How to use this … No score." note. **Zero numbers/weights/0–100.**
**Result:** ⬜

### T3.2 Import a usable prose brief — 🤖
Tell Claude: **"I already have a job preferences brief"** and paste the contents of
`$JSOS/examples/sample-preferences.md`.
**Expected:** no full interview; writes `preferences.md` preserving your prose; no numbers introduced.
**Result:** ⬜

### T3.3 Import a brief that has a 0–100 rubric → converted — 🤖
Paste `$JSOS/skills/job-preference-interview/evals/files/imported-rubric-brief.md` and ask it to use it.
**Expected:** it notes the system is **qualitative**, converts to prose, and **drops the rubric/weights/points**;
the written `preferences.md` has the prose sections and **no numbers**.
**Result:** ⬜

---

## 4. Returning-user home + conversational config

*(Prereq: complete T2.1 in this sandbox so a workspace + registry exist.)*

### T4.1 Second `job-search` visit shows home (not onboarding) — 🤖
Say **"/job-search:job-search"** again (or "check my job search").
**Expected:** **no onboarding**; shows a status line (workspace · brief age · schedule on/off + frequency ·
last run health), the latest digest summary (date + counts), a pipeline snapshot (counts by status +
`needs_human_check` to review), and conversational quick-actions.
**Result:** ⬜

### T4.2 Add a query conversationally — 🤖
Say: **"add a query for 'staff machine learning engineer' in 'Remote'."**
**Verify (👤):** `cat "$JSOS_TEST/.job-search/config.yaml"` → a new `queries[]` entry with those keywords/location,
`enabled: true`, `version: 1` intact, **no budget/score fields added**.
**Result:** ⬜

### T4.2b Edit a query conversationally — 🤖
Say: **"change the location on the staff ML query to 'United States'."**
**Verify (👤):** `config.yaml` → that **same** `queries[]` item's `location` is updated; its `id`/`keywords`
unchanged, other queries untouched, `version: 1` intact.
**Result:** ⬜

### T4.2c Remove a query conversationally — 🤖
Say: **"drop the staff ML query."**
**Verify (👤):** `config.yaml` → that item is gone; remaining queries intact; `version: 1` intact.
**Result:** ⬜

### T4.3 Change frequency conversationally — 🤖
Say: **"change how often it runs to weekly."**
**Verify (👤):** `config.yaml` → `schedule.frequency: weekly`.
**Result:** ⬜

### T4.4 Turn the schedule off — *verify*, don't just take its word — 🤖 + 👤
Seed a "schedule running" marker first (registry only), so there's something to turn off:
```bash
printf '{\n  "version": 1,\n  "active_workspace": "%s/.job-search",\n  "scheduling": {"installed": true, "mechanism": "loop", "set_at": "2026-06-11T00:00:00+00:00"}\n}\n' "$JSOS_TEST" > "$JOBSEARCH_OS_REGISTRY"
```
Then say: **"actually, turn off the schedule for now."**
**Expected:** Claude (a) tells you to stop the loop (end the session / cancel the pending wakeup), (b) clears
the scheduling marker in the registry, (c) confirms it's off — and never touches your `crontab`.
**Verify (👤):**
```bash
grep -A2 '"scheduling"' "$JOBSEARCH_OS_REGISTRY"    # "installed": false, mechanism null
crontab -l 2>/dev/null | grep -c job-search-run     # 0 — your real crontab is untouched
```
**Result:** ⬜

### T4.5 Update preferences (re-interview) — 🤖
Say: **"update my preferences"** → it re-invokes the interview and rewrites `preferences.md` (new `created_at`).
**Result:** ⬜

### T4.6 Mark a job's status — 🤖
After a run has populated `jobs.jsonl`, say: **"mark the <company> role as interested."**
**Verify (👤):** `tail -1 "$JSOS_TEST/.job-search/jobs.jsonl"` → a single-line `status_changed` event for that
posting's `source_id` with `"status":"interested"`; the home pipeline count reflects it.
**Result:** ⬜

### T4.7 Conversational robustness — the interface IS the product — 🤖
The config interface is natural language, so test more than one phrasing per action. For each cell, send the
phrasing and record whether Claude makes the **right** edit — or asks **one** clarifying question when genuinely
ambiguous. It must never silently do the wrong thing; **`version: 1` stays; no score/budget fields ever appear.**

| Action | Multi-intent | Oblique | Negative / exclude | Typo / loose |
|---|---|---|---|---|
| Frequency | "add an ML query **and** make it hourly" | "stop pulling so often" | — | "make it evry day" |
| Query | (multi-intent above) | "also keep an eye out for staff roles" | "I don't want the onsite ones" | "ad a querey for data eng" |
| Status | "mark Acme applied and Beta rejected" | "I'm into the Acme one" | "I'm not interested in Beta" | — |

**Expected, per cell:** correct `config.yaml`/`jobs.jsonl` edit **or** one targeted clarifying question
(e.g. "by 'so often' do you mean hourly→daily?"); multi-intent applies **both** changes; negative phrasings
**exclude** (add an exclusion / mark not-interested), never add the thing. `version: 1` preserved throughout.
**Verify (👤):** `cat "$JSOS_TEST/.job-search/config.yaml"` after the multi-intent + typo rows; fold the state
after the status row.
**Result:** ⬜

### T4.8 Home failure-states — don't bury problems — 🤖 + 👤
The healthy home is T4.1; these are the states `home.md:26-92` says must render specifically. Build each, then
say **"/job-search:job-search"**:
- **No runs yet** (workspace exists, no digest): complete onboarding but **decline** the sample run (or
  `rm "$JSOS_TEST/.job-search/reports/"*.md`). → Home says *"No runs yet — want me to run your first search
  now?"*, not an empty digest block.
- **Last run blocked:** seed a blocked run-health record, then open home:
  ```bash
  mkdir -p "$JSOS_TEST/.job-search/runs"
  printf '{"run_health":"blocked","error":"E-QUOTA"}\n' > "$JSOS_TEST/.job-search/runs/2099-01-01T00-00-00Z.json"
  ```
  → Home **names `E-QUOTA`** with its billing recovery and says existing matches are unaffected — it does
  **not** bury the failure under a cheery summary.
- **Stale brief (>3 months):** age the brief, then open home:
  ```bash
  sed -i.bak 's/created_at:.*/created_at: 2025-01-01/' "$JSOS_TEST/.job-search/preferences.md"
  ```
  → Home surfaces the stale-brief nudge ("your preferences are about N months old — want to update them?").
**Result:** ⬜

---

## 5. Scheduled run (`job-search-run`) — LIVE

### T5.1 Live run produces a digest — 🤖
Say: **"run a job search now"** (or `/job-search:job-search-run`).
**Expected:** free `status` gate first; one `search-jobs` per enabled query; new postings judged from summary,
full details read for the promising ones; writes `reports/<date>-digest.md` (Run health line; counts line;
Strong→Moderate→Weak; Filtered-out: N; calls-first usage; footnotes) and appends `evaluated` events to
`jobs.jsonl`. No scores, budget fields, or invented actual charge.
**Verify (👤):** `cat "$JSOS_TEST/.job-search/reports/"*.md` ; `wc -l "$JSOS_TEST/.job-search/jobs.jsonl"`.
**Result:** ⬜

### T5.2 Re-run dedups — 🤖
Immediately run it again.
**Expected:** dedup by `source_id` → "No new postings — you've already seen all N of these"; **no** duplicate
`evaluated` events; no `get-posting` calls; Run health healthy; exits 0.
**Result:** ⬜

### T5.3 Headless first-run with no workspace → E-NO-CONFIG — 👤
```bash
T2=$(mktemp -d)
JOBSEARCH_OS_REGISTRY="$T2/absent.json" JOBSEARCH_OS_HOME="$T2" \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run"     # no --workspace, empty sandbox
echo "exit: $?"; rm -rf "$T2"
```
**Expected:** names **E-NO-CONFIG** (run the job-search skill); makes no calls; no `runs/` record is written (no workspace) — the failure is visible because the next job-search visit routes to onboarding; the process exits **0** (do not assert non-zero).
**Result:** ⬜

### T5.4 Headless **+ live** run — the actual scheduled path — 👤  ★ production path
This is the command half of the **`/loop` line** from T9.1 (only delta: `--plugin-dir`, since the plugin isn't
installed in the sandbox). It proves the scheduled job itself works headlessly against the real API — the
mandatory suite otherwise tests headless-only on the fake shim (T7.8–T7.10) and live-only interactively (T5.1).
```bash
cd "$JSOS_TEST/.job-search" && claude --plugin-dir "$JSOS" -p "/job-search:job-search-run" \
  >> "$JSOS_TEST/.job-search/runs/cron.log" 2>&1
echo "exit: $?"
tail -8 "$JSOS_TEST/.job-search/runs/cron.log"          # the run summary, exactly as cron would log it
ls -t "$JSOS_TEST/.job-search/reports/"*.md | head -1   # a digest exists / was refreshed
```
**Expected:** exit **0**; **no prompt** (headless); a `reports/<date>-digest.md` with the **same shape** as T5.1
(Run health line, counts line, Strong→Moderate→Weak); the summary lands in `cron.log`. Fresh matches **or** a clean
"you've already seen all N of these" dedup digest are both passes (dedup if T5.1 already searched this workspace);
0 live results → §0.4 fallback.
**Cross-check** `/loop` runs this same skill headlessly each interval — per the interval table in
`shared/references/internals.md`, daily composes to
`/loop 24h /job-search:job-search-run` (loose-skill installs → `/loop 24h /job-search-run`).
**Result:** ⬜

### T5.4C Codex headless run writes the workspace directly — 👤  ★ Codex production path
Run this only where `codex` is installed and the Job Search skills are installed for Codex. It exists because
Codex `workspace-write` can read `~/.job-search` from another cwd while refusing to write run artifacts there.
The workspace must be the Codex cwd, or it must be passed with `--add-dir`.
```bash
cd "$JSOS_TEST/.job-search" && codex exec --skip-git-repo-check --sandbox workspace-write \
  -c sandbox_workspace_write.network_access=true '$job-search-run' \
  >> "$JSOS_TEST/.job-search/runs/codex.log" 2>&1
echo "exit: $?"
tail -8 "$JSOS_TEST/.job-search/runs/codex.log"
ls -t "$JSOS_TEST/.job-search/reports/"*.md | head -1
ls -t "$JSOS_TEST/.job-search/runs/"*.json | head -1
```
**Expected:** exit **0**; no prompt; the newest digest and run record are written directly under
`$JSOS_TEST/.job-search/`, not under `/private/tmp` or another recovery directory; the digest has the normal
Run health line, counts line, and match sections with reasoning.
**Equivalent from another cwd:** replace `cd "$JSOS_TEST/.job-search" &&` with
`codex exec --skip-git-repo-check --sandbox workspace-write --add-dir "$JSOS_TEST/.job-search" ...`.
**Result:** ⬜

### T5.5 Non-healthy digest shape — `blocked` must replace the body — 👤 (fake shim)
A blocked run must write a digest whose body is the **named error + fix**, not a cheery summary. Drive the
deterministic `down` scenario and read the digest:
```bash
SH5=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$SH5" >/dev/null
PATH="$SH5/_bin:$PATH" JOBSEARCH_FIXTURES="$JSOS/tests/fixtures" JOBSEARCH_TEST_SCENARIO=down \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $SH5"; echo "exit: $?"
cat "$SH5/reports/"*.md 2>/dev/null; rm -rf "$SH5"
```
**Expected:** writes a `runs/<id>.json` with `run_health: blocked` naming **E-SERVICE-DOWN**, so the next job-search home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?`; the digest's Run-health line reads exactly **`Run health: blocked (action needed)`**
(the full set is `healthy | partial (<why>) | degraded (job sources flaky) | blocked (action needed)`); the body is
the **E-SERVICE-DOWN** message ("unreachable right now … next scheduled run will retry"), **not** a match list.
(`degraded`/`partial` digest shapes are strengthened in T7.9/T7.7.)
**Result:** ⬜

---

## 6. Relevance evaluation (`evaluate-job-fit`)

### T6.1 A fitting posting — 🤖
Paste a real job description that matches your brief and ask **"does this fit my preferences?"**
**Expected:** `relevant: true` + a band (`weak/moderate/strong`) + 1–3 sentences of reasoning citing specifics.
**No numeric score.**
**Result:** ⬜

### T6.2 A dealbreaker violation — 🤖
Paste a posting that clearly violates a must-have (e.g. onsite in a city you ruled out).
**Expected:** `relevant: false`, the dealbreaker named in the reasoning; band is null.
**Result:** ⬜

### T6.3 An unknown must-have — 🤖
Paste a posting that simply doesn't mention something you require (e.g. remote policy unstated).
**Expected:** **not rejected**; `needs_human_check: true`, the unknown listed, and the exact question to confirm
in the reasoning. Unknowns are never counted against it.
**Result:** ⬜

---

## 7. Named-error paths (no silent failures)

### Live-triggerable

### T7.1 E-NO-AUTH — 👤
```bash
T3=$(mktemp -d); cp -R "$JSOS_TEST/.job-search" "$T3/.job-search" 2>/dev/null || true
AGENT_DATA_API_KEY="" JOBSEARCH_OS_HOME="$T3" JOBSEARCH_OS_REGISTRY="$T3/reg.json" \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $T3/.job-search"
echo "exit: $?"; rm -rf "$T3"
```
*(If your key is in `~/.agent-data/config.json`, temporarily test in a shell where it isn't, or skip — the eval covers it.)*
**Expected:** halts with **E-NO-AUTH** (names the `export AGENT_DATA_API_KEY=…` fix); nothing pulled; writes a `runs/<id>.json` with `run_health: blocked` naming **E-NO-AUTH**, so the next job-search home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?`.
**Result:** ⬜

### T7.2 E-NO-AGENT-DATA — 👤
```bash
T4=$(mktemp -d)
PATH="/usr/bin:/bin" JOBSEARCH_OS_HOME="$T4" JOBSEARCH_OS_REGISTRY="$T4/reg.json" \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $T4/.job-search"  # agent-data not on this PATH
echo "exit: $?"; rm -rf "$T4"
```
**Expected:** **E-NO-AGENT-DATA** naming the `npm install -g agent-data` fix; writes a `runs/<id>.json` with `run_health: blocked` naming **E-NO-AGENT-DATA**, so the next job-search home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?`. *(The trimmed
PATH needs no python3 — the skills are zero-dependency; see T9.4.)*
**Result:** ⬜

### T7.3 E-NO-CONFIG — covered by T5.3. **Result:** ⬜
### T7.4 E-NO-PREFERENCES — 👤
```bash
T5=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$T5/.job-search" >/dev/null
: > "$T5/.job-search/preferences.md"
claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $T5/.job-search"; echo "exit: $?"; rm -rf "$T5"
```
**Expected:** **E-NO-PREFERENCES** naming the job-preference-interview skill; nothing pulled; writes a `runs/<id>.json` with `run_health: blocked` naming **E-NO-PREFERENCES**, so the next job-search home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?`.
**Result:** ⬜

### Fake-shim only (deterministic error injection — cannot be forced on the live API)

Shared setup for T7.5–T7.11:
```bash
SH=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$SH" >/dev/null
export FAKE="PATH=$SH/_bin:$PATH JOBSEARCH_FIXTURES=$JSOS/tests/fixtures"
# run pattern:  env $FAKE JOBSEARCH_TEST_SCENARIO=<scenario> claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $SH"
```
Run each by giving Claude: *"run the job-search-run skill with --workspace $SH and the fake shim (PATH=$SH/_bin:$PATH,
JOBSEARCH_FIXTURES=$JSOS/tests/fixtures, JOBSEARCH_TEST_SCENARIO=<scenario>) and show the digest + exit code."*

| Test | scenario | Expected | Result |
|---|---|---|---|
| T7.5 **E-QUOTA** | `quota` | plain-language quota note leads with the billing recovery and exact zero prior metered calls; rejected attempt is unmetered; no retry or invented balance/charge; existing matches intact; writes a `runs/<id>.json` with `run_health: blocked` naming **E-QUOTA**, so the next job-search home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?` | ⬜ |
| T7.6 **E-SERVICE-DOWN** | `down` | "service down" digest, Run health blocked; **no** search/get-posting calls; writes a `runs/<id>.json` with `run_health: blocked` naming **E-SERVICE-DOWN**, so the next job-search home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?` | ⬜ |
| T7.7 **E-UPSTREAM-STRETCH** | `stretch` | retries the 502 with backoff, opens each source's circuit after two consecutive failed queries against it (the shim fails every source → all stretched); writes a **partial** digest (Run health `partial (all sources unavailable)`); doesn't crash | ⬜ |
| T7.8 invalid-pair (non-error) | `invalid-pair` | no retry; summary-only judgment + "detail link expired" footnote; `detail_read:false`; run completes, exit 0 | ⬜ |
| T7.9 degraded (non-error) | `degraded` | Run-health line reads `degraded (job sources flaky)`; digest notes results this run may be affected; **no detail-read cap** (reads promising matches as normal); still produces matches; exit 0 | ⬜ |
| T7.10 many promising postings | `many-promising` | every promising posting is evaluated; if the host hits a subagent/thread limit, it continues in rolling batches or falls back sequentially; capacity backpressure alone does **not** make Run health partial | ⬜ |
| T7.11 zero / all-known | `zero-empty` | a completed, non-error outcome: every enabled stream ran and returned nothing, and the reply still ends on ONE actionable next step — an offer to propose broader, complementary role families for the user to accept, never a hand-edit of `config.yaml` keywords and never an automatic re-search with different terms; exit 0. (All-known: pre-seed jobs.jsonl with the happy ids → "No new postings — you've already seen all N of these." — leave the queries as they are.) | ⬜ |

```bash
rm -rf "$SH"
```

The next three reuse the same fake shim and are fully **offline** (no credits). Each builds its own throwaway
workspace, so they don't depend on the shared `$SH` above.

### T7.11 E-CONFIG-VERSION — a config from a newer version halts — 👤
```bash
SHV=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$SHV" >/dev/null
sed -i.bak 's/^version: 1/version: 3/' "$SHV/config.yaml"      # pretend a newer skill wrote it
PATH="$SHV/_bin:$PATH" JOBSEARCH_FIXTURES="$JSOS/tests/fixtures" \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $SHV"; echo "exit: $?"; rm -rf "$SHV"
```
**Expected:** **E-CONFIG-VERSION** ("written by a newer version … update the job-search skills"); HALT at
preflight (no `search-jobs`/`get-posting`); writes a `runs/<id>.json` with `run_health: blocked` naming **E-CONFIG-VERSION**, so the next job-search home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?`.
**Result:** ⬜

### T7.12 E-BAD-QUERY — skip the bad query, keep the good ones — 👤
E-BAD-QUERY is **non-blocking** (skip the query, continue). Build a workspace with one good and one malformed
query (the `bad-query` scenario rejects only the `INVALID` sentinel location with a `422`):
```bash
SHB=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$SHB" >/dev/null
cat > "$SHB/config.yaml" <<'YAML'
version: 1
workspace:
  preferences_path: "preferences.md"
queries:
  - { id: "good", keywords: "software engineer", location: "United States",   limit: 10, enabled: true }
  - { id: "bad",  keywords: "data engineer",     location: "INVALID-LOCATION", limit: 10, enabled: true }
search:
  detail_model: "balanced"  # valid legacy-v1 selector
schedule:
  frequency: "daily"
  time: "08:00"
YAML
PATH="$SHB/_bin:$PATH" JOBSEARCH_FIXTURES="$JSOS/tests/fixtures" JOBSEARCH_TEST_SCENARIO=bad-query \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $SHB"; echo "exit: $?"
cat "$SHB/reports/"*.md 2>/dev/null; rm -rf "$SHB"
```
**Expected:** the **bad** query → **E-BAD-QUERY** naming the param (`location`, from `details[].loc`) + the
"fix it in `config.yaml`" guidance, and is **skipped**; the **good** query still runs and produces matches; Run
health **partial**; **no retry** on the 422 (`retryable:false`); run **completes, exit 0** (skip, not halt).
**Result:** ⬜

### T7.13 detail-fetch-failed (non-error) — retry, then fall back to summary — 👤
```bash
SHD=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$SHD" >/dev/null
PATH="$SHD/_bin:$PATH" JOBSEARCH_FIXTURES="$JSOS/tests/fixtures" JOBSEARCH_TEST_SCENARIO=detail-fetch-failed \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $SHD"; echo "exit: $?"
cat "$SHD/reports/"*.md 2>/dev/null; rm -rf "$SHD"
```
**Expected:** the `502 detail_fetch_failed` is **retryable** → retries with backoff, then **gives up on the detail**
and judges from the **summary** (footnote that the detail couldn't be read); `detail_read:false` for that posting;
the run **completes, exit 0** (a footnote, not a failure).
**Result:** ⬜

### T7.14 Pagination and usage-context matrix — 🤖 + 👤 (fake shim, fully offline)

Use the named eval prompt as the setup recipe for each row; each recipe creates its own temporary workspace,
redirected registry, fake-shim call log, and artifact assertions. Drive one pass manually here as an offline
smoke check. The structural gate proves only that the recipes are coherent; it does not substitute for these
effect checks or the off-CI behavioral eval runs.

| Case | Recipe | Observable pass condition | Result |
|---|---|---|---|
| Default, no pagination | `job-search-run` eval 26 | omitted review-depth config makes exactly the first-page calls, never sends a cursor, records first-page scope, and leaves config/registry bytes unchanged | ⬜ |
| Finite, one-off | `job-search-agent` eval 6 + `job-search-run` eval 31 | preview and exact confirmation precede metered work; the run records one-off finite scope and leaves config byte-identical | ⬜ |
| Finite, saved | `job-search-agent` eval 7 + `job-search-run` eval 32 | config is unchanged before yes, saved atomically after yes, and a later headless run uses durable consent without another prompt | ⬜ |
| Exhaustive `all` | `job-search-agent` evals 8–9 + `job-search-run` eval 33 | ambiguous wording defaults to one-off; explicit recurring wording saves only after yes; board streams drain, LinkedIn stays one page, and scratch is removed | ⬜ |
| Incomplete cursor | `job-search-run` eval 29 | trustworthy rows are kept, healthy streams continue, partial-depth evidence is recorded, no cursor/checkpoint is durable, and the next run starts from page one | ⬜ |
| Quota with zero / prior usage | `job-search-run` evals 6 and 30 | first-attempt rejection reports zero; later rejection derives prior metered attempts from the completed call log, excludes the rejected attempt, and preserves earlier records | ⬜ |
| One-time deeper-coverage nudge | `job-search` evals 11–14 | only eligible local evidence renders the offer; shown/declined/deferred/unanswered outcomes write the marker before interaction and suppress every later home view | ⬜ |
| Usage explanation | `job-search-agent` eval 11 | reads local run records, leads with actual calls and operation breakdown, labels the stored equivalent, makes no API call, and changes no config/registry bytes | ⬜ |

#### Five-run post-release deeper-coverage worksheet — observation only

After release, fill this from `runs/<run_id>.json` for five **comparable finite runs** (same ordered sources,
enabled query count, and finite review target). This is local product observation, not a release gate. Do not
generalize from fewer than five runs, and do not let the worksheet or the agent change config automatically;
any later review-depth change remains a separate conversational choice with its normal consent boundary.

| Run (oldest → newest) | `continuation_rows` | `unique_unseen_roles_continuations` | `selected_roles_from_continuations` | `metered_calls` | `same_run_cross_query_duplicate_rows` | `cross_source_rows_merged` | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| 1 |  |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |  |
| 4 |  |  |  |  |  |  |  |
| 5 |  |  |  |  |  |  |  |

For each row, copy the first three values and both duplicate/merge counts from `pagination_metrics`, and
copy calls from `agent_data_usage.metered_calls`. After all five rows exist, note whether continuation is
consistently contributing unseen and selected roles, and how that observed contribution relates to calls
and duplicate/merge volume. Record the observation; do not auto-tune `max_new_postings_per_run`.

---

## 8. Never-clobber / data safety

### T8.1 Adopt an existing workspace without overwriting — 👤 + 🤖
```bash
T6=$(mktemp -d)
mkdir -p "$T6/job-search"                                  # LEGACY (visible) location
cp "$JSOS/templates/config.example.yaml" "$T6/job-search/config.yaml"
sed -i.bak -e 's/^version: 2/version: 1/' \
  -e 's/^  # Setup inserts the required exact search.detail_model before writing a valid new workspace\./  detail_model: "balanced"/' \
  "$T6/job-search/config.yaml"; rm -f "$T6/job-search/config.yaml.bak"
printf 'SENTINEL-PREFS\n' > "$T6/job-search/preferences.md"
printf '{"event":"evaluated","source_id":"SENTINEL-JOB","status":"new"}\n' > "$T6/job-search/jobs.jsonl"
shasum -a 256 "$T6/job-search/"{preferences.md,jobs.jsonl,config.yaml}     # record
```
Launch Claude with `JOBSEARCH_OS_HOME="$T6"` (no registry yet) and say **"/job-search:job-search"**.
**Expected:** it detects + **adopts** the legacy workspace ("Found an existing workspace at …"), writes the
registry to point there, and goes to **home (no fresh interview)**.
**Verify:** re-run `shasum -a 256 …` → **identical**; `SENTINEL-PREFS` / `SENTINEL-JOB` intact; only `runs/`+`reports/`
added. `rm -rf "$T6"`.
**Result:** ⬜

### T8.2 Real data untouched (run after the whole pass) — 👤
```bash
ls -ld ~/.job-search 2>/dev/null && echo "exists (was it yours before testing?)" || echo "~/.job-search absent — good"
stat -f '%Sm' ~/job-search 2>/dev/null    # mtime should predate your testing
crontab -l 2>/dev/null | wc -l            # unchanged (no test cron entries)
```
**Expected:** your real `~/.job-search` is unchanged/absent, `~/job-search` mtime predates testing, `crontab`
unchanged. (All tests used `$JSOS_TEST`/temp dirs + declined real scheduling.)
**Result:** ⬜

---

## 9. Scheduling (unattended-first; in-session `/loop` fallback)

Scheduling is **unattended-first**: the advocated default is an **unattended wall-clock schedule**
(`cron`/`launchd` where the host has one), with the in-session `/loop` as the **named fallback**. A
**mandatory config-time canary** must prove the schedule actually fires before it is recorded active in the
registry. The tests below exercise the **`/loop` fallback** path and the never-write-a-real-crontab consent
guarantee; the config-time **canary is not yet exercised here** (it is the runtime canary check noted under
"Automated lanes vs. the manual residual" above — a known residual, not a gap).

### T9.1 The composed `/loop` line matches the pinned interval table — 🤖
In a sandboxed session, for each frequency ask: **"if my schedule were <frequency>, what's the exact /loop
line?"** (or read it off the scheduling offers in T2.1/T4.3).
**Expected:** exactly the interval table in `shared/references/internals.md` → Scheduling setup —
`hourly → /loop 1h …`, `every-2-hours → /loop 2h …`, `every-6-hours → /loop 6h …`, `daily → /loop 24h …`,
`weekly → /loop 168h …`; the target is `/job-search:job-search-run` in this plugin suite (bare
`/job-search-run` only for loose-skill installs). Any other interval or target is a ❌.
**Result:** ⬜

### T9.3 `/loop` scheduling — nothing installed on the machine — 🤖 + 👤
This drives the **in-session `/loop` fallback** — the path taken when the host has no unattended
scheduler or the user declines the machine change (the suite never writes a real crontab). When you
decline the unattended schedule (or ask to keep it in-session), onboarding's scheduling step uses the
in-session `/loop`. Say:
**"keep it running automatically, but just in this session."**
**Expected:** Claude shows the loop line **`/loop <interval> /job-search:job-search-run`** (the suite runs
as the plugin, so the target is namespaced; matching your configured frequency — `24h` for daily) and records
the mechanism — **without** writing any crontab line or launchd plist.
**Verify (👤):**
```bash
grep -A2 '"scheduling"' "$JOBSEARCH_OS_REGISTRY"    # "installed": true, "mechanism": "loop"
crontab -l 2>/dev/null | grep -c job-search-run     # 0 — nothing installed in cron
```
**Result:** ⬜

### T9.4 Zero-Python user path — the headline guarantee — 👤
The shipped skills must work on a machine with **no Python at all**. Mask `python3` and run a full headless
pass (fake shim, so it's free):
```bash
T9=$(mktemp -d); MASK=$(mktemp -d)
printf '#!/bin/sh\necho "python3: command not found" >&2\nexit 127\n' > "$MASK/python3"; chmod +x "$MASK/python3"
"$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$T9"
PATH="$MASK:$T9/_bin:$PATH" JOBSEARCH_FIXTURES="$JSOS/tests/fixtures" JOBSEARCH_TEST_SCENARIO=happy \
  JOBSEARCH_OS_HOME="$T9" JOBSEARCH_OS_REGISTRY="$T9/reg.json" \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $T9"
ls "$T9/reports/"*.md && grep -c '"source_id"' "$T9/jobs.jsonl"
rm -rf "$T9" "$MASK"
```
**Expected:** the run completes identically to T7's happy path — digest written, single-line events with
`source_id` appended — with `python3` resolving to the failing mask the whole time. Any "python3: command
not found" surfacing as a run error is a ❌ (the skills must never invoke it).
**Result:** ⬜

---

## 10. Philosophy guardrails (cross-cutting) — 👤

### T10.1 No numeric scoring, budget config, or invented charge in any output **file** — 👤
Skim every digest/brief/config Claude produced during testing (under `$JSOS_TEST` and any `$SH*`/`$T*` dirs you
kept). This covers files; **chat replies** are covered by T10.2.
```bash
grep -rniE "0-100|0–100|fit score|[0-9]+ ?points|category weight|^[[:space:]]*(budget|credits?|cost)[[:space:]]*[:=]" \
  "$JSOS_TEST" 2>/dev/null
grep -rniE "actual charge|pay-as-you-go|\$[0-9]|credits?" "$JSOS_TEST" 2>/dev/null
```
**Expected:** the first grep is empty except an explicitly requested fit score that remained in chat rather than
a saved artifact. Review the second grep: salary display, accurate calls-first usage, a clearly labeled pay-as-
you-go equivalent, and **E-QUOTA** recovery are allowed; an unlabeled or invented actual charge/account balance
is not. No `budget`, `credits`, or `cost` config field or hard monetary cap appears.
**Result:** ⬜

### T10.2 Philosophy holds in CHAT, not just files — 🤖 + 👤
The qualitative-relevance / usage-context rule must hold in Claude's **replies**, not only in saved files. Capture a few
scripted probes headlessly (two of them try to *elicit* a violation) and grep the transcript:
```bash
PROBES="$JSOS_TEST/probes.txt"; : > "$PROBES"
for q in "how do I control how much this costs?" \
         "which of these matches is the best fit — rank them for me?" \
         "show me the results from the latest run" \
         "give each of my matches a fit score out of 100"; do
  printf '\n### %s\n' "$q" >> "$PROBES"
  (cd "$JSOS_TEST/.job-search" && claude --plugin-dir "$JSOS" -p "$q") >> "$PROBES" 2>&1
done
grep -niE "0-100|0–100|fit score|[0-9]+ ?points|category weight|\$[0-9]|credits?|budget" "$PROBES"
```
After running the probes, also grep the **saved files** for any persisted scores (an on-request score in the live reply is allowed; what is forbidden is writing it into an artifact):
```bash
grep -rniE "fit score|[0-9]+ ?points|category weight" \
  "$JSOS_TEST/.job-search/reports/" "$JSOS_TEST/.job-search/jobs.jsonl" \
  "$JSOS_TEST/.job-search/config.yaml" 2>/dev/null
```
Note: `salary`/`$`-amounts (job salary info) and reactive `E-QUOTA` wording are allowed and should not cause a ❌.

**Expected (read the transcript):** Default/unsolicited relevance output stays band-only. The usage answer
leads with actual calls and the outcome levers — frequency, sources, and review depth — and may load accurate
current pricing from the canonical agent-data contract when it clearly labels a pay-as-you-go equivalent. It
must not invent an actual charge, account balance, or `budget`/`credits`/`cost` config field. For the **explicit**
"fit score out of 100" request, honoring it in the reply
is acceptable (the agent is flexible) **as long as** it (a) notes scoring is non-default and
qualitative bands are the real signal, and (b) does NOT persist the score into any
digest/brief/`config.yaml`/`jobs.jsonl`. A ❌ is: a numeric relevance score in **unsolicited** output, an
on-request score written into a saved artifact, a monetary budget control, or an unlabeled/invented charge.
For "show me the results from the latest run", a ❌ is a title-only list of matches; each shown match must
include the digest's reasoning line and any "confirm" warning.
**Result:** ⬜

---

## 11. Docs accuracy — 👤

### T11.1 README ↔ reality
Open `$JSOS/README.md`: the install commands match what you ran (`claude --plugin-dir`, `/plugin install
job-search@agent-data` gated "once published"); the troubleshooting table matches `shared/references/errors.md`
(spot-check 3 rows).
**Result:** ⬜

### T11.2 Sample digest ↔ real digest
Compare `$JSOS/examples/sample-digest.md` to a real digest from T5.1 — same structure (header, Run health, counts
line, Strong/Moderate/Weak, Filtered-out, footnotes).
**Result:** ⬜

---

## 12. Full eval regression — 🤖 + ⚙️

First, the **structural gate** (⚙️, host-independent) — every scenario is well-formed before any is driven:
```bash
cd "$JSOS" && python3 scripts/eval_harness.py --root .   # "Eval harness: eval scenarios coherent."
```

Then ask Claude, for each skill, to **run its evals** (the `harness` in `skills/<skill>/evals/evals.json`; they use the
fake-agent-data shim, so zero real credits) — **185 scenarios**:
- `evaluate-job-fit` (5) · `job-search-run` (72) · `job-preference-interview` (5) · `job-search` (57) · `job-search-agent` (46).

Each suite now includes a **discovery** scenario (plant the skill among its siblings, drive a naive prompt, assert the
right skill is selected and the confusable sibling is not — the four overlap pairs). The judgment-heavy **stochastic**
scenarios (fit verdicts, injection-resistance, cross-source merge, weighted fair-share selection, baited stop-after-first-match
resistance, and every discovery scenario) are marked to run at **N ≥ 5** with a **no-guidance control** arm — that behavioral
rep loop is the **off-CI live-harness step** (record pass-rate + variance + the control delta with `scripts/eval_harness.py`
`aggregate_reps` / `control_delta`); a single driven pass here is the smoke check. Every **crown-jewel** scenario carries a
baited shortcut **and** the opposite-direction control (e.g. stop-after-early-results vs. complete-the-queue, resume-a-cursor
vs. close-interrupted-and-research, silently-migrate-v1 vs. passive-compat), and asserts on **effects** rather than exact prose.
Milestone/liveness scenarios pin a **fixed-time fixture** (a deterministic clock), and each driven run stamps a **unique run
marker** into its artifacts (checked with `--check-artifacts`) so a stale artifact can never create a false pass.
**Expected:** the structural gate is clean; every driven scenario passes; outputs are philosophy-clean.
**Result:** ⬜

---

## 13. Config command surface (PLANNED — pending build) — 🤖

Today all configuration is **conversational** (you chat; Claude edits `config.yaml`). Dedicated config **slash
commands** — an `/effort`-style surface, e.g. `/job-search-frequency hourly` — are **planned but not built yet**
(see `docs/exec-plans/tech-debt-tracker.md` → `TODO-CONFIG-COMMANDS`). These tests are **pending-build**: they are **N/A** today and only go
green once the commands ship. A green run here must never imply the commands exist.

| Test | Planned command | Expected once built | Result |
|---|---|---|---|
| T13.1 | `/job-search-frequency <hourly…weekly>` | sets `schedule.frequency` to the same value the conversational path (T4.3) would; `version: 1` intact; no cost math | ⬜ pending-build |
| T13.2 | `/job-search-add-query "<keywords>" "<location>"` | appends a `queries[]` item identical to T4.2's conversational result | ⬜ pending-build |
| T13.3 | `/job-search-schedule off` | turns the schedule off **and clears the registry marker** (via `set-unscheduled`) | ⬜ pending-build |

**Acceptance for each:** the command produces the **same** `config.yaml`/registry edit as its conversational
equivalent (parity), errors on bad input with a named `E-*`, and never introduces a numeric/budget field. Until
built, mark **N/A (pending build)**.

---

## 14. Multi-source (LinkedIn + Ashby + Greenhouse + Lever)

### T14.1 Live Ashby search returns ashby rows — 👤
```bash
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 search-jobs \
  --keywords "software engineer" --limit 3 --source ashby \
  --fields id,source_id,source_url,title,company_name,source
```
**Expected:** rows with `"source":"ashby"`, UUID `source_id`s, `jobs.ashbyhq.com` URLs.
**Result:** ⬜

### T14.1a Live Greenhouse search returns greenhouse rows — 👤
```bash
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 search-jobs \
  --keywords "software engineer" --limit 3 --source greenhouse \
  --fields id,source_id,source_url,title,company_name,source,posted_at
```
**Expected:** rows with `"source":"greenhouse"`, `<company>:<numeric>` `source_id`s, `boards.greenhouse.io` URLs, and a populated `posted_at`.
**Result:** ⬜

### T14.1b Live Lever search returns lever rows — 👤
```bash
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 search-jobs \
  --keywords "software engineer" --limit 3 --source lever \
  --fields id,source_id,source_url,title,company_name,source,posted_at,salary_display
```
**Expected:** rows with `"source":"lever"`, `<company>:<uuid>` `source_id`s, `jobs.lever.co` URLs, and a populated `posted_at` (Lever's `salary_display` may carry HTML — treat as free text, never parse).
**Result:** ⬜

### T14.1c Live ATS phrase-sensitivity contract smoke — 👤 (LIVE · separately authorized · **not a merge gate**)

**Never run this automatically, and never treat it as a gate.** Every merge-gating assertion about phrase
sensitivity runs offline against the bundled shim (`JOBSEARCH_TEST_SCENARIO=query-sensitive`, `job-search`
eval 54 and `job-search-run` eval 72) — that is what proves the *behavior*. This smoke checks only that the
**live ATS contract still has the shape that behavior assumes**. It makes **billable, networked**
`search-jobs` calls, so **get explicit approval for billable/network calls before running it**. Without that
approval, without network, or without credits, record it verbatim as
**`SKIPPED — authorization or network unavailable`** — a skipped smoke is **never** reported as passed, and a
red one opens an investigation rather than blocking a merge.

Send the **same** location, limit, freshness, and Ashby source three times, changing only `--keywords`:
(1) the phrase-stuffed query, (2) `product engineer`, (3) `AI engineer`.
```bash
LISTING=f9a6ec16-0bfd-44d8-b3ee-073776745ee7
FIELDS=id,source_id,source_url,title,company_name,location_display,posted_at,published_at,source
CUTOFF=$(date -u -v-14d +%F)     # GNU: date -u -d '14 days ago' +%F — the shipped past-2-weeks window
echo "observed: $(date -u +%F)"
for KW in "founding product engineer AI startup" "product engineer" "AI engineer"; do
  printf '\n### keywords=%s\n' "$KW"
  agent-data call "$LISTING" search-jobs --keywords "$KW" --location "United States" \
    --limit 25 --source ashby --published_on_or_after "$CUTOFF" --fields "$FIELDS"
done
```
**Record** the exact request parameters sent, the number of rows each response returned, the effective date
fields present on the returned rows (`published_at` / `posted_at` — the effective date is the later of the
two), and the **observation date** (results are only interpretable against the day they were pulled):

| Observed (UTC) | keywords | location · limit · cutoff · source | rows returned | effective date fields present |
|---|---|---|---:|---|
|  | `founding product engineer AI startup` | United States · 25 · `<cutoff>` · ashby |  |  |
|  | `product engineer` | United States · 25 · `<cutoff>` · ashby |  |  |
|  | `AI engineer` | United States · 25 · `<cutoff>` · ashby |  |  |

**Grade the contract shape and the relative retrieval only — never an absolute count.** Market inventory is
volatile, so no specific row count is a pass condition:
- **Contract shape:** each response echoes `data.query.source: "ashby"` and the sent
  `data.query.published_on_or_after`; every returned row carries `source: "ashby"`, a non-null `source_id`, a
  `jobs.ashbyhq.com` `source_url`, and its effective date fields (both may be null — record that, don't fail it).
- **Relative retrieval:** under identical parameters the two broad role families return **at least as many**
  rows as the phrase-stuffed query. All three at zero on a quiet day, or equal counts, is **not** a failure —
  re-run once before recording. The signal worth investigating is the stuffed phrase out-retrieving *both*
  broad families, which would mean live phrase behavior moved away from what the shim encodes.
**Result:** ⬜ / `SKIPPED — authorization or network unavailable`

### T14.2 Shim multi-source run — 🤖
"Build the eval sandbox (§0.2), export `JOBSEARCH_TEST_SCENARIO=multi-source`, run
job-search-run against the sandbox workspace, and show the digest + jobs.jsonl."
**Expected:** per-source counts breakdown; ashby events carry `"source":"ashby"`; null-date
entries carry a date mark; the first-Ashby-pass footnote is present.
**Result:** ⬜

### T14.3 One source down never blanks the run — 🤖
"Same sandbox, `JOBSEARCH_TEST_SCENARIO=one-source-down`. Run job-search-run; show the digest."
**Expected:** LinkedIn matches land; Run health `partial (ashby unavailable)`; outage footnote.
**Result:** ⬜

---

## Acceptance checklist (sign-off)

- ⬜ Install: plugin validates `--strict`; loads via `--plugin-dir`; single-home references resolve (§1)
- ⬜ Isolation pre-flight passes; canonical persona set before any LIVE test (§0.2, §0.4)
- ⬜ First-run `/job-search:job-search` onboards end-to-end and shows **real live matches**; TTFV recorded < ~5 min (T2.1)
- ⬜ Interview produces a **prose** brief; the 0–100 rubric is gone; import + rubric→prose work (§3)
- ⬜ Returning `/job-search:job-search` shows home incl. **failure-states** (no-runs, blocked, stale-brief); **all config changes work conversationally** — add/**edit**/**remove** query, frequency, schedule off, prefs, status — and survive **phrasing variety** (§4)
- ⬜ **Headless + live** run (the cron path) writes a correct digest; live run **dedups** on re-run; **headless** first-run → E-NO-CONFIG (names the error, exits 0, no `runs/` record); a `blocked` run writes `run_health: blocked` naming the `E-*` so the home view surfaces it (process exits 0) (§5)
- ⬜ Relevance is **qualitative** (relevant + weak/moderate/strong + reasoning); dealbreakers reject; unknowns flag, never reject (§6)
- ⬜ Every blocked path is a **named `E-*`** with its fix — auth, no-CLI, no-config, **config-version**, no-prefs, quota, down, stretch, **bad-query**, invalid-pair, detail-fetch-failed, degraded, zero/all-known (§7)
- ⬜ **Never clobbers** real data; adopts an existing workspace byte-identically; real `~/.job-search`/`~/job-search`/crontab untouched (§8)
- ⬜ Scheduling correct (the composed `/loop <interval>` matches the pinned table per frequency; `/loop` sets `mechanism:loop`; **zero-Python user path** proven with python3 masked) (§9)
- ⬜ **No numeric scores/weights, budget config, or invented charge** in files or unsolicited chat; accurate calls-first usage context is labeled, and users control frequency, sources, and review depth (§10)
- ⬜ Docs match reality (install commands, error table, sample digest) (§11)
- ⬜ Full regression green: `pytest` (**617**; gate on `0 failed`) + the eval structural gate (`eval_harness.py`) + all five skills' evals (**185** scenarios) (§0.3, §12)
- ⬜ Planned config slash-command tests are marked **N/A (pending build)**, not green (§13)
- ⬜ Multi-source: live Ashby/Greenhouse/Lever rows; shim multi-source run shows per-source counts + first-pass footnote; one source down never blanks the run (§14)
- ⬜ Live ATS phrase-sensitivity contract smoke (T14.1c) is **non-gating**: recorded green only after explicit approval for billable/network calls, otherwise `SKIPPED — authorization or network unavailable` (never as passed)

**Teardown:** `rm -rf "$JSOS_TEST"` and any `$T*`/`$SH*` dirs you kept.

---

## Maintainer notes (fill in each pass) — DX feedback loop
Capture reality so the next review can compare against it (this is the boomerang signal — don't skip it):
- **TTFV (T2.1):** ______ s  ·  **Smoke-subset wall-clock:** ______ min  ·  **Full-pass wall-clock:** ______ min
- **Where did onboarding / the home view confuse you?** (the one thing you'd fix first) ______
- **Any T4.7 phrasing Claude misread?** ______
- **New product gaps found** (add to `docs/exec-plans/tech-debt-tracker.md`): ______
