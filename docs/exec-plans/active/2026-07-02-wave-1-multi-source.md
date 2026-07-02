---
title: Wave 1 — Multi-Source Job Search (LinkedIn + Ashby + Experimental Workday)
state: active
created: 2026-07-02
---

# Wave 1 — Multi-Source Job Search (LinkedIn + Ashby + Experimental Workday)

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **How this plan was produced.** A 2026-07-01 strategy session (critical review + live prod
> probes of the agent-data Job Postings API + a ratified design) chose "Approach C — One
> Contract, Many Sources." The full rationale, findings (F1–F24), alternatives, and the Wave 2–5
> roadmap live in the **local-only, untracked** strategy doc
> `docs-private/2026-07-02-multi-source-and-expansion-strategy.md` (git-ignored on purpose —
> do not link it from tracked docs; CI cannot resolve it). This plan is self-contained: every
> decision needed to execute is restated here.

**Goal:** The runner currently speaks to exactly one job source — the LinkedIn listing — with
`source:"linkedin"` hardcoded at event-write time, a bare `source_id` dedup key, and
LinkedIn-named error strings (one CI-enforced). The live API now takes `--source
<linkedin|ashby|workday>` on both routes and never fans out across sources, so aggregation is
explicitly the client's job. Wave 1 makes the client honestly multi-source: fan out per
(query × source), dedup per source, survive one source dying, handle Ashby's null `posted_at`
without flooding digests, merge the same real-world role seen on two sources (PR2), ship
Workday as an explicit experiment (PR3) — and fold in the review's hardening items (red CI,
doc drift) so the base is clean.

**Architecture:** One parameterized contract file plus a compact per-source quirks table — no
per-source contract files, no descriptor/plugin layer (rejected: interpreted indirection is
what 8 host models execute divergently). The existing loop widens per (query × source); every
new behavior extends a procedure hosts already run. Zero new event types; config stays
`version: 1`; no migration (every legacy event already carries `source:"linkedin"`).

**Tech stack:** Markdown prose procedures (shared/references + skills), Python 3.11 stdlib dev
tooling (pytest, doc_lint, philosophy_guard), the fake-agent-data PATH shim + JSON fixtures,
skill evals (skill-creator harness), GitHub Actions.

## Global constraints

Copied from the enforced core beliefs + ratified design; every task implicitly includes these:

- **Qualitative-never-numeric:** no scores/weights/thresholds anywhere in product output.
- **No call caps:** relevance decides how many searches/detail reads happen; freshness + dedup
  are the only containment. (This is why there is **no seeding** of first Ashby runs.)
- **Config stays `version: 1`; all schema changes additive; the runner never writes config.**
- **Source enum literal:** `linkedin | ashby | workday` (lowercase in config/CLI). Default when
  `search.sources` is absent: `["linkedin", "ashby"]`. Workday is in no default.
- **Run-health literal set (exact):** `healthy | partial (<why>) | degraded (job sources flaky)
  | blocked (action needed)` where `<why>` ∈ `N errors` · `<source> unavailable` · `all sources
  unavailable`. The old literal `degraded (LinkedIn flaky)` dies everywhere in one commit (T5).
- **Edit `shared/references/*.md` only at the source** — never the synced copies; run
  `./scripts/build.sh` inside the same commit; CI enforces byte-identical sync.
- **Single-source runs keep today's digest byte-shape** — the counts breakdown and per-match
  source tags render only when more than one source was searched.
- Conventional Commits (`feat(scope):`, `test(scope):`, `docs(scope):`, `ci:`); one commit per
  task; append to the Progress log in the same commit.

### Shared vocabulary (the cross-task interface — later tasks consume these names verbatim)

| Name | Definition |
|---|---|
| `search.sources` | ordered list in `config.yaml` `search:` block; values from the source enum; absent → `["linkedin", "ashby"]` |
| `evaluated.source` | REQUIRED event field, copied from the result row's `source` — never a hardcoded literal |
| `evaluated.posted_at_extracted` | OPTIONAL ISO date — a JD-stated posting date extracted during the detail read when the API `posted_at` was null |
| `evaluated.same_role_as` | OPTIONAL flat string `"<source>:<source_id>"` on a merged secondary row (PR2 only) |
| `E-SOURCE-UNSUPPORTED` | server `400 unsupported_source` (`error.param:"source"`) OR a config token outside the enum, caught at preflight |
| `E-SOURCE-IGNORED` | HTTP 200 whose echoed `data.query.source` ≠ the requested source (absent echo counts as `linkedin`) — a legacy server silently swallowing `--source` |
| Shim scenarios | `multi-source` · `one-source-down` · `source-unsupported` · `legacy-source-swallow` (+ env `JOBSEARCH_TEST_DOWN_SOURCE`, default `ashby`) |
| Fixture names | `search-jobs.<source>.json`, `get-posting.<source>.json`, `get-posting.<source>.<posting_id>.json` |
| Digest marks | counts breakdown `(6 LinkedIn · 2 Ashby)`; match tag ` · Ashby`; date marks `date not stated` / `posted ~Jun 25 (from posting text)` |
| First-pass footnote | fires when a source returned rows AND that source's known-ids set was empty at run start: "First pass over <Source> company boards — this batch can include older postings, since boards don't always state dates." |

## Non-goals

- **No per-query `sources:` override** — all queries run against all enabled sources; the
  operator manual names per-query targeting as a known deferred knob.
- **No seeding / mark-seen-without-digesting** — it is a call-count cap in a trenchcoat
  (violates no-caps); the first-pass flood is bounded by `limit` + the summary scan + dedup and
  labeled by the first-pass footnote.
- **No upstream/marketplace changes in this repo** — stale listing copy, remote/date filters,
  per-source status, populating Ashby `posted_at` are the owner's separate marketplace
  checklist (tracked in the strategy doc), not tasks here.
- **No platform-adapter edits** — detail-read mechanics, model tiers, and scheduling are
  untouched; nothing in multi-source is host-specific.
- **No new skills; no Wave 2+ features** (pipeline actions, HN watcher, dossiers, …).
- **E-UPSTREAM-STRETCH keeps its name** — semantics go per-source; renaming would churn every
  eval and doc for zero user value.
- **No renaming of the listing UUID** — `f9a6ec16-0bfd-44d8-b3ee-073776745ee7` serves all three
  sources; what dies is the single-source assumption, not the id.

## Done when

All hold, run from repo root:

- [ ] `python3 -m pytest -q` → green locally, AND the first green run of the `ci` workflow on
      GitHub (the Actions tab has been red since the Zero-Python migration — T1 fixes it)
- [ ] `python3 scripts/doc_lint.py --root .` → clean
- [ ] `python3 scripts/philosophy_guard.py --root .` → green
- [ ] `./scripts/build.sh && test -z "$(git status --porcelain skills)"` → build is a no-op
- [ ] `grep -rn '"source":"linkedin"' shared/references skills --include='*.md'` → **0 hits**
      (the write-time hardcode is gone from every procedure; fixtures under `tests/` may still
      carry it — they are data, not procedure)
- [ ] `grep -rn 'degraded (LinkedIn flaky)' --include='*.md' . | grep -v docs/exec-plans | grep -v CHANGELOG` → **0 hits**
- [ ] **Live Ashby proof** (real API, no shim): `agent-data call
      f9a6ec16-0bfd-44d8-b3ee-073776745ee7 search-jobs --keywords "software engineer" --limit 3
      --source ashby --fields id,source_id,source_url,title,company_name,source` returns rows
      with `"source":"ashby"`, UUID `source_id`s, `jobs.ashbyhq.com` URLs
- [ ] **Live end-to-end run:** a sandboxed workspace with `sources: ["linkedin", "ashby"]` runs
      `job-search-run` against the **real** API → digest shows the per-source counts breakdown,
      ashby matches carry date marks, events carry row-level `source`; an immediate second run
      re-evaluates nothing (per-source dedup holds). Transcript pasted into the Progress log.
- [ ] **Live Workday-degrades-gracefully proof:** the same sandbox with `sources: ["linkedin",
      "ashby", "workday"]` completes `partial (workday unavailable)` with the outage footnote
      while Workday's upstream still 502s (it did on 2026-07-01 — today's brokenness IS the test)
