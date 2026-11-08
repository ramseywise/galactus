"""`kg` command line. Run as `python -m kg.cli <command>` from `runs/ai/knowledge-graph`.

Every command accepts `--dry-run`. For commands that would call a model it means no call
and zero spend; read-only commands accept it and behave the same. Live spend (`build`
without `--dry-run`, `propose`, `repeat`) refuses unless `KG_LIVE=1` is set, naming it.
Output locations are all flags, so tests write only under `tmp_path`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from kg import build as kb
from kg.config import ConfigError, Settings
from kg.contract import NotApproved, approve, load_pack, pack_hash, require_approved
from kg.judge.seat import JudgeSeat
from kg.models import NotApplicable
from kg.profile import BuildRefused, census, estimate_cost, iter_pages, refuse_if_empty
from kg.propose.proposer import Proposer
from kg.route import apply_decisions, render_table
from kg.store import SqliteStore

COMMANDS = (
    "profile",
    "approve",
    "propose",
    "build",
    "inspect",
    "review",
    "promote",
    "unpromote",
    "verify",
    "repeat",
    "ask",
    "label",
)
EXIT_REFUSED = 2
EXIT_HALTED = 3


class RefusedError(Exception):
    """A command refused by name; printed to stderr, exit code 2."""


def _common() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--dry-run", action="store_true", help="no model calls, zero spend")
    p.add_argument("--corpus-root", type=Path, default=None)
    p.add_argument("--db", type=Path, default=None, help="SQLite store (default KG_DB_PATH)")
    p.add_argument("--records-dir", type=Path, default=kb.DEFAULT_RECORDS_DIR)
    p.add_argument("--decisions-dir", type=Path, default=kb.DEFAULT_DECISIONS_DIR)
    p.add_argument("--pack", type=Path, default=None, help="default packs/<domain>-v1.json")
    return p


def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="kg", description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    c = _common()

    def add(name: str, help_: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, parents=[c], help=help_)

    add("profile", "census and cost estimate for a domain").add_argument("domain")
    p = add("approve", "record a human approval of the pack (writes the approval file)")
    p.add_argument("domain")
    p.add_argument("--by", required=True, help="the person approving")
    p = add("propose", "propose candidates for one page (live)")
    p.add_argument("page", help="corpus-relative path, e.g. eval/foo.md")
    p = add("build", "build a domain: propose, gate, judge, route, store")
    p.add_argument("domain")
    p.add_argument(
        "--write-record", action="store_true", help="also write report+record on a dry run"
    )
    add("inspect", "show a build's stats and report").add_argument("build_id")
    p = add("review", "show the review queue, or apply a decisions file")
    p.add_argument("build_id")
    p.add_argument("--decisions", type=Path, default=None, help="JSONL of accept/reject decisions")
    p = add("promote", "promote a complete build so default reads serve it")
    p.add_argument("build_id")
    p.add_argument("--waive", action="append", default=[], metavar="PAGE")
    p.add_argument("--reason", default=None)
    add("unpromote", "demote a build and restore the previous promoted one").add_argument(
        "build_id"
    )
    add("verify", "re-check stored quotes against the current corpus").add_argument("build_id")
    p = add("repeat", "run one page n times; Jaccard over canonical keys (live)")
    p.add_argument("page")
    p.add_argument("--n", type=int, default=5)
    p = add("ask", "query the store by entity surface form")
    p.add_argument("entity")
    p.add_argument("--k", type=int, default=1)
    p.add_argument("--build", default=None, help="query this build instead of the promoted one")
    add("label", "label gold triples (passes remaining flags to kg.label)")
    return ap


def _settings(args: argparse.Namespace) -> Settings:
    s = Settings.load()
    if args.corpus_root is not None:
        from dataclasses import replace

        s = replace(s, corpus_root=args.corpus_root.expanduser())
    return s


def _pack_path(args: argparse.Namespace, domain: str) -> Path:
    if args.pack is not None:
        return args.pack
    packs = kb.RUN_DIR / "packs"
    found = sorted(packs.glob(f"{domain}-v*.json"))
    if not found:
        raise RefusedError(f"no pack for domain {domain!r} in {packs}; pass --pack")
    return found[-1]


def _store(args: argparse.Namespace, settings: Settings) -> SqliteStore:
    db = args.db or settings.db_path or kb.DEFAULT_DB_PATH
    db.parent.mkdir(parents=True, exist_ok=True)
    return SqliteStore(db, corpus_root=settings.corpus_root)


def _require_live(command: str) -> None:
    if os.environ.get("KG_LIVE") != "1":
        raise RefusedError(
            f"`kg {command}` spends money; set KG_LIVE=1 after the spend decision "
            "(or pass --dry-run)"
        )


def main(
    argv: Sequence[str] | None = None,
    *,
    proposer: Proposer | None = None,
    seat: JudgeSeat | None = None,
) -> int:
    """Entry point. `proposer` / `seat` inject fakes for tests; the live guard still applies."""
    args, extra = make_parser().parse_known_args(argv)
    if extra and args.command != "label":
        make_parser().error(f"unrecognised arguments: {' '.join(extra)}")
    try:
        return _dispatch(args, extra, proposer, seat)
    except (RefusedError, BuildRefused, NotApproved, ConfigError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED


def _dispatch(
    args: argparse.Namespace, extra: list[str], proposer: Proposer | None, seat: JudgeSeat | None
) -> int:
    cmd = args.command
    if cmd == "label":
        return _label(args, extra)
    settings = _settings(args)
    if cmd == "profile":
        profile = census(settings.require_corpus_root(), args.domain)
        refuse_if_empty(profile)
        est = estimate_cost(
            profile, proposer_model=settings.proposer_model, judge_model=settings.judge_model
        )
        print(
            f"domain {profile.domain}: {profile.page_count} pages "
            f"({profile.empty_count} empty, {profile.split_count} to split), "
            f"{profile.est_tokens} est tokens\nprofile_hash {profile.profile_hash}\n"
            f"estimate {est}"
        )
        return 0
    if cmd == "approve":
        path = _pack_path(args, args.domain)
        h = pack_hash(load_pack(path))
        if args.dry_run:
            print(f"dry run: would approve {path.name} (sha256 {h}) as {args.by}; nothing written")
            return 0
        rec = approve(path, args.by)
        kb.append_decision(
            args.decisions_dir,
            "approvals",
            {
                "kind": "approval",
                "pack": path.name,
                "pack_hash": rec.pack_hash,
                "by": rec.approved_by,
            },
        )
        print(f"approved {path.name} sha256 {rec.pack_hash} by {rec.approved_by}")
        return 0
    if cmd == "build":
        return _build(args, settings, proposer, seat)
    if cmd in ("propose", "repeat"):
        return _model_page(args, settings, proposer)

    # store-backed commands
    store = _store(args, settings)
    if cmd == "inspect":
        stats = store.stats(args.build_id)
        print(json.dumps(stats.model_dump(), indent=2))
        try:
            print(kb.load_report(args.records_dir, args.build_id).render())
        except BuildRefused as exc:
            print(f"(no report: {exc})")
        return 0
    if cmd == "review":
        if args.decisions is None:
            print(render_table(_review_rows(store, args.build_id)))
            return 0
        n = apply_decisions(store, args.build_id, args.decisions)
        for line in args.decisions.read_text(encoding="utf-8").splitlines():
            if line.strip():
                kb.append_decision(
                    args.decisions_dir, args.build_id, {"kind": "review", **json.loads(line)}
                )
        print(
            f"applied {n} decision(s); recorded in {kb.decisions_file(args.decisions_dir, args.build_id)}"
        )
        return 0
    if cmd == "promote":
        waived = kb.promote(
            store,
            args.build_id,
            records_dir=args.records_dir,
            decisions_dir=args.decisions_dir,
            waive=args.waive,
            reason=args.reason,
        )
        print(f"promoted {args.build_id}" + (f" (waived: {', '.join(waived)})" if waived else ""))
        return 0
    if cmd == "unpromote":
        restored = kb.unpromote(store, args.build_id, decisions_dir=args.decisions_dir)
        print(f"unpromoted {args.build_id}; restored {restored or 'nothing (no previous build)'}")
        return 0
    if cmd == "verify":
        v = kb.verify(store, args.build_id, settings.require_corpus_root())
        print(
            f"checked {v.checked} quote(s): {v.fresh} fresh, {len(v.stale)} stale, "
            f"{len(v.missing_pages)} page(s) missing"
        )
        for page, quote in v.stale:
            print(f"  stale: {page}: {quote[:70]!r}")
        for page in v.missing_pages:
            print(f"  missing page: {page}")
        return 0 if not v.stale and not v.missing_pages else 1
    if cmd == "ask":
        hits = store.passages({args.entity}, args.k, build_id=args.build, current_profile_hash=None)
        if not hits:
            print(
                f"nothing for {args.entity!r}"
                + ("" if args.build else " (default reads see promoted builds, accept tier, only)")
            )
            return 0
        for h in hits:
            print(f"[{h.tier} hop{h.hop} {h.freshness}] {h.source_path}: {h.text}")
        return 0
    raise AssertionError(cmd)


def _review_rows(store: SqliteStore, build_id: str):
    from kg.route.review_queue import review_rows

    return review_rows(store, build_id)


def _label(args: argparse.Namespace, extra: list[str]) -> int:
    from kg import label

    extra = list(extra)
    if "--corpus-root" not in extra:
        extra += ["--corpus-root", str(_settings(args).corpus_root)]
    if "--out" not in extra:
        extra += ["--out", str(kb.RUN_DIR / "evals" / "gold" / "eval-v1.jsonl")]
    if args.dry_run:
        print(f"dry run: would run `kg.label {' '.join(extra)}`")
        return 0
    return label.main(extra)


def _build(
    args: argparse.Namespace, settings: Settings, proposer: Proposer | None, seat: JudgeSeat | None
) -> int:
    settings.require_corpus_root()
    pack_path = _pack_path(args, args.domain)
    pack = load_pack(pack_path)
    records = args.records_dir if (not args.dry_run or args.write_record) else None
    if args.dry_run:
        report = asyncio.run(
            kb.abuild(
                args.domain,
                settings,
                proposer or _NoModel(),  # type: ignore[arg-type]
                seat or _NoModel(),  # type: ignore[arg-type]
                None,
                pack=pack,
                pack_path=pack_path,
                dry_run=True,
                records_dir=records,
            )
        )
        print(report.render())
        return 0
    _require_live("build")
    try:
        require_approved(pack, pack_path)
    except NotApproved as exc:
        raise NotApproved(f"{exc} (pack not approved; only --dry-run is allowed)") from exc
    proposer, seat = _live_models(settings, proposer, seat)
    store = _store(args, settings)
    report = asyncio.run(
        kb.abuild(
            args.domain,
            settings,
            proposer,
            seat,
            store,
            pack=pack,
            pack_path=pack_path,
            dry_run=False,
            records_dir=records,
        )
    )
    print(report.render())
    return EXIT_HALTED if report.status == "halted" else 0


def _live_models(
    settings: Settings, proposer: Proposer | None, seat: JudgeSeat | None
) -> tuple[Proposer, JudgeSeat]:
    if proposer is None:
        from kg.propose.anthropic import AnthropicProposer

        proposer = AnthropicProposer(settings)
    if seat is None:
        from kg.judge.claude import ClaudeSeat

        seat = ClaudeSeat(settings)
    return proposer, seat


class _NoModel:
    """Stands in for a proposer or seat on a dry run; any call is a bug."""

    name = "dry-run"
    last_usage = None

    def available(self) -> tuple[bool, str]:
        return True, ""

    async def propose(self, *a: object, **k: object) -> object:
        raise AssertionError("a dry run must not call a model")

    judge = propose


def _model_page(args: argparse.Namespace, settings: Settings, proposer: Proposer | None) -> int:
    domain = args.page.split("/", 1)[0]
    pack_path = _pack_path(args, domain)
    pack = load_pack(pack_path)
    root = settings.require_corpus_root()
    page = next((p for p in iter_pages(root, domain) if p.path == args.page), None)
    if page is None:
        raise RefusedError(f"page {args.page!r} not found under {root / domain}")
    n = getattr(args, "n", 1)
    if args.dry_run:
        print(f"dry run: would call the proposer {n}x on {page.path} ({len(page.body)} chars)")
        return 0
    _require_live(args.command)
    require_approved(pack, pack_path)
    proposer, _ = _live_models(settings, proposer, None)
    if args.command == "repeat":
        j = asyncio.run(kb.repeat(page, pack, proposer, args.n))
        print(
            f"jaccard over canonical keys, n={args.n}: "
            + (f"n/a ({j.reason})" if isinstance(j, NotApplicable) else f"{j:.3f}")
        )
        return 0
    result = asyncio.run(proposer.propose(page, pack))
    print(f"{result.page_path}: {result.status}" + (f" ({result.reason})" if result.reason else ""))
    for c in result.candidates:
        print(f"  {c.subject} --{c.relation}--> {c.object}: {c.quote[:70]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
