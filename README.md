# Job Search

Job Search is a plugin that turns Claude Code into a job search assistant. Describe what you want, and Claude pulls fresh job postings, judges each against your preferences, and generates a ranked digest of the matches.

<img width="704" height="480" alt="job-search-demo" src="https://github.com/user-attachments/assets/237647be-41c1-46f8-8b14-69e6d804f9d6" />

## How it works

1. Run `/job-search` and Claude asks what you're after: the role, the level, your must-haves, dealbreakers, and where you want to work.
2. Claude stores your preferences then runs a live search, comparing each job posting against those preferences.
3. Claude filters out irrelevant postings and generates a digest with the postings worth your attention, along with its reasoning for each. 
4. Finally, Claude offers to run your search on a schedule, surfacing new postings only when they match your preferences.

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

**One session, no install.** 

Launch Claude Code with the `--plugin-dir` launch flag:

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
