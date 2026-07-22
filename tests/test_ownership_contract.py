"""Canonical ownership contract: one shared home, fenced at the front door, siblings discriminated.

Mirrors tests/test_query_strategy_contract.py in shape. Stdlib only.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
OWNERSHIP = ROOT / "shared" / "references" / "ownership.md"
MARKER = "ownership-contract:skill-roles"

COLUMNS = ("Skill", "Exclusively owns", "Never", "Instead")
OWNERS = ("`job-search`", "`job-search-run`", "`evaluate-job-fit`", "mechanics scripts")


def _marked_block(path, marker):
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- {re.escape(marker)} -->\n(.*?)\n<!-- /{re.escape(marker)} -->",
        text,
        re.S,
    )
    assert match, f"missing {marker} in {path.relative_to(ROOT)}"
    return match.group(1)


def _prose(path):
    """Whitespace-collapsed file text, for pinning a SENTENCE rather than a line.

    The contract is hard-wrapped, so "does not imitate the runner" spans a line break on disk and a raw
    `in text` check fails on wrapping alone — a phantom failure that says nothing about the contract, and
    that would return every time a sentence is re-flowed. Collapsing runs of whitespace keeps the pin on
    the words. Mirrors `_normalized_prose` in tests/test_usage_context_contract.py, which exists for
    exactly this reason. No wording is weakened: any edit to the words themselves still goes RED."""
    return " ".join(path.read_text(encoding="utf-8").split())


def _rows(block):
    """(header cells, data rows) of stripped cells from a marked Markdown table.

    Splitting on `|` is safe here because no cell contains an escaped pipe — the `Never` column separates
    its clauses with `·` for exactly that reason. A row whose cell count differs from the header's is
    returned as-is so `_row_faults` can REPORT the malformation instead of silently reshaping it."""
    parsed = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = tuple(cell.strip() for cell in line.strip("|").split("|"))
        if all(set(cell) <= set("-: ") for cell in cells):
            continue  # the |---|---| separator row
        parsed.append(cells)
    assert parsed, "the ownership table has no rows at all"
    return parsed[0], parsed[1:]


def _row_faults(block):
    """Every structural fault in the ownership table: wrong header, wrong owner set or order, a row with
    the wrong number of cells, or any empty cell.

    Factored out of the test so the detection itself can be exercised against known-corrupt samples
    (`test_row_fault_detection_is_not_vacuous`). A structural gate that only ever sees the good input
    proves nothing about what it would catch."""
    header, rows = _rows(block)
    faults = []
    if header != COLUMNS:
        faults.append(f"header is {header}, expected {COLUMNS}")
    owners = tuple(row[0] for row in rows)
    if owners != OWNERS:
        faults.append(f"owner rows are {owners}, expected {OWNERS}")
    for row in rows:
        if len(row) != len(COLUMNS):
            faults.append(f"{row[0]}: {len(row)} cells, expected {len(COLUMNS)}")
            continue
        for column, cell in zip(COLUMNS, row):
            if not cell:
                faults.append(f"{row[0]}: empty `{column}` cell")
    return faults


def shipped_surfaces():
    """Every shipped Markdown file that is NOT knowledge-base prose about the product.

    `skills/` and `shared/` are the runtime tree an agent loads; `templates/`, `examples/`, `.opencode/`
    and the root-level docs ship in the same clone and are exactly where a well-meaning editor would
    paste a copy of the table. `docs/` is excluded DELIBERATELY, not by oversight: the exec plan that
    commissioned this contract quotes the marked block verbatim inside a fenced code block, so scanning
    it would fail on the plan rather than on a duplicate. `.superpowers/` and `docs-private/` are
    excluded for the same reason (task briefs and reports quote the block) and neither ships."""
    return (sorted(ROOT.glob("skills/**/*.md"))
            + sorted(ROOT.glob("shared/**/*.md"))
            + sorted(ROOT.glob("templates/**/*.md"))
            + sorted(ROOT.glob("examples/**/*.md"))
            + sorted(ROOT.glob(".opencode/*.md"))
            + sorted(ROOT.glob("*.md")))


def test_ownership_contract_exists_and_names_every_skill():
    block = _marked_block(OWNERSHIP, MARKER)
    for skill in ("job-search", "job-search-run", "evaluate-job-fit"):
        assert f"`{skill}`" in block, f"ownership contract does not name {skill}"
    for skill_dir in ("job-search", "job-search-run", "evaluate-job-fit"):
        assert (ROOT / "skills" / skill_dir / "SKILL.md").exists()


def test_ownership_contract_is_single_homed():
    """AAS-BOUND-03: only shared/references/ownership.md carries the marked block.

    Scanned over every shipped non-KB surface, not just the runtime tree: the audit that produced this
    contract found ownership already stated in ARCHITECTURE.md, so a root-level doc is a REALISTIC place
    for a second copy to appear, and a skills+shared-only glob would never see it."""
    surfaces = shipped_surfaces()
    assert len(surfaces) >= 20, f"the shipped-surface scan collapsed to {len(surfaces)} files"
    assert OWNERSHIP in surfaces, "the scan does not reach the contract's own home"
    hits = sorted(
        p.relative_to(ROOT)
        for p in surfaces
        if f"<!-- {MARKER} -->" in p.read_text(encoding="utf-8")
    )
    assert hits == [OWNERSHIP.relative_to(ROOT)], f"ownership contract restated in {hits}"

    # A second copy INSIDE the home is invisible to a per-file scan, and `_marked_block` would silently
    # read only the first of the two — the shape a bad conflict resolution leaves behind.
    text = OWNERSHIP.read_text(encoding="utf-8")
    assert text.count(f"<!-- {MARKER} -->") == 1, "the marked block is opened more than once"
    assert text.count(f"<!-- /{MARKER} -->") == 1, "the marked block is closed more than once"


def test_every_prohibition_is_paired_with_an_alternative():
    """AAS-FORM-10: every row names what the skill owns, what it must never do, AND what to do instead.

    The name checks above still pass on a gutted table — a row whose `Never` or `Instead` cell was
    emptied, or a dropped `mechanics scripts` row, leaves every asserted skill name in place. This is the
    assertion that fails for those corruptions."""
    assert _row_faults(_marked_block(OWNERSHIP, MARKER)) == []


def test_row_fault_detection_is_not_vacuous():
    """Prove the structural gate above can actually go RED, on the three corruptions it exists to catch."""
    good = _marked_block(OWNERSHIP, MARKER)
    header, rows = _rows(good)
    assert header == COLUMNS and len(rows) == len(OWNERS)

    def _table(data_rows):
        return "\n".join(["| " + " | ".join(COLUMNS) + " |", "|---|---|---|---|"]
                         + ["| " + " | ".join(cells) + " |" for cells in data_rows])

    gutted = [list(row) for row in rows]
    gutted[0][3] = ""                                   # the front door's `Instead` cell emptied
    dropped = [list(row) for row in rows[:-1]]          # the `mechanics scripts` row deleted
    renamed = _table([list(row) for row in rows]).replace("| Exclusively owns |", "| Owns |", 1)

    for sample, expected in (
        (_table(gutted), "empty `Instead` cell"),
        (_table(dropped), "owner rows are"),
        (renamed, "header is"),
    ):
        faults = _row_faults(sample)
        assert any(expected in fault for fault in faults), f"{expected!r} not caught: {faults}"


def test_front_door_row_routes_to_both_sibling_owners():
    """The live failure this contract exists to stop: the front door called the job source, judged the
    postings, and wrote the digest and job rows itself. Prohibiting that is only half the fix — its row
    must also name BOTH owners it hands off to, or the agent is told to stop with nowhere to go."""
    _, rows = _rows(_marked_block(OWNERSHIP, MARKER))
    front_door = {row[0]: row for row in rows}["`job-search`"]
    for prohibited in ("calls the job source", "judges a posting", "jobs.jsonl"):
        assert prohibited in front_door[2], f"the front door's `Never` cell drops {prohibited!r}"
    for owner in ("`job-search-run`", "`evaluate-job-fit`"):
        assert owner in front_door[3], f"the front door's `Instead` cell does not route to {owner}"


def test_owner_unavailable_rules_forbid_imitation():
    text = _prose(OWNERSHIP)
    assert "does not imitate the runner" in text
    assert "no inline mini-rubric" in text


def test_triage_line_bounds_the_summary_scan():
    """A2: the cheap scan may reject only on a structured field that contradicts a must-have."""
    text = _prose(OWNERSHIP)
    assert "structured summary field explicitly contradicts a must-have" in text
    assert "queues for the judge" in text
