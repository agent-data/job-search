# Home — the returning-user playbook

You routed here because the Discovery procedure (`internals.md`) reported `first_run: false`. Your job:
show a **compact, glanceable home** for the user's job search, then let them drive the next action by
**chatting**. Think dashboard, not log dump — a few lines they can scan in seconds.

Follow `../../../shared/references/internals.md`, `../../../shared/references/conventions.md`, `../../../shared/references/errors.md`, and `../../../shared/references/voice.md` exactly. No numeric scores.

## Gather

Use the workspace Discovery (SKILL.md Step 0) already found as `<ws>` throughout.

Read just what the home view needs (all local):

- **Schedule marker:** read it from the registry (`internals.md` → Registry) →
  `{"installed":<bool>,"mechanism":<active-mechanism>|null,"set_at":<iso>|null}` — the mechanism value
  is recorded by the active platform (see your platform's adapter → Scheduling).
- **Update status:** follow `../../../shared/references/update.md` (it self-gates on whether the active
  platform's adapter declares a verified update recipe) using the bundled
  `../../../shared/references/build-stamp.md` and the registry `update_check` cache. The result is either
  `update_available` with the local/remote build ids and the active adapter's update recipe, or no signal.
  Any check failure means no signal; the home still renders.
- **Brief age:** the `updated_at:` line near the top of `<ws>/preferences.md` (fall back to `created_at` if absent).
- **Last run health:** the newest `<ws>/runs/*.json` (its `run_health`), or fall back to the **Run health**
  line of the latest digest.
- **Latest digest:** the newest `<ws>/reports/<date>-digest.md` — its date and its **counts line**.
- **Pipeline:** fold `<ws>/jobs.jsonl` per the fold operation in `conventions.md` → current jobs (one per (`source`, `source_id`),
  last-write-wins; records aliased by `same_role_as` count as one role — see the fold operation in
  `conventions.md`). Count by `status` and tally how many have `needs_human_check: true`.

If the workspace is somehow missing its `config.yaml` (e.g. the directory was deleted out from under the
registry), that's **`E-NO-CONFIG`** — say so with its fix ("Run the job-search skill (say 'set up job
search') to set it up") and offer to re-onboard, rather than rendering a broken home.

## Render the home

If `../../../shared/references/update.md` reports `update_available`, print this single banner line first, then the normal
home view:

```text
Update available: Job Search <local_version> <local_hash> -> <remote_version> <remote_hash> — run:
<platform update recipe>
```

Copy `<platform update recipe>` verbatim from the active platform's adapter → Packaging & install. Do not
show this banner on adapters without a verified update recipe.

Keep it tight. A good shape:

```
Job search — <ws path>
Brief: updated <date> (<N months ago>)   ·   Sources: LinkedIn + Ashby   ·   Schedule: <on, daily | off>   ·   Last run: <run health>

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

- **Status line.** Workspace path; brief age from `preferences.md:updated_at` (fallback `created_at`); sources from `config.yaml` `search.sources` (absent → the default pair); render any additional sources (e.g. `+ Greenhouse`, `+ Lever`) when listed; schedule from
  the registry's scheduling marker — render the cadence (from `config.yaml:schedule.frequency`, e.g. "daily")
  when installed, or "off" when not; the marker carries only on/off + the mechanism value recorded at install time
  (the mechanism label is not surfaced in the status line);
  last-run health from the newest `runs/*.json` `run_health` (or the latest digest's Run health line). Run
  health is one of the four run-health states defined in `conventions.md` (the digest "Run health" line).
- **Latest digest.** Read the newest `reports/<date>-digest.md`; show its date and reproduce its **counts
  line** (the `N new · S strong · M moderate · W weak · F filtered out · n searches · m detail reads` line —
  see the digest format in `conventions.md`). If there are no digests yet, say "No runs yet — want me to run
  your first search now?" and offer the run.
- **Pipeline.** From the folded array, counts by `status` (`new | interested | applied | rejected |
  archived`) and the count of `needs_human_check: true` to review. Keep it one line.

## Quick actions (conversational — never make the user edit a file)

Offer these and apply each by **chatting**, editing `config.yaml` per the `internals.md` recipes:

- **Run a search now** → disclose it makes live calls, then invoke `job-search-run` against `<ws>`. On a host
  that gates parallel detail reads behind approval (your platform's adapter → Concurrent detail reads), if
  `search.parallel_detail_reads` is unset, first ask the same one-time parallel-subagent approval from
  `onboarding.md` → Parallel detail-read approval; write the answer to `config.yaml`, and on yes perform the
  host-specific subagent setup the adapter specifies (or show the exact path + content if the sandbox blocks
  the write). If `search.parallel_detail_reads: true`, include the adapter's required authorization sentence
  in the invocation context. Then show the fresh digest's strong/moderate matches with each match's
  reasoning line, link, and any "confirm" warning.
- **Add or edit a query** → append/modify a `queries[]` item
  (`{ id, keywords, location, limit, enabled }`); `limit` is the per-query feed size (its range and default live in `conventions.md`).
  Preserve comments; keep `version: 1`. If the user asks for another search without naming keywords,
  **derive** it from their brief (don't make them pick) and acknowledge what you added — same as onboarding
  step 5.
- **Tune the feed** → set `search.freshness` to narrow or widen the recency window; set `search.detail_model`
  to control which model tier reads full posting details; set `search.sources` to choose job sources (narrow
  to a single board, or add more company boards to widen coverage); and, where the host needs approval, set
  `search.parallel_detail_reads` (`true | false`) to use parallel subagents or read sequentially. The allowed
  values for each key — the freshness windows, the detail-model tiers, and the source list — live in the
  config schema in `conventions.md`. Your platform's adapter → Model tiers maps each detail tier to the actual
  model; when discussing this knob on a specific host, name the exact models from that adapter → Model tiers.
  Edit `config.yaml` per the `internals.md` recipes; preserve comments; keep `version: 1`.
- **Change how often it runs** → set `schedule.frequency` to `hourly | every-2-hours | every-6-hours |
  daily | weekly` (and `schedule.time` for daily/weekly). Reuse the plain-language nudge — "daily suits most
  searches; hourly only for a fast-moving, active search."
- **Update preferences** → invoke `job-preference-interview` (it reads the existing brief and updates it,
  refreshing `updated_at`).
- **Show your preferences brief** → print `<ws>/preferences.md`'s body in your reply as normal message text
  (wherever the user is reading it — no code fence, skip the front-matter lines, never just the path).
- **Change or turn off the schedule** → re-run the scheduling flow in `onboarding.md` with the new cadence,
  then update the scheduling marker. Show the **recurring-run recipe** verbatim from your platform's adapter
  → Run recipe — copy exactly, do not reconstruct the tokens. If `search.parallel_detail_reads: true`, choose
  the adapter's approved-parallel recipe/prompt variant; where the adapter uses a scheduled-prompt
  authorization, the scheduled prompt must include that adapter's required authorization sentence. To turn it
  off, apply the teardown for whichever scheduling tier is active (see your platform's adapter → Scheduling),
  then clear the scheduling marker so it reads `installed: false`, and tell the user it's off.
- **Show the latest digest** → print the newest `reports/<date>-digest.md` (strong → moderate → weak →
  filtered-out) unchanged, as normal message text in your reply (wherever the user is reading it — never
  inside a code fence, never just the file path).

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
experience) — are **planned (Plan C, not yet scheduled)**. Mention them if the user asks what's next, but defer; they
aren't wired yet.
