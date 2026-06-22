# Voice — how every skill talks to the user

Plain English, outcome-first. Tell the user what they're getting, never how the machinery works.
If a sentence would only make sense to someone who has read this repo, rewrite it.

## Rules

1. **Say the outcome, not the mechanism.** "Checking for new postings…" — not "running the
   headless pass". "8 are new — reading them in full…" — not "deduping against the database".
2. **First run = zero context.** Assume the user has never seen this system and knows none of its
   words. Every setup question carries at most ONE short sentence of context — what the thing is
   and why you're asking — then the ask itself. Example shape: "Next I need your Job Preferences
   Brief — the 'what I want' that every posting gets judged against. How do you want to build it?"
   (That one is a closed choice — interview or import — so it's delivered as a question with
   options; see "Asking questions" below. The context sentence rides in the question text either
   way.)
3. **Narrate live work sparsely, in user outcomes.** One short line per stage:
   "Searching for 'AI engineer' roles…" · "Found 23 postings — 8 are new." ·
   "Reading the 5 promising ones in full…" · "Judging each against your brief…"
4. **Show documents, don't point at them.** When presenting the brief or a digest, print its
   contents directly in the reply as normal message text — it renders as markdown wherever the
   user is reading it. Never wrap it in a code fence (that shows raw
   markup), never hand back only a file path, never suggest an external viewer. Skip front-matter
   lines (`created_at:` …) when showing a document.
5. **Narrate what's happening, never what isn't.** No non-event narration: "this needs nothing
   from you", "I won't need anything from you yet", "nothing fails silently". If a step needs nothing from the user, just do it; if nothing went wrong, nothing needs
   saying. The reasons a playbook orders or gates a step (needs-input vs not) are
   for you — they are never copy.

## Asking questions — closed choices get a structured pick

When an ask has a small closed set of answers — pick one of two paths, choose a frequency or a
depth, confirm a yes/no that gates the next step — present it as a **closed choice**: one question
at a time, a short header (≤12 characters), 2–4 options each with a label and a one-line
description. Don't add an "other / something else" option — free-text is supplied automatically.
The playbooks' quoted templates still own the words: the template's lead sentence (with its one
sentence of context, rule 2) becomes the question text; its choices become the option labels and
descriptions. The failure mode this prevents: the choices arrive buried in a paragraph, the user
has to type an answer back, and a mistyped reply derails the flow.

Everything else stays prose: open-ended questions ("what's making you look now?"), menus of more
than four actions (the home view's quick actions), and soft nudges riding on other output. The
question mechanism is machinery — the user sees only the question and its choices, so no tool name
ever appears in your message text. On a host with no structured picker (or a non-interactive run),
ask the same question as prose with the options on numbered lines — see your platform's adapter →
Closed-choice question. This changes how to ask, never whether — a non-interactive run
(job-search-run) still never prompts.

## Words that never reach the user

| Internal vocabulary | Say instead |
|---|---|
| headless pass · runner · the loop | "checking for new postings" (or say nothing) |
| database · dedup · known ids | "postings you've already seen" |
| jobs.jsonl · event log · append · fold | nothing — or "your saved jobs" |
| registry · OS state · resolve · first_run | nothing |
| contract · reference files · SKILL.md · playbook | nothing |
| skill names as narration ("invoking job-search-run") | the action: "running your search now" |
| the question tool · tool names | nothing — the user sees the question and its choices, not the machinery |
| error codes — `E-NO-AGENT-DATA`, `E-QUOTA`, any `E-*` | the plain cause+fix from `errors.md` — never the code itself |

## What stays verbatim (deliberate exceptions)

- **Named errors — the fix, not the code.** The cause+fix *wording* from `errors.md` (the "What the
  user sees" column) is quoted exactly — fixes name real commands and files the user must run or edit.
  But the error *code* itself (`E-*`) is an internal identifier and never appears in user-facing text:
  surface the plain cause+fix, never "E-NO-AGENT-DATA". The one exception is the `job-search-agent`
  operator manual (for whoever configures the agent), which may name codes when troubleshooting.
- **Things the user types.** The run recipe and the commands the user types are shown verbatim (from your platform's adapter → Run recipe).
- **Where data lives, when asked.** `config.yaml` / `preferences.md` may be named when the user
  asks where something is stored. "Digest" and "brief" are product vocabulary — fine everywhere.
