# Customizing the Job Search Agent

This reference covers the flexibility and customization workflows — how to honor special requests, narrow results, tune the rubric, and add new capabilities — without breaking the clean defaults.

---

## 1. Honoring an explicit score or cost-math request

Default output is qualitative — relevant + weak/moderate/strong + reasoning — with no scores and no cost math. But the agent is yours and flexible: when a user **explicitly** asks for a 0–100 score, a ranking number, or per-call cost estimates, **honor it in your reply**.

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

Importance lives in the bucket assignment, never in numeric weights or score multipliers. Run `/job-preference-interview` for a guided way to restructure the brief, or edit `preferences.md` directly.

---

## 4. Tuning the search feed & detail reads

Three `config.yaml` keys (schema in `shared/references/conventions.md`) control how much the system fetches, how fresh it is, and how carefully it reads each posting.

**Recency window — `search.freshness`**

Filters each posting's `posted_at` on the client side after the feed is returned (the search API has no date parameter).

| Value | What passes |
|---|---|
| `any` | Everything in the feed regardless of age |
| `past-week` | Posted within the last 7 days |
| `past-2-weeks` | Posted within the last 14 days *(default)* |
| `past-month` | Posted within the last 30 days |

Narrowing the window keeps the digest focused on live roles. Widening it is useful when you haven't run a search in a while and want to catch up.

**Feed size — `queries[].limit`**

Sets how many postings each query pulls (1–100, default 25). A higher limit fetches more raw postings per query, but it is not pagination — there is no way to walk deeper pages. The practical path to seeing more new postings is **breadth + frequency**: several varied queries with meaningful keyword differences, run regularly, with dedup preventing repeats from inflating the digest.

**Detail-read model — `search.detail_model`**

After the primary pass scans summaries, the agent fans out one detail-read subagent per promising posting in parallel (see `references/parallelism.md` for the general pattern). Each subagent follows the `evaluate-job-fit` skill. This key controls which model those subagents use.

| Value | Behavior |
|---|---|
| `haiku` | Fast and light *(default)* |
| `sonnet` | More deliberate on nuanced qualitative judgments |
| `opus` | Highest fidelity |
| `inherit` | Uses the same model as the top-level run |

Haiku is the right starting point for most searches. It is a touch looser on subtle qualitative calls — occasionally emitting an out-of-vocabulary band or a stray numeric value — but the consolidation step after all subagents return validates and coerces every verdict before anything reaches `jobs.jsonl` or the digest, so no invalid output persists. For roles where the brief's distinctions are fine-grained or the must-have/red-flag list is long, set `detail_model: sonnet` (or `opus`) to improve judgment fidelity. This is a **fidelity/speed tradeoff**, not a quality-gate — the defaults are safe either way.

---

## 5. Adding a new capability or skill

See the **"Extending & contributing"** section in `SKILL.md` for the full workflow. Key points:

- Shared references live in `shared/references/*.md`; helper scripts live in `scripts/`. Files under `skills/<skill>/references/` and `skills/<skill>/scripts/` are **generated**, not authored — after any shared edit, run `./scripts/build.sh` to re-sync.
- New skills go under `skills/<skill>/` with a `SKILL.md` and `evals/evals.json`. Evals run through the fake `agent-data` shim in `tests/` — no metered API calls.
- Keep `scripts/philosophy_guard.py` green before opening a PR (no numeric scores, budget/cost/credit fields, or score-threshold config in tracked paths).

Full contributor guide: `CONTRIBUTING.md`.
