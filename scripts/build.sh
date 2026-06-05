#!/usr/bin/env bash
# build.sh — make each skill self-contained for the loose-skills install mode.
# Syncs the single-source-of-truth shared/references/*.md into every skill's references/,
# and bundles scripts/state.py into the skills that use it. Run after editing shared/ or scripts/.
# Idempotent; resolves the repo root from this script's own location (cwd-independent).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# 1) Sync shared references into each skill that has a references/ dir (or should).
for skill in skills/*/; do
  mkdir -p "${skill}references"
  cp shared/references/*.md "${skill}references/"
done

# 2) Bundle state.py into the skills that invoke it (currently: job-search-run).
mkdir -p skills/job-search-run/scripts
cp scripts/state.py skills/job-search-run/scripts/state.py

echo "build: synced references into $(ls -d skills/*/ | wc -l | tr -d ' ') skill(s); bundled state.py into job-search-run"
