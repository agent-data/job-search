# Job Search

Job Search is a plugin that turns your coding agent into a job search assistant. Describe what you want, and the agent pulls fresh job postings, judges each against your preferences, and generates a ranked digest of the matches.

<img width="3182" height="2160" alt="job-search-demo-screenshot" src="https://github.com/user-attachments/assets/a3c45a7e-6a93-4afa-86f0-f522c8f8d53c" />

## Quickstart

Give your agent Job Search: [Claude Code](#claude-code) · [Codex](#codex) · [Cursor](#cursor) · [opencode](#opencode) · [Gemini CLI](#gemini-cli) · [GitHub Copilot CLI](#github-copilot-cli) · [Factory Droid](#factory-droid) · [Pi](#pi).

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

Job Search is one skills library that every supported agent reads from the same local clone. Two steps set up what's shared; then follow the section for your agent.

**1. Set your `agent-data` API key.** `agent-data` is the job-data source (postings currently come from LinkedIn Jobs). Create a key at [agent-data.motie.dev](https://agent-data.motie.dev) (Profile → API Key), then:

```bash
export AGENT_DATA_API_KEY=mtk_…      # or save it to ~/.agent-data/config.json
agent-data whoami                     # confirms api_key_set: true
```

Don't have the CLI yet? `npm install -g agent-data`.

**2. Clone the repo.** Every agent installs from this local clone — `/path/to/job-search` below is wherever you put it.

```bash
git clone https://github.com/agent-data/job-search
```

Now install for your agent.

### Claude Code

Register the local clone as a marketplace, then install:

```
/plugin marketplace add /path/to/job-search
/plugin install job-search@agent-data
```

Or run it for a single session without installing:

```bash
claude --plugin-dir /path/to/job-search
```

### Codex

Copy the skills into your Codex skills directory:

```bash
mkdir -p ~/.agents/skills && cp -r /path/to/job-search/skills/* ~/.agents/skills/
```

### Cursor

Open the cloned repo in Cursor — it loads the bundled skills from the repo's `.cursor-plugin/` manifest.

### opencode

Run opencode from inside the cloned repo. It loads the bundled plugin (`.opencode/plugins/job-search.js`), which registers the Job Search skills:

```bash
cd /path/to/job-search && opencode
```

### Gemini CLI

Install the extension from the local clone:

```bash
gemini extensions install /path/to/job-search
```

Update later with `gemini extensions update job-search`.

### GitHub Copilot CLI

Register the clone as a marketplace, then install:

```bash
copilot plugin marketplace add /path/to/job-search
copilot plugin install job-search@agent-data
```

### Factory Droid

Register the clone as a marketplace, then install:

```bash
droid plugin marketplace add /path/to/job-search
droid plugin install job-search@agent-data
```

### Pi

Install from the local clone:

```bash
pi install /path/to/job-search
```

After installing, start it — in Claude Code run `/job-search`; on any other agent, tell it to run the **job-search** skill.

## Contributing

Building on or exploring the repo with an AI agent? Start at [AGENTS.md](AGENTS.md), the map of the architecture, design beliefs, and plans — including how one `skills/` tree runs across every supported agent. See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev workflow and [TESTING.md](TESTING.md) for the test harness.

## License

MIT — see [`LICENSE`](LICENSE).
