#!/bin/sh
# support-summary.sh — emit a WHITELIST-ONLY local support diagnostic on STDOUT.
#
# On the user's explicit request only. The caller (documented in shared/references/internals.md
# §"Local support summary") atomically writes this STDOUT to {workspace}/support-summary.txt, displays
# the WHOLE file to the user, and asks nothing further unless the user explicitly wants help attaching
# it to a GitHub issue. This mechanic makes NO network/upload/browser call — it reads local files only.
#
# It is a WHITELIST, built by EXTRACTING ONLY the allowed nonsecret fields — never by dumping and
# filtering. Even if the workspace or registry contain API keys, auth headers, pagination cursors,
# opaque continuation tokens, preferences, job descriptions, or match prose, this summary contains NONE
# of them. The whitelist is EXACTLY: build stamp; host-reported harness/version; OS/architecture;
# schedule state; latest run health; internal error code; aggregate agent-data calls; nonsecret request
# IDs. Every field is pulled by exact key, scoped to its object — nothing else is read out.
#
# The internal error code (the operator `E-*` code, or a bounded internal class) IS whitelisted here:
# this is an operator/support diagnostic like runs/<id>.json, reviewed in full by the user before they
# choose to attach it — not a normal chat/digest/home/notification surface — so the "no raw E-* to the
# user" rule (errors.md) does not strip it. Bounded-secret and PII fields stay excluded.
#
# This is the scripted form of the model-run prose contract in internals.md; that prose remains the
# no-runtime fallback.
#
# Usage: support-summary.sh WORKSPACE REGISTRY HARNESS_NAME HARNESS_VERSION   # summary on STDOUT
set -u

[ "$#" -eq 4 ] || {
  echo 'usage: support-summary.sh WORKSPACE REGISTRY HARNESS_NAME HARNESS_VERSION' >&2
  exit 2
}
workspace=$1
registry=$2
harness_name=$3
harness_version=$4

ISSUES_URL='https://github.com/agent-data/job-search/issues'

# Collapse host-reported strings to a single printable line so a stray newline can never reshape the
# summary. (Values sourced from the workspace/registry come through the exact-key extractors below.)
oneline() { printf '%s' "$1" | tr -d '\n\r' | cut -c1-200; }

# Print the string value of "KEY":"VALUE" found in the text on $1 (empty if absent or a JSON null).
# The value is read only from that exact key; scope the text to one object before calling.
str_field() {
  _sf_text=$1
  _sf_key=$2
  printf '%s' "$_sf_text" \
    | grep -o "\"$_sf_key\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
    | head -1 \
    | sed "s/^\"$_sf_key\"[[:space:]]*:[[:space:]]*\"//; s/\"\$//"
}

# Print true|false for a boolean "KEY":true/false (empty if absent or non-boolean). Two fixed matches
# instead of a regex alternation, so this stays portable BRE (no `\|`).
bool_field() {
  _bf_text=$1
  _bf_key=$2
  if printf '%s' "$_bf_text" | grep -q "\"$_bf_key\"[[:space:]]*:[[:space:]]*true"; then
    printf 'true'
  elif printf '%s' "$_bf_text" | grep -q "\"$_bf_key\"[[:space:]]*:[[:space:]]*false"; then
    printf 'false'
  fi
}

# Print the integer value of "KEY": <digits> (empty if absent).
num_field() {
  _nf_text=$1
  _nf_key=$2
  printf '%s' "$_nf_text" \
    | grep -Eo "\"$_nf_key\"[[:space:]]*:[[:space:]]*[0-9]+" \
    | head -1 \
    | grep -Eo '[0-9]+$'
}

# ---- build stamp: the bundled plugin build, resolved from this script's own location ----------------
script_dir=$(CDPATH= cd -P "$(dirname "$0")" && pwd -P 2>/dev/null) || script_dir=
build_version=unknown
build_hash=unknown
if [ -n "${script_dir:-}" ] && [ -f "$script_dir/../../references/build-stamp.md" ]; then
  _stamp=$script_dir/../../references/build-stamp.md
  _v=$(grep '^version:' "$_stamp" 2>/dev/null | head -1 | sed 's/^version:[[:space:]]*//')
  _h=$(grep '^content_hash:' "$_stamp" 2>/dev/null | head -1 | sed 's/^content_hash:[[:space:]]*//')
  [ -n "${_v:-}" ] && build_version=$_v
  [ -n "${_h:-}" ] && build_hash=$_h
fi

# ---- OS / architecture ------------------------------------------------------------------------------
os_kernel=$(uname -s 2>/dev/null) || os_kernel=
os_arch=$(uname -m 2>/dev/null) || os_arch=
[ -n "${os_kernel:-}" ] || os_kernel=unknown
[ -n "${os_arch:-}" ] || os_arch=unknown

