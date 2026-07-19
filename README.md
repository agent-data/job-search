# Job Search

Turn your coding agent into an automated job-search assistant. Tell it what you want in plain English — it pulls fresh postings from LinkedIn, Ashby, Greenhouse, and Lever, judges each one against your preferences, and writes a filtered digest of the matches. On demand, or on a schedule.

<img width="3182" height="2160" alt="job-search-demo-screenshot" src="https://github.com/user-attachments/assets/a3c45a7e-6a93-4afa-86f0-f522c8f8d53c" />

**Private by default.** Your preferences, the postings you've seen, run logs, and every digest live in a private workspace on your own machine — `~/.job-search/` — that ships with a deny-all `.gitignore`, so none of it is ever committed to a repository or uploaded anywhere. No cloud, no hosted dashboard, no service holding your search history. Your machine, your data.

Instead of keyword alerts, you get judgment: each posting is weighed against a plain-English brief of your must-haves, dealbreakers, and preferences, and every shown match carries a one-line reason so you can see why it landed where it did.

## Quickstart

1. **Install the plugin** for your coding agent — see [Installation](#installation) (one-time, per agent).
2. **Just say what you're after.** In your agent, type:

   > **Set up my job search. I'm looking for** a senior product-design role, remote in the US, at a mission-driven company.

That's the whole golden path. The agent takes it from there: it checks a couple of prerequisites, creates your private workspace, learns what you want, saves your first searches, and pulls live postings — ending on real matches found seconds ago, usually within about five minutes.

You **don't** need a preferences document to begin. If you have relevant material — a resume, a cover letter, or notes from past applications — share it and the agent will draw on it as background; if you don't, a sentence or two about what you want is enough to start.

> Prefer to drive with commands? `/job-search` kicks off the same onboarding. Slash commands are deterministic shortcuts and fallbacks — never a separate track from the conversation.

## Before your first search: agent-data

Job Search reads live postings through the [agent-data](https://agent-data.motie.dev) marketplace CLI, so that's the one prerequisite. You don't set it up by hand — during onboarding the agent handles it and recovers if something's missing:

- **Install.** If the CLI isn't on your `PATH`, the agent installs it for you (`npm install -g agent-data`). If your permissions block a global install, that's a one-line handoff, not a dead end: the agent gives you the exact command to run yourself (`! npm install -g agent-data`) and continues once it lands.
- **Authenticate.** The agent walks you through generating an API key, connects with `agent-data init --api-key <KEY> -y`, and confirms it with `agent-data whoami`. Your key is only asked for at this step, and it's stored by agent-data's own CLI — never in this repo.

**Agent-data offers a 100-call monthly free tier** — enough to get started with your first searches. A first search starts with a handful of calls; reading promising postings in full may add a few detail calls. Job Search previews any added work before it runs and reports the actual calls after every run — calls first, never a hidden charge. Current pricing and metering are single-sourced in [`shared/references/agent-data-contract.md`](shared/references/agent-data-contract.md) and your [account billing page](https://agent-data.motie.dev/settings/billing).

## What a run looks like

In a live run, the agent shows a **strong early look** the moment a few fully-judged matches are ready — then keeps going on its own, no second confirmation, and finishes with the full digest:

```text
You: Run a search now.

Job Search: Searching LinkedIn and Ashby for "senior product designer"…
Found 42 postings — 10 are new. Reading the promising ones in full…

Here are the first strong matches while I keep reviewing the rest:

• Senior Product Designer — Tidewater Health — Remote (US)
  Owns a care-navigation area end to end; the healthcare mission you're after.

…still reading the remaining postings…

Job search digest — 2026-06-05
10 new postings (7 LinkedIn · 3 Ashby) · 2 strong · 2 moderate · 2 weak · 3 filtered out
Agent-data usage: 9 metered calls this run · about $0.072 pay-as-you-go equivalent
```

The early look is a first look, not the finished list — the agent continues automatically and the digest is the whole picture. See a complete example in [`examples/sample-digest.md`](examples/sample-digest.md).

## What you can ask

Everything is conversational — you say it in plain English, and the agent does it. A few of the things you can ask:

| You want to… | Say something like |
|---|---|
| **Set up / start** | "Set up my job search. I'm looking for a staff backend role in Europe." |
| **Refine what you want** | "Add remote-US as a must-have," or "make my preferences more thorough." |
| **Run now** | "Run a search now," or "check for new jobs." |
| **Schedule it** | "Run my search every morning." The agent proposes an unattended schedule on your machine, shows you the exact change first, and records it only after a **canary run proves it actually works** — it never claims a search is scheduled until that's verified. |
| **Explain usage** | "Explain my agent-data usage." |
| **Understand a match** | "Why is this a strong match?" — or paste a posting: "Does this job fit what I want?" |
| **Pause / stop** | "Pause my schedule," or "stop scheduling." |

The home view (`/job-search`) and the other skills are there as shortcuts; the sentence is the interface.

## Support matrix

Job Search runs on eight agent harnesses from one shared skill tree. **No live end-to-end coverage has been recorded yet** — the live support matrix is tracked as a separate task (T9.4) and has not been run. Every row below is **structural** (its manifest parses and the skills resolve their shared references in place) and **expected-to-work** from today's contracts; treat the model and live columns as *pending verification*, not as proven live results.

_Verified (structural / expected-to-work): 2026-07-17._

| Harness | Version | OS / arch | Scheduler | Modes | Models (primary / detail) | Status |
|---|---|---|---|---|---|---|
| Claude Code | ≥ 2.1.x | macOS, Linux (arm64, x86_64) | unattended `cron`/`launchd`; in-session `/loop` fallback | interactive + headless | session-inherited / exact `search.detail_model` (host-resolved at setup) | structural · expected-to-work |
| Codex | current | macOS, Linux (arm64, x86_64) | unattended `cron`/`launchd`; in-session loop fallback | interactive + headless | session-inherited / host-resolved exact model | structural · expected-to-work |
| Cursor | current | macOS, Linux (arm64, x86_64) | unattended `cron`/`launchd`; in-session loop fallback | interactive + headless | session-inherited / host-resolved exact model | structural · expected-to-work |
| opencode | current | macOS, Linux (arm64, x86_64) | unattended `cron`/`launchd`; in-session loop fallback | interactive + headless | session-inherited / host-resolved exact model | structural · expected-to-work |
| Gemini CLI | current | macOS, Linux (arm64, x86_64) | unattended `cron`/`launchd`; in-session loop fallback | interactive + headless | session-inherited / host-resolved exact model | structural · expected-to-work |
| GitHub Copilot CLI | current | macOS, Linux (arm64, x86_64) | unattended `cron`/`launchd`; in-session loop fallback | interactive + headless | session-inherited / host-resolved exact model | structural · expected-to-work |
| Factory Droid | current | macOS, Linux (arm64, x86_64) | unattended `cron`/`launchd`; in-session loop fallback | interactive + headless | session-inherited / host-resolved exact model | structural · expected-to-work |
| Pi | current | macOS, Linux (arm64, x86_64) | unattended `cron`/`launchd`; in-session loop fallback | interactive + headless | session-inherited / host-resolved exact model | structural · expected-to-work |

Notes, honestly:
- **Models.** No model selector is exposed to set the *primary* model (a known harness limitation), so the primary is the model the session already runs on; the *detail-read* model is the exact `search.detail_model` the agent picks at setup (the least-powerful model on the host that can judge fit well, host-resolved). The specific tested model IDs per host are what the live matrix (T9.4) will record; they are not pinned here.
- **Scheduler.** The advocated default is an *unattended* machine schedule that fires with no session open, gated on your explicit consent and recorded only after a config-time canary passes; the in-session loop is the named fallback. Cloud schedulers do not qualify (they can't see your local workspace or auth). See [`docs/SECURITY.md`](docs/SECURITY.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md).
- **Live vs. structural.** A green structural gate is not a passed behavioral run. Live verification per host is the deferred T9.4 lane.

**Hit a snag?** Ask the agent for a support summary and it writes a local, whitelist-only diagnostic — build stamp, harness and version, OS and architecture, schedule state, and the latest run's health, internal error code, agent-data call count, and request IDs. It deliberately leaves out your preferences, the postings, match details, API keys, auth headers, and cursors. The agent shows you the whole file first; nothing is uploaded automatically. Review it, then attach it yourself to a new issue at [github.com/agent-data/job-search/issues](https://github.com/agent-data/job-search/issues) if you want to share it.

## Installation

Installation differs by harness. If you use more than one, install Job Search separately for each. After installing, start with the natural-language golden path above (or the `/job-search` shortcut).

### Claude Code

Register the marketplace, then install:

```
/plugin marketplace add agent-data/job-search
/plugin install job-search@agent-data
```

Then run `/job-search` — or just say "set up my job search" — to start.

### Codex

Register the marketplace, install the plugin, and launch Codex:

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

Then tell Gemini to run the **job-search** skill.

### GitHub Copilot CLI

Register the marketplace, then install:

```bash
copilot plugin marketplace add agent-data/job-search
copilot plugin install job-search@agent-data
```

Then tell Copilot to run the **job-search** skill.

### Factory Droid

Register the marketplace, then install:

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

## What's inside

Five skills make up the plugin — you mostly touch the first one:

- **job-search** — the front door: onboarding, status, and your home view.
- **job-preference-interview** — builds your plain-English preferences brief.
- **job-search-run** — one headless search pass; this is what a schedule runs.
- **evaluate-job-fit** — judges a single posting you paste in.
- **job-search-agent** — the operator manual the agent reaches for to configure, extend, or troubleshoot the system.

## Contributing

Building on or exploring the repo with an AI agent? Start at [AGENTS.md](AGENTS.md) — the map of the architecture, design beliefs, and plans, including how one `skills/` tree runs across every supported agent, and the single-source-of-truth runtime contracts under [`shared/references/`](shared/references/). See [ARCHITECTURE.md](ARCHITECTURE.md) for the structural map, [CONTRIBUTING.md](CONTRIBUTING.md) for the dev workflow, and [TESTING.md](TESTING.md) for the test harness.

## License

MIT — see [`LICENSE`](LICENSE).
