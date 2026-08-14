"""Command-line surface for the review core. Five subcommands, stdlib only.

`argparse`, not `click`: `click` is not in galactus's dependency tree, and
adding a dependency for five subcommands in one small file is not a trade
worth making. Parity with guacamayo would be `uv add click` — never
`pip install`, which `pip_guard.sh` blocks.

    validate-finding  < finding.json      exit 0 accept / 1 reject
    detect-signals    < ["path", ...]     active + skipped + injection hits
    detect-track      < {"doc": str, "files": [...]}   track + source + confidence
    derive-phases     < {"doc": str}      live BUILD phases + CROSS capabilities
    verdict           < review.json       the merge decision

`derive-phases` is the only subcommand whose exit code carries a routing
outcome rather than a payload verdict: exit 1 means the doc could not be
routed, which is distinct from a doc that routed to zero remaining phases
because it is finished.

Note the payload divergence: `detect-signals` reads a **bare JSON list**, while
`detect-track` reads a **JSON object** — it has two independent optional inputs
and a list cannot carry both. Same *contract* (JSON in, JSON out, exit 0),
different *payload*. This is deliberate; do not "fix" the inconsistency.

Every rejection carries a machine-readable `reason` tag so the Measurement rows
(schema validity, quoted_span rate, skill-load fidelity) have an instrument.
"""

from __future__ import annotations

import argparse
import json
import sys

from pydantic import ValidationError

from review.models import ReporterDispatchEntry, ReviewFinding
from review.phases import active_capabilities, active_phases, read_doc_signals
from review.signals import active_dimensions, detect_injection, detect_signals, detect_track
from review.validate import validate_finding
from review.verdict import compute_verdict


