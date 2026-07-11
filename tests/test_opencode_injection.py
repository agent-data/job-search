"""opencode session-start injection lifecycle (AAS-PORT-08, finding #10).

The opencode plugin surfaces the pack by injecting a bootstrap message via the
`experimental.chat.messages.transform` hook. That hook fires on EVERY agent step, so the injection
must follow the AAS-PORT-08 lifecycle rather than unconditionally prepending a system message:

  - USER-role, not system (repeated system messages bloat tokens / break some models);
  - DEDUP-GUARD: a per-step/per-turn callback must not duplicate the bootstrap;
  - COMPACTION RE-INJECT: when compaction drops the bootstrap, the next transform re-adds it.

These are behavioral assertions against the real committed plugin, exercised through node (skipped
when node is absent, mirroring the validate_platforms node checks — CI without node must not fail).
This is a structural, not-live-verified proof (opencode is not installed here): it exercises the
transform function directly, not a running opencode instance.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = ROOT / ".opencode" / "plugins" / "job-search.js"

# Node driver: import the real plugin, run its transform through the three lifecycle scenarios, and
# emit the results as JSON on stdout for the Python assertions below.
_DRIVER = """
import plugin from %(plugin)s;
const t = plugin.experimental.chat.messages.transform;
const MARK = "You are running inside opencode.";
const countBootstraps = (msgs) =>
  msgs.filter((m) => m && typeof m.content === "string" && m.content.includes(MARK)).length;

// 1. fresh conversation
const fresh = t([{ role: "user", content: "hello" }]);
// 2. per-step callback re-runs the transform on its own output (the OpenCode double-fire trap)
const rerun = t(fresh);
// 3. compaction dropped the bootstrap -> a later turn must re-inject it
const compacted = t([{ role: "user", content: "a later turn, bootstrap already compacted away" }]);

console.log(JSON.stringify({
  fresh_injected_role: fresh[0].role,
  fresh_bootstraps: countBootstraps(fresh),
  rerun_bootstraps: countBootstraps(rerun),
  reinject_role: compacted[0].role,
  reinject_bootstraps: countBootstraps(compacted),
  nonarray_passthrough: t(null),
}));
"""


def _run_driver():
    if shutil.which("node") is None:
        pytest.skip("node not on PATH")
    driver = _DRIVER % {"plugin": json.dumps(str(PLUGIN))}
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", driver],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def test_injects_as_user_role_not_system():
    """The bootstrap is injected as a user-role message (AAS-PORT-08), never system."""
    r = _run_driver()
    assert r["fresh_injected_role"] == "user"
    assert r["fresh_bootstraps"] == 1


def test_dedup_guard_prevents_double_injection():
    """Re-running the transform on its own output (the per-step callback double-fire) must not
    duplicate the bootstrap — exactly one remains."""
    r = _run_driver()
    assert r["rerun_bootstraps"] == 1


def test_reinjects_after_compaction():
    """When the bootstrap has been compacted out of the context, the next transform re-injects it
    as a user-role message."""
    r = _run_driver()
    assert r["reinject_bootstraps"] == 1
    assert r["reinject_role"] == "user"


def test_non_array_messages_passthrough():
    """A defensive guard: a non-array messages value is returned unchanged, never wrapped."""
    r = _run_driver()
    assert r["nonarray_passthrough"] is None


def test_plugin_source_uses_user_role_not_system():
    """Source-level backstop so the role can never silently regress to system even if node is
    unavailable to run the behavioral checks."""
    src = PLUGIN.read_text(encoding="utf-8")
    assert 'role: "user"' in src, "bootstrap must be injected as a user-role message (AAS-PORT-08)"
    assert 'role: "system"' not in src, "system-role injection is the AAS-PORT-08 defect (finding #10)"
