---
name: job-preference-interview
description: Build or update the user's Job Preferences Brief at a depth they choose — a quick free-form sketch (~1 question), a standard interview, or a thorough pass — producing a prose preferences.md (Summary, Must-haves/dealbreakers, Strong preferences, Nice-to-haves, Red flags). Imports an existing brief too, and can deepen a light brief later. Use when the user wants to set up or refine what they want in a job, or when job-search onboarding needs a brief: "set up my job preferences", "what I want in a job", "redo my preferences interview", "change my must-haves", "import my preferences brief". Not for judging a specific posting (→ evaluate-job-fit).
disable-model-invocation: false
user-invocable: true
---

# job-preference-interview

> To configure, extend, customize, or troubleshoot the agent itself (or understand its
> capabilities), use the **job-search-agent** skill — the operator manual.

Build the user's **Job Preferences Brief** at a depth they choose — from a one-line sketch to a thorough
interview — the prose `preferences.md` that `evaluate-job-fit` later reads next to a posting to judge it.
Follow `references/voice.md` for how you talk and how you present the finished brief — and don't narrate
setup mechanics (no "resolving the workspace", no reference-file talk; your first words open the
conversation itself).

## Purpose
Produce a **prose** brief a model can read against a job posting and judge it **qualitatively**:
relevant or not, and if relevant weak / moderate / strong, with plain-language reasoning. The brief is the
"what I want" half of the system; `evaluate-job-fit` is the reader.

**No numbers.** Do not produce a fit score, a numeric scale, per-category point values, or category weights, and
do not ask the user to rank categories against each other numerically. Importance is expressed by which **bucket** a
factor lands in (must-have vs. strong preference vs. nice-to-have), never as math. Capture compensation, hours,
and the like as plain words ("at least ~$180K base", "no regular on-call"), never as a formula.

This skill is **interactive only** — it asks questions and waits for answers. Never invoke it in a headless or
scheduled run.

## Where it writes
Resolve `$OS` (`scripts/osctl.py`) from **this skill's own directory** (`${CLAUDE_SKILL_DIR}/scripts/…` as a
plugin), never cwd; find the workspace with `python3 "$OS" resolve` and never hard-code its path.

```
python3 "$OS" resolve   →  {"workspace":"<abs>","first_run":<bool>,"source":"registry|default|legacy|none"}
```

- Write the brief to `<workspace>/<config.workspace.preferences_path>` (default `preferences.md`).
- If `resolve` reports `first_run: true` **and** you were invoked standalone (no workspace set up yet), write
  to the resolved default path anyway and tell the user exactly where it went. (If onboarding owns the
  workspace, it tells you where to write.)
- If a `preferences.md` already exists, you are **updating** it — read it first, fill gaps, and confirm changes
  rather than silently overwriting.
- Put `created_at:` and `updated_at:` front-matter lines at the top, matching
  `templates/preferences.example.md`. On a **new** brief set both to today; on an **update** keep `created_at`
  and refresh `updated_at` to today — the home view measures staleness from `updated_at`:

  ```
  ---
  created_at: 2026-06-05
  updated_at: 2026-06-08
  ---
  # Job Preferences Brief
  ...
  ```

## Choose a depth (offer all three; give the question estimate)
Before you ask anything, let the user choose how deep to go — and make clear they can **start light and deepen
later** (a follow-up interview reads the existing brief and *enriches* it, never overwrites). **The depth ask
happens even when another skill invoked you.** Onboarding's hand-off, an args string ("standard interview",
"one question at a time"), or any invoker's description of this skill never counts as the user's choice — only
the user's own words do (they already said "just a quick sketch" / "make it thorough" → honor that and skip
the ask). The failure mode: an invoker pre-picks "standard", the depth question silently disappears, and the
user never learns a one-question sketch existed.

Ask it with the question tool (`references/voice.md` → Asking questions). Header `Depth`; question: "This
brief is the plain-English 'what I want' that every job posting gets judged against. How deep do you want to
go? You can always come back for a deeper pass later."; options:

1. **Quick sketch** — "~1 question — describe what you want in a sentence or two; see matching jobs right away."
2. **Standard interview** — "~6–10 questions, one at a time, over what matters most."
3. **Thorough interview** — "~15–20 questions across every dimension, for the most precise brief."

(Standalone only — not mid-onboarding, where import was just declined — add a fourth option: **Import** —
"already have one written down? Paste it or give me the path.")

Whatever the depth, the **output is the same five-section brief** (below): depth changes how much you ask, not
the shape of the result. If a brief already exists, any path **updates** it — read it first, fill gaps, and
confirm changes rather than overwriting.

### Quick sketch — the fast escape hatch
For users who'd rather see jobs now than answer questions:
1. Ask once: *"In a sentence or two — what are you after? (role, where, pay floor, anything that's a
   dealbreaker)"*. Take whatever they give you; don't push for more.
2. Draft the five-section brief from **only what they actually said**, plus *safe, direct* implications (e.g. an
   on-call **red flag** from "good work-life balance") — a stated role / location / pay floor becomes a
   **Must-have**, softer wants go to **Strong preferences / Nice-to-haves**. **Don't invent preferences they
   didn't express**; leave a section empty rather than padding it — they can deepen it later. Ask **at most one**
   follow-up, and only if a likely must-have is missing entirely.
3. Write it, **show it rendered in your reply** (no code fence), say in one line where it went, and tell the
   user plainly they can **run a deeper interview anytime** to sharpen it — then hand back so they can run a
   search.

