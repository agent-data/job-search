---
title: Hermes Harness Review — Skills System & Packaging
status: current
verified: partial
last_reviewed: 2026-06-30
code_refs: [shared/references/platform/hermes.md, docs/design-docs/2026-06-30-hermes-job-search-concierge.md, docs/exec-plans/active/2026-06-30-hermes-concierge-layer.md, docs/design-docs/2026-06-29-hermes-native-plugin.md, runtime/hermes_job_search/cli.py]
---
# Hermes Harness Review — Skills System & Packaging

How Hermes discovers, loads, triggers, and *mutates* on-disk skills, and how a third-party
pack installs — checked against the source so the maintainers can decide how to ship the
concierge layer. The load-bearing surprise for the concierge plan is that Hermes is not a
passive loader: a default-enabled background **Curator** and a foreground `skill_manage` tool
both edit installed skills, and *which install method you pick decides whether `job-search`
is exposed to that.

Scope boundary: this doc covers discovery, frontmatter, triggering, supporting-file bundling,
install/provenance, and the skill-mutation surfaces. Scheduling/cron/channel delivery and the
identity layer (`SOUL.md`, project-`AGENTS.md`) are other reviewers' scope and are only flagged
here, never resolved.

Source links point at `NousResearch/hermes-agent@main`; line numbers are cited in prose, not as
link anchors. Anything not reproduced on a running Hermes carries a **[PIN]**, matching the
adapter's discipline.

## What Hermes provides

