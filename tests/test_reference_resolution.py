"""Per-host reference-resolution marker tests (AAS-TEST-10).

Every file an agent reads at runtime sits inside a skill. The 2026-07-31 restructure promoted the
last two shared references to skills of their own — `job-search-runbook` and `agent-data-reference`
— and moved the last two mechanics scripts into the runbook skill, so `shared/` is gone. A skill
that needs a reference invokes the skill holding it by name; a skill that needs a file names that
file with a path nothing has to compute. These tests prove the shape holds under every supported
host's install view: a dangling pointer -> RED, a pointer landing on a real file -> GREEN.

Install model (STEP 0 finding, verified). Every documented distribution channel is a whole-repo
git/editable clone loaded in place — marketplace add+install (Claude/Codex/Copilot/Droid),
git-clone-and-open (Cursor), `gemini extensions install <url>`, opencode `git+https`, `pi install
git:...`/`pi -e`. The Claude marketplace install on disk (~/.claude/plugins/marketplaces/agent-data)
is a full clone. No manifest declares an npm-style `files` allowlist that would ship less than the
whole tree (a `"skills": "./skills/"` field only *locates* skills within the cloned tree — it is not
a ship-restriction), and no host documents a filesystem read-scope jail confining a skill to its own
directory. So every skill sits under one install root on every host, and a pointer from one skill to
a file in another resolves. The per-host loop asserts that ships-skills property from each manifest
and would go RED for any host that ever shipped a subset.
"""
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
# Unique marker planted in the one file holding the job-postings reference.
MARKER = "reference-resolution-marker:8f2a4c1e-single-home"

# The two references promoted to skills on 2026-07-31. Every other skill reaches one by this name.
REFERENCE_SKILLS = ("job-search-runbook", "agent-data-reference")

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

# The hand-authored skill-local reference ORIGINALS that legitimately remain under skills/. The set
# is empty: the 2026-07-30 rewrite folded the home view and the first-run flow into
# skills/job-search/SKILL.md and shrank the operator manual to a routing card, deleting the last two
# playbooks, and the 2026-07-31 restructure turned the two shared references into skills rather than
# into per-skill reference files. So any `references/…` pointer now dangles.
SKILL_LOCAL_ORIGINALS = set()

# A reference-file PATH pointer: a reintroduced shared ref (`../../shared/references/x.md`) or a
# skill-local ref (`references/x.md`, `references/platform/x.md`). A bare prose name (a filename with
# no directory component) is not a path and is intentionally NOT matched — resolution is a property
# of paths, not of doc-name shorthand.
_PTR = re.compile(r"(?:\.\./)*(?:shared/)?references/(?:platform/)?[A-Za-z0-9._-]+\.md")

# A script PATH pointer in its two written forms: co-located `scripts/x.sh`, which a skill writes for
# its own script and which resolves against that skill's directory, and `skills/<skill>/scripts/x.sh`,
# which a skill writes for another skill's script and which resolves from the install root. Both
# arms of every invoke-or-prose-fallback must reach a real file — a dangling invocation would
# silently drop to the prose fallback on every host.
_COLOCATED_SCRIPT_PTR = re.compile(r"(?<![\w./-])scripts/[A-Za-z0-9._-]+\.sh")
_ROOT_SCRIPT_PTR = re.compile(r"(?<![\w./-])skills/[A-Za-z0-9._-]+/scripts/[A-Za-z0-9._-]+\.sh")


def _skill_files():
    """Every SKILL.md, which is now every file an agent takes a runtime path from."""
    return sorted(SKILLS.glob("*/SKILL.md"))


def _pointer_files():
    """Files whose reference pointers must resolve: every SKILL.md (no skill-local originals remain)."""
    return _skill_files() + [ROOT / rel for rel in sorted(SKILL_LOCAL_ORIGINALS)]


def _pointers(path):
    """Distinct reference-path pointers found in `path` (globs excluded)."""
    out = []
    for m in _PTR.finditer(path.read_text(encoding="utf-8")):
        tok = m.group(0)
        if "*" not in tok and tok not in out:
            out.append(tok)
    return out


