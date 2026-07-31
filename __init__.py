"""Hermes Agent plugin adapter for Job Search.

Hermes imports this file when the enabled plugin loads (once per process) and
calls register(ctx). It verifies the installed tree is complete, then registers
the seven skills under namespaced fallback names (job-search:<skill>). Bare-name
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
    "job-search-runbook",
    "agent-data-reference",
)

REQUIRED_DIRS = (
    "skills/job-search/templates",
    "skills/job-search/scripts",
    "skills/job-search-run/templates",
    "skills/job-search-run/scripts",
    "skills/job-preference-interview/templates",
    "skills/job-search-runbook/scripts",
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
