# Fix the Final Review Findings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Addendum to:** [`2026-08-05-counts-from-the-event-log.md`](2026-08-05-counts-from-the-event-log.md) and [`2026-08-07-remove-status-changed.md`](2026-08-07-remove-status-changed.md), both fully executed. This plan fixes what the final whole-branch review found on the result.

**Goal:** Fix the three defects that put a wrong number in front of the user, correct one false claim that shipped in a comment, delete a hazard write-up that describes nothing, and stop a scheduling eval leaving a live recurring job on the owner's machine.

**Architecture:** Every fix ships with the test that would have caught it. The whole-branch review measured 90 mutations against the suite and 25 survived, all concentrated in the scripts that *write* the event log rather than the ones that read it — so a fix without a test would re-open the same gap.

**Tech Stack:** POSIX `sh` and `awk` only in shipped scripts — no `jq`, no Python, no bash-isms. `awk -f event-field.awk -f prog.awk`, because POSIX awk forbids mixing `-f` with inline program text. The eval harness is stdlib Python.

## DO NOT MERGE THIS BRANCH

The owner's instruction, 2026-08-08: "DO NOT merge this branch yet. I will want to review again after the fixes have been implemented." Finish this plan, report, and stop. Do not run `superpowers:finishing-a-development-branch`, do not open a pull request, do not merge to `main`.

## Global Constraints

- **Branch `feat/counts-from-the-event-log`.** Never commit to `main`.
- **`git add` names paths.** No `git add -A` in any commit step.
- **Public repo, MIT, © Aptiq Labs, Inc.** No tracked file — not a doc, not a commit message — mentions a hosted or commercial product.
- **Tests read live agent-data.** Never mocks, never a fake `agent-data` shim, never a committed response fixture, and no live response is committed. Metered calls are free to the owner; never shrink, cap or price a run.
- **Never write a number into a tracked file that a reader cannot re-run.** A header on this branch once cited a `wc` over `evals/results/`, which `.gitignore:18` excludes, so the figure worked on one machine only. Check any path you cite with `git ls-files <path>`.
- **No scratch command may write into the repository, and nothing may touch `~/.job-search`** — that is the owner's real workspace, and an escaped eval job wrote into it on 2026-08-07. Work under an absolute temp path.
- **The word budget is relaxed** (owner, 2026-08-07). Do not cut prose to hit a target.
- **A posting's current state is its `evaluated` line.** Not "the last line" — `surfaced`, `queued` and `detail` events carry `source` and `source_id` too. Never "the fold".
- **No idiom, figure of speech, or personification for a plain fact.** Never state a measurable fact without running the command that settles it, and cite the command.

---

### Task 1: Stop an unterminated last line swallowing the next event

**Files:**
- Modify: `skills/job-search-run/scripts/event-log-append.sh:82`, `skills/job-search-run/scripts/queue-detail-read.sh:106`, `skills/job-search-run/scripts/record-api-response.sh:166,315,456`, `skills/job-search-run/scripts/record-judgment.sh:198`
- Test: `tests/test_mechanics_scripts.py`

**Interfaces:**
- Produces: every appender leaves `jobs.jsonl` with one JSON object per physical line, whatever state it found the file in.

**The defect, reproduced.** With the last line of `jobs.jsonl` lacking a trailing newline, `record-judgment.sh` appends its event onto that line at exit 0. The field readers take each key's first occurrence, so the joined line reads as whatever the first event was. Measured on a posting judged relevant: `run-counts.sh` gives `postings_reviewed=0 postings_unreviewed=1`, `run-matches.sh` prints no rows, `posting-counts.sh` prints `relevant=0 to_confirm=0 filtered=0`. `find-judgment.awk` can then no longer see the buried judgment, so a second contradictory verdict is accepted at exit 0 — two `evaluated` substrings on one physical line. Nothing detects it: `validate-workspace.sh` reads `jobs.jsonl` only through `run-counts.sh`, which reports the wrong-but-consistent numbers.

There are **six** append sites, not five.

- [ ] **Step 1: Write the failing test**

