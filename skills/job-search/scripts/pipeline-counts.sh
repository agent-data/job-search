#!/bin/sh
# pipeline-counts.sh — print how many postings sit in each state, for the home view.
#
# Usage: pipeline-counts.sh <jobs.jsonl>
#
# Prints one key=value per line: new, interested, applied, rejected, archived, to_confirm.
#
# A posting can have several lines — the judgment the run that found it wrote, then a
# status_changed line when the user says they applied somewhere. Its current state is the last line
# sharing its source and source_id. A posting that names another in same_role_as is the same
# opening seen twice and counts once, under the one that was read.
#
# A posting the run judged not relevant is not in the pipeline. Its judgment still carries
# status new — that is the funnel's starting state, not a claim about relevance — and a run now
# writes a line for every posting it surfaced, so counting by status alone would fill `new` with
# postings the run threw out. A posting the user has reacted to is in the pipeline whatever the
# run decided, because the reaction is the more recent and better-informed answer.
#
# to_confirm counts over the same postings the other five keys count. A rejected posting whose
# judgment set needs_human_check is in none of them, so its open question is in no number here
# either; the home card puts `(<k> to confirm)` on the Pipeline line, beside the five.
#
# The event log grows past what a context window holds. Measured on 2026-08-07: three live searches
# at limit 25, one detail read and a judgment on each of the 75 postings gave a jobs.jsonl of 159
# lines and 106,263 bytes, and that is one run. The home view runs this script rather than reading
# the file itself for that reason.
#
# `../../job-search-run/scripts` is where event-field.awk lives, and the walk out of this skill and
# into the next one holds because `skills/` ships as one directory in every packaging in this repo:
# `.codex-plugin`, `.cursor-plugin` and `.factory-plugin` each name `"skills": "./skills/"`,
# `.claude-plugin/plugin.json` names no path at all, and INSTALL_FOR_HERMES.md:206 checks
# `skills/job-search-runbook/scripts/workspace-discovery.sh` under the installed plugin.
# close-run.sh:53-57 is the same paragraph about its own walk to run-counts.sh; change the two
# together.
#
# Exit 0: the counts printed. Exit 2: nothing printed — no log at that path. Any other status is
# awk failing partway, which leaves part of the key set on stdout: read these counts after checking
# the status, never because stdout has lines in it.
#
# A missing operand is the exception the caller sees a shell-picked code for, the way
# run-counts.sh:28-29 records: measured on 2026-08-07 at 1 under sh and bash and 2 under dash.
set -u

here=$(dirname "$0")
lib=$here/../../job-search-run/scripts/event-field.awk

jobs=${1:?usage: pipeline-counts.sh <jobs.jsonl>}
[ -f "$jobs" ] || { printf 'pipeline-counts.sh: no such file: %s\n' "$jobs" >&2; exit 2; }

# exec, so the status the caller sees is awk's own. Nothing is post-processed here, and a pipeline
# would report the last stage rather than awk.
exec awk -f "$lib" -f "$here/pipeline-counts.awk" "$jobs"
