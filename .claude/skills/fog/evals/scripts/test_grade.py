#!/usr/bin/env python3
"""Self-test for grade.py — every check must FAIL on a bad run, not just pass on a good one.

An eval grader that only ever returns PASS is the failure mode the fog fixture itself
exists to catch. Each case below pairs a positive (correct output must pass) with a
negative (output that genuinely violates the invariant must fail).

Run: python3 scripts/test_grade.py
"""
import importlib.util
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("grade", HERE / "grade.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

FAILURES = []


def check(name, actual, expected):
    if actual != expected:
        FAILURES.append(f"{name}: expected {expected}, got {actual}")
    print(f"  {'ok  ' if actual == expected else 'FAIL'} {name}")


def planted(text, **kw):
    return g.grade_planted(text, g.split_claims(text), **kw)


def empty(text, **kw):
    return g.grade_empty(text, g.split_claims(text), **kw)


# --- P4: basis grounding, block scalar vs inline vs hand-waving ------------------
print("P4 — basis grounding")
BLOCK_SCALAR = """
id: FOG-001
claim:
  title: A failed category and an empty category return the same value
  statement: >
    The caller cannot tell them apart.
  basis: >
    SPEC.md §2.1 code block: `except Exception: continue`, with no logging and no
    partial-failure flag on the return value.
confidence: likely
decision_impact: fatal
"""
check("block-scalar basis is grounded", planted(BLOCK_SCALAR)["P4"][0], True)

INLINE = BLOCK_SCALAR.replace(
    "  basis: >\n    SPEC.md §2.1 code block: `except Exception: continue`, with no logging and no\n    partial-failure flag on the return value.\n",
    "  basis: SPEC.md §2.1 `except Exception: continue`\n",
)
check("inline basis is grounded", planted(INLINE)["P4"][0], True)

HANDWAVE = BLOCK_SCALAR.replace(
    "    SPEC.md §2.1 code block: `except Exception: continue`, with no logging and no\n    partial-failure flag on the return value.",
    "    This seems like it could be a problem in general and is worth thinking about.",
)
check("hand-waving basis FAILS", planted(HANDWAVE)["P4"][0], False)

NO_BASIS = BLOCK_SCALAR.replace("  basis: >\n", "  notes: >\n")
check("missing basis FAILS", planted(NO_BASIS)["P4"][0], False)
check("no claims at all FAILS", planted("nothing here")["P4"][0], False)

# --- P1: N1 typed abstention (§2.4) ---------------------------------------------
print("\nP1 — N1 typed abstention negative control")
N1_VIOLATION = """
id: FOG-001
claim:
  title: The summarize abstention is a collapse site
  statement: >
    §2.4 returns "summary unavailable" as prose, so a failed call is indistinguishable
    from a genuinely missing abstract and the caller silently drops it.
  basis: >
    SPEC.md §2.4
confidence: likely
decision_impact: costly
"""
check("claim asserting §2.4 collapses FAILS", planted(N1_VIOLATION)["P1"][0], False)

N1_CREDITED = """
id: FOG-001
claim:
  title: Two chained model calls decide relevance with no check between them
  statement: >
    `match_topics` and `rank_by_relevance` are chained probabilistic steps. §2.4's typed
    `Unavailable` arm shows the design already knows how to type an abstention — it is
    the correct counter-example, and these two steps do not follow it.
  basis: >
    SPEC.md §2.2, §2.3
confidence: likely
decision_impact: costly
"""
check("crediting §2.4 as handled passes", planted(N1_CREDITED)["P1"][0], True)

N1_INCIDENTAL = """
id: FOG-001
claim:
  title: Total fetch failure is indistinguishable from a quiet week
  statement: >
    `fetch_new_papers` swallows every exception, so a collapse in §2.1 propagates through
    match_topics, rank_by_relevance and summarize without any signal.
  basis: >
    SPEC.md §2.1
confidence: certain
decision_impact: fatal
"""
check("incidental 'summarize' mention passes", planted(N1_INCIDENTAL)["P1"][0], True)

# The real runs write every schema key as a block scalar, so a `statement:` body that
# does not stop at the next sibling key swallows basis/if_wrong/check. Both fields below
# carry control-trigger words the *statement* never uses — the whole point of reading the
# thesis only. This is the shape that produced two false P1 failures on real runs.
N1_FULL_SCHEMA = """
id: FOG-003
claim:
  title: The design types abstention once and does not apply it where it matters more
  statement: >
    §2.4 correctly types uncertainty as `Ok(text) | Unavailable(reason)`. The two
    ranking steps upstream of it do not, so the one place the pattern is applied is
    the place it was least needed.
  basis: >
    SPEC.md §2.4 against §2.2 — the typed `Unavailable` arm exists only for summarize.
  if_wrong: >
    If the ranking steps do carry a comparable signal, the collapse site is not there
    and the two failures are indistinguishable for a benign reason.
  if_wrong_note: >
    A reviewer who reads §2.4 as the collapse site has matched the word "unavailable"
    rather than the mechanism, and would silently drop the real finding.
  check: read §2.2 and §2.3 for a typed abstention arm
confidence: likely
decision_impact: costly
"""
check(
    "control words in if_wrong/basis do not flag P1",
    planted(N1_FULL_SCHEMA)["P1"][0],
    True,
)
check(
    "thesis stops at the next sibling key",
    "if_wrong" not in g.claim_thesis(g.split_claims(N1_FULL_SCHEMA)["FOG-003"]),
    True,
)
check(
    "full-schema claim still reads its own basis",
    planted(N1_FULL_SCHEMA)["P4"][0],
    True,
)

N1_FULL_VIOLATION = N1_FULL_SCHEMA.replace(
    "    §2.4 correctly types uncertainty as `Ok(text) | Unavailable(reason)`. The two\n"
    "    ranking steps upstream of it do not, so the one place the pattern is applied is\n"
    "    the place it was least needed.",
    "    §2.4 returns \"summary unavailable\" as prose, so a failed call is\n"
    "    indistinguishable from a genuinely missing abstract.",
)
check(
    "same schema, violating statement, still FAILS",
    planted(N1_FULL_VIOLATION)["P1"][0],
    False,
)

# --- P3: N3 deterministic cap (§2.5) --------------------------------------------
print("\nP3 — N3 deterministic cap negative control")
N3_VIOLATION = """
id: FOG-001
claim:
  title: The character cap is a probabilistic step that should be deterministic
  statement: >
    §2.5 asks the model to be brief rather than counting characters in code. The 900
    character cap should be deterministic.
  basis: >
    SPEC.md §2.5
confidence: likely
decision_impact: costly
"""
check("claim inverting §2.5 FAILS", planted(N3_VIOLATION)["P3"][0], False)

N3_COUNTEREXAMPLE = """
id: FOG-001
claim:
  title: Two chained model calls sit on top of the deterministic substrate
  statement: >
    §2.5 shows the design already holds the deterministic-where-possible rule: the 900
    character cap is counted in code, explicitly. §2.2 and §2.3 do not follow it.
  basis: >
    SPEC.md §2.2 against §2.5
confidence: likely
decision_impact: costly
"""
check("citing §2.5 as counter-example passes", planted(N3_COUNTEREXAMPLE)["P3"][0], True)

# --- E3: clean-pass language on the empty target ---------------------------------
print("\nE3 — clean-pass language")
check(
    "plain negation passes",
    empty("This is an error, not a clean pass. Stopping.")["E3"][0],
    True,
)
check(
    "negation split by newline passes",
    empty("This is an error, not a clean\npass. Stopping.")["E3"][0],
    True,
)
check(
    "negation split by markdown emphasis passes",
    empty("An empty target is an **error, not a clean pass.** Stopping.")["E3"][0],
    True,
)
check(
    "counterfactual passes",
    empty("Reporting a clean pass here would be the exact defect this skill finds.")["E3"][0],
    True,
)
check(
    "genuine clean pass FAILS",
    empty("Reviewed the target. No findings found; this is a clean pass.")["E3"][0],
    False,
)
check(
    "genuine all-clear FAILS",
    empty("Nothing of concern in this design.")["E3"][0],
    False,
)
check(
    "'looks good' FAILS",
    empty("The design looks good to me.")["E3"][0],
    False,
)

# --- S5 / E7: report-only filesystem check ---------------------------------------
print("\nS5 / E7 — report-only")
check("no --workspace is UNCHECKED, not PASS", planted(BLOCK_SCALAR)["S5"][0], None)

pristine = g.EVALS / "fixtures" / "finds-planted-defects" / "input"
with tempfile.TemporaryDirectory() as td:
    ws = Path(td)
    for src in pristine.rglob("*"):
        if src.is_file():
            dst = ws / src.relative_to(pristine)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
    (ws / "output.md").write_text("report")
    check("pristine workspace + output.md passes", planted(BLOCK_SCALAR, workspace=str(ws), allow={"output.md"})["S5"][0], True)

    (ws / "notes.txt").write_text("stray")
    check("stray created file FAILS", planted(BLOCK_SCALAR, workspace=str(ws), allow={"output.md"})["S5"][0], False)
    (ws / "notes.txt").unlink()

    target = ws / "SPEC.md"
    original = target.read_bytes()
    target.write_bytes(original + b"\nedited by the run\n")
    check("modified fixture FAILS", planted(BLOCK_SCALAR, workspace=str(ws), allow={"output.md"})["S5"][0], False)
    target.write_bytes(original)

    target.unlink()
    check("deleted fixture FAILS", planted(BLOCK_SCALAR, workspace=str(ws), allow={"output.md"})["S5"][0], False)

check("missing workspace dir FAILS", planted(BLOCK_SCALAR, workspace="/nonexistent/xyz")["S5"][0], False)

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S):")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("all grader self-tests passed")
