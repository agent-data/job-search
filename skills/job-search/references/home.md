# Home — the returning-user playbook

You routed here because the Discovery procedure (`internals.md`) reported `first_run: false`. Your job:
show a **compact, glanceable home** for the user's job search, then let them drive the next action by
**chatting**. Think dashboard, not log dump — a few lines they can scan in seconds.

Follow `../../../shared/references/internals.md`, `../../../shared/references/conventions.md`, `../../../shared/references/errors.md`, and `../../../shared/references/voice.md` exactly. No numeric scores.
For every run record or digest, also follow `../../../shared/references/run-lifecycle.md` → **Artifact
authority for every reader**: invoke `lifecycle-fold.sh` for the candidate's exact run_id, require
`closed=true` plus matching folded record state, and use only that fold-derived digest. An open ledger,
including an intended-complete pre-close file window, is not a home run and is excluded.

**Contents:** [Gather](#gather) · [Render the home](#render-the-home) · [Quick actions](#quick-actions-conversational--never-make-the-user-edit-a-file) · [Applying your feedback](#applying-your-feedback-steering-the-search) · [Nudges](#nudges-surface-only-when-they-apply) · [Coming soon (Plan C)](#coming-soon-plan-c)

## Gather

Use the workspace Discovery (SKILL.md Step 0) already found as `<ws>` throughout.

Read just what the home view needs (all local):

- **Schedule marker:** read it from the registry (`internals.md` → Registry) → the `scheduling` object
  (`installed`/`verified` booleans, `mechanism`, `set_at`, and the rest of the expanded state). Apply the
  read semantics there: an absent `verified` reads `false`, a legacy `mechanism: loop` marker reads
  **session-only**, and a legacy installed-only marker (no `verified`/`verified_at`/`canary_run_id`) reads
  **unverified** — never verified. Reading never rewrites the marker.
- **Schedule health (derived — local + unmetered):** for an installed schedule, derive its ongoing health per
  `../../../shared/references/internals.md` → **Schedule health**. This is a local, unmetered read (never a
  scheduler trigger or a metered call) that compares the registry marker, the scheduler's own local
  registration (read it back and compare it to what the registry recorded), and the **latest
  scheduled-attributable run** — the newest `trigger: scheduled` run per
  `../../../shared/references/conventions.md` → Latest scheduled-attributable run, with the `canary_run_id`
  canary excluded — using the configured cadence/time/timezone and the documented 30-minute post-fire grace
  period. It resolves to **exactly one** state in that precedence: registration drift · latest scheduled run
  blocked · needs attention (two or more missed fires) · not recently observed (one missed fire) ·
  verified/running · unverified · session-only · absent.
- **Update status:** follow `../../../shared/references/update.md` (it self-gates on the cached update
  signal) using the bundled `../../../shared/references/build-stamp.md` and the registry `update_check`
  cache. The result is either `update_available` with the local/remote build ids, or no signal.
  Any check failure means no signal; the home still renders.
- **Brief age:** the `updated_at:` line near the top of `<ws>/preferences.md` (fall back to `created_at` if absent).
- **Config facts:** from `<ws>/config.yaml`, count enabled queries and read `search.sources` (using its
  documented default when absent), `schedule.frequency`, and whether `search.max_new_postings_per_run` is
  omitted, finite, or `"all"`. These facts drive review-depth previews; do not estimate from the last run.
  This is a passive version-1 home read when the config major is 1: preserve `config.yaml` byte-for-byte,
  do not create `runs/detail-model-binding.json`, and do not migrate merely to render the home.
- **Last run health, usage, and depth evidence:** among complete-name-matching candidates, first apply the
  lifecycle authority procedure above, then choose the newest authoritative closed run and read its
  `run_health`, `review_scope`, `agent_data_usage`, and `pagination_metrics`. Nudge eligibility comes only
  from that record, never from a digest inference, an older run, or an unclosed candidate.
- **Deeper-coverage marker:** expand `<ws>` to its absolute path and read that exact workspace's entry from
  the registry `deeper_coverage_nudges` map (`internals.md` → Registry). Absence means no marker; another
  workspace's marker does not count.
- **Query-health nudge marker:** read the registry's single `query_health_nudge` object (`internals.md` →
  Registry). Absence means no query-health nudge has been shown. It only records what was already said —
  it never proves anything about retrieval — and reading it never rewrites it.
