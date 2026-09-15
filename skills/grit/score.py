#!/usr/bin/env python3
"""grit scoring — turn evidence into a per-concept level.

    python3 score.py record <concept> --source repo|sandbox
                     --assistance none|partial|full --task <id> [--root DIR]
    python3 score.py show [--root DIR]

THE MODEL, AND WHY IT IS SHAPED THIS WAY

A score has to prove something. That rules out XP — a number you add to is a
number you can farm, and a farmed record says whatever its owner wants. So
nothing here accumulates freely. Every event is worth

    credit = source_weight x assistance_factor x novelty

and a concept's score is the capped sum. Three multipliers, three reasons:

  source_weight   Real repository work (0.5) outweighs a sandbox exercise
                  (0.2). Passing a JavaScript exercise about token buckets is
                  not the same as shipping one in your own service, and the
                  numbers should not pretend otherwise.

  assistance      none 1.0 / partial 0.5 / full 0.0. If the assistant wrote it,
                  the concept earns nothing — that is the whole product in one
                  coefficient. `partial` exists so that taking a hint is worth
                  recording honestly rather than hiding.

  novelty         1 / (1 + times you have already produced this same evidence).
                  The second run of one tutorial is worth half the first, the
                  fourth a quarter. Repetition is not learning, and without this
                  the score is farmable by replaying one exercise.

`proven` additionally REQUIRES two distinct unaided repository tasks (see
PROVEN_NEEDS_UNAIDED_TASKS). No amount of sandbox grinding reaches it, and
neither does repeating one real task. That rule is what stops the ladder from
being climbable without doing real work twice.

Failures lower the level, ageing halves the weight, and both are deliberate: a
measurement that can only go up is not a measurement.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Optional, Sequence, cast

# ── Types ────────────────────────────────────────────────────────────────────
# The vocabulary the rest of the product borrows. `Source` and `Assistance` are
# the two inputs that decide what an event is worth; `Level` is what comes out.
# Named here because a typo in a bare string ("repp") would silently score 0.0
# through `.get(..., default)` rather than raise.
Source = Literal["repo", "sandbox"]
Assistance = Literal["none", "partial", "full"]
Level = Literal["unproven", "recall", "proven"]


@dataclass(frozen=True)
class EvidenceRow:
    """One line of evidence.jsonl.

    Frozen because the file is append-only (AGENTS.md §6): the remedy for a
    wrong record is a new measurement, never an edit. A mutable row would make
    the one operation this product forbids the easiest one to write.
    """

    concept: str
    source: Source
    assistance: Assistance
    task: str = ""
    detail: str = ""
    project: str = ""
    failed: bool = False
    at: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EvidenceRow":
        """Tolerate a partial or hand-written row. Unknown `source`/
        `assistance` values fall back to the weakest interpretation rather than
        raising — a corrupt line must not void the whole record."""
        source = raw.get("source")
        assistance = raw.get("assistance")
        return cls(
            concept=str(raw.get("concept", "?")),
            source=cast(Source, source if source in SOURCE_WEIGHT else "sandbox"),
            assistance=cast(
                Assistance, assistance if assistance in ASSISTANCE else "full"
            ),
            task=str(raw.get("task", "")),
            detail=str(raw.get("detail", "")),
            project=str(raw.get("project", "")),
            failed=bool(raw.get("failed")),
            at=str(raw.get("at", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        """The on-disk shape. `failed` is omitted when False so the file stays
        byte-comparable with what earlier versions wrote."""
        row: dict[str, Any] = {
            "at": self.at or _get_timestamp(),
            "concept": self.concept,
            "source": self.source,
            "assistance": self.assistance,
            "task": self.task,
            "detail": self.detail,
            "project": self.project,
        }
        if self.failed:
            row["failed"] = True
        return row


@dataclass
class ConceptScore:
    """The derived verdict for one concept. Never stored — recomputed from
    evidence on every read, so a bug in this arithmetic is fixable by editing
    code rather than by repairing data."""

    score: float
    level: Level
    passes: int
    fails: int
    unaided_repo: bool
    unaided_tasks: int
    projects: int
    blocked_by: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 3),
            "level": self.level,
            "passes": self.passes,
            "fails": self.fails,
            "unaided_repo": self.unaided_repo,
            "unaided_tasks": self.unaided_tasks,
            "projects": self.projects,
            "blocked_by": self.blocked_by,
        }


@dataclass
class Profile:
    """Every concept's standing, plus the headline counts the dashboard reads."""

    concepts: dict[str, ConceptScore] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        proven = sum(1 for c in self.concepts.values() if c.level == "proven")
        recall = sum(1 for c in self.concepts.values() if c.level == "recall")
        return {
            "concepts": {n: c.to_dict() for n, c in self.concepts.items()},
            "headline": {
                "proven": proven,
                "recall": recall,
                "tracked": len(self.concepts),
            },
            "note": self.note,
        }


