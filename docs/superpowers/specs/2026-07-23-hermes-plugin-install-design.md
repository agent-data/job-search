# Hermes Agent plugin install — design

**Date:** 2026-07-23 · **Branch:** `feat/hermes-plugin-install` (off `main` 793aef5, v0.6.0) ·
**Status:** approved in brainstorm; exec plan next.

**Evidence pin:** every Hermes behavior below was verified read-only against
`NousResearch/hermes-agent` v0.19.0, commit `b0358cf3c8aff565f193eea82e75586631438014`
(committed 2026-07-22). Citations are `file:line` in that revision. If implementation happens
against a newer Hermes, re-verify the pinned facts first.

## Goal

A Hermes Agent user can:

1. Open a new Hermes Agent session.
2. Paste one short instruction from the README.
3. Hermes retrieves `INSTALL_FOR_HERMES.md` and follows it.
4. Job Search installs through Hermes's plugin manager
   (`hermes plugins install agent-data/job-search --enable`).
5. The five skills become available under their normal names — `job-search`, `job-search-run`,
   `job-search-agent`, `job-preference-interview`, `evaluate-job-fit`.
6. The user starts a new session and says: “Set up my job search. I'm looking for …”

The user never edits YAML by hand, never clones the repository themselves, and never needs a
qualified name like `job-search:job-search`.

## Approach

Install the complete repository as a Hermes plugin: `hermes plugins install
agent-data/job-search --enable` clones the whole tree to `<HERMES_HOME>/plugins/job-search/`.
The repo gains a minimal Hermes adapter at its root — `plugin.yaml` (manifest), `__init__.py`
(integrity check + namespaced fallback skill registration), `after-install.md` (post-install
panel), `INSTALL_FOR_HERMES.md` (the agent-facing installation guide). The skills reach
normal-name discovery through a second, config-side path: the installing Hermes instance adds
`plugins/job-search/skills` to the active profile's `skills.external_dirs` — Hermes resolves
that relative entry against HERMES_HOME, exactly where the plugin manager put the tree.

Keeping the repository intact is required: every skill resolves `../../shared/references/*.md`
and `../../shared/scripts/mechanics/*.sh` relative to its own directory, and those hops land
inside the installed plugin. Nothing under `skills/`, `shared/`, or `templates/` changes; the
skills are never installed or copied individually.

Two registration paths are deliberate:

- **`skills.external_dirs`** → the five skills enter `<available_skills>` and `hermes skills
  list` under their bare names, get `/job-search`-style slash commands, and are selectable from
  natural language. This path fulfils the product promise.
- **`ctx.register_skill()` in `__init__.py`** → explicit namespaced fallbacks
  (`job-search:job-search`, …) reachable via `skill_view("job-search:<name>")`. Source-verified:
  skills registered this way never appear in `<available_skills>` or `hermes skills list`
  (facts 8 and 17 below), so this path alone cannot satisfy the goal — which is why the config
  edit is mandatory and the guide, not `__init__.py`, performs it.

## Supersedes

The unmerged `feat/hermes-native-host` branch (2026-06-29/30) integrated Hermes through
`hermes skills tap add`, per-skill platform adapter files (`references/platform/hermes.md`),
and a bundled stdlib-Python state-ops runtime (`runtime/hermes_job_search/`); its design doc
(`docs/design-docs/2026-06-29-hermes-native-plugin.md` on that branch) explicitly rejected the
plugin-manager route. This design replaces that approach: main now ships the deterministic
mechanics as shell scripts (`shared/scripts/mechanics/`), so the bundled runtime is
unnecessary, and the plugin manager provides install/update/remove lifecycle plus the
intact-repo guarantee. The old branch stays parked and unmerged; none of its files are reused.

## What Hermes does (source-verified facts this design stands on)

