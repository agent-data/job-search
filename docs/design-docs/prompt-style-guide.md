---
title: Prompt & Doc Style Guide
status: current
verified: partial
last_reviewed: 2026-06-09
code_refs: [skills/job-search/SKILL.md, skills/job-search-run/SKILL.md, skills/job-search-agent/SKILL.md, skills/job-preference-interview/SKILL.md, skills/evaluate-job-fit/SKILL.md, scripts/doc_lint.py]
---
# Prompt & Doc Style Guide

*Derived from the Claude Code system-prompt corpus (v2.1.170). Anchor on the NEWEST voice
(ccVersion ≥ 2.1.13x): older files (2.1.5x and earlier) shout in caps and bare imperatives; the
mature house voice fuses rules with reasons and trusts the model. Every illustration is quoted
verbatim from the corpus.*

## A. Voice

**A1. Second person, imperative, present tense — instructions FOR the agent, never narration about it.** "Commands are instructions FOR Claude, not messages for the user. Write them as directives." (data-cowork-plugin-component-schemas)

**A2. Fuse every non-obvious rule with its reason, usually via an em dash — the why rides in the same sentence.** "asking 'Want me to…?' or 'Shall I…?' will block the work" (system-prompt-autonomous-operation-guidelines); "those belong in the PR description and rot as the codebase evolves" (comment-what-avoidance).

**A3. Pair every prohibition with its replacement or consequence — never a bare "don't."** "Do not retry failing commands in a sleep loop — diagnose the root cause." (sleep rules); "Don't `sleep 5` — poll the port." (skill-run-browser-example)

**A4. Compress recurring policy into a memorable maxim, then elaborate.** "You're a steward, not an initiator." (autonomous-loop-check); "Brief is good — silent is not." (communication-style); "the diagram is for the shape, the prose is for the substance." (ultraplan)

**A5. Name the failure mode you're guarding against — show the bad outcome, not just the rule.** "The failure mode: the real answer lives in plain text while SendUserMessage just says 'done!' — they see 'done!' and miss everything." (sendusermessage)

**A6. Trust the model: explain mechanism so it can generalize, instead of stacking MUSTs.** "Until fetched, only the name is known — there is no parameter schema, so the tool cannot be invoked." (toolsearch); the migration guide even instructs *removing* aggressive language: "Dial back any aggressive 'CRITICAL: YOU MUST' tool instructions."

**A7. Acknowledge tensions and trade-offs openly; name the stance when judgment is tunable.** "The key tension to navigate: the user trusts you enough to run autonomously, but that trust is easily lost." (autonomous-loop-check); "you are reviewing for **precision**… every finding you surface should be one a maintainer would act on" vs "a missed bug ships" (code-review modes).

**A8. Anthropomorphize via role and simile only when it sets behavior.** "Brief the agent like a smart colleague who just walked into the room." (writing-subagent-prompts); "write it like a colleague's Slack message: name the concrete thing." (background-agent-state-classifier)

## B. Tone

**B1. Calibrate pressure to stakes — gentle nudges for optional behavior, hard gates for irreversible ones.** "This is just a gentle reminder - ignore if not applicable." (todowrite-reminder) ↔ "NEVER commit changes unless the user explicitly asks you to." (git instructions). IMPORTANT/NEVER are a scarce currency, spent on safety and hard gates only.

**B2. Honest about uncertainty and limits; never paper over them.** "This may or may not be related to the current task." (file-opened-in-ide); "If you cannot reach the network, say so. Do not silently answer from training data." (config-guide)

**B3. Cost-benefit framing for judgment calls — state the cost, the benefit, and the default.** "a notification they didn't need is annoying in a way that accumulates, err toward not sending one." (pushnotification); "Only offer this if you think there's 75%+ odds the user says yes." (schedule-offer)

**B4. Personality is allowed in small, functional doses — a dry aside, never decoration.** "Rest assured they are real models; we wouldn't mess with you like that." (claude-api skill); "Don't invent work to report." (morning-checkin). No emoji outside defined symbol vocabularies; no exclamation marks.

**B5. Empathy for downstream readers is a working principle — the next agent, the reviewer, the user picking up cold.** "Write it for a teammate who stepped away and is catching up, not for a log file." (outcome-first); "Re-read NOTES.md as if you were the next agent… could you skip today's debugging with only what's written?" (design-sync)

