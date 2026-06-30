---
title: Hermes harness review — tools, clarify & delivery channels
status: current
verified: partial
last_reviewed: 2026-06-30
code_refs: [shared/references/platform/hermes.md, docs/design-docs/2026-06-30-hermes-job-search-concierge.md, docs/exec-plans/active/2026-06-30-hermes-concierge-layer.md, docs/design-docs/2026-06-29-hermes-native-plugin.md]
---
# Hermes harness review — tools, clarify & delivery channels

> **Fact-check caveat.** A later verification pass overturned this doc's BLOCKING claim that "the
> messaging gateway wires no clarify": `clarify` **is** wired on messaging (a `tools/clarify_gateway.py`
> pending-session path exists; choices render as a numbered list). Downgrade that finding from blocking to
> a verify-live caution (interactive choices vs. a pending free-text reply). The T4/open-ended and
> auto-"Other" conclusions stand. Read the [Corrections log](overview.md#corrections-log) first.

What the `clarify` tool actually does and — the load-bearing part — **where it actually renders**, plus
how Hermes routes a scheduled run's output to a delivery destination and what "set up a new destination"
really costs. This is the substrate under exec-plan **T4** (the duplicate-"Other" preference bug) and
design **§11** (delivery-destination selection + the new-destination handoff) — the two places the
concierge most directly leans on a surface-specific Hermes mechanism.

Hermes source files are linked whole at commit `f98b5d0` of `NousResearch/hermes-agent`; the line
numbers cited in prose were read at that commit. This doc is source-cited, **not** verified against a
running Hermes (`verified: partial`); the messaging-surface behavior in particular needs a live pass.

## What Hermes provides

### `clarify` — two modes, and the only way the duplicate "Other" arises

`clarify` has exactly two modes, selected by whether `choices` is supplied
([`tools/clarify_tool.py`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/tools/clarify_tool.py),
modes at lines 23-55):

- **Multiple-choice** — pass a `choices` list. `MAX_CHOICES = 4` (line 18); a 5th option labeled
  `Other (type your answer)` is **always auto-appended by the CLI renderer** when choices exist
  ([`cli.py`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/cli.py), lines 11052-11076),
  and any authored choices beyond the first four are **silently truncated** (clarify_tool.py:52-53).
- **Open-ended** — **omit `choices` entirely** → a free-text prompt. This is a **first-class, supported
  mode**, not a degraded one (clarify_tool.py:113-121). The renderer shows
  `Type your answer in the prompt below, then press Enter.` rather than a picker (cli.py:10996-11001,
  11046-11048). A correctly-authored open-ended ask therefore **cannot** render as a malformed picker.

The duplicate-"Other" symptom has a single, precise cause: the auto-append at cli.py:11052-11076 is
**unconditional** when choices exist, and `clarify` **does not dedupe** the authored choices list
(clarify_tool.py:51). So authoring your own "Other / something else" option produces **two** Other-ish
rows. `clarify` never double-appends on its own — the only way to get the duplicate is to hand it a
choices list for what should have been an open-ended ask.

### Where `clarify` actually renders — the surface gap

`clarify` only works when a `clarify_callback` is wired into the agent. When none is injected the tool
returns a **soft JSON error**, not a crash:
`{"error":"Clarify tool is not available in this execution context."}` (clarify_tool.py:57-61; call
site [`run_agent.py`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/run_agent.py)
:9299-9305, whose `AIAgent` constructor defaults `clarify_callback=None` at lines 929, 1149). Across the
whole repo the callback is wired in only four places — `cli.py`, `tui_gateway/server.py`,
`hermes_cli/oneshot.py` (a synthetic neutralizer), and `delegate_tool.py` (`=None`). The messaging
gateway is conspicuously absent.

| Surface | `clarify` renders interactively? | Mechanism |
|---|---|---|
| Interactive CLI (`hermes chat` TUI) | **YES** | callback wired (cli.py:3604, 8592-8657); on no answer within the timeout (default 120s) the agent is told `Use your best judgement to make the choice and proceed.` |
| Web / TUI gateway | **YES** | wired as a blocking client request ([`tui_gateway/server.py`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/tui_gateway/server.py):1598-1600) |
| Messaging gateway (Telegram / Discord / Slack / WhatsApp / Signal / …) | **NO** | tool is *offered* but **no callback is wired** → soft error |
| Headless oneshot (`hermes -z` / `run_oneshot`) | **NO** | synthetic callback returns `[oneshot mode: no user available. Pick the best option … and continue.]` ([`hermes_cli/oneshot.py`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/hermes_cli/oneshot.py):297-308, 320-331; routed at `hermes_cli/main.py`:10375-10381) |
| Cron / scheduled session | **NO** | the `clarify` (and `messaging`) toolset is disabled; fresh isolated session, `skip_memory=True` ([`cron/scheduler.py`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/cron/scheduler.py):1044-1057) |
| Subagent (leaf **or** orchestrator) | **NO** | `clarify` is in `DELEGATE_BLOCKED_TOOLS`, the toolset is stripped, and children are built with `clarify_callback=None` ([`tools/delegate_tool.py`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/tools/delegate_tool.py):40-49, 2393-2396) |

The messaging row is the surprise. `clarify` **is** in `_HERMES_CORE_TOOLS` and in every messaging
platform's toolset ([`toolsets.py`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/toolsets.py)
:29-31, 53-54, 350-398), so the model is **offered** the tool on Telegram/Discord/Slack/WhatsApp/Signal.
But the messaging gateway
([`gateway/run.py`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/gateway/run.py)) wires no
callback — the string `clarify` does not appear anywhere in that file, and none of its four `AIAgent`
constructions (incl. 12276-12322) pass `clarify_callback`. So on a messaging surface a `clarify` call
returns the soft "not available" error and renders nothing interactive.

