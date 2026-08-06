"""Fixtures shared by the mechanics and validator suites."""
import pytest

CONFIG = "version: 1\nqueries: []\nschedule:\n  frequency: daily\nsearch:\n  sources: [linkedin]\n"
PREFS = "---\ncreated_at: 2026-07-16T14:00:00Z\nupdated_at: 2026-07-16T14:00:00Z\n---\n\nA brief.\n"


@pytest.fixture
def tmp_workspace(tmp_path):
    """A workspace the validator passes: a valid config, a valid brief, and an empty `runs/`.

    There is no run record in it. A test that needs one writes its own, so that the record it
    asserts against is the one visible in the test.
    """
    ws = tmp_path / "workspace"
    (ws / "runs").mkdir(parents=True)
    (ws / "config.yaml").write_text(CONFIG, encoding="utf-8")
    (ws / "preferences.md").write_text(PREFS, encoding="utf-8")
    return ws
