---
type: design-doc
title: "Count a run from the event log it writes"
status: current
verified: partial
last_reviewed: 2026-08-05
claimed_paths: [skills, tests, evals]
owner_area: Skills & references
repos: [job-search-os]
---

# Count a run from the event log it writes

**Branch:** `feat/counts-from-the-event-log`

A run reports numbers it worked out in its head, and they are wrong. This design moves every
number and every timestamp out of the model's account of the run and into scripts that read the
run's own event log. The model keeps the judgments, which are the only part of a run that is
genuinely its work.

## 1. What is wrong, measured

One real run: `~/.job-search/runs/2026-08-05T02-59-42Z.json`,
`~/.job-search/reports/2026-08-04-digest.md`, `~/.job-search/jobs.jsonl`. Every figure below was
re-measured on 2026-08-05; the command that settles each one is given.

**a. `completed_at` is composed, not read.** The record states `2026-08-05T03:15:00Z`. The file
containing that statement was written at `03:06:50Z`.

```sh
grep completed_at ~/.job-search/runs/2026-08-05T02-59-42Z.json
TZ=UTC stat -f '%Sm' -t '%Y-%m-%dT%H:%M:%SZ' ~/.job-search/runs/2026-08-05T02-59-42Z.json
```

A timestamp read before a file is written cannot be later than that file's mtime. No skill names
a command for reading the clock: `grep -rn "date -u" skills/` returns nothing.

**b. The digest's counts line breaks the rule the skill gives it.** `job-search-run/SKILL.md:123`
states the counts line opens with the number of lines the run appended to `jobs.jsonl`. That
number is 17. The digest opened with 9.

```sh
grep -c 2026-08-05T02-59-42Z ~/.job-search/jobs.jsonl        # 17
sed -n 4p ~/.job-search/reports/2026-08-04-digest.md         # "9 new postings …"
```

**c. A band was reported with no row behind it.** The digest's counts line claims two weak
matches. `jobs.jsonl` holds two `strong`, five `moderate`, and no `weak` row at all.

```sh
grep -o '"match":"[^"]*"' ~/.job-search/jobs.jsonl | sort | uniq -c
```

**d. The record and the digest disagree on metered calls.** Record: `total_metered: 24`. Digest:
"23 metered calls this run."

**e. The record carries no counts.** Its full field set is `run_id, trigger, scheduler_id,
brief_revision, close_state, run_health, sources, queries, agent_data_usage{…}, started_at,
completed_at`.

**f. Most postings the run surfaced never reached `jobs.jsonl` at all.** The digest's own footnote
says LinkedIn returned 55 unique postings and 17 were read in full. Its "Also not relevant" section
names 23 companies; 15 of them have no line in `jobs.jsonl`. All 17 rows that do exist carry
`detail_read: true`, so no posting settled from its summary row was ever recorded — against
`job-search-run/SKILL.md:93`, "Every candidate ends this run with a line in `jobs.jsonl`."

Defect (f) is why (b) cannot be fixed by instruction alone. The counts line is defined over lines
in `jobs.jsonl`, and the run does not write a line for most of what it saw.

## 2. The change, in one sentence

Every value in the run record and in the digest's counts line is either copied from an agent-data
response or computed from `jobs.jsonl`. The model supplies judgments and nothing else.

## 3. Architecture

`jobs.jsonl` is already an append-only log where the last line for a `source` + `source_id` wins.
Four new event types join the `evaluated` one it already holds:

| Event | Written by | Carries |
|---|---|---|
| `call` | a script, after every agent-data call | route, source, query, rows returned, rows new, request id, whether it succeeded |
| `surfaced` | a script, from the search response | every metadata field the row arrived with |
| `queued` | a script, when the scan sends a posting for a full read | that this posting is to be read — nothing else |
| `detail` | a script, from the get-posting response | `description_markdown` and the detail-only fields |
| `evaluated` | a script, from the model's judgment | relevant, band, reasoning, dealbreakers, unknowns, needs-human-check |

`status_changed` stays as it is — the user saying they applied somewhere.

Eight scripts, placed in the skill that owns the step:

