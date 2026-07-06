---
title: Multi-Source Reconciliation — Greenhouse + Lever in, Workday out, wire-contract drift fixed
state: active
created: 2026-07-06
base_branch: feat/wave-1-multi-source
---

# Multi-Source Reconciliation — Greenhouse + Lever

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Follow the repo's execution protocol in
> [`../../PLANS.md`](../../PLANS.md): TDD + the per-commit doc-reviewer pass.
>
> **How this plan was produced.** A 2026-07-06 session verified the *live* agent-data Job Postings
> API (`agent-data docs f9a6ec16-…` + real `search-jobs`/`get-posting` probes) and found the API
> contract had **drifted** from what the unmerged Wave 1 branch documents. The user chose **full
> reconciliation, folded into `feat/wave-1-multi-source`**, no PR (merge to local `main`, test,
> then the user pushes). This plan is self-contained: every edit is spelled out with exact
> before/after text.

**Goal.** Make the client faithfully match the live API contract. The live listing now serves
**four** sources — `linkedin | ashby | greenhouse | lever` — and has **dropped Workday** (a hard
`400 validation_error`, not the "enum-live but 502s" experiment Wave 1 shipped). Error codes also
drifted (`unsupported_source`/`unsupported_field`/`invalid_pair` → `400 validation_error`;
`502 *_failed` → `503 upstream_unavailable`). Register Greenhouse + Lever end-to-end, remove
Workday, fix the wire-contract drift, and generalize the cross-source merge (now that two more
mergeable board sources exist) — all on `feat/wave-1-multi-source` so Wave 1 lands as an accurate
four-source release.

**Architecture.** Same as Wave 1: **one parameterized contract file + a compact per-source quirks
table**, no per-source contract files and **no descriptor/plugin layer** (still rejected — YAGNI
holds at four sources; interpreted indirection is what N host models execute divergently). The
existing per-`(query × source)` fan-out already generalizes; the work is (a) registering two
sources in the enum + quirks + shim + fixtures + evals, (b) deleting Workday, (c) retargeting the
documented error codes onto the `retryable` boolean the client already branches on, and (d) paying
down the `TODO-MERGE-SOURCE-PRIMARY` debt the new board sources bring due. Zero new event types;
config stays `version: 1`; no migration.

**Tech stack.** Markdown prose procedures (`shared/references/` + skills, fanned by
`scripts/build.sh`), Python 3.11 stdlib dev tooling (pytest, `scripts/doc_lint.py`,
philosophy_guard), the `tests/fake-agent-data` PATH shim + JSON fixtures, skill evals
(skill-creator harness), GitHub Actions.

## Global constraints

Every task implicitly includes these (copied from the enforced core beliefs + Wave 1):

- **Qualitative-never-numeric:** no scores/weights/thresholds anywhere in product output.
- **No call caps:** relevance decides how many searches / detail reads happen; freshness + dedup are
  the only containment. No seeding.
- **Config stays `version: 1`; all schema changes additive; the runner never writes config.**
- **`shared/references/*.md` is the single source of truth.** Hand-edit only the `shared/` original,
  then run `./scripts/build.sh` and commit the regenerated per-skill copies. CI fails if the copies
  are stale (`.github/workflows/ci.yml`: `build.sh` then `git status --porcelain skills` must be
  empty).
- **Same-commit contract flip:** when the source enum or an owned literal changes in
  `shared/references/`, update the matching `scripts/doc_lint.py` `DUP_SIGNATURES` regex in the
  *same commit* so the KB-duplication guard stays meaningful.
- **Live data for all proofs** (`[[live-data-for-all-tests]]`): the Done-when gate needs real
  Greenhouse + Lever search/detail and a real end-to-end run — never fixtures-only.

## Non-goals — explicitly OUT of scope (do not build)

- **No descriptor/plugin/source-registry layer.** Four sources still don't earn it; the quirks
  table *is* the per-source contract.
- **No per-query source targeting.** Still a deferred knob — every query runs against every enabled
  source.
- **No `TODO-ALIAS-STATUS-DIVERGENCE` work.** Adding sources does not trigger it (no pipeline action
  mutates one leg of an aliased pair). It stays parked in the tech-debt tracker.
- **No new response fields.** The API now exposes `published_at`, `staleness_status`, `apply_url`,
  `is_remote`, `workplace_type`, etc. Consuming them is a separate enhancement; this reconciliation
  keeps the existing field set.
- **No auto-apply, no numeric cost/credit surfacing, no `score`/`weight` field anywhere.**

---

## Ground truth (live-verified 2026-07-06 — the evidence every task depends on)

From `agent-data docs f9a6ec16-0bfd-44d8-b3ee-073776745ee7` and live probes:

- **Allowed sources:** `linkedin, ashby, greenhouse, lever` (docs param description + the
  `400` error message both enumerate exactly these). Omitted `--source` → `linkedin`.
- **Workday removed:** `agent-data … search-jobs --source workday` → HTTP 400,
  `code:"validation_error"`, `param:"source"`, `retryable:false`,
  message `"Unsupported source 'workday' for source. Allowed values: linkedin, ashby, greenhouse, lever."`
  (An arbitrary token like `foobar-not-a-source` returns the identical shape.)
- **Error-code drift** (docs): `422 validation_error` (bad param, `details[].loc`), `400 validation_error`
  (bad `fields=` **or** unsupported `source`; `error.param` identifies which; `retryable:false`),
  `503 upstream_unavailable` (`retryable:true`). Get-posting pair mismatch → `400 validation_error`
  (`retryable:false`). The `retryable` boolean is unchanged, so the client's retry branch still works;
  only the documented code strings + E-\* triggers are stale.
- **Greenhouse quirks (live):** `source_id` `<company>:<numeric>` (`zuora:7310605`); `source_url`
  `boards.greenhouse.io/<company>/jobs/<id>?gh_jid=<id>` (canonical apply page); **`posted_at`
  populated** (ISO); `salary_display` usually null; detail read works (`meta.mode:"live_detail"`),
  `employment_type` often absent (lands in `missing_fields` alongside `workplace_type`, `is_remote`, …).