- [ ] Evals 4 and 9 reworded + new evals 15–18 (PR1) and 19 (PR2) pass via the eval harness
- [ ] Sample digest, CHANGELOG, PRODUCT_SENSE, ARCHITECTURE, QUALITY_SCORE, TESTING.md all
      updated (T10); a cold reader of the KB meets no LinkedIn-only claim

## How to execute

Per `docs/PLANS.md`: task-by-task, red → green → commit, one scoped Conventional Commit per
task, appending to the Progress log (and Decision log for judgment calls) in the same commit.
Subagent-driven execution is recommended; each task below is self-contained enough to hand to a
fresh subagent along with the Global constraints + Shared vocabulary sections.

**Hard ordering:** T1 (CI green) first — everything after relies on trustworthy local+CI gates.
T2 (shim + fixtures) before T11 (evals that use the new scenarios). T3–T5 (contracts) before T6
(the run skill references them). T9 (template) before T11 (eval workspaces copy the template).
Within a task, every `shared/references/` edit is followed by `./scripts/build.sh` in the same
commit.

**"Red" for prose tasks:** where no pytest can fail first, the red step is a grep/lint gate that
demonstrably returns the OLD wording before the edit (each task names it exactly). Run the gate,
see it fail (old text present / new text absent), make the edit, re-run to green. Doc tasks end
with `python3 scripts/doc_lint.py --root .` clean.

---

## PR1 — core multi-source + hardening (branch `feat/multi-source-core`)

### Task T1 [BLOCKS] — CI actually runs pytest; RELIABILITY describes the real gates

**Files:**
- Modify: `.github/workflows/ci.yml` (after the `actions/setup-python@v5` step)
- Modify: `docs/RELIABILITY.md:146-147`

**Interfaces:** Produces a trustworthy `python3 -m pytest -q` gate every later task relies on.

- [ ] **Step 1 (red):** confirm the gap — `grep -n "pip install" .github/workflows/ci.yml`
      returns nothing, and the repo has no `requirements*.txt` / `pyproject.toml` / `setup.py`
      (that is why every CI run since 2026-06-11 fails at "Unit tests" with
      `No module named pytest`).
- [ ] **Step 2 (green):** insert between the `setup-python` step and "Unit tests":

```yaml
      - name: Install test dependencies
        run: python3 -m pip install pytest
```

- [ ] **Step 3:** fix `docs/RELIABILITY.md` — replace the sentence
      "runs the pytest suite, the philosophy guard, and the doc linter on every change." with:
      "runs five gates on every change: the pytest suite, the philosophy guard, the doc linter,
      the structural platform validation, and the build-sync no-op check."
- [ ] **Step 4 (verify):** `python3 -m pytest -q` → green locally; `python3 scripts/doc_lint.py
      --root .` → clean; push the branch and confirm the `ci` workflow's "Unit tests" step goes
      green on GitHub.
- [ ] **Step 5 (commit):** `ci: install pytest so the unit-test gate actually runs; docs(reliability): describe all five CI gates`

### Task T2 [BLOCKS] — the fake shim speaks `--source`; per-source fixtures; 4 new scenarios

**Files:**
- Modify: `tests/fake-agent-data`
- Modify: `tests/test_fake_agent_data.py`
- Create: `tests/fixtures/multi-source/search-jobs.ashby.json`
- Create: `tests/fixtures/multi-source/get-posting.ashby.json`
- Create: `tests/fixtures/multi-source/get-posting.ashby.jp_ashbyacme01.json`
- Modify: `skills/job-search-run/evals/files/setup-workspace.sh` (freshness de-flake)

**Interfaces:**
- Produces: scenarios `multi-source` / `one-source-down` / `source-unsupported` /
  `legacy-source-swallow`; env `JOBSEARCH_TEST_DOWN_SOURCE` (default `ashby`); fixture cascade
  `search-jobs.<source>.json` (non-linkedin sources NEVER fall back to the plain linkedin
  fixture — a missing per-source fixture is a loud error, not silent linkedin data);
  `get-posting.<source>.<posting_id>.json` beats `get-posting.<source>.json`; every 200 search
  response gets `data.query.source = <requested>` injected EXCEPT in `legacy-source-swallow`
  (which returns the happy fixture verbatim — its `data.query` has no `source` key, modeling
  "absent echo = linkedin").

- [ ] **Step 1 (red):** append the failing tests to `tests/test_fake_agent_data.py`:

```python
def test_search_source_flag_echoes_requested_source():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "ashby"],
             scenario="multi-source")
    data = json.loads(r.stdout)["data"]
    assert data["query"]["source"] == "ashby"
    assert all(row["source"] == "ashby" and row["posted_at"] is None for row in data["results"])

def test_search_defaults_to_linkedin_and_injects_echo():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x"], scenario="multi-source")
    data = json.loads(r.stdout)["data"]
    assert data["query"]["source"] == "linkedin"
    assert len(data["results"]) == 2  # happy fallback carries the linkedin rows

def test_one_source_down_fails_only_the_down_source():
    down = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "ashby"],
                scenario="one-source-down")
    assert down.returncode != 0
    body = json.loads(down.stderr)["error"]
    assert body["code"] == "search_failed" and body["retryable"] is True
    ok = shim(["call", LISTING, "search-jobs", "--keywords", "x"], scenario="one-source-down")
    assert ok.returncode == 0

def test_source_unsupported_400s_non_linkedin():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "ashby"],
             scenario="source-unsupported")
    assert r.returncode != 0
    body = json.loads(r.stderr)["error"]
    assert body["code"] == "unsupported_source" and body["param"] == "source" \
        and body["retryable"] is False

def test_legacy_swallow_returns_linkedin_rows_without_source_echo():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "ashby"],
             scenario="legacy-source-swallow")
    data = json.loads(r.stdout)["data"]
    assert "source" not in data["query"]  # absent echo = linkedin (the E-SOURCE-IGNORED trigger)
    assert all(row["source"] == "linkedin" for row in data["results"])

def test_unknown_source_value_is_rejected():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "monster"])
    assert r.returncode != 0
    assert json.loads(r.stderr)["error"]["code"] == "unsupported_source"

def test_get_posting_routes_per_source_and_per_posting_id():
    default = shim(["call", LISTING, "get-posting", "--posting_id", "jp_ashbyzeph01",
                    "--source_url", "u", "--source", "ashby"], scenario="multi-source")
    assert json.loads(default.stdout)["data"]["company_name"] == "Zephyr Robotics"
    acme = shim(["call", LISTING, "get-posting", "--posting_id", "jp_ashbyacme01",
                 "--source_url", "u", "--source", "ashby"], scenario="multi-source")
    assert json.loads(acme.stdout)["data"]["company_name"] == "Acme"
```

- [ ] **Step 2:** `python3 -m pytest tests/test_fake_agent_data.py -q` → the 7 new tests FAIL
      (unknown scenario / missing fixtures / no `--source` handling).
- [ ] **Step 3 (green):** modify `tests/fake-agent-data`:
  - Add near the top: `SRC_ALLOWED = ("linkedin", "ashby", "workday")`.
  - Extend `fixture()` with an ordered-candidates cascade:

```python
def fixture(name, names=None):
    # Try each candidate filename in order, scenario dir first then "happy" (so error-injection
    # scenarios keep reusing happy's data). `names` lets a caller pass a per-source cascade.
    for fname in (names or [name]):
        for scen in (SCEN, "happy"):
            path = os.path.join(FIX, scen, fname)
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
    err("fixture_not_found", f"no fixture {name!r} for scenario {SCEN!r} (no happy fallback)", False)
```

  - Replace the `search-jobs` branch body with (keeping `bad-query` exactly as-is):

```python
        if slug == "search-jobs":
            src = flag(argv, "--source") or "linkedin"
            if SCEN == "legacy-source-swallow":
                out(fixture("search-jobs.json"))  # --source silently ignored; no echo injected
            if src not in SRC_ALLOWED or (SCEN == "source-unsupported" and src != "linkedin"):
                err("unsupported_source", f"source {src!r} is not supported", False, param="source")
            if SCEN == "one-source-down" and src == os.environ.get("JOBSEARCH_TEST_DOWN_SOURCE", "ashby"):
                err("search_failed", f"{src} search failed", True)
            if SCEN == "stretch":
                err("search_failed", "upstream fetch failed", True)
            if SCEN == "quota":
                err("quota_exceeded", "monthly API limit reached", False)
            if SCEN == "bad-query":
                loc = flag(argv, "--location")
                if loc and "INVALID" in loc.upper():
                    err("invalid_request", f"location {loc!r} is not a recognized value", False,
                        param="location",
                        details=[{"loc": ["query", "location"], "msg": "unrecognized location",
                                  "type": "value_error"}])
            names = [f"search-jobs.{src}.json"] if src != "linkedin" else ["search-jobs.json"]
            fx = fixture("search-jobs.json", names=names)
            fx.setdefault("data", {}).setdefault("query", {})["source"] = src
            out(fx)
```

  - In the `get-posting` branch, after the two error-scenario checks, route per source:

