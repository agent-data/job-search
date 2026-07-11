# Platform adapter — Pi (earendil-works pi-coding-agent)

The active-platform adapter a skill reads when it runs on **Pi** (earendil-works pi-coding-agent).
Neutralized prose names an action ("ask a closed choice", "show the run recipe") and defers the
Pi-specific literal here. Read only the section you need; each is self-contained. Companion reference:
`../../../docs/design-docs/multi-harness-portability.md` (the dossier) carries the verification status
and every "pin on install" caveat.

> **Verification.** Pi is **not installed** here — every runtime claim is structural, grounded in
> vendor docs and the superpowers origin repository, **not a live probe**. Items whose behavior is
> unconfirmed on a running Pi instance carry a **PIN** tag — confirm them before relying on the line
> in shipped copy. The install-line repo slug (`agent-data/job-search`) comes from project memory, not
> a Pi file — treat it as a **PIN**.

## Identity

The host agent is **Pi**; refer to it as "Pi" (or "the agent") in any user-facing line that would
otherwise say "Claude Code". Pi reads `AGENTS.md` for instructions; ensure the repo root contains an
appropriate entry-point file (or symlink) that Pi auto-loads on session start — the exact filename
is **PIN**.

## Tool map

Skills speak in actions; on Pi they resolve to these. Pi loads skills natively via the `pi.skills`
manifest pointer — there is no separate skill-invoke tool.

| Action | Pi tool |
|---|---|
| Read a file | native read tool — **PIN**: exact tool name |
| Write a whole file | native write tool — see **Whole-file write** below; **PIN**: exact tool name |
| Edit part of a file | native edit tool — **PIN**: exact tool name |
| Run a shell command | native shell tool — **PIN**: exact tool name |
| Search / list files | native search/shell tool — **PIN**: exact tool name |
| Dispatch a subagent | only via optional `pi-subagents` package — see **Concurrent detail reads** |
| Track a task list | native task-tracking tool (if present) — **PIN**: exact tool name |
| Ask a closed-choice question | none — see **Closed-choice question** |

## Run recipe

Show the user **verbatim**, copied exactly — do not reconstruct the tokens elsewhere. Pi skills are
invoked by name via the `pi.skills` manifest; there is no Claude-style `job-search:` namespace
prefix.

```
One-off run anytime:
  <pi-headless-command> job-search-run          # PIN: exact Pi headless command — see Headless invocation
Recurring (consent-gated cron/launchd — see Scheduling):
  set up a cron or launchd entry wrapping the one-off command on your cadence
```

PIN: the exact Pi headless invocation command is unverified — confirm the spelling before showing
this recipe to a user.

## Scheduling

Pi is **Tier 2** (see the dossier §4 scheduling matrix):

- **No native local scheduler documented.** Zero scheduler-related hits were found across all Pi
  files read; Pi is not installed here to probe further. This is a strong working assumption, not an
  absolute confirmed fact — **PIN**: confirm no native Pi scheduler exists before relying on the
  Tier-2 fallback.
- **Tier 2 — consent-gated machine schedule.** Because no native local scheduler is documented, fall
  back to a **consent-gated** `crontab`/`launchd` entry wrapping the Pi headless command (see
  Headless invocation). Show the exact cron/launchd line to the user, get an **explicit yes**, never
  install it silently, and leave it user-removable. Record `scheduling.mechanism: cron` (or
  `launchd`) in the registry. The consent-gated cron/launchd fallback is sanctioned precisely because
  Pi offers no verified native local alternative.

A cloud scheduler does **not** qualify — it cannot see the local `~/.job-search` workspace or the
local agent-data auth.

## Headless invocation

