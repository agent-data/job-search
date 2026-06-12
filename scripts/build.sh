#!/usr/bin/env bash
# build.sh — make each skill self-contained for the loose-skills install mode.
# Syncs the single-source-of-truth shared/references/*.md into every skill's references/.
# Run after editing shared/. Idempotent; resolves the repo root from this script's own
# location (cwd-independent). Nothing executable is bundled — the skills ship markdown only.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

for skill in skills/*/; do
  mkdir -p "${skill}references"
  cp shared/references/*.md "${skill}references/"
done

echo "build: synced references into $(ls -d skills/*/ | wc -l | tr -d ' ') skill(s)"
