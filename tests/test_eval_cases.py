"""Structural lint for the behavior-eval config: `evals/behaviors.md` and `evals/cases/*.yaml`.

The behavior evals themselves run against the live API and are a local release gate, never a CI
step. What CI can check is that the two halves of the config still agree: every matrix row names a
case file that exists, every case file carries the header fields its runner reads, and the
`behaviors:` list in a case matches the rows that name it. Case files are configuration, so
matching their keys and ids here is a structural check, not a documentation-substring assertion.

A case comes in one of two shapes, and carries exactly one of them:

* one `prompt`, graded as a whole session — `run_eval.py` runs these;
* a list of `phrases`, each its own session, graded on which skill it loaded —
  `run_triggering.py` runs these.

Both shapes carry `behaviors`, `workspace`, `timeout_s` and `models`.

The header parse is deliberately dependency-free (no PyYAML): CI installs pytest and nothing else,
and these five fields are all flat top-level keys.
"""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
BEHAVIORS = EVALS / "behaviors.md"
CASES_DIR = EVALS / "cases"

REQUIRED_HEADER_FIELDS = ("behaviors", "workspace", "timeout_s", "models")
# Exactly one of these says how the case supplies what it sends.
PROMPT_FIELDS = ("prompt", "phrases")
BEHAVIOR_ID = re.compile(r"^B([1-9][0-9]*)$")
CASE_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.yaml")


def _case_paths():
    return sorted(CASES_DIR.glob("*.yaml"))


def _top_level_keys(text):
    """Every key written at column 0, in order. Block scalars are indented, so they never match."""
    return [m.group(1) for m in re.finditer(r"(?m)^([A-Za-z_][A-Za-z0-9_]*):", text)]


def _flow_list(text, key):
    """Read a `key: [a, b, c]` flow list written at column 0."""
    match = re.search(rf"(?m)^{re.escape(key)}:[ \t]*\[([^\]]*)\]", text)
    assert match, f"{key}: must be a bracketed list"
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def _matrix_rows():
    """Parse the behaviors.md matrix into (id, case-file names) pairs, in file order."""
    rows = []
    for line in BEHAVIORS.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 4 or not BEHAVIOR_ID.match(cells[0]):
            continue
        rows.append((cells[0], CASE_FILENAME.findall(cells[2])))
    return rows


def _cases_by_behavior():
    """behavior id -> the case files whose header claims it."""
    claimed = {}
    for path in _case_paths():
        for behavior in _flow_list(path.read_text(encoding="utf-8"), "behaviors"):
            claimed.setdefault(behavior, []).append(path.name)
    return claimed


def test_behaviors_matrix_is_parseable_and_ids_are_unique_and_contiguous():
    rows = _matrix_rows()
    assert rows, "evals/behaviors.md has no parseable matrix rows"
    ids = [row_id for row_id, _ in rows]
    assert len(ids) == len(set(ids)), f"duplicate behavior ids: {ids}"
    numbers = [int(BEHAVIOR_ID.match(row_id).group(1)) for row_id in ids]
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"behavior ids must run B1..B{len(numbers)} in order, got {ids}"
    )


def test_every_matrix_row_names_at_least_one_existing_case_file():
    missing = []
    empty = []
    for row_id, case_files in _matrix_rows():
        if not case_files:
            empty.append(row_id)
        for name in case_files:
            if not (CASES_DIR / name).is_file():
                missing.append((row_id, name))
    assert not empty, f"behavior rows name no case file: {empty}"
    assert not missing, f"behavior rows name case files that do not exist: {missing}"


def test_every_case_file_is_named_by_at_least_one_matrix_row():
    named = {name for _, case_files in _matrix_rows() for name in case_files}
    orphans = [path.name for path in _case_paths() if path.name not in named]
    assert not orphans, f"case files no behavior row grades: {orphans}"


@pytest.mark.parametrize("case", [path.name for path in _case_paths()])
def test_case_header_carries_every_required_field(case):
    keys = _top_level_keys((CASES_DIR / case).read_text(encoding="utf-8"))
    assert len(keys) == len(set(keys)), f"{case}: duplicate top-level keys {keys}"
    missing = [field for field in REQUIRED_HEADER_FIELDS if field not in keys]
    assert not missing, f"{case}: header is missing {missing}"
    supplied = [field for field in PROMPT_FIELDS if field in keys]
    assert len(supplied) == 1, (
        f"{case}: a case carries exactly one of {list(PROMPT_FIELDS)}, got {supplied}"
    )


@pytest.mark.parametrize("case", [path.name for path in _case_paths()])
def test_case_header_values_are_in_range(case):
    text = (CASES_DIR / case).read_text(encoding="utf-8")

    workspace = re.search(r"(?m)^workspace:[ \t]*(\S+)", text)
    assert workspace and workspace.group(1) in {"fresh", "seeded"}, (
        f"{case}: workspace must be fresh or seeded"
    )

    timeout = re.search(r"(?m)^timeout_s:[ \t]*(\d+)", text)
    assert timeout and int(timeout.group(1)) > 0, f"{case}: timeout_s must be a positive integer"

    models = _flow_list(text, "models")
    assert models, f"{case}: models must name at least one model"
    assert set(models) <= {"sonnet", "haiku"}, f"{case}: unknown model in {models}"

    if re.search(r"(?m)^phrases:[ \t]*$", text):
        phrases = re.findall(r"(?m)^[ \t]+-[ \t]+id:[ \t]*(\S+)", text)
        assert phrases, f"{case}: phrases must list at least one entry, each with an id"
        assert len(phrases) == len(set(phrases)), f"{case}: duplicate phrase ids {phrases}"
        prompts = re.findall(r"(?m)^[ \t]+prompt:[ \t]*(\S.*)$", text)
        assert len(prompts) == len(phrases), (
            f"{case}: {len(phrases)} phrases carry {len(prompts)} prompts; each needs its own"
        )
        return

    prompt = re.search(r"(?m)^prompt:[ \t]*(\S.*)?$", text)
    assert prompt, f"{case}: prompt is missing"
    assert (prompt.group(1) or "").strip() in {"|", ">"} or (prompt.group(1) or "").strip(), (
        f"{case}: prompt must carry text or open a block scalar"
    )


@pytest.mark.parametrize("case", [path.name for path in _case_paths()])
def test_case_behaviors_are_known_ids(case):
    known = {row_id for row_id, _ in _matrix_rows()}
    claimed = _flow_list((CASES_DIR / case).read_text(encoding="utf-8"), "behaviors")
    assert claimed, f"{case}: behaviors must name at least one row"
    unknown = [behavior for behavior in claimed if behavior not in known]
    assert not unknown, f"{case}: behaviors names ids absent from behaviors.md: {unknown}"


def test_case_headers_and_matrix_rows_agree_both_ways():
    """A case claims exactly the rows that name it, so a case run reports the rows it graded."""
    claimed = _cases_by_behavior()
    mismatched = []
    for row_id, case_files in _matrix_rows():
        if sorted(claimed.get(row_id, [])) != sorted(case_files):
            mismatched.append((row_id, sorted(case_files), sorted(claimed.get(row_id, []))))
    assert not mismatched, (
        "behaviors.md and the case headers disagree (row, matrix says, cases claim): "
        f"{mismatched}"
    )
