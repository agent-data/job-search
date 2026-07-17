# Onboarding — the first-run playbook

You routed here because the Discovery procedure (`internals.md`) reported `first_run: true`. Your job: take
the user from nothing to **real job matches found seconds ago**, in a few minutes, end-to-end. Be warm and
brisk — this should feel magical, not like filling out a form.

Follow `../../../shared/references/internals.md`, including its canonical
[Agent-data usage decisions](../../../shared/references/internals.md#agent-data-usage-decisions),
`../../../shared/references/conventions.md`, `../../../shared/references/errors.md`, and
`../../../shared/references/voice.md` exactly — don't restate their details from memory.

**Ground rule — how you behave, not a speech to give:** every step that can't proceed stops with a
**named error** (an `E-*` from `errors.md`) that tells the user the cause and the exact fix. There are no
silent failures. And you configure everything by **chatting** — the user never hand-edits a file. No
scores, ever. Never announce these guarantees to the user ("nothing fails silently", "every
step will say so plainly") — reliability is demonstrated, not promised; meta-assurances are noise.

**Assume zero context.** A first-run user has never seen this system and doesn't know its words. Per
`voice.md`: give every question below one short plain-English sentence of what the thing is and why you're
asking — then ask, closed choices (`voice.md` → Asking questions). No internal vocabulary, ever.

**Contents:** [1. Welcome](#1-welcome) · [2. Prerequisites — agent-data](#2-prerequisites--get-agent-data-ready) · [3. Workspace](#3-workspace) · [4. Preferences](#4-preferences--one-quick-question) · [5. Searches](#5-searches-derive-from-the-brief--dont-make-the-user-pick-keywords) · [6. First live sample run](#6-first-live-sample-run--the-magical-moment) · [7. Scheduling](#7-scheduling-offer-it) · [8. Home](#8-home)

---

## 1. Welcome

The router (SKILL.md Step 0) already said the welcome — your first user-facing words, spoken the moment
discovery reported `first_run: true`, **before this playbook was opened**. If that somehow hasn't happened,
say it now (the template lives in Step 0) before anything else: no prerequisite check, no workspace
command, no tool call the user can see comes before the welcome — in every mode, headless included. "Let
me read the references / run some checks first" is the failure mode: it opens the user's first minute with
machinery talk instead of a greeting.

Then go, one step at a time. Keep the user oriented but don't over-explain.

## 2. Prerequisites — get agent-data ready

This plugin runs on a tool called **agent-data** — it's what pulls and reads live job postings. Right after
the welcome (§1 owns your first words), make sure it's ready, before anything persistent. Nothing is
searched, written, or created until it's working.

**Keep the user oriented — explain, don't script.** Narrate the way a good assistant does by default: a
short line of what you're doing and why around non-obvious work, in your own words — no fixed formula, no
line per command. The one hard part: the user must never watch an install attempt or a permission prompt with
no idea what "agent-data" is. Introduce it **once**, the first time it comes up — e.g. "This plugin uses a
tool called **agent-data** to pull live job postings — let me check whether it's set up on your machine."
After that it's introduced: at later steps "agent-data isn't installed yet — installing it now" is plenty.
Re-explaining what it's for at every step reads like a script, not an assistant. Don't announce a result
you haven't verified, and don't tell the user how long anything will take.

**The check (pinned — don't improvise it).** Look for the real command on `PATH` with `command -v
agent-data`, and confirm it's authenticated — `agent-data whoami` should report `api_key_set: true` (per
`../../../shared/references/agent-data-contract.md`).

- **Already set up** → say so as a verified fact in one short line ("agent-data is ready") and continue.
- **Missing or not authenticated** → **set it up for the user; don't stop.** Lead with the solution, not an
  error. The internal codes for this state (`E-NO-AGENT-DATA`, `E-NO-AUTH`) are for your reasoning only —
  **never show them to the user** (`voice.md`). Two starting points, one path — a **missing** CLI starts at
  step 1; one that's on `PATH` but **unauthenticated** starts at step 2. Keep these steps in sync with the
  canonical, host-agnostic path in `../../../shared/references/agent-data-contract.md` → Auth:

  1. **Install it.** Don't ask the user for anything here — no key yet, no confirmation; the API key
     belongs to the connect step. (And don't narrate that — "this needs nothing from you" is non-event
     noise, `voice.md` rule 5.) Tell them it isn't installed and that you're installing it — they already
     know what agent-data is from the check, so don't re-define it. Before the install attempt, load the
     currently verified available-tier fact from `../../../shared/references/agent-data-contract.md` and use
     the exact pre-install rendering in `../../../shared/references/voice.md` → **Agent-data usage
     context**. Do not add an account-plan, balance, allowance, or visibility caveat. If the canonical fact
     cannot be verified, omit the tier claim rather than guessing. Then run:

     ```
     npm install -g agent-data
     ```

     **If permission settings block the install** (stricter modes guard agent-chosen global installs),
     that's expected, not an error — no apology spiral, no stopping. One plain line and the exact command
     for the user to run themselves — `npm install -g agent-data` — e.g. "My permission settings want
     installs run by you. Run this and I'll pick up once it lands." If your host can run a shell command
     in-session so you see its result, use it for the install so you get the outcome directly.
     Pick up at the version check once it lands.

     Confirm the install took with `agent-data --version` before moving on — no pre-claimed success.
  2. **Connect their account.** (Start here when `agent-data` was already on `PATH` but `whoami` reported
     `api_key_set: false` — don't reinstall.) Get an API key — give the full steps, not just "paste a key":
     - Open **<https://agent-data.motie.dev/settings/account>** (sign in, or create a free account if you
       don't have one yet).
     - On the Account settings page, click **Generate API Key**.
     - Copy the key — it starts with `mtk_` — and paste it here.

     Ask for the key as a plain prose question — it's a free-text secret, not a closed choice.
  3. **Authenticate** with the key they pasted — the same universal command on every host:

     ```
     agent-data init --api-key <KEY> -y
     ```

     Substitute their key for `<KEY>`. This saves it to `~/.agent-data/config.json`; see
     `../../../shared/references/agent-data-contract.md` → Auth for the details (don't add a host-specific
     selector flag).
  4. **Verify it worked** — re-check auth with `agent-data whoami` (`api_key_set: true`). If it still
     reports `api_key_set: false` or you see `401 Invalid API key`, the key was wrong — ask them to
     generate a fresh one and paste it again.
  5. Some hosts may need a fresh session to pick up a newly-installed CLI on `PATH`.

  Once it verifies, confirm in one line and continue. If setup genuinely can't finish (e.g. they can't get a
  key right now), explain plainly where things stand and what's left — still no raw error code.

## 3. Workspace

Look at the `source` that Discovery (SKILL.md Step 0) already determined.

### Adopt an existing workspace (never clobber)

If `source` is `legacy` — or you otherwise detect an existing workspace (a directory that already has a
`config.yaml`, `preferences.md`, or `jobs.jsonl`) — **adopt it; do not recreate it**:

1. Tell the user: **"Found an existing workspace at `<path>` — using it."**
2. Record it as the active workspace in the registry (`internals.md` → Registry write rules — this writes
   **only** the registry).
3. Additively create only what's **missing**: ensure `runs/` and `reports/` exist.
4. **Never overwrite** an existing `config.yaml`, `preferences.md`, or `jobs.jsonl`. (See the never-clobber
   rule in `internals.md`.)

If the adopted workspace already has a `config.yaml` and `preferences.md`, it isn't really first-run —
confirm what's there with the user and skip straight to a sample run (step 6) and the home view (step 8),
rather than re-interviewing or re-scaffolding.

### Create a fresh workspace

Otherwise, **silently default to `~/.job-search/`** — do **not** ask where to put it. A new user doesn't
know what a "workspace" is, and the default location is never worth a setup question. Mention a path only as
an **escape hatch**: when the user's request **explicitly named a folder** (honor that override, and you
may state it back) or when you're **adopting an existing workspace** (above). Never turn the location into a
question.

1. Create the directory — `~/.job-search`, or the explicit folder the user named — plus `runs/` and
   `reports/`.
2. Copy `templates/workspace.gitignore` → `<workspace>/.gitignore` and create an empty
   `<workspace>/jobs.jsonl`. Load `templates/config.example.yaml` as an in-memory candidate; do **not** copy
   the intentionally incomplete template to `<workspace>/config.yaml`.
3. **Resolve the setup-only detail-model choice now.** Use the current host roster to select the exact
   least-powerful available model that performs fit judgment well, unless the user has explicitly requested
   another exact available model. Don't ask the user to pick a model — this is a silent setup decision, not a
   question. If the host cannot assign a separate worker model, select the creating session's exact primary
   model and plan sequential detail reads. This is the only model-selection decision; the headless run will
   obey the saved exact identifier.
4. Hold the config candidate in memory through the preferences, query, and optional parallel-approval steps
   below. Do not record the workspace as active yet. If an exact executable selection and canonical binding
   cannot be established, do not write `config.yaml` or `runs/detail-model-binding.json`, do not run an
   invalid workspace, and route to interactive model repair. The final valid version-2 config, sidecar, and
   registry write happen together at the end of §5.

Mention briefly that this workspace is **private** (the bundled `.gitignore` is deny-all) — preferences,
where they're hunting, and matched jobs live here and shouldn't be committed to a public repo.

## 4. Preferences — one quick question

The system needs a **Job Preferences Brief** (prose `preferences.md`) — the "what I want" half that the
runner reads against each posting. On first run you build a **provisional, high-signal** version fast; the
user can deepen it anytime. This is the one place onboarding introduces the brief.

**If the invocation already says what they want, use that — don't ask again.** A setup request like "Set up
my job search — I want a senior remote AI role, IC not management" already carries the preferences; go
straight to drafting the brief from it.

**Otherwise ask exactly one free-form question.** It's free text, so ask it **inline as prose**, not the
question box (`../../../shared/references/voice.md` → Asking questions). Ask it **verbatim**:

> In a sentence or two, what are you looking for? If useful, share or point me to relevant material such as
> a resume, cover letter, or notes from previous applications.

**Supplied material is background evidence, not preferences.** A resume, cover letter, or notes are
**context** that informs the brief — never an existing brief, and never silently promoted into must-haves
or preferences. When the material conflicts with what the user just said, **the user's stated intent
wins**: don't turn a résumé line (an old title, a past location, a former stack) into a dealbreaker they
never asked for.

**Write a provisional high-signal brief.** Draft the five sections (Summary, Must-haves/dealbreakers,
Strong preferences, Nice-to-haves, Red flags — `../../../shared/references/conventions.md` owns the set)
the way **`job-preference-interview`** drafts a **quick sketch** (its *Quick sketch* section owns that
method): from **only what the user actually said** plus safe, direct implications — a stated role /
location / pay floor becomes a **Must-have**, softer wants go to **Strong preferences / Nice-to-haves**, an
on-call aversion becomes a **Red flag**. **Don't invent preferences they didn't express**; leave a section
sparse rather than padding it. Write it to `<workspace>/preferences.md` with `created_at:` + `updated_at:`
front-matter lines (the home view flags a stale brief from `updated_at`). You present it — rendered, next to
the derived searches — at the **confidence checkpoint** in §5; don't print it twice.

**The deeper interview and importing a written brief are later refinements, not first-run gates.** A
standard or thorough **`job-preference-interview`** pass (its depth choice) and importing an
already-written brief stay available **after** the user has seen results — offer them then, never as a
first-run question. If a run is ever attempted before a usable brief exists, that path surfaces
**`E-NO-PREFERENCES`** (build one with the **job-preference-interview** skill, or point
`config.yaml:workspace.preferences_path` at your own prose brief).

## 5. Searches (derive from the brief — don't make the user pick keywords)

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
2. **Render them into the in-memory version-2 config candidate** per the `internals.md` "Add a query" recipe
   — never make the user open the file. One worked item — the `keywords` and `location` below are
   **illustrative; derive your own from
   *this* user's brief, never paste these literal words**:

   ```yaml
   - { id: "ml-platform-sf", keywords: "ML platform engineer", location: "San Francisco Bay Area", limit: 25, enabled: true }
   ```

   Give each `id` a short, human slug built from that query's own terms; keep `enabled: true`; `limit: 25`
   is a fine default. Preserve the template's comments and structure, keep `version: 2`, and insert the
   exact setup-selected identifier as `search.detail_model`.
3. **Show one compact confidence checkpoint — the brief and the searches — then go live.** Present, as a
   single short look before the first live run: the **provisional brief** rendered in the reply (per
   `../../../shared/references/voice.md` — no code fence, skip the front-matter lines) and the **search
   interpretation** you derived — which sources, which queries, which locations. Make clear it's all fully
   editable, and that this is a **look, not a gate**: you're about to go live, not asking permission to
   (the run's consent is handled by the setup request + the §6 cost context, not a confirmation here). Name
   the searches, e.g.:

   > "From your preferences I'll search **LinkedIn and public Ashby company boards** for **'AI engineer' · 'ML platform engineer'** across **US-remote +
   > the SF Bay Area**. I can add, retune, or drop any of these anytime — just say the word."

   Only if the brief is too thin to derive anything sensible (rare) do you ask one focused question to fill
   the gap — lead with derivation, never a blank "what should I search for?".
   The config already comes preset with a recency window (recent postings only — you can change it, or ask
   for a different window any time) and the exact detail model selected during setup — both are tunable
   anytime just by asking. The config also comes preset with the default job sources (LinkedIn + Ashby
   company boards) — tunable anytime just by asking.

### Parallel detail-read approval (approval-gating hosts only)

Some hosts gate parallel subagents behind one explicit user approval before the runner may use them for
posting-detail reads. If your host gates subagents this way, run this step; if it does **not** gate
subagents, skip this whole step (the parallel fan-out is already the default) and go to §6.

On an **approval-gating host**, if `search.parallel_detail_reads` is unset, ask once after the searches are
derived and before the first live run. Ask it as a closed choice; the question must say **subagents** and
must name the exact detail model already selected during setup. Present that selection as a fact, not a tier
choice.

On **yes**:

1. Add `search.parallel_detail_reads: true` to the in-memory config candidate; preserve comments/structure
   and keep `version: 2`.
2. Keep the already-selected exact `search.detail_model`; parallel approval is not a second model-selection
   decision.
3. Perform any host-specific subagent setup your host needs
   (e.g. writing a scoped profile so unattended runs may use subagents). Tell the user in plain language what
   the setting does. If the sandbox blocks that write, show the exact path and content;
   don't silently skip it.

On **no**, add `search.parallel_detail_reads: false` to the config candidate and read details sequentially.
Do not ask again unless the user later asks to change it.

### Finalize the runnable version-2 workspace

Before the first live run, finish the template-copy-to-runnable integration:

1. Render a complete candidate from `templates/config.example.yaml` with `version: 2`, the derived queries,
   the exact setup-selected `search.detail_model`, and any parallel choice. Validate it against
   `conventions.md`; the static template by itself is not a valid workspace config.
2. Build the canonical private `runs/detail-model-binding.json` candidate with a fresh locally generated
   `binding_id`, the exact same `detail_model`, origin `configured_auto` for the setup default or
   `configured_user` for an explicit user choice, and current UTC `bound_at`.
3. Validate both complete candidates before touching their final paths. Then atomically write the sidecar and
   atomically write `config.yaml`. If either write fails, leave the workspace non-runnable, do not invoke the
   runner, and report the interactive repair route; never proceed with a config/sidecar mismatch.
4. Only after both files are valid and present, record the workspace as active in the registry
   (`internals.md` → Registry write rules).

This establishes a fresh binding before the first live run. Later model-binding writes replace the whole
sidecar—even when the literal model is unchanged—under the canonical `conventions.md` policy. Ordinary
config edits do not write it.

## 6. First live sample run — the magical moment

This is the payoff. Before invoking the runner, compute `B` from the saved enabled queries and sources and
apply the `first_live_run` row in the canonical
[Agent-data usage decisions](../../../shared/references/internals.md#agent-data-usage-decisions). Render the
one-or-two-sentence first-live context from `../../../shared/references/voice.md` → **Agent-data usage
context** before the first metered call. When `B = 4`, use that reference's approved baseline-four rendering
verbatim. If the dated available-tier fact cannot be verified, use its calls-only fallback. The onboarding
request is scoped consent for this first run: after the context, proceed without a redundant confirmation.

Invoke **`job-search-run`** against the workspace (pass `--workspace <workspace>`). It probes the
source, searches each enabled query, skips postings already seen, judges each new posting against the
brief, reads full descriptions for the promising ones, and writes a digest. On a host that gates parallel
detail reads behind approval, if
`search.parallel_detail_reads: true`, the invocation context must include the exact authorization sentence
your host requires — the saved config records the user's preference, and that sentence is the run's
explicit authorization. Then present the result like a
discovery, not a log dump — surface the **strong and moderate** matches from the digest **as normal message
text in your reply** (rendered markdown — never a code fence, never just the digest's file path):

Before reading or presenting that record/digest, apply
`../../../shared/references/run-lifecycle.md` → **Artifact authority for every reader**: invoke
`lifecycle-fold.sh` for the candidate's exact run_id, require `closed=true` and matching folded state, and
use only the digest derived by that fold. Do not present intended-complete files while the ledger is open.

> e.g. "Here are **N jobs matching your brief**, found seconds ago:"
> then the strong matches (title — company — location — one-line reasoning — link), then
> moderate. Include any "confirm" warning from the digest. Never collapse this to a title-only list.

Handle whatever the run reports, in plain language:

- **Blocked** → the run halts on a named error, surfaced through the run record (the run record is the
  contract; a host exit code, where trustworthy, is an additional signal only). Show that error's cause +
  fix verbatim from `errors.md` and stop the magical framing. Do not improvise quota recovery, account
  state, or a different fix; the named-error table owns the current wording.
- **Zero results, all already known** (only possible on an adopted workspace) → reassuring, not an error:
  "No new postings — you've already seen all N of these."
- **Zero results, literally empty** → actionable: offer to broaden the keywords in the query (and apply it
  conversationally).

Don't show run internals or scores — just the matches and, if relevant, the named error.

## 7. Scheduling (offer it)

Offer to keep the search running automatically. **Advocate the unattended schedule** as the default — one
that keeps firing with **no session open**, on the host's or the OS's own scheduler (a `cron` or `launchd`
job, or the host's native unattended scheduler) — because that's the only way the overnight and
next-morning runs, the ones that matter most, actually happen; an in-session loop stops the instant the
session closes. Compose the schedule for your own host (there's no per-host recipe to paste — `internals.md`
→ Scheduling setup). The **in-session loop is the named fallback**, for a host with no unattended scheduler
or a user who'd rather not change their machine: tell them plainly it **runs only while a session is open**,
so a quiet overnight is expected and closing the session stops it.

The unattended schedule is a real change to the user's machine, so the consent core is intact: **show the
exact line first, write it only on an explicit yes, and leave it user-removable** — never silent, never
auto-installed.

Ask it as a closed choice (`voice.md` → Asking questions). Header `Schedule`; question: "Want me to keep
checking automatically? New matches will land in a digest without you having to ask."; options: **Yes, keep
checking** — "runs on its own, on your chosen cadence" · **No, I'll run it myself** — "a one-off search
stays one command away".

**On yes** — pick the cadence, then start it, prove it, and record it:

Before previewing the schedule, resolve the creating session's exact primary model per `internals.md`. Present
the exact primary and detail bindings as facts, not choices; if the exact primary is unknown, require an
explicit exact available selection before creating a verified schedule. After the canary, the scheduling
registry write includes that exact `primary_model` and origin (`session_inheritance` for the default,
`user_override` for an explicit choice) alongside the ordinary marker.

1. **Ask how often — now, as part of setting the schedule up.** This is the moment the cadence
   actually matters, so ask it here, not before there's a schedule: a closed choice (`voice.md` →
   Asking questions), the plain-language nudge carried by the recommended-first option. Header
   `Frequency`; lead sentence yours to word (e.g. "How often should it check?"); options, recommended
   first:
   - **Daily (Recommended)** — "suits most searches"
   - **Hourly** — "only for a fast-moving, active search"
   - **Every 6 hours** — "a few times a day, without the firehose"
   - **Weekly** — "a slow-burn watch"

   Resolve the proposed `schedule.frequency` to `hourly | every-2-hours | every-6-hours | daily | weekly`
   — `every-2-hours` has no button, so map a typed answer ("every couple of hours") to the nearest allowed
   value and say which one you propose. Hold the value for the preview; do not write it yet.
2. **Compose the cadence** for the chosen frequency from `internals.md` → Scheduling setup (which
   builds the cron time line with `schedule-line.sh` where a shell runtime exists); the host wraps it
   with its own command / launchd / interval translation.
3. **Preview, confirm once, then start.** Apply the `schedule_enable_with_canary` row in the canonical
   [Agent-data usage decisions](../../../shared/references/internals.md#agent-data-usage-decisions) and the
   persistent preview in `../../../shared/references/voice.md`: show the current/proposed baseline, proposed
   cadence comparison, uncertain continuation/detail work, one canary, and exact machine change. Ask one
   scoped yes/no question covering the frequency write, that exact machine change, and exactly one real
   scheduled-path canary. Before that yes, write neither config nor scheduler state. On yes, atomically save
   the frequency and start the unattended schedule. This approval is not standing authority for another
   metered canary attempt.
4. **Prove it works before you record it — run the canary.** Never tell the user it's scheduled until its
   exact unattended invocation has succeeded end to end. Confirm the schedule is **registered** (it appears
   in the host's scheduler), then trigger **one real run through that scheduled invocation** — its own
   permissions and environment, **not this session's** (this session already holds the access the real run
   must prove, so running the canary here would pass while the real scheduled run fails) — and confirm it
   left a fresh record whose exact run_id passes that same `run-lifecycle.md` `lifecycle-fold.sh` authority
   procedure with `closed=true`, matching lifecycle state, `can_complete=true`, and `run_health` other than
   blocked; reached agent-data; and wrote the fold-derived digest in the workspace. An open intended-complete
   record never verifies the canary. The user gets a live digest out of it. If the canary **fails**: diagnose the gap and propose the exact fix. Before every
   metered repair or retry canary, apply the `metered_canary_retry_or_repair` row, give fresh calls-first
   context for that attempt, and obtain a fresh scoped yes. The original schedule approval covered only the
   machine change and first canary. Re-run only after the new consent — loop until green. If it genuinely
   can't be made to work, **name the gap
   plainly and do not claim it's scheduled.** Full flow, consent framing, and failure loop:
   `../../../shared/references/internals.md` → Scheduling setup.
5. **Only after a green canary, record it** so you don't re-ask: set the scheduling marker (`internals.md` →
   Registry write rules — recording the mechanism actually used).

**On no:** leave it unscheduled — tell them they can turn it on later by just asking, and that a one-off run
is always one command away (the composed one-off recipe below).

**Either way, compose the recurring-run and one-off-run recipes for the host and show both to the user**, so
they can re-run the search on demand and restart or remove the schedule themselves. If
`search.parallel_detail_reads: true` and your host gates parallel subagents behind approval, the scheduled
prompt must include the exact subagent-authorization sentence your host requires — the saved config records
the user's preference, and that sentence is the scheduled run's explicit authorization. This pack has no
per-host adapter, so you compose that sentence, and the recipes, for your host yourself.

## 8. Home

You're done. Print the **home view** to land the user on their dashboard — hand off to the format in
`home.md` (status line · latest digest · pipeline · quick actions). Close with a short line that
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
      `npm install -g agent-data` handoff for the user to run, not an error
- [ ] workspace resolved **silently to `~/.job-search`** — no "where should I put it?" question; a path was
      named only as an escape hatch (an explicit user override, or adopting an existing workspace);
      **never clobbered** an existing `config.yaml` / `preferences.md` / `jobs.jsonl`; a fresh workspace was
      recorded active only after a valid version-2 config and matching atomic
      `runs/detail-model-binding.json` write established the exact model binding
- [ ] `preferences.md` exists — a **provisional** brief written from the one-sentence sketch (asked
      verbatim, free-form/inline) or from preferences already in the invocation; supplied material treated
      as background evidence, not auto-preferences; the deeper interview / import are later refinements, not
      first-run gates
- [ ] 2–3 `queries[]` **derived from the brief** and written (no upfront keyword-picking); one compact
      **confidence checkpoint** (provisional brief + search interpretation) shown before the live run
- [ ] on an approval-gating host, if `search.parallel_detail_reads` was unset, the user was asked once about
      parallel subagents; the answer was rendered into `config.yaml`; on yes the host-specific subagent setup
      your host needs was performed (or the exact path + content was shown if blocked); the user saw
      the already-selected exact detail-read model named as a fact, with no second tier-selection decision
- [ ] first **live** `job-search-run` got the canonical one-or-two-sentence context before its first metered
      call (the approved baseline-four rendering when applicable; calls-only when the tier fact could not be
      verified), then ran without a redundant confirmation; strong/moderate matches shown — or the named
      error if blocked
- [ ] shown matches include the digest reasoning and any "confirm" warning, not just titles/companies
- [ ] scheduling offered with the **unattended** schedule advocated as default (in-session loop the named
      fallback — "runs only while a session is open"); on yes the frequency was asked, then one scoped preview
      and confirmation covered the frequency write, exact machine change, and first canary; every later
      metered repair/retry canary got fresh context and a fresh scoped yes; the **canary green (registration
      + one real scheduled run) before** the marker was set — or the gap named and NOT claimed scheduled;
      recurring + one-off recipes composed for
      the host and shown either way; if parallel detail reads were approved on an approval-gating host, the
      scheduled prompt carries the host's required subagent-authorization sentence
- [ ] the workspace location and interview depth were **not** asked before results (silent default;
      provisional sketch); the model was setup-selected silently (never a question); the single "what are you
      looking for?" question was **free-form inline**, not a box; the scheduling and frequency closed choices
      came **after** results (the one host-specific exception is the approval-gating subagent question above);
      every ask carried one line of plain-English context; no internal vocabulary reached the user
      (`voice.md`)
- [ ] home view printed
