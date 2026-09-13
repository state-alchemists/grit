# ADR 0008 — Interactive sandbox tutorials, with a declared evidence gap

- **Status**: Accepted
- **Date**: 2026-09-13
- **Deciders**: Go Frendi
- **Context tags**: tutorials, interactivity, runtime, grounding, verification

## Context

ADR 0005 established that a tutorial must be grounded in a task with an acceptance check. The question left open was *what the tutorial actually is* — a document to read, or something the user executes.

The tutorial is interactive: a JavaScript sandbox that runs in the dashboard, where the user writes code and a check passes or fails immediately. Presentation is adjustable by the user's stated preference (format, depth, pace), but the core interaction is **doing the exercise**, not reading or observing.

This creates a real tension with ADR 0003 and ADR 0005 that must be stated rather than smoothed over.

**Against ADR 0003:** an interactive tutorial is the most *guidance-dense* artifact in the entire design. It is scaffolding, step structure, and explicit instruction — everything the expertise reversal effect says is redundant and costly for a proficient user. The defence is that ADR 0003's policy is *narrow* and *adaptive*: the tutorial fires only on measured unfamiliarity with the specific concept. An interactive sandbox for a concept you have demonstrated you don't know is not the harm case. An interactive sandbox for a concept you do know is, and ADR 0001 exists to prevent it.

**Against ADR 0005:** the check runs in a JavaScript sandbox, not against the user's repository. The user's actual code is Go, or Python, or Rust. A token refill implemented in JavaScript and verified in JavaScript is **synthetic** — it is a check, but it is not their check.

## Decision

> Tutorials are interactive JavaScript sandboxes rendered in the dashboard, in which the user writes code to satisfy an executable check. Preference adjusts presentation, not interactivity. **The sandbox check is a weaker guarantee than the repository check, and the product must not claim otherwise.**

## Rationale

- **"Do the exercise" is the strongest interaction available.** It produces a retrieval event with immediate feedback — the configuration the testing-effect literature supports ([Rowland 2014](https://doi.org/10.1037/a0037559), **g = 0.50**) and the one Kazemitabaar et al. (IUI 2025) found beat six alternatives.
- **Presentation is genuinely a preference; interactivity is not.** Format, depth, and pace govern *how* the exercise is delivered and are cheap to get wrong. Whether the user writes code is the mechanism. This keeps the delegation boundary intact (ADR 0001).
- **Real repo work is still available** and is the stronger path. The sandbox is what fires when a concept must be taught *before* touching the repo; once the concept is in play on real code, the repository check governs.

## Alternatives Considered

- **Panel in the real editor, checks against the repo only** — rejected as the sole mechanism. It cannot teach a concept the user has never met: there is nothing to write against until they understand the concept, which is circular. Retained as the second half of the loop.
- **Predict-and-observe** — rejected as the primary interaction. Lower expert cost and legitimate as a *variant* for users who prefer it, but the transfer evidence is weak (St. Hilaire et al. 2024: **g = 0.54 tested, g = 0.04 transfer**) and it produces no artifact.
- **Explore-the-mechanism simulation** — rejected as the primary interaction. Strong for building intuition, but it produces no retrieval event, so it is the weakest option by evidence.
- **Read-only tutorial documents** — rejected. This is Roll et al.'s zero-domain-learning configuration (ADR 0005).

## Consequences

- **Positive**: tutorials are executed, not read, and the check is immediate. The strongest supported interaction is the default.
- **Negative**: **the sandbox is a weaker oracle than the repository.** A user can pass a JavaScript rate-limiter exercise and still be unable to implement one in their Go service. The measurement layer must record which kind of check closed a task and must not treat them as equivalent.
- **Negative**: sandbox exercises must be *authored*, and a bad exercise teaches a bad lesson. The item bank for tutorials is a maintenance burden with the same staleness risk as the concept taxonomy (§ Design 7.5).
- **Negative**: this is the guidance-densest artifact in the product. If ADR 0001's routing is even slightly wrong, this is the component that converts routing error into expertise-reversal harm. **ADR 0007 is a harder prerequisite because of this decision, not a softer one.**
- **Follow-ups**: does a sandbox pass transfer to repository performance on the same concept? That is a specific, cheap test and it is not in the current study. It should be added to Q1.

## Backlinks

- [ADR index](index.md)
- [ADR 0001](0001-route-on-measured-proficiency.md) · [0003](0003-withhold-guidance-by-default.md) · [0005](0005-grounded-on-demand-tutorials.md) · [0007](0007-critical-path-battery-validity.md)
