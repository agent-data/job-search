---
title: Codex Portability — What It Takes to Run job-search on OpenAI Codex
status: aspirational
verified: partial
last_reviewed: 2026-06-22
code_refs: [shared/references/internals.md, shared/references/voice.md, shared/references/parallelism.md, scripts/build.sh, .claude-plugin/plugin.json]
---
# Codex Portability — What It Takes to Run job-search on OpenAI Codex

> **Aspirational assessment, not a commitment.** This doc answers *"what's necessary to extend this
> plugin to Codex?"* It maps the work and recommends an approach; it does **not** build a Codex
> bundle, and nothing here has been greenlit. The product today targets Claude Code only —
> [AGENTS.md](../../AGENTS.md) and [ARCHITECTURE.md](../../ARCHITECTURE.md) frame it as "Claude Code
> as a job-search OS," and there is no other-harness language anywhere in the repo. Treat this as the
> scoping study you would act on *if* a Codex target is adopted.

## Verdict

**Feasible, and mostly mechanical.** The data / state / judgment core is already harness-agnostic and
needs zero Codex-specific work. The Claude coupling is shallow and concentrated — it lives in a
handful of [`shared/references/`](../../shared/references/internals.md) files plus a few skill
playbooks, and every Claude-specific mechanism has a clean Codex equivalent. The only founding-belief
collision — scheduling — resolves without violating the belief, because Codex ships a native,
consent-based scheduler (**Automations**) that installs nothing on the user's machine.

