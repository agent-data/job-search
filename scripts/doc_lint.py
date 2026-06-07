#!/usr/bin/env python3
"""Doc lint: validate the in-repo knowledge base (AGENTS.md + docs/**) is structured,
cross-linked, fresh, and does not duplicate the shared/references single source of truth.

Mirrors scripts/philosophy_guard.py in shape: scan(root) -> (hits, warnings); main() prints
hits and returns 1 on failure, else prints "Doc lint: clean." and returns 0. Stdlib only.

Rules are added one per task as scan_* functions called from scan(). This skeleton has none yet.
"""
import argparse, os, re, sys

# Canonical names the knowledge base must cover (used by later rules, e.g. quality-score-coverage).
DOMAINS = ("discovery-search", "preferences-judgment", "workspace-state",
           "scheduling-consent", "error-surfacing")
LAYERS = ("deterministic-core", "shared-references", "skill-layer", "hooks-guards", "tests-evals")

# The knowledge base = these root files + everything under docs/. Nothing else is scanned.
KB_FILES = ("AGENTS.md", "CLAUDE.md", "ARCHITECTURE.md")
KB_DIRS = ("docs",)
LINK_RE = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")


def iter_md_files(root):
    """Yield absolute paths of every Markdown file in the knowledge base under `root`."""
    for name in KB_FILES:
        p = os.path.join(root, name)
        if os.path.isfile(p):
            yield p
    for d in KB_DIRS:
        base = os.path.join(root, d)
        for dirpath, _, files in os.walk(base):
            for fn in files:
                if fn.endswith(".md"):
                    yield os.path.join(dirpath, fn)


def parse_links(text):
    """Return [(target, line_no)] for every inline Markdown link in `text`."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for m in LINK_RE.finditer(line):
            out.append((m.group(1), i))
    return out


def slugify(heading):
    """GitHub-style heading slug: lowercase, drop punctuation, spaces->hyphens."""
    s = heading.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def _headings(text):
    return {slugify(m.group(1)) for line in text.splitlines()
            for m in [HEADING_RE.match(line)] if m}


def scan_internal_links(root):
    """Every repo-relative Markdown link and #anchor must resolve. http(s)/mailto skipped."""
    hits = []
    for path in iter_md_files(root):
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        own_headings = _headings(text)
        for target, line in parse_links(text):
            if re.match(r"^(https?:|mailto:)", target):
                continue
            rel = os.path.relpath(path, root)
            pathpart, _, anchor = target.partition("#")
            if pathpart == "":            # same-file anchor
                if anchor and slugify(anchor) not in own_headings:
                    hits.append(f"{rel}:{line}: internal-links: no heading for anchor #{anchor}")
                continue
            if pathpart.startswith("/"):  # repo-root-relative
                tgt = os.path.join(root, pathpart.lstrip("/"))
            else:                          # relative to this file
                tgt = os.path.normpath(os.path.join(os.path.dirname(path), pathpart))
            if not os.path.exists(tgt):
                hits.append(f"{rel}:{line}: internal-links: broken link to {target}")
                continue
            if anchor and tgt.endswith(".md"):
                with open(tgt, encoding="utf-8", errors="replace") as tf:
                    if slugify(anchor) not in _headings(tf.read()):
                        hits.append(f"{rel}:{line}: internal-links: no heading for anchor in {target}")
    return hits


AGENTS_MAX_LINES = 150
REQUIRED_AGENTS_LINKS = (
    "ARCHITECTURE.md",
    "docs/design-docs/index.md",
    "docs/design-docs/core-beliefs.md",
    "docs/exec-plans/index.md",
    "docs/product-specs/index.md",
    "docs/QUALITY_SCORE.md",
    "docs/PRODUCT_SENSE.md",
    "docs/RELIABILITY.md",
    "docs/SECURITY.md",
    "docs/INTERFACE.md",
    "docs/PLANS.md",
    "shared/references",
)


def scan_agents_map(root):
    """AGENTS.md must exist (when a KB is present), stay under a size budget, and link to every pillar."""
    path = os.path.join(root, "AGENTS.md")
    has_kb = os.path.isdir(os.path.join(root, "docs"))
    if not os.path.isfile(path):
        return ["AGENTS.md: agents-map: AGENTS.md is missing (the KB entry point)"] if has_kb else []
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    hits = []
    n = len(text.splitlines())
    if n > AGENTS_MAX_LINES:
        hits.append(f"AGENTS.md: agents-map: too large ({n} lines > {AGENTS_MAX_LINES}); keep it a map")
    targets = [t for t, _ in parse_links(text)]
    for req in REQUIRED_AGENTS_LINKS:
        if not any(req in t for t in targets):
            hits.append(f"AGENTS.md: agents-map: missing required pointer to {req}")
    return hits


def scan(root, strict_fresh=False, only=None):
    """Return (hits, warnings). hits fail the lint; warnings are advisory.

    Each rule is a scan_<rule>(root) -> list[str] of "path:line: <rule>: <detail>" strings.
    Rules are dispatched through the ordered RULES registry so unit tests can target one rule
    via --only; pass `only` to restrict the run to the named rule(s)."""
    hits, warnings = [], []
    for name, fn in RULES.items():
        if only and name not in only:
            continue
        hits += fn(root)
    return hits, warnings


RULES = {
    "internal-links": scan_internal_links,
    "agents-map": scan_agents_map,
}


def main():
    ap = argparse.ArgumentParser(description="Lint the in-repo documentation knowledge base.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--strict-fresh", action="store_true",
                    help="escalate staleness warnings to failures (for an on-demand freshness sweep)")
    ap.add_argument("--only", action="append", help="run only the named rule(s); repeatable")
    args = ap.parse_args()
    hits, warnings = scan(args.root, strict_fresh=args.strict_fresh, only=args.only)
    for w in warnings:
        print(f"warning: {w}")
    if hits:
        print("Doc lint FAILED:")
        print("\n".join(hits))
        return 1
    print("Doc lint: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
