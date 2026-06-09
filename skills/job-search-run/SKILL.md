---
name: job-search-run
description: Run one headless, non-interactive job-search pass — load the preferences brief and config, search agent-data for each saved query, skip postings it has already seen, judge each new posting's relevance, read full descriptions for promising matches, and write a digest. Use to run the scheduled search, check for new jobs, or when invoked by a schedule. (For interactive setup or the home view, use job-search.)
disable-model-invocation: false
user-invocable: true
---

# job-search-run

> To configure, extend, customize, or troubleshoot the agent itself (or understand its
> capabilities), use the **job-search-agent** skill — the operator manual.

Run ONE headless job-search pass over the workspace. Free gates before metered calls; no silent failures.
**Shape:** search → dedup/freshen → **scan summaries in this (primary) context** → **fan out one parallel
subagent per promising posting** for the detail read → **consolidate** into a digest.
Read `references/agent-data-contract.md` (CLI + routes + retry rules), `references/errors.md` (every E-* with
the exact cause+fix wording), `references/conventions.md` (file schemas + digest format),
`references/parallelism.md` (parallel-by-default + how to brief a subagent), and `references/voice.md` (how
any user-facing line is worded) — follow them exactly.

Resolve the workspace with `python3 "$OS" resolve` (bundled `scripts/osctl.py`; registry → `~/.job-search/` → legacy `~/job-search/`) UNLESS `--workspace <path>` is given, which overrides. Resolve `$OS` (and `$STATE`) from this skill's own directory (e.g. `${CLAUDE_SKILL_DIR}/scripts/...` as a plugin) — never assume cwd. This run is HEADLESS: never prompt. If `resolve` reports `first_run` (no workspace/config yet) → E-NO-CONFIG naming the **job-search** skill as the fix (HALT, exit 1); onboarding is interactive and lives in the `job-search` skill, not here. The job source listing id is `f9a6ec16-0bfd-44d8-b3ee-073776745ee7`.

**Retries:** branch only on the error envelope's `retryable` boolean (`true` → retry with backoff up to 3×;
`false` → never retry), not on the error `code` string — see `references/agent-data-contract.md`.

## Loop
0. **Preflight (free).**
   - `agent-data` not found on PATH → E-NO-AGENT-DATA (HALT, exit 1).
   - No `config.yaml` → E-NO-CONFIG (HALT, exit 1).
   - `agent-data whoami`; `api_key_set:false` → E-NO-AUTH (HALT, exit 1).
   - `config.yaml` `version` major unknown → E-CONFIG-VERSION (HALT, exit 1).
   - Brief missing/empty (`workspace.preferences_path`) → E-NO-PREFERENCES (HALT, exit 1, named fix).
   - `agent-data call <listing> status`: `ok` proceed; `degraded` set a flag (set Run health: degraded;
     note "LinkedIn flaky — results this run may be affected" in the digest; no detail-read cap — read
     promising matches as normal); unreachable → E-SERVICE-DOWN (write a "service down" digest, HALT, exit 1).

   > Before exiting on ANY E-* HALT where a workspace exists (E-NO-AUTH, E-NO-PREFERENCES,
   > E-CONFIG-VERSION, E-SERVICE-DOWN, E-QUOTA), write `runs/<run_id>.json` with
   > `run_health:"blocked"` + the error, so the next home view surfaces it.
