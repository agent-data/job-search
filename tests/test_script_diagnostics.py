"""Tests for the stderr diagnostics the agent-invoked scripts write about what they did.

The scripts in the `scripts/` directories are run by an agent, not by a person watching a terminal,
so an agent needs a line it can read to confirm what a call did. Each script this file covers used
to write nothing on either stream on the path that does the write, which left the agent with only
the exit status. Each test here runs one script through `sh` and checks the sentence it wrote to
stderr and the exit status it gave back. `queue-detail-read.sh` and `record-judgment.sh` both append
to the log file and write nothing to stdout, so the new stderr line has to leave stdout empty, and
that is checked too.

Helpers are defined here rather than imported from `tests/test_mechanics_scripts.py`, so this file
collects on its own.
"""
import json
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN_SCRIPTS = ROOT / "skills" / "job-search-run" / "scripts"
QUEUE = RUN_SCRIPTS / "queue-detail-read.sh"
JUDGE = RUN_SCRIPTS / "record-judgment.sh"

RID = "2026-08-05T16-47-00Z"


def run_script(script, *args, shell="sh", env=None):
    """Run one mechanics script through POSIX `sh` (portable; not bash) and capture both streams."""
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([shell, str(script), *[str(a) for a in args]],
                          capture_output=True, text=True, env=e)


def lines(path):
    """The events in a jobs.jsonl, parsed, skipping blank lines."""
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


# ------------------------------------------------------------------ queue-detail-read.sh

def test_queueing_a_posting_says_it_queued_it(tmp_path):
    """The write is announced, the way the already-queued branch announces the write it did not
    make. Without this line a queued posting and one queued twice both give nothing on stdout,
    nothing on stderr and exit 0, so the caller cannot tell them apart."""
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
