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
MECH = ROOT / "shared" / "scripts" / "mechanics"
# Unique marker planted in the ONE canonical home (shared/references/agent-data.md).
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

# The hand-authored skill-local reference ORIGINALS that legitimately remain under skills/ (no
# shared/references twin). Everything else under skills/*/references/ was a build-fanned copy and is
# gone. The set is now empty: the 2026-07-30 rewrite folded the home view and the first-run flow into
# skills/job-search/SKILL.md and shrank the operator manual to a routing card, deleting the last two
# playbooks. Every skill reads shared/references/ in place, so a skill-local pointer now dangles.
SKILL_LOCAL_ORIGINALS = set()

# A reference-file PATH pointer: an in-place shared ref (`../../shared/references/x.md`,
# `../../../shared/references/x.md`) or a kept skill-local ref (`references/x.md`,
# `references/platform/x.md`). A bare prose name (a filename with no directory component) is not a
# path and is intentionally NOT matched — resolution is a property of paths, not of doc-name shorthand.
_PTR = re.compile(r"(?:\.\./)*(?:shared/)?references/(?:platform/)?[A-Za-z0-9._-]+\.md")

# A shared mechanics-script PATH pointer the P4/T4.2 invoke-or-prose-fallback wiring makes. The
# 2026-07-30 rewrite settled on one written form — `<plugin-root>/shared/scripts/mechanics/x.sh`,
# resolved from the install root — and the older relative forms (`../../shared/scripts/mechanics/x.sh`
# from a SKILL.md, `../scripts/mechanics/x.sh` from a shared/references body) still resolve, so both
# are matched here. The "run the shared script where a runtime exists" arm must reach the shared
# scripts home — a dangling invocation would silently drop to the fallback on every host.
#
# Only the scripts more than one skill runs are left under shared/scripts/mechanics/. A script with a
# single skill consumer moved into that skill on 2026-07-31 and is named `scripts/x.sh` from its
# SKILL.md; `_COLOCATED_SCRIPT_PTR` matches those, and the same host loop proves they resolve too.
_SCRIPT_PTR = re.compile(
    r"(?:<plugin-root>/|(?:\.\./)+)(?:shared/)?scripts/mechanics/[A-Za-z0-9._-]+\.sh")
_COLOCATED_SCRIPT_PTR = re.compile(r"(?<![\w./-])scripts/[A-Za-z0-9._-]+\.sh")


def _pointer_files():
    """Files whose reference pointers must resolve: every SKILL.md (no skill-local originals remain)."""
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
                # no skill-local originals remain, so any skill-local pointer is dangling
                assert target.relative_to(ROOT).as_posix() in SKILL_LOCAL_ORIGINALS, (
                    f"{host}: {f.relative_to(ROOT)} -> `{ptr}` is a skill-local pointer that is not "
                    f"one of the kept originals (the set is empty)")


def test_marker_present_in_single_home():
    assert MARKER in (SHARED / "agent-data.md").read_text(encoding="utf-8"), (
        "the resolution marker was removed from shared/references/agent-data.md")


@pytest.mark.parametrize("host", sorted(HOST_MANIFESTS))
def test_every_skill_reaches_the_marked_home_on_host(host):
    """Positive proof that resolution lands on the ONE marked source tree, not a stray copy: each of
    the five skills' SKILL.md points at a shared reference that resolves in place into
    shared/references/, the directory carrying the marker. Which reference a skill cites is that
    skill's own business — which reference each one cites changes as the skills are rewritten — so
    the marker proves the DIRECTORY reached is the single home."""
    ok, reason = _ships_shared(HOST_MANIFESTS[host])
    assert ok, f"{host}: {reason}"
    marked = [p.name for p in sorted(SHARED.glob("*.md")) if MARKER in p.read_text(encoding="utf-8")]
    assert marked, "no file under shared/references/ carries the resolution marker"
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        reached = []
        for ptr in _pointers(skill_md):
            if "shared/references" not in ptr:
                continue
            target = (skill_md.parent / ptr).resolve()
            assert target.exists(), f"{host}: {skill_md.relative_to(ROOT)} -> `{ptr}` dangling"
            if target.parent == SHARED:
                reached.append(ptr)
        assert reached, (
            f"{host}: {skill_md.relative_to(ROOT)} makes no in-place pointer into the single home "
            f"shared/references/ (marker carried by {marked})")


