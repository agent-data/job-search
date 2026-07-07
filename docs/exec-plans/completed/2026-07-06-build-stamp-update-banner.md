---
title: Build Stamp + Claude/Codex Update Banner
state: completed
created: 2026-07-06
completed: 2026-07-07
---

# Build Stamp + Claude/Codex Update Banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Follow the repo's execution protocol in
> [`../../PLANS.md`](../../PLANS.md): TDD, frequent scoped commits, and the per-commit doc-reviewer pass
> for substantive KB changes.
>
> **How this plan was produced.** A 2026-07-06 planning session investigated the stale installed-cache
> failure from the multi-source dogfooding pass. The user chose: remote published build stamp for update
> detection; real update affordance only for the two primary tested harnesses (Claude Code and Codex);
> and a new tech-debt item explicitly pulling back the broad unverified harness-support claim.

**Goal:** Make a running Job Search install state its concrete build identity and tell Claude/Codex users
when a newer published build is available, with an exact update command and no auto-update.

**Architecture:** Add a deterministic dev-side build-stamp generator and copy its markdown stamp into
every skill through the existing `build.sh` fan-out. Runtime skills remain markdown-only: `job-search-run`
reads the bundled stamp and writes it into run records; `job-search` reads the bundled stamp plus a cached
remote stamp and renders a non-blocking home-view banner only on Claude/Codex. CI adds release-integrity
guards so shipped runtime-content changes cannot keep the old version string.

**Tech Stack:** Bash (`scripts/build.sh`), Python 3.11 stdlib dev tooling, Markdown runtime contracts in
`shared/references/`, generated skill reference copies, pytest, `scripts/validate_platforms.py`, GitHub
Actions, skill-creator eval JSON.

---

## File Structure

- Create `scripts/build_stamp.py` — deterministic stamp generator for `shared/references/build-stamp.md`.
- Create `tests/test_build_stamp.py` — unit tests for stamp determinism and hash-scope exclusions.
- Create `scripts/check_release_integrity.py` — manifest version sync plus PR version-bump gate.
- Create `tests/test_release_integrity.py` — unit tests for manifest sync and changed-runtime-surface detection.
- Create `shared/references/update.md` — runtime update-check/cache/banner procedure.
- Modify `scripts/build.sh` — sync shared references, generate stamp, then copy stamp into every skill.
- Modify `.github/workflows/ci.yml` — run release-integrity checks.
- Modify all manifest files that carry `version` — bump `0.3.0` to `0.4.0`.
- Modify `scripts/validate_platforms.py` and `tests/test_validate_platforms.py` — enforce Claude/Codex update recipes.
- Modify `shared/references/conventions.md` and `skills/job-search-run/SKILL.md` — add build metadata to run records and summary output.
- Modify `skills/job-search/SKILL.md` and `skills/job-search/references/home.md` — load update contract and render the banner.
- Modify `skills/job-search/evals/evals.json` and `skills/job-search-run/evals/evals.json` — add acceptance expectations.
- Modify `docs/exec-plans/tech-debt-tracker.md` — add `TODO-HARNESS-SUPPORT-SCOPE`.
- Modify `docs/exec-plans/index.md` — keep this plan linked under Active now; move the entry to Completed
  when the plan is finished and archived.

## Global Constraints

- Runtime skills still ship markdown only. Python scripts are dev-side tooling and must not be required on user machines.
- Build identity is `version + content_hash`; git SHA is best-effort and may be `unknown` in installed plugin caches.
- Update checking is non-blocking. Network failure, missing `curl`, malformed remote stamp, or an unverified harness skips the banner and does not create a named job-search error.
- Only Claude/Codex get in-product update commands in this plan. Other harnesses remain documented as expected/aspirational until live verification.
- No config schema bump. Workspace `config.yaml` stays `version: 1`.
- No auto-update. The user gets a command; the agent never runs it without an explicit user request.
- Edit source references under `shared/references/`, then run `./scripts/build.sh`; do not hand-edit generated synced reference copies.

## Non-goals

- No per-harness capability-record refactor. This plan uses the existing platform adapters.
- No broad update command support for Cursor, opencode, Gemini, Copilot, Droid, or Pi.
- No remote endpoint service. The published stamp is the raw GitHub `shared/references/build-stamp.md`.
- No cryptographic signing or supply-chain attestation. The stamp is a practical staleness signal, not a security guarantee.
- No automatic plugin-manager invocation from the home view.

## Tasks

### Task 1: Deterministic Build Stamp Generator `[BLOCKS]`

**Files:**
- Create: `scripts/build_stamp.py`
- Create: `tests/test_build_stamp.py`
- Modify: `scripts/build.sh`
- Generate: `shared/references/build-stamp.md`
- Generate: `skills/*/references/build-stamp.md`

- [ ] **Step 1: Write failing build-stamp tests**

Create `tests/test_build_stamp.py`:

