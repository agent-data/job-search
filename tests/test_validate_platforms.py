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

def test_adapter_may_omit_inapplicable_section(tmp_path):
    # required-if-applicable (doc-15 rec 2, AAS-ANTI-28): an adapter may OMIT a canonical section it has
    # no verified content for — the gate no longer forces every host to manufacture all 12. With nothing
    # pointing at it, adapter-sections passes (the omission is not flagged).
    _seed_adapters(tmp_path)
    p = tmp_path / "shared" / "references" / "platform" / "codex.md"
    p.write_text(p.read_text().replace("## Scheduling\n\nbody for Scheduling.\n\n", ""))
    r = run_validate(tmp_path, "--only", "adapter-sections")
    assert r.returncode == 0, r.stdout + r.stderr

def test_adapter_omitted_section_still_flags_if_referenced(tmp_path):
    # the relaxation is required-IF-APPLICABLE: omission is allowed ONLY for a section nothing points at.
    # adapter-sections stays SILENT on the omission (relaxed), but a skill/neutral-body pointer at the
    # omitted section must STILL flag via the cross-ref layer (skills must not point at nothing). This
    # proves both halves at once: the section flag is gone; the cross-ref safety net is intact.
    _seed_adapters(tmp_path)
    p = tmp_path / "shared" / "references" / "platform" / "cursor.md"
    p.write_text(p.read_text().replace("## Model tiers\n\nbody for Model tiers.\n\n", ""))
    sr = tmp_path / "shared" / "references"
    (sr / "conventions.md").write_text("pick the model via your platform's adapter → Model tiers.\n")
    r = run_validate(tmp_path, "--only", "adapter-sections", "--only", "adapter-cross-refs")
    assert r.returncode == 1
    assert "absent from adapter(s): cursor" in r.stdout           # cross-ref still fires
    assert "missing canonical section" not in r.stdout            # adapter-sections relaxed

def test_adapter_stub_section_is_an_accepted_cross_ref_target(tmp_path):
    # doc-15 rec 2: instead of manufacturing content, an adapter may carry a section as a one-line
    # "no verified guidance" STUB. The stub heading is present, so it still LANDS a skill's pointer
    # (the cross-ref resolves against sections-present) — omission and stub are both accepted.
    _seed_adapters(tmp_path)
    p = tmp_path / "shared" / "references" / "platform" / "cursor.md"
    p.write_text(p.read_text().replace(
        "## Model tiers\n\nbody for Model tiers.\n\n",
        "## Model tiers\n\n_no verified guidance; see the capability matrix_\n\n"))
    sr = tmp_path / "shared" / "references"
    (sr / "conventions.md").write_text("pick the model via your platform's adapter → Model tiers.\n")
    r = run_validate(tmp_path, "--only", "adapter-sections", "--only", "adapter-cross-refs")
    assert r.returncode == 0, r.stdout + r.stderr

def test_adapter_sections_resurrected_fanned_copy_flagged(tmp_path):
    _seed_adapters(tmp_path)
    # the fan-out is removed (belief 5): ANY skills/*/references/platform/ copy is a resurrected
    # fanned copy and must fail — even a byte-identical one.
    copy_dir = tmp_path / "skills" / "job-search" / "references" / "platform"
    copy_dir.mkdir(parents=True)
    (copy_dir / "claude.md").write_text(_adapter_md())
    r = run_validate(tmp_path, "--only", "adapter-sections")
    assert r.returncode == 1 and "resurrected" in r.stdout

def test_adapter_sections_single_home_no_skill_copies_passes(tmp_path):
    _seed_adapters(tmp_path)
    # single-homed adapters with NO per-skill platform copies is the valid steady state.
    (tmp_path / "skills" / "job-search").mkdir(parents=True)
    r = run_validate(tmp_path, "--only", "adapter-sections")
    assert r.returncode == 0, r.stdout + r.stderr

def test_underscore_partial_is_not_an_adapter(tmp_path):
    # an underscore-prefixed file (e.g. _common.md) is a SHARED PARTIAL, not a harness adapter: it holds
    # the host-neutral boilerplate the adapters point to and is NOT required to carry the 12 sections.
    _seed_adapters(tmp_path)
    d = tmp_path / "shared" / "references" / "platform"
    (d / "_common.md").write_text("# shared partial\n\n## Whole-file write\n\nthe common rule.\n")
    r = run_validate(tmp_path, "--only", "adapter-sections")
    assert r.returncode == 0, r.stdout + r.stderr

def test_underscore_partial_not_a_cross_ref_target(tmp_path):
    # the partial is excluded from the adapter set, so a canonical section it happens NOT to carry is
    # still resolvable (resolution is proven against the real adapters, never the partial).
    _seed_adapters(tmp_path)
    d = tmp_path / "shared" / "references" / "platform"
    (d / "_common.md").write_text("# shared partial\n\n## Written record\n\nno canonical sections here.\n")
    sr = tmp_path / "shared" / "references"
    (sr / "voice.md").write_text("ask as prose — see your platform's adapter → Closed-choice question.\n")
    r = run_validate(tmp_path, "--only", "adapter-cross-refs")
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


def test_codex_parallel_subagent_tier_rename_stays_green(tmp_path):
    # finding #24 / AAS-ANTI-29: the gate must NOT pin a specific model id. Renaming an id in the
    # adapter's own tier table (a routine upstream rename) keeps the gate green — the binding still
    # resolves; only the literal changed. The literal no longer lives in the validator.
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "codex.md").write_text(_codex_parallel_doc(model_fast="| `fast` | `gpt-6-nano` |\n"))
    r = run_validate(tmp_path, "--only", "codex-parallel-subagents")
    assert r.returncode == 0, r.stdout + r.stderr


