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

- **Scripted mechanics** — `tests/test_mechanics_scripts.py` (483 tests, `python3 -m pytest tests/test_mechanics_scripts.py -q --collect-only`; run them with `pytest -q tests/test_mechanics_scripts.py`): the deterministic state operations the skills call out to — opening and closing a run, workspace discovery, schedule-line composition, dedup, the jobs.jsonl event-line append, recording one agent-data response, queueing a detail read and listing the queue, recording a judgment, and reading a run's counts and its matches back out of the log — each driven through `sh` against a temp fixture. One case runs `sh -n` and strict `dash -n` over every bundled shell script, wherever its owning skill keeps it, so none of them is quietly bash-only: `ls skills/*/scripts/*.sh | wc -l` gives 15, and `ls skills/*/scripts/*.awk | wc -l` gives 9 more `awk` programs those scripts hand off to. `validate-workspace.sh` is syntax-checked here and behavior-tested in the next bullet.
- **Workspace validator** — `tests/test_validate_workspace.py`: `skills/job-search-runbook/scripts/validate-workspace.sh` run against workspaces built per case. It checks config.yaml's required keys, `---` front matter with ISO `created_at`/`updated_at` in preferences.md, the run-record shape and UTC `Z` timestamps, and — with `--post-close` — that no started-marker or scratch directory survived the run. These file rules used to live only as prose in the skills; the script is now what enforces them.
- **Hardened skill evals** — `python3 scripts/eval_harness.py --root .` validates every `skills/*/evals/evals.json` for structural coherence (contiguous ids, well-formed scenarios, a **discovery** scenario per skill for the four overlap pairs, **stochastic** scenarios carrying `reps ≥ 5` + a **no-guidance control** arm, and — on milestone/liveness scenarios — a **fixed-time fixture** (`fixed_time`: a deterministic reference clock with a valid ISO `now` and a `checks` subset of `milestone`/`liveness`) so those derivations never read the wall clock) and rejects the pinned pack-authored `gpt-5*` literal regression family. Legacy version-1 selectors may resolve through host tier roles; version-2 test and runtime setup injects an exact host-resolved identifier. Pack-authored fixtures and prose never hard-code that identifier. `tests/test_eval_harness.py` unit-tests the rep-aggregation (pass-rate + variance), the control-delta, the fixed-time-fixture validation, and the **unique run marker** enforcement — the off-CI artifact check (`scripts/eval_harness.py --check-artifacts`) accepts a per-run `run_marker` and, for any `run_marked` assertion, requires the artifact to carry it, so a stale artifact left in a reused workspace can never create a false pass.
- **Release integrity** — `scripts/check_release_integrity.py`: version-sync across the 7 manifests (six JSON plus the Hermes `plugin.yaml`).

Verifying a host-specific action such as scheduling is now a **runtime config-time canary** check, replacing the deleted per-host **structural adapter validation**.

How the skills *behave* is graded by live behavior evals the maintainer runs against the real Job Postings API before a release. They need an API key, cost money, and are not in this repository. No test asserts sentences of documentation prose; the suites that did were retired on 2026-07-30 in favor of the evals plus `validate-workspace.sh`. Two pytest files still open a reference file, and neither reads it for wording: `tests/test_reference_resolution.py` follows every path a SKILL.md names, from each host's install view, and fails on a dangling one, and `tests/test_usage_context_contract.py` checks that pricing and metering facts have exactly one owning file (the `agent-data-reference` skill).