```python
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stamp.py"


def run_stamp(root, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
    )


def seed_runtime_tree(root):
    (root / ".claude-plugin").mkdir()
    (root / ".codex-plugin").mkdir()
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "job-search", "version": "1.2.3"}) + "\n"
    )
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "job-search", "version": "1.2.3"}) + "\n"
    )
    shared = root / "shared" / "references"
    shared.mkdir(parents=True)
    (shared / "conventions.md").write_text("# Conventions\n\nruntime contract\n")
    skill = root / "skills" / "job-search"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: job-search\ndescription: test\n---\n")
    (skill / "references" / "conventions.md").write_text("# Conventions\n\nruntime contract\n")
    evals = skill / "evals"
    evals.mkdir()
    (evals / "evals.json").write_text('{"ignored":"eval-only"}\n')


def test_stamp_output_is_deterministic(tmp_path):
    seed_runtime_tree(tmp_path)
    first = run_stamp(tmp_path)
    second = run_stamp(tmp_path)
    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert first.stdout == second.stdout
    assert "version: 1.2.3" in first.stdout
    assert "content_hash: sha256:" in first.stdout
    assert "generated_at" not in first.stdout


def test_stamp_hash_changes_for_runtime_content_but_not_evals_or_stamp(tmp_path):
    seed_runtime_tree(tmp_path)
    base = run_stamp(tmp_path).stdout

    (tmp_path / "skills" / "job-search" / "evals" / "evals.json").write_text(
        '{"ignored":"changed eval"}\n'
    )
    assert run_stamp(tmp_path).stdout == base

    (tmp_path / "shared" / "references" / "build-stamp.md").write_text(
        "# old generated stamp\ncontent_hash: sha256:aaaaaaaaaaaa\n"
    )
    (tmp_path / "skills" / "job-search" / "references" / "build-stamp.md").write_text(
        "# copied generated stamp\ncontent_hash: sha256:bbbbbbbbbbbb\n"
    )
    assert run_stamp(tmp_path).stdout == base

    (tmp_path / "skills" / "job-search" / "SKILL.md").write_text(
        "---\nname: job-search\ndescription: changed runtime\n---\n"
    )
    changed = run_stamp(tmp_path).stdout
    assert changed != base
    assert "version: 1.2.3" in changed


def test_write_mode_creates_parent_and_writes_stamp(tmp_path):
    seed_runtime_tree(tmp_path)
    out = tmp_path / "shared" / "references" / "build-stamp.md"
    r = run_stamp(tmp_path, "--write", str(out))
    assert r.returncode == 0, r.stdout + r.stderr
    text = out.read_text()
    assert text == r.stdout
    assert text.startswith("# Job Search build stamp\n")
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_build_stamp.py -q
```

Expected: fail because `scripts/build_stamp.py` does not exist.

- [ ] **Step 3: Add the build-stamp generator**

Create `scripts/build_stamp.py`:

```python
#!/usr/bin/env python3
"""Generate the deterministic Job Search build stamp.

The stamp is markdown because the shipped runtime surface is markdown-only. This script is dev-side
tooling used by scripts/build.sh and CI; users do not need Python to run the skills.
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys

PUBLISHED_STAMP_URL = (
    "https://raw.githubusercontent.com/agent-data/job-search/main/"
    "shared/references/build-stamp.md"
)
HASH_SCOPE_TEXT = (
    "skills/**, shared/references/**, .claude-plugin/plugin.json, "
    ".codex-plugin/plugin.json; excludes skills/*/evals/** and generated build-stamp.md"
)
PRIMARY_VERSION_MANIFEST = pathlib.Path(".claude-plugin/plugin.json")
EXTRA_HASH_FILES = (
    pathlib.Path(".claude-plugin/plugin.json"),
    pathlib.Path(".codex-plugin/plugin.json"),
)


def _is_generated_stamp(path):
    return path.name == "build-stamp.md"


def _is_skill_eval(path):
    parts = path.parts
    return len(parts) >= 3 and parts[0] == "skills" and "evals" in parts[2:]


def iter_hash_paths(root):
    root = pathlib.Path(root)
    candidates = []
    for base in (root / "skills", root / "shared" / "references"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if _is_generated_stamp(rel) or _is_skill_eval(rel):
                continue
            candidates.append(rel)
    for rel in EXTRA_HASH_FILES:
        if (root / rel).is_file():
            candidates.append(rel)
    return sorted(set(candidates), key=lambda p: p.as_posix())


def read_version(root):
    path = pathlib.Path(root) / PRIMARY_VERSION_MANIFEST
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise SystemExit(f"{path}: cannot read primary version manifest: {e}") from e
    except ValueError as e:
        raise SystemExit(f"{path}: invalid JSON: {e}") from e
    version = str(data.get("version", "")).strip()
    if not version:
        raise SystemExit(f"{path}: missing non-empty version")
    return version


def content_hash(root):
    root = pathlib.Path(root)
    h = hashlib.sha256()
    for rel in iter_hash_paths(root):
        h.update(rel.as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update((root / rel).read_bytes())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()[:12]


def render_stamp(root):
    version = read_version(root)
    digest = content_hash(root)
    return (
        "# Job Search build stamp\n\n"
        "This file is generated by `scripts/build_stamp.py` through `scripts/build.sh`.\n"
        "Do not edit it by hand.\n\n"
        f"version: {version}\n"
        f"content_hash: {digest}\n"
        "hash_algorithm: sha256-truncated-12\n"
        f"hash_scope: {HASH_SCOPE_TEXT}\n"
        f"published_stamp_url: {PUBLISHED_STAMP_URL}\n"
    )


def main():
    ap = argparse.ArgumentParser(description="Generate the Job Search build stamp.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--write", help="write the stamp to this path as well as stdout")
    args = ap.parse_args()

    root = pathlib.Path(args.root).resolve()
    text = render_stamp(root)
    if args.write:
        out = pathlib.Path(args.write)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Update `scripts/build.sh`**

Replace the file with:

```bash
#!/usr/bin/env bash
# build.sh — make each skill self-contained for the loose-skills install mode.
# Syncs the single-source-of-truth shared/references/*.md into every skill's references/.
# Run after editing shared/. Idempotent; resolves the repo root from this script's own
# location (cwd-independent). Nothing executable is bundled — the skills ship markdown only.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

