# Job Search OS

Turn Claude Code into an operating system for your job search. Define your preferences once, then let
Claude Code pull fresh job postings, judge each one's relevance against what you actually want, and hand you
a ranked digest — plus (coming soon) resume comparison and truthful resume tailoring.

**Relevance is a qualitative judgment, not a score.** Claude reads each posting against your plain-English
preferences and decides **relevant or not**, and if relevant, **weak / moderate / strong** — with reasoning.
No 0–100 scores, no arbitrary category weights. You tune the system in human terms (how often to pull),
never in credits.

> **Status — early.** The core engine is built, tested, and verified against the live job API: the
> `evaluate-job-fit` and `job-search-run` skills, the job database, and the agent-data integration. Still to
> come: a guided setup + preferences interview (so you won't create the workspace by hand), resume tools, and
> a one-command plugin install. See [What's built / what's next](#whats-built--whats-next).

## Requirements

- [Claude Code](https://claude.com/claude-code)
- The **agent-data** CLI (the job-data source):
  ```bash
  npm install -g agent-data
  agent-data whoami        # should show "api_key_set": true
  ```
  Not authenticated? Generate a key at https://agent-data.motie.dev (Profile → API Key), then either
  `export AGENT_DATA_API_KEY=mtk_…` or save it to `~/.agent-data/config.json`.
- Python 3.9+ (the bundled `state.py` is dependency-free).

## Quick start (test the current core)

Until the guided setup ships (next milestone), install the skills and create a workspace by hand. The steps
below assume the repo is at `~/job-search-os` — adjust the path if you cloned it elsewhere.

### 1. Install the two skills

They're self-contained, so symlinking them into your Claude Code skills directory works and keeps them in
sync as you pull updates:

```bash
mkdir -p ~/.claude/skills
ln -s ~/job-search-os/skills/evaluate-job-fit ~/.claude/skills/evaluate-job-fit
ln -s ~/job-search-os/skills/job-search-run   ~/.claude/skills/job-search-run
```
(Prefer copies? `cp -R` the two folders instead. If you later edit `shared/references/` or
`scripts/state.py`, run `./scripts/build.sh` to re-sync the bundled copies inside each skill.)

### 2. Create your private workspace

This holds your preferences, matched jobs, and run logs. It's personal — never commit it to a public repo.

```bash
mkdir -p ~/job-search/runs ~/job-search/reports
cp ~/job-search-os/templates/config.example.yaml    ~/job-search/config.yaml
cp ~/job-search-os/templates/preferences.example.md ~/job-search/preferences.md
cp ~/job-search-os/templates/workspace.gitignore    ~/job-search/.gitignore
: > ~/job-search/jobs.jsonl
```
Now **edit two files**:
- `~/job-search/preferences.md` — replace the example with *your* must-haves / dealbreakers, strong
  preferences, nice-to-haves, and red flags. Plain English; the model reads this directly.
- `~/job-search/config.yaml` — set your `queries` (keywords + location) and `schedule.frequency`.

### 3. Run it

In a Claude Code session:
```
/job-search-run --workspace ~/job-search
```
Claude probes the source, searches agent-data for each query, dedups against your database, judges each new
posting against your brief, reads full descriptions for the promising ones, and writes a digest to
`~/job-search/reports/<date>-digest.md` — grouped strong → moderate → weak, with a "filtered out" count and
plain-language reasoning. New matches are recorded in `~/job-search/jobs.jsonl` (re-running is safe; it never
re-evaluates a job it has already seen).

> Each run uses the agent-data API (one call per query, plus one per full description it reads). The free
> tier covers regular daily searching; if you ever hit the limit, the run tells you in plain language to pull
> less often or upgrade — you never reason about credits.

### Also try: judge a single posting

Paste any job description and ask whether it fits:
```
/evaluate-job-fit
```
Point it at your brief (`~/job-search/preferences.md`) and paste the JD. You'll get: relevant or not, a
weak/moderate/strong band, the reasoning, any dealbreakers it hits, and anything the posting didn't state
(flagged "unknown" — never counted against it).

## How it works

| Piece | Role |
|---|---|
| `skills/job-search-run` | The scheduled runner: pull → dedup → judge → digest (headless-safe). |
| `skills/evaluate-job-fit` | The relevance "brain": one posting + your brief → qualitative verdict. |
| `scripts/state.py` | Dependency-free engine for the append-only `jobs.jsonl` job database. |
| `shared/references/` | The agent-data contract, the named-error catalog, and workspace conventions. |
| `~/job-search/` (your workspace) | Private data: preferences, matched jobs, run logs, digests. |

The single job source today is the agent-data "Job Postings API" (LinkedIn-backed). The source sits behind a
small contract so more sources can be added later.

## Privacy

Your `~/job-search/` workspace is personal — preferences, where you're job-hunting, and (later) your resume.
The included `.gitignore` is deny-all. **Never commit your workspace to a public repo.** The code in this
repo contains no personal data.

## What's built / what's next

- ✅ **Core (now):** `evaluate-job-fit`, `job-search-run`, `state.py`, references/templates, tests; verified
  across 10 run scenarios and a live-API smoke test.
- ⏳ **Onboarding:** `job-preference-interview` (build your brief by Q&A) + `job-search-setup` (one command:
  scaffold the workspace, pick a frequency, do a first run, print how to schedule it locally).
- ⏳ **Resume:** `resume-compare` (qualitative fit + gaps, read-only) and `resume-tailor` (truthful,
  provenance-checked — never invents experience).
- ⏳ **Packaging:** an installable Claude Code plugin and polished docs.

## Development

```bash
python3 -m pip install --user pytest
python3 -m pytest -q          # state.py + the agent-data shim (no real API calls)
./scripts/build.sh            # re-sync bundled references + state.py into the skills after editing sources
```

## License

MIT — see [`LICENSE`](LICENSE).
