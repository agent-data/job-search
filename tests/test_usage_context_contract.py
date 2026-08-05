"""Structural contract tests for calls-first agent-data usage decisions.

Everything here reads a machine-readable surface: a config template or fenced config example, a
shell fixture, or an entry in a skill's evals.json. How the surrounding guidance prose reads is
graded by the behavior evals in evals/ — never by substring assertions here. The marked-block
parses this file used to carry went with the references that held them on 2026-07-31.
"""

from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
AGENT_DATA = SKILLS / "agent-data-reference" / "SKILL.md"
CONFIG_TEMPLATE = ROOT / "skills" / "job-search" / "templates" / "config.example.yaml"
RUNNER_SETUP = ROOT / "skills" / "job-search-run" / "evals" / "files" / "setup-workspace.sh"

# Agent-data's per-call prices, which change whenever its plans change.
VOLATILE_PRICE_LITERALS = ("$0.008", "$0.0075", "$0.0067", "$0.005")

FORBIDDEN_EQUIVALENT_CHARGE_EXCEPTIONS = (
    re.compile(r"unless live account data says otherwise"),
    re.compile(
        r"(?:pay-as-you-go|computed|dollar) equivalent.{0,160}"
        r"\b(?:unless|except(?: when)?|but if)\b.{0,160}\b(?:account|charge)\b"
    ),
    re.compile(
        r"\b(?:unless|except(?: when)?|but if)\b.{0,160}\b(?:account|billing)\b"
        r".{0,160}\b(?:pay-as-you-go|computed|dollar) equivalent\b"
    ),
    re.compile(
        r"if live account(?:-plan)? metadata is absent,?\s+say the equivalent is not an actual charge"
    ),
    re.compile(
        r"(?:pay-as-you-go equivalent|equivalent).{0,200}\bnot an actual charge\b.{0,100}"
        r"\b(?:because|if|when|unless|except)\b.{0,160}\b(?:account|metadata)\b"
    ),
)


def _persisted_config_surfaces(root):
    """Yield real config templates/schemas and fenced persisted-config examples."""
    roots = [root / name for name in ("skills", "examples")]
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if re.search(r"(?:^|/)(?:config|[^/]+\.config)(?:\.[^/]+)*\.(?:ya?ml|json)$", relative):
                yield relative, path.read_text(encoding="utf-8")
                continue
            if path.suffix != ".md":
                continue

            text = path.read_text(encoding="utf-8")
            for index, match in enumerate(
                re.finditer(r"(?ms)^```(?P<info>[^\n]*)\n(?P<body>.*?)^```[ \t]*$", text), start=1
            ):
                info = match.group("info").strip().lower()
                if info not in {"", "yaml", "yml", "config.yaml", "config.yml"}:
                    continue
                heading_start = text.rfind("\n#", 0, match.start())
                context = text[heading_start + 1 if heading_start >= 0 else 0:match.start()]
                if "config.yaml" in context.lower() or info.startswith("config."):
                    yield f"{relative}#config-fence-{index}", match.group("body")


def _forbidden_monetary_config_key_hits(root):
    config_key = re.compile(
        r"(?im)^[ \t]*(?:-[ \t]*)?[\"']?(budget|credits|cost)[\"']?[ \t]*:"
    )
    hits = []
    for surface, text in _persisted_config_surfaces(root):
        hits.extend((surface, match.group(1).lower()) for match in config_key.finditer(text))
    return hits


def _eval(skill):
    path = ROOT / "skills" / skill / "evals" / "evals.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_static_config_template_is_v2_but_never_invents_a_model_identifier():
    """The template setup copies carries no model field at all: the 2026-07-30 rewrite retired
    that apparatus, so the line telling setup to insert one went with the onboarding prose."""
    template = CONFIG_TEMPLATE.read_text(encoding="utf-8")
    assert re.search(r"(?m)^version:\s*2\s*$", template)
    assert not re.search(r"(?m)^\s*detail_model\s*:", template)
    for selector in ("fast", "balanced", "high", "inherit"):
        assert not re.search(rf"\b{selector}\b", template.lower())


def test_runner_eval_fixture_pins_calls_first_context_and_a_validator_checked_close():
    """What the runner's shim fixtures pin about usage decisions, after the 2026-07-30 rewrite
    replaced the model-binding and config-version fixtures (that apparatus is retired): the setup
    script points discovery at a private workspace served by the fake shim, the happy case requires
    the calls-first context before the first metered call, and the quota case requires the
    allowance message."""
    setup = RUNNER_SETUP.read_text(encoding="utf-8")
    assert "registry.json" in setup          # discovery lands on the built workspace
    assert "fake-agent-data" in setup        # every case runs against the shim, spending nothing

    evals = _eval("job-search-run")["evals"]
    happy = next(case for case in evals if case["id"] == 1)
    joined = " ".join(happy["expectations"]).lower()
    assert "before the first search-jobs call" in joined
    assert "free monthly allowance" in joined
    assert "validate-workspace.sh --post-close exits 0" in joined

    quota = next(case for case in evals if "quota" in case["scenario"])
    assert "monthly allowance is spent" in " ".join(quota["expectations"]).lower()


