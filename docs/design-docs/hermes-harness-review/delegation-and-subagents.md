---
title: Hermes harness review — delegation & subagents
status: current
verified: partial
last_reviewed: 2026-06-30
code_refs: [shared/references/platform/hermes.md, docs/design-docs/2026-06-30-hermes-job-search-concierge.md, docs/exec-plans/active/2026-06-30-hermes-concierge-layer.md, docs/design-docs/2026-06-29-hermes-native-plugin.md]
---
# Hermes harness review — delegation & subagents

> **Fact-check caveat.** A later verification pass overturned this doc's central conclusion: top-level
> `delegate_task` is **background/async by default** (backed by `tools/async_delegation.py`), **not**
> inline/blocking as stated below — so the adapter's background PIN should be *kept*, not retired. Read
> the [Corrections log](overview.md#corrections-log) before acting on anything here.

How Hermes spawns subagents (the `delegate_task` tool), and what its concurrency cap, depth limit,
model inheritance, and **inline/blocking** result delivery mean for the concierge's first-batch
calibration step. This is the topic the adapter still carries an open PIN on, so it is the one most
likely to change a design assumption.

Hermes source links below pin to commit `f98b5d0` of `NousResearch/hermes-agent` so the line anchors
stay valid as `main` drifts. They were read at that commit; this doc is source-cited, **not** verified
against a running Hermes (`verified: partial`).

## What Hermes provides

The subagent-dispatch tool is registered as **`delegate_task`** — the OpenAI function-calling schema
name and the registry name are both that literal
([`tools/delegate_tool.py#L2352`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/tools/delegate_tool.py#L2352),
registry at `#L2515`). It has two call modes:

- **single** — `delegate_task(goal=…, context=…, toolsets=…)`; the single goal is normalised into a
  one-task list internally.
- **batch** — `delegate_task(tasks=[…])`; when `tasks` is present the top-level `goal/context/toolsets`
  are ignored ([`#L2472`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/tools/delegate_tool.py#L2472)).

Each task object:

| Field | Required | Notes |
|---|---|---|
| `goal` | **yes** | the only required field |
| `context` | no | the child sees *only* `goal` + `context` (see fresh-agent isolation) |
| `toolsets` | no | intersected with the parent's enabled toolsets; omitted → child inherits the parent's set |
| `role` | no | `leaf` (default) or `orchestrator` |
| `acp_command` / `acp_args` | no | ACP passthrough; unused by job-search |

**Synchronous / inline / blocking — the load-bearing fact.** `delegate_task` runs inside the parent's
current turn. A single task runs directly; a batch runs inside a `with ThreadPoolExecutor(...)` block
([`#L1985`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/tools/delegate_tool.py#L1985))
that blocks until **every** future finishes, then results are sorted by `task_index`
([`#L2097`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/tools/delegate_tool.py#L2097))
and returned together as one array, one entry per task. The schema says so verbatim: "delegate_task
runs SYNCHRONOUSLY" ([`#L2372`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/tools/delegate_tool.py#L2372))
and "Results are always returned as an array, one entry per task" (`#L2401`). The docs agree —
"It blocks the parent until every child finishes … It is **not** a background job queue"
([`delegation.md#L225`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/website/docs/user-guide/features/delegation.md#L225);
`delegation-patterns.md#L28`, `#L241` call it "synchronous"). **There is no background/async delegation
path.** Durable work that must outlive the turn uses the *separate* `cronjob` or
`terminal(background=True, notify_on_complete=True)` tools, which the docs recommend instead of
`delegate_task` for that case.

What a parent *sees* during a delegation is **in-turn progress streaming**, not deferred delivery: child
thinking/tool-progress is relayed above the spinner via `_build_child_progress_callback`
([`#L647`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/tools/delegate_tool.py#L647)) →
`KawaiiSpinner.print_above` (`#L731`, `#L760`; test `tests/agent/test_subagent_progress.py`) *during*
the blocking call. That stream is the most likely source of an "it might run in the background"
impression — but the results still arrive inline, at the end of the same turn.

Bounds and isolation:

| Property | Value | Source |
|---|---|---|
| Concurrency cap | **3** (`delegation.max_concurrent_children`; env `DELEGATION_MAX_CONCURRENT_CHILDREN`; floor 1, no hard ceiling) | `delegate_tool.py#L127`; `delegation.md#L124` |
| Over-cap batch | **rejected** with a `tool_error` ("Too many tasks: N … max_concurrent_children is M") — **not** truncated, **no** children spawned | `delegate_tool.py#L1899` |
| Depth | **flat, 1** by default (parent depth 0 → child depth 1; a depth-1 child calling `delegate_task` is rejected); clamped to `[1,3]` via `delegation.max_spawn_depth` | `delegate_tool.py#L128`, `#L389` |
| Leaf-blocked tools | a `leaf` child (the default) cannot call `delegate_task`, `clarify`, `memory`, `send_message`, or `execute_code` | `delegate_tool.py#L40`-`L48` |
| Model | child inherits the parent's model (`effective_model = model or parent_agent.model`); the LLM-facing schema exposes **no** per-call `model` param — the only override is config `delegation.model` / `delegation.provider` | `delegate_tool.py#L982`; `delegation.md#L143` |
| Iteration budget | `delegation.max_iterations` default **50**, not model-exposed (a model-supplied value is ignored) | `delegate_tool.py#L476` |
| Isolation | each child is a fresh agent with **zero** knowledge of the parent's conversation; only `goal` + `context` go in, only the child's final summary comes back | schema `#L2378`; `delegation.md` |
| Nesting | only `role='orchestrator'` lets a child delegate further (still no `clarify`/`memory`/`send_message`/`execute_code`); requires `max_spawn_depth >= 2`; global kill-switch `delegation.orchestrator_enabled` | `delegate_tool.py#L221` (patterns doc) |
| Interrupt | on parent interrupt (new message, `/stop`, `/new`) in-flight children are cancelled (`status="interrupted"`) and discarded | `delegation-patterns.md#L241` |

**Source doc-drift on depth (flagged, not a behavior change).** The authoritative runtime value is
`max_spawn_depth = 1` (`MAX_DEPTH = 1` at `#L128`; `_get_max_spawn_depth()` returns 1 at `#L389`;
`delegation-patterns.md#L221` says "default of 1"). Three spots disagree by saying "2" — notably the
`_build_child_agent(..., max_spawn_depth: int = 2)` param default
([`#L539`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/tools/delegate_tool.py#L539)) — but
the runtime guard consults `_get_max_spawn_depth()` (1), so flat-depth-1 governs. [PIN: confirm the
effective depth on a live instance, since the in-source defaults disagree.]

## How the job-search adapter uses it

The adapter's **Concurrent detail reads** section in
[`shared/references/platform/hermes.md`](../../../shared/references/platform/hermes.md) is accurate on
every mechanical point; the source confirms it and resolves its one open PIN.

| Adapter claim | Verdict | Detail |
|---|---|---|
| Fans out via `delegate_task(tasks=[{goal, context, toolsets, role}, …])`, one task per posting | **CONFIRMS** | task-object fields match the schema exactly; the omitted `acp_command`/`acp_args` are harmless |
| Each child is a fresh agent with no parent history → pass full context per task | **CONFIRMS** | children have zero conversation memory; only `goal`+`context` are visible |
| Results return inline, sorted by task index; the call blocks until every child finishes | **CONFIRMS** | `#L2097` sort, `#L1985` blocking executor, `delegation.md#L225` |
| Concurrency defaults to 3; an over-cap batch is rejected (not truncated) → chunk into groups of ≤3 | **CONFIRMS** | `#L127`, `#L1899`; chunking is the correct mitigation |
| Depth is flat (`max_spawn_depth: 1`): a child cannot itself delegate or `clarify` | **CONFIRMS** | `#L128` + leaf-blocked set `#L40`-`L48`; see the depth doc-drift note above |
| `delegate_task` children inherit the parent's model | **CONFIRMS** | `#L982`; no per-call model param exists |
| "leaf subagents also have `clarify` blocked" (Closed-choice section) | **CONFIRMS** | `clarify` is in `DELEGATE_BLOCKED_TOOLS` |
| **PIN:** "one code path suggested top-level delegations may run in the BACKGROUND … Confirm on the live pass; until then the sequential fallback is the safe path" | **CONTRADICTS** | no background path exists; the "code path" is the in-turn progress relay (`#L647`, `#L731`). The PIN can be retired and the line restated as inline/blocking unconditionally |

The one substantive correction: the adapter still hedges that delegations *might* run in the background
and treats its sequential fallback as the safe path "for a strictly in-turn run." The source closes
that — delivery is inline/blocking, full stop. The sequential read-and-judge fallback remains valid, but
only as a **capacity/authorization** fallback (Hermes refuses to spawn, or no slot is free), never
because background delivery is a risk. Nothing in this topic is left UNCONFIRMED against the source; the
adapter's *other* PINs (install flags, exit codes, paths) are out of scope here and unverified.

## Implications for the concierge layer

Assessed against the concierge design doc
([`../2026-06-30-hermes-job-search-concierge.md`](../2026-06-30-hermes-job-search-concierge.md)) and the
exec plan ([`../../exec-plans/active/2026-06-30-hermes-concierge-layer.md`](../../exec-plans/active/2026-06-30-hermes-concierge-layer.md)).
The substrate these subagents serve is the same one described in the
[Hermes-native plugin design](../2026-06-29-hermes-native-plugin.md).

**1. First manual calibration batch — SOUND, and now stronger.** Design step 7 says Hermes "should run
the first batch manually and treat it as calibration," producing "relevant jobs only," "concise
reasoning for each presented match," and "lightweight analytics about the batch"; exec-plan T3 Step 4
restates this. Inline/blocking delivery is exactly what an interactive front door wants: the user is
present and waiting, the turn blocks until every detail read completes, then the concierge computes
analytics and asks for a reaction in the same turn. The resolved (non-background) semantics make the
concurrent batch path the *preferred* one and remove the need for the adapter's over-conservative
"sequential is the safe path" framing — sequential is now purely a capacity fallback.

**2. Concurrency cap is unstated in the calibration step — NEEDS CHANGE (caution).** Neither the design's
step 7 nor exec-plan T3 Step 4 / the Done-when line ("the first manual batch shows relevant jobs plus
lightweight analytics") mentions the cap. If a calibration batch has **>3** promising postings and they
are passed to a *single* `delegate_task(tasks=[…])` call, the **entire call is rejected** with a
`tool_error` and no subagents run — it is not truncated. The mitigation is the adapter's existing
chunk-to-≤3 contract (groups run in sequence, or raise `delegation.max_concurrent_children`). The
worker skill (`job-search-run`) presumably already honors this, but the calibration step in the design
doc and exec plan should state the chunking requirement explicitly so a well-aimed first batch with many
matches does not fail on its most important run.

**3. Interview / preference drafting must stay in the parent turn — SOUND, with a guardrail.** Design
steps 3–5 use `clarify` for true closed choices and ask "one question at a time" during preference
shaping; that works because `clarify` runs in the parent turn. But leaf children have `clarify`,
`memory`, and `send_message` hard-blocked, so the interview and the permissioned memory-draft must
**never** be delegated to a subagent — a child cannot ask the user or write the brief. Keep them in the
main concierge turn; only the read-and-judge detail work belongs in `delegate_task`.

**4. Per-subagent cheap-tier reads are not available — CAUTION on cost framing.** The design's
"lightweight analytics" and any implicit "a cheaper model does the bulk reads" expectation (true on
Claude Code, whose `Task` tool offers per-subagent model selection) does **not** hold on Hermes:
children inherit the parent's model and the schema has no per-task `model`. A cheaper bulk-read tier
requires setting `delegation.model` / `delegation.provider` in config — it cannot be chosen per task by
the skill. Any cost language in the concierge analytics should reflect that detail reads run at the
parent's model/cost unless that config is set; the adapter's `inherit` tier note already says this.

**5. Explainability live re-checks — SOUND.** The design's explainability model says that for
"why didn't we alert on X?" Hermes may "perform a live re-check of the posting or search state"
(step under *Explainability model*; exec-plan T6). A delegated re-check is also inline/blocking and
returns within the turn — appropriate for an interactive answer; no background/deferred delivery is
needed or available. A re-check child is still a leaf, so it must be handed full context up front (it
cannot `clarify` for missing detail).

None of these are blocking. The only change the layer *needs* is making the ≤3 chunking explicit at the
calibration step (item 2); the rest is confirmation plus two guardrails.

## Open questions / must-verify-live

- **Background delivery is resolved against source, not a live run.** The in-repo claim (inline/blocking)
  is solid; the live pass should still confirm no host-specific wrapper or gateway setting re-routes a
  top-level delegation into a later message. [PIN]
- **Effective depth default.** The in-source defaults disagree (1 vs 2; see the doc-drift note); the
  governing `_get_max_spawn_depth()` returns 1, but a live instance should confirm a depth-1 child is in
  fact refused. [PIN] — irrelevant to the default flat job-search path, but it bounds any future nesting.
- **Config-level model override path.** `delegation.model` / `delegation.provider` resolution was
  confirmed in code but not exhaustively traced through every credential branch; verify on a live
  instance if the concierge ever configures a cheaper bulk-read tier. [PIN]
- **No background-delegation CLI surface to verify.** The review brief named four source files that do
  **not** exist in the clone (`tools/async_delegation.py`,
  `tests/cli/test_cli_delegate_background_notice.py`, and two others); their behaviors are covered by
  `tools/delegate_tool.py` + the existing `test_delegate*.py` / `test_subagent_progress.py` tests. There
  is no "background notice" CLI path to confirm because there is no background delegation.
