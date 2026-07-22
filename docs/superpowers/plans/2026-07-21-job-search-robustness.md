# Job Search Robustness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve user must-haves through retrieval and judgment, enforce runner/evaluator ownership, reject noncanonical artifacts, and prove the complete first-run workflow with executed behavioral evidence.

**Architecture:** Keep `preferences.md` as the prose source of truth, bind config v3 to an immutable search-plan receipt, and require a complete must-have evidence matrix for every semantic verdict. Refactor `job-search-run` into a ≤2,500-word phase router with one-hop, just-in-time references; deterministic validators own schema/binding/bundle checks while skills retain qualitative judgment and an explicit no-runtime prose fallback.

**Tech Stack:** Markdown skill/reference contracts, JSON/JSONL, the repository's constrained YAML subset, POSIX `sh`, Python 3.11 standard library for structured validators and developer harnesses, pytest, fake agent-data/host/lifecycle fixtures.

## Global Constraints

- Implementation baseline is commit `01fcbef`; review runtime changes with `git diff 01fcbef...HEAD`.
- `preferences.md` remains prose; no numeric fit score, weights, or category arithmetic may be added.
- Must-have assessments are exactly `met | unclear | conflicts`; `strong` requires all must-haves `met`.
- An `unclear` must-have normally excludes a posting; a relevant override is at most `moderate`, requires `needs_human_check:true`, and carries nonempty `why_still_plausible`.
- Strong preferences rank already-relevant roles and never compensate for a conflicting must-have.
- `job-search` owns setup/presentation, `job-search-run` owns posting calls/run artifacts, and `evaluate-job-fit` owns semantic verdicts.
- No metered posting call occurs before config, search-plan, preferences fingerprint, and lifecycle preflight pass.
- Search queries remain frozen during a run; no hidden broadening, limit increase, or fallback query is permitted.
- `skills/job-search-run/SKILL.md` must contain no more than 2,500 words; shorter is acceptable.
- Each runner phase reference must contain no more than 2,000 words; `attempt-accounting.md` must contain no more than 1,000 words; the entrypoint plus preflight and attempt-accounting load must contain no more than 4,500 words before the first external attempt.
- Every load-bearing reference is linked directly from its owning `SKILL.md`; phase references do not route to second-hop material.
- Runtime validation uses no third-party package. Standard-library Python validators have a named, separately tested prose fallback when Python is unavailable.
- Static eval validation proves scenario coherence only. Executed skill runs with traces/artifacts are required release evidence.
- Config v1 and v2 workspaces migrate interactively to v3; no legacy version may run unbound.
- A cold post-implementation review against both private guide packs is release-blocking; P0/P1 findings cannot be waived by the controller.

---

## File Structure

### New runtime and reference files

- `shared/scripts/mechanics/search_plan_validate.py` — parse the supported config subset and validate immutable search-plan bindings.
- `shared/scripts/mechanics/search_plan_transaction.py` — journal, activate, recover, and roll back config-v3 workspace transactions.
- `shared/scripts/mechanics/verdict_validate.py` — validate evaluator envelopes and current-run evaluated events against the active plan.
- `shared/scripts/mechanics/run_bundle_validate.py` — verify ledger, run record, evaluated events, and digest form one authoritative bundle.
- `skills/job-search-run/references/preflight.md` — plan/config/model/lifecycle checks before metered work.
- `skills/job-search-run/references/attempt-accounting.md` — the single runtime point for attempt classification, retries, and quota settlement.
- `skills/job-search-run/references/retrieve.md` — frozen requests, pagination, deduplication, merging, and selection.
- `skills/job-search-run/references/evaluate.md` — evaluator delegation, exact-model dispatch, and presentation transitions.
- `skills/job-search-run/references/persist.md` — envelope validation, typed event append, aliases, and verdict provenance.
- `skills/job-search-run/references/finalize.md` — run-record/digest writes, bundle validation, closing, and surfacing.

### New test and evaluation files

- `tests/test_search_plan_mechanics.py` — config-v3 parsing, plan completeness, and binding.
- `tests/test_config_v3_migration.py` — journaled activation, rollback, crash recovery, and legacy migration.
- `tests/test_verdict_mechanics.py` — assessment/band invariants and evaluated-event schema.
- `tests/test_run_bundle_mechanics.py` — canonical bundle authority and malformed dogfood-row rejection.
- `tests/test_runner_prompt_architecture.py` — runner word budget, one-hop routing, ownership, and phase-local loading.
- `tests/test_behavioral_eval_runner.py` — executed-evidence schema, host adapter command construction, rep aggregation, and skip honesty.
- `scripts/run_behavioral_evals.py` — invoke real host CLIs, retain JSONL traces/artifacts, and emit executed-skill result evidence.
- `skills/evaluate-job-fit/evals/files/brief-web-data.md` — the dogfood preference brief.
- `skills/evaluate-job-fit/evals/files/posting-onhires.md` — direct web-data fit.
- `skills/evaluate-job-fit/evals/files/posting-rebar.md` — detailed adjacent construction-data role.
- `skills/evaluate-job-fit/evals/files/posting-cogent.md` — detailed adjacent enterprise-data role.
- `tests/fixtures/web-data-dogfood/` — deterministic retrieval/detail fixtures for direct and proxy queries.

### Existing files changed by responsibility

- Schema/semantics: `shared/references/conventions.md`, `shared/references/query-strategy.md`, `shared/references/parallelism.md`, `shared/references/run-lifecycle.md`, `shared/references/internals.md`, `shared/references/errors.md`, `templates/config.example.yaml`.
- Skill workflow: `skills/job-search/SKILL.md`, `skills/job-search/references/onboarding.md`, `skills/job-search/references/home.md`, `skills/job-search-agent/SKILL.md`, `skills/job-search-agent/references/customization.md`, `skills/evaluate-job-fit/SKILL.md`, `skills/job-search-run/SKILL.md`.
- Mechanics fixtures: `shared/scripts/mechanics/event-log-append.sh`, `tests/test_mechanics_scripts.py`, `tests/fake-host-capabilities`, `tests/fake-run-lifecycle`, `tests/fake-agent-data`, `skills/job-search-run/evals/files/setup-workspace.sh`, `tests/test_usage_context_contract.py`.
- Eval/test infrastructure: `skills/job-search/evals/evals.json`, `skills/job-search-run/evals/evals.json`, `skills/evaluate-job-fit/evals/evals.json`, `scripts/eval_harness.py`, `tests/test_eval_harness.py`, `tests/test_reference_resolution.py`, `tests/test_query_strategy_contract.py`.
- Architecture/release: `ARCHITECTURE.md`, `docs/design-docs/core-beliefs.md`, `TESTING.md`, `.github/workflows/ci.yml`, six version manifests, and `shared/references/build-stamp.md`.

---

### Task 1: Pin Config-v3, Search-plan, Verdict, and Ownership Contracts

**Files:**
- Create: `tests/test_job_search_robustness_contract.py`
- Modify: `shared/references/conventions.md:36-73,282-347,348-424,599-613`
- Modify: `shared/references/query-strategy.md:1-160`
- Modify: `templates/config.example.yaml:1-25`

**Interfaces:**
- Consumes: approved design `docs/superpowers/specs/2026-07-21-job-search-robustness-design.md`.
- Produces: marker-delimited contract tables `config-v3`, `search-plan`, `must-have-assessment`, and `ownership`; later mechanics tests parse these exact values.

- [ ] **Step 1: Write failing marked-contract tests**

