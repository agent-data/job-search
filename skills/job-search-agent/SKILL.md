---
name: job-search-agent
description: The operator manual for the job search agent — how it works, why a run came back wrong, and how to change what it does. Use when the user asks how the agent works, what it can do, why the last run failed or found nothing, what a run spent on the job-postings API, or how to change a query, a job source, the recency window, or how often the search runs — how does my job search agent work, explain my agent-data usage, why did the run fail, how do I add a query, change how often it runs. (Setting it up, the home view, and steering the search are job-search; one search pass is job-search-run.)
---

# job-search-agent

The operator manual: how this agent is put together, what to change to get different results, and
what to do when a run comes back wrong. Daily use belongs to the other skills — this card says where
each answer lives, then covers changing the search, explaining what a run spent, and the symptoms a
user arrives with.

## Where each answer lives

| The question | Where it is answered |
|---|---|
| Where the user's files are, what each one holds, and how a run opens and closes | the `job-search-runbook` skill |
| The job-postings CLI, the quirks of each source, retries, and what a call costs | the `agent-data-reference` skill |
| Setting it up, the home view, steering the search, starting or stopping the schedule | the `job-search` skill |
| One search pass, from preflight through the digest to the close | the `job-search-run` skill |
| What the user wants in a job, written as prose in `preferences.md` | the `job-preference-interview` skill |
| How one posting is judged against that brief | the `evaluate-job-fit` skill |

## Changing what it does

Every search setting is a field in the workspace's `config.yaml`: the `queries[]` entries with their
keywords, location, limit and `enabled` flag, plus `search.sources` and `search.freshness`. Edit the
file in place, keeping its comments and shape, then check it with the plugin's
`skills/job-search-runbook/scripts/validate-workspace.sh <workspace>`. The change takes effect
on the next run.

A change that raises what a run opens with — one more query, one more source — gets its new cost
stated before it is saved, per `agent-data-reference`'s cost recipe.

Changing how often the search runs goes through the `job-search` skill, which composes the cadence,
installs the recurring job, and canaries it.

## Explaining what a run spent

Read the newest `runs/<run_id>.json` in the workspace and report its `agent_data_usage`: `searches`,
`detail_reads`, `other`, and `total_metered`, which is the first three added together. That read is
local and spends nothing. `close-run.sh` counts all four at close from the `call` events in
`jobs.jsonl`, and the run wrote one of those events for every attempt it made: `searches` counts
every `call` event whose route is `search-jobs`, a retried one included, which is why it can come
out above the `B` below.
`agent-data-reference` carries the rest — how many calls a month are free, the per-call rates past
that, and `B = enabled queries × enabled sources` as what one run opens with. What the user was
actually billed sits on their account at https://agent-data.motie.dev/settings/billing.

## Symptom → fix

| Symptom | Likely cause | Fix |
|---|---|---|
| Runs finish, but no matches, while real postings exist | the query keywords miss what the brief's must-haves call for | Broaden that query's keywords in `config.yaml`, or run `job-preference-interview` to bring the brief in line |
| A search comes back with no rows at all | keywords too narrow, or a location too specific | Broaden the `keywords` or the `location` in that query |
| The run closed blocked and its digest names the monthly allowance | the free calls for the month are spent, so agent-data is refusing further calls | Check the account at https://agent-data.motie.dev/settings/billing; the matches already saved are unaffected |
| The schedule stopped firing | the installed job was removed, or the machine it runs on was asleep | Read `scheduling` in the registry the runbook's file map names, look for that job in the scheduler `mechanism` names, and reinstall it through the `job-search` skill, which canaries it |
| The home view keeps offering to refresh the brief | `preferences.md` has not been updated in a long time, and runs have happened since | Run `job-preference-interview`, which moves `updated_at` to today |
| A run died mid-flight | it stopped before it could close, leaving its `runs/.started-*` marker behind | Say the last run did not finish, then close and clear it before running again — the first step of the runbook's run contract, which gives both commands and where the `<run_id>` comes from |
| The digest says the run left postings unjudged | it stopped before judging everything it found; `close-run.sh` refuses a `complete` close over unjudged postings, so that record reads `blocked` or `interrupted` | Its `postings_unreviewed` is how many; run the search again, which offers those postings once more because a posting carrying no judgment is not treated as one already seen |
