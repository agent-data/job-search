import subprocess, sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[1]
VALIDATE = ROOT / "scripts" / "validate_platforms.py"

# The 12 canonical adapter sections — kept in sync with validate_platforms.CANONICAL_SECTIONS.
SECTIONS = ("Identity", "Tool map", "Run recipe", "Scheduling", "Headless invocation",
            "Closed-choice question", "Concurrent detail reads", "Model tiers",
            "Whole-file write", "Block-alert channel", "agent-data setup", "Packaging & install")


def run_validate(target, *extra):
    return subprocess.run([sys.executable, str(VALIDATE), "--root", str(target), *extra],
                          capture_output=True, text=True)


def _adapter_md(sections=SECTIONS):
    return "# Platform adapter — Test\n\nintro\n\n" + "".join(
        f"## {s}\n\nbody for {s}.\n\n" for s in sections)


def _seed_adapters(root, harnesses=("claude", "codex", "cursor"), sections=SECTIONS):
    """Write a minimal but complete platform/ adapter set under a tmp root."""
    d = root / "shared" / "references" / "platform"
    d.mkdir(parents=True)
    for h in harnesses:
        (d / f"{h}.md").write_text(_adapter_md(sections))


# ---- repo-level: the real tree must pass every check ----

def test_validator_runs_clean_on_repo():
    r = run_validate(ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "clean" in r.stdout.lower()

def test_empty_tree_is_clean():
    # nothing to validate in a bare tree -> clean
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        r = run_validate(t)
        assert r.returncode == 0, r.stdout + r.stderr


# ---- adapter-sections ----

def test_adapter_sections_complete_passes(tmp_path):
    _seed_adapters(tmp_path)
    r = run_validate(tmp_path, "--only", "adapter-sections")
    assert r.returncode == 0, r.stdout + r.stderr

def test_adapter_sections_missing_section_fails(tmp_path):
    _seed_adapters(tmp_path)
    # drop the Scheduling heading from one adapter
    p = tmp_path / "shared" / "references" / "platform" / "codex.md"
    p.write_text(p.read_text().replace("## Scheduling\n\nbody for Scheduling.\n\n", ""))
    r = run_validate(tmp_path, "--only", "adapter-sections")
    assert r.returncode == 1
    assert "Scheduling" in r.stdout and "codex.md" in r.stdout

def test_adapter_sections_renamed_section_fails(tmp_path):
    _seed_adapters(tmp_path)
    p = tmp_path / "shared" / "references" / "platform" / "cursor.md"
    p.write_text(p.read_text().replace("## Model tiers", "## Model levels"))
    r = run_validate(tmp_path, "--only", "adapter-sections")
    assert r.returncode == 1 and "Model tiers" in r.stdout

def test_adapter_sections_synced_copy_must_match(tmp_path):
    _seed_adapters(tmp_path)
    # a skills/*/references/platform/ copy that drifts from source must fail
    copy_dir = tmp_path / "skills" / "job-search" / "references" / "platform"
    copy_dir.mkdir(parents=True)
    (copy_dir / "claude.md").write_text(_adapter_md() + "\nDRIFTED EXTRA LINE\n")
    r = run_validate(tmp_path, "--only", "adapter-sections")
    assert r.returncode == 1 and "synced copy differs" in r.stdout

def test_adapter_sections_synced_copy_matching_passes(tmp_path):
    _seed_adapters(tmp_path)
    src = (tmp_path / "shared" / "references" / "platform" / "claude.md").read_text()
    copy_dir = tmp_path / "skills" / "job-search" / "references" / "platform"
    copy_dir.mkdir(parents=True)
    (copy_dir / "claude.md").write_text(src)  # byte-for-byte
    r = run_validate(tmp_path, "--only", "adapter-sections")
    assert r.returncode == 0, r.stdout + r.stderr


# ---- manifest-parse ----

def test_manifest_valid_json_passes(tmp_path):
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "x"}))
    (tmp_path / "package.json").write_text(json.dumps({"name": "y", "version": "0.1.0"}))
    r = run_validate(tmp_path, "--only", "manifest-parse")
    assert r.returncode == 0, r.stdout + r.stderr

def test_manifest_corrupt_json_fails(tmp_path):
    (tmp_path / ".cursor-plugin").mkdir()
    (tmp_path / ".cursor-plugin" / "plugin.json").write_text('{"name": "x",}')  # trailing comma
    r = run_validate(tmp_path, "--only", "manifest-parse")
    assert r.returncode == 1
    assert "invalid JSON" in r.stdout and "cursor-plugin" in r.stdout