1. **Search the feed (one metered `search-jobs` per enabled query; run the queries concurrently).** For each
   `queries[]` with `enabled:true`, call `search-jobs` with `--keywords` (+ `--location`, `--limit`) and `--fields id,source_id,source_url,title,company_name,location_display,salary_display,posted_at,detail_available,source`.
   `limit` is the feed size (1–100, **default 25**) — pull generously and lean on **breadth** (several varied
   queries beat one giant pull; there's no pagination and re-runs reorder). See remote-derivation and "as many
   NEW as possible" in `references/internals.md`.
   - `502 search_failed` (retryable) → retry up to 3× with backoff; on give-up record the error and continue.
     **Two consecutive queries that fail entirely (all retries exhausted) → E-UPSTREAM-STRETCH: stop searching the rest.**
   - `422`/`400 unsupported_field` → E-BAD-QUERY (name the bad param from `details[].loc`), skip that query.
   - A quota/limit/payment failure (see errors.md detection) → E-QUOTA (HALT, exit 1).
2. **Dedup + freshen (free).** `python3 "$STATE" known-ids --jobs <workspace>/jobs.jsonl` → the known set;
   NEW = results whose non-null `source_id` is not in it. Then apply `search.freshness` (default `past-2-weeks`):
   drop NEW rows whose `posted_at` is older than the window — the API has no date parameter, so this is a
   client-side filter on `posted_at` (`any` disables it). Null-`source_id` rows can't be deduped → skip, count
   "unidentifiable".
3. **Scan the feed here, in this (primary) context — the cheap first pass.** Review every NEW posting's SUMMARY
   fields (title, company, `location_display`, `salary_display`, `posted_at`). Reject the clearly-irrelevant from
   the summary alone — a must-have plainly violated and stated right in the row (e.g. an onsite-elsewhere
   `location_display`) → record irrelevant, NO detail read. Queue everything relevant-or-uncertain, and for each queued posting jot a one-line
   **steer** for the detail read — your provisional read + the *specific* open questions it must resolve (which
   must-haves are unconfirmed from the summary, what's uncertain), e.g. "looks strong; confirm remote-US —
   location says Austin" or "confirm IC vs manager; seniority unstated". The cheap scan does real work — it
   produces the primary's guidance for each detail review, not just a gate.
4. **Fan out the detail reads — one subagent per queued posting, in PARALLEL.** The reads are independent, so
   dispatch all queued postings **at once, in a single batch** of concurrent subagents (model =
   `search.detail_model`, default `haiku`; `inherit` = this run's own model) — never a one-at-a-time loop. Hand
   each subagent the **orchestration + the primary's steer**: the posting's `id` + `source_url` pair, the brief's
   path, the **`evaluate-job-fit` skill to follow**, and the **per-posting steer from the scan** (your provisional
   read + the specific must-haves/unknowns it should confirm) — brief it like a colleague with zero context (see
   **Briefing each detail subagent**). Never a re-stated rubric — that skill's `SKILL.md`
   is the single source of truth for *how* to judge; the primary supplies *what* to judge and *what to confirm*.
   Each subagent calls `get-posting` with the row's `id` (`--posting_id`) AND its `--source_url` (the same-row
   pair), judges `description_markdown` + `missing_fields[]` (missing = "not stated", never negative) by following
   that skill and **resolving the steer's open questions**, and returns ONLY its `source_id` + the structured
   judgment object. Per-posting errors stay inside that subagent: `400 invalid_pair` (not retryable) → judge from summary,
   note "detail link expired"; `502 detail_fetch_failed` (retryable) → retry/backoff, then summary-only + note.
   **No cap** — every queued posting gets a subagent; the scan (relevance), not a count, decided how many. Running
   them in parallel is the point: it cuts wall-clock, keeps full JDs out of this context, and lets a
   faster/cheaper model do the bulk reads.
5. **Consolidate + persist + report.** Collect the parallel subagents' verdicts and **validate each before it lands**: `match` must be `strong | moderate | weak`, or `null` when `relevant` is false — coerce anything else (a faster delegated model can emit a stray number or out-of-vocab band) and never let a numeric score reach `jobs.jsonl` or the digest. Then for each new posting append the FULL `evaluated` event (complete schema in
   conventions.md §jobs.jsonl) via `python3 "$STATE" append --jobs <workspace>/jobs.jsonl --event '<json>'`.
   The event MUST carry provenance — `event:"evaluated"`, `ts`, `run_id`, `source:"linkedin"`, `query_id`,
   `title`, `company_name`, `location_display`, `salary_display`, `posted_at`, `source_url`,
   `posting_id_at_seen` (the `jp_` id), `detail_read` — AND the judgment — `source_id`, `relevant`, `match`,
   `reasoning`, `dealbreakers_hit`, `unknowns`, `needs_human_check`, `status:"new"`, `first_seen`. Write
   `runs/<run_id>.json` and `reports/<date>-digest.md` (format in conventions.md; strong → moderate → weak,
   then "filtered out: N"). Print a 5-line terminal summary.

## Briefing each detail subagent

`references/parallelism.md` is the general rule (parallel-by-default + how to brief a subagent that starts with
zero context). Applied here: hand each detail subagent the posting's `id`+`source_url` pair, the brief's path,
the `evaluate-job-fit` skill to follow, and your scan's **steer** — the provisional read plus the specific
must-have/unknown to confirm (e.g. *"Strong on AI/LLM-IC-Python; confirm remote-US — `location_display` says
Austin"*). It returns only its `source_id` + the structured judgment object. Keep the steer a provisional read +
open question, never a verdict.

## Narrating a live run (interactive sessions only)

Scheduled/headless invocations stay as they are — quiet until the 5-line summary + digest. But when this
skill runs inside a live conversation (onboarding's first run, "run a search now"), narrate progress
sparsely per `references/voice.md`: one short line per stage, in user outcomes — "Searching for
'<keywords>'…" → "Found N postings — M are new." → "Reading the M promising ones in full…" → then the
matches as normal message text (never a code fence, never just the digest's path). Internal vocabulary
(headless, dedup, database, jobs.jsonl, registry, contract/reference files, skill names) never reaches the
user — see the table in `voice.md`.

## Run health, surfacing & exit codes
Every run ends by writing `runs/<run_id>.json` with at least `{"run_id","run_health",
"error"|null,"ts"}`. **Every HALT path writes this record with `run_health:"blocked"` and
its `E-*` BEFORE stopping** — this is the source the home view reads, so a failed scheduled
run is named on the user's next job-search home view. When a workspace exists, a HALT also writes
the blocked `reports/<date>-digest.md` (named error + fix as the body). If
`notify.desktop_notify_on_block` is true, fire one desktop notification on a blocked run.

Surfacing is the home view + the blocked digest + the desktop notification — NOT the
process exit code. A headless `claude -p` run returns 0 even when blocked (a skill cannot
set the host exit code); do not rely on it, and do not tell the user a cron job's `$?`
will be non-zero.

Exception: **E-NO-CONFIG / first_run** means there is no workspace to write into — this is
inherently visible because the next time the user opens the **job-search** skill it routes
to onboarding. Name the error and stop.

## Idempotency
Re-running the same day re-searches (cheap) but dedup means no posting is re-evaluated or re-read. Never write
a duplicate `evaluated` event for a known `source_id`.