| Script | Skill | What it does |
|---|---|---|
| `open-run.sh` | runbook | one clock read mints `run_id` and `started_at`; creates the marker; takes the brief revision; runs the workspace checks |
| `record-api-response.sh` | run | turns one agent-data response into the events it implies |
| `queue-detail-read.sh` | run | marks one posting as one to read in full |
| `list-detail-read-queue.sh` | run | prints the queued postings, one per line, for handing to readers |
| `record-judgment.sh` | run | records one posting's judgment |
| `run-counts.sh` | run | prints this run's counts, `agent_data_usage` included |
| `close-run.sh` | runbook | reads the clock for `completed_at`; takes the counts from `run-counts.sh`; writes the record; clears the marker and scratch |
| `pipeline-counts.sh` | job-search | prints the home view's per-status counts |

The `call` event is written for every attempt, including a failed one — it is the record that the
call happened, which is what makes `agent_data_usage` a count rather than a report. The rows are
all-or-nothing: a response with one bad row appends none of its rows, and the rejection names the
file, the row and the field.

### What the model still supplies

Judgments — relevant or not, which band, the reasoning, the dealbreakers, the unknowns, whether a
human should confirm. Which postings to read in full. And three values at close it alone knows:
`trigger`, `scheduler_id`, `close_state`.

It supplies no count, no timestamp, no posting id, no URL, and no JSON.

## 4. The run record

The eleven existing fields stay. Seven are added:

```json
"postings_surfaced": 50,
"postings_reviewed": 47,
"postings_unreviewed": 3,
"postings_detail_read": 35,
"matches": { "strong": 3, "moderate": 12, "weak": 0 },
"filtered_out": 32,
"by_source": { "linkedin": 25, "ashby": 25 }
```

`postings_detail_read` counts postings that have a `detail` event. It is deliberately not named
`detail_reads`: `agent_data_usage.detail_reads` already exists and counts calls, retries and
failures included. Thirty-five postings queued, 33 returning first try, 1 on a retry and 1 failing
after three attempts gives `postings_detail_read: 34` and `agent_data_usage.detail_reads: 38`. One
is coverage and one is money.

`agent_data_usage` stops being reported and becomes a count of `call` events.

Four invariants, checked by `validate-workspace.sh --post-close`:

1. `strong + moderate + weak + filtered_out == postings_reviewed`
2. `postings_reviewed + postings_unreviewed == postings_surfaced`
3. `sum(by_source) == postings_surfaced`, and `postings_surfaced == sum(rows_new)` over this run's
   successful `call` events — `rows_new` and not `rows_returned`, because one opening reached by
   two queries is returned twice and surfaced once
4. every count equals what `run-counts.sh` recomputes from `jobs.jsonl`

Only 3 and 4 compare the record against something outside itself. Invariants 1 and 2 are
arithmetic the record could satisfy while being uniformly wrong, which is what the real digest
did: `2 + 5 + 2 = 9` balances, against 17 rows.

`postings_unreviewed` is the field that says a run stopped without finishing. In a run that
completed it is zero, and the digest and home view carry it when it is not.

Per the handoff's §3.4, no token or cost field is added. The model cannot measure its own spend,
so any such field would be composed.

## 5. Timestamps

`open-run.sh` reads the clock once. `started_at` keeps the colons; `run_id` uses dashes because it
is a filename. One read means they name the same instant, and the validator checks that they do.
`close-run.sh` reads the clock again for `completed_at`.

Two gates:

- `completed_at` is later than `started_at`.
- `completed_at` is not later than the run record's own mtime. Implemented with `touch -t` on a
  reference file and `test -nt`. Run against the defective record above, this reports
  `completed_at is LATER than the file that states it`.

*Unverified: `-nt` is not in POSIX `test`, though dash, bash and ksh all have it. Confirm on CI's
Linux runner before relying on it.*

## 6. Opening a run validates the workspace

`open-run.sh` calls `validate-workspace.sh` rather than reimplementing it, so the check cannot be
skipped and lives in one place (AAS-BOUND-03, AAS-FORM-04). Exit codes carry the outcome:

- **No `config.yaml`** — nothing to write into. Exit 2, no marker, no run. This is the first-run
  path the run skill already routes to `job-search`.
- **Workspace present, files broken** — the run opens and the findings print. Exit 1. The agent
  closes it `blocked`, so the failure leaves a record the home view surfaces. This preserves
  today's ordering, where opening precedes validation precisely so a failure is recorded rather
  than silently absent.