def test_manifest_absent_optional_is_not_a_failure(tmp_path):
    # no manifests present at all -> nothing to parse -> clean (optional, discovered not required)
    r = run_validate(tmp_path, "--only", "manifest-parse")
    assert r.returncode == 0, r.stdout + r.stderr

def test_opencode_js_bad_syntax_fails_when_node_present(tmp_path):
    import shutil
    if shutil.which("node") is None:
        import pytest; pytest.skip("node not on PATH")
    d = tmp_path / ".opencode" / "plugins"; d.mkdir(parents=True)
    (d / "job-search.js").write_text('const x = "unterminated\n')  # broken syntax
    r = run_validate(tmp_path, "--only", "manifest-parse")
    assert r.returncode == 1 and "node --check failed" in r.stdout

def test_opencode_js_valid_passes_when_node_present(tmp_path):
    import shutil
    if shutil.which("node") is None:
        import pytest; pytest.skip("node not on PATH")
    d = tmp_path / ".opencode" / "plugins"; d.mkdir(parents=True)
    (d / "job-search.js").write_text("export const Plugin = async () => ({});\n")
    r = run_validate(tmp_path, "--only", "manifest-parse")
    assert r.returncode == 0, r.stdout + r.stderr


# ---- adapter-cross-refs ----

def test_cross_ref_resolves_passes(tmp_path):
    _seed_adapters(tmp_path)
    sr = tmp_path / "shared" / "references"
    (sr / "voice.md").write_text(
        "Ask it as prose — see your platform's adapter → Closed-choice question. Done.\n")
    r = run_validate(tmp_path, "--only", "adapter-cross-refs")
    assert r.returncode == 0, r.stdout + r.stderr

def test_cross_ref_compound_resolves_passes(tmp_path):
    _seed_adapters(tmp_path)
    sr = tmp_path / "shared" / "references"
    (sr / "internals.md").write_text(
        "Use its file tools (your platform's adapter → Tool map / Whole-file write) here.\n")
    r = run_validate(tmp_path, "--only", "adapter-cross-refs")
    assert r.returncode == 0, r.stdout + r.stderr

def test_cross_ref_wrapped_across_lines_passes(tmp_path):
    _seed_adapters(tmp_path)
    sr = tmp_path / "shared" / "references"
    (sr / "voice.md").write_text("see your platform's adapter →\nClosed-choice question. ok\n")
    r = run_validate(tmp_path, "--only", "adapter-cross-refs")
    assert r.returncode == 0, r.stdout + r.stderr

def test_cross_ref_bogus_section_fails(tmp_path):
    _seed_adapters(tmp_path)
    sr = tmp_path / "shared" / "references"
    (sr / "voice.md").write_text("see your platform's adapter → Bogus section. nope\n")
    r = run_validate(tmp_path, "--only", "adapter-cross-refs")
    assert r.returncode == 1
    assert "not a canonical section" in r.stdout and "voice.md" in r.stdout

def test_cross_ref_in_skill_fails(tmp_path):
    _seed_adapters(tmp_path)
    sk = tmp_path / "skills" / "job-search"; sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text("compose from your platform's adapter → Run reciept (typo).\n")
    r = run_validate(tmp_path, "--only", "adapter-cross-refs")
    assert r.returncode == 1 and "not a canonical section" in r.stdout

def test_cross_ref_non_adapter_arrows_ignored(tmp_path):
    _seed_adapters(tmp_path)
    sr = tmp_path / "shared" / "references"
    # arrows not anchored by "adapter" (data flow, fallback, error map) are NOT cross-refs
    (sr / "errors.md").write_text(
        "Pipeline: search → dedup → judge → persist → digest. true → retry; → E-QUOTA.\n")
    r = run_validate(tmp_path, "--only", "adapter-cross-refs")
    assert r.returncode == 0, r.stdout + r.stderr

