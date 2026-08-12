"""Unit tests for dedup.sh's --near mode: the same-opening guard.

A company that posts one opening in several locations shows up as several search rows with
different source_ids and titles that differ only by a location parenthetical. Reading each of
them bills a detail call for a posting already read (3 such billed reads across the 2026-07-30
evals). `dedup.sh --near` collapses those rows within one run: candidate rows arrive on stdin as
`<source>:<source_id><TAB>company<TAB>title`, and the ids of the openings to judge come back on
stdout — the first row of each same-company, same-normalized-title group.

`--near` reads column 1 as an opaque id: it prints the column back as written and never splits it
on the colon. So the rows below carry a bare id where a run carries the `<source>:<source_id>`
form, and every assertion reads the same either way.

Driven through POSIX `sh` (and strict `dash` where present), like every other bundled script.
"""
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEDUP = ROOT / "skills" / "job-search-run" / "scripts" / "dedup.sh"

SHELLS = ["sh"] + (["dash"] if shutil.which("dash") else [])


def run_near(rows, shell="sh"):
    """Run `dedup.sh --near` with `rows` (list of (id, company, title)) on stdin."""
    stdin = "".join("%s\t%s\t%s\n" % row for row in rows)
    return subprocess.run([shell, str(DEDUP), "--near"], input=stdin,
                          capture_output=True, text=True)


@pytest.mark.parametrize("shell", SHELLS)
def test_near_collapses_one_opening_posted_in_two_locations(shell):
    """The RED case: same company, titles equal once the location parenthetical is stripped,
    different source_ids -> the second row is a duplicate and does not reach a detail read."""
    r = run_near([("aa1", "Acme", "Software Engineer (Remote)"),
                  ("bb2", "Acme", "Software Engineer (New York, NY)")], shell)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["aa1"], r.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_near_keeps_different_openings_at_one_company(shell):
    """Two genuinely different roles at one company both stay — this guard never merges roles."""
    r = run_near([("aa1", "Acme", "Software Engineer (Remote)"),
                  ("bb2", "Acme", "Data Engineer (Remote)")], shell)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["aa1", "bb2"], r.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_near_keeps_the_same_title_at_two_companies(shell):
    """One title is common across employers; only same-company rows can be the same opening."""
    r = run_near([("aa1", "Acme", "Software Engineer"),
                  ("bb2", "Globex", "Software Engineer")], shell)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["aa1", "bb2"], r.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_near_ignores_case_and_spacing_differences(shell):
    """Boards write one opening's company and title with different casing and spacing."""
    r = run_near([("aa1", "Acme", "Senior  Software Engineer (Remote)"),
                  ("bb2", "ACME", "senior software engineer (Austin, TX)")], shell)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["aa1"], r.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_near_collapses_three_locations_of_one_opening_to_the_first(shell):
    r = run_near([("aa1", "Acme", "Platform Engineer (Remote - US)"),
                  ("bb2", "Acme", "Platform Engineer (Boston)"),
                  ("cc3", "Acme", "Platform Engineer (Denver)"),
                  ("dd4", "Globex", "Platform Engineer (Denver)")], shell)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["aa1", "dd4"], r.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_near_keeps_a_row_whose_company_or_title_is_missing(shell):
    """A row with nothing to compare is kept: dropping it would lose an unjudged opening."""
    stdin = "aa1\t\tSoftware Engineer\nbb2\tAcme\t\ncc3\ndd4\tAcme\tSoftware Engineer\n"
    r = subprocess.run(["sh", str(DEDUP), "--near"], input=stdin, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["aa1", "bb2", "cc3", "dd4"], r.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_near_skips_blank_lines_and_repeats_of_one_source_id(shell):
    stdin = "\naa1\tAcme\tSoftware Engineer\n\naa1\tAcme\tSoftware Engineer\n"
    r = subprocess.run([shell, str(DEDUP), "--near"], input=stdin, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["aa1"], r.stdout


def test_near_rejects_extra_arguments():
    """`--near` reads rows on stdin and takes no other argument; a stray one is a usage error."""
    r = subprocess.run(["sh", str(DEDUP), "--near", "jobs.jsonl"], input="",
                       capture_output=True, text=True)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "usage" in (r.stdout + r.stderr).lower()


def test_known_id_mode_still_works(tmp_path):
    """The two-argument known-ids mode is unchanged by the new mode."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text('{"event":"evaluated","source":"linkedin","source_id":"a"}\n')
    r = subprocess.run(["sh", str(DEDUP), str(jobs), "linkedin"], input="a\nb\n",
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["b"], r.stdout
