#!/usr/bin/env python3
"""Structural validation for the multi-harness platform layer.

The six non-Claude harnesses (codex, cursor, opencode, gemini, copilot, droid, pi) cannot be
live-tested in CI — no harness is installed on the runner. Codex is proven by the manual P0 live
lane (run by hand, off-CI); the remaining six get this STRUCTURAL gate instead. It proves, without
running any harness, that every platform adapter is complete, every manifest parses, and every
adapter cross-reference the neutralized skill prose makes actually resolves on every harness — so a
dangling `→ Section` pointer or a malformed manifest is caught before install. This is the
platform/-subdir lane the plan calls for (doc_lint.py deliberately scans only the KB, not
shared/references or skills, so this is a NEW lane, not a doc_lint rule).

Mirrors scripts/doc_lint.py in shape: scan(root) -> hits; main() prints hits and returns 1 on
failure, else prints "Platform validation: clean." and returns 0. `--root` arg. Stdlib only.

Nine checks, dispatched via the CHECKS registry:
  - adapter-sections:  every shared/references/platform/<harness>.md SOURCE adapter carries all 12
                       canonical `## ` sections (exact names). Synced skills/*/references/platform/
                       copies are asserted to match their source byte-for-byte.
  - manifest-parse:    every manifest JSON that EXISTS parses as valid JSON (an absent optional one
                       is skipped, not a failure). The .opencode/plugins/job-search.js plugin is
                       `node --check`'d IF node is on PATH, else an informational skip (CI without
                       node must not fail).
  - skill-frontmatter: every skills/*/SKILL.md opens with a `---`-fenced YAML frontmatter block
                       whose plain (unquoted) scalar values carry no ': ' (colon-space) — the
                       construct strict-YAML harnesses (Codex et al.) reject though Claude's lenient
                       reader tolerates it — plus the required name/description keys. Stdlib-only.
  - adapter-cross-refs: scan shared/references/*.md + skills/**/*.md (NOT the adapters themselves)
                       for adapter cross-references — the arrow form the neutralized prose uses
                       (`adapter → <Section>`, `… defers to → <Section>`). Every referenced
                       <Section> must be one of the 12 canonical sections AND exist as a `## `
                       heading in EVERY adapter (so a skill resolves its pointer on any harness).
  - codex-workspace-write: Codex headless/run recipes must make the active job-search workspace
                       writable (`cd <workspace>` or `--add-dir <workspace>`) as well as enabling
                       network egress. This catches the live regression where `workspace-write`
                       could read `~/.job-search` but could not persist run artifacts there.
  - codex-parallel-subagents: Codex must document the job-search parallel-detail preference, scoped
                       profile, explicit scheduled prompt authorization, fallback, and model mapping.
  - runtime-bundle:    the stdlib runtime bundled into each consuming skill's scripts/hermes_job_search/
                       must match runtime/hermes_job_search/ byte-for-byte, and no other skill may
                       carry it (no-op when the runtime source is absent).
  - hermes-runtime-invocation: once shared/references/platform/hermes.md exists, it must document the
                       bundled-runtime terminal invocation + the hermes-cron / delegate_task mechanisms.
  - hermes-prior-session: once hermes.md exists, it must document the prior-session recall capability
                       (the session_search mechanism, the permission gate, and that drafts go to the
                       workspace brief, never USER.md). No-op until hermes.md is authored.
"""
import argparse, json, os, re, shutil, subprocess, sys

# The 12 canonical adapter sections, in their canonical order (from claude.md / codex.md).
CANONICAL_SECTIONS = (
    "Identity",
    "Tool map",
    "Run recipe",
    "Scheduling",
    "Headless invocation",
    "Closed-choice question",
    "Concurrent detail reads",
    "Model tiers",
    "Whole-file write",
    "Block-alert channel",
    "agent-data setup",
    "Packaging & install",
)

PLATFORM_DIR = os.path.join("shared", "references", "platform")
HEADING_RE = re.compile(r"^##\s+(.*?)\s*#*\s*$")

# Manifests to check. Each may be absent (optional) — discovered, never hard-required.
JSON_MANIFESTS = (
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".codex-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    ".factory-plugin/plugin.json",
    "gemini-extension.json",
    "package.json",
)
JS_PLUGIN = ".opencode/plugins/job-search.js"


def adapter_sources(root):
    """Yield (harness, abspath) for every SOURCE adapter under shared/references/platform/."""
    base = os.path.join(root, PLATFORM_DIR)
    if not os.path.isdir(base):
        return
    for fn in sorted(os.listdir(base)):
        if fn.endswith(".md"):
            yield fn[:-3], os.path.join(base, fn)


