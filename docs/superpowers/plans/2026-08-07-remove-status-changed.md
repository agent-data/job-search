# Remove the `status_changed` Event Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Addendum to:** [`2026-08-05-counts-from-the-event-log.md`](2026-08-05-counts-from-the-event-log.md), which is mid-execution — Tasks 0 through 12 have landed, Tasks 13 through 18 have not. That plan's execution is **frozen** until Task 1 of this plan lands, because its Tasks 13, 14, 16 and 17 carry instructions that would write `status_changed` back in.

**Goal:** Remove the `status_changed` event type and the `status` field from the product, and replace the home card's Pipeline line with counts that say what the filtering did.

**Architecture:** `status_changed` is the only way a posting's status ever leaves `new` — `record-judgment.awk:57` hardcodes `"status":"new"` on every judgment it writes. Removing it makes `evaluated` the only event a state reader looks at, and a posting carries at most one `evaluated` event, so its current state is that one line and the per-field-versus-per-line question that this plan's parent got wrong in five places stops existing. `status` becomes a constant nothing reads, so it goes too.

A posting carries at most one `evaluated` event because both append paths refuse a second one for a `(source, source_id)` that already has one: `event-log-append.sh:19-20` states the rule and `:60-72` enforces it, and `record-judgment.sh:17` reads "Exit 0: recorded, or this posting already carries exactly this judgment", with the retry-versus-conflict decision at `:156-195`. Measured 2026-08-07 by running each script twice over a temp log under an absolute path. Piping a second `evaluated` event with a different verdict to `event-log-append.sh` exits 0 and leaves one `evaluated` line. Calling `record-judgment.sh` again with the same verdict exits 0 and prints "linkedin:a already carries this verdict — nothing written"; with a different verdict it exits 1 and prints "linkedin:a already has a judgment in run R, and it is not the line this call would write". The log holds one `evaluated` line in every case.

Do not reason from the event's field set instead. An `evaluated` event does **not** carry every field on every line: `record-judgment.awk:59-60` writes `same_role_as` and `posted_at_extracted` only when they are non-empty.

**Tech Stack:** POSIX `sh` and `awk` only in shipped scripts — no `jq`, no Python, no bash-isms. `awk -f event-field.awk -f prog.awk`, because POSIX awk forbids mixing `-f` with inline program text.

## Why this is being removed

The owner's decision, 2026-08-07: "the primary value add of this plugin right now is NOT application tracking, it's producing hyper-personalized and relevant job postings, where you can describe exactly what you would and wouldn't do, how much you want to get paid, qualifications, and background, and it will do a lot of the filtering one would have to do from reading the job descriptions." Application tracking is wanted eventually, not now.

A posting is already never shown twice without any help from `status_changed`: `dedup.sh:69-73` builds its known-ids set by grepping `"event":"evaluated"` only. Recording that the user already applied changes nothing about what they see next.

## Global Constraints

Inherited verbatim from the parent plan:

- **Branch `feat/counts-from-the-event-log`.** Never commit to `main`.
- **`git add` names paths.** No `git add -A` in any commit step.
- **Public repo, MIT, © Aptiq Labs, Inc.** No tracked file — not a doc, not a commit message — mentions a hosted or commercial product.
- **Tests read live agent-data.** Never mocks, never a fake `agent-data` shim, never a committed response fixture, and no live response is committed. Metered calls are free to the owner; never shrink, cap or price a run.
- **Prose voice.** The `SKILL.md` files are continuous prose read by a model at runtime. Do not restructure them into checklists or add headings that were not there.
- **No metaphors, no invented jargon.** Say what the code does. Personification is the same failure: a gate does not see, a contract does not know.
- **Never state a measurable fact without running the command that settles it.** Cite the command next to the number.
- **No scratch command may write into the repository.** Work under an absolute temp path.

Replacing the parent plan's `:45` phrasing rule, which is what introduced the defect this removal makes moot:

