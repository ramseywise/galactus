#!/usr/bin/env python3
"""Grade a /fog run against the script-checkable invariants.

Usage:
    python3 grade.py --case finds-planted-defects --output run1.md [--json]
    python3 grade.py --case empty-target-is-error --output run1.md

Grades ONLY `check: script` invariants. The `check: judge` ones are printed as a
checklist for the human/LLM grader — they are not scored here.

Recall (R*), precision (P*) and structural (S*) invariants are reported as SEPARATE
rates. Do not average them: a run with perfect recall and zero precision is a failing
run, because a skill that flags everything scores perfect recall by construction.

Claim blocks are parsed per decide-shared/references/claim-schema.md — a block starts at
an `id:` line (FOG-NNN / FA-NNN) and runs to the next one.
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALS = HERE.parent

CLAIM_ID = re.compile(r"^\s*(?:-\s*)?id:\s*((?:FOG|FA)-\d+)", re.M | re.I)
ANY_CLAIM_ID = re.compile(r"\b(?:FOG|FA)-\d+\b", re.I)
FA_ID = re.compile(r"\bFA-\d+\b", re.I)
IMPACT = re.compile(r"decision_impact:\s*(fatal|costly|recoverable|cosmetic)", re.I)
CONFIDENCE = re.compile(r"confidence:\s*(certain|likely|speculative|unknown)", re.I)
# A YAML block scalar body runs until the next key at any indent, NOT merely until the
# next unindented line — every key inside `claim:` is itself indented, so a naive
# `(?:[ \t]+.*\n)+` swallows basis/if_wrong into whatever field came first.
KEY_AHEAD = r"(?![ \t]*(?:-[ \t]*)?[A-Za-z_][\w -]*:(?:[ \t]|$))"
BLOCK_BODY = rf"((?:{KEY_AHEAD}[ \t]+\S.*\n?|[ \t]*\n)+)"


def block_scalar(field):
    """Regex for `field: >` followed by its folded body, or an inline `field: value`."""
    return (
        re.compile(rf"{field}:[ \t]*[>|][-+]?[ \t]*\n{BLOCK_BODY}", re.I),
        re.compile(rf"{field}:[ \t]*(\S.*)", re.I),
    )


# `basis:` is a block scalar in practice, so a capture that stops at the newline reads
# back the literal ">" and scores every schema-conformant claim ungrounded.
BASIS_BLOCK, BASIS_INLINE = block_scalar("basis")
# a grounded basis cites a section, a file, or a named function/step
GROUNDED = re.compile(r"§\s*\d|\bSPEC\.md\b|\.py\b|:\d+|`[^`]+`|\b\w+\(\)", re.I)


def basis_text(block):
    """Return the basis body, whether written as a block scalar or inline."""
    m = BASIS_BLOCK.search(block)
    if m:
        return m.group(1)
    m = BASIS_INLINE.search(block)
    return m.group(1) if m else ""


def split_claims(text):
    """Split output into claim blocks keyed by id."""
    marks = [(m.start(), m.group(1).upper()) for m in CLAIM_ID.finditer(text)]
    if not marks:
        return {}
    blocks = {}
    for i, (pos, cid) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        blocks[cid] = text[pos:end]
    return blocks


def find_claim(blocks, subject, mechanism=None):
    """Return (id, block) for the first claim matching subject (and mechanism)."""
    for cid, block in blocks.items():
        if subject.search(block) and (mechanism is None or mechanism.search(block)):
            return cid, block
    return None, None


TITLE = re.compile(r"title:[ \t]*(.+)", re.I)
STATEMENT_BLOCK, STATEMENT_INLINE = block_scalar("statement")


def claim_thesis(block):
    """Title + statement — what the claim ASSERTS, minus basis/if_wrong/check prose.

    Negative-control checks must read this rather than the whole block. A claim about
    D1 that merely lists `summarize` among the downstream steps, or one that cites the
    §2.5 cap as the design's own correct counter-example, is not a claim against the
    control — and expected.md explicitly permits both. `if_wrong` is likewise excluded:
    it states what would follow if the claim were mistaken, not what the run asserts.
    """
    parts = []
    m = TITLE.search(block)
    if m:
        parts.append(m.group(1))
    m = STATEMENT_BLOCK.search(block) or STATEMENT_INLINE.search(block)
    if m:
        parts.append(m.group(1))
    return "\n".join(parts)


def flags_control(blocks, subject, defect):
    """Ids of claims whose THESIS asserts the negative control is a defect.

    Returns [] when the control is only mentioned, or credited as correctly-handled.
    """
    hits = []
    for cid, block in blocks.items():
        thesis = claim_thesis(block)
        if subject.search(thesis) and defect.search(thesis):
            hits.append(cid)
    return hits


def grade_report_only(workspace, case, allow):
    """S5 / E7 — the run edited nothing in the scratch workspace it was pointed at.

    Compares the workspace against the pristine fixture input. Returns (passed,
    evidence). Without --workspace the invariant is UNCHECKED, not passed: a filesystem
    invariant that silently reports PASS on no evidence is exactly the collapse this
    fixture exists to catch.
    """
    if workspace is None:
        return None, "UNCHECKED — pass --workspace <scratch dir> to score this"

    ws = Path(workspace)
    if not ws.is_dir():
        return False, f"workspace not found: {ws}"

    pristine = EVALS / "fixtures" / case / "input"
    problems = []

    for src in sorted(p for p in pristine.rglob("*") if p.is_file()):
        rel = src.relative_to(pristine)
        got = ws / rel
        if not got.is_file():
            problems.append(f"{rel} deleted")
        elif got.read_bytes() != src.read_bytes():
            problems.append(f"{rel} modified ({src.stat().st_size} -> {got.stat().st_size} bytes)")

    expected = {p.relative_to(pristine).as_posix() for p in pristine.rglob("*") if p.is_file()}
    for got in sorted(p for p in ws.rglob("*") if p.is_file()):
        rel = got.relative_to(ws).as_posix()
        if rel not in expected and rel not in allow:
            problems.append(f"{rel} created")

    if problems:
        return False, "; ".join(problems)
    return True, f"{len(expected)} fixture file(s) byte-identical; no unexpected files"


def grade_planted(text, blocks, workspace=None, allow=()):
    res = {}

    mig = re.compile(r"topics_freetext|§\s*3\b|migration|backfill", re.I)
    irrev = re.compile(r"irreversib|reversib|unstaged|cannot be undone|no way back", re.I)
    cid, block = find_claim(blocks, mig, irrev)
    res["R3"] = (cid is not None, f"matched claim {cid}" if cid else "no claim ties the migration to irreversibility")

    if block:
        m = IMPACT.search(block)
        impact = m.group(1).lower() if m else None
        res["R4"] = (impact == "fatal", f"{cid} decision_impact={impact or 'absent'}")
    else:
        res["R4"] = (False, "R3 unmatched — no claim to rank")

    # --- precision: negative controls must NOT be flagged ---
    # N1: the typed `Ok | Unavailable` abstention (§2.4). Fails only if a claim asserts
    # THAT mechanism is a collapse site — per expected.md, "reporting it means the run
    # matched on the word 'unavailable' rather than on the mechanism."
    n1 = re.compile(r"summary unavailable|Unavailable\b|§\s*2\.4|typed abstention", re.I)
    n1_bad = re.compile(
        r"collapse site|collapses|indistinguishable|swallow|silently (?:drop|discard|lost)",
        re.I,
    )
    hits = flags_control(blocks, n1, n1_bad)
    res["P1"] = (not hits, "clean" if not hits else f"flags the typed abstention: {', '.join(hits)}")

    # N3: the 900-char cap (§2.5) is already deterministic. Fails only if a claim
    # asserts it is probabilistic / should be made deterministic. Citing it as the
    # design's own correct counter-example is allowed and must not fail this.
    n3 = re.compile(r"900|character cap|char cap|render_email|§\s*2\.5", re.I)
    n3_bad = re.compile(
        r"(?:should|must|ought to) (?:be|become) determinis|"
        r"should not be a model call|is (?:a )?probabilistic|"
        r"asks? the model to (?:be brief|count)",
        re.I,
    )
    hits = flags_control(blocks, n3, n3_bad)
    res["P3"] = (not hits, "clean" if not hits else f"flags the deterministic cap: {', '.join(hits)}")

    # --- P4: every claim's basis is grounded ---
    ungrounded = [c for c, b in blocks.items() if not GROUNDED.search(basis_text(b))]
    res["P4"] = (
        bool(blocks) and not ungrounded,
        "all grounded" if blocks and not ungrounded
        else "no claim blocks parsed" if not blocks
        else f"ungrounded basis: {', '.join(ungrounded)}",
    )

    # --- P5: not uniformly speculative ---
    confs = [m.group(1).lower() for m in CONFIDENCE.finditer(text)]
    res["P5"] = (
        bool(confs) and not all(c == "speculative" for c in confs),
        f"confidences={confs or 'none found'}",
    )

    # --- structural ---
    res["S2"] = (bool(FA_ID.search(text)), "FA ids present" if FA_ID.search(text) else "no FA-NNN ids — advisor findings renumbered or dispatch missing")

    fog_line = re.compile(r"the fog\b", re.I).search(text)
    fix_first = re.compile(r"fix first|one to fix", re.I).search(text)
    blind = re.compile(r"could not see|couldn't see|blind spot", re.I).search(text)
    missing = [n for n, v in [("the-fog", fog_line), ("fix-first", fix_first), ("blind-spots", blind)] if not v]
    res["S3"] = (not missing, "all three present" if not missing else f"missing: {', '.join(missing)}")

    res["S5"] = grade_report_only(workspace, "finds-planted-defects", allow)

    return res


def grade_empty(text, blocks, workspace=None, allow=()):
    res = {}
    err = re.compile(r"empty|unreadable|nothing to (read|interrogate)|no content", re.I)
    res["E1"] = (bool(err.search(text)), "error stated" if err.search(text) else "no empty/unreadable error")
    ids = ANY_CLAIM_ID.findall(text)
    res["E2"] = (not ids, "no claims" if not ids else f"claims emitted: {sorted(set(i.upper() for i in ids))}")
    # Negated forms ("this is an error, NOT a clean pass") are correct output, not a
    # violation — strip them before matching, or the check false-positives on the very
    # phrasing a good run uses to disclaim the verdict. Two shapes defeated the naive
    # scrubber, both seen in real runs:
    #   1. The phrase split across a line break or markdown emphasis ("not a **clean\n
    #      pass**") — `negated` spans it via \s+ but the literal in `clean` cannot.
    #      Normalize whitespace and strip emphasis before matching.
    #   2. The counterfactual ("reporting a clean pass here WOULD BE the exact defect")
    #      — a statement of what the run refuses to do, not a verdict.
    flat = re.sub(r"\s+", " ", re.sub(r"[*_`]", "", text))
    counterfactual = re.compile(
        r"\b(?:report(?:ing|ed)?|emit(?:ting)?|return(?:ing)?|issu(?:e|ing)|declar(?:e|ing))\s+"
        r"(?:an?\s+)?(?:clean pass|all-clear)[^.]*?\bwould\b[^.]*\.",
        re.I,
    )
    negated = re.compile(r"\b(?:not|never|isn't|is not|rather than|instead of)\s+(?:an?\s+)?(?:clean pass|all-clear|empty review)", re.I)
    scrubbed = negated.sub(" ", counterfactual.sub(" ", flat))
    clean = re.compile(r"no (collapse sites|findings|issues) found|clean pass|looks good|nothing of concern", re.I)
    hit = clean.search(scrubbed)
    res["E3"] = (not hit, "no clean-pass language" if not hit else f"clean-pass phrasing: {hit.group(0)!r}")
    res["E4"] = (not FA_ID.search(text), "no advisor dispatch" if not FA_ID.search(text) else "FA ids present — advisor was dispatched over an empty target")
    res["E7"] = grade_report_only(workspace, "empty-target-is-error", allow)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, choices=["finds-planted-defects", "empty-target-is-error"])
    ap.add_argument("--output", required=True, help="file holding the /fog run output")
    ap.add_argument(
        "--workspace",
        help="scratch dir the run was pointed at. Required to score the report-only "
        "invariant (S5 / E7); without it that invariant reports UNCHECKED.",
    )
    ap.add_argument(
        "--allow",
        default="output.md",
        help="comma-separated files the run may create in the workspace (default: output.md)",
    )
    ap.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = ap.parse_args()

    text = Path(args.output).read_text()
    blocks = split_claims(text)
    allow = {a.strip() for a in args.allow.split(",") if a.strip()}

    spec = json.loads((EVALS / "assertions" / f"{args.case}.json").read_text())
    by_id = {i["id"]: i for i in spec["invariants"]}

    grader = grade_planted if args.case == "finds-planted-defects" else grade_empty
    results = grader(text, blocks, workspace=args.workspace, allow=allow)

    if args.json:
        print(json.dumps({k: {"passed": v[0], "evidence": v[1], "text": by_id[k]["text"]} for k, v in results.items()}, indent=2))
        return 0

    print(f"case: {args.case}   claim blocks parsed: {len(blocks)}\n")
    groups = {}
    for k, (passed, ev) in sorted(results.items()):
        mark = "SKIP" if passed is None else "PASS" if passed else "FAIL"
        print(f"  [{mark}] {k}  {by_id[k]['text']}")
        print(f"         {ev}")
        if passed is not None:
            groups.setdefault(k[0], []).append(passed)

    unchecked = [k for k, v in results.items() if v[0] is None]

    print("\n  rates (do NOT average across groups):")
    label = {"R": "recall", "P": "precision", "S": "structural", "E": "error-path"}
    for g, vals in sorted(groups.items()):
        print(f"    {label.get(g, g):11s} {sum(vals)}/{len(vals)}")
    if unchecked:
        print(f"    UNCHECKED (not counted above): {', '.join(sorted(unchecked))}")

    judge = [i for i in spec["invariants"] if i["check"] == "judge"]
    if judge:
        print("\n  judge invariants — not scored here, grade manually:")
        for i in judge:
            print(f"    - {i['id']}: {i['text']}")

    print("\n  NOTE: scripted subset only. Perfect recall with failing precision is a FAILING run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
