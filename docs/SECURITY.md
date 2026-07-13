# Security & Privacy

Job Search handles career-sensitive PII: the preferences brief, every posting judged against
it, run logs, and (in future) resumes. The threat model is one sentence — **keep that data on the
user's machine and out of any public repository.** This document maps each mechanism that enforces
that posture and says plainly where enforcement is human review, not automation.

**Out of scope** — this posture does not defend against: a compromised or shared machine (the
workspace is plaintext on disk); a collaborator with write access committing data past review; or
instructions embedded in fetched posting text — postings are untrusted web content the model
reads, and the judging skills treat them as data to evaluate, never instructions to follow (the
guard line in [`evaluate-job-fit`](../skills/evaluate-job-fit/SKILL.md) and the
[detail-read briefing](../skills/job-search-run/SKILL.md) in `job-search-run`). If a reader needs
those guarantees, nothing below should be read as implying them.

## What's at risk, and where it lives

The workspace contains everything personal — the brief, judged postings, run records, digests.
None of it belongs in a public repo, and none of it is uploaded anywhere by this system. The
sections below walk the enforcement, layer by layer.

## How the workspace stays out of git

The workspace lives outside this repo — by default at `~/.job-search/` on your machine. At
first-run, the setup copies [`../templates/workspace.gitignore`](../templates/workspace.gitignore)
into the workspace root. That file is a genuine deny-all: its only rules are `*` (block
everything) and `!.gitignore` (keep the gitignore itself). Accidentally running `git add` from
inside the workspace cannot commit personal data; the gitignore blocks it at the source.

For the full workspace layout (which files live where and what each contains), see
[`../shared/references/conventions.md`](../shared/references/conventions.md). Do not reproduce
field lists from that file here — it is the single source of truth.

## How the public repo stays free of personal data

This repository contains no personal data. All shipped examples (`examples/`) use synthetic,
fictional postings and preferences. The [`../CONTRIBUTING.md`](../CONTRIBUTING.md) project
philosophy section states the "private and local" rule and names the mechanism that backs it: the
`scripts/philosophy_guard.py` script scans shipped output (`examples/`, `templates/`) and fails
CI if it finds numeric scores, budget fields, or other artifacts that would indicate real personal
data had leaked into a generated example.

## Scheduling writes nothing without your explicit consent

A recurring search needs a scheduler, and setting one up is the only time the system proposes writing to
your machine. **No schedule is ever written silently or without your explicit yes**, and you are always
shown the exact line first.

For reliability, the agent **advocates an unattended machine schedule** — a `cron` or `launchd` entry (or
your host's own scheduler) that runs the search even when no session is open, so a pull you're expecting
actually happens. Because that writes to your machine, it lands **only on your explicit yes, with the exact
line shown to you first** — never silent, never auto-installed, and always user-removable. If you'd rather
install nothing, the **named fallback is an in-session loop** that re-runs the search only while a session is
open: it writes no cron line or plist, but it stops when the session ends.

Whichever you choose, the agent never initiates a **silent or un-consented** write: scheduling is offered as
a yes/no you choose, and a machine schedule lands only after you approve the exact line. Before recording the
schedule the agent also runs a one-time **config-time canary** — a real run through the actual scheduled
invocation — to confirm the job will genuinely work, so a misconfigured schedule fails at setup in front of
you rather than silently the next day.

This is an **instruction-level design rule**, carried by every skill's pinned references — there is no
runtime hook enforcing it (the former PreToolUse guard was removed: it required Python on your machine and
gated something you're entitled to do). If you explicitly ask for cron or launchd, it's your machine and your
call: the agent shows you the exact line first, then writes it on your yes. You also remain free to run cron
or launchd by hand in your own shell, as always. The scheduling flow is documented in
[`../shared/references/internals.md`](../shared/references/internals.md) (see the scheduling section).

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
