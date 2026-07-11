#!/bin/sh
# workspace-discovery.sh — resolve the active workspace, its source, and whether this is a first run.
#
# Reproduces the pinned precedence in shared/references/internals.md §"Workspace discovery & first-run
# detection", honoring $JOBSEARCH_OS_REGISTRY, $XDG_CONFIG_HOME, $JOBSEARCH_OS_HOME, $HOME exactly as
# the pinned expressions do:
#   1. Registry parses with a non-empty active_workspace W  -> W, source=registry; first_run only if W
#      has no config.yaml. The registry wins UNCONDITIONALLY — never fall through, even when W lacks a
#      config.yaml (falling through could silently switch the user's workspace).
#   2. $H/.job-search/config.yaml exists  -> $H/.job-search, source=default, not a first run.
#   3. $H/job-search/config.yaml  exists  -> $H/job-search,  source=legacy,  not a first run.
#   4. otherwise first run: $H/.job-search (not yet created), source=none.
# This is the scripted form of the model-run prose contract; that prose remains the no-runtime fallback.
#
# Prints three key=value lines:  workspace=<abs path>  source=<registry|default|legacy|none>
#                                first_run=<true|false>
set -u

REG="${JOBSEARCH_OS_REGISTRY:-${XDG_CONFIG_HOME:-${JOBSEARCH_OS_HOME:-$HOME}/.config}/job-search/config.json}"
H="${JOBSEARCH_OS_HOME:-$HOME}"

emit() { printf 'workspace=%s\nsource=%s\nfirst_run=%s\n' "$1" "$2" "$3"; }

# 1) Registry wins unconditionally when it holds a non-empty active_workspace.
if [ -f "$REG" ]; then
  W=$(grep -o '"active_workspace"[[:space:]]*:[[:space:]]*"[^"]*"' "$REG" 2>/dev/null \
        | cut -d'"' -f4 | head -1)
  if [ -n "${W:-}" ]; then
    if [ -f "$W/config.yaml" ]; then
      emit "$W" registry false
    else
      emit "$W" registry true
    fi
    exit 0
  fi
fi

# 2) Default hidden workspace has a config.
if [ -f "$H/.job-search/config.yaml" ]; then
  emit "$H/.job-search" default false
  exit 0
fi

# 3) Legacy visible workspace has a config.
if [ -f "$H/job-search/config.yaml" ]; then
  emit "$H/job-search" legacy false
  exit 0
fi

# 4) First run: the default workspace path, not yet created.
emit "$H/.job-search" none true
