# Behavior → eval matrix (B1–B14)

The 14 kept behaviors from `docs/superpowers/specs/2026-07-30-skill-overhaul-design.md` §Eval
plan, one row id each. Later tasks cite rows by id (B1…B14). Every case runs on **both** models:

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

Each case file's `behaviors:` header lists exactly the rows above that name it, so a case run
tells you which rows it graded.
