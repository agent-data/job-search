# Job Search

Job Search is a plugin that turns Claude Code into a job search assistant. Describe what you want, and Claude pulls fresh job postings, judges each against your preferences, and generates a ranked digest of the matches.

<img width="3182" height="2160" alt="job-search-demo-screenshot" src="https://github.com/user-attachments/assets/a3c45a7e-6a93-4afa-86f0-f522c8f8d53c" />

## How it works

1. Install the plugin and run `/job-search`
2. Claude will ask a few questions to understand the roles you’re interested in and save your preferences locally.
3. Claude will then pull live job postings, compare posts against your preferences, and generate a digest with only the posts that are relevant.
4. *Optionally* Claude can also run your search on a schedule (e.g., daily) to surface new posts matching your preferences over time.

See an example digest in [`examples/sample-digest.md`](examples/sample-digest.md).

## Requirements

- **[Claude Code](https://claude.com/claude-code)**
- **The `agent-data` CLI** — the job-data source. Generate an API key at [agent-data.motie.dev](https://agent-data.motie.dev) (Profile → API Key), then `export AGENT_DATA_API_KEY=mtk_…` (or save it to `~/.agent-data/config.json`) and verify with `agent-data whoami`. 

  *Note: agent-data currently provides job postings from the following sources: LinkedIn Jobs.*

## Quick start

1. **Set your `agent-data` API key.** Grab one at [agent-data.motie.dev](https://agent-data.motie.dev) (Profile → API Key), then export it:
   ```bash
   export AGENT_DATA_API_KEY=mtk_…
   ```
2. **Launch Claude Code then register the local clone as a marketplace:**
   ```
   /plugin marketplace add /path/to/job-search-os
   /plugin install job-search-os@agent-data
   ```
3. **Kick off your job search.** Run `/job-search`

## What's inside

### Skills Library

- **job-search** — the front door: onboarding, status, and your home view.
- **job-preference-interview** — builds your plain-English preferences brief.
- **job-search-run** — one headless search pass; this is what the schedule runs.
- **evaluate-job-fit** — judges a single posting you paste in.
- **job-search-agent** — the operator manual Claude reaches for to configure, extend, or troubleshoot the system.

## Installation

Clone the repo, then pick an install path.

**Persistent (recommended).** Register the local clone as a marketplace, then install:

```
/plugin marketplace add /path/to/job-search-os
/plugin install job-search-os@agent-data
```

**One session, no install.** Launch Claude Code with the `--plugin-dir` launch flag:

```bash
claude --plugin-dir /path/to/job-search-os
```

After installing, run the front door slash command, or just say what you want:

```
/job-search-os:job-search
```

## Contributing

Building on or exploring the repo with an AI agent? Start at [AGENTS.md](AGENTS.md), the map of the architecture, design beliefs, and plans. See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev workflow and [TESTING.md](TESTING.md) for the test harness.

## License

MIT — see [`LICENSE`](LICENSE).
