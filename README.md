# Job Search

Job Search is a plugin that turns your coding agent into a job search assistant. Describe what you want, and the agent pulls fresh job postings, judges each against your preferences, and generates a ranked digest of the matches.

<img width="3182" height="2160" alt="job-search-demo-screenshot" src="https://github.com/user-attachments/assets/a3c45a7e-6a93-4afa-86f0-f522c8f8d53c" />

## How it works

1. Install the plugin and run `/job-search`
2. The agent asks a few questions to understand the roles you’re interested in and saves your preferences locally.
3. The agent then pulls live job postings, compares posts against your preferences, and generates a digest with only the posts that are relevant.
4. *Optionally* the agent can also run your search on a schedule (e.g., daily) to surface new posts matching your preferences over time.

See an example digest in [`examples/sample-digest.md`](examples/sample-digest.md).

## Requirements

- **A supported coding agent.** **[Claude Code](https://claude.com/claude-code)** is verified and is the quickstart below; **Codex** is live-proven. Other harnesses (Cursor, opencode, Gemini CLI, Copilot CLI, Factory Droid, Pi) ship adapters + manifests and are structurally validated — pin on install. See **[Running on other harnesses](#running-on-other-harnesses)**.
- **The `agent-data` CLI** — the job-data source (harness-independent). Generate an API key at [agent-data.motie.dev](https://agent-data.motie.dev) (Profile → API Key), then `export AGENT_DATA_API_KEY=mtk_…` (or save it to `~/.agent-data/config.json`) and verify with `agent-data whoami`. 

  *Note: agent-data currently provides job postings from the following sources: LinkedIn Jobs.*

## Quick start — Claude Code (the verified path)

1. **Set your `agent-data` API key** (harness-independent). Grab one at [agent-data.motie.dev](https://agent-data.motie.dev) (Profile → API Key), then export it:
   ```bash
   export AGENT_DATA_API_KEY=mtk_…
   ```
2. **Launch Claude Code then register the local clone as a marketplace:**
   ```
   /plugin marketplace add /path/to/job-search
   /plugin install job-search@agent-data
   ```
3. **Kick off your job search.** Run `/job-search`

On other harnesses the API-key step is the same; the install step differs — see **[Running on other harnesses](#running-on-other-harnesses)**.

## What's inside

### Skills Library

- **job-search** — the front door: onboarding, status, and your home view.
- **job-preference-interview** — builds your plain-English preferences brief.
- **job-search-run** — one headless search pass; this is what the schedule runs.
- **evaluate-job-fit** — judges a single posting you paste in.
- **job-search-agent** — the operator manual the agent reaches for to configure, extend, or troubleshoot the system.

## Installation — Claude Code (the verified path)

Clone the repo, then pick an install path.

**Persistent (recommended).** Register the local clone as a marketplace, then install:

```
/plugin marketplace add /path/to/job-search
/plugin install job-search@agent-data
```

**One session, no install.** Launch Claude Code with the `--plugin-dir` launch flag:

```bash
claude --plugin-dir /path/to/job-search
```

After installing, run the front door slash command, or just say what you want:

```
/job-search:job-search
```

## Running on other harnesses

The plugin is harness-agnostic by design. **One `skills/` tree** is the whole product; each host agent reads it **in place** through a per-harness distribution manifest that already ships in the repo, and the agent **self-selects** its platform adapter — `shared/references/platform/<name>.md` — which carries that harness's literals (tool map, scheduling, headless invocation, model tiers).

Manifests that ship today:

| Harness | Manifest(s) that ship |
|---|---|
| Claude Code | `.claude-plugin/` (`plugin.json` + `marketplace.json`) |
| Codex | `.codex-plugin/plugin.json` |
| Cursor | `.cursor-plugin/plugin.json` |
| opencode | `package.json` + `.opencode/plugins/job-search.js` |
| Gemini CLI | `gemini-extension.json` + `GEMINI.md` |
| Copilot CLI | reuses `.claude-plugin/` |
| Factory Droid | `.factory-plugin/plugin.json` |
| Pi | the `pi` block in `package.json` |

**Verification status — read before relying on a harness.** Only **Claude Code** is fully verified (the quickstart above) and **Codex** is live-proven. The other six (Cursor, opencode, Gemini CLI, Copilot CLI, Factory Droid, Pi) are **structurally validated and pin-on-install** — their adapters and manifests exist and pass structural checks, but they have not been run live. Before relying on one, confirm the exact install command in your harness's own docs and in its platform adapter (`shared/references/platform/<name>.md`) rather than assuming a command that looks right.

For the architecture behind the adapter layer and the single-source-of-truth `shared/references/` tree, see [AGENTS.md](AGENTS.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

## Contributing

Building on or exploring the repo with an AI agent? Start at [AGENTS.md](AGENTS.md), the map of the architecture, design beliefs, and plans. See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev workflow and [TESTING.md](TESTING.md) for the test harness.

## License

MIT — see [`LICENSE`](LICENSE).
