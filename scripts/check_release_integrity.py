#!/usr/bin/env python3
"""Release integrity checks for versioned job-search plugin artifacts.

Dev-side tooling only: skills ship markdown, not this Python script.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

VERSION_MANIFESTS = (
    pathlib.Path(".claude-plugin/plugin.json"),
    pathlib.Path(".codex-plugin/plugin.json"),
    pathlib.Path(".cursor-plugin/plugin.json"),
    pathlib.Path(".factory-plugin/plugin.json"),
    pathlib.Path("gemini-extension.json"),
    pathlib.Path("package.json"),
)
PRIMARY_MANIFEST = pathlib.Path(".claude-plugin/plugin.json")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _rel(path):
    return pathlib.Path(path).as_posix()


def _read_json_file(path):
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f), None
    except OSError as e:
        return None, f"{_rel(path)}: cannot read JSON ({e})"
    except ValueError as e:
        return None, f"{_rel(path)}: invalid JSON ({e})"


def _read_json_at_revision(root, rel, revision):
    proc = subprocess.run(
        ["git", "show", f"{revision}:{rel.as_posix()}"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().replace("\n", " ")
        return None, f"{rel.as_posix()}: cannot read from {revision} ({detail})"
    try:
        return json.loads(proc.stdout), None
    except ValueError as e:
        return None, f"{rel.as_posix()}: invalid JSON at {revision} ({e})"


def _version_tuple(version):
    if not SEMVER_RE.match(version):
        return None
    return tuple(int(part) for part in version.split("."))


def _manifest_versions(root):
    versions = {}
    hits = []
    for rel in VERSION_MANIFESTS:
        data, err = _read_json_file(root / rel)
        if err:
            hits.append(err)
            continue
        version = str(data.get("version", "")).strip()
        if not version:
            hits.append(f"{rel.as_posix()}: missing non-empty version")
            continue
        if _version_tuple(version) is None:
            hits.append(f"{rel.as_posix()}: version '{version}' is not semver x.y.z")
            continue
        versions[rel] = version
    return versions, hits


def check_version_sync(root):
    versions, hits = _manifest_versions(root)
    primary = versions.get(PRIMARY_MANIFEST)
    if primary is None:
        return hits or [f"{PRIMARY_MANIFEST.as_posix()}: missing primary version manifest"]
    for rel in VERSION_MANIFESTS:
        version = versions.get(rel)
        if version is not None and version != primary:
            hits.append(
                f"{rel.as_posix()}: version sync mismatch: {version} "
                f"(expected {primary} from {PRIMARY_MANIFEST.as_posix()})"
            )
    return hits


def _git_changed_paths(root, base):
    commands = (
        ("git diff", ["git", "diff", "--name-only", f"{base}...HEAD"]),
        ("git diff", ["git", "diff", "--name-only"]),
        ("git diff", ["git", "diff", "--name-only", "--cached"]),
        ("git ls-files", ["git", "ls-files", "--others", "--exclude-standard"]),
    )
    paths = set()
    hits = []
    for label, cmd in commands:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip().replace("\n", " ")
            hits.append(f"{label} failed ({' '.join(cmd)}): {detail}")
            continue
        paths.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
    return sorted(paths), hits


def _is_generated_stamp(path):
    return pathlib.PurePosixPath(path).name == "build-stamp.md"


def _is_skill_eval(path):
    parts = pathlib.PurePosixPath(path).parts
    return len(parts) >= 4 and parts[0] == "skills" and parts[2] == "evals"


def _is_runtime_surface(path):
    if _is_generated_stamp(path) or _is_skill_eval(path):
        return False
    return (
        path.startswith("skills/")
        or path.startswith("shared/references/")
        or path.startswith("shared/scripts/")
    )


def _primary_version_at(root, base):
    data, err = _read_json_at_revision(root, PRIMARY_MANIFEST, base)
    if err:
        return None, err
    version = str(data.get("version", "")).strip()
    if _version_tuple(version) is None:
        return None, f"{PRIMARY_MANIFEST.as_posix()}: base version '{version}' is not semver x.y.z"
    return version, None


def _current_primary_version(root):
    data, err = _read_json_file(root / PRIMARY_MANIFEST)
    if err:
        return None, err
    version = str(data.get("version", "")).strip()
    if _version_tuple(version) is None:
        return None, f"{PRIMARY_MANIFEST.as_posix()}: current version '{version}' is not semver x.y.z"
    return version, None


def check_version_bump(root, base):
    changed, hits = _git_changed_paths(root, base)
    if hits:
        return hits
    runtime_paths = [path for path in changed if _is_runtime_surface(path)]
    if not runtime_paths:
        return []

    base_version, err = _primary_version_at(root, base)
    if err:
        return [err]
    current_version, err = _current_primary_version(root)
    if err:
        return [err]

    if _version_tuple(current_version) > _version_tuple(base_version):
        return []

    detail = ", ".join(runtime_paths)
    return [
        "runtime surface changed without a forward version bump in "
        f"{PRIMARY_MANIFEST.as_posix()} "
        f"(base {base_version}, current {current_version}); changed: {detail}"
    ]


def main():
    ap = argparse.ArgumentParser(description="Check release manifest integrity.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--check-version-sync", action="store_true")
    ap.add_argument("--check-version-bump", action="store_true")
    ap.add_argument("--base", help="base git revision for --check-version-bump")
    args = ap.parse_args()

    root = pathlib.Path(args.root).resolve()
    if not args.check_version_sync and not args.check_version_bump:
        ap.error("select at least one check")
    if args.check_version_bump and not args.base:
        ap.error("--check-version-bump requires --base")

    hits = []
    if args.check_version_sync or args.check_version_bump:
        hits.extend(check_version_sync(root))
    if args.check_version_bump:
        hits.extend(check_version_bump(root, args.base))

    if hits:
        print("Release integrity failed:")
        for hit in hits:
            print(f"- {hit}")
        return 1

    print("Release integrity: version sync clean; version bump clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
