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