- **The state rule, stated once, correctly.** A posting's current state is **the last `evaluated` line** for its `source` and `source_id`. Not "the last line" — `surfaced`, `queued` and `detail` events also carry `source` and `source_id`, so the last line for a posting is often not a judgment. Never write "the fold".

New for this plan:

- **The word budget is relaxed** (owner, 2026-08-07). Do not hand any implementer a per-file word ceiling. Reconciliation happens at the final eval.
- **Nothing under `evals/results/` is touched.** Measured 2026-08-07: `grep -rl status_changed evals/results/ | wc -l` gives 31 files and `grep -rho status_changed evals/results/ | wc -l` gives 37 occurrences across 129 run directories. They are historical run transcripts and stay exactly as written.

---

### Task 1: Correct the parent plan and the spec

Do this first. Until it lands, the parent plan's Tasks 13, 14, 16 and 17 contain instructions that write `status_changed` back into shipped files.

**Files:**
- Modify: `docs/superpowers/plans/2026-08-05-counts-from-the-event-log.md`
- Modify: `docs/superpowers/specs/2026-08-05-counts-from-the-event-log-design.md`

**Interfaces:**
- Produces: the corrected instructions every later task in both plans reads.

- [ ] **Step 1: Invert the event-shape contract at `plan:80`**

`plan:80` currently reads, inside the section "The event shapes every task depends on":

> `status_changed` is unchanged.

Replace with:

> There is no `status_changed` event. It was removed on 2026-08-07 along with the `status` field — see [`2026-08-07-remove-status-changed.md`](2026-08-07-remove-status-changed.md). A posting's current state is its last `evaluated` line.

- [ ] **Step 2: Replace the state-rule phrasing in the Global Constraints at `plan:45`**

`plan:45` currently reads:

> - **No metaphors, no invented jargon.** Say what the code does. "The last line for a `source` and `source_id` wins", never "the fold". Personification is the same failure: a gate does not see, a contract does not know.

The quoted replacement phrase states the wrong rule and is the origin of the defect this plan removes. Replace the sentence containing it with:

> Say what the code does. A posting's current state is "the last `evaluated` line for a `source` and `source_id`", never "the fold" — and not "the last line", because `surfaced`, `queued` and `detail` events carry those two fields too.

- [ ] **Step 3: Fix the four unexecuted task instructions**

| Plan line | Currently says | Replace with |
|---|---|---|
| `:3667` | Task 12 Step 2 — name the five event types "plus `status_changed` for what the user tells it" | Name only `call`, `surfaced`, `queued`, `detail`, `evaluated`, and state the rule as the last `evaluated` line |
| `:3795-3797` | Task 14 Step 3 — how to find the posting whose `status_changed` to append | Delete the whole step; renumber the steps after it |
| `:3871` | Task 16 — the `evals.json:65` rewrite | See Task 5 Step 2 of this plan, which owns that line now |
| `:3990` | Task 17 Step 4 — the home-view assertion over a five-status seed | See Task 5 Step 3 of this plan, which owns it now |

- [ ] **Step 4: Fix the two plan lines that carry the wrong state rule into shipped text**

`:3563` is Task 11's verbatim script header and `:3874` is Task 16's replacement text for `docs/RELIABILITY.md:53`. `:3874`'s "Now" column quotes that line as "current state is computed by folding them by dedup key", stopping one character before "(last-write-wins per field)" — the qualifier that states the rule. Correct both to the last-`evaluated`-line rule. `RELIABILITY.md:53` reads in full:

```
events, and current state is computed by folding them by dedup key (last-write-wins per field).
```

Its replacement must be: `events, and a posting's current state is its last `evaluated` line for that dedup key.`

- [ ] **Step 5: Correct the spec**

The spec is `status: current`, so it is corrected rather than left as a written record.