```python
def test_an_append_onto_a_log_whose_last_line_lacks_a_newline_stays_one_event_per_line(tmp_path):
    """A log can end without a trailing newline — a hand edit, a truncated copy, an editor that
    does not add one. Appending onto it must not join two events into one physical line, because
    every field reader takes a key's first occurrence and would read the joined line as the first
    event, losing the second entirely."""
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        '{"event":"surfaced","run_id":"R","source":"linkedin","source_id":"100",'
        '"title":"T","company_name":"C","location_display":"L",'
        '"source_url":"https://x/1","ts":"2026-08-08T10:00:10Z"}',   # no trailing newline
        encoding="utf-8",
    )
    run_record_judgment(jobs, run_id="R", source="linkedin", source_id="100",
                        detail_read="false", relevant="true", match="strong",
                        needs_human_check="false", reasoning="fits")
    lines = jobs.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, f"expected two physical lines, got {len(lines)}: {lines}"
    assert json.loads(lines[0])["event"] == "surfaced"
    assert json.loads(lines[1])["event"] == "evaluated"
```

Write the same case for each of the other five append sites, driving the script that owns it.

- [ ] **Step 2: Run it and watch it fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k lacks_a_newline -q`
Expected: FAIL — one physical line, and the second assertion raises on the joined text.

- [ ] **Step 3: Add the guard to all six sites**

Immediately before each append, in the script that owns it:

```sh
# A log that does not end in a newline would take this event onto its last line, and every field
# reader takes a key's first occurrence, so the joined line would read as the earlier event and
# this one would be lost. `tail -c1 | wc -l` answers 1 when the last byte is a newline and 0
# otherwise — verified 2026-08-08 under sh, dash and bash.
if [ -s "$jobs" ] && [ "$(tail -c1 "$jobs" | wc -l)" -eq 0 ]; then printf '\n' >> "$jobs"; fi
```

The `[ -s ]` test matters: without it an empty log gains a leading blank line.

- [ ] **Step 4: Run the tests**

Run: `python3 -m pytest tests/ -q`
Expected: pass. Report the count; it was 937 before this task.

- [ ] **Step 5: Commit**

```bash
git add skills/job-search-run/scripts/event-log-append.sh skills/job-search-run/scripts/queue-detail-read.sh \
        skills/job-search-run/scripts/record-api-response.sh skills/job-search-run/scripts/record-judgment.sh \
        tests/test_mechanics_scripts.py
git commit -m "fix(run): never append an event onto an unterminated last line"
```

---

### Task 2: Report a duplicate opening instead of counting it twice

**Files:**
- Modify: `skills/job-search-run/scripts/run-counts.awk`, `skills/job-search-run/scripts/run-counts.sh`, `skills/job-search-run/scripts/run-matches.awk`, `skills/job-search-run/scripts/run-matches.sh`, `skills/job-search-runbook/scripts/close-run.sh`, `skills/job-search-runbook/scripts/validate-workspace.sh`, `skills/job-search-run/SKILL.md`
- Test: `tests/test_mechanics_scripts.py`, `tests/test_validate_workspace.py`

**Interfaces:**
- Produces: `run-counts.sh` gains one output key, `duplicates_of_another`. `run-matches.sh` gains an eleventh column carrying the other locations the same opening was posted in.

**The defect, reproduced.** One opening posted in two cities, the second judgment carrying `same_role_as`: `run-counts.sh` prints `match_strong=2` and `run-matches.sh` prints two rows, while `posting-counts.sh` prints `relevant=1`. The user sees the same job twice in the digest and one posting on the home card. `posting-counts.awk` reads `same_role_as`; `run-counts.awk` and `run-matches.awk` never do — measured, 2 references against 0 and 0. It is not rare: all four live runs captured on 2026-08-07 set the field, with 1, 1, 9 and 1 aliases.

**The owner's decision, 2026-08-08:** "The digest should say one and highlighted 'similar' postings or something like that - we shouldn't just choose a random location and swallow the rest."

**The constraint that shapes it.** `validate-workspace.sh:406` enforces `strong + moderate + weak + filtered == reviewed`. Dropping aliases from the bands while `reviewed` still counts postings breaks that invariant on every record. So the duplicate gets its own key and the sum still holds: `match_strong=1`, `duplicates_of_another=1`, `postings_reviewed=2`, and `1 + 1 = 2`.

- [ ] **Step 1: Write the failing tests**

```python
def test_one_opening_posted_twice_is_one_match_and_one_duplicate(tmp_path):
    """A run that finds the same opening in two cities reports one match, not two, and says so
    rather than silently dropping the second — the digest and the home card must agree about how
    many openings the run found."""
    jobs = seed_two_cities(tmp_path)          # 2 surfaced + 2 evaluated, the second same_role_as
    counts = run_counts(jobs, RUN_ID)
    assert counts["match_strong"] == 1
    assert counts["duplicates_of_another"] == 1
    assert counts["postings_reviewed"] == 2
    assert (counts["match_strong"] + counts["match_moderate"] + counts["match_weak"]
            + counts["filtered_out"] + counts["duplicates_of_another"]) == counts["postings_reviewed"]

