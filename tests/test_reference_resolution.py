"""Per-host reference-resolution marker tests (AAS-TEST-10).

Proves the single-home cutover (belief 5): every reference a skill makes resolves IN PLACE to the one
canonical shared/references/ home, under each supported host's install view. This structural proof
REPLACES the removed byte-equality fan-out gate — the ~80 per-skill copies are gone (git rm'd) and each
skill references the single source via `../../shared/references/<file>.md` (from a SKILL.md) or
`../../../shared/references/<file>.md` (from a skill-local reference body). A dangling pointer -> RED; a
resolved pointer that lands on the marked single home -> GREEN.

Install model (STEP 0 finding, verified). Every documented distribution channel is a whole-repo
git/editable clone loaded in place — marketplace add+install (Claude/Codex/Copilot/Droid),
git-clone-and-open (Cursor), `gemini extensions install <url>`, opencode `git+https`, `pi install
git:...`/`pi -e`. The Claude marketplace install on disk (~/.claude/plugins/marketplaces/agent-data) is
a full clone that carries shared/. No manifest declares an npm-style `files` allowlist that would ship
skills/ in isolation (a `"skills": "./skills/"` field only *locates* skills within the cloned tree — it
is not a ship-restriction), and no host documents a filesystem read-scope jail confining a skill to its
own directory. So shared/ sits as a sibling of skills/ under one install root on every host, and
`../../shared/references/...` resolves. The per-host loop asserts that ships-shared property from each
manifest and would go RED for any host that ever shipped skills-only.
"""
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared" / "references"
MECH = ROOT / "shared" / "scripts" / "mechanics"
LIFECYCLE = SHARED / "run-lifecycle.md"
LIFECYCLE_LEDGER_PATH = "runs/.lifecycle-{run_id}.jsonl"
LIFECYCLE_METRICS_PATH = "{workspace}/metrics.json"

# Unique marker planted in the ONE canonical home (shared/references/conventions.md).
MARKER = "reference-resolution-marker:8f2a4c1e-single-home"

# The eight adapter hosts -> the manifest that governs each host's install. Six manifest FILES cover
# eight hosts: Copilot reuses the Claude manifest; Droid can use the Claude-compat manifest or the
# .factory-plugin one; opencode and Pi both ship via package.json.
HOST_MANIFESTS = {
    "claude": ".claude-plugin/plugin.json",
    "codex": ".codex-plugin/plugin.json",
    "cursor": ".cursor-plugin/plugin.json",
    "droid": ".factory-plugin/plugin.json",
    "gemini": "gemini-extension.json",
    "opencode": "package.json",
    "pi": "package.json",
    "copilot": ".claude-plugin/plugin.json",
}

# The four hand-authored skill-local reference ORIGINALS that legitimately remain under skills/ (no
# shared/references twin). Everything else under skills/*/references/ was a build-fanned copy and is
# gone.
SKILL_LOCAL_ORIGINALS = {
    "skills/job-search/references/home.md",
    "skills/job-search/references/onboarding.md",
    "skills/job-search-agent/references/customization.md",
    "skills/job-search-agent/references/scheduling-and-consent.md",
}

# A reference-file PATH pointer: an in-place shared ref (`../../shared/references/x.md`,
# `../../../shared/references/x.md`) or a kept skill-local ref (`references/x.md`,
# `references/platform/x.md`). A bare prose name ("conventions.md" with no directory component) is not a
# path and is intentionally NOT matched — resolution is a property of paths, not of doc-name shorthand.
_PTR = re.compile(r"(?:\.\./)*(?:shared/)?references/(?:platform/)?[A-Za-z0-9._-]+\.md")

