---
title: Hermes-Native Host — Adapter + Bundled State-Ops Runtime
status: current
verified: partial
last_reviewed: 2026-06-29
code_refs: [shared/references/platform/hermes.md, shared/references/internals.md, shared/references/conventions.md, skills/job-search-agent/SKILL.md, scripts/build.sh, scripts/validate_platforms.py, runtime/hermes_job_search/cli.py]
---
# Hermes-Native Host — Adapter + Bundled State-Ops Runtime

Adds **Hermes** (Nous Research's [`hermes-agent`](https://github.com/nousresearch/hermes-agent)) as a
first-class, Hermes-native host — *additively*, without disturbing the other eight harnesses. The Hermes
path uses Hermes's real primitives (native cron, `delegate_task` fan-out, deliver-to-chat) and moves the
deterministic state operations out of prose-only procedures into a small bundled stdlib-Python runtime.
The contracts themselves are unchanged — they stay pinned in
[`shared/references/internals.md`](../../shared/references/internals.md) and
[`shared/references/conventions.md`](../../shared/references/conventions.md); the runtime is just a second
*executor* of the same contracts, used only on Hermes.

## Decisions

1. **Skills stay harness-neutral.** Hermes-nativeness lives in the adapter
   [`shared/references/platform/hermes.md`](../../shared/references/platform/hermes.md) plus the runtime,
   not in forked skill prose. Every existing harness is untouched.
2. **Runtime = stdlib-only Python via the `terminal` tool** — `python3
   ${HERMES_SKILL_DIR}/scripts/hermes_job_search/cli.py <op>` → one JSON object on stdout. No MCP server,
   no `plugin.yaml`, no new dependencies. (MCP needs the non-stdlib `mcp` SDK; a Hermes plugin needs
   gated executable-tool registration + a gateway restart — both overkill for a CLI the agent shells out
   to. Hermes's own shipped skills, e.g. `arxiv`, bundle a stdlib `scripts/` CLI exactly this way.)
3. **Verification = structural + source-cited.** Every adapter literal is cited against
   `hermes-agent@main` and structurally validated; live end-to-end proof is run by the maintainer on a
   real Hermes install from this branch. Unreproduced literals carry a **PIN** tag.

## Architecture (three layers)

- **Skill layer** — the five skills, harness-neutral, deferring mechanism to the active adapter.
- **Deterministic runtime** — [`runtime/hermes_job_search/`](../../runtime/hermes_job_search/cli.py): a
  stdlib CLI over `discover-workspace`, `read-registry`, `set-active-workspace`, `set-scheduling` /
  `clear-scheduling`, `load-config`, `update-config`, `known-ids`, `append-event`, `fold-state`,
  `write-run-record`, `write-digest`. Adapted from the deleted `osctl.py`/`state.py` (commit `932f89f`)
  with the registry dir corrected to `job-search` and whole-file writes made atomic (`os.replace`).
  Bundled into the three consuming skills' `scripts/` by [`scripts/build.sh`](../../scripts/build.sh) and
  pinned byte-for-byte by [`scripts/validate_platforms.py`](../../scripts/validate_platforms.py)
  (`runtime-bundle`). Judgment never enters it, and `philosophy_guard.py` scans it so it can never emit a
  numeric score.
- **Hermes integration** — `hermes.md` maps the 12 canonical adapter sections to Hermes primitives.

## What stays prompt/LLM-driven vs code-driven

- **Model:** the preference interview, qualitative job-fit judgment (relevant; match
  strong/moderate/weak/null; reasoning/unknowns/dealbreakers), conversational config, troubleshooting.
- **Runtime (Hermes path only):** workspace discovery, registry read/write, config load + surgical
  update, known-id extraction, event append/validation, event-log fold, run-record + digest writing.

## Hermes-native scheduling, parallelism, delivery

- **Scheduling.** Recurring runs use Hermes's native cron (`hermes cron create … --skill job-search-run
  --deliver origin`, or the `cronjob` tool). A scheduled run executes the headless skill in a fresh,
  isolated session, writes the durable local artifacts, and delivers a concise summary back to the
  originating chat. The registry records `scheduling.mechanism: hermes-cron` plus the optional `job_id`
  and `deliver`. (See `hermes.md` → Scheduling / Block-alert channel.)
- **Parallelism.** Promising-posting detail reads fan out via `delegate_task` batch mode — one task per
  posting, each child handed full context (it has no parent history) — chunked into groups of ≤3 to
  respect Hermes's default concurrency cap, with a sequential fallback for the refusal/zero-capacity
  case. One open question (inline vs background top-level delegation) is PIN'd in `hermes.md` for the
  live pass.

## Honest-docs reconciliation

Reintroducing shipped Python for the Hermes path made several KB claims ("nothing ships but markdown",
"no helper script", "zero runtime dependencies") no longer universally true. They are rewritten so: the
native-execution harnesses stay markdown-only and Python-free; the Hermes adapter is the lone exception,
running the identical contracts through the bundled runtime with judgment staying in the model. (Files:
AGENTS.md, ARCHITECTURE.md, TESTING.md, RELIABILITY.md, QUALITY_SCORE.md, core-beliefs.md.) The completed
`2026-06-11-zero-python-*` exec-plan and the 0.3.0 changelog entry are left as historical record.

## Packaging & verification

Ships as a Hermes skill pack (no plugin manifest required). The turnkey "install + verify this branch on
a real Hermes" block lives in `hermes.md` → Packaging & install (and the README Hermes section): clone
the branch, run `./scripts/build.sh`, register the skills (`hermes skills tap add` / `skills.external_dirs`
/ drop into `~/.hermes/skills/`), then `hermes chat -Q -s job-search-run -q "run a job search now"` and
`hermes cron create … --skill job-search-run --deliver origin`.

## Source citations (hermes-agent@main)

Skill/`SKILL.md` format + install: `agent/skill_*.py`, `hermes_cli/skills_hub.py`,
`hermes_cli/subcommands/skills.py`. Cron: `cron/jobs.py`, `cron/scheduler.py`,
`hermes_cli/subcommands/cron.py`, `docs/chronos-managed-cron-contract.md`. Subagents:
`docs/user-guide/features/delegation.md`. Tools: `website/docs/reference/tools-reference.md`. Models:
`hermes_cli/model_catalog.py`, `model_normalize.py`. Identity: `docs/user-guide/features/personality`,
`context-files`. Every adapter literal traces to one of these; the unreproduced ones carry a **PIN** tag
in [`hermes.md`](../../shared/references/platform/hermes.md).
