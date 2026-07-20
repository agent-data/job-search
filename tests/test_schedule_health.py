"""Deterministic, fixed-clock pressure for T7.1: derive ongoing schedule health from local evidence.

The single-source contract lives in shared/references/internals.md (§ Schedule health) with the run-record
reader selection in shared/references/conventions.md and the doctrine one hop away in
skills/job-search/references/home.md and skills/job-search-agent/references/scheduling-and-consent.md. The
behavioural evals live in the two skills' evals.json (coverage_kind executable_fixture).

This module does two jobs, mirroring tests/test_scheduling_eligibility.py:

  (1) it PINS the precedence + liveness contract text structurally (the RED->GREEN driver for T7.1), and
  (2) it is the EXECUTABLE REFERENCE for the deterministic precedence + 30-minute grace + one-vs-two
      missed-fire thresholds + the DST-aware next/previous-fire math, computed against a FAKE fixed clock
      (never wall-clock), so the capability is real, not merely asserted — the eval_harness.aggregate_reps
      precedent.

No live effects, no real scheduler, no network, no model, no agent-data account, and NOTHING metered: the
health check is a local, unmetered read over the registry marker, the scheduler's own registration, and the
latest scheduled-attributable run record, evaluated at a supplied fixed `now`. Timezone math uses the stdlib
`zoneinfo`; the DST-boundary case is the load-bearing proof that a daily fire across a fall-back/spring-forward
transition is not spuriously counted as missed.
"""
import pathlib
import re
from datetime import datetime, timedelta, timezone

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTERNALS = ROOT / "shared" / "references" / "internals.md"
CONVENTIONS = ROOT / "shared" / "references" / "conventions.md"
HOME = ROOT / "skills" / "job-search" / "references" / "home.md"
SCHEDULING = ROOT / "skills" / "job-search-agent" / "references" / "scheduling-and-consent.md"

# The canonical 8-state precedence, highest priority first. The reference implementation below emits
# exactly these tokens; the contract table in internals.md must enumerate the same tokens in this order.
PRECEDENCE = (
    "registration_drift",
    "latest_run_blocked",
    "needs_attention",
    "not_recently_observed",
    "verified_running",
    "unverified",
    "session_only",
    "absent",
)

GRACE = timedelta(minutes=30)  # documented post-fire grace period
INTERVAL_HOURS = {"hourly": 1, "every-2-hours": 2, "every-6-hours": 6}

try:  # zoneinfo ships in the stdlib (3.9+); a host may still lack the IANA tz database.
    from zoneinfo import ZoneInfo

    ZoneInfo("America/New_York")
    ZoneInfo("America/Los_Angeles")
    _TZ_DB = True
except Exception:  # pragma: no cover - only when the tz database is unavailable
    _TZ_DB = False

_needs_tz = pytest.mark.skipif(not _TZ_DB, reason="IANA tz database unavailable (zoneinfo)")


# ---------------------------------------------------------------------------
# Executable reference: the deterministic liveness math (fixed clock, DST-aware)
# ---------------------------------------------------------------------------
def expected_fires(baseline, now, cadence, hhmm, tz):
    """Every scheduled fire instant f (aware UTC) with baseline < f <= now, computed in the CONFIGURED
    timezone so a daily fire keeps its local wall-clock time across a DST transition (its UTC offset
    shifts by an hour, its local HH:MM does not)."""
    assert baseline <= now
    h, m = hhmm
    start = baseline.astimezone(tz).date()
    end = now.astimezone(tz).date()
    day, one = start, timedelta(days=1)
    fires = []
    while day <= end:
        if cadence == "daily":
            hours = [h]
        elif cadence == "weekly":
            hours = [h] if day.weekday() == 0 else []  # Monday
        else:
            hours = range(0, 24, INTERVAL_HOURS[cadence])
        for hour in hours:
            minute = m if cadence in ("daily", "weekly") else 0
            f = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz).astimezone(timezone.utc)
            if baseline < f <= now:
                fires.append(f)
        day += one
    return sorted(fires)