# A mechanics-script PATH pointer the P4/T4.2 invoke-or-prose-fallback wiring makes: the in-place shared
# script (`../../shared/scripts/mechanics/x.sh` from a SKILL.md, `../scripts/mechanics/x.sh` from a
# shared/references body). The "run the shared script where a runtime exists" arm must resolve in place to
# the single scripts home — a dangling invocation would silently drop to the fallback on every host.
_SCRIPT_PTR = re.compile(r"(?:\.\./)+(?:shared/)?scripts/mechanics/[A-Za-z0-9._-]+\.sh")

LIFECYCLE_CONSUMERS = (
    ROOT / "ARCHITECTURE.md",
    SHARED / "conventions.md",
    SHARED / "internals.md",
)

LIFECYCLE_PHASES = (
    "preflight",
    "searching",
    "selection_settled",
    "reviewing_initial_batch",
    "early_results_shown",
    "reviewing_remaining",
    "finalizing",
    "complete",
)

LIFECYCLE_EVENTS = (
    "run_started",
    "phase_changed",
    "posting_state",
    "attempt_started",
    "attempt_accounted",
    "attempt_resolved",
    "brief_revision",
    "milestone",
    "run_closed",
)

LIFECYCLE_POSTING_STATES = (
    "queued",
    "evaluating",
    "evaluated",
    "presented",
    "terminally_skipped",
)

LIFECYCLE_PRESENTATION_TRANSITION = {
    "presented_identity": "same_run_id+source+source_id",
    "qualifying_job_event": "evaluated+relevant_true+nonempty_reasoning",
    "surface_proof": "rendered_relevant_posting_with_reasoning",
    "transition_order": "append_after_successful_render",
    "ledger_content": "state_transition_only",
    "reasoning_available_only": "insufficient",
    "title_only_render": "insufficient",
    "scheduled_or_canary": "no_interactive_presented_transition",
}

LIFECYCLE_CLOSE_STATES = (
    "complete",
    "blocked",
    "interrupted",
)

LIFECYCLE_METRICS = (
    "onboarding_started_at",
    "agent_data_ready_at",
    "first_live_call_at",
    "first_relevant_match_ready_at",
    "early_results_shown_at",
    "run_completed_at",
    "schedule_verified_at",
)

LIFECYCLE_LEDGER = {
    "path": LIFECYCLE_LEDGER_PATH,
    "write_mode": "append_only",
    "visibility": "hidden",
    "writer": "coordinator_only",
}

LIFECYCLE_INVARIANTS = {
    "presented_counts_as_evaluated": "true",
    "presented_counts_as_presented": "true",
    "early_results_terminal": "false",
    "blocked_counts_as_complete": "false",
    "interrupted_counts_as_complete": "false",
}

LIFECYCLE_COMPLETION_CLAUSES = {
    "remaining_zero": "remaining=0",
    "in_flight_zero": "in_flight=0",
    "selected_settled": "selected=evaluated+terminally_skipped",
    "all_started_attempts_accounted": "each_attempt_started_has_exactly_one_attempt_accounted",
    "no_blocking_attempt_failure": "no_permanent_or_unresolved_attempt_failure",
    "final_run_record_written": "runs/{run_id}.json",
    "final_digest_written": "reports/{ISO-date}-digest.md",
    "ledger_closed_complete": "closed_with_complete_state",
}

LIFECYCLE_RECOVERY = {
    "closed": "do_not_append_or_replay",
    "open_after_selection_settled": "resume_queued_and_reconcile_evaluating",
    "open_before_selection_settled": "close_interrupted_and_restart_with_fresh_call_context",
}

LIFECYCLE_SEARCH_STATE = {
    "cursor_persistence": "prohibited",
    "cursor_reconstruction": "prohibited",
    "cursor_reuse": "prohibited",
    "search_restart": "clean_required",
    "pagination_scratch": "separate_non_resumable",
}

LIFECYCLE_PROHIBITED_FIELDS = {
    "api_keys",
    "auth_headers",
    "environment_dumps",
    "pagination_cursors",
    "opaque_api_continuation_tokens",
    "full_job_descriptions",
    "preferences_text",
    "match_prose",
}

