#!/usr/bin/env python3
"""Self-test for bin/study_report.py — run it; do not reason about it.

Tests the TOOL's arithmetic against known-by-hand inputs, not the real-world
hypothesis ADR 0012 asks about — that needs real usage data, which is the
whole point of the tool existing.
"""

from __future__ import annotations

import os
import sys
import tempfile
from typing import cast

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skills", "grit"))
import study_report as SR  # noqa: E402
import score as S  # noqa: E402


def ev(
    concept: str,
    source: str,
    assistance: str,
    at: str,
    failed: bool = False,
    task: str = "t",
) -> S.EvidenceRow:
    return S.EvidenceRow(
        at=at,
        concept=concept,
        source=cast(S.Source, source),
        assistance=cast(S.Assistance, assistance),
        task=task,
        failed=failed,
        project="/p",
    )


def _check_q1_predicts_from_prior_events_only() -> None:
    # c1: one unaided pass, no history -> predicted "unproven" (score_concept([])).
    # c2: one unaided fail, no history -> predicted "unproven" too.
    # c3: two unaided passes -> the SECOND is predicted from the first (a real
    # 0.5 score), landing in "recall". The first is still "unproven": nothing
    # precedes it, and it must not see its own outcome or c1/c2's events.
    rows = [
        ev("c1", "repo", "none", "2026-01-01T00:00:00+00:00", failed=False),
        ev("c2", "repo", "none", "2026-01-01T00:00:00+00:00", failed=True),
        ev("c3", "repo", "none", "2026-01-01T00:00:00+00:00", failed=False, task="a"),
        ev("c3", "repo", "none", "2026-01-02T00:00:00+00:00", failed=False, task="b"),
    ]
    out = SR.q1_predicted_vs_actual(rows)
    assert out["unproven"] == {"pass": 2, "fail": 1}, out
    assert out["recall"] == {"pass": 1, "fail": 0}, out
    assert "proven" not in out, out


def _check_q1_ignores_assisted_and_sandbox_events() -> None:
    # Only source=repo, assistance=none events are predictions to score. An
    # AI-written or sandbox event is real evidence for the LEVEL but is not
    # itself the kind of outcome Q1 is correlating against.
    rows = [
        ev("c", "repo", "full", "2026-01-01T00:00:00+00:00"),
        ev("c", "sandbox", "none", "2026-01-01T00:00:00+00:00"),
        ev("c", "repo", "partial", "2026-01-01T00:00:00+00:00"),
    ]
    assert SR.q1_predicted_vs_actual(rows) == {}, SR.q1_predicted_vs_actual(rows)


def _check_q2_splits_by_total_event_count_per_concept() -> None:
    # "busy" has FREQUENT_AT events total; "quiet" has one. Every event is a
    # distinct-task unaided repo pass, so as "busy" accumulates evidence its
    # own later events predict higher levels than its first (score climbs)
    # — the split is about which CONCEPT an event belongs to, not what level
    # it lands in, so what must hold is the total count per bucket, not the
    # per-level breakdown.
    busy = [
        ev("busy", "repo", "none", "2026-01-0%dT00:00:00+00:00" % (i + 1), task=str(i))
        for i in range(SR.FREQUENT_AT)
    ]
    quiet = [ev("quiet", "repo", "none", "2026-01-01T00:00:00+00:00")]
    frequent, rare = SR.q2_frequent_vs_rare(busy + quiet)

    def total(bucket: SR.Bucket) -> int:
        return sum(v["pass"] + v["fail"] for v in bucket.values())

    assert total(frequent) == SR.FREQUENT_AT, frequent
    assert total(rare) == 1, rare
    assert rare.get("unproven") == {"pass": 1, "fail": 0}, rare


def _check_q2b_compares_partial_against_none_by_assistance() -> None:
    rows = [
        ev("c", "repo", "none", "2026-01-01T00:00:00+00:00", failed=False),
        ev("c", "repo", "none", "2026-01-01T00:00:00+00:00", failed=True),
        ev("c", "sandbox", "partial", "2026-01-01T00:00:00+00:00", failed=True),
        ev("c", "repo", "full", "2026-01-01T00:00:00+00:00", failed=True),
    ]
    out = SR.q2b_partial_vs_none(rows)
    assert out["none"] == {"pass": 1, "fail": 1}, out
    assert out["partial"] == {"pass": 0, "fail": 1}, out
    assert "full" not in out, out


def _check_main_handles_an_empty_root_without_crashing() -> None:
    with tempfile.TemporaryDirectory() as root:
        assert SR.main(["study_report.py", "--root", root]) == 0


def main() -> int:
    _check_q1_predicts_from_prior_events_only()
    _check_q1_ignores_assisted_and_sandbox_events()
    _check_q2_splits_by_total_event_count_per_concept()
    _check_q2b_compares_partial_against_none_by_assistance()
    _check_main_handles_an_empty_root_without_crashing()
    print("ok — 5 study_report properties hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
