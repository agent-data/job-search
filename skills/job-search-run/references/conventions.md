# Workspace conventions & file contracts

The **workspace** (default the hidden `~/.job-search/`; an existing visible `~/job-search/` is **adopted**, not replaced — see `internals.md`) is PRIVATE per-user data — never committed to a public repo.

```
~/.job-search/
  config.yaml                # queries + schedule (human terms only; NO budgets/score thresholds)
  preferences.md             # Job Preferences Brief — prose only
  resumes/master.md          # base resume; resumes/tailored/ for generated ones (Plan C)
  jobs.jsonl                 # append-only EVENT log; current state = fold by source_id
  runs/<run_id>.json         # per-run audit log
  reports/<date>-digest.md   # human digest per run
  .gitignore                 # deny-all (from templates/workspace.gitignore)
```
**Discovery & OS state:** skills never hard-code the workspace path — they find it with the Discovery
procedure in `internals.md` (registry → `~/.job-search/` → legacy `~/job-search/` → first-run). The registry
and the discovery/first-run/scheduling rules live in `internals.md`.

## config.yaml
```yaml
version: 1
workspace:
  preferences_path: "preferences.md"
  master_resume_path: "resumes/master.md"
queries:
  - { id: "ai-eng-remote", keywords: "AI engineer", location: "United States", limit: 25, enabled: true }
search:
  freshness: "past-2-weeks"  # any | past-week | past-2-weeks | past-month — client-side recency filter on posted_at (no API date param)
  detail_model: "haiku"      # model the per-posting detail subagents use: haiku | sonnet | opus | inherit
schedule:
  frequency: "daily"         # hourly | every-2-hours | every-6-hours | daily | weekly → /loop interval (24h for daily)
  time: "08:00"              # informational under /loop (loop fires on an interval, not at a wall-clock time)
  timezone: "America/Los_Angeles"
notify:
  digest_path_template: "reports/{date}-digest.md"
  desktop_notify_on_block: true
```
The **`search` block** tunes the feed: `freshness` is a client-side recency window on `posted_at` (the API has
no date param; `any` = no filter); `detail_model` is the model the runner's per-posting detail subagents use
(`inherit` = the run's own model). **`queries[].limit`** (1–100, default 25) is the per-query feed size — pull
generously across several varied queries rather than one giant pull; there is no pagination, so breadth +
frequency + dedup accumulate coverage. Query construction (incl. deriving "remote") lives in `internals.md`.

`run_id` format: UTC timestamp `YYYY-MM-DDTHH-MM-SSZ` (hyphens, not colons, in the time component — safe as a filename on every platform). `<date>` for digests: `YYYY-MM-DD` (local tz).

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

**Event-line contract** (the operations below depend on it): one event per line; each line is a single-line
JSON object — never pretty-printed; every event carries a non-empty `"source_id"`; the literal key
`"source_id"` appears exactly once per line. Validate an event against this contract before appending it.

Operations (no helper script — perform these exactly):
- **Known ids** (the dedup set; missing file = empty set):
  ```bash
  grep -o '"source_id"[[:space:]]*:[[:space:]]*"[^"]*"' "$WS/jobs.jsonl" 2>/dev/null | cut -d'"' -f4 | sort -u
  ```
- **Append one event** (the heredoc keeps quoting safe — apostrophes in `reasoning` are fine):
  ```bash
  cat >> "$WS/jobs.jsonl" <<'EOF'
  {"event":"evaluated","ts":"…","source_id":"…",…}
  EOF
  ```
- **Current state (fold):** Read `jobs.jsonl` and fold in-context — group events by `source_id`, later
  events override earlier per field, drop the `event` key. The pipeline view = the folded records tallied
  by `status` (plus the `needs_human_check: true` count).

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
against a posting (e.g. "Remote within the US, or SF Bay Area onsite"). Two front-matter dates sit near the
top: `created_at:` (origin, preserved across updates) and `updated_at:` (last change). **Staleness is measured
from `updated_at`** (fall back to `created_at` for briefs written before `updated_at` existed).

## Relevance vocabulary (qualitative — NO numbers)
- **relevant**: boolean. False only when a must-have/dealbreaker is clearly violated.
- **match**: `strong` (hits must-haves + most strong preferences) | `moderate` (solid, some gaps) |
  `weak` (relevant but thin) | `null` (when not relevant).
- **unknowns**: brief criteria the posting doesn't address ("not stated"). NEVER counted against a posting.
- **needs_human_check**: true when a must-have/dealbreaker can't be confirmed from the posting. When true, write the specific question to resolve into the `reasoning` field (e.g. "Remote policy not stated — confirm before applying").
- **dealbreakers_hit**: list of must-haves/dealbreakers observably violated.

## Digest format (reports/<date>-digest.md)
```
# Job search digest — <date>
Run health: healthy
9 new postings · 3 strong · 2 moderate · 1 weak · 3 filtered out · <n> searches · <m> detail reads

## Strong matches
- **<title>** — <company> — <location>
  <one-line reasoning>.  [view](<source_url>)
  ⚠ confirm: <needs_human_check question, if any>

## Moderate matches
…

## Weak matches
…

## Filtered out (not relevant): 3
<one line each: title — company — why rejected>

<footnotes: stale detail links, partial failures, unidentifiable (null source_id) rows, brief-age nudge>
```
Strong first. Always show the Run health line and the counts. Run health is one of `healthy` |
`partial (N errors)` | `degraded (LinkedIn flaky)` | `blocked (action needed)`. If blocked, replace the body
with the named error's cause+fix (see `errors.md`).
