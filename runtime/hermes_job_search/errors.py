"""errors.py — JSON result envelope + named error for the job-search state-ops runtime.

Every command returns one of these envelopes on stdout: success -> {"ok": true, ...}, failure ->
{"ok": false, "error": "<code>", "message": "<human>"}. Judgment never lives here — this layer only
does deterministic bookkeeping (workspace/registry/log/digest), never qualitative ranking.
"""


class JobSearchError(Exception):
    """A named, surfaced failure — never a silent one. Carries a stable code + human message."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def ok(**fields):
    return {"ok": True, **fields}


def fail(code, message):
    return {"ok": False, "error": code, "message": message}