**UNVERIFIED — PIN.** No `pi exec`-style headless command has been found in any file read; the exit-code
contract is unknown. Keep the **written record primary** on Pi (the three blocked-run channels and the
record-is-primary contract are shared — see `_common.md` → **Written record**). On Pi the exit-code add-on
is **UNKNOWN** until confirmed on a live install: whether a Pi headless run exits non-zero on a blocked run
is **PIN** — confirm before wiring `$?` in a Tier-2 cron wrapper. The "native skill tool / real exit codes
/ headless command" facts are the shipped integration test's assertions (the test SKIPs when Pi is absent)
— not observed on a running instance.

## Closed-choice question

Pi has **no structured-choice UI** documented. Ask the same question as prose with the options on
numbered lines (the fallback `voice.md` already specifies), then read the user's number. Keep authoring
the header/question/labels in the skill; only the presentation degrades to numbered prose.

## Concurrent detail reads

Pi does **not** include a subagent dispatch primitive in its core install. Subagents are only available
via the optional **`pi-subagents`** package — this is **install-gated**, not a config flag (contrast
Codex, where `multi_agent` is a flag in `config.toml`). If `pi-subagents` is installed, dispatch all
queued postings at once in a single batch of concurrent subagents — never a one-at-a-time loop. If
`pi-subagents` is **not installed**, read and judge each posting **sequentially** — never block one read
on another, and **never fabricate a dispatch**. The mandatory sequential path is always present; the
concurrent path is strictly install-gated.

PIN: the exact subagent dispatch API (tool name, call signature, concurrency semantics) is unverified.

## Model tiers

`config.yaml` carries a portable tier token; map it to a Pi model id here.

| Tier token | Pi model |
|---|---|
| `fast` | a fast/lightweight Pi model — **PIN**: exact current id |
| `balanced` | a mid-tier Pi model — **PIN**: exact current id |
| `high` | a capable/reasoning Pi model — **PIN**: exact current id |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default `fast`).
PIN: exact current Pi model ids — confirm on install.

## Whole-file write

On Pi the whole-file write uses Pi's native write tool, or write to a temp file then `mv` into place. The
shared read-modify-write-the-whole-file rule (and the `jobs.jsonl` `>>` append exception) is in
`_common.md` → **Whole-file write**.

PIN: exact Pi write-tool name — confirm on install.

## Block-alert channel

On Pi the attention-pull alert channel is **UNKNOWN** — skip the alert silently until a live channel is
confirmed. The shared two-file durable-guarantee frame is in `_common.md` → **Block-alert channel**.

PIN: confirm whether Pi exposes a desktop/terminal notification surface before enabling the
`notify.desktop_notify_on_block` knob on this harness.

## agent-data setup

Authenticate with the shared harness-neutral `--api-key` path — see `_common.md` → **agent-data auth
(harness-neutral)** (Pi has no `--pi` flag). Pi-specific: this saves the key to `~/.agent-data/config.json`;
`agent_type` will be `null` — that is cosmetic skill-install metadata, **not** an auth/runtime gate. The
plugin install (via `pi.skills` manifest) is what places the job-search skills; `init` only needs to
authenticate.

PIN: confirm the agent-data CLI is on `PATH` inside Pi's runtime and that its network egress is
permitted. The install-line repo slug (`agent-data/job-search`) is from project memory, not a Pi file.

## Packaging & install

Ships as a Pi package: the **root `package.json`** carries a `pi` block —

```json
{
  "keywords": ["pi-package"],
  "pi": {
    "skills": ["./skills"]
  }
}
```

— pointing `pi.skills` at the **same** one `skills/` tree (no per-platform bundle). The optional
`pi.extensions` field may also be used for additional Pi-specific extensions (PIN: confirm field
semantics on install).

**Important — shared `package.json` with opencode:** Pi's `pi` block and opencode's fields (`main`,
`type`) live in the **same root `package.json`** — one file, both blocks. Task T5.2 sequences the
opencode fields and the Pi block together into a single `package.json`; neither adapter should author
the file in isolation. Note this coordination in any packaging step.

Install via Pi's package manager, or provide the repo slug to `pi install` (PIN: exact install
command — the repo slug `agent-data/job-search` is from project memory, not a Pi file).
