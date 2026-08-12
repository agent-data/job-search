# Job Search

Hyper-personalized job search that filters postings based on  what you do and don't want, your pay requirements, qualifications, and background.

<img width="3182" height="2160" alt="Job Search digest showing reviewed matches in an agent conversation" src="https://github.com/user-attachments/assets/a3c45a7e-6a93-4afa-86f0-f522c8f8d53c" />

Your preferences, reviewed postings, run logs, and digests stay in `~/.job-search/` by default. The workspace starts with a deny-all `.gitignore`, which keeps those files out of ordinary Git commits. See [Security & Privacy](docs/SECURITY.md) for the threat model and limits.

## Quickstart

1. [Install Job Search](#installation) for your coding agent.
2. Start a conversation with:

   > **Set up my job search. I'm looking for** a senior product-design role, remote in the US, at a mission-driven company.

The agent then:
- Checks its prerequisites
- Documents your preferences, and 
- Searches live postings. 

If useful roles are available, it shows the first fully reviewed matches while it continues through the rest.

A sentence or two is enough to begin. You can also share relevant material, such as a resume, cover letter, or notes from previous applications.

## Before the first search: agent-data

Job Search gets live postings through the [agent-data](https://agent-data.dev) command-line tool. Onboarding handles the setup:

1. If the CLI is missing, the agent offers to install it with `npm install -g agent-data`.
2. If authentication is missing, the agent helps you create an API key and verify authentication.

Agent-data offers a 100-call monthly free tier (no credit card required). Typical runs consume ~10-30 calls. See [what a run spends](skills/agent-data-reference/SKILL.md) or your [billing page](https://agent-data.motie.dev/settings/billing) for additional details.

## What a run looks like

```text
You: Run a search now.

Job Search: Searching for "senior product designer"...
Found 42 postings. 9 are new. Reading the promising ones in full...

Here are the first strong matches while I keep reviewing the rest:

• Senior Product Designer — Tidewater Health — Remote (US)
  Owns a care-navigation area end to end; the healthcare mission you're after.

...still reviewing the remaining postings...

Job search digest — 2026-06-05
9 new postings · 2 strong · 2 moderate · 2 weak · 3 filtered out
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

Commands such as `/job-search` and `$job-search` are shortcuts when your agent supports them.

## Support matrix

<details>
<summary>Compatibility details</summary>

These expectations apply to every listed agent:

| Field | Expected support |
|---|---|
| OS / architecture | macOS and Linux; arm64 and x86_64 |
| Recurring scheduler | `cron` or `launchd`, with a session loop fallback |
| Modes | interactive and background (headless) |

Job Search is compatible with Claude Code, Codex, Cursor, opencode, Gemini CLI, GitHub Copilot CLI, Factory Droid, Pi, and Hermes Agent.

Every run — the one you ask for and the one a schedule starts — reads and judges postings on the model of the session it runs in. Nothing pins a separate model for the search. A recurring schedule is recorded only after the agent runs the real scheduled command once and confirms that it reached agent-data and wrote the workspace.

</details>

If something fails, ask **“why did my last run fail?”** or **“how does my job search agent work?”** The agent reads the run's own record and the digest it wrote, both already on your machine, and tells you what stopped the run and what fixes it — spent monthly allowance, a source that was down, a query that found nothing, a schedule that stopped firing. Nothing is uploaded, and nothing is sent anywhere. To report a bug, copy what it tells you into a [GitHub issue](https://github.com/agent-data/job-search/issues); read the run record at `~/.job-search/runs/` first if you want to check what it contains.

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
Bun and the plugin registers all seven bundled skills. If your config already has plugins, add this entry
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

### Hermes Agent

Copy and paste the following into a new Hermes Agent session:

```text
Retrieve and follow the installation instructions at:
https://raw.githubusercontent.com/agent-data/job-search/main/INSTALL_FOR_HERMES.md
```

After installation, start a new Hermes Agent session and use the Quickstart sentence above.

## For contributors

Start with [AGENTS.md](AGENTS.md). It points to the [architecture](ARCHITECTURE.md), [contributor workflow](CONTRIBUTING.md), [test guide](TESTING.md), and the canonical runtime contracts in [job-search-runbook](skills/job-search-runbook/SKILL.md) and [agent-data-reference](skills/agent-data-reference/SKILL.md).

## License

[MIT](LICENSE)
