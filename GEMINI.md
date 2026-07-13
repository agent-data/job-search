# job-search — Gemini CLI entry file

This file is loaded by Gemini CLI as the session context (`contextFileName: GEMINI.md` in
`gemini-extension.json`). It isolates Gemini to this file without touching `AGENTS.md`, which
remains a plain repo file shared by all harnesses.

## Skill

@skills/job-search/SKILL.md

## Tool map

The job-search skills use platform-neutral action vocabulary ("read a file", "ask a closed
choice", "dispatch a subagent"). On Gemini CLI those actions resolve to Gemini's native tools,
which Gemini binds by self-selection at run time — there is no per-host adapter file. The pinned
contracts and all runtime detail (scheduling, headless invocation, agent-data setup) live once in
`shared/references/`; Gemini resolves each action, its scheduler, and its model against its own
capabilities, then verifies the result rather than looking up a host-specific recipe.

## Repo orientation

For codebase structure, architecture, and contribution guidelines, see `AGENTS.md`.