def test_no_fanned_reference_copy_remains():
    """The fan-out is gone: no *.md remains under skills/*/references/ at all
    (no shared-twin copy, no references/platform/ adapter copy)."""
    present = set()
    for refs in (ROOT / "skills").glob("*/references"):
        for p in refs.rglob("*.md"):
            present.add(p.relative_to(ROOT).as_posix())
    fanned = sorted(present - SKILL_LOCAL_ORIGINALS)
    assert not fanned, f"fanned reference copies still present (must be single-homed): {fanned}"


# ------------------------------------------------------ mechanics-script resolution (P4/T4.2)

def _script_pointer_files():
    """Files that invoke a mechanics script: every SKILL.md + every shared/references body (the
    invoke-or-prose-fallback wiring lives in the runner and in the contracts it defers to)."""
    files = sorted((ROOT / "skills").glob("*/SKILL.md"))
    files += sorted(SHARED.glob("*.md"))
    return files


def _script_pointers(path):
    """Distinct script PATH pointers found in `path`, each with the directory it resolves against and
    the directory it has to land in: a `<plugin-root>/…` pointer resolves from the install root and a
    relative one from the file's own directory, both landing in shared/scripts/mechanics; a
    co-located `scripts/x.sh` resolves from the file's own directory and lands there."""
    out = []
    seen = set()
    text = path.read_text(encoding="utf-8")
    for m in _SCRIPT_PTR.finditer(text):
        tok = m.group(0)
        if tok in seen:
            continue
        seen.add(tok)
        base = ROOT / tok[len("<plugin-root>/"):] if tok.startswith("<plugin-root>/") \
            else path.parent / tok
        out.append((tok, base, MECH))
    for m in _COLOCATED_SCRIPT_PTR.finditer(text):
        tok = m.group(0)
        if tok in seen:
            continue
        seen.add(tok)
        out.append((tok, path.parent / tok, path.parent / "scripts"))
    return out


@pytest.mark.parametrize("host", sorted(HOST_MANIFESTS))
def test_every_mechanics_script_resolves_in_place_on_host(host):
    """P4/T4.2: the 'run the script' arm of each invoke-or-prose-fallback must resolve IN PLACE on every
    host — the same ships-shared property the references rely on. A shared script lands in
    shared/scripts/mechanics, a single-consumer one in its own skill's scripts/. A dangling script
    pointer -> RED (the runtime arm would never fire)."""
    ok, reason = _ships_shared(HOST_MANIFESTS[host])
    assert ok, f"{host}: {reason}"
    assert MECH.is_dir(), f"{host}: shared/scripts/mechanics not shipped"
    any_ptr = False
    for f in _script_pointer_files():
        for ptr, unresolved, home in _script_pointers(f):
            any_ptr = True
            target = unresolved.resolve()
            assert target.exists(), (
                f"{host}: {f.relative_to(ROOT)} -> `{ptr}` is DANGLING (no {target})")
            assert target.parent == home.resolve(), (
                f"{host}: {f.relative_to(ROOT)} -> `{ptr}` does not land in "
                f"{home.resolve().relative_to(ROOT)}")
    assert any_ptr, (
        f"{host}: no script pointer found in any SKILL.md or shared/references body — the "
        f"P4/T4.2 invoke-or-prose-fallback wiring is missing")


# ------------------------------------------------- co-located pointers (skill-locality, 2026-07-31)
#
# The 0.8.0 behavior evals measured both models mis-resolving this pack's own file pointers: sonnet
# read `../../shared/references/runbook.md` with one `..` too few, and haiku expanded `<plugin-root>`
# to the skill's own directory. Each miss costs a wasted tool call and a visible recovery, so the
# restructure gives every file with a single skill consumer an address that needs no computation.
#
# The written form: a path relative to the file that names it. From a SKILL.md that is
# `templates/<file>` or `scripts/<file>` — the skill's own directory, which is where the file now
# sits. From a file outside the skill (a shared/references body) it is the same file's path from the
# repo root, `skills/<skill>/templates/<file>`. Neither form asks the model to count `../` steps or
# to expand a token.
#
# These four files still carry a computed pointer, and each belongs to a later task: the two
# remaining mechanics scripts move next, and the two shared references become skills after that.
# The set shrinks to empty as those land. Any other computed pointer fails the test below.
DEFERRED_MOVES = {
    "shared/scripts/mechanics/validate-workspace.sh",
    "shared/scripts/mechanics/workspace-discovery.sh",
    "shared/references/runbook.md",
    "shared/references/agent-data.md",
}