```python
            src = flag(argv, "--source") or "linkedin"
            pid = flag(argv, "--posting_id") or ""
            if src != "linkedin":
                out(fixture("get-posting.json",
                            names=[f"get-posting.{src}.{pid}.json", f"get-posting.{src}.json"]))
            out(fixture("get-posting.json"))
```

  - Update the module docstring's scenario list to append
    `| multi-source | one-source-down | source-unsupported | legacy-source-swallow` and note
    `JOBSEARCH_TEST_DOWN_SOURCE` (default `ashby`).
- [ ] **Step 4:** create the fixtures. `tests/fixtures/multi-source/search-jobs.ashby.json` —
      note row 1 is the SAME real-world role as happy's linkedin `source_id:"1001"` row (Acme /
      Senior AI Engineer / Remote US) for PR2's merge, row 2 is ashby-only:

```json
{ "data": { "query": {"keywords": "AI engineer", "location": "United States", "source": "ashby"}, "status": "completed",
    "results": [
      { "id": "jp_ashbyacme01", "source_id": "6e9a1f00-1111-4aaa-8bbb-2cc3dd4ee5f6",
        "source_url": "https://jobs.ashbyhq.com/acme/6e9a1f00-1111-4aaa-8bbb-2cc3dd4ee5f6",
        "title": "Senior AI Engineer", "company_name": "Acme", "location_display": "Remote (US)",
        "salary_display": null, "posted_at": null, "source": "ashby", "detail_available": true },
      { "id": "jp_ashbyzeph01", "source_id": "0b7c2d33-2222-4ccc-9ddd-3ee4ff5aa6b7",
        "source_url": "https://jobs.ashbyhq.com/zephyr/0b7c2d33-2222-4ccc-9ddd-3ee4ff5aa6b7",
        "title": "Staff AI Engineer", "company_name": "Zephyr Robotics", "location_display": "Remote (US)",
        "salary_display": null, "posted_at": null, "source": "ashby", "detail_available": true } ],
    "warnings": [], "started_at": "2026-07-02T08:00:00Z", "completed_at": "2026-07-02T08:00:00Z" },
  "meta": { "request_id": "req_fakeashby" } }
```

  `tests/fixtures/multi-source/get-posting.ashby.json` (the default ashby detail — Zephyr; its
  JD STATES a date, exercising `posted_at_extracted`):

```json
{ "data": { "id": "jp_ashbyzeph01", "source_id": "0b7c2d33-2222-4ccc-9ddd-3ee4ff5aa6b7",
    "title": "Staff AI Engineer", "company_name": "Zephyr Robotics", "location_display": "Remote (US)",
    "posted_at": null, "employment_type": "FullTime", "source": "ashby",
    "source_url": "https://jobs.ashbyhq.com/zephyr/0b7c2d33-2222-4ccc-9ddd-3ee4ff5aa6b7",
    "missing_fields": [],
    "description_markdown": "**Job Posted:** June 25th, 2026\n\nStaff-level IC building LLM-powered robotics tooling in Python. Remote within the US. No people management. On-call is opt-in and paid." },
  "meta": { "mode": "live_detail", "request_id": "req_fakeashbydetail" } }
```

  `tests/fixtures/multi-source/get-posting.ashby.jp_ashbyacme01.json` (the merge primary —
  mirrors the happy linkedin detail so the merge is judged from company+title+location, not
  from a description that announces it):

```json
{ "data": { "id": "jp_ashbyacme01", "source_id": "6e9a1f00-1111-4aaa-8bbb-2cc3dd4ee5f6",
    "title": "Senior AI Engineer", "company_name": "Acme", "location_display": "Remote (US)",
    "posted_at": null, "employment_type": "FullTime", "source": "ashby",
    "source_url": "https://jobs.ashbyhq.com/acme/6e9a1f00-1111-4aaa-8bbb-2cc3dd4ee5f6",
    "missing_fields": [],
    "description_markdown": "**Job Posted:** June 28th, 2026\n\nBuild production LLM features in Python on AWS. IC role, path to staff. No on-call. Equity." },
  "meta": { "mode": "live_detail", "request_id": "req_fakeashbydetail2" } }
```

