# Security & Privacy

Job Search OS handles career-sensitive PII: your preferences brief, matched job postings, run
logs, and (in future) resumes. The threat model is simple — keep that data on your machine and
out of any public repository. This document describes each mechanism that enforces that posture,
and states plainly where the system relies on human review rather than automation.

## What's protected

The workspace contains everything personal: the preferences brief you wrote, every posting the
agent has ever judged against it, the run audit logs, and the digest reports. None of that
material belongs in a public repo, and none of it is uploaded anywhere by this system. The
mechanisms below enforce that at every layer.

## Private, local-first workspace

The workspace lives outside this repo — by default at `~/.job-search/` on your machine. At
first-run, the setup copies [`../templates/workspace.gitignore`](../templates/workspace.gitignore)
into the workspace root. That file is a genuine deny-all: its only rules are `*` (block
everything) and `!.gitignore` (keep the gitignore itself). Accidentally running `git add` from
inside the workspace cannot commit personal data; the gitignore blocks it at the source.

For the full workspace layout (which files live where and what each contains), see
[`../shared/references/conventions.md`](../shared/references/conventions.md). Do not reproduce
field lists from that file here — it is the single source of truth.

## No PII in the public repo

This repository contains no personal data. All shipped examples (`examples/`) use synthetic,
fictional postings and preferences. The [`../CONTRIBUTING.md`](../CONTRIBUTING.md) project
philosophy section states the "private and local" rule and names the mechanism that backs it: the
`scripts/philosophy_guard.py` script scans shipped output (`examples/`, `templates/`) and fails
CI if it finds numeric scores, budget fields, or other artifacts that would indicate real personal
data had leaked into a generated example.

## Scheduling never writes your machine

Scheduling is Claude Code's native `/loop` — `/loop <interval> /job-search-run` re-runs the search inside an
open Claude session. The agent never installs a cron line or a launchd plist; nothing scheduling-related is
written to your machine. A PreToolUse hook
([`../hooks/guard-scheduled-tasks.py`](../hooks/guard-scheduled-tasks.py)) is a defense-in-depth backstop that
enforces this on the agent's Bash tool calls:

- **Deny** — any model-initiated `crontab` or launchd *install* (the message points back to `/loop`).
- **Defer** — reads (`crontab -l`), list commands, schedule removal, `/loop`, and any command that merely
  *mentions* these words (a `grep`, an `echo`). Detection is anchored to a shell command position, so
  searching for these terms is never blocked.

You remain free to run cron or launchd by hand in your own shell — the guard only gates the agent. The
`/loop` flow is documented in [`../shared/references/internals.md`](../shared/references/internals.md) (see
the scheduling section). Do not reproduce the hook's exact decision strings here — link the source.

## Auth and secrets

The agent-data API key is the only credential the system uses. It is provided via the environment
(`AGENT_DATA_API_KEY`) or the agent-data CLI's own config file (`~/.agent-data/config.json`); it
is never stored in this repository. If the key is absent or invalid at run time, the agent halts
immediately with a named error and writes a blocked run record. The full named-error catalogue —
including the auth failure error, its cause, and its fix — is in
[`../shared/references/errors.md`](../shared/references/errors.md).

## Credit-free, side-effect-free testing

The test suite and skill evals route all agent-data calls through a fake shim in `tests/`. This
means:

- No metered API calls are made.
- No charges are incurred.
- No real workspace is touched (the env vars redirect everything to a temp directory).

This posture is a hard requirement documented in [`../CONTRIBUTING.md`](../CONTRIBUTING.md) and
verified by the setup in [`../TESTING.md`](../TESTING.md): every new code path that calls
agent-data must go through the shim in evals, not the live CLI.

## No application-URL scraping

The job-data source deliberately does not expose an `application_url` field.
[`../shared/references/agent-data-contract.md`](../shared/references/agent-data-contract.md) states
this explicitly in the `get-posting` route definition. The system therefore never scrapes or
follows application endpoints — the omission is intentional, not a gap.

## Residual risks and honest limits

The deny-all workspace gitignore template is the primary guard against accidentally-committed PII.
Beyond that template, **there is no automated CI scan that checks whether workspace content was
committed to the public repo**. The guarantee rests on two things: the deny-all template (which
must have been copied in by first-run setup), and human review of any PR that touches
`examples/` or `templates/`.

This honest limit is acknowledged in [`design-docs/core-beliefs.md`](design-docs/core-beliefs.md)
under "Private & local" (Belief 3): "Beyond the template this is **cultural** — there is no CI
check that scans for committed PII, so review must catch it." Do not claim stronger protection
than this.
