# Behavior → eval matrix (B1–B20)

B1–B14 are the 14 kept behaviors from
`docs/superpowers/specs/2026-07-30-skill-overhaul-design.md` §Eval plan, one row id each. B15 and
B16 were added by the 2026-07-31 skill locality restructure, which gave every file a skill reads an
address inside the skill's own directory and grew the plugin from five skills to seven. Each of
those changes needs its own measurement: that files resolve, and that routing still lands on the
skill that owns the phrase.

B17–B20 were added by the 2026-08-05 change that moved every count a run reports out of the model's
head and into scripts that read the run's own event log. That change is only visible in the files a
run leaves behind, so each of those four rows re-derives a number from the captured log and compares
it against what the run wrote down.
Later tasks cite rows by id (B1…B20). Every case runs on **both** models:

```bash
python3 evals/run_eval.py --case <case> --model sonnet
python3 evals/run_eval.py --case <case> --model haiku
```

`triggering` is the one case `run_eval.py` cannot run — it holds a list of phrases instead of a
single `prompt`, and `run_eval.py` raises `KeyError: 'prompt'` on it. It has its own driver:

```bash
python3 evals/run_triggering.py --model sonnet --reps 9
python3 evals/run_triggering.py --model haiku --reps 9
```

Grading methods used below: **grader-judged transcript** (a grader agent reads the stamped
`transcript.jsonl` and judges the behavior), **artifact check** (a deterministic read of the
captured `workspace/`, `result.json`, or transcript tool calls), **validator**
(`validate-workspace.sh`, added by the scripts task). No assertion may match substrings of
documentation files.

