---
type: design-doc
title: "Verify-don't-encode: adapter-free portability, unattended scheduling, and config-time run verification"
status: superseded
verified: partial
last_reviewed: 2026-07-16
code_refs: [shared/references/internals.md, shared/references/conventions.md, shared/references/parallelism.md, shared/references/errors.md, shared/references/agent-data-contract.md, shared/references/voice.md, skills/job-search-agent/references/scheduling-and-consent.md, skills/job-search/references/onboarding.md, skills/job-search-run/SKILL.md, docs/design-docs/core-beliefs.md, scripts/doc_lint.py, .github/workflows/ci.yml]
claimed_paths: [skills, shared/references, scripts]
owner_area: Skills & references
repos: [job-search-os]
---

# Verify-don't-encode: adapter-free portability, unattended scheduling, and config-time run verification

> **Superseded:** [Cost-aware decisions, explicit models, and canary-verified recurring jobs](2026-07-16-cost-aware-verified-recurring-jobs-design.md)
> retains the runtime-verification thesis while replacing the recurring-mechanism eligibility,
> primary/detail model ownership, cost-context scope, and migration design.

This design builds on the plugin **as it ships on this branch** — the running skills, references, and the
minimized-but-present per-host adapter layer — and takes it one increment further. It is self-contained:
it describes a delta from the current code, not from any planning doc. It makes three coupled changes:

1. **Advocate the unattended schedule** — a recurring run that fires with no interactive session open —
   as the default, re-weighting Belief 7 while keeping its consent core intact.
2. **Mandatory config-time verification** — never tell the user a job is scheduled until its exact
   unattended invocation has been *observed* to succeed end-to-end. This closes the "the run silently
   lacked permissions, discovered the next day" failure.
3. **Delete the per-host adapter layer entirely** — zero residual. The agent resolves its own tools,
   models, scheduler, and permissions from neutral action-language, self-aware conditionals, and — for
   anything with an observable artifact — the verification step above.

The spine that makes all three cohere is one principle: **verify, don't encode.**

## The thesis: verify, don't encode

A per-host adapter exists to *encode* facts about a harness so a shared skill body stays correct on it.
But a capable coding agent already knows its own tools, models, and OS; it can probe its own environment;
and where a host-specific action produces an **observable artifact**, the agent can *prove* the action
worked instead of trusting an encoded recipe. So most adapter content is redundant with the agent's own
knowledge plus a verification step — and an encoded recipe is worse than verification in two ways: it
drifts as harnesses change, and it is **lossy and inconsistent** (see Ground truth: the Codex adapter
encodes a scheduled-run write gotcha; the Claude adapter encodes none — and the failure this design fixes
slipped through on exactly that gap).

**Adapter-necessity test** — encode a per-host fact only if it is *all three* of:

1. **not derivable** by the agent from its own environment, **and**
2. **not probeable** at runtime, **and**
3. **not verifiable** after the fact (no observable artifact would catch a wrong guess).

If even one is false, it is neutral action-language, not an adapter. Applied to this plugin (below), the
test removes the entire per-host layer.

**Verify-don't-encode clause (the reconciliation with `AAS-LANG-07`).** `AAS-LANG-07` records measured
evidence that *pure* abstraction can degrade reliability — a step naming no concrete tool passed 2/6 until
native tools were named. This design is **not** pure abstraction: it pairs neutral action-language with
(a) **self-aware conditionals** for capabilities the agent can introspect, (b) **required slots** for
parameters whose omission resolves to a bad default, and (c) **runtime verification** for any host-specific
action with an observable artifact. The worktree experiment `AAS-LANG-07` cites failed precisely because it
had *no* runtime backstop. Where a backstop exists, verification replaces the adapter that `AAS-LANG-07`
would otherwise require.

## Ground truth (what ships on this branch today)