- [ ] **Step 5 (de-flake, folded here because it edits the same test surface):** the happy
      fixtures' `posted_at` values (2026-06-02/03) have aged past the default `past-2-weeks`
      freshness window, so date-dependent evals rot with the calendar. In
      `skills/job-search-run/evals/files/setup-workspace.sh`, immediately after the line that
      copies `config.example.yaml` into the sandbox workspace, pin freshness (adapt the variable
      name to the script's own):

```bash
sed -i.bak 's/freshness: "past-2-weeks"/freshness: "any"/' "$WS/config.yaml" && rm -f "$WS/config.yaml.bak"
```

- [ ] **Step 6 (verify):** `python3 -m pytest -q` → ALL green (old + 7 new).
- [ ] **Step 7 (commit):** `test(shim): fake-agent-data speaks --source — per-source fixtures, query echo, 4 multi-source scenarios; pin eval freshness to "any"`

### Task T3 [BLOCKS] — the contract goes multi-source (`agent-data-contract.md`)

**Files:**
- Modify: `shared/references/agent-data-contract.md` (then `./scripts/build.sh`)

**Interfaces:**
- Consumes: live API behavior verified 2026-07-01 (probe transcript in the strategy doc).
- Produces: the contract text T6's loop follows — `--source` on both routes, echo-verification
  rule, per-source stretch rule, the quirks table.

- [ ] **Step 1 (red):** `grep -n "The only job source in v1" shared/references/agent-data-contract.md`
      → returns line 3 (the claim the live API now falsifies).
- [ ] **Step 2 (green):** rewrite the header block (lines 1–9) to:

```markdown
# agent-data Job Postings API — contract

One listing, three sources. Accessed via the `agent-data` CLI (JSON stdout, errors to stderr,
exit 1 on failure). Every `search-jobs` / `get-posting` call targets exactly ONE source via
`--source` (`linkedin | ashby | workday`; omitted → `linkedin`) — the API never fans out across
sources. Aggregation (the per-source fan-out, dedup, and merging) is this client's job.

- **Listing id:** `f9a6ec16-0bfd-44d8-b3ee-073776745ee7` (serves all sources)
- **CLI shape:** `agent-data call <listing-id> <slug> [--flag value ...]`. Add `--dry-run` to print the
  resolved request without executing. `agent-data whoami` reports auth.
- **Dedup key:** the PAIR (**`source`**, **`source_id`**) — `source_id` is stable only within its
  source. The row's `id` (format `jp_<12-hex>`) is listing-scoped and NOT stable — use it only as a
  short-lived pairing token with `source_url`.
```

- [ ] **Step 3:** in **Route: search-jobs** — add `[--source <linkedin|ashby|workday>]` to the
      CLI example line; change the pagination bullet to "**No pagination on any source**;
      re-running may reorder. Vary keywords/location for breadth."; add `400 unsupported_source`
      to the Errors bullet; and add these two bullets:

```markdown
- **`--source` targets ONE source** (omitted → `linkedin`). Comma-separated or repeated values →
  `400 unsupported_source` (`error.param: "source"`, `retryable:false`) — drop that source for
  this run (E-SOURCE-UNSUPPORTED in `errors.md`), never retry it.
- **Echo-verification (legacy-server defense).** Older service deployments silently IGNORE
  unknown params. After every search, confirm the echoed `data.query.source` equals the source
  you requested (an ABSENT echo counts as `linkedin`). On mismatch → E-SOURCE-IGNORED
  (`errors.md`): skip that source's remaining queries this run, and keep any returned rows under
  their own row-level `source` value (they are real rows of whatever source actually answered).
```

- [ ] **Step 4:** in **Route: status** — append: "The probe is an AGGREGATE across all sources:
      `degraded` cannot be attributed to one source; per-source health is inferred from search
      outcomes. (Upstream ask on file: per-source status.)"
      In **Route: get-posting** — add `[--source <linkedin|ashby|workday>]` to the example and a
      bullet: "Pass the row's `source` explicitly — it removes inference ambiguity; old servers
      ignore it harmlessly."
- [ ] **Step 5:** replace the envelope section's final stretch sentence with: "If two consecutive
      `search-jobs` calls **against the same source** return 502, stop searching THAT source this
      run (per-source stretch) — other sources continue; all enabled sources stretched → stop
      searching entirely. See `errors.md` (E-UPSTREAM-STRETCH)." Then append the new section:

```markdown
## Per-source quirks (one table, the only per-source contract surface)

| | linkedin | ashby | workday |
|---|---|---|---|
| `source_id` | numeric string | Ashby posting UUID | experimental — verify on first real data |
| `source_url` | `linkedin.com/jobs/view/…` + tracking params | clean canonical `jobs.ashbyhq.com/<company>/<uuid>` — **this IS the live apply page** (link it; never frame as auto-apply) | — |
| `posted_at` | date-only in search; full timestamp in detail | **null in BOTH** — a date often appears in the JD prose ("Job Posted: …"); extract it during the detail read | — |
| freshness | window applies normally | null rule applies (never drop null; see `conventions.md`) | — |
| latency / mode | live scrape (seconds) | indexed corpus (~ms); may include months-old or closed postings — the canonical link is how the user verifies openness | 502s expected while upstream stabilizes |
| coverage | LinkedIn job search | broad crawl of public Ashby company boards | WIP upstream |
| `salary_display` | usually null; free text — never parse | usually null | — |
| enums (`employment_type`, …) | `FULL_TIME` | `FullTime` — treat ALL cross-source enums as free text; never exact-match | — |
| `missing_fields` | usually `["application_url"]` | usually `[]` | — |
```

- [ ] **Step 6 (verify):** `./scripts/build.sh` → synced; `python3 scripts/doc_lint.py --root .`
      → clean; `git status --porcelain skills` shows only the synced copies;
      `grep -rn "only job source" shared skills` → 0 hits.
- [ ] **Step 7 (commit):** `feat(contract): one contract, many sources — --source on both routes, echo-verification, per-source quirks table`

### Task T4 [BLOCKS] — conventions: `search.sources`, composite dedup, source-tagged digest

**Files:**
- Modify: `shared/references/conventions.md` (then `./scripts/build.sh`)

**Interfaces:**
- Produces: the `search.sources` schema T6/T8/T9 use; the per-source known-ids operation; the
  `evaluated.source` + `posted_at_extracted` event fields; the digest format T6 writes and the
  home view reproduces; the new run-health literal (T5 owns the errors-side sites).

- [ ] **Step 1 (red):** `grep -n 'source":"linkedin"' shared/references/conventions.md` → line
      56 (the hardcode); `grep -n "default 25" shared/references/conventions.md` → line 47.
- [ ] **Step 2 (green) — config schema:** in the `config.yaml` example's `search:` block, add as
      the FIRST line, and update the trailing prose paragraph:

```yaml
  sources: ["linkedin", "ashby"]  # ordered job sources every query runs against: linkedin | ashby | workday — omit the key for this default; workday is experimental (expect partial runs while upstream stabilizes)
```

  Prose addition to the `search` block paragraph: "`sources` is the ordered list of job sources
  each enabled query runs against (order = presentation order in per-source counts). An absent
  key means `[\"linkedin\", \"ashby\"]`. Tokens outside the enum are dropped at preflight with a
  digest footnote (E-SOURCE-UNSUPPORTED), never a HALT. Per-query source targeting is a known
  deferred knob — all queries run against all enabled sources. The runner reads `sources` and
  never writes it."
- [ ] **Step 3 — limit-default drift (F9):** change the `queries[].limit` sentence to:
      "**`queries[].limit`** (1–100; the API's own default is 20 when omitted — the config
      template sets 25 explicitly) is the per-query feed size — …" (rest unchanged).
- [ ] **Step 4 — events:** update the jobs.jsonl section:
  - Header sentence → "Current state = fold by (**`source`**, **`source_id`**), last-write-wins
    per field (a legacy event with no `source` attaches by `source_id` alone — every legacy
    `evaluated` event already carries `source:"linkedin"`, so in practice only old
    `status_changed` lines lack it)."
  - The `evaluated` example line: replace `"source":"linkedin"` with `"source":"<the result
    row's source — copied, NEVER a hardcoded literal>"`, and `"source_id":"<linkedin id, DEDUP
    KEY>"` with `"source_id":"<source-native id — with source, the DEDUP KEY>"`. After
    `"posted_at":"<iso>"` add: `"posted_at_extracted":"<iso date — OPTIONAL; only when the API
    posted_at was null and the JD states a date>",`.
  - Event-line contract: append "; every `evaluated` event carries a non-empty `"source"`; the
    literal key `"source"` appears at most once per line (the per-source pre-filter grep depends
    on it, exactly as the `"source_id"`-once rule protects the id extraction)".
  - Replace the **Known ids** operation with:

````markdown
- **Known ids** (the dedup set — one per enabled source `S`; missing file = empty set):
  ```bash
  grep -E '"source"[[:space:]]*:[[:space:]]*"'"$S"'"' "$WS/jobs.jsonl" 2>/dev/null \
    | grep -o '"source_id"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4 | sort -u
  ```
  (The `"source"` key pattern cannot match `"source_id"`/`"source_url"` — the closing quote
  must follow immediately. Legacy history all carries `source:"linkedin"`, so the linkedin set
  matches every pre-multi-source event: no migration.)
````

- [ ] **Step 5 — runs/<run_id>.json:** in the example, add `"source":"<source>"` inside each
      `queries[]` entry (entries are now per query × source), and after the `queries` array add
      `"sources_searched":["linkedin","ashby"], "sources_failed":[],`.
- [ ] **Step 6 — digest format:** update the Digest format section:
  - Counts line example → `9 new postings (6 LinkedIn · 3 Ashby) · 3 strong · 2 moderate · 1
    weak · 3 filtered out · <n> searches · <m> detail reads` with the note: "the parenthetical
    per-source breakdown appears ONLY when more than one source was searched; single-source runs
    keep today's exact line."
  - After the match-entry template add: "When more than one source was searched, append
    ` · <Source>` to the match meta line (e.g. `**<title>** — <company> — <location> · Ashby`).
    A match whose `posted_at` was null carries a date mark on its reasoning line: `posted
    ~<Mon D> (from posting text)` when the detail read extracted a JD-stated date, else `date
    not stated`; add `— older than your freshness window` when the extracted date falls outside
    it (the entry still lands in its verdict band: the read is already paid; relevance decides)."
  - Footnotes list: add "first pass over a source (that source's known-ids set was empty at run
    start): `First pass over <Source> company boards — this batch can include older postings,
    since boards don't always state dates.`" and "per-source outage / unsupported / ignored (one
    line each — exact texts in `errors.md`)".
  - Run-health line → `healthy | partial (<why>) | degraded (job sources flaky) | blocked
    (action needed)` — "`<why>` is exactly one of `N errors` (scattered per-query/per-posting
    errors) · `<source> unavailable` (a whole source lost this run) · `all sources unavailable`.
    Precedence: name a lost source over counting errors; `all sources` over one."
- [ ] **Step 7 (verify):** `./scripts/build.sh`; `python3 scripts/doc_lint.py --root .` clean;
      `grep -n 'source":"linkedin"' shared/references/conventions.md` → 0 hits;
      `python3 -m pytest -q` green.
- [ ] **Step 8 (commit):** `feat(conventions): search.sources config, composite (source, source_id) dedup, source-tagged digest format`

### Task T5 [BLOCKS] — errors go source-agnostic; the CI-enforced literal flips atomically

**Files:**
- Modify: `shared/references/errors.md` (then `./scripts/build.sh`)
- Modify: `scripts/doc_lint.py:247-255` (DUP_SIGNATURES)

**Interfaces:**
- Produces: E-SOURCE-UNSUPPORTED + E-SOURCE-IGNORED rows and the exact user-facing texts T6
  references; the new run-health literal `degraded (job sources flaky)`; a new DUP signature
  owning the source enum.

- [ ] **Step 1 (red):** `grep -rn "degraded (LinkedIn flaky)" shared/references scripts` → the
      current literal sites (errors.md:5 + doc_lint.py:251).