## Interview method
This is the **Standard** and **Thorough** path — same method, different coverage. **Standard** (~6–10 questions)
works the core dimensions below and skips whatever the user says doesn't matter. **Thorough** (~15–20) works
through *every* dimension with follow-ups and deliberately fleshes out all four buckets — nice-to-haves and red
flags included.

### Standing rules (apply to every question)
- Ask **one main question at a time** (a single tight, directly-related follow-up is fine). **Wait** for the
  answer before moving on. Never dump a long checklist of questions.
- **Adapt** to answers — let each reply decide what to probe next.
- **Make vague answers concrete.** When you hear "good culture", "decent pay", "work-life balance", ask a
  follow-up that turns it into something **observable** a reader could actually check against a posting
  ("good culture" → "small teams, low meeting load, ships weekly"; "decent pay" → "base at least ~$X").
- **Make answering easy.** Offer a few example options or a simple scale when it helps, and **always** let the
  user say "no preference", "skip", or "that's a dealbreaker". When a question is a genuine pick-one with 2–4
  natural answers (IC vs. manager; remote / hybrid / onsite), ask it with the question tool — options as
  labels, the automatic free-text option catching "no preference" and nuance; open questions stay prose
  (`references/voice.md` → Asking questions).
- Keep every message short. Don't lecture or pad.

### Flow
1. **Start** with the user's current situation and what's prompting the search ("What's making you look now?"),
   then work through the dimensions below.
2. **Reflect back every 4–5 questions** in 1–2 sentences so the user can correct you.
3. **Finish** when you have enough detail or the user says they're done — then write the brief.

## Dimensions to cover
Skip any the user says don't matter; add others if they come up. For each, learn **what** they want, **how much
it matters** (which bucket), and **what would be a dealbreaker**.

1. **Role** — function, title, seniority, scope, day-to-day, IC vs. manager.
2. **Industry / domain / mission** — the kind of product, problem, or work.
3. **Company** — size, stage (early startup → enterprise), culture, values, reputation.
4. **Compensation** — base, bonus, equity, benefits, and a minimum acceptable. Capture as **prose**, never as
   math ("≥ ~$180K base; equity matters; benefits flexible").
5. **Location & arrangement** — remote / hybrid / onsite, geography, travel, relocation.
6. **Work-life balance** — hours, intensity, on-call, PTO, flexibility.
7. **Growth** — learning, promotion path, mentorship, skill development.
8. **Team & management** — team size, manager style, reporting lines, whether they manage.
9. **Tools / tech stack / skills / methods** used day to day.
10. **Stability vs. risk** — job security, funding stage, risk tolerance.
11. **Hard constraints / dealbreakers** — anything that's an automatic no.

## Calibration (qualitative buckets, NOT weights)
At a natural point — once the dimensions are mostly covered — sort the factors into four buckets. This replaces
any scoring: importance lives in the bucket, full stop.

- **Must-haves / dealbreakers** — absent or violated = automatic reject. Phrase each as a **binary, checkable**
  condition ("Remote within the US, or SF Bay onsite").
- **Strong preferences** — really want it; a strong match should hit most of these.
- **Nice-to-haves** — pluses, not requirements.
- **Red flags** — things whose presence makes a posting worse / a likely pass.

Do **not** ask the user to assign numbers or weights, and do **not** ask how categories trade off against each
other numerically. If they volunteer a relative ordering, capture it in words inside the bucket.

## Output: the brief
Write the prose document to the path above, with **exactly** these sections —
`references/conventions.md` ("preferences.md — prose brief") owns the authoritative set (names + order);
the gloss below is orientation, not a second source of truth:

- **Summary** — 2–3 sentences capturing the ideal role in plain language.
- **Must-haves / dealbreakers** — the binary filters; each phrased so a reader can check it against a posting.
- **Strong preferences** — the heavily-wanted, non-binary criteria.
- **Nice-to-haves** — the pluses.
- **Red flags** — anti-preferences whose presence weighs against a posting.

Every item is **plain and observable** — something a reader could verify against a posting's text, not an
internal feeling. Skip an empty section's bullets rather than inventing filler.

End the brief with a one-line **How to use this** note, e.g.:

> _How to use this: Claude reads this brief next to a job posting and judges whether it's relevant, and if so
> whether it's a weak, moderate, or strong match — with reasoning. No score._

After writing, **show the user the brief itself** — print `preferences.md`'s body directly in your reply as
normal message text (rendered markdown; no code fence, skip the front-matter lines — see
`references/voice.md`), say in one line where it's saved, and offer to refine any section.

## Import an existing brief
If the user already has a brief, accept a **file path** or **pasted prose** instead of interviewing from
scratch.

1. **Validate it's usable.** It should be prose with at least a **Summary** and **Must-haves**.
2. **If it carries a numeric rubric or category weights** (a fit-score scale, per-category points, percentage
   weights), tell the user this system is **qualitative only** and offer to **convert it to prose** — keep the criteria,
   drop the numbers, and reshape into the five sections above.
3. **If it's thin** (missing sections, vague items), offer a few targeted enrich questions to fill the gaps —
   using the same one-question-at-a-time method.
4. Map its contents onto the five sections, add the `created_at:` + `updated_at:` front-matter lines, and write
   `preferences.md` at the resolved path. Show the finished brief rendered in your reply the same way (no
   code fence), and confirm in one line where it's saved.
