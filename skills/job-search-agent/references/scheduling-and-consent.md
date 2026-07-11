# Scheduling & consent

How the Job Search Agent schedules its recurring run, and where the "never write the user's machine
**without consent**" line is drawn.

## Mechanism: the host's scheduler — read your platform's adapter

The MECHANISM lives in your platform's adapter → Scheduling; the ACTIONS below are the same on every
host. The model is **two-tier** — use whichever applies to the active host:

- **Tier 1 — native local scheduler (preferred).** Where the host has one (see your adapter →
  Scheduling), use it: it runs where it can see the local `~/.job-search` workspace and the local
  agent-data auth, and **installs nothing on the user's machine** (no crontab, no launchd, no privileged
  write). The exact recipe lives in the adapter — do not spell it here.
- **Tier 2 — no native local scheduler.** A **consent-gated** machine-level cron/launchd schedule is the
  sanctioned fallback — written **only on an explicit user yes, with the exact line shown before it is
  written**, never silent, never auto-installed, and user-removable.
- **Cloud schedulers do not qualify** — a cloud agent can't see the local workspace or the `agent-data`
  auth, so a run there reaches neither the user's data nor their credentials and produces nothing. This is
  the test any candidate scheduler must pass on either tier.

A given host sits on **whichever tier its adapter names** — a Tier-1-only host (its adapter names a native
local scheduler) never reaches for the Tier-2 fallback. Read the adapter to learn which applies.

| Step | How | Notes |
|------|-----|-------|
| Compose the line | from `schedule.frequency` (your adapter → Run recipe carries the cadence→interval/cron mapping) | The interval table and the verbatim recipe live in the adapter, not here. |
| Start it (on yes) | start the schedule on the active mechanism | Offer scheduling as a yes/no; check the scheduling marker first so you never re-ask. |
| Record it | set the scheduling marker (`../../../shared/references/internals.md` → Registry write rules) | Records the **active** mechanism (your adapter → Scheduling gives its value), so the home view shows the schedule and you don't re-ask. |
| Turn it off | stop the active schedule, then clear the scheduling marker | The adapter's Scheduling section gives the teardown for whichever tier is active; the marker reads `installed: false` afterwards. |

`schedule.time` in `config.yaml` is honored when the active scheduler is **wall-clock-based** (a Tier-2
cron/launchd run fires at the named time) and ignored when the scheduler is **interval-only** (a Tier-1
in-session loop fires on an interval from when it started, not at a wall-clock time) — see your adapter →
Scheduling for which the active mechanism is. Always also show the user the verbatim recurring-run and
one-off-run recipe **from your adapter → Run recipe** — copy them exactly as written; do not reconstruct
those tokens here.

## Consent: where the line is

The stance is instruction-level, carried by every skill in this system. A native local scheduler
**installs nothing** — prefer it where the adapter names one. A machine-level cron/launchd line is written
**only on an explicit user yes, with the exact line shown first**, never silent, never auto-installed, and
user-removable — that is the Tier-2 sanctioned fallback. Reads (`crontab -l`, `launchctl list`), removals,
and mere mentions of these words were never restricted.

If the user explicitly asks for cron or launchd, it's their machine and their call: where a native local
scheduler exists, offer it first so they know the no-install option, then help with what they asked for;
where none exists, the consent-gated machine schedule is the fallback — show the exact line first, then
write it on their yes.

There is no enforcement hook behind this stance — it is a design rule, not a technical control. A user
typing `crontab -e` in their own terminal was always, and remains, entirely their own business.