LIFECYCLE_METRIC_PROPERTIES = {
    "path": LIFECYCLE_METRICS_PATH,
    "local_only": "true",
    "pii_allowed": "false",
    "telemetry_enabled": "false",
    "write_mode": "atomic_whole_file",
}

LIFECYCLE_METRIC_DOCUMENT = {
    "version": "1",
    "required_root_keys": "version,active_setup_id,setups",
    "record_container": "setups[]",
    "active_selector": "active_setup_id",
    "record_identity": "setup_id",
    "identity_format": "setup-{uuid_v4_lowercase}",
    "timestamp_scope": "per_setup_record",
    "unobserved_timestamps": "omitted",
}

LIFECYCLE_METRIC_OWNERS = {
    "onboarding_started_at": "front_door",
    "agent_data_ready_at": "front_door",
    "first_live_call_at": "runner",
    "first_relevant_match_ready_at": "runner",
    "early_results_shown_at": "runner",
    "run_completed_at": "runner",
    "schedule_verified_at": "schedule_setup",
}

LIFECYCLE_METRIC_WRITE_RULES = {
    "timestamp_writer": "owner_only",
    "first_observation": "write_once",
    "existing_timestamp": "preserve_exactly",
    "setup_id": "immutable",
    "new_onboarding_attempt": "append_new_setup_record",
    "historical_setup_records": "never_overwrite_or_delete",
}

LIFECYCLE_ACTIVATION = {
    "persisted": "false",
    "run_health": "not_blocked",
    "fully_evaluated_postings": "at_least_one",
    "relevant_matches_shown_with_reasoning": "at_least_one_valid_presented_transition",
}

LIFECYCLE_DERIVED_DURATIONS = {
    "time_to_help": "onboarding_started_at->early_results_shown_at",
    "first_match_review_latency": "first_live_call_at->first_relevant_match_ready_at",
    "total_run_time": "first_live_call_at->run_completed_at",
}

LIFECYCLE_COMPLETION_SIGNATURE = {
    "remaining=0",
    "in_flight=0",
    "selected=evaluated+terminally_skipped",
    "attempt_started",
    "attempt_accounted",
    "runs/{run_id}.json",
    "reports/{ISO-date}-digest.md",
}

LIFECYCLE_COMPLETION_MARKED_TOKENS = (
    set(LIFECYCLE_COMPLETION_CLAUSES) | set(LIFECYCLE_COMPLETION_CLAUSES.values())
)

LIFECYCLE_OWNER_CONTRACT_GROUPS = (
    set(LIFECYCLE_PHASES),
    set(LIFECYCLE_EVENTS),
    set(LIFECYCLE_POSTING_STATES),
    set(LIFECYCLE_PRESENTATION_TRANSITION) | set(LIFECYCLE_PRESENTATION_TRANSITION.values()),
    set(LIFECYCLE_CLOSE_STATES),
    set(LIFECYCLE_METRICS),
    LIFECYCLE_COMPLETION_SIGNATURE,
    LIFECYCLE_COMPLETION_MARKED_TOKENS,
    set(LIFECYCLE_METRIC_DOCUMENT) | set(LIFECYCLE_METRIC_DOCUMENT.values()),
    set(LIFECYCLE_METRIC_OWNERS) | set(LIFECYCLE_METRIC_OWNERS.values()),
    set(LIFECYCLE_METRIC_WRITE_RULES) | set(LIFECYCLE_METRIC_WRITE_RULES.values()),
    set(LIFECYCLE_ACTIVATION) | set(LIFECYCLE_ACTIVATION.values()),
    set(LIFECYCLE_DERIVED_DURATIONS) | set(LIFECYCLE_DERIVED_DURATIONS.values()),
)