def _ships_skills(manifest_rel):
    """Model, from a manifest, whether the host's install ships the whole `skills/` tree.

    Every documented install is a whole-repo clone loaded in place. The only thing that could break
    that is an npm-style `files` allowlist omitting skills/ — none use one. A `skills` pointer
    selects where skills live in the cloned tree; it is NOT a ship-restriction. Returns (ok, reason)."""
    path = ROOT / manifest_rel
    if not path.is_file():
        return False, f"manifest {manifest_rel} is missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return False, f"manifest {manifest_rel} is not valid JSON: {e}"
    files = data.get("files")
    if isinstance(files, list) and not any("skills" in str(f) for f in files):
        return False, f"manifest {manifest_rel} `files` allowlist would not ship skills/"
    return True, ""


@pytest.mark.parametrize("host", sorted(HOST_MANIFESTS))
def test_every_reference_resolves_in_place_on_host(host):
    ok, reason = _ships_skills(HOST_MANIFESTS[host])
    assert ok, f"{host}: {reason}"
    # Whole-tree in-place clone: the install root is the repo root, and skills/ sits under it.
    install_root = ROOT
    assert (install_root / "skills").is_dir(), f"{host}: skills/ not shipped"
    assert not (install_root / "shared").exists(), (
        f"{host}: shared/ is back; every file an agent reads belongs inside a skill")
    for f in _pointer_files():
        for ptr in _pointers(f):
            target = (f.parent / ptr).resolve()
            assert target.exists(), (
                f"{host}: {f.relative_to(ROOT)} -> `{ptr}` is DANGLING (no {target})")
            assert target.relative_to(ROOT).as_posix() in SKILL_LOCAL_ORIGINALS, (
                f"{host}: {f.relative_to(ROOT)} -> `{ptr}` is a reference-file pointer that is not "
                f"one of the kept skill-local originals (the set is empty)")


def test_marker_present_in_the_reference_skill():
    assert MARKER in (SKILLS / "agent-data-reference" / "SKILL.md").read_text(encoding="utf-8"), (
        "the resolution marker was removed from skills/agent-data-reference/SKILL.md")


def test_marker_appears_in_exactly_one_shipped_file():
    """One copy of the job-postings reference, not a per-skill fan-out. The marker used to prove
    that every skill's `../../shared/references/…` pointer landed in the one shared home; consumers
    now invoke `agent-data-reference` by name, so what is left to prove is that the name resolves to
    exactly one file."""
    holders = sorted(p.relative_to(ROOT).as_posix()
                     for p in SKILLS.rglob("*.md") if MARKER in p.read_text(encoding="utf-8"))
    assert holders == ["skills/agent-data-reference/SKILL.md"], (
        f"the job-postings reference should live in exactly one file; found: {holders}")


@pytest.mark.parametrize("host", sorted(HOST_MANIFESTS))
def test_every_consumer_skill_names_a_reference_skill_on_host(host):
    """Positive proof that a consumer can still get to the mechanics: each of the five consumer
    skills names at least one of the two reference skills by the exact name its host invokes. Which
    reference a skill needs is that skill's own business and changes as the skills are rewritten, so
    this asserts the naming, not which one."""
    ok, reason = _ships_skills(HOST_MANIFESTS[host])
    assert ok, f"{host}: {reason}"
    for name in REFERENCE_SKILLS:
        assert (SKILLS / name / "SKILL.md").is_file(), f"{host}: skills/{name}/SKILL.md not shipped"
    for skill_md in _skill_files():
        if skill_md.parent.name in REFERENCE_SKILLS:
            continue
        text = skill_md.read_text(encoding="utf-8")
        named = [name for name in REFERENCE_SKILLS if name in text]
        assert named, (
            f"{host}: {skill_md.relative_to(ROOT)} names neither reference skill "
            f"({' nor '.join(REFERENCE_SKILLS)}), so nothing points it at the mechanics")