def test_the_duplicate_location_rides_on_the_row_that_survives(tmp_path):
    """The other city is information the user wants, so it appears on the surviving row rather
    than being dropped with the duplicate posting."""
    jobs = seed_two_cities(tmp_path)
    rows = run_matches(jobs, RUN_ID, "strong")
    assert len(rows) == 1
    assert rows[0]["location_display"] == "Remote, USA"
    assert rows[0]["also_posted"] == "Austin, TX"

def test_the_digest_count_equals_the_rows_it_lists(tmp_path):
    """The heading and the list under it are read together; a count above a shorter list is the
    defect this task exists to remove."""
    jobs = seed_two_cities(tmp_path)
    assert run_counts(jobs, RUN_ID)["match_strong"] == len(run_matches(jobs, RUN_ID, "strong"))
```

Also write: an alias naming a posting that is **not in the log**, and an alias whose value does not carry the documented `<source>:<source_id>` shape. Decide and pin what each does — see Step 3.

- [ ] **Step 2: Run them and watch them fail**

Run: `python3 -m pytest tests/test_mechanics_scripts.py -k "opening_posted_twice or duplicate_location or digest_count_equals" -q`
Expected: FAIL — `match_strong` is 2, `duplicates_of_another` is not a key, and two rows come back.

- [ ] **Step 3: Change the two readers**

`run-counts.awk`: read `same_role_as` alongside `relevant` and `match` on the `evaluated` branch. In the END walk, a posting carrying it increments `duplicates` and is counted in no band. Print `duplicates_of_another=%d` in the key set. Keep `postings_reviewed` counting postings, because it pairs with `postings_unreviewed` against `postings_surfaced` and describes work done, not openings found.

`run-matches.awk`: a posting carrying `same_role_as` does not get its own row. Resolve the value to the posting it names and attach that alias's `location_display` to the named posting's row as an eleventh column, comma-joined when more than one names it. A row with no aliases carries an empty column, so the column count never varies.

**`job-search-run/SKILL.md:110` documents the flag as `--same-role-as <source>:<source_id>`, and nothing has ever resolved or validated that shape** — `posting-counts.awk` only tests whether the field is non-empty, and `record-judgment.sh` checks only for control characters. Resolving it makes the format load-bearing for the first time. Decide and state in the header what happens when the value names a posting that is not in this run's log: counting it as a duplicate hides a posting, and counting it as its own row restores the double count. Pin whichever you choose with the test from Step 1.

`run-counts.sh` and `run-matches.sh`: update the key list and column list in their headers.

`close-run.sh`: carry `duplicates_of_another` into the run record beside the other count fields.

`validate-workspace.sh`: the band-sum check at `:406` must include the new key.

- [ ] **Step 4: Run the tests and drive it end to end**

Run: `python3 -m pytest tests/ -q`
Then, from a copy under an absolute temp path, on a log holding one opening posted in two cities:

```bash
sh skills/job-search-run/scripts/run-counts.sh <ws>/jobs.jsonl <run_id>
sh skills/job-search-run/scripts/run-matches.sh <ws>/jobs.jsonl <run_id> strong
sh skills/job-search/scripts/posting-counts.sh <ws>/jobs.jsonl
```
Expected: `match_strong=1` with `duplicates_of_another=1`, one row carrying the other city, and `relevant=1`. The two screens now agree. Run under `sh` and `dash` crossed with `/usr/bin/awk` and `/opt/homebrew/bin/mawk`; `/opt/homebrew/bin/awk` does not exist, so select an awk with a PATH holding a symlink named `awk`.

- [ ] **Step 5: Update the run skill's digest section**

`job-search-run/SKILL.md`'s digest section describes what the counts line and the listing hold. Say that an opening found in more than one place counts once and its other locations ride on its row. Do not restructure the section.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search-run/scripts/run-counts.awk skills/job-search-run/scripts/run-counts.sh \
        skills/job-search-run/scripts/run-matches.awk skills/job-search-run/scripts/run-matches.sh \
        skills/job-search-runbook/scripts/close-run.sh skills/job-search-runbook/scripts/validate-workspace.sh \
        skills/job-search-run/SKILL.md tests/test_mechanics_scripts.py tests/test_validate_workspace.py
git commit -m "fix(run): count one opening once, and name where else it was posted"
```

