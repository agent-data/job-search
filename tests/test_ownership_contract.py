"""Canonical ownership contract: one shared home, fenced at the front door, siblings discriminated.

Mirrors tests/test_query_strategy_contract.py in shape. Stdlib only.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
OWNERSHIP = ROOT / "shared" / "references" / "ownership.md"
MARKER = "ownership-contract:skill-roles"

COLUMNS = ("Skill", "Exclusively owns", "Never", "Instead")
OWNERS = ("`job-search`", "`job-search-run`", "`evaluate-job-fit`", "`job-preference-interview`",
          "`job-search-agent`", "mechanics scripts")
SKILLS = tuple(owner.strip("`") for owner in OWNERS if owner.startswith("`"))

# An `Instead` cell has to send the agent somewhere it can actually go: a named owner, or an action it can
# take unaided. A `Never` cell is the opposite kind of sentence — a prohibition, never a destination.
HANDOFF_VERBS = ("invoke", "route", "return", "fail", "stop", "hand", "delegate", "defer", "queue",
                 "escalate", "ask", "use")

# The two actions the whole contract turns on, each claimed in `Exclusively owns` by exactly one row and
# forbidden in `Never` by every skill row that claims neither. Keyed by the phrase the prose beneath the
# table uses, so a fault message and the paragraph it enforces say the same words.
# `Exclusively owns` phrases are the claim; `Never` phrases are the prohibition — different vocabularies
# because a cell that OWNS the pull says "metered calls" while a cell that FORBIDS it says "job source".
# Each `owns` tuple holds the natural ways a cell says it owns that action, so the gate asks whether the
# claim is still legible rather than whether one blessed phrase survived: a single-phrase vocabulary
# couples the contract to the runner's current wording, and any later rewrite of its responsibilities goes
# RED for saying the same thing differently. Kept narrow enough that only a cell claiming THIS action
# matches, and asymmetric to the `never` phrases so a prohibition cannot read as a claim.
PULL, VERDICT = "searching the job source", "a fit verdict"
CLAIMS = {
    PULL: {"owner": "`job-search-run`",
           "owns": ("metered calls", "the pull", "searching the job source"),
           "never": ("job source", "a search")},
    VERDICT: {"owner": "`evaluate-job-fit`", "owns": ("relevance", "dealbreakers"),
              "never": ("judg", "verdict")},
}

# `Exclusively owns` is an enumeration, not a residual claim. "everything else" is the shape a cell takes
# when someone stops enumerating: it swallows every other row's exclusive territory while the header still
# says *exclusively*, so the table contradicts itself and no reader can tell who owns what.
# Matched on word boundaries, not as bare substrings: "etc" is a substring of `fetching` and `sketch` —
# both words this pack uses about itself — so an unbounded match fires on a legitimate rewrite and reports
# a residual claim that is not there, which is worse than missing one because the message misdirects.
RESIDUAL_CLAIMS = ("everything", "anything", "all else", "the rest", "whatever", "etc")

_FENCE = re.compile(r"^(?:```|~~~)")
_CODE_SPAN = re.compile(r"`[^`]*`")
_PARENTHETICAL = re.compile(r"\([^()]*\)")


def _marked_block(path, marker):
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- {re.escape(marker)} -->\n(.*?)\n<!-- /{re.escape(marker)} -->",
        text,
        re.S,
    )
    assert match, f"missing {marker} in {path.relative_to(ROOT)}"
    return match.group(1)


def _normalized_prose(path):
    """Whitespace-collapsed file text, for pinning a SENTENCE rather than a line.

    The contract is hard-wrapped, so "does not imitate the runner" spans a line break on disk and a raw
    `in text` check fails on wrapping alone — a phantom failure that says nothing about the contract, and
    that would return every time a sentence is re-flowed. Collapsing runs of whitespace keeps the pin on
    the words. Same name and same body as the helper in tests/test_usage_context_contract.py, which exists
    for exactly this reason. No wording is weakened: any edit to the words themselves still goes RED."""
    return " ".join(path.read_text(encoding="utf-8").split())


def _rows(block):
    """(header cells, data rows) of stripped cells from a marked Markdown table.

    Splitting on `|` is safe here because no cell contains an escaped pipe — the `Never` column separates
    its clauses with `·` for exactly that reason. A row whose cell count differs from the header's is
    returned as-is so `_row_faults` can REPORT the malformation instead of silently reshaping it.

    A separator row must actually contain a dash. `set(cell) <= set("-: ")` alone is true of a row of EMPTY
    cells, so `| | | | |` would be swallowed as a separator and the corruption would surface later as an
    owner-set mismatch — a message that sends the reader to fix the owner list rather than the blank row
    they actually added."""
    parsed = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = tuple(cell.strip() for cell in line.strip("|").split("|"))
        if all(set(cell) <= set("-: ") for cell in cells) and any("-" in cell for cell in cells):
            continue  # the |---|---| separator row — a dash is what makes it one
        parsed.append(cells)
    assert parsed, "the ownership table has no rows at all"
    return parsed[0], parsed[1:]


def _lead_word(cell):
    """The cell's first word, stripped of Markdown emphasis and punctuation, lowercased."""
    first = cell.strip().split()[0] if cell.strip() else ""
    return first.strip("*_`—-–:;,.()").lower()