def missed_fires(now, baseline, cadence, hhmm, tz, grace=GRACE):
    """Count expected fires whose post-fire grace has fully elapsed with no observed run since `baseline`.
    A fire still inside its grace window (now < f + grace) is imminent, not missed."""
    return sum(1 for f in expected_fires(baseline, now, cadence, hhmm, tz) if f + grace <= now)


def derive_schedule_health(*, now, marker, registration_matches, latest_scheduled_run,
                           cadence, hhmm, tz, grace=GRACE):
    """Render exactly one state token from PRECEDENCE.

    `marker` is the registry scheduling object (installed/verified/mechanism/verified_at/...).
    `registration_matches` is the three-source comparison result: True when the scheduler's own local
    registration still equals what the registry recorded, False on drift.
    `latest_scheduled_run` is the newest scheduled-attributable run record (trigger=scheduled, the canary
    EXCLUDED via canary_run_id) or None; each carries started_at (aware UTC) and run_health.
    The anomaly states (ranks 1-4) apply only to an installed+verified unattended schedule; a non-verified
    marker reads unverified, a loop reads session-only, an uninstalled marker reads absent."""
    if not marker.get("installed"):
        return "absent"
    if marker.get("mechanism") == "loop":
        return "session_only"
    if not marker.get("verified"):
        return "unverified"
    if not registration_matches:
        return "registration_drift"
    if latest_scheduled_run and latest_scheduled_run.get("run_health") == "blocked":
        return "latest_run_blocked"
    baseline = latest_scheduled_run["started_at"] if latest_scheduled_run else marker["verified_at"]
    missed = missed_fires(now, baseline, cadence, hhmm, tz, grace)
    if missed >= 2:
        return "needs_attention"
    if missed == 1:
        return "not_recently_observed"
    return "verified_running"


# ---------------------------------------------------------------------------
# Fixture builders (fixed clocks only — no wall-clock, nothing metered)
# ---------------------------------------------------------------------------
def _verified_marker(**over):
    m = {
        "installed": True,
        "verified": True,
        "mechanism": "launchd",
        "scheduler_id": "job-fixture-1",
        "cadence": "daily",
        "verified_at": None,
        "canary_run_id": "2026-07-10T08-00-00Z",
    }
    m.update(over)
    return m


def _run(started_local, tz, run_health="healthy"):
    return {"started_at": started_local.replace(tzinfo=tz).astimezone(timezone.utc),
            "run_health": run_health}


def _at(y, mo, d, h, mi, tz):
    return datetime(y, mo, d, h, mi, tzinfo=tz).astimezone(timezone.utc)


# ===========================================================================
# (1) The reference math + precedence — the deterministic fixed-clock proof
# ===========================================================================
@_needs_tz
def test_grace_boundary_just_before_and_after():
    tz = ZoneInfo("America/Los_Angeles")
    hhmm, cadence = (8, 0), "daily"
    marker = _verified_marker()
    yesterday = _run(datetime(2026, 6, 9, 8, 2), tz)  # fired ~on time yesterday
    # 08:29 local — 1 minute BEFORE today's 08:00 fire clears its 30-minute grace -> not missed -> running
    before = derive_schedule_health(now=_at(2026, 6, 10, 8, 29, tz), marker=marker,
                                    registration_matches=True, latest_scheduled_run=yesterday,
                                    cadence=cadence, hhmm=hhmm, tz=tz)
    assert before == "verified_running"
    # 08:31 local — grace has elapsed on exactly one expected fire -> not recently observed
    after = derive_schedule_health(now=_at(2026, 6, 10, 8, 31, tz), marker=marker,
                                   registration_matches=True, latest_scheduled_run=yesterday,
                                   cadence=cadence, hhmm=hhmm, tz=tz)
    assert after == "not_recently_observed"


@_needs_tz
def test_one_missed_fire_is_not_recently_observed():
    tz = ZoneInfo("America/Los_Angeles")
    marker = _verified_marker()
    last = _run(datetime(2026, 6, 9, 8, 2), tz)               # yesterday
    now = _at(2026, 6, 10, 9, 0, tz)                          # one daily fire (today 08:00) overdue
    assert missed_fires(now, last["started_at"], "daily", (8, 0), tz) == 1
    assert derive_schedule_health(now=now, marker=marker, registration_matches=True,
                                  latest_scheduled_run=last, cadence="daily", hhmm=(8, 0),
                                  tz=tz) == "not_recently_observed"


