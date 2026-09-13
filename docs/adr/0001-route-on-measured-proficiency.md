# ADR 0001 — Route on measured proficiency, never on self-report

- **Status**: Accepted
- **Date**: 2026-09-13
- **Deciders**: Go Frendi
- **Context tags**: routing, measurement, profiling, expertise-reversal

## Context

The product must decide, for each concept a task requires, whether the user needs a tutorial. The obvious mechanism is to ask: *"do you know token buckets?"* and route on the answer. It is cheap, requires no instrumentation, and works in a single conversational turn.

The evidence says this specific question is unreliable, and unreliable in a direction that concentrates harm on the users it is meant to protect.

METR (2025, RCT, 16 experienced OSS developers, 246 tasks on their own mature repos) found AI made developers **19% slower** while those developers believed it made them **20% faster** — a ~39-point gap. That is not a self-reporting accuracy problem users can fix by trying harder; it is a measurement problem.

The population at risk is precisely the population that answers confidently. A senior developer who has watched AI write twelve rate limiters will say they know token buckets. The people most likely to route themselves past the tutorial are the ones who most need it.

An earlier design in this repository asked users to pick a mode (*walkthrough / attempt / solve*) at the start of each mission. Kapoor et al. (2025, N=885) measured that design: with optional guardrails and a "See Solution" bypass, **50% of students used the bypass at least once, 14% on every problem, and lower-performing students bypassed more, especially near deadlines.** Routing on a self-declared preference reproduced the failure it was meant to prevent.

## Decision

> We will route on demonstrated proficiency, measured either by a calibrated onboarding battery or by a probe question on the specific concept, and never on the user's claim of knowledge.

The user may name which concepts they believe they have. That selection determines *what is probed*, never what happens. The routing decision comes from the answer or the measurement.

## Rationale

- **The battery is not self-report, so METR's gap does not apply to it.** This is the only mechanism in the design that can answer "can proficiency be inferred?" rather than assume it.
- **A probe question is itself a retrieval-practice event** ([Rowland 2014](https://doi.org/10.1037/a0037559), meta-analysis, **g = 0.50**), so the router does work even when it routes *away* from a tutorial.
- **The disqualifying evidence is specific and directional.** METR shows the error is not random noise but systematic over-confidence, which is the worst possible failure mode for routing.

The finding that made this non-negotiable: an earlier phase of this design relied on a mode the user selected at mission start. That is the Kapoor configuration, measured at 50% bypass. The trigger moved from a *mode you choose once* to a *question at the moment of work*, which removes the bypass affordance structurally rather than arguing about it.

## Alternatives Considered

- **Ask the user directly and trust the answer** — rejected. This is the METR case. It routes the most at-risk users past the intervention, silently, and the error is invisible by construction.
- **Infer proficiency purely from instrumented signal, never ask** — rejected as the *primary* mechanism, not on principle but because inference is unvalidated (see ADR 0005). Retained as the long-run target; real work is the ground truth and updates the profile continuously.
- **Optional onboarding, trust claims for users who skip** — rejected. The confident skip, so routing degrades to claims for exactly the at-risk population. Profile completion is required.
- **Full game-based onboarding** — rejected for the *instrument* while retained as packaging. Games test ability *in the game*; routing needs ability *in the workflow*. See ADR 0006.

## Consequences

- **Positive**: routing errors are visible and correctable, rather than silent. The battery produces a real datum; the probe produces a retrieval event even when no tutorial is needed.
- **Negative**: the product now requires an onboarding step before it can route at all. A coding assistant has been turned into an exam you sit first.
- **Negative**: the battery and probes are **external guidance**, and the expertise reversal effect (ADR 0003) says guidance is costly for experts. The battery reduces probe frequency; it does not eliminate the cost.
- **Follow-ups**: run Q1 — does the battery predict real-work proficiency? Until answered, the profile is a well-packaged prior, not a measurement. See ADR 0007.

## Backlinks

- [ADR index](index.md)
- [ADR 0002 — Required profile](0002-required-profile-with-decay.md)
- [ADR 0005 — Grounded on-demand tutorials](0005-grounded-on-demand-tutorials.md)
- [ADR 0006 — Calibrated battery, not mini-games](0006-calibrated-battery-not-mini-games.md)
