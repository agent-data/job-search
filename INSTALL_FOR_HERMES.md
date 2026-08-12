# Install Job Search on Hermes Agent

This guide is written for the Hermes Agent instance performing the installation.
Read the whole file before changing anything, then work the steps in order. Each
step names its commands, the expected result, and when to stop.

Verified against hermes-agent v0.19.0 (commit `b0358cf`, 2026-07-22). If a
command below behaves differently on this machine, say so in your report
instead of improvising around it.

What this installs: the complete Job Search repository as the Hermes plugin
`job-search`, with its seven skills available by their normal names — the five
a user reaches, `job-search`, `job-search-run`, `job-search-agent`,
`job-preference-interview` and `evaluate-job-fit`, and the two that hold the
mechanics those five draw on, `job-search-runbook` and
`agent-data-reference`. The skills read each other and their own `templates/`
and `scripts/` directories from the installed repository, so the repository
must stay intact: install it whole through the plugin manager, never as seven
separate skills.

## Step 1 — Confirm the environment

1. This guide is for Hermes Agent. If you are not a Hermes Agent instance with
   shell access, stop and tell the user.
2. `command -v git` and `command -v hermes` must both print a path. If either
   is missing, stop and tell the user what is missing and that it must be
   installed first.
3. Find the active profile's config file and derive HERMES_HOME from it:

   ```bash
   CONFIG="$(hermes config path)"
   HERMES_HOME="$(dirname "$CONFIG")"
   ```

   Do not assume `~/.hermes/config.yaml`: the active profile may live under a
   profiles directory (starting Hermes with `--profile <name>` points
   HERMES_HOME at `<root>/profiles/<name>`). Work only with this config file.
   If `hermes config path` fails, stop and explain that the active profile
   could not be identified.

## Step 2 — Inspect any existing installation

```bash
hermes plugins list
test -d "$HERMES_HOME/plugins/job-search" && echo present || echo absent
```

- **absent** → continue to Step 3 and use the install command.
- **present** → check for local changes first:

  ```bash
  git -C "$HERMES_HOME/plugins/job-search" status --porcelain
  ```

  - Output empty, and the directory contains `plugin.yaml`, `__init__.py`, all
    seven `skills/<name>/SKILL.md` files, `skills/job-search/templates/`,
    `skills/job-search/scripts/`, `skills/job-search-run/templates/`,
    `skills/job-search-run/scripts/`,
    `skills/job-preference-interview/templates/`, and
    `skills/job-search-runbook/scripts/` → healthy install; go to
    Step 3 and use the update command. That is the same list `__init__.py`
    checks on load, so a tree that passes here is a tree the plugin loads.
  - Output empty but any of those files or directories is missing → the
    install is incomplete. Tell the user, then reinstall fresh:

    ```bash
    hermes plugins install agent-data/job-search --force
    ```

    `--force` deletes the plugin directory and clones it again — use it only
    in this clean-but-incomplete case.
  - Output not empty → the installed repository has local changes. Show the
    user the `git status` output, keep every file as it is, and stop: the
    user decides what happens to their changes.

A command exiting 0 is not proof of a working install — Step 5 verifies files
and discovery no matter which path ran.

## Step 3 — Install or update through Hermes

New install:

```bash
hermes plugins install agent-data/job-search --enable
```

`--enable` matters: a non-interactive install without it leaves the plugin
disabled.

Existing clean install:

```bash
hermes plugins update job-search
```

Installed but disabled (shown by `hermes plugins list`):

```bash
hermes plugins enable job-search
```