def test_no_fanned_reference_copy_remains():
    """The fan-out is gone: no *.md remains under skills/*/references/ at all
    (no shared-twin copy, no references/platform/ adapter copy)."""
    present = set()
    for refs in SKILLS.glob("*/references"):
        for p in refs.rglob("*.md"):
            present.add(p.relative_to(ROOT).as_posix())
    fanned = sorted(present - SKILL_LOCAL_ORIGINALS)
    assert not fanned, f"fanned reference copies still present (must be single-homed): {fanned}"


# ------------------------------------------------------ mechanics-script resolution (P4/T4.2)

def _script_pointers(path):
    """Distinct script PATH pointers in `path`, each paired with the file it must resolve to: a
    co-located `scripts/x.sh` against the naming file's own directory, a `skills/<skill>/scripts/x.sh`
    from the install root."""
    out = []
    seen = set()
    text = path.read_text(encoding="utf-8")
    for m in _ROOT_SCRIPT_PTR.finditer(text):
        tok = m.group(0)
        if tok not in seen:
            seen.add(tok)
            out.append((tok, ROOT / tok))
    for m in _COLOCATED_SCRIPT_PTR.finditer(text):
        tok = m.group(0)
        if tok not in seen and not any(tok in root_tok for root_tok, _ in out):
            seen.add(tok)
            out.append((tok, path.parent / tok))
    return out


@pytest.mark.parametrize("host", sorted(HOST_MANIFESTS))
def test_every_mechanics_script_resolves_in_place_on_host(host):
    """P4/T4.2: the 'run the script' arm of each invoke-or-prose-fallback must resolve IN PLACE on
    every host — the same ships-skills property the references rely on. A dangling script pointer
    -> RED (the runtime arm would never fire)."""
    ok, reason = _ships_skills(HOST_MANIFESTS[host])
    assert ok, f"{host}: {reason}"
    any_ptr = False
    for f in _skill_files():
        for ptr, target in _script_pointers(f):
            any_ptr = True
            assert target.resolve().is_file(), (
                f"{host}: {f.relative_to(ROOT)} -> `{ptr}` is DANGLING (no {target.resolve()})")
    assert any_ptr, (
        f"{host}: no script pointer found in any SKILL.md — the P4/T4.2 "
        f"invoke-or-prose-fallback wiring is missing")


# ------------------------------------------------- co-located pointers (skill-locality, 2026-07-31)
#
# The 0.8.0 behavior evals measured both models mis-resolving this pack's own file pointers: sonnet
# read `../../shared/references/runbook.md` with one `..` too few, and haiku expanded the plugin-root
# token to the skill's own directory. Each miss costs a wasted tool call and a visible recovery, so
# the restructure gives every file an address that needs no computation.
#
# The written form: a path relative to the file that names it. From a SKILL.md naming its own file
# that is `templates/<file>` or `scripts/<file>`. From a SKILL.md naming a file in another skill it
# is that file's path from the repo root, `skills/<skill>/<dir>/<file>`. Neither form asks the model
# to count `../` steps or to expand a token.
#
# Nothing is exempt. The set held the four files a later task owned — the two mechanics scripts and
# the two shared references — and that task landed on 2026-07-31, so every computed pointer now
# fails the test below.
DEFERRED_MOVES = set()
# The directories those files sat in. A computed pointer at a whole directory is the same defect as
# one at a file, so the exemption had to cover both. Derived, so it cannot drift from the set above.
DEFERRED_DIRS = {str(pathlib.PurePosixPath(p).parent) for p in DEFERRED_MOVES}

# A pointer the model has to compute: `<plugin-root>/…` expands a token, `../../…` counts two or
# more directory steps up from the file it is written in. A single `../` (a SKILL.md naming its
# sibling skill's SKILL.md) is one step inside `skills/` and is not part of this move.
#
# The tail matches a directory as well as a file. An earlier version required a file extension,
# which let `<plugin-root>/templates/` back in unnoticed — the gate for this whole restructure
# missing the very pointer shape it exists to catch.
_COMPUTED_PTR = re.compile(r"(?:<plugin-root>/|(?:\.\./){2,})((?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]*)")