---

### Task 3: Three claims that are wrong, and one grep that is a regex

**Files:**
- Modify: `skills/job-search-run/scripts/event-log-append.sh:72`, `skills/job-search-run/scripts/dedup.sh:70`, `skills/job-search-run/scripts/find-judgment.awk`, `skills/job-search/scripts/posting-counts.awk:30-34`, `skills/job-search-run/scripts/queue-detail-read.sh:59-68`, `skills/job-search-run/scripts/record-judgment.sh:95-119`
- Test: `tests/test_mechanics_scripts.py`

- [ ] **Step 1: Write the failing tests**

Three cases, each reproduced by the review:

```python
def test_a_source_whose_name_holds_a_regex_metacharacter_is_matched_literally(tmp_path):
    """The source name is spliced into a grep -E pattern, so `a.c` matches a stored `axc` and a
    judgment for a real posting is silently dropped at exit 0."""

def test_a_source_whose_name_holds_an_unbalanced_bracket_does_not_break_the_duplicate_check(tmp_path):
    """`[x` makes grep -E fail on an unbalanced bracket, and the duplicate guard then admits a
    second judgment for a posting that already has one, at exit 0."""

def test_a_judgment_from_an_earlier_run_blocks_a_contradictory_one_in_this_run(tmp_path):
    """find-judgment.awk scopes its lookup to run_id, so a later run writes a second contradictory
    judgment for the same posting at exit 0 — measured: same run id exits 1 with one evaluated
    line, a different run id exits 0 with two."""
```

- [ ] **Step 2: Run them and watch them fail**

Expected: all three FAIL. The review measured that deleting either the `run_id` or the `source` filter from `find-judgment.awk:39-40` leaves all 937 tests passing, so nothing holds that behaviour today.

- [ ] **Step 3: Make the two greps literal**

`event-log-append.sh:72` and `dedup.sh:70` splice `$src` into an ERE. Replace with a form that cannot be a regex. `grep -F` matches a fixed string; the whitespace tolerance the surrounding comment relies on has to be preserved another way, so state in the header what the replacement does and does not tolerate.

- [ ] **Step 4: Decide `find-judgment.awk`'s scope, and say why in the header**

It filters on `event`, `run_id`, `source` and `source_id`. The `run_id` filter is what lets a later run write a contradictory judgment. Note that `dedup.sh` already keys its known-posting set on `evaluated` events across **all** runs — `grep -c run_id skills/job-search-run/scripts/dedup.sh` gives 0 — so a judged posting is not re-surfaced in the normal flow, and this guard only fires on a posting that reached a judgment another way. Choose the scope deliberately and record the reason.

- [ ] **Step 5: Correct the false claim shipped in a comment**

`posting-counts.awk:30-34` says a posting has at most one `evaluated` line "because event-log-append.sh and record-judgment.sh both refuse a second". Measured: `event-log-append.sh:71-74` refuses any second; `record-judgment.sh` refuses only within the same `run_id`. Rewrite it to state what each path actually enforces, and cite the command that settles it.

- [ ] **Step 6: Delete the prefix-hazard write-up**

`queue-detail-read.sh:59-68`, `record-judgment.sh:95-119` and `find-judgment.awk:32-37` describe a hazard that cannot occur in the code they are attached to: the greps include the closing quote. Measured 2026-08-08 on a log holding `source_id` `abcd` — `grep -c -F '"source_id":"abc'` gives 1, and `grep -c -F '"source_id":"abc"'`, which is the form the scripts build, gives 0. Two independent final reviewers reached the same conclusion. **Delete the write-up and its "change all five together or neither" instruction. Do not rewrite it.**

- [ ] **Step 7: Run the tests**

Run: `python3 -m pytest tests/ -q && python3 scripts/doc_lint.py --root . && python3 scripts/philosophy_guard.py --root .`

- [ ] **Step 8: Commit**

```bash
git add skills/job-search-run/scripts/event-log-append.sh skills/job-search-run/scripts/dedup.sh \
        skills/job-search-run/scripts/find-judgment.awk skills/job-search/scripts/posting-counts.awk \
        skills/job-search-run/scripts/queue-detail-read.sh skills/job-search-run/scripts/record-judgment.sh \
        tests/test_mechanics_scripts.py
git commit -m "fix(run): match a source name literally, and stop three comments claiming what is not true"
```

---

### Task 4: Stop a scheduling eval leaving a live job on the machine

**Files:**
- Modify: `evals/run_eval.py`
- Test: `tests/test_eval_harness.py`

**What happened, 2026-08-07.** The `schedule` case tests the recurring-job feature, so the run installed a real launchd job. `run_eval.py:36-44`'s `kill_group` SIGKILLs the child's process group, and launchd starts its job outside that group, so the job survived teardown and fired after the harness restored the owner's real `~/.job-search`. It appended 10 `call` events and left a 16-file scratch directory there. The `schedule` case has run at least five times before that day, so this has been reachable for a week.

- [ ] **Step 1: Write the failing test**

A test that runs the harness's teardown against a workspace where a job has been registered outside the process group, and asserts the teardown reports or removes it. If the harness cannot detect one, the test asserts the teardown **fails loudly** rather than reporting success — a silent pass is what let this reach a real workspace.

- [ ] **Step 2: Decide the mechanism and implement it**

Two candidates, and the choice belongs in the header with its reason. Either the harness records what scheduler entries exist before the session and compares afterwards, failing the run when a new one survives; or the eval workspace is given a scheduler namespace the harness can enumerate and remove. Whichever is chosen, teardown must not report success while a job it cannot see is still installed.

- [ ] **Step 3: Run the tests**

Run: `python3 -m pytest tests/test_eval_harness.py tests/test_eval_cases.py -q && python3 scripts/eval_harness.py --root .`

- [ ] **Step 4: Commit**

```bash
git add evals/run_eval.py tests/test_eval_harness.py
git commit -m "test(evals): fail the teardown when a scheduled job outlives the session"
```

---

## After this plan

Report to the owner and **stop**. Do not merge, do not open a pull request, do not run `superpowers:finishing-a-development-branch`. The owner reviews again first.

Three findings from the whole-branch review are deliberately **not** in this plan, and the report should say so:

1. **The writer test gaps** — 22 of 51 mutations of `record-api-response.sh`, `record-judgment.sh`, `queue-detail-read.sh`, `json-scan.awk` and `event-field.awk` survive with 937 passing. Tasks 1 through 3 retire several of them, but the rest need design decisions rather than assertions: `detail_read` is written onto every `evaluated` event and read by nothing, no event's `ts` is asserted except the queue's, and `test_every_event_builder_escapes_a_value_the_same_way` compares six function source texts to each other.
2. **Brief-scoped dedup** — reconsidering a posting after the brief changes. Mechanically small, but a whole-file hash means any edit re-surfaces everything; the targeted version reconsiders only postings previously judged not relevant.
3. **`AGENTS.md:29`** is stale on both halves: it says the corpus "are 9,092 words" and "the budget is 10,000", against a measured 10,468.
