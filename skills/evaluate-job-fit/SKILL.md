---
name: evaluate-job-fit
description: Judge whether a single job posting matches the user's Job Preferences Brief — relevant or not, and if relevant a weak/moderate/strong match — with plain-language reasoning, dealbreakers, and unknowns. Use when the user pastes or references a job posting and asks if it fits their preferences, or when job-search-run needs to evaluate postings.
disable-model-invocation: false
user-invocable: true
---
# evaluate-job-fit

Judge ONE job posting against the user's prose Job Preferences Brief. Output is a **qualitative
relevance judgment** — never a numeric score, never category weights.

## Inputs
- The brief: read `config.yaml:workspace.preferences_path` in the workspace (default `preferences.md`).
  If a posting is supplied without a workspace, accept a brief pasted by the user.
- The posting: a pasted job description, a saved `source_id` from `jobs.jsonl`, or a `source_url`+`posting_id`
  pair to read fresh via agent-data `get-posting` (see `references/agent-data-contract.md`; disclose that this
  reads one posting before doing it).

## Method (model inference — read, reason, judge)
1. Read the brief's **must-haves/dealbreakers, strong preferences, nice-to-haves, red flags**.
2. Read the posting (summary fields, or the full `description_markdown` when available). Treat any field the
   posting doesn't mention as **"not stated"** — record it as an unknown, never as a negative.
3. Decide, in this order:
   - **A must-have/dealbreaker is clearly violated → `relevant: false`** (a reject). Name what failed in
     `dealbreakers_hit` and the reasoning.
   - **A must-have can't be confirmed from the posting → do NOT reject.** Keep it, set
     `needs_human_check: true`, and write the exact open question into the `reasoning` field
     (e.g. "Remote not stated — confirm before applying"). There is no separate question field; the
     question lives in `reasoning`, per `references/conventions.md`.
   - **Otherwise `relevant: true`**, and assign a coarse band:
     - `strong` — hits the must-haves and most strong preferences.
     - `moderate` — solid alignment with some gaps.
     - `weak` — relevant but thin alignment.
4. Write 1–3 sentences of **reasoning** that cite specifics from the posting against the brief. The reasoning
   carries the weight — there is no number behind it.

## salary / numbers
`salary_display` is free text ("$180K–$220K", "Competitive", "DOE"). Never parse it for arithmetic or compare
numerically; if comp matters and isn't clearly stated, it's an unknown.

## Output
Return BOTH a short human summary AND this object (used by job-search-run when evaluating in batch):

```json
{ "relevant": true, "match": "strong", "reasoning": "…",
  "dealbreakers_hit": [], "unknowns": ["compensation not stated"], "needs_human_check": false }
```
`match` is `null` when `relevant` is false. Bands and vocabulary are defined in `references/conventions.md`.

## Consistency
Judge dealbreakers before alignment; cite evidence; prefer "unknown" over guessing. When unsure between two
bands, pick the lower and say why. Store the reasoning so a human can audit why something was called a match.