| Spec line | Currently says | Action |
|---|---|---|
| `:77` | "`jobs.jsonl` is already an append-only log where the last line for a `source` + `source_id` wins." | Rewrite to the last-`evaluated`-line rule, and add that this sentence was wrong when written — the rule has been last-write-wins per field since `docs/design-docs/2026-06-05-os-design.md:168` |
| `:88` | "`status_changed` stays as it is — the user saying they applied somewhere." | Replace with a statement that the event type is removed, naming this plan |
| `:101` | "\| `pipeline-counts.sh` \| job-search \| prints the home view's per-status counts \|" | Rename to `posting-counts.sh` and restate what it prints |
| `:266` | "why §8's queue and `pipeline-counts.sh` exist" | Same rename |
| `:278-279`, `:304`, `:306` | the `job-search/SKILL.md` and `job-search/scripts/` rows, and the "fold" language rows | Update the script name; `:306`'s inventory row for `RELIABILITY.md 41, 44, 53` must carry the full quoted line, not the substring the scan captured |

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-08-05-counts-from-the-event-log.md \
        docs/superpowers/specs/2026-08-05-counts-from-the-event-log-design.md
git commit -m "docs(plan,spec): remove status_changed from the instructions that write it"
```

---

### Task 2: `posting-counts.sh` replaces `pipeline-counts.sh`

**Files:**
- Create: `skills/job-search/scripts/posting-counts.sh`, `skills/job-search/scripts/posting-counts.awk`
- Delete: `skills/job-search/scripts/pipeline-counts.sh`, `skills/job-search/scripts/pipeline-counts.awk`
- Modify: `tests/test_mechanics_scripts.py` (the twelve tests at `:4667-4886`)

**Interfaces:**
- Consumes: `../../job-search-run/scripts/event-field.awk` for `jval`.
- Produces: three lines on stdout — `relevant=<n>`, `to_confirm=<k>`, `filtered=<f>`. Task 4 wires the home card to these three keys.

**Nothing calls the old script.** Measured 2026-08-07 at `7e32a3f`: `grep -rn pipeline-counts skills/` returns nothing outside the two files themselves. It shipped in Task 11 and the parent plan's Task 14 was going to wire it in. Renaming it breaks no caller.

The name changes because "pipeline" is the removed concept. If `posting-counts` reads wrong to the reviewer, `home-counts` is the alternative; it is a one-word change and not worth a fix round either way.

- [ ] **Step 1: Write `posting-counts.awk`**

```awk
# posting-counts.awk — see posting-counts.sh.
#
# A posting is keyed by its source and its source_id joined with SUBSEP, the 0x1c byte, the way
# run-counts.awk:14-16 keys one. That byte cannot reach a value: json-scan.awk refuses a raw
# control character inside a string, and jval leaves the escape that spells it as the six
# characters it is written with. Joining with a printable byte instead would give two postings one
# key: with a pipe, source `a` with source_id `b|c` and source `a|b` with source_id `c` both come
# out as `a|b|c`, and the two would be counted as one.
#
# An `evaluated` event is the only one that says what a run decided about a posting, so a posting's
# current state is its last `evaluated` line. Dropping the other event types here saves three jval
# calls on each one; it is not what keeps them out of the counts, since none of them carries
# `relevant` for the END block to read.
#
# Nothing here depends on the order the END block visits postings in: all three printed numbers are
# sums and the three printf statements are in a fixed order, so `for (k in seen)` prints the same
# output under every awk.
#
# same_role_as is read for whether it is there, not for what it names. The row it names is the row
# that was read, and that row is counted on its own line; looking it up would change no count.

{
  if (jval($0, "event") != "evaluated") next
  k = jval($0, "source") SUBSEP jval($0, "source_id")
  seen[k] = 1

  # In any log the product writes, these three assignments never overwrite anything: a posting has
  # at most one evaluated line, because event-log-append.sh and record-judgment.sh both refuse a
  # second evaluated event for a (source, source_id) that already has one. Assigning rather than
  # testing first keeps this loop the same shape as run-counts.awk's and costs nothing; a
  # hand-edited log with two judgments for one posting would take the later line.
  rel[k]   = jval($0, "relevant")
  human[k] = jval($0, "needs_human_check")
  if (jval($0, "same_role_as") != "") alias[k] = 1
}

