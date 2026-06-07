import subprocess, sys, pathlib, datetime
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


def test_dup_pointer_with_link_passes(tmp_path):
    d = tmp_path / "docs"; d.mkdir()
    (d / "a.md").write_text(
        "Frequencies live in [conventions.md](../shared/references/conventions.md); "
        "it lists every-2-hours among others.\n")
    r = run_lint(tmp_path, "--only", "no-shared-reference-duplication")
    assert r.returncode == 0, r.stdout + r.stderr

def test_dup_restated_without_link_fails(tmp_path):
    d = tmp_path / "docs"; d.mkdir()
    (d / "a.md").write_text("Frequencies: hourly, every-2-hours, every-6-hours, daily, weekly.\n")
    r = run_lint(tmp_path, "--only", "no-shared-reference-duplication")
    assert r.returncode == 1 and "frequency enum" in r.stdout

def test_dup_exempts_exec_plans(tmp_path):
    d = tmp_path / "docs" / "exec-plans" / "active"; d.mkdir(parents=True)
    (d / "p.md").write_text("This plan mentions every-2-hours as an example token.\n")
    r = run_lint(tmp_path, "--only", "no-shared-reference-duplication")
    assert r.returncode == 0, r.stdout

def test_dup_exempts_historical_design_doc(tmp_path):
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    body = _design_fm(status="historical") + "The run_id format is YYYY-MM-DDTHH-MM-SSZ here.\n"
    (d / "old.md").write_text(body)
    r = run_lint(tmp_path, "--only", "no-shared-reference-duplication")
    assert r.returncode == 0, r.stdout


def test_index_lists_all_siblings_passes(tmp_path):
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    (d / "spec-a.md").write_text("# A\n")
    (d / "index.md").write_text("# Index\n\n- [A](spec-a.md)\n")
    r = run_lint(tmp_path, "--only", "index-completeness")
    assert r.returncode == 0, r.stdout + r.stderr

def test_index_missing_entry_fails(tmp_path):
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    (d / "spec-a.md").write_text("# A\n")
    (d / "index.md").write_text("# Index\n\n(nothing linked)\n")
    r = run_lint(tmp_path, "--only", "index-completeness")
    assert r.returncode == 1 and "spec-a.md" in r.stdout

def test_index_exec_plans_subdirs_passes(tmp_path):
    a = tmp_path / "docs" / "exec-plans" / "active"; a.mkdir(parents=True)
    (a / "p1.md").write_text("# P1\n")
    (tmp_path / "docs" / "exec-plans" / "index.md").write_text("# Plans\n\n- [P1](active/p1.md)\n")
    r = run_lint(tmp_path, "--only", "index-completeness")
    assert r.returncode == 0, r.stdout + r.stderr


def _full_quality_score():
    from importlib import util as _u  # mirror the canonical lists without importing the module here
    rows = "\n".join(
        f"| `{name}` | {kind} | strong | some gap |"
        for name, kind in (
            [("discovery-search","domain"),("preferences-judgment","domain"),
             ("workspace-state","domain"),("scheduling-consent","domain"),
             ("error-surfacing","domain"),("deterministic-core","layer"),
             ("shared-references","layer"),("skill-layer","layer"),
             ("hooks-guards","layer"),("tests-evals","layer")]))
    return "# Quality Score\n\n| Area | Kind | Grade | Gaps |\n|---|---|---|---|\n" + rows + "\n"

def test_quality_score_complete_passes(tmp_path):
    d = tmp_path / "docs"; d.mkdir()
    (d / "QUALITY_SCORE.md").write_text(_full_quality_score())
    r = run_lint(tmp_path, "--only", "quality-score-coverage")
    assert r.returncode == 0, r.stdout + r.stderr

def test_quality_score_missing_domain_fails(tmp_path):
    d = tmp_path / "docs"; d.mkdir()
    text = _full_quality_score().replace("| `scheduling-consent` | domain | strong | some gap |\n", "")
    (d / "QUALITY_SCORE.md").write_text(text)
    r = run_lint(tmp_path, "--only", "quality-score-coverage")
    assert r.returncode == 1 and "scheduling-consent" in r.stdout

def test_quality_score_missing_layer_fails(tmp_path):
    d = tmp_path / "docs"; d.mkdir()
    text = _full_quality_score().replace("| `hooks-guards` | layer | strong | some gap |\n", "")
    (d / "QUALITY_SCORE.md").write_text(text)
    r = run_lint(tmp_path, "--only", "quality-score-coverage")
    assert r.returncode == 1 and "hooks-guards" in r.stdout


def test_plan_state_matches_dir_passes(tmp_path):
    a = tmp_path / "docs" / "exec-plans" / "active"; a.mkdir(parents=True)
    (a / "p.md").write_text("---\ntitle: P\nstate: active\ncreated: 2026-06-07\n---\n# P\n")
    r = run_lint(tmp_path, "--only", "plan-location")
    assert r.returncode == 0, r.stdout + r.stderr

def test_plan_state_mismatch_fails(tmp_path):
    a = tmp_path / "docs" / "exec-plans" / "active"; a.mkdir(parents=True)
    (a / "p.md").write_text("---\ntitle: P\nstate: completed\ncreated: 2026-06-07\ncompleted: 2026-06-07\n---\n# P\n")
    r = run_lint(tmp_path, "--only", "plan-location")
    assert r.returncode == 1 and "state" in r.stdout

def test_plan_loose_in_root_fails(tmp_path):
    e = tmp_path / "docs" / "exec-plans"; e.mkdir(parents=True)
    (e / "stray-plan.md").write_text("---\ntitle: X\nstate: active\ncreated: 2026-06-07\n---\n# X\n")
    r = run_lint(tmp_path, "--only", "plan-location")
    assert r.returncode == 1 and "loose" in r.stdout

def test_plan_root_allows_tracker_and_index(tmp_path):
    e = tmp_path / "docs" / "exec-plans"; e.mkdir(parents=True)
    (e / "index.md").write_text("# Plans\n")
    (e / "tech-debt-tracker.md").write_text("# Tech Debt\n")
    r = run_lint(tmp_path, "--only", "plan-location")
    assert r.returncode == 0, r.stdout + r.stderr


def _recent(): return (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
def _old(): return (datetime.date.today() - datetime.timedelta(days=200)).isoformat()

def test_fresh_recent_no_warning(tmp_path):
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    (d / "x.md").write_text(_design_fm(last_reviewed=_recent()))
    r = run_lint(tmp_path, "--only", "freshness-markers")
    assert r.returncode == 0
    assert "freshness" not in r.stdout

def test_fresh_stale_warns_not_fails(tmp_path):
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    (d / "x.md").write_text(_design_fm(last_reviewed=_old()))
    r = run_lint(tmp_path, "--only", "freshness-markers")
    assert r.returncode == 0           # warning, not a failure, by default
    assert "warning" in r.stdout and "x.md" in r.stdout

def test_fresh_stale_fails_under_strict(tmp_path):
    d = tmp_path / "docs" / "design-docs"; d.mkdir(parents=True)
    (d / "x.md").write_text(_design_fm(last_reviewed=_old()))
    r = run_lint(tmp_path, "--only", "freshness-markers", "--strict-fresh")
    assert r.returncode == 1 and "x.md" in r.stdout
