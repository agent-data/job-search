# Job Search

Job Search is a plugin that turns Claude Code into a job search assistant. Describe what you want, and Claude pulls fresh job postings, judges each against your preferences, and generates a ranked digest of the matches.

## How it works

Run `/job-search` and Claude asks what you're after: the role, the level, your must-haves, dealbreakers, and where you want to work. Claude stores your preferences then runs a live search, comparing each job posting against those preferences. Claude filters out irrelevant postings and generates a digest with the postings worth your attention, along with its reasoning for each. Finally, it offers to run your search on a schedule, surfacing new postings only when they match your preferences.

See an example digest in [`examples/sample-digest.md`](examples/sample-digest.md).

## Requirements

- **[Claude Code](https://claude.com/claude-code)**
- **The `agent-data` CLI** — the job-data source. Generate an API key at [agent-data.motie.dev](https://agent-data.motie.dev) (Profile → API Key), then `export AGENT_DATA_API_KEY=mtk_…` (or save it to `~/.agent-data/config.json`) and verify with `agent-data whoami`. *Note: agent-data currently provides job postings from the following sources: LinkedIn Jobs.*

## Quick start

1. **Set your `agent-data` API key.** Grab one at [agent-data.motie.dev](https://agent-data.motie.dev) (Profile → API Key), then export it:
   ```bash
   export AGENT_DATA_API_KEY=mtk_…
   ```
2. **Launch Claude Code then register the local clone as a marketplace:**
   ```bash
   claude
   ```
   ```
  /plugin marketplace add /path/to/job-search-os
  /plugin install job-search-os@agent-data
  ```
3. **Kick off your job search.** Run `/job-search`

## What's inside

Five skills, each triggered by what you say:

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

**One session, no install.** `--plugin-dir` is a launch flag, so run it in your shell, then run `/job-search-os:job-search` in the session it opens:

```bash
claude --plugin-dir /path/to/job-search-os
```

<details>
<summary><strong>No plugin system? Install loose skills.</strong></summary>

Build the bundled copies, then symlink the skills into `~/.claude/skills/`:

```bash
cd /path/to/job-search-os
./scripts/build.sh
mkdir -p ~/.claude/skills
for s in job-search job-search-run evaluate-job-fit job-preference-interview job-search-agent; do
  ln -s "$PWD/skills/$s" ~/.claude/skills/$s
done
```

Re-run `./scripts/build.sh` after pulling updates. In this mode the skills are invocable bare: `/job-search`, or just say "set up job search."

</details>

After installing, run the front door, or just say what you want:

```
/job-search-os:job-search
```

Natural language works in every mode: "set up job search," "find me jobs," "check my job search." A one-step marketplace install is coming once the plugin is published.

## Contributing

Building on or exploring the repo with an AI agent? Start at [AGENTS.md](AGENTS.md), the map of the architecture, design beliefs, and plans. See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev workflow and [TESTING.md](TESTING.md) for the test harness.

## License

MIT — see [`LICENSE`](LICENSE).