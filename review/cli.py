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


def _cmd_verdict(args: argparse.Namespace) -> int:
    """Compute the verdict from a review payload.

    Input: `{findings: [...], dispatch: [...], injection_hits: [...],
    validation_failures: int}`. The orchestrator must run this, not read the
    ladder and decide for itself — that is the whole point of the ladder being
    a pure function.
    """
    payload = json.load(sys.stdin)
    findings = [ReviewFinding.model_validate(f) for f in payload.get("findings", [])]
    dispatch = [
        ReporterDispatchEntry.model_validate(d) for d in payload.get("dispatch", [])
    ]
    decision = compute_verdict(
        findings,
        dispatch,
        payload.get("injection_hits", []),
        payload.get("validation_failures", 0),
    )
    json.dump({"merge_decision": decision.value}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="review.cli", description=__doc__)
    parser.add_argument(
        "--repo-root", default=".", help="Root that file paths are relative to."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser(
        "validate-finding", help="Validate one finding read from stdin."
    )
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