> **[PIN — inferred]** The `clarify` module docstring (clarify_tool.py:6-11) claims messaging platforms
> render choices "as a numbered list" via `gateway/run.py`. **No such renderer exists** in `gateway/`.
> The documented messaging-clarify behavior is not implemented in this checkout; no alternative
> (button- or reply-based) path was found. Treat messaging-clarify as non-functional until a live run
> proves otherwise.

### Scheduled delivery — the `deliver` target model

A scheduled run's **final response text** is delivered to the job's `deliver` target (cron/scheduler.py
:150-184; tool schema
[`tools/cronjob_tools.py`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/tools/cronjob_tools.py)
:469, 501-503):

- `local` — **no delivery**; the output is saved only.
- `origin` — deliver to the chat the job was created from (`{platform, chat_id, thread_id}`). This is
  also the documented effect of **omitting `deliver`**. If `origin` is missing, it falls back to the
  first platform with a configured home channel.
- `platform:chat_id:thread_id` — an explicit target.

A run **suppresses** delivery by emitting a `[SILENT]` marker (or empty output); the output is still
saved either way (cron/scheduler.py:112-115). So a message that must reach the user has to emit
non-empty text. Valid delivery platforms (cron/scheduler.py:76-100): telegram, discord, slack, whatsapp,
signal, matrix, mattermost, homeassistant, dingtalk, feishu, wecom, weixin, sms, email, webhook,
bluebubbles, qqbot, yuanbao. Home-channel env vars exist for most of these (telegram/discord/slack/
signal/matrix/mattermost/sms/email/…) **but not whatsapp** — WhatsApp delivery needs an explicit
`chat_id`/`origin`, with no home-channel fallback.

Delivery is daemon-bound: the **gateway** is a single background process that connects to all configured
messaging platforms, runs the cron scheduler (ticking ~60s), and delivers results
([`website/docs/user-guide/messaging/index.md`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/website/docs/user-guide/messaging/index.md)
:9, 66-95). **Scheduled delivery only fires while the gateway is running.**

### Adding a destination — `/sethome`, pairing, and the gateway-setup wizard