def _contract_block(text, name):
    """Body between stable owner-only lifecycle contract markers."""
    pattern = (
        rf"<!-- lifecycle-contract:{re.escape(name)} -->\s*"
        rf"(?P<body>.*?)\s*<!-- /lifecycle-contract:{re.escape(name)} -->"
    )
    match = re.search(pattern, text, re.DOTALL)
    assert match, f"run-lifecycle.md is missing the {name!r} semantic contract block"
    return match.group("body")


def _contract_list(text, name):
    """Normalized first code token from each list row in a marked contract block."""
    block = _contract_block(text, name)
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    assert lines, f"the {name!r} semantic contract list is empty"
    tokens = []
    for line in lines:
        match = re.fullmatch(r"(?:\d+\.|-)\s+`([^`]+)`(?:\s+.*)?", line)
        assert match, f"the {name!r} semantic contract has a malformed list row: {line!r}"
        tokens.append(match.group(1))
    assert len(tokens) == len(set(tokens)), (
        f"the {name!r} semantic contract has a duplicate list token: {tokens}")
    return tuple(tokens)


def _contract_table(text, name):
    """Normalized key/value code cells from a marked Markdown table."""
    block = _contract_block(text, name)
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    assert len(lines) >= 3, f"the {name!r} semantic contract table has no data rows"
    assert re.fullmatch(r"\|[^|]+\|[^|]+\|", lines[0]), (
        f"the {name!r} semantic contract has a malformed table header")
    assert re.fullmatch(r"\|\s*:?-+:?\s*\|\s*:?-+:?\s*\|", lines[1]), (
        f"the {name!r} semantic contract has a malformed table separator")
    rows = []
    for line in lines[2:]:
        match = re.fullmatch(r"\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|", line)
        assert match, f"the {name!r} semantic contract has a malformed table row: {line!r}"
        rows.append(match.groups())
    keys = [key for key, _ in rows]
    assert len(keys) == len(set(keys)), (
        f"the {name!r} semantic contract has a duplicate table key: {keys}")
    return dict(rows)


def _contract_token_groups(text):
    """Normalized code tokens from bounded contract-like Markdown blocks, never the whole file."""
    groups = []
    for block in re.split(r"\n\s*\n", text):
        code_tokens = re.findall(r"`([^`]+)`", block)
        structural = any(re.match(r"^\s*(?:\d+\.|-|\|)", line)
                         for line in block.splitlines())
        if code_tokens and (structural or len(code_tokens) >= 2):
            groups.append({re.sub(r"\s+", "", token) for token in code_tokens})
    return groups


def _pointer_files():
    """Files whose reference pointers must resolve: every SKILL.md + the four skill-local originals."""
    files = sorted((ROOT / "skills").glob("*/SKILL.md"))
    files += [ROOT / rel for rel in sorted(SKILL_LOCAL_ORIGINALS)]
    return files


def _pointers(path):
    """Distinct reference-path pointers found in `path` (globs excluded)."""
    out = []
    for m in _PTR.finditer(path.read_text(encoding="utf-8")):
        tok = m.group(0)
        if "*" not in tok and tok not in out:
            out.append(tok)
    return out


def _ships_shared(manifest_rel):
    """Model, from a manifest, whether the host's install ships shared/ reachably from skills/.

    Every documented install is a whole-repo clone loaded in place, so shared/ is a sibling of skills/.
    The only thing that could break that is an npm-style `files` allowlist omitting shared/ — none use
    one. A `skills` pointer selects where skills live in the cloned tree; it is NOT a ship-restriction.
    Returns (ok, reason)."""
    path = ROOT / manifest_rel
    if not path.is_file():
        return False, f"manifest {manifest_rel} is missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return False, f"manifest {manifest_rel} is not valid JSON: {e}"
    files = data.get("files")
    if isinstance(files, list) and not any("shared" in str(f) for f in files):
        return False, f"manifest {manifest_rel} `files` allowlist would not ship shared/"
    return True, ""