- [ ] **Step 2 (green) — errors.md:**
  - Line 5 run-health enum → `healthy | partial (<why>) | degraded (job sources flaky) |
    blocked (action needed)`.
  - **E-UPSTREAM-STRETCH** row → When: "2 consecutive `search-jobs` 502s **against the same
    source** (all retries exhausted)". User sees: "\<Source\> was unreachable this run (repeated
    upstream errors) — results from the other sources only; the next scheduled run will retry."
    / all enabled sources stretched: "Job sources were unreachable this run (repeated upstream
    errors). Partial or no results; the next scheduled run will retry." Run effect: "stop
    searching that source, others continue; all stretched → stop searching, partial digest;
    Run health `partial (<source> unavailable)` / `partial (all sources unavailable)`".
  - Add two rows after E-UPSTREAM-STRETCH:

```markdown
| **E-SOURCE-UNSUPPORTED** | the service answers `400 unsupported_source` (`error.param:"source"`), or preflight finds a `search.sources` token outside the contract's source enum (a config typo) | "This agent-data service doesn't recognize the '<source>' job source — searched <the others>. Remove it from `search.sources` in `config.yaml`, or update the agent-data service." | non-retryable; drop that source for the run, continue; Run health `partial (<source> unavailable)` |
| **E-SOURCE-IGNORED** | a 200 search response whose echoed `data.query.source` ≠ the requested source (an ABSENT echo counts as `linkedin`) — a legacy server silently ignoring `--source` | "The agent-data service predates source selection — only LinkedIn was searched. Update the service, or set `search.sources: ["linkedin"]` to match it." | skip that source's remaining queries this run; keep returned rows under their row-level `source` (they dedup against the genuine calls — no event poisoning); Run health `partial (<source> unavailable)` |
```

  - **E-SERVICE-DOWN** user text → "The job-search service is unreachable right now. This is
    usually temporary — the next scheduled run will retry." (it gates the whole service — the
    one legitimately global HALT).
  - invalid_pair footnote: "(LinkedIn re-indexed)" → "(the source re-indexed it)".
- [ ] **Step 3 — doc_lint:** in `DUP_SIGNATURES`, change
      `(re.compile(r"degraded \(LinkedIn flaky\)"), "run-health states"),` to
      `(re.compile(r"degraded \(job sources flaky\)"), "run-health states"),` and add
      `(re.compile(r"linkedin \| ashby \| workday"), "job source enum"),`.
- [ ] **Step 4 (verify):** `./scripts/build.sh`; `python3 -m pytest -q` green (test_doc_lint has
      no pinned literal — verified 2026-07-02); `python3 scripts/doc_lint.py --root .` clean;
      `grep -rn "degraded (LinkedIn flaky)" shared scripts skills` → 0 hits.
- [ ] **Step 5 (commit):** `feat(errors): per-source stretch, E-SOURCE-UNSUPPORTED, E-SOURCE-IGNORED; run-health literal goes source-agnostic (lint signature updated atomically)`

### Task T6 [BLOCKS] — the run loop fans out per (query × source)

**Files:**
- Modify: `skills/job-search-run/SKILL.md` (SKILL bodies are NOT build-synced — direct edit)

**Interfaces:**
- Consumes: T3's contract (echo-verification, quirks), T4's config/known-ids/digest formats,
  T5's error texts. Produces: the runner behavior evals 15–18 assert.

- [ ] **Step 1 (red):** `grep -n 'source:"linkedin"' skills/job-search-run/SKILL.md` → line 100;
      `grep -n "default 25" skills/job-search-run/SKILL.md` → line 50.
- [ ] **Step 2 (green)** — surgical sentence replacements (keep everything not named):
  - **Intro (line 21):** append to the listing-id sentence: "— one listing serving every job
    source; the enabled sources come from `config.yaml` `search.sources` (absent →
    `["linkedin", "ashby"]`), validated against the contract's enum at preflight (an unknown
    token → E-SOURCE-UNSUPPORTED: drop it, footnote the fix, continue)."
  - **Step 0** degraded note → "job sources flaky — results this run may be affected" and the
    Run-health value → `degraded (job sources flaky)`.
  - **Step 1 heading** → "**Search the feed (one `search-jobs` per enabled query × enabled
    source; run the whole batch concurrently).**" Body edits: pass `--source <s>` on every
    call; limit sentence → "(1–100; the API defaults to 20 — the config template sets 25)";
    after the call description add: "**Echo-verify every 200 response:** if the echoed
    `data.query.source` (absent = `linkedin`) ≠ the requested source → E-SOURCE-IGNORED: skip
    this source's remaining queries, keep the returned rows under their own row-level `source`.
    A `400 unsupported_source` → E-SOURCE-UNSUPPORTED: drop the source, continue." Stretch rule
    → "**Two consecutive fully-failed queries against the SAME source → E-UPSTREAM-STRETCH for
    that source: stop searching it; other sources continue. All enabled sources stretched →
    stop searching entirely (partial digest).** Failure counters are per-source and reset on
    that source's first success."
  - **Step 2** → per-source dedup + the null-date rule: "Run the **known-ids** operation once
    per enabled source (`conventions.md` §jobs.jsonl) → per-source known sets; NEW = rows whose
    non-null `source_id` is not in THEIR OWN source's set. Record which sources had an EMPTY
    known set at run start (that triggers the first-pass footnote in step 5). Then apply
    `search.freshness`: drop NEW rows whose `posted_at` is older than the window — **a null
    `posted_at` is NEVER dropped**: treat the row as new-if-unseen and carry a date-unknown mark
    into the scan and digest."
  - **Step 3** — append to the steer instruction: "When a queued row's `posted_at` is null, the
    steer also asks the detail read to extract a JD-stated posting date if the description names
    one ('Job Posted: …')."
  - **Step 4** — the `get-posting` sentence gains: "pass the row's `--source` explicitly
    (contract → get-posting)."
  - **Step 5** — provenance sentence: replace `source:"linkedin"` with "`source` — **copied from
    the result row, never a literal**"; add `posted_at_extracted` to the judgment field list
    ("optional — the JD-stated date when the API `posted_at` was null"); counts line + digest
    per `conventions.md` (breakdown + tags + date marks); add: "Footnotes: first-pass-per-source
    (for each source flagged in step 2), and one line per lost source (stretch / unsupported /
    ignored — exact texts in `errors.md`). Run health: any lost source → `partial (<source>
    unavailable)`; all lost → `partial (all sources unavailable)`."
  - **Terminal summary** Run-health line token → `degraded (job sources flaky)` (inside the
    example block's `<healthy | partial (N errors) | degraded | blocked>` placeholder — leave
    the placeholder; only prose literals change).
- [ ] **Step 3 (verify):** `grep -n 'source:"linkedin"' skills/job-search-run/SKILL.md` → 0;
      `grep -n "LinkedIn flaky" skills/job-search-run/SKILL.md` → 0;
      `python3 scripts/doc_lint.py --root .` clean; `./scripts/build.sh` no-op.
- [ ] **Step 4 (commit):** `feat(run): fan out per (query × source) — per-source circuit breakers, echo-verification, null-date handling`

### Task T7 [BLOCKS] — the judge extracts JD-stated dates

**Files:**
- Modify: `skills/evaluate-job-fit/SKILL.md`

**Interfaces:** Produces `posted_at_extracted` in the returned judgment object (consumed by T6
step 5 and eval 15).

- [ ] **Step 1 (green):** in **Method** step 2, append: "When the posting's structured
      `posted_at` is null (some sources omit it) and the description text states a posting date
      (e.g. 'Job Posted: April 27th, 2026'), extract it as an ISO date and include it in the
      output object as `posted_at_extracted`. A date the posting doesn't state stays exactly
      that — 'date not stated', an unknown, never a negative." In **Output**, add the optional
      field to the JSON example: `"posted_at_extracted": "2026-06-25"` with a trailing comment
      "// optional — only when the API posted_at was null and the JD stated a date".
- [ ] **Step 2 (verify):** `python3 scripts/doc_lint.py --root .` clean.
- [ ] **Step 3 (commit):** `feat(judge): extract a JD-stated posting date when the API posted_at is null`

### Task T8 [BLOCKS] — sources become visible: home, onboarding, operator manual, internals

**Files:**
- Modify: `skills/job-search/references/home.md` (hand-authored — NOT build-synced)
- Modify: `skills/job-search/references/onboarding.md` (hand-authored)
- Modify: `skills/job-search-agent/SKILL.md`
- Modify: `shared/references/internals.md` (then `./scripts/build.sh`)

