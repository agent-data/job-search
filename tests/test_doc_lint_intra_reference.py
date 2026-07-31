"""Intra-reference / skill-local duplication guard (doc_lint no-shared-reference-duplication, P2/T2.2).

The base rule guards only KB docs (docs/ + root) against restating a shared/references literal.
These tests cover the extension: within the REFERENCE LAYER itself — shared/references/*.md plus the
hand-authored skill-local references (skills/*/references/*.md that are NOT build-fanned copies) — a
NON-owner file that reproduces another reference's OWNED distinctive literal, without a resolving
pointer on the line, must be flagged. The owner file, a pointing line, a build-fanned copy, and
SKILL.md runbook bodies must NOT be flagged.
"""
import subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "doc_lint.py"
ONLY = ("--only", "no-shared-reference-duplication")

# The one literal a shared reference owns, and so the one the reference-layer arm can be driven with:
# the job source enum, owned by shared/references/agent-data.md. The freshness and run-health enums
# stopped being owner-enforced when the reference that held them was deleted on 2026-07-31, so the
# arms below that used them were folded into the source-enum arms.
SRC = "linkedin | ashby | greenhouse | lever"
OWNER = "shared/references/agent-data.md"


def run_lint(target):
    return subprocess.run([sys.executable, str(LINT), "--root", str(target), *ONLY],
                          capture_output=True, text=True)


def _mk(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


# --- RED: the new behavior (currently unguarded) ------------------------------------------------

def test_shared_ref_restating_another_ref_fails(tmp_path):
    # agent-data.md OWNS the source enum; a DIFFERENT shared ref reproduces it, no pointer.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}); omitted -> linkedin.\n")
    _mk(tmp_path, "shared/references/runbook.md", f"  sources: [..]  # {SRC} — pick any.\n")
    r = run_lint(tmp_path)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "job source enum" in r.stdout and "runbook.md" in r.stdout, r.stdout


def test_skill_local_original_restating_owned_literal_fails(tmp_path):
    # Any skills/*/references/*.md with no shared/references twin is a skill-local ORIGINAL and is
    # scanned. The pack ships none today, so this fixture writes one; it restates the source enum
    # with no pointer.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}).\n")
    _mk(tmp_path, "skills/job-search-agent/references/local-playbook.md", f"Sources line: {SRC}.\n")
    r = run_lint(tmp_path)
    assert r.returncode == 1 and "job source enum" in r.stdout, r.stdout + r.stderr


# --- must NOT false-positive: owner / pointer / fanned copy --------------------------------------

def test_owner_file_holding_its_own_literal_passes(tmp_path):
    # The owner carries its own literal; the only other ref merely points -> clean.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}).\n")
    _mk(tmp_path, "shared/references/runbook.md", "  sources: [..]  # the enum lives in agent-data.md\n")
    r = run_lint(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_non_owner_pointing_on_the_line_passes(tmp_path):
    # runbook.md restates the source enum BUT names its owner's filename on the same line.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}).\n")
    _mk(tmp_path, "shared/references/runbook.md", f"a query runs against {SRC} — see agent-data.md.\n")
    r = run_lint(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_shared_references_path_pointer_passes(tmp_path):
    # The base DUP_ALLOW exemption (a shared/references/... path on the line) still applies intra-layer.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}).\n")
    _mk(tmp_path, "shared/references/runbook.md",
        f"  sources: [..]  # {SRC} — defined in shared/references/agent-data.md\n")
    r = run_lint(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_build_fanned_copy_not_flagged(tmp_path):
    # skills/*/references/agent-data.md is a byte-copy of the shared source (shared file of the SAME
    # basename exists) -> a fanned copy, excluded from the scan even though it holds the enum.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}).\n")
    _mk(tmp_path, "skills/job-search/references/agent-data.md", f"`--source` ({SRC}).\n")
    r = run_lint(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_skill_md_runbook_not_scanned(tmp_path):
    # A SKILL.md runbook may restate an enum in an output-template; SKILL.md bodies are not scanned.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}).\n")
    _mk(tmp_path, "skills/job-search-run/SKILL.md", f"Digest template counts sources: {SRC}.\n")
    r = run_lint(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
