# Who owns what — the skill boundary

**Load this when:** you are about to search the job source, judge a posting, or write a run artifact,
and you are not certain the skill you are in owns that action.

Each skill below owns its column exclusively. The boundary is drawn by **action**, not by whether the
invocation happens to be interactive: an interactive pull is still a pull, and a verdict reached in
conversation is still a verdict.

<!-- ownership-contract:skill-roles -->
| Skill | Exclusively owns | Never | Instead |
|---|---|---|---|
| `job-search` | setup, status, the home view, routing, applying the config changes a user asks for in conversation, feedback routing | calls the job source · judges a posting · writes `jobs.jsonl`, `runs/*.json`, or a digest | invoke `job-search-run` for the pull — it writes those artifacts; invoke `evaluate-job-fit` for a verdict |
| `job-search-run` | preflight, metered calls, orchestration, validated persistence, finalization | produce a fit verdict from its own rubric (one bounded exception: **Triage is not a verdict**, below) | route every semantic judgment to `evaluate-job-fit` |
| `evaluate-job-fit` | relevance, must-have assessment, band, reasoning, dealbreakers, unknowns | write workspace state or change retrieval configuration | return the envelope; the coordinator persists it |
| `job-preference-interview` | the Job Preferences Brief's content — building, refining, deepening, and importing it | judge a posting against the brief it just wrote · call the job source · change retrieval configuration | invoke `evaluate-job-fit` for a verdict; the front door applies config changes |
| `job-search-agent` | explaining how the system works, troubleshooting a run, and the customization and extension playbooks | run a search · judge a posting · write run artifacts | invoke `job-search-run` for a pull; invoke `evaluate-job-fit` for a verdict |
| mechanics scripts | schema, append, fold, and binding validation | make a semantic fit or query-quality judgment | fail closed and return to the caller |
<!-- /ownership-contract:skill-roles -->

Read the `Never` column down and the same two prohibitions recur — they are what this contract is
actually for: **searching the job source belongs to `job-search-run`, and a fit verdict belongs to
`evaluate-job-fit`.** Every skill that owns neither carries both prohibitions. (`evaluate-job-fit` reads
one posting's detail to judge it; reading one posting is not a search.) `job-search-agent` owns the manual
for what is configurable and how; `job-search` is where a config change the user asks for gets applied.

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
`location_display` reading onsite-Chicago against a remote-US must-have. The structured fields are the
search-row fields named in
[agent-data-contract.md § Route: search-jobs](agent-data-contract.md#route-search-jobs); a description
snippet is not one of them. When the contradiction is not unambiguous from the field's literal value, the
posting **queues for the judge** — as does anything needing interpretation: domain fit, seniority,
culture, stage.

Mechanical duplicate and malformed-record rejection stay with the runner and the validators, because
neither is a fit judgment.
