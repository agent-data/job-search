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

def test_allows_calls_first_payg_equivalent(tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "digest.md").write_text(
        "Agent-data usage: 9 metered calls this run · about $0.072 pay-as-you-go equivalent\n")
    r = run_guard(tmp_path)
    assert r.returncode == 0, r.stdout

def test_still_flags_credit_or_cost_config_fields(tmp_path):
    (tmp_path / "templates").mkdir()
    for name in ("credits", "cost"):
        (tmp_path / "templates" / f"{name}.yaml").write_text(f"{name}: 100\n")
    r = run_guard(tmp_path)
    assert r.returncode == 1
    assert "credits.yaml" in r.stdout and "cost.yaml" in r.stdout

def test_flags_unverified_actual_charge_claim(tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "bad-charge.md").write_text(
        "Your actual charge for this run was $0.072.\n")
    r = run_guard(tmp_path)
    assert r.returncode == 1
    assert "actual charge" in r.stdout

def test_allows_not_actual_charge_disclaimer(tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "usage.md").write_text(
        "About $0.072 pay-as-you-go equivalent, not an actual charge.\n")
    r = run_guard(tmp_path)
    assert r.returncode == 0, r.stdout

def test_dollar_or_salary_text_does_not_hide_fit_score(tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "bad-score.md").write_text(
        "Salary: $180K. Fit score: 87/100.\n")
    r = run_guard(tmp_path)
    assert r.returncode == 1
    assert "fit score" in r.stdout
