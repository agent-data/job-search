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

## Route: status  (run this first)
```
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 status
```
Returns `{"status": "ok"}` healthy or `{"status": "degraded"}` when upstream fetches are failing at a high
rate. A fresh service is `ok` by default. The probe is an AGGREGATE across all sources: `degraded`
cannot be attributed to one source; per-source health is inferred from search outcomes. (Upstream
ask on file: per-source status.)

## Route: search-jobs
```
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 search-jobs \
  --keywords "<required>" [--location "<optional>"] [--limit <1-100, default 20>] [--source <linkedin|ashby|workday>] \
  --fields id,source_id,source_url,title,company_name,location_display,salary_display,posted_at,detail_available,source
```
- **No pagination on any source**; re-running may reorder. Vary keywords/location for breadth.
- **`--source` targets ONE source** (omitted → `linkedin`). Comma-separated or repeated values →
  `400 unsupported_source` (`error.param: "source"`, `retryable:false`) — drop that source for
  this run (E-SOURCE-UNSUPPORTED in `errors.md`), never retry it.
- **Echo-verification (legacy-server defense).** Older service deployments silently IGNORE
  unknown params. After every search, confirm the echoed `data.query.source` equals the source
  you requested (an ABSENT echo counts as `linkedin`). On mismatch → E-SOURCE-IGNORED
  (`errors.md`): skip that source's remaining queries this run, and keep any returned rows under
  their own row-level `source` value (they are real rows of whatever source actually answered).
- **Returns** `data.results[]`, each row (all nullable): `id` (`jp_…`), `source_id`, `source_url`, `title`,
  `company_name`, `location_display`, `salary_display` (FREE TEXT — never parse for numbers), `posted_at`
  (ISO), `source`, `search_status`, `detail_available` (bool). Also `data.warnings[]`, `data.status`,
  `data.started_at/completed_at`, `meta.request_id`.
- **Errors:** `422 invalid_request` (`details[].loc` names the bad param), `400 unsupported_field`
  (bad `fields=` name), `400 unsupported_source` (`retryable:false`), `502 search_failed`
  (`retryable:true`).

## Route: get-posting  (needs the id+source_url PAIR from one search row)
```
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 get-posting \
  --posting_id "<jp_ id from the row>" --source_url "<source_url from the SAME row>" [--source <linkedin|ashby|workday>] \
  --fields id,title,company_name,location_display,employment_type,posted_at,description_markdown,missing_fields
```
- **Pass the row's `source` explicitly** — it removes inference ambiguity; old servers ignore it
  harmlessly.
- **Returns** `data.description_markdown` (full JD), `data.employment_type`, `data.missing_fields[]` (fields
  the page didn't yield — treat as "not stated", NEVER as a negative), plus the summary fields; `meta.mode`,
  `meta.request_id`. **`application_url` is intentionally not exposed.**
- **Errors:** `400 invalid_pair` (`retryable:false` — the id/source_url don't match; do NOT retry, fall back
  to summary-only), `422 invalid_request` (missing/invalid source_url), `400 unsupported_field`,
  `502 detail_fetch_failed` (`retryable:true`).

## Error envelope (all routes)
```json
{"error": {"code": "...", "message": "...", "param": "...", "request_id": "...", "retryable": true, "source": "...", "details?": [...]}}
```
(`details` is present on `422 invalid_request`; it may be absent on other errors.) **Branch retries on the `retryable` boolean, not on parsing `code`.** Retry only `retryable:true` (the 502s):
up to 3 attempts, exponential backoff with jitter (~1s, 3s, 7s). Never retry `invalid_pair` / `invalid_request`
/ `unsupported_field`. If two consecutive `search-jobs` calls **against the same source** return 502, stop searching
THAT source this run (per-source stretch) — other sources continue; all enabled sources stretched
→ stop searching entirely. See `errors.md` (E-UPSTREAM-STRETCH).

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
