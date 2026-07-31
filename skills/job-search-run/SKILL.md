---
name: job-search-run
description: Run one headless, non-interactive job-search pass that finds and judges new postings and writes a digest. Use to run the scheduled search, check for new jobs, or run a search on demand — run a job search now, pull jobs now, do a fresh search — or when a schedule starts the run. (For interactive setup or the home view, use job-search; for a single pasted posting, use evaluate-job-fit.)
---

# job-search-run

One pass over the user's job-search workspace: search the enabled sources, judge what is new
against their brief, write the digest, close the run. Nobody is there to answer a question while
it runs, so every choice comes from `config.yaml`, `preferences.md`, and two references to read
first, both named here relative to this file:

- `../../shared/references/runbook.md` — the workspace, the run contract, the scratch rule.
- `../../shared/references/agent-data.md` — the CLI, the per-source quirks, retries, what calls cost.

## Preflight, then open the run

1. Find the workspace with the runbook's discovery step. On a first run — the one with no
   `config.yaml` yet — say that setup happens in the job-search skill, and stop there: this run
   has no workspace to write into.
2. Open the run as the runbook's run contract does: a leftover marker means the last run stopped
   before it could close, so say that and delete it; then create this run's marker and take the
   brief revision. From here on, a failure closes as a `blocked` run.
3. Run `agent-data whoami`. When `api_key_set` comes back false, close blocked: the API key is
   missing, and `agent-data init` from agent-data.md's CLI table is the fix.
4. Run `<plugin-root>/shared/scripts/mechanics/validate-workspace.sh <workspace>`. Silence means
   config and brief are usable; each line it prints names one file and one broken rule, so close
   blocked and report those in plain language.
5. Say what this run opens with, in the shape agent-data.md's cost recipe gives, before searching.

## Search

Read the route list once with `agent-data docs <listing id>`, which is free, and take every
parameter name from it. One `search-jobs` call reaches one source, so each enabled query runs once
per entry in `search.sources`: keywords, location and `limit` from the query, `source` from the
list, `search.freshness` as the cutoff parameter the route docs name (the `any` window sends
none). This pass reads those first pages and stops there — a continuation page holds what the next
run finds new.

Send each response straight into `runs/.scratch/<run_id>/` as it arrives, every row with its `id`
and `source_url` together (the scratch rule), then check the saved copy for the echoes: the source
echo per agent-data.md's source-echo row, and the cutoff the same way, where one that comes back
missing or altered means applying that date to the rows yourself.

## Reconcile

1. **Already judged** — per source, feed the candidate `source_id`s into this skill's
   `scripts/dedup.sh <workspace>/jobs.jsonl <source>`; what it prints, every source's output
   together, is what this run has to judge.
2. **The same row from two queries** — one `(source, source_id)` pair reaching you twice is one
   candidate: keep the first, and remember the other query found it too.
3. **One opening posted twice** — pipe the survivors as `source_id<TAB>company<TAB>title` into
   `dedup.sh --near`, which prints the openings to judge: one role in four cities, one read.

## Scan the summaries

Judge every candidate from its row first — title, company, `location_display`, `salary_display`,
date. Settle a row that plainly breaks a must-have the brief names right there: record it as not
relevant, with no detail read. That keeps detail reads few, and this scan is where you write the
guidance each read works from: everything that could match, and what a row leaves open, goes on
the read list with a one-line **steer** — your provisional read plus the question that read has to
answer, the must-have the row left unconfirmed. A senior-IC title with an Austin location earns a
steer that reads strong and asks whether the role is remote within the US; a row with neither date
field filled also asks for the date the description states.

## Read and judge

Where your host has subagents, dispatch one per posting on the read list, in parallel: each is
judged in its own fresh context, leaving this session's for coordinating the run. Where your host
has none, work the list in order. Both paths run on the host's own model. Brief each subagent
cold: the row's `id` and `source_url` as the pair they arrived in, its `source`, the path to
`preferences.md`, the `evaluate-job-fit` skill to follow, and that posting's steer. The read is
agent-data.md's `get-posting` recipe.

Append one line per row to `<workspace>/jobs.jsonl` by piping the single-line event JSON into
this skill's `scripts/event-log-append.sh <workspace>/jobs.jsonl`, which checks the line and skips a
pair the log already holds. Its `templates/jobs-event.example.json` is one such line with every
field filled — copy that field set, and fill it from this run:

- `event` is `evaluated`, `run_id` is this run's id, and `status` starts at `new`.
- `source`, `source_id`, `title`, `company_name`, `location_display`, `salary_display`, and
  `source_url` copied from the row as they arrived; `posting_id_at_seen` from the row's `id`;
  `posted_at` from its dates through agent-data.md's per-source date row; `query_id` the query.
- `detail_read` is true for a posting read in full and false for one settled from its row;
  `relevant`, `match`, `reasoning`, `dealbreakers_hit`, `unknowns`, and `needs_human_check` are the
  judgment as `evaluate-job-fit` returned it, and `ts` and `first_seen` the UTC moment of it.
- `posted_at_extracted` joins the line when the row carried no date and the description states one;
  `same_role_as` joins a dropped near-duplicate, holding `<source>:<source_id>` of the row that was
  read, whose judgment it carries with `detail_read` false.

Every candidate ends this run with a line in `jobs.jsonl` — the judgment from its detail read, or
the one the scan settled from its row. A pass ending with candidates unjudged closes `interrupted`,
its digest saying how many are left.

## Digest

`<date>` is this run's start date in UTC as `YYYY-MM-DD`; the path is
`notify.digest_path_template` with `{date}` substituted, or `reports/{date}-digest.md` by default.
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
  ⚠ confirm: <the open question, on a judgment that set needs_human_check>

## Moderate matches
## Weak matches
## Filtered out (not relevant): 3
- <title> — <company> — <the must-have it broke>

<footnotes>
```

Strong band first. The counts line opens with the number of lines this run appended to
`jobs.jsonl`, and its band and per-source numbers count those same lines; the breakdown and the
` · <Source>` tag appear when the run searched more than one source. A match whose row carried no
date ends its reasoning line with the date the description stated, or with the fact that none is.
Footnotes carry the rest: expired detail links, a source lost partway, and — for each company
board (ashby, greenhouse, lever) that returned rows while this workspace held none of its postings
yet — a first pass over it reaching back further than the freshness window.

## Close

Close through the runbook's steps 4 and 5, in that order: the run record, the digest, deleting the
marker and the scratch directory, then
`<plugin-root>/shared/scripts/mechanics/validate-workspace.sh <workspace> --post-close <run_id>`,
fixing whatever it prints. Copy the field set of this skill's `templates/run-record.example.json`,
with this run's value in each field.

`trigger` is `manual` for a run the user asked for and `scheduled` for one a scheduler started,
including the verification run after a schedule change. `agent_data_usage` counts the calls this
run made, retries and failed attempts included, rather than the calls it opened with.
`run_health` is the single word `healthy` when every search answered and every candidate reached a
judgment, and `degraded` on every other close, a `blocked` one included — the digest then names
which source was lost or what stopped the run. `close_state` is a separate field, defined in the
runbook. Finish by saying what the run found and where the digest is, in plain language.

## When a call or a run stops early

Retries, the three-attempt budget, and the rule ending one source's work after two retryable
failures in a row live in agent-data.md; after them, finish the pass with what you have, judging
the postings a source failed on from their rows. A run that has to stop closes the same way — the
runbook's `blocked` and `interrupted` states — with what happened and one next step in its digest.