@pytest.mark.parametrize("host", sorted(HOST_MANIFESTS))
def test_every_reference_resolves_in_place_on_host(host):
    ok, reason = _ships_shared(HOST_MANIFESTS[host])
    assert ok, f"{host}: {reason}"
    # Whole-tree in-place clone: the install root places skills/ and shared/ as siblings (== repo root).
    install_root = ROOT
    assert (install_root / "shared" / "references").is_dir(), f"{host}: shared/references not shipped"
    for f in _pointer_files():
        for ptr in _pointers(f):
            target = (f.parent / ptr).resolve()
            assert target.exists(), (
                f"{host}: {f.relative_to(ROOT)} -> `{ptr}` is DANGLING (no {target})")
            if "shared/references" in ptr:
                # an in-place shared pointer must land inside the single home
                assert target.parent == SHARED or SHARED in target.parents, (
                    f"{host}: {f.relative_to(ROOT)} -> `{ptr}` does not land in shared/references")
            else:
                # a skill-local pointer may only reach one of the four kept originals
                assert target.relative_to(ROOT).as_posix() in SKILL_LOCAL_ORIGINALS, (
                    f"{host}: {f.relative_to(ROOT)} -> `{ptr}` is a skill-local pointer that is not "
                    f"one of the four kept originals")


def test_marker_present_in_single_home():
    assert MARKER in (SHARED / "conventions.md").read_text(encoding="utf-8"), (
        "the resolution marker was removed from shared/references/conventions.md")


@pytest.mark.parametrize("host", sorted(HOST_MANIFESTS))
def test_every_skill_reaches_the_marked_home_on_host(host):
    """Positive proof that resolution lands on the ONE marked source, not a stray copy: each of the five
    skills' SKILL.md reaches shared/references/conventions.md in place, and that file carries the marker."""
    ok, reason = _ships_shared(HOST_MANIFESTS[host])
    assert ok, f"{host}: {reason}"
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        reached = False
        for ptr in _pointers(skill_md):
            if ptr.endswith("shared/references/conventions.md"):
                target = (skill_md.parent / ptr).resolve()
                assert target.exists(), f"{host}: {skill_md.relative_to(ROOT)} -> `{ptr}` dangling"
                assert MARKER in target.read_text(encoding="utf-8"), (
                    f"{host}: {skill_md.relative_to(ROOT)} -> `{ptr}` did not reach the marked home")
                reached = True
        assert reached, (
            f"{host}: {skill_md.relative_to(ROOT)} makes no in-place conventions.md pointer to the "
            f"single home")


def test_no_fanned_reference_copy_remains():
    """The fan-out is gone: the only *.md under skills/*/references/ are the four skill-local originals
    (no shared-twin copy, no references/platform/ adapter copy)."""
    present = set()
    for refs in (ROOT / "skills").glob("*/references"):
        for p in refs.rglob("*.md"):
            present.add(p.relative_to(ROOT).as_posix())
    fanned = sorted(present - SKILL_LOCAL_ORIGINALS)
    assert not fanned, f"fanned reference copies still present (must be single-homed): {fanned}"


def test_run_lifecycle_contract_is_single_homed_and_consumed():
    """T1.1: the lifecycle schema has one shared owner and every architecture/reference consumer links it."""
    assert LIFECYCLE.is_file(), "shared/references/run-lifecycle.md is the required single contract home"

    for consumer in LIFECYCLE_CONSUMERS:
        consumer_text = consumer.read_text(encoding="utf-8")
        targets = re.findall(r"\[[^]]+\]\(([^)#]+\.md)\)", consumer_text)
        resolved = {(consumer.parent / target).resolve() for target in targets}
        assert LIFECYCLE.resolve() in resolved, (
            f"{consumer.relative_to(ROOT)} must link to shared/references/run-lifecycle.md")

        assert "<!-- lifecycle-contract:" not in consumer_text, (
            f"{consumer.relative_to(ROOT)} duplicates an owner-only semantic contract marker")
        assert LIFECYCLE_LEDGER_PATH not in consumer_text, (
            f"{consumer.relative_to(ROOT)} duplicates the lifecycle ledger path")
        assert LIFECYCLE_METRICS_PATH not in consumer_text, (
            f"{consumer.relative_to(ROOT)} duplicates the lifecycle metrics path")
        consumer_groups = _contract_token_groups(consumer_text)
        duplicated = [tokens for tokens in LIFECYCLE_OWNER_CONTRACT_GROUPS
                      if any(tokens <= group for group in consumer_groups)]
        assert not duplicated, (
            f"{consumer.relative_to(ROOT)} duplicates lifecycle contract structure: {duplicated}")