- **Lever quirks (live):** `source_id` `<company>:<uuid>` (`zoox:f4746da4-…`); `source_url`
  `jobs.lever.co/<company>/<uuid>` (canonical apply page); **`posted_at` populated** (ISO w/
  microseconds); **`salary_display` can be raw HTML** (still free text — never parse, strip markup on
  display); `employment_type` `Full-time` (a third distinct enum casing); `missing_fields` minimal
  (e.g. `["is_listed"]`).

Probe transcripts are in this session's scratchpad (`search.greenhouse.json`, `search.lever.json`,
`detail.greenhouse.json`, `detail.lever.json`, `probe.workday.json`, `listing-docs.txt`).

---

## Task 1 — Reconcile the wire contract to live (enum + error codes + quirks)

Make the *documented + executed* contract match the live API: the four-source enum, the
`validation_error`/`upstream_unavailable` codes, and a four-column quirks table. This is the atomic
contract flip (enum literal + `doc_lint` guard move together).

**Files:**
- Modify: `shared/references/agent-data-contract.md` (enum lines 5, 27, 50; error lines 32, 43-45,
  58-60, 66-70; quirks table 74-84)
- Modify: `shared/references/errors.md` (E-BAD-QUERY :15, E-UPSTREAM-STRETCH :16, E-SOURCE-UNSUPPORTED
  :17, pair-mismatch note :22, detection :33)
- Modify: `skills/job-search-run/SKILL.md` (inline code refs: step 1 lines 55-58; step 4 lines 108-109)
- Modify: `scripts/doc_lint.py` (`DUP_SIGNATURES` regex :252)
- Regenerate: `skills/*/references/agent-data-contract.md` + `errors.md` (via `build.sh`)

- [ ] **Step 1 — `agent-data-contract.md` intro + enum (lines 3-6, 27, 50).**
  - Line 3 `One listing, three sources.` → `One listing, four sources.`
  - Line 5 `\`--source\` (\`linkedin | ashby | workday\`; omitted → \`linkedin\`)` →
    `` `--source` (`linkedin | ashby | greenhouse | lever`; omitted → `linkedin`) ``
  - Line 27 `[--source <linkedin|ashby|workday>]` → `[--source <linkedin|ashby|greenhouse|lever>]`
  - Line 50 `[--source <linkedin|ashby|workday>]` → `[--source <linkedin|ashby|greenhouse|lever>]`

- [ ] **Step 2 — `agent-data-contract.md` error codes.** Replace the drifted strings:
  - Line 32 (search `--source` rejection): `` `400 unsupported_source` (`error.param: "source"`, `retryable:false`) `` →
    `` `400 validation_error` (`error.param:"source"`, `retryable:false`; the message names the allowed sources) ``
  - Lines 43-45 (search Errors) → replace with:
    `` - **Errors:** `422 validation_error` (`details[].loc` names the bad param), `400 validation_error` (a bad `fields=` name OR an unsupported `--source`; `error.param` says which), `503 upstream_unavailable` (`retryable:true`). ``
  - Lines 58-60 (get-posting Errors) → replace with:
    `` - **Errors:** `400 validation_error` (`retryable:false`) — a request-contract failure; the common case is a `posting_id`/`source_url` **pair mismatch** (the row was re-indexed): do NOT retry, fall back to summary-only. `422 validation_error` (missing/invalid source_url), `503 upstream_unavailable` (`retryable:true`). ``
  - Lines 66-70 (retry paragraph) → replace `the 502s` with `the 503 \`upstream_unavailable\`s`;
    replace `Never retry \`invalid_pair\` / \`invalid_request\` / \`unsupported_field\`` with
    `Never retry a non-retryable \`validation_error\` (a bad pair, bad field, or unsupported source)`;
    replace `return 502` (line 68) with `return a retryable 503`. Keep the sentence
    **"Branch retries on the \`retryable\` boolean, not on parsing \`code\`"** and strengthen it:
    add `— the service collapses most 4xx to \`validation_error\` and uses \`error.param\` to name the field, so the boolean is the reliable signal.`

- [ ] **Step 3 — `agent-data-contract.md` quirks table (lines 74-84).** Replace the whole table with
  the four-source version (values from Ground truth):

```markdown
| | linkedin | ashby | greenhouse | lever |
|---|---|---|---|---|
| `source_id` | numeric string | Ashby posting UUID | `<company>:<numeric>` (e.g. `zuora:7310605`) | `<company>:<uuid>` (e.g. `zoox:f4746da4-…`) |
| `source_url` | `linkedin.com/jobs/view/…` + tracking params | clean canonical `jobs.ashbyhq.com/<company>/<uuid>` — **this IS the live apply page** (link it; never frame as auto-apply) | clean canonical `boards.greenhouse.io/<company>/jobs/<id>?gh_jid=<id>` — **IS the live apply page** | clean canonical `jobs.lever.co/<company>/<uuid>` — **IS the live apply page** |
| `posted_at` | date-only in search; full timestamp in detail | **null in BOTH** — a date often appears in the JD prose ("Job Posted: …"); extract it during the detail read | **populated** (ISO) in search + detail — freshness applies normally | **populated** (ISO) in search + detail — freshness applies normally |
| freshness | window applies normally | null rule applies (never drop null; see `conventions.md`) | window applies normally | window applies normally |
| latency / mode | live scrape (seconds) | indexed corpus (~ms); may include months-old or closed postings — the canonical link is how the user verifies openness | service-refreshed store (~ms); detail serves the stored snapshot first, live fallback on cache miss; may include older/closed postings | service-refreshed store (~ms); snapshot-first detail, live fallback on miss; may include older/closed postings |
| coverage | LinkedIn job search | broad crawl of public Ashby company boards | crawl of public Greenhouse company boards | crawl of public Lever company boards |
| `salary_display` | usually null; free text — never parse | usually null | usually null; free text — never parse | **may be raw HTML** — still FREE TEXT; never parse for numbers, strip/ignore markup when displaying |
| enums (`employment_type`, …) | `FULL_TIME` | `FullTime` — treat ALL cross-source enums as free text; never exact-match | often absent (→ `missing_fields`); when present, free text | `Full-time` — free text; a third distinct casing (reinforces: never exact-match) |
| `missing_fields` | usually `["application_url"]` | usually `[]` | may include `employment_type`, `workplace_type`, `is_remote`, … (treat as "not stated") | usually minimal (e.g. `["is_listed"]`) |
```