# The identity of one piece of work, for novelty and the distinct-task count.
TaskKey = tuple[str, str, str]

# Builds a synthetic evidence row for the self-check, so each property can be
# read on one line.
Ev = Callable[..., EvidenceRow]

# Real work counts for more than an exercise. See ADR 0004: a sandbox check is
# a weaker oracle, and the weights are that rule expressed as arithmetic.
# Calibrated so that ONE unaided task is strong evidence but not proof — two
# distinct ones are. A single instance is a data point, not a capability, and
# an early draft that scored 1.0 for one task made `proven` meaningless.
#   1 unaided repo task      0.50  -> recall
#   2 distinct unaided tasks 1.00  -> proven
#   the SAME task twice      0.75  -> still recall (novelty halves the repeat)
#   one tutorial, ground     ~0.40 -> recall ceiling, never proven
SOURCE_WEIGHT: dict[str, float] = {"repo": 0.5, "sandbox": 0.2}

# The core claim of the product, as a number.
ASSISTANCE: dict[str, float] = {"none": 1.0, "partial": 0.5, "full": 0.0}

# A single task or tutorial can never contribute more than this multiple of its
# own weight, however many times it is repeated. `1/(1+n)` alone was not enough:
# it is a harmonic series, so six runs of one tutorial still added 0.49 and
# pushed a concept to `proven`. Repetition has to have a hard ceiling, not a
# slow one.
PER_TASK_CAP = 1.5

# `proven` needs TWO distinct unaided repository tasks. One is a data point that
# a well-ground tutorial can top up past the threshold; two is a pattern.
PROVEN_NEEDS_UNAIDED_TASKS = 2

LEVELS: tuple[str, ...] = ("unproven", "recall", "proven")
RECALL_AT = 0.30
PROVEN_AT = 0.80
STALE_DAYS = 90


def _get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _age_days(stamp: str, now: Optional[datetime] = None) -> int:
    try:
        then = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return ((now or datetime.now(timezone.utc)) - then).days


def get_evidence_path(root: str) -> str:
    return os.path.join(root, "evidence.jsonl")


def load(root: str) -> list[EvidenceRow]:
    path = get_evidence_path(root)
    if not os.path.exists(path):
        return []
    out: list[EvidenceRow] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                out.append(EvidenceRow.from_dict(json.loads(line)))
            except ValueError:
                continue  # one bad line must not void a record
    return out


def compose_task_key(source: str, project: str, task: str) -> TaskKey:
    """The identity of a piece of work, for novelty and for the distinct-task count.

    Repository tasks are scoped by project: task ids are per-project sequences,
    so `001` in two different repos is two different tasks. Without the project
    they collided, and two genuine unaided tasks scored as one repeated one —
    0.75/recall instead of 1.00/proven, silently penalising anyone who works
    across more than one codebase.

    Tutorials are deliberately NOT scoped. They live in one place per person, so
    the same exercise is the same exercise wherever you happen to run it, and
    repeating it must decay no matter which repo you are sitting in.
    """
    if source == "repo":
        return (source, project or "", task or "")
    return (source, "", task or "")


