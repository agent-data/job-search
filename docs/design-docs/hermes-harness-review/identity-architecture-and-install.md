---
title: Hermes Harness Review — Identity, Architecture & Install
status: current
verified: partial
last_reviewed: 2026-06-30
code_refs: [shared/references/platform/hermes.md, docs/design-docs/2026-06-30-hermes-job-search-concierge.md, docs/exec-plans/active/2026-06-30-hermes-concierge-layer.md, docs/design-docs/2026-06-29-hermes-native-plugin.md, runtime/hermes_job_search/cli.py, README.md, AGENTS.md]
---
# Hermes Harness Review — Identity, Architecture & Install

> **Fact-check caveat.** A later verification pass overturned one claim below: a no-`origin` cron run
> falls back to a configured **home channel**, not local-only. The doc's load-bearing findings (no
> host==Hermes signal; `${HERMES_SKILL_DIR}` is a load-time template token, not a shell env var) stand.
> Read the [Corrections log](overview.md#corrections-log) first.

How Hermes establishes agent identity, discovers project context and skills, and installs a skill pack — the substrate the [concierge layer](../2026-06-30-hermes-job-search-concierge.md) bootstraps onto. It matters because the concierge's host-gating, its SOUL.md-vs-AGENTS.md channel choice, and its single-file install story each rest on Hermes mechanics that the shipped [adapter](../../../shared/references/platform/hermes.md) partly mis-describes. This is one doc of the Hermes harness review (`overview.md` indexes the set); scheduling/delivery and skill-runtime mechanics are covered in their sibling docs. Hermes source is cited against `NousResearch/hermes-agent@main`; lines a running Hermes has not yet confirmed carry a **PIN**, matching the adapter's discipline.

## What Hermes provides

### Identity and HERMES_HOME

The host agent is **Hermes** ("Hermes Agent"), built by Nous Research; the CLI binary is `hermes`. When no persona file is present the system prompt falls back to `You are Hermes Agent, an intelligent AI assistant created by Nous Research.` ([`agent/prompt_builder.py`](https://github.com/NousResearch/hermes-agent/blob/main/agent/prompt_builder.py) L134-142). `HERMES_HOME` defaults to `~/.hermes` and is overridable by the `HERMES_HOME` env var; the skills dir is `HERMES_HOME/skills` and config is `HERMES_HOME/config.yaml` ([`hermes_constants.py`](https://github.com/NousResearch/hermes-agent/blob/main/hermes_constants.py) L12-18, 228, 236-238).

### Project-context discovery — the exact rules

This is the heart of the SOUL/AGENTS channel question. Hermes loads at most **one** project-context file per session plus an always-on identity file, by these rules ([`agent/prompt_builder.py`](https://github.com/NousResearch/hermes-agent/blob/main/agent/prompt_builder.py) L76-110, 1041-1180; [`agent/subdirectory_hints.py`](https://github.com/NousResearch/hermes-agent/blob/main/agent/subdirectory_hints.py)):

| File | Where Hermes looks at startup | Loaded into | Notes |
|---|---|---|---|
| `SOUL.md` | `HERMES_HOME` only (`~/.hermes/SOUL.md`) | system prompt — identity slot #1 | never probes cwd; always loaded independently of project context |
| `.hermes.md` / `HERMES.md` | cwd, then walk **up to the git root** | system prompt — project context | the **only** file given the git-root walk |
| `AGENTS.md` | cwd **top-level only** | system prompt — project context | **no recursive walk, no git-root walk** |
| `CLAUDE.md` | cwd top-level only | system prompt — project context | loads only if no `.hermes.md`/`AGENTS.md` |
| `.cursorrules` | cwd top-level only | system prompt — project context | last in priority |
| `AGENTS.md`/`CLAUDE.md`/`.cursorrules` in navigated subdirs | dirs the agent opens, ancestor-walk ≤5 parents | the **tool result**, not the system prompt | progressive `SubdirectoryHintTracker`; not a startup load |

Two consequences the concierge depends on:

- **First-match-wins project context.** Priority is `.hermes.md` → `AGENTS.md` → `CLAUDE.md` → `.cursorrules`; only the first present is loaded. This repo ships **both** `AGENTS.md` and `CLAUDE.md` at root, so on Hermes `AGENTS.md` wins and `CLAUDE.md` is ignored ([`agent/prompt_builder.py`](https://github.com/NousResearch/hermes-agent/blob/main/agent/prompt_builder.py) L1144-1176).
- **SOUL.md is identity-only, from HERMES_HOME.** It carries tone/personality/style; repo-specific paths, commands, ports, and workflow belong in `AGENTS.md` ([`website/docs/guides/use-soul-with-hermes.md`](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/guides/use-soul-with-hermes.md) L26-36, 196-210). The auto-injected context set is exactly `AGENTS.md`, `SOUL.md`, `.cursorrules`, memory, and preloaded skills ([`hermes_cli/_parser.py`](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/_parser.py) L203-209, via `--ignore-rules`).

### Skill discovery and registration

Hermes discovers skills by scanning every skills directory for `SKILL.md` ([`agent/skill_utils.py`](https://github.com/NousResearch/hermes-agent/blob/main/agent/skill_utils.py) L328-344) — no plugin manifest is required. Three registration paths, all real:

- `hermes skills tap add <owner/repo>` — add a GitHub repo as a skills source ([`hermes_cli/main.py`](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/main.py) L9217-9221).
- Drop skill directories into `~/.hermes/skills/<category>/<skill>/` ([`hermes_constants.py`](https://github.com/NousResearch/hermes-agent/blob/main/hermes_constants.py) L236-238).
- `skills.external_dirs` in `config.yaml` (default `[]`): expands `~`/`${VAR}`, resolves relative paths against `HERMES_HOME`, and skips any entry resolving to `~/.hermes/skills/` ([`hermes_cli/config.py`](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/config.py) L972-976; [`agent/skill_utils.py`](https://github.com/NousResearch/hermes-agent/blob/main/agent/skill_utils.py) L174-229). Pointing it at this repo's `skills/` dir is exactly the supported use.

`${HERMES_SKILL_DIR}` and `${HERMES_SESSION_ID}` are **SKILL.md template tokens**, text-substituted into the skill markdown at load time (gated by `skills.template_vars`, default `True`) — **not** shell env vars exported into the `terminal` subprocess ([`agent/skill_preprocessing.py`](https://github.com/NousResearch/hermes-agent/blob/main/agent/skill_preprocessing.py) L10-13, 37-60, 115-131).

### Install footprint

The real one-liner is `curl -fsSL .../scripts/install.sh | bash` ([`scripts/install.sh`](https://github.com/NousResearch/hermes-agent/blob/main/scripts/install.sh)). It is not lightweight: it provisions **Python 3.11 via `uv`** and downloads **Node 22** into `~/.hermes/node/`, symlinking `node`/`npm`/`npx` into `~/.local/bin` "for browser tools". ripgrep is **optional** — installed via a system package manager (apt/brew/pkg/cargo) when possible, with file search degrading to a `grep` fallback when absent ([`setup-hermes.sh`](https://github.com/NousResearch/hermes-agent/blob/main/setup-hermes.sh) L217-266; install.sh L607-613). `setup-hermes.sh` is the manual-clone developer path (`uv venv` + `pip install -e .[all]`) and seeds bundled skills into `~/.hermes/skills/`. The `agent-data` CLI also installs to `~/.local/bin`, so it lands on the same PATH Hermes uses.

### Headless invocation, delivery, memory

`hermes chat -Q -s <skill> -q "<prompt>"` runs a single non-interactive pass: `-q/--query` passes the prompt, `-s/--skills` preloads skills, `-Q/--quiet` keeps stdout to the response ([`hermes_cli/_parser.py`](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/_parser.py) L236-256, 270-275). Cron delivery target `origin` means the chat the job was created from; when no origin info exists the code falls back to `local` (save to file), **not** a home channel ([`cron/scheduler.py`](https://github.com/NousResearch/hermes-agent/blob/main/cron/scheduler.py) L126-159). Hermes has genuine persistent cross-session memory plus FTS5 session search ([`agent/prompt_builder.py`](https://github.com/NousResearch/hermes-agent/blob/main/agent/prompt_builder.py) L150-174) — the capability the concierge's "draft preferences from prior context" depends on.

## How the job-search adapter uses it

Reconciling the [adapter](../../../shared/references/platform/hermes.md) against the source. Identity-, install-, and packaging-relevant claims only; scheduling/delivery PINs belong to the sibling scheduling doc.

| Adapter claim / PIN | Verdict | Evidence |
|---|---|---|
| Host is Hermes / "Hermes Agent", built by Nous Research, CLI `hermes` | **CONFIRMED** | prompt_builder.py L134-142 |
| `SOUL.md` lives under `HERMES_HOME`, loaded only from there; keep job-search out of it | **CONFIRMED** | prompt_builder.py L1041-1050; use-soul-with-hermes.md |
| "Hermes reads a project `AGENTS.md` by **walking cwd → git root**" | **CONTRADICTED** | `AGENTS.md` is cwd top-level only (prompt_builder.py L1079-1092, 1146); the git-root walk belongs to `.hermes.md`/`HERMES.md` |
| Skills discovered by `SKILL.md` scan; install via `tap add` / `~/.hermes/skills/` / `skills.external_dirs` [PIN] | **CONFIRMED** (PIN resolved) | skill_utils.py L328-344; main.py L9217-9221; config.py L972-976 |
| PIN: `${HERMES_SKILL_DIR}` is exported into the skill's `terminal` session | **CONTRADICTED** | it is a load-time SKILL.md **template token**, not a shell env var (skill_preprocessing.py L10-13, 54-55) |
| PIN: `hermes chat -Q/-s/-q` flags are well-formed | **CONFIRMED** | _parser.py L236-256, 270-275 |
| Exit code of a quiet `hermes chat -Q` is trustworthy ("YES") | **UNCONFIRMED** | not traced to the `cmd_chat`/oneshot return-code path |
| `hermes -z "<prompt>"` ignores `-s/--skills` | **UNCONFIRMED** | top-level `-s` is registered as an inherited flag paired with `-z` (_parser.py L96-108, 174-181); runtime behavior not traced |
| Hermes silently ignores Claude-only `SKILL.md` frontmatter keys | **UNCONFIRMED** | the "discover by `SKILL.md` scan" half is confirmed; the ignore-foreign-keys half was not verified in the frontmatter parser |

Two contradictions are load-bearing for this review:

- **The `AGENTS.md` walk is wrong.** A repo-root `AGENTS.md` auto-loads **only when Hermes is launched from the directory that directly contains it** — not from a subdirectory, and not via a git-root walk. The adapter also cites `hermes_cli/config.py` as the source for this behavior, but the authoritative code is `agent/prompt_builder.py` (+ `agent/subdirectory_hints.py`). The Identity section of the adapter needs this corrected so no future work relies on a subdirectory-launched repo `AGENTS.md` loading.
- **`${HERMES_SKILL_DIR}` resolves at load, not in the shell.** The adapter's run recipe — `python3 ${HERMES_SKILL_DIR}/scripts/hermes_job_search/cli.py` — works because the model reads the **already-substituted** concrete path from its rendered SKILL.md; typing the literal `${HERMES_SKILL_DIR}` into a fresh shell would not expand it. The PIN's own stated fallback (resolve the skill dir from the run path) is the safe instruction, and becomes load-bearing if a user has disabled `skills.template_vars`.

## Implications for the concierge layer

For each relevant assumption in the [design doc](../2026-06-30-hermes-job-search-concierge.md) and [exec plan](../../exec-plans/active/2026-06-30-hermes-concierge-layer.md):

| Assumption (source) | Verdict | Why |
|---|---|---|
| Bootstrap source of truth is a single `hermes/INSTALL.md`; README points there directly (design "Bootstrap phase"; exec T1) | **sound** | Hermes has no special discovery for `INSTALL.md` — it is a plain doc the agent reads only when README/user points there. The design already frames it as a "documentation boundary only," which is the right model. |
| Concierge behavior is host-gated — active only when the host is Hermes (design "Hermes-only behavior is host-gated"; exec non-goal "No cross-host behavior change") | **needs change** | Hermes exposes **no single `host == Hermes` boolean** to a skill. `HERMES_PLATFORM`/`HERMES_SESSION_PLATFORM` denote the messaging **channel** (telegram/discord/cli…), not host identity ([`agent/skill_utils.py`](https://github.com/NousResearch/hermes-agent/blob/main/agent/skill_utils.py) L121-160). Neither the design nor the adapter names a concrete detection signal. |
| SOUL.md-vs-AGENTS.md is the identity-vs-guidance boundary; keep job-search out of SOUL.md (design "Hermes source layer"; adapter Identity) | **sound, with one fix** | The boundary is real. In practice the concierge ships guidance in **bundled skills** (exec T2 syncs `hermes/references` into skills), not a repo `AGENTS.md` — correctly, since installed behavior must not depend on the repo tree. Fix the adapter's `AGENTS.md`-walk line so nobody relies on repo-`AGENTS.md` auto-load. |
| Register via `tap add` / `~/.hermes/skills/` / `skills.external_dirs`; deterministic runtime executes state ops (design "Hermes source layer"; exec T1/T2) | **sound** | All three paths and the `SKILL.md`-scan discovery are confirmed; `external_dirs` resolves relative paths against `HERMES_HOME`. `INSTALL.md` can safely document all three. |
| Memory-assisted preference drafting, with permission, from memory + session history (design steps 3-4; memory policy) | **sound** | Persistent memory + FTS5 session search exist; the permission gate and "workspace brief is canonical, memory is only a draft" rule are UX choices, not Hermes limitations. |
| Build/validation bundles Hermes-only references into the intended skills, byte-for-byte, with no bleed (exec T2) | **sound** | `build.sh` already syncs the runtime and shared refs into the consuming skills and `validate_platforms.py` enforces a byte-for-byte match; extending the same pattern to `hermes/references` is low-risk. |
| Runtime path references are consistent across docs (design cites `runtime/hermes_job_search/cli.py`; adapter cites `${HERMES_SKILL_DIR}/scripts/hermes_job_search/cli.py`) | **needs change (clarity)** | Both are correct but name **different layers**: [`runtime/hermes_job_search/cli.py`](../../../runtime/hermes_job_search/cli.py) is the repo **source**; `skills/<skill>/scripts/hermes_job_search/` is the **bundled** in-skill copy that `build.sh` produces and that `${HERMES_SKILL_DIR}` resolves to. State the source-vs-bundled distinction explicitly so a cold reader does not think there are two runtimes. |

On host-gating specifically — the most consequential design decision here: gating is achievable, and the build already relies on "an active platform adapter the agent self-selects." But the design leaves the mechanism unspecified. Pin a **deterministic** signal the runtime can check — presence of `~/.hermes/` or a set `HERMES_HOME`, or the `hermes` binary on PATH — rather than relying on the model self-identifying as Hermes, so the gate is reproducible across sessions and models. This connects directly to the [Hermes-native plugin architecture](../2026-06-29-hermes-native-plugin.md), which keeps the skills harness-neutral and pushes all Hermes-specificity into the adapter + runtime.

## Open questions / must-verify-live

Only a running Hermes can settle these; treat each as **PIN** until reproduced on the maintainer's live install:

- **Exit-code trustworthiness of `hermes chat -Q`.** The adapter asserts a quiet run exits non-zero on failure; this was not traced to the chat/oneshot return-code path. Until proven, the written run record stays the primary signal, and the exit code is only an add-on.
- **Whether `hermes -z` honors `-s/--skills`.** The parser accepts `-s` paired with `-z`, which contradicts the adapter's "ignores `-s`"; the runtime behavior is untraced. `chat -Q -s … -q …` remains the safe way to preload this skill.
- **Whether Hermes silently ignores Claude-only `SKILL.md` frontmatter keys.** The packaging claim rests on this; the frontmatter parser was not inspected.
- **A concrete `host == Hermes` detection signal.** None is documented in Hermes or the concierge docs. The design must choose one (see host-gating above) before the gate can be implemented deterministically.
- **`skills.template_vars` disabled.** It defaults `True`, but if a user turns it off, `${HERMES_SKILL_DIR}` will not substitute and the "resolve the skill dir from the run path" fallback becomes load-bearing — not currently called out in the design.
- **No-origin delivery fallback.** When a cron job has no origin info, delivery falls back to `local` (file save), not the "home channel" the adapter's parenthetical implies — minor, and primarily a scheduling-doc concern.
