# Scheduling & consent

How the Job Search Agent schedules its recurring run with Claude Code's native `/loop`, and where the
"never write the user's machine" line is drawn.

## Mechanism: native `/loop` (the only one the agent sets up)

Job Search OS schedules with Claude Code's native **`/loop`**: `/loop <interval> /job-search-os:job-search-run`
(plugin installs — plugin skills are only invocable namespaced; loose-skill installs drop the prefix) re-runs the
search on an interval inside an **open Claude session**. There is no privileged write — nothing is added to
the user's crontab or launchd, and nothing persists on their machine. The tradeoff: it runs only while a
Claude session is open. (`/schedule` — cloud routines — is intentionally not used: a cloud agent wouldn't
have the local workspace or `agent-data` auth.)

| Step | How | Notes |
|------|-----|-------|
| Compose the line | interval table in `internals.md` → Scheduling setup | hourly→`1h`, every-2-hours→`2h`, every-6-hours→`6h`, daily→`24h`, weekly→`168h`. Namespaced target (`/job-search-os:job-search-run`) when running as a plugin (this skill appears as `job-search-os:…` in the skill list); bare for loose skills. |
| Start it (on yes) | run the composed `/loop …` line | Runs in the current session; stops when the session ends. |
| Record it | set the scheduling marker (`internals.md` → Registry write rules) | Records `mechanism: loop` so the home view shows the schedule and you don't re-ask. |
| Turn it off | stop the loop, then clear the scheduling marker | The marker reads `installed: false` afterwards. |

`schedule.time` in `config.yaml` is informational under `/loop` (the loop fires on an interval from when it's
started, not at a wall-clock time). Always also show the user the verbatim `/loop` recipe from `internals.md`
so they can start or restart it themselves.

## Consent: where the line is

The stance is instruction-level, carried by every skill in this system: **never initiate a crontab or
launchd install yourself** — scheduling is `/loop`, which needs no write to the machine. If the user
explicitly asks for cron or launchd, it's their machine and their call: show the `/loop` recipe first so
they know the no-install option, then help with what they asked for. Reads (`crontab -l`,
`launchctl list`), removals, and mere mentions of these words were never restricted.

There is no enforcement hook behind this stance — it is a design rule, not a technical control. A user
typing `crontab -e` in their own terminal was always, and remains, entirely their own business.
