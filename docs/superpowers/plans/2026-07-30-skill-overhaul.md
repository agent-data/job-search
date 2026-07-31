# Job-Search Skill Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the plugin's five skills, shared references, structures, and scripts to the
census-proven shape — ~9k words total, positive recipes, validators over prose, behavior evals on
sonnet+haiku — per `docs/superpowers/specs/2026-07-30-skill-overhaul-design.md`.

**Architecture:** Five self-contained skills (≤150 lines each) + a two-file shared core
(`agent-data.md` gotchas/cost, `runbook.md` mechanics) + started-marker/end-record run contract +
`validate-workspace.sh` for every mechanical rule + an eval harness that replaces all substring
and lifecycle tests.

**Tech Stack:** Markdown skills, POSIX shell scripts, Python 3.11+ eval runner (uv), `claude -p`
for eval execution, live agent-data API (no mocks, ever).

## Global Constraints

- Work happens directly on `main`; commit after every task; do NOT push (user pushes).
- NEVER commit anything referencing external users of the Job Postings API (emails, org ids,
  per-user telemetry). Private evidence lives in `docs-private/` (gitignored). Eval baselines
  committed as aggregate numbers only — no machine paths, no org ids.
- Workspace file formats stay compatible: `preferences.md`, `jobs.jsonl`, `config.yaml`, digest
  files unchanged. Old run records must remain readable; old ledgers are ignored, never deleted.
- All 8 harness adapters keep working (Claude Code, Codex, Cursor, opencode, Gemini, Copilot,
  Droid, Pi/Hermes).
- Behavior is tested by evals against the LIVE API (per standing rule: no mocks/fixtures), run on
  BOTH `--model sonnet` and `--model haiku`. Unit-style tests are allowed ONLY for shell scripts
  and the validator. No test may assert substrings of documentation files.
- Skills provide (a) non-obvious gotchas/reminders and (b) process recipes. No quoted
  anti-examples or sayable sample sentences anywhere. No numeric call caps — cost awareness via
  the summary-scan steer and cost-context recipe only.
- Line budgets (checked by lint): job-search ≤150, job-search-run ≤150, evaluate-job-fit ≤80,
  job-preference-interview ≤120, job-search-agent ≤60, agent-data.md ≤120, runbook.md ≤100.
- Version: bump to 0.8.0 at the end; keep-a-changelog entry required.
- Writing rules from CLAUDE.md apply to every generated file (concrete language, no idioms,
  measure before asserting).

---

### Task 1: Eval harness + RED baseline in-repo

**Files:**
- Create: `evals/run_eval.py`, `evals/behaviors.md`, `evals/baseline/2026-07-30-red-baseline.md`
- Create: `evals/cases/` (6 case files, below)
- Modify: `TESTING.md` (append an "Behavior evals" section)

**Interfaces:**
- Produces: `python3 evals/run_eval.py --case <name> --model {sonnet|haiku}` → writes
  `evals/results/<ts>-<case>-<model>/` containing `transcript.jsonl`, `workspace/` (the captured
  `~/.job-search`), `result.json`. Later tasks run this after every skill rewrite.
- Produces: `evals/behaviors.md` — the behavior→eval matrix later tasks cite by row id (B1…B14).

- [ ] **Step 1: Write `evals/behaviors.md`** — copy the 14-row matrix from the spec §Eval plan,
  one row id each (B1 first-message-plain-language … B14 wall-clock/calls-vs-baseline), each row
  naming its case file and grading method (grader-judged transcript, artifact check, or
  validator).

- [ ] **Step 2: Write the 6 case files** under `evals/cases/`, each a YAML header + prompt:
  `quickstart.yaml` (README quickstart sentence, fresh workspace), `headless-run.yaml` (seeded
  workspace + "run one pass now, no questions"), `fit.yaml` (live posting fetched at runtime,
  brief inline), `schedule.yaml` (post-first-run session: "keep this running daily" → must
  configure job + run the real canary through the scheduled path), `kill-midrun.yaml` (start a
  run, kill the process after first search, next session must report the orphaned marker),
  `fault-503.yaml` (detail reads against a source_url pointing at a dead upstream posting; agent
  must stop after 2 consecutive failures and fall back to summary judgment). Header fields:
  `behaviors: [B…]`, `workspace: fresh|seeded`, `timeout_s`, `models: [sonnet, haiku]`.

