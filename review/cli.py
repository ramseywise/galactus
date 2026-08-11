"""Command-line surface for the review core. Three subcommands, stdlib only.

`argparse`, not `click`: `click` is not in galactus's dependency tree, and
adding a dependency for three subcommands in one small file is not a trade
worth making. Parity with guacamayo would be `uv add click` — never
`pip install`, which `pip_guard.sh` blocks.

    validate-finding  < finding.json      exit 0 accept / 1 reject
    detect-signals    < ["path", ...]     active + skipped + injection hits
    verdict           < review.json       the merge decision

Every rejection carries a machine-readable `reason` tag so the Measurement rows
(schema validity, quoted_span rate, skill-load fidelity) have an instrument.
"""

from __future__ import annotations

import argparse
import json
import sys

from pydantic import ValidationError

from review.models import ReporterDispatchEntry, ReviewFinding
from review.signals import active_dimensions, detect_injection, detect_signals
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


def _verdict_error(reason: str, message: str) -> int:
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
        return _verdict_error("not_json", f"stdin is not valid JSON: {e}")

    try:
        findings, dispatch, injection_hits, validation_failures = _parse_verdict_payload(payload)
    except (TypeError, ValueError) as e:
        return _verdict_error("schema", str(e))

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

    p_verdict = sub.add_parser("verdict", help="Compute the merge decision.")
    p_verdict.set_defaults(func=_cmd_verdict)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
