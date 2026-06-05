---
name: job-search-run
description: Run one job-search pass — load the preferences brief and config, search agent-data for each saved query, dedup against the local job database, judge each new posting's relevance, read full descriptions for promising matches, and write a digest. Use to run the scheduled search, check for new jobs, or when invoked by a schedule.
disable-model-invocation: false
user-invocable: true
---

# job-search-run

Run ONE headless job-search pass over the workspace. Free gates before metered calls; no silent failures.
Read `references/agent-data-contract.md` (CLI + routes + retry rules), `references/errors.md` (every E-* with
the exact cause+fix wording), and `references/conventions.md` (file schemas + digest format) — follow them exactly.

Workspace = the current directory unless `--workspace <path>` is given (a scheduled run's cwd is the
workspace, NOT the repo). The job source listing id is `f9a6ec16-0bfd-44d8-b3ee-073776745ee7`.
Deterministic db ops use `state.py`, bundled in the job-search-os repo at `scripts/state.py` (i.e.
`../../scripts/state.py` relative to THIS skill directory). Resolve its absolute path from the skill's own
location and use it below as `$STATE` — never assume the current directory contains `scripts/`.

**Retries:** branch only on the error envelope's `retryable` boolean (`true` → retry with backoff up to 3×;
`false` → never retry), not on the error `code` string — see `references/agent-data-contract.md`.

## Loop
0. **Preflight (free).**
   - No `config.yaml` → E-NO-CONFIG (HALT, exit 1).
   - `agent-data whoami`; `api_key_set:false` → E-NO-AUTH (HALT, exit 1).
   - `config.yaml` `version` major unknown → E-CONFIG-VERSION (HALT, exit 1).
   - Brief missing/empty (`workspace.preferences_path`) → E-NO-PREFERENCES (HALT, exit 1, named fix).
   - `agent-data call <listing> status`: `ok` proceed; `degraded` set a flag (cap detail reads at ~2 this run,
     set Run health: degraded, note "LinkedIn flaky" in the digest); unreachable → E-SERVICE-DOWN (write a
     "service down" digest, HALT, exit 1).
1. **Search (one metered call per enabled query).** For each `queries[]` with `enabled:true`, call `search-jobs`
   with `--keywords` (+ `--location`, `--limit`) and `--fields id,source_id,source_url,title,company_name,location_display,salary_display,posted_at,detail_available,source`.
   - `502 search_failed` (retryable) → retry up to 3× with backoff; on give-up record the error and continue.
     **Two consecutive 502s across queries → E-UPSTREAM-STRETCH: stop searching.**
   - `422`/`400 unsupported_field` → E-BAD-QUERY (name the bad param from `details[].loc`), skip that query.
   - A quota/limit/payment failure (see errors.md detection) → E-QUOTA (HALT, exit 1).
2. **Dedup (free).** `python3 "$STATE" known-ids --jobs <workspace>/jobs.jsonl` → the known set.
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
   - If many look relevant, read the most promising first (≈up to 5–10 on a healthy run, ~2 when degraded) and
     mark the rest "summary-only, not yet fully read" in the digest.
5. **Persist + report.** For each new posting, append the FULL `evaluated` event (complete schema in
   conventions.md §jobs.jsonl) via `python3 "$STATE" append --jobs <workspace>/jobs.jsonl --event '<json>'`.
   The event MUST carry provenance — `event:"evaluated"`, `ts`, `run_id`, `source:"linkedin"`, `query_id`,
   `title`, `company_name`, `location_display`, `salary_display`, `posted_at`, `source_url`,
   `posting_id_at_seen` (the `jp_` id), `detail_read` — AND the judgment — `source_id`, `relevant`, `match`,
   `reasoning`, `dealbreakers_hit`, `unknowns`, `needs_human_check`, `status:"new"`, `first_seen`. Write
   `runs/<run_id>.json` and `reports/<date>-digest.md` (format in conventions.md; strong → moderate → weak,
   then "filtered out: N"). Print a 5-line terminal summary.

## Run health & exit codes
Every digest starts with a **Run health** line (`healthy | partial | degraded | blocked`). HALT paths
(E-NO-CONFIG, E-NO-AUTH, E-CONFIG-VERSION, E-NO-PREFERENCES, E-SERVICE-DOWN, E-QUOTA) exit non-zero so a schedule
surfaces them; if `notify.desktop_notify_on_block` is true, fire one desktop notification on a blocked run.
Successful/partial runs exit 0.

## Idempotency
Re-running the same day re-searches (cheap) but dedup means no posting is re-evaluated or re-read. Never write
a duplicate `evaluated` event for a known `source_id`.