What stays a **labeled TRANSITIONAL residual** (👤/🤖, driven by hand): the **behavioral cross-host matrix** — actually running a skill end-to-end on each of the eight hosts that are **not installable on the CI runner** (Codex/Cursor/opencode/Gemini/Copilot/Droid/Pi/Hermes Agent), and the **N ≥ 5 stochastic eval reps** (the discovery/verdict/injection/merge scenarios run against the shim to record real pass-rate + variance + the control delta). These are the **off-CI live-harness step** — expected, not a gap: CI proves the scenarios are *well-formed*; the behavioral reps prove they *pass*, and shrink as hosts become installable. A green structural gate must never be read as a passed behavioral matrix.

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
uses — the `job-search-runbook` skill):
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
**Expected:** `951 passed` **and `0 failed`** — treat **`0 failed`** as the real gate. The count moves in both
directions: it grows when tests are added, and it fell three times as the 2026-07-30 overhaul landed. First
688 → 547, when the documentation-prose suites were retired. Then, on 2026-07-31, **554 → 377 → 374 → 372**:
554 was the measured count once tasks 5–10 had added their own tests; deleting the shared reference corpus and
the structures it defined (the exact-model binding sidecar, the version-1 migration, the lifecycle ledger,
the eight-state schedule health) took the tests that read them with it (**−177**); trimming the scheduler
shim to the contracts that survive took three more (**−3**); retiring the `internal_record` assertion
surface, which required a run record to carry a raw `E-*` code no shipped file writes any more, replaced its
three tests with one that rejects the retired name (**−2**). It then grew on the same day as the skill
locality restructure landed: **372 → 385 → 408**, the co-location gates first and then the frontmatter and
locality suite that came with promoting the two shared references to skills. It grew four more times as
the locality proof and its gates landed: **408 → 411 → 418 → 421 → 429** — the eval-case lint gained the
second case shape, a list of trigger phrases in place of one prompt (**+3**), and
`test_reference_resolution.py` gained three rounds of checks that reject a pointer naming a file in the
reference skill's own directory, each round adding the written forms the previous rule let pass
(**+7**, **+3**, **+8**). It then more than doubled as the counting scripts landed, and moved twice more
after that: **429 → 927 → 937 → 939 → 937**. The scripts that record a run's events and read its numbers
back out brought their own unit tests with them (**+498**, most of it in `test_mechanics_scripts.py`, which
went from 28 tests to 439); the home view's counter added the last of those scripts (**+10**); making that
counter report a posting none of its count lines accounted for added two (**+2**); and replacing the home
card's status counts with what the filtering found took out the two cases that existed only for a status
(**−2**). It then grew four more times as the fixes from the 2026-08-08 whole-branch review landed, one
step per fix: **937 → 948 → 967 → 976 → 1037**. Guarding every append site against a log that ends without
a newline added eleven (**+11**); counting an opening found in two cities once, and naming the other places
on the row that survives, added nineteen (**+19**); matching a source name as text rather than as a search
pattern, and dropping `find-judgment.awk`'s run scope, added nine (**+9**); and making the eval harness
refuse to report success while a scheduled job it did not remove is still installed added sixty-one
(**+61**, most of it in `test_eval_harness.py`, which went from 62 tests to 116). Each figure is
`python3 -m pytest tests/ -q --collect-only` at that commit — `b3ac24d`, `9523321`, `08baee7`, `8e849eb`,
`7d6fbba`, `faa3645`, `f785765`, `0e5f40b`, `2cd027e`. It then fell once more, to **951**, when the
top-level `evals/` stopped being tracked on 2026-08-10 and `9bf0536` dropped the tests that read it:
all of `test_eval_cases.py` (**−32**) and the `evals/run_eval.py` section of `test_eval_harness.py`
(**−54**, taking that file from 116 tests to 62). For those figures, run the same `--collect-only`
command at `5950e88` and at `9bf0536`, on the whole suite and on `tests/test_eval_harness.py`.
Update the number here whenever it changes. Covers the doc linter, the philosophy guard,
the release-integrity checks, the scripted-mechanics unit tests, the workspace validator
(`test_validate_workspace.py`), the **eval-scenario validator +
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
bug closes the run `blocked`, mis-shapes the digest, or crashes; a quiet market completes healthy and says "0
results — broaden keywords" (T7.11). Only the former is a ❌.

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
**Expected:** `0 failed` — the shared contracts live **once**, in the `job-search-runbook` and
`agent-data-reference` skills, and each of the other five invokes whichever of the two it needs and
nothing outside them; there are **no per-skill bundled copies**.
Nothing is generated into `skills/`, so there is no build step to re-run.
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
last run health), the latest digest summary (date + counts), a **Matches** block reading
`<n> relevant postings found · <k> need your confirmation · <f> filtered out`, and conversational
quick-actions. The three numbers are the `relevant`, `to_confirm` and `filtered` values that
`skills/job-search/scripts/posting-counts.sh <workspace>/jobs.jsonl` prints.
**Result:** ⬜