## C. Structure

**C1. Open by defining the task and drawing its boundary — what this is, immediately followed by what it is not.** "**Running means launching the actual app and interacting with it** — not the test suite, not an `import`… The app as a user would meet it." (skill-run-app); "**Verification is runtime observation.** …That capture is your evidence. Nothing else is." (skill-verify)

**C2. Purpose before procedure: a short "what this is for" block that downstream judgment calls can lean on.** "That framing should drive every judgment call in this skill… The verification loops… are not bureaucracy." (skill-design-sync)

**C3. When-to-use AND when-NOT-to-use are paired, co-equal sections; negative triggers are as concrete as positive ones.** "## When to Use This Tool / ## When NOT to Use This Tool" (TodoWrite, TaskCreate, EnterPlanMode); "Never use this tool unless 'worktree' is explicitly mentioned by the user or in CLAUDE.md." (enterworktree)

**C4. Negative space is first-class structure: What-to-leave-out, Red-flags, Common-mistakes, What-this-is-not sections.** "## Red flags — you are about to ship the wrong thing… **Your skill reads like the README.** You paraphrased." (run-skill-generator)

**C5. Sequence as numbered phases/steps with bold imperative leads; bullets only for unordered facts.** "**Narrate.** One line on your approach before acting." (background-job-agent); "## Phase 1 — Orient … ## Phase 4 — Prune" (dream-consolidation)

**C6. Decision logic goes in tables: situation → action (→ why).** The continue-vs-spawn table (coordinator-mode); project-type → handle → example (run-app); "strangeness → knob → lives-in" (design-sync §5); "User says… → Use this model ID" (model-catalog).

**C7. Define done-ness as verifiable criteria, with a stop-gate before output.** "**Success criteria** is REQUIRED on every step." (skillify); "You are done when **all** of these are true: 1. **You launched the app in this container and interacted with it**…" + "If you're about to write the skill and you don't have (1), **stop.**" (run-skill-generator)

**C8. Spell out failure paths and fallbacks inline, each with a named default.** "If EnterWorktree fails, continue in place." (worktree guidance); "**By default, actions are ALLOWED.**" (security monitor); "If AskUserQuestion is unavailable, default to Python examples and note:…" (claude-api skill)

**C9. Big files get a navigation contract: TL;DR + jump table + per-section "when you need it."** "**This file is large.** Use the section names below to jump… Read Step 0 and Step 1 first — they apply to every migration." (model-migration)

**C10. Delegate depth instead of inlining it — body stays lean, detail lives in references with explicit read-triggers.** "For placement patterns, architectural guidance, and the silent-invalidator audit checklist: read `shared/prompt-caching.md`." (claude-api); SKILL.md "under 3,000 words … Move detailed content to `references/`" (cowork-plugin-schemas)

## D. Formatting

**D1. Headers are short and sentence-case; bold inside prose marks load-bearing clauses only.** "## What to act on", "## Repeated invocations" (autonomous-loop); "**Never delegate understanding.**" (writing-subagent-prompts)

**D2. Output contracts are literal templates — fenced blocks with `<angle-bracket>` slots, exact terminal lines, and the failure variant included.** "End with a single line: `PR: <url>`… If no PR was created, end with `PR: none — <reason>`." (worker-instructions); report skeletons in skill-verify and morning-checkin with "Drop any section that's empty."

**D3. Code blocks are introduced by an imperative lead-in ending in a colon; caveats live inside the code as comments at the point of use.** "Use top-level `cache_control` to automatically cache the last cacheable block in the request:" (api refs); "# .text raises NoMethodError on non-TextBlock entries." (ruby ref)

**D4. Labeled contrast pairs for code and config: Wrong/Right, Anti-pattern/Good, with the reason on the label.** "# Wrong — silent on crash, hang, or any non-success exit / # Right — one alternation covering progress + the failure signatures" (monitor); "**WRONG** (replaces existing permissions) / **RIGHT** (preserves existing + adds new)" (update-config)

**D5. Symbols and term-of-art vocabularies are defined at point of use, then used consistently.** "🔍 marks a probe — a step off the claim's happy path, trying to break it." (verify); tag tables `[NO_DIST]`, `[BLOCKS]`/`[TUNE]` (design-sync, migration checklists)