**Interfaces:** Consumes T4's config schema + T5's error names. Produces the user-visible
surface (home `Sources:` line, onboarding recap, operator "Job sources" section).

- [ ] **Step 1 (red):** `grep -rn "LinkedIn flaky" skills/job-search/references/home.md
      skills/job-search-agent/SKILL.md` → the two remaining literal sites (home.md:57,
      job-search-agent:91).
- [ ] **Step 2 — home.md:**
  - In the rendered example's status line, extend to: `Brief: updated <date> (<N months ago>)
    ·   Sources: LinkedIn + Ashby   ·   Schedule: <on, daily | off>   ·   Last run: <…>`.
  - In the "Status line" note, add: "sources from `config.yaml` `search.sources` (absent → the
    default pair); render `+ Workday (experimental)` when listed."
  - Line 57's run-health literal → `degraded (job sources flaky)`.
  - In **Tune the feed**, append: "set `search.sources` to choose job sources (e.g. drop back to
    `[\"linkedin\"]`, or add `\"workday\"` to try the experimental source — expect
    `partial (workday unavailable)` runs while its upstream stabilizes)."
- [ ] **Step 3 — onboarding.md §5:** in item 3's acknowledgment example, change the quote to
      "From your preferences I'll search **LinkedIn and public Ashby company boards** for
      **'AI engineer' · 'ML platform engineer'** across **US-remote + the SF Bay Area**. …"
      and append to the following sentence: "The config also comes preset with the default job
      sources (LinkedIn + Ashby company boards) — tunable anytime just by asking." **No new
      question is asked** (TTFV guard: the closed-choice count stays four).
- [ ] **Step 4 — job-search-agent/SKILL.md:**
  - Line 12 system-paragraph: "It searches LinkedIn postings via agent-data" → "It searches
    LinkedIn and Ashby company-board postings (Workday experimental) via agent-data".
  - Line 56 config list: "the `search` block (`freshness`, `detail_model`,
    `parallel_detail_reads`, `queries[].limit`)" → add `sources` first: "(`sources`,
    `freshness`, `detail_model`, `parallel_detail_reads`, `queries[].limit`)".
  - Line 91 literal → `degraded (job sources flaky)`.
  - New section after **Configuring it (conversational)**:

```markdown
## Job sources

Searches run against the sources listed in `config.yaml` `search.sources` (see
`references/conventions.md`; absent means the default pair). What each source is, honestly:

- **linkedin** — LinkedIn job search, fetched live (slow, seconds per query). Posting links go
  to LinkedIn; LinkedIn withholds the direct application URL.
- **ashby** — a broad crawl of public Ashby company boards, served from an index (fast).
  Board links ARE the live apply pages. Boards often omit posting dates — undated matches carry
  "date not stated" (or a date read out of the posting text) rather than being hidden.
- **workday — experimental.** Enable by adding `"workday"` to `search.sources`; expect
  `partial (workday unavailable)` runs while its upstream stabilizes — one source failing never
  blocks the others.

To disable a source, set the list without it (e.g. `search.sources: ["linkedin"]`). Per-query
source targeting ("search only Ashby for this query") is a known deferred knob — today every
query runs against every enabled source. Source-related failures are named errors:
E-SOURCE-UNSUPPORTED and E-SOURCE-IGNORED in `references/errors.md`.
```

- [ ] **Step 5 — internals.md** (Config read/update recipes): add a bullet after "Tune the feed":

```markdown
- **Choose job sources:** set `search.sources` — an ordered list from the contract's source enum
  (see `agent-data-contract.md`); omit the key for the default `["linkedin", "ashby"]`. Adding
  `"workday"` opts into the experimental source (expect partial runs while upstream stabilizes).
  Only conversational flows write this; the headless runner reads it and never changes config.
```

- [ ] **Step 6 (verify):** `./scripts/build.sh`; `python3 scripts/doc_lint.py --root .` clean;
      `grep -rn "LinkedIn flaky" skills shared` → 0 hits.
- [ ] **Step 7 (commit):** `feat(front-door): job sources are visible — home Sources line, onboarding recap, operator-manual section, config recipe`

### Task T9 [BLOCKS] — the config template ships sources

**Files:**
- Modify: `templates/config.example.yaml`

**Interfaces:** Produces the template eval workspaces copy (T11) and onboarding scaffolds (§3).

- [ ] **Step 1 (green):** add as the first line of the `search:` block:

```yaml
  sources: ["linkedin", "ashby"]   # job sources each query runs against — add "workday" to try the experimental Workday source (expect failures while upstream stabilizes)
```

- [ ] **Step 2 (verify):** `python3 scripts/philosophy_guard.py --root .` green (no numeric
      field added); `python3 -m pytest -q` green.
- [ ] **Step 3 (commit):** `feat(config): search.sources ships default [linkedin, ashby]; workday is an explicit opt-in comment`

### Task T10 [BLOCKS] — the docs stop claiming LinkedIn-only; hardening drift fixes

**Files:**
- Modify: `docs/PRODUCT_SENSE.md:101-104` (the multi-source non-goal bullet)
- Modify: `ARCHITECTURE.md:5`
- Modify: `docs/QUALITY_SCORE.md:15`
- Modify: `TESTING.md` (append a multi-source section)
- Modify: `CHANGELOG.md` (new Unreleased section)
- Modify: `examples/sample-digest.md`
- Modify: `docs/exec-plans/index.md` + move `docs/exec-plans/active/2026-06-07-doc-knowledge-base.md`
  and `docs/exec-plans/active/2026-06-22-multi-harness-portability.md` (F11 filing — see step 6)
- Modify: `skills/job-search/references/home.md` ("Coming soon" honesty — F12)

- [ ] **Step 1 (red):** `grep -n "we do not build a plugin system now" docs/PRODUCT_SENSE.md` →
      the stale non-goal; `grep -n "It searches LinkedIn postings" ARCHITECTURE.md` → line 5.
- [ ] **Step 2 — PRODUCT_SENSE.md:** replace the whole multi-source bullet (lines 101–104) with
      the text below; where it says `shared/references/agent-data-contract.md`, make that a
      relative markdown link exactly like the existing errors.md link two bullets up (target
      `../shared/references/agent-data-contract.md`). (The link is written as plain text HERE
      because doc_lint resolves quoted links relative to THIS plan file.)

```markdown
- **Multi-source aggregation — shipped 2026-07; the non-goal's own trigger fired.** This entry
  previously refused multi-source aggregation "before a second source exists," naming the seam
  as sufficient. That condition ended when the Job Postings API shipped per-source selection
  (Ashby live, Workday experimental) — see the contract in
  shared/references/agent-data-contract.md. We added client-side fan-out over that one
  parameterized contract — per-source circuit breakers, a composite dedup key, conservative
  cross-source merging — **not** a source-plugin system; the seam held as designed. Still
  refused: a descriptor/plugin layer before a fourth source earns it.
```

- [ ] **Step 3 — ARCHITECTURE.md:5:** "It searches LinkedIn postings through the agent-data
      marketplace," → "It searches LinkedIn and Ashby company-board postings (plus experimental
      Workday) through the agent-data marketplace,". **QUALITY_SCORE.md** `discovery-search`
      row: grade stays `strong`; gap text → "Workday is experimental (upstream still
      stabilizing); per-query source targeting deferred; cross-source merging is conservative by
      design (unsure → distinct entries)."
- [ ] **Step 4 — TESTING.md:** append as the next top-level numbered section (after the current
      last one), following the doc's driver-legend format:

```markdown
## <N>. Multi-source (LinkedIn + Ashby)

### T<N>.1 Live Ashby search returns ashby rows — 👤
```bash
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 search-jobs \
  --keywords "software engineer" --limit 3 --source ashby \
  --fields id,source_id,source_url,title,company_name,source
```
**Expected:** rows with `"source":"ashby"`, UUID `source_id`s, `jobs.ashbyhq.com` URLs.
**Result:** ⬜

### T<N>.2 Shim multi-source run — 🤖
"Build the eval sandbox (§0.2), export `JOBSEARCH_TEST_SCENARIO=multi-source`, run
job-search-run against the sandbox workspace, and show the digest + jobs.jsonl."
**Expected:** per-source counts breakdown; ashby events carry `"source":"ashby"`; null-date
entries carry a date mark; the first-Ashby-pass footnote is present.
**Result:** ⬜

### T<N>.3 One source down never blanks the run — 🤖
"Same sandbox, `JOBSEARCH_TEST_SCENARIO=one-source-down`. Run job-search-run; show the digest."
**Expected:** LinkedIn matches land; Run health `partial (ashby unavailable)`; outage footnote.
**Result:** ⬜
```

