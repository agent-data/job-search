# Install job-search on Hermes

Hermes-specific bootstrap. This is a pre-install document — once installed, you never need it again; drive
everything from the `job-search` skill. (Other hosts: ignore this file and follow your own install path.)

## 1. Install and load the plugin
- Add the source and install the skills:
  - `hermes skills tap add agent-data/job-search`
  - `hermes skills install job-search`   # tap add registers the source; install loads the skills [PIN: confirm on a live install]
  - Alternatives: point `skills.external_dirs` in `~/.hermes/config.yaml` at the repo's `skills/` dir, or
    copy the skill directories into `~/.hermes/skills/<category>/<skill>/`.
- If installing from this repo's source tree, first run `./scripts/build.sh` so each skill carries its
  synced references and the bundled state-ops runtime.

## 2. Verify the skills are visible
- `hermes skills list` should show `job-search`, `job-search-run`, `job-preference-interview`,
  `evaluate-job-fit`, and `job-search-agent` (each is also a slash command, e.g. `/job-search-run`).

## 3. Set up agent-data (the only step that needs you)
- `agent-data init --hermes --api-key <KEY> --yes` then `agent-data whoami` → expect `api_key_set: true`.
- Get a key by creating an agent-data account first; everything else installs without your input.

## 4. First run
- Run the `job-search` skill (or `/job-search`). On first run it onboards end-to-end: a quick prerequisite
  check, a private workspace, your preferences (it can draft a starting point from your prior sessions, with
  your permission), your first live search shown as real matches, and a recurring schedule delivered to a
  channel you choose.