def test_cross_ref_section_absent_from_one_adapter_fails(tmp_path):
    # a referenced section that exists in some adapters but is missing from another -> unresolvable
    # on that harness. (Use --only so adapter-sections doesn't also flag the missing heading.)
    _seed_adapters(tmp_path)
    # remove "Scheduling" from just one adapter
    p = tmp_path / "shared" / "references" / "platform" / "cursor.md"
    p.write_text(p.read_text().replace("## Scheduling\n\nbody for Scheduling.\n\n", ""))
    sr = tmp_path / "shared" / "references"
    (sr / "home.md").write_text("recorded by the active platform (your adapter → Scheduling).\n")
    r = run_validate(tmp_path, "--only", "adapter-cross-refs")
    assert r.returncode == 1
    assert "absent from adapter(s): cursor" in r.stdout

def test_cross_ref_defers_to_resolves_passes(tmp_path):
    # the "defers to → <Section>" deferral form is a genuine adapter cross-ref and must resolve
    _seed_adapters(tmp_path)
    sr = tmp_path / "shared" / "references"
    (sr / "conventions.md").write_text(
        "the fan-out itself defers to → Concurrent detail reads (inherit = the run's own model).\n")
    r = run_validate(tmp_path, "--only", "adapter-cross-refs")
    assert r.returncode == 0, r.stdout + r.stderr

def test_cross_ref_defers_to_bogus_section_fails(tmp_path):
    # a typo'd / renamed target on the "defers to →" form must now be caught (was silently un-validated)
    _seed_adapters(tmp_path)
    sr = tmp_path / "shared" / "references"
    (sr / "conventions.md").write_text(
        "the fan-out itself defers to → Concurent detail reads (typo).\n")
    r = run_validate(tmp_path, "--only", "adapter-cross-refs")
    assert r.returncode == 1
    assert "not a canonical section" in r.stdout and "conventions.md" in r.stdout

def test_adapters_themselves_not_scanned_for_cross_refs(tmp_path):
    # the adapters define the sections; a "→ Bogus" inside an adapter body is not a cross-ref source
    _seed_adapters(tmp_path)
    p = tmp_path / "shared" / "references" / "platform" / "claude.md"
    p.write_text(p.read_text() + "\nsee the adapter → Bogus thing here.\n")
    r = run_validate(tmp_path, "--only", "adapter-cross-refs")
    assert r.returncode == 0, r.stdout + r.stderr


# ---- skill-frontmatter ----

def _seed_skill(root, name, description,
                extra="disable-model-invocation: false\nuser-invocable: true\n", body="\n# Body\n"):
    """Write a minimal skills/<name>/SKILL.md with the given frontmatter description."""
    d = root / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n{extra}---\n{body}")

def test_skill_frontmatter_clean_passes(tmp_path):
    _seed_skill(tmp_path, "job-search", 'Set up and steer the search — e.g. "start my job search".')
    r = run_validate(tmp_path, "--only", "skill-frontmatter")
    assert r.returncode == 0, r.stdout + r.stderr

def test_skill_frontmatter_unquoted_colon_fails(tmp_path):
    # the exact Codex bug: a plain description value with a ': ' before quoted examples
    _seed_skill(tmp_path, "job-search",
                'Steer the search, what they\'re looking for: "start my job search".')
    r = run_validate(tmp_path, "--only", "skill-frontmatter")
    assert r.returncode == 1
    assert "skill-frontmatter" in r.stdout and "job-search" in r.stdout and "': '" in r.stdout

def test_skill_frontmatter_em_dash_fix_passes(tmp_path):
    # the shipped fix shape: an em-dash instead of the colon before the examples
    _seed_skill(tmp_path, "job-search-run",
                'Run one pass — "run a job search now", "pull jobs now", "do a fresh search".')
    r = run_validate(tmp_path, "--only", "skill-frontmatter")
    assert r.returncode == 0, r.stdout + r.stderr

def test_skill_frontmatter_quoted_value_with_colon_passes(tmp_path):
    # a double-quoted value may legitimately contain a colon — must not be a false positive
    _seed_skill(tmp_path, "job-search", '"Steer the search: the front door and home screen."')
    r = run_validate(tmp_path, "--only", "skill-frontmatter")
    assert r.returncode == 0, r.stdout + r.stderr

def test_skill_frontmatter_missing_required_key_fails(tmp_path):
    d = tmp_path / "skills" / "job-search"; d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: job-search\nuser-invocable: true\n---\n# body\n")
    r = run_validate(tmp_path, "--only", "skill-frontmatter")
    assert r.returncode == 1 and "missing required key 'description'" in r.stdout