### T4.2 Add a query conversationally — 🤖
Say: **"add a query for 'staff machine learning engineer' in 'Remote'."**
**Verify (👤):** `cat "$JSOS_TEST/.job-search/config.yaml"` → a new `queries[]` entry with those keywords/location,
`enabled: true`, `version: 2` intact, **no budget/score fields added**.
**Result:** ⬜

### T4.2b Edit a query conversationally — 🤖
Say: **"change the location on the staff ML query to 'United States'."**
**Verify (👤):** `config.yaml` → that **same** `queries[]` item's `location` is updated; its `id`/`keywords`
unchanged, other queries untouched, `version: 2` intact.
**Result:** ⬜

### T4.2c Remove a query conversationally — 🤖
Say: **"drop the staff ML query."**
**Verify (👤):** `config.yaml` → that item is gone; remaining queries intact; `version: 2` intact.
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

### T4.7 Conversational robustness — the interface IS the product — 🤖
The config interface is natural language, so test more than one phrasing per action. For each cell, send the
phrasing and record whether Claude makes the **right** edit — or asks **one** clarifying question when genuinely
ambiguous. It must never silently do the wrong thing; **`version: 2` stays; no score/budget fields ever appear.**

| Action | Multi-intent | Oblique | Negative / exclude | Typo / loose |
|---|---|---|---|---|
| Frequency | "add an ML query **and** make it hourly" | "stop pulling so often" | — | "make it evry day" |
| Query | (multi-intent above) | "also keep an eye out for staff roles" | "I don't want the onsite ones" | "ad a querey for data eng" |
| Preferences | "make it fully remote **and** drop anything under $180K" | "I keep seeing crypto roles" | "I don't want contract work" | "make it fully remoet" |

**Expected, per cell:** correct `config.yaml`/`preferences.md` edit **or** one targeted clarifying question
(e.g. "by 'so often' do you mean hourly→daily?"); multi-intent applies **both** changes; negative phrasings
**exclude** (add an exclusion to the query, or a dealbreaker to the brief), never add the thing.
`version: 2` preserved throughout. A preference that holds across postings goes to `preferences.md`
through `job-preference-interview`, never to `jobs.jsonl` — only a run appends to that log.
**Verify (👤):** `cat "$JSOS_TEST/.job-search/config.yaml"` after the multi-intent + typo rows;
`grep updated_at "$JSOS_TEST/.job-search/preferences.md"` after the preferences row — it refreshes, and
the new constraint reads in the brief's prose.
**Result:** ⬜

### T4.8 Home failure-states — don't bury problems — 🤖 + 👤
The healthy home is T4.1; these are the states the front door
([`skills/job-search/SKILL.md`](skills/job-search/SKILL.md), the home-view step) must render specifically.
Build each, then say **"/job-search:job-search"**:
- **No runs yet** (workspace exists, no digest): complete onboarding but **decline** the sample run (or
  `rm "$JSOS_TEST/.job-search/reports/"*.md`). → Home says *"No runs yet — want me to run your first search
  now?"*, not an empty digest block.
- **Last run blocked:** seed a record whose run stopped early, then open home:
  ```bash
  mkdir -p "$JSOS_TEST/.job-search/runs"
  printf '{"close_state":"blocked","run_health":"degraded","stopped_by":"the monthly allowance is spent"}\n' \
    > "$JSOS_TEST/.job-search/runs/2099-01-01T00-00-00Z.json"
  ```
  → Home says the last run stopped because the monthly allowance is spent, points at the billing page, and
  says existing matches are unaffected — it does **not** bury the failure under a cheery summary.
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

