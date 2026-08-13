# job-search — Gemini CLI entry file

This file is loaded by Gemini CLI as the session context (`contextFileName: GEMINI.md` in
`gemini-extension.json`). It isolates Gemini to this file without touching `AGENTS.md`, which
remains a plain repo file shared by all harnesses.

## Skill

@skills/job-search/SKILL.md

## Tool map

The job-search skills use platform-neutral action vocabulary ("read a file", "ask a closed
choice", "dispatch a subagent"). On Gemini CLI those actions resolve to Gemini's native tools,
which Gemini binds by self-selection at run time — there is no per-harness adapter file. The pinned
contracts and all runtime detail (scheduling, headless invocation, agent-data setup) live once in two
skills of their own. Gemini CLI has no skill-invocation verb, so read them as the files
`skills/job-search-runbook/SKILL.md` (the workspace, what each file in it holds, how one run opens and
closes) and `skills/agent-data-reference/SKILL.md` (the CLI, the per-source quirks, retries, what a
call costs), and read a sibling skill the same way, at `skills/<name>/SKILL.md`. Gemini resolves each
action, its scheduler, and its model against its own capabilities, then verifies the result rather
than looking up a harness-specific recipe.

## Repo orientation

For codebase structure, architecture, and contribution guidelines, see `AGENTS.md`.
