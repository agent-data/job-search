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
4. Run the plugin's `skills/job-search-runbook/scripts/validate-workspace.sh <workspace>`. Silence
   means config and brief are usable; each line it prints names one file and one broken rule, so
   close blocked and report those in plain language.
5. Say what this run opens with, in the shape `agent-data-reference`'s cost recipe gives, before
   searching.

## Search

Read the route list once with `agent-data docs <listing id>`, which is free, and take every
parameter name from it. One `search-jobs` call reaches one source, so each enabled query runs once
per entry in `search.sources`: keywords, location and `limit` from the query, `source` from the
list, `search.freshness` as the cutoff parameter the route docs name (the `any` window sends
none). This pass reads those first pages and stops there — a continuation page holds what the next
run finds new.

Capture both streams of every call into `runs/.scratch/<run_id>/`, because a call that fails writes
its body to stderr and leaves stdout empty: `agent-data call … > <name>.json 2> <name>.err`. Then
hand whichever file got written — the `.json` when the call returned, the `.err` when it failed — to
this skill's `scripts/record-api-response.sh <run_id> <workspace>/jobs.jsonl <response>
--route search-jobs --query-id <the query's id> --source <the source you asked for>`. That appends
the call itself and one line per row it kept, leaving out a posting any run has already judged and
one an earlier search of this run surfaced. Pass `--source` on every call, a failed one
included: `run-counts.sh` groups the search calls by source and query id, and a failed attempt
recorded without it lands in a group of its own, where the run reports a search that never returned
even though the retry answered. A non-zero exit means the call failed or a row was unusable, and
stderr says which — the call event is written either way, and nothing else is.

Then check the saved response for the echoes: the source echo per `agent-data-reference`'s
source-echo row, and the cutoff the same way, where one that comes back missing or altered means
applying that date to the rows yourself.

## Reconcile

`record-api-response.sh` has already left out the rows that need no judgment. One case is left for
you, because no script decides it: one opening posted several times over. A company running the same
role in four cities returns four rows with four `source_id`s and titles that differ only by the
city, and reading each spends a detail call on a posting already read. Pipe the rows this run
surfaced as `source_id<TAB>company<TAB>title` into this skill's `scripts/dedup.sh --near`, which
prints back the `source_id` of the first row in each group sharing a company and a title: one role
in four cities, one read. Keep the ids it left out — each of those postings still needs a judgment
before this run can close, and "Read and judge" says how it gets one.

## Scan the summaries

Judge every surfaced row from what the row carries — title, company, `location_display`,
`salary_display`, the date. A row that plainly breaks a must-have the brief names is settled here,
with no detail read, through this skill's
`scripts/record-judgment.sh <workspace>/jobs.jsonl --run-id <run_id> --source <source>
--source-id <source_id> --detail-read false --relevant false --reasoning '<the must-have it broke>'`.
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
`source_id`, `posting_id_at_seen`, `source_url`, `title`, `company_name`. Where your host has
subagents, dispatch one per line, in parallel: each posting is judged in its own fresh context,
leaving this session's for coordinating the run. Where your host has none, work the list in order.
Both paths run on the host's own model.

A reader has none of this session's context, so its line is the whole brief. Hand it that line as it
came off the list — `posting_id_at_seen` and `source_url` are the pair `get-posting` needs, and
`agent-data-reference`'s recipe for that route is how the call is written — along with the path to
`preferences.md` and the `evaluate-job-fit` skill to follow.

Capture each detail response the way a search is captured, then send it through
`scripts/record-api-response.sh <run_id> <workspace>/jobs.jsonl <response> --route get-posting
--source <source>`, which stores the posting's text on a `detail` event so a later run can judge it
again against a changed brief instead of paying to read it twice. Record what `evaluate-job-fit`
returned with `record-judgment.sh`: `--detail-read true`, `--relevant true|false`,
`--match strong|moderate|weak` on a relevant posting and no `--match` on one that is not,
`--needs-human-check true` when the judgment leaves the user a question, `--dealbreakers` and
`--unknowns` as semicolon-separated lists, and `--reasoning` as the line the digest prints. The
script writes the JSON, so nothing a reasoning line says has to be escaped, and it copies the title,
company, location, URL and date off the row that surfaced the posting rather than taking them from
you. Two more flags cover what a row left open: `--posted-at-extracted <date>` when the row carried
no date and the description states one, and `--same-role-as <source>:<source_id>` on a posting
`dedup.sh --near` left out, naming the row that was read and carrying its judgment with
`--detail-read false`. Each of those two flags is the only thing that writes its field, so a
judgment recorded without them carries neither.

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
weak, and the ones judged not relevant. Render each section from the lines carrying its band, so a
heading that says three strong is followed by the three lines whose band is strong.

An opening the run found in more than one place counts once and is listed once. The postings whose
judgment named another in `--same-role-as` are counted under `duplicates_of_another` and in no band,
and they get no line of their own; the other places that opening was posted arrive in the
`also_posted` column of the line that is listed, joined with `; `. Say those places on that line
rather than dropping them — the user is choosing where to apply.

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
links, a source lost partway, and — for each company board (ashby, greenhouse, lever) that returned
rows while this workspace held none of its postings yet — a first pass over it reaching back
further than the freshness window.

## Close

Close is the runbook's step 4, in the order it gives: `close-run.sh`, then this digest, then
`clear-run.sh`, then the plugin's
`skills/job-search-runbook/scripts/validate-workspace.sh <workspace> --post-close <run_id>`, fixing
whatever it prints. Three values on the `close-run.sh` command line are yours to decide and nothing
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