def test_skill_frontmatter_missing_block_fails(tmp_path):
    d = tmp_path / "skills" / "job-search"; d.mkdir(parents=True)
    (d / "SKILL.md").write_text("# No frontmatter here\n\nbody\n")
    r = run_validate(tmp_path, "--only", "skill-frontmatter")
    assert r.returncode == 1 and "missing `---`-fenced" in r.stdout


# ---- codex-workspace-write ----

def test_codex_workspace_write_clean_passes(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "codex.md").write_text(
        "cd <workspace> && codex exec --skip-git-repo-check --sandbox workspace-write \\\n"
        "  -c sandbox_workspace_write.network_access=true '$job-search-run'\n"
        "codex exec --skip-git-repo-check --sandbox workspace-write --add-dir <workspace> \\\n"
        "  -c sandbox_workspace_write.network_access=true '$job-search-run'\n"
    )
    r = run_validate(tmp_path, "--only", "codex-workspace-write")
    assert r.returncode == 0, r.stdout + r.stderr

def test_codex_workspace_write_without_workspace_fails(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "codex.md").write_text(
        "codex exec --skip-git-repo-check --sandbox workspace-write \\\n"
        "  -c sandbox_workspace_write.network_access=true '$job-search-run'\n"
    )
    r = run_validate(tmp_path, "--only", "codex-workspace-write")
    assert r.returncode == 1
    assert "codex-workspace-write" in r.stdout
    assert "cd <workspace>" in r.stdout and "--add-dir <workspace>" in r.stdout


# ---- codex-parallel-subagents ----

def _codex_parallel_doc(**overrides):
    parts = {
        "preference": "search.parallel_detail_reads controls whether detail reads use subagents.\n",
        "profile": "$CODEX_HOME/job-search.config.toml enables the job-search profile.\n",
        "feature": "[features]\nmulti_agent = true\n",
        "cli_profile": "codex exec --profile job-search '$job-search-run --workspace <workspace>. Use parallel subagents for all detail reads.'\n",
        "automation_prompt": "Codex Automation prompt: Use $job-search-run. Use parallel subagents for all detail reads.\n",
        "model_fast": "| `fast` | `gpt-5.4-mini` |\n",
        "model_balanced": "| `balanced` | `gpt-5.4` |\n",
        "model_high": "| `high` | `gpt-5.5` |\n",
        "fallback": "If Codex refuses subagent spawning, read and judge each posting sequentially.\n",
    }
    parts.update(overrides)
    return "\n".join(parts.values())


def test_codex_parallel_subagent_contract_clean_passes(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "codex.md").write_text(_codex_parallel_doc())
    r = run_validate(tmp_path, "--only", "codex-parallel-subagents")
    assert r.returncode == 0, r.stdout + r.stderr


def test_codex_parallel_subagent_contract_requires_explicit_prompt(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "codex.md").write_text(_codex_parallel_doc(cli_profile="", automation_prompt=""))
    r = run_validate(tmp_path, "--only", "codex-parallel-subagents")
    assert r.returncode == 1
    assert "Use parallel subagents for all detail reads" in r.stdout


def test_codex_parallel_subagent_contract_requires_mini_fast_model(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "codex.md").write_text(_codex_parallel_doc(model_fast="| `fast` | `gpt-5` |\n"))
    r = run_validate(tmp_path, "--only", "codex-parallel-subagents")
    assert r.returncode == 1
    assert "gpt-5.4-mini" in r.stdout


def test_codex_parallel_subagent_contract_requires_balanced_model(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "codex.md").write_text(_codex_parallel_doc(model_balanced=""))
    r = run_validate(tmp_path, "--only", "codex-parallel-subagents")
    assert r.returncode == 1
    assert "balanced" in r.stdout and "gpt-5.4" in r.stdout


# ---- runtime-bundle: the bundled state-ops runtime must match source, only in consuming skills ----

def _seed_runtime(root, files=("cli.py", "registry.py"),
                  bundle_into=("job-search", "job-search-run", "job-search-agent")):
    src = root / "runtime" / "hermes_job_search"
    src.mkdir(parents=True)
    for fn in files:
        (src / fn).write_text(f"# {fn}\nprint('ok')\n")
    for skill in bundle_into:
        dest = root / "skills" / skill / "scripts" / "hermes_job_search"
        dest.mkdir(parents=True)
        for fn in files:
            (dest / fn).write_text((src / fn).read_text())
    return src