If the update command surfaces a git error (for example "Not possible to
fast-forward"), the installed repository has local changes or diverged
history: show the user git's message verbatim and stop, as in Step 2.

Clone manually only if the `hermes plugins install` command itself fails, and
say in your report that you used this recovery path:

```bash
git clone https://github.com/agent-data/job-search "$HERMES_HOME/plugins/job-search"
hermes plugins enable job-search
```

Hermes's `skills tap` / `skills install` commands install skills one at a time
without the shared repository files; the plugin route above is the supported
one for Job Search.

## Step 4 — Make the skills discoverable by their normal names

Skills registered by the plugin's own loader carry only namespaced names
(`job-search:job-search`, …) and never enter Hermes's available-skills list.
The normal names come from this config step.

Edit the config file from Step 1 (`$CONFIG`) with your file tools so that
`skills.external_dirs` contains this entry exactly once:

```yaml
skills:
  external_dirs:
    - plugins/job-search/skills
```

Requirements:

- Preserve every existing setting and every existing `external_dirs` entry;
  keep `external_dirs` a YAML list.
- Check for an equivalent entry before adding one: Hermes expands `~` and
  `${VAR}` and resolves a relative entry against HERMES_HOME, so
  `plugins/job-search/skills` and `$HERMES_HOME/plugins/job-search/skills`
  name the same directory. Never add a duplicate.
- Prefer the relative form: it resolves against whichever HERMES_HOME is
  active, so it stays correct per profile.
- Edit the file rather than using `hermes config set` for this key — that
  command takes a single KEY VALUE pair, and preserving a YAML list through
  it is unverified.

Verify the saved config:

```bash
hermes config get skills.external_dirs
test -d "$HERMES_HOME/plugins/job-search/skills" && echo dir-ok
```

`hermes config get` re-reads the file through Hermes's own parser, so a parse
error or a lost entry shows up here. The `test -d` matters: Hermes silently
skips an `external_dirs` entry whose directory does not exist.

## Step 5 — Verify the installation

Run every check. The final report states which checks ran and their results.

1. **Plugin enabled.** `hermes plugins list` shows `job-search` as enabled.
   This reads manifests and config only — it proves discovery and enabled
   state, not that the plugin's code loads.
2. **Files intact.**

   ```bash
   cd "$HERMES_HOME/plugins/job-search"
   ls plugin.yaml __init__.py after-install.md INSTALL_FOR_HERMES.md
   ls skills/job-search/SKILL.md skills/job-search-run/SKILL.md \
      skills/job-search-agent/SKILL.md skills/job-preference-interview/SKILL.md \
      skills/evaluate-job-fit/SKILL.md skills/job-search-runbook/SKILL.md \
      skills/agent-data-reference/SKILL.md
   ls -d skills/job-search/templates skills/job-search/scripts \
      skills/job-search-run/templates skills/job-search-run/scripts \
      skills/job-preference-interview/templates skills/job-search-runbook/scripts
   ```

   Every listed path must exist.
3. **Config verified.** The two Step 4 checks passed and the entry appears
   exactly once.
4. **Bare-name discovery.** `hermes skills list` (a fresh Hermes process)
   lists all seven skills by their bare names. This check proves the
   normal-name goal.
5. **Plugin loads.** Trigger a real plugin load in a fresh process and look
   for a load error:

   ```bash
   HERMES_PLUGINS_DEBUG=1 hermes -z "Reply with exactly: ok" 2>/tmp/hermes-load-check.log
   grep -q "Failed to load plugin 'job-search'" /tmp/hermes-load-check.log "$HERMES_HOME/logs/agent.log" 2>/dev/null \
     && echo LOAD-ERROR || echo load-ok
   rm -f /tmp/hermes-load-check.log
   ```

   The one-shot run makes one small model call and no Job Postings API calls.
   `load-ok` together with check 4 means the plugin loaded and registered its
   namespaced fallback skills (`job-search:<skill>`); those names never show
   in `hermes skills list`, so the absence of a load error is their evidence.
   On `LOAD-ERROR`, show the user the matching log lines — the plugin's own
   error text names what is missing and the reinstall command. The user can
   also see per-plugin load state by typing `/plugins` in their next session.
6. **References and scripts are in place.**

   ```bash
   test -f "$HERMES_HOME/plugins/job-search/skills/job-search-runbook/SKILL.md" && echo refs-ok
   test -x "$HERMES_HOME/plugins/job-search/skills/job-search-runbook/scripts/workspace-discovery.sh" && echo scripts-ok
   ```

Git having cloned the files is not the success condition — checks 4 and 5
are: Hermes loads the plugin and discovers the skills.

## Step 6 — Check for skill-name collisions

A local skill in `$HERMES_HOME/skills/` with the same name wins over an
external directory, so Hermes would load that skill instead:

```bash
for s in job-search job-search-run job-search-agent job-preference-interview evaluate-job-fit; do
  test -d "$HERMES_HOME/skills/$s" && echo "COLLISION: $HERMES_HOME/skills/$s"
done
```

On a collision: name the conflicting path in your report, keep it exactly as
it is, and tell the user Job Search installed but normal discovery for that
name stays blocked until they rename or remove their local skill. Do not
claim full success.

## Step 7 — Finish

Hermes builds its available-skills list when a session starts, so the newly
discoverable skills appear in the next session, not in this one. Tell the
user to start a new session — `/new` — and then send:

```text
Set up my job search. I'm looking for …
```

Job Search onboarding in that session handles agent-data setup, the private
workspace, and any recurring schedule.

Report to the user:

- the plugin install path (`$HERMES_HOME/plugins/job-search`);
- the config file you changed (`$CONFIG`) and what changed in it;
- whether the plugin loaded (check 5) and which verification checks ran;
- whether all seven bare skill names were found (check 4);
- any collision from Step 6;
- that a new session (`/new`) is needed before the skills appear.

## Updating

1. `git -C "$HERMES_HOME/plugins/job-search" status --porcelain` — if the
   output is not empty, show it to the user and stop; local changes are the
   user's to resolve.
2. `hermes plugins update job-search`
3. Re-run Step 5 checks 1, 3, 4, and 5.
4. Tell the user to start a new session (`/new`).

## Removing

1. `CONFIG="$(hermes config path)"`; `HERMES_HOME="$(dirname "$CONFIG")"`.
2. In `$CONFIG`, remove every `skills.external_dirs` entry that resolves to
   `$HERMES_HOME/plugins/job-search/skills` — the relative form, the absolute
   form, and any `~` or `${VAR}` form of the same directory. Preserve every
   other entry and every other setting.
3. Also remove `job-search` from `plugins.enabled` (and from
   `plugins.disabled` if present): `hermes plugins remove` deletes files only
   and leaves these entries behind.
4. `hermes plugins remove job-search`
5. `test -d "$HERMES_HOME/plugins/job-search" || echo removed`
6. Tell the user to start a new session (`/new`).

Removing the plugin leaves `~/.job-search` — the user's preferences, history,
and digests — in place. Deleting that workspace is a separate action the user
takes deliberately.
