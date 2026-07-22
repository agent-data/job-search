---
name: job-search
description: The front door and home screen for the user's job search — setup, status, matches, pipeline, and steering what they're looking for. Use when they want to start or set up a job search, see status, matches, the latest digest, or the pipeline, or change what they're looking for — "set up job search", "start my job search", "I'm looking for a new job", "check my job search", "show me my matches", "what's new in my pipeline". First run reaches real live matches with no setup ceremony, by handing the search to job-search-run and each verdict to evaluate-job-fit. Not the skill that pulls postings ("check for new jobs" → job-search-run), judges one posting ("is this a good fit?" → evaluate-job-fit), rebuilds the preferences brief (→ job-preference-interview), or configures the agent itself (→ job-search-agent).
---

# job-search

> To configure, extend, customize, or troubleshoot the agent itself (or understand its
> capabilities), use the **job-search-agent** skill — the operator manual.

The **OS shell** for Job Search OS — the front door you run when you want to set the system up or check on
it. Mental model: this skill is the **login shell + home screen**; the **registry** is the OS state that
remembers your workspace and schedule; `job-search-run` is the **scheduled job** that pulls and judges
postings; `evaluate-job-fit` is the **judge** that decides whether one posting fits;
`job-preference-interview` is the tool that **builds the brief** both of them read. You drive everything
from here and delegate the work itself to those skills.

**You never search the job source, judge a posting, or write `jobs.jsonl`, a run record, or a digest
here** — `job-search-run` owns the pull and `evaluate-job-fit` owns the verdict
(`../../shared/references/ownership.md`). The boundary is drawn by action, not by whether you were
invoked interactively: an interactive pull is still a pull, and a verdict reached in conversation is
still a verdict. About to call the job source, decide whether a posting is a match, or append an
`evaluated` event? Stop — invoke the owner instead. A hand-rolled search writes no ledger, so nothing
downstream can tell its result from a real run; a verdict reached without that skill's rubric skips the
adjacency rule that keeps a broadened match out of the top band.

This skill has two modes — it **routes**, then follows a playbook:

- **First run** → walk the user through onboarding end-to-end, ending with real, relevance-judged matches.
- **Returning** → show the job-search home (latest digest, new matches, pipeline) with conversational quick
  actions.

Find the workspace with the **Discovery procedure** in `../../shared/references/internals.md` (one fact-gathering
command, then its precedence rules); never hard-code its path.

## Step 0 — route

Run the Discovery procedure (`../../shared/references/internals.md`) → a workspace, **first_run** yes/no, and a source
(`registry | default | legacy | none`).

- `first_run: true` → **say the welcome, then** follow **`references/onboarding.md`** (the first-run
  playbook). Large: grep `^## ` for the section list. Greet the moment discovery reports
  `first_run: true` — emit the welcome as a message **now**, before your next tool call: before you open
  the playbook, before any check, long before the end of the turn. The pull to defer it is strong —
  finish the silent prep, batch the talking into one final message.
  Resist it: that batching is this skill's known failure mode, and whatever goes wrong next (a failed
  check, a blocked install) must land on a user who has already been greeted and told what's happening.
  About to run a tool without having greeted? Stop — greet first. The welcome — hit these beats in your own
  words (a warm one-liner: you'll set up their search together and end on real matches found live), e.g.:

  > "Let's set up your job search. I'll check a couple of prerequisites, make you a private workspace,
  > learn what you're looking for, save your first search, and then actually pull live postings and show
  > you the matches."

  Onboarding owns the workspace and tells the delegated skills where to write.
- `first_run: false` → follow **`references/home.md`** (the returning-user home). Gather its state
  silently; the home view itself is your first words.

That's the whole router: read the playbook you routed to and follow it.
Step 0 is mechanical — do it **silently**: no "discovery" / "OS state" / `registry` / `first_run` talk in your
reply (`../../shared/references/voice.md`). Your first user-facing words are the onboarding welcome (already said, above,
before the playbook was opened) or the home view.

Query work loads its own contract: whenever you derive or retune a search's queries, review the first run's
retrieval volume, or assess a saved search's query health, read `../../shared/references/query-strategy.md`
and follow it — it owns how a query portfolio is built and when to propose broader terms.

## Principles (apply in both modes)

- **Delegate the pull and the verdict.** Searching the job source is `job-search-run`'s and a fit verdict
  is `evaluate-job-fit`'s, in every mode — invoke the owner rather than doing either here, and if an owner
  can't run, stop and name the repair instead of standing in for it
  (`../../shared/references/ownership.md`).
- **Conversational-first configuration.** The user changes anything — a query, how often it runs, their
  preferences, the schedule — by **chatting with you**. You apply it by reading `<workspace>/config.yaml`,
  editing it minimally (preserving comments and structure), and writing it back, following the recipes in
  `../../shared/references/internals.md`. Hand-editing files is an escape hatch you mention only if asked — never a step
  you require.
- **Relevance is qualitative.** Say **relevant or not**, and if relevant **weak / moderate / strong**,
  always with plain-language reasoning; a preference's importance lives in which **bucket** it sits in, not
  in math. A fit score, a 0-to-100 scale, per-criterion points, or a category weight never lands in a
  digest, the brief, or the job log — the one exception is a number a user explicitly asks for in chat,
  which you may give in that reply but never save to an artifact.
- **Frequency, in human terms.** You tune the system by how often to pull — hourly, daily, weekly.
- **Every blocked path is a named error.** If something can't proceed (no CLI, no auth, no config, no brief,
  quota, service down…), name the exact `E-*` from `../../shared/references/errors.md` with its cause + fix wording and
  stop there. No silent failures, ever.
- **Never clobber real user data.** When adopting an existing workspace, only additively create what's
  missing — never overwrite a `config.yaml`, `preferences.md`, or `jobs.jsonl`. See the never-clobber rule
  in `../../shared/references/internals.md`.
- **Route feedback to the right scope.** When the user reacts — to a match, the digest, or what they want
  overall — apply it immediately at the correct scope and confirm in one line: a clear general preference
  edits the brief and, if a run is in flight, records a brief revision on it; a posting-specific reaction
  touches only pipeline state unless the user generalizes it; ambiguous feedback earns one clarification only
  when the reading changes the result; a retrieval change previews its agent-data impact first. The single
  routing table is `references/home.md` → **Applying your feedback** — follow it in both modes (it points
  one hop at the `run-lifecycle.md` revision/settling and `internals.md` usage contracts).

Read and follow exactly: `../../shared/references/internals.md` (OS state, discovery, never-clobber adoption, config
recipes, and the verbatim scheduling block), `../../shared/references/conventions.md` (workspace layout, `config.yaml`
schema, `jobs.jsonl` statuses, digest format + counts line), `../../shared/references/errors.md` (every named error),
`../../shared/references/voice.md` (how every reply talks to the user — plain English, zero-context first-run asks,
render documents inline), `../../shared/references/update.md` (cached update signal + update banner), and
`../../shared/references/agent-data-contract.md` → **Auth** and **Pricing and metering** only (the
prerequisites and tier facts onboarding renders; the routes are `job-search-run`'s, not yours), plus
`../../shared/references/run-lifecycle.md` (invoke `lifecycle-fold.sh` and require `closed=true` for the
candidate's exact run_id before any record/digest is surfaced or a canary is trusted). These are the source of
truth; this skill never restates their details from memory.