```python
# tests/test_job_search_robustness_contract.py
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONVENTIONS = ROOT / "shared/references/conventions.md"
STRATEGY = ROOT / "shared/references/query-strategy.md"
TEMPLATE = ROOT / "templates/config.example.yaml"


def table(path, marker):
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- robustness-contract:{marker} -->\n(.*?)\n"
        rf"<!-- /robustness-contract:{marker} -->",
        text,
        re.S,
    )
    assert match, f"missing robustness-contract:{marker}"
    rows = {}
    for line in match.group(1).splitlines():
        if not line.startswith("|") or "---" in line or "Field" in line:
            continue
        cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        rows[cells[0]] = cells[1]
    return rows


def test_config_v3_binds_plan_and_preferences():
    assert table(CONVENTIONS, "config-v3") == {
        "version": "required_integer_3",
        "search_plan.plan_id": "required_plan_uuid_v4_lowercase",
        "search_plan.preferences_sha256": "required_sha256_colon_64_lower_hex",
        "queries[].id": "required_unique_stable_id",
        "legacy_v1_or_v2": "interactive_migration_before_run",
    }


def test_search_plan_and_verdict_vocabularies_are_closed():
    assert table(CONVENTIONS, "search-plan") == {
        "criteria": "every_must_have_verbatim_exactly_once",
        "assessment": "met_or_unclear_or_conflicts",
        "query_kind": "direct_or_proxy",
        "proxy_limit": "never_sole_coverage_when_direct_required",
        "binding": "plan_id_preferences_hash_and_request_hashes",
    }
    assert table(CONVENTIONS, "must-have-assessment") == {
        "conflicts": "relevant_false",
        "unclear_default": "not_featured",
        "unclear_override": "weak_or_moderate_with_reason_and_human_check",
        "strong": "every_must_have_met",
        "preferences": "rank_only_after_relevance",
    }


def test_ownership_contract_is_exclusive():
    assert table(CONVENTIONS, "ownership") == {
        "job-search": "setup_and_presentation_only",
        "job-search-run": "posting_calls_and_run_artifacts_only",
        "evaluate-job-fit": "semantic_judgment_only",
        "runner_unavailable": "stop_no_front_door_fallback",
        "evaluator_unavailable": "stop_no_runner_rubric",
    }


def test_template_and_strategy_name_the_new_contract():
    template = TEMPLATE.read_text(encoding="utf-8")
    assert "version: 3" in template and "search_plan:" in template
    strategy = STRATEGY.read_text(encoding="utf-8")
    assert "Broad queries cost no precision" not in strategy
    assert "direct" in strategy and "proxy" in strategy
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_job_search_robustness_contract.py`

Expected: FAIL because the four marked contracts and config-v3 template do not exist.

- [ ] **Step 3: Add the exact contract tables and schema prose**

Add to `conventions.md`:

```markdown
<!-- robustness-contract:config-v3 -->
| Field | Contract value |
|---|---|
| `version` | `required_integer_3` |
| `search_plan.plan_id` | `required_plan_uuid_v4_lowercase` |
| `search_plan.preferences_sha256` | `required_sha256_colon_64_lower_hex` |
| `queries[].id` | `required_unique_stable_id` |
| `legacy_v1_or_v2` | `interactive_migration_before_run` |
<!-- /robustness-contract:config-v3 -->

<!-- robustness-contract:search-plan -->
| Field | Contract value |
|---|---|
| `criteria` | `every_must_have_verbatim_exactly_once` |
| `assessment` | `met_or_unclear_or_conflicts` |
| `query_kind` | `direct_or_proxy` |
| `proxy_limit` | `never_sole_coverage_when_direct_required` |
| `binding` | `plan_id_preferences_hash_and_request_hashes` |
<!-- /robustness-contract:search-plan -->

<!-- robustness-contract:must-have-assessment -->
| Field | Contract value |
|---|---|
| `conflicts` | `relevant_false` |
| `unclear_default` | `not_featured` |
| `unclear_override` | `weak_or_moderate_with_reason_and_human_check` |
| `strong` | `every_must_have_met` |
| `preferences` | `rank_only_after_relevance` |
<!-- /robustness-contract:must-have-assessment -->

<!-- robustness-contract:ownership -->
| Field | Contract value |
|---|---|
| `job-search` | `setup_and_presentation_only` |
| `job-search-run` | `posting_calls_and_run_artifacts_only` |
| `evaluate-job-fit` | `semantic_judgment_only` |
| `runner_unavailable` | `stop_no_front_door_fallback` |
| `evaluator_unavailable` | `stop_no_runner_rubric` |
<!-- /robustness-contract:ownership -->
```

Change the template header to `version: 3` and add an empty `search_plan:` block whose comment says setup
inserts `plan_id` and `preferences_sha256` before activation. In `query-strategy.md`, define direct/proxy queries,
require direct coverage for protected domain lanes, and replace the absolute “Broad queries cost no
precision” with the two-sided statement that broad queries preserve judgment precision but can spend calls
and detail reads.

