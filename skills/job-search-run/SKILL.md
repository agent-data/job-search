---
name: job-search-run
description: Run one headless, non-interactive job-search pass that finds and judges new postings and writes a digest. Use to run the scheduled search, check for new jobs, or run a search on demand — run a job search now, pull jobs now, do a fresh search — or when a schedule starts the run. (For interactive setup or the home view, use job-search; for a single pasted posting, use evaluate-job-fit.)
---

# job-search-run

One pass over the user's job-search workspace: search the enabled sources, judge what is new
against their brief, write the digest, close the run. Nobody is there to answer a question while
it runs, so every choice comes from `config.yaml`, `preferences.md`, and two skills to invoke
first:

- `job-search-runbook` — the workspace, the run contract, the scratch rule.
- `agent-data-reference` — the CLI, the per-source quirks, retries, what calls cost.

## Preflight, then open the run

1. Find the workspace with the runbook's discovery step. On a first run — the one with no
   `config.yaml` yet — say that setup happens in the job-search skill, and stop there: this run
   has no workspace to write into.
2. Open the run as the runbook's run contract does: a leftover marker means the last run stopped
   before it could close, so say that and delete it; then create this run's marker and take the
   brief revision. From here on, a failure closes as a `blocked` run.
3. Run `agent-data whoami`. When `api_key_set` comes back false, close blocked: the API key is
   missing, and `agent-data init` from `agent-data-reference`'s CLI table is the fix.
4. Run the plugin's `skills/job-search-runbook/scripts/validate-workspace.sh <workspace>`, and keep
   both streams: one of its three answers arrives on stdout and the other two on stderr, so a call
   that captured stdout alone would read a clean workspace as silence. A single line on stderr
   reading `checked <workspace> — no broken rule found`, at exit 0, means the config and the brief
   are both usable. Read the path in that line and confirm it is the workspace you meant to check,
   because every valid workspace passes this check the same way, so the path is the only part of the
   answer that tells you which one was read. One line per problem on stdout instead, each naming one
   file and one broken rule, at exit 1, means the workspace is not usable: close blocked and report
   those problems to the user in plain language. Exit 2 with a message on stderr means the command
   was wrong rather than the workspace — a path that is no workspace, or a flag the script does not
   take — so fix the command and run it again.
5. Say what this run opens with, in the shape `agent-data-reference`'s cost recipe gives, before
   searching.

## Search

Read the route list once with `agent-data docs <listing id>`, which is free, and take every
parameter name from it. One `search-jobs` call reaches one source, so each enabled query runs once
per entry in `search.sources`: keywords, location and `limit` from the query, `source` from the
list, `search.freshness` as the cutoff parameter the route docs name (the `any` window sends
none). This pass reads those first pages and stops there — a continuation page holds what the next
run finds new.

Run each search with this skill's `scripts/search-jobs.sh --query-id <the query's id> --source <the
source you asked for> -- <the route's own parameters>`. Everything after `--` goes to the route
unchanged, so the parameter names come from `agent-data docs` and this script never has to know
them. It finds the workspace and the open run itself, captures both streams into
`runs/.scratch/<run_id>/`, and records the call whether it returned or failed. It appends the call
itself and one line per row it kept, leaving out a posting any run has already judged and one an
earlier search of this run surfaced. Pass `--source` on every call, a failed one included:
`run-counts.sh` groups the search calls by source and query id, and a failed attempt recorded
without it lands in a group of its own, where the run reports a search that never returned even
though the retry answered. A non-zero exit means the call failed or a row was unusable, and stderr
says which — the call event is written either way, and nothing else is.

Then check the saved response for the echoes: the source echo per `agent-data-reference`'s
source-echo row, and the cutoff the same way, where one that comes back missing or altered means
applying that date to the rows yourself.

## Reconcile

`record-api-response.sh` has already left out the rows that need no judgment. One case is left for
you, because no script decides it: one opening posted several times over. A company running the same
role in four cities returns four rows with four `source_id`s and titles that differ only by the
city, and reading each spends a detail call on a posting already read. Pipe the rows this run
surfaced as `<source>:<source_id><TAB>company<TAB>title` into this skill's
`scripts/dedup.sh --near`. On stdout it prints the first row of each group sharing a company and a
title, so one role posted in four cities becomes one posting to read. On stderr it names every row
it left out and the row it matched that row to, written in the `<source>:<source_id>` form
`--same-role-as` takes, so you do not have to work out that pairing yourself. Each row it left out
still needs a judgment before this run can close, and "Read and judge" says how it gets one.

## Scan the summaries