Recommended path: **keep one source tree and add a thin platform-adapter layer**, so
[`build.sh`](../../scripts/build.sh) emits both the Claude plugin bundle and a Codex skill bundle.
That preserves the single-source-of-truth belief (#5 in [core-beliefs.md](core-beliefs.md)) instead
of forking.

## Verified against the local install (2026-06-22)

The Codex facts below were checked against `developers.openai.com/codex/*`, the superpowers
`codex-tools.md` mapping, **and the Codex already installed on this machine**, which grounds the
assessment:

- `codex-cli 0.140.0` is installed; `~/.codex/` is a full install (`config.toml`, `skills/`,
  `plugins/`, `sessions/`, …).
- `~/.codex/skills/` exists but is empty; **`~/.agents/skills/` is already populated** (with
  `clerk-cli`, `clerk-webhooks`) — concrete proof the cross-runtime skills path is live here and is a
  real install target.
- `~/.codex/config.toml` sets `model = "gpt-5.5"` and `model_reasoning_effort = "high"` and has a
  `[features]` block — but `multi_agent` is **not** currently enabled, so the subagent fan-out would
  need that flag turned on (see the delta map).

## Ports unchanged — the harness-agnostic core

These need no Codex-specific work; they are data, contracts, and judgment, defined once and pointed to
(never restated) here:

- The user-facing config schema and the prose preferences brief — [`conventions.md`](../../shared/references/conventions.md).
- The append-only job event log and its fold-to-state rule, the per-run audit records, and the digest
  format — [`conventions.md`](../../shared/references/conventions.md).
- The machine registry (XDG-based, env-overridable) and the workspace-discovery / first-run
  precedence — POSIX one-liners in [`internals.md`](../../shared/references/internals.md).
- The named-error catalog and the agent-data CLI contract —
  [`errors.md`](../../shared/references/errors.md) and [`agent-data-contract.md`](../../shared/references/agent-data-contract.md).
- The voice rules and the qualitative-only philosophy — [`voice.md`](../../shared/references/voice.md)
  and [core-beliefs.md](core-beliefs.md).

The agent-data CLI is itself harness-independent — the skills already shell out to it, and Codex
shells out the same way.

## Delta map (Claude → Codex)

Severity = how much work / risk the swap carries, not importance.

| Mechanism (where it's coupled) | Codex equivalent | Sev | Action |
|---|---|---|---|
| Skill frontmatter `user-invocable` / `disable-model-invocation` (every `SKILL.md`) | `name` + `description` frontmatter, plus an optional `agents/openai.yaml` (`policy.allow_implicit_invocation`, `interface.display_name`) | LOW | Generate `openai.yaml` per skill at build |
| Bundled per-skill [`references/`](../../shared/references/internals.md) dir | Native — Codex skills read `references/`, `scripts/`, `assets/` | LOW | none |
| Loose-skill install path `~/.claude/skills/` | `~/.codex/skills/` or the cross-runtime `~/.agents/skills/` | LOW | Build emit target / install step |
| Packaging [`.claude-plugin/plugin.json`](../../.claude-plugin/plugin.json) + `marketplace.json` | Codex "plugin" bundle (distribution layer over skills; manifest format under-documented) **or** ship as a skills directory | MED | Add a Codex manifest or skills-dir emit |
| Namespaced slash `/job-search:job-search-run` ([`internals.md`](../../shared/references/internals.md)) | `$job-search-run` mention, the `/skills` picker, or implicit-by-description | MED | Rewrite the verbatim recipe strings |
| The closed-choice question tool ([`voice.md`](../../shared/references/voice.md), onboarding, interview) | **No structured-choice UI in Codex** — fall back to the numbered-prose path `voice.md` already specifies for non-interactive hosts | **HIGH** | The fallback exists; accept an onboarding UX regression |
| Subagent fan-out ([`parallelism.md`](../../shared/references/parallelism.md), [`job-search-run`](../../skills/job-search-run/SKILL.md)) | `spawn_agent` / `wait_agent` / `close_agent`, gated behind `[features] multi_agent = true` in `~/.codex/config.toml` | MED | Framing is already tool-neutral; document the flag as a prereq |
| `/loop` scheduling ([`internals.md`](../../shared/references/internals.md)) | **Codex Automations** — cron-syntax scheduled runs + thread-heartbeat wake-ups, consent-based, nothing installed on the machine | MED | Map the recipe; set the registry `scheduling.mechanism` to an automation value |
| `claude -p` headless ([`job-search-run`](../../skills/job-search-run/SKILL.md), RELIABILITY, TESTING) | `codex exec` (`--json`, `--output-schema`, `--sandbox`, `-o`) | MED | `codex exec` returns **real exit codes** (see belief note) |
| Desktop notification (the `notify` block — [`conventions.md`](../../shared/references/conventions.md)) | Codex App **Triage** / notifications; no-op on pure CLI | MED | Remap or drop on CLI |
| Model buckets `haiku` \| `sonnet` \| `opus` \| `inherit` (customization) | Codex models (`gpt-5.x` / `gpt-5-codex` / o-series; local default is `gpt-5.5`) + `inherit` | LOW–MED | Keep the fast-vs-capable buckets, map the names |
| File tools + "never shell redirection" ([`internals.md`](../../shared/references/internals.md), [`conventions.md`](../../shared/references/conventions.md)) | `shell` (`cat`/`grep`/`find`) + `apply_patch` for structured create/edit | LOW | Re-phrase "use the file tools" tool-neutrally |
| CI gate `claude plugin validate --strict` | Codex skill validation, or none | LOW | Dev-side only |
| Instructions file `CLAUDE.md` vs **`AGENTS.md`** | Codex reads `AGENTS.md` + `~/.codex/AGENTS.md` | LOW | Repo already ships [AGENTS.md](../../AGENTS.md) — already aligned |

## Founding-belief reckoning

Recommendations the build would act on — **not** edits made by this doc.

- **Belief #7 (consent-gated autonomy)** names "Claude Code's native `/loop`" and forbids the agent
  installing crontab/launchd. The belief's *intent* — consent-gated, with no privileged write to the
  user's machine — is mechanism-agnostic. Codex Automations satisfy it exactly (the user opts in;
  nothing is installed). Recommend re-wording the belief to "the host's native, consent-gated
  scheduler (Claude Code `/loop`; Codex Automations)." The belief holds; only the mechanism name
  generalizes. See [core-beliefs.md](core-beliefs.md).
- **Belief #6 (deterministic, testable, headless)** says to read run outcome from the written record,
  never the exit code, because a headless `claude -p` exits 0 even when it halted. That is a
  Claude-`-p` workaround: `codex exec` returns real exit codes. The record-based surfacing stays the
  design regardless (the home view reads it), but Codex can additionally trust the exit code.
- **Belief #5 (single source of truth)** must be preserved by the platform layer: `build.sh` emits
  both targets, and no one hand-edits a generated bundle.
- The "Claude Code as a job-search OS" framing in [AGENTS.md](../../AGENTS.md) /
  [ARCHITECTURE.md](../../ARCHITECTURE.md) would generalize to "an agent harness."

## Recommended approach — one tree + a platform-adapter layer

Introduce a thin per-platform adapter under `shared/references/` (e.g. `platform/claude.md` +
`platform/codex.md`, or a single two-column `harness-map.md`) that pins the ~6 coupled concepts:

1. the scheduling recipe + the registry `scheduling.mechanism` value,
2. the closed-choice question mechanism + its prose fallback,
3. the subagent-dispatch verb + how it's enabled,
4. the headless-invocation command + its exit-code semantics,
5. the model-bucket name mapping,
6. the notification channel.

Refactor the coupled reference files so they reference the *active platform's* adapter instead of
naming Claude tools inline (most of the prose — e.g. [`parallelism.md`](../../shared/references/parallelism.md)
and the question rules in [`voice.md`](../../shared/references/voice.md) — is already tool-neutral and
needs little change). Extend [`build.sh`](../../scripts/build.sh) to emit a Codex bundle (`SKILL.md` +
`references/` + a generated `agents/openai.yaml`) into a `dist/codex/` output (or install straight to
`~/.agents/skills/`). Keep the evals and CI green for **both** targets.

## Phased build roadmap (when greenlit)

- **P0 — spike (cheap proof).** Copy the five skills into `~/.agents/skills/`, hand-swap the coupled
  strings, and run one live search via `codex exec` against agent-data. Proves the portable core runs
  on the Codex already on this machine before any refactor.
- **P1 — adapter.** Factor the platform adapter into `shared/references/`; keep the Claude build
  byte-identical (regression-safe).
- **P2 — Codex emit.** Add the Codex target to `build.sh` (+ `openai.yaml` generation + Codex
  manifest).
- **P3 — scheduling.** Wire the Codex Automations mapping and the registry mechanism value; update the
  scheduling playbook and onboarding.
- **P4 — UX.** Verify the numbered-prose question fallback on Codex; map model buckets; route
  notifications through Triage.
- **P5 — generalize.** Update the beliefs / AGENTS framing; add a Codex row to the
  [TESTING](../../AGENTS.md) matrix; add CI for the Codex bundle.

## Open risks / unknowns

- Codex's **plugin-bundle manifest** is under-documented — the *skill* format is clear, the
  multi-skill *bundle/distribution* format less so. P0/P2 should pin it empirically.
- `spawn_agent` requires the user to enable `multi_agent` (not on by default — confirmed off in the
  local `config.toml`). Without it, the detail-read fan-out runs sequentially.
- **No structured-choice UI** on Codex — a real onboarding UX regression versus the question box;
  the prose fallback is functional but plainer.
- Automations and Triage are richest in the Codex **App**; a pure-CLI user gets `codex exec` plus
  their own cadence and loses the desktop notification.
- The **agent-data CLI must be on PATH inside the Codex sandbox**, and `codex exec --sandbox` /
  approval mode must permit the npm-installed binary and its network call.
