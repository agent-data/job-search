---
title: Job Search OS — Foundation & Core (Plan A)
state: completed
created: 2026-06-05
completed: 2026-06-07
---

# Job Search OS — Plan A: Foundation + Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation and core of the open-source "Job Search OS" — the shared contract/conventions, the deterministic `state.py` job-database engine, the `evaluate-job-fit` relevance skill, and the `job-search-run` headless runner — so a user with a preferences brief can pull, dedup, relevance-judge, and digest LinkedIn job postings via the `agent-data` CLI.

**Architecture:** Claude Code skills (Markdown `SKILL.md`) orchestrate; deterministic mechanics live in dependency-free Python (`state.py`); relevance is **qualitative model inference** (no scores/weights) owned by the `evaluate-job-fit` skill. Data lives in a private file workspace (`config.yaml`, prose `preferences.md`, append-only `jobs.jsonl` event log, `runs/`, `reports/`). The single job source is the agent-data "Job Postings API" behind a thin contract reference. Skills are verified with **skill-creator evals** against a `fake-agent-data` shim so no real credits are spent in tests.

**Tech Stack:** Claude Code skills + skill-creator; Python 3.9+ stdlib only (no runtime deps); pytest (dev only); bash; the `agent-data` CLI (v0.8.0, already installed + authed).

---

## Scope & Sequence

