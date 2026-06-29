"""paths.py — workspace/registry path resolution + atomic whole-file writes (stdlib only).

Path defaults are redirectable for tests/evals without touching real data, via flags or env:
  registry:   --registry  >  $JOBSEARCH_OS_REGISTRY  >  $XDG_CONFIG_HOME/job-search/config.json  >  ~/.config/...
  workspaces: --default-workspace/--legacy-workspace  >  derived from $JOBSEARCH_OS_HOME  >  ~

This mirrors shared/references/internals.md exactly. NOTE the registry dir is `job-search` (the
current contract), not the `job-search-os` of the now-deleted scripts/osctl.py.
"""
import json
import os
from datetime import datetime, timezone

CONFIG_NAME = "config.yaml"


def utc_run_id():
    """run_id format (conventions.md): UTC YYYY-MM-DDTHH-MM-SSZ — hyphens in the time, safe as a filename."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def local_date():
    """<date> for digests (conventions.md): local-tz YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def home():
    return os.environ.get("JOBSEARCH_OS_HOME") or os.path.expanduser("~")


def default_workspace():
    return os.path.join(home(), ".job-search")


def legacy_workspace():
    return os.path.join(home(), "job-search")


def registry_path(override=None):
    if override:
        return override
    if os.environ.get("JOBSEARCH_OS_REGISTRY"):
        return os.environ["JOBSEARCH_OS_REGISTRY"]
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home(), ".config")
    return os.path.join(xdg, "job-search", "config.json")


def has_config(workspace):
    return bool(workspace) and os.path.isfile(os.path.join(workspace, CONFIG_NAME))


def workspace_paths(workspace):
    return {
        "jobs": os.path.join(workspace, "jobs.jsonl"),
        "config": os.path.join(workspace, CONFIG_NAME),
        "runs_dir": os.path.join(workspace, "runs"),
        "reports_dir": os.path.join(workspace, "reports"),
    }


def atomic_write(path, text):
    """Whole-file replace, never a streamed/redirected partial: write a temp file in the same
    directory, fsync, then os.replace (atomic on a single filesystem). Mirrors the registry write
    rules in internals.md and protects every structured-state write the runtime owns."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = "{}.tmp.{}".format(path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_json(path, data):
    """2-space indent + trailing newline, written atomically (registry / run-record convention)."""
    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