- [ ] **Step 4 — `errors.md` code triggers.**
  - E-BAD-QUERY (:15) When-cell: `\`422 invalid_request\` / \`400 unsupported_field\` on a search` →
    `\`422 validation_error\` / \`400 validation_error\` on a search (a bad param or \`fields=\`; \`error.param\` / \`details[].loc\` names it)`
  - E-UPSTREAM-STRETCH (:16) When-cell: `2 consecutive \`search-jobs\` 502s **against the same source**` →
    `2 consecutive retryable \`503 upstream_unavailable\`s on \`search-jobs\` **against the same source**`
  - E-SOURCE-UNSUPPORTED (:17) When-cell: `the service answers \`400 unsupported_source\` (\`error.param:"source"\`)` →
    `the service answers \`400 validation_error\` with \`error.param:"source"\` (its message names the allowed sources)`
  - Pair-mismatch note (:22): `**invalid_pair** (\`400\`, \`retryable:false\`) on \`get-posting\`: the \`jp_\`/\`source_url\` pair went stale` →
    `**Pair mismatch** — a \`400 validation_error\` (\`retryable:false\`) on \`get-posting\` whose \`error.param\` names \`posting_id\`/\`source_url\`: the \`jp_\`/\`source_url\` pair went stale`
  - Detection (:33): `502 → retry` → `a retryable 503 → retry`

- [ ] **Step 5 — `job-search-run/SKILL.md` inline code refs.**
  - Line 55: `A \`400 unsupported_source\` → E-SOURCE-UNSUPPORTED` →
    `A \`400 validation_error\` with \`error.param:"source"\` → E-SOURCE-UNSUPPORTED`
  - Line 56: `\`502 search_failed\` (retryable) → retry up to 3×` → `\`503 upstream_unavailable\` (retryable) → retry up to 3×`
  - Line 58: `\`422\`/\`400 unsupported_field\` → E-BAD-QUERY (name the bad param from \`details[].loc\`)` →
    `\`422\`/\`400 validation_error\` (a bad param or \`fields=\`) → E-BAD-QUERY (name the bad param from \`error.param\`/\`details[].loc\`)`
  - Lines 108-109: `\`400 invalid_pair\` (not retryable) → judge from summary … \`502 detail_fetch_failed\` (retryable) → retry/backoff` →
    `\`400 validation_error\` (not retryable — a \`posting_id\`/\`source_url\` pair mismatch) → judge from summary, note "detail link expired"; \`503 upstream_unavailable\` (retryable) → retry/backoff`

- [ ] **Step 6 — `doc_lint.py` enum guard (:252).**
  `(re.compile(r"linkedin \| ashby \| workday"), "job source enum"),` →
  `(re.compile(r"linkedin \| ashby \| greenhouse \| lever"), "job source enum"),`

- [ ] **Step 7 — Fan out + verify.**
  Run: `./scripts/build.sh`
  Run (must all pass):
  ```bash
  grep -c "linkedin | ashby | greenhouse | lever" shared/references/agent-data-contract.md   # ≥1
  grep -ic workday shared/references/agent-data-contract.md shared/references/errors.md        # 0 each
  python3 scripts/doc_lint.py                                                                   # clean
  python3 scripts/philosophy_guard.py 2>/dev/null || true                                       # clean if present
  python3 -m pytest -q                                                                          # green (shim/tests unchanged yet)
  git status --porcelain skills                                                                 # empty after the add below
  ```
  Expected: enum grep ≥1; `workday` count 0 in both shared files; doc_lint clean; pytest still green
  (no test depends on these docs yet).

- [ ] **Step 8 — Commit.**
  ```bash
  git add shared/references/agent-data-contract.md shared/references/errors.md \
          skills/job-search-run/SKILL.md scripts/doc_lint.py skills/*/references/
  git commit -m "fix(contract): reconcile wire contract to live — 4-source enum, validation_error/503 codes, gh+lever quirks"
  ```

---

## Task 2 — Retire Workday; write the honest four-source catalog

Delete every runtime claim that Workday is an enabled/experimental source, and describe the real
four sources honestly.

**Files:**
- Modify: `templates/config.example.yaml:9`
- Modify: `shared/references/conventions.md:28` (config-block comment)
- Modify: `shared/references/internals.md:94-96` ("Choose job sources")
- Modify: `skills/job-search-agent/SKILL.md:70-81` ("## Job sources" bullets)
- Modify: `skills/job-search/references/home.md:84` ("Tune the feed")
- Modify: `ARCHITECTURE.md:5` (intro source list)
- Modify: `docs/PRODUCT_SENSE.md` (the multi-source bullet Wave 1 added — the "Ashby live, Workday experimental" clause)
- Regenerate: `skills/*/references/conventions.md` + `internals.md` (via `build.sh`)

- [ ] **Step 1 — `templates/config.example.yaml:9`.** Replace the line with:
  ```yaml
  sources: ["linkedin", "ashby"]   # job sources each query runs against: linkedin | ashby | greenhouse | lever — add "greenhouse"/"lever" to search more company boards
  ```

- [ ] **Step 2 — `conventions.md:28`.** Replace the inline comment:
  `# ordered job sources … : linkedin | ashby | workday — omit the key for this default; workday is experimental (expect partial runs while upstream stabilizes)` →
  `# ordered job sources every query runs against: linkedin | ashby | greenhouse | lever — omit the key for this default; greenhouse/lever widen coverage across more company boards`

- [ ] **Step 3 — `internals.md:94-96`.** Replace the "Adding \"workday\"…" sentence:
  `Adding \`"workday"\` opts into the experimental source (expect partial runs while upstream stabilizes).` →
  `The default is \`["linkedin", "ashby"]\`; add \`"greenhouse"\` and/or \`"lever"\` to search more public company boards. One source failing never blocks the others.`