def _section_headings(text):
    """Ordered list of `## ` heading titles in `text`."""
    return [m.group(1) for line in text.splitlines() for m in [HEADING_RE.match(line)] if m]


def scan_adapter_sections(root):
    """Every source adapter must carry all 12 canonical `## ` sections (exact names); each synced
    skills/*/references/platform/ copy must match its source byte-for-byte (build.sh keeps them in
    sync — a drifted copy would ship a stale adapter on install)."""
    hits = []
    sources = list(adapter_sources(root))
    for harness, path in sources:
        rel = os.path.relpath(path, root)
        with open(path, encoding="utf-8", errors="replace") as f:
            src_text = f.read()
        present = set(_section_headings(src_text))
        for sec in CANONICAL_SECTIONS:
            if sec not in present:
                hits.append(f"{rel}: adapter-sections: missing canonical section '## {sec}'")
        # Synced copies under skills/*/references/platform/<harness>.md must equal the source.
        for dirpath, _, files in os.walk(os.path.join(root, "skills")):
            if not dirpath.endswith(os.path.join("references", "platform")):
                continue
            copy = os.path.join(dirpath, harness + ".md")
            if not os.path.isfile(copy):
                continue
            with open(copy, encoding="utf-8", errors="replace") as f:
                if f.read() != src_text:
                    hits.append(f"{os.path.relpath(copy, root)}: adapter-sections: synced copy "
                                f"differs from source {rel} (re-run build.sh)")
    return hits


def scan_manifest_parse(root):
    """Every manifest JSON that exists must parse; the opencode .js plugin is node --check'd when
    node is available (informational skip otherwise — CI without node must not fail)."""
    hits = []
    for rel in JSON_MANIFESTS:
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue  # optional manifest, discovered not required
        try:
            with open(path, encoding="utf-8") as f:
                json.load(f)
        except (ValueError, OSError) as e:
            hits.append(f"{rel}: manifest-parse: invalid JSON ({e})")
    js = os.path.join(root, JS_PLUGIN)
    if os.path.exists(js):
        node = shutil.which("node")
        if node is None:
            print(f"info: manifest-parse: node not on PATH; skipped `node --check` of {JS_PLUGIN}")
        else:
            proc = subprocess.run([node, "--check", js], capture_output=True, text=True)
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout).strip().replace("\n", " ")
                hits.append(f"{JS_PLUGIN}: manifest-parse: node --check failed ({detail})")
    return hits


# A skills/*/SKILL.md opens with a `---`-fenced YAML frontmatter block. Codex and the other
# non-Claude harnesses parse it with a STRICT YAML loader; Claude's reader is lenient, so a defect
# (e.g. a plain scalar containing ': ') loads fine on Claude yet "Skipped … invalid YAML: mapping
# values are not allowed in this context" on Codex. We stay stdlib-only and target that exact
# failure mode rather than re-implementing a YAML parser.
_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.DOTALL)
_YAML_NONPLAIN = "\"'|>&*!"  # value first-chars meaning "not a plain scalar" (quoted/block/anchor/tag)


def _skill_md_files(root):
    """Yield abspaths of every skills/*/SKILL.md, sorted."""
    base = os.path.join(root, "skills")
    if not os.path.isdir(base):
        return
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name, "SKILL.md")
        if os.path.isfile(path):
            yield path


def scan_skill_frontmatter(root):
    """Every skills/*/SKILL.md must open with a `---`-fenced YAML frontmatter block a STRICT YAML
    loader accepts — so the skill loads on Codex and the other strict-parsing harnesses, not just on
    Claude's lenient reader. Stdlib-only and targeted at the failure mode that actually bit us: a
    plain (unquoted, non-block) `key: value` whose value contains a ': ' (colon-space) is rejected by
    strict YAML ("mapping values are not allowed in this context"); quote the value or, house style,
    use an em-dash. Also requires the block to exist and to carry `name` and `description`. (This is
    the convention superpowers ships by — no SKILL.md description carries a value-internal colon.)"""
    hits = []
    for path in _skill_md_files(root):
        rel = os.path.relpath(path, root)
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        m = _FRONTMATTER_RE.match(text)
        if not m:
            hits.append(f"{rel}: skill-frontmatter: missing `---`-fenced YAML frontmatter block")
            continue
        keys = set()
        for line in m.group(1).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key, sep, raw_value = line.partition(":")
            if not sep or not key or key != key.strip():
                continue  # indented / continuation / list item — out of scope for this targeted check
            keys.add(key)
            value = raw_value.strip()
            if value and value[0] not in _YAML_NONPLAIN and ": " in raw_value:
                col = len(key) + 1 + raw_value.index(": ") + 1
                hits.append(f"{rel}: skill-frontmatter: unquoted '{key}' value contains a ': ' "
                            f"(col {col}) — strict YAML rejects this; quote it or use ' — '")
        for required in ("name", "description"):
            if required not in keys:
                hits.append(f"{rel}: skill-frontmatter: frontmatter missing required key '{required}'")
    return hits


