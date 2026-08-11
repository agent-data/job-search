#!/bin/sh
# workspace-discovery.sh — resolve the active workspace, its source, and whether this is a first run.
#
# Reproduces the workspace-discovery precedence in this skill's SKILL.md §"Find the
# workspace", honoring $JOBSEARCH_OS_REGISTRY, $XDG_CONFIG_HOME, $JOBSEARCH_OS_HOME, $HOME exactly as
# the pinned expressions do:
#   1. Registry parses with a non-empty active_workspace W  -> W, source=registry; first_run only if W
#      has no config.yaml. The registry wins UNCONDITIONALLY — never fall through, even when W lacks a
#      config.yaml (falling through could silently switch the user's workspace).
#   2. $H/.job-search/config.yaml exists  -> $H/.job-search, source=default, not a first run.
#   3. $H/job-search/config.yaml  exists  -> $H/job-search,  source=legacy,  not a first run.
#   4. otherwise first run: $H/.job-search (not yet created), source=none.
# This is the scripted form of the model-run prose contract; that prose remains the no-runtime fallback.
#
# Prints three key=value lines on stdout:  workspace=<abs path>
#                                          source=<registry|default|legacy|none>
#                                          first_run=<true|false>
#
# and one line on stderr saying what it found at the registry path. Four states fall past the
# registry step, and the three keys above say nothing about which one happened: a registry holding an
# empty active_workspace, one whose active_workspace is not a string at all, a registry that is not
# JSON at all, and no registry file. Measured 2026-08-11 on one HOME with the file rewritten between
# calls, all four printed the same three keys on stdout and exited 0, so the stderr line is the only
# part of the answer that separates them. This skill's SKILL.md §"Find the workspace" requires the
# caller to stop the run on the registry that is not JSON, and this script does not parse JSON: the
# `grep` below reads the first three the same way, so those three share one stderr line, which says
# what the grep did establish — that the file holds no non-empty active_workspace string. The state
# the line does separate out is no registry file at that path, where the caller has nothing to
# parse-check.
set -u

REG="${JOBSEARCH_OS_REGISTRY:-${XDG_CONFIG_HOME:-${JOBSEARCH_OS_HOME:-$HOME}/.config}/job-search/config.json}"
H="${JOBSEARCH_OS_HOME:-$HOME}"

emit() { printf 'workspace=%s\nsource=%s\nfirst_run=%s\n' "$1" "$2" "$3"; }

# 1) Registry wins unconditionally when it holds a non-empty active_workspace.
if [ -f "$REG" ]; then
  W=$(grep -o '"active_workspace"[[:space:]]*:[[:space:]]*"[^"]*"' "$REG" 2>/dev/null \
        | cut -d'"' -f4 | head -1)
  if [ -n "${W:-}" ]; then
    printf 'workspace-discovery.sh: registry %s names active_workspace %s — found by grep, which does not check that the file is JSON, so parse-check the file yourself\n' \
      "$REG" "$W" >&2
    if [ -f "$W/config.yaml" ]; then
      emit "$W" registry false
    else
      emit "$W" registry true
    fi
    exit 0
  else
    # One line for three states, because the grep above reads all three the same way: a registry
    # holding an empty active_workspace, one whose active_workspace is not a string — the grep
    # matches a quoted value, and `{"active_workspace": 42}` is valid JSON holding none — and a
    # registry that is not JSON at all. Naming one of the three would state something the grep never
    # established, so the line reports what it did establish: the file holds no non-empty
    # active_workspace string. Measured 2026-08-11 on a registry holding `{"active_workspace": 42}`,
    # the script wrote this line and exited 0.
    #
    # This path does not stop here — it falls through to the two config checks below and then
    # to the first-run line, so the workspace on stdout is not always source=none. Measured
    # 2026-08-11 with a registry that is not JSON and a config.yaml at $H/.job-search: source=default.
    printf 'workspace-discovery.sh: registry %s holds no non-empty "active_workspace" string — grep does not check that the file is JSON, so parse-check the file yourself\n' \
      "$REG" >&2
  fi
else
  printf 'workspace-discovery.sh: no registry file at %s — nothing to parse-check\n' "$REG" >&2
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