def test_per_call_dollar_prices_live_in_one_skill():
    """Agent-data's per-call prices change when its plans change. One copy can be corrected; a
    second copy goes stale silently and the agent then quotes a price that is no longer real. And
    with no copy at all, an agent asked what a run costs has nothing to quote, so the count of
    owning files is pinned at exactly one: skills/agent-data-reference/SKILL.md."""
    owners = {}
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        found = [literal for literal in VOLATILE_PRICE_LITERALS if literal in text]
        if found:
            owners[path.relative_to(ROOT).as_posix()] = found
    assert len(owners) == 1, (
        f"the per-call dollar prices {list(VOLATILE_PRICE_LITERALS)} must live in exactly one "
        f"skill — a second copy goes stale silently, and none at all leaves the agent "
        f"with no price to quote. Found: {owners}"
    )
    owner, literals = next(iter(owners.items()))
    assert owner == AGENT_DATA.relative_to(ROOT).as_posix(), (
        f"the per-call dollar prices moved out of {AGENT_DATA.relative_to(ROOT)} to {owner}"
    )
    assert sorted(literals) == sorted(VOLATILE_PRICE_LITERALS), (
        f"{owner} is missing some of the per-call prices: has {literals}"
    )


def test_behavioral_evals_keep_computed_equivalents_unconditionally_non_charge():
    violations = []
    for eval_path in sorted(ROOT.glob("skills/*/evals/evals.json")):
        data = json.loads(eval_path.read_text(encoding="utf-8"))
        for case in data["evals"]:
            for expectation in case["expectations"]:
                normalized = " ".join(expectation.lower().split())
                for pattern in FORBIDDEN_EQUIVALENT_CHARGE_EXCEPTIONS:
                    if pattern.search(normalized):
                        violations.append((data["skill_name"], case["id"], pattern.pattern))
    assert not violations, f"behavioral evals condition equivalent-vs-charge semantics: {violations}"

    # The operator manual's usage fixture pinned a stored pay-as-you-go equivalent until the
    # 2026-07-30 rewrite: a run record now stores call counts only, so the fixture asks for the
    # counts as stored and for any dollar figure to be called an estimate.
    usage_case = next(
        case for case in _eval("job-search-agent")["evals"]
        if "what the last run spent" in case["scenario"]
    )
    expectations = " ".join(usage_case["expectations"]).lower()
    assert "as they are stored" in expectations
    assert "estimate rather than an actual charge" in expectations
    assert "agent-data.motie.dev/settings/billing" in expectations


def test_t2_2_effect_evals_cover_the_fake_only_red_cases():
    """The runner's per-attempt accounting case left this set with the attempt ledger it graded
    (the 2026-07-30 rewrite counts calls in the run record instead); what the runner's fixtures now
    pin about usage lives in test_runner_eval_fixture_pins_calls_first_context... above. The front
    door's two approved-sentence fixtures went with the same rewrite: the cost facts are stated in
    the agent's own words now, so its first-run fixture pins the ordering instead of the wording.
    The operator manual's review-depth and repeat-consent fixtures went with the same rewrite, which
    left one cost decision in that skill: a config change that raises what a run opens with states
    the new cost before it is saved."""
    search = _eval("job-search")
    agent = _eval("job-search-agent")

    search_by_id = {case["id"]: case for case in search["evals"]}
    first_run = " ".join(search_by_id[1]["expectations"]).lower()
    assert "before the first search-jobs entry" in first_run
    assert "free monthly calls" in first_run

    increases = next(
        case for case in agent["evals"]
        if "states the new cost before saving it" in case["scenario"]
    )
    joined = " ".join(increases["expectations"]).lower()
    assert "before config.yaml is written" in joined
    assert "comments and shape preserved" in joined
    assert "setup-workspace.sh" in increases["prompt"]


def test_no_budget_credits_or_cost_key_in_persisted_config_surfaces():
    hits = _forbidden_monetary_config_key_hits(ROOT)
    assert not hits, f"forbidden monetary config keys ship in config surfaces: {hits}"


def test_non_config_cost_fields_and_prose_are_allowed(tmp_path):
    api_doc = tmp_path / "skills" / "agent-data-reference" / "api.md"
    api_doc.parent.mkdir(parents=True)
    api_doc.write_text(
        "Ordinary prose may discuss cost: it is not persisted config.\n\n"
        "```json\n{\"cost\": \"response metadata\"}\n```\n",
        encoding="utf-8",
    )
    run_artifact = tmp_path / "examples" / "sample-run.json"
    run_artifact.parent.mkdir(parents=True)
    run_artifact.write_text('{"cost": "artifact context"}\n', encoding="utf-8")

    assert _forbidden_monetary_config_key_hits(tmp_path) == []


def test_forbidden_key_detection_is_scoped_to_real_config_surfaces(tmp_path):
    template = tmp_path / "skills" / "job-search" / "templates" / "config.example.yaml"
    template.parent.mkdir(parents=True)
    template.write_text("version: 1\nsearch:\n  cost: 10\n", encoding="utf-8")
    schema_doc = tmp_path / "skills" / "agent-data-reference" / "schema.md"
    schema_doc.parent.mkdir(parents=True)
    schema_doc.write_text(
        "## config.yaml\n\n```yaml\nversion: 1\nbudget: 25\ncredits: 50\n```\n",
        encoding="utf-8",
    )

    assert sorted(_forbidden_monetary_config_key_hits(tmp_path)) == [
        ("skills/agent-data-reference/schema.md#config-fence-1", "budget"),
        ("skills/agent-data-reference/schema.md#config-fence-1", "credits"),
        ("skills/job-search/templates/config.example.yaml", "cost"),
    ]
