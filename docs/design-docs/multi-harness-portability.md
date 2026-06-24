---
title: Multi-Harness Portability — Research Dossier (Codex · Cursor · opencode · Gemini CLI · Copilot CLI · Factory Droid · Pi)
status: aspirational
verified: partial
last_reviewed: 2026-06-22
code_refs: [shared/references/internals.md, shared/references/conventions.md, shared/references/voice.md, shared/references/parallelism.md, shared/references/errors.md, shared/references/agent-data-contract.md, skills/job-search/references/onboarding.md, skills/job-search/references/home.md, skills/job-search-agent/references/scheduling-and-consent.md, skills/job-search-agent/references/customization.md, skills/job-search-run/SKILL.md, scripts/build.sh, .claude-plugin/plugin.json, docs/design-docs/codex-portability.md]
---
# Multi-Harness Portability — Research Dossier

> **Raw research material, not a commitment.** This dossier consolidates seven adversarially-verified
> single-harness portability studies into one reference so the lead can synthesize a house-style
> exec-plan. It maps the work; it builds nothing. The product today targets Claude Code only —
> [AGENTS.md](../../AGENTS.md) frames it as "Claude Code as a job-search OS." The per-harness Codex
> study at [codex-portability.md](codex-portability.md) is the structural model this generalizes.
> Every per-platform claim below carries a confidence and a source; the **Open risks** section
> (§6) pulls every `unverified`/`wrong` verdict from the underlying studies forward verbatim so the
> synthesizer inherits the doubt, not just the conclusions.
>
> **Provenance.** Each platform study was produced by a research subagent and then re-checked by a
> separate adversarial verifier (the `.verdict` block). "Verified" below means *a verifier confirmed
> it against a file read or a live command this session*; it does **not** mean observed on a running
> instance of that harness unless the row says so. Codex is the only harness **installed locally**
> (`codex-cli 0.140.0`); Cursor, opencode, Gemini CLI, the standalone Copilot binary, Factory Droid,
> and Pi are **not installed**, so their runtime claims are grounded in superpowers' shipped adapters
> + vendor docs, never a live probe.

---

## 1. Per-platform adapter table

One row per platform. **Sev/confidence** is the verifier's overall confidence in the row, not the
work's importance. Adapter cells name the *mechanism*; the literal recipe strings belong in a future
`shared/references/platform/<name>.md` (see §3), not inline.

