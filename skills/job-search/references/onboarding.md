# Onboarding — the first-run playbook

You routed here because `python3 "$OS" resolve` returned `first_run: true`. Your job: take the user from
nothing to **real job matches found seconds ago**, in a few minutes, end-to-end. Be warm and brisk — this
should feel magical, not like filling out a form.

Resolve `$OS` (and `$STATE`) from **this skill's own directory** (e.g. `${CLAUDE_SKILL_DIR}/scripts/...`).
Follow `internals.md`, `conventions.md`, `errors.md`, and `voice.md` exactly — don't restate their details
from memory.

**Ground rule — how you behave, not a speech to give:** every step that can't proceed stops with a
**named error** (an `E-*` from `errors.md`) that tells the user the cause and the exact fix. There are no
silent failures. And you configure everything by **chatting** — the user never hand-edits a file. No
scores, no credits, ever. Never announce these guarantees to the user ("nothing fails silently", "every
step will say so plainly") — reliability is demonstrated, not promised; meta-assurances are noise.

**Assume zero context.** A first-run user has never seen this system and doesn't know its words. Per
`voice.md`: give every question below one short plain-English sentence of what the thing is and why you're
asking — then ask, closed choices through the question tool (`voice.md` → Asking questions). No internal
vocabulary, ever.

---

## 1. Welcome

The router (SKILL.md Step 0) already said the welcome — your first user-facing words, spoken the moment
`resolve` returned `first_run: true`, **before this playbook was opened**. If that somehow hasn't happened,
say it now (the template lives in Step 0) before anything else: no prerequisite check, no workspace
command, no tool call the user can see comes before the welcome — in every mode, headless included. "Let
me read the references / run some checks first" is the failure mode: it opens the user's first minute with
machinery talk instead of a greeting.

Then go, one step at a time. Keep the user oriented but don't over-explain.

## 2. Prerequisites — get agent-data ready (free)

This plugin runs on a tool called **agent-data** — it's what pulls and reads live job postings. Right after
the welcome (§1 owns your first words), make sure it's ready, before anything metered or persistent. These
are free checks — no metered calls, no cost — and nothing is searched, written, or created until it's
working.

**Keep the user oriented — explain, don't script.** Narrate the way Claude Code does by default: a short
line of what you're doing and why around non-obvious work, in your own words — no fixed formula, no line
per command. The one hard part: the user must never watch an install attempt or a permission prompt with
no idea what "agent-data" is. Introduce it **once**, the first time it comes up — e.g. "This plugin uses a
tool called **agent-data** to pull live job postings — let me check whether it's set up on your machine."
After that it's introduced: at later steps "agent-data isn't installed yet — installing it now" is plenty.
Re-explaining what it's for at every step reads like a script, not an assistant. Don't announce a result
you haven't verified, and don't tell the user how long anything will take.

**The check (pinned — don't improvise it).** Look for the real command on `PATH` with `command -v
agent-data`, and confirm it's authenticated — `agent-data whoami` should report `api_key_set: true` (per
`agent-data-contract.md`).

- **Already set up** → say so as a verified fact in one short line ("agent-data is ready ✓") and continue.
- **Missing or not authenticated** → **set it up for the user; don't stop.** Lead with the solution, not an
  error. The internal codes for this state (`E-NO-AGENT-DATA`, `E-NO-AUTH`) are for your reasoning only —
  **never show them to the user** (`voice.md`). Two starting points, one path — a **missing** CLI starts at
  step 1; one that's on `PATH` but **unauthenticated** starts at step 2. Keep these steps in sync with the
  canonical setup doc (<https://agent-data.dev/setup/claude-code.md>):

  1. **Install it.** Don't ask the user for anything here — no key yet, no confirmation; the API key
     belongs to the connect step. (And don't narrate that — "this needs nothing from you" is non-event
     noise, `voice.md` rule 5.) Tell them it isn't installed and that you're installing it — they already
     know what agent-data is from the check, so don't re-define it — and run:

     ```
     npm install -g agent-data
     ```

     **If permission settings block the install** (stricter modes guard agent-chosen global installs),
     that's expected, not an error — no apology spiral, no stopping. One plain line and the exact command
     to run in-session, e.g. "My permission settings want installs run by you. Type this in the prompt —
     the `!` runs it here so I'll see the result: `! npm install -g agent-data`". Pick up at the version
     check once it lands.

     Confirm the install took with `agent-data --version` before moving on — no pre-claimed success.
  2. **Connect their account.** (Start here when `agent-data` was already on `PATH` but `whoami` reported
     `api_key_set: false` — don't reinstall.) Get an API key — give the full steps, not just "paste a key":
     - Open **<https://agent-data.motie.dev/settings/account>** (sign in, or create a free account if you
       don't have one yet).
     - On the Account settings page, click **Generate API Key**.
     - Copy the key — it starts with `mtk_` — and paste it here.

     Ask for the key as a plain prose question — it's a free-text secret, not a closed choice, so don't use
     the question tool.
  3. **Authenticate**, substituting the key they pasted:

     ```
     agent-data init --claude-code --api-key <KEY> --yes
     ```

     This saves the key to `~/.agent-data/config.json` and installs the Claude Code discovery skill.
  4. **Verify it worked** — re-check auth with `agent-data whoami` (`api_key_set: true`). If it still
     reports `api_key_set: false` or you see `401 Invalid API key`, the key was wrong — ask them to
     generate a fresh one and paste it again.
  5. If Claude Code is older than `2.1.0`, a session restart may be needed for the new tool to load;
     `2.1.0`+ hot-loads, so no restart is needed.

  Once it verifies, confirm in one line and continue. If setup genuinely can't finish (e.g. they can't get a
  key right now), explain plainly where things stand and what's left — still no raw error code.

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

1. **Confirm the location with the question tool** (`voice.md` → Asking questions) — a new user doesn't
   know what a "workspace" is, so the context rides in the question text. Header `Workspace`; question:
   "Everything your job search learns and finds — your preferences, saved searches, and matched jobs —
   lives in one private folder on your machine. Where should I put it?"; options: **`~/.job-search`** —
   "the default: private and out of the way" · **Somewhere else** — "name any folder; I'll use that". (A
   path typed via the free-text option is equally fine.)
2. Create the directory plus `runs/` and `reports/`.
3. Copy `templates/config.example.yaml` → `<workspace>/config.yaml` and
   `templates/workspace.gitignore` → `<workspace>/.gitignore`.
4. Create an empty `<workspace>/jobs.jsonl`.
5. Record it: `python3 "$OS" set-active --workspace <workspace>`.

Mention briefly that this workspace is **private** (the bundled `.gitignore` is deny-all) — preferences,
where they're hunting, and matched jobs live here and shouldn't be committed to a public repo.

## 4. Preferences — interview or import (a fork)

The system needs a **Job Preferences Brief** (prose `preferences.md`) — the "what I want" half that the
runner reads against each posting. This is a closed two-way choice, so ask it with the question tool
(`voice.md` → Asking questions), the what-it-is context riding in the question text. Header `Brief`;
question: "Next I need your **Job Preferences Brief** — the plain-English 'what I want' that every posting
gets judged against. How do you want to build it?"; options:

- **Interview me** — "I'll ask questions and write the brief from your answers — you pick how deep to go."
- **Import one** — "you already have it written down — paste it or give me the path."

Then route on the answer:

- **Interview** → invoke the **`job-preference-interview`** skill, passing exactly two things: that this is
  onboarding, and where to write — e.g. args: `onboarding — write the brief to <workspace>/preferences.md`.
  Nothing else: no depth, no question count, no description of its method. That skill opens by letting the
  **user** choose how deep to go, and an invocation that says "standard" or "one question at a time" reads
  as a depth already chosen — the ask silently disappears and the user never learns a one-question sketch
  existed. It ends with the brief (Summary, Must-haves/dealbreakers, Strong preferences, Nice-to-haves,
  Red flags) written to `<workspace>/preferences.md`.
- **Import** → also hand off to **`job-preference-interview`**, which accepts a file path or pasted prose,
  validates it's usable (prose with at least a Summary and Must-haves), converts any numeric rubric/weights
  to prose (this system is qualitative only), enriches thin sections with a few targeted questions, and
  writes `preferences.md`. Follow that skill's import rules — don't reimplement them here.

The interview skill ends by **showing the finished brief rendered in the reply** (per `voice.md`) — don't
re-print it here; confirm and move on. Either way, the brief ends up at `<workspace>/preferences.md` with
`created_at:` + `updated_at:` front-matter lines (the home view flags a stale brief from `updated_at`). If for some reason a run is attempted before a usable brief exists, that path surfaces
**`E-NO-PREFERENCES`** (build one with the **job-preference-interview** skill, or point
`config.yaml:workspace.preferences_path` at your own prose brief).

## 5. Searches + frequency (derive from the brief — don't make the user pick keywords)

You just built the brief, so you already know what they want. **Derive the searches from it — don't ask the
user to name keywords.** They can retune anytime; the goal here is zero upfront homework.

1. **Derive 2–3 queries from `preferences.md`.** Read the **Summary**, **Must-haves / dealbreakers**, and
   **Strong preferences**, and turn them into a few complementary searches:
   - **keywords** — the role/title and domain terms a job board would match (e.g. "AI engineer", "ML platform
     engineer", "LLM engineer"). Give each query a *different* angle, not one near-duplicate.
   - **location** — read it off the brief's location constraints: "remote within the US" → `United States`;
     "onsite in the SF Bay Area" → `San Francisco Bay Area`. If the brief allows both, cover each with its
     own query. **If remote is a must-have, also fold the word `remote` into `keywords`** (e.g. "remote AI
     engineer") — the search API has no remote filter, so without it the feed fills with onsite roles the
     judge then has to cull.
2. **Write them to `config.yaml`** per the `internals.md` "Add a query" recipe — never make the user open the
   file. Each item:

   ```yaml
   - { id: "ml-platform-sf", keywords: "ML platform engineer", location: "San Francisco Bay Area", limit: 25, enabled: true }
   ```

   Give each `id` a short, human slug; keep `enabled: true`; `limit: 25` is a fine default. Preserve the
   file's comments and structure, and keep `version: 1`.
3. **Acknowledge what you saved — don't ask them to choose.** Name the searches you derived and make clear
   they're fully editable, e.g.:

   > "From your preferences I'll search for **'AI engineer' · 'ML platform engineer'** across **US-remote +
   > the SF Bay Area**. I can add, retune, or drop any of these anytime — just say the word."

   Only if the brief is too thin to derive anything sensible (rare) do you ask one focused question to fill
   the gap — lead with derivation, never a blank "what should I search for?".
   The config already comes preset with a recency window (recent postings only) and a fast model for reading
   posting details — both are tunable anytime just by asking.
4. **Pick a frequency — with the question tool** (`voice.md` → Asking questions), the plain-language nudge
   carried by the recommended-first option — **no credit or cost math**. Header `Frequency`; question:
   "How often should I check for new postings? You can change this anytime by just telling me."; options,
   recommended first:

   - **Daily (Recommended)** — "suits most searches"
   - **Hourly** — "only for a fast-moving, active search"
   - **Every 6 hours** — "a few times a day, without the firehose"
   - **Weekly** — "a slow-burn watch"

   Set `schedule.frequency` to the chosen allowed value: `hourly | every-2-hours | every-6-hours | daily |
   weekly` — `every-2-hours` has no button, so map a typed answer ("every couple of hours") to the nearest
   allowed value and say which one you set. **Never** add a budget, cost, or score/weight field — those
   don't exist in this system.

## 6. First live sample run — the magical moment

This is the payoff. Disclose it plainly first, then do it:

> "Now I'll run your first search for real — this makes **live calls** to pull and read postings."

Invoke **`job-search-run`** against the workspace (pass `--workspace <workspace>`). It probes the
source, searches each enabled query, skips postings already seen, judges each new posting against the
brief, reads full descriptions for the promising ones, and writes a digest. Then present the result like a
discovery, not a log dump — surface the **strong and moderate** matches from the digest **as normal message
text in your reply** (rendered markdown — never a code fence, never just the digest's file path):

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
  "No new postings — you've already seen all N of these."
- **Zero results, literally empty** → actionable: offer to broaden the keywords in the query (and apply it
  conversationally).

Don't show run internals, credits, or scores — just the matches and, if relevant, the named error.

## 7. Scheduling (offer it; native `/loop`, nothing touches the machine)

Offer to keep the search running automatically. Job Search OS schedules with Claude Code's **native
`/loop`** — it re-runs the search on an interval **inside an open Claude session** and never writes anything
to the user's machine (no crontab, no launchd). Follow `internals.md`. Say it plainly, including the one
tradeoff: it runs **while you have a Claude session open**.

Ask it with the question tool (`voice.md` → Asking questions). Header `Schedule`; question: "Want me to
keep checking automatically while you have Claude open? New matches will land in a digest without you
having to ask."; options: **Yes, keep checking** — "runs while a Claude session is open; stops when it
ends" · **No, I'll run it myself** — "a one-off search stays one command away".

**On yes:**

1. Get the deterministic command for the chosen frequency:
   `python3 "$OS" loop-command --frequency <f>` → prints e.g. `/loop 24h /job-search-run`.
   **Match the target to the install:** plugin skills are only invocable namespaced, so when these skills
   run as a plugin (this skill appears as `job-search-os:…` in your skill list — the usual install), add
   `--namespace job-search-os` so it prints `/loop 24h /job-search-os:job-search-run`. Loose skills in
   `~/.claude/skills/` use the bare form.
2. **Start it** by running that `/loop …` command, then record it so you don't re-ask:
   `python3 "$OS" set-scheduled` (records `mechanism: loop`).
3. Show the user the exact `/loop` line so they can restart it anytime (it stops when the session ends).

**On no:** leave it unscheduled — tell them they can turn it on later by just asking, and that a one-off run
is always one slash command away (`/job-search-os:job-search-run` as a plugin; `/job-search-run` as loose
skills).

**Either way, show this recipe verbatim** (in the form for THIS install) so the user can start or restart it
themselves (from `internals.md`):

```
Recurring (runs while a Claude session is open — nothing installed on your machine):
  /loop <interval> /job-search-os:job-search-run      # hourly → 1h · daily → 24h · weekly → 168h
One-off run anytime:
  /job-search-os:job-search-run
```

(For loose-skill installs, drop the `job-search-os:` prefix from both lines.)

## 8. Home

You're done. Print the **home view** to land the user on their dashboard — hand off to the format in
`references/home.md` (status line · latest digest · pipeline · quick actions). Close with a short line that
they can just tell you what they want next ("run a search now", "add another query", "change how often it
runs", "update my preferences", "show the latest digest").

---

### Onboarding checklist (don't skip a guard)

- [ ] the welcome was the FIRST user-facing text — reference reads silent before it; no check, command,
      or narration preceded it
- [ ] agent-data ready — checked via the pinned `command -v agent-data` + auth probe; if **missing**,
      **installed first, then connected** (`npm install -g agent-data` → `agent-data --version` →
      key-generation steps → `agent-data init` → live `whoami` verify); if only **unauthenticated**, key
      steps → init → verify, no reinstall — **the user always knew what was happening and why**
      (agent-data introduced once, never re-defined per step), solution-first, **no raw error code
      shown**, no premature claim, no duration promise; a permission-blocked install became a one-line
      `! npm install -g agent-data` handoff, not an error
- [ ] workspace adopted-or-created; **never clobbered** an existing `config.yaml` / `preferences.md` /
      `jobs.jsonl`; `set-active` recorded
- [ ] `preferences.md` exists (interview or import via `job-preference-interview`)
- [ ] 2–3 `queries[]` **derived from the brief** and written (no upfront keyword-picking); searches
      acknowledged; `schedule.frequency` set (plain-language nudge, **no cost math**)
- [ ] first **live** `job-search-run` done; strong/moderate matches shown — or the named error if blocked
- [ ] scheduling offered via native `/loop`; on yes started + `set-scheduled`; `/loop` recipe shown either way
- [ ] every ask carried one line of plain-English context; the four closed choices (workspace location,
      interview-or-import, frequency, scheduling) went through the question tool; no internal vocabulary
      reached the user (`voice.md`)
- [ ] home view printed