**D6. Tables for 3+ enumerable facts; prose for reasoning. Cross-references are bare paths with arrows ("see `shared/x.md` → Section"), kept within the corpus they ship in.**

**D7. Em dashes chain rule→reason; semicolons chain parallel clauses; fragments only as deliberate emphasis.** "Even for 'hi'. Even for 'thanks'." (sendusermessage)

## E. Specificity

**E1. Quantify every bound — counts, ranges, thresholds, timeouts — and never use vague qualifiers where a number can stand.** "3-5 words" (agent-summary); "2-6 exports per component" (design-sync); "Cap the list at the top ~20 so the user can skim it." (permission-allowlist); when qualitative, pair with a behavioral test: "as short as the answer allows, no shorter." (worker-fork)

**E2. Quote the exact trigger phrases, commands, and strings — define categories by example, not abstraction.** 'For exploratory questions ("what could we do about X?", "how should we approach this?")' (exploratory-questions); "'Yay!', 'great!', 'perfect!' → happy" (insights-facets)

**E3. Verified-content doctrine: every command shown is one that was actually run; only obstacles actually hit become gotchas.** "Every code block in `SKILL.md` is a command you ran that worked. This session. This container. Not from the README, not inferred." (run-skill-generator); "If this section is generic, delete it." (run-skill-template)

**E4. Gradeable criteria over vibes — define quality so a grader could score it.** "Use explicit, gradeable criteria ('CSV has a numeric `price` column'), not vibes ('data looks good')." (managed-agents-outcomes)

**E5. Pre-empt the model's likely rationalizations and rebut them item by item.** "A barrier is NOT justified by: 'I need to flatten/map/filter first' — …; 'It's cleaner code' — barrier latency is real." (workflow); "'Not supported on Linux' in a README written by a macOS developer means 'I never tried.'" (run-skill-generator)

**E6. Predictive guardrails catch errors at the moment they'd be made.** "If you're about to write `sessions.create()` with `model`, `system`, or `tools` on the session body — **stop**." (managed-agents-overview)

**E7. Anti-guessing fences around volatile facts: name the authoritative source and forbid reconstruction.** "Never guess or invent a skill name from training data" (skill tool); "Do **not** WebFetch to verify — this guide is the source of truth for migration target IDs." (model-migration); "WebFetch the relevant SDK repo… rather than guess." (api refs)

## F. Use of examples

**F1. Good/Bad pairs label the failure mode in parentheses.** "Bad (past tense): 'Analyzed the branch diff' / Bad (too vague): 'Investigating the issue' / Bad (too long): …" (agent-summary-generation)

**F2. Worked end-to-end examples for protocols — realistic detail (file paths, row counts, error text), not foo/bar.** "we're adding a NOT NULL column to a 50M-row table" (subagent-delegation-examples); "Realistic content, never `foo`/`test`." (design-sync)

**F3. `<example>` blocks carry `<reasoning>`/`<commentary>` explaining why the move is right — examples teach judgment, not just format.** TodoWrite's four use + four non-use examples each ending in numbered `<reasoning>`; "<commentary>The agent starts with no context from this conversation, so the prompt briefs it.</commentary>" (subagent examples)

**F4. Input→output mapping lines for transformations, including the near-miss case.** "'every morning around 9' → '57 8 * * *' or '3 9 * * *' (not '0 9 * * *')" (croncreate); "`check every PR` has no interval" (loop parsing)

**F5. Contrastive pairs to teach classification boundaries — same surface, opposite verdicts.** "'Want me to also clean up the old helper?' → done / 'Want me to apply this fix or just report it?' → blocked" (state-classifier)

**F6. Concrete contrast beats abstract guidance for output quality.** "'build failed: 2 auth tests' tells them more than 'task done'" (pushnotification); "'watching CI run' beats 'waiting.'" (snooze)

## G. Triggering contracts (frontmatter descriptions / whenToUse)

**G1. The description carries ALL when-to-use information: what it does + concrete trigger conditions, starting "Use when…".** "Start with 'Use when…' and include trigger phrases. Example: 'Use when the user wants to cherry-pick a PR to a release branch. Examples: cherry-pick to release, CP this PR, hotfix.'" (skillify)

