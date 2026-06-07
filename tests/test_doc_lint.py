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


def _design_fm(**over):
    fm = {"title": "T", "status": "current", "verified": "partial",
          "last_reviewed": "2026-06-07", "code_refs": "[scripts/osctl.py]"}
    fm.update(over)
    return "---\n" + "\n".join(f"{k}: {v}" for k, v in fm.items()) + "\n---\n# T\n"

def test_frontmatter_valid_design_doc_passes(tmp_path):
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    (d / "x.md").write_text(_design_fm())
    r = run_lint(tmp_path, "--only", "frontmatter-schema")
    assert r.returncode == 0, r.stdout + r.stderr

def test_frontmatter_missing_key_fails(tmp_path):
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    (d / "x.md").write_text("---\ntitle: T\nverified: partial\nlast_reviewed: 2026-06-07\ncode_refs: [scripts/osctl.py]\n---\n# T\n")
    r = run_lint(tmp_path, "--only", "frontmatter-schema")
    assert r.returncode == 1 and "status" in r.stdout

def test_frontmatter_bad_enum_fails(tmp_path):
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    (d / "x.md").write_text(_design_fm(status="bogus"))
    r = run_lint(tmp_path, "--only", "frontmatter-schema")
    assert r.returncode == 1 and "status" in r.stdout

def test_frontmatter_absent_block_fails(tmp_path):
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    (d / "x.md").write_text("# No frontmatter\n")
    r = run_lint(tmp_path, "--only", "frontmatter-schema")
    assert r.returncode == 1 and "frontmatter" in r.stdout.lower()

def test_frontmatter_index_exempt(tmp_path):
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    (d / "index.md").write_text("# Index, no frontmatter\n")
    r = run_lint(tmp_path, "--only", "frontmatter-schema")
    assert r.returncode == 0, r.stdout

def test_frontmatter_valid_plan_passes(tmp_path):
    d = tmp_path / "docs" / "exec-plans" / "active"; d.mkdir(parents=True)
    (d / "p.md").write_text("---\ntitle: P\nstate: active\ncreated: 2026-06-07\n---\n# P\n")
    r = run_lint(tmp_path, "--only", "frontmatter-schema")
    assert r.returncode == 0, r.stdout + r.stderr

def test_frontmatter_completed_plan_requires_completed_date(tmp_path):
    d = tmp_path / "docs" / "exec-plans" / "completed"; d.mkdir(parents=True)
    (d / "p.md").write_text("---\ntitle: P\nstate: completed\ncreated: 2026-06-07\n---\n# P\n")
    r = run_lint(tmp_path, "--only", "frontmatter-schema")
    assert r.returncode == 1 and "completed" in r.stdout

def test_code_refs_resolve_passes(tmp_path):
    (tmp_path / "thing.py").write_text("x = 1\n")
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    (d / "x.md").write_text(_design_fm(code_refs="[thing.py]"))
    r = run_lint(tmp_path, "--only", "code-refs-exist")
    assert r.returncode == 0, r.stdout + r.stderr

def test_code_refs_missing_fails(tmp_path):
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    (d / "x.md").write_text(_design_fm(code_refs="[nope.py]"))
    r = run_lint(tmp_path, "--only", "code-refs-exist")
    assert r.returncode == 1 and "nope.py" in r.stdout
