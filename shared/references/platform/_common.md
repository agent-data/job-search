# Platform adapters — shared common boilerplate

This is a **shared partial, not a harness adapter**: the host-neutral boilerplate that was otherwise
repeated near-verbatim across every `shared/references/platform/<host>.md` adapter. Each adapter keeps its
12 canonical `## ` sections and its genuinely host-specific delta, and points here for the common rule — so
there is one home to edit instead of eight to hand-sync (AAS-FORM-04). The leading `_` marks this as a
partial: the platform validator treats only the non-underscore files under `platform/` as adapters.

Nothing here is host-specific. Anything that varies by host — the headless command, whether the exit code
is trustworthy, the concrete tool name, the attention-pull alert surface — stays inline in that host's
adapter.

## Written record

Every harness surfaces a run outcome through the **written record** — the durable contract the home view
reads. The record is **primary on every harness**; a harness's exit-code behavior is an *add-on* that its
adapter's **Headless invocation** states, never a replacement. On a blocked run, write all three channels
before the run stops:

- the **blocked run record** (`runs/<run_id>.json` with `run_health:"blocked"` + the named error, written
  before the run exits),
- the **blocked digest** (`reports/<date>-digest.md` with the named error's cause + fix as the body),
- the **home view** the next time the user opens the **job-search** skill (it reads `run_health` from the
  newest `runs/<id>.json`).

## Whole-file write

For structured-state files (the registry `config.json`, the workspace `config.yaml`), read the current
file first, apply the change to the parsed object, and write the **whole file back atomically** — never a
partial, redirected, or streamed write that can truncate or interleave a structured-state file. Where the
host has no guaranteed-atomic whole-file write tool, write to a temp file then `mv` it into place. The
concrete write tool for each host is in that adapter's **Tool map** / **Whole-file write**. Appending one
immutable line to the event log (`jobs.jsonl`) stays a legitimate shell `>>` append (a heredoc keeps
quoting safe).

## Block-alert channel

The durable guarantee is two file-backed channels (the blocked digest + the home-view run record) — both
plain file writes that survive regardless of any alert surface. An attention-pull alert is *additional* and
capability-gated by the user's on-block notify knob (`notify.desktop_notify_on_block`); whether this host
exposes such a surface is stated in that host's adapter. If no attention-pull channel is available or
confirmed, skip it silently — the two file channels still carry the failure.

## agent-data auth (harness-neutral)

On every non-Claude harness, authenticate the same way. `agent-data init` has **no per-harness flag for
this host** (its selectors are `--claude-code|--open-claw|--hermes|--nano-claw`), so use the harness-neutral
path — it sets the key without installing a harness-specific discovery skill, which job-search does not
need:

```
agent-data init --api-key <KEY> -y     # then: agent-data whoami  → api_key_set:true
```

**Do not** use `--claude-code` on a non-Claude harness — that flag drops a loose agent-data discovery skill
into `~/.claude/skills/` that can shadow or duplicate the plugin skill. The `--api-key`-only path is the
verified workaround for all non-Claude harnesses. The agent-data CLI must be on `PATH` inside the host's
execution environment and its outbound network egress to the agent-data endpoint permitted.