def _cmd_validate_finding(args: argparse.Namespace) -> int:
    data = json.load(sys.stdin)
    ok, reason, message = validate_finding(
        data, assigned_reporter=args.assigned_reporter, repo_root=args.repo_root
    )
    json.dump({"ok": ok, "reason": reason, "message": message}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if ok else 1


def _cmd_detect_signals(args: argparse.Namespace) -> int:
    files = json.load(sys.stdin)
    signals = detect_signals(files, repo_root=args.repo_root)
    dimensions = active_dimensions(signals)
    json.dump(
        {
            "signals": signals,
            "active": dimensions["active"],
            "skipped": dimensions["skipped"],
            "injection_hits": detect_injection(files, repo_root=args.repo_root),
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


def _cmd_detect_track(args: argparse.Namespace) -> int:
    """Classify a work item as the `ml` or `agent` track.

    Input is a JSON **object** — `{"doc": str, "files": [...]}`, both optional —
    not the bare list `detect-signals` reads. A malformed payload is a
    rejection, not a traceback: the orchestrator piping into this reads JSON, so
    it must get JSON it can branch on.
    """
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        return _payload_error("not_json", f"stdin is not valid JSON: {e}")

    if not isinstance(payload, dict):
        return _payload_error(
            "schema",
            f"payload must be a JSON object like "
            f'{{"doc": "...", "files": [...]}}, got {type(payload).__name__}',
        )

    files = payload.get("files")
    if files is not None and not isinstance(files, list):
        return _payload_error("schema", f"'files' must be a list, got {type(files).__name__}")

    doc = payload.get("doc")
    if doc is not None and not isinstance(doc, str):
        return _payload_error("schema", f"'doc' must be a string, got {type(doc).__name__}")

    result = detect_track(doc_text=doc, files=files, repo_root=args.repo_root)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_derive_phases(args: argparse.Namespace) -> int:
    """Derive the live BUILD phases and CROSS capabilities for a plan doc.

    Input is `{"doc": str}` — the plan doc's text. Routing is content-first, so
    the doc's own front matter decides, never its path.

    `unroutable` is reported explicitly rather than inferred from an empty
    `active` list: a doc whose state cannot be derived and a doc that is
    genuinely finished both have no phases left, and collapsing them is the
    false-confidence failure the three-way outcome rule exists to prevent.
    """
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        return _payload_error("not_json", f"stdin is not valid JSON: {e}")

    if not isinstance(payload, dict):
        return _payload_error(
            "schema",
            f'payload must be a JSON object like {{"doc": "..."}}, got {type(payload).__name__}',
        )

    doc = payload.get("doc")
    if not isinstance(doc, str):
        return _payload_error(
            "schema",
            f"'doc' must be a string, got {type(doc).__name__}",
        )

    signals = read_doc_signals(doc)
    phases = active_phases(signals)
    capabilities = active_capabilities(signals)
    json.dump(
        {
            "signals": signals,
            "unroutable": phases["unroutable"],
            "phases": {"active": phases["active"], "skipped": phases["skipped"]},
            "capabilities": {
                "active": capabilities["active"],
                "skipped": capabilities["skipped"],
            },
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    # An underivable doc is a failure to route, not a successful empty result.
    return 1 if phases["unroutable"] else 0


def _payload_error(reason: str, message: str) -> int:
    """Emit a structured payload rejection on stdout and return exit 1.

    Same shape as `validate-finding`'s rejection, and for the same reason: the
    orchestrator that pipes into this command reads JSON, so a malformed
    payload must come back as JSON it can branch on rather than as a traceback
    on stderr that it can only log.
    """
    json.dump(
        {"error": "invalid_payload", "reason": reason, "message": message},
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 1


def _parse_verdict_payload(
    payload: object,
) -> tuple[list[ReviewFinding], list[ReporterDispatchEntry], list, int]:
    """Coerce a raw verdict payload into `compute_verdict`'s four arguments.

    Raises `TypeError` on a wrong-typed field and `ValueError` on a well-typed
    but out-of-range one; the caller treats both as one rejection. The ladder is
    a pure function over typed inputs, so keeping the enforcement here means
    `compute_verdict` never has to defend itself against stdin.
    """
    if not isinstance(payload, dict):
        raise TypeError(f"payload must be a JSON object, got {type(payload).__name__}")

    for field in ("findings", "dispatch", "injection_hits"):
        if not isinstance(payload.get(field, []), list):
            raise TypeError(f"{field!r} must be a list, got {type(payload[field]).__name__}")

    # `bool` is an `int` subclass, so it would otherwise slip through as 0/1.
    validation_failures = payload.get("validation_failures", 0)
    if isinstance(validation_failures, bool) or not isinstance(validation_failures, int):
        raise TypeError(
            f"'validation_failures' must be an integer, got {type(validation_failures).__name__}"
        )
    if validation_failures < 0:
        raise ValueError(f"'validation_failures' must be >= 0, got {validation_failures}")

    findings_raw = payload.get("findings", [])
    dispatch_raw = payload.get("dispatch", [])
    injection_hits = payload.get("injection_hits", [])

    try:
        findings = [ReviewFinding.model_validate(f) for f in findings_raw]
    except ValidationError as e:
        raise ValueError(f"invalid entry in 'findings': {e}") from e

    try:
        dispatch = [ReporterDispatchEntry.model_validate(d) for d in dispatch_raw]
    except ValidationError as e:
        raise ValueError(f"invalid entry in 'dispatch': {e}") from e

    return findings, dispatch, injection_hits, validation_failures


def _cmd_verdict(args: argparse.Namespace) -> int:
    """Compute the verdict from a review payload.

    Input: `{findings: [...], dispatch: [...], injection_hits: [...],
    validation_failures: int}`. The orchestrator must run this, not read the
    ladder and decide for itself — that is the whole point of the ladder being
    a pure function.

    A malformed payload is a rejection, not a crash: `insufficient_context` is
    a verdict about a review that ran, so a payload that never parsed must not
    borrow it. It exits 1 with `error: invalid_payload` instead.
    """
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        return _payload_error("not_json", f"stdin is not valid JSON: {e}")

    try:
        findings, dispatch, injection_hits, validation_failures = _parse_verdict_payload(payload)
    except (TypeError, ValueError) as e:
        return _payload_error("schema", str(e))

    decision = compute_verdict(findings, dispatch, injection_hits, validation_failures)
    json.dump({"merge_decision": decision.value}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="review.cli", description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Root that file paths are relative to.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate-finding", help="Validate one finding read from stdin.")
    p_validate.add_argument(
        "--assigned-reporter",
        default=None,
        help="The dimension this dispatch was told to load (F7 load verification).",
    )
    p_validate.set_defaults(func=_cmd_validate_finding)

    p_signals = sub.add_parser(
        "detect-signals", help="Detect dispatch signals for a JSON list of files."
    )
    p_signals.set_defaults(func=_cmd_detect_signals)

    p_track = sub.add_parser(
        "detect-track",
        help='Classify a work item: {"doc": str, "files": [...]} on stdin (object, not a list).',
    )
    p_track.set_defaults(func=_cmd_detect_track)

    p_phases = sub.add_parser(
        "derive-phases",
        help='Derive live BUILD phases + CROSS capabilities: {"doc": str} on stdin.',
    )
    p_phases.set_defaults(func=_cmd_derive_phases)

    p_verdict = sub.add_parser("verdict", help="Compute the merge decision.")
    p_verdict.set_defaults(func=_cmd_verdict)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
