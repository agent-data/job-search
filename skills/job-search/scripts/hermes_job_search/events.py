"""events.py — deterministic operations on the jobs.jsonl append-only event log (stdlib only).

Current state = fold events by source_id (last-write-wins per field). Adapted from the repo's prior
scripts/state.py. The log is append-only, so append_event uses append mode (not a whole-file replace);
every other state file the runtime owns is written atomically (see paths.atomic_write).
"""
import json
import os

from errors import JobSearchError


def read_events(path):
    try:
        with open(path, encoding="utf-8") as f:
            events = []
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except ValueError as exc:
                    raise JobSearchError("jobs_malformed_json", "malformed JSON at line {}: {}".format(i, exc))
            return events
    except FileNotFoundError:
        return []  # missing log = empty set


def known_ids(events):
    seen, ordered = set(), []
    for e in events:
        sid = e.get("source_id")
        if sid and sid not in seen:
            seen.add(sid)
            ordered.append(sid)
    return ordered


def append_event(path, event):
    if not isinstance(event, dict) or not event.get("source_id"):
        raise JobSearchError("event_invalid", "event must be a JSON object with a non-empty source_id")
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")  # one single-line event
    return event["source_id"]


def fold(events):
    state = {}  # source_id -> merged record (dict preserves first-seen order)
    for e in events:
        sid = e.get("source_id")
        if not sid:
            continue
        rec = state.setdefault(sid, {})
        for k, v in e.items():
            if k != "event":
                rec[k] = v  # later events override
    return list(state.values())


def tally(records):
    by_status, needs_human_check = {}, 0
    for r in records:
        status = r.get("status")
        if status:
            by_status[status] = by_status.get(status, 0) + 1
        if r.get("needs_human_check") is True:
            needs_human_check += 1
    return {"by_status": by_status, "needs_human_check": needs_human_check, "total": len(records)}
