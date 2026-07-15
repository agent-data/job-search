# Customizing the Job Search Agent

This reference covers the flexibility and customization workflows — how to honor special requests, narrow results, tune the rubric, and add new capabilities — without breaking the clean defaults.

**Contents:** [1. Honoring an explicit score request](#1-honoring-an-explicit-score-request) · [2. Adding a custom filter](#2-adding-a-custom-filter-or-narrowing-results) · [3. Changing how postings are judged](#3-changing-how-postings-are-judged) · [4. Tuning the search feed & detail reads](#4-tuning-the-search-feed--detail-reads) · [5. Explaining agent-data usage](#5-explaining-agent-data-usage) · [6. Adding a new capability or skill](#6-adding-a-new-capability-or-skill)

---

## 1. Honoring an explicit score request

Default output is qualitative — relevant + weak/moderate/strong + reasoning — with no numeric scores. But the agent is yours and flexible: when a user **explicitly** asks for a 0–100 score or a ranking number, **honor it in your reply**.

Two hard rules:

1. **Note once** that scoring is non-default and that the qualitative bands + reasoning are the real signal (so the user stays informed, not silently switched onto a scored system).
2. **Never persist** the requested numbers into a digest, the brief, `config.yaml`, or `jobs.jsonl` — those stay band-only so the default experience and the CI philosophy guard (`scripts/philosophy_guard.py`) remain clean.

If the user wants the numbers saved, write them to a clearly-named side file (e.g. `reports/<date>-scored.md`), never the canonical event log.

---

## 2. Adding a custom filter or narrowing results

Two routes depending on where you want the narrowing to happen:

**Source-side (fewer postings fetched):** Edit `queries[]` in `config.yaml`. Tighten `keywords`, add a `location`, lower `limit`, or set `enabled: false` to pause a query entirely. Lowering `limit` reduces rows returned by each call; disabling a query reduces the number of first-page calls. Both reduce noise before judgment runs.

**Judgment-side (postings fetched but screened out):** For criteria like "only fully-remote" or "no agencies", add them to the **preferences brief** (`preferences.md`) as a must-have or red flag. `evaluate-job-fit` reads the brief and enforces the criterion qualitatively — a must-have that is absent makes the posting not relevant; a red flag present makes it weak or not relevant with a named reason.

Do NOT invent a numeric filter or threshold to implement either kind of narrowing. Importance and exclusion live in the brief's prose buckets, never in math.

---

## 3. Changing how postings are judged

`evaluate-job-fit` is the rubric. It reads the preferences brief and applies whatever priority structure the brief expresses.

To shift the importance of a factor, move it between the brief's buckets:

| Bucket | Effect on judgment |
|---|---|
| **Must-have** | Absence makes the posting not relevant |
| **Strong preference** | Absence or mismatch weakens the rating |
| **Nice-to-have** | Noted positively when present; absence doesn't hurt |
| **Red flag** | Presence weakens or disqualifies the posting |

Importance lives in the bucket assignment, never in numeric weights or score multipliers. Run the **job-preference-interview** skill for a guided way to restructure the brief, or edit `preferences.md` directly.

---

## 4. Tuning the search feed & detail reads

Five settings in `config.yaml` (schema in `../../../shared/references/conventions.md`) control page size,
review depth, recency, whether detail reads run in parallel, and how carefully the agent reads each posting.

**Recency window — `search.freshness`**

Sets how recent a posting must be. It resolves to a `published_on_or_after` cutoff the search API
applies server-side (with a client-side fallback where a deployment ignores it), filtering each posting
by its effective publication date. The four values, the window each admits, and the default are in the
config schema — see `../../../shared/references/conventions.md` (the `config.yaml` section). Narrowing
keeps the digest focused on live roles; widening catches up after a gap. You can also ask for a one-off
window that isn't a preset — "only postings from the past day", "since June 1" — and that single run
uses it in place of the saved value.

**Feed size — `queries[].limit`**

Sets the maximum rows requested on each query/source call; its range and default (and the
API-vs-template distinction) are in the config schema. It is a per-call page size, never the total number
of roles reviewed in a run.

**Review depth — `search.max_new_postings_per_run`**

Omit this advanced setting for normal first-page coverage. A positive integer asks the agent to judge up
to that many unique unseen roles; exact `"all"` asks it to exhaust the currently traversable Ashby,
Greenhouse, and Lever results. LinkedIn remains one page. The accepted values and run-record meanings live
in `../../../shared/references/conventions.md`; the cursor and metering facts live in
`../../../shared/references/agent-data-contract.md`.

Interpret time scope before taking action:

| User wording | Scope and effect |
|---|---|
| “now,” “once,” “this run” | one-off override; do not write config |
| “each run,” “from now on,” “every time” | saved setting; write only after preview and confirmation |
| ambiguous depth request such as “scan everything” | default to one run and say so before confirmation |
| “go back to normal,” “use first-page coverage” | reduce or remove the saved setting immediately when the time scope is recurring |

Before any enablement or increase, compute the first-page baseline from the current config:

```text
first-page search calls per run = enabled queries × enabled sources
scheduled baseline = first-page calls per run × runs in the named period
```

Then state the unknown additions: every continuation page on one company-board stream adds one metered
search call, and every full-posting read adds one metered detail call. A finite target bounds roles judged,
not page calls, because known and duplicate rows can require more pages. `"all"` has no reliable call
ceiling in advance. If a dollar equivalent helps, load the current verified rate from the canonical
agent-data contract and label the result **pay-as-you-go equivalent**, never an actual charge.

Ask for an explicit yes to the exact one-off or saved scope before invoking a run or atomically writing
config. A saved value is durable consent, so later scheduled runs do not ask again. A smaller finite target,
`all` to finite, removal, or a one-off first-page override is a reversible decrease and takes effect without
confirmation.

**High-quality scope handling**

- “Review up to 50 new postings this run.” → preview a finite one-off; after yes, run without changing config.
- “Review up to 50 every run.” → preview a recurring finite change; after yes, save `50`.
- “Scan everything.” → explicitly make it one-off, name the unbounded-in-advance additions, then confirm.
- “Scan everything every time.” → preview recurring exhaustive depth; after yes, save `"all"`.
- “Go back to normal first-page coverage.” → remove the saved setting immediately.

**Low-quality near-misses**

- Treating “scan everything” as recurring and silently saving `"all"`.
- Writing config or starting metered work before the user confirms the previewed scope.
- Describing the review target as a credit allowance or promising that it caps page calls.

Emulate the high-quality examples' time-scope resolution, preview ordering, and exact confirmation; never
use the low-quality near-misses as alternate implementations.

**Parallel detail reads — `search.parallel_detail_reads`**

Controls whether promising postings are read through parallel subagents where the host supports them.

| Value | Behavior |
|---|---|
| unset | An interactive front-door flow may ask once on hosts that need explicit approval; the headless runner never asks and takes the host default (parallel where no approval is required) |
| `true` | User approved parallel detail-read subagents where available |
| `false` | Read details sequentially |

Only `job-search` / the home view writes this preference after talking with the user. `job-search-run` is
headless: it reads the value and never edits config itself — `false` reads sequentially, `true` fans out, and
unset takes the host default (parallel where no approval is required; sequential on hosts that gate subagents
behind approval — see `../../../shared/references/parallelism.md`). It also falls back to sequential
whenever the host lacks or refuses subagents.

**Detail-read model — `search.detail_model`**

After the primary pass scans summaries, the agent reads the full details for every promising posting. When
the run uses the parallel fan-out (the default where the host supports it), it fans out one detail-read
subagent per posting (see
`../../../shared/references/parallelism.md` for the general pattern, the host's own fan-out primitive, and the
sequential fallback). Each subagent follows the `evaluate-job-fit` skill. This
key controls which tier those detail readers use — the agent binds the tier to a concrete model from its own
roster. If the user asks which model a tier maps to on this host, name the concrete model you'd use.

The four tiers, what each is for, and which is the default are in the config schema — see
`../../../shared/references/conventions.md` (the `config.yaml` section).

`balanced` — the **mid-tier reviewer floor** — is the default, because the per-posting fit verdict is a judgment, not a mechanical step: a well-specified, bite-sized review belongs on a mid-tier model, not the cheapest tier. Scale up with `detail_model: high` where the brief's distinctions are fine-grained or the must-have/red-flag list is long. Opt down with `detail_model: fast` (the cheapest tier) for faster, lighter reads — a touch looser on subtle qualitative calls (occasionally an out-of-vocabulary band or a stray numeric value), though the consolidation step after all subagents return still validates and coerces every verdict before anything reaches `jobs.jsonl` or the digest, so no invalid output persists. This is a **fidelity/speed tradeoff**, not a quality-gate — and the genuinely mechanical bulk (dedup, the summary prefilter, provenance) stays cheap regardless of this tier.

> **Note:** Per-subagent tier selection is effective only on hosts that support isolated-context subagents.
> On a single-model host, or one without isolated-context subagents, the knob is inert. If parallel reads are
> disabled, unavailable, or refused, the same tier still describes the intended detail-read fidelity, but the
> runner evaluates sequentially.

---

## 5. Explaining agent-data usage

“Explain my agent-data usage” is a read-only local explanation. Read recent `runs/*.json` records and lead
with actual `agent_data_usage.metered_calls`; then explain the stored `by_operation` breakdown and the
configured outcome drivers (frequency, enabled queries, enabled sources, and review mode). Use each
historical run's stored decimal strings as written—do not recompute an old equivalent with today's rate.

When `payg_equivalent_usd` is present, label it a **pay-as-you-go equivalent**. If live account-plan metadata
is absent, say the equivalent is not an actual charge and direct account-specific plan, allowance, and
billing questions to <https://agent-data.motie.dev/settings/billing>. Do not call agent-data for this
explanation, mutate config or registry state, infer a remaining balance, or claim a plan, rollover, renewal,
or exhaustion date. Do not add or recommend `budget`, `credits`, or `cost` config fields. Load current exact
pricing and metering facts only from `../../../shared/references/agent-data-contract.md`.

---

## 6. Adding a new capability or skill

See the **"Extending & contributing"** section in `SKILL.md` for the full workflow. Key points:

- Shared references live in `shared/references/*.md`; helper scripts live in `scripts/`. Each fact is single-homed there and referenced in place under the bundle — there are no generated per-skill reference copies to re-sync (`./scripts/build.sh` regenerates only the build stamp).
- New skills go under `skills/<skill>/` with a `SKILL.md` and `evals/evals.json`. Evals run through the fake `agent-data` shim in `tests/`, not the live CLI.
- Keep `scripts/philosophy_guard.py` green before opening a PR (no numeric scores or score-threshold config in tracked paths).

Full contributor guide: `CONTRIBUTING.md`.
