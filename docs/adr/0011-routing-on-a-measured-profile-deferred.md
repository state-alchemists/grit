# ADR 0011 — Routing on a measured profile, and why it is deferred

- **Status**: Accepted — **deferred**, nothing implements it
- **Date**: 2026-09-13 (consolidated 2026-09-14)
- **Deciders**: Go Frendi
- **Context tags**: routing, measurement, profiling, onboarding, psychometrics, expertise-reversal

> **Consolidation note.** This record merges three earlier ADRs that decided one thing between them — how the product would decide who needs a tutorial: *Route on measured proficiency, never on self-report*, *Calibrated onboarding battery, not a set of mini-games*, and the routing requirement from *Require a populated profile*. They were separate files describing a single unbuilt subsystem, which made the deferral hard to see. Nothing here was rejected; the decay half of the profile ADR shipped and lives in [ADR 0010](0010-proficiency-decays-with-inactivity.md).

## Context

The product must decide, per concept a task requires, whether the user needs a tutorial. The obvious mechanism is to ask — *"do you know token buckets?"* — and route on the answer. It is cheap, needs no instrumentation, and resolves in one conversational turn.

The evidence says that specific question is unreliable, and unreliable in a direction that concentrates harm on the users it is meant to protect.

METR (2025, RCT, 16 experienced OSS developers, 246 tasks on their own mature repos) found AI made developers **19% slower** while those developers believed it made them **20% faster** — a ~39-point gap. That is not a self-reporting accuracy problem users can fix by trying harder; it is a measurement problem.

The population at risk is precisely the population that answers confidently. A senior developer who has watched AI write twelve rate limiters will say they know token buckets. The people most likely to route themselves past the tutorial are the ones who most need it.

An earlier design in this repository asked users to pick a mode — *walkthrough / attempt / solve* — at the start of each mission. Kapoor et al. (2025, N=885) measured that design: with optional guardrails and a "See Solution" bypass, **50% of students used the bypass at least once, 14% on every problem, and lower-performing students bypassed more, especially near deadlines.** Routing on a self-declared preference reproduced the failure it was meant to prevent.

That settles *what not to route on*. Two questions follow: what the instrument is, and whether the profile it fills is optional.

## Decision

> Route on demonstrated proficiency — measured by a calibrated, adaptive onboarding battery or by a probe on the specific concept — never on a claim of knowledge. A populated profile is required for routing, degrading to a probe rather than a block. Gamification is permitted as packaging, never as the instrument.

The user may name which concepts they believe they have. That selection determines *what is probed*, never what happens.

Routing precedence:

1. **Profiled concept** → route from the profile; no question asked.
2. **Unprofiled concept** → route from a probe question.
3. **Never** → route from "I know this."

The battery is adaptive, spans a range of item difficulty, and has a deliberate stopping rule. Success escalates difficulty, failure descends.

## Rationale

- **A battery is not self-report, so METR's gap does not apply to it.** It is the only mechanism in the design that can *answer* "can proficiency be inferred?" rather than assume it — which is why [ADR 0012](0012-profile-validity-is-the-critical-path.md) is stated against it.
- **A probe question is itself a retrieval-practice event** ([Rowland 2014](https://doi.org/10.1037/a0037559), meta-analysis, **g = 0.50**), so the router does useful work even when it routes *away* from a tutorial.
- **The disqualifying evidence is specific and directional.** METR shows the error is systematic over-confidence, not random noise — the worst possible failure mode for routing.
- **A game measures ability in the game**, while routing needs ability in the user's workflow, and these diverge hardest for experts. A developer who has written rate limiters for a decade may do badly on a timed token-bucket puzzle because they are bored, not ignorant. A game-based battery therefore **under-rates experienced users and routes them into tutorials they do not need** — expertise reversal ([ADR 0002](0002-withhold-guidance-by-default.md)) manufactured by the onboarding step itself.
- **The stopping rule matters more than the format.** A battery that stops at the first failure under-rates anyone with a specific, unusual gap — a common shape for senior developers with deep expertise in one stack and none in an adjacent one.
- **Skippable onboarding fails for a specific reason.** Kapoor et al. found the users who bypass guardrails are the lower-performing ones, especially under time pressure. The same incentive applies to skipping calibration: the confident skip first and suffer most.
- **Unprofiled concepts need a fallback, not a block.** Blocking would make the product unusable on any new technology — exactly when a user needs it.

## Alternatives Considered

- **Ask the user directly and trust the answer** — rejected. This is the METR case. It routes the most at-risk users past the intervention, silently, and the error is invisible by construction.
- **Mini-games as the instrument** — rejected, for the under-rating argument above. Retained as presentation only: a battery can be paced, scored and made satisfying without the score being a game score.
- **A fixed linear test** — rejected. Slow for experts, discouraging for beginners, biased at both ends.
- **Infer proficiency purely from instrumented signal, never ask** — rejected as the *primary* mechanism, not on principle but because inference is unvalidated. Retained as the long-run target — and note that [ADR 0009](0009-graded-score-from-capped-evidence.md) subsequently made a version of it the *only* mechanism.
- **Work-derived profiling only, no battery** — rejected as the sole mechanism: honest but slow, and empty at first run, precisely when routing is needed. **This is the option that shipped**, once ADR 0009 established that an empty profile at first run is acceptable because nothing routes on it.
- **Optional profile, trust claims when absent** — rejected. Reintroduces the self-report problem for exactly the at-risk population.
- **Block routing until the full taxonomy is profiled** — rejected. Punishes users for working in a technology the taxonomy has not seen.
- **No onboarding; probe every concept every time** — rejected. Probes are themselves guidance ([ADR 0002](0002-withhold-guidance-by-default.md)), so this maximises the harm case it was meant to avoid.

## Why this is deferred

[ADR 0009](0009-graded-score-from-capped-evidence.md) made repository work an evidence source, so a profile can be populated by doing real work with the assistant kept out of the editor. That removed the reason the battery had to exist *before anything could be measured* — which was the only thing forcing it to be built first.

What the deferral costs, stated plainly rather than discovered later:

- **There is no router.** The skill offers the self-completion choice on every activation; it does not decide, from a measurement, who needs a tutorial. The offer is uniform, which is the thing this ADR argued against.
- **There is no probe.** An unprofiled concept produces no question, so the retrieval-practice benefit above is not being collected.
- **First run is empty and stays empty until you do work.** That is honest, and it is worse as a demo than a battery would be.

The decision stands as the design position. If routing is built, it is built this way.

## Consequences

- **Positive**: routing errors would be visible and correctable rather than silent, and the battery would produce a real datum against which [ADR 0012](0012-profile-validity-is-the-critical-path.md) could be run.
- **Negative**: building it turns a coding assistant into an exam you sit first. This friction is unavoidable given the decision above, and it is real.
- **Negative**: the battery and probes are **external guidance**, and the expertise reversal effect ([ADR 0002](0002-withhold-guidance-by-default.md)) says guidance is costly for experts. A battery reduces probe frequency; it does not eliminate the cost.
- **Negative**: **validity is unproven.** A battery in version control is *reproducible*, not *accurate* — [ADR 0012](0012-profile-validity-is-the-critical-path.md).

## Backlinks

- [ADR index](README.md)
- [ADR 0002 — Withhold guidance by default](0002-withhold-guidance-by-default.md)
- [ADR 0009 — A graded score](0009-graded-score-from-capped-evidence.md) — what deferred this
- [ADR 0010 — Proficiency decays](0010-proficiency-decays-with-inactivity.md) — the half that shipped
- [ADR 0012 — Profile validity is the critical path](0012-profile-validity-is-the-critical-path.md)
