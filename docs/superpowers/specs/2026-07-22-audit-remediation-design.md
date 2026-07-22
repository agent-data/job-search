---
type: design-doc
title: "Audit remediation: enforceable ownership, preserved intent, a thin runner, and gates that can see"
status: current
verified: partial
last_reviewed: 2026-07-22
code_refs: [skills/job-search/SKILL.md, skills/job-search/references/onboarding.md, skills/job-search/references/home.md, skills/job-search-run/SKILL.md, skills/evaluate-job-fit/SKILL.md, skills/job-preference-interview/SKILL.md, skills/job-search-agent/SKILL.md, shared/references/conventions.md, shared/references/parallelism.md, shared/references/query-strategy.md, shared/references/run-lifecycle.md, shared/references/update.md, shared/references/voice.md, scripts/doc_lint.py, scripts/check_release_integrity.py, tests/test_reference_resolution.py, tests/test_scheduling_eligibility.py]
claimed_paths: [skills, shared, scripts, tests, templates, .opencode, docs/superpowers/reviews]
owner_area: Skills & references
repos: [job-search-os]
---

# Audit remediation: enforceable ownership, preserved intent, a thin runner, and gates that can see

This design responds to
[`docs/superpowers/reviews/2026-07-22-plugin-style-audit.md`](../reviews/2026-07-22-plugin-style-audit.md),
a full-surface review of the five skills, their references, the shared references, the mechanics
scripts, the host manifests, the eval suite, and CI against every rule in
`docs-private/prompt-style-guide/` and `docs-private/agent-agnostic-skills/` — 278 items, producing
12 MUST-rule violations, ~67 SHOULD/CONSIDER violations, 11 anti-pattern hits, and 13 defects
verified line-by-line.

**Supersession.** This document fully supersedes
`docs/superpowers/specs/2026-07-21-job-search-robustness-design.md` and
`docs/superpowers/plans/2026-07-21-job-search-robustness.md`. Both are re-marked `status: superseded`
with a redirect line pointing here. No content, conclusion, or contract is inherited from them; the
config-v3 migration, search-plan receipts, preference fingerprints, must-have evidence matrices, and
workspace bundle authority they proposed are explicitly **not** part of this design.

## The problem

The audit found one disease and a set of consequences.

> The pack has an ownership **metaphor**, not an ownership **boundary**. Who may call the job source,
> who may judge a posting, and who may write run artifacts is asserted in `ARCHITECTURE.md`, in the
> operator manual's "when to use it" table, and in soft framing in the front door — none of which is a
> constraint at the moment the decision is made. A repo-wide grep for any exclusivity statement in
> `shared/references/` returns nothing.

Both dogfooded failures follow from that, plus two composition bugs:

1. **The front door reproduced work owned by siblings.** No prohibition exists anywhere in the three
   front-door files; the one stated exclusion is keyed to *interactivity* ("Not the place for a
   non-interactive run"), which an interactive onboarding pull does not trip; the front door is
   *required* to read the file carrying the literal `search-jobs`/`get-posting` invocations; and
   `evaluate-job-fit` is named nowhere in the front door while the front door is handed the judge's
   full verdict vocabulary in the second person.
2. **A stated domain was broadened, then scored strong.** The brief classifier is a closed three-item
   list — "a stated role / location / pay floor becomes a Must-have, softer wants go to Strong
   preferences" — so a stated domain is demoted by rule. Nothing requires the user's own wording to
   survive; the only guardrail bans *addition* ("don't invent preferences they didn't express"), not
   *generalization*. The band rule then permits the outcome, because `strong` = "must-haves and most
   strong preferences" and the demoted domain is outvoted.

The verbosity in `job-search-run/SKILL.md` (686 lines / 7,772 words) is a symptom: roughly 2,200 of
those words restate contracts that already have canonical homes, and the copies have measurably
drifted.

## Goals

- Make each skill's exclusive ownership a constraint stated at the point of decision, with every
  prohibition paired with its alternative.
- Preserve a stated requirement in the user's own words from the brief through to the band decision,
  without adding a scoring rubric or a deterministic matching rule.
- Reduce `job-search-run/SKILL.md` to an orchestration spine within the disclosure budget, by deleting
  duplication rather than relocating it.
- Fix every verified defect **and** extend the gate that should have caught it, so each class cannot
  silently return.
- Keep the pack's privacy posture honest: no undisclosed network egress, no false locality claim.
- Report evidence at its real tier: deterministic gates as pass/fail, behavioral evals as rates.

## Non-goals

- No config schema change, no `version: 3`, no workspace migration.
- No search-plan receipts, preferences fingerprints, must-have evidence matrices, or bundle-authority
  validator.
- No new sibling skills. AAS-BOUND-07 is explicit that the sanctioned response to size is a references
  split; the runner's phases share one run's mutable state, which is not a seam.
- No relocation of the machine registry out of `~/.config/job-search/`.
- No re-adjudication of the three open tension-register entries the audit landed on (AAS-T-03 detail-model
  tier floor, AAS-T-05 description what-half, AAS-T-06 recipe-vs-prohibition). They are recorded as
  open, with the audit's evidence attached, and left to the doctrine owners.
- No requirement that a posting repeat the user's words, and no automatic rejection of a posting that
  omits a must-have. Relevance stays qualitative.

## Design decision and alternatives

### Chosen: correct the instruction at the point of decision, pin it with the repo's own contract idiom

Each fix is one of three things: a sentence where the decision is made, a deleted duplicate, or a gate
that can see the defect. Every new invariant gets a marked `<!-- …-contract:name -->` block in one
canonical home plus a pytest module in the established style of `tests/test_query_strategy_contract.py`
— which already asserts single-homing, one-hop pointers, and semantic properties, and is the pattern
this repo reaches for.

This is chosen because it matches the audit's actual causes. Every failed behavior traces to a missing
sentence, a misclassifying enumeration, or a drifted hand-copy — not to absent machinery. It is also
the cheapest path that leaves the pack simpler than it found it.

### Rejected: full re-architecture (config v3, receipts, evidence matrices)

The superseded design concluded that prose is stochastic and must be backed by runtime gates, and
proposed immutable search-plan receipts binding every query to verbatim must-haves through a
preferences hash, plus a must-have assessment matrix in every verdict and a workspace bundle
validator. Rejected on three grounds: it forces a real migration that leaves unbound workspaces
unrunnable; it adds a second machine-readable source of truth beside `preferences.md`, which the pack's
qualitative-by-default belief exists to avoid; and it addresses causes this audit did not find while
leaving the ones it did find — the missing prohibition, the closed classifier list, the drifted copies
— untouched.

### Rejected: prose fixes with no new gates

Correcting the instructions without extending CI would fix today's instances and none of tomorrow's.
The evidence against it is in the audit: the runner reached 686 lines *after* a prior style audit
looked at it and waived the size; two dangling reference pointers survived because the pointer gate
excludes the directory they live in; a five-of-six gate tuple has been asserting the wrong thing under
617 green tests. Judgment-based review has already failed on each of these.

## Track A — Ownership becomes a constraint

### A1. The canonical contract

New `shared/references/ownership.md` — small, single-purpose, one hop from every `SKILL.md`. It carries
one marked block:

```text
<!-- ownership-contract:skill-roles -->
| Skill | Exclusively owns | Never | Instead |
<!-- /ownership-contract:skill-roles -->
```

Every skill in the pack gets a row, not only the three the audit found colliding: a table that claims
exclusivity while omitting skills asserts ownership over territory the absentees hold, and its load
trigger is reachable from them.

| Skill | Exclusively owns | Never | Instead |
|---|---|---|---|
| `job-search` | setup, status, the home view, routing, applying the config changes a user asks for in conversation, feedback routing | calls the job source · judges a posting · writes `jobs.jsonl`, `runs/*.json`, or a digest | invoke `job-search-run` for the pull — it writes those artifacts; invoke `evaluate-job-fit` for a verdict |
| `job-search-run` | preflight, metered calls, orchestration, validated persistence, finalization | produce a fit verdict from its own rubric (one bounded exception: **Triage is not a verdict**, A2 below) | route every semantic judgment to `evaluate-job-fit` |
| `evaluate-job-fit` | relevance, must-have assessment, band, reasoning, dealbreakers, unknowns | write workspace state or change retrieval configuration | return the envelope; the coordinator persists it |
| `job-preference-interview` | the Job Preferences Brief's content — building, refining, deepening, and importing it | judge a posting against the brief it just wrote · call the job source · change retrieval configuration | invoke `evaluate-job-fit` for a verdict; the front door applies config changes |
| `job-search-agent` | explaining how the system works, troubleshooting a run, and the customization and extension playbooks | run a search · judge a posting · write run artifacts | invoke `job-search-run` for a pull; invoke `evaluate-job-fit` for a verdict |
| mechanics scripts | schema, append, fold, and binding validation | make a semantic fit or query-quality judgment | fail closed and return to the caller |

Beneath the table, the file names the pattern the `Never` column encodes rather than leaving a reader to
induce it: **searching the job source belongs to `job-search-run`, and a fit verdict belongs to
`evaluate-job-fit`** — so every skill that owns neither carries both prohibitions. (`evaluate-job-fit`
reads one posting's detail to judge it; reading one posting is not a search.) That sentence is the
invariant CI enforces row by row, so it cannot be a claim the table quietly stops satisfying.

The file also carries the two owner-unavailable rules: if the runner is unavailable the front door
**stops and names the repair** and does not imitate it; if the judge is unavailable the runner **stops
semantic evaluation** and does not fall back to an inline mini-rubric.

### A2. The triage/verdict line

The runner's cheap summary scan stays — it is a real cost saving — but is bounded so it cannot become a
verdict. It may reject a posting only when a **structured summary field explicitly contradicts a
must-have** (`location_display` reads onsite-Chicago against a remote-US must-have). Anything requiring
interpretation — domain fit, seniority read, culture, stage — queues for the judge. Mechanical dedup and
malformed-record rejection remain in the runner and the validators, because neither is a fit judgment.

This line is testable and is what distinguishes triage from judging.

### A3. Surface changes

- `skills/job-search/SKILL.md` — add the ownership prohibition to **Principles**, stated by action, not
  by interactivity, each prohibition paired with its alternative in the same sentence. Add
  `evaluate-job-fit` to the mental-model paragraph. Replace "almost no logic of its own" with the
  observable trigger it was standing in for.
- `skills/job-search/SKILL.md` frontmatter — add the missing sibling discriminator ("judging one
  posting → `evaluate-job-fit`"); cut the ordered workflow clause ("a one-question sketch, then live
  postings") in favor of a capability phrase plus the delegation; drop the `/job-search` slash token,
  which belongs in the host manifests.
- `skills/job-search-run/SKILL.md` frontmatter — replace the stage enumeration with a capability
  phrase.
- `skills/job-search-agent/SKILL.md` frontmatter — open verb-first like its four siblings.
- `references/home.md` — add "is this one a fit?" to the quick actions, routed to `evaluate-job-fit`;
  route **Applying your feedback** → "recheck already-shown matches" through the judge rather than an
  in-place re-judgment.
- `skills/job-search/SKILL.md` — narrow the mandatory read of `agent-data-contract.md` to the auth and
  available-tier sections onboarding actually consumes, rather than the whole route contract.

### A4. The handoff contract

`skills/evaluate-job-fit/SKILL.md` currently opens its Output section with an unconditional "Return
BOTH a short human summary AND this object", which contradicts the delegated return contract in
`parallelism.md` ("The object is the whole message, nothing else") whose validator treats extra prose
as a malformed envelope. Split the two invocation modes before showing any schema: an interactive
invocation returns the human summary; a delegated invocation returns exactly one raw envelope, and the
banned-token rule is the last instruction a dispatched worker reads.

### A5. Verification

- `tests/test_ownership_contract.py` — the block is single-homed; the prohibition is present in the
  front door; `agent-data-contract.md` is absent from the front door's mandatory-read list; every skill
  named in the contract exists; each description carries its sibling discriminators.
- New behavioral eval (`skills/job-search/evals/evals.json`) — drive **only** `job-search` under a
  shortcut-pressure first-run prompt; assert a `runs/<run_id>.json` plus its lifecycle ledger exist,
  with a `must_not` on front-door-issued `search-jobs` rows in the call log.
- Fix the harness self-invocation at `evals.json:3`, which instructs the eval **driver** to run
  `job-search-run` itself, so eval 1's "Runs a real sample job-search-run" stops being satisfied by the
  harness rather than the skill.

## Track B — Intent preservation

### B1. The canonical contract

New marked block `<!-- intent-contract:preservation -->` in `shared/references/conventions.md`
§ `preferences.md — prose brief`, which already owns the brief's contract and is one hop from every
skill. Two halves:

**Writing the brief.** A requirement the user states about the job itself enters **Must-haves in their
own words**. A hedged or comparative want goes to Strong preferences or Nice-to-haves. An aversion
becomes a Red flag. A stated requirement is never restated at a broader level of generality, and never
replaced by the category it belongs to.

The closed three-item list ("role / location / pay floor") is **deleted, not extended** — extending an
enumeration only moves the hole. `onboarding.md`'s duplicate copy of the method is deleted and replaced
by the pointer its own sentence already implies; `job-preference-interview/SKILL.md` remains the owner
of the quick-sketch method itself.

**Judging against the brief.** A brief term matched only at a broader level of generality is **not a
hit**. When a verdict claims a must-have is met, `reasoning` names the user's own term. This is a
disqualifier on the band claim, not a lexical matching requirement: a posting may satisfy a web-data
requirement through crawler operation or public-web acquisition without using the phrase — what it may
not do is satisfy it by belonging to a broader category the user did not ask for.

### B2. Teaching the boundary

- `skills/evaluate-job-fit/SKILL.md` — add the contrastive near-miss pair for strong-vs-moderate: two
  postings sharing role, location, and pay, differing only in whether the domain is the one the brief
  names, each with its one-line "because". The reject boundary four lines above already gets a proper
  pair; the band boundary the skill itself calls "the one that slips" does not.
- Fence the worked verdict example and swap its band, so the judging skill's only worked verdict is not
  a `Strong match` sitting beside an emit instruction.
- Rewrite both steer examples (`job-search-run/SKILL.md:626` and `:416`) so they cannot anchor a band:
  the steer is a provisional read plus an open question, and the current exemplars open with the band
  word the worker must choose independently.
- `shared/references/parallelism.md` — carry the band rule as **required slots** in the worker-brief
  skeleton, not only as a by-reference pointer. This is the channel that actually reaches the cheaper
  delegated model, and a pointer costs it a re-read it may not take.
- `shared/references/query-strategy.md` — grade "Broad queries cost no precision" to its base rate. As
  an absolute it is the belief that licenses treating an adjacent category as interchangeable with the
  user's term.
- `templates/preferences.example.md` — keep the five-section shell and front-matter complete; stub the
  substance. The same AI-engineer persona currently recurs as illustration in three places.

### B3. The checkpoint

`onboarding.md` §5's confidence checkpoint already renders the brief before the first live run. Give the
**must-haves** focus within it and invite correction — these are the hard filters, anything wrong? No
new question and no new gate: the display exists, this makes the misclassification visible at the one
moment it is cheap to fix.

### B4. Verification

- `tests/test_intent_contract.py` — the block is single-homed; no surface enumerates a closed must-have
  list; `onboarding.md` carries no second copy of the classifier; the judge carries the
  generality disqualifier; the worker-brief skeleton carries the band slots.
- New behavioral evals: an adjacent-domain posting that clears every must-have must land `moderate`
  with reasoning naming the domain gap (the audit found **no expectation anywhere in the 185 scenarios
  ever requires `moderate` or `weak`**); and a quick-sketch drafting scenario where a stated domain must
  land in Must-haves in the user's own words.

## Track C — A thin runner and navigable references

### C1. Targets

`skills/job-search-run/SKILL.md`: 686 lines / 7,772 words → **≤300 lines / ≤2,000 words**.

| Move | From | To |
|---|---|---|
| Lifecycle coordinator block (103 lines) | body | deleted; ~10 lines of runner-specific ordering plus the one-hop pointer to `run-lifecycle.md` |
| Streams, pagination branch table, finite allocator, scratch lifecycle | body | new `references/retrieval-and-selection.md`, load-triggered "when paginating past the first page" |
| Attempt-accounting tables and decimal arithmetic | body | new `references/accounting.md`, load-triggered "before the first metered attempt" |
| Step 5's run-record field enumeration | body | pointer to `conventions.md` § `runs/<run_id>.json` |
| Run-health surfacing prose | body | pointer to `errors.md`, keeping only the runner-specific exit shape |

Kept in the body: scope and exclusive ownership, the phase-routing table, the gates before metered
calls / persistence / reporting, the scan-and-steer, the delegation contract, narration, and the
completion self-check.

The refactor **removes** duplication rather than relocating it. Query semantics, fit semantics,
lifecycle, accounting, delegated output, and error rendering each keep exactly one owner. A critical
process rule may still appear beside its governed action, in the completion checklist, and as a red flag
paired with the correct alternative — that is repetition within a skill, which the guides permit, not a
second home.

**The duplication is currently pinned by CI, and that pin must be re-pointed, not deleted.**
`tests/test_run_lifecycle_pressure.py::test_runner_contract_drives_every_mutation_and_completion_through_ledger`
asserts nineteen literal substrings are present **in the runner's body** — both
`<!-- run-lifecycle-runner:coordinator -->` fence markers plus sixteen prose fragments
("validate trigger/scheduler attribution before creating the ledger", "immutable folded source order",
"orphan resolution fails this pre-close validation", …), every one of which this design deletes as a
copy of `run-lifecycle.md`. The test therefore does not merely tolerate the hand-copy; it *requires*
it, which is why the block survived a prior audit.

The rewrite is a re-pointing with no loss of coverage, and the distinction matters because the lazy fix
— dropping the failing assertions — would silently retire sixteen real invariants:

1. Each fragment is asserted against `shared/references/run-lifecycle.md`, its canonical home, so the
   invariant is still pinned somewhere.
2. The runner is asserted to carry the one-hop pointer plus only its genuinely runner-specific
   ordering, and is asserted **not** to restate the fragments — inverting the assertion, so the test
   now enforces single-homing instead of duplication.

If a fragment turns out to have no canonical home in `run-lifecycle.md`, that fragment is genuinely
runner-owned and stays in the body. Discovering which ones those are is part of the work, not a reason
to relax the test.

### C2. Reference maps first

Add a `**Contents:**` anchor line to every reference over roughly 100 lines — eight `shared/references`
files currently have none, including `internals.md` at 926 lines / 9,091 words — plus grep hints in the
consuming `SKILL.md` for `internals.md` and `conventions.md`.

This is sequenced **before** the runner split. Pushing depth into unmapped references makes partial-read
failures worse, which is the exact mechanism AAS-BOUND-01 exists to prevent.

### C3. The remaining hand-copies

| Fact | Homes today | Single home |
|---|---|---|
| `search.parallel_detail_reads` tri-state | 4 | `parallelism.md` |
| The six scheduler eligibility gates | 3 | `internals.md` gates table |
| Query-portfolio doctrine and the repeated-thin contract | 3 | `query-strategy.md` |
| Quick-sketch drafting method | 2 | `job-preference-interview/SKILL.md` (Track B) |
| The job-source listing id | 2 shipped + tests | `agent-data-contract.md`; tests parse it |

### C4. One-hop closure and register

Each `SKILL.md` directly links what it actually needs: `query-strategy.md` and the mechanics scripts from
the runner; `errors.md` and `run-lifecycle.md` from `evaluate-job-fit`; the templates and the mechanics
scripts from the front door. Emphasis is rationed where bold density is ≥0.4 spans per line
(`scheduling-and-consent.md` at 0.50, `job-preference-interview/SKILL.md` at 0.44) — reserved for the
irreversible gates, plain elsewhere.

### C5. Considered and declined

Bundling the finite allocator and the decimal arithmetic as mechanics scripts (AAS-FORM-08) is declined.
The disclosure cost that motivated it is removed by moving both into `references/retrieval-and-selection.md`
and `references/accounting.md`; adding a script plus its pinned prose fallback for a rarely-exercised path
buys determinism the pack does not currently lack, at the cost of two more surfaces to keep in sync.
Recorded here so the decline is visible rather than an omission.

## Track D — Gates that can see the defect

Every verified defect is fixed **and** paired with the gate that should have caught it. The gate work is
what makes this track more than a cleanup pass.

| Defect | Fix | Gate |
|---|---|---|
| `lifecycle-fold.sh` / `lifecycle-append.sh` named in 17 places, never with a resolvable path | path every invocation | script-pointer scan requires a resolvable path for every named `.sh` |
| `references/build-stamp.md` dangles in `update.md` and `conventions.md` | correct to the sibling form | extend `_pointer_files()` to `shared/references/*.md` — one line; its sibling already globs that tree |
| Repo-root `templates/…` paths inside skill files (×4) | anchor relatively | extend the pointer scan to `templates/` |
| `.opencode/plugins/job-search.js` points at the deleted `shared/references/platform/` | delete the pointers; describe the real contract | extend the pointer scan to `.opencode/` |
| eval 2 demands the recipe dump that eval 47 and `onboarding.md` forbid | fix eval 2 and `TESTING.md:174` | contract test pins the decline behavior so prose and eval cannot diverge |
| `test_scheduling_eligibility.py` asserts five of six gates (`inspectable` missing) | fix | derive `GATES` from the parsed contract table instead of a hardcoded tuple |
| Nothing validates `skills/*/SKILL.md` frontmatter | — | new `doc_lint` rule: closed key set, `name` ↔ directory equality, description cap |
| `job-search-run/SKILL.md` at 686 lines | Track C | new `doc_lint` rule: per-`SKILL.md` line and word ceiling, failing the build past it |
| `CHANGELOG.md` at 0.6.0 against six manifests at 0.6.1 | bump | `check_release_integrity.py --check-undeclared-version` flags version-bearing files outside the manifest list that disagree |
| "coerce anything else" licenses manufacturing a band | **reject**: an out-of-vocab band is a malformed envelope, fails closed, settles via summary fallback or `terminally_skipped` | contract test asserts the runner and `parallelism.md` state the same rule |
| "All data lives under `~/.job-search/`" is false | name the registry and the agent-data key locations, and mark the never-committed line a design rule rather than an enforced control | covered by the existing doc-lint claim checks |
| `TESTING.md`'s loose grep alternation cannot distinguish a violation from allowed text | anchor the patterns to the artifact fields that may not carry them | — |
| Stale `"version":"0.4.0"` literal in a `conventions.md` emit example | render as a placeholder like its two siblings | undeclared-version audit above |

Also in this track, each a one-to-three-line correction with its rule cited in the diff: the visibility
premise in `voice.md` graded and host-scoped rather than asserted as universal; a relaxation condition on
the narration budget; the escape hatch suffixed to the judge's no-numbers prohibition; a reader persona
for the user channel; the untrusted-content demotion carried into the runner's in-primary summary scan
and front-loaded in the judge; both branches glossed on the boolean and enum fields the schema owner
leaves to inference; the `agentskills.io` framing line in `AGENTS.md`; a contribution disclosure section in
`CONTRIBUTING.md`; a pack-precedence line declaring user configuration above these skills; native-first
ordering in the schedule-health read-back; and the parallel-subagent profile write shown before the yes
that authorizes it rather than after.

## Track E — Update-check consent

`shared/references/update.md` fetches the author-hosted build stamp from `raw.githubusercontent.com`
whenever its 24-hour cache is stale, with no opt-in and no disclosure, in a pack whose stated posture is
private and local-first.

- New registry key `update_check.consent` — `granted` | `declined`; absent means not yet asked.
- `onboarding.md` §7 asks once, as **its own closed choice** after the schedule decision resolves.
  Deliberately not folded into the scheduling confirmation: scoped consent is something this pack gets
  right elsewhere, and bundling an egress decision into a machine-change yes would break it.
- Absent or declined consent → no fetch, no banner. The home renders normally through the existing
  no-signal path, which already handles a failed or missing check.
- `job-search-agent/SKILL.md` and `README.md` describe the check, what it sends, and how to change the
  answer.

## Verification plan

**Merge-gating, deterministic.** `tests/test_ownership_contract.py`, `tests/test_intent_contract.py`, the
extended pointer and script-pointer scans, the derived scheduling-gate tokens, the two new `doc_lint`
rules (frontmatter validation and the SKILL.md size budget), and `--check-undeclared-version`. These run
in the existing CI job; no new lane.

**Opt-in, non-gating, behavioral.** Three new eval scenarios — ownership hand-off, adjacent-domain
`moderate`, and domain-lands-in-must-haves — run through `eval_harness.py` against the fake agent-data
shim. Behavioral evals stay out of the merge gate, which is the split AAS-TEST-02 asks for and the repo
already honors.

**Honesty of evidence.** A skipped or unavailable model is reported as skipped, never as green. Static
eval-harness success proves scenario coherence only and is never described as behavioral proof. Where a
claim about model behavior has not been executed, the design says so.

## Rollout

No migration. No config schema change, no workspace touch, no user-visible state change except the new
`update_check.consent` key, whose absence is a valid state that suppresses the network call. Existing
workspaces keep running unchanged through every phase.

The work is sequenced so each phase is independently shippable and CI-green: reference maps (C2) →
ownership (A) → intent (B) → runner split (C1, C3, C4) → gates and defects (D) → consent (E). C2 precedes
C1 because splitting into unmapped references is the failure mode the split exists to avoid. A and B
precede C1 so the runner is thinned once, against its final content, rather than edited twice.

## Traceability

Every audit finding maps to exactly one track. Rule IDs resolve against the two rule indexes in
`docs-private/`.

| Track | Findings addressed |
|---|---|
| A — Ownership | PSG-SUB-01, SUB-09, SUB-12, SUB-13 · PSG-TOOL-01, TOOL-03 · PSG-F-09 · PSG-ANTI-10 · AAS-TRIG-01, TRIG-03, TRIG-05 · AAS-PROC-02 · AAS-AUTO-10 · AAS-LANG-02 · AAS-ANTI-10 · AAS-TEST-16 |
| B — Intent | PSG-SUB-05 · PSG-F-08 (steer example), F-14 · AAS-EX-01, EX-02, EX-03, EX-04 · AAS-FORM-04 (classifier), FORM-14 · AAS-PACK-02 · AAS-SKILL-08 · AAS-TEST-03 |
| C — Thinning | AAS-SKILL-04 · AAS-BOUND-01, BOUND-02, BOUND-03, BOUND-05 · AAS-FORM-04 (remaining copies), FORM-07 · AAS-ANTI-04, ANTI-13, ANTI-29 · PSG-F-05 · PSG-ANTI-02, ANTI-09 |
| D — Gates and defects | AAS-SKILL-03, SKILL-09 · AAS-ANTI-21, ANTI-32, ANTI-35, ANTI-41, ANTI-42 · AAS-DIST-01, DIST-06 · AAS-TEST-01, TEST-04, TEST-11 · AAS-PORT-04, PORT-05, PORT-07 · AAS-AUTO-06 · AAS-PACK-04, PACK-06 · AAS-FORM-01, FORM-03, FORM-09, FORM-10 · PSG-COMM-09, COMM-20 · PSG-INJ-01 · PSG-SAFE-10 · PSG-TOOL-05, TOOL-10, TOOL-13, TOOL-15 · PSG-F-01, F-02, F-04, F-07, F-08 (version literal) · PSG-ANTI-07 |
| E — Consent | AAS-ANTI-36 |
| Declined, recorded | AAS-FORM-08 (see C5) |
| Open tensions, not resolved | AAS-AUTO-11 → AAS-T-03 · AAS-TRIG-01 what-half → AAS-T-05 · AAS-FORM-01 register → AAS-T-06 |

## Risks

**Thinning can drop a load-bearing rule — and one existing test actively pushes the wrong way.** The
moves are mechanical (delete duplicates, relocate whole sections behind load-triggers), but as C1
records, `test_runner_contract_drives_every_mutation_and_completion_through_ledger` currently *requires*
the duplicated block, so the split will turn it red. The mitigation is the re-pointing procedure in C1:
every fragment is re-asserted against its canonical home and the runner assertion is inverted to enforce
single-homing. Deleting a failing assertion is the one move this design forbids outright — it would
retire sixteen invariants under cover of a refactor. If a fragment has no canonical home elsewhere, it
is runner-owned and stays.

**A size gate can be gamed by pushing prose sideways.** The duplication contract tests and the one-hop
closure are what make the budget mean something; the ceiling alone would just relocate bulk.

**Prompt-level fixes are stochastic.** This is the honest limit of the chosen approach. Deterministic
gates cover structure — single-homing, resolvable pointers, frontmatter, size, contract presence. They
cannot prove a model will honor a prohibition. The behavioral evals measure that and are reported as
pass rates across repetitions with a no-guidance control, not as a green check.

**The ownership prohibition could over-fire**, making the front door refuse work it legitimately owns.
The triage/verdict line (A2) is drawn precisely to prevent this, and the eval suite keeps its existing
first-run and home-view scenarios as the counter-pressure.

## Completion criteria

- The ownership contract is single-homed, fenced in the front door by action, and observed in the
  behavioral hand-off eval.
- A stated requirement survives verbatim from the sketch into Must-haves, and an adjacent-domain posting
  that clears every must-have lands `moderate` in the behavioral eval.
- `job-search-run/SKILL.md` is at or below 300 lines and 2,000 words, with phase-local one-hop
  references, and the size gate is green.
- Every reference over ~100 lines carries a `**Contents:**` map.
- All thirteen verified defects are fixed and each paired gate demonstrably fails on the pre-fix state.
- `pytest`, `philosophy_guard`, `doc_lint`, release integrity, and the build-stamp sync are green.
- Behavioral evals are executed and reported at their honest tier, with rates and any skips named.
- The two superseded documents carry `status: superseded` and a redirect to this design.
