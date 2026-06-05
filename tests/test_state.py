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

# append to tests/test_state.py

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

# append to tests/test_state.py

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