def test_codex_parallel_subagent_missing_tier_binding_fails(tmp_path):
    # de-literalized but NOT toothless: a tier with no row / no bound id in the table still fails —
    # the binding must resolve. (Keeps the real coverage; only the specific-id assertion is dropped.)
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "codex.md").write_text(_codex_parallel_doc(model_balanced=""))
    r = run_validate(tmp_path, "--only", "codex-parallel-subagents")
    assert r.returncode == 1
    assert "balanced" in r.stdout


def test_codex_parallel_subagent_unbound_tier_fails(tmp_path):
    # a tier row PRESENT but not bound to a code-quoted model id (prose placeholder / empty) is
    # malformed — the binding does not resolve — and still fails.
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "codex.md").write_text(_codex_parallel_doc(model_high="| `high` | (unset) |\n"))
    r = run_validate(tmp_path, "--only", "codex-parallel-subagents")
    assert r.returncode == 1
    assert "high" in r.stdout


# ---- primary-update-recipes ----

def test_primary_update_recipes_clean_passes(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "claude.md").write_text(
        "## Packaging & install\n\n"
        "### Update recipe\n\n"
        "```bash\n"
        "claude plugin marketplace update agent-data\n"
        "claude plugin update job-search@agent-data\n"
        "```\n"
    )
    (p / "codex.md").write_text(
        "## Packaging & install\n\n"
        "### Update recipe\n\n"
        "```bash\n"
        "codex plugin marketplace upgrade agent-data\n"
        "codex plugin add job-search@agent-data\n"
        "```\n"
    )
    r = run_validate(tmp_path, "--only", "primary-update-recipes")
    assert r.returncode == 0, r.stdout + r.stderr


def test_primary_update_recipes_missing_claude_update_fails(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "claude.md").write_text("## Packaging & install\n\nno update command\n")
    (p / "codex.md").write_text(
        "## Packaging & install\n\n"
        "codex plugin marketplace upgrade agent-data\n"
        "codex plugin add job-search@agent-data\n"
    )
    r = run_validate(tmp_path, "--only", "primary-update-recipes")
    assert r.returncode == 1
    assert "claude plugin update job-search@agent-data" in r.stdout


def test_primary_update_recipes_missing_codex_upgrade_fails(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "claude.md").write_text(
        "## Packaging & install\n\n"
        "claude plugin marketplace update agent-data\n"
        "claude plugin update job-search@agent-data\n"
    )
    (p / "codex.md").write_text("## Packaging & install\n\ncodex plugin add job-search@agent-data\n")
    r = run_validate(tmp_path, "--only", "primary-update-recipes")
    assert r.returncode == 1
    assert "codex plugin marketplace upgrade agent-data" in r.stdout


def test_primary_update_recipes_commands_outside_packaging_fails(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "claude.md").write_text(
        "## Run recipe\n\n"
        "```bash\n"
        "claude plugin marketplace update agent-data\n"
        "claude plugin update job-search@agent-data\n"
        "```\n\n"
        "## Packaging & install\n\n"
        "### Update recipe\n\n"
        "```bash\n"
        "```\n"
    )
    (p / "codex.md").write_text(
        "## Packaging & install\n\n"
        "### Update recipe\n\n"
        "```bash\n"
        "codex plugin marketplace upgrade agent-data\n"
        "codex plugin add job-search@agent-data\n"
        "```\n"
    )
    r = run_validate(tmp_path, "--only", "primary-update-recipes")
    assert r.returncode == 1
    assert "claude.md" in r.stdout and "Packaging & install" in r.stdout


def test_primary_update_recipes_reversed_command_order_fails(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "claude.md").write_text(
        "## Packaging & install\n\n"
        "### Update recipe\n\n"
        "```bash\n"
        "claude plugin update job-search@agent-data\n"
        "claude plugin marketplace update agent-data\n"
        "```\n"
    )
    (p / "codex.md").write_text(
        "## Packaging & install\n\n"
        "### Update recipe\n\n"
        "```bash\n"
        "codex plugin marketplace upgrade agent-data\n"
        "codex plugin add job-search@agent-data\n"
        "```\n"
    )
    r = run_validate(tmp_path, "--only", "primary-update-recipes")
    assert r.returncode == 1
    assert "claude.md" in r.stdout and "exact command lines" in r.stdout


def test_primary_update_recipes_extra_command_in_fence_fails(tmp_path):
    p = tmp_path / "shared" / "references" / "platform"
    p.mkdir(parents=True)
    (p / "claude.md").write_text(
        "## Packaging & install\n\n"
        "### Update recipe\n\n"
        "```bash\n"
        "claude plugin marketplace update agent-data\n"
        "claude plugin update job-search@agent-data\n"
        "claude plugin list\n"
        "```\n"
    )
    (p / "codex.md").write_text(
        "## Packaging & install\n\n"
        "### Update recipe\n\n"
        "```bash\n"
        "codex plugin marketplace upgrade agent-data\n"
        "codex plugin add job-search@agent-data\n"
        "```\n"
    )
    r = run_validate(tmp_path, "--only", "primary-update-recipes")
    assert r.returncode == 1
    assert "claude.md" in r.stdout and "exact command lines" in r.stdout
