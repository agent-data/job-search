# tests/test_state.py
import json, subprocess, sys, pathlib
SCRIPT = str(pathlib.Path(__file__).resolve().parent.parent / "scripts" / "state.py")

def run(args, **kw):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, **kw)

def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))

def test_known_ids_missing_file_is_empty(tmp_path):
    r = run(["known-ids", "--jobs", str(tmp_path / "nope.jsonl")])
    assert r.returncode == 0
    assert r.stdout.strip() == ""

def test_known_ids_dedupes_and_skips_null(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    write_jsonl(jobs, [
        {"event": "evaluated", "source_id": "111"},
        {"event": "evaluated", "source_id": "111"},   # duplicate
        {"event": "evaluated", "source_id": "222"},
        {"event": "evaluated", "source_id": None},     # null -> skipped
        {"event": "status_changed", "source_id": "222", "status": "interested"},
    ])
    r = run(["known-ids", "--jobs", str(jobs)])
    assert r.returncode == 0
    assert r.stdout.split() == ["111", "222"]

def test_append_creates_and_appends(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    ev = {"event": "evaluated", "source_id": "333", "title": "X"}
    r = run(["append", "--jobs", str(jobs), "--event", json.dumps(ev)])
    assert r.returncode == 0
    lines = jobs.read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["source_id"] == "333"
    # second append adds a line, does not overwrite
    run(["append", "--jobs", str(jobs), "--event", json.dumps({"event": "status_changed", "source_id": "333", "status": "applied"})])
    assert len(jobs.read_text().splitlines()) == 2

def test_append_rejects_missing_source_id(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    r = run(["append", "--jobs", str(jobs), "--event", json.dumps({"event": "evaluated"})])
    assert r.returncode != 0
    assert "source_id" in (r.stderr + r.stdout)
    assert not jobs.exists()  # nothing written on rejection

def test_fold_last_write_wins_preserves_fields(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    write_jsonl(jobs, [
        {"event": "evaluated", "source_id": "444", "title": "Eng", "status": "new", "match": "weak"},
        {"event": "status_changed", "source_id": "444", "status": "interested"},  # overrides status only
    ])
    r = run(["fold", "--jobs", str(jobs)])
    assert r.returncode == 0
    state = json.loads(r.stdout)
    assert len(state) == 1
    rec = state[0]
    assert rec["status"] == "interested"   # last write wins
    assert rec["title"] == "Eng"            # untouched field preserved
    assert rec["match"] == "weak"

def test_fold_empty_is_empty_array(tmp_path):
    r = run(["fold", "--jobs", str(tmp_path / "nope.jsonl")])
    assert r.returncode == 0
    assert json.loads(r.stdout) == []

def test_append_preserves_existing_file(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    write_jsonl(jobs, [{"source_id": "prior", "title": "Pre-existing"}])
    r = run(["append", "--jobs", str(jobs), "--event", json.dumps({"source_id": "new"})])
    assert r.returncode == 0
    lines = jobs.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["source_id"] == "prior"
    assert json.loads(lines[1])["source_id"] == "new"

def test_fold_preserves_first_seen_order(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    write_jsonl(jobs, [
        {"event": "evaluated", "source_id": "444", "title": "First"},
        {"event": "evaluated", "source_id": "555", "title": "Second"},
        {"event": "status_changed", "source_id": "444", "status": "interested"},
    ])
    r = run(["fold", "--jobs", str(jobs)])
    assert r.returncode == 0
    assert [rec["source_id"] for rec in json.loads(r.stdout)] == ["444", "555"]

def test_malformed_line_is_clean_error_not_traceback(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text('{"source_id": "1", "title": "ok"}\nthis is not json\n')
    r = run(["fold", "--jobs", str(jobs)])
    assert r.returncode == 1
    assert "Traceback" not in r.stderr             # no raw Python traceback
    assert "malformed JSON at line 2" in r.stderr  # names the bad line

def test_non_ascii_roundtrips_unescaped(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    r = run(["append", "--jobs", str(jobs), "--event",
             json.dumps({"source_id": "9", "company_name": "Müller & Söhne"})])
    assert r.returncode == 0
    raw = jobs.read_text()
    assert "Müller & Söhne" in raw  # stored unescaped (ensure_ascii=False)
    assert json.loads(raw.splitlines()[0])["company_name"] == "Müller & Söhne"
