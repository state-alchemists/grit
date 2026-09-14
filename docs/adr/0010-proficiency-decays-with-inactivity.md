# ADR 0010 — Proficiency decays with inactivity

- **Status**: Accepted — implemented (`STALE_DAYS = 90`)
- **Date**: 2026-09-13 (scope narrowed 2026-09-14)
- **Deciders**: Go Frendi
- **Context tags**: profiling, staleness, decay, measurement

> **Scope note.** This ADR originally decided two things: that a populated profile is *required for routing*, and that proficiency *decays*. The routing requirement is deferred with the rest of the router — see [ADR 0011](0011-routing-on-a-measured-profile-deferred.md). Decay shipped, and is what this record now covers.

## Context

A stored proficiency value raises a question the moment it is written: does it stay true?

Software work changes what people can do, in both directions. A developer who spent a quarter in a framework becomes fluent in it; one who spent a quarter in management may not have written production code at all. A value that never expires reports both as unchanged.

This matters more here than in a typical profile store, because the number is a *claim about capability*. "You are proven at token buckets" on evidence from eighteen months ago is not a measurement — it is a memory presented as one.

## Decision

> Proficiency values decay with inactivity. Evidence older than a staleness horizon counts for less rather than counting fully or being discarded.

Implemented in [ADR 0009](0009-graded-score-from-capped-evidence.md)'s model: evidence older than `STALE_DAYS` (90) contributes **half** its weight. Because the score is recomputed from `evidence.jsonl` on every read, decay needs no scheduled job and no stored expiry — a level falls simply because time passed, the next time anyone looks.

## Rationale

- **Stale confidence is worse than no confidence.** No confidence prompts a question; stale confidence asserts silently. The failure modes are asymmetric, so the default should favour the one that asks.
- **Halving beats discarding.** A hard cutoff makes a level fall off a cliff on an arbitrary day. Halving degrades the claim while keeping the evidence, which is the honest shape: you probably still know it, and nobody has checked lately.
- **Recomputation is what makes decay safe to tune.** The horizon is a guess. Because nothing is stored, changing it re-derives every level rather than migrating a database of wrong numbers.
- **A number that can only rise is not a measurement.** Decay and failure penalties are the two mechanisms that let it fall, and both are deliberate.

## Alternatives Considered

- **Never expire proficiency** — rejected. It converts the profile from a measurement into an assumption while retaining the appearance of measurement.
- **Hard expiry: evidence older than N days counts zero** — rejected. Same cliff problem, and it discards real evidence for a calendar reason.
- **Re-verify with a quiz on expiry** — rejected. That is another battery ([ADR 0011](0011-routing-on-a-measured-profile-deferred.md)) arriving through the back door, and it charges the user for the passage of time.
- **Decay per concept, tuned by how fast the technology moves** — attractive and not built. It needs a per-concept volatility estimate nobody has.

## Consequences

- **Positive**: a level reflects recent capability, and a user who stops practising sees it fall rather than keeping a badge.
- **Positive**: re-verification is free and tied to real work. A concept demonstrably used unaided in a real task is fresh evidence and refreshes the value without a quiz — which is what the original follow-up on this ADR asked for.
- **Negative**: **the horizon is unvalidated.** 90 days is a judgement. Too short and it nags a competent user; too long and it certifies someone who has drifted. Nothing has measured which.
- **Negative**: decay is invisible until someone reads the dashboard. There is no notification that a concept went stale, so a level can quietly fall without the user learning anything from it.

## Backlinks

- [ADR index](README.md)
- [ADR 0009 — A graded score, derived from capped evidence](0009-graded-score-from-capped-evidence.md) — where decay is implemented
- [ADR 0011 — Routing on a measured profile, deferred](0011-routing-on-a-measured-profile-deferred.md) — the routing half of the original ADR
- [ADR 0012 — Profile validity is the critical path](0012-profile-validity-is-the-critical-path.md)