END {
  for (k in seen) {
    if (k in alias) continue    # the same opening, counted under the row that was read
    if (rel[k] == "true") {
      relevant++
      if (human[k] == "true") confirm++
    } else {
      filtered++
    }
  }
  printf "relevant=%d\n",   relevant+0
  printf "to_confirm=%d\n", confirm+0
  printf "filtered=%d\n",   filtered+0
}
```

- [ ] **Step 2: Write `posting-counts.sh`**

Start from the shipped `pipeline-counts.sh` and keep these paragraphs unchanged, because they are still true and each was measured: the `../../job-search-run/scripts` walk and why it holds across every packaging (`:33-39`), the log-size measurement that justifies a script rather than reading the file (`:27-31`), and the missing-operand exit codes (`:47-48`).

Change: the usage line and the key set (`relevant`, `to_confirm`, `filtered`); the exit-code paragraph, which loses exit 1 entirely — there is no unknown-status case left, so exit 0 means the counts printed and exit 2 means no log at that path; and the paragraph at `:19-25` about `to_confirm` counting over the same postings as the five status keys, which now says `to_confirm` counts over the relevant postings only.

- [ ] **Step 3: Delete the three tests that only exist for `status_changed`**

Delete from `tests/test_mechanics_scripts.py`:
- `test_a_rejected_posting_the_user_reacts_to_enters_the_pipeline`
- `test_a_judgment_written_without_a_status_counts_as_new`
- `test_a_status_none_of_the_six_lines_counts_is_reported_and_not_dropped`

These were verified to be the only three that fail when the handling is removed: an extracted copy of `7e32a3f` with the `status_changed` handling deleted from `pipeline-counts.awk:51,58,71` gave **3 failed, 936 passed**.

- [ ] **Step 4: Rewrite the nine surviving tests against the new keys**

Rename each to name the script and the behavior, keeping every existing assertion that still applies. Keep `test_two_postings_that_would_share_a_pipe_joined_key_are_counted_separately` — it is the sole killer of the pipe-joined-key mutant and the only thing pinning `SUBSEP`.

`test_the_last_line_for_a_posting_wins` needs different handling. Its log is a judgment followed by a `status_changed`, and the obvious repair — make the second line another `evaluated` event — would pin a shape the product cannot produce. Both append paths refuse a second `evaluated` event for a `(source, source_id)` that already has one; the Architecture paragraph above names the lines and the commands that measured it. So do not name a test after a rule no run exercises: `test_the_last_evaluated_line_for_a_posting_wins` claims one.

Either drop the test, or keep it as a reader test over a hand-written log and name it for that — `test_a_hand_written_log_with_two_judgments_for_one_posting_takes_the_later_line` says what it does. If you keep it, its docstring must say that only a hand-written or hand-edited log reaches this case, so the next reader knows the assertion pins the awk's behavior and not the product's. Say which you chose in the report.

Add one test the old suite had no case for: **a posting judged not relevant lands in `filtered`, not in `relevant`**, asserting all three numbers on a log holding one relevant and one not-relevant judgment.

- [ ] **Step 5: Run the tests**

Run: `python3 -m pytest tests/ -q`
Expected: pass. Record the count; it was 939 at `7e32a3f` and this task deletes 3 and adds 1.

Also run the script end to end under both awks and both shells, from a copy under an absolute temp path:

```bash
sh skills/job-search/scripts/posting-counts.sh evals/seeds/schedule/jobs.jsonl
dash skills/job-search/scripts/posting-counts.sh evals/seeds/schedule/jobs.jsonl
```

Expected: identical output, exit 0. That seed log holds two relevant postings; today the old script prints `new=2 interested=0 applied=0 rejected=0 archived=0 to_confirm=0` against it.

- [ ] **Step 6: Commit**

```bash
git add skills/job-search/scripts/posting-counts.sh skills/job-search/scripts/posting-counts.awk \
        tests/test_mechanics_scripts.py
