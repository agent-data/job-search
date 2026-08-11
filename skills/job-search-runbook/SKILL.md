---
name: job-search-runbook
description: "Not user-facing; job-search takes user questions. Mechanics the job-search skills read before a run: the workspace-discovery and validate-workspace scripts, the file table, how a run opens and closes."
---

# job-search-runbook — workspace, run contract, scratch

The mechanics every flow needs: where the user's workspace is, what each file in it holds, how one
run opens and closes, and what stays off disk.

## Find the workspace

Every path below that names a file in the user's workspace is relative to the `workspace` this step
prints. The few that name a file inside the plugin instead say so where they are written. Run the
plugin's `skills/job-search-runbook/scripts/workspace-discovery.sh`.

It prints three `key=value` lines on stdout:

```
workspace=/Users/dana/job-search
source=legacy
first_run=false
```

It writes one more line to stderr, naming the registry path and saying what it found there, so a
terminal or a tool result that merges the two streams shows four lines. That line says whether there
is a file at that path at all — or that it could not tell — and whether a non-empty
`active_workspace` string came out of it. Read it together with the parse-check rule at the end of
this section.

`first_run=true` means that path has no `config.yaml` yet and setup creates it. `source=legacy` means
the workspace sits at the older visible path: keep using it, and record it in the registry as
`active_workspace` so later runs find it. An existing `config.yaml`, `preferences.md`, or `jobs.jsonl`
stays as it is — adopting a workspace adds only the missing `runs/` and `reports/` directories.

The registry file — the one to read here and to write for adoption or scheduling — is
`$JOBSEARCH_OS_REGISTRY` when set, otherwise
`${XDG_CONFIG_HOME:-${JOBSEARCH_OS_HOME:-$HOME}/.config}/job-search/config.json`.

Where no shell runs, read that file and apply the same order yourself. In the rules below, `$H` is
`$JOBSEARCH_OS_HOME` when set and `$HOME` otherwise (tests and evals set it to move the home base).
First match decides:

1. The registry parses as JSON and holds a non-empty `active_workspace` — use it and stop, even with
   no `config.yaml` there (that is a first run); falling through could move the user elsewhere.
2. `$H/.job-search/config.yaml` exists — workspace `$H/.job-search`.
3. `$H/job-search/config.yaml` exists — workspace `$H/job-search`.
4. Neither exists — first run, workspace `$H/.job-search`, which setup creates.

A registry file that exists but does not parse as JSON stops the run: report that the file at that
path cannot be read, rather than picking a workspace it might not name. The script reads the file
with `grep`, so its stderr line tells you whether there is a file at that path but never whether
that file is JSON — parse-check it yourself. A registry the script could not look at stops the run
the same way: its line says a directory on the way to that path cannot be searched, so nothing there
was read and no file there was ruled out, and the workspace on stdout came from the rules below
rather than from the registry.

## What each file holds