- [ ] **Step 4 — `job-search-agent/SKILL.md` Job sources (:75-77).** Replace the **workday** bullet
  with two honest bullets:
  ```markdown
  - **greenhouse** — a crawl of public Greenhouse company boards, served from a service-refreshed
    store (fast). Board links ARE the live apply pages. Postings carry real dates, so freshness
    filters normally.
  - **lever** — a crawl of public Lever company boards, served from a store (fast). Board links ARE
    the live apply pages. Postings carry real dates; some list salary as embedded HTML (shown as
    plain text, never parsed for numbers).
  ```
  (Leave the `linkedin` and `ashby` bullets and the "To disable a source…" paragraph intact.)

- [ ] **Step 5 — `home.md:84`.** In the "Tune the feed" bullet replace
  `add "workday" to try the experimental source — expect \`partial (workday unavailable)\` runs while its upstream stabilizes` →
  `add "greenhouse" or "lever" to search more company boards`

- [ ] **Step 6 — `ARCHITECTURE.md:5`.** Replace `LinkedIn and Ashby company-board postings (plus experimental Workday)` →
  `LinkedIn, Ashby, Greenhouse, and Lever company-board postings`.

- [ ] **Step 7 — `docs/PRODUCT_SENSE.md:104`.** Replace the parenthetical `(Ashby live, Workday experimental)` →
  `(Ashby, Greenhouse, and Lever live)`. Keep the "still refused: a descriptor/plugin layer" sentence.

- [ ] **Step 8 — Fan out + verify.**
  ```bash
  ./scripts/build.sh
  grep -rin workday shared/ skills/ templates/ ARCHITECTURE.md docs/PRODUCT_SENSE.md   # 0 hits
  python3 scripts/doc_lint.py                                                            # clean
  python3 -m pytest -q                                                                   # green
  ```
  Expected: zero `workday` hits in runtime docs (exec-plans/CHANGELOG history may still mention it —
  those are out of this grep's scope); doc_lint + pytest clean.

- [ ] **Step 9 — Commit.**
  ```bash
  git add templates/config.example.yaml shared/references/conventions.md shared/references/internals.md \
          skills/job-search-agent/SKILL.md skills/job-search/references/home.md ARCHITECTURE.md \
          docs/PRODUCT_SENSE.md skills/*/references/
  git commit -m "feat(sources): retire Workday (dropped upstream); document the real linkedin/ashby/greenhouse/lever catalog"
  ```

---

## Task 3 — Generalize the cross-source merge to N board sources (`TODO-MERGE-SOURCE-PRIMARY`)

Two new mergeable board sources bring the parked P3 debt due: the merge hardcodes "Ashby is always
the primary" and a two-name "also on LinkedIn" string, and run-health `<why>` can't name a
multi-source loss. Generalize all three; mark the debt resolved.

**Decision — primary selection (recorded in Decision log):** In a merged group the ONE detail read
goes to a **board-source row** (`ashby | greenhouse | lever`) — their `source_url` is the canonical
apply page and their detail is complete. If the group has several board sources, pick the one
earliest in the run's `search.sources` order (deterministic + user-tunable, consistent with the
existing "presentation order = config order" rule). A `linkedin` row is primary only when the group
has no board source.

**Files:**
- Modify: `skills/job-search-run/SKILL.md:81-84` (merge rule) and `:122` (run-health line)
- Modify: `shared/references/conventions.md:153` (merged-entry link copy) and `:153-157` (run-health `<why>`)
- Modify: `shared/references/errors.md:16` (E-UPSTREAM-STRETCH run-health phrasing)
- Modify: `docs/exec-plans/tech-debt-tracker.md:65-74` (mark `TODO-MERGE-SOURCE-PRIMARY` resolved)
- Regenerate: `skills/*/references/conventions.md` + `errors.md` (via `build.sh`)

- [ ] **Step 1 — `job-search-run/SKILL.md:81-84` merge rule.** Replace the "on the Ashby row when the
  group has one …" sentence with:
  `For a merged group: ONE detail read, on a **board-source row** — \`ashby\`, \`greenhouse\`, or \`lever\`, whose \`source_url\` is the company's canonical live apply page and whose detail is complete. If the group has several board sources, pick the one earliest in the run's \`search.sources\` order; a \`linkedin\` row is the target only when the group has NO board source. The steer notes "also on <the other sources>"; the judgment applies to every row in the group.`

- [ ] **Step 2 — `conventions.md` merged-entry copy + `same_role_as` parse note.** Replace the merged-entry sentence (`:153`) with:
  `A cross-source role merged via \`same_role_as\` renders as ONE entry whose link line shows every source — the **primary board source's canonical link first**, then \`· [also on <Source>](<other source_url>)\` for each other row in \`search.sources\` order, e.g. \`[view on company board](<primary board source_url>) · [also on LinkedIn](<linkedin source_url>)\`. 'view' verbs, never 'apply'. (The primary is the board-source row that got the detail read — see the merge rule in \`job-search-run\` step 3; a \`linkedin\`-only group has no company-board link and shows just its LinkedIn link.)`

  Then, in the SAME file's §jobs.jsonl, make the `same_role_as` parse safe for composite ids
  (greenhouse/lever `source_id`s contain a colon): at the `same_role_as` definition (`:63`) append
  ` — parse by splitting on the FIRST colon only (e.g. same_role_as:"greenhouse:acme:7310605" → source "greenhouse", source_id "acme:7310605")`,
  and at the fold operation's alias clause (`:93`) note the alias lookup uses that first-colon split.