@_needs_tz
def test_two_missed_fires_is_needs_attention():
    tz = ZoneInfo("America/Los_Angeles")
    marker = _verified_marker()
    last = _run(datetime(2026, 6, 8, 8, 2), tz)               # two days ago
    now = _at(2026, 6, 10, 9, 0, tz)                          # 06-09 08:00 and 06-10 08:00 both overdue
    assert missed_fires(now, last["started_at"], "daily", (8, 0), tz) == 2
    assert derive_schedule_health(now=now, marker=marker, registration_matches=True,
                                  latest_scheduled_run=last, cadence="daily", hhmm=(8, 0),
                                  tz=tz) == "needs_attention"


@_needs_tz
def test_manual_run_after_a_missed_schedule_does_not_mask_the_gap():
    # A manual run 1h ago is NOT scheduled-attributable: the latest SCHEDULED fire is still yesterday's,
    # so the missed schedule still surfaces. (The caller passes only the scheduled run here.)
    tz = ZoneInfo("America/Los_Angeles")
    marker = _verified_marker()
    last_scheduled = _run(datetime(2026, 6, 9, 8, 2), tz)     # yesterday's scheduled fire
    now = _at(2026, 6, 10, 9, 0, tz)                          # a manual run at ~08:00 today is ignored
    assert derive_schedule_health(now=now, marker=marker, registration_matches=True,
                                  latest_scheduled_run=last_scheduled, cadence="daily", hhmm=(8, 0),
                                  tz=tz) == "not_recently_observed"


@_needs_tz
def test_canary_only_history_reads_running_not_missed():
    # The only scheduled-path run is the canary (canary_run_id), which is NOT an ordinary scheduled fire,
    # so latest_scheduled_run is None and the baseline is verified_at. No ordinary fire is yet overdue.
    tz = ZoneInfo("America/Los_Angeles")
    marker = _verified_marker(verified_at=_at(2026, 6, 10, 8, 1, tz))  # canary fired today 08:01
    now = _at(2026, 6, 10, 12, 0, tz)                         # before tomorrow's 08:00 fire
    assert derive_schedule_health(now=now, marker=marker, registration_matches=True,
                                  latest_scheduled_run=None, cadence="daily", hhmm=(8, 0),
                                  tz=tz) == "verified_running"


@_needs_tz
def test_registration_drift_wins_over_everything():
    tz = ZoneInfo("America/Los_Angeles")
    marker = _verified_marker()
    overdue = _run(datetime(2026, 6, 1, 8, 2), tz)           # very overdue AND blocked would also apply
    assert derive_schedule_health(now=_at(2026, 6, 10, 9, 0, tz), marker=marker,
                                  registration_matches=False, latest_scheduled_run=overdue,
                                  cadence="daily", hhmm=(8, 0), tz=tz) == "registration_drift"


@_needs_tz
def test_blocked_scheduled_run_wins_over_liveness():
    tz = ZoneInfo("America/Los_Angeles")
    marker = _verified_marker()
    blocked = _run(datetime(2026, 6, 10, 8, 3), tz, run_health="blocked")  # on-time but blocked
    assert derive_schedule_health(now=_at(2026, 6, 10, 8, 40, tz), marker=marker,
                                  registration_matches=True, latest_scheduled_run=blocked,
                                  cadence="daily", hhmm=(8, 0), tz=tz) == "latest_run_blocked"


@_needs_tz
def test_recovered_run_reads_running_again():
    # After a gap, a fresh healthy on-time scheduled fire resets the baseline -> back to running.
    tz = ZoneInfo("America/Los_Angeles")
    marker = _verified_marker()
    fresh = _run(datetime(2026, 6, 10, 8, 4), tz)            # today's fire landed healthy, within grace
    assert derive_schedule_health(now=_at(2026, 6, 10, 8, 40, tz), marker=marker,
                                  registration_matches=True, latest_scheduled_run=fresh,
                                  cadence="daily", hhmm=(8, 0), tz=tz) == "verified_running"


