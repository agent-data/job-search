#!/usr/bin/env python3
"""cli.py — job-search deterministic state-ops runtime.

Invoked by a host (on Hermes, via the terminal tool) as a file:
    python3 ${HERMES_SKILL_DIR}/scripts/hermes_job_search/cli.py <command> [flags]
Run as a file, this dir is sys.path[0], so siblings import by plain name (no __init__.py, no -m;
module names never shadow stdlib). Every command prints exactly ONE JSON object to stdout, sends any
diagnostics to stderr, and exits 0 (ok) / non-0 (failure). Judgment stays in the model; this layer
only does deterministic bookkeeping (workspace/registry/log/digest).
"""
import argparse
import json
import os
import sys

import config_yaml
import digest
import events
import paths
import records
import registry
from errors import JobSearchError


def _emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _config_path(args):
    if args.config:
        return args.config
    if args.workspace:
        return os.path.join(args.workspace, "config.yaml")
    raise JobSearchError("usage", "provide --workspace or --config")


def _jobs_path(args):
    if args.jobs:
        return args.jobs
    if args.workspace:
        return os.path.join(args.workspace, "jobs.jsonl")
    raise JobSearchError("usage", "provide --jobs or --workspace")


def cmd_discover_workspace(args):
    _emit({"ok": True, **registry.resolve(args.registry, args.default_workspace, args.legacy_workspace)})


def cmd_read_registry(args):
    path = paths.registry_path(args.registry)
    _emit({"ok": True, "registry": registry.read_registry(path), "path": path})


def cmd_set_active_workspace(args):
    _emit({"ok": True, "registry": registry.set_active(args.workspace, args.registry)})


def cmd_set_scheduling(args):
    sched = registry.set_scheduling(args.mechanism, args.set_at, args.job_id, args.deliver, args.registry)
    _emit({"ok": True, "scheduling": sched})


def cmd_clear_scheduling(args):
    _emit({"ok": True, "scheduling": registry.clear_scheduling(args.registry)})


def cmd_load_config(args):
    path = _config_path(args)
    _emit({"ok": True, "config": config_yaml.load_config(path), "path": path})


def cmd_update_config(args):
    path = _config_path(args)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise JobSearchError("E-NO-CONFIG", "No config.yaml found at {}.".format(path))
    changed = []
    for pair in (args.set or []):
        key, _, value = pair.partition("=")
        text = config_yaml.set_scalar(text, key.strip(), value)
        changed.append(key.strip())
    if args.add_query:
        text = config_yaml.add_query(text, json.loads(sys.stdin.read()))
        changed.append("queries[+]")
    paths.atomic_write(path, text)
    _emit({"ok": True, "path": path, "changed": changed})


def cmd_known_ids(args):
    ids = events.known_ids(events.read_events(_jobs_path(args)))
    _emit({"ok": True, "known_ids": ids, "count": len(ids)})


def cmd_append_event(args):
    raw = args.event if args.event is not None else sys.stdin.read()
    try:
        event = json.loads(raw)
    except ValueError as exc:
        raise JobSearchError("event_invalid", "event is not valid JSON: {}".format(exc))
    sid = events.append_event(_jobs_path(args), event)
    _emit({"ok": True, "appended": True, "source_id": sid})


def cmd_fold_state(args):
    folded = events.fold(events.read_events(_jobs_path(args)))
    _emit({"ok": True, "records": folded, "tally": events.tally(folded)})


def cmd_write_run_record(args):
    record = json.loads(sys.stdin.read())
    path = records.write_run_record(args.workspace, record)
    _emit({"ok": True, "path": path, "run_health": record.get("run_health")})


def cmd_write_digest(args):
    payload = json.loads(sys.stdin.read())
    date = args.date or payload.get("date") or paths.local_date()
    path = digest.write_digest(args.workspace, date, payload)
    _emit({"ok": True, "path": path, "run_health": payload.get("run_health")})


def build_parser():
    p = argparse.ArgumentParser(prog="hermes_job_search",
                                description="job-search deterministic state-ops runtime")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON (always on)")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover-workspace", help="resolve the active workspace + first_run + source")
    d.add_argument("--registry")
    d.add_argument("--default-workspace")
    d.add_argument("--legacy-workspace")
    d.set_defaults(func=cmd_discover_workspace)

    rr = sub.add_parser("read-registry", help="print the registry object (or null) + its resolved path")
    rr.add_argument("--registry")
    rr.set_defaults(func=cmd_read_registry)

    sa = sub.add_parser("set-active-workspace", help="record the active workspace in the registry")
    sa.add_argument("--workspace", required=True)
    sa.add_argument("--registry")
    sa.set_defaults(func=cmd_set_active_workspace)

    ss = sub.add_parser("set-scheduling", help="set the scheduling marker (default mechanism hermes-cron)")
    ss.add_argument("--mechanism", default="hermes-cron")
    ss.add_argument("--set-at")
    ss.add_argument("--job-id")
    ss.add_argument("--deliver")
    ss.add_argument("--registry")
    ss.set_defaults(func=cmd_set_scheduling)

    cs = sub.add_parser("clear-scheduling", help="clear the scheduling marker (turn-off)")
    cs.add_argument("--registry")
    cs.set_defaults(func=cmd_clear_scheduling)

    lc = sub.add_parser("load-config", help="parse config.yaml (E-NO-CONFIG / E-CONFIG-VERSION)")
    lc.add_argument("--workspace")
    lc.add_argument("--config")
    lc.set_defaults(func=cmd_load_config)

    uc = sub.add_parser("update-config", help="surgical config edits (preserve comments)")
    uc.add_argument("--workspace")
    uc.add_argument("--config")
    uc.add_argument("--set", action="append", metavar="KEY=VALUE", help="set an allow-listed scalar key")
    uc.add_argument("--add-query", action="store_true", help="append one query item (JSON on stdin)")
    uc.set_defaults(func=cmd_update_config)

    ki = sub.add_parser("known-ids", help="deduped source_id set from jobs.jsonl (the dedup set)")
    ki.add_argument("--jobs")
    ki.add_argument("--workspace")
    ki.set_defaults(func=cmd_known_ids)

    ae = sub.add_parser("append-event", help="validate + append one event (JSON on stdin or --event)")
    ae.add_argument("--jobs")
    ae.add_argument("--workspace")
    ae.add_argument("--event")
    ae.set_defaults(func=cmd_append_event)

    fs = sub.add_parser("fold-state", help="fold jobs.jsonl into current records + a status tally")
    fs.add_argument("--jobs")
    fs.add_argument("--workspace")
    fs.set_defaults(func=cmd_fold_state)

    wr = sub.add_parser("write-run-record", help="write runs/<run_id>.json (record JSON on stdin)")
    wr.add_argument("--workspace", required=True)
    wr.set_defaults(func=cmd_write_run_record)

    wd = sub.add_parser("write-digest", help="render+write reports/<date>-digest.md (payload JSON on stdin)")
    wd.add_argument("--workspace", required=True)
    wd.add_argument("--date")
    wd.set_defaults(func=cmd_write_digest)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
        return 0
    except JobSearchError as e:
        _emit({"ok": False, "error": e.code, "message": e.message})
        sys.stderr.write("{}: {}\n".format(e.code, e.message))
        return 1


if __name__ == "__main__":
    sys.exit(main())
