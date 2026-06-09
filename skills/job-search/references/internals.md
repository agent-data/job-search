# OS internals — registry, workspace discovery, config & scheduling

The "OS state" that survives across sessions so any skill finds the user's data identically. Deterministic
parts live in `scripts/osctl.py` (bundled into each skill at `scripts/osctl.py`; resolve its absolute path
from the skill's own directory and call it as `$OS`, exactly like `$STATE`). Never hard-code or re-derive
the paths below — call `osctl.py`.

## Registry (machine-managed OS state — JSON, not YAML)
Location: `$XDG_CONFIG_HOME/job-search-os/config.json`, i.e. `~/.config/job-search-os/config.json`
(fallback `~/.job-search-os/config.json` when `~/.config` is unavailable). Tests/evals redirect it with
`$JOBSEARCH_OS_REGISTRY`. Schema:
```json
{ "version": 1,
  "active_workspace": "/Users/<u>/.job-search",
  "scheduling": { "installed": true, "mechanism": "loop", "set_at": "<iso>" } }
```
The registry is machine state; the workspace's `config.yaml` stays the user-facing config.

## Workspace discovery & first-run detection
`python3 "$OS" resolve` -> `{"workspace": "<abs>", "first_run": <bool>, "source": "registry|default|legacy|none"}`.
Order: registry `active_workspace` (if it has `config.yaml`) -> `~/.job-search/` (if `config.yaml`) ->
legacy `~/job-search/` (if `config.yaml`) -> else **first-run** (workspace = `~/.job-search/`, not yet created).
First-run = no candidate workspace has a `config.yaml`.

## Never-clobber adoption
If `resolve` returns `source: "legacy"` (or you otherwise find an existing workspace), **adopt** it:
`python3 "$OS" set-active --workspace <path>` (writes only the registry). NEVER overwrite an existing
`config.yaml`, `preferences.md`, or `jobs.jsonl`; only additively create missing `runs/` and `reports/`.
Tell the user: "Found an existing workspace at <path> — using it."

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
  (`haiku | sonnet | opus | inherit` — the model the runner's per-posting detail subagents use). `queries[].limit`
  (1–100, default 25) is the per-query feed size.
- **Derive "remote" into the query:** `search-jobs` has no remote flag, so when the brief requires remote (or
  rejects onsite-elsewhere), fold `remote` into the query `keywords` and/or set `location` to the brief's allowed
  geographies — otherwise the feed fills with onsite roles the judge then filters out.
- **Pull as many NEW as possible:** there's no pagination and re-runs reorder, so breadth + frequency + dedup do
  the work, not a giant single pull — keep `limit` sensible (default 25, up to 100), run several varied queries
  (role synonyms, key locations, remote variants), run often, and dedup; distinct postings accumulate across runs.
- **Change frequency:** set `schedule.frequency` to one of `hourly | every-2-hours | every-6-hours | daily | weekly`.
- **Change run time:** set `schedule.time` (HH:MM, used for daily/weekly).
- Always keep `version: 1`. NEVER add a budget, cost, or score/weight field (philosophy).

## Scheduling setup (native `/loop` — nothing is installed on the user's machine)
Job Search OS schedules with Claude Code's native **`/loop`**: it re-runs the search on an interval inside an
open Claude session. There is **no privileged write** — no crontab, no launchd, nothing on the user's machine.
The one tradeoff: it runs only while a Claude session is open.

Get the artifact deterministically: `python3 "$OS" loop-command --frequency <f>` → prints
`/loop <interval> /job-search-run` (hourly→`1h`, every-2-hours→`2h`, every-6-hours→`6h`, daily→`24h`,
weekly→`168h`; `schedule.time` is informational under /loop — the loop fires on an interval from when it's
started). **Match the /loop target to the install:** plugin skills are only invocable namespaced, so when
these skills run as a plugin (this skill appears as `job-search-os:…` in your skill list — the usual
install), add `--namespace job-search-os` so it prints `/loop <interval> /job-search-os:job-search-run`;
loose skills copied into `~/.claude/skills/` use the bare form. Offer it as a yes/no; on yes, run that
`/loop` command and record it with `python3 "$OS" set-scheduled` (mechanism `loop`). Check
`schedule-status` so you never re-ask. ALWAYS also show this recipe verbatim (in the form for THIS install)
so the user can start or restart it themselves:

```
Recurring (runs while a Claude session is open — nothing installed on your machine):
  /loop <interval> /job-search-os:job-search-run      # hourly → 1h · daily → 24h · weekly → 168h
One-off run anytime:
  /job-search-os:job-search-run
```

(For loose-skill installs, drop the `job-search-os:` prefix from both lines.)

To turn scheduling off: stop the loop (end the session, or cancel the pending wakeup), then
`python3 "$OS" set-unscheduled` (clears the marker — no more stale `installed: true`).

### Safety net: the scheduling guard hook

A PreToolUse hook (`hooks/guard-scheduled-tasks.py`) is a defense-in-depth backstop, not part of the normal
flow. Scheduling is native `/loop`, so the model never needs to touch the machine — the guard therefore
**denies** any model-initiated `crontab`/launchd *install* and points back to `/loop`. It defers everything
else: reads (`crontab -l`), removals, `/loop` itself, and commands that merely *mention* these words (a
`grep`, an `echo`). The user stays free to run cron/launchd by hand in their own shell — the guard only gates
the agent's Bash tool calls.

## osctl.py command reference
`resolve` · `set-active --workspace P` · `loop-command --frequency F [--namespace job-search-os]` ·
`schedule-status` · `set-scheduled [--mechanism loop]` · `set-unscheduled`.
All accept `--registry P` (and resolve accepts `--default-workspace`/`--legacy-workspace`) for tests/evals.