- **Adapter layer present but minimized.** `shared/references/platform/` holds nine files — `_common.md`
  (host-neutral boilerplate) plus one adapter per host (`claude.md` ≈ 165 lines, `codex.md`, `cursor.md`,
  `gemini.md`, `pi.md`, `opencode.md`, `droid.md`, `copilot.md`). Each keeps ~12 canonical sections
  (Identity, Tool map, Run recipe, Scheduling, Headless invocation, Closed-choice, Concurrent detail reads,
  Model tiers, Whole-file write, Block-alert, agent-data setup, Packaging/Update). Roughly **66** "see your
  platform's adapter →" pointers across `skills/` + `shared/` defer to it. `scripts/validate_platforms.py`
  structurally gates the adapter files (section presence, tier-not-literal-id).
- **Scheduling stance.** `scheduling-and-consent.md` + `internals.md` (Scheduling setup) encode a two-tier
  model: **Tier 1 native local scheduler preferred** (on Claude that is session-bound `/loop`, which
  "installs nothing"); **Tier 2 consent-gated cron/launchd** only where no native local scheduler exists or
  the user asks. Belief 7 (`core-beliefs.md`) states the preference for the install-nothing option.
- **No config-time verification exists.** Setup ends by *recording* the schedule; whether the unattended
  invocation can actually write the workspace or reach agent-data is discovered only when it next runs (or
  fails to). This is the gap.
- **The lossy-encoding evidence.** `codex.md` encodes, PIN-tagged from live testing, that the
  `workspace-write` sandbox reads but will not write `~/.job-search` unless it is cwd / `--add-dir`, and
  that egress is blocked without `sandbox_workspace_write.network_access=true`. `claude.md` encodes **no**
  equivalent scheduled-run permission gotcha — so the per-host approach is inconsistent, and the permission
  failure this design targets went uncaught.

## Feature A — advocate the unattended schedule (amends Belief 7)