- **Clean** — exit 0.

`validate-workspace.sh` stays a separate script because two other flows call it standalone: the
agent skill tells the user to run it after hand-editing `config.yaml`, and setup runs it before a
first search.

`agent-data whoami` stays the run skill's own preflight step. The runbook owns the workspace and
the run contract; the CLI belongs to `agent-data-reference`, and `open-run.sh` reaching for it
would put a fact in two homes.

## 7. A close that cannot contradict its own log

`close-run.sh` derives `run_health` from the log: healthy means every search call succeeded and
`postings_unreviewed` is zero. It refuses `--close-state complete` while postings are unreviewed
or a search call failed, and names which.

`evals/baseline/2026-07-30-red-baseline.md:177` already records this failure — "a healthy close
over a hundred unjudged candidates". Today nothing stops it.

## 8. The detail-read queue

The scan settles the rows that plainly break a must-have and queues the rest. Queuing records one
fact and no more — that this posting is one to read:

```
queue-detail-read.sh jobs.jsonl --run-id … --source linkedin --source-id 4449006488
```

It exists so the run can mark a posting without editing `jobs.jsonl`, and so the list of what is
still to read survives outside the coordinating agent's context.

**Nothing about the expected judgment is carried into the queue**, and the `steer` this replaces —
`job-search-run/SKILL.md:57-65,73`, a provisional band plus the open question a read must settle —
is deleted rather than reworked, along with the two eval assertions that graded it
(`job-search-run/evals/evals.json:193,194`). Two reasons, and the second is the one that decides
it:

- A provisional band anchors the reader on a verdict before it has read anything, which works
  directly against `evaluate-job-fit`'s own correction that "the strong/moderate line is the one
  that slips" and that a tie goes to the lower band.
- A named question becomes the scope of the answer. The read is meant to produce an analysis of
  the posting that stands as the reasoning for the judgment; handed "Is this role remote within
  the US?", a reader answers that and stops.

`evaluate-job-fit/SKILL.md:42-44` already owns this behavior and places it correctly — the reader,
which has the posting in front of it, derives the open question and writes it into `reasoning`:
"There is no separate question field; the question lives in `reasoning`." The steer handed that
question down from the orchestrator, which has only seen a summary row. One home, and the
better-informed party (AAS-BOUND-03).

*Inference, not measured: `2026-07-30-skill-overhaul-design.md:74` credits "summary-scan steer"
with killing 65% of detail calls as one phrase. The mechanism that removes a call is the scan
deciding not to read, which this design keeps; the steer is guidance passed to a read that is
already happening. Re-measure detail-call count against the RED baseline after the change rather
than assuming the credit separates cleanly.*

`list-detail-read-queue.sh` prints one tab-separated line per queued, not-yet-judged posting:
`source`, `source_id`, `posting_id_at_seen`, `source_url`, `title`, `company_name`. That is what a
reader needs to fetch and judge the posting, and nothing that pre-judges it. It is also the only
thing the run hands out — the coordinating agent never opens `jobs.jsonl`, which grows past what a
context window can hold. The queue shrinks as judgments land.

## 9. Storing descriptions — a deliberate rule reversal

`job-search-runbook/SKILL.md:103` currently says: "Write none of these to a file: API keys and auth
headers, pagination cursors, full job descriptions, preference text anywhere but `preferences.md`."
Full job descriptions come off that list. Keys, headers, cursors and preference text stay on it.

The reason is that a stored description makes re-judging free. Today, editing `preferences.md`
means the next run pays metered calls to read the same postings again. With the text on the
`detail` event, a changed brief is re-applied by appending new `evaluated` events and reading no
posting twice.

Measured cost, four live detail reads on 2026-08-05: `description_markdown` runs 4,108–8,806 bytes
(Harvey/Ashby 4,108; LinkedIn 8,806; Plaid 5,619; Superpower 4,877), mean 5,852. Against a
three-query, two-source config at `limit: 25`, a run surfaces up to 150 postings at 861 bytes each
and reads roughly 35 in full, so `jobs.jsonl` grows by about 326 KB a run and about 10 MB a month
on a daily schedule.

That growth is why §8's queue and `pipeline-counts.sh` exist. `grep` and `awk` are unbothered by a
10 MB file; a context window is not.

## 10. What changes in each file