| File | Written by | Read by |
|---|---|---|
| `config.yaml` — queries, sources, schedule | setup, then the user by hand | every run, the home view |
| `preferences.md` — the brief, in prose | the preference interview | every run, every fit judgment |
| `jobs.jsonl` — append-only event log, one JSON object per line. A run writes a `call` event for each agent-data request and `surfaced`, `queued`, `detail` and `evaluated` events about postings. A posting has several lines, all carrying the same `source` and `source_id`, and its current state is its last `evaluated` line. | every run | the home view, duplicate checks |
| `runs/<run_id>.json` — one record per run; `<run_id>` is the run's UTC start time with dashes for the colons, like `2026-07-30T15-04-02Z`, so it works as a filename | `skills/job-search-runbook/scripts/close-run.sh` | the home view, the agent skill |
| `runs/.started-<run_id>` — empty marker: this run is open | `skills/job-search-runbook/scripts/open-run.sh`, deleted by `skills/job-search-runbook/scripts/clear-run.sh` | the next run |
| `reports/<date>-digest.md` — the digest the user reads | a run at close | the user, the home view |
| `.gitignore` — copied from the plugin's `skills/job-search/templates/workspace.gitignore`; denies everything but itself | setup | git |
| `~/.config/job-search/config.json` — the registry, which sits outside the workspace: `active_workspace`, plus `scheduling` holding the booleans `installed` and `verified` — both true only after a canary proved the job — and the strings `mechanism` (cron, launchd, or the host's own) and `scheduler_id` | setup, schedule changes | discovery, the home view |

## One run, start to close

1. **Look for a leftover marker** — `ls <workspace>/runs/.started-* 2>/dev/null`. A marker there
   belongs to a run that stopped before it could close. Say that the last run did not finish,
   delete the marker, and go on with this run.
2. **Open the run** — run the plugin's `skills/job-search-runbook/scripts/open-run.sh <workspace>`.
   It prints `run_id`, `started_at` and `brief_revision` on stdout, in that order; carry all three
   through the run. Exit 1 means the run is open — the marker is on disk and those three lines are
   printed — and something is wrong that this run cannot fix: read stdout after the three lines for
   the findings about the workspace files, and stderr for the case where the brief's revision could
   not be taken. Report whichever you got in plain language and close the run `blocked`. Exit 2
   means the run did not open and nothing was written, and stderr says which of four things
   happened: there is no such workspace; there is no `config.yaml`, which is the one that means
   setup has not run; `runs/` could not be made or the marker could not be written into it; or this
   `run_id` is already taken because another run opened in the same second. That marker belongs to
   the run that just opened, not to a run that stopped — leave it alone, do not go back to step 1
   and delete it, and run `skills/job-search-runbook/scripts/open-run.sh` again a second later.
3. **Do the run's work**, recording events as you go.
4. **Close, in this order.** First
   `skills/job-search-runbook/scripts/close-run.sh <workspace> <run_id> --trigger … --close-state …`,
   with `--brief-revision` from step 2, `--sources` and `--queries` from the run, and
   `--scheduler-id` when a scheduler started it. It writes `runs/<run_id>.json`, works out
   `run_health` and prints it, and refuses a `complete` close while any posting is still unjudged,
   saying how many. Then the digest, which the run skill defines. Then
   `skills/job-search-runbook/scripts/clear-run.sh <workspace> <run_id>`, which deletes the marker
   and the scratch directory. Then
   `skills/job-search-runbook/scripts/validate-workspace.sh <workspace> --post-close <run_id>`,
   fixing whatever it prints on stdout. A close with nothing wrong prints nothing there and writes
   one line to stderr — `checked <workspace> and run <run_id> — no broken rule found` — which is
   the answer, not a finding to act on.

The digest is written between the record and the clearing because it carries `run_health` off the
record and may still need the responses in the scratch directory.

`trigger`, `scheduler_id` and `close_state` are the only values in the record you decide; the other
three you pass come from step 2 and the run. Every count and both timestamps come from `jobs.jsonl`
and the clock.

A run that has to stop early closes the same way: `close_state` is `blocked` when you can name what
stopped it, and `interrupted` when it ends unfinished and its work cannot be reconstructed.

## Running it unattended

A scheduler starts a run the way a person does — on Claude Code, `claude -p /job-search:job-search-run`
(the plugin namespace is part of that target), with `--permission-mode acceptEdits` and
`--allowedTools Bash,Read,Write,Edit,Glob,Grep,Skill,Task` so the run can search and write its own
workspace. A cron or launchd process has no login session, so the job's environment carries a token
from `claude setup-token` as `CLAUDE_CODE_OAUTH_TOKEN`. Another host takes its own headless flags,
in the same shape: this pack's run skill, permission to write the workspace, credentials in the job.

## Scratch

A run's own working files go in `runs/.scratch/<run_id>/`: each search row as it arrived, `id` and
`source_url` paired for the detail read. `skills/job-search-runbook/scripts/clear-run.sh`, in
step 4, deletes the directory.

## What stays off disk

The workspace holds a private job search. Write none of these to a file: API keys and auth headers,
pagination cursors, preference text anywhere but `preferences.md`. A posting's own text is not on
that list: it is stored on the posting's `detail` event, so a changed brief can be re-applied by
judging that stored text again instead of paying to read the same postings a second time.
