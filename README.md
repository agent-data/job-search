# Job Search

Job Search is a plugin that turns your coding agent into a job search assistant. Describe what you want, and the agent pulls fresh job postings, judges each against your preferences, and generates a ranked digest of the matches.

<img width="3182" height="2160" alt="job-search-demo-screenshot" src="https://github.com/user-attachments/assets/a3c45a7e-6a93-4afa-86f0-f522c8f8d53c" />

## Quickstart

- **Set your `agent-data` API key.** Grab one at [agent-data.motie.dev](https://agent-data.motie.dev) (Profile → API Key), then export it:

  ```bash
  export AGENT_DATA_API_KEY=mtk_…
  ```

- Give your agent Job Search: [Claude Code](#claude-code) · [Codex](#codex) · [Cursor](#cursor) · [opencode](#opencode) · [Gemini CLI](#gemini-cli) · [GitHub Copilot CLI](#github-copilot-cli) · [Factory Droid](#factory-droid) · [Pi](#pi).

## How it works

1. Install Job Search for your coding agent and start it (in Claude Code, run `/job-search`).
2. The agent asks a few questions to understand the roles you're interested in and saves your preferences locally.
3. It pulls live job postings, compares each against your preferences, and generates a digest with only the postings that are relevant.
4. It can also run your search on a schedule (e.g., daily) to surface new matches over time.

See an example digest in [`examples/sample-digest.md`](examples/sample-digest.md).

## What's inside

### Skills Library

- **job-search** — the front door: onboarding, status, and your home view.
- **job-preference-interview** — builds your plain-English preferences brief.
- **job-search-run** — one headless search pass; this is what the schedule runs.
- **evaluate-job-fit** — judges a single posting you paste in.
- **job-search-agent** — the operator manual the agent reaches for to configure, extend, or troubleshoot the system.

## Installation

Installation differs by harness. If you use more than one, install Job Search separately for each one.

### Claude Code

Register our marketplace, then install:

```
/plugin marketplace add agent-data/job-search
/plugin install job-search@agent-data
```

Then run `/job-search` to start.

### Codex

Register our marketplace, install the plugin, and launch Codex:

```bash
# Run in the normal shell
codex plugin marketplace add agent-data/job-search
codex plugin add job-search@agent-data

# Then launch or restart Codex
codex
```

Then run `$job-search` to start.

### Cursor

Clone the repo and open it in Cursor — it loads the bundled skills from the repo's `.cursor-plugin/` manifest:

```bash
git clone https://github.com/agent-data/job-search
```

Then tell Cursor to run the **job-search** skill.

### opencode

Add Job Search to the `plugin` array in your `opencode.json` (global or project-level):

```json
{
  "plugin": ["job-search@git+https://github.com/agent-data/job-search.git"]
}
```

Restart opencode — it installs the plugin and registers the skills. Details and troubleshooting: [`.opencode/INSTALL.md`](.opencode/INSTALL.md). (Or run from a local clone: `cd /path/to/job-search && opencode`.)

Then tell opencode to run the **job-search** skill.

### Gemini CLI

Install the extension straight from git:

```bash
gemini extensions install https://github.com/agent-data/job-search
```

Update later with `gemini extensions update job-search`.

Then tell Gemini to run the **job-search** skill.

### GitHub Copilot CLI

Register our marketplace, then install:

```bash
copilot plugin marketplace add agent-data/job-search
copilot plugin install job-search@agent-data
```

Then tell Copilot to run the **job-search** skill.

### Factory Droid

Register our marketplace, then install:

```bash
droid plugin marketplace add https://github.com/agent-data/job-search
droid plugin install job-search@agent-data
```

Then tell Droid to run the **job-search** skill.

### Pi

Install from git:

```bash
pi install git:github.com/agent-data/job-search
```

For an editable/development install, point Pi at a local clone: `pi -e /path/to/job-search`.

Then tell Pi to run the **job-search** skill.

## Contributing

Building on or exploring the repo with an AI agent? Start at [AGENTS.md](AGENTS.md), the map of the architecture, design beliefs, and plans — including how one `skills/` tree runs across every supported agent. See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev workflow and [TESTING.md](TESTING.md) for the test harness.

## License

MIT — see [`LICENSE`](LICENSE).