@_needs_tz
def test_non_verified_markers_read_their_posture():
    tz = ZoneInfo("America/Los_Angeles")
    common = dict(now=_at(2026, 6, 10, 9, 0, tz), registration_matches=True,
                  latest_scheduled_run=None, cadence="daily", hhmm=(8, 0), tz=tz)
    assert derive_schedule_health(marker=_verified_marker(mechanism="loop", verified=False),
                                  **common) == "session_only"
    assert derive_schedule_health(marker=_verified_marker(verified=False, mechanism="launchd"),
                                  **common) == "unverified"
    assert derive_schedule_health(marker={"installed": False}, **common) == "absent"


# --- the DST-boundary proof (the subtle case) -----------------------------
@_needs_tz
def test_dst_fall_back_daily_fire_is_not_spuriously_missed():
    # America/New_York daily 09:00. DST ends 2026-11-01: 09:00 local shifts from 13:00 UTC (EDT) to
    # 14:00 UTC (EST). A naive `last_fire + 24h` in UTC would place the Nov-1 fire an hour early and
    # wrongly flag it missed; the DST-aware local-wall-clock computation must NOT.
    tz = ZoneInfo("America/New_York")
    marker = _verified_marker(cadence="daily")
    last = _run(datetime(2026, 10, 31, 9, 5), tz)            # Sat 09:05 EDT == 13:05 UTC
    now = _at(2026, 11, 1, 9, 20, tz)                        # Sun 09:20 EST == 14:20 UTC, inside grace
    assert missed_fires(now, last["started_at"], "daily", (9, 0), tz) == 0
    assert derive_schedule_health(now=now, marker=marker, registration_matches=True,
                                  latest_scheduled_run=last, cadence="daily", hhmm=(9, 0),
                                  tz=tz) == "verified_running"
    # And once the DST-shifted fire's grace truly elapses, it counts exactly once.
    later = _at(2026, 11, 1, 9, 45, tz)                      # 14:45 UTC > 14:00 + 0:30
    assert missed_fires(later, last["started_at"], "daily", (9, 0), tz) == 1
    assert derive_schedule_health(now=later, marker=marker, registration_matches=True,
                                  latest_scheduled_run=last, cadence="daily", hhmm=(9, 0),
                                  tz=tz) == "not_recently_observed"


@_needs_tz
def test_dst_spring_forward_daily_fire_is_not_spuriously_missed():
    # DST begins 2026-03-08: 09:00 local shifts from 14:00 UTC (EST) to 13:00 UTC (EDT).
    tz = ZoneInfo("America/New_York")
    last = _run(datetime(2026, 3, 7, 9, 5), tz)             # Sat 09:05 EST == 14:05 UTC
    now = _at(2026, 3, 8, 9, 20, tz)                        # Sun 09:20 EDT == 13:20 UTC, inside grace
    assert missed_fires(now, last["started_at"], "daily", (9, 0), tz) == 0


@_needs_tz
def test_reference_state_set_matches_the_documented_precedence():
    # Every token the reference implementation can emit is one of the eight documented precedence states.
    emitted = {
        "absent", "session_only", "unverified", "registration_drift", "latest_run_blocked",
        "needs_attention", "not_recently_observed", "verified_running",
    }
    assert emitted == set(PRECEDENCE)


# ===========================================================================
# (2) Contract-text pins — the precedence + liveness contract is single-homed
# ===========================================================================
def _precedence_rows():
    """Parse the internals.md `schedule-health-contract:precedence` marked table into an ordered list of
    (rank, token) pairs."""
    text = INTERNALS.read_text(encoding="utf-8")
    m = re.search(
        r"<!-- schedule-health-contract:precedence -->\n(.*?)\n<!-- /schedule-health-contract:precedence -->",
        text, re.DOTALL)
    assert m, "internals.md is missing the schedule-health-contract:precedence marked table"
    rows = []
    for line in m.group(1).splitlines():
        if not line.startswith("|") or set(line.replace("|", "").strip()) <= {"-"}:
            continue
        cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
        if cells[0].lower() in {"rank", "priority"}:  # header
            continue
        rows.append((cells[0], cells[1]))
    return rows