Judge every surfaced row from what the row carries — title, company, `location_display`,
`salary_display`, the date. A row that plainly breaks a must-have the brief names is settled here,
with no detail read, through this skill's
`scripts/record-judgment.sh <workspace>/jobs.jsonl --run-id <run_id> --source <source>
--source-id <source_id> --detail-read false --relevant false
--dealbreakers '<the must-have it broke>' --reasoning '<how the row breaks it>'`.
Every other row goes on the read list with this skill's
`scripts/queue-detail-read.sh <workspace>/jobs.jsonl --run-id <run_id> --source <source>
--source-id <source_id>`, which records that the posting is one to read and nothing else.

This scan is the only thing deciding whether a posting costs a detail call, so settling every row
the row itself settles is what keeps detail reads few. Send nothing about the judgment you expect: a
provisional band would anchor the reader before it has read anything, and naming the question it
has to answer would stop it looking for anything else. The reader works the open question out from
the posting and writes it into its reasoning.

## Read and judge

The read list is this skill's `scripts/list-detail-read-queue.sh <workspace>/jobs.jsonl <run_id>`,
which prints one tab-separated line per posting this run queued and has not judged yet: `source`,
`source_id`, `posting_id_at_seen`, `source_url`, `title`, `company_name`. It writes one line to
stderr as well: how many lines of the log name this run, then how many postings the run queued, how
many of those already carry a judgment, and how many are left to read. Read that line every time no
row comes back, because a queue worked all the way off and a mistyped run id both print nothing —
`0 of <n> lines … name run` is the mistyped id. Where your host has subagents, give each subagent
two or three postings, and start every subagent in one step, before any of them has returned. Fewer
than four postings go to one subagent. Each subagent judges its postings in its own fresh context,
which leaves this session's context for coordinating the run. Starting some subagents and waiting
for them to return before starting the rest makes the run take as long as the slowest subagent in
each group, added up over the groups. Where your host has none, work the list in order. Both paths
run on the host's own model.

A subagent cannot see this session, so its prompt is everything it gets. Write each prompt with
these five parts, in this order:

1. Its job postings, one block each, carrying the `source`, `source_id`, `posting_id_at_seen`,
   `source_url`, `title` and `company_name` the read list printed.
2. The `evaluate-job-fit` skill to load.
3. The `fetch-posting.sh` command for each posting, written out with that posting's values already
   in place.
4. The `record-judgment.sh` command for each posting, with `--source`, `--source-id` and
   `--detail-read true` already in place, and the remaining values named in words: `--relevant`
   takes `true` or `false`, and `--match` takes `strong`, `moderate` or `weak` and is left off when
   `--relevant` is `false`.
5. What to return for each posting: the title, the company, whether it is relevant, the match band,
   and the reasoning line.

Both scripts find the workspace and the open run themselves, so the prompt carries no file paths.

Read each posting with this skill's `scripts/fetch-posting.sh --posting-id <posting_id_at_seen>
--source-url <source_url> --source <source>`. It finds the workspace and the open run itself, so it
takes nothing else. It records the billable call the run is charged for, and it stores the
posting's text so a later run can judge it again against a changed brief instead of paying to read
it twice. Record what `evaluate-job-fit` returned with this skill's `scripts/record-judgment.sh`,
which finds the workspace and the open run itself: `--detail-read true`, `--relevant` as `true` or
`false`, `--match` as `strong`, `moderate` or `weak` on a relevant posting and no `--match` on one
that is not, `--needs-human-check true` when the judgment leaves the user a question,
`--dealbreakers` and `--unknowns` as semicolon-separated lists, and `--reasoning` as the line the
digest prints. The script writes the JSON, so nothing a reasoning line says has to be escaped, and
it copies the title, company, location, URL and date off the row that surfaced the posting rather
than taking them from you. Two more flags cover what a row left open: `--posted-at-extracted
<date>` when the row carried no date and the description states one, and `--same-role-as
<source>:<source_id>` on a posting `dedup.sh --near` left out, naming the row that was read and
carrying its judgment with `--detail-read false`. Each of those two flags is the only thing that
writes its field, so a judgment recorded without them carries neither. `--detail-read true` needs
the posting's text already stored, which `fetch-posting.sh` does; a judgment claiming a read with
nothing stored is refused.

This skill's `templates/jobs-event.example.json` holds one line of each of the five event types a
run writes — `call`, `surfaced`, `queued`, `detail`, `evaluated` — each in the shape and field order
the script that writes it produces. Read it to see what a line in the log holds; the scripts above
write every line a run appends, and none is filled in by hand.

Every posting this run surfaced ends the run with a judgment — the one from its detail read, or the
one the scan settled from its row. `close-run.sh` refuses a `complete` close while any is still
unjudged and says how many, so a pass that ends that way closes `interrupted`, its digest saying how
many are left.

## Digest

`<date>` is this run's start date in UTC as `YYYY-MM-DD`; the path is
`notify.digest_path_template` with `{date}` substituted, or `reports/{date}-digest.md` by default.

Both halves of the file are read back out of `jobs.jsonl` rather than written from memory of the
run. The numbers come from this skill's `scripts/run-counts.sh <workspace>/jobs.jsonl <run_id>`,
which prints one `key=value` per line; the postings come from
`scripts/run-matches.sh <workspace>/jobs.jsonl <run_id>`, which prints one tab-separated line per
posting this run judged — band, source, source_id, title, company_name, location_display,
source_url, needs_human_check, posted_at, reasoning, also_posted — strong first, then moderate,
weak, and the ones judged not relevant. Both write one line to stderr as well, opening with how many
lines of the log name this run: `0 of <n> lines … name run` means the run id is wrong, and every
number below it would be a zero copied into the digest. `run-matches.sh` carries its per-band tally
on that line — strong, moderate, weak, filtered, and the postings that are the same opening as
another and got no row. Render each section from the lines carrying its band and take how many it
holds from that tally rather than counting the rows yourself, so a heading that says three strong is
followed by the three lines whose band is strong.

An opening the run found in more than one place counts once and is listed once. The postings whose
judgment named another in `--same-role-as` are counted under `duplicates_of_another` and in no band,
and they get no line of their own; the other places that opening was posted arrive in the
`also_posted` column of the line that is listed, joined with `; `. VERY IMPORTANT: Say those places on that line
rather than dropping them — the user is choosing where to apply, UNLESS the location contradicts the user's preferences.

One of those postings adds nothing to that column: one whose row came back with no location. It is
still counted under `duplicates_of_another`, so that number can be higher than the number of places
`also_posted` names, and a line whose column is empty is a line to write without an `also posted in`
of its own.

The file takes this shape, with this run's numbers and matches in place of the placeholders:

```
# Job search digest — <date>
Run ID: <run_id>
Run health: healthy
9 new postings (6 LinkedIn · 3 Ashby) · 3 strong · 2 moderate · 1 weak · 3 filtered out · 4 searches · 5 detail reads
Agent-data usage: 9 metered calls this run

