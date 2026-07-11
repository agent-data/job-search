"""Per-host reference-resolution marker tests (AAS-TEST-10).

Proves the single-home cutover (belief 5): every reference a skill makes resolves IN PLACE to the one
canonical shared/references/ home, under each supported host's install view. This structural proof
REPLACES the removed byte-equality fan-out gate — the ~80 per-skill copies are gone (git rm'd) and each
skill references the single source via `../../shared/references/<file>.md` (from a SKILL.md) or
`../../../shared/references/<file>.md` (from a skill-local reference body). A dangling pointer -> RED; a
resolved pointer that lands on the marked single home -> GREEN.

Install model (STEP 0 finding, verified). Every documented distribution channel is a whole-repo
git/editable clone loaded in place — marketplace add+install (Claude/Codex/Copilot/Droid),
git-clone-and-open (Cursor), `gemini extensions install <url>`, opencode `git+https`, `pi install
git:...`/`pi -e`. The Claude marketplace install on disk (~/.claude/plugins/marketplaces/agent-data) is
a full clone that carries shared/. No manifest declares an npm-style `files` allowlist that would ship
skills/ in isolation (a `"skills": "./skills/"` field only *locates* skills within the cloned tree — it
is not a ship-restriction), and no host documents a filesystem read-scope jail confining a skill to its
own directory. So shared/ sits as a sibling of skills/ under one install root on every host, and
`../../shared/references/...` resolves. The per-host loop asserts that ships-shared property from each
manifest and would go RED for any host that ever shipped skills-only.
"""
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared" / "references"

# Unique marker planted in the ONE canonical home (shared/references/conventions.md).
MARKER = "reference-resolution-marker:8f2a4c1e-single-home"

# The eight adapter hosts -> the manifest that governs each host's install. Six manifest FILES cover
# eight hosts: Copilot reuses the Claude manifest; Droid can use the Claude-compat manifest or the
# .factory-plugin one; opencode and Pi both ship via package.json.
HOST_MANIFESTS = {
    "claude": ".claude-plugin/plugin.json",
    "codex": ".codex-plugin/plugin.json",
    "cursor": ".cursor-plugin/plugin.json",
    "droid": ".factory-plugin/plugin.json",
    "gemini": "gemini-extension.json",
    "opencode": "package.json",
    "pi": "package.json",
    "copilot": ".claude-plugin/plugin.json",
}

# The four hand-authored skill-local reference ORIGINALS that legitimately remain under skills/ (no
# shared/references twin). Everything else under skills/*/references/ was a build-fanned copy and is
# gone.
SKILL_LOCAL_ORIGINALS = {
    "skills/job-search/references/home.md",
    "skills/job-search/references/onboarding.md",
    "skills/job-search-agent/references/customization.md",
    "skills/job-search-agent/references/scheduling-and-consent.md",
}

# A reference-file PATH pointer: an in-place shared ref (`../../shared/references/x.md`,
# `../../../shared/references/x.md`) or a kept skill-local ref (`references/x.md`,
# `references/platform/x.md`). A bare prose name ("conventions.md" with no directory component) is not a
# path and is intentionally NOT matched — resolution is a property of paths, not of doc-name shorthand.
_PTR = re.compile(r"(?:\.\./)*(?:shared/)?references/(?:platform/)?[A-Za-z0-9._-]+\.md")


def _pointer_files():
    """Files whose reference pointers must resolve: every SKILL.md + the four skill-local originals."""
    files = sorted((ROOT / "skills").glob("*/SKILL.md"))
    files += [ROOT / rel for rel in sorted(SKILL_LOCAL_ORIGINALS)]
    return files


def _pointers(path):
    """Distinct reference-path pointers found in `path` (globs excluded)."""
    out = []
    for m in _PTR.finditer(path.read_text(encoding="utf-8")):
        tok = m.group(0)
        if "*" not in tok and tok not in out:
            out.append(tok)
    return out