```yaml
# evals/cases/quickstart.yaml
behaviors: [B1, B2, B3, B4, B10, B13]
workspace: fresh
timeout_s: 1500
models: [sonnet, haiku]
prompt: >
  Set up my job search. I'm looking for a senior product-design role,
  remote in the US, at a mission-driven company.
```

- [ ] **Step 3: Write `evals/run_eval.py`** (~120 lines): stash any `~/.job-search` aside,
  optionally seed from `evals/seeds/<case>/`, spawn
  `claude -p <prompt> --model <m> --allowedTools Bash,Read,Write,Edit,Glob,Grep,Skill,AskUserQuestion,TodoWrite --permission-mode acceptEdits --verbose --output-format stream-json`
  with wall-clock line-stamping (reuse the runner pattern proven in the census evals: Popen +
  readline loop + timeout kill), capture the workspace, restore the stash. `kill-midrun` support:
  `--kill-after-event <regex-on-tool-name>` terminates the child after the first `search-jobs`
  Bash call completes.

- [ ] **Step 4: Write `evals/baseline/2026-07-30-red-baseline.md`** — aggregate numbers only from
  today's iteration-1: first-result 190s / onboarding 28-41 min / 37 and 64 metered calls / read
  path ~3,550 lines / greeting 4th / 35 permission dialogs / assertion outcomes per eval. No
  paths, no user data.

- [ ] **Step 5: Smoke the runner** — `python3 evals/run_eval.py --case fit --model sonnet`
  (cheapest case). Expected: results dir with transcript + result.json; exit 0.

- [ ] **Step 6: Commit** — `git add evals TESTING.md && git commit -m "test(evals): behavior eval harness, cases, and RED baseline"`

---

### Task 2: Harmful-line fixes that ship independently

**Files:**
- Modify: `shared/references/agent-data-contract.md:66` (billing fact), `:71-79` (status-first)
- Modify: `skills/job-search-run/SKILL.md:275-278` (status probe), `:186` (free-route claim)
- Modify: `skills/evaluate-job-fit/SKILL.md:27-30` (posted_at rule)
- Modify: `shared/references/parallelism.md:35-41`, `shared/references/conventions.md`
  (exact-model sections), `skills/job-search-agent/references/customization.md:170-216`

**Interfaces:**
- Produces: the corrected facts later tasks copy into the new shared core: "status and whoami are
  never required; status bills a metered call", "detail_model accepts haiku | sonnet | opus or an
  exact id", the both-null posted_at guard.

- [ ] **Step 1:** In `agent-data-contract.md`: replace line 66's claim with "Every `call` route,
  including `status`, is metered against the included-call allowance; `whoami` is local and
  free." Delete the "run status first" recommendation block (71-79) entirely.
- [ ] **Step 2:** In `job-search-run/SKILL.md`: delete the preflight status-probe step (275-278);
  fix the free-route accounting note at 186 to count status as metered (or simply delete the
  status mention — the probe is gone).
- [ ] **Step 3:** In `evaluate-job-fit/SKILL.md:27-30`: make the rule fire only when BOTH
  `posted_at` AND `published_at` are null (copy the wording pattern from
  `job-search-run/SKILL.md:505`, which is correct).
- [ ] **Step 4:** In `parallelism.md`, `conventions.md`, `customization.md`: replace the
  exact-identifier requirement with: "`detail_model` is one of `haiku`, `sonnet`, `opus`, or an
  exact model id when the host exposes one. Tier aliases are valid run-record values." Delete the
  repair/forbidden-token machinery paragraphs in the same sections.
- [ ] **Step 5:** Run `python3 evals/run_eval.py --case headless-run --model sonnet` (seed:
  copy `evals/seeds/headless-run/` = AI-engineer preferences + 2-query config). Expected in
  transcript: zero `status` calls; run completes; digest written.
- [ ] **Step 6: Commit** — `git commit -am "fix(skills): remove status probe, correct billing fact, posted_at guard, tier-alias model names"`

---

### Task 3: `validate-workspace.sh` (the mechanical-rules validator)

**Files:**
- Create: `shared/scripts/mechanics/validate-workspace.sh`
- Create: `tests/test_validate_workspace.py`
- Modify: `templates/preferences.example.md` (ensure `---` front matter with `created_at`,
  `updated_at`), `templates/config.example.yaml` (timezone comment: "use the system timezone")

