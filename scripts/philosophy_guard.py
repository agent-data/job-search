#!/usr/bin/env python3
"""Philosophy guard: fail if SHIPPED default-output artifacts contain a numeric fit score,
category weight, per-criterion points, or a budget/credit knob. Honored-on-request scores
live only in chat, never in committed artifacts — so this scans what we ship, not what a
user might ask for.

Scanned: examples/, templates/, and the shipped state-ops runtime/ (so the digest-writer can never
introduce a numeric score). Skipped: prose that DEFINES the philosophy (it names the forbidden things
to forbid them) and the source data field salary_display.
"""
import argparse, os, re, sys

SCAN_DIRS = ("examples", "templates", "runtime")
PATTERNS = [
    (re.compile(r"\bfit score\b", re.I), "fit score"),
    (re.compile(r"\b\d{1,3}\s*/\s*100\b"), "N/100 score"),
    (re.compile(r"\b0\s*[-–]\s*100\b"), "0-100 scale"),
    (re.compile(r"\bcategory weight", re.I), "category weight"),
    (re.compile(r"\b\d+\s*(points|pts)\b", re.I), "points"),
    # budget/credit are forbidden as a CONFIG FIELD or a cost KNOB, not as prose words:
    (re.compile(r"(?im)^\s*(budget|credits?|cost)\s*[:=]"), "budget/credit/cost config field"),
    (re.compile(r"\bbudget\s*(knob|cap)\b", re.I), "budget knob"),
    (re.compile(r"\bcredit\s*(math|cost|estimate|remaining|balance)\b", re.I), "credit math"),
    (re.compile(r"\b\d+\s*credits?\b", re.I), "credit count"),
]
ALLOW_LINE = re.compile(r"E-QUOTA|salary|\$\s?\d", re.I)


def scan(root):
    hits = []
    for d in SCAN_DIRS:
        base = os.path.join(root, d)
        for dirpath, _, files in os.walk(base):
            for fn in files:
                if not fn.endswith((".md", ".yaml", ".yml", ".py")):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if ALLOW_LINE.search(line):
                            continue
                        for rx, label in PATTERNS:
                            if rx.search(line):
                                hits.append(f"{os.path.relpath(path, root)}:{i}: {label}: {line.strip()}")
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    hits = scan(args.root)
    if hits:
        print("Philosophy guard FAILED — numeric score / budget language in shipped output:")
        print("\n".join(hits))
        return 1
    print("Philosophy guard: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
