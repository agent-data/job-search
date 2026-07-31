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
   brief revision from `preferences.md`. From here on, a failure closes as a `blocked` run.
3. Run `agent-data whoami`. When `api_key_set` comes back false, close blocked: the API key is
   missing, and `agent-data init` from agent-data.md's CLI table is the fix.
4. Run `<plugin-root>/shared/scripts/mechanics/validate-workspace.sh <workspace>`. Silence means
   config and brief are usable; each line it prints names one file and one broken rule, so close
   blocked and report those in plain language.
5. Say what this run opens with, in the shape agent-data.md's cost recipe gives, before searching.

## Search

Read the route list once with `agent-data docs <listing id>`, which is free, and take every
parameter name from it. One `search-jobs` call reaches one source, so each enabled query in
`config.yaml` runs once per entry in `search.sources`: keywords, location and `limit` from the
query, `source` from the list. Turn `search.freshness` into the cutoff parameter the route docs
name; the `any` window sends no cutoff.

Check each response against what you asked for — the source echo, per the source-echo row in
agent-data.md, and the cutoff echo the same way; a sent cutoff that comes back missing or altered
means keeping the rows and applying that date yourself. Write every returned row into
`runs/.scratch/<run_id>/` as it arrived, `id` and `source_url` together (the scratch rule).

## Reconcile

1. **Already judged** — per source, feed the candidate `source_id`s into
   `<plugin-root>/shared/scripts/mechanics/dedup.sh <workspace>/jobs.jsonl <source>`; what it
   prints, every source's output together, is what this run has to judge.
2. **The same row from two queries** — one `(source, source_id)` pair reaching you twice is one
   candidate: keep the first, and remember the other query found it too.
3. **One opening posted twice** — feed the survivors as `source_id<TAB>company<TAB>title` lines
   into `dedup.sh --near`, which prints the openings to judge and drops the repeats, so a company
   posting one role in four cities bills one detail read rather than four.

## Scan the summaries

Judge every candidate from its row first — title, company, `location_display`, `salary_display`,
date. Settle a row that plainly breaks a must-have the brief names right there: record it as not
relevant, with no detail read. That is what keeps detail reads few, and this scan is also where you
write the guidance each read works from: everything that could match, and what a row leaves open,
goes on the read list with a one-line **steer** — your provisional read plus the specific question
the detail read has to answer, the must-have the row left unconfirmed, what is uncertain. A
row whose title reads senior IC and whose location reads Austin gets a steer saying it looks
strong and asking whether the role is remote within the US; a row with neither date field filled
also asks for the posting date the description states.

## Read and judge

Where your host has subagents, dispatch one per posting on the read list, in parallel: each
posting is judged in its own fresh context, leaving this session's context for coordinating the
run. Where your host has none, work the read list in order. Both paths run on the host's own
model. Give each subagent enough to work cold: the row's `id` and `source_url` as the pair they
arrived in, its `source`, the path to `preferences.md`, the `evaluate-job-fit` skill to follow for
the judgment, and that posting's steer. The read itself is agent-data.md's `get-posting` recipe.

Append one line per row to `<workspace>/jobs.jsonl` by piping the single-line event JSON into
`<plugin-root>/shared/scripts/mechanics/event-log-append.sh <workspace>/jobs.jsonl`, which checks
the line and skips a pair the log already holds. `<plugin-root>/templates/jobs-event.example.json`
is one such line with every field filled — copy that field set, and fill it from this run:

- `source`, `source_id`, `title`, `company_name`, `location_display`, `salary_display`,
  `posted_at`, `source_url` copied from the row as they arrived, and `posting_id_at_seen` from the
  row's `id`; `query_id` names the query whose search returned it.
- `detail_read` is true for a posting read in full and false for one settled from its row;
  `relevant`, `match`, `reasoning`, `dealbreakers_hit`, `unknowns`, and `needs_human_check` are
  the judgment as `evaluate-job-fit` returned it; `ts` and `first_seen` are the UTC moment of it.
- `posted_at_extracted` joins the line when the row carried no date and the description states
  one. `same_role_as` joins a row the near-duplicate step dropped, holding
  `<source>:<source_id>` of the row that was read: such a row carries that row's judgment with
  `detail_read` false, so the next run treats it as already judged.

Every candidate ends this run with a line in `jobs.jsonl` — the judgment from its detail read, or
the one the scan settled from its row. A pass that ends with candidates still unjudged is an
`interrupted` run, and its digest says how many are left for the next one.

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

Strong band first. Count the lines this run appended to `jobs.jsonl` — in total, by source, by
band — and write those counts on the counts line; the per-source breakdown in parentheses and the
` · <Source>` tag appear when the run searched more than one source. A match whose row carried no
date ends its reasoning line with the date the description stated, or with the fact that none is
stated. Footnotes carry the rest: expired detail links, a source lost partway, and — for each
company board (ashby, greenhouse, lever) that returned rows while this workspace held none of its
postings yet — that a first pass over it reaches back further than the freshness window.

## Close

Close through the runbook's steps 4 and 5, in that order: the run record, the digest, deleting the
marker and the scratch directory, then
`<plugin-root>/shared/scripts/mechanics/validate-workspace.sh <workspace> --post-close <run_id>`,
fixing whatever it prints. Copy the field set of
`<plugin-root>/templates/run-record.example.json`, with this run's value in each field.

`trigger` is `manual` for a run the user asked for and `scheduled` for one a scheduler started,
including the verification run after a schedule change. `run_health` is the single word `healthy`
when every search answered and every candidate reached a judgment, and `degraded` when the run
finished anyway with a source skipped or a search lost — then name that source and the reason in
the digest. `close_state` is a separate field, defined in the runbook. Finish by saying what the
run found and where the digest is, in plain language.

## When a call or a run stops early

Retries, the three-attempt budget, and the rule ending one source's work after two retryable
failures in a row live in agent-data.md; after them, finish the pass with what you have, judging
the postings a source failed on from their rows. A run that has to stop closes the same way — the
runbook's `blocked` and `interrupted` states — with what happened and one next step in its digest.
