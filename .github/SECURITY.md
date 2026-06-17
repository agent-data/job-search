# Security Policy

## Reporting a vulnerability

If you find a security or privacy issue in Job Search, please report it **privately** — do not
open a public issue:

- Use GitHub's private vulnerability reporting: the **"Report a vulnerability"** button on this
  repository's **Security** tab.

We aim to acknowledge a report within 5 business days and will coordinate a fix and disclosure
with you.

## Posture and scope

Job Search handles career-sensitive data **locally**. How that data is kept on your machine and
out of any public repository — the deny-all workspace `.gitignore`, the no-PII-in-repo rule, the
offline test shim — and the **explicit out-of-scope** items (a compromised machine,
prompt-injection in fetched postings) are documented in [`docs/SECURITY.md`](../docs/SECURITY.md).
