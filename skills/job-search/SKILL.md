---
name: job-search
description: Set up and run your job search — the front door. Use for "set up job search", "start my job search", "find me jobs", "check my job search", "job search status", or /job-search. On first run it onboards you end-to-end (prereqs, workspace, preferences interview, queries + frequency, a first live search, and scheduling); afterward it shows your job-search home (latest digest, new matches, pipeline) with quick actions.
disable-model-invocation: false
user-invocable: true
---

# job-search

> To configure, extend, customize, or troubleshoot the agent itself (or understand its
> capabilities), use the **job-search-agent** skill — the operator manual.

The **OS shell** for Job Search OS — the front door you run when you want to set the system up or check on
it. Mental model: this skill is the **login shell + home screen**; `osctl.py` is the **OS state** that
remembers your workspace and schedule; `job-search-run` is the **scheduled job** that pulls and judges
postings; `job-preference-interview` is the tool that **builds the brief** the runner reads. You drive
everything from here and delegate the heavy lifting to those skills.

This skill has two modes and almost no logic of its own — it **routes**, then follows a playbook:

- **First run** → walk the user through onboarding end-to-end, ending with real matches found seconds ago.
- **Returning** → show the job-search home (latest digest, new matches, pipeline) with conversational quick
  actions.

Resolve `$OS` (`scripts/osctl.py`) and `$STATE` (`scripts/state.py`) from **this skill's own directory**
(`${CLAUDE_SKILL_DIR}/scripts/…` as a plugin), never cwd; find the workspace with `python3 "$OS" resolve` and
never hard-code its path.

## Step 0 — route

Run:

```
python3 "$OS" resolve   →  {"workspace":"<abs>","first_run":<bool>,"source":"registry|default|legacy|none"}
```

- `first_run: true` → follow **`references/onboarding.md`** (the first-run playbook). Onboarding owns the
  workspace and tells the delegated skills where to write.
- `first_run: false` → follow **`references/home.md`** (the returning-user home).

That's the whole router. Everything else is in the two playbooks; read the one you routed to and follow it.

## Principles (apply in both modes)

- **Conversational-first configuration.** The user changes anything — a query, how often it runs, their
  preferences, the schedule — by **chatting with you**. You apply it by reading `<workspace>/config.yaml`,
  editing it minimally (preserving comments and structure), and writing it back, following the recipes in
  `references/internals.md`. Hand-editing files is an escape hatch you mention only if asked — never a step
  you require.
- **No numeric relevance.** Relevance is qualitative — **relevant or not**, and if relevant **weak /
  moderate / strong**, with plain-language reasoning. Never show or invent a fit score, a 0-to-100 scale,
  per-category points, or category weights. Importance lives in which **bucket** a preference is in, never in
  math.
- **No credit/budget math.** Never surface credits, per-call cost, or a budget knob, and never ask the user
  to reason about them. The only place cost ever appears is **reactively**, as the named error `E-QUOTA`
  (the API limit was hit) with its plain-language fix. You tune the system in human terms (how often to
  pull), never in credits.
- **Every blocked path is a named error.** If something can't proceed (no CLI, no auth, no config, no brief,
  quota, service down…), name the exact `E-*` from `references/errors.md` with its cause + fix wording and
  stop there. No silent failures, ever.
- **Never clobber real user data.** When adopting an existing workspace, only additively create what's
  missing — never overwrite a `config.yaml`, `preferences.md`, or `jobs.jsonl`. See the never-clobber rule
  in `references/internals.md`.

Read and follow exactly: `references/internals.md` (OS state, discovery, never-clobber adoption, config
recipes, and the verbatim scheduling block), `references/conventions.md` (workspace layout, `config.yaml`
schema, `jobs.jsonl` statuses, digest format + counts line), `references/errors.md` (every named error), and
`references/agent-data-contract.md` (the source contract `job-search-run` honors). These are the source of
truth; this skill never restates their details from memory.
