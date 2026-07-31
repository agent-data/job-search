---
name: job-search
description: Set up, check on, and steer the user's job search — the front door and home view. Use when they want to start or set up a job search, see their status, matches, latest digest, or pipeline, change what they are looking for, or start, change, or stop the search that runs on a schedule — set up job search, start my job search, I am looking for a new job, check my job search, show me my matches, what is new in my pipeline, keep this running daily — or /job-search. A first run reaches live matches fast: one question, real postings, then the offer to keep it running on its own. (For a pull with nobody watching, use job-search-run; for configuring or troubleshooting the agent itself, use job-search-agent.)
---

# job-search

The front door: first-time setup, the home view after that, and where the user steers their search
from by talking to you. The work belongs to the other skills — `job-search-run` pulls and judges
postings, `job-preference-interview` writes the brief, `evaluate-job-fit` judges one posting. Two
references carry the mechanics, named relative to this file, two steps below `<plugin-root>`:

- `../../shared/references/runbook.md` — the workspace, what each file in it holds, the run contract.
- `../../shared/references/agent-data.md` — the CLI, what a call costs, what to say before spending one.

## Your first message on a first run

Your first output is a message to the user, before any other work. It says what this sets up and
what they end up with, in this order: a private folder for their search, a short brief of what they
want, and live postings judged against it. Two sentences. Every noun in it is something the user
owns or can see; name each idea in the plain words a person would use for it, the first time they
meet it.

## How to communicate

These ten rules govern how you say things, in every mode below.

1. Define each idea in plain words the first time the user meets it — the brief, a job source, the
   free monthly calls, the recurring job, the digest — in the sentence or offer that first uses it.
2. Before metered work, say what it opens with, in your own words, per agent-data.md's cost recipe.
3. Ask one question at a time, and only when the answer changes what you do; a closed choice goes
   through your host's question interface (numbered prose without one), open questions stay prose.
4. Show matches as message text in your reply — title, company, location, the reasoning line, the
   link — as rendered markdown, with the digest's path as a closing detail.
5. Say what a posting states and name what it leaves unstated; the judgment arrives carrying both.
6. Use the user's own words for their field, their seniority, and where they want to work.
7. Every noun in a reply is something the user owns or can see: their preferences, a posting, a
   search, the digest, the schedule, the folder these live in. The rest is yours to work with.
8. Narrate events — what you did and what came back. A step that produced nothing to report passes
   in silence.
9. Write state in the present tense: what is set up, what runs, what the last run found.
10. Keep each message to a sentence or two plus whatever document you render; go longer on request.

## Route

Find the workspace with the runbook's discovery step, silently, and go where it points.

- No `config.yaml` there yet → **First run**, below.
- A workspace already set up → **Home**, below.
- The registry file is there and JSON parsing fails on it → stop there, say the file at that path
  cannot be read, and offer to rewrite it around the workspace you can see; on a yes, write it fresh
  with that workspace as `active_workspace`.

Other intents leave: what they want in a job → `job-preference-interview`, a pasted posting →
`evaluate-job-fit`, an unwatched pull → `job-search-run`, the agent itself → `job-search-agent`.

## First run

1. Open with your first message above.
2. Run `agent-data whoami` — the whole preflight, local and free. On `api_key_set: false`, say the
   key is missing, give agent-data.md's `agent-data init` line, and go on once it reports true.
3. Build the workspace where discovery pointed: copy `<plugin-root>/templates/config.example.yaml` to
   `config.yaml` and `<plugin-root>/templates/workspace.gitignore` to `.gitignore`, create an empty
   `jobs.jsonl`, and make `runs/` and `reports/`. A file already there stays as it is. Say in one
   line that this folder is theirs and private.
4. Write this machine's zone into `schedule.timezone` in that `config.yaml`: `readlink /etc/localtime`
   prints it after `zoneinfo/`, and a schedule fires on the machine's own clock.
5. Get the brief. Hand `job-preference-interview` a request for a quick sketch: it asks its one
   question and writes `preferences.md`. When the request already says what they want, hand those
   words over as that question's answer and ask for the brief drafted from them — whatever they
   name, in whatever detail. Role and where they want to work is usually all a first request
   carries; pay, hours and dealbreakers wait for the deeper pass they can take once matches are on
   screen.
6. Derive two or three searches from the brief into `queries[]` in `config.yaml`, each with a short
   `id` from its own terms and the template's field set: keywords are the role and domain terms a job
   board matches, location is the geography the brief names, and remote rides in the keywords per
   agent-data.md's LinkedIn row. Say which searches you derived and that they change on request.
7. Give the user the cost sentence rule 2 asks for, then invoke `job-search-run` on the workspace.
8. Render what came back: the strong matches, then the moderate ones, each with its reasoning line
   and its link, plus any confirm note the digest carries. Where the run judged postings and few or
   none of them fit, say what it searched and name the one change most likely to help.