for skill in skills/*/; do
  mkdir -p "${skill}references"
  cp shared/references/*.md "${skill}references/"
  # Per-platform adapters live one level down in shared/references/platform/; copy them too so a
  # loose-skill install carries every harness adapter and the agent self-selects its own at runtime.
  if compgen -G "shared/references/platform/*.md" > /dev/null; then
    mkdir -p "${skill}references/platform"
    cp shared/references/platform/*.md "${skill}references/platform/"
  fi
done

python3 scripts/build_stamp.py --root "$REPO" --write shared/references/build-stamp.md >/dev/null

for skill in skills/*/; do
  cp shared/references/build-stamp.md "${skill}references/build-stamp.md"
done

echo "build: synced references into $(ls -d skills/*/ | wc -l | tr -d ' ') skill(s)"
```

- [ ] **Step 5: Run the build and focused tests**

Run:

```bash
./scripts/build.sh
python3 -m pytest tests/test_build_stamp.py -q
```

Expected: tests pass, `shared/references/build-stamp.md` and every `skills/*/references/build-stamp.md`
exist.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add scripts/build_stamp.py scripts/build.sh tests/test_build_stamp.py shared/references/build-stamp.md skills/*/references/build-stamp.md
git commit -m "feat(build): generate job-search build stamp"
```

### Task 2: Version Sync + Version-Bump Release Gate `[BLOCKS]`

**Files:**
- Create: `scripts/check_release_integrity.py`
- Create: `tests/test_release_integrity.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.codex-plugin/plugin.json`
- Modify: `.cursor-plugin/plugin.json`
- Modify: `.factory-plugin/plugin.json`
- Modify: `gemini-extension.json`
- Modify: `package.json`

- [ ] **Step 1: Write failing release-integrity tests**

Create `tests/test_release_integrity.py`:

```python
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_release_integrity.py"


def run_check(root, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
    )


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def seed_manifests(root, version="1.2.3"):
    write_json(root / ".claude-plugin" / "plugin.json", {"name": "job-search", "version": version})
    write_json(root / ".codex-plugin" / "plugin.json", {"name": "job-search", "version": version})
    write_json(root / ".cursor-plugin" / "plugin.json", {"name": "job-search", "version": version})
    write_json(root / ".factory-plugin" / "plugin.json", {"name": "job-search", "version": version})
    write_json(root / "gemini-extension.json", {"name": "job-search", "version": version})
    write_json(root / "package.json", {"name": "job-search", "version": version})


def init_git_repo(root):
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)


def commit_all(root, msg):
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=root, check=True, capture_output=True)


def test_manifest_version_sync_passes(tmp_path):
    seed_manifests(tmp_path, "1.2.3")
    r = run_check(tmp_path, "--check-version-sync")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "version sync clean" in r.stdout


def test_manifest_version_sync_fails_on_mismatch(tmp_path):
    seed_manifests(tmp_path, "1.2.3")
    write_json(tmp_path / ".codex-plugin" / "plugin.json", {"name": "job-search", "version": "1.2.4"})
    r = run_check(tmp_path, "--check-version-sync")
    assert r.returncode == 1
    assert ".codex-plugin/plugin.json" in r.stdout
    assert "1.2.4" in r.stdout


def test_runtime_surface_change_requires_claude_version_bump(tmp_path):
    init_git_repo(tmp_path)
    seed_manifests(tmp_path, "1.2.3")
    p = tmp_path / "skills" / "job-search" / "SKILL.md"
    p.parent.mkdir(parents=True)
    p.write_text("---\nname: job-search\ndescription: old\n---\n")
    commit_all(tmp_path, "base")
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()

    p.write_text("---\nname: job-search\ndescription: changed\n---\n")
    r = run_check(tmp_path, "--check-version-bump", "--base", base)
    assert r.returncode == 1
    assert "runtime surface changed" in r.stdout
    assert ".claude-plugin/plugin.json" in r.stdout

    write_json(tmp_path / ".claude-plugin" / "plugin.json", {"name": "job-search", "version": "1.2.4"})
    write_json(tmp_path / ".codex-plugin" / "plugin.json", {"name": "job-search", "version": "1.2.4"})
    write_json(tmp_path / ".cursor-plugin" / "plugin.json", {"name": "job-search", "version": "1.2.4"})
    write_json(tmp_path / ".factory-plugin" / "plugin.json", {"name": "job-search", "version": "1.2.4"})
    write_json(tmp_path / "gemini-extension.json", {"name": "job-search", "version": "1.2.4"})
    write_json(tmp_path / "package.json", {"name": "job-search", "version": "1.2.4"})
    r = run_check(tmp_path, "--check-version-bump", "--base", base)
    assert r.returncode == 0, r.stdout + r.stderr


