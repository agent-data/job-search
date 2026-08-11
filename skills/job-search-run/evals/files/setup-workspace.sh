#!/usr/bin/env bash
# Usage: setup-workspace.sh <dest_dir>
# Builds a private test workspace at <dest_dir> from the skills' templates, a registry that points
# discovery at it, and a _bin/ holding an `agent-data` symlink to the fake shim. Run job-search-run
# with <dest_dir>/_bin FIRST on PATH and JOBSEARCH_OS_REGISTRY=<dest_dir>/_bin/registry.json (plus
# JOBSEARCH_FIXTURES and JOBSEARCH_TEST_SCENARIO) so the skill's discovery lands on this workspace
# and its `agent-data` calls hit the shim — no network, no real credits. Prints the exports to use.
set -euo pipefail
DEST="$1"
# this script lives at skills/job-search-run/evals/files/ — repo root is four levels up
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
mkdir -p "$DEST/runs" "$DEST/reports" "$DEST/_bin"
cp "$REPO/skills/job-search/templates/config.example.yaml" "$DEST/config.yaml"
# Pin freshness so dated shim fixtures do not rot with the calendar. Pin two sources as well: the
# template ships one source, and the cases below need a second one to have anything to fan out to,
# lose partway, or file under the wrong name — so this harness sets what it tests instead of
# inheriting whatever the product default happens to be.
sed -i.bak -e 's/freshness: "past-2-weeks"/freshness: "any"/' \
           -e 's|^  sources: \["linkedin"\].*|  sources: ["linkedin", "ashby"]   # pinned here, not inherited: these cases need a second source|' \
           "$DEST/config.yaml"
rm -f "$DEST/config.yaml.bak"
cp "$REPO/skills/job-preference-interview/templates/preferences.example.md" "$DEST/preferences.md"
: > "$DEST/jobs.jsonl"
ln -sf "$REPO/tests/fake-agent-data" "$DEST/_bin/agent-data"
printf '{ "version": 1, "active_workspace": "%s" }\n' "$DEST" > "$DEST/_bin/registry.json"
cat <<EOF
export PATH="$DEST/_bin:\$PATH"
export JOBSEARCH_OS_REGISTRY="$DEST/_bin/registry.json"
export JOBSEARCH_FIXTURES="$REPO/tests/fixtures"
workspace=$DEST
EOF