**Interfaces:**
- Produces: `validate-workspace.sh WORKSPACE [--post-close RUN_ID]` → exit 0 or per-failure lines
  `INVALID <file> <rule>`. Rules: config.yaml parses + required keys
  (`version,queries,search.sources,schedule`); `search.detail_model` is NOT validated at all —
  not required, not shape-checked, ignored if present (the model-field apparatus is retired;
  the run skill instead encourages delegating detail reads to subagents for context isolation
  and efficiency);
  preferences.md has `---` front matter with ISO
  `created_at`/`updated_at`; run records match the slim schema (Task 5) with UTC `Z` timestamps;
  with `--post-close`: no `runs/.started-<RUN_ID>` marker, no `runs/.scratch/<RUN_ID>/`.

- [ ] **Step 1: Write failing script tests** in `tests/test_validate_workspace.py` — build a tmp
  workspace per case: valid passes; missing front matter fails with `INVALID preferences.md
  front-matter`; bad detail_model fails; `+00:00` timestamp in a run record fails; leftover
  marker fails under `--post-close`.

```python
def test_missing_front_matter_fails(tmp_workspace):
    (tmp_workspace / "preferences.md").write_text("# Brief\nJust text\n")
    r = run_validator(tmp_workspace)
    assert r.returncode != 0
    assert "INVALID preferences.md front-matter" in r.stdout
```

- [ ] **Step 2:** `pytest tests/test_validate_workspace.py -v` → all FAIL (script absent).
- [ ] **Step 3: Write the script** — POSIX sh + awk (match the existing mechanics style; no jq
  dependency), ~120 lines.
- [ ] **Step 4:** `pytest tests/test_validate_workspace.py -v` → PASS.
- [ ] **Step 5: Commit** — `git commit -am "feat(scripts): validate-workspace.sh replaces prose-only file rules"`

---

### Task 4: Retire substring and lifecycle tests

**Files:**
- Delete: `tests/test_run_lifecycle_pressure.py`; the 82 lifecycle-named tests in
  `tests/test_mechanics_scripts.py` (keep the rest); every assertion in
  `tests/test_schedule_health.py` and `tests/test_usage_context_contract.py` that greps doc
  substrings (delete the files if nothing else remains); the substring assertions in
  `tests/test_reference_resolution.py:426-433`.