def _named_owners(cell):
    """The owner skills this cell names. Backticks disambiguate: `job-search-run` does not contain
    `job-search`, because the closing backtick has to land right after the name."""
    return [owner for owner in OWNERS if owner.startswith("`") and owner in cell]


def _claims(cell, action):
    """Whether an `Exclusively owns` cell claims `action` (`PULL` or `VERDICT`)."""
    return any(phrase in cell.lower() for phrase in CLAIMS[action]["owns"])


def _bans(cell, action):
    """Whether a `Never` cell forbids `action`, ignoring its parenthesized carve-outs.

    A carve-out names the action it excepts, so it carries the very words the ban is matched on: the
    runner's cell ends `(one bounded exception: **Triage is not a verdict**, below)`, and a cell reduced
    to that parenthetical alone would satisfy a bare substring check while forbidding nothing. The ban has
    to survive outside its own exception."""
    outside = _PARENTHETICAL.sub(" ", cell).lower()
    return any(phrase in outside for phrase in CLAIMS[action]["never"])


def _residual_claims(cell):
    """The residual-claim words this `Exclusively owns` cell uses, matched whole."""
    lowered = cell.lower()
    return [word for word in RESIDUAL_CLAIMS if re.search(rf"\b{re.escape(word)}\b", lowered)]