def get_known_concepts(root: str) -> list[str]:
    return sorted({e.concept for e in load(root) if e.concept})


def get_near_duplicates(root: str, concept: str, cutoff: float = 0.82) -> list[str]:
    """Existing concept names close enough to `concept` to be the same idea.

    Fragmentation is the silent failure of this model: `token-bucket`,
    `token_bucket` and `token-buckets` split one concept's evidence three ways,
    so the work is done three times and nothing ever reaches `proven`. Nobody
    notices, because each name looks reasonable on its own.

    A warning, never a block — the user owns their concept names, and two
    similar names are sometimes genuinely two things.
    """
    existing = get_known_concepts(root)
    if concept in existing:
        return []
    norm: Callable[[str], str] = (
        lambda x: x.lower().replace("_", "-").replace(" ", "-").rstrip("s")
    )
    hits = [c for c in existing if norm(c) == norm(concept)]
    hits += [
        c
        for c in difflib.get_close_matches(concept, existing, n=3, cutoff=cutoff)
        if c not in hits
    ]
    return hits


def record(
    root: str,
    concept: str,
    source: str,
    assistance: str,
    task: str,
    detail: str = "",
    project: str = "",
    failed: bool = False,
) -> EvidenceRow:
    if source not in SOURCE_WEIGHT:
        raise ValueError("source must be one of %s" % list(SOURCE_WEIGHT))
    if assistance not in ASSISTANCE:
        raise ValueError("assistance must be one of %s" % list(ASSISTANCE))
    row = EvidenceRow(
        at=_get_timestamp(),
        concept=concept,
        source=cast(Source, source),  # validated above
        assistance=cast(Assistance, assistance),  # validated above
        task=task,
        detail=detail,
        project=os.path.abspath(project) if project else "",
        # Before the write, not on the returned dict: the file is the record,
        # and a failure that misses it scores as a pass.
        failed=failed,
    )
    os.makedirs(root, exist_ok=True)
    with open(get_evidence_path(root), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row.to_dict()) + "\n")
    return row


@dataclass
class _Tally:
    """Running state while folding events into a score. Mutable scratch, not
    part of the result — `ConceptScore` is what comes out."""

    total: float = 0.0
    passes: int = 0
    fails: int = 0
    seen: dict[TaskKey, int] = field(default_factory=dict)
    given: dict[TaskKey, float] = field(default_factory=dict)
    unaided_tasks: set[TaskKey] = field(default_factory=set)
    projects: set[str] = field(default_factory=set)


def score_concept(
    events: Sequence[EvidenceRow], now: Optional[datetime] = None
) -> ConceptScore:
    """Score one concept's events. Pure: no clock, no disk, no globals."""
    t = _Tally()
    for ev in sorted(events, key=lambda e: e.at):
        _fold_event(t, ev, now)
    return _tally_to_score(t)


def _fold_event(t: _Tally, ev: EvidenceRow, now: Optional[datetime]) -> None:
    """Add one event's contribution to the tally."""
    if ev.failed:
        # A measured failure is evidence too, and it points down. Without this
        # the score only ever rises, which is what a vanity metric is.
        t.fails += 1
        t.total = max(0.0, t.total - 0.25)
        return
    t.passes += 1
    if ev.project:
        t.projects.add(ev.project)
    key = compose_task_key(ev.source, ev.project, ev.task)
    t.total += _credit_for(t, ev, key, now)
    if ev.source == "repo" and ev.assistance == "none":
        t.unaided_tasks.add(key)


def _credit_for(
    t: _Tally, ev: EvidenceRow, key: TaskKey, now: Optional[datetime]
) -> float:
    """One event's credit: weight x assistance x novelty, then the stale
    penalty, then the per-task ceiling."""
    novelty = 1.0 / (1.0 + t.seen.get(key, 0))
    t.seen[key] = t.seen.get(key, 0) + 1
    weight = SOURCE_WEIGHT.get(ev.source, 0.2)
    credit = weight * ASSISTANCE.get(ev.assistance, 0.0) * novelty
    if _age_days(ev.at, now) > STALE_DAYS:
        credit *= 0.5  # old evidence is weaker evidence
    return _apply_task_cap(t, key, credit, weight)


