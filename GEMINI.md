# job-search — Gemini CLI entry file

This file is loaded by Gemini CLI as the session context (`contextFileName: GEMINI.md` in
`gemini-extension.json`). It isolates Gemini to this file without touching `AGENTS.md`, which
remains a plain repo file shared by all harnesses.

## Skill

@skills/job-search/SKILL.md

## Tool map

The job-search skills use platform-neutral action vocabulary ("read a file", "ask a closed
choice", "dispatch a subagent"). On Gemini CLI those actions resolve to Gemini's native tools.
The mapping — and all Gemini-specific runtime details (scheduling, headless invocation, model
tiers, agent-data setup) — lives in the platform adapter:

`shared/references/platform/gemini.md`

> **Reconciliation note — no separate `references/gemini-tools.md`.**
> The platform adapter pattern (`shared/references/platform/<name>.md`) serves as the single
> tool-map reference for each harness. A standalone `references/gemini-tools.md` is not
> authored because `shared/references/platform/gemini.md` already carries the full tool table
> and all runtime detail. `GEMINI.md` points directly at the platform adapter; no intermediate
> file is needed.

## Repo orientation

For codebase structure, architecture, and contribution guidelines, see `AGENTS.md`.
