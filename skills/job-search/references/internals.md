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
  "scheduling": { "installed": true, "mechanism": "cron|launchd|loop", "set_at": "<iso>" } }
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
- **Change frequency:** set `schedule.frequency` to one of `hourly | every-2-hours | every-6-hours | daily | weekly`.
- **Change run time:** set `schedule.time` (HH:MM, used for daily/weekly).
- Always keep `version: 1`. NEVER add a budget, cost, or score/weight field (philosophy).

## Scheduling setup (offer to set it up; consent + marker; always show the copy-paste fallback)
Generate the artifact deterministically: `python3 "$OS" schedule-line --frequency <f> --time <t> --workspace <ws>`
(cron), or `python3 "$OS" launchd-plist --frequency <f> --time <t> --workspace <ws>` (macOS robust). Explain
the options, ask a yes/no, and ONLY on yes perform the privileged write (append the crontab line, or write the
plist to `~/Library/LaunchAgents/dev.jobsearchos.run.plist` and `launchctl load` it). Then record it:
`python3 "$OS" set-scheduled --mechanism <cron|launchd|loop>`. Check `schedule-status` so you never re-ask.
ALWAYS also print this copy-paste fallback verbatim:

```
OPTION A — OS cron (recommended; runs even when Claude is closed)
  crontab -e  →  0 8 * * *  cd ~/.job-search && claude -p "/job-search-run" >> ~/.job-search/runs/cron.log 2>&1
       (an hourly frequency would generate `0 * * * *`, etc. — setup writes the line matching your choice)
  • Verify now:  cd ~/.job-search && claude -p "/job-search-run"
  • macOS: the Mac must be awake at run time — keep it on, use `caffeinate`, or install the launchd plist
    (StartCalendarInterval can wake the machine — the robust mac option).
OPTION B — keep Claude open and loop:  /loop <frequency> /job-search-run
Not sure? Use Option A.
```

## osctl.py command reference
`resolve` · `set-active --workspace P` · `schedule-line --frequency F [--time T] [--workspace W]` ·
`launchd-plist --frequency F [--time T] [--workspace W]` · `schedule-status` · `set-scheduled --mechanism M`.
All accept `--registry P` (and resolve accepts `--default-workspace`/`--legacy-workspace`) for tests/evals.
