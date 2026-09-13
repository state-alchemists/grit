# ADR 0010 — The profile is derived from the ledger by the daemon

- **Status**: **Superseded by [ADR 0014](0014-graded-score-from-capped-evidence.md)**
- **Date**: 2026-09-13
- **Deciders**: Go Frendi
- **Context tags**: profile, ledger, derived-state, provenance, routing

## Context

ADR 0009 made the daemon the writer of the ledger. That left a gap: the ledger records **events** ("this tutorial was completed"), but routing needs **beliefs** ("this person is weak at token buckets, at this confidence, as of this date"). DESIGN §5 specifies a profile of exactly that shape; nothing wrote it. The daemon persisted one file, `ledger.json`, keyed on a tutorial *filename*, with no per-concept value and no learner identity.

So the design had a learner model on paper and an event log in code. Three concrete deficiencies:

1. **No routing input.** The router needs per-concept proficiency; there was none.
2. **No concept normalization.** The ledger keys on `"concept": "token-bucket.html"`. Two tutorials about the same idea are two unrelated rows.
3. **No provenance.** `routing.via` exists in the task schema but never reaches the ledger, so the ADR 0007 audit — "is the *battery* the thing that's mis-routing?" — cannot be answered.

There is also a semantic question the ledger alone cannot settle: **a completed tutorial is unambiguously a negative signal** (it only fired because a gap was measured), but what does a *pass* mean? Reading it as strong evidence of proficiency is unjustified — nobody studies what they already know, and ADR 0008 already established that a sandbox check is a *weaker* oracle than a repository check.

## Decision

> **The daemon derives `profile.json` from the ledger.** The ledger is ground truth; the profile is a recomputable materialized view. **A tutorial pass is a weak positive signal, capped**: it may raise proficiency to `recall` but may never assert `strong`. Only real work (`source: work`) can assert strong proficiency.

## Rationale

- **One writer, or the profile and ledger drift.** Two processes writing state eventually disagree, and the disagreement is invisible — the worst failure mode for a measurement system. The daemon already owns the ledger; deriving from it costs nothing and cannot contradict it.
- **Derived state is recomputable.** If the derivation rule is wrong, the profile is rebuilt from events rather than repaired by hand. That is what makes the rule safe to change.
- **`recall` is the right ceiling for a sandbox pass.** It is the academic sense — "can reproduce this now" — and it is precisely what the sandbox check demonstrates. It deliberately does not claim `strong`, because ADR 0008 established that passing a JavaScript exercise does not mean the user can implement the concept in their own stack.
- **The cap is the ADR 0008 consequence made concrete.** ADR 0008 says "never present a sandbox check as a repository check." This decision is that rule expressed in the data model, where it can actually be enforced rather than merely stated.

## Alternatives Considered

- **No upgrade on pass** — rejected. It is the most conservative option and the hardest to game, but it makes tutorial work nearly invisible in the profile: a user could complete many tutorials with the profile never reflecting any of it. The routing signal would not improve at all from the one activity the product actually generates.
- **Upgrade to the source's confidence outright** — rejected. A pass would assert something the sandbox check does not demonstrate, which is the precise over-claim ADR 0008 forbids.
- **Assistant writes the profile** — rejected as the primary mechanism. More flexible (it could weigh justification quality), but it creates a second writer, and two writers on one file eventually disagree without anything surfacing the conflict.
- **Do not store a profile at all; compute at query time** — rejected, but this is the closest runner-up and remains viable. It has no staleness and no drift. It was rejected because the design needs somewhere to record *confidence that is not derivable from events* — a battery result with its own uncertainty, and decay that is a function of elapsed time rather than of any event.

## Consequences

- **Positive**: routing gets the input it needs; provenance is preserved per concept; the profile is always consistent with the ledger by construction.
- **Positive**: the ADR 0007 audit becomes possible — `source` distinguishes battery-derived from work-derived proficiency, so a mis-routing battery can be identified specifically.
- **Negative**: the daemon now owns *semantics*, not just storage. The derivation rule (how evidence maps to proficiency, how confidence accumulates, what decay does) is a model of learning, and it is unvalidated — ADR 0007's concern now lives partly in code rather than only in a study design.
- **Negative**: **subject identity is still absent.** The profile is per-machine, not per-person. One `~/.grit/profile.json` cannot distinguish two users on one machine, and cannot follow a user across machines. This is acceptable for a local single-user tool and should be stated as a limit rather than discovered.
- **Negative**: a `recall`-capped profile may **under-represent experts**, since an expert who passes a tutorial for an unfamiliar-but-adjacent concept is still recorded at `recall`. This compounds the bias already named in DESIGN §7.2.
- **Follow-ups**: the derivation rule must be **calibrated against real-work outcomes**, not just implemented. If `recall` entries fail on real work at a rate indistinguishable from `weak` ones, the mapping is not carrying information. This belongs in Q1.

## Backlinks

- [ADR index](index.md)
- [ADR 0001](0001-route-on-measured-proficiency.md) · [0002](0002-required-profile-with-decay.md) · [0007](0007-critical-path-battery-validity.md) · [0008](0008-interactive-sandbox-tutorials.md) · [0009](0009-completion-via-local-daemon.md)

---

## Superseded — 2026-09-13

This ADR derived proficiency from tutorial completions only, and capped a tutorial pass at `recall`. Both survive in spirit; neither survives in form.

What was wrong: with no tutorial generator, "derived from the ledger" meant derived from an input that never arrives, so the profile could not be populated at all. ADR 0014 replaces the ledger with an evidence file that **repository work also writes to**, and replaces the flat cap with a graded `source_weight × assistance × novelty` model.

What carries over unchanged: real work outranks a sandbox exercise, the profile is recomputed rather than stored, and no amount of sandbox activity reaches the top level.
