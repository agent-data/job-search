#!/usr/bin/env python3
"""state.py — deterministic operations on a jobs.jsonl append-only event log.

Current state = fold events by source_id (last-write-wins per field).
Subcommands: known-ids | append | fold.  Stdlib only.
"""
import argparse, json, sys


def read_events(path):
    try:
        with open(path, encoding="utf-8") as f:
            out = []
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
            return out
    except FileNotFoundError:
        return []


def known_ids(events):
    seen, ordered = set(), []
    for e in events:
        sid = e.get("source_id")
        if sid and sid not in seen:
            seen.add(sid)
            ordered.append(sid)
    return ordered


def cmd_known_ids(args):
    for sid in known_ids(read_events(args.jobs)):
        print(sid)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="jobs.jsonl operations")
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("known-ids", help="print one source_id per line (deduped)")
    k.add_argument("--jobs", required=True)
    k.set_defaults(func=cmd_known_ids)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
