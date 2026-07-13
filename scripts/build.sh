#!/usr/bin/env bash
# build.sh — regenerate the deterministic content-hash build stamp in its single home.
#
# The reference fan-out was removed (belief 5): every fact is single-homed in shared/references/ and
# each skill references it IN PLACE under the guaranteed bundle install (e.g. a SKILL.md points at
# ../../shared/references/<file>.md). Every supported host installs the whole pack tree — there is no
# loose single-skill install — so shared/ resolves from each skill; per-host reference resolution is
# proven by tests/test_reference_resolution.py. No per-host assembly is needed today, so this build is
# stamp-only. Idempotent; resolves the repo root from this script's own location (cwd-independent).
#
# If a future host genuinely cannot resolve a path outside a skill's own directory (a hard sandbox),
# THAT is the sole case for assembly: add a deterministic step here that writes that host's
# self-contained copies from the single source into a build-output dir (never re-tracked in skills/).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

python3 scripts/build_stamp.py --root "$REPO" --write shared/references/build-stamp.md >/dev/null

echo "build: regenerated shared/references/build-stamp.md (references are single-homed; no fan-out)"
