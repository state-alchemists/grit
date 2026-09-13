# ADR 0007 — Battery validity is the critical path

- **Status**: Accepted
- **Date**: 2026-09-13
- **Deciders**: Go Frendi
- **Context tags**: validation, study, risk, falsification

## Context

Every decision in this repository now depends on one unverified assumption: **that a short calibrated battery predicts real-work proficiency.**

- ADR 0001 routes on it.
- ADR 0002 stores it, decays it, and re-verifies against it.
- ADR 0003 withholds guidance based on it — the expertise-reversal argument depends on knowing who is an expert.
- ADR 0006 builds it and concedes it is unproven.

If the battery does not predict real-work proficiency, then **routing runs on noise**, the profile is an expensive quiz, and the dashboard is a confident view of a guess. The design does not degrade gracefully in that case; it collapses to a tutorial prompt before every task — the expertise-reversal harm case, delivered by design.

This is not a hypothetical risk to note and proceed past. It is the load-bearing claim.

## Decision

> Battery validity is the critical path and is tested before further design or implementation effort is invested. The study is preregistered, cheap, and specified to be falsifiable.

## Rationale

- **It is cheap to test.** No product is needed: a set of concepts, an item bank, and a log of real work over the following weeks. The cost is a weekend, not a build.
- **Everything downstream is speculative until it is answered.** Continuing to design against an unvalidated instrument is how this repository's earlier errors happened — a citation read wrong, a mechanism justified post-hoc.
- **A negative result is a real result.** If the battery does not predict, the honest product is a mirror (ADR 0004) with no router, and that is worth knowing before building the router.

## The study

**Q1 — Does the battery predict real-work proficiency?** Take the battery on a set of concepts. Over the following weeks, record actual unassisted performance on those same concepts in real work. If predictions and outcomes agree at better than chance, routing works. If not, the battery is an expensive quiz.

**Q2 — Does the battery under-rate experts?** Compare battery scores against demonstrated work performance **separately for concepts used frequently vs. rarely**. If it systematically under-rates the frequently-used set — because it quizzes people on synthetic items for things they do daily — the instrument is biased against the population it is meant to route correctly.

**Q3 — Adaptive vs. uniform vs. none.** Three conditions, randomised per task: adaptive gating, uniform gating, no gating. Contingent on Q1 succeeding. Predicts the adaptive condition wins; a real chance it does not.

**Q4 — Do stated preferences match what works?** Record the chosen tutorial format and the subsequent justification outcome. If format choice predicts nothing about outcome, preference is decoration and should stop being a first-class input.

## Preregistered predictions, with real chances of failing

1. The battery will **over-rate concepts the user has read about** and **under-rate concepts they do daily but would fail a quiz on**. If both hold, the profile needs a work-derived correction term and is never the final word.
2. **Probe-routing and claim-routing may produce the same outcomes**, because the user answers the claim first and the probe second, and the framing leaks. If so, the probe adds nothing and should be cut.
3. **Uniform gating may be worse than no gating** for experienced developers. If it is, that is a genuine finding and the product should be a mirror and nothing else.

## Method constraints

Adapted from the single-case-study methods review:

- **Randomised alternating treatments** (the METR design), not phase blocks.
- **Wash-in period excluded** from analysis, to let the novelty effect decay.
- **≥5 completed tasks per concept per condition.**
- **EMA probes** for in-the-moment friction — 4–6/day, last-30-minutes window, deferral latency logged.
- **Preregistered on OSF before week 1**, including decision rules and what would falsify each prediction.
- **Abandoned tasks are first-class outcomes**, not dropped — they are the most informative data and the most likely to be lost.

## Explicit non-measure

**Retained skill.** No design here can measure it; that requires a delayed unassisted assessment. Adoption and behaviour are not learning, and this study must not be reported as if they were. This is the same category error that produced the Kapoor mis-citation earlier in the design.

## Consequences

- **Positive**: the highest-risk assumption is tested before investment compounds on top of it.
- **Negative**: no implementation work should proceed until Q1 returns. That is a real delay.
- **Negative**: an N=1 study cannot distinguish "the battery is invalid" from "the battery is invalid for me." The version worth running later — 10–20 developers, gated at random, measuring completion and switch rates — is a weekend of work and has not been run by anyone in this space.
- **Follow-ups**: if Q1 fails, ADR 0001, 0002, 0003, and 0006 all require revision, and the product reduces to ADR 0004.

## Backlinks

- [ADR index](index.md)
- [ADR 0001](0001-route-on-measured-proficiency.md) · [0002](0002-required-profile-with-decay.md) · [0003](0003-withhold-guidance-by-default.md) · [0006](0006-calibrated-battery-not-mini-games.md)
