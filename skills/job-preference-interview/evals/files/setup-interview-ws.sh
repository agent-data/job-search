#!/usr/bin/env bash
# Usage: setup-interview-ws.sh <tmp>. Creates an isolated temp dir and prints it. The eval RUNNER then
# exports JOBSEARCH_OS_REGISTRY=<tmp>/registry.json and JOBSEARCH_OS_HOME=<tmp> (so the brief is written
# under <tmp>/.job-search, never real data). This script itself only makes the dir.
set -euo pipefail
DEST="$1"; mkdir -p "$DEST"; echo "$DEST"
