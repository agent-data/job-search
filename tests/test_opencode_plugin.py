"""OpenCode plugin compatibility checks."""

import json
import pathlib
import shutil
import subprocess

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = ROOT / ".opencode" / "plugins" / "job-search.js"

_DRIVER = """
import * as mod from %(plugin)s;

const exports = Object.values(mod);
const plugins = exports.filter((value) => typeof value === "function");
const hooks = plugins.length === 1 ? await plugins[0]({}) : null;
const config = {};
await hooks?.config?.(config);
await hooks?.config?.(config);

console.log(JSON.stringify({
  exportCount: plugins.length,
  hasConfigHook: typeof hooks?.config === "function",
  skillsPaths: config.skills?.paths ?? [],
}));
"""


def _run_driver():
    if shutil.which("node") is None:
        pytest.skip("node not on PATH")
    driver = _DRIVER % {"plugin": json.dumps(str(PLUGIN))}
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", driver],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def test_exports_one_opencode_plugin_function():
    result = _run_driver()
    assert result["exportCount"] == 1
    assert result["hasConfigHook"] is True


def test_registers_the_bundle_skills_path_once():
    result = _run_driver()
    assert result["skillsPaths"] == [str(ROOT / "skills")]
