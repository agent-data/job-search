# agent-data Job Postings API — contract

The only job source in v1. Accessed via the `agent-data` CLI (JSON stdout, errors to stderr, exit 1 on failure).

- **Listing id:** `f9a6ec16-0bfd-44d8-b3ee-073776745ee7`
- **CLI shape:** `agent-data call <listing-id> <slug> [--flag value ...]`. Add `--dry-run` to print the
  resolved request without executing. `agent-data whoami` reports auth.
- **Dedup key:** the LinkedIn-native **`source_id`** (stable across searches). The row's `id` (format
  `jp_<12-hex>`) is listing-scoped and NOT stable — use it only as a short-lived pairing token with `source_url`.

## Route: status  (run this first)
```
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 status
```
Returns `{"status": "ok"}` healthy or `{"status": "degraded"}` when upstream fetches are failing at a high
rate. A fresh service is `ok` by default.

## Route: search-jobs
```
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 search-jobs \
  --keywords "<required>" [--location "<optional>"] [--limit <1-100, default 20>] \
  --fields id,source_id,source_url,title,company_name,location_display,salary_display,posted_at,detail_available,source
```
- **No pagination** (LinkedIn has no stable cursor); re-running may reorder. Vary keywords/location for breadth.
- **Returns** `data.results[]`, each row (all nullable): `id` (`jp_…`), `source_id`, `source_url`, `title`,
  `company_name`, `location_display`, `salary_display` (FREE TEXT — never parse for numbers), `posted_at`
  (ISO), `source`, `search_status`, `detail_available` (bool). Also `data.warnings[]`, `data.status`,
  `data.started_at/completed_at`, `meta.request_id`.
- **Errors:** `422 invalid_request` (`details[].loc` names the bad param), `400 unsupported_field`
  (bad `fields=` name), `502 search_failed` (`retryable:true`).

## Route: get-posting  (needs the id+source_url PAIR from one search row)
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
{"error": {"code": "...", "message": "...", "param": "...", "request_id": "...", "retryable": true, "source": "...", "details?": [...]}}
```
(`details` is present on `422 invalid_request`; it may be absent on other errors.) **Branch retries on the `retryable` boolean, not on parsing `code`.** Retry only `retryable:true` (the 502s):
up to 3 attempts, exponential backoff with jitter (~1s, 3s, 7s). Never retry `invalid_pair` / `invalid_request`
/ `unsupported_field`. If two consecutive `search-jobs` calls return 502, stop searching this run
(LinkedIn stretch-outage) — see `errors.md` (E-UPSTREAM-STRETCH).
