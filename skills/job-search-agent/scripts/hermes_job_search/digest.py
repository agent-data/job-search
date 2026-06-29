"""digest.py — render + write reports/<date>-digest.md in the fixed conventions.md format.

The runtime owns only STRUCTURE + counts; the qualitative prose (titles, one-line reasoning,
confirm questions, filtered reasons, footnotes) is supplied by the model. Because the renderer emits
only structure and tallies, it structurally cannot introduce a numeric ranking of its own.
"""
import os

import paths


def _health_line(payload):
    health = payload.get("run_health", "healthy")
    if health == "partial":
        return "partial ({} errors)".format(payload.get("error_count", 0))
    if health == "degraded":
        return "degraded (LinkedIn flaky)"
    if health == "blocked":
        return "blocked (action needed)"
    return "healthy"


def _match_block(lines, label, items):
    if not items:
        return
    lines.append("")
    lines.append("## {}".format(label))
    for it in items:
        lines.append("- **{}** — {} — {}".format(it.get("title", ""), it.get("company", ""), it.get("location", "")))
        lines.append("  {}  [view]({})".format(it.get("reasoning", "").rstrip(), it.get("url", "")))
        if it.get("confirm"):
            lines.append("  ⚠ confirm: {}".format(it["confirm"]))


def render(payload):
    date = payload.get("date", "")
    lines = ["# Job search digest — {}".format(date), "Run health: {}".format(_health_line(payload))]

    if payload.get("run_health") == "blocked":
        err = payload.get("error", {})
        lines += ["", "**{}** — {}".format(err.get("code", ""), err.get("message", ""))]
        return "\n".join(lines) + "\n"

    c = payload.get("counts", {})
    lines.append("{} new postings · {} strong · {} moderate · {} weak · {} filtered out · {} searches · {} detail reads".format(
        c.get("new", 0), c.get("strong", 0), c.get("moderate", 0), c.get("weak", 0),
        c.get("filtered", 0), c.get("searches", 0), c.get("detail_reads", 0)))

    _match_block(lines, "Strong matches", payload.get("strong", []))
    _match_block(lines, "Moderate matches", payload.get("moderate", []))
    _match_block(lines, "Weak matches", payload.get("weak", []))

    filtered = payload.get("filtered", [])
    lines += ["", "## Filtered out (not relevant): {}".format(len(filtered))]
    for it in filtered:
        lines.append("- {} — {} — {}".format(it.get("title", ""), it.get("company", ""), it.get("why", "")))

    notes = payload.get("notes", [])
    if notes:
        lines += ["", "---", "_Notes:_"]
        lines += ["- {}".format(n) for n in notes]

    return "\n".join(lines) + "\n"


def write_digest(workspace, date, payload):
    payload = dict(payload)
    payload.setdefault("date", date)
    path = os.path.join(workspace, "reports", "{}-digest.md".format(date))
    paths.atomic_write(path, render(payload))
    return path
