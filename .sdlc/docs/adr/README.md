# Architecture Decision Records

Decisions are recorded here rather than in prose design documents, so that a future reader can reconstruct *why* the design is shaped the way it is — including which options were rejected and what evidence drove the choice.

Numbers run in reading order, not in the order the decisions were taken: everything here was decided in one design pass, so chronology carries no information and a number that tells you where to start does.

**Superseded decisions do not get their own file.** When a decision is replaced, it is folded into the ADR that replaced it, as a rejected alternative with the reason it failed. A record nobody should act on is not worth a place in the index, and the reasoning is only useful next to the decision that overruled it. Consolidated on 2026-09-14, and again on 2026-09-27 when tutorials were removed: 0004–0006 are folded into 0003 and their numbers are not reused, so a gap in the sequence is a fold, not a missing file. The originals are in git history.

## Index

| ADR | Title | Status | What it decides |
|---|---|---|---|
| [0001](ADR-0001-measure-the-effect.md) | Measure the effect; make the invisible visible | Accepted | Measurement is the foundation, not a feature |
| [0002](ADR-0002-withhold-guidance-by-default.md) | Withhold guidance by default; grant it narrowly and adaptively | Accepted | The intervention policy, driven by the expertise reversal effect |
| [0003](ADR-0003-repository-work-is-the-only-evidence.md) | Repository work is the only evidence; tutorials are removed | Accepted | The one evidence source, and why tutorials, the ledger and gates went. Folds in the former 0003–0006 |
| [0007](ADR-0007-hooks-must-fail-open.md) | A hook must fail open, and the guard belongs in the registration | Accepted | Why a broken hook must never block a tool call |
| [0008](ADR-0008-dashboard-polls-files-it-does-not-push.md) | The dashboard polls files; nothing pushes | Accepted | The end-to-end data path, with a diagram |
| [0009](ADR-0009-graded-score-from-capped-evidence.md) | A graded score, derived from capped evidence | Accepted | How work becomes a level, and why it cannot be farmed |
| [0010](ADR-0010-proficiency-decays-with-inactivity.md) | Proficiency decays with inactivity | Accepted | Whether a stored level stays true |
| [0011](ADR-0011-routing-on-a-measured-profile-deferred.md) | Routing on a measured profile, and why it is deferred | Accepted — **partly built** | How the product decides who is offered guidance; the battery and probe are unbuilt |
| [0012](ADR-0012-profile-validity-is-the-critical-path.md) | Profile validity is the critical path | Accepted — **unrun** | What must be tested for any of this to mean anything |

**Accepted — deferred** means the decision stands but nothing implements it. **Accepted — unrun** means it specifies a study nobody has done.

For how the system actually works — processes, files, invariants — read [architecture.md](../architecture.md) first. These records say *why*, not *what*.

## Reading order

The numbers are the reading order. If you want less than all of it:

- **Read one**: [0012](ADR-0012-profile-validity-is-the-critical-path.md). It names what would make everything else wrong.
- **Read three**: [0001](ADR-0001-measure-the-effect.md) (why measure at all) → [0009](ADR-0009-graded-score-from-capped-evidence.md) (how work becomes a level) → [0012](ADR-0012-profile-validity-is-the-critical-path.md) (why that might mean nothing).
- **Building on it**: [0007](ADR-0007-hooks-must-fail-open.md) and [0008](ADR-0008-dashboard-polls-files-it-does-not-push.md) are the ones with invariants you can break by accident.

## What was rejected, and where it lives

Rejected options are documented inside the ADR that rejected them. The four most tempting to reintroduce:

- **Per-mission mode selection** (*walkthrough / attempt / solve*) — the original design. Measured failing by Kapoor et al. (2025, N=885): 50% bypass, worst among those who needed the friction most. See [0011](ADR-0011-routing-on-a-measured-profile-deferred.md).
- **Mini-games as the onboarding instrument** — a game measures ability in the game, and under-rates the experts it would then route into guidance they do not need. See [0011](ADR-0011-routing-on-a-measured-profile-deferred.md).
- **A profile derived from tutorial completions alone** — tried and superseded: its only input was the one thing nothing generates, so the profile could never be populated. See [0009](ADR-0009-graded-score-from-capped-evidence.md).
- **Tutorials as a second evidence source** — built, never used, removed: the page's check was invisible to the daemon and its judge credential unreachable in practice. See [0003](ADR-0003-repository-work-is-the-only-evidence.md).
- **XP, streaks, and an accumulated score** — a number you add to is a number you can farm. See [0009](ADR-0009-graded-score-from-capped-evidence.md).

## Consequences across all ADRs

Most consequences of the set are stated once, where they belong: what is unproven in [DESIGN.md §4](../DESIGN.md) (the unvalidated constants, the judgment of a justification, practice-repository transfer), the one evidence source in [0003](ADR-0003-repository-work-is-the-only-evidence.md), the two-task `shipped` gate in [0009](ADR-0009-graded-score-from-capped-evidence.md). Three belong to no single record:

- **The router is one rule** ([0011](ADR-0011-routing-on-a-measured-profile-deferred.md)): guidance is pre-selected only on a recorded failure. That is the adaptivity [0002](ADR-0002-withhold-guidance-by-default.md) asks for at its narrowest, and it is still the largest gap between the recorded design and the running product — there is no battery and no probe.
- **The record is per-machine, not per-person.** One `~/.grit/evidence.jsonl` cannot distinguish two users sharing a machine, and does not follow a user between machines.
- **Everything is plaintext under `~/.grit`** — every concept failed, every project worked in. Loopback-only and never transmitted is the entire privacy claim ([DESIGN.md §3](../DESIGN.md)); it is a real boundary, and it is the only one.