def test_lifecycle_consumer_contract_detection_is_bounded():
    expected = set(LIFECYCLE_EVENTS)
    scattered = "\n\n".join(f"Mentions `{token}` independently." for token in LIFECYCLE_EVENTS)
    assert not any(expected <= group for group in _contract_token_groups(scattered))

    grouped = "Closed vocabulary: " + ", ".join(f"`{token}`" for token in LIFECYCLE_EVENTS)
    assert any(expected <= group for group in _contract_token_groups(grouped))


def test_lifecycle_contract_list_parser_rejects_duplicate_rows():
    duplicate = """<!-- lifecycle-contract:duplicate-list -->
- `same`
- `same`
<!-- /lifecycle-contract:duplicate-list -->"""
    with pytest.raises(AssertionError, match="duplicate"):
        _contract_list(duplicate, "duplicate-list")


@pytest.mark.parametrize("second_value", ("same", "conflict"))
def test_lifecycle_contract_table_parser_rejects_duplicate_keys(second_value):
    duplicate = f"""<!-- lifecycle-contract:duplicate-table -->
| Key | Value |
|---|---|
| `same` | `same` |
| `same` | `{second_value}` |
<!-- /lifecycle-contract:duplicate-table -->"""
    with pytest.raises(AssertionError, match="duplicate"):
        _contract_table(duplicate, "duplicate-table")


def test_run_lifecycle_contract_has_stable_vocabulary():
    text = LIFECYCLE.read_text(encoding="utf-8")

    assert _contract_table(text, "ledger") == LIFECYCLE_LEDGER
    assert _contract_list(text, "phases") == LIFECYCLE_PHASES
    assert set(_contract_list(text, "events")) == set(LIFECYCLE_EVENTS)
    assert set(_contract_list(text, "posting-states")) == set(LIFECYCLE_POSTING_STATES)
    assert set(_contract_list(text, "close-states")) == set(LIFECYCLE_CLOSE_STATES)
    assert set(_contract_list(text, "metric-timestamps")) == set(LIFECYCLE_METRICS)


def test_run_lifecycle_contract_pins_rendered_presentation_transition():
    text = LIFECYCLE.read_text(encoding="utf-8")

    assert _contract_table(text, "presentation-transition") == LIFECYCLE_PRESENTATION_TRANSITION


def test_run_lifecycle_contract_pins_completion_recovery_and_privacy():
    text = LIFECYCLE.read_text(encoding="utf-8")

    assert _contract_table(text, "invariants") == LIFECYCLE_INVARIANTS
    assert _contract_table(text, "completion") == LIFECYCLE_COMPLETION_CLAUSES
    assert _contract_table(text, "recovery") == LIFECYCLE_RECOVERY
    assert _contract_table(text, "search-state") == LIFECYCLE_SEARCH_STATE
    assert set(_contract_list(text, "persistence-prohibitions")) == LIFECYCLE_PROHIBITED_FIELDS
    assert _contract_table(text, "metric-properties") == LIFECYCLE_METRIC_PROPERTIES


