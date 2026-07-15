# agent-data Job Postings API — contract

_Last verified:_ route contract against the live CLI on 2026-07-14; pagination producer contract against
local producer code/tests on 2026-07-15; pricing/metering values supplied and approved on 2026-07-15
without a live account/pricing probe. This mirrors a live, evolving service. When actual CLI output or
live account/pricing metadata disagrees (a new field, a renamed error, a source added or dropped), trust
the live source, treat the stale line here as the thing to fix, and re-stamp the relevant date when you
re-verify. Never fill a gap from memory: if a field, source, or error code isn't in the real output, it
isn't in the contract.

One listing, four sources. Accessed via the `agent-data` CLI (JSON stdout, errors to stderr,
exit 1 on failure). Every `search-jobs` / `get-posting` call targets exactly ONE source via
`--source` (`linkedin | ashby | greenhouse | lever`; omitted → `linkedin`) — the API never fans out across
sources. Aggregation (the per-source fan-out, dedup, and merging) is this client's job.

- **Listing id:** `f9a6ec16-0bfd-44d8-b3ee-073776745ee7` (serves all sources)
- **CLI shape:** `agent-data call <listing-id> <slug> [--flag value ...]`. Add `--dry-run` to print the
  resolved request without executing. Authenticate first — see **Auth** below.
- **Dedup key:** the PAIR (**`source`**, **`source_id`**) — `source_id` is stable only within its
  source. The row's `id` (format `jp_<12-hex>`) is listing-scoped and NOT stable — use it only as a
  short-lived pairing token with `source_url`.

## Auth

Authenticate once, the same way on every host:

```
agent-data init --api-key <KEY> -y
```

This writes the key to `~/.agent-data/config.json` **without installing a discovery skill** — the plugin
resolves every route from this contract and needs none. `agent-data init` also accepts host-specific
selector flags that additionally drop a loose discovery skill for that host; the plugin needs none, so
do **not** pass one here. The CLI must be on `PATH` in the run's execution environment, with outbound
network egress to the agent-data endpoint permitted. Verify with `agent-data whoami` → `api_key_set: true`.

## Pricing and metering

These values were verified on 2026-07-15. Live account/pricing metadata wins when available; update this
date and downstream tests when the service changes. Do not infer rollover, overage, renewal, or balance
behavior not stated here. The pricing values were supplied and approved for this contract; no live
account/pricing probe was run.

| Option | Included metered calls | Effective value |
|---|---:|---:|
| Free tier | 100 | no charge |
| Pay as you go | purchased as needed | $0.008 per metered call; $5 adds 625 calls |
| $30 monthly subscription | 4,000/month | $0.0075/call if fully used |
| $100 monthly subscription | 15,000/month | about $0.0067/call if fully used |
| $200 monthly subscription | 40,000/month | $0.005/call if fully used |

Subscription effective rates assume full use. Search and detail attempts are metered external calls, so
use call count as the primary usage measure and do not infer an actual charge without live account data.

- Each successful `search-jobs` or `get-posting` attempt counts as one metered call.
- Failed attempts and retry attempts currently count. The producer plans to make failures unmetered, so
  this is a dated current-state fact, not a permanent promise.
- A call rejected for quota or payment does not count.
- Free routes such as `status` and `whoami` do not count.

If agent-data returns an explicit charged or metered status for an attempt, that status overrides inference
from the outcome.

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
  --keywords "<required>" [--location "<optional>"] [--limit <1-100, default 20>] [--source <linkedin|ashby|greenhouse|lever>] \
  [--published_on_or_after <YYYY-MM-DD>] [--cursor <opaque token>] \
  --fields id,source_id,source_url,title,company_name,location_display,salary_display,posted_at,published_at,detail_available,source
```
- **`--cursor <opaque token>`** is optional. Omit to fetch the first page. Ashby, Greenhouse, and Lever
  return `data.pagination` and accept its continuation token. `data.pagination.has_more` is a boolean;
  `data.pagination.next_cursor` is an opaque string when `has_more:true` and is `null` when
  `has_more:false`. LinkedIn omits `data.pagination`; LinkedIn cursor is rejected as a non-retryable
  `400 validation_error` with `error.param:"cursor"`.
- **Continuation binding.** Replay `source`, `keywords`, `location`, `published_on_or_after`, the literal
  `fields` value, and `limit` exactly, then add only the returned cursor. Cursors are opaque, expire after
  24 hours, and are never durable checkpoints: do not decode, persist, or resume them. Ordering and
  traversal are best-effort, not snapshot isolation.
- **`--source` targets ONE source** (omitted → `linkedin`). Comma-separated or repeated values →
  `400 validation_error` (`error.param:"source"`, `retryable:false`; the message names the allowed sources) — drop that source for
  this run (E-SOURCE-UNSUPPORTED in `errors.md`), never retry it.
- **Echo-verification (legacy-server defense).** Older service deployments silently IGNORE
  unknown params. After every search, confirm the echoed `data.query.source` equals the source
  you requested (an ABSENT echo counts as `linkedin`). On mismatch → E-SOURCE-IGNORED
  (`errors.md`): skip that source's remaining queries this run, and keep any returned rows under
  their own row-level `source` value (they are real rows of whatever source actually answered).
- **`--published_on_or_after <YYYY-MM-DD>`** (optional; omit → no recency filter) keeps only rows whose
  **effective publication date** — the later of `published_at` and `posted_at`, using whichever is
  present — is on or after the date; a row with **no** effective date (both null) is **excluded** when
  the filter is set. The service applies it **as part of the search** (fills up to `limit` with
  in-window rows — not a post-slice of the first `limit`) and **echoes** it at
  `data.query.published_on_or_after` — the legacy-server check, same as `source`: a present, equal echo
  means the service filtered; an absent/`null` echo means a deployment predating the param, so filter
  client-side instead. A malformed date is a non-retryable `422 validation_error`
  (`param:"published_on_or_after"`); a future/over-tight date returns an empty `status:"completed"`
  result, not an error.
- **Returns** `data.results[]`, each row (all nullable): `id` (`jp_…`), `source_id`, `source_url`, `title`,
  `company_name`, `location_display`, `salary_display` (FREE TEXT — never parse for numbers), `posted_at`
  (ISO), `published_at` (ISO date-time), `source`, `search_status`, `detail_available` (bool). Also `data.warnings[]`, `data.status`,
  `data.started_at/completed_at`, `meta.request_id`.
- **Errors:** `422 validation_error` (`details[].loc` names the bad param), `400 validation_error` (a bad `fields=` name OR an unsupported `--source`; `error.param` says which), `503 upstream_unavailable` (`retryable:true`).

## Route: get-posting  (needs the id+source_url PAIR from one search row)
```
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 get-posting \
  --posting_id "<jp_ id from the row>" --source_url "<source_url from the SAME row>" [--source <linkedin|ashby|greenhouse|lever>] \
  --fields id,title,company_name,location_display,employment_type,posted_at,description_markdown,missing_fields
