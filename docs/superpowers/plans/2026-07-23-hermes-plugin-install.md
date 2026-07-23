# Hermes Plugin Install Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install Job Search on Hermes Agent through its plugin manager, with the five skills discoverable by their normal names after one config edit performed by the installing Hermes instance.

**Architecture:** The whole repository installs as the Hermes plugin `job-search` (`hermes plugins install agent-data/job-search --enable` clones it to `<HERMES_HOME>/plugins/job-search`). Four new root files form the adapter: `plugin.yaml` (manifest), `__init__.py` (integrity check + `job-search:<name>` fallback registrations), `after-install.md` (post-install panel), `INSTALL_FOR_HERMES.md` (agent-facing guide that adds `plugins/job-search/skills` to `skills.external_dirs` and verifies). Nothing under `skills/`, `shared/`, or `templates/` changes.

**Tech Stack:** Python 3 stdlib only (repo rule: dev tooling is stdlib-only; no PyYAML), pytest, bash, markdown.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-23-hermes-plugin-install-design.md`. Its 18-row fact table pins every Hermes behavior to `hermes-agent` v0.19.0, commit `b0358cf` (2026-07-22) with `file:line` citations. Guide text must not claim a Hermes behavior outside that table.
- Branch: `feat/hermes-plugin-install`. Commits: scoped conventional (`feat(hermes): …`, `docs(hermes): …`, `chore(release): …`).
- All authored text follows the repo `CLAUDE.md` rules: name the thing itself (never an abstraction for a concrete thing), no idioms, no personification, and never state a measurable fact without the command that measured it.
- Agent-facing guide copy states boundaries by ownership ("onboarding in the next session handles X"), never as "do not X" prohibition lists (user decision, 2026-07-23).
- `__init__.py` never edits Hermes config; the adapter registers no tools, hooks, or commands.
- End state: version `0.7.0` in all seven version manifests (six JSON + `plugin.yaml`); until Task 6, everything stays at `0.6.0`.
- Gates that must be green at the end (Task 6): `python3 scripts/doc_lint.py --root .` · `python3 -m pytest -q` · `python3 scripts/check_release_integrity.py --root . --check-version-sync --check-version-bump --base main` · `git status --porcelain` empty after `./scripts/build.sh`.
- Do not push and do not merge — after execution, the merge decision goes through superpowers:finishing-a-development-branch with the user.
- `INSTALL_FOR_HERMES.md` and `after-install.md` sit at the repo root, which `scripts/doc_lint.py` does not scan (it scans `AGENTS.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `docs/**`). This plan file itself IS scanned: it contains no markdown links on purpose.

---

### Task 1: `plugin.yaml` + manifest tests

**Files:**
- Create: `plugin.yaml`
- Test: `tests/test_hermes_plugin.py` (new file, first half)

**Interfaces:**
- Produces: `plugin.yaml` at the repo root with top-level `version: "x.y.z"` line readable by regex `^version:` (Task 3's checker and Task 6's bump rely on this exact shape); `tests/test_hermes_plugin.py` with `ROOT`, `SKILLS`, `_manifest_value()` reused by Task 2's tests in the same file.

- [ ] **Step 1: Write the failing manifest tests**

Create `tests/test_hermes_plugin.py`:

```python
"""Hermes plugin adapter checks: manifest shape and __init__.py registration."""

import importlib.util
import json
import pathlib
import re
import shutil

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "plugin.yaml"
ADAPTER = ROOT / "__init__.py"

SKILLS = (
    "job-search",
    "job-search-run",
    "job-search-agent",
    "job-preference-interview",
    "evaluate-job-fit",
)


def _manifest_text():
    return MANIFEST.read_text(encoding="utf-8")


def _manifest_value(key):
    m = re.search(rf'^{key}:\s*["\']?([^"\'\n#]+?)["\']?\s*$', _manifest_text(), re.MULTILINE)
    assert m, f"plugin.yaml has no top-level '{key}:' line"
    return m.group(1).strip()


def test_manifest_fields():
    assert _manifest_value("manifest_version") == "1"
    assert _manifest_value("name") == "job-search"
    assert _manifest_value("kind") == "standalone"
    assert _manifest_value("description")


def test_manifest_version_matches_primary_manifest():
    primary = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert _manifest_value("version") == primary["version"]


def test_manifest_declares_no_env_or_tools():
    text = _manifest_text()
    assert "requires_env" not in text
    assert "provides_tools" not in text
    assert "provides_hooks" not in text
```

