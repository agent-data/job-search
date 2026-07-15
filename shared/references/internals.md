# OS internals — registry, workspace discovery, config & scheduling

The "OS state" that survives across sessions so any skill finds the user's data identically. The host agent performs these procedures itself, with its own file-read/write and shell
tools, plus the exact shell lines below. Never hard-code or re-derive the
paths and precedence rules — follow the procedures as written; they are the contract every skill shares.

## Registry (machine-managed OS state — JSON, not YAML)
Location (tests/evals redirect it via `$JOBSEARCH_OS_REGISTRY`):
```bash
REG="${JOBSEARCH_OS_REGISTRY:-${XDG_CONFIG_HOME:-${JOBSEARCH_OS_HOME:-$HOME}/.config}/job-search/config.json}"
```
i.e. `~/.config/job-search/config.json` by default. Schema:
```json
{ "version": 1,
  "active_workspace": "/Users/<u>/.job-search",
  "scheduling": { "installed": true, "mechanism": "loop", "set_at": "<iso>" },
  "deeper_coverage_nudges": {
    "/Users/<u>/.job-search": {
      "workspace": "/Users/<u>/.job-search",
      "shown_at": "<iso>",
      "outcome": "enabled|declined|deferred"
    }
  } }
```
The registry is machine state; the workspace's `config.yaml` stays the user-facing config.

The resolved `$REG` is **the one and only registry**: evaluate the expression in Bash and use the path it
prints for every read and write. Never consult or touch any other location — in particular, when
`$JOBSEARCH_OS_REGISTRY` resolves it elsewhere, the default `~/.config/...` path is out of bounds entirely
(reading it can only mix two registries and confuse the result).

**Write rules (every structured-state whole-file write).** These govern the registry `config.json` and the
workspace `config.yaml` alike. Read the current file first (it may not exist), apply the change to the
parsed object, and write the **whole file back atomically** — a full replace in place, never a streamed,
redirected, or partial write that can truncate or interleave a structured-state file. Use your host's
whole-file write tool; where none is guaranteed-atomic, write to a temp file then `mv` it into place.
Appending one immutable line to the event log (`jobs.jsonl`) stays a legitimate shell `>>` append (a heredoc
keeps quoting safe). For the registry, write at the resolved `$REG` path; preserve any keys you don't own;
always keep `"version": 1`; store `active_workspace` as an absolute path (expand `~`); 2-space indent;
trailing newline; `mkdir -p` the parent directory first.
If the file exists but is not valid JSON, stop and tell the user (offer to rewrite it from the known
workspace) — never guess or silently fall through; guessing could switch workspaces. Only the **job-search**
front door (onboarding / adoption) and the scheduling flows write the registry; the headless runner never
does.

- **Record the active workspace** (adoption and onboarding both end here): merge
  `{"version": 1, "active_workspace": "<abs path>"}` per the write rules. This writes ONLY the registry; it
  never touches workspace files.
- **Read the scheduling marker:** the registry's `scheduling` object, defaulting to
  `{"installed": false, "mechanism": null, "set_at": null}` when absent.
- **Set the scheduling marker** (a recurring run was started): merge
  `"scheduling": {"installed": true, "mechanism": "<active mechanism>", "set_at": "<UTC ISO>"}` — record the
  mechanism actually used: a short token for the scheduler the agent bound the run to (an unattended
  `cron`/`launchd` schedule, or `loop` for the in-session fallback). Take the timestamp
  from `date -u +%Y-%m-%dT%H:%M:%S+00:00`.
- **Clear the scheduling marker** (turn-off): merge
  `"scheduling": {"installed": false, "mechanism": null, "set_at": null}`.
- **Read the deeper-coverage nudge marker for workspace W:** expand W to its absolute path and look up that
  exact path in `deeper_coverage_nudges`; absence means no marker. The map is per absolute workspace, not
  global, and each marker's `workspace` value must equal its map key.
