---
name: job-search
description: Set up, check on, and steer the user's job search — the front door and home screen. Use when they want to start or set up a job search, see status, matches, the latest digest, or the pipeline, or change what they're looking for — "set up job search", "start my job search", "I'm looking for a new job", "check my job search", "show me my matches", "what's new in my pipeline", or /job-search. First run onboards end-to-end; afterward it shows the job-search home with quick actions. Not for a fresh headless pull ("check for new jobs" → job-search-run) or for configuring/troubleshooting the agent itself (→ job-search-agent).
---

# job-search

> To configure, extend, customize, or troubleshoot the agent itself (or understand its
> capabilities), use the **job-search-agent** skill — the operator manual.

The **OS shell** for Job Search OS — the front door you run when you want to set the system up or check on
it. Mental model: this skill is the **login shell + home screen**; the **registry** is the OS state that
remembers your workspace and schedule; `job-search-run` is the **scheduled job** that pulls and judges
postings; `job-preference-interview` is the tool that **builds the brief** the runner reads. You drive
everything from here and delegate the heavy lifting to those skills.

Not the place for a non-interactive run — that's `job-search-run` (see your platform's adapter → Headless invocation) — or for changing the system's wiring,
which is `job-search-agent`'s manual (see the note above).

This skill has two modes and almost no logic of its own — it **routes**, then follows a playbook:

- **First run** → walk the user through onboarding end-to-end, ending with real matches found seconds ago.
- **Returning** → show the job-search home (latest digest, new matches, pipeline) with conversational quick
  actions.

Find the workspace with the **Discovery procedure** in `../../shared/references/internals.md` (one fact-gathering
command, then its precedence rules); never hard-code its path.

## Step 0 — route

Run the Discovery procedure (`../../shared/references/internals.md`) → a workspace, **first_run** yes/no, and a source
(`registry | default | legacy | none`).

- `first_run: true` → **say the welcome, then** follow **`references/onboarding.md`** (the first-run
  playbook). Greet the moment discovery reports `first_run: true` — emit the welcome as a message **now**,
  before your next tool call: before you open the playbook, before any check, long before the end of the
  turn. The pull to defer it is strong — finish the silent prep, batch the talking into one final message.
  Resist it: that batching is this skill's known failure mode, and whatever goes wrong next (a failed
  check, a blocked install) must land on a user who has already been greeted and told what's happening.
  About to run a tool without having greeted? Stop — greet first. The welcome, verbatim or close to it:

  > "Let's set up your job search. I'll check a couple of prerequisites, make you a private workspace,
  > learn what you're looking for, save your first search, and then actually pull live postings and show
  > you the matches."

  Onboarding owns the workspace and tells the delegated skills where to write.
- `first_run: false` → follow **`references/home.md`** (the returning-user home). Gather its state
  silently; the home view itself is your first words.

That's the whole router. Everything else is in the two playbooks; read the one you routed to and follow it.
Step 0 is mechanical — do it **silently**: no "discovery" / "OS state" / `registry` / `first_run` talk in your
reply (`../../shared/references/voice.md`). Your first user-facing words are the onboarding welcome (already said, above,
before the playbook was opened) or the home view.

## Principles (apply in both modes)

- **Conversational-first configuration.** The user changes anything — a query, how often it runs, their
  preferences, the schedule — by **chatting with you**. You apply it by reading `<workspace>/config.yaml`,
  editing it minimally (preserving comments and structure), and writing it back, following the recipes in
  `../../shared/references/internals.md`. Hand-editing files is an escape hatch you mention only if asked — never a step
  you require.
- **No numeric relevance.** Relevance is qualitative — **relevant or not**, and if relevant **weak /
  moderate / strong**, with plain-language reasoning. Never show or invent a fit score, a 0-to-100 scale,
  per-category points, or category weights. Importance lives in which **bucket** a preference is in, never in
  math.
- **Frequency, in human terms.** You tune the system by how often to pull — hourly, daily, weekly.
- **Every blocked path is a named error.** If something can't proceed (no CLI, no auth, no config, no brief,
  quota, service down…), name the exact `E-*` from `../../shared/references/errors.md` with its cause + fix wording and
  stop there. No silent failures, ever.
- **Never clobber real user data.** When adopting an existing workspace, only additively create what's
  missing — never overwrite a `config.yaml`, `preferences.md`, or `jobs.jsonl`. See the never-clobber rule
  in `../../shared/references/internals.md`.

Read and follow exactly: `../../shared/references/internals.md` (OS state, discovery, never-clobber adoption, config
recipes, and the verbatim scheduling block), `../../shared/references/conventions.md` (workspace layout, `config.yaml`
schema, `jobs.jsonl` statuses, digest format + counts line), `../../shared/references/errors.md` (every named error),
`../../shared/references/voice.md` (how every reply talks to the user — plain English, zero-context first-run asks,
render documents inline), `../../shared/references/update.md` (cached update signal + update banner, shown only where the adapter declares a verified update recipe), and
`../../shared/references/agent-data-contract.md` (the source contract `job-search-run` honors). These are the source of
truth; this skill never restates their details from memory.
