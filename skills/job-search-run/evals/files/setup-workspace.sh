#!/usr/bin/env bash
# Usage: setup-workspace.sh <dest_dir>
# Builds a minimal PRIVATE test workspace from the repo templates, plus a _bin/ containing an
# `agent-data` symlink to the fake-agent-data shim. Run job-search-run with <dest_dir>/_bin FIRST on
# PATH (and JOBSEARCH_FIXTURES + JOBSEARCH_TEST_SCENARIO set) so its `agent-data` calls hit the shim —
# no network, no real credits. Prints <dest_dir>.
set -euo pipefail
DEST="$1"
# this script lives at skills/job-search-run/evals/files/ — repo root is four levels up
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
mkdir -p "$DEST/runs" "$DEST/reports" "$DEST/_bin"
cp "$REPO/templates/config.example.yaml" "$DEST/config.yaml"
# Runner evals exercise the bounded legacy-v1 path unless a case explicitly builds v2. Turn the intentionally
# incomplete setup template into a valid v1 fixture with a saved selector, and pin freshness so dated fixtures
# do not rot with the calendar.
sed -i.bak \
  -e 's/^version: 2/version: 1/' \
  -e 's/freshness: "past-2-weeks"/freshness: "any"/' \
  -e 's/^  # Setup inserts the required exact search.detail_model before writing a valid new workspace\./  detail_model: "balanced"  # legacy v1 eval selector/' \
  "$DEST/config.yaml"
rm -f "$DEST/config.yaml.bak"
cp "$REPO/templates/preferences.example.md" "$DEST/preferences.md"
: > "$DEST/jobs.jsonl"
ln -sf "$REPO/tests/fake-agent-data" "$DEST/_bin/agent-data"
echo "$DEST"
