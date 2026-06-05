#!/usr/bin/env bash
# Usage: setup-onboarding.sh <tmp>. Builds a FIRST-RUN sandbox: only a _bin/agent-data shim symlink.
# The eval RUNNER exports JOBSEARCH_OS_REGISTRY=<tmp>/registry.json and JOBSEARCH_OS_HOME=<tmp> (so the
# registry + default/legacy workspaces live under <tmp> — real ~/.config, ~/.job-search, ~/job-search are
# never touched), plus PATH=<tmp>/_bin:$PATH + JOBSEARCH_FIXTURES + JOBSEARCH_TEST_SCENARIO for the shim.
# Scheduling installs are STUBBED in evals (no crontab/launchctl). Prints <tmp>.
set -euo pipefail
DEST="$1"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
mkdir -p "$DEST/_bin"
ln -sf "$REPO/tests/fake-agent-data" "$DEST/_bin/agent-data"
echo "$DEST"