# An adapter cross-reference is the neutralized-prose form "… adapter → <Section>" (the literal word
# "adapter" — "your platform's adapter", "your adapter", "the active platform's adapter") OR the
# deferral form "… defers to → <Section>" (e.g. "the fan-out itself defers to → Concurrent detail
# reads"), then an arrow (→), then a canonical section name. The arrow is otherwise heavily
# overloaded in this repo (data-flow "search → dedup → judge", fallbacks "true → retry", path
# precedence, error mapping "→ E-QUOTA", the doc-heading pointer "internals.md → Scheduling setup"),
# so we anchor on the word "adapter" or the phrase "defers to" — only those forms are adapter
# pointers.
#
# The trailing section name may be wrapped across a line break ("adapter → Model\ntiers"), wrapped in
# **bold** or `code`, or COMPOUND ("adapter → Tool map / Whole-file write" — two sections joined by
# "/"). We normalize whitespace to single spaces and strip emphasis markers, then greedily match the
# LONGEST canonical name that begins the text after the arrow, and continue matching across "/ "
# joiners. An arrow anchored by "adapter" whose target matches no canonical name is an unresolved /
# typo'd / renamed pointer -> a hit.
_CANON_BY_LEN = sorted(CANONICAL_SECTIONS, key=len, reverse=True)
_WS_RE = re.compile(r"\s+")
_EMPHASIS_RE = re.compile(r"[*`]")
# "adapter" + optional possessive, OR the "defers to" verb phrase, then the arrow. Matches
# "adapter →", "adapter's →", and the neutralized "… defers to → <Section>" deferral pointer.
# Both are genuine adapter cross-references; the doc-heading pointer ("internals.md → Scheduling
# setup"), data-flow arrows ("search → dedup"), and error maps ("→ E-QUOTA") are NOT anchored by
# either token and so stay correctly excluded.
_ADAPTER_ARROW_RE = re.compile(r"(?:adapter(?:'s)?|defers to)\s*→\s*")


def _normalize(text):
    """Collapse all whitespace to single spaces and strip markdown emphasis (* and `)."""
    return _WS_RE.sub(" ", _EMPHASIS_RE.sub("", text))


def _match_section(after):
    """Greedily match the longest canonical section name that begins `after`; return (name, rest)
    where rest is the text following the matched name, or (None, after) if none matches."""
    for sec in _CANON_BY_LEN:
        if after.startswith(sec):
            return sec, after[len(sec):]
    return None, after


def _refs_in_text(text):
    """Yield ('OK', section) for each canonical section pointed at by an "adapter → …" or
    "defers to → …" reference, and ('UNRESOLVED', snippet) for such an anchored arrow whose target is
    not a canonical section. Handles compound "adapter → A / B" pointers (both A and B are yielded)."""
    norm = _normalize(text)
    out = []
    for m in _ADAPTER_ARROW_RE.finditer(norm):
        after = norm[m.end():]
        sec, rest = _match_section(after)
        if sec is None:
            out.append(("UNRESOLVED", after[:40].strip()))
            continue
        out.append(("OK", sec))
        # Continue across "/ <Section>" compound joiners (e.g. "Tool map / Whole-file write").
        while True:
            stripped = rest.lstrip()
            if not stripped.startswith("/"):
                break
            nxt, rest2 = _match_section(stripped[1:].lstrip())
            if nxt is None:
                break
            out.append(("OK", nxt))
            rest = rest2
    return out


def _cross_ref_files(root):
    """shared/references/*.md (NOT platform/ adapters) + every skills/**/*.md (NOT the synced
    references/platform/ adapter copies). These are the files whose pointers must resolve."""
    files = []
    sr = os.path.join(root, "shared", "references")
    if os.path.isdir(sr):
        for fn in sorted(os.listdir(sr)):
            if fn.endswith(".md"):
                files.append(os.path.join(sr, fn))
    sk = os.path.join(root, "skills")
    for dirpath, _, fns in os.walk(sk):
        if dirpath.endswith(os.path.join("references", "platform")):
            continue  # the adapters themselves are not cross-ref sources
        for fn in sorted(fns):
            if fn.endswith(".md"):
                files.append(os.path.join(dirpath, fn))
    return files