This is **Plan A of a four-plan sequence** decomposed from `docs/superpowers/specs/2026-06-05-job-search-os-design.md` (the spec's 7-phase build sequence):

- **Plan A (this plan) — Foundation + Core (spec phases 1–4):** repo scaffold, shared references, `state.py`, `evaluate-job-fit`, `job-search-run`. **Delivers a working headless runner.**
- **Plan B — Onboarding (phase 5):** `job-preference-interview`, `job-search-setup`.
- **Plan C — Resume (phase 6):** `resume-compare`, `resume-tailor`, `provenance.py`.
- **Plan D — Packaging & polish (phase 7):** README, `plugin.json`, `build.sh` dual-distribution, examples.

Plan A produces working, testable software on its own: given a workspace folder containing a `config.yaml` and a prose `preferences.md`, `/job-search-run` pulls postings, dedups, judges relevance, and writes a digest.

## Prerequisites (verify before Task 1)

- `agent-data` on PATH and authed: `agent-data whoami` shows `"api_key_set": true`. (Verified: v0.8.0, key from config.)
- Python 3.9+: `python3 --version`.
- pytest for dev: `python3 -m pip install --user pytest` (or a venv).
- Claude Code with the `skill-creator` skill available (used to author + eval the two skills).
- No git worktree needed — Task 1 creates the brand-new `~/job-search-os` repo.

## File Structure (created by this plan)

```
~/job-search-os/                          # NEW public repo (no personal data ever)
  .gitignore                              # repo ignores (__pycache__, .pytest_cache, *.pyc)
  LICENSE                                 # MIT
  README.md                               # one-paragraph skeleton (full README in Plan D)
  shared/references/
    agent-data-contract.md                # distilled Job Postings API contract (single source of truth)
    errors.md                             # the E-* named-error table (cause + fix + what the user sees)
    conventions.md                        # workspace layout, file schemas, relevance vocabulary, digest format
  scripts/
    state.py                              # deterministic jobs.jsonl engine: known-ids | append | fold
  skills/
    evaluate-job-fit/
      SKILL.md                            # the relevance brain (qualitative, model inference)
      references/                         # dev copy of the 3 shared references (synced; Plan D adds build.sh)
      evals/evals.json                    # skill-creator eval cases
      evals/files/                        # sample brief + labeled postings
    job-search-run/
      SKILL.md                            # the headless run loop
      references/
      evals/evals.json
      evals/files/
  templates/
    config.example.yaml                   # starter config (queries + schedule, no budgets)
    preferences.example.md                # model prose brief
    workspace.gitignore                   # deny-all template for the PRIVATE workspace
  tests/
    test_state.py                         # pytest for state.py
    fake-agent-data                       # PATH shim returning canned JSON per scenario (no real credits)
    fixtures/<scenario>/...               # canned agent-data responses for run evals
```

Two distinct directories the reader must never confuse: **`~/job-search-os/`** is the public code repo (this plan commits to it); **`~/job-search/`** is the per-user PRIVATE workspace the runner reads/writes (never committed; created by Plan B's setup, or by hand for testing).

---

## Phase 1 — Repo scaffold, shared references, templates

### Task 1: Initialize the repo

**Files:**
- Create: `~/job-search-os/.gitignore`
- Create: `~/job-search-os/LICENSE`
- Create: `~/job-search-os/README.md`

- [ ] **Step 1: Create the repo and enter it**

```bash
mkdir -p ~/job-search-os && cd ~/job-search-os && git init
```
Expected: `Initialized empty Git repository in …/job-search-os/.git/`

- [ ] **Step 2: Write `.gitignore`** (repo-level; the workspace deny-all template is separate)

```gitignore
__pycache__/
*.pyc
.pytest_cache/
.DS_Store
*.skill
```

- [ ] **Step 3: Write `LICENSE`** (MIT — fill the copyright line)

```text
MIT License

Copyright (c) 2026 Aptiq Labs, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Write `README.md`** (skeleton; full version in Plan D)

```markdown
# Job Search OS

Turn Claude Code into an operating system for your job search. Define your preferences once,
then let Claude Code pull fresh job postings on a schedule, judge each one's relevance against
what you actually want, and hand you a ranked digest — plus on-demand resume comparison and
truthful resume tailoring.

> **Status:** under construction. Core runner (`evaluate-job-fit`, `job-search-run`) lands first.

## Requirements
- [Claude Code](https://claude.com/claude-code)
- The `agent-data` CLI: `npm install -g agent-data`, then set your key (`agent-data whoami` to verify).

## Privacy
Your personal data (preferences, resumes, matched jobs) lives in a separate **private** workspace
folder (default `~/job-search/`) and must never be committed to a public repo. See `templates/workspace.gitignore`.

## License
MIT — see `LICENSE`.
```

- [ ] **Step 5: Commit**

```bash
cd ~/job-search-os && git add . && git commit -m "chore: scaffold job-search-os repo (license, gitignore, readme skeleton)"
```

### Task 2: Write `shared/references/agent-data-contract.md`

This is the single source of truth for how the whole system talks to the job source. Content is distilled from the live `agent-data docs f9a6ec16-0bfd-44d8-b3ee-073776745ee7`.

**Files:**
- Create: `~/job-search-os/shared/references/agent-data-contract.md`

- [ ] **Step 1: Write the contract file**

````markdown
# agent-data Job Postings API — contract

The only job source in v1. Accessed via the `agent-data` CLI (JSON stdout, errors to stderr, exit 1 on failure).

- **Listing id:** `f9a6ec16-0bfd-44d8-b3ee-073776745ee7`
- **CLI shape:** `agent-data call <listing-id> <slug> [--flag value ...]`. Add `--dry-run` to print the
  resolved request without executing. `agent-data whoami` reports auth.
- **Free vs metered:** `whoami`, `search`, `docs`, and the listing's `status` route are FREE. The
  `search-jobs` and `get-posting` calls are metered. **Never surface credits to the user** — see `errors.md` (E-QUOTA).
- **Dedup key:** the LinkedIn-native **`source_id`** (stable across searches). The row's `id` (format
  `jp_<12-hex>`) is listing-scoped and NOT stable — use it only as a short-lived pairing token with `source_url`.

## Route: status  (free, run this first)
```
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 status
```
Returns `{"status": "ok"}` healthy or `{"status": "degraded"}` when upstream fetches are failing at a high
rate. Does not consume the fetch budget. A fresh service is `ok` by default.

## Route: search-jobs  (metered)
```
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 search-jobs \
  --keywords "<required>" [--location "<optional>"] [--limit <1-100, default 20>] \
  --fields id,source_id,source_url,title,company_name,location_display,salary_display,posted_at,detail_available
```
- **No pagination** (LinkedIn has no stable cursor); re-running may reorder. Vary keywords/location for breadth.
- **Returns** `data.results[]`, each row (all nullable): `id` (`jp_…`), `source_id`, `source_url`, `title`,
  `company_name`, `location_display`, `salary_display` (FREE TEXT — never parse for numbers), `posted_at`
  (ISO), `source`, `search_status`, `detail_available` (bool). Also `data.warnings[]`, `data.status`,
  `data.started_at/completed_at`, `meta.request_id`.
- **Errors:** `422 invalid_request` (`details[].loc` names the bad param), `400 unsupported_field`
  (bad `fields=` name), `502 search_failed` (`retryable:true`).

## Route: get-posting  (metered; needs the id+source_url PAIR from one search row)
```
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 get-posting \
  --posting_id "<jp_ id from the row>" --source_url "<source_url from the SAME row>" \
  --fields id,title,company_name,location_display,employment_type,posted_at,description_markdown,missing_fields
```
- **Returns** `data.description_markdown` (full JD), `data.employment_type`, `data.missing_fields[]` (fields
  the page didn't yield — treat as "not stated", NEVER as a negative), plus the summary fields; `meta.mode`,
  `meta.request_id`. **`application_url` is intentionally not exposed.**
- **Errors:** `400 invalid_pair` (`retryable:false` — the id/source_url don't match; do NOT retry, fall back
  to summary-only), `422 invalid_request` (missing/invalid source_url), `400 unsupported_field`,
  `502 detail_fetch_failed` (`retryable:true`).

## Error envelope (all routes)
```json
{"error": {"code": "...", "message": "...", "param": "...", "request_id": "...", "retryable": true, "source": "...", "details": []}}
```
**Branch retries on the `retryable` boolean, not on parsing `code`.** Retry only `retryable:true` (the 502s):
up to 3 attempts, exponential backoff with jitter (~1s, 3s, 7s). Never retry `invalid_pair` / `invalid_request`
/ `unsupported_field`. If two consecutive `search-jobs` calls return 502, stop searching this run
(LinkedIn stretch-outage) — see `errors.md` (E-UPSTREAM-STRETCH).
````

- [ ] **Step 2: Sanity-check the contract against live docs (free)**

```bash
agent-data docs f9a6ec16-0bfd-44d8-b3ee-073776745ee7 | python3 -c "import sys,json; d=json.load(sys.stdin); print([r['slug'] for r in d['api']['routes']])"
```
Expected: `['status', 'search-jobs', 'get-posting']` — confirms route slugs match the contract.

- [ ] **Step 3: Commit**

```bash
cd ~/job-search-os && git add shared/references/agent-data-contract.md && git commit -m "docs: add agent-data Job Postings API contract reference"
```

### Task 3: Write `shared/references/errors.md`

**Files:**
- Create: `~/job-search-os/shared/references/errors.md`

- [ ] **Step 1: Write the named-error table**

````markdown
# Named errors (E-*) — cause + fix + what the user sees

Every failure is named and visible (no silent failures). Headless runs that are BLOCKED exit non-zero so a
cron log/desktop notify shows it. The digest's "Run health" line is one of: `healthy | partial (N errors) |
degraded (LinkedIn flaky) | blocked (action needed)`.

| Code | When | What the user sees (cause + fix) | Run effect |
|---|---|---|---|
| **E-NO-CONFIG** | `config.yaml` missing in the workspace | "No `config.yaml` found in <workspace>. Run `/job-search-setup` to create one." | HALT, exit 1 |
| **E-NO-AUTH** | `agent-data whoami` shows `api_key_set:false` | "agent-data is not authenticated. Run `export AGENT_DATA_API_KEY=mtk_…` (or save it to `~/.agent-data/config.json`), then verify with `agent-data whoami`. No data was pulled." | HALT, exit 1 |
| **E-CONFIG-VERSION** | `config.yaml` `version` major is newer than this code supports | "This `config.yaml` was written by a newer version. Update the job-search-os skills, or check `version:` in config." | HALT, exit 1 |
| **PATH B (no preferences)** | `preferences.md` missing/empty | "No Job Preferences Brief found. Run `/job-preference-interview` to build one, or point `config.yaml:workspace.preferences_path` at your own prose brief. Nothing was pulled." | HALT, exit 1 |
| **E-SERVICE-DOWN** | `status` route unreachable / non-200 | "The job source is unreachable right now. This is usually temporary — the next scheduled run will retry." | HALT, exit 1, write "service down" digest |
| **E-BAD-QUERY** | `422 invalid_request` / `400 unsupported_field` on a search | "Query '<id>' is invalid: <param from details[].loc>. Fix it in `config.yaml` under `queries`." | skip that query, continue |
| **E-UPSTREAM-STRETCH** | 2 consecutive `search-jobs` 502s | "LinkedIn was unreachable this run (repeated upstream errors). Partial or no results; the next scheduled run will retry." | stop searching, partial digest |
| **E-QUOTA** | agent-data reports its API limit reached (metered call rejected for quota/payment) | "agent-data's API limit for this period has been reached, so no new postings were pulled. This usually means searches are running very often — lower `schedule.frequency` in `config.yaml` (e.g. `daily` instead of `hourly`), or upgrade your plan at agent-data.motie.dev. Your existing matches are unaffected." | HALT, exit 1 |

### Expected non-errors (footnotes, not failures)
- **invalid_pair** (`400`, `retryable:false`) on `get-posting`: the `jp_`/`source_url` pair went stale (LinkedIn
  re-indexed). Judge from the summary instead and add a digest footnote: "1 posting's detail link had expired;
  judged from its summary." Not an error.
- **Zero results — all already known:** reassuring, not an error — "No NEW postings — all N already in your database."
- **Zero results — literally empty:** actionable — "Searches ran but returned 0 results. Broaden keywords in
  `config.yaml`, or check `agent-data call <listing> status`."

### Detecting E-QUOTA vs E-NO-AUTH from the CLI
Both surface as a non-zero `agent-data call`. Distinguish by: run `agent-data whoami` first (covers auth). If
auth is fine but a metered call fails with a payment/quota/limit signal in stderr (e.g. HTTP 402/429, or a
message mentioning credits/quota/limit), treat as E-QUOTA. Anything else upstream is treated per its
`retryable` flag (502 → retry; otherwise record + continue).
````

- [ ] **Step 2: Commit**

```bash
cd ~/job-search-os && git add shared/references/errors.md && git commit -m "docs: add named-error (E-*) reference"
```

### Task 4: Write `shared/references/conventions.md`

**Files:**
- Create: `~/job-search-os/shared/references/conventions.md`

- [ ] **Step 1: Write the conventions file** (workspace layout, file schemas, relevance vocabulary, digest format)

````markdown
# Workspace conventions & file contracts

The **workspace** (default `~/job-search/`) is PRIVATE per-user data — never committed to a public repo.

```
~/job-search/
  config.yaml                # queries + schedule (human terms only; NO budgets/score thresholds)
  preferences.md             # Job Preferences Brief — prose only
  resumes/master.md          # base resume; resumes/tailored/ for generated ones (Plan C)
  jobs.jsonl                 # append-only EVENT log; current state = fold by source_id
  runs/<run_id>.json         # per-run audit log
  reports/<date>-digest.md   # human digest per run
  .gitignore                 # deny-all (from templates/workspace.gitignore)
```

## config.yaml
```yaml
version: 1
workspace:
  preferences_path: "preferences.md"
  master_resume_path: "resumes/master.md"
queries:
  - { id: "ai-eng-remote", keywords: "AI engineer", location: "United States", limit: 25, enabled: true }
schedule:
  frequency: "daily"         # hourly | every-2-hours | every-6-hours | daily | weekly
  time: "08:00"
  timezone: "America/Los_Angeles"
notify:
  digest_path_template: "reports/{date}-digest.md"
  desktop_notify_on_block: true
```
`run_id` format: UTC timestamp `YYYY-MM-DDTHH-MM-SSZ`. `<date>` for digests: `YYYY-MM-DD` (local tz).

## jobs.jsonl — append-only events (one JSON object per line)
Current state = fold by `source_id`, last-write-wins per field. Two event types:
```jsonc
{ "event":"evaluated", "ts":"<iso>", "run_id":"…", "source":"linkedin", "source_id":"<linkedin id, DEDUP KEY>",
  "query_id":"…", "title":"…", "company_name":"…", "location_display":"…", "salary_display":"…",
  "posted_at":"<iso>", "source_url":"…", "posting_id_at_seen":"jp_…", "detail_read":true,
  "relevant":true, "match":"strong|moderate|weak|null", "reasoning":"…",
  "dealbreakers_hit":[], "unknowns":[], "needs_human_check":false, "status":"new", "first_seen":"<iso>" }
{ "event":"status_changed", "ts":"<iso>", "source_id":"…", "status":"interested", "note":"…" }
```
Allowed `status`: `new | interested | applied | rejected | archived`.

## runs/<run_id>.json — audit log
```jsonc
{ "run_id":"…", "started_at":"…", "completed_at":"…", "status_probe":"ok|degraded|unreachable",
  "queries":[ { "query_id":"…", "keywords":"…", "results_returned":25, "new":6, "errors":[] } ],
  "results_summary":{ "total_results":50, "new_postings":9, "evaluated":9, "detail_read":5,
                      "relevant":6, "strong":3, "moderate":2, "weak":1 },
  "errors":[ { "stage":"get-posting", "source_id":"…", "code":"detail_fetch_failed",
               "retryable":true, "attempts":3, "final":"gave_up", "request_id":"…" } ],
  "run_health":"healthy|partial|degraded|blocked" }
```
No budget block, no credit/USD fields.

## preferences.md — prose brief (the model reads this; NO machine-readable contract, NO weights)
Sections: a 2–3 sentence **Summary**; **Must-haves / dealbreakers** (the binary filters); **Strong
preferences**; **Nice-to-haves**; **Red flags**. Each item is plain, observable language a reader could check
against a posting (e.g. "Remote within the US, or SF Bay Area onsite"). A `created_at:` line near the top lets
a stale brief be flagged.

## Relevance vocabulary (qualitative — NO numbers)
- **relevant**: boolean. False only when a must-have/dealbreaker is clearly violated.
- **match**: `strong` (hits must-haves + most strong preferences) | `moderate` (solid, some gaps) |
  `weak` (relevant but thin) | `null` (when not relevant).
- **unknowns**: brief criteria the posting doesn't address ("not stated"). NEVER counted against a posting.
- **needs_human_check**: true when a must-have/dealbreaker can't be confirmed from the posting (state the question).
- **dealbreakers_hit**: list of must-haves/dealbreakers observably violated.

## Digest format (reports/<date>-digest.md)
```
# Job search digest — <date>
Run health: healthy
9 new postings · 3 strong · 2 moderate · 1 weak · 3 filtered out · spent <n> search + <m> detail reads

## Strong matches
- **<title>** — <company> — <location>
  <one-line reasoning>.  view `<source_url>`
  ⚠ confirm: <needs_human_check question, if any>

## Moderate matches
…

## Weak matches
…

## Filtered out (not relevant): 3
<one line each: title — company — why rejected>

<footnotes: stale detail links, partial failures, brief-age nudge>
```
Strong first. Always show the Run health line and the counts. If blocked, replace the body with the named
error's cause+fix (see `errors.md`).
````

- [ ] **Step 2: Commit**

```bash
cd ~/job-search-os && git add shared/references/conventions.md && git commit -m "docs: add workspace conventions & file-contract reference"
```

### Task 5: Write the templates

**Files:**
- Create: `~/job-search-os/templates/config.example.yaml`
- Create: `~/job-search-os/templates/preferences.example.md`
- Create: `~/job-search-os/templates/workspace.gitignore`

- [ ] **Step 1: Write `templates/config.example.yaml`**

```yaml
version: 1
workspace:
  preferences_path: "preferences.md"
  master_resume_path: "resumes/master.md"
queries:
  - { id: "ai-eng-remote",  keywords: "AI engineer",          location: "United States",         limit: 25, enabled: true }
  - { id: "ml-platform-sf", keywords: "ML platform engineer", location: "San Francisco Bay Area", limit: 25, enabled: true }
schedule:
  frequency: "daily"           # hourly | every-2-hours | every-6-hours | daily | weekly
  time: "08:00"                # used for daily/weekly
  timezone: "America/Los_Angeles"
notify:
  digest_path_template: "reports/{date}-digest.md"
  desktop_notify_on_block: true
```

- [ ] **Step 2: Write `templates/preferences.example.md`** (a model prose brief the evaluator can read)

```markdown
---
created_at: 2026-06-05
---
# Job Preferences Brief

**Summary:** Senior/staff AI engineer (individual contributor) building production LLM systems at a
fast-moving startup; remote within the US or SF Bay onsite; values shipping over process.

## Must-haves / dealbreakers
- Individual-contributor engineering role (NOT primarily people-management).
- Remote within the US, OR onsite in the SF Bay Area. (Onsite elsewhere is a dealbreaker.)
- Works on AI/ML or LLM-powered products (not ML-in-name-only).

## Strong preferences
- Senior or staff level; real technical ownership.
- Small-to-mid startup that ships quickly with low process.
- Python + cloud + modern LLM tooling.

## Nice-to-haves
- Mentorship / a path toward staff/principal.
- Equity with meaningful upside.

## Red flags
- On-call rotations or heavy ops burden.
- "AI" used only as marketing with no real ML work.
```

- [ ] **Step 3: Write `templates/workspace.gitignore`** (deny-all; the workspace is PII)

```gitignore
# job-search workspace is PRIVATE — do not commit to a public repo
*
!.gitignore
!config.example.yaml
```

- [ ] **Step 4: Commit**

```bash
cd ~/job-search-os && git add templates/ && git commit -m "feat: add workspace config/preferences/gitignore templates"
```

---

## Phase 2 — `state.py` (deterministic job-database engine, TDD)

`state.py` is the only place that reads/writes `jobs.jsonl`. Three subcommands: `known-ids` (dedup),
`append` (write one event), `fold` (current state). Dependency-free (stdlib `json`, `argparse`, `sys`).

### Task 6: `known-ids` — list deduped source_ids

**Files:**
- Create: `~/job-search-os/scripts/state.py`
- Test: `~/job-search-os/tests/test_state.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_state.py
import json, subprocess, sys, pathlib
SCRIPT = str(pathlib.Path(__file__).resolve().parent.parent / "scripts" / "state.py")

def run(args, **kw):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, **kw)

def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))

