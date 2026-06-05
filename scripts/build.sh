#!/usr/bin/env bash
# build.sh — make each skill self-contained for the loose-skills install mode.
# Syncs the single-source-of-truth shared/references/*.md into every skill's references/,
# and bundles scripts/state.py into the skills that use it. Run after editing shared/ or scripts/.
# Idempotent; resolves the repo root from this script's own location (cwd-independent).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# 1) Sync shared references AND bundle the helper scripts into every skill (self-contained loose mode).
for skill in skills/*/; do
  mkdir -p "${skill}references" "${skill}scripts"
  cp shared/references/*.md "${skill}references/"
  cp scripts/state.py scripts/osctl.py "${skill}scripts/"
done

echo "build: synced references + bundled state.py/osctl.py into $(ls -d skills/*/ | wc -l | tr -d ' ') skill(s)"