def scan_adapter_cross_refs(root):
    """Every `→ <Section>` pointer in the prose must name one of the 12 canonical sections, and that
    section must exist as a `## ` heading in EVERY source adapter (so the pointer resolves on any
    harness). An arrow whose target matches no canonical name is an unresolved/typo'd pointer."""
    hits = []
    # Which canonical sections actually exist in every adapter? (scan_adapter_sections already flags
    # a genuinely missing section; here we guard the cross-ref against a section absent on some host.)
    sources = list(adapter_sources(root))
    per_adapter = {}
    for harness, path in sources:
        with open(path, encoding="utf-8", errors="replace") as f:
            per_adapter[harness] = set(_section_headings(f.read()))
    for path in _cross_ref_files(root):
        rel = os.path.relpath(path, root)
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        for kind, target in _refs_in_text(text):
            if kind == "UNRESOLVED":
                hits.append(f"{rel}: adapter-cross-refs: arrow target is not a canonical section: "
                            f"'→ {target}'")
                continue
            missing = sorted(h for h in per_adapter if target not in per_adapter[h])
            if missing:
                hits.append(f"{rel}: adapter-cross-refs: section '{target}' is referenced but "
                            f"absent from adapter(s): {', '.join(missing)}")
    return hits


def scan_codex_workspace_write(root):
    """Codex `workspace-write` grants writes only to the cwd/workspace roots. Job Search stores state in
    the active workspace (usually ~/.job-search), so the Codex adapter must pin a run recipe that either
    runs from `<workspace>` or passes it with `--add-dir`. Network egress alone is insufficient."""
    hits = []
    rel = os.path.join(PLATFORM_DIR, "codex.md")
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        return hits
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if "sandbox_workspace_write.network_access=true" not in text:
        hits.append(f"{rel}: codex-workspace-write: missing network egress config")
    if "cd <workspace> && codex exec" not in text and "--add-dir <workspace>" not in text:
        hits.append(f"{rel}: codex-workspace-write: codex exec recipe must run from or add the job-search workspace")
    if "cd <workspace> && codex exec" not in text:
        hits.append(f"{rel}: codex-workspace-write: missing primary `cd <workspace> && codex exec` recipe")
    if "--add-dir <workspace>" not in text:
        hits.append(f"{rel}: codex-workspace-write: missing `--add-dir <workspace>` alternate recipe")
    return hits


def scan_codex_parallel_subagents(root):
    """Codex subagent collaboration is preference-gated and prompt-authorized. The adapter must pin
    both layers for job-search: a user-approved job-search preference, a scoped Codex profile for
    headless runs, explicit scheduled prompt wording, a sequential fallback, and the concrete Codex
    model IDs used for each detail-read tier."""
    hits = []
    rel = os.path.join(PLATFORM_DIR, "codex.md")
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        return hits
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    required = (
        ("search.parallel_detail_reads",
         "missing job-search `search.parallel_detail_reads` preference"),
        ("job-search.config.toml",
         "missing scoped Codex profile file `$CODEX_HOME/job-search.config.toml`"),
        ("multi_agent = true",
         "missing `multi_agent = true` profile setting"),
        ("--profile job-search",
         "missing `--profile job-search` in the Codex CLI recipe"),
        ("Use parallel subagents for all detail reads",
         "missing explicit scheduled prompt authorization: `Use parallel subagents for all detail reads`"),
        ("sequential",
         "missing sequential fallback if Codex refuses or cannot spawn subagents"),
    )
    for needle, message in required:
        if needle not in text:
            hits.append(f"{rel}: codex-parallel-subagents: {message}")
    tier_rows = (
        ("fast", "gpt-5.4-mini"),
        ("balanced", "gpt-5.4"),
        ("high", "gpt-5.5"),
    )
    for tier, model in tier_rows:
        if not re.search(rf"`{tier}`\s*\|\s*`{re.escape(model)}`", text):
            hits.append(f"{rel}: codex-parallel-subagents: missing Codex `{tier}` "
                        f"detail-read model mapping to `{model}`")
    return hits


