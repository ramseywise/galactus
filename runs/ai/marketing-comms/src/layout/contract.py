"""Loading layout templates from disk.

Templates are data, not code: the contract everything else is validated against
lives in `templates/*.json` so a designer can change a word limit without a
deploy. Loading is strict — a malformed template fails at load, not at
generation time.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from models import LayoutTemplate

TEMPLATE_DIR_NAME = "templates"


class TemplateNotFoundError(FileNotFoundError):
    """Raised when a template id has no corresponding JSON file."""


def default_template_dir() -> Path:
    """Locate the repo's `templates/` directory.

    Walks up from this file to the project root. Callers that need a different
    location pass `template_dir` explicitly.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / TEMPLATE_DIR_NAME
        if candidate.is_dir():
            return candidate
    raise TemplateNotFoundError(
        f"could not locate a {TEMPLATE_DIR_NAME}/ directory above {__file__}"
    )


def load_template_file(path: str | Path) -> LayoutTemplate:
    """Load and validate a single template JSON file."""
    p = Path(path)
    if not p.is_file():
        raise TemplateNotFoundError(f"template file not found: {p}")
    with p.open(encoding="utf-8") as fh:
        return LayoutTemplate.model_validate(json.load(fh))


def load_template(template_id: str, template_dir: str | Path | None = None) -> LayoutTemplate:
    """Load a template by id from `template_dir` (default: repo `templates/`).

    Raises:
        TemplateNotFoundError: If no `{template_id}.json` exists.
        ValueError: If the file exists but violates the template schema, or if
            its `template_id` field disagrees with the requested id.
    """
    directory = Path(template_dir) if template_dir is not None else default_template_dir()
    template = load_template_file(directory / f"{template_id}.json")
    if template.template_id != template_id:
        raise ValueError(
            f"template id mismatch: file {template_id}.json declares "
            f"template_id={template.template_id!r}"
        )
    return template


@lru_cache(maxsize=8)
def load_template_cached(template_id: str) -> LayoutTemplate:
    """Cached load from the default template directory.

    Templates are immutable at runtime, so caching is safe. Tests that write
    ad-hoc templates should use `load_template` with an explicit directory.
    """
    return load_template(template_id)


def available_templates(template_dir: str | Path | None = None) -> list[str]:
    """List loadable template ids in the directory."""
    directory = Path(template_dir) if template_dir is not None else default_template_dir()
    return sorted(p.stem for p in directory.glob("*.json"))
