# Named errors (E-*) — cause + fix + what the user sees

Every failure is named and visible — no silent failures. The durable guarantee for blocked runs is two **file-backed channels**: the **blocked digest** (named error as the body) and the **home view** (reads `run_health` from the newest `runs/<id>.json`) — both plain file writes that survive on any host. Every HALT therefore writes a `runs/<id>.json` blocked record. An attention-pull alert is capability-gated: it fires only when the `notify.desktop_notify_on_block` knob is set AND the host has an attention-pull channel (see your adapter → Block-alert channel); when it has none, skip it silently — the two file channels still carry the failure.

Surface every outcome through the written record — the record is the contract the home view reads — because a skill cannot set the host's exit code; whether `$?` can also be trusted is per-harness (see your adapter → Headless invocation). The digest's "Run health" line is one of: `healthy | partial (N errors) | degraded (LinkedIn flaky) | blocked (action needed)`.

| Code | When | What the user sees (cause + fix) | Run effect |
|---|---|---|---|
| **E-NO-AGENT-DATA** | the `agent-data` CLI is not found on PATH (prereq check, before `whoami`) | "The agent-data CLI isn't installed. Install it (`npm install -g agent-data`), then run `agent-data whoami` to authenticate. Nothing was pulled." | HALT, exit 1 |
| **E-NO-CONFIG** | `config.yaml` missing in the workspace | "No `config.yaml` found in <workspace>. Run the job-search skill (say 'set up job search') to set it up." | HALT, exit 1 |
| **E-NO-AUTH** | `agent-data whoami` shows `api_key_set:false` | "agent-data is not authenticated. Run `export AGENT_DATA_API_KEY=mtk_…` (or save it to `~/.agent-data/config.json`), then verify with `agent-data whoami`. No data was pulled." | HALT, exit 1 |
| **E-CONFIG-VERSION** | `config.yaml` `version` major is newer than this code supports | "This `config.yaml` was written by a newer version. Update the job-search skills, or check `version:` in config." | HALT, exit 1 |
| **E-NO-PREFERENCES** | `preferences.md` missing/empty (the no-preferences run path) | "No Job Preferences Brief found. Run the job-preference-interview skill to build one, or point `config.yaml:workspace.preferences_path` at your own prose brief. Nothing was pulled." | HALT, exit 1 |
| **E-SERVICE-DOWN** | `status` route unreachable / non-200 | "The job source is unreachable right now. This is usually temporary — the next scheduled run will retry." | HALT, exit 1, write "service down" digest |
| **E-BAD-QUERY** | `422 invalid_request` / `400 unsupported_field` on a search | "Query '<id>' is invalid: <param from details[].loc>. Fix it in `config.yaml` under `queries`." | skip that query, continue |
| **E-UPSTREAM-STRETCH** | 2 consecutive `search-jobs` 502s | "LinkedIn was unreachable this run (repeated upstream errors). Partial or no results; the next scheduled run will retry." | stop searching, partial digest |
| **E-QUOTA** | agent-data reports its API limit reached (a call rejected for quota/payment) | "agent-data's API limit for this period has been reached, so no new postings were pulled. This usually means searches are running very often — lower `schedule.frequency` in `config.yaml` (e.g. `daily` instead of `hourly`), or upgrade your plan at agent-data.motie.dev. Your existing matches are unaffected." | HALT, exit 1 |

### Expected non-errors (footnotes, not failures)
- **invalid_pair** (`400`, `retryable:false`) on `get-posting`: the `jp_`/`source_url` pair went stale (LinkedIn
  re-indexed). Judge from the summary instead and add a digest footnote: "1 posting's detail link had expired;
  judged from its summary." Not an error.
- **Zero results — all already known:** reassuring, not an error — "No new postings — you've already seen all N of these."
- **Zero results — literally empty:** actionable — "Searches ran but returned 0 results. Broaden keywords in
  `config.yaml`, or check `agent-data call <listing> status`."

### Detecting E-QUOTA vs E-NO-AUTH from the CLI
Both surface as a non-zero `agent-data call`. Distinguish by: run `agent-data whoami` first (covers auth). If
auth is fine but an agent-data call fails with a payment/quota/limit signal in stderr (e.g. HTTP 402/429, or a
message mentioning quota/limit), treat as E-QUOTA. Anything else upstream is treated per its
`retryable` flag (502 → retry; otherwise record + continue).