- Modify: `.github/workflows/*` (or the repo's CI entry): gate = remaining script tests +
  `validate-workspace.sh` self-tests + eval-case lint (`evals/behaviors.md` rows each name an
  existing case file). Live evals are a release gate run locally, not CI (they hit the live API).
- Modify: `TESTING.md` — replace the retired suites' descriptions with the eval-gate description.

**Interfaces:**
- Consumes: Task 1's `evals/behaviors.md`; Task 3's validator.

- [ ] **Step 1:** Delete/trim the files above; run `pytest` — remaining suite green.
- [ ] **Step 2:** `grep -rn "assert.*in.*read_text\|substring" tests/` → zero doc-substring
  assertions remain.
- [ ] **Step 3:** Update CI config + TESTING.md.
- [ ] **Step 4: Commit** — `git commit -am "test: retire substring/lifecycle suites for behavior evals + validator"`

---

### Task 5: Shared core — `runbook.md` (run contract, discovery, paths, scratch)

**Files:**
- Create: `shared/references/runbook.md` (≤100 lines)
- Create: `templates/run-record.example.json`

**Interfaces:**
- Produces (later tasks copy these exactly): started-marker path `runs/.started-<run_id>`;
  run-record schema fields `run_id, trigger(manual|scheduled), scheduler_id, close_state
  (complete|blocked|interrupted), run_health, sources, queries, agent_data_usage
  {searches, detail_reads, other, total_metered}, started_at, completed_at` (UTC, `Z` suffix);
  `brief_revision = sha256(preferences.md)[:12]`; scratch dir `runs/.scratch/<run_id>/`; path
  convention `<plugin-root>/…` for every script/template reference.

- [ ] **Step 1: Write `templates/run-record.example.json`** with the exact fields above and
  realistic values.
- [ ] **Step 2: Write `runbook.md`** with sections: Discovery (the ~334-word recipe, script at
  `<plugin-root>/shared/scripts/mechanics/workspace-discovery.sh`, prose fallback = read the
  registry file, one worked example); File map (one line per workspace file: writer → readers);
  Run contract (marker → work → record+digest → delete marker; orphaned marker on next run =
  tell the user the previous run died, then rerun; the record template IS
  `templates/run-record.example.json`); Scratch rule (everything temporary under
  `runs/.scratch/<run_id>/`, deleted before close, never contains full job descriptions);
  Privacy list (never persist: API keys, auth headers, pagination cursors, full job descriptions,
  preferences text outside preferences.md).
- [ ] **Step 3: Lint** — `wc -l shared/references/runbook.md` ≤100; every referenced path exists.
- [ ] **Step 4: Commit** — `git commit -am "feat(shared): runbook.md — discovery, run contract, scratch, privacy"`

---

### Task 6: Shared core — `agent-data.md` (gotchas + cost)

**Files:**
- Create: `shared/references/agent-data.md` (≤120 lines)

**Interfaces:**
- Produces: the quirks table + cost recipe every skill cites as
  `shared/references/agent-data.md`. Consumed by Tasks 7, 9, 10.

- [ ] **Step 1: Write the file** with sections: CLI basics (search/docs/call/whoami, params are
  route flags, `agent-data docs <listing>` is authoritative and free — read it per run); Quirks
  table with AT MINIMUM these rows, stated as recipes: LinkedIn location — put "remote" in
  `--keywords`, filter on `location_display`; never pass `--location "Remote"` (returns
  India-located rows); LinkedIn fields — `is_remote`/`workplace_type` are null on every LinkedIn
  row, judge remoteness from `location_display` + description text; board sources
  (ashby/greenhouse/lever) — full-text match relaxes to half the terms, expect off-topic rows,
  reject from titles before any detail read; detail reads — copy `id` AND `source_url` together
  from the same search row (never construct either); failures — a detail read that returns
  5xx/upstream-failure twice in a row on a source: stop detail reads for that source this run,
  judge those postings from summaries; status — bills a metered call and is never required;
  quota — free tier is 100 included calls per month, then 403 insufficient_credits: stop metered
  work and tell the user their options. Cost recipe: B = enabled queries × sources; before the
  first metered call of a session, tell the user the free-tier size and B in your own words;
  detail reads are the main cost — the summary scan exists to keep them few.
- [ ] **Step 2: Lint** — ≤120 lines; no quoted sample sentences (`grep -c '"' ` on user-facing
  say-instructions = 0).
- [ ] **Step 3: Commit** — `git commit -am "feat(shared): agent-data.md — per-source gotchas and cost recipe"`

---

### Task 7: Rewrite `job-search-run`

**Files:**
- Rewrite: `skills/job-search-run/SKILL.md` (≤150 lines)
- Modify: `shared/scripts/mechanics/dedup.sh` (same-opening guard)
- Create: `tests/test_dedup_guard.py`

**Interfaces:**
- Consumes: runbook contract (Task 5), agent-data.md (Task 6), `event-log-append.sh` (existing,
  unchanged) for jobs.jsonl appends.
- Produces: digest template (embedded in this SKILL.md, copied from the current
  `conventions.md:577-608` rendering that both evals produced correctly, minus the
  board-footnote misfire: the "boards don't always state dates" footnote applies only when a
  BOARD source contributed rows); the close checklist later cited by evals B8/B9.

- [ ] **Step 1: Write the new SKILL.md**: frontmatter description (triggering conditions only);
  Preflight (discovery per runbook; `agent-data whoami`; config+preferences valid via
  `validate-workspace.sh`); Start (write marker; compute brief_revision); Search (one call per
  query×source; echo-verify source and cutoff; append raw rows to `runs/.scratch/<run_id>/`);
  Reconcile (dedup by `(source, source_id)` via `dedup.sh` against jobs.jsonl known-ids; collapse
  same-run duplicates); Summary scan (the kept 178-word steer, verbatim in function: judge
  titles/locations against the brief FIRST; only postings that could plausibly match get a
  detail read); Detail+judge (per posting: `get-posting` with id+source_url from the row; judge
  with evaluate-job-fit's rule; append the evaluated event to jobs.jsonl via event-log-append.sh;
  delegate detail reads to fresh subagents wherever the host has them — one posting per
  subagent, judged in its own isolated context, which keeps the coordinating session's context
  clean for coordination and lets reads run in parallel; sequential only where the host has no
  subagents; never gated on any model field);
  Digest (embedded template); Close (write record from `templates/run-record.example.json`
  shape; run `validate-workspace.sh --post-close`; delete marker + scratch); Failure handling
  (the 2-consecutive-5xx source rule; on any close_state≠complete say what happened + one next
  step).
- [ ] **Step 2: dedup guard** — failing test first: two rows, same company, titles equal after
  lowercasing/stripping location parentheticals, different source_ids → second row marked
  duplicate. Then implement in `dedup.sh` (new mode `--near`), `pytest
  tests/test_dedup_guard.py -v` → PASS.
- [ ] **Step 3: Evals** — `run_eval.py --case headless-run --model sonnet` then `--model haiku`.
  Grade B5 (detail reads < postings found), B6 (0 fabricated ids), B8 (digest numbers re-derive
  from jobs.jsonl — grader recomputes), B9 via `--case kill-midrun --model sonnet` (orphaned
  marker reported).
- [ ] **Step 4: Lint** — ≤150 lines; references only runbook.md + agent-data.md.
- [ ] **Step 5: Commit** — `git commit -am "feat(run): rewrite job-search-run on marker+record contract"`

---

### Task 8: Trim `evaluate-job-fit` and `job-preference-interview`

**Files:**
- Modify: `skills/evaluate-job-fit/SKILL.md` (≤80 lines)
- Modify: `skills/job-preference-interview/SKILL.md` (≤120 lines)

**Interfaces:**
- Consumes: nothing shared (fit inlines its needs).
- Produces: fit's judgment rule cited by Task 7; the sketch method Task 9 points to (single copy).

- [ ] **Step 1: Fit** — delete the batch-envelope paragraph (55-59) and the Discovery routing;
  replace with: "Preferences live at the path `workspace.preferences_path` names in
  `config.yaml` (default `preferences.md`) inside the workspace the registry names (default
  `~/.job-search`)." Keep everything else (it's the proven template).
- [ ] **Step 2: Interview** — delete depth tiers (59-92) and the invoker-pre-pick guard; the
  quick-sketch method stays HERE only; front matter comes from copying
  `templates/preferences.example.md`.
- [ ] **Step 3: Evals** — `run_eval.py --case fit --model sonnet` and `--model haiku`; grade B12
  (dealbreakers cited, unknowns surfaced, nothing fabricated).
- [ ] **Step 4: Commit** — `git commit -am "refactor(fit,interview): trim to proven core; single-home sketch method"`

---

### Task 9: Rewrite the front door (`job-search`) — onboarding, home, scheduling, canary

**Files:**
- Rewrite: `skills/job-search/SKILL.md` (≤150 lines)
- Delete: `skills/job-search/references/onboarding.md`, `skills/job-search/references/home.md`
- Modify: `templates/config.example.yaml` (add `schedule.consented: null` key with comment)

**Interfaces:**
- Consumes: runbook discovery; interview's sketch; job-search-run; `schedule-line.sh` (existing)
  for job install lines.
- Produces: the communication recipe (all user-facing skills point here); the schedule+canary
  flow evals B10/B11 grade.

- [ ] **Step 1: Write the new SKILL.md** with sections:
  How to communicate (the spec's ~10 positive rules, verbatim from spec §Communication model —
  define concepts at first mention with the offer carrying the explanation; cost facts in your
  own words before metered work; one question at a time via the host's question mechanism;
  matches as message text with reasoning; never fabricate posting facts — name what's unknown;
  match the user's vocabulary; no internal vocabulary in user-facing text).
  Routing (first_run true → First run; false → Home; fit/interview/agent by intent — the
  feedback-routing table kept from home.md:246-251).
  First run: check `agent-data whoami` (if unconfigured: point to `agent-data init`, then
  continue); create the workspace by copying `templates/` files (system timezone into
  config.yaml); one-question sketch (or skip if the request already states preferences); derive
  queries (fold "remote" into keywords per agent-data.md); invoke job-search-run; render
  matches with reasoning; THEN the schedule moment (below). Explain the free tier before the
  first metered call.
  Schedule moment: right after first matches render, offer the recurring job as the product's
  point (define it plainly); on yes → write `schedule.consented: <ISO date>` to config.yaml,
  install via `schedule-line.sh` (cron/launchd/host-native loop), then CANARY: immediately run
  the configured job once through the real scheduled path; because it follows the first run,
  dedup means few or no new postings — if time has passed, a full run is correct. Setup is done
  ONLY when the canary produces a run record with `trigger: scheduled` and a healthy close;
  report the result either way. On no → note how to enable later, move on.
  Home: render the status card (the kept template from home.md:76-94: workspace path, brief
  date, sources, schedule state, last run health, latest digest counts, pipeline counts) +
  next-actions menu + stale-brief nudge (brief older than 30 days with runs since → offer a
  refresh once).
- [ ] **Step 2: Delete** onboarding.md and home.md; `grep -rn "onboarding.md\|references/home"
  skills/ shared/ *.md` → zero references remain.
- [ ] **Step 3: Evals** — `run_eval.py --case quickstart --model sonnet` and `--model haiku`:
  grade B1 (first message plain-language, no internal vocabulary — grader-judged), B2 (brief and
  free tier each explained at first mention), B3 (no status call), B4 (cost context before first
  metered call), B10 (schedule offered right after matches; consent recorded on yes).
  `run_eval.py --case schedule --model sonnet`: grade B11 (job installed AND canary ran through
  the scheduled path AND record shows trigger: scheduled).
- [ ] **Step 4: Commit** — `git commit -am "feat(front-door): rewrite job-search — communication recipe, early schedule moment, mandatory canary"`

---

### Task 10: Shrink `job-search-agent` to the ops card

**Files:**
- Rewrite: `skills/job-search-agent/SKILL.md` (≤60 lines)
- Delete: `skills/job-search-agent/references/customization.md`,
  `skills/job-search-agent/references/scheduling-and-consent.md`
- Delete: `skills/job-search-agent/evals/` entries that target deleted content (keep/port any
  that grade surviving behaviors)

**Interfaces:**
- Consumes: agent-data.md (usage explanation), runbook.md (file map), front door (routing).

- [ ] **Step 1:** Rewrite: description (triggering: how does it work / why did a run fail /
  change behavior); the symptom→fix table (kept verbatim from SKILL.md:183-189, plus one new
  row: "run died mid-flight → orphaned `runs/.started-*` marker; rerun"); usage explanation =
  read the latest run record's `agent_data_usage` + agent-data.md's cost facts; config changes =
  edit config.yaml, validate with `validate-workspace.sh`, changes apply next run; scheduling
  changes → front door's schedule moment (canary required on any new/changed job).
- [ ] **Step 2:** `grep -rn "customization.md\|scheduling-and-consent" skills/ shared/ *.md
  tests/` → zero references.
- [ ] **Step 3: Commit** — `git commit -am "refactor(agent): ops-card rewrite; delete customization + scheduling references"`

---

### Task 11: Delete the old shared corpus + lifecycle scripts + structures

**Files:**
- Delete: `shared/references/internals.md`, `conventions.md`, `run-lifecycle.md`, `errors.md`,
  `voice.md`, `parallelism.md`, `update.md`, `build-stamp.md`, `agent-data-contract.md`
- Delete: `shared/scripts/mechanics/lifecycle-append.sh`, `lifecycle-fold.sh`,
  `support-summary.sh`
- Modify: `skills/job-search-run/SKILL.md` record template note (version field reads from
  `.claude-plugin/plugin.json` — the one place version appears)
- Modify: any file still referencing a deleted path (found by grep)

**Interfaces:**
- Consumes: everything Tasks 5-10 produced (the survivors must already carry all load-bearing
  content: quirks, cost recipe, discovery, run contract, digest/record templates, privacy list).

- [ ] **Step 1: Pre-delete sweep** — for each file to delete, `grep -rn "<basename>" skills/
  shared/ templates/ tests/ evals/ *.md .claude-plugin/ agents/ 2>/dev/null` and fix every
  remaining reference to point at the new owner (or delete the referencing passage).
- [ ] **Step 2: Delete** the files. `grep -rn "internals.md\|conventions.md\|run-lifecycle\|
  voice.md\|parallelism.md\|errors.md\|agent-data-contract\|build-stamp\|update.md\|
  lifecycle-append\|lifecycle-fold\|support-summary" . --include="*.md" --include="*.py"
  --include="*.sh" --include="*.json" --include="*.yaml" | grep -v docs-private | grep -v
  docs/superpowers` → empty.
- [ ] **Step 3:** `pytest` green; `run_eval.py --case headless-run --model sonnet` still passes
  (proves no live dependency on deleted files).
- [ ] **Step 4: Word/line accounting** — `wc -w skills/*/SKILL.md shared/references/*.md` total
  ≤10,000 words; record the number in the commit message.
- [ ] **Step 5: Commit** — `git commit -am "refactor!: delete legacy shared corpus and lifecycle machinery (<N> words remain)"`

---

### Task 12: Repo docs, manifests, harness verification, version

**Files:**
- Modify: `ARCHITECTURE.md`, `AGENTS.md`, `README.md`, `TESTING.md`, `CONTRIBUTING.md` (describe
  the new layout; move any contributor-facing content that lived in deleted refs),
  `CHANGELOG.md` (0.8.0 entry: rewritten skills, deleted contracts, migration note: old ledgers
  ignored, metrics.json/binding sidecar no longer written, workspaces compatible),
  `.claude-plugin/plugin.json` + the 6 host manifests + Hermes `plugin.yaml` (version 0.8.0;
  release-integrity sync), release-integrity script (drop build-stamp sync, keep manifest sync).
- Verify: all 8 adapters reference only existing files.

- [ ] **Step 1:** Update the five repo docs; CHANGELOG entry written keep-a-changelog style.
- [ ] **Step 2:** Bump versions; run the release-integrity script; `pytest` green.
- [ ] **Step 3: Harness sweep** — for each adapter dir/manifest: grep its referenced paths
  against the tree; zero dangling references.
- [ ] **Step 4: Commit** — `git commit -am "chore(release): 0.8.0 — skill overhaul"`

---

### Task 13: Full eval matrix + micro-tests (release gate)

**Files:**
- Create: `evals/results/…` (local, gitignored — add `evals/results/` to `.gitignore`)
- Create: `docs-private/2026-07-30-overhaul-eval-report.md` (private: full outputs)
- Modify: `evals/baseline/2026-07-30-red-baseline.md` (append the GREEN aggregate table)

**Interfaces:**
- Consumes: all 6 cases, both models — 12 runs (kill-midrun and fault-503 may run sonnet-only if
  haiku cannot drive the harness; record any such exclusion with its reason).

- [ ] **Step 1: Micro-tests first** (writing-skills method) for the two highest-risk wordings:
  the communication recipe's first-message behavior and the cost-context recipe. 5+ single-shot
  reps per variant per model + a no-guidance control, manually read every output; tighten
  wording if reps diverge; re-run.
- [ ] **Step 2: Run the matrix** — all cases × {sonnet, haiku}. Grade every behavior row in
  `evals/behaviors.md`; write per-run grading.json (text/passed/evidence).
- [ ] **Step 3: Benchmark vs RED** — aggregate table: pass-rate per behavior per model,
  wall-clock, metered calls, read-path lines, permission-prompt count. GREEN targets: read path
  ≤700 lines; quickstart first-result ≤ RED's 190s; headless metered calls ≤ RED's 64 on the
  same seed; B1-B12 pass on BOTH models.
- [ ] **Step 4:** Any failing behavior: fix the owning file, re-run that case only, repeat until
  green; log each iteration in the private report.
- [ ] **Step 5: Commit** — `git add evals/baseline .gitignore && git commit -m "test(evals): green matrix vs RED baseline (aggregates)"`

---

### Task 14: Dogfood

- [ ] **Step 1:** Fresh terminal, real TUI, this machine: delete `~/.job-search` (stash first if
  present), run the README quickstart sentence end-to-end including saying yes to the schedule,
  watching the canary complete. This is the eval-5 surface — the churn surface — driven by a
  human.
- [ ] **Step 2:** Note every rough edge in `docs-private/2026-07-30-overhaul-eval-report.md`;
  fix blockers (loop with Task 13's per-case re-runs); leave polish items listed.
- [ ] **Step 3: Commit** any fixes — `git commit -am "fix(skills): dogfood findings"`

---

## Self-review (done at write time)

- Spec coverage: every spec section maps to a task (communication→9, skills→7/8/9/10, shared
  core→5/6, structures→5/7/11, scripts→3/7/11, scheduling+canary→9, evals→1/13, migration→12,
  landing order→task order). Gaps: none found.
- Placeholders: none; every doc-writing task carries its section list and must-carry content;
  code/test steps carry code or exact commands.
- Type consistency: marker/record/scratch names identical across Tasks 5, 7, 9, 11; behavior ids
  B1-B14 defined in Task 1 and cited in 7/8/9/13; validator flag `--post-close` consistent in
  3/7.
- Privacy: private outputs route to docs-private/; evals/results gitignored; baselines aggregate.