git rm skills/job-search/scripts/pipeline-counts.sh skills/job-search/scripts/pipeline-counts.awk
git commit -m "feat(job-search): count relevant postings instead of pipeline statuses"
```

---

### Task 3: Stop writing the `status` field

**Files:**
- Modify: `skills/job-search-run/scripts/record-judgment.awk:5,57`
- Modify: `skills/job-search-run/scripts/event-log-append.sh:7`
- Modify: `skills/job-search-run/templates/jobs-event.example.json`
- Modify: `skills/job-search-run/SKILL.md:81`
- Modify: `tests/test_mechanics_scripts.py` (the `status`-as-sample-field uses)

**Interfaces:**
- Consumes: nothing from Task 2.
- Produces: an `evaluated` event with no `status` key. Task 4's prose describes this event.

`record-judgment.awk:57` is the only writer of `status` in the repository, and it writes the constant `"new"`. Once Task 2 lands, nothing reads it.

- [ ] **Step 1: Delete the write**

Delete `record-judgment.awk:57`:

```awk
  out = out ",\"status\":\"new\""
```

- [ ] **Step 2: Repoint the field-ordering comment at `record-judgment.awk:5`**

It currently uses `status` as its example of a free-text value that could be mistaken for a field:

> to contain "status": cannot be mistaken for the status field. The reverse case — a dealbreaker

Pick a field that still exists on the event — `match` and `relevant` are both short words that can appear in `reasoning` text — and rewrite the sentence around it. Do not leave an example naming a field the event no longer carries.

- [ ] **Step 3: Correct the `event-log-append.sh` header at `:7`**

It says:

> This is the append path for a `status_changed` event, and for an `evaluated` event on a host that is writing one by hand.

Half of that is now false. The script keeps its purpose: `job-search-run/SKILL.md:75-79` routes every `evaluated` row a run writes through it. Rewrite the sentence to name only the `evaluated` path.

- [ ] **Step 4: Remove `status` from the event template and the field list**

`skills/job-search-run/templates/jobs-event.example.json` carries `"needs_human_check":false,"status":"new"` — delete the `status` pair, keep `needs_human_check`.

`skills/job-search-run/SKILL.md:81` says "`status` starts at `new`." Delete that sentence.

- [ ] **Step 5: Repoint the tests that use `status` as a sample field**

`tests/test_mechanics_scripts.py:64`, `:579-590`, `:1704`, `:1755-1774` use `status` as a sample or asserted key in tests that are not about the pipeline. Swap it for a field the event still carries. These are incidental uses; do not change what each test asserts.

- [ ] **Step 6: Run the tests and the doc gates**

Run: `python3 -m pytest tests/ -q && python3 scripts/doc_lint.py --root . && python3 scripts/philosophy_guard.py --root .`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add skills/job-search-run/scripts/record-judgment.awk skills/job-search-run/scripts/event-log-append.sh \
        skills/job-search-run/templates/jobs-event.example.json skills/job-search-run/SKILL.md \
        tests/test_mechanics_scripts.py
git commit -m "fix(run): stop writing a status field nothing reads"
```

---

### Task 4: The agent-facing prose

**Files:**
- Modify: `skills/job-search/SKILL.md:127-128` (the Home read list), `:139` (the card), `:161` (the reactions table)
- Modify: `skills/job-search-runbook/SKILL.md:54` (the `jobs.jsonl` file-table row)

**Interfaces:**
- Consumes: the three output keys from Task 2, and the event shape from Task 3.

This reopens what Task 12 of the parent plan committed at `7e32a3f`.

- [ ] **Step 1: Replace the Home read list at `:127-128`**

