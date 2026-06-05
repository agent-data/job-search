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


def append_event(path, event):
    if not isinstance(event, dict) or not event.get("source_id"):
        raise ValueError("event must be a JSON object with a non-empty source_id")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def cmd_append(args):
    try:
        append_event(args.jobs, json.loads(args.event))
    except (ValueError, json.JSONDecodeError) as e:
        print(f"append failed: {e}", file=sys.stderr)
        return 1
    return 0


def fold(events):
    state = {}  # source_id -> merged record (insertion order preserved by dict)
    for e in events:
        sid = e.get("source_id")
        if not sid:
            continue
        rec = state.setdefault(sid, {})
        for k, v in e.items():
            if k != "event":
                rec[k] = v  # later events override present keys
    return list(state.values())


def cmd_fold(args):
    print(json.dumps(fold(read_events(args.jobs))))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="jobs.jsonl operations")
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("known-ids", help="print one source_id per line (deduped)")
    k.add_argument("--jobs", required=True)
    k.set_defaults(func=cmd_known_ids)
    a = sub.add_parser("append", help="append one event (must include source_id)")
    a.add_argument("--jobs", required=True)
    a.add_argument("--event", required=True, help="JSON object")
    a.set_defaults(func=cmd_append)
    f = sub.add_parser("fold", help="print current state as a JSON array (folded by source_id)")
    f.add_argument("--jobs", required=True)
    f.set_defaults(func=cmd_fold)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
