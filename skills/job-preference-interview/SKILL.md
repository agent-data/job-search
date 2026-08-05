---
name: job-preference-interview
description: Build, refine, deepen, or import the user's Job Preferences Brief — a quick free-form sketch from one question, a standard interview, or a thorough pass — producing a prose preferences.md (Summary, Must-haves/dealbreakers, Strong preferences, Nice-to-haves, Red flags). Use when the user wants to define or change what they want in a job, or to go deeper than a first-run quick sketch — "set up my job preferences", "what I want in a job", "redo my preferences interview", "change my must-haves", "make my brief more thorough", "import my preferences brief". Not the front door or home view (→ job-search), and not for judging a specific posting (→ evaluate-job-fit).
---

# job-preference-interview

> To configure, extend, customize, or troubleshoot the agent itself (or understand its
> capabilities), use the **job-search-agent** skill — the operator manual.

Build the user's **Job Preferences Brief** — the prose `preferences.md` that `evaluate-job-fit` later reads next
to a posting to judge it. This skill asks questions and waits for the answers, so it runs with the user present;
a scheduled run has nobody to answer. Your first words open the conversation itself, not the mechanics behind it.
How you say everything here — a word defined where it first lands, one question at a time, state in the present
tense — follows the ten rules under **How to communicate** in `../job-search/SKILL.md`.

The brief is prose a model reads against a posting to judge it **qualitatively**: relevant or not, and if relevant
weak / moderate / strong, with plain-language reasoning. Importance lives in which **bucket** a factor lands in —
must-have vs. strong preference vs. nice-to-have — never in math: no fit score, no numeric scale, no per-category
points or weights, and no asking the user to rank categories against each other numerically. Compensation, hours,
and the like are captured in plain words: at least ~$180K base, no regular on-call.

## Where it writes
Find the workspace with the discovery step in the `job-search-runbook` skill; the brief is the path
`workspace.preferences_path` names in that workspace's `config.yaml`, default `preferences.md`. When no workspace
is set up yet, write to the resolved default path and say in one line where the brief went.

A brief that already exists is an **update**: read it first, fill the gaps, and confirm changes rather than
overwriting. Copy the front matter — and the whole finished shape — from this skill's
`templates/preferences.example.md`. A new brief carries today's date in both `created_at` and
`updated_at`; an update keeps `created_at` and moves `updated_at` to today, because the home view
measures staleness from `updated_at`. When the user changes the brief while a search is running,
writing the updated brief is still your whole job; what the running search does with it is the
job-search front door's feedback routing.

## How deep to go
What the user asked for decides. Someone who wants to move fast, or a hand-off from the front door asking for a
sketch, gets the **quick sketch**; anyone else gets the **interview** — and when they ask for a thorough pass,
work every dimension with follow-ups and fill all four buckets. Say that a brief can be deepened anytime, since a
later pass reads what exists and enriches it, and either path produces the same five-section brief.

### Quick sketch
1. Ask one question — what they are after in a sentence or two: role, where, pay floor, and anything that is a
   dealbreaker. Take whatever they give you.
2. Draft the five-section brief from **only what they actually said**, plus *safe, direct* implications (an
   on-call **red flag** from wanting good work-life balance). A stated role, location, or pay floor becomes a
   **Must-have**; softer wants go to **Strong preferences** or **Nice-to-haves**. A section they said nothing
   about stays empty rather than padded with preferences they never expressed. Ask **at most one** follow-up, and
   only where the user answered here and a likely must-have is missing entirely; a sketch handed to you with its
   answer already in it is drafted from those words, and the gaps wait for a deeper pass.
3. Material they share — a resume, a cover letter, notes — is **background evidence** that informs the brief,
   never an existing brief and never silently turned into must-haves; where it conflicts with what they said,
   what they said wins.
4. Write it, show it rendered in your reply, say in one line where it went, and tell them a deeper interview can
   sharpen it whenever they want. Then hand back so they can run a search.

