# COPILOT.md

GitHub Copilot CLI loads this file from the repo root at session start (the `COPILOT_CLI`
session-start hook). Like `CLAUDE.md`, it is a thin redirect to the agnostic instruction map:

Coding agents working on this repo: read **[AGENTS.md](AGENTS.md)** — the entry-point map. It
points to the architecture, the agent-first core beliefs, the design/exec plans, and the runtime
single source of truth in `shared/references/`.

Running the **job-search** skill on Copilot: the pack installs via the shared `.claude-plugin/`
manifest; the skills use platform-neutral action vocabulary and the pinned contracts in
`shared/references/`. Copilot resolves its own tools, scheduler, headless invocation, and model at
run time by self-selection — there is no per-host adapter file.
