# Workspace conventions & file contracts

The **workspace** (default the hidden `~/.job-search/`; an existing visible `~/job-search/` is **adopted**, not replaced — see `internals.md`) is PRIVATE per-user data — never committed to a public repo.

```
~/.job-search/
  config.yaml                # queries + schedule (human terms only; no score thresholds)
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
  sources: ["linkedin", "ashby"]  # ordered job sources every query runs against: linkedin | ashby | workday — omit the key for this default; workday is experimental (expect partial runs while upstream stabilizes)
  freshness: "past-2-weeks"  # any | past-week | past-2-weeks | past-month — client-side recency filter on posted_at (no API date param)
  detail_model: "fast"       # portable tier the per-posting detail reads use: fast | balanced | high | inherit (the model id each maps to → your platform's adapter → Model tiers)
  # parallel_detail_reads: true  # optional: approved use of parallel subagents for detail reads where the host supports them
schedule:
  frequency: "daily"         # hourly | every-2-hours | every-6-hours | daily | weekly — the cadence the schedule runs on (its mapping for the active scheduler → your platform's adapter → Scheduling)
  time: "08:00"              # HH:MM, honored when the active scheduler is wall-clock-based (a Tier-2 cron/launchd schedule); ignored when it is interval-only (a Tier-1 in-session loop) — see your platform's adapter → Scheduling
  timezone: "America/Los_Angeles"
notify:
  digest_path_template: "reports/{date}-digest.md"
  desktop_notify_on_block: true
```
The **`search` block** tunes the feed: `sources` is the ordered list of job sources each enabled query runs
against (order = presentation order in per-source counts). An absent key means `["linkedin", "ashby"]`. Tokens
outside the enum are dropped at preflight with a digest footnote (E-SOURCE-UNSUPPORTED), never a HALT.
Per-query source targeting is a known deferred knob — all queries run against all enabled sources. The runner
reads `sources` and never writes it. `freshness` is a client-side recency window on `posted_at` (the API has
no date param; `any` = no filter); `detail_model` is a portable tier token (`fast | balanced | high | inherit`)
the runner's per-posting detail reads use — the model each maps to lives in your platform's adapter → Model
tiers, and the fan-out itself defers to → Concurrent detail reads (`inherit` = the run's own model).
`parallel_detail_reads` is optional and records whether the user approved parallel subagents for detail
reads on hosts that require explicit authorization. Unset means interactive front-door flows may ask; `true`
means use parallel subagents where available; `false` means read details sequentially. The runner reads this
field but never writes it.
**`queries[].limit`** (1–100; the API's own default is 20 when omitted — the config template sets 25 explicitly) is the per-query feed size — pull
generously across several varied queries rather than one giant pull; there is no pagination, so breadth +
frequency + dedup accumulate coverage. Query construction (incl. deriving "remote") lives in `internals.md`.

`run_id` format: UTC timestamp `YYYY-MM-DDTHH-MM-SSZ` (hyphens, not colons, in the time component — safe as a filename on every platform). `<date>` for digests: `YYYY-MM-DD` (local tz).

## jobs.jsonl — append-only events (one JSON object per line)
Current state = fold by (**`source`**, **`source_id`**), last-write-wins per field (a legacy event with no `source` attaches by `source_id` alone — every legacy `evaluated` event already carries `source:"linkedin"`, so in practice only old `status_changed` lines lack it). Two event types:
```jsonc
{ "event":"evaluated", "ts":"<iso>", "run_id":"…", "source":"<the result row's source — copied, NEVER a hardcoded literal>", "source_id":"<source-native id — with source, the DEDUP KEY>",
  "query_id":"…", "title":"…", "company_name":"…", "location_display":"…", "salary_display":"…",
  "posted_at":"<iso>", "posted_at_extracted":"<iso date — OPTIONAL; only when the API posted_at was null and the JD states a date>", "same_role_as":"<source>:<source_id> — OPTIONAL; this row is the same real-world role as that primary row>", "source_url":"…", "posting_id_at_seen":"jp_…", "detail_read":true,
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

Operations (no helper script — perform these exactly):
- **Known ids** (the dedup set — one per enabled source `S`; missing file = empty set):
  ```bash
  grep -E '"source"[[:space:]]*:[[:space:]]*"'"$S"'"' "$WS/jobs.jsonl" 2>/dev/null \
    | grep -o '"source_id"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4 | sort -u
  ```
  (The `"source"` key pattern cannot match `"source_id"`/`"source_url"` — the closing quote
  must follow immediately. Legacy history all carries `source:"linkedin"`, so the linkedin set
  matches every pre-multi-source event: no migration.)
- **Append one event** (the heredoc keeps quoting safe — apostrophes in `reasoning` are fine):
  ```bash
  cat >> "$WS/jobs.jsonl" <<'EOF'
  {"event":"evaluated","ts":"…","source":"…","source_id":"…",…}
  EOF
  ```
- **Current state (fold):** read `jobs.jsonl` and fold in-context — group events by (`source`, `source_id`) — a legacy event with no `source` (old `status_changed` lines) attaches to its `source_id`'s record — later
  events override earlier per field, drop the `event` key. The pipeline view = the folded records tallied
  by `status` (plus the `needs_human_check: true` count). A folded record whose `same_role_as` names another present record is an ALIAS of it — count and display the pair as one (the pipeline view and home counts treat aliases as one role).

## runs/<run_id>.json — audit log
```jsonc
{ "run_id":"…", "started_at":"…", "completed_at":"…", "status_probe":"ok|degraded|unreachable",
  "queries":[ { "query_id":"…", "source":"<source>", "keywords":"…", "results_returned":25, "new":6, "errors":[] } ],
  "sources_searched":["linkedin","ashby"], "sources_failed":[],
  "results_summary":{ "total_results":50, "new_postings":9, "evaluated":9, "detail_read":5,
                      "relevant":6, "strong":3, "moderate":2, "weak":1 },
  "errors":[ { "stage":"get-posting", "source_id":"…", "code":"detail_fetch_failed",
               "retryable":true, "attempts":3, "final":"gave_up", "request_id":"…" } ],
  "run_health":"healthy|partial|degraded|blocked" }
```

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

<footnotes: stale detail links, partial failures, unidentifiable (null source_id) rows, brief-age nudge; first pass over a source (that source's known-ids set was empty at run start): `First pass over <Source> company boards — this batch can include older postings, since boards don't always state dates.`; per-source outage / unsupported / ignored (one line each — exact texts in `errors.md`)>
```
Strong first. Always show the Run health line and the counts. The parenthetical per-source breakdown in the
counts line appears ONLY when more than one source was searched; single-source runs keep today's exact line.
When more than one source was searched, append ` · <Source>` to the match meta line (e.g. `**<title>** —
<company> — <location> · Ashby`). A match whose `posted_at` was null carries a date mark on its reasoning
line: `posted ~<Mon D> (from posting text)` when the detail read extracted a JD-stated date, else `date not
stated`; add `— older than your freshness window` when the extracted date falls outside it (the entry still
lands in its verdict band: the read is already paid; relevance decides). A cross-source role merged via `same_role_as` renders as ONE entry whose link line shows every source: `[view on company board](<ashby source_url>) · [also on LinkedIn](<linkedin source_url>)` — the canonical company-board link first; 'view' verbs, never 'apply'. When the JD-stated date meaningfully precedes the other source's `posted_at`, one qualitative clause is allowed — 'on the company's board days before LinkedIn — early'; never a numeric freshness score. Run health is one of `healthy` |
`partial (<why>)` | `degraded (job sources flaky)` | `blocked (action needed)`, where `<why>` is exactly one
of `N errors` (scattered per-query/per-posting errors) · `<source> unavailable` (a whole source lost this
run) · `all sources unavailable`. Precedence: name a lost source over counting errors; `all sources` over
one. If blocked, replace the body with the named error's cause+fix (see `errors.md`).
