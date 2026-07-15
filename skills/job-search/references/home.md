# Home — the returning-user playbook

You routed here because the Discovery procedure (`internals.md`) reported `first_run: false`. Your job:
show a **compact, glanceable home** for the user's job search, then let them drive the next action by
**chatting**. Think dashboard, not log dump — a few lines they can scan in seconds.

Follow `../../../shared/references/internals.md`, `../../../shared/references/conventions.md`, `../../../shared/references/errors.md`, and `../../../shared/references/voice.md` exactly. No numeric scores.

**Contents:** [Gather](#gather) · [Render the home](#render-the-home) · [Quick actions](#quick-actions-conversational--never-make-the-user-edit-a-file) · [Nudges](#nudges-surface-only-when-they-apply) · [Coming soon (Plan C)](#coming-soon-plan-c)

## Gather

Use the workspace Discovery (SKILL.md Step 0) already found as `<ws>` throughout.

Read just what the home view needs (all local):

- **Schedule marker:** read it from the registry (`internals.md` → Registry) →
  `{"installed":<bool>,"mechanism":<active-mechanism>|null,"set_at":<iso>|null}` — the mechanism value
  records the scheduler the recurring run was bound to, set by the scheduling flow (`internals.md` →
  Registry write rules).
- **Update status:** follow `../../../shared/references/update.md` (it self-gates on the cached update
  signal) using the bundled `../../../shared/references/build-stamp.md` and the registry `update_check`
  cache. The result is either `update_available` with the local/remote build ids, or no signal.
  Any check failure means no signal; the home still renders.
- **Brief age:** the `updated_at:` line near the top of `<ws>/preferences.md` (fall back to `created_at` if absent).
- **Config facts:** from `<ws>/config.yaml`, count enabled queries and read `search.sources` (using its
  documented default when absent), `schedule.frequency`, and whether `search.max_new_postings_per_run` is
  omitted, finite, or `"all"`. These facts drive review-depth previews; do not estimate from the last run.
- **Last run health, usage, and depth evidence:** the newest `<ws>/runs/*.json`—its `run_health`,
  `review_scope`, `agent_data_usage`, and `pagination_metrics`—or fall back to the **Run health** line of the
  latest digest only when no run record exists. Nudge eligibility comes only from the newest run record,
  never from a digest inference or an older run.
- **Deeper-coverage marker:** expand `<ws>` to its absolute path and read that exact workspace's entry from
  the registry `deeper_coverage_nudges` map (`internals.md` → Registry). Absence means no marker; another
  workspace's marker does not count.
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
<host update command>
```

Fill `<host update command>` from your host's own plugin/skill update mechanism, per `update.md` → Banner
— the command that updates an already-installed plugin/skill on the host you're running on.

Keep it tight. A good shape:

```
Job search — <ws path>
Brief: updated <date> (<N months ago>)   ·   Sources: LinkedIn + Ashby   ·   Schedule: <on, daily | off>   ·   Last run: <run health>

Latest digest — <date>
  <N> new postings · <S> strong · <M> moderate · <W> weak · <F> filtered out · <n> searches · <m> detail reads

Pipeline
  new <n> · interested <n> · applied <n> · rejected <n> · archived <n>     (<k> need a human check)

What next? Just tell me:
  • run a search now            • add or edit a query
  • change how often it runs    • tune the feed
  • review deeper results       • explain agent-data usage
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
  that gates parallel detail reads behind approval, if
  `search.parallel_detail_reads` is unset, first ask the same one-time parallel-subagent approval from
  `onboarding.md` → Parallel detail-read approval; write the answer to `config.yaml`, and on yes perform any
  host-specific subagent setup your host needs (or show the exact path + content if the sandbox blocks
  the write). If `search.parallel_detail_reads: true`, include the authorization sentence your host requires
  in the invocation context. Then show the fresh digest's strong/moderate matches with each match's
  reasoning line, link, and any "confirm" warning.
- **Add or edit a query** → append/modify a `queries[]` item
  (`{ id, keywords, location, limit, enabled }`); `limit` is the per-query feed size (its range and default live in `conventions.md`).
  Preserve comments; keep `version: 1`. If the user asks for another search without naming keywords,
  **derive** it from their brief (don't make them pick) and acknowledge what you added — same as onboarding
  step 5.
- **Tune the feed** → set `search.freshness` to narrow or widen the recency window (applied server-side), or just ask for a window in the moment — "jobs from the last day" — and that search uses it; set `search.detail_model`
  to control which model tier reads full posting details; set `search.sources` to choose job sources (narrow
  to a single board, or add more company boards to widen coverage); and, where the host needs approval, set
  `search.parallel_detail_reads` (`true | false`) to use parallel subagents or read sequentially. The allowed
  values for each key — the freshness windows, the detail-model tiers, and the source list — live in the
  config schema in `conventions.md`. The agent binds each detail tier to a concrete model from its own roster;
  when the user asks which model a tier maps to on this host, name the concrete model you'd use.
  Edit `config.yaml` per the `internals.md` recipes; preserve comments; keep `version: 1`.
- **Review deeper results** → interpret one-off versus saved wording and follow **Review-depth changes**
  below. `queries[].limit` remains per-call page size; `search.max_new_postings_per_run` controls the run's
  review depth. Never turn a role target into a credit allowance or a promised page-call cap.
- **Explain agent-data usage** → follow **Usage help** below. This is a local read-only action; it does not
  call agent-data or change config/registry state.
- **Change how often it runs** → set `schedule.frequency` to `hourly | every-2-hours | every-6-hours |
  daily | weekly` (and `schedule.time` for daily/weekly). Reuse the plain-language nudge — "daily suits most
  searches; hourly only for a fast-moving, active search."
- **Update preferences** → invoke `job-preference-interview` (it reads the existing brief and updates it,
  refreshing `updated_at`).
- **Show your preferences brief** → print `<ws>/preferences.md`'s body in your reply as normal message text
  (wherever the user is reading it — no code fence, skip the front-matter lines, never just the path).
- **Change or turn off the schedule** → re-run the scheduling flow in `onboarding.md` with the new cadence,
  then update the scheduling marker. Show the **recurring-run recipe** composed for the host verbatim —
  copy exactly, do not reconstruct the tokens; when `search.parallel_detail_reads: true`, the composed
  recipe must carry whatever authorization the host's unattended parallel fan-out needs. To turn it
  off, stop the active schedule, then clear the scheduling marker (`internals.md` → Registry write rules)
  so it reads `installed: false`, and tell the user it's off.
- **Show the latest digest** → print the newest `reports/<date>-digest.md` (strong → moderate → weak →
  filtered-out) unchanged, as normal message text in your reply (wherever the user is reading it — never
  inside a code fence, never just the file path).

### Review-depth changes

Resolve the user's time scope with the table in `../../../shared/references/internals.md` → Config
read/update recipes. “Now,” “once,” or “this run” is one-off; “each run,” “from now on,” or “every time” is
saved. An ambiguous depth request such as “scan everything” defaults to one run, and the preview says so.

For any enablement or increase—first-page coverage to finite, a larger finite target, or finite to
`"all"`—perform these steps in order:

1. Count current enabled queries and enabled sources. State the exact first-page baseline as
   `<enabled queries> × <enabled sources> = <metered search calls per run>`.
2. Multiply that baseline by the current schedule for a named period and label calendar totals as
   approximate. For a one-off request, say the schedule does not multiply this run, then show the saved
   cadence's multiplication only as a comparison. If scheduling is off, say there is no recurring
   multiplier.
3. State the additions that cannot be known in advance: every continuation page on one company-board
   stream adds one metered search call, and every full-posting read adds one metered detail call. A finite
   target limits unique roles reviewed, not page calls; `"all"` has no reliable call ceiling. LinkedIn
   remains one page.
4. Ask a closed yes/no for the exact target and exact one-off or saved scope. Before yes, do not invoke the
   runner and do not change config. After yes, either pass the one-off scope to `job-search-run` without a
   config write or atomically write the saved value, then take the requested action.

Load any current metering or rate fact from
`../../../shared/references/agent-data-contract.md`; do not copy it here. A saved value is durable consent,
so scheduled runs use it without asking again. A smaller finite target, `all` to finite, removal, or a
one-off first-page override is reversible: apply it immediately without confirmation, preserve `version: 1`,
and never add a `budget`, `credits`, or `cost` config field.

### Usage help

For “explain my usage,” read recent local `runs/*.json` records and lead with actual
`agent_data_usage.metered_calls`. Explain the stored `by_operation` breakdown and the outcome drivers in
the current config: schedule, enabled queries, enabled sources, and review mode. Use each historical run's
stored decimal equivalent as written rather than recomputing it against today's rate.

When an equivalent is present, label it **pay-as-you-go equivalent**. If live account-plan metadata is not
available, say it is not an actual charge and direct account-specific questions to
<https://agent-data.motie.dev/settings/billing>. Do not infer remaining allowance, current plan, rollover,
renewal, or exhaustion. Make no agent-data call and write no config or registry state for this explanation.
Current exact pricing and metering facts stay in `../../../shared/references/agent-data-contract.md`.

## Nudges (surface only when they apply)

- **Stale brief.** If `preferences.md:updated_at` (fallback `created_at`) is older than ~3 months, gently suggest a refresh: "Your
  preferences are about <N> months old — want to update them? Just say so and I'll walk through it." (This
  mirrors the digest's brief-age footnote.)
- **Deeper company-board coverage (one time per absolute workspace).** Render this only when the newest run
  is `first_page`, `pagination_metrics.deeper_coverage_nudge_eligible` is `true`,
  `unique_unseen_roles_first_pages` is zero, at least one listed healthy cursor-capable stream has trustworthy
  `has_more_at_stop:true`, and the absolute workspace has no registry marker. Explain that the last search
  found no unseen roles in its first pages while deeper results were available, then offer deeper
  company-board coverage. State that each additional board page and full-posting read adds a metered call;
  do not expose cursor strings or turn the home into a page browser.

  If the user asks to enable depth, follow **Review-depth changes**—including the exact first-page baseline,
  schedule multiplication, unknown additions, and confirmation—before running or writing config. After the
  displayed nudge resolves, atomically merge exactly one marker for the absolute workspace per
  `internals.md`: `enabled` only after the confirmed enablement takes effect, `declined` for no, and
  `deferred` when the user says later or chooses another action. Preserve all unknown registry keys. A
  present marker suppresses every later automatic nudge for that workspace, including declined/deferred;
  the user can still ask for depth later. Scheduled runs write eligibility evidence only and never this
  shown/outcome marker.
- **Last run blocked/failed.** If the newest run's `run_health` is `blocked` (or the latest digest shows a
  blocked/failed run), name the specific **`E-*`** from `errors.md` with its cause + fix — e.g. `E-QUOTA`
  (restore access at https://agent-data.motie.dev/settings/billing; existing matches are unaffected; discuss
  usage levers only if the user asks), `E-NO-AUTH` (re-export the key), `E-SERVICE-DOWN` (temporary; next run
  retries). Don't bury a failure inside an otherwise-cheery home.

## Coming soon (Plan C)

Resume actions — **compare** your resume against a match and **tailor** it (truthfully, never inventing
experience) — are **planned (Plan C, not yet scheduled)**. Mention them if the user asks what's next, but defer; they
aren't wired yet.