- [ ] **Step 5 — CHANGELOG.md:** insert directly under the intro paragraph:

```markdown
## [Unreleased]

### Added
- **Multi-source job search.** `search.sources` selects the job sources each query runs against
  (`linkedin`, `ashby`, plus experimental `workday`); searches fan out per query × source with
  per-source circuit breakers, composite (source, source_id) dedup, and honest handling of
  Ashby's undated postings (a JD-stated date is extracted during the detail read). Digests
  carry per-source counts and source tags. Two new named errors (E-SOURCE-UNSUPPORTED,
  E-SOURCE-IGNORED) cover unknown sources and legacy servers that ignore source selection.
- Multi-source test surface: fake-shim `--source` support, per-source fixtures, and four new
  scenarios (multi-source, one-source-down, source-unsupported, legacy-source-swallow).

### Fixed
- CI actually runs the unit-test gate (pytest was never installed on the runner).
- `search-jobs` limit default corrected to the API's real value (20) in the run skill and
  conventions; the config template still sets 25 explicitly.
```

- [ ] **Step 6 — exec-plan filing (F11):** flip `2026-06-22-multi-harness-portability.md` and
      `2026-06-07-doc-knowledge-base.md` to `state: completed` + `completed: 2026-07-02`, move
      both to `docs/exec-plans/completed/`, update `docs/exec-plans/index.md` (move entries under
      Completed; the doc-knowledge-base entry gains "— parts describing the removed Python
      tooling are historical; superseded by the Zero-Python migration"). Confirm with
      `python3 scripts/doc_lint.py --root . --only plan-location --only index-completeness`.
      *(Judgment call: the multi-harness plan's own log says P1–P5 complete and the work is on
      main; if the owner still wants it open pending all-harness testing, skip its move and log
      the decision — the doc-knowledge-base move is unconditional.)*
- [ ] **Step 7 — home.md "Coming soon" honesty (F12):** change the Plan C paragraph's "are
      **coming soon (Plan C)**" to "are **planned (Plan C, not yet scheduled)**" so shipped copy
      stops promising an unscheduled feature.
- [ ] **Step 8 — sample digest:** update `examples/sample-digest.md`: counts line →
      `9 new postings (6 LinkedIn · 3 Ashby) · 2 strong · 2 moderate · 2 weak · 3 filtered out ·
      4 searches · 5 detail reads`; give the Forge Labs strong match the ashby treatment — meta
      line `**Lead Product Designer, Developer Tools** — Forge Labs — Remote (US) · Ashby`, link
      `[view on company board](https://jobs.ashbyhq.com/forge-labs/1b2c3d4e-5f60-4a7b-8c9d-0e1f2a3b4c5d)`,
      and append `date not stated` to its reasoning line; in _Notes:_ change "(LinkedIn
      re-indexed)" to "(the source re-indexed it)" and add the line "- First pass over Ashby
      company boards — this batch can include older postings, since boards don't always state
      dates."
- [ ] **Step 9 (verify):** `python3 scripts/doc_lint.py --root .` clean;
      `python3 scripts/philosophy_guard.py --root .` green;
      `grep -rn "LinkedIn-only" docs ARCHITECTURE.md` → no live-doc claims remain.
- [ ] **Step 10 (commit):** `docs(product): multi-source ships — the YAGNI non-goal reversed on its own stated trigger; drift + filing hardening (F9-F12)`

### Task T11 [BLOCKS] — evals: two reworded, four new

**Files:**
- Modify: `skills/job-search-run/evals/evals.json`

**Interfaces:** Consumes T2's scenarios + T9's template (eval workspaces copy it).

- [ ] **Step 1 (green) — reword:** eval id 4 (stretch — the shim fails EVERY source, so this is
      now the all-sources case): expectation 2 → "Digest says job sources were unreachable
      (all enabled sources stretched) and the next run will retry (Run health: partial (all
      sources unavailable))". Eval id 9 (degraded): expectation 1 → "Sets Run health: degraded
      (job sources flaky) and notes job sources are flaky (results this run may be affected) in
      the digest".
- [ ] **Step 2 — add evals 15 and 16 exactly:**

```json
{
  "id": 15,
  "scenario": "multi-source",
  "prompt": "Same harness but JOBSEARCH_TEST_SCENARIO=multi-source (the workspace config ships search.sources [linkedin, ashby]; linkedin returns the happy rows via fallback, ashby returns 2 rows with UUID source_ids and null posted_at). Run job-search-run against <tmp> and show the digest + jobs.jsonl.",
  "expectations": [
    "Runs one search-jobs per (enabled query × enabled source), passing --source on every call, and verifies the echoed data.query.source matches the request",
    "Every evaluated event's source is copied from its result row (linkedin rows → \"linkedin\", ashby rows → \"ashby\") — never a hardcoded literal",
    "Ashby rows with null posted_at are NOT dropped by the freshness window; their digest entries carry a date mark ('posted ~<date> (from posting text)' or 'date not stated'), and a detail-read null-date posting whose JD states a date yields posted_at_extracted on its event",
    "The digest counts line includes a per-source breakdown (e.g. '(2 LinkedIn · 2 Ashby)') and ashby match meta lines carry a ' · Ashby' tag",
    "The first-pass-over-Ashby footnote appears (the ashby known-ids set was empty at run start)",
    "Immediately re-running produces no duplicate evaluated events for any (source, source_id) pair",
    "Output contains no numeric score; exits 0"
  ]
},
{
  "id": 16,
  "scenario": "one-source-down",
  "prompt": "Same harness but JOBSEARCH_TEST_SCENARIO=one-source-down (every ashby search-jobs returns a retryable 502; linkedin succeeds via the happy fallback). Run job-search-run and show the digest.",
  "expectations": [
    "Retries the ashby 502s with backoff, opens the ashby circuit after two consecutive fully-failed ashby queries, and stops calling ashby for the rest of the run",
    "LinkedIn queries complete and their matches appear as normal — one source down never blanks the run",
    "Run health is 'partial (ashby unavailable)' and a footnote says Ashby was unreachable this run and the next run will retry",
    "runs/<id>.json lists ashby in sources_failed; exits 0 (partial, not a HALT)"
  ]
}
```

- [ ] **Step 3 — add evals 17 and 18** following eval 15/16's exact JSON shape:
  - **17, scenario `source-unsupported`:** expectations — surfaces E-SOURCE-UNSUPPORTED's
    footnote naming the fix (remove '<source>' from `search.sources`, or update the agent-data
    service); does NOT retry the 400 (retryable:false); linkedin results still land; Run health
    `partial (ashby unavailable)`; exits 0.
  - **18, scenario `legacy-source-swallow`:** expectations — detects the missing/mismatched
    `data.query.source` echo and surfaces E-SOURCE-IGNORED's footnote (the service predates
    source selection — only LinkedIn was searched); writes ZERO events with `"source":"ashby"`;
    the swallowed call's returned rows dedup against the genuine linkedin call's rows (no
    duplicate evaluated events); Run health `partial (ashby unavailable)`; exits 0.
- [ ] **Step 4 (verify):** `python3 -c "import json; json.load(open('skills/job-search-run/evals/evals.json'))"`
      → parses; run evals 15–18 + reworded 4 and 9 via the eval harness (skill-creator), paste
      outcomes into the Progress log.
- [ ] **Step 5 (commit):** `test(evals): multi-source scenarios — per-source partials, unsupported/ignored sources, null dates, first-pass footnote`

**→ Open PR1** (`feat/multi-source-core`): run the full Done-when gate minus the PR2/PR3 items;
paste the live-run transcript into the PR body.

---

## PR2 — cross-source semantic merge (branch `feat/cross-source-merge`)

### Task T12 [BLOCKS] — the merge rule + `same_role_as`

**Files:**
- Modify: `skills/job-search-run/SKILL.md` (step 3 + step 5)
- Modify: `shared/references/conventions.md` (event schema + fold + digest) (then `./scripts/build.sh`)

