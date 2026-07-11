#!/bin/sh
# schedule-line.sh — compose the five-field cron schedule expression for a cadence.
#
# The scheduling contract in shared/references/internals.md §Scheduling pins the cadence enum
# (schedule.frequency) and schedule.time (HH:MM, honored for daily/weekly) and defers the composed
# line to the host. This is the deterministic, host-neutral core of that composition: the cron
# time expression (minute hour day-of-month month day-of-week) for a cadence —
#   hourly         -> 0 * * * *
#   every-2-hours  -> 0 */2 * * *
#   every-6-hours  -> 0 */6 * * *
#   daily  HH:MM   -> <m> <h> * * *      (default time 08:00)
#   weekly HH:MM   -> <m> <h> * * 1      (default time 08:00; Monday)
# matching the repo's established schedule-line cron mapping. A host wraps this expression with its
# own command/launchd translation. This is the scripted form of a model-run prose contract; that
# prose remains the no-runtime fallback.
#
# NOTE (flagged for the D10 fallback prose): the weekly day-of-week (Monday = 1) and the daily/weekly
# default time (08:00, the config default) are inherited from the repo's prior schedule-line contract;
# they are not otherwise pinned in shared/references/. Adjust here and in the fallback together.
#
# Usage: schedule-line.sh <frequency> [HH:MM]
set -u
freq=${1:?usage: schedule-line.sh <frequency> [HH:MM]}
time=${2:-08:00}

case $freq in
  hourly)        printf '%s\n' '0 * * * *'   ; exit 0 ;;
  every-2-hours) printf '%s\n' '0 */2 * * *' ; exit 0 ;;
  every-6-hours) printf '%s\n' '0 */6 * * *' ; exit 0 ;;
  daily|weekly)  : ;;   # need the time — handled below
  *) echo "schedule-line: unknown frequency '$freq' (want hourly|every-2-hours|every-6-hours|daily|weekly)" >&2
     exit 1 ;;
esac

# Parse HH:MM for daily/weekly; strip a single leading zero so cron gets 8 not 08, 5 not 05.
case $time in
  [0-9]*:[0-9]*) : ;;
  *) echo "schedule-line: bad time '$time' (want HH:MM)" >&2; exit 1 ;;
esac
hh=${time%%:*}
mm=${time##*:}
hh=${hh#0}; [ -n "$hh" ] || hh=0
mm=${mm#0}; [ -n "$mm" ] || mm=0

if [ "$freq" = daily ]; then
  printf '%s %s * * *\n' "$mm" "$hh"
else
  printf '%s %s * * 1\n' "$mm" "$hh"   # weekly: Monday (1)
fi
