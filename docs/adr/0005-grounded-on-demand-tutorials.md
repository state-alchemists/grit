# ADR 0005 — Ground every tutorial in a task with a check

- **Status**: Accepted
- **Date**: 2026-09-13
- **Deciders**: Go Frendi
- **Context tags**: tutorials, on-demand, verification, transfer

## Context

Users should be able to ask for a tutorial on anything. That is a reasonable product expectation, and it sits awkwardly against two findings.

**First, the evidence against untethered tutorials.** Roll, Aleven, McLaren & Koedinger built a Help Tutor plus Self-Assessment Tutor plus classroom instruction that durably improved help-seeking **behaviour** — it persisted after the tutor was switched off and transferred to new content — and produced **no domain-learning effect**. Both groups improved equally. Aleven et al.'s own retrospective summary of the line: **"help helps, but only so much."**

A tutorial with no task attached has no retrieval event and no check. It is the configuration that produced zero measurable learning despite working as designed.

**Second, transfer is weak across the whole mechanism family.** [St. Hilaire, Chan & Ahn (2024)](https://doi.org/10.3758/s13423-023-02359-2), meta-analysis: pretesting benefit for the *tested* material is **g = 0.54**, but the general (transfer) benefit is **g = 0.04** — essentially nil. Mastery programmes show **d ≈ 0.5 on teacher-made tests but ≈ 0.08 on standardised tests** ([Kulik et al. 1990](https://doi.org/10.3102/00346543060002265), 108 evaluations).

**Third, a contradiction inside the design.** ADR 0001 requires a profile precisely because the user's claim of knowledge cannot be trusted. But "I want to learn X" is the same self-assessment, pointed the other way. The same faculty cannot be untrustworthy for routing *out* of a tutorial and authoritative for routing *into* one.

## Decision

> Every tutorial is generated against a task with an acceptance check. "Teach me X" creates a task, not a lesson. A tutorial library is not built.

Three entry points, in order of support:

| Trigger | Mechanism | Evidence |
|---|---|---|
| **Gap hit on a real task** | Attached to work with an acceptance check | Supported — this is the retrieval-and-apply case |
| **On-demand request** | Creates a task with a check; tutorial generated for the gap actually hit | Equivalent to the above once grounded |
| **Browse a library** | External guidance, no task attached | Contraindicated for experts (ADR 0003); zero learning gain in Roll et al. |

## Rationale

- **Grounding resolves the contradiction rather than banning the feature.** On-demand survives; what it cannot be is a lesson to read. The user keeps the self-directed feel and the design keeps verification.
- **A check is what makes "justify the result" meaningful.** With ground truth, a wrong justification is *detectably* wrong. Without it, evaluation collapses to internal coherence and the system agrees with confident nonsense.
- **A library is the course-platform path.** Every learning product that mistook content for practice ends there, and the evidence above says this one would arrive with no measurable benefit.

## Alternatives Considered

- **Open on-demand lessons, no task** — rejected. The most useful-feeling option and the least supported; also the exact self-report asymmetry ADR 0001 rejects.
- **Gap-triggered only, no on-demand at all** — rejected as too restrictive. Users legitimately want to learn things their current work does not require; grounding keeps this while preserving the check.
- **Build a persistent tutorial library over time** — rejected. Cached tutorials are reused per concept (a performance optimisation), but browsing is a different product with different evidence, and mixing them drifts the design.

## Consequences

- **Positive**: no artifact exists in the product whose value is unverifiable. Every tutorial terminates in a check and a justification.
- **Negative**: on-demand feels heavier than browsing. The user asked to learn something and was handed work — correct on the evidence, worse as a demo.
- **Negative**: in **ungrounded domains** (non-coding), there is no oracle, so this ADR cannot hold. General mode carries a weaker guarantee and the documentation must say so rather than let the coding guarantee appear to transfer.
- **Follow-ups**: measure whether grounded on-demand outperforms gap-triggered (Q4 in the study).

## Backlinks

- [ADR index](index.md)
- [ADR 0001 — Route on measured proficiency](0001-route-on-measured-proficiency.md)
- [ADR 0003 — Withhold guidance by default](0003-withhold-guidance-by-default.md)