# A co-located pointer written in a SKILL.md: the skill's own `templates/`, `scripts/` or
# `references/` directory. The lookbehind rejects a match inside a longer path, where the directory
# name is not the start of the pointer.
#
# Two shapes an earlier version of this pattern let through, both caught by planting them:
#   - the trailing file name is optional, so a bare `templates/` is a pointer too. Requiring an
#     extension is the same mistake `_COMPUTED_PTR` above records having made once already.
#   - `./scripts/foo.sh` is the form the failing run actually executed. Dropping `.` from the
#     lookbehind does not reach it — the character before `scripts` is `/`, which the lookbehind
#     also rejects — so the `./` has to be matched explicitly.
#
# This pattern feeds `_plugin_file_pointers` as well as the reference gate, so widening it widened
# both: a bare `templates/` or `scripts/` written in any of the seven SKILL.md files is now a
# dangling-pointer failure when that directory does not exist beside it. That is the behaviour to
# want — a pointer at a directory the skill does not have is broken wherever it is written — but it
# is a second effect of one edit, so it is recorded here rather than left to be discovered.
#
# Its three directory names are fixed because it is shared. The per-skill rule in
# `_colocated_offenders_in` derives the set from the skill instead, which is what covers a
# directory nobody listed here.
_COLOCATED_PTR = re.compile(
    r"(?<![\w./-])(?:\./)?(?:templates|scripts|references)/"
    r"(?:[A-Za-z0-9._-]+(?:\.[A-Za-z0-9]+)?)?")

# The same file addressed from the repo root, which is how a SKILL.md names a file another skill owns.
_ROOT_SKILL_PTR = re.compile(
    r"(?<![\w./-])skills/[A-Za-z0-9._-]+/(?:templates|scripts)/[A-Za-z0-9._-]+\.[A-Za-z0-9]+")


def _agent_facing_files():
    """Every file an agent reads at runtime and takes file paths from: the seven SKILL.md bodies."""
    return _skill_files()


def _computed_pointers_in(text):
    """Distinct computed pointers in `text`, each as (written token, the path it addresses). The
    address drops a trailing `/` so a directory pointer compares against the same names a file
    pointer does."""
    out = []
    for m in _COMPUTED_PTR.finditer(text):
        pair = (m.group(0), m.group(1).rstrip("/"))
        if pair not in out:
            out.append(pair)
    return out


def _computed_pointers(path):
    return _computed_pointers_in(path.read_text(encoding="utf-8"))


def _computed_offenders_in(rel, text):
    """The computed pointers in `text` that no later task has claimed — the defect this restructure
    removes, as `path -> token` lines."""
    return [f"{rel} -> `{tok}`" for tok, tail in _computed_pointers_in(text)
            if tail not in DEFERRED_MOVES and tail not in DEFERRED_DIRS]


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


def test_no_computed_pointer_survives_anywhere():
    """Every file is addressed without arithmetic. A `<plugin-root>/…` or `../../…` pointer in any
    SKILL.md is the defect this restructure removes, and nothing is exempt from it any more."""
    offenders = []
    for f in _agent_facing_files():
        offenders += _computed_offenders_in(f.relative_to(ROOT).as_posix(),
                                            f.read_text(encoding="utf-8"))
    assert not offenders, (
        "these pointers still make the model compute an address; name the file from the skill that "
        "owns it, or the skill that holds the reference:\n  "
        + "\n  ".join(offenders))


