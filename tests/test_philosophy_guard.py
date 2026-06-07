import subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "philosophy_guard.py"

def run_guard(target):
    return subprocess.run([sys.executable, str(GUARD), "--root", str(target)],
                          capture_output=True, text=True)

def test_repo_is_clean():
    r = run_guard(ROOT)
    assert r.returncode == 0, r.stdout + r.stderr

def test_flags_a_fit_score_in_an_example(tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "bad.md").write_text("Fit score: 87/100\n")
    r = run_guard(tmp_path)
    assert r.returncode == 1
    assert "bad.md" in r.stdout

def test_allows_salary_display_and_equota(tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "ok.md").write_text(
        "- Senior Engineer — Acme — $180K–$220K\nE-QUOTA: API limit reached.\n")
    r = run_guard(tmp_path)
    assert r.returncode == 0, r.stdout

def test_prose_budget_word_not_flagged(tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "brief.md").write_text(
        "- No support or budget for a design team (red flag).\n")
    assert run_guard(tmp_path).returncode == 0, run_guard(tmp_path).stdout

def test_budget_config_field_flagged(tmp_path):
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "cfg.yaml").write_text("budget: 100\n")
    r = run_guard(tmp_path)
    assert r.returncode == 1 and "cfg.yaml" in r.stdout