## Interview method
The interview works the dimensions below and skips whatever the user says does not matter — about 6–10 questions,
or 15–20 on a thorough pass.
- Ask **one main question at a time** (a single tight, directly-related follow-up is fine) and **wait** for the
  answer before moving on. **Adapt** — let each reply decide what to probe next.
- **Make vague answers concrete.** Good culture, decent pay, work-life balance each need a follow-up that turns
  them into something **observable** a reader could check against a posting: small teams, low meeting load, ships
  weekly; base at least ~$X.
- **Make answering easy.** Offer a few example options or a simple scale where it helps, and **always** leave room
  for no preference, skip, or that's a dealbreaker.
- Keep every message to one or two sentences, plus a closed choice's option lines — longer only when the user asks
  you to explain something at greater length.
- **Start** with what is prompting the search, **reflect back** every 4–5 questions in 1–2 sentences so the user
  can correct you, and **finish** when you have enough detail or the user says they are done.

## Dimensions to cover
Skip any the user says don't matter; add others that come up. For each, learn **what** they want, **how much it
matters** (which bucket), and **what would be a dealbreaker**.
1. **Role** — function, title, seniority, scope, day-to-day, IC vs. manager.
2. **Industry / domain / mission** — the kind of product, problem, or work.
3. **Company** — size, stage (early startup through enterprise), culture, values, reputation.
4. **Compensation** — base, bonus, equity, benefits, a minimum acceptable, as **prose**: ≥ ~$180K base.
5. **Location & arrangement** — remote / hybrid / onsite, geography, travel, relocation.
6. **Work-life balance** — hours, intensity, on-call, PTO, flexibility.
7. **Growth** — learning, promotion path, mentorship, skill development.
8. **Team & management** — team size, manager style, reporting lines, whether they manage.
9. **Tools / tech stack / skills / methods** used day to day.
10. **Stability vs. risk** — job security, funding stage, risk tolerance.
11. **Hard constraints / dealbreakers** — anything that is an automatic no.

## Calibration (qualitative buckets, NOT weights)
Once the dimensions are mostly covered, sort the factors into four buckets. That sorting is where importance
lives, and a relative ordering the user volunteers is captured in words inside its bucket.
- **Must-haves / dealbreakers** — absent or violated = automatic reject. Phrase each as a **binary, checkable**
  condition: remote within the US, or SF Bay onsite.
- **Strong preferences** — really want it; a strong match should hit most of these.
- **Nice-to-haves** — pluses, not requirements.
- **Red flags** — things whose presence makes a posting worse / a likely pass.

## Output: the brief
Write the prose document to the resolved path in the shape of this skill's `templates/preferences.example.md` —
the front matter, then these five sections in this order:
- **Summary** — 2–3 sentences capturing the ideal role in plain language.
- **Must-haves / dealbreakers** — the binary filters, each phrased so a reader can check it against a posting.
- **Strong preferences** — the heavily-wanted, non-binary criteria.
- **Nice-to-haves** — the pluses.
- **Red flags** — anti-preferences whose presence weighs against a posting.

Every item is **plain and observable** — something a reader could verify against a posting's text, not an internal
feeling — and a section the user gave nothing for keeps its heading and skips its bullets rather than carrying
filler. The brief ends with the one-line **How to use this** note the template closes with.

After writing, **show the user the brief itself** — print `preferences.md`'s body directly in your reply as normal
message text, rendered markdown outside any code fence, front-matter lines skipped — say in one line where it's
saved, and offer to refine any section.

## Import an existing brief
A user who already has a brief hands you a **file path** or **pasted prose** instead of an interview.
1. **Validate it's usable.** It should be prose with at least a **Summary** and **Must-haves**.
2. **Convert a numeric rubric or category weights** — a fit-score scale, per-category points, percentage weights.
   Tell the user this system is **qualitative only** and offer to convert the brief to prose: keep the criteria,
   drop the numbers, reshape into the five sections.
3. **Fill thin or vague sections** with a few targeted questions, asked the same one-question-at-a-time way.
4. Map its contents onto the five sections, add the front matter, and write the brief at the resolved path. Show
   it rendered in your reply the same way, and confirm in one line where it's saved.
