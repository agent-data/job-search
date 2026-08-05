"""Every shipped skill is a real skill, and every runtime file lives inside one (2026-07-31).

The two shared references became skills on 2026-07-31, so `shared/` is gone: every file an agent
reads at runtime now sits inside the skill that owns it, and a sibling reaches a reference by skill
name instead of counting `../` steps. The 0.8.0 live evals measured both models mis-resolving the
old forms — sonnet read `../../shared/references/runbook.md` with one `..` too few, haiku expanded
the plugin-root token to the skill's own directory — so a SKILL.md that still carries `../../` is
the defect this shape removes.

What each test holds:
  - `shared/` does not exist, so nothing an agent reads sits outside a skill.
  - Every skill directory has a SKILL.md whose frontmatter carries a `name` matching the directory
    and a non-empty `description`, within the 1024-character frontmatter limit.
  - Both promoted references are present under the names their consumers invoke.
  - Each promoted reference's description stays inside a 200-character budget: a sibling skill
    reads it to decide whether to spend a read, and a claude.ai compatibility pass put truncation
    around there.
  - No SKILL.md contains `../../`.
  - `test_reference_resolution.py` exempts nothing: its `DEFERRED_MOVES` allowlist held these two
    references while they were a later task's to move, and is empty once they have moved.
"""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

# The two references promoted to skills. A consumer invokes each by these exact names.
PROMOTED = ("job-search-runbook", "agent-data-reference")

# The claude.ai compatibility budget for a description a sibling skill reads (research, not a
# measured cliff — the two promoted references are cheap to keep well inside it).
REFERENCE_DESCRIPTION_MAX = 200
# The skill spec's own frontmatter limit, which every skill in the pack must respect.
FRONTMATTER_MAX = 1024


def _skill_dirs():
    return sorted(p for p in SKILLS.iterdir() if p.is_dir())


def _frontmatter(skill_md):
    """The raw frontmatter block of `skill_md`, or None when the file opens without one."""
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    return text[4:end + 1]


def _field(frontmatter, key):
    """The value of `key`, with any YAML quoting stripped — a description holding a colon has to be
    quoted, and those quotes are not part of the text a host shows."""
    for line in frontmatter.splitlines():
        if line.startswith(key + ":"):
            value = line[len(key) + 1:].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            return value
    return None


def test_shared_directory_is_gone():
    """No runtime file sits outside a skill: `shared/` held the last two, and both moved."""
    assert not (ROOT / "shared").exists(), (
        "shared/ still exists; every file an agent reads belongs inside the skill that owns it")


@pytest.mark.parametrize("name", PROMOTED)
def test_promoted_reference_is_a_skill(name):
    """Both references resolve as skills under the names every consumer invokes."""
    assert (SKILLS / name / "SKILL.md").is_file(), f"skills/{name}/SKILL.md is missing"


@pytest.mark.parametrize("skill_dir", _skill_dirs(), ids=lambda p: p.name)
def test_skill_frontmatter_is_valid(skill_dir):
    skill_md = skill_dir / "SKILL.md"
    assert skill_md.is_file(), f"{skill_dir.name}: no SKILL.md"
    fm = _frontmatter(skill_md)
    assert fm is not None, f"{skill_dir.name}: SKILL.md has no --- frontmatter block"
    assert len(fm) <= FRONTMATTER_MAX, (
        f"{skill_dir.name}: frontmatter is {len(fm)} characters (limit {FRONTMATTER_MAX})")
    name = _field(fm, "name")
    assert name == skill_dir.name, (
        f"{skill_dir.name}: frontmatter name is {name!r}, which does not match the directory")
    description = _field(fm, "description")
    assert description, f"{skill_dir.name}: frontmatter has no description"


@pytest.mark.parametrize("name", PROMOTED)
def test_promoted_reference_description_stays_in_budget(name):
    fm = _frontmatter(SKILLS / name / "SKILL.md")
    assert fm is not None, f"skills/{name}/SKILL.md has no frontmatter"
    description = _field(fm, "description") or ""
    assert 0 < len(description) <= REFERENCE_DESCRIPTION_MAX, (
        f"{name}: description is {len(description)} characters "
        f"(budget {REFERENCE_DESCRIPTION_MAX})")


@pytest.mark.parametrize("skill_md", sorted(SKILLS.glob("*/SKILL.md")), ids=lambda p: p.parent.name)
def test_no_skill_counts_directory_steps_up(skill_md):
    """`../../` is the form the live evals caught both models mis-resolving."""
    text = skill_md.read_text(encoding="utf-8")
    assert "../../" not in text, (
        f"{skill_md.parent.name}/SKILL.md still points at a file by counting directory steps up; "
        f"name the skill that owns it instead")


def test_reference_resolution_exempts_nothing():
    """`DEFERRED_MOVES` held the files a later task owned. That task is this one, and it is done."""
    path = ROOT / "tests" / "test_reference_resolution.py"
    spec = importlib.util.spec_from_file_location("reference_resolution_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DEFERRED_MOVES == set(), (
        f"these files are still exempt from the computed-pointer gate: "
        f"{sorted(module.DEFERRED_MOVES)}")
