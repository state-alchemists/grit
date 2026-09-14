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

import argparse
import difflib
import json
import os
import sys
from datetime import datetime, timezone

# Real work counts for more than an exercise. See ADR 0004: a sandbox check is
# a weaker oracle, and the weights are that rule expressed as arithmetic.
# Calibrated so that ONE unaided task is strong evidence but not proof — two
# distinct ones are. A single instance is a data point, not a capability, and
# an early draft that scored 1.0 for one task made `proven` meaningless.
#   1 unaided repo task      0.50  -> recall
#   2 distinct unaided tasks 1.00  -> proven
#   the SAME task twice      0.75  -> still recall (novelty halves the repeat)
#   one tutorial, ground     ~0.40 -> recall ceiling, never proven
SOURCE_WEIGHT = {"repo": 0.5, "sandbox": 0.2}

# The core claim of the product, as a number.
ASSISTANCE = {"none": 1.0, "partial": 0.5, "full": 0.0}

# A single task or tutorial can never contribute more than this multiple of its
# own weight, however many times it is repeated. `1/(1+n)` alone was not enough:
# it is a harmonic series, so six runs of one tutorial still added 0.49 and
# pushed a concept to `proven`. Repetition has to have a hard ceiling, not a
# slow one.
PER_TASK_CAP = 1.5

# `proven` needs TWO distinct unaided repository tasks. One is a data point that
# a well-ground tutorial can top up past the threshold; two is a pattern.
PROVEN_NEEDS_UNAIDED_TASKS = 2

LEVELS = ("unproven", "recall", "proven")
RECALL_AT = 0.30
PROVEN_AT = 0.80
STALE_DAYS = 90


def _now():
    return datetime.now(timezone.utc).isoformat()


def _age_days(stamp, now=None):
    try:
        then = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return ((now or datetime.now(timezone.utc)) - then).days


def evidence_path(root):
    return os.path.join(root, "evidence.jsonl")


def load(root):
    path = evidence_path(root)
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue  # one bad line must not void a record
    return out


def task_key(source, project, task):
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


def known_concepts(root):
    return sorted({e.get("concept", "") for e in load(root) if e.get("concept")})


def near_duplicates(root, concept, cutoff=0.82):
    """Existing concept names close enough to `concept` to be the same idea.

    Fragmentation is the silent failure of this model: `token-bucket`,
    `token_bucket` and `token-buckets` split one concept's evidence three ways,
    so the work is done three times and nothing ever reaches `proven`. Nobody
    notices, because each name looks reasonable on its own.

    A warning, never a block — the user owns their concept names, and two
    similar names are sometimes genuinely two things.
    """
    existing = known_concepts(root)
    if concept in existing:
        return []
    norm = lambda x: x.lower().replace("_", "-").replace(" ", "-").rstrip("s")
    hits = [c for c in existing if norm(c) == norm(concept)]
    hits += [
        c
        for c in difflib.get_close_matches(concept, existing, n=3, cutoff=cutoff)
        if c not in hits
    ]
    return hits