def _row_faults(block):
    """Every fault in the ownership table — shape AND content.

    Shape: wrong header, wrong owner set or order, a row with the wrong number of cells, or any empty cell.

    Content, three rules:

    1. The two columns have to stay the two KINDS of sentence they are. An `Instead` cell must send the
       agent somewhere — naming an owner skill, or opening with a handoff verb it can act on unaided. A
       `Never` cell must forbid, so it may not name another owner (that is a destination, and destinations
       belong one column over) nor open with a handoff verb. Shape alone passed the two corruptions that
       first motivated this: swapping `Never` with `Instead` on the runner's row — which makes the contract
       MANDATE the exact behavior it was written to forbid — and reducing an `Instead` cell to `TBD`.

    2. The pull and the verdict are each claimed in `Exclusively owns` by exactly one row, the one the
       prose beneath the table names, and no cell claims residual territory. Checking that column for
       non-emptiness alone let two corruptions through: SWAPPING the runner's and the judge's `Owns` cells,
       which makes the table say the judge owns the metered calls and the runner owns the verdict while the
       `Never` cells one column over still say the opposite; and replacing the front door's cell with
       "everything else", which claims every other row's exclusive territory in two words.

    3. THE invariant the contract asserts in prose — every skill that owns neither the pull nor the verdict
       carries BOTH prohibitions. Untested, the source prohibition could be deleted from
       `job-preference-interview` or both from `job-search-agent` — the exact failure class those two rows
       were added to close — with the whole file still green. Scoped to skill rows because the prose scopes
       it to skills: `mechanics scripts` is a validator, and forbidding it to search is not the claim.

    4. The runner forbids the verdict. Rule 3 exempts any row that owns one of the two actions, so the
       runner's `Never` — the contract's second-most load-bearing prohibition, and the one standing between
       the skill that already holds every posting and judging them — was pinned by non-emptiness alone and
       could be deleted with the suite green. Checked with rule 3's own VERDICT vocabulary so the two
       cannot drift, and chained to it so exactly one of the two always reads that cell. Deliberately not
       mirrored onto `evaluate-job-fit`: the prose carves out reading one posting's detail as not a search,
       so the judge legitimately carries no source prohibition.

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
    whole = [row for row in rows if len(row) == len(COLUMNS)]
    for row in rows:
        if len(row) != len(COLUMNS):
            faults.append(f"{row[0]}: {len(row)} cells, expected {len(COLUMNS)}")
            continue
        for column, cell in zip(COLUMNS, row):
            if not cell:
                faults.append(f"{row[0]}: empty `{column}` cell")
        cells = dict(zip(COLUMNS, row))
        owns, never, instead = cells["Exclusively owns"], cells["Never"], cells["Instead"]
        if instead and not (_named_owners(instead) or _lead_word(instead) in HANDOFF_VERBS):
            faults.append(f"{row[0]}: `Instead` names no owner and opens with no handoff verb "
                          f"{HANDOFF_VERBS} — it is not an alternative: {instead!r}")
        if never and _named_owners(never):
            faults.append(f"{row[0]}: `Never` names {_named_owners(never)[0]} — that is a destination, "
                          f"and destinations belong in `Instead`: {never!r}")
        elif never and _lead_word(never) in HANDOFF_VERBS:
            faults.append(f"{row[0]}: `Never` opens with the handoff verb {_lead_word(never)!r} — it reads "
                          f"as an instruction, not a prohibition: {never!r}")
        residual = _residual_claims(owns)
        if residual:
            faults.append(f"{row[0]}: `Exclusively owns` claims {residual[0]!r} — a residual claim "
                          f"swallows every other row's exclusive territory; enumerate the actions this "
                          f"skill owns instead: {owns!r}")
        # Rule 3 — a skill that owns neither of the two contested actions must forbid both.
        if row[0].startswith("`") and not (_claims(owns, PULL) or _claims(owns, VERDICT)):
            for action in (PULL, VERDICT):
                if not _bans(never, action):
                    faults.append(
                        f"{row[0]}: `Exclusively owns` claims neither the pull nor the verdict, so its "
                        f"`Never` must forbid both — it carries no clause about {action}, which belongs "
                        f"to {CLAIMS[action]['owner']}; say so with one of "
                        f"{CLAIMS[action]['never']}: {never!r}")
        # Rule 4 — the runner owns the pull, so rule 3 exempts its row and never reads its `Never`.
        elif row[0] == CLAIMS[PULL]["owner"] and not _bans(never, VERDICT):
            faults.append(
                f"{row[0]}: `Never` drops the fit-verdict ban — owning the pull exempts this row from "
                f"the both-prohibitions rule above, so this cell is the only thing keeping the skill that "
                f"holds every posting out of {VERDICT}, which belongs to {CLAIMS[VERDICT]['owner']}; say "
                f"so with one of {CLAIMS[VERDICT]['never']}: {never!r}")

    # Rule 2 — one claimant each, and it is the row the prose names.
    for action in (PULL, VERDICT):
        claimants = [row[0] for row in whole if _claims(row[1], action)]
        if claimants != [CLAIMS[action]["owner"]]:
            faults.append(
                f"{CLAIMS[action]['owner']}: `Exclusively owns` gives {action} to "
                f"{claimants or 'no row at all'} — exactly one row claims it, and the prose beneath the "
                f"table says it is this one; name it there with one of {CLAIMS[action]['owns']}")
    return faults


def _quotation_free(text):
    """`text` with fenced code blocks and inline code spans removed.

    Mirrors the fence-tracking walk `_unfenced_lines` in tests/test_reference_resolution.py, and exists for
    the same reason: a marker shown inside a code fence is a PICTURE of the block, not a second home for
    it. Both `docs/` files that carry the marker are quotations — the design doc sketches the header inside
    a fenced block, the exec plan pastes the whole table inside one and also names the marker in an inline
    code span. Dropping both forms is what lets `docs/` stay in scope, where a genuine unfenced paste
    still reads as the duplicate it would be."""
    kept, fence = [], None
    for line in text.split("\n"):
        marker = _FENCE.match(line.strip())
        if marker:
            token = marker.group(0)[0]
            if fence is None:
                fence = token
            elif fence == token:
                fence = None
            continue
        if fence is None:
            kept.append(_CODE_SPAN.sub("", line))
    return "\n".join(kept)


def _shipped_surfaces():
    """Every shipped Markdown file that is NOT knowledge-base prose about the product, plus `docs/`.

    `skills/` and `shared/` are the runtime tree an agent loads; `templates/`, `examples/`, `.opencode/`
    and the root-level docs ship in the same clone and are exactly where a well-meaning editor would paste
    a copy of the table. `docs/` is in scope too — the design doc and exec plan that commissioned this
    contract quote the marked block, but they quote it inside code fences and spans, which
    `_quotation_free` removes; excluding the whole directory to dodge two quotations would blind the gate
    to every real duplicate a design doc could grow. `.superpowers/` and `docs-private/` stay out because
    neither ships.

    What widening the scan buys is bounded, and the bound is the marker: this gate matches on
    `<!-- ownership-contract:skill-roles -->`, so it finds a copy that was pasted WITH its markers and is
    blind to one that was retyped without them. A marker-less restatement of the table — the design doc
    carried a four-row one that drifted out of date — is out of its reach by construction, and stays a
    matter for review."""
    return (sorted(ROOT.glob("skills/**/*.md"))
            + sorted(ROOT.glob("shared/**/*.md"))
            + sorted(ROOT.glob("templates/**/*.md"))
            + sorted(ROOT.glob("examples/**/*.md"))
            + sorted(ROOT.glob("docs/**/*.md"))
            + sorted(ROOT.glob(".opencode/**/*.md"))
            + sorted(ROOT.glob("*.md")))


def test_ownership_contract_exists_and_names_every_skill():
    """Every skill in the pack gets a row. A contract that claims exclusivity while omitting skills asserts
    ownership over territory the absentees hold — and its load trigger is reachable from them, so an
    omitted skill reads a table that answers a question about someone else."""
    block = _marked_block(OWNERSHIP, MARKER)
    shipped = sorted(p.parent.name for p in ROOT.glob("skills/*/SKILL.md"))
    assert shipped == sorted(SKILLS), f"skills/ ships {shipped}, the contract names {sorted(SKILLS)}"
    for skill in SKILLS:
        assert f"`{skill}`" in block, f"ownership contract does not name {skill}"


def test_ownership_contract_is_single_homed():
    """AAS-BOUND-03: only shared/references/ownership.md carries the marked block.

    Scanned over every shipped non-KB surface, not just the runtime tree: the audit that produced this
    contract found ownership already stated in ARCHITECTURE.md, so a root-level doc is a REALISTIC place
    for a second copy to appear, and a skills+shared-only glob would never see it."""
    surfaces = _shipped_surfaces()
    assert len(surfaces) >= 20, f"the shipped-surface scan collapsed to {len(surfaces)} files"
    assert OWNERSHIP in surfaces, "the scan does not reach the contract's own home"

    # The stripping walk is proven on a fixture, not on live `docs/` prose. Asserting that some file in
    # `docs/` still quotes the block made a legitimate cleanup of the plan or the design doc go RED with a
    # message about the walk rather than about a duplicate — a gate coupled to prose it has no stake in.
    marker = f"<!-- {MARKER} -->"
    fixture = "\n".join(["```text", marker, "```",
                         f"the marker is also named inline as `{marker}` here",
                         marker])
    kept = _quotation_free(fixture).count(marker)
    assert kept == 1, (
        f"_quotation_free kept {kept} markers of a fixture holding one fenced, one inline-span and one "
        f"bare — only the bare one is a second home: {_quotation_free(fixture)!r}")

    hits = sorted(
        p.relative_to(ROOT)
        for p in surfaces
        if f"<!-- {MARKER} -->" in _quotation_free(p.read_text(encoding="utf-8"))
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
    emptied, or a dropped `mechanics scripts` row, leaves every asserted skill name in place. So does a
    table whose `Never` and `Instead` cells were SWAPPED, or whose alternative was replaced by filler: the
    shape is untouched and every name is where it was. This is the assertion that fails for all of them."""
    assert _row_faults(_marked_block(OWNERSHIP, MARKER)) == []


