#!/usr/bin/env python3
"""Preview resolved copier defaults without rendering any files.

Usage:
    python scripts/preview_defaults.py project_type=rag external_systems="[slack,github]"
    python scripts/preview_defaults.py --all  # Show all parameters and their defaults

Reads copier.yaml and resolves the default Jinja expressions given the provided
overrides. Prints a table of all parameters with their resolved values.

NOTE: This is an approximation — copier's actual Jinja evaluation happens in a
specific order (each question sees only prior answers). This script uses a
simplified resolution that handles most cases but may diverge from copier's
actual behavior for deeply nested Jinja dependencies. When in doubt, use
`copier copy --pretend` for authoritative resolution.
"""

import re
import sys
from pathlib import Path


def load_copier_yaml() -> str:
    """Load copier.yaml as raw text (avoid pyyaml dependency)."""
    path = Path(__file__).resolve().parents[2] / "copier.yaml"
    return path.read_text()


def extract_questions(raw: str) -> list[dict]:
    """Extract question definitions from copier.yaml (simplified parser)."""
    questions = []
    current = None

    for line in raw.split("\n"):
        # Top-level key (not indented, not starting with _ or #)
        if re.match(r"^[a-z][a-z_]*:", line):
            if current:
                questions.append(current)
            name = line.split(":")[0]
            current = {
                "name": name,
                "type": "str",
                "default": None,
                "choices": None,
                "when": "true",
            }
        elif current and line.startswith("  "):
            stripped = line.strip()
            if stripped.startswith("type:"):
                current["type"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("default:"):
                val = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                current["default"] = val
            elif stripped.startswith("when:"):
                val = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                current["when"] = val
            elif stripped.startswith("multiselect:") and "true" in stripped.lower():
                current["type"] = "multiselect"

    if current:
        questions.append(current)

    return questions


def resolve_defaults(questions: list[dict], overrides: dict[str, str]) -> dict[str, str]:
    """Resolve defaults in order, applying overrides."""
    resolved = {}

    for q in questions:
        name = q["name"]
        if name in overrides:
            resolved[name] = overrides[name]
        elif q["default"] is not None:
            default = q["default"]
            # Simple Jinja resolution for common patterns
            value = resolve_jinja(default, resolved)
            resolved[name] = value
        else:
            resolved[name] = "(ask user)"

    return resolved


def resolve_jinja(template: str, context: dict[str, str]) -> str:
    """Simplified Jinja resolution for common copier.yaml patterns."""
    if "{{" not in template:
        return template

    result = template

    # Simple variable substitution: {{ var_name }}
    for key, val in context.items():
        result = result.replace(f"{{{{ {key} }}}}", str(val))
        result = result.replace(f"{{{{{key}}}}}", str(val))

    # Common patterns
    # {{ X != 'Y' }}
    neq = re.search(r"\{\{\s*(\w+)\s*!=\s*'([^']+)'\s*\}\}", result)
    if neq:
        var, val = neq.group(1), neq.group(2)
        if var in context:
            return str(context[var] != val)

    # {{ X == 'Y' }}
    eq = re.search(r"\{\{\s*(\w+)\s*==\s*'([^']+)'\s*\}\}", result)
    if eq:
        var, val = eq.group(1), eq.group(2)
        if var in context:
            return str(context[var] == val)

    # {{ X in ['a', 'b', 'c'] }}
    in_list = re.search(r"\{\{\s*(\w+)\s+in\s+\[([^\]]+)\]\s*\}\}", result)
    if in_list:
        var = in_list.group(1)
        items_raw = in_list.group(2)
        items = [i.strip().strip("'\"") for i in items_raw.split(",")]
        if var in context:
            return str(context[var] in items)

    # {{ 'X' in var }}
    str_in = re.search(r"\{\{\s*'([^']+)'\s+in\s+(\w+)\s*\}\}", result)
    if str_in:
        val, var = str_in.group(1), str_in.group(2)
        if var in context:
            return str(val in context[var])

    # If we can't resolve, return the template as-is
    if "{{" in result:
        return f"(unresolved: {template})"
    return result


def print_table(resolved: dict[str, str], questions: list[dict], show_all: bool):
    """Print a formatted table of resolved values."""
    # Filter to user-facing questions unless --all
    if not show_all:
        hidden = {q["name"] for q in questions if q["when"] == "false"}
        display = {k: v for k, v in resolved.items() if k not in hidden}
    else:
        display = resolved

    max_name = max(len(k) for k in display) if display else 10
    max_val = max(len(str(v)) for v in display.values()) if display else 10
    max_val = min(max_val, 60)

    print(f"\n{'Parameter':<{max_name}}  {'Resolved Value':<{max_val}}")
    print(f"{'─' * max_name}  {'─' * max_val}")
    for name, value in display.items():
        val_str = str(value)[:60]
        print(f"{name:<{max_name}}  {val_str:<{max_val}}")

    print(f"\n({len(display)} parameters shown)")


def main():
    args = sys.argv[1:]
    show_all = "--all" in args
    args = [a for a in args if a != "--all"]

    # Parse key=value overrides
    overrides = {}
    for arg in args:
        if "=" in arg:
            key, val = arg.split("=", 1)
            overrides[key] = val

    raw = load_copier_yaml()
    questions = extract_questions(raw)
    resolved = resolve_defaults(questions, overrides)

    if overrides:
        print(f"Overrides applied: {overrides}")
    print_table(resolved, questions, show_all)

    # Show key derived values
    print("\n── Key derived values ──")
    derived_keys = [
        "scaffold_full_project",
        "is_agent_shaped",
        "has_typescript",
        "include_mcp_server",
        "enable_postgres_checkpointer",
    ]
    for k in derived_keys:
        if k in resolved:
            print(f"  {k}: {resolved[k]}")


if __name__ == "__main__":
    main()
