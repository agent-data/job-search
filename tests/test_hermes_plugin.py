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