**Change.** The scheduling flow advocates, as its **default recommendation**, an **unattended** schedule —
one that runs with no interactive session open — using the host's/OS's real scheduler that survives
session-close (launchd, cron, or the host's native unattended scheduler), preferring one that **re-fires
missed runs on wake** where available. A session-bound in-session loop is **demoted to a named fallback**,
offered only when no unattended scheduler is available or the user declines the machine change; when it is
used, the user is told plainly it runs *only while a session is open*, so a quiet overnight is expected.

**Consent is preserved, not removed.** The exact machine change is **shown before it is written**, applied
only on an explicit yes, and stays user-removable. The re-weighting is *reliability > installs-nothing*,
never *silent > consented*. This is a conscious amendment to Belief 7's current "prefer the install-nothing
native local scheduler" — the install-nothing value yields to unattended reliability, but the
no-silent-privileged-write core is untouched (`AAS-AUTO-02`: spend consent on the one-way door).

**Neutral phrasing (no adapter).** The directive names the *goal and the required conditions*, not a
host mechanism: "set up a recurring run that fires without a session open, using your host's or OS's
scheduler; it must run where it can write the workspace and reach agent-data." The agent binds this to its
own scheduler.

## Feature B — config-time verification: the canary (the linchpin)

**The honesty contract.** Never tell the user a job is scheduled until its **exact unattended invocation
has been observed to succeed end-to-end.** This is what turns adapter-deletion from a risk into a safe
move: a wrong self-configuration is caught *now*, not the next day (Belief 4: no silent failures).

**Two-layer proof, both required before the schedule is recorded:**

1. **Registration** — confirm the schedule is actually registered with the host/OS scheduler (it appears in
   the scheduler's own job list). Proves it exists.
2. **Execution canary** — trigger **one real fire through the actual scheduled path**, then confirm it
   produced the expected **artifacts**: a fresh `runs/<id>.json` with `run_health` ≠ `blocked`, evidence
   **agent-data was reached**, and evidence the **workspace was written**. Default depth is a **real run**
   (truest proof; the user gets a live digest; the quota cost is one run the first scheduled fire would
   spend anyway).

**Same-context imperative (the non-negotiable subtlety).** The canary must run through the *real* unattended
invocation — non-interactive, the scheduled command's permission profile and environment, no TTY — **not**
the agent's own interactive session, where it already holds write/agent-data permission and would pass while
the real run fails. This is `PSG-SUB-06`'s "*prove it works, not that it exists*" and `AAS-LANG-08`'s
route-success-through-the-written-record, applied to scheduling.

**Self-debug + consent-gated fix loop.** If the canary fails, the agent **debugs it itself**, using its own
knowledge of its host — there is no troubleshooting reference to consult (see Teardown). The neutral setup
directive states only the required conditions ("ensure the unattended run can write the workspace and call
agent-data"); the agent diagnoses the specific failure from the canary's artifacts (write denied /
agent-data unreachable / subagents refused), **proposes the exact host-appropriate fix, shows it, applies it
on consent, and re-runs the canary.** Loop until green. If it cannot be made to work, **do not claim it is
scheduled** — surface the exact gap in named-error style and stop. No "all set."

**Accepted tradeoff.** On a host with subtle sandbox quirks, the agent may need a fix cycle or two, and in
the worst case reports an honest gap instead of auto-succeeding. That is strictly better than the status quo
(a silent next-day failure) and is the deliberate cost of not maintaining harness-specific troubleshooting.

## The teardown — the per-host layer dissolves to zero

Each of the ~12 adapter concerns routes to one of four fates; none is a per-host file. `shared/references/platform/`
(all nine files, `_common.md` included) is **deleted**.

| Adapter concern | Fate | Destination |
|---|---|---|
| Identity · Tool map · Closed-choice · Whole-file write · agent-data setup | **Neutral action-language** | Bodies already name the action ("dispatch a subagent", "ask a closed choice", "write the whole file atomically", "authenticate agent-data"). The agent maps to its own tool. The neutral `agent-data init --api-key … -y` path already works on every host. |
| Concurrent-detail-reads approval · Block-alert surface | **Self-aware conditional** (`AAS-LANG-03`) | "*If* your host gates subagents behind approval, get it once, then fan out; otherwise parallelize by default." / "*If* your host has an attention-pull surface, use it; otherwise the two file channels carry the failure." The agent introspects. (This moves the Codex approval gate from an adapter exception to a conditional — `PSG-SUB-09` local application.) |
| Headless invocation · Run recipe · Scheduling mechanism | **Neutral action-language + verify** | The agent composes the invocation/schedule for its own host; the **canary proves it** (Feature B). The directive states required conditions, not host tokens. |
| Exit-code trust | **Dropped** | The written record is already the *universal* success contract (Belief 6). Per-host exit-code trust is dead weight and is removed. |
| Model tier → id | **Self-selection, no table** | See below. |

**Where `_common.md`'s neutral content goes.** It is host-neutral already, so it re-homes into the shared
references it belongs to, as plain rules: the written-record contract → `errors.md`; the atomic whole-file
write rule → `conventions.md` (or `internals.md` alongside the registry write rules); the block-alert
two-file frame → `errors.md`; the neutral agent-data auth path → `agent-data-contract.md`.

**The setup directive holds the required-conditions, in-skill.** The steer for headless/unattended setup
lives *inside the scheduling skill* (`scheduling-and-consent.md` + `internals.md`), phrased as conditions +
verify — e.g. "ensure the unattended run can write the workspace and call agent-data; then verify by running
it." **No harness troubleshooting reference is created.** agent-data-side troubleshooting may still be
maintained where genuinely useful (it is the product/CLI, not the harness) in `agent-data-contract.md` /
`errors.md`; harness troubleshooting is not.

**The ~66 "see your platform's adapter →" pointers** rewrite to the neutral action, the self-aware
conditional, or the verify step, per the table above.

## Model selection without a table

The config keeps the portable tier token (`fast | balanced | high`) as **intent**. The body instructs, in
the sanctioned language (`AAS-AUTO-11` + `AAS-AUTO-07`):

> Dispatch every subtask with an **explicitly specified** model (a required slot — never omit it, or it
> silently inherits the wrong tier). Use the **least powerful model that can handle the task well, to
> conserve cost and increase speed**: the mechanical steps (dedup, prefilter, extraction, provenance) on
> your **cheapest** model; the per-posting fit **verdict is a judgment, so never your cheapest** — the
> least-powerful model that does *that judgment* well, scaled up for a higher-risk or ambiguous posting.

The agent binds these to concrete model ids **from its own roster**. No `tier → id` table, on any host.

## Doctrine touched (grounded in the live docs)

These edit `status: current` living docs — the beliefs and the guides that are ground truth today.

- **Belief 7 (`core-beliefs.md`).** Advocate the unattended schedule (consent preserved); demote the
  session-loop to a fallback; **add the mandatory config-time canary** as a precondition to recording a
  schedule.
- **Belief 12 / `AAS-AUTO-11`.** The model-selection language already fits ("least powerful that can do it
  well", judgment never the cheapest); the change is that the tier binds by **agent self-selection**, with
  no adapter table — reinforced by `AAS-AUTO-07` (required model slot).
- **`AAS-LANG-04` (bind model ids in the adapter).** Superseded for this pack by self-selection: the tier
  token stays portable; the id is chosen from the agent's own roster. Stated as a conscious deviation with
  the honest risk named below.
- **`AAS-LANG-07`.** Add the *verify-don't-encode* clause: where a host-specific action produces an
  observable artifact, runtime verification substitutes for the adapter the pure-abstraction floor would
  otherwise require.
- **`PSG-SUB-09` local application.** The Codex subagent-approval gate moves from "preserved as an adapter
  exception" to a **self-aware conditional** in the shared body.

## Concrete code changes

- **Delete** `shared/references/platform/` (nine files) and `scripts/validate_platforms.py`; remove the
  `validate_platforms` lane from `.github/workflows/ci.yml`.
- **Re-home** `_common.md`'s neutral content into `errors.md` / `conventions.md` / `agent-data-contract.md`.
- **Rewrite** the ~66 adapter pointers across `skills/` + `shared/` to neutral action / self-aware
  conditional / verify.
- **Scheduling** (`scheduling-and-consent.md`, `internals.md`, `onboarding.md` §7): advocate unattended;
  demote the session-loop; add the required-conditions setup directive **and the mandatory canary** before
  recording the schedule.
- **Runner** (`job-search-run/SKILL.md`) + `parallelism.md`: model dispatch as self-selection with a
  required explicit model; subagent approval + capacity as self-aware conditionals; success via the written
  record (drop exit-code-trust language).
- **`doc_lint.py`**: update `code_refs` across docs that cited the deleted adapters; there is no adapter
  structural gate to keep.

## Testing / how we know it works

- **The canary is the per-host runtime check.** Verification-by-execution is now a *runtime* per-host proof
  of write + agent-data + scheduling, so the shipped, manual cross-host matrix shrinks toward the
  irreducible behavioral residual.
- **Model-tier eval flips.** From "asserts the tier binding resolves from the adapter table" to "asserts the
  runner dispatches an **explicit, non-cheapest** model for the per-posting verdict."
- **Portability regression.** Trigger/behavioral evals per installable host; the neutral action-language is
  exercised by those runs. Un-installable hosts remain a labeled manual residual.

## Honest risks / soft spots (named, not hidden)

1. **Model tier has no runtime backstop.** A too-cheap judgment produces a normal-looking digest — the
   canary cannot tell it apart. Mitigation is the *required-slot* + the *"never your cheapest for judgment"*
   guardrail language. This is the design's one residual **risk** (not a residual adapter). Accepted.
2. **Run/update recipes become agent-composed** for the host. These are recoverable copy-paste failures, not
   silent ones, and are verifiable where the agent runs them.
3. **First-run scheduling may fail-and-report more often** on hosts with subtle sandbox quirks, since no
   harness troubleshooting is maintained. Accepted deliberately: no silent next-day failure is the priority,
   and the agent debugs its own host.

## Non-goals / out of scope

- **Design-doc status cleanup** (stale `aspirational`/`active` frontmatter on other docs) — a separate
  session.
- **Cloud/machine-off scheduling** — the target is unattended-on-this-machine (no session open); a cloud
  runner cannot see the local workspace or agent-data auth and is not in scope.
- **The multi-source plans** and **re-verifying the six structural-only harnesses live** — untouched here.