- **Query-health evidence (derived — local + unmetered):** skip this entirely when that marker's stored
  `search_shape` still matches the current saved shape. Otherwise, and only if the workspace already holds
  them, scan back from the newest run record and take the first three that are both
  **lifecycle-authoritative** — closed, complete, non-canary runs that pass the artifact-authority procedure
  above — and *comparable* to today's saved search: every stream carries the current request fields
  (`../../../shared/references/conventions.md` → the request evidence every stream records) with
  `request_origin: saved`; the enabled queries, sources, locations, limits, and saved `search.freshness`
  selector match `config.yaml` — that saved selector, never the rolling cutoff a particular run happened to
  send; and for the source being judged, every enabled stream succeeded (no `source_failed` or
  `pagination_incomplete` stop, and that source absent from `sources_failed`). Then sum each source's raw
  `results_returned` across its enabled streams, per run. A record that misses any request field, holds a
  failed stream, or ran a one-off override is **skipped** — never counted toward the three, and never padded
  out with weaker evidence; keep scanning further back for records that do qualify. Fewer than three
  comparable records anywhere means there is nothing to assess. This read is local and unmetered.
- **Latest digest:** the exact digest derived by the selected run's fold — its date and **counts line**.
  Never select a digest independently by filename.
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
Brief: updated <date> (<N months ago>)   ·   Sources: LinkedIn + Ashby   ·   Schedule: <daily | daily · not recently observed | session-only | off>   ·   Last run: <run health>

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
  the **derived Schedule health** state (`internals.md` → Schedule health) gathered above — render the cadence
  (from `config.yaml:schedule.frequency`, e.g. "daily") for a **verified/running** schedule, and for a live
  but degraded schedule append the derived label: "daily · not recently observed" after one missed fire,
  "daily · needs attention (overdue)" after two or more, "daily · last scheduled run blocked", or "daily ·
  schedule registration drifted"; "session-only" for a session-only loop; "unverified" for an
  installed-but-unverified marker; and "off" when not installed (a legacy installed-only/unverified marker is
  not a verified schedule — don't render it as "on"); the mechanism token itself is not surfaced in the status
  line. This label only names the derived state; the cause-and-fix for a **blocked** run is the "Last run
  blocked/failed" nudge below (owned by `errors.md`), not re-rendered here.
  Last-run health comes from the newest lifecycle-authorized closed `runs/<run_id>.json` `run_health`. Run
  health is one of the four run-health states defined in `conventions.md` (the digest "Run health" line).
- **Latest digest.** Read the exact fold-derived digest for that same authorized run; show its date and reproduce its **counts
  line** (the `N new · S strong · M moderate · W weak · F filtered out · n searches · m detail reads` line —
  see the digest format in `conventions.md`). If there are no digests yet, say "No runs yet — want me to run
  your first search now?" and offer the run.
- **Pipeline.** From the folded array, counts by `status` (`new | interested | applied | rejected |
  archived`) and the count of `needs_human_check: true` to review. Keep it one line.

## Quick actions (conversational — never make the user edit a file)

Offer these and apply each by **chatting**, editing `config.yaml` per the `internals.md` recipes. Preserve the
existing config major on ordinary edits. For version 2, an ordinary edit does not write model-binding
provenance: require the current `runs/detail-model-binding.json` to be valid and preserve it byte-for-byte.
Only a model-binding write refreshes that sidecar with a fresh binding id, even when the exact model is
unchanged. A version-1 workspace remains readable and runnable through bounded compatibility: compatible
query, freshness, source, parallelism, schedule-field, and review-depth edits preserve version 1. Only an
action that requires an exact version-2 binding—such as changing the detail model or creating verified
scheduling—routes through the canonical **Version-1 staged migration** transaction in
`../../../shared/references/internals.md`; ordinary edits do not.

- **Run a search now** → disclose it makes live calls, then invoke `job-search-run` against `<ws>`. On a host
  that gates parallel detail reads behind approval, if
  `search.parallel_detail_reads` is unset, first ask the same one-time parallel-subagent approval from
  `onboarding.md` → Parallel detail-read approval; write the answer to `config.yaml`, and on yes perform any
  host-specific subagent setup your host needs (or show the exact path + content if the sandbox blocks
  the write). If `search.parallel_detail_reads: true`, include the authorization sentence your host requires
  in the invocation context. Then show the fresh digest's strong/moderate matches with each match's
  reasoning line, link, and any "confirm" warning — a relevant match shown with its reasoning is the
  **activation** defined in `../../../shared/references/run-lifecycle.md` → **Activation** (a nonblocked run,
  at least one fully evaluated posting, and at least one relevant match shown with reasoning); a blocked run
  or a match not yet shown is not. If the run came back nonblocked and judged postings but surfaced **no
  relevant match**, apply `../../../shared/references/run-lifecycle.md` → **Zero-relevant recovery** instead
  of a matches list — a completed outcome about fit, not proof the queries were too narrow. Say it ran and
  what it learned, don't imply a match landed, and offer exactly **one** high-signal next step (not a list),
  chosen from the rejection reasons where the run's raw per-source volume came back healthy rather than from
  the relevance count; if the user takes it, that fresh search is a new run and gets new calls-first cost
  context before its calls.
- **Add or edit a query** → append/modify a `queries[]` item
  (`{ id, keywords, location, limit, enabled }`); `limit` is the per-query feed size (its range and default live in `conventions.md`).
  Preserve comments and preserve the existing config major. If the user asks for another search without naming keywords,
  **derive** it from their brief (don't make them pick) and acknowledge what you added — same as onboarding
  step 5.
- **Tune the feed** → set `search.freshness` to narrow or widen the recency window (applied server-side), or just ask for a window in the moment — "jobs from the last day" — and that search uses it; set `search.detail_model`
  through setup, an explicit conversational user choice (`configured_user`), or interactive repair to an
  exact available model identifier; set `search.sources` to choose job sources (narrow
  to a single board, or add more company boards to widen coverage); and, where the host needs approval, set
  `search.parallel_detail_reads` (`true | false`) to use parallel subagents or read sequentially. The allowed
  values and exact-model ownership live in `conventions.md`; the setup/repair selection policy lives in
  `internals.md`. Edit `config.yaml` per those recipes and preserve comments plus the existing config major.
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
- **Change or turn off the schedule** → an explicit ask to (re)schedule re-runs the **one-decision handoff**
  in `onboarding.md` §7 (**Daily — recommended / Different schedule / Not now** → one scoped confirmation →
  the config-time canary), then updates the scheduling marker. Record the marker (and re-render the schedule
  as on) only **after the green canary**; on a scheduled choice, show the **recurring-run recipe** composed for
  the host verbatim — copy exactly, do not reconstruct the tokens; when `search.parallel_detail_reads: true`,
  the composed recipe must carry whatever authorization the host's unattended parallel fan-out needs. On **Not
  now**, leave it unscheduled and **do not dump the recipe blocks**. To turn it off, stop the active schedule,
  then clear the scheduling marker (`internals.md` → Registry write rules) so it reads `installed: false`, and
  tell the user it's off.
- **Show the latest digest** → print the exact fold-derived digest for the newest authorized closed run (strong → moderate → weak →
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
2. For a saved request, load the exact saved-cadence comparison window and run count from
   `../../../shared/references/internals.md` → “Choose one-off or saved review depth”; do not substitute
   another period. Multiply the first-page baseline by that run count and label the result approximate. If
   scheduling is off, say there is no recurring multiplier. For a one-off request, say the run does not
   change the recurring schedule and do not attach a recurring multiplier.
3. State the additions that cannot be known in advance: every continuation page on one company-board
   stream adds one metered search call, and every full-posting read adds one metered detail call. A finite
   target limits unique roles reviewed, not page calls; `"all"` has no reliable call ceiling. LinkedIn
   remains one page.
4. Apply the resolved scope:
   - A one-off request is scoped consent after the concise preview: run it once without a second confirmation
     question and apply the one-off write effect below.
   - For a saved request, ask a closed yes/no for the exact target. Before yes, do not invoke the runner and
     do not change config. After yes, apply the matching saved write effect below, then take the requested
     action.

- **Saved version-2 depth-only edit:** atomically update only the depth value, preserve the existing config
  major, and leave a valid `runs/detail-model-binding.json` byte-for-byte unchanged.
- **Saved version-1 depth-only edit:** atomically update only the depth value, preserve version 1, and write
  no sidecar.
- **One-off:** pass the scope to `job-search-run` and write neither config nor sidecar.

Load any current metering or rate fact from
`../../../shared/references/agent-data-contract.md`; do not copy it here. A saved value is durable consent,
so scheduled runs use it without asking again. A smaller finite target, `all` to finite, removal, or a
one-off first-page override is reversible: apply it immediately without confirmation using the same
version-2, version-1, or one-off write effect above, and never add a `budget`, `credits`, or `cost` config
field.

### Usage help

For “explain my usage,” read only recent local `runs/<run_id>.json` records that pass the exact run_id and
closed-ledger authority procedure above, and lead with actual
`agent_data_usage.metered_calls`. Explain the stored `by_operation` breakdown and the outcome drivers in
the current config: schedule, enabled queries, enabled sources, and review mode. Use each historical run's
stored decimal equivalent as written rather than recomputing it against today's rate.

When an equivalent is present, label it **pay-as-you-go equivalent**. If live account-plan metadata is not
available, say it is not an actual charge and direct account-specific questions to
<https://agent-data.motie.dev/settings/billing>. Do not infer remaining allowance, current plan, rollover,
renewal, or exhaustion. Make no agent-data call and write no config or registry state for this explanation.
Current exact pricing and metering facts stay in `../../../shared/references/agent-data-contract.md`.

## Applying your feedback (steering the search)

When the user reacts to what they see — a match, the digest, the pipeline, or what they want overall — route
that reaction by **what kind of change it is**, apply it immediately at the right scope, and confirm in one
line. This is the **single home** for feedback routing: the interview skill and the operator manual point
here rather than restate it. It also does not restate the contracts it uses — the `brief_revision` ledger
event and the in-flight settling rule are owned by `../../../shared/references/run-lifecycle.md`, and the
agent-data usage-decision table is owned by `../../../shared/references/internals.md` — it routes to them one
hop. Apply this in both modes: the front-door `SKILL.md` routes here for the returning home and after the
first-run results.

| Feedback | Scope | What you do |
|---|---|---|
| **Clear general preference** — "across the board I only want fully-remote roles", "drop anything below ~$180K base" | the brief | Update `preferences.md` immediately (via `job-preference-interview`, folding it into the right bucket and refreshing `updated_at`). If a run is in flight, **record the brief revision on it** — increment the revision and append one `brief_revision` event to the active run's open ledger per `run-lifecycle.md` (the identifier only, never the preferences text; the ledger stays coordinator-written). Confirm in **one line**. Then apply it per **Applying a preference change** below. |
| **Posting-specific** — "not this company", "already applied here", "not this one" | pipeline only | Change only that posting's `status` with a `jobs.jsonl` `status_changed` event (`../../../shared/references/conventions.md` → jobs.jsonl) — never the brief, no revision — **unless** the user generalizes it ("no companies like X", "nothing in adtech"). A generalization is a general preference: take the brief row above instead. |
| **Ambiguous** — "the location's not right", "too junior" | ask once, only if it matters | Ask **one** short clarification **only when the interpretation would change the result** (different readings keep different postings relevant, or edit different buckets). When every reasonable reading lands the same way, pick one and proceed — do not ask a question whose answer cannot change what you do. |
| **Retrieval-changing** — "also search Greenhouse and Lever", "look at the last day", "open it up to the whole US" | new search / config | **Preview agent-data impact first.** Classify the change with `../../../shared/references/internals.md` → **Agent-data usage decisions** and render its row's context with `../../../shared/references/voice.md` → **Agent-data usage context** before any new search or persistent write. A one-off request is scoped consent to run once (context, then run); a saved change asks one scoped confirmation before the atomic write. |

**Applying a preference change** (the general-preference row, and a posting-specific note the user generalized):

- **Remaining queue.** Apply the new brief revision to every posting still to be judged — the run's `queued`
  postings are evaluated under it as they come up. Don't block, cancel, or restart the run to do this.
- **Already-shown jobs — recheck only when the outcome could change.** Re-judge an already-shown posting
  **only when the edit could move its verdict** — a tightened must-have a shown match no longer clears, or a
  loosened constraint that could now let a previously-excluded posting back in. When the edit **cannot** change
  what the user already saw (it tightens or loosens a dimension a shown posting already clears, or already
  fails, on the same side; or it doesn't apply to those postings), leave the shown verdict as it stands.
  Re-evaluating already-shown postings when the outcome cannot change is a non-goal — don't spend a detail read
  or re-emit a verdict for no reason.
- **In-flight evaluations settle first.** An evaluation already under way finishes and settles under the brief
  revision it started on **before** the new revision applies to later reviews. That settling ordering — and
  what it means for the started detail worker's judgment — is owned by
  `../../../shared/references/run-lifecycle.md` (`brief_revision`); route to it, don't re-decide it here.

## Nudges (surface only when they apply)

- **Stale brief.** If `preferences.md:updated_at` (fallback `created_at`) is older than ~3 months, gently suggest a refresh: "Your
  preferences are about <N> months old — want to update them? Just say so and I'll walk through it." (This
  mirrors the digest's brief-age footnote.)
- **Deeper company-board coverage (one time per absolute workspace).** Render this only when the newest
  lifecycle-authorized closed run
  is `first_page`, `pagination_metrics.deeper_coverage_nudge_eligible` is `true`,
  `unique_unseen_roles_first_pages` is zero, at least one listed healthy cursor-capable stream has trustworthy
  `has_more_at_stop:true`, the current config omits `search.max_new_postings_per_run` (resolved first-page
  coverage), and the absolute workspace has no registry marker. A saved finite or `"all"` setting suppresses
  the automatic nudge even if the latest run's first-page evidence is eligible. Explain that the last search
  found no unseen roles in its first pages while deeper results were available, then offer deeper company-board
  coverage. State that each additional board page and full-posting read adds a metered call; do not expose
  cursor strings or turn the home into a page browser.

  As soon as the eligible nudge renders—and before awaiting a reply—atomically merge exactly one marker for
  the absolute workspace per `internals.md`, with `outcome: deferred`. Preserve every unknown registry key.
  This provisional marker makes display durable even if the interaction ends without an answer; never append
  or create a second marker for the same workspace.

  If the user asks to enable depth, follow **Review-depth changes**—including the exact first-page baseline,
  canonical schedule comparison, unknown additions, and confirmation—before running or writing config. Keep
  the existing marker `deferred` until confirmed enablement takes effect, then atomically change only that
  same marker's outcome to `enabled`. A no changes only its outcome to `declined`; preserve its `workspace`
  and original `shown_at`. Later, another action, or no reply leaves it `deferred`. A present marker suppresses
  every later automatic nudge for that workspace, including after an unanswered display, decline, or deferral;
  the user can still ask for depth later. Scheduled runs write eligibility evidence only and never this
  shown/outcome marker.
- **Query health — repeatedly thin retrieval (at most once per unchanged search shape).** Consider this only
  when the three comparable records gathered above exist and, for a source with `Q` enabled queries, each of
  those runs returned a source total of `0` through `Q - 1`; a total of `Q` or more in any of the three
  settles it — say nothing. Only the raw `results_returned` sum activates this. New, deduplicated, selected,
  detail-read, and relevance counts describe fit quality rather than retrieval health, and never trigger it.

  That condition earns an assessment, not a nudge. Weigh how common the role family plausibly is, how tight
  the requested location is, and how narrow the saved freshness window is: a rare specialty, a deliberately
  tight search, or plausible market scarcity fully explains the volume, and saying nothing is then the right
  outcome. Opening the home view is never a retune — the saved queries stay byte-for-byte untouched unless
  the user accepts a proposal.

  When it is worth saying, say it once for every qualifying source together: one evidence sentence naming the
  affected source or sources and the raw volume observed — one evidence bullet instead when a long source
  list would be hard to scan — then one question offering to propose broader role families. Keep the causal
  claim honest with *may*: market supply and the active filters remain plausible explanations.

  As soon as that nudge renders—and before awaiting a reply—atomically merge the single `query_health_nudge`
  marker per `internals.md`, storing the current shape, the affected sources, and `outcome: shown`. Preserve
  every unknown registry key. Change that outcome to `dismissed` once the user declines, and to `accepted`
  only once the proposed change has actually been applied — a proposal the user accepts and then abandons at
  the scoped confirmation below changed nothing, so the marker stays at its prior value and suppresses
  exactly the same. While the stored shape matches the current saved shape, show no further query-health
  nudge; a confirmed query, location, limit, freshness, or source change makes a new shape, which becomes
  assessable again after three new comparable runs of its own.

  Even after the user says yes, nothing is written on that alone: route the proposed retune through the
  **Retrieval-changing** row of **Applying your feedback** — the agent-data usage preview and the scoped
  confirmation a persistent change requires — before writing `config.yaml`.
- **Last run blocked/failed.** If the newest authorized closed run's `run_health` is `blocked`, select the
  rendering by the record's internal `E-*`/class but render only the structured **cause · preserved work ·
  next step · exact fix** — the home view is user-facing, so the raw `E-*` code never appears
  (`../../../shared/references/errors.md` → Internal classification vs. user rendering). Examples: `E-QUOTA` →
  restore access at https://agent-data.motie.dev/settings/billing, existing matches unaffected (discuss usage
  levers only if the user asks); `E-NO-AUTH` → re-export the key; `E-SERVICE-DOWN` → temporary. For a
  **temporary** failure (service down, upstream stretch, incomplete pagination) render the retry clause for
  the **derived Schedule health** state gathered above (`errors.md` → Retry language by verified schedule
  state): a verified schedule names its next run, an `absent` schedule offers a **manual** retry ("run a
  search now"), and an `unverified`/`session_only`/`registration_drift` schedule says it can't be relied on
  and names the repair path — never promise an automatic scheduled retry when none is verified. For the
  bounded model-binding or version-1 migration classes, render only the observed cause, preserved/restored
  work, next step, and exact conversational fix; never show the internal class or invent a raw migration code.
  Recovery is conversational — the quick actions perform the safe fix in chat, never a required file edit.
  Don't bury a failure inside an otherwise-cheery home.

## Coming soon (Plan C)

Resume actions — **compare** your resume against a match and **tailor** it (truthfully, never inventing
experience) — are **planned (Plan C, not yet scheduled)**. Mention them if the user asks what's next, but defer; they
aren't wired yet.