def _apply_task_cap(t: _Tally, key: TaskKey, credit: float, weight: float) -> float:
    """Hard ceiling per distinct task. Doing the same thing again is allowed and
    is even good practice — it just stops counting as new evidence."""
    room = max(0.0, weight * PER_TASK_CAP - t.given.get(key, 0.0))
    credit = min(credit, room)
    t.given[key] = t.given.get(key, 0.0) + credit
    return credit


def _tally_to_score(t: _Tally) -> ConceptScore:
    total = max(0.0, min(1.0, t.total))
    enough_unaided = len(t.unaided_tasks) >= PROVEN_NEEDS_UNAIDED_TASKS
    level = _level_for(total, enough_unaided)
    return ConceptScore(
        score=total,
        level=level,
        passes=t.passes,
        fails=t.fails,
        unaided_repo=bool(t.unaided_tasks),
        unaided_tasks=len(t.unaided_tasks),
        projects=len(t.projects),
        blocked_by=_get_blocked_reason(level, total, enough_unaided, len(t.unaided_tasks)),
    )


def _level_for(total: float, enough_unaided: bool) -> Level:
    if total >= PROVEN_AT and enough_unaided:
        return "proven"
    if total >= RECALL_AT:
        return "recall"
    return "unproven"


def _get_blocked_reason(
    level: Level, total: float, enough_unaided: bool, unaided_count: int
) -> Optional[str]:
    """Why this concept is not `proven`, in the user's terms — or None when it
    already is."""
    if level == "proven":
        return None
    if total >= PROVEN_AT and not enough_unaided:
        return (
            "needs %d distinct unaided tasks in a real repository "
            "(you have %d)" % (PROVEN_NEEDS_UNAIDED_TASKS, unaided_count)
        )
    if enough_unaided:
        return "needs more evidence"
    return None


def profile(root: str, now: Optional[datetime] = None) -> Profile:
    by_concept: dict[str, list[EvidenceRow]] = {}
    for ev in load(root):
        by_concept.setdefault(ev.concept, []).append(ev)
    return Profile(
        concepts={c: score_concept(evs, now) for c, evs in by_concept.items()},
        note=(
            "Derived from evidence.jsonl. `proven` requires unaided work "
            "in a real repository — sandbox exercises alone cannot reach "
            "it, and repeating one exercise is worth progressively less."
        ),
    )


def _demo() -> None:
    """Self-check. Every assertion is a property the model must not lose."""
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)

    def ev(
        source: str,
        assistance: str,
        task: str,
        at: str = "2026-01-01T00:00:00+00:00",
        failed: bool = False,
        project: str = "/p",
    ) -> EvidenceRow:
        return EvidenceRow(
            at=at,
            concept="c",
            source=cast(Source, source),
            assistance=cast(Assistance, assistance),
            task=task,
            failed=failed,
            project=project,
        )

    _check_assistance(ev, now)
    _check_proven_needs_two_unaided(ev, now)
    _check_repetition_is_capped(ev, now)
    _check_failures_and_age(ev, now)
    _check_task_identity(ev, now)
    _check_near_duplicate_detection()
    _check_failed_flag_reaches_the_file()
    print("ok — 18 scoring properties hold")


def _check_assistance(ev: Ev, now: datetime) -> None:
    """AI did it -> nothing, however many times."""
    r = score_concept([ev("repo", "full", "t1"), ev("repo", "full", "t2")], now)
    assert r.score == 0 and r.level == "unproven", r

    # Partial help earns partial credit — half, not zero and not full.
    full = score_concept([ev("repo", "none", "t1")], now).score
    part = score_concept([ev("repo", "partial", "t1")], now).score
    assert abs(part - full / 2) < 1e-9, (full, part)