def test_the_table_states_the_pattern_its_never_column_encodes():
    """The paragraph beneath the table is what `_row_faults` rule 3 enforces, so it has to survive.

    Deleted, the table still reads as five rows of unrelated prohibitions, and the reader has to induce
    the pattern the contract is actually for. The check runs both ways: this pins the claim, `_row_faults`
    pins the table against it, and neither can drift without the other going RED."""
    text = _normalized_prose(OWNERSHIP)
    for sentence in ("searching the job source belongs to `job-search-run`, and a fit verdict belongs to "
                     "`evaluate-job-fit`.",
                     "Every skill that owns neither carries both prohibitions.",
                     "reading one posting is not a search"):
        assert sentence in text, f"the pairing paragraph no longer says {sentence!r}"


def test_row_fault_detection_is_not_vacuous():
    """Prove the gate above can actually go RED, on the ten corruptions it exists to catch.

    Samples 4 and 5 are the ones a shape-only check waved through: a `Never`/`Instead` swap on the runner's
    row, which turns the prohibition into the instruction, and a filler alternative that satisfies
    non-emptiness while telling the agent nothing.

    Samples 6-9 are the ones the shipped gate waved through even after that: the source prohibition deleted
    from `job-preference-interview`, both prohibitions deleted from `job-search-agent`, the runner's and the
    judge's `Owns` cells swapped so the table contradicts its own `Never` column, and the front door's
    `Owns` reduced to a residual claim. The first two are the failure class those two rows were ADDED to
    close, on the two rows that added them.

    Sample 10 is the one that survived all of those: the runner's `Never` reduced to its own parenthetical
    carve-out. Rule 3 exempted the row, and the carve-out names the verdict it excepts — so the cell still
    read as forbidding one, and the ban deleted cleanly with the suite green."""
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

    by_owner = {row[0]: index for index, row in enumerate(rows)}
    inverted = [list(row) for row in rows]              # the runner told to do what it must never do
    runner = inverted[by_owner["`job-search-run`"]]
    runner[2], runner[3] = runner[3], runner[2]
    filler = [list(row) for row in rows]                # the judge's alternative reduced to filler
    filler[by_owner["`evaluate-job-fit`"]][3] = "TBD"

    unsourced = [list(row) for row in rows]             # the brief-writer no longer forbidden to search
    unsourced[by_owner["`job-preference-interview`"]][2] = "judge a posting against the brief it just wrote"
    unguarded = [list(row) for row in rows]             # the manual forbidden neither pull nor verdict
    unguarded[by_owner["`job-search-agent`"]][2] = "write run artifacts"
    unbanned = [list(row) for row in rows]              # the runner's ban reduced to its own carve-out
    unbanned[by_owner["`job-search-run`"]][2] = (
        "(one bounded exception: **Triage is not a verdict**, below)")
    traded = [list(row) for row in rows]                # the pull and the verdict change hands
    traded[by_owner["`job-search-run`"]][1], traded[by_owner["`evaluate-job-fit`"]][1] = (
        rows[by_owner["`evaluate-job-fit`"]][1], rows[by_owner["`job-search-run`"]][1])
    residual = [list(row) for row in rows]              # the front door claims the whole table
    residual[by_owner["`job-search`"]][1] = "everything else"

    for sample, expected in (
        (_table(gutted), "empty `Instead` cell"),
        (_table(dropped), "owner rows are"),
        (renamed, "header is"),
        (_table(inverted), "that is a destination"),
        (_table(filler), "it is not an alternative"),
        (_table(unsourced), "no clause about searching the job source"),
        (_table(unguarded), "no clause about a fit verdict"),
        (_table(unbanned), "`Never` drops the fit-verdict ban"),
        (_table(traded), "gives searching the job source to"),
        (_table(residual), "a residual claim"),
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
    assert "artifacts" in front_door[3], (
        "the front door's `Never` forbids three things — calling the source, judging, AND writing "
        "`jobs.jsonl`/`runs/*.json`/a digest — but its `Instead` accounts for only two: say that the "
        "runner writes those artifacts as part of the pull")


def test_owner_unavailable_rules_forbid_imitation():
    text = _normalized_prose(OWNERSHIP)
    assert "does not imitate the runner" in text
    assert "no inline mini-rubric" in text


def test_triage_line_bounds_the_summary_scan():
    """A2: the cheap scan may reject only on a structured field that contradicts a must-have."""
    text = _normalized_prose(OWNERSHIP)
    assert "structured summary field explicitly contradicts a must-have" in text
    assert "queues for the judge" in text

    # The carve-out has to live INSIDE the marked block, because the block is the quotable unit: a skill
    # that copies the table into its own context carries the runner's `Never` cell verbatim, and without
    # the pointer that cell reads as an unqualified ban on the summary scan the runner is supposed to run.
    # Pinned on the cell, not on the file, so deleting it from the cell cannot be masked by the section
    # heading of the same name further down.
    _, rows = _rows(_marked_block(OWNERSHIP, MARKER))
    runner = {row[0]: row for row in rows}["`job-search-run`"][2]
    for carve_out in ("one bounded exception", "Triage is not a verdict"):
        assert carve_out in runner, (
            f"the runner's `Never` cell drops {carve_out!r} — inside the block it is the only thing "
            f"telling a reader the summary scan is still sanctioned: {runner!r}")
