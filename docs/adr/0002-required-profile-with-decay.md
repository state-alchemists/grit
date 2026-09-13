# ADR 0002 — Require a populated profile, and let proficiency decay

- **Status**: Accepted — unblocked by [ADR 0014](0014-graded-score-from-capped-evidence.md)
- **Date**: 2026-09-13
- **Deciders**: Go Frendi
- **Context tags**: profiling, onboarding, staleness, routing

## Context

ADR 0001 establishes that routing cannot trust self-report. That leaves a question about the profile itself: is filling it optional, and does a stored proficiency value stay valid?

Both matter because the profile is the value the router reads. An optional profile recreates the problem ADR 0001 rejected — users who skip are routed on claims. A permanent profile creates a different problem: proficiency from six months ago is a prior about a person who no longer exists.

Software work changes what people can do, in both directions. A developer who spent a quarter in a framework becomes fluent in it; one who spent a quarter in management may not have written production code at all. A profile that never expires reports both as unchanged.

## Decision

> A populated profile is required for routing, with graceful degradation for unprofiled concepts, and proficiency values decay with inactivity.

Routing rules, in precedence order:

1. **Profiled concept** → route from the profile; no question asked.
2. **Unprofiled concept** → route from a probe question (ADR 0001).
3. **Never** → route from "I know this."

## Rationale

- **Skippable onboarding fails for a specific reason.** Kapoor et al. (2025) found the users who bypass guardrails are the lower-performing ones, especially under time pressure. The same incentive applies to skipping a calibration step: the confident skip first and suffer most.
- **Unprofiled concepts need a fallback, not a block.** Blocking on an unprofiled concept would make the product unusable on any new technology — which is exactly when a user needs it. A probe is cheap and produces a datum.
- **Stale confidence is worse than no confidence**, because no confidence triggers a probe and stale confidence routes silently. The failure modes are asymmetric, so the default should favour the one that asks.

## Alternatives Considered

- **Optional profile, trust claims when absent** — rejected. Reintroduces ADR 0001's problem for exactly the at-risk population.
- **Block routing until the full taxonomy is profiled** — rejected. Punishes users for working in a technology the taxonomy has not seen, which is the moment of highest need.
- **Never expire proficiency** — rejected. It converts the profile from a measurement into an assumption while retaining the appearance of measurement.
- **Confidence-gated progressive profiling** — partially adopted. Routing confidence grows as signal accumulates; this is how degradation works in practice rather than a hard on/off.

## Consequences

- **Positive**: routing is honest about what it knows. Unprofiled concepts are handled explicitly rather than by guessing.
- **Negative**: onboarding friction is now mandatory. This is a real cost paid before any value is delivered.
- **Negative**: decay must be tuned, and a badly tuned curve either probes too often (annoying an expert, see ADR 0003) or too rarely (silently wrong). The decay curve is a parameter nobody has validated, and it is exposed in `profile.json`.
- **Follow-ups**: decay re-verification should be cheap and tied to real work, not another battery. A concept demonstrably used unaided in a real task is fresh evidence and should refresh the value without a quiz.

## Backlinks

- [ADR index](index.md)
- [ADR 0001 — Route on measured proficiency](0001-route-on-measured-proficiency.md)
- [ADR 0003 — Withhold guidance by default](0003-withhold-guidance-by-default.md)

---

## Addendum — 2026-09-13: this requirement cannot currently be met

This ADR requires a populated profile before the router can function. The implementation has no way to populate one.

The chain is `profile ← ledger ← tutorial session ← a tutorial file`, and **nothing generates a tutorial file**. `/profile` therefore returns `{}` on every installation and will keep doing so. The only route to a single profile entry is hand-authoring an HTML page and a differential test in JavaScript, per concept.

So the decision stands as a design position and is inoperable as a requirement. Two consequences worth stating plainly rather than discovering later:

- **The router cannot run.** Every concept reads as unprofiled, which under ADR 0001 routes to a probe. With no probe budget this produced an interrogation on first contact — three essay questions before a file existed. The budget added to `SKILL.md` caps the symptom; the cause is here.
- **The dashboard's headline figures are permanently zero.** The standing ring and every concept count derive from the profile. The one measurement that does work — assistant authorship, from the hook — was not on the dashboard at all until it was added on this date.

Until tutorial generation exists (ADR 0005) or the battery is built and validated (ADR 0007), the honest reading of this ADR is *"required, and not yet obtainable"*. It should not be cited as a shipped constraint.

## Addendum 2 — 2026-09-13: unblocked, by a second evidence source

The blockage above was caused by a single input: tutorials, which nothing generates. [ADR 0014](0014-graded-score-from-capped-evidence.md) adds **repository tasks** as an evidence source, so the profile can now be populated by doing real work with the assistant kept out of the editor — no tutorial required.

The requirement in this ADR therefore stands and is now satisfiable. What remains unproven is not whether a profile can exist, but whether the level it reports predicts real capability — still ADR 0007, still unrun.
