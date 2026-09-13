# ADR 0006 — Calibrated onboarding battery, not a set of mini-games

- **Status**: Accepted
- **Date**: 2026-09-13
- **Deciders**: Go Frendi
- **Context tags**: onboarding, calibration, psychometrics, instrumentation

## Context

ADR 0001 requires proficiency to be measured rather than asked, and ADR 0002 requires the profile before routing works. That leaves the question of **what the onboarding instrument actually is**.

The intuitive answer is a set of mini-games: fun, low-friction, and it produces a score. The problem is that a game measures ability **in the game**, while routing needs ability **in the user's actual workflow**. These diverge hardest for experts — a developer who has written rate limiters for a decade may do badly on a timed token-bucket puzzle because they are bored, not ignorant.

The consequence is not neutral. A game-based battery **systematically under-rates experienced users, who are then routed into tutorials they do not need** — which is the expertise reversal of ADR 0003 arriving through the front door, manufactured by the onboarding step itself.

## Decision

> Onboarding is an adaptive, calibrated battery with items spanning a range of difficulty and a deliberate stopping rule. Gamification is permitted as packaging — pacing, feedback, progress — but never as the instrument.

## Rationale

- **Calibration is how psychometrics has always handled this.** You do not ask people their ability; you measure it, with items that span difficulty so a strong respondent can demonstrate strength quickly.
- **Adaptive selection is both shorter and fairer.** Success escalates difficulty, failure descends. A fixed easy-to-hard sequence wastes a strong user's time and a fixed hard sequence humiliates a weak one.
- **The stopping rule matters more than the format.** A battery that stops at the first failure will systematically under-rate anyone with a specific, unusual gap — which is a common shape for senior developers who have deep expertise in one stack and none in an adjacent one.
- **It is not self-report, so METR's ~39-point gap does not apply.** This is the first mechanism in the design capable of answering the critical question (ADR 0007) rather than assuming it.

## Alternatives Considered

- **Mini-games as the instrument** — rejected, for the reason above. Retained as presentation only: a battery can be paced, scored, and made satisfying without the score being a game score.
- **A fixed linear test** — rejected. Slow for experts, discouraging for beginners, and biased at both ends.
- **Work-derived profiling only, no battery** — rejected as the sole mechanism. Honest but slow, and empty at first run — precisely when routing is needed. Retained alongside: real work is ground truth and continuously corrects the battery.
- **No onboarding; probe every concept every time** — rejected. Probes are themselves guidance (ADR 0003), so this maximises the harm case it was meant to avoid.

## Consequences

- **Positive**: the profile starts populated, so most concepts route without a question — which is what keeps ADR 0003's probe cost down.
- **Negative**: it is a test, and tests are unpopular. A user who wanted a coding assistant has been handed an exam before they can use it. This friction is unavoidable given ADR 0001, but it is real.
- **Negative**: **validity is unproven.** A battery in version control is *reproducible*, not *accurate*. (Q1, ADR 0007.)
- **Negative**: the instrument can be biased against the population it serves, and the bias is invisible without a specific test. (Q2, ADR 0007.)
- **Follow-ups**: keep the battery short and adaptive; frame it as calibration rather than assessment; make its usefulness visible early — the first time it prevents a pointless tutorial, the cost is repaid.

## Backlinks

- [ADR index](index.md)
- [ADR 0001 — Route on measured proficiency](0001-route-on-measured-proficiency.md)
- [ADR 0002 — Required profile with decay](0002-required-profile-with-decay.md)
- [ADR 0007 — The critical path](0007-critical-path-battery-validity.md)