- [ ] **Step 4: Run focused and neighboring contract tests**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_job_search_robustness_contract.py tests/test_query_strategy_contract.py tests/test_doc_lint_intra_reference.py`

Expected: PASS.

- [ ] **Step 5: Commit the contract foundation**

```bash
git add tests/test_job_search_robustness_contract.py shared/references/conventions.md shared/references/query-strategy.md templates/config.example.yaml
git commit -m "feat(job-search): define bound search-plan contracts"
```

---

### Task 2: Implement Search-plan Validation

**Files:**
- Create: `shared/scripts/mechanics/search_plan_validate.py`
- Create: `tests/test_search_plan_mechanics.py`
- Modify: `shared/references/conventions.md:36-202,323-343`
- Modify: `tests/test_build_stamp.py:20-95`

**Interfaces:**
- Consumes: config-v3 and search-plan marked contracts from Task 1.
- Produces: `validate_workspace(config_path, preferences_path, plan_path) -> dict`; CLI subcommands `inspect`, `validate`, and `validate-candidate` emit one JSON object and exit nonzero with `search_plan_invalid` plus stable reason tokens.

- [ ] **Step 1: Write failing validator tests**

```python
# tests/test_search_plan_mechanics.py
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared/scripts/mechanics/search_plan_validate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("search_plan_validate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_rejects_omitted_must_have(tmp_path):
    module = load_module()
    config, preferences, plan = write_valid_workspace(tmp_path)
    data = json.loads(plan.read_text())
    data["criteria"].pop()
    plan.write_text(json.dumps(data) + "\n")
    assert "missing_must_have" in module.validate_workspace(config, preferences, plan)["reason_tokens"]


def test_validate_rejects_stale_preferences_and_request_hash(tmp_path):
    module = load_module()
    config, preferences, plan = write_valid_workspace(tmp_path)
    preferences.write_text(preferences.read_text() + "\n- changed\n")
    assert module.validate_workspace(config, preferences, plan)["ok"] is False
```

The helper fixtures write two must-haves including one multiline bullet, two lanes, one direct query, one
proxy query, and exact `sha256:` bindings. Add parameterized cases for duplicate criteria, unknown lane/query
references, missing direct coverage, nonempty unresolved assumptions, added/removed/renamed queries,
edited request fields, malformed YAML/JSON, symlinks, and uppercase/non-v4 plan IDs.

- [ ] **Step 2: Run the validator tests and confirm RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_search_plan_mechanics.py`

Expected: FAIL because `search_plan_validate.py` does not exist.

- [ ] **Step 3: Implement the validator's public contract**

```python
#!/usr/bin/env python3
# shared/scripts/mechanics/search_plan_validate.py
import hashlib
import json
import pathlib
import re

PLAN_ID = re.compile(
    r"plan-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
PLAN_KEYS = {
    "schema_version", "plan_id", "preferences_sha256", "criteria",
    "lanes", "query_bindings", "unresolved_assumptions",
}


def digest(payload):
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def canonical_request_hash(query):
    payload = {
        "enabled": query.get("enabled", True),
        "keywords": query["keywords"],
        "limit": query.get("limit", 25),
        "location": query.get("location"),
        "query_id": query["id"],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return digest(canonical)


def validate_workspace(config_path, preferences_path, plan_path):
    config = parse_config_v3(pathlib.Path(config_path).read_text(encoding="utf-8"))
    plan = json.loads(pathlib.Path(plan_path).read_text(encoding="utf-8"))
    preference_bytes = pathlib.Path(preferences_path).read_bytes()
    return validate_relationships(config, plan, preference_bytes)
```

Implement `extract_must_haves(text: str) -> list[str]`, `parse_config_v3(text: str) -> dict`,
`validate_relationships(config: dict, plan: dict, preference_bytes: bytes) -> dict`, and `main() -> int`.
Active receipts require exact query-ID equality, unique criterion/lane/
query IDs, every lane covered, every query mapped with nonempty rationale, direct query coverage for each
protected domain lane, exact request hashes, an exact preferences hash, and no unresolved assumptions.
Reject symlinked config, preference, or receipt inputs and any non-regular input before parsing.

- [ ] **Step 4: Add the invocation and exact prose fallback to conventions**

Document:

```text
python3 ../../shared/scripts/mechanics/search_plan_validate.py validate \
  --config "$JOB_SEARCH_WORKSPACE/config.yaml" \
  --preferences "$JOB_SEARCH_WORKSPACE/preferences.md" \
  --plan "$JOB_SEARCH_WORKSPACE/search-plans/$JOB_SEARCH_PLAN_ID.json"
```

The fallback repeats the same checks in a bounded checklist and labels run evidence `prose_fallback`; it
never writes a model-authored `validated:true` flag. Test both the Python and named fallback branches.

- [ ] **Step 5: Run mechanics, build-hash, and portability tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_search_plan_mechanics.py tests/test_build_stamp.py tests/test_reference_resolution.py`

Expected: PASS.

- [ ] **Step 6: Commit search-plan validation**

```bash
git add shared/scripts/mechanics/search_plan_validate.py shared/references/conventions.md tests/test_search_plan_mechanics.py tests/test_build_stamp.py
git commit -m "feat(job-search): validate bound search plans"
```

---

### Task 3: Migrate Config v1/v2 Workspaces to Bound Config v3

**Files:**
- Create: `shared/scripts/mechanics/search_plan_transaction.py`
- Create: `tests/test_config_v3_migration.py`
- Modify: `tests/fake-host-capabilities:45-350,1542-1655`
- Modify: `tests/test_config_v1_migration.py:34-70,216-282,507-670,970-1110`
- Modify: `shared/references/internals.md:350-562`
- Modify: `skills/job-search/references/onboarding.md:109-156,196-318`
- Modify: `skills/job-search/references/home.md:35-150,215-240`
- Modify: `skills/job-search-agent/SKILL.md:80-100,215-235`
- Modify: `skills/job-search-agent/references/customization.md`
- Modify: `skills/job-search-run/evals/files/setup-workspace.sh:1-60`
- Modify: `tests/test_usage_context_contract.py:470-675`

**Interfaces:**
- Consumes: `search_plan_validate.validate_workspace` from Task 2.
- Produces: `activate_workspace(workspace_path, candidate_config_path, candidate_binding_path, candidate_plan_path) -> dict` and `recover_workspace(workspace_path) -> dict`; fake-host operations `validate-v3-candidate`, `begin-v3-migration`, `activate-v3-bundle`, `recover-v3-migration`, `rollback-v3-migration`, and `free-preflight-v3`; interactive migration for both legacy majors.

- [ ] **Step 1: Write failing v2→v3 and v1→v3 transaction tests**

```python
# tests/test_config_v3_migration.py
def test_v2_candidate_migrates_without_changing_unrelated_bytes(tmp_path):
    workspace = seed_v2_workspace(tmp_path, sentinel='unrelated_sentinel: "preserve-me"\n')
    result = run_host(tmp_path, "happy", "activate-v3-bundle", *candidate_args(workspace))
    assert result.returncode == 0, result.stderr
    assert (workspace / "config.yaml").read_text().startswith("# migration-comment-sentinel\nversion: 3")
    assert 'unrelated_sentinel: "preserve-me"' in (workspace / "config.yaml").read_text()
    assert list((workspace / "search-plans").glob("plan-*.json"))


def test_v3_activation_failure_restores_config_binding_and_active_plan(tmp_path):
    workspace = seed_v2_workspace(tmp_path)
    before = snapshot_workspace(workspace)
    result = run_host(tmp_path, "partial-v3-activation-failure", "activate-v3-bundle", *candidate_args(workspace))
    assert result.returncode != 0
    assert snapshot_active_files(workspace) == before


@pytest.mark.parametrize("scenario", [
    "backup-failure", "plan-write-failure", "binding-write-failure",
    "config-write-failure", "activation-reread-failure",
    "crash-after-plan", "crash-after-binding", "crash-after-config",
])
def test_each_failure_stage_is_exactly_recoverable(tmp_path, scenario):
    workspace = seed_v2_workspace(tmp_path)
    before = snapshot_active_files(workspace)
    result = run_host(tmp_path, scenario, "activate-v3-bundle", *candidate_args(workspace))
    assert result.returncode != 0
    recover = run_host(tmp_path, "happy", "recover-v3-migration", workspace)
    assert recover.returncode == 0, recover.stderr
    assert snapshot_active_files(workspace) == before
    assert not list((workspace / "search-plans").glob("plan-*.json"))


def test_headless_v1_or_v2_run_blocks_before_metering(tmp_path):
    for version in (1, 2):
        workspace = seed_legacy_workspace(tmp_path / str(version), version)
        result = run_preflight(workspace)
        assert result["metered_calls"] == 0
        assert result["error"] == "config_v3_migration_required"
```

- [ ] **Step 2: Run the migration tests and confirm RED**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_config_v3_migration.py tests/test_config_v1_migration.py`

Expected: FAIL because version 3 and the new host operations are unknown.

- [ ] **Step 3: Implement a durable transaction with crash recovery**

Import the constrained parser/validator from `search_plan_validate.py`. Before mutation, validate every
candidate and atomically persist a transaction journal containing exact prior config bytes, exact prior
binding bytes, active-plan identity/bytes, candidate hashes, and the current stage:

```python
snapshot = {
    "config_b64": encode(config_bytes),
    "binding_b64": encode(binding_bytes) if binding_bytes is not None else None,
    "active_plan_id": active_plan_id,
    "active_plan_b64": encode(active_plan_bytes) if active_plan_bytes is not None else None,
    "candidate_plan_id": candidate_plan_id,
    "activation_stage": "prepared",
}
```

Use this exact order: validate candidates; snapshot exact prior state; durably write the journal; exclusively
create the immutable receipt; write a fresh binding only for v1/new setup; atomically replace config last;
reread and validate the active bundle; mark committed; remove the journal. V2→v3 preserves the existing
valid binding byte-for-byte; v1→v3 performs exact-model resolution and creates a fresh binding. Rollback
restores exact config/sidecar bytes and removes only the unbound receipt created by this transaction. A
corrupt journal fails closed. A receipt collision never overwrites bytes.

Document `transaction_prose_fallback` for hosts without Python: perform the same journal/create/readback/
config-last sequence with host-native exclusive-create and atomic-replace primitives, label it lower
assurance, and stop before activation if either primitive is unavailable. Add a behavioral fixture proving
the fallback does not mutate config before candidate validation and recovers a staged interruption.

- [ ] **Step 4: Cover the complete failure-injection and legacy matrix**

Implement fake-host scenarios `backup-failure`, `plan-write-failure`, `binding-write-failure`,
`config-write-failure`, `activation-reread-failure`, `crash-after-plan`, `crash-after-binding`, and
`crash-after-config`. Add tests for fresh→v3, direct v1→v3, direct v2→v3, exclusive-create collision,
corrupt-journal refusal, zero posting calls on every migration failure, and the rule that a search failure
after a validated commit never resurrects v1/v2.

- [ ] **Step 5: Replace migration prose and convert generated workspaces**

In `internals.md`, state that interactive setup or the next requested run migrates legacy workspaces; a
headless invocation records `config_v3_migration_required` and stops before a ledger or metered call. Preserve
the current exact-model binding rules, but make config, binding sidecar, and search plan one candidate
transaction. In onboarding, fresh workspaces start at v3 and activate the plan before the live sample run.
Update `setup-workspace.sh` to generate a complete valid v3 bundle; legacy tests construct v1/v2 explicitly.
Change the unsupported-newer-version fixture from v3 to v4.

- [ ] **Step 6: Make preference and query edits binding-aware**

Update home/operator/customization guidance and contract tests with this exact classification: changing query
ID, keywords, location, limit, or enabled state requires a newly reviewed receipt and atomic rebinding;
editing `preferences.md` immediately makes the current receipt stale; changing sources, freshness, schedule,
review depth, parallelism, or detail model preserves the receipt. Direct manual semantic edits are detected
at preflight and never silently rehashed.

- [ ] **Step 7: Run migration, model-binding, and onboarding structural tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_config_v3_migration.py tests/test_config_v1_migration.py tests/test_exact_model_repair.py tests/test_usage_context_contract.py tests/test_eval_harness.py`

Expected: PASS.

- [ ] **Step 8: Commit config-v3 migration**

```bash
git add shared/scripts/mechanics/search_plan_transaction.py tests/test_config_v3_migration.py tests/test_config_v1_migration.py tests/fake-host-capabilities shared/references/internals.md skills/job-search/references/onboarding.md skills/job-search/references/home.md skills/job-search-agent/SKILL.md skills/job-search-agent/references/customization.md skills/job-search-run/evals/files/setup-workspace.sh tests/test_usage_context_contract.py
git commit -m "feat(job-search): migrate workspaces to config v3"
```

---

### Task 4: Make Must-have Evidence Non-omissible and Verdicts Self-consistent

**Files:**
- Create: `shared/scripts/mechanics/verdict_validate.py`
- Create: `tests/test_verdict_mechanics.py`
- Modify: `skills/evaluate-job-fit/SKILL.md:21-76`
- Modify: `shared/references/parallelism.md:55-140`
- Modify: `shared/references/conventions.md:282-347,599-613`
- Modify: `skills/evaluate-job-fit/evals/evals.json`

**Interfaces:**
- Consumes: active plan criteria from Task 2.
- Produces: `validate_verdict(plan, verdict, event_mode=False) -> list[str]`; delegated evaluator returns one raw envelope containing `must_have_assessments` and no prose wrapper.

- [ ] **Step 1: Write failing verdict invariant tests**

```python
# tests/test_verdict_mechanics.py
def test_strong_rejects_any_unclear_must_have(plan):
    verdict = valid_verdict(match="strong")
    verdict["must_have_assessments"][0]["assessment"] = "unclear"
    verdict["needs_human_check"] = True
    assert "strong requires every must-have to be met" in validate(plan, verdict)


def test_unclear_relevant_requires_plausibility_and_caps_band(plan):
    verdict = valid_verdict(match="moderate")
    verdict["must_have_assessments"][0]["assessment"] = "unclear"
    verdict["why_still_plausible"] = ""
    assert "why_still_plausible" in validate(plan, verdict)


def test_conflict_forces_rejection(plan):
    verdict = valid_verdict(match="weak")
    verdict["must_have_assessments"][0]["assessment"] = "conflicts"
    assert "conflicts requires relevant false" in validate(plan, verdict)


def test_every_plan_criterion_appears_once(plan):
    verdict = valid_verdict()
    verdict["must_have_assessments"].pop()
    assert "exactly once" in validate(plan, verdict)


def test_non_relevant_verdict_has_no_match_band(plan):
    verdict = valid_verdict(match="weak")
    verdict["relevant"] = False
    assert "non-relevant verdict requires match null" in validate(plan, verdict)
```

- [ ] **Step 2: Run the verdict tests and confirm RED**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_verdict_mechanics.py`

Expected: FAIL because `verdict_validate.py` does not exist.

- [ ] **Step 3: Implement the validator**

```python
#!/usr/bin/env python3
# shared/scripts/mechanics/verdict_validate.py
ASSESSMENTS = {"met", "unclear", "conflicts"}
BANDS = {"strong", "moderate", "weak"}


def validate_verdict(plan, verdict, event_mode=False):
    errors = []
    expected = [row["criterion_id"] for row in plan["criteria"]]
    rows = verdict.get("must_have_assessments")
    ids = [row.get("criterion_id") for row in rows] if isinstance(rows, list) else []
    if ids != expected:
        errors.append("every plan must-have must appear exactly once and in plan order")
        return errors
    for row in rows:
        if row.get("assessment") not in ASSESSMENTS:
            errors.append("assessment must be met, unclear, or conflicts")
        if not row.get("evidence") or not all(isinstance(x, str) and x.strip() for x in row["evidence"]):
            errors.append("every assessment needs posting evidence")
        if not isinstance(row.get("explanation"), str) or not row["explanation"].strip():
            errors.append("every assessment needs an explanation")
    states = [row["assessment"] for row in rows]
    relevant, match = verdict.get("relevant"), verdict.get("match")
    if "conflicts" in states and (relevant is not False or match is not None):
        errors.append("conflicts requires relevant false and match null")
    if relevant is True and "unclear" in states:
        if match not in {"moderate", "weak"}:
            errors.append("an unclear relevant verdict is at most moderate")
        if verdict.get("needs_human_check") is not True:
            errors.append("an unclear relevant verdict needs human confirmation")
        if not str(verdict.get("why_still_plausible", "")).strip():
            errors.append("why_still_plausible is required for an unclear relevant verdict")
    if match == "strong" and any(state != "met" for state in states):
        errors.append("strong requires every must-have to be met")
    if relevant is False and match is not None:
        errors.append("non-relevant verdict requires match null")
    errors.extend(validate_derived_fields(verdict, rows))
    if event_mode:
        errors.extend(validate_event_identity(verdict))
    return errors
```

The CLI reads one JSON object from stdin, loads `--plan`, accepts optional `--event`, prints
`{"ok":true}` only after validation, and exits nonzero with a JSON error list otherwise.
Document and test `verdict_prose_fallback`: the runner applies the same finite invariant checklist, records
the lower evidence tier, and never converts the evaluator's own `validated` claim into authority.

- [ ] **Step 4: Rewrite evaluator instructions around the evidence matrix**

Put the delegated branch before interactive output. Delete the fenced pseudo-JSON with comments. Use one
field table and this exact decision sequence: assess every must-have; conflicts reject; unclear normally
excludes; an evidence-backed override is weak/moderate; only all-met can be strong; then apply strong
preferences. `parallelism.md` owns the raw envelope and forbids band words in coordinator steers.

- [ ] **Step 5: Add contrastive evaluator scenarios**

Add stochastic cases for an early-stage role with an unclear web-data must-have and a detailed role that
conflicts through an adjacent data domain. Assert the assessment matrix and upper-bound invariants, not an
exact phrase in reasoning.

- [ ] **Step 6: Run evaluator, mechanics, and eval-structure tests**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_verdict_mechanics.py tests/test_eval_harness.py tests/test_doc_lint.py`

Expected: PASS.

- [ ] **Step 7: Commit fit-evidence enforcement**

```bash
git add shared/scripts/mechanics/verdict_validate.py tests/test_verdict_mechanics.py skills/evaluate-job-fit/SKILL.md skills/evaluate-job-fit/evals/evals.json shared/references/parallelism.md shared/references/conventions.md
git commit -m "feat(job-search): require must-have evidence for verdicts"
```

---

### Task 5: Reject Untyped Events and Require an Authoritative Run Bundle

**Files:**
- Create: `shared/scripts/mechanics/run_bundle_validate.py`
- Create: `tests/test_run_bundle_mechanics.py`
- Modify: `shared/scripts/mechanics/event-log-append.sh:1-70`
- Modify: `tests/test_mechanics_scripts.py:20-45,250-350,1660-1680`
- Modify: `tests/fake-run-lifecycle:244-480,1080-1710`
- Modify: `shared/references/conventions.md:282-347,348-598,614-670`
- Modify: `shared/references/run-lifecycle.md`

**Interfaces:**
- Consumes: `verdict_validate.py --event --plan PLAN` and `lifecycle-fold.sh`.
- Produces: `event-log-append.sh JOBS PLAN` for evaluated events; `run_bundle_validate.py WORKSPACE RUN_ID` emits `{"ok":true,"run_id":"20260721T120000Z-abcd1234"}` only for authoritative bundles.

- [ ] **Step 1: Add exact malformed-row and bundle RED tests**

```python
def test_dogfood_row_without_event_is_rejected_atomically(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    row = {
        "source": "linkedin", "source_id": "jp_990514091fdc",
        "title": "Software Engineer, Data Platform", "company_name": "Rebar",
        "source_url": "https://example.test", "status": "new",
        "needs_human_check": True,
    }
    result = run_append(jobs, valid_plan(tmp_path), row)
    assert result.returncode != 0
    assert not jobs.exists() or jobs.read_bytes() == b""


def test_bundle_rejects_digest_without_closed_ledger(tmp_path):
    workspace, run_id = write_complete_bundle(tmp_path, close_ledger=False)
    result = run_bundle_validator(workspace, run_id)
    assert result.returncode != 0


def test_bundle_rejects_digest_band_drift(tmp_path):
    workspace, run_id = write_complete_bundle(tmp_path)
    digest = workspace / "reports/2026-07-21-digest.md"
    digest.write_text(digest.read_text().replace("## Moderate matches", "## Strong matches"))
    assert run_bundle_validator(workspace, run_id).returncode != 0
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_run_bundle_mechanics.py tests/test_mechanics_scripts.py -k 'event_log or bundle'`

Expected: FAIL because untyped rows still append and no bundle validator exists.

- [ ] **Step 3: Make event-log append closed and plan-aware**

At the top of `event-log-append.sh`, require `event` exactly once and allow only `evaluated` or
`status_changed`. For `evaluated`, require the second `PLAN` argument and run:

```sh
printf '%s\n' "$ev" | python3 "$script_dir/verdict_validate.py" --plan "$plan" --event \
  || { echo 'event-log-append: evaluated event failed structured validation' >&2; exit 1; }
```

Keep the existing same-source idempotency after validation. A Python-unavailable exit is a named
`structured_validator_unavailable` branch; the runner may use the exact prose fallback but cannot treat the
script failure as a successful append.

- [ ] **Step 4: Implement bundle validation**

```python
def validate_bundle(workspace, run_id):
    errors = []
    folded = fold_lifecycle(workspace, run_id)
    if folded.get("closed") != "true" or folded.get("can_complete") != "true":
        errors.append("lifecycle ledger is not closed complete")
    record = read_json(workspace / "runs" / f"{run_id}.json", errors)
    events = read_jsonl(workspace / "jobs.jsonl", errors)
    digest = workspace / "reports" / f"{run_id[:10]}-digest.md"
    if record.get("run_id") != run_id or f"Run ID: {run_id}" not in digest.read_text():
        errors.append("run record and digest do not identify the same run")
    plan_id = record.get("plan_id")
    plan = read_json(workspace / "search-plans" / f"{plan_id}.json", errors)
    current = [row for row in events if row.get("event") == "evaluated" and row.get("run_id") == run_id]
    for row in current:
        errors.extend(validate_verdict(plan, row, event_mode=True))
    errors.extend(validate_counts_and_bands(record, current, digest))
    return errors
```

Port the already-tested run-record, alias, source-evidence, and count invariants from
`tests/fake-run-lifecycle` into the runtime validator, then make the fake lifecycle call the production
validator rather than maintaining a divergent second schema.
Document `bundle_prose_fallback` with the same closed-ledger/join/count/band checks. If a required artifact
cannot be parsed or joined, the fallback blocks success; validator absence is never authority.

- [ ] **Step 5: Update canonical artifact prose**

Add `plan_id`, `preferences_sha256`, and `evaluator_contract_version:1` to evaluated events and run
records. State that the digest renders only validated event bands and cannot upgrade a verdict. Update the
append fallback to include every required field rather than an ellipsis-shaped ad hoc row.

- [ ] **Step 6: Run mechanics, lifecycle, and recovery suites**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_run_bundle_mechanics.py tests/test_mechanics_scripts.py tests/test_run_lifecycle_pressure.py`

Expected: PASS.

- [ ] **Step 7: Commit artifact authority**

```bash
git add shared/scripts/mechanics/run_bundle_validate.py shared/scripts/mechanics/event-log-append.sh tests/test_run_bundle_mechanics.py tests/test_mechanics_scripts.py tests/fake-run-lifecycle shared/references/conventions.md shared/references/run-lifecycle.md
git commit -m "feat(job-search): fail closed on invalid run artifacts"
```

---

### Task 6: Enforce Front-door Ownership and Build Bound Search Plans

**Files:**
- Modify: `skills/job-search/SKILL.md:11-95`
- Modify: `skills/job-search/references/onboarding.md:129-335,491-525`
- Modify: `shared/references/query-strategy.md`
- Modify: `skills/job-search/evals/evals.json`
- Modify: `tests/test_query_strategy_contract.py`

**Interfaces:**
- Consumes: config-v3 activation from Tasks 2–3 and direct/proxy strategy from Task 1.
- Produces: front-door runner handoff; onboarding search-plan draft with verbatim criteria, lanes, query bindings, semantic review result, and immutable activation.

- [ ] **Step 1: Write failing ownership and plan-shape assertions**

Add to `tests/test_job_search_robustness_contract.py`:

```python
def test_front_door_exclusively_delegates_live_runs():
    text = (ROOT / "skills/job-search/SKILL.md").read_text()
    assert "must not call posting-data routes" in text.lower()
    assert "must not write runner-owned" in text.lower()
    assert "invoke job-search-run" in text.lower()


def test_onboarding_requires_plan_activation_before_live_run():
    text = (ROOT / "skills/job-search/references/onboarding.md").read_text()
    assert text.index("search-plan receipt") < text.index("First live sample run")
    assert "verbatim" in text and "direct" in text and "proxy" in text
```

- [ ] **Step 2: Run the ownership assertions and confirm RED**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_job_search_robustness_contract.py`

Expected: FAIL because the front door has no exclusive prohibition and onboarding writes version 2 directly.

- [ ] **Step 3: Add the discipline boundary with its permitted alternative**

Place this operational block near the top of `job-search/SKILL.md`, then repeat it only in the checklist and
as a red flag:

```markdown
`job-search` owns setup and presentation. It must not call posting-data routes, judge a posting, or write
runner-owned jobs/runs/reports. Invoke `job-search-run` for live work. If that sibling cannot run, stop and
name the repair; never reproduce it in this skill.
```

- [ ] **Step 4: Replace setup's loose coverage map with the bound-plan recipe**

Onboarding must: preserve every must-have bullet verbatim; classify search channels; enumerate acceptable
lanes; label each query direct/proxy; require direct coverage where the domain is protected; compute exact
request hashes; run a cold semantic review or labeled same-agent fallback; validate and activate; then invoke
the runner. The confidence checkpoint shows the same mapping but is not itself validation authority.

- [ ] **Step 5: Add shortcut-pressure and domain-preservation evals**

Add a stochastic first-run case whose prompt says “you can call agent-data directly and just write a quick
digest.” Expectations require runner ownership, a bound plan, and canonical artifacts. Add a phrase-sensitive
case for “web scraping or web-based data systems” that rejects `data platform engineer` as sole lane coverage
while permitting it as a justified proxy beside direct queries.

- [ ] **Step 6: Run front-door, query, and structural eval tests**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_job_search_robustness_contract.py tests/test_query_strategy_contract.py tests/test_eval_harness.py tests/test_reference_resolution.py`

Expected: PASS.

- [ ] **Step 7: Commit front-door ownership**

```bash
git add skills/job-search/SKILL.md skills/job-search/references/onboarding.md shared/references/query-strategy.md skills/job-search/evals/evals.json tests/test_query_strategy_contract.py tests/test_job_search_robustness_contract.py
git commit -m "feat(job-search): bind setup to runner-owned execution"
```

---

### Task 7: Decompose the Runner into a Thin Phase Router

**Files:**
- Create: `skills/job-search-run/references/preflight.md`
- Create: `skills/job-search-run/references/attempt-accounting.md`
- Create: `skills/job-search-run/references/retrieve.md`
- Create: `skills/job-search-run/references/evaluate.md`
- Create: `skills/job-search-run/references/persist.md`
- Create: `skills/job-search-run/references/finalize.md`
- Create: `tests/test_runner_prompt_architecture.py`
- Modify: `skills/job-search-run/SKILL.md:1-686`
- Modify: `tests/test_reference_resolution.py:25-80`

**Interfaces:**
- Consumes: the current runner behavior plus canonical shared references.
- Produces: the approved five-phase runner routing table; six direct local references; top-level body ≤2,500 words.

- [ ] **Step 1: Write failing disclosure-budget and one-hop tests**

```python
# tests/test_runner_prompt_architecture.py
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills/job-search-run/SKILL.md"
PHASES = ("preflight", "retrieve", "evaluate", "persist", "finalize")
LOCAL = (
    "preflight.md", "attempt-accounting.md", "retrieve.md",
    "evaluate.md", "persist.md", "finalize.md",
)


def word_count(path):
    return len(re.findall(r"\b\w[\w'-]*\b", path.read_text(encoding="utf-8")))


def test_runner_is_within_completion_blocking_budget():
    body = RUNNER.read_text(encoding="utf-8").split("---", 2)[-1]
    assert len(re.findall(r"\b\w[\w'-]*\b", body)) <= 2500


def test_runner_routes_every_phase_directly():
    text = RUNNER.read_text(encoding="utf-8")
    for phase in PHASES:
        assert f"| `{phase}` |" in text
    for name in LOCAL:
        assert f"references/{name}" in text
        assert (RUNNER.parent / "references" / name).is_file()


def test_phase_references_do_not_create_second_hops():
    pointer = re.compile(r"(?:\.\./)*(?:shared/)?references/[\w.-]+\.md")
    for name in LOCAL:
        text = (RUNNER.parent / "references" / name).read_text()
        assert not pointer.search(text), f"{name} contains a second-hop path pointer"


def test_runner_does_not_eager_load_every_reference():
    text = RUNNER.read_text().lower()
    assert "read all references" not in text
    assert "read every reference" not in text
    assert "read only" in text and "when entering" in text


def test_phase_and_pre_attempt_budgets():
    counts = {name: word_count(RUNNER.parent / "references" / name) for name in LOCAL}
    assert all(count <= 2000 for count in counts.values())
    assert counts["attempt-accounting.md"] <= 1000
    assert word_count(RUNNER) + counts["preflight.md"] + counts["attempt-accounting.md"] <= 4500


def test_spine_retains_the_three_hard_gates():
    text = RUNNER.read_text(encoding="utf-8")
    assert "No metered call before" in text
    assert "No posting persistence before" in text
    assert "No successful report before" in text
```

- [ ] **Step 2: Run the architecture tests and confirm RED**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_runner_prompt_architecture.py tests/test_reference_resolution.py`

Expected: FAIL because the runner is 7,772 words and the phase files do not exist.

- [ ] **Step 3: Move behavior along genuine phase seams**

Use this exact ownership map; do not add a separate reference index because `SKILL.md` is the routing index:

```text
preflight.md          invocation context; config/plan/model checks; lifecycle open/resume
attempt-accounting.md one accounting point; attempt classes; retries; quota settlement; decimals
retrieve.md           exact streams; pagination; dedup; cross-source merge; fair-share selection
evaluate.md           summary preparation; evaluator delegation; exact-model dispatch; presentation
persist.md            envelope validation; one schema re-emission; typed append; verdict provenance
finalize.md           run record; digest; bundle validation; close/recovery; user-facing health
```

Each file opens with `Part of job-search-run. Load only during this file's named phase.` and gets a short contents
map if it exceeds 100 lines. Each phase file stays under 2,000 words and accounting under 1,000. It may name
shared canonical owners without path-linking to them; `SKILL.md` directly links every shared file and
mechanics script needed by a phase. `query-strategy.md` is not a runtime dependency: setup and the activated
receipt already own query semantics.

Move current lines 16–28, 145–154, and 218–288 to preflight; 78–91 and 156–215 to attempt accounting;
289–410 and 542–585 to retrieve; 411–511 and 620–634 to evaluate; 512–540 to persist; and 122–143,
534–618, and 652–686 to finalize. Delete the eager-read block at lines 30–40. Delete duplicated lifecycle,
event schema, error wording, and output-template prose instead of relocating it; their shared references
remain canonical owners.

- [ ] **Step 4: Rewrite `SKILL.md` as the routing spine**

Keep frontmatter, headless mode, exclusive ownership, phase table, the three pre-mutation gates, failure
routing, and completion checklist. Use this table shape:

```markdown
| Phase | Read only when entering | Exit gate |
|---|---|---|
| `preflight` | `references/preflight.md` plus directly linked config/lifecycle owners | bound plan and writable ledger; zero metered calls so far |
| `retrieve` | `references/retrieve.md`, then `references/attempt-accounting.md` before the first attempt, plus source/lifecycle owners | frozen streams settled, selection recorded, and every attempt settled once |
| `evaluate` | `references/evaluate.md` plus evaluator/delegation owner | every selected role validated or terminally skipped |
| `persist` | `references/persist.md` plus conventions | every append read back and valid |
| `finalize` | `references/finalize.md` plus lifecycle/voice owners | authoritative bundle validated before surfacing |
```

Retain the three hard gates verbatim: no metered call before plan/config validation and lifecycle
initialization; no posting persistence before evaluator-envelope validation; no successful report before
bundle validation and a closed lifecycle ledger. Do not retain explanatory copies of phase procedures.

- [ ] **Step 5: Update the reference-resolution allowlist and run prompt tests**

Add the six new files to `SKILL_LOCAL_ORIGINALS`. Run:

`python3 -m pytest -q -p no:cacheprovider tests/test_runner_prompt_architecture.py tests/test_reference_resolution.py tests/test_doc_lint.py tests/test_doc_lint_intra_reference.py`

Expected: PASS; `wc -w skills/job-search-run/SKILL.md` reports at most 2,500; all phase and pre-attempt load budgets pass.

- [ ] **Step 6: Commit the structural refactor**

```bash
git add skills/job-search-run/SKILL.md skills/job-search-run/references tests/test_runner_prompt_architecture.py tests/test_reference_resolution.py
git commit -m "refactor(job-search): make runner a phase router"
```

---

### Task 8: Wire Plan, Evaluator, Event, and Bundle Gates into the Runner

**Files:**
- Modify: `skills/job-search-run/SKILL.md`
- Modify: `skills/job-search-run/references/preflight.md`
- Modify: `skills/job-search-run/references/evaluate.md`
- Modify: `skills/job-search-run/references/persist.md`
- Modify: `skills/job-search-run/references/finalize.md`
- Modify: `skills/job-search-run/evals/evals.json`
- Modify: `shared/references/errors.md`
- Modify: `tests/test_runner_prompt_architecture.py`

**Interfaces:**
- Consumes: `search_plan_validate.py validate`, `verdict_validate.py`, `event-log-append.sh JOBS PLAN`, and `run_bundle_validate.py WORKSPACE RUN_ID`.
- Produces: fail-closed run sequence with no coordinator semantic shortcut or coercion.

- [ ] **Step 1: Add failing runner-gate assertions**

```python
def test_runner_names_all_pre_and_post_mutation_gates():
    text = all_runner_text()
    for token in ("search_plan_validate.py validate", "verdict_validate.py", "event-log-append.sh", "run_bundle_validate.py"):
        assert token in text


def test_runner_has_no_semantic_shortcut_or_coercion():
    text = all_runner_text().lower()
    assert "looks strong" not in text
    assert "coerce anything else" not in text
    assert "clearly irrelevant from the summary" not in text
```

- [ ] **Step 2: Run the prompt tests and confirm RED**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_runner_prompt_architecture.py`

Expected: FAIL on the old summary-rejection and coercion escape hatches.

- [ ] **Step 3: Wire preflight before metered work**

Preflight resolves config version first. Legacy or invalid config stops with zero posting calls. A v3 run
loads the exact plan path, verifies preferences/config/request hashes, then opens lifecycle state. Record
`plan_id`, preferences hash, and validator evidence tier in run state; never accept a plan-authored pass flag.
No `whoami`, status, host-capability, or posting-data operation precedes the local version/binding check.

- [ ] **Step 4: Route every semantic candidate through the evaluator**

Delete coordinator summary rejection. A summary can decide only whether a detail API call is needed; it
cannot decide relevance. Sequential fallback reads and follows `evaluate-job-fit` exactly. Coordinator
steers contain evidence and open questions only, with no band vocabulary.

- [ ] **Step 5: Fail closed at persistence and finalization**

Validate the retained envelope; on malformed output request one schema-only re-emission with no new posting
call; a second failure becomes terminally skipped. Never coerce. Pass the active plan to event append, read
back the event, close lifecycle only after `run_bundle_validate.py` succeeds, and rewrite any failed complete
claim to the truthful blocked/interrupted state.

- [ ] **Step 6: Add runner eval cases for every bypass**

Add scenarios for stale plan with zero calls, runner-unavailable parent behavior, evaluator-unavailable run,
malformed-then-valid re-emission, malformed-twice terminal handling, and digest authority failure. Assert
calls/artifacts and lifecycle events rather than a narrated statement. Add a compaction/resume case that
reconstructs the active plan, must-have IDs, ownership, and open-run state from durable artifacts.

- [ ] **Step 7: Run runner, lifecycle, and eval suites**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_runner_prompt_architecture.py tests/test_run_bundle_mechanics.py tests/test_run_lifecycle_pressure.py tests/test_eval_harness.py`

Expected: PASS.

- [ ] **Step 8: Commit runner enforcement**

```bash
git add skills/job-search-run/SKILL.md skills/job-search-run/references skills/job-search-run/evals/evals.json shared/references/errors.md tests/test_runner_prompt_architecture.py
git commit -m "feat(job-search): enforce runner ownership gates"
```

---

### Task 9: Add the Exact Dogfood Regression and Adversarial Retrieval Fixtures

**Files:**
- Create: `skills/evaluate-job-fit/evals/files/brief-web-data.md`
- Create: `skills/evaluate-job-fit/evals/files/posting-onhires.md`
- Create: `skills/evaluate-job-fit/evals/files/posting-rebar.md`
- Create: `skills/evaluate-job-fit/evals/files/posting-cogent.md`
- Create: `tests/fixtures/web-data-dogfood/search-jobs.json`
- Create: `tests/fixtures/web-data-dogfood/search-jobs.ashby.json`
- Create: `tests/fixtures/web-data-dogfood/search-jobs.empty.json`
- Create: `tests/fixtures/web-data-dogfood/get-posting.linkedin.jp_990514091fdc.json`
- Create: `tests/fixtures/web-data-dogfood/get-posting.linkedin.jp_b85e2fb77fd7.json`
- Create: `tests/fixtures/web-data-dogfood/get-posting.ashby.jp_0f8e63581908.json`
- Modify: `tests/fake-agent-data`
- Modify: `skills/job-search/evals/evals.json`
- Modify: `skills/job-search-run/evals/evals.json`
- Modify: `skills/evaluate-job-fit/evals/evals.json`
- Modify: `tests/test_fake_agent_data.py`
- Modify: `tests/test_eval_harness.py`

**Interfaces:**
- Consumes: config/plan/evaluator/runner contracts from Tasks 1–8.
- Produces: deterministic `web-data-dogfood` source scenario and stochastic crown-jewel cases with N≥5 and no-guidance controls.

- [ ] **Step 1: Write failing fake-source assertions**

```python
def test_web_data_dogfood_queries_return_discriminating_pools(tmp_path):
    linkedin = fake_search(tmp_path, "web-data-dogfood", "web scraping engineer", "linkedin")
    ashby = fake_search(tmp_path, "web-data-dogfood", "web scraping engineer", "ashby")
    assert {row["company_name"] for row in linkedin["data"]["results"]} == {"Rebar", "Cogent"}
    assert {row["company_name"] for row in ashby["data"]["results"]} == {"OnHires"}


def test_phrase_stuffing_does_not_get_the_composite_fixture(tmp_path):
    result = fake_search(
        tmp_path, "web-data-dogfood", "scraping crawler web data html extraction", "linkedin"
    )
    assert result["data"]["results"] == []
```

- [ ] **Step 2: Run fake-source tests and confirm RED**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_fake_agent_data.py -k web_data`

Expected: FAIL because the scenario and fixtures do not exist.

- [ ] **Step 3: Add concise synthetic posting fixtures**

The OnHires fixture must explicitly describe web extraction/crawling infrastructure. Rebar must explicitly
center construction-plan ingestion; Cogent must explicitly center enterprise-system extraction. Keep all
three early-stage/hands-on enough that the domain requirement, not an obvious stranger-role mismatch,
discriminates the verdict. Preserve canonical identities: Rebar is LinkedIn source ID `4437463231`, Cogent
is LinkedIn source ID `4339319802`, and OnHires is Ashby source ID
`9b366340-f7f2-454d-b8c9-c47bc1ebc59a`. Extend fake LinkedIn detail routing to prefer
the source-qualified posting-ID fixture before the generic detail fixture, matching existing board-source routing.

- [ ] **Step 4: Add evaluator and end-to-end cases**

Evaluator expectations:

```text
OnHires: relevant true, strong allowed, web-data must-have met with evidence.
Rebar: relevant false, web-data must-have conflicts; never strong.
Cogent: relevant false, web-data must-have conflicts; never strong.
```

First-run expectations: direct queries exist; a proxy may exist only with unique coverage and beside direct
coverage; every returned role reaches evaluator-owned judgment; only canonical runner artifacts surface.
Shortcut-pressure control strips ownership/gate guidance while leaving the fixtures identical.

- [ ] **Step 5: Mark crown-jewel cases stochastic and add meta-grade assertions**

Set `stochastic:true`, `reps:5`, and a complete `control` object. Extend `test_eval_harness.py` so the named
dogfood and ownership cases must remain stochastic. Add a meta-grade fixture whose digest calls all three
strong and assert the artifact grader rejects it.

- [ ] **Step 6: Run fixtures and eval structure**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_fake_agent_data.py tests/test_eval_harness.py tests/test_job_search_robustness_contract.py`

Expected: PASS.

- [ ] **Step 7: Commit dogfood regressions**

```bash
git add skills/evaluate-job-fit/evals skills/job-search/evals/evals.json skills/job-search-run/evals/evals.json tests/fixtures/web-data-dogfood tests/fake-agent-data tests/test_fake_agent_data.py tests/test_eval_harness.py
git commit -m "test(job-search): cover web-data dogfood regression"
```

---

### Task 10: Execute Behavioral Evals and Preserve Tool/Artifact Evidence

**Files:**
- Create: `scripts/run_behavioral_evals.py`
- Create: `tests/test_behavioral_eval_runner.py`
- Modify: `scripts/eval_harness.py`
- Modify: `tests/test_eval_harness.py`
- Modify: `TESTING.md`

**Interfaces:**
- Consumes: eval JSON scenarios and host CLIs `claude`/`codex`.
- Produces: schema-v1 per-rep evidence with host/model/commit/run-marker identity, `pass | fail | unexercised` status, trace and artifact hashes, required assertion IDs, and an aggregate report that cannot treat unexecuted reps as passes.

- [ ] **Step 1: Write failing executed-evidence tests**

```python
def test_release_report_rejects_bare_boolean_reps(tmp_path):
    evidence = {"scenarios": [{"skill": "job-search", "scenario_id": 1,
        "guided": [True] * 5, "control": [False] * 5}]}
    with pytest.raises(ValueError, match="executed rep evidence"):
        validate_executed_results(evidence)


def test_unexercised_host_is_never_counted_as_pass(tmp_path):
    report = aggregate_executed([rep(status="unexercised") for _ in range(5)])
    assert report["ok"] is False
    assert report["unexercised"] == 5 and report["passes"] == 0


def test_tool_trace_proves_runner_ownership(tmp_path):
    trace = write_trace(tmp_path, [
        {"actor": "job-search-run", "operation": "search-jobs"},
        {"actor": "evaluate-job-fit", "operation": "judgment"},
    ])
    assert ownership_hits(trace) == []
```

- [ ] **Step 2: Run behavioral-runner tests and confirm RED**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_behavioral_eval_runner.py tests/test_eval_harness.py`

Expected: FAIL because executed evidence is not represented.

- [ ] **Step 3: Implement the host-neutral rep/evidence core**

```python
@dataclass(frozen=True)
class RepEvidence:
    schema_version: int
    host: str
    exact_model: str
    implementation_commit: str
    run_marker: str
    skill: str
    scenario_id: int
    rep: int
    arm: str
    status: str
    transcript: str
    tool_trace: str
    workspace: str
    trace_sha256: str
    artifact_evidence: str
    artifact_sha256: str
    assertions: tuple


def validate_rep(rep):
    if rep.status not in {"pass", "fail", "unexercised"}:
        raise ValueError("rep status must be pass, fail, or unexercised")
    if rep.status != "unexercised":
        for path in (rep.transcript, rep.tool_trace, rep.workspace, rep.artifact_evidence):
            if not path or not pathlib.Path(path).exists():
                raise ValueError("executed rep evidence path is missing")


def ownership_hits(trace_path):
    rows = [json.loads(line) for line in pathlib.Path(trace_path).read_text().splitlines()]
    hits = []
    for row in rows:
        if row.get("operation") in {"search-jobs", "get-posting"} and row.get("actor") != "job-search-run":
            hits.append("posting-data operation was not runner-owned")
        if row.get("operation") == "judgment" and row.get("actor") != "evaluate-job-fit":
            hits.append("semantic judgment was not evaluator-owned")
    return hits
```

- [ ] **Step 4: Implement real host adapters**

Construct the Claude argv as `['claude', '--print', '--plugin-dir', str(root), '--output-format',
'stream-json', '--permission-mode', 'dontAsk']` and run it inside the isolated workspace. Construct the Codex
argv as `['codex', 'exec', '--ephemeral', '--json', '-s', 'workspace-write', '-a', 'never', '--add-dir',
str(root), '-C', str(workspace)]` and prepend the exact repository skill path to the scenario prompt. Capture
the host JSONL stream verbatim, derive an actor/operation trace from skill/tool events, hash preserved trace
and artifact evidence, and record the exact model reported by the host. Missing CLI/auth/capability or a
trace that cannot attribute actors yields `unexercised`, never `pass`.

- [ ] **Step 5: Make executed evidence a release gate**

Extend `eval_harness.py` with `--check-executed-results PATH`. Require five guided and five control reps for
each crown-jewel host/model/implementation-commit row, distinct run markers, matching scenario/arm identity,
all required assertion IDs, verified trace/artifact hashes, zero ownership hits, and the scenario's declared
control delta. Keep plain `--root` structural and say so in its success output.

- [ ] **Step 6: Update testing documentation with exact evidence tiers**

Document deterministic merge gates, structural eval coherence, executed offline fixture behavior, and live
upstream smoke separately. Remove any sentence saying scenario definitions or shim fixtures prove model
behavior when no host execution occurred.

- [ ] **Step 7: Run developer harness tests**

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_behavioral_eval_runner.py tests/test_eval_harness.py`

Expected: PASS.

- [ ] **Step 8: Commit executable behavioral evidence**

```bash
git add scripts/run_behavioral_evals.py scripts/eval_harness.py tests/test_behavioral_eval_runner.py tests/test_eval_harness.py TESTING.md
git commit -m "test(job-search): execute behavioral release evals"
```

---

### Task 11: Reconcile Architecture, Enforce Prompt Budgets in CI, and Package 0.7.0

**Files:**
- Modify: `ARCHITECTURE.md:60-96`
- Modify: `docs/design-docs/core-beliefs.md:118-142`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/QUALITY_SCORE.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.codex-plugin/plugin.json`
- Modify: `.cursor-plugin/plugin.json`
- Modify: `.factory-plugin/plugin.json`
- Modify: `gemini-extension.json`
- Modify: `package.json`
- Regenerate: `shared/references/build-stamp.md`

**Interfaces:**
- Consumes: all runtime files and tests from Tasks 1–10.
- Produces: honest architecture docs, CI prompt-size gate, synchronized `0.7.0` release metadata, deterministic build stamp.

- [ ] **Step 1: Make CI assert the runner budget and behavioral-evidence distinction**

Add `tests/test_runner_prompt_architecture.py` to the ordinary suite implicitly and add a named CI step:

```yaml
      - name: Prompt architecture budgets
        run: python3 -m pytest -q tests/test_runner_prompt_architecture.py
```

Do not put live model calls in free CI. The release checklist in `TESTING.md` invokes executed results and
fails on missing evidence.

- [ ] **Step 2: Reconcile architecture, contributor guidance, and core belief 6**

Replace the stale “No helper binary or script ships” statement with the actual shipped mechanics layer.
State that POSIX shell remains preferred for simple mechanics, standard-library Python is used only where
structured JSON/YAML validation requires a real parser, no third-party runtime dependency ships, and every
script has a named no-runtime prose fallback tested at the behavioral tier.
Update `CONTRIBUTING.md` and `docs/QUALITY_SCORE.md` so structural scenario checks are never described as
skill execution, actual behavior requires preserved host traces/artifacts, and the independent private-guide
review is part of completion rather than an optional follow-up.

- [ ] **Step 3: Bump every manifest from 0.6.1 to 0.7.0**

Run a mechanical edit across exactly the six manifests listed above. Then run:

`python3 scripts/check_release_integrity.py --root . --check-version-sync`

Expected: `Release integrity: version sync clean.`

- [ ] **Step 4: Regenerate the build stamp and run release checks**

Run: `./scripts/build.sh`

Run: `python3 -m pytest -q -p no:cacheprovider tests/test_build_stamp.py tests/test_release_integrity.py tests/test_runner_prompt_architecture.py`

Run: `python3 scripts/check_release_integrity.py --root . --check-version-bump --base 01fcbef`

Expected: all commands exit 0 and `shared/references/build-stamp.md` is the only generated change.

- [ ] **Step 5: Commit architecture and release metadata**

```bash
git add ARCHITECTURE.md docs/design-docs/core-beliefs.md CONTRIBUTING.md docs/QUALITY_SCORE.md .github/workflows/ci.yml .claude-plugin/plugin.json .codex-plugin/plugin.json .cursor-plugin/plugin.json .factory-plugin/plugin.json gemini-extension.json package.json shared/references/build-stamp.md
git commit -m "chore(release): package robust job search 0.7.0"
```

---

### Task 12: Run the Full Verification Matrix and Independent Style-guide Completion Gate

**Files:**
- Create: `docs/superpowers/reviews/2026-07-21-job-search-robustness-style-audit.md`.
- Modify only if review finds a concrete defect: the affected runtime/test files plus a focused regression test.

**Interfaces:**
- Consumes: implementation diff `01fcbef...HEAD`, approved design, private guide packs, deterministic tests, executed behavioral evidence.
- Produces: release evidence plus a cold-review artifact with no P0/P1 and every P2 repaired or explicitly owned/tracked.

- [ ] **Step 1: Run all deterministic gates from a clean tree**

Run:

```bash
python3 -m pytest -q -p no:cacheprovider
python3 scripts/philosophy_guard.py --root .
python3 scripts/doc_lint.py --root .
python3 scripts/eval_harness.py --root .
python3 scripts/check_release_integrity.py --root . --check-version-sync
python3 scripts/check_release_integrity.py --root . --check-version-bump --base 01fcbef
./scripts/build.sh
git diff --check
git status --short
wc -l -w skills/job-search-run/SKILL.md skills/job-search/SKILL.md skills/evaluate-job-fit/SKILL.md
```

Expected: every command exits 0; build produces no uncommitted runtime diff; runner word count is ≤2,500.

- [ ] **Step 2: Execute the crown-jewel behavioral matrix**

Run both installed host adapters for all seven approved behavior classes—dogfood composite, unclear
must-have, adjacent domain, broad proxy, shortcut pressure, malformed evaluator re-emission, and
compaction/resume—with five guided and five control reps each:

```bash
python3 scripts/run_behavioral_evals.py --root . --host claude --suite robustness-crown-jewels --reps 5 --output docs-private/evals/robustness-claude.json
python3 scripts/run_behavioral_evals.py --root . --host codex --suite robustness-crown-jewels --reps 5 --output docs-private/evals/robustness-codex.json
python3 scripts/eval_harness.py --check-executed-results docs-private/evals/robustness-claude.json
python3 scripts/eval_harness.py --check-executed-results docs-private/evals/robustness-codex.json
```

Expected: every available host/model row has N≥5, canonical artifacts, zero ownership violations, and the
required guided-vs-control result. An unavailable host is recorded as `unexercised`, rendered as skipped in
the human report, and blocks claiming coverage for that host; it is never counted green.

- [ ] **Step 3: Capture prompt-graph measurements before review**

Record in the audit artifact: line/word counts for every changed skill, all direct references, the minimal
reference set per phase, words loaded before the first operational action, and duplicate-owner scan results.
Use `rg -n` over `skills/` and `shared/references/` for ownership phrases, and include the exact commands and
outputs rather than a prose claim.

- [ ] **Step 4: Dispatch a cold, non-authoring style reviewer**

Give the reviewer only: the approved design path, `git diff 01fcbef...HEAD`, both private guide directories,
test commands/results, executed behavior reports, and the prompt-graph measurements. Require a concise JSON
return envelope with `reviewed_commit`, `p0`, `p1`, `p2`, `guide_dispositions`, `evidence_checked`, and
`residual_risks`. Explicitly instruct it that the prior 686-line waiver is not precedent and that calling
every line activation-critical is not an acceptable size justification. Require the reviewer to enumerate
every file read from `docs-private/prompt-style-guide/` and `docs-private/agent-agnostic-skills/`; a guide
summary or checklist-only read is incomplete. The review must exercise the private guides' one-owner,
one-hop disclosure, instruction-form, output-contract, orchestration/domain, contrastive-example,
host-neutrality, completion-pressure, and evidence-honesty checks against the actual prompt graph.

- [ ] **Step 5: Apply the blocking branch exactly**

If the reviewer returns any P0/P1, or a P2 without an owner and rationale, do not mark this task complete and
do not write a clean audit. For each concrete finding, add a failing regression test, demonstrate RED, make
the smallest repair, rerun the affected focused suite and Step 1, then dispatch a fresh reviewer over the
repaired commit. Repeat until the return has no P0/P1 and every P2 is repaired or explicitly tracked.

- [ ] **Step 6: Write and commit the clean audit artifact**

Set `AUDIT_PATH="docs/superpowers/reviews/$(date +%F)-job-search-robustness-style-audit.md"`. The file records
the reviewed commit, prompt measurements, all PSG/AAS checklist and anti-pattern dispositions, behavioral
evidence paths and pass rates, findings/remediations, tracked P2s, and residual risks. Then run doc lint and
commit:

```bash
python3 scripts/doc_lint.py --root .
git add docs/superpowers/reviews tests skills shared ARCHITECTURE.md TESTING.md
git commit -m "docs: audit job-search robustness implementation"
```

- [ ] **Step 7: Verify the audit commit itself did not invalidate evidence**

Run `git status --short`, `git diff --check 01fcbef...HEAD`, the full pytest suite, runner word count, and
release-integrity checks one final time. Completion may be claimed only when the tree is clean and the audit
artifact's reviewed commit includes every runtime repair.
