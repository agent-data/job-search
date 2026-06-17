# Home — the returning-user playbook

You routed here because the Discovery procedure (`internals.md`) reported `first_run: false`. Your job:
show a **compact, glanceable home** for the user's job search, then let them drive the next action by
**chatting**. Think dashboard, not log dump — a few lines they can scan in seconds.

Follow `internals.md`, `conventions.md`, `errors.md`, and `voice.md` exactly. No numeric scores.

## Gather

Use the workspace Discovery (SKILL.md Step 0) already found as `<ws>` throughout.

Read just what the home view needs (all local):

- **Schedule marker:** read it from the registry (`internals.md` → Registry) →
  `{"installed":<bool>,"mechanism":"loop"|null,"set_at":<iso>|null}`.
- **Brief age:** the `updated_at:` line near the top of `<ws>/preferences.md` (fall back to `created_at` if absent).
- **Last run health:** the newest `<ws>/runs/*.json` (its `run_health`), or fall back to the **Run health**
  line of the latest digest.
- **Latest digest:** the newest `<ws>/reports/<date>-digest.md` — its date and its **counts line**.
- **Pipeline:** fold `<ws>/jobs.jsonl` per the fold operation in `conventions.md` → current jobs (one per
  `source_id`, last-write-wins). Count by `status` and tally how many have `needs_human_check: true`.

If the workspace is somehow missing its `config.yaml` (e.g. the directory was deleted out from under the
registry), that's **`E-NO-CONFIG`** — say so with its fix ("Run the job-search skill (say 'set up job
search') to set it up") and offer to re-onboard, rather than rendering a broken home.

## Render the home

Keep it tight. A good shape:

```
Job search — <ws path>
Brief: updated <date> (<N months ago>)   ·   Schedule: <on, daily via /loop | off>   ·   Last run: <healthy | partial (N) | degraded | blocked>

Latest digest — <date>
  9 new postings · 3 strong · 2 moderate · 1 weak · 3 filtered out · <n> searches · <m> detail reads

Pipeline
  new 12 · interested 4 · applied 2 · rejected 6 · archived 1     (3 need a human check)

What next? Just tell me:
  • run a search now            • add or edit a query
  • change how often it runs    • tune the feed
  • update your preferences     • change or turn off the schedule
  • show the latest digest      • show your preferences brief
```

Notes on each part:

- **Status line.** Workspace path; brief age from `preferences.md:updated_at` (fallback `created_at`); schedule from
  the registry's scheduling marker (on + mechanism, or off) — the **frequency** to render (e.g. "daily" in "daily via /loop")
  comes from `config.yaml:schedule.frequency`, since the marker carries only on/off + mechanism;
  last-run health from the newest `runs/*.json` `run_health` (or the latest digest's Run health line). Run
  health is one of `healthy | partial (N errors) | degraded (LinkedIn flaky) | blocked (action needed)`.
- **Latest digest.** Read the newest `reports/<date>-digest.md`; show its date and reproduce its **counts
  line** (the `N new · S strong · M moderate · W weak · F filtered out · n searches · m detail reads` line —
  see the digest format in `conventions.md`). If there are no digests yet, say "No runs yet — want me to run
  your first search now?" and offer the run.
- **Pipeline.** From the folded array, counts by `status` (`new | interested | applied | rejected |
  archived`) and the count of `needs_human_check: true` to review. Keep it one line.

## Quick actions (conversational — never make the user edit a file)

Offer these and apply each by **chatting**, editing `config.yaml` per the `internals.md` recipes:

- **Run a search now** → invoke `job-search-run` against `<ws>` (disclose it makes live calls), then
  show the fresh digest's strong/moderate matches.
- **Add or edit a query** → append/modify a `queries[]` item
  (`{ id, keywords, location, limit, enabled }`); `limit` is the per-query feed size (1–100, default 25).
  Preserve comments; keep `version: 1`. If the user asks for another search without naming keywords,
  **derive** it from their brief (don't make them pick) and acknowledge what you added — same as onboarding
  step 5.
- **Tune the feed** → set `search.freshness` (`any | past-week | past-2-weeks | past-month`) to narrow or
  widen the recency window, and/or set `search.detail_model` (`haiku | sonnet | opus | inherit`) to control
  which model reads full posting details (default `haiku`). Edit `config.yaml` per the `internals.md`
  recipes; preserve comments; keep `version: 1`.
- **Change how often it runs** → set `schedule.frequency` to `hourly | every-2-hours | every-6-hours |
  daily | weekly` (and `schedule.time` for daily/weekly). Reuse the plain-language nudge — "daily suits most
  searches; hourly only for a fast-moving, active search."
- **Update preferences** → invoke `job-preference-interview` (it reads the existing brief and updates it,
  refreshing `updated_at`).
- **Show your preferences brief** → print `<ws>/preferences.md`'s body in your reply as normal message text
  (rendered markdown — no code fence, skip the front-matter lines, never just the path).
- **Change or turn off the schedule** → re-run the scheduling flow in `onboarding.md`: compose the
  `/loop …` line from the interval table in `internals.md` → Scheduling setup, run it, then set the
  scheduling marker; always show the verbatim `/loop` recipe from `internals.md`. To turn it off, stop the
  loop (end the session or cancel the pending wakeup), then clear the scheduling marker so it reads
  `installed: false`, and tell the user it's off.
- **Show the latest digest** → print the newest `reports/<date>-digest.md` (strong → moderate → weak →
  filtered-out) unchanged, as normal message text in your reply (rendered markdown — never inside a code
  fence, never just the file path).

## Nudges (surface only when they apply)

- **Stale brief.** If `preferences.md:updated_at` (fallback `created_at`) is older than ~3 months, gently suggest a refresh: "Your
  preferences are about <N> months old — want to update them? Just say so and I'll walk through it." (This
  mirrors the digest's brief-age footnote.)
- **Last run blocked/failed.** If the newest run's `run_health` is `blocked` (or the latest digest shows a
  blocked/failed run), name the specific **`E-*`** from `errors.md` with its cause + fix — e.g. `E-QUOTA`
  (pull less often or upgrade; existing matches unaffected), `E-NO-AUTH` (re-export the key), `E-SERVICE-DOWN`
  (temporary; next run retries). Don't bury a failure inside an otherwise-cheery home.

## Coming soon (Plan C)

Resume actions — **compare** your resume against a match and **tailor** it (truthfully, never inventing
experience) — are **coming soon (Plan C)**. Mention them if the user asks what's next, but defer; they
aren't wired yet.
