# OS internals — registry, workspace discovery, config & scheduling

The "OS state" that survives across sessions so any skill finds the user's data identically. There is no
helper script: Claude Code performs these procedures itself, with the file tools (Read/Write) and the exact
shell lines below. Never hard-code or re-derive the paths and precedence rules — follow the procedures as
written; they are the contract every skill shares.

## Registry (machine-managed OS state — JSON, not YAML)
Location (tests/evals redirect it via `$JOBSEARCH_OS_REGISTRY`):
```bash
REG="${JOBSEARCH_OS_REGISTRY:-${XDG_CONFIG_HOME:-${JOBSEARCH_OS_HOME:-$HOME}/.config}/job-search-os/config.json}"
```
i.e. `~/.config/job-search-os/config.json` by default. Schema:
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
the parsed object, and Write the whole file back with the file tools — never shell redirection — at the
resolved `$REG` path. Preserve any keys you don't own; always keep `"version": 1`; store `active_workspace`
as an absolute path (expand `~`); 2-space indent; trailing newline; `mkdir -p` the parent directory first.
If the file exists but is not valid JSON, stop and tell the user (offer to rewrite it from the known
workspace) — never guess or silently fall through; guessing could switch workspaces. Only the **job-search**
front door (onboarding / adoption) and the scheduling flows write the registry; the headless runner never
does.

- **Record the active workspace** (adoption and onboarding both end here): merge
  `{"version": 1, "active_workspace": "<abs path>"}` per the write rules. This writes ONLY the registry; it
  never touches workspace files.
- **Read the scheduling marker:** the registry's `scheduling` object, defaulting to
  `{"installed": false, "mechanism": null, "set_at": null}` when absent.
- **Set the scheduling marker** (a `/loop` was started): merge
  `"scheduling": {"installed": true, "mechanism": "loop", "set_at": "<UTC ISO>"}` — timestamp from
  `date -u +%Y-%m-%dT%H:%M:%S+00:00`.
- **Clear the scheduling marker** (turn-off): merge
  `"scheduling": {"installed": false, "mechanism": null, "set_at": null}`.

## Workspace discovery & first-run detection
Gather the facts with one command, then apply the precedence rules:
```bash
REG="${JOBSEARCH_OS_REGISTRY:-${XDG_CONFIG_HOME:-${JOBSEARCH_OS_HOME:-$HOME}/.config}/job-search-os/config.json}"
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
The one tradeoff: it runs only while a Claude session is open. Never initiate a crontab/launchd install
yourself; if the user explicitly asks for cron, it's their machine and their call — show the `/loop` recipe
first and let them decide.

Compose the scheduling line from `schedule.frequency`: `/loop <interval> /job-search-run` with hourly→`1h`,
every-2-hours→`2h`, every-6-hours→`6h`, daily→`24h`, weekly→`168h`. (`schedule.time` is informational under
/loop — the loop fires on an interval from when it's started; intervals are hour-based, e.g. `24h` not `1d`,
since /loop's duration parser is not guaranteed to accept a day unit.) **Match the /loop target to the
install:** plugin skills are only invocable namespaced, so when these skills run as a plugin (this skill
appears as `job-search-os:…` in your skill list — the usual install) the target is
`/job-search-os:job-search-run`; loose skills copied into `~/.claude/skills/` use the bare `/job-search-run`.
Offer it as a yes/no; on yes, run that `/loop` command and set the scheduling marker (write rules above).
Check the marker before offering so you never re-ask. ALWAYS also show this recipe verbatim (in the form for
THIS install) so the user can start or restart it themselves:

```
Recurring (runs while a Claude session is open — nothing installed on your machine):
  /loop <interval> /job-search-os:job-search-run      # hourly → 1h · daily → 24h · weekly → 168h
One-off run anytime:
  /job-search-os:job-search-run
```

(For loose-skill installs, drop the `job-search-os:` prefix from both lines.)

To turn scheduling off: stop the loop (end the session, or cancel the pending wakeup), then clear the
scheduling marker (write rules above — no more stale `installed: true`).
