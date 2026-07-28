# Job Search installed — one step remains

Hermes installed the complete Job Search repository into this directory.

**The five skills are not yet available by their normal names.** The Hermes
instance running this install must add this plugin's `skills/` directory to the
active profile's `skills.external_dirs`, then verify discovery. The remaining
steps are in `INSTALL_FOR_HERMES.md`, in this directory.

Hermes builds its available-skills list when a session starts, so the skills
appear only in a session started after that configuration step (`/new`).

Installation is complete only after the verification steps in
`INSTALL_FOR_HERMES.md` pass.
