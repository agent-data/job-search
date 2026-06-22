# OS internals — registry, workspace discovery, config & scheduling

The "OS state" that survives across sessions so any skill finds the user's data identically. There is no
helper script: the host agent performs these procedures itself, with its file tools (see your platform's
adapter → Tool map / Whole-file write) and the exact shell lines below. Never hard-code or re-derive the
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
  "scheduling": { "installed": true, "mechanism": "loop", "set_at": "<iso>" } }
```
The registry is machine state; the workspace's `config.yaml` stays the user-facing config.

The resolved `$REG` is **the one and only registry**: evaluate the expression in Bash and use the path it
prints for every read and write. Never consult or touch any other location — in particular, when
`$JOBSEARCH_OS_REGISTRY` resolves it elsewhere, the default `~/.config/...` path is out of bounds entirely
(reading it can only mix two registries and confuse the result).

**Write rules (every registry write).** Read the current file first (it may not exist), apply the change to
the parsed object, and write the whole file back atomically at the resolved `$REG` path — a full replace in
place (see your platform's adapter → Whole-file write), never a streamed or redirected partial, which can
truncate or interleave a structured-state file. Preserve any keys you don't own; always keep `"version": 1`;
store `active_workspace` as an absolute path (expand `~`); 2-space indent; trailing newline; `mkdir -p` the
parent directory first.
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
  mechanism actually used (see your platform's adapter → Scheduling for its value), and take the timestamp
  from `date -u +%Y-%m-%dT%H:%M:%S+00:00`.
- **Clear the scheduling marker** (turn-off): merge
  `"scheduling": {"installed": false, "mechanism": null, "set_at": null}`.

## Workspace discovery & first-run detection
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
- **Tune the feed (`search` block):** `search.freshness` (`any | past-week | past-2-weeks | past-month` — a
  client-side recency filter on `posted_at`; the API has no date param) and `search.detail_model`
  (`fast | balanced | high | inherit` — a portable tier token the runner's per-posting detail reads use; the
  literal model each maps to lives in your platform's adapter → Model tiers, and the fan-out itself defers to
  → Concurrent detail reads). `queries[].limit` (1–100, default 25) is the per-query feed size.
- **Derive "remote" into the query:** `search-jobs` has no remote flag, so when the brief requires remote (or
  rejects onsite-elsewhere), fold `remote` into the query `keywords` and/or set `location` to the brief's allowed
  geographies — otherwise the feed fills with onsite roles the judge then filters out.
- **Pull as many NEW as possible:** there's no pagination and re-runs reorder, so breadth + frequency + dedup do
  the work, not a giant single pull — keep `limit` sensible (default 25, up to 100), run several varied queries
  (role synonyms, key locations, remote variants), run often, and dedup; distinct postings accumulate across runs.
- **Change frequency:** set `schedule.frequency` to one of `hourly | every-2-hours | every-6-hours | daily | weekly`
  (the cadence→interval mapping for the active scheduler lives in your platform's adapter → Run recipe).
- **Change run time:** set `schedule.time` (HH:MM, used for daily/weekly).
- Always keep `version: 1`. NEVER add a score or weight field (philosophy).

## Scheduling setup
Schedule the recurring run on the cadence the user picks, using the host's scheduler — the MECHANISM lives in
your platform's adapter → Scheduling. Read it: it is **two-tier**. **Tier 1** — a native LOCAL scheduler
(consent-based, installs nothing on the user's machine): use it where the adapter names one. **Tier 2** — no
native local scheduler: a consent-gated machine-level cron/launchd schedule is the **sanctioned fallback** —
only on an explicit user yes, with the exact line shown before it is written, never silent, never
auto-installed, and user-removable. A cloud scheduler that cannot see the local `~/.job-search` workspace or
the local agent-data auth does **not** qualify on either tier — it is skipped (a run that cannot reach the
user's data and credentials produces nothing).

The ACTIONS are the same across hosts. Compose the cadence from `schedule.frequency` (the adapter's Run
recipe carries the cadence→interval/cron mapping). Offer scheduling as a yes/no; check the scheduling marker
first so you never re-ask. On yes, start the schedule and set the scheduling marker (write rules above —
recording the mechanism actually used). ALWAYS also show the **recurring-run recipe** and the **one-off-run
recipe** verbatim — copy them exactly as written in your platform's adapter → Run recipe; do not reconstruct
those tokens here.

To turn scheduling off, stop the active schedule (the adapter's Scheduling section gives the teardown for
Tier 1 vs Tier 2), then clear the scheduling marker (write rules above — no more stale `installed: true`).
