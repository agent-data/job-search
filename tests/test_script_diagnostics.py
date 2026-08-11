"""Tests for the stderr diagnostics the agent-invoked scripts write about what they did.

The scripts in the `scripts/` directories are run by an agent, not by a person watching a terminal,
so an agent needs a line it can read to confirm what a call did. Each script this file covers wrote
nothing to stderr on the path that succeeds, which left the agent with the exit status and whatever
that path puts on stdout. Each test here runs one script and checks the sentence it wrote to stderr
and the exit status it gave back. `queue-detail-read.sh` and `record-judgment.sh` both append to the
log file and write nothing to stdout, so the new stderr line has to leave stdout empty, and that is
checked too. `dedup.sh --near` does write to stdout, so its tests check that every id that used to
come back still does, in the same order. `list-detail-read-queue.sh` writes the read list to stdout,
so its tests check that the rows that used to come back still do.

The `dedup.sh --near` tests run through POSIX `sh` and through `dash` where it is installed, the way
`tests/test_dedup_guard.py` drives that same script. Helpers are defined here rather than imported
from `tests/test_mechanics_scripts.py` or `tests/test_dedup_guard.py`, so this file collects on its
own.
"""
import json
import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN_SCRIPTS = ROOT / "skills" / "job-search-run" / "scripts"
QUEUE = RUN_SCRIPTS / "queue-detail-read.sh"
JUDGE = RUN_SCRIPTS / "record-judgment.sh"
DEDUP = RUN_SCRIPTS / "dedup.sh"
LIST_QUEUE = RUN_SCRIPTS / "list-detail-read-queue.sh"

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
    """No rows is the ordinary case at the end of a run and also what a mistyped run id gives, and
    from outside the two were the same: nothing on stdout, nothing on stderr, exit 0."""
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