It currently says to read "`jobs.jsonl` folded to one entry per `source` + `source_id` with the last line winning, counting a line that names another posting in `same_role_as` as that one role". Replace with a call to `skills/job-search/scripts/posting-counts.sh <workspace>/jobs.jsonl`, which prints `relevant`, `to_confirm` and `filtered`. The card must not read the log itself: measured 2026-08-07, one run gave a `jobs.jsonl` of 159 lines and 106,263 bytes.

- [ ] **Step 2: Replace the card's Pipeline block at `:139`**

Currently:

```
Pipeline
  new <n> · interested <n> · applied <n> · rejected <n> · archived <n>   (<k> to confirm)
```

Replace with:

```
Matches
  <n> relevant postings found · <k> need your confirmation · <f> filtered out
```

`<n>` is `relevant`, `<k>` is `to_confirm`, `<f>` is `filtered`, each read from the script's output rather than worked out. The other four card blocks — the title, the status line, the latest digest and the next-actions menu — are unchanged.

- [ ] **Step 3: Remove the per-posting reaction row at `:161`**

The row reads:

> | Something about one posting — already applied there, not this company | that posting's line in `jobs.jsonl`: append a `status_changed` event carrying its new `status`. |

Delete the row. The three other rows in that table stay. Do not replace it with a row saying the product cannot do this — the parent plan's constraint against telling an agent "do not X" for something it never does applies.

- [ ] **Step 4: Rewrite the `jobs.jsonl` row in the runbook's file table at `:54`**

The row currently reads:

> `jobs.jsonl` — append-only event log, one JSON object per line. A run writes a `call` event for each agent-data request and `surfaced`, `queued`, `detail` and `evaluated` events about postings; a `status_changed` event records what the user says about one. A posting has several lines, all carrying the same `source` and `source_id`: read them in order, and the last line to carry a field states that field's current value. | every run; the home view for `status_changed` | the home view, the pipeline, duplicate checks

Three changes: drop the `status_changed` clause; change the "written by" cell to `every run`; and replace the field-by-field rule with the simple one that is now true — a posting has several lines sharing its `source` and `source_id`, and its current state is its last `evaluated` line. The "read by" cell drops "the pipeline".

- [ ] **Step 5: Verify every claim against the scripts**

For each script name, flag and printed key the prose states, run the thing and confirm. List each claim with the command that settled it. Do not add a test that greps these files for a phrase — the parent plan forbids it and `evals/behaviors.md:27` sets the same bar.

- [ ] **Step 6: Run the doc gates and record the word counts**

Run: `python3 scripts/doc_lint.py --root . && python3 scripts/philosophy_guard.py --root . && python3 -m pytest tests/ -q`
Run: `wc -w skills/*/SKILL.md` — record the corpus total in the commit message. The glob covers every skill once; do not also name a file, which counts it twice.

- [ ] **Step 7: Commit**

```bash
git add skills/job-search/SKILL.md skills/job-search-runbook/SKILL.md
git commit -m "docs(skills): show what the filtering found instead of a pipeline"
```

---

### Task 5: Evals, seeds and the repo docs

**Files:**
- Modify: `skills/job-search/evals/evals.json:62,64,65,134`
- Modify: `evals/seeds/schedule/jobs.jsonl` (and any other seed carrying `"status"`)
- Modify: `TESTING.md:236-237,282-285,297,303,675,915`
- Modify: `tests/test_eval_harness.py:278,306,350,394,397`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Repoint the eval-harness fixture**

`tests/test_eval_harness.py` uses `status_changed` as a generic sample event type in a fixture that is not about the pipeline. Swap it for a real event type — `surfaced` or `queued`. Do not change what the tests assert.

- [ ] **Step 2: Fix the two home-view eval expectations**

`skills/job-search/evals/evals.json:64` says the card shows "…then the pipeline counts, then the next-actions menu" — rename the block. `:65` says "The pipeline counts are the fold of jobs.jsonl by source and source_id with the last line winning, and the human-check count matches the seeded two" — replace with an expectation that reads whatever `posting-counts.sh` prints rather than a hand-worked number, plus the human-check count.

