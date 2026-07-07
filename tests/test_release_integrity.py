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


def test_untracked_runtime_surface_addition_requires_version_bump(tmp_path):
    init_git_repo(tmp_path)
    seed_manifests(tmp_path, "1.2.3")
    commit_all(tmp_path, "base")
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()

    p = tmp_path / "skills" / "new-skill" / "SKILL.md"
    p.parent.mkdir(parents=True)
    p.write_text("---\nname: new-skill\ndescription: new\n---\n")

    r = run_check(tmp_path, "--check-version-bump", "--base", base)
    assert r.returncode == 1
    assert "runtime surface changed" in r.stdout
    assert "skills/new-skill/SKILL.md" in r.stdout


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


def test_ci_build_noop_check_includes_canonical_stamp():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "git status --porcelain skills shared/references/build-stamp.md" in text
    assert "git --no-pager diff --stat skills shared/references/build-stamp.md" in text
    assert "shared/references/build-stamp.md" in text
