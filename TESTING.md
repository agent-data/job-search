# Job Search OS — Test Plan

A thorough, **Claude-Code-driven** acceptance test suite. The goal: prove every intended feature works,
end to end, with Claude Code as the primary tester. You mostly read instructions to Claude and confirm what
it reports; a few checks are pure shell or visual.

## How to use this doc

- **Driver legend:** 🤖 = give the instruction to Claude Code and let it run · 👤 = you run a shell command or eyeball output · ⚙️ = automated (pytest/CLI).
- **Platform:** written for **macOS** (launchd, BSD `stat -f`, `shasum`). On **Linux**, use cron only — skip the launchd test (T9.2) — and swap BSD-isms (`stat -f '%Sm'` → `stat -c '%y'`); `shasum -a 256`, `xmllint`, and `grep -E` work on both.
- **Live-first.** Tests use the real `agent-data` API (per the project's design and your call). The handful of
  error conditions you can't trigger on demand (quota, outage, stale links) use the bundled **fake-agent-data
  shim** — clearly marked.
- **Isolation is mandatory.** Every test runs in a throwaway sandbox. Your real `~/.job-search/`,
  `~/job-search/`, the OS registry, and your `crontab` are **never** touched. Setup §0.2 redirects everything
  under a temp dir via the `JOBSEARCH_OS_*` env vars.
- Mark each test ✅ / ❌ in the **Result** box. The final **Acceptance checklist** is your sign-off.
- Estimated time: **~75–90 min** for the full pass (the live first-run T2.1 and the §12 evals dominate). The **Smoke subset** — T0.3, T1.1, **T7.13**, T6.1, T7.1 — is a genuine **~10 min** mostly-offline confidence check; it skips the full live onboarding (run T2.1 in the full pass).

---

## 0. Setup

### 0.1 Prerequisites — 👤
```bash
claude --version                 # ≥ 2.1.x
agent-data whoami                # api_key_set: true   (else: set AGENT_DATA_API_KEY and re-check)
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 status   # {"status":"ok"}  (free)
python3 --version                # ≥ 3.9
```
**Expected:** all four succeed; `whoami` shows `api_key_set: true`; status is `ok`.
**Result:** ⬜

### 0.2 Create an isolated sandbox — 👤 (run once per test session)
```bash
export JSOS=~/job-search-os
export JSOS_TEST=$(mktemp -d)
export JOBSEARCH_OS_REGISTRY="$JSOS_TEST/registry.json"
export JOBSEARCH_OS_HOME="$JSOS_TEST"
echo "Sandbox: $JSOS_TEST"
```
Now the registry and the default (`$JSOS_TEST/.job-search`) + legacy (`$JSOS_TEST/job-search`) workspaces all
live under the temp dir.

**Isolation pre-flight — run before any destructive/live test (cheap insurance).** Prove the redirect is live so
nothing can reach your real data:
```bash
python3 "$JSOS/scripts/osctl.py" resolve | python3 -c 'import json,os,sys; r=json.load(sys.stdin); ws=r["workspace"]; t=os.environ["JSOS_TEST"]; assert ws.startswith(t), f"LEAK: workspace {ws} is outside {t}"; assert os.environ.get("JOBSEARCH_OS_REGISTRY","").startswith(t), "LEAK: registry outside sandbox"; print("isolation OK →", ws)'
```
**Expected:** `isolation OK → …/.job-search` under `$JSOS_TEST`. A `LEAK:` / `AssertionError` means the env vars
aren't set in this shell — **stop and re-run the exports** before any test that writes or pulls.

**Launch Claude Code from this same shell** so the skills inherit the env:
```bash
claude --plugin-dir "$JSOS"
```
**Safety rules while testing:**
- When onboarding reaches **scheduling**, answer **"no, just show me the commands"** — do NOT let it install a
  real cron job / launchd plist (that's a lingering side effect). A dedicated, reversible scheduling test is §9.
- **Teardown** when done: `rm -rf "$JSOS_TEST"`. (Re-`export JSOS_TEST=$(mktemp -d)` + the two env vars for a
  fresh first-run.)

### 0.3 Regression baseline — ⚙️
```bash
cd "$JSOS" && python3 -m pytest -q
```
**Expected:** `62 passed` **and `0 failed`** — treat **`0 failed`** as the real gate (the exact count grows as
tests are added; bump this number when it does). Covers `state.py` + `osctl.py` + the fake-shim self-tests
(incl. the `bad-query` scenario behind T7.12).
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
bug throws a named `E-*`, mis-shapes the digest, or crashes; a quiet market returns a clean "0 results — broaden
keywords" (T7.10). Only the former is a ❌.

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

### T1.3 Loose-skills self-containment — 👤
```bash
cd "$JSOS" && ./scripts/build.sh && git status --short
ls skills/*/scripts/osctl.py skills/*/references/internals.md
```
**Expected:** build prints the sync line; `git status` is **empty** (committed copies are in sync); every skill
has its own bundled `scripts/osctl.py` + `references/internals.md`.
**Result:** ⬜

### T1.4 Trigger resolves — 🤖
In a `claude --plugin-dir "$JSOS"` session, type `/job-` and check the completion menu; also try the natural
language "set up job search".
**Expected:** `job-search` (and the other skills) appear; `/job-search` resolves (or `/job-search-os:job-search`
if another plugin claims the bare name); the NL phrase triggers the orchestrator. *(Don't complete the run here —
that's T2.1.)*
**Result:** ⬜

---

## 2. First-run onboarding — the magical moment

### T2.1 Full first-run, end to end (LIVE) — 🤖 + 👤  ★ flagship test
**Setup:** fresh sandbox (§0.2), Claude launched from that shell. Confirm first-run:
```bash
python3 "$JSOS/scripts/osctl.py" resolve     # first_run:true, source:none, workspace:$JSOS_TEST/.job-search
```
**Steps (🤖):** Start the TTFV clock, then say **"set up job search"** (or `/job-search`). Drive it from the
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
- Runs a **live** sample search and shows **real, current** postings judged relevant/weak/moderate/strong with
  reasoning — "found seconds ago." **No numeric scores, no dollar/credit figures.** (0 results → apply the §0.4
  sparse-data fallback before calling this a ❌.)
- Prints the scheduling copy-paste options (cron / launchd / `/loop`) and the home view.
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
Fresh sandbox. Tell Claude: **"/job-preference-interview"** and answer ~6–8 questions.
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

### T4.1 Second `/job-search` shows home (not onboarding) — 🤖
Say **"/job-search"** again (or "check my job search").
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
Seed a "schedule installed" marker first (registry only — **no** real cron), so there's something to turn off:
```bash
python3 "$JSOS/scripts/osctl.py" set-scheduled --mechanism cron   # schedule-status now {"installed":true,...}
```
Then say: **"actually, turn off the schedule for now."**
**Expected:** Claude (a) sees the marker and gives the **exact** removal command (remove the crontab line /
`launchctl unload`), (b) does **not** silently edit your real `crontab`, (c) confirms it's off.
**Verify (👤):**
```bash
python3 "$JSOS/scripts/osctl.py" schedule-status   # SHOULD read {"installed": false, ...}
crontab -l 2>/dev/null | grep -c job-search-run     # 0 — your real crontab is untouched
```
**⚠ Known gap (TODO-SCHED-OFF):** there is currently **no** `osctl.py` command to clear the marker, and the
turn-off flow (`home.md:79-80`) only removes the OS artifact — so `schedule-status` may still report
`installed: true` (stale). If it does, that's the product gap, not a tester error: mark the marker line ❌ and
see the TODO in §13. (The crontab-untouched check must still pass.)
**Result:** ⬜

### T4.5 Update preferences (re-interview) — 🤖
Say: **"update my preferences"** → it re-invokes the interview and rewrites `preferences.md` (new `created_at`).
**Result:** ⬜

### T4.6 Mark a job's status — 🤖
After a run has populated `jobs.jsonl`, say: **"mark the <company> role as interested."**
**Verify (👤):** `python3 "$JSOS/scripts/state.py" fold --jobs "$JSOS_TEST/.job-search/jobs.jsonl"` → that
posting's `status` is `interested`; the home pipeline count reflects it.
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
say **"/job-search"**:
- **No runs yet** (workspace exists, no digest): complete onboarding but **decline** the sample run (or
  `rm "$JSOS_TEST/.job-search/reports/"*.md`). → Home says *"No runs yet — want me to run your first search
  now?"*, not an empty digest block.
- **Last run blocked:** seed a blocked run-health record, then open home:
  ```bash
  mkdir -p "$JSOS_TEST/.job-search/runs"
  printf '{"run_health":"blocked","error":"E-QUOTA"}\n' > "$JSOS_TEST/.job-search/runs/2099-01-01T00-00-00Z.json"
  ```
  → Home **names `E-QUOTA`** with its fix (pull less often / upgrade; existing matches unaffected) — it does
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
Say: **"run a job search now"** (or `/job-search-run`).
**Expected:** free `status` gate first; one `search-jobs` per enabled query; new postings judged from summary,
full details read for the promising ones; writes `reports/<date>-digest.md` (Run health line; counts line;
Strong→Moderate→Weak; Filtered-out: N; footnotes) and appends `evaluated` events to `jobs.jsonl`. No scores/credits.
**Verify (👤):** `cat "$JSOS_TEST/.job-search/reports/"*.md` ; `wc -l "$JSOS_TEST/.job-search/jobs.jsonl"`.
**Result:** ⬜

### T5.2 Re-run dedups — 🤖
Immediately run it again.
**Expected:** dedup by `source_id` → "No NEW postings — all already in your database"; **no** duplicate
`evaluated` events; no `get-posting` calls; Run health healthy; exits 0.
**Result:** ⬜

### T5.3 Headless first-run with no workspace → E-NO-CONFIG — 👤
```bash
T2=$(mktemp -d)
JOBSEARCH_OS_REGISTRY="$T2/absent.json" JOBSEARCH_OS_HOME="$T2" \
  claude --plugin-dir "$JSOS" -p "/job-search-run"     # no --workspace, empty sandbox
echo "exit: $?"; rm -rf "$T2"
```
**Expected:** names **E-NO-CONFIG** (run `/job-search`); makes no calls; no `runs/` record is written (no workspace) — the failure is visible because the next `/job-search` routes to onboarding; the process exits **0** (do not assert non-zero).
**Result:** ⬜

### T5.4 Headless **+ live** run — the actual cron path — 👤  ★ production path
This is the command half of the **daily cron line** from T9.1 (only delta: `--plugin-dir`, since the plugin isn't
installed in the sandbox). It proves the scheduled job itself works headlessly against the real API — the
mandatory suite otherwise tests headless-only on the fake shim (T7.8–T7.10) and live-only interactively (T5.1).
```bash
cd "$JSOS_TEST/.job-search" && claude --plugin-dir "$JSOS" -p "/job-search-run" \
  >> "$JSOS_TEST/.job-search/runs/cron.log" 2>&1
echo "exit: $?"
tail -8 "$JSOS_TEST/.job-search/runs/cron.log"          # the run summary, exactly as cron would log it
ls -t "$JSOS_TEST/.job-search/reports/"*.md | head -1   # a digest exists / was refreshed
```
**Expected:** exit **0**; **no prompt** (headless); a `reports/<date>-digest.md` with the **same shape** as T5.1
(Run health line, counts line, Strong→Moderate→Weak); the summary lands in `cron.log`. Fresh matches **or** a clean
"No NEW postings" dedup digest are both passes (dedup if T5.1 already searched this workspace); 0 live results →
§0.4 fallback.
**Cross-check** the command equals the T9.1 daily line (sans schedule prefix + log redirect):
`python3 "$JSOS/scripts/osctl.py" schedule-line --frequency daily --workspace "$JSOS_TEST/.job-search"`.
**Result:** ⬜

### T5.5 Non-healthy digest shape — `blocked` must replace the body — 👤 (fake shim)
A blocked run must write a digest whose body is the **named error + fix**, not a cheery summary. Drive the
deterministic `down` scenario and read the digest:
```bash
SH5=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$SH5" >/dev/null
PATH="$SH5/_bin:$PATH" JOBSEARCH_FIXTURES="$JSOS/tests/fixtures" JOBSEARCH_TEST_SCENARIO=down \
  claude --plugin-dir "$JSOS" -p "/job-search-run --workspace $SH5"; echo "exit: $?"
cat "$SH5/reports/"*.md 2>/dev/null; rm -rf "$SH5"
```
**Expected:** writes a `runs/<id>.json` with `run_health: blocked` naming **E-SERVICE-DOWN**, so the next `/job-search` home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?`; the digest's Run-health line reads exactly **`Run health: blocked (action needed)`**
(the full set is `healthy | partial (N errors) | degraded (LinkedIn flaky) | blocked (action needed)`); the body is
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
  claude --plugin-dir "$JSOS" -p "/job-search-run --workspace $T3/.job-search"
echo "exit: $?"; rm -rf "$T3"
```
*(If your key is in `~/.agent-data/config.json`, temporarily test in a shell where it isn't, or skip — the eval covers it.)*
**Expected:** halts with **E-NO-AUTH** (names the `export AGENT_DATA_API_KEY=…` fix); nothing pulled; writes a `runs/<id>.json` with `run_health: blocked` naming **E-NO-AUTH**, so the next `/job-search` home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?`.
**Result:** ⬜

### T7.2 E-NO-AGENT-DATA — 👤
```bash
T4=$(mktemp -d)
PATH="/usr/bin:/bin" JOBSEARCH_OS_HOME="$T4" JOBSEARCH_OS_REGISTRY="$T4/reg.json" \
  claude --plugin-dir "$JSOS" -p "/job-search-run --workspace $T4/.job-search"  # agent-data not on this PATH
echo "exit: $?"; rm -rf "$T4"
```
**Expected:** **E-NO-AGENT-DATA** naming the `npm install -g agent-data` fix; writes a `runs/<id>.json` with `run_health: blocked` naming **E-NO-AGENT-DATA**, so the next `/job-search` home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?`. *(Skip if `python3`
isn't on the trimmed PATH on your system — rely on the eval; or add the python dir to PATH.)*
**Result:** ⬜

### T7.3 E-NO-CONFIG — covered by T5.3. **Result:** ⬜
### T7.4 E-NO-PREFERENCES — 👤
```bash
T5=$(mktemp -d); mkdir -p "$T5/.job-search/runs" "$T5/.job-search/reports"
cp "$JSOS/templates/config.example.yaml" "$T5/.job-search/config.yaml"; : > "$T5/.job-search/preferences.md"; : > "$T5/.job-search/jobs.jsonl"
claude --plugin-dir "$JSOS" -p "/job-search-run --workspace $T5/.job-search"; echo "exit: $?"; rm -rf "$T5"
```
**Expected:** **E-NO-PREFERENCES** naming `/job-preference-interview`; nothing pulled; writes a `runs/<id>.json` with `run_health: blocked` naming **E-NO-PREFERENCES**, so the next `/job-search` home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?`.
**Result:** ⬜

### Fake-shim only (deterministic error injection — cannot be forced on the live API)

Shared setup for T7.5–T7.10:
```bash
SH=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$SH" >/dev/null
export FAKE="PATH=$SH/_bin:$PATH JOBSEARCH_FIXTURES=$JSOS/tests/fixtures"
# run pattern:  env $FAKE JOBSEARCH_TEST_SCENARIO=<scenario> claude --plugin-dir "$JSOS" -p "/job-search-run --workspace $SH"
```
Run each by giving Claude: *"run /job-search-run --workspace $SH with the fake shim (PATH=$SH/_bin:$PATH,
JOBSEARCH_FIXTURES=$JSOS/tests/fixtures, JOBSEARCH_TEST_SCENARIO=<scenario>) and show the digest + exit code."*

| Test | scenario | Expected | Result |
|---|---|---|---|
| T7.5 **E-QUOTA** | `quota` | plain-language quota note (lower frequency / upgrade) — **no credit math**; no retry; existing matches intact; writes a `runs/<id>.json` with `run_health: blocked` naming **E-QUOTA**, so the next `/job-search` home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?` | ⬜ |
| T7.6 **E-SERVICE-DOWN** | `down` | "service down" digest, Run health blocked; **no** search/get-posting calls; writes a `runs/<id>.json` with `run_health: blocked` naming **E-SERVICE-DOWN**, so the next `/job-search` home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?` | ⬜ |
| T7.7 **E-UPSTREAM-STRETCH** | `stretch` | retries the 502 with backoff, stops after two consecutive failed queries; writes a **partial** digest (Run health `partial (N errors)`); doesn't crash | ⬜ |
| T7.8 invalid-pair (non-error) | `invalid-pair` | no retry; summary-only judgment + "detail link expired" footnote; `detail_read:false`; run completes, exit 0 | ⬜ |
| T7.9 degraded (non-error) | `degraded` | Run-health line reads `degraded (LinkedIn flaky)`; caps detail reads (~2); still produces matches; exit 0 | ⬜ |
| T7.10 zero / all-known | `zero-empty` | "Searches ran but returned 0 results — broaden keywords"; exit 0. (All-known: pre-seed jobs.jsonl with the happy ids → "No NEW postings.") | ⬜ |

```bash
rm -rf "$SH"
```

The next three reuse the same fake shim and are fully **offline** (no credits). Each builds its own throwaway
workspace, so they don't depend on the shared `$SH` above.

### T7.11 E-CONFIG-VERSION — a config from a newer version halts — 👤
```bash
SHV=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$SHV" >/dev/null
sed -i.bak 's/^version: 1/version: 2/' "$SHV/config.yaml"      # pretend a newer skill wrote it
PATH="$SHV/_bin:$PATH" JOBSEARCH_FIXTURES="$JSOS/tests/fixtures" \
  claude --plugin-dir "$JSOS" -p "/job-search-run --workspace $SHV"; echo "exit: $?"; rm -rf "$SHV"
```
**Expected:** **E-CONFIG-VERSION** ("written by a newer version … update the job-search-os skills"); HALT at
preflight (no `search-jobs`/`get-posting`); writes a `runs/<id>.json` with `run_health: blocked` naming **E-CONFIG-VERSION**, so the next `/job-search` home view surfaces it; the headless `claude -p` process returns **0**, so do not assert on `$?`.
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
schedule:
  frequency: "daily"
  time: "08:00"
YAML
PATH="$SHB/_bin:$PATH" JOBSEARCH_FIXTURES="$JSOS/tests/fixtures" JOBSEARCH_TEST_SCENARIO=bad-query \
  claude --plugin-dir "$JSOS" -p "/job-search-run --workspace $SHB"; echo "exit: $?"
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
  claude --plugin-dir "$JSOS" -p "/job-search-run --workspace $SHD"; echo "exit: $?"
cat "$SHD/reports/"*.md 2>/dev/null; rm -rf "$SHD"
```
**Expected:** the `502 detail_fetch_failed` is **retryable** → retries with backoff, then **gives up on the detail**
and judges from the **summary** (footnote that the detail couldn't be read); `detail_read:false` for that posting;
the run **completes, exit 0** (a footnote, not a failure).
**Result:** ⬜

---

## 8. Never-clobber / data safety

### T8.1 Adopt an existing workspace without overwriting — 👤 + 🤖
```bash
T6=$(mktemp -d)
mkdir -p "$T6/job-search"                                  # LEGACY (visible) location
cp "$JSOS/templates/config.example.yaml" "$T6/job-search/config.yaml"
printf 'SENTINEL-PREFS\n' > "$T6/job-search/preferences.md"
printf '{"event":"evaluated","source_id":"SENTINEL-JOB","status":"new"}\n' > "$T6/job-search/jobs.jsonl"
shasum -a 256 "$T6/job-search/"{preferences.md,jobs.jsonl,config.yaml}     # record
```
Launch Claude with `JOBSEARCH_OS_HOME="$T6"` (no registry yet) and say **"/job-search"**.
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

## 9. Scheduling artifacts

### T9.1 Cron lines — ⚙️
```bash
for f in hourly every-2-hours every-6-hours daily weekly; do
  python3 "$JSOS/scripts/osctl.py" schedule-line --frequency "$f" --time 08:00 --workspace "$JSOS_TEST/.job-search"
done
```
**Expected:** `0 * * * *`, `0 */2 * * *`, `0 */6 * * *`, `0 8 * * *`, `0 8 * * 1` respectively, each followed by
`cd "…/.job-search" && claude -p "/job-search-run" >> "…/runs/cron.log" 2>&1`.
**Result:** ⬜

### T9.2 launchd plist is well-formed — 👤 *(macOS only; on Linux skip — use cron, T9.1)*
```bash
python3 "$JSOS/scripts/osctl.py" launchd-plist --frequency daily --time 08:00 --workspace "$JSOS_TEST/.job-search" | xmllint --noout - && echo "valid plist"
```
**Expected:** `valid plist`; contains `StartCalendarInterval` with Hour 8.
**Result:** ⬜

### T9.3 (Opt-in, reversible) real cron round-trip — 👤
*Only if you want to verify a real install.* Do it in a way you can undo: install the generated line, confirm one
run writes to the log, then **remove it**. Skip if you'd rather not touch your crontab.
**Result:** ⬜ / N/A

### T9.4 `/loop` scheduling — no privileged write — 🤖 + 👤
`/loop` keeps a Claude session open instead of installing cron/launchd. Say: **"set it up with /loop instead —
keep Claude open and loop it."**
**Expected:** Claude prints the loop line **`/loop <frequency> /job-search-run`** (using your configured
frequency) and records the mechanism in the registry — **without** writing any crontab line or launchd plist.
**Verify (👤):**
```bash
python3 "$JSOS/scripts/osctl.py" schedule-status   # {"installed": true, "mechanism": "loop", ...}
crontab -l 2>/dev/null | grep -c job-search-run     # 0 — nothing installed in cron
```
**Result:** ⬜

---

## 10. Philosophy guardrails (cross-cutting) — 👤

### T10.1 No numeric scoring or credit math in any output **file** — 👤
Skim every digest/brief/config Claude produced during testing (under `$JSOS_TEST` and any `$SH*`/`$T*` dirs you
kept). This covers files; **chat replies** are covered by T10.2.
```bash
grep -rniE "0-100|0–100|fit score|[0-9]+ ?points|category weight|\$[0-9]|credits?" "$JSOS_TEST" 2>/dev/null
```
**Expected:** the only cost language anywhere is the reactive **E-QUOTA** wording; **no** numeric relevance score,
weight, points, or dollar/credit figure in any digest or brief.
**Result:** ⬜

### T10.2 Philosophy holds in CHAT, not just files — 🤖 + 👤
The no-numbers / frequency-only rule must hold in Claude's **replies**, not only in saved files. Capture a few
scripted probes headlessly (two of them try to *elicit* a violation) and grep the transcript:
```bash
PROBES="$JSOS_TEST/probes.txt"; : > "$PROBES"
for q in "how do I control how much this costs?" \
         "which of these matches is the best fit — rank them for me?" \
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

**Expected (read the transcript):** Default/unsolicited output stays band-only with no cost
math. The cost answer leads with **frequency** (and may explain that more queries × higher
limit × more often = more usage); it must not invent a per-call **dollar/credit** figure or
a budget knob. For the **explicit** "fit score out of 100" request, honoring it in the reply
is acceptable (the agent is flexible) **as long as** it (a) notes scoring is non-default and
qualitative bands are the real signal, and (b) does NOT persist the score into any
digest/brief/`config.yaml`/`jobs.jsonl`. A ❌ is: a numeric score or budget figure in
**unsolicited** output, OR an on-request score written into a saved artifact.
**Result:** ⬜

---

## 11. Docs accuracy — 👤

### T11.1 README ↔ reality
Open `$JSOS/README.md`: the install commands match what you ran (`claude --plugin-dir`, `/plugin install
job-search-os@agent-data` gated "once published"); the troubleshooting table matches `shared/references/errors.md`
(spot-check 3 rows).
**Result:** ⬜

### T11.2 Sample digest ↔ real digest
Compare `$JSOS/examples/sample-digest.md` to a real digest from T5.1 — same structure (header, Run health, counts
line, Strong/Moderate/Weak, Filtered-out, footnotes).
**Result:** ⬜

---

## 12. Full eval regression — 🤖

Ask Claude, for each skill, to **run its evals** (the `harness` in `skills/<skill>/evals/evals.json`; they use the
fake-agent-data shim, so zero real credits):
- `evaluate-job-fit` (3) · `job-search-run` (11) · `job-preference-interview` (3) · `job-search` (5).
**Expected:** all pass; outputs are philosophy-clean.
**Result:** ⬜

---

## 13. Config command surface (PLANNED — pending build) — 🤖

Today all configuration is **conversational** (you chat; Claude edits `config.yaml`). Dedicated config **slash
commands** — an `/effort`-style surface, e.g. `/job-search-frequency hourly` — are **planned but not built yet**
(see `TODOS.md` → `TODO-CONFIG-COMMANDS`). These tests are **pending-build**: they are **N/A** today and only go
green once the commands ship. A green run here must never imply the commands exist.

| Test | Planned command | Expected once built | Result |
|---|---|---|---|
| T13.1 | `/job-search-frequency <hourly…weekly>` | sets `schedule.frequency` to the same value the conversational path (T4.3) would; `version: 1` intact; no cost math | ⬜ pending-build |
| T13.2 | `/job-search-add-query "<keywords>" "<location>"` | appends a `queries[]` item identical to T4.2's conversational result | ⬜ pending-build |
| T13.3 | `/job-search-schedule off` | turns the schedule off **and clears the registry marker** (also resolves `TODO-SCHED-OFF`) | ⬜ pending-build |

**Acceptance for each:** the command produces the **same** `config.yaml`/registry edit as its conversational
equivalent (parity), errors on bad input with a named `E-*`, and never introduces a numeric/budget field. Until
built, mark **N/A (pending build)**.

---

## Acceptance checklist (sign-off)

- ⬜ Install: plugin validates `--strict`; loads via `--plugin-dir`; loose-skills self-contained (§1)
- ⬜ Isolation pre-flight passes; canonical persona set before any LIVE test (§0.2, §0.4)
- ⬜ First-run `/job-search` onboards end-to-end and shows **real live matches**; TTFV recorded < ~5 min (T2.1)
- ⬜ Interview produces a **prose** brief; the 0–100 rubric is gone; import + rubric→prose work (§3)
- ⬜ Returning `/job-search` shows home incl. **failure-states** (no-runs, blocked, stale-brief); **all config changes work conversationally** — add/**edit**/**remove** query, frequency, schedule off, prefs, status — and survive **phrasing variety** (§4)
- ⬜ **Headless + live** run (the cron path) writes a correct digest; live run **dedups** on re-run; **headless** first-run → E-NO-CONFIG (names the error, exits 0, no `runs/` record); a `blocked` run writes `run_health: blocked` naming the `E-*` so the home view surfaces it (process exits 0) (§5)
- ⬜ Relevance is **qualitative** (relevant + weak/moderate/strong + reasoning); dealbreakers reject; unknowns flag, never reject (§6)
- ⬜ Every blocked path is a **named `E-*`** with its fix — auth, no-CLI, no-config, **config-version**, no-prefs, quota, down, stretch, **bad-query**, invalid-pair, detail-fetch-failed, degraded, zero/all-known (§7)
- ⬜ **Never clobbers** real data; adopts an existing workspace byte-identically; real `~/.job-search`/`~/job-search`/crontab untouched (§8)
- ⬜ Scheduling artifacts correct (cron lines per frequency; valid launchd plist; **`/loop`** sets `mechanism:loop` with no privileged write) (§9)
- ⬜ **No numeric scores/weights/credit knobs** in files **or chat**; frequency is the only cost lever (§10)
- ⬜ Docs match reality (install commands, error table, sample digest) (§11)
- ⬜ Full regression green: `pytest` (**62**; gate on `0 failed`) + all four skills' evals (§0.3, §12)
- ⬜ Planned config slash-command tests are marked **N/A (pending build)**, not green (§13)

**Teardown:** `rm -rf "$JSOS_TEST"` and any `$T*`/`$SH*` dirs you kept.

---

## Maintainer notes (fill in each pass) — DX feedback loop
Capture reality so the next review can compare against it (this is the boomerang signal — don't skip it):
- **TTFV (T2.1):** ______ s  ·  **Smoke-subset wall-clock:** ______ min  ·  **Full-pass wall-clock:** ______ min
- **Where did onboarding / the home view confuse you?** (the one thing you'd fix first) ______
- **Any T4.7 phrasing Claude misread?** ______
- **New product gaps found** (add to `TODOS.md`): ______
