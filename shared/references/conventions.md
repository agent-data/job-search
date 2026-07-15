# Workspace conventions & file contracts
<!-- reference-resolution-marker:8f2a4c1e-single-home — this is the ONE canonical home; every skill reaches it in place. Asserted by tests/test_reference_resolution.py; do not remove. -->

The **workspace** (default the hidden `~/.job-search/`; an existing visible `~/job-search/` is **adopted**, not replaced — see `internals.md`) is PRIVATE per-user data — never committed to a public repo.

```
~/.job-search/
  config.yaml                # queries + schedule (human terms only; no score thresholds)
  preferences.md             # Job Preferences Brief — prose only
  resumes/master.md          # base resume; resumes/tailored/ for generated ones (Plan C)
  jobs.jsonl                 # append-only EVENT log; current state = fold by (source, source_id)
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
  sources: ["linkedin", "ashby"]  # ordered job sources every query runs against (the source enum is defined in agent-data-contract.md) — omit the key for this default; greenhouse/lever widen coverage across more company boards
  freshness: "past-2-weeks"  # any | past-week | past-2-weeks | past-month — recency window; resolves to a server-side published_on_or_after cutoff (client-side fallback if the echo is absent); default past-2-weeks
  detail_model: "balanced"   # tier the per-posting fit VERDICT runs at — the mid-tier reviewer floor (default): fast | balanced | high | inherit (the agent binds each tier to a concrete model from its own roster — the least-powerful that does the task well; the verdict is a judgment, so never the cheapest)
  # max_new_postings_per_run: 50  # optional: positive integer or "all"; omit for first-page coverage
  # parallel_detail_reads: true  # optional: approved use of parallel subagents for detail reads where the host supports them
schedule:
  frequency: "daily"         # hourly | every-2-hours | every-6-hours | daily | weekly — the cadence the schedule runs on (its cron mapping composed via `schedule-line.sh` — see `internals.md` → Scheduling setup)
  time: "08:00"              # HH:MM, honored when the active scheduler is wall-clock-based (an unattended cron/launchd schedule); ignored when it is interval-only (an in-session loop)
  timezone: "America/Los_Angeles"
notify:
  digest_path_template: "reports/{date}-digest.md"
  desktop_notify_on_block: true
```
The **`search` block** tunes the feed: `sources` is the ordered list of job sources each enabled query runs
against (order = presentation order in per-source counts). An absent key means `["linkedin", "ashby"]`. Tokens
outside the enum are dropped at preflight with a digest footnote (E-SOURCE-UNSUPPORTED), never a HALT.
Per-query source targeting is a known deferred knob — all queries run against all enabled sources. The runner
reads `sources` and never writes it. `freshness` is a recency window that resolves to a **`published_on_or_after` cutoff** the search API
applies server-side, with a client-side filter as fallback. A row's **effective publication date** is
the later of `published_at` and `posted_at`, using whichever is present (unknown only when both are
null); the window admits rows whose effective date is on or after the cutoff. `any` sends no cutoff (no
filter); `past-week` = today − 7 days; `past-2-weeks` = today − 14 days (the default); `past-month` =
today − 30 days. Those values are the persisted defaults — the cutoff is only a date, so an ad-hoc
recency the user names for a single run ("only postings published in the past day", "since June 1")
resolves to its own cutoff and overrides the saved default for that run, with no new enum value. The
runner sends the cutoff and echo-verifies `data.query.published_on_or_after`; where a deployment omits
the echo it filters client-side by the same effective date. Under an active window a row with no
effective date is dropped (server parity); with `any` nothing is dropped. `detail_model` is a portable tier token for the per-posting **fit verdict** — the
judgment the detail read produces. Because that verdict is a judgment, not a mechanical step, it runs at the
**mid-tier reviewer floor**: `balanced` is the default, scaled up to `high` for a higher-risk or ambiguous
posting, never dispatched on the cheapest tier by default and never reflexively on the most capable. The
genuinely mechanical bulk — dedup, the summary prefilter, provenance — runs cheap in the runner's primary
context and the shared scripts, independent of this knob. The tiers: `fast` (the cheapest tier — an explicit
opt-down: faster, a touch looser on subtle qualitative calls), `balanced` (the mid-tier reviewer floor; the
default), `high` (highest fidelity), `inherit` (the run's own model — the one value that maps to no explicit
override, and only by the user's choice; the runner otherwise always dispatches an explicit model). A legacy
`haiku` / `sonnet` / `opus` value — some `config.yaml` files from earlier versions carry the pre-tier form —
is accepted as an alias for `fast` / `balanced` / `high` respectively. The agent
binds each tier to a concrete model from its own roster — the least-powerful model that does the task well;
the fit verdict is a judgment, so never the cheapest.
`parallel_detail_reads` is optional and records whether the user approved parallel subagents for detail
reads on hosts that require explicit authorization. Unset means interactive front-door flows may ask; `true`
means use parallel subagents where available; `false` means read details sequentially. The runner reads this
field but never writes it.

`search.max_new_postings_per_run` is an optional review-depth setting. Its accepted values and resolved
behavior are:

| Stored value | Resolved review scope |
|---|---|
| key omitted | `first_page`: fetch one page from each enabled query × enabled source and never follow a cursor |
| positive integer | `finite`: continue cursor-capable board streams until at most that many unique unseen real-world roles are selected for judgment, or eligible sources exhaust |
| exact string `"all"` | `all`: exhaust the currently traversable Ashby, Greenhouse, and Lever streams; LinkedIn remains one page |
| present `null`, zero, negative integer, float, numeric string, or any other token | invalid config: halt in preflight before any metered call, using E-BAD-CONFIG from `errors.md` |

Omission is the backward-compatible default; it does not prompt, write config, or add continuation calls.
The finite target bounds unique roles judged after known-id dedup and same-role merging, not page calls:
known and duplicate rows can require additional pages before the target settles. `queries[].limit` (1–100;
the API default is 20 when omitted and this template sets 25) remains the per-call page size for one
query/source request. The additive setting keeps `version: 1`; there is no migration. Conversational one-off
and saved-change recipes live in `internals.md`.

`run_id` format: UTC timestamp `YYYY-MM-DDTHH-MM-SSZ` (hyphens, not colons, in the time component — safe as a filename on every platform). `<date>` for digests: `YYYY-MM-DD` (local tz).

## jobs.jsonl — append-only events (one JSON object per line)
Current state = fold by (**`source`**, **`source_id`**), last-write-wins per field (an event with no `source` (all pre-multi-source history, and any `status_changed` line that omits it) attaches by `source_id` alone — every legacy `evaluated` event already carries `source:"linkedin"`, so in practice only old `status_changed` lines lack it). Two event types:
```jsonc
{ "event":"evaluated", "ts":"<iso>", "run_id":"…", "source":"<the result row's source — copied, NEVER a hardcoded literal>", "source_id":"<source-native id — with source, the DEDUP KEY>",
  "query_id":"…", "title":"…", "company_name":"…", "location_display":"…", "salary_display":"…",
  "posted_at":"<iso>", "posted_at_extracted":"<iso date — OPTIONAL; only when the API posted_at was null and the JD states a date>", "same_role_as":"<source>:<source_id> — OPTIONAL; this row is the same real-world role as that primary row — parse by splitting on the FIRST colon only (e.g. same_role_as:"greenhouse:acme:7310605" → source "greenhouse", source_id "acme:7310605")>", "source_url":"…", "posting_id_at_seen":"jp_…", "detail_read":true,
  "relevant":true, "match":"strong|moderate|weak|null", "reasoning":"…",
  "dealbreakers_hit":[], "unknowns":[], "needs_human_check":false, "status":"new", "first_seen":"<iso>" }
{ "event":"status_changed", "ts":"<iso>", "source_id":"…", "status":"interested", "note":"…" }
```
Allowed `status`: `new | interested | applied | rejected | archived`.

**Event-line contract** (the operations below depend on it): one event per line; each line is a single-line
JSON object — never pretty-printed; every event carries a non-empty `"source_id"`; the literal key
`"source_id"` appears exactly once per line; every `evaluated` event carries a non-empty `"source"`; the
literal key `"source"` appears at most once per line (the per-source pre-filter grep depends on it, exactly as
the `"source_id"`-once rule protects the id extraction); `same_role_as` is a FLAT string — never a nested object (the `"source_id"`-appears-once rule is load-bearing for the grep extraction). Validate an event against this contract before appending it.

Operations — **run the shared script where a shell runtime exists, else follow the prose fallback**
(each script reproduces its fallback EXACTLY — pinned by `tests/test_mechanics_scripts.py`; the scripts
are the skills' own POSIX shell, no third-party dependency):
- **Known ids** — the dedup step, one per enabled source `S` (missing file = empty set).
  **Script:** `../scripts/mechanics/dedup.sh "$WS/jobs.jsonl" "$S"` — candidate `source_id`s on stdin,
  the NEW ones (not already recorded for `S`) on stdout; blank candidate lines (a null `source_id`) are
  skipped. **Prose fallback** — extract the known set with the pinned pipeline, then keep the candidates
  not in it:
  ```bash
  grep -E '"source"[[:space:]]*:[[:space:]]*"'"$S"'"' "$WS/jobs.jsonl" 2>/dev/null \
    | grep -o '"source_id"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4 | sort -u
  ```
  (The `"source"` key pattern cannot match `"source_id"`/`"source_url"` — the closing quote
  must follow immediately. Legacy history all carries `source:"linkedin"`, so the linkedin set
  matches every pre-multi-source event: no migration.)
- **Append one event** — validate the line against the event-line contract above, then append idempotently.
  **Script:** `../scripts/mechanics/event-log-append.sh "$WS/jobs.jsonl"` — the single-line event JSON on
  stdin (it validates, then appends; an `evaluated` event whose `(source, source_id)` is already recorded is
  a no-op). **Prose fallback** (validate first; the heredoc keeps quoting safe — apostrophes in `reasoning`
  are fine):
  ```bash
  cat >> "$WS/jobs.jsonl" <<'EOF'
  {"event":"evaluated","ts":"…","source":"…","source_id":"…",…}
  EOF
  ```
- **Current state (fold):** read `jobs.jsonl` and fold in-context — group events by (`source`, `source_id`) — an event with no `source` (all pre-multi-source history, and any `status_changed` line that omits it) attaches to its `source_id`'s record — later
  events override earlier per field, drop the `event` key. The pipeline view = the folded records tallied
  by `status` (plus the `needs_human_check: true` count). A folded record whose `same_role_as` names another present record is an ALIAS of it (match the reference by splitting `same_role_as` on the FIRST colon only — source, then a possibly-colon-bearing `source_id` — the same parse as its definition above) — count and display the pair as one (the pipeline view and home counts treat aliases as one role).

## runs/<run_id>.json — audit log
```jsonc
{ "run_id":"…", "started_at":"…", "completed_at":"…",
  "build": { "version":"0.4.0", "content_hash":"sha256:abcdef123456", "git_sha":"<short sha|unknown>" },
  "status_probe":"ok|degraded|unreachable",
  "queries":[ {
    "query_id":"…", "source":"<source>", "keywords":"…", "results_returned":25, "new":6,
    "pages_fetched":3, "rows_scanned":75, "unique_candidates":31, "selected_for_review":25,
    "has_more_at_stop":true,
    "stop_reason":"first_page_complete|target_reached|sources_exhausted|unpaginated|pagination_incomplete|source_failed",
    "attempts":3, "request_ids":["req_…"], "upstream_code":null, "retryable":null,
    "errors":[]
  } ],
  "sources_searched":["linkedin","ashby"], "sources_failed":[],
  "review_scope": {
    "mode":"first_page|finite|all", "target_new_postings":null,
    "origin":"default|one_off|saved",
    "outcome":"completed_first_pages|target_reached|sources_exhausted|incomplete"
  },
  "agent_data_usage": {
    "metered_calls":9,
    "unit_rate_usd":"<decimal unit rate used for this run>",
    "payg_equivalent_usd":"<decimal equivalent for this run>",
    "pricing_basis":"pay_as_you_go_equivalent",
    "by_operation": { "initial_search":4, "continuation_search":2, "detail_read":3 },
    "diagnostics": { "retry_attempts":1, "charged_failures":1, "quota_rejections":0, "free_route_calls":2 }
  },
  "pagination_metrics": {
    "first_page_rows":80, "continuation_rows":50, "known_rows":62,
    "same_run_cross_query_duplicate_rows":18, "cross_source_rows_merged":4,
    "unique_unseen_roles_first_pages":0, "unique_unseen_roles_continuations":28,
    "selected_roles_from_continuations":20,
    "deeper_coverage_nudge_eligible":true,
    "deeper_coverage_nudge_streams":["ai-eng-remote:ashby"]
  },
  "results_summary":{ "total_results":50, "new_postings":9, "evaluated":9, "detail_read":5,
                      "relevant":6, "strong":3, "moderate":2, "weak":1 },
  "errors":[ { "stage":"get-posting", "source_id":"…", "code":"upstream_unavailable",
               "retryable":true, "attempts":3, "final":"gave_up", "request_id":"…" } ],
  "run_health":"healthy|partial|degraded|blocked" }
```
`build.version` and `build.content_hash` are copied from the bundled `references/build-stamp.md`.
`build.git_sha` is best-effort: use `git -C <job-search root> rev-parse --short HEAD` only when the
executing Job Search plugin/source root is reliably known and that root has a `.git` context; otherwise
write `"unknown"`. Never derive `git_sha` from the caller/current working directory, because that can
record the user's project SHA instead of the Job Search build. The build object is required on every run
record written by `job-search-run`, including blocked records where a workspace exists.

Each `queries` item is one logical query/source stream. `unpaginated` is reserved for LinkedIn.
`has_more_at_stop` is boolean only when valid board pagination metadata makes it trustworthy; write `null`
for LinkedIn and for an incomplete pagination contract branch. `attempts` includes retries, and
`request_ids` retains the observable request provenance. Never write a cursor, decoded cursor payload, or
resumable continuation state to the stream or any other durable run-record field.

`review_scope.target_new_postings` is a positive integer only in `finite` mode and `null` otherwise.
`completed_first_pages` means every enabled stream completed its ordinary first-page branch;
`target_reached` means a finite selection target settled; `sources_exhausted` means every healthy eligible
stream ended; and any quota halt, source failure, or untrustworthy pagination branch makes the outcome
`incomplete` while preserving trustworthy rows already found. `origin` records whether the resolved choice
came from omission (`default`), a conversational one-run override (`one_off`), or config (`saved`).

`agent_data_usage` is attempt-based. Its three `by_operation` counters classify each metered attempt exactly
once and must sum to `metered_calls`; retry and charged-failure diagnostics are subsets, while quota
rejections and free-route calls are unmetered, so none of those diagnostic counters is added again. Store
`unit_rate_usd` and `payg_equivalent_usd` as decimal strings so historical arithmetic does not change after
a pricing update. The canonical dated metering rules and the rate used to derive these fields live only in
`agent-data-contract.md`; verify there rather than copying a rate into this contract.

`pagination_metrics` is local aggregate evidence, not telemetry. The deeper-coverage nudge is eligible only
when `unique_unseen_roles_first_pages` is zero and at least one healthy cursor-capable stream returned
trustworthy `has_more:true`; `deeper_coverage_nudge_streams` lists those `<query_id>:<source>` identities and
is empty when ineligible. The runner records this evidence but never a shown marker; the home-view registry
marker is owned by `internals.md`.

### Pagination scratch lifecycle

First-page-only runs stay in context and create no scratch file. Immediately before the first continuation
call, create `runs/.pagination-<run_id>.jsonl` and hand the candidate pool between phases by that path. Write
only normalized posting summaries, query/source provenance, stream ownership, and merge bookkeeping—never a
cursor, a decoded payload, or a recovery checkpoint. Process the file in chunks of at most 100 lines; if a
larger pool remains, process another bounded chunk.

Remove the scratch file on every handled success or halt, including quota and partial-pagination exits. A
later run may delete stale files matching the exact `.pagination-<run_id>.jsonl` shape, but it must never
resume, replay, or recover continuation from one.

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
9 new postings (6 LinkedIn · 3 Ashby) · 3 strong · 2 moderate · 1 weak · 3 filtered out · <n> searches · <m> detail reads

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

<footnotes: stale detail links, partial failures, unidentifiable (null source_id) rows, brief-age nudge; first pass over a source (that source returned rows AND its known-ids set was empty at run start): `First pass over <Source> company boards — this batch can include older postings, since boards don't always state dates.`; per-source outage / unsupported / ignored (one line each — exact texts in `errors.md`)>
```
Strong first. Always show the Run health line and the counts. The parenthetical per-source breakdown in the
counts line appears ONLY when more than one source was searched; single-source runs keep today's exact line.
The counts line counts result ROWS — a cross-source merged pair contributes to both its sources' breakdown
figures and to N; the collapse to one role shows in the merged entry itself and in the pipeline/home counts
(see the alias rule in §jobs.jsonl), never by shrinking N.
When more than one source was searched, append ` · <Source>` to the match meta line (e.g. `**<title>** —
<company> — <location> · Ashby`). A match whose `posted_at` was null carries a date mark on its reasoning
line: `posted ~<Mon D> (from posting text)` when the detail read extracted a JD-stated date, else `date not
stated`; add `— older than your freshness window` when the extracted date falls outside it (the entry still
lands in its verdict band: the read is already paid; relevance decides). A cross-source role merged via `same_role_as` renders as ONE entry whose link line shows every source — the **primary board source's canonical link first**, then `· [also on <Source>](<url>)` for each other row in `search.sources` order, e.g. `[view on company board](<primary board source_url>) · [also on LinkedIn](<linkedin source_url>)`. 'view' verbs, never 'apply'. (The primary is the board-source row that got the detail read — see the merge rule in `job-search-run` step 3; a `linkedin`-only group has no company-board link and shows just its LinkedIn link.) When the JD-stated date meaningfully precedes the other source's `posted_at`, one qualitative clause is allowed — 'on the company's board days before LinkedIn — early'; never a numeric freshness score. Run health is one of `healthy` |
`partial (<why>)` | `degraded (job sources flaky)` | `blocked (action needed)`, where `<why>` is one
of `N errors` (scattered per-query/per-posting errors) · `<source> unavailable` (one whole source lost this
run) · `<sourceA>, <sourceB> unavailable` (several — but not all — sources lost, each named in
`search.sources` order) · `all sources unavailable` (every enabled source lost). Precedence: name lost
source(s) over counting errors; `all sources unavailable` only when EVERY enabled source is lost, otherwise
list the specific ones. If blocked, replace the body with the named error's cause+fix (see `errors.md`).
