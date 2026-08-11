"""Tests for the stderr diagnostics the agent-invoked scripts write about what they did.

The scripts in the `scripts/` directories are run by an agent, not by a person watching a terminal,
so an agent needs a line it can read to confirm what a call did. Each script this file covers wrote
nothing to stderr on the path that succeeds, which left the agent with the exit status and whatever
that path puts on stdout. Each test here runs one script and checks the sentence it wrote to stderr
and the exit status it gave back. `queue-detail-read.sh` and `record-judgment.sh` both append to the
log file and write nothing to stdout, so the new stderr line has to leave stdout empty, and that is
checked too. `dedup.sh --near` does write to stdout, so its tests check that every id that used to
come back still does, in the same order. `list-detail-read-queue.sh` writes the read list to stdout,
so its tests check that the rows that used to come back still do. `run-counts.sh`, `run-matches.sh`
and `posting-counts.sh` write the digest's numbers, the digest's rows and the home card's three
counts, so their tests pin the whole block of stdout, byte for byte. `workspace-discovery.sh` had no
`>&2` write on any path at all, and its three `key=value` lines are read by key, so its tests pin the
whole block of stdout too. `validate-workspace.sh` writes its findings to stdout and exits 1, so its
new line is on the exit-0 path only and its tests check that a workspace with findings still leaves
stderr empty. `dedup-surfaced.awk` is not run directly: it runs inside `record-api-response.sh` on
the search route, which redirects its stdout into the file it then appends to `jobs.jsonl`, so every
line that program prints on stdout becomes an event in the user's log. Its tests drive
`record-api-response.sh` and check that the diagnostic reached stderr, that stdout stayed empty, and
that the appended events are the same ones as before. `event-log-append.sh` takes the event on stdin
and writes nothing to stdout, so its tests check that stdout stays empty on the append, on the skip
and on every one of its seven refusals.

The last section is a guard rather than a content test. Every test above pins one script's exact
sentence, so deleting that sentence from the script turns the test that reads it red — that case is
already covered. The case that is not is an edit that drops a feature and takes both with it: the
line goes out of the script and the test written for it goes out of the suite, and every test left
passes over a script that has stopped saying what it did. The guard is the one that fails then. It
runs one invocation per exit-0 branch of the ten scripts and reads no wording — only that the branch
wrote to stderr, how many lines it wrote, and that each line opens with the prefix that branch uses.
Reword a line and the guard stays green while the content test above goes red; delete one and the
guard goes red.

The `dedup.sh --near` tests and the failed-append test run through POSIX `sh` and through `dash`
where it is installed, the way `tests/test_dedup_guard.py` drives that same script. Helpers are
defined here rather than imported from `tests/test_mechanics_scripts.py` or
`tests/test_dedup_guard.py`, so this file collects on its own.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN_SCRIPTS = ROOT / "skills" / "job-search-run" / "scripts"
RUNBOOK_SCRIPTS = ROOT / "skills" / "job-search-runbook" / "scripts"
QUEUE = RUN_SCRIPTS / "queue-detail-read.sh"
JUDGE = RUN_SCRIPTS / "record-judgment.sh"
DEDUP = RUN_SCRIPTS / "dedup.sh"
LIST_QUEUE = RUN_SCRIPTS / "list-detail-read-queue.sh"
COUNTS = RUN_SCRIPTS / "run-counts.sh"
MATCHES = RUN_SCRIPTS / "run-matches.sh"
POSTINGS = ROOT / "skills" / "job-search" / "scripts" / "posting-counts.sh"
DISCOVERY = RUNBOOK_SCRIPTS / "workspace-discovery.sh"
VALIDATOR = RUNBOOK_SCRIPTS / "validate-workspace.sh"
RECORD_API = RUN_SCRIPTS / "record-api-response.sh"
APPEND = RUN_SCRIPTS / "event-log-append.sh"
SEARCH_FIXTURE = ROOT / "tests" / "fixtures" / "api-responses" / "search.linkedin.json"

RID = "2026-08-05T16-47-00Z"

SHELLS = ["sh"] + (["dash"] if shutil.which("dash") else [])


def run_script(script, *args, shell="sh", env=None):
    """Run one mechanics script through POSIX `sh` (portable; not bash) and capture both streams."""
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([shell, str(script), *[str(a) for a in args]],
                          capture_output=True, text=True, env=e)


def run_near(rows, shell="sh"):
    """Run `dedup.sh --near` with `rows` (list of (id, company, title)) on stdin."""
    stdin = "".join("%s\t%s\t%s\n" % row for row in rows)
    return subprocess.run([shell, str(DEDUP), "--near"], input=stdin,
                          capture_output=True, text=True)


def run_append(jobs, event, shell="sh"):
    """Run `event-log-append.sh` over `jobs` with one event line on stdin."""
    return subprocess.run([shell, str(APPEND), str(jobs)], input=event + "\n",
                          capture_output=True, text=True)


def lines(path):
    """The events in a jobs.jsonl, parsed, skipping blank lines."""
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


# ------------------------------------------------------------------ queue-detail-read.sh

def test_queueing_a_posting_says_it_queued_it(tmp_path):
    """The write is announced on stderr. The other branch, the one that finds the posting already
    queued, prints `is already queued for this run — nothing written`. Without this line a queued
    posting and one queued twice both give nothing on stdout, nothing on stderr and exit 0, so the
    caller cannot tell them apart."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"77"}\n' % RID,
        encoding="utf-8")
    r = run_script(QUEUE, jobs, "--run-id", RID, "--source", "linkedin", "--source-id", "77")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert "queue-detail-read: queued linkedin:77 for run %s" % RID in r.stderr, r.stderr
    # The event still landed, and exactly once.
    assert sum(1 for e in lines(jobs) if e["event"] == "queued") == 1

    # The second call is the no-op branch, and it still says the opposite thing.
    again = run_script(QUEUE, jobs, "--run-id", RID, "--source", "linkedin", "--source-id", "77")
    assert again.returncode == 0, again.stdout + again.stderr
    assert "already queued" in again.stderr, again.stderr
    assert "queued linkedin:77 for run" not in again.stderr, again.stderr


# ------------------------------------------------------------------ record-judgment.sh

def test_recording_a_judgment_says_the_verdict_back(tmp_path):
    """The recorded verdict, said back from the variables this script validated rather than
    re-parsed from the line it wrote, so the caller can check the flags it passed are the fields the
    log now holds. Without it, a recorded judgment and a refused one both give nothing on stdout,
    nothing on stderr and exit 0."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"77",'
        '"title":"Analyst","company_name":"Acme"}\n' % RID, encoding="utf-8")
    r = run_script(JUDGE, jobs, "--run-id", RID, "--source", "linkedin", "--source-id", "77",
                   "--detail-read", "true", "--relevant", "true", "--match", "moderate",
                   "--reasoning", "fits the brief")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert "record-judgment: recorded linkedin:77 for run %s" % RID in r.stderr, r.stderr
    assert "relevant true" in r.stderr, r.stderr
    assert "match moderate" in r.stderr, r.stderr
    assert "detail_read true" in r.stderr, r.stderr
    # An optional flag that was not passed is not invented.
    assert "same_role_as" not in r.stderr, r.stderr
    assert "needs_human_check" not in r.stderr, r.stderr
    # The judgment still landed, and exactly once.
    assert sum(1 for e in lines(jobs) if e["event"] == "evaluated") == 1


def test_the_verdict_line_carries_the_optional_flags_that_were_passed(tmp_path):
    """--same-role-as is what the digest's also_posted column is built from, so a caller that passed
    it can confirm it reached the log."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"78",'
        '"title":"Analyst","company_name":"Acme"}\n' % RID, encoding="utf-8")
    r = run_script(JUDGE, jobs, "--run-id", RID, "--source", "linkedin", "--source-id", "78",
                   "--detail-read", "false", "--relevant", "true", "--match", "weak",
                   "--needs-human-check", "true", "--same-role-as", "linkedin:77",
                   "--reasoning", "the same opening as 77")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "same_role_as linkedin:77" in r.stderr, r.stderr
    assert "needs_human_check true" in r.stderr, r.stderr


# ------------------------------------------------------------------ dedup.sh --near

