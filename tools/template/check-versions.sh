#!/usr/bin/env bash
# Report dependency drift between versions.toml and each consumer manifest.
#
# Read-only by design. This repo is canon for shared versions, and the other
# repos pull from it — a script that edited galactus or dssg would be writing to
# repos it does not own, on branches it did not create. Drift is reported; the
# fix happens in the consumer, on its own branch, with its own test run.
#
# Usage:
#   scripts/check-versions.sh            # report drift, exit 1 if any
#   scripts/check-versions.sh --quiet    # exit code only
#
# Exit codes: 0 = aligned (or only skips), 1 = drift found, 2 = bad invocation.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKSPACE_ROOT="$(cd "$REPO_ROOT/.." && pwd)"
MANIFEST="$REPO_ROOT/versions.toml"

QUIET=0
case "${1:-}" in
  --quiet) QUIET=1 ;;
  "") ;;
  *) echo "usage: $(basename "$0") [--quiet]" >&2; exit 2 ;;
esac

[ -f "$MANIFEST" ] || { echo "FAIL: $MANIFEST not found" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "FAIL: python3 required" >&2; exit 2; }

# The comparison is delegated to python3 for tomllib — parsing TOML and JSON in
# bash would mean regexes over both formats, which is how a checker starts
# reporting drift that isn't there.
python3 - "$MANIFEST" "$WORKSPACE_ROOT" "$QUIET" <<'PY'
import json
import re
import sys
import tomllib
from pathlib import Path

manifest_path, workspace_root, quiet = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] == "1"
spec = tomllib.loads(manifest_path.read_text())

# Flatten [ts] + [ts.frontend] into one name -> version map. Nested tables are
# organisational only; a package is pinned once regardless of which table holds it.
canon: dict[str, str] = {}
for section in ("ts", "py"):
    for key, value in spec.get(section, {}).items():
        if isinstance(value, dict):
            canon.update(value)
        elif key != "requires-python":
            canon[key] = value

findings: list[tuple[str, str, str, str]] = []  # consumer, package, want, got
skipped: list[str] = []
checked = 0


def compare(consumer: str, deps: dict[str, str]) -> None:
    """Record a finding for every dep that is pinned in versions.toml and differs."""
    global checked
    for name, got in deps.items():
        want = canon.get(name)
        if want is None:
            continue  # not a shared dependency — the consumer owns it
        checked += 1
        if got != want:
            findings.append((consumer, name, want, got))


for consumer in spec.get("consumers", []):
    name, rel, kind = consumer["name"], consumer["manifest"], consumer["kind"]
    path = workspace_root / rel

    if not path.exists():
        skipped.append(f"{name} — not checked out at {rel}")
        continue

    raw = path.read_text()

    if kind == "npm":
        # A .jinja package.json is not valid JSON: copier conditionals sit
        # inside the dependency block. Strip the jinja tags, then strip the
        # trailing commas that stripping can leave behind, then parse.
        if path.suffix == ".jinja":
            raw = re.sub(r"\{%.*?%\}", "", raw, flags=re.DOTALL)
            raw = re.sub(r"\{\{.*?\}\}", "TEMPLATED", raw)
            raw = re.sub(r",(\s*[}\]])", r"\1", raw)
        try:
            pkg = json.loads(raw)
        except json.JSONDecodeError as exc:
            skipped.append(f"{name} — could not parse ({exc.msg} at line {exc.lineno})")
            continue
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        compare(name, deps)

    elif kind == "pyproject":
        try:
            data = tomllib.loads(raw)
        except tomllib.TOMLDecodeError as exc:
            skipped.append(f"{name} — could not parse ({exc})")
            continue
        # PEP 621 dependency strings ("anthropic>=0.40") split into name + spec.
        deps = {}
        for entry in data.get("project", {}).get("dependencies", []):
            m = re.match(r"^([A-Za-z0-9._-]+)\s*(.*)$", entry.strip())
            if m and m.group(2):
                deps[m.group(1)] = m.group(2).strip()
        compare(name, deps)

    else:
        skipped.append(f"{name} — unknown kind {kind!r}")

if quiet:
    sys.exit(1 if findings else 0)

for note in skipped:
    print(f"  SKIP  {note}")

if findings:
    print(f"\nDRIFT: {len(findings)} dependency mismatch(es) vs versions.toml\n")
    width = max(len(f"{c} {p}") for c, p, _, _ in findings)
    for consumer, package, want, got in findings:
        label = f"{consumer} {package}"
        print(f"  {label:<{width}}  want {want:<12} got {got}")
    print(
        "\nFix in the consumer repo, on its own branch, with its own test run —\n"
        "this script never edits another repo. If the consumer is right and the\n"
        "manifest is stale, update versions.toml instead."
    )
    sys.exit(1)

print(f"\nOK: {checked} shared dependencies aligned across {len(spec.get('consumers', []))} consumers.")
sys.exit(0)
PY
