# Job Search

Turn your coding agent into a job-search assistant. Describe what you want in plain English. Job Search finds postings from LinkedIn and ATS platforms like Ashby and Greenhouse, judges each role against your preferences, and writes a filtered digest. Run it on demand or on a schedule.

<img width="3182" height="2160" alt="Job Search digest showing reviewed matches in an agent conversation" src="https://github.com/user-attachments/assets/a3c45a7e-6a93-4afa-86f0-f522c8f8d53c" />

Your preferences, reviewed postings, run logs, and digests stay in `~/.job-search/` by default. The workspace starts with a deny-all `.gitignore`, which keeps those files out of ordinary Git commits. See [Security & Privacy](docs/SECURITY.md) for the threat model and limits.

## Quickstart

1. [Install Job Search](#installation) for your coding agent.
2. Start a conversation with:

   > **Set up my job search. I'm looking for** a senior product-design role, remote in the US, at a mission-driven company.

The agent checks its prerequisites, creates `~/.job-search/`, documents your preferences, and searches live postings. If useful roles are available, it shows the first fully reviewed matches while it continues through the rest.

   > **Checkpoint:** setup worked when the agent summarizes what it understood and either shows a reviewed match or explains why the search returned none. It then writes the complete digest to your local workspace.

A sentence or two is enough to begin. You can also share relevant material, such as a resume, cover letter, or notes from previous applications. Refine the search after you see the first results.

## Before the first search: agent-data

Job Search gets live postings through the [agent-data](https://agent-data.dev) command-line tool. Onboarding handles the setup:

1. If the CLI is missing, the agent offers to install it with `npm install -g agent-data`. If a global install needs different permissions, it gives you the exact command to run.
2. If authentication is missing, the agent helps you create an API key, runs `agent-data init --api-key <KEY> -y`, and verifies it with `agent-data whoami`. The agent-data CLI stores the key in its own config, outside this repository.

Agent-data offers a 100-call monthly free tier; the example below uses 9 metered calls. Before a choice increases expected usage, Job Search previews the change. After each run, it reports actual attempts. Any dollar amount is labeled as a pay-as-you-go equivalent, not an account charge. See the [agent-data contract](shared/references/agent-data-contract.md) or your [billing page](https://agent-data.motie.dev/settings/billing) for current details.

## What a run looks like

```text
You: Run a search now.

Job Search: Searching LinkedIn and Ashby for "senior product designer"...
Found 42 postings. 9 are new. Reading the promising ones in full...

Here are the first strong matches while I keep reviewing the rest:

• Senior Product Designer — Tidewater Health — Remote (US)
  Owns a care-navigation area end to end; the healthcare mission you're after.

...still reviewing the remaining postings...

Job search digest — 2026-06-05
9 new postings (6 LinkedIn · 3 Ashby) · 2 strong · 2 moderate · 2 weak · 3 filtered out
Agent-data usage: 9 metered calls this run · about $0.072 pay-as-you-go equivalent
```

See the [complete sample digest](examples/sample-digest.md).

## What you can ask

| Goal | Example |
|---|---|
| Start | “Set up my job search. I'm looking for a staff backend role in Europe.” |
| Refine preferences | “Make remote US a must-have,” or “also include fintech roles.” |
| Search now | “Run a search now,” or “check for new jobs.” |
| Schedule searches | “Run my search every morning.” The agent shows the local change, asks for approval, tests the real scheduled path, and only then marks it active. The default runs without an open agent session. |
| Explain usage | “Explain my agent-data usage.” |
| Review a match | “Why is this a strong match?” or “Does this posting fit what I want?” |
| Pause or stop | “Pause my schedule,” or “stop scheduling.” |

Natural language is the main interface. Commands such as `/job-search` and `$job-search` are shortcuts when your agent supports them.

## Support matrix

<details>
<summary>Compatibility details</summary>

These expectations apply to every listed agent:

| Field | Expected support |
|---|---|
| OS / architecture | macOS and Linux; arm64 and x86_64 |
| Recurring scheduler | `cron` or `launchd`, with a session loop fallback |
| Modes | interactive and background (headless) |

Job Search is compatible with Claude Code, Codex, Cursor, opencode, Gemini CLI, GitHub Copilot CLI, Factory Droid, and Pi.

The primary model is inherited from the session that creates the job. Setup records an exact detail-review model, and scheduled runs reuse it. A recurring schedule is recorded only after the agent tests the actual invocation and confirms that it can reach agent-data and write the workspace.

</details>

If something fails, ask the agent to “create a support summary.” It shows you a local diagnostic containing system and run-health metadata, without preferences, posting content, match details, credentials, cursors, or environment dumps. Nothing is uploaded automatically. You can review the file and attach it to a [GitHub issue](https://github.com/agent-data/job-search/issues).

## Installation

Choose your coding agent below. After installation, use the [Quickstart](#quickstart) sentence. Installation succeeded when Job Search opens onboarding and begins the agent-data check.

### Claude Code

Run these commands inside Claude Code:

```text
/plugin marketplace add agent-data/job-search
/plugin install job-search@agent-data
```

Use `/job-search` if you need the command shortcut.

### Codex

Run in your shell, then launch or restart Codex:

```bash
codex plugin marketplace add agent-data/job-search
codex plugin add job-search@agent-data
codex
```

Use `$job-search` if you need the skill shortcut.

### Cursor

Clone the repository, then symlink it into Cursor's local plugins directory:

```bash
git clone https://github.com/agent-data/job-search
ln -s "$(pwd)/job-search" ~/.cursor/plugins/local/job-search
```

### opencode

Add Job Search to the `plugin` array in your global OpenCode config at
`~/.config/opencode/opencode.json`, or to an `opencode.json` in a project where you want to use it:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["job-search@git+https://github.com/agent-data/job-search.git"]
}
```

Restart OpenCode, then start with: **“Set up my job search.”** OpenCode installs the git package with
Bun and the plugin registers the five bundled skills. If your config already has plugins, add this entry
to the existing array rather than replacing it.

See [`.opencode/INSTALL.md`](.opencode/INSTALL.md) for verification, revision pinning, local development,
and troubleshooting.

### Gemini CLI

```bash
gemini extensions install https://github.com/agent-data/job-search
```

### GitHub Copilot CLI

```bash
copilot plugin marketplace add agent-data/job-search
copilot plugin install job-search@agent-data
```

### Factory Droid

```bash
droid plugin marketplace add https://github.com/agent-data/job-search
droid plugin install job-search@agent-data
```

### Pi

```bash
pi install git:github.com/agent-data/job-search
```

For an editable local install, run `pi -e /path/to/job-search`.

## For contributors

Start with [AGENTS.md](AGENTS.md). It points to the [architecture](ARCHITECTURE.md), [contributor workflow](CONTRIBUTING.md), [test guide](TESTING.md), and canonical runtime contracts in [`shared/references/`](shared/references/).

## License

[MIT](LICENSE)
