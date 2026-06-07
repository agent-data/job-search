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


def scan(root, strict_fresh=False):
    """Return (hits, warnings). hits fail the lint; warnings are advisory.

    Each rule is a scan_<rule>(root) -> list[str] of "path:line: <rule>: <detail>" strings,
    appended here. No rules are implemented yet (the skeleton is always clean)."""
    hits, warnings = [], []
    # later tasks append rule results here, e.g.:
    #   hits += scan_internal_links(root)
    return hits, warnings


def main():
    ap = argparse.ArgumentParser(description="Lint the in-repo documentation knowledge base.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--strict-fresh", action="store_true",
                    help="escalate staleness warnings to failures (for an on-demand freshness sweep)")
    args = ap.parse_args()
    hits, warnings = scan(args.root, strict_fresh=args.strict_fresh)
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
