#!/usr/bin/env bash
# build.sh — make each skill self-contained for the loose-skills install mode.
# Syncs the single-source-of-truth shared/references/*.md into every skill's references/, and the
# optional stdlib-Python state-ops runtime (runtime/hermes_job_search/) into the consuming skills'
# scripts/. Only the Hermes adapter invokes that runtime; every other harness ships markdown only
# and never runs it. Run after editing shared/ or runtime/. Idempotent; resolves the repo root from
# this script's own location (cwd-independent).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

for skill in skills/*/; do
  mkdir -p "${skill}references"
  cp shared/references/*.md "${skill}references/"
  # Per-platform adapters live one level down in shared/references/platform/; copy them too so a
  # loose-skill install carries every harness adapter and the agent self-selects its own at runtime.
  if compgen -G "shared/references/platform/*.md" > /dev/null; then
    mkdir -p "${skill}references/platform"
    cp shared/references/platform/*.md "${skill}references/platform/"
  fi
done

# Bundle the stdlib-Python state-ops runtime into the skills whose Hermes path invokes it (the front
# door, the headless run, and the operator manual). rm -rf first so a deleted source file cannot
# linger in a bundle. The byte-for-byte match is enforced by validate_platforms.py (runtime-bundle).
RUNTIME_SKILLS=(job-search job-search-run job-search-agent)
if compgen -G "runtime/hermes_job_search/*.py" > /dev/null; then
  for skill in "${RUNTIME_SKILLS[@]}"; do
    dest="skills/${skill}/scripts/hermes_job_search"
    rm -rf "$dest"
    mkdir -p "$dest"
    cp runtime/hermes_job_search/*.py "$dest/"
  done
  echo "build: synced runtime into ${#RUNTIME_SKILLS[@]} consuming skill(s)"
fi

echo "build: synced references into $(ls -d skills/*/ | wc -l | tr -d ' ') skill(s)"