- [ ] **Step 3 — run-health `<why>` (three places, one wording).**
  - `conventions.md:153-157` — replace the `<why>` enumeration with:
    `where \`<why>\` is one of \`N errors\` (scattered per-query/per-posting errors) · \`<source> unavailable\` (one whole source lost this run) · \`<sourceA>, <sourceB> unavailable\` (several — but not all — sources lost, each named in \`search.sources\` order) · \`all sources unavailable\` (every enabled source lost). Precedence: name lost source(s) over counting errors; \`all sources unavailable\` only when EVERY enabled source is lost, otherwise list the specific ones.`
  - `job-search-run/SKILL.md:122` — replace `any lost source → \`partial (<source> unavailable)\`; all lost → \`partial (all sources unavailable)\`` with
    `one lost source → \`partial (<source> unavailable)\`; several (not all) → \`partial (<sourceA>, <sourceB> unavailable)\` naming each in \`search.sources\` order; all lost → \`partial (all sources unavailable)\``
  - `errors.md:16` (E-UPSTREAM-STRETCH Run-effect cell) — replace `Run health \`partial (<source> unavailable)\` / \`partial (all sources unavailable)\`` with
    `Run health \`partial (<lost source(s) unavailable — each named in search.sources order>)\` / \`partial (all sources unavailable)\` when every enabled source is lost`

- [ ] **Step 4 — resolve the debt in `tech-debt-tracker.md:65-74`.** Immediately under the
  `### P3 — merged-entry strings hardcode LinkedIn/Ashby …` heading, insert a resolution line
  (mirroring the `**Resolved 2026-06-08 by removal.**` style at :58):
  `**Resolved 2026-07-06 by [2026-07-06-multi-source-reconciliation-greenhouse-lever](2026-07-06-multi-source-reconciliation-greenhouse-lever.md).** Greenhouse + Lever are the third/fourth mergeable board sources; the merged-entry copy, the primary-selection rule (board-source row, earliest in \`search.sources\`), and run-health \`<why>\` are now N-source. Kept as a resolved record.`

- [ ] **Step 5 — Fan out + verify.**
  ```bash
  ./scripts/build.sh
  grep -n "board-source row" skills/job-search-run/SKILL.md           # ≥1
  grep -in "also on LinkedIn" shared/references/conventions.md         # still present as the EXAMPLE only
  grep -n "several — but not all" shared/references/conventions.md     # ≥1
  python3 scripts/doc_lint.py && python3 -m pytest -q                  # clean + green
  ```

- [ ] **Step 6 — Commit.**
  ```bash
  git add skills/job-search-run/SKILL.md shared/references/conventions.md shared/references/errors.md \
          docs/exec-plans/tech-debt-tracker.md skills/*/references/
  git commit -m "feat(merge): generalize cross-source merge to N board sources; resolve TODO-MERGE-SOURCE-PRIMARY"
  ```

---

## Task 4 — Update the fake-agent-data shim + its tests to the live error contract (TDD)

The shim still emits the OLD codes (`unsupported_source`, `search_failed`, `detail_fetch_failed`,
`invalid_request`, `invalid_pair`). Retarget them onto the live codes so tests exercise reality.
Red first, then green.

**Files:**
- Modify: `tests/test_fake_agent_data.py` (code assertions)
- Modify: `tests/fake-agent-data` (emitted error codes)

- [ ] **Step 1 — Write the failing assertions.** In `tests/test_fake_agent_data.py`, change:
  - `test_get_posting_detail_fetch_failed_is_retryable` (:50): `body["code"] == "detail_fetch_failed"` → `body["code"] == "upstream_unavailable"`
  - `test_bad_query_422_on_sentinel_location` (:80): `body["code"] == "invalid_request"` → `body["code"] == "validation_error"`
  - `test_one_source_down_fails_only_the_down_source` (:109): `body["code"] == "search_failed"` → `body["code"] == "upstream_unavailable"`
  - `test_source_unsupported_400s_non_linkedin` (:118): `body["code"] == "unsupported_source"` → `body["code"] == "validation_error"` (keep the `param == "source"` and `retryable is False` asserts)
  - `test_unknown_source_value_is_rejected` (:131): `["error"]["code"] == "unsupported_source"` → `== "validation_error"`

- [ ] **Step 2 — Run; verify red.**
  Run: `python3 -m pytest -q tests/test_fake_agent_data.py`
  Expected: the five edited tests FAIL (shim still emits old codes).

- [ ] **Step 3 — Retarget the shim's codes.** In `tests/fake-agent-data`:
  - `:73` `err("unsupported_source", f"source {src!r} is not supported", False, param="source")` →
    `err("validation_error", f"Unsupported source {src!r} for source. Allowed values: linkedin, ashby, greenhouse, lever.", False, param="source")`
  - `:75` `err("search_failed", f"{src} search failed", True)` → `err("upstream_unavailable", f"{src} search failed", True)`
  - `:77` `err("search_failed", "upstream fetch failed", True)` → `err("upstream_unavailable", "upstream fetch failed", True)`
  - `:83` `err("invalid_request", f"location {loc!r} is not a recognized value", False, param="location", details=[…])` →
    same call but code `"validation_error"` (keep message/param/details)
  - `:93` `err("invalid_pair", "posting_id/source_url mismatch", False)` →
    `err("validation_error", "posting_id/source_url mismatch", False, param="posting_id")`
  - `:95` `err("detail_fetch_failed", "upstream detail fetch failed", True)` →
    `err("upstream_unavailable", "upstream detail fetch failed", True)`
  (Leave `quota_exceeded` :79 unchanged — quota is not part of the wire-code drift.)

- [ ] **Step 4 — Run; verify green.**
  Run: `python3 -m pytest -q tests/test_fake_agent_data.py`
  Expected: all pass.

- [ ] **Step 5 — Commit.**
  ```bash
  git add tests/fake-agent-data tests/test_fake_agent_data.py
  git commit -m "test(shim): emit the live error contract — validation_error / upstream_unavailable"
  ```

---

## Task 5 — Register Greenhouse + Lever in the shim (allow-list + fixtures + tests, TDD)

**Files:**
- Modify: `tests/fake-agent-data:17` (`SRC_ALLOWED`)
- Create: `tests/fixtures/happy/search-jobs.greenhouse.json`, `get-posting.greenhouse.json`,
  `search-jobs.lever.json`, `get-posting.lever.json`
- Modify: `tests/test_fake_agent_data.py` (new per-source tests)