@pytest.mark.parametrize("shell", SHELLS)
def test_near_names_the_row_each_collapsed_row_was_matched_to(shell):
    """`job-search-run/SKILL.md` asks for `--same-role-as <source>:<source_id>` on every posting
    `--near` left out, naming the row that was read. `--near` works out that pairing to decide the
    row is a duplicate and used to drop it, so the caller had to compare its own input against
    stdout by hand to recover which id went with which."""
    r = run_near([("linkedin:aa1", "Acme", "Software Engineer (Remote)"),
                  ("linkedin:aa2", "Acme", "Software Engineer (NYC)")], shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.split() == ["linkedin:aa1"], r.stdout
    assert "dedup.sh --near: linkedin:aa2 is the same opening as linkedin:aa1" in r.stderr, r.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_near_reports_how_many_rows_it_read_and_handed_back(shell):
    """65 ids out of a 67-row input, with 0 bytes on stderr, is what the 2026-08-10 run got back at
    16:27:18 from a call that had worked. It wrote that the script "reads from jobs.jsonl directly,
    not via my generated TSV" and "seems to have queried the log itself" (16:27:26), then spent
    three more bash calls, at 16:27:34, 16:27:42 and 16:27:49, re-deriving the rows, reading the
    script's source, and running the same call a second time."""
    r = run_near([("linkedin:aa1", "Acme", "Software Engineer (Remote)"),
                  ("linkedin:aa2", "Acme", "Software Engineer (NYC)"),
                  ("linkedin:bb1", "Beta", "Analyst")], shell=shell)
    assert "dedup.sh --near: 3 rows read, 2 openings to judge, 1 the same opening as one above" \
        in r.stderr, r.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_near_reports_zero_collapsed_when_every_row_is_its_own_opening(shell):
    """The count line prints on the path where no row is collapsed too, so a caller that gets back
    no pairing line still gets a sentence saying how many rows the script read and how many it
    handed back."""
    r = run_near([("linkedin:aa1", "Acme", "Engineer"),
                  ("linkedin:bb1", "Beta", "Analyst")], shell=shell)
    assert "2 rows read, 2 openings to judge, 0 the same opening as one above" in r.stderr, r.stderr
    assert "is the same opening as" not in r.stderr, r.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_near_accounts_for_every_row_it_read(shell):
    """A row with no id and a row repeating an id already read are each dropped by their own guard.
    With three counts on the line, those rows were counted in `rows read` and in nothing else: 4
    rows came back as 2 openings and 0 collapsed, and a caller looking for the other two rows would
    run the script again or write its own parser. Each guard now has a count, printed when it is not
    zero, so the printed numbers sum to the rows read."""
    rows = [("linkedin:aa1", "Acme", "Engineer"),
            ("linkedin:aa1", "Acme", "Engineer"),
            ("", "Beta", "Analyst"),
            ("linkedin:bb1", "Beta", "Analyst")]
    r = run_near(rows, shell=shell)
    assert ("dedup.sh --near: 4 rows read, 2 openings to judge, 0 the same opening as one above, "
            "1 with no id, 1 the same id as one above") in r.stderr, r.stderr

    # Neither guard fired here, so neither count is printed and the line stays three counts.
    clean = run_near([("linkedin:aa1", "Acme", "Engineer"),
                      ("linkedin:bb1", "Beta", "Analyst")], shell=shell)
    assert "with no id" not in clean.stderr, clean.stderr
    assert "the same id as one above" not in clean.stderr, clean.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_the_near_counts_read_as_english_when_each_of_them_is_one(shell):
    """One row in used to read `1 rows read, 1 openings to judge`. The two counts that carry a noun
    take the singular at one; the three that carry none read the same at every number, so the empty
    call below still reads `0 rows read`."""
    r = run_near([("linkedin:aa1", "Acme", "Engineer")], shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "linkedin:aa1\n", r.stdout
    assert ("dedup.sh --near: 1 row read, 1 opening to judge, 0 the same opening as one above"
            in r.stderr), r.stderr

    empty = run_near([], shell=shell)
    assert empty.returncode == 0, empty.stdout + empty.stderr
    assert empty.stdout == "", empty.stdout
    assert ("dedup.sh --near: 0 rows read, 0 openings to judge, 0 the same opening as one above"
            in empty.stderr), empty.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_near_stdout_is_unchanged_by_the_new_stderr(shell):
    """stdout is the id list the caller works from. Every id that used to come back still does, in
    the same order."""
    rows = [("linkedin:aa1", "Acme", "Engineer (Remote)"),
            ("linkedin:aa2", "Acme", "Engineer (NYC)"),
            ("linkedin:bb1", "Beta", "Analyst"),
            ("", "Gamma", "Ignored"),
            ("linkedin:cc1", "", "")]
    r = run_near(rows, shell=shell)
    assert r.stdout == "linkedin:aa1\nlinkedin:bb1\nlinkedin:cc1\n", r.stdout


# ------------------------------------------------------------------ list-detail-read-queue.sh

def test_the_read_queue_says_how_much_of_it_is_worked_off(tmp_path):
    """Two postings are queued here and one of them is judged, so one row comes back. That row was
    the whole answer: it did not say how many postings the run queued or how many of them were
    already judged, so a caller could not tell a queue most of the way worked off from a queue with
    one posting in it."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("".join([
        '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"1",'
        '"posting_id_at_seen":"jp_1","source_url":"https://example.test/1",'
        '"title":"Analyst","company_name":"Acme"}\n' % RID,
        '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"2",'
        '"posting_id_at_seen":"jp_2","source_url":"https://example.test/2",'
        '"title":"Engineer","company_name":"Beta"}\n' % RID,
        '{"event":"queued","run_id":"%s","source":"linkedin","source_id":"1"}\n' % RID,
        '{"event":"queued","run_id":"%s","source":"linkedin","source_id":"2"}\n' % RID,
        '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"1",'
        '"relevant":"false"}\n' % RID,
    ]), encoding="utf-8")
    r = run_script(LIST_QUEUE, jobs, RID)
    assert r.returncode == 0, r.stdout + r.stderr
    # The whole row, not a count of rows: the six columns each carry a different value here, so a
    # dropped column, a reordered pair, or a changed separator fails this line.
    assert r.stdout == "linkedin\t2\tjp_2\thttps://example.test/2\tEngineer\tBeta\n", r.stdout
    assert "list-detail-read-queue: 2 queued for run %s, 1 already judged, 1 to read" % RID \
        in r.stderr, r.stderr


def test_a_run_id_that_names_no_event_is_not_the_same_as_an_empty_queue(tmp_path):
    """A mistyped run id reads `0 queued`, where a worked-off queue reads its real queued count with
    every one of them judged."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"queued","run_id":"%s","source":"linkedin","source_id":"1"}\n' % RID,
        encoding="utf-8")
    r = run_script(LIST_QUEUE, jobs, "2026-01-01T00-00-00Z")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert "0 queued for run 2026-01-01T00-00-00Z, 0 already judged, 0 to read" in r.stderr, r.stderr


# ------------------------------------------------------------------ run-counts.sh

# Six lines, five of them naming RID: one answered search that brought in two rows, the two postings
# it surfaced, one detail read, and one judgment. The sixth line names another run, so a run_id
# guard that stopped filtering would print `6 of 6`.
WORKED_LOG = "".join([
    '{"event":"call","run_id":"%s","route":"search-jobs","ok":"true","source":"linkedin",'
    '"query_id":"q1","rows_new":2}\n' % RID,
    '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"1"}\n' % RID,
    '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"2"}\n' % RID,
    '{"event":"detail","run_id":"%s","source":"linkedin","source_id":"1"}\n' % RID,
    '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"1","relevant":"true",'
    '"match":"strong"}\n' % RID,
    '{"event":"surfaced","run_id":"other","source":"ashby","source_id":"9"}\n',
])

# What the run above prints on stdout, byte for byte. Pinned as the whole block rather than as a
# count of lines or a set of substrings: every key is here in its printed order, so a renamed key, a
# reordered pair, a dropped key or a changed number fails this comparison.
WORKED_STDOUT = (
    "postings_surfaced=2\n"
    "postings_reviewed=1\n"
    "postings_unreviewed=1\n"
    "postings_detail_read=1\n"
    "match_strong=1\n"
    "match_moderate=0\n"
    "match_weak=0\n"
    "filtered_out=0\n"
    "duplicates_of_another=0\n"
    "by_source_linkedin=2\n"
    "calls_searches=1\n"
    "calls_detail_reads=0\n"
    "calls_other=0\n"
    "calls_total_metered=1\n"
    "calls_failed=0\n"
    "searches_never_succeeded=0\n"
    "searches_never_succeeded_ids=\n"
    "rows_new_total=2\n"
)

# The same keys with every number zeroed, which is what a run id no event carries prints: 332 bytes
# over 17 lines. The one key missing is `by_source_linkedin` — no posting surfaced, so no source is
# named.
ZEROED_STDOUT = (
    "postings_surfaced=0\n"
    "postings_reviewed=0\n"
    "postings_unreviewed=0\n"
    "postings_detail_read=0\n"
    "match_strong=0\n"
    "match_moderate=0\n"
    "match_weak=0\n"
    "filtered_out=0\n"
    "duplicates_of_another=0\n"
    "calls_searches=0\n"
    "calls_detail_reads=0\n"
    "calls_other=0\n"
    "calls_total_metered=0\n"
    "calls_failed=0\n"
    "searches_never_succeeded=0\n"
    "searches_never_succeeded_ids=\n"
    "rows_new_total=0\n"
)


@pytest.mark.parametrize("shell", SHELLS)
def test_run_counts_says_how_many_lines_of_the_log_name_the_run(tmp_path, shell):
    """Every key prints whether or not the run id matched anything, so a run that did nothing and a
    run id no event carries both printed the same 332 bytes on stdout, 0 bytes on stderr and exit 0
    (measured 2026-08-11 with `sh skills/job-search-run/scripts/run-counts.sh <log>
    2026-01-01T00-00-00Z | wc -c`). This line says which of the two happened."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(WORKED_LOG, encoding="utf-8")
    r = run_script(COUNTS, jobs, RID, shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "run-counts.sh: 5 of 6 lines in %s name run %s" % (jobs, RID) in r.stderr, r.stderr
    assert r.stdout == WORKED_STDOUT, r.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_a_run_id_no_event_carries_reads_zero_lines_rather_than_zero_work(tmp_path, shell):
    """A mistyped run id reads `0 of 6 lines`, where a run whose events are in the log reads a count
    above zero even when it surfaced nothing. stdout is the same zeroed key set it was before this
    line existed."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(WORKED_LOG, encoding="utf-8")
    r = run_script(COUNTS, jobs, "2026-01-01T00-00-00Z", shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "run-counts.sh: 0 of 6 lines in %s name run 2026-01-01T00-00-00Z" % jobs \
        in r.stderr, r.stderr
    assert r.stdout == ZEROED_STDOUT, r.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_run_counts_writes_the_line_on_the_path_that_exits_1(tmp_path, shell):
    """A relevant posting carrying no band makes this script print `INVALID …` and exit 1. The line
    is written before that check runs, so the caller reading a failed call gets it too."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("".join([
        '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"1"}\n' % RID,
        '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"1",'
        '"relevant":"true"}\n' % RID,
    ]), encoding="utf-8")
    r = run_script(COUNTS, jobs, RID, shell=shell)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "run-counts.sh: 2 of 2 lines in %s name run %s" % (jobs, RID) in r.stderr, r.stderr
    assert r.stdout == (
        "postings_surfaced=1\n"
        "postings_reviewed=1\n"
        "postings_unreviewed=0\n"
        "postings_detail_read=0\n"
        "match_strong=0\n"
        "match_moderate=0\n"
        "match_weak=0\n"
        "filtered_out=0\n"
        "duplicates_of_another=0\n"
        "by_source_linkedin=1\n"
        "calls_searches=0\n"
        "calls_detail_reads=0\n"
        "calls_other=0\n"
        "calls_total_metered=0\n"
        "calls_failed=0\n"
        "searches_never_succeeded=0\n"
        "searches_never_succeeded_ids=\n"
        "rows_new_total=0\n"
        "INVALID relevant-row-without-a-band=1\n"
    ), r.stdout


# ------------------------------------------------------------------ run-matches.sh

def surfaced(source_id, run_id=RID):
    """One `surfaced` event. `run-matches.awk` reads no field but the ids off this event — every
    column it prints comes off the judgment — so the three keys here are all it needs."""
    return ('{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"%s"}\n'
            % (run_id, source_id))


def evaluated(source_id, band, needs_human_check="false", same_role_as=None, location=None,
              run_id=RID):
    """One `evaluated` event carrying the fields the listing prints. `band` None is a posting judged
    not relevant, which reaches the listing as `filtered`; a band of `""` is a posting judged
    relevant carrying no band at all."""
    relevant = "false" if band is None else "true"
    match = "" if band is None else ',"match":"%s"' % band
    role = "" if same_role_as is None else ',"same_role_as":"%s"' % same_role_as
    where = location if location is not None else "City %s" % source_id
    return ('{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"%s",'
            '"relevant":"%s"%s,"title":"Engineer %s","company_name":"Company %s",'
            '"location_display":"%s","source_url":"https://example.test/%s",'
            '"needs_human_check":"%s","posted_at":"2026-08-04","reasoning":"Judged %s"%s}\n'
            % (run_id, source_id, relevant, match, source_id, source_id, where, source_id,
               needs_human_check, source_id, role))


# One run judged in all four bands, with one more posting recorded as the same opening as `s1`. The
# four band counts are 1, 2, 3 and 4 — every one different — so a `printf` that reads the wrong
# counter prints a number this file does not expect.
FOUR_BAND_LOG = "".join(
    [surfaced(s) for s in ["s1", "m1", "m2", "w1", "w2", "w3", "f1", "f2", "f3", "f4", "d1"]]
    + [evaluated("s1", "strong", needs_human_check="true")]
    + [evaluated(s, "moderate") for s in ["m1", "m2"]]
    + [evaluated(s, "weak") for s in ["w1", "w2", "w3"]]
    + [evaluated(s, None) for s in ["f1", "f2", "f3", "f4"]]
    + [evaluated("d1", "strong", same_role_as="linkedin:s1", location="Portland, OR")])

# What the run above prints on stdout, byte for byte. Pinned as the whole listing rather than as a
# count of rows: the eleven columns of the first row each hold a different non-empty value, so a
# dropped column, a reordered pair or a changed separator fails this comparison. `d1` has no row of
# its own — its location is the last column of the row it names.
FOUR_BAND_STDOUT = (
    "strong\tlinkedin\ts1\tEngineer s1\tCompany s1\tCity s1\thttps://example.test/s1\ttrue\t"
    "2026-08-04\tJudged s1\tPortland, OR\n"
    "moderate\tlinkedin\tm1\tEngineer m1\tCompany m1\tCity m1\thttps://example.test/m1\tfalse\t"
    "2026-08-04\tJudged m1\t\n"
    "moderate\tlinkedin\tm2\tEngineer m2\tCompany m2\tCity m2\thttps://example.test/m2\tfalse\t"
    "2026-08-04\tJudged m2\t\n"
    "weak\tlinkedin\tw1\tEngineer w1\tCompany w1\tCity w1\thttps://example.test/w1\tfalse\t"
    "2026-08-04\tJudged w1\t\n"
    "weak\tlinkedin\tw2\tEngineer w2\tCompany w2\tCity w2\thttps://example.test/w2\tfalse\t"
    "2026-08-04\tJudged w2\t\n"
    "weak\tlinkedin\tw3\tEngineer w3\tCompany w3\tCity w3\thttps://example.test/w3\tfalse\t"
    "2026-08-04\tJudged w3\t\n"
    "filtered\tlinkedin\tf1\tEngineer f1\tCompany f1\tCity f1\thttps://example.test/f1\tfalse\t"
    "2026-08-04\tJudged f1\t\n"
    "filtered\tlinkedin\tf2\tEngineer f2\tCompany f2\tCity f2\thttps://example.test/f2\tfalse\t"
    "2026-08-04\tJudged f2\t\n"
    "filtered\tlinkedin\tf3\tEngineer f3\tCompany f3\tCity f3\thttps://example.test/f3\tfalse\t"
    "2026-08-04\tJudged f3\t\n"
    "filtered\tlinkedin\tf4\tEngineer f4\tCompany f4\tCity f4\thttps://example.test/f4\tfalse\t"
    "2026-08-04\tJudged f4\t\n"
)

def tally(named, total, jobs, run_id, strong, moderate, weak, filtered, dups, unbanded=0):
    """The stderr line `run-matches.sh` writes. `named` of `total` lines in the log name `run_id`, in
    the same words `run-counts.sh` says it in — the two scripts read the same log and are meant to
    reach the same pair of numbers. The noun follows `total` and the verb follows `named`, so a
    one-line log reads `1 of 1 line … names run`, which is what
    `test_the_opening_reads_as_english_when_one_line_names_the_run` holds. The sixth count is written
    only when it is above zero, so it is left off unless `unbanded` is given."""
    sixth = "" if not unbanded else \
        ", %d judged relevant with no band and given no row" % unbanded
    return ("run-matches.sh: %d of %d line%s in %s name%s run %s — %d strong, %d moderate, %d weak, "
            "%d filtered, %d the same opening as another and given no row%s\n"
            % (named, total, "" if total == 1 else "s", jobs, "s" if named == 1 else "", run_id,
               strong, moderate, weak, filtered, dups, sixth))


FOUR_BAND_LINES = len(FOUR_BAND_LOG.splitlines())


@pytest.mark.parametrize("shell", SHELLS)
def test_run_matches_reports_the_band_tally_the_digest_headings_use(tmp_path, shell):
    """`job-search-run/SKILL.md` asks for a heading that says how many strong matches there are and
    then a line for each of them. The rows come from here, and until this line existed the count
    over them did not: the agent counted the rows itself. Each count is incremented where its row is
    printed, so the heading and the rows under it cannot disagree.

    The counts are 1, 2, 3 and 4, and the run also holds one posting recorded as the same opening as
    another, which gets no row and is counted last."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(FOUR_BAND_LOG, encoding="utf-8")
    r = run_script(MATCHES, jobs, RID, shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == FOUR_BAND_STDOUT, r.stdout
    assert r.stderr == tally(FOUR_BAND_LINES, FOUR_BAND_LINES, jobs, RID, 1, 2, 3, 4, 1), r.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_a_run_that_judged_nothing_and_a_run_id_no_event_carries_read_differently(tmp_path, shell):
    """Both of those runs print no rows and an all-zero tally, so the counts alone do not say which
    one happened: measured 2026-08-11 on the log below, the two calls printed the same six zeros and
    differed only in the run id echoed back. The line opens with how many of the log's lines name the
    run, which is the number that separates them — 3 of 3 for the run that judged nothing, 0 of 3 for
    the id no event carries.

    `run-counts.sh` reports that same pair for the same log and the same id, in the same words, and
    this asserts both scripts' lines so the two cannot drift into describing it differently."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("".join([surfaced("n1"), surfaced("n2"), surfaced("n3")]), encoding="utf-8")

    judged_nothing = run_script(MATCHES, jobs, RID, shell=shell)
    assert judged_nothing.returncode == 0, judged_nothing.stdout + judged_nothing.stderr
    assert judged_nothing.stdout == "", judged_nothing.stdout
    assert judged_nothing.stderr == tally(3, 3, jobs, RID, 0, 0, 0, 0, 0), judged_nothing.stderr

    no_such_run = run_script(MATCHES, jobs, "2026-01-01T00-00-00Z", shell=shell)
    assert no_such_run.returncode == 0, no_such_run.stdout + no_such_run.stderr
    assert no_such_run.stdout == "", no_such_run.stdout
    assert no_such_run.stderr == tally(0, 3, jobs, "2026-01-01T00-00-00Z", 0, 0, 0, 0, 0), \
        no_such_run.stderr

    assert judged_nothing.stderr != no_such_run.stderr

    c = run_script(COUNTS, jobs, RID, shell=shell)
    assert "run-counts.sh: 3 of 3 lines in %s name run %s\n" % (jobs, RID) in c.stderr, c.stderr
    c = run_script(COUNTS, jobs, "2026-01-01T00-00-00Z", shell=shell)
    assert "run-counts.sh: 0 of 3 lines in %s name run 2026-01-01T00-00-00Z\n" % jobs in c.stderr, \
        c.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_a_run_id_no_event_carries_prints_no_row_off_a_log_full_of_judgments(tmp_path, shell):
    """The run id is read on every line before anything else, so a log holding eleven judged
    postings prints nothing for an id none of them carries. The tally says so twice over: 0 of 22
    lines name it, and every count is zero."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(FOUR_BAND_LOG, encoding="utf-8")
    r = run_script(MATCHES, jobs, "2026-01-01T00-00-00Z", shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert r.stderr == tally(0, FOUR_BAND_LINES, jobs, "2026-01-01T00-00-00Z", 0, 0, 0, 0, 0), \
        r.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_the_last_count_follows_same_role_as_being_there_not_what_it_names(tmp_path, shell):
    """A posting whose judgment carries `same_role_as` is the same opening as another, so it gets no
    row and is counted in the last number instead. The test is whether the field is there, never on
    what it names, which is the test `run-counts.sh` counts `duplicates_of_another` on — so the two
    scripts reach the same number and this test checks both.

    Four postings carry the field and not one of them puts a location on a row: `d1` names a posting
    this run surfaced and never judged, `d2` names an id no search of this run turned up, `d3`
    carries a value not written as `<source>:<source_id>` at all, and `d4` names `a1` but came back
    without a location, which reaches this script as the four characters `null`. All four are
    counted. Measured 2026-08-11: with the count taken after the first-colon split instead, `d3`
    goes uncounted, and with it taken after the empty-location check, `d4` does."""
    log = "".join([
        surfaced("a1"), surfaced("d1"), surfaced("d2"), surfaced("d3"), surfaced("d4"),
        evaluated("d1", "strong", same_role_as="linkedin:a1"),
        evaluated("d2", "strong", same_role_as="linkedin:zz9"),
        evaluated("d3", "strong", same_role_as="the other Austin listing"),
        evaluated("d4", "strong", same_role_as="linkedin:a1", location="null"),
    ])
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(log, encoding="utf-8")
    n = len(log.splitlines())
    r = run_script(MATCHES, jobs, RID, shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert r.stderr == tally(n, n, jobs, RID, 0, 0, 0, 0, 4), r.stderr
    # All four were judged strong, and neither script counts any of them as strong.
    c = run_script(COUNTS, jobs, RID, shell=shell)
    assert c.returncode == 0, c.stdout + c.stderr
    assert "duplicates_of_another=4\n" in c.stdout, c.stdout
    assert "match_strong=0\n" in c.stdout, c.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_a_relevant_row_with_no_band_is_counted_where_it_is_left_out(tmp_path, shell):
    """A row judged relevant whose `match` is none of strong, moderate and weak gets no row here.
    Without a count of its own it would be in the log and in none of the five numbers, so the tally
    would not add up to the postings this run reviewed. It is counted in a sixth number, printed
    only when it is not zero. `run-counts.sh` is the script that owns this finding and exits 1 on
    it; this one prints its listing and exits 0, and the two report the same number."""
    log = "".join([
        surfaced("s1"), surfaced("u1"),
        evaluated("s1", "strong"),
        evaluated("u1", ""),
    ])
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(log, encoding="utf-8")
    n = len(log.splitlines())
    r = run_script(MATCHES, jobs, RID, shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == (
        "strong\tlinkedin\ts1\tEngineer s1\tCompany s1\tCity s1\thttps://example.test/s1\tfalse\t"
        "2026-08-04\tJudged s1\t\n"
    ), r.stdout
    assert r.stderr == tally(n, n, jobs, RID, 1, 0, 0, 0, 0, unbanded=1), r.stderr
    c = run_script(COUNTS, jobs, RID, shell=shell)
    assert c.returncode == 1, c.stdout + c.stderr
    assert "INVALID relevant-row-without-a-band=1\n" in c.stdout, c.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_the_sixth_count_is_left_off_when_no_row_is_missing_a_band(tmp_path, shell):
    """The run in `test_run_matches_reports_the_band_tally_the_digest_headings_use` has no such row,
    and its tally is five counts. This checks the wording is absent rather than present with a
    zero."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(FOUR_BAND_LOG, encoding="utf-8")
    r = run_script(MATCHES, jobs, RID, shell=shell)
    assert "with no band" not in r.stderr, r.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_the_opening_reads_as_english_when_one_line_names_the_run(tmp_path, shell):
    """Both scripts open on the same six words and both used to read `1 of 1 lines … name run`. The
    noun follows the total and the verb follows the count in front of it, so a log of one line reads
    `1 of 1 line … names run` and a log of six with one line matching reads `1 of 6 lines … names
    run`. Zero takes the plural verb, and a log of one line naming another run reads `0 of 1 line …
    name run`. Both scripts are asserted on every log, because the two are meant to report the same
    pair in the same words."""
    one = tmp_path / "one.jsonl"
    one.write_text(surfaced("only"), encoding="utf-8")
    c = run_script(COUNTS, one, RID, shell=shell)
    assert c.returncode == 0, c.stdout + c.stderr
    assert "run-counts.sh: 1 of 1 line in %s names run %s\n" % (one, RID) in c.stderr, c.stderr
    m = run_script(MATCHES, one, RID, shell=shell)
    assert m.returncode == 0, m.stdout + m.stderr
    assert m.stderr == tally(1, 1, one, RID, 0, 0, 0, 0, 0), m.stderr
    assert "1 of 1 line in %s names run" % one in m.stderr, m.stderr

    # The same one line, read for a run it does not name: the verb goes back to the plural and the
    # noun stays singular, because the noun follows the total rather than the count in front of it.
    c0 = run_script(COUNTS, one, "2026-01-01T00-00-00Z", shell=shell)
    assert "run-counts.sh: 0 of 1 line in %s name run" % one in c0.stderr, c0.stderr
    m0 = run_script(MATCHES, one, "2026-01-01T00-00-00Z", shell=shell)
    assert m0.stderr == tally(0, 1, one, "2026-01-01T00-00-00Z", 0, 0, 0, 0, 0), m0.stderr

    # One line of six naming the run: singular verb over a plural noun.
    six = tmp_path / "six.jsonl"
    six.write_text(surfaced("a") + "".join(
        surfaced(s, run_id="2026-01-01T00-00-00Z") for s in ["b", "c", "d", "e", "f"]),
        encoding="utf-8")
    c6 = run_script(COUNTS, six, RID, shell=shell)
    assert "run-counts.sh: 1 of 6 lines in %s names run %s\n" % (six, RID) in c6.stderr, c6.stderr
    m6 = run_script(MATCHES, six, RID, shell=shell)
    assert m6.stderr == tally(1, 6, six, RID, 0, 0, 0, 0, 0), m6.stderr
    assert "1 of 6 lines in %s names run" % six in m6.stderr, m6.stderr


# ------------------------------------------------------------------ posting-counts.sh

# Five judgments over the whole log, which is what this script reads — it takes no run id. Two
# postings were kept, one of them carrying an open question, and three were thrown out, one of those
# also carrying an open question. The three printed numbers are 2, 1 and 3 — every one different —
# so a `printf` that reads the wrong counter prints a number this file does not expect.
JUDGED_LOG = "".join([
    '{"event":"evaluated","source":"linkedin","source_id":"r1","relevant":"true",'
    '"match":"strong"}\n',
    '{"event":"evaluated","source":"linkedin","source_id":"r2","relevant":"true","match":"weak",'
    '"needs_human_check":"true"}\n',
    '{"event":"evaluated","source":"linkedin","source_id":"f1","relevant":"false"}\n',
    '{"event":"evaluated","source":"linkedin","source_id":"f2","relevant":"false"}\n',
    '{"event":"evaluated","source":"linkedin","source_id":"f3","relevant":"false",'
    '"needs_human_check":"true"}\n',
])

# What the log above prints on stdout, byte for byte, and what a log holding no judgment prints.
# Pinned as the whole block rather than as a count of lines or a set of substrings: all three keys
# are here in their printed order, so a renamed key, a reordered pair, a dropped key or a changed
# number fails this comparison. The second is not called ZEROED_STDOUT because that name is taken
# above by `run-counts.sh`'s zeroed key set, and a second binding of it would rebind the first —
# measured 2026-08-11 with it named that way, the two shells of
# test_a_run_id_no_event_carries_reads_zero_lines_rather_than_zero_work failed on their
# `assert r.stdout == ZEROED_STDOUT` while the six tests in this section passed.
JUDGED_STDOUT = "relevant=2\nto_confirm=1\nfiltered=3\n"
NO_JUDGMENT_STDOUT = "relevant=0\nto_confirm=0\nfiltered=0\n"


def read_line(lines_read, judged, aliased):
    """The stderr line `posting-counts.sh` writes.

    The three counts on it are the lines the script read, the postings carrying a judgment, and the
    postings among those whose judgment names another one. `relevant` plus `filtered` plus the third
    count equals the second, which is why the third is there. `to_confirm` is not one of the terms in
    that sum, because it counts within `relevant`.

    Each count carries its noun, and the noun and its verb are singular at one, which is what
    `test_the_counts_read_as_english_when_each_of_them_is_one` holds.
    """
    return ("posting-counts.sh: %d %s read, %d %s a judgment, %d of those %s the same opening as "
            "another posting, counted under neither relevant nor filtered\n"
            % (lines_read, "line" if lines_read == 1 else "lines",
               judged, "posting carries" if judged == 1 else "postings carry",
               aliased, "is" if aliased == 1 else "are"))


@pytest.mark.parametrize("shell", SHELLS)
def test_posting_counts_separates_an_empty_log_from_one_it_could_not_parse(tmp_path, shell):
    """Three zeroed keys at exit 0 covered a log with no judgments, an empty log, and a file of lines
    that are not JSON at all. Measured 2026-08-11 against the script as it stood before this line
    existed: 200 lines of `not json at all <n>` gave stdout `relevant=0 to_confirm=0 filtered=0`, 0
    bytes on stderr and exit 0, byte for byte what an empty file gave. `skills/job-search/SKILL.md`
    tells the agent to run this script rather than read the log itself — `grep -n 'reading that log
    yourself' skills/job-search/SKILL.md` — so those three keys were the whole of what it had."""
    junk = tmp_path / "junk.jsonl"
    junk.write_text("".join("not json at all %d\n" % i for i in range(200)), encoding="utf-8")
    r = run_script(POSTINGS, junk, shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == NO_JUDGMENT_STDOUT, r.stdout
    assert r.stderr == read_line(200, 0, 0), r.stderr

    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    e = run_script(POSTINGS, empty, shell=shell)
    assert e.returncode == 0, e.stdout + e.stderr
    assert e.stdout == NO_JUDGMENT_STDOUT, e.stdout
    assert e.stderr == read_line(0, 0, 0), e.stderr
    # The two runs printed the same stdout, and the line is what tells them apart.
    assert r.stdout == e.stdout
    assert r.stderr != e.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_posting_counts_says_how_many_postings_carry_a_judgment(tmp_path, shell):
    """A log of five judgments reads `5 lines read, 5 postings carry a judgment`, which is the pair
    that separates it from the log of 200 lines that are not JSON and from the empty one. stdout is
    the same three keys it was before this line existed."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(JUDGED_LOG, encoding="utf-8")
    r = run_script(POSTINGS, jobs, shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == JUDGED_STDOUT, r.stdout
    assert r.stderr == read_line(5, 5, 0), r.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_the_counts_on_the_line_account_for_the_postings_the_three_keys_leave_out(tmp_path, shell):
    """A posting whose judgment names another one in `same_role_as` is the same opening seen twice,
    so it is counted under neither `relevant` nor `filtered` — `grep -n 'counts under NEITHER'
    skills/job-search/scripts/posting-counts.sh` is where that is written down. `postings carry a
    judgment` counts it, because it does carry one, so with only two counts on the line an agent
    would read `2 postings carry a judgment` over a stdout saying `relevant=1 to_confirm=0
    filtered=0` and find that 1 plus 0 is not 2. The third count is that posting.

    The log also holds a `surfaced` line, so `lines read` here is above the postings judged for a
    reason other than text that is not JSON."""
    log = "".join([
        '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"r1"}\n' % RID,
        '{"event":"evaluated","source":"linkedin","source_id":"r1","relevant":"true",'
        '"match":"strong"}\n',
        '{"event":"evaluated","source":"linkedin","source_id":"d1","relevant":"true",'
        '"match":"strong","same_role_as":"linkedin:r1"}\n',
    ])
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(log, encoding="utf-8")
    r = run_script(POSTINGS, jobs, shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "relevant=1\nto_confirm=0\nfiltered=0\n", r.stdout
    assert r.stderr == read_line(3, 2, 1), r.stderr

    # The same check written as arithmetic over the numbers actually printed, so it fails on any log
    # where they stop adding up rather than only on this one. `posting-counts.sh` is the only text on
    # the line, and it carries no digit, so the three numbers are every digit run on it. Measured
    # 2026-08-11 with `judged++` moved below the `same_role_as` test in a copy of the script: the
    # line reads `1 posting carries a judgment` and this comparison fails at 1 != 1 + 0 + 1.
    lines_read, judged, aliased = [int(n) for n in re.findall(r"[0-9]+", r.stderr)]
    relevant, _, filtered = [int(l.split("=", 1)[1]) for l in r.stdout.splitlines()]
    assert judged == relevant + filtered + aliased, r.stdout + r.stderr
    assert lines_read == 3, r.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_the_counts_read_as_english_when_each_of_them_is_one(tmp_path, shell):
    """A log of one judgment used to read `1 lines read, 1 postings carry a judgment`. The noun and
    its verb take the singular at one, and the third count is a clause with a verb of its own, so at
    one it reads `1 of those is` and at any other number `n of those are`."""
    one = tmp_path / "one.jsonl"
    one.write_text('{"event":"evaluated","source":"linkedin","source_id":"r1","relevant":"true",'
                   '"match":"strong"}\n', encoding="utf-8")
    r = run_script(POSTINGS, one, shell=shell)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "relevant=1\nto_confirm=0\nfiltered=0\n", r.stdout
    assert r.stderr == ("posting-counts.sh: 1 line read, 1 posting carries a judgment, 0 of those "
                        "are the same opening as another posting, counted under neither relevant "
                        "nor filtered\n"), r.stderr

    # The third count at one, which is the only place `is` appears.
    aliased = tmp_path / "aliased.jsonl"
    aliased.write_text(
        '{"event":"evaluated","source":"linkedin","source_id":"r1","relevant":"true",'
        '"match":"strong"}\n'
        '{"event":"evaluated","source":"linkedin","source_id":"d1","relevant":"true",'
        '"match":"strong","same_role_as":"linkedin:r1"}\n', encoding="utf-8")
    a = run_script(POSTINGS, aliased, shell=shell)
    assert a.returncode == 0, a.stdout + a.stderr
    assert "2 postings carry a judgment, 1 of those is the same opening" in a.stderr, a.stderr


# ------------------------------------------------------------------ workspace-discovery.sh

def discovery_env(home):
    """An environment rooted at `home` with no registry redirect.

    `XDG_CONFIG_HOME` and `JOBSEARCH_OS_REGISTRY` are set to the empty string rather than left out:
    `run_script` starts from `os.environ`, and the script reads both with `${VAR:-...}`, which takes
    the default for an empty value as well as for an unset one. Without these two, a machine that
    exports `XDG_CONFIG_HOME` would put the registry somewhere other than
    `<home>/.config/job-search/config.json` and every path below would be read against the wrong
    file.
    """
    return {"HOME": str(home), "JOBSEARCH_OS_HOME": str(home),
            "XDG_CONFIG_HOME": "", "JOBSEARCH_OS_REGISTRY": ""}


def registry_path(home):
    """Where `discovery_env` puts the registry file."""
    return home / ".config" / "job-search" / "config.json"


def named_line(reg, workspace):
    """The line for a registry that holds a non-empty `active_workspace`."""
    return ("workspace-discovery.sh: registry %s names active_workspace %s — found by grep, which "
            "does not check that the file is JSON, so parse-check the file yourself\n"
            % (reg, workspace))


def unnamed_line(reg):
    """The line for a registry file that exists and yields no workspace.

    One line for three states, because the `grep` reaches all three the same way: a registry holding
    an empty `active_workspace`, one whose `active_workspace` is not a string, and a registry that is
    not JSON at all. The line reports what the `grep` established rather than naming one of the
    three, which is the most this script can say without parsing the file.
    """
    return ('workspace-discovery.sh: registry %s holds no non-empty "active_workspace" string — '
            "grep does not check that the file is JSON, so parse-check the file yourself\n" % reg)


def no_registry_line(reg):
    """The line for a path holding no registry file. This is the one state a caller no longer has to
    establish for itself: with no file there, there is nothing to parse-check."""
    return "workspace-discovery.sh: no registry file at %s — nothing to parse-check\n" % reg


def keys(workspace, source, first_run):
    """The three `key=value` lines this script prints, in the order it prints them."""
    return "workspace=%s\nsource=%s\nfirst_run=%s\n" % (workspace, source, first_run)


@pytest.mark.parametrize("shell", SHELLS)
def test_discovery_says_which_of_the_four_registry_states_it_found(tmp_path, shell):
    """`source=none` covers four states — no registry file, a registry holding an empty
    `active_workspace`, one whose `active_workspace` is not a string, and a registry that is not JSON
    — and `skills/job-search-runbook/SKILL.md` requires the caller to stop the run on the last: "A
    registry file that exists but does not parse as JSON stops the run." Measured 2026-08-11 with one
    HOME and the registry file rewritten between calls: all four print the same three keys and exit
    0, so stdout says nothing about which one happened.

    The script does not parse JSON, so the last three states share one line. That line says the file
    holds no non-empty `active_workspace` string, which is what the `grep` established and is true of
    all three; `{"active_workspace": 42}` is the state that makes "names no active_workspace" false,
    because the key is there and the file is JSON. What the caller gets that it did not have is
    whether there is a file at that path at all.
    """
    home = tmp_path / "h"
    (home / ".job-search").mkdir(parents=True)
    reg = registry_path(home)
    reg.parent.mkdir(parents=True)
    env = discovery_env(home)
    # `.job-search` exists with no `config.yaml` in it, so all four calls fall through to the
    # first-run path and print the same three keys.
    three_keys = keys(home / ".job-search", "none", "true")

    missing = run_script(DISCOVERY, shell=shell, env=env)
    assert missing.returncode == 0, missing.stdout + missing.stderr
    assert missing.stderr == no_registry_line(reg), missing.stderr
    assert missing.stdout == three_keys, missing.stdout

    reg.write_text('{"active_workspace": ""}', encoding="utf-8")
    empty = run_script(DISCOVERY, shell=shell, env=env)
    assert empty.returncode == 0, empty.stdout + empty.stderr
    assert empty.stderr == unnamed_line(reg), empty.stderr
    assert empty.stdout == three_keys, empty.stdout

    reg.write_text("this is not json", encoding="utf-8")
    unparsed = run_script(DISCOVERY, shell=shell, env=env)
    assert unparsed.returncode == 0, unparsed.stdout + unparsed.stderr
    assert unparsed.stderr == unnamed_line(reg), unparsed.stderr
    assert unparsed.stdout == three_keys, unparsed.stdout

    reg.write_text('{"active_workspace": 42}', encoding="utf-8")
    number = run_script(DISCOVERY, shell=shell, env=env)
    assert number.returncode == 0, number.stdout + number.stderr
    assert number.stderr == unnamed_line(reg), number.stderr
    assert number.stdout == three_keys, number.stdout
    # The line has to hold for this state as well as for the other two, so it says what the `grep`
    # found rather than that the registry names no workspace.
    assert "names no active_workspace" not in number.stderr, number.stderr

    # stdout is byte-identical across all four, which is why the stderr line is needed. The call
    # with no file there is separated from the other three; those three share a line.
    assert missing.stdout == empty.stdout == unparsed.stdout == number.stdout
    assert missing.stderr != empty.stderr
    assert empty.stderr == unparsed.stderr == number.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_discovery_names_the_workspace_the_registry_chose(tmp_path, shell):
    """The registry wins over both config paths and over the first-run path, so the workspace it
    names is the one the whole run works in. The line says which path that is, and says the value
    came from a `grep` over an unparsed file."""
    home = tmp_path / "h"
    ws = tmp_path / "chosen"
    ws.mkdir(parents=True)
    (ws / "config.yaml").write_text("version: 1\n", encoding="utf-8")
    reg = registry_path(home)
    reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"active_workspace": str(ws)}), encoding="utf-8")
    r = run_script(DISCOVERY, shell=shell, env=discovery_env(home))
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stderr == named_line(reg, ws), r.stderr
    assert r.stdout == keys(ws, "registry", "false"), r.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_the_other_precedence_paths_print_the_three_keys_they_printed_before(tmp_path, shell):
    """The script's header lists four paths that reach `emit`. The one above is the registry with a
    `config.yaml` at the workspace it names; here are the other three, plus the registry path's
    other branch — a registry naming a workspace that has no `config.yaml`, which prints
    `source=registry first_run=true`.

    Each stdout is pinned as the whole block rather than as a count of lines or one key: all three
    keys are here in their printed order, so a renamed key, a reordered pair or a changed value fails
    this comparison.
    """
    default_home = tmp_path / "default"
    (default_home / ".job-search").mkdir(parents=True)
    (default_home / ".job-search" / "config.yaml").write_text("version: 1\n", encoding="utf-8")
    d = run_script(DISCOVERY, shell=shell, env=discovery_env(default_home))
    assert d.returncode == 0, d.stdout + d.stderr
    assert d.stdout == keys(default_home / ".job-search", "default", "false"), d.stdout
    assert d.stderr == no_registry_line(registry_path(default_home)), d.stderr

    legacy_home = tmp_path / "legacy"
    (legacy_home / "job-search").mkdir(parents=True)
    (legacy_home / "job-search" / "config.yaml").write_text("version: 1\n", encoding="utf-8")
    leg = run_script(DISCOVERY, shell=shell, env=discovery_env(legacy_home))
    assert leg.returncode == 0, leg.stdout + leg.stderr
    assert leg.stdout == keys(legacy_home / "job-search", "legacy", "false"), leg.stdout
    assert leg.stderr == no_registry_line(registry_path(legacy_home)), leg.stderr

    first_home = tmp_path / "first"
    first_home.mkdir()
    f = run_script(DISCOVERY, shell=shell, env=discovery_env(first_home))
    assert f.returncode == 0, f.stdout + f.stderr
    assert f.stdout == keys(first_home / ".job-search", "none", "true"), f.stdout
    assert f.stderr == no_registry_line(registry_path(first_home)), f.stderr

    fresh_home = tmp_path / "fresh"
    fresh_ws = tmp_path / "named-but-not-created"
    fresh_reg = registry_path(fresh_home)
    fresh_reg.parent.mkdir(parents=True)
    fresh_reg.write_text(json.dumps({"active_workspace": str(fresh_ws)}), encoding="utf-8")
    n = run_script(DISCOVERY, shell=shell, env=discovery_env(fresh_home))
    assert n.returncode == 0, n.stdout + n.stderr
    assert n.stdout == keys(fresh_ws, "registry", "true"), n.stdout
    assert n.stderr == named_line(fresh_reg, fresh_ws), n.stderr


# ------------------------------------------------------------------ validate-workspace.sh

def run_validator(workspace, *args, shell="sh"):
    """`validate-workspace.sh` over one workspace, through POSIX `sh` unless a shell is named.

    A thin wrapper over `run_script` rather than an import from `tests/test_validate_workspace.py`,
    so this file collects on its own.
    """
    return run_script(VALIDATOR, workspace, *args, shell=shell)


def clean_line(workspace, run_id=None):
    """The line this script writes when it finds nothing wrong, run id and all."""
    if run_id is None:
        return "validate-workspace.sh: checked %s — no broken rule found\n" % workspace
    return ("validate-workspace.sh: checked %s and run %s — no broken rule found\n"
            % (workspace, run_id))


def write_clean_run(workspace, run_id=RID):
    """A run record `--post-close` finds nothing wrong with, written into `runs/`.

    The counts hold to the three sums this script checks with no log to compare against: the three
    bands plus `filtered_out` plus `duplicates_of_another` equal `postings_reviewed`,
    `postings_reviewed` plus `postings_unreviewed` equal `postings_surfaced`, and `by_source` sums
    to `postings_surfaced`. The `tmp_workspace` fixture writes no `jobs.jsonl`, so `run-counts.sh`
    prints nothing and the comparison against the log is skipped. `completed_at` is a past instant,
    so it stays no later than the mtime of the file written here.
    """
    record = {
        "run_id": run_id,
        "trigger": "manual",
        "close_state": "complete",
        "started_at": "2026-08-05T16:47:00Z",
        "completed_at": "2026-08-05T16:48:00Z",
        "postings_surfaced": 2,
        "postings_reviewed": 2,
        "postings_unreviewed": 0,
        "postings_detail_read": 1,
        "matches": {"strong": 1, "moderate": 0, "weak": 0},
        "filtered_out": 1,
        "duplicates_of_another": 0,
        "by_source": {"linkedin": 2},
    }
    path = workspace / "runs" / ("%s.json" % run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def test_a_clean_workspace_says_which_workspace_was_checked(tmp_workspace):
    """Two different valid workspaces both exit 0 with zero bytes on both streams, so silence does
    not say which one was read. Measured 2026-08-11 against the script as it stood before this line
    existed, on two workspaces built the way the `tmp_workspace` fixture builds one: both exited 0,
    both wrote 0 bytes to stdout and 0 bytes to stderr, and `cmp` reported both streams identical.

    That is the whole of what this line adds. A path that does not exist and a directory that is
    not a workspace were both already told apart, measured the same day: the first exits 2 with
    `validate-workspace.sh: no such workspace: <path>` and the second exits 1 with 69 bytes of
    findings on stdout.
    """
    r = run_validator(tmp_workspace)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert r.stderr == clean_line(tmp_workspace), r.stderr


def test_the_clean_line_names_the_run_when_post_close_is_given(tmp_workspace):
    """`--post-close` checks the run's record on top of the workspace's two files, so the line names
    the run as well. Without the run id a caller cannot tell a call that checked the record from one
    that checked only `config.yaml` and `preferences.md`."""
    write_clean_run(tmp_workspace)
    r = run_validator(tmp_workspace, "--post-close", RID)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert r.stderr == clean_line(tmp_workspace, RID), r.stderr


def test_quiet_when_clean_suppresses_only_that_line(tmp_workspace):
    """`open-run.sh` runs this script inside its own and already tells its caller the same thing
    through its exit status, and `tests/test_mechanics_scripts.py` requires `open-run.sh` to write
    exactly one line to stderr under a PATH with no digest command — the test there is
    `test_a_present_brief_with_no_way_to_digest_it_is_not_called_missing` — where a second line
    would be a `command not found` from something that PATH is missing. Redirecting the whole of
    this script's stderr at that call site would suppress this script's own failures along with the
    line, so the flag suppresses the line alone.

    This is the only flag in the pack that leaves a line out of a success path, which is why the
    guard at the end of this file has no entry for the branch it takes. Measured 2026-08-11 with
    `git grep -n -- "--quiet\\|--silent\\|QUIET\\|SILENT" skills/*/scripts/`: eight hits, and every
    one of them is this flag — `validate-workspace.sh:14,15,29,32,42,537`, which is the two header
    lines, the `QUIET_WHEN_CLEAN` variable, the usage line, the flag parse and the `if` that reads
    it, and `open-run.sh:127,130`, which is the one caller that passes it. The read of `open-run.sh`
    at the end ties the flag to that caller: take the flag off that call and this test fails,
    because no other call in the pack passes it.
    """
    r = run_validator(tmp_workspace, "--quiet-when-clean")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert r.stderr == "", r.stderr
    # A real failure of this script still reaches the caller with the flag set.
    missing = tmp_workspace.parent / "no-such-workspace"
    bad = run_validator(missing, "--quiet-when-clean")
    assert bad.returncode == 2, bad.stdout + bad.stderr
    assert bad.stdout == "", bad.stdout
    assert bad.stderr == "validate-workspace.sh: no such workspace: %s\n" % missing, bad.stderr

    open_run = (RUNBOOK_SCRIPTS / "open-run.sh").read_text(encoding="utf-8")
    assert "validate-workspace.sh\" \"$ws\" --quiet-when-clean" in open_run, open_run


def test_a_workspace_with_findings_still_writes_nothing_to_stderr(tmp_workspace):
    """The line is on the exit-0 path only, so it is not on this one. Two tests in
    `tests/test_validate_workspace.py` —
    `test_a_count_written_with_a_leading_zero_loses_no_finding` and
    `test_the_count_and_timestamp_checks_run_under_every_shell` — require stderr to be empty over a
    workspace this script found something wrong with, and a caller reading stderr for this script's
    own failures would read a findings line there as one."""
    (tmp_workspace / "config.yaml").write_text("version: 1\n", encoding="utf-8")
    r = run_validator(tmp_workspace)
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stderr == "", r.stderr
    assert r.stdout == ("INVALID config.yaml missing-key queries\n"
                        "INVALID config.yaml missing-key schedule\n"
                        "INVALID config.yaml missing-key search.sources\n"), r.stdout


# ------------------------------------------------------------------ dedup-surfaced.awk

def record_search(jobs, body, query_id="q", shell="sh"):
    """Run one search body through `record-api-response.sh`, the only caller of the awk program.

    `dedup-surfaced.awk` takes its input from that script and writes its rows back to it, so there
    is no way to drive it that also exercises the redirection the diagnostic has to stay out of.
    """
    return run_script(RECORD_API, RID, jobs, body, "--route", "search-jobs",
                      "--query-id", query_id, shell=shell)


def api_rows():
    """The 25 rows of the LinkedIn search fixture, in the order the response holds them."""
    return json.loads(SEARCH_FIXTURE.read_text(encoding="utf-8"))["data"]["results"]


def api_body(tmp_path, name, rows):
    """A search response carrying `rows`, built by swapping the results of the LinkedIn fixture, so
    every field the row builder reads is the one the live API sends."""
    body = json.loads(SEARCH_FIXTURE.read_text(encoding="utf-8"))
    body["data"]["results"] = rows
    path = tmp_path / name
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def judged_event(source_id, run_id="2026-08-01T00-00-00Z"):
    """An `evaluated` event from an earlier run. `dedup-surfaced.awk` skips a judged posting
    whatever run judged it, so the run id here is deliberately not this run's."""
    return ('{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"%s",'
            '"relevant":true,"match":"weak"}\n' % (run_id, source_id))


def surfaced_event(source_id, run_id=RID):
    return ('{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"%s"}\n'
            % (run_id, source_id))


def dedup_line(judged, already, repeated):
    """Every count names its unit, and the unit is rows rather than postings: a response repeating a
    posting the log already judged counts both of its rows under `already judged`, which
    `test_the_counts_are_rows_and_a_repeat_of_a_judged_posting_is_counted_as_judged` holds."""
    def rows(n):
        return "%d row%s" % (n, "" if n == 1 else "s")
    return ("dedup-surfaced: %s already judged, %s already surfaced by this run, "
            "%s repeated inside this response" % (rows(judged), rows(already), rows(repeated)))


def totals_line(appended, returned):
    return ("record-api-response.sh: %d rows appended, %d rows in the response"
            % (appended, returned))


def test_a_response_that_loses_no_row_says_so_with_three_zeros(tmp_path):
    """The line is written on every search, not only where something dropped. Without it, a run
    whose whole page was new and a run whose diagnostic went missing look the same to the caller."""
    jobs = tmp_path / "jobs.jsonl"
    r = record_search(jobs, SEARCH_FIXTURE, query_id="q1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert dedup_line(0, 0, 0) in r.stderr, r.stderr
    assert totals_line(25, 25) in r.stderr, r.stderr


def test_the_same_page_twice_in_one_run_is_reported_as_already_surfaced(tmp_path):
    """`0 rows appended, 25 rows in the response` says nothing about whether the 25 already carry a
    verdict or were surfaced by an earlier query of this same run. Those are different facts about
    the run, and this program is the only place either one is worked out."""
    jobs = tmp_path / "jobs.jsonl"
    first = record_search(jobs, SEARCH_FIXTURE, query_id="q1")
    assert first.returncode == 0, first.stdout + first.stderr
    second = record_search(jobs, SEARCH_FIXTURE, query_id="q2")
    assert second.returncode == 0, second.stdout + second.stderr
    assert dedup_line(0, 25, 0) in second.stderr, second.stderr
    assert totals_line(0, 25) in second.stderr, second.stderr


def test_a_posting_that_already_carries_a_verdict_is_reported_as_judged(tmp_path):
    """The judged check is not scoped to a run: a posting with a verdict from any run is not offered
    again. A caller that sees three rows go missing off a fresh log can tell from this line that the
    reason is three verdicts already in the log rather than a query it ran twice."""
    jobs = tmp_path / "jobs.jsonl"
    rows = api_rows()
    jobs.write_text("".join(judged_event(row["source_id"]) for row in rows[:3]), encoding="utf-8")
    r = record_search(jobs, api_body(tmp_path, "ten.json", rows[:10]), query_id="q1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert dedup_line(3, 0, 0) in r.stderr, r.stderr
    assert totals_line(7, 10) in r.stderr, r.stderr


def test_a_row_the_one_response_holds_twice_is_counted_apart_from_the_other_two(tmp_path):
    """A row repeated inside a single response is dropped by the same branch as the other two, and
    it is neither already judged nor already surfaced: no verdict in the log covers it, and no
    earlier search of this run returned it. A caller told only `10 rows appended, 12 rows in the
    response` would go looking in its log for two postings that were never there."""
    jobs = tmp_path / "jobs.jsonl"
    rows = api_rows()
    body = api_body(tmp_path, "twelve.json", rows[:10] + [rows[0], rows[3]])
    r = record_search(jobs, body, query_id="q1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert dedup_line(0, 0, 2) in r.stderr, r.stderr
    assert totals_line(10, 12) in r.stderr, r.stderr


def test_a_posting_this_run_surfaced_and_then_judged_is_reported_as_judged(tmp_path):
    """Both rules match this posting, and it is counted once. The label is the later of the two
    events in the log, and a run writes the verdict after the row it surfaced, so a posting it has
    since judged is reported as judged. Counting it under both would break the one property the
    three counts have: that they add up to the rows the response held minus the rows appended."""
    jobs = tmp_path / "jobs.jsonl"
    rows = api_rows()
    jobs.write_text(surfaced_event(rows[0]["source_id"])
                    + judged_event(rows[0]["source_id"], run_id=RID), encoding="utf-8")
    r = record_search(jobs, api_body(tmp_path, "one.json", rows[:1]), query_id="q1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert dedup_line(1, 0, 0) in r.stderr, r.stderr
    assert totals_line(0, 1) in r.stderr, r.stderr


def test_the_three_counts_account_for_every_row_that_was_not_appended(tmp_path):
    """One response holding a row of each kind, so the three counts are told apart rather than
    summed. Every row the program drops is dropped by the one branch these three count, so the three
    add up to the rows the response held minus the rows appended, and there is no fourth kind."""
    jobs = tmp_path / "jobs.jsonl"
    rows = api_rows()
    jobs.write_text(judged_event(rows[0]["source_id"]), encoding="utf-8")
    first = record_search(jobs, api_body(tmp_path, "three.json", rows[1:4]), query_id="q1")
    assert first.returncode == 0, first.stdout + first.stderr
    assert dedup_line(0, 0, 0) in first.stderr, first.stderr
    # rows[0] already carries a verdict, rows[1] was surfaced by the query above, rows[4] is here
    # twice, and rows[5] is new.
    body = api_body(tmp_path, "five.json", [rows[0], rows[1], rows[4], rows[4], rows[5]])
    second = record_search(jobs, body, query_id="q2")
    assert second.returncode == 0, second.stdout + second.stderr
    assert dedup_line(1, 1, 1) in second.stderr, second.stderr
    assert totals_line(2, 5) in second.stderr, second.stderr
    counts = re.search(r"dedup-surfaced: (\d+) rows? already judged, (\d+) rows? already surfaced "
                       r"by this run, (\d+) rows? repeated inside this response", second.stderr)
    totals = re.search(r"record-api-response\.sh: (\d+) rows appended, (\d+) rows in the response",
                       second.stderr)
    assert counts and totals, second.stderr
    appended, returned = int(totals.group(1)), int(totals.group(2))
    assert sum(int(g) for g in counts.groups()) == returned - appended, second.stderr


def test_the_counts_are_rows_and_a_repeat_of_a_judged_posting_is_counted_as_judged(tmp_path):
    """The three counts are rows, not postings, and the line says `row` or `rows` so a reader is not
    left to work out which. A response holding five rows over three postings that already carry a
    verdict — two of the three sent twice — counts all five under `already judged` and none under
    `repeated inside this response`, because the pair is in the set before either of a posting's
    rows is read. Without the unit on the line, `5 already judged` over a log holding three verdicts
    reads as a fourth and a fifth verdict nobody wrote.
    """
    jobs = tmp_path / "jobs.jsonl"
    rows = api_rows()
    three = rows[:3]
    jobs.write_text("".join(judged_event(row["source_id"]) for row in three), encoding="utf-8")
    body = api_body(tmp_path, "five.json", three + [rows[0], rows[1]])
    r = record_search(jobs, body, query_id="q1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert dedup_line(5, 0, 0) in r.stderr, r.stderr
    assert "5 rows already judged" in r.stderr, r.stderr
    assert totals_line(0, 5) in r.stderr, r.stderr

    # The singular at one, on the same three counts.
    single = tmp_path / "single.jsonl"
    single.write_text(judged_event(rows[0]["source_id"]), encoding="utf-8")
    one = record_search(single, api_body(tmp_path, "two.json", rows[:2]), query_id="q1")
    assert one.returncode == 0, one.stdout + one.stderr
    assert ("dedup-surfaced: 1 row already judged, 0 rows already surfaced by this run, "
            "0 rows repeated inside this response" in one.stderr), one.stderr


def test_the_diagnostic_stays_off_the_stdout_that_becomes_the_event_log(tmp_path):
    """`record-api-response.sh` runs the awk program with its stdout redirected to the file it then
    appends to `jobs.jsonl` — `grep -n 'dedup-surfaced.awk'
    skills/job-search-run/scripts/record-api-response.sh` finds the one invocation — so a line
    printed there becomes an event in the user's log rather than a diagnostic. Both passes are
    checked: the first prints three zeros and the second prints a count of 25, and the log holds the
    same 27 events either way."""
    jobs = tmp_path / "jobs.jsonl"
    rows = api_rows()
    first = record_search(jobs, SEARCH_FIXTURE, query_id="q1")
    assert first.returncode == 0, first.stdout + first.stderr
    assert first.stdout == "", first.stdout
    second = record_search(jobs, SEARCH_FIXTURE, query_id="q2")
    assert second.returncode == 0, second.stdout + second.stderr
    assert second.stdout == "", second.stdout
    assert "dedup-surfaced" not in jobs.read_text(encoding="utf-8"), jobs.read_text()
    events = lines(jobs)
    assert [e["event"] for e in events] == ["call"] + ["surfaced"] * 25 + ["call"]
    assert [e["source_id"] for e in events[1:26]] == [row["source_id"] for row in rows]
    assert [e["rows_new"] for e in (events[0], events[26])] == [25, 0]


# ------------------------------------------------------------------ event-log-append.sh

def test_appending_an_event_by_hand_says_whether_it_landed(tmp_path):
    """Appending an event and skipping a duplicate both gave exit 0 with zero bytes on both
    streams, so a caller that piped an event in could not tell the two apart.

    The skip is the `evaluated` path only — `grep -n 'evtype. = evaluated'
    skills/job-search-run/scripts/event-log-append.sh` finds the one branch that holds it — so this
    case is written with an `evaluated` event. The script writes nothing to stdout on either path,
    and the new line has to leave stdout empty, so that is checked too.
    """
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("", encoding="utf-8")
    ev = ('{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"9",'
          '"relevant":true,"match":"strong"}' % RID)

    first = run_append(jobs, ev)
    assert first.returncode == 0, first.stdout + first.stderr
    assert first.stdout == "", first.stdout
    assert "event-log-append: appended evaluated for linkedin:9" in first.stderr, first.stderr

    second = run_append(jobs, ev)
    assert second.returncode == 0, second.stdout + second.stderr
    assert second.stdout == "", second.stdout
    assert ("event-log-append: linkedin:9 already has this event — nothing written"
            in second.stderr), second.stderr
    assert "appended" not in second.stderr, second.stderr
    assert len(lines(jobs)) == 1, jobs.read_text()


def test_an_appended_event_is_named_by_its_own_type(tmp_path):
    """The type in the line is the one on the event, not the word `evaluated`. A `surfaced` event
    is also the one case where the same event twice is appended twice rather than skipped, because
    the skip branch runs only for `evaluated`. Measured 2026-08-11 on `git show
    64e7d06:skills/job-search-run/scripts/event-log-append.sh`: the same `surfaced` event piped in
    twice exited 0 both times and left two lines in the log.
    """
    jobs = tmp_path / "jobs.jsonl"
    ev = '{"event":"surfaced","run_id":"%s","source":"ashby","source_id":"abc-1"}' % RID

    first = run_append(jobs, ev)
    assert first.returncode == 0, first.stdout + first.stderr
    assert "event-log-append: appended surfaced for ashby:abc-1" in first.stderr, first.stderr

    second = run_append(jobs, ev)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "event-log-append: appended surfaced for ashby:abc-1" in second.stderr, second.stderr
    assert "nothing written" not in second.stderr, second.stderr
    assert len(lines(jobs)) == 2, jobs.read_text()


@pytest.mark.parametrize("shell", SHELLS)
def test_an_append_that_failed_says_nothing_about_appending(tmp_path, shell):
    """The append was the last command in the script, so the status the caller saw was its own. The
    status is now taken before the printf and given back after it, and this holds both halves of
    that: a failed append still exits non-zero, and it writes no line saying the event landed.

    The log here is under a path whose parent is a file, so `mkdir -p` cannot make the directory and
    the `>>` has nowhere to write. Measured 2026-08-11 against `git show
    64e7d06:skills/job-search-run/scripts/event-log-append.sh`, the version before this line was
    added, which gives the same status on the same input: 1 under `sh` and 2 under `dash`.
    """
    (tmp_path / "notadir").write_text("", encoding="utf-8")
    jobs = tmp_path / "notadir" / "jobs.jsonl"
    r = run_append(jobs, '{"event":"evaluated","source":"linkedin","source_id":"9"}', shell=shell)
    assert r.returncode != 0, r.stdout + r.stderr
    assert r.stdout == "", r.stdout
    assert "event-log-append: appended" not in r.stderr, r.stderr
    assert not jobs.exists()


def test_a_refused_event_still_says_only_what_it_refused(tmp_path):
    """The script refuses an event seven ways, and each writes one line and exits 1. Every refusal
    is written with `echo` and the two new lines with `printf`, so `grep -c "echo
    'event-log-append:" skills/job-search-run/scripts/event-log-append.sh` counts the refusals and
    returns 7. The two new lines are on the exit-0 paths, so a refusal still says nothing about an
    append. Nothing is written to the log either: the file the caller named is not created at all.
    """
    jobs = tmp_path / "jobs.jsonl"
    refusals = [
        ('{"event":"evaluated","source":"linkedin","source_id":"9"}\n'
         '{"event":"evaluated","source":"linkedin","source_id":"10"}',
         "event must be a single line"),
        ("", "empty event"),
        ('{"event":"evaluated","source":"linkedin","source_id":"9","source_id":"10"}',
         '"source_id" must appear exactly once'),
        ('{"event":"evaluated","source":"linkedin","source_id":""}',
         '"source_id" must be non-empty'),
        ('{"event":"evaluated","source":"linkedin","source":"ashby","source_id":"9"}',
         '"source" must appear at most once'),
        ('{"event":"evaluated","source":"linkedin","source_id":"9",'
         '"same_role_as":{"id":"ashby:1"}}',
         '"same_role_as" must be a flat string'),
        ('{"event":"evaluated","source_id":"9"}',
         'evaluated event needs a non-empty "source"'),
    ]
    for event, said in refusals:
        r = subprocess.run(["sh", str(APPEND), str(jobs)], input=event,
                           capture_output=True, text=True)
        assert r.returncode == 1, (event, r.stdout, r.stderr)
        assert r.stdout == "", (event, r.stdout)
        assert r.stderr == "event-log-append: %s\n" % said, (event, r.stderr)
        assert not jobs.exists(), jobs.read_text()


# --------------------------------------------------- one invocation per exit-0 branch of the ten

# One entry per exit-0 branch of the ten scripts: the prefix every line that branch writes opens
# with, and how many lines it writes to stderr.
#
# This is keyed on branches rather than on scripts because six of the ten scripts have more than one
# exit-0 branch, and a case per script runs one of those branches and never runs the others.
# Measured 2026-08-11: with a case per script, deleting the `printf` from `queue-detail-read.sh`'s
# already-queued branch left the guard 10 of 10 green, and the only test that went red was that
# script's own content test, which would go out of the suite with the line it reads.
#
# The line count is what makes a deletion visible on the one branch that writes two lines.
# `dedup.sh --near` prints a line per collapsed row and then a counts line, so with only "stderr is
# not empty" to go on, deleting either of them leaves the other and the case stays green.
#
# The prefixes are written out one branch at a time rather than worked out from the filename,
# because the pack does not work them out from the filename either. Measured 2026-08-11 with
# `python3 -c "import sys; sys.path.insert(0, 'tests'); import test_script_diagnostics as t; p =
# {v[0] for v in t.BRANCH_STDERR.values()}; print(len(t.BRANCH_STDERR), len(p), sum('.sh' in x for x
# in p))"`: 18 branches, 11 distinct prefixes, 7 of them carrying `.sh`.
#
# Two exit-0 branches of these scripts are missing from this map, because it holds only the branches
# that write a line. `validate-workspace.sh --quiet-when-clean` leaves its line out for its one
# caller, and `test_quiet_when_clean_suppresses_only_that_line` above is where that branch is
# checked. `dedup.sh <jobs.jsonl> <source>`, the two-argument mode, was never given a line at all:
# measured 2026-08-11, three candidate ids against a log holding one judgment printed two ids on
# stdout and exited 0 with 0 bytes on stderr.
BRANCH_STDERR = {
    "dedup.sh --near (a pair collapsed)":                       ("dedup.sh --near: ", 2),
    "dedup.sh --near (no pair collapsed)":                      ("dedup.sh --near: ", 1),
    "event-log-append.sh (appended)":                           ("event-log-append: ", 1),
    "event-log-append.sh (the event is already there)":         ("event-log-append: ", 1),
    "list-detail-read-queue.sh":                                ("list-detail-read-queue: ", 1),
    "posting-counts.sh":                                        ("posting-counts.sh: ", 1),
    "queue-detail-read.sh (queued)":                            ("queue-detail-read: ", 1),
    "queue-detail-read.sh (already queued)":                    ("queue-detail-read: ", 1),
    "record-judgment.sh (recorded)":                            ("record-judgment: ", 1),
    "record-judgment.sh (the verdict is already there)":        ("record-judgment: ", 1),
    "run-counts.sh":                                            ("run-counts.sh: ", 1),
    "run-matches.sh":                                           ("run-matches.sh: ", 1),
    "validate-workspace.sh (clean)":                            ("validate-workspace.sh: ", 1),
    "validate-workspace.sh (clean, --post-close)":              ("validate-workspace.sh: ", 1),
    "validate-workspace.sh (--help)":                           ("usage: validate-workspace.sh ", 1),
    "workspace-discovery.sh (the registry names a workspace)":  ("workspace-discovery.sh: ", 1),
    "workspace-discovery.sh (the registry names none)":         ("workspace-discovery.sh: ", 1),
    "workspace-discovery.sh (no registry file)":                ("workspace-discovery.sh: ", 1),
}


def success_calls(tmp_path, workspace):
    """One call per branch in `BRANCH_STDERR`, each on an input that reaches that branch at exit 0.

    Every input is built the way the tests above build the same script's input, through the same
    helpers and the same log constants, so the guard runs the success paths those tests already pin
    rather than a second set of its own. The branches a script reaches only on a second call — a
    posting queued twice, a verdict recorded twice, an event appended twice — run the first call
    here and hand back the second.

    `validate-workspace.sh` is called without `--quiet-when-clean` on both of its clean branches,
    because that flag leaves the line out; `test_quiet_when_clean_suppresses_only_that_line` above
    is where the flag is checked.

    Each value is a function rather than a finished `CompletedProcess`, so the fixture below can
    build all eighteen and run the one its parameter names.
    """
    def queue_detail_read():
        jobs = tmp_path / "queued.jsonl"
        jobs.write_text(surfaced_event("77"), encoding="utf-8")
        return run_script(QUEUE, jobs, "--run-id", RID, "--source", "linkedin", "--source-id", "77")

    def queue_detail_read_already_queued():
        # The same posting offered twice. The first call appends the queued event, the second finds
        # it, writes its own line and exits 0 without appending a second one — a second event would
        # put the posting on the read list twice.
        jobs = tmp_path / "queued-twice.jsonl"
        jobs.write_text(surfaced_event("78"), encoding="utf-8")
        args = (jobs, "--run-id", RID, "--source", "linkedin", "--source-id", "78")
        first = run_script(QUEUE, *args)
        assert first.returncode == 0, ("the first queue call should exit 0\n"
                                       + first.stdout + first.stderr)
        return run_script(QUEUE, *args)

    def record_judgment():
        jobs = tmp_path / "judged.jsonl"
        jobs.write_text(
            '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"77",'
            '"title":"Analyst","company_name":"Acme"}\n' % RID, encoding="utf-8")
        return run_script(JUDGE, jobs, "--run-id", RID, "--source", "linkedin", "--source-id", "77",
                          "--detail-read", "true", "--relevant", "true", "--match", "moderate",
                          "--reasoning", "fits the brief")

    def record_judgment_already_recorded():
        # The same verdict recorded twice. The script drops the timestamp from both lines before
        # comparing them, so the second call reaches the branch that finds this exact verdict
        # already in the log even when the two calls land in different seconds.
        jobs = tmp_path / "judged-twice.jsonl"
        jobs.write_text(
            '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"78",'
            '"title":"Analyst","company_name":"Acme"}\n' % RID, encoding="utf-8")
        args = (jobs, "--run-id", RID, "--source", "linkedin", "--source-id", "78",
                "--detail-read", "true", "--relevant", "true", "--match", "moderate",
                "--reasoning", "fits the brief")
        first = run_script(JUDGE, *args)
        assert first.returncode == 0, ("the first record call should exit 0\n"
                                       + first.stdout + first.stderr)
        return run_script(JUDGE, *args)

    def list_detail_read_queue():
        # Two postings queued and one of them judged, which is the log
        # `test_the_read_queue_says_how_much_of_it_is_worked_off` reads: one row on stdout, and
        # none of the three counts on the stderr line is zero.
        jobs = tmp_path / "read-queue.jsonl"
        jobs.write_text("".join([
            '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"1",'
            '"posting_id_at_seen":"jp_1","source_url":"https://example.test/1",'
            '"title":"Analyst","company_name":"Acme"}\n' % RID,
            '{"event":"surfaced","run_id":"%s","source":"linkedin","source_id":"2",'
            '"posting_id_at_seen":"jp_2","source_url":"https://example.test/2",'
            '"title":"Engineer","company_name":"Beta"}\n' % RID,
            '{"event":"queued","run_id":"%s","source":"linkedin","source_id":"1"}\n' % RID,
            '{"event":"queued","run_id":"%s","source":"linkedin","source_id":"2"}\n' % RID,
            '{"event":"evaluated","run_id":"%s","source":"linkedin","source_id":"1",'
            '"relevant":"false"}\n' % RID,
        ]), encoding="utf-8")
        return run_script(LIST_QUEUE, jobs, RID)

    def event_log_append():
        jobs = tmp_path / "appended.jsonl"
        return run_append(jobs, '{"event":"surfaced","run_id":"%s","source":"ashby",'
                                '"source_id":"abc-1"}' % RID)

    def event_log_append_already_there():
        # The same event offered twice. The skip is on `evaluated` events only — a posting is
        # recorded as `surfaced` before it is judged, and skipping on that first event would drop
        # the judgment — so this is an evaluated event, not the surfaced one above.
        jobs = tmp_path / "appended-twice.jsonl"
        event = ('{"event":"evaluated","run_id":"%s","source":"ashby","source_id":"abc-2",'
                 '"relevant":"true","match":"strong"}' % RID)
        first = run_append(jobs, event)
        assert first.returncode == 0, ("the first append should exit 0\n"
                                       + first.stdout + first.stderr)
        return run_append(jobs, event)

    def dedup_near_collapsing():
        # Two rows of the same opening: the second is collapsed into the first, so this call writes
        # the pairing line and then the counts line.
        return run_near([("linkedin:aa1", "Acme", "Software Engineer (Remote)"),
                         ("linkedin:aa2", "Acme", "Software Engineer (NYC)")])

    def dedup_near_collapsing_nothing():
        # Two different openings, so no pairing line is written and the counts line is the whole of
        # stderr. This is the branch that says a call which collapsed nothing still speaks.
        return run_near([("linkedin:aa1", "Acme", "Software Engineer"),
                         ("linkedin:bb2", "Beta", "Data Analyst")])

    def run_counts():
        jobs = tmp_path / "counted.jsonl"
        jobs.write_text(WORKED_LOG, encoding="utf-8")
        return run_script(COUNTS, jobs, RID)

    def run_matches():
        jobs = tmp_path / "matched.jsonl"
        jobs.write_text(FOUR_BAND_LOG, encoding="utf-8")
        return run_script(MATCHES, jobs, RID)

    def posting_counts():
        jobs = tmp_path / "postings.jsonl"
        jobs.write_text(JUDGED_LOG, encoding="utf-8")
        return run_script(POSTINGS, jobs)

    def workspace_discovery_no_registry():
        # The default path: a `.job-search` holding a `config.yaml` and no registry file, which is
        # one of the four calls in
        # `test_the_other_precedence_paths_print_the_three_keys_they_printed_before`.
        home = tmp_path / "discovery-home"
        (home / ".job-search").mkdir(parents=True)
        (home / ".job-search" / "config.yaml").write_text("version: 1\n", encoding="utf-8")
        return run_script(DISCOVERY, env=discovery_env(home))

    def workspace_discovery_registry_names_a_workspace():
        # A registry naming a workspace that holds a config.yaml, which is the call in
        # `test_discovery_names_the_workspace_the_registry_chose`. This branch exits 0 at the
        # registry step and never reaches the two config checks below it.
        home = tmp_path / "discovery-registry-home"
        ws = tmp_path / "discovery-chosen"
        ws.mkdir(parents=True)
        (ws / "config.yaml").write_text("version: 1\n", encoding="utf-8")
        reg = registry_path(home)
        reg.parent.mkdir(parents=True)
        reg.write_text(json.dumps({"active_workspace": str(ws)}), encoding="utf-8")
        return run_script(DISCOVERY, env=discovery_env(home))

    def workspace_discovery_registry_names_none():
        # A registry file holding an empty `active_workspace`, which is one of the three states
        # that share a line in `test_discovery_says_which_of_the_four_registry_states_it_found`.
        # This branch writes its line and falls through to the default config below, so the call
        # exits 0 there.
        home = tmp_path / "discovery-unnamed-home"
        (home / ".job-search").mkdir(parents=True)
        (home / ".job-search" / "config.yaml").write_text("version: 1\n", encoding="utf-8")
        reg = registry_path(home)
        reg.parent.mkdir(parents=True)
        reg.write_text('{"active_workspace": ""}', encoding="utf-8")
        return run_script(DISCOVERY, env=discovery_env(home))

    def validate_workspace():
        return run_validator(workspace)

    def validate_workspace_post_close():
        # `--post-close` checks the run's record on top of the workspace's two files and says so on
        # its own line, which is the call in
        # `test_the_clean_line_names_the_run_when_post_close_is_given`.
        write_clean_run(workspace)
        return run_validator(workspace, "--post-close", RID)

    def validate_workspace_help():
        # The one branch here that predates the 2026-08-11 plan: `-h` and `--help` print the usage
        # line and exit 0. Measured 2026-08-11, `sh validate-workspace.sh --help` exited 0 with 0
        # bytes on stdout and the usage line on stderr. This case is the only test that runs the
        # branch: measured 2026-08-11 with `git grep -n -- '--help' tests/`, every hit is in this
        # file. Its line opens with `usage: ` rather than with the bare script name, which is why
        # `BRANCH_STDERR` carries a prefix per branch rather than one per script.
        return run_script(VALIDATOR, "--help")

    calls = {
        "dedup.sh --near (a pair collapsed)": dedup_near_collapsing,
        "dedup.sh --near (no pair collapsed)": dedup_near_collapsing_nothing,
        "event-log-append.sh (appended)": event_log_append,
        "event-log-append.sh (the event is already there)": event_log_append_already_there,
        "list-detail-read-queue.sh": list_detail_read_queue,
        "posting-counts.sh": posting_counts,
        "queue-detail-read.sh (queued)": queue_detail_read,
        "queue-detail-read.sh (already queued)": queue_detail_read_already_queued,
        "record-judgment.sh (recorded)": record_judgment,
        "record-judgment.sh (the verdict is already there)": record_judgment_already_recorded,
        "run-counts.sh": run_counts,
        "run-matches.sh": run_matches,
        "validate-workspace.sh (clean)": validate_workspace,
        "validate-workspace.sh (clean, --post-close)": validate_workspace_post_close,
        "validate-workspace.sh (--help)": validate_workspace_help,
        "workspace-discovery.sh (the registry names a workspace)":
            workspace_discovery_registry_names_a_workspace,
        "workspace-discovery.sh (the registry names none)": workspace_discovery_registry_names_none,
        "workspace-discovery.sh (no registry file)": workspace_discovery_no_registry,
    }
    # The fixture takes its parameters from `BRANCH_STDERR`, so a branch listed here and not there
    # would be built and never run. This assertion fails instead.
    assert sorted(calls) == sorted(BRANCH_STDERR), (sorted(calls), sorted(BRANCH_STDERR))
    return calls


@pytest.fixture(params=sorted(BRANCH_STDERR))
def success_branch(request, tmp_path, tmp_workspace):
    """One exit-0 branch per parameter, as `(label, call)`, where `call()` reaches that branch.
    `tmp_workspace` is requested for the three `validate-workspace.sh` branches; the rest build what
    they need under `tmp_path`."""
    return request.param, success_calls(tmp_path, tmp_workspace)[request.param]


def test_every_exit_0_branch_of_the_instrumented_scripts_still_writes_a_line(success_branch):
    """One invocation per exit-0 branch, reading whether the branch wrote to stderr rather than what
    it wrote.

    Every test above pins one branch's exact sentence, and deleting that sentence from the script
    turns the test that reads it red — that case is already covered. The case that is not is an edit
    that drops a feature and takes both with it: the line goes out of the script and the test
    written for it goes out of the suite, and every test left passes over a script that has stopped
    saying what it did. This is the test that fails then, because it is parametrised over
    `BRANCH_STDERR` rather than written next to any one line, so taking a line out of a script
    without taking its entry out of that map leaves a case with nothing to read.

    No wording is read here, so a rewording leaves this green while the content test above goes red.

    The exit status is checked first and in the same test, because a call that failed would satisfy
    the stderr check for the wrong reason: nine of these ten scripts already wrote to stderr when
    they refuse an argument or cannot find the file they were handed, before the 2026-08-11 TD-008
    plan added a line to any of them. Measured 2026-08-11 with `git show 4fb0672:<path> | grep -c
    '>&2'` over the ten, where 4fb0672 is the commit before the plan's first: the nine counts run
    from 1 to 7, and `workspace-discovery.sh` counts 0.
    """
    label, call = success_branch
    prefix, expected = BRANCH_STDERR[label]
    r = call()
    assert r.returncode == 0, "%s: this is meant to be a success call, and it exited %d\n%s" % (
        label, r.returncode, r.stdout + r.stderr)

    written = [line for line in r.stderr.splitlines() if line.strip() != ""]
    assert written != [], (
        "%s exited 0 and wrote nothing to stderr. A caller reading that cannot tell it from a "
        "script that never ran, and re-running to find out is what TD-008 measured: 4 bash calls "
        "and 31 seconds on dedup.sh --near in the 2026-08-10 run." % label)
    assert len(written) == expected, (
        "%s writes %d line(s) to stderr and this call wrote %d. Either one of its lines was "
        "deleted, or a line was added and BRANCH_STDERR still holds the old count.\n%s"
        % (label, expected, len(written), r.stderr))
    for line in written:
        assert line.startswith(prefix), (
            "%s: every line this branch writes should open with %r, so a caller reading a stderr "
            "stream that several scripts wrote to can tell which one wrote the line; got %r"
            % (label, prefix, line[:80]))
