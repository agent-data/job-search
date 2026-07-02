# Product Sense

This document captures **product judgment**: who the user is, the stances that shape every
feature decision, and — most importantly — what we deliberately refuse to build and why. For the
*engineering and agent-first principles* that enforce these stances mechanically, see
[docs/design-docs/core-beliefs.md](design-docs/core-beliefs.md).

**Read the [Non-goals](#non-goals-yagni--the-heart-of-this-doc) section first — it is the heart of
this doc.** The stances tell you what the product *is*; the non-goals tell you what it
refuses to become and why, which is the part most likely to be re-litigated. Jump table:
[Who this is for](#who-this-is-for) · [Product stances](#product-stances) ·
[Non-goals (the heart)](#non-goals-yagni--the-heart-of-this-doc) ·
[How product sense is kept honest](#how-product-sense-is-kept-honest).

---

## Who this is for

Job Search is built for a single persona: a technically comfortable job seeker who wants their
search to run itself. They have Claude Code installed and can follow a five-minute setup, but they
do not want to babysit a dashboard, tune a scoring rubric, or reason about API credits. They
describe what they want once, in plain English, and then expect the system to surface relevant
matches on a schedule — with enough reasoning to act on, and with nothing buried in a log file
when something goes wrong. The product turns Claude Code into their private job-search operating
system; their workspace, their data, their machine.

---

## Product stances

### Qualitative relevance over false precision

Job fit is a judgment, not arithmetic. The system decides **relevant or not**, and if relevant,
**weak / moderate / strong** — always accompanied by plain-language reasoning citing the posting
against the brief. There are no fit scores, no category weights, no per-criterion points. The
reasoning carries the weight; the band locates it in the digest. This stance is mechanically
enforced — see the **Qualitative, never numeric** and **Prose over knobs** beliefs in
[docs/design-docs/core-beliefs.md](design-docs/core-beliefs.md).

### Frequency, not budget

The only lever the user touches is how often the system runs. Cost surfaces in exactly one place
— the reactive quota error — and when it does, the fix is always a frequency change or a plan
upgrade, never credit arithmetic. For the exact wording of that error and the principle behind
it, see [shared/references/errors.md](../shared/references/errors.md) and the **Frequency, not
budget** belief in [docs/design-docs/core-beliefs.md](design-docs/core-beliefs.md).

### Privacy as a promise

The workspace is the user's private data — preferences, matched postings, run logs, resumes. It
ships with a deny-all `.gitignore` and setup refuses to scaffold inside a directory whose `.git`
points at a public remote. The workspace layout and the "never committed" contract are owned by
[shared/references/conventions.md](../shared/references/conventions.md). For how this is enforced
(culturally and mechanically), see the **Private & local** belief in
[docs/design-docs/core-beliefs.md](design-docs/core-beliefs.md).

### Prose over knobs

Preferences are a brief — a short prose document with must-haves, strong preferences,
nice-to-haves, and red flags — not a rubric with weights attached. A preference's importance
lives in which bucket it sits in, not in a number. Users change preferences by talking to the
agent; hand-editing `config.yaml` is an escape hatch, not a requirement. The brief shape and
the conversational-first configuration principle are both captured in
[docs/design-docs/core-beliefs.md](design-docs/core-beliefs.md).

### The magical moment and zero-friction T0

Within about five minutes of installing, the user sees real, live postings judged against their
own brief — strong, moderate, or weak, with reasoning — without writing a single file by hand.
That first digest is the **magical moment**: the product stops being abstract and starts being
useful. Every step in onboarding either directly builds toward that moment or gates it safely.
The full onboarding flow, TTFV target, and friction-killer decisions are specified in
[docs/product-specs/new-user-onboarding.md](product-specs/new-user-onboarding.md).

### Docs-as-product

The documentation, the named errors, and the knowledge base are part of the product surface, not
an afterthought. Every failure mode is named and carries its own fix; every pillar doc is
mechanically checked for broken links and drift from the shared-references source of truth.
This stance is enforced by the philosophy guard and `doc_lint` — see the **Docs-as-product**
belief in [docs/design-docs/core-beliefs.md](design-docs/core-beliefs.md).

---

## Non-goals (YAGNI) — the heart of this doc

These are the things we explicitly refuse to build in v1, each with the reasoning behind the
decision.

- **Numeric scoring, category weights, salary parsing.** A score invites false precision and
  shifts the user's attention from writing better preferences to tuning a rubric. `salary_display`
  is treated as opaque text; parsing it would require arithmetic the model can only approximate.
  Qualitative bands plus reasoning are more honest and more actionable.

- **Credit budgeting and cost dashboards.** Users cannot predict per-call costs, so a budget knob
  forces reasoning over a number they cannot control. Frugal-by-behavior design (dedup, judge from
  the free summary first, detail reads only for promising matches) keeps usage modest without any
  user-visible math. The one place cost can ever surface — a quota limit — is handled reactively
  as a named error; see [shared/references/errors.md](../shared/references/errors.md).

- **Multi-source aggregation — shipped 2026-07; the non-goal's own trigger fired.** This entry
  previously refused multi-source aggregation "before a second source exists," naming the seam
  as sufficient. That condition ended when the Job Postings API shipped per-source selection
  (Ashby live, Workday experimental) — see the contract in
  [shared/references/agent-data-contract.md](../shared/references/agent-data-contract.md). We added client-side fan-out over that one
  parameterized contract — per-source circuit breakers, a composite dedup key, conservative
  cross-source merging — **not** a source-plugin system; the seam held as designed. Still
  refused: a descriptor/plugin layer before a fourth source earns it.

- **A dedicated pipeline/triage-board skill.** The `status` field on each job event (tracked in
  [shared/references/conventions.md](../shared/references/conventions.md)) and the per-run digest
  cover the v1 tracking need. A full triage board is meaningful only once the user has accumulated
  enough matches and an established workflow; building it now would be premature.

- **Cloud sync, hosted dashboard, email/Slack notifications.** The product's identity is
  local-first: the workspace lives on the user's machine, runs are driven by Claude Code's native
  `/loop`, and the digest is a file. Adding cloud infrastructure inverts that identity and
  introduces data-custody questions for sensitive job-search PII. A desktop notification on a
  blocked run (when action is needed) is the narrow exception — configured locally.

- **Scraping application URLs.** The agent-data Job Postings API deliberately does not expose
  `application_url`. Surfacing apply links would imply the product is a one-click application
  tool; it is a relevance filter and research aid. That boundary also keeps the product from
  being mistaken for automation that submits applications without the user's intent.

---

## How product sense is kept honest

Two mechanical backstops prevent product sense from drifting as the codebase evolves.

The **philosophy guard** (`scripts/philosophy_guard.py`) scans shipped artifacts — digests,
templates, examples — and fails the build if a numeric fit score, a category weight, or a
budget/cost config field appears. This makes the qualitative-over-numeric and frequency-over-
budget stances hard constraints, not just intentions.

The **doc linter** (`scripts/doc_lint.py`) checks that every live KB doc links shared/references
rather than restating contract literals, that every Markdown link resolves, and that the index
files stay complete. Together they ensure the docs-as-product stance is enforced structurally.

The **maturity scorecard** at [docs/QUALITY_SCORE.md](QUALITY_SCORE.md) grades every product
domain and architectural layer against known gaps — re-graded as the code changes. It is the
on-demand product-health snapshot.

For the full system rationale, the OS model, and the layer map, see
[ARCHITECTURE.md](../ARCHITECTURE.md) and [docs/design-docs/index.md](design-docs/index.md).
