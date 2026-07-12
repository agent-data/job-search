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

## Prove it works before recording the schedule — the canary

The canary is **mandatory before recording the schedule**: never tell the user a job is scheduled until its
exact unattended invocation has been **observed to succeed end to end**. A wrong self-configuration is
caught now, not discovered the next day. Two layers, both required:

1. **Registration.** Confirm the schedule is actually registered — it appears in the host's or OS's own
   scheduler job list. This proves it *exists*.
2. **Execution canary.** Trigger **one real run through the exact scheduled invocation**, then confirm the
   artifacts it leaves behind: a fresh `runs/<id>.json` whose `run_health` is anything other than `blocked`,
   evidence that **agent-data was reached**, and evidence that the **workspace was written**. This proves it
   *works*. Default depth is a **real run** — the truest proof, and the user gets a live digest out of it
   (the quota cost is one run the first scheduled fire would spend anyway).

**Same context — the non-negotiable part.** The canary must fire through the *real* unattended path:
non-interactive, no TTY, the **scheduled command's own permissions and environment — not this session's.**
This interactive session already holds workspace-write and agent-data permission, so running the canary
here would pass while the real scheduled run fails, proving nothing. Route it through the actual scheduled
invocation or it does not count.

**If the canary fails, debug it yourself.** There is no host troubleshooting reference to consult — diagnose
the specific gap from the artifacts (workspace write denied · agent-data unreachable · subagents refused),
**propose the exact host-appropriate fix, show it, apply it on the user's yes, and re-run the canary.** Loop
until green. If it cannot be made to work, name the exact gap in the same named-error style the rest of the
system uses and **stop — do not claim it is scheduled.** No "all set." Only after a **green canary** do you
set the scheduling marker.

## Actions

The steps are the same whichever scheduler is active; the agent binds each to its own host.

| Step | How | Notes |
|------|-----|-------|
| Compose the cadence | from `schedule.frequency`, via `../../../shared/scripts/mechanics/schedule-line.sh <frequency> [HH:MM]` where a shell runtime exists (the prose fallback in `../../../shared/references/internals.md` → Scheduling setup composes the same line directly) | Host-neutral cron time expression; the host wraps it with its own command / launchd / interval translation. |
| Start it (on yes) | offer scheduling as a yes/no, check the scheduling marker first so you never re-ask, then start the unattended schedule on an affirmative answer | Show the user the exact machine change **before** writing it (Consent below). |
| Verify | run the **canary** above — registration + one real scheduled run, proven from the artifacts | Mandatory gate: no green canary, no marker. |
| Record it | set the scheduling marker (`../../../shared/references/internals.md` → Registry write rules) | Records the **active** mechanism so the home view shows the schedule and you don't re-ask. Only after a green canary. |
| Turn it off | stop the active schedule, then clear the scheduling marker (`../../../shared/references/internals.md` → Registry write rules) | The marker reads `installed: false` afterwards. |

`schedule.time` in `config.yaml` is honored when the active scheduler is **wall-clock-based** (an unattended
cron/launchd run fires at the named time) and ignored when it is **interval-only** (an in-session loop fires
on an interval from when it started, not at a wall-clock time). Always also compose the **recurring-run and
one-off-run recipe for the host** and show both to the user verbatim, so they can re-run the search on demand
and stop or restart the schedule themselves.

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