- **Set the deeper-coverage nudge marker:** only the **job-search home view**, after it actually displays the
  evidence-backed deeper-coverage nudge, merges
  `"deeper_coverage_nudges": {"<absolute W>": {"workspace":"<absolute W>", "shown_at":"<UTC ISO>", "outcome":"enabled|declined|deferred"}}`.
  Use `enabled` when the user enables deeper coverage, `declined` when they decline, and `deferred` when they
  leave it for later. The runner never writes this shown marker. A present marker suppresses later automatic
  nudges for that workspace, including after decline or deferral; the user can still request deeper coverage.
  Apply the ordinary registry write rules: merge into the current object, preserve every unknown registry
  key, and atomically replace the whole file.

## Workspace discovery & first-run detection
**Run the shared script where a shell runtime exists:** `../scripts/mechanics/workspace-discovery.sh` prints
three lines — `workspace=<abs path>`, `source=<registry|default|legacy|none>`, `first_run=<true|false>` —
reproducing the precedence below EXACTLY (pinned by `tests/test_mechanics_scripts.py`), honoring `$REG`/`$H`
as defined here. **Where there is no shell runtime, gather the facts and apply the precedence in-model.**

**Corrupt-registry guard (a caller MUST check this before trusting discovery's result).** The script
grep-extracts `active_workspace` and CANNOT detect a corrupt-but-non-grepable registry — a corrupt file
would make it silently fall through to default/first-run, the "guessing could switch workspaces" hazard the
Registry write-rules warn against. Robust JSON validation is out of the zero-dependency script's scope by
design, so this check lives in the caller's prose: before trusting the result, confirm the registry file (if
present) parses as JSON; a **present-but-unparseable** registry is the corrupt-registry case above — never
guess, never fall through. The **headless runner** maps it to **E-BAD-REGISTRY** (`errors.md`, HALT); the
**job-search** front door offers to rewrite it from the known workspace.

