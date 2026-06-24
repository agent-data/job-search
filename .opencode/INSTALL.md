# Installing Job Search for opencode

## Prerequisites

- [opencode](https://opencode.ai) installed
- Your `agent-data` API key set (see the README's Installation step 1)

## Installation

Add Job Search to the `plugin` array in your `opencode.json` (global or project-level):

```json
{
  "plugin": ["job-search@git+https://github.com/agent-data/job-search.git"]
}
```

Restart opencode. The plugin installs through opencode's plugin manager and registers the
Job Search skills.

Verify by asking opencode to run the **job-search** skill.

opencode uses its own plugin install. If you also use Claude Code, Codex, or another harness,
install Job Search separately for each one.

## Running from a local clone instead

If you'd rather not use the git-backed package, clone the repo and run opencode from inside it —
the bundled plugin (`.opencode/plugins/job-search.js`) registers the skills:

```bash
git clone https://github.com/agent-data/job-search
cd job-search && opencode
```

## Updating

opencode installs Job Search through a git-backed package spec. Some opencode and Bun versions
pin the resolved git dependency in a lockfile or cache, so a restart may not pick up the newest
commit. If updates don't appear, clear opencode's package cache or reinstall the plugin.

To pin a specific revision, append a ref (a branch or commit SHA) to the spec:

```json
{
  "plugin": ["job-search@git+https://github.com/agent-data/job-search.git#main"]
}
```

## Troubleshooting

**Plugin not loading**

1. Check logs: `opencode run --print-logs "hello" 2>&1 | grep -i job-search`
2. Verify the plugin line in your `opencode.json`
3. Make sure you're on a recent version of opencode

**Skills not found**

1. Ask opencode to list its skills
2. Confirm the plugin is loading (see above)

## Getting help

- Issues: https://github.com/agent-data/job-search/issues
- Repository: https://github.com/agent-data/job-search
