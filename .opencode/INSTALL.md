# Installing Job Search for opencode

## Prerequisites

- [opencode](https://opencode.ai) installed

Job Search checks for the `agent-data` CLI and authentication during onboarding. You do not need to
configure either one before installing the plugin.

## Installation

Add Job Search to the `plugin` array in one of these files:

- `~/.config/opencode/opencode.json` to make it available in every project
- `opencode.json` in a project root to make it available only in that project

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["job-search@git+https://github.com/agent-data/job-search.git"]
}
```

If the file already contains plugins, add the Job Search entry to its existing `plugin` array instead of
replacing the array.

Restart OpenCode. OpenCode passes the git package specification to Bun, installs the whole repository in
its package cache, and loads the package entry point. The plugin then registers the bundled `skills/`
directory; keeping the whole repository together allows each skill to resolve `shared/references/`.

Start with:

> **Set up my job search.**

Installation succeeded when OpenCode loads the **job-search** skill and begins the `agent-data`
prerequisite check. To inspect plugin loading directly, run:

```bash
opencode run --print-logs "Use the job-search skill to set up my job search."
```

The logs must not contain `failed to load plugin` or `Plugin export is not a function`.

opencode uses its own plugin install. If you also use Claude Code, Codex, or another harness,
install Job Search separately for each one.

## Running from a local clone instead

For local development, clone the repository and run OpenCode from its root. OpenCode automatically loads
the bundled `.opencode/plugins/job-search.js` file, which registers that clone's skills:

```bash
git clone https://github.com/agent-data/job-search
cd job-search
opencode
```

## Updating

OpenCode installs package plugins under `~/.cache/opencode/packages/`. Bun may reuse a cached git
resolution, so restarting OpenCode does not guarantee that a moving branch has updated. To force a
fresh install, delete the package's directory under `~/.cache/opencode/packages/` and restart
OpenCode.

For reproducible installs, append a commit SHA to the specification and change that SHA when you want to
upgrade:

```json
{
  "plugin": ["job-search@git+https://github.com/agent-data/job-search.git#<commit-sha>"]
}
```

## Troubleshooting

**Plugin not loading**

1. Check logs: `opencode run --print-logs "hello"`
2. Verify the plugin line in your `opencode.json`
3. Look for `failed to load plugin` and the accompanying error
4. Confirm the configured revision exists in the repository
5. If the plugin was first installed before the fix you need, delete its directory under
   `~/.cache/opencode/packages/` and restart OpenCode — Bun reuses the cached git resolution
6. Make sure you are using a recent version of OpenCode

**Skills not found**

1. Ask OpenCode to list its skills
2. Confirm the plugin is loading (see above)
3. Confirm **job-search**, **job-search-run**, **job-preference-interview**, **evaluate-job-fit**, and
   **job-search-agent** are listed

## Getting help

- Issues: https://github.com/agent-data/job-search/issues
- Repository: https://github.com/agent-data/job-search
