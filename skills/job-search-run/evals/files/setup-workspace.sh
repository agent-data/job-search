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
cp "$REPO/templates/preferences.example.md" "$DEST/preferences.md"
: > "$DEST/jobs.jsonl"
ln -sf "$REPO/tests/fake-agent-data" "$DEST/_bin/agent-data"
echo "$DEST"
