# Job Search OS

**Turn Claude Code into the operating system for your job search.**

Within about five minutes of installing, you'll see real job postings judged against *your* stated
preferences — relevant or not, and how strong a match, with plain-language reasoning — and then keep getting
them on a schedule you control. You don't script anything: you run `/job-search` and Claude Code sets up the
whole thing by asking you a few questions.

You define what you want once, in plain English. Claude pulls fresh postings, reads each one against your
brief, and hands you a ranked digest. No dashboards, no scoring spreadsheets, no credit math — the data lives
in a private folder on your own machine.

```
# Job search digest — 2026-06-05
Run health: healthy
9 new postings · 2 strong · 2 moderate · 2 weak · 3 filtered out · 2 searches · 5 detail reads

## Strong matches
- **Senior Product Designer** — Tidewater Health — Remote (US)
  Embedded with a product+eng pod, owns a care-navigation area end to end, healthcare mission you're after.  [view](…)
```

See a full one in [`examples/sample-digest.md`](examples/sample-digest.md).

---

## Requirements

- **[Claude Code](https://claude.com/claude-code)** — this is a Claude Code plugin.
- **The `agent-data` CLI, authenticated** — it's the job-data source.
  ```bash
  agent-data whoami        # should show  api_key_set: true
  ```
  Not authenticated? Generate a key at [agent-data.motie.dev](https://agent-data.motie.dev) (Profile → API
  Key), then either `export AGENT_DATA_API_KEY=mtk_…` or save it to `~/.agent-data/config.json`, and re-run
  `agent-data whoami`.
- **Python 3.9+** — the bundled helper scripts are dependency-free.

---

## Install from source (works today)

Clone the repo and pick the option that fits how permanent you want it.

**A — Try it in one session (non-persistent).** Launch Claude Code with the plugin loaded — `--plugin-dir`
is a *launch* flag, so run this in your **shell**, not inside a Claude Code session that's already open:

```bash
claude --plugin-dir /path/to/job-search-os
```

That command **starts a new** Claude Code session with the plugin available; run `/job-search` inside it.
(Already in a running session? Use option **B** instead.)

**B — Install it persistently from a local clone.** Register the clone as a local marketplace, then install:

```
/plugin marketplace add /path/to/job-search-os
/plugin install job-search-os@agent-data
```

**C — Loose skills (no plugin system).** Each skill folder is self-contained. Build the bundled copies, then
copy or symlink the skills you want into `~/.claude/skills/`:

```bash
cd /path/to/job-search-os
./scripts/build.sh
mkdir -p ~/.claude/skills
ln -s "$PWD/skills/job-search"       ~/.claude/skills/job-search
ln -s "$PWD/skills/job-search-run"   ~/.claude/skills/job-search-run
ln -s "$PWD/skills/evaluate-job-fit" ~/.claude/skills/evaluate-job-fit
ln -s "$PWD/skills/job-preference-interview" ~/.claude/skills/job-preference-interview
```

(Prefer copies that won't change under you? `cp -R` each folder instead of symlinking. After editing anything
under `shared/references/` or `scripts/`, re-run `./scripts/build.sh` to re-sync the bundled copies — see
[CONTRIBUTING.md](CONTRIBUTING.md).)

Contributing or exploring the codebase with an AI agent? See [AGENTS.md](AGENTS.md) — the agent-facing map of the repo (architecture, design beliefs, plans, quality).

After any of the above, run:

```
/job-search
```

Claude sets up everything by asking you a few questions — it checks the prerequisites, creates your private
workspace, interviews you to build a preferences brief, helps you pick your search queries and how often to
run, does a **first live search right then** so you see real matches seconds later, and offers to schedule it.

You don't have to remember the slash command. Natural language works too:

> "set up job search" · "find me jobs" · "check my job search"

If `/job-search` is ever ambiguous with another plugin, the always-unambiguous form is
`/job-search-os:job-search`.

---

## Install from the marketplace (once published)

Once this plugin is published to the agent-data marketplace, install will be a single step — but that
publication is not live yet, so the commands below will not work today. When it is published, the golden
one-step path will be:

```
/plugin marketplace add agent-data/job-search-os
/plugin install job-search-os@agent-data
```

Then run `/job-search` as above.

---

## What it does

**Qualitative relevance — never a score.** Claude reads each posting against your plain-English brief and
decides two things: **relevant or not** (false only when a must-have or dealbreaker is clearly violated), and
if relevant, **weak / moderate / strong** — always with reasoning. There are **no 0–100 fit scores, no
category weights, no points.** Importance lives in *which bucket* you put a preference in (must-have vs.
strong-preference vs. nice-to-have), not in math. Anything a posting doesn't state is flagged "unknown" and
**never counted against it**; if a dealbreaker can't be confirmed, the digest tells you exactly what to
check before applying.

**You control frequency, not a budget.** You tune the system in human terms — how often it runs (`hourly`,
`every-2-hours`, `every-6-hours`, `daily`, `weekly`) — by chatting with Claude. There is no budget knob and
nothing about credits to reason about.

**Private and local.** Your preferences, the jobs it's matched, your run logs, and your digests live in a
hidden workspace on your own machine (`~/.job-search/`). Nothing personal is uploaded to this repo or
anywhere else.

---

## Cost, honestly

Most of what the system does is **free**. On the `agent-data` CLI, `search`, `docs`, `status`, and `whoami`
are free; **only `search-jobs` and `get-posting` are metered.**

The system is frugal *by behavior*, not by making you do arithmetic:

- It **judges from the free posting summary first** and only spends a metered detail read on postings that
  already look promising.
- It **dedupes against your local job database**, so it never re-pulls or re-evaluates a posting it has
  already seen.
- One search per query per run, plus a detail read only for the promising matches.

If the API limit for the period is ever reached, you get a **plain-language note** — never credit math:

> "agent-data's API limit for this period has been reached, so no new postings were pulled. This usually
> means searches are running very often — lower `schedule.frequency` in `config.yaml` (e.g. `daily` instead
> of `hourly`), or upgrade your plan at agent-data.motie.dev. Your existing matches are unaffected."

That's the only place cost ever shows up, and the fix is always a frequency change or a plan upgrade — you're
never asked to reason about credits.

---

## Privacy

Your workspace (default `~/.job-search/`) is **private, personal data** — your preferences, where you're
job-hunting, the postings you've matched, and (later) your resume. It ships with a **deny-all `.gitignore`**:

```gitignore
# job-search workspace is PRIVATE — do not commit to a public repo
*
!.gitignore
```

**Never commit your workspace to a public repo.** The code in *this* repository contains no personal data.

---

## Troubleshooting

Every failure mode is **named and visible** — no silent failures. Blocked runs never fail silently: each writes a **blocked digest** (the named error + its
fix as the body), fires a **desktop notification**, and is named in your **home view** the
next time you run `/job-search`. (A headless `claude -p` run itself exits 0 even when
blocked — the surfacing is the digest/notification/home, not the shell exit code.) The digest's
**Run health** line is one of `healthy | partial (N errors) | degraded (LinkedIn flaky) | blocked (action
needed)`.

| Code | When | What you see (cause + fix) | Run effect |
|---|---|---|---|
| **E-NO-AGENT-DATA** | the `agent-data` CLI is not found on PATH (prereq check, before `whoami`) | "The agent-data CLI isn't installed. Install it (`npm install -g agent-data`), then run `agent-data whoami` to authenticate. Nothing was pulled." | HALT, exit 1 |
| **E-NO-CONFIG** | `config.yaml` missing in the workspace | "No `config.yaml` found in <workspace>. Run `/job-search` to set it up." | HALT, exit 1 |
| **E-NO-AUTH** | `agent-data whoami` shows `api_key_set:false` | "agent-data is not authenticated. Run `export AGENT_DATA_API_KEY=mtk_…` (or save it to `~/.agent-data/config.json`), then verify with `agent-data whoami`. No data was pulled." | HALT, exit 1 |
| **E-CONFIG-VERSION** | `config.yaml` `version` major is newer than this code supports | "This `config.yaml` was written by a newer version. Update the job-search-os skills, or check `version:` in config." | HALT, exit 1 |
| **E-NO-PREFERENCES** | `preferences.md` missing/empty (the no-preferences run path) | "No Job Preferences Brief found. Run `/job-preference-interview` to build one, or point `config.yaml:workspace.preferences_path` at your own prose brief. Nothing was pulled." | HALT, exit 1 |
| **E-SERVICE-DOWN** | `status` route unreachable / non-200 | "The job source is unreachable right now. This is usually temporary — the next scheduled run will retry." | HALT, exit 1, write "service down" digest |
| **E-BAD-QUERY** | `422 invalid_request` / `400 unsupported_field` on a search | "Query '<id>' is invalid: <param from details[].loc>. Fix it in `config.yaml` under `queries`." | skip that query, continue |
| **E-UPSTREAM-STRETCH** | 2 consecutive `search-jobs` 502s | "LinkedIn was unreachable this run (repeated upstream errors). Partial or no results; the next scheduled run will retry." | stop searching, partial digest |
| **E-QUOTA** | agent-data reports its API limit reached (metered call rejected for quota/payment) | "agent-data's API limit for this period has been reached, so no new postings were pulled. This usually means searches are running very often — lower `schedule.frequency` in `config.yaml` (e.g. `daily` instead of `hourly`), or upgrade your plan at agent-data.motie.dev. Your existing matches are unaffected." | HALT, exit 1 |

**Expected non-errors** (these show up as footnotes, not failures):

- A posting's detail link went stale (LinkedIn re-indexed) — Claude judges it from the summary and adds a
  footnote. Not an error.
- "No NEW postings — all already in your database." Reassuring, not a failure.
- "Searches ran but returned 0 results." Actionable: broaden your keywords in `config.yaml`.

---

## See a real digest before you install

Output speaks louder than a README. Two realistic, fictional examples ship in this repo:

- **[`examples/sample-digest.md`](examples/sample-digest.md)** — a full digest in the real format: the
  Run-health line, the counts line, strong → moderate → weak matches with reasoning and `view` links,
  `⚠ confirm:` flags where a dealbreaker can't be confirmed, the filtered-out list with one-line reasons, and
  footnotes.
- **[`examples/sample-preferences.md`](examples/sample-preferences.md)** — the kind of plain-English
  preferences brief Claude builds with you: a short summary, must-haves/dealbreakers, strong preferences,
  nice-to-haves, and red flags. (Yours is built by the interview during `/job-search`.)

---

## Roadmap

This release covers **discovery + qualitative relevance + local scheduling**: the front-door
`/job-search` onboarding, the preferences interview, the scheduled runner, single-posting evaluation, and a
private local workspace.

**Operator manual:** the `job-search-agent` skill is the reference Claude reaches for to configure, extend, or troubleshoot the agent.

**Coming next (Plan C):** resume tools — `resume-compare` (a qualitative read of how your resume lines up
against a posting, with gaps; read-only) and `resume-tailor` (truthful, provenance-checked tailoring that
never invents experience you don't have).

---

## License

MIT — see [`LICENSE`](LICENSE).