- [ ] **Step 1 — Write failing tests.** Append to `tests/test_fake_agent_data.py`:
```python
def test_greenhouse_echoes_source_and_populated_posted_at():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "greenhouse"])
    data = json.loads(r.stdout)["data"]
    assert data["query"]["source"] == "greenhouse"
    assert all(row["source"] == "greenhouse" and row["posted_at"] for row in data["results"])

def test_lever_salary_html_passes_through_untouched():
    r = shim(["call", LISTING, "search-jobs", "--keywords", "x", "--source", "lever"])
    data = json.loads(r.stdout)["data"]
    assert data["query"]["source"] == "lever"
    assert data["results"][0]["source"] == "lever" and data["results"][0]["posted_at"]
    assert "<div>" in data["results"][0]["salary_display"]  # raw HTML preserved verbatim

def test_get_posting_greenhouse_and_lever_route_per_source():
    gh = shim(["call", LISTING, "get-posting", "--posting_id", "jp_gh0000000001",
               "--source_url", "u", "--source", "greenhouse"])
    assert json.loads(gh.stdout)["data"]["title"] == "Senior AI Engineer"
    lv = shim(["call", LISTING, "get-posting", "--posting_id", "jp_lv0000000001",
               "--source_url", "u", "--source", "lever"])
    assert json.loads(lv.stdout)["data"]["employment_type"] == "Full-time"
```

- [ ] **Step 2 — Run; verify red.**
  Run: `python3 -m pytest -q tests/test_fake_agent_data.py -k "greenhouse or lever"`
  Expected: FAIL — `greenhouse`/`lever` rejected by `SRC_ALLOWED` (validation_error) and no fixtures.

- [ ] **Step 3 — Add to the allow-list.** `tests/fake-agent-data:17`
  `SRC_ALLOWED = ("linkedin", "ashby", "workday")` → `SRC_ALLOWED = ("linkedin", "ashby", "greenhouse", "lever")`

- [ ] **Step 4 — Create fixtures** (modeled on the live probe shapes):

  `tests/fixtures/happy/search-jobs.greenhouse.json`:
```json
{ "data": { "status": "completed", "warnings": [], "results": [
  { "id": "jp_gh0000000001", "source_id": "acme:7310605",
    "source_url": "https://boards.greenhouse.io/acme/jobs/7310605?gh_jid=7310605",
    "title": "Senior AI Engineer", "company_name": "Acme", "location_display": "Remote, US",
    "salary_display": null, "posted_at": "2026-05-15T19:01:28", "detail_available": true, "source": "greenhouse" },
  { "id": "jp_gh0000000002", "source_id": "acme:7460760",
    "source_url": "https://boards.greenhouse.io/acme/jobs/7460760?gh_jid=7460760",
    "title": "Staff Platform Engineer", "company_name": "Acme", "location_display": "San Francisco, CA",
    "salary_display": null, "posted_at": "2026-06-23T13:18:51", "detail_available": true, "source": "greenhouse" }
] } }
```
  `tests/fixtures/happy/get-posting.greenhouse.json`:
```json
{ "data": { "id": "jp_gh0000000001", "title": "Senior AI Engineer", "company_name": "Acme",
  "location_display": "Remote, US", "employment_type": null, "posted_at": "2026-05-15T19:01:28",
  "description_markdown": "## About Acme\n\nWe are hiring a Senior AI Engineer to build LLM-powered products in Python. Remote within the US.\n",
  "missing_fields": ["employment_type", "workplace_type", "is_remote"] } }
```
  `tests/fixtures/happy/search-jobs.lever.json`:
```json
{ "data": { "status": "completed", "warnings": [], "results": [
  { "id": "jp_lv0000000001", "source_id": "acme:f4746da4-8eb8-43e2-b7ce-bf3c7cf9640d",
    "source_url": "https://jobs.lever.co/acme/f4746da4-8eb8-43e2-b7ce-bf3c7cf9640d",
    "title": "Senior AI Engineer", "company_name": "Acme", "location_display": "Remote (US)",
    "salary_display": "<div><strong>Base Salary Range</strong></div>\n<div>$180,000 – $240,000</div>",
    "posted_at": "2026-05-04T23:11:01.125000", "detail_available": true, "source": "lever" }
] } }
```
  `tests/fixtures/happy/get-posting.lever.json`:
```json
{ "data": { "id": "jp_lv0000000001", "title": "Senior AI Engineer", "company_name": "Acme",
  "location_display": "Remote (US)", "employment_type": "Full-time", "posted_at": "2026-05-04T23:11:01.125000",
  "description_markdown": "Acme builds autonomy software. We want a Senior AI Engineer (Python, LLMs), remote in the US.\n",
  "missing_fields": ["is_listed"] } }
```

- [ ] **Step 5 — Run; verify green.**
  Run: `python3 -m pytest -q tests/test_fake_agent_data.py`
  Expected: all pass (the new three + the full suite).

- [ ] **Step 6 — Commit.**
  ```bash
  git add tests/fake-agent-data tests/test_fake_agent_data.py tests/fixtures/happy/
  git commit -m "test(sources): register greenhouse+lever in the shim — allow-list, fixtures, per-source tests"
  ```

---

## Task 6 — Reconcile + extend the runner evals

**Files:**
- Modify: `skills/job-search-run/evals/evals.json`
- Create: `tests/fixtures/multi-source/search-jobs.greenhouse.json`,
  `tests/fixtures/multi-source/get-posting.greenhouse.jp_ghacme01.json`

- [ ] **Step 1 — Fix eval 17 (`source-unsupported`) code drift.** In its `prompt`, replace
  `a non-retryable 400 unsupported_source with error.param 'source'` →
  `a non-retryable 400 validation_error with error.param 'source'`. (Expectations already say
  "E-SOURCE-UNSUPPORTED's footnote" and "Does NOT retry the 400" — no change.)

- [ ] **Step 2 — Replace the Workday eval (id 20) with a Greenhouse one-source-down.** Workday is
  gone, so its `sed`-enables-workday eval is invalid. Replace the whole id-20 object with:
```json
    {
      "id": 20,
      "scenario": "one-source-down",
      "prompt": "Same harness but JOBSEARCH_TEST_SCENARIO=one-source-down with two per-case tweaks that make greenhouse the failing source: (a) export JOBSEARCH_TEST_DOWN_SOURCE=greenhouse (every greenhouse search-jobs returns a retryable 503; linkedin succeeds via the happy fallback and ashby returns its happy-fallback fixture row), and (b) enable greenhouse in the sandbox config via `sed -i.bak 's/sources: [\"linkedin\", \"ashby\"]/sources: [\"linkedin\", \"ashby\", \"greenhouse\"]/' <tmp>/config.yaml && rm -f <tmp>/config.yaml.bak`. Run job-search-run and show the digest.",
      "expectations": [
        "Retries the greenhouse 503s with backoff, opens the greenhouse circuit after two consecutive fully-failed greenhouse queries, and stops calling greenhouse for the rest of the run",
        "LinkedIn and Ashby queries complete and their matches appear as normal — one source down never blanks the run",
        "Run health is 'partial (greenhouse unavailable)' and a footnote says Greenhouse was unreachable this run and the next run will retry",
        "runs/<id>.json lists greenhouse in sources_failed and both linkedin and ashby in sources_searched; exits 0 (partial, not a HALT)"
      ]
    }
```

- [ ] **Step 3 — Add eval 21: four-source fan-out with populated dates + Lever HTML salary.** Append
  (before the closing `]`):
```json
    ,{
      "id": 21,
      "scenario": "multi-source",
      "prompt": "Same multi-source harness, but the sandbox config ships search.sources [\"linkedin\", \"ashby\", \"greenhouse\", \"lever\"] (edit config.yaml before running). linkedin+ashby return their happy/multi-source fixtures; greenhouse returns 2 rows with populated posted_at; lever returns 1 row with populated posted_at and a salary_display containing raw HTML. Run job-search-run against <tmp> and show the digest + jobs.jsonl.",
      "expectations": [
        "Runs one search-jobs per (enabled query × each of the four enabled sources), passing --source on every call, and verifies each echoed data.query.source matches the request",
        "Every evaluated event's source is copied from its result row (greenhouse rows → 'greenhouse', lever rows → 'lever'); no hardcoded literal",
        "Greenhouse and Lever rows have populated posted_at and are filtered by the freshness window normally (no null-date footnote for them)",
        "The Lever row's HTML salary_display is shown as plain text and NEVER parsed into a number; output carries no numeric score or dollar figure derived from it",
        "The digest counts line's per-source breakdown names all searched sources (e.g. '(… LinkedIn · … Ashby · … Greenhouse · … Lever)') and match meta lines carry the correct ' · <Source>' tag",
        "Immediately re-running produces no duplicate evaluated events for any (source, source_id) pair; exits 0"
      ]
    }
```

- [ ] **Step 4 — Add eval 22: generalized merge primary (Greenhouse over LinkedIn).** Append:
```json
    ,{
      "id": 22,
      "scenario": "multi-source",
      "prompt": "Same as eval 21's four-source config, focused on the cross-source duplicate. linkedin returns Acme 'Senior AI Engineer' (source_id 1001, Remote US). greenhouse returns the SAME Acme 'Senior AI Engineer' (source_id acme:7310605, posting jp_ghacme01, Remote US, populated posted_at). Run job-search-run against <tmp> and show the digest + jobs.jsonl.",
      "expectations": [
        "Recognizes the two Acme 'Senior AI Engineer' rows (linkedin 1001 + greenhouse acme:7310605) as ONE real-world role and merges the pair",
        "Spends exactly ONE detail read, and that read is on the GREENHOUSE row (jp_ghacme01 — the company board), NOT the linkedin row (the primary is a board source, generalized beyond Ashby)",
        "The merged role renders as ONE digest entry whose link line shows the greenhouse company-board link first, then an 'also on LinkedIn' link — '[view on company board](https://boards.greenhouse.io/acme/jobs/7310605?gh_jid=7310605) · [also on LinkedIn](https://www.linkedin.com/jobs/view/1001)' ('view' verbs, never 'apply')",
        "jobs.jsonl carries TWO evaluated events sharing the verdict; the linkedin event bears same_role_as:'greenhouse:acme:7310605' and the greenhouse event bears none",
        "The counts line counts rows, not merged roles; output has no numeric score; exits 0"
      ]
    }
```

- [ ] **Step 5 — Add the merge-eval fixtures.**
  `tests/fixtures/multi-source/search-jobs.greenhouse.json`:
```json
{ "data": { "status": "completed", "warnings": [], "results": [
  { "id": "jp_ghacme01", "source_id": "acme:7310605",
    "source_url": "https://boards.greenhouse.io/acme/jobs/7310605?gh_jid=7310605",
    "title": "Senior AI Engineer", "company_name": "Acme", "location_display": "Remote, US",
    "salary_display": null, "posted_at": "2026-05-15T19:01:28", "detail_available": true, "source": "greenhouse" }
] } }
```
  `tests/fixtures/multi-source/get-posting.greenhouse.jp_ghacme01.json`:
```json
{ "data": { "id": "jp_ghacme01", "title": "Senior AI Engineer", "company_name": "Acme",
  "location_display": "Remote, US", "employment_type": null, "posted_at": "2026-05-15T19:01:28",
  "description_markdown": "Acme is hiring a Senior AI Engineer (Python, LLMs), remote in the US.\n",
  "missing_fields": ["employment_type"] } }
```

- [ ] **Step 6 — Verify + commit.**
  ```bash
  python3 -c "import json; d=json.load(open('skills/job-search-run/evals/evals.json')); ids=[c['id'] for c in d['evals']]; assert ids==sorted(ids) and len(ids)==len(set(ids)), ids; print('evals ok', ids)"
  grep -in workday skills/job-search-run/evals/evals.json   # 0
  git add skills/job-search-run/evals/evals.json tests/fixtures/multi-source/
  git commit -m "test(evals): reconcile source-unsupported code; swap workday eval for greenhouse; add 4-source + generalized-merge evals"
  ```

---

## Task 7 — Full gate suite, LIVE proof, housekeeping, and merge to local main