## Strong matches
- **<title>** — <company> — <location> · <Source>
  <one line of reasoning>.  [view](<source_url>)
  also posted in <the also_posted column, on a posting whose column is not empty>
  ⚠ confirm: <the open question, from the reasoning of a posting whose needs_human_check reads true>

## Moderate matches
## Weak matches
## Filtered out (not relevant): 3
- <title> — <company> — <the must-have it broke>

<footnotes>
```

`Run health:` is the `run_health=` line `close-run.sh` printed. The counts line opens with
`postings_surfaced` and reads on through `match_strong`, `match_moderate`, `match_weak` and
`filtered_out`; the parenthetical breaks that opening number down by the `by_source_*` lines and
appears, with the ` · <Source>` tag on each posting, only when the run searched more than one
source. `calls_searches` and `calls_detail_reads` close the line, and `calls_total_metered` is the
usage line under it. A match whose `posted_at` came back empty ends its reasoning line with the date
the description stated, or with the fact that none is.

Two more lines belong in the digest when these counts are not zero. When `postings_unreviewed` is
not zero, say how many postings this run never judged. When `searches_never_succeeded` is not zero,
a footnote names the searches `searches_never_succeeded_ids` lists, each written
`<source>:<query_id>`, as searches that never returned. Footnotes carry the rest: expired detail
links and a source lost partway.

## Close

Close is the runbook's step 4, in the order it gives: `close-run.sh`, then this digest, then
`clear-run.sh`, then the plugin's
`skills/job-search-runbook/scripts/validate-workspace.sh <workspace> --post-close <run_id>`, fixing
whatever it prints on stdout. A close with nothing wrong prints nothing there and writes one line to
stderr — `checked <workspace> and run <run_id> — no broken rule found` — which is the answer, not
a finding to act on. Three values on the `close-run.sh` command line are yours to decide and nothing
else in the record is. `--trigger` is `manual` for a run the user asked for and `scheduled` for one
a scheduler started, including the verification run after a schedule change; `--scheduler-id` names
that job; `--close-state` is the runbook's `complete`, `blocked` or `interrupted`.
`--brief-revision`, `--sources` and `--queries` come off the open and off this run.

The script fills the rest of the record from `run-counts.sh` and one clock read, so the record and
the digest are built from the same log and cannot disagree — this skill's
`templates/run-record.example.json` shows the fields it writes. It works out `run_health` as well,
and prints it as `run_health=healthy` or `run_health=degraded`: a run reads `degraded` when it
closed anything but `complete`, left a posting unjudged, had a search that never returned after its
retries, or judged a posting relevant without a band. Finish by saying what the run found and where
the digest is, in plain language.

## When a call or a run stops early

Retries, the three-attempt budget, and the rule ending one source's work after two retryable
failures in a row live in `agent-data-reference`; after them, finish the pass with what you have,
judging the postings a source failed on from their rows. A run that has to stop closes the same way — the
runbook's `blocked` and `interrupted` states — with what happened and one next step in its digest.
