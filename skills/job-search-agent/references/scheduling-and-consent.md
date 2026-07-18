# Scheduling & consent

How the Job Search Agent schedules its recurring run, why the default is an **unattended** schedule that
fires with no session open, and where the "never write the user's machine **without consent**" line is drawn.

## Mechanism: an unattended schedule on the host's own scheduler

**Advocate an unattended schedule as the default.** Set the recurring run up so it keeps firing with **no
interactive session open**, using the host's or the OS's own scheduler that survives session-close (e.g.
launchd, cron, or the host's native unattended scheduler). Where that scheduler can **re-fire a run missed
while the machine was asleep**, prefer it. The agent composes the schedule for its own host — there is no
per-host recipe to look up here.

Why unattended is the default: a search is only useful if it runs when the user isn't watching. An
in-session loop stops the instant the session closes, so the overnight and next-morning runs — the ones
that matter most — silently never happen. The re-weighting is **reliability > installs-nothing**: the
install-nothing convenience of a session loop yields to a schedule that actually fires. It is **never**
silent > consented — the unattended schedule is a real machine change, and (see Consent below) it is still
shown first and written only on an explicit yes.

**Required conditions (state these when you set it up, host-neutral).** *Set up the run so it can write the
workspace and call agent-data.* Those are the only two things the unattended run must be able to do; the
canary below is what proves it can. Nothing host-specific beyond that — no harness troubleshooting recipe.

**Fallback — an in-session loop.** When the host has no unattended scheduler, or the user declines the
machine change, offer an **in-session loop** (a recurring run driven from inside an open interactive
session) as a named fallback. Tell the user plainly that it runs only while a session is open — so a quiet
overnight is expected, and closing the session stops it. It installs nothing, but it is the fallback, not
the recommendation.

**One disqualifier on either path:** cloud schedulers do not qualify — a cloud runner can't see the local
`~/.job-search` workspace or the local agent-data auth, so a run there reaches neither the user's data nor
their credentials and produces nothing. This is the test any candidate scheduler must pass.

## Eligibility gates — a scheduler qualifies only when it passes every one

Advocacy is not enough: before the agent binds a recurring run to any mechanism, that mechanism must clear
**six gates**, and a single failure disqualifies it for a *verified* schedule. A candidate is eligible only
when it is:

- **unattended** — it fires with no interactive session open;
- **canary-testable** — a real run can be triggered through its registered invocation, so the canary below
  can actually prove it;
- **exact-primary-model-preserving** — it preserves the exact primary model, never silently substituting a
  host default for the exact recurring primary-model binding;
- **local-reaching** — it reaches the local workspace, agent-data auth, and network (the cloud disqualifier
  above is exactly this gate failing);
- **inspectable** — its registration can be read back and compared to what was staged;
- **reversible** — it can be disabled and removed.

**Selection is native-first, then OS, then nothing verified.** Probe the host's **native** mechanism first and
choose it only when every gate passes; otherwise choose an **OS** mechanism (`cron`/`launchd`) that passes
every gate; if neither qualifies, create **no verified recurring job** — the in-session loop is offered only as
the labeled **session-only** fallback. The full gate table, the selection order, and the registry state
machine (disabled staging → a green canary is the only thing that sets `installed` and `verified`) are
single-homed in `../../../shared/references/internals.md` → Scheduling setup and the Registry; this file does
not restate the field schema.

**An existing job the agent did not stage is UNOWNED.** Inspect it first and compare it to what you would
stage; if it does not match, do **not** silently clobber it — surface the drift and ask to adopt it (reuse it)
or replace it (remove, then re-stage). Only a green canary through a job the agent controls verifies the
schedule and records the marker.

## The handoff: one decision, one confirmation

The recurring-schedule handoff is **one useful decision, not a form** — a single closed choice
(`../../../shared/references/voice.md` → Asking questions), offered **after activation** (the first live
results are on screen) or **when the user explicitly asks to schedule**. Check the scheduling marker first so a
verified or session-only schedule is never re-offered. The three options are **Daily — recommended** ·
**Different schedule** · **Not now**.

- **Not now** leaves the search unscheduled — no machine change, no marker — and **does not dump the
  recurring/one-off recipe blocks**; a wall of host commands the user did not ask for is noise. Say plainly
  that scheduling can be turned on later just by asking and a one-off search is always a request away, and ask
  no cadence question (there is nothing to schedule).
- **Daily — recommended** fixes the cadence at `daily`. **Different schedule** asks exactly one cadence
  question (hourly · every 6 hours · weekly — daily is already the recommended option; a typed "every couple
  of hours" maps to the nearest `schedule.frequency` value).

On a scheduled choice, show **one scoped confirmation** — never a chain of separate model, migration,
frequency, and canary prompts. That single confirmation contains, all at once:

- the **cadence**;
- the **exact machine change** and the **removal path** (how the user turns it off later);
- the exact **primary and detail model bindings stated as facts** — "primary: `<exact id>`; detail:
  `<exact id>`", never "choose a model": the primary is the exact creating-session model with origin
  `session_inheritance`, or an explicit exact available model with origin `user_override`; the detail model is
  the exact configured `search.detail_model`;
- the **version-1 → version-2 migration** when the workspace needs one (folded in per
  `../../../shared/references/internals.md` → Version-1 staged migration, never a separate prompt);
- the **agent-data call preview** (the `schedule_enable_with_canary` row — the current/proposed first-page
  baseline, the saved-cadence comparison, and the uncertain continuation/detail additions); and
- **one canary**.

The user's single yes covers that exact machine change and **exactly one** real scheduled-path canary — and
nothing more. It is **not** standing authority for a second metered canary attempt (see the failure loop
below). Before the yes, write neither config nor scheduler state.

## Prove it works before recording the schedule — the canary

The canary is **mandatory before recording the schedule**: never tell the user a job is scheduled until its
exact unattended invocation has been **observed to succeed end to end**. A wrong self-configuration is
caught now, not discovered the next day. Two layers, both required:

1. **Registration (disabled) + inspection.** Register the job **disabled**, then confirm it appears in the
   host's or OS's own scheduler job list and **inspect the registration**, comparing it to exactly what you
   staged. Staging never writes the `installed`/`verified` marker. This proves it *exists* and is *ours* — a
   drifted or foreign registration is surfaced, not clobbered.
2. **Execution canary.** Fire **one real run through the exact scheduled invocation**, then confirm the
   artifacts it leaves behind by applying `../../../shared/references/run-lifecycle.md` → **Artifact
   authority for every reader**: invoke `lifecycle-fold.sh` for the candidate's exact run_id, require
   `closed=true`, matching record phase/close state, and `can_complete=true`; then require `run_health` other
   than `blocked`, evidence that **agent-data was reached**, and the exact fold-derived digest **and its
   workspace write**. An open ledger or intended-complete pre-close file never verifies a canary. This proves
   it *works*. Default depth is a **real run** — the truest proof, and the user gets a live digest out of it
   (the quota cost is one run the first scheduled fire would spend anyway). The scheduled prompt states the run
   is **headless** and must read `search.detail_model` from config and use that **exact model for every
   posting-detail judgment**; the canary also confirms the exact **primary model was preserved** — a scheduler
   that silently swaps the exact recurring primary model for a host default is **not** primary-model-preserving
   in practice (the run may still complete healthy), so it **fails the canary** and is rejected, never
   recorded.

**Same context — the non-negotiable part.** The canary must fire through the *real* unattended path:
non-interactive, no TTY, the **scheduled command's own permissions and environment — not this session's.**
This interactive session already holds workspace-write and agent-data permission, so running the canary
here would pass while the real scheduled run fails, proving nothing. Route it through the actual scheduled
invocation or it does not count.

**If the canary fails, debug it yourself — and never claim success.** A failed canary **removes or disables**
the newly created job, leaves `verified` **false** (and writes no `installed` marker), preserves the exact
failure internally (the bounded `E-SCHEDULE-CANARY` class — a blocked canary run record may carry it, but the
raw code is **never** a user-facing surface, per `../../../shared/references/errors.md`), and makes **no
success claim** — no "all set." There is no host troubleshooting reference to consult: diagnose the specific
gap from the artifacts (workspace write denied · agent-data unreachable · subagents refused · exact model not
preserved), **propose the exact host-appropriate fix, show it, apply it on the user's yes, and re-fire.** The
retry consent depends on **where** it failed:

- A **pre-meter** failure — it blocked before any metered agent-data call (`metered_calls` 0) — spent **none**
  of the approved single-canary metered budget, so it **does not consume** the metered-retry consent: re-fire
  the one canary after a **free** fix **without** a fresh cost confirmation. (A new *privileged machine change*
  to close the gap still needs its own yes — that is the consent line below, not the metered one.)
- An **after-meter** failure — it blocked after at least one metered call (`metered_calls` ≥ 1) — **consumed**
  the approved attempt, so any further canary needs a **fresh** calls-first preview
  (`../../../shared/references/internals.md` → Agent-data usage decisions, `metered_canary_retry_or_repair`)
  and a **fresh** scoped yes.

Loop until green. If it cannot be made to work, name the exact gap in the same named-error style the rest of
the system uses and **stop — do not claim it is scheduled.** Only after a **green canary** do you set the
scheduling marker (`installed` and `verified` together, with the exact `canary_run_id` and primary-model
binding — schema in `../../../shared/references/internals.md`).

### Repairing an expired or refused exact model

Expiry or exact-dispatch refusal first leaves the recurring job **disabled and unverified**. Then follow the
single source of truth in `../../../shared/references/internals.md` → **Exact-model repair**, including its
`exact-model-repair-candidate`, `exact-model-repair-confirmation`, and
`exact-model-repair-transaction` marked contracts. Do not silently substitute a host default or use a model
prefix as an identifier.

Show both exact primary and detail before/after values, including an unchanged valid slot; show the config,
binding, scheduler, machine-change/removal, and exact rollback effects. Add the canonical calls-first preview
for one real scheduled-path repair canary. Then ask **one scoped confirmation** for that complete proposal
and exactly one canary—no separate model, config, scheduler, or canary confirmations. Model identity is
neutral; the real canary is the metered action.

Stage an approved candidate while the job stays disabled and unverified. On any partial setup or canary
failure, restore the exact transaction snapshot automatically and leave no proposed model active. A retry
needs fresh calls-first context and a fresh scoped confirmation. **Only a green real scheduled-path canary**
commits the repair, enables the job, and marks the registry verified. Render either the initial binding
failure or the later setup/activation/canary phase through `../../../shared/references/errors.md` →
`model-repair-rendering`; normal chat and digests never show the raw internal failure token.

## Schedule health (local, unmetered)

Once a schedule is recorded, the home view keeps **deriving its ongoing health** from local evidence. This is
a **local, unmetered** read — never a scheduler trigger, a canary, or a metered agent-data call. It compares
three sources: the local registry marker, the scheduler's **own local registration** (read back and compared
to what was recorded), and the **latest scheduled-attributable run**. The **canary proves setup but is not
counted as an ordinary scheduled fire**, so a freshly verified schedule whose only run is its canary reads
healthy rather than missed. Using the configured cadence/time/timezone and a documented 30-minute post-fire
grace period, one missed expected fire reads **"not recently observed"** and two or more reads **"needs
attention."** The full eight-state precedence (registration drift · latest scheduled run blocked · overdue ·
not recently observed · verified/running · unverified · session-only · absent) and the timezone/DST-aware
missed-fire math are single-homed in `../../../shared/references/internals.md` → **Schedule health**, with the
run-record selection in `../../../shared/references/conventions.md` → Latest scheduled-attributable run. These
health checks stay **unmetered**; a **repair or retry canary** is the separately costed, separately consented
metered action described above, never a passive liveness read.

