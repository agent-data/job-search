# Who owns what — the skill boundary

**Load this when:** you are about to search the job source, judge a posting, or write a run artifact,
and you are not certain the skill you are in owns that action.

Each skill below owns its column exclusively. The boundary is drawn by **action**, not by whether the
invocation happens to be interactive: an interactive pull is still a pull, and a verdict reached in
conversation is still a verdict.

<!-- ownership-contract:skill-roles -->
| Skill | Exclusively owns | Never | Instead |
|---|---|---|---|
| `job-search` | setup, status, the home view, routing, config edits, feedback routing | calls the job source · judges a posting · writes `jobs.jsonl`, `runs/*.json`, or a digest | invoke `job-search-run` for the pull; invoke `evaluate-job-fit` for a verdict |
| `job-search-run` | preflight, metered calls, orchestration, validated persistence, finalization | produce a fit verdict from its own rubric | route every semantic judgment to `evaluate-job-fit` |
| `evaluate-job-fit` | relevance, must-have assessment, band, reasoning, dealbreakers, unknowns | write workspace state or change retrieval configuration | return the envelope; the coordinator persists it |
| mechanics scripts | schema, append, fold, and binding validation | make a semantic fit or query-quality judgment | fail closed and return to the caller |
<!-- /ownership-contract:skill-roles -->

## When an owner is unavailable

Stopping is the sanctioned outcome; substituting yourself is not.

- **The runner is unavailable** → the front door stops and names the repair. It does not imitate the
  runner: a hand-rolled search writes no ledger, so nothing downstream can tell the result from a real
  run.
- **The judge is unavailable** → the runner stops semantic evaluation. It uses no inline mini-rubric:
  a second rubric is a second source of truth, and the two drift the moment either is edited.

## Triage is not a verdict

The runner's cheap summary scan is a cost saving, not a judgment, so it is bounded. It may reject a
posting only when a **structured summary field explicitly contradicts a must-have** — a
`location_display` reading onsite-Chicago against a remote-US must-have. Anything needing
interpretation — domain fit, seniority, culture, stage — **queues for the judge**.

Mechanical duplicate and malformed-record rejection stay with the runner and the validators, because
neither is a fit judgment.
