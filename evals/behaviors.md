# Behavior → eval matrix (B1–B16)

B1–B14 are the 14 kept behaviors from
`docs/superpowers/specs/2026-07-30-skill-overhaul-design.md` §Eval plan, one row id each. B15 and
B16 were added by the 2026-07-31 skill locality restructure, which gave every file a skill reads an
address inside the skill's own directory and grew the plugin from five skills to seven. Each of
those changes needs its own measurement: that files resolve, and that routing still lands on the
skill that owns the phrase.
Later tasks cite rows by id (B1…B16). Every case runs on **both** models:

```bash
python3 evals/run_eval.py --case <case> --model sonnet
python3 evals/run_eval.py --case <case> --model haiku
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
| B8 | jobs.jsonl conformance + digest numbers re-derive from it | headless-run.yaml | validator + artifact check |
| B9 | run killed mid-flight → orphaned started-marker reported honestly on the next run | kill-midrun.yaml | artifact check (marker exists after the kill) + grader-judged transcript (follow-up session says the last run died, then reruns) |
| B10 | recurring job offered right after first matches; consent recorded | quickstart.yaml | grader-judged transcript + artifact check (`schedule.consented` in the captured config.yaml) |
| B11 | canary runs the real job via the scheduled path before setup is called done | schedule.yaml | artifact check (run record with `trigger: scheduled` and healthy close, written by the canary) + grader-judged transcript |
| B12 | fit judgment: dealbreakers cited, unknowns surfaced, no fabricated posting facts | fit.yaml | grader-judged transcript |
| B13 | read-path budget: files/lines read before the first API call ≤ target (~650 lines) | quickstart.yaml | artifact check (sum of Read-tool lines before the first metered call in the transcript) |
| B14 | wall-clock and metered calls vs the RED baseline | headless-run.yaml | artifact check (`result.json` wall seconds + metered-call count from the transcript, compared against `evals/baseline/2026-07-30-red-baseline.md`) |
| B15 | every plugin file the agent opens resolves on the first attempt, and no miss costs a recovery search | quickstart.yaml, headless-run.yaml | artifact check (`evals/grade_b15.py`) |
| B16 | each trigger phrase loads the skill that owns it, and neither reference skill is selected for a user's words | triggering.yaml | artifact check (`evals/run_triggering.py` writes the selected skill per session and the per-phrase rate) |

Each case file's `behaviors:` header lists exactly the rows above that name it, so a case run
tells you which rows it graded.

## How B15 is graded

`evals/grade_b15.py <run-dir>` replays the run's `transcript.jsonl` and counts the file opens the
agent got wrong. It takes the plugin directory from the run's own `init` event, so a transcript
recorded against an older checkout is graded against the tree that was live for it (`--tree` points
the existence check at a worktree when the checkout has since moved).

- Every `Read` whose `file_path` sits under the plugin directory is one open.
- Every `Bash` command contributes one open per whitespace-separated token that starts with the
  plugin directory — `cat <path>`, `bash <path>`, and a bare `<path>` run as a script all count.
  A sweep that looked only at `Read` would miss all three.
- An open is a **miss** when the path is not a file in the tree. A `Read` also counts as a miss when
  its result came back an error. A `Bash` command's non-zero exit does not count: that is usually
  the script's own verdict, not a path that failed to resolve.
- A `Glob`, `Grep`, `pwd`, or `ls` in the 60 seconds after a miss counts as a **recovery search**.
  A miss costs one wasted call, and then however many calls the agent spends hunting for the file
  while the user watches the raw tool output.
- Paths under the plugin's own `evals/` directory are skipped — those are the harness's scratch and
  results, not something a skill pointed the agent at.

The row passes when a run's miss count is zero.

The method is deliberately wider than the 0.8.0 measurement it replaces, which counted only `Read`
calls on `shared/references/` and `templates/` paths. On the two 0.8.0 runs that were measured by
hand it returns the same miss counts, and on other 0.8.0 runs it finds misses the narrower scope did
not report — reference filenames the model invented, and workspace files it looked for inside a
skill directory.
