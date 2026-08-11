#!/bin/sh
# posting-counts.sh — print what the filtering found, for the home view.
#
# Usage: posting-counts.sh <jobs.jsonl>
#
# Prints one key=value per line: relevant, to_confirm, filtered.
#
# A posting's current state is its last `evaluated` line — the judgment the run that found it wrote.
# A posting the run judged relevant counts under `relevant` and one it judged not relevant counts
# under `filtered`. A posting whose judgment names another in same_role_as counts under NEITHER: it
# is the same opening seen twice, and the row it names was read and is counted on its own line. So
# `relevant` plus `filtered` is the number of openings judged, not the number of postings judged —
# measured on 2026-08-07, two judgments where the second names the first give relevant=1 filtered=0.
#
# to_confirm counts over the relevant postings only. A filtered posting whose judgment set
# needs_human_check is counted under `filtered`, and its open question is in no number here.
#
# The event log grows past what a context window holds, which is why the home view runs this script
# rather than reading the file itself. A run appends one `surfaced` line per NEW row a search
# returns (record-api-response.sh:9) and one `evaluated` line per posting it judges, so a first run
# of three searches at limit 25 leaves 150 lines before any `call`, `queued` or `detail` line, and
# every later run adds to the same file. There is
# no live log in the repository to point at: `.gitignore` excludes `evals/results/`, so any figure
# taken from a run on one machine cannot be re-run on another.
#
# `../../job-search-run/scripts` is where event-field.awk lives, and the walk out of this skill and
# into the next one holds because `skills/` ships as one directory in every packaging in this repo:
# `.codex-plugin`, `.cursor-plugin` and `.factory-plugin` each name `"skills": "./skills/"`,
# `.claude-plugin/plugin.json` names no path at all, and INSTALL_FOR_HERMES.md:206 checks
# `skills/job-search-runbook/scripts/workspace-discovery.sh` under the installed plugin.
# close-run.sh carries the same paragraph about its own walk to run-counts.sh — `grep -n 'ships as
# one directory' skills/job-search-runbook/scripts/close-run.sh`; change the two together.
#
# It also writes one line to stderr: how many lines it read, how many postings carry a judgment, and
# how many of those are the same opening as another posting. `relevant` plus `filtered` plus that
# third count equals the second, so the line accounts for the postings the three keys leave out. All
# three keys print as 0 for a log holding no judgment, for an empty log and for a file of lines that
# are not JSON at all, and the line is what tells those apart.
#
# Exit 0: the three counts printed. Exit 2: no counts printed — no log at that path, named on
# stderr. Any other status is awk failing partway, which leaves part of the key set on stdout: read
# these counts after checking the status, never because stdout has lines in it.
#
# A missing operand is the exception the caller sees a shell-picked code for, the way
# run-counts.sh's own header records — `grep -n 'missing operand'
# skills/job-search-run/scripts/run-counts.sh`: measured on 2026-08-07 at 1 under sh and bash and
# 2 under dash.
set -u

here=$(dirname "$0")
lib=$here/../../job-search-run/scripts/event-field.awk

jobs=${1:?usage: posting-counts.sh <jobs.jsonl>}
[ -f "$jobs" ] || { printf 'posting-counts.sh: no such file: %s\n' "$jobs" >&2; exit 2; }

# exec, so the status the caller sees is awk's own. Nothing is post-processed here, and a pipeline
# would report the last stage rather than awk.
exec awk -f "$lib" -f "$here/posting-counts.awk" "$jobs"