### T5.3 Headless first-run with no workspace — 👤
```bash
T2=$(mktemp -d)
JOBSEARCH_OS_REGISTRY="$T2/absent.json" JOBSEARCH_OS_HOME="$T2" \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run"     # no --workspace, empty sandbox
echo "exit: $?"; rm -rf "$T2"
```
**Expected:** the reply says there is no job search set up yet and names the job-search skill as the way to
set one up; it makes no `agent-data` calls. Nothing is written under `$T2` — with no workspace there is
nowhere to put a run record, and the failure stays visible because the next job-search visit routes to
onboarding. The process exits **0** (do not assert non-zero).
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
**Cross-check** `/loop` runs this same skill headlessly each interval — daily composes to
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
**Expected:** the three blocked-close conditions from §7, with the dead service as the cause. The digest's
health line reads **`Run health: degraded`** and its body says the service is unreachable and the next
scheduled run will retry — **not** a match list. `run_health` is one word: `healthy` when every search
answered and every candidate reached a judgment, `degraded` on every other close, a blocked one included.
What stopped the run is carried by `close_state` plus the digest's own wording, not by a code.
(The degraded digest shape is pushed harder in T7.7/T7.9.)
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

## 7. Blocked and degraded paths (no silent failures)

Every test in this section grades the same three observable things, so read this once instead of re-reading
it per row. There is no error-code catalogue any more — nothing to look a code up in, and no code to assert
on. What a blocked run owes the user is:

Below, `$WS` stands for whichever throwaway workspace the row built (`$T3`, `$SH`, and so on).

1. **A closed run record.** `runs/<run_id>.json` exists, with `close_state: blocked` and
   `run_health: degraded`. Read it: `cat "$WS/runs/"*.json`. The record is what the *next* front-door visit
   reads, so a scheduled run that failed overnight is named the next morning — that is the whole point of
   writing it before stopping.
2. **A digest that says what stopped it.** `reports/<date>-digest.md` leads with `Run health: degraded`,
   and its body is the cause and the fix in plain words, not a match list and not a cheery summary. Grade
   the sentences: would a user who read only this know what happened and what to do?
3. **No leftovers.** `"$JSOS/skills/job-search-runbook/scripts/validate-workspace.sh" "$WS" --post-close <run_id>`
   exits 0 and prints nothing — the started-marker and the scratch directory are gone even though the run
   stopped early.

**Condition 3 only applies where the rest of the workspace is valid.** The validator grades the whole
workspace, not just the run's leftovers, so a row that deliberately seeds a broken file will fail it on
that file no matter how cleanly the run closed. Measured on T7.4's seed (a workspace from
`setup-workspace.sh` with `preferences.md` emptied):

```
$ skills/job-search-runbook/scripts/validate-workspace.sh "$WS" --post-close 2026-07-30T09-00-00Z
INVALID preferences.md front-matter
exit=1
```

That is the validator working correctly, not the run failing. Each row below says which conditions it
grades; where a row grades 1 and 2 only, check the leftovers by hand instead —
`ls -a "$WS/runs/"` shows no `.started-*` and no `.scratch/`.

