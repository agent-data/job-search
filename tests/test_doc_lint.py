import subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "doc_lint.py"

def run_lint(target, *extra):
    return subprocess.run([sys.executable, str(LINT), "--root", str(target), *extra],
                          capture_output=True, text=True)

def test_lint_runs(tmp_path):
    # an empty tree has no KB to violate — linter exits clean
    r = run_lint(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "clean" in r.stdout.lower()

def test_kb_is_clean():
    # the real repo's knowledge base must always pass the linter
    r = run_lint(ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
