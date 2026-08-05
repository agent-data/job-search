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

It prints three lines:

```
workspace=/Users/dana/job-search
source=legacy
first_run=false
```

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
path cannot be read, rather than picking a workspace it might not name. The script reads it with
`grep` and cannot tell a corrupt file from an absent one, so parse-check it yourself.

## What each file holds

| File | Written by | Read by |
|---|---|---|
| `config.yaml` — queries, sources, schedule | setup, then the user by hand | every run, the home view |
| `preferences.md` — the brief, in prose | the preference interview | every run, every fit judgment |
| `jobs.jsonl` — append-only event log, one JSON object per line; a posting's current state is the fold of its events by `source` + `source_id` | every run | the home view, the pipeline, duplicate checks |
| `runs/<run_id>.json` — one record per run | a run at close | the home view, the agent skill |
| `runs/.started-<run_id>` — empty marker: this run is open | a run at start, deleted at close | the next run |
| `reports/<date>-digest.md` — the digest the user reads | a run at close | the user, the home view |
| `.gitignore` — copied from the plugin's `skills/job-search/templates/workspace.gitignore`; denies everything but itself | setup | git |
| `~/.config/job-search/config.json` — the registry, which sits outside the workspace: `active_workspace`, plus `scheduling` holding the booleans `installed` and `verified` — both true only after a canary proved the job — and the strings `mechanism` (cron, launchd, or the host's own) and `scheduler_id` | setup, schedule changes | discovery, the home view |

## One run, start to close

1. **Look for a leftover marker** — `ls <workspace>/runs/.started-* 2>/dev/null`. A marker there
   belongs to a run that stopped before it could close. Say that the last run did not finish,
   delete the marker, and go on with this run.
2. **Open the run.** `run_id` is the current UTC time written like `2026-07-30T15-04-02Z` — an ISO
   timestamp with dashes in place of the colons, so it works as a filename. Create the empty marker
   `runs/.started-<run_id>`, then read the brief's revision before anything can edit it:
   `shasum -a 256 <workspace>/preferences.md | cut -c1-12` (or `sha256sum` — same digest).
3. **Do the run's work**, appending to `jobs.jsonl` as you go.
4. **Close.** Write `runs/<run_id>.json` — every field, with realistic values, is in the plugin's
   `skills/job-search-run/templates/run-record.example.json`. `brief_revision` is the digest from step 2.
   `trigger` is `manual` when the user asked for this run and `scheduled` when a scheduler started
   it, and `scheduler_id` names that scheduler or is `null` for a manual run. `agent_data_usage`
   counts metered calls: `searches`, `detail_reads`, everything else in `other`, and their sum in
   `total_metered`. Then write `reports/<date>-digest.md`. Then delete `runs/.started-<run_id>` and
   `runs/.scratch/<run_id>/`.
5. **Check the close** — run the plugin's
   `skills/job-search-runbook/scripts/validate-workspace.sh <workspace> --post-close <run_id>`.
   It prints nothing and exits 0 when the workspace is right; each line it does print names one
   file and one broken rule to fix.

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

A run's own working files go in `runs/.scratch/<run_id>/`, which step 4 deletes: each search row as
it arrived, `id` and `source_url` paired for the detail read, plus the posting lines you cite.

## What stays off disk

The workspace holds a private job search. Write none of these to a file: API keys and auth headers,
pagination cursors, full job descriptions, preference text anywhere but `preferences.md`.
