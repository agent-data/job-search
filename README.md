# Job Search OS

Turn Claude Code into an operating system for your job search. Define your preferences once,
then let Claude Code pull fresh job postings on a schedule, judge each one's relevance against
what you actually want, and hand you a ranked digest — plus on-demand resume comparison and
truthful resume tailoring.

> **Status:** under construction. Core runner (`evaluate-job-fit`, `job-search-run`) lands first.

## Requirements
- [Claude Code](https://claude.com/claude-code)
- The `agent-data` CLI: `npm install -g agent-data`, then set your key (`agent-data whoami` to verify).

## Privacy
Your personal data (preferences, resumes, matched jobs) lives in a separate **private** workspace
folder (default `~/job-search/`) and must never be committed to a public repo. See `templates/workspace.gitignore`.

## License
MIT — see `LICENSE`.