| id | behavior | case file | grading method |
|---|---|---|---|
| B1 | first message explains what is happening in plain language, no internal vocabulary | quickstart.yaml | grader-judged transcript (first user-visible message); the interactive-TUI variant of this check is driven manually with expect, outside `run_eval.py` |
| B2 | concepts defined at first mention (brief, free tier, recurring job) | quickstart.yaml | grader-judged transcript |
| B3 | whoami-only preflight; no `status` call anywhere | quickstart.yaml, headless-run.yaml | artifact check (no `status` call in any transcript's Bash tool calls); server-side API-gateway logs are a manual cross-check |
| B4 | cost context stated before the first metered call | quickstart.yaml, headless-run.yaml | grader-judged transcript |
| B5 | summary scan reduces detail reads (detail-read count vs postings found) | headless-run.yaml | artifact check (count `get-posting` calls vs search rows in the transcript and run record) |
| B6 | id+source_url pairing: 0 fabricated ids | headless-run.yaml | artifact check (every `get-posting` id appears in an earlier search result in the same transcript) |
| B7 | detail-read fault fallback: stop after 2 consecutive failed detail reads on a source, judge the rest from summaries (fault injected via postings whose upstream page is dead) | fault-503.yaml | grader-judged transcript + artifact check (all postings judged; no further detail attempts after the second consecutive failure) |
| B8 | jobs.jsonl conformance + digest numbers and digest listings re-derive from it | headless-run.yaml | artifact check: for the run's `run_id`, `skills/job-search-run/scripts/run-counts.sh` over the captured `workspace/jobs.jsonl`, the count fields in the captured `workspace/runs/<run_id>.json`, and the numbers parsed out of the digest's counts line must all be the same. The postings the digest names under each band must be the postings `skills/job-search-run/scripts/run-matches.sh` prints for that band, matched on company and title. Plus `validate-workspace.sh --post-close <run_id>` exiting 0 |
| B9 | run killed mid-flight → orphaned started-marker reported honestly on the next run | kill-midrun.yaml | artifact check (marker exists after the kill) + grader-judged transcript (follow-up session says the last run died, then reruns) |
| B10 | recurring job offered right after first matches; consent recorded | quickstart.yaml | grader-judged transcript + artifact check (`schedule.consented` in the captured config.yaml) |
| B11 | canary runs the real job via the scheduled path before setup is called done | schedule.yaml | artifact check (run record with `trigger: scheduled` and healthy close, written by the canary) + grader-judged transcript |
| B12 | fit judgment: dealbreakers cited, unknowns surfaced, no fabricated posting facts | fit.yaml | grader-judged transcript |
| B13 | read-path budget: files/lines read before the first API call ≤ target (~650 lines) | quickstart.yaml | artifact check (sum of Read-tool lines before the first metered call in the transcript) |
| B14 | wall-clock and metered calls vs the RED baseline | headless-run.yaml | artifact check (`result.json` wall seconds + metered-call count from the transcript, compared against `evals/baseline/2026-07-30-red-baseline.md`) |
| B15 | every plugin file the agent opens resolves on the first attempt, and no miss costs a recovery search | quickstart.yaml, headless-run.yaml | artifact check (`evals/grade_b15.py`) |
| B16 | each trigger phrase loads the skill that owns it, and neither reference skill is selected for a user's words | triggering.yaml | artifact check (`evals/run_triggering.py` writes the selected skill per session and the per-phrase rate) |
| B17 | `completed_at` in the run record is a clock read, not a time the run wrote from memory | headless-run.yaml | artifact check (it parses as the `YYYY-MM-DDTHH:MM:SSZ` shape `date -u` prints, falls after `started_at`, and falls at or before the mtime of the record file itself) |
| B18 | no posting is judged or stored that the run never surfaced, and the call counts in the record are the `call` events the log holds | headless-run.yaml | artifact check — see below |
| B19 | the close in the record of the run that recovers from a killed one is the close its own log supports | kill-midrun.yaml | artifact check — see below |
| B20 | the digest and the home card agree about one log: no opening is listed twice, and the two report the same numbers | headless-run.yaml | artifact check — see below |

Each case file's `behaviors:` header lists exactly the rows above that name it, so a case run
tells you which rows it graded.

## How B15 is graded

`evals/grade_b15.py <run-dir>` replays the run's `transcript.jsonl` and counts the file opens the
agent got wrong. It takes the plugin directory from the run's own `init` event, so a transcript
recorded against an older checkout is graded against the tree that was live for it (`--tree` points
the existence check at a worktree when the checkout has since moved).

- Every `Read` whose `file_path` sits under the plugin directory is one open — **including a `Read`
  aimed at a directory**, which comes back `EISDIR` and is a real failed open. An earlier version of
  this grader dropped directories before checking the error and could not see that shape at all;
  a reference is only a directory to aim at because it became a skill, so the blind spot sat exactly
  where the new failures live.
- Every `Bash` command contributes one open per path it names under the plugin directory —
  `cat <path>`, `bash <path>`, and a bare `<path>` run as a script all count. Paths are followed
  through `cd`, so `cd <skill dir> && ./scripts/foo.sh` is one open on that script; a scan that kept
  only tokens already rooted at the plugin directory sees nothing there.
- A path the command text cannot show — assembled from a variable that expanded to nothing — is
  picked up from the shell's own `No such file or directory` line instead. Absolute paths under the
  plugin directory are left to the command-text scan, so nothing is counted twice.
- An open is a **miss** when the path is not a file in the tree. A `Read` also counts as a miss when
  its result came back an error. A `Bash` command's non-zero exit does not count: that is usually
  the script's own verdict, not a path that failed to resolve.
- A `Glob`, `Grep`, `pwd`, `ls`, or `find` in the 60 seconds after a miss counts as a **recovery
  search**. A miss costs one wasted call, and then however many calls the agent spends hunting for
  the file while the user watches the raw tool output.
- Paths under the plugin's own `evals/` directory are skipped — those are the harness's scratch and
  results, not something a skill pointed the agent at.

The row passes when a run's miss count is zero.

The method is deliberately wider than the 0.8.0 measurement it replaces, which counted only `Read`
calls on `shared/references/` and `templates/` paths. Restricted to that narrower scope it returns
the 0.8.0 published miss counts exactly, including a denominator of 11 on the sonnet quickstart.
Widened, it finds misses the narrower scope did not report — reference filenames the model invented,
workspace files it looked for inside a skill directory, a script reached through `cd`, and a
reference opened as a directory.

**Widen the grader before trusting a clean sweep.** Every widening in the list above was added
because a shape it could not see turned out to be present. A run graded clean by a narrow grader is
not evidence that the run was clean.

## How B18 is graded

Two reads of the captured `jobs.jsonl`, both counted by hand, so neither expectation comes out of
the script it is checking:

- Every `evaluated` event and every `detail` event carrying this `run_id` has a `surfaced` event
  with the same `run_id`, `source` and `source_id`. `run-counts.awk:63-66` walks only the postings
  the run surfaced, so a judgment with no `surfaced` event behind it lands in no number the run
  reports — the row goes into the log, the digest says nothing about it, and nothing prints a
  warning.
- The `call` events for this `run_id`, counted by route, are `agent_data_usage.searches`,
  `.detail_reads` and `.other` in `runs/<run_id>.json`, and the `detail` events counted the same
  way are its `postings_detail_read`.

What is not graded here: whether every row a search returned reached the log. The response bodies
live in `runs/.scratch/<run_id>/`, which `clear-run.sh` deletes at close, so after a clean run
nothing outside the log says how many rows came back. The `rows_returned` field on each
`search-jobs` `call` event is the only surviving count, and it cannot be checked against the rows
themselves.

## How B19 is graded

Three values in the captured `runs/<run_id>.json` are worked out again from the captured
`jobs.jsonl` by hand — without `run-counts.sh`, so the expectation does not come from the script
being checked — and compared against what the record holds:

- `postings_unreviewed` — the postings carrying a `surfaced` event with this `run_id` and no
  `evaluated` event with the same `run_id`, `source` and `source_id`.
- `close_state` — a record whose `postings_unreviewed` is above zero reads `blocked` or
  `interrupted`. `close-run.sh` refuses a `complete` close over unjudged postings and writes
  nothing, so this pair fails only on a record `close-run.sh` did not write.
- `run_health` — `healthy` only when the close is `complete`, nothing is unjudged, every
  `<source>:<query_id>` group of `search-jobs` `call` events holds at least one carrying `ok:true`,
  and no `evaluated` event with `relevant:true` carries a `match` outside strong, moderate and weak.
  A `complete` close reads `degraded` for two reasons and no others: a search whose attempts all
  failed, and a relevant row carrying no band.

The killed session leaves no record of its own to grade. `job-search-runbook/SKILL.md`'s step 1 has
the next run say the last one did not finish, delete its marker and go on, and no step writes a
record for the run that died. So this row grades the record the recovering session writes — the
one case in the suite where a session writes a close right after cleaning up after a run whose
work it never saw.

## How B20 is graded

The seed for this case carries an empty event log — `wc -c evals/seeds/headless-run/jobs.jsonl`
prints 0 — so after one pass the captured `jobs.jsonl` holds that run's events and nothing else.
That is what lets a per-run script and a whole-file script be compared here: both are reading the
same postings.

- No row `skills/job-search-run/scripts/run-matches.sh` prints for the run belongs to a posting
  whose `evaluated` event carries `same_role_as`. A judgment carrying that field is the same opening
  as a row already in the listing, and `skills/job-search-run/evals/evals.json:48`, in the scenario
  for one opening posted in several cities, expects the digest to list that opening once.
- `match_strong` plus `match_moderate` plus `match_weak` from
  `skills/job-search-run/scripts/run-counts.sh` equals `relevant` from
  `skills/job-search/scripts/posting-counts.sh`, and `filtered_out` equals `filtered`, over that
  same log.

**This row fails today. Reporting that is what it was added for.** `posting-counts.awk` reads
`same_role_as` and the two scripts behind the digest never do:

```bash
grep -c same_role_as skills/job-search/scripts/posting-counts.awk \
  skills/job-search-run/scripts/run-counts.awk skills/job-search-run/scripts/run-matches.awk
```

prints 2, 0 and 0. Measured on 2026-08-07 on a four-line log — two `surfaced` events, then two
`evaluated` events whose second names the first in `same_role_as` — `run-counts.sh` printed
`match_strong=2`, `run-matches.sh` printed two rows for the one opening, and `posting-counts.sh`
printed `relevant=1`.

The listing half is settled: the digest shows one opening once, so `run-matches.awk` printing one
row per posting is the side to change. The counts half is not settled, and this row does not decide
it. `job-search-run/SKILL.md` defines the counts line on postings — it opens with
`postings_surfaced` — while `posting-counts.sh`'s own header says `relevant` plus `filtered` is
the number of openings judged rather than the number of postings judged. Two units, each written
down, and nothing says which one the user should be shown. Changing the listing without settling
the unit would leave a digest whose heading says three strong above two rows, which
`run-matches.sh`'s header rules out. Settle the unit first; until then this row is where the
disagreement gets reported.
