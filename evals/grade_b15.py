#!/usr/bin/env python3
"""Grade B15 over one or more eval transcripts: did every plugin file the agent opened
resolve on the first attempt, and did any miss cost a recovery search?

Usage: python3 evals/grade_b15.py evals/results/<run-dir> [<run-dir> ...]
       python3 evals/grade_b15.py --json evals/results/<run-dir>

Method (the C10 method of the 2026-07-30 matrix, widened so it cannot miss a shape):

* Every `Read` whose `file_path` sits under the plugin directory counts as an open.
* Every `Bash` command counts one open per whitespace-separated token that starts with the
  plugin directory and is not a directory — this catches `cat <path>`, `bash <path>`, and a
  bare `<path>` run as a script, which a Read-only sweep would not see.
* An open is a **miss** when its tool result came back an error, or when the path it named
  does not exist in the tree. Both are checked; either one counts.
* A `Glob`, `Grep`, `pwd`, or `ls` issued in the 60 seconds after a miss counts as a
  **recovery search** — the flailing C10 measured, not just the wasted call.

The plugin directory comes from the transcript's own `init` event, so a run recorded against
a different checkout is graded against the tree that was live for it. `--tree` overrides it
when the checkout has since moved (the pre-promotion baseline is graded from a worktree).

Also reported, for comparability with the 0.8.0 C10 rows: the **reference-and-template
subset**, the files C10 scoped itself to. Pre-promotion those live under `shared/references/`
and `templates/`; post-promotion the templates live under `skills/*/templates/` and the two
references are skills, reached by name — so a `Skill` call to `job-search:job-search-runbook`
or `job-search:agent-data-reference` counts as one resolution that cannot miss.
"""
import argparse, json, os, re, sys

REF_SKILLS = ("job-search:job-search-runbook", "job-search:agent-data-reference")
# The reference-and-template subset, in both trees: shared/references/… and templates/…
# before the restructure, skills/*/templates/… and the two reference SKILL.md files after.
REF_SUBSET = re.compile(
    r"(shared/references/|/templates/|^templates/"
    r"|skills/(job-search-runbook|agent-data-reference)/SKILL\.md)")
RECOVERY_BASH = re.compile(r"^\s*(pwd|ls)\b")
RECOVERY_WINDOW_S = 60.0


def events(transcript):
    """Yield (elapsed_seconds, parsed stream-json event) for one transcript."""
    with open(transcript) as f:
        for ln in f:
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            line = rec.get("line")
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            yield rec.get("t"), ev


def plugin_dir(transcript, name="job-search"):
    for _, ev in events(transcript):
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            for p in ev.get("plugins") or []:
                if p.get("name") == name:
                    return p.get("path", "").rstrip("/")
    return None


def init_skills(transcript, prefix="job-search:"):
    for _, ev in events(transcript):
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            return sorted(s for s in (ev.get("skills") or []) if s.startswith(prefix))
    return []


def bash_paths(command, root):
    """Every token in a shell command that names a file under the plugin directory."""
    out = []
    for tok in re.split(r"[\s;|&<>()\"']+", command or ""):
        tok = tok.rstrip(",")
        if tok.startswith(root + "/"):
            out.append(tok)
    return out


def grade(run_dir, tree=None):
    transcript = os.path.join(run_dir, "transcript.jsonl")
    if not os.path.isfile(transcript):
        return {"run": os.path.basename(run_dir), "error": "no transcript"}
    root = plugin_dir(transcript)
    if not root:
        return {"run": os.path.basename(run_dir), "error": "no plugin path in init event"}
    opens, recoveries, ref_hits, uses = [], [], [], {}
    tool_events = []  # (t, name, input) for every tool call, for the recovery window

    for t, ev in events(transcript):
        for b in (ev.get("message") or {}).get("content") or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                uses[b.get("id")] = (t, b.get("name"), b.get("input") or {})
                tool_events.append((t, b.get("name"), b.get("input") or {}))
                if b.get("name") == "Skill" and (b.get("input") or {}).get("skill") in REF_SKILLS:
                    ref_hits.append({"t": t, "skill": b["input"]["skill"]})
            elif b.get("type") == "tool_result":
                u = uses.get(b.get("tool_use_id"))
                if not u:
                    continue
                t0, name, inp = u
                if name == "Read" and str(inp.get("file_path", "")).startswith(root + "/"):
                    attempts = [inp["file_path"]]
                elif name == "Bash":
                    attempts = bash_paths(inp.get("command", ""), root)
                else:
                    continue
                err = bool(b.get("is_error"))
                for p in attempts:
                    if p.startswith(os.path.join(root, "evals") + os.sep):
                        continue  # the run's own scratch and results, not a plugin reference
                    resolved = p if not tree else os.path.join(tree, os.path.relpath(p, root))
                    if os.path.isdir(resolved):
                        continue  # a directory named in a shell command is not a file open
                    exists = os.path.isfile(resolved)
                    # A Bash call reports one exit status for the whole command, and a non-zero
                    # exit is usually the script's own verdict, not a path that did not resolve.
                    # Only a Read's error is evidence about the path; for Bash, existence decides.
                    miss = (not exists) if name == "Bash" else ((not exists) or err)
                    opens.append({"t": t0, "tool": name, "path": p,
                                  "exists": exists, "is_error": err, "miss": miss})

    for m in [o for o in opens if o["miss"]]:
        for t, name, inp in tool_events:
            if t is None or m["t"] is None or not (m["t"] < t <= m["t"] + RECOVERY_WINDOW_S):
                continue
            if name in ("Glob", "Grep") or (
                    name == "Bash" and RECOVERY_BASH.match(inp.get("command", ""))):
                recoveries.append({"t": t, "tool": name,
                                   "detail": (inp.get("pattern") or inp.get("command", ""))[:80],
                                   "after_miss_at": m["t"]})

    subset = [o for o in opens if REF_SUBSET.search(o["path"])]
    return {
        "run": os.path.basename(run_dir),
        "plugin_dir": root,
        "job_search_skills_loaded": init_skills(transcript),
        "opens": len(opens),
        "misses": sum(1 for o in opens if o["miss"]),
        "missed_paths": [o["path"] for o in opens if o["miss"]],
        "recovery_searches": len(recoveries),
        "recovery_detail": recoveries,
        "ref_template_opens": len(subset),
        "ref_template_misses": sum(1 for o in subset if o["miss"]),
        "reference_skill_calls": len(ref_hits),
        "b15_pass": sum(1 for o in opens if o["miss"]) == 0,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+")
    ap.add_argument("--tree", help="grade paths against this tree instead of the live one")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = [grade(d, args.tree) for d in args.run_dirs]
    if args.json:
        print(json.dumps(rows, indent=1))
        return
    for r in rows:
        if r.get("error"):
            print("%-46s %s" % (r["run"], r["error"]))
            continue
        print("%-46s opens %3d  misses %d  recovery %d  | ref+tpl %2d/%d miss  | ref-skill calls %d"
              % (r["run"], r["opens"], r["misses"], r["recovery_searches"],
                 r["ref_template_misses"], r["ref_template_opens"], r["reference_skill_calls"]))
        for p in r["missed_paths"]:
            print("      MISS", p)
    bad = [r for r in rows if not r.get("error") and not r["b15_pass"]]
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
