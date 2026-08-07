#!/bin/sh
# posting-counts.sh — print what the filtering found, for the home view.
#
# Usage: posting-counts.sh <jobs.jsonl>
#
# Prints one key=value per line: relevant, to_confirm, filtered.
#
# A posting's current state is its last `evaluated` line — the judgment the run that found it wrote.
# A posting the run judged relevant counts under `relevant`, one it judged not relevant counts under
# `filtered`, and every judged posting is in exactly one of the two. A posting that names another in
# same_role_as is the same opening seen twice and counts once, under the one that was read.
#
# to_confirm counts over the relevant postings only. A filtered posting whose judgment set
# needs_human_check is counted under `filtered`, and its open question is in no number here.
#
# The event log grows past what a context window holds, which is why the home view runs this script
# rather than reading the file itself. One live run's log is in the repository:
# `wc -lc evals/results/2026-07-31T10-53-54Z-headless-run-sonnet/workspace/jobs.jsonl` gives 317
# lines and 274,335 bytes.
#
# `../../job-search-run/scripts` is where event-field.awk lives, and the walk out of this skill and
# into the next one holds because `skills/` ships as one directory in every packaging in this repo:
# `.codex-plugin`, `.cursor-plugin` and `.factory-plugin` each name `"skills": "./skills/"`,
# `.claude-plugin/plugin.json` names no path at all, and INSTALL_FOR_HERMES.md:206 checks
# `skills/job-search-runbook/scripts/workspace-discovery.sh` under the installed plugin.
# close-run.sh:53-57 is the same paragraph about its own walk to run-counts.sh; change the two
# together.
#
# Exit 0: the three counts printed. Exit 2: nothing printed — no log at that path. Any other status
# is awk failing partway, which leaves part of the key set on stdout: read these counts after
# checking the status, never because stdout has lines in it.
#
# A missing operand is the exception the caller sees a shell-picked code for, the way
# run-counts.sh:28-29 records: measured on 2026-08-07 at 1 under sh and bash and 2 under dash.
set -u

here=$(dirname "$0")
lib=$here/../../job-search-run/scripts/event-field.awk

jobs=${1:?usage: posting-counts.sh <jobs.jsonl>}
[ -f "$jobs" ] || { printf 'posting-counts.sh: no such file: %s\n' "$jobs" >&2; exit 2; }

# exec, so the status the caller sees is awk's own. Nothing is post-processed here, and a pipeline
# would report the last stage rather than awk.
exec awk -f "$lib" -f "$here/posting-counts.awk" "$jobs"
