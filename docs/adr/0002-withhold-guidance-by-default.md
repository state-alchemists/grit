# ADR 0002 — Withhold guidance by default; grant it narrowly and adaptively

- **Status**: Accepted
- **Date**: 2026-09-13
- **Deciders**: Go Frendi
- **Context tags**: expertise-reversal, scaffolding, tutorials, cognitive-load

## Context

The product's target user is an experienced developer. It offers tutorials, probe questions, and socratic feedback — all of which are **external guidance**. A large body of evidence says guidance designed for novices becomes redundant or actively harmful for experts.

Kalyuga, Ayres, Chandler & Sweller (2003), *Educational Psychologist* 38(1):23–31:

> "Instructional techniques that are highly effective with inexperienced learners can lose their effectiveness and even have negative consequences when used with more experienced learners."

Quantified in Kalyuga (2007), *Educational Psychology Review* 19:509–539, across studies totalling **>2,200 students**, conservative effect-size differences ranged **0.45 to 2.99, mid-range 1.72**:

| Study | Novice ES | Expert ES |
|---|---|---|
| Kalyuga et al. (1998) — fault-finding | **+1.89** | **−0.88** |
| Lee et al. (2006) — iconic vs. symbolic simulation | **+1.60** | **−1.39** |
| Kalyuga & Sweller (2004) — worked examples vs. problem solving | **+1.20** | **−0.36** |

The mechanism is cognitive load: guidance substituting for a novice's missing schemas becomes *redundant* for an expert, and reconciling the overlap consumes working memory.

Independently corroborated from a different literature: Roll et al. (2014) found hints aided learning at *medium* skill, while **unattended attempts were more effective at both low and high skill** — the same non-monotonic shape, found from a different direction.

An earlier design in this repository made step-gating (the user states what code must do before seeing it) the *default for every generation*. That mechanism has real support — [Kazemitabaar et al., IUI 2025](https://arxiv.org/abs/2410.08922) found it beat six alternatives, N=82 + N=42 — but **on novice programmers doing short educational tasks**. Applying it uniformly to experienced developers inverts the population the evidence came from.

## Decision

> Guidance is withheld by default and granted narrowly, adaptively, and only on measured evidence that a specific concept is unfamiliar.

Concretely: no uniform step-gating, no blanket per-mission tutorials, and no conventional code review as feedback. Intervention fades in on evidence of unfamiliarity and fades out on evidence of fluency. Friction is the exception, earned by demonstrated need.

## Rationale

- **The population mismatch is disqualifying for uniform scaffolding.** Every expertise-reversal study is in school or vocational populations, but the *direction* is consistent and the magnitude is large. Where evidence is population-mismatched, the safe default is the one that does not apply guidance.
- **Adaptivity is the literature's own prescription.** Kalyuga & Sweller (2004) found learner-adapted instruction beat non-adapted, **ES 0.46, rising to 0.55 (knowledge) and 0.69 (efficiency)** when both expertise and cognitive load drove adaptation.
- **The costs are asymmetric.** Withholding too much means a user stays stuck and asks — recoverable in one turn. Over-guiding an expert wastes attention on every task and is invisible to them, which is the entire failure this product addresses.

## Alternatives Considered

- **Step-gating at every generation** — rejected as default. Evidenced, but on novices and short tasks; contraindicated for experts at mid-range ES 1.72. Retained for concepts *measured* as unfamiliar.
- **Uniform per-mission tutorials** — rejected. Same reason, and tutorials are the most guidance-dense artifact in the design.
- **Withhold everything; never intervene** — rejected. Reduces the product to a mirror and discards the one mechanism with a controlled comparison behind it.
- **Ask how much guidance the user wants** — partially adopted and bounded. Format, depth, and pace are askable; *whether* guidance is needed is measured.

## Consequences

- **Positive**: the product does not impose novice scaffolding on experts, which is the single largest known harm risk in this design space.
- **Negative**: adaptivity requires knowing proficiency per concept. That is the critical path (ADR 0012), and if proficiency cannot be inferred, this decision collapses — the design reverts to either uniform scaffolding (which reverses) or none (which is a mirror).
- **Negative**: **guidance still occurs.** One probe question is asked per unprofiled concept, and the expertise-reversal literature applies to *questions* too. Whether one question falls under the harm threshold is untested.
- **Follow-ups**: instrument the probe itself — how often does it fire, and does firing correlate with worse outcomes for high-proficiency users? That is the measurement that would falsify this ADR.

## Backlinks

- [ADR index](README.md)
- [ADR 0011 — Routing, deferred](0011-routing-on-a-measured-profile-deferred.md)
- [ADR 0003 — Grounded on-demand tutorials](0003-grounded-on-demand-tutorials.md)
- [ADR 0012 — The critical path](0012-profile-validity-is-the-critical-path.md)