@pytest.mark.parametrize("planted", [
    "copy `<plugin-root>/templates/config.example.yaml` to `config.yaml`",   # a file
    "copy a template out of `<plugin-root>/templates/`",                     # a whole directory
    "the copyable examples in `../../templates/`",                           # relative, directory
    "read `../../templates/preferences.example.md` first",                   # relative, file
    "run `<plugin-root>/scripts/schedule-line.sh daily`",                    # a moved script
    "run `<plugin-root>/shared/scripts/mechanics/validate-workspace.sh <workspace>`",  # a promoted script
    "the discovery step in `../../shared/references/runbook.md`",            # a promoted reference
    "a script under `<plugin-root>/shared/scripts/mechanics/`",              # the promoted directory
])
def test_the_gate_catches_a_reintroduced_computed_pointer(planted):
    """The gate above only earns trust if it fires. Planting each shape of pointer this restructure
    removed — file or directory, token-prefixed or `../../`-prefixed — must produce an offender.
    The last three were exempt while the two scripts and the two references were a later task's to
    move; that task landed, so they are offenders now."""
    offenders = _computed_offenders_in("skills/job-search/SKILL.md", planted)
    assert offenders, f"the gate did not catch a reintroduced pointer: {planted!r}"


# Every rule below starts with this: not inside a longer path, and an optional `./`. Written once
# because writing it twice is how the `./` spelling got back in — `_COLOCATED_PTR` matched it and
# the bare-name rule beside it did not, and the form the live failure executed was `./…`.
_NOT_IN_A_PATH = r"(?<![\w./-])(?:\./)?"


def _own_subdirs(skill_dir):
    """Every directory inside this skill, whatever it is called.

    Derived rather than hardcoded. `_COLOCATED_PTR` knows only `templates|scripts|references`
    because it is shared with the resolution tests; a skill that grows a `bin/` would slip past it,
    and did when that was tried."""
    return sorted(d.name for d in skill_dir.iterdir() if d.is_dir())


def _own_file_names(skill_dir):
    """Every file name living in a directory of this skill's own, at any depth."""
    return sorted({f.name for d in skill_dir.iterdir() if d.is_dir()
                   for f in d.rglob("*") if f.is_file()})


def _body_without_frontmatter(text):
    """The SKILL.md body, with the YAML frontmatter block removed."""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[end + 4:]
    return text


def _colocated_offenders_in(rel, text, skill_dir=None):
    """Every way a reference skill can name one of its own files without naming itself.

    Three rules, because the address is what has to be unambiguous and there is more than one way
    to leave it ambiguous:
      - a path starting at a co-located directory this file knows by name — `scripts/x.sh`,
        `./scripts/x.sh`, a bare `templates/`;
      - the same, for a directory this skill actually has, whatever it is called, so a new `bin/`
        is covered without editing a list here;
      - a bare file name that is one of this skill's own files, with no directory at all.
        `workspace-discovery.sh` on its own tells a reader nothing about where to find it.

    A name inside a full `skills/<skill>/…` path is preceded by `/`, which every rule's lookbehind
    rejects, so the written form this gate asks for never trips it.

    **The bare-name rule reads the body only, never the frontmatter.** A `description:` is a routing
    surface — a router reads it to choose a skill, and nobody executes a path out of it — and it has
    a 200-character budget that a full `skills/<skill>/scripts/<file>` path does not fit inside. So
    the remedy this rule demands is unavailable there, and applying it to frontmatter would leave a
    gate whose only escape is writing the script names without their extensions by luck.
    """
    out = []

    def add(tok, why=""):
        line = f"{rel} -> `{tok}`{why}"
        if line not in out:
            out.append(line)

    for m in _COLOCATED_PTR.finditer(text):
        add(m.group(0))
    if skill_dir:
        subdirs = _own_subdirs(skill_dir)
        if subdirs:
            own_dir = re.compile(_NOT_IN_A_PATH + r"(?:" +
                                 "|".join(re.escape(d) for d in subdirs) + r")/"
                                 r"(?:[A-Za-z0-9._-]+(?:\.[A-Za-z0-9]+)?)?")
            for m in own_dir.finditer(text):
                add(m.group(0))
        names = _own_file_names(skill_dir)
        if names:
            bare = re.compile(_NOT_IN_A_PATH + r"(?:" +
                              "|".join(re.escape(n) for n in names) + r")\b")
            for m in bare.finditer(_body_without_frontmatter(text)):
                add(m.group(0), " (a file of this skill's, named without the skill)")
    return out


