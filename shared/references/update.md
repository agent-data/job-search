# Update check — build stamp, cache, and banner

This contract is read by the **job-search** home/onboarding view only. Headless **job-search-run**
records its own build but never checks for updates. The check is a convenience signal, not a gate:
never auto-update, never block rendering the home view, and never create an `E-*` named error from an
update-check failure.

## Local build

Read `references/build-stamp.md` and parse these literal lines:

- `version: <semver>`
- `content_hash: sha256:<12-hex>`
- `published_stamp_url: <https URL>`

If the local stamp is missing or malformed, skip the update banner. Do not guess a version from a
manifest at runtime.

## Supported hosts

Show update banners only on the primary tested plugin hosts:

- Claude Code
- Codex

For every other platform adapter, skip the update check and banner. Those adapters may still load and run,
but their update command paths are not treated as a verified product surface yet.

## Registry cache

Use the resolved registry from `internals.md` and preserve all existing keys. The optional cache object is:

```json
{
  "update_check": {
    "checked_at": "2026-07-06T12:00:00+00:00",
    "latest": {
      "version": "0.4.0",
      "content_hash": "sha256:abcdef123456",
      "published_stamp_url": "https://raw.githubusercontent.com/agent-data/job-search/main/shared/references/build-stamp.md"
    },
    "status": "ok"
  }
}
```

A cache is fresh for 24 hours. When fresh, use it and do not hit the network. When absent or stale, try one
lightweight fetch of the local stamp's `published_stamp_url`:

```bash
curl -fsSL --max-time 5 "<published_stamp_url>"
```

If `curl` is unavailable, the command fails, or the fetched stamp is malformed, keep any previous cache but
do not show a banner from stale data. The home view still renders normally.

Write a successful fresh result back to the registry with the registry whole-file write rules in
`internals.md`: read current JSON, merge only `update_check`, preserve unrelated keys, keep `version: 1`,
and write atomically.

## Comparison

Compare semantic versions as `major.minor.patch` integers.

- Remote version greater than local version -> update available.
- Remote version equal to local version and `content_hash` differs -> update available. This catches the
  exact "same version, different content" failure from the 2026-07-06 dogfooding pass.
- Remote version lower than local version -> no banner.
- Remote version equal and hash equal -> no banner.
- Any non-semver value -> no banner.

## Banner

When an update is available, render one compact line above the normal home view:

```text
Update available: Job Search <local_version> <local_hash> -> <remote_version> <remote_hash> — run:
<platform update recipe>
```

Copy the platform update recipe verbatim from the active platform's adapter → Packaging & install.
Do not reconstruct command tokens in this file. If no verified update recipe exists for the active adapter,
skip the banner.