`:62`'s prompt seeds "nine postings across the five statuses with two carrying needs_human_check true", which is no longer reachable — `record-judgment.awk` is the only writer and every judgment is the same. Reseed it as nine judged postings, some relevant and some not, two carrying `needs_human_check` true.

- [ ] **Step 3: Drop sub-reaction (b) from scenario 13**

Scenario 13, "feedback lands at the scope it belongs to", drives four separate sessions with one reaction each. Only (b) is about `status_changed`. The owner decided on 2026-08-07 to drop it.

Delete from the prompt at `:131`: `(b) 'already applied at Northwind, drop that one';`

Delete the matching expectation at `:134`: `"(b) appends one status_changed event for that posting to jobs.jsonl and leaves preferences.md byte-for-byte unchanged",`

Keep (a), (c) and (d) exactly as written — they grade preference routing, the one-question rule and config edits, none of which this removal touches. Do not relabel (c) and (d); renaming them to (b) and (c) would make the scenario's four-session prompt and its expectations disagree with every prior eval result under `evals/results/`.

- [ ] **Step 4: Clean the seeds**

`evals/seeds/schedule/jobs.jsonl` carries `"status":"new"` on 3 lines. Remove the key from every seed event so the seeds match what `record-judgment.awk` now writes. Run `grep -rn '"status"' evals/seeds/` and confirm it returns nothing.

- [ ] **Step 5: Fix `TESTING.md`**

`:282-285` is scenario T4.6, "Mark a job's status", which tests a behavior that no longer exists — delete the scenario. `:236-237`, `:297`, `:303` and `:915` reference the pipeline or the status row; `:675` uses `"status":"new"` as a sentinel. Rewrite each against what the product does now.

- [ ] **Step 6: Write the CHANGELOG entry**

In the file's existing Keep a Changelog shape, under `## [Unreleased]`, say what changed for someone using the pack: the home card now reports how many relevant postings the filtering found and how many it filtered out, and per-posting status tracking has been removed. Do not invent a version number; the parent plan's Task 16 owns the version bump.

- [ ] **Step 7: Verify nothing is left**

Run: `grep -rn status_changed skills/ tests/ evals/ --include='*' | grep -v evals/results/`
Expected: no output. `evals/results/` is excluded because those are historical run transcripts — 31 files, 37 occurrences, 129 run directories, all left as written.

Run: `python3 -m pytest tests/ -q && python3 scripts/eval_harness.py --root . && python3 scripts/doc_lint.py --root . && python3 scripts/philosophy_guard.py --root .`
Expected: clean. `eval_harness.py` is not a CI job, so nothing else catches a malformed scenario file.

- [ ] **Step 8: Commit**

```bash
git add skills/job-search/evals/evals.json evals/seeds/ TESTING.md tests/test_eval_harness.py CHANGELOG.md
git commit -m "test(evals): grade the home card on what the filtering found"
```

---

## What the parent plan does after this lands

Its execution resumes at Task 13. Task 13 is unaffected — its Step 1 already names only `call`, `surfaced`, `queued`, `detail` and `evaluated`. Task 14 loses its Step 3 (Task 1 Step 3 above deletes it) and its Step 1 is done by Task 4 above. Task 16 keeps its rewrite table minus the rows this plan owns. It no longer gains `TESTING.md:284`: that line was the verify step of scenario T4.6, which Task 5 of this plan deleted whole, and `:284` now falls inside T4.7. Task 16 instead gains `TESTING.md:93`, `:104` and `:922`, which state the suite size as 429 where `python3 -m pytest tests/ -q --collect-only` gives 937. Task 17 Step 4's home-view assertion is done by Task 5 above.

Task 12 of the parent plan, committed at `7e32a3f`, is superseded in part by Task 4 above and stays otherwise as written.