def test_no_reference_skill_addresses_a_file_from_its_own_directory():
    """A reference skill names every file in full, `skills/<skill>/…`, never `scripts/<file>`.

    The two shapes gated above were caught by the 0.8.0 evals. This one was caught by the evals
    *after* the restructure, and it is the same defect wearing different clothes. The runbook said
    "run this skill's `scripts/workspace-discovery.sh`"; a model executing `job-search-run` read
    that sentence, bound it to its own directory, ran `cd <job-search-run> && ./scripts/…`, got
    exit 127, and spent three `ls` calls finding the real path.

    Why the rule is scoped to reference skills and not to all seven: a co-located pointer says "the
    directory of the skill this text belongs to", and that is only unambiguous when the skill that
    owns the text is the skill doing the work. A user-triggered skill is entered and then acts, so
    the two coincide and the short form is correct — it is the form Task 1 established. A reference
    skill is never the one acting: its text is always carried out by a sibling, so the same pointer
    resolves against whichever skill happens to be executing.

    This checks the pointer's form, which is what a test can settle. The possessive that introduced
    it — "this skill's" — is prose, and prose is not what makes the address ambiguous; writing the
    skill out in full fixes the sentence whether or not a possessive precedes it.
    """
    offenders = []
    for name in REFERENCE_SKILLS:
        f = SKILLS / name / "SKILL.md"
        offenders += _colocated_offenders_in(f.relative_to(ROOT).as_posix(),
                                             f.read_text(encoding="utf-8"), f.parent)
    assert not offenders, (
        "a reference skill is read while a different skill is executing, so a pointer relative to "
        "'this skill' resolves against the wrong directory. Name the owning skill in full, "
        "`skills/<skill>/…`:\n  " + "\n  ".join(offenders))


@pytest.mark.parametrize("planted", [
    # This list is the gate. Every spelling anyone has defeated it with is kept here by name,
    # permanently, because the gate has now been declared working twice and defeated twice — both
    # times by a spelling nobody had planted, never by a flaw anyone spotted by reading it.
    #
    # Round 2: the sentence that failed live.
    "Run this skill's `scripts/workspace-discovery.sh`.",
    # Round 3: three spellings that beat the first regex — it required a file extension and its
    # lookbehind could not see past a leading `./`.
    "Run this skill's `./scripts/workspace-discovery.sh`.",
    "Take a template out of this skill's `templates/`, and the scripts are in `scripts/`.",
    "Run this skill's `workspace-discovery.sh`.",
    # Round 4: six more, all the same `./` hole reopened in the bare-name rule, which had been
    # built with the lookbehind but without the `./` alternative.
    "Run this skill's `./workspace-discovery.sh`.",
    "Check the close with `./validate-workspace.sh <workspace> --post-close <run_id>`.",
    "Run `cd skills/job-search-runbook/scripts && ./workspace-discovery.sh`.",
    "```bash\n./workspace-discovery.sh\n```",
    'Run `sh ./workspace-discovery.sh` or `bash -c "./workspace-discovery.sh"`.',
    # The live failure with one directory segment removed, which is as close to it as prose gets.
    'Run `cd "$dir" && ./workspace-discovery.sh && echo ok`.',
    # Written forms that were caught from the start, kept so a rewrite cannot lose them.
    "Check the close with `scripts/validate-workspace.sh <workspace>`.",
    "The shape is in `templates/run-record.example.json`.",
])
def test_the_reference_gate_catches_a_reintroduced_colocated_pointer(planted):
    """The gate above only earns trust if it fires — on every spelling, not on one.

    A gate whose adversarial cases live only in a review transcript is a gate that drifts back.
    Each entry above passed the whole suite at some point: the first before the gate existed, the
    next three against its first regex, and the next six against its second, where the `./` hole
    the third round closed in one rule was reopened in the rule the third round added."""
    assert _colocated_offenders_in("skills/job-search-runbook/SKILL.md", planted,
                                   SKILLS / "job-search-runbook"), (
        f"the gate did not catch a reintroduced co-located pointer: {planted!r}")