Why these assertions: `name: job-search` pins the install directory (spec fact 2 — the manifest name beats the repo name); `manifest_version: 1` is the installer's ceiling (fact 6); `requires_env` must stay absent because onboarding must work unauthenticated and the installer prompts interactively for every listed variable (spec §1).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_hermes_plugin.py -q`
Expected: 3 failed — each with `FileNotFoundError` (no `plugin.yaml`).

- [ ] **Step 3: Create `plugin.yaml`**

Exactly this content (version stays `0.6.0` until Task 6 bumps every manifest together):

```yaml
manifest_version: 1
name: job-search
version: "0.6.0"
description: A private, local-first job-search assistant — five skills that find postings, judge them against your prose preferences (no scores), and write digests on a schedule you control.
kind: standalone
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_hermes_plugin.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add plugin.yaml tests/test_hermes_plugin.py
git commit -m "feat(hermes): add plugin.yaml manifest"
```

---

### Task 2: `__init__.py` adapter + registration tests

**Files:**
- Create: `__init__.py`
- Test: `tests/test_hermes_plugin.py` (append to Task 1's file)

**Interfaces:**
- Consumes: `ROOT`, `SKILLS`, `ADAPTER` from Task 1's test module.
- Produces: root `__init__.py` exposing `register(ctx)` (Hermes's entry point, spec fact 7), module constants `REPO_ROOT: Path` and `SKILLS: tuple[str, ...]`. `ctx.register_skill(name, path)` is the only ctx method it may call (signature per spec fact 8: `register_skill(name: str, path: Path, description: str = "")`).

- [ ] **Step 1: Write the failing adapter tests**

Append to `tests/test_hermes_plugin.py`:

```python
class StubCtx:
    """Records register_skill calls; any other ctx attribute access fails the test."""

    def __init__(self):
        self.skills = []

    def register_skill(self, name, path, description=""):
        self.skills.append((name, pathlib.Path(path)))

    def __getattr__(self, attr):
        raise AssertionError(f"adapter touched unexpected ctx attribute: {attr}")


def _load_adapter(path):
    spec = importlib.util.spec_from_file_location("job_search_hermes_adapter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_tree(tmp_path):
    """A minimal complete install: the real adapter + empty SKILL.mds + required dirs."""
    root = tmp_path / "job-search"
    for name in SKILLS:
        (root / "skills" / name).mkdir(parents=True)
        (root / "skills" / name / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    for rel in ("shared/references", "shared/scripts/mechanics", "templates"):
        (root / rel).mkdir(parents=True)
    shutil.copy2(ADAPTER, root / "__init__.py")
    return root


def test_register_registers_exactly_the_five_skills():
    ctx = StubCtx()
    _load_adapter(ADAPTER).register(ctx)
    assert [name for name, _ in ctx.skills] == list(SKILLS)
    for name, path in ctx.skills:
        assert path == ROOT / "skills" / name / "SKILL.md"
        assert path.is_file()


def test_missing_skill_dir_fails_naming_it(tmp_path):
    root = _synthetic_tree(tmp_path)
    shutil.rmtree(root / "skills" / "evaluate-job-fit")
    with pytest.raises(RuntimeError, match=r"skills/evaluate-job-fit/SKILL\.md"):
        _load_adapter(root / "__init__.py").register(StubCtx())


def test_missing_shared_references_fails_naming_it(tmp_path):
    root = _synthetic_tree(tmp_path)
    shutil.rmtree(root / "shared" / "references")
    with pytest.raises(RuntimeError, match=r"shared/references"):
        _load_adapter(root / "__init__.py").register(StubCtx())


def test_error_names_the_force_reinstall_recovery(tmp_path):
    root = _synthetic_tree(tmp_path)
    shutil.rmtree(root / "templates")
    with pytest.raises(RuntimeError, match=r"hermes plugins install agent-data/job-search --force"):
        _load_adapter(root / "__init__.py").register(StubCtx())
```

Note on `StubCtx.__getattr__`: Python calls `__getattr__` only for attributes not found normally, so `register_skill` and `skills` resolve while any other method access raises — that is the "no other ctx method touched" check.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_hermes_plugin.py -q`
Expected: 3 passed (Task 1), 4 failed — `FileNotFoundError` loading `__init__.py`.

- [ ] **Step 3: Create `__init__.py`**

Exactly this content:

```python
"""Hermes Agent plugin adapter for Job Search.

Hermes imports this file when the enabled plugin loads (once per process) and
calls register(ctx). It verifies the installed tree is complete, then registers
the five skills under namespaced fallback names (job-search:<skill>). Bare-name
discovery does not come from here: the skills.external_dirs entry documented in
INSTALL_FOR_HERMES.md provides it, because plugin-registered skills never enter
Hermes's available-skills list.

Dev note: this adapter is Hermes-only and inert everywhere else. It must stay
stdlib-only, must never edit Hermes config, and must never register tools,
hooks, or commands.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

SKILLS = (
    "job-search",
    "job-search-run",
    "job-search-agent",
    "job-preference-interview",
    "evaluate-job-fit",
)

REQUIRED_DIRS = (
    "shared/references",
    "shared/scripts/mechanics",
    "templates",
)


def register(ctx):
    missing = []
    for name in SKILLS:
        if not (REPO_ROOT / "skills" / name / "SKILL.md").is_file():
            missing.append(f"skills/{name}/SKILL.md")
    for rel in REQUIRED_DIRS:
        if not (REPO_ROOT / rel).is_dir():
            missing.append(rel + "/")
    if missing:
        raise RuntimeError(
            "job-search plugin install is incomplete — missing: "
            + ", ".join(missing)
            + ". Reinstall with: hermes plugins install agent-data/job-search --force "
            "(see INSTALL_FOR_HERMES.md in the plugin directory)."
        )
    for name in SKILLS:
        ctx.register_skill(name, REPO_ROOT / "skills" / name / "SKILL.md")
```

The explicit `SKILLS` tuple is the point: an incomplete release fails with every missing path named, instead of silently registering whatever exists (spec §2).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_hermes_plugin.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add __init__.py tests/test_hermes_plugin.py
git commit -m "feat(hermes): add __init__.py adapter with integrity check and fallback skill registration"
```

---

### Task 3: release-integrity version sync for `plugin.yaml`

**Files:**
- Modify: `scripts/check_release_integrity.py:13-21` (VERSION_MANIFESTS) and `:61-77` (`_manifest_versions`), adding one helper + one regex
- Modify: `tests/test_release_integrity.py:23-29` (`seed_manifests`), `:74-79` and `:118-121` (the two inline manifest-bump blocks), plus two new tests

**Interfaces:**
- Consumes: `plugin.yaml` from Task 1 (top-level `version: "x.y.z"` line).
- Produces: `_read_manifest_version(path) -> (version | None, error | None)` inside `check_release_integrity.py`; `write_yaml_manifest(path, version)` helper in the test module. Every entry in `VERSION_MANIFESTS` is REQUIRED to exist — that is existing behavior (a missing JSON manifest already fails the sync check), which is why the seeded tmp repos must now include `plugin.yaml`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_release_integrity.py`, add after `seed_manifests` (keep `seed_manifests` unchanged for this step):

```python
def write_yaml_manifest(path, version):
    path.write_text(
        'manifest_version: 1\nname: job-search\nversion: "%s"\nkind: standalone\n' % version
    )


def test_yaml_manifest_version_sync_fails_on_mismatch(tmp_path):
    seed_manifests(tmp_path, "1.2.3")
    write_yaml_manifest(tmp_path / "plugin.yaml", "1.2.4")
    r = run_check(tmp_path, "--check-version-sync")
    assert r.returncode == 1
    assert "plugin.yaml" in r.stdout
    assert "1.2.4" in r.stdout


def test_yaml_manifest_missing_version_line_fails(tmp_path):
    seed_manifests(tmp_path, "1.2.3")
    (tmp_path / "plugin.yaml").write_text("manifest_version: 1\nname: job-search\n")
    r = run_check(tmp_path, "--check-version-sync")
    assert r.returncode == 1
    assert "plugin.yaml" in r.stdout
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_release_integrity.py -q`
Expected: the two new tests FAIL (the checker does not read `plugin.yaml` yet, so both return exit 0); the pre-existing tests still pass.

- [ ] **Step 3: Modify `scripts/check_release_integrity.py`**

Add `plugin.yaml` as the last `VERSION_MANIFESTS` entry:

```python
VERSION_MANIFESTS = (
    pathlib.Path(".claude-plugin/plugin.json"),
    pathlib.Path(".codex-plugin/plugin.json"),
    pathlib.Path(".cursor-plugin/plugin.json"),
    pathlib.Path(".factory-plugin/plugin.json"),
    pathlib.Path("gemini-extension.json"),
    pathlib.Path("package.json"),
    pathlib.Path("plugin.yaml"),
)
```

Add directly below `_read_json_at_revision` (module has `import re` already):

```python
_YAML_VERSION_RE = re.compile(r"""^version:[ \t]*["']?([^"'\s#]+)["']?[ \t]*$""", re.MULTILINE)


def _read_manifest_version(path):
    """Return (version, error) from a JSON manifest or a top-level YAML version line.

    Stdlib-only on purpose: Python ships no YAML parser, so the Hermes manifest's
    version is read as a line, not parsed as YAML.
    """
    if path.suffix in (".yaml", ".yml"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            return None, f"{_rel(path)}: cannot read ({e})"
        match = _YAML_VERSION_RE.search(text)
        if not match:
            return None, f"{_rel(path)}: missing top-level version line"
        return match.group(1), None
    data, err = _read_json_file(path)
    if err:
        return None, err
    return str(data.get("version", "")).strip(), None
```

Replace the body of `_manifest_versions` so both formats go through the helper (the empty/semver checks stay as they are):

```python
def _manifest_versions(root):
    versions = {}
    hits = []
    for rel in VERSION_MANIFESTS:
        version, err = _read_manifest_version(root / rel)
        if err:
            hits.append(err)
            continue
        if not version:
            hits.append(f"{rel.as_posix()}: missing non-empty version")
            continue
        if _version_tuple(version) is None:
            hits.append(f"{rel.as_posix()}: version '{version}' is not semver x.y.z")
            continue
        versions[rel] = version
    return versions, hits
```

- [ ] **Step 4: Update the seeded tmp repos (required — a missing manifest fails the sync check)**

In `tests/test_release_integrity.py`:

1. `seed_manifests` gains one line at the end:

```python
    write_yaml_manifest(root / "plugin.yaml", version)
```

(`write_yaml_manifest` may sit below `seed_manifests` in the file — the call resolves when
`seed_manifests` runs, not when it is defined.)

2. In `test_runtime_surface_change_requires_claude_version_bump`, after the six `write_json(... "1.2.4")` lines add:

```python
    write_yaml_manifest(tmp_path / "plugin.yaml", "1.2.4")
```

3. In `test_shared_scripts_change_is_runtime_surface_requiring_version_bump`, after the `for manifest in (...)` bump loop add:

```python
    write_yaml_manifest(tmp_path / "plugin.yaml", "1.2.4")
```

- [ ] **Step 5: Run the module, then the whole suite**

Run: `python3 -m pytest tests/test_release_integrity.py -q`
Expected: all pass (7 pre-existing + 2 new = `9 passed`).

Run: `python3 scripts/check_release_integrity.py --root . --check-version-sync`
Expected: `Release integrity: version sync clean; version bump clean.` (repo is at 0.6.0 everywhere, `plugin.yaml` included since Task 1).

- [ ] **Step 6: Commit**

```bash
git add scripts/check_release_integrity.py tests/test_release_integrity.py
git commit -m "feat(release): version-sync the Hermes plugin.yaml manifest"
```

---

### Task 4: `after-install.md` + `INSTALL_FOR_HERMES.md`

**Files:**
- Create: `after-install.md`
- Create: `INSTALL_FOR_HERMES.md`

**Interfaces:**
- Consumes: nothing from earlier tasks at runtime; the guide's file checks name `plugin.yaml` and `__init__.py` from Tasks 1–2.
- Produces: the two agent-facing documents. `after-install.md` points at `INSTALL_FOR_HERMES.md` by exact filename; Task 5's README section points at the raw-URL of `INSTALL_FOR_HERMES.md`.

- [ ] **Step 1: Create `after-install.md`**

Exactly this content (Hermes renders it in a panel right after install — spec fact 5; no fences, no links, because it displays inside a Rich markdown panel):

```markdown
# Job Search installed — one step remains

Hermes installed the complete Job Search repository into this directory.

**The five skills are not yet available by their normal names.** The Hermes
instance running this install must add this plugin's `skills/` directory to the
active profile's `skills.external_dirs`, then verify discovery. The remaining
steps are in `INSTALL_FOR_HERMES.md`, in this directory.

Hermes builds its available-skills list when a session starts, so the skills
appear only in a session started after that configuration step (`/new`).

Installation is complete only after the verification steps in
`INSTALL_FOR_HERMES.md` pass.
```

- [ ] **Step 2: Create `INSTALL_FOR_HERMES.md`**

Exactly this content:

````markdown
# Install Job Search on Hermes Agent

This guide is written for the Hermes Agent instance performing the installation.
Read the whole file before changing anything, then work the steps in order. Each
step names its commands, the expected result, and when to stop.

Verified against hermes-agent v0.19.0 (commit `b0358cf`, 2026-07-22). If a
command below behaves differently on this machine, say so in your report
instead of improvising around it.

What this installs: the complete Job Search repository as the Hermes plugin
`job-search`, with its five skills available by their normal names —
`job-search`, `job-search-run`, `job-search-agent`, `job-preference-interview`,
`evaluate-job-fit`. The skills read `shared/references/`,
`shared/scripts/mechanics/`, and `templates/` from the installed repository, so
the repository must stay intact: install it whole through the plugin manager,
never as five separate skills.

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
    five `skills/<name>/SKILL.md` files, `shared/references/`,
    `shared/scripts/mechanics/`, and `templates/` → healthy install; go to
    Step 3 and use the update command.
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
      skills/evaluate-job-fit/SKILL.md
   ls -d shared/references shared/scripts/mechanics templates
   ```

   Every listed path must exist.
3. **Config verified.** The two Step 4 checks passed and the entry appears
   exactly once.
4. **Bare-name discovery.** `hermes skills list` (a fresh Hermes process)
   lists all five skills by their bare names. This check proves the
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
6. **References resolve in place.**

   ```bash
   test -f "$HERMES_HOME/plugins/job-search/skills/job-search/../../shared/references/internals.md" && echo refs-ok
   test -x "$HERMES_HOME/plugins/job-search/shared/scripts/mechanics/workspace-discovery.sh" && echo scripts-ok
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
- whether all five bare skill names were found (check 4);
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
   form, and any `~`/`${VAR}` spelling of the same directory. Preserve every
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
````

- [ ] **Step 3: Claims audit — trace every Hermes claim to the spec fact table**

Open the spec (`docs/superpowers/specs/2026-07-23-hermes-plugin-install-design.md`, "What Hermes does" table) and confirm each guide claim maps to its fact row. The complete mapping (fix the guide, not the mapping, if one fails):

| Guide claim | Spec fact |
|---|---|
| `hermes config path` prints the active config; HERMES_HOME = its parent; `--profile` → `<root>/profiles/<name>` | 12 |
| Install shorthand `agent-data/job-search`; destination `$HERMES_HOME/plugins/job-search` (manifest name) | 1, 2 |
| `--enable` needed; non-interactive install without it lands disabled | 3 |
| `--force` deletes + re-clones; update = `git pull --ff-only`, refuses on local changes | 13 |
| after-install panel behavior (why after-install.md exists) | 5 |
| Plugin-registered skills carry only namespaced names, absent from the available-skills list | 8 |
| Relative `external_dirs` entry resolves against HERMES_HOME; `~`/`${VAR}` expand; missing dir silently skipped | 9 |
| Local `$HERMES_HOME/skills/<name>` wins collisions | 11 |
| `hermes plugins list` proves discovery/state, not load | 15 |
| Available-skills list built at session start; `/new` is the reset (no `/reset`) | 16 |
| `hermes skills list` = fresh-process bare-name listing incl. external dirs | 17 |
| `hermes -z` oneshot = fresh process that imports enabled plugins | 18 |
| Load-failure log line `Failed to load plugin 'job-search'` | 7 |
| `hermes plugins remove` leaves `plugins.enabled`/`plugins.disabled` entries | 14 |
| `/plugins` (in-session) shows per-plugin load state | 15 |

Also re-read both new files once against the repo `CLAUDE.md` writing rules
(concrete nouns, no idioms, no prohibition lists — boundaries stated by
ownership).

- [ ] **Step 4: Confirm doc_lint ignores root guides and nothing else breaks**

Run: `python3 scripts/doc_lint.py --root .`
Expected: `Doc lint: clean.` (root-level markdown outside `AGENTS.md`/`CLAUDE.md`/`ARCHITECTURE.md` is not scanned; this confirms no accidental docs/** damage).

- [ ] **Step 5: Commit**

```bash
git add after-install.md INSTALL_FOR_HERMES.md
git commit -m "docs(hermes): add agent-facing install guide and after-install note"
```

---

### Task 5: README section + ARCHITECTURE distribution list

**Files:**
- Modify: `README.md:80` (support matrix sentence) and `README.md:165-169` (insert section after Pi)
- Modify: `ARCHITECTURE.md:132-134` (Distribution manifest list)

**Interfaces:**
- Consumes: `INSTALL_FOR_HERMES.md` from Task 4 (the raw URL target).
- Produces: the user-facing install entry point. No code interfaces.

- [ ] **Step 1: Edit the support matrix sentence**

In `README.md`, replace:

```text
Job Search is compatible with Claude Code, Codex, Cursor, opencode, Gemini CLI, GitHub Copilot CLI, Factory Droid, and Pi.
```

with:

```text
Job Search is compatible with Claude Code, Codex, Cursor, opencode, Gemini CLI, GitHub Copilot CLI, Factory Droid, Pi, and Hermes Agent.
```

- [ ] **Step 2: Insert the Hermes Agent install section**

In `README.md`, directly after the Pi section's last line
(`For an editable local install, run \`pi -e /path/to/job-search\`.`) and
before `## For contributors`, insert:

````markdown

### Hermes Agent

Copy and paste the following into a new Hermes Agent session:

```text
Retrieve and follow the installation instructions at:
https://raw.githubusercontent.com/agent-data/job-search/main/INSTALL_FOR_HERMES.md
```

After installation, start a new Hermes Agent session and use the Quickstart sentence above.
````

(The closing line is plain text on purpose — it matches the approved README flow, and the
Installation intro two paragraphs up already carries the linked Quickstart pointer.)

- [ ] **Step 3: Extend the ARCHITECTURE distribution list**

In `ARCHITECTURE.md`, the Distribution paragraph currently reads (wrapped
across lines — copy the exact bytes from the file when editing):

```text
**Distribution.** One `skills/` tree, read in place, ships to every harness via a per-harness manifest —
`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`, `.factory-plugin/`, `gemini-extension.json`,
`package.json`.
```

Change the manifest list so it ends:

```text
`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`, `.factory-plugin/`, `gemini-extension.json`,
`package.json`, and the root `plugin.yaml` + `__init__.py` (Hermes Agent).
```

- [ ] **Step 4: Confirm no other live doc enumerates the supported hosts**

Run: `grep -rn "Factory Droid" --include="*.md" . 2>/dev/null | grep -v docs-private | grep -v node_modules | grep -v ".opencode"`
Expected: hits only in `README.md` (edited above), `docs/design-docs/multi-harness-portability.md` (historical dossier — leave as-is), `docs/exec-plans/completed/` (historical — leave as-is), and `docs/superpowers/` (spec + this plan). If any other live doc lists the hosts, update it the same way as the README sentence.

- [ ] **Step 5: Run doc_lint and commit**

Run: `python3 scripts/doc_lint.py --root .`
Expected: `Doc lint: clean.`

```bash
git add README.md ARCHITECTURE.md
git commit -m "docs(hermes): README install section + support matrix + distribution list"
```

---

### Task 6: version 0.7.0, CHANGELOG, stamp, full gates

**Files:**
- Modify: `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.factory-plugin/plugin.json`, `gemini-extension.json`, `package.json`, `plugin.yaml` (version `0.6.0` → `0.7.0` in each)
- Modify: `CHANGELOG.md` (new 0.7.0 entry at the top of the release list)
- Regenerate: `shared/references/build-stamp.md` (via `./scripts/build.sh`)

**Interfaces:**
- Consumes: everything; this is release prep. All seven manifests must end at the same version or Task 3's sync check fails.

- [ ] **Step 1: Bump the seven manifests**

In each of the six JSON manifests, change `"version": "0.6.0"` to
`"version": "0.7.0"` (one occurrence per file). In `plugin.yaml`, change
`version: "0.6.0"` to `version: "0.7.0"`.

Verify: `grep -H '"version"' .claude-plugin/plugin.json .codex-plugin/plugin.json .cursor-plugin/plugin.json .factory-plugin/plugin.json gemini-extension.json package.json && grep -H '^version' plugin.yaml`
Expected: seven lines, all showing `0.7.0`.

- [ ] **Step 2: Add the CHANGELOG entry**

In `CHANGELOG.md`, insert directly above the `## [0.6.0] — 2026-07-15` line:

```markdown
## [0.7.0] — 2026-07-23

### Added
- **Hermes Agent support.** Job Search installs on Hermes Agent with
  `hermes plugins install agent-data/job-search --enable`, through a root-level Hermes adapter:
  `plugin.yaml`, `__init__.py` (verifies the installed tree, then registers the five skills under
  `job-search:<name>` fallback names), `after-install.md`, and the agent-facing
  `INSTALL_FOR_HERMES.md` guide, which makes the skills discoverable by their normal names via
  `skills.external_dirs` and verifies the install end to end. The README gains a Hermes Agent
  install section and the support matrix now lists Hermes Agent. Structurally verified; every
  guide claim is cited against hermes-agent v0.19.0 source.
- Release integrity now version-syncs the Hermes `plugin.yaml` alongside the six JSON manifests.

```

- [ ] **Step 3: Regenerate the build stamp**

Run: `./scripts/build.sh`
Expected: `build: regenerated shared/references/build-stamp.md (references are single-homed; no fan-out)`

Then: `head -8 shared/references/build-stamp.md`
Expected: a `version: 0.7.0` line (the content hash also changes because `.claude-plugin/plugin.json` is inside the hash scope).

- [ ] **Step 4: Run every gate**

```bash
python3 scripts/doc_lint.py --root .
python3 -m pytest -q
python3 scripts/check_release_integrity.py --root . --check-version-sync --check-version-bump --base main
```

Expected, in order: `Doc lint: clean.` · `612 passed` (603 on main + 7 in
`tests/test_hermes_plugin.py` + 2 new in `tests/test_release_integrity.py`) ·
`Release integrity: version sync clean; version bump clean.`

- [ ] **Step 5: Commit and confirm a clean tree**

```bash
git add .claude-plugin/plugin.json .codex-plugin/plugin.json .cursor-plugin/plugin.json \
        .factory-plugin/plugin.json gemini-extension.json package.json plugin.yaml \
        CHANGELOG.md shared/references/build-stamp.md
git commit -m "chore(release): 0.7.0 — Hermes Agent support"
git status --porcelain
```

Expected: empty `git status` output. Stop here — merge/push goes through
superpowers:finishing-a-development-branch with the user.
