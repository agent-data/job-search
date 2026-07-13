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
    # Shipped runtime code: the portable-shell mechanics scripts are in the hash scope (P4/T4.3).
    mech = root / "shared" / "scripts" / "mechanics"
    mech.mkdir(parents=True)
    (mech / "dedup.sh").write_text("#!/bin/sh\necho stub\n")


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

    # A mechanics-script edit is shipped runtime code, so it MUST flip the content hash (P4/T4.3).
    (tmp_path / "shared" / "scripts" / "mechanics" / "dedup.sh").write_text(
        "#!/bin/sh\necho changed\n"
    )
    changed_after_script = run_stamp(tmp_path).stdout
    assert changed_after_script != changed


def test_hash_scope_lists_shared_scripts(tmp_path):
    """The shipped mechanics scripts are in the hash scope, and the stamp says so (P4/T4.3)."""
    seed_runtime_tree(tmp_path)
    out = run_stamp(tmp_path).stdout
    assert "shared/scripts/**" in out


def test_write_mode_creates_parent_and_writes_stamp(tmp_path):
    seed_runtime_tree(tmp_path)
    out = tmp_path / "shared" / "references" / "build-stamp.md"
    r = run_stamp(tmp_path, "--write", str(out))
    assert r.returncode == 0, r.stdout + r.stderr
    text = out.read_text()
    assert text == r.stdout
    assert text.startswith("# Job Search build stamp\n")
