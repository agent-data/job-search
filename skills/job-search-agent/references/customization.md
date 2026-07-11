# Customizing the Job Search Agent

This reference covers the flexibility and customization workflows — how to honor special requests, narrow results, tune the rubric, and add new capabilities — without breaking the clean defaults.

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

**Source-side (fewer postings fetched):** Edit `queries[]` in `config.yaml`. Tighten `keywords`, add a `location`, lower `limit`, or set `enabled: false` to pause a query entirely. This reduces API calls and noise before judgment runs.

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

Four `config.yaml` keys (schema in `shared/references/conventions.md`) control how much the system fetches,
how fresh it is, whether detail reads run in parallel, and how carefully it reads each posting.

**Recency window — `search.freshness`**

Filters each posting's `posted_at` on the client side after the feed is returned (the search API has no date parameter).

The four values and the exact window each admits (and which is the default) are in the config schema — see
`shared/references/conventions.md` (the `config.yaml` section).

Narrowing the window keeps the digest focused on live roles. Widening it is useful when you haven't run a search in a while and want to catch up.

**Feed size — `queries[].limit`**

Sets how many postings each query pulls; its range and default (and the API-vs-template distinction) are in the config schema — see `shared/references/conventions.md`. A higher limit fetches more raw postings per query, but it is not pagination — there is no way to walk deeper pages. The practical path to seeing more new postings is **breadth + frequency**: several varied queries with meaningful keyword differences, run regularly, with dedup preventing repeats from inflating the digest.

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
behind approval, e.g. Codex). It also falls back to sequential whenever the host lacks or refuses subagents.

**Detail-read model — `search.detail_model`**

After the primary pass scans summaries, the agent reads the full details for every promising posting. When
the run uses the parallel fan-out (the default where the host supports it), it fans out one detail-read
subagent per posting (see
`references/parallelism.md` for the general pattern; the fan-out primitive and sequential fallback defer to
your platform's adapter → Concurrent detail reads). Each subagent follows the `evaluate-job-fit` skill. This
key controls which tier those detail readers use — the literal model each tier maps to lives in your
platform's adapter → Model tiers. When discussing this on a specific host, name the exact model IDs from that
adapter → Model tiers.

The four tiers, what each is for, and which is the default are in the config schema — see
`shared/references/conventions.md` (the `config.yaml` section).

`fast` is the right starting point for most searches. It is a touch looser on subtle qualitative calls — occasionally emitting an out-of-vocabulary band or a stray numeric value — but the consolidation step after all subagents return validates and coerces every verdict before anything reaches `jobs.jsonl` or the digest, so no invalid output persists. For roles where the brief's distinctions are fine-grained or the must-have/red-flag list is long, set `detail_model: balanced` (or `high`) to improve judgment fidelity. This is a **fidelity/speed tradeoff**, not a quality-gate — the defaults are safe either way.

> **Note:** Per-subagent tier selection is effective only on hosts that support isolated-context subagents —
> see your platform's adapter → Concurrent detail reads. The adapter notes whether per-subagent model selection
> even exists; a single-model host makes the knob inert. If parallel reads are disabled, unavailable, or refused,
> the same tier still describes the intended detail-read fidelity, but the runner evaluates sequentially.

---

## 5. Adding a new capability or skill

See the **"Extending & contributing"** section in `SKILL.md` for the full workflow. Key points:

- Shared references live in `shared/references/*.md`; helper scripts live in `scripts/`. Files under `skills/<skill>/references/` and `skills/<skill>/scripts/` are **generated**, not authored — after any shared edit, run `./scripts/build.sh` to re-sync.
- New skills go under `skills/<skill>/` with a `SKILL.md` and `evals/evals.json`. Evals run through the fake `agent-data` shim in `tests/`, not the live CLI.
- Keep `scripts/philosophy_guard.py` green before opening a PR (no numeric scores or score-threshold config in tracked paths).

Full contributor guide: `CONTRIBUTING.md`.