## Actions

The steps are the same whichever scheduler is active; the agent binds each to its own host. The one step
that differs is **Verify**: the **unattended schedule** must pass the config-time canary below (registration
in the scheduler's job list + a real run through the *actual scheduled invocation, not this session*), while
the **in-session-loop fallback** can satisfy neither canary layer — it registers in no scheduler job list and
its run *is* this session — so it is confirmed instead by observing its **first in-session fire** leave a
fresh run that passes `run-lifecycle.md` exact run_id + `lifecycle-fold.sh` + matching `closed=true`
authority before the marker is recorded.

| Step | How | Notes |
|------|-----|-------|
| Compose the cadence | from `schedule.frequency`, via `../../../shared/scripts/mechanics/schedule-line.sh <frequency> [HH:MM]` where a shell runtime exists (the prose fallback in `../../../shared/references/internals.md` → Scheduling setup composes the same line directly) | Host-neutral cron time expression; the host wraps it with its own command / launchd / interval translation. |
| Start it (on a scheduled choice) | offer the **one-decision handoff** (Daily — recommended / Different schedule / Not now — above), check the scheduling marker first so you never re-ask, then on a scheduled choice show the **one confirmation** and stage the unattended schedule disabled | Show the user the exact machine change **before** writing it (Consent below). **Not now** declines with no recipe dump. |
| Verify | **Unattended:** run the **canary** above — registration + one real scheduled run, proven from the authoritative closed artifacts. **In-session-loop fallback:** it can neither register nor run outside this session, so confirm its first fire through the same exact-run closed-ledger gate. | Mandatory gate either way: no authoritative proof, no marker. |
| Record it | set the scheduling marker (`../../../shared/references/internals.md` → Registry write rules) | Records the **active** mechanism so the home view shows the schedule and you don't re-ask. Only after Verify passed (a green canary, or the loop's observed first-fire run record). |
| Turn it off | stop the active schedule, then clear the scheduling marker (`../../../shared/references/internals.md` → Registry write rules) | The marker reads `installed: false` afterwards. |