```
- **Pass the row's `source` explicitly** — it removes inference ambiguity; old servers ignore it
  harmlessly.
- **Returns** `data.description_markdown` (full JD), `data.employment_type`, `data.missing_fields[]` (fields
  the page didn't yield — treat as "not stated", NEVER as a negative), plus the summary fields; `meta.mode`,
  `meta.request_id`. **`application_url` is intentionally not exposed.**
- **Errors:** `400 validation_error` (`retryable:false`) — a request-contract failure; the common case is a `posting_id`/`source_url` **pair mismatch** (the row was re-indexed): do NOT retry, fall back to summary-only. `422 validation_error` (missing/invalid source_url), `503 upstream_unavailable` (`retryable:true`).

## Error envelope (all routes)
```json
{"error": {"code": "...", "message": "...", "param": "...", "request_id": "...", "retryable": true, "source": "...", "details?": [...]}}
```
(`details` is present on `422 validation_error`; it may be absent on other errors.) **Branch retries on the `retryable` boolean, not on parsing `code` — the service collapses most 4xx to `validation_error` and uses `error.param` to name the field, so the boolean is the reliable signal.** Retry only `retryable:true` (the 503 `upstream_unavailable`s):
up to 3 attempts, exponential backoff with jitter (~1s, 3s, 7s). Never retry a non-retryable `validation_error` (a bad pair, bad field, or unsupported source). If two consecutive `search-jobs` calls **against the same source** return a retryable 503, stop searching
THAT source this run (per-source stretch) — other sources continue; all enabled sources stretched
→ stop searching entirely. See `errors.md` (E-UPSTREAM-STRETCH).

## Per-source quirks (one table, the only per-source contract surface)

| | linkedin | ashby | greenhouse | lever |
|---|---|---|---|---|
| `source_id` | numeric string | Ashby posting UUID | `<company>:<numeric>` (e.g. `zuora:7310605`) | `<company>:<uuid>` (e.g. `zoox:f4746da4-…`) |
| `source_url` | `linkedin.com/jobs/view/…` + tracking params | clean canonical `jobs.ashbyhq.com/<company>/<uuid>` — **this IS the live apply page** (link it; never frame as auto-apply) | clean canonical `boards.greenhouse.io/<company>/jobs/<id>?gh_jid=<id>` — **IS the live apply page** | clean canonical `jobs.lever.co/<company>/<uuid>` — **IS the live apply page** |
| `posted_at` | date-only in search; full timestamp in detail | **null in BOTH** — a date often appears in the JD prose ("Job Posted: …"); extract it during the detail read | **populated** (ISO) in search + detail — freshness applies normally | **populated** (ISO) in search + detail — freshness applies normally |
| `published_at` | null (use `posted_at`) | **populated** (drives freshness — `posted_at` is null) | populated (= `posted_at`) | populated (= `posted_at`) |
| freshness | window applies via effective date | window applies via `published_at` (posted_at null) | window applies via effective date | window applies via effective date |
| latency / mode | live scrape (seconds) | indexed corpus (~ms); may include months-old or closed postings — the canonical link is how the user verifies openness | service-refreshed store (~ms); detail serves the stored snapshot first, live fallback on cache miss; may include older/closed postings | service-refreshed store (~ms); snapshot-first detail, live fallback on miss; may include older/closed postings |
| coverage | LinkedIn job search | broad crawl of public Ashby company boards | crawl of public Greenhouse company boards | crawl of public Lever company boards |
| `salary_display` | usually null; free text — never parse | usually null | usually null; free text — never parse | **may be raw HTML** — still FREE TEXT; never parse for numbers, strip/ignore markup when displaying |
| enums (`employment_type`, …) | `FULL_TIME` | `FullTime` — treat ALL cross-source enums as free text; never exact-match | often absent (→ `missing_fields`); when present, free text | `Full-time` — free text; a third distinct casing (reinforces: never exact-match) |
| `missing_fields` | usually `["application_url"]` | usually `[]` | may include `employment_type`, `workplace_type`, `is_remote`, … (treat as "not stated") | usually minimal (e.g. `["is_listed"]`) |