| File | Change |
|---|---|
| `job-search-run/SKILL.md` | Reconcile, Scan, Read-and-judge, Digest and Close rewritten around the scripts |
| `job-search-run/scripts/` | five new; `dedup.sh`'s known-ids job absorbed into `record-api-response.sh` (`--near` stays); `event-log-append.sh` idempotency restricted to `evaluated` lines |
| `job-search-run/templates/` | run record gains the seven fields; the event example becomes one per event type |
| `job-search-runbook/SKILL.md` | steps 2 and 4 become `open-run.sh` and `close-run.sh`; the file table's rule restated plainly; full job descriptions leave the off-disk list |
| `job-search-runbook/scripts/` | `open-run.sh`, `close-run.sh` new; `validate-workspace.sh` gains the four invariants, the count fields and the two timestamp gates |
| `job-search/SKILL.md` | the home view calls `pipeline-counts.sh` instead of reading `jobs.jsonl` |
| `job-search/scripts/` | `pipeline-counts.sh` new |
| `job-search-agent/SKILL.md` | `agent_data_usage` is counted, not reported; a symptom row for a run with unreviewed postings |
| `scripts/doc_lint.py` | `DUP_SIGNATURES`' digest-counts-line entry gains an owner once the rule moves out of prose and into `run-counts.sh` |

### Two conflicts with shipped scripts, both reproduced

**`event-log-append.sh` silently drops the judgment.** Its idempotency check greps every line
carrying the `(source, source_id)` pair, whatever the event type, so an `evaluated` event that
follows a `surfaced` event for the same posting is treated as already recorded. Reproduced: a file
with one `surfaced` line, piped one `evaluated` event, still holds one line. The check must look
only at `evaluated` lines.

**`dedup.sh` drops a posting that was never judged.** Its known set is every `source_id` with any
event, so a posting a stopped run surfaced and never judged is skipped forever. Reproduced: with
`abc-123` surfaced and unjudged, `dedup.sh` filters it out of the candidates. The set must be
source_ids carrying an `evaluated` event.

### Language fixes on this branch

The metaphors below stand in for plain facts. Live files only; dated design docs and completed
exec-plans keep their wording as written records.

| File | Line | Term |
|---|---|---|
| `skills/job-search-runbook/SKILL.md` | 54 | "the fold of its events" |
| `skills/job-search/SKILL.md` | 127 | "folded to one entry per" |
| `skills/job-search/evals/evals.json` | 65 | "the fold of jobs.jsonl by" |
| `docs/RELIABILITY.md` | 41, 44, 53 | "the event-log fold", "always folds", "computed by folding" |
| `ARCHITECTURE.md` | 96 | "(known-ids / append / fold)" |
| `TESTING.md` | 302 | "fold the state" |
| `INSTALL_FOR_HERMES.md` | 264 | "any `~`/`${VAR}` spelling of the same directory" |
| `docs/superpowers/plans/2026-07-23-hermes-plugin-install.md` | 720 | the same sentence |
| `docs/design-docs/multi-harness-portability.md` | 588 | "command spelling" |
| `skills/job-search-run/SKILL.md` | 62, 64, 73 | "a steer" as a noun — deleted with the concept, per §8 |
| `skills/job-search-run/evals/evals.json` | 174, 193, 194 | the same |

`evals/baseline/2026-07-30-red-baseline.md:178` ("the close state's presence and spelling") is
literal — it means whether `complete` is spelled correctly — and stays.

### The word budget

`AGENTS.md` sets a 10,000-word budget over the seven `SKILL.md` files. `wc -w skills/*/SKILL.md`
reports 9,092 today. The blocks the scripts take over hold 1,087 words:

| Block | Words |
|---|---|
| `job-search-run` Reconcile (46-55) | 88 |
| `job-search-run` Scan (56-65) | 132 |
| `job-search-run` Read and judge (66-95) | 305 |
| `job-search-run` Digest counts rule (122-129) | 113 |
| `job-search-run` Close (131-145) | 159 |
| `job-search-runbook` One run, start to close (61-84) | 258 |
| `job-search-runbook` Scratch (96-98) | 32 |

*Estimate, not a measurement: replacements naming eight scripts and their flags cost roughly 550
words, leaving the corpus below where it starts. The implementation plan re-measures with
`wc -w skills/*/SKILL.md` and treats exceeding 10,000 as a blocking defect.*