def test_run_lifecycle_contract_pins_metric_ownership_activation_and_durations():
    text = LIFECYCLE.read_text(encoding="utf-8")

    assert _contract_table(text, "metric-document") == LIFECYCLE_METRIC_DOCUMENT
    assert _contract_table(text, "metric-owners") == LIFECYCLE_METRIC_OWNERS
    assert _contract_table(text, "metric-write-rules") == LIFECYCLE_METRIC_WRITE_RULES
    assert _contract_table(text, "activation") == LIFECYCLE_ACTIVATION
    assert _contract_table(text, "derived-durations") == LIFECYCLE_DERIVED_DURATIONS


# ------------------------------------------------------ mechanics-script resolution (P4/T4.2)

def _script_pointer_files():
    """Files that invoke a mechanics script: every SKILL.md + every shared/references body (the
    invoke-or-prose-fallback wiring lives in the runner and in the contracts it defers to)."""
    files = sorted((ROOT / "skills").glob("*/SKILL.md"))
    files += sorted(SHARED.glob("*.md"))
    return files


def _script_pointers(path):
    """Distinct mechanics-script PATH pointers found in `path`."""
    out = []
    for m in _SCRIPT_PTR.finditer(path.read_text(encoding="utf-8")):
        tok = m.group(0)
        if tok not in out:
            out.append(tok)
    return out


@pytest.mark.parametrize("host", sorted(HOST_MANIFESTS))
def test_every_mechanics_script_resolves_in_place_on_host(host):
    """P4/T4.2: the 'run the shared script' arm of each invoke-or-prose-fallback must resolve IN PLACE to
    the single mechanics home on every host — the same ships-shared property the references rely on. A
    dangling script pointer -> RED (the runtime arm would never fire)."""
    ok, reason = _ships_shared(HOST_MANIFESTS[host])
    assert ok, f"{host}: {reason}"
    assert MECH.is_dir(), f"{host}: shared/scripts/mechanics not shipped"
    any_ptr = False
    for f in _script_pointer_files():
        for ptr in _script_pointers(f):
            any_ptr = True
            target = (f.parent / ptr).resolve()
            assert target.exists(), (
                f"{host}: {f.relative_to(ROOT)} -> `{ptr}` is DANGLING (no {target})")
            assert target.parent == MECH, (
                f"{host}: {f.relative_to(ROOT)} -> `{ptr}` does not land in shared/scripts/mechanics")
    assert any_ptr, (
        f"{host}: no mechanics-script pointer found in any SKILL.md or shared/references body — the "
        f"P4/T4.2 invoke-or-prose-fallback wiring is missing")


# ------------------------------------------------------ internal reference maps (AAS-BOUND-05)

MAPPED_REFERENCES = (
    "shared/references/conventions.md",
    "shared/references/errors.md",
    "shared/references/internals.md",
    "shared/references/run-lifecycle.md",
    "shared/references/voice.md",
    "shared/references/parallelism.md",
    "shared/references/query-strategy.md",
    "shared/references/agent-data-contract.md",
    "skills/job-search-agent/references/scheduling-and-consent.md",
)


def test_every_large_reference_carries_an_internal_map():
    """AAS-BOUND-05: a reference over ~100 lines gets a ToC so a partial read reveals its scope."""
    for rel in MAPPED_REFERENCES:
        path = ROOT / rel
        lines = path.read_text(encoding="utf-8").split("\n")
        assert len(lines) > 100, f"{rel} is no longer large; drop it from MAPPED_REFERENCES"
        head = "\n".join(lines[:6])
        assert "**Contents:**" in head, f"{rel} has no `**Contents:**` map in its first 6 lines"
        anchors = [a for a in re.findall(r"\]\(#([a-z0-9_-]+)\)", head)]
        assert len(anchors) >= 3, f"{rel} map has {len(anchors)} anchors; expected one per `##` section"
        slugs = {
            re.sub(r"[^a-z0-9 _-]", "", m.group(1).lower()).replace(" ", "-")
            for m in re.finditer(r"^## (.+)$", path.read_text(encoding="utf-8"), re.M)
        }
        for anchor in anchors:
            assert anchor in slugs, f"{rel} map anchor #{anchor} matches no `##` heading"
