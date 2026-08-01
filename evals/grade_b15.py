#!/usr/bin/env python3
"""Grade B15 over one or more eval transcripts: did every plugin file the agent opened
resolve on the first attempt, and did any miss cost a recovery search?

Usage: python3 evals/grade_b15.py evals/results/<run-dir> [<run-dir> ...]
       python3 evals/grade_b15.py --json evals/results/<run-dir>

Method (the 2026-07-30 matrix's method, widened four times — each widening added because a
shape the grader could not see turned out to be present in the runs it had already graded):

* Every `Read` whose `file_path` sits under the plugin directory counts as an open, **including
  a Read aimed at a directory**, which returns EISDIR and is a real failed open. Discarding
  directories before checking the error hid that shape completely.
* Every `Bash` command counts one open per path it names under the plugin directory. Paths are
  followed through `cd`, so `cd <skill dir> && ./scripts/foo.sh` is one open on that script;
  keeping only tokens already rooted at the plugin directory sees nothing there. `=` splits as
  a separator, so a shell assignment `SCRIPT=/abs/path` yields the path and not a mangled token.
* A path the command text cannot show — assembled from a variable that expanded to nothing — is
  taken from the shell's own "No such file or directory" line. Absolute paths under the plugin
  directory are left to the command-text scan, so nothing is counted twice.
* An open is a **miss** when the path is not a file in the tree; a `Read` also misses when its
  result came back an error. A `Bash` non-zero exit does not count — that is usually the
  script's own verdict, not a path that failed to resolve.
* A `Glob`, `Grep`, `pwd`, `ls`, or `find` issued in the 60 seconds after a miss counts as a
  **recovery search** — the calls the agent spends hunting, not just the wasted one.

Restricted to the 2026-07-30 scope (Read only, on `shared/references/` and `templates/` paths)
this returns that matrix's published counts exactly: 1 of 11 and 2 of 6.

The plugin directory comes from the transcript's own `init` event, so a run recorded against
a different checkout is graded against the tree that was live for it. `--tree` overrides it
when the checkout has since moved (the pre-promotion baseline is graded from a worktree).

**This depends on where the graded session was standing.** Relative paths resolve against the
session's own cwd, and the branch that does it accepts any token containing a `/` — a `sed`
expression, `AI/ML`, an unexpanded `~/Library/LaunchAgents`. Those become candidate opens and
would each be counted a miss; today they are all discarded because `run_eval.py` puts every
session's cwd inside the plugin's own `evals/` tree, which this script skips. Point a session's
cwd anywhere else under the plugin and the false misses appear. The fix is to require a
candidate to look like a path before resolving it, rather than to depend on where the harness
stands; until then, re-check this script's output whenever the harness cwd moves.

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
RECOVERY_BASH = re.compile(r"^\s*(pwd|ls|find)\b")
RECOVERY_WINDOW_S = 60.0
# A shell reports a path it could not open. This is how a failed open is caught when the command
# text cannot show the path — built from a variable that expanded to nothing, most often.
SHELL_NOT_FOUND = re.compile(r"(\S+): No such file or directory")
# What makes a path plugin-internal even when it is not rooted at the plugin directory.
PLUGIN_SHAPED = re.compile(r"(^|/)(skills|shared|templates|scripts)/")
SEGMENT_SPLIT = re.compile(r"(?:&&|\|\||[;\n|])")
CD_SEGMENT = re.compile(r"^\s*cd\s+(\S+)")
GLOB_CHARS = set("*?[]{}$")


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


def session_cwd(transcript):
    """The directory the session starts in, which is what a relative path resolves against."""
    for _, ev in events(transcript):
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            return ev.get("cwd")
    return None


def init_skills(transcript, prefix="job-search:"):
    for _, ev in events(transcript):
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            return sorted(s for s in (ev.get("skills") or []) if s.startswith(prefix))
    return []


def bash_paths(command, root, cwd=None):
    """Every path a shell command names under the plugin directory, absolute or relative.

    A relative path is only visible once you know what directory the shell is standing in, so
    this walks the command segment by segment and follows `cd`. Without that,
    `cd <skill dir> && ./scripts/foo.sh` yields nothing, and that is a real failed open.
    """
    out, here = [], cwd
    for segment in SEGMENT_SPLIT.split(command or ""):
        moved = CD_SEGMENT.match(segment)
        if moved:
            target = moved.group(1).strip("\"'")
            here = target if os.path.isabs(target) else (
                os.path.normpath(os.path.join(here, target)) if here else None)
            continue
        # `=` splits too: a shell assignment like `SCRIPT=/abs/path` holds a real path, and
        # leaving it glued to the variable name makes the token look like a relative path.
        for tok in re.split(r"[\s<>()=\"']+", segment):
            tok = tok.strip().rstrip(",")
            if not tok or GLOB_CHARS & set(tok):
                continue
            if tok.startswith(root + "/"):
                out.append(os.path.normpath(tok))
            elif here and ("/" in tok) and not os.path.isabs(tok):
                resolved = os.path.normpath(os.path.join(here, tok.lstrip("./") if
                                                         tok.startswith("./") else tok))
                if resolved.startswith(root + "/"):
                    out.append(resolved)
    return out


def shell_reported_misses(result_text, root):
    """Plugin paths the shell said it could not open, taken from the command's own output.

    The input-side scan can only see paths the command spells out. A path assembled from a
    variable that expanded to nothing never appears there, and the only place it shows up is the
    error the shell printed. Absolute paths under the plugin directory are left to the input-side
    scan, so nothing is counted twice.
    """
    out = []
    for path in SHELL_NOT_FOUND.findall(result_text or ""):
        if path.startswith(root + "/"):
            continue  # the input-side scan already has this one
        if PLUGIN_SHAPED.search(path) and not path.startswith("./"):
            out.append(path)
    return out


def grade(run_dir, tree=None):
    transcript = os.path.join(run_dir, "transcript.jsonl")
    if not os.path.isfile(transcript):
        return {"run": os.path.basename(run_dir), "error": "no transcript"}
    root = plugin_dir(transcript)
    if not root:
        return {"run": os.path.basename(run_dir), "error": "no plugin path in init event"}
    cwd = session_cwd(transcript)
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
                body = b.get("content")
                body = body if isinstance(body, str) else json.dumps(body)
                err = bool(b.get("is_error"))
                if name == "Read" and str(inp.get("file_path", "")).startswith(root + "/"):
                    attempts = [(inp["file_path"], False)]
                elif name == "Bash":
                    attempts = [(p, False) for p in bash_paths(inp.get("command", ""), root, cwd)]
                    attempts += [(p, True) for p in shell_reported_misses(body, root)]
                else:
                    continue
                for p, from_shell_error in attempts:
                    if p.startswith(os.path.join(root, "evals") + os.sep):
                        continue  # the run's own scratch and results, not a plugin reference
                    resolved = p if not tree else os.path.join(tree, os.path.relpath(p, root))
                    if from_shell_error:
                        # The shell already said it could not open this one.
                        exists, miss = False, True
                    elif name == "Bash" and os.path.isdir(resolved):
                        continue  # a directory named in a shell command is not a file open
                    else:
                        exists = os.path.isfile(resolved)
                        # A Bash call reports one exit status for the whole command, and a
                        # non-zero exit is usually the script's own verdict, not a path that did
                        # not resolve — so for Bash, existence decides. A Read's error is
                        # evidence about the path itself, including a Read aimed at a directory,
                        # which is a real failed open and is why the directory skip above is
                        # scoped to Bash.
                        miss = (not exists) if name == "Bash" else ((not exists) or err)
                    opens.append({"t": t0, "tool": name, "path": p, "exists": exists,
                                  "is_error": err, "miss": miss,
                                  "seen_in": "shell error" if from_shell_error else "command"})

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
