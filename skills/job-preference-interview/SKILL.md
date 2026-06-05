---
name: job-preference-interview
description: Build or update the user's Job Preferences Brief through a one-question-at-a-time interview, producing a prose preferences.md (Summary, Must-haves/dealbreakers, Strong preferences, Nice-to-haves, Red flags). Also imports an existing brief. Use when the user wants to set up or refine what they want in a job, or when job-search onboarding needs a brief.
disable-model-invocation: false
user-invocable: true
---

# job-preference-interview

Interview the user, one question at a time, to build their **Job Preferences Brief** — the prose
`preferences.md` that `evaluate-job-fit` later reads next to a posting to judge it.

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
Resolve the workspace with the bundled `osctl.py`. It is copied into this skill's own directory at
`scripts/osctl.py`; resolve its absolute path **from this skill's directory** (e.g.
`${CLAUDE_SKILL_DIR}/scripts/osctl.py` when installed as a plugin) and use it below as `$OS` — exactly as the
sibling skills resolve `$STATE`. Never hard-code or re-derive the workspace path.

```
python3 "$OS" resolve   →  {"workspace":"<abs>","first_run":<bool>,"source":"registry|default|legacy|none"}
```

- Write the brief to `<workspace>/<config.workspace.preferences_path>` (default `preferences.md`).
- If `resolve` reports `first_run: true` **and** you were invoked standalone (no workspace set up yet), write
  to the resolved default path anyway and tell the user exactly where it went. (If onboarding owns the
  workspace, it tells you where to write.)
- If a `preferences.md` already exists, you are **updating** it — read it first, fill gaps, and confirm changes
  rather than silently overwriting.
- Put a `created_at: YYYY-MM-DD` line at the top in front-matter style, matching
  `templates/preferences.example.md`:

  ```
  ---
  created_at: 2026-06-05
  ---
  # Job Preferences Brief
  ...
  ```

## Interview method
- Ask **one main question at a time** (a single tight, directly-related follow-up is fine). **Wait** for the
  answer before moving on. Never dump a long checklist of questions.
- **Start** with the user's current situation and what's prompting the search ("What's making you look now?"),
  then work through the dimensions below.
- **Adapt** to answers — let each reply decide what to probe next.
- **Make vague answers concrete.** When you hear "good culture", "decent pay", "work-life balance", ask a
  follow-up that turns it into something **observable** a reader could actually check against a posting
  ("good culture" → "small teams, low meeting load, ships weekly"; "decent pay" → "base at least ~$X").
- **Make answering easy.** Offer a few example options or a simple scale when it helps, and **always** let the
  user say "no preference", "skip", or "that's a dealbreaker".
- **Reflect back every 4–5 questions** in 1–2 sentences so the user can correct you.
- Keep every message short. Don't lecture or pad.
- **Finish** when you have enough detail or the user says they're done — then write the brief.

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
Write the prose document to the path above, with **exactly** these sections (matching
`shared/references/conventions.md` and `templates/preferences.example.md`):

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

After writing, tell the user the file path and offer to refine any section.

## Import an existing brief
If the user already has a brief, accept a **file path** or **pasted prose** instead of interviewing from
scratch.

1. **Validate it's usable.** It should be prose with at least a **Summary** and **Must-haves**.
2. **If it carries a numeric rubric or category weights** (a fit-score scale, per-category points, percentage
   weights), tell the user this system is **qualitative only** and offer to **convert it to prose** — keep the criteria,
   drop the numbers, and reshape into the five sections above.
3. **If it's thin** (missing sections, vague items), offer a few targeted enrich questions to fill the gaps —
   using the same one-question-at-a-time method.
4. Map its contents onto the five sections, add the `created_at:` front-matter line, and write
   `preferences.md` at the resolved path. Confirm the path with the user.