## 11. Where no shell runs

`dedup.sh` sets the precedent this follows: "This is the scripted form of the model-run prose
contract; that prose remains the no-runtime fallback." Every new script states its rule in its own
header, so a host with no shell has the rule even without the script (AAS-PORT-01).

The honest part: counts worked out by hand are not gated by anything. On such a host the run says
so, rather than presenting numbers as checked. This is the handoff's §3.1 principle — an absent
value is honest, a wrong one is not — applied to the counts as well as the clock.

## 12. Testing

**Unit.** `tests/test_mechanics_scripts.py` covers the eight scripts, including the failure paths
proven while designing this: an error response refused with its code and message, a row missing
`source_id` refused with nothing appended, a judgment about a posting no search surfaced refused,
`--relevant true` without a band refused, `--relevant false` carrying a band refused, an identical
judgment recorded twice reported and skipped, a different judgment for the same posting refused
with both lines printed, and free text containing `"`, `\`, a tab and a newline round-tripping
byte-exact.

`tests/test_validate_workspace.py` gains the four invariants, the count fields and the two
timestamp gates.

**Behavioral.** B8 ("jobs.jsonl conformance + digest numbers re-derive from it") gains an
assertion it can fail: the digest's counts line, the run record's counts, and `run-counts.sh`
output must be the same numbers. Two rows are added — `completed_at` no later than the record's
mtime, and `postings_unreviewed` carried into the digest when it is not zero. Assertions read
artifacts, never the model's prose (AAS-TEST-04).

**Live.** One search per source against the real API, checked for the row-shape differences the
formatter absorbs (AAS-TEST-09). Two are known and one is undocumented: LinkedIn fills `posted_at`
and leaves `published_at`, `salary_display`, `is_remote`, `workplace_type`, `employment_type`,
`department_name` and `team_name` null on every row; Ashby is the reverse; and Ashby's
`published_at` carries no timezone (`2026-08-05T04:37:31.446000`) where LinkedIn's does
(`2026-08-04T00:00:00+00:00`). `agent-data-reference` should gain that last row.

## 13. Style anchoring

Prompt changes follow the two in-repo guides. The rules this design leans on:

| Rule | Bears on |
|---|---|
| AAS-FORM-08 | bundling deterministic mechanics as scripts, where a runtime exists |
| AAS-AUTO-11 | scripts cheapen mechanics; judgment stays with the model |
| AAS-FORM-14 | the run record's counts are structured slots, not sentences a model composes |
| AAS-BOUND-03 | the open question a read must settle keeps its one home in `evaluate-job-fit` |
| AAS-BOUND-03, AAS-FORM-04 | `open-run.sh` calls `validate-workspace.sh` rather than restating it |
| AAS-BOUND-08 | the invariants live in the validator |
| AAS-BOUND-09 | the detail-read queue and stored descriptions are handed over as paths and rows |
| AAS-SKILL-03 | scripts resolved by relative path from the skill root |
| AAS-PORT-01 | every script names what a host without a shell does instead |
| AAS-TEST-04 | assertions read artifacts, not prose |
| PSG-TOOL-04, PSG-TOOL-11 | script failures name the consequence and the corrective action |
| PSG-SUB-02 | the queue line is a self-contained brief for a reader with no other context |
| PSG-F-04, AAS-FORM-10 | prohibitions in the rewritten prose carry their alternative |
| PSG-F-02 | the word budget is a counted number with a re-measure step, not "be concise" |

**A deliberate stance on an open question.** The agent-agnostic-skills guide records divergence
\#11 — "Bundled validator scripts vs model-executed contracts" — as having no settled practice.
This design goes all the way to bundled scripts. The justification is measured rather than
doctrinal: asked to count its own rows, the model reported 9 against 17, reported a band with no
row behind it, and disagreed with its own record on metered calls.

## 14. Out of scope

- The `strong / moderate / weak` vocabulary is unchanged.
- `run_id`'s format is unchanged; consumers sort on it.
- `.scratch/` and the `.started-<run_id>` marker keep their meaning.
- No token or cost field.
- The prose voice of the SKILL.md files stays continuous prose. They are read by a model at
  runtime, not by a person browsing documentation, and are not restructured into checklists.
