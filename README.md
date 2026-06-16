# Job Search OS

**Turn Claude Code into the operating system for your job search.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Tested on Claude Code](https://img.shields.io/badge/tested%20on-Claude%20Code-6b46c1)

Job Search OS is a Claude Code plugin that runs your job search. Describe what you want once, in
plain English; Claude pulls fresh postings, judges each against your brief, and hands you a ranked
digest — then keeps doing it on a schedule you control.

## How it works

It starts the moment you install. You run one command and Claude asks what you're after — the role,
the level, your must-haves and dealbreakers, where you want to work. You answer in plain English;
there are no forms or config files to fill in.

As soon as your brief is ready, Claude runs a live search right then, so within a few minutes of
installing you're looking at real postings — each judged against *your* brief, marked relevant or
not and weak / moderate / strong, with plain-language reasoning. Then it offers to keep running on a
schedule you pick — hourly, daily, weekly — and you can always say no.

After that it stays conversational. "Find me jobs." "Also search staff roles." "Run this daily
instead of hourly." You never edit a file or memorize a command.

```
# Job search digest — 2026-06-05
Run health: healthy
9 new postings · 2 strong · 2 moderate · 2 weak · 3 filtered out · 2 searches · 5 detail reads

## Strong matches
- **Senior Product Designer** — Tidewater Health — Remote (US)
  Embedded with a product+eng pod, owns a care-navigation area end to end, healthcare mission you're after.  [view](…)
```

See a full one in [`examples/sample-digest.md`](examples/sample-digest.md).

## Requirements

- **[Claude Code](https://claude.com/claude-code)** — this is a Claude Code plugin.
- **The `agent-data` CLI, authenticated** — the job-data source. Verify with `agent-data whoami` (it
  should show `api_key_set: true`). No key yet? Generate one at
  [agent-data.motie.dev](https://agent-data.motie.dev) (Profile → API Key), then `export
  AGENT_DATA_API_KEY=mtk_…` (or save it to `~/.agent-data/config.json`) and re-check.

Tested on **Claude Code** (macOS and Linux). Other Anthropic surfaces — Claude AI, Claude Cowork —
should work but aren't tested yet.

## Installation

Clone the repo, then pick how permanent you want it.

**One session (no install).** `--plugin-dir` is a launch flag, so run it in your shell, then run
`/job-search-os:job-search` in the session it opens:

```bash
claude --plugin-dir /path/to/job-search-os
```

**Persistent (local marketplace).** Register the clone, then install:

```
/plugin marketplace add /path/to/job-search-os
/plugin install job-search-os@agent-data
```

**Loose skills (no plugin system).** Build the bundled copies, then symlink the skills into
`~/.claude/skills/`:

```bash
cd /path/to/job-search-os
./scripts/build.sh
mkdir -p ~/.claude/skills
for s in job-search job-search-run evaluate-job-fit job-preference-interview job-search-agent; do
  ln -s "$PWD/skills/$s" ~/.claude/skills/$s
done
```

(Re-run `./scripts/build.sh` after pulling updates.) A one-step marketplace install is coming once
the plugin is published.

After installing, run the front door — or just say what you want:

```
/job-search-os:job-search     # plugin install
/job-search                   # loose-skill install
```

Natural language works in every mode: "set up job search," "find me jobs," "check my job search."
(Plugin skills are only invocable namespaced as `/plugin:skill`; the bare `/job-search` exists only
for loose-skill installs.)

## Everyday use

Everything is conversational — you never have to remember a command or hand-edit a file:

| To… | Say something like… |
|---|---|
| Set up / onboard | "set up job search" |
| Run a search now | "find me jobs" · "run a job search now" |
| Check status & latest digest | "check my job search" |
| Add or change a search | "also search for staff product designer roles" |
| Change how often it runs | "run this daily instead of hourly" |
| Update your preferences | "update my preferences — I'm open to fully remote now" |
| Pause / resume scheduling | "pause the scheduled search" |

## What's inside

Five skills, each triggered by what you say:

- **job-search** — the front door: onboarding, status, and your home view.
- **job-preference-interview** — builds your plain-English preferences brief.
- **job-search-run** — one headless search pass; this is what the schedule runs.
- **evaluate-job-fit** — judges a single posting you paste in.
- **job-search-agent** — the operator manual Claude reaches for to configure, extend, or
  troubleshoot the system.

## Philosophy

- **Qualitative relevance, never a score.** Claude reads each posting against your brief and decides
  *relevant or not*, then *weak / moderate / strong* — always with reasoning. No 0–100 scores, no
  weights, no points. What a posting doesn't state is marked "unknown" and never counted against it.
- **You control frequency, not a budget.** You tune how often it runs in plain terms (hourly …
  weekly). There's no credit math to reason about.
- **Frugal by behavior.** It judges from the free posting summary first and spends a metered detail
  read only on promising matches, and it never re-pulls a posting it has already seen.
- **Private and local.** Your preferences, matches, logs, and digests live in `~/.job-search/` on
  your own machine, behind a deny-all `.gitignore`. Nothing personal is uploaded anywhere.

## Troubleshooting

Failures are named and visible — never silent. Every error carries its cause and fix in plain
language, right where you'll see it. A blocked run writes a digest explaining what happened, fires a
desktop notification, and surfaces the next time you open the job-search skill. The digest's **Run
health** line reads `healthy`, `partial`, `degraded`, or `blocked (action needed)`.

Full error reference: [`shared/references/errors.md`](shared/references/errors.md).

## Roadmap

This release covers discovery, qualitative relevance, and local scheduling: onboarding, the
preferences interview, the scheduled runner, single-posting evaluation, and a private local
workspace.

**Coming next:** resume tools — `resume-compare` (a read-only, qualitative look at how your resume
lines up against a posting, with gaps) and `resume-tailor` (truthful, provenance-checked tailoring
that never invents experience you don't have).

## Contributing

Building on or exploring the repo with an AI agent? Start at [AGENTS.md](AGENTS.md) — the map of the
architecture, design beliefs, and plans. See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev workflow
and [TESTING.md](TESTING.md) for the test harness. This project has a
[Code of Conduct](CODE_OF_CONDUCT.md).

## License

MIT — see [`LICENSE`](LICENSE).
