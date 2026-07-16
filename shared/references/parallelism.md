# Parallel by default — concurrency & delegating to subagents

Independent work runs concurrently, not in sequence. When subtasks don't depend on each other — reading ten
different documents, judging ten postings, running several searches — dispatch them **at once, in a single
batch** of subagents, never a one-at-a-time loop. Time-to-value is a product feature, and parallelism is how
you cut wall-clock when the work is genuinely independent. Isolating each subtask in its own subagent also
keeps the primary context clean. For posting-detail judgments, interactive setup has already selected and
persisted the exact model binding described in `internals.md`; runtime dispatch does not select a tier or
reinterpret that decision.

The bar is *mutual independence*: if subtask B needs subtask A's result, they're sequential — don't force them
parallel. If they don't, running them serially is wasted wall-clock.

Use your host's subagent primitive if it has one. If it has none, or no slot is free, degrade gracefully to
the sequential fallback: read and judge each item one at a time — never fabricate a dispatch.

If your host requires explicit user approval before it will use subagents for job-search detail reads, get
that approval once before fanning out; otherwise fan out by default. Treat missing approval as a real boundary
on an approval-gating host, not as implied permission: the interactive front door may ask and store the answer
in `search.parallel_detail_reads`, while a headless runner reads that stored preference. How an **unset**
preference resolves depends on your host: one that gates subagents behind approval reads sequentially until the
user approves, but one that needs no approval keeps the parallel-by-default fan-out above. An explicit `false`
is always a user opt-out to sequential reads; `true` is always the parallel fan-out where the primitive
exists.

## Posting-detail model binding

Configuration time owns selection. Setup chooses the least-powerful available model that can perform fit
judgment well unless the user selects another exact available model. If the host cannot assign a separate
worker model, setup persists the exact primary model as `search.detail_model` and configures sequential
judgments. Those are setup decisions, never headless runtime heuristics.

<!-- exact-model-contract:runtime-detail-dispatch -->
For each posting-detail judgment, use the exact `search.detail_model`.
<!-- /exact-model-contract:runtime-detail-dispatch -->

The exact value is required at dispatch. Never omit it, reinterpret it as a tier, or silently substitute
another model. A sequential fallback is valid only when it still executes that exact configured model; setup
uses the exact primary binding when the host has no separate-worker-model capability.

If the host has a concurrent primitive but refuses more subagents because its thread/slot limit is reached,
that is **backpressure**, not a run-health error. Keep the already-dispatched work, wait for a completed subagent,
close it promptly, and dispatch the next queued item. Continue in rolling batches until every queued item has
either a detail judgment or the sequential fallback has handled it. Do not mark the run `partial`
only because capacity forced batching.

## Briefing a subagent

A fresh subagent starts with **zero context** — it hasn't seen this conversation, what you've tried, or why the
task matters. Brief it like a sharp colleague who just walked into the room: enough that it can make judgment
calls, not a terse command (terse command-style prompts produce shallow, generic work). The briefing contract
below is harness-agnostic. Each brief carries:

- **The goal, and why it matters** — what you're accomplishing and what its output feeds into.
- **What you already know or ruled out** — so the subagent doesn't re-derive the obvious or repeat a dead end.
- **Instructions by reference** — where a rubric, skill, or contract already defines *how*, point to it; don't
  re-type it. The referenced source is the single source of truth; a copy in the prompt only drifts.
- **The open questions, not a step list** — a *lookup* gets the exact command; an *investigation* gets the
  question. Prescribed micro-steps become dead weight the moment the premise is wrong — let the subagent follow
  the evidence where it leads.
- **A tight return** — say exactly what to send back (a structured object, or e.g. "report in under 200 words"),
  so nothing extraneous comes back to wade through.

**Never delegate the understanding you owe.** "Based on your findings, fix it" or "decide if it fits" punts
your synthesis onto the subagent. A good brief *proves you did the thinking* — it names what you found and the
one or two things still to resolve. Frame those as a provisional read + an open question, **never a verdict**:
asserting the answer ("this is the bug", "this is a strong match") anchors the subagent instead of letting the
evidence decide.

## The delegated return channel

A subagent that judges a delegated item returns its result as the agreed structured object **as plain text in
its final message** — that final-message text *is* the return, and the dispatcher (e.g. `job-search-run`
consuming a per-posting fit verdict) reads the object straight from it. Never write the judgment to a
side-channel `.md`/report file; never wrap it in a fenced code block (the JSON fence a cheaper model
reflexively adds); never precede it with a confirmation or politeness line ("Done.", "Here's the judgment").
The object is the whole message, nothing else. This is the single home for the delegated return contract — the
runner's detail-subagent brief and the judge's "used by job-search-run" batch path point here rather than
restating it.
