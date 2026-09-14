# ADR 0012 — Profile validity is the critical path

- **Status**: Accepted — the study is **unrun**
- **Date**: 2026-09-13 (restated against the score, 2026-09-14)
- **Deciders**: Go Frendi
- **Context tags**: validation, study, risk, falsification

> **Restatement note.** This ADR was written as *"Battery validity is the critical path"*, when the onboarding battery was the only instrument. [ADR 0009](0009-graded-score-from-capped-evidence.md) replaced the battery with a score derived from observed work, and [ADR 0011](0011-routing-on-a-measured-profile-deferred.md) deferred the battery indefinitely. **The instrument changed; the question did not.** It is restated here against the thing that actually ships.

> **Progress note.** `bin/study_report.py` computes Q1, Q2 and Q2b retrospectively from an existing `evidence.jsonl` — no new instrumentation was needed, because every unaided repository event already carries its own later outcome (its `failed` flag). This does not answer the questions; it only means the answer is a command away once enough real usage has accumulated. Status stays **unrun**: a first look at one person's own log is not the study, which still needs the ≥5-tasks-per-condition, preregistered, multi-week design under "Method constraints" below.

## Context

Every decision in this repository depends on one unverified assumption: **that the level a concept carries predicts real-work proficiency.**

- [ADR 0001](0001-measure-the-effect.md) exists to make that level visible.
- [ADR 0002](0002-withhold-guidance-by-default.md) withholds guidance based on it — the expertise-reversal argument depends on knowing who is an expert.
- [ADR 0009](0009-graded-score-from-capped-evidence.md) computes it and concedes every constant in it is a judgement.
- [ADR 0010](0010-proficiency-decays-with-inactivity.md) ages it.
- [ADR 0011](0011-routing-on-a-measured-profile-deferred.md) would route on it, if it were built.

If a `proven` concept does not predict real capability, then the levels are noise, the dashboard is a confident view of a guess, and the product's central claim — *"a score you did not award yourself"* — is true about the mechanism and empty about the meaning. The design does not degrade gracefully in that case. It collapses to a measurement of who typed what, which is [ADR 0001](0001-measure-the-effect.md) and nothing more.

This is not a hypothetical risk to note and proceed past. It is the load-bearing claim.

**What changed with the instrument.** The battery was to be validated *before* it was built, because it was pure cost until it predicted something. The score is different: it is derived from work the user was doing anyway, so it is cheap to collect and already accumulating. That makes the study easier to run and removes the argument for blocking implementation on it — but it removes none of the risk, because an unvalidated number shown to a user is a claim whether or not it was cheap.

## Decision

> Profile validity is the critical path. The study is preregistered, cheap, and specified to be falsifiable. Until it returns, no level may be described to a user as more than *what was observed*.

## Rationale

- **It is cheap to test.** No new product is needed. `evidence.jsonl` already records concept, source, assistance and date; what is missing is a later unassisted outcome to correlate against.
- **A negative result is a real result.** If the level does not predict, the honest product is authorship measurement ([ADR 0001](0001-measure-the-effect.md)) with no levels at all — worth knowing before a router is built on top.
- **The failure is invisible without the study.** A level that carries no information looks exactly like one that does. Nothing in the running system can tell the difference, which is why it needs an outside measurement rather than more tests.

## The study

**Q1 — Does the level predict unassisted real-work proficiency?** Take the concepts a profile rates `proven`, `recall` and `unproven`. Over the following weeks, record actual unassisted performance on those same concepts in real work. If levels and outcomes agree at better than chance, the score carries information. If not, it is an expensive activity log.

**Q2 — Does the score under-rate experts?** Compare levels against demonstrated performance **separately for concepts used frequently vs. rarely**. The specific risk here is structural, not statistical: `proven` requires two distinct unaided repository tasks, so an expert who simply has not done two scoreable tasks in a concept is recorded at `recall` indefinitely. If the frequently-used set is systematically under-rated, the threshold is measuring opportunity rather than capability.

**Q2b — Does `assistance: partial` carry information?** It is the one self-reported coefficient in the model. If `partial` outcomes are indistinguishable from `none` outcomes, the coefficient is decoration and should be cut rather than defended.

**Q3 — Adaptive vs. uniform vs. none.** Three conditions, randomised per task: adaptive gating, uniform gating, no gating. Contingent on Q1 succeeding, and contingent on a router existing. Predicts the adaptive condition wins; a real chance it does not.

**Q4 — Do stated preferences match what works?** Record the chosen tutorial format and the subsequent justification outcome. If format choice predicts nothing about outcome, preference is decoration and should stop being a first-class input.

## Preregistered predictions, with real chances of failing

1. The score will **under-rate concepts the user is expert in but has not recently done scoreable work on**, because the two-task threshold measures opportunity as well as capability. If this holds, `proven` needs a path that does not depend on task count.
2. **`partial` and `none` may produce indistinguishable outcomes**, because the hook cannot see whether the user read a tutorial first and the assistant's estimate is a guess. If so, the coefficient should be cut.
3. **The judgment gate may pass justifications that later fail on the same concept.** It is a model output with no ground truth. If judge-sound answers fail at the rate of judge-unsound ones, the third gate is ceremony.

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

- **Positive**: the highest-risk assumption is named, and the data needed to test it is already being collected rather than waiting on a build.
- **Negative**: the product ships levels it cannot yet justify. This is mitigated by saying so — in the README, in `DESIGN.md`, and in what the assistant is permitted to claim — and not otherwise.
- **Negative**: an N=1 study cannot distinguish "the score is invalid" from "the score is invalid for me." The version worth running later — 10–20 developers, measuring unassisted outcomes against recorded levels — is a weekend of work and has not been run by anyone in this space. This is deliberately weaker evidence than the multi-subject studies the README cites to motivate the product at all (Bastani et al., N≈1000; METR, N=16 developers × 246 tasks) — a result from this study is a first signal about this design, not a replication at their strength, and must not be reported or cited as if it were.
- **Follow-ups**: if Q1 fails, [ADR 0002](0002-withhold-guidance-by-default.md), [0009](0009-graded-score-from-capped-evidence.md), [0010](0010-proficiency-decays-with-inactivity.md) and [0011](0011-routing-on-a-measured-profile-deferred.md) all require revision, and the product reduces to [ADR 0001](0001-measure-the-effect.md).

## Backlinks

- [ADR index](README.md)
- [ADR 0001 — Measure the effect](0001-measure-the-effect.md)
- [ADR 0009 — A graded score](0009-graded-score-from-capped-evidence.md)
- [ADR 0011 — Routing, deferred](0011-routing-on-a-measured-profile-deferred.md)