9. Then offer the recurring job below, and land them on the home view once that is settled.

## The recurring job

A search that runs on its own is the point of the whole thing, so offer it while the first matches
are still on screen, and say plainly what it is: this same search, running by itself on a schedule,
leaving a digest of whatever is new. Say what that cadence costs to keep: the calls one run opens
with, that many again every day or week it fires, against the free monthly calls agent-data.md
counts — the user hears the monthly total before a yes is recorded. Ask once, with daily as the
usual cadence; their yes starts the install, as does a request that already asks for it.

1. Write today's date into `schedule.consented` in `config.yaml`, with `schedule.frequency` and
   `schedule.time` holding the cadence they picked. That date is the standing yes a scheduled,
   headless, or subagent run proceeds on.
2. `<plugin-root>/shared/scripts/mechanics/schedule-line.sh <frequency> [HH:MM]` prints the cron time
   expression for that cadence. Wrap it in whatever your host schedules with — cron, launchd, or the
   host's own recurring-job command — running `job-search-run` against this workspace the way the
   runbook's unattended section shows. As you install it, show the user that line and where it lives;
   this changes their machine.
3. **Run the canary now**: a job that has been installed and has never run is unproven. It spends,
   and in a session that has not searched yet it is the first metered call, so give the cost sentence
   rule 2 asks for first. Then fire the job through the path the scheduler will use — that invocation
   and that environment, rather than this session — and stay with it until it lands.
4. The canary passes when it leaves a run record whose `trigger` is `scheduled` and whose close is
   healthy — `close_state: complete` with `run_health: healthy`. On that record and not before,
   write the job into the registry the runbook names, `installed` and `verified` both true, which is
   where the home view reads the schedule from; setup is finished there, and the user hears that the
   schedule is live and when it next runs. Every other ending is the same ending — the canary failed,
   or you could not fire it at all — and it goes the same way: remove the job the way the turn-off
   recipe below does, so nothing you installed is left to fire unproven, leave the registry unwritten
   and `schedule.consented` as it is, and say what stopped the canary and what the next step is.

To turn it off, undo the install the way it was made — that cron line deleted, that launchd job
unloaded and its file removed, or the host's own removal command — then clear the registry's
`scheduling` marker (`installed: false` or the object dropped) and say what was removed. A user who
leaves it off hears that it starts whenever they ask, and a search on demand is one sentence away.

## Home

Read, all of it local: `config.yaml` (enabled queries, `search.sources`, `schedule.frequency`,
`schedule.consented`), the registry the runbook names, for the schedule state, the `updated_at` line
of `preferences.md` (`created_at` where that is the only one), the newest `runs/<run_id>.json` and
the digest it points at, and `jobs.jsonl` folded to one entry per `source` + `source_id` with the
last line winning, counting a line that names another posting in `same_role_as` as that one role.
Then render the card:

```
Job search — <workspace path>
Brief: updated <date>  ·  Sources: LinkedIn + Ashby  ·  Schedule: daily  ·  Last run: healthy

Latest digest — <date>
  <the digest's counts line, as it is written there>

Pipeline
  new <n> · interested <n> · applied <n> · rejected <n> · archived <n>   (<k> to confirm)

What next? Just tell me:
  • run a search now            • add or edit a query
  • change how often it runs    • update your preferences
  • show the latest digest      • show your preferences brief
```

Sources are the ones `search.sources` lists, in the words a person uses for them; the schedule reads
as its cadence while `schedule.consented` holds a date and the registry's `scheduling` carries
`installed` and `verified` both true, and off otherwise — an object missing either one is an install
no canary proved. Last run is the newest record's `run_health`. A record whose `close_state` is
`blocked` or `interrupted` earns a line under the card: what stopped that run, which its record and
digest name, and the one thing that gets it going again. Before the first run, offer that search in
place of the digest and pipeline lines. A brief older than 30 days, where runs have happened since,
earns one offer under the card to refresh it through `job-preference-interview`.

## When the user reacts

| What they say | Where it lands |
|---|---|
| A preference that holds across postings — only fully-remote, nothing under a pay floor | `preferences.md`, through `job-preference-interview`, which refreshes `updated_at`. Confirm in one line; a run in flight judges what is left under the new brief. |
| Something about one posting — already applied there, not this company | that posting's line in `jobs.jsonl`: append a `status_changed` event carrying its new `status`. |
| A reaction that reads two ways — the location is wrong, too junior | one short question, asked where the two readings lead to different actions, and your own best reading where they land the same. |
| A change to what gets searched — add a source, widen the location, only the last day | a `queries[]` or `search.sources` edit in `config.yaml`, with the new cost stated first per rule 2. A one-off ask runs once and leaves the file as it is. Every config edit here is yours to make, comments and shape preserved. |