def _ships_shared(manifest_rel):
    """Model, from a manifest, whether the host's install ships shared/ reachably from skills/.

    Every documented install is a whole-repo clone loaded in place, so shared/ is a sibling of skills/.
    The only thing that could break that is an npm-style `files` allowlist omitting shared/ — none use
    one. A `skills` pointer selects where skills live in the cloned tree; it is NOT a ship-restriction.
    Returns (ok, reason)."""
    path = ROOT / manifest_rel
    if not path.is_file():
        return False, f"manifest {manifest_rel} is missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return False, f"manifest {manifest_rel} is not valid JSON: {e}"
    files = data.get("files")
    if isinstance(files, list) and not any("shared" in str(f) for f in files):
        return False, f"manifest {manifest_rel} `files` allowlist would not ship shared/"
    return True, ""


@pytest.mark.parametrize("host", sorted(HOST_MANIFESTS))
def test_every_reference_resolves_in_place_on_host(host):
    ok, reason = _ships_shared(HOST_MANIFESTS[host])
    assert ok, f"{host}: {reason}"
    # Whole-tree in-place clone: the install root places skills/ and shared/ as siblings (== repo root).
    install_root = ROOT
    assert (install_root / "shared" / "references").is_dir(), f"{host}: shared/references not shipped"
    for f in _pointer_files():
        for ptr in _pointers(f):
            target = (f.parent / ptr).resolve()
            assert target.exists(), (
                f"{host}: {f.relative_to(ROOT)} -> `{ptr}` is DANGLING (no {target})")
            if "shared/references" in ptr:
                # an in-place shared pointer must land inside the single home
                assert target.parent == SHARED or SHARED in target.parents, (
                    f"{host}: {f.relative_to(ROOT)} -> `{ptr}` does not land in shared/references")
            else:
                # a skill-local pointer may only reach one of the four kept originals
                assert target.relative_to(ROOT).as_posix() in SKILL_LOCAL_ORIGINALS, (
                    f"{host}: {f.relative_to(ROOT)} -> `{ptr}` is a skill-local pointer that is not "
                    f"one of the four kept originals")


def test_marker_present_in_single_home():
    assert MARKER in (SHARED / "conventions.md").read_text(encoding="utf-8"), (
        "the resolution marker was removed from shared/references/conventions.md")


@pytest.mark.parametrize("host", sorted(HOST_MANIFESTS))
def test_every_skill_reaches_the_marked_home_on_host(host):
    """Positive proof that resolution lands on the ONE marked source, not a stray copy: each of the five
    skills' SKILL.md reaches shared/references/conventions.md in place, and that file carries the marker."""
    ok, reason = _ships_shared(HOST_MANIFESTS[host])
    assert ok, f"{host}: {reason}"
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        reached = False
        for ptr in _pointers(skill_md):
            if ptr.endswith("shared/references/conventions.md"):
                target = (skill_md.parent / ptr).resolve()
                assert target.exists(), f"{host}: {skill_md.relative_to(ROOT)} -> `{ptr}` dangling"
                assert MARKER in target.read_text(encoding="utf-8"), (
                    f"{host}: {skill_md.relative_to(ROOT)} -> `{ptr}` did not reach the marked home")
                reached = True
        assert reached, (
            f"{host}: {skill_md.relative_to(ROOT)} makes no in-place conventions.md pointer to the "
            f"single home")


def test_no_fanned_reference_copy_remains():
    """The fan-out is gone: the only *.md under skills/*/references/ are the four skill-local originals
    (no shared-twin copy, no references/platform/ adapter copy)."""
    present = set()
    for refs in (ROOT / "skills").glob("*/references"):
        for p in refs.rglob("*.md"):
            present.add(p.relative_to(ROOT).as_posix())
    fanned = sorted(present - SKILL_LOCAL_ORIGINALS)
    assert not fanned, f"fanned reference copies still present (must be single-homed): {fanned}"