def test_known_ids_missing_file_is_empty(tmp_path):
    r = run(["known-ids", "--jobs", str(tmp_path / "nope.jsonl")])
    assert r.returncode == 0
    assert r.stdout.strip() == ""

def test_known_ids_dedupes_and_skips_null(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    write_jsonl(jobs, [
        {"event": "evaluated", "source_id": "111"},
        {"event": "evaluated", "source_id": "111"},   # duplicate
        {"event": "evaluated", "source_id": "222"},
        {"event": "evaluated", "source_id": None},     # null -> skipped
        {"event": "status_changed", "source_id": "222", "status": "interested"},
    ])
    r = run(["known-ids", "--jobs", str(jobs)])
    assert r.returncode == 0
    assert r.stdout.split() == ["111", "222"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_state.py -k known_ids -v`
Expected: FAIL (state.py does not exist yet).

- [ ] **Step 3: Write the minimal implementation**

```python
#!/usr/bin/env python3
"""state.py — deterministic operations on a jobs.jsonl append-only event log.

Current state = fold events by source_id (last-write-wins per field).
Subcommands: known-ids | append | fold.  Stdlib only.
"""
import argparse, json, sys


def read_events(path):
    try:
        with open(path, encoding="utf-8") as f:
            out = []
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
            return out
    except FileNotFoundError:
        return []


def known_ids(events):
    seen, ordered = set(), []
    for e in events:
        sid = e.get("source_id")
        if sid and sid not in seen:
            seen.add(sid)
            ordered.append(sid)
    return ordered


def cmd_known_ids(args):
    for sid in known_ids(read_events(args.jobs)):
        print(sid)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="jobs.jsonl operations")
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("known-ids", help="print one source_id per line (deduped)")
    k.add_argument("--jobs", required=True)
    k.set_defaults(func=cmd_known_ids)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_state.py -k known_ids -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/job-search-os && git add scripts/state.py tests/test_state.py && git commit -m "feat(state): known-ids subcommand with dedup + null-skip"
```

### Task 7: `append` — write one validated event

**Files:**
- Modify: `~/job-search-os/scripts/state.py`
- Test: `~/job-search-os/tests/test_state.py`

- [ ] **Step 1: Add failing tests**

```python
# append to tests/test_state.py

def test_append_creates_and_appends(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    ev = {"event": "evaluated", "source_id": "333", "title": "X"}
    r = run(["append", "--jobs", str(jobs), "--event", json.dumps(ev)])
    assert r.returncode == 0
    lines = jobs.read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["source_id"] == "333"
    # second append adds a line, does not overwrite
    run(["append", "--jobs", str(jobs), "--event", json.dumps({"event": "status_changed", "source_id": "333", "status": "applied"})])
    assert len(jobs.read_text().splitlines()) == 2

def test_append_rejects_missing_source_id(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    r = run(["append", "--jobs", str(jobs), "--event", json.dumps({"event": "evaluated"})])
    assert r.returncode != 0
    assert "source_id" in (r.stderr + r.stdout)
    assert not jobs.exists()  # nothing written on rejection
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_state.py -k append -v`
Expected: FAIL with "invalid choice: 'append'".

- [ ] **Step 3: Add the implementation** (insert before `main`, and register the subparser)

```python
def append_event(path, event):
    if not isinstance(event, dict) or not event.get("source_id"):
        raise ValueError("event must be a JSON object with a non-empty source_id")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def cmd_append(args):
    try:
        append_event(args.jobs, json.loads(args.event))
    except (ValueError, json.JSONDecodeError) as e:
        print(f"append failed: {e}", file=sys.stderr)
        return 1
    return 0
```

Register inside `main` (after the `known-ids` parser):

```python
    a = sub.add_parser("append", help="append one event (must include source_id)")
    a.add_argument("--jobs", required=True)
    a.add_argument("--event", required=True, help="JSON object")
    a.set_defaults(func=cmd_append)
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_state.py -k append -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/job-search-os && git add scripts/state.py tests/test_state.py && git commit -m "feat(state): append subcommand with source_id validation"
```

### Task 8: `fold` — current state, last-write-wins per source_id

**Files:**
- Modify: `~/job-search-os/scripts/state.py`
- Test: `~/job-search-os/tests/test_state.py`

- [ ] **Step 1: Add failing tests**

```python
# append to tests/test_state.py

def test_fold_last_write_wins_preserves_fields(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    write_jsonl(jobs, [
        {"event": "evaluated", "source_id": "444", "title": "Eng", "status": "new", "match": "weak"},
        {"event": "status_changed", "source_id": "444", "status": "interested"},  # overrides status only
    ])
    r = run(["fold", "--jobs", str(jobs)])
    assert r.returncode == 0
    state = json.loads(r.stdout)
    assert len(state) == 1
    rec = state[0]
    assert rec["status"] == "interested"   # last write wins
    assert rec["title"] == "Eng"            # untouched field preserved
    assert rec["match"] == "weak"

def test_fold_empty_is_empty_array(tmp_path):
    r = run(["fold", "--jobs", str(tmp_path / "nope.jsonl")])
    assert r.returncode == 0
    assert json.loads(r.stdout) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_state.py -k fold -v`
Expected: FAIL with "invalid choice: 'fold'".

- [ ] **Step 3: Add the implementation** (insert before `main`, and register the subparser)

```python
def fold(events):
    state = {}  # source_id -> merged record (insertion order preserved by dict)
    for e in events:
        sid = e.get("source_id")
        if not sid:
            continue
        rec = state.setdefault(sid, {})
        for k, v in e.items():
            if k != "event":
                rec[k] = v  # later events override present keys
    return list(state.values())


def cmd_fold(args):
    print(json.dumps(fold(read_events(args.jobs))))
    return 0
```

Register inside `main`:

```python
    f = sub.add_parser("fold", help="print current state as a JSON array (folded by source_id)")
    f.add_argument("--jobs", required=True)
    f.set_defaults(func=cmd_fold)
```

- [ ] **Step 4: Run the full test file**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_state.py -v`
Expected: PASS (all 6 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/job-search-os && git add scripts/state.py tests/test_state.py && git commit -m "feat(state): fold subcommand (last-write-wins current state)"
```

---

## Phase 3 — `evaluate-job-fit` skill (the relevance brain)

Authored and tested with **skill-creator** (invoke it and follow its workflow). The skill is verified by
qualitative evals: a sample prose brief + labeled postings, asserting correct `relevant`/`match` calls and
unknown/dealbreaker handling. No numeric scoring anywhere.

### Task 9: Author the `evaluate-job-fit` SKILL.md

**Files:**
- Create: `~/job-search-os/skills/evaluate-job-fit/SKILL.md`
- Create (sync): `~/job-search-os/skills/evaluate-job-fit/references/{agent-data-contract.md,errors.md,conventions.md}`

- [ ] **Step 1: Copy the shared references into the skill** (dev sync; Plan D adds `build.sh` to automate)

```bash
cd ~/job-search-os && mkdir -p skills/evaluate-job-fit/references && cp shared/references/*.md skills/evaluate-job-fit/references/
```

- [ ] **Step 2: Invoke skill-creator to author the skill, then write `SKILL.md` with EXACTLY this frontmatter and method**

Frontmatter (drives triggering — keep WHAT + WHEN):

```yaml
---
name: evaluate-job-fit
description: Judge whether a single job posting matches the user's Job Preferences Brief — relevant or not, and if relevant a weak/moderate/strong match — with plain-language reasoning, dealbreakers, and unknowns. Use when the user pastes or references a job posting and asks if it fits their preferences, or when job-search-run needs to evaluate postings.
disable-model-invocation: false
user-invocable: true
---
```

SKILL.md body (this is the method; keep it tight, < ~200 lines):

```markdown
# evaluate-job-fit

Judge ONE job posting against the user's prose Job Preferences Brief. Output is a **qualitative
relevance judgment** — never a numeric score, never category weights.

## Inputs
- The brief: read `config.yaml:workspace.preferences_path` in the workspace (default `preferences.md`).
  If a posting is supplied without a workspace, accept a brief pasted by the user.
- The posting: a pasted job description, a saved `source_id` from `jobs.jsonl`, or a `source_url`+`posting_id`
  pair to read fresh via agent-data `get-posting` (see `references/agent-data-contract.md`; disclose that this
  reads one posting before doing it).

## Method (model inference — read, reason, judge)
1. Read the brief's **must-haves/dealbreakers, strong preferences, nice-to-haves, red flags**.
2. Read the posting (summary fields, or the full `description_markdown` when available). Treat any field the
   posting doesn't mention as **"not stated"** — record it as an unknown, never as a negative.
3. Decide, in this order:
   - **A must-have/dealbreaker is clearly violated → `relevant: false`** (a reject). Name what failed in
     `dealbreakers_hit` and the reasoning.
   - **A must-have can't be confirmed from the posting → do NOT reject.** Keep it, set
     `needs_human_check: true`, and state the exact open question (e.g. "Remote not stated — confirm before applying").
   - **Otherwise `relevant: true`**, and assign a coarse band:
     - `strong` — hits the must-haves and most strong preferences.
     - `moderate` — solid alignment with some gaps.
     - `weak` — relevant but thin alignment.
4. Write 1–3 sentences of **reasoning** that cite specifics from the posting against the brief. The reasoning
   carries the weight — there is no number behind it.

## salary / numbers
`salary_display` is free text ("$180K–$220K", "Competitive", "DOE"). Never parse it for arithmetic or compare
numerically; if comp matters and isn't clearly stated, it's an unknown.

## Output
Return BOTH a short human summary AND this object (used by job-search-run when evaluating in batch):

​```json
{ "relevant": true, "match": "strong", "reasoning": "…",
  "dealbreakers_hit": [], "unknowns": ["compensation not stated"], "needs_human_check": false }
​```
`match` is `null` when `relevant` is false. Bands and vocabulary are defined in `references/conventions.md`.

## Consistency
Judge dealbreakers before alignment; cite evidence; prefer "unknown" over guessing. When unsure between two
bands, pick the lower and say why. Store the reasoning so a human can audit why something was called a match.
```

- [ ] **Step 3: Commit**

```bash
cd ~/job-search-os && git add skills/evaluate-job-fit/ && git commit -m "feat(skill): add evaluate-job-fit (qualitative relevance judgment)"
```

### Task 10: Create eval cases for `evaluate-job-fit` and run them

**Files:**
- Create: `~/job-search-os/skills/evaluate-job-fit/evals/evals.json`
- Create: `~/job-search-os/skills/evaluate-job-fit/evals/files/brief.md`
- Create: `~/job-search-os/skills/evaluate-job-fit/evals/files/posting-strong.md`
- Create: `~/job-search-os/skills/evaluate-job-fit/evals/files/posting-dealbreaker.md`
- Create: `~/job-search-os/skills/evaluate-job-fit/evals/files/posting-unknown-remote.md`

- [ ] **Step 1: Write the sample brief** `evals/files/brief.md`

```markdown
# Job Preferences Brief
## Must-haves / dealbreakers
- Individual-contributor engineering role (not primarily people-management).
- Remote within the US, OR onsite in the SF Bay Area (onsite elsewhere is a dealbreaker).
- Works on AI/ML or LLM products.
## Strong preferences
- Senior/staff IC; Python + cloud + LLM tooling; fast-moving startup, low process.
## Nice-to-haves
- Mentorship; meaningful equity.
## Red flags
- On-call rotations; "AI" as marketing only.
```

- [ ] **Step 2: Write three labeled postings**

`evals/files/posting-strong.md` (expected: relevant=true, match=strong):
```markdown
Senior AI Engineer — Acme (Remote, US)
Build production LLM features in Python on AWS at a fast-moving Series A startup. IC role with technical
ownership and a path to staff. Equity included. No on-call.
```

`evals/files/posting-dealbreaker.md` (expected: relevant=false; dealbreaker = onsite outside SF Bay):
```markdown
Machine Learning Engineer — Globex (Onsite — Austin, TX, 5 days/week)
Onsite only in Austin. Build ML models for ad targeting. Python.
```

`evals/files/posting-unknown-remote.md` (expected: relevant=true but needs_human_check=true; remote not stated):
```markdown
Staff AI Engineer — Initech
Work on LLM-powered developer tools in Python. Senior/staff IC role. (Location/remote policy not specified.)
```

- [ ] **Step 3: Write `evals/evals.json`**

```json
{
  "skill_name": "evaluate-job-fit",
  "evals": [
    {
      "id": 1,
      "prompt": "Using the brief in evals/files/brief.md, evaluate the posting in evals/files/posting-strong.md.",
      "files": ["evals/files/brief.md", "evals/files/posting-strong.md"],
      "expectations": [
        "Judges relevant: true",
        "Assigns match: strong",
        "Reasoning cites IC role, remote-US, LLM/Python, and startup fit",
        "Outputs no numeric score or category weights"
      ]
    },
    {
      "id": 2,
      "prompt": "Using the brief in evals/files/brief.md, evaluate the posting in evals/files/posting-dealbreaker.md.",
      "files": ["evals/files/brief.md", "evals/files/posting-dealbreaker.md"],
      "expectations": [
        "Judges relevant: false",
        "match is null",
        "dealbreakers_hit names the onsite-outside-SF-Bay violation",
        "Does not invent unstated facts"
      ]
    },
    {
      "id": 3,
      "prompt": "Using the brief in evals/files/brief.md, evaluate the posting in evals/files/posting-unknown-remote.md.",
      "files": ["evals/files/brief.md", "evals/files/posting-unknown-remote.md"],
      "expectations": [
        "Does NOT auto-reject despite remote policy being unstated",
        "Sets needs_human_check: true with a clear question about remote/location",
        "Lists location/remote under unknowns rather than counting it against the posting"
      ]
    }
  ]
}
```

- [ ] **Step 4: Run the evals via skill-creator (with-skill vs without-skill baseline) and review**

Invoke the `skill-creator` skill and run its eval workflow against `skills/evaluate-job-fit/evals/evals.json`
(it dispatches with-skill and without-skill subagents in the same turn, grades against the `expectations`,
and opens the review viewer). Confirm all three cases pass the expectations and that **no output contains a
numeric score or weights**. Fix the SKILL.md method and re-run until green.

- [ ] **Step 5: Commit**

```bash
cd ~/job-search-os && git add skills/evaluate-job-fit/evals/ && git commit -m "test(skill): add evaluate-job-fit evals (strong / dealbreaker / unknown-remote)"
```

---

## Phase 4 — `job-search-run` skill (the headless runner)

The orchestration skill. It shells out to `agent-data` (per `references/agent-data-contract.md`) and `state.py`,
applies the `evaluate-job-fit` method to each new posting, and writes the digest + run log. Verified with a
`fake-agent-data` PATH shim so the four data paths are tested without spending real credits.

### Task 11: Build the `fake-agent-data` test shim + fixtures

**Files:**
- Create: `~/job-search-os/tests/fake-agent-data`
- Create: `~/job-search-os/tests/fixtures/happy/search-jobs.json`
- Create: `~/job-search-os/tests/fixtures/happy/get-posting.json`
- Create: `~/job-search-os/tests/fixtures/zero-empty/search-jobs.json`
- Test: `~/job-search-os/tests/test_fake_agent_data.py`

- [ ] **Step 1: Write the failing shim tests**

```python
# tests/test_fake_agent_data.py
import json, os, subprocess, pathlib
SHIM = str(pathlib.Path(__file__).resolve().parent / "fake-agent-data")
LISTING = "f9a6ec16-0bfd-44d8-b3ee-073776745ee7"

def shim(args, scenario="happy", extra_env=None):
    env = dict(os.environ, JOBSEARCH_TEST_SCENARIO=scenario,
               JOBSEARCH_FIXTURES=str(pathlib.Path(SHIM).parent / "fixtures"))
    if extra_env:
        env.update(extra_env)
    return subprocess.run([SHIM, *args], capture_output=True, text=True, env=env)

def test_whoami_authed_by_default():
    r = shim(["whoami"])
    assert r.returncode == 0 and json.loads(r.stdout)["api_key_set"] is True

def test_whoami_unauth_when_env_set():
    r = shim(["whoami"], extra_env={"JOBSEARCH_TEST_NOAUTH": "1"})
    assert json.loads(r.stdout)["api_key_set"] is False

def test_status_ok_by_default():
    r = shim(["call", LISTING, "status"])
    assert json.loads(r.stdout)["status"] == "ok"

def test_search_returns_fixture():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "AI engineer"])
    assert r.returncode == 0
    assert len(json.loads(r.stdout)["data"]["results"]) >= 1

def test_search_502_on_stretch_scenario():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x"], scenario="stretch")
    assert r.returncode != 0
    assert json.loads(r.stderr)["error"]["retryable"] is True
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_fake_agent_data.py -v`
Expected: FAIL (shim does not exist / not executable).

- [ ] **Step 3: Write the shim** `tests/fake-agent-data` (then `chmod +x`)

```python
#!/usr/bin/env python3
"""fake-agent-data — a PATH shim that mimics `agent-data` for tests. No network, no credits.

Scenario via env JOBSEARCH_TEST_SCENARIO (default "happy"); fixtures dir via JOBSEARCH_FIXTURES.
Scenarios: happy | zero-empty | stretch | invalid-pair | degraded | quota.
JOBSEARCH_TEST_NOAUTH=1 makes whoami report unauthenticated.
"""
import json, os, sys

SCEN = os.environ.get("JOBSEARCH_TEST_SCENARIO", "happy")
FIX = os.environ.get("JOBSEARCH_FIXTURES", "")


def out(obj):  # JSON to stdout, exit 0
    print(json.dumps(obj)); sys.exit(0)


def err(code, message, retryable):  # error envelope to stderr, exit 1
    print(json.dumps({"error": {"code": code, "message": message, "retryable": retryable,
                                "param": None, "request_id": "req_fake", "source": "fake"}}), file=sys.stderr)
    sys.exit(1)


def fixture(name):
    with open(os.path.join(FIX, SCEN, name), encoding="utf-8") as f:
        return json.load(f)


def main(argv):
    if not argv:
        err("usage", "no command", False)
    if argv[0] == "whoami":
        out({"api_key_set": os.environ.get("JOBSEARCH_TEST_NOAUTH") != "1",
             "api_key_source": "config", "base_url": "https://example.test"})
    if argv[0] == "call":
        slug = argv[2] if len(argv) > 2 else ""
        if slug == "status":
            if SCEN == "down":
                err("service_unreachable", "status route unreachable", True)
            out({"status": "degraded" if SCEN == "degraded" else "ok"})
        if slug == "search-jobs":
            if SCEN == "stretch":
                err("search_failed", "upstream fetch failed", True)
            if SCEN == "quota":
                err("quota_exceeded", "monthly API limit reached", False)
            out(fixture("search-jobs.json"))
        if slug == "get-posting":
            if SCEN == "invalid-pair":
                err("invalid_pair", "posting_id/source_url mismatch", False)
            out(fixture("get-posting.json"))
    err("unsupported", f"unhandled args: {argv}", False)


if __name__ == "__main__":
    main(sys.argv[1:])
```

Then: `chmod +x ~/job-search-os/tests/fake-agent-data`

- [ ] **Step 4: Write the fixtures**

`tests/fixtures/happy/search-jobs.json`:
```json
{ "data": { "query": {"keywords": "AI engineer", "location": "United States"}, "status": "ok",
    "results": [
      { "id": "jp_aaaaaaaaaaaa", "source_id": "1001", "source_url": "https://www.linkedin.com/jobs/view/1001",
        "title": "Senior AI Engineer", "company_name": "Acme", "location_display": "Remote (US)",
        "salary_display": "$180K-$220K", "posted_at": "2026-06-03T00:00:00Z", "source": "linkedin",
        "detail_available": true },
      { "id": "jp_bbbbbbbbbbbb", "source_id": "1002", "source_url": "https://www.linkedin.com/jobs/view/1002",
        "title": "ML Engineer", "company_name": "Globex", "location_display": "Austin, TX (Onsite)",
        "salary_display": "Competitive", "posted_at": "2026-06-02T00:00:00Z", "source": "linkedin",
        "detail_available": true } ],
    "warnings": [], "started_at": "2026-06-05T08:00:00Z", "completed_at": "2026-06-05T08:00:02Z" },
  "meta": { "request_id": "req_fakesearch" } }
```

`tests/fixtures/happy/get-posting.json`:
```json
{ "data": { "id": "jp_aaaaaaaaaaaa", "source_id": "1001", "title": "Senior AI Engineer", "company_name": "Acme",
    "location_display": "Remote (US)", "posted_at": "2026-06-03T00:00:00Z", "employment_type": "Full-time",
    "source_url": "https://www.linkedin.com/jobs/view/1001", "missing_fields": [],
    "description_markdown": "Build production LLM features in Python on AWS. IC role, path to staff. No on-call. Equity." },
  "meta": { "mode": "live_detail", "request_id": "req_fakedetail" } }
```

`tests/fixtures/zero-empty/search-jobs.json`:
```json
{ "data": { "query": {"keywords": "AI engineer"}, "status": "ok", "results": [], "warnings": [],
    "started_at": "2026-06-05T08:00:00Z", "completed_at": "2026-06-05T08:00:01Z" },
  "meta": { "request_id": "req_fakeempty" } }
```

- [ ] **Step 5: Run to verify shim tests pass**

Run: `cd ~/job-search-os && python3 -m pytest tests/test_fake_agent_data.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
cd ~/job-search-os && git add tests/fake-agent-data tests/fixtures/ tests/test_fake_agent_data.py && git commit -m "test: add fake-agent-data shim + fixtures for run evals"
```

### Task 12: Author the `job-search-run` SKILL.md

**Files:**
- Create: `~/job-search-os/skills/job-search-run/SKILL.md`
- Create (sync): `~/job-search-os/skills/job-search-run/references/{agent-data-contract.md,errors.md,conventions.md}`

- [ ] **Step 1: Sync the shared references into the skill**

```bash
cd ~/job-search-os && mkdir -p skills/job-search-run/references && cp shared/references/*.md skills/job-search-run/references/
```

- [ ] **Step 2: Invoke skill-creator and write `SKILL.md` with EXACTLY this frontmatter and loop**

Frontmatter:

```yaml
---
name: job-search-run
description: Run one job-search pass — load the preferences brief and config, search agent-data for each saved query, dedup against the local job database, judge each new posting's relevance, read full descriptions for promising matches, and write a digest. Use to run the scheduled search, check for new jobs, or when invoked by a schedule.
disable-model-invocation: false
user-invocable: true
---
```

SKILL.md body (the loop; lean on the references — keep < ~300 lines):

```markdown
# job-search-run

Run ONE headless job-search pass over the workspace. Free gates before metered calls; no silent failures.
Read `references/agent-data-contract.md` (CLI + routes + retry rules), `references/errors.md` (every E-* with
the exact cause+fix wording), and `references/conventions.md` (file schemas + digest format) — follow them exactly.

Workspace = the current directory unless `--workspace <path>` is given. The job source listing id is
`f9a6ec16-0bfd-44d8-b3ee-073776745ee7`. Deterministic db ops use `scripts/state.py`.

## Loop
0. **Preflight (free).**
   - No `config.yaml` → E-NO-CONFIG (HALT, exit 1).
   - `agent-data whoami`; `api_key_set:false` → E-NO-AUTH (HALT, exit 1).
   - `config.yaml` `version` major unknown → E-CONFIG-VERSION (HALT, exit 1).
   - Brief missing/empty (`workspace.preferences_path`) → PATH B no-preferences (HALT, exit 1, named fix).
   - `agent-data call <listing> status`: `ok` proceed; `degraded` set a flag (read fewer details, warn in digest);
     unreachable → E-SERVICE-DOWN (write a "service down" digest, HALT, exit 1).
1. **Search (one metered call per enabled query).** For each `queries[]` with `enabled:true`, call `search-jobs`
   with `--keywords` (+ `--location`, `--limit`) and `--fields id,source_id,source_url,title,company_name,location_display,salary_display,posted_at,detail_available`.
   - `502 search_failed` (retryable) → retry up to 3× with backoff; on give-up record the error and continue.
     **Two consecutive 502s across queries → E-UPSTREAM-STRETCH: stop searching.**
   - `422`/`400 unsupported_field` → E-BAD-QUERY (name the bad param from `details[].loc`), skip that query.
   - A quota/limit/payment failure (see errors.md detection) → E-QUOTA (HALT, exit 1).
2. **Dedup (free).** `python3 scripts/state.py known-ids --jobs <workspace>/jobs.jsonl` → the known set.
   New postings = results whose non-null `source_id` is not in that set. (Rows with null `source_id` can't be
   deduped → skip and count as "unidentifiable" in the digest.)
3. **Evaluate from the summary (free).** Apply the `evaluate-job-fit` method (read its SKILL.md as the rubric)
   to each NEW posting using only the summary fields. Clearly-irrelevant (a must-have plainly violated) →
   record irrelevant, no detail read. Relevant or uncertain → queue for a detail read.
4. **Read details for promising matches (one metered call each), most-promising first.** Call `get-posting`
   with the row's `id` as `--posting_id` AND its `--source_url` (the pair). Re-judge with `description_markdown`
   + `missing_fields[]` (missing = "not stated", never negative).
   - `400 invalid_pair` (not retryable) → judge from summary only; footnote "detail link expired".
   - `502 detail_fetch_failed` (retryable) → retry/backoff; on give-up, summary-only + note.
   - If many look relevant, read the top batch and mark the rest "summary-only, not yet fully read" in the digest.
5. **Persist + report.** For each new posting, append an `evaluated` event via
   `python3 scripts/state.py append --jobs <workspace>/jobs.jsonl --event '<json>'` (schema in conventions.md;
   include `source_id`, `relevant`, `match`, `reasoning`, `dealbreakers_hit`, `unknowns`, `needs_human_check`,
   `status:"new"`, `first_seen`). Write `runs/<run_id>.json` and `reports/<date>-digest.md` (format in
   conventions.md; strong → moderate → weak, then "filtered out: N"). Print a 5-line terminal summary.

## Run health & exit codes
Every digest starts with a **Run health** line (`healthy | partial | degraded | blocked`). HALT paths
(E-NO-CONFIG, E-NO-AUTH, E-CONFIG-VERSION, PATH B, E-SERVICE-DOWN, E-QUOTA) exit non-zero so a schedule
surfaces them; if `notify.desktop_notify_on_block` is true, fire one desktop notification on a blocked run.
Successful/partial runs exit 0.

## Idempotency
Re-running the same day re-searches (cheap) but dedup means no posting is re-evaluated or re-read. Never write
a duplicate `evaluated` event for a known `source_id`.
```

- [ ] **Step 3: Commit**

```bash
cd ~/job-search-os && git add skills/job-search-run/ && git commit -m "feat(skill): add job-search-run headless loop"
```

### Task 13: Eval the four data paths against the shim

**Files:**
- Create: `~/job-search-os/skills/job-search-run/evals/evals.json`
- Create: `~/job-search-os/skills/job-search-run/evals/files/setup-workspace.sh`

The run skill calls `agent-data` by bare name, so evals run it with the `tests/` shim FIRST on PATH and a temp
workspace. `setup-workspace.sh` builds a temp workspace (config + brief + empty jobs.jsonl) and prints its path.

- [ ] **Step 1: Write `evals/files/setup-workspace.sh`**

```bash
#!/usr/bin/env bash
# Usage: setup-workspace.sh <dest_dir>   (creates a minimal test workspace; copies repo templates)
set -euo pipefail
DEST="$1"; REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
mkdir -p "$DEST/runs" "$DEST/reports"
cp "$REPO/templates/config.example.yaml" "$DEST/config.yaml"
cp "$REPO/templates/preferences.example.md" "$DEST/preferences.md"
: > "$DEST/jobs.jsonl"
echo "$DEST"
```
Then: `chmod +x ~/job-search-os/skills/job-search-run/evals/files/setup-workspace.sh`

- [ ] **Step 2: Write `evals/evals.json`** (each case sets `JOBSEARCH_TEST_SCENARIO` and puts the shim on PATH)

```json
{
  "skill_name": "job-search-run",
  "evals": [
    {
      "id": 1,
      "prompt": "Set up a temp workspace with evals/files/setup-workspace.sh. Put the repo's tests/ dir on PATH (so `agent-data` resolves to tests/fake-agent-data) with JOBSEARCH_TEST_SCENARIO=happy and JOBSEARCH_FIXTURES=<repo>/tests/fixtures. Run job-search-run against that workspace. Then show the digest and jobs.jsonl.",
      "expectations": [
        "Calls status before any search-jobs call",
        "Writes a reports/<date>-digest.md whose Run health line is 'healthy'",
        "Surfaces the Acme Senior AI Engineer as a strong (or moderate) match and groups it before weaker ones",
        "Judges the onsite-Austin ML role as not relevant (dealbreaker) and counts it under 'filtered out'",
        "Appends an evaluated event per new posting to jobs.jsonl via state.py (deduped by source_id)",
        "Output contains no numeric score, no category weights, and no dollar/credit cost figures"
      ]
    },
    {
      "id": 2,
      "prompt": "Same setup but JOBSEARCH_TEST_SCENARIO=zero-empty. Run job-search-run and show the digest.",
      "expectations": [
        "Distinguishes 'literally zero results' and suggests broadening keywords or checking status",
        "Spends no get-posting calls",
        "Exits 0 (this is a normal, non-error outcome)"
      ]
    },
    {
      "id": 3,
      "prompt": "Same setup but JOBSEARCH_TEST_NOAUTH=1 (whoami reports unauthenticated). Run job-search-run.",
      "expectations": [
        "Stops at preflight with the E-NO-AUTH message (export AGENT_DATA_API_KEY + verify with whoami)",
        "Pulls nothing and exits non-zero",
        "Does not call search-jobs"
      ]
    },
    {
      "id": 4,
      "prompt": "Same setup but JOBSEARCH_TEST_SCENARIO=stretch (every search-jobs returns a retryable 502). Run job-search-run and show the digest.",
      "expectations": [
        "Retries the 502 with backoff, then stops searching after two consecutive failures (E-UPSTREAM-STRETCH)",
        "Digest says LinkedIn was unreachable and the next run will retry (Run health: degraded or partial)",
        "Does not crash; distinguishes this from a 'genuinely no new jobs' run"
      ]
    },
    {
      "id": 5,
      "prompt": "Run with an empty workspace dir that has NO preferences.md (delete it after setup). Run job-search-run.",
      "expectations": [
        "Takes PATH B (no-preferences): names the fix (/job-preference-interview or point preferences_path at a brief)",
        "Spends nothing and exits non-zero"
      ]
    }
  ]
}
```

- [ ] **Step 3: Run the evals via skill-creator and review**

Invoke `skill-creator` and run its eval workflow for `skills/job-search-run/evals/evals.json`. For each case the
executor must prepend the repo `tests/` dir to PATH and export `JOBSEARCH_TEST_SCENARIO` / `JOBSEARCH_FIXTURES`
(and `JOBSEARCH_TEST_NOAUTH` for case 3) before invoking the skill, so `agent-data` resolves to the shim. Grade
against the `expectations`. Iterate on the SKILL.md until all five paths behave correctly and **no output shows
scores, weights, or credit costs**.

- [ ] **Step 4: Commit**

```bash
cd ~/job-search-os && git add skills/job-search-run/evals/ && git commit -m "test(skill): add job-search-run four-path evals against fake-agent-data"
```

### Task 14: Full-suite green + live smoke test

- [ ] **Step 1: Run the whole pytest suite**

Run: `cd ~/job-search-os && python3 -m pytest -v`
Expected: PASS (all `test_state.py` + `test_fake_agent_data.py`).

- [ ] **Step 2: One real, low-cost smoke run** (spends a couple of metered calls — confirms the contract is right)

```bash
mkdir -p /tmp/js-smoke && cp ~/job-search-os/templates/config.example.yaml /tmp/js-smoke/config.yaml \
  && cp ~/job-search-os/templates/preferences.example.md /tmp/js-smoke/preferences.md \
  && : > /tmp/js-smoke/jobs.jsonl && mkdir -p /tmp/js-smoke/runs /tmp/js-smoke/reports
# Edit config to a single enabled query with limit 5 to keep it cheap, then:
cd /tmp/js-smoke && claude -p "/job-search-run --workspace /tmp/js-smoke"
```
Expected: a real `reports/<date>-digest.md` with `Run health: healthy`, at least one relevance-judged posting,
and `jobs.jsonl` containing `evaluated` events. Confirm no scores/credits appear. (If LinkedIn is degraded, you
may see the E-UPSTREAM/degraded path instead — that's a valid pass for the error handling.)

- [ ] **Step 3: Commit any fixes surfaced by the smoke run**

```bash
cd ~/job-search-os && git add -A && git commit -m "fix: address issues found in live smoke run" || echo "nothing to commit"
```

---

## Self-Review (completed against the spec)

**Spec coverage (Plan A scope = spec phases 1–4):**
- Shared core references (agent-data-contract, errors, conventions) → Tasks 2–4. ✓
- Templates (config/preferences/workspace.gitignore) → Task 5. ✓
- `state.py` fold/dedup/append → Tasks 6–8 (TDD). ✓
- `evaluate-job-fit` (qualitative relevant/not + weak/moderate/strong, unknowns, dealbreakers, needs_human_check; no scores/weights) → Tasks 9–10. ✓
- `job-search-run` (preflight + free `status` gate, search with retry-on-`retryable`, dedup via state.py, summary-then-detail evaluation, persist events + run log + digest, four data paths, named E-* errors, exit codes) → Tasks 11–14. ✓
- Frequency-not-budget / no credit-think → enforced by eval expectations ("no credit costs"); E-QUOTA is reactive only. ✓
- Deferred to later plans (interview, setup, resume, packaging/build.sh) → noted in Scope & Sequence. ✓

**Placeholder scan:** No TBD/TODO; every code/file step shows complete content; eval cases carry concrete expectations. ✓

**Type/name consistency:** `state.py` subcommands (`known-ids`/`append`/`fold`) and flags (`--jobs`, `--event`)
match across tasks and the run skill's calls. `jobs.jsonl` event fields (`source_id`, `relevant`, `match`,
`reasoning`, `dealbreakers_hit`, `unknowns`, `needs_human_check`, `status`, `first_seen`) match conventions.md,
the evaluate-job-fit output object, and the run's append step. Listing id is identical everywhere. Shim scenario
names (`happy`/`zero-empty`/`stretch`/`invalid-pair`/`degraded`/`quota`/`down`) match the run evals. ✓

---

## Next plans (after Plan A is green)
- **Plan B — Onboarding:** `job-preference-interview` (refactor `~/cookbooks/job-preference-interview.md` into a
  prose-brief skill, dropping its 0–100 rubric) and `job-search-setup` (preflight, scaffold workspace from
  templates, interview-or-import, choose `schedule.frequency` with a plain-language nudge, magical first sample
  search, print copy-paste cron/launchd/loop scheduling).
- **Plan C — Resume:** `resume-compare` (qualitative fit + gaps, read-only) and `resume-tailor` + `provenance.py`
  (truthful tailoring; every tailored line must trace to the master; non-sourced content excluded by default).
- **Plan D — Packaging & polish:** `plugin.json`, `scripts/build.sh` (sync `shared/references/*` into each
  skill's `references/` for the loose-skills install mode), full README (docs-as-product, named-error table,
  privacy), `examples/sample-digest.md`, dual plugin + loose-skills install verification.
```
