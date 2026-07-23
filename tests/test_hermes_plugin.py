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
