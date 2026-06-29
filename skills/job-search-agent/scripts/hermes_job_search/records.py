"""records.py — write the per-run audit log runs/<run_id>.json (stdlib only).

The runtime owns the deterministic write (atomic, 2-space JSON); the model owns the record's
contents. Every HALT path writes a record with run_health "blocked" + a named error, so the home
view surfaces a failed scheduled run — the durable file channel named errors.md requires.
"""
import os

import paths
from errors import JobSearchError

VALID_HEALTH = ("healthy", "partial", "degraded", "blocked")


def write_run_record(workspace, record):
    run_id = record.get("run_id")
    if not run_id:
        raise JobSearchError("run_record_invalid", "run record must include a run_id")
    if record.get("run_health") not in VALID_HEALTH:
        raise JobSearchError("run_record_invalid",
                             "run_health must be one of {}".format(list(VALID_HEALTH)))
    path = os.path.join(workspace, "runs", "{}.json".format(run_id))
    paths.write_json(path, record)
    return path