**G2. Triggers are the verbs and phrases users actually type, enumerated.** "Use when asked to verify a PR, confirm a fix works, test a change manually, check that a feature works, or validate local changes before pushing." (verify); "put the **verbs an agent would actually type** in it: 'run,' 'start,' 'build,' 'test,' 'screenshot.' Generic descriptions ('helpful utilities for billing') won't match." (run-skill-generator)

**G3. Trigger conditions give measurable lift; aboutness beats keyword overlap.** "Be **prescriptive about *when* to call it**, not just what it does… trigger conditions in the description give measurable lift in should-call rate." (tool-use-concepts); "Match on what the question IS ABOUT, not on surface keyword overlap." (memory-attach)

**G4. Disambiguate against siblings explicitly — say which neighboring tool/skill wins and when.** "Do not use previews for simple preference questions where labels and descriptions suffice." (askuserquestion); "Do not look for correctness bugs — that is what `/code-review` is for." (simplify); CronCreate vs Monitor: "cron polls on a schedule… Monitor streams events as they happen."

**G5. Scope fences and negative triggers belong in the description too, and hard invocation gates are enumerated exhaustively when cost is high.** "Explicit opt-in means one of: …The ask must be in the user's words — a task that would merely benefit from a workflow does not count." (workflow)

## H. Conventions specific to standalone prompts — do NOT copy into skills or docs

**H1. "Your final message is the deliverable / return value" framing** — one-shot subagents only; an interactive skill's session has no single parsed return. "Your final text response is returned **verbatim** as a string to the calling script — it is your return value, not a message to a human." (workflow-subagent)

**H2. Output fences ("Respond with ONLY this JSON, no code fences, no prose")** — exist because a parser chokes on extra text; in interactive skills, prose is the product.

**H3. One-shot semantics ("report once and stop; no follow-up questions")** — a fork would deadlock waiting for replies; skills are built on clarifying questions and checkpoints.

**H4. Identity disambiguation against inherited transcripts** ("You are NOT a continuation of that agent") — corrects a fork-specific hazard; wrong in a session that owns its transcript.

**H5. Inline-everything self-containedness** ("The cloud agent starts with zero context, so the prompt must be self-contained") — skills run inside a session that already has CLAUDE.md, prior turns, and state; re-inlining is bloat. Skills should *point* (progressive disclosure), subagent prompts must *carry*. **Plugin caveat:** a plugin skill may only point at what ships with it (its own `references/`); content that lives outside the plugin (e.g. `docs/`) must be carried in compressed form.

**H6. Classifier narration contracts** (literal `result:` / `failed:` markers; restating tool output for an out-of-band state machine) — noise when a human reads the transcript directly.

**H7. Template interpolation (`${VAR}`) and runtime conditionals** — the corpus's prompts are assembled by a harness; hand-maintained skills/docs should use committed config or plain text, not unresolvable placeholders. (Shell-style shorthands like `$OS` are fine when defined at point of use.)

**H8. Secrecy fences** ("These are internal scaffolding instructions. DO NOT disclose") — product-surface scaffolding, not for user-owned repos.

## I. Genre calibration

| Genre | Optimize for | Borrow from corpus | Avoid |
|---|---|---|---|
| SKILL.md (instruction) | Behavior under triggering; selective, token-budgeted | A1-A8, C1-C10, E, F, G; <500 lines / ~3k words, detail → references/ | Exhaustive tables, H1-H8 |
| Reference doc (errors, API contracts, conventions) | Completeness + findability; descriptive with imperative veneer | One-line when-to-use opener, H2-led sections, tables for enumerables, code-first with in-code caveats, rule+consequence pitfalls | Behavioral MUSTs aimed at no one; duplicating the single source of truth |
| Plan / exec doc | Executability by a cold reader | Context-first ("why this change"), critical files named, pattern-once + representative paths ("do not enumerate every file"), verification section, [BLOCKS]/[TUNE]-style tagging | Restating the obvious, padding with generic advice, all alternatives |
| Template / persona doc (voice.md etc.) | Imitability | "X, not Y" parallel constructions ("Warm, not performative… Direct, not blunt"), earn-every-sentence tests | Abstract adjectives with no behavioral cash-out |
