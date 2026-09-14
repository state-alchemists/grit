#!/usr/bin/env python3
"""bin/study_report.py — retrospective signal for ADR 0012's Q1/Q2/Q2b.

    python3 bin/study_report.py [--root DIR]

ADR 0012 says the validation study is cheap because `evidence.jsonl` already
records concept, source, assistance and date, and "what is missing is a later
unassisted outcome to correlate against." That outcome does not need to be
collected going forward: every unaided repository event already carries one —
its own `failed` flag is the real-work result of the very task the level
existed to predict. So this walks the log in time order and, for each unaided
repo event, asks what the level *would have said* using only the evidence
that came strictly before it — then checks that prediction against what
actually happened.

This does not run the study. Q1/Q2/Q2b need real usage accumulated over time
(and Q3/Q4 need a router and a tutorial-format choice that do not exist yet —
see ADR 0011). This is the instrument, not the result: point it at a real
`~/.grit` after enough work has happened, not at a fixture.

NOT a pass/fail gate — it reports, it does not assert the product works, so
it is not part of AGENTS.md's "run it" test list. Its own correctness is
`bin/test_study_report.py`.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(os.path.dirname(HERE), "skills", "grit")
if SKILL not in sys.path:
    sys.path.insert(0, SKILL)
import score as S  # noqa: E402

FREQUENT_AT = 5  # ADR 0012's own method constraint: "≥5 completed tasks per concept"

Bucket = dict[str, dict[str, int]]  # {level_or_group: {"pass": n, "fail": n}}


def _predicted_level(prior: list[S.EvidenceRow], at_iso: str) -> str:
    """What the level was, using only evidence strictly before `at_iso`.

    `now=at_iso` matters, not just `prior`: staleness decay (ADR: evidence
    older than 90 days counts half) must be judged as of the event being
    predicted, not as of today.
    """
    now = None
    try:
        now = datetime.fromisoformat(at_iso.replace("Z", "+00:00")) if at_iso else None
    except ValueError:
        pass
    return S.score_concept(prior, now).level


def q1_predicted_vs_actual(rows: list[S.EvidenceRow]) -> Bucket:
    """For every unaided repo event, bucket by the level predicted from prior
    evidence of the SAME concept only, and tally its actual pass/fail."""
    by_concept: dict[str, list[S.EvidenceRow]] = defaultdict(list)
    for r in rows:
        by_concept[r.concept].append(r)

    out: Bucket = defaultdict(lambda: {"pass": 0, "fail": 0})
    for events in by_concept.values():
        events = sorted(events, key=lambda e: e.at)
        for i, ev in enumerate(events):
            if ev.source != "repo" or ev.assistance != "none":
                continue
            level = _predicted_level(events[:i], ev.at)
            out[level]["fail" if ev.failed else "pass"] += 1
    return dict(out)


def q2_frequent_vs_rare(rows: list[S.EvidenceRow]) -> tuple[Bucket, Bucket]:
    """Q1's same split, run separately for concepts with >= FREQUENT_AT total
    events (in the whole log) vs. fewer. The risk ADR 0012 names is structural:
    an expert who simply has not done two scoreable tasks recently reads as
    `recall` forever, which would show up here as the frequent set predicting
    worse than the rare set despite (presumably) equal or better real skill.
    """
    totals: dict[str, int] = defaultdict(int)
    for r in rows:
        totals[r.concept] += 1
    frequent = [r for r in rows if totals[r.concept] >= FREQUENT_AT]
    rare = [r for r in rows if totals[r.concept] < FREQUENT_AT]
    return q1_predicted_vs_actual(frequent), q1_predicted_vs_actual(rare)


def q2b_partial_vs_none(rows: list[S.EvidenceRow]) -> Bucket:
    """Does `assistance: partial` carry information `none` doesn't? Compares
    raw pass/fail rate by assistance value — not filtered to source=repo,
    since a tutorial (`sandbox`) can also be recorded as `partial`."""
    out: Bucket = defaultdict(lambda: {"pass": 0, "fail": 0})
    for r in rows:
        if r.assistance not in ("none", "partial"):
            continue
        out[r.assistance]["fail" if r.failed else "pass"] += 1
    return dict(out)


def _rate(bucket: dict[str, int]) -> str:
    n = bucket["pass"] + bucket["fail"]
    if not n:
        return "n=0"
    return "n=%d, fail-rate=%.2f" % (n, bucket["fail"] / n)


def _print_bucket(title: str, b: Bucket) -> None:
    print(title)
    if not b:
        print("  no qualifying events yet")
        return
    for key in sorted(b):
        print("  %-10s %s" % (key, _rate(b[key])))


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=os.environ.get("GRIT_ROOT", "~/.grit"))
    args = p.parse_args(argv[1:])
    root = os.path.expanduser(args.root)

    rows = S.load(root)
    if not rows:
        print("no evidence yet at %s — nothing to report" % root)
        return 0

    print("study_report — ADR 0012, retrospective signal from %d event(s)\n" % len(rows))
    _print_bucket("Q1 — predicted level vs. actual outcome (unaided repo events):", q1_predicted_vs_actual(rows))
    print()
    frequent, rare = q2_frequent_vs_rare(rows)
    _print_bucket("Q2 — same, concepts with >= %d total events:" % FREQUENT_AT, frequent)
    print()
    _print_bucket("Q2 — same, concepts with < %d total events:" % FREQUENT_AT, rare)
    print()
    _print_bucket("Q2b — pass/fail rate by assistance value:", q2b_partial_vs_none(rows))
    print(
        "\nA real read on Q1 needs the higher-predicted buckets to show a "
        "lower fail-rate than the lower ones, at more than a handful of "
        "events per bucket. This is a first look, not a verdict."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
