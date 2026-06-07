#!/usr/bin/env python3
"""Doc lint: validate the in-repo knowledge base (AGENTS.md + docs/**) is structured,
cross-linked, fresh, and does not duplicate the shared/references single source of truth.

Mirrors scripts/philosophy_guard.py in shape: scan(root) -> (hits, warnings); main() prints
hits and returns 1 on failure, else prints "Doc lint: clean." and returns 0. Stdlib only.

Rules are scan_* functions dispatched via the RULES registry (currently 9: internal-links, agents-map, frontmatter-schema, code-refs-exist, no-shared-reference-duplication, index-completeness, quality-score-coverage, plan-location, freshness-markers).
"""
import argparse, datetime, os, re, sys

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
    """GitHub-style heading slug (github-slugger): lowercase, drop chars not in [\\w\\s-], then each
    whitespace char -> '-'. Does NOT collapse consecutive hyphens (a heading like 'A — B' yields
    'a--b') and does NOT strip leading/trailing hyphens — both matching github-slugger exactly."""
    s = heading.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s", "-", s)


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


def read_frontmatter(path):
    """Parse a leading --- ... --- block into {key: str|list}. Returns None if absent/unterminated.
    Not full YAML: supports flat 'key: value' and 'key: [a, b]' (our known, controlled schema)."""
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fm = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fm
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            fm[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
        else:
            fm[key] = val.strip("'\"")
    return None  # unterminated frontmatter => treat as missing


STATUS_ENUM = {"current", "superseded", "historical", "aspirational"}
VERIFIED_ENUM = {"verified", "partial", "unverified"}
STATE_ENUM = {"active", "completed", "abandoned"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VERIFICATION_DIRS = ("docs/design-docs", "docs/product-specs")
PLAN_DIRS = ("docs/exec-plans/active", "docs/exec-plans/completed")


def _under(path, root, prefix):
    rel = os.path.relpath(path, root)
    return rel == prefix or rel.startswith(prefix + os.sep)


def scan_frontmatter(root):
    """design-docs & product-specs need verification frontmatter; plans need state frontmatter."""
    hits = []
    for path in iter_md_files(root):
        rel = os.path.relpath(path, root)
        if os.path.basename(path) == "index.md":
            continue
        is_verif = any(_under(path, root, d) for d in VERIFICATION_DIRS)
        is_plan = any(_under(path, root, d) for d in PLAN_DIRS)
        if not (is_verif or is_plan):
            continue
        fm = read_frontmatter(path)
        if fm is None:
            hits.append(f"{rel}: frontmatter-schema: missing or malformed frontmatter block")
            continue

        def _missing(key):
            # absent, or present but an empty STRING (e.g. `status:`). An empty list
            # (`code_refs: []`) is allowed by the schema, so empty lists are NOT missing.
            v = fm.get(key)
            return key not in fm or (isinstance(v, str) and v.strip() == "")

        if is_verif:
            for k in ("title", "status", "verified", "last_reviewed", "code_refs"):
                if _missing(k):
                    hits.append(f"{rel}: frontmatter-schema: missing required key '{k}'")
            if fm.get("status") and fm["status"] not in STATUS_ENUM:
                hits.append(f"{rel}: frontmatter-schema: status '{fm['status']}' not in {sorted(STATUS_ENUM)}")
            if fm.get("verified") and fm["verified"] not in VERIFIED_ENUM:
                hits.append(f"{rel}: frontmatter-schema: verified '{fm['verified']}' not in {sorted(VERIFIED_ENUM)}")
            if fm.get("last_reviewed") and not DATE_RE.match(str(fm["last_reviewed"])):
                hits.append(f"{rel}: frontmatter-schema: last_reviewed '{fm['last_reviewed']}' is not YYYY-MM-DD")
            if "code_refs" in fm and not isinstance(fm["code_refs"], list):
                hits.append(f"{rel}: frontmatter-schema: code_refs must be a list")
        if is_plan:
            for k in ("title", "state", "created"):
                if _missing(k):
                    hits.append(f"{rel}: frontmatter-schema: missing required key '{k}'")
            if fm.get("state") and fm["state"] not in STATE_ENUM:
                hits.append(f"{rel}: frontmatter-schema: state '{fm['state']}' not in {sorted(STATE_ENUM)}")
            if fm.get("created") and not DATE_RE.match(str(fm["created"])):
                hits.append(f"{rel}: frontmatter-schema: created '{fm['created']}' is not YYYY-MM-DD")
            if fm.get("state") == "completed" and "completed" not in fm:
                hits.append(f"{rel}: frontmatter-schema: completed plan must have a 'completed' date")
    return hits


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
        results = fn(root)
        if name == "freshness-markers":
            (hits if strict_fresh else warnings).extend(results)
        else:
            hits += results
    return hits, warnings


def scan_code_refs(root):
    """Every path in a design-doc / product-spec `code_refs:` list must exist in the repo."""
    hits = []
    for path in iter_md_files(root):
        if os.path.basename(path) == "index.md":
            continue
        if not any(_under(path, root, d) for d in VERIFICATION_DIRS):
            continue
        fm = read_frontmatter(path)
        if not fm or not isinstance(fm.get("code_refs"), list):
            continue  # frontmatter-schema already flags a missing / non-list code_refs
        rel = os.path.relpath(path, root)
        for ref in fm["code_refs"]:
            if not os.path.exists(os.path.join(root, ref)):
                hits.append(f"{rel}: code-refs-exist: code_ref does not exist: {ref}")
    return hits


# Distinctive literals OWNED by shared/references/*. A live KB doc reproducing one of these
# (without linking the source on the same line) is duplicating a contract that will drift.
DUP_SIGNATURES = [
    (re.compile(r"every-2-hours"), "frequency enum"),
    (re.compile(r"YYYY-MM-DDTHH-MM-SSZ"), "run_id format"),
    (re.compile(r"interested\W+applied\W+rejected"), "job status enum"),
    (re.compile(r"degraded \(LinkedIn flaky\)"), "run-health states"),
    (re.compile(r"strong\s*·\s*\d+\s*moderate"), "digest counts line"),
    (re.compile(r"desktop_notify_on_block"), "config field"),
    (re.compile(r"API limit for this period has been reached"), "E-QUOTA verbatim"),
]
DUP_ALLOW = re.compile(r"shared/references")  # a line that points to the source is fine


def _is_live_kb_doc(path, root):
    rel = os.path.relpath(path, root)
    if rel == "docs/exec-plans" or rel.startswith("docs/exec-plans" + os.sep):
        return False
    if rel == "docs/generated" or rel.startswith("docs/generated" + os.sep):
        return False
    fm = read_frontmatter(path)
    if fm and fm.get("status") in ("historical", "superseded"):
        return False
    return True


def scan_shared_dup(root):
    """Live KB docs must not restate shared/references contracts; link the source instead."""
    hits = []
    for path in iter_md_files(root):
        if not _is_live_kb_doc(path, root):
            continue
        rel = os.path.relpath(path, root)
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if DUP_ALLOW.search(line):
                    continue
                for rx, label in DUP_SIGNATURES:
                    if rx.search(line):
                        hits.append(f"{rel}:{i}: no-shared-reference-duplication: "
                                    f"{label} restated without linking shared/references")
    return hits


INDEX_DIRS = ("docs/design-docs", "docs/product-specs", "docs/exec-plans")


def scan_indexes(root):
    """Each section index.md must link every sibling .md under its tree (no missing entries)."""
    hits = []
    for d in INDEX_DIRS:
        index = os.path.join(root, d, "index.md")
        if not os.path.isfile(index):
            continue
        with open(index, encoding="utf-8", errors="replace") as f:
            text = f.read()
        linked = set()
        for target, _ in parse_links(text):
            if re.match(r"^(https?:|mailto:)", target):
                continue
            pathpart = target.split("#")[0]
            if pathpart:
                linked.add(os.path.normpath(os.path.join(os.path.dirname(index), pathpart)))
        base = os.path.join(root, d)
        for dirpath, _, files in os.walk(base):
            for fn in files:
                if not fn.endswith(".md") or fn == "index.md":
                    continue
                sib = os.path.normpath(os.path.join(dirpath, fn))
                if sib not in linked:
                    hits.append(f"{os.path.relpath(index, root)}: index-completeness: "
                                f"missing link to {os.path.relpath(sib, root)}")
    return hits


QS_GRADES = ("strong", "adequate", "thin", "missing")


def scan_quality_score(root):
    """QUALITY_SCORE.md must grade every canonical domain and layer (id + a grade word) and have a gaps field."""
    path = os.path.join(root, "docs", "QUALITY_SCORE.md")
    if not os.path.isfile(path):
        return ["docs/QUALITY_SCORE.md: quality-score-coverage: file is missing"] \
            if os.path.isdir(os.path.join(root, "docs")) else []
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    hits = []
    for name in DOMAINS + LAYERS:
        if not any(name in ln and any(g in ln.lower() for g in QS_GRADES) for ln in lines):
            hits.append(f"docs/QUALITY_SCORE.md: quality-score-coverage: "
                        f"no graded entry for '{name}' (need the id + a grade word in {QS_GRADES})")
    if not any("gap" in ln.lower() for ln in lines):
        hits.append("docs/QUALITY_SCORE.md: quality-score-coverage: no 'gaps' column/section found")
    return hits


EXEC_PLANS = "docs/exec-plans"
EXEC_ROOT_ALLOWED = {"index.md", "tech-debt-tracker.md"}


def scan_plan_location(root):
    """A plan's state must match its directory; no loose plan files in the exec-plans/ root."""
    hits = []
    base = os.path.join(root, EXEC_PLANS)
    if not os.path.isdir(base):
        return hits
    for fn in sorted(os.listdir(base)):
        full = os.path.join(base, fn)
        if os.path.isfile(full) and fn.endswith(".md") and fn not in EXEC_ROOT_ALLOWED:
            hits.append(f"{EXEC_PLANS}/{fn}: plan-location: loose plan in exec-plans/ root "
                        f"(move it into active/ or completed/)")
    for sub in ("active", "completed"):
        d = os.path.join(base, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".md") or fn == "index.md":
                continue
            fm = read_frontmatter(os.path.join(d, fn)) or {}
            if fm.get("state") != sub:
                hits.append(f"{EXEC_PLANS}/{sub}/{fn}: plan-location: state "
                            f"{fm.get('state')!r} does not match its directory ({sub})")
    return hits


FRESH_DAYS = 90


def scan_freshness(root):
    """Warn when a design-doc / product-spec's last_reviewed is older than FRESH_DAYS.
    Returned items are routed to WARNINGS by default and to HITS under --strict-fresh (see scan())."""
    out = []
    today = datetime.date.today()
    for path in iter_md_files(root):
        if os.path.basename(path) == "index.md":
            continue
        if not any(_under(path, root, d) for d in VERIFICATION_DIRS):
            continue
        fm = read_frontmatter(path) or {}
        lr = fm.get("last_reviewed")
        if not lr or not DATE_RE.match(str(lr)):
            continue  # missing / malformed dates are the frontmatter-schema rule's job
        try:
            reviewed = datetime.date.fromisoformat(str(lr))
        except ValueError:
            continue
        age = (today - reviewed).days
        if age > FRESH_DAYS:
            out.append(f"{os.path.relpath(path, root)}: freshness-markers: "
                       f"last_reviewed {lr} is {age} days old (> {FRESH_DAYS}); re-review and bump the date")
    return out


RULES = {
    "internal-links": scan_internal_links,
    "agents-map": scan_agents_map,
    "frontmatter-schema": scan_frontmatter,
    "code-refs-exist": scan_code_refs,
    "no-shared-reference-duplication": scan_shared_dup,
    "index-completeness": scan_indexes,
    "quality-score-coverage": scan_quality_score,
    "plan-location": scan_plan_location,
    "freshness-markers": scan_freshness,
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