Two very different operations hide behind "a new destination":

- **A new chat/channel on an already-configured platform** is light: `/sethome` sets the current chat as
  that platform's home channel, or pass an explicit `chat_id`. No restart (messaging/index.md:133). DM
  `pairing approve` authorizes a new **user** on an already-configured platform — it is *not* a way to
  add a platform (messaging/index.md:200-214).
- **A new platform** is heavily out-of-band: create a bot/token with the provider (e.g. Telegram
  `@BotFather`), run the interactive `hermes gateway setup` wizard, which "offers to start/restart the
  gateway when done" (messaging/index.md:97-118;
  [`telegram.md`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/website/docs/user-guide/messaging/telegram.md)
  :11-27). A gateway **restart** is the documented way to apply platform/config changes (gateway/run.py
  :7056, 13612) — and the restart tears down the active gateway/session.

### Other tool literals (for completeness)

Web tools are `web_search`, `web_extract`, and `web_crawl` — **there is no `web_fetch`** (toolsets.py:33,
77;
[`tools/web_tools.py`](https://github.com/NousResearch/hermes-agent/blob/f98b5d0/tools/web_tools.py)
:11-12, 31). `delegate_task` runs synchronously inline in the parent turn (delegate_tool.py:2369); its
concurrency, depth, model-inheritance, and the leaf `clarify` block are covered in the sibling review
[`delegation-and-subagents.md`](delegation-and-subagents.md) and not repeated here — it matters to this
topic only as the "subagent cannot clarify" row above.

## How the job-search adapter uses it

Reconciled against the Hermes adapter
[`shared/references/platform/hermes.md`](../../../shared/references/platform/hermes.md) — its
**Tool map**, **Closed-choice question**, **Scheduling**, and **Block-alert channel** sections.

| Adapter claim | Verdict | Detail |
|---|---|---|
| `clarify` = a question plus a `choices` list of ≤4 options (hermes.md:107-108) | **CONFIRMS** | `MAX_CHOICES = 4`, excess truncated (clarify_tool.py:18-20, 52-53) |
| Hermes auto-appends a final "Other" choice, so **never author** an "other / something else" option (hermes.md:108-110) | **CONFIRMS** | auto-append is unconditional + no dedup; authoring "Other" is exactly what produces the T4 duplicate. The adapter's warning is the correct guard |
| If >4 discrete options are needed, ask as prose on numbered lines (hermes.md:110-111) | **CONFIRMS** | `clarify` hard-truncates to 4, so >4 must be prose |
| `clarify` is unavailable in a headless or cron run; there, pick a sane default and never block (hermes.md:112-113, 74) | **CONFIRMS** | cron disables the toolset; oneshot injects a "pick a default" neutralizer. Different mechanisms, same net effect |
| Leaf subagents also have `clarify` blocked (hermes.md:114) | **CONFIRMS** | both leaf and orchestrator children; see the sibling delegation review |
| A cron run is a fresh, isolated session that cannot `clarify` (hermes.md:74) | **CONFIRMS** | scheduler.py:1044-1057 |
| Tool map: `web_extract` / `web_search`, no `web_fetch` (hermes.md:39) | **CONFIRMS** | web_tools.py:11-12 |
| Cron delivers to the job's `deliver` target; default `origin` = the creating chat, else the home channel; `[SILENT]`/empty suppresses (hermes.md:48, 185-195) | **CONFIRMS** | scheduler.py:150-184, 112-115 |
| The on-block notify knob maps to "deliver the block to chat" ([Block-alert channel](../../../shared/references/platform/hermes.md)) | **CONFIRMS** | it relies on the same `deliver`/`origin` routing (scheduler.py:150-184) |
| `clarify` is **THE** mechanism for closed-choice questions on Hermes, presented surface-agnostically (hermes.md:38, 105-114) | **CONTRADICTS / INCOMPLETE** | see below |

**The one material gap.** The adapter's **Closed-choice question** section names exactly one exception
to `clarify` — "unavailable in a headless or cron run." It never says that `clarify` **also does not
render on messaging platforms**. The source shows `clarify` renders interactively only on the CLI/TUI
and the web/TUI gateway; on Telegram/Discord/Slack/WhatsApp/Signal it is offered but the gateway wires
no callback, so it returns the soft "not available" error. Because `/job-search` is invocable from a
messaging surface, this omission is load-bearing for the concierge (next section). The adapter should
add messaging to the list of surfaces where `clarify` cannot be used and prescribe the numbered-prose
fallback there too.

**UNCONFIRMED (PINs this topic leaves open):**

- The adapter's headless recipe `hermes chat -Q -s job-search-run -q "…"` (hermes.md:88-93) carries an
  open `[PIN]` on its flags, and this topic could not close it. `hermes_cli/main.py` routes only
  `-z`/`--oneshot` through `run_oneshot` (the synthetic clarify); whether `hermes chat -q <prompt>` runs
  via the **interactive** CLI — where, with no TTY, a `clarify` call would **time out after ~120s** and
  fall through to "use your best judgement" — or via a true non-interactive runner was not pinned. It
  matters only if the headless path ever issues a `clarify`; `job-search-run` is self-contained, so in
  practice it should not.
- What the model does **after** receiving the messaging "not available" error is inferred (a graceful
  re-ask in prose), not traced. The error itself is confirmed; the recovery is not.

## Implications for the concierge layer

Assessed against the concierge design doc
[`../2026-06-30-hermes-job-search-concierge.md`](../2026-06-30-hermes-job-search-concierge.md) and the
exec plan [`../../exec-plans/active/2026-06-30-hermes-concierge-layer.md`](../../exec-plans/active/2026-06-30-hermes-concierge-layer.md).
The runtime/substrate framing is the [Hermes-native plugin design](../2026-06-29-hermes-native-plugin.md).

**1. Closed-choice asks on a messaging surface — BLOCKING.** The concierge interview and its closed
menus — §3's decline path (`short interview` / `comprehensive interview` / `import existing brief`),
§10's cadence menu, §11's `here` / configured-destination / `set up a new destination` — all assume
`clarify` renders wherever the user is. It does not. A user who drives `/job-search` from Telegram (a
primary Hermes surface) gets the soft "not available" error for **every** closed-choice ask, not just
open-ended ones — degraded onboarding end to end. Exec-plan **T4** fixes only the open-ended case.
**Required change:** make the flow messaging-aware — when the surface is a messaging platform, ask both
open-ended **and** closed-choice questions as numbered prose, treating `clarify` as CLI/TUI-only; or
explicitly scope the interactive concierge to the CLI/TUI and document that messaging onboarding falls
back to prose. The design and the adapter both silently assume `clarify` works on the user's surface.

**2. T4's open-ended fix (design §5, exec-plan T4 Step 2) — SOUND, and correctly targeted.** Design §5
says keep open-ended questions "actually open-ended" and "use `clarify` only for true multiple-choice
decisions." That is exactly right: the duplicate-"Other" arises only when a skill passes a `choices`
list (including a hand-authored "Other") for what should be open-ended, colliding with the always-on
auto-"Other." Omitting `choices` / using prose for open-ended asks is the correct remedy — and **more
robust than relying on `clarify`'s native open-ended mode**, because even open-ended `clarify` does not
render on messaging. The adapter already encodes this guard (hermes.md:108-110).

**3. T4's "broken clarify fallback" framing — NEEDS CHANGE (caution): it is a misdiagnosis.** The exec
plan (Done-when, line 35; T4 objective) attributes the symptom to a "broken `clarify` fallback." The
tool is not broken — the symptom is mis-use: authoring `choices` plus an explicit "Other" for an
open-ended question collides with the always-on auto-"Other." The chosen remedy still resolves it, but
the eval should assert the **behavioral contract** (open-ended ⇒ no `choices` passed ⇒ free-text
render), not that a "`clarify` bug" was patched — otherwise a future author re-introduces choices and
the eval, written against a phantom bug, still passes.

**4. The new-destination handoff (§11 + Delivery-handoff policy) — NEEDS CHANGE (caution): it conflates
two cases.** §11 says if the user picks "set up a new destination," `job-search` should "hand off to
Hermes-native channel setup and resume the flow afterward … continuous … not like a separate product."
That is realistic for a **new chat/channel on an already-configured platform** (light: `/sethome` or an
explicit `chat_id`, no restart, genuinely in-flow). It is **not** realistic for a **new platform**:
native setup means creating a provider bot+token out-of-band (`@BotFather`), running the interactive
`hermes gateway setup` wizard, and start/restarting the gateway — a multi-minute, multi-app, human-driven
process whose restart tears down the active session. Single-turn "resume continuously" is not achievable
there. **Required change:** the design must distinguish new-platform (heavy, "configure out-of-band, then
resume on the next interaction/run") from new-chat-on-existing-platform (light, in-flow), and stop
promising single-turn continuity for the new-platform case. The design's own non-goal — don't duplicate
Hermes messaging-setup docs — is sound; it just under-specifies the resume contract.

**5. Enumerating "already-configured destinations" (§11) — CAUTION: not a tool call.** The `deliver`
mapping is clean: `here` ⇒ `origin` (the creating chat) or `/sethome`; an explicit channel ⇒
`platform:chat_id:thread_id`; save-only ⇒ `local`. But there is **no first-class API to list configured
channels** — the concierge must read gateway config/env (the `*_HOME_CHANNEL` vars, configured platform
tokens) via the `terminal` tool to populate the "already-configured" option. Flag this as a config/env
read, and remember WhatsApp has no home-channel fallback (it needs an explicit `chat_id`).

**6. Proactive recurring job, delivered to "here" (§10, §12) — SOUND.** `cronjob(action="create", …,
deliver="origin")` resolves to the creating chat, and the scheduled `job-search-run` executes headless
with `clarify` and messaging disabled — so it must be fully self-contained, which it already is.
Consistent with the adapter's Scheduling section (hermes.md:65-77).

**7. "Recurring delivery just works once they opt in" (implicit, §10-13) — CAUTION.** Scheduled delivery
fires **only while the gateway daemon is running** (the scheduler ticks inside the gateway). A user who
lives in the CLI and never starts `hermes gateway` gets no scheduled delivery. The concierge should
verify the gateway is installed and running **before** promising recurring delivery — the adapter
already notes "the gateway must be running for jobs to fire" (hermes.md:68-69); the flow should surface
that as an explicit prerequisite check, not an assumption.

## Open questions / must-verify-live

- **Messaging-clarify is non-functional in source, but unproven on a live run.** The docstring claims a
  numbered-list renderer that does not exist; no button/reply alternative was found. A live Telegram run
  settles whether `clarify` silently degrades to the soft error (the inference) or some UI exists that
  the static read missed. **[PIN]** — gates implication #1's severity.
- **The `hermes chat -Q -s … -q` headless path.** Whether it wires `clarify` (interactive CLI → ~120s
  timeout → "use your best judgement") or runs non-interactively, plus the exact `-Q/-q/-s` spellings,
  was not pinned; only `-z` routes through `run_oneshot`. **[PIN]** (adapter hermes.md:88-93).
- **Model recovery after the "not available" error on messaging** is inferred (graceful prose re-ask),
  not traced. **[PIN]**
- **Can the gateway hot-add one new platform without a full restart?** Evidence points to
  restart-required (the wizard "offers to start/restart"; multiple restart paths), but a hot-add path was
  not exhaustively ruled out. This decides whether a new-**platform** handoff (implication #4) can ever be
  in-flow. **[PIN]**
- **"Set up a new destination" semantics.** The design never states whether this means a new platform or
  a new chat on an existing platform — and the feasibility of "resume continuously" hinges entirely on
  that distinction. This is a design gap to close, not a Hermes-source question.
