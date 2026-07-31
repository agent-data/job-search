"""Intra-reference / skill-local duplication guard (doc_lint no-shared-reference-duplication, P2/T2.2).

The base rule guards only KB docs (docs/ + root) against restating a reference skill's literal.
These tests cover the extension: within the REFERENCE LAYER itself — the two reference skills plus
any hand-authored skill-local reference (skills/*/references/*.md) — a NON-owner file that
reproduces another reference's OWNED distinctive literal, without a resolving pointer on the line,
must be flagged. The owner file, a pointing line, and a consumer skill's SKILL.md body must NOT be
flagged.
"""
import subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "doc_lint.py"
ONLY = ("--only", "no-shared-reference-duplication")

# The one literal a reference skill owns, and so the one the reference-layer arm can be driven with:
# the job source enum, owned by skills/agent-data-reference/SKILL.md. The freshness and run-health
# enums stopped being owner-enforced when the reference that held them was deleted on 2026-07-31, so
# the arms below that used them were folded into the source-enum arms.
SRC = "linkedin | ashby | greenhouse | lever"
OWNER = "skills/agent-data-reference/SKILL.md"
OTHER_REFERENCE = "skills/job-search-runbook/SKILL.md"


def run_lint(target):
    return subprocess.run([sys.executable, str(LINT), "--root", str(target), *ONLY],
                          capture_output=True, text=True)


def _mk(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


# --- RED: the new behavior (currently unguarded) ------------------------------------------------

def test_reference_skill_restating_another_one_fails(tmp_path):
    # agent-data-reference OWNS the source enum; the OTHER reference skill reproduces it, no pointer.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}); omitted -> linkedin.\n")
    _mk(tmp_path, OTHER_REFERENCE, f"  sources: [..]  # {SRC} — pick any.\n")
    r = run_lint(tmp_path)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "job source enum" in r.stdout and "job-search-runbook" in r.stdout, r.stdout


def test_skill_local_original_restating_owned_literal_fails(tmp_path):
    # Every skills/*/references/*.md is a hand-authored ORIGINAL and is scanned. The pack ships none
    # today, so this fixture writes one; it restates the source enum with no pointer.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}).\n")
    _mk(tmp_path, "skills/job-search-agent/references/local-playbook.md", f"Sources line: {SRC}.\n")
    r = run_lint(tmp_path)
    assert r.returncode == 1 and "job source enum" in r.stdout, r.stdout + r.stderr


# --- must NOT false-positive: owner / pointer / fanned copy --------------------------------------

def test_owner_file_holding_its_own_literal_passes(tmp_path):
    # The owner carries its own literal; the only other ref merely points -> clean.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}).\n")
    _mk(tmp_path, OTHER_REFERENCE, "  sources: [..]  # the enum lives in agent-data-reference\n")
    r = run_lint(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_non_owner_pointing_on_the_line_passes(tmp_path):
    # job-search-runbook restates the source enum BUT names its owner skill on the same line.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}).\n")
    _mk(tmp_path, OTHER_REFERENCE, f"a query runs against {SRC} — see agent-data-reference.\n")
    r = run_lint(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_owner_path_pointer_passes(tmp_path):
    # The base DUP_ALLOW exemption (the owner skill's path on the line) still applies intra-layer.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}).\n")
    _mk(tmp_path, OTHER_REFERENCE,
        f"  sources: [..]  # {SRC} — defined in skills/agent-data-reference/SKILL.md\n")
    r = run_lint(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_copy_under_a_skills_references_dir_is_flagged(tmp_path):
    # The build that fanned byte-copies of the shared references into skills/*/references/ is gone,
    # and with it the exemption those copies used to get. A copy left there now is a second home for
    # the enum, which is the drift this rule exists to catch, so it must be flagged.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}).\n")
    _mk(tmp_path, "skills/job-search/references/agent-data.md", f"`--source` ({SRC}).\n")
    r = run_lint(tmp_path)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "job source enum" in r.stdout and "skills/job-search/references" in r.stdout, r.stdout


def test_a_consumer_skills_body_is_not_scanned(tmp_path):
    # A consumer skill may restate an enum in an output template; only the reference skills and
    # skills/*/references/ are scanned, so a consumer's SKILL.md body is not.
    _mk(tmp_path, OWNER, f"`--source` ({SRC}).\n")
    _mk(tmp_path, "skills/job-search-run/SKILL.md", f"Digest template counts sources: {SRC}.\n")
    r = run_lint(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
