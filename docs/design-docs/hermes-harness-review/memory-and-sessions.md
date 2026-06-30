---
title: Hermes Harness — Memory & Session History
status: current
verified: partial
last_reviewed: 2026-06-30
code_refs: [shared/references/platform/hermes.md, docs/design-docs/2026-06-30-hermes-job-search-concierge.md, docs/exec-plans/active/2026-06-30-hermes-concierge-layer.md, docs/design-docs/2026-06-29-hermes-native-plugin.md]
---
# Hermes Harness — Memory & Session History

Grounds the concierge layer's draft-from-prior-context feature in what the Hermes harness actually
exposes. The feature under review: "ask permission before using memory and session history to draft a
starting brief" and "create a concise, editable draft brief from memory and session history" (the
[concierge design](../2026-06-30-hermes-job-search-concierge.md), §3–§4 and the *Memory and
session-history policy* block). The job is to pin the gate that the
[exec plan](../../exec-plans/active/2026-06-30-hermes-concierge-layer.md) wants ("`job-search` asks
permission before drafting preferences from prior context") to real mechanics rather than assumed ones.
See `overview.md` for the cross-doc synthesis and the sibling review docs in this directory for the other
harness surfaces.

Boundary: two **independent** Hermes subsystems are in scope — built-in memory (`MEMORY.md` / `USER.md`)
and session history (`session_search`) — and only the slice that bears on drafting-from-prior-context.
This is not a general Hermes memory manual. Every literal below is a read of `NousResearch/hermes-agent`
at commit `184c10c`, **not a live run**; line numbers are pinned to that commit. The
[adapter](../../../shared/references/platform/hermes.md) cites `@main` instead, so treat any literal as
PIN-until-live, matching the adapter's own verification posture.

## What Hermes provides

The decisive shape: **memory is *pushed*, session history is *pulled*.** Built-in memory is auto-injected
into the system prompt and has no read action; the agent passively sees it and cannot un-see it. Session
history is reachable only through an explicit search call. Neither is the job-search workspace brief.

| Property | Built-in memory | Session history |
|---|---|---|
| Tool | `memory` — actions `add` / `replace` / `remove` + an atomic `operations` batch ([`memory_tool.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/tools/memory_tool.py):906–975, schema 1005–1070, registry 1076–1089) | `session_search` — FTS5 retrieval, shapes discovery / scroll / read / browse, zero LLM calls ([`session_search_tool.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/tools/session_search_tool.py):1–30, 619–740, registry 903–921) |
| How the agent consumes it | passive system-prompt injection at session start; **there is no `read` action** (`memory_tool.py`:11–14, 571–582; [`system_prompt.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/agent/system_prompt.py):426–444) | explicit model-callable search returning the **actual stored messages** (`session_search_tool.py`:619–740) |
| Backing store | `~/.hermes/memories` — `MEMORY.md` (agent notes, **2200 chars**) + `USER.md` (user profile, **1375 chars**) (`memory_tool.py`:55–57, 124) | `~/.hermes/state.db` — SQLite + FTS5, full message history ([`sessions.md`](https://github.com/NousResearch/hermes-agent/blob/184c10c/website/docs/user-guide/sessions.md):11, 15–27) |
| Scope | profile-global, cross-session, agent-curated, **tiny** — not a job-preferences store | profile-global, cross-session; **all** CLI + messaging sessions are auto-stored |
| Default state | **ON, no setup**: `memory_enabled` / `user_profile_enabled` default True; tool declares no external deps ([`config.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/hermes_cli/config.py):2029–2030; `memory_tool.py`:978–980; [`agent_init.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/agent/agent_init.py):1206–1218) | available whenever `state.db` exists (`session_search_tool.py`:743–749) |
| Writes | **unrestricted by default**: `write_approval` defaults False; a background self-improvement review can also auto-save entries (`config.py`:2043; `memory_tool.py`:957; [`memory.md`](https://github.com/NousResearch/hermes-agent/blob/184c10c/website/docs/user-guide/features/memory.md):221–272) | read-only retrieval |
| Freshness | snapshot **frozen at session start** — mid-session writes hit disk but do not change the prompt until the next session (`memory_tool.py`:571–582) | live read of the DB at call time |

**Cron / subagent isolation (decisive cross-check).** A cron run is built `skip_memory=True` (in-source
comment: cron system prompts "would corrupt user representations") with `platform="cron"`
([`scheduler.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/cron/scheduler.py):2476–2507).
Those two flags gate off both the built-in `MemoryStore` and the external provider (`agent_init.py`:1206,
1227; injection requires `_memory_store` at `system_prompt.py`:426–444), so **no `MEMORY.md`/`USER.md`
snapshot and no provider context enter a cron session's prompt.** The provider contract says the same
independently — `"cron"` is a recognized context and providers "should skip writes for non-primary
contexts"
([`memory_provider.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/agent/memory_provider.py):71–76).
`delegate_task` subagents are likewise `skip_memory=True`
([`delegate_tool.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/tools/delegate_tool.py):1288).

One nuance worth recording: a default cron run still **carries the `memory` and `session_search` tool
schemas** (the `hermes-cron` toolset is `_HERMES_CORE_TOOLS`, which lists both —
[`platforms.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/hermes_cli/platforms.py):43;
[`toolsets.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/toolsets.py)). The `memory` tool
is inert in cron (store is `None` → returns "Memory is not available", `memory_tool.py`:924–925), but
`session_search` reads `state.db` directly and is independent of the skipped store. Its DB-read path shows
no platform gate, so a cron agent **could in principle actively call `session_search` to read prior
interactive transcripts** — i.e. cron's "no prior context" means no *auto-injected* context, not
necessarily no *reachable* history. `[PIN — inferred: whether session_search is runtime-blocked in a
cron/subagent context is unconfirmed; clarify is also in-schema yet runtime-blocked in cron, so a gate may
exist that this read did not locate. Immaterial to job-search-run, whose self-contained prompt never calls
it.]`

**Headless ≠ cron.** The one-off path `hermes chat -Q -s job-search-run -q "…"` is distinct: `quiet_mode`
and `skip_memory` are independent flags. In the chat path only `--ignore-rules`
(`HERMES_IGNORE_RULES`) sets `skip_memory`
([`cli.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/cli.py):3655–3664;
[`main.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/hermes_cli/main.py):2347–2351), while
cron sets *both* explicitly (`scheduler.py`:2496 vs 2503). So a plain `-Q` headless run **loads memory
normally** — quiet does not imply memoryless. `[PIN: confirm against hermes chat --help; only the
quiet/skip_memory independence was traced, not every branch of the chat parser.]`

**External memory providers** (Honcho, Mem0, et al.) are opt-in and **off by default**: `memory.provider`
empty = built-in only; a provider activates only when set *and* `is_available()` (deps + creds), at most
one at a time, running *alongside* built-in memory, never replacing it (`config.py`:2046–2049;
`agent_init.py`:1227–1238;
[`memory-providers.md`](https://github.com/NousResearch/hermes-agent/blob/184c10c/website/docs/user-guide/features/memory-providers.md):9,
28–39). Honcho specifically needs `pip install honcho-ai` + a Honcho Cloud account or API key, is
configured via `hermes memory setup`, and injects into the **USER message at API time**, not the
`MEMORY.md` path
([honcho README](https://github.com/NousResearch/hermes-agent/blob/184c10c/plugins/memory/honcho/README.md):1–39).
For a default Hermes install, ignore providers — the concierge sees built-in memory only.

**Not memory substrate.** `insights.py` (usage/cost analytics over `state.db`), `session_recap.py`
(in-memory summary of the *current* session only — no cross-session, no LLM), and `active_sessions.py`
(live open-session leases) are auxiliary and are **not** the draft-from-context source
([`insights.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/agent/insights.py):1–17;
[`session_recap.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/hermes_cli/session_recap.py):1–19;
[`active_sessions.py`](https://github.com/NousResearch/hermes-agent/blob/184c10c/hermes_cli/active_sessions.py):1–6).

## How the job-search adapter uses it

The [adapter](../../../shared/references/platform/hermes.md) is **silent on built-in memory and
`session_search`** — it carries no PIN about either surface. That is a coverage gap, not a contradiction:
the concierge design (not the adapter) is what introduces the memory/session-history claims. The adapter's
load-bearing claims that this read touches:

| Adapter claim (section) | Source verdict | Note |
|---|---|---|
| "A cron run is a **fresh, isolated session with no prior context** and cannot `clarify`, so the scheduled prompt must be self-contained." (Scheduling) | **CONFIRMS** | `skip_memory=True` + `platform="cron"` → no `MEMORY.md`/`USER.md` snapshot, no provider context (`scheduler.py`:2503–2504; `agent_init.py`:1206, 1227). Precise reading: "no prior context" = no *auto-injected* context; `session_search` is still in-schema (see the inferred PIN above). `clarify` being in-schema-but-runtime-gated in cron is the precedent that in-schema ≠ functional. |
| `delegate_task` children are "a **fresh agent with no parent history**" / "the child knows nothing you do not hand it." (Concurrent detail reads) | **CONFIRMS** | Subagents are `skip_memory=True` (`delegate_tool.py`:1288) — no built-in or external memory; `memory_provider.py` also notes a subagent has no provider session. |
| Persona lives in `SOUL.md` under `HERMES_HOME`; inject job-search guidance via workspace `AGENTS.md`, kept separate from identity. (Identity) | **CONFIRMS** (tangential) | Cron is built `load_soul_identity=True` and loads `AGENTS.md` only when a workdir is set (`scheduler.py`:2497–2502): **SOUL identity is inherited on cron, persistent memory is not.** |
| Headless flags `-Q/-s/-q` and exit-code semantics. (Headless invocation, already `[PIN]`) | **PARTIAL** | Confirmed only that `quiet_mode` and `skip_memory` are independent and that a plain `-Q` run loads memory; the adapter's flag PIN stands. Candidate addition for the adapter: state that headless `-Q` is *not* memoryless (only `--ignore-rules` is). |

**CONTRADICTS: none found.** The only adapter action that meaningfully maps to memory is `clarify`
gating, and the design's §5 ("use `clarify` only for true multiple-choice decisions") is consistent with
the adapter's "`clarify` is unavailable in a headless or cron run." If the adapter is to absorb anything,
it is two facts it currently omits: built-in memory is **on-by-default and profile-global**, and **cron
has none**.

## Implications for the concierge layer

Assessed against the [concierge design](../2026-06-30-hermes-job-search-concierge.md). Verdicts:
**sound** (ship as written), **needs change** (re-word/extend before relying on it), **blocking** (would
mislead the user or the agent).

**1 — "ask permission before using memory and session history to draft a starting brief" (§3); "create a
concise, editable draft brief from memory and session history" (§4). NEEDS CHANGE (not blocking).** The
draft path is feasible in the interactive front door — `MEMORY.md`/`USER.md` is auto-injected and
`session_search` is available. But built-in memory is **already in the agent's context at session start**
(frozen snapshot, no read action): the gate cannot prevent memory from being *loaded*, only whether the
agent *actively synthesizes/drafts from* it. Session history is genuinely gated (an explicit
`session_search` call). Re-word the policy from "may inform … only with permission" toward "may be **used
to draft** only with permission," and let the prompt acknowledge that prior context is already visible —
the design's own "make clear that prior context would be used" (§3) is the right instinct; the policy
line just should not imply the gate is access control. Map session-history use cleanly to "do not call
`session_search` until permission is granted."

**2 — "If Hermes has enough prior context to be useful, `job-search` must ask permission …" (§3),
draft-first only when useful. NEEDS CHANGE (small).** The guard is correct — a fresh user has empty
`MEMORY.md`/`USER.md` and few/no sessions, so the draft path should no-op into the interview/import
choices. But the §1 *silent readiness check* lists "whether a preferences brief already exists" and does
**not** probe whether memory/sessions are non-empty. Add that probe to §1 so the concierge never offers
to "draft from prior context" when there is nothing to draft from (and never skips when there is).

**3 — "Inferred preferences should not be silently promoted to durable user-profile truth unless the user
explicitly confirms they are durable." SOUND, and load-bearing — strengthen.** This maps to a **real
leak channel**: Hermes has a `USER.md` profile store the agent writes to **autonomously by default**
(`write_approval` False), and a background self-improvement review can auto-save profile/memory entries.
So an inferred preference *can* reach durable Hermes profile truth without the user. Honor the policy
concretely: keep drafted/inferred preferences in the **workspace brief only** and never write them to
`USER.md` unless the user confirms durability. For a deployment that wants a hard gate on autonomous
profile writes, recommend setting `memory.write_approval=true`.

**4 — "The canonical working state is the local workspace brief, not Hermes global memory." SOUND.**
Well-founded: Hermes global memory is real but profile-scoped, cross-session, agent-curated, and **tiny**
(2200 / 1375 char caps) — explicitly not a preferences store. Anchoring on the workspace brief (owned by
the deterministic runtime, see the [native-plugin design](../2026-06-29-hermes-native-plugin.md)) avoids
profile-coupling and avoids depending on those small global stores. Worth stating in-brief *why* (the
caps + curation), so a reader understands the choice.

**5 — Does the scheduled (cron) run get to use memory/session history? SOUND as designed.** No
auto-context on cron (`skip_memory=True`, `platform="cron"`). The concierge already confines drafting to
the interactive front door and runs the self-contained `job-search-run` on cron, so it never relies on
cron-time memory; on-block alerting routes through the adapter's *Block-alert channel*, not memory. Keep
the draft-from-context feature **strictly** in the interactive front door — never attempt
memory-assisted drafting inside the cron or `--ignore-rules` headless pass.

**6 — Drafting from "session history" via `session_search` (§4). NEEDS CHANGE (caution).**
`session_search` returns **raw past messages from all prior sessions** in the profile (interactive ranked
above cron; subagent/tool sessions hidden — `session_search_tool.py`:36–50, 106–120). Synthesizing a job
brief from arbitrary past conversations can surface irrelevant or sensitive content from unrelated work —
exactly the "creepy or overconfident" draft the design warns against (§3). The permission prompt + "draft,
not settled truth" framing mitigate; strengthen by **narrowing `session_search` queries to job/career
terms** and **showing the user what was drawn on**, so the draft is legible and bounded.

## Open questions / must-verify-live

Only a running Hermes can settle these; all are PIN-tagged and consistent with the adapter's source-cited,
not-yet-live posture.

- **`session_search` reachability in cron/subagent.** In-schema and the DB-read path shows no platform
  gate, so a cron/subagent could likely call it — but `clarify` is in-schema yet runtime-blocked in cron,
  so a gate may exist that this read did not find. Immaterial to `job-search-run` (never calls it), but
  confirm before assuming cron is hermetically history-free.
- **Background self-improvement → `USER.md` write path.** The autonomous write is documented (`memory.md`)
  and `write_approval` defaults False, but the end-to-end write was **not** code-traced. Confirm whether
  the self-improvement review is on by default and whether it writes `USER.md` without confirmation —
  this is the factual basis for implication 3.
- **Headless flag wiring.** Confirm `-Q/-s/-q` against `hermes chat --help` and that a plain `-Q` run is
  not memoryless (only `--ignore-rules` skips memory). Inherits the adapter's existing headless `[PIN]`.
- **Front-door platform string.** Which platform the interactive concierge runs under (`cli` vs a gateway
  platform) was not traced per-skill. Both load built-in memory by default, so feasibility holds either
  way; the value matters only if a future gateway platform changed the memory default.
- **Commit drift.** Findings are pinned to `184c10c`; the adapter cites `@main`. Confirm no drift in the
  memory/`session_search` defaults between the two on the live pass.
