"""Census of one corpus domain, its stable hash, and the cost estimate that gates a build.

A build is refused before any spend when the domain is empty (a mistyped domain must not
cost $0 and pass, fog FA-002) or when the estimate exceeds the build ceiling. The estimate
is an estimate, not a meter: its basis string names every assumption, including the
survival rate, so a reader can see what it would take for the number to be wrong.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from kg.profile.normalise import NORMALISATION_RULE_HASH, normalise
from kg.profile.prices_table import PRICES, SOURCE_DATE, ModelPrice

SPLIT_TOKENS = 6000
"""Pages above this estimated size are split on headings before proposing."""

# Estimate assumptions. Each is printed in the basis string.
PROPOSER_OVERHEAD_TOKENS = 1500  # instructions + pack, per proposer call
PROPOSER_OUTPUT_TOKENS = 800  # candidate JSON, per proposer call
REPAIR_RETRY_RATE = 0.2  # share of proposer calls that need the one repair retry
CANDIDATES_PER_CALL = 10
SURVIVAL_RATE = 0.75  # share of candidates that pass the four gates and reach the judge
JUDGE_INPUT_TOKENS = 1200  # judge prompt + evidence window, per survivor
JUDGE_OUTPUT_TOKENS = 300


class BuildRefused(RuntimeError):  # noqa: N818 — name fixed by the plan
    """The build was refused before any spend."""


@dataclass(frozen=True)
class Page:
    path: str  # posix, relative to the corpus root, e.g. "eval/foo.md"
    body: str  # normalised


@dataclass(frozen=True)
class PageProfile:
    path: str
    bytes: int
    est_tokens: int
    split: bool
    body_sha256: str

    @property
    def calls(self) -> int:
        """Proposer calls this page costs: one per split chunk, at least one."""
        return max(1, math.ceil(self.est_tokens / SPLIT_TOKENS))


@dataclass(frozen=True)
class Profile:
    domain: str
    pages: tuple[PageProfile, ...]
    normalisation_rule_hash: str
    profile_hash: str

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def est_tokens(self) -> int:
        return sum(p.est_tokens for p in self.pages)

    @property
    def split_count(self) -> int:
        return sum(p.split for p in self.pages)

    @property
    def empty_count(self) -> int:
        return sum(p.est_tokens == 0 for p in self.pages)


@dataclass(frozen=True)
class Estimate:
    usd: float
    basis: str

    def __str__(self) -> str:
        return f"${self.usd:.2f} ({self.basis})"


def _domain_files(corpus_root: Path, domain: str) -> list[Path]:
    domain_dir = corpus_root / domain
    if not domain_dir.is_dir():
        return []
    return sorted(
        p
        for p in domain_dir.glob("*.md")
        if p.is_file()
        and not p.name.startswith("_")
        # Relative parts only: on macOS the absolute path itself starts with /private.
        and "private" not in p.relative_to(corpus_root).parts
    )


def iter_pages(corpus_root: Path, domain: str) -> Iterator[Page]:
    for f in _domain_files(corpus_root, domain):
        yield Page(
            path=f.relative_to(corpus_root).as_posix(),
            body=normalise(f.read_text(encoding="utf-8")),
        )


def census(corpus_root: Path, domain: str) -> Profile:
    pages: list[PageProfile] = []
    for f in _domain_files(corpus_root, domain):
        raw = f.read_bytes()
        body = normalise(raw.decode("utf-8"))
        est = math.ceil(len(body) / 4)
        pages.append(
            PageProfile(
                path=f.relative_to(corpus_root).as_posix(),
                bytes=len(raw),
                est_tokens=est,
                split=est > SPLIT_TOKENS,
                body_sha256=hashlib.sha256(raw).hexdigest(),
            )
        )
    h = hashlib.sha256(NORMALISATION_RULE_HASH.encode())
    for p in sorted(pages, key=lambda p: p.path):
        h.update(f"\n{p.path}\t{p.body_sha256}".encode())
    return Profile(
        domain=domain,
        pages=tuple(pages),
        normalisation_rule_hash=NORMALISATION_RULE_HASH,
        profile_hash=h.hexdigest(),
    )


def _price(prices: Mapping[str, ModelPrice], model: str) -> ModelPrice:
    try:
        return prices[model]
    except KeyError:
        raise BuildRefused(
            f"no price for model {model!r}; add it to kg/profile/prices_table.py before building"
        ) from None


def estimate_cost(
    profile: Profile,
    prices: Mapping[str, ModelPrice] = PRICES,
    *,
    proposer_model: str = "claude-haiku-5-5",
    judge_model: str = "claude-sonnet-5-5",
) -> Estimate:
    p, j = _price(prices, proposer_model), _price(prices, judge_model)
    calls = sum(pg.calls for pg in profile.pages) * (1 + REPAIR_RETRY_RATE)
    proposer_in = profile.est_tokens * (1 + REPAIR_RETRY_RATE) + calls * PROPOSER_OVERHEAD_TOKENS
    proposer_out = calls * PROPOSER_OUTPUT_TOKENS
    survivors = sum(pg.calls for pg in profile.pages) * CANDIDATES_PER_CALL * SURVIVAL_RATE
    proposer_usd = (proposer_in * p.input_per_mtok + proposer_out * p.output_per_mtok) / 1e6
    judge_usd = (
        survivors
        * (JUDGE_INPUT_TOKENS * j.input_per_mtok + JUDGE_OUTPUT_TOKENS * j.output_per_mtok)
    ) / 1e6
    basis = (
        f"{profile.page_count} pages, {profile.est_tokens} est tokens; "
        f"proposer {proposer_model} ${proposer_usd:.2f}, judge {judge_model} ${judge_usd:.2f}; "
        f"assumes {CANDIDATES_PER_CALL} candidates/call, survival rate {SURVIVAL_RATE:.0%}, "
        f"repair retries {REPAIR_RETRY_RATE:.0%}; prices as of {SOURCE_DATE}"
    )
    return Estimate(usd=round(proposer_usd + judge_usd, 4), basis=basis)


def refuse_if_empty(profile: Profile) -> None:
    if profile.page_count == 0:
        raise BuildRefused(
            f"domain {profile.domain!r} has no pages; check the domain name and KG_CORPUS_ROOT"
        )


def refuse_if_over(estimate: Estimate, ceiling: float) -> None:
    if estimate.usd > ceiling:
        raise BuildRefused(
            f"estimated ${estimate.usd:.2f} exceeds the build ceiling ${ceiling:.2f}: "
            f"{estimate.basis}"
        )