def _check_proven_needs_two_unaided(ev: Ev, now: datetime) -> None:
    """`proven` is two DISTINCT unaided repository tasks, and nothing else."""
    # One unaided repo task is strong evidence but NOT proof.
    r = score_concept([ev("repo", "none", "t1")], now)
    assert r.level == "recall", "one task must not prove a concept: %s" % r

    # Two DISTINCT unaided tasks do prove it.
    r = score_concept([ev("repo", "none", "t1"), ev("repo", "none", "t2")], now)
    assert r.level == "proven", r


def _check_repetition_is_capped(ev: Ev, now: datetime) -> None:
    """Repetition decays, and one exercise can never reach `proven`."""
    # The same task done twice does not — novelty halves the repeat.
    r = score_concept([ev("repo", "none", "t1"), ev("repo", "none", "t1")], now)
    assert r.level == "recall", "repeating one task must not prove it: %s" % r

    # Grinding ONE tutorial plateaus at PER_TASK_CAP x 0.2 = 0.30 — never
    # reaches proven, and never gets there without real work.
    same = [ev("sandbox", "none", "tut-a") for _ in range(8)]
    r = score_concept(same, now)
    assert r.level != "proven", "one tutorial, repeated, must not prove anything"
    assert not r.unaided_repo

    # Distinct tutorials are worth more than the same one repeated.
    varied = score_concept([ev("sandbox", "none", "tut-%d" % i) for i in range(3)], now)
    repeated = score_concept([ev("sandbox", "none", "tut-a") for _ in range(3)], now)
    assert varied.score > repeated.score, (varied, repeated)

    # A ground tutorial plus ONE real task is still not proof.
    r = score_concept(same + [ev("repo", "none", "real-1")], now)
    assert r.level != "proven", "one real task must not be enough: %s" % r

    # TWO distinct unaided real tasks are.
    r = score_concept(
        same + [ev("repo", "none", "real-1"), ev("repo", "none", "real-2")], now
    )
    assert r.level == "proven" and r.unaided_tasks == 2, r

    # Repeating ONE repo task forever is capped and never proves anything.
    r = score_concept([ev("repo", "none", "t1") for _ in range(20)], now)
    assert r.level == "recall", "one task repeated must cap out: %s" % r
    assert r.score <= 0.75 + 1e-9, r


def _check_failures_and_age(ev: Ev, now: datetime) -> None:
    """A measurement that can only go up is not a measurement."""
    # A failure pushes the level back down.
    r = score_concept(
        [
            ev("sandbox", "none", "t1"),
            ev("repo", "none", "t2", failed=True),
            ev("repo", "none", "t3", failed=True),
        ],
        now,
    )
    assert r.fails == 2 and r.score < 0.4, r

    # Old evidence weighs half.
    fresh = score_concept(
        [ev("repo", "none", "t1", at="2026-01-01T00:00:00+00:00")], now
    )
    stale = score_concept(
        [ev("repo", "none", "t1", at="2020-01-01T00:00:00+00:00")], now
    )
    assert stale.score < fresh.score, (fresh, stale)


def _check_task_identity(ev: Ev, now: datetime) -> None:
    """What counts as "the same task" — the rule that stops cross-repo work
    being silently penalised."""
    # The same task id in two different projects is two tasks, not a repeat.
    r = score_concept(
        [
            ev("repo", "none", "001", project="/a"),
            ev("repo", "none", "001", project="/b"),
        ],
        now,
    )
    assert r.level == "proven" and r.unaided_tasks == 2, (
        "task ids collided across projects: %s" % r
    )
    assert r.projects == 2, r

    # A tutorial is the same tutorial wherever it is run — project is ignored.
    r = score_concept(
        [
            ev("sandbox", "none", "tut-a", project="/a"),
            ev("sandbox", "none", "tut-a", project="/b"),
        ],
        now,
    )
    assert r.score < 0.4, "a repeated tutorial must decay across projects too: %s" % r