| # | Fact | Citation (hermes-agent@b0358cf) |
|---|---|---|
| 1 | `hermes plugins install` accepts `owner/repo` shorthand → `https://github.com/owner/repo.git` | `hermes_cli/plugins_cmd.py:206-211` |
| 2 | Destination is `<HERMES_HOME>/plugins/<name>`; `<name>` comes from `plugin.yaml` `name` first, repo name only as fallback | `plugins_cmd.py:75-79, 121, 497-500` |
| 3 | `--enable` writes `plugins.enabled`; without it a non-TTY install lands **disabled** (the enable prompt fires only on a TTY) | `plugins_cmd.py:602-621`; `subcommands/plugins.py:34-44` |
| 4 | The whole tree installs unfiltered (no size caps, no file filtering; 60 s clone timeout); root-level `*.example` files are copied to their stem names — nothing in this repo matches that glob | `plugins_cmd.py:472-533, 278-296` |
| 5 | `after-install.md` at the plugin root is rendered as markdown in a panel right after install | `plugins_cmd.py:399-406` |
| 6 | The installer enforces `manifest_version` ≤ 1; the runtime validates `kind` against `{standalone, backend, exclusive, platform, model-provider}` (unknown → warning + `standalone`); unknown manifest fields are ignored | `plugins_cmd.py:69-72, 507-523`; `plugins.py:277, 1587-1592` |
| 7 | The entry point is root `__init__.py`, function `register(ctx)`; plugins load once per process at agent/gateway/oneshot start; a raised exception is caught per-plugin and stored as that plugin's `error` while other plugins keep loading; disabled plugins are never imported | `plugins.py:1772-1792, 2040-2046, 1824-1829, 1390-1395, 1458-1468` |
| 8 | `ctx.register_skill(name, path, description="")`: `path` must be the existing SKILL.md file; `name` must match `[a-zA-Z0-9_-]+` with no `:`; the skill is stored as `<plugin>:<name>` and is **not** listed in `<available_skills>` — plugin skills are explicit loads via `skill_view()` only | `plugins.py:1198-1241` (docstring at `:1204-1211`); `tools/skills_tool.py:696-699, 1002-1045`; `agent/prompt_builder.py:1526-1527` |
| 9 | A **relative** `skills.external_dirs` entry resolves against **HERMES_HOME** (not cwd, not the config file's directory); `~` and `${VAR}` expand; a nonexistent directory is silently skipped; the local skills dir and duplicates are dropped | `agent/skill_utils.py:483-508` |
| 10 | External-dir skills are one subdirectory per skill containing `SKILL.md`; **no frontmatter field is required** (`name` defaults to the directory name; `version` is never read); support dirs (`references/`, `templates/`, `assets/`, `scripts/`) are excluded from the walk | `skill_utils.py:797-819`; `skills_tool.py:727-761`; `skill_utils.py` `parse_frontmatter:123-169` |
| 11 | Name collisions: the local `<HERMES_HOME>/skills/` tree wins over external dirs; first-seen wins in config order | `skills_tool.py:718-739`; `prompt_builder.py:1631-1657` |
| 12 | `hermes config path` prints the active profile's config file; HERMES_HOME resolution order is context override → `HERMES_HOME` env var → platform default; `--profile <name>` sets `HERMES_HOME=<root>/profiles/<name>`; a sticky `active_profile` file supplies the default profile | `subcommands/config.py:56-57`; `hermes_cli/config.py:684-686, 9103-9104`; `hermes_constants.py:106-131`; `main.py:471-647` |
| 13 | `hermes plugins update <name>` runs `git pull --ff-only`; local changes make git itself refuse and the tree is left untouched; force-reinstall is `hermes plugins install <spec> --force` (delete + fresh clone); update has no `--force` | `plugins_cmd.py:636-673, 1969-1975, 525-533` |
| 14 | `hermes plugins remove <name>` deletes the tree and cleans **no** config — stale `plugins.enabled`/`plugins.disabled` entries remain | `plugins_cmd.py:676-690, 693-770` |
| 15 | `hermes plugins list` reads manifests only — it cannot prove a plugin loaded; load results surface in-session via `/plugins`, or on stderr/log with `HERMES_PLUGINS_DEBUG=1` during a real load | `plugins_cmd.py:1125-1188`; `cli.py:9236-9257` |
| 16 | The `<available_skills>` prompt block is built at agent construction and cached; `/reload-skills` does **not** invalidate it; the session-reset command is **`/new`** — there is no `/reset` | `prompt_builder.py:1501-1753`; `system_prompt.py:316-324`; `skill_commands.py:438-439`; `commands.py:68` |
| 17 | `hermes skills list` is a deterministic, token-free, fresh-process listing of local + external-dir skills by bare name; it excludes plugin-registered skills | `skills_hub.py:924-1020` |
| 18 | `hermes -z "<prompt>"` (oneshot mode) starts a fresh agent process — importing enabled plugins — sends one prompt, prints the final reply, and exits | `hermes_cli/oneshot.py:1-20, 70` |

Three places Hermes's public docs disagree with its source, resolved in source's favor:
`requires_env` is not a load gate (prompted at install, reported by the dashboard, never blocks
`register()`); `HERMES_PLUGINS_DEBUG=1 hermes plugins list` shows no load tracebacks (list
never imports modules); the relative-path base of `external_dirs` is undocumented.

## Deliverables

### 1. `plugin.yaml` (repo root)

```yaml
manifest_version: 1
name: job-search
version: "0.7.0"
description: A private, local-first job-search assistant — five skills that find postings, judge them against your prose preferences (no scores), and write digests on a schedule you control.
kind: standalone
```

No `requires_env`: Job Search onboarding must remain available when agent-data is missing or
unauthenticated, and declaring it would also add an interactive env-var prompt during install
(fact 4's installer flow). No `provides_tools`/`provides_hooks` — the adapter provides none.
`name: job-search` pins the install directory (fact 2).

### 2. `__init__.py` (repo root)

Stdlib-only (`pathlib`), no Hermes imports, no I/O beyond existence checks, on the order of 40
lines:

1. `REPO_ROOT = Path(__file__).resolve().parent`.
2. An explicit tuple of the five skill names — never a directory scan, so an incomplete
   release fails loudly instead of shrinking silently.
3. Verify `skills/<name>/SKILL.md` for each name, and the directories `shared/references/`,
   `shared/scripts/mechanics/`, `templates/`.
4. On any miss: `raise RuntimeError` naming every missing path and the recovery
   (`hermes plugins install agent-data/job-search --force`; see `INSTALL_FOR_HERMES.md`).
   Hermes stores the message as the plugin's load error and keeps loading other plugins
   (fact 7).
5. Otherwise register each skill:
   `ctx.register_skill(name, REPO_ROOT / "skills" / name / "SKILL.md")` — default (empty)
   description, so no frontmatter text is duplicated into Python.

Nothing else: no tools, hooks, commands, config writes, workspace logic, or agent-data logic.
A root `__init__.py` is inert for every other consumer: the pytest suite loads modules via
`importlib` file paths (`grep -rn "sys.path\|import scripts\|from scripts" tests/*.py` finds
no package imports), the other harnesses read their own manifests, and `scripts/doc_lint.py`
scans only `AGENTS.md`/`CLAUDE.md`/`ARCHITECTURE.md` plus `docs/**`.

### 3. `after-install.md` (repo root)

At most ~10 lines, rendered in the installer's panel (fact 5). Content: the repository is
installed at this directory; the five skills are not yet discoverable by their normal names;
the Hermes instance that ran the install must add `plugins/job-search/skills` to the active
profile's `skills.external_dirs` and verify discovery — the remaining steps are in
`INSTALL_FOR_HERMES.md` in this directory; a new session (`/new`) is required before the
skills appear; installation is complete only after that verification passes. It does not
duplicate the guide.

### 4. `INSTALL_FOR_HERMES.md` (repo root)

Written for the Hermes Agent instance executing it, not for a human at a shell. Opens with:
read this whole file before changing anything. Each step carries exact commands, the expected
result, and a stop condition. Carries the line “Verified against hermes-agent v0.19.0
(`b0358cf`, 2026-07-22).” Structure:

**Step 1 — Confirm the environment.** `command -v git`, `command -v hermes`;
`hermes config path` → the active config file; HERMES_HOME = that file's parent directory
(fact 12). Never assume `~/.hermes/config.yaml`; never modify another profile. If hermes is
missing or the active profile cannot be identified: stop and explain.

**Step 2 — Inspect any existing installation.** `hermes plugins list` +
`test -d "$HERMES_HOME/plugins/job-search"`. Cases:
(a) absent → install (Step 3);
(b) present and `git -C "$HERMES_HOME/plugins/job-search" status --porcelain` empty → update
(Step 3);
(c) present, clean, but incomplete — missing `plugin.yaml`, `__init__.py`, any of the five
`skills/<name>/SKILL.md`, or the three shared directories → explain, then
`hermes plugins install agent-data/job-search --force` (fact 13);
(d) local changes → show the `git status` output, change nothing, tell the user what blocks
the update, stop.
A command exiting 0 is never taken as proof by itself — Step 5 verifies files and discovery
regardless.

**Step 3 — Install or update through Hermes.**
New install: `hermes plugins install agent-data/job-search --enable` (the flag also avoids the
disabled-by-default non-TTY path, fact 3). Existing clean install:
`hermes plugins update job-search`. Installed but disabled:
`hermes plugins enable job-search`. Manual cloning only if the Hermes plugin command fails,
labeled explicitly as recovery. Never `hermes skills tap add`; never install the skills
individually.

**Step 4 — Make the skills discoverable.** Edit the file printed by `hermes config path` with
file tools — not `hermes config set`, which is scalar-oriented — so that

```yaml
skills:
  external_dirs:
    - plugins/job-search/skills
```

holds the entry exactly once, preserving every other setting and every existing
`external_dirs` entry, and keeping `external_dirs` a YAML list. Equivalence check before
adding: resolve each existing entry the way Hermes does — expand `~` and `${VAR}`, resolve a
relative path against HERMES_HOME (fact 9) — and compare absolute paths;
`$HERMES_HOME/plugins/job-search/skills` is the same entry as the relative form. Prefer the
relative form (it moves with the active profile). Verify: `hermes config get
skills.external_dirs` re-parses the saved file through Hermes's own reader, and `test -d` the
resolved directory — a nonexistent directory is silently skipped at scan time (fact 9), so
this check is load-bearing.

**Step 5 — Verify (layered; the final report says which layers ran).**

1. `hermes plugins list` → `job-search` enabled. Proves discovery + enabled state only
   (fact 15).
2. Files: `plugin.yaml`, `__init__.py`, the five `skills/<name>/SKILL.md`,
   `shared/references/`, `shared/scripts/mechanics/`, `templates/`.
3. Config: the `external_dirs` entry present exactly once; the resolved directory exists.
4. `hermes skills list` (fresh process) → all five bare names present (fact 17). This is the
   deterministic proof of normal-name discovery.
5. Load proof: `HERMES_PLUGINS_DEBUG=1 hermes -z "Reply with exactly: ok"` → stderr free of
   `Failed to load plugin 'job-search'` (facts 7, 18). One small model call, zero agent-data
   calls. The user-visible alternative is `/plugins` in the next session.
6. In-place reference resolution: from an installed skill directory,
   `test -f "$HERMES_HOME/plugins/job-search/skills/job-search/../../shared/references/internals.md"`
   and `test -x "$HERMES_HOME/plugins/job-search/shared/scripts/mechanics/workspace-discovery.sh"`
   (the mechanics scripts ship executable — `ls -l shared/scripts/mechanics/` shows
   `-rwxr-xr-x`).

**Step 6 — Skill-name collisions.** For each of the five names:
`test -d "$HERMES_HOME/skills/<name>"` — a local skill with the same name wins over the
external dir (fact 11). On a hit: name the conflicting path, delete nothing, report that Job
Search installed but normal discovery is blocked for that name, and do not claim full success.

**Step 7 — Finish.** Explain that Hermes builds its available-skills list when a session
starts (fact 16), so the five skills appear after the user starts a new session — `/new`
(there is no `/reset`). Give the exact next step:

```text
Set up my job search. I’m looking for …
```

and note that Job Search onboarding in that session handles agent-data setup, the private
workspace, and any schedule. Report to the user: the plugin install path; the config file that
changed; whether the plugin loaded (and which evidence); whether all five bare skill names
were found; that a new session is required.

**Updating.** Check `git -C "$HERMES_HOME/plugins/job-search" status --porcelain` is empty →
`hermes plugins update job-search` (git refuses on local changes; surface its message
verbatim; never overwrite) → re-run Step 5 layers 1, 3, 4, 5 → new session.

**Removing.** Locate the active config; remove every `external_dirs` entry whose resolved path
equals `$HERMES_HOME/plugins/job-search/skills` (relative and absolute forms alike),
preserving unrelated entries; also remove stale `job-search` entries from `plugins.enabled`
and `plugins.disabled` — Hermes's remove command leaves them behind (fact 14); then
`hermes plugins remove job-search`; verify the plugin directory is gone; new session.
`~/.job-search` is user data — plugin removal never touches it.

### 5. `README.md`

Add `### Hermes Agent` after `### Pi` under `## Installation`:

````markdown
### Hermes Agent

Copy and paste the following into a new Hermes Agent session:

```text
Retrieve and follow the installation instructions at:
https://raw.githubusercontent.com/agent-data/job-search/main/INSTALL_FOR_HERMES.md
```

After installation, start a new Hermes Agent session and use the Quickstart sentence above.
````

(In the real README this closing line links “Quickstart” to the existing `#quickstart`
section anchor; the link is spelled out here as plain text only because this spec file has no
such heading for the linter to resolve.)

Support-matrix sentence becomes “…, Factory Droid, Pi, and Hermes Agent.” Both ship in the
same change (structural-verification decision below).

### 6. Release plumbing

- Bump `.claude-plugin/plugin.json` 0.6.0 → 0.7.0 and sync the other five JSON manifests;
  `plugin.yaml` is born at 0.7.0; add the CHANGELOG 0.7.0 entry (Added — Hermes Agent
  support); run `./scripts/build.sh` to restamp (the stamp embeds the version, and
  `.claude-plugin/plugin.json` is inside the hash scope).
- `scripts/check_release_integrity.py`: add `plugin.yaml` to `VERSION_MANIFESTS`; the reader
  branches on suffix — JSON via `json.load` as today, `.yaml` via a stdlib regex on the
  `version:` line (Python's stdlib has no YAML parser, and dev tooling stays stdlib-only).
- `plugin.yaml` and `__init__.py` stay **out** of the build-stamp hash scope and out of
  `_is_runtime_surface` — matching the precedent that `.opencode/plugins/job-search.js` and
  four of the six version manifests sit outside both.

### 7. Docs and tests

- `ARCHITECTURE.md` → Distribution: add `plugin.yaml` + `__init__.py` (Hermes) to the
  per-harness manifest list.
- New `tests/test_hermes_plugin.py`, mirroring `tests/test_opencode_plugin.py`: manifest
  assertions (`manifest_version == 1`, `name == "job-search"`, `kind == "standalone"`,
  version equals `.claude-plugin/plugin.json`); a stub-`ctx` load of `__init__.py` via
  `importlib` asserting exactly five `register_skill` calls with existing SKILL.md paths and
  no other `ctx` method touched; tamper cases in a temp copy (drop one skill directory; drop
  `shared/references/`) → an error naming the missing path.
- Extend `tests/test_release_integrity.py` to cover the YAML manifest branch (in-sync passes;
  a drifted `plugin.yaml` version fails).
- Gates before merge: `python3 scripts/doc_lint.py --root .` · `python3 -m pytest -q` ·
  `python3 scripts/check_release_integrity.py --check-version-sync --check-version-bump
  --base main` · a clean regenerated build stamp.
- Claims audit (an exec-plan step): every `hermes` command, config key, path, and behavior
  claim in `INSTALL_FOR_HERMES.md` and `after-install.md` traces to a citation in the fact
  table above, or to a fresh citation gathered at the same pin.

## Build-time constraints (the adapter stays this small)

`__init__.py` never edits Hermes config. The adapter declares and registers no tools, hooks,
commands, runtime state, workspace setup, or agent-data setup. No per-skill copies, and no
Hermes-specific instructions inside `skills/` or `shared/` — the skills already tell the host
agent to use its own file, shell, question, delegation, and scheduling capabilities.
`skills/`, `shared/`, and `templates/` are untouched: Hermes accepts the existing SKILL.md
frontmatter as-is (fact 10) and the `../../` references resolve in place (Approach above).

## Error handling summary

| Failure | Behavior | Where the user sees it |
|---|---|---|
| Incomplete install (missing skill or shared dir) | `__init__.py` raises, naming every missing path + the force-reinstall recovery | `/plugins` in-session; `HERMES_PLUGINS_DEBUG=1` stderr/log; Step 5 layer 5 |
| hermes or git missing; profile unresolvable | guide stops and explains | the install conversation |
| Local changes in the installed repo | update refused by `git pull --ff-only`; guide shows git's message and changes nothing | the install conversation |
| Local skill-name collision | guide names the conflicting path, deletes nothing, reports discovery blocked for that name | the install conversation + final report |
| `external_dirs` entry pointing at a missing dir | silently skipped by Hermes at scan time | caught by Step 4 `test -d` and Step 5 layer 4 |

## Decisions record

- Base: new branch `feat/hermes-plugin-install` off main; `feat/hermes-native-host` recorded
  as superseded and left untouched (user, 2026-07-23).
- README support-matrix gate: structural verification — green repo gates plus source-cited
  guide claims, the same bar as the six structurally-verified hosts (user, 2026-07-23).
- Version bumps to 0.7.0 in this branch (user, 2026-07-23).
- `plugin.yaml` is version-sync-checked but not hashed (approved).
- `register_skill` uses default descriptions — no frontmatter duplication (approved).
- `/new` replaces `/reset` everywhere — there is no `/reset` (evidence-forced; approved).
- Load proof via `HERMES_PLUGINS_DEBUG=1 hermes -z …`, with `/plugins` as the named
  alternative (approved).
- Removal also cleans `plugins.enabled`/`plugins.disabled` (evidence-forced; approved).
- The guide's finish step carries **no prohibition list**: the draft's four “do not” lines
  (live API call, API-key ask, `~/.job-search` creation, schedule creation) are removed —
  the installing agent legitimately does those things later through onboarding. The boundary
  is stated positively instead: onboarding in the next session handles agent-data setup, the
  workspace, and any schedule (user, 2026-07-23).

## Out of scope

Live end-to-end proof on a real Hermes install — Hermes is not run on the development
machine; the user may live-verify later and adjust the guide. Changes to skills, shared
references, mechanics scripts, or templates. Hermes cron/scheduling integration — the skills'
host-neutral scheduling procedures already cover scheduling at runtime.