# ---- schedule state: ONLY installed/verified/mechanism/cadence, scoped to the flat scheduling object
schedule_configured=false
sched_installed=unknown
sched_verified=unknown
sched_mechanism=
sched_cadence=
if [ -f "$registry" ]; then
  reg_flat=$(tr '\n' ' ' < "$registry" 2>/dev/null)
  # The scheduling object is flat (no nested braces), so [^}]* stops at its own closing brace and
  # never reaches deeper_coverage_nudges or any other key. Bracket-expression literals keep it BRE.
  sched_obj=$(printf '%s' "$reg_flat" | grep -o '"scheduling"[[:space:]]*:[[:space:]]*[{][^}]*[}]')
  if [ -n "$sched_obj" ]; then
    schedule_configured=true
    _i=$(bool_field "$sched_obj" installed)
    _ver=$(bool_field "$sched_obj" verified)
    _mech=$(str_field "$sched_obj" mechanism)
    _cad=$(str_field "$sched_obj" cadence)
    [ -n "${_i:-}" ] && sched_installed=$_i
    [ -n "${_ver:-}" ] && sched_verified=$_ver
    sched_mechanism=${_mech:-}
    sched_cadence=${_cad:-}
  fi
fi

# ---- latest run record: newest run_id-shaped file only (never the binding sidecar or hidden files) --
record_name=
run_health=unknown
internal_code=none
metered_calls=unknown
request_ids=
if [ -d "$workspace/runs" ]; then
  record_name=$(ls -1 "$workspace/runs" 2>/dev/null \
    | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z\.json$' \
    | sort | tail -1)
fi
if [ -n "${record_name:-}" ] && [ -f "$workspace/runs/$record_name" ]; then
  rec_flat=$(tr '\n' ' ' < "$workspace/runs/$record_name" 2>/dev/null)
  _rh=$(str_field "$rec_flat" run_health)
  [ -n "${_rh:-}" ] && run_health=$_rh
  _mc=$(num_field "$rec_flat" metered_calls)
  [ -n "${_mc:-}" ] && metered_calls=$_mc
  # Internal code: scope to the SINGULAR flat `error` object, then read code/class, then VALIDATE
  # against the exact operator grammar / the closed class set — belt and suspenders over the scoping,
  # so no unexpected content in that object can be emitted verbatim.
  err_obj=$(printf '%s' "$rec_flat" | grep -o '"error"[[:space:]]*:[[:space:]]*[{][^}]*[}]')
  if [ -n "$err_obj" ]; then
    _code=$(str_field "$err_obj" code)
    _class=$(str_field "$err_obj" class)
    if printf '%s' "$_code" | grep -Eq '^E-[A-Z0-9]+(-[A-Z0-9]+)*$'; then
      internal_code=$_code
    elif [ "$_class" = detail_model_binding_unavailable ] || [ "$_class" = config_v1_migration_failed ]; then
      internal_code=$_class
    fi
  fi
  # Nonsecret request IDs: values under request_id / request_ids keys ONLY (a cursor never lives there,
  # and the run record persists no cursor at all). Flattened text handles pretty-printed arrays.
  request_ids=$(
    {
      printf '%s' "$rec_flat" \
        | grep -o '"request_id"[[:space:]]*:[[:space:]]*"[^"]*"' \
        | sed 's/^"request_id"[[:space:]]*:[[:space:]]*"//; s/"$//'
      printf '%s' "$rec_flat" \
        | grep -o '"request_ids"[[:space:]]*:[[:space:]]*[[][^]]*[]]' \
        | sed 's/^"request_ids"[[:space:]]*:[[:space:]]*[[]//; s/[]]$//' \
        | grep -o '"[^"]*"' \
        | sed 's/^"//; s/"$//'
    } 2>/dev/null | grep -v '^$' | sort -u
  )
fi

# ---- emit the whitelist-only summary ----------------------------------------------------------------
printf 'Job Search — local support summary\n'
printf 'Whitelist-only: nonsecret fields only. Nothing here is uploaded — review it, then attach it\n'
printf 'to a GitHub issue yourself if you choose to.\n'
printf '\n'
printf 'Build:             %s (%s)\n' "$build_version" "$build_hash"
printf 'Harness:           %s %s\n' "$(oneline "$harness_name")" "$(oneline "$harness_version")"
printf 'OS / arch:         %s %s\n' "$os_kernel" "$os_arch"
if [ "$schedule_configured" = true ]; then
  printf 'Schedule:          installed=%s verified=%s' "$sched_installed" "$sched_verified"
  [ -n "$sched_mechanism" ] && printf ' mechanism=%s' "$sched_mechanism"
  [ -n "$sched_cadence" ] && printf ' cadence=%s' "$sched_cadence"
  printf '\n'
else
  printf 'Schedule:          not configured\n'
fi
if [ -n "${record_name:-}" ]; then
  printf 'Latest run:        %s\n' "$record_name"
  printf 'Latest run health: %s\n' "$run_health"
  printf 'Internal code:     %s\n' "$internal_code"
  printf 'Agent-data calls:  %s metered this run\n' "$metered_calls"
  if [ -n "$request_ids" ]; then
    printf 'Request IDs:\n'
    printf '%s\n' "$request_ids" | sed 's/^/  - /'
  else
    printf 'Request IDs:       none recorded\n'
  fi
else
  printf 'Latest run:        none recorded\n'
fi
printf '\n'
printf 'Report an issue:   %s\n' "$ISSUES_URL"