# The Hermes path bundles a stdlib-Python state-ops runtime into the consuming skills' scripts/.
RUNTIME_SRC = os.path.join("runtime", "hermes_job_search")
CONSUMING_SKILLS = ("job-search", "job-search-run", "job-search-agent")


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def scan_runtime_bundle(root):
    """The runtime bundled into each consuming skill's scripts/hermes_job_search/ must match the
    source byte-for-byte (build.sh keeps them in sync, mirroring the adapter synced-copy guarantee),
    and no NON-consuming skill may carry it. No-op when the runtime source is absent (so the empty
    tree and the synthetic-tmp adapter tests stay clean)."""
    hits = []
    src_dir = os.path.join(root, RUNTIME_SRC)
    if not os.path.isdir(src_dir):
        return hits
    src = {fn: _read_bytes(os.path.join(src_dir, fn))
           for fn in os.listdir(src_dir) if fn.endswith(".py")}
    skills_base = os.path.join(root, "skills")
    if not os.path.isdir(skills_base):
        return hits
    for skill in sorted(os.listdir(skills_base)):
        dest = os.path.join(skills_base, skill, "scripts", "hermes_job_search")
        rel = os.path.join("skills", skill, "scripts", "hermes_job_search")
        present = os.path.isdir(dest)
        if skill in CONSUMING_SKILLS:
            if not present:
                hits.append(f"{rel}: runtime-bundle: missing bundled runtime (re-run build.sh)")
                continue
            dest_files = {fn for fn in os.listdir(dest) if fn.endswith(".py")}
            if dest_files != set(src):
                hits.append(f"{rel}: runtime-bundle: bundled file set differs from source (re-run build.sh)")
            for fn, data in src.items():
                dp = os.path.join(dest, fn)
                if os.path.isfile(dp) and _read_bytes(dp) != data:
                    hits.append(f"{rel}/{fn}: runtime-bundle: differs from source (re-run build.sh)")
        elif present:
            hits.append(f"{rel}: runtime-bundle: unexpected bundle in a non-consuming skill "
                        f"(only {', '.join(CONSUMING_SKILLS)} bundle the runtime)")
    return hits


def scan_hermes_runtime_invocation(root):
    """Once the Hermes adapter exists, it must document how the Hermes path invokes the bundled
    runtime (the terminal-tool call) and its Hermes-native scheduling + fan-out mechanisms. No-op
    until shared/references/platform/hermes.md is authored (so it stays green before that commit)."""
    hits = []
    rel = os.path.join(PLATFORM_DIR, "hermes.md")
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        return hits
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    for needle, message in (
        ("scripts/hermes_job_search/cli.py", "missing the bundled-runtime invocation `scripts/hermes_job_search/cli.py`"),
        ("hermes-cron", "missing the `hermes-cron` scheduling mechanism marker"),
        ("delegate_task", "missing the `delegate_task` concurrent-detail-reads mechanism"),
    ):
        if needle not in text:
            hits.append(f"{rel}: hermes-runtime-invocation: {message}")
    return hits


def scan_hermes_prior_session(root):
    """Once the Hermes adapter exists, it must document the prior-session recall capability the preference
    interview's draft-from-prior-context offer depends on: the session_search mechanism, the permission
    gate, and that drafts go to the workspace brief, never USER.md. No-op until hermes.md is authored."""
    hits = []
    rel = os.path.join(PLATFORM_DIR, "hermes.md")
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        return hits
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if "## Prior-session recall" not in text:
        hits.append(f"{rel}: hermes-prior-session: missing the '## Prior-session recall' section")
        return hits
    for needle, message in (
        ("session_search", "missing the `session_search` mechanism marker"),
        ("USER.md", "must state the draft never writes USER.md (durable-profile guard)"),
    ):
        if needle not in text:
            hits.append(f"{rel}: hermes-prior-session: {message}")
    return hits


CHECKS = {
    "adapter-sections": scan_adapter_sections,
    "manifest-parse": scan_manifest_parse,
    "skill-frontmatter": scan_skill_frontmatter,
    "adapter-cross-refs": scan_adapter_cross_refs,
    "codex-workspace-write": scan_codex_workspace_write,
    "codex-parallel-subagents": scan_codex_parallel_subagents,
    "runtime-bundle": scan_runtime_bundle,
    "hermes-runtime-invocation": scan_hermes_runtime_invocation,
    "hermes-prior-session": scan_hermes_prior_session,
}


def scan(root, only=None):
    """Return hits (a list of 'path: <check>: <detail>' strings) across all CHECKS.
    Pass `only` (a name or iterable) to restrict the run to the named check(s) — used by unit tests."""
    if isinstance(only, str):
        only = [only]
    hits = []
    for name, fn in CHECKS.items():
        if only and name not in only:
            continue
        hits += fn(root)
    return hits


def main():
    ap = argparse.ArgumentParser(description="Structural validation of the platform adapter layer.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--only", action="append", help="run only the named check(s); repeatable")
    args = ap.parse_args()
    hits = scan(args.root, only=args.only)
    if hits:
        print("Platform validation FAILED:")
        print("\n".join(hits))
        return 1
    print("Platform validation: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