**Interfaces:** Produces `evaluated.same_role_as` (flat string `"<source>:<source_id>"`) and the
merged digest entry format eval 19 asserts.

- [ ] **Step 1 (green) — run SKILL.md step 3, append:**

```markdown
   **Cross-source merge (conservative).** After forming the NEW set, group rows that are the
   same real-world role seen on multiple sources: same company (allowing trivial name variants),
   same or equivalent role title, compatible location → one role. **When uncertain, treat as
   distinct — two detail reads are cheaper than a wrong merge.** For a merged group: ONE detail
   read, on the Ashby row when the group has one (its detail is complete and its URL is the
   company's live apply page), with the steer noting "also on <other source>"; the judgment
   applies to every row in the group.
```

  **Step 5, append to the event instructions:** "For a merged group, append one `evaluated`
  event per row (each with its own `source`/`source_id`/`source_url`/`posted_at`), all sharing
  the verdict fields; every NON-primary row's event also carries
  `"same_role_as":"<source>:<source_id>"` pointing at the primary (the row that got the detail
  read)."
- [ ] **Step 2 — conventions.md:** event schema — after `posted_at_extracted` add
  `"same_role_as":"<source>:<source_id> — OPTIONAL; this row is the same real-world role as
  that primary row>",` and extend the event-line contract: "`same_role_as` is a FLAT string —
  never a nested object (the `\"source_id\"`-appears-once rule is load-bearing for the grep
  extraction)". Fold rule — append: "a folded record whose `same_role_as` names another present
  record is an ALIAS of it — count and display the pair as one (the pipeline view and home
  counts treat aliases as one role)." Digest format — add the merged-entry link form:
  "`[view on company board](<ashby source_url>) · [also on LinkedIn](<linkedin source_url>)` —
  the canonical company-board link first; 'view' verbs, never 'apply'." Optionally note the
  earliest-signal phrasing: "when the JD-stated date meaningfully precedes the other source's
  `posted_at`, one qualitative clause is allowed — 'on the company's board days before
  LinkedIn — early'; never a numeric freshness score."
- [ ] **Step 3 (verify):** `./scripts/build.sh`; `python3 scripts/doc_lint.py --root .` clean.
- [ ] **Step 4 (commit):** `feat(merge): conservative cross-source same-role merge — same_role_as alias events, company-board-first digest links`

### Task T13 [BLOCKS] — merge eval

**Files:**
- Modify: `skills/job-search-run/evals/evals.json` (add eval 19)
- Modify: `examples/sample-digest.md` (one merged entry)

- [ ] **Step 1 (green) — eval 19** (scenario `multi-source` — the fixtures from T2 already
      contain the Acme pair): expectations — the Acme "Senior AI Engineer" appears as ONE digest
      entry with the company-board link first and an "also on LinkedIn" link; the single detail
      read for the pair went to the ashby row; jobs.jsonl carries TWO evaluated events sharing
      the verdict, the linkedin one bearing `same_role_as:"ashby:6e9a1f00-1111-4aaa-8bbb-2cc3dd4ee5f6"`;
      the Zephyr ashby-only row is NOT merged with anything; pipeline/home counts treat the Acme
      pair as one role; exits 0.
- [ ] **Step 2:** sample digest — convert one strong match to the merged link form from
      conventions.md → Digest format: a "view on company board" link to its `jobs.ashbyhq.com`
      URL, then " · ", then an "also on LinkedIn" link to the LinkedIn URL.
- [ ] **Step 3 (verify):** eval 19 via the harness; evals 15–18 still pass (no merge regression:
      eval 15's dedup expectation is unaffected because merge only changes which row gets the
      detail read plus the extra field); `python3 scripts/doc_lint.py --root .` clean.
- [ ] **Step 4 (commit):** `test(evals): cross-source merge — one entry, two events, alias counted once`

**→ Open PR2.**

---

## PR3 — Workday experimental (branch `feat/workday-experimental`)

### Task T14 [TUNE] — Workday enable flow, live-degradation proof, workday eval variant

**Files:**
- Modify: `skills/job-search-run/evals/evals.json` (add eval 20)
- Modify: `CHANGELOG.md` (Unreleased → Added line)

The mechanics are already generic (T2's `one-source-down` honors `JOBSEARCH_TEST_DOWN_SOURCE`;
T8 shipped the operator enable flow; T9 shipped the template comment). This task proves them.

- [ ] **Step 1 (green) — eval 20** (scenario `one-source-down`, per-case tweaks: export
      `JOBSEARCH_TEST_DOWN_SOURCE=workday` AND
      `sed -i.bak 's/sources: \["linkedin", "ashby"\]/sources: ["linkedin", "ashby", "workday"]/' <tmp>/config.yaml`):
      expectations — linkedin and ashby matches land normally; workday's failures open only ITS
      circuit; Run health `partial (workday unavailable)` with the outage footnote; exits 0.
- [ ] **Step 2 — live proof (real API, no shim):** in a sandboxed workspace with
      `sources: ["linkedin", "ashby", "workday"]`, run `job-search-run`; while Workday's
      upstream still 502s this completes `partial (workday unavailable)` with linkedin+ashby
      results intact. Paste the transcript into the Progress log. (If Workday has come up by
      execution time, the run is simply healthy 3-source — paste that instead and note it.)
- [ ] **Step 3:** CHANGELOG Unreleased → Added: "- Workday is available as an explicit opt-in
      experimental source (`search.sources: [..., \"workday\"]`); a failing source degrades the
      run to `partial`, never blocks it."
- [ ] **Step 4 (commit):** `feat(sources): workday ships as an explicit experiment — opt-in, partial-on-failure, live-verified`

**→ Open PR3. Then run the full Done-when gate; on all-green flip this plan to
`state: completed`, add `completed:`, move to `completed/`, update the index.**

---

## Self-review (author pass, done 2026-07-02 before execution)

- Spec coverage: design points 1–12 of the ratified Approach C map to T3–T11 (1→T4/T9, 2→T3,
  3→T4, 4→T12/T13, 5→T3/T5/T6, 6→T4/T6/T7, 7→T4/T5, 8→T4/T12, 9→T4/T8, 10→T8, 11→T2/T11,
  12→T10); hardening F9→T4/T6, F10→T1, F11/F12→T10, F13→T1. Deferred items are fenced in
  Non-goals.
- Name consistency: `search.sources`, `posted_at_extracted`, `same_role_as`,
  `E-SOURCE-UNSUPPORTED`, `E-SOURCE-IGNORED`, `partial (<source> unavailable)`,
  `degraded (job sources flaky)`, scenario and fixture names — all defined once in Shared
  vocabulary and used verbatim in every task.
- Placeholder scan: every code/config/JSON step carries its actual content; prose edits are
  surgical sentence replacements with the exact new text; the only executor-adapts spots are
  flagged inline (setup-workspace.sh variable name; TESTING.md section number; the multi-harness
  plan-filing judgment call).

## Progress log

- 2026-07-02 — plan authored (strategy session 2026-07-01; Approach C ratified). Execution not
  yet started.

## Decision log

- **Announced-default-on for Ashby** (absent `search.sources` → `["linkedin","ashby"]`): opt-in
  would make multi-source a dead feature for the existing install base; the announcement is
  structural (per-source counts, first-pass footnote, home Sources line), not stored state.
- **No seeding of first Ashby runs** — mark-seen-without-digesting is a call-count cap in a
  trenchcoat (violates the no-caps rule); the flood is bounded by limit/scan/dedup and labeled.
- **E-UPSTREAM-STRETCH keeps its name** with per-source semantics — renaming churns evals/docs
  for zero user value.
- **Quirks live in ONE contract file**, not per-source files — per-source files would fan out
  ×5 skills via build.sh and destroy the read-once property; a descriptor layer is the plugin
  system PRODUCT_SENSE still refuses.
- **Merge is conservative by design** — "when uncertain, treat as distinct"; the worst cross-host
  divergence degrades to duplicate tagged entries, never a wrong merge.
- **Eval workspaces pin `freshness: "any"`** — fixture `posted_at` values are static; a relative
  freshness window makes evals rot with the calendar (they already had, silently, by 2026-07-02).
- **The strategy doc is untracked in git-ignored `docs-private/`** — `doc_lint` walks the
  filesystem, so an untracked file under `docs/` either fails local index-completeness or, if
  indexed, fails CI's link check; outside `docs/` it is invisible to both. Never link it from
  tracked docs.
