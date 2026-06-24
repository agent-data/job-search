# Parallel by default — concurrency & delegating to subagents

Independent work runs concurrently, not in sequence. When subtasks don't depend on each other — reading ten
different documents, judging ten postings, running several searches — dispatch them **at once, in a single
batch** of subagents, never a one-at-a-time loop. Time-to-value is a product feature, and parallelism is how
you cut wall-clock when the work is genuinely independent. Isolating each subtask in its own subagent also
keeps the primary context clean and lets a faster, cheaper model do the bulk work.

The bar is *mutual independence*: if subtask B needs subtask A's result, they're sequential — don't force them
parallel. If they don't, running them serially is wasted wall-clock.

Whether an isolated-context concurrent subagent primitive is available, any concurrency cap, and the
**mandatory sequential fallback** (read and judge each item one at a time — never fabricate a dispatch) live in
the active platform's adapter → **Concurrent detail reads**. Read your adapter before dispatching; a host with
no concurrent primitive degrades gracefully through that fallback.

If the host has a concurrent primitive but refuses more subagents because its thread/slot limit is reached,
that is **backpressure**, not a run-health error. Keep the already-dispatched work, wait for a completed subagent,
close it promptly, and dispatch the next queued item. Continue in rolling batches until every queued item has
either a detail judgment or the adapter's sequential fallback has handled it. Do not mark the run `partial`
only because capacity forced batching.

## Briefing a subagent

A fresh subagent starts with **zero context** — it hasn't seen this conversation, what you've tried, or why the
task matters. Brief it like a sharp colleague who just walked into the room: enough that it can make judgment
calls, not a terse command (terse command-style prompts produce shallow, generic work). The dispatch verb —
how you actually invoke a subagent on your platform — is in the active platform's adapter → **Concurrent detail
reads**. The briefing contract below is harness-agnostic. Each brief carries:

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