**Discovery is a filesystem walk for `SKILL.md` — no manifest.** Hermes walks the skills dir
yielding every `SKILL.md`, excluding `.git`, `.github`, `.hub`, `.archive`
([`iter_skill_index_files`, agent/skill_utils.py:440](https://github.com/NousResearch/hermes-agent/blob/main/agent/skill_utils.py)).
Nothing in the load path reads a plugin manifest. The canonical local dir is
`SKILLS_DIR = HERMES_HOME/'skills'` i.e. `~/.hermes/skills/`
([tools/skills_tool.py:85](https://github.com/NousResearch/hermes-agent/blob/main/tools/skills_tool.py)).
The nested `~/.hermes/skills/<category>/<skill>/SKILL.md` layout is real — discovery is a recursive
walk and `<category>` is just a path segment.

**`skills.external_dirs` is a real `config.yaml` key.**
[`get_external_skills_dirs` / `get_all_skills_dirs`, agent/skill_utils.py:174-243](https://github.com/NousResearch/hermes-agent/blob/main/agent/skill_utils.py)
read `skills.external_dirs` (a string or list), expand `~` and `${VAR}`, resolve relative paths
against `HERMES_HOME` (not cwd), dedup, drop the local dir and any non-existent dir. The **local
dir is scanned first, external dirs after, in config order** — this ordering drives the
first-seen-name-wins rule below.

| Persistence path | What lives there |
|---|---|
| `~/.hermes/skills/` | local skills (copy-in, hub installs) |
| `~/.hermes/skills/.hub/lock.json` | hub/tap install provenance ledger (`HubLockFile.record_install`) |
| `~/.hermes/skills/.bundled_manifest` | names+hashes of Hermes's *own* repo skills seeded by `skills_sync` |
| `~/.hermes/skills/.archive/` | where the Curator moves skills (recoverable; never deleted) |
| `skills.external_dirs` (config.yaml) | extra trusted skill roots, scanned after the local dir |

**Frontmatter is agentskills.io-compatible and forgiving.** It is parsed as YAML (`CSafeLoader`)
with a `key:value` fallback. Hermes consumes only `name`, `description`, `platforms`, and the
`metadata.hermes.*` namespace (tags, related_skills, fallback/requires toolsets/tools, config);
unknown top-level keys are loaded into the dict but **never read**
([agent/skill_utils.py:249-325](https://github.com/NousResearch/hermes-agent/blob/main/agent/skill_utils.py)).
The validator requires **only `name` + `description`**
([tools/skill_manager_tool.py:217-253](https://github.com/NousResearch/hermes-agent/blob/main/tools/skill_manager_tool.py));
`version`/`author`/`license` are conventional and unenforced. A Claude-only `allowed-tools` key is
simply ignored — no bundled Hermes skill carries one.

**Triggering is dual: slash command *and* description.** Every enabled `SKILL.md` is auto-exposed
as a `/slash-command` (name lowercased, spaces/underscores→hyphens, invalid chars stripped); local
dir first, **first-seen name wins**, disabled and platform-incompatible skills skipped
([agent/skill_commands.py:215-277](https://github.com/NousResearch/hermes-agent/blob/main/agent/skill_commands.py)).
There is **no separate skill-invoke tool**. Skills are *also* description-triggerable: the prompt
builder renders a `name + description` skills index into the system prompt (snapshot-cached), and a
skill can be loaded by name via `skills_list`/`skill_view`
([agent/prompt_builder.py:563-652](https://github.com/NousResearch/hermes-agent/blob/main/agent/prompt_builder.py)).
So a skill triggers by slug, by aboutness, or by explicit name — not slash-only.

**Bundling a `scripts/` runtime (plus `references/`, `templates/`, `assets/`) is the canonical
pattern.** On load Hermes injects `[Skill directory: <abs>]`, lists the supporting files, and tells
the model to run scripts **by absolute path** via the `terminal` tool
([agent/skill_commands.py:139-202](https://github.com/NousResearch/hermes-agent/blob/main/agent/skill_commands.py));
Hermes's own bundled skills (e.g. google-workspace) invoke `python` scripts exactly this way. Extra
bundled reference files are harmless — Hermes lists them and resolves them by path.

**`${HERMES_SKILL_DIR}` / `${HERMES_SESSION_ID}` are content substitutions, not shell env vars.**
`substitute_template_vars` replaces these tokens **in the rendered `SKILL.md` text** at load time,
gated by `template_vars` which **defaults ON**
([agent/skill_preprocessing.py:42-60,126](https://github.com/NousResearch/hermes-agent/blob/main/agent/skill_preprocessing.py)).
A grep of `agent/`, `tools/`, `gateway/` finds these names *only* in that content-substitution path
— they are never exported into the `terminal` session. A bare `echo $HERMES_SKILL_DIR` in a shell
would be empty. Inline-shell expansion of `` !`cmd` `` is **OFF by default** (`inline_shell`,
False); template-var substitution is the only default-on preprocessing.

**A skill has a built-in config channel.** `metadata.hermes.config` entries are resolved from
`skills.config.*` in `config.yaml` (or defaults) and injected as a `[Skill config: …]` block into
the loaded skill message ([agent/skill_utils.py:269-420](https://github.com/NousResearch/hermes-agent/blob/main/agent/skill_utils.py)).

**Install verbs and provenance.** `hermes skills tap add <owner/repo>` only **registers** a GitHub
repo as a source (`mgr.add`); installing from it is a separate step
([hermes_cli/skills_hub.py:1037-1047](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/skills_hub.py)).
Hub/tap installs land under `~/.hermes/skills/` and are recorded in `.hub/lock.json`. Provenance is
derived, not stored as a tag: a skill is **agent-created iff its name is in neither `.bundled_manifest`
nor `.hub/lock.json`** ([tools/skill_usage.py:109-148](https://github.com/NousResearch/hermes-agent/blob/main/tools/skill_usage.py)).
A third-party pack is therefore *never* "bundled" provenance, and **how you install it decides its
class**:

| Install method | Provenance class | Curator-eligible? | Pinnable? |
|---|---|---|---|
| `tap`/hub install (`.hub/lock.json`) | hub-installed | no | no |
| copy into `~/.hermes/skills/<cat>/<skill>/` | **agent-created** | **yes** | yes |
| `skills.external_dirs` → repo `skills/` | external (outside scanned base) | no | n/a |

**The Curator edits agent-created skills autonomously, by default.** `is_enabled()` returns
`cfg.get('enabled', True)` — **ON unless config says otherwise**
([agent/curator.py:39-42](https://github.com/NousResearch/hermes-agent/blob/main/agent/curator.py)).
`maybe_run_curator()` fires from gateway idle ticks
([gateway/run.py:13484-13490](https://github.com/NousResearch/hermes-agent/blob/main/gateway/run.py))
and from the CLI, spawning a forked LLM agent. Defaults: review every 7 days, mark stale at 30 days
unused, archive at 90 days unused; the first run is deferred one interval and report-only. Strict
invariants: it **only touches agent-created skills**, **never deletes** (archives to `.archive/`,
recoverable), and **skips pinned** skills. Its LLM "umbrella consolidation" pass can MERGE / CREATE /
PATCH / ARCHIVE / demote agent-created skills.

**The foreground `skill_manage` tool can edit *any* skill.** Its docstring is explicit: existing
skills "(bundled, hub-installed, or user-created) can be modified or deleted wherever they live"
([tools/skill_manager_tool.py:1-8](https://github.com/NousResearch/hermes-agent/blob/main/tools/skill_manager_tool.py)),
and the tool actively tells the model to "patch it immediately" when a skill it used had gaps. The
**only** hard fence is `_pinned_guard`, and it is best-effort (a write goes through if the telemetry
sidecar is unreadable). Create refuses on a name collision across all dirs; the agent-created
security scan is OFF by default.

**Pinning protection is asymmetric.** `hermes curator pin/unpin` **refuse for bundled and
hub-installed skills** ([hermes_cli/curator.py:217-237](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/curator.py)).
So a **hub-installed** `job-search` cannot be pinned → `_pinned_guard` does **not** shield it from
`skill_manage` edits (though the Curator still won't auto-archive a hub install). A **copied-in**
`job-search` is agent-created, so it *can* be pinned — but is *also* Curator-eligible.

**Security and host markers.** Loading a skill from outside `~/.hermes/skills/` plus configured
`external_dirs` logs a non-blocking "outside the trusted skills directory" warning; `external_dirs`
are treated as trusted ([tools/skills_tool.py:1013-1041](https://github.com/NousResearch/hermes-agent/blob/main/tools/skills_tool.py)).
Community/hub installs are always security-scanned (`scan_skill`); builtin never; agent-created only
if `skills.guard_agent_created` is set. For host-gating, Hermes sets/reads `HERMES_SESSION_PLATFORM`
(and `HERMES_PLATFORM`), with `HERMES_HOME` present
([gateway/session_context.py:32-66](https://github.com/NousResearch/hermes-agent/blob/main/gateway/session_context.py))
— the substrate a skill needs to branch on "am I on Hermes." **[PIN]** exact marker spelling and
in-session visibility are inferred from source, not yet reproduced on a live run.

## How the job-search adapter uses it

Reconciling [the adapter](../../../shared/references/platform/hermes.md) line by line. The adapter is
accurate where it matters; one PIN is wrong and two omit a hazard.

- **CONFIRMS — Packaging (`hermes.md:216-218`): "Ships as a Hermes skill pack … with no plugin
  manifest required."** Discovery scans for `SKILL.md` only; the agentskills.io frontmatter (name +
  description required, `metadata.hermes.*` namespace) loads cleanly and Claude-only keys are ignored.

- **CONFIRMS — Tool map (`hermes.md:26-28`): an installed skill is a slash command, not a separate
  skill-invoke tool.** Add the nuance the adapter omits: it is *also* description-triggerable via the
  prompt skills-index and loadable by name, so triggering is not slash-only — relevant to the
  concierge's "front door" framing.

- **CONFIRMS / PIN resolved — `external_dirs` (`hermes.md:224-225` [PIN]).** `skills.external_dirs`
  behaves exactly as the adapter describes (`~`/`${VAR}` expansion, `HERMES_HOME`-relative, dedup,
  existence check), and external dirs are treated as trusted (no outside-dir warning). The PIN can be
  cleared.

- **CONFIRMS — bundled runtime via `terminal` by path (`hermes.md:41,167-183`).** The
  `scripts/hermes_job_search/` pattern is the canonical supporting-file mechanism; Hermes lists
  `scripts/` and instructs running by absolute path. The source-vs-bundled split is consistent:
  [`runtime/hermes_job_search/cli.py`](../../../runtime/hermes_job_search/cli.py) is the source,
  `skills/*/scripts/hermes_job_search/cli.py` are `build.sh`-synced copies — not a contradiction.

- **CONTRADICTS — `${HERMES_SKILL_DIR}` "exported into the skill's `terminal` session"
  (`hermes.md:175` [PIN]).** It is **not** a terminal env var. The token is substituted into the
  `SKILL.md` *content* at load (default-on `template_vars`); the runtime call works because the literal
  `${HERMES_SKILL_DIR}` in the rendered skill text is replaced with the absolute path *before* the
  model runs it. The adapter's fallback advice ("resolve the skill directory from the run path") is
  sound — Hermes also injects `[Skill directory: <abs>]` — but the "exported into terminal session"
  framing is wrong, and the real latent footgun is `template_vars: false` (below), which the adapter
  does not mention.

- **INCOMPLETE — verify recipe (`hermes.md:233`).** The recipe runs `hermes skills tap add
  agent-data/job-search` then jumps straight to `hermes chat -s job-search-run`. Because `tap add`
  only *registers* the source, the required intermediate `hermes skills install …` step is missing.
  Treat the recipe as incomplete until the install verb is added.

- **OMITS a hazard — install-by-copy (`hermes.md:223-224`).** The layout is supported, but the
  adapter presents copy-in as an equivalent option with no mention of the Curator. A copied-in pack is
  **agent-created**, exposing `job-search` to the default-enabled Curator's stale/archive/consolidate
  behavior (see Implications). Tap/hub and `external_dirs` installs are not exposed this way.

- **UNCONFIRMED — Identity (`hermes.md:19-22`).** `SOUL.md` load from `HERMES_HOME` and the project
  `AGENTS.md` cwd→git-root walk are out of this topic's read set (they live in `hermes_cli/config.py`
  + context-files docs). Not contradicted, just not verified here — the identity/config reviewer owns
  it.

## Implications for the concierge layer

Assessing each relevant assumption in [the concierge design doc](../2026-06-30-hermes-job-search-concierge.md)
and [exec plan](../../exec-plans/active/2026-06-30-hermes-concierge-layer.md).

**SOUND — host-gate inside one canonical skill (design §"Hermes-only behavior is host-gated";
exec T3).** The design's "The concierge behavior is active only when the host is Hermes" and "avoids
introducing a second public skill name" is feasible: Hermes supplies the host/platform markers and a
single skill triggers by description + slash and branches internally — the same adapter-selection
mechanism job-search already uses across hosts. Detection is the skill's own job; Hermes only supplies
the markers (spelling still **[PIN]**). No platform constraint forces a second skill, so the
[Hermes-native plugin design](../2026-06-29-hermes-native-plugin.md)'s single-pack model holds.

**SOUND — bundle Hermes-only references so installed behavior never depends on the repo tree
(design §"Post-install phase": "Installed behavior must not depend on the source repo's `hermes/`
tree still existing"; exec T2).** Aligns with Hermes mechanics: `references/` (and `templates/`,
`scripts/`, `assets/`) are listed at load and resolved by absolute path; extra bundled reference files
are harmless. The bundle-from-source model already works for the runtime, so bundling references the
same way is a no-op risk for Hermes. The exec plan's "Done when … `git status --porcelain skills` →
empty" gate is structurally sound — carrying `scripts/` + `references/` inside each skill is exactly
how Hermes ships supporting files.

**CAUTION — install method is not Curator-neutral (design §"Architecture"/§"Bootstrap vs
post-install"; adapter omits it).** This is the most important finding for the maintainers. The docs
treat copy-into-`~/.hermes/skills/` as an equivalent install, with **no mention of the Curator**. A
copied-in pack is agent-created, so the default-enabled background Curator can mark `job-search` stale
at 30 days unused, archive it at 90 days, and its LLM consolidation pass could merge/patch/demote it.
A job-search install that sits idle between runs is precisely the "unused" profile the Curator prunes.
Mitigations, in preference order: **(1)** prefer `tap`/hub install or `skills.external_dirs` (neither
is Curator-eligible); **(2)** if copy-in is used, document `hermes curator pin job-search` (works only
because copy-in is agent-created) or disabling the Curator. Blast radius is limited — archive is
recoverable, never auto-deleted — so this is a caution, not a blocker, but the adapter's Packaging
section should name it.

**CAUTION — installed skills are not immutable substrate (design implicit; exec "no hand-edited
bundles" gate).** The design implicitly assumes the installed skills are stable execution substrate.
But `skill_manage` can edit/patch/delete **any** skill "wherever it lives," including `job-search`'s
`SKILL.md` and bundled `scripts/`, and its description encourages "patch it immediately" on gaps. A
**hub-installed** `job-search` cannot be pinned, so `_pinned_guard` will not shield it; only a copy-in
(agent-created) install can be pinned. This is a low-probability but real self-modification/drift
vector. Mitigate by leaning on `build.sh` as source-of-truth plus the `validate_platforms.py`
byte-equality drift check the exec plan already adds, and document that agent/user edits to an
installed skill will not reflect upstream.

**SOUND — permissioned memory-assisted drafting (design §3-4 + §"Memory and session-history
policy"; exec T3 step 3).** The substrate exists — Hermes memory is `MEMORY.md`/`USER.md` plus session
history — and the design's permission gate ("ask permission before using memory and session history to
draft a starting brief") is purely **prompt-level discipline**, not enforced by Hermes. That is exactly
the moderate model the design wants; nothing in the skills layer blocks or weakens it.

**SOUND and necessary — `clarify` for closed choices only (design §5: "use `clarify` only for true
multiple-choice decisions"; exec T4).** `clarify` **always auto-appends a 5th "Other (type your
answer)" option** ([tools/clarify_tool.py:19](https://github.com/NousResearch/hermes-agent/blob/main/tools/clarify_tool.py)),
so authoring your own Other/free-text option yields a *duplicate* — which is the dogfooding bug T4
targets. The fix (never author Other; render open-ended asks as plain prose) is correct and matches
[adapter §"Closed-choice question"](../../../shared/references/platform/hermes.md).

**PLAUSIBLE (defer) — delivery handoff to Hermes-native channel setup (design §11 +
§"Delivery-handoff policy").** Nothing in the skills/packaging layer blocks the "hand off to
Hermes-native setup, then resume" design. The deep cron/channel routing verification is the scheduling
reviewer's scope; at this layer it is sound.

## Open questions / must-verify-live

Only a running Hermes can settle these:

- **Host-marker spelling and visibility [PIN].** Confirm `HERMES_SESSION_PLATFORM` / `HERMES_PLATFORM`
  / `HERMES_HOME` are present and carry the expected values in an installed-skill run — the host-gating
  branch depends on it.
- **`template_vars: false` footgun.** With this override, a literal `${HERMES_SKILL_DIR}` is left
  unsubstituted in `SKILL.md`, breaking the runtime invocation. Default is `true`, but the adapter
  should carry a one-line note and the skill should prefer the `[Skill directory: <abs>]` injection or
  path-resolution fallback rather than relying solely on the token.
- **Curator reach via raw `terminal` to an `external_dirs` install.** The live candidate list is
  agent-created-only and the dry-run banner forbids `terminal` mutations under `~/.hermes/skills/`, but
  `terminal` itself is unrestricted — residual (low) uncertainty whether a forked Curator agent could
  `mv`/`rm` an `external_dirs` copy. Verify before recommending `external_dirs` as fully hands-off.
- **Hub/community install scan verdict.** The bundled Python runtime uses `subprocess`/`os`; confirm
  whether `scan_skill` heuristics gate a hub install to an "ask" verdict (allow/ask/block, user can
  force) — possible one-time install friction.
- **Identity layer.** `SOUL.md` load and project-`AGENTS.md` walk are unverified here — identity
  reviewer's scope.

Meta-note for the maintainers: three files named in the original research brief do **not** exist in
`hermes-agent@main` (`agent/skill_bundles.py`, `tools/skill_provenance.py`,
`hermes_cli/subcommands/skills.py`). The real equivalents are `tools/skill_usage.py` (provenance via
`.bundled_manifest`/`.hub/lock.json`), `tools/skills_sync.py` (bundled-skill seeding), and
`hermes_cli/skills_hub.py` + `hermes_cli/skills_config.py` (CLI skills commands). Cite those.