| Platform | Distribution manifest (where it ships) | Subagent dispatch | Closed-choice question UI | Scheduling: native-local / cloud / relaxed-cron fallback | Headless cmd + exit codes | `agent-data init` flag | Confidence |
|---|---|---|---|---|---|---|---|
| **OpenAI Codex** (codex-cli 0.140.0, **installed**) | `.codex-plugin/plugin.json` (JSON) beside `.claude-plugin/`; `skills:"./skills/"` points at the SAME one tree; no codegen (sync script rsyncs, not transforms) | **Yes, native** — `spawn_agent` / `wait_agent` / `close_agent`. `multi_agent` is `stable/true` (on by default in 0.140.0); older builds need `[features] multi_agent=true`. Live run observed a finite thread limit, so batching/close discipline is required | **None** — no structured-choice tool. Numbered-prose fallback per voice.md. Inferred from tool/feature inventory, not an explicit "none exists" statement | **NATIVE-LOCAL: Codex Automations** (cron-syntax, runs in the on-disk project dir, sees `~/.job-search` + local agent-data auth — point its working dir at the workspace so `workspace-write` can persist run artifacts, **unverified**). App/daemon required; **pure CLI has no automation subcommand** → relaxed-cron fallback there. Cloud `codex cloud exec` rejected (can't see local workspace) | `codex exec` (alias `e`); `--json`, `--output-schema`, `--sandbox`, `--skip-git-repo-check`; the job-search workspace must be cwd or passed with `--add-dir` so `workspace-write` can persist run artifacts. **REAL non-zero exit codes** (infra/MCP/submission/git-apply failures doc-confirmed; model-level HALT exit not live-repro'd) | **None** (no `--codex`). Use `agent-data init --api-key <KEY> -y`; `whoami` confirmed `api_key_set:true` | **High** on distribution/tool-map/headless mechanics after `--cd`/`--add-dir`; **Medium** on App Automation behavior + model-halt exit code |
| **Cursor** (Claude-compatible, **not installed**) | `.cursor-plugin/plugin.json` beside `.claude-plugin/`; `skills:"./skills/"`. Mirror superpowers' real file but **omit** its dead `agents/`/`commands/` pointers | **Assumed yes** (Claude-compatible tool names; superpowers ships **no** cursor-tools remap → the signal it needs none). Gating + filesystem-sharing of parallel Task subagents **unverified** | **Assumed yes** (`AskUserQuestion`, Claude-compatible) — **unverified**; numbered-prose fallback already in voice.md | **NONE found.** No Cursor native local scheduler in any file read → relaxed-cron consent-gated fallback. Cloud rejected by the same workspace/auth bar | **UNKNOWN** — Cursor's headless command + exit-code semantics not found/probed. Keep record-based surfacing | **None** (no `--cursor`, live-verified). `--api-key`-only. **Avoid `--claude-code`** (installs a loose agent-data skill that may shadow the plugin one) | **Medium-low**. Distribution high; everything runtime is openQuestion |
| **opencode** (OpenCode.ai, **not installed**) | `package.json` `main:".opencode/plugins/job-search.js"` + `type:module`, **plus** that JS plugin (a `config` hook pushes `skills/` into `config.skills.paths`; an `experimental.chat.messages.transform` hook injects a bootstrap + **inline** tool-map). No `<platform>-tools.md` — the map is inline in JS | **Optional** — `@mention` subagent system (no core flag like Codex's; concurrency semantics unverified). Fallback: sequential | **None surfaced** → numbered-prose fallback | **UNKNOWN** — none documented; superpowers ships no scheduling for any platform → relaxed-cron fallback (cloud rejected by the workspace/auth bar) | `opencode run --print-logs --format json "<prompt>"`. **REAL non-zero exit codes** (test harness treats non-zero=fail, 124=timeout) — but that is opencode's *own* process exit, not proven for a skill-level HALT | **None** (no `--opencode`, live-verified). `--api-key`-only; skills ship via the plugin's `config.skills.paths` hook | **Medium**. Distribution/tool-map/headless-exit high (file-grounded); scheduler/notify/model-ids openQuestion |
| **Gemini CLI** (Google, **not installed**) | `gemini-extension.json` at repo root (`name/description/version/contextFileName:GEMINI.md`) + a `GEMINI.md` that `@`-imports the front-door SKILL.md AND a new `references/gemini-tools.md` | **Yes, native** — `@generalist` (built-in all-tools) / `@named` agent; parallel = request all in one prompt. No documented gating flag | **`ask_user`** ("request structured input") — likely the closed-choice analog, but labeled-options-vs-free-text fidelity **undocumented**; numbered-prose fallback otherwise | **NONE found** in the three Gemini sources read → relaxed-cron consent-gated launchd/cron fallback. Cloud rejected | **UNVERIFIED** — no print-mode command documented in sources read; exit-code semantics unknown | **None** (no `--gemini`, live-verified). `--api-key`-only then `whoami` | **Medium**. Distribution/tool-map/subagent/buckets/init high; headless/scheduler/notify/model-ids openQuestion |
| **GitHub Copilot CLI** (`copilot`; also `gh copilot`, **binary not on PATH**) | **Reuses the Claude manifest** — `.claude-plugin/marketplace.json` + `plugin.json` + the one `skills/` tree. **No `.copilot-plugin/`** (superpowers ships none) | **Yes** — `task` with `agent_type:"general-purpose"`/`"explore"`; status via `read_agent`/`list_agents`; parallel = multiple `task` calls. **No documented gate** (contrast Codex) | **None** — `EnterPlanMode`/`ExitPlanMode` are "no equivalent"; no structured-choice tool → numbered-prose fallback | **NONE.** GitHub Actions cron is **CLOUD** (runner can't see local workspace/auth) → rejected. `gh copilot` is a one-shot launcher, no schedule subcommand → relaxed-cron fallback is the FIRST place the relaxed rule fires | `copilot -p "<prompt>"` with `--allow-tool`/`--allow-all-tools` (the `gh copilot -p … --allow-tool 'shell(git)'` form is documented in `gh copilot --help`). Exit codes **LIKELY real but UNVERIFIED** (binary not installed) | **None** (no `--copilot`, live-verified). `--api-key`-only; plugin install ships the skills | **Medium**. Manifest/tool-map/init high (file+live); install-arg form + headless exit unverified |
| **Factory Droid** (`droid`, **not installed**) | `.factory-plugin/plugin.json` (Factory's own format; **only** `plugin.json` goes inside `.factory-plugin/`). **Or** rely on Droid's Claude-plugin compat reading `.claude-plugin/` (what superpowers actually does — ships no `.factory-plugin/`) | **Yes, native** — `Task` with `subagent_type`. **Enabled by default** (toggle off in `/settings` Experimental); no gate flag (contrast Codex) | **None documented** (no `AskUserQuestion` analog in the tool list) → numbered-prose fallback | **NONE native.** Docs delegate scheduling to external CI/CD (a GitHub Actions cron example = CLOUD) → rejected. Relaxed-cron consent-gated cron/launchd fallback | `droid exec` (`--auto low|medium|high` — default **read-only**, so a writing run needs ≥`--auto low`; `--output-format`). **REAL exit codes** ("0 success / non-zero failure incl. unmet objective; treat non-zero as failed in CI"; exceeding autonomy → non-zero, no partial changes) | **None** (no `--droid`/`--factory`, live-verified). `--api-key`-only | **Medium-high** on docs-grounded facts (manifest/tools/headless-exit/no-scheduler); openQuestions on marketplace `@name`, skill-invocation syntax, model IDs |
| **Pi** (earendil-works pi-coding-agent, superpowers origin/dev, **not installed**) | `package.json` `pi` block: `keywords:["pi-package"]`, `pi.skills:["./skills"]` (+ optional `pi.extensions`). **Repo has no `package.json` today** — Pi support ADDS one | **Not in core** — only via the optional `pi-subagents` package. **Install-gated**, not config-flag-gated (contrast Codex). Fallback: **sequential, never fabricate Task** | **None** documented → numbered-prose fallback | **NONE** documented (zero scheduler hits across all Pi files) → relaxed-cron consent-gated cron/launchd fallback. Cloud rejected | **UNVERIFIED** — no `pi exec`-style command in any file read; exit-code contract unknown. Keep record-based surfacing | **None** (no `--pi`, live-verified). `--api-key`-only; skills via `pi.skills` manifest | **Medium**. Distribution/tool-map/subagent-gating/init high (file+live); headless/scheduler/notify/model-ids openQuestion |

**Cross-platform invariant (all seven):** the agent-data CLI is harness-independent — every skill
shells out to it identically (it lives on PATH, unauthenticated-by-machine until `agent-data init`
sets the key). The only universal sandbox caveat: the binary + its network egress must be permitted
inside each host's sandbox/approval mode. See [agent-data-contract.md](../../shared/references/agent-data-contract.md).

**Distribution pattern shared by all seven:** ONE `skills/` tree, read in place by each host's native
plugin/skill manager, plus a thin hand-committed per-platform manifest — **no per-platform bundle
emission, no build codegen**. This *contradicts* the `build.sh`-emits-a-`dist/`-bundle framing in
[codex-portability.md](codex-portability.md) (L26-27, L119-121): the proven superpowers mechanism is
in-place reading via a manifest pointer, not codegen. The synthesizer should reconcile that doc to the
in-place pattern.

---

## 2. Complete coupling inventory (grouped by file)

The completeness backstop the prior single-harness doc lacked. Every coupling found, with line +
kind + severity. **Kinds:** `slash-recipe`, `loop-scheduling`, `headless-invocation`,
`closed-choice-question`, `subagent-dispatch`, `model-buckets`, `file-tools`, `desktop-notify`,
`agent-data-init`, `plugin-distribution`, `claude-naming-framing`.

> **THE FOUR HAND-AUTHORED PER-SKILL REFERENCES — the prior doc's blind spot.**
> [`scripts/build.sh`](../../scripts/build.sh) fans `shared/references/*.md` into each skill's
> `references/`, but the four files below live **inside a skill** and are **NOT synced** — they must
> each be neutralized **in place**, by hand: **`skills/job-search/references/onboarding.md`**,
> **`skills/job-search-agent/references/scheduling-and-consent.md`**,
> **`skills/job-search/references/home.md`**, **`skills/job-search-agent/references/customization.md`**.
> A neutralization pass that only touches `shared/references/` leaves these four stale, contradicting
> the neutralized copies. `onboarding.md` is the densest-coupled file in the whole repo.

### `shared/references/internals.md` — NOT harness-agnostic (most Claude-coupled reference)

| Line | Kind | Sev | Coupling |
|---|---|---|---|
| L3-6 intro | claude-naming-framing | high | "Claude Code performs these procedures itself, with the file tools" — names the executor |
| L4-5, L26-29 | file-tools | high | "Write the whole file back with the file tools — never shell redirection" — Claude-tool-shaped write rule governing every registry/config write |
| L84-85 | model-buckets | high | `haiku\|sonnet\|opus\|inherit` bucket set; `inherit` is a Claude subagent concept |
| L84-85 | subagent-dispatch | med | "per-posting detail subagents" assumes Task fan-out |
| L96-101 | loop-scheduling | high | `/loop` section + the OLD blanket "never initiate a crontab/launchd install" prohibition the relaxed rule lifts |
| L103-106 | loop-scheduling | high/med | `/loop <interval>` recipe + hour-unit quirk (`24h` not `1d`; parser may reject a day unit) |
| L106-109, L121 | slash-recipe / plugin-distribution | high/med | namespaced `/job-search:job-search-run` vs bare; `~/.claude/skills/`; "drop the prefix" |
| L114-119 | slash-recipe | high | verbatim user-facing recipe block (`/loop` + namespaced slash, shown to user) |
| L17, L40-44 | loop-scheduling | med | registry marker hard-codes `mechanism:"loop"` |

### `shared/references/conventions.md` — NOT harness-agnostic (config block only)

| Line | Kind | Sev | Coupling |
|---|---|---|---|
| 29 | model-buckets | high | detail-model enum `haiku\|sonnet\|opus\|inherit` |
| 29 | subagent-dispatch | med | "per-posting detail subagents" |
| 31 | loop-scheduling | high | frequency comment maps onto `/loop` interval ("24h for daily") |
| 32 | loop-scheduling | high | "`schedule.time` … informational under `/loop`" — **now WRONG** off-Claude: a cron/launchd fallback CAN honor wall-clock time |
| 36 | desktop-notify | med | the on-block notify config field assumes a desktop-notify host capability |
| 73 | file-tools | low | "Read … and fold in-context" carries the no-helper-script doctrine |

*Note: the rest of conventions.md (workspace layout, event-log contract, run records, digest format)
is harness-agnostic and ports cleanly. It also USES `cat >> … <<'EOF'` heredoc appends — shell
redirection is embraced for the append-one-line case, not forbidden; only structured-state whole-file
rewrites defer to the file-tools rule.*

### `shared/references/voice.md` — NOT harness-agnostic

| Line | Kind | Sev | Coupling |
|---|---|---|---|
| 30, 33, 43, 58 | closed-choice-question | high | names the `AskUserQuestion` tool + its constraints (≤12-char header, 2-4 options, auto free-text, no "other") |
| 44 | headless-invocation | med | assumes Claude "print mode"/headless where the question tool is unavailable |
| 8-9, 52 | loop-scheduling | med | "the loop"/"runner"/"headless pass" internal vocab |
| 68 | slash-recipe | high | "the `/loop` recipe and slash commands are shown verbatim" |
| 22-23 | claude-naming-framing | high | hard-codes "Claude Code terminal or claude.ai" as the markdown render targets |
| 1 | claude-naming-framing | low | "skill" framing |

### `shared/references/parallelism.md` — NOT harness-agnostic (conceptual only)

Wording is clean (names no Claude surface), but the **entire premise** is a subagent/Task fan-out
capability: isolated per-subagent context (L1, L3-7), batched parallel dispatch, a one-shot bounded
return (L12-32 briefing contract), and per-subagent model selection (L7). Treat as a single
`subagent-dispatch` capability dependency, severity **med**. On a host with no subagent primitive the
file's core premise has no execution path.

### `shared/references/errors.md` — NOT harness-agnostic (preamble only)

| Line | Kind | Sev | Coupling |
|---|---|---|---|
| L6 | headless-invocation | high | "a headless `claude -p` run returns 0 even when blocked" — Claude exit-code quirk baked in as the reason for the blocked-record design |
| L4 | desktop-notify | med | a desktop notification asserted as a guaranteed block-surfacing channel |
| L5 | claude-naming-framing | low | "the job-search skill" / "home view" surface names |
| L12 | agent-data-init | low | `npm install -g agent-data` bootstrap (note: NOT `init --claude-code` here — already the neutral path) |

*The E-\* catalog, agent-data commands, HTTP codes, and run-record concepts are portable. Exit codes
in the table (HALT, exit 1) are generic OS codes, NOT Claude-coupled.*

### `shared/references/agent-data-contract.md` — **harness-agnostic** ✓

Pure CLI API contract (route signatures, JSON envelope, retryable-boolean retry). No Claude mechanism.
The two flagged lines (CLI invocation via shell L3; retry/backoff L49-52) are generic shell/agent
assumptions that transfer unchanged. **No portability edits required.**

### `skills/job-search/references/onboarding.md` — HAND-AUTHORED, NOT SYNCED, densest-coupled

| Line | Kind | Sev | Coupling |
|---|---|---|---|
| 18, 125, 143-150, 204-212, 260-261 | closed-choice-question | high | ~6 `AskUserQuestion` invocations (Header + closed options) |
| 58 | agent-data-init | high | points at the Claude-only `agent-data.dev/setup/claude-code.md` |
| 72 | other | med | the `!`-bang in-prompt command (Claude TUI affordance) |
| 84 | closed-choice-question | med | "free-text secret … so don't use the question tool" — distinction exists only because of AskUserQuestion |
| 88-91 | agent-data-init | high | `agent-data init --claude-code --api-key <KEY> --yes` + "installs the Claude Code discovery skill" |
| 95-96 | other | high | explicit Claude version gate (`<2.1.0` needs restart; `2.1.0`+ hot-loads) |
| 153, 160, 225 | subagent-dispatch | med | skill invocation with args |
| 236 | headless-invocation | med | "exits non-zero" assumption to detect blocked runs |
| 251-296 | loop-scheduling / slash-recipe / plugin-distribution | high | the entire `/loop` scheduling §7 + namespaced recipe + `~/.claude/skills/` + records `mechanism:loop` |

### `skills/job-search/references/home.md` — HAND-AUTHORED, NOT SYNCED

| Line | Kind | Sev | Coupling |
|---|---|---|---|
| 34, 52-54 | loop-scheduling | high | rendered status line literally shows "daily via /loop" |
| 16 | loop-scheduling | med | schedule marker enum hard-codes `mechanism:"loop"` |
| 76-77 | model-buckets | high | detail-model bucket enum |
| 78-80 | loop-scheduling | med | frequency enum maps onto the `/loop` interval table |
| 86-89 | loop-scheduling | high | composes/runs a verbatim `/loop …` line; teardown via session lifecycle ("end the session… cancel the pending wakeup") |
| 68-69, 81-82 | subagent-dispatch | med | "invoke job-search-run / job-preference-interview" by name |
| 83-84, 90-92 | claude-naming-framing | low | markdown-rendered-chat output assumptions |

### `skills/job-search-agent/references/scheduling-and-consent.md` — HAND-AUTHORED, NOT SYNCED

Structurally built around `/loop` as "the only one the agent sets up" — nearly every line couples.
L3, L6, L8-13 (`/loop`, cloud `/schedule` rejected for no-local-workspace/auth), L17 (hour-unit
interval table), L8-9/L17 (namespaced vs loose), L18/L22-24 (`schedule.time` informational under
`/loop`), **L28-32 (the blanket "never initiate a crontab or launchd install yourself" — the exact
prohibition the relaxed rule lifts at Tier 2)**. Severity **high** throughout. The cloud-rejection
*rationale* (no local workspace/auth) is harness-agnostic and is the test any candidate scheduler
must pass — preserve it.

### `skills/job-search-agent/references/customization.md` — HAND-AUTHORED, NOT SYNCED

| Line | Kind | Sev | Coupling |
|---|---|---|---|
| 72 | subagent-dispatch | high | per-posting parallel detail-read subagents |
| 74-81 | model-buckets | high | the `haiku\|sonnet\|opus\|inherit` table + prose naming Anthropic model families as the tuning vocabulary |
| 9/34/45/72 | other | low | named-skill references |

### `skills/job-search/SKILL.md` — thin router, mostly agnostic

Delegates mechanism to references. Literal couplings: L3 `/job-search` slash token (slash-recipe,
med); L3/L19 "headless pull" naming the Claude headless mode (low). Greeting/output-ordering contract
is an interaction-model assumption.

### `skills/job-search-run/SKILL.md` — NOT harness-agnostic

| Line | Kind | Sev | Coupling |
|---|---|---|---|
| frontmatter | plugin-distribution | high | `disable-model-invocation`/`user-invocable` = Claude skill-manifest schema |
| L14-15, L71-77, L84-87, L107-116 | subagent-dispatch | high | the whole fan-out architecture (parallel subagents in one batch, briefing, "hand each the evaluate-job-fit skill to follow") |
| L72-73, L87 | model-buckets | high | `search.detail_model`, default `haiku`; `inherit` = the run's model |
| L137 | desktop-notify | med | fire one desktop notification on a blocked run (config-gated) |
| L138-142 | headless-invocation | high | names `claude -p` + the exit-0-on-block quirk |
| L3, L10-11, L19, L144-146 | slash-recipe | low | skill-name routing |

### `skills/job-search-agent/SKILL.md` — NOT harness-agnostic

Dominant couplings: L29/L44/L75-81/L100 (`/loop` + open-session + crontab/launchd prohibition +
namespaced target), L89 (`claude -p` exit-0 quirk + desktop-notify), L69 (subagent fan-out), L4-5
(skill frontmatter fields). Per the relaxed rule, L77-81's "never install crontab/launchd" is stale.

### `skills/job-preference-interview/SKILL.md` — NOT harness-agnostic

Highest-value: L64/L72-73/L106-109 `AskUserQuestion` usages (Header, 2-4 cap, auto free-text) and
**L164-165 "Claude reads this brief next to a job posting"** — a literal "Claude" string written into
the user-facing `preferences.md` footer (must become the agent/assistant generically). L29-30
headless distinction; L33/L36 file-write delegated to internals.md; frontmatter fields. Much is
delegated to voice.md/internals.md — inventory those separately.

### `skills/evaluate-job-fit/SKILL.md` — **harness-agnostic** ✓ (essentially)

No direct Claude-mechanism references. Weak couplings only: cross-skill references by bare name
(L3/L9-10/L15), `references/internals.md` Discovery-procedure delegation (inherits whatever internals
carries), and frontmatter `disable-model-invocation`/`user-invocable` (skill-manifest schema). Porting
needs no prose rewrite here, only verifying the delegated references port.

### `AGENTS.md` / `ARCHITECTURE.md` — NOT harness-agnostic (framing)

`AGENTS.md` L3 "Claude Code as a … operating system" + L3-4 "a plugin with five skills … Claude Code
executes natively"; L27 `build.sh`/`skills/*/references` (claude-naming-framing + plugin-distribution,
high). Note L6 already uses neutral "coding agents" — the template to follow. `ARCHITECTURE.md` names
Claude Code as the kernel (L3, L23), pins scheduling to `/loop` + never-install-cron (L28, L61-66 —
**relaxed-rule conflict**), and defines distribution solely as the `.claude-plugin` plugin + loose
skills (L125-127). Desktop-notify (L71) and headless-run framing (L129-131) are implicit couplings.

### `docs/design-docs/core-beliefs.md` — NOT harness-agnostic (design doc)

Belief 4 (L79, L84): a desktop notification asserted as a guaranteed error channel + "headless
`claude -p` exits 0 even when blocked" (3× across the doc). Belief 6 (L109-116): "Claude Code
executes natively" + the exit-code rationale. **Belief 7 (L128-142): scheduling = `/loop`; "the
agent never initiates a write"; eval "the harness forbids crontab/launchctl writes" — directly
CONTRADICTS the relaxed Tier-2 fallback.** Belief 12 (L208-217): subagent fan-out + `search.detail_model`
knob (model-buckets). Verify-steps name "Claude" directly (low).

### `docs/SECURITY.md` — NOT harness-agnostic

Dominant: the entire "## Scheduling never writes your machine" section (L43-55) — `/loop` as THE
scheduler, namespaced-vs-loose slash split, the PreToolUse hook reference, "open Claude session", and
the flat "the agent never initiates a cron line or a launchd plist" assertion that **now contradicts
the relaxed rule**. Lower: `skills/<name>/SKILL.md` path convention, "skill evals". The **auth
section (L59-64) is clean** — env-var/CLI-config path, not `--claude-code`.

### `CLAUDE.md` — NOT harness-agnostic (by filename convention only)

5-line shim; body addresses generic "coding agents" and redirects to the agnostic `AGENTS.md`. The
ONLY coupling is the filename/auto-load convention (Claude Code auto-loads `CLAUDE.md`). Keep it as a
Claude-only redirect; give each other harness its own equivalently-named entry file pointing at
`AGENTS.md`.

---

## 3. Neutralization pattern per kind

The recommended shape is the same the Codex study prescribes: **speak in ACTIONS inline; defer the
harness-specific literal to the active platform's adapter** at `shared/references/platform/<active>.md`
(to be created — selected at build/install time so a skill reads exactly one adapter and never
branches on harness). Each pattern below was independently verified; the verifier's caveats are folded
into §6.

### `slash-recipe`
**Approach:** prose names the action ("show the recurring-run recipe and the one-off-run recipe for
this install, verbatim from the platform adapter's Run recipe block") and never spells the tokens. The
adapter owns the exact one-off string, the recurring/schedule-start string with its `<interval>`/cron
slot, any namespacing rule (the `job-search:` prefix is a Claude-only concern), and the in-block
"installs nothing?" caveat. The recurring recipe IS the loop-scheduling schedule-start line, so the
two kinds share one adapter section.
**Before** (internals.md): a fenced block hard-coding `/loop <interval> /job-search:job-search-run` +
the bare one-off + "(drop the `job-search:` prefix)".
**After:** "ALWAYS show the user the **recurring-run recipe** and the **one-off-run recipe** verbatim
— copy them exactly as written in the active platform's adapter (`platform/<name>.md` → Run recipe)…
do not reconstruct those tokens here."
**Style rules honored:** D6 (bare arrowed cross-ref), E7 (anti-guessing fence — name the source,
forbid reconstruction), E3/E2 (verbatim shown commands), D2 (literal template lives in the adapter),
C10/H5 (delegate depth to the plugin's own references), A2/A3 (rule fused with reason; prohibition
paired with replacement).

### `loop-scheduling`
**Approach (THE policy change):** speak scheduling in actions ("schedule the recurring run on the
cadence the user picks; offer it as a yes/no; record it; offer a clean turn-off") and defer mechanism
to the adapter. The adapter encodes a **two-tier RELAXED stance**: **Tier 1** — a native LOCAL
consent-based scheduler exists (Claude `/loop`; Codex Automations): use it, installs nothing. **Tier 2**
— NO native local scheduler: a consent-gated machine-level cron/launchd schedule is the **sanctioned
fallback** (explicit yes, exact line shown before writing, never silent, never auto-installed,
user-removable). The blanket "never install crontab/launchd" prohibition is lifted **only at Tier 2**.
A cloud scheduler that can't see `~/.job-search` or the local agent-data auth does **not** qualify as
Tier 1 (per [scheduling-and-consent.md](../../skills/job-search-agent/references/scheduling-and-consent.md),
which rejects cloud `/schedule` for exactly that reason). Belief #7 keeps its INTENT (consent-gated;
no SILENT/auto privileged write) while the mechanism generalizes.
**Before** (scheduling-and-consent.md): "## Mechanism: native `/loop` (the only one the agent sets
up)… **never initiate a crontab or launchd install yourself**."
**After:** "## Mechanism: the host's scheduler — read the active adapter… Native local scheduler
(preferred)… Consent-gated machine schedule (sanctioned fallback) — only on an explicit user yes, with
the exact line shown before it is written, never silent, never auto-installed… A cloud scheduler that
can't see the local workspace or auth does not qualify and is skipped."
**Style rules honored:** A1 (imperative), A3 (prohibition→replacement), A6/A7 (mechanism explained as a
tunable gated trade-off), B1 (IMPORTANT/NEVER reserved for the real hard gate), C8 (named-default
fallback), C6/D6 (situation→action in the adapter; arrowed cross-ref).

### `headless-invocation`
**Approach:** the action is invariant inline ("run job-search-run headless — a non-interactive,
never-prompt pass that ends by writing a run record"). Replace the universal-sounding "a headless
`claude -p` returns 0 even when blocked; never trust `$?`" with a mechanism-first rule true on **every**
harness — "surface every outcome through the written record (the blocked run record + blocked digest +
home view), because the record is the contract the home view reads. Whether the exit code can ALSO be
trusted is per-harness — see `platform/<active>.md` → Headless invocation." Adapter pins two fields:
`launch command` and `exit code trustworthy (yes/no + consequence)`. Claude: `claude -p`, NO. Codex:
`codex exec`, YES. opencode/Droid: real exit codes, YES. Cursor/Gemini/Pi/Copilot: UNKNOWN → keep
record-based surfacing primary.
**Style rules honored:** A1/A2/A3, A6 (explain "a skill cannot set the host exit code" so it
generalizes), B2 (state the exit-0 fact as Claude-specific, not universal), C8 (record is the named
default; exit-code is the per-harness add-on), D6/E7.
**Verifier flag (see §6):** as written this rewrite has real build + eval prerequisites — `build.sh`
must sync the new `platform/` subdir, and the five `evals.json` exit-code expectations must branch on
the platform under test, not flat-swap.

### `closed-choice-question`
**Approach:** replace every "the question tool"/"AskUserQuestion" with the action ("ask `<X>` as a
closed choice") and move the mechanism description (rendering, header/option-count bounds, prose
fallback) into the adapter → "Closed-choice question". voice.md keeps the harness-agnostic DECISION
(closed-choice vs prose; what's user-facing) and the invariant that no tool name appears in user text.
Skill playbooks keep authoring the WORDS (header/question/labels) and swap the verb. The adapter
decides structured-picker vs numbered-prose per host, so a no-UI host degrades by reading its own
adapter.
**Style rules honored:** A1, C8 (failure path with named default), C10/H5 (delegate; plugin points at
its own references), D6, E1 (bounds quantified at point of use in the adapter), E2/E7 (keep the literal
mechanism name in ONE authoritative place; forbid reconstruction).

### `subagent-dispatch`
**Approach:** the action is fixed and platform-free ("for each promising posting, read its full
description and judge it INDEPENDENTLY, so full JDs stay out of the orchestrating context and the reads
run concurrently when the host can"). Defer the fan-out verb, whether an isolated-context concurrent
primitive exists, any concurrency cap, how it's enabled, and the **mandatory sequential fallback** to
the adapter → "Concurrent detail reads". parallelism.md stays the canonical pattern statement but stops
asserting the fork capability as universal. **Keep the "single batch, never a one-at-a-time loop"
performance imperative inline** for the always-available case (verifier flagged that the draft "after"
weakened it — "never block one read on another" permits a serial loop; restore the eager-batch nudge).
**Style rules honored:** A2, A6 (explain mutual-independence → concurrent-where-allowed), C8/C10
(named fallback + delegate verb), D6, E1, H5.

### `model-buckets`
**Approach:** the config value and prose carry portable TIER TOKENS (`fast | balanced | high | inherit`),
never Anthropic model names; one adapter table → "Model tiers" maps each token to the host's real model
id (Claude: `fast→haiku`, `balanced→sonnet`, `high→opus`; Codex: `fast→gpt-5`-class, `high→gpt-5-codex`/
o-series). `inherit` stays portable ("the model this run is on"); the adapter notes whether per-subagent
model selection even exists (Codex gates fan-out behind `multi_agent`; a single-model host makes the
knob inert).
**Style rules honored:** D5 (define the tier vocabulary at point of use), D6 (table + arrowed ref),
E7 (concrete model id named only in the adapter), C6/C10, A7 (keep the fidelity/speed-tradeoff framing).
**Verifier flag (see §6):** this is a **breaking config-value migration** (live `config.yaml` carries
`haiku`); the adapter must accept legacy `haiku|sonnet|opus` as tier aliases or onboarding must
rewrite them, and the 3-tier abstraction is **lossy on Codex** (fast-vs-capable only). The cited
"philosophy_guard scans detail_model" rationale is **wrong** — that guard only forbids cost/credit
fields and numeric scores.

### `file-tools`
**Approach:** state the action ("read the current file, apply the change to the parsed object, then
write the whole file back atomically — a full replace in place, never a streamed/redirected partial
that can truncate or interleave") and defer the primitive to the adapter → "Whole-file write". Claude:
the Write tool. Codex: `apply_patch`, or write-to-temp-then-`mv`. **Preserve the existing distinction:**
appending one immutable line to the event log stays a legitimate shell `>>` heredoc on every harness;
only structured-state whole-file rewrites defer to the adapter.
**Style rules honored:** A1, A3 (replaces the bare-tool ban with the atomic-replace invariant + its
consequence), A6 (explain the invariant so it generalizes), C10/D6, E7, H7 (`<active>` resolved by the
build, not a runtime placeholder).

### `desktop-notify`
**Approach:** DEMOTE the alert from a guaranteed third leg to a capability-gated channel. State the
durable guarantee in **two** channels only (the blocked digest + the home-view run record — both plain
file writes that survive on any host). Re-frame the alert as conditional twice: gated by the user's
on-block notify knob AND by whether the host has an attention-pull channel at all; when it has none,
skip it silently — the two file-backed channels still carry the failure. Keep the config knob
(harness-neutral intent); its FULFILLMENT moves to the adapter → "Block-alert channel" (Claude:
terminal/phone notification; Codex: App Triage / CLI none; bare cron: none). **This is honest, not a
weakening** — the notification was already conditional in the live code; the inaccurate text was
errors.md's "three guaranteed ways".
**Style rules honored:** C8 (named-default fallback), B3 (cost-benefit; the alert is the only
attention-PULLING channel, so opt-in + capability-gated), A3 (skip-the-alert paired with "the two file
channels still surface the failure"), A2/D7, D6, C10, E2.

### `agent-data-init`
**Approach:** speak the action ("authenticate the agent-data CLI and install its discovery skill for
the active harness") and defer the one harness-named token — the `init` flag — to the adapter →
"agent-data setup". **Ground truth (live `agent-data init --help`):** `init` owns a FIXED enum of
mutually-exclusive selectors — `--claude-code | --open-claw | --hermes | --nano-claw` — plus
harness-neutral `--api-key <key>` and `-y/--yes` (and `--nano-claw-path`). The flag is the only coupled
slot; the key, config path, `whoami` probe, and `npm install -g agent-data` floor are already neutral
and stay. The adapter supplies `agent_data_init_flag`, the discovery-skill artifact name, the
per-harness setup-doc URL, and the post-install load/restart note.
**Style rules honored:** E7/E3 (verified against the live CLI; name the authoritative source), A1, H7
(named adapter field, not `${VAR}`), C10/D6, D3.
**Verifier flag (see §6):** the no-flag `--api-key`-only path is the workaround for **all six**
non-Claude harnesses (none has its own selector); the `--nano-claw` selector additionally requires
`--nano-claw-path`, which a flat init template has no slot for.

### `plugin-distribution`
**Approach:** speak the action ("package and install this agent so its skills load together and resolve
each other") and defer manifest format / install command / launch flag / namespacing / install location
to the adapter → "Packaging & install". Distinguish **dev-side** packaging/CI (`.claude-plugin/`,
`marketplace.json`, `build.sh` emit paths — allowed to stay Claude-named in dev-only docs per H5) from
**runtime** prose a skill reads (the namespaced-vs-loose invocation distinction, "this plugin", loose
`~/.claude/skills/`) which becomes an adapter pointer. The recurring "plugin skills are only invocable
namespaced" sentence collapses to a single `<run-invocation>` adapter slot read by the slash-recipe,
loop-scheduling, AND subagent-dispatch kinds.
**Style rules honored:** A1, A2, C10/H5 (the adapter lives under `shared/references/` which build.sh
bundles, never an external `docs/` path), D6, E7.

### `claude-naming-framing`
**Approach:** name the HOST generically ("the host agent"/"the agent") with the concrete name pinned in
the adapter's Identity line; generalize "Claude Code as a job-search OS" → "an agent harness as a
job-search OS"; rendering surface "Claude Code terminal or claude.ai" → "wherever the user is reading"
with markdown capability deferred to the adapter; CLAUDE.md stays a Claude-only redirect to the agnostic
AGENTS.md (acknowledged in the Claude adapter, not scrubbed).
**Style rules honored:** A2, A3 (the lifted cron prohibition gets its replacement), A6, B1, C8, D6, H5.

---

## 4. The SCHEDULING MATRIX (relaxed-cron rule applied per platform)

The **relaxed rule:** schedule with a host's NATIVE LOCAL consent-based scheduler where one exists
(installs nothing). Where NONE exists, a **consent-gated machine-level cron/launchd schedule is the
sanctioned fallback** — explicit user consent, the exact line shown to the user, never silent, never
auto-installed. A **CLOUD** scheduler that cannot see the local `~/.job-search` workspace or the local
agent-data auth does **NOT** count (the repo rejects cloud `/schedule` for exactly that reason —
[scheduling-and-consent.md](../../skills/job-search-agent/references/scheduling-and-consent.md) L12-13).

| Platform | Tier | Native local scheduler? | Recommended mechanism | Registry `scheduling.mechanism` | Evidence (local vs cloud determination) |
|---|---|---|---|---|---|
| **Claude Code** (baseline) | **Tier 1** | `/loop` — in-session, installs nothing | `/loop <interval> /job-search:job-search-run`; `schedule.time` informational (interval-only) | `loop` | Existing design; `/loop` is session-bound local |
| **Codex** | **Tier 1 (App) / Tier 2 (pure CLI)** | **YES — Automations** (App/daemon; runs in the on-disk project dir or a local worktree → sees workspace + auth). Pure CLI: **no automation subcommand** | App: a standalone/thread Automation (cron cadence) in LOCAL project mode → `$job-search:job-search-run`. Pure CLI: consent-gated `crontab`/`launchd` wrapping `codex exec --sandbox workspace-write '$job-search:job-search-run'` | `codex-automation` (App) / `cron`/`launchd` (CLI) | **EVIDENCE-BACKED, not asserted.** Manual: "the machine running the local Codex app must be powered on, Codex must be running, and the selected project must still be available on disk"; automations "run directly in the project directory". `codex --help` has no automation subcommand; `codex cloud` is the only scheduler-adjacent CLI and is CLOUD → rejected |
| **Cursor** | **Tier 2 (likely)** | **NONE found** in any file read | Consent-gated `cron`/`launchd` wrapping Cursor's headless invocation (command UNKNOWN — pin first) | `cron`/`launchd` | No Cursor scheduler in superpowers or sibling docs; `/loop` analog existence is an openQuestion. Cloud rejected by the workspace/auth bar |
| **opencode** | **Tier 2 (likely)** | **UNKNOWN** — none documented; superpowers ships no scheduling for any platform | Consent-gated `cron`/`launchd` wrapping `opencode run …`. opencode returns real exit codes, so a wrapper can act on `$?` | `cron`/`launchd` | Correctly left **UNKNOWN** (not asserted). Cloud disqualifier grounded in scheduling-and-consent.md |
| **Gemini CLI** | **Tier 2 (likely)** | **NONE found** in the three Gemini sources read | Consent-gated `launchd` (macOS) / `cron` wrapping the headless run (command UNVERIFIED) | `cron`/`launchd` | `grep` for schedule/cron/automation across gemini-tools.md = no match; the tool table schedules nothing. Cloud rejected. Recommendation contingent on confirming no native scheduler |
| **Copilot CLI** | **Tier 2** | **NONE.** `gh copilot` is a one-shot launcher; **GitHub Actions cron is CLOUD** | Consent-gated `cron`/`launchd` wrapping `copilot -p "/job-search:job-search-run"` | `cron`/`launchd` | **The FIRST place the relaxed rule actually fires** (unlike Claude `/loop` and Codex Automations, Copilot offers neither). `gh copilot --help` shows no schedule subcommand; copilot-tools.md lists no scheduler tool; Actions runner can't see the local workspace/auth |
| **Factory Droid** | **Tier 2** | **NONE native** — docs delegate scheduling to external CI/CD (a GitHub Actions cron example = CLOUD) | Consent-gated `cron`/`launchd` running `droid exec --auto low -o text "<run the pass>"`. Droid returns real exit codes | `cron`/`launchd` | **EVIDENCE-BACKED.** droid-exec doc: scheduling "delegated to external CI/CD systems"; only cron is a GitHub Actions example. Repo's cloud-rejection rationale applies identically |
| **Pi** | **Tier 2 (likely)** | **NONE** documented (zero scheduler hits across all Pi files); Pi not installed to probe | Consent-gated `cron`/`launchd` wrapping the Pi headless command (UNVERIFIED — pin first) | `cron`/`launchd` | Correctly left a strong working assumption, **not asserted absolute**. Cloud disqualifier grounded in scheduling-and-consent.md |

**Matrix-wide consequences for the relaxed rule:**
- **core-beliefs.md belief #7 and its eval** ("the harness forbids crontab/launchctl writes",
  L139-142) must be re-scoped to "asserts no SILENT/un-consented write; a shown, user-approved Tier-2
  line is allowed" — otherwise green evals enforce the stale prohibition the relaxed rule lifts.
- **docs/SECURITY.md L43-55** ("Scheduling never writes your machine" / "the agent never initiates a
  cron line or a launchd plist") must become conditional on the active mechanism, or it lies on every
  Tier-2 host.
- **conventions.md L32** ("`schedule.time` informational under `/loop`") is wrong on a wall-clock
  cron/launchd fallback (where `schedule.time` IS honored) — must defer to the adapter.
- The **"installs nothing on your machine"** property is TRUE for Tier 1 (`/loop`, Automations) and
  FALSE for the Tier-2 cron/launchd fallback; any copy asserting it must become conditional.
- The Tier-2 consent gate must travel **inside** the adapter's recurring-recipe block (show-before-run
  + explicit-yes), so an action-biased model can't read it as "just run it" the way the current
  `/loop` flow's "on yes, run that command" reads.

---

## 5. The `agent-data init` gap + workaround + upstream ask

**The gap (live-verified against `~/.local/bin/agent-data`, `agent-data init --help`):** `init`
exposes a **fixed enum** of harness selectors —
`--claude-code | --open-claw | --hermes | --nano-claw` — plus the harness-neutral `--api-key <key>`,
`-y/--yes`, and `--nano-claw-path <path>`. There is **NO `--codex`, `--cursor`, `--opencode`,
`--gemini`, `--copilot`, `--droid`, or `--pi` flag.** Confirmed independently by all seven studies.

**Why it doesn't matter for job-search:** the harness flag only controls **where agent-data copies its
OWN discovery skill** (into that harness's skill dir). job-search does not need that copy — it ships
its own agent-data usage through the plugin, and the agent-data **capability** reaches every harness
through the CLI on PATH. The flag is cosmetic to job-search's runtime.

**The workaround (the sanctioned path on all six non-Claude harnesses):**
```
agent-data init --api-key <KEY> -y
```
Sets up the API key + global CLI install **without** installing a harness-specific skill wrapper.
**Live-verified functional:** `agent-data whoami` returns `api_key_set:true`, `api_key_source:config`,
a working `base_url`, and `agent_type:null` — i.e. the key-only path yields a fully authenticated CLI;
`agent_type` is cosmetic skill-install metadata, **not** an auth/runtime gate. The plugin install (per
harness) is what places the job-search skills; `init` only needs to authenticate.

**Caveats:**
- `--quiet` to suppress nags is **not** in `init --help` (Codex study flagged it; low impact — the
  core `--api-key -y` path is verified).
- The **`--nano-claw` selector additionally requires `--nano-claw-path`** — a flat init template that
  only fills the flag slot would break for that selector (not job-search's path, but noted for the
  adapter's init field).
- On a host that genuinely has no agent-data selector and no plugin path, the adapter routes to the
  **fully flag-free auth path** already in errors.md / SECURITY.md (`export AGENT_DATA_API_KEY=…` or
  hand-write the CLI config), with no discovery skill installed.
- **Cursor-specific hazard:** do **not** substitute `--claude-code` on Cursor — it drops a loose
  agent-data skill into `~/.claude/skills/` that may shadow or duplicate the plugin one.

**Upstream ask (non-blocking, recommended):** file a request with the agent-data CLI maintainers for
either per-harness selectors (`--codex`/`--cursor`/`--opencode`/`--gemini`/`--copilot`/`--droid`/`--pi`)
or, better, a **generic `--skills-dir <path>` / `--none`** flag, so the discovery skill can land in any
runtime's skill directory and the workaround becomes first-class. Until then, `--api-key`-only is the
documented route.

**Repo-edit flag:** onboarding.md L88 and `skills/job-search/evals/evals.json` **hard-code**
`agent-data init --claude-code --api-key <KEY> --yes`. For any non-Claude target that string must drop
`--claude-code` to the `--api-key`-only form (defer the flag to the adapter's `agent_data_init_flag`
field; do not flat-edit).

---

## 6. Open risks & UNVERIFIED claims

Every `unverified`/`wrong` verdict pulled forward from the underlying studies, so the synthesizer
inherits the doubt. **The scheduling local-vs-cloud determination is called out per platform first —
it is the single most important check, and in every case the verifier confirmed it is EVIDENCE-BACKED
(grounded in a file/command read), NOT asserted.**

### 6a. Scheduling local-vs-cloud determination (per platform)
- **Codex — VERIFIED, evidence-backed.** Automations are LOCAL by direct manual text ("the machine
  running the local Codex app must be powered on… the selected project must still be available on
  disk"; "automations run directly in the project directory"). The pure-CLI caveat (no automation
  subcommand; `codex cloud` is the only scheduler-adjacent CLI and is cloud) is verified against
  `codex --help` / `codex cloud --help`.
- **Copilot — VERIFIED, evidence-backed.** `gh copilot --help` = one-shot launcher, no schedule
  subcommand; copilot-tools.md lists no scheduler tool; GitHub Actions cron is cloud. The only soft
  spot: "Actions cron runs on a remote runner" is general platform knowledge, but the load-bearing
  disqualifier (no local workspace/auth) is grounded in scheduling-and-consent.md.
- **Droid — VERIFIED, evidence-backed.** droid-exec doc explicitly delegates scheduling to external
  CI/CD with only a GitHub Actions cron example; repo cloud-rejection rationale applies.
- **Gemini — VERIFIED-as-source-scoped.** `grep` across the three Gemini sources read returns no
  scheduler; the doc honestly says "None found"/"N/A", not "Gemini has no scheduler as absolute fact".
- **Cursor / opencode / Pi — correctly left UNKNOWN, not asserted.** No native scheduler surfaced in
  files read; none installed to probe. Each grounds only the cloud disqualifier (which IS in a real
  file), and makes the cron-fallback recommendation contingent on a live check.

### 6b. WRONG claims caught by verifiers (correct before relying on)
- **opencode:** the study said the repo's `package.json` "exists; would gain main+type" — **FALSE**,
  there is no `package.json` at the repo root today; it must be CREATED.
- **Gemini:** the study said "the AGENTS.md→CLAUDE.md symlink in job-search" — **FALSE** for job-search
  (AGENTS.md is a regular 2163-byte file; the symlink exists only in superpowers). The conclusion
  (contextFileName isolates Gemini to GEMINI.md, so AGENTS.md is irrelevant) still holds.
- **Cursor:** the study claimed job-search's `marketplace.json` has "the same shape" as superpowers' —
  **WRONG**; per-plugin fields differ (superpowers carries version+author, no category; job-search
  carries category, no version/author). The high-level "both ship a marketplace.json an install
  resolves against" holds.
- **Factory Droid:** the study attributed "plugin.json … (not Claude Code's format)" to Factory's docs
  — **WRONG**; the doc says the OPPOSITE ("compatible with plugins built for Claude Code… the format
  is interoperable"). The path/fields/warning are correct; only the quoted gloss is wrong. Also a
  minor `--output-format` value (`stream-json` vs `stream-jsonrpc`) was over-listed.
- **model-buckets neutralization:** the pattern's rationale claimed `philosophy_guard.py` scans
  `detail_model`/model literals — **WRONG**; that guard only forbids cost/credit config fields and
  numeric scores. (Verified this session: the guard's `DUP`/score logic does not touch model names.)

### 6c. UNVERIFIED runtime claims (no live install) — pin empirically before shipping copy
- **Codex:** `multi_agent` default is **version-dependent** (on in 0.140.0, opt-in in older builds —
  detect/instruct conditionally); `enable_fanout` is under-development (the CSV batch-fanout path may
  need it; the basic spawn/wait/close trio doesn't); `codex exec` non-zero on a **model-level HALT**
  (vs infra/MCP/submission/git-apply) **not live-repro'd**; the literal `spawn_agent`/`wait_agent`/
  `close_agent` token names come from superpowers' codex-tools.md, not the Codex manual (manual uses
  prose); no-structured-choice-tool is an inventory **inference**, not an explicit manual statement;
  Automations behavior on a headless/server box (no App) untested; agent-data egress allowlist under
  `--sandbox workspace-write` not constructed/tested; third-party marketplace publishing policy is a
  vendor question.
- **Cursor:** EVERY runtime claim is inferred (Cursor not installed) — Claude-compatible tool names
  (from "no cursor-tools remap"), Task availability + gating, parallel-subagent filesystem sharing,
  `AskUserQuestion` support, native scheduler existence, headless command + exit-code semantics
  (real-non-zero vs always-0), notification surface, concrete model ids, sandbox agent-data egress,
  whether Cursor reads `.claude-plugin/marketplace.json` verbatim, whether it reads `~/.claude/skills/`.
  Also unconfirmed this session: that job-search has no `agents/`/`commands/` dir.
- **opencode:** subagent concurrency + any enabling flag for `@mention`; native scheduler
  existence/locality; exact native file/edit/web-fetch tool names; notification channel; literal
  model ids; whether a skill-level HALT sets opencode's exit code; whether agent-data is on PATH inside
  `opencode run`. Doc note: README.opencode.md says the bootstrap injects via
  `experimental.chat.system.transform`, but the JS uses `experimental.chat.messages.transform` — the
  JS is ground truth. The "native skill tool emits `"tool":"skill"`" / "real exit codes" facts are the
  shipped integration test's **assertions** (the test SKIPs when opencode is absent), not observed
  here.
- **Gemini:** headless/print-mode command spelling; headless exit-code semantics; `ask_user`
  closed-choice fidelity (labeled options vs free-text); whether any native scheduler ships at all;
  `@generalist` gating; notification surface; current Flash/Pro-class model ids; whether the GEMINI.md
  `@`-import auto-attaches at session start (syntax confirmed in-file, runtime unobserved); whether
  `gemini extensions install <url>` ingests the one `skills/` tree as-is.
- **Copilot:** exact `copilot plugin marketplace add` / `install` argument forms (the superpowers
  precedent uses a marketplace-repo slug `obra/superpowers-marketplace`, not the plugin's own repo, so
  the analogy doesn't pin job-search's arg); `copilot -p` exit-code semantics; the `--allow-all-tools`
  flag name (not in gh's terse help); whether `task` carries any runtime gate; Copilot model-selector
  ids; whether Copilot honors the COPILOT_CLI session-start hook contract (superpowers does, v1.0.11+).
- **Factory Droid:** exact `plugin@marketplace` name resolution after `droid plugin marketplace add`
  (superpowers uses `superpowers@superpowers` while its marketplace.json is `superpowers-dev`);
  whether Droid has any AskUserQuestion analog; Droid's on-demand skill-invocation syntax (callable
  tool vs namespaced slash vs pure auto-invocation) — the **highest-risk rewrite**, gates the verbatim
  recipe strings; whether `droid exec` maps a skill-level HALT to non-zero; which `--auto` level the
  scheduled pass needs (likely `low`); Droid's exact current Anthropic model ids (catalog may lag);
  whether `.factory-plugin/` coexists with `.claude-plugin/` or is unnecessary via compat.
- **Pi:** headless command + exit-code contract; native scheduler existence (strongly evidenced absent
  by a zero-hit grep, but unprobed); notification channel; web-fetch tool name; literal model ids;
  whether a HALT sets Pi's exit code; whether agent-data is on PATH inside `pi run`. The install-line
  repo slug (`agent-data/job-search`) is from MEMORY, not a Pi file. The "native skill tool / real
  exit codes / headless command" facts are the shipped integration test's **assertions** (test SKIPs
  when Pi is absent), not observed here.

### 6d. Cross-cutting build/eval prerequisites (block the whole neutralization)
- **`build.sh` is a flat glob** (`cp shared/references/*.md …`) — it does **NOT** recurse into a new
  `shared/references/platform/` subdir and does **NO** `<active>` template resolution. Every adapter
  cross-reference dangles until build.sh is taught to (a) copy the selected adapter into each skill's
  `references/` and (b) resolve `<active>` to a concrete filename. This is a hard prerequisite, not a
  "safer alternative".
- **`shared/references/platform/` does not exist yet** — every "see `platform/<active>.md` → …"
  pointer references a missing file until the adapters land in the same change as the prose.
- **The five `evals.json` exit-code expectations** assert "a headless run exits 0" and must branch on
  the platform under test (Claude=0, Codex/opencode/Droid=non-zero-on-HALT), not flat-swap — a flat
  rewrite silently changes Claude's contract.
- **`model-buckets` is a breaking config-value migration** — accept legacy `haiku|sonnet|opus` aliases
  or rewrite live `config.yaml`.
- **The four hand-authored references (§2) must be converted in the same pass** as their shared-tree
  siblings, or the repo ships one neutralized copy and several stale verbatim ones that contradict it.
- **H7 risk:** the literal `<active>` token must be build-resolved, not shipped verbatim, or it reads
  as an unresolved template placeholder in user-followed cross-references.

---

## 7. Synthesis pointers for the lead

- The Codex and Cursor/Copilot/Droid distribution stories are **manifest-only, zero-codegen** — the
  cheapest portability proof is the §3 adapter layer plus a `build.sh` that selects one adapter.
- **Reconcile [codex-portability.md](codex-portability.md)** to the in-place one-tree pattern (it still
  assumes a `dist/` bundle emit).
- The relaxed-cron rule's real teeth are §4 + the three doc contradictions it surfaces (belief #7 eval,
  SECURITY.md, conventions.md `schedule.time`). Those are the load-bearing edits.
- Sequence the §6d prerequisites (build.sh recursion + `<active>` resolution + the `platform/` dir)
  **before** any prose neutralization lands, or every cross-reference dangles.