`schedule.time` in `config.yaml` is honored when the active scheduler is **wall-clock-based** (an unattended
cron/launchd run fires at the named time) and ignored when it is **interval-only** (an in-session loop fires
on an interval from when it started, not at a wall-clock time). **On the recorded (scheduled) path**, compose
the **recurring-run and one-off-run recipe for the host** and show both to the user verbatim, so they can
re-run the search on demand and stop or restart the schedule themselves — but **not on a Not now decline**,
where a recipe dump the user didn't ask for is only noise.

## Consent: where the line is

The stance is instruction-level, carried by every skill in this system: the agent never initiates a
**silent or un-consented** privileged write. The unattended schedule is a real machine change, so the exact
change is **shown before it is written**, applied only on an explicit user yes, and stays user-removable —
never silent, never auto-installed. Advocating the unattended schedule re-weights the old install-nothing
preference toward reliability; it does **not** loosen this consent gate. Reads (`crontab -l`,
`launchctl list`), removals, and mere mentions of these words were never restricted.

If the user explicitly asks for cron or launchd, it's their machine and their call: help them set up what
they asked for, showing the exact line first and writing it on their yes. If they'd rather not change the
machine at all, the in-session loop is the no-install fallback — offer it so they know the option.

There is no enforcement hook behind this stance — it is a design rule, not a technical control. A user
typing `crontab -e` in their own terminal was always, and remains, entirely their own business.