def record(
    root, concept, source, assistance, task, detail="", project="", failed=False
):
    if source not in SOURCE_WEIGHT:
        raise ValueError("source must be one of %s" % list(SOURCE_WEIGHT))
    if assistance not in ASSISTANCE:
        raise ValueError("assistance must be one of %s" % list(ASSISTANCE))
    row = {
        "at": _now(),
        "concept": concept,
        "source": source,
        "assistance": assistance,
        "task": task,
        "detail": detail,
        "project": os.path.abspath(project) if project else "",
    }
    if failed:
        # Before the write, not on the returned dict: the file is the record,
        # and a failure that misses it scores as a pass.
        row["failed"] = True
    os.makedirs(root, exist_ok=True)
    with open(evidence_path(root), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row


def score_concept(events, now=None):
    """Score one concept's events. Pure: no clock, no disk, no globals."""
    total = 0.0
    seen = {}  # (source, task) -> how many times already
    given = {}  # (source, task) -> credit already granted
    unaided_tasks = set()  # distinct repo tasks done with no help
    projects = set()
    passes = fails = 0

    for ev in sorted(events, key=lambda e: e.get("at", "")):
        source = ev.get("source", "sandbox")
        assistance = ev.get("assistance", "full")
        key = task_key(source, ev.get("project", ""), ev.get("task", ""))

        if ev.get("failed"):
            # A measured failure is evidence too, and it points down. Without
            # this the score only ever rises, which is what a vanity metric is.
            fails += 1
            total = max(0.0, total - 0.25)
            continue

        passes += 1
        if ev.get("project"):
            projects.add(ev["project"])
        novelty = 1.0 / (1.0 + seen.get(key, 0))
        seen[key] = seen.get(key, 0) + 1

        weight = SOURCE_WEIGHT.get(source, 0.2)
        credit = weight * ASSISTANCE.get(assistance, 0.0) * novelty
        if _age_days(ev.get("at"), now) > STALE_DAYS:
            credit *= 0.5  # old evidence is weaker evidence

        # Hard ceiling per distinct task. Doing the same thing again is allowed
        # and is even good practice — it just stops counting as new evidence.
        room = max(0.0, weight * PER_TASK_CAP - given.get(key, 0.0))
        credit = min(credit, room)
        given[key] = given.get(key, 0.0) + credit
        total += credit

        if source == "repo" and assistance == "none":
            unaided_tasks.add(key)

    total = max(0.0, min(1.0, total))
    enough_unaided = len(unaided_tasks) >= PROVEN_NEEDS_UNAIDED_TASKS

    if total >= PROVEN_AT and enough_unaided:
        level = "proven"
    elif total >= RECALL_AT:
        level = "recall"
    else:
        level = "unproven"

    blocked = None
    if level != "proven":
        if total >= PROVEN_AT and not enough_unaided:
            blocked = (
                "needs %d distinct unaided tasks in a real repository "
                "(you have %d)" % (PROVEN_NEEDS_UNAIDED_TASKS, len(unaided_tasks))
            )
        elif enough_unaided:
            blocked = "needs more evidence"

    return {
        "score": round(total, 3),
        "level": level,
        "passes": passes,
        "fails": fails,
        "unaided_repo": bool(unaided_tasks),
        "unaided_tasks": len(unaided_tasks),
        "projects": len(projects),
        "blocked_by": blocked,
    }


def profile(root, now=None):
    by_concept = {}
    for ev in load(root):
        by_concept.setdefault(ev.get("concept", "?"), []).append(ev)
    concepts = {c: score_concept(evs, now) for c, evs in by_concept.items()}
    proven = sum(1 for v in concepts.values() if v["level"] == "proven")
    recall = sum(1 for v in concepts.values() if v["level"] == "recall")
    return {
        "concepts": concepts,
        "headline": {"proven": proven, "recall": recall, "tracked": len(concepts)},
        "note": (
            "Derived from evidence.jsonl. `proven` requires unaided work "
            "in a real repository — sandbox exercises alone cannot reach "
            "it, and repeating one exercise is worth progressively less."
        ),
    }


def _demo():
    """Self-check. Every assertion is a property the model must not lose."""
    base = "2026-01-01T00:00:00+00:00"

    def ev(source, assistance, task, at=base, failed=False, project="/p"):
        return {
            "at": at,
            "source": source,
            "assistance": assistance,
            "task": task,
            "failed": failed,
            "project": project,
        }

    now = datetime(2026, 1, 2, tzinfo=timezone.utc)

    # AI did it -> nothing, however many times.
    r = score_concept([ev("repo", "full", "t1"), ev("repo", "full", "t2")], now)
    assert r["score"] == 0 and r["level"] == "unproven", r

    # One unaided repo task is strong evidence but NOT proof.
    r = score_concept([ev("repo", "none", "t1")], now)
    assert r["level"] == "recall", "one task must not prove a concept: %s" % r

    # Two DISTINCT unaided tasks do prove it.
    r = score_concept([ev("repo", "none", "t1"), ev("repo", "none", "t2")], now)
    assert r["level"] == "proven", r

    # The same task done twice does not — novelty halves the repeat.
    r = score_concept([ev("repo", "none", "t1"), ev("repo", "none", "t1")], now)
    assert r["level"] == "recall", "repeating one task must not prove it: %s" % r

    # Grinding ONE tutorial plateaus at PER_TASK_CAP x 0.2 = 0.30 — never reaches
    # proven, and never gets there without real work.
    same = [ev("sandbox", "none", "tut-a") for _ in range(8)]
    r = score_concept(same, now)
    assert r["level"] != "proven", "one tutorial, repeated, must not prove anything"
    assert not r["unaided_repo"]

    # Distinct tutorials are worth more than the same one repeated.
    varied = score_concept([ev("sandbox", "none", "tut-%d" % i) for i in range(3)], now)
    repeated = score_concept([ev("sandbox", "none", "tut-a") for _ in range(3)], now)
    assert varied["score"] > repeated["score"], (varied, repeated)

    # A ground tutorial plus ONE real task is still not proof.
    r = score_concept(same + [ev("repo", "none", "real-1")], now)
    assert r["level"] != "proven", "one real task must not be enough: %s" % r

    # TWO distinct unaided real tasks are.
    r = score_concept(
        same + [ev("repo", "none", "real-1"), ev("repo", "none", "real-2")], now
    )
    assert r["level"] == "proven" and r["unaided_tasks"] == 2, r

    # Repeating ONE repo task forever is capped and never proves anything.
    r = score_concept([ev("repo", "none", "t1") for _ in range(20)], now)
    assert r["level"] == "recall", "one task repeated must cap out: %s" % r
    assert r["score"] <= 0.75 + 1e-9, r

    # Partial help earns partial credit — half, not zero and not full.
    full = score_concept([ev("repo", "none", "t1")], now)["score"]
    part = score_concept([ev("repo", "partial", "t1")], now)["score"]
    assert abs(part - full / 2) < 1e-9, (full, part)

    # A failure pushes the level back down.
    r = score_concept(
        [
            ev("sandbox", "none", "t1"),
            ev("repo", "none", "t2", failed=True),
            ev("repo", "none", "t3", failed=True),
        ],
        now,
    )
    assert r["fails"] == 2 and r["score"] < 0.4, r

    # Old evidence weighs half.
    fresh = score_concept(
        [ev("repo", "none", "t1", at="2026-01-01T00:00:00+00:00")], now
    )
    stale = score_concept(
        [ev("repo", "none", "t1", at="2020-01-01T00:00:00+00:00")], now
    )
    assert stale["score"] < fresh["score"], (fresh, stale)

    # The same task id in two different projects is two tasks, not a repeat.
    r = score_concept(
        [
            ev("repo", "none", "001", project="/a"),
            ev("repo", "none", "001", project="/b"),
        ],
        now,
    )
    assert r["level"] == "proven" and r["unaided_tasks"] == 2, (
        "task ids collided across projects: %s" % r
    )
    assert r["projects"] == 2, r

    # A tutorial is the same tutorial wherever it is run — project is ignored.
    r = score_concept(
        [
            ev("sandbox", "none", "tut-a", project="/a"),
            ev("sandbox", "none", "tut-a", project="/b"),
        ],
        now,
    )
    assert r["score"] < 0.4, (
        "a repeated tutorial must decay across projects too: %s" % r
    )

    # Near-duplicate detection: the guard against silent fragmentation.
    import shutil as _sh
    import tempfile

    tmp = tempfile.mkdtemp(prefix="grit-names-")
    try:
        record(tmp, "token-bucket", "repo", "none", "t1", project="/p")
        for variant in ("token_bucket", "token-buckets", "Token-Bucket"):
            assert near_duplicates(tmp, variant), (
                "%s must be flagged against token-bucket" % variant
            )
        assert not near_duplicates(
            tmp, "middleware-ordering"
        ), "an unrelated concept must not be flagged"
        assert not near_duplicates(
            tmp, "token-bucket"
        ), "an exact match is not a duplicate, it is the same concept"
    finally:
        _sh.rmtree(tmp, ignore_errors=True)

    # `--failed` must actually reach the file. It did not, and a recorded
    # failure raised the score instead of lowering it.
    tmp2 = tempfile.mkdtemp(prefix="grit-failed-")
    try:
        record(tmp2, "c", "repo", "none", "t1", project="/p")
        before = score_concept(load(tmp2))["score"]
        record(tmp2, "c", "repo", "none", "t2", project="/p", failed=True)
        rows = load(tmp2)
        assert rows[-1].get("failed") is True, (
            "failed flag never reached the evidence file: %s" % rows[-1]
        )
        after = score_concept(rows)["score"]
        assert after < before, "a recorded failure must LOWER the score (%s -> %s)" % (
            before,
            after,
        )
    finally:
        _sh.rmtree(tmp2, ignore_errors=True)

    print("ok — 18 scoring properties hold")


def main():
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
    args = ap.parse_args()
    root = os.path.expanduser(args.root)

    if args.command == "selftest":
        _demo()
        return 0

    if args.command == "concepts":
        names = known_concepts(root)
        print(
            "\n".join(names)
            if names
            else "(no concepts yet — the first recorded task creates one)"
        )
        return 0

    if args.command == "show":
        print(json.dumps(profile(root), indent=2))
        return 0

    if not (args.concept and args.source and args.assistance):
        print("record needs <concept> --source --assistance", file=sys.stderr)
        return 2
    dupes = near_duplicates(root, args.concept)
    if dupes:
        print(
            "grit: '%s' looks like an existing concept: %s\n"
            "      Using a new name SPLITS the evidence, and a split concept "
            "can never reach `proven`.\n"
            "      Reuse one of those names unless this is genuinely a "
            "different idea." % (args.concept, ", ".join(dupes)),
            file=sys.stderr,
        )
    row = record(
        root,
        args.concept,
        args.source,
        args.assistance,
        args.task,
        args.detail,
        args.project,
        failed=args.failed,
    )
    print(
        json.dumps(
            score_concept([e for e in load(root) if e.get("concept") == args.concept]),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
