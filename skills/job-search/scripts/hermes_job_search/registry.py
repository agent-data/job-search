"""registry.py — registry read/write/resolve + scheduling marker (stdlib only).

The registry is machine-managed OS state (JSON); the workspace's config.yaml stays user-facing.
Adapted from the repo's prior scripts/osctl.py, with two corrections: the registry dir is
`job-search` (in paths.py), and every write goes through paths.write_json (atomic os.replace).
"""
import os
from datetime import datetime, timezone

import paths
from errors import JobSearchError

REGISTRY_VERSION = 1


def read_registry(path):
    """Parsed object, or None if absent. A corrupt registry stops loudly — never fall through
    (guessing could silently switch the user's workspace)."""
    try:
        with open(path, encoding="utf-8") as f:
            import json
            return json.load(f)
    except FileNotFoundError:
        return None
    except ValueError as exc:  # json.JSONDecodeError is a ValueError
        raise JobSearchError("registry_invalid_json", "registry at {} is not valid JSON: {}".format(path, exc))


def write_registry(path, data):
    paths.write_json(path, data)


def resolve(registry_override=None, default_ws=None, legacy_ws=None):
    """Workspace discovery precedence: registry (wins unconditionally) > default > legacy > first-run."""
    default_ws = default_ws if default_ws is not None else paths.default_workspace()
    legacy_ws = legacy_ws if legacy_ws is not None else paths.legacy_workspace()
    reg = read_registry(paths.registry_path(registry_override))
    if reg and reg.get("active_workspace"):
        ws = reg["active_workspace"]
        return {"workspace": ws, "first_run": not paths.has_config(ws), "source": "registry"}
    if paths.has_config(default_ws):
        return {"workspace": default_ws, "first_run": False, "source": "default"}
    if paths.has_config(legacy_ws):
        return {"workspace": legacy_ws, "first_run": False, "source": "legacy"}
    return {"workspace": default_ws, "first_run": True, "source": "none"}


def set_active(workspace, registry_override=None):
    """Record the active workspace; writes ONLY the registry, preserving any keys we don't own."""
    path = paths.registry_path(registry_override)
    reg = read_registry(path) or {"version": REGISTRY_VERSION}
    reg["version"] = REGISTRY_VERSION
    reg["active_workspace"] = os.path.abspath(os.path.expanduser(workspace))
    write_registry(path, reg)
    return reg


def read_scheduling(registry_override=None):
    reg = read_registry(paths.registry_path(registry_override)) or {}
    return reg.get("scheduling") or {"installed": False, "mechanism": None, "set_at": None}


def set_scheduling(mechanism="hermes-cron", set_at=None, job_id=None, deliver=None, registry_override=None):
    """Set the scheduling marker. mechanism defaults to hermes-cron; job_id/deliver are optional
    additive fields (a Claude `loop` registry without them still round-trips)."""
    path = paths.registry_path(registry_override)
    reg = read_registry(path) or {"version": REGISTRY_VERSION}
    reg["version"] = REGISTRY_VERSION
    sched = {
        "installed": True,
        "mechanism": mechanism,
        "set_at": set_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if job_id:
        sched["job_id"] = job_id
    if deliver:
        sched["deliver"] = deliver
    reg["scheduling"] = sched
    write_registry(path, reg)
    return sched


def clear_scheduling(registry_override=None):
    """Turn-off: clear the marker, preserving version + active_workspace."""
    path = paths.registry_path(registry_override)
    reg = read_registry(path) or {"version": REGISTRY_VERSION}
    reg["version"] = REGISTRY_VERSION
    reg["scheduling"] = {"installed": False, "mechanism": None, "set_at": None}
    write_registry(path, reg)
    return reg["scheduling"]
