# Platform adapter — Factory Droid

The active-platform adapter a skill reads when it runs on **Factory Droid** (`droid`). Neutralized
prose names an action ("ask a closed choice", "show the run recipe") and defers the Droid-specific
literal here. Read only the section you need. Shared boilerplate is in `_common.md`; the full
per-platform study and every "confirm on install" item are in the dossier
(`../../../docs/design-docs/multi-harness-portability.md`).

> **Verification.** Factory Droid (`droid`) is **not installed** here — every runtime claim below is
> structural (vendor docs + superpowers' shipped adapter files), not a live probe. This adapter is
> deliberately lean: it carries only the genuine Droid residual and honest stubs. Treat every literal
> as unconfirmed until probed on a running instance (AAS-TEST-15), on a par with the other
> un-installed siblings — no capability is asserted flatly here.

## Identity

The host agent is **Factory Droid**; refer to it as "Droid" (or "the agent") in any user-facing line
that would otherwise say "Claude Code". Droid reads a session-start context file (analogous to
`CLAUDE.md`) on launch; the exact filename is unverified — confirm with `droid --help` on a live
install.

## Tool map

Skills speak in actions; on Droid they resolve to Droid's native tools. The action vocabulary is the
portable contract; the native tool-name literals are unverified here. The one host-specific note that
carries weight: subagents dispatch via **`Task` with `subagent_type`** — see **Concurrent detail
reads** (the exact accepted `subagent_type` values are unverified). Closed-choice questions have no
structured UI — see **Closed-choice question**.

## Run recipe

`droid exec` defaults to **read-only mode**; a search pass writes run records and digests, so the run
needs at least `--auto low` to permit those writes (whether `--auto low` suffices vs `--auto medium`
is unverified — confirm on a live install).

```
One-off run anytime:
  droid exec --auto low "run job-search-run"
Recurring (consent-gated machine schedule — see Scheduling):
  a cron/launchd entry wrapping the one-off command on your cadence
```

The exact skill-invocation string Droid expects (callable tool vs namespaced slash vs pure
auto-invocation) is the highest-risk unverified item — confirm it before relying on this recipe.

## Scheduling

Droid is **Tier 2** — no native local scheduler (Droid's docs delegate scheduling to external CI/CD,
citing only a GitHub Actions cron example, which is cloud and cannot see the local `~/.job-search`
workspace or agent-data auth). Fall back to a **consent-gated** `crontab`/`launchd` entry wrapping
`droid exec --auto low "run job-search-run"`: show the exact line, get an explicit yes, never install
it silently, leave it user-removable, and record `scheduling.mechanism: cron` (or `launchd`). To turn
scheduling off, remove the crontab entry and clear the scheduling marker in the registry.

## Headless invocation

Run the search pass non-interactively with `droid exec --auto low "run job-search-run"` (the default
is read-only, so a writing run needs at least `--auto low`). Surface every outcome through the
**written record** (the three blocked-run channels and the record-is-primary contract are shared —
see `_common.md` → **Written record**). Droid's exit-code behavior is **UNVERIFIED here** — whether
a headless run (or a skill-level HALT) returns non-zero on a blocked run is unconfirmed on an
un-installed host; until it is probed on a live install, never tell the user a cron wrapper's `$?`
will be non-zero on a blocked run, and rely on the written record, not `$?`.

## Closed-choice question

Droid has **no structured-choice UI** documented. Ask the same question as prose with the options on
numbered lines (the fallback `voice.md` already specifies), then read the user's number. Keep
authoring the header/question/labels in the skill; only the presentation degrades.

## Concurrent detail reads

Droid supports isolated-context subagents via the **`Task`** tool with `subagent_type`. Where the
subagent primitive is available, dispatch all queued postings **at once, in a single batch** — never
a one-at-a-time loop. When no subagent slot is available, read and judge each posting
**sequentially** — never block one read on another, but **do not fabricate a dispatch**. (Whether
subagents are on by default and the exact `subagent_type` values Droid accepts are unverified.)

## Model tiers

`config.yaml` carries a portable tier token; map it to a Droid model here. The tier tokens are the
portable contract; the concrete Droid model ids are unverified — confirm with `droid models list` or
equivalent on a live install.

| Tier token | Droid model |
|---|---|
| `fast` | a fast model (Factory's current fast tier) |
| `balanced` | a mid-tier model |
| `high` | a high-capability model |
| `inherit` | the model this run is already on |

A legacy model name carried over from another harness's config maps to the nearest tier (default `fast`).

## Whole-file write

On Droid the whole-file write uses the native write tool, or write to a temp file then `mv` into
place. The shared read-modify-write-the-whole-file rule (and the `jobs.jsonl` `>>` append exception)
is in `_common.md` → **Whole-file write**.

## Block-alert channel

Droid exposes **no documented desktop-notification channel** — skip the attention-pull alert silently
when the `notify.desktop_notify_on_block` knob is set (confirm whether any notification API exists on
a live install). The shared two-file durable-guarantee frame is in `_common.md` → **Block-alert
channel**.

## agent-data setup

Authenticate with the shared harness-neutral `--api-key` path — see `_common.md` → **agent-data auth
(harness-neutral)** (Droid has no `--droid`/`--factory` flag).

## Packaging & install

Droid loads the pack from a committed manifest — **the committed manifest is the spec** (AAS-PORT-07):
`.factory-plugin/plugin.json` exists in the repo and points at the **same** one `skills/` tree (no
per-platform bundle). Droid also supports the `.claude-plugin/` compatibility layer. Install via
Droid's plugin manager; the exact `droid plugin marketplace add` / `install` argument form is
unverified — confirm against `droid plugin --help` on a live install.