@pytest.mark.parametrize("allowed", [
    # Each carries something the gate looks for and must still pass, so an over-firing gate is
    # caught here: a `scripts/` segment inside a rooted path, a `templates/` segment inside a
    # rooted path, and plain file names that are not this skill's own files.
    "run the plugin's `skills/job-search-runbook/scripts/workspace-discovery.sh`",
    "the shape is `skills/job-search-run/templates/run-record.example.json`",
    "the workspace holds `config.yaml`, `preferences.md` and `jobs.jsonl`",
])
def test_the_reference_gate_leaves_a_fully_named_pointer_alone(allowed):
    """A gate that fired on everything would be no gate. A reference skill naming the owning skill
    in full is the form this asks for and must pass, as must a plain file name that is not one of
    this skill's own files."""
    assert _colocated_offenders_in("skills/job-search-runbook/SKILL.md", allowed,
                                   SKILLS / "job-search-runbook") == []


def test_the_reference_gate_covers_a_directory_it_was_never_told_about(tmp_path):
    """A skill that grows a new directory is covered without anyone editing a list.

    `_COLOCATED_PTR` knows three directory names because it is shared with the resolution tests.
    The per-skill rule derives the set from the skill itself, so a `bin/` nobody anticipated is
    caught — it was not, before this test existed."""
    skill = tmp_path / "a-reference-skill"
    (skill / "bin").mkdir(parents=True)
    (skill / "bin" / "probe-helper.sh").write_text("#!/bin/sh\n")
    for planted in ("run this skill's `bin/probe-helper.sh`",
                    "run this skill's `./bin/probe-helper.sh`",
                    "run this skill's `probe-helper.sh`"):
        assert _colocated_offenders_in("x/SKILL.md", planted, skill), (
            f"a derived directory went ungated: {planted!r}")
    assert _colocated_offenders_in(
        "x/SKILL.md", "run the plugin's `skills/a-reference-skill/bin/probe-helper.sh`", skill) == []


def test_the_bare_name_rule_leaves_the_routing_description_alone(tmp_path):
    """A `description:` names what a skill holds; nobody executes a path out of it, and the full
    `skills/<skill>/scripts/<file>` form the gate asks for does not fit its 200-character budget.
    Demanding it there would leave a gate whose only escape is naming the scripts without their
    extensions and hoping nobody adds them."""
    skill = tmp_path / "a-reference-skill"
    (skill / "scripts").mkdir(parents=True)
    (skill / "scripts" / "validate-workspace.sh").write_text("#!/bin/sh\n")
    fm = ('---\nname: a-reference-skill\n'
          'description: "Not user-facing. Holds validate-workspace.sh."\n---\n\n# body\n')
    assert _colocated_offenders_in("x/SKILL.md", fm, skill) == []
    assert _colocated_offenders_in("x/SKILL.md", fm + "Run `validate-workspace.sh`.\n", skill), (
        "the body is still gated even when the frontmatter is not")


@pytest.mark.parametrize("allowed", [
    "copy this skill's `templates/config.example.yaml` to `config.yaml`",
    "the shape is `skills/job-search-run/templates/run-record.example.json`",
    "run the plugin's `skills/job-search-runbook/scripts/validate-workspace.sh <workspace>`",
    "the ten rules under **How to communicate** in `../job-search/SKILL.md`",
])
def test_the_gate_leaves_the_written_forms_alone(allowed):
    """A gate that fired on everything would be no gate. Both written forms — a skill's own file and
    another skill's file from the repo root — must pass, as must the single `../` a SKILL.md uses to
    name a sibling SKILL.md, which is one step inside `skills/` and needs no arithmetic."""
    assert _computed_offenders_in("skills/job-search/SKILL.md", allowed) == []


def test_every_plugin_file_a_skill_names_exists():
    """Every path to a plugin file named in a SKILL.md lands on a real file."""
    missing = []
    for f in _agent_facing_files():
        for tok, target in _plugin_file_pointers(f):
            if not target.resolve().exists():
                missing.append(f"{f.relative_to(ROOT)} -> `{tok}` (no {target.resolve()})")
    assert not missing, "dangling plugin-file pointers:\n  " + "\n  ".join(missing)
