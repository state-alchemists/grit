# ADR 0014 — A graded score, derived from capped evidence

- **Status**: Accepted — supersedes [ADR 0010](0010-profile-derived-from-ledger.md)
- **Date**: 2026-09-13
- **Deciders**: Go Frendi
- **Context tags**: scoring, proficiency, anti-farming, scope

## Context

The product had no way to answer *"what can I do?"*. ADR 0010 derived a profile from tutorial completions only, which — with no tutorial generator — meant the profile could never be populated (see the addendum on [ADR 0002](0002-required-profile-with-decay.md)). The working measurement, assistant authorship, fed nothing.

The scope was then set explicitly: a score that proves capability, earned from **either** a real repository task **or** a tutorial; full credit for unaided work, partial when the assistant helped but the human still wrote it, none when the assistant wrote it; and repeating the same tutorial must not keep paying.

That last constraint is what makes a score defensible here at all. Earlier documents rejected scoring outright — *"a score people can farm makes the record say whatever they want"* — and that objection is correct about **accumulated** scores. It is not an objection to a score **derived from evidence with diminishing weight**, which is what this ADR specifies.

## Decision

> A concept's score is the capped sum of its evidence, where each event is worth `source_weight × assistance × novelty`, and `proven` additionally requires two distinct unaided repository tasks.

| Factor | Values | Why |
|---|---|---|
| `source_weight` | repo **0.5**, sandbox **0.2** | A JavaScript exercise about token buckets is not shipping one in your own service |
| `assistance` | none **1.0**, partial **0.5**, full **0.0** | If the assistant wrote it, the concept earns nothing. `partial` exists so taking a hint is worth recording rather than hiding |
| `novelty` | `1/(1+repeats)`, **capped at 1.5 × weight per distinct task** | Repetition is practice, not new evidence |

A task's identity is `(source, project, task)` for repository work and `(source, task)` for tutorials. Repository task ids are per-project sequences, so `001` in two repositories is two tasks; without the project in the key they collided and two genuine unaided tasks scored 0.75/recall instead of 1.00/proven — silently penalising anyone working across more than one codebase. Tutorials are deliberately unscoped: they live in one place per person, so the same exercise is the same exercise wherever it is run, and repeating it decays no matter which repo you are sitting in.

Levels: `unproven` → `recall` at **0.30** → `proven` at **0.80 and ≥ 2 distinct unaided repository tasks**. Failures subtract 0.25. Evidence older than 90 days counts half.

Evidence lives in `~/.grit/evidence.jsonl`; the score is recomputed from it, never stored.

## Rationale

The calibration is the decision — the shape alone does not constrain anything. Two numbers were wrong in the first draft and both were caught by running the model rather than reading it:

- **A single unaided task scored 1.0 and went straight to `proven`.** One instance is a data point, not a capability. Weights were halved so one task reaches `recall` and two reach `proven`.
- **`1/(1+n)` decay was not enough.** It is a harmonic series: six runs of one tutorial still added 0.49 and reached `proven`. Slow decay is not a ceiling. `PER_TASK_CAP` makes it a hard one.

The **two-task** requirement closes the last gap. With one, a well-ground tutorial could top a single real task over the threshold; with two, the only route to `proven` is doing the work twice, unaided, in a real repository.

Verified end to end:

```
1 unaided repo task                 0.50  recall
+ same tutorial ground 6x           0.80  recall    (capped; still not proven)
+ a task the AI wrote               0.80  recall    (contributes exactly 0)
+ a 2nd distinct unaided task       1.00  proven
```

## Consequences

- **The profile can finally be populated**, from repository work alone. ADR 0002's blocked status is lifted for the repo path; tutorials remain a second source whose generator is unbuilt.
- **Scoring depends on authorship verification.** `verify_edit.py` maps its verdict to `--assistance`, so the coefficient is observed rather than declared. `UNVERIFIED` maps to `full` — if nobody can prove who typed it, it does not count as theirs.
- **The score can go down**, from failures and from ageing. That is the point; a figure that only rises is a vanity metric.
- **The numbers are judgement, not measurement.** 0.5, 0.2, 0.3, 0.8, 1.5, two tasks — every one is a choice. They are internally consistent and defensible, and none of them is validated against whether a `proven` concept predicts real capability. That study is still ADR 0007's, still unrun.
- **Proficiency is per person, not per project**, and stays in `~/.grit/evidence.jsonl`. Learning token buckets in one repository does not un-learn them in the next. Only the raw observations — the authorship log and the snapshots — are per project, because that is where the work happens. Each evidence row records which project it came from, so provenance is inspectable even though the score is not partitioned.
- **Concept names are the schema, and they are chosen in conversation.** That makes naming a correctness concern, not a style one, and it fails silently in two directions. *Fragmentation* — `token-bucket` vs `token_bucket` — splits one concept's evidence so it can never reach `proven`, and looks like the product is broken. *Collision* — `middleware` meaning two different things in two repositories — merges unrelated evidence and inflates a level. Mitigated three ways: `score.py concepts` lists what exists, `score.py record` warns on a near-duplicate name before writing, and `SKILL.md` requires the assistant to read the list before proposing and to name the *transferable* idea, qualifying it only where the knowledge does not transfer. None of that is enforcement — the user owns their names — but the silent case is now a loud one.
- **`assistance: partial` is self-reported by the assistant.** The hook proves the human typed the bytes; it cannot see whether they read a tutorial first. This is the one soft coefficient in the model and it should be named as such rather than hidden.

## Alternatives Considered

- **XP / streaks / levels** — rejected, and this is the objection the earlier documents were right about: an accumulated number is farmable, and a farmed record is worthless.
- **Binary, unaided-or-nothing** — rejected. It punishes asking questions, which is the healthiest observed way to use an assistant, and it pushes people to hide help rather than record it.
- **Two separate tracks, never combined** — the most honest option and rejected on purpose: the requirement was a score that proves capability, and two numbers prove less clearly than one level per concept.
- **A single global number** — rejected. Most legible, most gameable, furthest from evidence.
- **Geometric decay without a cap** — rejected; `0.5^n` converges to 2× base, which still lets one repeated repository task reach `proven`.

## Backlinks

- [ADR index](index.md)
- [ADR 0010 — Profile derived from ledger](0010-profile-derived-from-ledger.md) (superseded)
- [ADR 0002 — Required profile](0002-required-profile-with-decay.md)
- [ADR 0008 — Sandbox is a weaker oracle](0008-interactive-sandbox-tutorials.md)
