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
import sys

import paths
import registry
from errors import JobSearchError


def _emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")


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