- [ ] **Step 1 — Static gate suite (on the branch).**
  ```bash
  python3 -m pytest -q                    # all green
  python3 scripts/doc_lint.py             # clean
  python3 scripts/philosophy_guard.py 2>/dev/null || true   # clean if present
  ./scripts/build.sh && git status --porcelain skills        # empty (copies already committed)
  python3 -c "import json; json.load(open('skills/job-search-run/evals/evals.json'))"   # parses
  ```

- [ ] **Step 2 — LIVE end-to-end proof** (`[[live-data-for-all-tests]]` — real API, no fixtures).
  In a throwaway sandbox workspace with `search.sources: ["linkedin", "ashby", "greenhouse", "lever"]`
  and a small brief, run one real `job-search-run` pass. **Record in the Progress log:**
  - the 5-line terminal summary + the digest's counts line showing a **per-source breakdown that
    includes Greenhouse and Lever**;
  - a Greenhouse and a Lever match each rendering with its canonical apply link and a real
    `posted_at`-based date (no "date not stated" for them);
  - an **immediate re-run showing zero new** (dedup by `(source, source_id)` holds for the new sources);
  - the **Workday-gone probe**:
    `agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 search-jobs --keywords x --limit 1 --source workday`
    → `400 validation_error`, `param:"source"`, `retryable:false`.
  - If a real cross-source duplicate appears, confirm the detail read landed on the board-source row
    and the merged entry links the board source first (the generalized primary). If none appears
    naturally, note that and rely on eval 22.

- [ ] **Step 3 — Run the new/updated evals live** (skill-creator harness) for
  `skills/job-search-run/evals/evals.json` ids 15-22; record pass/fail in the Progress log. Any
  failure blocks the merge.

- [ ] **Step 4 — Housekeeping edits.**
  - `CHANGELOG.md`: add an entry — "Job sources: added Greenhouse and Lever; removed Workday (dropped
    upstream); wire error codes reconciled to `validation_error`/`upstream_unavailable`."
  - `docs/exec-plans/index.md`: add this plan to the active list (match the existing row format).
  - `TESTING.md`: mirror the Ashby live-test recipe (~:680-698) for Greenhouse and Lever; update any
    source-list/enum mention and refresh the pytest count if one is cited.
  - `docs/exec-plans/active/2026-07-02-wave-1-multi-source.md`: add a Progress-log line — "2026-07-06:
    the multi-source reconciliation plan folded into this branch **removed the experimental Workday
    track** (API dropped it — now a hard 400) and added Greenhouse + Lever; see
    `2026-07-06-multi-source-reconciliation-greenhouse-lever.md`."
  - Commit: `git add -A && git commit -m "docs: changelog + plan index + TESTING recipes + Wave-1 pointer for gh/lever reconciliation"`

- [ ] **Step 5 — Merge to LOCAL main; hand off.** (User directive: **no PR** — merge locally, test,
  the user pushes.)
  ```bash
  git checkout main
  git merge --no-ff feat/wave-1-multi-source -m "merge: Wave 1 multi-source + greenhouse/lever reconciliation"
  python3 -m pytest -q && python3 scripts/doc_lint.py && ./scripts/build.sh && git status --porcelain skills
  ```
  Expected: clean merge; the full gate suite green on `main`; `skills` porcelain empty. **Do NOT
  push.** Report the merge result + the live-proof digest and hand off to the user to test and push.
  Post-merge lifecycle (per `docs/PLANS.md`): once the user confirms, flip BOTH this plan and the Wave 1
  plan to `state: completed` and move them to `docs/exec-plans/completed/`.

---

## Done-when (the gate — all must hold before merge)

- [ ] `python3 -m pytest -q` green; `scripts/doc_lint.py` clean; philosophy_guard clean; `build.sh`
      second run a no-op with `skills` porcelain empty; `evals.json` parses with contiguous unique ids.
- [ ] `grep -rin workday shared/ skills/ templates/ ARCHITECTURE.md docs/PRODUCT_SENSE.md` → 0 hits
      (runtime docs carry no Workday claim); the quirks table + enum name exactly
      `linkedin | ashby | greenhouse | lever`.
- [ ] LIVE: a real four-source `job-search-run` digest with a per-source breakdown including
      Greenhouse + Lever, real `posted_at` dates on gh/lever matches, a zero-new re-run, and the
      Workday `400 validation_error` probe — all pasted into the Progress log.
- [ ] LIVE: evals 15-22 pass on the skill-creator harness (incl. the greenhouse-primary merge, eval 22).
- [ ] `TODO-MERGE-SOURCE-PRIMARY` marked resolved; `feat/wave-1-multi-source` merged into local `main`
      with the gate suite green on `main`; **not pushed** (handed to the user).

## Progress log

_(Fill during execution — per the repo protocol, paste the live transcripts here.)_

## Decision log

- **2026-07-06 — Full reconciliation, folded into `feat/wave-1-multi-source` (user).** The live API
  had drifted (Workday dropped to a hard 400; Greenhouse + Lever added; error codes →
  `validation_error`/`upstream_unavailable`). Rather than merge a stale Wave 1 and fix forward, fold
  the reconciliation into the unmerged branch so Wave 1 lands accurate. **No PR** — merge to local
  `main`, test, user pushes.
- **2026-07-06 — Still no descriptor/plugin layer.** Four sources don't earn it; the quirks table is
  the per-source contract. (Wave 1's "a fourth source earns it" was a trigger to *reconsider*, not a
  commitment — reconsidered and declined; YAGNI.)
- **2026-07-06 — Merge primary = board-source row, earliest in `search.sources`.** Board sources
  (ashby/greenhouse/lever) have canonical apply pages + complete detail, so they outrank LinkedIn for
  the single detail read; ties broken by config order (deterministic, user-tunable, consistent with
  the existing "presentation order = config order" rule). LinkedIn is primary only for a LinkedIn-only
  group.
- **2026-07-06 — Retry stays keyed on the `retryable` boolean.** The service collapses most 4xx to
  `validation_error` and uses `error.param` to name the field, so classifying on the boolean (+
  `param`) is more robust than parsing code strings — the drift fix reinforces the existing rule
  rather than replacing it.