def test_runtime_bundle_clean_when_in_sync(tmp_path):
    _seed_runtime(tmp_path)
    r = run_validate(tmp_path, "--only", "runtime-bundle")
    assert r.returncode == 0, r.stdout + r.stderr


def test_runtime_bundle_absent_source_is_noop(tmp_path):
    r = run_validate(tmp_path, "--only", "runtime-bundle")
    assert r.returncode == 0, r.stdout + r.stderr


def test_runtime_bundle_drift_fails(tmp_path):
    _seed_runtime(tmp_path)
    drift = tmp_path / "skills" / "job-search-run" / "scripts" / "hermes_job_search" / "cli.py"
    drift.write_text("# tampered\n")
    r = run_validate(tmp_path, "--only", "runtime-bundle")
    assert r.returncode == 1
    assert "runtime-bundle" in r.stdout and "build.sh" in r.stdout


def test_runtime_bundle_missing_in_consuming_skill_fails(tmp_path):
    import shutil
    _seed_runtime(tmp_path)
    shutil.rmtree(tmp_path / "skills" / "job-search-agent" / "scripts" / "hermes_job_search")
    r = run_validate(tmp_path, "--only", "runtime-bundle")
    assert r.returncode == 1 and "missing" in r.stdout


def test_runtime_bundle_in_non_consuming_skill_fails(tmp_path):
    _seed_runtime(tmp_path)
    extra = tmp_path / "skills" / "evaluate-job-fit" / "scripts" / "hermes_job_search"
    extra.mkdir(parents=True)
    (extra / "cli.py").write_text("# x\n")
    r = run_validate(tmp_path, "--only", "runtime-bundle")
    assert r.returncode == 1 and "non-consuming" in r.stdout


# ---- hermes-runtime-invocation: no-op until hermes.md exists, then must document the call ----

def test_hermes_runtime_invocation_absent_is_noop(tmp_path):
    r = run_validate(tmp_path, "--only", "hermes-runtime-invocation")
    assert r.returncode == 0, r.stdout + r.stderr


def test_hermes_runtime_invocation_present_passes(tmp_path):
    d = tmp_path / "shared" / "references" / "platform"
    d.mkdir(parents=True)
    (d / "hermes.md").write_text(
        "## Whole-file write\nrun `python3 ${HERMES_SKILL_DIR}/scripts/hermes_job_search/cli.py`\n"
        "## Scheduling\nrecord scheduling.mechanism: hermes-cron\n"
        "## Concurrent detail reads\nfan out via delegate_task\n")
    r = run_validate(tmp_path, "--only", "hermes-runtime-invocation")
    assert r.returncode == 0, r.stdout + r.stderr


def test_hermes_runtime_invocation_missing_needle_fails(tmp_path):
    d = tmp_path / "shared" / "references" / "platform"
    d.mkdir(parents=True)
    (d / "hermes.md").write_text("## Scheduling\nhermes-cron\n## Concurrent detail reads\ndelegate_task\n")
    r = run_validate(tmp_path, "--only", "hermes-runtime-invocation")
    assert r.returncode == 1 and "hermes-runtime-invocation" in r.stdout


# ---- hermes-prior-session: no-op until hermes.md exists, then must document prior-session recall ----

def test_hermes_prior_session_present_passes(tmp_path):
    d = tmp_path / "shared" / "references" / "platform"
    d.mkdir(parents=True)
    (d / "hermes.md").write_text(
        "## Prior-session recall\n\nUse `session_search`; draft to the brief, never USER.md.\n")
    r = run_validate(tmp_path, "--only", "hermes-prior-session")
    assert r.returncode == 0, r.stdout


def test_hermes_prior_session_missing_section_fails(tmp_path):
    d = tmp_path / "shared" / "references" / "platform"
    d.mkdir(parents=True)
    (d / "hermes.md").write_text("## Identity\n\nHermes.\n")
    r = run_validate(tmp_path, "--only", "hermes-prior-session")
    assert r.returncode == 1
    assert "hermes-prior-session" in r.stdout


def test_hermes_prior_session_missing_needle_fails(tmp_path):
    d = tmp_path / "shared" / "references" / "platform"
    d.mkdir(parents=True)
    (d / "hermes.md").write_text("## Prior-session recall\n\nRecall prior context to draft.\n")
    r = run_validate(tmp_path, "--only", "hermes-prior-session")
    assert r.returncode == 1
    assert "hermes-prior-session" in r.stdout