Gather the facts with one command, then apply the precedence rules:
```bash
REG="${JOBSEARCH_OS_REGISTRY:-${XDG_CONFIG_HOME:-${JOBSEARCH_OS_HOME:-$HOME}/.config}/job-search/config.json}"
H="${JOBSEARCH_OS_HOME:-$HOME}"
echo "registry: $REG"; cat "$REG" 2>/dev/null
test -f "$H/.job-search/config.yaml" && echo DEFAULT_HAS_CONFIG
test -f "$H/job-search/config.yaml"  && echo LEGACY_HAS_CONFIG
```
The printed `registry:` path is the one to use for any later registry write in this session.
First match decides — the result is a workspace path, a `source`, and whether this is a **first run**:
1. The registry parses and has a non-empty `active_workspace` W → workspace = W, source `registry`;
   first-run only if W has no `config.yaml` (check: `test -f "<W>/config.yaml"`). **The registry wins
   unconditionally — never fall through to the other candidates, even when W lacks `config.yaml`** (falling
   through could silently switch the user's workspace).
2. `DEFAULT_HAS_CONFIG` → workspace `$H/.job-search`, source `default`, not a first run.
3. `LEGACY_HAS_CONFIG` → workspace `$H/job-search`, source `legacy`, not a first run.
4. Otherwise **first run**: workspace = `$H/.job-search` (not yet created), source `none`.

First-run = no candidate workspace has a `config.yaml`. (`$JOBSEARCH_OS_HOME` redirects the home base for
tests/evals.)

## Never-clobber adoption
If discovery lands on the legacy workspace (or you otherwise find an existing workspace), **adopt** it:
record it as the active workspace in the registry (write rules above — only the registry is written). NEVER
overwrite an existing `config.yaml`, `preferences.md`, or `jobs.jsonl`; only additively create missing
`runs/` and `reports/`. Tell the user: "Found an existing workspace at <path> — using it."

## Config read/update recipes (conversational-first; config.yaml is YAML)
The user changes config by **chatting**; manual editing is an escape hatch. To apply a change, read
`<workspace>/config.yaml`, edit it minimally (preserve comments/structure), and write it back.
- **Add a query:** append to `queries:` an item like
  `  - { id: "ml-platform-sf", keywords: "ML platform engineer", location: "San Francisco Bay Area", limit: 25, enabled: true }`
  When the user hasn't named keywords (onboarding, or a vague "add another search"), **derive** them from
  `preferences.md` — role/title + domain terms for `keywords`, the brief's location constraints for
  `location` — then **acknowledge** what you saved rather than asking them to pick.
- **Tune the feed (`search` block):** `search.freshness` narrows or widens the recency filter on
  `posted_at`/`published_at` (server-side via `published_on_or_after`, with a client-side fallback);
  `search.detail_model` picks the portable tier the runner's
  per-posting detail reads use — the allowed values for each (the freshness windows and the detail tiers) live
  in `conventions.md`; the agent binds each tier to a concrete model from its own roster — the least-powerful
  model that does the task well; the fit verdict is a judgment, so never the cheapest.
  `search.parallel_detail_reads` is optional: unset
  means an interactive front-door flow may ask whether to use parallel subagents where the host requires
  explicit approval; `true` means the user approved; `false` means use sequential detail reads. Only
  conversational front-door flows write this preference; the headless runner reads it and never changes config.
  `queries[].limit` is the per-query feed size (its range and default live in `conventions.md`).
- **Choose job sources:** set `search.sources` — an ordered list from the contract's source enum
  (see `agent-data-contract.md`); omit the key for the default `["linkedin", "ashby"]`. The default is
  `["linkedin", "ashby"]`; add `"greenhouse"` and/or `"lever"` to search more public company boards. One
  source failing never blocks the others.
  Only conversational flows write this; the headless runner reads it and never changes config.
- **Derive "remote" into the query:** `search-jobs` has no remote flag, so when the brief requires remote (or
  rejects onsite-elsewhere), fold `remote` into the query `keywords` and/or set `location` to the brief's allowed
  geographies — otherwise the feed fills with onsite roles the judge then filters out.
- **Choose one-off or saved review depth:** interpret the user's time scope before changing anything. The
  accepted `search.max_new_postings_per_run` values and exact run-record fields live in `conventions.md`;
  `queries[].limit` remains each query/source call's page size, not a run total.

  | User wording | Interpretation | Config write |
  |---|---|---|
  | “now,” “once,” “this run” | one-off finite, exhaustive, or first-page override | none |
  | “each run,” “from now on,” “every time” | saved setting | write the positive integer or exact `"all"` only after preview and confirmation |
  | ambiguous “scan everything” or depth request | default to one run and say that scope before confirmation | none |
  | “go back to normal,” “use first-page coverage” | remove the saved key or use a one-off first-page override, according to the explicit time scope | remove immediately when saved |

  Before any one-off or saved enablement/increase (`first_page → finite`, larger finite target, or
  `finite → all`), first preview the exact requested scope and the known call model, then ask for explicit
  confirmation, and only after a yes run once or atomically write config. The preview explains that ordinary
  first pages depend on enabled queries × enabled sources; every continuation board page and full-posting read
  is another metered operation; a finite target bounds unique roles judged rather than continuation calls;
  and `"all"` has no reliable call ceiling in advance. Consult `agent-data-contract.md` for the canonical
  dated metering/rate facts; do not copy a volatile rate into this recipe or invent account state.

  A saved value is durable consent, so scheduled/headless runs use it without prompting. A one-off override
  records `review_scope.origin:one_off` in the run but never mutates config. Decreasing a finite target,
  changing `all → finite`, removing the key, or choosing a one-off first-page override is reversible and
  immediate; make that reduction without confirmation. Always keep config `version: 1`.
- **Explain my agent-data usage (read-only):** read the workspace's `runs/*.json` records and explain actual
  `agent_data_usage` call totals, the recorded pay-as-you-go equivalent when present, the operation breakdown,
  and the configured outcome drivers (frequency, enabled sources/queries, and review mode). Use the decimal
  strings stored with each historical run; point to `agent-data-contract.md` for current canonical
  metering/pricing context. Do not write config or registry state, make an API call, infer a current balance or
  plan, or relabel the recorded equivalent as an actual charge.
- **Change frequency:** set `schedule.frequency` to one of `hourly | every-2-hours | every-6-hours | daily | weekly`
  (the cadence→cron mapping the active scheduler uses is composed in → Scheduling setup below).
- **Change run time:** set `schedule.time` (HH:MM, used for daily/weekly).
- Always keep `version: 1`. NEVER add a score or weight field (philosophy).

## Scheduling setup
**Advocate an unattended schedule** for the recurring run — one that keeps firing with **no interactive
session open** — on the host's or the OS's own scheduler that survives session-close (a `cron` or `launchd`
job, or the host's native unattended scheduler); where that scheduler can re-fire a run missed while the
machine slept, prefer it. The agent composes the schedule for its own host — there is no per-host recipe to
look up. Advocate it because an in-session loop stops the instant the session closes, so the overnight and
next-morning runs — the ones that matter most — silently never happen. When the host has **no** unattended
scheduler, or the user declines the machine change, offer an **in-session loop** — a recurring run driven
from inside an open session that installs nothing but runs **only while a session is open** — as the **named
fallback**. On either path, **cloud schedulers do not qualify**: a cloud runner can't see the local
`~/.job-search` workspace or the local agent-data auth, so a run there reaches neither the user's data nor
their credentials and produces nothing — the test any candidate scheduler must pass. (Full doctrine, consent
framing, and canary spec: the operator manual's `scheduling-and-consent.md`.)

The ACTIONS are the same across hosts; the agent binds each to its own host. Compose the cadence from
`schedule.frequency`. **Compose the five-field cron time expression with the shared script where a shell
runtime exists:** `../scripts/mechanics/schedule-line.sh <frequency> [HH:MM]`
prints `minute hour day-of-month month day-of-week` for the cadence; the host then wraps it with its own
command/launchd or interval translation. **Fallback (no shell runtime) — compose it directly:**
`hourly → 0 * * * *`; `every-2-hours → 0 */2 * * *`; `every-6-hours → 0 */6 * * *`;
`daily HH:MM → <m> <h> * * *`; `weekly HH:MM → <m> <h> * * 1` (**weekly day-of-week = Monday, `1`**).
`schedule.time` (`HH:MM`) is honored for daily/weekly and its **default is `08:00`**; strip a single leading
zero so cron gets `8`/`5`, not `08`/`05`. (Both soft-defaults — Monday for weekly, `08:00` for the time —
match the script and are pinned by `tests/test_mechanics_scripts.py`.) Offer scheduling as a yes/no; check
the scheduling marker first so you never re-ask. On yes — after showing the user the exact machine change —
start the **unattended schedule** (the in-session loop only as the fallback above). ALWAYS also **compose the
recurring-run recipe and the one-off-run recipe for the host** and show both to the user verbatim, so they
can re-run the search on demand and stop or restart the schedule themselves.

**Verify before recording — the canary (mandatory).** Before recording the scheduling marker, verify the
schedule works. For the **unattended schedule**, use the **config-time canary**: **registration** (it appears
in the host scheduler's job list) + one **real run through the exact scheduled invocation** (its own
permissions/env, not this session's) proving a fresh `runs/<id>.json` (`run_health` ≠ `blocked`), agent-data
reached, and workspace written; on failure, diagnose + consent-gated fix + re-run; **never record the marker
until the canary is green**. The **in-session-loop fallback** (`mechanism: loop`) can satisfy neither canary
layer — it registers in no scheduler job list and its run *is* this session — so verify it differently:
confirm its **first in-session fire** leaves a fresh run record, then record the marker. Full consent-framed
flow: the operator manual's `scheduling-and-consent.md` §the canary. Only then set the scheduling marker
(write rules above — recording the mechanism actually used).

To turn scheduling off, stop the active schedule, then clear the scheduling marker (write rules above — no
more stale `installed: true`).
