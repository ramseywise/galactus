#!/usr/bin/env python3
"""Fail when a module under the project's source roots is imported by nothing.

Why this exists (AIT-51): this is the Python half of the guard AIT-44 shipped for
the TypeScript render (`scripts/check-unimported.mjs`). Both renders have the same
failure mode — a module ships into every scaffold referenced by neither the agent
nor a test, and gets its first real exercise from a type checker rather than a code
path. `security/guards.py` was exactly that on the Python side (#50).

Why a bespoke walker rather than an off-the-shelf tool:

  - `vulture` is heuristic dead-code detection. It reports unused *names* with a
    confidence score, false-positives on Pydantic models, FastAPI route handlers
    and LangGraph node registrations, and needs a whitelist file that rots.
  - `ruff`'s F401 is per-file *unused imports* — the opposite question.
  - `deptry` works at dependency/package level, not module level.

The question here is narrow and structural: **does any other module import this
one?** An `ast.walk` over `Import`/`ImportFrom` answers it exactly, the way the TS
version walks specifiers.

The check is module-level ("does any other file import this?"), not export-level.
Unused individual exports are a separate, noisier question; a starter template
legitimately ships helper functions the user has not called yet. A file nobody
imports at all is never legitimate.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Process entry points: reached by the runtime, a Makefile target, or a dynamic
# import — never by a static `import` from another module. Anything listed here is
# exempt from needing an importer, and every entry MUST say why it cannot be
# reached statically. A module that could be imported normally does not belong
# here; wire it into a real code path or give it a test instead.
#
# Paths are module paths relative to a source root (dotted), matching how the
# render's PYTHONPATH exposes them.
ENTRY_POINTS: dict[str, str] = {
    # `make {agent}-up` runs `uvicorn agents.<agent>.main:app` — the ASGI app is
    # named on a command line, so no module imports main.py.
    "agents.*.main": "uvicorn target (Makefile: `uvicorn agents.<agent>.main:app`)",
    # `make {agent}-api-up` runs the ADK HTTP edge the same way.
    "agents.*.api.main": "uvicorn target (Makefile: ADK api app)",
    # `python -m core.pipelines.corpus <cmd>` — __main__.py is executed by the
    # interpreter's -m machinery, never imported.
    "core.pipelines.corpus.__main__": "`python -m` entry (Makefile: corpus-preprocess/ingest)",
    # `make eval-run` / `eval-gate` / `eval-report` run `python -m evals.pipelines.run`.
    "evals.pipelines.run": "`python -m` entry (Makefile: eval-run/eval-gate/eval-report)",
    # `make eval-grade*` runs `python -m evals.pipelines.grade`.
    "evals.pipelines.grade": "`python -m` entry (Makefile: eval-grade/eval-grade-gate)",
    # `make eval-compare` runs `python -m evals.pipelines.compare`.
    "evals.pipelines.compare": "`python -m` entry (Makefile: eval-compare)",
    # `make eval-calibrate` runs `python -m evals.pipelines.calibration`.
    "evals.pipelines.calibration": "`python -m` entry (Makefile: eval-calibrate)",
    # `make rag-build-index` runs `python -m agents.rag_agent.build_index`.
    "agents.rag_agent.build_index": "`python -m` entry (Makefile: rag-build-index)",
    # evals/graders/custom/__init__.py loads this package's modules with
    # pkgutil.iter_modules + importlib.import_module so @register decorators run.
    # The user's own graders land here; nothing imports them by name, by design.
    "evals.graders.custom.*": "dynamically imported by evals.graders.custom.all_graders()",
    # `make nbks-corpus` runs `marimo run nbks/corpus_analysis.py` — a notebook,
    # executed by marimo rather than imported.
    "nbks.corpus_analysis": "marimo notebook (Makefile: nbks-corpus)",
}

# ADK discovers an agent package by importing `<pkg>.agent` and reading its
# `root_agent`; `adk web` / `adk run` name the package directory, so no module
# imports agent.py statically.
ENTRY_POINTS["agents.*.agent"] = "ADK entry (`adk run`/`adk web` import <pkg>.agent:root_agent)"


def import_roots() -> list[Path]:
    """Read the render's own import roots from pyproject.toml.

    `pythonpath` is the single source of truth for how this project resolves
    imports (pytest reads it directly; the Makefile mirrors it into PYTHONPATH).
    Deriving the roots from it keeps this guard correct across the whole render
    matrix — flat vs nested layout, ml on or off — instead of hardcoding paths
    that only hold for one row.

    These roots define how a dotted module name resolves. Which files the guard
    actually *judges* is a narrower question — see `source_dirs()`.
    """
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    raw = config.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("pythonpath", ["."])
    roots = []
    for entry in raw:
        path = (ROOT / entry).resolve()
        if path.is_dir():
            roots.append(path)
    return roots


# Package dirs that hold the project's own source. These are the files the guard
# judges — the same trees the Makefile's LINT_PATHS covers, minus tests/. `.` is
# an import root (so `core.x` and `evals.x` resolve) but is NOT a source dir:
# rooting the scan there would sweep in tests/, scripts/, and any standalone
# sibling tree and report each as its own orphan.
SOURCE_DIR_NAMES = ("core", "evals", "ml", "src")


def source_dirs(roots: list[Path]) -> list[Path]:
    """The directories whose modules must each have an importer.

    An import root that is itself a package tree (e.g. `backend/src`) is a source
    dir outright. The repo root contributes only its named source packages.
    """
    dirs: list[Path] = []
    for root in roots:
        if root == ROOT:
            dirs.extend(d for name in SOURCE_DIR_NAMES if (d := root / name).is_dir())
        else:
            dirs.append(root)
    # Deduplicate: under a flat layout `./src` is an import root AND `src` is a
    # named source package under `.`, so the same dir arrives twice.
    dirs = sorted(set(dirs))
    # A nested root (backend/src) can also be reached via a parent root
    # (backend, added for ml); keep the outermost only so files aren't scanned
    # twice under two different module names.
    return [d for d in dirs if not any(d != o and o in d.parents for o in dirs)]


# Directories that are never project source: vendored tooling payload, caches,
# and the virtualenv. Mirrors pyproject's ruff extend-exclude plus the obvious
# build/VCS noise.
SKIP_DIRS = {
    ".claude",
    ".agents",
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    "frontend",
    "infrastructure",
    "mcp_servers",
}


def python_files(base: Path) -> list[Path]:
    """Every .py file under base, skipping vendored and generated trees."""
    if not base.is_dir():
        return []
    found = []
    for path in base.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.relative_to(base).parts):
            continue
        found.append(path)
    return found


def module_name(path: Path, roots: list[Path]) -> str | None:
    """Dotted module name for a file, as the render's PYTHONPATH would see it.

    Longest matching root wins: with `backend/src` and `.` both on the path,
    backend/src/guardrails/guards.py is `guardrails.guards`, not
    `backend.src.guardrails.guards`.
    """
    best: str | None = None
    best_len = -1
    for root in roots:
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if len(str(root)) <= best_len:
            continue
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        if not parts:
            continue
        best = ".".join(parts)
        best_len = len(str(root))
    return best


def imported_modules(path: Path, own_module: str | None, is_package: bool = False) -> set[str]:
    """Modules named by this file's import statements, absolute and relative.

    Relative imports (`from .nodes import generate`) are resolved against the
    importing module's own package, so `level`-prefixed forms count as importers
    the same way absolute ones do. This is the Python analogue of the TS version
    resolving `./agent.js` against the importing file's directory.
    """
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError:
        # A file that does not parse cannot be reasoned about; the linter and
        # type checker will report it far more usefully than this guard would.
        return set()

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and own_module is not None:
                # `from . import x` inside module p.q.mod resolves against p.q;
                # each extra dot strips one more package level. Inside a package's
                # __init__.py, own_module is ALREADY the package (p.q for
                # p/q/__init__.py), so level 1 resolves against it directly — one
                # fewer segment to strip. This is the re-export idiom
                # (`from .thing import Thing`), so getting it wrong would report
                # every re-exported submodule as an orphan.
                strip = node.level - 1 if is_package else node.level
                parts = own_module.split(".")
                base = ".".join(parts[: len(parts) - strip] if strip else parts)
                prefix = f"{base}.{node.module}" if node.module and base else (node.module or base)
            else:
                prefix = node.module or ""
            if not prefix:
                continue
            names.add(prefix)
            # `from pkg.mod import name` also imports `pkg.mod.name` when name is
            # a submodule rather than an attribute — record both readings.
            for alias in node.names:
                if alias.name != "*":
                    names.add(f"{prefix}.{alias.name}")
    return names


def is_exempt(module: str) -> str | None:
    """Return the reason this module is an entry point, or None."""
    for pattern, reason in ENTRY_POINTS.items():
        if pattern == module:
            return reason
        if "*" in pattern:
            head, _, tail = pattern.partition("*")
            if not module.startswith(head):
                continue
            rest = module[len(head) :]
            if tail == "":
                return reason
            # `agents.*.main` — the wildcard covers exactly one path segment.
            if tail.startswith(".") and rest.endswith(tail) and "." not in rest[: -len(tail)]:
                return reason
    return None


def is_namespace_init(path: Path) -> bool:
    """True for an __init__.py that only marks a package (no runtime content).

    A bare or docstring/`from __future__`-only __init__.py is package plumbing,
    not a module with behaviour to wire up. Its package is reached whenever any
    submodule is imported, and demanding a direct importer for it would only
    push noise into ENTRY_POINTS. An __init__.py that re-exports (the common
    Python idiom this guard must respect) has real statements and is judged
    normally — and its re-exports count as imports of the submodules.
    """
    if path.name != "__init__.py":
        return False
    try:
        body = ast.parse(path.read_text(), filename=str(path)).body
    except SyntaxError:
        return False
    for node in body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # module docstring
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        return False
    return True


def main() -> int:
    roots = import_roots()
    if not roots:
        print("FAIL: no import roots found — is tool.pytest.ini_options.pythonpath set?")
        return 1
    sources = source_dirs(roots)
    if not sources:
        print("OK: no Python source roots in this render — nothing to check.")
        return 0

    source_files = sorted({f for d in sources for f in python_files(d)})
    by_module: dict[str, Path] = {}
    for path in source_files:
        name = module_name(path, roots)
        if name and not is_namespace_init(path):
            by_module.setdefault(name, path)

    # Tests count as importers deliberately: a module exercised only by a test is
    # wired enough to have been imported and run at least once, which is the bar
    # this guard enforces. Test files are importers only — never subjects.
    #
    # Edges are kept as (importer, imported) rather than a flat set of imported
    # names: reachability has to be judged from OUTSIDE the module being judged.
    # A package whose __init__ re-exports its own submodules would otherwise
    # bootstrap itself — __init__ marks thing.py imported, thing.py then marks
    # the package reachable — and an entirely unreachable package would pass.
    edges: list[tuple[str, str]] = []
    test_files = python_files(ROOT / "tests")
    for path in sorted(set(source_files) | set(test_files)):
        importer = module_name(path, roots)
        for target in imported_modules(path, importer, is_package=path.name == "__init__.py"):
            edges.append((importer or "", target))

    def reached_from_outside(module: str) -> bool:
        """True if anything outside `module`'s own subtree imports it.

        A module counts as reached when it is imported directly, or — for a
        package — when any module under it is: importing `pkg.sub` executes
        `pkg/__init__.py`, so the package is genuinely loaded.
        """
        for importer, target in edges:
            if target != module and not target.startswith(f"{module}."):
                continue
            if importer == module or importer.startswith(f"{module}."):
                continue  # self-referential: the package importing its own parts
            return True
        return False

    orphans = []
    for module, path in sorted(by_module.items()):
        if reached_from_outside(module):
            continue
        if is_exempt(module):
            continue
        orphans.append((module, path.relative_to(ROOT)))

    if orphans:
        print("FAIL: these modules are imported by nothing:\n")
        for module, rel in orphans:
            print(f"  {rel}  ({module})")
        print(
            "\n"
            "Every module must be reached by the agent, by another module, or by a\n"
            "test. Fix by wiring it into a real code path, or — if it cannot be\n"
            "wired — add a test that imports and exercises it, and say why in the\n"
            "module's header comment.\n"
            "\n"
            "A genuine process entry point (uvicorn target, `python -m` runner,\n"
            "dynamically imported plugin) belongs in ENTRY_POINTS in\n"
            "scripts/check_imports.py, with a comment saying why it cannot be\n"
            "imported statically."
        )
        return 1

    scanned = ", ".join(sorted(str(d.relative_to(ROOT)) for d in sources))
    print(f"OK: all {len(by_module)} modules under {scanned} have an importer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