def test_eval_and_generated_stamp_changes_do_not_require_bump(tmp_path):
    init_git_repo(tmp_path)
    seed_manifests(tmp_path, "1.2.3")
    eval_path = tmp_path / "skills" / "job-search" / "evals" / "evals.json"
    eval_path.parent.mkdir(parents=True)
    eval_path.write_text("{}\n")
    stamp_path = tmp_path / "shared" / "references" / "build-stamp.md"
    stamp_path.parent.mkdir(parents=True)
    stamp_path.write_text("# stamp\n")
    commit_all(tmp_path, "base")
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()

    eval_path.write_text('{"changed": true}\n')
    stamp_path.write_text("# changed stamp\n")
    r = run_check(tmp_path, "--check-version-bump", "--base", base)
    assert r.returncode == 0, r.stdout + r.stderr
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_release_integrity.py -q
```

Expected: fail because `scripts/check_release_integrity.py` does not exist.

- [ ] **Step 3: Add the release-integrity script**

Create `scripts/check_release_integrity.py`:

```python
#!/usr/bin/env python3
"""Release integrity checks for Job Search.

Checks are stdlib-only and dev-side. They guard the exact failure from 2026-07-06: runtime content
changed while the installed plugin version stayed the same.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

VERSION_MANIFESTS = (
    pathlib.Path(".claude-plugin/plugin.json"),
    pathlib.Path(".codex-plugin/plugin.json"),
    pathlib.Path(".cursor-plugin/plugin.json"),
    pathlib.Path(".factory-plugin/plugin.json"),
    pathlib.Path("gemini-extension.json"),
    pathlib.Path("package.json"),
)
PRIMARY_MANIFEST = pathlib.Path(".claude-plugin/plugin.json")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _read_json(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def read_version(root, rel):
    path = pathlib.Path(root) / rel
    try:
        version = str(_read_json(path).get("version", "")).strip()
    except (OSError, ValueError) as e:
        return None, f"{rel}: cannot read version ({e})"
    if not version:
        return None, f"{rel}: missing non-empty version"
    if not SEMVER_RE.match(version):
        return None, f"{rel}: version '{version}' is not x.y.z semver"
    return version, None


def check_version_sync(root):
    hits = []
    primary, err = read_version(root, PRIMARY_MANIFEST)
    if err:
        return [err]
    for rel in VERSION_MANIFESTS:
        path = pathlib.Path(root) / rel
        if not path.exists():
            continue
        version, err = read_version(root, rel)
        if err:
            hits.append(err)
        elif version != primary:
            hits.append(f"{rel}: version {version} does not match {PRIMARY_MANIFEST} version {primary}")
    return hits


def changed_paths(root, base):
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise SystemExit(f"git diff against {base} failed: {detail}")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def runtime_surface_path(path):
    if path.endswith("build-stamp.md"):
        return False
    if path.startswith("skills/") and "/evals/" in path:
        return False
    return path.startswith("skills/") or path.startswith("shared/references/")


def read_version_at(root, base, rel):
    proc = subprocess.run(
        ["git", "show", f"{base}:{rel.as_posix()}"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return None
    return str(data.get("version", "")).strip() or None


def semver_tuple(v):
    return tuple(int(part) for part in v.split("."))


def check_version_bump(root, base):
    paths = changed_paths(root, base)
    runtime_changed = [p for p in paths if runtime_surface_path(p)]
    if not runtime_changed:
        return []
    old = read_version_at(root, base, PRIMARY_MANIFEST)
    new, err = read_version(root, PRIMARY_MANIFEST)
    if err:
        return [err]
    if old is None:
        return [f"{PRIMARY_MANIFEST}: could not read base version at {base}"]
    if old == new or semver_tuple(new) <= semver_tuple(old):
        return [
            "runtime surface changed without a forward version bump in "
            f"{PRIMARY_MANIFEST}: base={old}, current={new}, changed={', '.join(runtime_changed)}"
        ]
    return []


def main():
    ap = argparse.ArgumentParser(description="Check Job Search release integrity.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--check-version-sync", action="store_true")
    ap.add_argument("--check-version-bump", action="store_true")
    ap.add_argument("--base", help="base git ref/sha for --check-version-bump")
    args = ap.parse_args()

    root = pathlib.Path(args.root).resolve()
    hits = []
    if args.check_version_sync:
        hits += check_version_sync(root)
    if args.check_version_bump:
        if not args.base:
            raise SystemExit("--base is required with --check-version-bump")
        hits += check_version_bump(root, args.base)
    if not args.check_version_sync and not args.check_version_bump:
        hits += check_version_sync(root)

    if hits:
        print("Release integrity FAILED:")
        print("\n".join(hits))
        return 1
    print("Release integrity: version sync clean; version bump clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Bump all manifest versions to `0.4.0`**

Change the `"version"` field from `"0.3.0"` to `"0.4.0"` in:

```text
.claude-plugin/plugin.json
.codex-plugin/plugin.json
.cursor-plugin/plugin.json
.factory-plugin/plugin.json
gemini-extension.json
package.json
```

- [ ] **Step 5: Add CI release-integrity checks**

In `.github/workflows/ci.yml`, add this step after structural validation and before `build.sh`:

```yaml
      - name: Release integrity
        run: |
          python3 scripts/check_release_integrity.py --root . --check-version-sync
          if [ "${{ github.event_name }}" = "pull_request" ]; then
            python3 scripts/check_release_integrity.py --root . --check-version-bump --base "${{ github.event.pull_request.base.sha }}"
          fi
```

- [ ] **Step 6: Run focused and full release checks**

Run:

```bash
python3 -m pytest tests/test_release_integrity.py -q
python3 scripts/check_release_integrity.py --root . --check-version-sync
./scripts/build.sh
```

Expected: tests pass; release-integrity prints clean; generated stamps now show `version: 0.4.0`.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add scripts/check_release_integrity.py tests/test_release_integrity.py .github/workflows/ci.yml \
  .claude-plugin/plugin.json .codex-plugin/plugin.json .cursor-plugin/plugin.json \
  .factory-plugin/plugin.json gemini-extension.json package.json \
  shared/references/build-stamp.md skills/*/references/build-stamp.md
git commit -m "ci(release): require synced versions and version bumps"
```

### Task 3: Update Contract + Claude/Codex Recipes `[BLOCKS]`

**Files:**
- Create: `shared/references/update.md`
- Modify: `shared/references/platform/claude.md`
- Modify: `shared/references/platform/codex.md`
- Modify: `scripts/validate_platforms.py`
- Modify: `tests/test_validate_platforms.py`
- Generate: `skills/*/references/update.md`
- Generate: `skills/*/references/platform/claude.md`
- Generate: `skills/*/references/platform/codex.md`

- [ ] **Step 1: Add failing validator tests for primary update recipes**

Append to `tests/test_validate_platforms.py`:

```python
# ---- primary-update-recipes ----

def test_primary_update_recipes_clean_passes(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "claude.md").write_text(
        "## Packaging & install\n\n"
        "Update recipe:\n"
        "```bash\n"
        "claude plugin marketplace update agent-data\n"
        "claude plugin update job-search@agent-data\n"
        "```\n"
    )
    (p / "codex.md").write_text(
        "## Packaging & install\n\n"
        "Update recipe:\n"
        "```bash\n"
        "codex plugin marketplace upgrade agent-data\n"
        "codex plugin add job-search@agent-data\n"
        "```\n"
    )
    r = run_validate(tmp_path, "--only", "primary-update-recipes")
    assert r.returncode == 0, r.stdout + r.stderr


def test_primary_update_recipes_missing_claude_update_fails(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "claude.md").write_text("## Packaging & install\n\nno update command\n")
    (p / "codex.md").write_text(
        "## Packaging & install\n\n"
        "codex plugin marketplace upgrade agent-data\n"
        "codex plugin add job-search@agent-data\n"
    )
    r = run_validate(tmp_path, "--only", "primary-update-recipes")
    assert r.returncode == 1
    assert "claude plugin update job-search@agent-data" in r.stdout


def test_primary_update_recipes_missing_codex_upgrade_fails(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "claude.md").write_text(
        "## Packaging & install\n\n"
        "claude plugin marketplace update agent-data\n"
        "claude plugin update job-search@agent-data\n"
    )
    (p / "codex.md").write_text("## Packaging & install\n\ncodex plugin add job-search@agent-data\n")
    r = run_validate(tmp_path, "--only", "primary-update-recipes")
    assert r.returncode == 1
    assert "codex plugin marketplace upgrade agent-data" in r.stdout
```

- [ ] **Step 2: Run the focused validator tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_validate_platforms.py -q
```

Expected: fail because `primary-update-recipes` is not a known validator check.

- [ ] **Step 3: Add the validator check**

In `scripts/validate_platforms.py`, add this function before `CHECKS`:

```python
def scan_primary_update_recipes(root):
    """Claude and Codex are the primary tested harnesses. Their adapters must carry exact update
    commands for the home-view update banner. Other adapters intentionally stay out of this check
    until they are live-verified."""
    hits = []
    required = {
        "claude": (
            "claude plugin marketplace update agent-data",
            "claude plugin update job-search@agent-data",
        ),
        "codex": (
            "codex plugin marketplace upgrade agent-data",
            "codex plugin add job-search@agent-data",
        ),
    }
    for harness, needles in required.items():
        rel = os.path.join(PLATFORM_DIR, harness + ".md")
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            hits.append(f"{rel}: primary-update-recipes: adapter is missing")
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        for needle in needles:
            if needle not in text:
                hits.append(f"{rel}: primary-update-recipes: missing `{needle}`")
    return hits
```

Then add it to `CHECKS`:

```python
    "primary-update-recipes": scan_primary_update_recipes,
```

- [ ] **Step 4: Create `shared/references/update.md`**

Create `shared/references/update.md`:

```markdown
# Update check — build stamp, cache, and banner

This contract is read by the **job-search** home/onboarding view only. Headless **job-search-run**
records its own build but never checks for updates. The check is a convenience signal, not a gate:
never auto-update, never block rendering the home view, and never create an `E-*` named error from an
update-check failure.

## Local build

Read `references/build-stamp.md` and parse these literal lines:

- `version: <semver>`
- `content_hash: sha256:<12-hex>`
- `published_stamp_url: <https URL>`

If the local stamp is missing or malformed, skip the update banner. Do not guess a version from a
manifest at runtime.

## Supported hosts

Show update banners only on the primary tested plugin hosts:

- Claude Code
- Codex

For every other platform adapter, skip the update check and banner. Those adapters may still load and run,
but their update command paths are not treated as a verified product surface yet.

## Registry cache

Use the resolved registry from `internals.md` and preserve all existing keys. The optional cache object is:

```json
{
  "update_check": {
    "checked_at": "2026-07-06T12:00:00+00:00",
    "latest": {
      "version": "0.4.0",
      "content_hash": "sha256:abcdef123456",
      "published_stamp_url": "https://raw.githubusercontent.com/agent-data/job-search/main/shared/references/build-stamp.md"
    },
    "status": "ok"
  }
}
```

A cache is fresh for 24 hours. When fresh, use it and do not hit the network. When absent or stale, try one
lightweight fetch of the local stamp's `published_stamp_url`:

```bash
curl -fsSL --max-time 5 "<published_stamp_url>"
```

If `curl` is unavailable, the command fails, or the fetched stamp is malformed, keep any previous cache but
do not show a banner from stale data. The home view still renders normally.

Write a successful fresh result back to the registry with the registry whole-file write rules in
`internals.md`: read current JSON, merge only `update_check`, preserve unrelated keys, keep `version: 1`,
and write atomically.

## Comparison

Compare semantic versions as `major.minor.patch` integers.

- Remote version greater than local version -> update available.
- Remote version equal to local version and `content_hash` differs -> update available. This catches the
  exact "same version, different content" failure from the 2026-07-06 dogfooding pass.
- Remote version lower than local version -> no banner.
- Remote version equal and hash equal -> no banner.
- Any non-semver value -> no banner.

## Banner

When an update is available, render one compact line above the normal home view:

```text
Update available: Job Search <local_version> <local_hash> -> <remote_version> <remote_hash> — run:
<platform update recipe>
```

Copy the platform update recipe verbatim from the active platform's adapter → Packaging & install.
Do not reconstruct command tokens in this file. If no verified update recipe exists for the active adapter,
skip the banner.
```

- [ ] **Step 5: Add update recipes to Claude and Codex adapters**

In `shared/references/platform/claude.md`, append to `## Packaging & install`:

```markdown

### Update recipe

Show the user **verbatim** when `references/update.md` reports an update is available:

```bash
claude plugin marketplace update agent-data
claude plugin update job-search@agent-data
```

Restart Claude Code after the update so the new plugin cache is loaded.
```

In `shared/references/platform/codex.md`, append to `## Packaging & install`:

```markdown

### Update recipe

Show the user **verbatim** when `references/update.md` reports an update is available:

```bash
codex plugin marketplace upgrade agent-data
codex plugin add job-search@agent-data
```

Restart Codex after the update so the new plugin cache is loaded.
```

- [ ] **Step 6: Build and run validation**

Run:

```bash
./scripts/build.sh
python3 -m pytest tests/test_validate_platforms.py -q
python3 scripts/validate_platforms.py --root .
```

Expected: tests pass; platform validation clean; `skills/*/references/update.md` exists.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add shared/references/update.md shared/references/platform/claude.md shared/references/platform/codex.md \
  scripts/validate_platforms.py tests/test_validate_platforms.py \
  skills/*/references/update.md skills/*/references/platform/claude.md skills/*/references/platform/codex.md
git commit -m "feat(update): add Claude and Codex update recipes"
```

### Task 4: Home-View Update Banner `[BLOCKS]`

**Files:**
- Modify: `skills/job-search/SKILL.md`
- Modify: `skills/job-search/references/home.md`
- Modify: `skills/job-search/evals/evals.json`

- [ ] **Step 1: Add a failing home eval expectation**

In `skills/job-search/evals/evals.json`, add a new returning-user case after the existing returning-user
home case:

```json
{
  "id": 9,
  "scenario": "returning-user home with cached update available",
  "prompt": "PRE-SEED before invoking: run setup-onboarding.sh <tmp>; create <tmp>/.job-search from templates (cp templates/config.example.yaml -> config.yaml, templates/preferences.example.md -> preferences.md, templates/workspace.gitignore -> .gitignore, mkdir runs reports, : > jobs.jsonl); write a sample <tmp>/.job-search/reports/2026-06-05-digest.md with Run health: healthy and a counts line; write <tmp>/registry.json with version:1, active_workspace:<tmp>/.job-search, and update_check.checked_at set to the current UTC time with latest.version 9.9.9, latest.content_hash sha256:999999999999, status ok. Now invoke job-search as Claude Code (discovery reports first_run:false, source:registry). Env as in harness. Do not allow a network call; the cache is fresh.",
  "expectations": [
    "Does NOT onboard — no interview, no workspace creation, no template copy, no preferences rewrite",
    "Reads the fresh registry update_check cache and does not fetch the network",
    "Renders a compact update banner above the normal home view: Job Search <local version/hash> -> 9.9.9 sha256:999999999999",
    "The banner includes the Claude update recipe exactly: claude plugin marketplace update agent-data, then claude plugin update job-search@agent-data",
    "Still renders the normal home view below the banner: status line, latest digest summary, pipeline, quick actions",
    "NO numeric score, NO weights, NO credit/dollar math"
  ]
}
```

If the current eval IDs already include `9`, use the next unused integer and keep the JSON valid.

- [ ] **Step 2: Update `skills/job-search/SKILL.md` references**

In the final "Read and follow exactly" sentence, add `references/update.md`:

```markdown
`references/update.md` (cached update signal + Claude/Codex update banner)
```

- [ ] **Step 3: Update home gather/render behavior**

In `skills/job-search/references/home.md`, add to `## Gather` after schedule marker:

```markdown
- **Update status:** on Claude Code or Codex only, follow `references/update.md` using the bundled
  `references/build-stamp.md` and the registry `update_check` cache. The result is either
  `update_available` with the local/remote build ids and the active adapter's update recipe, or no signal.
  Any check failure means no signal; the home still renders.
```

Then add at the start of `## Render the home`:

```markdown
If `references/update.md` reports `update_available`, print this single banner line first, then the normal
home view:

```text
Update available: Job Search <local_version> <local_hash> -> <remote_version> <remote_hash> — run:
<platform update recipe>
```

Copy `<platform update recipe>` verbatim from the active platform's adapter → Packaging & install. Do not
show this banner on adapters without a verified update recipe.
```

- [ ] **Step 4: Run build and relevant checks**

Run:

```bash
./scripts/build.sh
python3 scripts/validate_platforms.py --root .
python3 scripts/doc_lint.py --root .
```

Expected: validation and doc lint pass.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add skills/job-search/SKILL.md skills/job-search/references/home.md skills/job-search/evals/evals.json \
  skills/*/references/build-stamp.md
git commit -m "feat(job-search): show Claude and Codex update banner"
```

### Task 5: Run Records + Summary Build Identity `[BLOCKS]`

**Files:**
- Modify: `shared/references/conventions.md`
- Modify: `skills/job-search-run/SKILL.md`
- Modify: `skills/job-search-run/evals/evals.json`
- Generate: `skills/*/references/conventions.md`

- [ ] **Step 1: Add failing run eval expectations**

In `skills/job-search-run/evals/evals.json`, update the happy case expectations by adding:

```json
"Writes runs/<id>.json with build.version and build.content_hash copied from references/build-stamp.md; build.git_sha is a short git sha when available, otherwise \"unknown\"",
"The terminal summary keeps five lines and appends the build id to the Run health line, e.g. Run health: healthy · Job Search 0.4.0 sha256:<hash> · git <sha|unknown>"
```

- [ ] **Step 2: Update `runs/<run_id>.json` contract**

In `shared/references/conventions.md`, change the run audit example to include `build`:

```jsonc
{ "run_id":"…", "started_at":"…", "completed_at":"…",
  "build": { "version":"0.4.0", "content_hash":"sha256:abcdef123456", "git_sha":"<short sha|unknown>" },
  "status_probe":"ok|degraded|unreachable",
  "queries":[ { "query_id":"…", "source":"<source>", "keywords":"…", "results_returned":25, "new":6, "errors":[] } ],
  "sources_searched":["linkedin","ashby"], "sources_failed":[],
  "results_summary":{ "total_results":50, "new_postings":9, "evaluated":9, "detail_read":5,
                      "relevant":6, "strong":3, "moderate":2, "weak":1 },
  "errors":[ { "stage":"get-posting", "source_id":"…", "code":"upstream_unavailable",
               "retryable":true, "attempts":3, "final":"gave_up", "request_id":"…" } ],
  "run_health":"healthy|partial|degraded|blocked" }
```

Immediately below the example, add:

```markdown
`build.version` and `build.content_hash` are copied from the bundled `references/build-stamp.md`.
`build.git_sha` is best-effort: use `git rev-parse --short HEAD` when the executing copy has a `.git`
context, else write `"unknown"`. The build object is required on every run record written by
`job-search-run`, including blocked records where a workspace exists.
```

- [ ] **Step 3: Update `job-search-run` run-health/summary instructions**

In `skills/job-search-run/SKILL.md`, add `references/build-stamp.md` to `## References`:

```markdown
- `references/build-stamp.md` — local build version + content hash to write into run records.
```

In `## Loop` step 0, before the preflight bullets, add:

```markdown
   - Read `references/build-stamp.md` and parse `version:` + `content_hash:`. Determine
     `git_sha` with `git rev-parse --short HEAD` when available; otherwise use `"unknown"`.
     Carry this `build` object into every `runs/<run_id>.json`, including blocked records.
```

In step 5, change the summary skeleton's Run health line to:

```text
Run health: <healthy | partial (<why>) | degraded (job sources flaky) | blocked> · Job Search <version> <content_hash> · git <sha|unknown>
```

In `## Run health, surfacing & exit codes`, change the minimum record sentence to:

```markdown
Every run ends by writing `runs/<run_id>.json` with at least `{"run_id","run_health",
"build","error"|null,"ts"}`.
```

- [ ] **Step 4: Build and run checks**

Run:

```bash
./scripts/build.sh
python3 scripts/doc_lint.py --root .
python3 scripts/validate_platforms.py --root .
```

Expected: checks pass; generated `skills/*/references/conventions.md` includes the build object.

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add shared/references/conventions.md skills/job-search-run/SKILL.md skills/job-search-run/evals/evals.json \
  skills/*/references/conventions.md skills/*/references/build-stamp.md
git commit -m "feat(run): record job-search build identity"
```

### Task 6: Support-Scope Debt + Docs `[TUNE]`

**Files:**
- Modify: `docs/exec-plans/tech-debt-tracker.md`
- Modify: `README.md`

- [ ] **Step 1: Add the support-scope tech-debt item**

In `docs/exec-plans/tech-debt-tracker.md`, add this under the current dogfooding-pass items:

```markdown
### P2 — broad harness support is overstated relative to live verification (`TODO-HARNESS-SUPPORT-SCOPE`)
**What:** Reframe non-Claude/Codex harnesses as "expected to work, not deeply tested" until each has a
live install/run/update verification lane. Keep Claude Code and Codex as the primary supported surfaces for
product-critical affordances such as update banners and scheduling recipes.
**Why:** The repo prematurely extended support language and installation instructions across several
harnesses, but only Claude Code and Codex have meaningful live testing. Treating every adapter as equally
supported makes future product work spend effort on unverified surfaces and can hand users commands that were
never exercised.
**Impact:** users on unverified harnesses may read aspirational install/update/schedule copy as a tested
promise; regressions on those hosts stay invisible because CI mostly checks structure, not real runtime
behavior.
**How to apply:** mark Claude/Codex as primary supported harnesses in user docs; label other adapters as
experimental/expected-to-work; require a live verification transcript before promoting any adapter to primary
or adding product-critical commands like update recipes.
**Linked tests:** none yet; future adapter-promotion work should add a manual live verification lane to
`TESTING.md`.
```

- [ ] **Step 2: Clarify README platform support**

In `README.md`, add this paragraph at the start of `## Installation`:

```markdown
Claude Code and Codex are the primary tested installs today. The other harness entries below are expected
to work from their manifests/adapters, but they have not had the same live verification depth yet; treat
them as experimental until their adapter is promoted in the tech-debt tracker.
```

- [ ] **Step 3: Run doc checks**

Run:

```bash
python3 scripts/doc_lint.py --root .
```

Expected: `Doc lint: clean.`

- [ ] **Step 4: Commit Task 6**

Run:

```bash
git add docs/exec-plans/tech-debt-tracker.md README.md
git commit -m "docs(platforms): clarify primary tested harnesses"
```

### Task 7: Full Verification + Plan Completion `[BLOCKS]`

**Files:**
- Modify: `docs/exec-plans/active/2026-07-06-build-stamp-update-banner.md`
- Modify when completing: `docs/exec-plans/index.md`

- [ ] **Step 1: Run full verification**

Run:

```bash
python3 -m pytest -q
python3 scripts/doc_lint.py --root .
python3 scripts/philosophy_guard.py --root .
python3 scripts/validate_platforms.py --root .
python3 scripts/check_release_integrity.py --root . --check-version-sync
./scripts/build.sh
test -z "$(git status --porcelain skills shared/references/build-stamp.md)" \
  || { git status --porcelain skills shared/references/build-stamp.md; exit 1; }
```

Expected:

```text
pytest: all tests pass
Doc lint: clean.
Philosophy guard: clean.
Platform validation: clean.
Release integrity: version sync clean; version bump clean.
build: synced references into 5 skill(s)
```

- [ ] **Step 2: Run focused grep checks**

Run:

```bash
rg -n "version\": \"0\\.3\\.0\"|version: 0\\.3\\.0" \
  .claude-plugin .codex-plugin .cursor-plugin .factory-plugin gemini-extension.json package.json shared skills
rg -n "claude plugin update job-search@agent-data|codex plugin add job-search@agent-data" shared/references/platform
rg -n "build-stamp.md|build\\.version|content_hash" shared/references skills/job-search-run skills/job-search
```

Expected: first command returns no matches; second shows Claude/Codex adapter recipe lines; third shows the
new build-stamp/update references.

- [ ] **Step 3: Run skill evals that cover the changed behavior**

Run the skill-creator eval harness for:

```text
skills/job-search/evals/evals.json
skills/job-search-run/evals/evals.json
```

Expected:

```text
job-search: returning-user update banner case passes with no network call
job-search-run: happy run writes build metadata and summary line
all existing cases still pass
```

- [ ] **Step 4: Update progress and decision logs**

Append task completion lines with commit SHAs to the Progress log and record any deviation from this plan in
the Decision log.

- [ ] **Step 5: Commit verification/log updates**

Run:

```bash
git add docs/exec-plans/active/2026-07-06-build-stamp-update-banner.md
git commit -m "docs(plan): log update banner verification"
```

## Done When

- [x] `python3 -m pytest -q` passes.
- [x] `python3 scripts/doc_lint.py --root .` prints `Doc lint: clean.`
- [x] `python3 scripts/philosophy_guard.py --root .` prints `Philosophy guard: clean.`
- [x] `python3 scripts/validate_platforms.py --root .` prints `Platform validation: clean.`
- [x] `python3 scripts/check_release_integrity.py --root . --check-version-sync` prints clean.
- [x] `./scripts/build.sh && test -z "$(git status --porcelain skills shared/references/build-stamp.md)"` passes.
- [x] Every manifest version is `0.4.0`.
- [x] `shared/references/build-stamp.md` and every `skills/*/references/build-stamp.md` contain the same stamp.
- [x] `job-search-run` writes build metadata to run records and prints it in the Run health summary line.
- [x] The `job-search` home view shows a cached update banner on Claude/Codex and skips the banner elsewhere.
- [x] Claude/Codex update recipes are exact and structurally validated.
- [x] `TODO-HARNESS-SUPPORT-SCOPE` exists in the tech-debt tracker.

## Self-Review

- [x] Every file named in the tasks exists now or is explicitly created by the task that first uses it.
- [x] No runtime behavior depends on Python on user machines.
- [x] The plan keeps product-critical update commands scoped to Claude/Codex.
- [x] The release gate excludes eval-only changes and generated build-stamp churn from mandatory version bumps.
- [x] The update check is non-blocking and cache-bounded.
- [x] The plan has no schema-version bump and no auto-update path.

## Progress Log

- 2026-07-06 — Plan created from the accepted design; not yet executed.
- 2026-07-07 — Task 1 complete: deterministic build-stamp generator, build fan-out, focused tests. Commit `3f99468`; review passed.
- 2026-07-07 — Task 2 complete: release-integrity script/tests, manifest `0.4.0` bump, CI gate, untracked-runtime regression. Commits `29818d7`, `1b1d05c`; review passed.
- 2026-07-07 — Task 3 complete: update contract, Claude/Codex update recipes, exact recipe validator. Commits `6dba38a`, `d184f1d`; review passed.
- 2026-07-07 — Task 4 complete: `job-search` home update-banner instructions and cached-update eval case. Commits `9f4b2ea`, `e61953e`; review passed.
- 2026-07-07 — Task 5 complete: run-record build metadata, summary build id, blocked-record build requirements, shared error wording. Commits `7e9ab4e`, `199d9df`; review passed.
- 2026-07-07 — Task 6 complete: primary-tested harness docs, support-scope debt item, unverified update recipe cleanup. Commits `6a83ef5`, `502a326`; review passed.
- 2026-07-07 — Task 7 local verification complete: `python3 -m pytest -q` → 116 passed; `doc_lint`, `philosophy_guard`, `validate_platforms`, and release-integrity clean; `./scripts/build.sh` synced 5 skills and the generated-surface porcelain check passed; grep checks matched expectations.

## Decision Log

- 2026-07-06 — **Remote stamp chosen.** A stale installed copy cannot discover a newer build from only its own bundled files, so update detection uses the raw published stamp URL and a 24-hour registry cache.
- 2026-07-06 — **Claude/Codex only for product-critical update commands.** Local help verified Claude `plugin update` and Codex marketplace `upgrade`/plugin `add`; other adapters stay out of scope until live verification.
- 2026-07-06 — **Content hash over shipped runtime surface, not evals.** Evals changing should not force a release version bump; skill/reference runtime content changing should.
- 2026-07-07 — **Release gate also checks local untracked runtime files.** CI sees committed PR files, but local verification can otherwise miss an untracked `skills/` or `shared/references/` runtime addition; `git ls-files --others --exclude-standard` is included in the dev-side check.
- 2026-07-07 — **Update recipe validation is exact and scoped.** The validator now reads `## Packaging & install` → `### Update recipe` → fenced `bash` lines, then compares the two expected command lines in order with no extras; substring checks were too weak for a runtime-copy contract.
- 2026-07-07 — **`git_sha` is best-effort and never caller-CWD-derived.** Installed plugin caches often have no `.git`; when the Job Search source root is not reliably known, write `"unknown"` rather than accidentally recording the user's project SHA.
- 2026-07-07 — **Skill-creator eval harness not run in this Codex environment.** The local `claude` binary is present, but `claude --print ...` reports `Not logged in · Please run /login`; no local skill-creator CLI exists. Verification used JSON parsing, pytest, doc lint, philosophy guard, platform validation, release-integrity, build no-op, grep checks, and per-task gpt-5.5/xhigh subagent review instead of live skill-creator eval results.
