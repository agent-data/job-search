---
name: agent-data-reference
description: "The job-postings API the job-search skills call, not something a user asks for: the agent-data CLI and listing id, the per-source quirks, the get-posting recipe, retries, what a call costs."
---

# agent-data-reference — the job-postings API
<!-- reference-resolution-marker:8f2a4c1e-single-home — the job-postings reference lives in this file and nowhere else; a sibling skill reaches it by invoking this skill. Asserted by tests/test_reference_resolution.py; do not remove. -->

One marketplace listing serves four job sources. This file carries what the route docs leave out:
the per-source behavior that changes a query or a judgment, what each call costs, and what to tell
the user before spending one. Route shapes here were read from `agent-data docs` on 2026-07-31.

## The CLI

| Command | What it returns | Cost |
|---|---|---|
| `agent-data whoami` | the resolved config, including `api_key_set` | local, free |
| `agent-data docs <listing-id>` | the live route list, every parameter, every response field | free |
| `agent-data call <listing-id> <slug> [--flag value ...]` | one route's results | one metered call per attempt |
| `agent-data init --api-key <KEY> -y` | writes the key to `~/.agent-data/config.json` | local, free |

The listing id is `f9a6ec16-0bfd-44d8-b3ee-073776745ee7`, and it serves all four sources. Route
parameters ride as flags after the slug, one flag per parameter.

`agent-data docs <listing-id>` is the authority on which routes exist, what each parameter is
called, and which fields come back. It is free, so read it once per run and take the shapes from
that output rather than from memory. The listing has three routes: `search-jobs` returns a page of
summary rows in `data.results[]`, `get-posting` returns one posting's full text, and `status`
reports service health. Adding `--dry-run` to a `call` prints the resolved request and spends
nothing.

One call reaches one source, named by `--source` (linkedin, ashby, greenhouse, or lever). Omit the
flag and the search runs against linkedin. The run does its own fan-out, merge, and duplicate
check, so one query across three enabled sources is three calls.

## Quirks that change a call

| What holds | The recipe |
|---|---|
| The route docs list `Remote` as a location value, and for LinkedIn that string goes to LinkedIn's own filter — a US remote search run that way came back with all-India rows | Put `remote` among the `--keywords`, keep `--location` for a real geography or omit it, and keep the rows whose `location_display` names the geography the user asked for |
| `is_remote` and `workplace_type` come back null on every LinkedIn row | Read remoteness from `location_display` and the description text |
| ashby, greenhouse, and lever match relaxed full text — all terms rank first, then progressively fewer down to a floor of half the terms — so off-topic rows are ordinary output | Judge each row from its title and company first, and spend a detail read only on the survivors |
| `keywords` is the one required search parameter; it takes up to 8 terms, and a trailing `*` makes a term a prefix | Send the terms the user's brief names, and let `--limit` (default 20, max 100) size the page |
| A row's `id` and `source_url` work only as the pair they arrived in — `id` is a short-lived pairing token, while `source_id` is the value that stays stable within its source — and a mismatched pair returns a non-retryable 400 | Copy both from the same row exactly as they arrived; a rejected pair falls back to judging that posting from its summary row |
| Paging works through `--cursor` on ashby, greenhouse, and lever, and LinkedIn rejects a cursor with a non-retryable 400 | When a run pages: take the next page from `data.pagination.next_cursor` while `has_more` is true, replaying every other flag exactly as sent. LinkedIn returns one page, so there is no next page to fetch |
| An older service deployment ignores `--source` and answers as linkedin, so a search aimed at another source comes back holding linkedin rows | After every search, compare the echoed `data.query.source` against the source you asked for (an absent echo counts as linkedin); when the two differ, file the returned rows under the source that actually answered, and skip the rest of that source's queries this run |
| ashby leaves `posted_at` null and carries the date in `published_at`; greenhouse and lever fill both; LinkedIn fills `posted_at` and leaves `published_at` null | Take freshness from whichever of the two is present, and from the later one when both are |
| `salary_display` is free text on every source and arrives as raw HTML on some lever rows; `employment_type` comes back as FULL_TIME, FullTime, or Full-time depending on the source | Strip any markup from `salary_display` and quote the remaining text as written; read `employment_type` as text, since its casing differs per source |
| A detail read returns `missing_fields[]`, naming what the page did not yield | Report each as a detail the posting leaves unstated |
| `source_url` on ashby, greenhouse, and lever is the live apply page; LinkedIn's carries tracking params | Link it as where the user applies |
| The `status` route bills a metered call, and what it reports is one global health number rather than per-source readiness | `whoami` answers the preflight question (`api_key_set`) locally and free, which is what a run needs before its first search |
| The free tier includes 100 calls a month; once it is spent the API answers `403 insufficient_credits`, and that rejected call is unmetered | Stop metered work and tell the user the allowance has been reached, so this run cannot continue until calls are available; their saved matches are unaffected, and their account at https://agent-data.motie.dev/settings/billing is where to check |

## Reading one posting

```sh
agent-data call f9a6ec16-0bfd-44d8-b3ee-073776745ee7 get-posting \
  --posting_id <the row's id> --source_url <the same row's source_url> --source <the row's source>
```

`posting_id` and `source_url` are both required. `--source` is optional, and passing the row's own
value removes an inference step. `--fields` is optional and trims the response.

## When a call fails

Branch on the response's `retryable` boolean. The service collapses most 4xx failures into
`validation_error` and names the offending field in `error.param`, so several different problems
share one code string, while the boolean carries the one thing that decides the next move: whether
trying again can work. When `retryable` is true — the 503 upstream failures — make up to 3 attempts
in all, waiting about 1s and then about 3s between them, adding jitter to each wait. When
`retryable` is false, change the request before calling again, or drop that step.

Every attempt bills, retries included, so a failure that keeps repeating keeps costing calls. A
call counts as failed once its 3 attempts are spent, and two retryable failures in a row on one
source end that operation for that source this run: for searches, drop that source and keep the
others going; for detail reads, judge that source's remaining postings from their summary rows.

## What a run spends

The free tier includes 100 metered calls a month at no charge. Past that, agent-data's rates as
verified on 2026-07-15 — live account data wins wherever it is available:

| Plan | Included metered calls | Effective rate |
|---|---|---|
| pay-as-you-go | purchased as needed | $0.008 per metered call; $5 adds 625 calls |
| $30 a month | 4,000 a month | $0.0075 per call at full use |
| $100 a month | 15,000 a month | about $0.0067 per call at full use |
| $200 a month | 40,000 a month | $0.005 per call at full use |

Count calls. Multiplying a call count by one of these rates produces an estimate; what the user
was actually billed comes from live account data.

`B = enabled queries × enabled sources` is the first-page cost of one run, because each enabled
query reaches each enabled source once: three queries across two sources is six calls. B is the
floor — continuation pages, detail reads, and metered failures and retries land on top of it.

Before the first metered call of a session, tell the user in your own words, in a sentence or two:
how many calls this run opens with (B), that agent-data includes 100 calls a month at no charge,
and that reading promising postings adds calls. Lead with the call count and follow it with the
free tier, so the user can see how big this run is against the month's allowance.

Detail reads are where the number grows, and the summary scan is what keeps them few: judge from
titles and summary rows first, then read full text only for the postings that survive that pass.

A change that raises B for every future run — one more query, one more source, a faster cadence —
gets its new B and the size of the increase stated before it is saved.