def test_internals_owns_the_eight_state_precedence_in_order():
    rows = _precedence_rows()
    assert [tok for _, tok in rows] == list(PRECEDENCE), (
        "internals.md must enumerate the eight schedule-health states in the documented precedence order")
    assert [rank for rank, _ in rows] == [str(i) for i in range(1, 9)], "ranks must be 1..8 in order"


def test_internals_documents_grace_and_missed_fire_thresholds():
    text = INTERNALS.read_text(encoding="utf-8").lower()
    assert "schedule health" in text
    assert "30-minute" in text or "30 minute" in text, "the documented 30-minute grace period must appear"
    assert "grace" in text
    # the one-vs-two missed-fire thresholds and their labels
    assert "not recently observed" in text and "needs attention" in text
    # the three compared sources
    assert "scheduled-attributable run" in text
    assert "registration" in text and "registry" in text
    # DST-aware and unmetered
    assert "timezone" in text
    assert "unmetered" in text or "local and unmetered" in text or "local, unmetered" in text


def test_internals_scopes_liveness_to_verified_and_excludes_the_canary():
    text = INTERNALS.read_text(encoding="utf-8").lower()
    assert "canary" in text and "ordinary scheduled fire" in text
    assert "verified" in text


def test_conventions_defines_latest_scheduled_attributable_run_excluding_canary():
    text = CONVENTIONS.read_text(encoding="utf-8")
    low = text.lower()
    assert "latest scheduled-attributable run" in low
    assert "canary_run_id" in text  # excluded because a canary is not an ordinary scheduled fire
    assert "internals.md" in text   # one hop to the precedence/liveness home


def test_home_renders_derived_schedule_health_one_hop():
    text = HOME.read_text(encoding="utf-8")
    low = text.lower()
    assert "schedule health" in low
    assert "internals.md" in text  # points one hop; never restates the precedence
    # the derived anomaly states are surfaced in the home status line
    for token in ("not recently observed", "needs attention", "registration"):
        assert token in low, f"home.md status line must surface the {token!r} schedule-health state"


def test_scheduling_doctrine_names_local_unmetered_health_one_hop():
    text = SCHEDULING.read_text(encoding="utf-8")
    low = text.lower()
    assert "schedule health" in low or "scheduler liveness" in low
    assert "unmetered" in low
    assert "internals.md" in text  # one hop to the single home
    assert "canary" in low and "ordinary scheduled fire" in low


# ===========================================================================
# (3) The behavioural evals are appended, executable-fixture, and cover the states
# ===========================================================================
def _evals(skill):
    import json
    path = ROOT / "skills" / skill / "evals" / "evals.json"
    return json.loads(path.read_text(encoding="utf-8"))["evals"]


def test_agent_schedule_health_evals_are_executable_fixture_and_cover_the_matrix():
    agent = _evals("job-search-agent")
    health = [c for c in agent if "schedule health" in c["scenario"].lower()
              or "schedule liveness" in c["scenario"].lower()]
    assert health, "job-search-agent must carry schedule-health derivation evals"
    assert all(c.get("coverage_kind") == "executable_fixture" for c in health)
    matrix = " ".join(" ".join([c["scenario"], c["prompt"], *c["expectations"]]).lower() for c in health)
    for phrase in ("registration drift", "blocked", "needs attention", "not recently observed",
                   "grace", "daylight", "canary", "unmetered"):
        assert phrase in matrix, f"agent schedule-health evals miss {phrase!r}"


def test_home_schedule_health_eval_present_and_executable_fixture():
    home = _evals("job-search")
    health = [c for c in home if "schedule health" in c["scenario"].lower()]
    assert health, "job-search must carry a home schedule-health rendering eval"
    assert all(c.get("coverage_kind") == "executable_fixture" for c in health)
    matrix = " ".join(" ".join([c["scenario"], c["prompt"], *c["expectations"]]).lower() for c in health)
    assert "scheduled-attributable run" in matrix or "latest scheduled" in matrix
    assert "unmetered" in matrix or "local" in matrix