# A pointer the model has to compute: `<plugin-root>/…` expands a token, `../../…` counts two or
# more directory steps up from the file it is written in. A single `../` (a SKILL.md naming its
# sibling skill's SKILL.md) is one step inside `skills/` and is not part of this move.
_COMPUTED_PTR = re.compile(r"(?:<plugin-root>/|(?:\.\./){2,})([A-Za-z0-9._/-]+\.[A-Za-z0-9]+)")

# A co-located pointer written in a SKILL.md: the skill's own `templates/`, `scripts/` or
# `references/` directory. The lookbehind rejects a match inside a longer path, where the directory
# name is not the start of the pointer.
_COLOCATED_PTR = re.compile(
    r"(?<![\w./-])(?:templates|scripts|references)/[A-Za-z0-9._-]+\.[A-Za-z0-9]+")

# The same co-located file addressed from the repo root, which is how a file outside the skill — a
# shared/references body — names it.
_ROOT_SKILL_PTR = re.compile(
    r"(?<![\w./-])skills/[A-Za-z0-9._-]+/(?:templates|scripts)/[A-Za-z0-9._-]+\.[A-Za-z0-9]+")


def _agent_facing_files():
    """Every file an agent reads at runtime and takes file paths from: the five SKILL.md bodies and
    both shared references."""
    return sorted((ROOT / "skills").glob("*/SKILL.md")) + sorted(SHARED.glob("*.md"))


def _computed_pointers(path):
    """Distinct computed pointers in `path`, each as (written token, the path it addresses)."""
    out = []
    for m in _COMPUTED_PTR.finditer(path.read_text(encoding="utf-8")):
        pair = (m.group(0), m.group(1))
        if pair not in out:
            out.append(pair)
    return out


def _plugin_file_pointers(path):
    """Every pointer in `path` that names a file inside this plugin, paired with the file it must
    resolve to: `<plugin-root>/…` and `skills/…` from the install root, `../../…` and a co-located
    one from the naming file's own directory."""
    text = path.read_text(encoding="utf-8")
    out = []

    def add(tok, target):
        if (tok, target) not in out:
            out.append((tok, target))

    for tok, tail in _computed_pointers(path):
        add(tok, ROOT / tail if tok.startswith("<plugin-root>/") else path.parent / tok)
    for m in _COLOCATED_PTR.finditer(text):
        add(m.group(0), path.parent / m.group(0))
    for m in _ROOT_SKILL_PTR.finditer(text):
        add(m.group(0), ROOT / m.group(0))
    return out


def test_no_computed_pointer_survives_outside_the_deferred_moves():
    """Every file with one skill consumer is addressed without arithmetic. A `<plugin-root>/…` or
    `../../…` pointer to anything but the four files a later task moves is the defect this
    restructure removes."""
    offenders = []
    for f in _agent_facing_files():
        for tok, tail in _computed_pointers(f):
            if tail not in DEFERRED_MOVES:
                offenders.append(f"{f.relative_to(ROOT)} -> `{tok}`")
    assert not offenders, (
        "these pointers still make the model compute an address for a file that has one skill "
        "consumer; move the file into that skill and name it from there:\n  "
        + "\n  ".join(offenders))


def test_every_plugin_file_a_skill_names_exists():
    """Every path to a plugin file named in a SKILL.md or a shared reference lands on a real file."""
    missing = []
    for f in _agent_facing_files():
        for tok, target in _plugin_file_pointers(f):
            if not target.resolve().exists():
                missing.append(f"{f.relative_to(ROOT)} -> `{tok}` (no {target.resolve()})")
    assert not missing, "dangling plugin-file pointers:\n  " + "\n  ".join(missing)
