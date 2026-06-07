# Onboarding — the first-run playbook

You routed here because `python3 "$OS" resolve` returned `first_run: true`. Your job: take the user from
nothing to **real job matches found seconds ago**, in a few minutes, end-to-end. Be warm and brisk — this
should feel magical, not like filling out a form.

Resolve `$OS` (and `$STATE`) from **this skill's own directory** (e.g. `${CLAUDE_SKILL_DIR}/scripts/...`).
Follow `internals.md`, `conventions.md`, and `errors.md` exactly — don't restate their details from memory.

**Ground rule, state it up front:** every step that can't proceed stops with a **named error** (an `E-*`
from `errors.md`) that tells the user the cause and the exact fix. There are no silent failures. And you
configure everything by **chatting** — the user never hand-edits a file. No scores, no credits, ever.

---

## 1. Welcome

Open with a sentence or two, not a wall of text. Tell the user what's about to happen and that it ends with
real postings:

> "Let's set up your job search. I'll check a couple of prerequisites, make you a private workspace, learn
> what you're looking for, save your first search, and then actually pull live postings and show you the
> matches — all in a few minutes. Every step that needs something from you will say so plainly; nothing
> fails silently."

Then go, one step at a time. Keep the user oriented but don't over-explain.

## 2. Prerequisites (free)

These are free checks — no metered calls, no cost. Do them before anything else.

1. **Is the `agent-data` CLI installed?** If it's not found on `PATH` →
   **`E-NO-AGENT-DATA`**: tell the user the agent-data CLI isn't installed; the fix is
   `npm install -g agent-data`, then `agent-data whoami` to authenticate. **Stop here** — nothing was set up.
2. **Is it authenticated?** Run `agent-data whoami`. If it reports `api_key_set: false` →
   **`E-NO-AUTH`**: tell the user agent-data isn't authenticated; the fix is to
   `export AGENT_DATA_API_KEY=mtk_…` (or save the key to `~/.agent-data/config.json`), then re-verify with
   `agent-data whoami`. **Stop here.**

When both pass, say so in one line ("agent-data is installed and authenticated ✓") and continue.

## 3. Workspace

Run `python3 "$OS" resolve` and look at `source`.

### Adopt an existing workspace (never clobber)

If `source` is `legacy` — or you otherwise detect an existing workspace (a directory that already has a
`config.yaml`, `preferences.md`, or `jobs.jsonl`) — **adopt it; do not recreate it**:

1. Tell the user: **"Found an existing workspace at `<path>` — using it."**
2. Record it: `python3 "$OS" set-active --workspace <path>` (this writes **only** the registry).
3. Additively create only what's **missing**: ensure `runs/` and `reports/` exist.
4. **Never overwrite** an existing `config.yaml`, `preferences.md`, or `jobs.jsonl`. (See the never-clobber
   rule in `internals.md`.)

If the adopted workspace already has a `config.yaml` and `preferences.md`, it isn't really first-run —
confirm what's there with the user and skip straight to a sample run (step 6) and the home view (step 8),
rather than re-interviewing or re-scaffolding.

### Create a fresh workspace

Otherwise, default to **`~/.job-search/`**:

1. **Confirm the location**, offering an override ("I'll put your private workspace at `~/.job-search/` —
   that good, or somewhere else?").
2. Create the directory plus `runs/` and `reports/`.
3. Copy `templates/config.example.yaml` → `<workspace>/config.yaml` and
   `templates/workspace.gitignore` → `<workspace>/.gitignore`.
4. Create an empty `<workspace>/jobs.jsonl`.
5. Record it: `python3 "$OS" set-active --workspace <workspace>`.

Mention briefly that this workspace is **private** (the bundled `.gitignore` is deny-all) — preferences,
where they're hunting, and matched jobs live here and shouldn't be committed to a public repo.

## 4. Preferences — interview or import (a fork)

The system needs a **Job Preferences Brief** (prose `preferences.md`) — the "what I want" half that the
runner reads against each posting. Ask which path the user wants:

> "Shall I **interview** you to build your preferences from scratch, or do you already have a **brief to
> import**?"

- **Interview** → invoke the **`job-preference-interview`** skill. It asks one question at a time and writes
  the prose brief (Summary, Must-haves/dealbreakers, Strong preferences, Nice-to-haves, Red flags) to
  `<workspace>/preferences.md`. Tell it this is onboarding so it writes to the workspace you just set up.
- **Import** → also hand off to **`job-preference-interview`**, which accepts a file path or pasted prose,
  validates it's usable (prose with at least a Summary and Must-haves), converts any numeric rubric/weights
  to prose (this system is qualitative only), enriches thin sections with a few targeted questions, and
  writes `preferences.md`. Follow that skill's import rules — don't reimplement them here.

Either way, the brief ends up at `<workspace>/preferences.md` with a `created_at:` line (used later to flag
a stale brief). If for some reason a run is attempted before a usable brief exists, that path surfaces
**`E-NO-PREFERENCES`** (build one with `/job-preference-interview`, or point
`config.yaml:workspace.preferences_path` at your own prose brief).

## 5. Queries + frequency (conversational-first — no cost talk)

Now save at least one search. Do this by **chatting**, then editing `config.yaml` per the `internals.md`
recipes — never make the user open the file.

1. **Get the search.** Ask for the **role / keywords** and the **location** ("What role should I search for,
   and where — remote, a metro, a country?"). It's fine to seed a couple if the brief makes them obvious,
   but confirm them.
2. **Write a `queries[]` entry** into `config.yaml`. Show the user the item shape so they see what you're
   saving:

   ```yaml
   - { id: "ml-platform-sf", keywords: "ML platform engineer", location: "San Francisco Bay Area", limit: 25, enabled: true }
   ```

   Give the `id` a short, human slug; keep `enabled: true`; `limit: 25` is a fine default. Preserve the
   file's comments and structure, and keep `version: 1`.
3. **Pick a frequency.** Ask how often to pull, with the plain-language nudge — **no credit or cost math**:

   > "How often should I check for new postings? **Daily suits most searches; choose hourly only if you're
   > in a fast-moving, active search.** You can change this anytime by just telling me."

   Set `schedule.frequency` to one of the allowed values: `hourly | every-2-hours | every-6-hours | daily |
   weekly`. (For `daily`/`weekly`, `schedule.time` sets when.) **Never** add a budget, cost, or
   score/weight field — those don't exist in this system.

## 6. First live sample run — the magical moment

This is the payoff. Disclose it plainly first, then do it:

> "Now I'll run your first search for real — this makes a few **live calls** to pull and read postings.
> Give me a moment…"

Invoke **`job-search-run`** against the workspace (`/job-search-run --workspace <workspace>`). It probes the
source, searches each enabled query, dedups, judges each new posting against the brief, reads full
descriptions for the promising ones, and writes a digest. Then present the result like a discovery, not a
log dump — surface the **strong and moderate** matches from the digest:

> "Here are **N jobs matching your brief**, found seconds ago:"
> then the strong matches (title — company — location — one-line reasoning — link), then moderate.

Handle whatever the run reports, in plain language:

- **Blocked** → the run halts on a named error and exits non-zero. Show that error's cause + fix verbatim
  from `errors.md` and stop the magical framing. Most likely here:
  - **`E-QUOTA`** — agent-data's API limit for this period was reached, so nothing new was pulled. Fix: pull
    less often (e.g. `daily` instead of `hourly` in `config.yaml`) or upgrade the plan. Existing matches are
    unaffected. (This is the **only** time cost ever surfaces — reactively.)
  - **`E-SERVICE-DOWN`** — the source is unreachable right now; usually temporary, the next run retries.
  - (Auth/config/preferences errors shouldn't appear if steps 2–5 succeeded; if one does, name it and fix
    the gap.)
- **Zero results, all already known** (only possible on an adopted workspace) → reassuring, not an error:
  "No new postings — all N already in your database."
- **Zero results, literally empty** → actionable: offer to broaden the keywords in the query (and apply it
  conversationally).

Don't show run internals, credits, or scores — just the matches and, if relevant, the named error.

## 7. Scheduling (offer it; consent + fallback)

Offer to make the search run on its own. Follow `internals.md` **exactly** — explain the options, get a
yes/no, and **always** print the verbatim copy-paste fallback regardless of the answer.

Explain the three options in a sentence each:

- **cron** (default) — the OS runs it on a schedule even when Claude is closed.
- **launchd** (robust macOS) — a launch agent that can wake the Mac at run time.
- **`/loop`** — keep a Claude session open and loop the run.

Ask a simple **yes/no**: "Want me to set this up to run automatically?"

**On yes:**

1. Generate the artifact deterministically with `$OS`:
   - cron → `python3 "$OS" schedule-line --frequency <f> --time <t> --workspace <workspace>`
   - launchd → `python3 "$OS" launchd-plist --frequency <f> --time <t> --workspace <workspace>`
2. If the user chose launchd or /loop specifically, first run `python3 "$OS" set-sched-intent --choice <mechanism>` (records consent for the guard).
3. Perform the **privileged write**: append the generated line to the crontab, **or** write the plist to
   `~/Library/LaunchAgents/dev.jobsearchos.run.plist` and `launchctl load` it.
4. Record it so you never re-ask: `python3 "$OS" set-scheduled --mechanism <cron|launchd|loop>`,
   then `python3 "$OS" clear-sched-intent`.
5. **Also print the verbatim fallback block below** (so the user has the manual recipe too).

**On no:** print the verbatim fallback block so the user can do it later, and only run
`python3 "$OS" set-scheduled --mechanism <m>` if they confirm they set it up themselves.

**Always print this fallback block verbatim** (from `internals.md`):

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

## 8. Home

You're done. Print the **home view** to land the user on their dashboard — hand off to the format in
`references/home.md` (status line · latest digest · pipeline · quick actions). Close with a short line that
they can just tell you what they want next ("run a search now", "add another query", "change how often it
runs", "update my preferences", "show the latest digest").

---

### Onboarding checklist (don't skip a guard)

- [ ] agent-data installed → else **E-NO-AGENT-DATA** (stop)
- [ ] agent-data authenticated → else **E-NO-AUTH** (stop)
- [ ] workspace adopted-or-created; **never clobbered** an existing `config.yaml` / `preferences.md` /
      `jobs.jsonl`; `set-active` recorded
- [ ] `preferences.md` exists (interview or import via `job-preference-interview`)
- [ ] at least one `queries[]` entry written; `schedule.frequency` set (plain-language nudge, **no cost
      math**)
- [ ] first **live** `job-search-run` done; strong/moderate matches shown — or the named error if blocked
- [ ] scheduling offered; on yes installed + `set-scheduled`; **fallback block printed verbatim either way**
- [ ] home view printed
