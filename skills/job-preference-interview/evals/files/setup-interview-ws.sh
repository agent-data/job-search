#!/usr/bin/env bash
# Usage: setup-interview-ws.sh <tmp>. Isolated, no real data touched: the eval exports
# JOBSEARCH_OS_REGISTRY=<tmp>/registry.json and JOBSEARCH_OS_HOME=<tmp> (so the brief is written under
# <tmp>/.job-search, never real data). Prints <tmp>.
set -euo pipefail
DEST="$1"; mkdir -p "$DEST"; echo "$DEST"
