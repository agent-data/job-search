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

def test_links_clean_passes(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Map\n")
    d = tmp_path / "docs"; d.mkdir()
    (d / "a.md").write_text(
        "# A Doc\n\nSee [the map](../AGENTS.md) and [this section](#a-doc).\n"
        "External [link](https://example.com/x) is ignored.\n")
    r = run_lint(tmp_path, "--only", "internal-links")
    assert r.returncode == 0, r.stdout + r.stderr

def test_links_broken_path_fails(tmp_path):
    d = tmp_path / "docs"; d.mkdir()
    (d / "a.md").write_text("See [missing](./does-not-exist.md).\n")
    r = run_lint(tmp_path, "--only", "internal-links")
    assert r.returncode == 1
    assert "does-not-exist.md" in r.stdout

def test_links_broken_anchor_fails(tmp_path):
    d = tmp_path / "docs"; d.mkdir()
    (d / "a.md").write_text("# Real Heading\n\nJump to [nowhere](#no-such-heading).\n")
    r = run_lint(tmp_path, "--only", "internal-links")
    assert r.returncode == 1
    assert "no-such-heading" in r.stdout

def test_links_external_url_ignored(tmp_path):
    d = tmp_path / "docs"; d.mkdir()
    (d / "a.md").write_text("[http](http://x.test) [https](https://x.test) [mail](mailto:a@b.c)\n")
    r = run_lint(tmp_path, "--only", "internal-links")
    assert r.returncode == 0, r.stdout

def _valid_agents_md():
    links = ["ARCHITECTURE.md", "docs/design-docs/index.md", "docs/design-docs/core-beliefs.md",
             "docs/exec-plans/index.md", "docs/product-specs/index.md", "docs/QUALITY_SCORE.md",
             "docs/PRODUCT_SENSE.md", "docs/RELIABILITY.md", "docs/SECURITY.md",
             "docs/INTERFACE.md", "docs/PLANS.md", "shared/references/"]
    return "# Agent Map\n\n" + "\n".join(f"- [{t}]({t})" for t in links) + "\n"

def test_agents_map_valid_passes(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "AGENTS.md").write_text(_valid_agents_md())
    r = run_lint(tmp_path, "--only", "agents-map")
    assert r.returncode == 0, r.stdout + r.stderr

def test_agents_map_missing_pillar_fails(tmp_path):
    (tmp_path / "docs").mkdir()
    text = _valid_agents_md().replace("- [docs/QUALITY_SCORE.md](docs/QUALITY_SCORE.md)\n", "")
    (tmp_path / "AGENTS.md").write_text(text)
    r = run_lint(tmp_path, "--only", "agents-map")
    assert r.returncode == 1 and "QUALITY_SCORE.md" in r.stdout

def test_agents_map_oversize_fails(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "AGENTS.md").write_text(_valid_agents_md() + "filler\n" * 200)
    r = run_lint(tmp_path, "--only", "agents-map")
    assert r.returncode == 1 and "too large" in r.stdout

def test_agents_map_missing_file_when_kb_present_fails(tmp_path):
    (tmp_path / "docs").mkdir()
    r = run_lint(tmp_path, "--only", "agents-map")
    assert r.returncode == 1 and "missing" in r.stdout.lower()