Two things that are **not** pass conditions. The headless `claude -p` process returns **0** even on a
blocked run (a skill cannot set the host process's exit status), so never assert on `$?`. And no exact
wording is required: two runs may explain the same block in different sentences and both pass, as long as
the cause and the fix are there.

A run that *finishes* its work while something went wrong is a different close: `close_state: complete`
with `run_health: degraded`. Those rows say so.

### Live-triggerable

### T7.1 The CLI is not authenticated — 👤
```bash
T3=$(mktemp -d); cp -R "$JSOS_TEST/.job-search" "$T3/.job-search" 2>/dev/null || true
AGENT_DATA_API_KEY="" JOBSEARCH_OS_HOME="$T3" JOBSEARCH_OS_REGISTRY="$T3/reg.json" \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $T3/.job-search"
echo "exit: $?"; rm -rf "$T3"
```
*(If your key is in `~/.agent-data/config.json`, temporarily test in a shell where it isn't, or skip — the eval covers it.)*
**Grades conditions 1, 2, and 3.**
**Expected:** the cause is the missing API key and the fix is the exact command that sets one
(`agent-data init --api-key …`, or exporting `AGENT_DATA_API_KEY`). Nothing is pulled — no `search-jobs`,
no `get-posting`.
**Result:** ⬜

### T7.2 The CLI is not installed — 👤
The workspace has to be real, or there is nowhere to write the record this row grades. Build one, then hide
`agent-data` by putting **only** `claude` on the PATH:
```bash
T4=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$T4/.job-search" >/dev/null
mkdir -p "$T4/bin"; ln -s "$(command -v claude)" "$T4/bin/claude"
command -v agent-data          # note where it really is — the mask below must not include that directory
PATH="$T4/bin:/usr/bin:/bin" JOBSEARCH_OS_HOME="$T4" JOBSEARCH_OS_REGISTRY="$T4/reg.json" \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $T4/.job-search"
echo "exit: $?"; cat "$T4/.job-search/runs/"*.json; rm -rf "$T4"
```
`agent-data` commonly sits in the same directory as `claude` (both under `~/.local/bin` on this machine),
which is why the symlink exists rather than a trimmed `$PATH` — dropping the directory would take `claude`
with it. If your `claude` needs a runtime that isn't in `/usr/bin` or `/bin`, add that directory too; the
only thing this row requires is that `agent-data` is absent.
**Grades conditions 1, 2, and 3.**
**Expected:** the cause is the missing `agent-data` command and the fix is `npm install -g agent-data`.
*(The masked PATH needs no python3 — the skills are zero-dependency; see T9.4.)*
**Result:** ⬜

### T7.3 No workspace at all — covered by T5.3. Grades neither 1 nor 3: there is no workspace, so there is nowhere to write a record and nothing to validate. **Result:** ⬜
### T7.4 The preferences brief is empty — 👤
```bash
T5=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$T5/.job-search" >/dev/null
: > "$T5/.job-search/preferences.md"
claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $T5/.job-search"; echo "exit: $?"
ls -a "$T5/.job-search/runs/"; rm -rf "$T5"
```
**Grades conditions 1 and 2 only.** The seed empties `preferences.md` on purpose, so the validator will
report `INVALID preferences.md front-matter` and exit 1 whatever the run did — that is the broken seed, not
a leftover. Check the leftovers from the `ls -a` instead: no `.started-*` and no `.scratch/`.
**Expected:** the cause is the empty brief — there is nothing to judge postings against — and the fix names
the job-preference-interview skill. Nothing is pulled.
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

`setup-workspace.sh` builds `$SH` from the repo templates, so every file in it is valid and **every row
below grades all three conditions**, plus whatever its own Expected column adds. A row marked "blocked
close" ends `close_state: blocked` / `run_health: degraded`; the rest complete.

| Test | scenario | Expected | Result |
|---|---|---|---|
| T7.5 monthly allowance spent | `quota` | **blocked close.** The digest leads with the spent allowance and the billing page as the fix, and states the run's actual prior metered calls — zero here, because the very first attempt was rejected. The rejected attempt is not counted as metered. No retry, no invented balance or charge. Postings already in `jobs.jsonl` are untouched | ⬜ |
| T7.6 service unreachable | `down` | **blocked close.** No `search-jobs` and no `get-posting` calls at all. The digest says the service is unreachable and that the next scheduled run will retry, instead of a match list | ⬜ |
| T7.7 every source keeps failing | `stretch` | retries the 502 with backoff, then stops searching a source after two consecutive failed queries against it (the shim fails every source, so all stop). The digest reads `Run health: degraded` and names every source as unavailable. It does not crash | ⬜ |
| T7.8 stale detail links | `invalid-pair` | no retry — a dead id/URL pair is not going to become live. Those postings are judged from their summaries with a "detail link expired" footnote and `detail_read:false`. The run **completes** (`close_state: complete`), exit 0 | ⬜ |
| T7.9 flaky sources, run still finishes | `degraded` | the digest's health line reads `degraded` and names the flaky sources as what degraded the run, and notes that this run's results may be incomplete. Promising matches are still read in full — nothing caps detail reads here — and matches are still produced. `close_state` stays **`complete`**: the run finished its work | ⬜ |
| T7.10 many promising postings | `many-promising` | every promising posting is evaluated; if the host hits a subagent or thread limit, it continues in rolling batches or falls back to working the list in order. Hitting that limit is not by itself a reason for `run_health: degraded` | ⬜ |
| T7.11 zero results / all already seen | `zero-empty` | completes healthy: "Searches ran but returned 0 results — broaden keywords", exit 0. (All-known variant: pre-seed `jobs.jsonl` with the happy ids → "No new postings — you've already seen all N of these.") | ⬜ |

```bash
rm -rf "$SH"
```

The next two reuse the same fake shim and are fully **offline** (no credits). Each builds its own throwaway
workspace, so they don't depend on the shared `$SH` above.

*(There is no config-version test any more. Nothing in the pack halts on a `config.yaml` version it does not
recognise — `validate-workspace.sh` requires `version` to be present and numeric, and that is all. If a
future release reintroduces a schema break, add the test back with it.)*

### T7.12 One malformed query is skipped, the good ones still run — 👤
A rejected query is **non-blocking**: skip it, keep going. Build a workspace with one good and one malformed
query (the `bad-query` scenario rejects only the `INVALID` sentinel location with a `422`):
```bash
SHB=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$SHB" >/dev/null
cat > "$SHB/config.yaml" <<'YAML'
version: 2
workspace:
  preferences_path: "preferences.md"
queries:
  - { id: "good", keywords: "software engineer", location: "United States",   limit: 10, enabled: true }
  - { id: "bad",  keywords: "data engineer",     location: "INVALID-LOCATION", limit: 10, enabled: true }
search:
  sources: ["linkedin"]
  freshness: "any"
schedule:
  frequency: "daily"
  time: "08:00"
YAML
PATH="$SHB/_bin:$PATH" JOBSEARCH_FIXTURES="$JSOS/tests/fixtures" JOBSEARCH_TEST_SCENARIO=bad-query \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $SHB"; echo "exit: $?"
cat "$SHB/reports/"*.md 2>/dev/null; rm -rf "$SHB"
```
**Expected:** the **bad** query is skipped, and the digest says which query was skipped, which parameter the
service rejected (`location`, from `details[].loc`), and that fixing it means editing `config.yaml`. The
**good** query still runs and produces matches. The 422 is **not retried** (`retryable:false`). The run
**completes** — `close_state: complete`, `run_health: degraded` because a query was lost — exit 0.
**Result:** ⬜

### T7.13 A detail read fails — retry, then judge from the summary — 👤
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

### T7.14 A run that died mid-flight is reported, not hidden — 👤
The one blocked-shaped state that isn't an API failure: the previous run was killed before it could close, so
its started-marker is still there and it has no record.
```bash
SHK=$(mktemp -d); bash "$JSOS/skills/job-search-run/evals/files/setup-workspace.sh" "$SHK" >/dev/null
: > "$SHK/runs/.started-2026-07-30T09-00-00Z"; mkdir -p "$SHK/runs/.scratch/2026-07-30T09-00-00Z"
PATH="$SHK/_bin:$PATH" JOBSEARCH_FIXTURES="$JSOS/tests/fixtures" JOBSEARCH_TEST_SCENARIO=happy \
  claude --plugin-dir "$JSOS" -p "/job-search:job-search-run --workspace $SHK"; echo "exit: $?"
ls -a "$SHK/runs/"; rm -rf "$SHK"
```
**Expected:** the run says up front that the last run did not finish, deletes the stale marker and its scratch
directory, and then does this run's work normally — a fresh record and digest, `close_state: complete`. Nothing
is silently swallowed, and no stale `.started-*` survives. This is behavior row B9; the `kill-midrun` eval case
covers the same ground with a real kill.
**Result:** ⬜

### T7.15 Pagination and usage-context matrix — 🤖 + 👤 (fake shim, fully offline)

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
cp "$JSOS/skills/job-search/templates/config.example.yaml" "$T6/job-search/config.yaml"
sed -i.bak -e 's/^version: 2/version: 1/' \
  "$T6/job-search/config.yaml"; rm -f "$T6/job-search/config.yaml.bak"   # an older workspace's config
printf 'SENTINEL-PREFS\n' > "$T6/job-search/preferences.md"
printf '{"event":"evaluated","source":"linkedin","source_id":"SENTINEL-JOB","relevant":true}\n' > "$T6/job-search/jobs.jsonl"
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
**Expected:** the interval each cadence in `skills/job-search/templates/config.example.yaml` maps to —
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
you-go equivalent, and the wording a spent-allowance run uses to point at billing are allowed; an unlabeled or
invented actual charge/account balance is not. No `budget`, `credits`, or `cost` config field or hard monetary
cap appears.
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
Note: `salary`/`$`-amounts (job salary info) and the reactive wording a spent-allowance run uses are allowed
and should not cause a ❌.

**Expected (read the transcript):** Default/unsolicited relevance output stays band-only. The usage answer
leads with actual calls and the outcome levers — frequency, sources, and review depth — and may load accurate
current pricing from the `agent-data-reference` skill when it clearly labels a pay-as-you-go equivalent. It
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
job-search@agent-data` gated "once published"); the troubleshooting table matches what the skills
actually do when a run is blocked (spot-check 3 rows).
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

Then ask Claude, for each of the five suites, to **run its evals** (the `harness` in `skills/<skill>/evals/evals.json`; they use the
fake-agent-data shim, so zero real credits) — **52 scenarios**, counted with
`python3 -c "import json,glob; print(sum(len(json.load(open(p))['evals']) for p in glob.glob('skills/*/evals/evals.json')))"`:
- `evaluate-job-fit` (5) · `job-search-run` (19) · `job-preference-interview` (5) · `job-search` (14) · `job-search-agent` (9).

Each suite now includes a **discovery** scenario (plant the skill among its siblings, drive a naive prompt, assert the
right skill is selected and the confusable sibling is not — the four overlap pairs). The judgment-heavy **stochastic**
scenarios (fit verdicts, injection-resistance, cross-source merge, weighted fair-share selection, baited stop-after-first-match
resistance, and every discovery scenario) are marked to run at **N ≥ 5** with a **no-guidance control** arm — that behavioral
rep loop is the **off-CI live-harness step** (record pass-rate + variance + the control delta with `scripts/eval_harness.py`
`aggregate_reps` / `control_delta`); a single driven pass here is the smoke check. Every **crown-jewel** scenario carries a
baited shortcut **and** the opposite-direction control (e.g. stop-after-early-results vs. complete-the-queue, resume-a-cursor
vs. close-interrupted-and-research), and asserts on **effects** rather than exact prose.
Milestone/liveness scenarios pin a **fixed-time fixture** (a deterministic clock), and each driven run stamps a **unique run
marker** into its artifacts (checked with `--check-artifacts`) so a stale artifact can never create a false pass.
**Expected:** the structural gate is clean; every driven scenario passes; outputs are philosophy-clean.
**Result:** ⬜

---

## 13. Config command surface (PLANNED — pending build) — 🤖

Today all configuration is **conversational** (you chat; Claude edits `config.yaml`). Dedicated config **slash
commands** — an `/effort`-style surface, e.g. `/job-search-frequency hourly` — are **planned but not built yet**
(tracked as `TODO-CONFIG-COMMANDS` in the maintainer's tech-debt tracker). These tests are **pending-build**: they are **N/A** today and only go
green once the commands ship. A green run here must never imply the commands exist.

| Test | Planned command | Expected once built | Result |
|---|---|---|---|
| T13.1 | `/job-search-frequency <hourly…weekly>` | sets `schedule.frequency` to the same value the conversational path (T4.3) would; `version: 2` intact; no cost math | ⬜ pending-build |
| T13.2 | `/job-search-add-query "<keywords>" "<location>"` | appends a `queries[]` item identical to T4.2's conversational result | ⬜ pending-build |
| T13.3 | `/job-search-schedule off` | turns the schedule off **and clears the registry scheduling marker** | ⬜ pending-build |

**Acceptance for each:** the command produces the **same** `config.yaml`/registry edit as its conversational
equivalent (parity), says in plain words what was wrong with bad input and how to fix it, and never introduces
a numeric/budget field. Until built, mark **N/A (pending build)**.

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

### T14.2 Shim multi-source run — 🤖
"Build the eval sandbox (§0.2), export `JOBSEARCH_TEST_SCENARIO=multi-source`, run
job-search-run against the sandbox workspace, and show the digest + jobs.jsonl."
**Expected:** per-source counts breakdown; ashby events carry `"source":"ashby"`; null-date
entries carry a date mark; the first-Ashby-pass footnote is present.
**Result:** ⬜

### T14.3 One source down never blanks the run — 🤖
"Same sandbox, `JOBSEARCH_TEST_SCENARIO=one-source-down`. Run job-search-run; show the digest."
**Expected:** LinkedIn matches land; Run health `degraded` with the digest naming ashby as the source that was lost; outage footnote.
**Result:** ⬜

---

## Acceptance checklist (sign-off)

- ⬜ Install: plugin validates `--strict`; loads via `--plugin-dir`; single-home references resolve (§1)
- ⬜ Isolation pre-flight passes; canonical persona set before any LIVE test (§0.2, §0.4)
- ⬜ First-run `/job-search:job-search` onboards end-to-end and shows **real live matches**; TTFV recorded < ~5 min (T2.1)
- ⬜ Interview produces a **prose** brief; the 0–100 rubric is gone; import + rubric→prose work (§3)
- ⬜ Returning `/job-search:job-search` shows home incl. **failure-states** (no-runs, blocked, stale-brief); **all config changes work conversationally** — add/**edit**/**remove** query, frequency, schedule off, prefs — and survive **phrasing variety** (§4)
- ⬜ **Headless + live** run (the cron path) writes a correct digest; live run **dedups** on re-run; **headless** first-run with no workspace says how to set one up and exits 0 with no `runs/` record; a run that stops early writes `close_state: blocked` with `run_health: degraded`, naming what stopped it so the home view surfaces it (process exits 0) (§5)
- ⬜ Relevance is **qualitative** (relevant + weak/moderate/strong + reasoning); dealbreakers reject; unknowns flag, never reject (§6)
- ⬜ Every blocked path **closes** — a `close_state: blocked` record plus a digest naming the cause and the fix in plain words, no leftovers — for no-auth, no-CLI, no-workspace, empty brief, spent allowance, and service down; and the paths that stop short of blocking (repeated outage, stale detail links, flaky sources, many promising postings, zero results, a malformed query, a failed detail read, a run that died mid-flight) each behave as their row says (§7)
- ⬜ **Never clobbers** real data; adopts an existing workspace byte-identically; real `~/.job-search`/`~/job-search`/crontab untouched (§8)
- ⬜ Scheduling correct (the composed `/loop <interval>` matches the pinned table per frequency; `/loop` sets `mechanism:loop`; **zero-Python user path** proven with python3 masked) (§9)
- ⬜ **No numeric scores/weights, budget config, or invented charge** in files or unsolicited chat; accurate calls-first usage context is labeled, and users control frequency, sources, and review depth (§10)
- ⬜ Docs match reality (install commands, error table, sample digest) (§11)
- ⬜ Full regression green: `pytest` (**951**; gate on `0 failed`) + the eval structural gate (`eval_harness.py`) + the five eval suites (**52** scenarios) (§0.3, §12)
- ⬜ Planned config slash-command tests are marked **N/A (pending build)**, not green (§13)
- ⬜ Multi-source: live Ashby/Greenhouse/Lever rows; shim multi-source run shows per-source counts + first-pass footnote; one source down never blanks the run (§14)

**Teardown:** `rm -rf "$JSOS_TEST"` and any `$T*`/`$SH*` dirs you kept.

---

## Maintainer notes (fill in each pass) — DX feedback loop
Capture reality so the next review can compare against it (this is the boomerang signal — don't skip it):
- **TTFV (T2.1):** ______ s  ·  **Smoke-subset wall-clock:** ______ min  ·  **Full-pass wall-clock:** ______ min
- **Where did onboarding / the home view confuse you?** (the one thing you'd fix first) ______
- **Any T4.7 phrasing Claude misread?** ______
- **New product gaps found** (add to the tech-debt tracker): ______