def _check_near_duplicate_detection() -> None:
    """The guard against silent fragmentation: `token-bucket`, `token_bucket`
    and `token-buckets` splitting one concept's evidence three ways."""
    tmp = tempfile.mkdtemp(prefix="grit-names-")
    try:
        record(tmp, "token-bucket", "repo", "none", "t1", project="/p")
        for variant in ("token_bucket", "token-buckets", "Token-Bucket"):
            assert get_near_duplicates(tmp, variant), (
                "%s must be flagged against token-bucket" % variant
            )
        assert not get_near_duplicates(
            tmp, "middleware-ordering"
        ), "an unrelated concept must not be flagged"
        assert not get_near_duplicates(
            tmp, "token-bucket"
        ), "an exact match is not a duplicate, it is the same concept"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _check_failed_flag_reaches_the_file() -> None:
    """`--failed` must actually reach the file. It did not, and a recorded
    failure raised the score instead of lowering it."""
    tmp = tempfile.mkdtemp(prefix="grit-failed-")
    try:
        record(tmp, "c", "repo", "none", "t1", project="/p")
        before = score_concept(load(tmp)).score
        record(tmp, "c", "repo", "none", "t2", project="/p", failed=True)
        rows = load(tmp)
        assert rows[-1].failed is True, (
            "failed flag never reached the evidence file: %s" % rows[-1]
        )
        after = score_concept(rows).score
        assert after < before, "a recorded failure must LOWER the score (%s -> %s)" % (
            before,
            after,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="grit scoring")
    ap.add_argument("command", choices=["record", "show", "concepts", "selftest"])
    ap.add_argument("concept", nargs="?")
    ap.add_argument("--source", choices=sorted(SOURCE_WEIGHT))
    ap.add_argument("--assistance", choices=sorted(ASSISTANCE))
    ap.add_argument("--task", default="")
    ap.add_argument("--detail", default="")
    ap.add_argument(
        "--project",
        default=os.getcwd(),
        help="repo this task belongs to; ignored for --source sandbox",
    )
    ap.add_argument("--failed", action="store_true")
    ap.add_argument(
        "--root", default=os.path.expanduser(os.environ.get("GRIT_ROOT", "~/.grit"))
    )
    return ap


def _print_concepts(root: str) -> int:
    names = get_known_concepts(root)
    print(
        "\n".join(names)
        if names
        else "(no concepts yet — the first recorded task creates one)"
    )
    return 0


def _print_profile(root: str) -> int:
    print(json.dumps(profile(root).to_dict(), indent=2))
    return 0


def _record_and_report(args: argparse.Namespace, root: str) -> int:
    """Record one task, warn about a fragmenting name, and print the new score."""
    if not (args.concept and args.source and args.assistance):
        print("record needs <concept> --source --assistance", file=sys.stderr)
        return 2
    _warn_if_name_splits_evidence(root, args.concept)
    record(
        root,
        args.concept,
        args.source,
        args.assistance,
        args.task,
        args.detail,
        args.project,
        failed=args.failed,
    )
    rows = [e for e in load(root) if e.concept == args.concept]
    print(json.dumps(score_concept(rows).to_dict(), indent=2))
    return 0


def _warn_if_name_splits_evidence(root: str, concept: str) -> None:
    """A warning, never a block — the user owns their concept names. But a
    split concept can never reach `proven`, and nobody notices a near-duplicate
    name because each one looks reasonable on its own."""
    dupes = get_near_duplicates(root, concept)
    if not dupes:
        return
    print(
        "grit: '%s' looks like an existing concept: %s\n"
        "      Using a new name SPLITS the evidence, and a split concept "
        "can never reach `proven`.\n"
        "      Reuse one of those names unless this is genuinely a "
        "different idea." % (concept, ", ".join(dupes)),
        file=sys.stderr,
    )


def main() -> int:
    args = _build_parser().parse_args()
    root = os.path.expanduser(args.root)

    if args.command == "selftest":
        _demo()
        return 0
    if args.command == "concepts":
        return _print_concepts(root)
    if args.command == "show":
        return _print_profile(root)
    return _record_and_report(args, root)


if __name__ == "__main__":
    sys.exit(main())
