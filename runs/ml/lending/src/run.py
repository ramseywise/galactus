"""runs/ml/lending proving run — logistic baseline → registry candidates → calibration → threshold.

Plan: `.claude/docs/plans/2026-08-10-ml-capability-parity.md` Phase D, Step 15.
Profile and leakage evidence: `runs/ml/lending/docs/DESIGN.md`.

This script is the *harness*, not the modelling. Every decision it makes was taken in
Step 14 and is recorded in DESIGN.md; the constants in `frame.py` are that document
expressed as code, so the two can be diffed. Nothing here infers a treatment at runtime —
an inferred default is an undocumented decision, and the point of the profiling step was
to have none.

MODULE LAYOUT
    `frame.py`     — the Step 14 constants + label/group/drop logic. Toolkit-free.
    `guards.py`    — deterministic leakage guards, abort semantics. Toolkit-free.
    `synthetic.py` — seeded fixture twins for tests and `--dry-run`. Toolkit-free.
    `splits.py`    — grouped fold plan, verified with `assert_no_group_leakage`. Toolkit-coupled.
    `summary.py`   — aggregates-only summary of a result. Toolkit-free.
    `run.py`       — this file: argparse + composition. Toolkit-coupled.

WHAT THIS RUN IS
    A test of the Phase A–C toolkit against a real frame with organic leakage. The data
    is a public US peer-lending extract standing in for collections data that has not
    arrived. **No number this produces is a statement about the client.** See the
    "What this document is, and what it is not" section of DESIGN.md.

DATA HANDLING
    `runs/ml/lending/data/` is gitignored and never read into anything that gets committed. This
    script prints aggregates only — metrics, counts, column names. It never prints a row,
    a row index, or an identifier value. The generated HTML report is written to
    `runs/ml/lending/docs/report.html`, which is TRACKED — ratified 2026-08-15: it embeds
    distributional detail derived from real records, but it is the only real
    `write_report` output in the repo and fraud's tests pin markup against it
    (`runs/ml/fraud/tests/conftest.py`). Private repo; history exposure accepted.

RUNNING IT
    The toolkit lives in `ai-project-template` (Phases A/B target that repo), and galactus
    deliberately declares no ML dependencies — it is not a distributable package. So this
    script is run against an external interpreter that has `ml` importable:

        ML_PACKAGE_ROOT=/path/containing/ml python runs/ml/lending/src/run.py

    `ML_PACKAGE_ROOT` is prepended to `sys.path`. Without it the import fails with a
    message saying so, rather than a bare ImportError.

    `--dry-run` exercises the identical path — guards, grouped split, fit, calibration,
    threshold, report, summary, record — on the seeded synthetic twin: no `data/` read,
    no network, seconds, with the report and record routed to a temp directory so the
    tracked real report and `runs/_index/` are never touched. It still needs
    `ML_PACKAGE_ROOT`: dry means no data, not no toolkit.

    Real runs write their `RunRecord` to `runs/_index/` via `experiments.io` — see
    `runs/_index/README.md` for the grain and how to read a record diff.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = POC_ROOT / "data" / "lending_club_2015Q4.csv"
DEFAULT_REPORT = POC_ROOT / "docs" / "report.html"
#: runs/_index/ — the committed record index, one file per training execution.
INDEX_ROOT = POC_ROOT.parents[1] / "_index"

# --- toolkit import ---------------------------------------------------------------
# Done before the `ml.*` imports so the failure is a sentence, not a stack trace.
_ml_root = os.environ.get("ML_PACKAGE_ROOT")
if _ml_root:
    sys.path.insert(0, _ml_root)

try:
    import experiments.record  # noqa: F401 — proves the rendered tree includes experiments/

    from runs._shared.parity import persist

    from ml.reporting.html import write_report
    from ml.workflows.classification import run_classification
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit(
        f"could not import the ML toolkit ({exc}).\n"
        "The toolkit lives in ai-project-template under\n"
        "  template/_scaffold/{{ py_project_root }}/ — both `ml` and `experiments` render\n"
        "as siblings there — and galactus declares no ML dependencies by design. Point\n"
        "ML_PACKAGE_ROOT at a rendered tree containing both packages, in an environment\n"
        "with pandas, scikit-learn, catboost and lightgbm installed."
    ) from exc

# Sibling modules — resolvable because this file's directory is on sys.path (as the
# script dir when run directly, via the tests' conftest insert otherwise). `splits`
# imports `ml.*` itself, which the guard above has already proven importable; the
# imports sit below the guard by necessity, hence the E402 opt-outs.
import synthetic  # noqa: E402
from frame import COST_FN, COST_FP, GROUP_COL, SEED, TARGET, load_frame, prepare_frame  # noqa: E402
from guards import (  # noqa: E402
    assert_excluded_absent,
    final_metric_alarm,
    single_feature_auc_alarm,
)
from run_record import assemble_run_record  # noqa: E402
from splits import build_split_plan  # noqa: E402
from summary import summarise  # noqa: E402

logger = logging.getLogger("ml_lending.run")

#: The dry-run's model set: venv-available only (no lightgbm in galactus's `ml` group).
DRY_RUN_MODELS = ["logistic"]


def record_destination(*, dry_run: bool, frame_hash: str, now: datetime, report_path: Path) -> Path:
    """Where a run's record lands: `runs/_index/{utc_timestamp}-{frame_hash[:8]}.json`
    for real runs (committed, Key Decision 7); the identical format beside the temp
    report for dry-runs, which never write into the index (Key Decision 5)."""
    name = f"{now:%Y%m%dT%H%M%SZ}-{frame_hash[:8]}.json"
    if dry_run:
        return report_path.parent / name
    return INDEX_ROOT / name


def run_pipeline(
    df, *, n_splits: int, models: list[str] | None, report_path: Path, summary_json: Path | None
) -> tuple[dict, object]:
    """The full harness path on an already-prepared frame: guards → split → fit →
    metric alarm → report → summary. Returns `(summary, result)` — the raw result rides
    along so `main` can assemble the run record from it. The seam tests use to drive the
    planted-leak twin through the real path — a `GuardError` here is the abort working,
    not a test bug."""
    # Guards (a) + (b): the drop actually held, and no lone column separates the label.
    # Abort semantics (Key Decision 6) — a leak found here never reaches the fit.
    assert_excluded_absent(df)
    single_feature_auc_alarm(df)

    split_plan = build_split_plan(df, n_splits)

    result = run_classification(
        # GROUP_COL is dropped here: the folds already encode the grouping, and leaving
        # the column in would let it be target-encoded as a feature. See build_split_plan.
        df.drop(columns=[GROUP_COL]),
        target=TARGET,
        output="binary",
        models=models,
        # 20.56% minority sits just above the toolkit's 20% strong-imbalance line, so the
        # cheapest correct option applies: reweight, do not synthesise. DESIGN.md notes
        # it is close enough to the boundary to re-check on real data.
        sampling="class_weight",
        # Grouping arrives via `splitter`, not `group_col` — passing both is the coupling
        # build_split_plan exists to avoid. `time_col` is moot for the same reason: the
        # extract spans two months (Nov–Dec 2015). DESIGN.md open item 1.
        splitter=split_plan,
        calibrate=True,
        cost_fp=COST_FP,
        cost_fn=COST_FN,
        seed=SEED,
    )

    # Structural guarantee, asserted rather than trusted: if any model fitted a
    # transformer outside its pipeline, every CV score above is inflated.
    result.assert_no_transform_outside_pipeline()

    # Guard (d): a near-perfect model on this frame means a leak got through anyway.
    final_metric_alarm({m.name: getattr(m.metrics, "roc_auc", None) for m in result.models})

    out = write_report(result, report_path, title="lending proving run — Lending Club proxy")
    summary = summarise(result, out=out)

    if summary_json:
        summary_json.write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    return summary, result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="synthetic frame, tiny model set, artifacts to a temp path; no data/, no network",
    )
    parser.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="registry names to run; default is every available binary classifier "
        f"(dry-run default: {DRY_RUN_MODELS})",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="write the aggregate summary here (metrics only, no row data)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.dry_run:
        df = prepare_frame(synthetic.clean_frame(SEED))
        models = args.models if args.models is not None else DRY_RUN_MODELS
        report_path = args.report
        if report_path == DEFAULT_REPORT:
            # Never overwrite the tracked real report with synthetic output.
            report_path = Path(tempfile.mkdtemp(prefix="lending-dry-run-")) / "report.html"
        logger.info("dry run: synthetic frame, models=%s, report=%s", models, report_path)
    else:
        df = load_frame(args.data)
        models = args.models
        report_path = args.report

    summary, result = run_pipeline(
        df,
        n_splits=args.n_splits,
        models=models,
        report_path=report_path,
        summary_json=args.summary_json,
    )

    # Record assembly — construction re-fires the registry's own validation — then
    # persistence via the registry's serializer (AIT#83), never a local writer.
    record = assemble_run_record(result, df.drop(columns=[GROUP_COL]), args)
    logger.info(
        "run record assembled: %s=%s (code %s, frame %s)",
        record.headline_metric,
        record.metrics[record.headline_metric],
        record.code.git_sha,
        record.data.frame_hash[:12],
    )
    written = persist(
        record,
        dry_run=args.dry_run,
        target=record_destination(
            dry_run=args.dry_run,
            frame_hash=record.data.frame_hash,
            now=datetime.now(UTC),
            report_path=report_path,
        ),
    )
    logger.info("run record written: %s", written)

    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
